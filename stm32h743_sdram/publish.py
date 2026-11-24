"""Release pictures of the H743 board with net names, in the look of the KiCad PCB editor (default dark theme).

    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\publish.py [--rest 20] [--stage all|dump|svg|png]

Reads the board only: it is copied to out/publish_work/ first, every step works on the copy. Writes stm32h743_sdram/publish/:
  layers/L1_F.Cu.svg|png ... L6_B.Cu.svg|png   one copper layer each, whole board, 100 px/mm
  layers/L1_F.Cu_silk.png, L6_B.Cu_silk_bottom_view.png   outer layers with their silkscreen (bottom mirrored, seen from below)
  closeups/L1|L3|L4|L6_mcu_sdram.png        MCU / SDRAM region (local x 26-66, y 20-52), 250 px/mm
  combined/all_layers.svg|png, signal_layers.svg|png and their *_mcu_sdram.png close-ups

How: 1. dump (KiCad python, pcbnew): tracks, arcs, vias, pads (polygons per layer), zone fills, board outline -> geom.json;
2. kicad-cli pcb export svg of the copper, silkscreen and edge layers in the editor's colour theme (layer colours are taken
from these plots, the silkscreen is inlined from them); 3. the SVGs are drawn here (copper in layer colours, zone fills
slightly transparent, vias as rings, net names as text, rules in label_* below); 4. headless Edge turns each SVG into a PNG,
in tiles of at most 4000 px that PIL puts together. Every heavy command runs alone, at low priority on four cores, with a
pause between them (--rest seconds).
"""
import argparse, json, math, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "stm32h743_sdram"
BOARD = os.path.join(HERE, NAME + ".kicad_pcb")
WORK = os.path.join(HERE, "out", "publish_work")
PUB = os.path.join(HERE, "publish")
CLI = r"D:\KiCad\bin\kicad-cli.exe"
KPY = r"D:\KiCad\bin\python.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
FONT = r"C:\Windows\Fonts\arial.ttf"
THEME = "_builtin_default"           # the editor's setting on this machine (pcbnew.json color_theme)

# board file coordinates (mm); local = board - 100
VIEW = (99.0, 99.0, 87.0, 77.0)       # whole board plus 1 mm
CLOSE = (126.0, 120.0, 40.0, 32.0)    # local x 26-66, y 20-52
PX_BOARD, PX_CLOSE = 100, 250
TILE = 4000

CU = [("F.Cu", "L1"), ("In1.Cu", "L2"), ("In2.Cu", "L3"), ("In3.Cu", "L4"), ("In4.Cu", "L5"), ("B.Cu", "L6")]
ROLE = {"L1": "top signal", "L2": "GND plane", "L3": "signal + GND pour", "L4": "signal + GND pour",
        "L5": "power plane (blocks)", "L6": "bottom signal"}
SIGNAL = ["F.Cu", "In2.Cu", "In3.Cu", "B.Cu"]

# KiCad default theme colours that the plots do not carry (builtin "KiCad Default" theme, KiCad 6-10)
BG = "#001023"           # LAYER_PCB_BACKGROUND
VIA = "#ECECEC"          # LAYER_VIA_THROUGH
HOLE_WALL = "#E3B72E"    # LAYER_VIA_HOLES / plated hole wall
NPTH = "#1AC4D2"         # LAYER_NON_PLATEDHOLES
FALLBACK = {"F.Cu": "#C83434", "In1.Cu": "#7FC87F", "In2.Cu": "#CE7D2C", "In3.Cu": "#4FCBCB", "In4.Cu": "#DB628B",
            "B.Cu": "#4D7FC4", "F.SilkS": "#F2EDA1", "B.SilkS": "#E8B2A7", "Edge.Cuts": "#D0D2CD"}
ZONE_OPACITY = 0.72
LABEL = "#FFFFFF"

# label rules (mm)
TRACK_H_FRAC, TRACK_H_MIN, TRACK_H_MAX = 0.65, 0.09, 0.6   # cap height = 65 % of the track width, within these limits
TRACK_REPEAT = 15.0       # one more name every 15 mm on a long straight run
SAME_NET_GAP = 3.0        # no two names of one net on one layer closer than this
PAD_H_MAX = 0.9
ZONE_H_MAX = 3.0
CAP = 0.716               # Arial cap height / em


def run_low(args, timeout=None):
    """One heavy command, low priority, four cores, in the foreground."""
    # one string: a list would make Python escape the quotes for cmd ("Access is denied")
    cmd = 'cmd /c start "" /low /affinity F /wait /b ' + subprocess.list2cmdline(args)
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def rest(s):
    if s:
        time.sleep(s)


