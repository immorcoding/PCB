"""Trial ground guard of the two crystals, NOT a deliverable: built on top of routes_probe_xtal.py's output (command
in that file). Proves that Y201's north-east ground pad, closed in by HSE_IN and HSE_OUT, reaches ground, and
that a guard fits between LSE_OUT and HSE_IN and between HSE_IN and HSE_OUT.

One chain (the routes format takes one per net):
  Y201 NE ground pad - east - 45 degrees up between the HSE_IN and HSE_OUT tracks - east at y 36.675 (between
  balls G1 and H1 inside the BGA) - ground ball G2 - back west at y 36.025 between the LSE_OUT and HSE_IN tracks (between balls
  F1 and G1) - 45 degrees down past the LSE OUT pad - west at y 36.8 - C225's ground pad - a through via west
  of Y201 - Y201 SW ground pad.
The turn at G2 is a 90 degree corner inside the ball: in the real routing the two guards are two ties to G2
(and F2). The guard is 0.09 mm inside the MCU rule area and 0.1524 mm outside, the minimum for power nets (rule
pwr_width; GND's class width 0.3048 does not fit between two crystal tracks at the 0.65 mm ball pitch). An L1
ground pour would drop a sliver this narrow (minwidth 0.3), so it is a track. The via shows as dangling here
(the sketch board has no plane fills).
"""
BOARD = "out/probe_xtal/stm32h743_sdram.kicad_pcb"
ORIGIN = (100, 100)
GROUP = "probe_xtal_gnd"
SKETCH = True
VIEWS = [("xtal", 25.0, 32.0, 37.0, 43.0, 100)]


def routes(job):
    # GND at its rule minimum (pwr_width 0.1524) outside the rule area instead of its class width
    job.profile.classes["GND_GUARD"] = dict(job.profile.classes["PWR"], width=0.1524)
    job.profile._cls["GND"] = "GND_GUARD"
    return {
        "GND": [("L1", ["Y201.4", (32.975, 37.9), (34.2, 36.675), (35.775, 36.675), "U201.G2", (35.775, 36.025),
                        (31.6, 36.025), (30.825, 36.8), (28.47, 36.8), (28.17, 37.1), "C225.2", (28.17, 39.55),
                        (28.72, 40.1), (29.3, 40.1)]),
                ("via", (29.3, 40.1)),
                ("L1", [(29.3, 40.1), "Y201.2"])],
    }
