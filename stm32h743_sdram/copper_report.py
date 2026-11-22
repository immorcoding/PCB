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
         there against out/layout; part B (routes_power_bga.py: balls, sharing, decoupling, VCAP / VDDA_MCU, the
         sketch copy's DRC and slots.txt). Writes <out dir>/table.txt and prints it.
slots    (D:\\KiCad\\bin\\python.exe stm32h743_sdram\\copper_report.py slots <refilled board> <out dir>) U31: plane slots
         under the BGAs, cut-off vias, the L3 blocks' strip from the feed vias into the ball field (slots.json / .txt).
         Options: --window NAME X0 Y0 X1 Y1 (repeatable; instead of the two BGA windows), --part-b <power_bga_sites.json>.
strip    (copper_report.py strip <board> GROUP ...) removes what those busroute groups wrote last time, so that
         build.sh route1 can rebuild sdram, power and power_bga in that order.
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


def strip(path, groups):
    """Remove what the busroute groups `groups` wrote into the board last time (as recorded in <board>.busroute.json),
    so that the groups can be rebuilt from scratch in their order (build.sh route1: the SDRAM bus first, the power
    groups after it, against the bus)."""
    from busroute.board import write, Board
    side = os.path.splitext(path)[0] + ".busroute.json"
    rec = json.load(open(side, encoding="utf-8")) if os.path.isfile(side) else {"groups": {}}
    cu = None
    for g in groups:
        if g not in rec["groups"]:
            print("strip: no group %s recorded in %s" % (g, os.path.basename(side)))
            continue
        if cu is None:
            cu = Board(path, (100, 100)).cu
        shared = "segs" in rec["groups"][g]
        w = write(path, path, g, [], [], [], (100, 100), cu, shared=shared)
        print("strip: group %s, %d items removed" % (g, w["removed"]))


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
    L += part_b_text(b, odir)
    L.append("耗时 %s" % os.environ.get("COPPER_SECONDS", "-"))
    txt = "\n".join(L)
    open(os.path.join(odir, "table.txt"), "w", encoding="utf-8").write(txt + "\n")
    print(txt)
    return 1 if n_mine else 0


def part_b_text(b, odir):
    """Part B of stop 5 (routes_power_bga.py) on the real board: balls, vias, sharing, the bottom decoupling, VCAP and
    VDDA_MCU, and the sketch copy's DRC and plane slots (U31)."""
    import pcbnew
    import routes_power_bga as RB
    L = [""]
    path = os.path.join(odir, "power_bga_sites.json")
    if not os.path.isfile(path):
        return L + ["B 部分: 没有 power_bga_sites.json"]
    s = json.load(open(path, encoding="utf-8"))
    kinds = collections.Counter(k for n, p, sz, k in s["vias"])
    L.append("B 部分（routes_power_bga.py）: 过孔 %d 个（球的 %d：球间位 %d、封装外圈外侧 %d、空球位 %d；电容和磁珠自己的 %d）" % (
        len(s["vias"]), kinds["ball"] + kinds["ball lane"] + kinds["ball edge"], kinds["ball"], kinds["ball lane"], kinds["ball edge"],
        kinds["own"] + kinds["tie"]))
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    for ref, nets in RB.POWER.items():
        balls = [p for p in fps[ref].Pads() if p.GetNetname() in nets]
        per = collections.Counter(p.GetNetname() for p in balls)
        names = {"%s.%s" % (ref, p.GetNumber()) for p in balls}
        sh = [x for x in s["shared"] if x[0] in names]
        ns = [k for k in s["nosite"] if k in names]
        vias = {tuple(v) for k, v in s["ball_via"].items() if k in names}
        L.append("  %s: 球 %d（%s），过孔 %d；共用过孔 %d：%s；没有位置 %d%s" % (
            ref, len(balls), " ".join("%s %d" % kv for kv in sorted(per.items())), len(vias), len(sh),
            " ".join("%s->%s" % (x[0].split(".")[1], "+".join(o.split(".")[1] for o in x[2])) for x in sh) or "-", len(ns),
            "".join("\n    %s: %s" % (k, s["nosite"][k][:230]) for k in ns)))
    caps = s["caps"]
    kc = collections.Counter(c["kind"] for c in caps.values())
    stubs = [(c.get("stub") or 0.0, k) for k, c in caps.items() if "stub" in c["kind"]]
    worst = max(stubs) if stubs else (0.0, "-")
    L.append("背面去耦（焊盘 %d 个）: %s；最长短线（焊盘边外的长度）%.3f mm（%s）" % (
        len(caps), "  ".join("%s %d" % kv for kv in sorted(kc.items())), worst[0], worst[1]))
    gown = [c for c in caps.values() if c["net"] == "GND" and c["kind"] != "pour" and not c.get("balls")]
    L.append("  电容地焊盘：和地球共用过孔 %d 个，自己的地过孔 %d 个（焊盘边到过孔中心最远 %.2f mm，超过 1.0 mm 的 %d）" % (
        sum(1 for c in caps.values() if c["net"] == "GND" and c.get("balls")), len(gown),
        max([c.get("edge", 0) for c in gown] or [0]), sum(1 for c in gown if c.get("edge", 0) > 1.0)))
    supply_own = sorted(k for k, c in caps.items() if c["net"] != "GND" and c["kind"].startswith("own"))
    L.append("  电源焊盘没有落到球的过孔、用自己的过孔到 L3 的 %d 个: %s" % (len(supply_own), " ".join(supply_own) or "-"))
    small = [(f.GetReference(), p) for r, f in fps.items() if r.startswith("C") and f.GetValue().replace(" ", "").lower() in ("100n", "100nf", "0.1u", "0.1uf")
             for p in f.Pads()]
    rows = []
    for ref, nets in RB.POWER.items():
        for p in fps[ref].Pads():
            n = p.GetNetname()
            if n in nets and n not in ("GND", "VCAP1", "VCAP2"):
                d = min((pcbnew.ToMM((q.GetPosition() - p.GetPosition()).EuclideanNorm()) for r, q in small if q.GetNetname() == n), default=99)
                rows.append((round(d, 2), "%s.%s" % (ref, p.GetNumber())))
    L.append("  每个电源球到最近 100 nF 的距离（LAY-2）: 最远 %.2f mm（%s），超过 2.5 mm 的 %d" % (max(rows)[0], max(rows)[1], sum(1 for r in rows if r[0] > 2.5)))
    cl = clusters(b, ["VCAP1", "VCAP2", "VDDA_MCU"])
    L.append("  VCAP1 / VCAP2 / VDDA_MCU 连通块: %s" % "  ".join("%s %d（%s）" % (n, len(g), " | ".join(" ".join(x) for x in g)[:110]) for n, g in cl.items()))
    L += pours_in_areas(b)
    sd = os.path.join(odir, "sketch_drc.json")
    if os.path.isfile(sd):
        d = json.load(open(sd, encoding="utf-8"))
        by = collections.Counter(v["type"] for v in d["violations"])
        hard = {k: n for k, n in by.items() if k in ("clearance", "hole_clearance", "annular_width", "copper_edge_clearance", "hole_to_hole",
                                                         "track_angle", "via_diameter", "track_width", "isolated_copper", "starved_thermal", "shorting_items")}
        L.append("线序草图副本（两组电源 + SDRAM 草图，填充后）DRC: %s；其中间距/孔/焊环/板边/线宽/角度/孤铜类 %s" % (
            " ".join("%s %d" % kv for kv in sorted(by.items())), " ".join("%s %d" % kv for kv in sorted(hard.items())) or "0"))
    sp = os.path.join(odir, "slots.txt")
    if os.path.isfile(sp):
        L += open(sp, encoding="utf-8").read().rstrip("\n").split("\n")
    return L


def pours_in_areas(b, areas=("BGA_MCU", "BGA_SDRAM")):
    """Zone fills inside the two BGA rule areas, from the saved fills: L1 must have none (user 2026-11-22, the F.Cu
    keep-outs NOPOUR_L1_* of place.py); L6 is listed per fill piece with the pads and vias of its net it joins
    there (left as it is, for the user to decide). Also the supply and ground balls of the two packages that are
    not on the main connected piece of their net."""
    import pcbnew
    import routes_power_bga as RB
    ids = list(b.GetEnabledLayers().CuStack())
    rect = {z.GetZoneName(): z.Outline() for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName() in areas}
    mm2 = lambda s: s.Area() / 1e12
    pads = [("%s.%s" % (f.GetReference(), p.GetNumber()), p) for f in b.GetFootprints() for p in f.Pads()]
    vias = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    l1, l6 = {}, []
    for z in b.Zones():
        if z.GetIsRuleArea() or not z.IsOnCopperLayer() or z.GetLayer() not in (ids[0], ids[-1]):
            continue
        lay = z.GetLayer()
        fill = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(lay)); fill.Simplify()
        for an, R in rect.items():
            F = pcbnew.SHAPE_POLY_SET(fill); F.BooleanIntersection(R); F.Simplify()
            if lay == ids[0]:
                l1[an] = l1.get(an, 0.0) + mm2(F)
                continue
            for k in range(F.OutlineCount()):
                one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(F.Outline(k))
                for h in range(F.HoleCount(k)):
                    one.AddHole(F.Hole(k, h))
                if mm2(one) < 0.01:
                    continue
                joined = []
                for name, p in pads:
                    if p.GetNetname() != z.GetNetname() or not p.IsOnLayer(lay):
                        continue
                    o = p.GetEffectivePolygon(lay, pcbnew.ERROR_INSIDE).Outline(0)
                    if any(one.Contains(o.CPoint(i)) for i in range(o.PointCount())) or one.Contains(p.GetPosition()):
                        joined.append(name)
                nv = sum(1 for v in vias if v.GetNetname() == z.GetNetname() and one.Collide(v.GetPosition(), int(v.GetWidth(lay) / 2)))
                l6.append((an, z.GetZoneName(), z.GetNetname(), mm2(one), joined, nv))
    out = ["  BGA 区内的 L1 铺铜（place.py 的 F.Cu 禁铺区 NOPOUR_L1_*，填充后）: %s" % "  ".join("%s %.3f mm2" % kv for kv in sorted(l1.items()))]
    out.append("  BGA 区内的 L6 铺铜（保留；每块: 面积、连到的本网络焊盘、本网络过孔数）:")
    for an, zn, net, a, joined, nv in sorted(l6, key=lambda r: (r[0], r[1], -r[3])):
        out.append("    %-9s %-20s %-9s %7.2f mm2  焊盘 %s  过孔 %d" % (an, zn, net, a, " ".join(sorted(joined)) or "-", nv))
    # supply and ground balls off the main piece of their net
    lost = []
    for net, groups in clusters(b, sorted({n for ns in RB.POWER.values() for n in ns})).items():
        main = max(groups, key=len)
        lost += ["%s(%s)" % (x, net) for g in groups if g is not main for x in g if x.split(".")[0] in RB.POWER and len(groups) > 1]
    out.append("  电源和地球不在本网络主连通块上的: %d %s" % (len(lost), " ".join(lost)))
    return out


