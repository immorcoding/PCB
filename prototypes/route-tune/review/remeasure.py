"""REVIEW (issue 21): independent re-measurement of a built variant. Uses NOTHING from lib/ and no pcbnew:
the board file is parsed as text, the DRC length probe is run here with its own rule file.

    python review/remeasure.py <key>          (any Python 3.8+, run from prototypes/route-tune)

Prints every disagreement with out/<key>/metrics.json:  length > 0.01 mm, area > 2 %, anything else unequal.
Exit code 1 when there is a finding.
"""
import json, math, os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = r"D:\KiCad\bin\kicad-cli.exe"
KI = r"D:\KiCad\share\kicad"
ROWS = "ABCDEFGHJKLMNPR"
BODY = {"U1": (8, 7, 18, 17), "U2": (23, 9.4, 31, 22.4)}          # package outlines, local mm (file mm - 100)
AREA = {"BGA_MCU": (7, 6, 19, 18), "BGA_SDRAM": (22, 8.4, 32, 23.4)}
CU = {"F.Cu": "L1", "In1.Cu": "L2", "In2.Cu": "L3", "In3.Cu": "L4", "In4.Cu": "L5", "B.Cu": "L6"}
# independent copies of the research tables (typed from the git sources, not imported from lib/balls.py)
MCU = dict(D0="M14", D1="L14", D2="B12", D3="C12", D4="R8", D5="P8", D6="P9", D7="R9", D8="P10", D9="R10", D10="N11",
           D11="P11", D12="R11", D13="P15", D14="P14", D15="N15", NBL0="A4", NBL1="A3", SDCLK="H14")
MCU_PORT = dict(D0="PD14", D1="PD15", D2="PD0", D3="PD1", D4="PE7", D5="PE8", D6="PE9", D7="PE10", D8="PE11", D9="PE12",
                D10="PE13", D11="PE14", D12="PE15", D13="PD8", D14="PD9", D15="PD10", NBL0="PE0", NBL1="PE1", SDCLK="PG8")
SDR = """A DQ26 DQ24 VSS VDD DQ23 DQ21|B DQ28 VDDQ VSSQ VDDQ VSSQ DQ19|C VSSQ DQ27 DQ25 DQ22 DQ20 VDDQ|D VSSQ DQ29 DQ30 DQ17 DQ18 VDDQ
|E VDDQ DQ31 NC NC DQ16 VSSQ|F VSS DQM3 A3 A2 DQM2 VDD|G A4 A5 A6 A10 A0 A1|H A7 A8 A12 NC BA1 A11|J CLK CKE A9 BA0 CS# RAS#
|K DQM1 NC NC CAS# WE# DQM0|L VDDQ DQ8 VSS VDD DQ7 VSSQ|M VSSQ DQ10 DQ9 DQ6 DQ5 VDDQ|N VSSQ DQ12 DQ14 DQ1 DQ3 VDDQ
|P DQ11 VDDQ VSSQ VDDQ VSSQ DQ4|R DQ13 DQ15 VSS VDD DQ0 DQ2"""
SDR_PIN = {}
for row in SDR.replace("\n", "").split("|"):
    p = row.split()
    for col, nm in zip((1, 2, 3, 7, 8, 9), p[1:]):
        SDR_PIN[p[0] + str(col)] = nm


def parse(text):
    """Minimal s-expression reader -> nested lists of strings."""
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


