"""Placement of steval_fcu001v2: positions, board outline, zone annotations.

    D:\\KiCad\\bin\\python.exe steval_fcu001v2\\place.py

Local frame (mm): origin at the board centre, x to the right, y down.
Rotations are KiCad footprint orientations in degrees (counter-clockwise).
A fourth entry "B" puts the part on the bottom side.
Re-running moves every listed part back to its table position and redraws
Edge.Cuts and the zone notes on Cmts.User.

Board: 40 x 40 mm, M3 holes in the corners. Parts are on the top side; only the
second set of motor solder pads is on the bottom.
  top edge     motor 1 pads, BLE module (antenna end at the edge), motor 2 pads
  left edge    battery header, USART header
  bottom edge  motor 3 pads, micro-USB, SWD header, motor 4 pads
  right edge   FC_Signal header, I2C header beside it
  corners      mounting hole, motor switch next to its pads
  centre       MCU (rotated 180: BLE SPI faces up, sensor SPI and USB face left,
               crystal and TIM2 face right, motor gates and LEDs face down)

The top and bottom edge rows are full: between the hole courtyards there is
27.5 mm, the bottom row (pads, USB, SWD, pads) needs 26.7 mm.
"""
import os, sys
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "steval_fcu001v2.kicad_pcb")
OX, OY = 100.0, 100.0                 # local origin on the page

XE, YE = 20.0, 20.0                   # half board size
HX, HY = 17.25, 17.25                 # mounting holes (hole edge 1.15 mm from the board edge)
MX, MY = 2.4, 0.5                     # MCU centre
# BLE module centre x. The footprint carries a 12 x 12 mm all-layer antenna keep-out
# reaching 9.95 mm to the left of the centre; this keeps it clear of the motor 1 pads.
BX = 0.65
QX, PX = 12.6, 10.4                   # |x| of the FETs / + pads, and of the - pads

