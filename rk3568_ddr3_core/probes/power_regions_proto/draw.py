"""PROTOTYPE (throwaway, issue 52): power-copper region sketches for the RK3568 + 2 x DDR3 verification board.

    python draw.py        -> out/<variant>.sketch (cu_sketch text), out/<variant>_board.png, out/<variant>_core.png,
                             out/metrics.json, power_regions.html

Question it answers: how do the SoC's supplies split into blocks on L3, which board edge does each block reach,
where do the vias and the back-side capacitors go. Nothing here is checked by KiCad; the numbers are a raster
model (0.025 mm) of the drawn blocks minus the antipads of every foreign via.
"""
import collections, html, json, math
from pathlib import Path

import numpy as np
from scipy import ndimage
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path as MPath
from matplotlib.patches import Polygon, Circle, Rectangle

import model as M
import rails as R
from variants import VARIANTS

M.load_rails()
HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

P = M.PITCH
GAP = 0.5                 # PWR-8 gap between blocks of different nets on the plane
G = 0.025                 # raster
BX0, BY0, BX1, BY1 = M.BOARD
EXT = 4.0                 # blocks are continued this far beyond a board edge for the raster (the "source" side)
BIG = list(R.BIG)
COL = {"VCC_DDR": "#d9822b", "VDD_CPU": "#d33f49", "VDD_LOGIC": "#3a7bd5", "VDD_GPU": "#2e9e6b", "VDD_NPU": "#8e5bd0",
       "VDDA_0V9": "#b0a030", "VCCA_1V8": "#3aa8b8", "VCC_3V3": "#c05a9c", "VCC_1V8": "#6b8e23", "GND": "#888888"}


def col(net):
    return COL.get(net, "#444444")


# ---- geometry ----------------------------------------------------------------------------------------------------
def resolve(verts, ext=0.0):
    e = {"W": BX0 - ext, "E": BX1 + ext, "N": BY0 - ext, "S": BY1 + ext}
    return [((e[x] if isinstance(x, str) else x * P), (e[y] if isinstance(y, str) else y * P)) for x, y in verts]


def on_edge(a, b, ext):
    for i, lim in ((0, BX0 - ext), (0, BX1 + ext), (1, BY0 - ext), (1, BY1 + ext)):
        if abs(a[i] - lim) < 1e-9 and abs(b[i] - lim) < 1e-9:
            return True
    return False


def inset(pts, ext=0.0, d=GAP / 2):
    """Pull every edge that is not on the board outline inwards: axis edges by d, 45 degree edges by 0.18 in x
    and in y (0.2546 across), so every vertex stays on a 0.01 mm grid and every edge on 0 / 45 / 90."""
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    s = 1 if area > 0 else -1
    lines = []
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        assert abs(dx) < 1e-9 or abs(dy) < 1e-9 or abs(abs(dx) - abs(dy)) < 1e-9, ("edge not on 0/45/90", a, b)
        ux, uy = (dx > 1e-9) - (dx < -1e-9), (dy > 1e-9) - (dy < -1e-9)
        nx, ny = -uy * s, ux * s
        k = 0.0 if on_edge(a, b, ext) else (d if (ux == 0 or uy == 0) else 0.18)
        lines.append(((a[0] + nx * k, a[1] + ny * k), (ux, uy)))
    out = []
    for i in range(n):
        (p, u), (q, v) = lines[i - 1], lines[i]
        den = u[0] * v[1] - u[1] * v[0]
        t = ((q[0] - p[0]) * v[1] - (q[1] - p[1]) * v[0]) / den
        out.append((round(p[0] + u[0] * t, 3), round(p[1] + u[1] * t, 3)))
    return out


def seg_dist(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / (ax * ax + ay * ay)))
    return math.hypot(p[0] - a[0] - t * ax, p[1] - a[1] - t * ay)


def edge_dist(p, poly):
    return min(seg_dist(p, poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))


def octd(a, b):
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)


KEEP_LANES = True
LANE_LINES = {-5, -4, -2, -1, 1, 2, 4, 5}      # via-site lines inside the lanes centred on k = +-1.5 and +-4.5


