"""Grid engine of planning.bga_plan and planning.bga_fan: the copper of a geo.json (planning.bga_dump) as exact
clearance fields on a 0.025 mm point grid, the legal via sites, the plane-slot rule, and shortest escapes over the
signal layers (the verifier).

The layers come from the board's board.toml (configure(cfg), called by the planners before anything else): the
signal layers (role signal / mixed; H743: L1 L3 L4 L6), the planes (L2 ground, whole; L5 the power blocks), the
power plane (role power), the ground plane (role ground) and the ground net ([power] ground).

Pure Python + numpy / scipy / scikit-image (system Python, not KiCad's). Nothing here allocates anything: the
allocation is bga_plan's model; this module only answers "is there room" for a given state.

Rules (profile C, docs/rule-profiles/C-bga-065.md; values read from geo["rules"]):
  track    inside a BGA rule area 0.09 wide, 0.09 to other copper; outside its class width, 0.127
  via      0.30 / 0.15 when wholly inside a rule area, else 0.45 / 0.20; pad to copper as a track; hole edge to
           other copper 0.2 (plated part holes 0.3); hole edge to hole edge 0.254; never on a pad
  planes   two vias foreign to a plane (L2: not GND; L5: not the net of the block they stand in) join their
           clearance holes when closer than (d1 + d2) / 2 + 2 * 0.127 + 0.2; a chain's length is the largest
           centre distance in it + the largest pad + 0.254 (copper.plane_slots, copper.bga_power)
The grid is aligned to the ball lattices (0.65 / 2 and 0.8 / 2 are multiples of 0.025), so the one-track
channels (0.08 mm of room between two pads, 0.01 mm between two vias) are met exactly: distances are computed
per copper item at the grid points, not from a raster.
"""
import math
import numpy as np

STEP = 0.025
PLANE_CLR, PLANE_MINW = 0.127, 0.2
CAP = 0.6                      # distances are kept up to this (the largest need is a 0.45 via: 0.352)
EPS = 1e-4

# the board's layers and ground net, set by configure(cfg)
LAYERS = None                  # signal layers, top to bottom
PLANES = None                  # plane layers (ground and power), top to bottom
PWR_PLANE = None               # the power plane (its blocks: one net each, the rest the whole-layer net)
GND_PLANE = None               # the ground plane
COPPER = None                  # every copper layer (pads without a layer list, vias)
TOP = BOTTOM = None            # the outer layers
GROUND = None                  # the ground net


def configure(cfg):
    """Take the layers and the ground net from a board configuration (core.config)."""
    global LAYERS, PLANES, PWR_PLANE, GND_PLANE, COPPER, TOP, BOTTOM, GROUND
    from Tools.KiCadDesignTools.core import config
    LAYERS = tuple(cfg.signal_layers())
    PLANES = tuple(cfg.plane_layers())
    pw = [l.L for l in cfg.layers if l.role == "power"]
    gn = [l.L for l in cfg.layers if l.role == "ground"]
    if len(pw) != 1 or len(gn) != 1:
        raise config.ConfigError("%s: the BGA planners need one ground and one power layer, found %s / %s" % (cfg.toml, gn, pw))
    PWR_PLANE, GND_PLANE = pw[0], gn[0]
    COPPER = tuple(l.L for l in cfg.layers)
    TOP, BOTTOM = cfg.layers[0].L, cfg.layers[-1].L
    GROUND = cfg.need("power.ground")


def _need_config():
    if LAYERS is None:
        raise RuntimeError("bga_grid: configure(cfg) has not been called")


class Item:
    __slots__ = ("net", "layers", "kind", "a", "b", "r", "poly", "box", "hole", "tag")

    def __init__(self, net, layers, kind, a=None, b=None, r=0.0, poly=None, hole=0.0, tag=""):
        self.net, self.layers, self.kind, self.a, self.b, self.r, self.poly, self.hole, self.tag = net, layers, kind, a, b, r, poly, hole, tag
        if kind == "poly":
            xs, ys = [p[0] for p in poly], [p[1] for p in poly]
            self.box = (min(xs), min(ys), max(xs), max(ys))
        elif kind == "seg":
            self.box = (min(a[0], b[0]) - r, min(a[1], b[1]) - r, max(a[0], b[0]) + r, max(a[1], b[1]) + r)
        else:
            self.box = (a[0] - r, a[1] - r, a[0] + r, a[1] + r)


