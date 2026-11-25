"""Ground stitching vias (finishing stop 8, FIN-4 step 1; run through finishing.finish stitch / pieces).

    -m Tools.KiCadDesignTools.finishing.finish <board dir> stitch <refilled board> <out> [--pieces]
    -m Tools.KiCadDesignTools.finishing.finish <board dir> pieces <refilled board> <out> <name>

The ground plane layers carry no pour pieces; the ground pours of the pour layers ([finish] pour_layers: the outer
ones of the copper sketch, the inner ones of finishing.pour) hang on vias. This adds through vias of the ground net
(size / drill of [finish.stitch] via):
  1. every pour piece of at least piece_min mm2: a long thin one (longer than long, mean width area / length under
     thin) gets one within end_r of each of its two ends (the farthest pair of its points) where none is; then one
     held by fewer than two vias / through-hole ground pads gets one at the legal point farthest from its existing
     anchor (the end of a finger);
  2. then greedy coverage: every point of the ground pours should lie within D of a ground via (anchor), D = d_open
     in open pour, d_dense within edge_band of the board edge and in the dense boxes, d_rim along a pour piece's rim;
     the candidate that covers the most uncovered pour is taken until no candidate covers min_gain mm2.
A piece (or a long piece's end) where no legal site is found is listed in stitch.txt ("no legal site"); `finish clean
<board> <out> anchor` then takes an inner piece that nothing holds away with a keep-out.
A candidate point is legal when (all measured on a raster of 0.05 mm, from KiCad's saved fill):
  - its via (r = size / 2) lies inside the ground fill of a pour layer with gnd_in of fill round it, and on the outer
    layers no copper of another net within r + outer (pour clearance) where it is not in the ground fill;
  - on the inner signal layers no copper of another net within r + lane (so it does not take a lane);
  - on the power plane it lies inside a power fill with r + plane_web of fill round it (no notch in a block edge, no
    chain with other vias' antipads) and outside the feed_keep boxes (the BGA feed tongues);
  - no pad of any net (any side) within r + pad; not inside a courtyard (top or bottom) grown by crt; not in a rule
    area (the BGA areas of place.toml [rule_areas], their no-pour areas, footprint keep-outs, the fiducials'
    keep-outs); not near the crystals (courtyards of xtal_refs grown by xtal_grow); board edge >= edge; other vias:
    centre distance >= r + r_other + via_gap (ground vias >= gnd_spacing); not in the silkscreen's label boxes
    (finishing.silk.reserved).

board.toml [finish.stitch] holds the values named above; [finish] pour_layers; [power] ground; plane layers from the
layer roles. setup(cfg) first (it sets up finishing.silk too).
"""
import json, math, os, re, sys
import numpy as np

from Tools.KiCadDesignTools.core import uuids

RES = 20                                   # px per mm
GRID = 0.5                                 # candidate grid (mm)


def setup(cfg):
    """The board's values (board.toml, place.toml, silk.toml) as this module's globals."""
    from Tools.KiCadDesignTools.copper.power_ties import power_plane
    from Tools.KiCadDesignTools.finishing import silk
    global OX, OY, VIA, R_VIA, GND_IN, OUTER, LANE, PAD, CRT, EDGE, L5_WEB, VIA_GAP, GND_SPACING, D_OPEN, D_DENSE, D_RIM
    global EDGE_BAND, MIN_GAIN, PIECE_MIN, LONG, THIN, END_R, DENSE, FEED_KEEP, XTAL_REFS, XTAL_GROW, GND, POUR_K, PLANE_K
    global PWR_K, BGA_AREAS
    s = cfg.need("finish.stitch")
    OX, OY = cfg.origin
    VIA = s["via"]                                             # {size, drill}
    R_VIA = s["via"]["size"] / 2
    GND_IN = s["gnd_in"]
    OUTER, LANE, PAD, CRT, EDGE = s["outer"], s["lane"], s["pad"], s["crt"], s["edge"]
    L5_WEB = s["plane_web"]
    VIA_GAP, GND_SPACING = s["via_gap"], s["gnd_spacing"]
    D_OPEN, D_DENSE, D_RIM = s["d_open"], s["d_dense"], s["d_rim"]
    EDGE_BAND = s["edge_band"]
    MIN_GAIN = s["min_gain"]                                   # mm2 of uncovered pour a new via must cover
    PIECE_MIN = s["piece_min"]                                 # mm2: smaller pieces are left as they are (listed)
    LONG, THIN, END_R = s["long"], s["thin"], s["end_r"]       # long and thin: a via within END_R of each end
    DENSE = {k: tuple(v) for k, v in s["dense"].items()}       # local mm boxes (x0, y0, x1, y1)
    FEED_KEEP = {k: tuple(v) for k, v in s["feed_keep"].items()}
    XTAL_REFS = tuple(s["xtal_refs"])
    XTAL_GROW = s["xtal_grow"]
    GND = cfg.need("power.ground")
    POUR_K = [int(L[1:]) - 1 for L in cfg.need("finish.pour_layers")]   # copper layer indexes (L1 = 0)
    PLANE_K = [int(L[1:]) - 1 for L in cfg.plane_layers()]
    PWR_K = int(power_plane(cfg)[1:]) - 1
    BGA_AREAS = {a["name"] for a in cfg.datafile("place.toml")["rule_areas"]["areas"]}
    silk.setup(cfg)


