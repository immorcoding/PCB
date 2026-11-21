"""Pictures of a routing state without opening KiCad. Qualitative only (PROC-14): numbers come from metrics.json.

render(board, out_dir, views, nets) writes for every view one picture per copper layer that carries tracks
in the view, plus <view>_all.png with those layers overlaid (translucent, top layer on top).
A view is (name, x0, y0, x1, y1, px_per_mm) in local mm; the grid is local mm. Tracks of `nets` (the group
just built) are drawn in the layer colour and named on their longest straight piece; other tracks are grey.
Vias are black with a white hole, pads grey (darker when they belong to the group), rule areas dashed green,
the board outline dark. Different views have different scales.
"""
import math, os

COLS = [(200, 45, 40), (150, 110, 20), (140, 60, 160), (35, 95, 200), (20, 140, 150), (25, 140, 70)]
BG = (253, 253, 250)
SS = 2
_FONTS = {}


def font(px):
    from PIL import ImageFont
    px = int(px)
    if px not in _FONTS:
        try:
            _FONTS[px] = ImageFont.truetype("arial.ttf", px)
        except OSError:
            _FONTS[px] = ImageFont.load_default()
    return _FONTS[px]


def colour(board, layer):
    k = board.layers.index(layer)
    return COLS[-1] if k == len(board.layers) - 1 else COLS[min(k, len(COLS) - 2)]


