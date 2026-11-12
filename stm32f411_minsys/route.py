"""Hand routing of stm32f411_minsys: the nets that are not left to the autorouter.

    D:\\KiCad\\bin\\python.exe stm32f411_minsys\\route.py [--keep]

Coordinates are in the same local frame as place.py (mm, x along the board from
header pin 20, y across, negative = J3 row). Every polyline is checked here
before it is written: segments must run at a multiple of 45 degrees and
consecutive segments may turn by at most 45 degrees (interior angle >= 135).

Without --keep, all tracks and vias on the board are removed first, so the
script rebuilds the hand-routed copper from scratch. With --keep, only copper
on the nets listed in HAND_NETS is replaced (use after the autorouter has added
the GPIO nets).
"""
import math, os, sys
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "stm32f411_minsys.kicad_pcb")
OX, OY = 100.0, 100.0
F, B = pcbnew.F_Cu, pcbnew.B_Cu

HAND_NETS = {"/OSC_IN", "/OSC_OUT", "/USB_D+", "/USB_D-", "Net-(J1-CC1)", "Net-(J1-CC2)",
             "VBUS", "+5V", "+3V3", "+3.3VA", "/VBAT", "Net-(U1-VCAP1)", "GND",
             "Net-(D2-A)", "Net-(D4-A)", "/NRST", "/BOOT0", "/SWDIO", "/SWCLK"}

board = pcbnew.LoadBoard(PCB)
keep = "--keep" in sys.argv
stale = [t for t in board.GetTracks() if not keep or t.GetNetname() in HAND_NETS]
if stale:
    for t in stale:
        board.Remove(t)
    # after a Remove(), pcbnew hands back untyped objects from its collections,
    # so save and start again from a fresh load
    pcbnew.SaveBoard(PCB, board)
    board = pcbnew.LoadBoard(PCB)

PADS = {}
for fp in board.GetFootprints():
    for p in fp.Pads():
        PADS.setdefault((fp.GetReference(), p.GetNumber()),
                        (pcbnew.ToMM(p.GetPosition().x) - OX, pcbnew.ToMM(p.GetPosition().y) - OY))


def pad(ref, num):
    return PADS[(ref, str(num))]


def P(pt):
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + pt[0]), pcbnew.FromMM(OY + pt[1]))


def net(name):
    n = board.FindNet(name)
    if n is None:
        raise SystemExit(f"no net {name}")
    return n


def T(name, width, pts, layer=F):
    """Add a polyline. Raises if a segment is off the 45-degree grid or a corner is too sharp."""
    pts = [(round(x, 4), round(y, 4)) for x, y in pts]
    dirs = []
    for a, c in zip(pts, pts[1:]):
        dx, dy = c[0] - a[0], c[1] - a[1]
        if abs(dx) < 1e-4 and abs(dy) < 1e-4:
            raise SystemExit(f"{name}: zero-length segment at {a}")
        if not (abs(dx) < 2e-3 or abs(dy) < 2e-3 or abs(abs(dx) - abs(dy)) < 2e-3):
            raise SystemExit(f"{name}: segment {a} -> {c} is not at 0/45/90 degrees")
        dirs.append(math.degrees(math.atan2(dy, dx)))
    for i, (d1, d2) in enumerate(zip(dirs, dirs[1:])):
        turn = abs((d2 - d1 + 180) % 360 - 180)
        if turn > 45.5:
            raise SystemExit(f"{name}: corner at {pts[i + 1]} turns {turn:.0f} degrees")
    for a, c in zip(pts, pts[1:]):
        s = pcbnew.PCB_TRACK(board)
        s.SetStart(P(a)); s.SetEnd(P(c)); s.SetWidth(pcbnew.FromMM(width))
        s.SetLayer(layer); s.SetNet(net(name)); board.Add(s)


def V(name, pt):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(pt)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(pcbnew.F_Cu, pcbnew.FromMM(0.6)); v.SetDrill(pcbnew.FromMM(0.3))
    v.SetLayerPair(F, B); v.SetNet(net(name)); board.Add(v)


def to_y(p, d, y):
    """From p, travel diagonally (d = (+-1, +-1)) until reaching y."""
    k = (y - p[1]) / d[1]
    assert k > 0, (p, d, y)
    return (p[0] + d[0] * k, y)


def to_x(p, d, x):
    k = (x - p[0]) / d[0]
    assert k > 0, (p, d, x)
    return (x, p[1] + d[1] * k)


