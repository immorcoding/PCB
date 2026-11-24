"""Ground pours on the inner signal layers, pour keep-outs, and the clean-up of fragments and narrow copper of the
STM32H743 + SDRAM board (finish.py pours / clean / report; stop 8, SPEC section 8, user 2026-11-24: "pour ground on the
inner signal layers too, it shortens the return paths; keep-outs first; remove fragments and narrow copper on every
layer; part of the finishing, before the stitching vias and the silkscreen").

    finish.py pours   <unfilled board> <out>        keep-outs and the L3 / L4 ground pours (pcbnew save)
    finish.py clean   <refilled board> <out>        keep-outs over the ground pieces no via holds (pcbnew save)
    finish.py report  <refilled board> <out> <name> pieces, widths, areas, return paths (reads only)

Why here and not in copper.sketch: the inner pours only make sense with their keep-outs, and the keep-outs over the
serpentines come from the tuning blocks the route2 groups wrote (a re-tune moves them). route2 applies copper.sketch
before any group is built, so a sketch region would be filled in route2 without those keep-outs and without the
stitching vias that hold its pieces. The outline is the whole board, as for the `whole` regions of copper.sketch
(nothing to draw by hand, PWR-3 / PWR-7 untouched); the sketch's comment on L3 points here.

Keep-outs (rule areas that forbid zone fills only; names start with FIN_ so that `finish.py strip` takes them away):
  FIN_NOPOUR_IN_MCU / _SDRAM  L3 + L4, the outline of the BGA rule area (the via field would shred the pour; the user
                              keeps outer pours out of the ball field too, NOPOUR_L1_*)
  FIN_TUNE_<layer>_<net>[_k]  every serpentine block on its layer, TUNE_MARGIN from its copper. A block is found on the
                              board, not typed: the arcs only busroute's tune.py writes (routes_sdram.py, routes_mcu_nw.py,
                              routes_local_eth.py TUNING), joined through the legs between them; its box is the smaller
                              of the 0 / 45 degree rectangles round that copper.
  FIN_KO_<layer>_<k>[_j]      clean-up (`clean`): a ground piece smaller than ISLAND_MIN without a pad (any pour layer),
                              or an inner one no via or through-hole ground pad holds after the stitching (no legal via
                              site): the piece's outline grown by KO_GROW; narrow ground copper (below SLIVER_W) that is
                              a spike / sliver of SLIVER_LEN or more or a neck of NECK_LEN or more: 0 / 45 degree boxes
                              over it (one, or one per 0.6 / 0.3 mm chunk where a single box would cover other ground)
Pours FIN_GND_L3 / FIN_GND_L4: net GND, priority 0, clearance CLEARANCE to every other net (a single-ended line is not
turned into a coplanar one closer than that), minimum width MIN_WIDTH, islands removed below ISLAND_MIN mm2 (KiCad's
area mode: an island is a piece with no pad, docs/tools.md; "always" would drop every piece held only by vias, which
on an inner layer is nearly all of them), pads by the rule file's zone_connection (the zone's own setting is only
the fallback), thermal gap and spoke 0.254 as the rule file, solid fill, no smoothing.

`report` measures every pour layer from the saved fill: per layer the ground pieces (area, ground vias / through-hole
ground pads in it, whether a pad of GND is in it), the local power regions' pieces, the area, and the narrow copper:
the parts of the fill that an opening with a disc of the layer's minimum width removes and that reach more than
DEPTH beyond the opened fill (a corner rounded by the disc is not narrow copper), with a ring round every
through-hole pad left out (its thermal spokes are 0.254 by the rule file). A narrow part that touches the wide copper
in one place only is a spike, in two or more a neck, in none a sliver piece. For L4 / L6 tracks that run in a gap
between the L5 blocks (route2_report.py's [跨缝] run) it gives the length with ground copper within 0.5 mm beside it
on its own layer.
"""
import json, math, os, sys, uuid

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))                     # interim (Tools/ consolidation stage 1): the repository root, for Tools.KiCadDesignTools
OX, OY = 100.0, 100.0
INNER = ("L3", "L4")
CLEARANCE, MIN_WIDTH = 0.2, 0.3
ISLAND_MIN = 2.0                       # mm2: smaller pieces without a pad are dropped by KiCad
THERMAL = 0.254                        # gap and spoke of the rule file's tht_thermal
TUNE_MARGIN = 0.5                      # serpentine copper -> pour
KO_GROW = 0.05                         # an unheld piece's keep-out: its outline grown by this
BGA = {"MCU": "BGA_MCU", "SDRAM": "BGA_SDRAM"}
POUR_LAYERS = ("L1", "L3", "L4", "L6")
MINW = {"L1": 0.3, "L3": MIN_WIDTH, "L4": MIN_WIDTH, "L6": 0.3, "L2": 0.2, "L5": 0.2}
RES = 40                               # report raster: px per mm (0.025 mm)
DEPTH = 0.1                            # a narrow part reaches this far beyond the opened fill
TH_RING = 0.6                          # around a through-hole pad: spokes, not measured
SLIVER_W = 0.6                         # narrow ground copper: narrower than this (twice the pour minimum width) ...
SLIVER_LEN, NECK_LEN = 1.0, 3.0        # ... a spike / sliver this long, or a neck between two wide parts this long
GAP_REACH = 0.5                        # return path: ground copper this close to the track edge
UUID_NS = uuid.UUID("0c9d8a52-7a43-4f0e-9b8e-5f2d1c7e4a11")


def _p():
    import pcbnew
    return pcbnew


