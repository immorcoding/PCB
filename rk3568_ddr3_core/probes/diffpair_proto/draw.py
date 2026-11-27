"""PROTOTYPE (issue 37, throwaway): what a differential pair should look like.

    python rk3568_ddr3_core/probes/diffpair_proto/draw.py

Writes diffpair_variants.html next to this file and prints the numbers.
Three scenes, three variants each, drawn to scale (mm) from the real DQS0 balls of the RK3568
(G1 / G2, west edge; drawn with "out of the package" pointing right). Nothing here went through
KiCad DRC; clearances are checked numerically by this script (sampled, 0.01 mm steps).
"""
import json, math, os, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = HERE.parents[1] / "lib"
PINS = json.loads((LIB / "rk3568_pins.json").read_text(encoding="utf-8"))
PKG = json.loads((LIB / "rk3568_pin_length_mm.json").read_text(encoding="utf-8"))

P = 0.65                 # SoC ball pitch
PAD = 0.30               # SoC pad
W_IN = 0.1016            # track inside the rule area
W_DP, G_DP = 0.104, 0.15 # 100 ohm pair on L1 / L6
CC = W_DP + G_DP         # 0.254 centre to centre
W_DQ = 0.15              # 50 ohm single-ended, outer layers
GUARD_GAP = 0.70         # edge to edge across a guard strip (issue 47)
POUR_CLR = 0.15
VIA, DRILL = 0.40, 0.20
RULE_EDGE = 9.5 - 8.775 + 1.0   # rule area edge, measured from the outer ball row
SQ2 = math.sqrt(2)

# ---------------------------------------------------------------- primitives
class Scene:
    def __init__(self, x0, x1, y0, y1, scale):
        self.box, self.s = (x0, x1, y0, y1), scale
        self.tracks, self.rounds, self.guides, self.texts, self.pour, self.erase = [], [], [], [], None, []

    def track(self, net, pts, w, cls="sig"):
        self.tracks.append((net, pts, w, cls))

    def pad(self, net, x, y, d, label="", cls="pad", drill=0):
        self.rounds.append((net, x, y, d, label, cls, drill))

    def guide(self, x, label):
        self.guides.append((x, label))

    def text(self, x, y, s):
        self.texts.append((x, y, s))


def plen(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def sample(pts, step=0.01):
    out = []
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.dist(a, b) / step))
        out += [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]
    return out


def min_clearance(sc):
    """Smallest copper-to-copper distance between different nets; returns (mm, what)."""
    objs = [(net, sample(pts), w / 2, f"{net} 线") for net, pts, w, _ in sc.tracks]
    objs += [(net, [(x, y)], d / 2, f"{net} {'过孔' if drill else '焊盘'}{lab}") for net, x, y, d, lab, _, drill in sc.rounds]
    best = (9.0, "")
    for i, (na, pa, ra, la) in enumerate(objs):
        for nb, pb, rb, lb in objs[i + 1:]:
            if na == nb:
                continue
            if len(pa) > 60 and len(pb) > 60:      # track against track: thin the samples
                pa2, pb2 = pa[::2], pb[::2]
            else:
                pa2, pb2 = pa, pb
            d = min(math.dist(p, q) for p in pa2 for q in pb2) - ra - rb
            if d < best[0]:
                best = (d, f"{la} ↔ {lb}")
    return best


COL = {"p": "#f2b134", "n": "#f58a3c", "dq": "#b9534e", "l6": "#4f8fe0", "l6n": "#7fb0ee"}

def svg(sc):
    x0, x1, y0, y1 = sc.box
    s = sc.s
    o = [f'<svg viewBox="{x0 * s:.0f} {y0 * s:.0f} {(x1 - x0) * s:.0f} {(y1 - y0) * s:.0f}" xmlns="http://www.w3.org/2000/svg" '
         f'style="width:100%;max-width:{(x1 - x0) * s:.0f}px;background:#10161c">']
    if sc.pour:                       # GND pour drawn as a fill, then cleared round every other net
        px0, px1 = sc.pour
        o.append(f'<rect x="{px0 * s}" y="{y0 * s}" width="{(px1 - px0) * s}" height="{(y1 - y0) * s}" fill="#1f5f7d"/>')
        o.append(f'<clipPath id="c{id(sc)}"><rect x="{px0 * s}" y="{y0 * s}" width="{(px1 - px0) * s}" height="{(y1 - y0) * s}"/></clipPath><g clip-path="url(#c{id(sc)})">')
        for net, pts, w, cls in sc.tracks:
            if cls == "l6" or cls == "l6n":
                continue
            p = " ".join(f"{x * s:.1f},{y * s:.1f}" for x, y in pts)
            o.append(f'<polyline points="{p}" fill="none" stroke="#10161c" stroke-width="{(w + 2 * POUR_CLR) * s:.1f}" stroke-linejoin="round" stroke-linecap="round"/>')
        for net, x, y, d, lab, cls, drill in sc.rounds:
            if net != "GND":
                o.append(f'<circle cx="{x * s:.1f}" cy="{y * s:.1f}" r="{(d / 2 + POUR_CLR) * s:.1f}" fill="#10161c"/>')
        o.append("</g>")
    for ex0, ey0, ex1, ey1 in sc.erase:      # copper the pour would drop (narrower than 0.30)
        o.append(f'<rect x="{ex0 * s:.1f}" y="{ey0 * s:.1f}" width="{(ex1 - ex0) * s:.1f}" height="{(ey1 - ey0) * s:.1f}" fill="#10161c"/>')
    for bx0, by0, bx1, by1 in getattr(sc, 'boxes', []):
        o.append(f'<rect x="{bx0 * s:.1f}" y="{by0 * s:.1f}" width="{(bx1 - bx0) * s:.1f}" height="{(by1 - by0) * s:.1f}" fill="none" stroke="#9be28f" stroke-dasharray="7 5" stroke-width="1.5"/>')
    for x, lab in sc.guides:
        o.append(f'<line x1="{x * s}" y1="{y0 * s}" x2="{x * s}" y2="{y1 * s}" stroke="#7d8c9a" stroke-dasharray="6 5"/>')
        o.append(f'<text x="{x * s + 4}" y="{y0 * s + 15}" fill="#b5c2ce" font-size="13">{lab}</text>')
    for order in (("l6", "l6n"), ("dq",), ("p", "n")):
        for net, pts, w, cls in sc.tracks:
            if cls in order:
                p = " ".join(f"{x * s:.1f},{y * s:.1f}" for x, y in pts)
                o.append(f'<polyline points="{p}" fill="none" stroke="{COL[cls]}" stroke-width="{w * s:.1f}" stroke-linejoin="round" stroke-linecap="round"><title>{net} {w} mm</title></polyline>')
    for net, x, y, d, lab, cls, drill in sc.rounds:
        fill = {"gnd": "#3fa7d6", "pad": "#8c979f", "p": COL["p"], "n": COL["n"], "dq": "#b9534e"}[cls]
        o.append(f'<circle cx="{x * s:.1f}" cy="{y * s:.1f}" r="{d / 2 * s:.1f}" fill="{fill}"><title>{net}</title></circle>')
        if drill:
            o.append(f'<circle cx="{x * s:.1f}" cy="{y * s:.1f}" r="{drill / 2 * s:.1f}" fill="#10161c"/>')
        if lab:
            o.append(f'<text x="{x * s:.1f}" y="{y * s + 4:.1f}" fill="#10161c" font-size="{max(9, s * 0.075):.0f}" text-anchor="middle" font-weight="600">{lab}</text>')
    for x, y, t in sc.texts:
        o.append(f'<text x="{x * s:.1f}" y="{y * s:.1f}" fill="#dfe7ee" font-size="13">{t}</text>')
    o.append(f'<line x1="{(x0 + 0.1) * s}" y1="{(y1 - 0.08) * s}" x2="{(x0 + 0.6) * s}" y2="{(y1 - 0.08) * s}" stroke="#fff" stroke-width="2"/>'
             f'<text x="{(x0 + 0.65) * s}" y="{(y1 - 0.08) * s + 4}" fill="#fff" font-size="12">0.5 mm</text></svg>')
    return "\n".join(o)