# ---------------------------------------------------------------- 1. dump (KiCad python)
def dump(board, out_json):
    import pcbnew
    b = pcbnew.LoadBoard(board)
    nm = lambda v: v / 1e6
    def short(n):
        n = n or ""
        try:
            n = pcbnew.UnescapeString(n)
        except Exception:
            pass
        return n.rsplit("/", 1)[-1]
    lid = {}
    for l in b.GetEnabledLayers().CuStack():
        lid[pcbnew.LayerName(l)] = l
    def polys(ps):
        out = []
        for i in range(ps.OutlineCount()):
            o = ps.Outline(i)
            out.append([[round(nm(o.CPoint(k).x), 4), round(nm(o.CPoint(k).y), 4)] for k in range(o.PointCount())])
            for j in range(ps.HoleCount(i)):
                h = ps.Hole(i, j)
                out.append([[round(nm(h.CPoint(k).x), 4), round(nm(h.CPoint(k).y), 4)] for k in range(h.PointCount())])
        return out
    g = {"tracks": [], "arcs": [], "vias": [], "pads": [], "zones": [], "outline": [],
         # the board's own layer names: kicad-cli names its plot files after them (In1.Cu -> L2_GND)
         "names": {pcbnew.LayerName(l): b.GetLayerName(l) for l in
                   list(b.GetEnabledLayers().CuStack()) + [pcbnew.F_SilkS, pcbnew.B_SilkS, pcbnew.Edge_Cuts]}}
    for t in b.GetTracks():
        c = t.GetClass()
        if c == "PCB_VIA":
            g["vias"].append({"x": nm(t.GetPosition().x), "y": nm(t.GetPosition().y), "d": nm(t.GetWidth(t.TopLayer())),
                              "drill": nm(t.GetDrillValue()), "net": short(t.GetNetname()),
                              "flash": [n for n, l in lid.items() if t.FlashLayer(l)]})
            continue
        e = {"layer": pcbnew.LayerName(t.GetLayer()), "w": nm(t.GetWidth()), "net": short(t.GetNetname()),
             "s": [nm(t.GetStart().x), nm(t.GetStart().y)], "e": [nm(t.GetEnd().x), nm(t.GetEnd().y)]}
        if c == "PCB_ARC":
            e["m"] = [nm(t.GetMid().x), nm(t.GetMid().y)]
            g["arcs"].append(e)
        else:
            g["tracks"].append(e)
    for fp in b.GetFootprints():
        for p in fp.Pads():
            net = short(p.GetNetname())
            if net.startswith("unconnected-") or net.startswith("Net-("):
                net = "" if net.startswith("unconnected-") else net
            ang = p.GetOrientation().AsDegrees()
            e = {"ref": fp.GetReference(), "num": p.GetNumber(), "net": net, "x": nm(p.GetPosition().x),
                 "y": nm(p.GetPosition().y), "ang": ang, "side": "B" if fp.IsFlipped() else "F", "layers": {}}
            for n, l in lid.items():
                if p.IsOnLayer(l) and p.FlashLayer(l):
                    ps = pcbnew.SHAPE_POLY_SET()
                    p.TransformShapeToPolygon(ps, l, 0, 2000, pcbnew.ERROR_INSIDE)
                    e["layers"][n] = polys(ps)
            if p.HasHole() if hasattr(p, "HasHole") else p.GetDrillSize().x > 0:
                ds = p.GetDrillSize()
                e["hole"] = [nm(ds.x), nm(ds.y)]
                e["pth"] = p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH
            g["pads"].append(e)
    for z in b.Zones():
        if z.GetIsRuleArea():
            continue
        td = z.IsTeardropArea() if hasattr(z, "IsTeardropArea") else False
        for n, l in lid.items():
            if not z.IsOnLayer(l):
                continue
            fp = z.GetFilledPolysList(l)
            if fp is None or fp.OutlineCount() == 0:
                continue
            g["zones"].append({"layer": n, "net": short(z.GetNetname()), "name": z.GetZoneName(), "teardrop": bool(td),
                               "polys": polys(fp)})
    ps = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(ps, True)
    g["outline"] = polys(ps)
    json.dump(g, open(out_json, "w"))
    print("dump: %d tracks, %d arcs, %d vias, %d pads, %d zone fills" % (
        len(g["tracks"]), len(g["arcs"]), len(g["vias"]), len(g["pads"]), len(g["zones"])))


