"""Silkscreen of a board (finishing stop 8, FIN-1 to FIN-3; run through finishing.finish silk).

    -m Tools.KiCadDesignTools.finishing.finish <board dir> silk <board> <out>

What it does: every reference field moves to the Fab layer of its side (assembly drawing; a footprint that has a Fab
copy of its reference gets the silkscreen one hidden), values that were on the silkscreen are hidden; the Gerbers
subtract the solder mask from the silkscreen; the footprints of silk.toml [mask] fine get their own solder-mask
expansion; then it prints the title blocks ([[title]]), a dot at the A1 corner of each part of [a1] parts, and the
labels ([texts]) and glyphs ([icons]) of silk.toml. Pin-1 marks and polarity marks are the footprints' own silkscreen
(kept). The decisions behind the H743 board's choices are in its silk.toml.

Placement: every item has an anchor (local mm, the wanted centre) and slides up to reach ([place] reach, or the item's
own) to clear the pads' solder-mask openings + pad_silk, other footprints' silkscreen + silk_gap, part bodies
(courtyard shrunk by body_in: text is not printed under a part), the board edge + edge and the items placed before it
(+ item_gap). Vias are tented: a spot clear of vias is preferred, one over a via is taken when there is no other. An
item that finds no spot is not printed and is listed in <out>/silk.txt (fix its anchor in silk.toml).

silk.toml: [sizes] (name -> [height, width, stroke]), [place] (icon_width, pad_silk, silk_gap, body_in, edge,
item_gap, reach), [mask] fine ({reference: expansion}), [a1] parts ([[reference, ball]]), [labels] texts ([text, x, y, rot,
size name, side]; rot 90 reads upwards, "B" items are mirrored on the bottom), icons ([glyph, x, y, scale, side,
reach?]; the glyphs are drawn by glyph() below), [[title]] (side, at, reserve box round the anchor, items: text or
icon with d = [dx, dy] from the anchor, size or scale, reach). setup(cfg) first.
"""
import math, os, sys
import numpy as np

RES = 20


def setup(cfg):
    """silk.toml as this module's globals."""
    global OX, OY, SIZES, ICON_W, PAD_SILK, SILK_GAP, BODY_IN, EDGE, ITEM_GAP, REACH, MASK_FINE, A1, TEXT, ICONS, TITLES
    d = cfg.datafile("silk.toml")
    if not d:
        raise ValueError("%s: no silk.toml" % cfg.dir)
    OX, OY = cfg.origin
    SIZES = {k: tuple(v) for k, v in d["sizes"].items()}
    p = d["place"]
    ICON_W = p["icon_width"]
    PAD_SILK, SILK_GAP, BODY_IN, EDGE, ITEM_GAP = p["pad_silk"], p["silk_gap"], p["body_in"], p["edge"], p["item_gap"]
    REACH = p["reach"]
    MASK_FINE = dict(d["mask"]["fine"])
    A1 = [tuple(r) for r in d["a1"]["parts"]]
    # text items: (text, x, y, rot, size, side); icons: (kind, x, y, scale, side[, reach])
    TEXT = [(s, x, y, rot, SIZES[size], side) for s, x, y, rot, size, side in d["labels"]["texts"]]
    ICONS = [tuple(r) for r in d["labels"]["icons"]]
    TITLES = d["title"]


def mm_box(bb):
    import pcbnew
    t = pcbnew.ToMM
    return t(bb.GetLeft()) - OX, t(bb.GetTop()) - OY, t(bb.GetRight()) - OX, t(bb.GetBottom()) - OY


