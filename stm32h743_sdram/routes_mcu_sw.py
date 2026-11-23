"""MCU south / west buses (stop 7, the remaining buses, issue 22): LTDC to the FPC J701, QSPI to the flash U401, the RMII
side to the PHY U501, the touch / I2C4 lines to their link resistors R701-R704, the user LEDs and key. Every net from
its BGA ball (fan_leads.lead: dog-bone and the planned run to the rule-area edge) to its destination, written with
coordinates (RTE-3, RTE-4: no autorouter). Local mm (board mm - 100).

    LOCAL_BOARD=<board> D:\\KiCad\\bin\\python.exe scripts\\busroute\\build.py stm32h743_sdram\\routes_mcu_sw.py --fast
    (build.sh route2 builds it on the real board once the group is in ROUTE2_GROUPS, after routes_mcu_nw.py; the
    east bundle's and the south / west balls' leads moved here from routes_mcu_east.py / routes_mcu_south.py)

Layer use south of the MCU (the SDRAM rivers: L1 y 44-46.5 east of x 38.5, L3 y 43.4-45.6 east of x 33.6, L4 D16 / D17
at y 47.5 / 47.75 east of x 43; the QSPI lines on L4 at x 36.1-41 down to y 58.6 form a wall on L4):
  L6  the east bundle (HSYNC, CLK, B3, G6, B4, R5 and the touch lines): a 0.25 mm step east right below the exits (off
      the L5 gap at the +3V3_MCU block's east edge, past the USART1_RX via), down the strip, SW at y 53.5, west at
      y 60.8-62.4 (south of the flash's +3V3_QSPI trace) and down into the FPC vias; VSYNC west at y 48.85 and down
      x 31.7; DE down x 29.9 / 30.2; both SE into their pins
  L4  B5 down x 35.45 (west of the QSPI wall) and east at y 59; B4 from the bundle (via at 42.25, 60.6) to 38.75; G5
      down x 43.9; USER_KEY from the field SW past the PHY to the key; PHY_NRST down the west corridor
  L3  G4 down x 42.75; G2 east at y 45.88 (just south of the SDRAM band), down x 49.1, west at y 65.2; the westward
      slow lines (LED1 / LED2, SCL) and the touch lines' last stretch
  L1  the R group (R3, R4, R6) east at y 49.99-51.3 and straight down into their pins (no FPC via); RXD0 / RXD1 west
      at y 48.75 / 49.35 into the PHY; the PHY-bound lines from the field vias; the last mm into every pad
FPC fan-in: every LTDC line ends in a via on its pin's x, two staggered rows (S y 68.75, N y 68.2), and a straight
L1 stub into the pad (the R group comes on L1 and needs none). The field: the west-gate L6 lines turn south in lanes
x 32.65-33.11 and west at y 42.63-43.09; with REF_CLK / MDIO (L4) and PHY_NRST (L4, corridor) their vias sit at
x 28.35-32.55, y 42.9-44.3 (south of the crystals' L1 box) in the order the PHY's pins need.

Open (lead and gate only, kept where routes_mcu_nw.py / routes_mcu_south.py left them):
  DISP, TXD0, G3, G7, BL_PWM  no via spot on the gate's x in the band: R203's / C217's vias (37.84-42.03, 26.2-27.15)
  TX_EN, B7                   a via only 0.86 / 0.66 mm from the gate (rule: 0.6); TX_EN alone is no use without TXD0
  B6, B7                      via the west corridor ~68 mm: beyond the LTDC spread (30 mm) against the south lines
  NCS                         from a north exit > 50 mm (QSPI cap 30 mm)
  TXD1                        its gate (30.0, 33.75) is inside Y202.1's pad clearance: no via within 0.6 mm
  QSPI IO2 / IO3              west exits: IO2 ~32.5 mm, IO3 ~28 mm + the 5 mm stub to R403 (cap 30, window CLK +-5);
                              no south exit through the field (L4 / L6 west runs, SDNWE closes L3)
"""
import os
from fan_leads import plan, info

