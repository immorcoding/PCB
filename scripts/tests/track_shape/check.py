"""Regression benchmark of scripts/track_shape.py (PROC-15): arcs in the runs.

    D:\\KiCad\\bin\\python.exe scripts\\tests\\track_shape\\check.py [--keep]

An empty six-layer board (stm32h743_sdram/make_project.py) gets four short routes on F.Cu, written as text by
busroute's writer (net names only, as KiCad 10 keeps them):

  A  a 45-degree corner, 0.1004 mm of straight, then an arc of radius 0.25 turning on the same way by 90
     degrees (RTE-8's signal: the old script stopped the run at the arc and reported nothing) -> one `sharp`
  B  a serpentine from busroute.tune (two humps, pitch 0.3, legs between tangent arcs) -> nothing
  C  a straight followed by an arc that starts 30 degrees off its direction -> one `arc-joint`
  D  no arcs: two 45-degree corners 0.2 mm apart -> one `sharp`, as before
  E  a straight that changes width (0.09 to 0.1016, in line, as at a rule-area edge), 0.1 mm of the wide straight,
     then an arc turning 90 degrees -> nothing (the width change is no corner; reported sharp before 2026-11-24)
Expected: sharp 2 (A, D), arc-joint 1 (C), off-grid / staircase / crowded / tiny 0, 8 arcs (A 1, B 5, C 1, E 1).
The track_shape.py before arcs were followed reported sharp 1 (D only) on this board.

Prints one line, `OK ...` or `FAIL ...`; exit code 0 = pass.
"""
import math, os, re, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", ".."))
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "stm32h743_sdram"))
import make_project                                         # noqa: E402
from busroute.board import write                            # noqa: E402
from busroute import tune                                   # noqa: E402

CU = {"L%d" % (i + 1): n for i, n in enumerate(["F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu"])}
W = 0.1016


def arc_from(p, h, r, turn):
    """Arc from p heading h (degrees, y down) turning by `turn` degrees (> 0: towards larger angles). -> (mid, end, end heading)."""
    sg = 1 if turn > 0 else -1
    hr = math.radians(h)
    c = (p[0] - sg * r * math.sin(hr), p[1] + sg * r * math.cos(hr))
    a0 = math.atan2(p[1] - c[1], p[0] - c[0])
    pt = lambda t: (round(c[0] + r * math.cos(a0 + t), 6), round(c[1] + r * math.sin(a0 + t), 6))
    return pt(math.radians(turn) / 2), pt(math.radians(turn)), h + turn


def step(p, h, d):
    return (round(p[0] + d * math.cos(math.radians(h)), 6), round(p[1] + d * math.sin(math.radians(h)), 6))


def routes():
    segs, arcs = [], []
    # A: corner, 0.1004 mm, arc on the same way
    a0, a1 = (2.0, 2.0), (4.0, 2.0)
    a2 = (4.071, 2.071)
    segs += [("A", "L1", a0, a1, W), ("A", "L1", a1, a2, W)]
    m, e, h = arc_from(a2, 45, 0.25, 90)
    arcs.append(("A", "L1", a2, m, e, W))
    segs.append(("A", "L1", e, step(e, h, 1.0), W))
    # B: a serpentine drawn by tune.draw on a straight at y = 4
    prims, base = tune.draw(("single", 2, 0.5, 0.15), 1.0, 1)
    p0 = (2.0, 4.0)
    W_ = lambda q: (round(p0[0] + q[0], 6), round(p0[1] + q[1], 6))
    segs.append(("B", "L1", p0, W_((1.0, 0.0)), W))
    j = W_((1.0, 0.0))
    for pr in prims:
        end = W_(pr[3] if pr[0] == "arc" else pr[2])
        if pr[0] == "arc":
            arcs.append(("B", "L1", j, W_(pr[2]), end, W))
        else:
            segs.append(("B", "L1", j, end, W))
        j = end
    segs.append(("B", "L1", j, W_((1.0 + base + 1.0, 0.0)), W))
    # C: straight, then an arc that starts 30 degrees off
    c0, c1 = (2.0, 7.0), (4.0, 7.0)
    segs.append(("C", "L1", c0, c1, W))
    m, e, h = arc_from(c1, 30, 0.5, 60)
    arcs.append(("C", "L1", c1, m, e, W))
    # D: two 45-degree corners 0.2 mm apart (no arcs)
    segs += [("D", "L1", (2.0, 9.0), (4.0, 9.0), W), ("D", "L1", (4.0, 9.0), (4.1414, 9.1414), W), ("D", "L1", (4.1414, 9.1414), (4.1414, 10.5), W)]
    # E: thin straight, wide straight in line (0.1 mm), arc turning 90 degrees
    e0, e1, e2 = (2.0, 12.0), (4.0, 12.0), (4.1, 12.0)
    segs += [("E", "L1", e0, e1, 0.09), ("E", "L1", e1, e2, W)]
    m, e, h = arc_from(e2, 0, 0.25, 90)
    arcs.append(("E", "L1", e2, m, e, W))
    segs.append(("E", "L1", e, step(e, h, 1.0), W))
    return segs, arcs


def main(argv):
    t0 = time.time()
    tmp = tempfile.mkdtemp(prefix="track_shape_")
    fails = []
    try:
        src = os.path.join(tmp, "empty.kicad_pcb")
        make_project.make_pcb(src)
        segs, arcs = routes()
        dst = os.path.join(tmp, "shapes.kicad_pcb")
        write(src, dst, "shapes", segs, [], [], (100.0, 100.0), CU, arcs=arcs)
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "track_shape.py"), dst], capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = r.stdout
        num = lambda k: int(re.search(r"^%s: (\d+)" % re.escape(k), out, re.M).group(1)) if re.search(r"^%s: (\d+)" % re.escape(k), out, re.M) else None
        got = {k: num(k) for k in ("off-grid", "staircase", "sharp", "crowded", "arc-joint")}
        got["tiny"] = int(re.search(r"^tiny \(< 0.1 mm\): (\d+)", out, re.M).group(1))
        got["arcs"] = int(re.search(r"^\d+ segments, (\d+) arcs", out, re.M).group(1))
        want = {"off-grid": 0, "staircase": 0, "sharp": 2, "crowded": 0, "arc-joint": 1, "tiny": 0, "arcs": 8}
        if got != want:
            fails.append("counts %r, expected %r\n%s" % (got, want, out))
        sharp = [l.split()[0] for l in out.splitlines() if l.startswith("    ") and "turns" in l and "segment" in l]
        if sorted(sharp) != ["A", "D"]:
            fails.append("sharp on %r, expected A and D\n%s" % (sharp, out))
        if not re.search(r"^    C F\.Cu at \(4\.0, 7\.0\): an arc joint turns 30\.0 deg", out, re.M):
            fails.append("the arc joint of C is not reported as 30 degrees\n%s" % out)
    finally:
        keep = "--keep" in argv or fails
        if fails:
            print("FAIL track_shape (%d); temp dir kept: %s" % (len(fails), tmp))
            print("\n".join("  " + f for f in fails))
        else:
            print("OK track_shape: corner + 0.1 mm + arc is sharp, serpentine legs are not, a width change + 0.1 mm + arc is not, "
                  "a 30-degree arc joint is reported, arc-free sharp as before; %.0f s%s" % (time.time() - t0, "; kept " + tmp if keep else ""))
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
