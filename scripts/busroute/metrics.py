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
    m = re.search(r"^arc-joint: (\d+)", txt, re.M)           # printed only for boards with arcs
    if m:
        ts["arc-joint"] = int(m.group(1))
    kind = None
    ts["group"] = collections.Counter()
    for l in txt.splitlines():
        m = re.match(r"^(off-grid|staircase|sharp|crowded|arc-joint): ", l)
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


LEN_TOL = 0.002              # geometry length vs DRC length, mm


def length_check(geo_drc, ruled, tol=LEN_TOL):
    """Geometry length minus DRC length, split by whether the net has a length rule (a length or skew limit of
    its class, or a TUNING group). Only ruled nets decide a build: elsewhere a difference (a bend inside a pad,
    a via DRC counts differently) changes no rule's verdict and is listed as a note.
    -> {"max_ruled": mm or None, "notes": {net: diff} of unruled nets beyond tol, "ok": bool}"""
    r = [abs(v) for n, v in geo_drc.items() if n in ruled]
    notes = {n: v for n, v in sorted(geo_drc.items()) if n not in ruled and abs(v) > tol}
    mx = max(r, default=None)
    return {"max_ruled": mx, "notes": notes, "ok": mx is None or mx <= tol}


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
    A("写入：%d 根网络，%d 段线，%d 个过孔（其中缝合地过孔 %d 个）%s" % (b["nets"], b["segments"], b["vias"], b["stitching_vias"],
                                                         "，%d 段圆弧" % b["arcs"] if "arcs" in b else ""))
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
        A("       track_shape.py（全板 / 本组）：off-grid %s / %d，staircase %s / %d，sharp %s / %d，crowded %s / %d，tiny %s；圆弧 %s 段%s" % (
            t["off-grid"], t["group"].get("off-grid", 0), t["staircase"], t["group"].get("staircase", 0), t["sharp"], t["group"].get("sharp", 0),
            t["crowded"], t["group"].get("crowded", 0), t["tiny"], t["arcs"],
            "，圆弧接点不相切 %s / %d" % (t["arc-joint"], t["group"].get("arc-joint", 0)) if "arc-joint" in t else ""))
    tu = m.get("tuning")
    if tu:
        gm = tu["geometry"]
        A("       蛇形几何：%d 块，%d 段圆弧；接点最大偏角 %.4f°，半径最大误差 %.6f，最短一段 %s，块内弯高最大差 %.6f；"
          "到别的铜最近 %s（clr %g），到规则区边最近 %s（area_gap %g），拐点到圆弧最短 %s（end %g）；ARC 发现 %d" % (
              gm["blocks"], gm["arcs"], gm["max_joint_deg"], gm["max_radius_error"], _mm(gm["shortest_piece"]), gm["max_height_spread"],
              _mm(gm["min_clr"]), tu["settings"]["clr"], _mm(gm["min_area_gap"]), tu["settings"]["area_gap"], _mm(gm["min_end"]), tu["settings"]["end"],
              sum(1 for f in m["findings"] if f["kind"] == "ARC")))
    A("[等长] %s，基准 %s%s" % ("长度（含蛇形）" if tu else "自然长度（没有蛇形）", " + ".join(L["ref"]) or "无", " = %.3f mm" % L["ref_length"] if L["ref"] else ""))
    for name, gr in L["groups"].items():
        A("       组 %s（%d 根）：最长 %s %.3f，最短 %s %.3f，相差 %.3f%s；绕远合计 %.2f" % (
            name, gr["nets"], gr["longest"][0], gr["longest"][1], gr["shortest"][0], gr["shortest"][1], gr["spread"],
            "；对基准 %+.3f .. %+.3f" % tuple(gr["to_ref_range"]) if gr["to_ref_range"] else "", gr["detour_total"]))
    if tu:
        for name, g in tu["groups"].items():
            if g.get("kind") == "ref":
                A("       蛇形 组 %s：基准 %s %.3f -> %.3f（目标 %.3f），窗口 %.3f .. %.3f（基准 %+g .. %+g），成员目标 %.3f；窗口内 %d / %d 根，"
                  "最差 %s 离窗口边 %+.3f；%d 块蛇形，补 %.3f mm；没补够：%s" % (
                      name, g["ref"], g["ref_natural"], g["ref_length"], g["ref_target"], g["window"][0], g["window"][1], g["lo"], g["hi"],
                      g["target"], g["inside"], g["total"], g["worst"][0], g["worst"][1], g["blocks"], g["added"],
                      "，".join("%s 差 %.3f" % kv for kv in g["missing"].items()) or "无"))
                continue
            A("       蛇形 组 %s：窗口 %.3f .. %.3f（最长 %s − %g），目标 %.3f；窗口内 %d / %d 根，最差 %s 离窗口下沿 %+.3f；%d 块蛇形，补 %.3f mm；没补够：%s" % (
                name, g["window"][0], g["window"][1], g["ref"], g["spread"], g["target"], g["inside"], g["total"], g["worst"][0], g["worst"][1],
                g["blocks"], g["added"], "，".join("%s 差 %.3f" % kv for kv in g["missing"].items()) or "无"))
        caps = tu.get("caps", {})
        A("       每根总长对上限：%s" % "，".join("%s %.3f / %s" % (n, L["nets"][n]["length"], caps.get(n) if caps.get(n) is not None else "—")
                                         for g in tu["groups"].values() for n in sorted(g["nets"], key=_natural)))
    A("       长度上限 %s：超过的 %d 根%s" % (L["limit"] if L["limit"] is not None else "按网络类", len(L["over_limit"]), "（" + " ".join(L["over_limit"]) + "）" if L["over_limit"] else ""))
    if "max_abs_geometry_minus_drc" in L:
        A("       几何长度对 DRC 实测长度：最大相差 %s mm（%d 根有 DRC 数）" % (L["max_abs_geometry_minus_drc"], len(L["geometry_minus_drc"])))
        lc = L.get("check")
        if lc:
            A("         有长度规则的网络（长度、skew 上限或蛇形组）最大相差 %s mm（上限 %g，判通过与否）；没有长度规则、相差超过 %g 的只报告：%s" % (
                "—" if lc["max_ruled"] is None else "%.4f" % lc["max_ruled"], LEN_TOL, LEN_TOL,
                "，".join("%s %+.4f" % kv for kv in lc["notes"].items()) or "无"))
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
    A("网络         长度    直线距离  对基准   过孔  各层长度%s%s" % ("                     蛇形" if tu else "", "   几何-DRC" if "geometry_minus_drc" in L else ""))
    refl = L["ref_length"]
    for n in sorted(L["nets"], key=_natural):
        x = L["nets"][n]
        A("%-12s %7.3f  %7.3f  %7s  %3d   %-28s %s%s" % (n, x["length"], x["direct"], "基准" if n in L["ref"] else ("%+.3f" % (x["length"] - refl) if refl is not None else "—"),
                                                       x["vias"], " ".join("%s %.2f" % kv for kv in x["layers"].items()),
                                                       ("%7.3f  " % x.get("tuned", 0.0)) if tu else "",
                                                       ("%+.4f" % L["geometry_minus_drc"][n] if n in L.get("geometry_minus_drc", {}) else "")))
    if m.get("pictures"):
        A("")
        A("图片：" + " ".join(m["pictures"]))
    return "\n".join(o) + "\n"


