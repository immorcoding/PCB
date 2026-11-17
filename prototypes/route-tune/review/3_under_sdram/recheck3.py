"""PROTOTYPE (issue 21) independent re-measurement for the review of variant 3_under_sdram.

Reads out/<key>/routetune.kicad_pcb as text (no pcbnew, nothing from lib/), runs its own DRC length probe with
kicad-cli, and compares with out/<key>/metrics.json.

Run from prototypes/route-tune:   D:/KiCad/bin/python.exe review/3_under_sdram/recheck3.py 3_under_sdram [--no-probe]
"""
import json, math, os, re, shutil, subprocess, sys, tempfile

KEY = sys.argv[1] if len(sys.argv) > 1 else "3_under_sdram"
PROBE = "--no-probe" not in sys.argv
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "out", KEY)
PCB = os.path.join(OUT, "routetune.kicad_pcb")
KICAD_CLI = "D:/KiCad/bin/kicad-cli.exe"
OFF = 100.0                                    # board-file mm - 100 = local mm
MCU_OUT = (8.0, 7.0, 18.0, 17.0); MCU_AREA = (7.0, 6.0, 19.0, 18.0)
SDR_OUT = (23.0, 9.4, 31.0, 22.4); SDR_AREA = (22.0, 8.4, 32.0, 23.4)
LAYER = {"F.Cu": "L1", "In3.Cu": "L4", "B.Cu": "L6"}
ROWS = "ABCDEFGHJKLMNPR"
# SDRAM ball map typed from docs/research/sdram-32bit-bga.md section 2 (columns 1 2 3 7 8 9)
SDR_MAP_TXT = """A DQ26 DQ24 VSS VDD DQ23 DQ21
B DQ28 VDDQ VSSQ VDDQ VSSQ DQ19
C VSSQ DQ27 DQ25 DQ22 DQ20 VDDQ
D VSSQ DQ29 DQ30 DQ17 DQ18 VDDQ
E VDDQ DQ31 NC NC DQ16 VSSQ
F VSS DQM3 A3 A2 DQM2 VDD
G A4 A5 A6 A10 A0 A1
H A7 A8 NC NC BA1 A11
J CLK CKE A9 BA0 CS# RAS#
K DQM1 NC NC CAS# WE# DQM0
L VDDQ DQ8 VSS VDD DQ7 VSSQ
M VSSQ DQ10 DQ9 DQ6 DQ5 VDDQ
N VSSQ DQ12 DQ14 DQ1 DQ3 VDDQ
P DQ11 VDDQ VSSQ VDDQ VSSQ DQ4
R DQ13 DQ15 VSS VDD DQ0 DQ2"""
SDR_FUNC = {}
for ln in SDR_MAP_TXT.splitlines():
    p = ln.split()
    for c, f in zip((1, 2, 3, 7, 8, 9), p[1:]):
        SDR_FUNC["%s%d" % (p[0], c)] = f
# MCU balls from balldata.py (research/sdram-placement-study): net -> (ball, ring)
MCU_BALL = {"D0": ("M14", 1), "D1": ("L14", 1), "D2": ("B12", 1), "D3": ("C12", 2), "D4": ("R8", 0), "D5": ("P8", 1), "D6": ("P9", 1),
            "D7": ("R9", 0), "D8": ("P10", 1), "D9": ("R10", 0), "D10": ("N11", 2), "D11": ("P11", 1), "D12": ("R11", 0), "D13": ("P15", 0),
            "D14": ("P14", 1), "D15": ("N15", 0), "NBL0": ("A4", 0), "NBL1": ("A3", 0), "SDCLK": ("H14", 1)}
FINDINGS = []


def finding(s):
    FINDINGS.append(s)


# ------------------------------------------------------------------ minimal s-expression reader
def parse(text):
    tok = re.findall(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()]+', text)
    pos = 0
    def rd():
        nonlocal pos
        t = tok[pos]; pos += 1
        if t == "(":
            L = []
            while tok[pos] != ")":
                L.append(rd())
            pos += 1
            return L
        return t[1:-1] if t.startswith('"') else t
    return rd()