# ---- vias: supply balls of the big rails move to a ball-gap site inside their own block ----------------------------
def place_vias(blocks):
    """-> (vias [(x, y, hole, pad, net, what)], no_site [ball]) ; blocks {net: polygon} (drawn, inset)."""
    vias = M.all_vias()
    occ = {(round(v[0] / P), round(v[1] / P)): i for i, v in enumerate(vias) if v[5].startswith("soc:")}
    balls = {b: (x, y) for b, x, y, k, net in M.soc_balls()}
    moved = 0
    if KEEP_LANES:
        # The package leaves ball rows K, N, T, W and columns 10, 13, 16, 19 empty through rings 3-7: four lanes a
        # side for plane copper. A via of a ball next to a lane goes to the ball's far side, off the lane.
        for i, v in enumerate(vias):
            if not v[5].startswith("soc:") or M.ring(v[5][4:]) > 7:
                continue
            bx, by = balls[v[5][4:]]
            ax_ = 1 if abs(bx) > abs(by) else 0            # east / west flank: lanes run in x, so look at the y line
            line = round(v[ax_] / P)
            if line not in LANE_LINES:
                continue
            new = list(v[:2]); new[ax_] = 2 * (by if ax_ else bx) - v[ax_]
            cands = [tuple(new)]
            alt = list(new); alt[1 - ax_] = 2 * (bx if ax_ else by) - v[1 - ax_]
            cands.append(tuple(alt))
            for c in cands:
                key = (round(c[0] / P), round(c[1] / P))
                if key not in occ:
                    del occ[(round(v[0] / P), round(v[1] / P))]
                    occ[key] = i
                    vias[i] = (round(c[0], 4), round(c[1], 4)) + v[2:]
                    moved += 1
                    break
    place_vias.moved = moved
    paths = {n: MPath(poly) for n, poly in blocks.items()}
    no_site = []
    for i, v in enumerate(vias):
        net, what = v[4], v[5]
        if not what.startswith("soc:") or net not in blocks or net not in BIG:
            continue
        bx, by = balls[what[4:]]
        def ok(s):
            return paths[net].contains_point(s) and edge_dist(s, blocks[net]) >= M.VIA_SUPPLY[0] / 2 + 0.15
        if ok((v[0], v[1])):
            continue
        cands = [(bx + sx * P / 2, by + sy * P / 2) for sx in (-1, 1) for sy in (-1, 1)]
        cands = [c for c in cands if ok(c) and (round(c[0] / P), round(c[1] / P)) not in occ]
        if not cands:
            no_site.append(what[4:])
            continue
        c = cands[0]
        del occ[(round(v[0] / P), round(v[1] / P))]
        occ[(round(c[0] / P), round(c[1] / P))] = i
        vias[i] = (round(c[0], 4), round(c[1], 4)) + v[2:]
    return vias, no_site


# ---- raster: is every via of a block joined to the block's board edge, and through how wide a channel ---------------
HALF = [0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5]