class Field:
    """Obstacle rasters of one side: hard (no silk) and soft (tented vias)."""
    def __init__(self, b, side):
        import pcbnew
        from PIL import Image, ImageDraw
        self.side = side
        bx = mm_box(b.GetBoardEdgesBoundingBox())
        self.x0, self.y0 = bx[0] - 1, bx[1] - 1
        self.w, self.h = int((bx[2] - bx[0] + 2) * RES), int((bx[3] - bx[1] + 2) * RES)
        hard, soft = Image.new("1", (self.w, self.h), 0), Image.new("1", (self.w, self.h), 0)
        dh, ds = ImageDraw.Draw(hard), ImageDraw.Draw(soft)
        mm = pcbnew.ToMM
        cu = pcbnew.F_Cu if side == "F" else pcbnew.B_Cu
        silk = pcbnew.F_SilkS if side == "F" else pcbnew.B_SilkS
        mask = pcbnew.F_Mask if side == "F" else pcbnew.B_Mask
        crt = pcbnew.F_CrtYd if side == "F" else pcbnew.B_CrtYd
        P = lambda v: self.px(mm(v.x) - OX, mm(v.y) - OY)
        for fp in b.GetFootprints():
            for p in fp.Pads():
                if not (p.IsOnLayer(mask) or p.HasHole()):
                    continue
                lay = mask if p.IsOnLayer(mask) else (cu if p.IsOnLayer(cu) else pcbnew.F_Cu)
                try:
                    poly = p.GetEffectivePolygon(cu if p.IsOnLayer(cu) else pcbnew.F_Cu, pcbnew.ERROR_OUTSIDE)
                except Exception:
                    continue
                grow = PAD_SILK + (mm(p.GetSolderMaskExpansion(mask)) if p.IsOnLayer(mask) else 0.0)
                poly = pcbnew.SHAPE_POLY_SET(poly)
                poly.Inflate(pcbnew.FromMM(grow), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, pcbnew.FromMM(0.01))
                for i in range(poly.OutlineCount()):
                    o = poly.Outline(i)
                    dh.polygon([P(o.CPoint(k)) for k in range(o.PointCount())], fill=1)
                if p.HasHole():
                    c = P(p.GetPosition()); r = (max(mm(p.GetDrillSize().x), mm(p.GetDrillSize().y)) / 2 + PAD_SILK) * RES
                    dh.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=1)
            for g in fp.GraphicalItems():
                if g.GetLayer() == silk:
                    self.shape(dh, g, SILK_GAP)
            cy = fp.GetCourtyard(crt)
            if cy.OutlineCount():
                cy = pcbnew.SHAPE_POLY_SET(cy)
                cy.Inflate(-pcbnew.FromMM(BODY_IN), pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS, pcbnew.FromMM(0.01))
                for i in range(cy.OutlineCount()):
                    o = cy.Outline(i)
                    if o.PointCount() >= 3:
                        dh.polygon([P(o.CPoint(k)) for k in range(o.PointCount())], fill=1)
        for t in b.GetTracks():
            if t.Type() == pcbnew.PCB_VIA_T:
                c = P(t.GetPosition()); r = (mm(t.GetWidth(pcbnew.F_Cu)) / 2 + 0.05) * RES
                ds.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=1)
        inside = Image.new("1", (self.w, self.h), 0)
        ol = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(ol, True)
        ol.Inflate(-pcbnew.FromMM(EDGE), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, pcbnew.FromMM(0.01))
        di = ImageDraw.Draw(inside)
        for i in range(ol.OutlineCount()):
            o = ol.Outline(i)
            di.polygon([P(o.CPoint(k)) for k in range(o.PointCount())], fill=1)
        self.hard = np.array(hard, dtype=bool) | ~np.array(inside, dtype=bool)
        self.soft = np.array(soft, dtype=bool)

    def px(self, x, y):
        return ((x - self.x0) * RES, (y - self.y0) * RES)

    def shape(self, d, g, grow):
        import pcbnew
        try:
            poly = pcbnew.SHAPE_POLY_SET()
            g.TransformShapeToPolygon(poly, g.GetLayer(), pcbnew.FromMM(grow), pcbnew.FromMM(0.01), pcbnew.ERROR_OUTSIDE)
        except Exception:
            return
        mm = pcbnew.ToMM
        for i in range(poly.OutlineCount()):
            o = poly.Outline(i)
            d.polygon([self.px(mm(o.CPoint(k).x) - OX, mm(o.CPoint(k).y) - OY) for k in range(o.PointCount())], fill=1)

    def rect(self, box, grow=0.0):
        x0, y0, x1, y1 = box
        a = self.px(x0 - grow, y0 - grow); c = self.px(x1 + grow, y1 + grow)
        return (max(0, int(a[1])), min(self.h, int(math.ceil(c[1]))), max(0, int(a[0])), min(self.w, int(math.ceil(c[0]))))

    def free(self, box):
        r0, r1, c0, c1 = self.rect(box)
        if r1 <= r0 or c1 <= c0:
            return False, False
        return not self.hard[r0:r1, c0:c1].any(), not self.soft[r0:r1, c0:c1].any()

    def block(self, box, grow=None):
        r0, r1, c0, c1 = self.rect(box, ITEM_GAP if grow is None else grow)
        self.hard[r0:r1, c0:c1] = True