def board_box(b):
    import pcbnew
    bb = b.GetBoardEdgesBoundingBox()
    mm = pcbnew.ToMM
    return mm(bb.GetLeft()) - OX, mm(bb.GetTop()) - OY, mm(bb.GetRight()) - OX, mm(bb.GetBottom()) - OY


class Raster:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0 = x0, y0
        self.w, self.h = int(math.ceil((x1 - x0) * RES)) + 1, int(math.ceil((y1 - y0) * RES)) + 1

    def px(self, x, y):
        return ((x - self.x0) * RES, (y - self.y0) * RES)

    def new(self):
        from PIL import Image
        return Image.new("1", (self.w, self.h), 0)

    @staticmethod
    def arr(img):
        return np.array(img, dtype=bool)


def disc_offsets(r):
    k = int(math.ceil(r * RES))
    return [(dx, dy) for dx in range(-k, k + 1) for dy in range(-k, k + 1) if dx * dx + dy * dy <= (r * RES) ** 2]


def dilate(a, r):
    """a grown by a disc of radius r mm"""
    if r <= 0:
        return a.copy()
    out = a.copy()
    k = int(math.ceil(r * RES))
    rr = (r * RES) ** 2
    H, W = a.shape
    for dy in range(-k, k + 1):
        for dx in range(-k, k + 1):
            if dx * dx + dy * dy > rr or (dx == 0 and dy == 0):
                continue
            ys, yd = (slice(0, H - dy), slice(dy, H)) if dy >= 0 else (slice(-dy, H), slice(0, H + dy))
            xs, xd = (slice(0, W - dx), slice(dx, W)) if dx >= 0 else (slice(-dx, W), slice(0, W + dx))
            out[yd, xd] |= a[ys, xs]
    return out


def erode(a, r):
    return ~dilate(~a, r)


