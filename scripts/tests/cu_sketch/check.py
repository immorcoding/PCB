"""Regression benchmark for scripts/cu_sketch.py.

    D:\\KiCad\\bin\\python.exe scripts\\tests\\cu_sketch\\check.py

Builds a 40 x 30 mm six-layer board in a temp directory (board origin at 100, 100; nets GND, +3V3, +5V,
+3V3A; ten vias, a through-hole pad, an SMD capacitor, two test pads on short tracks, a rule area, a
hand-made ground zone; a rule file with through-hole thermal / SMD solid) and a sketch with eight regions:

    L1  whole GND, and a +5V pour over a via, the capacitor pad and the through-hole pad (swallowed whole);
        a ground via stands in the middle of the pour, 2.5 mm of copper left on either side of its hole
    L2  whole GND
    L3  whole +3V3, a +5V block shaped like a dumbbell (two 8 x 8 lobes joined by a bar 1.2 mm wide),
        a +3V3A block 0.5 mm to the right of it        -> three blocks, the plane gap everywhere 0.5 mm
    L4  a +5V dumbbell whose 0.4 mm bar is cut by the ground via: one lobe has a via, the other nothing
    L6  a +3V3A pour over its two vias

Expected:
  check    the good sketch passes with no warning; four bad ones are each reported with their reason and
           nothing else: an edge at 30 degrees [angle], two blocks 0.3 mm apart [gap], a bow-tie outline
           [self-cross], a pour that covers half of the through-hole pad [th-pad]; a bad sketch is not applied
  apply    8 zones; a second run says "unchanged" and leaves the file byte for byte the same; applying to a
           fresh copy of the bare board gives the same file again; still "unchanged" after KiCad refilled
           and saved the board; the rule area and the hand-made zone are still there
  measure  after KiCad's own fill: 0 edges off the 45 degree grid; one piece per zone except the L4 region
           (2 pieces = 1 fragment, 1 of them unconnected, DRC isolated_copper 1); blocks L2 1, L3 3, L4 2;
           L3 gaps 0.500 mm (+-0.01) for all three pairs; L1 pour to ground 0.200 mm (+-0.01); narrowest
           connection 1.200 mm (+-0.02) for the L3 +5V block (the bar, both vias sit in the lobes) and
           2.500 mm (+-0.05) for the L1 pour (20 - 17 mm minus the hole radius 0.3 + 0.2); 0 unconnected
           items, no starved thermal; with --skip-areas on the rule area around one via the L3 block has a
           single anchor left and no narrowest connection
  read     gives back the eight regions with the same vertices; with the old sketch the text comes back
           identical; after a zone is dragged the changed outline, the edges off the grid and the
           out-of-date `whole` zone are reported and comments survive
Prints one line, `OK ...` or `FAIL ...`; exit code 0 = pass. About 10 s.
"""
import json, os, shutil, subprocess, sys, tempfile, time
import pcbnew
from pcbnew import VECTOR2I, FromMM as mm

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, SCRIPTS)
import cu_sketch

OX, OY = 100, 100
GAP_TOL, NECK_TOL, NECK_TOL_ROUND = 0.01, 0.02, 0.05

DRU = """(version 1)
(rule "tht_thermal"
  (condition "A.Type == 'Pad' && A.Pad_Type == 'Through-hole'")
  (constraint zone_connection thermal_reliefs)
  (constraint thermal_spoke_width (min 0.254mm))
  (constraint thermal_relief_gap (min 0.254mm))
  (constraint min_resolved_spokes 2))
(rule "smd_solid"
  (condition "A.Type == 'Pad' && A.Pad_Type == 'SMD'")
  (constraint zone_connection solid))
"""

