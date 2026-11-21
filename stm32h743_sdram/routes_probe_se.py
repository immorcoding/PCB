"""Trial escape, NOT part of the SDRAM deliverable: can the non-SDRAM balls of the MCU's bottom-right corner get out
to the south past the SDRAM bands? Built on top of the SDRAM sketch's output board (never on the real board):

    D:\\KiCad\\bin\\python.exe scripts\\busroute\\build.py stm32h743_sdram\\routes_probe_se.py --sketch --out stm32h743_sdram\\out\\probe_se

(build routes_sdram.py into out\\sketch\\rot0 first). Rough tracks from the balls to y = 50.8, about 3 mm south of the
lowest SDRAM band (D16 on L4 at y 47.75), with the net-class widths and vias of the profile.

West four (M11 N12 N13 R12): dog-bone or straight lead to a via inside the rule area, then L4 straight south in the
corridor between A11 (L4, x = 40.0) and D16 (L4, x = 43.25), under the L6 band (y 43.6-45.6) and the L1 band
(y 45.3-46.3). East four (N14 R14 R15 R13): via inside the rule area, L4 south east of D17 (x 43.9), spread to a
0.65 mm pitch, up to L1 at y = 46.85 (below the L1 band, above D16 / D17, which run east on L4 at y 47.5 / 47.75 since
round 3), L1 south. M15 (I2C4_SDA) is not drawn: it is enclosed by SDRAM escapes on every layer (see the report).
"""
BOARD = "out/sketch/rot0/stm32h743_sdram.kicad_pcb"
ORIGIN = (100, 100)
GROUP = "probe_se"
SKETCH = True
OPEN_ENDS = True
Y_OUT = 50.8
VIEWS = [("se", 39.0, 38.0, 48.0, 51.5, 100)]


def routes(job):
    net = lambda b: job.board.pad("U201." + b).net
    v, R = "via", {}

    def r(ball, pieces):
        R[net(ball)] = pieces
    # west: L4 in the corridor x 40.0 - 43.25
    r("M11", [("L1", ["U201.M11", (42.275, 39.925)]), (v, (42.275, 39.925)),
              ("L4", [(42.275, 39.925), (41.95, 40.25), (41.95, 42.4), (41.3, 43.05), (41.3, Y_OUT)])])
    r("N12", [("L1", ["U201.N12", (42.275, 40.575)]), (v, (42.275, 40.575)), ("L4", [(42.275, 40.575), (42.275, Y_OUT)])])
    r("R12", [("L1", ["U201.R12", (42.6, 42.5)]), (v, (42.6, 42.5)), ("L4", [(42.6, 42.5), (42.6, Y_OUT)])])
    r("N13", [("L1", ["U201.N13", (42.925, 40.575)]), (v, (42.925, 40.575)), ("L4", [(42.925, 40.575), (42.925, Y_OUT)])])
    # east: L4 east of D17, spread to 0.6 mm (staggered jogs), up to L1 below the L1 band
    r("R14", [("L1", ["U201.R14", (44.225, 41.875)]), (v, (44.225, 41.875)),
              ("L4", [(44.225, 41.875), (44.225, 43.9), (44.55, 44.225), (44.55, 46.85)]), (v, (44.55, 46.85)),
              ("L1", [(44.55, 46.85), (44.55, Y_OUT)])])
    r("N14", [("L1", ["U201.N14", (44.225, 40.575)]), (v, (44.225, 40.575)),
              ("L4", [(44.225, 40.575), (44.6, 40.95), (44.6, 43.6), (45.15, 44.15), (45.15, 46.85)]), (v, (45.15, 46.85)),
              ("L1", [(45.15, 46.85), (45.15, Y_OUT)])])
    r("R15", [("L1", ["U201.R15", (44.875, 41.875), (45.2, 41.875)]), (v, (45.2, 41.875)),
              ("L4", [(45.2, 41.875), (45.2, 43.3), (45.75, 43.85), (45.75, 46.85)]), (v, (45.75, 46.85)),
              ("L1", [(45.75, 46.85), (45.75, Y_OUT)])])
    r("R13", [("L1", ["U201.R13", (43.575, 41.875), (43.9, 42.2), (45.475, 42.2), (45.8, 42.525)]), (v, (45.8, 42.525)),
              ("L4", [(45.8, 42.525), (45.8, 43.0), (46.35, 43.55), (46.35, 46.85)]), (v, (46.35, 46.85)),
              ("L1", [(46.35, 46.85), (46.35, Y_OUT)])])
    return R
