"""Line-order assignment of the SDRAM bus (RTE-13): which layer, which way round the MCU, which SDRAM ball.

    python stm32h743_sdram/line_order.py scan                      every SDRAM rotation x byte-lane mapping, one line each
    python stm32h743_sdram/line_order.py solve <rot> <map> [out]   one case in full: table, crossings, lengths, swap.csv
  options: --gap <mm>  body-to-body distance (default 8)   --dy <mm>  SDRAM centre below the MCU centre (default 0)
           --free-pass N  layers the buses passing a side of the MCU must leave free there (default 1)

Runs on the system Python (needs scipy >= 1.9 for the solver); ball positions come from balls.json, written by
    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\line_order.py dump

Deterministic: no search by trial routing. The model (all of it is an estimate to be confirmed by the bundles):

  MCU     Every ball leaves through one of its nearest sides (depth = rows from that side, at most 4). Balls of
          depth 1-2 leave on L1, deeper ones through a via on an inner layer. Outside the package a net runs on
          one "river" layer (L1, L4 or L6) to the SDRAM. Vias: 0 if depth <= 2 and the river is L1, otherwise 2
          (one at each end; on an inner river the SDRAM ball gets a via next to it).
  order   t = position of the exit on the MCU outline, clockwise from the south-west corner. A west-side net may
          go north-about (t) or south-about (t + perimeter). u = position of the entry on the SDRAM outline,
          anticlockwise from the middle of the side facing away from the MCU. Rows 1-2 of the SDRAM are entered
          from outside, the inner row from one of the two open ends of the aisle (deepest ball nearest the middle).
          Two nets on one river layer do not cross when t and u are in the same order and their t differ by less
          than one turn. The same order is asked on inner layers, which is stricter than needed there.
  swaps   Data bits are free inside a byte lane and lanes are free among the four SDRAM bytes (NBL follows its
          lane to that byte's DQM). The solver places data nets into a class of balls (rows 1-2 of a quadrant, or
          its inner balls through one end); the bits inside a class are then matched exactly.
  length  Octile shortest path from the exit round the two packages to the entry, plus the escape at both ends.
"""
import itertools, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BALLS = os.path.join(HERE, "out", "sketch", "balls.json")
LAYERS = ("L1", "L4", "L6")
MCU_HALF = 6.5            # the ring the rivers start from: package 5.0 + rule area 1.0 + 0.5
SD_HALF = (4.0, 6.5)      # SDRAM body half size at rotation 0
VIA_COST = 3.0            # mm of objective per via
OPENING_CAP = 12          # tracks through one end of the aisle per layer (3.2 mm between ball rows)
LEN_CAP = 55.0
DETOUR_CAP = 22.0         # options longer than a net's shortest one by more than this are not offered
UNDER_LAYERS = ("L4",)    # layers that may cross under the MCU
EAST_END = False          # offer routes round the far end of the SDRAM
UNDER_CAP = 10            # tracks under the MCU per layer (ring rows E and L, four channels between the centre vias)
EAST_CHANNELS = 14        # row channels of the MCU's east side per inner layer
W_LANE, W_ADDR = 2.0, 0.5
SKIP_COST = 500.0         # a net left without a place (diagnosis only)


def dump():
    import pcbnew
    b = pcbnew.LoadBoard(os.path.join(HERE, "stm32h743_sdram.kicad_pcb"))
    out = {}
    for ref in ("U201", "U301"):
        fp = b.FindFootprintByReference(ref)
        c = fp.GetPosition()
        out[ref] = {"pos": [c.x / 1e6 - 100, c.y / 1e6 - 100], "rot": fp.GetOrientationDegrees(),
                    "pads": {p.GetNumber(): [round(p.GetPosition().x / 1e6 - 100, 3), round(p.GetPosition().y / 1e6 - 100, 3), p.GetNetname()]
                             for p in fp.Pads()}}
    os.makedirs(os.path.dirname(BALLS), exist_ok=True)
    json.dump(out, open(BALLS, "w"), indent=0)
    print("wrote", BALLS)


def octile(a, b):
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)


