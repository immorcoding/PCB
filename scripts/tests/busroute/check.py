"""Regression benchmark of scripts/busroute (PROC-15).

    D:\\KiCad\\bin\\python.exe scripts\\tests\\busroute\\check.py [--keep]

Builds a 40 x 30 mm six-layer board in a temp folder from the H743 project's own files (stackup and empty
board from stm32h743_sdram/make_project.py, its .kicad_pro, its .kicad_dru): U1 = the stock
UFBGA-201 0.65 mm footprint, U2 = the project's 90-ball 0.8 mm footprint (0.33 mm pads), one rule area round
each (BGA_MCU, BGA_SDRAM: package + 1 mm), ground pours on L2 and L5. Then routes the twelve nets of
bench_routes.py and expects:

  full build        no finding, DRC clean for the group, the rule canary OK, every net connected pad to pad
                    (pcbnew), the board file equal to the model, geometry length = DRC length within 0.002 mm,
                    the pinned length and via count of every net, the pinned lanes of the fan-out
  again             a second build is byte-identical
  two groups        the ten bundle nets and the two hand nets built as separate groups on one board give
                    the same copper as the single build (a group build does not disturb other nets)
  negative cases    two lanes that must cross (ORDER), a pitch below the clearance (PitchError with the
                    missing 0.0286 mm), a via on a ball pad (VIAPAD), a channel used twice (CHANNEL)
  obstacles         part X1 with two plated pads numbered SH and an F.Cu keep-out inside the footprint
                    (bench_obstacles.py): the fast check reports the track over the first SH pad and in the keep-out
  length verdict    metrics.length_check: a geometry-vs-DRC difference fails only nets with a length rule

Length tuning (tune.py), on the same board with other balls on the nets (TUNE_PADS) and bench_tune.py:
  plain             the routes without TUNING: DRC reports the lane's skew (rule sdram_lane1, 5 mm) -- the rule is live
  budget            --tuning-budget numbers of variant "short": targets, needs, RTE-2 capacities, the one short net
  tune              a 5-lane bundle (3 slots, two start on one line, a bump beside a lane 0.25 mm away), a hand-written route with a
                    double-sided free site, one whose site is short for amp 0.5 (amplitude raised): every group inside
                    its spread, DRC clean (skew included), geometry length = DRC length within 0.01 mm, no finding,
                    the arc checks (tangency, radius, pieces >= 0.1, equal heights, clr / area_gap / end) and
                    track_shape.py (arc joints, sharp, crowded) clean, the pinned lengths and blocks
  short             one more net whose site is far too short: drawn what fits (DRC clean, arc checks clean), the
                    only finding is TUNE "missing 9.145 mm", which equals target - its DRC-measured length

Prints one line, `OK ...` or `FAIL ...`; exit code 0 = pass. --keep leaves the temp folder.
"""
import os, shutil, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", ".."))
ROOT = os.path.dirname(SCRIPTS)
PROJ = os.path.join(ROOT, "stm32h743_sdram")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, PROJ)
import pcbnew                                               # noqa: E402
import make_project                                         # noqa: E402
from busroute import job, Board                             # noqa: E402

OX = OY = 100.0
MCU, RAM = (13.0, 12.0), (27.0, 15.9)
AREAS = {"BGA_MCU": (7.0, 6.0, 19.0, 18.0), "BGA_SDRAM": (22.0, 8.4, 32.0, 23.4)}
PADS = {"FMC_D0": ("N15", "J1"), "FMC_D1": ("N14", "J2"), "FMC_D2": ("P15", "K1"), "FMC_D3": ("P14", "K2"),
        "FMC_D4": ("R13", "M1"), "FMC_D5": ("R12", "M2"), "FMC_D6": ("L12", "F1"), "FMC_D7": ("M12", "F2"),
        "FMC_D8": ("L13", "G1"), "FMC_D9": ("M13", "G2"), "FMC_D10": ("H15", "A1"), "FMC_D11": ("G15", "B2")}