def spot(field, box_at, x, y, reach=None):
    """Nearest position to (x, y) (0.05 steps, within reach) where box_at(x, y) is free of hard obstacles; a spot also
    clear of vias is taken when it is at most 0.6 mm further. -> (x, y, distance, over_via) or None"""
    reach = REACH if reach is None else reach
    n = int(round(reach / 0.05))
    cands = sorted((i * i + j * j, i, j) for i in range(-n, n + 1) for j in range(-n, n + 1) if i * i + j * j <= n * n)
    first = None
    for d2, i, j in cands:
        d = math.sqrt(d2) * 0.05
        if first is not None and d > first[2] + 0.6:
            break
        px, py = x + i * 0.05, y + j * 0.05
        ok, clean = field.free(box_at(px, py))
        if ok and clean:
            return round(px, 3), round(py, 3), d, False
        if ok and first is None:
            first = (round(px, 3), round(py, 3), d, True)
    return first


# ------------------------------------------------------------------------------------------------ glyphs
def glyph(kind):
    """Line art in a box of about 2.4 mm centred on (0, 0), y down: [("seg", (x, y), (x, y)) | ("arc", centre, r, a0, a1)
    | ("circle", centre, r) | ("dot", centre, r) | ("text", s, (x, y), size)]"""
    G = []
    seg = lambda a, b: G.append(("seg", a, b))
    if kind == "headphones":                        # headband arc and two ear cups
        G.append(("arc", (0, 0.3), 1.0, 180, 360))
        for sx in (-1, 1):
            seg((sx * 1.0, 0.3), (sx * 1.0, 0.9))
            G += [("seg", (sx * 0.75, 0.25), (sx * 0.75, 1.15)), ("seg", (sx * 0.75, 0.25), (sx * 1.15, 0.25)),
                  ("seg", (sx * 1.15, 0.25), (sx * 1.15, 1.15)), ("seg", (sx * 0.75, 1.15), (sx * 1.15, 1.15))]
    elif kind == "linein":                          # an arrow into a jack ring
        G.append(("circle", (0.45, 0), 0.55))
        seg((-1.1, 0), (0.1, 0)); seg((0.1, 0), (-0.25, -0.35)); seg((0.1, 0), (-0.25, 0.35))
    elif kind == "sdcard":                          # card outline with the clipped corner and contacts
        pts = [(-0.8, -1.1), (0.45, -1.1), (0.8, -0.75), (0.8, 1.1), (-0.8, 1.1), (-0.8, -1.1)]
        for a, b in zip(pts, pts[1:]):
            seg(a, b)
        for k in range(4):
            seg((-0.5 + k * 0.3, -0.75), (-0.5 + k * 0.3, -0.35))
    elif kind == "ethernet":                        # RJ45 socket face: body, latch notch, contacts
        pts = [(-1.1, -0.9), (1.1, -0.9), (1.1, 0.7), (0.45, 0.7), (0.45, 1.05), (-0.45, 1.05), (-0.45, 0.7), (-1.1, 0.7), (-1.1, -0.9)]
        for a, b in zip(pts, pts[1:]):
            seg(a, b)
        for k in range(4):
            seg((-0.6 + k * 0.4, -0.9), (-0.6 + k * 0.4, -0.45))
    elif kind == "display":                         # monitor and stand
        pts = [(-1.2, -0.9), (1.2, -0.9), (1.2, 0.6), (-1.2, 0.6), (-1.2, -0.9)]
        for a, b in zip(pts, pts[1:]):
            seg(a, b)
        seg((0, 0.6), (0, 1.0)); seg((-0.5, 1.05), (0.5, 1.05))
    elif kind == "dcjack":                          # centre positive: + -- (o -- -
        G.append(("arc", (0, 0), 0.5, 220, 500)); G.append(("dot", (0, 0), 0.15))  # sleeve (C open to the left), pin
        seg((0, 0), (-1.15, 0)); seg((-1.6, -0.25), (-1.6, 0.25)); seg((-1.85, 0), (-1.35, 0))   # pin to +
        seg((0.5, 0), (1.15, 0)); seg((1.35, 0), (1.85, 0))                                   # sleeve to -
    elif kind == "warning":                         # triangle with "!"
        h = 1.9
        pts = [(0, -h / 2), (h / 2 * 1.1, h / 2), (-h / 2 * 1.1, h / 2), (0, -h / 2)]
        for a, b in zip(pts, pts[1:]):
            seg(a, b)
        seg((0, -0.35), (0, 0.35)); G.append(("dot", (0, 0.65), 0.08))
    elif kind == "bug":                             # debug: a beetle
        G.append(("circle", (0, 0.2), 0.55)); G.append(("circle", (0, -0.6), 0.25))
        seg((0, -0.35), (0, 0.75))
        for sy in (-0.1, 0.25, 0.6):
            seg((-0.55, sy), (-1.0, sy - 0.15)); seg((0.55, sy), (1.0, sy - 0.15))
    elif kind == "can":                             # bus: two lines twisted once
        seg((-1.2, -0.45), (-0.4, -0.45)); seg((-0.4, -0.45), (0.4, 0.45)); seg((0.4, 0.45), (1.2, 0.45))
        seg((-1.2, 0.45), (-0.4, 0.45)); seg((-0.4, 0.45), (-0.1, 0.11)); seg((0.1, -0.11), (0.4, -0.45)); seg((0.4, -0.45), (1.2, -0.45))
    elif kind == "reset":                           # circular arrow
        G.append(("arc", (0, 0), 0.8, 300, 600))
        a = math.radians(300)
        tip = (0.8 * math.cos(a), 0.8 * math.sin(a))
        seg(tip, (tip[0] - 0.4, tip[1])); seg(tip, (tip[0] + 0.05, tip[1] + 0.4))
    elif kind == "button":                          # push button: cap over contacts
        G.append(("circle", (0, 0), 0.75)); G.append(("dot", (0, 0), 0.3))
    elif kind == "ground":                          # earth symbol
        seg((0, -1.0), (0, 0)); seg((-0.8, 0), (0.8, 0)); seg((-0.5, 0.35), (0.5, 0.35)); seg((-0.2, 0.7), (0.2, 0.7))
    elif kind == "mark":                            # the designer's mark: a trace bent into a C, a via at each end
        G.append(("arc", (0, 0), 0.9, 45, 315))
        for a in (45, 315):
            c = (0.9 * math.cos(math.radians(a)), 0.9 * math.sin(math.radians(a)))
            G.append(("circle", c, 0.22))
        G.append(("dot", (0, 0), 0.18))
    return G


