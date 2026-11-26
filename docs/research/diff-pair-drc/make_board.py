"""Build the differential-pair DRC fixture `dpdrc.kicad_pcb` (+ .kicad_pro, predict.json).

Issue #44 (map #26): experiments E1-E5 of docs/research/diff-pair-tooling.md section 9 (branch
research/diff-pair-tooling). Every pair is a separate pair of nets /<CASE>_P, /<CASE>_N, so one board holds all
cases and one DRC run per rule set reads them all.

All coordinates are integer nanometres, written straight into VECTOR2I: what this script computes is exactly what
the board file holds. predict.json carries, per pair, the uncoupled length and the coupled segment pairs that the
source reading of section 3.4 predicts (exact integer parallelism, same layer, projection overlap, gap window; the
"no other copper between" test is NOT modelled, so a DRC value that differs from the prediction points at it).

Run with KiCad's Python (through core.heavy, see run.py):
    D:\\KiCad\\bin\\python.exe -I make_board.py <outdir> <template.kicad_pro>
"""
import json, math, os, sys
from fractions import Fraction
import pcbnew
from pcbnew import VECTOR2I

OUT = os.path.abspath(sys.argv[1])
TEMPLATE_PRO = os.path.abspath(sys.argv[2])
STEM = "dpdrc"
MM = 1_000_000
W = 100_000            # track width 0.1 mm
S = 250_000            # centre spacing 0.25 mm -> edge gap 0.15 mm

b = pcbnew.CreateEmptyBoard()
b.SetCopperLayerCount(2)
LAYERS = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu}
nets, geom, notes = {}, {}, {}


def net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(b, name)
        b.Add(n)
        nets[name] = n
        geom[name] = []
    return nets[name]


def V(p):
    return VECTOR2I(int(p[0]), int(p[1]))


def line(n, layer, p0, p1):
    p0, p1 = (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1]))
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(V(p0)); t.SetEnd(V(p1)); t.SetWidth(W)
    t.SetLayer(LAYERS[layer]); t.SetNet(net(n)); b.Add(t)
    geom[n].append(("L", layer, p0, p1))


def polyline(n, layer, pts):
    for p0, p1 in zip(pts, pts[1:]):
        line(n, layer, p0, p1)


def arc(n, layer, c, r, a0_deg, a1_deg):
    """circular arc about integer centre c, radius r (nm), from angle a0 to a1 (degrees, KiCad y down)."""
    pt = lambda a: (round(c[0] + r * math.cos(math.radians(a))), round(c[1] + r * math.sin(math.radians(a))))
    p0, pm, p1 = pt(a0_deg), pt((a0_deg + a1_deg) / 2), pt(a1_deg)
    a = pcbnew.PCB_ARC(b)
    a.SetStart(V(p0)); a.SetMid(V(pm)); a.SetEnd(V(p1)); a.SetWidth(W)
    a.SetLayer(LAYERS[layer]); a.SetNet(net(n)); b.Add(a)
    geom[n].append(("A", layer, p0, p1, c, r, a0_deg, a1_deg))
    return p0, p1


def via(n, p, d=450_000, drill=200_000):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(V(p)); v.SetWidth(d); v.SetDrill(drill)
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(net(n)); b.Add(v)


def footprint(ref, pos, pads):
    """pads: (number, (x, y) absolute nm, net, (w, h) nm, die nm)"""
    fp = pcbnew.FOOTPRINT(b)
    fp.SetReference(ref); fp.SetValue(ref); fp.SetPosition(V(pos))
    fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
    for num, p, nn, size, die in pads:
        pad = pcbnew.PAD(fp)
        pad.SetNumber(str(num)); pad.SetShape(pcbnew.PAD_SHAPE_RECT)
        pad.SetSize(V(size)); pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        pad.SetLayerSet(pad.SMDMask()); pad.SetPosition(V(p)); pad.SetNet(net(nn))
        if die:
            pad.SetPadToDieLength(int(die))
        fp.Add(pad)
    b.Add(fp)


