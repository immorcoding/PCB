"""PROTOTYPE (throwaway): what the T-branch via array looks like (issue 59).

    python rk3568_ddr3_core/probes/tee_array_proto/draw.py

Writes tee_array_variants.html and metrics.json next to this file.
Real ball positions and the placement chosen on issue 34. Lengths are octilinear estimates (obstacles ignored).
Nothing went through DRC. The trunk order at the SoC is assumed (west to east along the north edge) until the
fan-out exists.
"""
import json
import math
import statistics as st
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "placement_proto"))
import draw as P  # noqa: E402

NETS = list(P.AC)
TIGHT = ("CKE", "CS0n", "ODT0")
CK = ("CLKP", "CLKN")
SOC_RULE = P.SOC_HALF + P.MARGIN            # 10.5
VIA_R, EDGE = 0.2, 0.15                     # via pad radius, pad edge to a rule-area edge
M = VIA_R + EDGE
SIG_SIG, PAIR, GND_MIN, GND_MAX = 0.8, 0.70, 0.60, 0.635
BRANCH_MAX = 15.24
LIMIT = -32.0                                # no board outline yet
START = (-SOC_RULE - M, -SOC_RULE - M)       # (-10.85, -10.85), the free point nearest the SoC corner
TRK, CLR = 0.134, 0.10                    # L4 track width, clearance used inside the band (assumption)
TRUNK_PITCH = 0.45                        # outer-layer trunk 0.15 wide, 2W edge to edge
N_REG, SPARE = len(NETS) - 2, 4
ENTRY_S = 1.4                             # where the trunks reach the band


def setup(slide):
    """Placement of issue 34 (L shape, 7.5 mm gap) with both chips slid along their edges by `slide` mm away from the corner."""
    global V, S, A, B, RING, TRUNK_LAYER, ROT_C, BODY, RULE, NECK_X, AXIS, SEG0, SLIDE, GATE, DATA
    SLIDE = slide
    V = P.l_variant("x", "x", "x", 7.5, -slide, [])
    S = {n: V.soc[P.SOC[n]] for n in NETS}
    A = {n: V.chip("A", P.AC[n]) for n in NETS}
    B = {n: V.chip("B", P.AC[n]) for n in NETS}
    RING = {n: round((P.SOC_FIELD - max(abs(S[n][0]), abs(S[n][1]))) / 0.65) + 1 for n in NETS}
    TRUNK_LAYER = {n: "L1" if RING[n] <= 2 else "L6" for n in NETS}   # assumption: inner balls drop to L6, not L4
    pa, pb = np.array([A[n] for n in NETS]), np.array([B[n] for n in NETS])
    R = np.array([[0.0, 1.0], [-1.0, 0.0]])                          # chip B is chip A turned 90 degrees about ROT_C
    ROT_C = tuple(np.linalg.solve(np.eye(2) - R, (pb - pa @ R.T).T).T.mean(axis=0))
    BODY = {c: (min(p[0] for p in V.polys()[c]), min(p[1] for p in V.polys()[c]),
                max(p[0] for p in V.polys()[c]), max(p[1] for p in V.polys()[c])) for c in "AB"}
    RULE = {c: (b[0] - P.MARGIN, b[1] - P.MARGIN, b[2] + P.MARGIN, b[3] + P.MARGIN) for c, b in BODY.items()}
    GATE = math.dist((BODY["A"][2], BODY["A"][1]), (BODY["B"][0], BODY["B"][3]))     # between the two body corners
    if RULE["A"][1] - M < RULE["B"][3] + M:        # the two rule areas overlap in y: a passage, go north through it first
        NECK_X = (RULE["A"][2] + M + RULE["B"][0] - M) / 2
        AXIS = [(NECK_X, START[1]), (NECK_X, RULE["A"][1] - M)]
    else:                                           # open corner: straight down the diagonal
        NECK_X = START[0]
        AXIS = [START, START]
    AXIS.append((AXIS[1][0] - 14.0, AXIS[1][1] - 14.0))
    SEG0 = AXIS[0][1] - AXIS[1][1]
    m = V.analyse()
    DATA = {b["byte"]: (b["pcb_med"], b["pcb_max"]) for b in m["bytes"]}


def in_rect(p, r, g=0.0):
    return r[0] - g < p[0] < r[2] + g and r[1] - g < p[1] < r[3] + g


