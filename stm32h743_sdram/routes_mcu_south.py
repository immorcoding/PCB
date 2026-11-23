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
           "I2C4_SCL", "USART1_TX", "USER_KEY", "QSPI_BK1_IO2", "LCD_DE", "QSPI_BK1_IO1", "QSPI_BK1_IO0", "QSPI_BK1_IO3",
           "RMII_REF_CLK", "ETH_MDIO", "RMII_CRS_DV", "RMII_RXD0", "RMII_RXD1", "LCD_R6", "LCD_R7", "LED1"]
# complete routes (after the lead): QSPI clock and IO0 / IO1 down L4 to the flash, the last stretch on L1 into its pins
DONE = {
    "QSPI_CLK": lambda x: [(x, 55.4)] + [V(x, 55.4), ("L1", [(x, 55.4), (34.215, 55.4), "U401.6"])],
    "QSPI_BK1_IO0": lambda x: [(x, 54.6)] + [V(x, 54.6), ("L1", [(x, 54.6), (32.6, 54.6), (32.25, 54.95), "U401.5"])],
    "QSPI_BK1_IO1": lambda x: [(x, 55.6), (x + 0.4, 56.0), (40.6, 56.0), (41.0, 56.4), (41.0, 58.635)] + [V(41.0, 58.635), ("L1", [(41.0, 58.635), "U401.2"])],
}


def V(x, y):
    return ("via", (x, y))


def thin(pieces):
    return [pc if pc[0] == "via" or len(pc) > 2 else (pc[0], pc[1], THIN) for pc in pieces]


# RMII receive side, REF_CLK and the management pair to the PHY (U501, west): the west exits run on west below the
# crystals, turn south at x 27.9-29.25 (west of the VDDA filter) and come up to L1 in a staggered via row (each lane
# 0.45 mm from its northern neighbour's via); RXD0 / RXD1 leave south and come up east of the QSPI lanes. On L1 the six
# lanes run west at 0.45 mm pitch and turn into the PHY pins as before (stop 7 tails); MDIO also takes its pull-up R503.
RMII = {   # net: (turn x for west exits | None, via, L1 points after the via)
    "RMII_REF_CLK": (27.9, (27.9, 46.1), [(25.6, 46.1), (23.1, 48.6), "U501.14"]),
    "ETH_MDC": (28.35, (28.35, 46.55), [(25.65, 46.55), (23.6, 48.6), "U501.13"]),
    "ETH_MDIO": (28.8, (28.8, 47.0), [(27.8, 47.0), (25.6, 49.2), "R503.2"]),
    "RMII_CRS_DV": (29.25, (29.25, 47.45), [(28.4, 47.45), (26.05, 49.8), "U501.11"]),
    "RMII_RXD0": (None, (38.7, 47.9), [(29.25, 47.9), (25.95, 51.2), "U501.8"]),
    "RMII_RXD1": (None, (39.15, 48.35), [(29.25, 48.35), (25.8, 51.8), "U501.7"]),
}


RMII_ON = False      # drafted, not built: the tails into the PHY and two ground vias (C226.2, Y201.2) need rework


def rmii(num, v):
    net = v["net"]
    turn, via, tail = RMII[net]
    e = tuple(v["exit"])
    if v["side"] == "W":
        pts = [(turn + 0.4, e[1]), (turn, e[1] + 0.4), (turn, via[1])]
    elif net == "RMII_RXD1":
        pts = [(e[0], 46.8), (via[0], 46.8 + via[0] - e[0]), via]
    else:
        pts = [via]
    out = ext(lead(num), pts) + [V(*via), ("L1", [via] + tail)]
    if net == "ETH_MDIO":
        return [out, [("L1", ["R503.2", "U501.12"])]]
    return out


def routes(job):
    R = {}
    for num, v in plan()["U201"]["signal"].items():
        net = v["net"]
        if net not in NETS_ES:
            continue
        e = tuple(v["exit"])
        if net in RMII and RMII_ON and ((v["side"] == "W") == (RMII[net][0] is not None)):
            R[net] = rmii(num, v)
            continue
        if net == "USART1_TX":
            R[net] = ext(lead(num), [(e[0], 50.85)]) + [V(e[0], 50.85), ("L4", [(e[0], 50.85), (60.34, 66.64), "J804.2"])]
        elif net in DONE and v["side"] == "S" and v["layer"] == "L4":
            tail = DONE[net](e[0])
            k = next(i for i, t in enumerate(tail) if isinstance(t, tuple) and t[0] == "via")
            R[net] = ext(lead(num), tail[:k]) + tail[k:]
        elif v["side"] == "S":
            R[net] = ext(lead(num), [(e[0], GATE_S)])
        elif v["side"] == "W":
            R[net] = ext(lead(num), [(GATE_W, e[1])])
    return {n: (thin(p) if not isinstance(p[0], list) else [thin(c) for c in p]) for n, p in R.items()}
