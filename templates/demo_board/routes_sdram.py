r"""SDRAM bus of the demo board: one byte lane (FMC_D0-D7, FMC_NBL0), A0-A3, BA0 and the clock through R1. Every net
is written by hand (PATHS: ball to ball, local mm; MCU centre (14, 14), SDRAM centre (29, 16) turned 180 degrees).

    D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.build templates/demo_board route
    D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.routing.busroute.build templates\demo_board\routes_sdram.py --fast
    D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.routing.busroute.build templates\demo_board\routes_sdram.py --tuning-budget

Layers (SPEC 6, 9): L1 the ball escapes and the nets that need no layer change (NBL0, BA0, the clock's MCU side);
L3 the eight data bits; L4 the four address lines and the clock's SDRAM side. Byte lane on L3, data bits swapped on
the SDRAM side (swap.csv) so that no two L3 lines cross: going round the MCU clockwise the data balls are D2, D3
(north east), D1, D0 (east), D7, D6, D4, D5 (south), and the SDRAM's lane balls seen from the west, north to south,
take them in that order. D2, D3, D1, D0 leave north along the MCU's east side into a band above the packages (its
depth sets their length) and come down between the packages; D7, D6, D4, D5 leave south, run east below the MCU and
come up between the packages. Each data line has two vias (one per BGA, 0.30 / 0.15 in the rule areas).
Length tuning (RTE-2, RTE-7): the lane's target is its longest natural line - spread + margin; D3 (band, humps
south), D2 (band, humps north), NBL0 (L1 north of the MCU, humps north) and D7 (between the packages, humps west)
have serpentine sites. The address lines meet the window round the clock (length_groups.json) by their routes.
"""
import os

BOARD = os.environ.get("BOARD", "demo_board.kicad_pcb")
ORIGIN = (100, 100)
GROUP = "sdram"
REF = ["FMC_SDCLK", "FMC_SDCLK_R"]
VIA_LIMIT = 3                 # the byte lane and the clock (rule sdram_via_max)
VIA_TARGET = 2
LEN_MAX = 30
LANE = ["FMC_D%d" % i for i in range(8)] + ["FMC_NBL0"]
ADDR = ["FMC_A0", "FMC_A1", "FMC_A2", "FMC_A3", "FMC_BA0"]
GROUPS = {"lane0": LANE, "addr": ADDR, "clock": REF}
NETS = LANE + ADDR + REF
YIELD_NETS = ["GND"]
DRC_IGNORE = {}
ADDR_WINDOW = 10              # SPEC 7.2: every address line within 10 mm of the clock (both pieces summed)
TUNING = {"groups": {"lane0": {"nets": LANE, "spread": 0.9},
                     "addr": {"nets": ADDR, "ref": REF, "lo": -ADDR_WINDOW, "hi": ADDR_WINDOW}},
          "margin": 0.3, "radius": 0.25, "amp": 0.5, "amp_max": 2.0, "pitch": {"default": 0.3, "FMC_SDCLK": 0.5, "FMC_SDCLK_R": 0.5},
          "end": 0.35, "clr": 0.19, "area_gap": 0.127, "keep": 0.7}
if os.environ.get("NOTUNE"):  # the natural routes
    TUNING = None
VIEWS = [("all", 0.0, 0.0, 40.0, 30.0, 30), ("between", 15.0, 1.0, 33.0, 23.0, 60)]