def esc(pin, k):
    """Point k mm (per axis) out from MCU pin `pin`, along the pad's own axis."""
    n = int(pin)
    d = (1, -1) if n <= 12 else (-1, -1) if n <= 24 else (-1, 1) if n <= 36 else (1, 1)
    p = pad("U1", pin)
    return (p[0] + d[0] * k, p[1] + d[1] * k)


NE, NW, SE, SW = (1, -1), (-1, -1), (1, 1), (-1, 1)

# GND vias beside pads the pours cannot reach, and the short stubs to them (filled in from DRC)
GND_VIAS = []
GND_STUBS = []

# ---------------------------------------------------------------- crystal
p5, p6 = pad("U1", 5), pad("U1", 6)
a = to_y(p5, NE, -2.30)
T("/OSC_IN", 0.254, [p5, a, (31.15, -2.30), (32.15, -3.30), (pad("C11", 1)[0], -3.30)])
a = to_x(p6, NE, 28.1)
T("/OSC_OUT", 0.254, [p6, a, (28.1, -4.9), (28.7, -5.5), (pad("Y1", 3)[0], -5.5)])

# ---------------------------------------------------------------- VDDA
p9 = pad("U1", 9)
T("+3.3VA", 0.25, [p9, to_x(p9, NE, 26.2), (26.2, -5.5)])
fbx = pad("FB1", 2)[0]
T("+3.3VA", 0.3, [(fbx, -5.5), (fbx, -7.0)])
T("+3.3VA", 0.2, [(35.62, -7.4), (35.42, -7.6), (27.5, -7.6), (27.3, -7.4), (27.3, -6.0), (26.9, -5.6)])

# ---------------------------------------------------------------- NRST
p7 = pad("U1", 7)
n1 = esc(7, 0.6)
T("/NRST", 0.2, [p7, n1, (n1[0], -4.1)])
V("/NRST", (n1[0], -4.1))
T("/NRST", 0.2, [(n1[0], -4.1), (n1[0], -6.9), (n1[0] + 0.7, -7.6), (39.0, -7.6)], B)
V("/NRST", (39.0, -7.6))
T("/NRST", 0.2, [(39.0, -7.6), (40.2, -7.6), (41.75, -6.05), (41.75, -5.53)], B)
V("/NRST", (41.75, -5.53))
T("/NRST", 0.2, [(41.75, -5.53), (42.6, -5.53)])
T("/NRST", 0.2, [(39.0, -7.6), (39.0, -6.3)])
T("/NRST", 0.2, [(39.0, -7.6), (38.1, -8.5), (38.1, -10.16)])

# ---------------------------------------------------------------- VCAP and MCU supply pins
p22, p24, p36, p48 = pad("U1", 22), pad("U1", 24), pad("U1", 36), pad("U1", 48)
T("Net-(U1-VCAP1)", 0.25, [p22, to_y(p22, NW, -2.6), (17.9, -2.6)])
T("+3V3", 0.25, [p24, to_y(p24, NW, -0.9), (17.9, -0.9)])
V("+3V3", (18.7, -0.9))
s = esc(36, 0.5)
T("+3V3", 0.25, [p36, s, (s[0], 6.3)])
T("+3V3", 0.25, [p48, to_y(p48, SE, 0.8), (30.5, 0.8)])

