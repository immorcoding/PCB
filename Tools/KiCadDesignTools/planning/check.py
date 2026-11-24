"""Clearance check of planned paths against a board, and the free copper area of regions (length-matching plans).

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.planning.check <board dir> [board] [--nets N ...|--group G ...]
                                                                     [--free DATA.py] [--json OUT]

Without --free: the present routes of the nets (default: the whole bus of board.toml, see planning/measure.py) are
checked as if they were planned, against every other copper of the board (a DRC-clean board gives 0 violations;
the self-test of the checker). --free DATA.py: the free area of the regions in the plan data module's FREE dict
(see free_area).

Library (planning/plan.py uses it):
  Rules.of(cfg, board)            widths, clearances and via sizes of the board: .kicad_pro / .kicad_dru through
                                  busroute's Profile (rule areas, in-area values, net classes, hole clearances), the
                                  serpentine clearance and the pours that yield from the routes file ([plan] routes)
  board_prims(board, rules, exclude, ...)   copper of the board except the nets in `exclude`: tracks, arcs, vias,
                                  pads (exact polygons), zone fills (pours of the yield nets left out: they are
                                  refilled), as Prims
  net_prims(P, rules, net)        a planned Net's copper (tracks with the width of the place, vias on every layer)
  check(P, rules, names)          every pair (planned item, other-net item) on one layer closer than required
  free_area(board, rules, regions, ...)    free copper area per region at a clearance (raster, 0.025 mm)

Geometry is exact for segments and circles (a segment of half width hw, a via = a zero-length segment); a pad is its
polygon (edges of zero width) or its circle; a zone fill is its polygon edges. Requirements: hole to hole
`hole_hole`; via hole to copper `hole_clr`, plated pad hole to copper `pth_hole_clr`; copper to copper the larger net
class clearance, `clr_area` when either item touches a rule area, the zone's own clearance against a pour, at least
the serpentine clearance when either item is a serpentine hump.
"""
import json, math, os, sys
from collections import defaultdict

EPS = 1e-6
CELL = 0.5                # spatial hash cell, mm
REACH = 0.35              # neighbours are searched this far beyond an item's half width (> every clearance)


# ----------------------------------------------------------------------------- geometry
def in_box(p, b, m=0.0):
    return b[0] - m <= p[0] <= b[2] + m and b[1] - m <= p[1] <= b[3] + m


def seg_hits_box(a, b, box):
    # Liang-Barsky
    x0, y0, x1, y1 = a[0], a[1], b[0], b[1]
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - box[0]), (dx, box[2] - x0), (-dy, y0 - box[1]), (dy, box[3] - y0)):
        if abs(p) < 1e-12:
            if q < 0:
                return False
        else:
            t = q / p
            if p < 0:
                if t > t1:
                    return False
                t0 = max(t0, t)
            else:
                if t < t0:
                    return False
                t1 = min(t1, t)
    return True


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def pt_seg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    if L2 < 1e-18:
        return dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def seg_seg(a, b, c, d):
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    if ((o1 > 0) != (o2 > 0)) and ((o3 > 0) != (o4 > 0)) and abs(o1) > 1e-15 and abs(o2) > 1e-15 and abs(o3) > 1e-15 and abs(o4) > 1e-15:
        return 0.0
    return min(pt_seg(a, c, d), pt_seg(b, c, d), pt_seg(c, a, b), pt_seg(d, a, b))


