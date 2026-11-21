"""Placement of the STM32H743 + SDRAM board: outline, mounting holes, rule areas and every part (stop 4).

    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\place.py [--pcb <other board file>] [--rot <SDRAM rotation>]

--pcb and --rot are for trials on a copy of the board (line-order sketches of other SDRAM rotations).

Local frame (mm): origin at the board's top-left corner, x right, y down; board-file mm = local + 100.
Rotations are KiCad footprint orientations in degrees (counter-clockwise seen from the top).
Re-running moves every part listed in PLACE back to its table position, redraws Edge.Cuts and the two
rule areas, and parks every part that is not listed in rows below the board. A fourth element "B" puts
a part on the bottom. Stop 3 placed the two BGAs; stop 4 placed the rest around copper.sketch (LAY-1),
keeping the SDRAM line-order sketch valid; the bottom decoupling positions come from decap_search.py.
Measure with `sh stm32h743_sdram/build.sh layout`.

Fixed by the SPEC (section 8.1): the MCU is not rotated (A1 top-left); the SDRAM sits next to it;
connectors on the board edge. Starting values (section 8.2): board 85 x 75 mm with R2 corners, M3
holes in the corners, SDRAM to the right of the MCU with about 5 mm between the package bodies.
"""
import math, os, sys
import pcbnew
from pcbnew import VECTOR2I, FromMM as mm, ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "stm32h743_sdram.kicad_pcb")
if "--pcb" in sys.argv:
    PCB = os.path.abspath(sys.argv[sys.argv.index("--pcb") + 1])
OX, OY = 100.0, 100.0                 # local origin on the page

