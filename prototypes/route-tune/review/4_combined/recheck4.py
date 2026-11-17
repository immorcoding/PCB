"""PROTOTYPE review (issue 21): independent re-measurement of 4_combined / 4b_combined_p05.

Own S-expression reader, nothing from lib/, no pcbnew. Reads out/<key>/routetune.kicad_pcb, runs its own
kicad-cli DRC, length probe and rule-file canary in a temp folder, and compares with metrics.json.
Usage: D:/KiCad/bin/python.exe review/4_combined/recheck4.py <key> [--nodrc] [--same <other key>]
Coordinates printed are local mm (board mm - 100, y down).
"""
import json, math, os, re, shutil, subprocess, sys, tempfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
CLI = r"D:\KiCad\bin\kicad-cli.exe"
BODY = {"U1": (8.0, 7.0, 18.0, 17.0), "U2": (23.0, 9.4, 31.0, 22.4)}
STRIP = (19.0, 22.0)
LAY = {"F.Cu": "L1", "In3.Cu": "L4", "B.Cu": "L6"}
ROWS = "ABCDEFGHJKLMNPR"
MCU_BALL = dict(D0="M14", D1="L14", D2="B12", D3="C12", D4="R8", D5="P8", D6="P9", D7="R9", D8="P10", D9="R10",
                D10="N11", D11="P11", D12="R11", D13="P15", D14="P14", D15="N15", NBL0="A4", NBL1="A3", SDCLK="H14")
SDR_MAP = """A DQ26 DQ24 VSS VDD DQ23 DQ21
B DQ28 VDDQ VSSQ VDDQ VSSQ DQ19
C VSSQ DQ27 DQ25 DQ22 DQ20 VDDQ
D VSSQ DQ29 DQ30 DQ17 DQ18 VDDQ
E VDDQ DQ31 NC NC DQ16 VSSQ
F VSS DQM3 A3 A2 DQM2 VDD
G A4 A5 A6 A10 A0 A1
H A7 A8 A12 NC BA1 A11
J CLK CKE A9 BA0 CS# RAS#
K DQM1 NC NC CAS# WE# DQM0
L VDDQ DQ8 VSS VDD DQ7 VSSQ
M VSSQ DQ10 DQ9 DQ6 DQ5 VDDQ
N VSSQ DQ12 DQ14 DQ1 DQ3 VDDQ
P DQ11 VDDQ VSSQ VDDQ VSSQ DQ4
R DQ13 DQ15 VSS VDD DQ0 DQ2"""
SDR_FUNC = {}
for _l in SDR_MAP.splitlines():
    _p = _l.split()
    for _c, _f in zip((1, 2, 3, 7, 8, 9), _p[1:]):
        SDR_FUNC[_p[0] + str(_c)] = _f
FIND = []


def finding(s):
    FIND.append(s)
    print("  FINDING: " + s)


def sexp(text):
    tok = re.findall(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()]+', text)
    stack, cur = [], []
    for t in tok:
        if t == "(":
            stack.append(cur); cur = []
        elif t == ")":
            done = cur; cur = stack.pop(); cur.append(done)
        else:
            cur.append(t[1:-1] if t.startswith('"') else t)
    return cur[0]


def kids(n, name):
    return [c for c in n if isinstance(c, list) and c and c[0] == name]


def kid(n, name):
    k = kids(n, name)
    return k[0] if k else None


def xy(n):
    return (round(float(n[1]) - 100.0, 7), round(float(n[2]) - 100.0, 7))


def load(path):
    root = sexp(open(path, encoding="utf-8").read())
    B = {"segs": [], "arcs": [], "vias": [], "pads": [], "areas": {}}
    # stackup -> z of every copper layer (top surface and thickness)
    z, zs = 0.0, {}
    started = False
    for l in kids(kid(kid(root, "setup"), "stackup"), "layer"):
        t = kid(l, "thickness")
        typ = kid(l, "type")[1]
        th = float(t[1]) if t else 0.0
        if typ == "copper":
            started = True
            zs[l[1]] = (z, th)
        if started:
            z += th
    B["z"] = zs
    for fp in kids(root, "footprint"):
        ref = [p[2] for p in kids(fp, "property") if p[1] == "Reference"][0]
        at = kid(fp, "at")
        fx, fy = float(at[1]) - 100, float(at[2]) - 100
        rot = float(at[3]) if len(at) > 3 else 0.0
        if rot:
            finding("footprint %s is rotated %s (script assumes 0)" % (ref, rot))
        for p in kids(fp, "pad"):
            a = kid(p, "at")
            n = kid(p, "net")
            B["pads"].append({"ref": ref, "name": p[1], "p": (round(fx + float(a[1]), 7), round(fy + float(a[2]), 7)),
                              "d": float(kid(p, "size")[1]), "net": (n[-1] if n else "")})
    for s in kids(root, "segment"):
        B["segs"].append({"a": xy(kid(s, "start")), "b": xy(kid(s, "end")), "w": float(kid(s, "width")[1]),
                          "layer": kid(s, "layer")[1], "net": kid(s, "net")[-1]})
    for s in kids(root, "arc"):
        B["arcs"].append({"a": xy(kid(s, "start")), "m": xy(kid(s, "mid")), "b": xy(kid(s, "end")), "w": float(kid(s, "width")[1]),
                          "layer": kid(s, "layer")[1], "net": kid(s, "net")[-1]})
    for s in kids(root, "via"):
        B["vias"].append({"p": xy(kid(s, "at")), "d": float(kid(s, "size")[1]), "drill": float(kid(s, "drill")[1]),
                          "layers": kid(s, "layers")[1:], "net": kid(s, "net")[-1]})
    for zn in kids(root, "zone"):
        nm = kid(zn, "name")
        if nm and nm[1].startswith("BGA_"):
            pts = [xy(p) for p in kids(kid(kid(zn, "polygon"), "pts"), "xy")]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            B["areas"][nm[1]] = {"rect": (min(xs), min(ys), max(xs), max(ys)), "npts": len(pts), "layers": kid(zn, "layers")[1:]}
    return B