# net: (length mm by geometry, vias). Via heights on this stackup: L1-L4 1.3932, L1-L6 1.6504.
EXPECT = {'FMC_D0': (6.8506, 0), 'FMC_D1': (8.632, 0), 'FMC_D2': (6.9127, 0), 'FMC_D3': (8.6941, 0), 'FMC_D4': (9.7485, 0), 'FMC_D5': (11.3395, 0),
          'FMC_D6': (11.6699, 2), 'FMC_D7': (12.532, 2), 'FMC_D8': (10.8127, 2), 'FMC_D9': (11.6749, 2), 'FMC_D10': (6.9542, 0), 'FMC_D11': (10.5786, 2)}
LANES = """fan-out of U1: 10 leads drawn, 0 refused
  side E on L1, left to right going out (4): FMC_D0[N15 straight]  FMC_D1[N14 channel]  FMC_D2[P15 straight]  FMC_D3[P14 channel]
  side E on L4, left to right going out (4): FMC_D6[L12 via]  FMC_D7[M12 via]  FMC_D8[L13 via]  FMC_D9[M13 via]
  side S on L1, left to right going out (2): FMC_D4[R13 straight]  FMC_D5[R12 straight]
fan-out of U2: 6 leads drawn, 0 refused
  side W on L1, left to right going out (6): FMC_D5[M2 channel]  FMC_D4[M1 straight]  FMC_D3[K2 channel]  FMC_D2[K1 straight]  FMC_D1[J2 channel]  FMC_D0[J1 straight]
via field: 2 rows, step 0.70, via 0.3 / 0.15, ground vias [(22.3, 13.85), (23.0, 13.85), (22.3, 15.95), (23.0, 15.95)]"""
# The tuning benchmark: other balls on the nets (bench_tune.py).
TUNE_PADS = {"FMC_D8": ("R13", "R1"), "FMC_D9": ("R12", "P1"), "FMC_D10": ("R11", "R2"), "FMC_D11": ("R10", "P2"), "FMC_D12": ("R9", "R3"),
             "FMC_A0": ("A9", "A9"), "FMC_A1": ("A10", "A8"), "FMC_A2": ("A11", "A7"), "FMC_A3": ("A12", "A3")}
# net: (natural length, length with serpentines) by geometry, variant "short" (A3 is tuned only there).
# Targets: lane1 26.62 - 4.2 + 0.3 = 22.72, hand 30.1284 - 2 + 0.3 = 28.4284. D11 / D12 run 0.65 mm nearer D10 on the east
# leg than before 2026-11-22 (D11 0.25 below D10: the lane-neighbour case of tune.py), hence shorter.
TUNE_LEN = {'FMC_A0': (30.1284, 30.1284), 'FMC_A1': (26.2784, 28.4284), 'FMC_A2': (22.4284, 28.4284), 'FMC_A3': (16.1784, 19.2834),
            'FMC_D8': (17.7971, 22.72), 'FMC_D9': (21.1031, 22.72), 'FMC_D10': (22.4778, 22.72), 'FMC_D11': (25.2454, 25.2454),
            'FMC_D12': (26.62, 26.62)}
# (net, kind, side, humps, height, pitch) of every block drawn in variant "short", in drawing order (neediest net first).
# A3: 2 humps (its site holds no more), 0.905 high (0.910 comes closer than 0.19 to A2): adds 3.105 of 12.250.
# A2: 8 humps at 0.504 would add its 6.000, the site holds 5: raised to (6 / 5 + 0.2575) / 2 = 0.7288.
# D8: 6 x (2 x 0.539 - 0.858 x 0.3) = 4.923. A1 both-sided, pitch 0.5: 3 humps would be 0.5014 high, an illegal
# 0.0014 mm leg, so 2 humps of 0.6985. D10 needs 0.242, below one hump of 2r: a bump of radius 0.15, drawn although D11
# runs 0.25 mm below D10 there (0.148 edge to edge < clr): the bump comes no closer to D11 than D10's straight.
TUNE_BLOCKS = [('FMC_A3', 'single', 'L', 2, 0.905, 0.3), ('FMC_A2', 'single', 'L', 5, 0.7288, 0.3), ('FMC_D8', 'single', 'L', 6, 0.539, 0.3),
               ('FMC_A1', 'both', 'both', 2, 0.6985, 0.5), ('FMC_D9', 'single', 'L', 2, 0.533, 0.3), ('FMC_D10', 'bump', 'L', 0, 0.2451, 0.3)]
