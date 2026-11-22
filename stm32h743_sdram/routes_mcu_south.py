"""MCU south side (stop 7 part 2): the balls of rows K-R west of the SDRAM's south escapes and of the south-east
corner, to the PHY, the QSPI flash, the FPC, the touch / I2C link resistors and the debug header. Written by hand
(coordinates from the board; the fan-out planned on the ball lattice with the plane-slot rule); no autorouter.

    D:\KiCad\bin\python.exe scripts\busroute\build.py stm32h743_sdram\routes_mcu_south.py --fast
    LOCAL_BOARD=<board> ... (build.sh route2 builds it on the real board after routes_mcu_east.py)

Not routed here (no way out without breaking a rule; see the stop-7 report): USER_KEY (N3), LCD_VSYNC (N4), LCD_G2
(P3), LCD_R4 (P4), LCD_B5 (R2), LCD_R6 (R4), LCD_R3 (R5), LED1 (M11), LED2 (N12): every ball-gap site they can reach
either holds a via already or would join the antipads of its neighbours into a plane slot over 3 mm.
I2C4_SDA / I2C4_SCL are drawn from the MCU to R704.2 / R703.2 only (entered from the north-east); the codec side
joins them from those pads' west or north side.
"""
import os

BOARD = os.environ.get("LOCAL_BOARD", "stm32h743_sdram.kicad_pcb")
ORIGIN = (100, 100)
GROUP = "mcu_south"
YIELD_NETS = ["GND"]
DRC_IGNORE = {"solder_mask_bridge": "mask webs between fine-pitch pads of the footprints (QFN, FPC), there before this group"}
VIA_LIMIT = 6
VIEWS = [("sw", 32.5, 37.5, 40.5, 49.0, 90), ("se", 40.5, 38.5, 50.5, 49.0, 90)]


def V(x, y):
    return ("via", (x, y))


def db(ball, via, lay, pts):
    """dog-bone: ball -> via on L1, then `pts` on `lay` from the via"""
    return [("L1", ["U201." + ball, via]), V(*via), (lay, [via] + list(pts))]




