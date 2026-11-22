"""Local circuits of the Ethernet PHY side (stop 7, routing two), the part that can be drawn on the stop-5 layout.
Every net by hand with coordinates (RTE-3); L1 only.

    D:\\KiCad\\bin\\python.exe scripts\\busroute\\build.py stm32h743_sdram\\routes_local_eth.py --fast
    D:\\KiCad\\bin\\python.exe scripts\\busroute\\build.py stm32h743_sdram\\routes_local_eth.py --out stm32h743_sdram\\out\\local_eth

BOARD as routes_local.py (LOCAL_BOARD=<board> builds it on another board).

  VDDCR        pin 6 down and 45 degrees to C507.1; C507.1 to C506.1 through the diagonal gap between the two
               capacitors' ground pads (the two capacitors stand the opposite way round), 0.25 mm there
  PHY_XI       pin 5 down the lane east of R506 (x 23.8) into Y501.1; Y501.1 east and 45 degrees into C508.1
  ETH_LED1_K   R511.1 by a via to L6 and up the lane between J501.12 and the lower mounting hole (x 4.63) into
               J501.10 (through-hole); on L1 the RJ45's own keep-out "Shield-board contact area" (x 4.64-8.94)
               closes that lane
  ETH_LED2_K   R512.1 straight up along the board edge, a step outside the pad, straight into J501.11
  ETH_SHIELD   J501.8 45 degrees down to the lower shield tab, R513.1 into it, the two shield tabs joined along
               x 9.84 (the tabs share the pad number SH: the upper one is reached by its coordinates)

Not drawn here, blocked by the stop-5 placement and pours (the report lists why and the proposed fixes):
ETH_TX_P / N, ETH_RX_P / N, PHY_RBIAS, PHY_XO, PHY_XO_R, ETH_LED1, ETH_LED2, PHY_RXER.
"""
import os

BOARD = os.environ.get("LOCAL_BOARD", "out/probe_east/base/stm32h743_sdram.kicad_pcb")
ORIGIN = (100, 100)
GROUP = "local_eth"
YIELD_NETS = ["GND"]
DRC_IGNORE = {"solder_mask_bridge": "mask webs between fine-pitch pads of the footprints (QFN, FPC), there before this group"}
VIEWS = [("phy", 0.0, 40.0, 32.0, 63.0, 40)]
NETS = ["VDDCR", "PHY_XI", "ETH_LED1_K", "ETH_LED2_K", "ETH_SHIELD"]
XT = 0.254                    # crystal lines: xtal_width (0.254 fixed)


def routes(job):
    R = {}
    R["VDDCR"] = [
        [("L1", ["U501.6", (23.65, 52.95), (24.5, 53.8), "C507.1"])],
        [("L1", ["C507.1", (25.3, 54.92), (25.495, 54.92), (26.0, 55.425), "C506.1"], 0.25)],
    ]
    R["PHY_XI"] = [
        [("L1", ["U501.5", (23.15, 53.35), (23.8, 54.0), (23.8, 58.15), "Y501.1"], XT)],
        [("L1", ["Y501.1", (24.57, 58.35), "C508.1"], XT)],
    ]
    R["ETH_LED1_K"] = [("L1", ["R511.1", (3.99, 59.3)]), ("via", (3.99, 59.3), (0.45, 0.2)),
                       ("L6", [(3.99, 59.3), (4.63, 58.66), (4.63, 46.88), "J501.10"])]
    R["ETH_LED2_K"] = [("L1", ["R512.1", (1.59, 54.5), (1.89, 54.2), "J501.11"])]
    R["ETH_SHIELD"] = [
        [("L1", ["J501.8", (12.38, 57.19), "J501.SH"])],             # J501.SH in the table = the lower tab (9.84, 57.19)
        [("L1", ["R513.1", (8.8875, 58.1425), "J501.SH", (9.84, 41.7)])],   # through the lower tab up to the upper
    ]
    return R