def free(p, g=M):
    """Via centre allowed: in the corner quadrant, outside every rule area by pad radius + 0.15."""
    if p[0] > -SOC_RULE - g + 1e-9 or p[1] > -SOC_RULE - g + 1e-9:
        return False
    if p[0] < LIMIT or p[1] < LIMIT:
        return False
    return not any(in_rect(p, RULE[c], g - 1e-9) for c in "AB")


def octd(a, b):
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)


def pt(s, lat):
    """Point at distance s along the axis, lat to the right (east, then north-east)."""
    if s <= SEG0:
        base, d = (NECK_X, START[1] - s), (0.0, -1.0)
    else:
        t = (s - SEG0) / math.sqrt(2)
        base, d = (AXIS[1][0] - t, AXIS[1][1] - t), (-math.sqrt(0.5), -math.sqrt(0.5))
    return (round(base[0] - lat * d[1], 4), round(base[1] + lat * d[0], 4))


def axis_s(p):
    """s of the axis point nearest p (for the equal-length centre)."""
    return min((math.dist(p, pt(k * 0.05, 0)), k * 0.05) for k in range(0, 400))[1]


# ---- band patterns ---------------------------------------------------------
def two_row(p, h, g_every):
    def gen(k, s):
        sig = (s, -h if k % 2 == 0 else h)
        g = [(s + p / 4, 0.0)] if k % 2 == 0 and (k // 2) % g_every == 0 else []
        return sig, g
    return gen, p / 2


def four_row(h1, h2, step, go):
    def gen(k, s):
        sig = (s, (-h1, h1, -h2, h2)[k % 4])
        g = {0: [(s + step / 2, 0.0)], 2: [(s, -h2 - go)], 3: [(s, h2 + go)]}.get(k % 4, [])
        return sig, g
    return gen, step


def make_band(gen, step, s_start):
    sig, gnd, k = [], [], 0
    ck = [pt(s_start - 0.8, -PAIR / 2), pt(s_start - 0.8, PAIR / 2)]
    rc = [pt(s_start - 0.8 - 0.3, -0.65), pt(s_start - 0.8 - 0.3, 0.65), pt(s_start - 0.8 - 2.05, 0.65), pt(s_start - 0.8 - 2.05, -0.65)]
    dropped = 0
    while len(sig) < N_REG + SPARE and k < 400:
        s = s_start + k * step
        (ss, lat), gs = gen(k, s)
        p = pt(ss, lat)
        if free(p) and all(math.dist(p, q["p"]) >= SIG_SIG - 1e-6 for q in sig) and all(math.dist(p, q) >= SIG_SIG - 1e-6 for q in ck) \
                and all(math.dist(p, g) >= GND_MIN - 1e-6 for g in gnd):
            sig.append({"p": p, "s": ss, "lat": lat, "side": "W" if lat < 0 else "E"})
            for gs_, gl in gs:
                g = pt(gs_, gl)
                if free(g) and all(math.dist(g, q["p"]) >= GND_MIN - 1e-6 for q in sig) and all(math.dist(g, q) >= GND_MIN - 1e-6 for q in gnd + ck):
                    gnd.append(g)
        else:
            dropped += 1
        k += 1
    for lat in (-PAIR / 2 - 0.61, PAIR / 2 + 0.61):       # one ground via outside each CK via
        gck = pt(s_start - 0.8, lat)
        if free(gck) and all(math.dist(gck, q["p"]) >= GND_MIN - 1e-6 for q in sig) and all(math.dist(gck, q) >= GND_MIN - 1e-6 for q in gnd):
            gnd.append(gck)
    return sig, gnd, ck, rc, dropped


# ---- assignment ------------------------------------------------------------
def lens(n, pos):
    p = pos["p"]
    trunk = octd(S[n], pt(ENTRY_S, 1.0)) + abs(pos["s"] - ENTRY_S) + abs(pos["lat"]) + (1.0 if pos["side"] == "W" else 0.0)
    return trunk, octd(p, A[n]), octd(p, B[n])


def cost(n, pos):
    t, a, b = lens(n, pos)
    if max(a, b) > BRANCH_MAX:
        return 1e5
    return (10 if n in TIGHT else 1) * abs(a - b) + 0.05 * (t + a + b)


def merge(seq1, seq2, poss):
    """Place two ordered lists of nets on ordered positions (positions may be skipped); least cost."""
    n1, n2, q = len(seq1), len(seq2), len(poss)
    INF = float("inf")
    dp = [[[INF] * (n2 + 1) for _ in range(n1 + 1)] for _ in range(q + 1)]
    back = {}
    dp[0][0][0] = 0.0
    for k in range(q):
        for i in range(n1 + 1):
            for j in range(n2 + 1):
                c = dp[k][i][j]
                if c == INF:
                    continue
                for di, dj, net in ((0, 0, None), (1, 0, seq1[i] if i < n1 else None), (0, 1, seq2[j] if j < n2 else None)):
                    if (di or dj) and net is None:
                        continue
                    v = c + (cost(net, poss[k]) if net else 0.0)
                    if v < dp[k + 1][i + di][j + dj]:
                        dp[k + 1][i + di][j + dj] = v
                        back[(k + 1, i + di, j + dj)] = (i, j, net)
    if dp[q][n1][n2] == INF:
        return INF, {}
    out, i, j = {}, n1, n2
    for k in range(q, 0, -1):
        pi, pj, net = back[(k, i, j)]
        if net:
            out[net] = poss[k - 1]
        i, j = pi, pj
    return dp[q][n1][n2], out


def exit_order(layer):
    """Trunk order where the lines leave the SoC's north edge: west to east (ties: outer ring first)."""
    return sorted((n for n in NETS if TRUNK_LAYER[n] == layer and n not in CK), key=lambda n: (round(S[n][0], 2), RING[n]))


def assign(sig):
    W = sorted((q for q in sig if q["side"] == "W"), key=lambda q: q["s"])
    E = sorted((q for q in sig if q["side"] == "E"), key=lambda q: q["s"])
    l1, l6 = exit_order("L1"), exit_order("L6")
    ckx = S["CLKP"][0]
    l1w = [n for n in l1 if S[n][0] < ckx][::-1]      # west of CK: go round the head, nearest the band first
    l1e = [n for n in l1 if S[n][0] >= ckx]
    best = None
    for k6 in range(len(l6) + 1):
        cw, aw = merge(l1w, l6[:k6][::-1], W)
        ce, ae = merge(l1e, l6[k6:], E)
        if best is None or cw + ce < best[0]:
            best = (cw + ce, {**aw, **ae}, k6)
    cm = np.array([[cost(n, q) for q in sig] for n in l1 + l6])
    r, c = linear_sum_assignment(cm)
    plain = {(l1 + l6)[i]: sig[j] for i, j in zip(r, c)}
    return best[1], plain, best[2], best[0] < 1e5


def build(key, title, blurb, slide, gen_step, s_start, notes, per_period, fix=True):
    setup(slide)
    if s_start is None:                      # centre the band on the equal-length centre
        s_start = max(3.2, round(axis_s(ROT_C) - (N_REG * gen_step[1]) / 2, 1))
    sig, gnd, ck, rc, dropped = make_band(*gen_step, s_start)
    if fix:                                  # every signal via gets a ground via within GND_MAX where one fits
        allsig = [q["p"] for q in sig] + ck
        for q in sorted(sig, key=lambda q: q["s"]):
            if min(math.dist(q["p"], g) for g in gnd) <= GND_MAX + 1e-6:
                continue
            opts = []
            for k in range(72):
                g = (round(q["p"][0] + 0.61 * math.cos(k * math.pi / 36), 4), round(q["p"][1] + 0.61 * math.sin(k * math.pi / 36), 4))
                if free(g) and all(math.dist(g, p) >= GND_MIN - 1e-6 for p in allsig) and all(math.dist(g, h) >= GND_MIN - 1e-6 for h in gnd):
                    opts.append((-sum(1 for p in allsig if math.dist(g, p) <= GND_MAX + 1e-6), round(math.dist(g, pt(q["s"], 0)), 3), g))
            if opts:
                gnd.append(min(opts)[2])
    asg, plain, k6, feasible = assign(sig)
    asg.update({"CLKP": {"p": ck[0], "s": s_start - 0.8, "lat": -PAIR / 2, "side": "W"},
                "CLKN": {"p": ck[1], "s": s_start - 0.8, "lat": PAIR / 2, "side": "E"}})
    rows = []
    for n in NETS:
        t, a, b = lens(n, asg[n])
        rows.append({"net": n, "via": asg[n]["p"], "s": asg[n]["s"], "side": asg[n]["side"], "trunk_layer": TRUNK_LAYER[n],
                     "trunk": t, "a": a, "b": b, "mis": abs(a - b)})
    used = [r["via"] for r in rows]
    nn = [min(math.dist(p, q) for q in used if q != p) for p in used]
    near = [min(math.dist(p, g) for g in gnd) for p in used]
    pm = [abs(lens(n, plain[n])[1] - lens(n, plain[n])[2]) for n in plain]
    allp = used + gnd
    gate_s = axis_s(((BODY["A"][2] + BODY["B"][0]) / 2, (BODY["A"][1] + BODY["B"][3]) / 2))     # where the axis passes between the body corners
    past = {L: sum(1 for r in rows if r["trunk_layer"] == L and r["s"] > gate_s) for L in ("L1", "L6")}
    width_at_neck = max((abs(q["lat"]) for q in sig if abs(q["s"] - gate_s) <= 1.0), default=0) * 2 + 0.4
    return {"key": key, "title": title, "blurb": blurb, "notes": notes, "feasible": feasible, "k6": k6, "dropped": dropped,
            "spare": len(sig) - N_REG, "nn_min": min(nn), "nn_med": st.median(nn),
            "gnd": len(gnd), "gnd_over": sum(1 for d in near if d > GND_MAX + 1e-6), "gnd_near": [min(near), st.median(near), max(near)],
            "s_range": [min(r["s"] for r in rows), max(r["s"] for r in rows)], "len": max(r["s"] for r in rows) - min(r["s"] for r in rows),
            "width": max(abs(q["lat"]) for q in sig) * 2 + 0.4, "reach": [min(p[0] for p in allp) - 0.2, min(p[1] for p in allp) - 0.2],
            "trunk": [min(r["trunk"] for r in rows), st.median(r["trunk"] for r in rows), max(r["trunk"] for r in rows)],
            "branch": [st.median(max(r["a"], r["b"]) for r in rows), max(max(r["a"], r["b"]) for r in rows)],
            "over": sum(max(r["a"], r["b"]) > BRANCH_MAX for r in rows),
            "mis_tight": {r["net"]: r["mis"] for r in rows if r["net"] in TIGHT}, "mis_ck": [r["mis"] for r in rows if r["net"] in CK],
            "mis_med": st.median(r["mis"] for r in rows), "mis_max": max(r["mis"] for r in rows),
            "mis_plain_med": st.median(pm), "mis_plain_max": max(pm),
            "past_neck": past, "neck_need": {L: past[L] * TRUNK_PITCH + width_at_neck for L in past}, "passage": GATE,
            "slide": SLIDE, "rot_c": ROT_C, "centre_s": axis_s(ROT_C), "data": DATA,
            "per_period": per_period, "rows": rows, "gnds": gnd, "rc": rc, "unused": [q["p"] for q in sig if q["p"] not in used]}


# ---- drawing ---------------------------------------------------------------
SC = 30
WIN = (-27.5, -27.5, -1.6, -4.4)
COL = {"bg": "#0f1a18", "L1": "#e0564f", "L6": "#5b93e6", "L4": "#58c38a", "ck": "#f2b134", "gnd": "#7fd6c8", "via": "#f4f1e8",
       "rule": "#3b4a47", "body": "#22302d", "txt": "#c9d6d2", "ball": "#6d7c78"}
SHORT = {"RESETn": "RST", "CLKP": "CK+", "CLKN": "CK-", "CS0n": "CS", "ODT0": "ODT", "RASn": "RAS", "CASn": "CAS", "WEn": "WE"}


def svg(m):
    setup(m["slide"])
    X = lambda x: (x - WIN[0]) * SC
    Y = lambda y: (y - WIN[1]) * SC
    o = [f'<svg viewBox="0 0 {(WIN[2] - WIN[0]) * SC:.0f} {(WIN[3] - WIN[1]) * SC:.0f}" role="img" aria-label="{m["title"]}" '
         f'xmlns="http://www.w3.org/2000/svg" style="width:100%;background:{COL["bg"]}" font-family="Consolas,monospace">']

    def rect(r, **kw):
        a = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in kw.items())
        o.append(f'<rect x="{X(r[0]):.1f}" y="{Y(r[1]):.1f}" width="{(r[2] - r[0]) * SC:.1f}" height="{(r[3] - r[1]) * SC:.1f}" {a}/>')
    rect((-SOC_RULE, -SOC_RULE, 0, 0), fill="none", stroke=COL["rule"], stroke_dasharray="6 4")
    rect((-P.SOC_HALF, -P.SOC_HALF, 0, 0), fill=COL["body"], stroke="none")
    for c in "AB":
        rect(RULE[c], fill="none", stroke=COL["rule"], stroke_dasharray="6 4")
        rect(BODY[c], fill=COL["body"], stroke="none")
    for b, xy in V.soc.items():
        if WIN[0] < xy[0] < WIN[2] and WIN[1] < xy[1] < WIN[3]:
            o.append(f'<circle cx="{X(xy[0]):.1f}" cy="{Y(xy[1]):.1f}" r="{0.15 * SC:.1f}" fill="none" stroke="{COL["ball"]}" stroke-width="0.6"/>')
    for c in "AB":
        for ball, fn, x, y in P.DDR_ALL:
            p = V.chip_pt(c, (x, y))
            if WIN[0] < p[0] < WIN[2] and WIN[1] < p[1] < WIN[3]:
                o.append(f'<circle cx="{X(p[0]):.1f}" cy="{Y(p[1]):.1f}" r="{0.19 * SC:.1f}" fill="none" stroke="{COL["ball"]}" stroke-width="0.6"/>')
    o.append(f'<path d="M{X(ROT_C[0]) - 7:.1f},{Y(ROT_C[1]):.1f}h14M{X(ROT_C[0]):.1f},{Y(ROT_C[1]) - 7:.1f}v14" stroke="{COL["txt"]}" stroke-width="1.2"/>')
    o.append(f'<text x="{X(ROT_C[0]) - 10:.1f}" y="{Y(ROT_C[1]) + 4:.1f}" fill="{COL["txt"]}" font-size="11" text-anchor="end">等长中心</text>')
    for r in m["rows"]:
        n, s = r["net"], r["via"]
        col = COL["ck"] if n in CK else COL["L4"]
        for t in (A[n], B[n]):
            o.append(f'<line x1="{X(s[0]):.1f}" y1="{Y(s[1]):.1f}" x2="{X(t[0]):.1f}" y2="{Y(t[1]):.1f}" stroke="{col}" stroke-width="0.9" opacity="0.5"/>')
            o.append(f'<circle cx="{X(t[0]):.1f}" cy="{Y(t[1]):.1f}" r="{0.19 * SC:.1f}" fill="{col}" opacity="0.5"/>')
        o.append(f'<circle cx="{X(S[n][0]):.1f}" cy="{Y(S[n][1]):.1f}" r="{0.15 * SC:.1f}" fill="{COL[r["trunk_layer"]]}" opacity="0.85"/>')
    if m["rc"]:
        o.append(f'<polygon points="{" ".join(f"{X(p[0]):.1f},{Y(p[1]):.1f}" for p in m["rc"])}" fill="{COL["L6"]}" fill-opacity="0.25" stroke="{COL["L6"]}" stroke-dasharray="4 3"/>')
        c = (sum(p[0] for p in m["rc"]) / 4, sum(p[1] for p in m["rc"]) / 4)
        o.append(f'<text x="{X(c[0]):.1f}" y="{Y(c[1]) + 4:.1f}" fill="{COL["txt"]}" font-size="10" text-anchor="middle">RC</text>')
    for p in m["unused"]:
        o.append(f'<circle cx="{X(p[0]):.1f}" cy="{Y(p[1]):.1f}" r="{VIA_R * SC:.1f}" fill="none" stroke="{COL["via"]}" stroke-width="0.8" stroke-dasharray="2 2"/>')
    for g in m["gnds"]:
        o.append(f'<circle cx="{X(g[0]):.1f}" cy="{Y(g[1]):.1f}" r="{VIA_R * SC:.1f}" fill="{COL["gnd"]}"/>')
    for r in m["rows"]:
        n, s = r["net"], r["via"]
        fill = COL["ck"] if n in CK else COL["via"]
        o.append(f'<circle cx="{X(s[0]):.1f}" cy="{Y(s[1]):.1f}" r="{VIA_R * SC:.1f}" fill="{fill}" stroke="{COL[r["trunk_layer"]]}" stroke-width="1.6"/>')
        dx = -1 if r["side"] == "W" else 1
        if n in CK or r["s"] > SEG0:
            lx, ly, anc = X(s[0]), Y(s[1]) + (11 if dx > 0 else -6), "middle"
            if n in CK:
                lx, ly, anc = X(s[0]) + dx * 9, Y(s[1]) + 3, ("end" if dx < 0 else "start")
        else:
            lx, ly, anc = X(s[0]) + dx * 9, Y(s[1]) + 3, ("end" if dx < 0 else "start")
        o.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="{COL["ck"] if n in CK or n in TIGHT else COL["txt"]}" font-size="8" text-anchor="{anc}">{SHORT.get(n, n)}</text>')
    for txt, p in (("RK3568", (-6.5, -6.0)), ("颗粒 A 地址端", (-19.5, -5.2)), ("颗粒 B 地址端", (-6.5, -24.6)), ("A1 角", (-9.0, -9.0))):
        o.append(f'<text x="{X(p[0]):.1f}" y="{Y(p[1]):.1f}" fill="{COL["txt"]}" font-size="13" text-anchor="middle">{txt}</text>')
    o.append(f'<line x1="{X(-27):.1f}" y1="{Y(-5):.1f}" x2="{X(-26):.1f}" y2="{Y(-5):.1f}" stroke="{COL["txt"]}" stroke-width="2"/>'
             f'<text x="{X(-26.5):.1f}" y="{Y(-5) - 6:.1f}" fill="{COL["txt"]}" font-size="11" text-anchor="middle">1 mm</text>')
    o.append("</svg>")
    return "\n".join(o)