def analyse_block(net, verts, vias):
    ext = inset(resolve(verts, EXT), EXT)          # continued beyond the board edge: that part is the source
    xs, ys = [p[0] for p in ext], [p[1] for p in ext]
    x0, y0 = min(xs) - 0.5, min(ys) - 0.5
    nx, ny = int((max(xs) - x0 + 0.5) / G) + 1, int((max(ys) - y0 + 0.5) / G) + 1
    gx, gy = x0 + (np.arange(nx) + 0.5) * G, y0 + (np.arange(ny) + 0.5) * G
    X, Y = np.meshgrid(gx, gy)
    mask = MPath(ext).contains_points(np.column_stack([X.ravel(), Y.ravel()])).reshape(ny, nx)
    own = []
    for x, y, hole, pad, vnet, what in vias:
        if not (x0 < x < x0 + nx * G and y0 < y < y0 + ny * G):
            continue
        if vnet == net:
            if mask[int((y - y0) / G), int((x - x0) / G)]:
                own.append((x, y, what))
            continue
        r = hole / 2 + M.HOLE_CU
        i0, i1 = max(0, int((y - r - y0) / G)), min(ny, int((y + r - y0) / G) + 2)
        j0, j1 = max(0, int((x - r - x0) / G)), min(nx, int((x + r - x0) / G) + 2)
        sub = (X[i0:i1, j0:j1] - x) ** 2 + (Y[i0:i1, j0:j1] - y) ** 2 <= r * r
        mask[i0:i1, j0:j1] &= ~sub
    outside = (X < BX0) | (X > BX1) | (Y < BY0) | (Y > BY1)
    d = ndimage.distance_transform_edt(mask) * G
    best = {w: 0.0 for _, _, w in own}
    for h in HALF:
        lab, _ = ndimage.label(d >= h)
        src = set(np.unique(lab[outside & (d >= h)])) - {0}
        if not src:
            break
        for x, y, w in own:
            r = max(0.3, h + 0.1)
            i0, i1 = max(0, int((y - r - y0) / G)), min(ny, int((y + r - y0) / G) + 1)
            j0, j1 = max(0, int((x - r - x0) / G)), min(nx, int((x + r - x0) / G) + 1)
            if src & set(np.unique(lab[i0:i1, j0:j1])):
                best[w] = 2 * h
    soc = sorted(v for w, v in best.items() if w.startswith("soc:"))
    ddr = sorted(v for w, v in best.items() if w.startswith("ddr"))
    drawn = inset(resolve(verts))
    edge = collections.defaultdict(float)
    for i in range(len(drawn)):
        a, b = drawn[i], drawn[(i + 1) % len(drawn)]
        for name, k, lim in (("西", 0, BX0), ("东", 0, BX1), ("北", 1, BY0), ("南", 1, BY1)):
            if abs(a[k] - lim) < 1e-9 and abs(b[k] - lim) < 1e-9:
                edge[name] += math.dist(a, b)
    return {"net": net, "area": round(float((mask & ~outside).sum()) * G * G, 1), "edge": {k: round(v, 1) for k, v in edge.items()},
            "soc_vias": len(soc), "soc_joined": sum(v >= M.MINW for v in soc), "soc_min": soc[0] if soc else None,
            "soc_med": soc[len(soc) // 2] if soc else None,
            "ddr_vias": len(ddr), "ddr_joined": sum(v >= M.MINW for v in ddr), "ddr_min": ddr[0] if ddr else None,
            "cut": sorted(w for w, v in best.items() if v < M.MINW)}


WIN = 11.6                 # window of the fine pass: the SoC rule area and a bit
GF = 0.0125
RULESETS = [("big", "过孔 0.4 / 0.2，铜最窄 0.2", None, 0.2), ("small", "区内过孔 0.30 / 0.15，铜最窄 0.1", 0.15, 0.1)]


def soc_conn(net, verts, vias, hole, minw):
    """Fine raster of the SoC area only. Which SoC vias of `net` are joined on L3, through copper at least `minw`
    wide, to the part of the block outside the SoC rule area. hole: drill of every via inside the ball field
    (None = as listed). -> {ball: True / False}"""
    poly = inset(resolve(verts, EXT), EXT)
    n = int(2 * WIN / GF)
    c = -WIN + (np.arange(n) + 0.5) * GF
    X, Y = np.meshgrid(c, c)
    mask = MPath(poly).contains_points(np.column_stack([X.ravel(), Y.ravel()])).reshape(n, n)
    own = []
    for x, y, h, pad, vnet, what in vias:
        if abs(x) > WIN or abs(y) > WIN:
            continue
        if vnet == net:
            own.append((x, y, what))
            continue
        if hole is not None and what.startswith("soc:"):
            h = hole
        r = h / 2 + M.HOLE_CU
        i0, i1 = max(0, int((y - r + WIN) / GF)), min(n, int((y + r + WIN) / GF) + 2)
        j0, j1 = max(0, int((x - r + WIN) / GF)), min(n, int((x + r + WIN) / GF) + 2)
        mask[i0:i1, j0:j1] &= ~((X[i0:i1, j0:j1] - x) ** 2 + (Y[i0:i1, j0:j1] - y) ** 2 <= r * r)
    d = ndimage.distance_transform_edt(mask) * GF
    lab, _ = ndimage.label(d >= minw / 2 - GF)            # one cell of slack for the raster
    rule = M.SOC_HALF + M.MARGIN
    src = set(np.unique(lab[(np.abs(X) > rule) | (np.abs(Y) > rule)])) - {0}
    out = {}
    for x, y, what in own:
        if not what.startswith("soc:"):
            continue
        r = 0.3
        i0, i1 = max(0, int((y - r + WIN) / GF)), min(n, int((y + r + WIN) / GF) + 1)
        j0, j1 = max(0, int((x - r + WIN) / GF)), min(n, int((x + r + WIN) / GF) + 1)
        out[what[4:]] = bool(src & set(np.unique(lab[i0:i1, j0:j1])))
    return out


def tie_groups(net):
    """Balls of one rail that are neighbours in a row or a column: the top-layer ties ("井") join them."""
    bs = {b: M.rc(b) for b, x, y, k, n in M.soc_balls() if k == "pwr" and n == net}
    par = {b: b for b in bs}
    def find(a):
        while par[a] != a:
            a = par[a]
        return a
    for a in bs:
        for c in bs:
            if abs(bs[a][0] - bs[c][0]) + abs(bs[a][1] - bs[c][1]) == 1:
                par[find(a)] = find(c)
    g = collections.defaultdict(list)
    for b in bs:
        g[find(b)].append(b)
    return list(g.values())


def core_report(net, verts, vias):
    out = {"groups": len(tie_groups(net)), "balls": sum(len(g) for g in tie_groups(net))}
    for key, label, hole, minw in RULESETS:
        j = soc_conn(net, verts, vias, hole, minw)
        fed = [b for g in tie_groups(net) if any(j.get(b) for b in g) for b in g]
        out[key] = {"joined": sum(j.values()), "fed": len(fed),
                    "unfed": sorted(b for g in tie_groups(net) for b in g if b not in fed)}
    return out


# ---- back-side capacitors: a pad over a supply via and a pad over a ground via (the approved via-in-pad case) -------
CAP_TARGET = {"VDD_CPU": 3, "VDD_LOGIC": 4, "VDD_GPU": 3, "VDD_NPU": 2, "VCC_DDR": 5}   # "back of the chip" parts of the reference schematic


def place_caps(vias):
    soc = [v for v in vias if v[5].startswith("soc:")]
    gnd = [v for v in soc if v[4] == "GND"]
    by_net = collections.defaultdict(list)
    for v in soc:
        if not v[4].startswith("sig:") and v[4] != "GND":
            by_net[v[4]].append(v)
    used, caps, short = set(), [], {}
    order = BIG + sorted(n for n in by_net if n not in BIG)
    for net in order:
        want = CAP_TARGET.get(net, len(by_net[net]))
        got = 0
        cand = []
        for v in by_net[net]:
            for g in gnd:
                dd = math.dist(v[:2], g[:2])
                if abs(dd - P) < 0.02 or abs(dd - P * math.sqrt(2)) < 0.02:
                    cand.append((0 if abs(dd - P * math.sqrt(2)) < 0.02 else 1, v, g))
        cand.sort(key=lambda c: (c[0], c[1][5], c[2][5]))
        seen = set()
        for pas in (0, 1):                      # first one capacitor per ball, then fill up to the count
            for kind, v, g in cand:
                if got >= want:
                    break
                if (pas == 0 and v[5] in seen) or v[5] in used or g[5] in used:
                    continue
                mid = ((v[0] + g[0]) / 2, (v[1] + g[1]) / 2)
                if any(math.dist(mid, c["mid"]) < 1.05 for c in caps):
                    continue
                used.update((v[5], g[5])); seen.add(v[5]); got += 1
                caps.append({"net": net, "mid": mid, "a": v[:2], "b": g[:2], "size": "0402" if kind == 0 else "0201"})
        short[net] = (got, want)
    return caps, short


# ---- small rails: from the ball's via on the back side to where the rail is picked up ------------------------------
RULE = M.SOC_HALF + M.MARGIN


def small_exits(vias, strips):
    """-> [(net, ball, via, target, length, side)] ; strips {net: polygon} (variant 2), else to the edge of the
    SoC rule area on a side that is free (east, south, west below chip A, north right of chip B)."""
    a_end = max(p[1] for p in M.chip_poly("A", M.MARGIN))
    b_end = max(p[0] for p in M.chip_poly("B", M.MARGIN))
    out = []
    for x, y, hole, pad, net, what in vias:
        if not what.startswith("soc:") or net in BIG or net == "GND" or net.startswith("sig:"):
            continue
        cands = [((RULE, y), "东"), ((x, RULE), "南")]
        cands.append(((-RULE, max(y, a_end + 0.5)), "西"))
        cands.append(((max(x, b_end + 0.5), -RULE), "北"))
        if net in strips:
            xs, ys = [p[0] for p in strips[net]], [p[1] for p in strips[net]]
            t = (min(max(x, min(xs) + 0.3), max(xs) - 0.3), min(max(y, min(ys) + 0.3), max(ys) - 0.3))
            side = "东" if t[0] > RULE - 0.5 and abs(t[1]) < RULE else ("南" if t[1] > 0 else "北")
            cands = [(t, side)]
        t, side = min(cands, key=lambda c: octd((x, y), c[0]))
        out.append((net, what[4:], (x, y), t, octd((x, y), t), side))
    return out


# ---- drawing ------------------------------------------------------------------------------------------------------
def draw(v, blocks, vias, caps, exits, core, path):
    lim = (-7.2, 7.2, -7.2, 7.2) if core else (BX0 - 1, BX1 + 1, BY0 - 1, BY1 + 1)
    fig, ax = plt.subplots(figsize=(11, 11), dpi=140 if core else 120)
    ax.set_xlim(lim[0], lim[1]); ax.set_ylim(lim[3], lim[2]); ax.set_aspect("equal")
    ax.add_patch(Rectangle((BX0, BY0), BX1 - BX0, BY1 - BY0, fc="#f4f4f1" if v["rest"] != "GND" else "#e9e9e6", ec="#222", lw=1.2))
    for net, poly in blocks.items():
        ax.add_patch(Polygon(poly, closed=True, fc=col(net), ec=col(net), alpha=0.33, lw=1.0))
        ax.add_patch(Polygon(poly, closed=True, fill=False, ec=col(net), lw=1.3))
    for name, poly in (("RK3568", [(-9.5, -9.5), (9.5, -9.5), (9.5, 9.5), (-9.5, 9.5)]), ("DDR3 A", M.chip_poly("A")), ("DDR3 B", M.chip_poly("B"))):
        ax.add_patch(Polygon(poly, closed=True, fill=False, ec="#111", lw=1.0, ls="--"))
        if not core:
            cx, cy = sum(p[0] for p in poly) / 4, sum(p[1] for p in poly) / 4
            ax.text(cx, cy + (8.4 if name == "RK3568" else 0), name, ha="center", va="center", fontsize=9, color="#111")
    if core:
        for b, x, y, k, net in M.soc_balls():
            if abs(x) < 7.6 and abs(y) < 7.6:
                ax.add_patch(Circle((x, y), 0.15, fc="none", ec=col(net) if k == "pwr" else "#bbb", lw=1.4 if k == "pwr" else 0.5))
                if k == "pwr":
                    ax.text(x, y, b, ha="center", va="center", fontsize=4.2, color="#000")
    for x, y, hole, pad, net, what in vias:
        if not (lim[0] < x < lim[1] and lim[2] < y < lim[3]):
            continue
        sig = net.startswith("sig:")
        c = "#9a9a9a" if sig else ("#333" if net == "GND" else col(net))
        ax.add_patch(Circle((x, y), pad / 2 if core else 0.17, fc=c if not sig else "none", ec=c, lw=0.6, alpha=0.95))
    for c in caps:
        (ax_, ay_), (bx_, by_) = c["a"], c["b"]
        ang = math.degrees(math.atan2(by_ - ay_, bx_ - ax_))
        L, Wd = (1.0, 0.5) if c["size"] == "0402" else (0.6, 0.3)
        r = Rectangle((-L / 2, -Wd / 2), L, Wd, fc="none", ec="#000", lw=1.1 if core else 0.5)
        r.set_transform(matplotlib.transforms.Affine2D().rotate_deg(ang).translate(*c["mid"]) + ax.transData)
        ax.add_patch(r)
    for net, ball, a, t, ln, side in exits:
        ax.plot([a[0], t[0]], [a[1], t[1]], color=col(net), lw=0.7, ls=":")
    if not core:
        for net, poly in blocks.items():
            for i in range(len(poly)):
                a, b = poly[i], poly[(i + 1) % len(poly)]
                for k, limv, off in ((0, BX0, (-0.5, 0)), (0, BX1, (0.5, 0)), (1, BY0, (0, -0.5)), (1, BY1, (0, 0.5))):
                    if abs(a[k] - limv) < 1e-9 and abs(b[k] - limv) < 1e-9 and math.dist(a, b) > 1.5:
                        mx, my = (a[0] + b[0]) / 2 + off[0], (a[1] + b[1]) / 2 + off[1]
                        ax.text(mx, my, net, ha="center", va="center", fontsize=7.5, color=col(net), rotation=90 if k == 0 else 0, fontweight="bold")
    from matplotlib.lines import Line2D
    hs = [Line2D([], [], marker="s", ls="", ms=9, mfc=col(n), mec=col(n), alpha=0.6, label=n) for n in blocks]
    hs += [Line2D([], [], marker="o", ls="", ms=5, mfc="#333", mec="#333", label="地过孔"),
           Line2D([], [], marker="o", ls="", ms=5, mfc="none", mec="#9a9a9a", label="信号过孔"),
           Line2D([], [], marker="o", ls="", ms=5, mfc="#444", mec="#444", label="小电源过孔"),
           Line2D([], [], ls=":", color="#444", label="小电源出线（示意）")]
    if core:
        hs.append(Line2D([], [], marker="s", ls="", ms=8, mfc="none", mec="#000", label="背面电容"))
    ax.legend(handles=hs, loc="lower left", fontsize=7.5, framealpha=0.92)
    ax.set_title(f"{v['title']}　L3 " + ("球区中心（空心圈是球，实心点是过孔，黑框是背面电容）" if core else "整板（板框为假设）"), fontsize=11)
    ax.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def write_sketch(v, blocks, path):
    lines = [f"# PROTOTYPE issue 52, {v['key']}: L3 blocks, mm, origin at the SoC centre (x east, y south).",
             "# Written by draw.py from variants.py; borders pulled back by gap / 2 from the drawn partition.",
             "layers 6", "planes L2 L3 L5", f"gap {GAP}", "clearance 0.2", "plane_clearance 0.127", "minwidth 0.2", ""]
    for net, poly in blocks.items():
        lines.append(f"region L3_{net} {net} L3")
        lines.append("  " + "  ".join(f"{x:g},{y:g}" for x, y in poly))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run():
    res = []
    for v in VARIANTS:
        blocks = {net: inset(resolve(verts)) for net, layer, verts in v["regions"]}
        write_sketch(v, blocks, OUT / f"{v['key']}.sketch")
        vias, no_site = place_vias(blocks)
        rows = [analyse_block(net, verts, vias) for net, layer, verts in v["regions"]]
        for row, (net, layer, verts) in zip(rows, v["regions"]):
            if net in BIG:
                row["core"] = core_report(net, verts, vias)
        caps, short = place_caps(vias)
        strips = {n: p for n, p in blocks.items() if n not in BIG}
        exits = small_exits(vias, strips if v["small"] == "strips" else {})
        draw(v, blocks, vias, caps, exits, False, OUT / f"{v['key']}_board.png")
        draw(v, blocks, vias, caps, exits, True, OUT / f"{v['key']}_core.png")
        sides = collections.Counter(e[5] for e in exits)
        res.append({"key": v["key"], "title": v["title"], "blurb": v["blurb"], "entry": v["entry"], "blocks": rows,
                    "no_site": no_site, "caps": {n: list(s) for n, s in short.items()}, "cap_sizes": dict(collections.Counter(c["size"] for c in caps)),
                    "exits": {"n": len(exits), "sides": dict(sides), "total": round(sum(e[4] for e in exits), 1),
                              "max": round(max(e[4] for e in exits), 1), "longest": max(exits, key=lambda e: e[4])[:2],
                              "by_net": {n: [round(sum(e[4] for e in exits if e[0] == n), 1), sum(1 for e in exits if e[0] == n)] for n in sorted({e[0] for e in exits})}},
                    "vias": dict(collections.Counter(("sig" if x[4].startswith("sig:") else ("gnd" if x[4] == "GND" else "pwr")) for x in vias if x[5].startswith("soc:")))})
    (OUT / "metrics.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    res = run()
    for r in res:
        print("==", r["title"])
        for b in r["blocks"]:
            print("  ", b["net"], b["area"], b["edge"], "ddr", b["ddr_joined"], "/", b["ddr_vias"], b.get("core"))
        print("   no site:", r["no_site"], "caps:", r["caps"], r["cap_sizes"])
        print("   exits:", r["exits"])
    import page
    page.write(res)
