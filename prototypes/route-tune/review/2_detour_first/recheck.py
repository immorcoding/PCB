"""PROTOTYPE review (issue 21): independent re-measurement of one variant's saved board.

Reads out/<key>/routetune.kicad_pcb as text (own S-expression reader, nothing from lib/, no pcbnew),
optionally runs its own DRC length probe with kicad-cli in a scratch folder, and compares with metrics.json.
Usage: python recheck.py <key> [--probe]
Coordinates printed are local mm (board mm - 100, y down).
"""
import json, math, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
CLI = r"D:\KiCad\bin\kicad-cli.exe"
BODY = {"U1": (8.0, 7.0, 18.0, 17.0), "U2": (23.0, 9.4, 31.0, 22.4)}
AREA = {"U1": (7.0, 6.0, 19.0, 18.0), "U2": (22.0, 8.4, 32.0, 23.4)}
STRIP = (19.0, 22.0)
LAY = {"F.Cu": "L1", "In3.Cu": "L4", "B.Cu": "L6"}
EPS = 1e-6


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


def kids(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def kid(node, name):
    k = kids(node, name)
    return k[0] if k else None


def in_rect(p, R, g=0.0):
    return R[0] - g <= p[0] <= R[2] + g and R[1] - g <= p[1] <= R[3] + g


def seg_dist(a, b, c, d):
    """Distance between segments ab and cd (0 when they cross)."""
    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    d1, d2, d3, d4 = cross(c, d, a), cross(c, d, b), cross(a, b, c), cross(a, b, d)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and abs(d1) > 1e-12 and abs(d2) > 1e-12:
        return 0.0
    return min(pt_seg(a, c, d), pt_seg(b, c, d), pt_seg(c, a, b), pt_seg(d, a, b))


def pt_seg(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    L2 = vx * vx + vy * vy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L2))
    return math.hypot(p[0] - a[0] - t * vx, p[1] - a[1] - t * vy)


def clip_outside(a, b, R):
    """Pieces of segment ab that lie outside rectangle R (list of (p, q))."""
    ts = [0.0, 1.0]
    for i, (lo, hi) in enumerate(((R[0], R[2]), (R[1], R[3]))):
        d = b[i] - a[i]
        if abs(d) > 1e-12:
            for v in (lo, hi):
                t = (v - a[i]) / d
                if 0 < t < 1:
                    ts.append(t)
    ts.sort()
    out = []
    for t0, t1 in zip(ts, ts[1:]):
        tm = (t0 + t1) / 2
        m = (a[0] + tm * (b[0] - a[0]), a[1] + tm * (b[1] - a[1]))
        if not (R[0] < m[0] < R[2] and R[1] < m[1] < R[3]):
            out.append(((a[0] + t0 * (b[0] - a[0]), a[1] + t0 * (b[1] - a[1])), (a[0] + t1 * (b[0] - a[0]), a[1] + t1 * (b[1] - a[1]))))
    return out


def hull(pts):
    pts = sorted(set(pts))
    def half(ps):
        h = []
        for p in ps:
            while len(h) >= 2 and (h[-1][0] - h[-2][0]) * (p[1] - h[-2][1]) - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0]) <= 0:
                h.pop()
            h.append(p)
        return h
    lo, up = half(pts), half(pts[::-1])
    return lo[:-1] + up[:-1]


def poly_area(h):
    return abs(sum(h[i][0] * h[(i + 1) % len(h)][1] - h[(i + 1) % len(h)][0] * h[i][1] for i in range(len(h)))) / 2