# --tuning-budget of variant "short": group -> (target, {net: (need, [(humps, cap at amp, cap at amp_max) per site])})
TUNE_BUDGET = {'lane1': (22.72, {'FMC_D8': (4.9229, [(6, 4.4549, 22.4549)]), 'FMC_D9': (1.6169, [(2, 1.485, 7.485)]),
                                 'FMC_D10': (0.2422, [(1, 0.7425, 3.7425)]), 'FMC_D11': (0.0, []), 'FMC_D12': (0.0, [])}),
               'hand': (28.4284, {'FMC_A0': (0.0, []), 'FMC_A1': (2.15, [(3, 2.1416, 11.1416)]), 'FMC_A2': (6.0, [(5, 3.7124, 18.7124)]),
                                  'FMC_A3': (12.25, [(2, 1.485, 7.485)])})}
# DRC item types that say nothing about the routes on this synthetic board.
IGNORE = {"lib_footprint_issues": "the two footprints are loaded from library folders, the board has no fp-lib-table",
          "lib_footprint_mismatch": "the BGA pads get solder-mask margin 0 as on the real board, which differs from the library",
          "silk_over_copper": "reference text of the footprints is where the generator put it",
          "silk_overlap": "same", "silk_edge_clearance": "same",
          "isolated_copper": "the two ground pours have no pad of their net on this board (2 items, with and without the stitching vias)",
          "skew_out_of_range": "the project's byte-lane skew rules (sdram_lane0-3, added after this benchmark) see the bench nets FMC_D0-D7; matching is not benchmarked here"}


