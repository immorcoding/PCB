"""Placement of steval_fcu001v2: positions, board outline, zone annotations.

    D:\\KiCad\\bin\\python.exe steval_fcu001v2\\place.py

Local frame (mm): origin at the board centre, x to the right, y down.
Rotations are KiCad footprint orientations in degrees (counter-clockwise).
Re-running moves every listed part back to its table position and redraws
Edge.Cuts and the zone notes on Cmts.User.

Board: 50 x 46 mm, M3 holes in the corners. Everything is on the top side.
  top edge     BLE module (antenna overhanging the keep-out strip), USART header
  left edge    battery header, LDO, battery divider
  bottom edge  micro-USB with charger above it, SWD header
  right edge   FC_Signal header, I2C header beside it
  corners      one motor switch each, solder pads at the left / right edge
  centre       MCU (rotated 180: BLE SPI faces up, sensor SPI and USB face left,
               crystal and TIM2 face right, motor gates and LEDs face down)
"""
import os, sys
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "steval_fcu001v2.kicad_pcb")
OX, OY = 100.0, 100.0                 # local origin on the page

XE, YE = 25.0, 23.0                   # half board size
HX, HY = 21.5, 19.5                   # mounting holes
MX, MY = 4.0, 2.0                     # MCU centre
BX = -2.0                             # BLE module centre x (its SPI column lands above the MCU)

PLACE = {
    "H1": (-HX, -HY, 0), "H2": (HX, -HY, 0), "H3": (-HX, HY, 0), "H4": (HX, HY, 0),

    # ---- MCU and its supply caps
    "U2": (MX, MY, 180),
    "C11": (1.9, -3.3, 180),          # VCAP1, pin 22
    "C3": (-0.3, -2.9, 180),          # VDD pin 24
    "C4": (-1.4, 4.75, 180),          # VDD pin 36
    "C5": (6.5, 7.2, 180),            # VDD pin 48
    "C6": (9.3, 5.0, 0),              # VBAT pin 1
    "C7": (9.1, 0.85, 0),             # VDDA pin 9
    # ---- HSE: OSC_IN (pin 5) runs between the two left pads to Y1.1, OSC_OUT (pin 6) to Y1.3
    "Y1": (12.2, 2.5, 90),
    "C9": (11.35, -0.7, 90),          # OSC_OUT load cap, above Y1.3
    "C8": (15.0, 3.6, 0),             # OSC_IN load cap, right of Y1.1
    # ---- reset
    "S1": (14.5, 7.2, 0),
    "R22": (10.4, 7.2, 90),
    "C10": (9.1, 7.2, 90),

    # ---- BLE module, antenna end at the top edge
    "U1": (BX, -YE + 8.9, 0),
    "C1": (-10.9, -12.2, 180),
    "R1": (-10.9, -13.5, 180),

    # ---- sensors, left of the MCU (SPI2 pins 26..29)
    "U8": (-5.5, 1.0, 270),           # IMU, near the board centre
    "C21": (-8.3, 0.4, 180),
    "C22": (-8.3, 1.6, 180),
    "U7": (-5.5, -5.0, 0),
    "C19": (-8.0, -5.6, 180),
    "C20": (-8.0, -4.4, 180),

    # ---- battery in, LDO, battery divider (left edge)
    "BT1": (-20.5, 1.27, 180),        # right-angle header, pins overhang the left edge
    "U6": (-15.0, 5.0, 0),
    "C16": (-17.8, 5.0, 90),
    "C18": (-19.0, 5.0, 90),
    "C17": (-11.9, 4.05, 0),
    "R10": (-18.9, 7.4, 0),
    "R11": (-16.9, 7.4, 0),
    "C2": (-17.65, 8.6, 0),

    # ---- USB and charger (bottom edge)
    # CN1: board edge 2.7 mm below the footprint origin (0.55 mm past the shell pads).
    # Pads left to right: VBUS, D-, D+, ID, GND - the same order the pair leaves the MCU in.
    "CN1": (-5.0, YE - 2.7, 0),
    "U3": (-5.3, 15.9, 270),          # MCU side up, connector side down, in line with CN1 D+/D-
    "C23": (-3.2, 15.9, 90),
    "D5": (-7.6, 16.0, 90),           # VBUS pad down, next to CN1 pin 1
    "C12": (-9.0, 16.0, 90),
    "R27": (-3.0, 12.6, 90),
    "R28": (-1.8, 12.6, 90),
    "R26": (-11.0, 20.0, 90),
    "C13": (-12.2, 20.0, 90),
    "U4": (-8.5, 12.2, 0),
    "C14": (-5.3, 13.2, 0),
    "C15": (-5.3, 14.3, 0),
    "R30": (-5.3, 11.25, 0),
    "R29": (-7.0, 9.3, 180),
    "LD3": (-9.8, 9.3, 0),

    # ---- status LEDs, below the MCU (PB4 / PB5)
    "R20": (-4.8, 8.2, 0),
    "LD1": (-2.2, 8.2, 180),
    "R21": (-4.8, 9.9, 0),
    "LD2": (-2.2, 9.9, 180),

    # ---- SWD (bottom edge) and test points
    "P8": (5.5, 17.0, 0),
    "R23": (10.9, 14.4, 180),
    "R24": (10.9, 15.73, 0),
    "TP1": (3.4, 11.6, 0),
    "TP2": (5.6, 11.6, 0),
    "TP3": (7.8, 11.6, 0),

    # ---- headers
    "P6": (22.5, -6.35, 0),           # FC_Signal, right edge
    "P3": (18.6, -6.5, 0),            # I2C
    "P7": (7.9, -20.8, 90),           # USART, top edge, pins run to the right
}

