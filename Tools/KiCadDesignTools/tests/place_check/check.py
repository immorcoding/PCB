"""Regression benchmark for placement/place_check.py and placement/escape_check.py.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.tests.place_check.check

Builds a 40 x 30 mm six-layer board in a temp directory (origin 100, 100) from KiCad library footprints:

    H1   M3 hole at (4, 4)                      R4 3.9 mm from its centre          -> hole 1
    U1   QFN-16 3 x 3 at (20, 15)               pin 1 +3V3 with C1 2.000 mm away   -> within the limit; escape "plane"
                                                pin 14 +3V3B with C3 3.000 mm away -> over the 2.5 mm limit; "plane"
                                                pin 3 XTAL with C5 beside it        -> escape "local"
                                                pin 5 boxed in by a foreign L1 track -> escape "blocked"
                                                EP GND                              -> escape "plane", 1 via
                                                the other 12 pins: a foreign ring of L1 track around the part,
                                                L4 open                             -> escape "out", 1 via
    C2   +5V capacitor with no IC pin on its rail
    C4   bottom capacitor, its pad 1 under U1 pin 9                                  -> under 1
    R1 / R2 courtyards overlapping (area from the outlines)                                  -> overlap 1
    R3   across the right edge (centre inside)                                     -> outside 1
    R5   inside a board rule area that forbids footprints                          -> keepout 1
    R6   off the board                                                             -> parked 1 (19 of 20 placed)
    J1   1x2 header across the left edge, declared --edge J1=L                     -> not outside, body -0.27
    TP1  test pad boxed in by R7..R10, no room for its label                       -> silk 1; TP2 free

Prints one line, `OK ...` or `FAIL ...`; exit code 0 = pass. About 10 s.
"""
import json, os, shutil, sys, tempfile
import pcbnew
from pcbnew import VECTOR2I, FromMM as mm, ToMM

from Tools.KiCadDesignTools.core import heavy

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
LIB = r"D:\KiCad\share\kicad\footprints"
OX, OY = 100.0, 100.0
V = lambda x, y: VECTOR2I(mm(OX + x), mm(OY + y))


def fp(board, lib, name, ref, x, y, rot=0, value="", bottom=False):
    f = pcbnew.FootprintLoad(os.path.join(LIB, lib + ".pretty"), name)
    f.SetReference(ref)
    f.SetValue(value or name)
    board.Add(f)
    if bottom:
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    f.SetOrientationDegrees(rot)
    f.SetPosition(V(x, y))
    return f