def evb1_block():
    f = HERE / "evb1_tee.json"
    if not f.exists():
        return "<p>没有 EVB1 的数据文件。</p>"
    d = json.loads(f.read_text(encoding="utf-8"))
    a = d["array"]
    vias = a["window_vias"]
    tee = {k: v["branch"]["pos_board"] for k, v in d["nets"].items() if isinstance(v.get("branch"), dict) and v["branch"].get("kind") == "via"}
    x0, y0 = min(v["x"] for v in vias) - 0.6, min(v["y"] for v in vias) - 0.6
    x1, y1 = max(v["x"] for v in vias) + 0.6, max(v["y"] for v in vias) + 0.6
    sc = 44
    o = [f'<svg viewBox="0 0 {(x1 - x0) * sc:.0f} {(y1 - y0) * sc:.0f}" role="img" aria-label="EVB1 的分叉过孔带" xmlns="http://www.w3.org/2000/svg" '
         f'style="width:100%;background:{COL["bg"]}" font-family="Consolas,monospace">']
    ay = (a["dram_axis_y_board"] - y0) * sc
    o.append(f'<line x1="0" y1="{ay:.1f}" x2="{(x1 - x0) * sc:.0f}" y2="{ay:.1f}" stroke="{COL["rule"]}" stroke-dasharray="2 5"/>')
    tp = {tuple(round(c, 3) for c in p): k for k, p in tee.items()}
    for v in vias:
        k = tp.get((round(v["x"], 3), round(v["y"], 3)))
        fill = COL["gnd"] if v["gnd"] else (COL["ck"] if k and "CLK" in k else COL["via"] if k else COL["ball"])
        o.append(f'<circle cx="{(v["x"] - x0) * sc:.1f}" cy="{(v["y"] - y0) * sc:.1f}" r="{v["pad"] / 2 * sc:.1f}" fill="{fill}"/>')
        if k:
            o.append(f'<text x="{(v["x"] - x0) * sc:.1f}" y="{(v["y"] - y0) * sc - 11:.1f}" fill="{COL["txt"]}" font-size="8" text-anchor="middle">{k.replace("DDR4_", "")[:6]}</text>')
    o.append(f'<line x1="14" y1="16" x2="{14 + sc}" y2="16" stroke="{COL["txt"]}" stroke-width="2"/><text x="{14 + sc / 2}" y="12" fill="{COL["txt"]}" font-size="11" text-anchor="middle">1 mm</text>')
    o.append("</svg>")
    return "\n".join(o)


