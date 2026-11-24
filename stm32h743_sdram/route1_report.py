"""The metrics table of stop 6 part A (build.sh route1): the SDRAM group on the real board, with the two power groups
built after it and KiCad's own refill. One table in the eight groups of PROC-4 (columns in docs/tools.md), numbers
read from the board file, the refilled DRC report and the scripts' outputs only.

    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\route1_report.py <board> <out dir>

Reads from <out dir>: drc.json (kicad-cli, refilled), sdram/metrics.json (the SDRAM build: lengths, vias, findings),
power_bga_sites.json, slots.json, escape_bga.json (and out/copper/escape_bga.json of stop 5 to compare), measure.txt,
dru_match.txt, and the environment ROUTE1_SECONDS / ROUND. Runs scripts/track_shape.py on the board. Writes
<out dir>/table.txt and prints it; exit code 1 when a hard number is off (unconnected, clearance-type DRC items,
copper-class unconnected, a crossing, a net over 60 mm or over 3 vias, a sharp corner, a byte lane over its skew rule
sdram_lane0-3, a via of a plane's own net cut off from it). Plane slot lengths are reported only: the user removed the
slot limit (it was 3.0 mm, SLOT_MAX, still the mark in the table).
"""
import collections, json, math, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)                     # interim (Tools/ consolidation stage 1): the repository root, for Tools.KiCadDesignTools
HARD_DRC = ("clearance", "hole_clearance", "annular_width", "copper_edge_clearance", "hole_to_hole", "shorting_items", "tracks_crossing",
            "track_width", "via_diameter", "track_angle", "isolated_copper", "starved_thermal")
SLOT_MAX = 3.0
STRAIGHT = 2.5                   # straights of data / NBL nets at least this long are candidate serpentine sites


def straights(b, nets, areas):
    """{net: [(length, a, c, layer)]} of straight track runs (collinear consecutive segments joined) outside the rule areas."""
    out = collections.defaultdict(list)
    def inside(p):
        return any(R[0] <= p[0] <= R[2] and R[1] <= p[1] <= R[3] for R in areas.values())
    for n in nets:
        segs = [(lay, a, c) for nn, lay, a, c, w, _ in b.tracks if nn == n]
        # join collinear neighbours
        runs = []
        for lay, a, c in segs:
            runs.append([lay, a, c])
        merged = True
        while merged:
            merged = False
            for i in range(len(runs)):
                for j in range(len(runs)):
                    if i == j or runs[i][0] != runs[j][0]:
                        continue
                    la, a1, c1 = runs[i]; lb, a2, c2 = runs[j]
                    for p, q, r_, s in ((a1, c1, a2, c2), (a1, c1, c2, a2), (c1, a1, a2, c2), (c1, a1, c2, a2)):
                        if math.dist(q, r_) < 1e-6:
                            d1 = (q[0] - p[0], q[1] - p[1]); d2 = (s[0] - r_[0], s[1] - r_[1])
                            if abs(d1[0] * d2[1] - d1[1] * d2[0]) < 1e-9 and d1[0] * d2[0] + d1[1] * d2[1] > 0:
                                runs[i] = [la, p, s]; runs.pop(j); merged = True
                                break
                    if merged:
                        break
                if merged:
                    break
        for lay, a, c in runs:
            L = math.dist(a, c)
            if L >= STRAIGHT and not (inside(a) and inside(c)):
                out[n].append((round(L, 2), a, c, lay))
    return out