def build(path):
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(6)
    nets = {}
    def net(n):
        if n not in nets:
            ni = pcbnew.NETINFO_ITEM(b, n)
            b.Add(ni)
            nets[n] = ni
        return nets[n]
    def setnets(f, m):
        for p in f.Pads():
            if p.GetNumber() in m:
                p.SetNet(net(m[p.GetNumber()]))
    for x0, y0, x1, y1 in ((0, 0, 40, 0), (40, 0, 40, 30), (40, 30, 0, 30), (0, 30, 0, 0)):
        s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
        s.SetStart(V(x0, y0)); s.SetEnd(V(x1, y1)); s.SetWidth(mm(0.1)); b.Add(s)
    h = fp(b, "MountingHole", "MountingHole_3.2mm_M3_Pad_Via", "H1", 4, 4)
    for p in h.Pads():
        p.SetNet(net("GND"))
    u = fp(b, "Package_DFN_QFN", "QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm", "U1", 20, 15)
    m = {str(k): "SIG%d" % k for k in range(1, 17)}
    m.update({"1": "+3V3", "3": "XTAL", "14": "+3V3B", "17": "GND"})
    setnets(u, m)
    pin = {p.GetNumber(): (ToMM(p.GetPosition().x) - OX, ToMM(p.GetPosition().y) - OY) for p in u.Pads()}
    cap = lambda ref, x, y, rot, n1, n2, val="100nF", bottom=False: setnets(
        fp(b, "Capacitor_SMD", "C_0402_1005Metric", ref, x, y, rot, val, bottom), {"1": n1, "2": n2})
    # C1: rail pad (pad 1; at +y for rotation 90) 2.0 mm due west of pin 1
    cap("C1", pin["1"][0] - 2.0, pin["1"][1] - 0.48, 90, "+3V3", "GND")
    # C3: rail pad (pad 1; at -x for rotation 0) 3.0 mm due north of pin 14
    cap("C3", pin["14"][0] + 0.48, pin["14"][1] - 3.0, 0, "+3V3B", "GND")
    cap("C5", pin["3"][0] - 1.6, pin["3"][1] + 0.3, 0, "GND", "XTAL", "15pF")
    cap("C2", 30, 25, 0, "+5V", "GND")
    # C4 on the bottom, its pad 1 (-x) under pin 9, pad 2 beyond the pin's end
    cap("C4", pin["9"][0] + 0.48, pin["9"][1], 0, "SIG20", "SIG21", bottom=True)
    res = lambda ref, x, y, rot=0, n1="R_A", n2="R_B": setnets(
        fp(b, "Resistor_SMD", "R_0402_1005Metric", ref, x, y, rot, "10k"), {"1": n1, "2": n2})
    res("R1", 30, 5); res("R2", 31.0, 5)
    res("R3", 39.5, 10)
    res("R4", 8.5, 6)
    res("R5", 30, 15)
    res("R6", 60, 40)
    z = pcbnew.ZONE(b)
    z.SetIsRuleArea(True); z.SetZoneName("no_parts"); ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); z.SetLayerSet(ls)
    for f_ in ("SetDoNotAllowTracks", "SetDoNotAllowVias", "SetDoNotAllowPads", "SetDoNotAllowZoneFills"):
        getattr(z, f_)(False)
    z.SetDoNotAllowFootprints(True)
    ch = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in ((28, 13), (32, 13), (32, 17), (28, 17)):
        ch.Append(mm(OX + x), mm(OY + y))
    ch.SetClosed(True); z.Outline().AddOutline(ch); b.Add(z)
    j = fp(b, "Connector_PinHeader_2.54mm", "PinHeader_1x02_P2.54mm_Vertical", "J1", 1.0, 20)
    setnets(j, {"1": "J_A", "2": "J_B"})
    t1 = fp(b, "TestPoint", "TestPoint_Pad_D1.0mm", "TP1", 10, 25, 0, "+3V3")
    t2 = fp(b, "TestPoint", "TestPoint_Pad_D1.0mm", "TP2", 33, 22, 0, "+5V")
    setnets(t1, {"1": "+3V3"}); setnets(t2, {"1": "+5V"})
    for ref, x, y, rot in (("R7", 10, 23.2, 0), ("R8", 10, 26.8, 0), ("R9", 7.7, 25, 90), ("R10", 12.3, 25, 90)):
        res(ref, x, y, rot)
    # foreign copper: a ring of L1 track around U1 (L4 stays open) and a U around pin 5
    def trk(pts, w, layer=pcbnew.F_Cu, n="WALL"):
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(b); t.SetStart(V(xa, ya)); t.SetEnd(V(xb, yb)); t.SetWidth(mm(w))
            t.SetLayer(layer); t.SetNet(net(n)); b.Add(t)
    trk([(14.5, 9.5), (25.5, 9.5), (25.5, 20.5), (14.5, 20.5), (14.5, 9.5)], 0.2)
    p5 = pin["5"]
    # (the U starts at the exposed pad's edge, so the pin cannot slip out between the two)
    trk([(p5[0] - 0.25, p5[1] - 0.6), (p5[0] - 0.25, p5[1] + 0.55), (p5[0] + 0.25, p5[1] + 0.55),
         (p5[0] + 0.25, p5[1] - 0.6)], 0.1)
    pcbnew.SaveBoard(path, b)
    return pin


def run(args):
    r = heavy.kicad_py(*args)
    return r.returncode, r.stdout.decode("utf-8", "replace")


