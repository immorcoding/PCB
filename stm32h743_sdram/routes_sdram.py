"""Line-order sketch of the SDRAM bus (RTE-13, stop 3 of issue 22): SDRAM at rotation 0, body gap 8 mm.

    D:\\KiCad\\bin\\python.exe scripts\\busroute\\build.py stm32h743_sdram\\routes_sdram.py --sketch --out stm32h743_sdram\\out\\sketch\\rot0

Follows stm32h743_sdram/line_order/line_order.txt (layer, way round the MCU, SDRAM ball of every net).
Structure per layer (local mm, MCU centre (40, 37), SDRAM centre (57, 37)):
  L1  l1n   north river: A10 A6 (south side, west about) A3 D28 D29 (west) D30 NBL3 NBL0 D2 (north);
            D29..D2 turn south into the strip to the SDRAM west face, A10 A6 A3 D28 run on to the aisle's north end
      l1e   D3 D24 D20 BA0 D13 D14 from the east side: south through the strip; D3 to M2, the rest east under the
            SDRAM and north into the aisle (D24 in the channel between columns 2 and 3)
      l1s   D11 D12 D9 D8 A11 south about: east below the SDRAM, north up its east side into the east face
  L4 / L6   see the functions below.
Deep balls of L1 nets go down a dog-bone and come back up to L1 through a second 0.30 via inside the MCU rule
area (between the outer ring and the area edge); balls of ring 0-1 of inner-layer nets take a dog-bone via
inside the area (no 0.45 via just outside it: at 0.325 lane pitch there is no room for them).
"""
import os
from busroute import Bundle
from busroute.geom import R2

BOARD = "stm32h743_sdram.kicad_pcb"
ORIGIN = (100, 100)
GROUP = "sdram"
SKETCH = True
REF = ["FMC_SDCLK", "FMC_SDCLK_R"]
VIA_LIMIT = 3
VIA_TARGET = 2
LEN_MAX = 60
ROUND = int(os.environ.get("ROUND", "1"))
DATA = ["FMC_D%d" % i for i in range(32)] + ["FMC_NBL%d" % i for i in range(4)]
ADDR = ["FMC_A%d" % i for i in range(13)] + ["FMC_BA0", "FMC_BA1", "FMC_SDNRAS", "FMC_SDNCAS", "FMC_SDNWE", "FMC_SDCKE0", "FMC_SDNE0"]
GROUPS = {"lane0": ["FMC_D%d" % i for i in range(8)] + ["FMC_NBL0"], "lane1": ["FMC_D%d" % i for i in range(8, 16)] + ["FMC_NBL1"],
          "lane2": ["FMC_D%d" % i for i in range(16, 24)] + ["FMC_NBL2"], "lane3": ["FMC_D%d" % i for i in range(24, 32)] + ["FMC_NBL3"],
          "addr": ADDR, "clock": ["FMC_SDCLK", "FMC_SDCLK_R"]}
DRC_IGNORE = {"skew_out_of_range": "byte-lane matching (sdram_lane0-3) is the tuning stage, not the line-order sketch (SPEC 9)"}
NETS = DATA + ADDR + ["FMC_SDCLK", "FMC_SDCLK_R"]
LAYERS = os.environ.get("LAYERS", "L1 L4 L6").split()
VIEWS = [("all", 29.0, 26.0, 66.0, 50.0, 40), ("strip", 44.0, 28.0, 54.0, 46.0, 100), ("sdram", 50.0, 28.0, 64.0, 47.0, 80),
         ("mcu", 33.0, 30.0, 47.0, 44.0, 100)]

