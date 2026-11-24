"""Ground stitching vias of the STM32H743 + SDRAM board (finish.py stitch / pieces; stop 8, FIN-4 step 1).

Ground has one plane (L2); the L1 and L6 ground pours hang on vias. This adds 0.45 / 0.2 through vias of GND:
  1. every pour piece (L1 or L6) of at least PIECE_MIN mm2 that is held by fewer than two vias / through-hole ground
     pads gets one at the legal point farthest from its existing anchor (the end of a finger);
  2. then greedy coverage: every point of the two ground pours should lie within D of a ground via (anchor), D = D_OPEN
     in open pour, D_DENSE within EDGE_BAND of the board edge and in the DENSE boxes (Ethernet, audio, the two
     switching regulators), D_RIM along a pour piece's rim; the candidate that covers the most uncovered pour is
     taken until no candidate covers MIN_GAIN mm2.
A candidate point is legal when (all measured on a raster of 0.05 mm, from KiCad's saved fill):
  - its via (r 0.225) lies inside the GND fill of L1 or of L6 with GND_IN of fill round it, and on L1 and L6 no copper
    of another net within r + OUTER (pour clearance) where it is not in the GND fill;
  - on L3 / L4 (signal layers) no copper of another net within r + LANE (so it does not take a lane);
  - on L5 it lies inside a power fill with r + L5_WEB of fill round it (no notch in a block edge, no chain with other
    vias' antipads) and outside the two BGA feed tongues (FEED_KEEP);
  - no pad of any net (any side) within r + PAD; not inside a courtyard (top or bottom) grown by CRT; not in a rule area
    (the BGA areas, their no-pour areas, footprint keep-outs, the fiducials' keep-outs); not in the crystals' L1 area
    (XTAL boxes); board edge >= EDGE; other vias: centre distance >= r + r_other + VIA_GAP (GND vias >= GND_SPACING).
"""
import json, math, os, re, sys, uuid
import numpy as np

OX, OY = 100.0, 100.0
RES = 20                                   # px per mm
R_VIA, DRILL = 0.225, 0.2
GND_IN = 0.05
OUTER, LANE, PAD, CRT, EDGE = 0.2, 0.25, 0.25, 0.1, 0.8
L5_WEB = 0.6
VIA_GAP, GND_SPACING = 0.3, 1.2
D_OPEN, D_DENSE, D_RIM = 4.0, 3.0, 3.5
EDGE_BAND = 4.0
MIN_GAIN = 6.0                             # mm2 of uncovered pour a new via must cover
PIECE_MIN = 1.5                            # mm2: smaller pieces are left as they are (listed)
GRID = 0.5                                 # candidate grid (mm)
# local mm boxes (x0, y0, x1, y1)
DENSE = {"Ethernet": (0, 37, 32, 62), "audio": (0, 0, 36, 34), "buck 3.3 V": (62, 27, 85, 39),
         "buck 5 V": (60, 37, 85, 52), "12 V input": (60, 50, 85, 70), "backlight boost": (47, 46, 60, 64)}
FEED_KEEP = {"+3V3_MCU tongue": (39.1, 24.5, 44.7, 31.5), "+3V3_SDRAM tongue": (55.1, 24.5, 61.5, 30.7)}
XTAL_REFS = ("Y201", "Y202", "C225", "C226", "C227", "C228", "Y501", "C508", "C509")
XTAL_GROW = 0.6


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
    pieces = {0: [], 5: []}                      # GND pour pieces on L1 / L6: list of point lists (px)
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
                if z.GetNetname() == "GND":
                    draw_g[k].polygon(pts, fill=1)
                    if k in pieces and not z.IsTeardropArea():
                        pieces[k].append(pts)
                else:
                    draw_f[k].polygon(pts, fill=1)
                    if k == 4:
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
        dr = draw_g[k] if net == "GND" else draw_f[k]
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
                if k in (0, 5):
                    dp.polygon(pts, fill=1)
                (draw_g[k] if p.GetNetname() == "GND" else draw_f[k]).polygon(pts, fill=1)
            if p.HasHole():
                q = p.GetPosition()
                hr = max(mm(p.GetDrillSize().x), mm(p.GetDrillSize().y)) / 2
                c = Pp(q)
                dp.ellipse([c[0] - hr * RES, c[1] - hr * RES, c[0] + hr * RES, c[1] + hr * RES], fill=1)
                if p.GetNetname() == "GND":
                    anchors_pad.append((mm(q.x) - OX, mm(q.y) - OY, ref + "." + p.GetNumber()))
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
                or z.GetZoneName().startswith("BGA_")):
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
    import finish_silk
    labels = finish_silk.reserved(b)
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
    ok &= in1 | in6
    for k in (0, L6):                                          # outer layers: clear of other nets where not in own pour
        gin = in1 if k == 0 else in6
        ok &= gin | ~dilate(f[k], R_VIA + OUTER)
    for k in range(1, L6):
        if k in (1, 4):                                        # L2 ground plane, L5 power plane (below)
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
        gap = (GND_SPACING if net == "GND" else r + R_VIA + VIA_GAP) * RES
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
    a = [(x, y) for x, y, r, dr, net in S["vias"] if net == "GND"]
    return a + [(x, y) for x, y, ref in S["anchors_pad"]]


