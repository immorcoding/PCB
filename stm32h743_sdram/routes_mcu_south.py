"""MCU south and south-west sides (the BGA block, SPEC 14 stop 3.4 - 3.6): the balls the BGA block plan (bga_fan.json)
fans out south (L4 / L6 runs along ball columns to the rule-area edge at y 43) or west below the crystals (L6 / L4 at
x 34). Outside the MCU's rule area L6 carries no SDRAM track, L4 none west of A11 (x 40) and none below y 48.4.

    LOCAL_BOARD=<board> D:\\KiCad\\bin\\python.exe scripts\\busroute\\build.py stm32h743_sdram\\routes_mcu_south.py --fast
    (build.sh route2 builds it on the real board after routes_mcu_east.py)

  USART1_TX  L6 straight south to y 50.85 (below the SDRAM's L4 band), a via to L4 and south-east to the debug header
             beside USART1_RX (complete)
  others     straight on to a GATE below the SDRAM's south bands (y = GATE_S; L4 lanes clear of D16 / D17 and A11),
             west exits to x = GATE_W (open ends; the way to the FPC, the QSPI flash, the PHY, the link resistors and
             the user LEDs / key is the next step, see the report)
Balls the plan could not place (no copper here): see the plan's unallocated list.
"""
import os
from fan_leads import plan, lead, ext

BOARD = os.environ.get("LOCAL_BOARD", "stm32h743_sdram.kicad_pcb")
ORIGIN = (100, 100)
GROUP = "mcu_south"
OPEN_ENDS = True
YIELD_NETS = ["GND"]
DRC_IGNORE = {"solder_mask_bridge": "mask webs between fine-pitch pads of the footprints (QFN, FPC), there before this group"}
VIA_LIMIT = 6
VIEWS = [("south", 32.0, 37.5, 47.0, 50.0, 60)]
THIN = 0.1016
GATE_S, GATE_W = 48.4, 32.8
NETS_ES = ["LCD_G2", "LCD_B5", "ETH_MDC", "LCD_VSYNC", "QSPI_CLK", "LCD_G4", "LCD_R4", "LCD_R3", "LED2", "LCD_G5",
           "I2C4_SCL", "USART1_TX", "USER_KEY", "QSPI_BK1_IO2", "LCD_DE", "QSPI_BK1_IO1"]


def V(x, y):
    return ("via", (x, y))


def thin(pieces):
    return [pc if pc[0] == "via" or len(pc) > 2 else (pc[0], pc[1], THIN) for pc in pieces]


def routes(job):
    R = {}
    for num, v in plan()["U201"]["signal"].items():
        net = v["net"]
        if net not in NETS_ES:
            continue
        e = tuple(v["exit"])
        if net == "USART1_TX":
            R[net] = ext(lead(num), [(e[0], 50.85)]) + [V(e[0], 50.85), ("L4", [(e[0], 50.85), (60.34, 66.64), "J804.2"])]
        elif net == "LCD_R4":           # passes the VDDA bead FB201 (pad edge x 37.875): gate just outside the area
            R[net] = ext(lead(num), [(e[0], 43.3)])
        elif v["side"] == "S":
            R[net] = ext(lead(num), [(e[0], GATE_S)])
        elif v["side"] == "W":
            R[net] = ext(lead(num), [(GATE_W, e[1])])
    return {n: thin(p) for n, p in R.items()}