def kids(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def kid(node, name):
    k = kids(node, name)
    return k[0] if k else None


def xy(n):
    return (float(n[1]) - OFF, float(n[2]) - OFF)


board = parse(open(PCB, encoding="utf-8").read())

# stackup: z of top / bottom of each copper layer
z = 0.0; cu = {}
for lay in kids(kid(kid(board, "setup"), "stackup"), "layer"):
    th = kid(lay, "thickness")
    th = float(th[1]) if th else 0.0
    if lay[1].endswith(".Cu"):
        cu[lay[1]] = (z, z + th)
    z += th


def attach_z(layer):
    """Where DRC attaches a via to a layer (lib/README claim, tested below against the probe): outer surface of
    F.Cu / B.Cu, mid-plane of an inner layer."""
    a, b = cu[layer]
    return a if layer == "F.Cu" else b if layer == "B.Cu" else (a + b) / 2


def via_h(l1, l2):
    return abs(attach_z(l1) - attach_z(l2))


# pads
pads = []                                       # (ref, name, x, y, dia, net)
for fp in kids(board, "footprint"):
    at = kid(fp, "at"); fx, fy = xy(at); rot = float(at[3]) if len(at) > 3 else 0.0
    ref = [p[2] for p in kids(fp, "property") if p[1] == "Reference"][0]
    for p in kids(fp, "pad"):
        a = kid(p, "at"); dx, dy = float(a[1]), float(a[2])
        r = math.radians(rot); px = fx + dx * math.cos(r) + dy * math.sin(r); py = fy - dx * math.sin(r) + dy * math.cos(r)
        net = kid(p, "net"); net = net[-1] if net else ""
        pads.append((ref, p[1], round(px, 6), round(py, 6), float(kid(p, "size")[1]), net))
PADPOS = {(r, n): (x, y) for r, n, x, y, d, net in pads}

segs, arcs, vias = [], [], []
for s in kids(board, "segment"):
    segs.append({"a": xy(kid(s, "start")), "b": xy(kid(s, "end")), "w": float(kid(s, "width")[1]), "layer": kid(s, "layer")[1], "net": kid(s, "net")[-1]})
for s in kids(board, "arc"):
    arcs.append({"a": xy(kid(s, "start")), "m": xy(kid(s, "mid")), "b": xy(kid(s, "end")), "w": float(kid(s, "width")[1]), "layer": kid(s, "layer")[1], "net": kid(s, "net")[-1]})
for s in kids(board, "via"):
    vias.append({"p": xy(kid(s, "at")), "d": float(kid(s, "size")[1]), "h": float(kid(s, "drill")[1]), "layers": kid(s, "layers")[1:], "net": kid(s, "net")[-1]})


def circle3(a, m, b):
    ax, ay = a; bx, by = m; cx, cy = b
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    return (ux, uy), math.hypot(ax - ux, ay - uy)


for a in arcs:
    c, r = circle3(a["a"], a["m"], a["b"]); a["c"] = c; a["r"] = r
    a0 = math.atan2(a["a"][1] - c[1], a["a"][0] - c[0]); am = math.atan2(a["m"][1] - c[1], a["m"][0] - c[0]); a1 = math.atan2(a["b"][1] - c[1], a["b"][0] - c[0])
    def nrm(t):
        while t <= -math.pi: t += 2 * math.pi
        while t > math.pi: t -= 2 * math.pi
        return t
    sw = nrm(am - a0) + nrm(a1 - am); a["a0"] = a0; a["sw"] = sw; a["len"] = abs(sw) * r
    n = 12
    a["poly"] = [(c[0] + r * math.cos(a0 + sw * i / n), c[1] + r * math.sin(a0 + sw * i / n)) for i in range(n + 1)]
for s in segs:
    s["len"] = math.hypot(s["b"][0] - s["a"][0], s["b"][1] - s["a"][1]); s["poly"] = [s["a"], s["b"]]

NETS = sorted({s["net"] for s in segs if s["net"].startswith("/FMC_")})
short = lambda n: n.replace("/FMC_", "")
inside = lambda p, R, eps=1e-9: R[0] - eps <= p[0] <= R[2] + eps and R[1] - eps <= p[1] <= R[3] + eps
key = lambda p: (round(p[0], 4), round(p[1], 4))


# ------------------------------------------------------------------ per-net path, length, shape
def tangent(el, at_start):
    """Unit direction of travel a->b at the start or the end of the element."""
    if "c" in el:
        ang = el["a0"] + (0 if at_start else el["sw"]); sgn = 1 if el["sw"] > 0 else -1
        return (-math.sin(ang) * sgn, math.cos(ang) * sgn)
    dx, dy = el["b"][0] - el["a"][0], el["b"][1] - el["a"][1]; L = math.hypot(dx, dy)
    return (dx / L, dy / L)


res = {}
for net in NETS:
    els = [dict(e) for e in segs + arcs if e["net"] == net]
    vs = [v for v in vias if v["net"] == net]
    p1 = [(x, y) for r, n, x, y, d, pn in pads if pn == net and r == "U1"]
    p2 = [(x, y, n) for r, n, x, y, d, pn in pads if pn == net and r == "U2"]
    if len(p1) != 1 or len(p2) != 1:
        finding("%s: pads U1 %d, U2 %d" % (net, len(p1), len(p2))); continue
    # node = (xy, layer); via joins layers at its xy
    adj = {}
    for i, e in enumerate(els):
        for end in ("a", "b"):
            adj.setdefault((key(e[end]), e["layer"]), []).append(i)
    for nk, lst in adj.items():
        if len(lst) > 2:
            finding("%s: T junction / branch at %s %s (%d ends)" % (net, nk[0], nk[1], len(lst)))
    cur = (key(p1[0]), "F.Cu"); used = set(); order = []; nv = 0; vlen = 0.0; vused = set()
    goal = key((p2[0][0], p2[0][1]))
    for _ in range(len(els) + len(vs) + 5):
        if cur[0] == goal and cur[1] == "F.Cu":
            break
        nxt = [i for i in adj.get(cur, []) if i not in used]
        if nxt:
            i = nxt[0]; e = els[i]; used.add(i)
            if key(e["a"]) != cur[0]:                      # flip so the element runs in travel direction
                e["a"], e["b"] = e["b"], e["a"]
                if "c" in e:
                    e["a0"] = e["a0"] + e["sw"]; e["sw"] = -e["sw"]; e["poly"] = e["poly"][::-1]
                else:
                    e["poly"] = e["poly"][::-1]
            order.append(e); cur = (key(e["b"]), e["layer"]); continue
        vv = [j for j, v in enumerate(vs) if key(v["p"]) == cur[0] and j not in vused]
        if not vv:
            finding("%s: path breaks at %s %s" % (net, cur[0], cur[1])); break
        vused.add(vv[0])
        others = [l for (k, l), lst in adj.items() if k == cur[0] and l != cur[1] and any(i not in used for i in lst)]
        if len(others) != 1:
            finding("%s: via at %s leads to %d layers" % (net, cur[0], len(others))); break
        order.append({"via": vs[vv[0]], "from": cur[1], "to": others[0]}); vlen += via_h(cur[1], others[0]); nv += 1
        cur = (cur[0], others[0])
    if len(used) != len(els):
        finding("%s: %d track pieces are not on the pad-to-pad path (stub / loop)" % (net, len(els) - len(used)))
    if len(vs) != nv:
        finding("%s: %d vias on the board, %d on the path" % (net, len(vs), nv))
    by_layer = {}
    for e in order:
        if "via" not in e:
            by_layer[LAYER[e["layer"]]] = by_layer.get(LAYER[e["layer"]], 0) + e["len"]
    # shape: segment directions and joints
    for i, e in enumerate(order):
        if "via" in e:
            continue
        if "c" not in e:
            d = tangent(e, True); ang = math.degrees(math.atan2(d[1], d[0])) % 45
            if min(ang, 45 - ang) > 0.05:
                finding("%s: segment %s-%s is off 0/45/90 by %.3f deg" % (net, key(e["a"]), key(e["b"]), min(ang, 45 - ang)))
            if e["len"] < 0.1 - 1e-6:
                finding("%s: segment shorter than 0.1 at %s (%.4f)" % (net, key(e["a"]), e["len"]))
        if i + 1 < len(order) and "via" not in order[i + 1]:
            f = order[i + 1]; t0 = tangent(e, False); t1 = tangent(f, True)
            turn = math.degrees(math.acos(max(-1, min(1, t0[0] * t1[0] + t0[1] * t1[1]))))
            if "c" in e or "c" in f:
                if turn > 0.5:
                    finding("%s: arc joint not tangent at %s (%.2f deg)" % (net, key(e["b"]), turn))
            elif turn > 45.05:
                finding("%s: corner of %.1f deg turn at %s on %s" % (net, turn, key(e["b"]), e["layer"]))
        if i + 2 < len(order) and "via" in order[i + 1]:
            f = order[i + 2]; t0 = tangent(e, False); t1 = tangent(f, True)
            turn = math.degrees(math.acos(max(-1, min(1, t0[0] * t1[0] + t0[1] * t1[1]))))
            if turn > 89.9:
                finding("%s: track turns %.0f deg through the via at %s" % (net, turn, key(e["b"])))
    res[net] = {"order": order, "xy": sum(e["len"] for e in order if "via" not in e), "vlen": vlen, "nv": nv, "by_layer": by_layer,
                "p1": p1[0], "p2": p2[0]}

# ------------------------------------------------------------------ widths against rule areas, via sizes, vias in the corridor
def seg_touches(s, R):
    a, b = s["a"], s["b"]
    for i in range(51):
        p = (a[0] + (b[0] - a[0]) * i / 50, a[1] + (b[1] - a[1]) * i / 50)
        if inside(p, R): return True
    return False


thin_out = {}
for e in segs + arcs:
    if not e["net"].startswith("/FMC_"): continue
    pts = e["poly"]
    touch = any(seg_touches({"a": pts[i], "b": pts[i + 1]}, MCU_AREA) or seg_touches({"a": pts[i], "b": pts[i + 1]}, SDR_AREA) for i in range(len(pts) - 1))
    wholly = all(inside(p, MCU_AREA) for p in pts) or all(inside(p, SDR_AREA) for p in pts)
    if abs(e["w"] - 0.09) < 1e-6:
        if not touch:
            finding("%s: 0.09 track that touches no rule area at %s" % (e["net"], key(e["a"])))
        if "c" not in e:                               # length of thin track outside both areas
            n = 200; out = sum(1 for i in range(n) if not inside((e["a"][0] + (e["b"][0] - e["a"][0]) * (i + .5) / n, e["a"][1] + (e["b"][1] - e["a"][1]) * (i + .5) / n), MCU_AREA)
                               and not inside((e["a"][0] + (e["b"][0] - e["a"][0]) * (i + .5) / n, e["a"][1] + (e["b"][1] - e["a"][1]) * (i + .5) / n), SDR_AREA)) * e["len"] / n
            thin_out[short(e["net"])] = thin_out.get(short(e["net"]), 0) + out
    elif abs(e["w"] - 0.1016) < 1e-6:
        if wholly:
            finding("%s: 0.1016 track wholly inside a rule area at %s" % (e["net"], key(e["a"])))
    else:
        finding("%s: track width %.4f at %s" % (e["net"], e["w"], key(e["a"])))
gap_vias = []
for v in vias:
    if not v["net"].startswith("/FMC_"): continue
    ins = inside(v["p"], MCU_AREA) or inside(v["p"], SDR_AREA)
    if ins and (abs(v["d"] - 0.30) > 1e-6 or abs(v["h"] - 0.15) > 1e-6): finding("%s: via %s size %.2f/%.2f inside a rule area" % (v["net"], key(v["p"]), v["d"], v["h"]))
    if not ins and (v["d"] < 0.45 - 1e-6 or v["h"] < 0.2 - 1e-6): finding("%s: via %s size %.2f/%.2f outside the rule areas" % (v["net"], key(v["p"]), v["d"], v["h"]))
    if 19.0 - v["d"] / 2 < v["p"][0] < 22.0 + v["d"] / 2 and not ins: gap_vias.append((short(v["net"]), key(v["p"])))
    if not ins: gap_vias.append((short(v["net"]) + " (outside both rule areas)", key(v["p"])))

# ------------------------------------------------------------------ gaps and crossings (same layer, different nets)
def d_pt_seg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def cross(a, b, c, d):
    o = lambda p, q, r: (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return o(a, b, c) * o(a, b, d) < -1e-12 and o(c, d, a) * o(c, d, b) < -1e-12


def d_seg_seg(a, b, c, d):
    if cross(a, b, c, d): return 0.0
    return min(d_pt_seg(a, c, d), d_pt_seg(b, c, d), d_pt_seg(c, a, b), d_pt_seg(d, a, b))


prims = {"F.Cu": [], "In3.Cu": [], "B.Cu": []}           # (net, kind, pieces [(a,b)], halfwidth, is_serp_arc, bbox)
def bbox(pts, m):
    return (min(p[0] for p in pts) - m, min(p[1] for p in pts) - m, max(p[0] for p in pts) + m, max(p[1] for p in pts) + m)
for e in segs + arcs:
    if e["layer"] in prims:
        pc = [(e["poly"][i], e["poly"][i + 1]) for i in range(len(e["poly"]) - 1)]
        prims[e["layer"]].append((e["net"], "arc" if "c" in e else "track", pc, e["w"] / 2, "c" in e, bbox(e["poly"], e["w"] / 2), e))
for v in vias:
    for l in prims:
        prims[l].append((v["net"], "via", [(v["p"], v["p"])], v["d"] / 2, False, bbox([v["p"]], v["d"] / 2), v))
for r, n, x, y, d, pn in pads:
    prims["F.Cu"].append((pn or "(%s.%s)" % (r, n), "pad", [((x, y), (x, y))], d / 2, False, bbox([(x, y)], d / 2), {"pad": r + "." + n}))
pairs = []
for l, P in prims.items():
    for i in range(len(P)):
        A = P[i]
        if not A[0].startswith("/FMC_"): continue
        for j in range(len(P)):
            B = P[j]
            if B[0] == A[0] or (B[0].startswith("/FMC_") and j < i): continue
            if A[5][0] > B[5][2] + 0.45 or B[5][0] > A[5][2] + 0.45 or A[5][1] > B[5][3] + 0.45 or B[5][1] > A[5][3] + 0.45: continue
            dmin = min(d_seg_seg(a, b, c, d) for a, b in A[2] for c, d in B[2])
            gap = dmin - A[3] - B[3]
            mid = A[2][0][0]
            need = 0.09 if (A[5][2] >= SDR_AREA[0] and A[5][0] <= SDR_AREA[2] and A[5][3] >= SDR_AREA[1] and A[5][1] <= SDR_AREA[3]) or \
                           (A[5][2] >= MCU_AREA[0] and A[5][0] <= MCU_AREA[2] and A[5][3] >= MCU_AREA[1] and A[5][1] <= MCU_AREA[3]) or \
                           (B[5][2] >= SDR_AREA[0] and B[5][0] <= SDR_AREA[2] and B[5][3] >= SDR_AREA[1] and B[5][1] <= SDR_AREA[3]) or \
                           (B[5][2] >= MCU_AREA[0] and B[5][0] <= MCU_AREA[2] and B[5][3] >= MCU_AREA[1] and B[5][1] <= MCU_AREA[3]) else 0.127
            hole = None
            if B[1] == "via": hole = dmin - A[3] - B[6]["h"] / 2          # copper of A to the hole wall of B
            if A[1] == "via" and B[1] != "via": hole = dmin - B[3] - A[6]["h"] / 2
            if A[1] == "via" and B[1] == "via": hole = dmin - A[6]["h"] / 2 - B[6]["h"] / 2
            pairs.append((gap, l, short(A[0]), A[1], short(B[0]), B[1], key(mid), need, hole, A[4] or B[4]))
            if dmin == 0.0 and A[1] != "via" and B[1] not in ("via", "pad"): finding("crossing on %s: %s x %s near %s" % (l, A[0], B[0], key(mid)))
            if gap < need - 1e-4: finding("gap %.4f < %.3f on %s: %s %s to %s %s near %s" % (gap, need, l, A[0], A[1], B[0], B[1], key(mid)))
pairs.sort()

# ------------------------------------------------------------------ serpentine blocks
blocks = []
for net in NETS:
    order = res[net]["order"]; i = 0
    while i < len(order):
        if "c" not in order[i]:
            i += 1; continue
        j = i
        while j + 1 < len(order) and "via" not in order[j + 1] and ("c" in order[j + 1] or (j + 2 < len(order) and "c" in order[j + 2])):
            j += 1
        blk = order[i:j + 1]
        base = order[i - 1]; t = tangent(base, False); nrm_ = (-t[1], t[0]); o = blk[0]["a"]
        off = lambda p: (p[0] - o[0]) * nrm_[0] + (p[1] - o[1]) * nrm_[1]
        along = lambda p: (p[0] - o[0]) * t[0] + (p[1] - o[1]) * t[1]
        # split at returns to the base line; a segment parallel to the base ON the base line splits the block
        humps = []; curmax = 0.0; plen = 0.0; legs = []; lead_in = base["len"]; pts_all = []
        for e in blk:
            for p in e["poly"]:
                pts_all.append(p)
                if abs(off(p)) > abs(curmax): curmax = off(p)
            if "c" not in e:
                d = tangent(e, True)
                if abs(d[0] * t[0] + d[1] * t[1]) < 0.01: legs.append(along(e["a"]))
                elif abs(off(e["a"])) < 1e-4: finding("%s: straight on the base line inside a serpentine run at %s (two blocks on one straight)" % (net, key(e["a"])))
            plen += e["len"]
            if abs(off(e["b"])) < 1e-4:
                humps.append(round(curmax, 4)); curmax = 0.0
        radii = sorted({round(e["r"], 4) for e in blk if "c" in e})
        sweeps = [abs(math.degrees(e["sw"])) for e in blk if "c" in e]
        span = along(blk[-1]["b"])
        nxt = order[j + 1] if j + 1 < len(order) else None
        lead_out = nxt["len"] if nxt and "via" not in nxt else 0.0
        n_in = 0; n_all = 0
        for e in blk:
            for k in range(len(e["poly"]) - 1):
                a, b = e["poly"][k], e["poly"][k + 1]
                for q in range(5):
                    p = (a[0] + (b[0] - a[0]) * (q + .5) / 5, a[1] + (b[1] - a[1]) * (q + .5) / 5); n_all += 1
                    n_in += 1 if inside(p, SDR_OUT) else 0
        ext = bbox(pts_all, blk[0]["w"] / 2)
        legs = sorted(set(round(v, 4) for v in legs))
        leg_pitch = sorted({round(legs[k + 1] - legs[k], 4) for k in range(len(legs) - 1)})
        blocks.append({"net": short(net), "layer": LAYER[blk[0]["layer"]], "humps": humps, "radii": radii, "pitch": [2 * r for r in radii], "leg_pitch": leg_pitch,
                       "gain": plen - abs(span), "span": abs(span), "lead_in": lead_in, "lead_out": lead_out, "under": n_in / n_all, "ext": ext,
                       "sweep": (min(sweeps), max(sweeps)), "width": blk[0]["w"], "start": key(blk[0]["a"]), "end": key(blk[-1]["b"]),
                       "all_in_sdr_area": all(inside(p, SDR_AREA) for p in pts_all)})
        i = j + 1
for b in blocks:
    want = 0.5 if b["net"] == "SDCLK" else 0.3
    if any(abs(p - want) > 2e-3 for p in b["pitch"]): finding("%s: serpentine pitch %s, expected %.1f" % (b["net"], b["pitch"], want))
    if any(abs(p - want) > 2e-3 for p in b["leg_pitch"]): finding("%s: leg spacing %s, expected %.1f" % (b["net"], b["leg_pitch"], want))
    hs = [abs(h) for h in b["humps"]]
    if max(hs) - min(hs) > 2e-3: finding("%s: unequal hump heights in one block %s" % (b["net"], b["humps"]))
    if b["sweep"][0] < 89.9 or b["sweep"][1] > 90.1: finding("%s: arc sweep %s" % (b["net"], b["sweep"]))
    if min(b["lead_in"], b["lead_out"]) < 0.35 - 1e-4: finding("%s: only %.3f mm of straight between a bend / via and the first arc" % (b["net"], min(b["lead_in"], b["lead_out"])))
    if b["width"] < 0.1 and not b["all_in_sdr_area"]: finding("%s: 0.09 serpentine leaves the rule area" % b["net"])

# ------------------------------------------------------------------ space numbers (centre lines outside both package outlines)
def hull(pts):
    pts = sorted(set(pts))
    def half(ps):
        h = []
        for p in ps:
            while len(h) >= 2 and (h[-1][0] - h[-2][0]) * (p[1] - h[-2][1]) - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0]) <= 0: h.pop()
            h.append(p)
        return h
    lo = half(pts); up = half(pts[::-1]); return lo[:-1] + up[:-1]