PLACE = {
    "H1": (-HX, -HY, 0), "H2": (HX, -HY, 0), "H3": (-HX, HY, 0), "H4": (HX, HY, 0),

    # ---- MCU and its supply caps
    "U2": (MX, MY, 180),
    "C11": (MX - 2.1, MY - 5.3, 180), # VCAP1, pin 22
    "C3": (MX - 4.3, MY - 4.9, 180),  # VDD pin 24
    "C4": (MX - 5.4, MY + 2.75, 180), # VDD pin 36
    "C5": (MX + 3.0, MY + 5.2, 180),  # VDD pin 48; clear of the lane under pins 45/46
    "C6": (MX + 5.3, MY + 3.0, 0),    # VBAT pin 1
    "C7": (MX + 5.85, MY - 1.35, 0),  # VDDA pin 9; its VDD via sits between the pin and the cap
    # ---- HSE: OSC_IN (pin 5) runs between the two left pads to Y1.1, OSC_OUT (pin 6) to Y1.3
    # Y1.3 is level with pin 6 so OSC_OUT runs straight and pins 7..12 stay free to leave
    "Y1": (MX + 8.2, MY + 1.35, 90),
    "C9": (MX + 7.35, MY - 1.8, 90),  # OSC_OUT load cap, above Y1.3
    "C8": (MX + 7.9, MY + 4.05, 180), # OSC_IN load cap, below Y1.1
    # ---- reset
    "S1": (7.3, 8.5, 0),
    "R22": (6.9, 5.6, 90),
    "C10": (8.0, 5.6, 90),

    # ---- BLE module, antenna end at the top edge
    "U1": (BX, -YE + 8.9, 0),
    "C1": (BX - 8.9, -9.2, 180),
    "R1": (BX - 8.9, -10.5, 180),

    # ---- sensors, left of the MCU (SPI2 pins 26..29)
    "U8": (-7.1, MY - 1.0, 270),      # IMU
    "C21": (-9.9, MY - 1.6, 180),
    "C22": (-9.9, MY - 0.4, 180),
    "U7": (-7.1, -5.0, 0),
    "C19": (-9.6, -5.6, 180),
    "C20": (-9.6, -4.4, 180),

    # ---- battery in, USART, LDO, battery divider (left edge)
    "BT1": (-15.5, -4.53, 180),       # right-angle header, pins overhang the left edge
    "P7": (-18.1, -0.79, 0),          # USART, pin 1 at the top
    "U6": (-11.8, 3.0, 0),
    "C16": (-14.5, 3.0, 90),
    "C18": (-15.7, 3.0, 90),
    "C17": (-8.7, 2.05, 0),
    "R10": (-14.8, 5.6, 0),
    "R11": (-12.8, 5.6, 0),
    "C2": (-10.8, 5.6, 180),

    # ---- USB and charger (bottom edge)
    # CN1: board edge 2.7 mm below the footprint origin (0.55 mm past the shell pads).
    # Pads left to right: VBUS, D-, D+, ID, GND - the same order the pair leaves the MCU in.
    "CN1": (-4.45, YE - 2.7, 0),
    "U3": (-4.78, 13.2, 270),         # MCU side up, connector side down, in line with CN1 D+/D-
    "C23": (-2.7, 13.3, 90),
    "D5": (-7.1, 13.3, 90),           # VBUS pad down, next to CN1 pin 1
    "C12": (-8.5, 13.3, 90),
    "R26": (-1.5, 13.3, 90),          # shell RC, right of the connector's signal pins
    "C13": (-0.3, 13.3, 90),
    "R27": (-2.7, 10.4, 90),
    "R28": (-1.5, 10.4, 90),
    "U4": (-7.9, 10.3, 0),
    "C14": (-4.7, 11.25, 0),
    "C15": (-4.7, 10.2, 0),
    "R30": (-4.7, 9.1, 0),
    "R29": (-7.6, 7.6, 180),
    "LD3": (-10.4, 7.6, 0),

    # ---- status LEDs, lower left of the MCU (PB4 / PB5)
    # straight below pins 40 / 41, cathode up. (Left of the MCU they sat in the only
    # top-layer lane the USB pair can take from pins 32/33 down to U3.)
    "LD2": (0.9, 6.9, 270),
    "R21": (0.9, 9.4, 90),
    "LD1": (2.5, 6.9, 270),
    "R20": (2.5, 9.4, 90),

    # ---- SWD (bottom edge) and test points
    "P8": (4.8, YE - 3.73, 0),
    "R23": (7.3, 11.4, 180),
    "R24": (9.3, 11.4, 0),
    "TP1": (1.7, 11.45, 0),           # SWDIO
    "TP2": (3.9, 11.45, 0),           # SWCLK
    "TP3": (14.6, 7.3, 0),            # NRST

    # ---- headers on the right edge
    "P6": (18.1, -6.35, 0),           # FC_Signal
    "P3": (14.4, -3.8, 0),            # I2C
}

# Motor switches, one per corner; the pads sit on the top / bottom edge.
#  sx  sy   Q     Rgate Rpd   bridge DNP   pad+   pad-   back+   back-
MOTORS = [
    (-1, -1, "Q1", "R2", "R4", "R12", "R14", "MP1", "MP2", "MP9", "MP10"),
    (+1, -1, "Q2", "R3", "R5", "R16", "R18", "MP3", "MP4", "MP11", "MP12"),
    (-1, +1, "Q3", "R6", "R7", "R13", "R15", "MP5", "MP6", "MP13", "MP14"),
    (+1, +1, "Q4", "R8", "R9", "R17", "R19", "MP7", "MP8", "MP15", "MP16"),
]
for sx, sy, q, rg, rp, rb, rn, pp, pn, bp, bn in MOTORS:
    top = sy < 0
    gx = sx * QX + (0.97 if top else -0.97)            # gate pad x (FET drain faces the board edge)
    rr = 0 if sx < 0 else 180                          # bridge resistors: pad 2 (Mn_OUT) under the - pad
    PLACE.update({
        q: (sx * QX, sy * 11.0, 90 if top else 270),
        rb: (sx * (PX + 0.6), sy * 15.35, rr),         # 0R bridge, drain -> pad
        rn: (sx * (PX + 0.6), sy * 13.95, rr),         # DNP: raw PWM -> pad
        pp: (sx * QX, sy * 18.0, 0), bp: (sx * QX, sy * 18.0, 0, "B"),
        pn: (sx * PX, sy * 18.0, 0), bn: (sx * PX, sy * 18.0, 0, "B"),
        rg: (gx, sy * 7.6, 90 if top else 270),        # gate resistor, pad 2 at the gate
        rp: (gx + sx * 1.3, sy * 7.6, 270 if top else 90),
    })
