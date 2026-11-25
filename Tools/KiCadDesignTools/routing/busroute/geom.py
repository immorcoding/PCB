"""Exact 0/45/90 geometry on an integer grid (0.1 um) and the float helpers of the checks.

Coordinates are LOCAL mm: board-file mm minus the board's origin, x to the right, y DOWN (as in KiCad),
so "N" is up on a picture and means smaller y. Everything that is generated (lanes, stubs, fan-out leads)
is computed on integers; a track is a piece of a line in one of four normal forms (x = c, y = c,
x - y = c, x + y = c) and a vertex is the meeting point of two lines.
"""
import math

G = 10000                                                   # integer units per mm
R2 = math.sqrt(2.0)
DIRS = {"E": (1, 0), "SE": (1, 1), "S": (0, 1), "SW": (-1, 1), "W": (-1, 0), "NW": (-1, -1), "N": (0, -1), "NE": (1, -1)}
NAME = {v: k for k, v in DIRS.items()}
RING = ["E", "SE", "S", "SW", "W", "NW", "N", "NE"]


class RouteError(Exception):
    """A description that cannot be turned into geometry. The text says what and where."""


def sgn(v):
    return (v > 0) - (v < 0)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def right(D):
    """Right-hand normal of a direction on the picture (y down): east -> south."""
    return (-D[1], D[0])


def diag(D):
    return D[0] != 0 and D[1] != 0


def unit(D):
    """mm of track per unit step along direction D."""
    return (R2 if diag(D) else 1.0) / G


def ipt(p):
    """mm point -> integer point; refuses coordinates finer than the 0.1 um grid."""
    out = []
    for v in p:
        k = round(v * G)
        if abs(v * G - k) > 2e-3:
            raise RouteError("coordinate %r is finer than the 0.0001 mm grid" % (v,))
        out.append(int(k))
    return tuple(out)


def fpt(p):
    return (round(p[0] / G, 4), round(p[1] / G, 4))


def dir_of(a, c):
    """Direction (sign pair) of the integer segment a -> c, or None when it is not at 0/45/90 degrees."""
    dx, dy = c[0] - a[0], c[1] - a[1]
    if (dx == 0 and dy == 0) or (dx != 0 and dy != 0 and abs(dx) != abs(dy)):
        return None
    return (sgn(dx), sgn(dy))


def turn(d1, d2):
    """Turn between two directions in units of 45 degrees (0..4)."""
    k = abs(RING.index(NAME[d1]) - RING.index(NAME[d2])) % 8
    return min(k, 8 - k)


class Line:
    """The line N . p = V travelled in direction D (N = right normal of D). lo / hi: the stations (D . p)
    between which a lane really is on this line (None = open)."""
    __slots__ = ("D", "N", "V", "lo", "hi", "kind", "tag", "leg")

    def __init__(self, D, V, lo=None, hi=None, kind="lane", tag="", leg=None):
        self.D, self.N, self.V, self.lo, self.hi, self.kind, self.tag, self.leg = D, right(D), V, lo, hi, kind, tag, leg


def through(D, p, **kw):
    return Line(D, dot(right(D), p), **kw)


