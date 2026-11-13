"""Hand routing of steval_fcu001v2, region by region, plus the copper pours.

    D:\\KiCad\\bin\\python.exe steval_fcu001v2\\route.py [--no-pour OUT.kicad_pcb [--skip NET ...]]

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


def ARC(name, width, start, mid, end, layer=F):
    """Queue an arc track through three points (used for the rounded length-tuning humps)."""
    OPS.append(("A", name, width, tuple(round(v, 4) for v in start), tuple(round(v, 4) for v in mid),
                tuple(round(v, 4) for v in end), layer))


def V(name, pt, dia=0.6, drill=0.3):
    OPS.append(("V", name, (round(pt[0], 4), round(pt[1], 4)), dia, drill))


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
    g = (c62[0], c62[1] + 0.8)                       # straight down: clear of the crystal keep-out
    T("GND", 0.3, [c62, g]); V("GND", g)
    c82 = pad("C8", 2)
    T("GND", 0.3, [c82, (c82[0], y4[1] + 0.5)])                      # C8.2 - Y1.4
    y2, c92 = pad("Y1", 2), pad("C9", 2)
    gv = (c92[0] + 0.85, c92[1])
    T("GND", 0.3, [c92, gv]); V("GND", gv)
    T("GND", 0.3, [y2, (y2[0], gv[1] + (y2[0] - gv[0])), gv])        # Y1.2 up and over to the same via

    # ---- supply pins and their caps
    p9, c71, c72 = pad("U2", 9), pad("C7", 1), pad("C7", 2)          # VDDA
    v = (7.05, p9[1] + 0.1)                                         # level with the pin it is 0.115 mm from TIM2_CH1
    T("VDD", 0.25, [p9, (6.55, p9[1]), (6.65, v[1]), v]); V("VDD", v)
    T("VDD", 0.25, [v, (c71[0] - 0.1, v[1])])
    g = (8.6, 0.0)
    T("GND", 0.3, [c72, (c72[0], -0.13), g]); V("GND", g)

    p1, c61 = pad("U2", 1), pad("C6", 1)                             # VBAT
    T("VDD", 0.25, [p1, (c61[0] - (c61[1] - p1[1]), p1[1]), c61])
    cap_vias("C6", (-0.55, 0.55), None, "VDD")       # down-left: x = 7.45 is the NRST lane on B.Cu

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
    T("/VCAP1", 0.25, [p22, (p22[0], -4.3), (c111[0], -4.3 - abs(c111[0] - p22[0])), c111])
    cap_vias("C11", None, (0.0, -0.8), "/VCAP1")

    # ---- NRST: straight to a via (the crystal lanes block the top layer), bottom layer from there
    p7 = pad("U2", 7)
    nv = (6.95, p7[1] - 0.1)
    T("/NRST", 0.2, [p7, (6.6, p7[1]), (6.7, nv[1]), nv]); V("/NRST", nv)


# ====================================================================== USB and charger
def usb_charger():
    # ---- USB pair, top layer only, 0.15 / 0.15 over the In1 ground plane.
    # Heading west out of pins 32/33 D- is the northern trace, so after the turn south it is
    # the western one. Below the charger caps the pair steps west and splits round U3.2 (GND),
    # D+ dropping into U3.1 and D- into U3.3; the ground via for U3.2 sits between them.
    W = 0.15
    p32, p33 = pad("U2", 32), pad("U2", 33)
    XP, XM = -4.15, -4.45            # first southward run, west of C4 and its vias
    LP, LM = -3.32, -3.62            # lane between R30/C15/C14 and R27
    u1, u3 = pad("U3", 1), pad("U3", 3)
    a = (XP + 0.3, p33[1]); b = (XP, p33[1] + 0.3)
    c = (XP, 5.0); d = to_x(c, SE, LP)
    # D+ is the inside trace on both turns and ends about 1.1 mm short of D-. Two rounded humps
    # (arcs of radius HR, 2*HR out and back, 4*HR long) in the free area left of the MCU make
    # that up: each adds (2*pi - 4) * HR.
    HR, HUMPS = 0.25, (6.0, 7.5)
    k = HR * math.sqrt(0.5)
    T("/USB_D+", W, [p33, a, b, c, d, (LP, HUMPS[0])])
    for n, y0 in enumerate(HUMPS):
        cx = LP + HR
        ARC("/USB_D+", W, (LP, y0), (cx - k, y0 + k), (cx, y0 + HR))                       # south -> east
        ARC("/USB_D+", W, (cx, y0 + HR), (cx + HR, y0 + 2 * HR), (cx, y0 + 3 * HR))        # round the far side
        ARC("/USB_D+", W, (cx, y0 + 3 * HR), (cx - k, y0 + 4 * HR - k), (LP, y0 + 4 * HR)) # west -> south
        nxt = HUMPS[n + 1] if n + 1 < len(HUMPS) else 11.6
        tail = [to_x((LP, 11.6), SW, u1[0]), u1] if n + 1 == len(HUMPS) else []
        T("/USB_D+", W, [(LP, y0 + 4 * HR), (LP, nxt)] + tail)
    a = (XM + 0.3, p32[1]); b = (XM, p32[1] + 0.3)
    c = (XM, 5.12); d = to_x(c, SE, LM)
    e = (LM, 10.6)
    T("/USB_D-", W, [p32, a, b, c, d, e, to_x(e, SW, u3[0]), u3])
    u2 = pad("U3", 2); v = (u2[0], 12.42)
    T("GND", 0.2, [u2, v]); V("GND", v, *SMALL)
    # connector side: straight down from U3, one step each to close up from the 1.0 mm pad
    # spacing to the connector's 0.65 mm. A small via for U3.5 fits between them.
    u4, u6, c2, c3 = pad("U3", 4), pad("U3", 6), pad("CN1", 2), pad("CN1", 3)
    T("/USB_CONN_D-", W, [u4, (u4[0], 14.65), to_x((u4[0], 14.65), SE, c2[0]), (c2[0], 15.4)])
    T("/USB_CONN_D+", W, [u6, (u6[0], 14.45), to_x((u6[0], 14.45), SW, c3[0]), (c3[0], 15.4)])
    u5, c231 = pad("U3", 5), pad("C23", 1)
    v = (u5[0], 14.1); w = (c231[0], 14.55)
    T("/USBLC_VBUS", W, [u5, v]); V("/USBLC_VBUS", v, *SMALL)
    T("/USBLC_VBUS", 0.2, [v, to_y(v, SE, w[1]), w], B); V("/USBLC_VBUS", w)
    T("/USBLC_VBUS", 0.2, [w, c231])

    # ---- VBUS: connector -> TVS -> C12, then up to the charger and its caps
    cn1, d51, c121, u44 = pad("CN1", 1), pad("D5", 1), pad("C12", 1), pad("U4", 4)
    a = (cn1[0], 15.2)
    T("VBUS", 0.3, [(cn1[0], 15.6), a, to_x(a, NW, d51[0])])
    y = d51[1]
    T("VBUS", 0.4, [(d51[0], y), (c121[0], y)])
    # branches leave from pad centres (a T on a bare track trips the corner rule)
    T("VBUS", 0.3, [(d51[0], y), to_x((d51[0], y), NW, -7.85), (-7.85, 12.2), to_y((-7.85, 12.2), NE, 11.35)])
    c141, c151 = pad("C14", 1), pad("C15", 1)
    v1 = (-5.78, u44[1]); V("VBUS", v1)
    T("VBUS", 0.4, [u44, v1])
    T("VBUS", 0.4, [v1, to_x(v1, NE, c141[0]), c141])
    T("VBUS", 0.4, [c141, c151])
    # R29 (charge LED) and R27 (USB monitor divider) take VBUS on the bottom layer
    r291, r271 = pad("R29", 1), pad("R27", 1)
    v2 = (r291[0] + 0.8, r291[1]); T("VBUS", 0.3, [r291, v2]); V("VBUS", v2)
    T("VBUS", 0.3, [v1, (v1[0], v2[1] + 0.51), v2], B)
    v3 = (r271[0], 11.8); T("VBUS", 0.3, [r271, v3]); V("VBUS", v3)
    T("VBUS", 0.3, [v1, to_y(v1, SE, v3[1]), v3], B)

    # ---- charger
    u45, r301 = pad("U4", 5), pad("R30", 1)
    T("/CHG_PROG", 0.2, [u45, (r301[0] - (u45[1] - r301[1]), u45[1]), r301])
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
    T("/USB_MONITOR", 0.2, [r272, (r281[0], r272[1])])

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
    # the cathodes are reached from the MCU fan-out vias on the bottom layer
    for led, r, name in (("LD2", "R21", "/LED2"), ("LD1", "R20", "/LED1")):
        k = pad(led, 1); v = (4.15, k[1])
        T(name, 0.2, [k, v]); V(name, v, *SMALL)
        T(name.replace("LED", "LD") + "_A", 0.2, [pad(led, 2), pad(r, 2)])
    r211, r201 = pad("R21", 1), pad("R20", 1)
    T("VDD", 0.3, [r201, r211])
    v = (r211[0] - 0.8, r211[1])                     # inside the In2 VDD island
    T("VDD", 0.3, [r211, v]); V("VDD", v)


# ====================================================================== MCU pin fan-out, BLE bus
SMALL = (0.45, 0.2)      # via size used only where a 0.6 mm via cannot sit between 0.5 mm-pitch pins


def mcu_fanout():
    W = 0.15
    names = {37: "/SWCLK", 39: "/I2C2_SDA", 40: "/LED2", 41: "/LED1", 42: "/MOTOR1", 43: "/MOTOR2",
             45: "/MOTOR3", 46: "/MOTOR4", 14: "/BLE_IRQ", 13: "/TIM2_CH4", 19: "/VBAT_SENSE", 21: "/I2C2_SCL"}
    # bottom side: three staggered rows, so a via never has a neighbour's via beside it
    rows = {37: 4.95, 39: 5.65, 40: 6.35, 41: 4.95, 42: 5.65, 43: 6.35, 45: 4.95, 46: 5.65}
    # top side: the four pins that are not BLE lines
    rows.update({14: -3.95, 13: -4.65, 19: -3.95, 21: -4.65})
    for pin, y in rows.items():
        p = pad("U2", pin); v = (p[0], y)
        T(names[pin], 0.2 if pin == 19 else W, [p, v])                               # VBAT* is in the PWR class
        if pin not in (37, 45):          # the autorouter took these two on from the stub on the top layer
            V(names[pin], v, *SMALL)
    # left side: USART and SWDIO drop to the bottom layer before the USB pair turns south
    for pin, name, x in ((30, "/USART1_TX", -1.9), (31, "/USART1_RX", -2.6), (34, "/SWDIO", -1.9)):
        p = pad("U2", pin); v = (x, p[1])
        T(name, W, [p, v]); V(name, v, *SMALL)
    # right side: pins 2 and 3, either side of the NRST lane (see ble_misc)
    p3 = pad("U2", 3); v = (6.95, p3[1])
    T("/USB_MONITOR", W, [p3, v]); V("/USB_MONITOR", v, *SMALL)
    p2 = pad("U2", 2); v = (8.15, p2[1] - 0.15)
    T("/LPS22HH_CS", W, [p2, (7.3, p2[1]), (7.45, v[1]), v]); V("/LPS22HH_CS", v, *SMALL)

    # BLE SPI: top layer only, under the module (outside its antenna keep-out), no vias.
    # Each line runs north from its pin, steps over to its own lane and turns east into its pad;
    # the easternmost pin takes the southernmost pad, so nothing crosses.
    bus = [(15, "/S1_CLK", 5.9, 7), (16, "/S1_MISO", 5.5, 8), (17, "/S1_MOSI", 5.1, 9),
           (18, "/BLE_CS", 4.7, 10), (20, "/BLE_RSTN", 4.3, 11)]
    for pin, name, lane, upad in bus:
        p, u = pad("U2", pin), pad("U1", upad)
        a = (p[0], -5.3)
        b = to_x(a, NE, lane)
        k = (u[0] - 0.4) - lane - 0.8                 # diagonal that ends 0.8 mm short of the pad end point
        T(name, W, [p, a, b, (lane, u[1] + k), (lane + k, u[1]), (u[0] - 0.4, u[1])])


# ====================================================================== battery in, LDO, divider
def power_in():
    # BT1 is through-hole: its pins land on the In2 +BATT pour and the In1 ground directly.
    c181, c161, u61, u63, r101 = pad("C18", 1), pad("C16", 1), pad("U6", 1), pad("U6", 3), pad("R10", 1)
    T("+BATT", 0.4, [c181, c161])
    T("+BATT", 0.3, [c161, to_y(c161, SE, u63[1]), u63])          # EN and the input caps
    v = (u61[0], 1.25)                                            # IN: its own via to the In2 pour
    T("+BATT", 0.4, [u61, v]); V("+BATT", v)
    v = (c181[0], 4.3)
    T("+BATT", 0.4, [c181, v]); V("+BATT", v)
    T("+BATT", 0.3, [v, (v[0], r101[1] - (r101[0] - v[0])), r101])
    for ref in ("C16", "C18"):
        p = pad(ref, 2); v = (p[0], 1.7)
        T("GND", 0.3, [p, v]); V("GND", v)
    u62 = pad("U6", 2); v = (-11.8, u62[1])
    T("GND", 0.3, [u62, v]); V("GND", v)
    # 3.3 V out
    u65, c171, c172 = pad("U6", 5), pad("C17", 1), pad("C17", 2)
    T("VDD", 0.4, [u65, c171])
    cap_vias("C17", (0.0, 0.8), (0.0, 0.8), "VDD")
    # USART header pin 1 sits over the +BATT part of In2: feed it from the LDO on the top layer
    p71 = pad("P7", 1)
    a = (-13.0, p71[1])
    T("VDD", 0.4, [p71, a, to_x(a, SE, u65[0]), u65])
    # battery divider
    r102, r111, c21 = pad("R10", 2), pad("R11", 1), pad("C2", 1)
    T("/VBAT_SENSE", 0.2, [r102, r111])
    a = to_y(r111, SE, 6.25); b = (c21[0] - (6.25 - c21[1]), 6.25)
    T("/VBAT_SENSE", 0.2, [r111, a, b, c21])


# ====================================================================== motor switches
def motor(n, sx, sy, q, d, rg, rp, rb, rn, pp, pn, gnd2):
    """One corner. sy = -1 for the top edge. gnd2 = offset of the second source via."""
    out, dr = f"/M{n}_OUT", f"/MOTOR{n}_N"
    drain, b1, b2, n2 = pad(q, 5), pad(rb, 1), pad(rb, 2), pad(rn, 2)
    # drain -> 0R bridge -> pad, 1 mm / 0.8 mm
    k = abs(b1[0] - drain[0])
    T(dr, 1.0, [(drain[0], drain[1] + sy * 0.4), (drain[0], b1[1] - sy * k), b1])
    pm = pad(pn, 1)
    k = abs(pm[0] - b2[0])
    T(out, 0.8, [b2, (b2[0], b2[1] + sy * 0.65), (pm[0], b2[1] + sy * (0.65 + k)), (pm[0], pm[1] - sy * 1.0)])
    k = abs(b2[0] - n2[0])
    T(out, 0.3, [n2, (b2[0], n2[1] + sy * k), b2])
    # the top and bottom solder pads share three vias each
    for ref, name in ((pp, "+BATT"), (pn, out)):
        p = pad(ref, 1)
        for dy in (-1.0, 0.0, 1.0):
            V(name, (p[0], p[1] + dy))
    # flyback diode: anode into the drain pad, cathode to the In2 +BATT pour
    an, ka = pad(d, 2), pad(d, 1)
    a = (an[0] - sx * 0.75, an[1] + sy * 0.75)
    T(dr, 0.5, [an, a, (drain[0] + sx * 1.0, a[1])])
    v = (ka[0], ka[1] - sy * 0.8)
    T("+BATT", 0.5, [ka, v]); V("+BATT", v)
    # sources: joined, two vias to ground on the side away from the gate
    g = pad(q, 4)
    src = sorted((pad(q, i) for i in (1, 2, 3)), key=lambda p: abs(p[0] - g[0]))
    far = src[-1]
    dirx = 1 if far[0] > g[0] else -1
    v1 = (far[0] + dirx * 0.75, far[1])
    T("GND", 0.5, [src[0], v1]); V("GND", v1)
    v2 = (v1[0] + gnd2[0], v1[1] + gnd2[1]); V("GND", v2)
    # gate
    g2, p1 = pad(rg, 2), pad(rp, 1)
    T(f"/M{n}_GATE", 0.2, [g, g2])
    T(f"/M{n}_GATE", 0.2, [p1, g2])


def motors():
    motor(1, -1, -1, "Q1", "D1", "R2", "R4", "R12", "R14", "MP1", "MP2", (0.0, 0.75))
    motor(2, +1, -1, "Q2", "D2", "R3", "R5", "R16", "R18", "MP3", "MP4", (0.0, 0.75))
    motor(3, -1, +1, "Q3", "D3", "R6", "R7", "R13", "R15", "MP5", "MP6", (0.0, 0.75))
    motor(4, +1, +1, "Q4", "D4", "R8", "R9", "R17", "R19", "MP7", "MP8", (0.0, -0.75))


# ====================================================================== sensors (SPI2)
def sensors():
    # ---- IMU supply. Nothing runs under the package on the top layer.
    c211, c221 = pad("C21", 1), pad("C22", 1)
    u85, u83, u82, u88 = pad("U8", 5), pad("U8", 3), pad("U8", 2), pad("U8", 8)
    T("VDD", 0.25, [c211, (u85[0], c211[1])])       # straight: C21.1 and U8.5 overlap in y
    v = (c211[0], -1.85)
    T("VDD", 0.25, [c211, v]); V("VDD", v)
    T("VDD", 0.2, [u83, u82])                       # pins 2 / 3 (SDx, SCx tied high): own small via,
    v = (u83[0] + 0.25, -2.35)                      # placed between the two SPI2 tracks on B.Cu
    T("VDD", 0.2, [u83, (v[0], u83[1] - 0.25), v]); V("VDD", v, *SMALL)
    a = (-9.0, c221[1])
    T("VDD", 0.25, [c221, a, to_y(a, SE, 0.9), (u88[0], 0.9)])
    v = (c221[0], 0.9)
    T("VDD", 0.25, [c221, v]); V("VDD", v)
    u86, u87 = pad("U8", 6), pad("U8", 7)
    T("GND", 0.25, [u87, u86])
    v = (pad("C21", 2)[0], u86[1])                  # lands between the two caps' ground pads
    T("GND", 0.25, [u86, v]); V("GND", v)

    # ---- barometer supply
    c191, c201, u71, u710 = pad("C19", 1), pad("C20", 1), pad("U7", 1), pad("U7", 10)
    T("VDD", 0.25, [c191, (u71[0], c191[1])])
    v = (u710[0], -6.7)                             # pin 10: straight up to its own via
    T("VDD", 0.25, [u710, v]); V("VDD", v)
    T("VDD", 0.25, [c191, c201]); V("VDD", ((c191[0] + c201[0]) / 2, (c191[1] + c201[1]) / 2))
    u78, u79, u73 = pad("U7", 8), pad("U7", 9), pad("U7", 3)
    T("GND", 0.2, [u79, u78])
    v = (u78[0], -6.6); T("GND", 0.25, [u78, v]); V("GND", v)
    v = (u73[0], -3.45); T("GND", 0.25, [u73, v]); V("GND", v)

    # ---- SPI2. Top layer: SDO chains MCU -> U8.1 -> U7.5; SDI and CS go straight to the IMU.
    # CLK crosses SDO/SDI, and SDI needs a second way round to the barometer: both on the bottom.
    p26, p27, p28, p29 = (pad("U2", i) for i in (26, 27, 28, 29))
    u81, u75 = pad("U8", 1), pad("U7", 5)
    a = (-3.4, p27[1])
    T("/S2_SDO", 0.2, [p27, a, to_y(a, NW, u81[1]), u81])
    T("/S2_SDO", 0.2, [u81, (u81[0], -3.5), to_x((u81[0], -3.5), NW, u75[0]), u75])
    u814 = pad("U8", 14)
    D = (-5.2, u814[1])                             # small via, level with the pad
    a = (D[0] + (p28[1] - D[1]), p28[1])
    T("/S2_SDI", 0.2, [p28, a, D]); V("/S2_SDI", D, *SMALL)
    T("/S2_SDI", 0.2, [D, (u814[0], D[1])])
    u74, E = pad("U7", 4), (-6.95, -3.0)
    T("/S2_SDI", 0.2, [D, (D[0], E[1] + (D[0] - E[0])), E], B); V("/S2_SDI", E)
    T("/S2_SDI", 0.2, [E, (E[0], -3.6), to_x((E[0], -3.6), NW, u74[0]), u74])
    u812 = pad("U8", 12)
    a = (-3.2, p29[1]); b = to_y(a, SW, 0.45); c = (-5.45, 0.45)
    T("/LSM6DSR_CS", 0.2, [p29, a, b, c, to_y(c, NW, u812[1]), u812])
    A, Bv, C = (-2.2, -2.1), (-4.4, -0.1), (-8.35, -2.9)
    a = (-1.85, p26[1])
    T("/S2_CLK", 0.2, [p26, a, to_x(a, NW, A[0])]); V("/S2_CLK", A)
    T("/S2_CLK", 0.2, [A, (-2.4, A[1]), Bv], B); V("/S2_CLK", Bv)
    u813, u72 = pad("U8", 13), pad("U7", 2)
    a = (-4.9, Bv[1])
    T("/S2_CLK", 0.2, [Bv, a, to_y(a, NW, u813[1]), u813])
    a = (C[0] + (Bv[1] - C[1]), Bv[1])
    T("/S2_CLK", 0.2, [Bv, a, C], B); V("/S2_CLK", C)
    T("/S2_CLK", 0.2, [u72, (C[0], u72[1] + (u72[0] - C[0])), C])


# ====================================================================== BLE module, reset, header supplies
def ble_misc():
    c11, u15 = pad("C1", 1), pad("U1", 5)
    T("VDD", 0.3, [c11, (u15[0] - 0.6, c11[1])])
    cap_vias("C1", (0.0, 0.8), (0.0, 0.8), "VDD")
    T("/BLE_IRQ", 0.2, [pad("R1", 1), (pad("U1", 4)[0] - 0.6, pad("R1", 1)[1])])
    u16 = pad("U1", 6); v = (u16[0], -6.9)
    T("GND", 0.4, [u16, v]); V("GND", v)

    # NRST: bottom layer from the via at pin 7 to the RC, then to the switch
    # It runs down x = 7.45, between the USB_MONITOR via (west of it) and the LPS22HH_CS via
    # (east of it), to a small via that just fits between the R22.2 and C10.1 pads.
    N1 = (6.95, pad("U2", 7)[1] - 0.1)
    r222, c101 = pad("R22", 2), pad("C10", 1)
    N2 = (7.45, 5.1)
    T("/NRST", 0.2, [(r222[0], 5.1), (c101[0], 5.1)]); V("/NRST", N2, *SMALL)
    T("/NRST", 0.2, [N1, to_x(N1, SE, N2[0]), N2], B)
    a = (8.6, 5.1)
    T("/NRST", 0.2, [(c101[0], 5.1), a, to_x(a, SE, 9.35), (9.35, 7.3)])          # C10.1 round to the switch
    T("/NRST", 0.2, [(5.25, 8.0), (5.75, 8.5), (8.85, 8.5), (9.35, 8.0)])   # the switch's two NRST pads

    # header / pull-up supplies inside the VDD island
    p81 = pad("P8", 1); v = (1.1, p81[1])
    T("VDD", 0.3, [p81, v]); V("VDD", v)
    cap_vias("R23", (0.0, 0.8), None, "VDD")


# ====================================================================== fixes to autorouted nets
# The autorouter branches off the middle of a track, which the corner rule reports as a
# 90-degree T. The NRST branch is dropped (AUTO_DROP) and redone from a pad. One more is
# left as it is: MOTOR4 on B.Cu at (9.2, 11.7), the tap to the DNP link R19 - both ways
# of moving it to a via run into the NRST track next to it.
AUTO_DROP = {
    ("/NRST", (9.35, 5.85), (9.4, 5.8)), ("/NRST", (9.4, 5.8), (10.2, 5.8)),
    ("/MOTOR3", (-12.5, 8.7), (-12.5, 10.0)),
    # MOTOR1: right angle with a 0.035 mm chamfer
    ("/MOTOR1", (-9.85, 1.475), (-7.5, 1.475)), ("/MOTOR1", (-7.5, 1.475), (-7.475, 1.5)),
    ("/MOTOR1", (-7.475, 1.5), (-7.475, 2.975)),
    # MOTOR3 from U2.45 to the via at (3.9, 10.475): hook round the MOTOR2 via, detour on B.Cu,
    # tracks ending beside their vias instead of on them
    ("/MOTOR3", (3.65, 6.05), (3.65, 4.95)), ("/MOTOR3", (2.675, 7.025), (3.65, 6.05)),
    ("/MOTOR3", (2.625, 7.025), (2.675, 7.025)), ("/MOTOR3", (1.975, 6.375), (2.625, 7.025)),
    ("/MOTOR3", (1.975, 6.375)),
    ("/MOTOR3", (1.975, 6.375), (3.1, 7.5)), ("/MOTOR3", (3.1, 7.5), (4.4, 7.5)), ("/MOTOR3", (4.4, 7.5), (5.95, 9.05)),
    ("/MOTOR3", (6.15, 9.05)),
    ("/MOTOR3", (5.975, 9.875), (5.975, 9.225)), ("/MOTOR3", (5.775, 10.075), (5.975, 9.875)),
    ("/MOTOR3", (4.25, 10.075), (5.775, 10.075)), ("/MOTOR3", (4.0, 10.325), (4.25, 10.075)),
}


def auto_fixes():
    # NRST to TP3: leaves from the switch pad and joins the autorouted run at (10.2, 5.8)
    T("/NRST", 0.2, [(9.35, 7.7), (10.2, 6.85), (10.2, 5.8)])
    # MOTOR3 turned 90 degrees at its via: leave the via at 45 degrees instead
    T("/MOTOR3", 0.2, [(-12.5, 8.7), (-12.8, 9.0), (-12.8, 9.7), (-12.5, 10.0)], B)
    # MOTOR1: the same corner with a 0.53 mm chamfer (as large as C17.2 allows)
    T("/MOTOR1", 0.2, [(-9.85, 1.475), (-7.85, 1.475), (-7.475, 1.85), (-7.475, 2.975)])
    # MOTOR3: straight down from the pin to its own via (as low as LD2.1 allows, clear of the
    # MOTOR2 track on B.Cu), one diagonal on B.Cu between the MOTOR2 track and the LED2 via,
    # then back to F.Cu round the switch pad
    a, c = (3.65, 7.05), (6.15, 9.25)
    T("/MOTOR3", 0.2, [(3.65, 4.95), a]); V("/MOTOR3", a)
    T("/MOTOR3", 0.2, [a, (3.95, 7.05), c], B); V("/MOTOR3", c)
    T("/MOTOR3", 0.2, [c, (6.15, 9.725), (5.8, 10.075), (4.3, 10.075), (3.9, 10.475)])   # midway between S1.2 and USB_MONITOR


# ====================================================================== ground for stranded pads
def gnd_stitch():
    # F.Cu pour pieces that hung on surface-mount pads only (scripts/pour_islands.py),
    # spots from scripts/via_spots.py: P8 / USB area, top right, R24, the switch.
    for v in ((1.0, 16.3), (15.8, -7.1), (9.21, 12.5), (8.55, 9.3), (8.5, 6.7)):
        V("GND", v)
    # The switch's left ground pad is boxed in by NRST, MOTOR3 and the LED vias (a track to the
    # right pad crosses MOTOR3, and MOTOR3 does not route with that track in place): one small
    # via in the pad. It is a 0.9 x 1.0 mm hand-solder pad.
    V("GND", (5.0, 9.6), *SMALL)                     # clear of I2C2_SDA passing under the pad on B.Cu
    # stitching between the F.Cu / B.Cu pours and the In1 plane: scripts/via_spots.py grid 5,
    # minus one spot inside the BLE antenna keep-out and one on the edge of the VDD island
    for v in STITCH:
        V("GND", v)


STITCH = [(-14.8, -18.55), (13.95, -18.55), (-18.55, -14.8), (-14.8, -14.8), (13.95, -14.8), (17.7, -14.8),
          (-18.55, -11.05), (16.45, -11.05), (-16.05, -8.55), (-4.8, -8.55), (-1.05, -8.55), (12.7, -8.55),
          (18.95, -8.55), (2.7, -7.3), (-18.55, -6.05), (-13.55, -6.05), (16.45, -6.05), (-4.8, -4.8),
          (-9.8, -3.55), (-18.55, -2.3), (-14.8, -2.3), (-2.3, 5.2), (16.45, 6.45), (-16.05, 7.7), (18.95, 8.95),
          (-7.3, 10.2), (-18.55, 11.45), (16.45, 11.45), (-14.8, 12.7), (-3.55, 12.7), (13.95, 13.95),
          (18.95, 13.95), (-8.55, 15.2), (0.2, 15.2), (8.95, 15.2), (-14.8, 16.45), (13.95, 17.7), (8.95, 18.95)]


REGIONS = [mcu_core, mcu_fanout, usb_charger, leds, power_in, motors, sensors, ble_misc, auto_fixes, gnd_stitch]
AUTO_SKIP = set()        # nets whose autorouted copper is not replayed

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

    lock = "--no-pour" in sys.argv       # the autorouter leaves KiCad-locked copper alone
    for op in OPS:
        if op[0] == "T":
            _, name, width, pts, layer = op
            for a, c in zip(pts, pts[1:]):
                s = pcbnew.PCB_TRACK(board)
                s.SetStart(P(a)); s.SetEnd(P(c)); s.SetWidth(pcbnew.FromMM(width))
                s.SetLayer(layer); s.SetNet(net(name)); s.SetLocked(lock); board.Add(s)
        elif op[0] == "A":
            _, name, width, p0, p1, p2, layer = op
            s = pcbnew.PCB_ARC(board)
            s.SetStart(P(p0)); s.SetMid(P(p1)); s.SetEnd(P(p2)); s.SetWidth(pcbnew.FromMM(width))
            s.SetLayer(layer); s.SetNet(net(name)); s.SetLocked(lock); board.Add(s)
        else:
            _, name, pt, dia, drill = op
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(P(pt)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetWidth(pcbnew.F_Cu, pcbnew.FromMM(dia)); v.SetDrill(pcbnew.FromMM(drill))
            v.SetLayerPair(F, B); v.SetNet(net(name)); v.SetLocked(lock); board.Add(v)

    # the autorouter's nets, replayed from auto_tracks.json (see scripts/auto_tracks.py);
    # nets listed in AUTO_SKIP have since been re-done by hand above
    auto = os.path.join(HERE, "auto_tracks.json")
    n_auto = 0
    skip = set(AUTO_SKIP)
    if "--skip" in sys.argv:               # nets about to be re-run through the autorouter
        skip |= set(sys.argv[sys.argv.index("--skip") + 1:])
    if os.path.isfile(auto):
        import json
        for o in json.load(open(auto, encoding="utf-8")):
            if o["net"] in skip:
                continue
            ident = (o["net"], tuple(o["at"])) if o["k"] == "via" else (o["net"], tuple(o["a"]), tuple(o["b"]))
            if ident in AUTO_DROP or (o["k"] == "seg" and (ident[0], ident[2], ident[1]) in AUTO_DROP):
                continue
            n_auto += 1
            if o["k"] == "seg":
                s = pcbnew.PCB_TRACK(board)
                s.SetStart(P(o["a"])); s.SetEnd(P(o["b"])); s.SetWidth(pcbnew.FromMM(o["w"]))
                s.SetLayer(board.GetLayerID(o["layer"])); s.SetNet(net(o["net"])); s.SetLocked(lock); board.Add(s)
            else:
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(P(o["at"])); v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetWidth(pcbnew.F_Cu, pcbnew.FromMM(o["d"])); v.SetDrill(pcbnew.FromMM(o["drill"]))
                v.SetLayerPair(F, B); v.SetNet(net(o["net"])); v.SetLocked(lock); board.Add(v)
    print("autorouter items replayed:", n_auto)

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