def sw():
    """South-west quadrant (rows K-R, columns 1-6). L1 is closed there by FMC_A6's loop (y 43.5, x 31.4) and L6 by
    FMC_SDNWE's loop with the VDDA filter inside it, so every ball goes down to L4: four through the strip between
    the ball field and the crystal (vias at x 34.15-35.0, west of FMC_A10's moved L4 leg), seven through ball-gap
    vias (two of them reached by a short L1 jog) and CRS_DV through a via below row R between C221 and FB201 (bottom);
    the sites keep every antipad chain on L2 / L3 / L5 at or under the 2.91 mm already there. One lane per ball-column
    line; outside the area the lanes pass the ground vias of C223 / C221 (34.3 / 35.35, 44.9), and below FMC_SDNWE's
    L6 leg (y 45.6) the PHY lines go up to L1 in two staggered via rows 0.9 mm apart (no antipad touches another) and
    run west in the PHY's pin order; QSPI and DE stay on L4 to vias at their pins."""
    R = {}
    # ---- QSPI
    R["QSPI_BK1_IO2"] = [
        [("L1", ["U201.K1", (34.5, 38.3), (34.15, 38.65), (34.15, 39.3)]), V(34.15, 39.3),
         ("L4", [(34.15, 39.3), (33.45, 40.0), (33.45, 52.0)]), V(33.45, 52.0),
         ("L6", [(33.45, 52.0), (33.91, 52.0), "R402.2"])],
        [("L6", ["R402.2", (38.96, 57.05), (40.45, 57.05)]), V(40.45, 57.05),
         ("L1", [(40.45, 57.05), (40.135, 57.365), "U401.3"])]]
    R["QSPI_BK1_IO3"] = [
        [("L1", ["U201.K2", (35.775, 38.625), (35.325, 38.625), (34.65, 39.3)]), V(34.65, 39.3),
         ("L4", [(34.65, 39.3), (33.68, 40.27), (33.68, 51.0), (34.2, 51.52), (34.2, 53.0), (33.6, 53.6), (33.6, 58.635)]), V(33.6, 58.635),
         ("L1", [(33.6, 58.635), "U401.7"])],
        [("L1", ["U401.7", (31.85, 58.635), (31.15, 57.935), (28.1, 57.935), (27.8, 58.235), "R403.2"])]]
    R["QSPI_BK1_IO1"] = db("L2", (36.425, 39.275), "L4", [(35.45, 40.25), (35.45, 43.6), (36.0, 44.15),
                                                         (36.0, 55.6), (36.4, 56.0), (40.6, 56.0), (41.0, 56.4), (41.0, 58.635)])         + [V(41.0, 58.635), ("L1", [(41.0, 58.635), "U401.2"])]
    R["QSPI_BK1_IO0"] = [("L1", ["U201.L3", (37.075, 39.275), (37.075, 39.925)]), V(37.075, 39.925),
                         ("L4", [(37.075, 39.925), (38.05, 40.9), (38.05, 43.9), (38.79, 44.64), (38.79, 53.91), (38.5, 54.2), (38.5, 54.6)]), V(38.5, 54.6),
                         ("L1", [(38.5, 54.6), (32.6, 54.6), (32.25, 54.95), "U401.5"])]
    R["QSPI_CLK"] = db("M6", (38.375, 39.925), "L4", [(38.7, 40.25), (38.7, 43.5), (39.04, 43.84), (39.04, 55.4)])         + [V(39.04, 55.4), ("L1", [(39.04, 55.4), (34.215, 55.4), "U401.6"])]
    # ---- PHY (RMII and MDIO / MDC): L4 down to the via rows below FMC_SDNWE's L6 loop, then L1 west
    R["RMII_REF_CLK"] = [("L1", ["U201.N2", (35.75, 39.9), (34.65, 39.9)]), V(34.65, 39.9),
                         ("L4", [(34.65, 39.9), (34.15, 40.4), (34.15, 43.9), (34.825, 44.575), (34.825, 46.1)]), V(34.825, 46.1),
                         ("L1", [(34.825, 46.1), (25.25, 46.1), (23.15, 48.2), "U501.14"])]
    R["ETH_MDC"] = db("M3", (36.425, 39.925), "L4", [(36.1, 40.25), (36.1, 43.525), (36.25, 43.675), (36.25, 45.55), (36.5, 45.8), (36.5, 46.3)])         + [V(36.5, 46.3), ("L1", [(36.5, 46.3), (36.29, 46.51), (25.6, 46.51), (23.65, 48.46), "U501.13"])]
    R["ETH_MDIO"] = [
        db("P2", (36.425, 41.225), "L4", [(37.075, 41.875), (37.075, 45.35), (37.45, 45.725), (37.45, 46.3)])
        + [V(37.45, 46.3), ("L1", [(37.45, 46.3), (37.0, 46.75), (28.1, 46.75), "R503.2"])],
        [("L1", ["R503.2", "U501.12"])]]
    # CRS_DV goes down on L1 to the gap between C221 and FB201 (bottom): its ball's own gap sites would chain the
    # antipads of the quadrant into a 3.15 mm slot
    R["RMII_CRS_DV"] = [("L1", ["U201.R3", (36.75, 42.35), (36.6, 42.5)]), V(36.6, 42.5),
                        ("L4", [(36.6, 42.5), (36.6, 45.45), (36.95, 45.8), (36.95, 47.2)]), V(36.95, 47.2), ("L1", [(36.95, 47.2), (28.65, 47.2), (26.1, 49.75), "U501.11"])]
    R["RMII_RXD0"] = [("L1", ["U201.N5", (37.725, 40.575), (37.075, 40.575)]), V(37.075, 40.575),
                      ("L4", [(37.075, 40.575), (37.4, 40.9), (37.4, 45.35), (37.9, 45.85), (37.9, 47.2)]), V(37.9, 47.2),
                      ("L1", [(37.9, 47.2), (37.45, 47.65), (29.55, 47.65), (25.95, 51.25), "U501.8"])]
    R["RMII_RXD1"] = db("P5", (37.725, 41.225), "L4", [(37.725, 45.25), (38.38, 45.905), (38.38, 46.3)])         + [V(38.38, 46.3), ("L1", [(38.38, 46.3), (38.38, 47.6), (37.88, 48.1), (30.0, 48.1), (26.35, 51.75), "U501.7"])]
    # ---- LCD
    R["LCD_DE"] = [("L1", ["U201.L1", (35.0, 39.4), (35.0, 39.55)]), V(35.0, 39.55),
                   ("L4", [(35.0, 39.55), (35.0, 41.2), (34.8, 41.4), (34.8, 43.35), (35.76, 44.31), (35.76, 66.2), (34.25, 67.71)]), V(34.25, 67.71),
                   ("L1", [(34.25, 67.71), "J701.7"])]
    return R


