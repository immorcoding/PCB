"""MCU east side (the BGA block, SPEC 14 stop 3.4 - 3.6): the balls of columns 14-15 that the BGA block plan
(bga_fan.json) fans out east on L6 (dog-bone, L6 run along a ball row to the rule-area edge at x 46). L6 carries no
SDRAM track outside the ball fields, so every lane is clear of the bus as soon as it leaves the MCU's rule area.

    LOCAL_BOARD=<board> D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.routing.busroute.build stm32h743_sdram\\routes_mcu_east.py --fast
    (build.sh route2 builds it on the real board after routes_local_eth.py)

  north   the CAN pair up the strip between the packages (L6, x 46.5 / 46.75) to y 22.0 / 22.4, east to the
          transceiver, a via to L1 into U801.1 / U801.4 (complete)
  south   USART1_RX, lane 0 of the south bundle (L6, x 46.25), below the SDRAM's south bands, a via to L4 at y 51.25
          and south-east on L4 to the debug header (complete). The other nine lanes of that bundle (the LCD, touch and
          I2C4 lines, lanes 1-9 at 0.2286 mm pitch from x 46.48) belong to routes_mcu_sw.py since stop 7's remaining
          buses (issue 22): that file draws them from the ball to the FPC / link resistors.
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
X0, PITCH = 46.25, 0.2286
SOUTH = ["USART1_RX"]          # lane 0; lanes 1-9 are routes_mcu_sw.py's


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
    # ---- USART1_RX: below the SDRAM's L4 band (D16 / D17 east legs at y 47.5 / 47.75): L4 south-east to the header
    # (the line x - y = -5.0 keeps clear of the ground vias at (54.775, 57.825), (55.125, 57.475))
    if "USART1_RX" in E:
        num, pts = south_lane("USART1_RX", 0)
        x = pts[-1][0]
        R["USART1_RX"] = ext(lead(num), pts + [(x, 51.25)]) + [V(x, 51.25), ("L4", [(x, 51.25), (62.88, 67.88), "J804.3"])]
    return {n: thin(p) for n, p in R.items()}
