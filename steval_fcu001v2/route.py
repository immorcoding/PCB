"""Hand routing of steval_fcu001v2, region by region, plus the copper pours.

    D:\\KiCad\\bin\\python.exe steval_fcu001v2\\route.py [--keep] [--no-pour OUT.kicad_pcb]

Coordinates are in the same local frame as place.py (mm, origin at the board
centre, y down). Every polyline is checked before it is written: segments run
at a multiple of 45 degrees and consecutive segments turn by at most 45 degrees.

Without --keep, all tracks and vias are removed first and the hand-routed copper
is rebuilt from scratch. With --keep, only copper on nets this script has touched
is replaced (use after the autorouter has added its nets).

Layers: F.Cu signals and parts, In1.Cu solid GND, In2.Cu +BATT with a VDD island
in the middle, B.Cu signals over a GND pour. Vias are 0.6 / 0.3 through.
"""
import math, os, sys
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "steval_fcu001v2.kicad_pcb")
OX, OY = 100.0, 100.0
F, B, IN1, IN2 = pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu
NE, NW, SE, SW = (1, -1), (-1, -1), (1, 1), (-1, 1)

OPS = []                 # ("T", net, width, pts, layer) / ("V", net, pt): collected, then written


def T(name, width, pts, layer=F):
    """Queue a polyline. Raises if a segment is off the 45-degree grid or a corner is too sharp."""
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
    OPS.append(("T", name, width, pts, layer))


def V(name, pt):
    OPS.append(("V", name, (round(pt[0], 4), round(pt[1], 4))))


def to_y(p, d, y):
    """From p, travel diagonally (d = (+-1, +-1)) until reaching y."""
    k = (y - p[1]) / d[1]
    assert k > 0, (p, d, y)
    return (p[0] + d[0] * k, y)


def to_x(p, d, x):
    k = (x - p[0]) / d[0]
    assert k > 0, (p, d, x)
    return (x, p[1] + d[1] * k)


def load_pads():
    b = pcbnew.LoadBoard(PCB)
    pads = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            pads.setdefault((fp.GetReference(), p.GetNumber()),
                            (round(pcbnew.ToMM(p.GetPosition().x) - OX, 4), round(pcbnew.ToMM(p.GetPosition().y) - OY, 4)))
    return pads


PADS = load_pads()


def pad(ref, num):
    return PADS[(ref, str(num))]


def cap_vias(ref, d1, d2, n1, n2="GND", w=0.3):
    """Via for each pad of a 2-pin part, offset d1 / d2 (mm) from pad 1 / pad 2, joined by a stub."""
    for num, d, n in (("1", d1, n1), ("2", d2, n2)):
        if d is None:
            continue
        p = pad(ref, num)
        v = (p[0] + d[0], p[1] + d[1])
        T(n, w, [p, v])
        V(n, v)


# ====================================================================== MCU core
MX, MY = pad("U2", 49)