def load(key):
    d = os.path.join(ROOT, "out", key)
    tree = sexp(open(os.path.join(d, "routetune.kicad_pcb"), encoding="utf-8").read())
    segs, arcs, vias, pads = [], [], [], []
    for n in kids(tree, "segment"):
        net = kid(n, "net")[1]
        s, e = kid(n, "start"), kid(n, "end")
        segs.append({"a": (float(s[1]) - 100, float(s[2]) - 100), "b": (float(e[1]) - 100, float(e[2]) - 100),
                     "w": float(kid(n, "width")[1]), "layer": kid(n, "layer")[1], "net": net})
    for n in kids(tree, "arc"):
        s, m, e = kid(n, "start"), kid(n, "mid"), kid(n, "end")
        arcs.append({"a": (float(s[1]) - 100, float(s[2]) - 100), "m": (float(m[1]) - 100, float(m[2]) - 100), "b": (float(e[1]) - 100, float(e[2]) - 100),
                     "w": float(kid(n, "width")[1]), "layer": kid(n, "layer")[1], "net": kid(n, "net")[1]})
    for n in kids(tree, "via"):
        a = kid(n, "at")
        vias.append({"p": (float(a[1]) - 100, float(a[2]) - 100), "size": float(kid(n, "size")[1]), "drill": float(kid(n, "drill")[1]),
                     "layers": kid(n, "layers")[1:], "net": kid(n, "net")[1]})
    for fp in kids(tree, "footprint"):
        at = kid(fp, "at"); fx, fy = float(at[1]) - 100, float(at[2]) - 100
        rot = float(at[3]) if len(at) > 3 else 0.0
        ref = [p[2] for p in kids(fp, "property") if p[1] == "Reference"][0]
        for p in kids(fp, "pad"):
            pa = kid(p, "at"); net = kid(p, "net")
            assert rot == 0.0, "rotated footprint: this reader assumes rotation 0"
            pads.append({"ref": ref, "name": p[1], "p": (fx + float(pa[1]), fy + float(pa[2])), "d": float(kid(p, "size")[1]),
                         "net": (net[-1] if net else "")})
    # stackup: z of every copper layer's top and bottom
    z, cu = 0.0, {}
    for l in kids(kid(kid(tree, "setup"), "stackup"), "layer"):
        t = kid(l, "thickness")
        t = float(t[1]) if t else 0.0
        if l[1].endswith(".Cu"):
            cu[l[1]] = (z, z + t)
        if l[1].endswith(".Cu") or l[1].startswith("dielectric"):
            z += t
    zones = []
    for zn in kids(tree, "zone"):
        nm = kid(zn, "name")
        if nm and kid(zn, "keepout") is None and nm[1].startswith("BGA"):
            pts = kids(kid(kid(zn, "polygon"), "pts"), "xy")
            xs = [float(p[1]) - 100 for p in pts]; ys = [float(p[2]) - 100 for p in pts]
            zones.append((nm[1], (min(xs), min(ys), max(xs), max(ys)), (kid(zn, "layers") or kid(zn, "layer"))[1:]))
        elif nm and nm[1].startswith("BGA"):
            pts = kids(kid(kid(zn, "polygon"), "pts"), "xy")
            xs = [float(p[1]) - 100 for p in pts]; ys = [float(p[2]) - 100 for p in pts]
            zones.append((nm[1], (min(xs), min(ys), max(xs), max(ys)), (kid(zn, "layers") or kid(zn, "layer"))[1:]))
    return d, segs, arcs, vias, pads, cu, zones


def via_h(cu, la, lb):
    """Via length as DRC counts it: outer surface of an outer layer, mid-plane of an inner layer."""
    def zz(l):
        t, b = cu[l]
        return t if l == "F.Cu" else b if l == "B.Cu" else (t + b) / 2
    return abs(zz(la) - zz(lb))


def probe(d, nets):
    """Own DRC length probe: copy the project, append a rule no net can meet, read the actual lengths."""
    tmp = tempfile.mkdtemp(prefix="recheck_")
    for f in os.listdir(d):
        if f.startswith("routetune.kicad_"):
            shutil.copy(os.path.join(d, f), tmp)
    with open(os.path.join(tmp, "routetune.kicad_dru"), "a", encoding="utf-8") as f:
        f.write('\n(rule "recheck_probe"\n  (condition "A.NetName == \'/FMC_*\'")\n  (constraint length (max 0.001mm)))\n')
    rep = os.path.join(tmp, "drc.json")
    subprocess.run([CLI, "pcb", "drc", "--refill-zones", "--severity-all", "--format", "json", "--units", "mm", "-o", rep,
                    os.path.join(tmp, "routetune.kicad_pcb")], capture_output=True)
    r = json.load(open(rep, encoding="utf-8"))
    out, other = {}, {}
    for v in r.get("violations", []):
        if v["type"] == "length_out_of_range" and "recheck_probe" in v["description"]:
            nums = re.findall(r"(-?\d+(?:\.\d+)?) mm", v["description"])
            net = None
            for it in v["items"]:
                mm_ = re.search(r"\[(/FMC_\w+)\]", it["description"])
                if mm_:
                    net = mm_.group(1)
            out[net] = float(nums[-1])
        else:
            other[v["type"]] = other.get(v["type"], 0) + 1
    shutil.rmtree(tmp, ignore_errors=True)
    return out, other, len(r.get("unconnected_items", []))