# ---------------------------------------------------------------- 2. kicad-cli plots: colours and silkscreen
def plots(board, work):
    d = os.path.join(work, "plots")
    os.makedirs(d, exist_ok=True)
    layers = ",".join([n for n, _ in CU] + ["F.SilkS", "B.SilkS", "Edge.Cuts"])
    r = run_low([CLI, "pcb", "export", "svg", "--layers", layers, "--mode-multi", "--page-size-mode", "1",
                 "--exclude-drawing-sheet", "--theme", THEME, "--drill-shape-opt", "0", "-o", d, board], timeout=900)
    if r.returncode:
        print(r.stdout.decode("utf-8", "replace")[-2000:], r.stderr.decode("utf-8", "replace")[-2000:])
        raise SystemExit("kicad-cli export svg failed")
    return d


NAMES = {}


def plot_file(d, layer):
    for tag in (NAMES.get(layer, layer).replace(".", "_"), layer.replace(".", "_"),
                layer.replace(".SilkS", "_Silkscreen")):
        f = os.path.join(d, "%s-%s.svg" % (NAME, tag))
        if os.path.exists(f):
            return f
    return None


def colours(d):
    col = dict(FALLBACK)
    for layer in FALLBACK:
        f = plot_file(d, layer)
        if not f:
            continue
        m = re.search(r"fill:(#[0-9A-Fa-f]{6})", open(f, encoding="utf-8").read()[3000:300000]) or \
            re.search(r"stroke:(#[0-9A-Fa-f]{6})", open(f, encoding="utf-8").read()[3000:300000])
        if m and m.group(1).upper() not in ("#000000", "#FFFFFF"):
            col[layer] = m.group(1).upper()
    return col


def silk_group(d, layer):
    """Inner content of kicad-cli's plot of a silkscreen layer, as a group in board mm."""
    f = plot_file(d, layer)
    s = open(f, encoding="utf-8").read()
    m = re.search(r'<svg[^>]*width="([\d.]+)mm"[^>]*viewBox="([\d.\- ]+)"', s, re.S)
    wmm = float(m.group(1))
    vb = [float(v) for v in m.group(2).split()]
    k = wmm / vb[2]
    body = s[s.index("<desc>"):]
    body = body[body.index("</desc>") + 7:body.rindex("</svg>")]
    return '<g transform="scale(%.8f) translate(%.4f %.4f)">%s</g>' % (k, -vb[0], -vb[1], body)


# ---------------------------------------------------------------- 3. SVG drawing
_font = None


def em_len(text):
    global _font
    if _font is None:
        from PIL import ImageFont
        _font = ImageFont.truetype(FONT, 1000)
    return _font.getlength(text) / 1000.0


def text_w(text, h):
    """Width in mm of text with cap height h."""
    return em_len(text) * h / CAP


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def upright(a):
    """Never upside down; vertical text reads bottom to top, as KiCad draws it."""
    a = (a + 180.0) % 360.0 - 180.0
    if a >= 89.99:
        a -= 180.0
    elif a < -90.01:
        a += 180.0
    return a


