"""Local nets of the demo board, written by hand with coordinates (RTE-3): the HSE crystal and its load capacitors,
the reset test pad, the debug UART, and the ground vias beside the ground pads of the top parts.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.build templates/demo_board route   (after the bus and the BGA power)
    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.routing.busroute.build templates\\demo_board\\routes_local.py --fast

Crystal (SPEC 9): both lines 0.254 mm (net class XTAL, also inside the MCU rule area), L1 only, no via; L2 under
them is whole. HSE_IN from ball G1 west into the IN pad (north-east pad, Y1 turned 180 degrees), C1 north of it;
HSE_OUT from ball H1 round the crystal's south-east ground pad into the OUT pad (south-west), C2 west of it.
Ground is not routed (this group owns no ground copper): each ground pad of these parts gets a 0.45 / 0.2 via beside
it (the crystal's two between its pads, under the body), joined by the L1 ground pour.
"""
import os

BOARD = os.environ.get("BOARD", "demo_board.kicad_pcb")
ORIGIN = (100, 100)
GROUP = "local"
VIA_LIMIT = 4
YIELD_NETS = ["GND"]          # the L1 / L6 ground pours give way to the tracks
PROFILE = {"area_free_classes": ["XTAL"]}    # the crystal lines keep 0.254 inside the MCU rule area (SPEC 7)
NETS = ["HSE_IN", "HSE_OUT", "NRST", "USART1_TX", "USART1_RX"]
VIEWS = [("west", 0.0, 8.0, 12.0, 24.0, 60), ("uart", 12.0, 17.0, 24.0, 30.0, 40)]
X = 0.254                     # crystal line width (XTAL class)
# ground vias beside the ground pads (written as extras: stitching vias of GND)
GND_VIAS = [(5.8, 12.85),     # Y1.2, between the crystal's pads
            (5.8, 14.55),     # Y1.4, between the crystal's pads (its other sides are closed by HSE_IN / HSE_OUT)
            (6.9, 9.7),       # C1.2
            (2.22, 15.45),    # C2.2
            (6.55, 19.0)]     # C9.2, north of the L5 +3V3 tongue to J1


def routes(job):
    R = {}
    R["HSE_IN"] = [[("L1", ["U1.G1", (7.4, 13.35), "Y1.1"], X)],
                   [("L1", ["Y1.1", "C1.1"], X)]]
    R["HSE_OUT"] = [[("L1", ["U1.H1", (9.2, 14.0), (7.75, 15.45), (5.25, 15.45), (4.7, 14.9), "Y1.3"], X)],
                    [("L1", ["Y1.3", "C2.1"], X)]]
    R["NRST"] = [("L1", ["U1.J1", (9.125, 14.975), (6.3, 17.8), "TP1.1"])]
    R["USART1_TX"] = [("L1", ["U1.R14", (17.9, 24.0), (16.5, 25.4), "J2.2"])]
    R["USART1_RX"] = [("L1", ["U1.R15", (18.55, 24.5), (19.04, 24.99), "J2.3"])]
    job.profile.classes["PWR"]["via"] = (0.45, 0.2)          # GND is PWR class (0.6 / 0.3): this board's vias are 0.45 / 0.2
    job.stitch += [("GND", p) for p in GND_VIAS]
    return R
