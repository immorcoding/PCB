"""MCU east side (the BGA block, SPEC 14 stop 3.4 - 3.6): the balls of columns 14-15 that the BGA block plan
(bga_fan.json) fans out east on L6 (dog-bone, L6 run along a ball row to the rule-area edge at x 46). L6 carries no
SDRAM track outside the ball fields, so every lane is clear of the bus as soon as it leaves the MCU's rule area.

    LOCAL_BOARD=<board> D:\\KiCad\\bin\\python.exe scripts\\busroute\\build.py stm32h743_sdram\\routes_mcu_east.py --fast
    (build.sh route2 builds it on the real board after routes_local_eth.py)

  north   the CAN pair up the strip between the packages (L6, x 46.5 / 46.75) to y 22.0 / 22.4, east to the
          transceiver, a via to L1 into U801.1 / U801.4 (complete)
  south   the other ten lanes turn south in the strip as one bundle (L6, 0.2286 mm pitch from x 46.25, the
          outermost 0.44 mm west of the SDCLK_R via at (48.75, 36.675)); USART1_RX goes on below the SDRAM's south
          bands, a via to L4 at y 51.25 and south-east on L4 to the debug header (complete); the LCD, touch and
          I2C4 lanes end at GATES at y = GATE_S (open ends: their way to the FPC / link resistors is the next step,
          see the report)
"""
import os
from fan_leads import plan, lead, ext

BOARD = os.environ.get("LOCAL_BOARD", "stm32h743_sdram.kicad_pcb")
ORIGIN = (100, 100)
GROUP = "mcu_east"
OPEN_ENDS = True
YIELD_NETS = ["GND"]
DRC_IGNORE = {"solder_mask_bridge": "mask webs between fine-pitch pads of the footprints (QFN, FPC), there before this group"}
VIA_LIMIT = 6
VIEWS = [("east", 42.5, 30.5, 52.0, 50.0, 60), ("north", 43.0, 12.0, 66.0, 34.0, 30)]
THIN = 0.1016
GATE_S = 46.8
X0, PITCH = 46.25, 0.2286
SOUTH = ["USART1_RX", "TP_RST", "I2C4_SDA", "TP_INT", "LCD_HSYNC", "LCD_CLK", "LCD_B3", "LCD_G6", "LCD_B4", "LCD_R5"]   # west -> east


def V(x, y):
    return ("via", (x, y))


def thin(pieces):
    return [pc if pc[0] == "via" or len(pc) > 2 else (pc[0], pc[1], THIN) for pc in pieces]


def by_net():
    return {v["net"]: num for num, v in plan()["U201"]["signal"].items() if v["side"] == "E"}


def south_lane(net, k):
    """Points after the exit (46.0, y): a diagonal to x_k and straight south."""
    num = by_net()[net]
    y = plan()["U201"]["signal"][num]["exit"][1]
    xk = round(X0 + PITCH * k, 4)
    return num, [(xk, round(y + xk - 46.0, 4))]


def routes(job):
    R = {}
    E = by_net()
    # ---- CAN: north up the strip, east along y 22.0 / 22.4, via to L1 at the transceiver
    if "FDCAN1_TX" in E:
        R["FDCAN1_TX"] = ext(lead(E["FDCAN1_TX"]), [(46.5, 32.6), (46.5, 22.4), (46.9, 22.0), (62.1, 22.0), (62.6, 21.5), (62.6, 15.095)]) + [
            V(62.6, 15.095), ("L1", [(62.6, 15.095), "U801.1"])]
    if "FDCAN1_RX" in E:
        R["FDCAN1_RX"] = ext(lead(E["FDCAN1_RX"]), [(46.75, 33.0), (46.75, 22.8), (47.15, 22.4), (63.15, 22.4), (63.6, 21.95), (63.6, 20.0)]) + [
            V(63.6, 20.0), ("L1", [(63.6, 20.0), (63.6, 19.45), "U801.4"])]
    # ---- the south bundle
    for k, net in enumerate(SOUTH):
        if net not in E:
            continue
        num, pts = south_lane(net, k)
        x = pts[-1][0]
        if net == "USART1_RX":
            # below the SDRAM's L4 band (D16 / D17 east legs at y 47.5 / 47.75): L4 south-east to the header
            # (the line x - y = -5.0 keeps clear of the ground vias at (47.525, 51.575), (54.775, 57.825), (55.125, 57.475))
            R[net] = ext(lead(num), pts + [(x, 51.25)]) + [V(x, 51.25), ("L4", [(x, 51.25), (62.88, 67.88), "J804.3"])]
        else:
            R[net] = ext(lead(num), pts + [(x, GATE_S)])
    return {n: thin(p) for n, p in R.items()}
