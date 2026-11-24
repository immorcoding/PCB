"""MCU north-gate nets taken round the west side (stop 7 compose, issue 22; c9: + QSPI_BK1_NCS and LCD_G3): LCD_B6,
LCD_B7, LCD_DISP, LCD_G3 to the FPC J701 (DISP through its resistor R705 first), QSPI_BK1_NCS to the flash's pin 1 and
its pull-up R401, RMII_TX_EN / RMII_TXD0 to the PHY's north pins, and PHY_NRST re-sited off the LSE crystal. Local mm
(board mm - 100); every net written with coordinates (RTE-3, RTE-4).

    LOCAL_BOARD=<board> D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.routing.busroute.build stm32h743_sdram\\routes_mcu_west.py --fast
    (build.sh route2 builds it on the real board after routes_mcu_sw.py)

  L3   from each gate north, nested 45-degree turns west at rows y 29.15 .. 27.9 (B6 southmost), north into a staircase
       of seven vias (34.75, 27.32) .. (37.45, 24.8) (0.45 east, 0.42 north each); G3 (L6 gate at x 40.65, TXD0's L3 x)
       crosses the TX legs on L1 (via (40.65, 27.3), row y 27.85, north at x 36.55 into its staircase via)
  L4   west from each via at its own row (pitch 0.42; the SAI vias moved north of the top row), round the corner into
       the corridor (lanes x 29.25 .. 27.88, pitch 0.2286, TXD1 west of them at 27.65), down the corridor
  TX   TXD0 / TX_EN turn west at y 41.5 / 41.95 to vias (25.45, 41.5) / (26.1, 41.95), L1 into pins 17 / 16
  LCD  G3 / NCS / DISP / B7 / B6 jog south-west below the TX turns to x 27.14 .. 28.06, down between the PHY's vias and
       USER_KEY (x 28.5); B6 / B7 turn east at y 59.35 / 59.58 and drop into FPC vias; DISP on to R705; NCS and G3 step
       west, drop to L3 (vias y 66.3 / 66.9, south of the I2C4 L6 rows) and run east in rows y 66.6 / 66.9: NCS north
       at x 39.26 to a via south of the flash's pin 1 (a second via from the pin to R401.2 on the bottom), G3 on to its
       FPC via (S row) and pin 25
  NRST PHY_NRST: L6 west to x 31.4, south past the LSE crystal's east side (x 30.9), west between the two crystals
       (y 36.75, under CODEC_NRST's L3 run), down x 28.1 west of the HSE crystal, SW to a via (25.95, 42.9), L1 as
       before into R501.1 and pin 15
"""
import os
from fan_leads import plan, lead, ext

BOARD = os.environ.get("LOCAL_BOARD", "stm32h743_sdram.kicad_pcb")
ORIGIN = (100, 100)
GROUP = "mcu_w"
OPEN_ENDS = True               # opt1: DISP and NCS branch at a via (one chain each starts or ends at the via)
YIELD_NETS = ["GND"]
VIA_LIMIT = 8
LEN_MAX = {"QSPI_BK1_NCS": 1000}   # SPEC 9 (user 2026-11-23): the chip select has no length cap (rule qspi_ncs_no_cap)
DRC_IGNORE = {"solder_mask_bridge": "mask webs between fine-pitch pads of the footprints (QFN, FPC), there before this group"}
VIEWS = [("north", 32.0, 23.5, 42.5, 31.5, 60), ("corridor", 24.0, 24.0, 34.0, 48.0, 35), ("phy", 20.0, 40.0, 30.0, 49.5, 60),
         ("south", 24.0, 52.0, 40.0, 70.5, 35)]
T = 0.1016
P = 0.2286


def r4(v):
    return round(v, 4)


def V(x, y):
    return ("via", (r4(x), r4(y)))


def L(layer, pts):
    return (layer, [p if isinstance(p, str) else (r4(p[0]), r4(p[1])) for p in pts], T)


def ball(net):
    return next(num for num, v in plan()["U201"]["signal"].items() if v["net"] == net)


def out(net, pts):
    """the planned lead (ball -> rule-area edge) continued through pts on its inner layer, thin outside the area"""
    pcs = ext(lead(ball(net)), pts)
    return [pc if pc[0] == "via" else (pc[0], [p if isinstance(p, str) else (r4(p[0]), r4(p[1])) for p in pc[1]], T) for pc in pcs]