BOARD = os.environ.get("LOCAL_BOARD", "stm32h743_sdram.kicad_pcb")
ORIGIN = (100, 100)
GROUP = "mcu_sw"
ROUND = 5
OPEN_ENDS = True
YIELD_NETS = ["GND"]
VIA_LIMIT = 8
DRC_IGNORE = {"solder_mask_bridge": "mask webs between fine-pitch pads of the footprints (QFN, FPC), there before this group"}
VIEWS = [("fpc", 28.0, 54.0, 50.0, 71.0, 45), ("south", 28.0, 40.0, 50.0, 56.0, 45), ("phy", 18.0, 40.0, 34.0, 54.0, 50),
         ("corridor", 26.0, 25.0, 46.0, 44.0, 35), ("qspi", 28.0, 52.0, 44.0, 62.0, 45)]
T = 0.1016
P = 0.2286
YS, YN = 68.75, 68.2          # FPC via rows (south / north)

# re-site of three south / west balls (out/sw/bga_fan_patch.json; the main session applies it to bga_fan.json, after
# which these entries change nothing): R3 and R4 swap their columns so that R3 (pin 47.25) is east of R4 (pin 46.75)
# on L6
PATCH = {
    "R5": {"net": "LCD_R3", "via": [37.725, 41.875], "layer": "L6", "side": "S",
           "run": [[37.725, 41.875], [38.05, 42.2], [38.05, 43.0]], "exit": [38.05, 43.0]},
    "P4": {"net": "LCD_R4", "via": [37.725, 41.225], "layer": "L6", "side": "S",
           "run": [[37.725, 41.225], [37.4, 41.55], [37.4, 43.0]], "exit": [37.4, 43.0]},
    # CRS_DV leaves south along column 2 (L6 x 36.1 is free below row R): its way round to the PHY keeps it longer
    # than REF_CLK, and the L6 row y 42.2 west of the field is no longer needed
    "R3": {"net": "RMII_CRS_DV", "via": [36.425, 41.875], "layer": "L6", "side": "S",
           "run": [[36.425, 41.875], [36.1, 42.2], [36.1, 43.0]], "exit": [36.1, 43.0], "len": 1.719},
}


def r4(v):
    return round(v, 4)


def pt(p):
    return p if isinstance(p, str) else (r4(p[0]), r4(p[1]))


def Lp(layer, pts, w=T):
    return (layer, [pt(p) for p in pts], w)


def V(x, y):
    return ("via", (r4(x), r4(y)))


def rec(ball):
    s = dict(info(ball))
    s.update(PATCH.get(ball, {}))
    return s


def ball_of(net):
    for num, v in plan()["U201"]["signal"].items():
        if v["net"] == net:
            return num
    return None


def lead(net):
    """[L1 dog-bone, via, inner-layer run to the rule-area edge] of the net's ball, as a list of pieces."""
    num = ball_of(net)
    s = rec(num)
    via = tuple(s["via"])
    run = [tuple(p) for p in s["run"]]
    if run and run[0] != via:
        run = [via] + run
    return [Lp("L1", ["U201." + num, via]), ("via", via), Lp(s["layer"], run)]


def exit_of(net):
    return tuple(rec(ball_of(net))["exit"])


def go(net, pts, *more):
    """lead + the run continued through pts on its own layer, then the further pieces."""
    pcs = lead(net)
    lay, p0, w = pcs[-1]
    return pcs[:-1] + [Lp(lay, list(p0) + list(pts))] + list(more)


def to_fpc(x, y, pin):
    """via at (x, y) and the L1 stub into J701.pin"""
    return [V(x, y), Lp("L1", [(x, y), "J701.%d" % pin])]


