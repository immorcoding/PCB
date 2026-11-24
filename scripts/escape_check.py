"""Way out of every pad of fine-pitch parts (LAY-2): can a track get from the pad to open board, or to its partner.

    D:\\KiCad\\bin\\python.exe scripts\\escape_check.py <board> --ref U201 [--ref U501 ...] [options] [--json out.json]

Options:
  --ref REF            part whose pads are checked (repeatable)
  --window X0 Y0 X1 Y1 the open-board boundary for all parts (local mm, see --origin); default per part: its
                       courtyard box grown by --margin
  --margin MM          default 3
  --layers L1 L4 L6    signal layers tracks may use (L1 = F.Cu, Ln = B.Cu); default L1 L4 L6
  --plane NET ...      nets that end in a plane or pour: they are connected as soon as a via can stand
                       somewhere the pad reaches (default GND and every net starting with +)
  --max-vias N         default 2
  --grid MM            raster step, default 0.025
  --origin X Y         default 100 100
  --debug REF.PAD PNG  paint what that pad reaches (per layer, side by side): blocked dark, free grey, reached
                       without a via green, after one via yellow, after two orange

Rules (from SPEC 6, 7 and the board's net classes; inside the rule areas whose names start with BGA_):
                       inside area   outside
  track width          0.09          0.1016
  clearance            0.09          0.127
  via                  0.30 / 0.15   0.45 / 0.20
  hole to copper       0.20          0.20
Every copper object on the board is an obstacle for other nets: pads (their real outline), tracks, vias, through
holes; footprint and board rule areas that forbid tracks are walls on their layers; the board edge with
0.3 mm. Distances are taken at cell centres on a grid aligned to multiples of --grid (0.65 and 0.8 mm ball
grids fall on it), with half a cell of tolerance, so a channel that is exactly as wide as the rule needs
counts as open.

Per pad the result is the first that applies, with the vias it needs (plane nets try `plane` first):
  plane   a plane net that can put a via down within reach (the count includes that via)
  local   reaches a pad of the same net on another part (crystal, capacitor, series resistor)
  out     reaches the window boundary
  blocked none of these within --max-vias
Each pad is checked alone: tracks of the other unrouted nets are not there yet, so `out` says a way exists,
not that all of them fit at once (capacity is a routing question).
"""
import argparse, collections, json, math, re, sys
import numpy as np
import pcbnew
from pcbnew import ToMM

EMPTY, MIXED = -2, -1


def opts(argv):
    p = argparse.ArgumentParser()
    p.add_argument("board")
    p.add_argument("--ref", action="append", required=True)
    p.add_argument("--window", nargs=4, type=float)
    p.add_argument("--margin", type=float, default=3.0)
    p.add_argument("--layers", nargs="+", default=["L1", "L4", "L6"])
    p.add_argument("--plane", nargs="*")
    p.add_argument("--max-vias", type=int, default=2)
    p.add_argument("--grid", type=float, default=0.025)
    p.add_argument("--origin", nargs=2, type=float, default=[100.0, 100.0])
    p.add_argument("--json")
    p.add_argument("--debug", nargs=2)
    return p.parse_args(argv)


def layer_id(board, name):
    n = board.GetCopperLayerCount()
    k = int(name[1:])
    if k == 1:
        return pcbnew.F_Cu
    if k == n:
        return pcbnew.B_Cu
    return getattr(pcbnew, "In%d_Cu" % (k - 1))


# ------------------------------------------------------------------------------------------- labelling

