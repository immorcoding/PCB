"""PROTOTYPE (issue 15): results of one variant after meander.py and the DRC run.

    D:\\KiCad\\bin\\python.exe tune_table.py <variant dir>     -> tune.txt (Chinese), tune_table.json

Puts side by side, per net: natural length (KiCad DRC), length added (meander.py's analytic sum),
their sum, the length KiCad's DRC measures on the tuned board (lengths.json from len_table.py), the
difference, the error to the target. Then:
  window rule  the variant's rule file is run against the UNTUNED source board (temp copy) and against
               the tuned board; the first must raise length violations (the rule is live), the second none.
  arcs         every PCB_ARC is checked from the board file: radius, length, and that both ends meet
               exactly one neighbour of the same net tangentially. scripts/track_shape.py only counts arcs.
A base board (no tune.json) only gets the window part.
"""
import collections, json, math, os, re, shutil, subprocess, sys, tempfile
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
CLI = r"D:\KiCad\bin\kicad-cli.exe"
NAME = "lentune"
mm = pcbnew.ToMM


def length_violations(report):
    """{net: description} of the length_out_of_range items in a kicad-cli DRC json."""
    out = {}
    for v in report["violations"]:
        if v["type"] == "length_out_of_range":
            m = re.search(r"\[(/[^\]]+)\]", v["items"][0]["description"]) if v["items"] else None
            nums = re.findall(r"(\d+\.\d+) mm", v["description"])
            out[m.group(1) if m else "?"] = "实际 %s，限值 %s" % (nums[-1], nums[0]) if len(nums) >= 2 else v["description"]
    return out


