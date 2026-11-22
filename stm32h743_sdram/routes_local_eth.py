"""Local circuits of the Ethernet PHY side (stop 7, routing two): the two 100 ohm pairs, the PHY's crystal, bias, LED
and strap nets, the RJ45's LED cathodes and shield. Every net by hand with coordinates (RTE-3).

    D:\\KiCad\\bin\\python.exe scripts\\busroute\\build.py stm32h743_sdram\\routes_local_eth.py --fast
    D:\\KiCad\\bin\\python.exe scripts\\busroute\\build.py stm32h743_sdram\\routes_local_eth.py --out stm32h743_sdram\\out\\local_eth

BOARD as routes_local.py (LOCAL_BOARD=<board> builds it on another board; build.sh route2 builds it on the real one).

The pairs (SPEC 6 / 9: L1 only, 0.1194 mm wide, 0.2032 mm gap, no via, intra-pair difference <= 1.27 mm). The
LAN8742A drives each pair with N on the north side of its west face (pins 20 / 22 above 21 / 23), and the RJ45
has P on the far side (pin 1 west of and above pin 2, pin 3 above pin 6), so on one layer a pair can only arrive
heading north. TX: west from the PHY, through its terminations, up the diagonal and between RJ45 pins 2 and 4;
N ends in pin 2, P runs up the column gap between the two pin rows into pin 1. RX: down from the PHY through its
terminations, west under pin 8 and up the column gap: N into pin 6, P on to pin 3. Each 49.9 ohm termination is IN
its line (LAN8742A p.55 Figure 3-23; the line passes through its signal pad, junctions only at pad centres): the
lines keep the PHY's 0.5 mm pitch through the resistors and close to the 0.3226 mm pair pitch after them. P is the
longer line of both pairs by the RJ45's pin geometry (it goes round pin 2, and pin 3 is 3.81 mm beyond pin 6): N
gets an arc serpentine on its outer side (RTE-7; TUNING below).
  PHY_XO / XO_R  pin 4 straight down into R506; R506 down the west side of the crystal into C509 and on to Y501.3
  PHY_XI         pin 5 down the lane east of R506 (x 23.8) into Y501.1; Y501.1 east and 45 degrees into C508.1
  VDDCR          pin 6 down and 45 degrees to C507.1; C507.1 to C506.1 between the two capacitors' ground pads, 0.25 mm
  PHY_RBIAS      pin 24 straight down into a via, L6 into R505 (bottom) under the PHY's south-west corner
  PHY_RXER       pin 10 east into a via (between the MCU-bound lanes of pins 8 / 9 / 11), L6 into R502 (bottom)
  ETH_LED1/2     the PHY's pins 3 / 2 straight down into a via each, L4 to the RJ45's LED pins 9 / 12 (through-hole):
                 LED1 north along x 17.1 outside the pin rows, west at y 40.1 north of the upper shield tab;
                 LED2 west at y 55.5 under the pin rows, north of the lower mounting hole at y 53.1, 45 degrees
                 down and straight into the pin. On L1 the pairs
                 and on L6 the VDDA region close both ways (SPEC 6 puts no other net on L4 here). R504 (the LED2 /
                 nINTSEL pull-down) sits at the LED pin, off J501.12 on L1
  ETH_LED1_K     J501.10 straight north on L1 into R511 (moved above the RJ45)
  ETH_LED2_K     R512.1 straight up along the board edge, a step outside the pad, straight into J501.11
  ETH_SHIELD     J501.8 on L6 45 degrees down to the lower shield tab; R513.1 into it and the two tabs joined along
                 x 9.84 on L1 (the tabs share the pad number SH: the upper one is reached by its coordinates)
"""
import os

BOARD = os.environ.get("LOCAL_BOARD", "out/probe_east/base/stm32h743_sdram.kicad_pcb")
ORIGIN = (100, 100)
GROUP = "local_eth"
YIELD_NETS = ["GND"]
DRC_IGNORE = {"solder_mask_bridge": "mask webs between fine-pitch pads of the footprints (QFN, FPC), there before this group"}
VIEWS = [("phy", 10.0, 43.0, 31.0, 62.0, 45), ("rj45", 0.0, 38.0, 23.0, 62.0, 30)]
NETS = ["VDDCR", "PHY_XI", "ETH_LED1_K", "ETH_LED2_K", "ETH_SHIELD",
        "ETH_TX_P", "ETH_TX_N", "ETH_RX_P", "ETH_RX_N", "PHY_XO", "PHY_XO_R", "ETH_LED1", "ETH_LED2", "PHY_RBIAS", "PHY_RXER"]
GROUPS = {"tx": ["ETH_TX_P", "ETH_TX_N"], "rx": ["ETH_RX_P", "ETH_RX_N"],
          "other": ["VDDCR", "PHY_XI", "PHY_XO", "PHY_XO_R", "PHY_RBIAS", "PHY_RXER", "ETH_LED1", "ETH_LED2", "ETH_LED1_K", "ETH_LED2_K", "ETH_SHIELD"]}