def piece_table(S):
    """[(layer index, piece index, area mm2, anchors inside, bbox, mask)]"""
    R = S["R"]
    A = anchors(S)
    rows = []
    for k in (0, S["nlayers"] - 1):
        for i, m in enumerate(piece_masks(S, k)):
            area = m.sum() / RES / RES
            n = 0
            for x, y in A:
                px, py = int(round((x - R.x0) * RES)), int(round((y - R.y0) * RES))
                if 0 <= py < m.shape[0] and 0 <= px < m.shape[1] and m[py, px]:
                    n += 1
            ys, xs = np.nonzero(m)
            bb = (xs.min() / RES + R.x0, ys.min() / RES + R.y0, xs.max() / RES + R.x0, ys.max() / RES + R.y0) if len(xs) else (0, 0, 0, 0)
            rows.append((k, i, area, n, bb, m))
    return rows


def pieces_report(path, out, name):
    S = scene(path)
    rows = piece_table(S)
    lines = ["GND pour pieces of %s (L1 / L6): layer, area mm2, ground anchors (vias and through-hole ground pads), bbox local mm" % os.path.basename(path)]
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
    for x, y in pts:
        blocks.append(nl.join(["\t(via", "\t\t(at %s %s)" % (fmt(x + OX), fmt(y + OY)), "\t\t(size 0.45)", "\t\t(drill 0.2)",
                               '\t\t(layers "F.Cu" "B.Cu")', '\t\t(net "GND")', '\t\t(uuid "%s")' % uuid.uuid4(), "\t)"]))
    k = text.rstrip().rfind(")")
    text = text[:k] + nl.join(blocks) + nl + text[k:]
    open(path, "w", encoding="utf-8", newline="").write(text)


def fmt(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return s


def main(path, out, pieces_only=False):
    """pieces_only: a second pass after the refill, for the pieces the first pass's vias created or left with one via"""
    import finish
    S = scene(path)
    R = S["R"]
    ok, X, Y = legal_mask(S)
    L6 = S["nlayers"] - 1
    pour = S["gnd"][0] & ~dilate(S["ko"], 0) | S["gnd"][L6]
    D = dense_radius(X, Y, S["inside"])
    # rim of every piece (within 0.5 mm of its edge) asks for D_RIM where that is tighter
    rim = (S["gnd"][0] & ~erode(S["gnd"][0], 0.5)) | (S["gnd"][L6] & ~erode(S["gnd"][L6], 0.5))
    D = np.where(rim, np.minimum(D, D_RIM), D)
    step = int(round(0.5 * RES))
    samp = np.zeros_like(pour); samp[::step, ::step] = True
    s1 = samp & S["gnd"][0]
    s6 = samp & S["gnd"][L6]
    sy = np.concatenate([np.nonzero(s1)[0], np.nonzero(s6)[0]])
    sx = np.concatenate([np.nonzero(s1)[1], np.nonzero(s6)[1]])
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
    added, why = [], []

    def take(i, reason):
        x, y = float(round(CX[i], 3)), float(round(CY[i], 3))
        added.append((x, y)); why.append(reason)
        cov[:] |= (SX - x) ** 2 + (SY - y) ** 2 <= SD ** 2
        alive[(CX - x) ** 2 + (CY - y) ** 2 < GND_SPACING ** 2] = False
    # 1. pieces with fewer than two anchors
    for k, i, area, n, bb, m in piece_table(S):
        if n >= 2 or area < PIECE_MIN:
            continue
        inside = alive & m[cy, cx]
        if not inside.any():
            continue
        pts = [(x, y) for x, y in A if m[int(round((y - R.y0) * RES)), int(round((x - R.x0) * RES))]] + added
        if pts:
            dist = np.min([(CX - x) ** 2 + (CY - y) ** 2 for x, y in pts], axis=0)
        else:
            dist = np.zeros(len(CX))
        j = int(np.argmax(np.where(inside, dist, -1)))
        if n == 0 or dist[j] >= 1.5 ** 2:
            take(j, "piece L%d #%d (%.1f mm2, %d anchor%s)" % (k + 1, i, area, n, "" if n == 1 else "s"))
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
        f.write("ground stitching vias added: %d (0.45 / 0.2, F.Cu-B.Cu)\n" % len(added))
        f.write("pour sample points (0.5 mm grid, L1 + L6): %d; within reach of a ground via before %.1f %%, after %.1f %%\n"
                % (total, 100.0 * cov0.sum() / total, 100.0 * cov.sum() / total))
        f.write("rule areas avoided: %s\n" % ", ".join(sorted(set(S["areas"]))))
        for (x, y), w in zip(added, why):
            f.write("  (%.3f, %.3f)  %s\n" % (x, y, w))
    print("stitch%s: %d ground vias added; pour within reach of a ground via %.1f %% -> %.1f %% (%s)" % (" (second pass, pieces)" if pieces_only else "", len(added), 100.0 * cov0.sum() / total, 100.0 * cov.sum() / total,
          os.path.join(out, "stitch2.txt" if pieces_only else "stitch.txt")))