def f2(x):
    return f"{x:.2f}"


def page(ms):
    head = (HERE.parent / "via_array_proto" / "page.tmpl.html").read_text(encoding="utf-8").split("<main>")[0].replace("字节组换层过孔阵", "T 型分叉过孔阵")
    rows = []

    def row(label, fn, ref=""):
        rows.append(f'<tr><th>{label}</th>' + "".join(f"<td>{fn(m)}</td>" for m in ms) + f'<td class="l">{ref}</td></tr>')

    def bad(cond, s):
        return f'<span class="bad">{s}</span>' if cond else s
    row("带子：长 × 宽", lambda m: f'{m["len"]:.1f} × {m["width"]:.1f}', "13.1 × 6.3")
    row("带子在轴线上从哪到哪（等长中心的位置）", lambda m: f'{m["s_range"][0]:.1f} 到 {m["s_range"][1]:.1f}（{m["centre_s"]:.1f}）', "")
    row("数据线估算，字节组 0 / 1 / 2 / 3 的中位", lambda m: " / ".join(f'{m["data"][k][0]:.1f}' for k in range(4)), "")
    row("板子要向西、向北伸到（SoC 中心为原点）", lambda m: f'x {m["reach"][0]:.1f}，y {m["reach"][1]:.1f}', "")
    row("信号过孔最近中心距，最小 / 中位", lambda m: f'{f2(m["nn_min"])} / {f2(m["nn_med"])}', "0.55（CK 对）/ 1.02")
    row("地过孔个数（地 : 信号）", lambda m: f'{m["gnd"]}（{m["gnd"] / 27:.2f}）', "29（1.2）")
    row("最近的地过孔，最小 / 中位 / 最大", lambda m: " / ".join(f2(x) for x in m["gnd_near"]), "0.63 / 0.69 / 1.08")
    row("0.635 内没有地过孔的信号过孔", lambda m: bad(m["gnd_over"], f'{m["gnd_over"]} / 27'), "多数超过（中位 0.69）")
    row("轴线上每一格要过的东西（L4）", lambda m: m["per_period"], "")
    row("空位", lambda m: str(m["spare"]), "")
    row("主干估算，最短 / 中位 / 最长", lambda m: " / ".join(f"{x:.1f}" for x in m["trunk"]), "14.1 / 21.8 / 29.9（实走）")
    row("分支（长的一支）估算，中位 / 最长", lambda m: " / ".join(f"{x:.1f}" for x in m["branch"]), "9.9 到 12.4（实走）；CK 14.9 到 15.6")
    row("分支超过 15.24 的网络", lambda m: bad(m["over"], str(m["over"])), "CK 的一支 15.6")
    row("两分支天然差：CKE / CS / ODT", lambda m: " / ".join(f2(m["mis_tight"][k]) for k in TIGHT), "这三根用 0 Ω 分叉")
    row("两分支天然差：CK+ / CK−", lambda m: " / ".join(f2(x) for x in m["mis_ck"]), "")
    row("两分支天然差：全部，中位 / 最大", lambda m: f'{f2(m["mis_med"])} / {f2(m["mis_max"])}', "走完后 0.10 / 0.475")
    row("同上，如果主干的顺序可以随便排", lambda m: f'{f2(m["mis_plain_med"])} / {f2(m["mis_plain_max"])}', "")
    row("两颗颗粒本体的角之间（口子）的宽度", lambda m: f2(m["passage"]), "")
    row("要穿过口子的主干，L1 / L6", lambda m: f'{m["past_neck"]["L1"]} / {m["past_neck"]["L6"]} 根', "")
    row("口子处每层要的宽度（带子 + 主干按 0.45 一根）", lambda m: " / ".join(bad(m["neck_need"][L] > m["passage"], f2(m["neck_need"][L])) for L in ("L1", "L6")), "")
    body = []
    for m in ms:
        body.append(f'<section><h2>{m["title"]}</h2><p>{m["blurb"]}</p>{svg(m)}<ul>{"".join(f"<li>{n}</li>" for n in m["notes"])}</ul></section>')
    th = "".join(f'<th>{m["title"].split("　")[0]}</th>' for m in ms)
    intro = (HERE / "intro.html").read_text(encoding="utf-8") if (HERE / "intro.html").exists() else ""
    outro = (HERE / "outro.html").read_text(encoding="utf-8") if (HERE / "outro.html").exists() else ""
    return (head + "<main>\n" + intro + "\n".join(body)
            + '<h2>三个候选的数</h2><p>长度是 45° / 90° 的最短估算，没有绕障，单位 mm。网络在带子上的先后按主干出 SoC 的顺序排（假设：沿北边从西到东），'
              '这样主干之间不交叉；L4 上的分支按构造不交叉。</p>'
            + f'<div class="scroll"><table><tr><th>项目</th>{th}<th>官方 EVB1（DDR4，实测）</th></tr>' + "\n".join(rows) + "</table></div>"
            + '<h2>官方 EVB1 的分叉过孔带</h2>' + (HERE / "evb1_note.html").read_text(encoding="utf-8") if (HERE / "evb1_note.html").exists() else ""
            ) + evb1_block() + outro + "\n</main>\n"