def arc_geom(a):
    (x1, y1), (x2, y2), (x3, y3) = a["a"], a["m"], a["b"]
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    cx = ((x1 ** 2 + y1 ** 2) * (y2 - y3) + (x2 ** 2 + y2 ** 2) * (y3 - y1) + (x3 ** 2 + y3 ** 2) * (y1 - y2)) / d
    cy = ((x1 ** 2 + y1 ** 2) * (x3 - x2) + (x2 ** 2 + y2 ** 2) * (x1 - x3) + (x3 ** 2 + y3 ** 2) * (x2 - x1)) / d
    r = math.hypot(x1 - cx, y1 - cy)
    a1, a2, a3 = (math.atan2(y - cy, x - cx) for (x, y) in (a["a"], a["m"], a["b"]))
    sw = (a3 - a1) % (2 * math.pi)
    if not (0 < (a2 - a1) % (2 * math.pi) < sw):
        sw -= 2 * math.pi
    return (cx, cy), r, a1, sw


def arc_pts(a, step=0.01):
    c, r, a1, sw = arc_geom(a)
    n = max(4, int(abs(sw) * r / step) + 1)
    return [(c[0] + r * math.cos(a1 + sw * i / n), c[1] + r * math.sin(a1 + sw * i / n)) for i in range(n + 1)]


def seg_pts(a, b, step=0.01):
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    n = max(1, int(L / step) + 1)
    return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]


def inrect(p, R, g=0.0):
    return R[0] - g <= p[0] <= R[2] + g and R[1] - g <= p[1] <= R[3] + g


def key(p):
    return (round(p[0], 5), round(p[1], 5))


def walk(B, net):
    """Ordered path U1 pad -> U2 pad: list of ("seg"/"arc"/"via", item, reversed)."""
    items = [("seg", s) for s in B["segs"] if s["net"] == net] + [("arc", s) for s in B["arcs"] if s["net"] == net]
    vias = [v for v in B["vias"] if v["net"] == net]
    pads = {p["ref"]: p for p in B["pads"] if p["net"] == net}
    prob = []
    if set(pads) != {"U1", "U2"}:
        return None, ["pads: %s" % sorted(pads)]
    node = {}
    for i, (k, s) in enumerate(items):
        for e in ("a", "b"):
            node.setdefault((key(s[e]), s["layer"]), []).append(i)
    for n, lst in node.items():
        isvia = any(key(v["p"]) == n[0] for v in vias)
        ispad = n[1] == "F.Cu" and any(key(p["p"]) == n[0] for p in pads.values())
        if len(lst) > 2 or (len(lst) == 2 and (isvia or ispad) and False):
            prob.append("T junction / branch at %s %s" % n)
        if len(lst) == 1 and not (isvia or ispad):
            prob.append("loose end at %s %s" % n)
    cur, lay = key(pads["U1"]["p"]), "F.Cu"
    used, path = set(), []
    goal = key(pads["U2"]["p"])
    for _ in range(len(items) + len(vias) + 2):
        nxt = [i for i in node.get((cur, lay), []) if i not in used]
        if nxt:
            i = nxt[0]; used.add(i)
            k, s = items[i]
            rev = key(s["a"]) != cur
            path.append((k, s, rev))
            cur = key(s["a"] if rev else s["b"])
            continue
        v = [v for v in vias if key(v["p"]) == cur and id(v) not in used]
        if v:
            used.add(id(v[0]))
            others = [l for l in LAY if l != lay and [i for i in node.get((cur, l), []) if i not in used]]
            if len(others) != 1:
                prob.append("via at %s: %d continuing layers" % (cur, len(others))); break
            path.append(("via", v[0], (lay, others[0])))
            lay = others[0]
            continue
        break
    if cur != goal or lay != "F.Cu":
        prob.append("path ends at %s %s, not at the U2 pad" % (cur, lay))
    if len([1 for i in range(len(items)) if i not in used]):
        prob.append("%d items not on the pad-to-pad path" % (len(items) - len([i for i in used if isinstance(i, int) and i < len(items)])))
    if len([v for v in vias if id(v) not in used]):
        prob.append("unused via")
    return path, prob


def zmid(B, layer):
    z, th = B["z"][layer]
    if layer == "F.Cu":
        return z
    if layer == "B.Cu":
        return z + th
    return z + th / 2


def measure(B, net):
    path, prob = walk(B, net)
    out = {"prob": prob, "path": path}
    if path is None:
        return out
    L, by, nv, vm = 0.0, {}, 0, 0.0
    for k, s, r in path:
        if k == "seg":
            d = math.hypot(s["b"][0] - s["a"][0], s["b"][1] - s["a"][1])
        elif k == "arc":
            c, rad, a1, sw = arc_geom(s)
            d = abs(sw) * rad
        else:
            d = abs(zmid(B, r[0]) - zmid(B, r[1])); nv += 1; vm += d
            L += d
            continue
        L += d
        by[LAY[s["layer"]]] = by.get(LAY[s["layer"]], 0.0) + d
    out.update(length=L, layers=by, vias=nv, via_mm=vm)
    return out


def tangent(k, s, rev, at_end):
    """Unit direction of travel at the start (at_end False) or end of a path item."""
    if k == "seg":
        a, b = (s["b"], s["a"]) if rev else (s["a"], s["b"])
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        return ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    c, r, a1, sw = arc_geom(s)
    ang = a1 + (sw if (at_end != rev) else 0.0)
    sgn = (1 if sw > 0 else -1) * (-1 if rev else 1)
    return (-math.sin(ang) * sgn, math.cos(ang) * sgn)