class Placer:
    """Oriented label rectangles; rejects overlaps (separating axis test) and same-net names too close."""
    def __init__(self):
        self.cell = 1.0
        self.grid = {}
        self.rects = []
        self.bynet = {}

    def _corners(self, r):
        cx, cy, hw, hh, a = r
        c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
        return [(cx + c * x - s * y, cy + s * x + c * y) for x, y in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]

    def _overlap(self, p, q):
        for poly in (p, q):
            for i in range(4):
                x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % 4]
                nx, ny = y2 - y1, x1 - x2
                a = [nx * x + ny * y for x, y in p]; b = [nx * x + ny * y for x, y in q]
                if max(a) <= min(b) or max(b) <= min(a):
                    return False
        return True

    def _cells(self, pts):
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        for i in range(int(min(xs) // self.cell), int(max(xs) // self.cell) + 1):
            for j in range(int(min(ys) // self.cell), int(max(ys) // self.cell) + 1):
                yield (i, j)

    def free(self, r, key=None, gap=0.0):
        if key and gap:
            for x, y in self.bynet.get(key, ()):
                if (x - r[0]) ** 2 + (y - r[1]) ** 2 < gap * gap:
                    return False
        pts = self._corners(r)
        seen = set()
        for c in self._cells(pts):
            for k in self.grid.get(c, ()):
                if k not in seen:
                    seen.add(k)
                    if self._overlap(pts, self.rects[k]):
                        return False
        return True

    def add(self, r, key=None):
        pts = self._corners(r)
        k = len(self.rects)
        self.rects.append(pts)
        for c in self._cells(pts):
            self.grid.setdefault(c, []).append(k)
        if key:
            self.bynet.setdefault(key, []).append((r[0], r[1]))


def f4(v):
    return ("%.4f" % v).rstrip("0").rstrip(".")


def path_d(polys):
    return "".join("M" + " ".join("%s %s" % (f4(x), f4(y)) for x, y in p) + "Z" for p in polys)


def arc_d(a):
    (sx, sy), (mx, my), (ex, ey) = a["s"], a["m"], a["e"]
    d = 2 * (sx * (my - ey) + mx * (ey - sy) + ex * (sy - my))
    if abs(d) < 1e-12:
        return "M%s %sL%s %s" % (f4(sx), f4(sy), f4(ex), f4(ey))
    ux = ((sx * sx + sy * sy) * (my - ey) + (mx * mx + my * my) * (ey - sy) + (ex * ex + ey * ey) * (sy - my)) / d
    uy = ((sx * sx + sy * sy) * (ex - mx) + (mx * mx + my * my) * (sx - ex) + (ex * ex + ey * ey) * (mx - sx)) / d
    r = math.hypot(sx - ux, sy - uy)
    cross = (mx - sx) * (ey - my) - (my - sy) * (ex - mx)
    sweep = 1 if cross > 0 else 0
    side = lambda px, py: (ex - sx) * (py - sy) - (ey - sy) * (px - sx)
    large = 1 if side(mx, my) * side(ux, uy) > 0 else 0
    return "M%s %sA%s %s 0 %d %d %s %s" % (f4(sx), f4(sy), f4(r), f4(r), large, sweep, f4(ex), f4(ey))


def pad_frame(pad, polys):
    """Long-axis angle and the pad's size along / across it, from its polygon in its own frame."""
    a = pad["ang"]
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    xs, ys = [], []
    for poly in polys:
        for x, y in poly:
            dx, dy = x - pad["x"], y - pad["y"]
            xs.append(dx * c - dy * s); ys.append(dx * s + dy * c)   # KiCad angles are counter-clockwise on screen
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    ang = -a                       # screen angle of the pad's x axis
    if abs(h - w) < 0.03 * max(w, h):
        return 0.0, w, h           # round or square: names run horizontally
    if h > w:
        ang, w, h = ang + 90.0, h, w
    return upright(ang), w, h


class Mirror:
    def __init__(self, on, cx):
        self.on, self.cx = on, cx

    def p(self, x, y):
        return (2 * self.cx - x, y) if self.on else (x, y)

    def a(self, ang):
        return upright(180.0 - ang) if self.on else upright(ang)


def text_el(x, y, ang, h, txt, op=None):
    fs = h / CAP
    o = ' opacity="%.2f"' % op if op is not None else ""
    return '<text transform="translate(%s %s) rotate(%.1f)" font-size="%s" y="%s"%s>%s</text>' % (
        f4(x), f4(y), ang, f4(fs), f4(h / 2), o, esc(txt))


def pad_labels(pads, layer, placer, mir, covered=None, check=False):
    out = []
    for p in pads:
        polys = p["layers"].get(layer)
        if not polys:
            continue
        ang, w, h = pad_frame(p, polys)
        x, y = mir.p(p["x"], p["y"])
        ang = mir.a(ang) if mir.on else ang
        if covered and covered(x, y):
            continue
        name, num = p["net"], p["num"]
        lines = []
        if name:
            hn = min(0.55 * h, 0.9 * w / max(em_len(name) / CAP, 1e-6), PAD_H_MAX)
            if num and h >= 0.7 and w >= 0.7:
                hu = min(hn * 0.6, 0.85 * w / max(em_len(num) / CAP, 1e-6))
                gap = 0.3 * hu
                if hn + gap + hu > 0.85 * h:
                    k = 0.85 * h / (hn + gap + hu); hn *= k; hu *= k; gap *= k
                tot = hu + gap + hn          # number above, name below, the pair centred on the pad
                lines = [(num, hu, -tot / 2 + hu / 2, 0.75), (name, hn, tot / 2 - hn / 2, None)]
            else:
                lines = [(name, hn, 0.0, None)]
        elif num:
            hu = min(0.4 * h, 0.85 * w / max(em_len(num) / CAP, 1e-6), PAD_H_MAX)
            lines = [(num, hu, 0.0, 0.75)]
        for txt, th, off, op in lines:
            if th < 0.025:
                continue
            c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            lx, ly = x - s * off, y + c * off
            r = (lx, ly, text_w(txt, th) / 2, th * 0.6, ang)
            if check and not placer.free(r):      # stacked view: a lower layer's pad gives way to names above
                continue
            placer.add(r)
            out.append(text_el(lx, ly, ang, th, txt, op))
    return out


def track_labels(tracks, layer, placer, mir, covered=None, tag=""):
    out = []
    segs = [t for t in tracks if t["layer"] == layer and t["net"] and not t["net"].startswith("unconnected-")]
    segs.sort(key=lambda t: -math.dist(t["s"], t["e"]))
    for t in segs:
        (sx, sy), (ex, ey) = mir.p(*t["s"]), mir.p(*t["e"])
        L = math.hypot(ex - sx, ey - sy)
        h = min(max(TRACK_H_FRAC * t["w"], TRACK_H_MIN), TRACK_H_MAX)
        tw = text_w(t["net"], h)
        if tw + 2 * h + t["w"] > L:
            continue
        ang = upright(math.degrees(math.atan2(ey - sy, ex - sx)))
        n = max(1, int(L // TRACK_REPEAT))
        for i in range(n):
            f = (i + 0.5) / n
            cx, cy = sx + (ex - sx) * f, sy + (ey - sy) * f
            if covered and covered(cx, cy):
                continue
            r = (cx, cy, tw / 2 + h * 0.3, h * 0.6, ang)
            key = tag + layer + "|" + t["net"]
            if placer.free(r, key, SAME_NET_GAP):
                placer.add(r, key)
                out.append(text_el(cx, cy, ang, h, t["net"]))
    return out


def zone_labels(zones, layer, mir, done):
    """Each island of a zone fill gets the net name once, big and faint, at its most interior point."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    out = []
    for z in zones:
        if z["layer"] != layer or z["teardrop"] or not z["net"]:
            continue
        for poly in z["polys"]:
            xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
            x0, y0, w, h = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
            if w < 1.5 or h < 1.5:
                continue
            res = min(10.0, 900.0 / max(w, h))
            # close the via and ball clearance holes first (about 1 mm): a perforated block still gets its name.
            # The margin is wider than the closing, so the image border stays empty (else erosion never ends).
            k = max(1, int(round(1.0 * res)))
            m = k + 3
            W, H = int(w * res) + 2 * m + 1, int(h * res) + 2 * m + 1
            im = Image.new("L", (W, H), 0)
            ImageDraw.Draw(im).polygon([((x - x0) * res + m, (y - y0) * res + m) for x, y in poly], fill=255)
            for _ in range(k):
                im = im.filter(ImageFilter.MaxFilter(3))
            for _ in range(k):
                im = im.filter(ImageFilter.MinFilter(3))
            last, steps = None, 0
            while im.getbbox() and steps < 4 * max(W, H):
                last = im
                im = im.filter(ImageFilter.MinFilter(5))
                steps += 2
            if last is None:
                continue
            r = steps / res
            if r < 0.6:
                continue
            a = np.argwhere(np.array(last) > 0)
            cy_, cx_ = a[len(a) // 2]
            cx, cy = x0 + (cx_ - m) / res, y0 + (cy_ - m) / res
            txt = z["net"]
            th = min(0.9 * r, ZONE_H_MAX, 1.7 * r / max(em_len(txt) / CAP, 1e-6))
            if th < 0.5:
                continue
            key = layer + "|" + txt
            if any(math.dist((cx, cy), q) < 12.0 for q in done.get(key, ())):
                continue
            done.setdefault(key, []).append((cx, cy))
            mx, my = mir.p(cx, cy)
            out.append(text_el(mx, my, 0.0, th, txt))
    return out


class Cover:
    """Raster of the copper of the layers above, to keep names only on the top-most visible copper."""
    def __init__(self, res=20.0):
        from PIL import Image, ImageDraw
        self.res = res
        self.im = Image.new("L", (int(VIEW[2] * res), int(VIEW[3] * res)), 0)
        self.dr = ImageDraw.Draw(self.im)

    def xy(self, x, y):
        return ((x - VIEW[0]) * self.res, (y - VIEW[1]) * self.res)

    def add(self, g, layer, zones=True):
        for t in g["tracks"] + g["arcs"]:
            if t["layer"] == layer:
                self.dr.line([self.xy(*t["s"]), self.xy(*t["e"])], fill=255, width=max(1, int(t["w"] * self.res)))
        for p in g["pads"]:
            for poly in p["layers"].get(layer, ()):
                self.dr.polygon([self.xy(*q) for q in poly], fill=255)
        if zones:
            for z in g["zones"]:
                if z["layer"] == layer:
                    for poly in z["polys"]:
                        self.dr.polygon([self.xy(*q) for q in poly], fill=255)

    def __call__(self, x, y):
        i, j = self.xy(x, y)
        try:
            return self.im.getpixel((int(i), int(j))) > 0
        except IndexError:
            return False


def layer_copper(g, layer, col, zones=True, zone_op=ZONE_OPACITY, op=1.0):
    s = ['<g id="%s" opacity="%.2f">' % (layer, op)]
    if zones:
        zp = [path_d(z["polys"]) for z in g["zones"] if z["layer"] == layer and not z["teardrop"]]
        if zp:
            s.append('<path fill="%s" fill-opacity="%.2f" d="%s"/>' % (col, zone_op, "".join(zp)))
    td = [path_d(z["polys"]) for z in g["zones"] if z["layer"] == layer and z["teardrop"]]
    if td:
        s.append('<path fill="%s" d="%s"/>' % (col, "".join(td)))
    byw = {}
    for t in g["tracks"]:
        if t["layer"] == layer:
            byw.setdefault(round(t["w"], 4), []).append("M%s %sL%s %s" % (f4(t["s"][0]), f4(t["s"][1]), f4(t["e"][0]), f4(t["e"][1])))
    for a in g["arcs"]:
        if a["layer"] == layer:
            byw.setdefault(round(a["w"], 4), []).append(arc_d(a))
    s.append('<g fill="none" stroke="%s" stroke-linecap="round" stroke-linejoin="round">' % col)
    for w, ds in sorted(byw.items()):
        s.append('<path stroke-width="%s" d="%s"/>' % (f4(w), "".join(ds)))
    s.append("</g>")
    pp = [path_d(p["layers"][layer]) for p in g["pads"] if layer in p["layers"]]
    if pp:
        s.append('<path fill="%s" d="%s"/>' % (col, "".join(pp)))
    s.append("</g>")
    return "".join(s)


def holes_and_vias(g, layer):
    """Vias as rings in the via colour (only a hole where the via has no pad on this layer), pad holes dark."""
    s = ['<g>']
    for v in g["vias"]:
        if layer is None or layer in v["flash"]:
            s.append('<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (f4(v["x"]), f4(v["y"]), f4(v["d"] / 2), VIA))
    for v in g["vias"]:
        s.append('<circle cx="%s" cy="%s" r="%s" fill="%s" stroke="%s" stroke-width="%s"/>' % (
            f4(v["x"]), f4(v["y"]), f4(v["drill"] / 2), BG, HOLE_WALL, f4(v["drill"] * 0.08)))
    for p in g["pads"]:
        if "hole" not in p:
            continue
        hx, hy = p["hole"]
        wall = HOLE_WALL if p.get("pth") else NPTH
        if abs(hx - hy) < 1e-6:
            s.append('<circle cx="%s" cy="%s" r="%s" fill="%s" stroke="%s" stroke-width="%s"/>' % (
                f4(p["x"]), f4(p["y"]), f4(hx / 2), BG, wall, f4(min(hx, 0.6) * 0.06)))
        else:
            w, L = min(hx, hy), max(hx, hy) - min(hx, hy)
            a = -p["ang"] + (90.0 if hy > hx else 0.0)
            c, sn = math.cos(math.radians(a)), math.sin(math.radians(a))
            x1, y1, x2, y2 = p["x"] - c * L / 2, p["y"] - sn * L / 2, p["x"] + c * L / 2, p["y"] + sn * L / 2
            d = "M%s %sL%s %s" % (f4(x1), f4(y1), f4(x2), f4(y2))
            s.append('<path d="%s" stroke="%s" stroke-width="%s" stroke-linecap="round"/>' % (d, wall, f4(w)))
            s.append('<path d="%s" stroke="%s" stroke-width="%s" stroke-linecap="round"/>' % (d, BG, f4(w * 0.88)))
    s.append("</g>")
    return "".join(s)


def outline(g, col):
    return '<path fill="none" stroke="%s" stroke-width="0.1" d="%s"/>' % (col, path_d(g["outline"]))


def svg_doc(body, title, view=VIEW, px=PX_BOARD):
    x, y, w, h = view
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
            'width="%dpx" height="%dpx" viewBox="%s %s %s %s">\n<title>%s</title>\n<rect x="%s" y="%s" width="%s" '
            'height="%s" fill="%s"/>\n%s\n</svg>\n' % (round(w * px), round(h * px), f4(x), f4(y), f4(w), f4(h), esc(title),
                                                      f4(x), f4(y), f4(w), f4(h), BG, body))


TEXT_STYLE = ('<g font-family="Arial, Helvetica, sans-serif" text-anchor="middle" fill="%s" fill-opacity="0.92" '
              'stroke="#000000" stroke-opacity="0.45" stroke-width="%s" paint-order="stroke" stroke-linejoin="round">')


def labels_group(items, stroke=0.012):
    return (TEXT_STYLE % (LABEL, f4(stroke))) + "".join(items) + "</g>"


def zone_label_group(items):
    return ('<g font-family="Arial, Helvetica, sans-serif" text-anchor="middle" fill="%s" fill-opacity="0.38">' % LABEL
            + "".join(items) + "</g>")


def build_layer(g, layer, col, silk=None, mirror=False):
    cx = VIEW[0] + VIEW[2] / 2
    mir = Mirror(mirror, cx)
    geo = [layer_copper(g, layer, col[layer]), holes_and_vias(g, layer), outline(g, col["Edge.Cuts"])]
    if silk:
        geo.append(silk)
    tr = ' transform="matrix(-1 0 0 1 %s 0)"' % f4(2 * cx) if mirror else ""
    pl = Placer()
    zl = zone_labels(g["zones"], layer, mir, {})
    lab = pad_labels(g["pads"], layer, pl, mir) + track_labels(g["tracks"], layer, pl, mir)
    # zone names faint over the copper, vias and silkscreen (a block under a BGA is full of vias), under the other names
    body = "<g%s>%s</g>\n%s\n%s" % (tr, "".join(geo), zone_label_group(zl), labels_group(lab))
    return body, len(lab), len(zl)


def build_combined(g, col, layers, zones):
    """Layers stacked as the editor draws them with every copper layer on and F.Cu active: back first, front on top."""
    mir = Mirror(False, 0)
    order = [n for n, _ in CU if n in layers][::-1]
    op = 1.0 if zones else 0.85
    parts = [layer_copper(g, n, col[n], zones=zones, zone_op=0.8, op=op) for n in order]
    parts.append(holes_and_vias(g, None))
    parts.append(outline(g, col["Edge.Cuts"]))
    pl, cov, lab, zl = Placer(), Cover(), [], []
    for n in order[::-1]:                       # front first: its names win
        lab += pad_labels(g["pads"], n, pl, mir, cov, check=n != order[-1])
        lab += track_labels(g["tracks"], n, pl, mir, cov)
        if zones and n == order[-1]:
            zl += zone_labels(g["zones"], n, mir, {})
        cov.add(g, n, zones=zones)
    body = "".join(parts) + zone_label_group(zl) + labels_group(lab)
    return body, len(lab)


# ---------------------------------------------------------------- 4. PNG through headless Edge, in tiles
def to_png(svg, png, view, px, work, pause):
    from PIL import Image
    x0, y0, w, h = view
    W, H = round(w * px), round(h * px)
    # a copy of the SVG drawn at this view and size (the close-ups only change the viewBox)
    src = open(svg, encoding="utf-8").read()
    src = re.sub(r'width="\d+px" height="\d+px" viewBox="[^"]+"',
                 'width="%dpx" height="%dpx" viewBox="%s %s %s %s"' % (W, H, f4(x0), f4(y0), f4(w), f4(h)), src, count=1)
    tmp_svg = os.path.join(work, "_view.svg")
    open(tmp_svg, "w", encoding="utf-8").write(src)
    out = Image.new("RGB", (W, H))
    prof = os.path.join(work, "edge_profile")
    nx, ny = math.ceil(W / TILE), math.ceil(H / TILE)
    for j in range(ny):
        for i in range(nx):
            tw, th = min(TILE, W - i * TILE), min(TILE, H - j * TILE)
            html = os.path.join(work, "_tile.html")
            open(html, "w", encoding="utf-8").write(
                '<html><body style="margin:0;background:%s;overflow:hidden"><div style="width:%dpx;height:%dpx;'
                'overflow:hidden;position:relative"><img src="_view.svg" style="position:absolute;left:%dpx;top:%dpx;'
                'width:%dpx;height:%dpx"></div></body></html>' % (BG, tw, th, -i * TILE, -j * TILE, W, H))
            shot = os.path.join(work, "_tile.png")
            if os.path.exists(shot):
                os.remove(shot)
            run_low([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                     "--user-data-dir=" + prof, "--window-size=%d,%d" % (tw, th), "--virtual-time-budget=20000",
                     "--screenshot=" + shot, "file:///" + html.replace("\\", "/")], timeout=600)
            t = Image.open(shot).convert("RGB")
            if t.size != (tw, th):
                t = t.crop((0, 0, tw, th))
            out.paste(t, (i * TILE, j * TILE))
            t.close()
            rest(min(pause, 3))
    out.save(png, optimize=False, compress_level=6)
    os.remove(tmp_svg)
    rest(pause)
    return W, H


# ---------------------------------------------------------------- driver
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all", choices=["all", "dump", "svg", "png"])
    ap.add_argument("--rest", type=float, default=20.0, help="pause in seconds between heavy commands")
    ap.add_argument("--only", default="", help="comma list of outputs to make (layer tags, silk, close, combined)")
    a = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    board = os.path.join(WORK, NAME + ".kicad_pcb")
    gj = os.path.join(WORK, "geom.json")
    if a.stage in ("all", "dump"):
        for ext in (".kicad_pcb", ".kicad_pro", ".kicad_prl", ".kicad_dru"):
            if os.path.exists(os.path.join(HERE, NAME + ext)):
                shutil.copyfile(os.path.join(HERE, NAME + ext), os.path.join(WORK, NAME + ext))
        r = run_low([KPY, os.path.abspath(__file__), "--dump-to", gj, board], timeout=900)
        print(r.stdout.decode("utf-8", "replace").strip().splitlines()[-1:])
        if r.returncode or not os.path.exists(gj):
            print(r.stderr.decode("utf-8", "replace")[-3000:])
            raise SystemExit("dump failed")
        rest(a.rest)
        plots(board, WORK)
        rest(a.rest)
        if a.stage == "dump":
            return
    g = json.load(open(gj))
    NAMES.update(g["names"])
    pd = os.path.join(WORK, "plots")
    col = colours(pd)
    only = set(x for x in a.only.split(",") if x)
    want = lambda k: not only or k in only
    for sub in ("layers", "closeups", "combined"):
        os.makedirs(os.path.join(PUB, sub), exist_ok=True)
    jobs = []      # (svg path, png path, view, px)
    for n, tag in CU:
        stem = "%s_%s" % (tag, n)
        if not want(tag):
            continue
        body, nl, nz = build_layer(g, n, col)
        title = "%s (%s), %s" % (tag, n, ROLE[tag])
        f = os.path.join(PUB, "layers", stem + ".svg")
        if a.stage != "png":
            open(f, "w", encoding="utf-8").write(svg_doc(body, title))
            print("%s: %d names, %d zone names" % (stem, nl, nz))
        jobs.append((f, os.path.join(PUB, "layers", stem + ".png"), VIEW, PX_BOARD))
        if n in SIGNAL:
            jobs.append((f, os.path.join(PUB, "closeups", tag + "_mcu_sdram.png"), CLOSE, PX_CLOSE))
    if want("silk"):
        for n, tag, silk, mirror, stem in (("F.Cu", "L1", "F.SilkS", False, "L1_F.Cu_silk"),
                                          ("B.Cu", "L6", "B.SilkS", True, "L6_B.Cu_silk_bottom_view")):
            sg = '<g fill="%s" stroke="%s">%s</g>' % (col[silk], col[silk], silk_group(pd, silk))
            body, nl, nz = build_layer(g, n, col, silk=sg, mirror=mirror)
            f = os.path.join(WORK, stem + ".svg")
            if a.stage != "png":
                open(f, "w", encoding="utf-8").write(svg_doc(body, stem))
            jobs.append((f, os.path.join(PUB, "layers", stem + ".png"), VIEW, PX_BOARD))
    for stem, layers, zones in (("all_layers", [n for n, _ in CU], True), ("signal_layers", SIGNAL, False)):
        if want("combined") or want(stem):
            f = os.path.join(PUB, "combined", stem + ".svg")
            if a.stage != "png":
                body, nl = build_combined(g, col, layers, zones)
                open(f, "w", encoding="utf-8").write(svg_doc(body, stem))
                print("%s: %d names" % (stem, nl))
            jobs.append((f, os.path.join(PUB, "combined", stem + ".png"), VIEW, PX_BOARD))
            jobs.append((f, os.path.join(PUB, "combined", stem + "_mcu_sdram.png"), CLOSE, PX_CLOSE))
    if a.stage == "svg":
        return
    for svg, png, view, px in jobs:
        t0 = time.time()
        W, H = to_png(svg, png, view, px, WORK, a.rest)
        print("%s %dx%d %.0f s" % (os.path.relpath(png, HERE), W, H, time.time() - t0))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--dump-to":
        dump(sys.argv[3], sys.argv[2])
    else:
        main()
