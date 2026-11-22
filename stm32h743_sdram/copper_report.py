"""Helpers of the copper step (build.sh copper) of the STM32H743 + SDRAM board.

    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\copper_report.py unfill <board>
    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\copper_report.py table <board> <out dir>

unfill   drops the saved fill of every zone from the board file (text, nothing else changes). Run before any
         copper is added: pcbnew gives a via that lies in another net's stale fill that net when the board is
         loaded (docs/tools.md), and kicad-cli's refill loads the board first.
table    the copper group of the metrics table (PROC-4, docs/tools.md) after the refill: cu_sketch measure (read
         from <out dir>/measure.json), the copper-class nets' unconnected pads counted by pcbnew's own connectivity
         on the refilled board (kicad-cli lists at most 499 unconnected items, and the signal nets are not routed
         yet), split into this task and part B (BGA balls and the bottom parts under them); per rail the feed vias
         against the rule of routes_power.py; ground vias; the loop and crystal ground vias (U56, U54); DRC by type;
         the power group on the line-order sketch copy (<out dir>/sketch_power/metrics.json) and the escape check
         there against out/layout. Writes <out dir>/table.txt and prints it.
"""
import collections, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))


def unfill(path):
    text = open(path, encoding="utf-8", newline="").read()
    lines = text.split("\n")
    out, i, n = [], 0, 0
    while i < len(lines):
        if re.match(r"^\t\t\(filled_polygon\r?$", lines[i]):
            j = i + 1
            while not re.match(r"^\t\t\)\r?$", lines[j]):
                j += 1
            i, n = j + 1, n + 1
            continue
        out.append(lines[i])
        i += 1
    if n:
        open(path, "w", encoding="utf-8", newline="").write("\n".join(out))
    print("unfill: %d filled polygons removed from %s" % (n, os.path.basename(path)))


COPPER = """GND +3V3 +5V +3V3A +3V3_MCU +3V3_SDRAM +3V3_QSPI +3V3_PHY +3V3_AUD +3V3_LCD +3V3_SD +3V3_CAN +5V_BL +5V_CAN
+5V_LDO +3V3_LDO +5V_REG +3V3_REG +12V_IN +12V +12V_JACK SW_5V SW_3V3 SW_BL LED_A +1V8 VDDA_MCU VDDA_PHY""".split()
# per rail: (feed pads, vias required) by the coordinator's rule: 1 per 0.5 A of the rail, at least 2 per output / side
RAILS = [
    ("+5V (1.2 A) R110 -> L3", ["R110.2"], 3), ("+3V3 (1.1 A) R111 -> L3", ["R111.2"], 3),
    ("+5V -> 3.3 V buck input (U102, C108)", ["U102.4", "C108.1"], 2),
    ("+3V3A LDO output -> L3 block (U103, C111)", ["U103.5", "C111.1"], 2),
    ("+3V3_MCU R203 -> L3 tongue (+ C217)", ["R203.2", "C217.1"], 2), ("+3V3_SDRAM R301 -> L3 tongue (+ C309)", ["R301.2", "C309.1"], 2),
    ("VDDA_PHY L1 column <-> L6 strip", ["column - L6 strip"], 2), ("VDDA_PHY FB501 <-> L6 strip", ["FB501.2"], 2),
] + [("+5V link %s" % p, [p], 2) for p in ("R112.1", "R710.1", "R814.1")] \
  + [("+3V3 link %s" % p, [p], 2) for p in ("R203.1", "R301.1", "R404.1", "R514.1", "R610.1", "R709.1", "R812.1", "R813.1", "R113.1")]
LOOPS = ["C104.2", "U101.1", "C102.2", "C103.2", "C705.2", "U701.2", "C703.2", "C704.2", "C108.2", "U102.2"]


def clusters(board, nets):
    """{net: [[pad names] per connected piece]} from pcbnew's connectivity of the board as saved (fills included)."""
    import pcbnew
    c = board.GetConnectivity()
    out = {}
    for net in nets:
        pads = [p for f in board.GetFootprints() for p in f.Pads() if p.GetNetname() == net]
        name = {id(p): "%s.%s" % (p.GetParentFootprint().GetReference(), p.GetNumber()) for p in pads}
        key = lambda p: (p.GetParentFootprint().GetReference(), p.GetNumber(), p.GetPosition().x, p.GetPosition().y)
        seen, groups = set(), []
        for p in pads:
            if key(p) in seen:
                continue
            grp = [p] + [q for q in c.GetConnectedItems(p) if q.Type() == pcbnew.PCB_PAD_T and q.GetNetname() == net]
            ks = {key(q) for q in grp}
            new = [q for q in pads if key(q) in ks and key(q) not in seen]
            seen |= ks
            groups.append(sorted({"%s.%s" % (q.GetParentFootprint().GetReference(), q.GetNumber()) for q in new} | {name[id(p)]}))
        out[net] = groups
    return out


