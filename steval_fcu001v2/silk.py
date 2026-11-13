"""Silkscreen of steval_fcu001v2: functional labels only.

    D:\\KiCad\\bin\\python.exe steval_fcu001v2\\silk.py

The board is too dense for reference designators at a legal size (text height >= 0.8 mm:
only 55 of 102 found a free spot), so none are printed: every reference is hidden from the
silkscreen and stays on the Fab layer for assembly drawings. What is printed is what someone
holding the board needs: header pin functions (both sides: the pins are through-hole),
motor pad polarity, battery polarity, test point and button names, the board name.

The silkscreen outlines of the three 1xN pin headers (NO_OUTLINE) are deleted: the space
between the pads and their neighbours is needed for the pin labels. Pin 1 is the square pad.

Text is 0.8 mm high (the minimum in docs/design-rules.md), 0.6 mm wide, 0.15 mm stroke.
Positions are in place.py's local frame (mm, origin at the board centre, y down) and are
the wanted text centre; a label may slide up to REACH to clear pads, footprint silkscreen,
the board edge and the labels placed before it. A label that finds no spot is printed where
it was asked for and reported with what is in its way, so the position can be fixed here.
Labels sit on tracks and tented vias freely. Re-running replaces all board-level silkscreen
text.
"""
import os
import subprocess
import sys
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "steval_fcu001v2.kicad_pcb")
OX, OY = 100.0, 100.0
H, W, T = 0.8, 0.6, 0.15
GAP, REACH, EDGE = 0.13, 0.4, 0.2      # clearance round a label, how far it may slide, board edge margin
NO_OUTLINE = ("P3", "P6", "P7")

# (text, x, y, rotation in degrees)
TOP = [
    # battery header
    ("BAT", -12.75, -5.0, 90), ("+", -13.8, -4.53, 0), ("-", -13.8, -6.6, 0),
    # USART header: pin functions to the right of the pins, the name above them (the strip
    # between the battery connector body and this header's body is too narrow for it)
    ("UART", -15.6, -2.5, 0),
    ("3V3", -16.05, -0.79, 0), ("GND", -16.05, 1.6, 0), ("RX", -16.35, 4.45, 0), ("TX", -16.35, 6.83, 0),
    # I2C header: pin functions written upwards in the gap between the two right-hand headers
    ("I2C", 14.4, -5.7, 0),
    ("3V3", 16.25, -3.8, 90), ("SDA", 16.25, -1.26, 90), ("SCL", 16.25, 1.28, 90), ("GND", 16.25, 3.82, 90),
    # FC_Signal header (battery, TIM2 channels 1-4, ground): only the two end pins are marked
    # on this side. The header body leaves 0.6 mm to the board edge, and the gap to the I2C
    # header holds that header's names; all six pins are labelled on the bottom.
    ("TIM2", 18.1, -8.1, 0),
    ("+", 16.25, -6.35, 0), ("G", 16.25, 6.35, 0),
    # SWD header and its two test points
    ("SWD", 8.3, 12.55, 0), ("DIO", 0.36, 11.45, 90), ("CLK", 5.24, 11.45, 90),
    # reset button and reset test point
    ("RST", 10.5, 8.5, 90), ("RST", 14.6, 5.65, 0),
    # charge LED
    ("CHG", -8.9, 6.2, 0),
    # board name
    ("FCU-4L", 10.7, -7.9, 0), ("rev A", 10.7, -6.8, 0),
]
BOTTOM = [
    ("BAT", -15.5, -2.6, 0), ("+", -13.8, -4.53, 0), ("-", -13.8, -7.07, 0),
    ("UART", -17.9, -2.6, 0),
    ("3V3", -15.9, -0.79, 0), ("GND", -15.9, 1.75, 0), ("RX", -16.2, 4.29, 0), ("TX", -16.2, 6.83, 0),
    ("I2C", 14.4, -5.7, 0),
    ("3V3", 12.35, -3.8, 0), ("SDA", 12.35, -1.26, 0), ("SCL", 12.35, 1.28, 0), ("GND", 12.35, 3.82, 0),
    ("TIM2", 18.0, -8.2, 0),
    ("+", 16.25, -6.35, 0), ("1", 16.25, -3.81, 0), ("2", 16.25, -1.27, 0), ("3", 16.25, 1.27, 0),
    ("4", 16.25, 3.81, 0), ("G", 16.25, 6.35, 0),
]
# motor pads: "Mn+" beside the + pad on both sides of the board (the other pad is -)
MOTOR = [("M1+", -14.2, -18.0), ("M2+", 14.2, -18.0), ("M3+", -14.2, 18.0), ("M4+", 14.2, 18.0)]
SILK = (pcbnew.F_SilkS, pcbnew.B_SilkS)


