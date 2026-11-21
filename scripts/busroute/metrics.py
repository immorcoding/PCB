"""The metrics of one build (PROC-4; columns in docs/tools.md): one JSON, one Chinese text table.

external(board file, nets)   what KiCad says about the written board: DRC (unconnected, items by type, split
                             into "touches a net of the group" and "elsewhere"), net lengths as DRC measures
                             them (a probe rule), scripts/track_shape.py, scripts/dru_canary.py. The four
                             run at the same time.
collect(...)                 the dict that is saved as metrics.json
table(m)                     the same as text
"""
import collections, os, re, subprocess, sys, threading

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = '(version 1)\n(rule "busroute_probe"\n  (constraint length (max 0.001mm)))\n'


def _drc_probe():
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    import drc_probe
    return drc_probe


def external(pcb, nets, refill=True, canary=True):
    dp = _drc_probe()
    nets, res, err = set(nets), {}, []

    def job(key, fn):
        try:
            res[key] = fn()
        except Exception as e:                              # reported, never swallowed
            err.append("%s: %s" % (key, e))

    def shape():
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "track_shape.py"), pcb], capture_output=True, text=True, encoding="utf-8", errors="replace")
        return r.stdout

    def can():
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "dru_canary.py"), pcb], capture_output=True, text=True, encoding="utf-8", errors="replace")
        return {"ok": r.returncode == 0, "text": ((r.stdout or "").strip().splitlines() or [""])[-1]}

    jobs = [("drc", lambda: dp.run_drc(pcb, refill=refill)), ("probe", lambda: dp.run_drc(pcb, PROBE)), ("shape", shape)]
    if canary and os.path.isfile(os.path.splitext(pcb)[0] + ".kicad_dru"):
        jobs.append(("canary", can))
    th = [threading.Thread(target=job, args=j) for j in jobs]
    [t.start() for t in th]
    [t.join() for t in th]
    if err:
        raise RuntimeError("; ".join(err))
    drc = res["drc"]
    mine = lambda v: any(dp.net_of(i) in nets for i in v["items"])
    def rows(vs):
        return [{"type": v["type"], "text": v["description"], "items": [i["description"] for i in v["items"]],
                 "at": [v["items"][0]["pos"]["x"], v["items"][0]["pos"]["y"]] if v["items"] and "pos" in v["items"][0] else None} for v in vs]
    vg = [v for v in drc["violations"] if mine(v)]
    ug = [v for v in drc["unconnected_items"] if mine(v)]
    lens = {}
    for v in res["probe"]["violations"]:
        if v["type"] == "length_out_of_range":
            lens[dp.net_of(v["items"][0])] = dp.numbers(v)[-1]
    txt = res["shape"]
    ts = {"lines": []}
    for k in ("off-grid", "staircase", "sharp", "crowded"):
        m = re.search(r"^%s: (\d+)" % k, txt, re.M)
        ts[k] = int(m.group(1)) if m else None
    m = re.search(r"^tiny \(< 0.1 mm\): (\d+)", txt, re.M)
    ts["tiny"] = int(m.group(1)) if m else None
    m = re.search(r"^(\d+) segments, (\d+) arcs", txt, re.M)
    ts["segments"], ts["arcs"] = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    kind = None
    ts["group"] = collections.Counter()
    for l in txt.splitlines():
        m = re.match(r"^(off-grid|staircase|sharp|crowded): ", l)
        if m:
            kind = m.group(1)
        elif l.startswith("    ") and kind and l.split()[0] in nets:
            ts["group"][kind] += 1; ts["lines"].append("%s: %s" % (kind, l.strip()))
    ts["group"] = dict(ts["group"])
    return {"drc": {"kicad": drc.get("kicad_version"), "unconnected_board": len(drc["unconnected_items"]), "unconnected_group": len(ug),
                    "unconnected_group_items": rows(ug), "by_type_board": dict(sorted(collections.Counter(v["type"] for v in drc["violations"]).items())),
                    "by_type_group": dict(sorted(collections.Counter(v["type"] for v in vg).items())), "group_items": rows(vg)},
            "drc_lengths": lens, "track_shape": ts, "canary": res.get("canary")}