def kids(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def kid(node, name):
    k = kids(node, name)
    return k[0] if k else None


def xy(n):
    return (float(n[1]) - 100, float(n[2]) - 100)


def arc_len(s, m, e):
    ax, ay = s; bx, by = m; cx, cy = e
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    a0, am, a1 = (math.atan2(y - uy, x - ux) for x, y in (s, m, e))
    sw = (a1 - a0) % (2 * math.pi)
    if (am - a0) % (2 * math.pi) > sw:
        sw -= 2 * math.pi
    return r * abs(sw), (ux, uy), r, a0, sw


def load(pcb):
    root = parse(open(pcb, encoding="utf-8").read())
    z, zc = 0.0, {}
    for l in kids(kid(kid(root, "setup"), "stackup"), "layer"):
        th = kid(l, "thickness")
        th = float(th[1]) if th else 0.0
        if l[1] in CU:
            zc[CU[l[1]]] = (z, z + th)
        if l[1] in CU or l[1].startswith("dielectric"):
            z += th if l[1] in CU or True else 0
        # masks are above F.Cu / below B.Cu: reset z so that the top of F.Cu is 0
        if l[1] == "F.Mask":
            z = 0.0
    segs, arcs, vias, pads, zones = [], [], [], {}, []
    for n in root[1:]:
        if not isinstance(n, list):
            continue
        if n[0] == "segment":
            segs.append({"a": xy(kid(n, "start")), "c": xy(kid(n, "end")), "w": float(kid(n, "width")[1]), "l": CU[kid(n, "layer")[1]], "net": kid(n, "net")[1]})
        elif n[0] == "arc":
            s, m, e = xy(kid(n, "start")), xy(kid(n, "mid")), xy(kid(n, "end"))
            L, c, r, a0, sw = arc_len(s, m, e)
            arcs.append({"a": s, "m": m, "c": e, "w": float(kid(n, "width")[1]), "l": CU[kid(n, "layer")[1]], "net": kid(n, "net")[1], "len": L, "ctr": c, "r": r, "a0": a0, "sw": sw})
        elif n[0] == "via":
            vias.append({"at": xy(kid(n, "at")), "size": float(kid(n, "size")[1]), "drill": float(kid(n, "drill")[1]), "net": kid(n, "net")[1], "layers": kid(n, "layers")[1:]})
        elif n[0] == "footprint":
            ref = [p[2] for p in kids(n, "property") if p[1] == "Reference"][0]
            o = xy(kid(n, "at"))
            for p in kids(n, "pad"):
                at = kid(p, "at"); nt = kid(p, "net")
                pads[(ref, p[1])] = {"xy": (o[0] + float(at[1]), o[1] + float(at[2])), "size": float(kid(p, "size")[1]), "net": nt[-1] if nt else ""}
        elif n[0] == "zone":
            pts = [(float(q[1]) - 100, float(q[2]) - 100) for q in kids(kid(kid(n, "polygon"), "pts"), "xy")]
            nm = kid(n, "name")
            zones.append({"name": nm[1] if nm else "", "rule_area": kid(n, "keepout") is not None or kid(n, "placement") is not None,
                          "layers": (kid(n, "layers") or kid(n, "layer"))[1:], "bbox": (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)), "n": len(pts)})
    return {"z": zc, "segs": segs, "arcs": arcs, "vias": vias, "pads": pads, "zones": zones}


def z_of(zc, layer):
    """Height at which DRC attaches a via to a layer: outer surface for L1 / L6, mid-plane for inner layers.
    (Found by fitting; the comparison with the DRC lengths below is what tests it.)"""
    top, bot = zc[layer]
    return top if layer == "L1" else bot if layer == "L6" else (top + bot) / 2


def lengths(b):
    key = lambda p: (round(p[0], 5), round(p[1], 5))
    out = {}
    for net in sorted({t["net"] for t in b["segs"] + b["arcs"] if t["net"].startswith("/FMC_")}):
        lay, ends = {}, {}
        for t in b["segs"]:
            if t["net"] == net:
                lay[t["l"]] = lay.get(t["l"], 0) + math.dist(t["a"], t["c"])
                for p in (t["a"], t["c"]):
                    ends.setdefault(key(p), set()).add(t["l"])
        for t in b["arcs"]:
            if t["net"] == net:
                lay[t["l"]] = lay.get(t["l"], 0) + t["len"]
                for p in (t["a"], t["c"]):
                    ends.setdefault(key(p), set()).add(t["l"])
        vh, nv = 0.0, 0
        for v in b["vias"]:
            if v["net"] == net:
                nv += 1
                ls = sorted(ends.get(key(v["at"]), ()))
                if len(ls) >= 2:
                    vh += abs(z_of(b["z"], ls[-1]) - z_of(b["z"], ls[0]))
        out[net[1:]] = {"length": sum(lay.values()) + vh, "vias": nv, "via_mm": vh, "layers": lay}
    return out