def mcu_core():
    # exposed pad: 3x3 GND vias; GND pins tied straight in to it
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            V("GND", (MX + 1.5 * i, MY + 1.5 * j))
    for pin in (8, 23, 35, 44, 47):
        p = pad("U2", pin)
        d = (-1, 0) if pin <= 12 else (0, 1) if pin <= 24 else (1, 0) if pin <= 36 else (0, -1)
        T("GND", 0.25, [p, (p[0] + 0.7 * d[0], p[1] + 0.7 * d[1])])

    # ---- crystal: top layer only, no vias
    p5, p6 = pad("U2", 5), pad("U2", 6)
    y3, y1 = pad("Y1", 3), pad("Y1", 1)
    T("/OSC_OUT", 0.254, [p6, y3])                                   # straight into Y1.3
    T("/OSC_OUT", 0.254, [y3, pad("C9", 1)])
    gap = (pad("Y1", 3)[1] + pad("Y1", 4)[1]) / 2                    # lane between Y1.3 and Y1.4 (GND)
    a = (7.9, p5[1])
    T("/OSC_IN", 0.254, [p5, a, to_y(a, SE, gap), (y1[0] - 1.0, gap), (y1[0], gap + 1.0)])
    c8 = pad("C8", 1)
    T("/OSC_IN", 0.254, [y1, (y1[0], c8[1] - (y1[0] - c8[0])), c8])
    # crystal can and load-cap grounds
    c62, y4 = pad("C6", 2), pad("Y1", 4)
    g = (c62[0] + 0.57, c62[1] + 0.57)
    T("GND", 0.3, [c62, g]); V("GND", g)
    c82 = pad("C8", 2)
    T("GND", 0.3, [c82, (c82[0], y4[1] + 0.5)])                      # C8.2 - Y1.4
    y2, c92 = pad("Y1", 2), pad("C9", 2)
    gv = (c92[0] + 0.85, c92[1])
    T("GND", 0.3, [c92, gv]); V("GND", gv)
    T("GND", 0.3, [y2, (y2[0], gv[1] + (y2[0] - gv[0])), gv])        # Y1.2 up and over to the same via

    # ---- supply pins and their caps
    p9, c71, c72 = pad("U2", 9), pad("C7", 1), pad("C7", 2)          # VDDA
    v = (7.05, p9[1] + 0.05)
    T("VDD", 0.25, [p9, (6.6, p9[1]), (6.65, v[1]), v]); V("VDD", v)
    T("VDD", 0.25, [v, (c71[0] - 0.1, v[1])])
    g = (8.6, 0.0)
    T("GND", 0.3, [c72, (c72[0], -0.13), g]); V("GND", g)

    p1, c61 = pad("U2", 1), pad("C6", 1)                             # VBAT
    T("VDD", 0.25, [p1, (6.6, p1[1]), (6.85, c61[1]), c61])
    cap_vias("C6", (0.0, 0.78), None, "VDD")

    p48, c51 = pad("U2", 48), pad("C5", 1)                           # VDD pin 48
    T("VDD", 0.25, [p48, (p48[0], 4.8), to_y((p48[0], 4.8), SE, 5.3), (c51[0] - 0.23, c51[1] - 0.1)])
    r221 = pad("R22", 1)                                             # NRST pull-up shares the VDD via
    d = r221[1] - c51[1]
    cap_vias("C5", (d, d), (0.0, 0.8), "VDD")
    T("VDD", 0.25, [r221, (c51[0] + d, r221[1])])

    p36, c41 = pad("U2", 36), pad("C4", 1)                           # VDD pin 36
    T("VDD", 0.25, [p36, c41])
    cap_vias("C4", (0.0, 0.8), (0.0, 0.8), "VDD")

    p24, c31 = pad("U2", 24), pad("C3", 1)                           # VDD pin 24
    a = (p24[0], -3.6)
    T("VDD", 0.25, [p24, a, to_y(a, NW, c31[1]), c31])
    cap_vias("C3", (0.0, -0.8), (0.0, -0.8), "VDD")

    p22, c111 = pad("U2", 22), pad("C11", 1)                         # VCAP1
    T("/VCAP1", 0.25, [p22, (p22[0], -4.3), (c111[0], -4.3 - (c111[0] - p22[0])), c111])
    cap_vias("C11", None, (0.0, -0.8), "/VCAP1")

    # ---- NRST: straight to a via (the crystal lanes block the top layer), bottom layer from there
    p7 = pad("U2", 7)
    nv = (6.95, p7[1] - 0.1)
    T("/NRST", 0.2, [p7, (6.6, p7[1]), (6.7, nv[1]), nv]); V("/NRST", nv)


