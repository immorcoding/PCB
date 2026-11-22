"""Checks without KiCad: the fast loop. DRC in the full build stays the authority.

Scene     every piece of copper as an item (track segment, round pad or via, polygon pad) in a grid index,
          with the clearance of the place: `clr_area` when either object touches a rule area (as the
          project's bga_clearance rule: intersectsArea on either side), else the larger net-class clearance.
geometry  the group's new copper against everything else and against itself.

Finding kinds (HARD ones fail a build; SHAPE_KINDS are only reported in sketch mode):
  CROSS    two nets cross on one layer              GAP    copper closer than the clearance of the place
  HOLE     a hole too close to copper or a hole     VIAPAD a via on a pad (ball pads take no via)
  PATH     not one pad-to-pad line                  VIAS   more vias than the limit
  LEN      longer than the limit                    EDGE   too close to the board edge
  KEEPOUT  inside a keep-out area                   ZONE   a track through another net's pour
  ORDER, PITCH, FAN, SLOT, CHANNEL                  from the generators (bundle.py, fanout.py)
  TUNE     a net that does not reach its length target (missing mm), a site off its route   (tune.py)
  SHAPE, CORNER, SHARP, ARC                         0/45/90, shortest segment, corners (design-rules.md);
                                                    serpentine arcs: tangency, radius, pieces, heights, clr (tune.py)
  VIATURN, OPEN, NOTE                               listed, never fail a build
"""
import math
from .geom import seg_dist, pt_seg, seg_rect_dist, seg_poly_dist, in_poly
from .routes import F

SHAPE_KINDS = ("SHAPE", "CORNER", "SHARP", "ARC")
NOTES = ("VIATURN", "OPEN", "NOTE")
CELL = 1.0


def is_hard(f, sketch=False):
    return f["kind"] not in NOTES and not (sketch and f["kind"] in SHAPE_KINDS)


class Item:
    __slots__ = ("kind", "net", "layer", "a", "b", "r", "hole", "pth", "poly", "area", "desc", "new", "box", "pad")

    def __init__(self, kind, net, layer, a, b, r, desc, hole=0.0, pth=False, poly=None, new=False, pad=None):
        self.kind, self.net, self.layer, self.a, self.b, self.r, self.desc = kind, net or None, layer, a, b, r, desc
        self.hole, self.pth, self.poly, self.new, self.pad, self.area = hole, pth, poly, new, pad, False
        if poly:
            xs, ys = [p[0] for p in poly], [p[1] for p in poly]
            self.box = (min(xs), min(ys), max(xs), max(ys))
        else:
            self.box = (min(a[0], b[0]) - r, min(a[1], b[1]) - r, max(a[0], b[0]) + r, max(a[1], b[1]) + r)


def _dist(a, b):
    """(distance between the centre geometries of two items, a point where it is reached)."""
    if a.kind == "poly" and b.kind == "poly":
        return min((seg_poly_dist(p, q, b.poly) for p, q in zip(a.poly, a.poly[1:] + a.poly[:1])), key=lambda x: x[0])
    if a.kind == "poly":
        d, q = seg_poly_dist(b.a, b.b, a.poly)
        return d, q
    if b.kind == "poly":
        return seg_poly_dist(a.a, a.b, b.poly)
    if a.kind == "round" and b.kind == "round":
        return math.dist(a.a, b.a), a.a
    if a.kind == "round":
        d, q = pt_seg(a.a, b.a, b.b)
        return d, q
    if b.kind == "round":
        return pt_seg(b.a, a.a, a.b)
    return seg_dist(a.a, a.b, b.a, b.b)