# ---------------------------------------------------------------- +3V3 distribution, top
T("+3V3", 0.5, [(12.84, -5.9), (16.2, -5.9)])                       # U2.5 - C2 - C3
T("+3V3", 0.5, [(14.7, -6.0), (14.7, -6.9), (14.4, -7.2), (6.04, -7.2), (5.08, -8.16), (5.08, -10.16)])  # J3 pin 18
T("+3V3", 0.3, [(13.2, -5.75), (13.86, -5.09), (13.86, -2.05), (14.16, -1.75), (16.9, -1.75), (17.4, -1.25)])  # to C6
V("+3V3", (15.05, -1.75))
T("+3V3", 0.3, [(35.95, 2.7), (37.38, 2.7)])                        # D3.A - R6.1, through the via
V("+3V3", (36.62, 2.7))
T("+3V3", 0.3, [(30.82, 3.6), (30.82, 1.1)])                        # up to C5
V("+3V3", (30.82, 3.6))
T("+3V3", 0.3, [(37.38, 3.0), (37.38, 4.3)])                        # R6.1 - R3.1
T("+3V3", 0.3, [(37.2, 4.6), (35.9, 4.6)])                          # R3.1 - C4.1
T("+3V3", 0.5, [(46.9, -3.81), (45.9, -3.81), (45.1, -3.01), (45.1, 4.73), (44.3, 5.53), (43.2, 5.53)])  # J2.1 - SW2.2
T("+3V3", 0.5, [(43.9, 5.8), (45.57, 5.8), (48.26, 8.49), (48.26, 10.16)])  # SW2.2 - J4 pin 1
T("+3V3", 0.3, [(37.6, -4.5), (37.6, -5.2)])                        # FB1.1
V("+3V3", (37.6, -4.5))
T("+3V3", 0.3, [(24.2, 6.9), (23.4, 6.9)])                          # C7
V("+3V3", (24.2, 6.9))
# +3V3, bottom: one run under the MCU between the thermal-via rows to the right-hand side,
# one along the lower-left edge to the bottom corner
T("+3V3", 0.5, [(15.05, -1.75), (21.39, -1.75), (26.74, 3.6), (35.72, 3.6), (36.62, 2.7),
                (40.39, 2.7), (46.9, -3.81)], B)
T("+3V3", 0.5, [(18.7, -0.9), (24.2, 4.6), (24.2, 6.9)], B)
T("+3V3", 0.3, [(46.5, -3.81), (38.29, -3.81), (37.6, -4.5)], B)   # J2.1 back to FB1

# ---------------------------------------------------------------- +5V
T("+5V", 0.5, [(6.75, -6.0), (6.85, -5.9), (10.56, -5.9)])          # D1.K - C1 - U2.1
T("+5V", 0.5, [(6.75, -6.0), (6.45, -6.3), (1.3, -6.3), (0.0, -7.6), (0.0, -10.16)])  # J3 pin 20
T("+5V", 0.3, [(10.56, -4.0), (9.7, -4.0), (9.5, -4.2), (9.5, -5.4), (10.0, -5.9)])   # CE
T("+5V", 0.5, [(0.0, -10.16), (1.56, -8.6), (48.3, -8.6), (49.2, -7.7), (49.2, 7.95), (48.3, 8.85),
               (44.49, 8.85), (43.18, 10.16)], B)                   # round the edge to J4 pin 3

# ---------------------------------------------------------------- VBUS and CC
T("VBUS", 0.4, [(5.0, -2.45), (5.5, -2.45), (5.8, -2.75), (5.8, -3.4), (6.3, -3.9), (6.75, -3.9)])
V("VBUS", (5.8, -3.2))
T("VBUS", 0.4, [(5.0, 2.45), (5.2, 2.45), (5.9, 3.15), (5.9, 3.5)])
V("VBUS", (5.9, 3.5))
T("VBUS", 0.4, [(5.9, 3.5), (7.1, 2.3), (7.1, -1.9), (5.8, -3.2)], B)
T("Net-(J1-CC1)", 0.2, [(5.0, -1.25), (5.2, -1.25), (6.0, -2.05), (6.4, -2.05)])
T("Net-(J1-CC2)", 0.2, [(5.0, 1.75), (5.5, 1.75), (5.8, 2.05), (6.4, 2.05)])

# ---------------------------------------------------------------- USB
p32, p33 = pad("U1", 32), pad("U1", 33)
YM, YP = 5.0, 5.35                                   # D- / D+ on the long horizontal run
xm, xp = p32[0] - (YM - p32[1]), p33[0] - (YP - p33[1])
T("/USB_D-", 0.2, [(4.38, 0.25), (9.0, 0.25), (13.75, YM), (xm, YM), p32])
V("/USB_D-", (16.4, YM))                             # tap for J4 pin 13
T("/USB_D-", 0.2, [(16.4, YM), (16.4, 8.78), (17.78, 10.16)], B)
T("/USB_D-", 0.2, [(4.38, -0.75), (5.2, -0.75), (5.6, -1.15), (6.5, -1.15), (7.9, 0.25)])   # B7 joins A7
T("/USB_D+", 0.2, [(4.38, -0.25), (5.2, -0.25), (5.5, -0.55), (5.85, -0.55)])                 # A6 to its via
V("/USB_D+", (5.85, -0.55))
T("/USB_D+", 0.2, [(5.85, -0.55), (5.85, 0.43), (6.2, 0.78)], B)
V("/USB_D+", (6.2, 0.78))
# D+ steps 0.25 mm away from the D- tap via
T("/USB_D+", 0.2, [(4.38, 0.78), (6.6, 0.78), (6.78, 0.6), (8.855, 0.6), (13.605, YP), (15.35, YP),
                   (15.6, 5.6), (17.2, 5.6), (17.45, YP), (xp, YP), p33])