def scene(path):
    """Read the board (with its saved fill) into rasters and lists. -> dict"""
    import pcbnew
    from PIL import ImageDraw
    b = pcbnew.LoadBoard(path)
    mm = pcbnew.ToMM
    ids = list(b.GetEnabledLayers().CuStack())
    bx = board_box(b)
    R = Raster(bx[0] - 0.5, bx[1] - 0.5, bx[2] + 0.5, bx[3] + 0.5)
    Pp = lambda v: R.px(mm(v.x) - OX, mm(v.y) - OY)
    gnd = {}
    foreign = {}
    fills = {}
    draw_g, draw_f = {}, {}
    for k, lid in enumerate(ids):
        gnd[k], foreign[k] = R.new(), R.new()
        draw_g[k], draw_f[k] = ImageDraw.Draw(gnd[k]), ImageDraw.Draw(foreign[k])
    pieces = {k: [] for k in POUR_K}                   # ground pour pieces per pour layer: list of point lists (px)
    l5 = R.new(); d5 = ImageDraw.Draw(l5)
    for z in b.Zones():
        if z.GetIsRuleArea():
            continue
        for k, lid in enumerate(ids):
            if not z.IsOnLayer(lid):
                continue
            f = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(lid))
            f.Fracture()
            for i in range(f.OutlineCount()):
                o = f.Outline(i)
                pts = [Pp(o.CPoint(j)) for j in range(o.PointCount())]
                if len(pts) < 3:
                    continue
                if z.GetNetname() == GND:
                    draw_g[k].polygon(pts, fill=1)
                    if k in pieces and not z.IsTeardropArea():
                        pieces[k].append(pts)
                else:
                    draw_f[k].polygon(pts, fill=1)
                    if k == PWR_K:
                        d5.polygon(pts, fill=1)
    vias = []
    for t in b.GetTracks():
        net = t.GetNetname()
        if t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            vias.append((mm(p.x) - OX, mm(p.y) - OY, mm(t.GetWidth(pcbnew.F_Cu)) / 2, mm(t.GetDrillValue()) / 2, net))
            continue
        k = ids.index(t.GetLayer())
        w = mm(t.GetWidth()) * RES
        dr = draw_g[k] if net == GND else draw_f[k]
        if t.Type() == pcbnew.PCB_ARC_T:
            a = pcbnew.Cast_to_PCB_ARC(t) if hasattr(pcbnew, "Cast_to_PCB_ARC") else t
            s, m, e = a.GetStart(), a.GetMid(), a.GetEnd()
            pts = arc_points((mm(s.x), mm(s.y)), (mm(m.x), mm(m.y)), (mm(e.x), mm(e.y)))
            seq = [R.px(x - OX, y - OY) for x, y in pts]
        else:
            seq = [Pp(t.GetStart()), Pp(t.GetEnd())]
        dr.line(seq, fill=1, width=max(1, int(round(w))))
        for q in (seq[0], seq[-1]):
            dr.ellipse([q[0] - w / 2, q[1] - w / 2, q[0] + w / 2, q[1] + w / 2], fill=1)
    pads, anchors_pad = [], []
    pad_img = R.new(); dp = ImageDraw.Draw(pad_img)
    crt = R.new(); dc = ImageDraw.Draw(crt)
    xtal = R.new(); dx_ = ImageDraw.Draw(xtal)
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        for p in fp.Pads():
            for k, lid in enumerate(ids):
                if not p.IsOnLayer(lid):
                    continue
                try:
                    o = p.GetEffectivePolygon(lid, pcbnew.ERROR_INSIDE).Outline(0)
                except Exception:
                    continue
                pts = [Pp(o.CPoint(j)) for j in range(o.PointCount())]
                if k in (0, len(ids) - 1):
                    dp.polygon(pts, fill=1)
                (draw_g[k] if p.GetNetname() == GND else draw_f[k]).polygon(pts, fill=1)
            if p.HasHole():
                q = p.GetPosition()
                hr = max(mm(p.GetDrillSize().x), mm(p.GetDrillSize().y)) / 2
                c = Pp(q)
                dp.ellipse([c[0] - hr * RES, c[1] - hr * RES, c[0] + hr * RES, c[1] + hr * RES], fill=1)
                if p.GetNetname() == GND:           # with its reach: the fill meets it by thermal spokes
                    sz = p.GetSize(pcbnew.F_Cu)
                    anchors_pad.append((mm(q.x) - OX, mm(q.y) - OY, ref + "." + p.GetNumber(), max(mm(sz.x), mm(sz.y)) / 2 + 0.3))
        for lay in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            cy = fp.GetCourtyard(lay)
            for i in range(cy.OutlineCount()):
                o = cy.Outline(i)
                pts = [Pp(o.CPoint(j)) for j in range(o.PointCount())]
                if len(pts) >= 3:
                    dc.polygon(pts, fill=1)
                    if ref in XTAL_REFS:
                        dx_.polygon(pts, fill=1)
    ko = R.new(); dk = ImageDraw.Draw(ko)
    areas = [z for z in b.Zones() if z.GetIsRuleArea()]
    for fp in b.GetFootprints():
        areas += [z for z in fp.Zones() if z.GetIsRuleArea()]
    names = []
    for z in areas:
        if not (z.GetDoNotAllowVias() or z.GetDoNotAllowZoneFills() or z.GetDoNotAllowTracks()
                or z.GetZoneName() in BGA_AREAS):
            continue
        names.append(z.GetZoneName() or "(footprint keep-out)")
        o = z.Outline()
        for i in range(o.OutlineCount()):
            ch = o.Outline(i)
            dk.polygon([Pp(ch.CPoint(j)) for j in range(ch.PointCount())], fill=1)
    edge = R.new(); de = ImageDraw.Draw(edge)
    ol = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(ol, True)
    for i in range(ol.OutlineCount()):
        ch = ol.Outline(i)
        de.polygon([Pp(ch.CPoint(j)) for j in range(ch.PointCount())], fill=1)
    from Tools.KiCadDesignTools.finishing import silk
    labels = silk.reserved(b)
    return {"labels": labels, "R": R, "gnd": {k: R.arr(v) for k, v in gnd.items()}, "foreign": {k: R.arr(v) for k, v in foreign.items()},
            "l5": R.arr(l5), "pads": R.arr(pad_img), "crt": R.arr(crt), "xtal": R.arr(xtal), "ko": R.arr(ko),
            "inside": R.arr(edge), "vias": vias, "anchors_pad": anchors_pad, "pieces": pieces, "areas": names,
            "nlayers": len(ids)}