def P(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


def strip():
    """Hide references and values, delete old labels and the header outlines; save.
    Runs in its own process (--strip): after a Remove() pcbnew's collections hand back
    untyped objects, and loading the board again in the same process does not cure it."""
    b = pcbnew.LoadBoard(PCB)
    hidden, gone = 0, []
    for fp in b.GetFootprints():
        for f in (fp.Reference(), fp.Value()):
            if f.GetLayer() in SILK and f.IsVisible():
                f.SetVisible(False)
                hidden += 1
        if fp.GetReference() in NO_OUTLINE:
            gone += [(fp, g) for g in fp.GraphicalItems() if g.GetLayer() in SILK]
    old = [d for d in b.GetDrawings() if d.GetLayer() in SILK]
    for fp, g in gone:
        fp.Remove(g)
    for d in old:
        b.Remove(d)
    pcbnew.SaveBoard(PCB, b)
    print(f"silkscreen: {hidden} references/values hidden, {len(gone)} header outline items removed")


def main():
    subprocess.run([sys.executable, os.path.abspath(__file__), "--strip"], check=True)
    b = pcbnew.LoadBoard(PCB)
    mm = pcbnew.ToMM
    obst = {l: [] for l in SILK}      # (x0, y0, x1, y1, what)

    def box(bb):
        return (mm(bb.GetLeft()) - OX, mm(bb.GetTop()) - OY, mm(bb.GetRight()) - OX, mm(bb.GetBottom()) - OY)

    for fp in b.GetFootprints():
        ref = fp.GetReference()
        for pad in fp.Pads():
            for silk, cu in ((pcbnew.F_SilkS, pcbnew.F_Cu), (pcbnew.B_SilkS, pcbnew.B_Cu)):
                if pad.IsOnLayer(cu) or pad.HasHole():
                    obst[silk].append(box(pad.GetBoundingBox()) + (f"{ref} pad {pad.GetNumber()}",))
        for g in fp.GraphicalItems():
            if g.GetLayer() not in obst:
                continue
            r = box(g.GetBoundingBox())
            if isinstance(g, pcbnew.PCB_SHAPE) and g.GetShape() == pcbnew.SHAPE_T_RECT:
                x0, y0, x1, y1 = r                                 # an outline: only its four edges
                obst[g.GetLayer()] += [e + (f"{ref} silk",) for e in
                                       ((x0, y0, x1, y0), (x1, y0, x1, y1), (x0, y1, x1, y1), (x0, y0, x0, y1))]
            else:
                obst[g.GetLayer()].append(r + (f"{ref} silk",))
    eb = box(b.GetBoardEdgesBoundingBox())

    def blockers(x, y, w, h, layer):
        x0, y0, x1, y1 = x - w / 2 - GAP, y - h / 2 - GAP, x + w / 2 + GAP, y + h / 2 + GAP
        out = []
        if x0 < eb[0] + EDGE - GAP or y0 < eb[1] + EDGE - GAP or x1 > eb[2] - EDGE + GAP or y1 > eb[3] - EDGE + GAP:
            out.append("board edge")
        return out + [o[4] for o in obst[layer] if o[0] < x1 and x0 < o[2] and o[1] < y1 and y0 < o[3]]

    moved, stuck = [], []

    def spot(s, x, y, rot, layer):
        w, h = len(s) * W + 0.05, H + T
        if rot in (90, 270):
            w, h = h, w
        best = None
        n = int(REACH / 0.05)
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                d = (i * i + j * j) ** 0.5 * 0.05
                if d <= REACH and (best is None or d < best[0]) and not blockers(x + i * 0.05, y + j * 0.05, w, h, layer):
                    best = (d, round(x + i * 0.05, 2), round(y + j * 0.05, 2))
        side = "F" if layer == pcbnew.F_SilkS else "B"
        if best is None:
            stuck.append(f"{side} {s} at ({x}, {y}): {sorted(set(blockers(x, y, w, h, layer)))}")
            best = (0, x, y)
        elif best[0] > 0.01:
            moved.append(f"{side} {s} {best[0]:.2f}")
        obst[layer].append((best[1] - w / 2, best[2] - h / 2, best[1] + w / 2, best[2] + h / 2, f"label {s}"))
        return best[1], best[2]

    def text(s, x, y, rot, layer):
        x, y = spot(s, x, y, rot, layer)
        t = pcbnew.PCB_TEXT(b)
        t.SetText(s); t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(W), pcbnew.FromMM(H)))
        t.SetTextThickness(pcbnew.FromMM(T))
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER); t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        t.SetPosition(P(x, y))
        t.SetTextAngle(pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T))
        if layer == pcbnew.B_SilkS:
            t.SetMirrored(True)
        b.Add(t)

    for s, x, y, rot in TOP:
        text(s, x, y, rot, pcbnew.F_SilkS)
    for s, x, y, rot in BOTTOM:
        text(s, x, y, rot, pcbnew.B_SilkS)
    for s, x, y in MOTOR:
        text(s, x, y, 90, pcbnew.F_SilkS)
        text(s, x, y, 90, pcbnew.B_SilkS)
    pcbnew.SaveBoard(PCB, b)
    print(f"silkscreen: {len(TOP) + len(BOTTOM) + 2 * len(MOTOR)} labels placed")
    print("  slid (mm):", ", ".join(moved) or "none")
    for s in stuck:
        print("  NO FREE SPOT:", s)


if __name__ == "__main__":
    strip() if "--strip" in sys.argv else main()
