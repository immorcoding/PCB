"""Copper regions from a text sketch (PWR-3, PWR-4, PWR-7, PWR-8, PWR-9): check, write as zones, read back, measure.

    D:\\KiCad\\bin\\python.exe scripts\\cu_sketch.py check   <sketch> [--board <board>]
    D:\\KiCad\\bin\\python.exe scripts\\cu_sketch.py apply   <sketch> <board> [-o <board out>]
    D:\\KiCad\\bin\\python.exe scripts\\cu_sketch.py read    <board> [--sketch <old sketch>] [-o <sketch out>]
    D:\\KiCad\\bin\\python.exe scripts\\cu_sketch.py measure <board> [--refill] [--drc <report.json>] [--json <out.json>]

The shapes are drawn by a person; this tool never invents one (PWR-4). The sketch is the source (PWR-7):
`apply` redraws the zones from it, so after dragging a zone in KiCad run `read` first.

Sketch file (UTF-8, '#' starts a comment, mm, x to the right and y down as in KiCad):

    origin 100 100            # optional: board coordinate = sketch coordinate + origin (default 0 0)
    layers 6                  # copper layer count; needed when no board is given
    planes L2 L3 L5           # plane layers (default: every inner layer); the others are "outer"
    gap 0.5                   # plane layers: least distance between regions of different nets (PWR-8)
    clearance 0.2             # outer layers: the same, and the zone clearance written there
    plane_clearance 0.127     # zone clearance written on plane layers (fill to vias and pads of other nets)
    minwidth 0.2              # narrowest part a drawn region may have; also the zone's minimum width
    minedge 0.2               # shortest edge
    th_margin 0.3             # a region that touches a through-hole pad of its net covers pad + this (PWR-9)

    region <name> <net> <layer> [whole] [priority=N] [clearance=mm] [minwidth=mm] [islands=keep|remove]
      x,y  x,y  x,y ...       # vertices in order, closed automatically, any number of lines

The values above are the defaults. <layer> is L1..Ln (L1 = F.Cu, Ln = B.Cu) or a KiCad name (F.Cu, In2.Cu).

`whole` takes no vertices: the region is the board rectangle (bounding box of Edge.Cuts + 1 mm; KiCad clips
the fill at the board edge). On a plane layer every drawn region of another net on that layer is cut out of
it, grown by `gap`; the growing is done with an octagon and what is left is opened with an octagon of gap/2,
so all corners come out chamfered, every edge stays exactly on 0/45/90, and spikes and necks narrower than
`gap` are dropped. Leftover pieces under 1 mm2 are not written. At most one `whole` region per layer. On an
outer layer nothing is cut out: KiCad keeps the lower-priority pour `clearance` away from the drawn ones.

What `check` enforces (exact integer arithmetic in nm; any error = exit code 1):
  grid        every vertex on 0.001 mm
  angle       every edge at 0, 45 or 90 degrees (PWR-3)
  short-edge  no edge shorter than minedge
  self-cross  the outline is closed and simple: no two edges touch or cross
  acute       no 45 degree corner (inside or outside)
  narrow      width >= minwidth, where width is the shortest straight line through the inside between two
              edges that are not neighbours
  gap         drawn regions of different nets on one layer: >= gap on a plane layer (PWR-8), >= the larger
              of the two clearances on an outer layer
  whole       one `whole` region per layer, and something is left of it
with a board also:
  layer, net  the layer and the net exist
  outside     a drawn region lies inside the board outline
  th-pad      a through-hole pad of the region's net that the region touches is covered whole (PWR-9)
and as warnings (exit code stays 0): a drawn region with no pad or via of its net under it [unfed], pads of
other nets under an outer-layer region [foreign], a `whole` region that falls into several pieces [pieces],
a vertex on a straight line [straight].

Zones written by `apply` (only zones named `cu:<name>` or `cu-whole:<name>` are ever replaced; rule areas and
all other zones are left alone):
  priority        0 for `whole`, 1 for drawn
  clearance       `clearance` on outer layers, `plane_clearance` on plane layers
  minimum width   `minwidth`
  islands         `whole`: removed by KiCad (ISLAND_REMOVAL_MODE_ALWAYS, PWR-5); drawn: kept, so that a piece
                  nothing feeds shows up in `measure` and in DRC (isolated_copper) instead of disappearing
  pad connection  ZONE_CONNECTION_THT_THERMAL, thermal gap and spoke width left at KiCad's defaults. This is
                  only the fallback: a `zone_connection` rule in the board's .kicad_dru wins over the zone
                  setting (checked on KiCad 10.0.8 with thermal, solid and none on the zone), which is what
                  PWR-9 asks for. `apply` warns when the rule file has no such rule.
  fill            solid, no corner smoothing; the UUID is derived from the zone name
Applying an unchanged sketch does not write the board; the same sketch on the same board gives the same file.
When `apply` does write, it clears the saved fill of every copper zone on the board, hand-made ones too: the
fills are stale, and pcbnew gives a via or track that lies in the saved fill of another net that net as soon
as a board is loaded or saved (net propagation from pads), so stale fills must not stay in the file.
What KiCad does with islands (10.0.8): with `remove`, a piece with no pad of its net behind it goes if another
piece of the zone is connected; a zone whose pieces are all islands is kept and reported by DRC.

`read` writes the sketch of the zones on the board. With --sketch it updates that text: comments, order and
parameters stay, and only regions whose outline or settings changed on the board are rewritten. It lists
edges that are no longer on 0/45/90 (exit code 1) and `whole` zones whose outline was edited by hand.

`measure` reads the fills KiCad saved (kicad-cli pcb drc --refill-zones --save-board; --refill runs that and
so rewrites the board) and prints the copper group of the metrics table (docs/tools.md), as text and JSON:
per zone the edges, edges off the 45 degree grid, filled pieces, fragments (pieces beyond the first), pieces
that touch no pad, via or track end of their net, and the narrowest connection; per layer the smallest
distance between fills of different nets; the fill pieces on each plane layer; from the DRC report the
unconnected items on the nets that have zones. Narrowest connection: the widest strip w such that, with the
fill shrunk by w/2, every pad, via and track end it joins still hangs on one part; found by bisection to
0.003 mm, reported with the place where the fill parts and the anchors that let go. It is skipped for the
nets of --ground (shrinking a whole-board pour takes minutes), and anchors inside the rule areas named by
--skip-areas (BGA via fields) are left out.
"""
import argparse, collections, json, math, os, re, shutil, subprocess, sys, tempfile, time, uuid
from decimal import Decimal, InvalidOperation
from fractions import Fraction

DRAWN, WHOLE = "cu:", "cu-whole:"
GRID = 1000                                   # nm: vertices, gap and origin must be multiples of this
PARAMS = {"gap": 500000, "clearance": 200000, "plane_clearance": 127000, "minwidth": 200000,
          "minedge": 200000, "th_margin": 300000}
WHOLE_MARGIN = 1000000                        # the board rectangle of a `whole` region: edge bounding box + this
WHOLE_SNAP = 100000                           # ... snapped outward to this
MIN_PIECE = 10 ** 12                          # nm2 (1 mm2): smaller leftovers of a `whole` region are not written
UUID_NS = uuid.UUID("6f0c1d4e-5b1a-4c57-9d53-0c7a63b1c001")
KICAD_CLI = os.path.join(os.path.dirname(sys.executable), "kicad-cli.exe")
if not os.path.isfile(KICAD_CLI):
    KICAD_CLI = r"D:\KiCad\bin\kicad-cli.exe"


# ------------------------------------------------------------------------------------------- numbers and text

def to_nm(text):
    """Decimal mm text -> integer nm; ValueError when it is not a number or finer than 1 nm."""
    try:
        v = Decimal(text) * 1000000
    except InvalidOperation:
        raise ValueError("'%s' is not a number" % text)
    if not v.is_finite() or v != v.to_integral_value():
        raise ValueError("'%s' is not a number on the nm grid" % text)
    return int(v)