def layer_ids(b):
    return {"L%d" % (i + 1): l for i, l in enumerate(b.GetEnabledLayers().CuStack())}


def chain(pts):
    pcbnew = _p()
    ch = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in pts:
        ch.Append(pcbnew.FromMM(OX + float(x)), pcbnew.FromMM(OY + float(y)))
    ch.SetClosed(True)
    return ch


def rule_area(b, name, lids, outline):
    """A keep-out that forbids zone fills only. outline: a SHAPE_LINE_CHAIN in board units."""
    pcbnew = _p()
    z = pcbnew.ZONE(b)
    z.SetIsRuleArea(True); z.SetZoneName(name)
    ls = pcbnew.LSET()
    for l in lids:
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    z.SetDoNotAllowTracks(False); z.SetDoNotAllowVias(False); z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    z.SetDoNotAllowZoneFills(True)
    z.Outline().AddOutline(outline)
    z.SetUuid(pcbnew.KIID(str(uuid.uuid5(UUID_NS, name))))
    b.Add(z)
    return z


# ---------------------------------------------------------------------------------------------------- tuning blocks
def arc_pts(s, m, e, n=16):
    (ax, ay), (bx, by), (cx, cy) = s, m, e
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return [s, e]
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    a0, a1, am = (math.atan2(p[1] - uy, p[0] - ux) for p in (s, e, m))
    sweep = (a1 - a0) % (2 * math.pi)
    if not ((am - a0) % (2 * math.pi) <= sweep):
        sweep -= 2 * math.pi
    return [(ux + r * math.cos(a0 + sweep * i / n), uy + r * math.sin(a0 + sweep * i / n)) for i in range(n + 1)]