VIA_LIMIT = 1
XT = 0.254                    # crystal lines: xtal_width (0.254 fixed)
# intra-pair difference: each pair ends within 0.6 mm (aimed at 0.3), well inside the rule's 1.27 (eth_skew)
TUNING = {"groups": {"tx": {"nets": ["ETH_TX_P", "ETH_TX_N"], "spread": 0.6},
                     "rx": {"nets": ["ETH_RX_P", "ETH_RX_N"], "spread": 0.6}},
          "margin": 0.3, "radius": 0.25, "amp": 0.5, "amp_max": 1.6, "pitch": {"default": 0.3},
          "end": 0.35, "clr": 0.19, "area_gap": 0.127, "keep": 0.5}


def V(x, y):
    return ("via", (x, y), (0.45, 0.2))


def pairs(job):
    R = {}
    # TX: N through R508 (upright north of the line) and the straight diagonal into pin 2; P through R507 (upright
    # south of it), up to the pair pitch, the diagonal beside N, west under pin 2 (y 47.3: P's corner into the column
    # gap stays clear of N's diagonal, which DRC's pair-gap check would otherwise read as coupled at 1.6 mm), up the
    # gap, 45 degrees into pin 1. Every bend lies outside the pads (DRC measures a bend inside a pad shorter)
    R["ETH_TX_N"] = [[("L1", ["U501.20", "R508.2"])],
                     [("L1", ["R508.2", "J501.2"])]]
    R["ETH_TX_P"] = [[("L1", ["U501.21", "R507.2"])],
                     [("L1", ["R507.2", (18.2, 49.2462), (16.2538, 47.3), (14.6, 47.3), (14.25, 46.95), (14.25, 46.11), "J501.1"])]]
    # RX: down through R510 (N, pad west) and R509 (P, pad east), west under pin 8, up the column gap
    R["ETH_RX_N"] = [[("L1", ["U501.22", (19.8, 50.75), (19.1, 51.45), "R510.2"])],
                     [("L1", ["R510.2", (19.1, 54.6), (18.7, 55.0), (14.9726, 55.0), (14.5726, 54.6), (14.5726, 51.6474), (14.87, 51.35), "J501.6"])]]
    R["ETH_RX_P"] = [[("L1", ["U501.23", (20.0, 51.25), (19.6, 51.65), "R509.2"])],
                     [("L1", ["R509.2", (19.6, 54.5562), (18.8336, 55.3226), (14.839, 55.3226), (14.25, 54.7336), (14.25, 48.65), "J501.3"])]]
    # serpentine sites on N, humps on the side away from P (right of p0 -> p1)
    job.slot("ETH_TX_N", "L1", (18.4, 48.99), (16.4, 46.99), side="R")
    job.slot("ETH_RX_N", "L1", (18.7, 55.0), (14.9726, 55.0), side="R")
    return R


def phy(job):
    R = {}
    R["PHY_XO"] = [("L1", ["U501.4", "R506.1"], XT)]
    R["PHY_XO_R"] = [[("L1", ["R506.2", (19.9, 57.86), "C509.1"], XT)],
                     [("L1", ["C509.1", (20.6, 60.05), "Y501.3"], XT)]]
    R["PHY_XI"] = [
        [("L1", ["U501.5", (23.15, 53.35), (23.8, 54.0), (23.8, 58.15), "Y501.1"], XT)],
        [("L1", ["Y501.1", (24.57, 58.35), "C508.1"], XT)],
    ]
    R["VDDCR"] = [
        [("L1", ["U501.6", (23.65, 52.95), (24.5, 53.8), "C507.1"])],
        [("L1", ["C507.1", (25.25, 54.87), (25.25, 55.325), "C506.1"], 0.25)],
    ]
    R["PHY_RBIAS"] = [("L1", ["U501.24", (20.4625, 52.4)]), V(20.4625, 52.4), ("L6", [(20.4625, 52.4), "R505.1"])]
    R["PHY_RXER"] = [("L1", ["U501.10", (26.3, 50.25)]), V(26.3, 50.25), ("L6", [(26.3, 50.25), "R502.1"])]
    return R


def leds(job):
    R = {}
    R["ETH_LED1"] = [("L1", ["U501.3", (22.15, 53.4)]), V(22.15, 53.4),
                     ("L4", [(22.15, 53.4), (21.65, 53.9), (17.6, 53.9), (17.1, 53.4), (17.1, 43.0), (14.2, 40.1), (2.4, 40.1),
                             (1.89, 40.61), "J501.9"])]
    R["ETH_LED2"] = [
        [("L1", ["U501.2", (21.65, 54.45)]), V(21.65, 54.45),
         ("L4", [(21.65, 54.45), (20.6, 55.5), (11.8, 55.5), (9.4, 53.1), (4.95, 53.1), (3.41, 54.64), "J501.12"])],
        [("L1", ["J501.12", (3.41, 59.82), "R504.1"])],
    ]
    R["ETH_LED1_K"] = [("L1", ["J501.10", "R511.1"])]
    R["ETH_LED2_K"] = [("L1", ["R512.1", (1.59, 54.5), (1.89, 54.2), "J501.11"])]
    R["ETH_SHIELD"] = [
        [("L6", ["J501.8", (12.38, 57.19), "J501.SH"])],                 # J501.SH in the table = the lower tab (9.84, 57.19)
        [("L1", ["R513.1", (8.8875, 58.1425), "J501.SH", (9.84, 41.7)])],   # through the lower tab up to the upper
    ]
    return R


def routes(job):
    R = {}
    for part in (pairs, phy, leds):
        R.update(part(job))
    return R