# ---------------------------------------------------------------- the east bundle (L6)
EAST = ["TP_RST", "I2C4_SDA", "TP_INT", "LCD_HSYNC", "LCD_CLK", "LCD_B3", "LCD_G6", "LCD_B4", "LCD_R5"]   # lanes k = 1..9
JOG = 0.25                     # the bundle steps east right below the exits: off the gap of the +3V3_MCU block's east
                               # edge (x 46-46.5 on L5) and past the USART1_RX via (46.25, 51.25)


def east_lane(net):
    k = EAST.index(net) + 1
    xk = r4(46.25 + P * k)
    ye = exit_of(net)[1]
    a = r4(41.5 + (9 - k) * 0.0947)                     # the eastmost lane jogs first
    return k, xk, [(xk, ye + xk - 46.0), (xk, a), (xk + JOG, a + JOG)]


def east_bundle():
    R = {}
    for j, net in enumerate(EAST[:8]):                  # j = 0 .. 7: TP_RST .. B4
        k, xk, pts = east_lane(net)
        x1 = r4(xk + JOG)
        t = r4(53.5 + 0.0947 * j)                       # SW turn
        c = x1 + t                                      # the diagonal x + y = c
        w = r4(60.8 + P * j)                            # westward run
        s = r4(c - w)
        if net == "LCD_G6":                             # leaves the diagonal straight down to its via
            R[net] = go(net, pts + [(x1, t), (41.75, c - 41.75), (41.75, YN)], *to_fpc(41.75, YN, 22))
        elif net == "LCD_B4":                           # leaves the diagonal at x 42.25, via to L4, west to 38.75
            R[net] = go(net, pts + [(x1, t), (42.25, c - 42.25), (42.25, 60.6)], V(42.25, 60.6),
                        Lp("L4", [(42.25, 60.6), (41.85, 61.0), (39.15, 61.0), (38.75, 61.4), (38.75, YN)]), *to_fpc(38.75, YN, 16))
        elif net == "LCD_B3":
            R[net] = go(net, pts + [(x1, t), (39.25, c - 39.25), (39.25, YS)], *to_fpc(39.25, YS, 17))
        elif net == "LCD_CLK":
            R[net] = go(net, pts + [(x1, t), (s, w), (36.65, w), (36.25, w + 0.4), (36.25, YS)], *to_fpc(36.25, YS, 11))
        elif net == "LCD_HSYNC":
            R[net] = go(net, pts + [(x1, t), (s, w), (35.65, w), (35.25, w + 0.4), (35.25, YS)], *to_fpc(35.25, YS, 9))
        elif net == "TP_INT":                           # L6 -> L3 at (34.6, 62.0), L3 to its pad via
            R[net] = go(net, pts + [(x1, t), (s, w), (35.0, w), (34.6, w + 0.4), (34.6, 62.0)], V(34.6, 62.0),
                        Lp("L3", [(34.6, 62.0), (34.2, 62.4), (32.05, 62.4), (31.65, 62.8), (31.65, 63.85)]), V(31.65, 63.85),
                        Lp("L1", [(31.65, 63.85), "R702.2"]))
        elif net == "I2C4_SDA":
            R[net] = go(net, pts + [(x1, t), (s, w), (34.4, w), (34.0, w + 0.4), (34.0, 62.9)], V(34.0, 62.9),
                        Lp("L3", [(34.0, 62.9), (32.3, 64.6), (29.65, 64.6)]), V(29.65, 64.6),
                        Lp("L1", [(29.65, 64.6), (29.25, 65.0), "R704.2"]))
        elif net == "TP_RST":
            R[net] = go(net, pts + [(x1, t), (s, w), (33.8, w), (33.4, w + 0.4), (33.4, 61.55)], V(33.4, 61.55),
                        Lp("L1", [(33.4, 61.55), (33.4, 65.94), "R701.2"]))
    # R5: the eastmost lane, straight down and SW into its via
    k, xk, pts = east_lane("LCD_R5")
    x1 = r4(xk + JOG)
    tR = 56.0
    R["LCD_R5"] = go("LCD_R5", pts + [(x1, tR), (46.25, tR + x1 - 46.25), (46.25, YS)], *to_fpc(46.25, YS, 31))
    return R