def label(mask):
    """8-connected components of a boolean image by run-length union-find. Returns (labels, count);
    label 0 = not in the mask."""
    ny, nx = mask.shape
    pad = np.zeros((ny, nx + 2), dtype=np.int8)
    pad[:, 1:-1] = mask
    d = np.diff(pad, axis=1)
    rows_s, cols_s = np.nonzero(d == 1)
    rows_e, cols_e = np.nonzero(d == -1)
    # runs [s, e) per row, already in row-major order
    n = len(rows_s)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    row_start = np.searchsorted(rows_s, np.arange(ny + 1))
    for r in range(1, ny):
        a0, a1 = row_start[r - 1], row_start[r]
        b0, b1 = row_start[r], row_start[r + 1]
        i, j = a0, b0
        while i < a1 and j < b1:
            # 8-connectivity: [s, e) runs touch if s_a <= e_b and s_b <= e_a (e exclusive, +1 diagonal)
            if cols_s[i] <= cols_e[j] and cols_s[j] <= cols_e[i]:
                ra, rb = find(i), find(j)
                if ra != rb:
                    parent[ra] = rb
            if cols_e[i] < cols_e[j]:
                i += 1
            else:
                j += 1
    roots = {}
    lab = np.zeros((ny, nx), dtype=np.int32)
    for k in range(n):
        r = find(k)
        if r not in roots:
            roots[r] = len(roots) + 1
        lab[rows_s[k], cols_s[k]:cols_e[k]] = roots[r]
    return lab, len(roots)


# ------------------------------------------------------------------------------------------- raster

class Raster:
    def __init__(self, x0, y0, x1, y1, g, layers):
        self.g = g
        self.i0, self.j0 = int(math.floor(x0 / g)), int(math.floor(y0 / g))
        self.nx, self.ny = int(math.ceil(x1 / g)) - self.i0 + 1, int(math.ceil(y1 / g)) - self.j0 + 1
        self.layers = layers
        self.trk = {L: np.full((self.ny, self.nx), EMPTY, dtype=np.int32) for L in layers}
        self.via = np.full((self.ny, self.nx), EMPTY, dtype=np.int32)
        self.area = np.zeros((self.ny, self.nx), dtype=bool)
        self.tol = g / 2

    def xs(self, i0, i1):
        return (np.arange(i0, i1) + self.i0) * self.g

    def ys(self, j0, j1):
        return (np.arange(j0, j1) + self.j0) * self.g

    def win(self, box, grow):
        """Index ranges of the cells within box grown by `grow`; None when outside."""
        g = self.g
        i0 = max(0, int(math.floor((box[0] - grow) / g)) - self.i0)
        i1 = min(self.nx, int(math.ceil((box[2] + grow) / g)) - self.i0 + 1)
        j0 = max(0, int(math.floor((box[1] - grow) / g)) - self.j0)
        j1 = min(self.ny, int(math.ceil((box[3] + grow) / g)) - self.j0 + 1)
        if i0 >= i1 or j0 >= j1:
            return None
        return i0, i1, j0, j1

    def cell(self, p):
        return int(round(p[1] / self.g)) - self.j0, int(round(p[0] / self.g)) - self.i0

    @staticmethod
    def mark(arr, sl, hit, net):
        sub = arr[sl]
        new = np.where(sub == EMPTY, net, np.where(sub == net, net, MIXED))
        arr[sl] = np.where(hit, new, sub)


