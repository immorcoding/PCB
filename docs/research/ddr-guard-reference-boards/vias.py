"""vias.py <dump.json> <layer> <signal-regex> [soc-ref]
Guard tracks = GND tracks on the layer within 0.30 mm (edge to edge) of a sample of a lane signal. Connected guard pieces ->
GND vias on them (centre within 0.08 mm of the centreline) -> spacing along the piece (cumulative length, mm); ball-field
stretches are listed separately by the caller. Also: signal layer-change vias vs nearest GND via."""
import sys, json, re, math, collections
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import numpy as np
import guard

def seg_dist(p, a, b):
    ab = b - a; l2 = ab @ ab
    t = 0 if l2 == 0 else np.clip((p - a) @ ab / l2, 0, 1); return float(np.linalg.norm(p - (a + t * ab))), float(t)

def main(dump, layer, rx):
    d = json.load(open(dump)); rxs = re.compile(rx)
    sig = [t for t in d["tracks"] if t["l"] == layer and rxs.search(t["net"])]
    S = []; W = []
    for t in sig:
        for p, u in guard.samples(t, .1): S.append(p); W.append(t["w"])
    S = np.array(S); W = np.array(W)
    G = [t for t in d["tracks"] if t["l"] == layer and guard.GND.match(t["net"])]
    sel = []
    for t in G:
        a, b = np.array(t["a"]), np.array(t["b"])
        lo = np.minimum(a, b) - .6 - t["w"] / 2; hi = np.maximum(a, b) + .6 + t["w"] / 2
        m = (S[:, 0] >= lo[0]) & (S[:, 0] <= hi[0]) & (S[:, 1] >= lo[1]) & (S[:, 1] <= hi[1])
        if not m.any(): continue
        dd = [seg_dist(p, a, b)[0] - t["w"] / 2 - w / 2 for p, w in zip(S[m], W[m])]
        if min(dd) <= .3: sel.append(t)
    print("guard segments:", len(sel), "widths:", sorted(collections.Counter(round(t["w"], 3) for t in sel).items()))
    # components
    comps = []; rest = sel[:]
    while rest:
        c = [rest.pop()]; grew = True
        while grew:
            grew = False
            for t in rest[:]:
                if any(min(math.hypot(t[e][0] - q[f][0], t[e][1] - q[f][1]) for e in "ab" for f in "ab") < .03 for q in c): c.append(t); rest.remove(t); grew = True
        comps.append(c)
    gv = [v for v in d["vias"] if guard.GND.match(v["net"])]
    GV = np.array([v["p"] for v in gv]); allspac = []; out = []
    for c in comps:
        # order by walking from an end
        keyf = lambda p: (round(p[0] / .03), round(p[1] / .03)); cnt = collections.Counter()
        for t in c:
            for e in "ab": cnt[keyf(t[e])] += 1
        ends = [t[e] for t in c for e in "ab" if cnt[keyf(t[e])] == 1]; branch = any(v > 2 for v in cnt.values())
        start = min(ends, key=lambda p: p[0]) if ends else c[0]["a"]; cur = tuple(start); rest2 = c[:]; path = []
        while rest2:
            bs = None
            for i, t in enumerate(rest2):
                for e, o in (("a", "b"), ("b", "a")):
                    dd = math.hypot(t[e][0] - cur[0], t[e][1] - cur[1])
                    if dd < .05 and (bs is None or dd < bs[0]): bs = (dd, i, e, o)
            if bs is None: break
            _, i, e, o = bs; t = rest2.pop(i); path.append((np.array(t[e]), np.array(t[o]), t["w"])); cur = tuple(t[o])
        L = sum(np.linalg.norm(b - a) for a, b, _ in path)
        pos = []; s0 = 0
        for a, b, w in path:
            m = (GV[:, 0] >= min(a[0], b[0]) - .1) & (GV[:, 0] <= max(a[0], b[0]) + .1) & (GV[:, 1] >= min(a[1], b[1]) - .1) & (GV[:, 1] <= max(a[1], b[1]) + .1)
            for p in GV[m]:
                dist, t = seg_dist(p, a, b)
                if dist <= .08: pos.append(s0 + t * np.linalg.norm(b - a))
            s0 += np.linalg.norm(b - a)
        pos = sorted(pos); pos = [p for i, p in enumerate(pos) if i == 0 or p - pos[i - 1] > .05]
        sp = list(np.diff(pos))
        out.append({"len": float(L), "nv": len(pos), "sp": [float(x) for x in sp], "first": float(pos[0]) if pos else None, "last": float(L - pos[-1]) if pos else None,
                    "start": [float(x) for x in start], "end": [float(x) for x in cur], "branch": branch, "uncovered": len(rest2), "wmax": max(w for *_, w in path)})
        allspac += sp
    out.sort(key=lambda o: -o["len"])
    for o in out[:40]:
        sp = o["sp"]
        print("guard piece len %6.2f mm (%5.0f mil) start (%.2f,%.2f) end (%.2f,%.2f) vias %2d  spacing min/med/max %s  first %s last %s %s" % (
            o["len"], o["len"] / .0254, *o["start"], *o["end"], o["nv"], ("%.2f/%.2f/%.2f" % (min(sp), np.median(sp), max(sp))) if sp else "-",
            "%.2f" % o["first"] if o["first"] is not None else "-", "%.2f" % o["last"] if o["last"] is not None else "-", "BRANCH" if o["branch"] else ""))
    if allspac:
        a = np.array(allspac); print("ALL via spacings along guard pieces (n=%d): min %.2f med %.2f max %.2f mm; mil: %.0f/%.0f/%.0f; >5.08 mm (200 mil): %d" % (
            len(a), a.min(), np.median(a), a.max(), a.min() / .0254, np.median(a) / .0254, a.max() / .0254, (a > 5.08).sum()))
        print(" percentiles 10/50/90:", np.percentile(a, [10, 50, 90]).round(2))
    json.dump(out, open(sys.argv[4], "w")) if len(sys.argv) > 4 else None
    # layer-change vias
    sv = [v for v in d["vias"] if rxs.search(v["net"])]
    print("signal vias:", len(sv), "GND via size:", collections.Counter((round(v["w"], 2), round(v["d"], 2)) for v in gv if v["w"]).most_common(3), "signal via size:", collections.Counter((round(v["w"], 2), round(v["d"], 2)) for v in sv))
    dd = []
    for v in sv:
        di = np.hypot(GV[:, 0] - v["p"][0], GV[:, 1] - v["p"][1]); dd.append(float(np.sort(di)[0]))
    if dd: print(" nearest GND via to signal vias (centre-centre mm): min %.2f med %.2f max %.2f; within 0.76 mm (30 mil): %d/%d; within 0.635 (25 mil): %d" % (min(dd), np.median(dd), max(dd), sum(x <= .762 for x in dd), len(dd), sum(x <= .635 for x in dd)))
    return out

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