# ---------------------------------------------------------------- scene 1: leaving the SoC ball field
BALLS = {  # (ring, row) -> (ball, net); real map round DQS0, west edge
    (0, -2): ("E1", "DQ1"), (0, -1): ("F1", "GND"), (0, 0): ("G1", "DQS0P"), (0, 1): ("H1", "DQ6"), (0, 2): ("J1", "DQ4"),
    (1, -2): ("E2", "DQ2"), (1, -1): ("F2", "DQ0"), (1, 0): ("G2", "DQS0N"), (1, 1): ("H2", "GND"), (1, 2): ("J2", "DQ5"),
    (2, -2): ("E3", "GND"), (2, -1): ("F3", "GND"), (2, 1): ("H3", "GND"), (2, 2): ("J3", "GND"),
}
XEND = 2.1


def exit_base(dq0=None, fan=0.0):
    sc = Scene(-1.6, XEND + 0.1, -1.75 - fan, 1.75, 190)
    for (ring, row), (ball, net) in BALLS.items():
        cls = "gnd" if net == "GND" else "p" if net.endswith("P") else "n" if net.endswith("N") else "dq"
        sc.pad(net if net != "GND" else "GND", -ring * P, row * P, PAD, ball, cls)
    sc.guide(0.725, "封装边")
    sc.guide(RULE_EDGE, "规则区边")
    sc.track("DQ1", [(0, -2 * P), (0.25, -2 * P), (0.25 + fan, -2 * P - fan), (XEND, -2 * P - fan)] if fan else [(0, -2 * P), (XEND, -2 * P)], W_IN, "dq")
    sc.track("DQ4", [(0, 2 * P), (XEND, 2 * P)], W_IN, "dq")
    sc.track("DQ6", [(0, P), (XEND, P)], W_IN, "dq")
    sc.track("DQ2", [(-P, -2 * P), (-P / 2, -1.5 * P)] + ([(0.25, -1.5 * P), (0.25 + fan, -1.5 * P - fan)] if fan else []) + [(XEND, -1.5 * P - fan)], W_IN, "dq")
    sc.track("DQ5", [(-P, 2 * P), (-P / 2, 1.5 * P), (XEND, 1.5 * P)], W_IN, "dq")
    sc.track("DQ0", dq0 or [(-P, -P), (-P / 2, -P / 2), (XEND, -P / 2)], W_IN, "dq")
    return sc


def exit_A():
    sc = exit_base()
    off = P / 2 - CC          # 0.071: the outer-ball track sits this far off its pad centre
    p = [(0, 0), (off, off), (XEND, off)]
    n = [(-P, 0), (-P / 2, P / 2), (XEND, P / 2)]
    return sc, p, n, off


def exit_B():
    sc = exit_base()
    a = 0.3                   # the inner-ball track starts its step 0.1 later, or the two steps pinch to 0.078
    b = a + (P / 2 - CC / 2)
    p = [(0, 0), (0.271, 0), (0.271 + CC / 2, -CC / 2), (XEND, -CC / 2)]
    n = [(-P, 0), (-P / 2, P / 2), (a, P / 2), (b, CC / 2), (XEND, CC / 2)]
    return sc, p, n, b


def exit_C():
    sc = exit_base()
    off = P / 2 - CC
    p = [(0, 0), (XEND, 0)]
    n = [(-P, 0), (-P / 2, P / 2), (RULE_EDGE, P / 2), (RULE_EDGE + off, CC), (XEND, CC)]
    return sc, p, n, RULE_EDGE + off


