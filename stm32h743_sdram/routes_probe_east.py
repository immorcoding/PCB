"""Trial escape (probe), NOT part of any deliverable: can the non-SDRAM balls on the MCU's east side get out past the
SDRAM rivers, and at what cost? Built on a snapshot of the committed board (SDRAM group as formal routing, power vias
and pours, fills removed with core.boardtext unfill), never on the real board:

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.routing.busroute.build stm32h743_sdram\\routes_probe_east.py --sketch --out stm32h743_sdram\\out\\probe_east\\run

Open ends: north y = 26.5, south y = 50.8, CAN also x >= 63 (east). Local mm (MCU centre (40, 37)).
Corridors used (see the report in issue #22 for capacities):
  north  L6 west of the l6n north legs (x < 47.25) and north of D23's lead (y 33.75): CAN pair, SDMMC1_D1
  north  L6 under the MCU between C208 and C218 (x 41.42), reached on L4 along ball row G: SDMMC1_D0
  south  L1 pocket P3 (D24 / SDCLK) -> east round the SDCLK_R via -> L4 pocket (A4 / l4s / SDCLK_R) -> L1 P7 ->
         L4 S4 (east of D17) -> L1 below the A11 lane: LCD_B3 ; same from pocket P4 (SDCLK / D20) through the
         throat west of the GND via (48.15, 37.375): LCD_CLK
  south  L4 S4 straight from a dog-bone: TP_RST, I2C4_SDA ; via L6 R3 into S4: I2C4_SCL
  east   L1 pocket P2 (D3 / D24) -> L6 R1 -> under the SDRAM (one track between the via rows) -> x 63 -> south: LCD_B4
Not drawn (enclosed or no capacity left): SDMMC1_D3 (B13), LCD_R5, LCD_G6, LCD_HSYNC, LCD_R7, TP_INT.
"""
BOARD = "out/probe_east/base/stm32h743_sdram.kicad_pcb"
ORIGIN = (100, 100)
GROUP = "probe_east"
SKETCH = True
YIELD_NETS = ["GND"]
OPEN_ENDS = True
YN, YS = 26.5, 50.8
VIEWS = [("east", 38.0, 25.5, 52.0, 51.5, 60), ("strip", 43.0, 30.0, 51.0, 44.0, 120), ("south", 43.0, 40.0, 50.0, 51.5, 120),
         ("sdram", 48.0, 30.0, 64.0, 51.5, 50)]