C = 0.35                                   # chamfer of every 90-degree turn (RTE: no chamfer under 0.35)
# c9: seven nets in the loop (rows south -> north): B6, B7, DISP, NCS, G3, TX_EN, TXD0. NCS (L3 gate x 39.35, boxed
# at its gate since stop 7) and G3 join between DISP and the TX pair: the TX lines keep the outer (west) lanes and turn
# west at the corridor's foot, the five LCD / flash lines go on south. G3's gate is on L6 at x 40.65 (TXD0's L3 x): it
# crosses the TX legs on L1 in the band north of the L1 river (y 27.85) to its staircase via.
NORTH = ["LCD_B6", "LCD_B7", "LCD_DISP", "QSPI_BK1_NCS", "LCD_G3", "RMII_TX_EN", "RMII_TXD0"]
GX = {"LCD_B6": 37.4, "LCD_B7": 38.05, "LCD_DISP": 38.7, "QSPI_BK1_NCS": 39.35, "RMII_TX_EN": 40.0, "RMII_TXD0": 40.65}
YR = {"LCD_B6": 29.15, "LCD_B7": 28.9, "LCD_DISP": 28.65, "QSPI_BK1_NCS": 28.4, "RMII_TX_EN": 28.15, "RMII_TXD0": 27.9}


def north(net):
    k = NORTH.index(net)
    vx, vy = r4(34.75 + 0.45 * k), r4(27.32 - 0.42 * k)
    lx = r4(29.25 - P * k)                          # corridor lane
    l4 = [(vx, vy), (lx + C, vy), (lx, vy + C)]
    if net == "LCD_G3":
        # L6 gate north to (40.65, 27.6), north of TXD0's L3 corner; L1 west along y 27.85 (under R203's pads, the
        # TX legs on L3 below), north at x 36.55 into the staircase
        pcs = out(net, [(40.65, 27.3)]) + [V(40.65, 27.3),
                                             L("L1", [(40.65, 27.3), (40.1, 27.85), (36.9, 27.85), (36.55, 27.5), (vx, vy)])]
        return pcs + [V(vx, vy)], l4, lx
    gx, yr = GX[net], YR[net]
    l3 = [(gx, yr + C), (gx - C, yr), (vx + C, yr), (vx, yr - C), (vx, vy)]
    return out(net, l3) + [V(vx, vy)], l4, lx