def ear(y0, need, x1=0.75, x2=1.45, c=0.1):
    """Chamfered U on a track at y = y0, pointing to -y, adding `need` mm."""
    H = (need + (8 - 4 * SQ2) * c) / 2
    return H, [(x1, y0), (x1 + c, y0 - c), (x1 + c, y0 - H + c), (x1 + 2 * c, y0 - H), (x2 - 2 * c, y0 - H),
               (x2 - c, y0 - H + c), (x2 - c, y0 - c), (x2, y0)]

# ---------------------------------------------------------------- scene 2: layer change
NB = [GUARD_GAP + CC / 2 + W_DP / 2 + W_DQ / 2]       # first DQ neighbour, centre
NB.append(NB[0] + W_DQ + 2 * W_DQ)                    # its S-S partner
STRIP = CC / 2 + W_DP / 2 + GUARD_GAP / 2             # guard strip centre line


def change(kind, vy=0.4):
    L = 3.0
    sc = Scene(-L, L, -2.3, 2.3, 130)
    sc.pour = (-L, L)
    fl = vy - CC / 2
    for sgn, cls, net in ((-1, "p", "DQS0P"), (1, "n", "DQS0N")):
        sc.track(net, [(-L, sgn * CC / 2), (-fl, sgn * CC / 2), (0, sgn * vy)], W_DP, cls)
        sc.track(net, [(0, sgn * vy), (fl, sgn * CC / 2), (L, sgn * CC / 2)], W_DP, "l6" if sgn < 0 else "l6n")
        sc.pad(net, 0, sgn * vy, VIA, "", cls, DRILL)
    gnd, bulge = [], 0.0
    if kind == "A":
        gy = vy + 0.6
        gnd = [(0, -gy), (0, gy), (-2.2, -STRIP), (-2.2, STRIP), (2.2, -STRIP), (2.2, STRIP)]
        bulge = gy + VIA / 2 + POUR_CLR + W_DQ / 2 - NB[0]
    else:
        d = math.sqrt(0.6 ** 2 - (STRIP - vy) ** 2)
        gnd = [(-d, -STRIP), (-d, STRIP)] + ([(d, -STRIP), (d, STRIP)] if kind == "C" else [(2.2, -STRIP), (2.2, STRIP)])
        gnd += [(-2.6, -STRIP), (-2.6, STRIP)]
    for x, y in gnd:
        sc.pad("GND", x, y, VIA, "", "gnd", DRILL)
    for sgn in (-1, 1):
        for k, c in enumerate(NB):
            name = f"DQ{'ab'[k]}{'+' if sgn > 0 else '-'}"
            if bulge > 0:
                h = 0.45
                pts = [(-L, sgn * c), (-h - bulge, sgn * c), (-h, sgn * (c + bulge)), (h, sgn * (c + bulge)), (h + bulge, sgn * c), (L, sgn * c)]
            else:
                pts = [(-L, sgn * c), (L, sgn * c)]
            sc.track(name, pts, W_DQ, "dq")
    sc.text(-L + 0.1, -2.05, "← 从这边来：差分对和邻线都在 L1（黄 / 橙 / 红），青色是 L1 的地铺铜")
    sc.text(0.35, 2.15, "换到 L6 后往这边走（蓝，在板子背面，不碰 L1 的铺铜）→")
    near = min(math.dist((0, vy), g) for g in gnd)
    half = max(max(abs(y) for _, y in gnd) + VIA / 2, vy + VIA / 2)
    return sc, {"gnd_n": sum(1 for g in gnd if abs(g[0]) < 1), "near": near, "half": half, "bulge": max(bulge, 0.0),
                "uncoupled": 2 * fl * SQ2}

# ---------------------------------------------------------------- scene 3: intra-pair compensation
def bumps(kind, need):
    L0, L1 = -0.5, 5.6
    sc = Scene(L0, L1, -2.0, 2.0, 150)
    sc.pour = (L0, L1)
    sc.guide(0.0, "规则区边")
    y = -CC / 2
    x = 0.3
    pts = [(L0, y)]
    if kind == "A":
        h, top, between = 0.30, 0.20, 0.20
        per = 2 * h * (SQ2 - 1)
        n = max(1, round(need / per))
        for _ in range(n):
            pts += [(x, y), (x + h, y - h), (x + h + top, y - h), (x + 2 * h + top, y)]
            x += 2 * h + top + between
        span = x - between - 0.3
    else:
        r, between = 0.30, 0.20
        h = r
        per = (math.pi - 2) * r
        n = max(1, round(need / per))
        for _ in range(n):
            pts += [(x, y)] + [(x + r - r * math.cos(a), y - r * math.sin(a)) for a in (math.pi * i / 24 for i in range(1, 24))] + [(x + 2 * r, y)]
            x += 2 * r + between
        span = x - between - 0.3
    pts.append((L1, y))
    sc.track("DQS0P", pts, W_DP, "p")
    sc.erase.append((0.3 - POUR_CLR, -(NB[0] - W_DQ / 2), 0.3 + span + POUR_CLR, y))
    sc.track("DQS0N", [(L0, CC / 2), (L1, CC / 2)], W_DP, "n")
    for sgn in (-1, 1):
        for k, c in enumerate(NB):
            sc.track(f"DQ{'ab'[k]}{'+' if sgn > 0 else '-'}", [(L0, sgn * c), (L1, sgn * c)], W_DQ, "dq")
    for vx in (0.5, 2.9, 5.2):
        sc.pad("GND", vx, STRIP, VIA, "", "gnd", DRILL)
    vx = 0.3 + span + 0.55
    while vx < L1 - 0.2:
        sc.pad("GND", vx, -STRIP, VIA, "", "gnd", DRILL)
        vx += 2.4
    return sc, {"n": n, "per": per, "added": n * per, "span": span, "h": h, "gap_max": G_DP + h,
                "to_nb": GUARD_GAP - h, "cu": GUARD_GAP - h - 2 * POUR_CLR}


