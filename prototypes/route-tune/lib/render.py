"""PROTOTYPE (issue 21): pictures of the routed bus. Qualitative only (PROC-14): numbers come from metrics.json.

render_all(B, out dir, extra views) writes, for every view, four pictures:
    <view>_L1.png  <view>_L4.png  <view>_L6.png  <view>_all.png   (all = the three signal layers overlaid)
L1 red, L4 blue, L6 green; vias black with a white hole; package outlines solid grey, rule areas dashed
green; arcs drawn as arcs; every net's name sits on its own track (longest straight piece in the view).
The grid is local mm (board file mm - 100). Different views have different scales: do not compare sizes
between views, only between variants in the same view.

A variant may add views with VIEWS = [("name", x0, y0, x1, y1, px_per_mm), ...] in its routes.py.
"""
import math, os
import pcbnew
from PIL import Image, ImageDraw, ImageFont
from common import BODY, AREAS, LID, Lp, mm, short, arc_pts

VIEWS = [  # name, x0, y0, x1, y1, px per mm
    ("bus", 7.0, 3.5, 32.5, 24.0, 44),                      # the whole bus
    ("corridor", 18.0, 11.5, 24.0, 22.5, 120),              # the strip between the two packages
    ("sdram", 21.5, 15.5, 31.5, 23.0, 120),                 # under the SDRAM body, byte lanes
    ("south", 12.5, 16.5, 22.5, 23.0, 120),                 # below the MCU
    ("north", 8.5, 4.0, 23.0, 10.5, 90),                    # above the MCU and the top of the corridor
]
COL = {"L1": (200, 45, 40), "L4": (35, 95, 200), "L6": (25, 140, 70)}
LAYER_NAME = {"L1": "L1 (F.Cu)", "L4": "L4 (In3.Cu)", "L6": "L6 (B.Cu)"}
BG = (253, 253, 250)
SS = 2
_FONTS = {}


def font(px):
    px = int(px)
    if px not in _FONTS:
        try:
            _FONTS[px] = ImageFont.truetype("arial.ttf", px)
        except OSError:
            _FONTS[px] = ImageFont.load_default()
    return _FONTS[px]


