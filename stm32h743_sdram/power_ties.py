"""Site search for the power group (routes_power.py): ground and supply vias beside pads, short ties of pads to
their pour, feed vias inside pours, and two-via hops over the bottom layer. Deterministic: the same board, sketch
and obstacle board give the same copper, so the group builds the same on the real board and on the line-order
sketch copy.

What a site has to keep (checked here; DRC in the build stays the authority):
  - the busroute scene: clearance and hole rules to every pad, to the tracks and vias of the SDRAM sketch
    (read from the sketch copy, nets of its `sdram` group) and to the copper this planner placed before
  - via outside both BGA rule areas (nothing new goes inside them), copper-to-edge clearance, no via on an SMD
    pad (except ALLOW, the approved exposed-pad vias), 0.5 mm centre to centre to vias and plated holes of its
    own net (hole to hole), 0.9 mm to plated holes of the connectors (hole to hole 0.45)
  - outer layers: a via or a track of net N stays `REGION_MARGIN` clear of every drawn region of another net on
    that layer (copper.sketch), so no local pour is cut by foreign copper
  - power plane (`PWR_PLANE`, L5 since 2026-11-23; it was L3): a via that must reach the plane lands inside the
    block of its net with `PLANE_MARGIN` to spare; +3V3 is the rest of the plane (outside every drawn block of that
    layer grown by the sketch's gap). L2 is the ground plane; every through via reaches it
Ties are straight from the pad centre (0/45/90) or have one 45 degree bend; the shortest legal one is taken,
ties that point at the part's own centre cost a little more (vias go beside the part, not under it).
"""
import math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import cu_sketch                                            # noqa: E402
from busroute.board import Board                            # noqa: E402
from busroute.checks import Scene                           # noqa: E402
from busroute.geom import in_poly, seg_poly_dist, seg_rect_dist, seg_dist, pt_seg, R2  # noqa: E402

DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
STEP = 0.025                 # search step along a direction (keeps the 0.1 um grid from a pad centre on it)
REGION_MARGIN = 0.1          # foreign copper to a drawn region of another net on an outer layer, beyond its own size
PWR_PLANE = "L5"            # the layer of the power blocks in copper.sketch (signal / GND / signal / signal / power / signal)
PLANE_MARGIN = 0.15          # a via that must hit its power block: inside it by radius + this
OWN_VIA = 0.5                # centre distance between two vias of one net (hole to hole 0.254 + 0.2)
PTH_VIA = 0.75               # via centre to a plated hole of another part (hole to hole 0.45 + radii)


def r4(v):
    return round(v * 10000) / 10000


def pad_dist(p, pad):
    """Distance from p to the pad's copper (0 inside); rectangular pads by their box, which errs on the near side
    at rounded corners."""
    if pad.poly is None:
        return max(0.0, math.dist(p, pad.pos) - pad.r)
    x0, y0, x1, y1 = pad.box
    return math.hypot(max(x0 - p[0], 0.0, p[0] - x1), max(y0 - p[1], 0.0, p[1] - y1))