def glyph_box(kind, s):
    xs, ys = [], []
    for g in glyph(kind):
        if g[0] == "seg":
            xs += [g[1][0], g[2][0]]; ys += [g[1][1], g[2][1]]
        elif g[0] in ("circle", "dot", "arc"):
            r = g[2]
            xs += [g[1][0] - r, g[1][0] + r]; ys += [g[1][1] - r, g[1][1] + r]
    pad = ICON_W
    return (min(xs) * s - pad, min(ys) * s - pad, max(xs) * s + pad, max(ys) * s + pad)


def draw_glyph(b, kind, x, y, s, side, width=None):
    import pcbnew
    width = ICON_W if width is None else width
    layer = pcbnew.F_SilkS if side == "F" else pcbnew.B_SilkS
    fx = -1 if side == "B" else 1          # the bottom is seen mirrored: draw the glyph mirrored so it reads right
    V = lambda px, py: pcbnew.VECTOR2I(pcbnew.FromMM(OX + x + fx * px * s), pcbnew.FromMM(OY + y + py * s))
    n = 0
    for g in glyph(kind):
        sh = pcbnew.PCB_SHAPE(b)
        sh.SetLayer(layer); sh.SetWidth(pcbnew.FromMM(width))
        if g[0] == "seg":
            sh.SetShape(pcbnew.SHAPE_T_SEGMENT); sh.SetStart(V(*g[1])); sh.SetEnd(V(*g[2]))
        elif g[0] in ("circle", "dot"):
            sh.SetShape(pcbnew.SHAPE_T_CIRCLE); sh.SetCenter(V(*g[1]))
            r = g[2]
            if g[0] == "dot":
                sh.SetFilled(True)
                r = max(r, width / 2 / s + 0.01)
            sh.SetEnd(V(g[1][0] + r * fx, g[1][1]))
        elif g[0] == "arc":
            (cx, cy), r, a0, a1 = g[1], g[2], g[3], g[4]
            am = (a0 + a1) / 2
            pt = lambda a: (cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
            sh.SetShape(pcbnew.SHAPE_T_ARC); sh.SetArcGeometry(V(*pt(a0)), V(*pt(am)), V(*pt(a1)))
        b.Add(sh)
        n += 1
    return n


def make_text(b, s, x, y, rot, size, side, bold=False):
    import pcbnew
    t = pcbnew.PCB_TEXT(b)
    t.SetText(s)
    t.SetLayer(pcbnew.F_SilkS if side == "F" else pcbnew.B_SilkS)
    h, w, th = size
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(w), pcbnew.FromMM(h)))
    t.SetTextThickness(pcbnew.FromMM(th))
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER); t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    t.SetTextAngle(pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T))
    if side == "B":
        t.SetMirrored(True)
    t.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y)))
    return t