def bump_C(need):
    off = P / 2 - CC
    dq0 = [(-P, -P), (-P / 2, -P / 2), (0.25, -P / 2), (0.25 + 0.435, -0.76), (XEND, -0.76)]
    sc = exit_base(dq0, fan=0.435)
    H, e = ear(off, need)
    sc.track("DQS0P", [(0, 0), (off, off)] + e + [(XEND, off)], W_IN, "p")
    sc.track("DQS0N", [(-P, 0), (-P / 2, P / 2), (XEND, P / 2)], W_IN, "n")
    return sc, H

def ear_flat(h):
    """Flat length (top of an ear, and between two ears) that keeps facing legs 3 x track width apart, edge to edge."""
    return max(0.15, 3 * W_DP + W_DP - 2 * min(0.10, h / 2))


def round_ear(x, h, top=None):     # rounded rectangle: fillet up, flat top, fillet down (user's choice)
    top = ear_flat(h) if top is None else top
    """Rounded ear starting at x on the baseline u = 0, pointing to +u. Returns (points, width)."""
    r = min(0.10, h / 2)
    q = [i * math.pi / 2 / 24 for i in range(25)]
    pts = [(x + r * math.sin(t), r - r * math.cos(t)) for t in q]
    pts += [(x + 2 * r - r * math.cos(t), h - r + r * math.sin(t)) for t in q]
    w = 4 * r + top
    pts += [(x + w - px + x, pu) for px, pu in reversed(pts)]
    return pts, w, 2 * h - (8 - 2 * math.pi) * r


EAR_MAX = 0.20      # user 2026-11-27: height is capped, not fixed


def ear_gain(h):
    return 2 * h - (8 - 2 * math.pi) * min(0.10, h / 2)


def ear_plan(need, hmax=EAR_MAX):
    """Fewest ears that can add `need`, then one common height that adds it exactly."""
    n = max(1, math.ceil(need / ear_gain(hmax) - 1e-9))
    lo, hi = 0.0, hmax
    for _ in range(50):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if n * ear_gain(mid) < need else (lo, mid)
    return n, hi


def ears(h, need, room=1.0, n=None):
    """Rounded ears on the short track. They start inside the rule area (x < 0) and spill past it if they must."""
    L0, L1 = -1.3, 4.3
    sc = Scene(L0, L1, -2.0, 2.0, 170)
    sc.pour = (0.0, L1)
    sc.guide(0.0, "规则区边")
    sc.text(L0 + 0.05, -1.75, "← 规则区内（展开段）")
    sc.text(0.9, -1.75, "规则区外：包地的直线段 →")
    y, between = -CC / 2, ear_flat(h)
    _, w, per = round_ear(0, h)
    n = n or max(1, round(need / per))
    x = -room
    pts = [(L0, y)]
    for _ in range(n):
        e, _, _ = round_ear(x, h)
        pts += [(px, y - pu) for px, pu in e]
        x += w + between
    end = x - between
    pts.append((L1, y))
    sc.track("DQS0P", pts, W_DP, "p")
    sc.track("DQS0N", [(L0, CC / 2), (L1, CC / 2)], W_DP, "n")
    cu = GUARD_GAP - h - 2 * POUR_CLR
    if end > 0 and cu < 0.30:
        sc.erase.append((0.0, -(NB[0] - W_DQ / 2), end + POUR_CLR, y))
    for sgn in (-1, 1):
        for k, c in enumerate(NB):
            sc.track(f"DQ{'ab'[k]}{'+' if sgn > 0 else '-'}", [(L0, sgn * c), (L1, sgn * c)], W_DQ, "dq")
    for vx in (0.5, 2.9):
        sc.pad("GND", vx, STRIP, VIA, "", "gnd", DRILL)
    vx = max(end, 0) + 0.5
    while vx < L1 - 0.2:
        sc.pad("GND", vx, -STRIP, VIA, "", "gnd", DRILL)
        vx += 2.4
    fit = sum(1 for i in range(n) if -room + i * (w + between) + w <= 0.0)
    return sc, {"n": n, "per": per, "w": w, "span": end + room, "spill": max(end, 0.0), "fit": fit, "left": need - n * per,
                "gap_max": G_DP + h, "to_nb": GUARD_GAP - h, "cu": cu}


def offset(pts, d):
    """Offset an open polyline by d (mitre joins)."""
    out = []
    for i, pt in enumerate(pts):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, len(pts) - 1)]
        def unit(u, v):
            l = math.dist(u, v)
            return ((v[0] - u[0]) / l, (v[1] - u[1]) / l)
        t1 = unit(a, pt) if i else unit(pt, b)
        t2 = unit(pt, b) if i < len(pts) - 1 else t1
        n1, n2 = (-t1[1], t1[0]), (-t2[1], t2[0])
        m = (n1[0] + n2[0], n1[1] + n2[1])
        k = d / (1 + n1[0] * n2[0] + n1[1] * n2[1])
        out.append((pt[0] + m[0] * k, pt[1] + m[1] * k))
    return out


def _unused_fillet(pts, R, steps=10):
    """Round every corner of a polyline with radius R."""
    out = [pts[0]]
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        u = ((a[0] - b[0]) / math.dist(a, b), (a[1] - b[1]) / math.dist(a, b))
        v = ((c[0] - b[0]) / math.dist(c, b), (c[1] - b[1]) / math.dist(c, b))
        ang = math.acos(max(-1, min(1, u[0] * v[0] + u[1] * v[1])))
        t = R / math.tan(ang / 2)
        p0 = (b[0] + u[0] * t, b[1] + u[1] * t)
        p1 = (b[0] + v[0] * t, b[1] + v[1] * t)
        bis = (u[0] + v[0], u[1] + v[1])
        bl = math.hypot(*bis)
        cen = (b[0] + bis[0] / bl * R / math.sin(ang / 2), b[1] + bis[1] / bl * R / math.sin(ang / 2))
        a0 = math.atan2(p0[1] - cen[1], p0[0] - cen[0])
        a1 = math.atan2(p1[1] - cen[1], p1[0] - cen[0])
        d = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        out += [(cen[0] + R * math.cos(a0 + d * i / steps), cen[1] + R * math.sin(a0 + d * i / steps)) for i in range(steps + 1)]
    return out + [pts[-1]]


