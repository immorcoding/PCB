"""Regression benchmark of planning/ (measure, check, serp, plan) (PROC-15).

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.tests.planning.check [--keep]

Builds a 30 x 20 mm six-layer board in a temp folder (fixture/: the empty board with the JLC06161H-3313E stackup, a
board.toml, a length_groups.json and a minimal .kicad_pro: Default class 0.1016 / 0.127, via 0.45 / 0.2, in-area
floors 0.09): parts U1 / U2 (SMD pads, circles 0.3), R1 (two 0.5 mm squares), J1 (plated pad 1.0 / drill 0.6), H1
(non-plated hole 1.0), a rule area BGA_A (x 1.5-5.5, y 3-12), a pour of net P on L3 (x 5-10, y 13-18, clearance 0.2)
and a ground pour on L6 over the board (it yields); copper written by busroute's text writer:

  A0    L1 U1.1 (3, 5) -> (10, 5), three humps of height 0.6, pitch 0.3, radius 0.15 (true arcs) to (11.8, 5), -> U2.1
        (25, 5): natural 22, adds 3 (2 x 0.6 - (4 - pi) 0.3) = 2.82743
  A1    L1 U1.2 (3, 7) -> (7, 7), via, L4 -> (19, 7), via, L1 -> U2.2 (25, 7): 22 + 2 x 1.3932 (L1-L4 via height)
  CK    L1 U1.3 (3, 9) -> (10, 9) -> (12, 11) R1.1:  7 + 2 sqrt 2
  CK_R  R1.2 (13, 11) -> (15, 11), via, L3 -> (21, 11), via, L1 -> (23, 9) -> (25, 9) U2.3: 10 + 2 sqrt 2 + 2 x 0.2572
  X     L4 (10, 7.35) -> (14, 7.35);  Y  L3 (5, 1.8) -> (10, 1.8);  Z  L3 (20, 2.5) -> (30, 2.5), width 0.2

Expected:
  measure   the four lengths, vias, natural length and the serpentine block of A0 (9 arcs, radius 0.15), every trace
            complete; the clock sum, the address lines against it and the window of length_groups.json (A0 +1.656
            outside -1 .. +1.62, A1 +1.615 inside)
  check     the present routes of A0 A1 CK CK_R against the rest: 0 violations. A planned A1 whose L4 piece runs at
            y 7.15 and a planned net B (L3 (6, 12.9) -> (20, 12.9) -> (20, 14.1), via there): exactly
            A1 / X on L4 0.0984 < 0.127; B / pour P on L3 0.0492 < 0.2 (the pour's clearance); B's via copper / H1's
            hole 0.175 < 0.2 on each of L1 L3 L4 L6 (the ground pour on L6 yields: no finding there)
  plan      pre / tail copy the present A1 round the planned L4 piece: planned length 25.2107; A0 with its humps
            stripped is 22.0; A0 drawn as a plan block (same humps) is 24.828 by the RTE-2 formula (0.858 p; the
            block record keeps what it adds to 0.001), 0.0006 above the true arcs
  serp      added(3, 0.6, 0.3) = 2.8278, amp_for of it = 0.6; the block rules: S1 (L3, 3 humps 0.6, straight
            1.7 / 1.0) ok, its height limited by Y to 0.9084 (capacity 4.678); S2 (height 0.4 < 0.5) not ok; S3 (on
            L1 inside BGA_A, a block-free layer) not ok
  free      L3 region x 21-29, y 1-4 with Z across it at a clearance of 0.3: about 17.6 mm2 free in two pieces of
            about 8.8 (raster: within 0.25, one row of cells along the region is 0.2 mm2; 17.4 = 8.8 + 8.6 on 2026-11-24)

Prints one line, `OK ...` or `FAIL ...`; exit code 0 = pass. --keep leaves the temp folder.
"""
import math, os, shutil, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "fixture")
import pcbnew                                                        # noqa: E402
from Tools.KiCadDesignTools.core import config                        # noqa: E402
from Tools.KiCadDesignTools.routing.busroute.board import Board, write  # noqa: E402
from Tools.KiCadDesignTools.planning import measure, check as C, serp  # noqa: E402
from Tools.KiCadDesignTools.planning.plan import Plan                 # noqa: E402

