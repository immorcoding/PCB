"""Pictures of the filled copper, one per layer, for the reviewer (qualitative only: necks, planes cut by via rows,
islands; every number comes from the board file, PROC-14).

    python -m Tools.KiCadDesignTools.views.copper_view <board dir> <board> <out dir> [L1 L2 L5 L6 ...] [--scale 14]
                                                       [--window x0 y0 x1 y1 --name <suffix>]
                                                       [--slots <slots.json> [--slot-min 3.0]] [--via-labels]

Reads the fills KiCad saved (kicad-cli pcb drc --refill-zones --save-board). Each net's fill has its own colour
(ground grey-green, the rails in strong colours, named once in the legend); pads of the layer, tracks and vias on
top; vias of the power group as rings; the two BGA rule areas dashed; a 5 mm grid in local coordinates
(board mm - origin). --slots marks the plane slots of copper.plane_slots (slots.json) on the drawn layer that are
at least --slot-min long (default: the longest of the layer) with a red line between their two far ends, labelled
with the length and both ends in local and board-file coordinates; --via-labels writes each via's net beside it
(without the prefix [copper_view] label_strip).

board.toml [copper_view]: layers (drawn when none are given), colours ({net: [r, g, b]}; other nets get a colour from
their name), label_strip; the origin is [board] origin. Arcs are drawn by the board folder's finish_pour.arc_pts.
"""
import colorsys, json, os, sys, zlib
import pcbnew
from PIL import Image, ImageDraw, ImageFont

from Tools.KiCadDesignTools.core import config

FIXED = {}                       # net -> colour, from [copper_view] colours (main)