def arc_points(s, m, e, n=12):
    (ax, ay), (bx, by), (cx, cy) = s, m, e
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return [s, e]
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    a0, a1, am = (math.atan2(p[1] - uy, p[0] - ux) for p in (s, e, m))
    def norm(a):
        return a % (2 * math.pi)
    sweep = norm(a1 - a0)
    if not (norm(am - a0) <= sweep):
        sweep -= 2 * math.pi
    return [(ux + r * math.cos(a0 + sweep * i / n), uy + r * math.sin(a0 + sweep * i / n)) for i in range(n + 1)]


def legal_mask(S, xtal_box=True):
    """Pixels where the centre of a new 0.45 mm ground via may go."""
    g1, g6, f = S["gnd"][0], S["gnd"][S["nlayers"] - 1], S["foreign"]
    L6 = S["nlayers"] - 1
    ok = erode(S["inside"], EDGE)
    in1, in6 = erode(g1, R_VIA + GND_IN), erode(g6, R_VIA + GND_IN)
    inner = np.zeros_like(in1)
    for k in S["pieces"]:
        if k not in (0, L6):
            inner |= erode(S["gnd"][k], R_VIA + GND_IN)
    ok &= in1 | in6 | inner
    for k in (0, L6):                                          # outer layers: clear of other nets where not in own pour
        gin = in1 if k == 0 else in6
        ok &= gin | ~dilate(f[k], R_VIA + OUTER)
    for k in range(1, L6):
        if k in PLANE_K:                                       # the ground and power planes (the power plane below)
            continue
        ok &= ~dilate(f[k], R_VIA + LANE)
    ok &= erode(S["l5"], R_VIA + L5_WEB)
    ok &= ~dilate(S["pads"], R_VIA + PAD)
    ok &= ~dilate(S["crt"], CRT)
    ok &= ~dilate(S["ko"], R_VIA)
    ok &= ~dilate(S["xtal"], XTAL_GROW)
    R = S["R"]
    H, W = ok.shape
    yy, xx = np.mgrid[0:H, 0:W]
    X, Y = xx / RES + R.x0, yy / RES + R.y0
    for x0, y0, x1, y1 in list(FEED_KEEP.values()) + S.get("labels", []):
        ok &= ~((X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1))
    from PIL import Image, ImageDraw
    img = Image.new("1", (W, H), 0)
    dv = ImageDraw.Draw(img)
    for x, y, r, dr, net in S["vias"]:
        gap = (GND_SPACING if net == GND else r + R_VIA + VIA_GAP) * RES
        cx, cy = R.px(x, y)
        dv.ellipse([cx - gap, cy - gap, cx + gap, cy + gap], fill=1)
    ok &= ~np.array(img, dtype=bool)
    return ok, X, Y


def dense_radius(X, Y, inside):
    """Required coverage radius per pixel."""
    D = np.full(X.shape, D_OPEN)
    ys, xs = np.nonzero(inside)                                 # the board is a rectangle (R2 corners)
    bx0, bx1, by0, by1 = xs.min() / RES, xs.max() / RES, ys.min() / RES, ys.max() / RES
    gx, gy = X - X.min(), Y - Y.min()
    near_edge = (gx < bx0 + EDGE_BAND) | (gx > bx1 - EDGE_BAND) | (gy < by0 + EDGE_BAND) | (gy > by1 - EDGE_BAND)
    D[near_edge] = D_DENSE
    for x0, y0, x1, y1 in DENSE.values():
        D[(X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1)] = D_DENSE
    return D


