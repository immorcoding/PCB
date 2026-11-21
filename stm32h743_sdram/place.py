"""Placement of the STM32H743 + SDRAM board: outline, mounting holes, the two BGAs with their rule areas.

    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\place.py

Local frame (mm): origin at the board's top-left corner, x right, y down; board-file mm = local + 100.
Rotations are KiCad footprint orientations in degrees (counter-clockwise seen from the top).
Re-running moves every part listed in PLACE back to its table position, redraws Edge.Cuts and the two
rule areas, and parks every part that is not listed yet in rows below the board (stop 3 places only
the two BGAs and the mounting holes; the rest follows the two sketches, LAY-1 and RTE-13).

Fixed by the SPEC (section 8.1): the MCU is not rotated (A1 top-left); the SDRAM sits next to it;
connectors on the board edge. Starting values (section 8.2): board 85 x 75 mm with R2 corners, M3
holes in the corners, SDRAM to the right of the MCU with about 5 mm between the package bodies.
"""
import math, os, sys
import pcbnew
from pcbnew import VECTOR2I, FromMM as mm, ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "stm32h743_sdram.kicad_pcb")
OX, OY = 100.0, 100.0                 # local origin on the page

BOARD_W, BOARD_H, CORNER_R = 85.0, 75.0, 2.0
HOLE_INSET = 4.0                      # M3 hole centres from the board edges
MCU = (40.0, 37.0)                    # centre of U201 (10 x 10 mm body)
BODY_GAP = 5.0                        # MCU body edge to SDRAM body edge
SDRAM_ROT = 90                        # 0: 8 wide x 13 tall, A1 top-left; 90: 13 wide x 8 tall, A1 bottom-left
AREA_MARGIN = 1.0                     # rule area = package body + 1 mm on every side (approved 2026-11-16)

MCU_BODY = (10.0, 10.0)
SDRAM_BODY = (8.0, 13.0)              # at rotation 0


def sdram_centre():
    w = SDRAM_BODY[0] if SDRAM_ROT % 180 == 0 else SDRAM_BODY[1]
    return (MCU[0] + MCU_BODY[0] / 2 + BODY_GAP + w / 2, MCU[1])


def sdram_size():
    return SDRAM_BODY if SDRAM_ROT % 180 == 0 else (SDRAM_BODY[1], SDRAM_BODY[0])


PLACE = {
    "U201": (MCU[0], MCU[1], 0),
    "U301": (*sdram_centre(), SDRAM_ROT),
    "H801": (HOLE_INSET, HOLE_INSET, 0), "H802": (BOARD_W - HOLE_INSET, HOLE_INSET, 0),
    "H803": (HOLE_INSET, BOARD_H - HOLE_INSET, 0), "H804": (BOARD_W - HOLE_INSET, BOARD_H - HOLE_INSET, 0),
}
RULE_AREAS = {
    "BGA_MCU": (MCU, MCU_BODY),
    "BGA_SDRAM": (sdram_centre(), sdram_size()),
}
BGA_REFS = ("U201", "U301")           # ball pads: solder-mask opening equal to the pad (approved exception)

V = lambda x, y: VECTOR2I(mm(OX + x), mm(OY + y))


def outline(board):
    w, h, r = BOARD_W, BOARD_H, CORNER_R
    def seg(p, q):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(*p)); s.SetEnd(V(*q)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); board.Add(s)
    def arc(c, a0):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_ARC)
        pt = lambda a: (c[0] + r * math.cos(math.radians(a)), c[1] + r * math.sin(math.radians(a)))
        s.SetArcGeometry(V(*pt(a0)), V(*pt(a0 + 45)), V(*pt(a0 + 90)))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); board.Add(s)
    seg((r, 0), (w - r, 0)); seg((w, r), (w, h - r)); seg((w - r, h), (r, h)); seg((0, h - r), (0, r))
    arc((r, r), 180); arc((w - r, r), 270); arc((w - r, h - r), 0); arc((r, h - r), 90)


def rule_areas(board):
    for name, ((cx, cy), (bw, bh)) in RULE_AREAS.items():
        z = pcbnew.ZONE(board)
        z.SetIsRuleArea(True); z.SetZoneName(name); z.SetLayerSet(pcbnew.LSET.AllCuMask())
        for f in ("SetDoNotAllowTracks", "SetDoNotAllowVias", "SetDoNotAllowPads", "SetDoNotAllowZoneFills", "SetDoNotAllowFootprints"):
            getattr(z, f)(False)
        hx, hy = bw / 2 + AREA_MARGIN, bh / 2 + AREA_MARGIN
        ch = pcbnew.SHAPE_LINE_CHAIN()
        for x, y in ((cx - hx, cy - hy), (cx + hx, cy - hy), (cx + hx, cy + hy), (cx - hx, cy + hy)):
            ch.Append(mm(OX + x), mm(OY + y))
        ch.SetClosed(True)
        z.Outline().AddOutline(ch)
        board.Add(z)


def park(board, fps):
    """Parts without a position yet: rows below the board, left to right by reference, on the top side."""
    x, y, row_h = 0.0, BOARD_H + 12.0, 0.0
    key = lambda fp: (fp.GetReference().rstrip("0123456789"), int("".join(ch for ch in fp.GetReference() if ch.isdigit()) or 0))
    for fp in sorted(fps, key=key):
        fp.SetOrientationDegrees(0)
        bb = fp.GetBoundingBox(False)
        w, h = ToMM(bb.GetWidth()) + 1.0, ToMM(bb.GetHeight()) + 1.0
        if x + w > 160.0:
            x, y, row_h = 0.0, y + row_h, 0.0
        c = fp.GetPosition()
        fp.SetPosition(VECTOR2I(c.x + mm(OX + x) - bb.GetLeft(), c.y + mm(OY + y) - bb.GetTop()))
        x += w; row_h = max(row_h, h)


def main():
    board = pcbnew.LoadBoard(PCB)
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    missing = sorted(set(PLACE) - set(fps))
    if missing:
        sys.exit("not on the board (run net2pcb first): " + " ".join(missing))
    for ref, (x, y, rot, *side) in PLACE.items():
        fp = fps[ref]
        if (fp.GetLayer() == pcbnew.B_Cu) != bool(side):
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(V(x, y))
    for ref in BGA_REFS:
        for pad in fps[ref].Pads():
            pad.SetLocalSolderMaskMargin(0)
    park(board, [fp for ref, fp in fps.items() if ref not in PLACE])
    # Everything that is read from the board is read above: after the first board.Remove() pcbnew's
    # collections are unusable in this process (docs/tools.md), so the old outline and rule areas are
    # listed first, removed together, and only then are the new ones added.
    old = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    old += [z for z in board.Zones() if z.GetIsRuleArea() and z.GetZoneName() in RULE_AREAS]
    for item in old:
        board.Remove(item)
    outline(board)
    rule_areas(board)
    pcbnew.SaveBoard(PCB, board)
    print("placed %d parts, parked %d; board %g x %g mm; SDRAM at (%.2f, %.2f) rot %d" % (
        len(PLACE), len(fps) - len(PLACE), BOARD_W, BOARD_H, *sdram_centre(), SDRAM_ROT))


if __name__ == "__main__":
    main()