def groups_table(lens, groups, ref):
    """Per group: natural lengths against the reference (its pieces summed), longest / shortest, direct spread."""
    ref = [n for n in (ref or []) if n in lens]
    ref_len = round(sum(lens[n]["length"] for n in ref), 4) if ref else None
    ref_direct = round(sum(lens[n]["direct"] for n in ref), 4) if ref else None
    out = {}
    for g, nets in groups.items():
        ns = [n for n in nets if n in lens and n not in ref]
        if not ns:
            continue
        L = {n: lens[n]["length"] for n in ns}
        D = {n: lens[n]["direct"] for n in ns}
        if ref:
            D2 = dict(D); D2["+".join(ref)] = ref_direct
        else:
            D2 = D
        lo, hi = min(L, key=L.get), max(L, key=L.get)
        out[g] = {"nets": len(ns), "longest": [hi, L[hi]], "shortest": [lo, L[lo]], "spread": round(L[hi] - L[lo], 4),
                  "to_ref": {n: round(L[n] - ref_len, 4) for n in ns} if ref else None,
                  "to_ref_range": [round(L[lo] - ref_len, 4), round(L[hi] - ref_len, 4)] if ref else None,
                  "direct_spread": round(max(D2.values()) - min(D2.values()), 4), "direct_longest": max(D2, key=D2.get), "direct_shortest": min(D2, key=D2.get),
                  "detour_total": round(sum(L[n] - D[n] for n in ns), 4)}
    return {"ref": ref, "ref_length": ref_len, "ref_direct": ref_direct, "groups": out}


def collect(info, lens, findings, hard, ext, extra):
    """info: group, board, routes file, mode, nets, limits. ext: external() or None in a fast build."""
    kinds = collections.Counter(f["kind"] for f in findings)
    nv = {n: v["vias"] for n, v in lens.items()}
    lim, tgt = info.get("via_limit"), info.get("via_target")
    gt = groups_table(lens, info["groups"], info.get("ref"))
    m = {"group": info["group"], "board": info["board"], "routes_file": info["routes_file"], "mode": info["mode"], "built": info["built"],
         "connectivity": {"paths_not_pad_to_pad": kinds.get("PATH", 0), "open_ends_listed": kinds.get("OPEN", 0),
                          "not_routed": info.get("not_routed", [])},
         "shape": {"geometry": {k: kinds.get(k, 0) for k in ("SHAPE", "CORNER", "SHARP", "VIATURN")}},
         "length": dict(gt, nets=lens, limit=info.get("len_max"), over_limit=[f["net"] for f in findings if f["kind"] == "LEN"]),
         "vias": {"max": max(nv.values()) if nv else 0, "total": sum(nv.values()), "limit": lim, "target": tgt,
                  "over_limit": sorted(n for n, v in nv.items() if lim is not None and v > lim),
                  "above_target": sorted(n for n, v in nv.items() if tgt is not None and v > tgt), "stitching": info["built"]["stitching_vias"]},
         "order": {"crossings": kinds.get("CROSS", 0), "order_problems": kinds.get("ORDER", 0),
                   "direct_spread": {g: v["direct_spread"] for g, v in gt["groups"].items()}},
         "copper": None, "rules": None,
         "clearance": {k: kinds.get(k, 0) for k in ("GAP", "PITCH", "HOLE", "VIAPAD", "EDGE", "KEEPOUT", "ZONE", "FAN", "SLOT", "CHANNEL")},
         "findings": findings, "hard_findings": hard, "profile": info["profile"]}
    if ext:
        geo_drc = {n: round(lens[n]["length"] - ext["drc_lengths"][n], 4) for n in lens if n in ext["drc_lengths"]}
        m["connectivity"].update(drc_unconnected_group=ext["drc"]["unconnected_group"], drc_unconnected_board=ext["drc"]["unconnected_board"],
                                 drc_by_type_group=ext["drc"]["by_type_group"], drc_by_type_board=ext["drc"]["by_type_board"],
                                 drc_group_items=ext["drc"]["group_items"], drc_unconnected_group_items=ext["drc"]["unconnected_group_items"])
        m["connectivity"]["pcbnew"] = ext.get("connectivity")
        m["shape"]["track_shape"] = ext["track_shape"]
        m["length"].update(drc=ext["drc_lengths"], geometry_minus_drc=geo_drc,
                           max_abs_geometry_minus_drc=max((abs(v) for v in geo_drc.values()), default=None),
                           not_measured_by_drc=sorted(n for n in lens if n not in ext["drc_lengths"]))
        m["rules"] = {"canary": ext["canary"]}
    m.update(extra)
    return m