PAIR_W = 2 * W_DP + G_DP          # 0.358, outer edge to outer edge of the pair
LEG_GAP = 3 * W_DQ                # 0.45, pair edge to pair edge between two legs (CLK / DQS: 3 x track width)
PAIR_PITCH = round(PAIR_W + LEG_GAP, 2)   # 0.81 leg centre distance
PAIR_AMP_MAX = 3.0     # user 2026-11-27: relax; the real cap is the room in the tuning area
END_STRAIGHT = 0.7


def hump(x0, pch, amp, q=48):
    """One RTE-7 hump of a centre line: quarter arc, leg, half circle, leg, quarter arc. Radius = pitch / 2. Points to -y."""
    r = pch / 2
    arc = lambda cx, cy, a0, a1: [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / q)), cy - r * math.sin(math.radians(a0 + (a1 - a0) * i / q))) for i in range(q + 1)]
    pts = arc(x0, -r, 270, 360)                     # (x0, 0) -> (x0 + r, -r)
    pts += arc(x0 + 2 * r, -(amp - r), 180, 0)      # over the top
    pts += arc(x0 + 4 * r, -r, 180, 270)            # back to the base line
    return pts


def pair_meander(amp=PAIR_PITCH, n=2, pch=PAIR_PITCH):
    """The pair meandering as a pair, drawn like the ordinary arc serpentine (RTE-7)."""
    L0, L1 = -0.6, 5.4
    sc = Scene(L0, L1, -2.2, 1.6, 150)
    sc.guide(0.0, "规则区边")
    x = END_STRAIGHT
    c = [(L0, 0)]
    for _ in range(n):
        c += hump(x, pch, amp)
        x += 2 * pch
    c.append((L1, 0))
    c = [pt for i, pt in enumerate(c) if i == 0 or math.dist(pt, c[i - 1]) > 1e-9]
    sc.track("DQS0P", offset(c, -CC / 2), W_DP, "p")
    sc.track("DQS0N", offset(c, CC / 2), W_DP, "n")
    nb = PAIR_W / 2 + LEG_GAP + W_DQ / 2
    sc.track("DQa+", [(L0, nb), (L1, nb)], W_DQ, "dq")
    sc.track("DQa-", [(L0, -(amp + nb)), (L1, -(amp + nb))], W_DQ, "dq")
    sc.boxes = [(0.0, -(amp + PAIR_W / 2 + LEG_GAP), END_STRAIGHT + n * 2 * pch + END_STRAIGHT, -(PAIR_W / 2))]
    sc.text(0.1, 1.35, "绿色虚线 = 等长区域：矩形，贴着直线段的一侧，里面不放别的线和过孔")
    added = plen(c) - (L1 - L0)
    return sc, added, plen(offset(c, -CC / 2)) - plen(offset(c, CC / 2)), n * (2 * amp - (4 - math.pi) * pch)

# ---------------------------------------------------------------- numbers
def soc_pairs():
    fn = {}
    for p in PINS:
        if p["part"] == "F":
            for part in p["name"].split("/"):
                if part.startswith("DDR3_"):
                    fn[part[5:]] = p["ball"]
    out = []
    for a, b in (("DQS0P", "DQS0N"), ("DQS1P", "DQS1N"), ("DQS2P", "DQS2N"), ("DQS3P", "DQS3N"), ("CLKP", "CLKN")):
        ba, bb = fn[a], fn[b]
        ring = lambda ball: min(ord(ball[0]) - 65, int(ball[1:]) - 1)     # A..=0, column 1 = 0 (west / north edges)
        outer, inner = (ba, bb) if ring(ba) < ring(bb) else (bb, ba)
        out.append((a[:-1], outer, inner, PKG[inner] - PKG[outer]))
    return out