BOARD_W, BOARD_H, CORNER_R = 85.0, 75.0, 2.0
HOLE_INSET = 4.0                      # M3 hole centres from the board edges
MCU = (40.0, 37.0)                    # centre of U201 (10 x 10 mm body)
BODY_GAP = 8.0                        # MCU body edge to SDRAM body edge
SDRAM_ROT = 0                         # 0: 8 wide x 13 tall, A1 top-left; 90: 13 wide x 8 tall, A1 bottom-left
if "--rot" in sys.argv:
    SDRAM_ROT = int(sys.argv[sys.argv.index("--rot") + 1])
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
    # SDCLK series resistor (SPEC 9): east of ball H14, on the line of its escape channel (y = 36.675); the
    # SDRAM line-order sketch (routes_sdram.py) runs FMC_SDCLK_R from pad 2 into a via at x = 48.75
    "R201": (MCU[0] + 7.2, MCU[1] - 0.325, 0),
}
# Stop 4: every other part, by block. Positions are absolute local coordinates (the two BGAs stay where the
# line-order sketch put them). Comments name the copper region of copper.sketch each group sits on.
PLACE.update({
    # ---- MCU, top side. Crystals west of the MCU (round 3): HSE Y201 turned 270 degrees and centred on the
    # FMC_A6 via at (31.4, 39.0), which sits in its row gap with the A6 track in its column gap; LSE Y202 stood
    # vertical north-west of it. Each load capacitor on the far side of its crystal pad; trial routes in
    # routes_probe_xtal.py (all four nets on L1, no via).
    "Y201": (31.4, 39.0, 270), "C225": (28.9, 37.9, 270), "C226": (32.4, 41.65, 180),
    "Y202": (29.2, 34.8, 90), "C227": (27.0, 33.55, 180), "C228": (27.0, 36.05, 180),
    # supply entry of the MCU block (L3_3V3_MCU reaches north under the SDRAM bands to these pads)
    "R203": (39.5, 26.2, 0), "C217": (42.8, 26.2, 0),
    # BOOT0 pull-down and test pad, reset key, SWD header on the top edge
    "R202": (41.0, 23.9, 0), "TP201": (41.0, 21.6, 0),
    "SW201": (42.0, 12.0, 0), "C224": (42.0, 14.6, 0),
    "J803": (40.6, 5.0, 0),
    "TP111": (48.8, 24.0, 0),
    # ---- SDRAM supply entry (L3_3V3_SDRAM reaches north to it); bulk capacitor beside it
    "R301": (55.5, 26.2, 0), "C309": (59.0, 26.2, 0),
    # ---- microSD on the top edge, card slot facing out (L1_3V3_SD). The body front is 0.48 mm inside the edge:
    # the shell pads stand 0.21 mm proud of it and need the 0.254 mm copper-to-edge clearance.
    "J801": (55.0, 8.6, 180),
    "R812": (52.3, 18.7, 0), "C801": (55.5, 18.7, 270), "C802": (58.8, 18.7, 0),
    "R801": (51.5, 21.5, 90), "R802": (52.9, 21.5, 90), "R803": (54.3, 21.5, 90),
    "R804": (55.7, 21.5, 90), "R805": (57.1, 21.5, 90), "R806": (58.5, 21.5, 90),
    # ---- audio: jacks on the top edge (headphone left, line in right), codec below them with SAI facing the
    # MCU (L3_3V3A under it; L1_3V3_AUD east of it, L1_1V8 south of it)
    "J601": (16.5, 8.5, 0), "J602": (28.5, 8.5, 0),
    # U601's exposed pad (DRVSS) gets thermal vias as a via-in-pad exception like the PHY (coordinator, stop 4
    # round 2); the vias come with the fan-out
    "U601": (19.0, 26.0, 180),
    "C613": (4.6, 22.5, 90), "C614": (9.9, 22.5, 90), "R604": (4.6, 16.9, 0), "R605": (8.2, 16.9, 0),
    "C609": (14.9, 22.3, 90), "C605": (14.9, 24.4, 90), "C607": (14.9, 28.1, 90),
    "C606": (13.6, 24.4, 90), "C608": (13.6, 28.4, 90), "C611": (13.6, 19.6, 90), "C610": (10.4, 28.2, 0),
    "R609": (17.0, 18.6, 0), "R607": (19.2, 18.6, 0), "R606": (21.4, 18.6, 0), "R608": (23.6, 18.6, 0),
    "C616": (17.25, 21.0, 90), "C615": (19.0, 21.0, 90),
    "C601": (22.95, 24.5, 90), "C602": (24.5, 23.6, 90), "R610": (26.1, 23.6, 270),
    "R603": (25.6, 28.6, 0), "C612": (25.6, 29.75, 0),
    "R601": (37.2, 23.0, 90), "R602": (38.4, 23.0, 90),
    # 3.3 V analog LDO north-east of the codec: +5V from the L3 +5V strip through R112 (L1_5V_LDO)
    "U103": (29.5, 20.0, 180), "C111": (26.4, 19.9, 90), "C110": (32.6, 20.4, 90), "R112": (34.6, 20.4, 270),
    "TP104": (29.6, 23.9, 0), "TP107": (37.6, 16.4, 0),
    # 1.8 V LDO under the codec, output straight to DVDD (L1_1V8, L1_3V3_LDO)
    "U104": (20.0, 31.7, 0), "C603": (23.2, 29.75, 0), "C113": (23.7, 31.5, 0), "C604": (23.7, 33.1, 0),
    "C112": (16.9, 31.7, 270), "R113": (15.0, 31.7, 90), "R109": (13.4, 32.0, 270), "TP108": (9.9, 31.9, 0),
    "TP105": (26.6, 31.6, 0), "TP110": (4.0, 30.4, 0),
    # ---- Ethernet: RJ45 on the left edge, PHY to its right (L1_VDDA_PHY, L1_3V3_PHY)
    "J501": (17.24, 39.0, 270),
    "U501": (26.5, 44.5, 90),
    "C502": (22.81, 42.6, 0), "C510": (22.81, 41.5, 0), "C511": (22.81, 40.4, 0),
    "R507": (22.81, 47.9, 0), "R508": (22.81, 49.0, 0), "R509": (22.81, 50.1, 0), "R510": (22.81, 51.2, 0),
    "R505": (23.9, 46.9, 0, "B"), "C503": (24.6, 48.6, 270), "R504": (25.9, 49.4, 90),
    "C507": (28.6, 48.6, 270), "C506": (30.1, 48.8, 90), "R506": (27.2, 49.4, 90),
    "Y501": (26.6, 53.2, 180), "C508": (29.6, 52.8, 90), "C509": (23.6, 53.4, 90),
    "C504": (30.0, 44.5, 90), "C505": (31.3, 45.3, 90), "R503": (30.0, 42.4, 0), "R502": (32.6, 46.0, 90),
    "R501": (27.0, 40.9, 0),
    "FB501": (32.0, 49.6, 270), "R514": (33.85, 49.4, 90), "C501": (21.5, 54.7, 180),
    "R511": (8.6, 54.4, 0), "R512": (6.2, 54.4, 0), "R513": (13.9, 54.4, 0),
    # ---- QSPI flash under the MCU's south-west corner (L1_3V3_QSPI)
    "U401": (36.0, 55.0, 180), "C401": (30.7, 56.9, 90), "C402": (29.3, 56.9, 90), "R404": (30.4, 59.6, 0),
    "R401": (38.6, 56.4, 90, "B"), "R402": (38.6, 54.2, 90, "B"), "R403": (27.8, 57.2, 90),
    # ---- user LEDs and key south of the QSPI
    "D802": (14.0, 59.0, 0), "R808": (14.0, 60.6, 0), "D803": (17.6, 59.0, 0), "R809": (17.6, 60.6, 0),
    "SW801": (16.0, 63.6, 0), "R810": (19.6, 63.0, 90), "R811": (21.0, 63.0, 90), "C806": (22.4, 63.0, 90),
    "TP109": (60.4, 54.4, 0),
    # ---- LCD connector on the bottom edge, opening out, 3 mm in (L1_3V3_LCD)
    "J701": (41.0, 68.78, 0),
    "R701": (29.25, 64.0, 90), "R702": (30.45, 64.0, 90), "R703": (31.65, 64.0, 90), "R704": (32.85, 64.0, 90),
    "R705": (27.8, 64.0, 90), "C701": (48.6, 64.4, 90), "C702": (48.6, 61.5, 90), "R709": (48.6, 58.4, 90),
    # ---- backlight boost right of the LCD connector (L1_5V_BL, L1_SW_BL, L1_LED_A)
    "L701": (51.9, 53.0, 0), "U701": (55.6, 56.4, 0), "D701": (52.6, 59.3, 90), "C705": (55.0, 59.9, 90),
    "C703": (56.3, 49.3, 0), "C704": (56.2, 54.6, 180), "R710": (53.0, 48.7, 0),
    "R708": (52.0, 63.8, 90), "R707": (55.2, 63.6, 0), "R706": (57.8, 55.4, 90), "TP701": (57.6, 58.9, 0),
    # ---- bottom side under the BGAs (SPEC 6, agreed exception to LAY-5): MCU decoupling, VCAP, VDDA filter, and
    # the SDRAM decoupling. Positions from decap_search.py on the SDRAM sketch board: pads clear of every L6
    # track and foreign via, every ball keeps a free via site, every VDD ball has a 100 nF within 2.5 mm.
    # L3_3V3_MCU and L3_3V3_SDRAM under them; VDDA_MCU is an L6 pour here (the SW corner is closed on L1, L4, L6).
    "C218": (42.15, 34.15, 90, "B"), "C219": (41.00, 38.45, 90, "B"), "C220": (35.45, 40.75, 90, "B"),
    "C222": (34.40, 40.95, 90, "B"), "C201": (39.60, 35.70, 0, "B"), "C202": (43.85, 37.90, 0, "B"),
    "C203": (39.65, 38.85, 90, "B"), "C204": (36.40, 35.55, 90, "B"), "C205": (39.25, 34.00, 0, "B"),
    "C206": (38.15, 38.00, 0, "B"), "C207": (35.35, 34.05, 0, "B"), "C208": (40.85, 33.80, 90, "B"),
    "C209": (42.20, 40.55, 0, "B"), "C210": (44.20, 35.55, 0, "B"), "C211": (38.00, 39.20, 0, "B"),
    "C212": (38.15, 36.75, 0, "B"), "C213": (37.75, 33.00, 90, "B"), "C214": (39.05, 32.50, 90, "B"),
    "C215": (35.20, 36.30, 90, "B"), "C221": (36.45, 42.50, 0, "B"), "C223": (32.90, 43.40, 90, "B"),
    "C216": (42.70, 41.95, 0, "B"), "FB201": (36.60, 44.05, 0, "B"),
    "C301": (58.80, 33.40, 90, "B"), "C302": (58.35, 41.10, 90, "B"), "C303": (54.80, 34.20, 90, "B"),
    "C304": (55.25, 39.80, 90, "B"), "C305": (56.30, 31.10, 90, "B"), "C306": (59.85, 40.25, 90, "B"),
    "C307": (58.75, 31.85, 0, "B"), "C308": (60.80, 37.20, 0, "B"),
    # ---- debug UART header on the bottom edge right of the LCD connector: GND TX RX 3V3 from the left
    "J804": (57.8, 71.0, 90),
    # ---- CAN: terminal on the right edge, transceiver and ESD beside it (L1_3V3_CAN, L1_5V_CAN)
    "J802": (79.05, 21.0, 90),
    "U801": (66.62, 17.0, 0), "D801": (72.4, 17.0, 0),
    "C803": (61.9, 18.0, 180), "C804": (61.3, 20.6, 180), "R814": (62.2, 23.9, 90),
    "C805": (68.6, 20.75, 90), "R813": (68.9, 22.6, 0),
    "R807": (71.9, 22.0, 90), "JP801": (76.0, 26.2, 90),
    # ---- 3.3 V buck (L1_SW_3V3, L1_3V3_REG; input from the L3 +5V band)
    "U102": (69.5, 32.4, 180), "L102": (75.3, 31.45, 0), "C108": (69.5, 29.6, 0), "C109": (79.8, 31.9, 90),
    "R111": (79.5, 36.7, 270), "R105": (67.5, 35.2, 0), "R106": (67.5, 36.4, 0), "R104": (71.0, 35.2, 0),
    "R108": (73.6, 34.3, 0), "TP106": (74.4, 36.2, 0), "TP103": (83.0, 33.6, 0),
    "D103": (73.6, 10.0, 90), "R107": (73.6, 13.2, 90),
    # ---- 5 V buck (L1_12V, L1_SW_5V, L1_5V_REG)
    "U101": (69.0, 43.0, 180), "L101": (76.3, 43.0, 0), "C101": (69.0, 45.4, 0), "C104": (69.9, 40.45, 180),
    "C102": (65.6, 38.8, 180), "C103": (66.4, 47.4, 0), "C105": (82.4, 40.0, 90), "C106": (82.4, 44.8, 270),
    "C107": (77.0, 48.4, 0), "R102": (65.0, 41.6, 90), "R103": (65.0, 44.2, 90), "R110": (72.0, 49.0, 180),
    "TP102": (68.3, 51.35, 0),
    # ---- 12 V input: DC jack on the right edge, fuse, reverse-polarity P-MOS, TVS, bulk (L1_12V_JACK,
    # L1_12V_IN, L1_12V)
    "J101": (71.3, 59.0, 90),
    "F101": (68.0, 58.5, 90), "Q101": (67.0, 54.4, 0), "D101": (63.6, 54.4, 90), "R101": (64.4, 58.2, 90),
    "D102": (70.8, 68.0, 270), "C114": (62.6, 64.5, 0), "TP101": (64.0, 50.6, 0),
})
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
    # SaveBoard also rewrites the project file next to the board (pcbnew's defaults filled in, classes reordered;
    # same rules). make_project.py is that file's source: keep its bytes.
    pro = os.path.splitext(PCB)[0] + ".kicad_pro"
    keep = open(pro, "rb").read() if os.path.isfile(pro) else None
    pcbnew.SaveBoard(PCB, board)
    if keep is not None:
        with open(pro, "wb") as f:
            f.write(keep)
    print("placed %d parts, parked %d; board %g x %g mm; SDRAM at (%.2f, %.2f) rot %d" % (
        len(PLACE), len(fps) - len(PLACE), BOARD_W, BOARD_H, *sdram_centre(), SDRAM_ROT))


if __name__ == "__main__":
    main()