PATTERNS = {
    "2r08": (lambda: two_row(0.8, 0.6, 2), False, "每 1.6 mm：4 根线 + 1 个地过孔，要 1.44"),
    "2r10": (lambda: two_row(1.0, 0.56, 1), True, "每 1.0 mm：2 根线 + 1 个地过孔，要 0.97"),
    "4r": (lambda: four_row(0.57, 1.32, 0.4, 0.61), True, "每 1.6 mm：4 根线 + 1 个地过孔，要 1.44"),
}


def show(m):
    print(f'\n== {m["title"]}  slide {m["slide"]} feasible {m["feasible"]} k6 {m["k6"]} dropped {m["dropped"]} spare {m["spare"]} centre s {m["centre_s"]:.1f} rot_c {[round(x, 2) for x in m["rot_c"]]}'
          f'\n  len {m["len"]:.1f} width {m["width"]:.1f} s {[round(x, 1) for x in m["s_range"]]} reach {[round(x, 1) for x in m["reach"]]}'
          f'\n  nn {m["nn_min"]:.3f}/{m["nn_med"]:.3f}  gnd {m["gnd"]} over {m["gnd_over"]} near {[round(x, 3) for x in m["gnd_near"]]}'
          f'\n  trunk {[round(x, 1) for x in m["trunk"]]} branch med/max {[round(x, 1) for x in m["branch"]]} over {m["over"]}'
          f'\n  mis tight {({k: round(v, 2) for k, v in m["mis_tight"].items()})} ck {[round(x, 2) for x in m["mis_ck"]]} med {m["mis_med"]:.2f} max {m["mis_max"]:.2f}'
          f' | free order med {m["mis_plain_med"]:.2f} max {m["mis_plain_max"]:.2f}'
          f'\n  gate {m["passage"]:.2f} past {m["past_neck"]} need {({k: round(v, 2) for k, v in m["neck_need"].items()})} data {({k: round(v[0], 1) for k, v in m["data"].items()})}')