def _seg_d(X, Y, a, c):
    ax, ay = a; cx, cy = c
    dx, dy = cx - ax, cy - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return np.hypot(X - ax, Y - ay)
    t = np.clip(((X - ax) * dx + (Y - ay) * dy) / L2, 0, 1)
    return np.hypot(X - (ax + t * dx), Y - (ay + t * dy))


def _poly_d(X, Y, poly):
    """Distance to a filled polygon (0 inside)."""
    d = None
    inside = np.zeros(X.shape, bool)
    n = len(poly)
    for i in range(n):
        a, c = poly[i], poly[(i + 1) % n]
        s = _seg_d(X, Y, a, c)
        d = s if d is None else np.minimum(d, s)
        (x1, y1), (x2, y2) = a, c
        if abs(y2 - y1) > 1e-12:
            cond = ((y1 > Y) != (y2 > Y)) & (X < (x2 - x1) * (Y - y1) / (y2 - y1) + x1)
            inside ^= cond
    d[inside] = 0.0
    return d


def item_dist(it, X, Y):
    """Distance from the points to the copper edge of the item (0 inside)."""
    if it.kind == "poly":
        return _poly_d(X, Y, it.poly)
    if it.kind == "seg":
        return np.maximum(_seg_d(X, Y, it.a, it.b) - it.r, 0.0)
    return np.maximum(np.hypot(X - it.a[0], Y - it.a[1]) - it.r, 0.0)


def scene_items(geo, drop_nets=(), yield_nets=None, extra=()):
    """Every piece of copper of a geo.json as Items. drop_nets: nets whose tracks and vias are left out (their
    pads stay). Zones of yield_nets (default: the ground net) are not obstacles (their pours give way); other zones
    on the signal layers are."""
    _need_config()
    if yield_nets is None:
        yield_nets = (GROUND,)
    out = []
    drop = set(drop_nets)
    for p in geo["pads"]:
        lays = tuple(p["layers"]) if p["layers"] else COPPER
        hole = p["hole"] + (0.1 if p["hole"] > 0 else 0.0)                      # plated part holes: 0.3 to copper, kept as 0.2 + 0.1
        tag = "%s.%s" % (p["ref"], p["num"])
        if p["shape"] == "circle":
            out.append(Item(p["net"], lays, "round", a=tuple(p["pos"]), r=p["r"], hole=hole, tag=tag))
        else:
            out.append(Item(p["net"], lays, "poly", poly=[tuple(q) for q in p["poly"]], a=tuple(p["pos"]), hole=hole, tag=tag))
    for n, pos, d, h in geo["vias"]:
        if n in drop:
            continue
        out.append(Item(n, COPPER, "round", a=tuple(pos), r=d / 2, hole=h / 2, tag="via"))
    for n, lay, a, c, w in geo["tracks"]:
        if n in drop:
            continue
        out.append(Item(n, (lay,), "seg", a=tuple(a), b=tuple(c), r=w / 2, tag="track"))
    for z in geo["zones"]:
        if z["net"] in yield_nets or not z["net"]:
            continue
        lays = tuple(l for l in z["layers"] if l in LAYERS)
        if lays:
            out.append(Item(z["net"], lays, "poly", poly=[tuple(q) for q in z["poly"]], tag="zone " + z["name"]))
    for k in geo["keepouts"]:
        lays = tuple(l for l in k["layers"] if l in LAYERS)
        if lays and k["tracks"]:
            out.append(Item("<keepout>", lays, "poly", poly=[tuple(q) for q in k["poly"]], tag="keepout " + k["name"]))
    out += list(extra)
    return out