out_pts2 = []; SDR_OUT2 = (23.0, 9.5, 31.0, 22.4)      # sensitivity: the outline's top edge 0.1 mm lower
out_pts = []; chan = {}; under_len = {}; under_sdr_area_len = {}
for e in segs + arcs:
    if not e["net"].startswith("/FMC_"): continue
    for k in range(len(e["poly"]) - 1):
        a, b = e["poly"][k], e["poly"][k + 1]; L = math.hypot(b[0] - a[0], b[1] - a[1]); n = max(2, int(L / 0.005))
        for q in range(n + 1):
            p = (a[0] + (b[0] - a[0]) * q / n, a[1] + (b[1] - a[1]) * q / n)
            if not inside(p, MCU_OUT, 0) and not inside(p, SDR_OUT, 0):
                out_pts.append((round(p[0], 3), round(p[1], 3)))
            if not inside(p, MCU_OUT, 0) and not inside(p, SDR_OUT2, 0):
                out_pts2.append((round(p[0], 3), round(p[1], 3)))
            if 19.0 <= p[0] <= 22.0:
                c = chan.setdefault(LAYER[e["layer"]], [1e9, -1e9]); c[0] = min(c[0], p[1]); c[1] = max(c[1], p[1])
        for q in range(n):
            p = (a[0] + (b[0] - a[0]) * (q + .5) / n, a[1] + (b[1] - a[1]) * (q + .5) / n)
            if inside(p, SDR_OUT): under_len[LAYER[e["layer"]]] = under_len.get(LAYER[e["layer"]], 0) + L / n