SKETCH = """# benchmark sketch of scripts/tests/cu_sketch/check.py
origin 100 100
layers 6
gap 0.5

region L1_GND GND L1 whole minwidth=0.3
region L2_GND GND L2 whole

# the power plane: +3V3 is what is left around the two blocks
region L3_3V3 +3V3 L3 whole
region L3_5V +5V L3              # dumbbell, bar 1.2 wide
  4,4  12,4  12,7.4  16,7.4  16,4  24,4
  24,12  16,12  16,8.6  12,8.6  12,12  4,12
region L3_3V3A +3V3A L3
  24.5,4  34,4  34,12  24.5,12

region L1_5V +5V L1 priority=2   # via, C1.1, and J1.1 swallowed whole
  17,6  23,6  23,24  22,25  18,25  17,24
region L6_3V3A +3V3A L6
  27,5  35,5  35,11  27,11

# cut in two by the ground via at 20,12.6: the lower lobe hangs on nothing
region L4_CUT +5V L4
  18,6  22,6  22,10  20.2,10  20.2,15  22,15
  22,19  18,19  18,15  19.8,15  19.8,10  18,10
"""

BAD = {     # name: (text to replace, replacement, code expected, words expected in the message)
    "30 degree edge": ("27,5  35,5  35,11  27,11", "27,5  35,5  35,11  29,11  27,9.845", "angle", ("L6_3V3A", "(29, 11) -> (27, 9.845)", "30.0 degrees")),
    "blocks 0.3 apart": ("24.5,4  34,4  34,12  24.5,12", "24.3,4  34,4  34,12  24.3,12", "gap", ("L3_5V", "L3_3V3A", "0.300 mm apart", "(24.150")),
    "bow-tie": ("27,5  35,5  35,11  27,11", "27,5  33,11  33,5  27,11", "self-cross", ("L6_3V3A", "crosses")),
    "half a through-hole pad": ("17,6  23,6  23,24  22,25  18,25  17,24", "17,6  23,6  23,21  22,22  18,22  17,21", "th-pad", ("L1_5V", "J1.1", "(20.000, 22.000)")),
}


def board(path):
    b = pcbnew.CreateEmptyBoard()
    b.SetCopperLayerCount(6)
    nets = {}
    for n in ("GND", "+3V3", "+5V", "+3V3A"):
        nets[n] = pcbnew.NETINFO_ITEM(b, n); b.Add(nets[n])
    P = lambda x, y: VECTOR2I(mm(x + OX), mm(y + OY))
    for x1, y1, x2, y2 in ((0, 0, 40, 0), (40, 0, 40, 30), (40, 30, 0, 30), (0, 30, 0, 0)):
        s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(P(x1, y1)); s.SetEnd(P(x2, y2))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); b.Add(s)
    for net, x, y in (("+5V", 8, 8), ("+5V", 20, 8), ("+3V3A", 30, 8), ("+3V3A", 32, 10), ("+3V3", 2, 2), ("+3V3", 38, 28),
                      ("GND", 2, 28), ("GND", 38, 2), ("GND", 26.5, 15), ("GND", 20, 12.6)):
        v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetWidth(pcbnew.F_Cu, mm(0.6)); v.SetDrill(mm(0.3))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(nets[net]); b.Add(v)

    def footprint(ref, pads):
        fp = pcbnew.FOOTPRINT(b); fp.SetReference(ref); fp.SetPosition(P(pads[0][2], pads[0][3])); b.Add(fp)
        for num, net, x, y, w, h, drill in pads:
            p = pcbnew.PAD(fp); p.SetNumber(num); p.SetPosition(P(x, y)); p.SetSize(pcbnew.F_Cu, VECTOR2I(mm(w), mm(h)))
            if drill:
                p.SetAttribute(pcbnew.PAD_ATTRIB_PTH); p.SetShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_CIRCLE)
                p.SetDrillSize(VECTOR2I(mm(drill), mm(drill))); p.SetLayerSet(pcbnew.PAD.PTHMask())
            else:
                p.SetAttribute(pcbnew.PAD_ATTRIB_SMD); p.SetShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_RECT); p.SetLayerSet(pcbnew.PAD.SMDMask())
            p.SetNet(nets[net]); fp.Add(p)

    def track(net, x1, y1, x2, y2):
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(x1, y1)); t.SetEnd(P(x2, y2)); t.SetWidth(mm(0.3)); t.SetLayer(pcbnew.F_Cu); t.SetNet(nets[net]); b.Add(t)

    def zone(name, layer, pts, net=None):
        z = pcbnew.ZONE(b); z.SetZoneName(name); z.SetLayer(layer)
        if net:
            z.SetNet(nets[net])
        else:
            z.SetIsRuleArea(True)
            for f in (z.SetDoNotAllowZoneFills, z.SetDoNotAllowTracks, z.SetDoNotAllowVias, z.SetDoNotAllowPads, z.SetDoNotAllowFootprints):
                f(False)
        o = z.Outline(); o.NewOutline()
        for x, y in pts:
            o.Append(mm(x + OX), mm(y + OY))
        b.Add(z)

    footprint("J1", [("1", "+5V", 20, 22, 2.0, 2.0, 1.0)])
    footprint("C1", [("1", "+5V", 22, 15, 1.0, 1.5, 0), ("2", "GND", 24.5, 15, 1.0, 1.5, 0)])
    footprint("TP1", [("1", "+3V3", 4, 2, 1.0, 1.0, 0)]); track("+3V3", 2, 2, 4, 2)
    footprint("TP2", [("1", "+3V3A", 30, 6.5, 1.0, 1.0, 0)]); track("+3V3A", 30, 8, 30, 6.5)
    zone("BGA", pcbnew.F_Cu, ((6, 6), (10, 6), (10, 10), (6, 10)))
    zone("hand_gnd", pcbnew.B_Cu, ((1, 22), (8, 22), (8, 29), (1, 29)), "GND")
    pcbnew.SaveBoard(path, b)