def piece_masks(S, k):
    from PIL import Image, ImageDraw
    R = S["R"]
    out = []
    for pts in S["pieces"][k]:
        img = Image.new("1", (R.w, R.h), 0)
        ImageDraw.Draw(img).polygon(pts, fill=1)
        out.append(np.array(img, dtype=bool))
    return out


def anchors(S):
    a = [(x, y) for x, y, r, dr, net in S["vias"] if net == GND]
    return a + [(x, y) for x, y, ref, reach in S["anchors_pad"]]


def anchors_reach(S):
    """[(x, y, reach)]: ground vias (0) and through-hole ground pads (the pad's half size + 0.3: thermal spokes)"""
    return [(x, y, 0.0) for x, y, r, dr, net in S["vias"] if net == GND] + [(x, y, reach) for x, y, ref, reach in S["anchors_pad"]]


def in_piece(m, x, y, R, reach=0.0):
    """Does piece mask m hold (x, y), or with reach any point within that square round it?"""
    px, py = int(round((x - R.x0) * RES)), int(round((y - R.y0) * RES))
    k = int(math.ceil(reach * RES))
    y0, y1, x0, x1 = max(0, py - k), min(m.shape[0], py + k + 1), max(0, px - k), min(m.shape[1], px + k + 1)
    return y1 > y0 and x1 > x0 and bool(m[y0:y1, x0:x1].any())


def ends_of(m, R):
    """The two far ends of a piece (the point farthest from its centroid, then the one farthest from that), length."""
    ys, xs = np.nonzero(m)
    X, Y = xs / RES + R.x0, ys / RES + R.y0
    i = int(np.argmax((X - X.mean()) ** 2 + (Y - Y.mean()) ** 2))
    j = int(np.argmax((X - X[i]) ** 2 + (Y - Y[i]) ** 2))
    return (float(X[i]), float(Y[i])), (float(X[j]), float(Y[j])), float(math.hypot(X[j] - X[i], Y[j] - Y[i]))


def piece_table(S):
    """[(layer index, piece index, area mm2, anchors inside, bbox, mask)]"""
    R = S["R"]
    A = anchors_reach(S)
    rows = []
    for k in sorted(S["pieces"]):
        for i, m in enumerate(piece_masks(S, k)):
            area = m.sum() / RES / RES
            n = sum(1 for x, y, reach in A if in_piece(m, x, y, R, reach))
            ys, xs = np.nonzero(m)
            bb = (xs.min() / RES + R.x0, ys.min() / RES + R.y0, xs.max() / RES + R.x0, ys.max() / RES + R.y0) if len(xs) else (0, 0, 0, 0)
            rows.append((k, i, area, n, bb, m))
    return rows


def pieces_report(path, out, name):
    S = scene(path)
    rows = piece_table(S)
    lines = ["%s pour pieces of %s (%s): layer, area mm2, ground anchors (vias and through-hole ground pads), bbox local mm" % (
        GND, os.path.basename(path), ", ".join("L%d" % (k + 1) for k in sorted(S["pieces"])))]
    hist = {}
    for k, i, area, n, bb, m in rows:
        L = "L%d" % (k + 1)
        hist.setdefault(L, {}).setdefault(min(n, 3), 0)
        hist[L][min(n, 3)] += 1
        lines.append("%s %3d  %8.2f  %3d  (%.1f, %.1f)-(%.1f, %.1f)" % (L, i, area, n, *bb))
    summ = "; ".join("%s: %d pieces, with 0 / 1 / 2 / 3+ anchors: %s" % (L, sum(h.values()), " / ".join(str(h.get(c, 0)) for c in range(4)))
                     for L, h in sorted(hist.items()))
    lines.insert(1, summ)
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "pieces_%s.txt" % name), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    json.dump({L: {str(c): v for c, v in h.items()} for L, h in hist.items()}, open(os.path.join(out, "pieces_%s.json" % name), "w"))
    print("pieces (%s): %s" % (name, summ))


