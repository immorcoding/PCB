"""Draw one copper layer of a region with a 1 mm coordinate grid, for planning hand routes.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.views.layer_view <board> <out.png> <F.Cu|B.Cu> x0 y0 x1 y1 [scale]

Coordinates are local (board mm - 100). Tracks and pads of the chosen layer are drawn in
colour with the net name on longer tracks; vias in black; pads of the other outer layer as
grey outlines. For qualitative planning only: read exact numbers from the file.
"""
import sys
import pcbnew
from PIL import Image, ImageDraw, ImageFont

path, out, lname = sys.argv[1:4]
x0, y0, x1, y1 = map(float, sys.argv[4:8])
sc = float(sys.argv[8]) if len(sys.argv) > 8 else 60
b = pcbnew.LoadBoard(path); mm = pcbnew.ToMM
layer = b.GetLayerID(lname)
img = Image.new("RGB", (int((x1 - x0) * sc), int((y1 - y0) * sc)), (252, 252, 250))
d = ImageDraw.Draw(img, "RGBA")
try:
    font = ImageFont.truetype("arial.ttf", int(sc * 0.28)); small = ImageFont.truetype("arial.ttf", int(sc * 0.2))
except OSError:
    font = small = ImageFont.load_default()
X = lambda x, y: ((x - x0) * sc, (y - y0) * sc)
L = lambda v: (mm(v.x) - 100, mm(v.y) - 100)
for gx in range(int(x0) - 1, int(x1) + 2):
    d.line([X(gx, y0), X(gx, y1)], fill=(0, 0, 0, 60 if gx % 5 == 0 else 22), width=1)
    d.text(X(gx + 0.03, y0 + 0.02), str(gx), fill=(90, 90, 90), font=small)
for gy in range(int(y0) - 1, int(y1) + 2):
    d.line([X(x0, gy), X(x1, gy)], fill=(0, 0, 0, 60 if gy % 5 == 0 else 22), width=1)
    d.text(X(x0 + 0.03, gy + 0.02), str(gy), fill=(90, 90, 90), font=small)


def colour(name):
    h = sum(ord(c) * (i + 3) for i, c in enumerate(name))
    return (40 + h % 170, 40 + (h // 7) % 150, 60 + (h // 13) % 170)


for fp in b.GetFootprints():
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        box = [X(mm(bb.GetLeft()) - 100, mm(bb.GetTop()) - 100), X(mm(bb.GetRight()) - 100, mm(bb.GetBottom()) - 100)]
        if p.IsOnLayer(layer):
            d.rectangle(box, fill=colour(p.GetNetname()) + (150,) if p.GetNetname() else (150, 150, 150, 120))
            d.text(box[0], f"{fp.GetReference()}.{p.GetNumber()}", fill=(0, 0, 0), font=small)
        else:
            d.rectangle(box, outline=(150, 150, 150, 160))
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        c = L(t.GetPosition()); r = mm(t.GetWidth(pcbnew.F_Cu)) / 2
        d.ellipse([X(c[0] - r, c[1] - r), X(c[0] + r, c[1] + r)], fill=(20, 20, 20, 230))
        d.text(X(c[0] + r, c[1] - r), t.GetNetname().lstrip("/"), fill=(0, 0, 0), font=small)
    elif t.GetLayer() == layer:
        a, c = L(t.GetStart()), L(t.GetEnd())
        d.line([X(*a), X(*c)], fill=colour(t.GetNetname()) + (235,), width=max(2, int(mm(t.GetWidth()) * sc)))
        if abs(a[0] - c[0]) + abs(a[1] - c[1]) > 2.5:
            d.text(X((a[0] + c[0]) / 2, (a[1] + c[1]) / 2 - 0.3), t.GetNetname().lstrip("/"), fill=(0, 0, 0), font=small)
img.save(out)
print("wrote", out, img.size)