OX = OY = 100.0
CU = {"L%d" % (i + 1): n for i, n in enumerate(["F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu"])}
W = 0.1016
VIA = (0.45, 0.2)
S2 = math.sqrt(2)
H14, H13 = 1.3932, 0.2572
EXPECT_LEN = {"A0": 22 + 3 * (1.2 - (4 - math.pi) * 0.3), "A1": 22 + 2 * H14, "CK": 7 + 2 * S2, "CK_R": 10 + 2 * S2 + 2 * H13}
EXPECT_VIAS = {"A0": 0, "A1": 2, "CK": 0, "CK_R": 2}
EXPECT_VIOL = [("L1", "B", "H1", 0.175, 0.2), ("L3", "B", "H1", 0.175, 0.2), ("L3", "B", "P", 0.0492, 0.2), ("L4", "A1", "X", 0.0984, 0.127),
               ("L4", "B", "H1", 0.175, 0.2), ("L6", "B", "H1", 0.175, 0.2)]


def hump_arcs(x0, y0, n, amp, pitch):
    """Arcs and legs of n humps towards -y (side L travelling east) from (x0, y0): [("arc", s, m, e) | ("seg", a, b)]."""
    r = pitch / 2
    c45 = r * math.cos(math.pi / 4)
    P = lambda u, v: (round(x0 + u, 6), round(y0 - v, 6))
    out = []
    s = 0.0
    for _ in range(n):
        out.append(("arc", P(s, 0), P(s + c45, r - c45), P(s + r, r)))
        out.append(("seg", P(s + r, r), P(s + r, amp - r)))
        out.append(("arc", P(s + r, amp - r), P(s + 2 * r, amp), P(s + 3 * r, amp - r)))
        out.append(("seg", P(s + 3 * r, amp - r), P(s + 3 * r, r)))
        out.append(("arc", P(s + 3 * r, r), P(s + 4 * r - c45, r - c45), P(s + 4 * r, 0)))
        s += 2 * pitch
    return out