class Field:
    """Clearance fields of a scene over a window. D[layer][j, i] = distance (mm, capped) from grid point (i, j) to
    the nearest copper edge on that layer; H = distance to the nearest hole edge (part holes grown by 0.1)."""

    def __init__(self, geo, window, items=None, step=STEP):
        _need_config()
        self.geo, self.step = geo, step
        self.x0, self.y0 = window[0], window[1]
        self.nx = int(round((window[2] - window[0]) / step)) + 1
        self.ny = int(round((window[3] - window[1]) / step)) + 1
        self.x1, self.y1 = self.x0 + (self.nx - 1) * step, self.y0 + (self.ny - 1) * step
        self.xs = self.x0 + step * np.arange(self.nx)
        self.ys = self.y0 + step * np.arange(self.ny)
        R = geo["rules"]
        self.w_area, self.clr_area = R["w_area"], R["clr_area"]
        self.via_in = tuple(R["via_area"])
        self.hole_clr, self.hole_hole = R["hole_clr"], R["hole_hole"]
        self.clr_out = 0.127
        self.via_out = (0.45, 0.2)
        self.areas = [tuple(a["rect"]) for n, a in sorted(geo["areas"].items()) if n in R["area_names"]]
        self.items = items if items is not None else scene_items(geo)
        X, Y = np.meshgrid(self.xs, self.ys)
        self.inA = np.zeros(X.shape, bool)
        for a in self.areas:
            self.inA |= (X >= a[0] - 1e-9) & (X <= a[2] + 1e-9) & (Y >= a[1] - 1e-9) & (Y <= a[3] + 1e-9)
        del X, Y
        self.D = {l: np.full((self.ny, self.nx), CAP, np.float32) for l in LAYERS}
        self.H = np.full((self.ny, self.nx), CAP, np.float32)
        self.cells = {}                                     # coarse index of the items: (cx, cy) of 1 mm cells -> [item index]
        for k, it in enumerate(self.items):
            self._stamp(it, self.D, self.H)
            b = it.box
            for cx in range(int(math.floor(b[0] - CAP)), int(math.floor(b[2] + CAP)) + 1):
                for cy in range(int(math.floor(b[1] - CAP)), int(math.floor(b[3] + CAP)) + 1):
                    self.cells.setdefault((cx, cy), []).append(k)

    # ---- grid helpers
    def ij(self, p):
        return int(round((p[0] - self.x0) / self.step)), int(round((p[1] - self.y0) / self.step))

    def inside(self, p, m=0.0):
        return self.x0 + m <= p[0] <= self.x1 - m and self.y0 + m <= p[1] <= self.y1 - m

    def pt(self, i, j):
        return (round(self.x0 + i * self.step, 4), round(self.y0 + j * self.step, 4))

    def _win(self, box, pad):
        i0 = max(0, int(math.floor((box[0] - pad - self.x0) / self.step)))
        i1 = min(self.nx, int(math.ceil((box[2] + pad - self.x0) / self.step)) + 1)
        j0 = max(0, int(math.floor((box[1] - pad - self.y0) / self.step)))
        j1 = min(self.ny, int(math.ceil((box[3] + pad - self.y0) / self.step)) + 1)
        return j0, j1, i0, i1

    def _stamp(self, it, D, H, win=None, off=(0, 0)):
        """min the item's distance into D (dict layer -> array) and H. win = (j0, j1, i0, i1) limits the patch and
        off = (j, i) is the position of D's origin in the full grid (patch arrays)."""
        j0, j1, i0, i1 = self._win(it.box, CAP)
        if win:
            j0, j1, i0, i1 = max(j0, win[0]), min(j1, win[1]), max(i0, win[2]), min(i1, win[3])
        if j0 >= j1 or i0 >= i1:
            return
        X, Y = np.meshgrid(self.xs[i0:i1], self.ys[j0:j1])
        sl = (slice(j0 - off[0], j1 - off[0]), slice(i0 - off[1], i1 - off[1]))
        d = None
        for l in LAYERS:
            if l in it.layers:
                if d is None:
                    d = item_dist(it, X, Y).astype(np.float32)
                np.minimum(D[l][sl], d, out=D[l][sl])
        if it.hole > 0 and H is not None:
            h = np.maximum(np.hypot(X - it.a[0], Y - it.a[1]) - it.hole, 0.0).astype(np.float32)
            np.minimum(H[sl], h, out=H[sl])

    def is_area(self, p, shrink=0.0):
        return any(a[0] + shrink - 1e-9 <= p[0] <= a[2] - shrink + 1e-9 and a[1] + shrink - 1e-9 <= p[1] <= a[3] - shrink + 1e-9 for a in self.areas)

    def near_items(self, box):
        seen = set()
        for cx in range(int(math.floor(box[0])), int(math.floor(box[2])) + 1):
            for cy in range(int(math.floor(box[1])), int(math.floor(box[3])) + 1):
                seen.update(self.cells.get((cx, cy), ()))
        return [self.items[k] for k in sorted(seen)]

    # ---- a net's own view: its own copper is no obstacle
    def opened(self, net, extra_own=()):
        """(D, H) copies where the copper of `net` (and the items in extra_own) is no obstacle: the patches round
        its items are recomputed from the other items."""
        D = {l: self.D[l].copy() for l in LAYERS}
        H = self.H.copy()
        own = [it for it in self.items if it.net == net] + list(extra_own)
        ownset = set(id(o) for o in own)
        for o in own:
            j0, j1, i0, i1 = self._win(o.box, CAP)
            if j0 >= j1 or i0 >= i1:
                continue
            Dp = {l: np.full((j1 - j0, i1 - i0), CAP, np.float32) for l in LAYERS}
            Hp = np.full((j1 - j0, i1 - i0), CAP, np.float32)
            box = (self.xs[i0] - CAP, self.ys[j0] - CAP, self.xs[i1 - 1] + CAP, self.ys[j1 - 1] + CAP)
            for it in self.near_items(box):
                if it.net == net or id(it) in ownset:
                    continue
                self._stamp(it, Dp, Hp, win=(j0, j1, i0, i1), off=(j0, i0))
            for l in LAYERS:
                if l in o.layers:
                    D[l][j0:j1, i0:i1] = Dp[l]
            if o.hole > 0:
                H[j0:j1, i0:i1] = Hp
        return D, H

    # ---- room for a track / a via
    def track_free(self, layer, width, D=None, H=None, tol=0.0):
        """Mask of the grid points where the centre line of a track of class width `width` may be.
        tol: slack outside the rule areas, for states whose copper is not on the grid (a real board's lanes at
        x = 35.76 are seen from the grid line 35.75: half a step, 0.0125, makes up for it; the planner's own
        copper is on the grid and is checked with tol = 0)."""
        D = (D or self.D)[layer]
        H = self.H if H is None else H
        need = np.where(self.inA, self.w_area / 2 + self.clr_area, width / 2 + self.clr_out - tol).astype(np.float32)
        hneed = np.where(self.inA, self.w_area / 2, width / 2 - tol).astype(np.float32) + self.hole_clr
        return (D >= need - EPS) & (H >= hneed - EPS)

    def via_size(self, p):
        return self.via_in if self.is_area(p, self.via_in[0] / 2) else self.via_out

    def via_ok(self, p, D=None, H=None, pads=None):
        """May a via stand at p (pad and hole against the copper of every signal layer, hole against holes)?
        D / H: a net's opened fields (its own tracks do not count); pads: the all-copper fields used for "never on
        a pad" (default: self.D, which holds every pad)."""
        if not self.inside(p, 0.3):
            return False
        d, h = self.via_size(p)
        i, j = self.ij(p)
        clr = self.clr_area if self.is_area(p) else self.clr_out
        need = max(d / 2 + clr, h / 2 + self.hole_clr)
        D = D or self.D
        for l in LAYERS:
            if D[l][j, i] < need - EPS:
                return False
        if (H if H is not None else self.H)[j, i] < h / 2 + self.hole_hole - EPS:
            return False
        return True