PATHS = {
    # ---- byte lane, north group: L3 up the MCU's east side into the band, down between the packages
    "FMC_D2": [("L1", ["U1.B12", (16.925, 9.775)]), ("via", (16.925, 9.775)),
               ("L3", [(16.925, 9.775), (16.925, 3.225), (17.325, 2.825), (21.4, 2.825), (21.8, 3.225), (21.8, 9.2), (22.2, 9.6),
                       (25.8, 9.6), (26.2, 10.0)]), ("via", (26.2, 10.0)),
               ("L1", [(26.2, 10.0), "U2.R8"])],
    "FMC_D3": [("L1", ["U1.C12", (16.925, 10.425)]), ("via", (16.925, 10.425)),
               ("L3", [(16.925, 10.425), (17.25, 10.1), (17.25, 3.7), (17.65, 3.3), (21.0, 3.3), (21.4, 3.7), (21.4, 9.6), (21.8, 10.0),
                       (25.4, 10.0)]), ("via", (25.4, 10.0)),
               ("L1", [(25.4, 10.0), "U2.R9"])],
    "FMC_D1": [("L1", ["U1.L14", (18.225, 15.625)]), ("via", (18.225, 15.625)),
               ("L3", [(18.225, 15.625), (18.55, 15.3), (18.55, 5.52), (18.95, 5.12), (20.6, 5.12), (21.0, 5.52), (21.0, 10.4), (21.4, 10.8),
                       (25.4, 10.8)]), ("via", (25.4, 10.8)),
               ("L1", [(25.4, 10.8), "U2.P9"])],
    "FMC_D0": [("L1", ["U1.M14", (18.225, 16.275)]), ("via", (18.225, 16.275)),
               ("L3", [(18.225, 16.275), (19.2, 15.3), (19.2, 6.37), (19.6, 5.97), (20.2, 5.97), (20.6, 6.37), (20.6, 10.8), (21.0, 11.2),
                       (25.8, 11.2), (26.2, 11.6)]), ("via", (26.2, 11.6)),
               ("L1", [(26.2, 11.6), "U2.N8"])],
    # ---- byte lane, south group: L3 down from the MCU's south balls, east below it, up between the packages
    "FMC_D7": [("L1", ["U1.R9", (14.975, 18.875)]), ("via", (14.975, 18.875)),
               ("L3", [(14.975, 18.875), (14.975, 20.2), (15.375, 20.6), (20.6, 20.6), (21.0, 20.2), (21.0, 12.4), (21.4, 12.0),
                       (26.6, 12.0), (27.0, 11.6)]), ("via", (27.0, 11.6)),
               ("L1", [(27.0, 11.6), "U2.N7"])],
    "FMC_D6": [("L1", ["U1.P9", (14.325, 18.225)]), ("via", (14.325, 18.225)),
               ("L3", [(14.325, 18.225), (14.65, 18.55), (14.65, 20.55), (15.05, 20.95), (21.0, 20.95), (21.4, 20.55), (21.4, 13.2),
                       (21.8, 12.8), (26.6, 12.8), (27.0, 12.4)]), ("via", (27.0, 12.4)),
               ("L1", [(27.0, 12.4), "U2.M8"])],
    "FMC_D4": [("L1", ["U1.R8", (14.325, 18.875)]), ("via", (14.325, 18.875)),
               ("L3", [(14.325, 18.875), (14.325, 20.9), (14.725, 21.3), (21.4, 21.3), (21.8, 20.9), (21.8, 14.0), (22.2, 13.6),
                       (26.6, 13.6), (27.0, 13.2)]), ("via", (27.0, 13.2)),
               ("L1", [(27.0, 13.2), "U2.M7"])],
    "FMC_D5": [("L1", ["U1.P8", (13.675, 18.225)]), ("via", (13.675, 18.225)),
               ("L3", [(13.675, 18.225), (13.675, 21.25), (14.075, 21.65), (21.8, 21.65), (22.2, 21.25), (22.2, 14.8), (22.6, 14.4),
                       (25.8, 14.4), (26.2, 14.0)]), ("via", (26.2, 14.0)),
               ("L1", [(26.2, 14.0), "U2.L8"])],
    # ---- the mask on L1: north of the MCU, down between the packages into ball K9 from the west
    "FMC_NBL0": [("L1", ["U1.A4", (11.4, 7.6), (11.8, 7.2), (24.2, 7.2), (24.6, 7.6), (24.6, 14.0), (25.0, 14.4), "U2.K9"])],
    # ---- bank address on L1 into J7 through the row gap at y 14.8, a dip south between the packages for the window
    "FMC_BA0": [("L1", ["U1.K14", (18.225, 14.975), (21.4, 14.975), (23.225, 16.8), (23.625, 16.8), (25.625, 14.8), (27.0, 14.8),
                        "U2.J7"])],
    # ---- clock: L1 to R1 (turned 90 degrees, pin 1 south), SDRAM side on L4 along y 12.0, up into J1 from the west
    "FMC_SDCLK": [("L1", ["U1.H14", (18.225, 13.675), "R1.1"])],
    "FMC_SDCLK_R": [("L1", ["R1.2", (20.6, 12.0)]), ("via", (20.6, 12.0)),
                    ("L4", [(20.6, 12.0), (31.0, 12.0), (31.4, 12.4), (31.4, 14.4), (31.8, 14.8)]), ("via", (31.8, 14.8)),
                    ("L1", [(31.8, 14.8), "U2.J1"])],
    # ---- address lines on L4: dog-bones on the MCU's west side, east under the MCU along its ball rows, down to the
    # SDRAM's rows G / F between the packages
    "FMC_A0": [("L1", ["U1.E2", (10.425, 12.375)]), ("via", (10.425, 12.375)),
               ("L4", [(10.425, 12.375), (10.75, 12.7), (20.6, 12.7), (23.9, 16.0), (25.8, 16.0), (26.2, 16.4)]), ("via", (26.2, 16.4)),
               ("L1", [(26.2, 16.4), "U2.G8"])],
    "FMC_A1": [("L1", ["U1.H3", (11.075, 13.675)]), ("via", (11.075, 13.675)),
               ("L4", [(11.075, 13.675), (11.4, 14.0), (21.33, 14.0), (23.73, 16.4), (25.4, 16.4)]), ("via", (25.4, 16.4)),
               ("L1", [(25.4, 16.4), "U2.G9"])],
    "FMC_A2": [("L1", ["U1.H2", (10.425, 14.325)]), ("via", (10.425, 14.325)),
               ("L4", [(10.425, 14.325), (10.75, 14.65), (21.41, 14.65), (23.56, 16.8), (26.6, 16.8), (27.0, 17.2)]), ("via", (27.0, 17.2)),
               ("L1", [(27.0, 17.2), "U2.F7"])],
    "FMC_A3": [("L1", ["U1.J2", (10.425, 14.975)]), ("via", (10.425, 14.975)),
               ("L4", [(10.425, 14.975), (10.75, 15.3), (21.49, 15.3), (23.79, 17.6), (29.8, 17.6), (30.2, 17.2)]), ("via", (30.2, 17.2)),
               ("L1", [(30.2, 17.2), "U2.F3"])],
}

# serpentine sites (net, layer, p0, p1, side as seen from p0 to p1): straights with room on one side
SITES = [
    ("FMC_D2", "L3", (17.325, 2.825), (21.4, 2.825), "L"),       # band, humps north (board edge at y 0)
    ("FMC_D3", "L3", (17.65, 3.3), (21.0, 3.3), "R"),            # band, humps south (D1's lane at y 5.12)
    ("FMC_NBL0", "L1", (11.8, 7.2), (24.2, 7.2), "L"),           # north of the MCU on L1, humps north
    ("FMC_D7", "L3", (21.0, 19.6), (21.0, 13.0), "L"),           # between the packages, humps west (MCU area at x 20)
]


def routes(job):
    for net, lay, p0, p1, side in SITES:
        job.slot(net, lay, p0, p1, side=side)
    return {n: [tuple(pc) for pc in pcs] for n, pcs in PATHS.items()}