def drc_probe(vdir):
    tmp = tempfile.mkdtemp(prefix="review_probe_")
    try:
        for ext in (".kicad_pcb", ".kicad_pro"):
            shutil.copy(os.path.join(vdir, "routetune" + ext), os.path.join(tmp, "routetune" + ext))
        open(os.path.join(tmp, "routetune.kicad_dru"), "w").write('(version 1)\n(rule "p"\n  (condition "A.NetName == \'/FMC_*\'")\n  (constraint length (max 0.001mm)))\n')
        subprocess.run([CLI, "pcb", "drc", "--severity-all", "--units", "mm", "--format", "json", "-o", os.path.join(tmp, "o.json"), os.path.join(tmp, "routetune.kicad_pcb")], capture_output=True)
        d = json.load(open(os.path.join(tmp, "o.json"), encoding="utf-8"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    got = {}
    for v in d["violations"]:
        if v["type"] == "length_out_of_range":
            net = re.search(r"\[(/FMC_\w+)\]", v["items"][0]["description"]).group(1)[1:]
            got[net] = float(re.findall(r"(-?\d+\.\d+) mm", v["description"])[-1])
    return got


def bus_points(b, step=0.005):
    pts = []
    for t in b["segs"]:
        if t["net"].startswith("/FMC_"):
            n = max(1, int(math.dist(t["a"], t["c"]) / step))
            pts += [(t["a"][0] + (t["c"][0] - t["a"][0]) * i / n, t["a"][1] + (t["c"][1] - t["a"][1]) * i / n, t["l"]) for i in range(n + 1)]
    for t in b["arcs"]:
        if t["net"].startswith("/FMC_"):
            n = max(8, int(t["len"] / step))
            pts += [(t["ctr"][0] + t["r"] * math.cos(t["a0"] + t["sw"] * i / n), t["ctr"][1] + t["r"] * math.sin(t["a0"] + t["sw"] * i / n), t["l"]) for i in range(n + 1)]
    for v in b["vias"]:
        if v["net"].startswith("/FMC_"):
            pts.append((v["at"][0], v["at"][1], "via"))
    inside = lambda p, R: R[0] <= p[0] <= R[2] and R[1] <= p[1] <= R[3]
    return [p for p in pts if not any(inside(p, R) for R in BODY.values())]


def hull_area(pts):
    P = sorted(set((round(p[0], 4), round(p[1], 4)) for p in pts))
    cr = lambda o, a, c: (a[0] - o[0]) * (c[1] - o[1]) - (a[1] - o[1]) * (c[0] - o[0])
    lo, up = [], []
    for p in P:
        while len(lo) > 1 and cr(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(up) > 1 and cr(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    h = lo[:-1] + up[:-1]
    return abs(sum(h[i][0] * h[(i + 1) % len(h)][1] - h[(i + 1) % len(h)][0] * h[i][1] for i in range(len(h)))) / 2


def seg_seg(a, c, p, q):
    """Distance between two segments (0 when they cross)."""
    def d_pt(x, s, e):
        vx, vy = e[0] - s[0], e[1] - s[1]
        L2 = vx * vx + vy * vy
        t = 0 if L2 == 0 else max(0, min(1, ((x[0] - s[0]) * vx + (x[1] - s[1]) * vy) / L2))
        return math.hypot(x[0] - s[0] - t * vx, x[1] - s[1] - t * vy)
    o = lambda u, v, w: (v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0])
    if o(a, c, p) * o(a, c, q) < 0 and o(p, q, a) * o(p, q, c) < 0:
        return 0.0
    return min(d_pt(a, p, q), d_pt(c, p, q), d_pt(p, a, c), d_pt(q, a, c))


def gaps(b):
    """Smallest copper gap between different nets per signal layer, crossings, and gaps below the clearance of the place."""
    touch = lambda pts, hw: any(R[0] - hw <= p[0] <= R[2] + hw and R[1] - hw <= p[1] <= R[3] + hw for R in AREA.values() for p in pts)
    out = {"cross": [], "viol": [], "min": {}}
    for layer in ("L1", "L4", "L6"):
        items = []
        for t in b["segs"]:
            if t["l"] == layer:
                items.append((t["net"], [t["a"], t["c"]], t["w"] / 2))
        for t in b["arcs"]:
            if t["l"] == layer:
                n = max(6, int(t["len"] / 0.02))
                items.append((t["net"], [(t["ctr"][0] + t["r"] * math.cos(t["a0"] + t["sw"] * i / n), t["ctr"][1] + t["r"] * math.sin(t["a0"] + t["sw"] * i / n)) for i in range(n + 1)], t["w"] / 2))
        for v in b["vias"]:
            items.append((v["net"], [v["at"], v["at"]], v["size"] / 2))
        if layer == "L1":
            for (ref, num), p in b["pads"].items():
                items.append((p["net"] or "%s.%s" % (ref, num), [p["xy"], p["xy"]], p["size"] / 2))
        boxes = [(min(p[0] for p in it[1]) - it[2], min(p[1] for p in it[1]) - it[2], max(p[0] for p in it[1]) + it[2], max(p[1] for p in it[1]) + it[2]) for it in items]
        best = None
        for i in range(len(items)):
            if not items[i][0].startswith("/FMC_"):
                continue
            for j in range(len(items)):
                if j == i or items[j][0] == items[i][0] or (items[j][0].startswith("/FMC_") and j < i):
                    continue
                A, Bx = boxes[i], boxes[j]
                if A[0] > Bx[2] + 0.3 or Bx[0] > A[2] + 0.3 or A[1] > Bx[3] + 0.3 or Bx[1] > A[3] + 0.3:
                    continue
                d = min(seg_seg(a, c, p, q) for a, c in zip(items[i][1], items[i][1][1:]) for p, q in zip(items[j][1], items[j][1][1:]))
                g = d - items[i][2] - items[j][2]
                need = 0.09 if touch(items[i][1], items[i][2]) or touch(items[j][1], items[j][2]) else 0.127
                rec = (round(g, 4), items[i][0], items[j][0], layer, [round(v, 3) for v in items[i][1][0]])
                if d == 0.0:
                    out["cross"].append(rec)
                if g < need - 1e-4:
                    out["viol"].append(rec + (need,))
                if best is None or g < best[0]:
                    best = rec
        out["min"][layer] = best
    return out


def shape(b):
    """0/45/90 only, bends of at most 45 degrees, arcs tangent to their neighbours, no T junction, no loose end."""
    bad = []
    node = lambda p, l, n: (n, l, round(p[0], 5), round(p[1], 5))
    at = {}
    for t in b["segs"] + b["arcs"]:
        if not t["net"].startswith("/FMC_"):
            continue
        if "len" not in t:
            dx, dy = abs(t["c"][0] - t["a"][0]), abs(t["c"][1] - t["a"][1])
            if min(dx, dy) > 2e-6 and abs(dx - dy) > 2e-6:
                bad.append("off 0/45/90: %s %s %s -> %s" % (t["net"], t["l"], t["a"], t["c"]))
            if math.hypot(dx, dy) < 0.1 - 1e-6:
                bad.append("segment shorter than 0.1: %s %s at %s (%.4f)" % (t["net"], t["l"], t["a"], math.hypot(dx, dy)))
        elif t["len"] < 0.1 - 1e-6:
            bad.append("arc shorter than 0.1: %s at %s" % (t["net"], t["a"]))
        for k, far in (("a", "c"), ("c", "a")):
            if "len" in t:                                   # direction of travel when LEAVING this end along the item
                ang = t["a0"] if k == "a" else t["a0"] + t["sw"]
                sgn = (1 if t["sw"] > 0 else -1) * (1 if k == "a" else -1)
                d = (-math.sin(ang) * sgn, math.cos(ang) * sgn)
            else:
                L = math.dist(t["a"], t["c"])
                d = ((t[far][0] - t[k][0]) / L, (t[far][1] - t[k][1]) / L)
            at.setdefault(node(t[k], t["l"], t["net"]), []).append((d, "len" in t))
    padxy = {(p["net"], round(p["xy"][0], 5), round(p["xy"][1], 5)) for p in b["pads"].values() if p["net"].startswith("/FMC_")}
    viaxy = {(v["net"], round(v["at"][0], 5), round(v["at"][1], 5)) for v in b["vias"]}
    for (net, l, x, y), ds in at.items():
        term = (net, x, y) in viaxy or (l == "L1" and (net, x, y) in padxy)
        if len(ds) != (1 if term else 2):
            bad.append("%s %s (%.3f, %.3f): %d track ends, expected %d" % (net, l, x, y, len(ds), 1 if term else 2))
        elif len(ds) == 2:
            (d1, a1), (d2, a2) = ds
            turn = math.degrees(math.acos(max(-1, min(1, -(d1[0] * d2[0] + d1[1] * d2[1])))))   # 0 = straight on
            if (a1 or a2) and turn > 0.1:
                bad.append("arc joint not tangent: %s %s (%.3f, %.3f) turn %.2f" % (net, l, x, y, turn))
            elif turn > 45.1:
                bad.append("bend sharper than 45: %s %s (%.3f, %.3f) turn %.1f" % (net, l, x, y, turn))
    return bad


def widths(b):
    bad = []
    ins = lambda p, R, g=0.0: R[0] - g <= p[0] <= R[2] + g and R[1] - g <= p[1] <= R[3] + g
    for t in b["segs"] + b["arcs"]:
        if not t["net"].startswith("/FMC_"):
            continue
        if "len" in t:
            ends = [t["a"], t["m"], t["c"]]
        else:                                                # sample the straight: a track may clip an area corner
            k = max(1, int(math.dist(t["a"], t["c"]) / 0.01))
            ends = [(t["a"][0] + (t["c"][0] - t["a"][0]) * i / k, t["a"][1] + (t["c"][1] - t["a"][1]) * i / k) for i in range(k + 1)]
        if abs(t["w"] - 0.09) < 1e-9:
            if not any(ins(p, R) for p in ends for R in AREA.values()):
                bad.append("0.09 track that does not touch a rule area: %s %s %s" % (t["net"], t["l"], t["a"]))
            far = max(min(max(R[0] - p[0], p[0] - R[2], R[1] - p[1], p[1] - R[3]) for R in AREA.values()) for p in ends)
            if far > 0.3 + 0.1 + 1e-6:                       # 0.3 by convention, + up to 0.1 when the cut is moved onto a bend
                bad.append("0.09 track reaches %.3f mm outside a rule area: %s %s %s" % (far, t["net"], t["l"], t["a"]))
        elif abs(t["w"] - 0.1016) < 1e-9:
            if any(ins(p, R, -1e-6) for p in ends for R in AREA.values()):
                bad.append("0.1016 track inside a rule area: %s %s %s -> %s" % (t["net"], t["l"], t["a"], t["c"]))
        else:
            bad.append("width %.4f: %s" % (t["w"], t["net"]))
    for v in b["vias"]:
        inside = any(ins(v["at"], R) for R in AREA.values())
        if (v["size"], v["drill"]) != ((0.3, 0.15) if inside else (0.45, 0.2)):
            bad.append("via %s at %s is %.2f/%.2f (%s a rule area)" % (v["net"], v["at"], v["size"], v["drill"], "inside" if inside else "outside"))
        if v["layers"] != ["F.Cu", "B.Cu"]:
            bad.append("via %s is not a through via" % v["net"])
    return bad


def balls(b):
    bad, swap = [], {}
    sym = open(os.path.join(KI, "symbols", "MCU_ST_STM32H7.kicad_sym"), encoding="utf-8").read()
    i = sym.find('(symbol "STM32H743IIKx"'); blk = sym[i:sym.find('\n\t(symbol "', i + 10)]
    m = re.search(r'\(extends "([^"]+)"', blk)
    if m:
        i = sym.find('(symbol "%s"' % m.group(1)); blk = sym[i:sym.find('\n\t(symbol "', i + 10)]
    pin = {nm: num for nm, num in re.findall(r'\(name "([^"]*)".*?\(number "([^"]*)"', blk, re.S)}
    for s, ball in MCU.items():
        if pin.get(MCU_PORT[s]) != ball:
            bad.append("KiCad symbol: %s is ball %s, the table says %s" % (MCU_PORT[s], pin.get(MCU_PORT[s]), ball))
        alts = re.search(r'\(name "%s".*?\(number "%s"\)?(.*?)\n\t\t\t\(pin ' % (MCU_PORT[s], ball), blk, re.S)
        if alts and ("FMC_" + s) not in alts.group(0):
            bad.append("KiCad symbol: %s has no alternate FMC_%s" % (MCU_PORT[s], s))
        p = b["pads"][("U1", ball)]
        r, c = ROWS.index(ball[0]), int(ball[1:])
        want = (13 + (c - 8) * 0.65, 12 + (r - 7) * 0.65)
        if p["net"] != "/FMC_" + s or math.dist(p["xy"], want) > 1e-6:
            bad.append("board: U1.%s is net %r at %s, expected /FMC_%s at %s" % (ball, p["net"], p["xy"], s, want))
    for (ref, num), p in b["pads"].items():
        if ref == "U2" and p["net"].startswith("/FMC_"):
            r, c = ROWS.index(num[0]), int(num[1:])
            want = (27 + {1: -3.2, 2: -2.4, 3: -1.6, 7: 1.6, 8: 2.4, 9: 3.2}[c], 15.9 - 5.6 + 0.8 * r)
            if math.dist(p["xy"], want) > 1e-6:
                bad.append("board: U2.%s at %s, expected %s" % (num, p["xy"], want))
            swap[p["net"][5:]] = (num, SDR_PIN[num])
        if ref == "U1" and p["net"].startswith("/FMC_") and MCU.get(p["net"][5:]) != num:
            bad.append("board: U1.%s carries %s" % (num, p["net"]))
    if sorted(swap) != sorted(MCU):
        bad.append("SDRAM side: nets present %s" % sorted(swap))
    if len({v[1] for v in swap.values()}) != 19:
        bad.append("an SDRAM pin is used twice")
    if swap.get("SDCLK", ("", ""))[1] != "CLK":
        bad.append("SDCLK goes to %s" % (swap.get("SDCLK"),))
    lanes = []
    for k in (0, 1):
        got = sorted(int(swap["D%d" % i][1][2:]) if swap["D%d" % i][1].startswith("DQ") and swap["D%d" % i][1][2:].isdigit() else -1 for i in range(8 * k, 8 * k + 8))
        if got not in (list(range(8)), list(range(8, 16))):
            bad.append("MCU byte lane %d lands on SDRAM pins %s (must be one whole lane DQ0-7 or DQ8-15)" % (k, got))
            continue
        lanes.append(got[0] // 8)
        if swap["NBL%d" % k][1] != "DQM%d" % (got[0] // 8):
            bad.append("NBL%d goes to %s but its lane went to SDRAM lane %d" % (k, swap["NBL%d" % k][1], got[0] // 8))
    if len(lanes) == 2 and lanes[0] == lanes[1]:
        bad.append("both MCU lanes on the same SDRAM lane")
    return bad, swap


def main():
    key = sys.argv[1]
    vdir = os.path.join(ROOT, "out", key)
    b = load(os.path.join(vdir, "routetune.kicad_pcb"))
    M = json.load(open(os.path.join(vdir, "metrics.json"), encoding="utf-8"))
    finds = []
    print("== %s" % key)
    print("stackup z (top, bottom) mm:", {k: (round(a, 4), round(c, 4)) for k, (a, c) in b["z"].items()})
    print("via heights: L1-L4 %.4f  L1-L6 %.4f  L4-L6 %.4f" % (z_of(b["z"], "L4") - z_of(b["z"], "L1"), z_of(b["z"], "L6") - z_of(b["z"], "L1"), z_of(b["z"], "L6") - z_of(b["z"], "L4")))
    g, d = lengths(b), drc_probe(vdir)
    print("net      mine      DRC(own probe)  metrics.json   vias  mine-DRC  metrics-DRC")
    for n in M["nets"]:
        m = M["nets"][n]
        print("%-10s %9.4f %9.4f %9.4f   %d   %+.4f  %+.4f" % (n, g[n]["length"], d.get(n, float("nan")), m["length_mm"], g[n]["vias"], g[n]["length"] - d.get(n, float("nan")), m["length_mm"] - d.get(n, float("nan"))))
        if n not in d:
            finds.append("%s: the review's own probe rule did not match this net" % n)
            continue
        if abs(g[n]["length"] - d[n]) > 0.01:
            finds.append("%s: board-file geometry %.4f vs DRC %.4f" % (n, g[n]["length"], d[n]))
        if abs(m["length_mm"] - d[n]) > 0.01:
            finds.append("%s: metrics.json length %.4f vs DRC %.4f" % (n, m["length_mm"], d[n]))
        if m["vias"] != g[n]["vias"]:
            finds.append("%s: metrics.json vias %d, board file %d" % (n, m["vias"], g[n]["vias"]))
        for l in ("L1", "L4", "L6"):
            if abs(m["layers"].get(l, 0) - g[n]["layers"].get(l, 0)) > 0.01:
                finds.append("%s: %s length metrics %.4f vs file %.4f" % (n, l, m["layers"].get(l, 0), g[n]["layers"].get(l, 0)))
        ball_u2 = [num for (ref, num), p in b["pads"].items() if ref == "U2" and p["net"] == "/" + n][0]
        a, c = b["pads"][("U1", MCU[n[4:]])]["xy"], b["pads"][("U2", ball_u2)]["xy"]
        dx, dy = abs(a[0] - c[0]), abs(a[1] - c[1])
        direct = max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)
        if abs(direct - m["direct_mm"]) > 0.01:
            finds.append("%s: direct_mm metrics %.4f vs %.4f" % (n, m["direct_mm"], direct))
        # serpentine gain from the board alone: arcs + the straight pieces between two arcs, minus the chord they replace
        if abs((m["route_mm"] + m["serpentine_mm"]) - m["length_mm"]) > 1e-3 or abs(m["detour_mm"] - (m["route_mm"] - m["direct_mm"])) > 1e-3:
            finds.append("%s: route/detour/serpentine do not add up" % n)
    pts = bus_points(b)
    ha = hull_area(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ch = [p[1] for p in pts if 19 <= p[0] <= 22]
    sp = M["space"]
    print("hull %.3f (metrics %.2f)  bbox %.3f x %.3f (metrics %s)  channel %.3f (metrics %.3f)" % (ha, sp["bus_hull_area_mm2"], max(xs) - min(xs), max(ys) - min(ys), sp["bus_bbox_mm"], max(ch) - min(ch), sp["channel_width_mm"]))
    if abs(ha - sp["bus_hull_area_mm2"]) > 0.02 * ha:
        finds.append("hull area: mine %.2f, metrics %.2f" % (ha, sp["bus_hull_area_mm2"]))
    if abs(max(xs) - min(xs) - sp["bus_bbox_mm"][0]) > 0.02 or abs(max(ys) - min(ys) - sp["bus_bbox_mm"][1]) > 0.02:
        finds.append("bbox: mine %.3f x %.3f, metrics %s" % (max(xs) - min(xs), max(ys) - min(ys), sp["bus_bbox_mm"]))
    if abs(max(ch) - min(ch) - sp["channel_width_mm"]) > 0.02:
        finds.append("channel width: mine %.3f, metrics %.3f" % (max(ch) - min(ch), sp["channel_width_mm"]))
    for l in ("L1", "L4", "L6"):
        cu = sum(math.dist(t["a"], t["c"]) * t["w"] for t in b["segs"] if t["l"] == l and t["net"].startswith("/FMC_")) + sum(t["len"] * t["w"] for t in b["arcs"] if t["l"] == l)
        if abs(cu - sp["copper_area_by_layer_mm2"].get(l, 0)) > 0.02 * max(cu, 0.01):
            finds.append("copper area %s: mine %.3f, metrics %.3f" % (l, cu, sp["copper_area_by_layer_mm2"].get(l, 0)))
    # serpentine totals from the board alone: per net, length - (length with every arc run replaced by its chord)
    tot = sum(M["nets"][n]["serpentine_mm"] for n in M["nets"])
    print("arcs %d (radii %s); serpentine total in metrics %.3f" % (len(b["arcs"]), sorted({round(a["r"], 4) for a in b["arcs"]}), tot))
    gp = gaps(b)
    print("smallest gap between nets per layer:", gp["min"])
    for c in gp["cross"]:
        finds.append("same-layer crossing: %s" % (c,))
    for c in gp["viol"]:
        finds.append("gap below clearance: %s" % (c,))
    for s in shape(b) + widths(b):
        finds.append(s)
    bb, swap = balls(b)
    finds += bb
    print("swap (net -> SDRAM ball, pin):", " ".join("%s=%s/%s" % (k, v[0], v[1]) for k, v in sorted(swap.items())))
    for n, m in M["nets"].items():
        if swap[n[4:]] != (m["sdram_ball"], m["sdram_pin"]):
            finds.append("%s: metrics says %s %s, the board pad is %s" % (n, m["sdram_ball"], m["sdram_pin"], swap[n[4:]]))
    ra = [z for z in b["zones"] if z["name"].startswith("BGA_")]
    for z in ra:
        if tuple(round(v, 6) for v in z["bbox"]) != tuple(float(v) for v in AREA[z["name"]]) or z["n"] != 4 or sorted(z["layers"]) != sorted(CU):
            finds.append("rule area %s: bbox %s, %d corners, layers %s" % (z["name"], z["bbox"], z["n"], z["layers"]))
    if len(ra) != 2:
        finds.append("%d rule areas named BGA_*" % len(ra))
    print("rule areas:", [(z["name"], z["bbox"], len(z["layers"])) for z in ra])
    print("\nFINDINGS (%d):" % len(finds))
    for f in finds:
        print("  - " + f)
    sys.exit(1 if finds else 0)


if __name__ == "__main__":
    main()
