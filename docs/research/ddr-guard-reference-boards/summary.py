"""summary.py <analysis.json from analyze_lane.main(jout=...)> : length-weighted statistics outside the ball fields.
Prints: signal width, G-S gap (nearest GND copper track on a side), guard track width, S-S gap, coverage by pattern."""
import sys, json, collections, re
import numpy as np
STEP = .05
res = json.load(open(sys.argv[1]))
if len(sys.argv) > 2:
    nre = re.compile(sys.argv[2]); res = {k: v for k, v in res.items() if nre.search(k)}
GND = re.compile(r"^(GND|VSS)", re.I)
gaps = collections.defaultdict(list); gw = []; sw = []; sg = []; pat = collections.Counter(); tot = 0; farg = []
for net, pcs in res.items():
    for pc in pcs:
        for r in pc["rec"]:
            if r["soc"] <= .3 or r["dram"] <= .3: continue
            tot += 1; sw.append(r["w"]); pat[r["c"] if r["c"][0] <= r["c"][1] else r["c"][::-1]] += 1
            for x in r["sd"]:
                if not x: continue
                if GND.match(x[1]) and x[2] == "trk": gaps["G-S"].append(x[0]); gw.append(x[3])
                elif GND.match(x[1]): gaps["G-S via/pad"].append(x[0])
                elif x[2] == "trk" and x[0] < .5: sg.append(x[0])
                if GND.match(x[1]) and .3 < x[0] <= 1.5: farg.append(x[0])
print("samples outside ball fields: %d (%.1f mm of signal)" % (tot, tot * STEP))
print("signal width (mm) counts:", collections.Counter(round(w, 3) for w in sw).most_common(6))
for k, v in gaps.items():
    v = np.array(v); print(k, "n", len(v), "gap mm pct 5/25/50/75/95:", np.percentile(v, [5, 25, 50, 75, 95]).round(3))
print("guard track width mm counts (length-weighted by sample):", collections.Counter(round(w, 3) for w in gw).most_common(10))
sg = np.array(sg) if len(sg) else np.array([np.nan]); print("signal-to-signal gap (<0.5) pct 5/25/50/75/95:", np.percentile(sg, [5, 25, 50, 75, 95]).round(3), collections.Counter(np.round(sg, 2)).most_common(5))
print("side-pattern shares (G,S,X,O per side, unordered):", [(k, "%.1f%%" % (100 * v / tot)) for k, v in pat.most_common(10)])
farg = np.array(farg); print("GND neighbour at 0.3-1.5 mm gap: n %d" % len(farg), np.percentile(farg, [10, 50, 90]).round(2) if len(farg) else "")
