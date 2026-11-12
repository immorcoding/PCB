"""Placement of stm32f411_minsys: positions, board outline, zone annotations.

    D:\\KiCad\\bin\\python.exe stm32f411_minsys\\place.py

Local frame (mm): x along the board, 0 at header pin 20 (USB end);
y across the board, 0 on the centre line, negative = J3 row (top).
Rotations are KiCad footprint orientations in degrees.
Re-running moves every listed part back to its table position and redraws
Edge.Cuts and the zone notes on Cmts.User.
"""
import os, sys
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "stm32f411_minsys.kicad_pcb")
OX, OY = 100.0, 100.0                 # local origin on the page

ROW = 10.16                           # header rows at y = +/-ROW (800 mil apart)
X0, X1 = -2.67, 50.93                 # board edge, 53.6 mm long
YE = 12.0                             # board edge, 24.0 mm wide (header courtyards stay inside)
CX = 24.13                            # MCU centre

SWX = 43.2                            # button column
PLACE = {
    # connectors. J3/J4 sit on the bottom side (pins point down, for a breadboard)
    "J1": (0.33, 0.0, 270),           # USB-C, opening at the left edge
    "J2": (46.9, -3.81, 0),           # SWD, right-angle, pins overhang the right edge
    "J3": (48.26, -ROW, 270, "B"),    # P1, pin 1 at the right
    "J4": (48.26, ROW, 270, "B"),     # P2, pin 1 at the right
    # MCU, rotated 45 deg: corner 12/13 up, 24/25 left, 36/37 down, 48/1 right
    "U1": (CX, 0.0, 225),
    # USB CC pull-downs, mirrored about the centre line
    "R1": (7.4, -2.4, 0),
    "R2": (7.4, 2.4, 0),
    # VBUS -> D1 -> +5V -> U2 -> +3V3, one row, left to right
    "D1": (6.75, -4.95, 270),
    "C1": (8.6, -4.95, 270),
    "U2": (11.7, -4.95, 0),
    "C2": (14.7, -4.95, 270),
    "C3": (16.4, -4.95, 270),
    # bottom-left row: power LED, bulk cap, VDD36 cap
    "D2": (8.0, 6.4, 0),
    "R3": (11.2, 6.4, 180),
    "C4": (14.4, 6.4, 0),
    "C7": (21.3, 6.4, 180),           # VDD pin 36 (bottom corner)
    # left corner of the MCU
    "R5": (13.3, -0.9, 0),            # PB2 pull-down
    "C6": (16.8, -0.9, 180),          # VDD pin 24
    "C14": (16.8, -2.6, 180),         # VCAP1 pin 22
    # right corner of the MCU. Row 1 leaves the strip above it free for
    # OSC_IN, PC13..15 and VBAT leaving the corner.
    "C5": (31.6, 0.8, 0),             # VDD pin 48
    "C10": (34.8, 0.8, 0),            # VBAT pin 1
    "D4": (37.9, 0.8, 0),             # user LED, K towards PC13
    "R4": (40.6, 1.7, 270),           # BOOT0 pull-down, next to SW2
    # row 2
    "D3": (34.9, 2.7, 0),             # +3V3 -> VBAT
    "R6": (38.2, 2.7, 0),
    # row 3: VDDA filter (FB1 + 1uF), feeds C9 through a bottom-layer hop
    "FB1": (34.9, 4.6, 0),
    "C8": (38.2, 4.6, 0),
    # HSE, hugging pins 5/6. Y1's 1-3 diagonal runs parallel to the MCU edge, so
    # both crystal pads are the same distance out; each load cap sits on its trace.
    "C12": (27.0, -5.5, 180),         # OSC_OUT: pin 6 -> C12 -> Y1.3
    "Y1": (30.3, -4.4, 90),
    "C11": (33.7, -3.3, 0),           # OSC_IN: pin 5 -> Y1.1 -> C11
    "C9": (27.0, -7.1, 0),            # VDDA 100nF, pin 9
    "C13": (39.0, -5.4, 270),         # NRST cap, at the button / header pin
    # reset / boot
    "SW1": (SWX, -3.3, 90),
    "SW2": (SWX, 3.3, 270),
}