def main():
    blocks, log = [], []
    # ---- scene 1
    rows1, board = [], {}
    for key, title, fnc, note in (
        ("A", "1A 以通道为轴：内圈球的线沿通道直出，外圈球的线贴着它出盘", exit_A,
         "内圈球（G2）的线斜进 G1、H1 之间的通道后一路直线；外圈球（G1）的线在盘内偏 0.071 mm 出盘，一出盘两根就是 0.15 的对内间隙。盘外只有一个 45° 拐点。"),
        ("B", "1B 以球行为轴：两根在球区外对称收拢成 Y 形", exit_B,
         "差分对的中心线落在球行上（和两边的 DQ 对称）。两根各拐一次 45°，在球区外约 0.5 mm 处收到 0.15 间隙并行；外圈球那根离 DQ0 的线更近。"),
        ("C", "1C 不急着合并：按半个球距并行，出规则区再收到 0.15", exit_C,
         "两根在规则区内保持 0.325 mm 中心距（间隙 0.22），都是直线；出规则区时内圈球那根收一小步。球区附近没有任何小拐点，但规则区内这 1.7 mm 耦合较松。"),
    ):
        sc, p, n, xc = fnc()
        sc.track("DQS0P", p, W_IN, "p")
        sc.track("DQS0N", n, W_IN, "n")
        diff = plen(n) - plen(p)
        board[key] = diff
        clr, what = min_clearance(sc)
        rows1.append(f"<tr><td>{key}</td><td>{xc:.2f}</td><td>{diff:.3f}</td><td>{len(p) + len(n) - 4}</td><td>{clr:.3f}（{what}）</td></tr>")
        log.append(("exit", key, round(diff, 4), round(clr, 4), what))
        blocks.append(("s1", f"<h3>{title}</h3><p>{note}</p>{svg(sc)}"))
    # ---- per pair need (exit A)
    pairs = soc_pairs()
    need = {name: board["A"] + dp for name, outer, inner, dp in pairs}
    rowsP = "".join(f"<tr><td>{name}</td><td>{outer}</td><td>{inner}</td><td>{dp:+.3f}</td><td>{board['A']:.3f}</td><td><b>{need[name]:.2f}</b></td></tr>"
                    for name, outer, inner, dp in pairs)
    worst = max(need.values())
    # ---- scene 2
    rows2 = []
    for key, title, note in (
        ("A", "2A 一字排开：地 – 信号 – 信号 – 地", "四个过孔排成一行，地过孔在信号过孔的正外侧。最对称；两边的线要各让出一个鼓包。"),
        ("B", "2B 借包地铜条上的过孔：两个地过孔退到来线一侧", "地过孔就是包地铜条上本来要打的过孔，挪到信号过孔后方 0.5 mm 处。线带不变宽，邻线全程直线。"),
        ("C", "2C 四角围住：来线一侧和去线一侧各两个", "和 2B 一样用铜条上的过孔，前后各一对，L1 和 L6 两侧的回流都有就近的地过孔。"),
    ):
        sc, st = change(key)
        clr, what = min_clearance(sc)
        rows2.append(f"<tr><td>{key}</td><td>{st['gnd_n']}</td><td>{st['near']:.2f}</td><td>{2 * st['half']:.2f}</td><td>{st['bulge']:.2f}</td><td>{st['uncoupled']:.2f}</td><td>{clr:.3f}（{what}）</td></tr>")
        log.append(("change", key, {k: round(v, 3) for k, v in st.items()}, round(clr, 4), what))
        blocks.append(("s2", f"<h3>{title}</h3><p>{note}</p>{svg(sc)}"))
        if key == "B":
            sc, st = change("B", vy=0.3)
            clr, what = min_clearance(sc)
            rows2.append(f"<tr><td>B，过孔对 0.60</td><td>{st['gnd_n']}</td><td>{st['near']:.2f}</td><td>{2 * st['half']:.2f}</td><td>{st['bulge']:.2f}</td><td>{st['uncoupled']:.2f}</td><td>{clr:.3f}（{what}）</td></tr>")
            log.append(("change", "B 0.60", {k: round(v, 3) for k, v in st.items()}, round(clr, 4), what))
            blocks.append(("s2", f"<h3>2B，两个信号过孔中心距 0.60（盘边到盘边 0.20）</h3><p>官方板是 0.552。张开段从 0.77 降到 {st['uncoupled']:.2f} mm；两个过孔在地层上的避让圈连成一个长圆孔。</p>{svg(sc)}"))
    # ---- scene 3 (third round, user 2026-11-27: height capped at 0.20, set per pair)
    rows3 = []
    for nm, outer, inner, dp in pairs:
        n, h = ear_plan(need[nm])
        sc, st = ears(h, need[nm], n=n)
        clr, what = min_clearance(sc)
        guard = "保住" if st["cu"] >= 0.30 else f"{st['cu']:.2f}，铺不进"
        rows3.append(f"<tr><td>{nm}</td><td>{need[nm]:.3f}</td><td>{n}</td><td>{h:.3f}</td><td>{st['w']:.2f}</td><td>{need[nm] - n * st['per']:+.3f}</td><td>{st['span']:.2f}</td>"
                     f"<td>{st['spill']:.2f}</td><td>{st['gap_max']:.2f}</td><td>{st['to_nb']:.2f}</td><td>{guard}</td><td>{clr:.3f}</td></tr>")
        log.append(("ear", nm, n, round(h, 4), {k: round(v, 3) for k, v in st.items()}, round(clr, 4), what))
        blocks.append(("s3", f"<h3>{nm}：补 {need[nm]:.2f} mm，{n} 个，高 {h:.3f}</h3>{svg(sc)}"))
    sc, added, skew, formula = pair_meander()
    clr, what = min_clearance(sc)
    log.append(("pair meander", round(added, 3), round(formula, 3), round(skew, 4), round(clr, 4), what))
    blocks.append(("s4", f"<h3>整对一起绕：两个弯，摆幅 {PAIR_PITCH}，腿中心距 {PAIR_PITCH}</h3><p>形状和普通线的圆弧蛇形相同（腿垂直、半圆封顶，中心线半径 = 腿中心距的一半），两根是同心圆弧，间隙全程 0.15。"
                         f"整对加长 {added:.2f} mm（公式 n·(2a − 0.858p) 给 {formula:.2f}），P、N 之间的差 {abs(skew):.3f} mm。</p>{svg(sc)}"))

    def sec(tag):
        return "".join(b for t, b in blocks if t == tag)

    head = '<!doctype html><html lang="zh"><meta charset="utf-8">'
    html = f"""<title>差分对画法原型</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
/* layout: one reading column; figures and tables scroll inside their own boxes */
:root{{--bg:#fbfcfd;--fg:#1c2630;--muted:#55636f;--line:#b8c2cc;--rule:#1c2630;--rec-bg:#eaf4ee;--rec-bar:#3f8f5f;--th:#eef2f5}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--bg:#12181e;--fg:#e3e9ee;--muted:#9fb0bd;--line:#3d4a55;--rule:#9fb0bd;--rec-bg:#17301f;--rec-bar:#5fb37f;--th:#1c252d;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#12181e;--fg:#e3e9ee;--muted:#9fb0bd;--line:#3d4a55;--rule:#9fb0bd;--rec-bg:#17301f;--rec-bar:#5fb37f;--th:#1c252d;color-scheme:dark}}
body{{font:15px/1.65 system-ui,"Microsoft YaHei","PingFang SC",sans-serif;background:var(--bg);color:var(--fg);max-width:1040px;margin:0 auto;padding-block:24px;
padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}}
h1{{font-size:26px;line-height:1.3;text-wrap:balance}}h2{{margin-top:44px;border-top:2px solid var(--rule);padding-top:14px;font-size:21px;text-wrap:balance}}h3{{margin-top:30px;font-size:17px}}
.wide{{overflow-x:auto}}table{{border-collapse:collapse;margin:10px 0;font-variant-numeric:tabular-nums}}td,th{{border:1px solid var(--line);padding:4px 9px;text-align:right;font-size:14px}}
th{{background:var(--th)}}td:first-child,th:first-child{{text-align:center}}
.k{{color:var(--muted)}}.k span{{display:inline-block;width:26px;height:6px;margin:0 6px 2px 14px}}.rec{{background:var(--rec-bg);border-left:4px solid var(--rec-bar);padding:8px 12px}}
svg{{display:block;border-radius:4px}}
</style>
<h1>原型（用完即弃）：差分对画成什么样</h1>
<p>三件事各出几种画法。第二轮：换层已定 2B；对内补偿改成圆角小耳朵（第三节重画）；出球区等官方板的实测。全部按比例画，单位 mm，数字由脚本算。
对象是 RK3568 的 DQS0（G1 / G2，西边），图里“出封装”的方向朝右；其余四对（DQS1–3、CLK）在球阵上的姿势相同。
没有过 KiCad 的 DRC；“最小间距”是脚本按 0.01 mm 取样算的铜到铜距离。</p>
<p class="k"><span style="background:{COL['p']}"></span>外圈球那根（短）<span style="background:{COL['n']}"></span>内圈球那根（长）<span style="background:{COL['dq']}"></span>旁边的 DQ
<span style="background:{COL['l6']}"></span>L6 上的线<span style="background:#1f5f7d;height:12px"></span>L1 地铺铜<span style="background:#3fa7d6;height:12px;width:12px;border-radius:6px"></span>地球 / 地过孔</p>

<h2>先看一个事实：五对差分线都是“一前一后”出球，外圈球那根天生短</h2>
<p>RK3568 的五对（DQS0–3、CLK）都在最外两圈，P、N 在同一行里一前一后垂直于封装边。两个焊盘之间（空隙 0.35 mm）只过得了一根线，
所以内圈球那根必须从外圈球旁边的通道绕出去，板上多走约 {board['A']:.2f} mm；再加上封装内引线的差，外圈球那根要补的长度如下（对内工作目标 0.15 mm，上限 0.30 mm）：</p>
<div class="wide"><table><tr><th>对</th><th>外圈球</th><th>内圈球</th><th>封装内：内 − 外</th><th>板上：内 − 外（画法 1A）</th><th>外圈球那根要补</th></tr>{rowsP}</table></div>
<p>颗粒那一头怎么进球区取决于颗粒的扇出，这里没有画。</p>

<h2>一、成对出 SoC 球区（L1）</h2>
<div class="wide"><table><tr><th>画法</th><th>从外圈球中心起多远开始按 0.15 间隙并行</th><th>板上长度差（内 − 外）</th><th>两根线的拐点数（含盘内的）</th><th>最小间距（规则区内下限 0.09）</th></tr>{''.join(rows1)}</table></div>
<p>地球（F1、H2 等）的过孔没有画，扇出工具要让它们避开这两条通道。旁边的 DQ 只画了直出的一段。</p>
<p><b>官方板怎么出</b>（子任务 2026-11-27 从 EVB1 和 LP4X 模板的板文件量出，共 11 对，全部在顶层出；几何数字主会话没有抽查，球位和封装引线长度和我们的表一致）：</p>
<ul>
<li>和 1A 是同一种画法。外圈球的线从盘心斜出一小段，偏心 0.05–0.08 mm 后直出；内圈球的线沿封装轴线走 0.2 mm，45° 拐进通道中心（偏 0.30–0.32 mm）后直出。</li>
<li>内圈球的线走的通道，另一侧总是地球（DQS0 是 G1 和 F1 之间）。图里画在了 G1、H1 之间，是镜像的另一侧；正式做时照官方选地球一侧。</li>
<li>11 对里有 7 对在离外圈球中心 0.01–0.26 mm 处就按最终间距并行（中心距 0.249，间隙 0.152，线宽 0.0965）；其余 4 对在 0.4–0.95 mm 处，原因是出球口上先放了一个补偿的小凸起。</li>
<li>对内补偿：梯形小凸起，高 0.152、顶 0.279、周期 0.864，每个补 0.126 mm；一部分紧贴出球口，一部分在包地的直线段上，包地线都不跟着绕。LP4X 补到板上加封装内只差 −0.12 至 +0.10 mm；EVB1 没有补平，五对剩 −0.41、+0.71、+1.26、+0.11、+0.60 mm。</li>
<li>换层的过孔对：中心距 0.552（一例 0.508），最近的地过孔在 SoC 一端 0.51–0.75 mm。我们已定的是 0.8 和 0.60（2B）。</li>
<li>整对一起绕：只有 LP4X 的 CLK_B 有一处，P、N 一起做了一个高 0.15 的梯形，不是连续的蛇形。</li>
</ul>
<p class="rec">我的推荐：1A，和官方板的画法相同。并行得最早、拐点最少；代价是外圈球那根在盘内偏心 0.071 mm 出盘（KiCad 算长度时按盘心到出盘点的直线折算，实测过）。</p>
{sec('s1')}

<h2>二、换层：过孔对和地过孔（L1 → L6，规则区外）</h2>
<p>已定的数：过孔 0.4 / 0.2，两个信号过孔中心距 ≥ 0.8；地过孔离信号过孔中心 ≤ 0.635（这里取 0.60，盘边到盘边 0.20）；
差分对两侧是 0.70 的包地间隙（铜条中心线离对的中心 {STRIP:.3f}），再外面是 DQ。邻线画成直通；整个字节组一起换层时 DQ 的过孔怎么排是另一件事，这里不定。</p>
<div class="wide"><table><tr><th>画法</th><th>贴身的地过孔数</th><th>地过孔到信号过孔中心</th><th>过孔占的总宽</th><th>邻线每侧让出</th><th>每层张开段（非耦合）</th><th>最小间距（下限 0.15）</th></tr>{''.join(rows2)}</table></div>
<p class="rec">已定（用户 2026-11-27）：2B。原来的推荐：2B，要更稳妥就 2C。两者都不让线带变宽；2A 每侧要鼓出约 0.5 mm，一个字节组里换层的地方会鼓成一个包。</p>
{sec('s2')}

<h2>三、对内补偿：圆角小耳朵，高度有上限、每对自己定</h2>
<p>已定（用户 2026-11-27）：圆角、矮、可以多几个；高度不固定，上限 {EAR_MAX:.2f} mm。脚本的算法：取能补完的最少个数，再把这一对的耳朵调成同一个高度，正好补完。
补在外圈球那根（短的）上，向外凸；从规则区内的展开段（约 1 mm）开始排，排不下的顺着伸到规则区外。图里的邻线是 DQS0 的间距，五对通用。</p>
<div class="wide"><table><tr><th>对</th><th>要补</th><th>个数</th><th>每个高</th><th>每个宽（腿间边到边 0.312）</th><th>补完还差</th><th>占的长度</th><th>伸出规则区</th>
<th>对内最大间隙</th><th>耳朵顶到邻线（要求 ≥ 0.45）</th><th>伸出段那一侧的地铜（最小 0.30）</th><th>最小间距</th></tr>{''.join(rows3)}</table></div>
<p>耳朵伸出规则区的那一小段，耳朵一侧的地铜窄于 0.30 mm，铺铜进不去，这一段单侧没有包地（另一侧有）。官方 LP4X 模板上唯一的一例也是这样：3 个高 0.152 mm 的梯形小凸起画在包地段上，包地线不跟着绕。</p>
{sec('s3')}
<h2>四、差分对的等长：拟定的数值（请确认）</h2>
<p>两样东西管两件事：小耳朵补对内的差（只动短的那根）；整对一起绕补这一对相对别的线的长度（两根同进同出，对内差不变）。整对一起绕用和普通线一样的圆弧；小耳朵是圆角矩形。</p>
<div class="wide"><table><tr><th>项</th><th>对内补偿（小耳朵）</th><th>整对一起绕</th><th>依据</th></tr>
<tr><td>形状</td><td>圆角矩形的小耳朵：圆角上去、平顶、圆角下来</td><td>和普通线的蛇形一样：腿垂直、半圆封顶，P、N 是同心圆弧</td><td>RTE-7；用户 2026-11-27</td></tr>
<tr><td>高度（摆幅）</td><td>上限 {EAR_MAX:.2f} mm；同一对里等高，高度按要补的量反算</td><td>起点 {PAIR_PITCH}（一个完整弯的最小值），上限 {PAIR_AMP_MAX} mm；同一块等高</td><td>官方板的小凸起高 0.152；普通线起始摆幅 0.5</td></tr>
<tr><td>半径</td><td>高度的一半（≤ 0.10 mm）</td><td>中心线 {PAIR_PITCH / 2:.3f}（腿中心距的一半）；里面那根 {PAIR_PITCH / 2 - CC / 2:.3f}</td><td>RTE-7</td></tr>
<tr><td>间距</td><td>3W：同一个耳朵的两条腿之间、相邻耳朵的腿之间，边到边 ≥ 0.312（3 × 0.104），所以平顶和耳朵之间的直线各约 0.24；对内间隙最大到 0.15 + 高度（≤ 0.35）</td><td>腿中心距 {PAIR_PITCH}：相邻两条腿之间，对的外边到外边 {LEG_GAP:.2f}（3 倍线宽）</td><td>接口档：CLK、DQS 的蛇形腿距 3 倍线宽</td></tr>
<tr><td>到邻线</td><td colspan="2">弯顶到别的信号 ≥ 0.45 mm（3 倍线宽）</td><td>接口档</td></tr>
<tr><td>位置</td><td>外圈球那根（短的）上，向外凸；从 SoC 规则区内的展开段排起，排不下的顺着伸到直线段</td><td>规则区外的直线段上；或颗粒下面的内层、背面</td><td>RTE-16；RTE-7</td></tr>
<tr><td>区域的形状</td><td>不单独划区域：一串耳朵贴着线，长度 ≈ 个数 × 0.83 − 0.24</td><td>矩形，贴在直线段空的一侧：长 = 个数 × 2 × 腿中心距 + 两头各 {END_STRAIGHT} 直线，深 = 摆幅 + {LEG_GAP:.2f}；里面不放别的线和过孔</td><td>RTE-2、RTE-7</td></tr>
<tr><td>补多少</td><td>每个 1.142 × 高度（高 0.20 时 0.228 mm）</td><td>每个弯 2a − 0.858p（最小的完整弯 {2 * PAIR_PITCH - (4 - math.pi) * PAIR_PITCH:.2f} mm）；要补的不到一个完整弯时画一个矮的小弯</td><td>RTE-2 的公式</td></tr>
<tr><td>包地</td><td colspan="2">弯的一侧地铜窄于 0.30 mm 时铺铜进不去，这一段单侧没有包地，逐处报长度；包地不跟着绕</td><td>官方板的做法</td></tr>
</table></div>
<p>内层（L4）的差分对是 0.103 / 0.20，对宽 0.406，腿中心距同样取 {PAIR_PITCH}（3 倍 L4 线宽是 0.40）。</p>
{sec('s4')}
"""
    out = HERE / "diffpair_variants.html"
    out.write_text(head + html + "</html>", encoding="utf-8")
    if os.environ.get("PAGE_OUT"):      # body-only copy for publishing as a page
        Path(os.environ["PAGE_OUT"]).write_text(html, encoding="utf-8")
    for row in log:
        print(row)
    print("need", {k: round(v, 3) for k, v in need.items()})
    print(out)


if __name__ == "__main__":
    main()