H = hull(out_pts)
area = abs(sum(H[i][0] * H[(i + 1) % len(H)][1] - H[(i + 1) % len(H)][0] * H[i][1] for i in range(len(H)))) / 2
bx = (min(p[0] for p in out_pts), min(p[1] for p in out_pts), max(p[0] for p in out_pts), max(p[1] for p in out_pts))
ch_all = (min(c[0] for c in chan.values()), max(c[1] for c in chan.values()))

# ------------------------------------------------------------------ direct distance, swap table, rings
def octi(a, b):
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1]); return max(dx, dy) - min(dx, dy) + min(dx, dy) * math.sqrt(2)


swap = {}
for net in NETS:
    n = short(net); ball = res[net]["p2"][2]; f = SDR_FUNC[ball]; swap[n] = (ball, f)
    mb = [nm for r, nm, x, y, d, pn in pads if r == "U1" and pn == net][0]
    if mb != MCU_BALL[n][0]: finding("%s: MCU ball %s, research table says %s" % (n, mb, MCU_BALL[n][0]))
    ring = min(ROWS.index(mb[0]), 14 - ROWS.index(mb[0]), int(mb[1:]) - 1, 15 - int(mb[1:]))
    if ring != MCU_BALL[n][1]: finding("%s: ring computed %d, table %d" % (n, ring, MCU_BALL[n][1]))
    # ring 0/1: L1 until outside the ball field (first via outside the outermost ball row/col); ring 2/3: via inside, leaves on L4
    first_via = next((e for e in res[net]["order"] if "via" in e), None)
    if first_via is None:
        if ring >= 2: finding("%s: ring %d ball without a via" % (n, ring))
        continue_ring = False
    vp = first_via["via"]["p"] if first_via else (99, 99)
    field = (13 - 7 * 0.65 - 0.01, 12 - 7 * 0.65 - 0.01, 13 + 7 * 0.65 + 0.01, 12 + 7 * 0.65 + 0.01)
    if ring <= 1 and inside(vp, field): finding("%s: ring %d ball but first via at %s is inside the ball field" % (n, ring, key(vp)))
    if ring >= 2 and first_via and (not inside(vp, field) or first_via["to"] != "In3.Cu"): finding("%s: ring %d ball must use a dog-bone via to L4" % (n, ring))
    if n == "SDCLK" and f != "CLK": finding("SDCLK lands on %s" % f)
    if n.startswith("NBL") and f != "DQM" + n[3]: finding("%s lands on %s" % (n, f))
    if n[0] == "D":
        if not f.startswith("DQ") or f.startswith("DQM"): finding("%s lands on %s" % (n, f))
        elif int(f[2:]) // 8 != int(n[1:]) // 8: finding("%s (lane %d) lands on %s (lane %d): lane swap without DQM following / mixed lanes" % (n, int(n[1:]) // 8, f, int(f[2:]) // 8))