# ---------------------------------------------------------------- south gates
def south():
    R = {}
    # R group: vias to L1, east, straight down into the pins (no FPC via)
    R["LCD_R3"] = go("LCD_R3", [(38.05, 49.6), (38.44, 49.99), (39.3, 49.99)], V(39.3, 49.99),
                     Lp("L1", [(39.3, 49.99), (46.85, 49.99), (47.25, 50.39), "J701.33"]))
    R["LCD_R4"] = go("LCD_R4", [(37.4, 49.7), (38.12, 50.42), (38.7, 50.42)], V(38.7, 50.42),
                     Lp("L1", [(38.7, 50.42), (46.35, 50.42), (46.75, 50.82), "J701.32"]))
    # R6 and VSYNC step from x 36.75 to 37.0 right below the area: x 36.4-36.9 is the gap at the east edge of the
    # +3V3_MCU block's tongue on L5 (y 44.8-48.2)
    R["LCD_R6"] = go("LCD_R6", [(36.75, 44.0), (37.0, 44.25), (37.0, 49.85), (36.75, 50.1), (36.75, 50.9)], V(36.75, 50.9),
                     Lp("L1", [(36.75, 50.9), (37.15, 51.3), (45.35, 51.3), (45.75, 51.7), "J701.30"]))
    # VSYNC: L6 west at y 48.85 (south of the tongue's gap), down x 31.7, SE into its pin
    R["LCD_VSYNC"] = go("LCD_VSYNC", [(36.75, 44.0), (37.0, 44.25), (37.0, 48.45), (36.6, 48.85), (32.1, 48.85), (31.7, 49.25),
                                      (31.7, 63.0), (34.75, 66.05), (34.75, YN)], *to_fpc(34.75, YN, 8))
    # B5: L4 down x 35.45 (west of the QSPI wall), east at y 59 south of the flash's L4 run, down into its via
    R["LCD_B5"] = go("LCD_B5", [(35.45, 58.6), (35.85, 59.0), (37.85, 59.0), (38.25, 59.4), (38.25, YS)], *to_fpc(38.25, YS, 15))
    # G4: L6 down, via to L3, straight down x 42.75
    R["LCD_G4"] = go("LCD_G4", [(42.6, 49.4), (42.75, 49.55), (42.75, 51.8)], V(42.75, 51.8),
                     Lp("L3", [(42.75, 51.8), (42.75, YN)]), *to_fpc(42.75, YN, 24))
    # G5: L6 down, via to L4, down x 43.9, SW to 42.25
    R["LCD_G5"] = go("LCD_G5", [(43.9, 51.8)], V(43.9, 51.8),
                     Lp("L4", [(43.9, 51.8), (43.9, 64.6), (42.25, 66.25), (42.25, YS)]), *to_fpc(42.25, YS, 23))
    # RXD: to L1 below the gates, west into the PHY's east pins
    R["RMII_RXD0"] = go("RMII_RXD0", [(38.7, 47.0), (39.3, 47.6), (39.3, 48.75)], V(39.3, 48.75),
                        Lp("L1", [(39.3, 48.75), (31.25, 48.75), (28.75, 51.25), "U501.8"]))
    R["RMII_RXD1"] = go("RMII_RXD1", [(38.7, 49.35)], V(38.7, 49.35),
                        Lp("L1", [(38.7, 49.35), (31.6, 49.35), (29.2, 51.75), "U501.7"]))
    # SCL: via to L3, west (south of the LEDs), down x 31.2 to its pad via
    R["I2C4_SCL"] = go("I2C4_SCL", [(43.25, 48.3)], V(43.25, 48.3),
                       Lp("L3", [(43.25, 48.3), (35.0, 48.3), (34.52, 48.78), (31.6, 48.78), (31.2, 49.18), (31.2, 63.25),
                                 (30.45, 64.0)]), V(30.45, 64.0), Lp("L1", [(30.45, 64.0), "R703.2"]))
    # LEDs: via to L3 below the SDRAM band, west through the gaps of the ground / +3V3_MCU via fence at x 32.7, SW past
    # the PHY's east side, down west of the crystal Y501, SW into a via west of each resistor, L1 into it from the west
    R["LED2"] = go("LED2", [(41.95, 46.86)], V(41.95, 46.86),
                   Lp("L3", [(41.95, 46.86), (41.61, 47.2), (33.56, 47.2), (33.16, 47.6), (30.0, 47.6), (20.6, 57.0), (20.6, 61.0),
                             (20.2, 61.4), (16.0, 61.4), (15.6, 61.8), (15.6, 63.8), (16.4, 64.6)]), V(16.4, 64.6),
                   Lp("L1", [(16.4, 64.6), "R809.1"]))
    R["LED1"] = go("LED1", [(42.6, 47.15), (41.95, 47.8)], V(41.95, 47.8),
                   Lp("L3", [(41.95, 47.8), (34.4, 47.8), (33.65, 48.55), (29.45, 48.55), (20.95, 57.05), (20.95, 62.25),
                             (18.0, 65.2), (13.5, 65.2), (12.9, 64.6)]), V(12.9, 64.6), Lp("L1", [(12.9, 64.6), "R808.1"]))
    return R