def pair(case, note):
    notes[case] = note
    return "/%s_P" % case, "/%s_N" % case


# ============================================================================ E1: integer offsets, exact parallelism
X0 = 0
y = 0
# E1A: 45 deg, P integer, N = P + one integer vector (176777, -176777) -> centre distance 250000.4
P, N = pair("E1A", "45 deg, N = P + the same integer vector at both ends")
p0, p1 = (X0, y), (X0 + 5 * MM, y + 5 * MM)
o = (176_777, -176_777)
line(P, "F", p0, p1); line(N, "F", (p0[0] + o[0], p0[1] + o[1]), (p1[0] + o[0], p1[1] + o[1]))

# E1B / E1B2: float centreline, P = round(C + h), N = round(C - h) at each end separately (h = S/2 along the normal)
h = S / 2 / math.sqrt(2)
def offsets_from_float(cx, cy, L):
    c0, c1 = (cx, cy), (cx + L, cy + L)
    P0 = (round(c0[0] + h), round(c0[1] - h)); P1 = (round(c1[0] + h), round(c1[1] - h))
    N0 = (round(c0[0] - h), round(c0[1] + h)); N1 = (round(c1[0] - h), round(c1[1] + h))
    dp, dn = (P1[0] - P0[0], P1[1] - P0[1]), (N1[0] - N0[0], N1[1] - N0[1])
    return P0, P1, N0, N1, dp[0] * dn[1] - dp[1] * dn[0]

found = {}
for k in range(1, 400):
    cx, cy, L = 8 * MM + 0.37 * k, y + 0.23 * k, 5 * MM + 0.61 * k
    r = offsets_from_float(cx, cy, L)
    key = "par" if r[4] == 0 else "skew"
    found.setdefault(key, (cx, cy, L, r))
    if len(found) == 2:
        break
cx, cy, L, (P0, P1, N0, N1, cr) = found["skew"]
dev = (P1[0] - P0[0] - (N1[0] - N0[0]), P1[1] - P0[1] - (N1[1] - N0[1]))
P, N = pair("E1B", "45 deg, float centreline, each end of P and N rounded separately: direction vectors differ "
                   "by (%d, %d) nm, cross product %d" % (dev[0], dev[1], cr))
line(P, "F", P0, P1); line(N, "F", N0, N1)
cx, cy, L, (P0, P1, N0, N1, cr) = found["par"]
P, N = pair("E1B2", "as E1B, a centreline where the separate rounding happens to stay parallel (cross 0)")
P0, P1, N0, N1 = [(p[0] + 8 * MM, p[1]) for p in (P0, P1, N0, N1)]
line(P, "F", P0, P1); line(N, "F", N0, N1)

# E1C: as E1A, N's far end 1 nm off in x
P, N = pair("E1C", "45 deg, as E1A with N's far end moved 1 nm in x")
p0, p1 = (X0 + 24 * MM, y), (X0 + 29 * MM, y + 5 * MM)
line(P, "F", p0, p1); line(N, "F", (p0[0] + o[0], p0[1] + o[1]), (p1[0] + o[0] + 1, p1[1] + o[1]))

# E1D / E1E: horizontal 10 mm, N's far end 1 nm off in y / exact
y = 8 * MM
P, N = pair("E1D", "horizontal 10 mm, N's far end 1 nm off in y")
line(P, "F", (X0, y), (X0 + 10 * MM, y)); line(N, "F", (X0, y + S), (X0 + 10 * MM, y + S + 1))
P, N = pair("E1E", "horizontal 10 mm, exact (control)")
line(P, "F", (X0 + 14 * MM, y), (X0 + 24 * MM, y)); line(N, "F", (X0 + 14 * MM, y + S), (X0 + 24 * MM, y + S))