def _cnt(d):
    return "、".join("%s %d" % kv for kv in d.items()) if d else "0"


def _mm(v):
    return "—" if v is None else "%.4f" % v


def budget_table(b, group, fname):
    """The text of --tuning-budget (tune.Tuning.budget())."""
    s = b["settings"]
    o = []
    A = o.append
    A("== 等长预算 %s（%s）：只算，不画 ==" % (group, fname))
    A("设置：摆幅 amp %g 起、最高 amp_max %g；腿间距 %s；块两头各留 %g（keep）；拐点到圆弧至少 %g（end）；余量 %g" % (
        s["amp"], s["amp_max"], "，".join("%s %g" % kv for kv in s["pitch"].items()), s["keep"], s["end"], s["margin"]))
    A("容量按 RTE-2 的式子，不查间距：单侧 n = ⌊(L − 2·keep) / 2p⌋ 个弯，补 n·(2a − 0.858p)；双侧 n = ⌊(L − 2·keep) / p⌋ − 1 个弯，补 2na − 0.429p(n + 1)")
    for g, t in b["groups"].items():
        A("")
        if t.get("kind") == "ref":
            A("组 %s：基准 %s 自然长度 %.3f，最长成员 %s %.3f，窗口 基准 %+g .. %+g，余量 %g → 基准目标 %.3f（要补 %.3f），成员目标 %.3f%s" % (
                g, t["ref"], t["ref_natural"], t["longest_net"], t["longest"], t["lo"], t["hi"], s["margin"], t["ref_target"], t["ref_need"],
                t["target"], "；没有走线的：" + " ".join(t["missing_nets"]) if t["missing_nets"] else ""))
        else:
            A("组 %s：最长 %s %.3f 是基准，容差 %g，余量 %g → 目标 %.3f%s" % (g, t["ref"], t["longest"], t["spread"], s["margin"], t["target"],
                                                              "；没有走线的：" + " ".join(t["missing_nets"]) if t["missing_nets"] else ""))
        A("  %-11s %8s %8s  %-50s %4s %9s %9s" % ("网络", "自然长度", "要补", "补线位置（层，直线长，朝向，腿间距）", "弯数", "容量@%g" % s["amp"], "容量@%g" % s["amp_max"]))
        for r in sorted(t["rows"], key=lambda r: _natural(r["net"])):
            first = True
            sites = r["sites"] or [None]
            for x in sites:
                head = ("%-12s %8.3f %8.3f" % (r["net"], r["natural"], r["need"])) if first else " " * 30
                if r["net"] == t["ref"] and first and x is None:
                    A("  %s  （基准，不补）" % head)
                elif x is None:
                    A("  %s  %s" % (head, "没有补线位置" if r["need"] > 1e-3 else "（不用补）"))
                else:
                    A("  %s  %-50s %4d %9.3f %9.3f" % (head, "%s (%s, %.2f mm, %s, p %g)" % (x["site"], x["layer"], x["length"], x["side"], x["pitch"]),
                                                      x["humps"], x["cap_amp"], x["cap_amp_max"]))
                first = False
            if len(r["sites"]) > 1:
                A("  %s  %-50s %4s %9.3f %9.3f" % (" " * 30, "合计", "", r["cap_amp"], r["cap_amp_max"]))
    A("")
    A("容量不够的：%s" % ("，".join("%s 要补 %.3f，最多 %.3f" % (x["net"], x["need"], x["cap_amp_max"]) for x in b["short"]) or "无"))
    if b["sites_without_group"]:
        A("不在任何组里的补线位置（不用）：%s" % "，".join(b["sites_without_group"]))
    A("用时 %.2f 秒" % b.get("seconds", 0))
    return "\n".join(o) + "\n"


def _natural(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]
