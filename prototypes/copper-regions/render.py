"""PROTOTYPE (issue 16): pictures of the filled copper, one per view, same views for every variant.

    D:\\KiCad\\bin\\python.exe render.py <variant dir>

Reads the fill KiCad saved in h7cu.kicad_pcb (run kicad-cli with --refill-zones --save-board first).
For qualitative review only (PROC-14): numbers come from measure.py.
"""
import os, sys
import pcbnew
from PIL import Image, ImageDraw, ImageFont
from culib import *

VIEWS = [  # key, layer, x0, y0, x1, y1, px per mm
    ("L3", "In2.Cu", -1, -1, 86, 76, 14),
    ("L1", "F.Cu", -1, -1, 86, 76, 14),
    ("L1_power", "F.Cu", 52, 26, 74, 66, 34),
    ("L1_audio", "F.Cu", 6, 18, 36, 32, 44),
    ("L3_mcu", "In2.Cu", 30, 28, 58, 46, 44),
    ("L2_mcu", "In1.Cu", 30, 28, 58, 46, 44),
]
BG = (253, 253, 250)
SS = 2      # supersampling


def font(px):
    try:
        return ImageFont.truetype("arial.ttf", px)
    except OSError:
        return ImageFont.load_default()


def draw_view(B, key, lname, x0, y0, x1, y1, sc, out):
    lid = LID[lname]; s = sc * SS
    img = Image.new("RGB", (int((x1 - x0) * s), int((y1 - y0) * s)), BG)
    d = ImageDraw.Draw(img, "RGBA")
    X = lambda p: ((p[0] - x0) * s, (p[1] - y0) * s)

    zs = sorted([z for z in zones(B) if z.GetLayer() == lid], key=lambda z: -z.GetFilledPolysList(lid).Area())
    for z in zs:
        col = COLOUR.get(z.GetNetname(), (120, 120, 120))
        fill = z.GetFilledPolysList(lid)
        for i in range(fill.OutlineCount()):
            d.polygon([X(p) for p in chain_pts(fill.Outline(i))], fill=col + (255,))
            for h in range(fill.HoleCount(i)):
                d.polygon([X(p) for p in chain_pts(fill.Hole(i, h))], fill=BG + (255,))
    for z in zs:                                             # the outline as drawn, over the fill
        col = tuple(int(c * 0.45) for c in COLOUR.get(z.GetNetname(), (120, 120, 120)))
        o = z.Outline()
        for i in range(o.OutlineCount()):
            for ch in [o.Outline(i)] + [o.Hole(i, h) for h in range(o.HoleCount(i))]:
                pts = [X(p) for p in chain_pts(ch)]
                d.line(pts + pts[:1], fill=col + (255,), width=max(1, SS))

    for t in B.GetTracks():                                  # tracks of the layer, vias on every layer
        col = COLOUR.get(t.GetNetname(), (70, 70, 70))
        if t.Type() == pcbnew.PCB_VIA_T:
            cx, cy = X(L(t.GetPosition())); r = mm(t.GetWidth(pcbnew.F_Cu)) / 2 * s; h = mm(t.GetDrill()) / 2 * s
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=tuple(int(c * 0.6) for c in col) + (255,))
            d.ellipse([cx - h, cy - h, cx + h, cy + h], fill=(255, 255, 255, 255))
        elif t.GetLayer() == lid:
            d.line([X(L(t.GetStart())), X(L(t.GetEnd()))], fill=tuple(int(c * 0.6) for c in col) + (255,),
                   width=max(1, int(mm(t.GetWidth()) * s)))
    f_ref = font(int(max(9, min(1.0 * sc, 22)) * SS))
    for fp in B.GetFootprints():
        cy_ = fp.GetCourtyard(pcbnew.F_CrtYd)
        for i in range(cy_.OutlineCount()):
            pts = [X(p) for p in chain_pts(cy_.Outline(i))]
            d.line(pts + pts[:1], fill=(0, 0, 0, 70), width=max(1, SS // 2))
        for p in fp.Pads():
            if not (p.HasHole() or p.IsOnLayer(lid)):
                continue
            bb = p.GetBoundingBox()
            a = X(L(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))); c = X(L(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom())))
            col = COLOUR.get(p.GetNetname(), (95, 95, 95))
            dark = tuple(int(v * 0.55) for v in col)
            if p.HasHole():
                d.ellipse([a, c], fill=dark + (255,))
                cx, cy = X(L(p.GetPosition())); h = mm(p.GetDrillSize().x) / 2 * s
                d.ellipse([cx - h, cy - h, cx + h, cy + h], fill=(255, 255, 255, 255))
            elif p.GetShape() == pcbnew.PAD_SHAPE_CIRCLE:
                d.ellipse([a, c], fill=dark + (235,))
            else:
                d.rectangle([a, c], fill=dark + (235,))
        if sc >= 30 or len(list(fp.Pads())) > 20:
            cx, cy = X(L(fp.GetPosition()))
            d.text((cx, cy), fp.GetReference(), fill=(0, 0, 0, 200), font=f_ref, anchor="mm")

    edge = pcbnew.SHAPE_POLY_SET(); B.GetBoardPolygonOutlines(edge, True)
    for i in range(edge.OutlineCount()):
        for ch in [edge.Outline(i)] + [edge.Hole(i, h) for h in range(edge.HoleCount(i))]:
            pts = [X(p) for p in chain_pts(ch)]
            d.line(pts + pts[:1], fill=(0, 0, 0, 255), width=2 * SS)
    for name, (ax0, ay0, ax1, ay1) in BGA.items():
        d.rectangle([X((ax0, ay0)), X((ax1, ay1))], outline=(0, 0, 0, 90), width=SS)

    step = 5 if sc < 30 else 1
    f_grid = font(int(9 * SS if sc < 30 else 11 * SS))
    for g in range(int(x0 // step) * step, int(x1) + 1, step):
        if g > x0:
            d.line([X((g, y0)), X((g, y1))], fill=(0, 0, 0, 26 if g % 5 else 46), width=1)
            if g % 5 == 0:
                d.text(X((g + 0.1, y0 + 0.05)), str(g), fill=(60, 60, 60, 255), font=f_grid)
    for g in range(int(y0 // step) * step, int(y1) + 1, step):
        if g > y0:
            d.line([X((x0, g)), X((x1, g))], fill=(0, 0, 0, 26 if g % 5 else 46), width=1)
            if g % 5 == 0:
                d.text(X((x0 + 0.1, g + 0.05)), str(g), fill=(60, 60, 60, 255), font=f_grid)

    nets = [n for n in COPPER_NETS if any(z.GetNetname() == n for z in zs)]
    f_leg = font(13 * SS); yy = img.size[1] - (len(nets) * 18 + 10) * SS
    d.rectangle([6 * SS, yy - 4 * SS, 96 * SS, img.size[1] - 6 * SS], fill=(255, 255, 255, 225), outline=(0, 0, 0, 120))
    for n in nets:
        d.rectangle([12 * SS, yy, 26 * SS, yy + 12 * SS], fill=COLOUR[n] + (255,))
        d.text((32 * SS, yy - 2 * SS), n, fill=(0, 0, 0, 255), font=f_leg); yy += 18 * SS
    img = img.resize((img.size[0] // SS, img.size[1] // SS), Image.LANCZOS)
    img.save(out)


if __name__ == "__main__":
    vdir = sys.argv[1]
    B = pcbnew.LoadBoard(os.path.join(vdir, "h7cu.kicad_pcb"))
    for key, lname, x0, y0, x1, y1, sc in VIEWS:
        if len(sys.argv) > 2 and key not in sys.argv[2:]:
            continue
        draw_view(B, key, lname, x0, y0, x1, y1, sc, os.path.join(vdir, key + ".png"))
        print("wrote", os.path.join(vdir, key + ".png"))