def make_board(tmp):
    pcb = os.path.join(tmp, "bench.kicad_pcb")
    shutil.copyfile(os.path.join(FIXTURE, "six_layer.kicad_pcb"), pcb)
    b = pcbnew.LoadBoard(pcb)
    mm = pcbnew.FromMM
    V = lambda x, y: pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))
    nets = {}

    def net(name):
        if name not in nets:
            nets[name] = pcbnew.NETINFO_ITEM(b, name); b.Add(nets[name])
        return nets[name]

    def chain(pts):
        ch = pcbnew.SHAPE_LINE_CHAIN()
        for x, y in pts:
            ch.Append(mm(OX + x), mm(OY + y))
        ch.SetClosed(True)
        return ch
    for a, c in (((0, 0), (30, 0)), ((30, 0), (30, 20)), ((30, 20), (0, 20)), ((0, 20), (0, 0))):
        s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(V(*a)); s.SetEnd(V(*c))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); b.Add(s)
    z = pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetZoneName("BGA_A"); z.SetLayerSet(pcbnew.LSET.AllCuMask())
    for f in ("SetDoNotAllowTracks", "SetDoNotAllowVias", "SetDoNotAllowPads", "SetDoNotAllowZoneFills", "SetDoNotAllowFootprints"):
        getattr(z, f)(False)
    z.Outline().AddOutline(chain([(1.5, 3), (5.5, 3), (5.5, 12), (1.5, 12)])); b.Add(z)
    parts = {"U1": [("1", (3, 5), "A0"), ("2", (3, 7), "A1"), ("3", (3, 9), "CK")],
             "U2": [("1", (25, 5), "A0"), ("2", (25, 7), "A1"), ("3", (25, 9), "CK_R")],
             "R1": [("1", (12, 11), "CK"), ("2", (13, 11), "CK_R")]}
    for ref, pads in parts.items():
        fp = pcbnew.FOOTPRINT(b); fp.SetReference(ref); fp.SetPosition(V(*pads[0][1]))
        for num, xy, n in pads:
            p = pcbnew.PAD(fp); p.SetNumber(num); p.SetAttribute(pcbnew.PAD_ATTRIB_SMD); p.SetLayerSet(pcbnew.PAD.SMDMask())
            shape, size = (pcbnew.PAD_SHAPE_RECT, 0.5) if ref == "R1" else (pcbnew.PAD_SHAPE_CIRCLE, 0.3)
            p.SetShape(pcbnew.PADSTACK.ALL_LAYERS, shape); p.SetSize(pcbnew.PADSTACK.ALL_LAYERS, pcbnew.VECTOR2I(mm(size), mm(size)))
            p.SetPosition(V(*xy)); p.SetNet(net(n)); fp.Add(p)
        b.Add(fp)
    for ref, xy, size, drill, attr, n in (("J1", (14, 15), 1.0, 0.6, pcbnew.PAD_ATTRIB_PTH, "J"), ("H1", (20, 15), 1.0, 1.0, pcbnew.PAD_ATTRIB_NPTH, None)):
        fp = pcbnew.FOOTPRINT(b); fp.SetReference(ref); fp.SetPosition(V(*xy))
        p = pcbnew.PAD(fp); p.SetNumber("1" if n else ""); p.SetAttribute(attr)
        p.SetShape(pcbnew.PADSTACK.ALL_LAYERS, pcbnew.PAD_SHAPE_CIRCLE); p.SetSize(pcbnew.PADSTACK.ALL_LAYERS, pcbnew.VECTOR2I(mm(size), mm(size)))
        p.SetDrillSize(pcbnew.VECTOR2I(mm(drill), mm(drill)))
        p.SetLayerSet(pcbnew.PAD.PTHMask() if n else pcbnew.PAD.UnplatedHoleMask()); p.SetPosition(V(*xy))
        if n:
            p.SetNet(net(n))
        fp.Add(p); b.Add(fp)
    for name, layer, pts in (("P", pcbnew.In2_Cu, [(5, 13), (10, 13), (10, 18), (5, 18)]),
                             ("GND", pcbnew.B_Cu, [(0.5, 0.5), (29.5, 0.5), (29.5, 19.5), (0.5, 19.5)])):
        z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(net(name)); z.SetZoneName("pour_" + name)
        z.SetLocalClearance(mm(0.2)); z.SetMinThickness(mm(0.2)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        z.Outline().AddOutline(chain(pts)); b.Add(z)
    for n in ("A0", "A1", "CK", "CK_R", "X", "Y", "Z"):
        net(n)
    pcbnew.SaveBoard(pcb, b)
    # copper as text (busroute's writer), then fill the pours with it in place
    segs, arcs = [], []
    segs.append(("A0", "L1", (3.0, 5.0), (10.0, 5.0), W))
    for it in hump_arcs(10.0, 5.0, 3, 0.6, 0.3):
        if it[0] == "arc":
            arcs.append(("A0", "L1", it[1], it[2], it[3], W))
        else:
            segs.append(("A0", "L1", it[1], it[2], W))
    segs.append(("A0", "L1", (11.8, 5.0), (25.0, 5.0), W))
    segs += [("A1", "L1", (3.0, 7.0), (7.0, 7.0), W), ("A1", "L4", (7.0, 7.0), (19.0, 7.0), W), ("A1", "L1", (19.0, 7.0), (25.0, 7.0), W)]
    segs += [("CK", "L1", (3.0, 9.0), (10.0, 9.0), W), ("CK", "L1", (10.0, 9.0), (12.0, 11.0), W)]
    segs += [("CK_R", "L1", (13.0, 11.0), (15.0, 11.0), W), ("CK_R", "L3", (15.0, 11.0), (21.0, 11.0), W),
             ("CK_R", "L1", (21.0, 11.0), (23.0, 9.0), W), ("CK_R", "L1", (23.0, 9.0), (25.0, 9.0), W)]
    segs += [("X", "L4", (10.0, 7.35), (14.0, 7.35), W), ("Y", "L3", (5.0, 1.8), (10.0, 1.8), W), ("Z", "L3", (20.0, 2.5), (30.0, 2.5), 0.2)]
    vias = [("A1", (7.0, 7.0)) + VIA + (True,), ("A1", (19.0, 7.0)) + VIA + (True,), ("CK_R", (15.0, 11.0)) + VIA + (True,), ("CK_R", (21.0, 11.0)) + VIA + (True,)]
    write(pcb, pcb, "bench", segs, vias, ["A0", "A1", "CK", "CK_R", "X", "Y", "Z"], (OX, OY), CU, arcs=arcs)
    b = pcbnew.LoadBoard(pcb)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(pcb, b)
    for f in ("board.toml", "length_groups.json", "bench.kicad_pro"):      # the project file after SaveBoard (it writes a default one)
        shutil.copyfile(os.path.join(FIXTURE, f), os.path.join(tmp, f))
    return pcb


def near(a, b, tol):
    return abs(a - b) <= tol


def main(argv):
    t0 = time.time()
    tmp = tempfile.mkdtemp(prefix="planning_")
    fails = []
    F = fails.append
    try:
        pcb = make_board(tmp)
        cfg = config.load(tmp)
        G = measure.groups(cfg)
        board = Board(pcb, cfg.origin, fills=True)
        # ---- measure
        res = measure.measure(cfg, board, G["bus"])
        for n, L in EXPECT_LEN.items():
            r = res[n]
            if not near(r["len"], L, 0.0006) or r["vias"] != EXPECT_VIAS[n] or not r["ok"] or r["unused"]:
                F("measure %s: len %.4f vias %d ok %s unused %d, expected %.4f / %d" % (n, r["len"], r["vias"], r["ok"], r["unused"], L, EXPECT_VIAS[n]))
        a0 = res["A0"]
        if not (near(a0["natural"], 22.0, 0.0006) and len(a0["blocks"]) == 1 and a0["blocks"][0]["humps_arcs"] == 9 and near(a0["blocks"][0]["r"], 0.15, 1e-3)
                and near(a0["blocks"][0]["adds"], EXPECT_LEN["A0"] - 22, 0.0006)):
            F("measure A0: natural %.4f blocks %r" % (a0["natural"], [(b["humps_arcs"], b["adds"], b["r"]) for b in a0["blocks"]]))
        txt = measure.report(res, G)
        want_lines = ["clock 23.17 (CK 9.83 + R 13.34, natural 23.17); address 24.79 - 24.83, vs clock +1.62 / +1.66",
                      "address window -1 .. +1.62 mm of the clock: 1 / 2 inside; outside: A0"]
        for w in want_lines:
            if w not in txt:
                F("measure report lacks %r:\n%s" % (w, "\n".join(txt)))
        # ---- check: the present routes are clean
        rules = C.Rules.of(cfg, board)
        Pl = Plan(cfg, board, rules)
        P = C.board_prims(board, rules, G["bus"])
        for n in G["bus"]:
            C.net_prims(P, rules, Pl.Net(n).keep_present())
        v0 = C.check(P, G["bus"])
        if v0:
            F("check of the present routes: %d violations %r" % (len(v0), v0[:5]))
        # ---- check: a planned A1 and a planned net B with known conflicts
        a1 = Pl.pre("A1", (7.0, 7.0)).hop("L4", (7.15, 7.15), (18.85, 7.15), (19.0, 7.0))
        Pl.tail(a1, (19.0, 7.0))
        bnet = Pl.Net("B").track("L3", [(6.0, 12.9), (20.0, 12.9), (20.0, 14.1)]).via((20.0, 14.1))
        P = C.board_prims(board, rules, ["A1", "B"])
        C.net_prims(P, rules, a1)
        C.net_prims(P, rules, bnet)
        viol = C.check(P, ["A1", "B"])
        got = sorted((k[0], k[1], k[2].split(".")[0].lstrip("~"), v[0], v[1]) for k, v in C.aggregate(viol, 99))
        if [(g[0], g[1], g[2], round(g[3], 4), g[4]) for g in got] != EXPECT_VIOL:
            F("planned conflicts %r, expected %r" % (got, EXPECT_VIOL))
        # ---- plan: lengths through pre / tail / strip / block
        La1 = Pl.length(a1)
        want = 4 + 2 * H14 + 2 * 0.15 * S2 + 11.7 + 6
        if not near(La1, want, 1e-4) or a1.n_vias() != 2:
            F("planned A1 %.4f vias %d, expected %.4f / 2" % (La1, a1.n_vias(), want))
        st = Pl.Net("A0").keep_present(strip_serp=True)
        if not near(Pl.length(st), 22.0, 1e-3):
            F("A0 with the humps stripped: %.4f, expected 22.0" % Pl.length(st))
        pa0 = Pl.Net("A0").track("L1", [(3.0, 5.0), (9.3, 5.0)]).block((25.0, 5.0), "L", 3, 0.6, tag="T")
        if not near(Pl.length(pa0), 22 + round(serp.added(3, 0.6, 0.3), 3), 1e-9) or not near(Pl.length(pa0) - EXPECT_LEN["A0"], 0.0006, 0.0001):
            F("A0 as a plan block %.4f (measured %.4f)" % (Pl.length(pa0), res["A0"]["len"]))
        # ---- serp
        if not near(serp.added(3, 0.6, 0.3), 2.8278, 1e-6) or not near(serp.amp_for(2.8278, 3, 0.3), 0.6, 1e-9):
            F("serp.added / amp_for %.6f %.6f" % (serp.added(3, 0.6, 0.3), serp.amp_for(2.8278, 3, 0.3)))
        nets = {"S1": Pl.Net("S1").track("L3", [(5.0, 3.0), (6.0, 3.0)]).block((9.5, 3.0), "L", 3, 0.6, tag="Z1"),
                "S2": Pl.Net("S2").track("L3", [(12.0, 3.0), (13.0, 3.0)]).block((16.5, 3.0), "L", 3, 0.4, tag="Z1"),
                "S3": Pl.Net("S3").track("L1", [(1.8, 11.5), (2.0, 11.5)]).block((5.4, 11.5), "R", 2, 0.6, tag="Z2")}
        P = C.board_prims(board, rules, [])
        for n in nets.values():
            C.net_prims(P, rules, n)
        recs = {r["net"]: r for r in serp.block_rules(nets, P, rules, set(cfg.get("plan.block_free_layers")))}
        s1 = recs["S1"]
        if not (s1["rules_ok"] and near(s1["straight_before"], 1.7, 1e-3) and near(s1["straight_after"], 1.0, 1e-3) and s1["limited_by"] == "Y"
                and near(s1["amp_max"], 0.9084, 1e-3) and near(s1["capacity"], 4.68, 0.006)):
            F("block rules S1 %r" % s1)
        if recs["S2"]["rules_ok"] or recs["S3"]["rules_ok"] or not recs["S3"]["axis_parallel"]:
            F("block rules S2 %r S3 %r" % (recs["S2"], recs["S3"]))
        # ---- free area
        fr = C.free_area(board, rules, {"r": (21.0, 1.0, 29.0, 4.0)}, 0.30, layers=["L3"])["r"]["L3"]
        if not (near(fr["free_mm2"], 17.6, 0.25) and len(fr["largest_pieces_mm2"]) == 2 and all(near(x, 8.8, 0.25) for x in fr["largest_pieces_mm2"])):
            F("free area %r, expected 17.6 in two pieces of 8.8" % fr)
        summary = "A0 %.4f (natural %.4f), A1 %.4f, clock %.4f; %d planned conflicts; S1 a_max %.4f; free %.1f mm2 %s" % (
            res["A0"]["len"], a0["natural"], res["A1"]["len"], res["CK"]["len"] + res["CK_R"]["len"], len(got), s1["amp_max"], fr["free_mm2"], fr["largest_pieces_mm2"])
    except Exception as e:
        import traceback
        F("exception: %s\n%s" % (e, traceback.format_exc()))
        summary = ""
    finally:
        keep = "--keep" in argv or fails
        if fails:
            print("FAIL planning (%d); temp dir kept: %s" % (len(fails), tmp))
            print("\n".join("  " + f for f in fails))
        else:
            print("OK planning: %s; %.0f s%s" % (summary, time.time() - t0, "; kept " + tmp if keep else ""))
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