# Motor switches: one per corner. (sx, sy) mirror the top-left block.
#            Q    D    Rgate Rpd  bridge DNP  pad+  pad-
MOTORS = [
    (-1, -1, "Q1", "D1", "R2", "R4", "R12", "R14", "MP1", "MP2"),
    (+1, -1, "Q2", "D2", "R3", "R5", "R16", "R18", "MP3", "MP4"),
    (-1, +1, "Q3", "D3", "R6", "R7", "R13", "R15", "MP5", "MP6"),
    (+1, +1, "Q4", "D4", "R8", "R9", "R17", "R19", "MP7", "MP8"),
]
for sx, sy, q, d, rg, rp, rb, rn, pp, pn in MOTORS:
    left = sx < 0
    gy = -0.97 if left else 0.97          # gate pad offset from the FET centre, in board y
    PLACE.update({
        q: (sx * 16.8, sy * 11.4, 180 if left else 0),       # drain towards the board edge
        d: (sx * 16.8, sy * 14.6, 0 if left else 180),       # cathode (+BATT) towards the edge
        rb: (sx * 20.0, sy * 11.3, 90),                       # 0R bridge drain -> pad
        rn: (sx * 19.9, sy * 13.6, 0),                        # DNP: raw PWM -> pad
        pp: (sx * 22.9, sy * 13.8, 90),
        pn: (sx * 22.9, sy * 11.2, 90),
        rg: (sx * 13.4, sy * 11.4 + gy, 180 if left else 0),  # gate resistor, level with the gate pad
        rp: (sx * 13.4, sy * 11.4 + gy + (1.2 if gy < 0 else -1.2), 0 if left else 180),
    })

# (label, x1, y1, x2, y2) in the local frame
ZONES = [
    ("BLE", -10.0, -YE + 0.2, 6.0, -10.0),
    ("MCU + HSE", -2.0, -4.2, 15.4, 9.4),
    ("SENSORS", -9.4, -6.5, -3.8, 3.0),
    ("BATT / LDO", -24.6, -3.3, -11.0, 9.2),
    ("USB / CHARGER", -13.3, 8.4, 0.4, YE - 0.2),
    ("SWD", 1.0, 10.4, 12.0, YE - 0.2),
    ("M1", -24.6, -15.8, -12.3, -9.3), ("M2", 12.3, -15.8, 24.6, -9.3),
    ("M3", -24.6, 9.3, -12.3, 15.8), ("M4", 12.3, 9.3, 24.6, 15.8),
]


def P(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


def main():
    b = pcbnew.LoadBoard(PCB)
    fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
    missing = sorted(set(fps) - set(PLACE)); extra = sorted(set(PLACE) - set(fps))
    if missing or extra:
        raise SystemExit(f"not in table: {missing}; not on board: {extra}")
    for ref, (x, y, rot) in PLACE.items():
        fp = fps[ref]
        fp.SetPosition(P(x, y))
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