def drc_with_rules(pcb_dir, rules_dir):
    tmp = tempfile.mkdtemp(prefix="window_")
    try:
        shutil.copy(os.path.join(pcb_dir, NAME + ".kicad_pcb"), tmp)
        for ext in (".kicad_pro", ".kicad_dru"):
            shutil.copy(os.path.join(rules_dir, NAME + ext), tmp)
        rpt = os.path.join(tmp, "o.json")
        subprocess.run([CLI, "pcb", "drc", "--severity-all", "--format", "json", "-o", rpt, os.path.join(tmp, NAME + ".kicad_pcb")], capture_output=True)
        return json.load(open(rpt, encoding="utf-8"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def arc_check(pcb):
    B = pcbnew.LoadBoard(pcb)
    xy = lambda v: (v.x, v.y)
    items = [t for t in B.GetTracks() if t.Type() != pcbnew.PCB_VIA_T]
    at = collections.defaultdict(list)
    for t in items:
        for p in (t.GetStart(), t.GetEnd()):
            at[(t.GetNetname(), t.GetLayer(), p.x, p.y)].append(t)

    def leave(t, p):                                        # unit direction of travel away from endpoint p along t
        s, e = xy(t.GetStart()), xy(t.GetEnd())
        if t.Type() != pcbnew.PCB_ARC_T:
            o = e if p == s else s
            L = math.dist(o, p); return ((o[0] - p[0]) / L, (o[1] - p[1]) / L)
        c, m = xy(t.GetCenter()), xy(t.GetMid())
        sgn = 1 if (s[0] - c[0]) * (m[1] - c[1]) - (s[1] - c[1]) * (m[0] - c[0]) > 0 else -1
        if p != s:
            sgn = -sgn
        r = math.dist(p, c)
        return (-sgn * (p[1] - c[1]) / r, sgn * (p[0] - c[0]) / r)

    arcs = [t for t in items if t.Type() == pcbnew.PCB_ARC_T]
    radii, worst, lone, short_arc = collections.Counter(), 0.0, 0, 1e9
    for t in arcs:
        radii[round(mm(t.GetRadius()), 3)] += 1
        short_arc = min(short_arc, mm(t.GetLength()))
        for p in (t.GetStart(), t.GetEnd()):
            nb = [o for o in at[(t.GetNetname(), t.GetLayer(), p.x, p.y)] if o is not t]
            if len(nb) != 1:
                lone += 1; continue
            a, b = leave(t, xy(p)), leave(nb[0], xy(p))
            worst = max(worst, math.degrees(math.acos(max(-1, min(1, -(a[0] * b[0] + a[1] * b[1]))))))
    segs = [mm(t.GetLength()) for t in items if t.Type() != pcbnew.PCB_ARC_T and t.GetNetname().startswith("/FMC_")]
    return {"arcs": len(arcs), "radii": dict(sorted(radii.items())), "shortest_arc": round(short_arc, 4) if arcs else None,
            "worst_tangent_deg": round(worst, 4), "ends_without_one_neighbour": lone, "shortest_segment": round(min(segs), 4)}


def main(vdir):
    sys.stdout.reconfigure(encoding="utf-8")
    drc = json.load(open(os.path.join(vdir, "drc.json"), encoding="utf-8"))
    after = length_violations(drc)
    tj = os.path.join(vdir, "tune.json")
    tune = json.load(open(tj, encoding="utf-8")) if os.path.exists(tj) else None
    L = json.load(open(os.path.join(vdir, "lengths.json"), encoding="utf-8"))["nets"]
    other = collections.Counter(v["type"] for v in drc["violations"] if v["type"] != "length_out_of_range")
    js = {"drc": {"unconnected": len(drc["unconnected_items"]), "length": after, "other": dict(other)},
          "canary": open(os.path.join(vdir, "canary.txt"), encoding="utf-8").read().strip().splitlines()[-1],
          "track_shape": open(os.path.join(vdir, "track_shape.txt"), encoding="utf-8").read().strip(),
          "arcs": arc_check(os.path.join(vdir, NAME + ".kicad_pcb")),
          "geo": json.load(open(os.path.join(vdir, "geo.json"), encoding="utf-8")),
          "pour": open(os.path.join(vdir, "pour_check.txt"), encoding="utf-8").read().strip().splitlines()}
    geo_txt = open(os.path.join(vdir, "geo.txt"), encoding="utf-8").read().strip().splitlines()
    out = []
    order = lambda n: (0, 0) if "CLK" in n else (1, int(re.sub(r"\D", "", n) or 0))
    if tune:
        before = length_violations(drc_with_rules(os.path.join(HERE, tune["src"]), vdir))
        js.update(target=tune["target"], window_L=tune["window_L"],
                  params={k: tune[k] for k in ("amp", "r", "mode", "where", "trim", "leg_spacing", "goal", "end", "clr", "area_gap")},
                  window_before=before, rows=[])
        ref = L[tune["ref"]]["length"]
        out += [("目标长度 %.3f mm（这一组里自然长度最长的那根）。" if tune["goal"] == "equal" else
                 "只动 SDCLK：补到 %.3f mm（其余 8 根自然长度范围的正中），其余的线不动。") % tune["target"] +
                "参数：半径 %.2f，摆幅 %.2f 起，腿间距 %.2f，%s，%s，位置 %s。守的间距：拐点到第一个圆弧 %.2f，到别的铜 %.3f，到规则区边 %.3f。" % (
                    tune["r"], tune["amp"], tune["leg_spacing"], {"single": "单侧", "double": "双侧"}[tune["mode"]],
                    "所有弯等高，比设定摆幅略高来凑数（要补的不到约 1.64 mm 时放不下双侧，画成单侧）" if tune["mode"] == "double"
                    else {"last": "最后一个弯压低凑数", "even": "所有弯压到一样高"}[tune["trim"]],
                    {"middle": "直线段中间", "mcu": "靠 MCU", "sdram": "靠 SDRAM"}[tune["where"]], tune["end"], tune["clr"], tune["area_gap"]), "",
                "| 网络 | 自然长度 | 要补 | 实补（脚本算） | 自然+实补 | DRC 实测 | 脚本−DRC | 离目标 | 没补上 | 整弯 | 小弯 | 各弯摆幅 | 蛇形在哪 | 过孔 | 对 SDCLK |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for n in sorted(tune["nets"], key=order):
            t, m = tune["nets"][n], L[n]
            where = "；".join("%s %s侧 (%.2f, %.2f)→(%.2f, %.2f)" % (b["layer"], b["side"], b["from"][0], b["from"][1], b["to"][0], b["to"][1]) for b in t["blocks"]) or "—"
            amps = " ".join("%.2f" % a for b in t["blocks"] for a in b["amps"]) or "—"
            row = {"net": n.lstrip("/"), "natural": t["natural"], "need": t["need"], "added": t["added"], "predicted": t["predicted"],
                   "drc": m["length"], "diff": round(t["predicted"] - m["length"], 4), "err": round(m["length"] - t["goal_len"], 4),
                   "missing": t["missing"], "humps": sum(b["humps"] for b in t["blocks"]), "bumps": sum(b["bumps"] for b in t["blocks"]),
                   "amps": amps, "where": where, "vias": m["vias"], "to_ref": round(m["length"] - ref, 4)}
            js["rows"].append(row)
            out.append("| %(net)s | %(natural).3f | %(need).3f | %(added).3f | %(predicted).4f | %(drc).4f | %(diff)+.4f | %(err)+.3f | %(missing).3f | %(humps)d | %(bumps)d | %(amps)s | %(where)s | %(vias)d | %(to_ref)+.3f |" % row)
        errs = [abs(r["err"]) for r in js["rows"]]
        short = [r for r in js["rows"] if r["missing"] > 0.0005]
        js["summary"] = {"max_abs_err": max(errs), "max_abs_diff": max(abs(r["diff"]) for r in js["rows"]), "not_reached": len(short),
                         "spread_after": round(max(r["drc"] for r in js["rows"]) - min(r["drc"] for r in js["rows"]), 4)}
        out += ["", "- 补完后最长和最短差 %.3f mm；离目标最远的一根差 %.3f mm；脚本算的长度和 DRC 实测最多差 %.4f mm。" % (
                    js["summary"]["spread_after"], js["summary"]["max_abs_err"], js["summary"]["max_abs_diff"]),
                "- 没补到目标的：%s。" % ("，".join("%s 差 %.3f" % (r["net"], r["missing"]) for r in short) or "无"),
                "- 窗口规则 `sdram_window`（每根对 SDCLK ±2.5 mm，L = %.4f）：同一份规则文件套在没补的板上报 %d 根（%s）；套在补完的板上报 %d 根%s。" % (
                    tune["window_L"], len(before), "，".join(k.lstrip("/") for k in sorted(before, key=order)) or "无", len(after),
                    "（%s）" % "；".join("%s %s" % (k.lstrip("/"), v) for k, v in after.items()) if after else "")]
    else:
        out += ["- 窗口规则 `sdram_window`（每根对 SDCLK ±2.5 mm，L 取这块板上 SDCLK 的实测长度）：报 %d 根%s。" % (
                    len(after), "（%s）" % "；".join("%s %s" % (k.lstrip("/"), v) for k, v in sorted(after.items(), key=lambda kv: order(kv[0]))) if after else "")]
    a = js["arcs"]
    out += ["- DRC：未连接 %d；长度超窗 %d；其他 %s。规则金丝雀：%s" % (js["drc"]["unconnected"], len(after),
                "，".join("%s %d" % kv for kv in other.items()) or "0", js["canary"]),
            "- 圆弧（脚本从板文件逐个检查）：%d 个；半径 %s；最短圆弧 %s mm；圆弧端点和相邻线段的切向最大偏差 %.4f°；没有接上或有分叉的端点 %d 个；这组线里最短的直线段 %.3f mm。" % (
                a["arcs"], "，".join("%.3f mm × %d" % kv for kv in a["radii"].items()) or "—", a["shortest_arc"], a["worst_tangent_deg"],
                a["ends_without_one_neighbour"], a["shortest_segment"]),
            "- `track_shape.py`（不检查圆弧）：" + "；".join(l.strip() for l in js["track_shape"].splitlines())] + geo_txt + [
            "- 铺地到信号过孔：" + "；".join(js["pour"])]
    open(os.path.join(vdir, "tune.txt"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    json.dump(js, open(os.path.join(vdir, "tune_table.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1])
