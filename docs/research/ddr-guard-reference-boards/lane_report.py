"""lane_report.py <dump.json> <layer> <signal-regex> <soc-ref> [step]
Walk each matching net from its SoC pad along the layer's tracks; classify both sides at every step as
G (GND copper within 0.30 mm), S (lane signal within 0.5), X (other-net copper within 0.5), O (open, nothing within 0.5);
run-length encode along the path (runs shorter than 0.2 mm are merged into the previous run) with s (path length from the SoC pad)
and board coordinates."""
import sys, json, re, math, collections
import numpy as np
sys.path.insert(0, __file__.rsplit("\\", 1)[0] if "\\" in __file__ else ".")
import guard

def chain(tracks, start):
    segs = [dict(t) for t in tracks]; cur = tuple(start); path = []
    while True:
        best = None
        for i, t in enumerate(segs):
            for end, other in (("a", "b"), ("b", "a")):
                dd = math.hypot(t[end][0] - cur[0], t[end][1] - cur[1])
                if dd < 0.05 and (best is None or dd < best[0]): best = (dd, i, end, other)
        if best is None: break
        _, i, end, other = best; t = segs.pop(i); path.append({"a": t[end], "b": t[other], "w": t["w"], "net": t["net"]}); cur = tuple(t[other])
    return path, cur, len(segs)

def kind(x, rxs):
    if x is None or x[0] > .5: return "O"
    if guard.GND.match(x[1]): return "G" if x[0] <= .3 else "O"
    if rxs.search(x[1]): return "S"
    return "X"

def run(d, layer, rx, soc, step=.05, reach=1.5):
    rxs = re.compile(rx); A, B, R, N, K = guard.items(d, layer)
    nets = sorted({t["net"] for t in d["tracks"] if t["l"] == layer and rxs.search(t["net"])})
    res = {}
    for net in nets:
        tr = [t for t in d["tracks"] if t["l"] == layer and t["net"] == net]
        pads = [p for p in d["pads"] if p["net"] == net and p["ref"] == soc]
        if not pads: continue
        start = pads[0]["p"]; path, end, left = chain(tr, start)
        sel = (N != net); a, b, r, nn, kk = A[sel], B[sel], R[sel], N[sel], K[sel]; ab = b - a; l2 = (ab ** 2).sum(1); l2[l2 == 0] = 1
        rec = []; s0 = 0.0
        for t in path:
            for p, u in guard.samples(t, step):
                ap = p - a; s = np.clip((ap * ab).sum(1) / l2, 0, 1); q = a + ab * s[:, None]; dv = q - p
                dist = np.hypot(dv[:, 0], dv[:, 1]); cr = u[0] * dv[:, 1] - u[1] * dv[:, 0]; dt = dv @ u
                gap = dist - r - t["w"] / 2; ok = (dist < reach) & (np.abs(dt) <= np.abs(cr) * 1.2); sd = []
                for mask in (cr > 0, cr < 0):
                    c = np.where(ok & mask)[0]
                    sd.append((float(gap[c[np.argmin(gap[c])]]), nn[c[np.argmin(gap[c])]], kk[c[np.argmin(gap[c])]], float(r[c[np.argmin(gap[c])]] * 2)) if len(c) else None)
                rec.append((s0, float(p[0]), float(p[1]), kind(sd[0], rxs) + kind(sd[1], rxs), sd)); s0 += step
        res[net] = (rec, start, end, left, path)
    return res

def rle(rec, minrun=4):
    runs = []
    for s0, x, y, code, sd in rec:
        c = "".join(sorted(code))
        if runs and (runs[-1]["c"] == c): runs[-1]["n"] += 1; runs[-1]["e"] = (s0, x, y)
        else: runs.append({"c": c, "n": 1, "b": (s0, x, y), "e": (s0, x, y), "sd": [sd]})
    # merge short
    out = []
    for r in runs:
        if out and r["n"] < minrun: out[-1]["n"] += r["n"]; out[-1]["e"] = r["e"]
        elif out and out[-1]["c"] == r["c"]: out[-1]["n"] += r["n"]; out[-1]["e"] = r["e"]
        else: out.append(r)
    return out

if __name__ == "__main__":
    d = json.load(open(sys.argv[1])); layer, rx, soc = sys.argv[2], sys.argv[3], sys.argv[4]; step = float(sys.argv[5]) if len(sys.argv) > 5 else .05
    for net, (rec, start, end, left, path) in run(d, layer, rx, soc, step).items():
        print("%s  path %.1f mm  from %s to %s  (unchained segs %d)" % (net, len(rec) * step, [round(v, 2) for v in start], [round(v, 2) for v in end], left))
        for r in rle(rec):
            print("   %s  s=%.2f..%.2f  (%.2f,%.2f)->(%.2f,%.2f)" % (r["c"], r["b"][0], r["e"][0] + step, r["b"][1], r["b"][2], r["e"][1], r["e"][2]))