def main():
    if "--matrix" in sys.argv:
        for slide in (0.0, 1.0, 2.0, 3.0):
            for key, (g, fix, per) in PATTERNS.items():
                for start in (3.2, None):
                    show(build(key, f"{key} start {start}", "", slide, g(), start, [], per, fix))
        return
    cands = CANDS()
    (HERE / "tee_array_variants.html").write_text(page(cands), encoding="utf-8")
    slim = [{k: v for k, v in m.items() if k not in ("blurb", "notes")} for m in cands]
    (HERE / "metrics.json").write_text(json.dumps(slim, ensure_ascii=False, indent=1), encoding="utf-8")
    for m in cands:
        show(m)
        print(f'  order W {[r["net"] for r in sorted(m["rows"], key=lambda r: r["s"]) if r["side"] == "W"]}'
              f'\n  order E {[r["net"] for r in sorted(m["rows"], key=lambda r: r["s"]) if r["side"] == "E"]}')


def CANDS():
    g, fix, per = PATTERNS["2r08"]
    a = build("tight", "A　两排，排内 0.80 mm",
              "两排过孔夹着轴线交错排，排内中心距 0.80 mm，两排相距 1.20 mm；轴线上每 1.6 mm 一个地过孔。",
              0.0, g(), 3.2,
              ["过孔最密。一半的信号过孔离地过孔 0.63 mm，另一半 0.85 mm，超过我们定的 0.635（官方板中位 0.69，最大 1.08）。",
               "地过孔再加密就过不了线：轴线上每 0.8 mm 已经有两根分支横穿过去。",
               "过了拐弯处，西边一排有一段落在颗粒 A 的规则区里，空着（图上带子中间的缺口）。"], per, fix)
    g, fix, per = PATTERNS["2r10"]
    b = build("ruled", "B　两排，排内 1.00 mm，每格一个地过孔",
              "排内中心距放到 1.00 mm，两排相距 1.12 mm，轴线上每 1.0 mm 一个地过孔：每个信号过孔 0.61 mm 处都有地过孔，一个地过孔管左右各一个。",
              0.0, g(), 3.2,
              ["满足 0.635。带子最长，最远的过孔越过等长中心 5 mm，那几根的分支估算到 15.0 mm，贴着 15.24 的上限。",
               "轴线上每 1.0 mm 过两根线加一个地过孔，线到过孔盘按 0.10 mm 算刚好放下（要 0.97）。"], per, fix)
    g, fix, per = PATTERNS["4r"]
    c = build("four", "C　四排（官方 EVB1 的排法）",
              "照官方 EVB1：沿轴线每 0.4 mm 一个过孔，左右交替、里外两排交替，共四排；地过孔在轴线上和最外侧，每个信号过孔 0.60 到 0.61 mm 处有一个。",
              0.0, g(), 3.2,
              ["带子最短，最远的过孔离等长中心最近：分支最短，两分支天然差的中位最小。",
               "带宽 3.0 mm（连外侧地过孔 4.3 mm）。在两颗颗粒之间的口子里外侧两排放不下，那一段只有里面两排。",
               "同一侧里外两排的过孔相距 1.10 mm，和官方板的中位 1.02 接近。"], per, fix)
    return [a, b, c]


if __name__ == "__main__":
    main()