def routes(job):
    net = lambda b: job.board.pad("U201." + b).net
    v, R = "via", {}

    def r(ball, pieces):
        R[net(ball)] = pieces
    # ---- north: CAN pair, dog-bone vias in the B / C gap row east of column 15, L6 north
    r("B15", [("L1", ["U201.B15", (45.1, 33.1), (45.425, 33.425)]), (v, (45.425, 33.425)), ("L6", [(45.425, 33.425), (45.425, YN)])])
    r("C15", [("L1", ["U201.C15", (44.875, 33.425)]), (v, (44.875, 33.425)), ("L6", [(44.875, 33.425), (44.875, YN)])])
    # ---- north: SDMMC1_D0 under the MCU: SW dog-bone, L4 west along row G, L6 north between via columns
    r("G14", [("L1", ["U201.G14", (43.575, 36.675)]), (v, (43.575, 36.675)),
              ("L4", [(43.575, 36.675), (43.25, 36.35), (41.3, 36.35), (40.975, 36.025)]), (v, (40.975, 36.025)),
              ("L6", [(40.975, 36.025), (41.42, 35.58), (41.42, 27.0)])])
    # ---- north: SDMMC1_D1 through the strip: P3 (L1) -> R1 (L6) -> P1 (L1) -> L6 west of the l6n north legs
    r("F14", [("L1", ["U201.F14", (44.225, 36.025), (44.875, 36.025), (45.2, 36.35), (45.9, 36.35), (46.1, 36.15), (49.4, 36.15)]),
              (v, (49.4, 36.15)), ("L6", [(49.4, 36.15), (48.7, 35.45), (48.7, 31.8)]), (v, (48.7, 31.8)),
              ("L1", [(48.7, 31.8), (46.3, 31.8)]), (v, (46.3, 31.8)), ("L6", [(46.3, 31.8), (46.3, YN)])])
    # ---- east: LCD_B4 from P2 down to R1, under the SDRAM between the via rows, south along x 63
    r("D15", [("L1", ["U201.D15", (48.625, 34.4), (49.3, 33.725)]), (v, (49.3, 33.725)),
              ("L6", [(49.3, 33.725), (51.45, 33.725), (52.725, 35.0), (53.9, 35.0), (54.15, 35.25), (57.6, 35.25), (57.75, 35.4),
                      (60.5, 35.4), (60.85, 35.75), (62.25, 35.75), (62.6, 36.1), (62.6, YS)])])
    # ---- south through the strip
    # LCD_B3: P3 north lane, round the SDCLK_R via on its east side, down to the L4 pocket
    r("F15", [("L1", ["U201.F15", (49.6, 35.7), (49.85, 35.95), (49.85, 37.15), (49.45, 37.55)]), (v, (49.45, 37.55)),
              ("L4", [(49.45, 37.55), (48.6, 38.4), (48.6, 42.75)]), (v, (48.6, 42.75)),
              ("L1", [(48.6, 42.75), (46.3, 42.75)]), (v, (46.3, 42.75)),
              ("L4", [(46.3, 42.75), (46.3, 44.6), (48.2, 46.5), (48.2, 46.9)]), (v, (48.2, 46.9)),
              ("L1", [(48.2, 46.9), (48.2, YS)])])
    # LCD_CLK: through the J15 / K15 gap into P4, down west of the GND via (48.15, 37.375)
    r("J14", [("L1", ["U201.J14", (44.225, 37.975), (44.875, 37.975), (45.2, 37.65), (47.325, 37.65), (47.55, 37.425)]), (v, (47.55, 37.425)),
              ("L4", [(47.55, 37.425), (47.73, 37.605), (47.73, 41.78), (47.95, 42.0)]), (v, (47.95, 42.0)),
              ("L1", [(47.95, 42.0), (46.1, 42.0), (45.8, 42.3)]), (v, (45.8, 42.3)),
              ("L4", [(45.8, 42.3), (45.8, 44.95), (47.25, 46.4), (47.25, 46.9)]), (v, (47.25, 46.9)),
              ("L1", [(47.25, 46.9), (47.25, YS)])])
    # LCD_R7 under the MCU: dog-bone into L4 along ball row H, up into the L1 moat round the centre GND block (column 11,
    # row L), down to L4 at (40.25, 39.25) and south in the corridor between A11 (L4 x 40.0) and D16 (L4 x 43.25)
    r("J15", [("L1", ["U201.J15", (44.875, 37.325)]), (v, (44.875, 37.325)),
              ("L4", [(44.875, 37.325), (44.55, 37.0), (41.95, 37.0), (41.625, 36.675)]), (v, (41.625, 36.675)),
              ("L1", [(41.625, 36.675), (41.95, 37.0), (41.95, 38.775), (41.775, 38.95), (40.55, 38.95), (40.25, 39.25)]), (v, (40.25, 39.25)),
              ("L4", [(40.25, 39.25), (40.65, 39.65), (40.65, 41.725), (40.975, 42.05), (40.975, YS)])])
    # ---- south: S4 (L4 east of D17) directly
    r("N14", [("L1", ["U201.N14", (44.225, 40.575)]), (v, (44.225, 40.575)), ("L4", [(44.225, 40.575), (44.225, 45.9), (44.4, 46.075), (44.4, 46.9)]), (v, (44.4, 46.9)),
              ("L1", [(44.4, 46.9), (44.4, YS)])])
    r("M15", [("L1", ["U201.M15", (44.875, 39.925)]), (v, (44.875, 39.925)),
              ("L4", [(44.875, 39.925), (44.55, 40.25), (44.55, 41.0), (44.8, 41.25), (44.8, 45.7), (45.35, 46.25), (45.35, 46.9)]), (v, (45.35, 46.9)),
              ("L1", [(45.35, 46.9), (45.35, YS)])])
    r("N13", [("L1", ["U201.N13", (43.575, 40.575)]), (v, (43.575, 40.575)),
              ("L6", [(43.575, 40.575), (44.0, 41.0), (44.6, 41.0), (45.3, 41.7)]), (v, (45.3, 41.7)),
              ("L4", [(45.3, 41.7), (45.3, 45.3), (46.3, 46.3), (46.3, 46.9)]), (v, (46.3, 46.9)),
              ("L1", [(46.3, 46.9), (46.3, YS)])])
    return R