def make_board(tmp, pads=None):
    """The benchmark board in `tmp`; `pads` = {net: (U1 ball, U2 ball)} (default PADS)."""
    pads = pads or PADS
    pcb = os.path.join(tmp, "bench.kicad_pcb")
    make_project.make_pcb(pcb)                              # empty six-layer board with the real stackup
    b = pcbnew.LoadBoard(pcb)
    mm = pcbnew.FromMM
    V = lambda x, y: pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))
    nets = {}

    def net(name):
        if name not in nets:
            nets[name] = pcbnew.NETINFO_ITEM(b, name); b.Add(nets[name])
        return nets[name]
    for a, c in (((0, 0), (40, 0)), ((40, 0), (40, 30)), ((40, 30), (0, 30)), ((0, 30), (0, 0))):
        s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(V(*a)); s.SetEnd(V(*c))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); b.Add(s)
    for name, (x0, y0, x1, y1) in AREAS.items():           # rule areas as stm32h743_sdram/place.py draws them
        z = pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetZoneName(name); z.SetLayerSet(pcbnew.LSET.AllCuMask())
        for f in ("SetDoNotAllowTracks", "SetDoNotAllowVias", "SetDoNotAllowPads", "SetDoNotAllowZoneFills", "SetDoNotAllowFootprints"):
            getattr(z, f)(False)
        ch = pcbnew.SHAPE_LINE_CHAIN()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            ch.Append(mm(OX + x), mm(OY + y))
        ch.SetClosed(True); z.Outline().AddOutline(ch); b.Add(z)
    libs = {"U1": (os.path.join(make_project.KICAD_FP, "Package_BGA.pretty"), "UFBGA-201_10x10mm_Layout15x15_P0.65mm", MCU),
            "U2": (os.path.join(PROJ, "h743.pretty"), make_project.SDRAM_FP + "_Pad0.33mm", RAM)}
    for ref, (lib, name, xy) in libs.items():
        fp = pcbnew.FootprintLoad(lib, name)
        fp.SetReference(ref); fp.SetPosition(V(*xy)); b.Add(fp)
        by = {p.GetNumber(): p for p in fp.Pads()}
        for p in fp.Pads():
            p.SetLocalSolderMaskMargin(0)
        for n, balls in pads.items():
            by[balls[0 if ref == "U1" else 1]].SetNet(net(n))
    for layer in (pcbnew.In1_Cu, pcbnew.In4_Cu):            # ground planes; filled by the DRC run
        z = pcbnew.ZONE(b); z.SetZoneName("GND_%d" % layer); z.SetLayer(layer); z.SetNet(net("GND"))
        z.SetLocalClearance(mm(0.2)); z.SetMinThickness(mm(0.2)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        ch = pcbnew.SHAPE_LINE_CHAIN()
        for x, y in ((0.5, 0.5), (39.5, 0.5), (39.5, 29.5), (0.5, 29.5)):
            ch.Append(mm(OX + x), mm(OY + y))
        ch.SetClosed(True); z.Outline().AddOutline(ch); b.Add(z)
    pcbnew.SaveBoard(pcb, b)
    make_project.make_pro(os.path.join(tmp, "bench.kicad_pro"))      # after SaveBoard (it writes a default .kicad_pro)
    shutil.copy(os.path.join(PROJ, make_project.NAME + ".kicad_dru"), os.path.join(tmp, "bench.kicad_dru"))
    shutil.copy(os.path.join(HERE, "bench_routes.py"), os.path.join(tmp, "bench_routes.py"))
    return pcb


def obst_board(src, dst):
    """A copy of the benchmark board with part X1 (bench_obstacles.py): two plated pads numbered SH at (19.0, 12.4)
    and (19.0, 15.0), and an F.Cu keep-out "contact" (tracks and vias) at x 20.2-20.8, y 10.6-11.4 inside it."""
    b = pcbnew.LoadBoard(src)
    mm = pcbnew.FromMM
    V = lambda x, y: pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))
    fp = pcbnew.FOOTPRINT(b); fp.SetReference("X1"); fp.SetPosition(V(19.0, 13.5))
    for y in (12.4, 15.0):
        p = pcbnew.PAD(fp); p.SetNumber("SH"); p.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
        p.SetShape(pcbnew.PADSTACK.ALL_LAYERS, pcbnew.PAD_SHAPE_CIRCLE)
        p.SetSize(pcbnew.PADSTACK.ALL_LAYERS, pcbnew.VECTOR2I(mm(1.0), mm(1.0))); p.SetDrillSize(pcbnew.VECTOR2I(mm(0.6), mm(0.6)))
        p.SetLayerSet(pcbnew.PAD.PTHMask()); p.SetPosition(V(19.0, y)); fp.Add(p)
    z = pcbnew.ZONE(fp); z.SetIsRuleArea(True); z.SetZoneName("contact")
    ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); z.SetLayerSet(ls)
    z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowZoneFills(True); z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    ch = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in ((20.2, 10.6), (20.8, 10.6), (20.8, 11.4), (20.2, 11.4)):
        ch.Append(mm(OX + x), mm(OY + y))
    ch.SetClosed(True); z.Outline().AddOutline(ch); fp.Add(z); b.Add(fp)
    pcbnew.SaveBoard(dst, b)
    make_project.make_pro(os.path.splitext(dst)[0] + ".kicad_pro")       # SaveBoard wrote a default one


def run(folder, variant, out=None, fast=False, pictures=False):
    os.environ["BUSROUTE_BENCH"] = variant
    log = []
    m, code = job.run(os.path.join(folder, "bench_routes.py"), fast=fast, out=out, pictures=pictures, log=log.append)
    return m, code, "\n".join(log)


def copper(pcb):
    b = Board(pcb, (OX, OY))
    return sorted((t[:5] for t in b.tracks), key=repr), sorted(b.vias, key=repr)