def tune_blocks(b):
    """Serpentine blocks on the board: [{layer, net, width, points (local mm), arcs}]. Arcs are written by busroute's
    tune.py only; arcs that share an end, or the two ends of one straight leg, are one block."""
    pcbnew = _p()
    mm = pcbnew.ToMM
    num = {v: k for k, v in layer_ids(b).items()}
    key = lambda v: (round(mm(v.x), 4), round(mm(v.y), 4))
    arcs, segs = [], []
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_ARC_T:
            a = pcbnew.Cast_to_PCB_ARC(t) if hasattr(pcbnew, "Cast_to_PCB_ARC") else t
            arcs.append((num[t.GetLayer()], t.GetNetname(), mm(t.GetWidth()), key(a.GetStart()), key(a.GetMid()), key(a.GetEnd())))
        elif t.Type() == pcbnew.PCB_TRACE_T:
            segs.append((num[t.GetLayer()], t.GetNetname(), key(t.GetStart()), key(t.GetEnd())))
    parent = list(range(len(arcs)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    ends = {}
    for i, (L, n, w, s, m, e) in enumerate(arcs):
        for p in (s, e):
            ends.setdefault((L, n, p), []).append(i)
    for idx in ends.values():
        for j in idx[1:]:
            parent[find(j)] = find(idx[0])
    legs = {}
    for L, n, s, e in segs:
        a, c = ends.get((L, n, s)), ends.get((L, n, e))
        if a and c:
            parent[find(c[0])] = find(a[0])
            legs.setdefault(find(a[0]), []).append((s, e))
    groups = {}
    for i in range(len(arcs)):
        groups.setdefault(find(i), []).append(i)
    out = []
    for root, idx in groups.items():
        L, n, w = arcs[idx[0]][:3]
        pts = []
        for i in idx:
            _, _, _, s, m, e = arcs[i]
            pts += arc_pts(s, m, e)
        for s, e in legs.get(root, []):
            pts += [s, e]
        pts = [(x - OX, y - OY) for x, y in pts]
        out.append({"layer": L, "net": n, "width": w, "arcs": len(idx), "points": pts})
    out.sort(key=lambda r: (r["layer"], r["net"], min(p[0] for p in r["points"])))
    return out


def block_box(pts, grow):
    """The smaller of the 0 and 45 degree rectangles round pts, grown by `grow`: (corners, angle, (length, height))."""
    best = None
    for ang in (0.0, 45.0):
        c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        u = [x * c + y * s for x, y in pts]
        v = [-x * s + y * c for x, y in pts]
        u0, u1, v0, v1 = min(u) - grow, max(u) + grow, min(v) - grow, max(v) + grow
        area = (u1 - u0) * (v1 - v0)
        if best is None or area < best[0] - 1e-9:
            corners = [(uu * c - vv * s, uu * s + vv * c) for uu, vv in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]
            best = (area, corners, ang, (u1 - u0, v1 - v0))
    return best[1], best[2], best[3]


# ---------------------------------------------------------------------------------------------------- pours
def pours(path, out):
    """Keep-outs over the BGA via fields (L3 / L4) and over every serpentine block (its layer), then the L3 / L4
    ground pours. Expects an unfilled board (finish.py strip took the last run's away)."""
    import finish
    pcbnew = _p()
    b = pcbnew.LoadBoard(path)
    lid = layer_ids(b)
    mm, FM = pcbnew.ToMM, pcbnew.FromMM
    log = []
    areas = {z.GetZoneName(): z for z in b.Zones() if z.GetIsRuleArea()}
    blocks = tune_blocks(b)
    bb = b.GetBoardEdgesBoundingBox()
    rect = (mm(bb.GetLeft()) - OX - 1, mm(bb.GetTop()) - OY - 1, mm(bb.GetRight()) - OX + 1, mm(bb.GetBottom()) - OY + 1)
    bga = []
    for short, name in BGA.items():
        z = areas.get(name)
        if z is None:
            log.append("no rule area %s on the board: no inner keep-out for it" % name)
            continue
        o = z.Outline().Outline(0)
        pts = [(mm(o.CPoint(k).x) - OX, mm(o.CPoint(k).y) - OY) for k in range(o.PointCount())]
        bga.append(("FIN_NOPOUR_IN_%s" % short, pts))
    made = []
    for name, pts in bga:
        rule_area(b, name, [lid[L] for L in INNER], chain(pts))
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        made.append({"name": name, "layers": list(INNER), "box": [min(xs), min(ys), max(xs), max(ys)], "angle": 0,
                     "why": "BGA via field (%s)" % name[len("FIN_NOPOUR_IN_"):]})
    seen = {}
    for blk in blocks:
        corners, ang, (lu, lv) = block_box(blk["points"], TUNE_MARGIN + blk["width"] / 2)
        base = "FIN_TUNE_%s_%s" % (blk["layer"], blk["net"])
        seen[base] = seen.get(base, 0) + 1
        name = base if seen[base] == 1 else "%s_%d" % (base, seen[base])
        rule_area(b, name, [lid[blk["layer"]]], chain(corners))
        xs, ys = [p[0] for p in corners], [p[1] for p in corners]
        made.append({"name": name, "layers": [blk["layer"]], "box": [min(xs), min(ys), max(xs), max(ys)], "angle": ang,
                     "size": [lu, lv], "arcs": blk["arcs"],
                     "why": "serpentine of %s (%d arcs), %.1f mm from its copper" % (blk["net"], blk["arcs"], TUNE_MARGIN)})
    gnd = b.FindNet("GND")
    for L in INNER:
        name = "FIN_GND_%s" % L
        z = pcbnew.ZONE(b)
        z.SetZoneName(name); z.SetLayer(lid[L]); z.SetNet(gnd)
        z.SetAssignedPriority(0); z.SetLocalClearance(FM(CLEARANCE)); z.SetMinThickness(FM(MIN_WIDTH))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)
        z.SetThermalReliefGap(FM(THERMAL)); z.SetThermalReliefSpokeWidth(FM(THERMAL))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_AREA); z.SetMinIslandArea(int(ISLAND_MIN * 1e12))
        z.SetFillMode(pcbnew.ZONE_FILL_MODE_POLYGONS)
        z.SetCornerSmoothingType(pcbnew.ZONE_SETTINGS.CORNER_SMOOTHING_NO_SMOOTHING)
        x0, y0, x1, y1 = rect
        z.Outline().AddOutline(chain([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]))
        z.SetUuid(pcbnew.KIID(str(uuid.uuid5(UUID_NS, name))))
        z.SetIsFilled(False)
        b.Add(z)
    finish.save_board(b, path)
    rec = finish.record(path)
    rec["keepouts"] = made
    rec["pieces_removed"] = []
    finish.save_record(path, rec)
    os.makedirs(out, exist_ok=True)
    lines = ["pour keep-outs (local mm; rule areas forbidding zone fills only)"]
    for m in made:
        x0, y0, x1, y1 = m["box"]
        lines.append("  %-28s %-6s box (%.2f, %.2f)-(%.2f, %.2f)%s  %s" % (
            m["name"], "+".join(m["layers"]), x0, y0, x1, y1, "  45 deg, %.2f x %.2f" % tuple(m["size"]) if m.get("angle") else "", m["why"]))
    lines.append("ground pours FIN_GND_L3 / FIN_GND_L4: clearance %.2f, minimum width %.2f, islands without a pad below %.1f mm2 removed, thermal %.3f"
                 % (CLEARANCE, MIN_WIDTH, ISLAND_MIN, THERMAL))
    lines += log
    open(os.path.join(out, "keepouts.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    n_t = sum(1 for m in made if m["name"].startswith("FIN_TUNE_"))
    print("pours: FIN_GND_L3, FIN_GND_L4; keep-outs: %d BGA (L3 + L4), %d serpentine blocks (%s)%s" % (
        len(bga), n_t, ", ".join("%s %d" % (L, sum(1 for m in made if m["name"].startswith("FIN_TUNE_%s_" % L))) for L in POUR_LAYERS),
        "; " + "; ".join(log) if log else ""))


# ---------------------------------------------------------------------------------------------------- pieces
def gnd_pieces(b, layers=POUR_LAYERS):
    """Ground pour pieces from the saved fill: [{layer, zone, area, anchors, pad, poly, bbox}]."""
    pcbnew = _p()
    mm = pcbnew.ToMM
    lid = layer_ids(b)
    vias = [t.GetPosition() for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == "GND"]
    th, smd = [], {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() != "GND":
                continue
            if p.HasHole():                   # reached by thermal spokes: the fill touches a circle round the pad
                sz = p.GetSize(pcbnew.F_Cu)
                th.append((p.GetPosition(), pcbnew.FromMM(mm(max(sz.x, sz.y)) / 2 + THERMAL + 0.05)))
            for L in layers:
                if p.IsOnLayer(lid[L]) and not p.HasHole():
                    smd.setdefault(L, []).append(p)
    out = []
    for z in b.Zones():
        if z.GetIsRuleArea() or z.IsTeardropArea() or z.GetNetname() != "GND":
            continue
        for L in layers:
            if not z.IsOnLayer(lid[L]):
                continue
            f = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(lid[L]))
            for i in range(f.OutlineCount()):
                one = pcbnew.SHAPE_POLY_SET()
                one.AddOutline(f.Outline(i))
                for h in range(f.HoleCount(i)):
                    one.AddHole(f.Hole(i, h))
                n_th = sum(1 for v, r in th if one.Collide(v, r))
                n = sum(1 for v in vias if one.Contains(v)) + n_th
                pad = n_th > 0 or any(one.Collide(p.GetPosition(), pcbnew.FromMM(0.05)) for p in smd.get(L, []))
                bb = one.BBox()
                out.append({"layer": L, "zone": z.GetZoneName(), "area": one.Area() / 1e12, "anchors": n, "pad": pad, "poly": one,
                    "bbox": (mm(bb.GetLeft()) - OX, mm(bb.GetTop()) - OY, mm(bb.GetRight()) - OX, mm(bb.GetBottom()) - OY)})
    return out


def piece_keepout(b, lid, p, name):
    """A keep-out over one fill piece: its outline grown by KO_GROW."""
    pcbnew = _p()
    poly = pcbnew.SHAPE_POLY_SET(p["poly"])
    poly.Inflate(pcbnew.FromMM(KO_GROW), pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS, pcbnew.FromMM(0.005))
    poly.Fracture()
    for i in range(poly.OutlineCount()):
        rule_area(b, name if i == 0 else "%s_%d" % (name, i + 1), [lid[p["layer"]]], poly.Outline(i))


def scene_masks(b):
    """Rasters (RES) for the shape clean-up: R, ground fill per pour layer, rings round through-hole pads, ground SMD
    pads per layer, ground vias."""
    pcbnew = _p()
    from PIL import ImageDraw
    mm = pcbnew.ToMM
    lid = layer_ids(b)
    bb = b.GetBoardEdgesBoundingBox()
    R = Raster(mm(bb.GetLeft()) - OX - 0.5, mm(bb.GetTop()) - OY - 0.5, mm(bb.GetRight()) - OX + 0.5, mm(bb.GetBottom()) - OY + 0.5)
    ring = R.img(); dr = ImageDraw.Draw(ring)
    pads = {L: R.img() for L in POUR_LAYERS}
    dp = {L: ImageDraw.Draw(pads[L]) for L in POUR_LAYERS}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            c = R.px(mm(p.GetPosition().x) - OX, mm(p.GetPosition().y) - OY)
            if p.HasHole():
                rr = (max(mm(p.GetSize(pcbnew.F_Cu).x), mm(p.GetSize(pcbnew.F_Cu).y)) / 2 + TH_RING) * R.res
                dr.ellipse([c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr], fill=1)
            elif p.GetNetname() == "GND":
                for L in POUR_LAYERS:
                    if p.IsOnLayer(lid[L]):
                        o = p.GetEffectivePolygon(lid[L], pcbnew.ERROR_OUTSIDE).Outline(0)
                        dp[L].polygon([R.px(mm(o.CPoint(k).x) - OX, mm(o.CPoint(k).y) - OY) for k in range(o.PointCount())], fill=1)
    vias = R.img(); dv = ImageDraw.Draw(vias)
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == "GND":
            c = R.px(mm(t.GetPosition().x) - OX, mm(t.GetPosition().y) - OY); rr = mm(t.GetWidth(pcbnew.F_Cu)) / 2 * R.res
            dv.ellipse([c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr], fill=1)
    gnd = {L: fill_mask(b, R, L, lambda z: z.GetNetname() == "GND") for L in POUR_LAYERS}
    return R, gnd, np.array(ring, dtype=bool), {L: np.array(v, dtype=bool) for L, v in pads.items()}, np.array(vias, dtype=bool)


def rects(ys, xs, R, chunk=None, axis=0):
    """0 / 45 degree rectangles (local mm corner lists) over a pixel set, grown by KO_GROW; with chunk, the set is cut
    along its long (axis 0) or short (axis 1) direction into pieces of that length first."""
    pts = np.stack([xs / R.res + R.x0, ys / R.res + R.y0], axis=1)
    half = 0.5 / R.res
    best = None
    for ang in (0.0, 45.0):
        c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        u, v = pts[:, 0] * c + pts[:, 1] * s, -pts[:, 0] * s + pts[:, 1] * c
        a = (u.max() - u.min()) * (v.max() - v.min())
        if best is None or a < best[0] - 1e-9:
            best = (a, ang, u, v)
    _, ang, u, v = best
    if chunk:
        long_u = (u.max() - u.min()) >= (v.max() - v.min())
        key = u if long_u == (axis == 0) else v
        n = max(1, int(math.ceil((key.max() - key.min()) / chunk)))
        groups = [np.nonzero((key >= key.min() + k * chunk - 1e-9) & (key <= key.min() + (k + 1) * chunk + 1e-9))[0] for k in range(n)]
    else:
        groups = [np.arange(len(u))]
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    out = []
    g = KO_GROW + half
    for idx in groups:
        if not len(idx):
            continue
        u0, u1, v0, v1 = u[idx].min() - g, u[idx].max() + g, v[idx].min() - g, v[idx].max() + g
        out.append([(uu * c - vv * s, uu * s + vv * c) for uu, vv in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))])
    return out, ang