# ====================================================================== USB and charger
def usb_charger():
    # ---- USB pair, top layer only, 0.15 / 0.15 over the In1 ground plane.
    # Heading west out of pins 32/33 D- is the northern trace, so after the turn south it is
    # the western one and reaches U3.3 by passing north of U3.1/U3.2. No crossing anywhere.
    W = 0.15
    p32, p33 = pad("U2", 32), pad("U2", 33)
    XP, XM = -4.15, -4.45            # first southward run, west of C4 and its vias
    LP, LM = -3.32, -3.62            # lane between R30/C15/C14 and R27
    u1, u3 = pad("U3", 1), pad("U3", 3)
    a = (XP + 0.3, p33[1]); b = (XP, p33[1] + 0.3)
    c = (XP, 5.0); d = to_x(c, SE, LP)
    T("/USB_D+", W, [p33, a, b, c, d, (LP, 11.95), to_x((LP, 11.95), SW, u1[0])])
    a = (XM + 0.3, p32[1]); b = (XM, p32[1] + 0.3)
    c = (XM, 5.12); d = to_x(c, SE, LM)
    e = (LM, 11.82); f = to_y(e, SW, 12.3)
    T("/USB_D-", W, [p32, a, b, c, d, e, f, (u3[0] + 0.15, 12.3), (u3[0], 12.45), u3])
    # connector side: the two traces step outward to let the U3.5 via sit between them
    u4, u6, c2, c3 = pad("U3", 4), pad("U3", 6), pad("CN1", 2), pad("CN1", 3)
    T("/USB_CONN_D-", W, [u4, (u4[0] - 0.15, u4[1] + 0.15), (u4[0] - 0.15, 14.5),
                          to_x((u4[0] - 0.15, 14.5), SE, c2[0]), (c2[0], 15.4)])
    T("/USB_CONN_D+", W, [u6, (u6[0] + 0.15, u6[1] + 0.15), (u6[0] + 0.15, 14.3),
                          to_x((u6[0] + 0.15, 14.3), SW, c3[0]), (c3[0], 15.4)])
    u5, c231 = pad("U3", 5), pad("C23", 1)
    v = (u5[0], 14.15); w = (c231[0], 14.55)
    T("/USBLC_VBUS", W, [u5, v]); V("/USBLC_VBUS", v)
    T("/USBLC_VBUS", 0.2, [v, to_y(v, SE, w[1]), w], B); V("/USBLC_VBUS", w)
    T("/USBLC_VBUS", 0.2, [w, c231])

    # ---- VBUS: connector -> TVS -> C12, then up to the charger and its caps
    cn1, d51, c121, u44 = pad("CN1", 1), pad("D5", 1), pad("C12", 1), pad("U4", 4)
    a = (cn1[0], 15.2)
    T("VBUS", 0.3, [(cn1[0], 15.6), a, to_x(a, NW, d51[0])])
    y = d51[1]
    T("VBUS", 0.4, [(d51[0], y), (c121[0], y)])
    # branches leave from pad centres (a T on a bare track trips the corner rule)
    T("VBUS", 0.3, [(d51[0], y), to_x((d51[0], y), NW, -7.85), (-7.85, 12.2), to_y((-7.85, 12.2), NE, 11.55), (-7.2, u44[1])])
    c141, c151 = pad("C14", 1), pad("C15", 1)
    T("VBUS", 0.4, [u44, c141])
    T("VBUS", 0.4, [c141, c151])
    # R29 (charge LED) and R27 (USB monitor divider) take VBUS on the bottom layer
    v1 = (-5.78, u44[1]); V("VBUS", v1)
    r291, r271 = pad("R29", 1), pad("R27", 1)
    v2 = (r291[0] + 0.8, r291[1]); T("VBUS", 0.3, [r291, v2]); V("VBUS", v2)
    T("VBUS", 0.3, [v1, (v1[0], v2[1] + 0.51), v2], B)
    v3 = (r271[0], 11.8); T("VBUS", 0.3, [r271, v3]); V("VBUS", v3)
    T("VBUS", 0.3, [v1, to_y(v1, SE, v3[1]), v3], B)

    # ---- charger
    u45, r301 = pad("U4", 5), pad("R30", 1)
    T("/CHG_PROG", 0.2, [u45, (-5.9, u45[1]), to_y((-5.9, u45[1]), NE, r301[1]), r301])
    u41, l31 = pad("U4", 1), pad("LD3", 1)
    a = (-9.9, u41[1])
    T("/CHG_STAT", 0.2, [u41, a, to_x(a, NW, l31[0]), l31])
    T("/LD3_A", 0.2, [pad("LD3", 2), pad("R29", 2)])
    u43, u42 = pad("U4", 3), pad("U4", 2)
    v = (-10.25, u43[1]); T("+BATT", 0.4, [u43, v]); V("+BATT", v)
    v = (-10.25, u42[1]); T("GND", 0.3, [u42, v]); V("GND", v)
    # TVS and C12 grounds
    d52, c122 = pad("D5", 2), pad("C12", 2)
    v = (-6.5, 12.5)
    T("GND", 0.3, [d52, to_y(d52, NE, v[1]), v]); V("GND", v)
    v = (c122[0] - 0.75, c122[1]); T("GND", 0.3, [c122, v]); V("GND", v)

    # ---- USB monitor divider
    r272, r281 = pad("R27", 2), pad("R28", 1)
    a = (-2.4, r272[1]); b = to_x(a, SE, -2.1); c = (-2.1, r281[1] - 0.3)
    T("/USB_MONITOR", 0.2, [r272, a, b, c, to_y(c, SE, r281[1]), r281])

    # ---- connector shell: the six shell pads joined on copper, RC to ground above
    y = 18.5
    T("/USB_SHIELD", 0.4, [(-7.83, y), (-1.08, y)])
    T("/USB_SHIELD", 0.4, [(-6.94, 16.3), (-6.94, 17.6), to_x((-6.94, 17.6), SW, -7.83)])
    T("/USB_SHIELD", 0.4, [(-1.96, 16.3), (-1.96, 17.5), to_x((-1.96, 17.5), SE, -1.08)])
    r261, c131 = pad("R26", 1), pad("C13", 1)
    T("/USB_SHIELD", 0.3, [r261, (r261[0], 15.3)])
    a = (c131[0], 14.3)
    T("/USB_SHIELD", 0.3, [c131, a, to_x(a, SW, -1.3)])