def fmt(nm):
    s = ("%d.%06d" % divmod(abs(nm), 1000000)).rstrip("0").rstrip(".")
    return ("-" if nm < 0 else "") + s


def fpt(p):
    return "(%s, %s)" % (fmt(p[0]), fmt(p[1]))


def ffrac(p):
    return "(%.3f, %.3f)" % (float(p[0]) / 1e6, float(p[1]) / 1e6)


# ------------------------------------------------------------------------------------------- exact geometry

def cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def on_seg(p, a, b):
    return cross(a, b, p) == 0 and min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])


def segs_touch(a, b, c, d):
    """True when segments ab and cd share at least one point."""
    d1, d2, d3, d4 = cross(c, d, a), cross(c, d, b), cross(a, b, c), cross(a, b, d)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    return on_seg(a, c, d) or on_seg(b, c, d) or on_seg(c, a, b) or on_seg(d, a, b)


def pt_seg(p, a, b):
    """(squared distance, closest point) from p to segment ab, as Fractions."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    t = Fraction((p[0] - a[0]) * dx + (p[1] - a[1]) * dy, l2) if l2 else Fraction(0)
    t = min(max(t, Fraction(0)), Fraction(1))
    q = (a[0] + t * dx, a[1] + t * dy)
    return (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2, q


def seg_seg(a, b, c, d):
    """(squared distance, [(point on ab, point on cd), ...]) for two segments that do not touch: every
    end-to-segment connection of that length (two of them when parallel stretches face each other)."""
    cands = []
    for p, (s, e), first in ((a, (c, d), True), (b, (c, d), True), (c, (a, b), False), (d, (a, b), False)):
        d2, q = pt_seg(p, s, e)
        cands.append((d2, (p, q) if first else (q, p)))
    best = min(c[0] for c in cands)
    return best, list({(Fraction(p[0]), Fraction(p[1]), Fraction(q[0]), Fraction(q[1])) for d2, (p, q) in cands if d2 == best})


def inside(p, contours):
    """1 inside, 0 on an edge, -1 outside (even-odd over all contours); exact for ints and Fractions."""
    n = 0
    for pts in contours:
        for i in range(len(pts)):
            a, b = pts[i - 1], pts[i]
            if cross(a, b, p) == 0 and min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]):
                return 0
            if (a[1] > p[1]) != (b[1] > p[1]):
                # x of the edge at height p.y, compared with p.x without dividing
                lhs = (p[0] - a[0]) * (b[1] - a[1])
                rhs = (p[1] - a[1]) * (b[0] - a[0])
                if (lhs < rhs) == (b[1] > a[1]):
                    n += 1
    return 1 if n % 2 else -1


def area2(pts):
    return sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))


def canonical(pts):
    """The same closed outline always as the same tuple: positive area, smallest vertex first."""
    pts = [tuple(p) for p in pts]
    pts = [p for i, p in enumerate(pts) if p != pts[i - 1]]
    if area2(pts) < 0:
        pts.reverse()
    k = pts.index(min(pts))
    return tuple(pts[k:] + pts[:k])


def canon_set(contours):
    return tuple(sorted(canonical(c) for c in contours))


def bbox(pts):
    return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)


def octilinear(a, b):
    dx, dy = abs(b[0] - a[0]), abs(b[1] - a[1])
    return dx == 0 or dy == 0 or dx == dy


def edges_of(contours):
    """[(a, b, contour index, edge index, edges in that contour)]"""
    return [(pts[i], pts[(i + 1) % len(pts)], ci, i, len(pts)) for ci, pts in enumerate(contours) for i in range(len(pts))]


def narrowest(contours, limit):
    """Narrowest width below `limit`, or None: (squared width, midpoint). Width = the shortest straight line
    through the inside between two edges that are not neighbours."""
    es = edges_of(contours)
    box = [(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])) for a, b, _, _, _ in es]
    best, lim2 = None, limit * limit
    for i in range(len(es)):
        a, b, ci, ei, n = es[i]
        for j in range(i + 1, len(es)):
            c, d, cj, ej, _ = es[j]
            if ci == cj and (ej - ei == 1 or ej - ei == n - 1):
                continue
            bi, bj = box[i], box[j]
            if bj[0] - bi[2] >= limit or bi[0] - bj[2] >= limit or bj[1] - bi[3] >= limit or bi[1] - bj[3] >= limit:
                continue
            if segs_touch(a, b, c, d):
                continue
            d2, cands = seg_seg(a, b, c, d)
            if d2 >= lim2 or (best and d2 >= best[0]):
                continue
            mid = (sum(k[0] + k[2] for k in cands) / (2 * len(cands)), sum(k[1] + k[3] for k in cands) / (2 * len(cands)))
            if inside(mid, contours) == 1:
                best = (d2, mid)
    return best


def poly_distance(P, Q):
    """(squared distance, point on P, point on Q) between two simple outlines; 0 when they touch or overlap."""
    for i in range(len(P)):
        for j in range(len(Q)):
            if segs_touch(P[i - 1], P[i], Q[j - 1], Q[j]):
                return Fraction(0), P[i], P[i]
    if inside(P[0], [Q]) >= 0:
        return Fraction(0), P[0], P[0]
    if inside(Q[0], [P]) >= 0:
        return Fraction(0), Q[0], Q[0]
    best = None
    for A, B, swap in ((P, Q, False), (Q, P, True)):
        for p in A:
            for j in range(len(B)):
                d2, q = pt_seg(p, B[j - 1], B[j])
                if best is None or d2 < best[0]:
                    best = (d2, q, p) if swap else (d2, p, q)
    return best


def hull(points):
    pts = sorted(set(points))

    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and cross(out[-2], out[-1], p) <= 0:
                out.pop()
            out.append(p)
        return out[:-1]
    return half(pts) + half(reversed(pts))


def octagon(g):
    """Vertices of the smallest octagon on the grid that contains the circle of radius g (0/45/90 edges)."""
    t = (g * 4142 // 10000) // GRID * GRID
    while (t + g) ** 2 < 2 * g * g:
        t += GRID
    return [(g, t), (t, g), (-t, g), (-g, t), (-g, -t), (-t, -g), (t, -g), (g, -t)]


# ------------------------------------------------------------------------------------------- the sketch

class Region:
    def __init__(self, name, net, layer, whole=False):
        self.name, self.net, self.layer, self.whole = name, net, layer, whole      # layer: copper number 1..n, or None
        self.pts, self.attrs = [], {}                                              # pts: sketch nm
        self.line, self.vlines = None, []

    def get(self, sk, key):
        """Effective value of priority / clearance / minwidth / islands."""
        if key in self.attrs:
            return self.attrs[key]
        if key == "priority":
            return 0 if self.whole else 1
        if key == "islands":
            return "remove" if self.whole else "keep"
        if key == "clearance":
            return sk.p["plane_clearance" if sk.is_plane(self.layer) else "clearance"]
        return sk.p["minwidth"]


class Sketch:
    def __init__(self):
        self.p = dict(PARAMS)
        self.origin, self.layers, self.planes = (0, 0), None, None
        self.regions, self.lines, self.problems = [], [], []
        self.stated = set()

    def is_plane(self, layer):
        if self.planes is not None:
            return layer in self.planes
        return layer is not None and self.layers is not None and 1 < layer < self.layers

    def err(self, code, region, text):
        self.problems.append(("ERROR", code, region, text))

    def warn(self, code, region, text):
        self.problems.append(("warning", code, region, text))

    def board_pts(self, r):
        return [(x + self.origin[0], y + self.origin[1]) for x, y in r.pts]


def layer_number(text, n):
    """'L3', 'In2.Cu', 'F.Cu', 'B.Cu' -> copper number; None when unknown (B.Cu needs the layer count n)."""
    m = re.fullmatch(r"L(\d+)", text)
    if m:
        return int(m.group(1)) or None
    m = re.fullmatch(r"In(\d+)\.Cu", text)
    if m:
        return int(m.group(1)) + 1
    return {"F.Cu": 1, "B.Cu": n}.get(text)


def parse(text, layers=None):
    """Sketch from text. `layers` (from a board) is used when the file does not state it."""
    sk = Sketch()
    sk.lines = text.splitlines()
    cur, pending = None, []
    for no, raw in enumerate(sk.lines):
        w = raw.split("#")[0].split()
        if not w:
            continue
        where = "line %d" % (no + 1)
        try:
            if w[0] == "region":
                pos = [t for t in w[1:] if "=" not in t and t != "whole"]
                if len(pos) != 3:
                    raise ValueError("expected: region <name> <net> <layer> [whole] [key=value ...]")
                cur = Region(pos[0], pos[1], pos[2], "whole" in w[1:])
                cur.line = no
                if not re.fullmatch(r"[A-Za-z0-9_.+\-]+", cur.name):
                    raise ValueError("region name '%s': use letters, digits and _ . + -" % cur.name)
                if any(r.name == cur.name for r in sk.regions):
                    raise ValueError("region name '%s' is used twice" % cur.name)
                sk.regions.append(cur)
                for t in w[1:]:
                    if "=" in t:
                        k, v = t.split("=", 1)
                        if k == "priority":
                            cur.attrs[k] = int(v)
                        elif k in ("clearance", "minwidth"):
                            cur.attrs[k] = to_nm(v)
                        elif k == "islands" and v in ("keep", "remove"):
                            cur.attrs[k] = v
                        else:
                            raise ValueError("unknown setting '%s'" % t)
            elif w[0] == "origin":
                sk.origin = (to_nm(w[1]), to_nm(w[2])); cur = None
            elif w[0] == "layers":
                sk.layers = int(w[1]); cur = None
            elif w[0] == "planes":
                pending.append((where, w[1:])); cur = None
            elif w[0] in PARAMS:
                sk.p[w[0]] = to_nm(w[1]); sk.stated.add(w[0]); cur = None
            elif "," in w[0] and cur is not None:
                for t in w:
                    x, y = t.split(",")
                    cur.pts.append((to_nm(x), to_nm(y)))
                cur.vlines.append(no)
            else:
                raise ValueError("cannot read '%s'" % raw.strip())
        except (ValueError, IndexError) as e:
            sk.err("syntax", where, str(e) if isinstance(e, ValueError) else "value missing")
    if sk.layers is None:
        sk.layers = layers
    elif layers is not None and layers != sk.layers:
        sk.err("layer", "-", "the sketch says %d copper layers, the board has %d" % (sk.layers, layers))
    for where, names in pending:
        nums = [layer_number(t, sk.layers) for t in names]
        if None in nums:
            sk.err("syntax", where, "planes: unknown layer among %s" % " ".join(names))
        sk.planes = set(n for n in nums if n)
    for r in sk.regions:
        name, r.layer = r.layer, layer_number(r.layer, sk.layers)
        if sk.layers is None:
            sk.err("layer", r.name, "copper layer count unknown: add a line `layers N` or give a board")
            r.layer = None
        elif r.layer is None or not 1 <= r.layer <= sk.layers:
            sk.err("layer", r.name, "no layer '%s' on a %d-layer board" % (name, sk.layers))
            r.layer = None
    for k in ("origin",) + tuple(PARAMS):
        vals = sk.origin if k == "origin" else (sk.p[k],)
        if any(v % GRID for v in vals) or (k != "origin" and vals[0] <= 0):
            sk.err("syntax", "-", "%s must be a positive multiple of 0.001 mm" % k if k != "origin" else "origin must be on the 0.001 mm grid")
    return sk


def lname(n):
    return "L%d" % n


def check_region(sk, r):
    """Shape checks of one drawn region; True when the outline is a simple polygon."""
    pts, n, bad = r.pts, len(r.pts), False
    if n < 3:
        sk.err("self-cross", r.name, "needs at least 3 vertices, has %d" % n)
        return False
    for p in pts:
        if p[0] % GRID or p[1] % GRID:
            sk.err("grid", r.name, "vertex %s is not on the 0.001 mm grid" % fpt(p))
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        if dx == 0 and dy == 0:
            sk.err("short-edge", r.name, "vertex %s is written twice in a row" % fpt(a)); bad = True
            continue
        if not octilinear(a, b):
            sk.err("angle", r.name, "edge %s -> %s is at %.1f degrees, not 0/45/90" % (
                fpt(a), fpt(b), math.degrees(math.atan2(abs(dy), abs(dx)))))
        if dx * dx + dy * dy < sk.p["minedge"] ** 2:
            sk.err("short-edge", r.name, "edge %s -> %s is %.3f mm long, below minedge %s" % (
                fpt(a), fpt(b), math.hypot(dx, dy) / 1e6, fmt(sk.p["minedge"])))
    if bad:
        return False
    simple = True
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        c = pts[(i + 2) % n]
        if cross(a, b, c) == 0:
            if (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]) < 0:
                sk.err("self-cross", r.name, "the outline doubles back on itself at %s" % fpt(b)); simple = False
            else:
                sk.warn("straight", r.name, "vertex %s lies on a straight line" % fpt(b))
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            c, d = pts[j], pts[(j + 1) % n]
            if segs_touch(a, b, c, d):
                sk.err("self-cross", r.name, "the outline crosses or touches itself: edge %s -> %s meets edge %s -> %s" % (
                    fpt(a), fpt(b), fpt(c), fpt(d)))
                simple = False
    if not simple:
        return False
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        if cross(a, b, c) != 0 and (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]) < 0:
            sk.err("acute", r.name, "corner at %s is sharper than 90 degrees" % fpt(b))
    w = r.get(sk, "minwidth")
    got = narrowest([pts], w)
    if got:
        sk.err("narrow", r.name, "%.3f mm wide at %s, below its minimum width %s" % (math.sqrt(got[0]) / 1e6, ffrac(got[1]), fmt(w)))
    return True


def check(sk, board=None):
    """Run every check; problems are appended to sk.problems. `board` is a BoardInfo or None."""
    ok = {}
    for r in sk.regions:
        if r.whole:
            if r.pts:
                sk.err("whole", r.name, "a `whole` region takes no vertices")
            continue
        ok[r.name] = check_region(sk, r)
    by_layer = collections.defaultdict(list)
    for r in sk.regions:
        if r.layer is not None:
            by_layer[r.layer].append(r)
    for layer, rs in sorted(by_layer.items()):
        wh = [r for r in rs if r.whole]
        if len(wh) > 1:
            sk.err("whole", wh[1].name, "%s already has the `whole` region %s" % (lname(layer), wh[0].name))
        drawn = [r for r in rs if not r.whole and ok.get(r.name)]
        for i in range(len(drawn)):
            for j in range(i + 1, len(drawn)):
                a, b = drawn[i], drawn[j]
                if a.net == b.net:
                    continue
                plane = sk.is_plane(layer)
                need = max(a.get(sk, "clearance"), b.get(sk, "clearance"), sk.p["gap"] if plane else 0)
                (ax0, ay0, ax1, ay1), (bx0, by0, bx1, by1) = bbox(a.pts), bbox(b.pts)
                if bx0 - ax1 >= need or ax0 - bx1 >= need or by0 - ay1 >= need or ay0 - by1 >= need:
                    continue
                d2, p, q = poly_distance(a.pts, b.pts)
                if d2 < need * need:
                    what = "overlap or touch at %s" % ffrac(p) if d2 == 0 else "are %.3f mm apart at %s" % (
                        math.sqrt(d2) / 1e6, ffrac(((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)))
                    sk.err("gap", a.name, "%s [%s] and %s [%s] on %s %s; %s is %s mm" % (
                        a.name, a.net, b.name, b.net, lname(layer), what, "the plane gap" if plane and need == sk.p["gap"] else "the clearance", fmt(need)))
    if board is not None:
        board.check(sk, ok)
    return sk.problems


def header(sk, r):
    out = "region %s %s %s" % (r.name, r.net, lname(r.layer) if r.layer else "?")
    if r.whole:
        out += " whole"
    for k in ("priority", "clearance", "minwidth", "islands"):
        if k in r.attrs:
            out += " %s=%s" % (k, fmt(r.attrs[k]) if k in ("clearance", "minwidth") else r.attrs[k])
    return out


def vertex_lines(r):
    return ["  " + "  ".join("%s,%s" % (fmt(x), fmt(y)) for x, y in r.pts[i:i + 6]) for i in range(0, len(r.pts), 6)]


# ------------------------------------------------------------------------------------------- the board

def _pcbnew():
    import pcbnew
    return pcbnew


def layer_id(n, count):
    pcbnew = _pcbnew()
    return pcbnew.F_Cu if n == 1 else pcbnew.B_Cu if n == count else getattr(pcbnew, "In%d_Cu" % (n - 1))


def chain(pts):
    pcbnew = _pcbnew()
    ch = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in pts:
        ch.Append(int(x), int(y))
    ch.SetClosed(True)
    return ch


def polyset(contours_list):
    """SHAPE_POLY_SET with one polygon per entry; an entry is [outline, hole, ...]."""
    ps = _pcbnew().SHAPE_POLY_SET()
    for contours in contours_list:
        ps.AddOutline(chain(contours[0]))
        for h in contours[1:]:
            ps.AddHole(chain(h))
    return ps


def chain_pts(ch):
    return [(ch.CPoint(i).x, ch.CPoint(i).y) for i in range(ch.PointCount())]


def polygons(ps):
    """[[outline, hole, ...], ...] of a SHAPE_POLY_SET, as point lists."""
    return [[chain_pts(ps.Outline(i))] + [chain_pts(ps.Hole(i, h)) for h in range(ps.HoleCount(i))] for i in range(ps.OutlineCount())]


def split(ps):
    """Each polygon of a SHAPE_POLY_SET as a SHAPE_POLY_SET of its own."""
    pcbnew, out = _pcbnew(), []
    for i in range(ps.OutlineCount()):
        one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(ps.Outline(i))
        for h in range(ps.HoleCount(i)):
            one.AddHole(ps.Hole(i, h))
        out.append(one)
    return out


def tool_zone(z):
    """(kind, region name, piece number) of a zone this tool wrote, else None."""
    if z.GetIsRuleArea():
        return None
    name = z.GetZoneName()
    if name.startswith(WHOLE):
        base, _, k = name[len(WHOLE):].partition("#")
        return "whole", base, int(k) if k.isdigit() else 1
    if name.startswith(DRAWN):
        return "drawn", name[len(DRAWN):], 1
    return None


class BoardInfo:
    """Everything the checks need from a board, read once (after BOARD.Remove() the collections are unusable)."""

    def __init__(self, path):
        pcbnew = _pcbnew()
        self.path = path
        self.b = b = pcbnew.LoadBoard(path)
        self.layers = b.GetCopperLayerCount()
        self.lid = {n: layer_id(n, self.layers) for n in range(1, self.layers + 1)}
        self.num = {v: k for k, v in self.lid.items()}
        self.outline = pcbnew.SHAPE_POLY_SET()
        self.has_outline = b.GetBoardPolygonOutlines(self.outline, False) and self.outline.OutlineCount() > 0
        bb = b.GetBoardEdgesBoundingBox()
        self.rect = None
        if bb.GetWidth() > 0 and bb.GetHeight() > 0:
            lo = lambda v: (v - WHOLE_MARGIN) // WHOLE_SNAP * WHOLE_SNAP
            hi = lambda v: -((-(v + WHOLE_MARGIN)) // WHOLE_SNAP * WHOLE_SNAP)
            self.rect = (lo(bb.GetLeft()), lo(bb.GetTop()), hi(bb.GetRight()), hi(bb.GetBottom()))
        self.pads = []
        for fp in b.GetFootprints():
            for p in fp.Pads():
                self.pads.append(("%s.%s" % (fp.GetReference(), p.GetNumber()), p.GetNetname(), bool(p.HasHole()), p))
        self.vias = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
        self.zones, self.copper_zones = [], []                # zones of this tool, in board order; all copper zones
        for z in b.Zones():
            if not z.GetIsRuleArea():
                self.copper_zones.append(z)
            tz = tool_zone(z)
            if tz:
                self.zones.append((tz, z))

    # --- what a `whole` region becomes -------------------------------------------------------------------

    def whole_polygons(self, sk, r):
        """[[outline, hole, ...], ...] in board nm for a `whole` region, pieces sorted; also the dropped count."""
        pcbnew = _pcbnew()
        x0, y0, x1, y1 = self.rect
        ps = polyset([[[(x0, y0), (x1, y0), (x1, y1), (x0, y1)]]])
        if sk.is_plane(r.layer):
            octa = octagon(sk.p["gap"])
            grown = pcbnew.SHAPE_POLY_SET()
            for o in sk.regions:
                if o.whole or o.layer != r.layer or o.net == r.net or len(o.pts) < 3:
                    continue
                pts = sk.board_pts(o)
                grown.BooleanAdd(polyset([[list(canonical(pts))]]))
                for i in range(len(pts)):
                    a, b = pts[i - 1], pts[i]
                    grown.BooleanAdd(polyset([[hull([(a[0] + ox, a[1] + oy) for ox, oy in octa] + [(b[0] + ox, b[1] + oy) for ox, oy in octa])]]))
            ps.BooleanSubtract(grown)
        if sk.is_plane(r.layer) and grown.OutlineCount():
            # open what is left by an octagon of gap/2: spikes and necks narrower than `gap` go, and the corners
            # that point into the copper come out chamfered like the ones around the blocks
            small = octagon(max(GRID, sk.p["gap"] // 2 // GRID * GRID))
            for grow in (False, True):
                band = pcbnew.SHAPE_POLY_SET()
                for c in polygons(ps):
                    for pts in c:
                        for i in range(len(pts)):
                            a, b = pts[i - 1], pts[i]
                            band.BooleanAdd(polyset([[hull([(a[0] + ox, a[1] + oy) for ox, oy in small] + [(b[0] + ox, b[1] + oy) for ox, oy in small])]]))
                ps.BooleanAdd(band) if grow else ps.BooleanSubtract(band)
        straight = lambda pts: [p for i, p in enumerate(pts) if cross(pts[i - 1], p, pts[(i + 1) % len(pts)]) != 0]
        polys = sorted(([straight(pts) for pts in c] for c in polygons(ps)), key=lambda c: min(c[0]))
        keep = [c for c in polys if abs(area2(c[0])) / 2 - sum(abs(area2(h)) / 2 for h in c[1:]) >= MIN_PIECE]
        return keep, len(polys) - len(keep)

    # --- checks that need the board ----------------------------------------------------------------------

    def check(self, sk, ok):
        pcbnew = _pcbnew()
        for r in sk.regions:
            if self.b.FindNet(r.net) is None:
                sk.err("net", r.name, "the board has no net '%s'" % r.net)
        if not self.has_outline:
            sk.warn("outside", "-", "the board has no closed outline: regions are not checked against it")
        for r in sk.regions:
            if r.layer is None or r.layer > self.layers:
                continue
            lid = self.lid[r.layer]
            if r.whole:
                if self.rect is None:
                    sk.err("whole", r.name, "the board has no Edge.Cuts to size a `whole` region from")
                    continue
                polys, dropped = self.whole_polygons(sk, r)
                off = sum(1 for c in polys for pts in c for i in range(len(pts)) if not octilinear(pts[i - 1], pts[i]))
                if off:
                    sk.err("angle", r.name, "internal: the derived outline has %d edges off 0/45/90" % off)
                if not polys:
                    sk.err("whole", r.name, "nothing is left of the board for this region")
                if len(polys) > 1 or dropped:
                    sk.warn("pieces", r.name, "falls into %d pieces (%s%s)%s" % (len(polys), ", ".join(
                        "%.1f mm2 from %s" % (abs(area2(c[0])) / 2e12, self.sk_pt(sk, min(c[0]))) for c in polys[:6]), " ..." if len(polys) > 6 else "",
                        "; %d leftover(s) under 1 mm2 not written" % dropped if dropped else ""))
                continue
            if not ok.get(r.name):
                continue
            pts = sk.board_pts(r)
            reg = polyset([[list(canonical(pts))]])
            if self.has_outline:
                out = pcbnew.SHAPE_POLY_SET(reg); out.BooleanSubtract(self.outline)
                if out.Area() > 1e9:                              # 0.001 mm2
                    bb = out.BBox()
                    sk.err("outside", r.name, "%.2f mm2 lies outside the board outline, around %s" % (
                        out.Area() / 1e12, self.sk_pt(sk, (bb.GetCenter().x, bb.GetCenter().y))))
            own, foreign = 0, []
            for label, net, th, p in self.pads:
                if not p.IsOnLayer(lid):
                    continue
                pos = p.GetPosition()
                if net != r.net:
                    if r.layer in (1, self.layers) and net and inside((pos.x, pos.y), [pts]) >= 0:
                        foreign.append("%s[%s]" % (label, net))
                    continue
                if th:
                    pad = pcbnew.SHAPE_POLY_SET()
                    p.TransformShapeToPolygon(pad, lid, sk.p["th_margin"], 5000, pcbnew.ERROR_OUTSIDE)
                    hit = pcbnew.SHAPE_POLY_SET(pad); hit.BooleanIntersection(reg)
                    if hit.Area() <= 1e8:
                        continue
                    own += 1
                    rest = pcbnew.SHAPE_POLY_SET(pad); rest.BooleanSubtract(reg)
                    if rest.Area() > 1e8:
                        sk.err("th-pad", r.name, "through-hole pad %s at %s is only partly covered (%.0f%% of pad + %s mm); cover it whole (PWR-9)" % (
                            label, self.sk_pt(sk, (pos.x, pos.y)), 100 * hit.Area() / pad.Area(), fmt(sk.p["th_margin"])))
                elif inside((pos.x, pos.y), [pts]) >= 0:
                    own += 1
            for v in self.vias:
                pos = v.GetPosition()
                if v.GetNetname() == r.net and v.IsOnLayer(lid) and inside((pos.x, pos.y), [pts]) >= 0:
                    own += 1
            if not own:
                sk.warn("unfed", r.name, "no pad or via of %s under it on %s" % (r.net, lname(r.layer)))
            if foreign:
                sk.warn("foreign", r.name, "pads of other nets under it: %s%s" % (" ".join(foreign[:8]), " ..." if len(foreign) > 8 else ""))

    def sk_pt(self, sk, p):
        return "(%.3f, %.3f)" % ((p[0] - sk.origin[0]) / 1e6, (p[1] - sk.origin[1]) / 1e6)

    # --- zones ------------------------------------------------------------------------------------------

    def wanted(self, sk):
        """The zones the sketch asks for, in order: dicts with every setting this tool controls."""
        out = []
        for r in sk.regions:
            if r.whole:
                polys, _ = self.whole_polygons(sk, r)
                names = [WHOLE + r.name] if len(polys) == 1 else ["%s%s#%d" % (WHOLE, r.name, k + 1) for k in range(len(polys))]
            else:
                polys, names = [[list(canonical(sk.board_pts(r)))]], [DRAWN + r.name]
            for name, contours in zip(names, polys):
                out.append({"name": name, "net": r.net, "layer": r.layer, "priority": r.get(sk, "priority"),
                            "clearance": r.get(sk, "clearance"), "minwidth": r.get(sk, "minwidth"),
                            "islands": r.get(sk, "islands"), "contours": canon_set(contours)})
        return out

    def existing(self):
        pcbnew, out = _pcbnew(), []
        for _tz, z in self.zones:
            polys = polygons(z.Outline())
            out.append({"name": z.GetZoneName(), "net": z.GetNetname(), "layer": self.num.get(z.GetLayer()),
                        "priority": z.GetAssignedPriority(), "clearance": z.GetLocalClearance(), "minwidth": z.GetMinThickness(),
                        "islands": "remove" if z.GetIslandRemovalMode() == pcbnew.ISLAND_REMOVAL_MODE_ALWAYS else "keep",
                        "contours": canon_set([c for poly in polys for c in poly]),
                        "_conn": z.GetPadConnection(), "_polys": len(polys)})
        return out

    def apply(self, sk, out_path):
        """Replace this tool's zones by the sketch's. Returns (written, text)."""
        pcbnew = _pcbnew()
        want, have = self.wanted(sk), self.existing()
        have = {h["name"]: h for h in have} if len(set(h["name"] for h in have)) == len(have) else {}
        same = len(want) == len(have) and all(
            w["name"] in have and have[w["name"]]["_conn"] == pcbnew.ZONE_CONNECTION_THT_THERMAL and have[w["name"]]["_polys"] == 1
            and all(have[w["name"]][k] == w[k] for k in w) for w in want)
        if same and os.path.abspath(out_path) == os.path.abspath(self.path):
            return False, "unchanged: the %d zones on the board already match the sketch" % len(want)
        b = self.b
        nets = {w["net"]: b.FindNet(w["net"]) for w in want}
        old = [z for _tz, z in self.zones]
        for z in self.copper_zones:                             # every saved fill is stale now, see the module text
            z.UnFill()
        for z in old:                                           # nothing is read from the board after this
            b.Remove(z)
        for w in want:
            z = pcbnew.ZONE(b)
            z.SetZoneName(w["name"]); z.SetLayer(self.lid[w["layer"]]); z.SetNet(nets[w["net"]])
            z.SetAssignedPriority(w["priority"]); z.SetLocalClearance(w["clearance"]); z.SetMinThickness(w["minwidth"])
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS if w["islands"] == "remove" else pcbnew.ISLAND_REMOVAL_MODE_NEVER)
            z.SetFillMode(pcbnew.ZONE_FILL_MODE_POLYGONS); z.SetCornerSmoothingType(pcbnew.ZONE_SETTINGS.CORNER_SMOOTHING_NO_SMOOTHING)
            o = z.Outline(); o.RemoveAllContours()
            cs = sorted(w["contours"], key=lambda c: -abs(area2(c)))       # the outline is the largest contour
            o.AddOutline(chain(cs[0]))
            for h in cs[1:]:
                o.AddHole(chain(h))
            z.SetUuid(pcbnew.KIID(str(uuid.uuid5(UUID_NS, w["name"]))))
            z.SetIsFilled(False)
            b.Add(z)
        src, dst = os.path.splitext(os.path.abspath(self.path))[0], os.path.splitext(os.path.abspath(out_path))[0]
        had = {ext: os.path.isfile(dst + ext) for ext in (".kicad_pro", ".kicad_dru")}
        pcbnew.SaveBoard(out_path, b)
        if src != dst:                                          # SaveBoard writes a default .kicad_pro next to a new board
            for ext, was in had.items():
                if not was and os.path.isfile(src + ext):
                    shutil.copy(src + ext, dst + ext)
        return True, "%d zones written to %s (%d of this tool's zones replaced); the fills of all %d zones on the board are cleared, refill with `measure --refill`" % (
            len(want), out_path, len(old), len(self.copper_zones) - len(old) + len(want))


def rule_file_decides(board_path):
    p = os.path.splitext(board_path)[0] + ".kicad_dru"
    if not os.path.isfile(p):
        return False
    text = "\n".join(l for l in open(p, encoding="utf-8", errors="replace").read().splitlines() if not l.lstrip().startswith("#"))
    return "zone_connection" in text


def kicad_open(board_path):
    d = os.path.dirname(os.path.abspath(board_path))
    return any(f.startswith("~") and f.endswith(".lck") for f in os.listdir(d))


# ------------------------------------------------------------------------------------------- read back

def read_board(board, old=None):
    """(sketch text, notes, off-grid edge count) from this tool's zones on the board. `old` is the sketch to
    update (its lines, comments, order and parameters are kept), or None."""
    sk = old if old is not None else Sketch()
    if sk.layers is None:
        sk.layers = board.layers
    new, notes, off_total = Sketch(), [], 0
    new.p, new.origin, new.layers, new.planes = sk.p, sk.origin, sk.layers, sk.planes
    seen, actual = {}, {}
    pcbnew = _pcbnew()
    for (kind, name, k), z in board.zones:
        polys = polygons(z.Outline())
        contours = [c for poly in polys for c in poly]
        off = [(c[i - 1], c[i]) for c in contours for i in range(len(c)) if not octilinear(c[i - 1], c[i])]
        if off:
            off_total += len(off)
            notes.append("OFF GRID %s: %d edge(s) no longer on 0/45/90: %s" % (z.GetZoneName(), len(off), "; ".join(
                "%s -> %s" % (board.sk_pt(sk, a), board.sk_pt(sk, b)) for a, b in off[:6]) + (" ..." if len(off) > 6 else "")))
        if name in seen:
            if kind == "whole" and seen[name].whole:
                actual[name] += contours
            else:
                notes.append("%s: a second zone with this region name is ignored" % z.GetZoneName())
            continue
        r = Region(name, z.GetNetname(), board.num.get(z.GetLayer()), kind == "whole")
        seen[name] = r; actual[name] = list(contours)
        if kind == "drawn":
            if len(contours) > 1:
                notes.append("%s: has %d cut-outs or extra outlines; a drawn region is one outline, only the first is read" % (z.GetZoneName(), len(contours) - 1))
            r.pts = [(x - sk.origin[0], y - sk.origin[1]) for x, y in polys[0][0]] if polys else []
            r.pts = [p for i, p in enumerate(r.pts) if p != r.pts[i - 1]]
        vals = {"priority": z.GetAssignedPriority(), "clearance": z.GetLocalClearance() or 0, "minwidth": z.GetMinThickness(),
                "islands": "remove" if z.GetIslandRemovalMode() == pcbnew.ISLAND_REMOVAL_MODE_ALWAYS else "keep"}
        r.attrs = {k2: v for k2, v in vals.items() if v != r.get(new, k2)}
        new.regions.append(r)
    for r in new.regions:                                        # was a derived outline edited by hand?
        if r.whole and board.rect is not None and r.layer:
            polys, _ = board.whole_polygons(new, r)
            if canon_set([c for poly in polys for c in poly]) != canon_set(actual[r.name]):
                notes.append("%s%s: its outline is not what the sketch derives (edited in KiCad, or the regions around it moved); `apply` will redraw it" % (WHOLE, r.name))
    by_name = {r.name: r for r in new.regions}
    out = []
    if old is None:
        out += ["# Copper region sketch, read back from %s by scripts/cu_sketch.py (format: see that script)." % os.path.basename(board.path),
                "layers %d" % board.layers] + ["%s %s" % (k, fmt(v)) for k, v in new.p.items()] + [""]
        todo = new.regions
    else:
        skip, repl = set(), {}
        for o in old.regions:
            r = by_name.get(o.name)
            if r is None:
                notes.append("%s: in the sketch but not on the board; kept as written" % o.name)
                continue
            same_head = (o.net, o.layer, o.whole) == (r.net, r.layer, r.whole) and all(
                o.get(old, k) == r.get(new, k) for k in ("priority", "clearance", "minwidth", "islands"))
            if not same_head:
                repl[o.line] = [header(new, r)]
                notes.append("%s: settings changed on the board" % o.name)
            if r.whole or (len(o.pts) >= 3 and len(r.pts) >= 3 and canonical(o.pts) == canonical(r.pts)):
                if r.whole and o.vlines:
                    skip.update(o.vlines)
                continue
            notes.append("%s: outline changed on the board (%d -> %d vertices)" % (o.name, len(o.pts), len(r.pts)))
            if o.vlines:
                repl[o.vlines[0]] = vertex_lines(r); skip.update(o.vlines[1:])
            else:
                repl[o.line] = repl.get(o.line, [old.lines[o.line]]) + vertex_lines(r)
        for no, line in enumerate(old.lines):
            if no in repl:
                out += repl[no]
            elif no not in skip:
                out.append(line)
        names = set(o.name for o in old.regions)
        todo = [r for r in new.regions if r.name not in names]
        for r in todo:
            notes.append("%s: on the board but not in the sketch; added at the end" % r.name)
    for r in todo:
        out += ([""] if out and out[-1].strip() else []) + [header(new, r)] + ([] if r.whole else vertex_lines(r))
    return "\n".join(out) + "\n", notes, off_total


# ------------------------------------------------------------------------------------------- measure

def run_drc(board_path, report):
    """Refill, save the board and write the JSON DRC report (PWR-6: connectivity is what KiCad's own fill says)."""
    subprocess.run([KICAD_CLI, "pcb", "drc", "--refill-zones", "--save-board", "--severity-all", "--units", "mm",
                    "--format", "json", "-o", report, board_path], capture_output=True)
    if not os.path.isfile(report):
        raise RuntimeError("kicad-cli wrote no DRC report for " + board_path)


class EdgeGrid:
    """Edges of a fill in square cells, for nearest-edge queries within one cell size."""

    def __init__(self, contours, cell):
        self.cell, self.cells, self.pts = cell, collections.defaultdict(list), []
        x0 = y0 = float("inf"); x1 = y1 = float("-inf")
        for pts in contours:
            for i in range(len(pts)):
                a, b = pts[i - 1], pts[i]
                self.pts.append(b)
                x0, y0, x1, y1 = min(x0, b[0]), min(y0, b[1]), max(x1, b[0]), max(y1, b[1])
                for cx in range(min(a[0], b[0]) // cell, max(a[0], b[0]) // cell + 1):
                    for cy in range(min(a[1], b[1]) // cell, max(a[1], b[1]) // cell + 1):
                        self.cells[(cx, cy)].append((a[0], a[1], b[0], b[1]))
        self.box = (x0, y0, x1, y1)

    def nearest(self, p, best):
        """(distance, point on an edge) closer than `best` to p, or None."""
        cx, cy, got = p[0] // self.cell, p[1] // self.cell, None
        for ix in (cx - 1, cx, cx + 1):
            for iy in (cy - 1, cy, cy + 1):
                for ax, ay, bx, by in self.cells.get((ix, iy), ()):
                    dx, dy = bx - ax, by - ay
                    l2 = dx * dx + dy * dy
                    t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / l2 if l2 else 0.0
                    t = 0.0 if t < 0 else 1.0 if t > 1 else t
                    qx, qy = ax + t * dx, ay + t * dy
                    d = math.hypot(p[0] - qx, p[1] - qy)
                    if d < best:
                        best, got = d, (d, (qx, qy))
        return got


def fill_distance(A, B, limit):
    """Smallest distance (nm) between two fills that do not overlap, with its midpoint; None beyond `limit`."""
    best, where = limit, None
    for P, Q in ((A, B), (B, A)):
        x0, y0, x1, y1 = Q.box
        for p in P.pts:
            if p[0] < x0 - best or p[0] > x1 + best or p[1] < y0 - best or p[1] > y1 + best:
                continue
            got = Q.nearest(p, best)
            if got:
                best, where = got[0], ((p[0] + got[1][0]) / 2, (p[1] + got[1][1]) / 2)
    return (best, where) if where else None


def anchors_of(board, net, lid, skip_areas, pcbnew):
    """Copper of a net on a layer that a fill is meant to join: (point, reach nm, kind, label, in a skipped area)."""
    out = []

    def add(pos, reach, kind, label):
        pt = pcbnew.VECTOR2I(pos.x, pos.y)
        out.append((pt, int(reach), kind, label, any(a.Contains(pt) for a in skip_areas)))
    mm = lambda pos: "(%.2f, %.2f)" % (pos.x / 1e6, pos.y / 1e6)
    for t in board.GetTracks():
        if t.GetNetname() != net:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            if t.IsOnLayer(lid):
                add(t.GetPosition(), t.GetWidth(lid) / 2, "via", "via" + mm(t.GetPosition()))
        elif t.GetLayer() == lid:
            for pos in (t.GetStart(), t.GetEnd()):
                add(pos, t.GetWidth() / 2, "track", "track" + mm(pos))
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == net and p.IsOnLayer(lid):
                s = p.GetSize(lid)
                add(p.GetPosition(), min(s.x, s.y) / 2, "th" if p.HasHole() else "smd", "%s.%s" % (fp.GetReference(), p.GetNumber()))
    return out


def neck(piece, anchors, nmax, th_reach, pcbnew):
    """Narrowest connection of one filled piece: the widest strip w for which, after shrinking the fill by w/2,
    all anchors still hang on one part. Returns (mm or None, state, location, anchors that let go first)."""
    if len(anchors) < 2:
        return None, "fewer than 2 anchors", None, []
    ROUND, ERR, TOL = pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, 2000, 20000

    def groups(w):
        d = pcbnew.SHAPE_POLY_SET(piece)
        d.Deflate(int(w // 2), ROUND, ERR)
        subs = split(d)
        g = []
        for pt, reach, kind, _label, _skip in anchors:
            r = int(reach + w // 2 + TOL + (th_reach if kind == "th" else 0))
            g.append(set(k for k, s in enumerate(subs) if s.Collide(pt, r)))      # an anchor may touch several parts
        return g, d

    together = lambda w: bool(set.intersection(*groups(w)[0]))
    lo, hi = 20000, nmax
    if not together(lo):
        return 0.0, "below 0.02", None, []
    if together(hi):
        return round(nmax / 1e6, 3), "at least", None, []
    for _ in range(11):
        mid = (lo + hi) // 2
        lo, hi = (mid, hi) if together(mid) else (lo, mid)
    g, d = groups(hi)
    main = collections.Counter(k for ks in g for k in ks).most_common(1)
    main = main[0][0] if main else None
    gone = [a for a, ks in zip(anchors, g) if main not in ks]
    # where: the parts grown back one by one. Two of them meet again at a pinch (a hole near an edge);
    # across a strip with parallel sides they do not, and the strip itself is what the shrinking took away.
    comps = []
    for s in split(d):
        s.Inflate(int(hi // 2), ROUND, ERR)
        comps.append(s)
    centre = lambda ps: (round(ps.BBox().GetCenter().x / 1e6, 3), round(ps.BBox().GetCenter().y / 1e6, 3))
    where, best = None, 0
    for i in range(len(comps)):
        fat = pcbnew.SHAPE_POLY_SET(comps[i]); fat.Inflate(4000, ROUND, ERR)
        for k in range(i + 1, len(comps)):
            t = pcbnew.SHAPE_POLY_SET(fat); t.BooleanIntersection(comps[k])
            if t.OutlineCount() and (where is None or main in (i, k)):
                where = centre(t)
    if where is None:
        lost = pcbnew.SHAPE_POLY_SET(piece)
        for c in comps:
            lost.BooleanSubtract(c)
        for L in split(lost):
            fat = pcbnew.SHAPE_POLY_SET(L); fat.Inflate(4000, ROUND, ERR)
            touch = 0
            for c in comps:
                t = pcbnew.SHAPE_POLY_SET(fat); t.BooleanIntersection(c)
                touch += 1 if t.OutlineCount() else 0
            holds = any(L.Collide(a[0], a[1]) for a in gone)
            if (touch >= 2 or holds) and L.Area() > best:
                best, where = L.Area(), centre(L)
    return round((lo + hi) / 2e6, 3), "", where, [a[3] for a in gone][:6]


def measure(board_path, drc=None, all_zones=False, skip_areas=(), ground=("GND",), neck_max=5.0, gap_max=2.0, th_reach=0.6, nets=()):
    """The copper group of the metrics table, as a dict. Reads the fills saved in the board file."""
    pcbnew = _pcbnew()
    t0 = time.time()
    b = pcbnew.LoadBoard(board_path)
    count = b.GetCopperLayerCount()
    num = {layer_id(n, count): n for n in range(1, count + 1)}
    areas = [z.Outline() for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName() in skip_areas]
    cache, rows, per_layer = {}, [], collections.defaultdict(list)
    limit = int(gap_max * 1e6)
    for z in b.Zones():
        tz = tool_zone(z)
        if z.GetIsRuleArea() or (tz is None and not all_zones):
            continue
        lid, net = z.GetLayer(), z.GetNetname()
        contours = [c for poly in polygons(z.Outline()) for c in poly]
        edges = sum(len(c) for c in contours)
        off = sum(1 for c in contours for i in range(len(c)) if not octilinear(c[i - 1], c[i]))
        fill = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(lid))
        fill.Simplify()                                  # saved fills join holes to the outline by slits; Deflate would cut along them
        pieces = split(fill)
        if (net, lid) not in cache:
            cache[(net, lid)] = anchors_of(b, net, lid, areas, pcbnew)
        anc = cache[(net, lid)]
        on = [[a for a in anc if p.Collide(a[0], a[1])] for p in pieces]
        row = {"zone": z.GetZoneName(), "tool": tz is not None, "whole": bool(tz and tz[0] == "whole"), "net": net, "layer": lname(num[lid]),
               "priority": z.GetAssignedPriority(), "edges": edges, "off_grid_edges": off,
               "pieces": len(pieces), "fragments": max(0, len(pieces) - 1), "unconnected_pieces": sum(1 for a in on if not a),
               "area_mm2": round(fill.Area() / 1e12, 2), "anchors": sum(len(a) for a in on),
               "neck_mm": None, "neck_note": "", "neck_at": None, "neck_lets_go": []}
        if not z.IsFilled() or not pieces:
            row["neck_note"] = "not filled"
        elif net in ground:
            row["neck_note"] = "ground: not measured"
        else:
            for p, a in zip(pieces, on):
                use = [x for x in a if not x[4]]
                w, note, where, gone = neck(p, use, int(neck_max * 1e6), int(th_reach * 1e6), pcbnew)
                if w is not None and (row["neck_mm"] is None or w < row["neck_mm"]):
                    row.update(neck_mm=w, neck_note=note, neck_at=where, neck_lets_go=gone)
                elif w is None and row["neck_mm"] is None:
                    row["neck_note"] = note
        rows.append(row)
        if pieces:
            per_layer[lid].append((row, EdgeGrid([c for poly in polygons(fill) for c in poly], limit)))
    layers = {}
    for lid, zs in sorted(per_layer.items(), key=lambda kv: num[kv[0]]):
        best, pairs = None, []
        for i in range(len(zs)):
            for j in range(i + 1, len(zs)):
                (ra, ga), (rb, gb) = zs[i], zs[j]
                if ra["net"] == rb["net"]:
                    continue
                got = fill_distance(ga, gb, limit)
                if got:
                    item = {"mm": round(got[0] / 1e6, 4), "at": [round(got[1][0] / 1e6, 3), round(got[1][1] / 1e6, 3)],
                            "a": ra["zone"], "b": rb["zone"], "nets": [ra["net"], rb["net"]]}
                    pairs.append(item)
                    if best is None or item["mm"] < best["mm"]:
                        best = item
        n = num[lid]
        layers[lname(n)] = {"plane": 1 < n < count, "regions": len(zs), "pieces": sum(r["pieces"] for r, _ in zs),
                            "nets": sorted(set(r["net"] for r, _ in zs)), "min_gap": best, "gaps": pairs}
    rows.sort(key=lambda r: (int(r["layer"][1:]), r["zone"]))
    copper = sorted(set(r["net"] for r in rows) | set(nets))
    out = {"board": os.path.basename(board_path), "zones": rows, "layers": layers, "copper_nets": copper,
           "plane_blocks": {k: v["pieces"] for k, v in layers.items() if v["plane"]},
           "gap_limit_mm": gap_max, "neck_limit_mm": neck_max, "drc": None}
    if drc and os.path.isfile(drc):
        d = json.load(open(drc, encoding="utf-8"))
        un = collections.Counter()
        for it in d.get("unconnected_items", []):
            for n in set(re.findall(r"\[([^\]]+)\]", " ".join(i["description"] for i in it["items"]))) & set(copper):
                un[n] += 1
        out["drc"] = {"unconnected_total": len(d.get("unconnected_items", [])), "unconnected_copper": sum(un.values()),
                      "unconnected_by_net": dict(sorted(un.items())),
                      "violations": dict(sorted(collections.Counter(v["type"] for v in d.get("violations", [])).items()))}
    out["seconds"] = round(time.time() - t0, 1)
    return out


def measure_text(m):
    L = ["铜皮指标  %s" % m["board"],
         "%-4s %-22s %-10s %4s %6s %5s %4s %6s %9s  %-10s %s" % ("层", "铺铜区", "网络", "边数", "非45°边", "块数", "碎片", "未连接", "面积mm2", "最窄连接mm", "位置 / 先脱开的")]
    for r in m["zones"]:
        if r["neck_mm"] is None:
            nk = "- (%s)" % r["neck_note"] if r["neck_note"] else "-"
        elif r["neck_note"] == "below 0.02":
            nk = "<0.02"
        else:
            nk = (">=%.2f" if r["neck_note"] == "at least" else "%.3f") % r["neck_mm"]
        at = ("(%.2f, %.2f) " % tuple(r["neck_at"]) if r["neck_at"] else "") + " ".join(r["neck_lets_go"])
        L.append("%-4s %-24s %-10s %5d %7d %6d %5d %7d %10.2f  %-12s %s" % (
            r["layer"], r["zone"], r["net"], r["edges"], r["off_grid_edges"], r["pieces"], r["fragments"], r["unconnected_pieces"], r["area_mm2"], nk, at))
    L.append("不同网络最小距离（每层；%.1f mm 以外不找）:" % m["gap_limit_mm"])
    for name, v in m["layers"].items():
        g = v["min_gap"]
        L.append("  %-3s %s" % (name, "%.3f mm  %s | %s  at (%.2f, %.2f)" % (g["mm"], g["a"], g["b"], g["at"][0], g["at"][1]) if g else "-"))
    L.append("电源面块数: " + ("  ".join("%s %d" % kv for kv in m["plane_blocks"].items()) or "-"))
    L.append("合计: 铺铜区 %d，非45°边 %d，碎片 %d，未连接的碎片 %d" % (
        len(m["zones"]), sum(r["off_grid_edges"] for r in m["zones"]), sum(r["fragments"] for r in m["zones"]), sum(r["unconnected_pieces"] for r in m["zones"])))
    if m["drc"]:
        d = m["drc"]
        L.append("铜皮类未连接数 (DRC): %d  %s   (全板未连接 %d；孤立铜皮 isolated_copper %d，花焊盘不足 starved_thermal %d)" % (
            d["unconnected_copper"], " ".join("%s %d" % kv for kv in d["unconnected_by_net"].items()), d["unconnected_total"],
            d["violations"].get("isolated_copper", 0), d["violations"].get("starved_thermal", 0)))
    else:
        L.append("铜皮类未连接数 (DRC): 没有给 DRC 报告（--drc 或 --refill）")
    L.append("耗时 %.1f s" % m["seconds"])
    return "\n".join(L)


# ------------------------------------------------------------------------------------------- command line

def load_sketch(path, layers=None):
    return parse(open(path, encoding="utf-8").read(), layers)


def report(problems, title):
    errs = [p for p in problems if p[0] == "ERROR"]
    print("%s: %d error(s), %d warning(s)" % (title, len(errs), len(problems) - len(errs)))
    for level, code, region, text in sorted(problems, key=lambda p: p[0] != "ERROR"):
        print("  %-7s [%s] %s: %s" % (level, code, region, text))
    return len(errs)


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Copper regions from a text sketch: check, apply, read, measure.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("sketch"); c.add_argument("--board")
    a = sub.add_parser("apply"); a.add_argument("sketch"); a.add_argument("board"); a.add_argument("-o", "--out")
    r = sub.add_parser("read"); r.add_argument("board"); r.add_argument("--sketch"); r.add_argument("-o", "--out")
    m = sub.add_parser("measure"); m.add_argument("board")
    m.add_argument("--refill", action="store_true", help="run kicad-cli DRC with --refill-zones --save-board first (rewrites the board)")
    m.add_argument("--drc", help="JSON DRC report to count unconnected items from (written here with --refill)")
    m.add_argument("--json", help="write the numbers here as JSON")
    m.add_argument("--all-zones", action="store_true", help="also measure copper zones this tool did not write")
    m.add_argument("--skip-areas", default="", help="rule area names, comma separated: anchors inside are left out of the narrowest connection (BGA via fields)")
    m.add_argument("--ground", default="GND", help="nets whose pours are not shrunk for the narrowest connection (default GND)")
    m.add_argument("--nets", default="", help="more copper-class nets to count unconnected items for")
    m.add_argument("--neck-max", type=float, default=5.0); m.add_argument("--gap-max", type=float, default=2.0)
    m.add_argument("--th-reach", type=float, default=0.6, help="copper this far (mm) from a through-hole pad counts as joined to it (thermal gap)")
    args = ap.parse_args(argv)
    if args.cmd == "check":
        board = BoardInfo(args.board) if args.board else None
        sk = load_sketch(args.sketch, board.layers if board else None)
        return 1 if report(check(sk, board), "cu_sketch check %s" % args.sketch) else 0
    if args.cmd == "apply":
        board = BoardInfo(args.board)
        sk = load_sketch(args.sketch, board.layers)
        if report(check(sk, board), "cu_sketch check %s" % args.sketch):
            print("SKETCH REJECTED, nothing written")
            return 1
        out = args.out or args.board
        if kicad_open(out):
            print("warning: a ~*.lck file next to %s: KiCad has the project open; reload the board there (File > Revert)" % out)
        if not rule_file_decides(args.board):
            print("warning: no zone_connection rule in the board's .kicad_dru: pads connect by the zone fallback (through-hole thermal, SMD solid, KiCad's default gap and spoke)")
        _written, text = board.apply(sk, out)
        print(text)
        return 0
    if args.cmd == "read":
        board = BoardInfo(args.board)
        old = load_sketch(args.sketch, board.layers) if args.sketch else None
        text, notes, off = read_board(board, old)
        if args.out:
            open(args.out, "w", encoding="utf-8", newline="\n").write(text)
        else:
            sys.stdout.write(text)
        for n in notes:
            print(n, file=sys.stderr)
        print("%d region(s) read from %s; %d edge(s) off 0/45/90" % (len(set(tz[1] for tz, _ in board.zones)), args.board, off), file=sys.stderr)
        return 1 if off else 0
    drc, tmp = args.drc, None
    if args.refill:
        if not drc:
            tmp = tempfile.mkdtemp(prefix="cu_sketch_"); drc = os.path.join(tmp, "drc.json")
        run_drc(args.board, drc)
    try:
        csv = lambda s: tuple(x for x in s.split(",") if x)
        res = measure(args.board, drc, args.all_zones, csv(args.skip_areas), csv(args.ground), args.neck_max, args.gap_max, args.th_reach, csv(args.nets))
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    if args.json:
        json.dump(res, open(args.json, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(measure_text(res))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