def rect_mask(R, shape, rs):
    from PIL import Image, ImageDraw
    img = Image.new("1", (shape[1], shape[0]), 0)
    d = ImageDraw.Draw(img)
    for r in rs:
        d.polygon([R.px(x, y) for x, y in r], fill=1)
    return np.array(img, dtype=bool)


def clean(path, out, stage):
    """stage "shape" (before the stitching): keep-outs over the narrow ground copper (narrower than SLIVER_W) that is a
    spike or a sliver of at least SLIVER_LEN or a neck of at least NECK_LEN (not within 0.5 mm of a ground pad; on L1 /
    L6 not over a ground via either: a pad's way to its via may run there), and over the ground pieces smaller than
    ISLAND_MIN that hold no pad (KiCad keeps those when a via joins them to a pad), on every pour layer. stage "anchor" (after the
    stitching): keep-outs over the inner ground pieces that no via or through-hole ground pad holds (no legal via site
    was found in them) or that are smaller than ISLAND_MIN without a pad; outer-layer pieces without a via are listed
    (they hold a pad). Returns the number of keep-outs added."""
    import finish
    pcbnew = _p()
    b = pcbnew.LoadBoard(path)
    lid = layer_ids(b)
    pieces = gnd_pieces(b)
    rec = finish.record(path)
    gone = rec.get("pieces_removed", [])
    k0 = len(gone)
    log = []
    add = []                                         # (layer, kind, piece or rectangles, area, box, why)
    for p in pieces:
        if p["layer"] not in INNER and stage == "anchor" and p["anchors"] == 0:
            log.append("%s piece of %.2f mm2 at (%.2f, %.2f)-(%.2f, %.2f) holds %s and no via: left (outer layer)" % (
                p["layer"], p["area"], *p["bbox"], "a ground pad" if p["pad"] else "nothing"))
            continue
        why = None
        if p["area"] < ISLAND_MIN and not p["pad"]:
            why = "piece of %.2f mm2 < %.1f mm2 without a pad (held by %d via%s)" % (p["area"], ISLAND_MIN, p["anchors"], "" if p["anchors"] == 1 else "s")
        elif stage == "anchor" and p["anchors"] == 0:
            why = "piece of %.2f mm2 that no via or through-hole ground pad holds (no legal via site)" % p["area"]
        if why:
            add.append((p["layer"], "piece", p, p["area"], p["bbox"], why))
    if stage == "shape":
        R, gnd, ring, pads, vias = scene_masks(b)
        for L in POUR_LAYERS:
            fill = gnd[L]
            near_pad = dilate(pads[L], 0.5, R.res)
            for kind, area, length, (cx, cy), ys, xs in narrow(fill, SLIVER_W, ring, R, pixels=True):
                if length < (NECK_LEN if kind == "neck" else SLIVER_LEN):
                    continue
                at = "%s %s %.2f mm long, %.3f mm2 at (%.2f, %.2f)" % (L, kind, length, area, cx, cy)
                c = pcbnew.VECTOR2I(pcbnew.FromMM(OX + float(xs[0]) / R.res + R.x0), pcbnew.FromMM(OY + float(ys[0]) / R.res + R.y0))
                if any(a[0] == L and a[1] == "piece" and a[2]["poly"].Collide(c, pcbnew.FromMM(0.05)) for a in add):
                    continue                             # in a piece that goes whole
                if near_pad[ys, xs].any():
                    log.append("kept (a ground pad within 0.5 mm): " + at)
                    continue
                if L not in INNER and vias[ys, xs].any():
                    log.append("kept (holds a ground via on an outer layer): " + at)
                    continue
                y0, y1, x0, x1 = max(0, ys.min() - 40), ys.max() + 41, max(0, xs.min() - 40), xs.max() + 41
                comp = np.zeros((y1 - y0, x1 - x0), dtype=bool)
                comp[ys - y0, xs - x0] = True
                allow = dilate(comp, 0.35, R.res)
                ok = None
                for chunk, axis in ((None, 0), (0.6, 0), (0.6, 1), (0.3, 0)):
                    rs, ang = rects(ys, xs, R, chunk, axis)
                    m = rect_mask(R, fill.shape, rs)[y0:y1, x0:x1]
                    sub = fill[y0:y1, x0:x1]
                    over = m[:sub.shape[0], :sub.shape[1]] & sub & ~allow[:sub.shape[0], :sub.shape[1]]
                    if over.sum() / R.res ** 2 < 0.005:
                        ok = (rs, ang, chunk)
                        break
                if ok is None:
                    log.append("kept (no clean 0 / 45 degree box over it): " + at)
                    continue
                rs, ang, chunk = ok
                xs_ = [x for r in rs for x, _ in r]; ys_ = [y for r in rs for _, y in r]
                add.append((L, "rects", rs, area, (min(xs_), min(ys_), max(xs_), max(ys_)),
                            "narrow %s below %.1f mm, %.2f mm long (%d box%s, %g deg)" % (kind, SLIVER_W, length, len(rs), "" if len(rs) == 1 else "es", ang)))
    k = k0
    for L, what, obj, area, box, why in add:
        k += 1
        name = "FIN_KO_%s_%d" % (L, k)
        if what == "piece":
            piece_keepout(b, lid, obj, name)
        else:
            for j, r in enumerate(obj):
                rule_area(b, name if j == 0 else "%s_%d" % (name, j + 1), [lid[L]], chain(r))
        gone.append({"name": name, "layer": L, "stage": stage, "kind": what, "area": round(area, 3), "box": [round(v, 3) for v in box], "why": why})
    if add:
        finish.save_board(b, path)
        rec["pieces_removed"] = gone
        finish.save_record(path, rec)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "clean_%s.txt" % stage), "a", encoding="utf-8") as f:
        f.write("== %s pass on %s: %d keep-out(s)\n" % (stage, os.path.basename(path), len(add)))
        for g in gone[k0:]:
            f.write("%s %s: %.3f mm2, box (%.2f, %.2f)-(%.2f, %.2f): %s\n" % (g["name"], g["layer"], g["area"], *g["box"], g["why"]))
        for l in log:
            f.write(l + "\n")
    n_by = {}
    for L, what, *_ in add:
        n_by[(L, what)] = n_by.get((L, what), 0) + 1
    print("clean (%s): %d keep-outs (%s); %d listed only (%s)" % (
        stage, len(add), ", ".join("%s %s %d" % (L, "pieces" if w == "piece" else "narrow", n) for (L, w), n in sorted(n_by.items())) or "none",
        len(log), os.path.join(out, "clean_%s.txt" % stage)))
    return len(add)


