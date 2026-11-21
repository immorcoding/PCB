"""Trial routes of the two crystals, NOT a deliverable: proves that each ball reaches its crystal pad and its load
capacitor on L1 without vias, next to the SDRAM sketch. The routes format takes one chain per net, so each chain runs ball - crystal pad -
capacitor and the build reports "3 pads, a route joins two" for every net (the crystal pad is passed through
mid-chain, which the PATH check does not count). Built on the sketch build's output board (never on the
real board):

    D:\\KiCad\\bin\\python.exe scripts\\busroute\\build.py stm32h743_sdram\\routes_probe_xtal.py --sketch --out stm32h743_sdram\\out\\probe_xtal

(build routes_sdram.py into out\\sketch\\rot0 first). One chain per net: ball - crystal pad - capacitor pad
(stop 4 round 3 placement: LSE Y202 vertical at (29.2, 34.8), HSE Y201 at 270 degrees centred on the FMC_A6
via at (31.4, 39.0), the via in its row gap and the A6 track in its column gap).

  LSE_IN   E1 west at y 35.05, 45 degrees up to the IN pad, on west to C227
  LSE_OUT  F1 west at y 35.7 (between the LSE_IN and HSE_IN tracks) into the OUT pad, on west to C228
  HSE_IN   G1 west at y 36.35 above the HSE, down at x 30.55 through the IN pad (NW) to C225 at y 37.42
  HSE_OUT  H1 west then 45 degrees down past the HSE's NE (GND) pad, down at x 33.45 east of it, into the
           OUT pad (SE) and on down to C226
"""
BOARD = "out/sketch/rot0/stm32h743_sdram.kicad_pcb"
ORIGIN = (100, 100)
GROUP = "probe_xtal"
SKETCH = True
PROFILE = {"w_area": 0.254}     # crystal lines stay 0.254 inside the MCU rule area too (SPEC 7: no area exception)
VIEWS = [("xtal", 25.0, 32.0, 37.0, 43.0, 100)]


def routes(job):
    return {
        "LSE_IN": [("L1", ["U201.E1", (31.35, 35.05), (29.85, 33.55), (29.2, 33.55), "C227.1"])],
        "LSE_OUT": [("L1", ["U201.F1", (29.55, 35.7), (29.2, 36.05), "C228.1"])],
        "HSE_IN": [("L1", ["U201.G1", (30.9, 36.35), (30.55, 36.7), (30.55, 37.07), (30.2, 37.42), "C225.1"])],
        "HSE_OUT": [("L1", ["U201.H1", (34.5, 37.0), (33.45, 38.05), (33.45, 39.75), (32.75, 40.45), (32.75, 41.52), "C226.1"])],
    }