class Planner:
    def __init__(self, board, profile, sketch_path, obstacle_board=None, obstacle_nets=(), via=(0.45, 0.2), allow=(), protect=()):
        self.b, self.pr, self.via = board, profile, tuple(via)
        self.allow = set(allow)
        self.protect = list(protect)                          # (net, (x0, y0, x1, y1)): narrow plane strips no via of another net may cut
        self.sc = Scene(board, profile, skip_nets=set(board.nets))           # pads only
        if obstacle_board:
            ob = Board(obstacle_board, board.origin)
            keep = set(obstacle_nets)
            for n, lay, a, c, w, _ in ob.tracks:
                if n in keep:
                    self.sc.add(self.sc.seg(n, lay, a, c, w, False))
            for n, p, d, h in ob.vias:
                if n in keep:
                    self.sc.add(self.sc.via(n, p, d, h, False))
        self.areas = board.rule_areas(profile.area_names)
        sk = cu_sketch.load_sketch(sketch_path, len(board.cu))
        self.gap = sk.p["gap"] / 1e6
        ox, oy = sk.origin[0] / 1e6 - board.origin[0], sk.origin[1] / 1e6 - board.origin[1]
        self.regions = []                                    # (name, net, layer "L1", poly in local mm)
        for r in sk.regions:
            if not r.whole:
                self.regions.append((r.name, r.net, "L%d" % r.layer, [(x / 1e6 + ox, y / 1e6 + oy) for x, y in r.pts]))
        self.pwr_whole = next((r.net for r in sk.regions if r.whole and "L%d" % r.layer == PWR_PLANE), None)
        xs = [p[0] for e in board.edges for p in e]
        ys = [p[1] for e in board.edges for p in e]
        self.box = (min(xs), min(ys), max(xs), max(ys))
        self.board_poly = None
        self.own_vias = []                                   # (net, p) placed here
        self.th = [(p.net, p.pos, p.hole) for p in board.all_pads() if p.hole > 0]
        self.chains, self.extras, self.log, self.done = {}, [], [], []
        self._pcache = {}
        self.own_segs = []                                   # (net, layer, a, c) placed here
        self.rbox = [(min(q[0] for q in poly), min(q[1] for q in poly), max(q[0] for q in poly), max(q[1] for q in poly)) for _, _, _, poly in self.regions]

    # ---------------------------------------------------------------- regions
    def region(self, name):
        return next(r for r in self.regions if r[0] == name)

    def _rdist(self, p, poly):
        """Signed distance from p to the polygon outline: negative inside."""
        d = min(pt_seg(p, a, c)[0] for a, c in zip(poly, poly[1:] + poly[:1]))
        return -d if in_poly(p, poly) else d

    def pwr_net(self, p, margin):
        """The power-plane block net at p when p is inside it by `margin`; None in a gap or near an edge of one."""
        for name, net, lay, poly in self.regions:
            if lay == PWR_PLANE:
                d = self._rdist(p, poly)
                if d <= -margin:
                    return net
                if d < self.gap + margin:
                    return None
        return self.pwr_whole

    def inside(self, net, layer, p, margin):
        return any(n == net and lay == layer and self._rdist(p, poly) <= -margin for _, n, lay, poly in self.regions)

    # ---------------------------------------------------------------- legality
    def via_why(self, net, p, plane=False, outer=(), plane_net=None):
        d, h = self.via
        r = d / 2
        for R in self.areas.values():
            if math.hypot(max(R[0] - p[0], 0.0, p[0] - R[2]), max(R[1] - p[1], 0.0, p[1] - R[3])) < r + 0.01:
                return "rule area"
        x0, y0, x1, y1 = self.box
        if not (x0 + r + self.pr.edge_clr <= p[0] <= x1 - r - self.pr.edge_clr and y0 + r + self.pr.edge_clr <= p[1] <= y1 - r - self.pr.edge_clr):
            return "board edge"
        if min(p[0] - x0, x1 - p[0]) < 3 and min(p[1] - y0, y1 - p[1]) < 3:
            if min(pt_seg(p, a, c)[0] for a, c in self.b.edges) < r + self.pr.edge_clr:
                return "board edge"
        for pn, R in self.protect:
            if pn != net and math.hypot(max(R[0] - p[0], 0.0, p[0] - R[2]), max(R[1] - p[1], 0.0, p[1] - R[3])) < r + self.pr.plane_clr:
                return "cuts the narrow %s strip" % pn
        for n, q in self.own_vias:
            if math.dist(p, q) < (OWN_VIA if n == net else d + 0.127):
                return "via of %s at (%.3f, %.3f)" % (n, q[0], q[1])
        for n, q, hr in self.th:
            if math.dist(p, q) < hr + h / 2 + (0.45 if n != net else 0.254):
                return "plated hole at (%.3f, %.3f)" % q
        it = self.sc.via(net, p, d, h)
        for o in self.sc.near(it, 0.1):
            if o.pad is not None and o.pad.smd:
                dd = math.dist(p, o.a) - o.r if o.kind == "round" else seg_poly_dist(p, p, o.poly)[0]
                if o.pad.name in self.allow:                  # approved via-in-pad: wholly on the pad or clear of it
                    x0, y0, x1, y1 = o.pad.box
                    if dd < r + 0.001 and not (x0 + r <= p[0] <= x1 - r and y0 + r <= p[1] <= y1 - r):
                        return "half on pad %s" % o.pad.name
                elif dd < r + 0.001:
                    return "on pad %s" % o.pad.name
        for (name, n, lay, poly), bx in zip(self.regions, self.rbox):
            if (lay in ("L1", "L%d" % len(self.b.cu)) and n != net and bx[0] - 1 < p[0] < bx[2] + 1 and bx[1] - 1 < p[1] < bx[3] + 1
                    and self._rdist(p, poly) < r + REGION_MARGIN):
                return "in region %s" % name
        why = self.sc.conflict([it])
        if why:
            return why
        if plane and self.pwr_net(p, r + PLANE_MARGIN) != (plane_net or net):
            return "not inside the %s block of %s" % (PWR_PLANE, plane_net or net)
        for lay in outer:
            if not self.inside(net, lay, p, r + 0.05):
                return "not inside a %s region of %s" % (lay, net)
        return None

    def seg_why(self, net, layer, a, c, w):
        if math.dist(a, c) < self.pr.min_seg - 1e-9:
            return "segment shorter than %.2f" % self.pr.min_seg
        for R in self.areas.values():
            if seg_rect_dist(a, c, R) < w / 2 + 0.01:
                return "rule area"
        for n, lay, p, q in self.own_segs:                  # no crossing of our own ties of the net (acute junctions)
            if n == net and lay == layer and seg_dist(a, c, p, q)[0] < 1e-6 and not {a, c} & {p, q}:
                return "crosses a tie of %s" % net
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

    # ---------------------------------------------------------------- placing
    def _put_via(self, net, p):
        d, h = self.via
        self.sc.add(self.sc.via(net, p, d, h, False))
        self.own_vias.append((net, p))

    def _put_seg(self, net, layer, a, c, w):
        self.sc.add(self.sc.seg(net, layer, a, c, w, False))
        self.own_segs.append((net, layer, a, c))

    def _paths(self, c, lmax, bend=True):
        """Candidate polylines from c: straight in 8 directions, then with one 45 degree bend; by length (a generator)."""
        key = (lmax, bend)
        if key not in self._pcache:
            self._pcache[key] = self._offsets(lmax, bend)
        for L, d, pts in self._pcache[key]:
            yield L, d, [c] + [(r4(c[0] + q[0]), r4(c[1] + q[1])) for q in pts]

    def _offsets(self, lmax, bend):
        c = (0.0, 0.0)
        out = []
        n = int(lmax / STEP)
        for d in DIRS:
            f = R2 if d[0] and d[1] else 1.0
            for k in range(1, n + 1):
                if k * STEP * f > lmax:
                    break
                out.append((k * STEP * f, d, [(r4(c[0] + d[0] * k * STEP), r4(c[1] + d[1] * k * STEP))]))
        if bend:
            for i, d in enumerate(DIRS):
                f1 = R2 if d[0] and d[1] else 1.0
                for e in (DIRS[(i + 1) % 8], DIRS[(i - 1) % 8]):
                    f2 = R2 if e[0] and e[1] else 1.0
                    for k in range(4, n):
                        a = k * STEP * f1
                        if a > lmax:
                            break
                        m = (r4(c[0] + d[0] * k * STEP), r4(c[1] + d[1] * k * STEP))
                        for j in range(4, n):
                            b = j * STEP * f2
                            if a + b > lmax:
                                break
                            out.append((a + b + 0.05, d, [m, (r4(m[0] + e[0] * j * STEP), r4(m[1] + e[1] * j * STEP))]))
        out.sort(key=lambda t: t[0])
        return out

    def pad(self, ref):
        """A Pad from "REF.NUM" or a Pad (pads with a shared number, e.g. shield pads, exist only as objects)."""
        return self.b.pads[ref] if isinstance(ref, str) else ref

    def start(self, pad):
        """First point of a chain: the pad's name when that names this pad and its centre is on the 0.1 um grid,
        else the centre snapped to that grid (at most 0.05 um away)."""
        c = self.centre(pad)
        return pad.name if self.b.pads.get(pad.name) is pad and c == tuple(pad.pos) else c

    @staticmethod
    def centre(pad):
        return (r4(pad.pos[0]), r4(pad.pos[1]))

    @staticmethod
    def octo(A, B):
        """Octilinear paths from A to B: straight, or the two with one 45 degree bend."""
        dx, dy = B[0] - A[0], B[1] - A[1]
        ax, ay = abs(dx), abs(dy)
        if ax < 1e-9 or ay < 1e-9 or abs(ax - ay) < 1e-9:
            return [[A, B]]
        s = min(ax, ay)
        sx, sy = (dx > 0) - (dx < 0), (dy > 0) - (dy < 0)
        return [[A, (r4(A[0] + sx * s), r4(A[1] + sy * s)), B], [A, (r4(B[0] - sx * s), r4(B[1] - sy * s)), B]]

    def _width(self, pad, w):
        if w:
            return w
        bx = pad.box
        return min(self.pr.width(pad.net), round(min(bx[2] - bx[0], bx[3] - bx[1]) * 0.8, 3))

    def _layer(self, pad):
        if pad.layers is None:
            return "L1"
        return sorted(pad.layers)[0]

    def tie_via(self, padname, net=None, plane=False, outer=(), lmax=1.6, w=None, pad_edge_max=None, plane_net=None, toward=None):
        """A via of the pad's net beside the pad, joined by a stub on the pad's layer. -> via point or None."""
        pad = self.pad(padname)
        padname = pad.name
        net = net or pad.net
        lay, w = self._layer(pad), self._width(pad, w)
        ctr = self.b.fp[pad.ref]["pos"]
        best, why0 = None, None
        for L, d, pts in self._paths(self.centre(pad), lmax):
            if best is not None and L >= best[0]:
                break
            p = pts[-1]
            e = pad_dist(p, pad)
            if e < self.via[0] / 2 + 0.001 or (pad_edge_max is not None and e > pad_edge_max + 1e-9):
                continue
            away = (p[0] - pad.pos[0]) * (pad.pos[0] - ctr[0]) + (p[1] - pad.pos[1]) * (pad.pos[1] - ctr[1])
            cost = L + (0.3 if away < -1e-6 and len(self.b.fp[pad.ref]["pads"]) <= 3 else 0.0)
            if toward is not None:
                cost += 0.2 * math.dist(p, toward)
            if best is not None and cost >= best[0]:
                continue
            why = self.via_why(net, p, plane, outer, plane_net)
            if why is None:
                for a, c in zip(pts, pts[1:]):
                    why = self.seg_why(net, lay, a, c, w)
                    if why:
                        break
            if why is None:
                best = (cost, pts)
            elif why0 is None:
                why0 = "%s (%.3f, %.3f)" % (why, p[0], p[1])
        if best is None:
            self.log.append("NO SITE  %s %s: nearest refusal %s" % (padname, net, why0))
            return None
        pts = best[1]
        for a, c in zip(pts, pts[1:]):
            self._put_seg(net, lay, a, c, w)
        self._put_via(net, pts[-1])
        self.chains.setdefault(net, []).append([(lay, [self.start(pad)] + pts[1:], w), ("via", pts[-1], self.via)])
        e = pad_dist(pts[-1], pad)
        self.done.append({"kind": "via", "pad": padname, "net": net, "at": pts[-1], "stub": round(best[0], 3), "edge": round(e, 3)})
        self.log.append("via      %-9s %-11s at (%.3f, %.3f), stub %.2f mm, pad edge to via centre %.2f" % (padname, net, pts[-1][0], pts[-1][1], best[0], e))
        return pts[-1]

    def tie_pour(self, padname, region=None, lmax=3.0, w=None):
        """A track from the pad into a drawn region of its net on the pad's layer. -> end point or None."""
        pad = self.pad(padname)
        padname, net = pad.name, pad.net
        lay, w = self._layer(pad), self._width(pad, w)
        regs = [r for r in self.regions if r[1] == net and r[2] == lay and (region is None or r[0] == region)]
        why0 = None
        for L, d, pts in self._paths(self.centre(pad), lmax):
            p = pts[-1]
            if not any(self._rdist(p, poly) <= -(w / 2 + 0.15) for _, _, _, poly in regs):
                continue
            why = next((y for y in (self.seg_why(net, lay, a, c, w) for a, c in zip(pts, pts[1:])) if y), None)
            if why is None:
                for a, c in zip(pts, pts[1:]):
                    self._put_seg(net, lay, a, c, w)
                self.chains.setdefault(net, []).append([(lay, [self.start(pad)] + pts[1:], w)])
                self.done.append({"kind": "tie", "pad": padname, "net": net, "at": p, "len": round(L, 3)})
                self.log.append("tie      %-9s %-11s into %s at (%.3f, %.3f), %.2f mm" % (padname, net, " ".join(r[0] for r in regs), p[0], p[1], L))
                return p
            if why0 is None:
                why0 = "%s (%.3f, %.3f)" % (why, p[0], p[1])
        self.log.append("NO TIE   %s %s: nearest refusal %s" % (padname, net, why0))
        return None

    def tie_pad(self, padname, target, w=None):
        """A track from a pad to another pad of its net on the same layer: straight or one 45 degree bend, else (pads
        in line) a detour to one side with two 45 degree bends each way."""
        pad, tp = self.pad(padname), self.pad(target)
        lay, w = self._layer(pad), self._width(pad, w)
        why0 = None
        A, B = self.centre(pad), self.centre(tp)
        cands = self.octo(A, B)
        if abs(A[0] - B[0]) < 1e-9 or abs(A[1] - B[1]) < 1e-9:
            u = ((B[0] > A[0]) - (B[0] < A[0]), (B[1] > A[1]) - (B[1] < A[1]))
            for k in range(4, 41):
                for side in (1, -1):
                    o = (-u[1] * side * k * STEP, u[0] * side * k * STEP)
                    p1 = (r4(A[0] + o[0] + u[0] * k * STEP), r4(A[1] + o[1] + u[1] * k * STEP))
                    p2 = (r4(B[0] + o[0] - u[0] * k * STEP), r4(B[1] + o[1] - u[1] * k * STEP))
                    if (p2[0] - p1[0]) * u[0] + (p2[1] - p1[1]) * u[1] > 0.1:
                        cands.append([A, p1, p2, B])
        for pts in cands:
            why = next((y for y in (self.seg_why(pad.net, lay, a, c, w) for a, c in zip(pts, pts[1:])) if y), None)
            if why is None:
                for a, c in zip(pts, pts[1:]):
                    self._put_seg(pad.net, lay, a, c, w)
                self.chains.setdefault(pad.net, []).append([(lay, [self.start(pad)] + pts[1:-1] + [self.start(tp)], w)])
                L = sum(math.dist(a, c) for a, c in zip(pts, pts[1:]))
                self.done.append({"kind": "tie", "pad": pad.name, "net": pad.net, "at": tp.pos, "len": round(L, 3)})
                self.log.append("tie      %-9s %-11s to pad %s, %.2f mm" % (pad.name, pad.net, tp.name, L))
                return True
            why0 = why0 or why
        self.log.append("NO TIE   %s %s to pad %s: %s" % (pad.name, pad.net, tp.name, why0))
        return False

    def feed(self, net, near, count, outer=(), plane=False, plane_net=None, spacing=0.8, radius=3.0, label=""):
        """`count` vias of `net` inside its regions on the `outer` layers (and its power-plane block with plane), nearest to
        `near` (a pad name or a point). No track: the pours join them. -> list of points."""
        c = self.b.pads[near].pos if isinstance(near, str) else near
        cand = []
        n = int(radius / 0.05)
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                p = (r4(c[0] + i * 0.05), r4(c[1] + j * 0.05))
                dd = math.dist(p, c)
                if dd <= radius:
                    cand.append((dd, p))
        cand.sort()
        got, why0 = [], None
        for dd, p in cand:
            if len(got) == count:
                break
            if any(math.dist(p, q) < spacing for q in got):
                continue
            why = self.via_why(net, p, plane, outer, plane_net)
            if why is None:
                got.append(p)
                self._put_via(net, p)
                self.extras.append((net, p))
            elif why0 is None:
                why0 = why
        for p in got:
            self.done.append({"kind": "feed", "pad": label or str(near), "net": net, "at": p})
        self.log.append("feed     %-11s %d/%d near %s%s: %s%s" % (net, len(got), count, near if isinstance(near, str) else "(%.2f, %.2f)" % near,
                                                             " " + label if label else "", " ".join("(%.3f, %.3f)" % q for q in got),
                                                             "" if len(got) == count else "  SHORT: " + str(why0)))
        return got

    def hop(self, padname, outer_to, lay_mid, lmax_a=1.5, lmax_mid=12.0, w=None, near_to=None):
        """Pad -> stub -> via A -> track on lay_mid -> via B inside the `outer_to` region (name) of the pad's net.
        lmax_a=0: no via A, the track on lay_mid (the pad's own layer) starts at the pad."""
        pad = self.pad(padname)
        padname, net = pad.name, pad.net
        lay, w = self._layer(pad), self._width(pad, w)
        rname, rnet, rlay, rpoly = self.region(outer_to)
        cb = []                                                 # via B: inside the target region, nearest first
        bx = [min(q[0] for q in rpoly), min(q[1] for q in rpoly), max(q[0] for q in rpoly), max(q[1] for q in rpoly)]
        for i in range(int((bx[2] - bx[0]) / 0.05) + 1):
            for j in range(int((bx[3] - bx[1]) / 0.05) + 1):
                p = (r4(bx[0] + i * 0.05), r4(bx[1] + j * 0.05))
                if self._rdist(p, rpoly) <= -(self.via[0] / 2 + 0.1):
                    cb.append((math.dist(p, near_to or pad.pos), p))
        cb.sort()
        cb = [p for _, p in cb if self.via_why(net, p) is None][:60]
        ca = [] if lmax_a else [(0.0, [self.centre(pad)])]                # via A: legal stub sites by the pad
        for L, d, pts in (self._paths(self.centre(pad), lmax_a, bend=False) if lmax_a else []):
            if len(ca) >= 24:
                break
            if self.via_why(net, pts[-1]) is None and all(self.seg_why(net, lay, a, c, w) is None for a, c in zip(pts, pts[1:])):
                ca.append((L, pts))
        best = None
        wm = self.pr.width(net) if lmax_a else w
        for La, pa in ca:
            A = pa[-1]
            for B in cb:
                if math.dist(A, B) < 0.6:
                    continue
                for path in self.octo(A, B):
                    if len(path) == 3 and (math.dist(path[0], path[1]) < 0.1 or math.dist(path[1], path[2]) < 0.1):
                        continue
                    L = La + sum(math.dist(a, c) for a, c in zip(path, path[1:]))
                    if L > lmax_mid or (best and L >= best[0]):
                        continue
                    if all(self.seg_why(net, lay_mid, a, c, wm) is None for a, c in zip(path, path[1:])):
                        best = (L, pa, path)
        if best is None:
            self.log.append("NO HOP   %s %s to %s over %s (%d via A sites, %d via B sites)" % (padname, net, outer_to, lay_mid, len(ca), len(cb)))
            return None
        L, pa, path = best
        if lmax_a:
            for a, c in zip(pa, pa[1:]):
                self._put_seg(net, lay, a, c, w)
            self._put_via(net, pa[-1])
            pieces = [(lay, [self.start(pad)] + pa[1:], w), ("via", pa[-1], self.via), (lay_mid, path, wm)]
        else:
            pieces = [(lay_mid, [self.start(pad)] + path[1:], wm)]
        for a, c in zip(path, path[1:]):
            self._put_seg(net, lay_mid, a, c, wm)
        self._put_via(net, path[-1])
        self.chains.setdefault(net, []).append(pieces + [("via", path[-1], self.via)])
        self.done.append({"kind": "hop", "pad": padname, "net": net, "at": path[-1], "len": round(L, 3)})
        self.log.append("hop      %-9s %-11s %s - %s - via (%.3f, %.3f) in %s, %.2f mm" % (
            padname, net, "via (%.3f, %.3f)" % tuple(pa[-1]) if lmax_a else "pad", lay_mid, path[-1][0], path[-1][1], outer_to, L))
        return path[-1]

    def fixed(self, padname, pieces):
        """A chain given in full (routes format: ("L1", [pad or points], width?) and ("via", (x, y))), checked like
        a searched one (via_why / seg_why for every via and segment) and placed only when all of it is legal.
        For the few ties whose searched site would block a later group's route. -> True / False."""
        pad = self.pad(padname)
        net = pad.net
        out, segs, vias, why = [], [], [], None
        for pc in pieces:
            if pc[0] == "via":
                p = (r4(pc[1][0]), r4(pc[1][1]))
                why = why or (lambda w: w and "via (%.3f, %.3f): %s" % (p[0], p[1], w))(self.via_why(net, p))
                vias.append(p)
                out.append(("via", p, self.via))
                continue
            lay, pts = pc[0], [self.centre(self.pad(q)) if isinstance(q, str) else (r4(q[0]), r4(q[1])) for q in pc[1]]
            w = pc[2] if len(pc) > 2 else (self._width(pad, None) if isinstance(pc[1][0], str) else self.pr.width(net))
            for a, c in zip(pts, pts[1:]):
                why = why or (lambda y: y and "%s (%.3f, %.3f)-(%.3f, %.3f): %s" % (lay, a[0], a[1], c[0], c[1], y))(self.seg_why(net, lay, a, c, w))
                segs.append((lay, a, c, w))
            out.append((lay, [self.start(pad) if isinstance(pc[1][0], str) and k == 0 else q for k, q in enumerate(pts)], w))
        if why:
            self.log.append("NO FIXED %s %s: %s" % (padname, net, why))
            return False
        for lay, a, c, w in segs:
            self._put_seg(net, lay, a, c, w)
        for p in vias:
            self._put_via(net, p)
        self.chains.setdefault(net, []).append(out)
        L = sum(math.dist(a, c) for _, a, c, _ in segs)
        self.done.append({"kind": "fixed", "pad": padname, "net": net, "at": vias[-1] if vias else None, "len": round(L, 3)})
        self.log.append("fixed    %-9s %-11s %d vias, %.2f mm" % (padname, net, len(vias), L))
        return True

    def via_in_pad(self, padname, nx, ny, pitch):
        """An nx x ny array of vias on an approved exposed pad (ALLOW), centred on it."""
        pad = self.b.pads[padname]
        pts = []
        for i in range(nx):
            for j in range(ny):
                p = (r4(pad.pos[0] + (i - (nx - 1) / 2) * pitch), r4(pad.pos[1] + (j - (ny - 1) / 2) * pitch))
                why = self.via_why(pad.net, p)
                if why and not why.startswith("on pad %s" % padname):
                    self.log.append("NO SITE  %s array (%.3f, %.3f): %s" % (padname, p[0], p[1], why))
                    continue
                self._put_via(pad.net, p)
                self.extras.append((pad.net, p))
                pts.append(p)
                self.done.append({"kind": "in pad", "pad": padname, "net": pad.net, "at": p})
        self.log.append("in pad   %-9s %-11s %d vias, pitch %.2f" % (padname, pad.net, len(pts), pitch))
        return pts