# ---------------------------------------------------------------------------------------------------- report
class Raster:
    def __init__(self, x0, y0, x1, y1, res=RES):
        self.x0, self.y0, self.res = x0, y0, res
        self.w, self.h = int(math.ceil((x1 - x0) * res)) + 1, int(math.ceil((y1 - y0) * res)) + 1

    def px(self, x, y):
        return ((x - self.x0) * self.res, (y - self.y0) * self.res)

    def img(self):
        from PIL import Image
        return Image.new("1", (self.w, self.h), 0)


def dilate(a, r, res=RES):
    if r <= 0:
        return a.copy()
    out = a.copy()
    k = int(math.ceil(r * res))
    rr = (r * res) ** 2
    H, W = a.shape
    for dy in range(-k, k + 1):
        for dx in range(-k, k + 1):
            if dx * dx + dy * dy > rr or (dx == 0 and dy == 0):
                continue
            ys, yd = (slice(0, H - dy), slice(dy, H)) if dy >= 0 else (slice(-dy, H), slice(0, H + dy))
            xs, xd = (slice(0, W - dx), slice(dx, W)) if dx >= 0 else (slice(-dx, W), slice(0, W + dx))
            out[yd, xd] |= a[ys, xs]
    return out


def erode(a, r, res=RES):
    return ~dilate(~a, r, res)