def main():
    key = sys.argv[1]
    d, segs, arcs, vias, pads, cu, zones = load(key)
    M = json.load(open(os.path.join(d, "metrics.json"), encoding="utf-8"))
    F = []                                             # findings
    nets = sorted({s["net"] for s in segs if s["net"].startswith("/FMC_")})
    print("nets %d, segments %d, arcs %d, vias %d, pads %d" % (len(nets), len(segs), len(arcs), len(vias), len(pads)))
    print("rule areas in the board:", zones)
    print("via heights from the stackup: L1-L4 %.4f  L1-L6 %.4f  L4-L6 %.4f" % (via_h(cu, "F.Cu", "In3.Cu"), via_h(cu, "F.Cu", "B.Cu"), via_h(cu, "In3.Cu", "B.Cu")))
    if len(nets) != 19:
        F.append("net count %d" % len(nets))
    drc = {}
    if "--probe" in sys.argv:
        drc, other, unc = probe(d, nets)
        print("own DRC probe: %d nets measured, other violations %s, unconnected %d" % (len(drc), other, unc))
        if other or unc:
            F.append("own DRC run: other violations %s, unconnected %d" % (other, unc))

    # ---------------------------------------------------------------- per net: path, length, vias, layers
    rows = {}
    for net in nets:
        S = [s for s in segs if s["net"] == net]
        A = [a for a in arcs if a["net"] == net]
        V = [v for v in vias if v["net"] == net]
        Pd = {p["ref"]: p for p in pads if p["net"] == net}
        if set(Pd) != {"U1", "U2"}:
            F.append("%s: pads %s" % (net, sorted(Pd)))
            continue
        # walk from the MCU pad: at each node take the unused item that starts there (same layer or through a via)
        def k(p):
            return (round(p[0], 5), round(p[1], 5))
        items = [(k(s["a"]), k(s["b"]), s) for s in S] + [(k(a["a"]), k(a["b"]), a) for a in A]
        used = [False] * len(items)
        vat = {k(v["p"]): v for v in V}
        pos, layer, length, vh, path, nv = k(Pd["U1"]["p"]), "F.Cu", 0.0, 0.0, [], 0
        bylayer = {}
        while True:
            nxt = [i for i, (a, b, it) in enumerate(items) if not used[i] and (a == pos or b == pos)]
            same = [i for i in nxt if items[i][2]["layer"] == layer]
            if len(nxt) > 1 and len(same) != 1:
                F.append("%s: branch (T junction?) at %s" % (net, pos))
            if not nxt:
                break
            i = same[0] if same else nxt[0]
            a, b, it = items[i]
            if it["layer"] != layer:
                if pos not in vat:
                    F.append("%s: layer change without via at %s" % (net, pos)); break
                vh += via_h(cu, layer, it["layer"]); nv += 1; layer = it["layer"]
                path.append(("via", pos))
            used[i] = True
            if "m" in it:
                # arc length from three points
                (x0, y0), (xm, ym), (x1, y1) = it["a"], it["m"], it["b"]
                ax, ay, bx, by = xm - x0, ym - y0, x1 - x0, y1 - y0
                dd = 2 * (ax * by - ay * bx)
                cx = x0 + (by * (ax * ax + ay * ay) - ay * (bx * bx + by * by)) / dd
                cy = y0 + (ax * (bx * bx + by * by) - bx * (ax * ax + ay * ay)) / dd
                r = math.hypot(x0 - cx, y0 - cy)
                a0, am, a1 = math.atan2(y0 - cy, x0 - cx), math.atan2(ym - cy, xm - cx), math.atan2(y1 - cy, x1 - cx)
                sw = (a1 - a0) % (2 * math.pi)
                if (am - a0) % (2 * math.pi) > sw:
                    sw = 2 * math.pi - sw
                L = r * sw
            else:
                L = math.hypot(it["b"][0] - it["a"][0], it["b"][1] - it["a"][1])
            length += L; bylayer[LAY[layer]] = bylayer.get(LAY[layer], 0.0) + L
            new = b if a == pos else a
            path.append((layer, pos, new, it))
            pos = new
        if not all(used):
            F.append("%s: %d track items not on the pad-to-pad path" % (net, used.count(False)))
        if pos != k(Pd["U2"]["p"]) or layer != "F.Cu":
            F.append("%s: path ends at %s on %s, not on the SDRAM pad" % (net, pos, layer))
        if nv != len(V):
            F.append("%s: %d vias on the board, %d used by the path" % (net, len(V), nv))
        rows[net] = {"len": length + vh, "vias": len(V), "bylayer": bylayer, "path": path, "pads": Pd, "V": V, "S": S, "A": A}

    ref = rows["/FMC_SDCLK"]["len"]
    print("\n%-10s %9s %9s %9s %8s %4s  %s" % ("net", "mine", "DRC", "metrics", "d(CLK)", "via", "layers"))
    worst = 0.0
    for net in nets:
        r = rows[net]; mn = M["nets"][net.lstrip("/")]
        dl = r["len"] - ref
        worst = max(worst, abs(dl))
        dv = drc.get(net)
        print("%-10s %9.4f %9s %9.4f %+8.3f %4d  %s" % (net[5:], r["len"], ("%.4f" % dv) if dv is not None else "-", mn["length_mm"], dl, r["vias"],
                                                      " ".join("%s %.2f" % kv for kv in sorted(r["bylayer"].items()))))
        if abs(r["len"] - mn["length_mm"]) > 0.002:
            F.append("%s: my length %.4f, metrics %.4f" % (net, r["len"], mn["length_mm"]))
        if dv is not None and abs(r["len"] - dv) > 0.002:
            F.append("%s: my length %.4f, own DRC probe %.4f" % (net, r["len"], dv))
        if abs(dl - mn["delta_to_sdclk_mm"]) > 0.002:
            F.append("%s: delta %.4f, metrics %.4f" % (net, dl, mn["delta_to_sdclk_mm"]))
        if abs(dl) > 2.5:
            F.append("%s: outside the window by %.3f" % (net, abs(dl) - 2.5))
        if r["len"] > 60:
            F.append("%s: longer than 60 mm" % net)
        if r["vias"] != mn["vias"]:
            F.append("%s: vias %d, metrics %d" % (net, r["vias"], mn["vias"]))
        if r["vias"] > 3:
            F.append("%s: %d vias (cap 3)" % (net, r["vias"]))
        for L, v in r["bylayer"].items():
            if abs(v - mn["layers"].get(L, 0)) > 0.002:
                F.append("%s: %s length %.4f, metrics %.4f" % (net, L, v, mn["layers"].get(L, 0)))
        # direct: octilinear pad to pad
        a, b = r["pads"]["U1"]["p"], r["pads"]["U2"]["p"]
        dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
        direct = max(dx, dy) - min(dx, dy) + min(dx, dy) * math.sqrt(2)
        if abs(direct - mn["direct_mm"]) > 0.002:
            F.append("%s: direct %.4f, metrics %.4f" % (net, direct, mn["direct_mm"]))
        r["direct"] = direct
    n_in = sum(1 for n in nets if abs(rows[n]["len"] - ref) <= 2.5)
    print("SDCLK %.4f; in window %d / %d; worst |delta| %.4f (metrics %.4f); sum direct %.3f; sum detour %.3f (metrics %.3f)" % (
        ref, n_in, len(nets), worst, M["totals"]["worst_delta_mm"], sum(rows[n]["direct"] for n in nets),
        sum(rows[n]["len"] - rows[n]["direct"] for n in nets), M["totals"]["total_detour_mm"]))
    if n_in != M["totals"]["in_window_count"]:
        F.append("in window %d, metrics %d" % (n_in, M["totals"]["in_window_count"]))

    # ---------------------------------------------------------------- shape: directions, corners, widths, vias
    bus = [s for s in segs if s["net"].startswith("/FMC_")]
    for s in bus:
        dx, dy = s["b"][0] - s["a"][0], s["b"][1] - s["a"][1]
        if not (abs(dx) < 1e-6 or abs(dy) < 1e-6 or abs(abs(dx) - abs(dy)) < 1e-6):
            F.append("%s %s: segment %s-%s is not 0/45/90" % (s["net"], s["layer"], s["a"], s["b"]))
        L = math.hypot(dx, dy)
        if L < 0.1 - 1e-6:
            F.append("%s %s: segment of %.4f mm at %s" % (s["net"], s["layer"], L, s["a"]))
        # width against the rule areas: 0.09 if it touches an area or lies within 0.3 mm (along the track) of one
        touch = any(clip_len_inside(s["a"], s["b"], R) > 1e-6 or in_rect(s["a"], R, 1e-6) or in_rect(s["b"], R, 1e-6) for R in AREA.values())
        inside = any(in_rect(s["a"], R, 1e-6) and in_rect(s["b"], R, 1e-6) for R in AREA.values())
        if inside and abs(s["w"] - 0.09) > 1e-6:
            F.append("%s %s: width %.4f inside a rule area at %s" % (s["net"], s["layer"], s["w"], s["a"]))
        if abs(s["w"] - 0.09) < 1e-6 and not touch:
            F.append("%s %s: 0.09 track that does not touch a rule area, %s-%s" % (s["net"], s["layer"], s["a"], s["b"]))
        if abs(s["w"] - 0.09) > 1e-6 and abs(s["w"] - 0.1016) > 1e-6:
            F.append("%s: width %.4f" % (s["net"], s["w"]))
        if abs(s["w"] - 0.1016) < 1e-6 and touch:
            F.append("%s %s: 0.1016 track touches a rule area, %s-%s" % (s["net"], s["layer"], s["a"], s["b"]))
    thin_out = {}
    corners = {"45": 0, "0": 0}
    via_turns, short_between = [], []
    for net in nets:
        p = rows[net]["path"]
        tr = [x for x in p if x[0] != "via"]
        # thin track outside the areas
        for (layer, a, b, it) in tr:
            if abs(it["w"] - 0.09) < 1e-6:
                L = math.hypot(b[0] - a[0], b[1] - a[1])
                ins = sum(clip_len_inside(a, b, R) for R in AREA.values())
                thin_out[net] = thin_out.get(net, 0.0) + L - ins
        for i in range(len(p) - 1):
            x, y = p[i], p[i + 1]
            if x[0] == "via" or y[0] == "via":
                continue
            d1 = (x[2][0] - x[1][0], x[2][1] - x[1][1]); d2 = (y[2][0] - y[1][0], y[2][1] - y[1][1])
            ang = abs(math.degrees(math.atan2(d1[0] * d2[1] - d1[1] * d2[0], d1[0] * d2[0] + d1[1] * d2[1])))
            if ang < 0.01:
                corners["0"] += 1
            elif abs(ang - 45) < 0.01:
                corners["45"] += 1
            else:
                F.append("%s %s: corner of %.2f deg turn at (%.4f, %.4f)" % (net, x[0], ang, x[2][0], x[2][1]))
        # turn at a via (track in, track out, seen in plan view)
        for i, x in enumerate(p):
            if x[0] == "via" and 0 < i < len(p) - 1:
                a, b = p[i - 1], p[i + 1]
                d1 = (a[2][0] - a[1][0], a[2][1] - a[1][1]); d2 = (b[2][0] - b[1][0], b[2][1] - b[1][1])
                ang = abs(math.degrees(math.atan2(d1[0] * d2[1] - d1[1] * d2[0], d1[0] * d2[0] + d1[1] * d2[1])))
                via_turns.append((net, x[1], round(ang, 1)))
        # merged straights (same direction, any width): bends closer than 0.35 that turn the same way
        runs = []
        for (layer, a, b, it) in tr:
            dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy); u = (round(dx / L, 6), round(dy / L, 6))
            if runs and runs[-1][0] == layer and runs[-1][1] == u and runs[-1][3] == a:
                runs[-1][2] += L; runs[-1][3] = b
            else:
                runs.append([layer, u, L, b, a])
        rows[net]["runs"] = runs
        for j in range(1, len(runs) - 1):
            if runs[j][0] == runs[j - 1][0] == runs[j + 1][0] and runs[j][2] < 0.35:
                c1 = runs[j - 1][1][0] * runs[j][1][1] - runs[j - 1][1][1] * runs[j][1][0]
                c2 = runs[j][1][0] * runs[j + 1][1][1] - runs[j][1][1] * runs[j + 1][1][0]
                short_between.append((net, runs[j][0], round(runs[j][2], 4), runs[j][4], "same way" if c1 * c2 > 0 else "S"))
    print("\ncorners: %d of 45 deg, %d straight joints (width change)" % (corners["45"], corners["0"]))
    print("straights shorter than 0.35 mm between two bends:", short_between or "none")
    for n, pnt, a in via_turns:
        if a >= 89.9:
            F.append("%s: track turns %.1f deg through the via at %s" % (n, a, pnt))
    print("turn through a via (deg): max %.1f; list of those above 45: %s" % (max(a for _, _, a in via_turns), [(n[5:], p, a) for n, p, a in via_turns if a > 45.1]))
    print("0.09 track outside the rule areas per net: max %.3f (%s); metrics max %.3f" % (
        max(thin_out.values()), max(thin_out, key=thin_out.get)[5:], max(M["checks"]["geometry"]["thin_outside_mm"].values())))

    # vias: size by place, in the strip, MCU ring convention
    strip_v = [v for v in vias if v["net"].startswith("/FMC_") and STRIP[0] < v["p"][0] < STRIP[1]]
    print("bus vias: %d; in the strip x 19-22 (centre): %d; touching the strip (edge): %d" % (
        sum(1 for v in vias if v["net"].startswith("/FMC_")), len(strip_v),
        sum(1 for v in vias if v["net"].startswith("/FMC_") and STRIP[0] < v["p"][0] + v["size"] / 2 and v["p"][0] - v["size"] / 2 < STRIP[1])))
    if strip_v:
        F.append("vias in the strip between the rule areas: %s" % [(v["net"], v["p"]) for v in strip_v])
    for v in vias:
        if not v["net"].startswith("/FMC_"):
            continue
        ins = any(in_rect(v["p"], R) for R in AREA.values())
        whole = any(in_rect(v["p"], R, -v["size"] / 2) for R in AREA.values())
        if ins and (abs(v["size"] - 0.30) > 1e-6 or abs(v["drill"] - 0.15) > 1e-6):
            F.append("%s: via %.2f/%.2f inside a rule area at %s" % (v["net"], v["size"], v["drill"], v["p"]))
        if not ins and (v["size"] < 0.45 - 1e-6 or v["drill"] < 0.2 - 1e-6):
            F.append("%s: via %.2f/%.2f outside the rule areas at %s" % (v["net"], v["size"], v["drill"], v["p"]))
        if ins and not whole:
            print("  note: via of %s at %s straddles a rule-area edge" % (v["net"], v["p"]))
        if v["layers"] != ["F.Cu", "B.Cu"]:
            F.append("%s: via layers %s" % (v["net"], v["layers"]))
    print("\nMCU breakout (ring 0 = outer row of balls):")
    for net in nets:
        r = rows[net]; p = r["pads"]["U1"]["p"]
        col = round((p[0] - 13) / 0.65) + 8; row = round((p[1] - 12) / 0.65)      # col 1..15, row -7..7
        ring = min(col - 1, 15 - col, row + 7, 7 - row)
        # layer on which the net crosses the package outline of U1
        leave = None
        for x in r["path"]:
            if x[0] != "via" and in_rect(x[1], BODY["U1"]) != in_rect(x[2], BODY["U1"]):
                leave = LAY[x[0]]; break
        first_via = next((x[1] for x in r["path"] if x[0] == "via"), None)
        note = ""
        if ring <= 1 and leave != "L1":
            note = "  <-- outer-ring ball does not leave on L1"
            F.append("%s: ring %d ball leaves the MCU on %s" % (net, ring, leave))
        if ring >= 2 and leave != "L4":
            note = "  <-- inner-ring ball does not leave on L4"
            F.append("%s: ring %d ball leaves the MCU on %s" % (net, ring, leave))
        print("  %-6s ball %s ring %d leaves the body on %s, first via %s%s" % (net[5:], r["pads"]["U1"]["name"], ring, leave, first_via, note))

    # swap table: names of the SDRAM balls from metrics/routes.json are the builder's; here only the lane test by ball
    RJ = json.load(open(os.path.join(d, "routes.json"), encoding="utf-8"))
    print("\nswap table (routes.json):", json.dumps(RJ.get("swap", RJ.get("SWAP", {})), ensure_ascii=False))

    # ---------------------------------------------------------------- clearances: same layer, different nets
    def need(p, q):
        return 0.09 if any(in_rect(p, R, 1e-6) or in_rect(q, R, 1e-6) for R in AREA.values()) else 0.127
    worst_gap, viol, cross = (9, None), [], []
    for i in range(len(bus)):
        s = bus[i]
        for j in range(i + 1, len(bus)):
            t = bus[j]
            if s["net"] == t["net"] or s["layer"] != t["layer"]:
                continue
            dd = seg_dist(s["a"], s["b"], t["a"], t["b"])
            if dd == 0.0:
                cross.append((s["net"], t["net"], s["layer"], s["a"], t["a"]))
            g = dd - s["w"] / 2 - t["w"] / 2
            inside = any((clip_len_inside(s["a"], s["b"], R) > 0 or in_rect(s["a"], R, 1e-6)) and (clip_len_inside(t["a"], t["b"], R) > 0 or in_rect(t["a"], R, 1e-6)) for R in AREA.values())
            nd = 0.09 if (abs(s["w"] - 0.09) < 1e-6 or abs(t["w"] - 0.09) < 1e-6) and inside else 0.127
            if g < worst_gap[0]:
                worst_gap = (g, (s["net"], t["net"], s["layer"], s["a"], s["b"]))
            if g < nd - 1e-4:
                viol.append((round(g, 4), nd, s["net"], t["net"], s["layer"], s["a"], t["a"]))
        for v in vias:
            if v["net"] == s["net"]:
                continue
            g = pt_seg(v["p"], s["a"], s["b"]) - s["w"] / 2 - v["size"] / 2
            nd = 0.09 if any(in_rect(v["p"], R) for R in AREA.values()) else 0.127
            if g < nd - 1e-4:
                viol.append((round(g, 4), nd, s["net"], "via " + v["net"], s["layer"], s["a"], v["p"]))
            hole = pt_seg(v["p"], s["a"], s["b"]) - s["w"] / 2 - v["drill"] / 2
            if hole < 0.2 - 1e-4:
                viol.append((round(hole, 4), "hole 0.2", s["net"], "via " + v["net"], s["layer"], s["a"], v["p"]))
        if s["layer"] == "F.Cu":
            for p in pads:
                if p["net"] == s["net"]:
                    continue
                g = pt_seg(p["p"], s["a"], s["b"]) - s["w"] / 2 - p["d"] / 2
                if g < 0.09 - 1e-4:
                    viol.append((round(g, 4), 0.09, s["net"], "pad %s%s" % (p["ref"], p["name"]), s["layer"], s["a"], p["p"]))
    print("\nsame-layer crossings between nets: %d %s" % (len(cross), cross[:5]))
    print("smallest track-to-track gap between different nets: %.4f %s" % worst_gap)
    print("gaps below the clearance of the place (tracks, vias incl. hole 0.2, pads on L1): %d" % len(viol))
    for v in viol[:20]:
        print("   ", v)
    if cross:
        F.append("%d same-layer crossings" % len(cross))
    if viol:
        F.append("%d clearance problems, first %s" % (len(viol), viol[0]))
    mg = M["checks"]["geometry"]["min_gap_all"]["gap"]
    if abs(worst_gap[0] - mg) > 0.002:
        print("  note: metrics min_gap_all %.4f vs mine %.4f" % (mg, worst_gap[0]))

    # ---------------------------------------------------------------- space
    pts, strip_y, by_layer_y = [], [], {}
    for s in bus:
        pcs = [(s["a"], s["b"])]
        for R in BODY.values():
            pcs = [q for pc in pcs for q in clip_outside(pc[0], pc[1], R)]
        for a, b in pcs:
            pts += [a, b]
        # strip: clip to x 19..22
        a, b = s["a"], s["b"]
        ts = [0.0, 1.0]
        if abs(b[0] - a[0]) > 1e-12:
            ts += [t for t in ((STRIP[0] - a[0]) / (b[0] - a[0]), (STRIP[1] - a[0]) / (b[0] - a[0])) if 0 < t < 1]
        ts.sort()
        for t0, t1 in zip(ts, ts[1:]):
            xm = a[0] + (t0 + t1) / 2 * (b[0] - a[0])
            if STRIP[0] - 1e-9 <= xm <= STRIP[1] + 1e-9:
                for t in (t0, t1):
                    y = a[1] + t * (b[1] - a[1])
                    strip_y.append(y); by_layer_y.setdefault(LAY[s["layer"]], []).append(y)
    for v in vias:
        if v["net"].startswith("/FMC_") and not any(in_rect(v["p"], R) for R in BODY.values()):
            pts.append(v["p"])
    h = hull(pts)
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    print("\nspace (centre lines of bus tracks outside both package outlines, plus via centres outside them):")
    print("  hull %.2f mm2 (metrics %.2f); bbox %.3f x %.3f (metrics %s); x %.3f..%.3f, y %.3f..%.3f" % (
        poly_area(h), M["space"]["bus_hull_area_mm2"], max(xs) - min(xs), max(ys) - min(ys), M["space"]["bus_bbox_mm"], min(xs), max(xs), min(ys), max(ys)))
    print("  strip x 19-22: y %.3f..%.3f = %.3f (metrics %.3f); by layer %s (metrics %s)" % (
        min(strip_y), max(strip_y), max(strip_y) - min(strip_y), M["space"]["channel_width_mm"],
        {L: round(max(v) - min(v), 3) for L, v in sorted(by_layer_y.items())}, M["space"]["channel_width_by_layer_mm"]))
    if abs(poly_area(h) - M["space"]["bus_hull_area_mm2"]) > 0.02 * poly_area(h):
        F.append("hull %.2f, metrics %.2f" % (poly_area(h), M["space"]["bus_hull_area_mm2"]))
    if abs(max(strip_y) - min(strip_y) - M["space"]["channel_width_mm"]) > 0.15:
        F.append("channel width %.3f, metrics %.3f" % (max(strip_y) - min(strip_y), M["space"]["channel_width_mm"]))

    # ---------------------------------------------------------------- serpentines (arcs)
    print("\narcs on the board: %d (bus nets: %d)" % (len(arcs), sum(1 for a in arcs if a["net"].startswith("/FMC_"))))
    if arcs:
        rad = {}
        for a in arcs:
            (x0, y0), (xm, ym), (x1, y1) = a["a"], a["m"], a["b"]
            ax, ay, bx, by = xm - x0, ym - y0, x1 - x0, y1 - y0
            dd = 2 * (ax * by - ay * bx)
            cx = x0 + (by * (ax * ax + ay * ay) - ay * (bx * bx + by * by)) / dd
            cy = y0 + (ax * (bx * bx + by * by) - bx * (ax * ax + ay * ay)) / dd
            rad.setdefault(a["net"], set()).add(round(math.hypot(x0 - cx, y0 - cy), 4))
            a["c"] = (cx, cy)
        for n, rs in sorted(rad.items()):
            print("  %s: arc radii %s -> leg pitch %s" % (n, sorted(rs), sorted(2 * r for r in rs)))
            if n == "/FMC_SDCLK" and min(rs) < 0.25 - 1e-4:
                F.append("SDCLK serpentine pitch below 0.5")
        under = sum(1 for a in arcs if in_rect(a["c"], BODY["U2"]))
        print("  arcs whose centre is under the SDRAM body: %d of %d" % (under, len(arcs)))

    print("\nFINDINGS (%d)" % len(F))
    for f in F:
        print("  -", f)


def clip_len_inside(a, b, R):
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    out = sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in clip_outside(a, b, R))
    return L - out


if __name__ == "__main__":
    main()