# E1G / E1H: centreline with two 45 deg bends: horizontal 3 mm, 45 deg 2 x 2 mm, horizontal 3 mm
y = 12 * MM
def bend_pair(case, x0, y0, mode):
    C = [(x0, y0), (x0 + 3 * MM, y0), (x0 + 5 * MM, y0 + 2 * MM), (x0 + 8 * MM, y0 + 2 * MM)]
    sides = {}
    for sgn, nm in ((-1, "P"), (1, "N")):
        pts = []
        if mode == "float":            # offset each vertex along the bisector, rounded separately
            for i, c in enumerate(C):
                dirs = []
                if i > 0:
                    dirs.append(((c[0] - C[i - 1][0]), (c[1] - C[i - 1][1])))
                if i < len(C) - 1:
                    dirs.append(((C[i + 1][0] - c[0]), (C[i + 1][1] - c[1])))
                ns = []
                for d in dirs:
                    l = math.hypot(*d); ns.append((-d[1] / l, d[0] / l))
                nx, ny = sum(n_[0] for n_ in ns) / len(ns), sum(n_[1] for n_ in ns) / len(ns)
                k = (S / 2) / (nx * nx + ny * ny)   # bisector scaled so the perpendicular offset is S/2
                pts.append((round(c[0] + sgn * k * nx), round(c[1] + sgn * k * ny)))
        else:                           # integer offset lines, corners by exact intersection
            a, bb = S // 2, 88_388      # horizontal: a; 45 deg: (bb, -bb) -> perpendicular 124999.4
            segs = []
            for c0, c1 in zip(C, C[1:]):
                d = (c1[0] - c0[0], c1[1] - c0[1])
                off =(0, sgn * a) if d[1] == 0 else (-sgn * bb, sgn * bb)
                segs.append(((c0[0] + off[0], c0[1] + off[1]), d))
            pts.append(segs[0][0])
            for (q0, d0), (q1, d1) in zip(segs, segs[1:]):
                den = d0[0] * d1[1] - d0[1] * d1[0]
                t = Fraction((q1[0] - q0[0]) * d1[1] - (q1[1] - q0[1]) * d1[0], den)
                x, yy = q0[0] + t * d0[0], q0[1] + t * d0[1]
                assert x.denominator == 1 and yy.denominator == 1, (x, yy)
                pts.append((int(x), int(yy)))
            last = segs[-1]
            pts.append((last[0][0] + last[1][0], last[0][1] + last[1][1]))
        sides[nm] = pts
    P, N = pair(case, "two 45 deg bends; offset by %s" % ("bisector, rounded per vertex" if mode == "float"
                                                          else "integer offset lines, exact corners"))
    polyline(P, "F", sides["P"]); polyline(N, "F", sides["N"])

bend_pair("E1G", X0, y, "float")
bend_pair("E1H", X0 + 14 * MM, y, "int")

# ============================================================================ E2: compensation bumps, arcs
y = 20 * MM
def straight_n(N, x0, y0):
    line(N, "F", (x0, y0 + S), (x0 + 10 * MM, y0 + S))

def bump_case(case, note, x0, y0, pts_p):
    P, N = pair(case, note)
    polyline(P, "F", [(x0 + px, y0 + py) for px, py in pts_p]); straight_n(N, x0, y0)
    return P, N

U = 100_000            # 0.1 mm
bump_case("E2Z", "straight pair 10 mm (control)", X0, y, [(0, 0), (100 * U, 0)])
bump_case("E2A", "rectangular bump on P away from N: h 0.3, top 0.6, vertical legs", X0 + 14 * MM, y,
          [(0, 0), (47 * U, 0), (47 * U, -3 * U), (53 * U, -3 * U), (53 * U, 0), (100 * U, 0)])
y = 23 * MM
bump_case("E2B", "rectangular bump on P towards N: h 0.02 (gap 0.15 -> 0.13), top 0.6", X0, y,
          [(0, 0), (47 * U, 0), (47 * U, 20_000), (53 * U, 20_000), (53 * U, 0), (100 * U, 0)])