def colour(net):
    if net in FIXED:
        return FIXED[net]
    h = (zlib.crc32(net.encode()) % 360) / 360.0
    r, g, b = colorsys.hls_to_rgb(h, 0.5, 0.75)
    return (int(r * 255), int(g * 255), int(b * 255))


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    cfg = config.load(argv[0])
    argv = argv[1:]
    cv = cfg.need("copper_view")
    FIXED.clear()
    FIXED.update({n: tuple(c) for n, c in cv.get("colours", {}).items()})
    OX, OY = cfg.origin
    strip = cv.get("label_strip", "")
    args = [a for a in argv if not a.startswith("--")]
    sc = float(argv[argv.index("--scale") + 1]) if "--scale" in argv else 14.0
    if "--scale" in argv:
        args.remove(argv[argv.index("--scale") + 1])
    win, name = None, ""
    if "--window" in argv:
        k = argv.index("--window")
        win = [float(v) for v in argv[k + 1:k + 5]]
        for v in argv[k + 1:k + 5]:
            args.remove(v)
    if "--name" in argv:
        name = "_" + argv[argv.index("--name") + 1]
        args.remove(argv[argv.index("--name") + 1])
    slots, slot_min = None, None
    if "--slots" in argv:
        slots = json.load(open(argv[argv.index("--slots") + 1], encoding="utf-8"))
        args.remove(argv[argv.index("--slots") + 1])
    if "--slot-min" in argv:
        slot_min = float(argv[argv.index("--slot-min") + 1])
        args.remove(argv[argv.index("--slot-min") + 1])
    via_labels = "--via-labels" in argv
    try:
        small = ImageFont.truetype("arial.ttf", 11)
    except OSError:
        small = ImageFont.load_default()
    path, out = args[0], args[1]
    layers = args[2:] or list(cv["layers"])
    b = pcbnew.LoadBoard(path)
    mm = pcbnew.ToMM
    ids = list(b.GetEnabledLayers().CuStack())
    lid = {"L%d" % (i + 1): l for i, l in enumerate(ids)}
    bb = b.GetBoardEdgesBoundingBox()
    x0, y0, x1, y1 = win or (mm(bb.GetLeft()) - OX - 1, mm(bb.GetTop()) - OY - 1, mm(bb.GetRight()) - OX + 1, mm(bb.GetBottom()) - OY + 1)
    TOP = 64 if not slots else 100
    W, H = int((x1 - x0) * sc), int((y1 - y0) * sc) + TOP
    try:
        font = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    X = lambda x, y: ((x - x0) * sc, (y - y0) * sc + TOP)
    P = lambda v: X(mm(v.x) - OX, mm(v.y) - OY)
    os.makedirs(out, exist_ok=True)
    for L in layers:
        layer = lid[L]
        img = Image.new("RGB", (W, H), (255, 255, 255))
        d = ImageDraw.Draw(img, "RGBA")
        for g in range(int(x0 // 5 * 5), int(x1) + 1, 5):
            d.line([X(g, y0), X(g, y1)], fill=(232, 232, 232)); d.text(X(g + 0.1, y0), str(g), fill=(160, 160, 160), font=font)
        for g in range(int(y0 // 5 * 5), int(y1) + 1, 5):
            d.line([X(x0, g), X(x1, g)], fill=(232, 232, 232)); d.text(X(x0, g + 0.1), str(g), fill=(160, 160, 160), font=font)
        nets = []
        def in_window(z):                                        # the legend names only the zones the picture shows
            if not win:
                return True
            bb = z.GetFilledPolysList(layer).BBox()
            return bb.GetWidth() > 0 and mm(bb.GetLeft()) - OX < x1 and mm(bb.GetRight()) - OX > x0 and \
                mm(bb.GetTop()) - OY < y1 and mm(bb.GetBottom()) - OY > y0
        zones = sorted((z for z in b.Zones() if not z.GetIsRuleArea() and z.IsOnLayer(layer)), key=lambda z: z.GetAssignedPriority())
        for z in zones:
            c = colour(z.GetNetname())
            if z.GetNetname() not in nets and not z.IsTeardropArea() and in_window(z):   # teardrops drawn, not named
                nets.append(z.GetNetname())
            f = z.GetFilledPolysList(layer)
            f = pcbnew.SHAPE_POLY_SET(f)
            f.Fracture()
            for i in range(f.OutlineCount()):
                o = f.Outline(i)
                d.polygon([P(o.CPoint(k)) for k in range(o.PointCount())], fill=c + (150,))
        for z in b.Zones():                                     # rule areas of this layer; pour keep-outs (FIN_) in red
            if z.GetIsRuleArea() and z.GetZoneName() and z.IsOnLayer(layer):
                o = z.Outline().Outline(0)
                pts = [P(o.CPoint(k)) for k in range(o.PointCount())]
                ink = (220, 0, 0) if z.GetZoneName().startswith("FIN_") and not z.GetZoneName().startswith("FIN_FID") else (0, 0, 0)
                for a, c2 in zip(pts, pts[1:] + pts[:1]):
                    n = int(max(abs(a[0] - c2[0]), abs(a[1] - c2[1])) / 8) + 1
                    for k in range(0, n, 2):
                        d.line([(a[0] + (c2[0] - a[0]) * k / n, a[1] + (c2[1] - a[1]) * k / n),
                                (a[0] + (c2[0] - a[0]) * (k + 1) / n, a[1] + (c2[1] - a[1]) * (k + 1) / n)], fill=ink, width=1)
        for f in b.GetFootprints():
            for p in f.Pads():
                if not p.IsOnLayer(layer):
                    continue
                try:
                    o = p.GetEffectivePolygon(layer, pcbnew.ERROR_INSIDE).Outline(0)
                except Exception:
                    continue
                c = colour(p.GetNetname()) if p.GetNetname() else (200, 200, 200)
                d.polygon([P(o.CPoint(k)) for k in range(o.PointCount())], fill=(250, 250, 250, 255), outline=(60, 60, 60))
                d.polygon([P(o.CPoint(k)) for k in range(o.PointCount())], fill=c + (110,))
        for t in b.GetTracks():
            if t.Type() == pcbnew.PCB_VIA_T:
                c, r = P(t.GetPosition()), mm(t.GetWidth(pcbnew.F_Cu)) / 2 * sc
                d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=(255, 255, 255), outline=colour(t.GetNetname()) if t.GetNetname() != "GND" else (40, 90, 40), width=2)
            elif t.GetLayer() == layer and t.Type() == pcbnew.PCB_ARC_T:     # serpentine arcs as arcs, not chords
                finish_pour = cfg.module("finish_pour")       # the board folder's (moves to Tools in a later batch)
                s_, m_, e_ = t.GetStart(), t.GetMid(), t.GetEnd()
                pts = finish_pour.arc_pts((mm(s_.x), mm(s_.y)), (mm(m_.x), mm(m_.y)), (mm(e_.x), mm(e_.y)), 12)
                d.line([X(x - OX, y - OY) for x, y in pts], fill=colour(t.GetNetname()) + (255,), width=max(1, int(mm(t.GetWidth()) * sc)))
            elif t.GetLayer() == layer:
                d.line([P(t.GetStart()), P(t.GetEnd())], fill=colour(t.GetNetname()) + (255,), width=max(1, int(mm(t.GetWidth()) * sc)))
        for dr in b.GetDrawings():
            if dr.GetLayer() == pcbnew.Edge_Cuts:
                if dr.GetShape() == pcbnew.SHAPE_T_SEGMENT:
                    d.line([P(dr.GetStart()), P(dr.GetEnd())], fill=(0, 0, 0), width=2)
        if via_labels:
            for t in b.GetTracks():
                if t.Type() == pcbnew.PCB_VIA_T:
                    x, y = mm(t.GetPosition().x) - OX, mm(t.GetPosition().y) - OY
                    if x0 <= x <= x1 and y0 <= y <= y1:
                        r = mm(t.GetWidth(pcbnew.F_Cu)) / 2
                        n = t.GetNetname()
                        n = n[len(strip):] if strip and n.startswith(strip) else n
                        d.text(X(x + r * 0.7, y - r * 0.7 - 0.28), n, fill=(20, 20, 20), font=small)
        marked = []
        if slots:
            mine = [s for s in slots["slots"] if s["layer"] == L and all(x0 <= px <= x1 and y0 <= py <= y1 for px, py in s["ends"])]
            lim = slot_min if slot_min is not None else max((s["length"] for s in mine), default=0)
            for s in mine:
                (ax, ay), (cx, cy) = s["ends"]
                if s["length"] < lim - 1e-9:
                    continue
                d.line([X(ax, ay), X(cx, cy)], fill=(230, 0, 0, 255), width=4)
                for px, py in s["ends"]:
                    q = X(px, py)
                    d.ellipse([q[0] - 5, q[1] - 5, q[0] + 5, q[1] + 5], outline=(230, 0, 0), width=2)
                q = X((ax + cx) / 2, (ay + cy) / 2)
                d.text((q[0] + 8, q[1] - 6), "%.2f mm" % s["length"], fill=(230, 0, 0), font=font)
                marked.append(s)
        d.rectangle([0, 0, W, TOP - 1], fill=(255, 255, 255))   # copper beyond the window's top edge stays out of the legend
        head = "%s  (%s)  zones: " % (L, os.path.basename(path))
        d.text((6, 4), head, fill=(0, 0, 0), font=font)
        tx, ty = 6 + d.textlength(head, font=font), 4
        for n in nets:
            wn = 22 + d.textlength(n, font=font)
            if tx + wn > W - 6:
                tx, ty = 6, ty + 17
            d.rectangle([tx, ty + 2, tx + 12, ty + 14], fill=colour(n))
            d.text((tx + 15, ty), n, fill=(0, 0, 0), font=font)
            tx += wn
        d.text((6, ty + 18), "vias: rings in the net colour (ground dark green); rule areas of the layer dashed, pour keep-outs red; grid 5 mm, local coordinates"
               + ("; via labels: net name, %s left out" % strip if via_labels else ""), fill=(90, 90, 90), font=font)
        for k, s in enumerate(marked):
            (ax, ay), (cx, cy) = s["ends"]
            d.text((6, ty + 36 + 17 * k), "red: plane slot %.2f mm (%s, %d vias) from (%.2f, %.2f) to (%.2f, %.2f) local = (%.2f, %.2f) to (%.2f, %.2f) in the board file"
                   % (s["length"], s["net"], s["vias"], ax, ay, cx, cy, ax + OX, ay + OY, cx + OX, cy + OY), fill=(200, 0, 0), font=font)
        fn = os.path.join(out, "%s%s.png" % (L, name))
        img.save(fn)
        print(fn)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