# ---------------------------------------------------------------- QSPI (the three complete lines, moved here)
def qspi():
    R = {}
    R["QSPI_CLK"] = go("QSPI_CLK", [(38.05, 55.4)], V(38.05, 55.4), Lp("L1", [(38.05, 55.4), (34.215, 55.4), "U401.6"]))
    R["QSPI_BK1_IO0"] = go("QSPI_BK1_IO0", [(37.4, 54.6)], V(37.4, 54.6),
                           Lp("L1", [(37.4, 54.6), (32.6, 54.6), (32.25, 54.95), "U401.5"]))
    R["QSPI_BK1_IO1"] = go("QSPI_BK1_IO1", [(36.1, 55.6), (36.5, 56.0), (40.6, 56.0), (41.0, 56.4), (41.0, 58.635)],
                           V(41.0, 58.635), Lp("L1", [(41.0, 58.635), "U401.2"]))
    return R


# ---------------------------------------------------------------- west gates: lanes x 32.65-33.56, west, the field
def lanes(i, row):
    """the west-gate L6 lanes: (34, row) west, down lane i, west at the field level. -> (points, x of the lane, y of
    the westward run). Lane i at x 32.65 + i P, run at 42.63 + i P, the second corner chamfered 0.4 + 0.1339 i
    (nested corners at an even pitch)."""
    x = r4(32.65 + P * i)
    y = r4(42.63 + P * i)
    d = r4(0.4 + 0.1339 * i)
    return [(x + 0.4, row), (x, row + 0.4), (x, y - d), (x - d, y)], x, y