SLOT_WINDOWS = {"MCU": (32.0, 29.0, 48.0, 45.0), "SDRAM": (50.0, 27.5, 64.0, 46.5)}   # rule area +- 2 mm (the via
#                column at x 59-60, y 28.5-37 that the stop-3 review saw lies in the SDRAM window)
REF_LAYERS = {"L2": ["L1"], "L3": ["L4"], "L5": ["L4", "L6"]}      # signal layers whose return current runs on the plane
SLOT_REPORT = 2.0                                                  # slots longer than this are listed
BLOCKS = {"+3V3_MCU": "BGA_MCU", "+3V3_SDRAM": "BGA_SDRAM"}


def slots(board_path, odir, windows=None, part_b=None):
    """U31 on a refilled board (the line-order sketch copy): per plane layer and BGA window, the voids of the plane
    fill that hold vias (antipads merged into slots), their length (farthest two points), the nets whose tracks
    on the neighbouring signal layer cross them, and whether the part-B vias make them longer; vias of the plane's
    own net that the fill does not hold on its main piece (cut off); the narrowest connection of the two BGA blocks
    on L3 between their feed vias and the ball field. Writes <out dir>/slots.json and slots.txt.
    windows: {name: (x0, y0, x1, y1)} instead of SLOT_WINDOWS (build.sh route1 measures the whole bus region);
    part_b: the power_bga_sites.json whose vias are counted as part B (default <out dir>/sketch_power_bga/)."""
    import math
    import pcbnew
    import cu_sketch
    from bga_power import PLANE_CLR, MINWIDTH
    b = pcbnew.LoadBoard(board_path)
    ids = list(b.GetEnabledLayers().CuStack())
    lname = {lid: "L%d" % (i + 1) for i, lid in enumerate(ids)}
    lid = {v: k for k, v in lname.items()}
    mm = lambda v: v / 1e6
    loc = lambda p: (round(mm(p.x) - 100, 3), round(mm(p.y) - 100, 3))
    V = lambda x, y: pcbnew.VECTOR2I(int(round((x + 100) * 1e6)), int(round((y + 100) * 1e6)))
    sp = part_b or os.path.join(odir, "sketch_power_bga", "power_bga_sites.json")
    mine = set()
    if os.path.isfile(sp):
        mine = {(n, round(p[0], 3), round(p[1], 3)) for n, p, s, k in json.load(open(sp, encoding="utf-8"))["vias"]}
    vias, tracks = [], collections.defaultdict(list)
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            vias.append((t.GetNetname(), loc(t.GetPosition()), mm(t.GetWidth(pcbnew.F_Cu))))
        elif t.Type() == pcbnew.PCB_TRACE_T:
            tracks[lname[t.GetLayer()]].append((t.GetNetname(), t.GetStart(), t.GetEnd()))
    areas = {z.GetZoneName(): z.Outline() for z in b.Zones() if z.GetIsRuleArea()}
    windows = windows or SLOT_WINDOWS
    out = {"board": board_path, "slots": [], "longest": {}, "cut_off": [], "necks": {},
           "windows": ["%s (%g, %g)-(%g, %g)" % ((k,) + tuple(w)) for k, w in windows.items()]}
    for wname, (x0, y0, x1, y1) in windows.items():
        win = pcbnew.SHAPE_POLY_SET()
        ch = pcbnew.SHAPE_LINE_CHAIN()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            ch.Append(V(x, y))
        ch.SetClosed(True)
        win.AddOutline(ch)
        for z in b.Zones():
            if z.GetIsRuleArea() or not z.IsOnCopperLayer():
                continue
            L = lname.get(z.GetLayer())
            if L not in REF_LAYERS:
                continue
            net = z.GetNetname()
            A = pcbnew.SHAPE_POLY_SET(z.Outline()); A.BooleanIntersection(win)
            if not A.OutlineCount():
                continue
            fill = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(z.GetLayer())); fill.Simplify()
            F = pcbnew.SHAPE_POLY_SET(fill); F.BooleanIntersection(win)
            void = pcbnew.SHAPE_POLY_SET(A); void.BooleanSubtract(F); void.Simplify()
            for k in range(void.OutlineCount()):
                o = void.Outline(k)
                pts = [loc(o.CPoint(i)) for i in range(o.PointCount())]
                one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(o)
                inside = [v for v in vias if v[0] != net and one.Contains(V(*v[1]))]
                if not inside:
                    continue
                far = max(((math.dist(p, q), p, q) for i, p in enumerate(pts) for q in pts[i + 1:]), default=(0, None, None))
                cross = set()
                for rl in REF_LAYERS[L]:
                    for n, a, c in tracks[rl]:
                        if one.Collide(pcbnew.SEG(a, c), 0):
                            cross.add(n)
                own = [v for v in inside if (v[0], round(v[1][0], 3), round(v[1][1], 3)) in mine]
                rest = [v for v in inside if v not in own]
                span = 0.0                                  # longest chain of the other vias alone (antipads merging)
                todo = list(range(len(rest)))
                while todo:
                    grp, st = set(), [todo.pop()]
                    while st:
                        i = st.pop(); grp.add(i)
                        for j in list(todo):
                            if math.dist(rest[i][1], rest[j][1]) < (rest[i][2] + rest[j][2]) / 2 + 2 * PLANE_CLR + MINWIDTH:
                                todo.remove(j); st.append(j)
                    m = [rest[i] for i in grp]
                    span = max(span, max((math.dist(a[1], c[1]) for a in m for c in m), default=0) + max(v[2] for v in m) + 2 * PLANE_CLR)
                row = {"window": wname, "layer": L, "zone": z.GetZoneName(), "net": net, "length": round(far[0], 3),
                       "ends": [far[1], far[2]], "vias": len(inside), "part_b_vias": len(own),
                       "without_part_b": round(span, 3), "via_nets": sorted({v[0] for v in inside}), "crossing": sorted(cross)}
                out["slots"].append(row)
            # vias of the plane's own net that are not on the main piece of its fill (cut off)
            pieces = cu_sketch.split(fill)
            if not pieces:
                continue
            main = max(range(len(pieces)), key=lambda i: pieces[i].Area())
            for v in vias:
                if v[0] == net and x0 <= v[1][0] <= x1 and y0 <= v[1][1] <= y1 and A.Contains(V(*v[1])):
                    if not pieces[main].Contains(V(*v[1])):
                        out["cut_off"].append({"layer": L, "zone": z.GetZoneName(), "net": net, "via": v[1], "part_b": (v[0], round(v[1][0], 3), round(v[1][1], 3)) in mine})
    out["slots"].sort(key=lambda r: (r["layer"], -r["length"]))
    for r in out["slots"]:
        k = r["layer"]
        if k not in out["longest"] or r["length"] > out["longest"][k]["length"]:
            out["longest"][k] = r
    # L3 blocks: narrowest connection between the feed vias (outside the rule area) and the ball field
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() not in BLOCKS or lname.get(z.GetLayer()) != "L3":
            continue
        net, area = z.GetNetname(), areas[BLOCKS[z.GetNetname()]]
        fill = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(z.GetLayer())); fill.Simplify()
        pieces = cu_sketch.split(fill)
        bb = area.BBox()
        centre = bb.GetCenter()
        feeds = [(t.GetPosition(), int(t.GetWidth(z.GetLayer()) / 2), "via", "feed via%s" % (loc(t.GetPosition()),), False) for t in b.GetTracks()
                 if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == net and not area.Contains(t.GetPosition())]
        balls = [(t.GetPosition(), int(t.GetWidth(z.GetLayer()) / 2)) for t in b.GetTracks()
                 if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == net and area.Contains(t.GetPosition())]
        main = max(pieces, key=lambda p: p.Area()) if pieces else None

        def reach(w):
            """Supply vias in the rule area that a strip of width w still joins to the feed vias."""
            d = pcbnew.SHAPE_POLY_SET(main)
            d.Deflate(int(w * 1e6 / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, 2000)
            subs = cu_sketch.split(d)
            fed = {k for k, s in enumerate(subs) for pt, r, *_ in feeds if s.Collide(pt, int(r + w * 1e6 / 2 + 20000))}
            return sum(1 for pt, r in balls if any(subs[k].Collide(pt, int(r + w * 1e6 / 2 + 20000)) for k in fed))
        lo, hi = 0.0, 5.0
        if main is not None and feeds and balls and reach(0.02):
            if reach(hi):
                lo = hi
            for _ in range(10):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if reach(mid) else (lo, mid)
        n2 = reach(2.0) if main is not None and feeds and balls else 0
        out["necks"][net] = {"pieces": len(pieces), "neck_mm": round(lo, 3), "feeds": len(feeds), "field_vias": len(balls),
                             "field_vias_at_2mm": n2,
                             "note": "the widest strip from the feed vias that still reaches a supply via in the rule area"}
    json.dump(out, open(os.path.join(odir, "slots.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    txt = slots_text(out)
    open(os.path.join(odir, "slots.txt"), "w", encoding="utf-8").write(txt + "\n")
    print(txt)


def slots_text(s):
    L = ["平面开槽（U31，填充后；窗口 %s）: 列出长于 %.1f mm 的" % (" ".join(s.get("windows", [])) or "规则区外扩 2 mm", SLOT_REPORT)]
    for r in s["slots"]:
        if r["length"] > SLOT_REPORT:
            L.append("  %-2s %-5s %-6.2f mm  (%.2f, %.2f)-(%.2f, %.2f)  过孔 %d（B 部分 %d，去掉它们后最长 %.2f）  过孔网络 %s  上方走线 %s" % (
                r["layer"], r["window"], r["length"], r["ends"][0][0], r["ends"][0][1], r["ends"][1][0], r["ends"][1][1], r["vias"], r["part_b_vias"],
                r["without_part_b"], " ".join(r["via_nets"][:8]) + (" …" if len(r["via_nets"]) > 8 else ""), " ".join(r["crossing"]) or "-"))
    L.append("  每层最长: " + "  ".join("%s %.2f mm (%s)" % (k, v["length"], v["window"]) for k, v in sorted(s["longest"].items())))
    L.append("  被切断的本网络过孔: %d%s" % (len(s["cut_off"]), "".join("\n    %s %s %s (%.2f, %.2f)%s" % (c["layer"], c["zone"], c["net"], c["via"][0], c["via"][1], " B 部分" if c["part_b"] else "") for c in s["cut_off"])))
    for net, n in s["necks"].items():
        L.append("  L3 %-11s 块数 %d；供电过孔 %d 个到球区（区内 %d 个本网络过孔）的最窄连接 %.2f mm（能连到第一个的最宽铜带）；按 2.0 mm 宽的铜带能到的 %d 个" % (
            net, n["pieces"], n["feeds"], n["field_vias"], n["neck_mm"], n["field_vias_at_2mm"]))
    return "\n".join(L)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if sys.argv[1] == "unfill":
        unfill(sys.argv[2])
    elif sys.argv[1] == "strip":
        strip(sys.argv[2], sys.argv[3:])
    elif sys.argv[1] == "table":
        sys.exit(table(sys.argv[2], sys.argv[3]))
    elif sys.argv[1] == "slots":
        a = sys.argv[4:]
        win = {a[k + 1]: tuple(float(v) for v in a[k + 2:k + 6]) for k in range(len(a)) if a[k] == "--window"} or None
        slots(sys.argv[2], sys.argv[3], win, a[a.index("--part-b") + 1] if "--part-b" in a else None)
    else:
        print(__doc__)
        sys.exit(2)