if len({v for v in swap.values()}) != 19: finding("swap table has duplicate balls")

# ------------------------------------------------------------------ own DRC probe: every /FMC_* net reports its length
drc_len = {}
if PROBE:
    tmp = tempfile.mkdtemp(prefix="recheck3_")
    for f in ("routetune.kicad_pcb", "routetune.kicad_pro"):
        shutil.copy(os.path.join(OUT, f), tmp)
    dru = open(os.path.join(OUT, "routetune.kicad_dru"), encoding="utf-8").read()
    dru = dru[:dru.index('(rule "sdram_len_max"')] + '(rule "probe_len"\n  (condition "A.NetName == \'/FMC_*\'")\n  (constraint length (max 1mm)))\n'
    open(os.path.join(tmp, "routetune.kicad_dru"), "w", encoding="utf-8").write(dru)
    rep = os.path.join(tmp, "probe.json")
    subprocess.run([KICAD_CLI, "pcb", "drc", "--severity-all", "--format", "json", "--units", "mm", "-o", rep, os.path.join(tmp, "routetune.kicad_pcb")],
                   capture_output=True)
    J = json.load(open(rep, encoding="utf-8"))
    for v in J.get("violations", []):
        if v.get("type") == "length_out_of_range":
            m = re.search(r"([0-9.]+) mm\)\s*$", v.get("description", "")); txt = json.dumps(v)   # last number = the actual length (any UI language)
            nm = re.search(r"/FMC_[A-Z0-9]+", txt)
            if m and nm: drc_len[nm.group(0)] = float(m.group(1))
    if len(drc_len) != 19: finding("own DRC probe matched %d nets, expected 19" % len(drc_len))
    shutil.rmtree(tmp, ignore_errors=True)