def blocked(a, b, box, eps=1e-6):
    """Does segment a-b pass through the inside of box (x0, y0, x1, y1)?"""
    x0, y0, x1, y1 = box[0] + eps, box[1] + eps, box[2] - eps, box[3] - eps
    t0, t1 = 0.0, 1.0
    d = (b[0] - a[0], b[1] - a[1])
    for p, q in ((-d[0], a[0] - x0), (d[0], x1 - a[0]), (-d[1], a[1] - y0), (d[1], y1 - a[1])):
        if abs(p) < 1e-12:
            if q < 0:
                return False
        else:
            r = q / p
            if p < 0:
                t0 = max(t0, r)
            else:
                t1 = min(t1, r)
    return t0 < t1 - 1e-9


def seg_hit(a, b, c, d):
    """Do the open segments a-b and c-d cross?"""
    def o(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return o(a, b, c) * o(a, b, d) < -1e-12 and o(c, d, a) * o(c, d, b) < -1e-12


def shortest(a, b, nodes, boxes, walls=()):
    pts = [a] + list(nodes) + [b]
    n = len(pts)
    dist = [math.inf] * n
    dist[0] = 0.0
    done = [False] * n
    for _ in range(n):
        i = min((k for k in range(n) if not done[k]), key=lambda k: dist[k], default=None)
        if i is None or dist[i] == math.inf:
            break
        done[i] = True
        for j in range(n):
            if not done[j] and not any(blocked(pts[i], pts[j], bx) for bx in boxes) and not any(seg_hit(pts[i], pts[j], *w) for w in walls):
                dist[j] = min(dist[j], dist[i] + octile(pts[i], pts[j]))
    return dist[-1]


class Model:
    def __init__(self, rot, gap=8.0, dy=0.0):
        B = json.load(open(BALLS))
        self.rot, self.gap = rot, gap
        m, s = B["U201"], B["U301"]
        self.mc = tuple(m["pos"])
        # SDRAM balls in the footprint's own frame (rotation 0), whatever the board's rotation is now
        th = math.radians(s["rot"])
        local = {}
        for num, (x, y, net) in s["pads"].items():
            dx, dy_ = x - s["pos"][0], y - s["pos"][1]
            local[num] = (round(dx * math.cos(th) - dy_ * math.sin(th), 3), round(dx * math.sin(th) + dy_ * math.cos(th), 3), net)
        th = math.radians(rot)
        self.c, self.s_ = math.cos(th), math.sin(th)
        hw = SD_HALF[0] if rot % 180 == 0 else SD_HALF[1]
        hh = SD_HALF[1] if rot % 180 == 0 else SD_HALF[0]
        self.sc = (self.mc[0] + 5.0 + gap + hw, self.mc[1] + dy)
        self.sbox = (self.sc[0] - hw, self.sc[1] - hh, self.sc[0] + hw, self.sc[1] + hh)
        self.mbox = (self.mc[0] - MCU_HALF, self.mc[1] - MCU_HALF, self.mc[0] + MCU_HALF, self.mc[1] + MCU_HALF)
        self.P = 8 * MCU_HALF
        self.U = 4 * (hw + hh)
        self.mcu = {net: (num, x, y) for num, (x, y, net) in m["pads"].items() if net.startswith("FMC_") and net != "FMC_SDCLK_R"}
        # the clock reaches the SDRAM as FMC_SDCLK_R behind the series resistor: one line for the order
        self.sd = {}
        for num, (lx, ly, net) in local.items():
            if net.startswith("FMC_"):
                self.sd[num] = dict(net="FMC_SDCLK" if net == "FMC_SDCLK_R" else net, lx=lx, ly=ly)
        for num, b in self.sd.items():
            b["entries"] = self._entries(b["lx"], b["ly"])
            b["pos"] = self.to_board(b["lx"], b["ly"])
            n = b["net"]
            b["byte"] = int(n[5:]) // 8 if n.startswith("FMC_D") else int(n[7:]) if n.startswith("FMC_NBL") else None
            b["quad"] = (1 if b["lx"] > 0 else -1, 1 if b["ly"] > 0 else -1)
        self.quad_of_byte = {}
        for b in self.sd.values():
            if b["byte"] is not None:
                assert self.quad_of_byte.setdefault(b["byte"], b["quad"]) == b["quad"]

    def to_board(self, lx, ly):
        return (self.sc[0] + lx * self.c + ly * self.s_, self.sc[1] - lx * self.s_ + ly * self.c)

    def u_of(self, p):
        x0, y0, x1, y1 = self.sbox
        yc, W, H = (y0 + y1) / 2, x1 - x0, y1 - y0
        x, y = p
        e = 1e-6
        if abs(x - x1) < e and y <= yc:
            return yc - y
        if abs(y - y0) < e:
            return H / 2 + (x1 - x)
        if abs(x - x0) < e:
            return H / 2 + W + (y - y0)
        if abs(y - y1) < e:
            return H / 2 + W + H + (x - x0)
        if abs(x - x1) < e:
            return H / 2 + W + H + W + (y1 - y)
        raise ValueError(p)

    def _entries(self, lx, ly):
        """[(kind, entry point on the box, u, length inside)]: kind 'out' or 'endN' / 'endS' (footprint frame)."""
        sg = 1 if lx > 0 else -1
        out = []
        if abs(lx) > 2.0:
            p = self.to_board(sg * SD_HALF[0], ly)
            out.append(("out", p, self.u_of(p), SD_HALF[0] - abs(lx)))
        else:
            for e, name in ((-1, "endA"), (1, "endR")):
                frac = (SD_HALF[1] - e * ly) / (2 * SD_HALF[1])
                p = self.to_board(sg * (1.4 - 1.2 * frac), e * SD_HALF[1])
                out.append((name, p, self.u_of(p), SD_HALF[1] - e * ly + 0.8))
            p = self.to_board(sg * SD_HALF[0], ly)          # inner layers only: from its own side, between the vias of rows 1-2
            out.append(("outv", p, self.u_of(p), SD_HALF[0] - abs(lx)))
        return out

    def exits(self, net):
        """[(side, depth, exit point, s)] of an MCU ball: every side it is at most 4 rows from."""
        num, x, y = self.mcu[net]
        cx, cy = self.mc
        d = {"W": round((x - cx + 4.55) / 0.65) + 1, "E": round((cx + 4.55 - x) / 0.65) + 1,
             "N": round((y - cy + 4.55) / 0.65) + 1, "S": round((cy + 4.55 - y) / 0.65) + 1}
        out = []
        for side, dep in d.items():
            if dep > 4:
                continue
            H = MCU_HALF
            if side == "W":
                p, s = (cx - H, y), (cy + H) - y
            elif side == "N":
                p, s = (x, cy - H), 2 * H + (x - (cx - H))
            elif side == "E":
                p, s = (cx + H, y), 4 * H + (y - (cy - H))
            else:
                p, s = (x, cy + H), 6 * H + ((cx + H) - x)
            out.append((side, dep, p, s))
        return out

    # ways round the MCU: (side, way) -> (corners passed, turns added to t). cw = clockwise seen from the top.
    WAYS = {("W", "cw"): (("NW", "NE"), 0), ("W", "ccw"): (("SW", "SE"), 1),
            ("N", "cw"): (("NE",), 0), ("N", "ccw"): (("NW", "SW", "SE"), 1),
            ("S", "ccw"): (("SE",), 0), ("S", "cw"): (("SW", "NW", "NE"), -1),
            ("E", "-"): ((), 0), ("E", "under"): ((), 0)}

    def path_len(self, side, way, p_exit, p_entry, turn):
        """turn: 0 = the path does not pass the far (east) end of the SDRAM; -1 = round it from the north to an
        entry in the south half; +1 = round it from the south to an entry in the north half."""
        x0, y0, x1, y1 = self.mbox
        g = 0.01
        corners = {"NW": (x0 - g, y0 - g), "NE": (x1 + g, y0 - g), "SE": (x1 + g, y1 + g), "SW": (x0 - g, y1 + g)}
        nodes = [corners[k] for k in self.WAYS[(side, way)][0]]
        a0, b0, a1, b1 = self.sbox
        ne, se = (a1 + g, b0 - g), (a1 + g, b1 + g)
        sd = [(a0 - g, b0 - g), ne, se, (a0 - g, b1 + g)]
        wall = [((a1, (b0 + b1) / 2), (a1 + 200.0, (b0 + b1) / 2))]
        boxes = [self.mbox, self.sbox]
        if turn == 0:
            return shortest(p_exit, p_entry, nodes + sd, boxes, wall)
        first, second = (ne, se) if turn < 0 else (se, ne)
        return shortest(p_exit, first, nodes + sd, boxes, wall) + octile(first, second) + shortest(second, p_entry, [], boxes, wall)

    def options(self, lane_map):
        """lane_map[mcu lane] = SDRAM byte. -> list of option dicts."""
        opts = []
        fixed_ball = {b["net"]: num for num, b in self.sd.items() if b["byte"] is None}
        dqm = {b["byte"]: num for num, b in self.sd.items() if b["net"].startswith("FMC_NBL")}
        classes = {}                                  # (quad, kind) -> [ball numbers] of data balls
        for num, b in self.sd.items():
            if b["net"].startswith("FMC_D"):
                for kind, p, u, inside in b["entries"]:
                    classes.setdefault((b["quad"], "out" if kind == "outv" else kind), []).append(num)
        self.classes = classes
        for net in sorted(self.mcu):
            lane = None
            if net.startswith("FMC_D"):
                lane = int(net[5:]) // 8
                quad = self.quad_of_byte[lane_map[lane]]
                targets = []
                for (q, kind), balls in classes.items():
                    if q == quad:
                        es = [next(e for e in self.sd[n]["entries"] if e[0] in ((kind, "outv") if kind == "out" else (kind,))) for n in balls]
                        us = [e[2] for e in es]
                        mid = es[len(es) // 2]
                        targets.append(dict(cls=(q, kind), ball=None, ulo=min(us), uhi=max(us), entry=mid[1], inside=sum(e[3] for e in es) / len(es), kind=kind))
            else:
                if net.startswith("FMC_NBL"):
                    lane = int(net[7:])
                    ball = dqm[lane_map[lane]]
                else:
                    ball = fixed_ball[net]
                targets = [dict(cls=None, ball=ball, ulo=u, uhi=u, entry=p, inside=inside, kind=kind) for kind, p, u, inside in self.sd[ball]["entries"]]
            mine = []
            exits = [(side, way, dep, p_exit, s + turns * self.P, dep * 0.65 + (MCU_HALF - 4.55 - 0.65), LAYERS)
                     for side, dep, p_exit, s in self.exits(net) for (sd, way), (_, turns) in self.WAYS.items() if sd == side]
            exits += self.under(net)
            for side, way, dep, p_exit, t, esc, layers in exits:
                for tg in targets:
                    half = self.U / 2
                    for turn in ((0, -1 if tg["ulo"] > half else 1) if EAST_END else (0,)):
                        ln = esc + self.path_len(side, way, p_exit, tg["entry"], turn) + tg["inside"]
                        if ln > LEN_CAP:
                            continue
                        for layer in layers:
                            if tg["kind"] == "outv" and layer == "L1":
                                continue
                            vias = 0 if (dep <= 2 and layer == "L1") else 2
                            o = dict(net=net, lane=lane, side=side, wind=way, depth=dep, t=t, layer=layer, vias=vias, length=ln, turn=turn, **tg)
                            o["ulo"] += turn * self.U; o["uhi"] += turn * self.U
                            mine.append(o)
            if mine:
                best = min(o["length"] for o in mine)
                opts += [o for o in mine if o["length"] <= best + DETOUR_CAP]
        return opts

    def under(self, net):
        """Exits to the east under the MCU, on L4 only (L6 under the package is kept for the decoupling):
        west-side balls of rows E-K run east through the ball-free ring and between the centre vias; south-side
        balls of depth 3-4 join the ring row L. They come out on the east side in the order of their rows."""
        num, x, y = self.mcu[net]
        cx, cy = self.mc
        H = MCU_HALF
        row = round((y - cy + 4.55) / 0.65)          # 0 = A
        col = round((x - cx + 4.55) / 0.65)
        out = []
        if col <= 3 and 4 <= row <= 10:
            ye = y
        elif row >= 11 and row <= 12 and 4 <= col <= 10:
            ye = cy + 4.55 - 3 * 0.65 + 0.01 * (row - 10) - 0.001 * col       # ring row L, a little below the west ones
        else:
            return out
        dep = min(col, 14 - col, row, 14 - row) + 1
        out.append(("E", "under", dep, (cx + H, ye), 4 * H + (ye - (cy - H)), (cx + H - x) + abs(ye - y) + 1.0, UNDER_LAYERS))
        return out


def solve(model, lane_map, free_pass=1, time_limit=60, allow_skip=False):
    """Every layer holds one chain of options ordered by t with u not decreasing: a path from a source to a sink
    in the graph of compatible options (edge variables continuous), each net on exactly one path."""
    import numpy as np
    from scipy.optimize import milp, LinearConstraint, Bounds
    from scipy.sparse import coo_matrix
    O = model.options(lane_map)
    n = len(O)
    nets = sorted({o["net"] for o in O})
    if len(nets) < len(model.mcu):
        return None
    lane_of = {o["net"]: o["lane"] for o in O}
    groups = [[x for x in nets if lane_of[x] == k] for k in range(4)] + [[x for x in nets if lane_of[x] is None]]
    passes = [(sd, l) for sd in "NS" for l in LAYERS]
    t = np.array([o["t"] for o in O]); ulo = np.array([o["ulo"] for o in O]); uhi = np.array([o["uhi"] for o in O])
    lay = np.array([LAYERS.index(o["layer"]) for o in O]); netid = np.array([nets.index(o["net"]) for o in O])
    tol = 0.2
    order = np.lexsort((np.arange(n), ulo, t))
    rank = np.empty(n, int); rank[order] = np.arange(n)
    before = rank[:, None] < rank[None, :]
    same = (lay[:, None] == lay[None, :]) & (netid[:, None] != netid[None, :])
    dt = t[None, :] - t[:, None]
    far = (np.abs(dt) >= model.P - 1e-6) | (np.abs(ulo[:, None] - ulo[None, :]) >= model.U - 1e-6)
    ok = same & before & ((dt <= tol) | (ulo[:, None] <= uhi[None, :] + 1e-6)) & ~far
    ei, ej = np.nonzero(ok)
    m = len(ei)
    fi, fj = np.nonzero(np.triu(same & far, 1))
    # variables: z, src, snk, spreads (10), passes (6), skip (nets), edges
    iz, isrc, isnk = 0, n, 2 * n
    iM = 3 * n; ip = iM + 10; isk = ip + len(passes); ie = isk + len(nets)
    nv = ie + m
    R, C, V, lo, hi = [], [], [], [], []
    def row(cols, vals, a, b):
        r = len(lo)
        R.extend([r] * len(cols)); C.extend(cols); V.extend(vals); lo.append(a); hi.append(b)
    for k in range(len(nets)):
        idx = list(np.nonzero(netid == k)[0])
        row(idx + [isk + k], [1.0] * (len(idx) + 1), 1, 1)
    into = [[] for _ in range(n)]; outof = [[] for _ in range(n)]
    for e, (i, j) in enumerate(zip(ei, ej)):
        outof[i].append(ie + e); into[j].append(ie + e)
    for i in range(n):
        row([isrc + i, iz + i] + into[i], [1.0, -1.0] + [1.0] * len(into[i]), 0, 0)
        row([isnk + i, iz + i] + outof[i], [1.0, -1.0] + [1.0] * len(outof[i]), 0, 0)
    for l in range(3):
        idx = list(np.nonzero(lay == l)[0])
        row([isrc + i for i in idx], [1.0] * len(idx), 0, 1)
    for i, j in zip(fi, fj):
        row([i, j], [1.0, 1.0], 0, 1)
    for cls, balls in model.classes.items():
        for lane in range(4):
            idx = [i for i, o in enumerate(O) if o["cls"] == cls and o["lane"] == lane]
            if idx:
                row(idx, [1.0] * len(idx), 0, len(balls))
            idx = [i for i in idx if O[i]["layer"] == "L1"]
            if idx and cls[1] == "out":
                row(idx, [1.0] * len(idx), 0, sum(1 for b in balls if abs(model.sd[b]["lx"]) > 2.0))
    for lane in range(4):
        q = model.quad_of_byte[lane_map[lane]]
        inner = [i for i, o in enumerate(O) if o["lane"] == lane and o["cls"] and o["kind"] != "out"]
        n_in = len(model.classes.get((q, "endA"), []))
        if inner:
            row(inner, [1.0] * len(inner), 0, n_in)
    for kind in ("endA", "endR"):
        for l in range(3):
            idx = [i for i, o in enumerate(O) if o["kind"] == kind and lay[i] == l]
            if idx:
                row(idx, [1.0] * len(idx), 0, OPENING_CAP)
    for l in range(1, 3):
        idx = [i for i, o in enumerate(O) if o["wind"] == "under" and lay[i] == l]
        if idx:
            row(idx, [1.0] * len(idx), 0, UNDER_CAP)
        idx = [i for i, o in enumerate(O) if lay[i] == l and o["side"] == "E" and (o["wind"] == "under" or o["depth"] >= 3)]
        if idx:
            row(idx, [1.0] * len(idx), 0, EAST_CHANNELS)
    cost = np.zeros(nv)
    for i, o in enumerate(O):
        cost[i] = o["length"] + VIA_COST * o["vias"]
    for g, members in enumerate(groups):
        if not members:
            continue
        w = W_LANE if g < 4 else W_ADDR
        cost[iM + 2 * g] = w; cost[iM + 2 * g + 1] = -w
        for x in members:
            k = nets.index(x)
            idx = list(np.nonzero(netid == k)[0])
            row(idx + [iM + 2 * g], [O[i]["length"] for i in idx] + [-1.0], -np.inf, 0)
            row(idx + [iM + 2 * g + 1, isk + k], [O[i]["length"] for i in idx] + [-1.0, 1000.0], 0, np.inf)
    for pi, (sd, l) in enumerate(passes):
        idx = [i for i, o in enumerate(O) if o["layer"] == l and along_side(o, sd)]
        for i in idx:
            row([i, ip + pi], [1.0, -1.0], -np.inf, 0)
    for sd in "NS":
        idx = [ip + pi for pi, (s2, l) in enumerate(passes) if s2 == sd]
        row(idx, [1.0] * len(idx), 0, 3 - free_pass)
    A = coo_matrix((V, (R, C)), shape=(len(lo), nv)).tocsr()
    integrality = np.zeros(nv); integrality[:n] = 1; integrality[ip:ie] = 1
    lb = np.zeros(nv); ub = np.ones(nv); ub[iM:ip] = 1000
    cost[isk:ie] = SKIP_COST
    if not allow_skip:
        ub[isk:ie] = 0
    res = milp(cost, constraints=LinearConstraint(A, np.array(lo), np.array(hi)), integrality=integrality, bounds=Bounds(lb, ub),
               options={"time_limit": time_limit, "mip_rel_gap": 0.02})
    if res.x is None:
        return None
    chosen = [O[i] for i in range(n) if res.x[i] > 0.5]
    left = [x for k, x in enumerate(nets) if res.x[isk + k] > 0.5]
    return dict(chosen=chosen, cost=res.fun, optimal=res.status == 0, n_opts=n, n_cross=m, left=left)


def along_side(o, sd):
    """Does the river of this option run along the north / south side of the MCU?"""
    if sd == "N":
        return o["side"] == "N" or (o["side"], o["wind"]) in (("W", "cw"), ("S", "cw"))
    return o["side"] == "S" or (o["side"], o["wind"]) in (("W", "ccw"), ("N", "ccw"))


def match_bits(model, chosen):
    """Give every data net its ball: same order of t and u on each layer, smallest spread of the estimate. -> ok"""
    ok = True
    used = set()
    for cls in sorted(model.classes, key=lambda c: c[1] == "out"):          # the two ends first
        nets = sorted((o for o in chosen if o["cls"] == cls), key=lambda o: o["t"])
        if not nets:
            continue
        kinds = ("out", "outv") if cls[1] == "out" else (cls[1],)
        ent = {b: next(e for e in model.sd[b]["entries"] if e[0] in kinds) for b in model.classes[cls] if b not in used}
        balls_u = sorted(ent, key=lambda b: ent[b][2])
        if len(balls_u) < len(nets):
            ok = False
            continue
        best = None
        for perm in itertools.permutations(balls_u, len(nets)):
            good = True
            for a in range(len(nets)):
                if nets[a]["layer"] == "L1" and ent[perm[a]][0] == "outv":
                    good = False; break
                for b in range(a + 1, len(nets)):
                    if nets[a]["layer"] == nets[b]["layer"] and nets[b]["t"] - nets[a]["t"] > 0.2 and ent[perm[a]][2] > ent[perm[b]][2]:
                        good = False; break
                if not good:
                    break
            if not good:
                continue
            ls = [o["length"] - o["inside"] + ent[q][3] for o, q in zip(nets, perm)]
            score = max(ls) - min(ls)
            if best is None or score < best[0]:
                best = (score, perm)
        if best is None:
            ok = False
            continue
        for o, q in zip(nets, best[1]):
            u = ent[q][2] + o["turn"] * model.U
            o["ball"], o["ulo"], o["uhi"], o["kind"] = q, u, u, ent[q][0]
            used.add(q)
    return ok


def crossings(model, chosen):
    """Pairs on one layer whose order of t and u disagrees, with the exact balls."""
    bad = []
    for a, b in itertools.combinations(chosen, 2):
        if a["layer"] != b["layer"]:
            continue
        dt, du = a["t"] - b["t"], a["ulo"] - b["ulo"]
        if abs(dt) >= model.P or abs(du) >= model.U or (abs(dt) > 0.2 and abs(du) > 1e-6 and dt * du < 0):
            bad.append((a["layer"], a["net"], b["net"]))
    return bad


def summary(model, chosen):
    L = {o["net"]: o["length"] for o in chosen}
    lanes = []
    for k in range(4):
        v = [o["length"] for o in chosen if o["lane"] == k] or [0.0]
        lanes.append((min(v), max(v)))
    ad = [o["length"] for o in chosen if o["lane"] is None] or [0.0]
    return dict(lanes=lanes, addr=(min(ad), max(ad)), clk=L.get("FMC_SDCLK", 0.0), total=sum(L.values()), longest=max(L.values()),
                vias=sum(o["vias"] for o in chosen), per_layer={l: sum(o["layer"] == l for o in chosen) for l in LAYERS})


def scan_one(job):
    rot, perm, gap, dy, fp, tl, skip, spread = job
    global W_LANE, W_ADDR
    if not spread:
        W_LANE = W_ADDR = 0.0
    m = Model(rot, gap, dy)
    r = solve(m, perm, fp, time_limit=tl, allow_skip=skip)
    tag = "%3d %s" % (rot, "".join(map(str, perm)))
    if not r:
        return tag + " no assignment"
    okb = match_bits(m, r["chosen"])
    s = summary(m, r["chosen"])
    return "%s  %2d  %7.1f %6.1f  %5.1f   %3d   %2d/%2d/%2d   %s   %4.1f-%4.1f   %4.1f  %s%s %s" % (
        tag, len(r["left"]), r["cost"], s["total"], s["longest"], s["vias"], *[s["per_layer"][l] for l in LAYERS],
        " ".join("%4.1f" % (b - a) for a, b in s["lanes"]), *s["addr"], s["clk"],
        "ok" if okb and not crossings(m, r["chosen"]) else "BITS", "" if r["optimal"] else " (time limit)", " ".join(x[4:] for x in r["left"]))


def args_opt(argv, name, default, cast=float):
    return cast(argv[argv.index(name) + 1]) if name in argv else default


def main(argv):
    if argv[0] == "dump":
        return dump()
    gap, dy, fp = args_opt(argv, "--gap", 8.0), args_opt(argv, "--dy", 0.0), args_opt(argv, "--free-pass", 1, int)
    skip, spread = "--skip" in argv, "--no-spread" not in argv
    if argv[0] == "scan":
        from concurrent.futures import ProcessPoolExecutor
        rots = [args_opt(argv, "--rot", 0, int)] if "--rot" in argv else (0, 90, 180, 270)
        jobs = [(rot, perm, gap, dy, fp, args_opt(argv, "--time", 30), skip, spread) for rot in rots for perm in itertools.permutations(range(4))]
        print("rot map  left  cost   total  longest  vias  L1/L4/L6   lane spreads          addr min-max  clk   bits", flush=True)
        with ProcessPoolExecutor(args_opt(argv, "--jobs", 8, int)) as ex:
            for line in ex.map(scan_one, jobs):
                print(line, flush=True)
        return
    if argv[0] == "solve":
        rot, perm = int(argv[1]), tuple(int(c) for c in argv[2])
        out = argv[3] if len(argv) > 3 and not argv[3].startswith("--") else None
        m = Model(rot, gap, dy)
        if not spread:
            global W_LANE, W_ADDR
            W_LANE = W_ADDR = 0.0
        r = solve(m, perm, fp, time_limit=args_opt(argv, "--time", 120), allow_skip=skip)
        if not r:
            sys.exit("no assignment")
        okb = match_bits(m, r["chosen"])
        bad = crossings(m, r["chosen"])
        ch = sorted(r["chosen"], key=lambda o: (o["layer"], o["t"]))
        lines = ["SDRAM rot %d, gap %.1f, dy %.1f, lane map %s (MCU lane -> SDRAM byte), %d options, %d compatible pairs, %s" % (
            rot, gap, dy, "".join(map(str, perm)), r["n_opts"], r["n_cross"], "optimal" if r["optimal"] else "time limit"),
            "SDRAM centre (%.2f, %.2f)" % m.sc,
            "bit matching %s; crossings left on a layer: %d %s" % ("ok" if okb else "FAILED", len(bad), bad[:6] if bad else ""),
            "left without a place: %s" % (" ".join(r["left"]) or "none"),
            "layer net          MCU  side way depth  SDRAM entry  est.mm vias"]
        for o in ch:
            num = m.mcu[o["net"]][0]
            lines.append("%-4s %-12s %-4s %s    %-4s %d     %-4s  %-5s  %5.1f  %d" % (
                o["layer"], o["net"], num, o["side"], o["wind"] + ("" if not o["turn"] else " east-end"), o["depth"], o["ball"], o["kind"], o["length"], o["vias"]))
        s = summary(m, r["chosen"])
        for k, (a, b) in enumerate(s["lanes"]):
            lines.append("lane %d -> byte %d: %.1f-%.1f mm, spread %.1f" % (k, perm[k], a, b, b - a))
        lines.append("address/command/clock: %.1f-%.1f mm, spread %.1f; clock %.1f" % (*s["addr"], s["addr"][1] - s["addr"][0], s["clk"]))
        lines.append("total %.1f mm, longest %.1f, vias %d, per layer %s" % (s["total"], s["longest"], s["vias"], s["per_layer"]))
        for sd in "NS":
            lines.append("rivers along the %s side of the MCU: %s" % (sd, {l: sum(1 for o in ch if o["layer"] == l and along_side(o, sd)) for l in LAYERS}))
        print("\n".join(lines))
        if out:
            os.makedirs(out, exist_ok=True)
            open(os.path.join(out, "line_order.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
            json.dump(dict(rot=rot, gap=gap, dy=dy, lane_map=perm, centre=m.sc,
                           nets=[{k: o[k] for k in ("net", "layer", "side", "wind", "turn", "depth", "ball", "kind", "length", "vias", "t", "ulo")} for o in ch]),
                      open(os.path.join(out, "line_order.json"), "w"), indent=1)
            with open(os.path.join(out, "swap.csv"), "w", encoding="utf-8", newline="\n") as f:
                f.write("sdram,net\n")
                for o in sorted(ch, key=lambda o: o["net"]):
                    old = m.sd[o["ball"]]["net"]
                    if old.startswith("FMC_D") or old.startswith("FMC_NBL"):
                        f.write("%s,%s\n" % (old.replace("FMC_D", "DQ").replace("FMC_NBL", "DQM"), o["net"]))


if __name__ == "__main__":
    main(sys.argv[1:])
