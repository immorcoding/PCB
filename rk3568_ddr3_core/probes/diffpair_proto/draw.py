"""PROTOTYPE (issue 37, throwaway): what a differential pair should look like.

    python rk3568_ddr3_core/probes/diffpair_proto/draw.py

Writes diffpair_variants.html next to this file and prints the numbers.
Three scenes, three variants each, drawn to scale (mm) from the real DQS0 balls of the RK3568
(G1 / G2, west edge; drawn with "out of the package" pointing right). Nothing here went through
KiCad DRC; clearances are checked numerically by this script (sampled, 0.01 mm steps).
"""
import json, math, re
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
        self.tracks, self.rounds, self.guides, self.texts, self.pour = [], [], [], [], None

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
        for net, pts, w, cls in sc.tracks:
            if cls == "l6" or cls == "l6n":
                continue
            p = " ".join(f"{x * s:.1f},{y * s:.1f}" for x, y in pts)
            o.append(f'<polyline points="{p}" fill="none" stroke="#10161c" stroke-width="{(w + 2 * POUR_CLR) * s:.1f}" stroke-linejoin="round" stroke-linecap="round"/>')
        for net, x, y, d, lab, cls, drill in sc.rounds:
            if net != "GND":
                o.append(f'<circle cx="{x * s:.1f}" cy="{y * s:.1f}" r="{(d / 2 + POUR_CLR) * s:.1f}" fill="#10161c"/>')
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


def exit_base(dq0=None):
    sc = Scene(-1.6, XEND + 0.1, -1.75, 1.75, 190)
    for (ring, row), (ball, net) in BALLS.items():
        cls = "gnd" if net == "GND" else "p" if net.endswith("P") else "n" if net.endswith("N") else "dq"
        sc.pad(net if net != "GND" else "GND", -ring * P, row * P, PAD, ball, cls)
    sc.guide(0.725, "封装边")
    sc.guide(RULE_EDGE, "规则区边")
    sc.track("DQ1", [(0, -2 * P), (XEND, -2 * P)], W_IN, "dq")
    sc.track("DQ4", [(0, 2 * P), (XEND, 2 * P)], W_IN, "dq")
    sc.track("DQ6", [(0, P), (XEND, P)], W_IN, "dq")
    sc.track("DQ2", [(-P, -2 * P), (-P / 2, -1.5 * P), (XEND, -1.5 * P)], W_IN, "dq")
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