def label(mask):
    """Connected parts (8-neighbour) of a boolean array: list of (ys, xs). Run-length union-find, numpy only."""
    H, W = mask.shape
    runs, parent = [], []
    prev = []
    rows = np.nonzero(mask.any(axis=1))[0]
    last_y = -2

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for y in rows:
        row = mask[y].astype(np.int8)
        d = np.diff(np.concatenate([[0], row, [0]]))
        st, en = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
        cur = []
        for s, e in zip(st, en):
            i = len(runs)
            runs.append((y, s, e)); parent.append(i); cur.append(i)
            if y == last_y + 1:
                for j in prev:
                    _, ps, pe = runs[j]
                    if ps <= e and pe >= s:           # 8-neighbour: [s-1, e] overlaps [ps, pe-1]
                        a, c = find(i), find(j)
                        if a != c:
                            parent[a] = c
        prev, last_y = cur, y
    comps = {}
    for i, (y, s, e) in enumerate(runs):
        comps.setdefault(find(i), []).append((y, s, e))
    out = []
    for rl in comps.values():
        ys = np.concatenate([np.full(e - s, y) for y, s, e in rl])
        xs = np.concatenate([np.arange(s, e) for y, s, e in rl])
        out.append((ys, xs))
    return out


def fill_mask(b, R, L, pred):
    """Raster of the saved fill on layer L of the zones that pass pred(zone)."""
    pcbnew = _p()
    from PIL import ImageDraw
    mm = pcbnew.ToMM
    lid = layer_ids(b)[L]
    img = R.img(); d = ImageDraw.Draw(img)
    for z in b.Zones():
        if z.GetIsRuleArea() or z.IsTeardropArea() or not z.IsOnLayer(lid) or not pred(z):
            continue
        f = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(lid))
        f.Fracture()
        for i in range(f.OutlineCount()):
            o = f.Outline(i)
            pts = [R.px(mm(o.CPoint(k).x) - OX, mm(o.CPoint(k).y) - OY) for k in range(o.PointCount())]
            if len(pts) >= 3:
                d.polygon(pts, fill=1)
    return np.array(img, dtype=bool)


def narrow(fill, w, skip, R, pixels=False):
    """Narrow copper of `fill` at width w: [(kind, area mm2, length mm, (x, y))] (+ ys, xs with pixels); kind spike /
    neck / sliver."""
    r = w / 2 - 0.5 / R.res                        # half a pixel of slack for the raster
    opened = dilate(erode(fill, r, R.res), r, R.res)
    thin = fill & ~opened & ~skip
    deep = thin & ~dilate(opened, DEPTH, R.res)
    if not deep.any():
        return []
    out = []
    near_body = dilate(opened, 2.0 / R.res, R.res)
    for ys, xs in label(thin):
        if not deep[ys, xs].any():
            continue
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        m = np.zeros((y1 - y0 + 5, x1 - x0 + 5), dtype=bool)
        m[ys - y0 + 2, xs - x0 + 2] = True
        grown = dilate(m, 2.0 / R.res, R.res)
        sub = near_body[max(0, y0 - 2):y0 - 2 + grown.shape[0], max(0, x0 - 2):x0 - 2 + grown.shape[1]]
        g = grown[:sub.shape[0], :sub.shape[1]] & sub
        touches = len(label(g)) if g.any() else 0
        kind = "sliver" if touches == 0 else ("spike" if touches == 1 else "neck")
        area = len(ys) / R.res ** 2
        length = math.hypot(x1 - x0, y1 - y0) / R.res
        out.append((kind, area, length, (float(xs.mean()) / R.res + R.x0, float(ys.mean()) / R.res + R.y0)) + ((ys, xs) if pixels else ()))
    return out