class Scene:
    def __init__(self, board, profile, skip_nets=(), skip_items=None):
        self.board, self.profile = board, profile
        self.areas = board.rule_areas(profile.area_names)
        self.items, self.grid = [], {}
        skip = set(skip_nets)
        segs_old, vias_old = skip_items or (set(), set())       # a shared group's own copper of last time
        r6 = lambda v: round(v, 6)
        for p in board.all_pads():                          # shield tabs that share one number are obstacles too
            layer = None if p.layers is None else (next(iter(p.layers)) if len(p.layers) == 1 else None)
            if p.shape == "circle":
                self.add(Item("round", p.net, layer, p.pos, p.pos, p.r, "pad " + p.name, hole=p.hole, pth=p.hole > 0, pad=p))
            else:
                self.add(Item("poly", p.net, layer, p.pos, p.pos, 0.0, "pad " + p.name, hole=p.hole, pth=p.hole > 0, poly=p.poly, pad=p))
        for n, lay, a, c, w, _ in board.tracks:
            if n not in skip and (n, board.cu[lay], r6(a[0]), r6(a[1]), r6(c[0]), r6(c[1])) not in segs_old:
                self.add(self.seg(n, lay, a, c, w, False))
        for n, p, d, h in board.vias:
            if n not in skip and (n, r6(p[0]), r6(p[1])) not in vias_old:
                self.add(self.via(n, p, d, h, False))

    def seg(self, net, layer, a, c, w, new=True):
        return Item("seg", net, layer, a, c, w / 2, "track of %s on %s" % (net, layer), new=new)

    def via(self, net, p, d, h, new=True):
        return Item("round", net, None, p, p, d / 2, "via of %s" % net, hole=h / 2, new=new)

    def add(self, it):
        if it.kind == "seg":
            it.area = any(seg_rect_dist(it.a, it.b, R) <= it.r + 1e-9 for R in self.areas.values())
        elif it.kind == "round":
            it.area = any(seg_rect_dist(it.a, it.a, R) <= it.r + 1e-9 for R in self.areas.values())
        else:
            it.area = any(it.box[0] <= R[2] and R[0] <= it.box[2] and it.box[1] <= R[3] and R[1] <= it.box[3] for R in self.areas.values())
        k = len(self.items)
        self.items.append(it)
        for cx in range(int(math.floor(it.box[0] / CELL)), int(math.floor(it.box[2] / CELL)) + 1):
            for cy in range(int(math.floor(it.box[1] / CELL)), int(math.floor(it.box[3] / CELL)) + 1):
                self.grid.setdefault((cx, cy), []).append(k)
        return k

    def near(self, it, margin=0.6):
        seen = set()
        b = it.box
        for cx in range(int(math.floor((b[0] - margin) / CELL)), int(math.floor((b[2] + margin) / CELL)) + 1):
            for cy in range(int(math.floor((b[1] - margin) / CELL)), int(math.floor((b[3] + margin) / CELL)) + 1):
                for k in self.grid.get((cx, cy), ()):
                    if k not in seen:
                        seen.add(k)
                        o = self.items[k]
                        if o is not it and o.box[0] <= b[2] + margin and b[0] <= o.box[2] + margin and o.box[1] <= b[3] + margin and b[1] <= o.box[3] + margin:
                            yield o

    def need(self, a, b):
        if a.area or b.area:
            return self.profile.clr_area
        return max(self.profile.clr(a.net), self.profile.clr(b.net))

    def pair(self, a, b):
        """Every clearance problem between two items: [(kind, gap, need, point)]."""
        if a.net is not None and a.net == b.net:
            return []
        out = []
        d, q = _dist(a, b)
        if a.layer is None or b.layer is None or a.layer == b.layer:
            gap, need = d - a.r - b.r, self.need(a, b)
            if d < 1e-9 and a.kind == "seg" and b.kind == "seg":
                out.append(("CROSS", 0.0, need, q))
            elif gap < need - 1e-6:
                out.append(("GAP", gap, need, q))
        for h, o in ((a, b), (b, a)):
            if h.hole <= 0:
                continue
            if o.kind == "seg":
                dd, qq = pt_seg(h.a, o.a, o.b)
            elif o.kind == "round":
                dd, qq = math.dist(h.a, o.a), h.a
            else:
                dd, qq = seg_poly_dist(h.a, h.a, o.poly)
            need = self.profile.pth_hole_clr if h.pth else self.profile.hole_clr
            if dd - h.hole - o.r < need - 1e-6:
                out.append(("HOLE", dd - h.hole - o.r, need, qq))
            if o.hole > 0 and h is a and dd - h.hole - o.hole < self.profile.hole_hole - 1e-6:
                out.append(("HOLE2", dd - h.hole - o.hole, self.profile.hole_hole, qq))
        return out

    def conflict(self, items, ignore=()):
        """First problem of candidate items (not in the scene) against the scene: text, or None."""
        for it in items:
            for o in self.near(it):
                if o in ignore:
                    continue
                for kind, gap, need, q in self.pair(it, o):
                    return "%s (%.3f, %.3f)" % (describe(kind, it, o, gap, need), q[0], q[1])
        return None


def describe(kind, a, b, gap, need):
    who = b.desc if b.net or b.pad is None else b.desc + " (no net)"
    if kind == "CROSS":
        return "crosses the %s at" % who
    if kind == "GAP":
        return ("overlaps the %s by %.4f mm (needs %.3f clear) at" % (who, -gap, need)) if gap < 0 else "%.4f mm from the %s, %.3f needed: %.4f missing at" % (gap, who, need, need - gap)
    if kind == "HOLE":
        hole, cu = (a, b) if a.hole > 0 and not (b.hole > 0 and b.kind == "round" and a.kind != "round") else (b, a)
        return "hole to copper %.4f mm (%s / %s), %.3f needed: %.4f missing at" % (gap, a.desc, who, need, need - gap)
    return "hole to hole %.4f mm against the %s, %.3f needed: %.4f missing at" % (gap, who, need, need - gap)