def blocks_of(path):
    """Serpentine blocks: maximal runs that start and end with an arc and hold only arcs and legs between them.
    A straight between two arcs that continues the host direction (travel direction before the block) ends the block
    only when it is longer than 1e-6 and collinear with the host line."""
    idx = [i for i, (k, s, r) in enumerate(path) if k == "arc"]
    if not idx:
        return []
    blocks, cur = [], [idx[0]]
    for i in idx[1:]:
        gap = path[cur[-1] + 1:i]
        if len(gap) <= 1 and all(g[0] == "seg" for g in gap):
            cur.append(i)
        else:
            blocks.append(cur); cur = [i]
    blocks.append(cur)
    res = []
    for b in blocks:
        i0, i1 = b[0], b[-1]
        k, s, r = path[i0]
        start = s["b"] if r else s["a"]
        k2, s2, r2 = path[i1]
        end = s2["a"] if r2 else s2["b"]
        h = tangent(*path[i0], at_end=False)
        nrm = (-h[1], h[0])
        pts, clen = [], 0.0
        for k, s, r in path[i0:i1 + 1]:
            pp = arc_pts(s, 0.004) if k == "arc" else seg_pts(s["a"], s["b"], 0.004)
            if r:
                pp = pp[::-1]
            pts += pp
        P = np.array(pts)
        clen = float(np.sum(np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1]))))
        u = (P[:, 0] - start[0]) * h[0] + (P[:, 1] - start[1]) * h[1]
        o = (P[:, 0] - start[0]) * nrm[0] + (P[:, 1] - start[1]) * nrm[1]
        chord = math.hypot(end[0] - start[0], end[1] - start[1])
        # humps = stretches on one side of the host line (offset beyond 0.01 mm), height = largest offset there
        humps, cur_s, cur_m = [], 0, 0.0
        for j in range(len(o)):
            sj = 0 if abs(o[j]) < 0.01 else (1 if o[j] > 0 else -1)
            if sj != cur_s:
                if cur_s != 0:
                    humps.append(cur_s * cur_m)
                cur_s, cur_m = sj, 0.0
            cur_m = max(cur_m, abs(o[j]))
        if cur_s != 0:
            humps.append(cur_s * cur_m)
        both = len(set(1 if x > 0 else -1 for x in humps)) > 1
        # pitch = spacing along the host of the legs: crossings of a level line (the host line itself for a
        # chain, half the lowest hump for single-sided, nudged so that no sample sits exactly on the level)
        lev = 1e-5 if both else 0.49999 * min(abs(x) for x in humps) * (1 if humps[0] > 0 else -1)
        q = o - lev
        cr = [float(u[j] + (u[j + 1] - u[j]) * (-q[j]) / (q[j + 1] - q[j])) for j in range(len(q) - 1) if (q[j] < 0) != (q[j + 1] < 0)]
        if both:
            cr = cr[1:-1] if abs(cr[0]) < 0.01 else cr      # the two ends touch the host line, they are not legs
            cr = [c for c in cr if 0.01 < c < float(u[-1]) - 0.01]
        pit = sorted(set(round(abs(cr[j + 1] - cr[j]), 2) for j in range(len(cr) - 1)))
        radii = sorted(set(round(arc_geom(path[i][1])[1], 4) for i in b))
        sweeps = sorted(set(round(abs(math.degrees(arc_geom(path[i][1])[3])), 2) for i in b))
        under = float(np.sum(np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1]))[[inrect(((P[j, 0] + P[j + 1, 0]) / 2, (P[j, 1] + P[j + 1, 1]) / 2), BODY["U2"]) for j in range(len(P) - 1)]]))
        # straight lead before the first arc and after the last one (same direction as host)
        def lead(i, step):
            L, j = 0.0, i + step
            while 0 <= j < len(path) and path[j][0] == "seg":
                t = tangent(*path[j], at_end=False)
                if abs(t[0] * h[0] + t[1] * h[1]) < 1 - 1e-6:
                    break
                L += math.hypot(path[j][1]["b"][0] - path[j][1]["a"][0], path[j][1]["b"][1] - path[j][1]["a"][1])
                j += step
            return L
        res.append({"i0": i0, "i1": i1, "start": start, "end": end, "layer": LAY[path[i0][1]["layer"]], "w": path[i0][1]["w"],
                    "humps": [round(float(x), 4) for x in humps], "both": both, "pitch": pit, "radii": radii, "sweeps": sweeps,
                    "gain": clen - chord, "copper": clen, "under": under, "lead_before": lead(i0, -1), "lead_after": lead(i1, +1),
                    "pts": P, "host": h})
    return res


def hull_area(pts):
    pts = sorted(set((round(x, 6), round(y, 6)) for x, y in pts))
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    h = lo[:-1] + up[:-1]
    return abs(sum(h[i][0] * h[(i + 1) % len(h)][1] - h[(i + 1) % len(h)][0] * h[i][1] for i in range(len(h)))) / 2