def draw(B, show, x0, y0, x1, y1, sc, out):
    s = sc * SS
    img = Image.new("RGB", (int((x1 - x0) * s), int((y1 - y0) * s)), BG)
    d = ImageDraw.Draw(img, "RGBA")
    X = lambda p: ((p[0] - x0) * s, (p[1] - y0) * s)
    fg = font(11 * SS)
    for g in range(int(math.ceil(x0)), int(x1) + 1):
        d.line([X((g, y0)), X((g, y1))], fill=(0, 0, 0, 40 if g % 5 == 0 else 16), width=1)
        if g % (1 if sc > 80 else 5) == 0:
            d.text(X((g + 0.05, y0 + 0.03)), str(g), fill=(90, 90, 90, 255), font=fg)
    for g in range(int(math.ceil(y0)), int(y1) + 1):
        d.line([X((x0, g)), X((x1, g))], fill=(0, 0, 0, 40 if g % 5 == 0 else 16), width=1)
        if g % (1 if sc > 80 else 5) == 0:
            d.text(X((x0 + 0.05, g + 0.03)), str(g), fill=(90, 90, 90, 255), font=fg)

    for ref, (bx0, by0, bx1, by1) in BODY.items():         # package outlines: solid grey, lightly filled
        d.rectangle([X((bx0, by0)), X((bx1, by1))], fill=(120, 120, 120, 22), outline=(110, 110, 110, 255), width=SS * 2)
        d.text(X((bx0 + 0.12, by0 + 0.1)), {"U1": "MCU (U1)", "U2": "SDRAM (U2)"}[ref], fill=(90, 90, 90, 255), font=font(13 * SS))
    for name, (ax0, ay0, ax1, ay1) in AREAS.items():        # rule areas: dashed green
        for (a, c) in (((ax0, ay0), (ax1, ay0)), ((ax1, ay0), (ax1, ay1)), ((ax1, ay1), (ax0, ay1)), ((ax0, ay1), (ax0, ay0))):
            n = int(math.dist(a, c) / 0.3)
            for i in range(0, n, 2):
                p = (a[0] + (c[0] - a[0]) * i / n, a[1] + (c[1] - a[1]) * i / n)
                q = (a[0] + (c[0] - a[0]) * (i + 1) / n, a[1] + (c[1] - a[1]) * (i + 1) / n)
                d.line([X(p), X(q)], fill=(0, 130, 90, 255), width=SS)
    for fp in B.GetFootprints():
        for p in fp.Pads():
            cx, cy = Lp(p.GetPosition()); r = mm(p.GetSizeX()) / 2
            if not (x0 - 1 <= cx <= x1 + 1 and y0 - 1 <= cy <= y1 + 1):
                continue
            used = p.GetNetname() != ""
            if "L1" in show:
                d.ellipse([X((cx - r, cy - r)), X((cx + r, cy + r))], fill=(70, 70, 70, 255) if used else (205, 205, 200, 255))
            else:
                d.ellipse([X((cx - r, cy - r)), X((cx + r, cy + r))], outline=(190, 190, 185, 255), width=1)
            if used and sc > 80 and "L1" in show:
                d.text(X((cx, cy - r - 0.12)), p.GetNumber(), fill=(40, 40, 40, 255), font=font(9 * SS), anchor="mm")
    longest = {}
    img = img.convert("RGBA")
    for name in ("L6", "L4", "L1"):                         # L1 on top
        if name not in show:
            continue
        limg = Image.new("RGBA", img.size, (0, 0, 0, 0))    # one image per layer, so that overlaid layers show through each other
        d = ImageDraw.Draw(limg)
        for t in B.GetTracks():
            if t.Type() == pcbnew.PCB_VIA_T or t.GetLayer() != LID[name]:
                continue
            col = COL[name] if t.GetNetname() != "GND" else (120, 130, 120)
            w = max(1, int(round(mm(t.GetWidth()) * s)))
            hw = mm(t.GetWidth()) / 2
            if t.Type() == pcbnew.PCB_ARC_T:
                for p in arc_pts(t, 0.012):                 # stamp discs along the arc: no slivers between chords
                    d.ellipse([X((p[0] - hw, p[1] - hw)), X((p[0] + hw, p[1] + hw))], fill=col + (255,))
                continue
            pts = [Lp(t.GetStart()), Lp(t.GetEnd())]
            d.line([X(p) for p in pts], fill=col + (255,), width=w)
            for p in pts:                                   # round ends
                d.ellipse([X((p[0] - hw, p[1] - hw)), X((p[0] + hw, p[1] + hw))], fill=col + (255,))
            a, c = pts
            if t.GetNetname() == "GND":
                continue
            L = math.dist(a, c)
            ts = [k / 40 for k in range(41) if x0 + 0.25 <= a[0] + (c[0] - a[0]) * k / 40 <= x1 - 0.25 and y0 + 0.25 <= a[1] + (c[1] - a[1]) * k / 40 <= y1 - 0.25]
            if ts and (ts[-1] - ts[0]) * L >= 0.3:
                vis = (ts[-1] - ts[0]) * L
                key2 = (t.GetNetname(), name)
                if key2 not in longest or vis > longest[key2][0]:
                    longest[key2] = (vis, a, c, ts[0], ts[-1], short(t.GetNetname()), col)
        if len(show) > 1:
            limg.putalpha(limg.getchannel("A").point(lambda v: int(v * 0.72)))
        img.alpha_composite(limg)
    img = img.convert("RGB")
    d = ImageDraw.Draw(img, "RGBA")
    for t in B.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            cx, cy = Lp(t.GetPosition()); r = mm(t.GetWidth(pcbnew.F_Cu)) / 2; h = mm(t.GetDrill()) / 2
            d.ellipse([X((cx - r, cy - r)), X((cx + r, cy + r))], fill=(20, 20, 20, 255) if t.GetNetname() != "GND" else (110, 120, 110, 255))
            d.ellipse([X((cx - h, cy - h)), X((cx + h, cy + h))], fill=(255, 255, 255, 255))
    fl = font((9 if sc < 80 else 11) * SS)
    placed = []
    for key2 in sorted(longest):                            # the name sits ON its own track, on a white tag; tags do not overlap
        vis, a, c, t0, t1, text, col = longest[key2]
        best = None
        for f in (0.5, 0.35, 0.65, 0.2, 0.8, 0.1, 0.9):
            tm = t0 + (t1 - t0) * f
            x, y = X((a[0] + (c[0] - a[0]) * tm, a[1] + (c[1] - a[1]) * tm))
            bx = d.textbbox((x, y), text, font=fl, anchor="mm")
            box = (bx[0] - 3 * SS, bx[1] - 2 * SS, bx[2] + 3 * SS, bx[3] + 2 * SS)
            if not any(box[0] < q[2] and q[0] < box[2] and box[1] < q[3] and q[1] < box[3] for q in placed):
                best = (x, y, box); break
            if best is None:
                best = (x, y, box)
        x, y, box = best
        placed.append(box)
        d.rounded_rectangle(list(box), radius=3 * SS, fill=(255, 255, 255, 235), outline=col + (255,), width=SS)
        d.text((x, y), text, fill=tuple(int(v * 0.6) for v in col) + (255,), font=fl, anchor="mm")
    fk = font(13 * SS); yy = 8 * SS
    for name in show:
        d.rectangle([img.size[0] - 150 * SS, yy, img.size[0] - 130 * SS, yy + 10 * SS], fill=COL[name] + (255,))
        d.text((img.size[0] - 124 * SS, yy - 3 * SS), LAYER_NAME[name], fill=(0, 0, 0, 255), font=fk); yy += 18 * SS
    img = img.resize((img.size[0] // SS, img.size[1] // SS), Image.LANCZOS)
    img.save(out)


def render_all(B, out_dir, extra=None):
    names = []
    for name, x0, y0, x1, y1, sc in VIEWS + list(extra or []):
        for tag, show in (("L1", ("L1",)), ("L4", ("L4",)), ("L6", ("L6",)), ("all", ("L1", "L4", "L6"))):
            f = "%s_%s.png" % (name, tag)
            draw(B, show, x0, y0, x1, y1, sc, os.path.join(out_dir, f))
            names.append(f)
    return names
