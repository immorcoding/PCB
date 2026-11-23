"""MCU north-gate nets taken round the west side (stop 7 compose, issue 22): LCD_B6, LCD_B7, LCD_DISP to the FPC J701
(DISP through its resistor R705 first), RMII_TX_EN / RMII_TXD0 to the PHY's north pins, and PHY_NRST re-sited off
the LSE crystal. Local mm (board mm - 100); every net written with coordinates (RTE-3, RTE-4).

    LOCAL_BOARD=<board> D:\\KiCad\\bin\\python.exe scripts\\busroute\\build.py stm32h743_sdram\\routes_mcu_west.py --fast
    (build.sh route2 builds it on the real board after routes_mcu_sw.py)

The north gates have no way south through the ball field (L6: the bottom decoupling pads; L4: the SDRAM lanes on rows
E / L; L3: the SDRAM river south of the field) nor east (the SDRAM bus). West of the gates the SAI lanes (L1 / L3 /
L6, x 31-34.25) leave only L4 between y 25.2 and 27.5 (north of FMC_A1's river at 27.75). So:
  L3   from each gate north, nested 45-degree turns west at rows y 28.75 .. 27.75 (B6 southmost), then north into
       a staircase of vias (34.75, 27.32) .. (36.55, 25.64) (0.45 east, 0.42 north each)
  L4   west from each via at its own row (pitch 0.42), round the corner into the corridor west of the SDRAM rivers
       (lanes x 29.25 .. 28.34, pitch 0.2286, between the crystal ground vias), down the corridor
  TX   TXD0 / TX_EN turn west at y 41.5 / 41.95 to vias (25.45, 41.5) / (26.1, 41.95), L1 diagonals parallel to
       PHY_NRST's into pins 17 / 16 from the north (TX_EN steps past R501.1)
  LCD  B6 / B7 / DISP jog south-west past the RMII vias to x 27.6 .. 27.14, down west of USER_KEY to the flash's
       level; B6 / B7 turn east at y 59.35 / 59.58 under the QSPI wall's south end (LCD_B5 at y 59.0) and drop into
       FPC vias on their pins' x (N row 68.2 / S row 68.75); DISP goes on down to R705.1 (via west of it), and from
       R705.1 by a via south of it and L4 east at y 67.75 to its FPC via (35.75, 68.2)
  NRST PHY_NRST: L6 west to x 31.4, south past the LSE crystal's east side (x 30.9), west between the two crystals
       (y 36.75, under CODEC_NRST's L3 run), down x 28.1 west of the HSE crystal, SW to a via (25.95, 42.9), L1 as
       before into R501.1 and pin 15
"""
import os
from fan_leads import plan, lead, ext

BOARD = os.environ.get("LOCAL_BOARD", "stm32h743_sdram.kicad_pcb")
ORIGIN = (100, 100)
GROUP = "mcu_w"
OPEN_ENDS = False
YIELD_NETS = ["GND"]
VIA_LIMIT = 8
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
# line -> (L3 gate lane x, L3 row y, staircase via, L4 row y = via y, corridor lane x)
NORTH = ["LCD_B6", "LCD_B7", "LCD_DISP", "RMII_TX_EN", "RMII_TXD0"]
GX = {"LCD_B6": 37.4, "LCD_B7": 38.05, "LCD_DISP": 38.7, "RMII_TX_EN": 40.0, "RMII_TXD0": 40.65}


def north(net):
    k = NORTH.index(net)
    gx = GX[net]
    yr = r4(28.75 - 0.25 * k)                       # L3 row
    vx, vy = r4(34.75 + 0.45 * k), r4(27.32 - 0.42 * k)
    lx = r4(29.25 - P * k)                          # corridor lane
    l3 = [(gx, yr + C), (gx - C, yr), (vx + C, yr), (vx, yr - C), (vx, vy)]
    l4 = [(vx, vy), (lx + C, vy), (lx, vy + C)]
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
    # ---- LCD: jog south-west below the TX turns (starts staggered so the diagonals keep the pitch), down x 27.6 ..
    jog = {"LCD_DISP": 42.4, "LCD_B7": r4(42.4 + 0.095), "LCD_B6": r4(42.4 + 0.19)}
    fin = {}
    for net in ("LCD_B6", "LCD_B7", "LCD_DISP"):
        pcs, l4, lx = north(net)
        x2 = r4(lx - 1.65)
        fin[net] = (pcs, l4 + [(lx, jog[net]), (x2, jog[net] + 1.65)], x2)
    # B6 / B7: east under the QSPI wall's south end, drop into their FPC vias
    for net, row, xp, yv, pin in (("LCD_B6", 59.35, 37.75, 68.2, 14), ("LCD_B7", r4(59.35 + P), 37.25, 68.75, 13)):
        pcs, l4, x2 = fin[net]
        R[net] = pcs + [L("L4", l4 + [(x2, row - C), (x2 + C, row), (xp - C, row), (xp, row + C), (xp, yv)]), V(xp, yv),
                        L("L1", [(xp, yv), "J701.%d" % pin])]
    # DISP: on down to a via west of R705.1, then R705.1 -> via south of it -> L4 east -> FPC via -> pin 10
    pcs, l4, x2 = fin["LCD_DISP"]
    R["LCD_DISP"] = [pcs + [L("L4", l4 + [(x2, r4(67.51 - (x2 - 26.9))), (26.9, 67.51)]), V(26.9, 67.51),
                            L("L1", [(26.9, 67.51), "R705.1"])],
                     [L("L1", ["R705.1", (27.8, 68.25)]), V(27.8, 68.25),
                      L("L4", [(27.8, 68.25), (28.3, 67.75), (35.3, 67.75), (35.75, 68.2)]), V(35.75, 68.2),
                      L("L1", [(35.75, 68.2), "J701.10"])]]
    # ---- PHY_NRST: off the LSE crystal (its old via sat between Y202's pads)
    R["PHY_NRST"] = [out("PHY_NRST", [(31.4, 34.4), (30.9, 34.9), (30.9, 36.25), (30.4, 36.75), (28.45, 36.75), (28.1, 37.1),
                                      (28.1, 40.75), (25.95, 42.9)]) + [V(25.95, 42.9),
                     L("L1", [(25.95, 42.9), (25.49, 42.9), (22.39, 46.0), "R501.1"])],
                     [L("L1", ["R501.1", (22.39, 47.91), (22.65, 48.17), "U501.15"])]]
    return R