def main():
    tmp = tempfile.mkdtemp(prefix="place_check_")
    try:
        path = os.path.join(tmp, "bench.kicad_pcb")
        build(path)
        # expected geometry from the courtyard outlines themselves (not the bounding boxes, which include the line)
        b = pcbnew.LoadBoard(path)
        F = {f.GetReference(): f for f in b.GetFootprints()}
        def cy(ref):
            ch = F[ref].GetCourtyard(pcbnew.F_CrtYd).Outline(0)
            pts = [(ToMM(ch.CPoint(i).x) - OX, ToMM(ch.CPoint(i).y) - OY) for i in range(ch.PointCount())]
            return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)
        r1, r2, r4 = cy("R1"), cy("R2"), cy("R4")
        exp_area = round((r1[2] - r2[0]) * (min(r1[3], r2[3]) - max(r1[1], r2[1])), 2)
        exp_hole = round(((r4[0] - 4) ** 2 + (r4[1] - 4) ** 2) ** 0.5, 2)          # R4's nearest corner to (4, 4)
        fails = []
        def want(name, got, exp):
            if got != exp:
                fails.append("%s: got %r, expected %r" % (name, got, exp))
        js = os.path.join(tmp, "place.json")
        rc, out = run(["Tools.KiCadDesignTools.placement.place_check", path, "--edge", "J1=L", "--limit", "2.5", "--json", js])
        R = json.load(open(js, encoding="utf-8"))
        want("exit code", rc, 1)
        want("placed", (R["parts"]["placed"], R["parts"]["total"]), (19, 20))
        want("parked", R["parts"]["parked"], ["R6"])
        want("outside", R["outside"], ["R3"])
        want("overlap", [(a, b) for a, b, _ in R["overlap"]], [("R1", "R2")] if R["overlap"] and R["overlap"][0][0] == "R1" else [("R2", "R1")])
        if R["overlap"]:
            want("overlap area", round(R["overlap"][0][2], 2), exp_area)
        want("hole", [(r, h, round(d, 2)) for r, h, d in R["hole"]], [("R4", "H1", exp_hole)])
        want("keepout", [k[0] for k in R["keepout"]], ["R5"])
        want("edge", (R["edge"]["J1"]["body_gap"], R["edge"]["J1"]["nearest_side"]), (-0.27, "L"))
        want("under", [tuple(u) for u in R["under"]], [("C4.1", "U1.9")])
        u1 = R["decoupling"]["per_ic"]["U1"]
        want("decoupling", (u1["pins"], u1["le_limit"], round(u1["worst"], 3), [o[0] for o in u1["over"]]), (2, 1, 3.0, ["14"]))
        caps = {c["ref"]: c for c in R["decoupling"]["caps"]}
        want("cap without pin", caps["C2"]["pin"], None)
        want("C1 distance", caps["C1"]["dist"], 2.0)
        want("silk", sorted(s[0] for s in R["silk"] if s[2]), ["TP1"])

        je = os.path.join(tmp, "escape.json")
        rc, out = run(["Tools.KiCadDesignTools.placement.escape_check", path, "--ref", "U1", "--window", "12", "7", "28", "23",
                       "--json", je])
        E = json.load(open(je, encoding="utf-8"))["U1"]
        want("escape exit code", rc, 1)
        st = {p: (r["status"], r["vias"]) for p, r in E.items()}
        want("escape local", sorted(p for p, s in st.items() if s == ("local", 0)), ["3"])
        want("escape plane rails", (st.get("1"), st.get("14")), (("plane", 1), ("plane", 1)))
        want("escape blocked", sorted(p for p, s in st.items() if s[0] == "blocked"), ["5"])
        want("escape plane", st.get("17"), ("plane", 1))
        outs = sorted((p for p, s in st.items() if s == ("out", 1)), key=int)
        want("escape out via 1", outs, [str(k) for k in range(1, 17) if k not in (1, 3, 5, 14)])
        if fails:
            print("FAIL " + "; ".join(fails))
            return 1
        print("OK place_check: 19/20 placed, 1 parked, outside 1, overlap 1, hole 1, keepout 1, under 1, decoupling "
              "2.000 / 3.000 mm, silk 1; escape_check: local 1, plane 3, blocked 1, out via 1 x12")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