def run(*args):
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "cu_sketch.py")] + list(args), capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "image handler" not in l)
    return r.returncode, out


def write(path, text):
    open(path, "w", encoding="utf-8", newline="\n").write(text)


def shapes(text):
    sk = cu_sketch.parse(text, 6)
    return sorted((r.name, r.net, r.layer, r.whole, cu_sketch.canonical(r.pts) if r.pts else ()) for r in sk.regions)


def main():
    t0 = time.time()
    tmp = tempfile.mkdtemp(prefix="cu_sketch_")
    bare, pcb, sketch = (os.path.join(tmp, n) for n in ("bare.kicad_pcb", "t.kicad_pcb", "sketch.txt"))
    fails = []

    def want(ok, text):
        if not ok:
            fails.append(text)
    try:
        board(bare)
        shutil.copy(bare, pcb)
        write(os.path.join(tmp, "t.kicad_dru"), DRU)
        write(os.path.join(tmp, "bare.kicad_dru"), DRU)
        write(sketch, SKETCH)

        # check
        code, out = run("check", sketch)
        want(code == 0 and "0 error(s), 0 warning(s)" in out, "check without a board: exit %d\n%s" % (code, out))
        code, out = run("check", sketch, "--board", pcb)
        want(code == 0 and "0 error(s), 0 warning(s)" in out, "check with the board: exit %d\n%s" % (code, out))
        p = os.path.join(tmp, "bad.txt")
        for name, (old, new, reason, words) in BAD.items():
            assert old in SKETCH
            write(p, SKETCH.replace(old, new))
            code, out = run("check", p, "--board", pcb)
            errs = [l for l in out.splitlines() if l.strip().startswith("ERROR")]
            want(code == 1 and len(errs) == 1 and "[%s]" % reason in errs[0] and all(w in errs[0] for w in words),
                 "bad sketch '%s': wanted exactly one [%s] error with %s; exit %d\n%s" % (name, reason, words, code, out))
        code, out = run("apply", p, pcb)
        want(code == 1 and "nothing written" in out and open(pcb, "rb").read() == open(bare, "rb").read(), "apply of a bad sketch must not write: exit %d\n%s" % (code, out))

        # apply: idempotent and deterministic
        code, out = run("apply", sketch, pcb)
        want(code == 0 and "8 zones written" in out, "apply: exit %d\n%s" % (code, out))
        first = open(pcb, "rb").read()
        code, out = run("apply", sketch, pcb)
        want(code == 0 and "unchanged" in out and open(pcb, "rb").read() == first, "second apply changed the board: exit %d\n%s" % (code, out))
        again = os.path.join(tmp, "again.kicad_pcb")
        code, out = run("apply", sketch, bare, "-o", again)
        want(code == 0 and open(again, "rb").read() == first, "apply to a fresh copy gave a different file: exit %d\n%s" % (code, out))
        want(os.path.isfile(os.path.join(tmp, "again.kicad_dru")), "apply -o did not bring the rule file along")

        # fill with KiCad itself, then measure
        mj, dj = os.path.join(tmp, "m.json"), os.path.join(tmp, "drc.json")
        code, out = run("measure", pcb, "--refill", "--drc", dj, "--json", mj)
        want(code == 0 and os.path.isfile(mj), "measure: exit %d\n%s" % (code, out))
        if os.path.isfile(mj):
            m = json.load(open(mj, encoding="utf-8"))
            z = {r["zone"]: r for r in m["zones"]}
            want(len(z) == 8, "zones measured: %s" % sorted(z))
            want(all(r["off_grid_edges"] == 0 for r in m["zones"]), "edges off the 45 degree grid: %s" % {k: r["off_grid_edges"] for k, r in z.items()})
            got = {k: (r["pieces"], r["fragments"], r["unconnected_pieces"]) for k, r in z.items()}
            want(all(v == ((2, 1, 1) if k == "cu:L4_CUT" else (1, 0, 0)) for k, v in got.items()), "pieces / fragments / unconnected: %s" % got)
            want(z.get("cu:L3_5V", {}).get("edges") == 12 and z.get("cu-whole:L3_3V3", {}).get("edges") == 8 + 24 and z.get("cu-whole:L1_GND", {}).get("edges") == 4,
                 "edge counts: %s" % {k: r["edges"] for k, r in z.items()})
            want(m["plane_blocks"] == {"L2": 1, "L3": 3, "L4": 2}, "plane blocks: %s" % m["plane_blocks"])
            g3, g1 = m["layers"]["L3"]["gaps"], m["layers"]["L1"]["min_gap"]
            want(len(g3) == 3 and all(abs(g["mm"] - 0.5) <= GAP_TOL for g in g3), "L3 gaps: %s" % g3)
            want(g1 and abs(g1["mm"] - 0.2) <= GAP_TOL, "L1 gap: %s" % g1)
            n = z.get("cu:L3_5V", {})
            want(n.get("neck_mm") is not None and abs(n["neck_mm"] - 1.2) <= NECK_TOL and n.get("neck_note") == "", "neck of L3_5V: %s %s" % (n.get("neck_mm"), n.get("neck_note")))
            at = n.get("neck_at") or [0, 0]
            want(111.5 <= at[0] <= 116.5 and 107 <= at[1] <= 109, "neck location of L3_5V: %s" % at)
            n = z.get("cu:L1_5V", {})
            want(n.get("anchors") == 3 and n.get("neck_mm") is not None and abs(n["neck_mm"] - 2.5) <= NECK_TOL_ROUND,
                 "L1_5V (via, SMD pad, through-hole pad; 2.5 mm beside the ground via): anchors %s neck %s %s" % (n.get("anchors"), n.get("neck_mm"), n.get("neck_lets_go")))
            at = n.get("neck_at") or [0, 0]
            want(116.5 <= at[0] <= 123.5 and 111.5 <= at[1] <= 113.7, "neck location of L1_5V: %s" % at)
            d = m["drc"] or {}
            want(d.get("unconnected_copper") == 0 and d.get("unconnected_total") == 0, "unconnected: %s" % d)
            v = d.get("violations", {"starved_thermal": 1})
            want("starved_thermal" not in v and v.get("isolated_copper") == 1, "DRC: %s" % v)
            want("最窄连接" in out and "电源面块数: L2 1  L3 3  L4 2" in out, "measure text:\n%s" % out)
        code, out = run("apply", sketch, pcb)
        want(code == 0 and "unchanged" in out, "apply after KiCad's refill and save is not a no-op: exit %d\n%s" % (code, out))
        mj2 = os.path.join(tmp, "m2.json")
        code, out = run("measure", pcb, "--all-zones", "--skip-areas", "BGA", "--json", mj2)
        m2 = {r["zone"]: r for r in json.load(open(mj2, encoding="utf-8"))["zones"]} if code == 0 else {}
        want(len(m2) == 9 and "hand_gnd" in m2 and m2["cu:L3_5V"]["neck_mm"] is None and m2["cu:L3_5V"]["neck_note"] == "fewer than 2 anchors",
             "measure --all-zones --skip-areas BGA: exit %d\n%s" % (code, out))

        # read back
        code, out = run("read", pcb, "-o", os.path.join(tmp, "back.txt"))
        back = open(os.path.join(tmp, "back.txt"), encoding="utf-8").read() if code == 0 else ""
        want(code == 0 and cu_sketch.parse(back, 6).origin == (0, 0), "read: exit %d\n%s" % (code, out))
        shift = lambda s: [(n, net, l, w, tuple((x + OX * 10**6, y + OY * 10**6) for x, y in pts)) for n, net, l, w, pts in s]
        want(back and shapes(back) == shift(shapes(SKETCH)), "read (no old sketch) does not give the sketch's regions:\n%s" % back)
        code, out = run("read", pcb, "--sketch", sketch, "-o", os.path.join(tmp, "back2.txt"))
        want(code == 0 and open(os.path.join(tmp, "back2.txt"), encoding="utf-8").read() == SKETCH, "read --sketch changed an unchanged sketch: exit %d\n%s" % (code, out))

        # zones dragged in KiCad: one corner moved off the grid, another zone moved by 1 mm; other zones untouched
        b = pcbnew.LoadBoard(pcb)
        others = sorted((zz.GetZoneName(), zz.GetNumCorners()) for zz in b.Zones() if not zz.GetZoneName().startswith("cu"))
        want(others == [("BGA", 4), ("hand_gnd", 4)], "the rule area and the hand-made zone after apply: %s" % others)
        for zz in b.Zones():
            if zz.GetZoneName() == "cu:L6_3V3A":
                zz.Outline().SetVertex(0, VECTOR2I(mm(OX + 27.3), mm(OY + 4.2)))
            if zz.GetZoneName() == "cu:L3_3V3A":
                for i in range(zz.Outline().TotalVertices()):
                    v = zz.Outline().CVertex(i)
                    zz.Outline().SetVertex(i, VECTOR2I(v.x + mm(1), v.y))
        moved = os.path.join(tmp, "moved.kicad_pcb")
        pcbnew.SaveBoard(moved, b)
        code, out = run("read", moved, "--sketch", sketch, "-o", os.path.join(tmp, "back3.txt"))
        back3 = open(os.path.join(tmp, "back3.txt"), encoding="utf-8").read()
        want(code == 1 and "OFF GRID cu:L6_3V3A: 2 edge(s)" in out and "L3_3V3A: outline changed" in out and "cu-whole:L3_3V3: its outline is not what the sketch derives" in out,
             "read of a dragged board: exit %d\n%s" % (code, out))
        want("25.5,4  35,4  35,12  25.5,12" in back3 and "# dumbbell, bar 1.2 wide\n  4,4  12,4" in back3 and "# the power plane" in back3,
             "read of a dragged board: text\n%s" % back3)
    except Exception:
        import traceback
        fails.append("exception: " + traceback.format_exc())
    secs = time.time() - t0
    if fails:
        print("FAIL cu_sketch (%d) in %.0f s; temp dir kept: %s" % (len(fails), secs, tmp))
        print("\n".join("  " + f for f in fails))
    else:
        shutil.rmtree(tmp, ignore_errors=True)
        print("OK cu_sketch: check (4 bad sketches named), apply twice, read back, measure (L3 3 blocks, gap 0.500, necks 1.2 and 2.5 mm, 1 loose piece found); %.0f s" % secs)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