def text_box(b, s, rot, size, side):
    """box of the text centred on (0, 0), local mm"""
    import pcbnew
    t = make_text(b, s, 0, 0, rot, size, side)
    sh = t.GetEffectiveTextShape()
    x0, y0, x1, y1 = mm_box(sh.BBox())
    g = size[2] / 2                                     # BBox of the stroke centre lines: add half the stroke
    return x0 - g, y0 - g, x1 + g, y1 + g


# ------------------------------------------------------------------------------------------------ main
def fields_to_fab(b):
    import pcbnew
    moved = hidden = 0
    for fp in b.GetFootprints():
        back = fp.GetLayer() == pcbnew.B_Cu
        silk = pcbnew.B_SilkS if back else pcbnew.F_SilkS
        fab = pcbnew.B_Fab if back else pcbnew.F_Fab
        has_fab_ref = any(isinstance(g, pcbnew.PCB_TEXT) and g.GetText() == "${REFERENCE}" and g.GetLayer() == fab for g in fp.GraphicalItems())
        r = fp.Reference()
        if r.GetLayer() == silk:
            if has_fab_ref:
                r.SetVisible(False); hidden += 1
            else:
                r.SetLayer(fab); moved += 1
        v = fp.Value()
        if v.GetLayer() == silk and v.IsVisible():
            v.SetVisible(False); hidden += 1
        for g in fp.GraphicalItems():
            if isinstance(g, pcbnew.PCB_TEXT) and g.GetLayer() == silk:
                g.SetLayer(fab); moved += 1
    return moved, hidden


def mask_fine(b):
    import pcbnew
    out = []
    for ref, m in MASK_FINE.items():
        fp = b.FindFootprintByReference(ref)
        fp.SetLocalSolderMaskMargin(pcbnew.FromMM(m))
        out.append("%s %.2f" % (ref, m))
    return out


def a1_dots(b):
    """A1 corner dots of the parts of [a1] (the BGAs), outside the body, at the corner nearest that ball"""
    import pcbnew
    res = []
    for ref, ball in A1:
        fp = b.FindFootprintByReference(ref)
        x0, y0, x1, y1 = mm_box(fp.GetCourtyard(pcbnew.F_CrtYd).BBox())
        p = next(q for q in fp.Pads() if q.GetNumber() == ball)
        px, py = pcbnew.ToMM(p.GetPosition().x) - OX, pcbnew.ToMM(p.GetPosition().y) - OY
        cx = x0 - 0.35 if abs(px - x0) < abs(px - x1) else x1 + 0.35
        cy = y0 - 0.35 if abs(py - y0) < abs(py - y1) else y1 + 0.35
        res.append((ref, cx, cy))
    return res


