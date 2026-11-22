"""Pictures of the filled copper, one per layer, for the reviewer (qualitative only: necks, planes cut by via rows,
islands; every number comes from the board file, PROC-14).

    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\copper_view.py <board> <out dir> [L1 L2 L3 L6 ...] [--scale 14]
                                                          [--window x0 y0 x1 y1 --name <suffix>]

Reads the fills KiCad saved (kicad-cli pcb drc --refill-zones --save-board). Each net's fill has its own colour
(ground grey-green, the rails in strong colours, named once in the legend); pads of the layer, tracks and vias on
top; vias of the power group as rings; the two BGA rule areas dashed; a 5 mm grid in local coordinates
(board mm - 100).
"""
import colorsys, os, sys, zlib
import pcbnew
from PIL import Image, ImageDraw, ImageFont

OX = OY = 100.0


FIXED = {"GND": (150, 170, 150), "+3V3": (205, 220, 120), "+5V": (235, 150, 60), "+3V3A": (90, 190, 230),
         "+3V3_MCU": (225, 90, 160), "+3V3_SDRAM": (200, 70, 60), "+12V": (120, 90, 220)}


def colour(net):
    if net in FIXED:
        return FIXED[net]
    h = (zlib.crc32(net.encode()) % 360) / 360.0
    r, g, b = colorsys.hls_to_rgb(h, 0.5, 0.75)
    return (int(r * 255), int(g * 255), int(b * 255))


def main(argv):
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
    path, out = args[0], args[1]
    layers = args[2:] or ["L1", "L2", "L3", "L6"]
    b = pcbnew.LoadBoard(path)
    mm = pcbnew.ToMM
    ids = list(b.GetEnabledLayers().CuStack())
    lid = {"L%d" % (i + 1): l for i, l in enumerate(ids)}
    bb = b.GetBoardEdgesBoundingBox()
    x0, y0, x1, y1 = win or (mm(bb.GetLeft()) - OX - 1, mm(bb.GetTop()) - OY - 1, mm(bb.GetRight()) - OX + 1, mm(bb.GetBottom()) - OY + 1)
    TOP = 64
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
        zones = sorted((z for z in b.Zones() if not z.GetIsRuleArea() and z.IsOnLayer(layer)), key=lambda z: z.GetAssignedPriority())
        for z in zones:
            c = colour(z.GetNetname())
            if z.GetNetname() not in nets:
                nets.append(z.GetNetname())
            f = z.GetFilledPolysList(layer)
            f = pcbnew.SHAPE_POLY_SET(f)
            f.Fracture()
            for i in range(f.OutlineCount()):
                o = f.Outline(i)
                d.polygon([P(o.CPoint(k)) for k in range(o.PointCount())], fill=c + (150,))
        for z in b.Zones():                                     # rule areas
            if z.GetIsRuleArea() and z.GetZoneName():
                o = z.Outline().Outline(0)
                pts = [P(o.CPoint(k)) for k in range(o.PointCount())]
                for a, c2 in zip(pts, pts[1:] + pts[:1]):
                    n = int(max(abs(a[0] - c2[0]), abs(a[1] - c2[1])) / 8) + 1
                    for k in range(0, n, 2):
                        d.line([(a[0] + (c2[0] - a[0]) * k / n, a[1] + (c2[1] - a[1]) * k / n),
                                (a[0] + (c2[0] - a[0]) * (k + 1) / n, a[1] + (c2[1] - a[1]) * (k + 1) / n)], fill=(0, 0, 0), width=1)
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
            elif t.GetLayer() == layer:
                d.line([P(t.GetStart()), P(t.GetEnd())], fill=colour(t.GetNetname()) + (255,), width=max(1, int(mm(t.GetWidth()) * sc)))
        for dr in b.GetDrawings():
            if dr.GetLayer() == pcbnew.Edge_Cuts:
                if dr.GetShape() == pcbnew.SHAPE_T_SEGMENT:
                    d.line([P(dr.GetStart()), P(dr.GetEnd())], fill=(0, 0, 0), width=2)
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
        d.text((6, ty + 18), "vias: rings in the net colour (ground dark green); BGA rule areas dashed; grid 5 mm, local coordinates", fill=(90, 90, 90), font=font)
        fn = os.path.join(out, "%s%s.png" % (L, name))
        img.save(fn)
        print(fn)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
