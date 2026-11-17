"""PROTOTYPE (issue 15): pictures of the routed group. Qualitative only (PROC-14): numbers come from
len_table.py and room.py.

    D:\\KiCad\\bin\\python.exe render.py <variant dir>      -> group.png, L1.png, L4.png in that folder

L1 tracks red, L4 tracks blue, vias black with a white hole, rule areas dashed, arcs drawn as arcs.
Coordinates on the grid are local mm (board file mm - 100).
"""
import math, os, sys
import pcbnew
from PIL import Image, ImageDraw, ImageFont

NAME = "lentune"
VIEWS = [  # file, layers shown, x0, y0, x1, y1, px per mm   (5 mm package gap)
    ("group", ("L1", "L4"), 6.0, 5.0, 33.0, 24.5, 60),
    ("L1", ("L1",), 12.5, 10.5, 27.0, 22.5, 110),
    ("L4", ("L4",), 13.5, 13.5, 27.5, 20.5, 110),
    ("crop_corridor", ("L1",), 18.6, 11.8, 22.6, 20.8, 190),      # close-ups: hump shape is judged here
    ("crop_south", ("L1",), 14.2, 17.8, 20.8, 23.0, 190),
    ("crop_L4", ("L4",), 18.6, 14.6, 22.6, 19.6, 190),
    ("crop_both", ("L1", "L4"), 18.6, 11.8, 22.6, 20.8, 190),     # both layers: where the L4 serpentines lie under the L1 ones
]
VIEWS_WIDE = [  # 8 mm package gap: the SDRAM is 3 mm further east
    ("group", ("L1", "L4"), 6.0, 5.0, 36.0, 24.5, 55),
    ("L1", ("L1",), 12.5, 10.0, 30.0, 22.5, 95),
    ("L4", ("L4",), 13.5, 13.5, 30.5, 20.5, 95),
    ("crop_corridor", ("L1",), 18.6, 10.6, 25.6, 20.8, 170),
    ("crop_south", ("L1",), 14.2, 17.8, 20.8, 23.0, 190),
    ("crop_L4", ("L4",), 18.6, 14.0, 25.6, 19.8, 170),
    ("crop_both", ("L1", "L4"), 18.6, 10.6, 25.6, 20.8, 170),
]
COL = {"L1": (200, 45, 40), "L4": (35, 95, 200)}
BG = (253, 253, 250)
SS = 2
mm = pcbnew.ToMM
Lp = lambda v: (mm(v.x) - 100, mm(v.y) - 100)


def font(px):
    try:
        return ImageFont.truetype("arial.ttf", int(px))
    except OSError:
        return ImageFont.load_default()


def arc_points(t, step=0.02):
    (x0, y0), (xm, ym), (x1, y1) = Lp(t.GetStart()), Lp(t.GetMid()), Lp(t.GetEnd())
    cx, cy = Lp(t.GetCenter())
    r = math.hypot(x0 - cx, y0 - cy)
    a0, am, a1 = (math.atan2(y - cy, x - cx) for x, y in ((x0, y0), (xm, ym), (x1, y1)))
    d = (a1 - a0) % (2 * math.pi)
    if (am - a0) % (2 * math.pi) > d:                       # the mid point lies the other way round
        d -= 2 * math.pi
    n = max(4, int(abs(d) * r / step))
    return [(cx + r * math.cos(a0 + d * i / n), cy + r * math.sin(a0 + d * i / n)) for i in range(n + 1)]