# flyback diodes, between the FET and the side edge: anode towards the FET
PLACE.update({"D1": (-17.0, -10.0, 0), "D2": (17.0, -10.0, 180), "D3": (-17.0, 10.0, 0), "D4": (17.0, 10.0, 180)})

# (label, x1, y1, x2, y2) in the local frame
ZONES = [
    ("BLE", BX - 10.0, -YE + 0.2, BX + 8.0, -7.0),
    ("MCU + HSE", -4.1, -5.6, 12.5, 6.7),
    ("SENSORS", -11.0, -6.5, -5.4, 1.5),
    ("BATT / LDO", -19.8, -9.0, -7.6, 6.3),
    ("USB / CHARGER", -12.1, 6.6, 0.4, YE - 0.2),
    ("SWD", 0.5, 10.2, 10.4, YE - 0.2),
    ("M1", -19.8, -YE + 0.2, -9.3, -6.5), ("M2", 9.3, -YE + 0.2, 19.8, -6.5),
    ("M3", -19.8, 6.5, -9.3, YE - 0.2), ("M4", 10.5, 6.5, 19.8, YE - 0.2),
]


def P(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


def main():
    b = pcbnew.LoadBoard(PCB)
    fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
    missing = sorted(set(fps) - set(PLACE)); extra = sorted(set(PLACE) - set(fps))
    if missing or extra:
        raise SystemExit(f"not in table: {missing}; not on board: {extra}")
    for ref, (x, y, rot, *side) in PLACE.items():
        fp = fps[ref]
        fp.SetPosition(P(x, y))
        if (fp.GetLayer() == pcbnew.B_Cu) != bool(side):
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        fp.SetOrientationDegrees(rot)

    # Do this BEFORE removing anything: after a board.Remove(), pcbnew hands back
    # untyped objects from its collections and touching them fails or crashes.
    for d in list(b.GetDrawings()):
        if d.GetLayer() in (pcbnew.Edge_Cuts, pcbnew.Cmts_User):
            b.Remove(d)

    def seg(layer, a, c, w=0.1):
        s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a)); s.SetEnd(P(*c)); s.SetLayer(layer); s.SetWidth(pcbnew.FromMM(w)); b.Add(s)

    def arc(centre, start, deg):
        s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetCenter(P(*centre)); s.SetStart(P(*start)); s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(deg, pcbnew.DEGREES_T))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.1)); b.Add(s)

    r = 2.0                                           # corner radius
    E = pcbnew.Edge_Cuts
    seg(E, (-XE + r, -YE), (XE - r, -YE)); seg(E, (XE, -YE + r), (XE, YE - r))
    seg(E, (XE - r, YE), (-XE + r, YE)); seg(E, (-XE, YE - r), (-XE, -YE + r))
    arc((-XE + r, -YE + r), (-XE, -YE + r), 90)       # each arc runs clockwise on screen
    arc((XE - r, -YE + r), (XE - r, -YE), 90)
    arc((XE - r, YE - r), (XE, YE - r), 90)
    arc((-XE + r, YE - r), (-XE + r, YE), 90)

    C = pcbnew.Cmts_User
    for name, x1, y1, x2, y2 in ZONES:
        for a, c in (((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)), ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))):
            seg(C, a, c, 0.08)
        t = pcbnew.PCB_TEXT(b); t.SetText(name); t.SetLayer(C)
        t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.7), pcbnew.FromMM(0.7)))
        t.SetTextThickness(pcbnew.FromMM(0.1))
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        t.SetPosition(P(x1 + 0.2, y1 - 0.6)); b.Add(t)

    pcbnew.SaveBoard(PCB, b)
    print(f"placed {len(PLACE)} parts, board {2 * XE:.1f} x {2 * YE:.1f} mm")


if __name__ == "__main__":
    main()