def tuning(tmp, want):
    """The length-tuning cases (see the module text). Returns the seconds they took."""
    t0 = time.time()
    tt = os.path.join(tmp, "tune")
    os.makedirs(tt)
    make_board(tt, TUNE_PADS)
    shutil.copy(os.path.join(HERE, "bench_tune.py"), os.path.join(tt, "bench_tune.py"))
    rt = os.path.join(tt, "bench_tune.py")
    quiet = lambda *a: None

    def build(variant, out):
        os.environ["BUSROUTE_BENCH"] = variant
        return job.run(rt, out=os.path.join(tt, out), pictures=False, log=quiet)

    m, code = build("plain", "out_plain")                  # control: the rule file's skew rule sees the natural spread
    want("skew_out_of_range" in m.get("connectivity", {}).get("drc_by_type_board", {}),
         "plain: DRC does not report the lane's skew before tuning: %r" % (m.get("connectivity", {}).get("drc_by_type_board"),))

    os.environ["BUSROUTE_BENCH"] = "short"
    tb = time.time()
    b, code = job.budget(rt, log=quiet)
    budget_s = time.time() - tb
    got = {g: (t["target"], {r["net"]: (r["need"], [(x["humps"], x["cap_amp"], x["cap_amp_max"]) for x in r["sites"]]) for r in t["rows"]})
           for g, t in b.get("groups", {}).items()}
    want(code == 1 and [x["net"] for x in b["short"]] == ["FMC_A3"], "budget: exit %d, short %r" % (code, b.get("short")))
    want(got == TUNE_BUDGET, "budget changed:\nTUNE_BUDGET = %r" % (got,))
    want(budget_s < 10, "budget took %.1f s" % budget_s)

    for variant in ("tune", "short"):
        m, code = build(variant, "out_" + variant)
        if "error" in m:
            want(False, "%s: could not be built: %s" % (variant, m["error"]))
            continue
        hard = [f for f in m["findings"] if f["hard"]]
        c, tu, L = m["connectivity"], m["tuning"], m["length"]
        other = {k: v for k, v in c["drc_by_type_board"].items() if k not in IGNORE}
        want(not other and c["drc_unconnected_board"] == 0 and c["pcbnew"]["fully_connected"] == 9,
             "%s: DRC %r, unconnected %d, connected %r" % (variant, other, c["drc_unconnected_board"], c["pcbnew"]))
        want(m["written"]["matches_model"], "%s: the board file does not hold the model's copper (arcs included)" % variant)
        d = L["max_abs_geometry_minus_drc"]
        want(d is not None and d <= 0.01 and not L["not_measured_by_drc"], "%s: geometry against DRC lengths: max %r" % (variant, d))
        g = tu["geometry"]
        want(not [f for f in m["findings"] if f["kind"] == "ARC"] and g["max_joint_deg"] <= 0.01 and g["max_radius_error"] <= 1e-4
             and g["shortest_piece"] >= 0.1 and g["max_height_spread"] <= 1e-4 and g["min_clr"] >= 0.19 and g["min_area_gap"] >= 0.127
             and g["min_end"] >= 0.35, "%s: arc geometry %r" % (variant, g))
        ts = m["shape"]["track_shape"]
        want(all(ts[k] == 0 for k in ("off-grid", "staircase", "sharp", "crowded", "tiny", "arc-joint")) and ts["arcs"] == g["arcs"],
             "%s: track_shape %r" % (variant, {k: ts.get(k) for k in ("off-grid", "staircase", "sharp", "crowded", "tiny", "arc-joint", "arcs")}))
        if variant == "tune":
            want(code == 0 and m["ok"] and not hard, "tune: exit %d, %r" % (code, [f["text"] for f in hard]))
            want(all(gr["inside"] == gr["total"] for gr in tu["groups"].values()) and not tu["missing"],
                 "tune: groups %r" % ({k: (v["inside"], v["total"], v["missing"]) for k, v in tu["groups"].items()},))
        else:
            gl = {n: (tu["natural"][n], v["length"]) for n, v in L["nets"].items()}
            want(gl == TUNE_LEN, "short: lengths changed:\nTUNE_LEN = %r" % (gl,))
            bl = [(x["net"], x["kind"], x["side"], x["humps"], x["amp"], x["pitch"]) for x in tu["blocks"]]
            want(bl == TUNE_BLOCKS, "short: blocks changed:\nTUNE_BLOCKS = %r" % (bl,))
            want(code == 1 and len(hard) == 1 and hard[0]["kind"] == "TUNE" and "FMC_A3: missing 9.145 mm" in hard[0]["text"],
                 "short: exit %d, hard findings %r" % (code, [f["text"] for f in hard]))
            hand = tu["groups"]["hand"]
            miss = hand["target"] - L["drc"]["FMC_A3"]
            want(abs(miss - tu["missing"]["FMC_A3"]) <= 0.001 and hand["inside"] == 3 and hand["total"] == 4,
                 "short: missing %r against target - DRC length %.4f" % (tu["missing"], miss))
    return time.time() - t0, budget_s


