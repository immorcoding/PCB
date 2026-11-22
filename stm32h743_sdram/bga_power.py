"""Supply and ground fan-out of the two BGAs and the bottom decoupling under them (stop 5, part B), for
routes_power_bga.py. Deterministic: the same board, sketch and obstacle board give the same copper, so the group
builds the same on the real board and on the line-order sketch copy.

Per supply or ground ball (GND, +3V3_MCU, +3V3_SDRAM, VDDA_MCU, VCAP1, VCAP2):
  a 0.30 / 0.15 via at one of the four ball-gap points round the ball (the centre of four ball positions, never on
  a pad), joined by a straight 45 degree dog-bone on L1. A site has to be legal against every pad, the SDRAM
  line-order sketch (its tracks and vias on every layer), part A's copper and what was placed here before
  (busroute's Scene: clearance 0.09 in the rule areas, hole to copper 0.2), keep 0.45 mm centre to centre to every
  other via, stay clear of the drawn outer-layer regions of other nets (the VDDA_MCU pockets) and, for a supply
  net, sit inside its own L3 block.
  Choice among the legal sites, best first: under a capacitor pad of the ball's net that has no via yet (the pad
  over the via, the approved via-in-pad case), then near one (an L6 stub of <= STUB_MAX), and always: no signal
  ball of the package (not routed by the SDRAM sketch) may lose its last free ball-gap site, and the via should
  not join antipads of other vias on L2 / L3 / L5 into a longer slot (U31). A ball with no legal site of its
  own shares a neighbouring ball's via of the same net (reported).
Per bottom capacitor pad (and the bead) under the BGAs: a via of its net under the pad (in-pad), else a stub on
L6 to the nearest via of its net (ball vias first) no longer than STUB_MAX from the pad edge, else a via of its
own under the pad, else (ground) a via of its own within GND_VIA_MAX of the pad edge.
"""
import math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import cu_sketch                                            # noqa: E402
from busroute.board import Board                            # noqa: E402
from busroute.checks import Scene                           # noqa: E402
from busroute.geom import in_poly, seg_poly_dist, pt_seg    # noqa: E402

VIA_IN = (0.30, 0.15)            # inside the rule areas
VIA_OUT = (0.45, 0.20)           # outside
VIA_PITCH = 0.45                 # least centre distance between two vias, any nets (hole to copper 0.2 needs 0.425)
REGION_MARGIN = 0.1              # foreign copper to a drawn outer-layer region of another net, beyond its own size
PLANE_MARGIN = 0.15              # a supply via inside its L3 block by radius + this
STUB_MAX = 0.7                   # L6 stub, pad edge to via centre
GND_VIA_MAX = 1.0                # a capacitor's own ground via: pad edge to via centre
BONE_W = (0.2, 0.15, 0.09)       # dog-bone widths, first legal
STUB_W = (0.25, 0.2, 0.15, 0.1)  # L6 stub widths
WIDE_W = (0.3, 0.25, 0.2)        # VCAP stubs ("short and wide")
PLANE_CLR = 0.127                # zone clearance on L2 / L3 / L5 (copper.sketch plane_clearance default)
MINWIDTH = 0.2                   # zone minimum width (copper.sketch minwidth)
SLOT_FREE = 1.5                  # a chain of merged antipads up to this long costs nothing (U31 lists those over 2.0)
SLOT_W = 400                     # score per mm of chain beyond SLOT_FREE (a capacitor pad over the via scores 1000)
MERGE_COST = 1200                # per antipad of another via it joins on a plane (more than a capacitor pad over it)
SHARE_90_FIRST = os.environ.get("BGA_SHARE90", "1") == "1"   # a shared via (90 degrees, short dog-bone) before a via that joins antipads
SHARE_COST = 150                 # sharing a neighbour's via in line (180 degrees) instead of a site of its own
EDGE_SLIDE = 0.6                 # an edge via may sit up to this much beyond one pitch out, on the ball's own line
PARITY = {("U201", "GND"): 0, ("U201", "+3V3_MCU"): 1}     # checkerboard colour of a net's vias (parity_ok)
if os.environ.get("BGA_PARITY"):                 # experiments: "g,s" (colours of GND, +3V3_MCU; "-" = none)
    _g, _s = os.environ["BGA_PARITY"].split(",")
    PARITY = {k: int(v) for k, v in ((("U201", "GND"), _g), (("U201", "+3V3_MCU"), _s)) if v != "-"}
LATTICE = {"U201"}               # packages whose own capacitor vias stay on ball-gap sites (unrouted signal balls
                                 # escape through the channels); under the SDRAM every signal is in the line-order sketch
SUPPLY = {"+3V3_MCU", "+3V3_SDRAM"}


def r4(v):
    return round(v * 10000) / 10000


def pad_dist(p, pad):
    if pad.poly is None:
        return max(0.0, math.dist(p, pad.pos) - pad.r)
    x0, y0, x1, y1 = pad.box
    return math.hypot(max(x0 - p[0], 0.0, p[0] - x1), max(y0 - p[1], 0.0, p[1] - y1))