def gap_runs(b, R, gnd_masks):
    """L4 / L6 track length inside a gap between the L5 blocks of copper.sketch, and how much of it has ground copper of
    its own layer within GAP_REACH of its edge."""
    pcbnew = _p()
    from Tools.KiCadDesignTools.copper import cu_sketch
    from Tools.KiCadDesignTools.routing.busroute.geom import in_poly, pt_seg
    mm = pcbnew.ToMM
    sk = cu_sketch.load_sketch(os.path.join(HERE, "copper.sketch"), 6)
    gap = sk.p["gap"] / 1e6
    ox, oy = sk.origin[0] / 1e6 - OX, sk.origin[1] / 1e6 - OY
    blocks = [[(x / 1e6 + ox, y / 1e6 + oy) for x, y in r.pts] for r in sk.regions if not r.whole and r.layer == 5]
    boxes = [(min(q[0] for q in p) - gap, min(q[1] for q in p) - gap, max(q[0] for q in p) + gap, max(q[1] for q in p) + gap) for p in blocks]

    def in_gap(p):
        ks = [k for k, (x0, y0, x1, y1) in enumerate(boxes) if x0 <= p[0] <= x1 and y0 <= p[1] <= y1]
        if not ks or any(in_poly(p, blocks[k]) for k in ks):
            return False
        return any(min(pt_seg(p, e0, e1)[0] for e0, e1 in zip(blocks[k], blocks[k][1:] + blocks[k][:1])) < gap for k in ks)
    lid = layer_ids(b)
    near = {}
    res = {}
    for t in b.GetTracks():
        if t.Type() != pcbnew.PCB_TRACE_T or t.GetNetname() == "GND":
            continue
        L = {lid["L4"]: "L4", lid["L6"]: "L6"}.get(t.GetLayer())
        if not L:
            continue
        a = (mm(t.GetStart().x) - OX, mm(t.GetStart().y) - OY); c = (mm(t.GetEnd().x) - OX, mm(t.GetEnd().y) - OY)
        w = round(mm(t.GetWidth()), 3)
        if (L, w) not in near:
            near[(L, w)] = dilate(gnd_masks[L], GAP_REACH + w / 2, R.res)
        Ln = math.dist(a, c)
        k = max(1, int(Ln / 0.02))
        for i in range(k):
            p = (a[0] + (c[0] - a[0]) * (i + 0.5) / k, a[1] + (c[1] - a[1]) * (i + 0.5) / k)
            if not in_gap(p):
                continue
            px, py = R.px(*p)
            covered = bool(near[(L, w)][int(round(py)), int(round(px))])
            r = res.setdefault(t.GetNetname(), {"L4": [0.0, 0.0], "L6": [0.0, 0.0]})
            r[L][0] += Ln / k
            r[L][1] += Ln / k if covered else 0.0
    return res


