"""SDRAM bus of the STM32H743 board: the line-order sketch of stop 3 (RTE-13) made the formal routing at stop 6 part A
(SKETCH off: shape findings fail the build). SDRAM at rotation 0, body gap 8 mm. Topology frozen at stop 3; stop 6
changed only via sites, lane coordinates and chamfers (marked "stop 6" below, the sketch's value in the comment).

    sh stm32h743_sdram/build.sh route1            (the real board: this group, then the two power groups, refill, table)
    D:\\KiCad\\bin\\python.exe scripts\\busroute\\build.py stm32h743_sdram\\routes_sdram.py --fast
    SDRAM_BOARD=<copy of the board> ... --fast    (try it on a copy, e.g. one with the power groups stripped)
    D:\\KiCad\\bin\\python.exe scripts\\busroute\\build.py stm32h743_sdram\\routes_sdram.py --sketch --out stm32h743_sdram\\out\\sketch\\rot0
                                                  (the line-order sketch copy, as build.sh layout / copper use it)

Follows stm32h743_sdram/line_order/line_order.txt (layer, way round the MCU, SDRAM ball of every net).
Structure per layer (local mm, MCU centre (40, 37), SDRAM centre (57, 37)):
  L1  l1n   north river: A10 A6 (south side, west about) A3 D28 D29 (west) D30 NBL3 NBL0 D2 (north);
            D29..D2 turn south into the strip to the SDRAM west face, A10 A6 A3 D28 run on to the aisle's north end
      l1e   D3 D24 D20 BA0 D13 D14 from the east side: south through the strip; D3 to M2, the rest east under the
            SDRAM and north into the aisle (D24 in the channel between columns 2 and 3)
      l1s   D11 D12 D9 D8 A11 south about: east below the SDRAM, north up its east side into the east face
  L4 / L3   see the functions below (L3 = SEC).
2026-11-23 (layer order signal / GND / signal / signal / power / signal, user): every piece that ran on L6 runs on L3
at the same coordinates (SEC); the comments below still say L6 where they tell the history of a piece.
Deep balls of L1 nets go down a dog-bone and come back up to L1 through a second 0.30 via inside the MCU rule
area (between the outer ring and the area edge); balls of ring 0-1 of inner-layer nets take a dog-bone via
inside the area (no 0.45 via just outside it: at 0.325 lane pitch there is no room for them).
"""
import os
from busroute import Bundle
from busroute.geom import R2

BOARD = os.environ.get("SDRAM_BOARD", "stm32h743_sdram.kicad_pcb")
ORIGIN = (100, 100)
GROUP = "sdram"
SKETCH = False
REF = ["FMC_SDCLK", "FMC_SDCLK_R"]
VIA_LIMIT = 3
VIA_TARGET = 2
LEN_MAX = 60
ROUND = int(os.environ.get("ROUND", "3"))
DATA = ["FMC_D%d" % i for i in range(32)] + ["FMC_NBL%d" % i for i in range(4)]
ADDR = ["FMC_A%d" % i for i in range(13)] + ["FMC_BA0", "FMC_BA1", "FMC_SDNRAS", "FMC_SDNCAS", "FMC_SDNWE", "FMC_SDCKE0", "FMC_SDNE0"]
GROUPS = {"lane0": ["FMC_D%d" % i for i in range(8)] + ["FMC_NBL0"], "lane1": ["FMC_D%d" % i for i in range(8, 16)] + ["FMC_NBL1"],
          "lane2": ["FMC_D%d" % i for i in range(16, 24)] + ["FMC_NBL2"], "lane3": ["FMC_D%d" % i for i in range(24, 32)] + ["FMC_NBL3"],
          "addr": ADDR, "clock": ["FMC_SDCLK", "FMC_SDCLK_R"]}
YIELD_NETS = ["GND"]
DRC_IGNORE = {"skew_out_of_range": "2026-11-23 tuning (RTE-15): no byte lane reaches the 5 mm of sdram_lane0-3 with tidy serpentines in the "
                                   "room the routed board leaves (compact pass 2026-11-23: lane 0 8.75, lane 1 10.17, lane 2 17.52, lane 3 13.30 mm; limiting nets "
                                   "D7, D9, D19, D26, reported per net in the tuning report); the address / command window "
                                   "(sdram_addr_window) is met and is not ignored"}
# ---- stop 6 part B: length tuning of the four byte lanes (RTE-2, RTE-7, RTE-15; SPEC 9: inside a lane longest -
# shortest <= 5 mm). spread per lane = the window aimed at (5 where the room allows it, see the report for the others);
# end / clr / area_gap / keep are the tool's defaults (not yet confirmed by the user, RTE open question).
# 2026-11-23: the pieces on L6 moved to L3 (SEC). A via L1 - L3 adds 0.2572 mm to a length instead of 1.6504 (L1 - L6), so
# every net that used L6 is 2.786 mm shorter with its two vias; lane 0 (D0 D1 D4-D7 shortest, D0 has no site) and lane 2
# (D18 D19 D21-D23) widen to what their sites reach (stop 6 part B: 11.34 and 18.6); lanes 1 and 3 use no L6 piece.
# 2026-11-23 tuning on the routed board (all groups in place, TUNE_OBSTACLES): each spread is the common target the room
# allows: lane 0 by D7 (inner lane of l6s, no room), lane 1 by D13 (2 humps of 1.975 between BA0 and D14 on its 2.85 mm
# straight), lane 2 by D21 / D22 (inner lanes of l6n), lane 3 by D30 (middle lane of the l1n river); lanes 2 and 3 as
# before (their blocks kept). Stop 8 (review 2): lane 3 13.6 (was 12.74): FMC_D26's lone hump removed, D26 (24.88 mm
# natural) is the lane's shortest and the target (longest D28 38.17 - 13.6 + margin 0.3 = 24.87) lies just below it, so
# D25 / D27 / D31 are matched to D26 (spread about 13.29, was 12.73)
# compact (2026-11-23, user review): l1s pulled in (D9 / D12 / D11 / D8 about 2.5 mm shorter) and l4ss pulled up (D16 /
# D17 2.7 mm shorter). Lane 1's target is D9's natural length (D9 has no room for a block that would not push the
# bundle's outer lanes outwards again): 10.47 (was 9.92). Lane 2: D16 is 2.7 shorter; the target is D19's natural
# length (D19 would otherwise get one lone 0.47 mm hump; D21 / D22 / D23 have no site): 17.83 (was 20.72), D18
# lengthened on its site.
LANE_SPREAD = {"lane0": float(os.environ.get("SPREAD0", "8.76")), "lane1": float(os.environ.get("SPREAD1", "10.47")), "lane2": float(os.environ.get("SPREAD2", "17.83")), "lane3": float(os.environ.get("SPREAD3", "13.6"))}
# 2026-11-23 (user, SPEC 9): every address / command line within 20 mm of the clock, the clock summed across R201;
# the clock is lengthened first (pitch 0.5, radius 0.25), then the short address lines (data pitch)
ADDR_WINDOW = float(os.environ.get("ADDR_WINDOW", "20"))
TUNING = {"groups": dict({g: {"nets": GROUPS[g], "spread": LANE_SPREAD[g]} for g in ("lane0", "lane1", "lane2", "lane3")},
                         addr={"nets": ADDR, "ref": ["FMC_SDCLK", "FMC_SDCLK_R"], "lo": -ADDR_WINDOW, "hi": ADDR_WINDOW}),
          "margin": 0.3, "radius": 0.25, "amp": 0.5, "amp_max": 2.0, "pitch": {"default": 0.3, "FMC_SDCLK": 0.5, "FMC_SDCLK_R": 0.5},
          "end": 0.35, "clr": 0.19, "area_gap": 0.127, "keep": 0.7}
if os.environ.get("NOTUNE"):                 # the natural routes (room surveys: tune_sites.py on a build of this)
    TUNING = None
# the copper of the groups built after this one (build.sh route2: the board as the last build left it); the
# serpentines keep clear of it (tune.py)
TUNE_OBSTACLES = os.environ.get("SDRAM_TUNE_OBSTACLES") or None
# corridors the MCU's other signals use on the SDRAM's layers next to the tuning zones (no serpentine; route1_report
# checks the arcs against them). 2026-11-23, rebuilt from the routed board (every group on it): the other signals'
# tracks on L1 / L3 / L4 within x 46-66, y 26-50 (the strip and round the SDRAM). The serpentines themselves keep
# clear of all other copper through TUNE_OBSTACLES; these boxes are the review check. Was (three-layer state, stop 7
# not routed): L3 33.2-44.3 x 27.4-31.0 and L4 35.9-43.0 x 43.0-48.6, now the MCU groups' real copper.
RESERVED = [("L4", 47.0, 26.6, 62.1, 28.05),            # LCD_BL_PWM along the SDRAM's north side (opt1: L4, was L1 y 27.8)
            ("L1", 46.0, 49.99, 47.25, 50.39),          # LCD_R3 south of the strip
            ("L3", 45.95, 26.0, 46.3, 27.4),            # SDMMC1_D3 north of the MCU's north-east corner
            ("L3", 46.0, 45.88, 49.1, 50.0),            # LCD_G2 below the l6s lanes
            ("L1", 64.3, 42.11, 65.0, 43.69)]           # FB_5V east of the SDRAM