def change(kind):
    L = 3.0
    sc = Scene(-L, L, -2.3, 2.3, 130)
    sc.pour = (-L, L)
    vy = 0.4
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
    sc = exit_base(dq0)
    H, e = ear(off, need)
    sc.track("DQS0P", [(0, 0), (off, off)] + e + [(XEND, off)], W_IN, "p")
    sc.track("DQS0N", [(-P, 0), (-P / 2, P / 2), (XEND, P / 2)], W_IN, "n")
    return sc, H

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
         "差分对的中心线落在球行上（和两边的 DQ 对称）。两根各拐一次 45°，在球区外约 0.5 mm 处合并；外圈球那根离 DQ0 的线更近。"),
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
    # ---- scene 3
    rows3 = []
    for key, title, note in (
        ("A", "3A 梯形小凸起（45° 斜边，高 0.30）", "AD 里常见的画法。顶边是直线：KiCad 的间隙规则如果写了上限，每个凸起都会报间隙越界，所以间隙规则不能写上限。"),
        ("B", "3B 半圆小凸起（半径 0.30）", "同样的高度，每个凸起补得更多，占的长度约一半。KiCad 不报间隙越界，整段弧算作非耦合长度。底部和直线相接处是直角，正式做时加小圆角。"),
    ):
        sc, st = bumps(key, worst)
        clr, what = min_clearance(sc)
        cnt = " / ".join(str(max(1, round(need[nm] / st["per"]))) for nm, *_ in pairs)
        rows3.append(f"<tr><td>{key}</td><td>规则区外第一段直线</td><td>{st['per']:.3f}</td><td>{st['n']}（{cnt}）</td><td>{st['span']:.2f}</td><td>{st['gap_max']:.2f}</td>"
                     f"<td>{st['to_nb']:.2f}</td><td>{st['cu']:.2f}，铺铜进不去</td><td>{clr:.3f}（{what}）</td></tr>")
        log.append(("bump", key, {k: round(v, 3) for k, v in st.items()}, round(clr, 4), what))
        blocks.append(("s3", f"<h3>{title}</h3><p>{note}</p>{svg(sc)}"))
    sc, H = bump_C(worst)
    clr, what = min_clearance(sc)
    hs = " / ".join(f"{(need[nm] + (8 - 4 * SQ2) * 0.1) / 2:.2f}" for nm, *_ in pairs)
    rows3.append(f"<tr><td>C</td><td>规则区内，出球后的展开段</td><td>{worst:.3f}</td><td>1（各 1）</td><td>0.70</td><td>{P / 2 - W_IN + H:.2f}（规则区内）</td>"
                 f"<td>不占包地段</td><td>不影响</td><td>{clr:.3f}（{what}）</td></tr>")
    log.append(("bump", "C", {"H": round(H, 3)}, round(clr, 4), what))
    blocks.append(("s3", f"<h3>3C 一个“耳朵”，藏在规则区内的展开段里</h3><p>出球区后邻线本来就要向两边展开（给 DQS 让出 0.70 的包地间隙），外圈球那根在这块空里绕一个 U 形，一次补完。"
                         f"图里补 {worst:.2f} mm，耳朵高 {H:.2f} mm；五对的高度依次是 {hs} mm。出规则区以后差分对是纯直线，包地不受影响。"
                         f"这和 RTE-16 现在写的“出规则区后的第一段直线”不同，选它要改那句话。</p>{svg(sc)}"))

    def sec(tag):
        return "".join(b for t, b in blocks if t == tag)

    html = f"""<!doctype html><html lang="zh"><meta charset="utf-8"><title>原型：差分对的样子（issue 37）</title>
<style>body{{font:15px/1.65 system-ui,"Microsoft YaHei",sans-serif;max-width:1040px;margin:24px auto;padding:0 16px;color:#1c2630;background:#fff}}
table{{border-collapse:collapse;margin:10px 0}}td,th{{border:1px solid #b8c2cc;padding:4px 9px;text-align:right;font-size:14px}}td:first-child,th:first-child{{text-align:center}}
h2{{margin-top:44px;border-top:2px solid #1c2630;padding-top:14px}}h3{{margin-top:30px}}
.k span{{display:inline-block;width:26px;height:6px;margin:0 6px 2px 14px}}.rec{{background:#eef6ea;border-left:4px solid #5a9a48;padding:8px 12px}}</style>
<h1>原型（用完即弃）：差分对画成什么样</h1>
<p>三件事各出三种画法，请各选一个（或说哪里要改）。全部按比例画，单位 mm，数字由脚本算。
对象是 RK3568 的 DQS0（G1 / G2，西边），图里“出封装”的方向朝右；其余四对（DQS1–3、CLK）在球阵上的姿势相同。
没有过 KiCad 的 DRC；“最小间距”是脚本按 0.01 mm 取样算的铜到铜距离。</p>
<p class="k"><span style="background:{COL['p']}"></span>外圈球那根（短）<span style="background:{COL['n']}"></span>内圈球那根（长）<span style="background:{COL['dq']}"></span>旁边的 DQ
<span style="background:{COL['l6']}"></span>L6 上的线<span style="background:#1f5f7d;height:12px"></span>L1 地铺铜<span style="background:#3fa7d6;height:12px;width:12px;border-radius:6px"></span>地球 / 地过孔</p>

<h2>先看一个事实：五对差分线都是“一前一后”出球，外圈球那根天生短</h2>
<p>RK3568 的五对（DQS0–3、CLK）都在最外两圈，P、N 在同一行里一前一后垂直于封装边。两个焊盘之间（空隙 0.35 mm）只过得了一根线，
所以内圈球那根必须从外圈球旁边的通道绕出去，板上多走约 {board['A']:.2f} mm；再加上封装内引线的差，外圈球那根要补的长度如下（对内工作目标 0.15 mm，上限 0.30 mm）：</p>
<table><tr><th>对</th><th>外圈球</th><th>内圈球</th><th>封装内：内 − 外</th><th>板上：内 − 外（画法 1A）</th><th>外圈球那根要补</th></tr>{rowsP}</table>
<p>颗粒那一头怎么进球区取决于颗粒的扇出，这里没有画。</p>

<h2>一、成对出 SoC 球区（L1）</h2>
<table><tr><th>画法</th><th>从外圈球中心起多远开始按 0.15 间隙并行</th><th>板上长度差（内 − 外）</th><th>两根线的拐点数</th><th>最小间距（规则区内下限 0.09）</th></tr>{''.join(rows1)}</table>
<p>地球（F1、H2 等）的过孔没有画，扇出工具要让它们避开这两条通道。旁边的 DQ 只画了直出的一段。</p>
<p class="rec">我的推荐：1A。并行得最早、拐点最少；代价是外圈球那根在盘内偏心 0.071 mm 出盘（KiCad 算长度时按盘心到出盘点的直线折算，实测过）。</p>
{sec('s1')}

<h2>二、换层：过孔对和地过孔（L1 → L6，规则区外）</h2>
<p>已定的数：过孔 0.4 / 0.2，两个信号过孔中心距 ≥ 0.8；地过孔离信号过孔中心 ≤ 0.635（这里取 0.60，盘边到盘边 0.20）；
差分对两侧是 0.70 的包地间隙（铜条中心线离对的中心 {STRIP:.3f}），再外面是 DQ。邻线画成直通；整个字节组一起换层时 DQ 的过孔怎么排是另一件事，这里不定。</p>
<table><tr><th>画法</th><th>贴身的地过孔数</th><th>地过孔到信号过孔中心</th><th>过孔占的总宽</th><th>邻线每侧让出</th><th>每层张开段（非耦合）</th><th>最小间距（下限 0.15）</th></tr>{''.join(rows2)}</table>
<p class="rec">我的推荐：2B，要更稳妥就 2C。两者都不让线带变宽；2A 每侧要鼓出约 0.5 mm，一个字节组里换层的地方会鼓成一个包。</p>
{sec('s2')}

<h2>三、对内补偿</h2>
<p>补在外圈球那根（短的）上，只能向外凸。图里按最大的一对补 {worst:.2f} mm。表里“个数”括号内依次是 DQS0 / DQS1 / DQS2 / DQS3 / CLK 各要几个。</p>
<table><tr><th>画法</th><th>位置</th><th>每个补</th><th>个数</th><th>占的长度</th><th>对内最大间隙</th><th>凸起顶到邻线（要求 ≥ 0.45）</th><th>凸起一侧剩的地铜宽（最小 0.30）</th><th>最小间距</th></tr>{''.join(rows3)}</table>
<p>3A、3B 的凸起会把那一侧 0.70 的包地间隙吃掉 0.30：凸起这一段那一侧没有地铜，到邻线也只有 0.40。要保住包地，邻线得在这一段整体外移 0.30（线带变宽）。
规则区外能用的直线段大约只有 3.5 mm（两个球区相距 7.5 mm，减去两头的规则区）。</p>
<p class="rec">我的推荐：3C，不够的零头再用 3B。要补的量是 0.4–1.0 mm，放在包地的直线段上代价大；放在规则区内的展开段里，一个耳朵就补完，包地段保持直线。</p>
{sec('s3')}
</html>"""
    out = HERE / "diffpair_variants.html"
    out.write_text(html, encoding="utf-8")
    for row in log:
        print(row)
    print("need", {k: round(v, 3) for k, v in need.items()})
    print(out)


if __name__ == "__main__":
    main()