def main(argv):
    t0 = time.time()
    tmp = tempfile.mkdtemp(prefix="busroute_")
    fails, times = [], {}

    def want(ok, text):
        if not ok:
            fails.append(text)
    try:
        pcb = make_board(tmp)
        o1, o2, oa, ob = (os.path.join(tmp, d) for d in ("out1", "out2", "outA", "outB"))
        m, code, log = run(tmp, "ok", o1, pictures=True)
        if "error" in m:
            want(False, "the benchmark routes could not be built: " + m["error"])
            raise StopIteration
        hard = [f for f in m["findings"] if f["hard"]]
        want(not hard, "geometry findings: " + "; ".join("%s %s" % (f["kind"], f["text"]) for f in hard))
        c = m["connectivity"]
        left = {k: v for k, v in c["drc_by_type_group"].items() if k not in IGNORE}
        want(not left, "DRC items on the group: %r %r" % (left, [i for i in c["drc_group_items"] if i["type"] in left][:6]))
        want(c["drc_unconnected_group"] == 0 and c["pcbnew"]["fully_connected"] == 12, "connectivity: %r, DRC unconnected %d" % (c["pcbnew"], c["drc_unconnected_group"]))
        other = {k: v for k, v in c["drc_by_type_board"].items() if k not in IGNORE}
        want(not other and c["drc_unconnected_board"] == 0, "DRC items on the board: %r, unconnected %d" % (other, c["drc_unconnected_board"]))
        want(m["rules"]["canary"] and m["rules"]["canary"]["ok"], "rule canary: %r" % (m["rules"],))
        want(m["written"]["matches_model"], "the board file does not hold the copper the model has")
        d = m["length"]["max_abs_geometry_minus_drc"]
        want(d is not None and d <= 0.002 and not m["length"]["not_measured_by_drc"], "geometry against DRC lengths: max %r, unmeasured %r" % (d, m["length"]["not_measured_by_drc"]))
        got = {n: (v["length"], v["vias"]) for n, v in m["length"]["nets"].items()}
        want(got == EXPECT, "lengths / vias changed:\nEXPECT = %r" % (got,))
        lanes = "\n".join(n for n in m["notes"])
        want(lanes == LANES, "fan-out lanes / via field changed:\nLANES = %r" % (lanes,))
        ts = m["shape"]["track_shape"]
        want(all(ts[k] == 0 for k in ("off-grid", "staircase", "sharp", "tiny")), "track_shape: %r" % ({k: ts[k] for k in ("off-grid", "staircase", "sharp", "crowded", "tiny")},))
        want(m["vias"]["stitching"] == 4 and m["vias"]["max"] == 2 and not m["vias"]["over_limit"], "vias: %r" % (m["vias"],))
        want(code == 0 and m["ok"], "the full build did not pass (exit %d)" % code)
        want(len(m.get("pictures", [])) == 4 and all(os.path.getsize(os.path.join(o1, p)) > 20000 for p in m["pictures"]), "pictures: %r" % (m.get("pictures"),))

        m2, code2, _ = run(tmp, "ok", o2)
        same = open(os.path.join(o1, "bench.kicad_pcb"), "rb").read() == open(os.path.join(o2, "bench.kicad_pcb"), "rb").read()
        want(same and code2 == 0 and m2["length"]["nets"] == m["length"]["nets"], "a second build is not identical")

        ma, codea, _ = run(tmp, "main10", oa)              # the bundle nets alone, then the hand nets onto that board
        shutil.copy(os.path.join(HERE, "bench_routes.py"), os.path.join(oa, "bench_routes.py"))
        mb, codeb, _ = run(oa, "hand", ob)
        want(codea == 0 and codeb == 0, "group builds: exit %d and %d" % (codea, codeb))
        want(copper(os.path.join(ob, "bench.kicad_pcb")) == copper(os.path.join(o1, "bench.kicad_pcb")), "two group builds do not give the copper of the single build")
        want(mb.get("connectivity", {}).get("drc_by_type_board", {}).keys() <= IGNORE.keys() and mb["connectivity"]["drc_unconnected_board"] == 0,
             "DRC after the two group builds: %r" % (mb.get("connectivity", {}).get("drc_by_type_board"),))

        # a shared group (SHARED, chains, piece width): GND ties on the single build's board, built twice in place
        os_ = os.path.join(tmp, "outS")
        os.makedirs(os_)
        for ext in (".kicad_pcb", ".kicad_pro", ".kicad_dru", ".busroute.json"):
            shutil.copy(os.path.join(o1, "bench" + ext), os.path.join(os_, "bench" + ext))
        shutil.copy(os.path.join(HERE, "bench_ties.py"), os.path.join(os_, "bench_ties.py"))
        spcb = os.path.join(os_, "bench.kicad_pcb")
        before = copper(spcb)
        r1 = job.run(os.path.join(os_, "bench_ties.py"), write_board=True, out=os.path.join(tmp, "outS_m"), pictures=False, log=lambda *a: None)
        b1 = open(spcb, "rb").read()
        r2 = job.run(os.path.join(os_, "bench_ties.py"), write_board=True, out=os.path.join(tmp, "outS_m"), pictures=False, log=lambda *a: None)
        b2 = open(spcb, "rb").read()
        after = copper(spcb)
        gv = lambda c: sorted(v for v in c[1] if v[0] == "GND")
        new_t = sorted(set(after[0]) - set(before[0]))
        want(r1[1] == 0 and r2[1] == 0, "shared group: exit %d / %d, %r" % (r1[1], r2[1], [f["text"] for f in r1[0].get("findings", []) if f.get("hard")][:4]))
        want(b1 == b2, "shared group: a second build in place changed the board")
        want(set(before[0]) <= set(after[0]) and set(gv(before)) <= set(gv(after)) and len(gv(after)) == len(gv(before)) + 2,
             "shared group: the main group's copper or its ground vias did not stay (GND vias %d -> %d)" % (len(gv(before)), len(gv(after))))
        want(sorted(t[4] for t in new_t if t[1] == "L1") == [0.25, 0.3048] and len(new_t) == 5, "shared group: new tracks %r" % (new_t,))
        want([t[4] for t in new_t if t[1] == "L6" and t[2][1] < 8.0] == [0.2], "shared group: the piece inside BGA_MCU is not 0.2 wide (area_free_classes) %r" % (new_t,))
        want(r1[0].get("shape", {}).get("track_shape", {}).get("off-grid") == 0, "shared group: track_shape off-grid %r" % (r1[0].get("shape", {}).get("track_shape"),))

        neg = {}
        for v in ("order", "pitch", "viapad", "channel"):
            mv, cv, lv = run(tmp, v, fast=True)
            neg[v] = (mv, cv, lv)
        mv, cv, lv = neg["order"]
        kinds = {f["kind"] for f in mv.get("findings", []) if f["hard"]}
        want(cv == 1 and "ORDER" in kinds and "CROSS" in kinds and "lane FMC_D2 is left of lane FMC_D1 in the bundle but its terminal" in lv, "negative case order: exit %d\n%s" % (cv, lv[-1500:]))
        mv, cv, lv = neg["pitch"]
        want(cv == 2 and mv.get("error_type") == "PitchError" and "PITCH trunk leg 1 (SE): lanes FMC_D0 | FMC_D1 are 0.2000 mm centre to centre, 0.2286 needed" in lv
             and "0.0286 mm missing" in lv, "negative case pitch: exit %d\n%s" % (cv, lv[-1500:]))
        mv, cv, lv = neg["viapad"]
        want(cv == 1 and any(f["kind"] == "VIAPAD" and "is on pad U2.B1" in f["text"] for f in mv.get("findings", [])), "negative case viapad: exit %d\n%s" % (cv, lv[-1500:]))
        mv, cv, lv = neg["channel"]
        want(cv == 2 and any(f["kind"] == "CHANNEL" and "U1.P14" in f["text"] and "already carries FMC_D1 (N14)" in f["text"] for f in mv.get("findings", [])),
             "negative case channel: exit %d\n%s" % (cv, lv[-1500:]))

        # obstacles of the fast check: a second pad with the same number (shield tabs) and a keep-out inside a footprint
        oo = os.path.join(tmp, "outO")
        os.makedirs(oo)
        for ext in (".kicad_pro", ".kicad_dru"):
            shutil.copy(os.path.join(tmp, "bench" + ext), os.path.join(oo, "bench" + ext))
        obst_board(pcb, os.path.join(oo, "bench.kicad_pcb"))
        shutil.copy(os.path.join(HERE, "bench_obstacles.py"), os.path.join(oo, "bench_obstacles.py"))
        lo = []
        mo, co = job.run(os.path.join(oo, "bench_obstacles.py"), fast=True, log=lo.append)
        fo_ = [f for f in mo.get("findings", []) if f["hard"]]
        want(co == 1 and any(f["kind"] in ("GAP", "HOLE") and "pad X1.SH" in f["text"] and f["at"] and abs(f["at"][1] - 12.4) < 0.6 for f in fo_)
             and any(f["kind"] == "KEEPOUT" and "X1:contact" in f["text"] for f in fo_),
             "obstacles: exit %d, findings %r" % (co, [f["text"] for f in fo_]))
        # the length verdict: only nets with a length rule decide; the others are notes
        from busroute import metrics as bm
        lcv = bm.length_check({"FMC_D0": 0.001, "CANH": 1.65, "VDDCR": -0.033}, {"FMC_D0"})
        lcf = bm.length_check({"FMC_D0": 0.01, "CANH": 0.0}, {"FMC_D0"})
        want(lcv["ok"] and list(lcv["notes"]) == ["CANH", "VDDCR"] and not lcf["ok"] and lcf["max_ruled"] == 0.01,
             "length verdict: %r / %r" % (lcv, lcf))

        # fan-out options: a per-ball inner layer ("@L6") and routes drawn before as obstacles (keep)
        from busroute import Fanout, Profile
        bb = Board(pcb, (OX, OY))
        fo = Fanout(bb, Profile.from_project(pcb), "U1")
        r1 = fo.escape({"L12": "E:via@L6", "M12": "E:via"}, inner="L4")
        l12, m12 = r1.leads.get("L12"), r1.leads.get("M12")
        want(l12 is not None and m12 is not None and l12.layer == "L6" and m12.layer == "L4" and l12.pieces[-1][0] == "L6",
             "fan-out @layer: %s" % r1.text())
        if l12 is not None:
            r2 = fo.escape({"L12": "E:via@L6"}, inner="L4", keep={"FMC_D10": [("via", l12.via)]})
            l2 = r2.leads.get("L12")
            want((l2 is None and "L12" in r2.refused) or (l2 is not None and l2.via != l12.via),
                 "fan-out keep: the via of another net at %r did not move the dog-bone (%s)" % (l12.via, r2.text()))

        # plane layers (type power in the layer table: L2 ground, L5 power since 2026-11-23) take no tracks; L3 is a
        # routing layer like L4
        from busroute.routes import resolve
        from busroute.geom import RouteError
        pr = Profile.from_project(pcb)
        want(bb.planes == {"L2", "L5"}, "plane layers of the bench board: %r" % (bb.planes,))
        try:
            resolve(bb, pr, {"FMC_D10": [("L5", [(5.0, 30.0), (6.0, 30.0)])]}, open_ok=True)
            want(False, "a track on the plane layer L5 was accepted")
        except RouteError as e:
            want("plane layer" in str(e), "a track on L5: %s" % e)
        try:
            resolve(bb, pr, {"FMC_D10": [("L3", [(5.0, 30.0), (6.0, 30.0)])]}, open_ok=True)
        except RouteError as e:
            want(False, "a track on the routing layer L3 was refused: %s" % e)

        times["tune"], times["budget"] = tuning(tmp, want)
    except StopIteration:
        pass
    finally:
        keep = "--keep" in argv or fails
        if fails:
            print("FAIL busroute (%d); temp dir kept: %s" % (len(fails), tmp))
            print("\n".join("  " + f for f in fails))
        else:
            print("OK busroute: 12 nets (ring 0-3 fan-out, bundle with corner and per-leg gaps, join, via field), DRC clean, "
                  "geometry = DRC lengths, 2 builds identical, 2 groups = 1 build, 4 negative cases, obstacles (shield tab, footprint keep-out), "
                  "length verdict, fan-out @layer and keep, a shared group of ties; "
                  "tuning (bundle slots, bump, free site both-sided, raised amp, missing, budget %.1f s) %.0f s; %.0f s%s" % (
                      times.get("budget", 0), times.get("tune", 0), time.time() - t0, "; kept " + tmp if keep else ""))
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