NETS = DATA + ADDR + ["FMC_SDCLK", "FMC_SDCLK_R"]
SEC = "L3"                                 # the bus's second inner layer (L6 until 2026-11-23, then L3: an inner layer next to
                                           # the ground plane L2; the bottom layer keeps the decoupling and the other groups)
LAYERS = os.environ.get("LAYERS", "L1 L3 L4").split()
VIEWS = [("all", 29.0, 26.0, 66.0, 50.0, 40), ("strip", 44.0, 28.0, 54.0, 46.0, 100), ("sdram", 50.0, 28.0, 64.0, 47.0, 80),
         ("mcu", 33.0, 30.0, 47.0, 44.0, 100)]

P = 0.25                                   # lane pitch outside the rule areas
# l6s's east leg under the strip and the SDRAM (compact, 2026-11-23: tried 0.25 mm higher; it shortens FMC_D7, lane 0's
# shortest net, which has no room for a serpentine, so lane 0's spread grows by 0.35: left at 43.6)
L6S_Y0 = float(os.environ.get("L6S_Y0", "43.6"))
L6S_WE = L6S_Y0 + 0.25 * 8
GND_RETURN = [                             # (x, y): the layer changes they serve
    (29.95, 32.2),                         # A10 (30.65, 32.8) and A6 (31.15, 31.9), L4 -> L1 west of the crystal box
    (34.15, 32.95),                        # D28 (33.3, 33.25) L4 -> L1, A3 (32.1, 31.6) has no site of its own
    # (30.45, 39.0) A6 (31.4, 39.0) L1 -> L4 dropped (opt1): A6 now changes layer at (30.66, 41.58), next to Y201's ground
    # via (routes_power.py FIXED)
    (35.45, 31.2),                         # D30 / NBL3 (36.1 / 36.75, 31.6) L4 -> L1, north of the MCU
    (45.45, 32.1),                         # D3 (45.525, 32.775) L3 -> L1 (stop 7 part 2: was (43.375, 32.025), on B13's L6 way north;
                                           # c8: 0.15 east, off SWDIO's L6 step from its via (44.875, 32.125))
    # (45.85, 37.325) D20 L4 -> L1 dropped (c9): D20 now changes layer inside the ball field (L4 -> L3 at (43.575, 37.975),
    # L3 -> L1 at (44.875, 37.975)) among the field's ground ball vias; LCD_HSYNC runs on L6 along that row
    (49.7, 36.5),                          # SDCLK_R (49.0, 36.675; 48.75 until c9) L1 -> L4 beside R201 (stop 7 part 2: was (48.15, 37.375), in the
                                           # L4 way from the pocket under the strip to the pocket south of SDCLK_R; 2026-11-23 tuning: was
                                           # (49.35, 37.3), where the clock now drops straight south on L4; same distance to the clock's via)
    (39.45, 46.45),                        # A11 (40.35, 46.3) L4 -> L1 south of the MCU
]


def V(d, p):
    """Lateral coordinate of point p for a lane travelling in direction d (bundle convention: N . p)."""
    D = {"E": (1, 0), "SE": (1, 1), "S": (0, 1), "SW": (-1, 1), "W": (-1, 0), "NW": (-1, -1), "N": (0, -1), "NE": (1, -1)}[d]
    return -D[1] * p[0] + D[0] * p[1]


def lane_v(d, c):
    """Lateral coordinate of the line `c` for direction d: c = x for N/S legs, y for E/W legs, x - y for SE/NW,
    x + y for NE/SW (the value that is constant along the leg)."""
    return {"E": c, "W": -c, "S": -c, "N": c, "SE": -c, "NW": c, "NE": c, "SW": -c}[d]


def meet_lines(d1, c1, d2, c2):
    """Point where line (d1, c1) meets line (d2, c2)."""
    def form(d, c):                      # a*x + b*y = c
        return {"E": (0, 1), "W": (0, 1), "N": (1, 0), "S": (1, 0), "SE": (1, -1), "NW": (1, -1), "NE": (1, 1), "SW": (1, 1)}[d] + (c,)
    a1, b1, e1 = form(d1, c1)
    a2, b2, e2 = form(d2, c2)
    det = a1 * b2 - a2 * b1
    return (round((e1 * b2 - e2 * b1) / det, 4), round((a1 * e2 - a2 * e1) / det, 4))


def bund(name, nets, layer, legs, start, end, span=None, anchor=None):
    """A bundle from line coordinates: legs = [(direction, {net: c})], c as in lane_v, for the nets present on
    that leg (lanes absent on a leg, see span, are put 0.3 mm beyond their present neighbour for the gaps).
    start / end = station of the anchor (nets[0]) on the first / last leg: x for E/W/diagonal legs, y for N/S."""
    a = anchor or nets[0]
    cs, gaps = [], {}
    for k, (d, c) in enumerate(legs):
        sc = R2 if d in ("SE", "NW", "NE", "SW") else 1.0
        vs = {n: lane_v(d, c[n]) for n in c}
        idx = [i for i, n in enumerate(nets) if n in vs]
        if not idx:
            raise ValueError("%s leg %d: no lane" % (name, k))
        for i, n in enumerate(nets):
            if n not in vs:
                before = [j for j in idx if j < i]
                after = [j for j in idx if j > i]
                if before:
                    vs[n] = vs[nets[before[-1]]] + 0.3 * sc * (i - before[-1]) / (1 if not after else (after[0] - before[-1]))
                else:
                    vs[n] = vs[nets[after[0]]] - 0.3 * sc * (after[0] - i)
        full = {n: {"E": 1, "W": -1, "S": -1, "N": 1, "SE": -1, "NW": 1, "NE": 1, "SW": -1}[d] * vs[n] for n in nets}
        cs.append((d, full))
        g = [round((vs[nets[i + 1]] - vs[nets[i]]) / sc, 12) for i in range(len(nets) - 1)]
        if g and min(g) <= 0:
            raise ValueError("%s leg %d (%s): lanes not in order, gaps %s" % (name, k, d, g))
        gaps[k] = g
    def pt(d, c, s):
        return (s, c) if d in ("E", "W") else (c, s) if d in ("N", "S") else (s, s - c) if d in ("SE", "NW") else (s, c - s)
    path = [pt(cs[0][0], cs[0][1][a], start)]
    for k in range(len(cs) - 1):
        path.append(meet_lines(cs[k][0], cs[k][1][a], cs[k + 1][0], cs[k + 1][1][a]))
    path.append(pt(cs[-1][0], cs[-1][1][a], end))
    return Bundle(name, nets, layer, path=[(round(x, 4), round(y, 4)) for x, y in path], pitch=P, gaps=gaps, anchor=a, span=span)


def ext(lead, pts):
    """A lead whose last piece runs on through `pts`."""
    lead = [tuple(pc) for pc in (lead.pieces if hasattr(lead, "pieces") else lead)]
    return list(lead[:-1]) + [(lead[-1][0], list(lead[-1][1]) + list(pts))]


def trim(lead, d):
    """A lead whose last segment ends `d` mm earlier."""
    pcs = [tuple(pc) for pc in (lead.pieces if hasattr(lead, "pieces") else lead)]
    lay, pts = pcs[-1]
    a, b = pts[-2], pts[-1]
    L = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
    end = (round(b[0] - d * (b[0] - a[0]) / L, 4), round(b[1] - d * (b[1] - a[1]) / L, 4))
    return pcs[:-1] + [(lay, list(pts[:-1]) + [end])]


def surface(lead, at, axis):
    """Cut an inner-layer escape lead at x (axis 'x') or y (axis 'y') = at, put a 0.30 via there and continue on
    L1 to where the lead ended (the rule-area edge)."""
    pcs = [list(pc) if pc[0] != "via" else pc for pc in lead.pieces]
    last = pcs[-1]
    lay, pts = last[0], list(last[1])
    end = pts[-1]
    cut = (at, end[1]) if axis == "x" else (end[0], at)
    pts = pts[:-1] + [cut]
    return [tuple(pc) if pc[0] == "via" else (pc[0], pc[1]) for pc in pcs[:-1]] + [(lay, pts), ("via", cut), ("L1", [cut, end])]