def meet(a, b):
    det = a.N[0] * b.N[1] - a.N[1] * b.N[0]
    if det == 0:
        raise RouteError("%s and %s are parallel, they never meet (a 45-degree leg is missing between them)" % (a.tag, b.tag))
    x = a.V * b.N[1] - b.V * a.N[1]
    y = a.N[0] * b.V - b.N[0] * a.V
    if x % det or y % det:
        raise RouteError("%s meets %s off the grid" % (a.tag, b.tag))
    return (x // det, y // det)


def at_uv(D, U, V):
    """The point with station U (= D . p) and lateral position V (= N . p)."""
    det = D[0] * D[0] + D[1] * D[1]
    x, y = U * D[0] - V * D[1], V * D[0] + U * D[1]
    if x % det or y % det:
        raise RouteError("station / offset parity: no grid point at U %d V %d on a diagonal" % (U, V))
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
        d = dir_of(out[i], out[i + 1])
        if d is not None and dir_of(out[i - 1], out[i]) == d:
            del out[i]
        else:
            i += 1
    return out


def ilen(a, c):
    return math.hypot(c[0] - a[0], c[1] - a[1]) / G


def shape_errors(pts, min_seg, free_first=False, free_last=False):
    """What is wrong with a polyline of integer points: [(kind, text, point mm)], kinds SHAPE and CORNER."""
    err, ds = [], []
    for k, (a, c) in enumerate(zip(pts, pts[1:])):
        d = dir_of(a, c)
        ds.append(d)
        if d is None:
            err.append(("SHAPE", "segment %s -> %s is not at 0/45/90 degrees" % (fpt(a), fpt(c)), fpt(a)))
            continue
        L = ilen(a, c)
        if L < min_seg - 1e-7 and not (free_first and k == 0) and not (free_last and k == len(pts) - 2):
            err.append(("SHAPE", "segment %s -> %s is %.4f mm long (shortest allowed %.2f)" % (fpt(a), fpt(c), L, min_seg), fpt(a)))
    for k, (d1, d2) in enumerate(zip(ds, ds[1:])):
        if d1 and d2 and turn(d1, d2) > 1:
            err.append(("CORNER", "%d-degree corner at %s (only 45-degree bends)" % (45 * turn(d1, d2), fpt(pts[k + 1])), fpt(pts[k + 1])))
    return err


def sharp_errors(pts, chamfer):
    """A segment shorter than `chamfer` with a corner the same way at both ends reads as a right angle
    (analysis/track_shape.py 'sharp')."""
    err = []
    for a, b, c, d in zip(pts, pts[1:], pts[2:], pts[3:]):
        L = ilen(b, c)
        x1 = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        x2 = (c[0] - b[0]) * (d[1] - c[1]) - (c[1] - b[1]) * (d[0] - c[0])
        if L < chamfer - 1e-7 and x1 * x2 > 0:
            err.append(("SHARP", "turns 90 degrees across a %.3f mm segment at %s (two corners the same way closer than %.2f)" % (L, fpt(b), chamfer), fpt(b)))
    return err


# ---------------------------------------------------------------- floats (mm)
def octile(a, c):
    """Shortest length of a 0/45/90-degree path between two points, ignoring obstacles."""
    dx, dy = abs(a[0] - c[0]), abs(a[1] - c[1])
    return max(dx, dy) - min(dx, dy) + min(dx, dy) * R2


def pt_seg(p, s, e):
    """(distance from point p to segment s-e, the nearest point of the segment)."""
    vx, vy = e[0] - s[0], e[1] - s[1]
    L2 = vx * vx + vy * vy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - s[0]) * vx + (p[1] - s[1]) * vy) / L2))
    q = (s[0] + t * vx, s[1] + t * vy)
    return math.hypot(p[0] - q[0], p[1] - q[1]), q


def seg_dist(a, b, c, d):
    """(shortest distance between segments ab and cd, the point of ab where it is reached)."""
    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    d1, d2, d3, d4 = cross(c, d, a), cross(c, d, b), cross(a, b, c), cross(a, b, d)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 != d2:
        t = d1 / (d1 - d2)
        return 0.0, (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
    best = (pt_seg(a, c, d)[0], a)
    x = (pt_seg(b, c, d)[0], b)
    if x[0] < best[0]:
        best = x
    for p in (c, d):
        dd, q = pt_seg(p, a, b)
        if dd < best[0]:
            best = (dd, q)
    return best


def in_rect(p, R, grow=0.0):
    return R[0] - grow <= p[0] <= R[2] + grow and R[1] - grow <= p[1] <= R[3] + grow


def seg_rect_dist(a, b, R):
    """Distance from segment ab to the filled rectangle R = (x0, y0, x1, y1); 0 when they touch."""
    if in_rect(a, R) or in_rect(b, R):
        return 0.0
    c = [(R[0], R[1]), (R[2], R[1]), (R[2], R[3]), (R[0], R[3])]
    return min(seg_dist(a, b, c[i], c[(i + 1) % 4])[0] for i in range(4))


def clip(a, c, R):
    """Parameter interval (t0, t1) of segment a-c inside rectangle R, or None."""
    t0, t1 = 0.0, 1.0
    for p, q in ((-(c[0] - a[0]), a[0] - R[0]), (c[0] - a[0], R[2] - a[0]), (-(c[1] - a[1]), a[1] - R[1]), (c[1] - a[1], R[3] - a[1])):
        if p == 0:
            if q < 0:
                return None
        elif p < 0:
            t0 = max(t0, q / p)
        else:
            t1 = min(t1, q / p)
    return (t0, t1) if t0 <= t1 else None


def in_poly(p, poly):
    x, y, inside = p[0], p[1], False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def seg_poly_dist(a, b, poly):
    """(distance from segment ab to the filled polygon, nearest point of ab)."""
    if in_poly(a, poly):
        return 0.0, a
    best = (1e9, a)
    for c, d in zip(poly, poly[1:] + poly[:1]):
        x = seg_dist(a, b, c, d)
        if x[0] < best[0]:
            best = x
    return best