class BgaPlanner:
    def __init__(self, board, profile, sketch_path, power, caps, obstacle_board=None, obstacle_prefix="FMC_",
                 skip_items=None, forbid=(), protect=()):
        """power = {ref: [nets]}; caps = [pad names] of the bottom parts under the BGAs (in-pad allowed there);
        forbid = sites (x, y) no via of this group may take (kept for a signal ball's escape)."""
        self.b, self.pr = board, profile
        self.power = power
        self.caps = [board.pads[n] for n in caps if n in board.pads]
        self.cap_names = {p.name for p in self.caps}
        self.forbid = {(r4(x), r4(y)) for x, y in forbid}
        self.protect = list(protect)
        self.sc = Scene(board, profile, skip_items=skip_items)
        segs_old, vias_old = skip_items or (set(), set())
        self.vias = [(n, p) for n, p, d, h in board.vias if (n, round(p[0], 6), round(p[1], 6)) not in vias_old]
        if obstacle_board and os.path.normcase(os.path.abspath(obstacle_board)) != os.path.normcase(board.path):
            ob = Board(obstacle_board, board.origin)
            for n, lay, a, c, w, _ in ob.tracks:
                if n.startswith(obstacle_prefix):
                    self.sc.add(self.sc.seg(n, lay, a, c, w, False))
            for n, p, d, h in ob.vias:
                if n.startswith(obstacle_prefix):
                    self.sc.add(self.sc.via(n, p, d, h, False))
                    self.vias.append((n, p))
        self.areas = board.rule_areas(profile.area_names)
        sk = cu_sketch.load_sketch(sketch_path, len(board.cu))
        self.gap = sk.p["gap"] / 1e6
        ox, oy = sk.origin[0] / 1e6 - board.origin[0], sk.origin[1] / 1e6 - board.origin[1]
        self.regions = [(r.name, r.net, "L%d" % r.layer, [(x / 1e6 + ox, y / 1e6 + oy) for x, y in r.pts]) for r in sk.regions if not r.whole]
        self.rbox = [(min(q[0] for q in poly), min(q[1] for q in poly), max(q[0] for q in poly), max(q[1] for q in poly)) for _, _, _, poly in self.regions]
        self.l3_whole = next((r.net for r in sk.regions if r.whole and r.layer == 3), None)
        self._pn = {}
        self.mine = []                       # (net, p, size, kind) vias placed here
        self.chains, self.extras, self.log, self.done = {}, [], [], []
        self.allow = set()                   # cap pads that got a via in them
        self.grids = {ref: self._grid(ref) for ref in power}
        self.sites_taken = {}                # site -> net
        self.ball_via = {}                   # ball pad name -> site
        self.shared = []                     # (ball, site, with ball)
        self.nosite = {}                     # ball -> reason
        self.cap_conn = {}                   # pad name -> dict
        self._signal_free = {}
        self.ends = {}                       # (layer, x, y) -> unit directions of this group's segments ending there

    # ---------------------------------------------------------------- geometry of the packages
    def _grid(self, ref):
        pads = self.b.by_ref[ref]
        xs = sorted({p.pos[0] for p in pads}); ys = sorted({p.pos[1] for p in pads})
        pitch = round(min(b - a for a, b in zip(xs, xs[1:]) if b - a > 0.1), 4)
        h = pitch / 2
        x0, y0 = xs[0], ys[0]
        nx, ny = int(round((xs[-1] - x0) / pitch)) + 1, int(round((ys[-1] - y0) / pitch)) + 1
        ij = {p.name: (int(round((p.pos[0] - x0) / pitch)), int(round((p.pos[1] - y0) / pitch))) for p in pads}
        area = next(R for R in self.areas.values() if R[0] <= x0 and R[1] <= y0 and R[2] >= xs[-1] and R[3] >= ys[-1])
        sites = lambda p: [(r4(p.pos[0] + sx * h), r4(p.pos[1] + sy * h)) for sy in (-1, 1) for sx in (-1, 1)]
        return {"pitch": pitch, "h": h, "nx": nx, "ny": ny, "ij": ij, "area": area, "pads": pads, "sites": sites}

    def ring(self, ref, name):
        g = self.grids[ref]
        i, j = g["ij"][name]
        return min(i, j, g["nx"] - 1 - i, g["ny"] - 1 - j)

    # ---------------------------------------------------------------- regions and planes
    def _rdist(self, p, poly):
        d = min(pt_seg(p, a, c)[0] for a, c in zip(poly, poly[1:] + poly[:1]))
        return -d if in_poly(p, poly) else d

    def l3_net(self, p, margin):
        for name, net, lay, poly in self.regions:
            if lay == "L3":
                d = self._rdist(p, poly)
                if d <= -margin:
                    return net
                if d < self.gap + margin:
                    return None
        return self.l3_whole

    def plane_nets(self, p):
        """{layer: net of the plane there} for L2, L3, L5."""
        k = (round(p[0], 4), round(p[1], 4))
        if k not in self._pn:
            self._pn[k] = {"L2": "GND", "L3": self.l3_net(p, 0.0), "L5": "GND"}
        return self._pn[k]

    # ---------------------------------------------------------------- legality
    def via_why(self, net, p, size=VIA_IN, pads_ok=()):
        d, h = size
        r = d / 2
        if size == VIA_IN:
            if not any(R[0] + r <= p[0] <= R[2] - r and R[1] + r <= p[1] <= R[3] - r for R in self.areas.values()):
                return "not inside a rule area"
        else:
            for R in self.areas.values():
                if math.hypot(max(R[0] - p[0], 0.0, p[0] - R[2]), max(R[1] - p[1], 0.0, p[1] - R[3])) < r + 0.01:
                    return "rule area"
        if (r4(p[0]), r4(p[1])) in self.forbid:
            return "kept free for a signal ball"
        for pn, R in self.protect:
            if pn != net and math.hypot(max(R[0] - p[0], 0.0, p[0] - R[2]), max(R[1] - p[1], 0.0, p[1] - R[3])) < r + 0.2:
                return "protected strip of %s" % pn
        for n, q in self.vias:
            if math.dist(p, q) < VIA_PITCH - 1e-9:
                return "via of %s at (%.3f, %.3f)" % (n, q[0], q[1])
        for n, q, s, k in self.mine:
            if math.dist(p, q) < VIA_PITCH - 1e-9:
                return "via of %s at (%.3f, %.3f)" % (n, q[0], q[1])
        it = self.sc.via(net, p, d, h)
        for o in self.sc.near(it, 0.1):
            if o.pad is not None and o.pad.smd and o.pad.net == net:
                dd = math.dist(p, o.a) - o.r if o.kind == "round" else seg_poly_dist(p, p, o.poly)[0]
                if dd < r + 0.001 and o.pad.name not in self.cap_names and o.pad.name not in pads_ok:
                    return "on pad %s" % o.pad.name
        for (name, n, lay, poly), bx in zip(self.regions, self.rbox):
            if (lay in ("L1", "L6") and n != net and bx[0] - 1 < p[0] < bx[2] + 1 and bx[1] - 1 < p[1] < bx[3] + 1
                    and self._rdist(p, poly) < r + REGION_MARGIN):
                return "in region %s" % name
        why = self.sc.conflict([it])
        if why:
            return why
        if net in SUPPLY and self.l3_net(p, r + PLANE_MARGIN) != net:
            return "not inside the L3 block of %s" % net
        return None

    def seg_why(self, net, layer, a, c, w):
        if math.dist(a, c) < self.pr.min_seg - 1e-9:
            return "segment shorter than %.2f" % self.pr.min_seg
        it = self.sc.seg(net, layer, a, c, w)
        why = self.sc.conflict([it])
        if why:
            return why
        lo = (min(a[0], c[0]) - 1, min(a[1], c[1]) - 1, max(a[0], c[0]) + 1, max(a[1], c[1]) + 1)
        for (name, n, lay, poly), bx in zip(self.regions, self.rbox):
            if (lay == layer and n != net and bx[0] < lo[2] and lo[0] < bx[2] and bx[1] < lo[3] and lo[1] < bx[3]
                    and seg_poly_dist(a, c, poly)[0] < w / 2 + REGION_MARGIN):
                return "through region %s" % name
        return None

    def _put_via(self, net, p, size, kind):
        self.sc.add(self.sc.via(net, p, size[0], size[1], False))
        self.mine.append((net, p, size, kind))
        self.sites_taken[(r4(p[0]), r4(p[1]))] = net
        for c in self.caps:
            if c.net == net and pad_dist(p, c) < size[0] / 2 - 1e-6:
                self.allow.add(c.name)

    def _put_seg(self, net, layer, a, c, w):
        self.sc.add(self.sc.seg(net, layer, a, c, w, False))
        L = math.dist(a, c)
        for p, q in ((a, c), (c, a)):
            self.ends.setdefault((layer, r4(p[0]), r4(p[1])), []).append(((q[0] - p[0]) / L, (q[1] - p[1]) / L))

    def angle_ok(self, layer, p, q):
        """A new segment p -> q on `layer` makes at least 135 degrees with every segment of this group ending at p
        (the board's corner_angle rule also judges two tracks that meet at a via)."""
        L = math.dist(p, q)
        u = ((q[0] - p[0]) / L, (q[1] - p[1]) / L)
        return all(u[0] * v[0] + u[1] * v[1] < -0.70 for v in self.ends.get((layer, r4(p[0]), r4(p[1])), []))

    def outside(self, ref, s):
        """The ball-gap point lies beyond the outer ring of the package (in the lane round it)."""
        g = self.grids[ref]
        x0, y0 = min(p.pos[0] for p in g["pads"]), min(p.pos[1] for p in g["pads"])
        i, j = (s[0] - x0) / g["pitch"], (s[1] - y0) / g["pitch"]
        return i < 0 or j < 0 or i > g["nx"] - 1 or j > g["ny"] - 1

    # ---------------------------------------------------------------- plane slots (U31)
    def merge_dist(self, s1, s2):
        return (s1[0] + s2[0]) / 2 + 2 * PLANE_CLR + MINWIDTH

    def slot_growth(self, net, p, size=VIA_IN):
        """How much longer (mm, summed over L2, L3, L5) the longest chain of merged antipads through p gets when a
        via of `net` goes there: 0 when it touches no other antipad on any plane where it is foreign."""
        allv = [(n, q, VIA_IN if self._in_area(q) else VIA_OUT) for n, q in self.vias if abs(q[0] - p[0]) < 5 and abs(q[1] - p[1]) < 5] \
            + [(n, q, s) for n, q, s, k in self.mine if abs(q[0] - p[0]) < 5 and abs(q[1] - p[1]) < 5]
        near = [v for v in allv if math.dist(v[1], p) < 2.5]
        tot = 0.0
        pn0 = self.plane_nets(p)
        for lay in ("L2", "L3", "L5"):
            if pn0[lay] == net:
                continue
            fv = [v for v in allv if self.plane_nets(v[1])[lay] != v[0]]
            hit = [v for v in near if self.plane_nets(v[1])[lay] != v[0] and math.dist(v[1], p) < self.merge_dist(size, v[2])]
            if not hit:
                continue
            before = max(self._chain_span(fv, v) for v in hit)
            after = self._chain_span(fv + [(net, p, size)], (net, p, size))
            tot += max(0.0, after - max(before, SLOT_FREE))
        return tot

    def merges(self, net, p, size=VIA_IN):
        """Antipads the via at p would join on L2, L3, L5 (counted per layer): other vias closer than the merge
        distance that are foreign to the plane where this one is too."""
        n = 0
        pn0 = self.plane_nets(p)
        near = [(m, q, VIA_IN if self._in_area(q) else VIA_OUT) for m, q in self.vias if abs(q[0] - p[0]) < 1 and abs(q[1] - p[1]) < 1]             + [(m, q, s) for m, q, s, k in self.mine if abs(q[0] - p[0]) < 1 and abs(q[1] - p[1]) < 1]
        for lay in ("L2", "L3", "L5"):
            if pn0[lay] == net:
                continue
            n += sum(1 for m, q, s in near if self.plane_nets(q)[lay] != m and math.dist(q, p) < self.merge_dist(size, s))
        return n

    def _in_area(self, q):
        return any(R[0] <= q[0] <= R[2] and R[1] <= q[1] <= R[3] for R in self.areas.values())

    def _chain_span(self, vs, start):
        seen, todo = {id(start)}, [start]
        mem = [start]
        while todo:
            v = todo.pop()
            for o in vs:
                if id(o) not in seen and math.dist(o[1], v[1]) < self.merge_dist(o[2], v[2]):
                    seen.add(id(o)); todo.append(o); mem.append(o)
        if len(mem) == 1:
            return start[2][0] + 2 * PLANE_CLR
        return max(math.dist(a[1], c[1]) for a in mem for c in mem) + start[2][0] + 2 * PLANE_CLR

    # ---------------------------------------------------------------- balls
    def parity_ok(self, ref, net, s):
        """PARITY: on a package listed there, the vias of a net keep to one colour of the ball-gap checkerboard, so
        two of them are never orthogonal neighbours (0.65 mm: their antipads merge on the planes where they are
        foreign; diagonal ones, 0.92 mm, keep a web)."""
        want = PARITY.get((ref, net))
        if want is None:
            return True
        g = self.grids[ref]
        x0, y0 = min(p.pos[0] for p in g["pads"]), min(p.pos[1] for p in g["pads"])
        k, l = round((s[0] - x0) / g["pitch"] - 0.5), round((s[1] - y0) / g["pitch"] - 0.5)
        return (k + l) % 2 == want

    def ball_candidates(self, ball, edge=False, lane=False, parity=True):
        """[(site, width)] legal for a dog-bone via of the ball's net, in a fixed order. edge=True: instead the
        empty ball positions next to the ball on its own row or column (outside the array, or in the aisle of the
        SDRAM), joined by a straight dog-bone: a via there sits midway between two channel lines like a ball."""
        g = self.grids[ball.ref]
        out = []
        if edge:                # one pitch out, or up to EDGE_SLIDE farther along the same line (first legal per side)
            occ = {q for q in g["ij"].values()}
            i, j = g["ij"][ball.name]
            sides = []
            for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                if (i + di, j + dj) in occ:
                    continue
                sides.append([(r4(ball.pos[0] + di * (g["pitch"] + k * 0.025)), r4(ball.pos[1] + dj * (g["pitch"] + k * 0.025)))
                              for k in range(int(EDGE_SLIDE / 0.025) + 1)])
        else:
            sides = [[s] for s in g["sites"](ball) if (lane or ball.ref not in LATTICE or not self.outside(ball.ref, s))
                     and (not parity or self.parity_ok(ball.ref, ball.net, s))]
        for pts in sides:
            for s in pts:
                if s in self.sites_taken or any(math.dist(s, q) < 1e-6 for q in self.sites_taken):
                    continue
                if self.via_why(ball.net, s) is not None:
                    continue
                w = next((w for w in BONE_W if self.seg_why(ball.net, "L1", ball.pos, s, w) is None), None)
                if w is not None:
                    out.append((s, w))
                    break
        return out

    def signal_balls(self, ref):
        nets = set(self.power[ref])
        return [p for p in self.grids[ref]["pads"] if p.net and p.net not in nets and not p.net.startswith(("unconnected", "FMC_"))
                and self.ring(ref, p.name) >= 1]

    def signal_free(self, ball):
        """Ball-gap sites where a via of the signal ball's net could still stand."""
        g = self.grids[ball.ref]
        return [s for s in g["sites"](ball) if s not in self.sites_taken and self.via_why(ball.net, s) is None]

    def _need_all(self):
        """{signal ball: its free ball-gap sites} for every package (balls with none left out)."""
        out = {}
        for ref in self.grids:
            for sb in self.signal_balls(ref):
                f = self.signal_free(sb)
                if f:
                    out[sb.name] = f
        return out

    def cap_pads_at(self, net, s, size=VIA_IN):
        return [c for c in self.caps if c.net == net and c.name not in self.cap_conn and pad_dist(s, c) < size[0] / 2 - 1e-6]

    def stub_path(self, pad, s, widths):
        """Shortest legal L6 stub from the pad to the via at s: (outside length, points, width) or None.
        Straight from the pad centre, or with one 45 degree bend, or straight from a point inside the pad that is in
        line with s (0 / 45 / 90)."""
        c = (r4(pad.pos[0]), r4(pad.pos[1]))
        cands = []
        dx, dy = s[0] - c[0], s[1] - c[1]
        ax, ay = abs(dx), abs(dy)
        if ax < 1e-9 or ay < 1e-9 or abs(ax - ay) < 1e-9:
            cands.append([c, s])
        else:
            m = min(ax, ay)
            sx, sy = (dx > 0) - (dx < 0), (dy > 0) - (dy < 0)
            cands += [[c, (r4(c[0] + sx * m), r4(c[1] + sy * m)), s], [c, (r4(s[0] - sx * m), r4(s[1] - sy * m)), s]]
        x0, y0, x1, y1 = pad.box
        for w in widths:
            for q in ((c[0], s[1]), (s[0], c[1])):          # in line with s, inside the pad by w / 2
                if x0 + w / 2 <= q[0] <= x1 - w / 2 and y0 + w / 2 <= q[1] <= y1 - w / 2:
                    cands.append([(r4(q[0]), r4(q[1])), s])
            for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):     # on a 45 degree line through s, nearest to s
                lo, hi = 0.0, 1e9
                for v, d, a0, a1 in ((s[0], dx, x0 + w / 2, x1 - w / 2), (s[1], dy, y0 + w / 2, y1 - w / 2)):
                    t0, t1 = sorted(((a0 - v) / d, (a1 - v) / d))
                    lo, hi = max(lo, t0), min(hi, t1)
                if lo <= hi:
                    tt = math.ceil(lo * 10000 - 1e-6) / 10000
                    if tt <= hi:
                        cands.append([(r4(s[0] + dx * tt), r4(s[1] + dy * tt)), s])
        best = None
        for pts in cands:
            if any(math.dist(a, b) < self.pr.min_seg - 1e-9 for a, b in zip(pts, pts[1:])):
                continue
            if not self.angle_ok("L6", pts[-1], pts[-2]):
                continue
            out = self._outside(pts, pad)
            if out > STUB_MAX + 1e-9 or (best and out >= best[0] - 1e-9):
                continue
            for w in widths:
                if all(self.seg_why(pad.net, "L6", a, b, w) is None for a, b in zip(pts, pts[1:])):
                    best = (out, pts, w)
                    break
        return best

    @staticmethod
    def _outside(pts, pad):
        """Length of the polyline outside the pad's copper (sampled)."""
        L = 0.0
        for a, b in zip(pts, pts[1:]):
            n = max(1, int(math.dist(a, b) / 0.005))
            for k in range(n):
                t = (k + 0.5) / n
                q = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                if pad_dist(q, pad) > 1e-9:
                    L += math.dist(a, b) / n
        return round(L, 3)

    def score(self, ball, s, need):
        sc = 0.0
        sc += 1000 * len(self.cap_pads_at(ball.net, s))
        for c in self.caps:
            if c.net == ball.net and c.name not in self.cap_conn and pad_dist(s, c) <= STUB_MAX and pad_dist(s, c) >= VIA_IN[0] / 2:
                sc += 200 if self.stub_path(c, s, STUB_W) else 0
        harm0 = harm1 = 0
        for sb, free in need.items():
            if s in free:
                k = len(free) - 1
                harm0 += k == 0
                harm1 += k == 1
        sc -= 5000 * harm0 + 20 * harm1
        sc -= MERGE_COST * self.merges(ball.net, s) + SLOT_W * self.slot_growth(ball.net, s)
        if ball.ref in LATTICE and self.outside(ball.ref, s):
            sc -= 600                        # the lane round the package carries the outer rings' escapes on L1
        return sc

    def place_balls(self, ref, prefer=None):
        """Every supply and ground ball of `ref` gets its via. prefer = {ball number: site} fixes a ball's site."""
        nets = set(self.power[ref])
        balls = sorted((p for p in self.grids[ref]["pads"] if p.net in nets), key=lambda p: (p.pos[1], p.pos[0]))
        sig = self.signal_balls(ref)
        cand = {p.name: self.ball_candidates(p) for p in balls}
        need = {sb.name: self.signal_free(sb) for sb in sig}
        for sb in sig:
            if not need[sb.name]:
                self.log.append("note     %s %s (signal) has no free ball-gap site before this group" % (sb.name, sb.net))
        need = {k: v for k, v in need.items() if v}
        # nets without a plane first (their capacitor must reach the ball's own via), then the balls with the fewest sites
        order = sorted(balls, key=lambda p: (0 if (prefer or {}).get(p.num) else 1, 0 if p.net not in SUPPLY and p.net != "GND" else 1,
                                             min(len(cand[p.name]), 3), 0 if any(self.cap_pads_at(p.net, s) for s, _ in cand[p.name]) else 1,
                                             len(cand[p.name]), p.pos[1], p.pos[0]))
        def take(ball, opts, kind):
            fixed = (prefer or {}).get(ball.num)
            if fixed:
                opts = [o for o in opts if o[0] == fixed] or opts
            s, w = max(opts, key=lambda o: (self.score(ball, o[0], need), -o[0][1], -o[0][0]))
            self._bone(ball, s, w, new_via=True, kind=kind)
            for k in list(need):
                if any(math.dist(q, s) < 1.2 for q in need[k]):
                    sb = self.b.pads[k]
                    need[k] = [q for q in need[k] if q != s and self.via_why(sb.net, q) is None]

        def share_opts(ball, straight):
            """Neighbouring vias of the ball's net it can reach by a dog-bone: [(site, width)]; straight = only where
            the new dog-bone continues an existing one in line (180 degrees at the via)."""
            out = []
            for s in g["sites"](ball):
                if self.sites_taken.get(s) == ball.net and (not straight or self.angle_ok("L1", s, ball.pos)):
                    w = next((w for w in BONE_W if self.seg_why(ball.net, "L1", ball.pos, s, w) is None), None)
                    if w is not None:
                        out.append((s, w))
            return out

        def share(ball, s, w):
            other = [b for b, q in self.ball_via.items() if q == s]
            end = s
            if not self.angle_ok("L1", s, ball.pos):
                # the dog-bone stops inside the via 0.05 mm short of its centre on each axis: two tracks that meet
                # at the centre at 90 degrees break the corner_angle rule; this one is joined by the via's copper
                sx, sy = (ball.pos[0] > s[0]) - (ball.pos[0] < s[0]), (ball.pos[1] > s[1]) - (ball.pos[1] < s[1])
                end = (r4(s[0] + 0.05 * sx), r4(s[1] + 0.05 * sy))
                self.log.append("short    %s ends inside the shared via (%.3f, %.3f) of %s (they meet at 90 degrees)" % (ball.name, s[0], s[1], " ".join(other)))
            self._bone(ball, s, w, new_via=False, end=end)
            self.shared.append((ball.name, s, other))

        g = self.grids[ref]
        # 1. a ball-gap site of its own; a neighbour's via in line competes when every own site would lengthen a
        #    slot of merged antipads (SHARE_COST against SLOT_W per mm)
        for ball in order:
            opts = self.ball_candidates(ball)
            if not opts and not cand[ball.name] and not share_opts(ball, True):
                opts = self.ball_candidates(ball, parity=False)   # no site of its colour at all: the other one, early
            if not opts:
                continue
            sh = share_opts(ball, True)
            if sh:
                best = max(self.score(ball, s, need) for s, _ in opts)
                if best < -SHARE_COST and best > -4000:        # the own sites only cost plane slots (not a signal's last site)
                    share(ball, *sh[0])
                    continue
            take(ball, opts, "ball")
        for ball in balls:
            if ball.name in self.ball_via:
                continue
            # 2. no site of its own: a neighbouring ball's via of the same net, in line
            sh = share_opts(ball, True)
            if sh:
                share(ball, *sh[0])
                continue
            # 2b. a site of the other colour (PARITY), unless it joins antipads and a neighbour's via can be shared
            opts = self.ball_candidates(ball, parity=False)
            if opts and SHARE_90_FIRST and min(self.merges(ball.net, s) for s, _ in opts) > 0:
                sh = share_opts(ball, False)
                if sh:
                    share(ball, *sh[0])
                    continue
            if opts:
                take(ball, opts, "ball")
                continue
            # 3. a ball-gap point in the lane round the package (only now: it narrows the lane the outer rings use)
            opts = self.ball_candidates(ball, lane=True)
            if opts:
                take(ball, opts, "ball lane")
                continue
            # 4. an empty ball position beside it on its own row or column (outer ring, the void inside the MCU's
            #    rings, the SDRAM aisle): midway between two channel lines like a ball
            opts = self.ball_candidates(ball, edge=True)
            if opts:
                take(ball, opts, "ball edge")
                continue
            # 5. a neighbour's via at 90 degrees (the corner_angle rule reports it)
            sh = share_opts(ball, False)
            if sh:
                share(ball, *sh[0])
                continue
            # 6. a straight L1 link to the next ball of the same net in its row or column that has a via (its via is shared)
            for nb in (balls if ball.net != "GND" else ()):      # ground is not routed (user 2026-11-21)
                if nb.net != ball.net or nb.name not in self.ball_via or abs(math.dist(nb.pos, ball.pos) - g["pitch"]) > 1e-6:
                    continue
                w = next((w for w in BONE_W if self.seg_why(ball.net, "L1", ball.pos, nb.pos, w) is None), None)
                if w is None:
                    continue
                s = self.ball_via[nb.name]
                self._put_seg(ball.net, "L1", ball.pos, nb.pos, w)
                self.chains.setdefault(ball.net, []).append([("L1", [ball.name, nb.name], w)])
                self.ball_via[ball.name] = s
                self.shared.append((ball.name, s, [nb.name]))
                self.done.append({"kind": "shared by link", "pad": ball.name, "net": ball.net, "at": s, "w": w, "via_of": nb.name})
                self.log.append("%-9s %-9s %-11s L1 link to %s, its via (%.3f, %.3f), %.2f" % ("link", ball.name, ball.net, nb.name, s[0], s[1], w))
                break
            if ball.name in self.ball_via:
                continue
            why = []
            for s in g["sites"](ball):
                if self.sites_taken.get(s) == ball.net:
                    why.append("dog-bone to the %s via at (%.3f, %.3f) blocked" % (ball.net, s[0], s[1]))
                else:
                    why.append("(%.3f, %.3f): %s" % (s[0], s[1], self.via_why(ball.net, s) if s not in self.sites_taken else "taken by " + self.sites_taken[s]))
            self.nosite[ball.name] = "; ".join(why)
            self.log.append("NO SITE  %s %s: %s" % (ball.name, ball.net, "; ".join(why)))
        left = [k for k, v in need.items() if not v]
        for k in left:
            self.log.append("LOST     %s (%s): its last free ball-gap site went to this group" % (k, self.b.pads[k].net))

    def _bone(self, ball, s, w, new_via, kind="ball", end=None):
        end = end or s
        self._put_seg(ball.net, "L1", ball.pos, end, w)
        piece = [("L1", [ball.name, end], w)]
        if new_via:
            self._put_via(ball.net, s, VIA_IN, kind)
            piece.append(("via", s, VIA_IN))
        else:
            kind = "shared"
        self.chains.setdefault(ball.net, []).append(piece)
        self.ball_via[ball.name] = s
        self.done.append({"kind": kind, "pad": ball.name, "net": ball.net, "at": s, "w": w})
        self.log.append("%-9s %-9s %-11s via (%.3f, %.3f), dog-bone %.2f" % (kind, ball.name, ball.net, s[0], s[1], w))

    # ---------------------------------------------------------------- capacitor pads
    def connect_caps(self, widths_for=None):
        """Every cap pad: in-pad, stub to a via of its net, own via in the pad, or (ground) own via near it."""
        widths_for = widths_for or {}
        for c in sorted(self.caps, key=lambda p: p.name):
            if c.name in self.cap_conn:
                continue
            ws = widths_for.get(c.net, STUB_W)
            mine = [(n, q, sz) for n, q, sz, k in self.mine if n == c.net]
            inpad = [q for n, q, sz in mine if pad_dist(q, c) < sz[0] / 2 - 1e-6]
            if inpad:
                q = min(inpad, key=lambda q: math.dist(q, c.pos))
                self._conn(c, "in-pad", q, 0.0)
                continue
            reg = self.pour_of(c)
            if reg:
                self.cap_conn[c.name] = {"kind": "pour", "net": c.net, "region": reg, "balls": []}
                self.log.append("cap      %-9s %-11s pour           %s" % (c.name, c.net, reg))
                continue
            best = None
            for n, q, sz in sorted(mine, key=lambda m: math.dist(m[1], c.pos)):
                if pad_dist(q, c) > STUB_MAX:
                    continue
                st = self.stub_path(c, q, ws)
                if st and (best is None or st[0] < best[0][0]):
                    best = (st, q)
            if best:
                (out, pts, w), q = best
                for a, b in zip(pts, pts[1:]):
                    self._put_seg(c.net, "L6", a, b, w)
                start = c.name if tuple(pts[0]) == tuple(c.pos) else pts[0]
                self.chains.setdefault(c.net, []).append([("L6", [start] + pts[1:], w)])
                self._conn(c, "stub", q, out, w)
                continue
            # a via of its own: under the pad (in-pad), else for ground within GND_VIA_MAX
            own = self.own_via(c)
            if own:
                continue
            self.cap_conn[c.name] = {"kind": "NONE", "net": c.net}
            near = []
            for n, q, sz in sorted(mine, key=lambda m: math.dist(m[1], c.pos))[:2]:
                near.append("%s via (%.3f, %.3f) %.2f from the pad edge" % (n, q[0], q[1], pad_dist(q, c)))
            g = next((g for g in self.grids.values() if g["area"][0] <= c.pos[0] <= g["area"][2] and g["area"][1] <= c.pos[1] <= g["area"][3]), None)
            if g:
                x00, y00 = g["pads"][0].pos
                for i in range(-2, 3):
                    for j in range(-2, 3):
                        s = (r4(x00 + g["h"] + g["pitch"] * (round((c.pos[0] - x00 - g["h"]) / g["pitch"]) + i)),
                             r4(y00 + g["h"] + g["pitch"] * (round((c.pos[1] - y00 - g["h"]) / g["pitch"]) + j)))
                        if pad_dist(s, c) <= 0.45:
                            near.append("site (%.3f, %.3f) %.2f: %s" % (s[0], s[1], pad_dist(s, c), "taken by " + self.sites_taken[s] if s in self.sites_taken else self.via_why(c.net, s)))
            self.log.append("NO CONN  %s %s: no via of its net under it or within a %.1f mm stub, no own via site; %s" % (c.name, c.net, STUB_MAX, "; ".join(near)))

    def pour_of(self, c):
        """Name of a drawn region of the pad's net on its layer that overlaps the pad by at least the zone's minimum
        width each way (the pour joins it solidly), else None."""
        lay = sorted(c.layers)[0] if c.layers else None
        x0, y0, x1, y1 = c.box
        for name, n, l, poly in self.regions:
            if n != c.net or l != lay:
                continue
            m = MINWIDTH / 2
            pts = [(x, y) for x in (x0 + m, (x0 + x1) / 2, x1 - m) for y in (y0 + m, (y0 + y1) / 2, y1 - m)]
            for p in pts:
                if self._rdist(p, poly) <= -m and all(self._rdist(q, poly) <= 0 for q in ((p[0] - m, p[1] - m), (p[0] + m, p[1] + m), (p[0] - m, p[1] + m), (p[0] + m, p[1] - m))):
                    return name
        return None

    def own_via(self, c, size=None):
        if c.net != "GND" and c.net not in SUPPLY:          # no plane behind it (VCAP1 / VCAP2, VDDA_MCU): a via alone joins nothing
            return False
        inside = self._in_area(c.pos)
        size = size or (VIA_IN if inside else VIA_OUT)
        lim = GND_VIA_MAX if c.net == "GND" else STUB_MAX
        raw = []
        ref = next((ref for ref, g in self.grids.items() if g["area"][0] <= c.pos[0] <= g["area"][2] and g["area"][1] <= c.pos[1] <= g["area"][3]), None)
        if size == VIA_IN and ref in LATTICE:       # only ball-gap sites (the channels stay centred)
            g = self.grids[ref]
            x00, y00 = g["pads"][0].pos
            k0, l0 = round((c.pos[0] - x00 - g["h"]) / g["pitch"]), round((c.pos[1] - y00 - g["h"]) / g["pitch"])
            for i in range(-3, 4):
                for j in range(-3, 4):
                    raw.append((r4(x00 + g["h"] + g["pitch"] * (k0 + i)), r4(y00 + g["h"] + g["pitch"] * (l0 + j))))
        else:
            step = 0.025
            n = int(1.4 / step)
            x0g, y0g = round(c.pos[0] / step) * step, round(c.pos[1] / step) * step
            raw = [(r4(x0g + i * step), r4(y0g + j * step)) for i in range(-n, n + 1) for j in range(-n, n + 1)]
        inpad_ok = size == VIA_IN                   # via-in-pad is approved only under the BGAs (rule areas)
        pts = sorted((pad_dist(p, c), math.dist(p, c.pos), p) for p in raw if pad_dist(p, c) <= lim
                     and (inpad_ok or pad_dist(p, c) >= size[0] / 2 + 0.001))
        need = self._need_all()
        scored = []
        for e, d, p in pts:
            if p in self.sites_taken:
                continue
            if self.via_why(c.net, p, size) is not None:
                continue
            colour = 1 if ref is not None and size == VIA_IN and not self.parity_ok(ref, c.net, p) else 0
            harm = sum(1 for free in need.values() if p in free and len(free) <= 1)
            lane = 1 if ref in LATTICE and self.outside(ref, p) else 0     # the lane round the MCU: last but one
            scored.append((harm, lane, colour, self.merges(c.net, p, size), 0 if e < size[0] / 2 - 1e-6 else 1, round(self.slot_growth(c.net, p, size), 3), e, d, p))
        scored.sort()
        for harm, _, _, _, _, _, e, d, p in scored:
            if e < size[0] / 2 - 1e-6:                     # in the pad
                self._put_via(c.net, p, size, "own")
                self.extras.append((c.net, p))
                self._conn(c, "own in-pad", p, 0.0)
                return True
            st = self.stub_path(c, p, STUB_W)
            if st:
                out, path, w = st
                for a, b in zip(path, path[1:]):
                    self._put_seg(c.net, "L6", a, b, w)
                self._put_via(c.net, p, size, "own")
                start = c.name if tuple(path[0]) == tuple(c.pos) else path[0]
                self.chains.setdefault(c.net, []).append([("L6", [start] + path[1:], w), ("via", p, size)])
                self._conn(c, "own via, stub", p, out, w)
                return True
        return False

    def _conn(self, c, kind, q, out, w=None):
        owner = [b for b, s in self.ball_via.items() if s == (r4(q[0]), r4(q[1]))]
        self.cap_conn[c.name] = {"kind": kind, "net": c.net, "via": q, "stub": out, "w": w, "balls": owner,
                                 "edge": round(pad_dist(q, c), 3)}
        self.log.append("cap      %-9s %-11s %-14s via (%.3f, %.3f)%s%s" % (c.name, c.net, kind, q[0], q[1],
                        ", stub %.3f outside the pad, w %.2f" % (out, w) if w else "", ", ball via of " + " ".join(owner) if owner else ""))

    # ---------------------------------------------------------------- odd jobs
    def tie_via_out(self, padname, net=None, lmax=1.6, plane=True, w=0.3, near=None):
        """A 0.45 / 0.2 via beside a pad outside the rule areas, stub on the pad's layer (the bead's supply side)."""
        pad = self.b.pads[padname]
        net = net or pad.net
        lay = sorted(pad.layers)[0] if pad.layers else "L1"
        c = (r4(pad.pos[0]), r4(pad.pos[1]))
        best, why0 = None, None
        step = 0.025
        n = int(lmax / step)
        for dx, dy in ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)):
            f = math.sqrt(2) if dx and dy else 1.0
            for k in range(1, n + 1):
                L = k * step * f
                if L > lmax or (best and L >= best[0]):
                    break
                p = (r4(c[0] + dx * k * step), r4(c[1] + dy * k * step))
                if pad_dist(p, pad) < VIA_OUT[0] / 2 + 0.001:
                    continue
                why = self.via_why(net, p, VIA_OUT, pads_ok=(padname,))
                if why is None and plane and net in SUPPLY and self.l3_net(p, VIA_OUT[0] / 2 + PLANE_MARGIN) != net:
                    why = "not in the L3 block"
                if why is None:
                    why = self.seg_why(net, lay, c, p, w)
                if why is None:
                    best = (L, p)
                    break
                why0 = why0 or "%s (%.3f, %.3f)" % (why, p[0], p[1])
        if best is None:
            self.log.append("NO SITE  %s %s: %s" % (padname, net, why0))
            return None
        L, p = best
        self._put_seg(net, lay, c, p, w)
        self._put_via(net, p, VIA_OUT, "tie")
        self.chains.setdefault(net, []).append([(lay, [padname if c == tuple(pad.pos) else c, p], w), ("via", p, VIA_OUT)])
        self.cap_conn[padname] = {"kind": "own via, stub", "net": net, "via": p, "stub": round(L - pad_dist(c, pad), 3), "w": w, "balls": [],
                                  "edge": round(pad_dist(p, pad), 3)}
        self.log.append("tie      %-9s %-11s via (%.3f, %.3f) %.2f mm from the pad centre" % (padname, net, p[0], p[1], L))
        return p