def se():
    """South-east corner: rows R and N-M of columns 12-15. R12 / R13 (LCD_G4 / G5) go down on L1 to two vias above
    each other between FMC_D11 (L1) and FMC_D16 (L4) and run south on L4 between FMC_A11 and FMC_D16; the others
    reach L4 in the corridor S4 (between FMC_D17 and FMC_D15, L4) by a dog-bone (N14, M15), an L1 lead (R14, R15) or
    an L6 hop under the SDRAM's L1 lanes (N13), and leave it below FMC_D17's L4 leg through a row of vias 0.95 mm
    apart (no antipad chain) to L6: TP_RST / I2C4 west to the link resistors, USART1 south-east to the header."""
    R = {}
    YB = 46.9                       # the via row below S4 (L1 band y 46.3, FMC_D17 L4 47.5, FMC_SDNWE L6 45.6)
    R["LCD_G4"] = [("L1", ["U201.R12", (42.6, 42.25), (42.75, 42.4)]), V(42.75, 42.4),
                   ("L4", [(42.75, 42.4), (42.34, 42.81), (42.34, 65.0)]), V(42.34, 65.0),
                   ("L1", [(42.34, 65.0), (42.75, 65.41), "J701.24"])]
    R["LCD_G5"] = [("L1", ["U201.R13", (43.25, 42.65), (42.75, 43.15)]), V(42.75, 43.15),
                   ("L4", [(42.75, 43.15), (42.75, 66.0), (42.25, 66.5), (42.25, 67.6)]), V(42.25, 67.6),
                   ("L1", [(42.25, 67.6), "J701.23"])]
    # S4 lanes, west to east: TP_RST 44.225, SDA 44.55, SCL 44.875, TX 45.55, RX 45.9
    R["TP_RST"] = db("N14", (44.225, 40.575), "L4", [(44.225, 45.9), (44.35, 46.025), (44.35, YB)]) + [
        V(44.35, YB), ("L6", [(44.35, YB), (44.35, 59.7), (39.75, 64.3), (34.6, 64.3)]), V(34.6, 64.3),
        ("L1", [(34.6, 64.3), (34.6, 66.0), (34.11, 66.49), "R701.2"])]
    # I2C4: four pads each (MCU, the FPC link resistor, the codec and its pull-up); this group draws MCU -> R70x, the
    # other two pads are joined from the R70x pads' west / north side by the next group (one chain here, so a list)
    R["I2C4_SDA"] = [db("M15", (44.875, 39.925), "L4", [(44.55, 40.25), (44.55, 45.5), (45.25, 46.2), (45.25, YB)]) + [
        V(45.25, YB), ("L6", [(45.25, YB), (45.25, 59.25), (39.75, 64.75), (33.6, 64.75)]), V(33.6, 64.75),
        ("L1", [(33.6, 64.75), (29.75, 64.75), (29.25, 65.25), "R704.2"])]]
    R["I2C4_SCL"] = [[("L1", ["U201.N13", (43.575, 40.575)]), V(43.575, 40.575),
                     ("L6", [(43.575, 40.575), (44.875, 41.875), (44.875, 42.85)]), V(44.875, 42.85),
                     ("L4", [(44.875, 42.85), (44.875, 45.4), (46.2, 46.725)]), V(46.2, 46.725),
                     ("L6", [(46.2, 46.725), (46.2, 59.15), (40.2, 65.15), (34.15, 65.15), (33.6, 65.7)]), V(33.6, 65.7),
                     ("L1", [(33.6, 65.7), (30.95, 65.7), (30.45, 66.2), "R703.2"])]]
    # USART1: RX (R15) takes the upper S4 via, TX (R14) the lower one; both leave on L6 south-east and RX passes under
    # TX's header pin (they swap sides without a crossing)
    R["USART1_RX"] = [("L1", ["U201.R15", (45.2, 42.2)]), V(45.2, 42.2),
                      ("L4", [(45.2, 42.2), (45.2, 44.66), (47.15, 46.61), (47.15, YB)]), V(47.15, YB),
                      ("L6", [(47.15, YB), (47.15, 47.3), (59.2, 59.35), (59.2, 72.2), (59.6, 72.6), (62.48, 72.6), (62.88, 72.2), "J804.3"])]
    R["USART1_TX"] = [("L1", ["U201.R14", (43.9, 41.95), (44.475, 42.525), (45.53, 42.525)]), V(45.53, 42.525),
                      ("L4", [(45.53, 42.525), (45.53, 44.26), (48.1, 46.83)]), V(48.1, 46.83),
                      ("L6", [(48.1, 46.83), (60.34, 59.07), "J804.2"])]
    return R


THIN = 0.1016      # every track of this group outside the rule areas: the bus width (Default-class nets too)


def thin(pieces):
    if pieces and isinstance(pieces[0], list):
        return [thin(c) for c in pieces]
    return [pc if pc[0] == "via" or len(pc) > 2 else (pc[0], pc[1], THIN) for pc in pieces]


def routes(job):
    job.profile.classes["PWR"]["via"] = (0.45, 0.2)
    R = {}
    for part in (sw, se):
        R.update(part())
    return {n: thin(p) for n, p in R.items()}