# ------------------------------------------------------------------ report
M = json.load(open(os.path.join(OUT, "metrics.json"), encoding="utf-8"))
print("== %s ==  segments %d, arcs %d, vias %d (bus %d)" % (KEY, len(segs), len(arcs), len(vias), sum(1 for v in vias if v["net"].startswith("/FMC_"))))
print("via heights from the stackup: L1-L4 %.4f  L1-L6 %.4f  L4-L6 %.4f" % (via_h("F.Cu", "In3.Cu"), via_h("F.Cu", "B.Cu"), via_h("In3.Cu", "B.Cu")))
clk = res["/FMC_SDCLK"]["xy"] + res["/FMC_SDCLK"]["vlen"]
clk_drc = drc_len.get("/FMC_SDCLK", clk)
print("net     mine     ownDRC   metrics  d(mine-DRC) toCLK   in  vias  L1     L4     L6     direct  serp   detour")
tot_serp = 0; tot_det = 0; tot_dir = 0; worst = 0; inw = 0; planar_det = 0
for net in NETS:
    r = res[net]; n = short(net); L = r["xy"] + r["vlen"]; mm = M["nets"]["FMC_" + n]
    d = drc_len.get(net); ref = d if d is not None else L
    direct = octi(r["p1"], r["p2"][:2]); sp = sum(b["gain"] for b in blocks if b["net"] == n); det = L - sp - direct
    tot_serp += sp; tot_det += det; tot_dir += direct; planar_det += det - r["vlen"]
    delta = ref - clk_drc; ok = abs(delta) <= 2.5 + 1e-9; inw += ok; worst = max(worst, abs(delta))
    print("%-6s %8.4f %8s %8.4f %9s %+8.4f  %s  %d   %6.3f %6.3f %6.3f  %6.3f %6.3f %7.3f" % (
        n, L, "%.4f" % d if d is not None else "-", mm["length_mm"], "%+.4f" % (L - d) if d is not None else "-", delta, "Y" if ok else "N", r["nv"],
        r["by_layer"].get("L1", 0), r["by_layer"].get("L4", 0), r["by_layer"].get("L6", 0), direct, sp, det))
    if d is not None and abs(L - d) > 2e-3: finding("%s: geometry %.4f vs own DRC %.4f" % (n, L, d))
    if abs(ref - mm["length_mm"]) > 2e-3: finding("%s: length %.4f vs metrics.json %.4f" % (n, ref, mm["length_mm"]))
    if r["nv"] != mm["vias"]: finding("%s: vias %d vs metrics %d" % (n, r["nv"], mm["vias"]))
    if r["nv"] > 3: finding("%s: %d vias (cap 3)" % (n, r["nv"]))
    if ref > 60: finding("%s: longer than 60 mm" % n)
    if abs(direct - mm["direct_mm"]) > 2e-3: finding("%s: direct %.3f vs metrics %.3f" % (n, direct, mm["direct_mm"]))
    if abs(sp - mm["serpentine_mm"]) > 5e-3: finding("%s: serpentine gain %.3f vs metrics %.3f" % (n, sp, mm["serpentine_mm"]))
    if abs(det - mm["detour_mm"]) > 5e-3: finding("%s: detour %.3f vs metrics %.3f" % (n, det, mm["detour_mm"]))
    if not ok and mm["in_window"]: finding("%s: outside the window by my numbers, metrics says inside" % n)
