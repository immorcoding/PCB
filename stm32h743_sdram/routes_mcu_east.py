"""MCU east side (stop 7 part 2): the balls of column 14-15 between the SDRAM's east escapes. Written by hand
(coordinates from the board); no autorouter.

    D:\KiCad\bin\python.exe scripts\busroute\build.py stm32h743_sdram\routes_mcu_east.py --fast
    LOCAL_BOARD=<board> ... (build.sh route2 builds it on the real board, before routes_mcu_south.py)

On every layer the strip between the MCU and the SDRAM is closed by the bus: L1 by the lanes D3 / D24 / SDCLK /
D20 / BA0 / D13 / D14 leaving east and turning south at x 49-50.5, L4 by D26 / D27 / D25 / D31 / SDCKE0 / A4 / A5 /
D10 / D15, L6 by D23 / D22 / D21 / D19 / D18 (turning north at x 47.25-48.25) and BA1 / A12 / D1 / D0. The ways out:
  north   L6 west of D23's north leg (x 47.25): the CAN pair, from vias just south of D3's L1 lane
  south   L1 pocket between D24 and SDCLK -> L4 pocket between SDCKE0 and A4 -> past the SDCLK_R via (its return
          via moved) -> L4 pocket south of SDCLK_R -> up to the L1 pocket above the SDRAM's south bands -> down
          into S4 (L4 between D17 and D15) -> below D17's leg to L1: LCD_B3 (4 vias); S4 is shared with
          routes_mcu_south.py and holds no further lane
"""
import os

BOARD = os.environ.get("LOCAL_BOARD", "stm32h743_sdram.kicad_pcb")
ORIGIN = (100, 100)
GROUP = "mcu_east"
YIELD_NETS = ["GND"]
DRC_IGNORE = {"solder_mask_bridge": "mask webs between fine-pitch pads of the footprints (QFN, FPC), there before this group"}
VIA_LIMIT = 6
VIEWS = [("east", 42.5, 30.5, 51.0, 49.0, 90), ("north", 43.0, 12.0, 66.0, 34.0, 30)]
THIN = 0.1016


def V(x, y):
    return ("via", (x, y))


def thin(pieces):
    return [pc if pc[0] == "via" or len(pc) > 2 else (pc[0], pc[1], THIN) for pc in pieces]


def routes(job):
    R = {}
    # ---- CAN: south of D3's L1 lane to vias, L6 north west of the SDRAM's L6 river, east at y 22, up to the
    # transceiver's west pins (TX pin 1 from the west, RX pin 4 from the south past the +5V_CAN strip)
    R["FDCAN1_TX"] = [("L1", ["U201.B15", (44.875, 33.425)]), V(44.875, 33.425),
                      ("L6", [(44.875, 33.425), (44.875, 22.4), (45.275, 22.0), (62.1, 22.0), (62.6, 21.5), (62.6, 15.095)]), V(62.6, 15.095),
                      ("L1", [(62.6, 15.095), "U801.1"])]
    R["FDCAN1_RX"] = [("L1", ["U201.C15", (45.425, 33.75), (45.75, 33.425)]), V(45.75, 33.425),
                      ("L6", [(45.75, 33.425), (45.75, 22.8), (46.15, 22.4), (63.15, 22.4), (63.6, 21.95), (63.6, 20.0)]), V(63.6, 20.0),
                      ("L1", [(63.6, 20.0), (63.6, 19.45), "U801.4"])]
    # ---- LCD_B3 (F15): see the module text
    R["LCD_B3"] = [("L1", ["U201.F15", (45.2, 35.7), (45.525, 36.025)]), V(45.525, 36.025),
                   ("L4", [(45.525, 36.025), (45.85, 36.35), (47.7, 36.35), (48.05, 36.7), (48.05, 41.45), (48.5, 41.9)]), V(48.5, 41.9),
                   ("L1", [(48.5, 41.9), (45.6, 41.9)]), V(45.6, 41.9),
                   ("L4", [(45.6, 41.9), (45.9, 42.2), (45.9, 43.75), (49.05, 46.9)]), V(49.05, 46.9),
                   ("L1", [(49.05, 46.9), (45.6, 50.35), (45.6, 61.0), (39.25, 67.35), "J701.17"])]
    return {n: thin(p) for n, p in R.items()}