def table(m):
    o = []
    A = o.append
    c, s, L, v, od = m["connectivity"], m["shape"], m["length"], m["vias"], m["order"]
    A("== 走线构建 %s（%s），模式：%s ==" % (m["group"], os.path.basename(m["routes_file"]), {"sketch": "线序草图（线形只报告）", "final": "正式走线"}[m["mode"]]))
    A("板：%s" % m["board"])
    b = m["built"]
    A("写入：%d 根网络，%d 段线，%d 个过孔（其中缝合地过孔 %d 个）" % (b["nets"], b["segments"], b["vias"], b["stitching_vias"]))
    A("")
    A("[连通] 不是焊盘到焊盘的线 %d；未走的网络 %d%s" % (c["paths_not_pad_to_pad"], len(c["not_routed"]), "（" + " ".join(c["not_routed"]) + "）" if c["not_routed"] else ""))
    if "drc_unconnected_group" in c:
        if c.get("pcbnew"):
            A("       从板文件读回：本组 %d 根里 %d 根的焊盘全部连通%s；pcbnew 全板飞线数 %d → %d" % (
                c["pcbnew"]["nets"], c["pcbnew"]["fully_connected"],
                "；没连通：" + " ".join(c["pcbnew"]["open"][:60]) if c["pcbnew"]["open"] and len(c["pcbnew"]["open"]) < c["pcbnew"]["nets"] else "",
                c["pcbnew"]["kicad_unconnected_before"], c["pcbnew"]["kicad_unconnected_after"]))
        A("       DRC 未连接（kicad-cli 每类最多列 499 条）：本组 %d，全板 %d；DRC 其他项：本组 %s，全板 %s" % (
            c["drc_unconnected_group"], c["drc_unconnected_board"], _cnt(c["drc_by_type_group"]), _cnt(c["drc_by_type_board"])))
        for k, why in (m.get("drc_ignored") or {}).items():
            A("       不计入的 DRC 类型 %s：%s" % (k, why))
    else:
        A("       （快速构建：没跑 DRC）")
    g = s["geometry"]
    A("[线形] 几何检查：非 0/45/90 或过短 %d，大于 45° 的拐角 %d，小倒角直角 %d，过孔处转弯 90° 及以上 %d（只列出）" % (g["SHAPE"], g["CORNER"], g["SHARP"], g["VIATURN"]))
    if "track_shape" in s:
        t = s["track_shape"]
        A("       track_shape.py（全板 / 本组）：off-grid %s / %d，staircase %s / %d，sharp %s / %d，crowded %s / %d，tiny %s；圆弧 %s 段" % (
            t["off-grid"], t["group"].get("off-grid", 0), t["staircase"], t["group"].get("staircase", 0), t["sharp"], t["group"].get("sharp", 0),
            t["crowded"], t["group"].get("crowded", 0), t["tiny"], t["arcs"]))
    A("[等长] 自然长度（没有蛇形），基准 %s%s" % (" + ".join(L["ref"]) or "无", " = %.3f mm" % L["ref_length"] if L["ref"] else ""))
    for name, gr in L["groups"].items():
        A("       组 %s（%d 根）：最长 %s %.3f，最短 %s %.3f，相差 %.3f%s；绕远合计 %.2f" % (
            name, gr["nets"], gr["longest"][0], gr["longest"][1], gr["shortest"][0], gr["shortest"][1], gr["spread"],
            "；对基准 %+.3f .. %+.3f" % tuple(gr["to_ref_range"]) if gr["to_ref_range"] else "", gr["detour_total"]))
    A("       长度上限 %s：超过的 %d 根%s" % (L["limit"] if L["limit"] is not None else "按网络类", len(L["over_limit"]), "（" + " ".join(L["over_limit"]) + "）" if L["over_limit"] else ""))
    if "max_abs_geometry_minus_drc" in L:
        A("       几何长度对 DRC 实测长度：最大相差 %s mm（%d 根有 DRC 数）" % (L["max_abs_geometry_minus_drc"], len(L["geometry_minus_drc"])))
    A("[过孔] 每根最多 %d，合计 %d；超过上限 %s 的 %d 根%s；超过目标 %s 的 %d 根%s" % (
        v["max"], v["total"], v["limit"], len(v["over_limit"]), "（" + " ".join(v["over_limit"]) + "）" if v["over_limit"] else "",
        v["target"], len(v["above_target"]), "（" + " ".join(v["above_target"]) + "）" if v["above_target"] else ""))
    A("[线序] 同层交叉 %d 处，线束顺序问题 %d 处；各线最短路径相差：%s" % (
        od["crossings"], od["order_problems"], "，".join("%s %.3f" % kv for kv in od["direct_spread"].items()) or "—"))
    cl = m["clearance"]
    A("[间距] " + "，".join("%s %d" % (k, n) for k, n in cl.items()))
    A("[铜皮] 不适用（本工具不铺铜）")
    A("[规则生效] %s" % (("金丝雀 " + ("OK" if m["rules"]["canary"]["ok"] else "失败：" + m["rules"]["canary"]["text"])) if m.get("rules") and m["rules"].get("canary") else "没跑（快速构建或没有规则文件）"))
    A("[构建] %.1f 秒%s" % (m.get("build_seconds", 0), "，第 %s 轮" % m["round"] if m.get("round") else ""))
    A("")
    A("结论：%s（会拦住构建的发现 %d 条）" % ("通过" if m.get("ok") else "不通过", m["hard_findings"]))
    for f in m["findings"]:
        if f["kind"] != "OPEN":
            A("  %s%-7s %s" % ("  " if not f.get("hard") else "! ", f["kind"], f["text"] if not f["net"] or f["net"] in f["text"] else "%s: %s" % (f["net"], f["text"])))
    if c["open_ends_listed"]:
        A("    OPEN    %d route ends are not on a pad (allowed by OPEN_ENDS; listed in metrics.json)" % c["open_ends_listed"])
    for it in [i for i in c.get("drc_group_items", []) if i["type"] not in (m.get("drc_ignored") or {})]:
        A("  ! DRC     %s: %s | %s" % (it["type"], it["text"], " / ".join(it["items"])))
    for it in c.get("drc_unconnected_group_items", [])[:40]:
        A("  ! DRC     unconnected: %s" % " / ".join(it["items"]))
    A("")
    A("网络         长度    直线距离  对基准   过孔  各层长度%s" % ("   几何-DRC" if "geometry_minus_drc" in L else ""))
    refl = L["ref_length"]
    for n in sorted(L["nets"], key=_natural):
        x = L["nets"][n]
        A("%-12s %7.3f  %7.3f  %7s  %3d   %-28s %s" % (n, x["length"], x["direct"], "基准" if n in L["ref"] else ("%+.3f" % (x["length"] - refl) if refl is not None else "—"),
                                                     x["vias"], " ".join("%s %.2f" % kv for kv in x["layers"].items()),
                                                     ("%+.4f" % L["geometry_minus_drc"][n] if n in L.get("geometry_minus_drc", {}) else "")))
    if m.get("pictures"):
        A("")
        A("图片：" + " ".join(m["pictures"]))
    return "\n".join(o) + "\n"


def _cnt(d):
    return "、".join("%s %d" % kv for kv in d.items()) if d else "0"


def _natural(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]