# ---------------------------------------------------------------- plane slots
def merge_dist(d1, d2):
    return (d1 + d2) / 2 + 2 * PLANE_CLR + PLANE_MINW


class Slots:
    """Chains of joined clearance holes on the planes (the ground plane, the power plane's blocks) for a set of vias
    [(net, (x, y), diameter)]."""

    def __init__(self, geo, vias=()):
        _need_config()
        self.blocks = [(z["net"], z["poly"]) for z in geo["zones"] if PWR_PLANE in z["layers"] and not z["name"].startswith("cu-whole")]
        self.whole = next((z["net"] for z in geo["zones"] if PWR_PLANE in z["layers"] and z["name"].startswith("cu-whole")), None)
        self.vias = []
        self.grid = {}
        for v in vias:
            self.add(*v)

    def l3_net(self, p):
        for net, poly in self.blocks:
            if _in_poly(p, poly):
                return net
        return self.whole

    def foreign(self, net, p):
        """The planes on which a via of `net` at p needs a clearance hole."""
        out = []
        if net != GROUND:
            out.append(GND_PLANE)
        if net != self.l3_net(p):
            out.append(PWR_PLANE)
        return out

    def add(self, net, p, d):
        v = (net, (float(p[0]), float(p[1])), d, tuple(self.foreign(net, p)))
        self.vias.append(v)
        self.grid.setdefault((int(math.floor(p[0])), int(math.floor(p[1]))), []).append(v)
        return v

    def remove_last(self):
        v = self.vias.pop()
        self.grid[(int(math.floor(v[1][0])), int(math.floor(v[1][1])))].remove(v)

    def _near(self, p):
        cx, cy = int(math.floor(p[0])), int(math.floor(p[1]))
        for a in (cx - 1, cx, cx + 1):
            for b in (cy - 1, cy, cy + 1):
                for v in self.grid.get((a, b), ()):
                    yield v

    def chain(self, start, plane):
        """The vias joined to `start` on `plane`, and the chain's length."""
        if plane not in start[3]:
            return [], 0.0
        seen, todo, mem = {id(start)}, [start], [start]
        while todo:
            v = todo.pop()
            for o in self._near(v[1]):
                if id(o) not in seen and plane in o[3] and math.dist(o[1], v[1]) < merge_dist(o[2], v[2]) - 1e-9:
                    seen.add(id(o)); todo.append(o); mem.append(o)
        if len(mem) == 1:
            return mem, start[2] + 2 * PLANE_CLR
        return mem, max(math.dist(a[1], c[1]) for a in mem for c in mem) + max(m[2] for m in mem) + 2 * PLANE_CLR

    def with_via(self, net, p, d):
        """Longest chain (over the three planes) through a via of `net` that would be added at p."""
        v = self.add(net, p, d)
        best = max((self.chain(v, pl)[1] for pl in PLANES), default=0.0)
        self.remove_last()
        return best

    def longest(self, box=None):
        """[(length, plane, [vias])] of every chain longer than one via, longest first."""
        out = []
        for pl in PLANES:
            seen = set()
            for v in self.vias:
                if id(v) in seen or pl not in v[3]:
                    continue
                if box and not (box[0] <= v[1][0] <= box[2] and box[1] <= v[1][1] <= box[3]):
                    continue
                mem, ln = self.chain(v, pl)
                seen.update(id(m) for m in mem)
                if len(mem) > 1:
                    out.append((round(ln, 3), pl, sorted((m[0], m[1]) for m in mem)))
        out.sort(key=lambda r: (-r[0], r[1], r[2]))
        return out