def write_vias(path, pts):
    text = open(path, encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in text else "\n"
    blocks = []
    keys = uuids.Keys()                       # uuid key: the via's position in the file
    for x, y in pts:
        uid = uuids.make(keys.unique("stitch:via:%s,%s" % (fmt(x + OX), fmt(y + OY))))
        blocks.append(nl.join(["\t(via", "\t\t(at %s %s)" % (fmt(x + OX), fmt(y + OY)), "\t\t(size %s)" % VIA["size"], "\t\t(drill %s)" % VIA["drill"],
                               '\t\t(layers "F.Cu" "B.Cu")', '\t\t(net "%s")' % GND, '\t\t(uuid "%s")' % uid, "\t)"]))
    k = text.rstrip().rfind(")")
    text = text[:k] + nl.join(blocks) + nl + text[k:]
    open(path, "w", encoding="utf-8", newline="").write(text)


def fmt(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return s


def main(path, out, pieces_only=False):
    """pieces_only: a second pass after the refill, for the pieces the first pass's vias created or left with one via"""
    from Tools.KiCadDesignTools.finishing import finish
    S = scene(path)
    R = S["R"]
    ok, X, Y = legal_mask(S)
    L6 = S["nlayers"] - 1
    PL = sorted(S["pieces"])                                   # the pour layers
    pour = S["gnd"][0] & ~dilate(S["ko"], 0) | S["gnd"][L6]
    D = dense_radius(X, Y, S["inside"])
    # rim of every piece (within 0.5 mm of its edge) asks for D_RIM where that is tighter
    rim = np.zeros_like(pour)
    for k in PL:
        rim |= S["gnd"][k] & ~erode(S["gnd"][k], 0.5)
    D = np.where(rim, np.minimum(D, D_RIM), D)
    step = int(round(0.5 * RES))
    samp = np.zeros_like(pour); samp[::step, ::step] = True
    sl = [samp & S["gnd"][k] for k in PL]
    sy = np.concatenate([np.nonzero(a)[0] for a in sl])
    sx = np.concatenate([np.nonzero(a)[1] for a in sl])
    SX, SY = sx / RES + R.x0, sy / RES + R.y0
    SD = D[sy, sx]
    A = anchors(S)
    cov = np.zeros(len(SX), dtype=bool)
    for x, y in A:
        cov |= (SX - x) ** 2 + (SY - y) ** 2 <= SD ** 2
    cov0 = cov.copy()
    cstep = int(round(GRID * RES))
    cm = np.zeros_like(ok); cm[::cstep, ::cstep] = True
    cy, cx = np.nonzero(ok & cm)
    CX, CY = cx / RES + R.x0, cy / RES + R.y0
    alive = np.ones(len(CX), dtype=bool)
    added, why, stuck = [], [], []

    def take(i, reason):
        x, y = float(round(CX[i], 3)), float(round(CY[i], 3))
        added.append((x, y)); why.append(reason)
        cov[:] |= (SX - x) ** 2 + (SY - y) ** 2 <= SD ** 2
        alive[(CX - x) ** 2 + (CY - y) ** 2 < GND_SPACING ** 2] = False
    AR = anchors_reach(S)
    # 1. long thin pieces: a via near each end; then pieces with fewer than two anchors
    for k, i, area, n, bb, m in piece_table(S):
        if area < PIECE_MIN:
            continue
        held = lambda: [(x, y) for x, y, reach in AR if in_piece(m, x, y, R, reach)] + [(x, y) for x, y in added if in_piece(m, x, y, R)]
        e0, e1, length = ends_of(m, R)
        if length > LONG and area / length < THIN:
            for ex, ey in (e0, e1):
                if any(math.hypot(x - ex, y - ey) <= END_R for x, y in held()):
                    continue
                inside = alive & m[cy, cx]
                d = (CX - ex) ** 2 + (CY - ey) ** 2
                if inside.any() and d[inside].min() <= (length / 2) ** 2:
                    j = int(np.argmin(np.where(inside, d, np.inf)))
                    take(j, "end of long piece L%d #%d (%.1f mm long, %.1f mm2; end (%.2f, %.2f), %.2f mm away)" % (
                        k + 1, i, length, area, ex, ey, math.sqrt(d[j])))
                else:
                    stuck.append("L%d #%d (%.1f mm2, %.1f mm long): none near its end (%.2f, %.2f)" % (k + 1, i, area, length, ex, ey))
        pts = held()
        if len(pts) >= 2:
            continue
        inside = alive & m[cy, cx]
        if not inside.any():
            if not pts:
                stuck.append("L%d #%d (%.1f mm2) at (%.2f, %.2f)-(%.2f, %.2f): no anchor" % (k + 1, i, area, *bb))
            continue
        if pts:
            dist = np.min([(CX - x) ** 2 + (CY - y) ** 2 for x, y in pts], axis=0)
        else:
            dist = np.zeros(len(CX))
        j = int(np.argmax(np.where(inside, dist, -1)))
        if not pts or dist[j] >= 1.5 ** 2:
            take(j, "piece L%d #%d (%.1f mm2, %d anchor%s)" % (k + 1, i, area, len(pts), "" if len(pts) == 1 else "s"))
    # 2. greedy coverage (lazy: a candidate's gain only falls as vias are added)
    import heapq
    if pieces_only:
        alive[:] = False
    unc_idx = np.nonzero(~cov)[0]
    cell = {}
    for k in unc_idx:
        cell.setdefault((int(SX[k]), int(SY[k])), []).append(k)
    dmax = float(SD.max())
    reach = int(math.ceil(dmax))
    near = {}
    for i in np.nonzero(alive)[0]:
        cx_, cy_ = int(CX[i]), int(CY[i])
        ks = [k for gx in range(cx_ - reach, cx_ + reach + 1) for gy in range(cy_ - reach, cy_ + reach + 1) for k in cell.get((gx, gy), ())]
        if not ks:
            continue
        ks = np.array(ks)
        ks = ks[(SX[ks] - CX[i]) ** 2 + (SY[ks] - CY[i]) ** 2 <= SD[ks] ** 2]
        if len(ks):
            near[i] = ks
    heap = [(-len(v), i) for i, v in near.items()]
    heapq.heapify(heap)
    while heap:
        g, i = heapq.heappop(heap)
        if not alive[i]:
            continue
        gain = int((~cov[near[i]]).sum())
        if gain * 0.25 < MIN_GAIN:
            if -g * 0.25 < MIN_GAIN:
                break
            continue
        if heap and gain < -heap[0][0]:
            heapq.heappush(heap, (-gain, i))
            continue
        take(i, "coverage %.1f mm2" % (gain * 0.25))
    write_vias(path, added)
    rec = finish.record(path)
    rec["vias"] = (rec.get("vias", []) if pieces_only else []) + added
    finish.save_record(path, rec)
    os.makedirs(out, exist_ok=True)
    total = len(SX)
    with open(os.path.join(out, "stitch2.txt" if pieces_only else "stitch.txt"), "w", encoding="utf-8") as f:
        f.write("ground stitching vias added: %d (%s / %s, F.Cu-B.Cu)\n" % (len(added), VIA["size"], VIA["drill"]))
        f.write("pour sample points (0.5 mm grid, %s): %d; within reach of a ground via before %.1f %%, after %.1f %%\n"
                % (" + ".join("L%d" % (k + 1) for k in PL), total, 100.0 * cov0.sum() / total, 100.0 * cov.sum() / total))
        names = sorted(set(S["areas"]))
        f.write("rule areas avoided: %s%s\n" % (", ".join(n for n in names if not n.startswith(("FIN_KO_", "FIN_TUNE_"))),
                "; %d serpentine keep-outs (FIN_TUNE_*), %d clean-up keep-outs (FIN_KO_*)" % (
                    sum(1 for n in names if n.startswith("FIN_TUNE_")), sum(1 for n in names if n.startswith("FIN_KO_")))))
        for (x, y), w in zip(added, why):
            f.write("  (%.3f, %.3f)  %s\n" % (x, y, w))
        for l in stuck:
            f.write("  no legal site: %s\n" % l)
    print("stitch%s: %d ground vias added; pour within reach of a ground via %.1f %% -> %.1f %%; no legal site: %d (%s)" % (
          " (second pass, pieces)" if pieces_only else "", len(added), 100.0 * cov0.sum() / total, 100.0 * cov.sum() / total, len(stuck),
          os.path.join(out, "stitch2.txt" if pieces_only else "stitch.txt")))
