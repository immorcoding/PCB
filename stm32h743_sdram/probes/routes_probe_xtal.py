"""Trial routes of the two crystals, NOT a deliverable: proves that each ball reaches its crystal pad and its load
capacitor on L1 without vias, next to the SDRAM sketch. The routes format takes one chain per net, so each chain
runs ball - crystal pad - capacitor and the build reports "3 pads, a route joins two" for every net (the crystal
pad is passed through mid-chain, which the PATH check does not count). Built on the sketch build's output board
(never on the real board):

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.routing.busroute.build stm32h743_sdram\\probes\\routes_probe_xtal.py --sketch --out stm32h743_sdram\\out\\probe_xtal
    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.routing.busroute.build stm32h743_sdram\\probes\\routes_probe_xtal_gnd.py --sketch --out stm32h743_sdram\\out\\probe_xtal_gnd

(build ../routes_sdram.py into out\\sketch\\rot0 first; the second file adds the ground guards on top of this one's
output). Placement of try/eth-west: LSE Y202 vertical at (29.5, 34.8), HSE Y201 at 270 degrees centred on the
FMC_A6 via at (31.4, 39.0), the via in its row gap and the A6 track in its column gap. Every chain enters its
crystal pad at the pad centre and goes on to the load capacitor beyond it.

  LSE_IN   E1 west at y 35.05, 45 degrees up to y 33.55, west through the IN pad (N) to C227
  LSE_OUT  F1 west at y 35.7, up to y 35.55 inside the rule area, west into the OUT pad (S) from its north-east,
           west to C228
  HSE_IN   G1 west at y 36.35, down to y 36.45 just outside the rule area, 45 degrees down into the IN pad (NW)
           over the NE ground pad, west to C225
  HSE_OUT  H1 west, 45 degrees down, south at x 33.15 east of the NE ground pad, 45 degrees into the OUT pad
           (SE), south and 45 degrees to C226
Between LSE_OUT and HSE_IN, and between HSE_IN and HSE_OUT, runs a ground guard (routes_probe_xtal_gnd.py); the
two small steps of LSE_OUT and HSE_IN make room for it at GND's minimum width (0.1524 mm, rule pwr_width) outside
the rule area.
"""
BOARD = "../out/sketch/rot0/stm32h743_sdram.kicad_pcb"
ORIGIN = (100, 100)
GROUP = "probe_xtal"
SKETCH = True
PROFILE = {"w_area": 0.254}     # crystal lines stay 0.254 inside the MCU rule area too (SPEC 7: no area exception)
VIEWS = [("xtal", 25.0, 32.0, 37.0, 43.0, 100)]


def routes(job):
    return {
        "LSE_IN": [("L1", ["U201.E1", (31.9, 35.05), (30.4, 33.55), "Y202.1", "C227.1"])],
        "LSE_OUT": [("L1", ["U201.F1", (34.6, 35.7), (34.45, 35.55), (30.0, 35.55), "Y202.2", "C228.1"])],
        "HSE_IN": [("L1", ["U201.G1", (34.0, 36.35), (33.9, 36.45), (32.0, 36.45), "Y201.1", "C225.1"])],
        "HSE_OUT": [("L1", ["U201.H1", (34.6, 37.0), (33.15, 38.45), (33.15, 39.2), "Y201.3", (32.25, 41.02), "C226.1"])],
    }