T("/USB_D+", 0.2, [(20.32, YP), (20.32, 10.16)])     # tap for J4 pin 12

# ---------------------------------------------------------------- VBAT
p1 = pad("U1", 1)
T("/VBAT", 0.25, [p1, to_y(p1, NE, -0.95), (32.58, -0.95), (34.03, 0.5)])        # into C10.1
T("/VBAT", 0.25, [(34.3, 0.5), (35.75, -0.95), (40.5, -0.95), (41.0, -1.45), (41.0, -6.9), (41.3, -7.2),
                  (46.96, -7.2), (48.26, -8.5), (48.26, -10.16)])              # out of C10.1 to J3 pin 1
T("/VBAT", 0.25, [(33.9, 1.0), (33.9, 2.6)])         # D3.K

# ---------------------------------------------------------------- SWD, BOOT0
p34, p37, p44 = pad("U1", 34), pad("U1", 37), pad("U1", 44)
s = esc(34, 1.1)
T("/SWDIO", 0.2, [p34, s, (s[0], s[1] + 0.22)])
V("/SWDIO", (s[0], s[1] + 0.22))
T("/SWDIO", 0.2, [(s[0], s[1] + 0.22), (s[0], 7.6), (s[0] + 0.7, 8.3), (47.5, 8.3), (48.3, 7.5),
                  (48.3, 0.13), (46.9, -1.27)], B)
c = esc(37, 0.72)
T("/SWCLK", 0.2, [p37, c])
V("/SWCLK", c)
e = to_y(c, SE, 6.3)
T("/SWCLK", 0.2, [c, e, (41.87, 6.3), (46.9, 1.27)], B)
bv = esc(44, 0.86)
T("/BOOT0", 0.2, [p44, bv])
V("/BOOT0", bv)
e = to_y(bv, NE, 1.6)
T("/BOOT0", 0.2, [bv, e, (38.88, 1.6), (39.6, 0.88)], B)
V("/BOOT0", (39.6, 0.88))
T("/BOOT0", 0.2, [(39.6, 0.88), (42.6, 0.88)])       # R4.1 and SW2.1

# ---------------------------------------------------------------- LED series links
T("Net-(D4-A)", 0.2, [(38.85, 1.0), (38.85, 2.5)])
T("Net-(D2-A)", 0.2, [(39.0, 4.8), (39.0, 6.1)])

# ---------------------------------------------------------------- GND
# U1 exposed pad: 3x3 vias on a 1.4 mm grid turned 45 degrees with the pad
CX = pad("U1", 49)[0]
for i in (-1, 0, 1):
    for j in (-1, 0, 1):
        V("GND", (CX + 0.99 * (i + j), 0.99 * (i - j)))
for pin in (8, 23, 35, 47):                          # GND pins straight in to the exposed pad
    T("GND", 0.25, [pad("U1", pin), esc(pin, -0.5)])
for v in GND_VIAS:
    V("GND", v)
for path in GND_STUBS:
    T("GND", 0.3, path)

# pours on both layers; the pad connection style comes from the .kicad_dru
have = {z.GetZoneName() for z in board.Zones()}
for name, layer in (("GND_F", F), ("GND_B", B)):
    if name in have or "--no-pour" in sys.argv:
        continue
    z = pcbnew.ZONE(board)
    z.SetZoneName(name); z.SetLayer(layer); z.SetNet(net("GND"))
    z.SetLocalClearance(pcbnew.FromMM(0.2)); z.SetMinThickness(pcbnew.FromMM(0.2))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    for x, y in ((-3.5, -12.5), (51.5, -12.5), (51.5, 12.5), (-3.5, 12.5)):
        z.AppendCorner(P((x, y)), -1)
    board.Add(z)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())

out = PCB
if "--no-pour" in sys.argv:            # copy for the autorouter: hand copper only, no pours
    out = sys.argv[sys.argv.index("--no-pour") + 1]
    for z in [z for z in board.Zones() if not z.GetIsRuleArea()]:
        board.Remove(z)                # last thing before saving (see the Remove() note above)
pcbnew.SaveBoard(out, board)
print("tracks", len([t for t in board.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]),
      "vias", len([t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]))