# ----------------------------------------------------------------------------- the board's numbers
class Rules:
    """What the checker and the planner need of a board: rule areas, widths, clearances, via sizes, layers."""

    def __init__(self, profile, areas, layers, serp_clr, yield_nets=(), limits=None):
        self.profile = profile
        self.areas = dict(areas)              # name -> (x0, y0, x1, y1)
        self.layers = list(layers)            # the signal layers (the copper a track may use)
        self.serp_clr = serp_clr
        self.yield_nets = set(yield_nets)
        self.limits = limits or {}            # serpentine limits (busroute tune.DEFAULTS + the routes file's TUNING)

    @classmethod
    def of(cls, cfg, board, routes=None):
        """From board.toml ([plan] routes: the routes module whose TUNING and YIELD_NETS apply), the board's
        .kicad_pro / .kicad_dru (next to the board file) and its rule areas."""
        from Tools.KiCadDesignTools.routing.busroute.profile import Profile
        from Tools.KiCadDesignTools.routing.busroute import tune
        prof = Profile.from_project(board.path)
        name = routes if routes is not None else cfg.get("plan.routes")
        mod = cfg.module(name) if name else None
        lim = dict(tune.DEFAULTS)
        lim.update({k: v for k, v in (getattr(mod, "TUNING", None) or {}).items() if k != "groups"})
        yn = getattr(mod, "YIELD_NETS", None)
        if yn is None:
            yn = [cfg.get("power.ground")] if cfg.get("power.ground") else []
        r = cls(prof, board.rule_areas(prof.area_names), cfg.signal_layers(), lim["clr"], yn, lim)
        r.module = mod
        return r

    def in_area(self, p, m=0.0):
        return any(in_box(p, b, m) for b in self.areas.values())

    def hits_area(self, a, b, grow=0.0):
        return any(seg_hits_box(a, b, (x0 - grow, y0 - grow, x1 + grow, y1 + grow)) for x0, y0, x1, y1 in self.areas.values())

    def width_for(self, net, a, b):
        """Track width of a planned piece: the in-area width when it comes within `extend` of a rule area."""
        return self.profile.w_area if self.hits_area(a, b, self.profile.extend) else self.profile.width(net)

    def via_size(self, net, p):
        return tuple(self.profile.via_area) if self.in_area(p) else tuple(self.profile.via_out(net))

    def clr(self, na, nb):
        return max(self.profile.clr(na), self.profile.clr(nb))


# ----------------------------------------------------------------------------- primitives
class Prims:
    """Copper primitives: segments (a, b, half width) and holes, per layer, in a spatial hash."""

    def __init__(self, rules):
        self.rules = rules
        self.items = []          # dict(kind, layer, net, a, b, hw, serp, what, zone, area, pth)
        self.grid = defaultdict(list)

    def add(self, kind, layer, net, a, b, hw, serp=False, what="", zone=None, pth=False):
        """zone: the pour's own clearance when the item is a pour edge (None otherwise)."""
        i = len(self.items)
        it = {"kind": kind, "layer": layer, "net": net, "a": a, "b": b, "hw": hw, "serp": serp, "what": what, "zone": zone, "pth": pth}
        it["area"] = self.rules.hits_area(a, b) if kind != "hole" else self.rules.in_area(a)
        self.items.append(it)
        m = hw + 0.4
        x0, x1 = min(a[0], b[0]) - m, max(a[0], b[0]) + m
        y0, y1 = min(a[1], b[1]) - m, max(a[1], b[1]) + m
        for gx in range(int(math.floor(x0 / CELL)), int(math.floor(x1 / CELL)) + 1):
            for gy in range(int(math.floor(y0 / CELL)), int(math.floor(y1 / CELL)) + 1):
                self.grid[(layer, gx, gy)].append(i)
        return i

    def near(self, layer, a, b, m):
        x0, x1 = min(a[0], b[0]) - m, max(a[0], b[0]) + m
        y0, y1 = min(a[1], b[1]) - m, max(a[1], b[1]) + m
        seen = set()
        for gx in range(int(math.floor(x0 / CELL)), int(math.floor(x1 / CELL)) + 1):
            for gy in range(int(math.floor(y0 / CELL)), int(math.floor(y1 / CELL)) + 1):
                for i in self.grid.get((layer, gx, gy), ()):
                    if i not in seen:
                        seen.add(i)
                        yield self.items[i]


def movable_vias(board_path):
    """Vias the finish step regenerates (its stitching vias, <board>.finish.json): not obstacles for a plan."""
    out = set()
    side = os.path.splitext(board_path)[0] + ".finish.json"
    if os.path.isfile(side):
        for v in json.load(open(side, encoding="utf-8")).get("vias", []):
            out.add((round(v[0], 2), round(v[1], 2)))
    return out