def draw(board, show, view, out, nets):
    from PIL import Image, ImageDraw
    name, x0, y0, x1, y1, sc = view
    s = sc * SS
    img = Image.new("RGB", (int((x1 - x0) * s), int((y1 - y0) * s)), BG)
    d = ImageDraw.Draw(img, "RGBA")
    X = lambda p: ((p[0] - x0) * s, (p[1] - y0) * s)
    vis = lambda p, m=1.0: x0 - m <= p[0] <= x1 + m and y0 - m <= p[1] <= y1 + m
    fg = font(11 * SS)
    every = 1 if sc > 60 else 5
    for g in range(int(math.ceil(x0)), int(x1) + 1):
        d.line([X((g, y0)), X((g, y1))], fill=(0, 0, 0, 40 if g % 5 == 0 else 16), width=1)
        if g % every == 0:
            d.text(X((g + 0.05, y0 + 0.03)), str(g), fill=(90, 90, 90, 255), font=fg)
    for g in range(int(math.ceil(y0)), int(y1) + 1):
        d.line([X((x0, g)), X((x1, g))], fill=(0, 0, 0, 40 if g % 5 == 0 else 16), width=1)
        if g % every == 0:
            d.text(X((x0 + 0.05, g + 0.03)), str(g), fill=(90, 90, 90, 255), font=fg)
    for a, c in board.edges:
        if vis(a, 50) or vis(c, 50):
            d.line([X(a), X(c)], fill=(60, 60, 60, 255), width=SS * 2)
    for an, a in board.areas.items():                       # rule areas: dashed green
        R = a["rect"]
        c = [(R[0], R[1]), (R[2], R[1]), (R[2], R[3]), (R[0], R[3])]
        for k in range(4):
            p, q = c[k], c[(k + 1) % 4]
            n = max(2, int(math.dist(p, q) / 0.3))
            for i in range(0, n, 2):
                d.line([X((p[0] + (q[0] - p[0]) * i / n, p[1] + (q[1] - p[1]) * i / n)), X((p[0] + (q[0] - p[0]) * (i + 1) / n, p[1] + (q[1] - p[1]) * (i + 1) / n))],
                       fill=(0, 130, 90, 255), width=SS)
    for p in board.pads.values():
        if not vis(p.pos):
            continue
        on = p.layers is None or any(l in p.layers for l in show)
        fill = ((70, 70, 70, 255) if p.net in nets else (190, 190, 185, 255)) if on else None
        if p.shape == "circle":
            box = [X((p.pos[0] - p.r, p.pos[1] - p.r)), X((p.pos[0] + p.r, p.pos[1] + p.r))]
            d.ellipse(box, fill=fill, outline=(190, 190, 185, 255))
        else:
            d.polygon([X(q) for q in p.poly], fill=fill, outline=(190, 190, 185, 255))
        if on and p.net in nets and sc > 80:
            d.text(X((p.pos[0], p.pos[1] - p.r - 0.12)), p.num, fill=(40, 40, 40, 255), font=font(9 * SS), anchor="mm")
    longest = {}
    img = img.convert("RGBA")
    for lay in reversed(show):                              # the first layer of `show` ends on top
        limg = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(limg)
        for n, l, a, c, w, _ in board.tracks:
            if l != lay or not (vis(a) or vis(c) or (min(a[0], c[0]) <= x1 and max(a[0], c[0]) >= x0 and min(a[1], c[1]) <= y1 and max(a[1], c[1]) >= y0)):
                continue
            col = colour(board, lay) if n in nets else (140, 140, 140)
            hw = w / 2
            d.line([X(a), X(c)], fill=col + (255,), width=max(1, int(round(w * s))))
            for p in (a, c):
                d.ellipse([X((p[0] - hw, p[1] - hw)), X((p[0] + hw, p[1] + hw))], fill=col + (255,))
            if n in nets:
                L = math.dist(a, c)
                ts = [k / 40 for k in range(41) if x0 + 0.25 <= a[0] + (c[0] - a[0]) * k / 40 <= x1 - 0.25 and y0 + 0.25 <= a[1] + (c[1] - a[1]) * k / 40 <= y1 - 0.25]
                if ts and (ts[-1] - ts[0]) * L >= 0.3 and ((n, lay) not in longest or (ts[-1] - ts[0]) * L > longest[(n, lay)][0]):
                    longest[(n, lay)] = ((ts[-1] - ts[0]) * L, a, c, ts[0], ts[-1], col)
        if len(show) > 1:
            limg.putalpha(limg.getchannel("A").point(lambda v: int(v * 0.72)))
        img.alpha_composite(limg)
    img = img.convert("RGB")
    d = ImageDraw.Draw(img, "RGBA")
    for n, p, dia, drill in board.vias:
        if vis(p):
            r, h = dia / 2, drill / 2
            d.ellipse([X((p[0] - r, p[1] - r)), X((p[0] + r, p[1] + r))], fill=(20, 20, 20, 255) if n in nets else (120, 130, 120, 255))
            d.ellipse([X((p[0] - h, p[1] - h)), X((p[0] + h, p[1] + h))], fill=(255, 255, 255, 255))
    fl = font((9 if sc < 80 else 11) * SS)
    placed = []
    common = os.path.commonprefix(sorted(nets)) if len(nets) > 1 else ""
    for key in sorted(longest):                             # the name sits on its own track, on a white tag
        _, a, c, t0, t1, col = longest[key]
        text = key[0][len(common):] or key[0]
        best = None
        for f in (0.5, 0.35, 0.65, 0.2, 0.8, 0.1, 0.9):
            tm = t0 + (t1 - t0) * f
            x, y = X((a[0] + (c[0] - a[0]) * tm, a[1] + (c[1] - a[1]) * tm))
            bx = d.textbbox((x, y), text, font=fl, anchor="mm")
            box = (bx[0] - 3 * SS, bx[1] - 2 * SS, bx[2] + 3 * SS, bx[3] + 2 * SS)
            if not any(box[0] < q[2] and q[0] < box[2] and box[1] < q[3] and q[1] < box[3] for q in placed):
                best = (x, y, box); break
            best = best or (x, y, box)
        x, y, box = best
        placed.append(box)
        d.rounded_rectangle(list(box), radius=3 * SS, fill=(255, 255, 255, 235), outline=col + (255,), width=SS)
        d.text((x, y), text, fill=tuple(int(v * 0.6) for v in col) + (255,), font=fl, anchor="mm")
    fk = font(13 * SS); yy = 8 * SS
    for lay in show:
        d.rectangle([img.size[0] - 150 * SS, yy, img.size[0] - 130 * SS, yy + 10 * SS], fill=colour(board, lay) + (255,))
        d.text((img.size[0] - 124 * SS, yy - 3 * SS), "%s (%s)" % (lay, board.cu[lay]), fill=(0, 0, 0, 255), font=fk); yy += 18 * SS
    if common:
        d.text((img.size[0] - 150 * SS, yy), "names without %s" % common, fill=(90, 90, 90, 255), font=fg)
    img = img.resize((img.size[0] // SS, img.size[1] // SS), Image.LANCZOS)
    img.save(out)


def default_view(board, nets, name="group"):
    pts = [p for n, l, a, c, w, _ in board.tracks if n in nets for p in (a, c)] + [p.pos for p in board.pads.values() if p.net in nets]
    if not pts:
        return None
    x0, y0, x1, y1 = min(p[0] for p in pts) - 1.5, min(p[1] for p in pts) - 1.5, max(p[0] for p in pts) + 1.5, max(p[1] for p in pts) + 1.5
    return (name, x0, y0, x1, y1, max(20, min(120, int(2400 / max(x1 - x0, y1 - y0)))))


def render(board, out_dir, views, nets):
    """-> [file names]. board = a Board snapshot of the file to show (re-read after writing)."""
    nets, names = set(nets), []
    views = list(views or [])
    if not views and default_view(board, nets):
        views = [default_view(board, nets)]
    for view in views:
        name, x0, y0, x1, y1, sc = view
        used = [l for l in board.layers if any(t[1] == l and t[0] in nets for t in board.tracks)] or board.layers[:1]
        for tag, show in [(l, (l,)) for l in used] + [("all", tuple(used))]:
            f = "%s_%s.png" % (name, tag)
            draw(board, show, view, os.path.join(out_dir, f), nets)
            names.append(f)
    return names