def geometry(board, profile, resolved, segs, vias, opts=None, arcs=()):
    """Findings of the group's copper: clearances, crossings, holes, vias on pads, board edge, keep-outs, pours,
    via count and length limits. `opts`: via_limit, via_target, len_max, yield_nets, allow_via_on. `arcs` (the
    serpentines of tune.py) are checked as chords, their half width grown by the largest sagitta."""
    opts = opts or {}
    finds = []
    owned = set() if opts.get("shared") else set(resolved)
    sc = Scene(board, profile, skip_nets=owned, skip_items=opts.get("skip_items"))
    new = [sc.seg(n, lay, a, c, w) for n, lay, a, c, w in segs] + [sc.via(n, p, d, h) for n, p, d, h, _ in vias]
    if arcs:
        from .tune import chords
        for n, lay, s, m, e, w in arcs:
            cs, sag = chords(s, m, e)
            new += [Item("seg", n, lay, a, c, w / 2 + sag, "arc of %s on %s" % (n, lay), new=True) for a, c in cs]
    for it in new:
        sc.add(it)
    order = {id(it): k for k, it in enumerate(new)}
    worst, crosses = {}, {}
    for it in new:
        for o in sc.near(it):
            if o.new and order[id(o)] < order[id(it)]:
                continue
            for kind, gap, need, q in sc.pair(it, o):
                if kind == "CROSS":
                    crosses[(tuple(sorted((it.net, o.net))), it.layer, round(q[0], 3), round(q[1], 3))] = (it, o, q)
                else:
                    k = (kind, it.net, o.net or o.desc, it.layer or o.layer)
                    if k not in worst or gap < worst[k][0]:
                        worst[k] = (gap, need, q, it, o)
    for (nets, layer, _, _), (it, o, q) in sorted(crosses.items(), key=lambda kv: (kv[0][1], kv[0][0], kv[0][2], kv[0][3])):
        finds.append(F("CROSS", "%s and %s cross on %s at (%.3f, %.3f)" % (nets[0], nets[1], layer, q[0], q[1]), it.net, q, other=o.net, layer=layer))
    for k in sorted(worst, key=lambda k: (worst[k][0], str(k))):
        gap, need, q, it, o = worst[k]
        kind = "HOLE" if k[0].startswith("HOLE") else "GAP"
        finds.append(F(kind, "%s: %s %s (%.3f, %.3f)" % (it.net, it.desc.split(" of ")[0], describe(k[0], it, o, gap, need), q[0], q[1]), it.net, q,
                       other=o.net or o.desc, layer=k[3], gap=round(gap, 4), need=need))
    allow = set(opts.get("allow_via_on", ()))
    for it in new:
        if it.kind == "round":                              # a via: never on a pad
            for o in sc.near(it, 0.1):
                if o.pad is None or not o.pad.smd or o.pad.name in allow:
                    continue
                d = math.dist(it.a, o.a) - o.r if o.kind == "round" else seg_poly_dist(it.a, it.a, o.poly)[0]
                if d < 0 or (o.net == it.net and d < it.r):
                    what = "is on" if d < 0 else "overlaps"
                    finds.append(F("VIAPAD", "%s: the via at (%.4f, %.4f) %s pad %s (pads take no via: move it to the centre of four balls)" % (
                        it.net, it.a[0], it.a[1], what, o.pad.name), it.net, it.a, other=o.pad.name))
        for a, c in board.edges:
            d = seg_dist(it.a, it.b, a, c)[0] - it.r
            if d < profile.edge_clr - 1e-6:
                finds.append(F("EDGE", "%s: %s is %.3f mm from the board edge (%.3f needed)" % (it.net, it.desc, d, profile.edge_clr), it.net, it.a))
                break
        for kz in board.keepouts:
            if (it.layer is None or it.layer in kz["layers"]) and ((it.kind == "seg" and kz["tracks"]) or (it.kind == "round" and kz["vias"])):
                if seg_poly_dist(it.a, it.b, kz["poly"])[0] <= it.r:
                    finds.append(F("KEEPOUT", "%s: %s enters the keep-out area %r" % (it.net, it.desc, kz["name"]), it.net, it.a))
        if it.kind == "seg":
            for z in board.zones:
                if z["net"] != it.net and it.layer in z["layers"] and z["net"] not in opts.get("yield_nets", ()):
                    if seg_poly_dist(it.a, it.b, z["poly"])[0] <= it.r:
                        k = ("ZONE", it.net, z["net"], it.layer)
                        if k not in worst:
                            worst[k] = True
                            finds.append(F("ZONE", "%s: a track on %s runs through the pour of %s (%s); list the net in YIELD_NETS if that pour gives way" % (
                                it.net, it.layer, z["net"] or "no net", z["name"] or "unnamed"), it.net, it.a, other=z["net"], layer=it.layer))
    nv = {n: sum(1 for pc in pcs if pc[0] == "via") for n, pcs in resolved.items()}
    for n in sorted(nv):
        lim = opts.get("via_limit") or profile.limit(n, "via_max")
        if lim is not None and nv[n] > lim:
            finds.append(F("VIAS", "%s has %d vias, the limit is %d" % (n, nv[n], lim), n))
    return finds, sc


def length_findings(profile, lens, opts=None):
    out = []
    for n in sorted(lens):
        lim = (opts or {}).get("len_max") or profile.limit(n, "length_max")
        if lim is not None and lens[n]["length"] > lim + 1e-9:
            out.append(F("LEN", "%s is %.3f mm long, the limit is %g" % (n, lens[n]["length"], lim), n))
    return out