def _in_poly(p, poly):
    x, y = p
    inside = False
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


# ---------------------------------------------------------------- shortest escapes (the verifier)
class Maze:
    """Shortest octilinear path of one net over three layers (bga_plan's: H743 L1 / L4 / L6) with through vias at
    given candidate sites. Planes of the cost volume: layer 1, via, layer 2, via, layer 3. A via site is one open
    point of both via planes (candidate sites are never neighbours on the grid, so a path cannot slide along a via
    plane)."""
    VIA_COST = 3.0             # mm of path a via counts as

    def __init__(self, field, layers):
        self.f = field
        self.layers = tuple(layers)

    def volume(self, masks, S, sel):
        """masks: {layer: track-free mask}; S: an object with index arrays I, J of the via candidates; sel: which
        of them are open."""
        f = self.f
        vol = np.full((5, f.ny, f.nx), np.inf)
        for k, l in zip((0, 2, 4), self.layers):           # the maze's own three layers, as route() names the planes
            vol[k][masks[l]] = 1.0
        c = self.VIA_COST / (2 * STEP) - 1.0                # two vertical steps of length STEP through a cell of cost c + neighbours of cost 1
        I, J = S.I[sel], S.J[sel]
        vol[1, J, I] = c
        vol[3, J, I] = c
        return vol

    OFFS = [(0, 0, 1), (0, 0, -1), (0, 1, 0), (0, -1, 0), (0, 1, 1), (0, 1, -1), (0, -1, 1), (0, -1, -1), (1, 0, 0), (-1, 0, 0)]

    def route(self, vol, starts, ends, max_cost=None):
        """starts / ends: [(layer, (x, y))]. -> (cost, [(layer or 'via', (x, y))...]) or None."""
        from skimage.graph import MCP_Geometric
        f = self.f
        K = {l: 2 * k for k, l in enumerate(self.layers)}   # three-layer verifier (try/fanout-first); not used for the L3 order
        S = [(K[l],) + f.ij(p)[::-1] for l, p in starts]
        E = [(K[l],) + f.ij(p)[::-1] for l, p in ends]
        S = [s for s in S if np.isfinite(vol[s])]
        E = [e for e in E if np.isfinite(vol[e])]
        if not S or not E:
            return None
        m = MCP_Geometric(vol, offsets=self.OFFS, sampling=(STEP, STEP, STEP))
        cost, _ = m.find_costs(S, E, find_all_ends=False, max_cost=max_cost) if max_cost else m.find_costs(S, E, find_all_ends=False)
        best = min(E, key=lambda e: cost[e])
        if not np.isfinite(cost[best]):
            return None
        tb = m.traceback(best)
        names = {0: self.layers[0], 1: "via", 2: self.layers[1], 3: "via", 4: self.layers[2]}
        return float(cost[best]), [(names[k], f.pt(i, j)) for k, j, i in tb]