def report(path, out, name):
    pcbnew = _p()
    from PIL import ImageDraw
    b = pcbnew.LoadBoard(path)
    mm = pcbnew.ToMM
    lid = layer_ids(b)
    bb = b.GetBoardEdgesBoundingBox()
    R = Raster(mm(bb.GetLeft()) - OX - 0.5, mm(bb.GetTop()) - OY - 0.5, mm(bb.GetRight()) - OX + 0.5, mm(bb.GetBottom()) - OY + 0.5)
    # rings round the through-hole pads (thermal spokes are 0.254 by the rule file: not pour copper)
    ring = R.img(); dr = ImageDraw.Draw(ring)
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.HasHole():
                c = R.px(mm(p.GetPosition().x) - OX, mm(p.GetPosition().y) - OY)
                rr = (max(mm(p.GetSize(pcbnew.F_Cu).x), mm(p.GetSize(pcbnew.F_Cu).y)) / 2 + TH_RING) * R.res
                dr.ellipse([c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr], fill=1)
    ring = np.array(ring, dtype=bool)
    pieces = gnd_pieces(b, layers=("L1", "L2", "L3", "L4", "L5", "L6"))
    rep = {"board": os.path.basename(path), "layers": {}}
    gnd_masks = {}
    lines = ["pour copper of %s (saved fill; local mm)" % os.path.basename(path)]
    for L in ("L1", "L2", "L3", "L4", "L5", "L6"):
        gm = fill_mask(b, R, L, lambda z: z.GetNetname() == "GND")
        gnd_masks[L] = gm
        own = [p for p in pieces if p["layer"] == L]
        row = {"gnd_pieces": len(own), "gnd_area": round(sum(p["area"] for p in own), 2)}
        if own:
            free = [p for p in own if not p["pad"]]
            row["smallest"] = round(min(p["area"] for p in own), 3)
            row["smallest_without_pad"] = round(min((p["area"] for p in free), default=0.0), 3)
            row["without_pad"] = len(free)
            row["anchors"] = {str(c): sum(1 for p in own if min(p["anchors"], 3) == c) for c in range(4)}
            row["pieces"] = [{"area": round(p["area"], 3), "anchors": p["anchors"], "pad": p["pad"],
                              "bbox": [round(v, 2) for v in p["bbox"]]} for p in sorted(own, key=lambda p: p["area"])]
        # other nets' zones on the layer (local power regions, plane blocks)
        others = {}
        for z in b.Zones():
            if z.GetIsRuleArea() or z.IsTeardropArea() or z.GetNetname() == "GND" or not z.IsOnLayer(lid[L]):
                continue
            f = z.GetFilledPolysList(lid[L])
            others[z.GetZoneName()] = [round(f.Outline(i).Area() / 1e12, 3) for i in range(f.OutlineCount())]
        row["power_pieces"] = sum(len(v) for v in others.values())
        row["power_smallest"] = min((a for v in others.values() for a in v), default=None)
        w = MINW[L]
        if gm.any():
            nar = narrow(gm, w, ring, R)
            row["narrow_at_min"] = [(k, round(a, 4), round(l, 3), [round(c[0], 2), round(c[1], 2)]) for k, a, l, c in nar]
            # narrowest: the widest test width (0.05 steps up to the layer minimum) that finds nothing
            lo = None
            for ww in [round(0.1 + 0.025 * i, 3) for i in range(int(round((w - 0.1) / 0.025)) + 1)]:
                if narrow(gm, ww, ring, R):
                    break
                lo = ww
            row["narrowest_at_least"] = lo
            wide = narrow(gm, SLIVER_W, ring, R)
            row["narrow_0_6"] = {k: sum(1 for q in wide if q[0] == k) for k in ("spike", "sliver", "neck")}
            row["slivers"] = [(k, round(a, 4), round(l, 3), [round(c[0], 2), round(c[1], 2)]) for k, a, l, c in wide
                              if l >= (NECK_LEN if k == "neck" else SLIVER_LEN)]
        rep["layers"][L] = row
        lines.append("%s ground: %d pieces, %.1f mm2%s; local power / plane pieces %d (smallest %s)" % (
            L, row["gnd_pieces"], row["gnd_area"],
            "" if not own else ", smallest %.2f mm2 (without a pad: %d, smallest %.2f), held by 0 / 1 / 2 / 3+ vias: %s" % (
                row["smallest"], row["without_pad"], row["smallest_without_pad"], " / ".join(str(row["anchors"][str(c)]) for c in range(4))),
            row["power_pieces"], row["power_smallest"]))
        if "narrow_at_min" in row:
            lines.append("    narrow copper below %.2f mm: %d part(s)%s; no part narrower than %s mm found" % (
                w, len(row["narrow_at_min"]), "".join(" %s %.3f mm2 at (%.2f, %.2f)" % (k, a, c[0], c[1]) for k, a, l, c in row["narrow_at_min"][:6]),
                row["narrowest_at_least"]))
            lines.append("    below %.1f mm: spikes %d, slivers %d, necks %d; spikes / slivers >= %.1f mm and necks >= %.1f mm long: %d%s" % (
                SLIVER_W, row["narrow_0_6"]["spike"], row["narrow_0_6"]["sliver"], row["narrow_0_6"]["neck"], SLIVER_LEN, NECK_LEN,
                len(row["slivers"]), "".join(" %s %.2f mm at (%.2f, %.2f)" % (k, l, c[0], c[1]) for k, a, l, c in row["slivers"][:20])))
    # serpentine copper to the ground fill of its layer (TUNE_MARGIN asked): exact, by bisection on KiCad's collision test
    fills = {}
    for z in b.Zones():
        if z.GetIsRuleArea() or z.IsTeardropArea() or z.GetNetname() != "GND":
            continue
        for l in lid.values():
            if z.IsOnLayer(l):
                fills.setdefault(l, []).append(pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(l)))
    lid_of = {v: k for k, v in lid.items()}
    tune_gap = {}
    for t in b.GetTracks():
        if t.Type() != pcbnew.PCB_ARC_T:
            continue
        l, L = t.GetLayer(), lid_of[t.GetLayer()]
        sh = t.GetEffectiveShape(l)
        hit = lambda c: any(f.Collide(sh, pcbnew.FromMM(c)) for f in fills.get(l, []))
        tune_gap.setdefault(L, None)
        if not hit(1.5):
            continue
        lo, hi = 0.0, 1.5
        for _ in range(16):
            mid = (lo + hi) / 2
            lo, hi = (lo, mid) if hit(mid) else (mid, hi)
        if tune_gap[L] is None or hi < tune_gap[L][0]:
            p = t.GetPosition()
            tune_gap[L] = (round(hi, 3), t.GetNetname(), round(mm(p.x) - OX, 2), round(mm(p.y) - OY, 2))
    rep["tune_gap"] = tune_gap
    lines.append("serpentine copper to the ground fill of its layer (nearest; - = none within 1.5 mm): %s" % (
        ", ".join("%s %s" % (L, "-" if v is None else "%.3f mm (%s at %.2f, %.2f)" % v) for L, v in sorted(tune_gap.items()))))
    runs = gap_runs(b, R, gnd_masks)
    tot = {L: [sum(r[L][0] for r in runs.values()), sum(r[L][1] for r in runs.values())] for L in ("L4", "L6")}
    rep["gap_runs"] = {"total": tot, "nets": {n: r for n, r in runs.items()}}
    lines.append("tracks in a gap between the L5 blocks: L4 %.2f mm (%.2f with ground within %.1f mm beside), L6 %.2f mm (%.2f); total %.2f mm, %.2f covered" % (
        tot["L4"][0], tot["L4"][1], GAP_REACH, tot["L6"][0], tot["L6"][1], tot["L4"][0] + tot["L6"][0], tot["L4"][1] + tot["L6"][1]))
    for n in sorted(runs, key=lambda n: -(runs[n]["L4"][0] + runs[n]["L6"][0])):
        r = runs[n]
        for L in ("L4", "L6"):
            if r[L][0] > 0.05:
                lines.append("      %-14s %s %.2f mm in a gap, %.2f with ground beside" % (n, L, r[L][0], r[L][1]))
    os.makedirs(out, exist_ok=True)
    json.dump(rep, open(os.path.join(out, "pours_%s.json" % name), "w", encoding="utf-8"), indent=1)
    open(os.path.join(out, "pours_%s.txt" % name), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(l for l in lines if not l.startswith("      ")))