def board_prims(board, rules, exclude, movable=(), drop=(), pad_net=None):
    """The board's copper on the signal layers except the nets in `exclude` (tracks, arcs, vias; pads of every net
    stay). movable: via positions (rounded to 0.01) of yield-net vias left out; drop: (net, layer, a, b) segments of
    other nets a plan replaces; pad_net: {(ref, num): net} pads that a plan gives another net (a pin swap).
    Pours of the yield nets are left out (refilled after routing); teardrops of excluded nets go with them."""
    P = Prims(rules)
    ex, lays, pad_net = set(exclude), set(rules.layers), pad_net or {}
    movable = set(movable)
    for (n, lay, a, b, w, is_arc) in board.tracks:
        if n in ex or lay not in lays:
            continue
        if not is_arc and any(d[0] == n and d[1] == lay and ((dist(d[2], a) < 0.01 and dist(d[3], b) < 0.01) or (dist(d[2], b) < 0.01 and dist(d[3], a) < 0.01)) for d in drop):
            continue
        P.add("seg", lay, n, a, b, w / 2, what="arc" if is_arc else "track")
    for (n, at, size, drill) in board.vias:
        if n in ex:
            continue
        if n in rules.yield_nets and (round(at[0], 2), round(at[1], 2)) in movable:
            continue
        for l in rules.layers:
            P.add("seg", l, n, at, at, size / 2, what="via")
            P.add("hole", l, n, at, at, drill / 2, what="via hole")
    for p in board.all_pads():
        net = pad_net.get((p.ref, p.num), p.net or ("~%s.%s" % (p.ref, p.num)))
        what = "pad %s.%s" % (p.ref, p.num)
        for l in rules.layers:
            if p.npth:                          # a hole goes through every layer, whatever copper layers the pad names
                P.add("hole", l, net, p.pos, p.pos, p.hole, what=what)
                continue
            if p.layers is not None and l not in p.layers:
                continue
            if p.shape == "circle":
                P.add("seg", l, net, p.pos, p.pos, p.r, what=what)
            else:
                pts = p.poly
                for i in range(len(pts)):
                    P.add("seg", l, net, pts[i], pts[(i + 1) % len(pts)], 0.0, what=what)
            if p.hole > 0:
                P.add("hole", l, net, p.pos, p.pos, p.hole, what=what + " hole", pth=True)
    for f in board.fills:
        if f["net"] in rules.yield_nets and not f["teardrop"]:
            continue
        if f["net"] in ex or f["layer"] not in lays or len(f["pts"]) < 3:
            continue
        pts = f["pts"]
        zc = None if f["teardrop"] else (f["clearance"] or 0.0)
        for i in range(len(pts)):
            P.add("seg", f["layer"], f["net"] or "?zone", pts[i], pts[(i + 1) % len(pts)], 0.0,
                  what="zone " + (f["name"] or "teardrop"), zone=zc)
    return P