def main(board_path, odir):
    import pcbnew
    from Tools.KiCadDesignTools.routing.busroute.board import Board
    import copper_report as CR
    bad = []
    L = []
    A = L.append
    b = Board(board_path, (100, 100))
    sd = json.load(open(os.path.join(odir, "sdram", "metrics.json"), encoding="utf-8"))
    nets = sorted(sd["length"]["nets"])
    A("== 走线一 A 部分（build.sh route1）：SDRAM 组写入真板，两组电源在它之后重建，KiCad 填充后量 ==")
    A("板：%s" % board_path)
    # ---- connectivity, read back from the file
    conn = b.connectivity(set(nets))
    full = [n for n, (a, c) in conn.items() if a == c and a > 1]
    nseg = sum(1 for t in b.tracks if t[0] in nets)
    nvia = sum(1 for v in b.vias if v[0] in nets)
    side = json.load(open(os.path.splitext(board_path)[0] + ".busroute.json", encoding="utf-8"))
    stitch = [tuple(x) for x in side["groups"].get("sdram", {}).get("extras", [])]
    d = json.load(open(os.path.join(odir, "drc.json"), encoding="utf-8"))
    def net_of(it):
        m = re.search(r"\[([^\]]+)\]", it.get("description", ""))
        return m.group(1) if m else None
    mine = lambda v: any(net_of(i) in nets for i in v["items"])
    by_all = collections.Counter(v["type"] for v in d["violations"])
    by_grp = collections.Counter(v["type"] for v in d["violations"] if mine(v))
    ug = [v for v in d["unconnected_items"] if mine(v)]
    A("")
    A("[连通] 本组 %d 根网络：从板文件读回焊盘全部连通的 %d 根%s；板文件里本组的线段 %d 段、过孔 %d 个（另有本组放的地过孔 %d 个）" % (
        len(nets), len(full), "；没连通：" + " ".join(sorted(set(nets) - set(full))) if len(full) < len(nets) else "", nseg, nvia, len(stitch)))
    A("       DRC（填充后，kicad-cli 每类最多列 499 条未连接）：本组未连接 %d；全板未连接 %d；本组的其他项 %s" % (
        len(ug), len(d["unconnected_items"]), " ".join("%s %d" % kv for kv in sorted(by_grp.items())) or "0"))
    A("       全板 DRC 按类型：%s" % (" ".join("%s %d" % kv for kv in sorted(by_all.items())) or "0"))
    hard = {k: n for k, n in by_all.items() if k in HARD_DRC}
    A("       间距 / 孔 / 焊环 / 板边 / 线宽 / 角度 / 孤铜类（全板）：%s" % (" ".join("%s %d" % kv for kv in sorted(hard.items())) or "0"))
    if ug or len(full) < len(nets):
        bad.append("unconnected")
    if hard:
        bad.append("DRC " + " ".join(hard))
    for v in [v for v in d["violations"] if v["type"] in HARD_DRC][:20]:
        A("  ! %s: %s | %s" % (v["type"], v["description"], " / ".join(i["description"] for i in v["items"])))
    # copper-class unconnected (pcbnew's connectivity of the refilled board)
    bb = pcbnew.LoadBoard(board_path)
    cl = CR.clusters(bb, CR.COPPER)
    lost = {n: [g for g in gs if g is not max(gs, key=len)] for n, gs in cl.items() if len(gs) > 1}
    nlost = sum(len(v) for v in lost.values())
    A("       铜皮类未连接（pcbnew 连通块）: %d%s" % (nlost, "".join("\n         %s: %s" % (n, " | ".join(" ".join(g[:6]) for g in gs)) for n, gs in sorted(lost.items()))))
    if nlost:
        bad.append("copper unconnected")
    sp = os.path.join(odir, "power_bga_sites.json")
    if os.path.isfile(sp):
        s = json.load(open(sp, encoding="utf-8"))
        A("       BGA 电源球没有过孔位置的: %d %s" % (len(s["nosite"]), " ".join(sorted(s["nosite"]))))
        p2 = s["ball_via"].get("U301.P2")
        A("       U58: U301.P2 (+3V3_SDRAM) 的过孔 %s" % (("(%.3f, %.3f)" % tuple(p2)) if p2 else "没有"))
    # ---- shape
    r = subprocess.run([sys.executable, "-m", "Tools.KiCadDesignTools.analysis.track_shape", os.path.abspath(board_path)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    ts, kind, lines = {}, None, collections.defaultdict(list)
    for l in r.stdout.splitlines():
        m = re.match(r"^(off-grid|staircase|sharp|crowded): (\d+)", l)
        if m:
            kind = m.group(1); ts[kind] = int(m.group(2)); continue
        m = re.match(r"^tiny \(< 0.1 mm\): (\d+)", l)
        if m:
            ts["tiny"] = int(m.group(1)); kind = None; continue
        m = re.match(r"^(\d+) segments, (\d+) arcs", l)
        if m:
            ts["arcs"] = int(m.group(2))
        if l.startswith("    ") and kind and l.split()[0] in nets:
            lines[kind].append(l.strip())
    geo = sd["shape"]["geometry"]
    A("[线形] 几何检查（本组）：非 0/45/90 或过短 %d，大于 45° 的拐角 %d，小倒角直角 %d，过孔处转弯 90° 及以上 %d" % (geo["SHAPE"], geo["CORNER"], geo["SHARP"], geo["VIATURN"]))
    A("       track_shape.py（全板 / 本组）：off-grid %s / %d，staircase %s / %d，sharp %s / %d，crowded %s / %d，tiny %s；圆弧 %s 段" % (
        ts.get("off-grid"), len(lines["off-grid"]), ts.get("staircase"), len(lines["staircase"]), ts.get("sharp"), len(lines["sharp"]),
        ts.get("crowded"), len(lines["crowded"]), ts.get("tiny"), ts.get("arcs")))
    for k in ("off-grid", "staircase", "sharp", "crowded"):
        for l in lines[k]:
            A("         %s: %s" % (k, l))
    for f in sd["findings"]:
        if f["kind"] == "VIATURN":
            A("         VIATURN: %s" % f["text"])
    if lines["sharp"] or lines["off-grid"] or lines["staircase"] or geo["SHARP"]:
        bad.append("shape")
    # ---- lengths
    Ln = sd["length"]
    tu = sd.get("tuning")
    dl = Ln.get("drc") or {}
    A("[等长] 长度（%s），基准 %s = %.3f mm" % ("含蛇形，DRC 量" if tu else "自然长度，没有蛇形", " + ".join(Ln["ref"]), Ln["ref_length"]))
    for g, gr in Ln["groups"].items():
        A("       组 %-6s %d 根：最短 %s %.3f，最长 %s %.3f，相差 %.3f；对基准 %+.3f .. %+.3f" % (
            g, gr["nets"], gr["shortest"][0], gr["shortest"][1], gr["longest"][0], gr["longest"][1], gr["spread"], gr["to_ref_range"][0], gr["to_ref_range"][1]))
    # the byte lanes against their DRC skew rules (sdram_lane0-3 of the rule file: longest minus shortest, DRC lengths)
    dru = open(os.path.splitext(board_path)[0] + ".kicad_dru", encoding="utf-8").read()
    lane_max = {"lane" + k: float(v) for k, v in re.findall(r'\(rule "sdram_lane(\d)"[^()]*\(condition "[^"]*"\)\s*\(constraint skew \(max ([\d.]+)mm\)\)', dru)}
    rows = []
    for g in sorted(lane_max):
        if g not in Ln["groups"]:
            continue
        k = int(g[4:])
        ls = {n: dl.get(n, Ln["nets"][n]["length"]) for n in ["FMC_D%d" % i for i in range(8 * k, 8 * k + 8)] + ["FMC_NBL%d" % k]}
        sp = max(ls.values()) - min(ls.values())
        rows.append("%s %.3f %s" % (g, sp, "满足" if sp <= lane_max[g] + 1e-6 else "超出 %.3f" % (sp - lane_max[g])))
        if sp > lane_max[g] + 1e-6:
            bad.append("%s skew" % g)
    A("       字节通道对规则（sdram_lane0-3，最长减最短，DRC 量）：上限 %s mm；%s" % (
        "/".join("%g" % lane_max[g] for g in sorted(lane_max)) or "规则文件里没有", "，".join(rows) or "—"))
    if len(lane_max) != 4:
        bad.append("lane rules")
    lon = max(Ln["nets"].items(), key=lambda kv: kv[1]["length"])
    A("       最长的网络 %s %.3f mm（上限 %s）；超过的 %d 根；DRC 量的长度对几何最大相差 %s mm" % (
        lon[0], lon[1]["length"], Ln["limit"], len(Ln["over_limit"]), Ln.get("max_abs_geometry_minus_drc")))
    lr = {k: n for k, n in by_all.items() if k in ("length_out_of_range", "skew_out_of_range")}
    if tu:
        # the columns of docs/tools.md: per group inside window / total, worst net and by how much, blocks and added
        # length, missing list; spread before (natural, geometry) -> after (DRC-measured lengths)
        nat = tu.get("natural", {})
        for g, x in tu["groups"].items():
            nets_g = list(x["nets"])
            after = {n: dl.get(n, Ln["nets"][n]["length"]) for n in nets_g}
            before = {n: nat.get(n, Ln["nets"][n]["length"]) for n in nets_g}
            if x.get("kind") == "ref":                     # a reference group: the clock (summed pieces) and its members
                R = sum(dl.get(n, Ln["nets"][n]["length"]) for n in x["ref_nets"])
                R0 = sum(nat.get(n, Ln["nets"][n]["length"]) for n in x["ref_nets"])
                lo, hi = R + x["lo"], R + x["hi"]
                out_ = {n: (v - hi if v > hi else v - lo) for n, v in after.items() if not (lo - 1e-6 <= v <= hi + 1e-6)}
                A("       蛇形 组 %s：基准 %s %.3f -> %.3f（DRC 量；目标 %.3f），窗口 %.3f .. %.3f（基准 %+g .. %+g）；成员对基准 %+.3f .. %+.3f -> %+.3f .. %+.3f；"
                  "窗口内 %d / %d 根；%d 块，补 %.3f mm；窗口外：%s" % (
                      g, x["ref"], R0, R, x["ref_target"], lo, hi, x["lo"], x["hi"], min(before.values()) - R0, max(before.values()) - R0,
                      min(after.values()) - R, max(after.values()) - R, len(nets_g) - len(out_), len(nets_g), x["blocks"], x["added"],
                      "，".join("%s %+.3f" % kv for kv in sorted(out_.items())) or "无"))
                if out_:
                    bad.append("%s window" % g)
                continue
            A("       蛇形 组 %s：最长 - 最短 %.3f -> %.3f（DRC 量）；窗口 %.3f .. %.3f（最长 %s − %g），目标 %.3f；窗口内 %d / %d 根；"
              "最差 %s 离窗口下沿 %+.3f；%d 块，补 %.3f mm；没补够：%s" % (
                  g, max(before.values()) - min(before.values()), max(after.values()) - min(after.values()), x["window"][0], x["window"][1],
                  x["ref"], x["spread"], x["target"], x["inside"], x["total"], x["worst"][0], x["worst"][1], x["blocks"], x["added"],
                  "，".join("%s 差 %.3f" % kv for kv in x["missing"].items()) or "无"))
        A("       蛇形块（层，起止，弯数 × 摆幅，朝向）：")
        for k in tu["blocks"]:
            A("         %-9s %s (%.3f, %.3f)-(%.3f, %.3f) %d × %.3f %s，补 %.3f" % (k["net"], k["layer"], k["from"][0], k["from"][1], k["to"][0], k["to"][1],
                                                                            k["humps"] or k["bumps"], k["amp"], k["side"], k["gain"]))
        # serpentines inside the corridors the main session reserved for stop 7 (routes file RESERVED): must be 0
        import importlib.util
        spec = importlib.util.spec_from_file_location("rs", os.path.join(HERE, "routes_sdram.py"))
        rs = importlib.util.module_from_spec(spec); spec.loader.exec_module(rs)
        hits = []
        for n, lay, s0, mid, e0, w in b.arc_items:
            for L_, x0, y0, x1, y1 in getattr(rs, "RESERVED", []):
                if lay == L_ and any(x0 - w / 2 <= p[0] <= x1 + w / 2 and y0 - w / 2 <= p[1] <= y1 + w / 2 for p in (s0, mid, e0)):
                    hits.append("%s %s (%.2f, %.2f)" % (n, lay, mid[0], mid[1]))
        A("       蛇形进保留通道（RESERVED 矩形）：%d%s" % (len(hits), "：" + "，".join(sorted(set(hits))[:10]) if hits else ""))
        if hits:
            bad.append("serpentine in a reserved corridor")
    A("       DRC 的等长项：%s；蛇形 %d 块（圆弧 %d 段）" % (" ".join("%s %d" % kv for kv in sorted(lr.items())) or "0",
                                                len(tu["blocks"]) if tu else 0, tu["arcs"] if tu else 0))
    if Ln["over_limit"]:
        bad.append("length")
    # straights >= 2.5 mm outside the rule areas on data / NBL nets (serpentine candidates)
    areas = b.rule_areas()
    data = [n for n in nets if re.match(r"FMC_(D\d+|NBL\d)$", n)]
    st = straights(b, data, {k: v for k, v in areas.items() if k.startswith("BGA_")})
    A("       数据 / NBL 线在规则区外 >= %.1f mm 的直线段：%d 段，%d 根线有（明细在 straights.json）" % (STRAIGHT, sum(len(v) for v in st.values()), len(st)))
    json.dump({n: v for n, v in sorted(st.items())}, open(os.path.join(odir, "straights.json"), "w", encoding="utf-8"), indent=0)
    # ---- vias
    v = sd["vias"]
    per = {n: x["vias"] for n, x in Ln["nets"].items()}
    A("[过孔] 每根最多 %d，合计 %d；上限 %s 超过的 %d 根；目标 %s 超过的 %d 根%s；数据 / NBL / 时钟用到 3 个的：%s" % (
        v["max"], v["total"], v["limit"], len(v["over_limit"]), v["target"], len(v["above_target"]),
        "（" + " ".join(v["above_target"]) + "）" if v["above_target"] else "",
        " ".join(n for n, k in sorted(per.items()) if k >= 3 and (n in data or "SDCLK" in n)) or "无"))
    A("       本组放的地过孔（换层处的回流，RTE-5）%d 个：%s" % (len(stitch), " ".join("(%.2f, %.2f)" % (x, y) for n, x, y in stitch)))
    if v["over_limit"]:
        bad.append("vias")
    # ---- order
    od = sd["order"]
    A("[线序] 同层交叉 %d 处，线束顺序问题 %d 处；各线最短路径相差：%s" % (od["crossings"], od["order_problems"], "，".join("%s %.3f" % kv for kv in od["direct_spread"].items())))
    if od["crossings"] or od["order_problems"]:
        bad.append("order")
    # ---- copper
    A("[铜皮]")
    mt = os.path.join(odir, "measure.txt")
    if os.path.isfile(mt):
        for l in open(mt, encoding="utf-8").read().splitlines():
            if l.startswith(("合计", "电源面块数", "铜皮类未连接数")):
                A("       " + l)
    sj = json.load(open(os.path.join(odir, "slots.json"), encoding="utf-8"))
    A("       平面开槽（填充后，窗口 %s）：每层最长 %s；被切断的本网络过孔 %d" % (
        " ".join(sj.get("windows", [])), "  ".join("%s %.2f mm (%.2f, %.2f)-(%.2f, %.2f)" % (k, r["length"], r["ends"][0][0], r["ends"][0][1], r["ends"][1][0], r["ends"][1][1])
                                       for k, r in sorted(sj["longest"].items())), len(sj["cut_off"])))
    for r in sj["slots"]:
        if r["length"] > 2.5:
            A("         %s %-5s %.2f mm (%.2f, %.2f)-(%.2f, %.2f) 过孔 %d：%s" % (r["layer"], r["window"], r["length"], r["ends"][0][0], r["ends"][0][1],
                                                                      r["ends"][1][0], r["ends"][1][1], r["vias"], " ".join(r["via_nets"][:9])))
    # slot length: reported, not judged (the user removed the plane-slot limit); a cut-off via still fails
    over = sorted(k for k, r in sj["longest"].items() if r["length"] > SLOT_MAX)
    if over:
        A("       开槽长度只报告（用户已取消开槽上限）：超过原来 %.1f mm 的层 %s" % (SLOT_MAX, " ".join(over)))
    if sj["cut_off"]:
        bad.append("cut-off vias")
    # the power plane L5 over the whole board (build.sh: copper_report.py slots --layers L5 --stem slots_l5): the
    # longest antipad chain inside each block; ground: L2 is the only plane, the L1 / L6 ground pieces hang on vias
    s5 = os.path.join(odir, "slots_l5.json")
    if os.path.isfile(s5):
        s5 = json.load(open(s5, encoding="utf-8"))
        A("       L5 每块最长的开槽（全板）：%s" % ("  ".join("%s %.2f mm (%.2f, %.2f)-(%.2f, %.2f)" % (
            k.split(" ", 1)[1], r["length"], r["ends"][0][0], r["ends"][0][1], r["ends"][1][0], r["ends"][1][1])
            for k, r in sorted(s5.get("longest_zone", {}).items())) or "无"))
    gv = sum(1 for n, *_ in b.vias if n == "GND")
    pi = os.path.join(odir, "pour_islands.txt")
    pis = [l.strip() for l in open(pi, encoding="utf-8").read().splitlines() if l.startswith("cu-whole:")] if os.path.isfile(pi) else []
    A("       地过孔 %d 个（GND 只有 L2 一层平面）；外层地铺铜：%s" % (gv, "；".join(pis) or "pour_islands.txt 没有"))
    if any(" 0 without" not in l for l in pis):
        bad.append("ground pieces")
    # ---- escape (U59)
    ej = os.path.join(odir, "escape_bga.json")
    old = os.path.join(HERE, "out", "copper", "escape_bga.json")
    if os.path.isfile(ej) and os.path.isfile(old):
        now, was = json.load(open(ej, encoding="utf-8")), json.load(open(old, encoding="utf-8"))
        A("[出线] escape_check（两颗 BGA，窗口 27 25 66 51），非 SDRAM、非电源的信号球，现在对停点 5：")
        for ref in ("U201", "U301"):
            pads = {p.num: p for p in b.by_ref[ref]}
            sig = [k for k, p in pads.items() if not p.net.startswith(("FMC_", "+", "GND", "VCAP", "VDDA")) and not p.net.startswith("unconnected")]
            cnt_now = collections.Counter("%s+%d" % (now[ref][k]["status"], now[ref][k]["vias"] or 0) for k in sig if k in now[ref])
            cnt_was = collections.Counter("%s+%d" % (was[ref][k]["status"], was[ref][k]["vias"] or 0) for k in sig if k in was[ref])
            A("       %s 信号球 %d：现在 %s；停点 5 %s" % (ref, len(sig), " ".join("%s %d" % kv for kv in sorted(cnt_now.items())),
                                                     " ".join("%s %d" % kv for kv in sorted(cnt_was.items()))))
            worse = [(k, was[ref][k], now[ref][k]) for k in sig if k in now[ref] and k in was[ref]
                     and (now[ref][k]["status"] == "blocked" and was[ref][k]["status"] != "blocked" or (now[ref][k]["vias"] or 0) > (was[ref][k]["vias"] or 0))]
            better = [(k, was[ref][k], now[ref][k]) for k in sig if k in now[ref] and k in was[ref]
                      and (was[ref][k]["status"] == "blocked" and now[ref][k]["status"] != "blocked" or (now[ref][k]["vias"] or 0) < (was[ref][k]["vias"] or 0))]
            for name, lst in (("变差", worse), ("变好", better)):
                if lst:
                    A("         %s %d: %s" % (name, len(lst), "  ".join("%s(%s) %s+%d -> %s+%d" % (k, pads[k].net, w["status"], w["vias"] or 0, n_["status"], n_["vias"] or 0) for k, w, n_ in lst)))
            blocked = [k for k in sig if now[ref].get(k, {}).get("status") == "blocked"]
            A("         出不来的: %s" % (" ".join("%s(%s)" % (k, pads[k].net) for k in blocked) or "0"))
    # ---- rules
    A("[规则生效] 金丝雀 %s；空匹配的规则 %s" % (
        "OK" if (sd.get("rules") or {}).get("canary", {}).get("ok") else "失败或没跑", _dru_empty(os.path.join(odir, "dru_match.txt"))))
    A("[构建] route1 一步 %s；第 %s 轮" % (os.environ.get("ROUTE1_SECONDS", "-"), os.environ.get("ROUND", sd.get("round"))))
    A("")
    A("结论：%s" % ("通过" if not bad else "不通过：" + "，".join(bad)))
    A("")
    A("网络         长度   DRC 量   蛇形   过孔  各层长度")
    for n in sorted(Ln["nets"], key=lambda s: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]):
        x = Ln["nets"][n]
        A("%-12s %7.3f  %7s  %5.3f  %3d   %s" % (n, x["length"], "%.3f" % dl[n] if n in dl else "—", x.get("tuned", 0.0) or 0.0, x["vias"],
                                             " ".join("%s %.2f" % kv for kv in x["layers"].items())))
    txt = "\n".join(L)
    open(os.path.join(odir, "table.txt"), "w", encoding="utf-8").write(txt + "\n")
    print(txt)
    return 1 if bad else 0


def _dru_empty(path):
    if not os.path.isfile(path):
        return "没跑"
    t = open(path, encoding="utf-8", errors="replace").read()
    return "%d" % len(re.findall(r"EMPTY", t)) + ("（%s）" % t.strip().splitlines()[-1] if t.strip() else "")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main(sys.argv[1], sys.argv[2]))