def west():
    R = {}
    # DE: lane 0, west at 42.63, down x 29.9 (L6; west of the gap at the +3V3_MCU tongue's west edge, x 30-30.5),
    # over to x 30.2 between the +3V3 / ground vias at y 56-59, SE into its pin
    pts, x, y = lanes(0, 39.6)
    R["LCD_DE"] = go("LCD_DE", pts + [(30.3, y), (29.9, y + 0.4), (29.9, 50.7), (30.2, 51.0), (30.2, 63.0), (34.25, 67.05),
                                      (34.25, YS)], *to_fpc(34.25, YS, 7))
    # MDC: lane 1, via (30.75, 43.8), L1 west at 43.8 between REF's and MDIO's vias, SW, down east of R501.2 into pin 13
    pts, x, y = lanes(1, 40.25)
    R["ETH_MDC"] = go("ETH_MDC", pts + [(31.15, y), (30.75, y + 0.4), (30.75, 43.8)], V(30.75, 43.8),
                      Lp("L1", [(30.75, 43.8), (25.89, 43.8), (24.09, 45.6), (24.09, 47.5), (23.65, 47.94), "U501.13"]))
    # USER_KEY: lane 2, via (31.35, y + 0.4) to L4, SW past the PHY (east of it), down x 28.4, SW to its via, L1 into
    # R811.2 from the north and on to C806.1
    pts, x, y = lanes(2, 40.9)
    vk = (31.35, r4(y + 0.4))
    R["USER_KEY"] = [go("USER_KEY", pts + [(31.75, y), vk], V(*vk),
                        Lp("L4", [vk, (31.35, 44.3), (28.4, 47.25), (28.4, 58.2)]), V(28.4, 58.2),
                        Lp("L3", [(28.4, 58.2), (21.0, 65.6)]), V(21.0, 65.6),
                        Lp("L1", [(21.0, 65.6), "R811.2"])),
                     [Lp("L1", ["R811.2", (21.99, 67.48), "C806.1"])]]
    # G2: one SW diagonal from its run (x 34.31) to the via (31.96, 43.9), parallel to the lanes' corners; L3 down, east
    # at y 45.88 (south of the SDRAM band), down x 49.1, west at 65.2, down into its FPC via
    pcs = lead("LCD_G2")
    lay, run, w = pcs[-1]
    R["LCD_G2"] = pcs[:-1] + [Lp(lay, list(run[:-1]) + [(34.31, 41.55), (31.96, 43.9)]), V(31.96, 43.9),
                              Lp("L3", [(31.96, 43.9), (31.96, 45.48), (32.36, 45.88), (48.7, 45.88), (49.1, 46.28), (49.1, 64.8),
                                        (48.7, 65.2), (44.25, 65.2), (43.75, 65.7), (43.75, YN)]), *to_fpc(43.75, YN, 26)]
    # CRS_DV (re-sited: south exit at x 36.1): L6 down, west at y 43.8 north of the VDDA_MCU pour, via (32.55, 44.3); L1
    # down x 32.4, SW between the ground / +3V3_MCU vias, west along y 49.75 into pin 11 (between R503.2 and the RXER
    # via). The way round keeps CRS_DV longer than REF_CLK (SPEC 9).
    R["RMII_CRS_DV"] = go("RMII_CRS_DV", [(36.1, 43.4), (35.7, 43.8), (33.05, 43.8), (32.55, 44.3)], V(32.55, 44.3),
                          Lp("L1", [(32.55, 44.3), (32.4, 44.45), (32.4, 46.8), (29.45, 49.75), "U501.11"]))
    # REF_CLK / MDIO: L4 west, SW in parallel, vias in the field; L1 west / SW into the PHY
    R["RMII_REF_CLK"] = go("RMII_REF_CLK", [(31.65, 40.9), (29.2, 43.35)], V(29.2, 43.35),
                           Lp("L1", [(29.2, 43.35), (26.01, 43.35), (23.86, 45.5), (23.86, 47.3), (23.15, 48.01), "U501.14"]))
    R["ETH_MDIO"] = [go("ETH_MDIO", [(31.65, 41.55), (28.95, 44.25)], V(28.95, 44.25),
                        Lp("L1", [(28.95, 44.25), (28.95, 45.9), (26.5, 48.35), "R503.2"])),
                     [Lp("L1", ["R503.2", "U501.12"])]]
    return R


# ---------------------------------------------------------------- the x 30 gates down the corridor on L4
def corridor():
    R = {}
    # PHY_NRST: routes_mcu_west.py (stop 7 compose). TXD1: no exit (open): west of the rule area its L3 row (y 33.75) is
    # boxed by the SAI lanes and the vias of FMC_A6 / A10 / ground to the north, CODEC_NRST's L3 row (y 34.4) to the
    # south, the L4 rivers (x 30.9-33.7, no via) and the LSE crystal Y202 to the west; the stub stops east of the crystal
    R["RMII_TXD1"] = go("RMII_TXD1", [(31.3, 33.75)])
    return R