def net_prims(P, rules, net):
    """Add a planned Net's copper to P (tracks on their layer at the width of the place, vias on every layer).
    A piece of a serpentine block that lies off the block's straight is a hump (held to the serpentine clearance)."""
    for it in net.items:
        if it[0] == "t":
            pts = it[2]
            for i in range(len(pts) - 1):
                serp = False
                if it[3]:
                    mid = ((pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2)
                    d = min(pt_seg(mid, tuple(b["straight"][0]), tuple(b["straight"][1])) for b in net.blocks)
                    serp = d > 0.1
                P.add("seg", it[1], net.name, pts[i], pts[i + 1], rules.width_for(net.name, pts[i], pts[i + 1]) / 2, serp=serp, what="planned")
        else:
            d, h = rules.via_size(net.name, it[1])
            for l in rules.layers:
                P.add("seg", l, net.name, it[1], it[1], d / 2, what="planned via")
                P.add("hole", l, net.name, it[1], it[1], h / 2, what="planned via hole")


def required(rules, A, B):
    prof = rules.profile
    if A["kind"] == "hole" and B["kind"] == "hole":
        return prof.hole_hole
    if A["kind"] == "hole" or B["kind"] == "hole":
        h = A if A["kind"] == "hole" else B
        return prof.pth_hole_clr if h["pth"] else prof.hole_clr
    req = prof.clr_area if (A["area"] or B["area"]) else rules.clr(A["net"], B["net"])
    z = [x["zone"] for x in (A, B) if x["zone"] is not None]
    if z:
        req = max(z)
    if A["serp"] or B["serp"]:
        req = max(req, rules.serp_clr)
    return req


def check(P, planned_names):
    """All pairs (planned item, any other-net item) on one layer. Returns the violations sorted:
    (gap, required, layer, net A, net B, (x, y) of A's middle, what)."""
    viol = []
    seen = set()
    pn = set(planned_names)
    for A in P.items:
        if A["net"] not in pn:
            continue
        for Bq in P.near(A["layer"], A["a"], A["b"], A["hw"] + REACH):
            if Bq["net"] == A["net"]:
                continue
            key = (min(id(A), id(Bq)), max(id(A), id(Bq)))
            if key in seen:
                continue
            seen.add(key)
            d = seg_seg(A["a"], A["b"], Bq["a"], Bq["b"]) - A["hw"] - Bq["hw"]
            req = required(P.rules, A, Bq)
            if d < req - 1e-4:
                mid = ((A["a"][0] + A["b"][0]) / 2, (A["a"][1] + A["b"][1]) / 2)
                viol.append((round(d, 4), req, A["layer"], A["net"], Bq["net"], (round(mid[0], 3), round(mid[1], 3)),
                             A["what"] + " / " + Bq["what"] + ("" if A["kind"] == Bq["kind"] == "seg" else " [%s-%s]" % (A["kind"], Bq["kind"]))))
    viol.sort()
    return viol


def aggregate(viol, top=45):
    """The closest violation per (layer, net A, net B, what), closest first."""
    agg = {}
    for v in viol:
        k = (v[2], v[3], v[4], v[6])
        if k not in agg or v[0] < agg[k][0]:
            agg[k] = (v[0], v[1], v[5])
    return sorted(agg.items(), key=lambda kv: kv[1][0])[:top]


# ----------------------------------------------------------------------------- free area
RES = 0.025               # raster cell, mm


def _label(mask):
    """Connected pieces (4-neighbourhood) of a boolean array: sizes in cells, by row runs and union-find."""
    import numpy as np
    parent = []

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    prev = []                 # (start, end, id) runs of the previous row
    runs_id = []
    for row in mask:
        d = np.diff(np.concatenate(([0], row.astype(np.int8), [0])))
        st, en = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
        cur = []
        j = 0
        for s, e in zip(st.tolist(), en.tolist()):
            k = len(parent)
            parent.append(k)
            runs_id.append((k, e - s))
            while j < len(prev) and prev[j][1] <= s:
                j += 1
            jj = j
            while jj < len(prev) and prev[jj][0] < e:
                a, b = find(prev[jj][2]), find(k)
                if a != b:
                    parent[b] = a
                jj += 1
            cur.append((s, e, k))
        prev = cur
    sizes = defaultdict(int)
    for k, n in runs_id:
        sizes[find(k)] += n
    return list(sizes.values())


def free_area(board, rules, regions, clearance, exclude=(), layers=None, movable=(), bands=None):
    """Free copper area per region and layer: a cell is free when no copper of a net outside `exclude` lies within
    `clearance` of its centre. Pours of the yield nets are not copper (they yield); yield-net vias at `movable`
    positions are left out. bands: {layer: [((x0, y0), (x1, y1), width)]} extra obstacles (e.g. a band along the
    reference plane's block edges). regions: {name: (x0, y0, x1, y1)}.
    Returns {region: {layer: {"box_mm2", "free_mm2", "largest_pieces_mm2"}}}."""
    import numpy as np
    from PIL import Image, ImageDraw
    layers = layers or rules.layers
    X0 = min(r[0] for r in regions.values()) - 1.0
    Y0 = min(r[1] for r in regions.values()) - 1.0
    X1 = max(r[2] for r in regions.values()) + 1.0
    Y1 = max(r[3] for r in regions.values()) + 1.0
    W, H = int(round((X1 - X0) / RES)), int(round((Y1 - Y0) / RES))
    ex, movable, c = set(exclude), set(movable), clearance

    def px(p):
        return ((p[0] - X0) / RES, (p[1] - Y0) / RES)

    def line(d, a, b, hw):
        ax, ay = px(a); bx, by = px(b)
        r = hw / RES
        L = math.hypot(bx - ax, by - ay)
        if L > 1e-9:
            nx, ny = -(by - ay) / L * r, (bx - ax) / L * r
            d.polygon([(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)], fill=1)
        d.ellipse([ax - r, ay - r, ax + r, ay + r], fill=1)
        d.ellipse([bx - r, by - r, bx + r, by + r], fill=1)
    out = {}
    for lay in layers:
        img = Image.new("1", (W, H), 0)
        d = ImageDraw.Draw(img)
        for f in board.fills:
            if f["layer"] != lay or f["net"] in ex or (f["net"] in rules.yield_nets and not f["teardrop"]) or len(f["pts"]) < 3:
                continue
            d.polygon([px(p) for p in f["pts"]], fill=1)
            for i in range(len(f["pts"])):
                line(d, f["pts"][i], f["pts"][(i + 1) % len(f["pts"])], c)
        for (n, l, a, b, w, _) in board.tracks:
            if l == lay and n not in ex:
                line(d, a, b, w / 2 + c)
        for p in board.all_pads():
            if p.npth:
                line(d, p.pos, p.pos, p.hole + c)
                continue
            if p.net in ex or (p.layers is not None and lay not in p.layers):
                continue
            if p.shape == "circle":
                line(d, p.pos, p.pos, p.r + c)
            else:
                d.polygon([px(q) for q in p.poly], fill=1)
                for i in range(len(p.poly)):
                    line(d, p.poly[i], p.poly[(i + 1) % len(p.poly)], c)
        for (n, at, size, drill) in board.vias:
            if n in ex or (n in rules.yield_nets and (round(at[0], 2), round(at[1], 2)) in movable):
                continue
            line(d, at, at, size / 2 + c)
        for (a, b, w) in (bands or {}).get(lay, []):
            line(d, a, b, w / 2 + c)
        busy = np.array(img, dtype=bool)
        for name, (x0, y0, x1, y1) in regions.items():
            i0, i1 = int((x0 - X0) / RES), int((x1 - X0) / RES)
            j0, j1 = int((y0 - Y0) / RES), int((y1 - Y0) / RES)
            sub = ~busy[j0:j1, i0:i1]
            sizes = sorted(_label(sub), reverse=True)[:2]
            out.setdefault(name, {})[lay] = {"box_mm2": round((x1 - x0) * (y1 - y0), 1), "free_mm2": round(float(sub.sum()) * RES * RES, 1),
                                             "largest_pieces_mm2": [round(s * RES * RES, 1) for s in sizes]}
    return out


def free_text(res):
    lines = []
    for name, v in res.items():
        lines.append(name)
        for lay, r in v.items():
            lines.append("   %s  box %.0f mm2, free %.1f mm2, largest connected pieces %s" % (lay, r["box_mm2"], r["free_mm2"], r["largest_pieces_mm2"]))
    return lines


# ----------------------------------------------------------------------------- command line
def load_data(path):
    """A plan data module by file path (planning/plan.py's format; no sys.path change)."""
    import importlib.util
    path = os.path.abspath(path)
    spec = importlib.util.spec_from_file_location("plan_data_" + os.path.splitext(os.path.basename(path))[0], path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv):
    import argparse
    from Tools.KiCadDesignTools.core import config
    from Tools.KiCadDesignTools.routing.busroute.board import Board
    from Tools.KiCadDesignTools.planning import measure
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(prog="python -m Tools.KiCadDesignTools.planning.check", description=__doc__.split("\n\n")[0])
    ap.add_argument("board_dir")
    ap.add_argument("board", nargs="?")
    ap.add_argument("--nets", nargs="+")
    ap.add_argument("--group", nargs="+")
    ap.add_argument("--free", metavar="DATA.py")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    cfg = config.load(a.board_dir)
    path = os.path.abspath(a.board or cfg.pcb)
    board = Board(path, cfg.origin, fills=True)
    rules = Rules.of(cfg, board)
    G = measure.groups(cfg)
    if a.free:
        data = load_data(a.free)
        F = data.FREE
        bands = {}
        for lay, f in F.get("bands", {}).items():
            segs = json.load(open(os.path.join(os.path.dirname(os.path.abspath(a.free)), f["file"]), encoding="utf-8"))["segments"]
            bands[lay] = [(tuple(s[0]), tuple(s[1]), f["width"]) for s in segs]
        res = free_area(board, rules, F["regions"], F["clearance"], exclude=G["bus"], layers=F.get("layers"), movable=movable_vias(path), bands=bands)
        print("\n".join(free_text(res)))
        if a.json:
            json.dump(res, open(a.json, "w", encoding="utf-8"), indent=1)
        return 0
    nets = measure.select(G, a.nets, a.group)
    P = board_prims(board, rules, nets, movable=movable_vias(path))
    from Tools.KiCadDesignTools.planning.plan import Plan
    pl = Plan(cfg, board, rules)
    for n in nets:
        net_prims(P, rules, pl.Net(n).keep_present())
    viol = check(P, nets)
    print("%d nets checked against the rest of %s: %d violations" % (len(nets), os.path.basename(path), len(viol)))
    for k, v in aggregate(viol):
        print("  ", k, v)
    if a.json:
        json.dump({"nets": nets, "violations": viol}, open(a.json, "w", encoding="utf-8"), indent=1)
    return 1 if viol else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
