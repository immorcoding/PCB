"""analyze_lane.py <dump.json> <layer> <signal-regex> <soc-ref> <dram-ref-suffix-map|-> [--json out.json]
Per net, per connected TOP piece (pieces end at vias / pads): ordered samples every 0.05 mm with both-side neighbour class
G (GND copper <=0.30 mm gap), S (lane signal <=0.5), X (other copper <=0.5), O (nothing within 0.5);
guard coverage, unguarded / three-signal stretches outside the ball fields, guard start/stop vs ball-field edges.
Ball fields: SoC = convex hull of its SMD pads (the SoC package is rotated 45 deg), DRAM = rectangle of the pads of the
DRAM the net goes to (nets ending _A -> U3300, _B -> U3301 for EVB1)."""
import sys, json, re, math, collections
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import numpy as np
import guard

STEP = .05

def hull(P):
    P = sorted(map(tuple, P)); cr = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in P:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]

def hull_dist(H, p):
    """signed distance to hull polygon (negative inside), mm."""
    inside = True; best = 1e9
    for i in range(len(H)):
        a, b = np.array(H[i]), np.array(H[(i + 1) % len(H)]); ab = b - a; t = np.clip((np.array(p) - a) @ ab / (ab @ ab), 0, 1)
        best = min(best, float(np.linalg.norm(np.array(p) - (a + t * ab))))
        if ab[0] * (p[1] - a[1]) - ab[1] * (p[0] - a[0]) < 0: inside = False
    return -best if inside else best

def rect_dist(R, p):
    x0, y0, x1, y1 = R; dx = max(x0 - p[0], 0, p[0] - x1); dy = max(y0 - p[1], 0, p[1] - y1)
    if dx == 0 and dy == 0: return -min(p[0] - x0, x1 - p[0], p[1] - y0, y1 - p[1])
    return math.hypot(dx, dy)

def pieces(tracks, tol=.03):
    segs = [dict(t) for t in tracks]; out = []
    while segs:
        comp = [segs.pop(0)]; grew = True
        while grew:
            grew = False
            for t in segs[:]:
                if any(min(math.hypot(t[e][0] - c[f][0], t[e][1] - c[f][1]) for e in "ab" for f in "ab") < tol for c in comp):
                    comp.append(t); segs.remove(t); grew = True
        # order: start at the degree-1 endpoint with the smallest x
        pts = collections.Counter()
        key = lambda p: (round(p[0] / tol), round(p[1] / tol))
        for c in comp:
            for e in "ab": pts[key(c[e])] += 1
        ends = [c[e] for c in comp for e in "ab" if pts[key(c[e])] == 1]
        start = min(ends, key=lambda p: p[0]) if ends else comp[0]["a"]
        path, cur, rest = [], tuple(start), comp[:]
        while rest:
            bs = None
            for i, t in enumerate(rest):
                for e, o in (("a", "b"), ("b", "a")):
                    dd = math.hypot(t[e][0] - cur[0], t[e][1] - cur[1])
                    if dd < tol * 1.5 and (bs is None or dd < bs[0]): bs = (dd, i, e, o)
            if bs is None: break
            _, i, e, o = bs; t = rest.pop(i); path.append({"a": t[e], "b": t[o], "w": t["w"], "net": t["net"]}); cur = tuple(t[o])
        out.append((path, rest))
    return out

def cls(x, rxs):
    if x is None or x[0] > .5: return "O"
    if guard.GND.match(x[1]): return "G" if x[0] <= .3 else "O"
    return "S" if rxs.search(x[1]) else "X"

