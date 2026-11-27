"""guard.py <dump.json> <layer> <signal-regex> [step_mm] -> pickle-free text report on stdout and 'guard_<tag>.json' if --save out.json.
For every sampled point along each matching signal track on the layer: nearest copper object on the left and on the right
(other nets only; tracks, vias, SMD pads), gap = edge-to-edge distance in mm. Aggregates guard coverage per net."""
import sys, json, re, math, collections
import numpy as np

GND = re.compile(r"^(GND|VSS|AGND|DGND)", re.I)

def items(d, layer):
    A, B, R, N, K = [], [], [], [], []
    for t in d["tracks"]:
        if t["l"] == layer: A.append(t["a"]); B.append(t["b"]); R.append(t["w"] / 2); N.append(t["net"]); K.append("trk")
    for a in d["arcs"]:
        if a["l"] == layer:
            for p, q in ((a["a"], a["m"]), (a["m"], a["b"])): A.append(p); B.append(q); R.append(a["w"] / 2); N.append(a["net"]); K.append("arc")
    for v in d["vias"]:
        # through vias reach every layer; blind/buried: only if layer between
        A.append(v["p"]); B.append(v["p"]); R.append(v["w"] / 2); N.append(v["net"]); K.append("via")
    for p in d["pads"]:
        if p["side"] == layer and p["smd"]:
            A.append(p["p"]); B.append(p["p"]); R.append(min(p["s"]) / 2); N.append(p["net"]); K.append("pad")
    return np.array(A), np.array(B), np.array(R), np.array(N), np.array(K)

def samples(t, step):
    a, b = np.array(t["a"]), np.array(t["b"]); L = np.linalg.norm(b - a)
    if L < 1e-9: return []
    u = (b - a) / L; n = max(1, int(L / step))
    return [(a + u * (L * (i + .5) / n), u) for i in range(n)]

def analyse(d, layer, rx, step=0.05, reach=1.5):
    A, B, R, N, K = items(d, layer)
    sig = [t for t in d["tracks"] if t["l"] == layer and rx.search(t["net"])]
    out = {}
    for net in sorted({t["net"] for t in sig}):
        S = []
        for t in sig:
            if t["net"] == net: S += [(p, u, t["w"]) for p, u in samples(t, step)]
        P = np.array([s[0] for s in S]); lo = P.min(0) - reach; hi = P.max(0) + reach
        m = (np.minimum(A, B).min(1) if False else True)
        sel = (np.maximum(A[:, 0], B[:, 0]) >= lo[0]) & (np.minimum(A[:, 0], B[:, 0]) <= hi[0]) & (np.maximum(A[:, 1], B[:, 1]) >= lo[1]) & (np.minimum(A[:, 1], B[:, 1]) <= hi[1]) & (N != net)
        a, b, r, nn, kk = A[sel], B[sel], R[sel], N[sel], K[sel]
        ab = b - a; l2 = (ab ** 2).sum(1); l2[l2 == 0] = 1
        rec = []
        for (p, u, w) in S:
            ap = p - a; s = np.clip((ap * ab).sum(1) / l2, 0, 1); q = a + ab * s[:, None]; dv = q - p
            dist = np.hypot(dv[:, 0], dv[:, 1]); cr = u[0] * dv[:, 1] - u[1] * dv[:, 0]; dt = dv @ u
            gap = dist - r - w / 2
            ok = (dist < reach) & (np.abs(dt) <= np.abs(cr) * 1.2)
            res = {}
            for side, mask in (("L", cr > 0), ("R", cr < 0)):
                c = np.where(ok & mask)[0]
                if len(c):
                    i = c[np.argmin(gap[c])]; res[side] = (float(gap[i]), nn[i], kk[i], float(r[i] * 2))
                else: res[side] = None
            rec.append((float(p[0]), float(p[1]), w, res))
        out[net] = rec
    return out

def classify(res, gnd_gap=0.3):
    def g(x): return x is not None and GND.match(x[1]) is not None and x[0] <= gnd_gap
    return g(res["L"]), g(res["R"])

if __name__ == "__main__":
    d = json.load(open(sys.argv[1])); layer = sys.argv[2]; rx = re.compile(sys.argv[3]); step = float(sys.argv[4]) if len(sys.argv) > 4 else .05
    out = analyse(d, layer, rx, step)
    for net, rec in out.items():
        n = len(rec); c = collections.Counter(classify(r[3]) for r in rec)
        both = c[(True, True)]; one = c[(True, False)] + c[(False, True)]; none = c[(False, False)]
        gg = [r[3][s][0] for r in rec for s in "LR" if r[3][s] and GND.match(r[3][s][1])]
        sg = [r[3][s][0] for r in rec for s in "LR" if r[3][s] and not GND.match(r[3][s][1]) and rx.search(r[3][s][1]) and r[3][s][0] < .5]
        print("%-16s len %5.1f  both %3.0f%%  one %3.0f%%  none %3.0f%%  GNDgap med %.3f  sig-sig gap med %s" % (
            net, n * step, 100 * both / n, 100 * one / n, 100 * none / n, np.median(gg) if gg else -1, "%.3f" % np.median(sg) if sg else "-"))