print("in window %d / 19 (metrics %d); worst |delta| %.4f (metrics %.4f); SDCLK %.4f" % (inw, M["totals"]["in_window_count"], worst, M["totals"]["worst_delta_mm"], clk_drc))
print("totals: direct %.3f, detour %.3f (of which via height %.3f, in-plane %.3f), serpentine %.3f   [metrics: %.3f / %.3f / %.3f]" % (
    tot_dir, tot_det, tot_det - planar_det, planar_det, tot_serp, M["totals"]["total_direct_mm"], M["totals"]["total_detour_mm"], M["totals"]["total_serpentine_mm"]))
S = M["space"]
print("hull %.2f mm2 (metrics %.2f); bbox %.3f x %.3f (metrics %s); x %.3f..%.3f y %.3f..%.3f" % (area, S["bus_hull_area_mm2"], bx[2] - bx[0], bx[3] - bx[1], S["bus_bbox_mm"], bx[0], bx[2], bx[1], bx[3]))
print("channel (x 19..22) y %.3f..%.3f = %.3f (metrics %.3f); by layer %s" % (ch_all[0], ch_all[1], ch_all[1] - ch_all[0], S["channel_width_mm"],
      {k: round(v[1] - v[0], 3) for k, v in sorted(chan.items())}))
H2 = hull(out_pts2)
area2 = abs(sum(H2[i][0] * H2[(i + 1) % len(H2)][1] - H2[(i + 1) % len(H2)][0] * H2[i][1] for i in range(len(H2)))) / 2
print("sensitivity: hull with the SDRAM outline's top edge taken 0.1 mm lower (y 9.5 instead of 9.4): %.2f mm2, bbox %.3f x %.3f" % (
    area2, max(p[0] for p in out_pts2) - min(p[0] for p in out_pts2), max(p[1] for p in out_pts2) - min(p[1] for p in out_pts2)))