P = 0.25                                   # lane pitch outside the rule areas


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
        g = [round((vs[nets[i + 1]] - vs[nets[i]]) / sc, 6) for i in range(len(nets) - 1)]
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
    return list(lead[:-1]) + [(lead[-1][0], list(lead[-1][1]) + list(pts))]


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
        "FMC_D6": db("P9", (40.975, 40.575), "L6", [(41.3, 40.9), (41.3, 43.0)]),
        "FMC_D7": db("R9", (40.325, 41.225), "L6", [(40.65, 41.55), (40.65, 43.0)]),
        "FMC_D4": db("R8", (40.325, 41.875), "L6", [(40.325, 43.0)]),
        "FMC_D5": db("P8", (39.675, 40.575), "L6", [(40.0, 40.9), (40.0, 43.0)]),
        "FMC_A8": db("R7", (39.675, 41.875), "L6", [(39.675, 43.0)]),
        "FMC_A9": db("P7", (39.675, 41.225), "L6", [(39.35, 41.55), (39.35, 43.0)]),
        "FMC_A7": db("N6", (39.025, 40.575), "L6", [(38.7, 40.9), (38.7, 43.0)]),
        "FMC_SDNRAS": db("R6", (38.375, 41.875), "L6", [(38.375, 43.0)]),
        # L1 nets with deep balls on the south side
        "FMC_A11": db("M7", (39.675, 39.925), "L4", [(40.0, 40.25), (40.0, 46.3)]) + [("via", (40.0, 46.3)), ("L1", [(40.0, 46.3), (40.3, 46.3)])],
        "FMC_A10": db("N7", (39.025, 39.925), "L4", [(33.2, 39.925), (32.5, 40.625)]) + [("via", (32.5, 40.625)), ("L1", [(32.5, 40.625), (32.5, 40.3)])],
        # L4 under the MCU (ball-free ring rows E / L, between the centre vias), out on the east side
        "FMC_D31": db("E3", (37.075, 35.375), "L4", [(37.4, 35.05), (46.0, 35.05)]),
        "FMC_SDCKE0": db("F4", (37.725, 36.025), "L4", [(38.05, 35.7), (46.0, 35.7)]),
        "FMC_A4": db("J3", (37.075, 37.325), "L4", [(37.4, 37.65), (46.0, 37.65)]),
        "FMC_A5": db("K3", (37.075, 38.625), "L4", [(37.4, 38.3), (46.0, 38.3)]),
        "FMC_D10": db("N11", (41.625, 39.925), "L4", [(41.625, 39.275), (41.95, 38.95), (46.0, 38.95)]),
        # BA1 on L6 (plan: L4): on L4 its ball H8, entered from the aisle's south end, sits between the balls of
        # NE0 / CAS / NBL1 entered from the north end (J8, K7, K9): no way through without a crossing
        "FMC_BA1": db("K13", (43.575, 38.625), "L6", [(49.3, 38.625), (51.725, 36.2), (58.6, 36.2), (59.0, 36.6)])
                   + [("via", (59.0, 36.6)), ("L1", [(59.0, 36.6), "U301.H8"])],
        # east side, rows chosen so that every inner layer leaves in the river order
        "FMC_D3": db("C12", (42.925, 33.425), "L6", [(43.575, 32.775)]) + [("via", (43.575, 32.775)), ("L1", [(43.575, 32.775), (46.0, 32.775)])],
        "FMC_D20": db("K12", (42.275, 37.975), "L4", [(45.4, 37.975)]) + [("via", (45.4, 37.975)), ("L1", [(45.4, 37.975), (46.0, 37.975)])],
        "FMC_D23": db("D13", (43.575, 34.075), "L6", [(43.9, 33.75), (46.0, 33.75)]),
        "FMC_D22": db("E13", (43.575, 34.725), "L6", [(43.9, 34.4), (46.0, 34.4)]),
        "FMC_D21": db("E12", (42.925, 35.375), "L6", [(43.25, 35.05), (46.0, 35.05)]),
        "FMC_D19": db("L12", (42.275, 39.275), "L6", [(41.95, 38.95), (41.95, 36.675), (42.275, 36.35), (46.0, 36.35)]),
        "FMC_D18": db("L13", (42.925, 38.625), "L6", [(42.925, 37.325), (43.25, 37.0), (46.0, 37.0)]),
        "FMC_A12": db("L15", (44.875, 39.275), "L6", [(45.2, 38.95), (46.0, 38.95)]),
        "FMC_D1": db("L14", (44.225, 39.275), "L6", [(44.55, 39.6), (46.0, 39.6)]),
        "FMC_D0": db("M14", (44.225, 39.925), "L6", [(44.55, 40.25), (46.0, 40.25)]),
        "FMC_D26": db("C14", (44.225, 33.425), "L4", [(44.55, 33.1), (46.0, 33.1)]),
        "FMC_D27": db("C13", (43.575, 33.425), "L4", [(43.9, 33.75), (46.0, 33.75)]),
        "FMC_D25": db("D14", (44.225, 34.075), "L4", [(44.55, 34.4), (46.0, 34.4)]),
    }
    fo = job.fanout("U201")
    req = {
        # L1 river
        "P11": "S+:L1", "R11": "S", "R10": "S", "P10": "S-:L1", "P6": "S+:L1",
        "E14": "E+:L1", "K14": "E+:L1", "P15": "E", "P14": "E+:L1",
        "A4": "N", "B12": "N", "D3": "N-:via@L4", "C4": "N-:via@L4",
        "J2": "W", "C2": "W-:L1", "C3": "W:via@L4",
        "H14": "E-:L1",
        # inner rivers
        "N15": "E:via@L4",
        "A3": "N:via@L4", "B7": "N:via@L4", "D4": "N:via@L6",
        "H2": "W:via@L4", "G4": "W:via@L4", "H3": "W:via@L6", "E2": "W:via@L6", "J4": "W:via@L6",
        "M13": "S:via@L4", "M12": "S:via@L4",
    }
    for k, v in list(req.items()):
        if os.environ.get("REQ_" + k):
            req[k] = os.environ["REQ_" + k]
    res = fo.escape(req, inner=("L4", "L6"), l1_depth=1, keep=hand)
    job.refused(res)
    job.notes.append(res.text())
    m = res.by_net()
    if os.environ.get("DUMP"):
        with open(os.environ["DUMP"], "w") as f:
            f.write(res.text() + "\n")
            for l in sorted(res.leads.values(), key=lambda l: (l.side, l.layer, l.lat)):
                f.write("%s %s %s %s %s %s\n" % (l.side, l.layer, l.net, l.ball, l.kind, [pc[1] if pc[0] == "via" else pc[1][-1] for pc in l.pieces][-2:]))
    m.update(hand)
    bus = job.bus()
    R = {}

    # ---------------------------------------------------------------- L1
    # deep balls of L1 nets: up again inside the rule area
    s_d3, s_d20 = m["FMC_D3"], m["FMC_D20"]
    s_d30 = surface(m["FMC_D30"], 31.6, "y")
    s_nbl3 = surface(m["FMC_NBL3"], 31.6, "y")
    s_d28 = surface(m["FMC_D28"], 34.6, "x")
    a11, a10 = m["FMC_A11"], m["FMC_A10"]

    if "L1" in LAYERS:
        # l1n: A10 A6 | A3 D28 D29 | D30 NBL3 NBL0 D2
        n_all = ["FMC_A10", "FMC_A6", "FMC_A3", "FMC_D28", "FMC_D29", "FMC_D30", "FMC_NBL3", "FMC_NBL0", "FMC_D2"]
        west = {"FMC_A6": 43.5}                                           # W leg (y), A6 only (A10 joins on the N leg)
        north = {"FMC_A10": 32.5, "FMC_A6": 33.0, "FMC_A3": 33.25, "FMC_D28": 33.5, "FMC_D29": 33.75}
        ye = {"FMC_A10": 28.8, "FMC_A6": 29.05, "FMC_A3": 29.3, "FMC_D28": 29.55, "FMC_D29": 29.8, "FMC_D30": 30.05,
              "FMC_NBL3": 30.3, "FMC_NBL0": 30.55, "FMC_D2": 30.8}
        nw = {n: north[n] - 43.5 + 0.6 for n in ("FMC_A6",)}             # x - y of the SW corner diagonal
        ne = {n: north[n] + ye[n] + 0.6 for n in north}                   # x + y of the NW corner diagonal (wider for outer)
        for n in north:
            ne[n] = north[n] + ye[n] + 0.6 + 0.0
        # strip: SE diagonal then south at xs
        xs = {"FMC_D29": 51.75, "FMC_D30": 51.5, "FMC_NBL3": 51.25, "FMC_NBL0": 51.0, "FMC_D2": 50.75}
        se = {n: xs[n] - ye[n] - 0.6 for n in xs}
        span = {"FMC_A10": (2, 3), "FMC_A6": (0, 3), "FMC_A3": (2, 3), "FMC_D28": (2, 3), "FMC_D29": (2, 5),
                "FMC_D30": (4, 5), "FMC_NBL3": (4, 5), "FMC_NBL0": (4, 5), "FMC_D2": (4, 5)}
        # legs: 0 W, 1 NW, 2 N, 3 NE, 4 E, 5 SE, 6 S  (lane order left->right: going W left = south)
        legs = [("W", west), ("NW", nw), ("N", north), ("NE", ne), ("E", ye), ("SE", se), ("S", xs)]
        span = {"FMC_A10": (2, 4), "FMC_A6": (0, 4), "FMC_A3": (2, 4), "FMC_D28": (2, 4), "FMC_D29": (2, 6),
                "FMC_D30": (4, 6), "FMC_NBL3": (4, 6), "FMC_NBL0": (4, 6), "FMC_D2": (4, 6)}
        l1n = bund("l1n", n_all, "L1", legs, 38.0, 41.0, span, anchor="FMC_A6")
        st = {"FMC_A6": m["FMC_A6"], "FMC_A10": a10, "FMC_A3": m["FMC_A3"], "FMC_D28": s_d28, "FMC_D29": m["FMC_D29"],
              "FMC_D30": s_d30, "FMC_NBL3": s_nbl3, "FMC_NBL0": m["FMC_NBL0"], "FMC_D2": m["FMC_D2"]}
        en = {"FMC_D29": [(51.75, 31.2), (51.95, 31.4), "U301.A1"],
              "FMC_D30": [(51.5, 31.6), (52.1, 32.2), "U301.B1"],
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
        yb = {"FMC_D24": 43.55, "FMC_D20": 43.8, "FMC_BA0": 44.05, "FMC_D13": 44.3, "FMC_D14": 44.55}
        se2 = {n: xs[n] - yb[n] + 0.4 for n in yb}
        xn = {"FMC_D20": 57.1, "FMC_BA0": 57.4, "FMC_D13": 57.7, "FMC_D14": 58.0}
        ne = {n: xn[n] + yb[n] - 0.4 for n in xn}
        # legs: 0 E, 1 SE, 2 S, 3 SE, 4 E, 5 NE, 6 N
        legs = [("E", y0), ("SE", se), ("S", xs), ("SE", se2), ("E", yb), ("NE", ne), ("N", xn)]
        l1e = bund("l1e", e_n, "L1", legs, 46.5, 34.0, {"FMC_D3": (0, 2), "FMC_D24": (0, 4)})
        bus.add(l1e, start={"FMC_D3": s_d3, "FMC_D24": m["FMC_D24"], "FMC_D20": s_d20, "FMC_BA0": m["FMC_BA0"],
                            "FMC_D13": m["FMC_D13"], "FMC_D14": m["FMC_D14"]},
                end={"FMC_D3": [(50.45, 39.2), (51.05, 39.8), (54.2, 39.8), "U301.M2"],
                     "FMC_D24": [(55.0, 43.2), (55.0, 33.4), "U301.C3"],
                     "FMC_D20": [(57.1, 35.3), "U301.D7"],
                     "FMC_BA0": [(57.4, 39.0), "U301.J7"],
                     "FMC_D13": [(57.7, 41.1), "U301.M7"],
                     "FMC_D14": [(58.0, 41.6), "U301.N7"]})

        # l1s: D11 D12 D9 D8 (+ A11) going S (left = east), then E, then N up the SDRAM's east side
        s_n = ["FMC_D11", "FMC_D12", "FMC_D9", "FMC_D8", "FMC_A11"]
        xs = {"FMC_D11": 42.275, "FMC_D12": 41.95, "FMC_D9": 41.3, "FMC_D8": 40.975}
        ys = {"FMC_D11": 45.3, "FMC_D12": 45.55, "FMC_D9": 45.8, "FMC_D8": 46.05, "FMC_A11": 46.3}
        se = {n: xs[n] - ys[n] + 0.3 for n in xs}
        xe = {"FMC_D11": 61.6, "FMC_D12": 61.85, "FMC_D9": 62.1, "FMC_D8": 62.35, "FMC_A11": 62.6}
        ne = {n: xe[n] + ys[n] - 0.6 for n in xe}
        legs = [("S", xs), ("SE", se), ("E", ys), ("NE", ne), ("N", xe)]
        l1s = bund("l1s", s_n, "L1", legs, 43.0, 40.0, {"FMC_A11": (2, 4)})
        bus.add(l1s, start={"FMC_D11": m["FMC_D11"], "FMC_D12": m["FMC_D12"], "FMC_D9": m["FMC_D9"], "FMC_D8": m["FMC_D8"], "FMC_A11": a11},
                end={"FMC_D11": [(61.6, 43.0), (61.2, 42.6), "U301.R9"],
                     "FMC_D12": [(61.85, 42.6), (61.45, 42.2), (59.8, 42.2), "U301.R8"],
                     "FMC_D9": [(62.1, 42.2), (61.7, 41.8), "U301.P9"],
                     "FMC_D8": [(62.35, 41.8), (61.95, 41.4), (59.8, 41.4), "U301.N8"],
                     "FMC_A11": [(62.6, 37.4), (62.2, 37.0), "U301.H9"]})
    # ---------------------------------------------------------------- L6
    def via_end(pts, via, ball, lay="L6"):
        """End terminal: `pts` on the inner layer, a 0.30 via, the dog-bone to the SDRAM ball on L1."""
        return [(lay, list(pts) + [via]), ("via", via), ("L1", [via, "U301." + ball])]

    if "L6" in LAYERS:
        # l6w: A1 A0 west, north up the west side, east along the north (joins l6n)
        l6w = bund("l6w", ["FMC_A1", "FMC_A0"], "L6",
                   [("W", {"FMC_A1": 37.65, "FMC_A0": 35.7}), ("NW", {"FMC_A1": 32.9 - 37.65 + 0.4, "FMC_A0": 33.15 - 35.7 + 0.4}),
                    ("N", {"FMC_A1": 32.9, "FMC_A0": 33.15}), ("NE", {"FMC_A1": 32.9 + 28.25 + 0.4, "FMC_A0": 33.15 + 28.5 + 0.4}),
                    ("E", {"FMC_A1": 28.25, "FMC_A0": 28.5})], 34.0, 45.0)
        bus.add(l6w, start={"FMC_A1": m["FMC_A1"], "FMC_A0": m["FMC_A0"]})
        # l6n: A1 A0 NBL2 | D23 D22 D21 D19 D18 (north river, D19 / D18 leave on the north side)
        n6 = ["FMC_A1", "FMC_A0", "FMC_NBL2", "FMC_D23", "FMC_D22", "FMC_D21", "FMC_D19", "FMC_D18"]
        y0 = {"FMC_D23": 33.75, "FMC_D22": 34.4, "FMC_D21": 35.05, "FMC_D19": 36.35, "FMC_D18": 37.0}
        xn = {"FMC_D23": 47.25, "FMC_D22": 47.5, "FMC_D21": 47.75, "FMC_D19": 48.0, "FMC_D18": 48.25}
        ye = {"FMC_A1": 28.25, "FMC_A0": 28.5, "FMC_NBL2": 28.75, "FMC_D23": 29.0, "FMC_D22": 29.25, "FMC_D21": 29.5,
              "FMC_D19": 29.75, "FMC_D18": 30.0}
        xs = {"FMC_A1": 62.35, "FMC_A0": 62.1, "FMC_NBL2": 61.85, "FMC_D23": 61.6, "FMC_D22": 61.35, "FMC_D21": 61.1}
        legs = [("E", y0), ("NE", {n: xn[n] + y0[n] - 0.4 for n in y0}), ("N", xn), ("NE", {n: xn[n] + ye[n] + 0.4 for n in xn}),
                ("E", ye), ("SE", {n: xs[n] - ye[n] - 0.4 for n in xs}), ("S", xs)]
        span = {"FMC_A1": (4, 6), "FMC_A0": (4, 6), "FMC_NBL2": (4, 6), "FMC_D19": (0, 4), "FMC_D18": (0, 4)}
        l6n = bund("l6n", n6, "L6", legs, 46.5, 40.0, span, anchor="FMC_D23")
        bus.add(l6n, start={n: m[n] for n in ["FMC_NBL2", "FMC_D23", "FMC_D22", "FMC_D21", "FMC_D19", "FMC_D18"]},
                end={"FMC_D18": via_end([(57.8, 30.4), (57.8, 32.2)], (58.2, 32.6), "C7"),
                     "FMC_D19": via_end([(60.2, 30.15), (60.2, 30.6)], (60.6, 31.0), "A9"),
                     "FMC_D21": via_end([(61.1, 33.0), (60.7, 33.4)], (59.8, 33.4), "C8"),
                     "FMC_D22": via_end([(61.35, 33.8), (60.95, 34.2)], (59.8, 34.2), "D8"),
                     "FMC_D23": via_end([(61.6, 34.6), (61.2, 35.0)], (59.8, 35.0), "E8"),
                     "FMC_NBL2": via_end([(61.85, 35.4), (61.45, 35.8)], (59.8, 35.8), "F8"),
                     "FMC_A0": via_end([(62.1, 35.8), (61.7, 36.2), (60.2, 36.2)], (59.8, 36.6), "G8"),
                     "FMC_A1": via_end([(62.35, 36.2), (61.95, 36.6)], (60.6, 36.6), "G9")})
        # l6e: A12 D1 D0 straight to the west face (D1 enters M3 from the west face, not through the aisle)
        bus.keep({"FMC_A12": m["FMC_A12"][:-1] + [("L6", [(44.875, 39.275), (45.2, 38.95), (50.0, 38.95), (52.35, 36.6)] + [(55.8, 36.6)])]
                  + [("via", (55.8, 36.6)), ("L1", [(55.8, 36.6), "U301.H3"])],
                  "FMC_D1": m["FMC_D1"][:-1] + [("L6", [(44.225, 39.275), (44.55, 39.6), (50.4, 39.6), (50.6, 39.8), (55.8, 39.8)])]
                  + [("via", (55.8, 39.8)), ("L1", [(55.8, 39.8), "U301.M3"])],
                  "FMC_D0": m["FMC_D0"][:-1] + [("L6", [(44.225, 39.925), (44.55, 40.25), (50.2, 40.25), (50.55, 40.6), (54.2, 40.6)])]
                  + [("via", (54.2, 40.6)), ("L1", [(54.2, 40.6), "U301.N2"])]})
        # l6ww: WE west, south down the west side, east (joins l6s as its outer lane)
        l6ww = bund("l6ww", ["FMC_SDNWE"], "L6", [("W", {"FMC_SDNWE": 38.3}), ("SW", {"FMC_SDNWE": 33.6 + 38.3 + 0.2}),
                                                    ("S", {"FMC_SDNWE": 33.6}), ("SE", {"FMC_SDNWE": 33.6 - 45.6 + 0.6}),
                                                    ("E", {"FMC_SDNWE": 45.6})], 34.0, 36.0)
        bus.add(l6ww, start={"FMC_SDNWE": m["FMC_SDNWE"]})
        # l6s: D6 D7 D4 D5 A8 A9 A7 RAS (+ WE) south, east under the SDRAM; D6 D7 D4 up its west face, the rest up the aisle
        s6 = ["FMC_D6", "FMC_D7", "FMC_D4", "FMC_D5", "FMC_A8", "FMC_A9", "FMC_A7", "FMC_SDNRAS", "FMC_SDNWE"]
        xs = {"FMC_D6": 41.3, "FMC_D7": 40.65, "FMC_D4": 40.325, "FMC_D5": 40.0, "FMC_A8": 39.675, "FMC_A9": 39.35, "FMC_A7": 38.7, "FMC_SDNRAS": 38.375}
        ye = {n: 43.6 + 0.25 * i for i, n in enumerate(s6)}
        xw = {"FMC_D6": 52.1, "FMC_D7": 52.35, "FMC_D4": 52.6}
        xa = {"FMC_D5": 55.6, "FMC_A8": 56.2, "FMC_A9": 56.6, "FMC_A7": 57.0, "FMC_SDNRAS": 57.4, "FMC_SDNWE": 57.8}
        legs = [("S", xs), ("SE", {n: xs[n] - ye[n] + 0.3 for n in xs}), ("E", ye)]
        l6s = bund("l6s", s6, "L6", legs, 43.0, 50.0, {"FMC_SDNWE": (2, 2)}, anchor="FMC_D6")
        bus.add(l6s, start={n: m[n] for n in xs})
        # west face part
        w6 = ["FMC_D6", "FMC_D7", "FMC_D4"]
        l6sw = bund("l6sw", w6, "L6", [("E", {n: ye[n] for n in w6}), ("NE", {n: xw[n] + ye[n] - 0.4 for n in w6}), ("N", xw)], 50.0, 42.0)
        bus.add(l6sw, end={"FMC_D6": via_end([(52.1, 41.8), (52.5, 41.4)], (55.8, 41.4), "N3"),
                           "FMC_D7": via_end([(52.35, 42.6), (52.75, 42.2)], (53.4, 42.2), "R1"),
                           "FMC_D4": via_end([(52.6, 43.4), (53.0, 43.0)], (54.2, 43.0), "R2")})
        a6 = ["FMC_D5", "FMC_A8", "FMC_A9", "FMC_A7", "FMC_SDNRAS", "FMC_SDNWE"]
        l6sa = bund("l6sa", a6, "L6", [("E", {n: ye[n] for n in a6}), ("NE", {n: xa[n] + ye[n] - 0.4 for n in a6}), ("N", xa)], 50.0, 40.0)
        bus.add(l6sa, end={"FMC_D5": via_end([(55.6, 42.6), (55.2, 42.2)], (54.2, 42.2), "P1"),
                           "FMC_A8": via_end([(56.2, 38.2), (55.8, 37.8), (54.6, 37.8)], (54.2, 37.4), "H2"),
                           "FMC_A9": via_end([(56.6, 37.8), (56.2, 37.4)], (55.8, 37.4), "J3"),
                           "FMC_A7": via_end([(57.0, 37.4), (56.6, 37.0), (53.8, 37.0)], (53.4, 37.4), "H1"),
                           "FMC_SDNRAS": via_end([(57.4, 38.6), (57.8, 38.2)], (60.6, 38.2), "J9"),
                           "FMC_SDNWE": via_end([(57.8, 39.8), (58.2, 39.4), (59.4, 39.4)], (59.8, 39.0), "K8")})
    # ---------------------------------------------------------------- clock: H14 -> R201 on L1, R201 -> L4 -> J1
    R["FMC_SDCLK"] = [("L1", list(m["FMC_SDCLK"].pieces[0][1]) + ["R201.1"])]
    if "L4" in LAYERS:
        bus.keep({"FMC_SDCLK_R": [("L1", ["R201.2", (48.75, 36.675)]), ("via", (48.75, 36.675)),
                                  ("L4", [(48.75, 36.675), (49.3, 36.675), (51.225, 38.6), (53.0, 38.6), (53.4, 38.2)]),
                                  ("via", (53.4, 38.2)), ("L1", [(53.4, 38.2), "U301.J1"])]})
        # straight to the west face: D27 D25 D31 CKE0
        bus.keep({"FMC_D27": ext(m["FMC_D27"], [(48.5, 33.75), (51.25, 31.0), (54.2, 31.0)]) + [("via", (54.2, 31.0)), ("L1", [(54.2, 31.0), "U301.A2"])],
                  "FMC_D25": ext(m["FMC_D25"], [(49.4, 34.4), (51.2, 32.6), (54.2, 32.6)]) + [("via", (54.2, 32.6)), ("L1", [(54.2, 32.6), "U301.C2"])],
                  "FMC_D31": ext(m["FMC_D31"], [(50.3, 35.05), (51.95, 33.4), (54.2, 33.4)]) + [("via", (54.2, 33.4)), ("L1", [(54.2, 33.4), "U301.D2"])],
                  "FMC_SDCKE0": ext(m["FMC_SDCKE0"], [(49.9, 35.7), (52.0, 37.8), (53.8, 37.8), (54.2, 38.2)]) + [("via", (54.2, 38.2)), ("L1", [(54.2, 38.2), "U301.J2"])]})
        # l4w + l4n: A2 NE0 (west) NBL1 CAS (north) D26 (east, up the strip) to the aisle's north end
        l4w = bund("l4w", ["FMC_A2", "FMC_SDNE0"], "L4",
                   [("W", {"FMC_A2": 37.65, "FMC_SDNE0": 37.0}), ("NW", {"FMC_A2": 32.9 - 37.65 + 0.4, "FMC_SDNE0": 33.15 - 37.0 + 0.4}),
                    ("N", {"FMC_A2": 32.9, "FMC_SDNE0": 33.15}), ("NE", {"FMC_A2": 32.9 + 28.25 + 0.4, "FMC_SDNE0": 33.15 + 28.5 + 0.4}),
                    ("E", {"FMC_A2": 28.25, "FMC_SDNE0": 28.5})], 34.0, 45.0)
        bus.add(l4w, start={"FMC_A2": m["FMC_A2"], "FMC_SDNE0": m["FMC_SDNE0"]})
        n4 = ["FMC_A2", "FMC_SDNE0", "FMC_NBL1", "FMC_SDNCAS", "FMC_D26"]
        ye = {"FMC_A2": 28.25, "FMC_SDNE0": 28.5, "FMC_NBL1": 28.75, "FMC_SDNCAS": 29.0, "FMC_D26": 29.25}
        xa = {"FMC_D26": 56.0, "FMC_SDNCAS": 57.0, "FMC_NBL1": 57.25, "FMC_SDNE0": 57.5, "FMC_A2": 57.8}
        legs = [("E", {"FMC_D26": 33.1}), ("NE", {"FMC_D26": 46.8 + 33.1 - 0.4}), ("N", {"FMC_D26": 46.8}),
                ("NE", {"FMC_D26": 46.8 + 29.25 + 0.4}), ("E", ye), ("SE", {n: xa[n] - ye[n] - 0.4 for n in n4}), ("S", xa)]
        l4n = bund("l4n", n4, "L4", legs, 46.3, 33.0, {"FMC_A2": (4, 6), "FMC_SDNE0": (4, 6), "FMC_NBL1": (4, 6), "FMC_SDNCAS": (4, 6)}, anchor="FMC_D26")
        bus.add(l4n, start={"FMC_NBL1": m["FMC_NBL1"], "FMC_SDNCAS": m["FMC_SDNCAS"], "FMC_D26": m["FMC_D26"]},
                end={"FMC_D26": via_end([(56.0, 33.8), (55.6, 34.2)], (54.2, 34.2), "E2", "L4"),
                     "FMC_SDNCAS": via_end([(57.0, 38.6), (57.4, 39.0)], (59.0, 39.0), "K7", "L4"),
                     "FMC_NBL1": via_end([(57.25, 38.2), (57.65, 38.6), (60.2, 38.6)], (60.6, 39.0), "K9", "L4"),
                     "FMC_SDNE0": via_end([(57.5, 37.0), (57.9, 37.4)], (59.0, 37.4), "J8", "L4"),
                     "FMC_A2": via_end([(57.8, 34.6)], (58.2, 35.0), "F7", "L4")})
        # l4s: A4 A5 D10 D15 south through the strip, east under the SDRAM, north into the aisle's south end
        s4 = ["FMC_A4", "FMC_A5", "FMC_D10", "FMC_D15"]
        y0 = {"FMC_A4": 37.65, "FMC_A5": 38.3, "FMC_D10": 38.95, "FMC_D15": 40.9}
        xs = {"FMC_A4": 47.5, "FMC_A5": 47.25, "FMC_D10": 47.0, "FMC_D15": 46.75}
        yb = {"FMC_A4": 43.6, "FMC_A5": 43.85, "FMC_D10": 44.1, "FMC_D15": 44.35}
        xn = {"FMC_A4": 56.4, "FMC_A5": 56.65, "FMC_D10": 57.0, "FMC_D15": 57.25}
        legs = [("E", y0), ("SE", {n: xs[n] - y0[n] - 0.3 for n in s4}), ("S", xs), ("SE", {n: xs[n] - yb[n] + 0.3 for n in s4}),
                ("E", yb), ("NE", {n: xn[n] + yb[n] - 0.4 for n in s4}), ("N", xn)]
        l4s = bund("l4s", s4, "L4", legs, 46.2, 40.0)
        bus.add(l4s, start={n: m[n] for n in s4},
                end={"FMC_A4": via_end([(56.4, 36.6), (56.0, 36.2), (53.8, 36.2)], (53.4, 35.8), "G1", "L4"),
                     "FMC_A5": via_end([(56.65, 35.8), (56.25, 35.4), (54.6, 35.4)], (54.2, 35.8), "G2", "L4"),
                     "FMC_D10": via_end([(57.0, 40.2), (57.4, 39.8)], (59.0, 39.8), "L8", "L4"),
                     "FMC_D15": via_end([(57.25, 41.0), (57.65, 40.6)], (59.0, 40.6), "M8", "L4")})
        # l4ss: D17 D16 south about: east below everything, up the SDRAM's east side, west along its north side
        ss = ["FMC_D17", "FMC_D16"]
        xs = {"FMC_D17": 43.9, "FMC_D16": 43.25}
        ye = {"FMC_D17": 44.85, "FMC_D16": 45.1}
        xn = {"FMC_D17": 61.75, "FMC_D16": 62.0}
        yw = {"FMC_D17": 29.85, "FMC_D16": 29.6}
        legs = [("S", xs), ("SE", {n: xs[n] - ye[n] + 0.3 for n in ss}), ("E", ye), ("NE", {n: xn[n] + ye[n] - 0.6 for n in ss}),
                ("N", xn), ("NW", {n: xn[n] - yw[n] - 0.6 for n in ss}), ("W", yw)]
        l4ss = bund("l4ss", ss, "L4", legs, 43.0, 61.0)
        bus.add(l4ss, start={n: m[n] for n in ss},
                end={"FMC_D17": via_end([(60.2, 30.25), (60.2, 30.6)], (59.8, 31.0), "A8", "L4"),
                     "FMC_D16": via_end([(59.4, 30.0), (59.4, 31.4)], (59.8, 31.8), "B9", "L4")})
    if "L6" in LAYERS:
        bus.keep({"FMC_BA1": m["FMC_BA1"]})
    R.update(bus.routes())
    return R