def routes(job):
    R = {}
    # ---- TX to the PHY: lanes turn west, vias, L1 diagonals into pins 17 / 16
    pcs, l4, lx = north("RMII_TXD0")
    R["RMII_TXD0"] = pcs + [L("L4", l4 + [(lx, 41.15), (lx - C, 41.5), (25.45, 41.5)]), V(25.45, 41.5),
                            L("L1", [(25.45, 41.5), (21.65, 45.3), "U501.17"])]
    pcs, l4, lx = north("RMII_TX_EN")
    R["RMII_TX_EN"] = pcs + [L("L4", l4 + [(lx, 41.6), (lx - C, 41.95), (26.1, 41.95)]), V(26.1, 41.95),
                             L("L1", [(26.1, 41.95), (25.65, 41.95), (21.9, 45.7), (21.9, 47.65), (22.15, 47.9), "U501.16"])]
    # ---- LCD and NCS: jog south-west below the TX turns (starts staggered so the diagonals keep the pitch), down x
    # 27.14 .. 28.06 between the PHY's vias and USER_KEY (x 28.5)
    LCD = ["LCD_G3", "QSPI_BK1_NCS", "LCD_DISP", "LCD_B7", "LCD_B6"]
    fin = {}
    for i, net in enumerate(LCD):
        pcs, l4, lx = north(net)
        jy = r4(42.21 + 0.095 * i)
        x2 = r4(lx - 1.193)
        fin[net] = (pcs, l4 + [(lx, jy), (x2, jy + 1.193)], x2)
    # B6 / B7: east under the QSPI wall's south end, drop into their FPC vias
    for net, row, xp, yv, pin in (("LCD_B6", 59.35, 37.75, 68.2, 14), ("LCD_B7", r4(59.35 + P), 37.25, 68.75, 13)):
        pcs, l4, x2 = fin[net]
        R[net] = pcs + [L("L4", l4 + [(x2, row - C), (x2 + C, row), (xp - C, row), (xp, row + C), (xp, yv)]), V(xp, yv),
                        L("L1", [(xp, yv), "J701.%d" % pin])]
    # opt1 (review 1): the loop's south end. G3 and NCS jog west at one height (starts staggered 0.0947 so the parallel
    # diagonals keep the lane pitch; were at y 63.5 / 64.5) and their vias stand on one 45-degree diagonal
    # (26.65, 66.9) / (27.1, 66.45). DISP: down to one via west of R705.1 as before and on along L4 east at the via's
    # row to the FPC via (a branch at the via, accepted: one via less; was R705.1 down to a second via (27.8, 68.25))
    JOG, JX = 64.0, {"LCD_G3": 26.65, "QSPI_BK1_NCS": 27.1}
    jog = {n: [(x2, r4(JOG + 0.0947 * k)), (JX[n], r4(JOG + 0.0947 * k + x2 - JX[n]))]
           for k, (n, (pcs, l4, x2)) in enumerate((n, fin[n]) for n in ("LCD_G3", "QSPI_BK1_NCS"))}
    pcs, l4, x2 = fin["LCD_DISP"]
    # stop 8 (review 2, b3): L4 runs east along y 67.79 (0.134 mm under VSYNC's FPC via) straight from the via's SE
    # step, without the hat (the step from y 68.05 up to 67.79, 2 bends; the crowded item). The via 0.26 higher (26.9,
    # 67.59) for it, the SW diagonal 0.25 higher (G3's via (26.65, 66.9) 0.14 mm off it) so that the vertical into the
    # via keeps 0.35. Tried first: the via at (26.9, 67.79) and L4 straight east from it: DRC track_angle (90 degrees
    # across the via, the corner_angle rule sees both L4 legs)
    R["LCD_DISP"] = [pcs + [L("L4", l4 + [(x2, 66.54), (26.9, r4(66.54 + x2 - 26.9)), (26.9, 67.59)]), V(26.9, 67.59),
                            L("L4", [(26.9, 67.59), (27.1, 67.79), (35.34, 67.79), (35.75, 68.2)]),
                            V(35.75, 68.2), L("L1", [(35.75, 68.2), "J701.10"])],
                     [L("L1", [(26.9, 67.59), (26.98, 67.51), "R705.1"])]]

    # NCS and G3 (west of DISP) step west and drop to L3 below the I2C4 / touch rows; L3 east in two rows south of
    # everything (y 66.4 / 66.65; G7 and G4 have left L3 at y 65.9): NCS north at x 39.245 to a via south of the flash's
    # pin 1 (north of the east bundle's L6 diagonals), L1 into it, and from the pin a second via to its pull-up R401.2 on
    # the bottom; G3 on east to its FPC via (S row) between G4's L1 and G2's L3 into pin 25
    # opt1 (review 1): NCS's L3 runs on north into the via that feeds R401 (39.095, 59.25), which also takes the L1
    # stub into U401.1 (a branch at the via, accepted: one via less; was a via (39.26, 60.395) south of pin 1)
    pcs, l4, x2 = fin["QSPI_BK1_NCS"]
    R["QSPI_BK1_NCS"] = [pcs + [L("L4", l4 + jog["QSPI_BK1_NCS"] + [(27.1, 66.45)]), V(27.1, 66.45),
                                # its L3 row at the via's y (66.45, was 66.6), up x 38.5 and one NE diagonal into the via (no turn-back
                                # across it: L1 leaves south-east)
                                L("L3", [(27.1, 66.45), (38.15, 66.45), (38.5, 66.1), (38.5, 59.845), (39.095, 59.25)]),
                                V(39.095, 59.25), L("L6", [(39.095, 59.25), (38.735, 58.89), "R401.2"])],
                         [L("L1", ["U401.1", (39.095, 59.25)])]]
    pcs, l4, x2 = fin["LCD_G3"]
    R["LCD_G3"] = pcs + [L("L4", l4 + jog["LCD_G3"] + [(26.65, 66.9)]), V(26.65, 66.9),
                         L("L3", [(26.65, 66.9), (42.9, 66.9), (43.25, 67.25), (43.25, 68.75)]), V(43.25, 68.75),
                         L("L1", [(43.25, 68.75), "J701.25"])]
    # ---- PHY_NRST: off the LSE crystal (its old via sat between Y202's pads)
    R["PHY_NRST"] = [out("PHY_NRST", [(31.4, 34.4), (30.9, 34.9), (30.9, 36.25), (30.4, 36.75), (28.45, 36.75), (28.1, 37.1),
                                      (28.1, 40.75), (25.95, 42.9)]) + [V(25.95, 42.9),
                     L("L1", [(25.95, 42.9), (25.49, 42.9), (22.39, 46.0), "R501.1"])],
                     [L("L1", ["R501.1", (22.39, 47.91), (22.65, 48.17), "U501.15"])]]
    return R