# Bottom-side parts: after the flip, the rotation is whichever one puts this pad here.
BACK_CHECK = {"J3": ("20", (0.0, -ROW)), "J4": ("20", (0.0, ROW))}

# 3D models the stock library does not ship; a look-alike is used instead.
MODELS = {
    # same 7x7 body, only the exposed pad differs
    "U1": "${KICAD10_3DMODEL_DIR}/Package_DFN_QFN.3dshapes/QFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm.step",
    # GCT USB4105 is a 16-pin receptacle of the same outline: visual stand-in only
    "J1": "${KICAD10_3DMODEL_DIR}/Connector_USB.3dshapes/USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal.step",
}

XK = (28.5, -6.6, 32.1, -2.2)         # crystal keep-out on B.Cu: x1, y1, x2, y2

# (label, x1, y1, x2, y2) in the local frame
ZONES = [
    ("USB-C IN", X0 + 0.3, -5.6, 5.8, 5.6),
    ("5V -> 3V3", 5.6, -6.9, 17.4, -3.3),
    ("MCU + DECOUPLING", 15.0, -8.4, 33.0, 8.4),
    ("HSE 8MHz", 25.3, -8.1, 35.4, -2.3),
    ("RST/BOOT", 41.3, -6.6, 45.1, 6.6),
    ("SWD", 45.2, -5.8, X1 - 0.2, 5.8),
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
        if ref in BACK_CHECK:
            num, want = BACK_CHECK[ref]
            for r in (0, 90, 180, 270):
                fp.SetOrientationDegrees(r)
                pad = next(p for p in fp.Pads() if p.GetNumber() == num)
                if abs(pad.GetPosition().x - P(*want).x) < 1000 and abs(pad.GetPosition().y - P(*want).y) < 1000:
                    break
            else:
                raise SystemExit(f"{ref}: no rotation puts pad {num} at {want}")
        if ref in MODELS:
            m = pcbnew.FP_3DMODEL()               # Models() hands out copies: rebuild the list
            m.m_Filename = MODELS[ref]
            fp.Models().clear()
            fp.Add3DModel(m)

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

    r = 1.0                                           # corner radius
    E = pcbnew.Edge_Cuts
    seg(E, (X0 + r, -YE), (X1 - r, -YE)); seg(E, (X1, -YE + r), (X1, YE - r))
    seg(E, (X1 - r, YE), (X0 + r, YE)); seg(E, (X0, YE - r), (X0, -YE + r))
    arc((X0 + r, -YE + r), (X0, -YE + r), 90)         # each arc runs clockwise on screen
    arc((X1 - r, -YE + r), (X1 - r, -YE), 90)
    arc((X1 - r, YE - r), (X1, YE - r), 90)
    arc((X0 + r, YE - r), (X0 + r, YE), 90)

    C = pcbnew.Cmts_User
    for name, x1, y1, x2, y2 in ZONES:
        for a, c in (((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)), ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))):
            seg(C, a, c, 0.08)
        t = pcbnew.PCB_TEXT(b); t.SetText(name); t.SetLayer(C)
        t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.7), pcbnew.FromMM(0.7)))
        t.SetTextThickness(pcbnew.FromMM(0.1))
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        t.SetPosition(P(x1 + 0.2, y1 - 0.6)); b.Add(t)

    # B.Cu under the crystal: GND pour only, no tracks or vias
    for z in list(b.Zones()):
        if z.GetZoneName() == "XTAL_KEEPOUT":
            b.Remove(z)
    z = pcbnew.ZONE(b)
    z.SetIsRuleArea(True); z.SetZoneName("XTAL_KEEPOUT"); z.SetLayer(pcbnew.B_Cu)
    z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False); z.SetDoNotAllowZoneFills(False)
    for x, y in ((XK[0], XK[1]), (XK[2], XK[1]), (XK[2], XK[3]), (XK[0], XK[3])):
        z.AppendCorner(P(x, y), -1)
    b.Add(z)

    pcbnew.SaveBoard(PCB, b)
    print(f"placed {len(PLACE)} parts, board {X1 - X0:.1f} x {2 * YE:.1f} mm")


if __name__ == "__main__":
    main()