def run_drc(vdir, extra_rule=None, only_rule=None, patch=None, refill=True):
    tmp = tempfile.mkdtemp(prefix="rt4_")
    try:
        for ext in (".kicad_pcb", ".kicad_pro", ".kicad_dru", ".kicad_prl"):
            if os.path.isfile(os.path.join(vdir, "routetune" + ext)):
                shutil.copy(os.path.join(vdir, "routetune" + ext), os.path.join(tmp, "routetune" + ext))
        dru = os.path.join(tmp, "routetune.kicad_dru")
        if only_rule is not None:
            open(dru, "w", encoding="utf-8").write("(version 1)\n" + only_rule)
        if patch:
            pcb = os.path.join(tmp, "routetune.kicad_pcb")
            t = open(pcb, encoding="utf-8").read().rstrip()
            assert t.endswith(")")
            open(pcb, "w", encoding="utf-8").write(t[:-1] + patch + "\n)\n")
        rpt = os.path.join(tmp, "drc.json")
        cmd = [CLI, "pcb", "drc", "--severity-all", "--units", "mm", "--format", "json", "-o", rpt]
        if refill:
            cmd.append("--refill-zones")
        subprocess.run(cmd + [os.path.join(tmp, "routetune.kicad_pcb")], capture_output=True)
        return json.load(open(rpt, encoding="utf-8"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def skeleton(B, net):
    """Corner points of the net's route with every serpentine block replaced by its chord."""
    path, prob = walk(B, net)
    bl = blocks_of(path)
    skip = {}
    for b in bl:
        skip[b["i0"]] = b
    pts, i = [], 0
    out = []
    while i < len(path):
        k, s, r = path[i]
        if i in skip:
            b = skip[i]
            out.append((b["layer"], key(b["start"]), key(b["end"])))
            i = b["i1"] + 1
            continue
        if k == "via":
            out.append(("via", key(s["p"]), (s["d"], s["drill"])))
        else:
            a, e = (s["b"], s["a"]) if r else (s["a"], s["b"])
            out.append((LAY[s["layer"]], key(a), key(e)))
        i += 1
    # merge collinear neighbours on one layer
    res = []
    for o in out:
        if res and o[0] != "via" and res[-1][0] == o[0]:
            (l, a, b) = res[-1]
            c, d = o[1], o[2]
            if b == c and abs((b[0] - a[0]) * (d[1] - c[1]) - (b[1] - a[1]) * (d[0] - c[0])) < 1e-7 and (b[0] - a[0]) * (d[0] - c[0]) + (b[1] - a[1]) * (d[1] - c[1]) > 0:
                res[-1] = (l, a, d)
                continue
        res.append(o)
    return res


def main():
    keyname = sys.argv[1]
    vdir = os.path.join(ROOT, "out", keyname)
    if [f for f in os.listdir(vdir) if f.startswith("~") and f.endswith(".lck")]:
        print("board is open in KiCad, stop"); sys.exit(2)
    B = load(os.path.join(vdir, "routetune.kicad_pcb"))
    M = json.load(open(os.path.join(vdir, "metrics.json"), encoding="utf-8"))
    nets = sorted(set(s["net"] for s in B["segs"] if s["net"].startswith("/FMC_")))
    print("== %s: %d nets, %d segments, %d arcs, %d vias" % (keyname, len(nets), len(B["segs"]), len(B["arcs"]), len(B["vias"])))
    if len(nets) != 19:
        finding("%d FMC nets on the board, not 19" % len(nets))
    AREA = {("U1" if "MCU" in k else "U2"): v["rect"] for k, v in B["areas"].items()}
    for k, v in B["areas"].items():
        ref = "U1" if "MCU" in k else "U2"
        want = (BODY[ref][0] - 1, BODY[ref][1] - 1, BODY[ref][2] + 1, BODY[ref][3] + 1)
        if max(abs(a - b) for a, b in zip(v["rect"], want)) > 1e-6 or v["npts"] != 4:
            finding("rule area %s is %s, expected %s" % (k, v["rect"], want))
        if set(v["layers"]) != {"F.Cu", "B.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu"}:
            finding("rule area %s layers %s" % (k, v["layers"]))
    print("rule areas:", {k: v["rect"] for k, v in B["areas"].items()})
    print("via heights by my stackup: L1-L4 %.4f, L1-L6 %.4f, L4-L6 %.4f" % (
        abs(zmid(B, "F.Cu") - zmid(B, "In3.Cu")), abs(zmid(B, "F.Cu") - zmid(B, "B.Cu")), abs(zmid(B, "In3.Cu") - zmid(B, "B.Cu"))))

    # ---- DRC, probe, canary (own runs)
    drcL = {}
    if "--nodrc" not in sys.argv:
        d = run_drc(vdir)
        by = {}
        for v in d["violations"]:
            by[v["type"]] = by.get(v["type"], 0) + 1
        print("own DRC (refill, all severities): unconnected %d, violations %d %s" % (len(d["unconnected_items"]), len(d["violations"]), by))
        if d["unconnected_items"]:
            finding("DRC unconnected %d" % len(d["unconnected_items"]))
        if d["violations"]:
            finding("DRC violations %s" % by)
            for v in d["violations"][:12]:
                print("     ", v["type"], v["description"], [(round(i["pos"]["x"] - 100, 3), round(i["pos"]["y"] - 100, 3)) for i in v["items"]][:2])
        dru = open(os.path.join(vdir, "routetune.kicad_dru"), encoding="utf-8").read()
        for m in re.finditer(r'\(rule\s+"([^"]+)"(.*?)(?=\n\(rule|\Z)', dru, re.S):
            if re.search(r"\(constraint\s+length\b", m.group(2)):
                cond = re.search(r'\(condition\s+"[^"]*"\)', m.group(2)).group(0)
                p = run_drc(vdir, only_rule='(rule "probe"\n  %s\n  (constraint length (max 0.001mm)))\n' % cond, refill=False)
                got = {}
                for v in p["violations"]:
                    if v["type"] == "length_out_of_range":
                        nm = re.search(r"\[(/[^\]]*)\]", v["items"][0]["description"])
                        nums = re.findall(r"(-?\d+(?:\.\d+)?) mm", v["description"])
                        if nm and nums:
                            got[nm.group(1)] = float(nums[-1])
                print("probe of rule %s: matched %d nets" % (m.group(1), len(got)))
                if len(got) != 19:
                    finding("length rule %s matches %d nets" % (m.group(1), len(got)))
                drcL = got or drcL
        w = re.search(r'rule "sdram_window".*?\(min ([\d.]+)mm\) \(opt ([\d.]+)mm\) \(max ([\d.]+)mm\)', dru, re.S)
        print("window rule in the rule file: min %s opt %s max %s" % w.groups())
        can = run_drc(vdir, refill=False, patch='\n\t(segment (start 60 60) (end 70 60) (width 0.2) (layer "F.Cu") (net "/FMC_D0") (uuid "11111111-1111-4111-8111-111111111111"))'
                      '\n\t(segment (start 70 60) (end 70 70) (width 0.2) (layer "F.Cu") (net "/FMC_D0") (uuid "11111111-1111-4111-8111-111111111112"))')
        fired = [v for v in can["violations"] if v["type"] == "track_angle"]
        print("canary (90-degree bend added to a copy): track_angle fired %d time(s)" % len(fired))
        if not fired:
            finding("canary: rule file not loaded")
        if any(v["type"] == "track_angle" for v in d["violations"]):
            finding("track_angle on the real board")

    # ---- per net
    print("\nnet        my_len   drc_len  metrics  d_clk    vias lay(L1/L4/L6)        direct  mcu  sdram")
    R = {}
    for n in nets:
        R[n] = measure(B, n)
        for p in R[n]["prob"]:
            finding("%s: %s" % (n, p))
    clk = R["/FMC_SDCLK"]["length"]
    swap, tot_v = {}, 0
    for n in nets:
        r, short = R[n], n[5:]
        m = M["nets"]["FMC_" + short]
        p1 = [p for p in B["pads"] if p["net"] == n and p["ref"] == "U1"][0]
        p2 = [p for p in B["pads"] if p["net"] == n and p["ref"] == "U2"][0]
        dx, dy = abs(p1["p"][0] - p2["p"][0]), abs(p1["p"][1] - p2["p"][1])
        direct = max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)
        r["direct"] = direct
        swap[short] = (p1["name"], p2["name"], SDR_FUNC[p2["name"]])
        tot_v += r["vias"]
        dl = drcL.get(n)
        print("%-9s %8.4f %8s %8.4f %+7.3f  %d    %5.2f/%5.2f/%5.2f   %7.3f  %-4s %s %s" % (
            short, r["length"], ("%.4f" % dl) if dl else "-", m["length_mm"], r["length"] - clk, r["vias"],
            r["layers"].get("L1", 0), r["layers"].get("L4", 0), r["layers"].get("L6", 0), direct, p1["name"], p2["name"], SDR_FUNC[p2["name"]]))
        if dl and abs(dl - r["length"]) > 2e-3:
            finding("%s: geometry %.4f vs own DRC probe %.4f" % (short, r["length"], dl))
        if abs(m["length_mm"] - r["length"]) > 2e-3:
            finding("%s: geometry %.4f vs metrics %.4f" % (short, r["length"], m["length_mm"]))
        if abs(m["direct_mm"] - direct) > 2e-3:
            finding("%s: direct %.4f vs metrics %.4f" % (short, direct, m["direct_mm"]))
        if m["vias"] != r["vias"]:
            finding("%s: vias %d vs metrics %d" % (short, r["vias"], m["vias"]))
        for L in ("L1", "L4", "L6"):
            if abs(m["layers"].get(L, 0) - r["layers"].get(L, 0)) > 2e-3:
                finding("%s: %s length %.4f vs metrics %.4f" % (short, L, r["layers"].get(L, 0), m["layers"].get(L, 0)))
        if abs(r["length"] - clk) > 2.5:
            finding("%s outside the window: %+.3f" % (short, r["length"] - clk))
        if r["length"] > 60:
            finding("%s over 60 mm" % short)
        if r["vias"] > 3:
            finding("%s: %d vias" % (short, r["vias"]))
        if p1["name"] != MCU_BALL[short]:
            finding("%s on MCU ball %s, expected %s" % (short, p1["name"], MCU_BALL[short]))
    print("SDCLK %.4f, window %.4f .. %.4f; in window %d/19; vias total %d, max %d" % (
        clk, clk - 2.5, clk + 2.5, sum(abs(R[n]["length"] - clk) <= 2.5 for n in nets), tot_v, max(R[n]["vias"] for n in nets)))
    if M["totals"]["in_window_count"] != sum(abs(R[n]["length"] - clk) <= 2.5 for n in nets):
        finding("in_window_count differs from metrics")

    # ---- swap legality
    lane = {s: (0 if int(v[2][2:]) < 8 else 1) for s, v in swap.items() if v[2].startswith("DQ") and not v[2].startswith("DQM")}
    lo = set(lane["D%d" % i] for i in range(8)); hi = set(lane["D%d" % i] for i in range(8, 16))
    if len(lo) != 1 or len(hi) != 1 or lo == hi:
        finding("data bits are not whole lanes: %s" % lane)
    else:
        if swap["NBL0"][2] != "DQM%d" % list(lo)[0] or swap["NBL1"][2] != "DQM%d" % list(hi)[0]:
            finding("DQM does not follow its lane: %s %s" % (swap["NBL0"], swap["NBL1"]))
    if len(set(v[2] for v in swap.values())) != 19:
        finding("two nets on one SDRAM function")
    if swap["SDCLK"][2] != "CLK":
        finding("SDCLK not on CLK")
    for s, v in swap.items():
        ms = M["nets"]["FMC_" + s]
        if (ms["mcu_ball"], ms["sdram_ball"], ms["sdram_pin"]) != v:
            finding("%s swap in metrics %s vs board %s" % (s, (ms["mcu_ball"], ms["sdram_ball"], ms["sdram_pin"]), v))
    print("swap: lanes swapped = %s; table checked against the 90-ball map (whole lanes, DQM follows, CLK)" % (list(lo) == [1]))

    # ---- breakout by ring, via positions
    print("\nbreakout:")
    gap_vias = []
    for n in nets:
        short = n[5:]
        ball = MCU_BALL[short]
        rr, cc = ROWS.index(ball[0]), int(ball[1:]) - 1
        ring = min(rr, cc, 14 - rr, 14 - cc)
        path = R[n]["path"]
        first_via = next(((i, s) for i, (k, s, r) in enumerate(path) if k == "via"), None)
        # layer on which the net crosses the MCU package outline
        cross_layer = None
        for k, s, r in path:
            if k != "via":
                a, b = s["a"], (s["b"] if k == "seg" else s["m"])
                if inrect(a, BODY["U1"]) != inrect(s["b"], BODY["U1"]):
                    cross_layer = LAY[s["layer"]]; break
        vin = first_via and inrect(first_via[1]["p"], BODY["U1"])
        if ring <= 1 and cross_layer != "L1":
            finding("%s (ring %d) leaves the MCU body on %s" % (short, ring, cross_layer))
        if ring >= 2 and (cross_layer != "L4" or not vin):
            finding("%s (ring %d) leaves the MCU body on %s, dog-bone via inside body: %s" % (short, ring, cross_layer, vin))
        for k, s, r in path:
            if k == "via":
                ina = [a for a, rect in AREA.items() if inrect(s["p"], rect)]
                want = (0.30, 0.15) if ina else (0.45, 0.20)
                if abs(s["d"] - want[0]) > 1e-6 or abs(s["drill"] - want[1]) > 1e-6:
                    finding("%s via at %s is %.2f/%.2f, expected %.2f/%.2f" % (short, s["p"], s["d"], s["drill"], want[0], want[1]))
                if not ina:
                    gap_vias.append((short, s["p"]))
                if set(s["layers"]) != {"F.Cu", "B.Cu"}:
                    finding("%s via layers %s" % (short, s["layers"]))
        print("  %-6s ball %-4s ring %d leaves body on %s%s" % (short, ball, ring, cross_layer, ", dog-bone" if vin else ""))
    print("vias outside both rule areas: %d %s" % (len(gap_vias), gap_vias))

    # ---- widths against the rule areas
    thin_out, wide_in = {}, 0.0
    for s in B["segs"] + B["arcs"]:
        if not s["net"].startswith("/FMC_"):
            continue
        pts = seg_pts(s["a"], s["b"], 0.005) if "m" not in s else arc_pts(s, 0.005)
        ins = [any(inrect(p, r) for r in AREA.values()) for p in pts]
        L = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))
        if abs(s["w"] - 0.09) < 1e-6:
            out_len = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1) if not (ins[i] and ins[i + 1]))
            if not any(ins):
                finding("0.09 track of %s does not touch a rule area: %s-%s" % (s["net"], s["a"], s["b"]))
            far = max([min(max(r[0] - p[0], p[0] - r[2], r[1] - p[1], p[1] - r[3]) for r in AREA.values()) for p in pts])
            if far > 0.4 + 1e-3:      # 0.3 by convention; up to 0.4 where a bend follows within 0.1 mm of the cut (shared builder)
                finding("0.09 track of %s reaches %.3f mm outside a rule area: %s-%s" % (s["net"], far, s["a"], s["b"]))
            elif far > 0.3 + 1e-3:
                print("  note: 0.09 track of %s reaches %.3f mm outside a rule area (bend within 0.1 mm of the 0.3 cut): %s-%s" % (s["net"][5:], far, s["a"], s["b"]))
            thin_out[s["net"][5:]] = thin_out.get(s["net"][5:], 0.0) + out_len
        elif abs(s["w"] - 0.1016) < 1e-6:
            if all(ins):
                wide_in += L
                finding("0.1016 track of %s wholly inside a rule area: %s-%s" % (s["net"], s["a"], s["b"]))
            elif any(ins):
                il = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1) if ins[i] and ins[i + 1])
                if il > 0.011:
                    finding("0.1016 track of %s runs %.3f mm inside a rule area: %s-%s" % (s["net"], il, s["a"], s["b"]))
        else:
            finding("width %.4f on %s" % (s["w"], s["net"]))
    print("\n0.09 track outside the rule areas, per net (allowed up to 0.3 per crossing):", {k: round(v, 3) for k, v in sorted(thin_out.items())})

    # ---- shape: directions, corners, arc joints
    nbad = 0
    for n in nets:
        path = R[n]["path"]
        for i, (k, s, r) in enumerate(path):
            if k == "seg":
                dx, dy = s["b"][0] - s["a"][0], s["b"][1] - s["a"][1]
                L = math.hypot(dx, dy)
                ang = math.degrees(math.atan2(dy, dx)) % 45
                if min(ang, 45 - ang) > 1e-3:
                    finding("%s: segment %s-%s is not 0/45/90 (%.4f deg off)" % (n, s["a"], s["b"], min(ang, 45 - ang))); nbad += 1
                if L < 0.1 - 1e-6:
                    finding("%s: segment of %.4f mm at %s" % (n, L, s["a"]))
            if i and k != "via" and path[i - 1][0] != "via":
                t0 = tangent(*path[i - 1], at_end=True)
                t1 = tangent(*path[i], at_end=False)
                turn = math.degrees(math.acos(max(-1, min(1, t0[0] * t1[0] + t0[1] * t1[1]))))
                isarc = k == "arc" or path[i - 1][0] == "arc"
                if isarc and turn > 0.2:
                    finding("%s: arc joint not tangent (%.2f deg) at %s" % (n, turn, s["a"])); nbad += 1
                if not isarc and turn > 45.01:
                    finding("%s: corner of %.1f deg turn at %s on %s" % (n, turn, (s["b"] if r else s["a"]), s["layer"])); nbad += 1
            if k == "via" and 0 < i < len(path) - 1:
                t0 = tangent(*path[i - 1], at_end=True); t1 = tangent(*path[i + 1], at_end=False)
                turn = math.degrees(math.acos(max(-1, min(1, t0[0] * t1[0] + t0[1] * t1[1]))))
                if turn >= 89.9:
                    print("  note: %s turns %.0f deg at the via %s" % (n[5:], turn, s["p"]))
    print("shape: %d direction / corner / tangent problems" % nbad)

    # ---- gaps, same layer, different nets (copper to copper), tracks sampled every 0.01 mm
    samp = {}      # (layer) -> list of (net, pts array, halfwidth, serp flag)
    BL = {n: blocks_of(R[n]["path"]) for n in nets}
    for n in nets:
        path = R[n]["path"]
        inblock = set()
        for b in BL[n]:
            inblock |= set(range(b["i0"], b["i1"] + 1))
        for i, (k, s, r) in enumerate(path):
            if k == "via":
                continue
            pts = np.array(seg_pts(s["a"], s["b"], 0.01) if k == "seg" else arc_pts(s, 0.01))
            samp.setdefault(s["layer"], []).append((n, pts, s["w"] / 2, i in inblock))
    others = []    # round copper: vias (all three layers) and pads (F.Cu)
    for v in B["vias"]:
        for l in LAY:
            others.append((l, v["net"], v["p"], v["d"] / 2, "via"))
    for p in B["pads"]:
        others.append(("F.Cu", p["net"], p["p"], p["d"] / 2, "pad %s.%s" % (p["ref"], p["name"])))
    best_all, best_serp, viol = None, None, 0
    pair_min = {}
    for layer, lst in samp.items():
        for i in range(len(lst)):
            ni, Pi, hi, si = lst[i]
            for j in range(i + 1, len(lst)):
                nj, Pj, hj, sj = lst[j]
                if ni == nj:
                    continue
                if Pi[:, 0].min() - Pj[:, 0].max() > 1.5 or Pj[:, 0].min() - Pi[:, 0].max() > 1.5 or Pi[:, 1].min() - Pj[:, 1].max() > 1.5 or Pj[:, 1].min() - Pi[:, 1].max() > 1.5:
                    continue
                D = np.hypot(Pi[:, None, 0] - Pj[None, :, 0], Pi[:, None, 1] - Pj[None, :, 1])
                k = np.unravel_index(np.argmin(D), D.shape)
                g = float(D[k]) - hi - hj
                at = (round(float(Pi[k[0], 0]), 3), round(float(Pi[k[0], 1]), 3))
                need = 0.09 if any(inrect(at, r) for r in AREA.values()) else 0.127
                rec = (g, ni[5:], nj[5:], LAY[layer], at, need)
                if g < need - 1e-4:
                    viol += 1; finding("gap %.4f < %.3f: %s / %s on %s at %s" % rec[:1] + (need,) + rec[1:5]) if False else finding("gap %.4f (need %.3f) %s / %s on %s at %s" % (g, need, ni[5:], nj[5:], LAY[layer], at))
                if best_all is None or g < best_all[0]:
                    best_all = rec
                if (si or sj) and (best_serp is None or g < best_serp[0]):
                    best_serp = rec
                if si or sj:
                    kk = tuple(sorted((ni[5:], nj[5:]))) + (LAY[layer],)
                    if kk not in pair_min or g < pair_min[kk][0]:
                        pair_min[kk] = rec
            for (l, nn, c, rad, what) in others:
                if l != layer or nn == ni:
                    continue
                d = np.hypot(Pi[:, 0] - c[0], Pi[:, 1] - c[1])
                k = int(np.argmin(d))
                g = float(d[k]) - hi - rad
                at = (round(float(Pi[k, 0]), 3), round(float(Pi[k, 1]), 3))
                need = 0.09 if any(inrect(at, r) for r in AREA.values()) else 0.127
                rec = (g, ni[5:], (nn[5:] if nn.startswith("/FMC_") else nn) + " " + what, LAY[layer], at, need)
                if g < need - 1e-4:
                    viol += 1; finding("gap %.4f (need %.3f) %s / %s on %s at %s" % (g, need, rec[1], rec[2], rec[3], at))
                if best_all is None or g < best_all[0]:
                    best_all = rec
                if si and (best_serp is None or g < best_serp[0]):
                    best_serp = rec
                if si and g < 0.3:
                    kk = (rec[1], rec[2], LAY[layer])
                    if kk not in pair_min or g < pair_min[kk][0]:
                        pair_min[kk] = rec
    print("\ngaps: smallest overall %.4f (%s / %s, %s at %s, need %.3f); clearance violations %d" % (best_all + (viol,)))
    if best_serp:
        print("gaps: smallest at a serpentine %.4f (%s / %s, %s at %s, need %.3f)" % best_serp)
        for kk, rec in sorted(pair_min.items(), key=lambda t: t[1][0])[:8]:
            print("      %.4f  %s / %s  %s at %s" % rec[:5])

    # ---- serpentines
    print("\nserpentines (net, layer, side, humps x height, pitch by crossings, arc radii, gain, under SDRAM body, leads):")
    tot_gain = tot_under = 0.0
    nb = nh = 0
    exc = []
    for n in nets:
        short = n[5:]
        m = M["nets"]["FMC_" + short]
        g_net = u_net = 0.0
        for b in BL[n]:
            hs = [abs(x) for x in b["humps"]]
            eq = max(hs) - min(hs) < 2e-3
            under = b["gain"] * b["under"] / b["copper"]
            g_net += b["gain"]; u_net += under
            nb += 1; nh += len(hs)
            # distance to the rule-area edges when on wide track
            edge = None
            if abs(b["w"] - 0.1016) < 1e-6:
                P = b["pts"]
                edge = min(float(np.min(np.maximum.reduce([r[0] - P[:, 0], P[:, 0] - r[2], r[1] - P[:, 1], P[:, 1] - r[3]]))) for r in AREA.values()) - b["w"] / 2
            else:
                P = b["pts"]
                ins = [r for r in AREA.values() if inrect(b["start"], r)]
                if not ins or not all(inrect((x, y), ins[0], -b["w"] / 2) for x, y in P):
                    finding("%s: serpentine on 0.09 track leaves its rule area" % short)
            if b["layer"] == "L1":
                for p in B["pads"]:
                    dmin = float(np.min(np.hypot(b["pts"][:, 0] - p["p"][0], b["pts"][:, 1] - p["p"][1])))
                    if dmin < 0.6:
                        finding("%s: L1 serpentine %.3f mm from ball %s.%s" % (short, dmin, p["ref"], p["name"]))
            print("  %-6s %s %-6s %d x %s  pitch %s  r %s sweep %s  gain %.4f  under body %.4f  lead %.3f / %.3f%s%s" % (
                short, b["layer"], "both" if b["both"] else "single", len(hs), ("%.3f" % hs[0]) if eq else str([round(x, 3) for x in hs]),
                b["pitch"], b["radii"], b["sweeps"], b["gain"], under, b["lead_before"], b["lead_after"],
                ("  to rule-area edge %.3f" % edge) if edge is not None else "", "" if eq else "  UNEQUAL"))
            if not eq:
                exc.append(short); finding("%s: unequal hump heights in one block %s" % (short, [round(x, 3) for x in hs]))
            want = 0.5 if short == "SDCLK" else None
            for p in b["pitch"]:
                if p < (0.5 if short == "SDCLK" else 0.3) - 2e-3:
                    finding("%s: leg pitch %.3f" % (short, p))
            for rr in b["radii"]:
                if b["pitch"] and abs(2 * rr - b["pitch"][0]) > 2e-3:
                    finding("%s: arc radius %.3f is not half the pitch %.3f" % (short, rr, b["pitch"][0]))
            if len(b["pitch"]) > 1 and b["pitch"][-1] - b["pitch"][0] > 2e-3:
                finding("%s: uneven leg pitch %s" % (short, b["pitch"]))
            if min(b["lead_before"], b["lead_after"]) < 0.35 - 1e-3:
                print("     note: lead %.3f / %.3f below 0.35 (may be a width change, not a bend)" % (b["lead_before"], b["lead_after"]))
            if len(hs) == 1:
                finding("%s: lone hump" % short)
        tot_gain += g_net; tot_under += u_net
        if abs(g_net - m["serpentine_mm"]) > 5e-3:
            finding("%s: serpentine gain %.4f vs metrics %.4f" % (short, g_net, m["serpentine_mm"]))
        if abs(u_net - m["serpentine_under_sdram_mm"]) > 0.05:
            finding("%s: serpentine under SDRAM %.4f vs metrics %.4f" % (short, u_net, m["serpentine_under_sdram_mm"]))
        if len(BL[n]) != m["n_serpentines"] or sum(len(b["humps"]) for b in BL[n]) != m["n_humps"]:
            finding("%s: blocks/humps %d/%d vs metrics %d/%d" % (short, len(BL[n]), sum(len(b["humps"]) for b in BL[n]), m["n_serpentines"], m["n_humps"]))
        route = R[n]["length"] - g_net
        if abs(route - m["route_mm"]) > 5e-3 or abs(route - R[n]["direct"] - m["detour_mm"]) > 5e-3:
            finding("%s: route %.4f detour %.4f vs metrics %.4f %.4f" % (short, route, route - R[n]["direct"], m["route_mm"], m["detour_mm"]))
        R[n]["route"] = route
    print("serpentine total %.3f mm in %d blocks / %d humps; under the SDRAM body %.3f mm = %.1f%% (metrics %.3f, %.1f%%)" % (
        tot_gain, nb, nh, tot_under, 100 * tot_under / tot_gain if tot_gain else 0, M["totals"]["serpentine_under_sdram_mm"], 100 * M["totals"]["serpentine_under_sdram_share"]))
    print("total detour %.3f (metrics %.3f)" % (sum(R[n]["route"] - R[n]["direct"] for n in nets), M["totals"]["total_detour_mm"]))
    if abs(sum(R[n]["route"] - R[n]["direct"] for n in nets) - M["totals"]["total_detour_mm"]) > 0.02:
        finding("total detour differs from metrics")

    # ---- space
    pts_all, pts_lay = [], {"L1": [], "L4": [], "L6": []}
    for s in B["segs"] + B["arcs"]:
        if not s["net"].startswith("/FMC_"):
            continue
        pp = seg_pts(s["a"], s["b"], 0.005) if "m" not in s else arc_pts(s, 0.005)
        pp = [p for p in pp if not inrect(p, BODY["U1"], -1e-9) and not inrect(p, BODY["U2"], -1e-9)]
        pts_all += pp; pts_lay[LAY[s["layer"]]] += pp
    for v in B["vias"]:
        if v["net"].startswith("/FMC_") and not inrect(v["p"], BODY["U1"], -1e-9) and not inrect(v["p"], BODY["U2"], -1e-9):
            pts_all.append(v["p"])
    A = hull_area(pts_all)
    xs, ys = [p[0] for p in pts_all], [p[1] for p in pts_all]
    ch = [p[1] for p in pts_all if STRIP[0] - 1e-9 <= p[0] <= STRIP[1] + 1e-9]
    print("\nspace: hull %.2f mm2 (metrics %.2f); bbox %.3f x %.3f, x %.3f..%.3f y %.3f..%.3f (metrics %s)" % (
        A, M["space"]["bus_hull_area_mm2"], max(xs) - min(xs), max(ys) - min(ys), min(xs), max(xs), min(ys), max(ys), M["space"]["bus_bbox_mm"]))
    print("space: channel (x 19-22) %.3f, y %.3f..%.3f (metrics %.3f); by layer %s (metrics %s)" % (
        max(ch) - min(ch), min(ch), max(ch), M["space"]["channel_width_mm"],
        {L: round(max(q[1] for q in v if 19 - 1e-9 <= q[0] <= 22 + 1e-9) - min(q[1] for q in v if 19 - 1e-9 <= q[0] <= 22 + 1e-9), 3) for L, v in pts_lay.items()},
        M["space"]["channel_width_by_layer_mm"]))
    if abs(A - M["space"]["bus_hull_area_mm2"]) > 0.3:
        finding("hull area %.2f vs metrics %.2f" % (A, M["space"]["bus_hull_area_mm2"]))
    if abs(max(ch) - min(ch) - M["space"]["channel_width_mm"]) > 0.02:
        finding("channel width %.3f vs metrics %.3f" % (max(ch) - min(ch), M["space"]["channel_width_mm"]))
    if abs(max(xs) - min(xs) - M["space"]["bus_bbox_mm"][0]) > 0.02 or abs(max(ys) - min(ys) - M["space"]["bus_bbox_mm"][1]) > 0.02:
        finding("bbox differs from metrics")
    # hull of the bus without serpentine copper, to see what the serpentines cost
    # lanes in the strip per layer: x positions of vertical tracks crossing y = 12 (a look at bundle spacing)
    for yy in (10.0, 12.0, 14.0):
        row = sorted((round(s["a"][0], 3), s["net"][5:], LAY[s["layer"]]) for s in B["segs"] if s["net"].startswith("/FMC_")
                     and abs(s["a"][0] - s["b"][0]) < 1e-6 and min(s["a"][1], s["b"][1]) <= yy <= max(s["a"][1], s["b"][1]) and 18.9 < s["a"][0] < 23.1)
        print("  vertical tracks crossing y=%.0f between x 19 and 23: %s" % (yy, row))

    # ---- sibling: same routes?
    if "--same" in sys.argv:
        other = sys.argv[sys.argv.index("--same") + 1]
        B2 = load(os.path.join(ROOT, "out", other, "routetune.kicad_pcb"))
        diff = 0
        for n in nets:
            a, b = skeleton(B, n), skeleton(B2, n)
            if a != b:
                diff += 1
                finding("route of %s differs from %s" % (n, other))
                for x, y in zip(a, b):
                    if x != y:
                        print("     ", x, "|", y); break
        print("\nroutes compared with %s (serpentines replaced by their chord, collinear pieces merged): %d of %d nets differ" % (other, diff, len(nets)))

    print("\nFINDINGS (%d)" % len(FIND))
    for f in FIND:
        print("  - " + f)


if __name__ == "__main__":
    main()