# ---------------------------------------------------------------- open nets: lead and gate only
def open_nets():
    R = {}
    # B6, B7, DISP, TX_EN, TXD0 and PHY_NRST: routes_mcu_west.py. NCS stops south of that group's L3 rows (y 27.75-28.75)
    for net in ("LCD_G7", "LCD_G3", "LCD_BL_PWM"):
        x = exit_of(net)[0]
        R[net] = go(net, [(x, 27.6)])
    R["QSPI_BK1_NCS"] = go("QSPI_BK1_NCS", [(exit_of("QSPI_BK1_NCS")[0], 29.5)])
    for net in ("QSPI_BK1_IO2", "QSPI_BK1_IO3"):
        y = exit_of(net)[1]
        R[net] = go(net, [(32.8, y)])
    return R


NETS = []


def codec_i2c():
    """I2C4 codec side (stop 7 compose): from the link resistors' MCU pads R703.2 / R704.2 by a via each (between
    R704 and R703 / NW of R704), L6 west along y 65.25 / 65.84, a via, L4 north in two lanes at x 22.83 / 22.6
    (west of the PHY block's vias, east of the codec's LDOs) to vias at the codec's north-east corner and L1 into
    U601.8 (SCL, from the north-east: C601 stands east of it) and U601.9 (SDA, from the north); R602 from U601.9's
    second way in. R601 is not reached: U601.8 has this one way in (C601's ground pad east of it, pin 7's tie south)."""
    # lanes x 22.83 / 22.6, east to 24.09 / 23.86 past the PHY's thermal via array (y 49-52) and back west below it (the
    # jogs staggered 0.0933 so the parallel diagonals keep the pitch)
    a1, b1 = 59.2, 48.9
    a2, b2 = r4(a1 + 0.0933), r4(b1 - 0.0933)
    scl = [Lp("L1", ["R703.2", (29.85, 65.89), (29.85, 65.7)]), V(29.85, 65.7),
           Lp("L6", [(29.85, 65.7), (29.4, 65.25), (23.25, 65.25)]), V(23.25, 65.25),
           Lp("L4", [(23.25, 65.25), (22.83, 64.83), (22.83, a2), (24.09, a2 - 1.26), (24.09, b2), (22.83, b2 - 1.26),
                     (22.83, 24.1425), (22.1875, 23.5)]), V(22.1875, 23.5),
           Lp("L1", [(22.1875, 23.5), "U601.8"])]
    sda = [Lp("L1", ["R704.2", (28.6, 65.84)]), V(28.6, 65.84),
           Lp("L6", [(28.6, 65.84), (23.0, 65.84)]), V(23.0, 65.84),
           Lp("L4", [(23.0, 65.84), (22.6, 65.44), (22.6, a1), (23.86, a1 - 1.26), (23.86, b1), (22.6, b1 - 1.26),
                     (22.6, 24.5), (20.75, 22.65)]), V(20.75, 22.65),
           Lp("L1", [(20.75, 22.65), "U601.9"])]
    # SDA's pull-up R602 from U601.9 (its second way in, from the north-east): via, L6 north of the codec's ground via,
    # east along y 22.01 (between the +3V3A / +3V3 vias and the ground via), via north of R602.2
    sda_pu = [Lp("L1", ["U601.9", (21.4, 22.9125)]), V(21.4, 22.9125),
              Lp("L6", [(21.4, 22.9125), (22.6, 21.7125), (24.95, 21.7125), (25.25, 22.0125), (38.1375, 22.0125),
                        (38.4, 21.75)]), V(38.4, 21.75),
              Lp("L1", [(38.4, 21.75), "R602.2"])]
    return {"I2C4_SCL": [scl], "I2C4_SDA": [sda, sda_pu]}


def routes(job):
    R = {}
    for part in (east_bundle, south, qspi, west, corridor, open_nets):
        R.update(part())
    for net, chains in codec_i2c().items():
        R[net] = [R[net]] + chains
    return R