bump_case("E2C", "trapezoid bump on P away from N: 45 deg legs, h 0.3, top 0.6", X0 + 14 * MM, y,
          [(0, 0), (44 * U, 0), (47 * U, -3 * U), (53 * U, -3 * U), (56 * U, 0), (100 * U, 0)])
y = 26 * MM
# E2D: rounded bump (project's tune.py shape): quarter arcs r 0.1, legs 0.1, top 0.6 at h 0.3
P, N = pair("E2D", "rounded bump on P away from N: quarter arcs r 0.1, legs 0.1, straight top 0.6 at h 0.3")
x0 = X0
line(P, "F", (x0, y), (x0 + 45 * U, y))
arc(P, "F", (x0 + 45 * U, y - U), U, 90, 0)               # (4.5, 0) -> (4.6, -0.1)
line(P, "F", (x0 + 46 * U, y - U), (x0 + 46 * U, y - 2 * U))
arc(P, "F", (x0 + 47 * U, y - 2 * U), U, 180, 270)        # (4.6, -0.2) -> (4.7, -0.3)
line(P, "F", (x0 + 47 * U, y - 3 * U), (x0 + 53 * U, y - 3 * U))
arc(P, "F", (x0 + 53 * U, y - 2 * U), U, 270, 360)        # (5.3, -0.3) -> (5.4, -0.2)
line(P, "F", (x0 + 54 * U, y - 2 * U), (x0 + 54 * U, y - U))
arc(P, "F", (x0 + 55 * U, y - U), U, 180, 90)             # (5.4, -0.1) -> (5.5, 0)
line(P, "F", (x0 + 55 * U, y), (x0 + 100 * U, y))
straight_n(N, x0, y)
# E2E: semicircle bump r 0.3
P, N = pair("E2E", "semicircle bump on P away from N, r 0.3")
x0 = X0 + 14 * MM
line(P, "F", (x0, y), (x0 + 47 * U, y))
arc(P, "F", (x0 + 50 * U, y), 3 * U, 180, 360)
line(P, "F", (x0 + 53 * U, y), (x0 + 100 * U, y))
straight_n(N, x0, y)
# E2F: 90 deg turn with concentric arcs (P outside r 1.125, N inside r 0.875)
y = 30 * MM
P, N = pair("E2F", "90 deg turn, concentric arcs r 1.125 / 0.875, then 3 mm down")
x0 = X0
c = (x0 + 5 * MM, y + 1 * MM)
line(P, "F", (x0, y - S // 2), (x0 + 5 * MM, y - S // 2)); arc(P, "F", c, MM + S // 2, 270, 360)
line(P, "F", (c[0] + MM + S // 2, c[1]), (c[0] + MM + S // 2, c[1] + 3 * MM))
line(N, "F", (x0, y + S // 2), (x0 + 5 * MM, y + S // 2)); arc(N, "F", c, MM - S // 2, 270, 360)
line(N, "F", (c[0] + MM - S // 2, c[1]), (c[0] + MM - S // 2, c[1] + 3 * MM))
# E2G: the same turn, P with the arc, N with a 45 deg chamfer (arc against lines)
P, N = pair("E2G", "90 deg turn, P arc r 1.125, N two-segment 45 deg chamfer")
x0 = X0 + 14 * MM
c = (x0 + 5 * MM, y + 1 * MM)
line(P, "F", (x0, y - S // 2), (x0 + 5 * MM, y - S // 2)); arc(P, "F", c, MM + S // 2, 270, 360)
line(P, "F", (c[0] + MM + S // 2, c[1]), (c[0] + MM + S // 2, c[1] + 3 * MM))
ri = MM - S // 2
polyline(N, "F", [(x0, y + S // 2), (x0 + 5 * MM, y + S // 2), (x0 + 5 * MM + ri, c[1]),
                  (x0 + 5 * MM + ri, c[1] + 3 * MM)])     # the chamfer is 45 deg: ri = c[1] - (y + S/2)

# ============================================================================ E3: pad-to-die, bend inside a pad
y = 40 * MM
def e3_case(case, note, x0, y0, die_p, pad_p, pts_p):
    P, N = pair(case, note)
    footprint("A" + case, (x0, y0), [(1, (x0, y0), P, pad_p, die_p), (2, (x0, y0 + 1 * MM), N, (300_000, 300_000), 0)])
    footprint("B" + case, (x0 + 10 * MM, y0), [(1, (x0 + 10 * MM, y0), P, (300_000, 300_000), 0),
                                                (2, (x0 + 10 * MM, y0 + 1 * MM), N, (300_000, 300_000), 0)])
    polyline(P, "F", [(x0 + px, y0 + py) for px, py in pts_p])
    line(N, "F", (x0, y0 + 1 * MM), (x0 + 10 * MM, y0 + 1 * MM))

e3_case("E3A", "straight 10 mm both; P's start pad has die_length 1.0 mm", X0, y, 1 * MM, (300_000, 300_000),
        [(0, 0), (10 * MM, 0)])
e3_case("E3B", "P bends inside its 0.6 mm start pad: (0,0)->(0.25,-0.25)->(0.5,0)->(10,0)", X0 + 14 * MM, y, 0,
        (600_000, 600_000), [(0, 0), (250_000, -250_000), (500_000, 0), (10 * MM, 0)])
y = 44 * MM
e3_case("E3C", "as E3B with a 0.3 mm start pad: the bend (0.25,-0.25) is outside the pad", X0, y, 0,
        (300_000, 300_000), [(0, 0), (250_000, -250_000), (500_000, 0), (10 * MM, 0)])

# ============================================================================ E4: skew rule that hits one net only
y = 50 * MM
for case, note in (("E4A", "skew within_diff_pairs, condition names only the P net"),
                   ("E4B", "skew within_diff_pairs, condition hits both nets (control)")):
    x0 = X0 if case == "E4A" else X0 + 14 * MM
    P, N = pair(case, note)
    line(P, "F", (x0, y), (x0 + 10 * MM, y))                                  # 10.000
    polyline(N, "F", [(x0, y + S), (x0 + 4 * MM, y + S), (x0 + 4 * MM, y + S + 500_000),
                      (x0 + 6 * MM, y + S + 500_000), (x0 + 6 * MM, y + S), (x0 + 10 * MM, y + S)])   # 11.000
y = 53 * MM
notes["E4C"] = "lone net /E4C_P (no /E4C_N on the board), skew within_diff_pairs on it"
line("/E4C_P", "F", (X0, y), (X0 + 10 * MM, y))

# ============================================================================ E5: paired layer change, vias
y = 58 * MM
VP = 700_000                    # signal via pitch
P, N = pair("E5A", "F.Cu pair jogs 45 deg out to a via pair (pitch 0.7), B.Cu pair jogs back; GND vias outside")
x0 = X0
xv = x0 + 5 * MM
j = VP // 2 - S // 2            # 225000 jog each side
for nm, sg in ((P, -1), (N, 1)):
    polyline(nm, "F", [(x0, y + sg * S // 2), (xv - j, y + sg * S // 2), (xv, y + sg * VP // 2)])
    via(nm, (xv, y + sg * VP // 2))
    polyline(nm, "B", [(xv, y + sg * VP // 2), (xv + j, y + sg * S // 2), (x0 + 10 * MM, y + sg * S // 2)])
via("/GND", (xv, y - VP // 2 - VP)); via("/GND", (xv, y + VP // 2 + VP))

# E5C-F: wide pair (centre spacing 0.85, gap 0.75) with a GND via between them at x 5 / 0.3 / 9.7 / none
WS = 850_000
for case, xg, note in (("E5C", 5 * MM, "wide pair (gap 0.75), GND via between them at the middle (x 5)"),
                       ("E5E", 300_000, "wide pair, GND via between them near the start (x 0.3)"),
                       ("E5F", 9_700_000, "wide pair, GND via between them near the end (x 9.7)"),
                       ("E5D", None, "wide pair, no via (control)")):
    k = ["E5C", "E5E", "E5F", "E5D"].index(case)
    x0, y0 = (X0 + 14 * MM * (k % 2), 62 * MM + 4 * MM * (k // 2))
    P, N = pair(case, note)
    line(P, "F", (x0, y0), (x0 + 10 * MM, y0)); line(N, "F", (x0, y0 + WS), (x0 + 10 * MM, y0 + WS))
    if xg is not None:
        via("/GND", (x0 + xg, y0 + WS // 2))

# E5G / E5H: wide pair with the GND via centred on the start / end of the overlap (x 0 / x 10)
for case, xg, x0 in (("E5G", 0, X0), ("E5H", 10 * MM, X0 + 14 * MM)):
    y0 = 70 * MM
    P, N = pair(case, "wide pair, GND via between them centred at x %g (an end of the overlap)" % (xg / MM))
    line(P, "F", (x0, y0), (x0 + 10 * MM, y0)); line(N, "F", (x0, y0 + WS), (x0 + 10 * MM, y0 + WS))
    via("/GND", (x0 + xg, y0 + WS // 2))

# ============================================================================ E1 sweep: how far off parallel still couples
# N's far end moved by d nm across the pair (towards P is avoided: away, so the gap only grows by d).
SWEEP = [1, 2, 3, 5, 10, 30, 100, 300, 1000, 3000, 10000]
for k, d in enumerate(SWEEP):          # horizontal 10 mm
    y0 = k * MM
    P, N = pair("E1T%02d" % k, "horizontal 10 mm, N's far end %d nm off (away from P)" % d)
    line(P, "F", (35 * MM, y0), (45 * MM, y0)); line(N, "F", (35 * MM, y0 + S), (45 * MM, y0 + S + d))
for k, d in enumerate(SWEEP):          # horizontal 1 mm
    y0 = 12 * MM + k * MM
    P, N = pair("E1U%02d" % k, "horizontal 1 mm, N's far end %d nm off (away from P)" % d)
    line(P, "F", (35 * MM, y0), (36 * MM, y0)); line(N, "F", (35 * MM, y0 + S), (36 * MM, y0 + S + d))
for k, d in enumerate(SWEEP):          # 45 deg, 5 x 5 mm, N's far end moved +d in x (away from P)
    x0, y0 = 40 * MM, 24 * MM + k * MM
    P, N = pair("E1V%02d" % k, "45 deg 7.07 mm, N's far end %d nm off in x" % d)
    p0, p1 = (x0, y0), (x0 + 5 * MM, y0 + 5 * MM)
    line(P, "F", p0, p1); line(N, "F", (p0[0] + o[0], p0[1] + o[1]), (p1[0] + o[0] + d, p1[1] + o[1]))

# ============================================================================ outline, save
edge = pcbnew.PCB_SHAPE(b)
edge.SetShape(pcbnew.SHAPE_T_RECT); edge.SetLayer(pcbnew.Edge_Cuts); edge.SetWidth(50_000)
edge.SetStart(V((-3 * MM, -3 * MM))); edge.SetEnd(V((50 * MM, 74 * MM)))
b.Add(edge)
os.makedirs(OUT, exist_ok=True)
pcb_path = os.path.join(OUT, STEM + ".kicad_pcb")
pcbnew.SaveBoard(pcb_path, b)

# ============================================================================ project: one net class, DP gap 0.15
pro = json.load(open(TEMPLATE_PRO, encoding="utf-8"))
ns = pro["net_settings"]
default = dict(next(c for c in ns["classes"] if c["name"] == "Default"))
default.update({"clearance": 0.1, "track_width": 0.1, "via_diameter": 0.45, "via_drill": 0.2,
                "diff_pair_gap": 0.15, "diff_pair_width": 0.1, "diff_pair_via_gap": 0.25})
ns["classes"] = [default]
ns["netclass_patterns"] = []
ns["netclass_assignments"] = None
pro["board"]["design_settings"]["rules"]["use_height_for_length_calcs"] = True
json.dump(pro, open(os.path.join(OUT, STEM + ".kicad_pro"), "w", encoding="utf-8"), indent=2)


# ============================================================================ predictions (source reading, 3.4)
def seg_len(g):
    if g[0] == "L":
        return math.dist(g[2], g[3])
    return g[5] * math.radians(abs(g[7] - g[6]))


def coupled_pairs(gp, gn, gmin, gmax):
    out = []
    for a in gp:
        for c in gn:
            if a[1] != c[1]:
                continue
            if a[0] == "L" and c[0] == "L":
                d1 = (a[3][0] - a[2][0], a[3][1] - a[2][1]); d2 = (c[3][0] - c[2][0], c[3][1] - c[2][1])
                if d1[0] ** 2 + d1[1] ** 2 <= 2 or d2[0] ** 2 + d2[1] ** 2 <= 2:
                    continue
                if d1[0] * d2[1] - d1[1] * d2[0] != 0:
                    continue                                   # not exactly parallel
                w = (c[2][0] - a[2][0], c[2][1] - a[2][1])
                if d1[0] * w[1] - d1[1] * w[0] == 0:
                    continue                                   # collinear
                l1 = math.hypot(*d1); u = (d1[0] / l1, d1[1] / l1)
                t0 = (c[2][0] - a[2][0]) * u[0] + (c[2][1] - a[2][1]) * u[1]
                t1 = (c[3][0] - a[2][0]) * u[0] + (c[3][1] - a[2][1]) * u[1]
                lo, hi = max(0.0, min(t0, t1)), min(l1, max(t0, t1))
                if hi - lo <= 0:
                    continue
                dist = abs(d1[0] * w[1] - d1[1] * w[0]) / l1
                gap = (dist - W) / MM
                ok = gap >= gmin - 0.0005 and (gmax is None or gap <= gmax + 0.0005)
                out.append({"p": [a[2], a[3]], "n": [c[2], c[3]], "len": round((hi - lo) / MM, 6),
                            "gap": round(gap, 6), "in_window": ok})
            elif a[0] == "A" and c[0] == "A":
                if math.dist(a[4], c[4]) >= W:
                    continue
                lo = max(min(a[6], a[7]), min(c[6], c[7])); hi = min(max(a[6], a[7]), max(c[6], c[7]))
                if hi - lo <= 0.001:
                    continue
                gap = (abs(a[5] - c[5]) - W) / MM
                ok = gap >= gmin - 0.0005 and (gmax is None or gap <= gmax + 0.0005)
                # coupled length of a concentric arc pair = the inner (shorter) arc (measured: E2F)
                out.append({"arc": True, "len": round(min(a[5], c[5]) * math.radians(hi - lo) / MM, 6),
                            "gap": round(gap, 6), "in_window": ok})
    return out


pred = {}
for case, note in notes.items():
    P, N = "/%s_P" % case, "/%s_N" % case
    tp = sum(seg_len(g) for g in geom.get(P, [])) / MM
    tn = sum(seg_len(g) for g in geom.get(N, [])) / MM
    entry = {"note": note, "len_P": round(tp, 6), "len_N": round(tn, 6)}
    if N in geom and P in geom:
        for tag, gmin, gmax in (("window", 0.14, 0.2), ("min_only", 0.14, None)):
            cps = coupled_pairs(geom[P], geom[N], gmin, gmax)
            coup = sum(c["len"] for c in cps if c["in_window"])
            entry[tag] = {"uncoupled": round(max(tp, tn) - coup, 6), "coupled": round(coup, 6),
                          "pairs": cps}
    pred[case] = entry
json.dump(pred, open(os.path.join(OUT, "predict.json"), "w", encoding="utf-8"), indent=1)
print("wrote", pcb_path, "nets:", len(nets), "cases:", len(notes))