def routes(job):
    B = job.board

    def db(ball, via, lay, pts):
        """A dog-bone written by hand: ball -> via (L1), then `pts` on layer `lay` from the via."""
        return [("L1", ["U201." + ball, via]), ("via", via), (lay, [via] + list(pts))]
    # ---- hand-written MCU leads (where the rule-based fan-out has no room)
    hand = {
        # south side, L6 river: order east -> west D6 D7 D4 D5 A8 A9 A7 RAS
        "FMC_D6": db("P9", (40.975, 40.575), SEC, [(41.3, 40.9), (41.3, 43.0)]),
        # stop 6 (U31): D7, D5, A9 and A7 take other via sites (sketch in brackets), found by a search over the sites of
        # this cluster (out/route1/tmp/cluster2.py): the antipads of the cluster no longer join the vias of D6, D10 and the
        # N8-N10 supply balls into one slot on L2 / L5 (3.32 mm at stop 5); lanes, layers and order unchanged.
        # D7: straight down from R9 to (40.65, 42.2), below row R [NW site (40.325, 41.225)]
        "FMC_D7": [("L1", ["U201.R9", (40.65, 42.2)]), ("via", (40.65, 42.2)), (SEC, [(40.65, 42.2), (40.65, 43.0)])],
        "FMC_D4": db("R8", (40.325, 41.875), SEC, [(40.325, 43.0)]),
        "FMC_D5": db("P8", (39.675, 41.225), SEC, [(40.0, 41.55), (40.0, 43.0)]),            # SW [NW (39.675, 40.575)]
        "FMC_A8": db("R7", (39.675, 41.875), SEC, [(39.675, 43.0)]),
        "FMC_A9": db("P7", (39.025, 40.575), SEC, [(39.025, 43.0)]),     # NW, lane x 39.025 [SE (39.675, 41.225), lane x 39.35]
        "FMC_A7": db("N6", (38.375, 40.575), SEC, [(38.7, 40.9), (38.7, 43.0)]),     # SW [SE (39.025, 40.575)]
        "FMC_SDNRAS": db("R6", (38.375, 41.875), SEC, [(38.375, 43.0)]),
        # L1 nets with deep balls on the south side
        # A11 surfaces with a 45 degree step on L4, so that the track does not turn 90 degrees across its via (sketch:
        # L4 straight down to (40.0, 46.3), L1 east from there)
        # compact (2026-11-23, user review "pull the bus in"): A11's via stays (LCD_G2 runs on L3 at y 45.88 just north
        # of it); on L1 it runs east 1.65 mm and steps NE up onto its lane (y 45.6, was 46.3), clear of D8's corner
        "FMC_A11": db("M7", (39.675, 39.925), "L4", [(40.0, 40.25), (40.0, 45.95), (40.35, 46.3)]) + [("via", (40.35, 46.3)), ("L1", [(40.35, 46.3), (42.0, 46.3), (42.7, 45.6)])],
        # round 3 (user): no SDRAM track on L1 beside the crystal pins E1-H1 (box x 29-34, y 33.5-38.5). A10, A3 and D28
        # pass the west side on L4 and come up to L1 north of the box; A6 goes down south of it (see l1n)
        # stop 7 part 2: A10's west leg runs on the row-L line (y 38.95) instead of y 39.925 and steps down to y 39.5
        # west of the ball field, below A6's via (31.4, 39.0): L4 south of row L is then free for the MCU's
        # south-west signal balls (rows L-R), which have no other way out (L1 is closed by A6, L6 by WE and the VDDA
        # filter). Same layer, side and order; 0.59 mm longer
        # opt1 (review 1, defect: no foreign copper on L1 at the crystals): A6 no longer comes up between Y201's pads;
        # A10 keeps its step down to y 39.5 (under Y201.4's ground via (32.25, 38.85)) and goes north at x 31.2, east of
        # A6's new L4 lane (x 30.66); its via moves from (30.65, 32.8), 0.3 mm from Y202's LSE_IN pad, to (31.2, 32.8)
        # (0.98 mm), south of A6's via, and L1 steps north-west onto its lane. 0.18 mm shorter
        "FMC_A10": db("N7", (39.025, 39.925), "L4", [(39.025, 39.275), (38.7, 38.95), (33.5, 38.95), (32.95, 39.5), (31.45, 39.5),
                                                      (31.2, 39.25), (31.2, 32.8)])
                   + [("via", (31.2, 32.8)), ("L1", [(31.2, 32.8), (30.65, 32.25)])],
        "FMC_A3": db("J2", (35.775, 37.975), "L4", [(32.3, 37.975), (31.9, 37.575), (31.9, 31.8), (32.1, 31.6)])
                  + [("via", (32.1, 31.6)), ("L1", [(32.1, 31.6), (32.1, 31.3)])],
        "FMC_D28": db("C3", (37.075, 34.075), "L4", [(36.75, 34.4), (33.7, 34.4), (33.3, 34.0), (33.3, 33.25)])
                   + [("via", (33.3, 33.25)), ("L1", [(33.3, 33.25), (33.3, 32.95)])],
        # L4 under the MCU (ball-free ring rows E / L, between the centre vias), out on the east side
        "FMC_D31": db("E3", (37.075, 35.375), "L4", [(37.4, 35.05), (46.0, 35.05)]),
        "FMC_SDCKE0": db("F4", (37.725, 36.025), "L4", [(38.05, 35.7), (46.0, 35.7)]),
        "FMC_A4": db("J3", (37.075, 37.325), "L4", [(37.4, 37.65), (46.0, 37.65)]),
        # try/sgsps (BGA block): A5 steps from row K (y 38.3) to the gap row y 38.625 before the area edge, so that TP_INT
        # (K15) can take a via at (45.8, 38.3) between D20's and BA0's L1 lanes (stop 7: K15 had no way out)
        "FMC_A5": db("K3", (37.075, 38.625), "L4", [(37.4, 38.3), (44.9, 38.3), (45.225, 38.625), (46.0, 38.625)]),
        "FMC_D10": db("N11", (41.625, 39.925), "L4", [(41.625, 39.275), (41.95, 38.95), (46.0, 38.95)]),
        # BA1 on L6 (plan: L4): on L4 its ball H8, entered from the aisle's south end, sits between the balls of
        # NE0 / CAS / NBL1 entered from the north end (J8, K7, K9): no way through without a crossing
        # stop 8 (review 2, b6): the NE step 0.85 east (x 50.15, was 49.3) so that BA1's straight holds the strip zone's
        # three-hump block (x 47.6 - 49.4, as A12 / D1 / D0); same length (the step only moves along the corner)
        "FMC_BA1": db("K13", (43.575, 38.625), SEC, [(50.15, 38.625), (52.575, 36.2), (58.6, 36.2), (59.0, 36.6)])
                   + [("via", (59.0, 36.6)), ("L1", [(59.0, 36.6), "U301.H8"])],
        # east side, rows chosen so that every inner layer leaves in the river order
        # stop 7 part 2: D3 surfaces one column further east, after an L6 leg along the row-B line (sketch / stop 6:
        # via at (43.575, 32.775), B13's north-east quadrant): SDMMC1_D3 (B13) can then take that site and go north on
        # L6. Same layers, side and lane; length unchanged (0.65 mm more on L6, 0.65 mm less on L1)
        # stop 7 c8: D3 stays on L3 two columns further, along the row-B line to the gap east of B15, and surfaces at
        # (45.525, 32.775) off the lattice: SDMMC1_D2 (B14) takes (44.225, 32.775). Same layers, side and lane; length
        # unchanged (1.3 mm more on L3, 1.3 mm less on L1)
        "FMC_D3": db("C12", (42.925, 33.425), SEC, [(43.25, 33.1), (45.2, 33.1), (45.525, 32.775)]) + [("via", (45.525, 32.775)), ("L1", [(45.525, 32.775), (46.0, 32.775)])],
        # c9: D20 leaves row J/K's gap line before J15's south-west site (LCD_R7's dog-bone via now): a via at (43.575,
        # 37.975), L3 along row K (between the vias of the gap rows) and up into the site south-east of J15, L1 east as
        # before. Same side, way round, lane; +0.27 mm, the via heights add up as before (L1-L4-L3-L1 = 2 x L1-L4)
        "FMC_D20": db("K12", (42.275, 37.975), "L4", [(43.575, 37.975)]) + [("via", (43.575, 37.975)),
                   ("L3", [(43.575, 37.975), (43.9, 38.3), (44.55, 38.3), (44.875, 37.975)]), ("via", (44.875, 37.975)),
                   ("L1", [(44.875, 37.975), (46.0, 37.975)])],
        "FMC_D23": db("D13", (43.575, 34.075), SEC, [(43.9, 33.75), (46.0, 33.75)]),
        "FMC_D22": db("E13", (43.575, 34.725), SEC, [(43.9, 34.4), (46.0, 34.4)]),
        "FMC_D21": db("E12", (42.925, 35.375), SEC, [(43.25, 35.05), (46.0, 35.05)]),
        "FMC_D19": db("L12", (42.275, 39.275), SEC, [(41.95, 38.95), (41.95, 36.675), (42.275, 36.35), (46.0, 36.35)]),
        "FMC_D18": db("L13", (42.925, 38.625), SEC, [(42.925, 37.325), (43.25, 37.0), (46.0, 37.0)]),
        "FMC_A12": db("L15", (44.875, 39.275), SEC, [(45.2, 38.95), (46.0, 38.95)]),
        "FMC_D1": db("L14", (44.225, 39.275), SEC, [(44.55, 39.6), (46.0, 39.6)]),
        "FMC_D0": db("M14", (44.225, 39.925), SEC, [(44.55, 40.25), (46.0, 40.25)]),
        "FMC_D26": db("C14", (44.225, 33.425), "L4", [(44.55, 33.1), (46.0, 33.1)]),
        "FMC_D27": db("C13", (43.575, 33.425), "L4", [(43.9, 33.75), (46.0, 33.75)]),
        "FMC_D25": db("D14", (44.225, 34.075), "L4", [(44.55, 34.4), (46.0, 34.4)]),
        # round 2 (user, 2026-11-21): A1 A0 NBL2 from L6 to L4, so that L6 carries no SDRAM track north or west of the MCU.
        # A1 leaves on row K, south of A2, as the outer lane of the L4 north river
        "FMC_A1": db("H3", (36.425, 37.325), "L4", [(36.425, 37.975), (36.1, 38.3), (34.0, 38.3)]),
        "FMC_A0": db("E2", (35.775, 35.375), "L4", [(35.45, 35.7), (34.0, 35.7)]),
        # try/sgsps (BGA block): A2 leaves its via west along the gap row y 37.325 (rule-based lead: row J, y 37.65), so
        # that NRST (J1) can take a via at (34.65, 37.65) between A2 and A3 on L4 (its four gap sites are taken)
        "FMC_A2": db("H2", (35.775, 37.325), "L4", [(34.0, 37.325)]),
        "FMC_NBL2": db("D4", (37.725, 34.075), "L4", [(38.05, 33.75), (38.05, 31.0)]),
    }
    fo = job.fanout("U201")
    req = {
        # L1 river
        "P11": "S+:L1", "R11": "S", "R10": "S", "P10": "S-:L1", "P6": "S+:L1",
        "E14": "E+:L1", "K14": "E+:L1", "P15": "E", "P14": "E+:L1",
        "A4": "N", "B12": "N", "D3": "N-:via@L4", "C4": "N-:via@L4",
        "C2": "W-:L1",
        "H14": "E-:L1",
        # inner rivers
        "N15": "E:via@L4",
        "A3": "N:via@L4", "B7": "N:via@L4",
        "G4": "W:via@L4", "J4": "W:via@" + SEC,
        "M13": "S:via@L4", "M12": "S:via@L4",
    }
    for k, v in list(req.items()):
        if os.environ.get("REQ_" + k):
            req[k] = os.environ["REQ_" + k]
    res = fo.escape(req, inner=("L4", SEC), l1_depth=1, keep=hand)
    job.refused(res)
    job.notes.append(res.text())
    m = res.by_net()
    if os.environ.get("DUMP"):
        with open(os.environ["DUMP"], "w") as f:
            f.write(res.text() + "\n")
            for l in sorted(res.leads.values(), key=lambda l: (l.side, l.layer, l.lat)):
                f.write("%s %s %s %s %s %s\n" % (l.side, l.layer, l.net, l.ball, l.kind, [pc[1] if pc[0] == "via" else pc[1][-1] for pc in l.pieces][-2:]))
    m.update(hand)
    # stop 7 compose: D2 (B12) leaves north between A11 (unconnected) and A12 (x 42.275, over the +3V3_MCU feed column
    # on L1, no via there) instead of between A12 and A13 (x 42.925): SDMMC1_CK (A12) takes the site (42.925, 32.125)
    # and runs north on L3. Set after the rule-based escape so that no other lead changes; same layer, lane and order
    m["FMC_D2"] = [("L1", ["U201.B12", (42.275, 32.775), (42.275, 31.0)])]
    bus = job.bus()
    R = {}

    # ---------------------------------------------------------------- L1
    # deep balls of L1 nets: up again inside the rule area
    s_d3, s_d20 = m["FMC_D3"], m["FMC_D20"]
    s_d30 = surface(m["FMC_D30"], 31.6, "y")
    s_nbl3 = surface(m["FMC_NBL3"], 31.6, "y")
    s_d28 = m["FMC_D28"]
    a11, a10 = m["FMC_A11"], m["FMC_A10"]

    if "L1" in LAYERS:
        # l1n: A10 A6 A3 D28 D29 (west, from their vias north of the crystal box) | D30 NBL3 NBL0 D2 (north)
        n_all = ["FMC_A10", "FMC_A6", "FMC_A3", "FMC_D28", "FMC_D29", "FMC_D30", "FMC_NBL3", "FMC_NBL0", "FMC_D2"]
        north = {"FMC_A10": 30.65, "FMC_A6": 31.15, "FMC_A3": 32.1, "FMC_D28": 33.3, "FMC_D29": 33.75}
        ye = {"FMC_A10": 28.8, "FMC_A6": 29.05, "FMC_A3": 29.3, "FMC_D28": 29.55, "FMC_D29": 29.8, "FMC_D30": 30.05,
              "FMC_NBL3": 30.3, "FMC_NBL0": 30.55, "FMC_D2": 30.8}
        ne = {n: north[n] + ye[n] + 0.6 for n in north}
        xs = {"FMC_D29": 51.75, "FMC_D30": 51.5, "FMC_NBL3": 51.25, "FMC_NBL0": 51.0, "FMC_D2": 50.75}
        se = {n: xs[n] - ye[n] - 0.6 for n in xs}
        legs = [("N", north), ("NE", ne), ("E", ye), ("SE", se), ("S", xs)]
        span = {"FMC_A10": (0, 2), "FMC_A6": (0, 2), "FMC_A3": (0, 2), "FMC_D28": (0, 2), "FMC_D29": (0, 3),
                "FMC_D30": (2, 3), "FMC_NBL3": (2, 4), "FMC_NBL0": (2, 4), "FMC_D2": (2, 4)}
        l1n = bund("l1n", n_all, "L1", legs, 33.2, 41.0, span, anchor="FMC_D29")
        # stop 6 part B: D29 / D30 / NBL3 (lane 3) get no site: the room south of D2 down to D3 (y 32.775) is reserved for
        # the stop-7 escapes of the MCU's east side (main session, 2026-11-22); the other sides are lanes or the SDRAM area
        # A6: L1 west below the MCU, up the west side to y 39.0, L4 past the crystal box, L1 again at (31.15, 31.9)
        # opt1 (review 1 defect): A6 ran on L1 between the HSE crystal's pads to a via at the crystal's centre (31.4, 39.0).
        # Now it drops to L4 south of the crystal (30.66, 41.58; 0.65 mm below Y201's ground pad, north of REF_CLK's L4
        # diagonal) and runs north on L4 at x 30.66 west of A10 (the two cross by A10 surfacing first at (31.2, 32.8)
        # and A6 passing north of that via to its old via). West leg at y 43.3 (was 43.5); 0.08 mm longer
        a6 = [("L1", list(m["FMC_A6"].pieces[0][1]) + [(38.725, 43.3), (32.38, 43.3), (30.66, 41.58)]), ("via", (30.66, 41.58)),
              ("L4", [(30.66, 41.58), (30.66, 32.39), (31.15, 31.9)]), ("via", (31.15, 31.9)), ("L1", [(31.15, 31.9), (31.15, 31.6)])]
        st = {"FMC_A6": a6, "FMC_A10": a10, "FMC_A3": m["FMC_A3"], "FMC_D28": s_d28, "FMC_D29": m["FMC_D29"],
              "FMC_D30": s_d30, "FMC_NBL3": s_nbl3, "FMC_NBL0": m["FMC_NBL0"], "FMC_D2": trim(m["FMC_D2"], 0.1)}
        # stop 6: D29 runs its SE leg on to row A (x - y = 21.35 meets y 31.4 at x 52.75); sketch: down the S leg to
        # (51.75, 31.2) and a 0.283 mm chamfer (SHARP)
        en = {"FMC_D29": [(52.75, 31.4), "U301.A1"],
              "FMC_D30": [(53.05, 32.2), "U301.B1"],      # stop 6: on along its SE leg to row B, like D29 (sketch: S leg and SE step)
              "FMC_NBL3": [(51.25, 34.6), (51.65, 35.0), (54.2, 35.0), "U301.F2"],
              "FMC_NBL0": [(51.0, 38.0), (51.6, 38.6), "U301.K1"],
              "FMC_D2": [(50.75, 38.6), (51.15, 39.0), (54.2, 39.0), "U301.L2"]}
        bus.add(l1n, start=st, end=en)
        # l1a: A10 A6 A3 D28 on to the aisle's north end
        a_n = ["FMC_A10", "FMC_A6", "FMC_A3", "FMC_D28"]
        xa = {"FMC_A6": 56.35, "FMC_A3": 56.1, "FMC_D28": 55.85}
        l1a = bund("l1a", a_n, "L1", [("E", {n: ye[n] for n in a_n}), ("SE", {n: xa[n] - ye[n] - 0.4 for n in xa}), ("S", xa)],
                   48.0, 33.0, {"FMC_A10": (0, 0)})
        bus.add(l1a, end={"FMC_A10": [(59.0, 29.3), (59.0, 35.8), "U301.G7"],
                          "FMC_D28": [(55.85, 33.35), "U301.D3"],
                          "FMC_A3": [(56.1, 34.7), "U301.F3"],
                          "FMC_A6": [(56.35, 35.25), "U301.G3"]})

        # l1e: D3 D24 D20 BA0 D13 D14 (going E, left = north)
        e_n = ["FMC_D3", "FMC_D24", "FMC_D20", "FMC_BA0", "FMC_D13", "FMC_D14"]
        y0 = {"FMC_D3": s_d3[-1][1][-1][1], "FMC_D24": m["FMC_D24"].end[1], "FMC_D20": s_d20[-1][1][-1][1],
              "FMC_BA0": m["FMC_BA0"].end[1], "FMC_D13": m["FMC_D13"].end[1], "FMC_D14": m["FMC_D14"].end[1]}
        y0["FMC_D3"] = s_d3[-1][1][-1][1]
        xs = {"FMC_D3": 50.45, "FMC_D24": 50.2, "FMC_D20": 49.95, "FMC_BA0": 49.7, "FMC_D13": 49.45, "FMC_D14": 49.2}
        se = {n: xs[n] - y0[n] - 0.3 for n in e_n}
        # compact (2026-11-23): the east leg under the SDRAM 0.2 mm higher (D24 hole to copper 0.2 from the vias of row y 43.0)
        yb = {"FMC_D24": 43.35, "FMC_D20": 43.6, "FMC_BA0": 43.85, "FMC_D13": 44.1, "FMC_D14": 44.35}
        se2 = {n: xs[n] - yb[n] + 0.4 for n in yb}
        xn = {"FMC_D20": 57.1, "FMC_BA0": 57.4, "FMC_D13": 57.7, "FMC_D14": 58.0}
        ne = {n: xn[n] + yb[n] - 0.4 for n in xn}
        # legs: 0 E, 1 SE, 2 S, 3 SE, 4 E, 5 NE, 6 N
        legs = [("E", y0), ("SE", se), ("S", xs), ("SE", se2), ("E", yb), ("NE", ne), ("N", xn)]
        l1e = bund("l1e", e_n, "L1", legs, 46.5, 34.0, {"FMC_D3": (0, 2), "FMC_D24": (0, 4)})
        # stop 6 part B: D13 (lane 1) humps north on its straight out of the MCU (station = x - 46.5), into the room
        # below BA0 (y 38.625); its south side and every side of D14 are reserved for the stop-7 escapes
        l1e.slot("FMC_D13", 0, 46.3 - 46.5, 49.15 - 46.3, side="L")
        # 2026-11-23 tuning: D14, the outer lane, humps south on the same straight into the free L1 room west of its
        # south leg (the ground pour gives way); both blocks start 0.7 after the rule-area side of the site
        l1e.slot("FMC_D14", 0, 46.3 - 46.5, 48.9 - 46.3, side="R")
        bus.add(l1e, start={"FMC_D3": s_d3, "FMC_D24": m["FMC_D24"], "FMC_D20": s_d20, "FMC_BA0": m["FMC_BA0"],
                            "FMC_D13": m["FMC_D13"], "FMC_D14": m["FMC_D14"]},
                end={"FMC_D3": [(50.45, 39.2), (51.05, 39.8), (54.2, 39.8), "U301.M2"],
                     "FMC_D24": [(55.0, 43.0), (55.0, 33.4), "U301.C3"],
                     "FMC_D20": [(57.1, 35.3), "U301.D7"],
                     "FMC_BA0": [(57.4, 39.0), "U301.J7"],
                     "FMC_D13": [(57.7, 41.1), "U301.M7"],
                     "FMC_D14": [(58.0, 41.6), "U301.N7"]})

        # l1s: D11 D12 D9 D8 (+ A11) going S (left = east), then E, then N up the SDRAM's east side
        s_n = ["FMC_D11", "FMC_D12", "FMC_D9", "FMC_D8", "FMC_A11"]
        xs = {"FMC_D11": 42.275, "FMC_D12": 41.95, "FMC_D9": 41.3, "FMC_D8": 40.975}
        # compact (2026-11-23, user review): the east leg right under l1e's (0.25 below D14, was 0.75 lower) and the
        # north leg up the SDRAM's east side inside its rule area (was x 61.6 - 62.6 at 0.25): D11 0.3 mm east of the
        # col-9 vias; D12 / D9 / D8 / A11 as far west as their entries into the east face allow without three
        # bends inside 2 mm (track_shape crowded): D12 and D8 need about 2 mm from their NW turn to the SW step into the
        # ball. The south-east corners are 1.0 mm diagonals (0.6 before) for the same reason
        ys = {"FMC_D11": 44.6, "FMC_D12": 44.85, "FMC_D9": 45.1, "FMC_D8": 45.35, "FMC_A11": 45.6}
        se = {n: xs[n] - ys[n] + 0.3 for n in xs}
        # D11 leaves the east leg on one NE diagonal straight into R9 (no north leg: three bends inside 1.2 mm otherwise)
        xe = {"FMC_D12": 61.45, "FMC_D9": 61.65, "FMC_D8": 61.85, "FMC_A11": 62.1}
        ne = {n: xe[n] + ys[n] - 1.0 for n in xe}
        legs = [("S", xs), ("SE", se), ("E", ys), ("NE", ne), ("N", xe)]
        l1s = bund("l1s", s_n, "L1", legs, 43.0, 40.0, {"FMC_A11": (2, 4), "FMC_D11": (0, 2)})
        # 2026-11-23 tuning: D11 (lane 1), the north lane of the east leg below the MCU, humps north into the free L1
        # room under the MCU area (station = x - 42.575, D11's corner)
        # compact (2026-11-23): the shorter east leg leaves D12 (lane 1) below the lane's target. D11's site shrinks to
        # x 42.95 - 45.55 and D12 gets x 46.3 - 48.5 next to it, humping north with D11 stepped north over it (free =
        # hump + 0.19 + track); both under the MCU's south edge, away from the outside of the bus (a block humping south
        # would push D9 / D8 / A11 out again). Was: D11 alone, x 43.0 - 48.5
        l1s.slot("FMC_D11", 2, 42.95 - 42.575, 2.6, side="L")
        l1s.slot("FMC_D12", 2, 46.3 - 42.575, 2.2, side="L", free=0.92)
        bus.add(l1s, start={"FMC_D11": m["FMC_D11"], "FMC_D12": m["FMC_D12"], "FMC_D9": m["FMC_D9"], "FMC_D8": m["FMC_D8"], "FMC_A11": a11},
                end={"FMC_D11": ["U301.R9"],
                     "FMC_D12": [(61.45, 43.2), (60.45, 42.2), (59.8, 42.2), "U301.R8"],
                     "FMC_D9": [(61.65, 42.5), (60.95, 41.8), "U301.P9"],
                     "FMC_D8": [(61.85, 41.85), (61.4, 41.4), (59.8, 41.4), "U301.N8"],
                     "FMC_A11": [(62.1, 37.25), (61.85, 37.0), "U301.H9"]})
    # ---------------------------------------------------------------- SEC (L3; L6 until 2026-11-23)
    def via_end(pts, via, ball, lay=SEC):
        """End terminal: `pts` on the inner layer, a 0.30 via, the dog-bone to the SDRAM ball on L1."""
        return [(lay, list(pts) + [via]), ("via", via), ("L1", [via, "U301." + ball])]

    if SEC in LAYERS:
        # l6n: D23 D22 D21 D19 D18 up the strip, east along the SDRAM's north side (D19 / D18 leave there)
        n6 = ["FMC_D23", "FMC_D22", "FMC_D21", "FMC_D19", "FMC_D18"]
        y0 = {"FMC_D23": 33.75, "FMC_D22": 34.4, "FMC_D21": 35.05, "FMC_D19": 36.35, "FMC_D18": 37.0}
        xn = {"FMC_D23": 47.25, "FMC_D22": 47.5, "FMC_D21": 47.75, "FMC_D19": 48.0, "FMC_D18": 48.25}
        ye = {"FMC_D23": 29.0, "FMC_D22": 29.25, "FMC_D21": 29.5, "FMC_D19": 29.75, "FMC_D18": 30.0}
        xs = {"FMC_D23": 61.6, "FMC_D22": 61.35, "FMC_D21": 61.1}
        # stop 6 part B: east of x 49 (the strip and the room north of the east leg west of x 49 are reserved for stop 7)
        # the east leg steps north on one nested NE jog (leg 5): D23 D22 D21 D19 by J6 (D23 to y 27.75; limit 27.7), D18 by
        # J18, out of the SDRAM area, so that D18 (lane 2's shortest) humps north into the gap D18 - D19. Sketch: no jog.
        J6, J18 = float(os.environ.get("J6", "1.25")), float(os.environ.get("J18", "0.68"))
        jj = {"FMC_D23": 49.75, "FMC_D22": 49.854, "FMC_D21": 49.958, "FMC_D19": 50.062, "FMC_D18": 50.166}   # jog starts (x), > 2 mm after the corners
        ye2 = {n: ye[n] - (J18 if n == "FMC_D18" else J6) for n in ye}
        legs = [("E", y0), ("NE", {n: xn[n] + y0[n] - 0.4 for n in y0}), ("N", xn), ("NE", {n: xn[n] + ye[n] + 0.4 for n in xn}),
                ("E", ye), ("NE", {n: jj[n] + ye[n] for n in ye}), ("E", ye2), ("SE", {n: xs[n] - ye2[n] - 0.4 for n in xs}), ("S", xs)]
        span = {"FMC_D19": (0, 6), "FMC_D18": (0, 6)}
        l6n = bund("l6n", n6, SEC, legs, 46.5, 40.0, span, anchor="FMC_D23")
        l6n.slot("FMC_D18", 6, 51.0 - (49.75 + J6), 55.6 - 51.0, side="L")     # station = x - D23's jog end
        l6n.slot("FMC_D19", 6, 55.2 - (49.75 + J6), 58.0 - 55.2, side="R")     # D19 humps south into the same gap, after D18's block
        bus.add(l6n, start={n: m[n] for n in n6},
                end={"FMC_D18": via_end([(57.8, 30.4), (57.8, 32.2)], (58.2, 32.6), "C7"),
                     "FMC_D19": via_end([(59.35, 29.75)], (60.6, 31.0), "A9"),     # one SE step from the lane (sketch: SE, S, SE: `crowded`)
                     "FMC_D21": via_end([(61.1, 33.0), (60.7, 33.4)], (59.8, 33.4), "C8"),
                     # try/sgsps (BGA block): D22 crosses to its via along ball row D (y 33.8), not the gap row y 34.2,
                     # so that the supply ball D9 gets the gap site (60.6, 34.2) as its own via (stop 5: it shared C9's)
                     "FMC_D22": via_end([(61.35, 33.4), (60.95, 33.8), (60.2, 33.8)], (59.8, 34.2), "D8"),
                     "FMC_D23": via_end([(61.6, 34.6), (61.2, 35.0)], (59.8, 35.0), "E8")})
        # l6e: A12 D1 D0 straight to the west face (D1 enters M3 from the west face, not through the aisle)
        # stop 6: A12 leaves its via along the gap row y 39.275 (sketch: NE step to y 38.95 and E: a 90 degree turn across
        # the via); same length
        # 2026-11-23 tuning: D1 and D0 step down out of the MCU area (one SE diagonal each, x 46.5) into the free L3
        # pocket south of them (bounded by the l6s lanes at y 43.6 and D6's NE diagonal), so that A12, D1 and D0 each
        # get a row of humps southwards on their straights, the blocks starting on one line (RTE-7). Was: D1 along y
        # 39.6 and D0 along y 40.25 straight to their NE steps (50.4 / 50.2), no site for either
        # stop 8 (review 2, b6): one tuning zone of four blocks of three humps each, all from x 47.6 to 49.4 (BA1 north,
        # A12 / D1 / D0 south). A12's block on its 45-degree diagonal is gone: its straight runs 0.525 further east (NE
        # step at x 50.2, same length; the diagonal x + y = 89.475 keeps 0.18 mm from the SDRAM's ground via (52.6,
        # 37.4)) and its whole need goes into one taller block. D1 and D0 leave their leads on their SE diagonals at x
        # 45.3 (east of the ball field's last via column, was 46.35) and run 0.35 / 0.3 mm lower (rows 40.75 / 41.75),
        # so that A12's taller humps fit above D1 and both lane-0 corners lie west of the zone's start. Was: BA1 two
        # humps from 47.0, A12 three from 47.05 plus three on its diagonal, D1 three and D0 four from 48.25
        D1Y, D0Y = float(os.environ.get("D1Y", "40.75")), float(os.environ.get("D0Y", "41.75"))
        DX, ZS, ZE = 45.3, 46.9, 50.15          # the lane-0 drops; the zone's sites (first arc at ZS + keep = 47.6, three humps)
        bus.keep({"FMC_A12": m["FMC_A12"][:-1] + [(SEC, [(44.875, 39.275), (50.2, 39.275), (52.875, 36.6)] + [(55.8, 36.6)])]
                  + [("via", (55.8, 36.6)), ("L1", [(55.8, 36.6), "U301.H3"])],
                  "FMC_D1": m["FMC_D1"][:-1] + [(SEC, [(44.225, 39.275), (44.55, 39.6), (DX, 39.6), (DX + D1Y - 39.6, D1Y),
                                                       (50.8, D1Y), (50.8 + D1Y - 39.8, 39.8), (55.8, 39.8)])]
                  + [("via", (55.8, 39.8)), ("L1", [(55.8, 39.8), "U301.M3"])],
                  # opt1 (review 1): D0 stays on its row 1 mm further east (NE step at x 51.4, was 50.4)
                  "FMC_D0": m["FMC_D0"][:-1] + [(SEC, [(44.225, 39.925), (44.55, 40.25), (DX, 40.25), (DX + D0Y - 40.25, D0Y),
                                                       (51.4, D0Y), (51.4 + D0Y - 40.6, 40.6), (54.2, 40.6)])]
                  + [("via", (54.2, 40.6)), ("L1", [(54.2, 40.6), "U301.N2"])]})
        job.slot("FMC_A12", SEC, (ZS, 39.275), (ZE, 39.275), side="R")                   # going east, R = south
        job.slot("FMC_D1", SEC, (ZS, D1Y), (ZE, D1Y), side="R")
        job.slot("FMC_D0", SEC, (ZS, D0Y), (ZE, D0Y), side="R")
        # l6ww: WE west, south down the west side, east (joins l6s as its outer lane)
        # stop 6: the SW leg starts at the lead's end (34.0, 38.3); sketch: a W leg and a 0.283 mm SW chamfer (SHARP)
        l6ww = bund("l6ww", ["FMC_SDNWE"], SEC, [("SW", {"FMC_SDNWE": 34.0 + 38.3}),
                                                    ("S", {"FMC_SDNWE": 33.6}), ("SE", {"FMC_SDNWE": 33.6 - L6S_WE + 0.6}),
                                                    ("E", {"FMC_SDNWE": L6S_WE})], 34.0, 36.0)
        bus.add(l6ww, start={"FMC_SDNWE": m["FMC_SDNWE"]})
        # l6s: D6 D7 D4 D5 A8 A9 A7 RAS (+ WE) south, east under the SDRAM; D6 D7 D4 up its west face, the rest up the aisle
        s6 = ["FMC_D6", "FMC_D7", "FMC_D4", "FMC_D5", "FMC_A8", "FMC_A9", "FMC_A7", "FMC_SDNRAS", "FMC_SDNWE"]
        xs = {"FMC_D6": 41.3, "FMC_D7": 40.65, "FMC_D4": 40.325, "FMC_D5": 40.0, "FMC_A8": 39.675, "FMC_A9": 39.025, "FMC_A7": 38.7, "FMC_SDNRAS": 38.375}
        ye = {n: L6S_Y0 + 0.25 * i for i, n in enumerate(s6)}
        xw = {"FMC_D6": 52.1, "FMC_D7": 52.35, "FMC_D4": 52.6}
        xa = {"FMC_D5": 55.6, "FMC_A8": 56.2, "FMC_A9": 56.6, "FMC_A7": 57.0, "FMC_SDNRAS": 57.4, "FMC_SDNWE": 57.8}
        legs = [("S", xs), ("SE", {n: xs[n] - ye[n] + 0.3 for n in xs}), ("E", ye)]
        l6s = bund("l6s", s6, SEC, legs, 43.0, 50.0, {"FMC_SDNWE": (2, 2)}, anchor="FMC_D6")
        bus.add(l6s, start={n: m[n] for n in xs})
        # west face part
        w6 = ["FMC_D6", "FMC_D7", "FMC_D4"]
        # stop 6: each lane leaves the E leg on one NE diagonal straight to the row of its via (sketch: NE, a short N leg
        # at x 52.1 / 52.35 / 52.6 and a second NE step: four bends in under 2 mm, `crowded`)
        l6sw = bund("l6sw", w6, SEC, [("E", {n: ye[n] for n in w6}), ("NE", {"FMC_D6": 94.0, "FMC_D7": 95.3, "FMC_D4": 96.6})], 50.0, 53.0)
        # stop 6 (U58): D6 runs under ball row N (y 41.0) and steps down to its via, so that the gap site (54.2, 41.4)
        # is free for the supply ball P2; sketch: along y 41.4 from (52.5, 41.4)
        bus.add(l6sw, end={"FMC_D6": via_end([(53.0, 41.0), (55.0, 41.0), (55.4, 41.4)], (55.8, 41.4), "N3"),
                           "FMC_D7": via_end([], (53.4, 42.2), "R1"),        # the fan's E stub from (53.1, 42.2)
                           "FMC_D4": via_end([], (54.2, 43.0), "R2")})       # E stub from (53.6, 43.0)
        a6 = ["FMC_D5", "FMC_A8", "FMC_A9", "FMC_A7", "FMC_SDNRAS", "FMC_SDNWE"]
        l6sa = bund("l6sa", a6, SEC, [("E", {n: ye[n] for n in a6}), ("NE", {n: xa[n] + ye[n] - 0.4 for n in a6}), ("N", xa)], 50.0, 40.0)
        # stop 6: D5 turns off the aisle 0.3 mm lower and A8 takes one NW diagonal to row 37.4 (sketch: D5 (55.6, 42.6),
        # (55.2, 42.2); A8 NW, W along y 37.8, NW: three bends in under 2 mm each, `crowded`)
        # try/sgsps (BGA block): D5 leaves the aisle at y 43.6 on one diagonal straight to its via (was: on to y 42.9, a
        # diagonal and a W stub), so that the ground ball R3 gets the gap site (55.8, 43.0) beside P3's
        bus.add(l6sa, end={"FMC_D5": via_end([(55.6, 43.6)], (54.2, 42.2), "P1"),
                           "FMC_A8": via_end([(56.2, 38.6), (55.0, 37.4)], (54.2, 37.4), "H2"),
                           "FMC_A9": via_end([(56.6, 37.8), (56.2, 37.4)], (55.8, 37.4), "J3"),
                           "FMC_A7": via_end([(57.0, 37.4), (56.6, 37.0), (53.8, 37.0)], (53.4, 37.4), "H1"),
                           # opt1: the via north-west of J9 (was (60.6, 38.2), south-east: the lane ran under the ball and
                           # the dog-bone came straight back, a 180 degree turn at the via)
                           "FMC_SDNRAS": via_end([(57.4, 38.2), (57.8, 37.8), (59.4, 37.8)], (59.8, 37.4), "J9"),
                           # WE keeps the sketch's path: K8's SW site (59.0, 39.0) is the ground via of C302.2 under the SDRAM
                           # (tried at stop 6: C302.2 then had no ground connection)
                           "FMC_SDNWE": via_end([(57.8, 39.8), (58.2, 39.4), (59.4, 39.4)], (59.8, 39.0), "K8")})
    # ---------------------------------------------------------------- clock: H14 -> R201 on L1, R201 -> L4 -> J1
    R["FMC_SDCLK"] = [("L1", list(m["FMC_SDCLK"].pieces[0][1]) + ["R201.1"])]
    if "L4" in LAYERS:
        # c9: the via 0.25 east (49.0, was 48.75): LCD_R5's L6 lane moved one pitch east (LCD_R7 joined the east bundle)
        # 2026-11-23 tuning (SPEC 9: every address / command line within 20 mm of the clock, the clock may carry a
        # serpentine): the clock takes the longer way round the L4 pocket south of its via (closed by the l4s lanes on
        # the west and south, the SDRAM area on the east; no other copper in it): straight down x 49.0 to y CLK_Y, east,
        # up x CLK_X and on as before; its serpentine humps east on the way down (pitch 0.5). Was: one SE diagonal
        # (49.3, 36.675) - (51.225, 38.6) and east along y 38.6. The U adds about 9.9 mm, the serpentine the rest.
        # The way down holds five humps (5.0 mm plus 0.7 at each end): the U's bottom runs 0.128 mm (edge to edge) above
        # A4's east leg (y 43.6), its corners are 0.29 mm chamfers.
        CY, CX, CC = float(os.environ.get("CLK_Y", "43.37")), float(os.environ.get("CLK_X", "51.25")), 0.29
        CV = (49.0, 36.675)
        bus.keep({"FMC_SDCLK_R": [("L1", ["R201.2", CV]), ("via", CV),
                                  ("L4", [CV, (49.0, CY - CC), (49.0 + CC, CY), (CX - CC, CY), (CX, CY - CC), (CX, 53.4 + 38.2 - CX),
                                          (53.4, 38.2)]),                  # up, then one NE diagonal into the via
                                                                           # (between the +3V3_SDRAM vias (52.6, 38.2) and (53.0, 39.4))
                                  ("via", (53.4, 38.2)), ("L1", [(53.4, 38.2), "U301.J1"])]})
        job.slot("FMC_SDCLK_R", "L4", CV, (49.0, CY - CC), side="L")              # going south, L = east
        # straight to the west face: D27 D25 D31 CKE0
        # stop 6 part B: lane 3's tuning zone in the strip between the packages (x 47.45 - 51.7): D27 D25 D31 rise at
        # x 47.05 / 47.3 / 47.3 to rows y27 / y25 / y31, stacked under D26's east leg (y 29.5), each humping south,
        # and drop into their via rows inside the SDRAM area (sketch: one NE diagonal each, straight to the via row)
        y27, y25, y31 = (float(os.environ.get(k, d)) for k, d in (("Y27", "30.35"), ("Y25", "32.1"), ("Y31", "34.55")))
        bus.keep({"FMC_D27": ext(m["FMC_D27"], [(46.65, 33.75), (47.05, 33.35), (47.05, y27 + 0.4), (47.45, y27), (52.0, y27), (52.0 + 31.0 - y27, 31.0), (54.2, 31.0)])
                  + [("via", (54.2, 31.0)), ("L1", [(54.2, 31.0), "U301.A2"])],
                  "FMC_D25": ext(m["FMC_D25"], [(46.9, 34.4), (47.3, 34.0), (47.3, y25 + 0.4), (47.7, y25), (52.0, y25), (52.0 + 32.6 - y25, 32.6), (54.2, 32.6)])
                  + [("via", (54.2, 32.6)), ("L1", [(54.2, 32.6), "U301.C2"])],
                  "FMC_D31": ext(m["FMC_D31"], [(47.05, 35.05), (47.05 + 35.05 - y31, y31), (52.0, y31), (52.0 + y31 - 33.4, 33.4), (54.2, 33.4)])
                  + [("via", (54.2, 33.4)), ("L1", [(54.2, 33.4), "U301.D2"])],
                  "FMC_SDCKE0": ext(m["FMC_SDCKE0"], [(49.9, 35.7), (52.0, 37.8), (53.8, 37.8), (54.2, 38.2)]) + [("via", (54.2, 38.2)), ("L1", [(54.2, 38.2), "U301.J2"])]})
        job.slot("FMC_D27", "L4", (47.7, y27), (51.7, y27), side="R")      # all four blocks start at x 48.4 (RTE-7)
        job.slot("FMC_D25", "L4", (47.7, y25), (51.7, y25), side="R")
        # opt1 (review 1): D31's site 0.8 mm shorter, three humps of about 0.8 mm instead of four of 0.63, nearer the
        # heights of D27 / D25 above it (CKE0 at y 35.7 limits it to about 0.85)
        job.slot("FMC_D31", "L4", (47.7, y31), (50.9, y31), side="R")
        # l4w + l4n: A1 A2 NE0 A0 (west) NBL1 NBL2 CAS (north) D26 (east, up the strip) to the aisle's north end.
        # In the aisle the lanes turn east in order (eastmost first); A0 and NBL2 reach their balls round the vias
        # of the nets outside them: A0 below NE0's J8, NBL2 below NBL1's K9 and back up east of column 9.
        w4 = ["FMC_A1", "FMC_A2", "FMC_SDNE0", "FMC_A0"]
        yw = {"FMC_A1": 38.3, "FMC_A2": 37.325, "FMC_SDNE0": 37.0, "FMC_A0": 35.7}     # try/sgsps: A2 37.65 -> 37.325
        xw = {"FMC_A1": 31.65, "FMC_A2": 32.15, "FMC_SDNE0": 32.4, "FMC_A0": 32.65}     # round 3: A3 runs between A1 and A2
        xw2 = dict(xw, FMC_A2=32.55, FMC_SDNE0=32.8, FMC_A0=33.05)                         # after the step north of the box
        ye = {"FMC_A1": 27.75, "FMC_A2": 28.0, "FMC_SDNE0": 28.25, "FMC_A0": 28.5, "FMC_NBL1": 28.75, "FMC_NBL2": 29.0,
              "FMC_SDNCAS": 29.25, "FMC_D26": 29.5}
        l4w = bund("l4w", w4, "L4", [("W", yw), ("NW", {n: xw[n] - yw[n] + 0.4 for n in w4}), ("N", xw),
                                    ("NE", {n: xw2[n] + ye[n] + 0.4 for n in w4}), ("E", {n: ye[n] for n in w4})], 34.0, 45.0)
        l4w.widen(2, 37.9 - 32.6, None, after="FMC_A1", by=0.4)
        bus.add(l4w, start={n: m[n] for n in w4})
        n4 = ["FMC_A1", "FMC_A2", "FMC_SDNE0", "FMC_A0", "FMC_NBL1", "FMC_NBL2", "FMC_SDNCAS", "FMC_D26"]
        xa = {"FMC_D26": 56.0, "FMC_SDNCAS": 56.87, "FMC_NBL2": 57.1, "FMC_NBL1": 57.33, "FMC_A0": 57.56, "FMC_SDNE0": 57.79,
              "FMC_A2": 58.55, "FMC_A1": 58.85}
        legs = [("E", {"FMC_D26": 33.1}), ("NE", {"FMC_D26": 46.8 + 33.1 - 0.4}), ("N", {"FMC_D26": 46.8}),
                ("NE", {"FMC_D26": 46.8 + 29.5 + 0.4}), ("E", ye), ("SE", {n: xa[n] - ye[n] - 0.4 for n in n4}), ("S", xa)]
        l4n = bund("l4n", n4, "L4", legs, 46.3, 33.0, {n: (4, 6) for n in n4 if n != "FMC_D26"}, anchor="FMC_D26")
        # stop 6 part B: D26 (lane 3) humps south on the east leg over lane 3's strip zone (station = x - 47.2), first
        # site; west towards the MCU area on its north leg (station = 32.7 - y), second site
        # stop 8 (review 2, b6): no site for D26 any more (its lone 0.55 mm hump on the east leg added 0.85 mm); it is
        # lane 3's shortest net, and lane 3's target is its natural length (LANE_SPREAD lane3 13.6)
        bus.add(l4n, start={n: m[n] for n in ["FMC_NBL1", "FMC_NBL2", "FMC_SDNCAS", "FMC_D26"]},
                end={"FMC_D26": via_end([(56.0, 33.8), (55.6, 34.2)], (54.2, 34.2), "E2", "L4"),
                     "FMC_SDNCAS": via_end([(56.87, 38.6), (57.27, 39.0)], (58.2, 39.0), "K7", "L4"),   # stop 6: SW site (sketch: SE (59.0, 39.0), 135 degrees)
                     "FMC_NBL2": via_end([(57.1, 38.2), (57.5, 38.6), (60.75, 38.6), (61.0, 38.35), (61.0, 36.05), (60.75, 35.8)], (59.8, 35.8), "F8", "L4"),
                     "FMC_NBL1": via_end([(57.33, 37.8), (57.73, 38.2)], (59.8, 38.2), "K9", "L4"),
                     "FMC_A0": via_end([(57.56, 37.4), (57.96, 37.8), (59.15, 37.8), (59.4, 37.55), (59.4, 37.0)], (59.8, 36.6), "G8", "L4"),
                     "FMC_SDNE0": via_end([(57.79, 37.0), (58.19, 37.4)], (59.0, 37.4), "J8", "L4"),
                     "FMC_A2": via_end([(58.55, 34.65)], (58.2, 35.0), "F7", "L4"),
                     "FMC_A1": via_end([(58.85, 35.85), (59.2, 36.2), (60.2, 36.2)], (60.6, 36.6), "G9", "L4")})
        # l4s: A4 A5 D10 D15 south through the strip, east under the SDRAM, north into the aisle's south end
        s4 = ["FMC_A4", "FMC_A5", "FMC_D10", "FMC_D15"]
        y0 = {"FMC_A4": 37.65, "FMC_A5": 38.625, "FMC_D10": 38.95, "FMC_D15": 40.9}   # try/sgsps: A5 38.3 -> 38.625
        xs = {"FMC_A4": 47.5, "FMC_A5": 47.25, "FMC_D10": 47.0, "FMC_D15": 46.75}
        yb = {"FMC_A4": 43.6, "FMC_A5": 43.85, "FMC_D10": 44.1, "FMC_D15": 44.35}
        xn = {"FMC_A4": 56.4, "FMC_A5": 56.65, "FMC_D10": 57.0, "FMC_D15": 57.25}
        # stop 6: D15 runs on along its lead's SE step (x - y = 4.3) to its lane (sketch: E along y 40.9, a 0.42 mm SE
        # step at x 46.45: three bends in 1.67 mm, `crowded`)
        se1 = {n: xs[n] - y0[n] - 0.3 for n in s4}
        se1["FMC_D15"] = 4.3
        legs = [("E", y0), ("SE", se1), ("S", xs), ("SE", {n: xs[n] - yb[n] + 0.3 for n in s4}),
                ("E", yb), ("NE", {n: xn[n] + yb[n] - 0.4 for n in s4}), ("N", xn)]
        l4s = bund("l4s", s4, "L4", legs, 46.2, 40.0, {"FMC_D15": (1, 6)})
        # 2026-11-23 tuning: D15 (lane 1), the outer lane of the east leg below the strip, humps south into the free L4
        # band between this bundle and l4ss (y 44.6 - 47.2), before the SDRAM area (station = x - 47.8, A4's corner)
        l4s.slot("FMC_D15", 4, 47.05 - 47.8, 51.75 - 47.05, side="R")
        bus.add(l4s, start=dict({n: m[n] for n in s4}, FMC_D15=trim(m["FMC_D15"], 0.8)),     # D15's lead ends at (45.2, 40.9), on its SE line
                end={"FMC_A4": via_end([(56.4, 36.6), (56.0, 36.2), (53.8, 36.2)], (53.4, 35.8), "G1", "L4"),
                     "FMC_A5": via_end([(56.65, 35.8), (56.25, 35.4), (54.6, 35.4)], (54.2, 35.8), "G2", "L4"),
                     "FMC_D10": via_end([(57.0, 40.2), (57.4, 39.8)], (59.0, 39.8), "L8", "L4"),
                     "FMC_D15": via_end([(57.25, 41.0), (57.65, 40.6)], (59.0, 40.6), "M8", "L4")})
        # l4ss: D17 D16 south about: east below everything, up the SDRAM's east side, west along its north side
        ss = ["FMC_D17", "FMC_D16"]
        xs = {"FMC_D17": 43.9, "FMC_D16": 43.25}
        # round 3: below the L1 band, so that the south-east corner balls can drop through. opt1 (review 1): 0.75 mm north
        # (was 47.5 / 47.75): off the top edge of the +5V arm of L5 (y 48), 1.5 mm shorter each
        # compact (2026-11-23, user review): 1.35 mm north (was 46.75 / 47.0), the lowest the L5 gaps allow: D17's
        # lower edge stays north of nothing, its upper edge 0.05 south of the +3V3_MCU block's south gap (y 44.8 - 45.3,
        # x 36.4 - 46) and the +3V3_SDRAM block's (y 44.5 - 45.0); D15's serpentine no longer reaches into this band
        ye = {"FMC_D17": 45.4, "FMC_D16": 45.65}
        xn = {"FMC_D17": 61.75, "FMC_D16": 62.0}
        yw = {"FMC_D17": 29.85, "FMC_D16": 29.6}
        legs = [("S", xs), ("SE", {n: xs[n] - ye[n] + 0.3 for n in ss}), ("E", ye), ("NE", {n: xn[n] + ye[n] - 0.6 for n in ss}),
                ("N", xn), ("NW", {n: xn[n] - yw[n] - 0.6 for n in ss}), ("W", yw)]
        # opt1 (review 1): D17 leaves the N leg on one NW diagonal straight into its via (x - y = 28.8, between the vias of
        # D19, +3V3_SDRAM and D16), instead of going on round the top of the ball field and back down to it (a hook of
        # four bends in 1.5 mm, `crowded`); D16 keeps the way round
        l4ss = bund("l4ss", ss, "L4", legs, 43.0, 61.0, {"FMC_D17": (0, 4)})
        bus.add(l4ss, start={n: m[n] for n in ss},
                end={"FMC_D17": via_end([(61.75, 32.95)], (59.8, 31.0), "A8", "L4"),
                     "FMC_D16": via_end([(59.4, 30.1), (59.4, 31.4)], (59.8, 31.8), "B9", "L4")})   # SW 0.1 longer (sketch 30.0: `crowded`)
    if SEC in LAYERS:
        bus.keep({"FMC_BA1": m["FMC_BA1"]})
        job.slot("FMC_BA1", SEC, (46.9, 38.625), (50.15, 38.625), side="L")             # going east, L = north (the strip zone, see l6e)
    # ---------------------------------------------------------------- ground return vias (RTE-5, SPEC 9)
    # beside the layer changes outside the ball fields, one per group, each at least 0.2 mm of plane web from every
    # antipad of another net (no plane slot grows); sites found against the round-1 board (out/route1/tmp/gndsite.py)
    job.profile.classes["PWR"]["via"] = (0.45, 0.2)              # GND is PWR class; this board's vias outside the areas are 0.45 / 0.2
    job.stitch += [("GND", p) for p in GND_RETURN]
    R.update(bus.routes())
    return R