def main(path, out):
    import pcbnew
    from Tools.KiCadDesignTools.finishing import finish
    b = pcbnew.LoadBoard(path)
    moved, hidden = fields_to_fab(b)
    b.GetPlotOptions().SetSubtractMaskFromSilk(True)           # Gerbers: silkscreen clipped at solder-mask openings
    masks = mask_fine(b)
    fields = {"F": Field(b, "F"), "B": Field(b, "B")}
    log, stuck, n_items = [], [], 0

    def place_text(s, x, y, rot, size, side, reach=REACH):
        nonlocal n_items
        bx = text_box(b, s, rot, size, side)
        f = fields[side]
        r = spot(f, lambda px, py: (px + bx[0], py + bx[1], px + bx[2], py + bx[3]), x, y, reach)
        if r is None:
            stuck.append("%s text %r at (%.2f, %.2f)" % (side, s, x, y))
            return None
        px, py, d, over = r
        b.Add(make_text(b, s, px, py, rot, size, side))
        f.block((px + bx[0], py + bx[1], px + bx[2], py + bx[3]))
        n_items += 1
        if d > 0.01 or over:
            log.append("%s %r moved %.2f mm%s" % (side, s, d, " (over a tented via)" if over else ""))
        return px, py, bx

    def place_icon(kind, x, y, s, side, reach=REACH, width=ICON_W):
        nonlocal n_items
        bx = glyph_box(kind, s)
        if side == "B":
            bx = (-bx[2], bx[1], -bx[0], bx[3])
        f = fields[side]
        r = spot(f, lambda px, py: (px + bx[0], py + bx[1], px + bx[2], py + bx[3]), x, y, reach)
        if r is None:
            stuck.append("%s icon %s at (%.2f, %.2f)" % (side, kind, x, y))
            return None
        px, py, d, over = r
        draw_glyph(b, kind, px, py, s, side, width)
        f.block((px + bx[0], py + bx[1], px + bx[2], py + bx[3]))
        n_items += 1
        if d > 0.01 or over:
            log.append("%s icon %s moved %.2f mm%s" % (side, kind, d, " (over a tented via)" if over else ""))
        return px, py

    # 1. the title blocks first (they need the largest free areas)
    title_block(b, fields["F"], place_text, place_icon, log, stuck)
    # 2. BGA A1 dots
    for ref, cx, cy in a1_dots(b):
        f = fields["F"]
        ok, _ = f.free((cx - 0.3, cy - 0.3, cx + 0.3, cy + 0.3))
        sh = pcbnew.PCB_SHAPE(b); sh.SetShape(pcbnew.SHAPE_T_CIRCLE); sh.SetLayer(pcbnew.F_SilkS)
        sh.SetWidth(pcbnew.FromMM(0.15)); sh.SetFilled(True)
        sh.SetCenter(pcbnew.VECTOR2I(pcbnew.FromMM(OX + cx), pcbnew.FromMM(OY + cy)))
        sh.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(OX + cx + 0.2), pcbnew.FromMM(OY + cy)))
        b.Add(sh); f.block((cx - 0.3, cy - 0.3, cx + 0.3, cy + 0.3)); n_items += 1
        if not ok:
            log.append("F A1 dot of %s at (%.2f, %.2f) touches an obstacle" % (ref, cx, cy))
    # 3. labels and icons
    for s, x, y, rot, size, side in TEXT:
        place_text(s, x, y, rot, size, side)
    for kind, x, y, sc, side, *reach in ICONS:
        place_icon(kind, x, y, sc, side, reach=reach[0] if reach else REACH)
    finish.save_board(b, path)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "silk.txt"), "w", encoding="utf-8") as fh:
        fh.write("silkscreen: %d items placed (texts, glyphs, dots); references to Fab %d, hidden %d; solder-mask expansion %s\n"
                 % (n_items, moved, hidden, ", ".join(masks)))
        for l in log:
            fh.write("  " + l + "\n")
        for s in stuck:
            fh.write("  NO SPOT: " + s + "\n")
    print("silk: %d items, %d moved, %d without a spot; references to Fab %d, hidden %d; mask %s"
          % (n_items, len(log), len(stuck), moved, hidden, ", ".join(masks)))
    for s in stuck:
        print("  NO SPOT:", s)


def title_block(b, field, place_text, place_icon, log, stuck):
    """The [[title]] blocks of silk.toml in order, each item at the block's anchor + d."""
    for tb in TITLES:
        x, y = tb["at"]
        for it in tb["items"]:
            dx, dy = it["d"]
            if "text" in it:
                place_text(it["text"], x + dx, y + dy, 0, SIZES[it["size"]], tb["side"], reach=it["reach"])
            else:
                place_icon(it["icon"], x + dx, y + dy, it["scale"], tb["side"], reach=it["reach"])


def reserved(b, grow=0.4):
    """Boxes (x0, y0, x1, y1) of every label and glyph at its anchor, both sides: the stitching vias keep out of them
    (FIN-4 puts the vias first; this keeps the label spots free of via bumps)"""
    out = []
    for txt, x, y, rot, size, side in TEXT:
        bx = text_box(b, txt, rot, size, side)
        out.append((x + bx[0] - grow, y + bx[1] - grow, x + bx[2] + grow, y + bx[3] + grow))
    for kind, x, y, sc, side, *reach in ICONS:
        bx = glyph_box(kind, sc)
        out.append((x - max(-bx[0], bx[2]) - grow, y + bx[1] - grow, x + max(-bx[0], bx[2]) + grow, y + bx[3] + grow))
    for tb in TITLES:
        x, y = tb["at"]
        r0, r1, r2, r3 = tb["reserve"]
        out.append((x + r0, y + r1, x + r2, y + r3))
    return out