def path_pieces(path):
    """A Maze path -> busroute pieces [("L1", [pts]), ("via", p), ...] with collinear points merged, its track
    length and its via count."""
    pieces, cur, lay, vias = [], [], None, 0
    k, n = 0, len(path)
    while k < n:
        k2 = k
        while k2 < n and path[k2][1] == path[k][1]:
            k2 += 1
        grp, p = [l for l, _ in path[k:k2]], path[k][1]
        if "via" in grp:
            if lay is None:
                lay = grp[0]
            if cur and cur[-1] != p:
                cur.append(p)
            if len(cur) > 1:
                pieces.append((lay, _merge(cur)))
            pieces.append(("via", p))
            vias += 1
            cur, lay = [p], next((l for l in reversed(grp) if l != "via"), lay)
        else:
            if lay is None:
                lay = grp[0]
            cur.append(p)
        k = k2
    if len(cur) > 1:
        pieces.append((lay, _merge(cur)))
    length = sum(math.dist(a, b) for pc in pieces if pc[0] != "via" for a, b in zip(pc[1], pc[1][1:]))
    return pieces, length, vias


def _merge(pts):
    out = [pts[0]]
    for p in pts[1:]:
        if p == out[-1]:
            continue
        if len(out) >= 2:
            a, b = out[-2], out[-1]
            if abs((b[0] - a[0]) * (p[1] - b[1]) - (b[1] - a[1]) * (p[0] - b[0])) < 1e-9 and (b[0] - a[0]) * (p[0] - b[0]) + (b[1] - a[1]) * (p[1] - b[1]) > 0:
                out[-1] = p
                continue
        out.append(p)
    return out


# ---------------------------------------------------------------- tidy: a grid path as few octilinear segments
def _line_cells(field, a, b):
    """Grid indices (J, I) of the points of the octilinear segment a-b (both on the grid)."""
    ia, ja = field.ij(a); ib, jb = field.ij(b)
    n = max(abs(ib - ia), abs(jb - ja))
    if n == 0:
        return np.array([ja]), np.array([ia])
    return np.round(np.linspace(ja, jb, n + 1)).astype(int), np.round(np.linspace(ia, ib, n + 1)).astype(int)


def _doglegs(a, b):
    """The ways from a to b with at most one 45 degree corner: [[a, b]] or [[a, m1, b], [a, m2, b]]."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if abs(dx) < 1e-9 or abs(dy) < 1e-9 or abs(abs(dx) - abs(dy)) < 1e-9:
        return [[a, b]]
    m = min(abs(dx), abs(dy))
    sx, sy = math.copysign(1, dx), math.copysign(1, dy)
    if abs(dx) > abs(dy):
        m1 = (round(a[0] + sx * m, 4), b[1]); m2 = (round(b[0] - sx * m, 4), a[1])
    else:
        m1 = (b[0], round(a[1] + sy * m, 4)); m2 = (a[0], round(b[1] - sy * m, 4))
    return [[a, m1, b], [a, m2, b]]             # diagonal first, straight first


def tidy(field, pts, mask, prefer=0):
    """The grid path `pts` (consecutive grid points of one layer, all inside `mask`) redrawn with as few
    octilinear segments as the mask allows: from each corner the farthest later point of the path that one
    straight or one dog-leg reaches inside the mask. Deterministic."""
    def clear(way):
        for p, q in zip(way, way[1:]):
            J, I = _line_cells(field, p, q)
            if not mask[J, I].all():
                return False
        return True
    out = [pts[0]]
    i, n = 0, len(pts)
    while i < n - 1:
        best, way = i + 1, [pts[i], pts[i + 1]]
        j, miss = i + 2, 0
        while j < n and miss < 60:
            ok = None
            ways = _doglegs(pts[i], pts[j])
            for w in (ways if prefer == 0 else ways[::-1]):
                if clear(w):
                    ok = w
                    break
            if ok:
                best, way, miss = j, ok, 0
            else:
                miss += 1
            j += 1
        out += way[1:]
        i = best
    return _merge(out)
