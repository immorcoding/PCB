"""PROTOTYPE (throwaway, issue 21): bundle routing. A generator IN FRONT of the builder: it writes ROUTES
(and TUNING entries) in the format of lib/README.md, nothing else. board.py / serp.py are not touched.

Why: typing every net as its own coordinate list makes nothing parallel. Here a bus is written as
bundles: an ordered list of nets (lanes), a centre path of 0/45/90 legs, a pitch per leg, a layer.

    bus = Bus(SWAP)                                   # knows every pad of both chips
    bus.keep(hand_routes)                             # hand-written nets: passed through, used as obstacles
    b = Bundle("trunk", nets, "L1", path=[(x, y), ...], pitch=0.23, gaps={2: [1.2, 0.8, ...]}, anchor="D14")
    b.widen(leg, s0, s1, after="D14", by=0.6)         # lanes right of D14 step aside between s0 and s1
    s = b.slot("D14", leg, s0, length, side="R")      # a serpentine site on a straight of that lane
    bus.add(b, start={net: terminal}, end={net: terminal})
    ROUTES = bus.routes()                             # {net: pieces}; raises with every problem listed
    s.fill(add=2.0)                                   # one equal-height block; TUNING = bus.tuning()
    print(bus.report())                               # length per lane before any serpentine

Geometry is done on integers (0.1 um). Every track is a piece of a LINE in one of four normal forms
(x = c, y = c, x - y = c, x + y = c) and every vertex is the meeting point of two consecutive lines, so
segments are exactly 0/45/90, corners are exactly 45 degrees and nested corners come out by themselves
(outer lanes longer). On a diagonal leg a gap is rounded UP to the grid (at most 0.07 um wider).

Lane order: index 0 is the LEFT lane seen along the direction of travel on the picture (y down): the
north lane of a bundle that runs east, the east lane of one that runs south. "R" / side=+1 means towards
higher lane numbers. Stations s are mm along a leg from the leg's first path point (may be negative).
"""
import math
import balls, board
from common import (AREAS, MCU, RAM, FOOTPRINT, W_IN, W_OUT, CLR_IN, CLR_OUT, SERP, VIA_IN, VIA_OUT, REF, SIGNAL_LAYERS,
                    full, short, area_of, octile)

G = 10000                                                   # integer units per mm
R2 = math.sqrt(2.0)
DIRS = {"E": (1, 0), "SE": (1, 1), "S": (0, 1), "SW": (-1, 1), "W": (-1, 0), "NW": (-1, -1), "N": (0, -1), "NE": (1, -1)}
NAME = {v: k for k, v in DIRS.items()}
RING = ["E", "SE", "S", "SW", "W", "NW", "N", "NE"]
HUMP_K = 8 - 2 * math.pi                                    # a hump of amplitude a at radius r adds 2a - HUMP_K * r
LEG_MIN = 0.105                                             # serp.LEG_MIN: a serpentine leg is absent or at least this long


class BundleError(SystemExit):
    pass


def sgn(v):
    return (v > 0) - (v < 0)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def right(D):
    """Right-hand normal of a direction on the picture (y down): east -> south."""
    return (-D[1], D[0])


def diag(D):
    return D[0] != 0 and D[1] != 0


def ipt(p):
    """mm point -> integer point; refuses coordinates finer than the 0.1 um grid."""
    out = []
    for v in p:
        k = round(v * G)
        if abs(v * G - k) > 1e-3:
            raise BundleError("bundle: coordinate %r is finer than 0.0001 mm" % (v,))
        out.append(int(k))
    return tuple(out)


def fpt(p):
    return (round(p[0] / G, 4), round(p[1] / G, 4))


def turn(d1, d2):
    """Turn between two directions in units of 45 degrees (0..4)."""
    k = abs(RING.index(NAME[d1]) - RING.index(NAME[d2])) % 8
    return min(k, 8 - k)


def dir_of(a, c):
    dx, dy = c[0] - a[0], c[1] - a[1]
    if (dx == 0 and dy == 0) or (dx != 0 and dy != 0 and abs(dx) != abs(dy)):
        return None
    return (sgn(dx), sgn(dy))


class Line:
    """The line N . p = V, travelled in direction D (N = right normal of D). lo / hi: for a lane piece, the
    stations (D . p) between which the lane really is on this line (None = open)."""
    def __init__(self, D, V, lo=None, hi=None, kind="lane", tag=""):
        self.D, self.N, self.V, self.lo, self.hi, self.kind, self.tag = D, right(D), V, lo, hi, kind, tag


def through(D, p, **kw):
    return Line(D, dot(right(D), p), **kw)


