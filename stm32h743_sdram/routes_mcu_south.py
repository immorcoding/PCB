"""MCU south side (the BGA block, SPEC 14 stop 3.4 - 3.6): USART1_TX, the one south ball of this file since stop 7's
remaining buses (issue 22). The LCD, QSPI, RMII, LED, key and I2C4 balls that the BGA block plan fans out south or
west belong to routes_mcu_sw.py, which draws them from the ball to their destinations (and holds the QSPI clock and
IO0 / IO1 routes that used to be here).

    LOCAL_BOARD=<board> D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.routing.busroute.build stm32h743_sdram\\routes_mcu_south.py --fast
    (the driver's route step builds it on the real board after routes_mcu_east.py)

  USART1_TX  L6 straight south to y 50.85 (below the SDRAM's L4 band), a via to L4 and south-east to the debug header
             beside USART1_RX (complete)
"""
import os
from Tools.KiCadDesignTools.routing.fan_plan import plan, lead, ext

BOARD = os.environ.get("LOCAL_BOARD", "stm32h743_sdram.kicad_pcb")
ORIGIN = (100, 100)
GROUP = "mcu_south"
OPEN_ENDS = True
YIELD_NETS = ["GND"]
DRC_IGNORE = {"solder_mask_bridge": "mask webs between fine-pitch pads of the footprints (QFN, FPC), there before this group"}
VIA_LIMIT = 6
VIEWS = [("south", 32.0, 37.5, 47.0, 50.0, 60)]
THIN = 0.1016
NETS_S = ["USART1_TX"]


def V(x, y):
    return ("via", (x, y))


def thin(pieces):
    return [pc if pc[0] == "via" or len(pc) > 2 else (pc[0], pc[1], THIN) for pc in pieces]


def routes(job):
    R = {}
    for num, v in plan()["U201"]["signal"].items():
        if v["net"] == "USART1_TX":
            e = tuple(v["exit"])
            R["USART1_TX"] = ext(lead(num), [(e[0], 50.85)]) + [V(e[0], 50.85), ("L4", [(e[0], 50.85), (60.34, 66.64), "J804.2"])]
    return {n: thin(p) for n, p in R.items()}