if abs(area - S["bus_hull_area_mm2"]) > 0.5: finding("hull area %.2f vs metrics %.2f" % (area, S["bus_hull_area_mm2"]))
if abs(ch_all[1] - ch_all[0] - S["channel_width_mm"]) > 0.02: finding("channel width %.3f vs metrics %.3f" % (ch_all[1] - ch_all[0], S["channel_width_mm"]))
print("bus copper under the SDRAM body (centre line inside the outline): %s  total %.1f" % ({k: round(v, 1) for k, v in sorted(under_len.items())}, sum(under_len.values())))
print("vias in the corridor / outside both rule areas: %s" % (gap_vias or "none"))
print("thin (0.09) track outside the rule areas, per net: max %.3f (%s)" % (max(thin_out.values()), max(thin_out, key=thin_out.get)))
for n_, v_ in thin_out.items():
    if v_ > 0.75: finding("%s: %.3f mm of 0.09 track outside the rule areas" % (n_, v_))
print("\nserpentine blocks (%d, %d humps, gain %.3f; share under the SDRAM body %.1f%%):" % (len(blocks), sum(len(b["humps"]) for b in blocks), tot_serp,
      100 * sum(b["gain"] * b["under"] for b in blocks) / max(tot_serp, 1e-9)))
for b in blocks:
    print("  %-6s %s  %d humps %s  radius %s  leg spacing %s  gain %.3f  span %.3f  lead in/out %.3f/%.3f  under body %.0f%%  x %.2f..%.2f y %.2f..%.2f" % (
        b["net"], b["layer"], len(b["humps"]), sorted(set(b["humps"])), b["radii"], b["leg_pitch"], b["gain"], b["span"], b["lead_in"], b["lead_out"], 100 * b["under"],
        b["ext"][0], b["ext"][1 + 1], b["ext"][1], b["ext"][3]))
print("\nsmallest copper gaps between different nets (gap, layer, A, B, near, DRC need, hole wall gap):")
for p in pairs[:14]:
    print("  %.4f %s %s %s - %s %s near %s need %.3f%s%s" % (p[0], LAYER[p[1]], p[2], p[3], p[4], p[5], p[6], p[7], "" if p[8] is None else "  hole %.4f" % p[8], "  [serpentine arc]" if p[9] else ""))
sp_pairs = [p for p in pairs if p[9]]
print("smallest gaps at serpentine arcs:")
for p in sp_pairs[:6]:
    print("  %.4f %s %s %s - %s %s near %s" % (p[0], LAYER[p[1]], p[2], p[3], p[4], p[5], p[6]))
holes = sorted([p for p in pairs if p[8] is not None], key=lambda p: p[8])
print("smallest hole-wall to foreign copper: %s" % ", ".join("%.4f %s-%s(%s)" % (p[8], p[2], p[4], p[5]) for p in holes[:5]))
for p in holes:
    if p[8] < 0.2 - 1e-4 and not (p[3] == "via" and p[5] == "via"): finding("hole wall to copper %.4f < 0.2: %s %s - %s %s near %s" % (p[8], p[2], p[3], p[4], p[5], p[6]))
print("\nswap table: " + ", ".join("%s->%s/%s" % (n, b, f) for n, (b, f) in sorted(swap.items())))
print("\nFINDINGS (%d)" % len(FINDINGS))
for f in FINDINGS: print("  - " + f)