def meet(a, b):
    det = a.N[0] * b.N[1] - a.N[1] * b.N[0]
    if det == 0:
        raise BundleError("bundle: %s and %s are parallel, they never meet (a 45-degree leg is missing between them)" % (a.tag, b.tag))
    x = a.V * b.N[1] - b.V * a.N[1]
    y = a.N[0] * b.V - b.N[0] * a.V
    if x % det or y % det:
        raise BundleError("bundle: %s meets %s at 90 degrees off the grid" % (a.tag, b.tag))
    return (x // det, y // det)


def at_uv(D, U, V):
    """The point with station U (= D . p) and lateral position V (= N . p)."""
    det = D[0] * D[0] + D[1] * D[1]
    x, y = U * D[0] - V * D[1], V * D[0] + U * D[1]
    assert x % det == 0 and y % det == 0, "parity"
    return (x // det, y // det)


def clean(pts):
    """Drop repeated points and points on a straight line."""
    out = []
    for p in pts:
        if out and p == out[-1]:
            continue
        out.append(p)
    i = 1
    while i < len(out) - 1:
        if dir_of(out[i - 1], out[i]) == dir_of(out[i], out[i + 1]) and dir_of(out[i], out[i + 1]) is not None:
            del out[i]
        else:
            i += 1
    return out


def shape_errors(pts, min_seg, free_first=False, free_last=False):
    """What is wrong with a polyline of integer points (after clean): list of texts, empty = fine."""
    err = []
    ds = []
    for k, (a, c) in enumerate(zip(pts, pts[1:])):
        d = dir_of(a, c)
        if d is None:
            err.append("segment %s -> %s is not at 0/45/90 degrees" % (fpt(a), fpt(c)))
            ds.append(None); continue
        ds.append(d)
        L = math.hypot(c[0] - a[0], c[1] - a[1]) / G
        if L < min_seg - 1e-7 and not (free_first and k == 0) and not (free_last and k == len(pts) - 2):
            err.append("segment %s -> %s is %.3f mm long (shortest allowed %.2f)" % (fpt(a), fpt(c), L, min_seg))
    for k, (d1, d2) in enumerate(zip(ds, ds[1:])):
        if d1 and d2 and turn(d1, d2) != 1:
            err.append("%d-degree corner at %s" % (45 * turn(d1, d2), fpt(pts[k + 1])))
    return err


def sharp_errors(pts, chamfer):
    """A segment shorter than `chamfer` with a 45-degree corner the same way at both ends reads as a right
    angle (scripts/track_shape.py 'sharp', must be 0)."""
    err = []
    for a, b, c, d in zip(pts, pts[1:], pts[2:], pts[3:]):
        L = math.hypot(c[0] - b[0], c[1] - b[1]) / G
        x1 = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        x2 = (c[0] - b[0]) * (d[1] - c[1]) - (c[1] - b[1]) * (d[0] - c[0])
        if L < chamfer - 1e-7 and x1 * x2 > 0:
            err.append("turns 90 degrees across a %.3f mm segment at %s (two corners the same way closer than %.2f)" % (L, fpt(b), chamfer))
    return err


def seg_dist(a, b, c, d):
    """(shortest distance between segments ab and cd, the point of ab where it is reached). Floats, mm."""
    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])

    def pt_seg(p, s, e):
        vx, vy = e[0] - s[0], e[1] - s[1]
        L2 = vx * vx + vy * vy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - s[0]) * vx + (p[1] - s[1]) * vy) / L2))
        q = (s[0] + t * vx, s[1] + t * vy)
        return math.hypot(p[0] - q[0], p[1] - q[1]), q

    d1, d2, d3, d4 = cross(c, d, a), cross(c, d, b), cross(a, b, c), cross(a, b, d)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 != d2:
        t = d1 / (d1 - d2)
        return 0.0, (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
    best = (pt_seg(a, c, d)[0], a)
    x = (pt_seg(b, c, d)[0], b)
    best = min(best, x)
    for p in (c, d):
        dd, q = pt_seg(p, a, b)
        best = min(best, (dd, q))
    return best


# ---------------------------------------------------------------- a bundle
class Bundle:
    """N lanes round one centre path.

    nets     lane order, left to right seen along the direction of travel
    path     centre path corner points [(x, y), ...]; legs at 0/45/90, corners exactly 45 degrees. The first and
             last point only fix the first / last line and the station zero: lanes start and end at their terminals.
    pitch    centre-to-centre lane spacing in mm, for every leg not named in gaps
    gaps     {leg number: pitch | [N-1 gaps]}: another spacing on that leg (e.g. wide where serpentines go, or
             the row pattern of the ball field the bundle runs into)
    anchor   the lane that sits ON the centre path (net name), or "centre" (the middle of the bundle does)
    span     {net: (first leg, last leg)} for a lane that joins late or leaves early (default: all legs)
    """
    def __init__(self, name, nets, layer, path, pitch, gaps=None, anchor="centre", span=None, min_seg=0.15):
        self.name, self.layer, self.min_seg = name, layer, min_seg
        self.nets = [full(n) for n in nets]
        assert layer in SIGNAL_LAYERS, layer
        n = len(self.nets)
        pts = [ipt(p) for p in path]
        self.legs = []
        for k, (a, c) in enumerate(zip(pts, pts[1:])):
            D = dir_of(a, c)
            if D is None:
                raise BundleError("%s: path leg %d (%s -> %s) is not at 0/45/90 degrees" % (name, k, fpt(a), fpt(c)))
            self.legs.append({"D": D, "N": right(D), "sc": R2 if diag(D) else 1.0, "U0": dot(D, a), "U1": dot(D, c), "Vc": dot(right(D), a)})
        for k in range(len(self.legs) - 1):
            if turn(self.legs[k]["D"], self.legs[k + 1]["D"]) != 1:
                raise BundleError("%s: the corner between leg %d and leg %d is %d degrees (must be 45; write a 90-degree turn as two legs)" % (
                    name, k, k + 1, 45 * turn(self.legs[k]["D"], self.legs[k + 1]["D"])))
        gaps = gaps or {}
        ia = None if anchor == "centre" else self.nets.index(full(anchor))
        for k, leg in enumerate(self.legs):
            g = gaps.get(k, pitch)
            g = [g] * (n - 1) if isinstance(g, (int, float)) else list(g)
            if len(g) != n - 1:
                raise BundleError("%s: gaps[%d] needs %d values (one per pair of neighbouring lanes)" % (name, k, n - 1))
            leg["gv"] = [int(math.ceil(x * G * leg["sc"] - 1e-6)) for x in g]
            pos = [0]
            for x in leg["gv"]:
                pos.append(pos[-1] + x)
            ref = pos[ia] if ia is not None else (pos[0] + pos[-1]) // 2
            leg["V"] = [leg["Vc"] + p - ref for p in pos]
        self.span = {net: (0, len(self.legs) - 1) for net in self.nets}
        for net, sp in (span or {}).items():
            self.span[full(net)] = tuple(sp)
        self.events, self.slots = [], []

    def idx(self, net):
        return self.nets.index(full(net)) if isinstance(net, str) else int(net)

    def U(self, leg, s):
        L = self.legs[leg]
        return L["U0"] + int(round(s * G * L["sc"]))

    # ---- stepping aside
    def widen(self, leg, s0, s1, after, by, side=1):
        """Between stations s0 and s1 of a leg the gap next to lane `after` grows by `by` mm: with side=+1 the
        lanes right of it move right, with side=-1 the lanes left of it move left. They leave and come back on
        45-degree jogs, nested (outer lanes jog out earlier and back later), and the first one has reached its
        new position exactly at s0 and leaves it exactly at s1. s0=None: wide from the start of the leg (no jog
        out: the corner before simply lands on the wide position); s1=None: wide to the end of the leg."""
        L = self.legs[leg]
        BIG = 10 ** 12
        e = {"leg": leg, "U0": -BIG if s0 is None else self.U(leg, s0), "U1": BIG if s1 is None else self.U(leg, s1), "j": self.idx(after),
             "side": 1 if side in (1, "R") else -1, "dV": int(math.ceil(by * G * L["sc"] - 1e-6)), "open0": s0 is None, "open1": s1 is None}
        if e["U1"] <= e["U0"] or e["dV"] <= 0:
            raise BundleError("%s: widen on leg %d needs s1 > s0 and by > 0" % (self.name, leg))
        self.events.append(e)
        return e

    def _hits(self, e, i):
        return i > e["j"] if e["side"] > 0 else i < e["j"]

    def shift(self, leg, i, U, skip=None):
        """Sideways shift (units) of lane i at station U from the widen events."""
        return sum(e["side"] * e["dV"] for e in self.events
                   if e is not skip and e["leg"] == leg and self._hits(e, i) and e["U0"] <= U <= e["U1"])

    def lane_lines(self, net):
        """The lines one lane runs on, in order: lane pieces and the jogs between them."""
        i, out = self.idx(net), []
        f, l = self.span[self.nets[i]]
        for k in range(f, l + 1):
            L = self.legs[k]
            D, N, tag = L["D"], L["N"], "%s leg %d (%s) lane %s" % (self.name, k, NAME[L["D"]], short(self.nets[i]))
            trans = []                                      # (station where the jog begins, sideways move)
            base = L["V"][i] + sum(e["side"] * e["dV"] for e in self.events if e["leg"] == k and self._hits(e, i) and e["open0"])
            for e in self.events:
                if e["leg"] != k or not self._hits(e, i):
                    continue
                j0 = e["j"] + e["side"]                     # the first lane that moves
                for which, Uref in (("out", e["U0"] - 1), ("in", e["U1"] + 1)):
                    if e["open0" if which == "out" else "open1"]:
                        continue
                    Uin = Uref + (1 if which == "out" else -1) * 2     # just inside the event: the other events that are on there
                    spread = abs((L["V"][i] + self.shift(k, i, Uin, e)) - (L["V"][j0] + self.shift(k, j0, Uin, e)))
                    t = int(math.ceil(spread * (R2 - 1))) + abs(i - j0)       # nested: outer lanes earlier out, later in
                    if which == "out":
                        trans.append((e["U0"] - e["dV"] - t, e["side"] * e["dV"], -1))
                    else:
                        trans.append((e["U1"] + t, -e["side"] * e["dV"], 1))
            trans.sort()
            cur, lo = base, None
            for Ub, dV, nudge in trans:
                if diag(D) and (Ub - cur) % 2:              # on a diagonal leg a point needs station and offset of equal parity
                    Ub += nudge
                out.append(Line(D, cur, lo, Ub, "lane", tag))
                Dj = (sgn(D[0] + sgn(dV) * N[0]), sgn(D[1] + sgn(dV) * N[1]))
                out.append(through(Dj, at_uv(D, Ub, cur), kind="jog", tag=tag + " jog"))
                cur += dV; lo = Ub + abs(dV)
            out.append(Line(D, cur, lo, None, "lane", tag))
        return out

    # ---- serpentine sites
    def slot(self, net, leg, s0, length, side="R", free=None, pitch=0.5, amp_cap=2.0):
        """A serpentine site: `length` mm of straight on lane `net` from station s0 of `leg`, humps towards
        side "R" / "L" (higher / lower lane numbers) or "both". With free = mm the neighbours on that side are
        moved (widen) so that their centre line is `free` away from this lane's centre line over the site.
        Returns a Slot; ask it for geometry and TUNING entries after bus.routes()."""
        i = self.idx(net)
        L = self.legs[leg]
        if free is not None:
            for sd in ((1, -1) if side == "both" else ((1,) if side == "R" else (-1,))):
                j = i + sd
                if 0 <= j < len(self.nets):
                    have = L["gv"][min(i, j)] / G / L["sc"]
                    if free > have + 1e-9:
                        self.widen(leg, s0, s0 + length, after=i, by=free - have, side=sd)
        s = Slot(self, i, leg, s0, length, side, pitch, amp_cap)
        self.slots.append(s)
        return s

    def lane_point(self, net, leg, s):
        """Integer point of a lane at a station (widen events included)."""
        i, L = self.idx(net), self.legs[leg]
        U = self.U(leg, s)
        V = L["V"][i] + self.shift(leg, i, U)
        if diag(L["D"]) and (U - V) % 2:
            U += 1
        return at_uv(L["D"], U, V)


class Slot:
    def __init__(self, b, i, leg, s0, length, side, pitch, amp_cap):
        self.b, self.i, self.leg, self.s0, self.length, self.side, self.pitch, self.amp_cap = b, i, leg, s0, length, side, pitch, amp_cap
        self.net = b.nets[i]
        self.bus = None

    def geometry(self):
        """Where the site is on the built routes: end points, side as a board direction, the free width to the
        neighbouring lane(s), the tallest hump that leaves serpentine clearance to it, and the board track it
        sits on (routes are cut into board tracks at corners and width changes; a serpentine needs ONE track)."""
        b, L = self.b, self.b.legs[self.leg]
        if self.bus is None or self.bus._routes is None:
            raise BundleError("slot %s: call bus.routes() first" % short(self.net))
        p0, p1 = b.lane_point(self.i, self.leg, self.s0), b.lane_point(self.i, self.leg, self.s0 + self.length)
        Um = (dot(L["D"], p0) + dot(L["D"], p1)) // 2
        if b.shift(self.leg, self.i, dot(L["D"], p0)) != b.shift(self.leg, self.i, dot(L["D"], p1)):
            raise BundleError("slot %s on %s leg %d: the lane itself jogs inside the site" % (short(self.net), b.name, self.leg))
        free = {}
        for sd in (1, -1):
            j = self.i + sd
            while 0 <= j < len(b.nets) and not (b.span[b.nets[j]][0] <= self.leg <= b.span[b.nets[j]][1]):
                j += sd
            if 0 <= j < len(b.nets):
                free[sd] = abs((L["V"][j] + b.shift(self.leg, j, Um)) - (L["V"][self.i] + b.shift(self.leg, self.i, Um))) / G / L["sc"]
        a, c = fpt(p0), fpt(p1)
        mid = ((a[0] + c[0]) / 2, (a[1] + c[1]) / 2)
        track = None
        for lay, pts in self.bus.final[self.net]:
            if lay != b.layer:
                continue
            for q0, q1, w in board.split_widths([tuple(p) for p in pts]):
                if all(seg_dist(q0, q1, p, p)[0] < 2e-4 for p in (a, c)):
                    track = (q0, q1, w)
        if track is None:
            raise BundleError("slot %s on %s leg %d (%s .. %s): not on ONE straight board track of the net (a corner, a jog or a width change lies inside; "
                              "0.09 track runs to 0.3 mm outside a rule area)" % (short(self.net), b.name, self.leg, a, c))
        w = track[2]
        clr = max(SERP["clr"], CLR_IN if w < W_OUT - 1e-6 else CLR_OUT)
        amax = {sd: min(self.amp_cap, f - w - clr - 0.004) for sd, f in free.items()}
        if self.side != "both":                             # serp.py keeps `clr` round ALL copper of a block, also behind the humps
            back = free.get(-1 if self.side == "R" else 1)
            if back is not None and back < w + clr + 0.002 - 1e-9:
                raise BundleError("slot %s on %s leg %d: the lane behind the humps is %.4f mm away, a serpentine needs %.4f (width %.4f + serpentine clearance %.2f): "
                                  "give that gap at least %.3f on this leg (gaps=) or widen it" % (short(self.net), b.name, self.leg, back, w + clr + 0.002, w, clr, w + clr + 0.003))
        N = L["N"]
        return {"net": self.net, "layer": b.layer, "from": a, "to": c, "at": (round(mid[0], 4), round(mid[1], 4)), "length": math.dist(a, c),
                "side": {1: NAME[N], -1: NAME[(-N[0], -N[1])]}, "free": free, "amp_max": amax, "width": w,
                "track": (track[0], track[1]), "track_length": math.dist(track[0], track[1]), "lead": math.dist(track[0], a)}

    def fill(self, add=None, amp=None, n=None):
        """One block of EQUAL-height humps in this site: give the length to add (the height is solved; as many
        humps as the site takes, fewer only when they would be too low to be legal) or the height (and
        optionally the number of humps). The block is centred in the site. Appends the TUNING entry to the
        bus and returns it (with "gain" = what it adds, for the author's arithmetic)."""
        g, p, r = self.geometry(), self.pitch, self.pitch / 2
        both = self.side == "both"
        sd = 1 if self.side == "R" else -1
        cap = min(g["amp_max"].get(1, self.amp_cap), g["amp_max"].get(-1, self.amp_cap)) if both else g["amp_max"].get(sd, self.amp_cap)
        nmax = int((g["length"] + 1e-6) / p) - 1 if both else int((g["length"] + 1e-6) / (2 * p))
        used = (lambda k: p * (k + 1)) if both else (lambda k: 2 * p * k)
        gain = (lambda k, a: 2 * k * a - (4 - math.pi) * r * (k + 1)) if both else (lambda k, a: k * (2 * a - HUMP_K * r))
        legal = lambda a: abs(a - p) < 1e-6 or a >= p + LEG_MIN - 1e-9
        tag = "slot %s on %s leg %d" % (short(self.net), self.b.name, self.leg)
        nmin = 2 if both else 1
        if nmax < nmin:
            raise BundleError("%s: %.2f mm of straight is too short for a hump at pitch %.2f" % (tag, g["length"], p))
        if amp is None:
            if add is None:
                raise BundleError("%s: give add= or amp=" % tag)
            pick = None
            for k in ([n] if n else range(nmax, nmin - 1, -1)):
                a = (add + (4 - math.pi) * r * (k + 1)) / (2 * k) if both else (add / k + HUMP_K * r) / 2
                if legal(a) and a <= cap + 1e-9:
                    pick = (k, a); break
            if pick is None:
                raise BundleError("%s: +%.3f mm does not fit as one equal-height block (site %.2f mm, pitch %.2f, at most %d humps of %.3f: +%.3f)" % (
                    tag, add, g["length"], p, nmax, cap, gain(nmax, cap)))
            n, amp = pick
        else:
            n = n or nmax
            if n > nmax or amp > cap + 1e-9 or not legal(amp):
                raise BundleError("%s: %d humps of %.3f do not fit (site takes %d humps, tallest %.3f; a height is %.2f or at least %.3f)" % (
                    tag, n, amp, nmax, cap, p, p + LEG_MIN))
        amp = round(amp, 4)
        where = g["lead"] + (g["length"] - used(n)) / 2
        end = SERP["end"]
        if where < end - 1e-6 or where + used(n) > g["track_length"] - end + 1e-6:
            raise BundleError("%s: the block would start %.3f mm from one end of its board track and stop %.3f mm from the other (needs %.2f)" % (
                tag, where, g["track_length"] - where - used(n), end))
        e = {"net": short(self.net), "at": g["at"], "layer": g["layer"], "pitch": p, "n": n, "amp": amp, "where": round(where, 4)}
        if both:
            e.update(side="both", first=g["side"][1])
        else:
            e["side"] = g["side"][sd]
        self.bus._tuning.append((self.net, g["layer"], g["track"], g["lead"], e))
        return dict(e, gain=round(gain(n, amp), 4))


# ---------------------------------------------------------------- the bus: bundles + hand routes -> ROUTES
class Bus:
    def __init__(self, swap, min_seg=0.15, fan_step=0.05, fan_max=8.0, chamfer=0.35):
        """swap = the variant's SWAP (net -> SDRAM pin name); it fixes the SDRAM pad of every net."""
        self.min_seg, self.fan_step, self.fan_max, self.chamfer = min_seg, fan_step, fan_max, chamfer
        table, _ = balls.check_swap(swap)
        self.pad, self.rounds = {}, []                      # rounds: (layer or None, net or None, centre mm, radius)
        for ref, ctr in (("U1", MCU), ("U2", RAM)):
            mine = {(balls.MCU_PINS[n][1] if ref == "U1" else table[n][1]): n for n in table}
            for ball, (x, y, size) in balls.fp_pads(FOOTPRINT[ref][0]).items():
                c = (round(ctr[0] + x, 4), round(ctr[1] + y, 4))
                self.rounds.append(("L1", mine.get(ball), c, size / 2))
                if ball in mine:
                    self.pad[(ref, mine[ball])] = c
        self.plan = {}                                      # net -> [item]; item = {"raw": pieces} | section dict
        self.kept = {}
        self.secs, self.bundles = [], []
        self.problems, self._routes, self.final, self._tuning = [], None, {}, []

    # ---- input
    def _pt(self, net, p):
        return self.pad[(p, net)] if isinstance(p, str) else (float(p[0]), float(p[1]))

    def _raw(self, net, pieces):
        out = []
        for pc in pieces:
            if pc[0] == "via":
                out.append(("via", self._pt(net, pc[1])) + tuple(pc[2:]))
            else:
                out.append((pc[0], [self._pt(net, p) for p in pc[1]]))
        return out

    def keep(self, routes):
        """Hand-written routes (lib/README.md format): returned unchanged by routes() and used as obstacles."""
        for net, pieces in routes.items():
            self.kept[full(net)] = (pieces, self._raw(full(net), pieces))

    def _terminal(self, net, spec, start):
        """-> (raw pieces before / after, lead points on the bundle's layer). Forms: "U1" / "U2" (the pad),
        (x, y) (a via or any point), [p, p, ...] (a hand-written lead on the bundle's layer, in travel
        order, strings allowed), {"pieces": [...]} (pieces on other layers; the bundle starts at their last
        point / ends at their first point; the via is added)."""
        if isinstance(spec, dict):
            raw = self._raw(net, spec["pieces"])
            pc = raw[-1] if start else raw[0]
            p = pc[1] if pc[0] == "via" else (pc[1][-1] if start else pc[1][0])
            return raw, [ipt(p)]
        if isinstance(spec, str) or (isinstance(spec, tuple) and not isinstance(spec[0], (tuple, list, str))):
            spec = [spec]
        return [], [ipt(self._pt(net, p)) for p in spec]

    def add(self, bundle, start=None, end=None):
        """Put a bundle on the bus. start / end = {net: terminal} (see _terminal). A net without a start whose
        route so far ends open on the same layer JOINS: its last line simply runs on until it meets its lane
        of this bundle (merging); a net without an end stays open for a later bundle (splitting: give the nets
        that leave an end or a shorter span, the others run on)."""
        start = {full(k): v for k, v in (start or {}).items()}
        end = {full(k): v for k, v in (end or {}).items()}
        self._routes = None
        self.bundles.append(bundle)
        for s in bundle.slots:
            s.bus = self
        for net in bundle.nets:
            items = self.plan.setdefault(net, [])
            lines = bundle.lane_lines(net)
            open_sec = items[-1] if items and "lines" in items[-1] and items[-1]["end"] is None else None
            if net in start:
                if open_sec:
                    raise BundleError("%s: %s still runs open in bundle %s, it cannot start again" % (bundle.name, short(net), open_sec["bundles"][-1].name))
                raw, lead = self._terminal(net, start[net], True)
                if raw:
                    items.append({"raw": raw})
                sec = {"net": net, "layer": bundle.layer, "lines": lines, "start": lead, "end": None, "bundles": [bundle]}
                items.append(sec); self.secs.append(sec)
            else:
                if not open_sec or open_sec["layer"] != bundle.layer:
                    raise BundleError("%s: %s has no start terminal and no open lane on %s to join from" % (bundle.name, short(net), bundle.layer))
                sec = open_sec
                sec["lines"] = self._join(sec["lines"], lines)
                sec["bundles"].append(bundle)
            if net in end:
                raw, lead = self._terminal(net, end[net], False)
                sec["end"] = lead
                if raw:
                    items.append({"raw": raw})

    def _join(self, A, B):
        """Chain two line lists of one net. The lane leaves A on the last piece that reaches the meeting point
        and enters B on the first piece that is still there (so a lane may join where the bundle is widened)."""
        m = self.min_seg * G
        ia = [k for k, l in enumerate(A) if l.kind == "lane"]
        ib = [k for k, l in enumerate(B) if l.kind == "lane"]
        for ka in reversed(ia):
            if A[ka].D != A[-1].D:
                break
            for kb in ib:
                if B[kb].D != B[0].D:
                    break
                a, b = A[ka], B[kb]
                if a.D == b.D:
                    if a.V == b.V:
                        return A[:ka + 1] + B[kb + 1:]
                    continue
                if turn(a.D, b.D) != 1:
                    raise BundleError("join: %s meets %s at %d degrees (must be 45)" % (a.tag, b.tag, 45 * turn(a.D, b.D)))
                X = meet(a, b)
                ua, ub = dot(a.D, X), dot(b.D, X)
                sa, sb = (R2 if diag(a.D) else 1.0), (R2 if diag(b.D) else 1.0)
                if (a.lo is None or ua >= a.lo + m * sa) and (a.hi is None or ua <= a.hi) and (b.hi is None or ub <= b.hi - m * sb) and (b.lo is None or ub >= b.lo):
                    return A[:ka + 1] + B[kb:]
        raise BundleError("join: %s cannot reach %s: they are parallel on different lines, or they meet inside a jog / less than %.2f mm after one "
                          "(end the widen earlier, or leave it open with s1=None so that the lane joins while it is still out)" % (A[-1].tag, B[0].tag, self.min_seg))

    # ---- obstacles
    def _need(self, p, what, r=0.0):
        """Smallest allowed centre distance at point p: track to track, or track to a pad / via of radius r."""
        w, c = (W_IN, CLR_IN) if area_of(p) else (W_OUT, CLR_OUT)
        return (w + c) if what == "track" else (r + w / 2 + c)

    def _hit(self, net, layer, segs, obst):
        """First obstacle the float segments come too close to: text, or None."""
        for a, b in segs:
            x0, x1, y0, y1 = min(a[0], b[0]) - 0.7, max(a[0], b[0]) + 0.7, min(a[1], b[1]) - 0.7, max(a[1], b[1]) + 0.7
            for o in obst:
                if o[2] == net or (o[1] is not None and o[1] != layer):
                    continue
                c, d = o[3], o[4]
                if max(c[0], d[0]) < x0 or min(c[0], d[0]) > x1 or max(c[1], d[1]) < y0 or min(c[1], d[1]) > y1:
                    continue
                dist, q = seg_dist(a, b, c, d)
                need = self._need(q, "track") if o[0] == "seg" else self._need(q, "round", o[5])
                if dist < need - 1e-6:
                    who = short(o[2]) if o[2] else "an unused ball"
                    kind = {"seg": "track", "pad": "pad", "via": "via"}[o[0]]
                    return ("crosses %s's %s" % (who, kind) if dist < 1e-9 else "%.3f mm from %s's %s (needs %.3f)" % (dist, who, kind, need)) + " at (%.3f, %.3f)" % q
        return None

    def _obst_pieces(self, net, pieces):
        out = []
        for pc in pieces:
            if pc[0] == "via":
                size = pc[2] if len(pc) > 2 else (VIA_IN if area_of(pc[1]) else VIA_OUT)
                out.append(("via", None, net, pc[1], pc[1], size[0] / 2))
            else:
                out += [("seg", pc[0], net, a, c) for a, c in zip(pc[1], pc[1][1:])]
        return out

    # ---- fans
    def _fan(self, sec, start, obst):
        """Connect the terminal of a section to its first (start) or last line: terminal, an optional straight
        along the lane direction, one 45-degree stub onto the lane line. The straight is the shortest (0.05 mm
        steps) that keeps shape and clearance. Returns the points in travel order."""
        net, layer = sec["net"], sec["layer"]
        line = sec["lines"][0 if start else -1]
        f = 1 if start else -1
        Df, N = (f * line.D[0], f * line.D[1]), line.N
        lead = sec["start"] if start else sec["end"]
        T = lead[-1] if start else lead[0]
        beyond = (lead[-2] if len(lead) > 1 else None) if start else (lead[1] if len(lead) > 1 else None)
        if start:
            nxt = sec["core"][0] if sec["core"] else None
        else:
            nxt = sec["core"][-1] if sec["core"] else sec["start_pts"][-1]
        dV = line.V - dot(N, T)
        step1 = dot(Df, Df)                                 # station advance of one unit step along the lane
        ul = (R2 if diag(Df) else 1.0) / G                  # mm per unit step
        ks = [0] + list(range(int(math.ceil(self.min_seg / ul)), int(self.fan_max / ul), max(1, int(round(self.fan_step / ul)))))
        first_bad, fallback = None, None
        for k in ks:
            q = (T[0] + k * Df[0], T[1] + k * Df[1])
            if dV == 0:
                if k:
                    break
                pts = [T]
            else:
                Dj = (sgn(Df[0] + sgn(dV) * N[0]), sgn(Df[1] + sgn(dV) * N[1]))
                pts = [T, q, meet(through(Dj, q, tag="fan stub of " + short(net)), line)]
            if nxt is not None:
                room = (dot(Df, nxt) - dot(Df, pts[-1])) / G / (R2 if diag(Df) else 1.0)
                if room < self.min_seg - 1e-7:
                    first_bad = first_bad or "the stub joins the lane %.3f mm before the lane's next corner at %s (needs %.2f): move the corner or the terminal" % (room, fpt(nxt), self.min_seg)
                    break
            poly = clean(([beyond] if beyond else []) + pts + ([nxt] if nxt else []))
            errs = shape_errors(poly, self.min_seg, free_first=beyond is not None) + sharp_errors(poly, self.chamfer)
            if errs:
                first_bad = first_bad or errs[0]
                continue
            fallback = fallback or pts
            segs = [(fpt(a), fpt(c)) for a, c in zip(poly, poly[1:])]
            why = self._hit(net, layer, segs, obst)
            if why is None:
                return pts if start else pts[::-1]
            first_bad = first_bad or why
        b = sec["bundles"][0 if start else -1]
        self.problems.append("FAN %s %s %s: no stub from %s reaches the lane cleanly (%s)" % (b.name, "start" if start else "end", short(net), fpt(T), first_bad))
        if fallback is None:
            raise BundleError("\n".join(["bundle: cannot even draw the stub:"] + self.problems))
        return fallback if start else fallback[::-1]

    def _fan_group(self, bundle, start, obst):
        secs = [s for s in self.secs if s["bundles"][0 if start else -1] is bundle and (s["start"] if start else s["end"]) is not None
                and (start or s.get("end_pts") is None)]
        if not start:
            secs = [s for s in secs if s["end"] is not None]
        rows = []
        for s in secs:
            line = s["lines"][0 if start else -1]
            T = s["start"][-1] if start else s["end"][0]
            rows.append((bundle.idx(s["net"]), line.V - dot(line.N, T), dot(line.N, T), s))
        rows.sort(key=lambda r: r[0])
        for (i, _, vt_i, si), (j, _, vt_j, sj) in zip(rows, rows[1:]):   # the order of the terminals against the lane order
            if si["lines"][0 if start else -1].D == sj["lines"][0 if start else -1].D and vt_i > vt_j:
                self.problems.append("ORDER %s %s: lane %s is left of lane %s in the bundle but its terminal %s is on the right of %s: they cross "
                                     "(swap the lanes, or swap the pins on the SDRAM side)" % (
                                         bundle.name, "start" if start else "end", short(si["net"]), short(sj["net"]),
                                         fpt(si["start"][-1] if start else si["end"][0]), fpt(sj["start"][-1] if start else sj["end"][0])))
        order = ([r for r in rows if r[1] == 0] + sorted([r for r in rows if r[1] > 0], key=lambda r: -r[0])
                 + sorted([r for r in rows if r[1] < 0], key=lambda r: r[0]))   # movers to the right: rightmost first; to the left: leftmost first
        for _, _, _, s in order:
            pts = self._fan(s, start, obst)
            if start:
                s["start_pts"] = s["start"][:-1] + pts
                done = s["start_pts"] + (s["core"][:1])
            else:
                s["end_pts"] = pts + s["end"][1:]
                done = (s["core"][-1:] or s["start_pts"][-1:]) + s["end_pts"]
            done = clean(done)
            obst += [("seg", s["layer"], s["net"], fpt(a), fpt(c)) for a, c in zip(done, done[1:])]

    # ---- output
    def routes(self, strict=True):
        """{net: pieces} for ROUTES (kept hand routes included). Every problem found (fan order, a stub that
        does not fit, a corner that eats a leg, crossings and gaps below the DRC clearance) is listed; with
        strict=True the build stops on them, with strict=False they are printed and the routes are returned
        anyway so that the picture can be looked at."""
        if self._routes is not None:
            return self._routes
        self.problems = []
        obst = [("pad", lay, net, c, c, r) for lay, net, c, r in self.rounds]
        for net, (_, raw) in self.kept.items():
            obst += self._obst_pieces(net, raw)
        for net, items in self.plan.items():
            for it in items:
                if "raw" in it:
                    obst += self._obst_pieces(net, it["raw"])
        for s in self.secs:
            if s["end"] is None:
                raise BundleError("bundle: %s is left open at the end of %s (give it an end terminal or a bundle to run into)" % (short(s["net"]), s["bundles"][-1].name))
            L = s["lines"]
            s["core"] = [meet(L[k], L[k + 1]) for k in range(len(L) - 1)]
            s.pop("start_pts", None); s.pop("end_pts", None)
            obst += [("seg", s["layer"], s["net"], fpt(a), fpt(c)) for a, c in zip(s["core"], s["core"][1:])]
        for b in self.bundles:
            self._fan_group(b, True, obst)
        for b in self.bundles:
            self._fan_group(b, False, obst)
        out, self.final = {}, {}
        for net, (pieces, raw) in self.kept.items():
            out[net], self.final[net] = pieces, [(pc[0], pc[1]) for pc in raw]
        for net, items in self.plan.items():
            flat = []
            for it in items:
                if "raw" in it:
                    flat += [(pc[0], pc[1]) if pc[0] == "via" else (pc[0], list(pc[1])) for pc in it["raw"]]
                    continue
                L = it["lines"]
                poly = clean(it["start_pts"] + it["core"] + it["end_pts"])
                n0, n1 = len(clean(it["start_pts"])), len(clean(it["end_pts"]))
                for e in shape_errors(poly, self.min_seg, free_first=len(it["start"]) > 1, free_last=len(it["end"]) > 1):
                    self.problems.append("SHAPE %s (%s): %s" % (short(net), " + ".join(b.name for b in it["bundles"]), e))
                for e in sharp_errors(poly, self.chamfer):
                    self.problems.append("SHARP %s (%s): %s" % (short(net), " + ".join(b.name for b in it["bundles"]), e))
                full_chain = it["start_pts"][-1:] + it["core"] + it["end_pts"][:1]
                for k, l in enumerate(L):                   # every piece must run forwards along its line
                    a, c = full_chain[k], full_chain[k + 1]
                    d = dot(l.D, c) - dot(l.D, a)
                    if d < 0:
                        self.problems.append("SHAPE %s: %s runs backwards by %.3f mm (the corners / jogs round it need more room)" % (
                            short(net), l.tag, -d / G / (R2 if diag(l.D) else 1.0)))
                flat.append((it["layer"], [fpt(p) for p in poly]))
            pieces = []
            for pc in flat:                                 # vias at layer changes, same-layer neighbours merged
                if pieces and pc[0] != "via" and pieces[-1][0] != "via":
                    if pieces[-1][0] == pc[0]:
                        merged = clean([ipt(p) for p in pieces[-1][1] + pc[1]])
                        pieces[-1] = (pc[0], [fpt(p) for p in merged]); continue
                    pieces.append(("via", pieces[-1][1][-1]))
                pieces.append(pc)
            where = None
            for pc in pieces:
                p0 = pc[1] if pc[0] == "via" else pc[1][0]
                if where is not None and math.dist(where, p0) > 1e-6:
                    self.problems.append("PATH %s: a piece starts at %s but the net was at %s" % (short(net), p0, where))
                where = pc[1] if pc[0] == "via" else pc[1][-1]
            self.final[net] = pieces
            res = []
            for pc in pieces:
                if pc[0] == "via":
                    res.append(pc); continue
                pts = list(pc[1])
                if pc is pieces[0] and math.dist(pts[0], self.pad[("U1", net)]) < 1e-6:
                    pts[0] = "U1"
                if pc is pieces[-1] and math.dist(pts[-1], self.pad[("U2", net)]) < 1e-6:
                    pts[-1] = "U2"
                res.append((pc[0], pts))
            if res[0][1][0] != "U1" or res[-1][1][-1] != "U2":
                self.problems.append("PATH %s: the route does not run from its MCU pad to its SDRAM pad" % short(net))
            out[net] = res
        self._check()
        self._routes = out
        if self.problems:
            text = "\n".join(["bundle: %d problem(s):" % len(self.problems)] + ["  BUNDLE " + p for p in self.problems])
            if strict:
                self._routes = None
                raise BundleError(text)
            print(text)
        return out

    def _check(self):
        """Every generated net against everything else: crossings and centre distances below width + clearance."""
        allo = {}
        for net, pieces in self.final.items():
            allo[net] = self._obst_pieces(net, pieces)
        pads = [("pad", lay, net, c, c, r) for lay, net, c, r in self.rounds]
        seen = set()
        for net in self.plan:
            for o in allo[net]:
                if o[0] != "seg":
                    continue
                for other, ob in list(allo.items()) + [(None, pads)]:
                    if other == net or (other in self.plan and other is not None and (other, net, o[1]) in seen):
                        continue
                    why = self._hit(net, o[1], [(o[3], o[4])], ob)
                    if why and (net, other, o[1]) not in seen:
                        seen.add((net, other, o[1]))
                        self.problems.append("GAP %s %s: %s" % (o[1], short(net), why))

    # ---- numbers
    def lengths(self):
        """{net: {"total", "layers": {L: mm}, "vias", "via_mm", "direct"}} of the routes as generated (no serpentines)."""
        if self._routes is None:
            self.routes()
        out = {}
        for net, pieces in self.final.items():
            lay, vias, vmm, prev = {}, 0, 0.0, None
            tracks = [pc for pc in pieces if pc[0] != "via"]
            for pc in tracks:
                lay[pc[0]] = lay.get(pc[0], 0.0) + sum(math.dist(a, c) for a, c in zip(pc[1], pc[1][1:]))
                if prev and prev != pc[0]:
                    vias += 1; vmm += board.via_height(prev, pc[0])
                prev = pc[0]
            out[net] = {"total": sum(lay.values()) + vmm, "layers": lay, "vias": vias, "via_mm": vmm,
                        "direct": octile(self.pad[("U1", net)], self.pad[("U2", net)])}
        return out

    def report(self):
        """Text table: every net's length before any serpentine, lane by lane, so that lane order and the
        serpentine budget can be chosen from numbers."""
        Ls = self.lengths()
        ref = Ls.get(REF, {}).get("total")
        longest = max(v["total"] for v in Ls.values())
        o = ["bundle length report (mm, by geometry, via height included, no serpentines)",
             "  %-8s %-18s %8s %8s %8s %9s  %4s  %s" % ("net", "bundles (lane)", "length", "direct", "to CLK", "to longest", "vias", "per layer")]
        done = set()
        rows = []
        for b in self.bundles:
            for i, net in enumerate(b.nets):
                if net not in done:
                    done.add(net)
                    where = ", ".join("%s(%d)" % (bb.name, bb.nets.index(net)) for bb in self.bundles if net in bb.nets)
                    rows.append((net, where))
        rows += [(net, "hand route") for net in self.kept if net not in done]
        for net, where in rows:
            v = Ls[net]
            o.append("  %-8s %-18s %8.3f %8.3f %8s %9.3f  %4d  %s" % (
                short(net), where, v["total"], v["direct"], "%+.3f" % (v["total"] - ref) if ref is not None else "-", v["total"] - longest, v["vias"],
                " ".join("%s %.2f" % kv for kv in sorted(v["layers"].items()))))
        return "\n".join(o)

    def tuning(self):
        """The TUNING entries of every slot.fill() so far. Blocks on one board track are applied from the SDRAM
        end backwards, so that the "where" offsets (measured from the track's MCU-side end) stay true."""
        order, groups = [], {}
        for net, layer, track, lead, e in self._tuning:
            k = (net, layer, track)
            if k not in groups:
                groups[k] = []; order.append(k)
            groups[k].append((lead, e))
        out = []
        for k in order:
            out += [e for _, e in sorted(groups[k], key=lambda x: -x[0])]
        return out


# ---------------------------------------------------------------- self test (no board): D:/KiCad/bin/python.exe lib/bundle.py
def _selftest():
    """Eight lanes, E -> SE -> E (one corner pair), pitch 0.25 / 0.30 / 0.25, a widen on the diagonal leg:
    checks nested corners (outer lanes longer by the textbook amount), spacing on every leg, jog nesting."""
    nets = ["D%d" % i for i in range(8)]
    b = Bundle("t", nets, "L4", [(0, 0), (4, 0), (8, 4), (12, 4)], 0.25, gaps={1: 0.30})
    b.widen(1, 1.5, 3.5, after="D3", by=0.6)
    polys = {}
    for n in nets:
        L = b.lane_lines(n)
        y = L[0].V
        pts = clean([(0, y)] + [meet(L[k], L[k + 1]) for k in range(len(L) - 1)] + [(12 * G, L[-1].V)])
        assert not shape_errors(pts, 0.15), (n, shape_errors(pts, 0.15))
        polys[n] = [fpt(p) for p in pts]
    length = {n: sum(math.dist(a, c) for a, c in zip(p, p[1:])) for n, p in polys.items()}
    gmin = {}
    for n1, n2 in zip(nets, nets[1:]):
        gmin[(n1, n2)] = min(seg_dist(a, c, d, e)[0] for a, c in zip(polys[n1], polys[n1][1:]) for d, e in zip(polys[n2], polys[n2][1:]))
    print("bundle self test: 8 lanes, E -> SE -> E, pitch 0.25 / 0.30 / 0.25, lanes right of D3 step aside 0.6 mm on the diagonal")
    for n in nets:
        print("  %-3s %7.4f mm  %2d points  %s" % (n, length[n], len(polys[n]), " ".join("(%.3f,%.3f)" % p for p in polys[n][:4]) + " ..."))
    print("  smallest centre distance between neighbours: " + ", ".join("%.4f" % v for v in gmin.values()))
    assert all(v >= 0.25 - 1e-6 for v in gmin.values()), gmin
    # E -> SE turns right (lane 0 is outside, longer); SE -> E turns left (lane 0 inside): with equal pitch on the
    # two E legs the two corners cancel and only the wider diagonal pitch leaves a difference of
    # 2 * (0.30 * sqrt(2) - 0.25) * (1 - sqrt(2)) ... checked numerically instead: lanes 0-3 (no jog) are an arithmetic row
    d = [length[nets[i + 1]] - length[nets[i]] for i in range(3)]
    assert max(d) - min(d) < 1e-3, d
    print("  lanes D0..D3 differ by a constant %.4f mm per lane (nested corners); D4..D7 carry two jogs each: +%.4f mm" % (d[0], length["D4"] - length["D3"] - d[0]))
    print("  OK")


if __name__ == "__main__":
    _selftest()