def draw(B, key, show, x0, y0, x1, y1, sc, out):
    s = sc * SS
    img = Image.new("RGB", (int((x1 - x0) * s), int((y1 - y0) * s)), BG)
    d = ImageDraw.Draw(img, "RGBA")
    X = lambda p: ((p[0] - x0) * s, (p[1] - y0) * s)
    lid = {"L1": pcbnew.F_Cu, "L4": pcbnew.In3_Cu}
    step = 1
    fg = font(11 * SS)
    for g in range(int(x0), int(x1) + 1, step):
        d.line([X((g, y0)), X((g, y1))], fill=(0, 0, 0, 40 if g % 5 == 0 else 16), width=1)
        if g % (1 if sc > 80 else 5) == 0:
            d.text(X((g + 0.05, y0 + 0.03)), str(g), fill=(90, 90, 90, 255), font=fg)
    for g in range(int(y0), int(y1) + 1, step):
        d.line([X((x0, g)), X((x1, g))], fill=(0, 0, 0, 40 if g % 5 == 0 else 16), width=1)
        if g % (1 if sc > 80 else 5) == 0:
            d.text(X((x0 + 0.05, g + 0.03)), str(g), fill=(90, 90, 90, 255), font=fg)

    for z in B.Zones():                                     # rule areas, dashed
        if not z.GetIsRuleArea():
            continue
        bb = z.GetBoundingBox()
        ax0, ay0 = Lp(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop())); ax1, ay1 = Lp(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
        for (a, c) in (((ax0, ay0), (ax1, ay0)), ((ax1, ay0), (ax1, ay1)), ((ax1, ay1), (ax0, ay1)), ((ax0, ay1), (ax0, ay0))):
            n = int(math.dist(a, c) / 0.3)
            for i in range(0, n, 2):
                p = (a[0] + (c[0] - a[0]) * i / n, a[1] + (c[1] - a[1]) * i / n)
                q = (a[0] + (c[0] - a[0]) * (i + 1) / n, a[1] + (c[1] - a[1]) * (i + 1) / n)
                d.line([X(p), X(q)], fill=(0, 130, 90, 255), width=SS)
        d.text(X((ax0 + 0.1, ay0 + 0.08)), z.GetZoneName(), fill=(0, 130, 90, 255), font=font(12 * SS))
    for fp in B.GetFootprints():
        bb = fp.GetFpPadsLocalBbox() if hasattr(fp, "GetFpPadsLocalBbox") else None
        for p in fp.Pads():
            cx, cy = Lp(p.GetPosition()); r = mm(p.GetSizeX()) / 2
            used = p.GetNetname() != ""
            if "L1" in show:
                d.ellipse([X((cx - r, cy - r)), X((cx + r, cy + r))], fill=(70, 70, 70, 255) if used else (205, 205, 200, 255))
            else:
                d.ellipse([X((cx - r, cy - r)), X((cx + r, cy + r))], outline=(190, 190, 185, 255), width=1)
            if used and sc > 80 and "L1" in show:
                d.text(X((cx, cy - r - 0.12)), p.GetNumber(), fill=(40, 40, 40, 255), font=font(9 * SS), anchor="mm")
    longest = {}
    for name in sorted(show, reverse=True):
        for t in B.GetTracks():
            if t.Type() == pcbnew.PCB_VIA_T or t.GetLayer() != lid[name]:
                continue
            col = COL[name] if t.GetNetname() != "GND" else (120, 130, 120)
            w = max(1, int(round(mm(t.GetWidth()) * s)))
            pts = arc_points(t) if t.Type() == pcbnew.PCB_ARC_T else [Lp(t.GetStart()), Lp(t.GetEnd())]
            if t.Type() == pcbnew.PCB_ARC_T:                 # stamp discs along the arc: no slivers between chords
                hw = mm(t.GetWidth()) / 2
                for p in arc_points(t, 0.008):
                    d.ellipse([X((p[0] - hw, p[1] - hw)), X((p[0] + hw, p[1] + hw))], fill=col + (255,))
                continue
            d.line([X(p) for p in pts], fill=col + (255,), width=w, joint="curve")
            for p in (pts[0], pts[-1]):                     # round ends
                d.ellipse([X((p[0] - mm(t.GetWidth()) / 2, p[1] - mm(t.GetWidth()) / 2)), X((p[0] + mm(t.GetWidth()) / 2, p[1] + mm(t.GetWidth()) / 2))], fill=col + (255,))
            a, c = pts[0], pts[1]                           # label: the longest straight piece of each net and layer inside the view
            sx, ex = max(x0 + 0.25, min(a[0], c[0])), min(x1 - 0.25, max(a[0], c[0]))
            sy, ey = max(y0 + 0.25, min(a[1], c[1])), min(y1 - 0.25, max(a[1], c[1]))
            if t.GetNetname() != "GND" and sx <= ex and sy <= ey:
                L = math.dist(a, c)
                # clip the segment to the view (axis-parallel and 45-degree segments only, so a box clip is enough)
                ts = [k / 40 for k in range(41) if x0 + 0.25 <= a[0] + (c[0] - a[0]) * k / 40 <= x1 - 0.25 and y0 + 0.25 <= a[1] + (c[1] - a[1]) * k / 40 <= y1 - 0.25]
                if ts and (ts[-1] - ts[0]) * L >= 0.3:
                    tm, vis = (ts[0] + ts[-1]) / 2, (ts[-1] - ts[0]) * L
                    mid = (a[0] + (c[0] - a[0]) * tm, a[1] + (c[1] - a[1]) * tm)
                    key2 = (t.GetNetname(), name)
                    if key2 not in longest or vis > longest[key2][0]:
                        longest[key2] = (vis, mid, t.GetNetname().replace("/FMC_", ""), col)
    for t in B.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            cx, cy = Lp(t.GetPosition()); r = mm(t.GetWidth(pcbnew.F_Cu)) / 2; h = mm(t.GetDrill()) / 2
            d.ellipse([X((cx - r, cy - r)), X((cx + r, cy + r))], fill=(20, 20, 20, 255) if t.GetNetname() != "GND" else (110, 120, 110, 255))
            d.ellipse([X((cx - h, cy - h)), X((cx + h, cy + h))], fill=(255, 255, 255, 255))
    fl = font((10 if sc < 80 else 12) * SS)
    for (_, p, text, col) in longest.values():           # the name sits ON its own track, on a white tag: no guessing which line it means
        x, y = X(p)
        bx = d.textbbox((x, y), text, font=fl, anchor="mm")
        d.rounded_rectangle([bx[0] - 3 * SS, bx[1] - 2 * SS, bx[2] + 3 * SS, bx[3] + 2 * SS], radius=3 * SS, fill=(255, 255, 255, 255), outline=col + (255,), width=SS)
        d.text((x, y), text, fill=tuple(int(c * 0.6) for c in col) + (255,), font=fl, anchor="mm")
    fk = font(13 * SS); yy = 8 * SS
    for name in show:
        d.rectangle([img.size[0] - 150 * SS, yy, img.size[0] - 130 * SS, yy + 10 * SS], fill=COL[name] + (255,))
        d.text((img.size[0] - 124 * SS, yy - 3 * SS), {"L1": "L1 (F.Cu)", "L4": "L4 (In3.Cu)"}[name], fill=(0, 0, 0, 255), font=fk); yy += 18 * SS
    img = img.resize((img.size[0] // SS, img.size[1] // SS), Image.LANCZOS)
    img.save(out)


if __name__ == "__main__":
    vdir = sys.argv[1]
    B = pcbnew.LoadBoard(os.path.join(vdir, NAME + ".kicad_pcb"))
    wide = any(z.GetIsRuleArea() and z.GetZoneName() == "BGA_SDRAM" and mm(z.GetBoundingBox().GetLeft()) - 100 > 23 for z in B.Zones())
    for key, show, x0, y0, x1, y1, sc in (VIEWS_WIDE if wide else VIEWS):
        draw(B, key, show, x0, y0, x1, y1, sc, os.path.join(vdir, key + ".png"))
        print("wrote", os.path.join(vdir, key + ".png"))