# ====================================================================== status LEDs
def leds():
    p40, p41 = pad("U2", 40), pad("U2", 41)
    k2, k1 = pad("LD2", 1), pad("LD1", 1)
    a = (p40[0], 5.6)
    T("/LED2", 0.2, [p40, a, to_x(a, SW, k2[0]), k2])
    a = (p41[0], 4.9)
    T("/LED1", 0.2, [p41, a, to_x(a, SE, k1[0]), k1])
    T("/LD2_A", 0.2, [pad("LD2", 2), pad("R21", 2)])
    T("/LD1_A", 0.2, [pad("LD1", 2), pad("R20", 2)])
    r211, r201 = pad("R21", 1), pad("R20", 1)
    v = (r201[0] + 0.85, r201[1])                    # inside the In2 VDD island
    T("VDD", 0.3, [r211, v]); V("VDD", v)


REGIONS = [mcu_core, usb_charger, leds]

# ====================================================================== pours
# In2: +BATT everywhere, VDD island on top of it. (x, y) corners in the local frame.
VDD_ISLAND = [(-11.3, -9.6), (15.6, -9.6), (15.6, 9.0), (9.5, 9.0), (9.5, 15.0), (0.5, 15.0), (0.5, 9.0), (-11.3, 9.0)]
BOARD = [(-20.5, -20.5), (20.5, -20.5), (20.5, 20.5), (-20.5, 20.5)]
POURS = [  # name, layer, net, priority, outline
    ("GND_F", F, "GND", 0, BOARD),
    ("GND_IN1", IN1, "GND", 0, BOARD),
    ("BATT_IN2", IN2, "+BATT", 0, BOARD),
    ("VDD_IN2", IN2, "VDD", 1, VDD_ISLAND),
    ("GND_B", B, "GND", 0, BOARD),
]


def main():
    for region in REGIONS:
        region()
    hand_nets = {op[1] for op in OPS}

    board = pcbnew.LoadBoard(PCB)
    keep = "--keep" in sys.argv
    stale = [t for t in board.GetTracks() if not keep or t.GetNetname() in hand_nets]
    stale += [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetParentFootprint() is None]
    if stale:
        for t in stale:
            board.Remove(t)
        # after a Remove(), pcbnew hands back untyped objects from its collections, so save
        # and start again from a fresh load. The stripped board goes to a side file (same
        # stem, so the project rules are still found next to it), never over the project board.
        import shutil, tempfile
        tmpdir = tempfile.mkdtemp(prefix="route_")
        for ext in (".kicad_pro", ".kicad_dru"):
            shutil.copy(PCB[:-len(".kicad_pcb")] + ext, tmpdir)
        stripped = os.path.join(tmpdir, os.path.basename(PCB))
        pcbnew.SaveBoard(stripped, board)
        board = pcbnew.LoadBoard(stripped)
        shutil.rmtree(tmpdir, ignore_errors=True)

    def P(pt):
        return pcbnew.VECTOR2I(pcbnew.FromMM(OX + pt[0]), pcbnew.FromMM(OY + pt[1]))

    def net(name):
        n = board.FindNet(name)
        if n is None:
            raise SystemExit(f"no net {name}")
        return n

    for op in OPS:
        if op[0] == "T":
            _, name, width, pts, layer = op
            for a, c in zip(pts, pts[1:]):
                s = pcbnew.PCB_TRACK(board)
                s.SetStart(P(a)); s.SetEnd(P(c)); s.SetWidth(pcbnew.FromMM(width))
                s.SetLayer(layer); s.SetNet(net(name)); board.Add(s)
        else:
            _, name, pt = op
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(P(pt)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetWidth(pcbnew.F_Cu, pcbnew.FromMM(0.6)); v.SetDrill(pcbnew.FromMM(0.3))
            v.SetLayerPair(F, B); v.SetNet(net(name)); board.Add(v)

    out = PCB
    if "--no-pour" in sys.argv:            # copy for the autorouter: hand copper only, no pours
        out = sys.argv[sys.argv.index("--no-pour") + 1]
    else:
        for name, layer, netname, prio, outline in POURS:
            z = pcbnew.ZONE(board)
            z.SetZoneName(name); z.SetLayer(layer); z.SetNet(net(netname)); z.SetAssignedPriority(prio)
            z.SetLocalClearance(pcbnew.FromMM(0.2)); z.SetMinThickness(pcbnew.FromMM(0.2))
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
            for pt in outline:
                z.AppendCorner(P(pt), -1)
            board.Add(z)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(out, board)
    print("tracks", len([t for t in board.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]),
          "vias", len([t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]),
          "hand nets", len(hand_nets))


if __name__ == "__main__":
    main()