def table(board_path, odir):
    import pcbnew
    import cu_sketch
    import routes_power as RP
    L = []
    m = json.load(open(os.path.join(odir, "measure.json"), encoding="utf-8"))
    L.append(cu_sketch.measure_text(m))
    # ---- connectivity of the copper-class nets
    b = pcbnew.LoadBoard(board_path)
    part_b = lambda name: name.split(".")[0] in RP.PART_B
    cl = clusters(b, COPPER)
    mine, theirs = {}, {}
    for net, groups in cl.items():
        if len(groups) < 2:
            continue
        main = max(groups, key=lambda g: (not all(part_b(x) for x in g), len(g)))
        for g in groups:
            if g is main:
                continue
            (theirs if all(part_b(x) for x in g) else mine).setdefault(net, []).append(g)
    n_mine = sum(len(v) for v in mine.values())
    n_b = sum(len(v) for v in theirs.values())
    L.append("")
    L.append("铜皮类未连接（pcbnew 连通块，填充后的板）: 本任务 %d，B 部分（BGA 球和其下背面件）%d" % (n_mine, n_b))
    for net, gs in sorted(mine.items()):
        L.append("  本任务 %-11s %s" % (net, "  ".join("[%s]" % " ".join(g[:6]) for g in gs)))
    for net, gs in sorted(theirs.items()):
        L.append("  B 部分 %-11s %d 块: %s" % (net, len(gs), " ".join(x for g in gs for x in g)[:160]))
    # ---- feed vias per rail
    sites = json.load(open(os.path.join(odir, "power_sites.json"), encoding="utf-8"))
    per_pad = collections.Counter(s["pad"] for s in sites["done"] if s["kind"] in ("via", "feed"))
    L.append("")
    L.append("供电过孔（每 0.5 A 至少 1 个；稳压器输出、跳线电阻每侧、分块入口至少 2 个）:")
    for label, pads, need in RAILS:
        got = sum(per_pad[p] for p in pads)
        L.append("  %-44s %d / %d %s" % (label, got, need, "ok" if got >= need else "MISS"))
    L.append("  +12V 链（0.94 A）、+5V_REG、+3V3_REG、+1V8、LED_A、+5V_BL: 全在 L1，不换层，没有供电过孔")
    single = [s for s in sites["done"] if s["kind"] == "via" and s["net"] in ("+3V3", "+5V", "+3V3A") and s["pad"] not in {p for _, ps, _ in RAILS for p in ps}]
    L.append("  其余 +3V3 / +5V / +3V3A 焊盘各 1 个过孔到 L3: %d 个焊盘" % len({s["pad"] for s in single}))
    # ---- ground
    g = [s for s in sites["done"] if s["net"] == "GND"]
    own = sorted({s["pad"] for s in g if s["kind"] == "via"})
    gpads = [("%s.%s" % (f.GetReference(), p.GetNumber()), p) for f in b.GetFootprints() for p in f.Pads() if p.GetNetname() == "GND"]
    cand = [n for n, p in gpads if not p.HasHole() and not part_b(n) and n != "U601.33" and not n.startswith("U501.")]
    rely = sorted(set(cand) - set(own))
    far = [s for s in g if s["kind"] == "via" and s["pad"].startswith("C") and s.get("edge", 0) > 1.0]
    L.append("")
    L.append("地: 过孔 %d 个（焊盘旁 %d，散热焊盘内 %d）；有自己过孔的焊盘 %d；靠铺地的焊盘 %d：%s" % (
        len(g), sum(1 for s in g if s["kind"] == "via"), sum(1 for s in g if s["kind"] == "in pad"), len(own), len(rely), " ".join(rely)))
    L.append("  电容地过孔离焊盘边超过 1.0 mm: %s" % (" ".join("%s %.2f" % (s["pad"], s["edge"]) for s in far) or "0"))
    miss = [l for l in sites["log"] if l.startswith("NO ")]
    L.append("  找不到位置的: %d%s" % (len(miss), "".join("\n    " + l for l in miss)))
    L.append("环路的地过孔（U56，焊盘边到过孔中心 mm）: " + "  ".join(
        "%s %s" % (p, " ".join("%.2f" % s["edge"] for s in g if s["pad"] == p) or "-") for p in LOOPS))
    L.append("晶振外壳地（U54）: " + "  ".join("%s %s" % (p, next(("via (%.2f, %.2f) 焊盘边 %.2f" % (s["at"][0], s["at"][1], s["edge"]) for s in g if s["pad"] == p), "没有位置"))
                                          for p in ("Y201.2", "Y201.4")))
    # ---- DRC of the refilled board
    d = json.load(open(os.path.join(odir, "drc.json"), encoding="utf-8"))
    by = collections.Counter(v["type"] for v in d["violations"])
    L.append("")
    L.append("DRC（填充后的真板）: %s；未连接 %d 条（kicad-cli 最多列 499 条，信号线还没走）" % (
        " ".join("%s %d" % kv for kv in sorted(by.items())), len(d.get("unconnected_items", []))))
    # ---- the sketch copy
    sk = os.path.join(odir, "sketch_power", "metrics.json")
    if os.path.isfile(sk):
        s = json.load(open(sk, encoding="utf-8"))
        cg = s.get("drc_counted_group", {})
        L.append("线序草图副本上的电源组: 拦住构建的发现 %d，本组的 DRC 项 %s" % (
            sum(1 for f in s.get("findings", []) if f.get("hard")), " ".join("%s %d" % kv for kv in sorted(cg.items())) or "0"))
    L.append("耗时 %s" % os.environ.get("COPPER_SECONDS", "-"))
    txt = "\n".join(L)
    open(os.path.join(odir, "table.txt"), "w", encoding="utf-8").write(txt + "\n")
    print(txt)
    return 1 if n_mine else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if sys.argv[1] == "unfill":
        unfill(sys.argv[2])
    elif sys.argv[1] == "table":
        sys.exit(table(sys.argv[2], sys.argv[3]))
    else:
        print(__doc__)
        sys.exit(2)