def seg_dist(X, Y, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    L2 = ax * ax + ay * ay
    if L2 == 0:
        return np.hypot(X - a[0], Y - a[1])
    t = np.clip(((X - a[0]) * ax + (Y - a[1]) * ay) / L2, 0, 1)
    return np.hypot(X - a[0] - t * ax, Y - a[1] - t * ay)


def poly_dist(X, Y, pts):
    """Distance to a closed polygon, 0 inside."""
    d = np.full(X.shape, np.inf)
    ins = np.zeros(X.shape, dtype=bool)
    n = len(pts)
    for k in range(n):
        a, b = pts[k - 1], pts[k]
        d = np.minimum(d, seg_dist(X, Y, a, b))
        if (a[1] > Y).any() or (b[1] > Y).any():
            c = ((a[1] > Y) != (b[1] > Y)) & (X < a[0] + (Y - a[1]) * (b[0] - a[0]) / ((b[1] - a[1]) or 1e-12))
            ins ^= c
    d[ins] = 0.0
    return d


# ------------------------------------------------------------------------------------------- main

def run(a):
    board = pcbnew.LoadBoard(a.board)
    ox, oy = a.origin
    Lm = lambda v: (ToMM(v.x) - ox, ToMM(v.y) - oy)
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    lids = {L: layer_id(board, L) for L in a.layers}
    netid, netname = {}, []
    def nid(n):
        if n not in netid:
            netid[n] = len(netname)
            netname.append(n)
        return netid[n]
    plane = set(a.plane) if a.plane is not None else None
    is_plane = (lambda n: n in plane) if plane is not None else (lambda n: n == "GND" or n.startswith("+"))

    def cbox(ref):
        f = fps[ref]
        cy = f.GetCourtyard(pcbnew.B_CrtYd if f.GetLayer() == pcbnew.B_Cu else pcbnew.F_CrtYd)
        bb = cy.BBox() if cy.OutlineCount() else f.GetBoundingBox(False)
        return (ToMM(bb.GetLeft()) - ox, ToMM(bb.GetTop()) - oy, ToMM(bb.GetRight()) - ox, ToMM(bb.GetBottom()) - oy)

    results = {}
    groups = collections.OrderedDict()
    for ref in a.ref:
        if a.window:
            w = tuple(a.window)
        else:
            b = cbox(ref)
            w = (b[0] - a.margin, b[1] - a.margin, b[2] + a.margin, b[3] + a.margin)
        groups.setdefault(w, []).append(ref)

    for w, refs in groups.items():
        R = Raster(*w, a.grid, a.layers)
        g = a.grid
        # rule areas
        for z in board.Zones():
            if z.GetIsRuleArea() and z.GetZoneName().startswith("BGA_"):
                bb = z.GetBoundingBox()
                box = (ToMM(bb.GetLeft()) - ox, ToMM(bb.GetTop()) - oy, ToMM(bb.GetRight()) - ox, ToMM(bb.GetBottom()) - oy)
                wn = R.win(box, 0)
                if wn:
                    i0, i1, j0, j1 = wn
                    X, Y = np.meshgrid(R.xs(i0, i1), R.ys(j0, j1))
                    R.area[j0:j1, i0:i1] |= (X >= box[0]) & (X <= box[2]) & (Y >= box[1]) & (Y <= box[3])
        A = R.area
        c = np.where(A, 0.09, 0.127)
        hw = np.where(A, 0.045, 0.0508)
        rv = np.where(A, 0.15, 0.225)
        hv = np.where(A, 0.075, 0.10)
        HC = 0.2
        tol = R.tol
        trk_thr = c + hw - tol
        via_thr = c + rv - tol

        pads_of = collections.defaultdict(list)       # net -> [(ref, pad number, layer names, centre)]

        def put_shape(dist_fn, box, net, layers, hole=None):
            """dist_fn(X, Y) = distance to the copper; hole = (centre, radius) for drilled objects."""
            grow = 0.6
            wn = R.win(box, grow)
            if wn is None:
                return
            i0, i1, j0, j1 = wn
            X, Y = np.meshgrid(R.xs(i0, i1), R.ys(j0, j1))
            d = dist_fn(X, Y)
            sl = (slice(j0, j1), slice(i0, i1))
            t_trk, t_via = trk_thr[sl], via_thr[sl]
            hit_t = d < t_trk
            hit_v = d < t_via
            hit_v |= d < HC + hv[sl] - tol                   # the via's hole to this copper
            if hole is not None:
                dc = np.hypot(X - hole[0][0], Y - hole[0][1])
                hit_t |= dc < hole[1] + HC + hw[sl] - tol    # track copper to this hole
                hit_v |= dc < hole[1] + HC + rv[sl] - tol    # via copper to this hole
            for L in layers:
                if L in R.trk:
                    R.mark(R.trk[L], sl, hit_t, net)
            if layers:
                R.mark(R.via, sl, hit_v, net)

        def expand(box, m):
            return (box[0] - m, box[1] - m, box[2] + m, box[3] + m)

        wbox = expand(w, 1.0)
        inside = lambda box: not (box[2] < wbox[0] or box[0] > wbox[2] or box[3] < wbox[1] or box[1] > wbox[3])
        # tracks and vias
        for t in board.GetTracks():
            n = nid(t.GetNetname())
            if t.GetClass() == "PCB_VIA":
                p = Lm(t.GetPosition()); r = ToMM(t.GetWidth(pcbnew.F_Cu)) / 2
                box = (p[0] - r, p[1] - r, p[0] + r, p[1] + r)
                if inside(box):
                    put_shape(lambda X, Y, p=p, r=r: np.hypot(X - p[0], Y - p[1]) - r, box, n, a.layers,
                              hole=(p, ToMM(t.GetDrillValue()) / 2))
                continue
            Lname = next((L for L, i in lids.items() if i == t.GetLayer()), None)
            s, e = Lm(t.GetStart()), Lm(t.GetEnd()); h = ToMM(t.GetWidth()) / 2
            box = (min(s[0], e[0]) - h, min(s[1], e[1]) - h, max(s[0], e[0]) + h, max(s[1], e[1]) + h)
            if inside(box):
                if Lname is None:
                    continue
                put_shape(lambda X, Y, s=s, e=e, h=h: seg_dist(X, Y, s, e) - h, box, n, [Lname])
        # pads
        for f in board.GetFootprints():
            for p in f.Pads():
                n = nid(p.GetNetname()) if p.GetNetname() else nid("<nc:%s.%s>" % (f.GetReference(), p.GetNumber()))
                lays = [L for L, i in lids.items() if p.IsOnLayer(i)]
                th = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
                bb = p.GetBoundingBox()
                box = (ToMM(bb.GetLeft()) - ox, ToMM(bb.GetTop()) - oy, ToMM(bb.GetRight()) - ox, ToMM(bb.GetBottom()) - oy)
                if not inside(box):
                    continue
                if p.GetNetname():
                    pads_of[p.GetNetname()].append((f.GetReference(), p.GetNumber(), lays, Lm(p.GetPosition())))
                hole = (Lm(p.GetPosition()), ToMM(p.GetDrillSize().x) / 2) if th else None
                for L in (lays or ([] if not th else a.layers)):
                    ps = p.GetEffectivePolygon(lids[L], pcbnew.ERROR_INSIDE)
                    for k in range(ps.OutlineCount()):
                        ch = ps.Outline(k)
                        pts = [(ToMM(ch.CPoint(i).x) - ox, ToMM(ch.CPoint(i).y) - oy) for i in range(ch.PointCount())]
                        put_shape(lambda X, Y, pts=pts: poly_dist(X, Y, pts), box, n, [L], hole=hole)
                if th and not lays:
                    put_shape(lambda X, Y, hp=hole: np.hypot(X - hp[0][0], Y - hp[0][1]) - hp[1], box, n, a.layers, hole=hole)
        # keep-out areas that forbid tracks, and the board edge
        mixed_layers = {}
        rule_areas = [z for z in board.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowTracks()]
        for f in board.GetFootprints():
            rule_areas += [z for z in f.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowTracks()]
        for z in rule_areas:
            zl = [L for L, i in lids.items() if z.GetLayerSet().Contains(i)]
            for k in range(z.Outline().OutlineCount()):
                ch = z.Outline().Outline(k)
                pts = [(ToMM(ch.CPoint(i).x) - ox, ToMM(ch.CPoint(i).y) - oy) for i in range(ch.PointCount())]
                box = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
                if inside(box):
                    put_shape(lambda X, Y, pts=pts: poly_dist(X, Y, pts), box, MIXED, zl)
        out = pcbnew.SHAPE_POLY_SET()
        board.GetBoardPolygonOutlines(out, True)
        ch = out.Outline(0)
        edge = [(ToMM(ch.CPoint(i).x) - ox, ToMM(ch.CPoint(i).y) - oy) for i in range(ch.PointCount())]
        X, Y = np.meshgrid(R.xs(0, R.nx), R.ys(0, R.ny))
        ins = np.zeros(X.shape, dtype=bool)
        for k in range(len(edge)):
            a_, b_ = edge[k - 1], edge[k]
            ins ^= ((a_[1] > Y) != (b_[1] > Y)) & (X < a_[0] + (Y - a_[1]) * (b_[0] - a_[0]) / ((b_[1] - a_[1]) or 1e-12))
        bad = ~ins | (seg_free_edge(X, Y, edge) < 0.3)
        for L in a.layers:
            R.trk[L][bad] = MIXED
        R.via[bad] = MIXED

        # common free space, labelled once per layer
        lab = {}
        border = {}
        for L in a.layers:
            lab[L], _ = label(R.trk[L] == EMPTY)
            l = lab[L]
            border[L] = set(np.unique(np.concatenate([l[0], l[-1], l[:, 0], l[:, -1]]))) - {0}
        vfree = R.via == EMPTY
        tri = np.stack([lab[L][vfree] for L in a.layers], axis=1)
        tri = np.unique(tri, axis=0) if len(tri) else tri
        via_links = collections.defaultdict(set)       # (L, label) -> set of (L', label')
        for row in tri:
            nodes = [(L, int(v)) for L, v in zip(a.layers, row) if v]
            for u in nodes:
                for v in nodes:
                    if u != v:
                        via_links[u].add(v)
        via_any = set((L, int(v)) for row in tri for L, v in zip(a.layers, row) if v)

        cache = {}
        for ref in refs:
            f = fps[ref]
            res = {}
            for p in f.Pads():
                net = p.GetNetname()
                if not net or net.startswith("unconnected"):
                    continue
                if net not in cache:
                    cache[net] = net_graph(R, a, lab, nid(net), pads_of.get(net, []))
                res[p.GetNumber()] = check_pad(R, a, lab, border, via_links, via_any, cache[net], ref, p, lids,
                                               is_plane(net), Lm)
                if a.debug and a.debug[0] == "%s.%s" % (ref, p.GetNumber()):
                    paint(R, a, lab, cache[net], res[p.GetNumber()].pop("_dist"), nid(net), a.debug[1])
                res[p.GetNumber()].pop("_dist", None)
            results[ref] = res
    return results, netname


def seg_free_edge(X, Y, edge):
    d = np.full(X.shape, np.inf)
    for k in range(len(edge)):
        d = np.minimum(d, seg_dist(X, Y, edge[k - 1], edge[k]))
    return d


def net_graph(R, a, lab, n, pads):
    """Cells owned by net n alone (around its own pads, tracks and vias) as blobs per layer, with their links
    to the common free components, to each other through vias of this net, to the boundary, and the parts
    whose pads they hold."""
    G = {"blob_of": {}, "links": collections.defaultdict(set), "border": set(), "via": set(),
         "pads": collections.defaultdict(set)}
    for L in a.layers:
        own = R.trk[L] == n
        if not own.any():
            continue
        bl, nb = label(own)
        for dj in (-1, 0, 1):
            for di in (-1, 0, 1):
                if dj == 0 and di == 0:
                    continue
                src = np.zeros_like(bl)
                ys_ = slice(max(dj, 0), bl.shape[0] + min(dj, 0)); yd = slice(max(-dj, 0), bl.shape[0] + min(-dj, 0))
                xs_ = slice(max(di, 0), bl.shape[1] + min(di, 0)); xd = slice(max(-di, 0), bl.shape[1] + min(-di, 0))
                src[ys_, xs_] = bl[yd, xd]
                m = (src > 0) & (lab[L] > 0)
                if m.any():
                    for b_, k_ in set(zip(src[m].tolist(), lab[L][m].tolist())):
                        G["links"][(L, "b", b_)].add((L, k_))
                        G["links"][(L, k_)].add((L, "b", b_))
        for b_ in set(np.unique(np.concatenate([bl[0], bl[-1], bl[:, 0], bl[:, -1]]))) - {0}:
            G["border"].add((L, "b", int(b_)))
        G["blob_of"][L] = bl
    ov = R.via == n
    if ov.any():
        jj, ii = np.nonzero(ov)
        seen = set()
        for j, i in zip(jj.tolist(), ii.tolist()):
            nodes = []
            for L2 in a.layers:
                if R.trk[L2][j, i] == EMPTY:
                    nodes.append((L2, int(lab[L2][j, i])))
                elif R.trk[L2][j, i] == n and L2 in G["blob_of"]:
                    nodes.append((L2, "b", int(G["blob_of"][L2][j, i])))
            key = tuple(nodes)
            if key in seen:
                continue
            seen.add(key)
            for u in nodes:
                G["via"].add(u)
                for v in nodes:
                    if u != v:
                        G["links"][u].add(v)
    for ref, num, lays, c in pads:
        for L in lays:
            if L in G["blob_of"]:
                j, i = R.cell(c)
                if 0 <= j < R.ny and 0 <= i < R.nx and G["blob_of"][L][j, i]:
                    G["pads"][(L, "b", int(G["blob_of"][L][j, i]))].add(ref)
    return G


def check_pad(R, a, lab, border, via_links, via_any, G, ref, pad, lids, plane, Lm):
    own_layers = [L for L, i in lids.items() if pad.IsOnLayer(i)]
    c0 = Lm(pad.GetPosition())
    starts = []
    for L in own_layers:
        if L in G["blob_of"]:
            j, i = R.cell(c0)
            if 0 <= j < R.ny and 0 <= i < R.nx and G["blob_of"][L][j, i]:
                starts.append((L, "b", int(G["blob_of"][L][j, i])))
    if not starts:
        return {"status": "blocked", "vias": None, "why": "pad centre not free for its own net"}
    # 0-1 BFS: moving between a blob and a common component on one layer costs 0, a via costs 1
    dist = {s: 0 for s in starts}
    dq = collections.deque(starts)
    best = {}
    while dq:
        u = dq.popleft()
        d = dist[u]
        partners = [r for r in G["pads"].get(u, ()) if r != ref]
        if partners and "local" not in best:
            best["local"] = (d, sorted(partners)[0])
        if (u in G["border"] or (len(u) == 2 and u[1] in border[u[0]])) and "out" not in best:
            best["out"] = (d, u[0])
        if plane and "plane" not in best and (u in via_any or u in G["via"]):
            best["plane"] = (d + 1, u[0])
        nbrs = [(v, 0 if v[0] == u[0] else 1) for v in G["links"].get(u, ())]
        if len(u) == 2:
            nbrs += [(v, 1) for v in via_links.get(u, ())]
        for v, w_ in nbrs:
            nd = d + w_
            if nd <= a.max_vias and nd < dist.get(v, 99):
                dist[v] = nd
                (dq.appendleft if w_ == 0 else dq.append)(v)
    for k in (("plane", "local", "out") if plane else ("local", "out")):
        if k in best and best[k][0] <= a.max_vias:
            return {"status": k, "vias": best[k][0], "via_layer_or_partner": best[k][1], "_dist": dist}
    return {"status": "blocked", "vias": None, "_dist": dist}


def paint(R, a, lab, G, dist, n, path):
    from PIL import Image
    cols = {0: (60, 170, 60), 1: (230, 200, 40), 2: (240, 130, 30)}
    tiles = []
    for L in a.layers:
        img = np.zeros((R.ny, R.nx, 3), dtype=np.uint8)
        t = R.trk[L]
        img[(t != EMPTY) & (t != n)] = (40, 40, 40)
        img[(t == EMPTY) | (t == n)] = (200, 200, 200)
        for node, d in sorted(dist.items(), key=lambda kv: -kv[1]):
            if node[0] != L:
                continue
            m = (lab[L] == node[1]) if len(node) == 2 else (G["blob_of"][L] == node[2])
            img[m] = cols.get(d, (200, 60, 60))
        tiles.append(img)
    gap = np.full((R.ny, 6, 3), 255, dtype=np.uint8)
    out = np.concatenate([x for t in tiles for x in (t, gap)][:-1], axis=1)
    Image.fromarray(out).save(path)


def report(results):
    for ref, res in results.items():
        cnt = collections.Counter((r["status"], r["vias"]) for r in res.values())
        parts = ["%s%s %d" % (s, "" if v in (None, 0) else "+%dvia" % v, k) for (s, v), k in sorted(cnt.items(), key=lambda x: (x[0][0], x[0][1] or 0))]
        blk = sorted(p for p, r in res.items() if r["status"] == "blocked")
        print("%-6s pads %3d: %s%s" % (ref, len(res), ", ".join(parts), ("  BLOCKED: " + " ".join(blk)) if blk else ""))


def main(argv):
    a = opts(argv)
    results, _ = run(a)
    report(results)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=1)
    return 1 if any(r["status"] == "blocked" for res in results.values() for r in res.values()) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