def main(dump, layer, rx, soc, drams, jout=None, reach=1.5):
    d = json.load(open(dump)); rxs = re.compile(rx); A, B, R, N, K = guard.items(d, layer)
    H = hull([p["p"] for p in d["pads"] if p["ref"] == soc and p["smd"]])
    dram = {}
    for suf, ref in drams.items():
        P = np.array([p["p"] for p in d["pads"] if p["ref"] == ref]); dram[suf] = (P[:, 0].min() - .19, P[:, 1].min() - .19, P[:, 0].max() + .19, P[:, 1].max() + .19)
    nets = sorted({t["net"] for t in d["tracks"] if t["l"] == layer and rxs.search(t["net"])})
    GV = np.array([v["p"] for v in d["vias"] if guard.GND.match(v["net"])])
    result = {}
    for net in nets:
        suf = next((s for s in dram if net.endswith(s)), None); RC = dram.get(suf)
        tr = [t for t in d["tracks"] if t["l"] == layer and t["net"] == net]
        sel = (N != net); a, b, r, nn, kk = A[sel], B[sel], R[sel], N[sel], K[sel]; ab = b - a; l2 = (ab ** 2).sum(1); l2[l2 == 0] = 1
        pcs = []
        for path, rest in pieces(tr):
            rec = []; s = 0.
            for t in path:
                for p, u in guard.samples(t, STEP):
                    ap = p - a; sp = np.clip((ap * ab).sum(1) / l2, 0, 1); q = a + ab * sp[:, None]; dv = q - p
                    dist = np.hypot(dv[:, 0], dv[:, 1]); cr = u[0] * dv[:, 1] - u[1] * dv[:, 0]; dt = dv @ u
                    gap = dist - r - t["w"] / 2; ok = (dist < reach) & (np.abs(dt) <= np.abs(cr) * 1.2); sd = []
                    for mask in (cr > 0, cr < 0):
                        c = np.where(ok & mask)[0]
                        if len(c): i = c[np.argmin(gap[c])]; sd.append([float(gap[i]), nn[i], kk[i], float(r[i] * 2)])
                        else: sd.append(None)
                    hd = hull_dist(H, p); rd = rect_dist(RC, p) if RC else 9
                    rec.append({"s": s, "p": [float(p[0]), float(p[1])], "w": t["w"], "c": cls(sd[0], rxs) + cls(sd[1], rxs), "sd": sd, "soc": hd, "dram": rd, "gv": float(np.min(np.hypot(GV[:, 0] - p[0], GV[:, 1] - p[1])))}); s += STEP
            if rec: pcs.append({"rec": rec, "start": path[0]["a"], "end": path[-1]["b"], "unchained": len(rest)})
        result[net] = pcs
    if jout: json.dump(result, open(jout, "w"), default=str)
    return result

def stretches(rec, pred, minlen=.25):
    out, cur = [], None
    for r in rec:
        if pred(r):
            if cur is None: cur = [r, r]
            else: cur[1] = r
        else:
            if cur and cur[1]["s"] - cur[0]["s"] + STEP >= minlen: out.append(tuple(cur))
            cur = None
    if cur and cur[1]["s"] - cur[0]["s"] + STEP >= minlen: out.append(tuple(cur))
    return out

if __name__ == "__main__":
    dump, layer, rx, soc = sys.argv[1:5]
    drams = dict(x.split("=") for x in sys.argv[5].split(",")) if sys.argv[5] != "-" else {}
    res = main(dump, layer, rx, soc, drams)
    for net, pcs in res.items():
        for i, pc in enumerate(pcs):
            rec = pc["rec"]; n = len(rec)
            hasg = sum(1 for r in rec if "G" in r["c"]) / n; gg = sum(1 for r in rec if r["c"] == "GG") / n
            wid = [r["w"] for r in rec]
            print("%s piece%d len %.2f from (%.2f,%.2f) to (%.2f,%.2f) w %.3f  G>=1 side %.0f%%  GG %.0f%%" % (net, i, n * STEP, *pc["start"], *pc["end"], np.median(wid), 100 * hasg, 100 * gg))
            out_ball = lambda r: r["soc"] > .3 and r["dram"] > .3
            for lab, pred in (("NO-GUARD(no G either side)", lambda r: out_ball(r) and "G" not in r["c"]),
                              ("OPEN/X side", lambda r: out_ball(r) and ("X" in r["c"] or "O" in r["c"])),
                              ("NO GND VIA within 100 mil", lambda r: out_ball(r) and r["gv"] > 2.54),
                              ("SS (3 sigs between guards)", lambda r: out_ball(r) and r["c"] == "SS")):
                for a_, b_ in stretches(rec, pred):
                    print("     %-28s s=%.2f..%.2f (%.2f,%.2f)->(%.2f,%.2f) soc %.2f dram %.2f nb %s" % (lab, a_["s"], b_["s"], *a_["p"], *b_["p"], a_["soc"], a_["dram"], [x[1] if x else None for x in a_["sd"]]))
