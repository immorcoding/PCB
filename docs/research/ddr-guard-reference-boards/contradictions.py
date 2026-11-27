"""contradictions.py <analysis.json> [minlen_mm]: per net, runs outside the ball fields (>0.3 mm from the SoC hull and the DRAM ball rectangle)
 - NOGUARD: no GND copper (<=0.30 mm gap) on either side
 - ONESIDE: GND on one side only and nothing (or foreign copper) on the other (not the pair partner)
 - SS:      both sides are lane signals (three or more signals between guards)
 - 'wide':  GND present but its gap is 0.3-1.5 mm on a side (too far to be a guard in the 1x width sense)"""
import sys, json, collections, re
STEP = .05
res = json.load(open(sys.argv[1])); minlen = float(sys.argv[2]) if len(sys.argv) > 2 else .5
if len(sys.argv) > 3: res = {k: v for k, v in res.items() if re.search(sys.argv[3], k)}
GND = re.compile(r"^(GND|VSS)", re.I)
def runs(rec, pred):
    out, cur = [], None
    for r in rec:
        if pred(r):
            cur = [r, r] if cur is None else [cur[0], r]
        else:
            if cur and cur[1]["s"] - cur[0]["s"] + STEP >= minlen: out.append(cur)
            cur = None
    if cur and cur[1]["s"] - cur[0]["s"] + STEP >= minlen: out.append(cur)
    return out
tot = collections.Counter(); length = collections.defaultdict(float)
for net, pcs in res.items():
    for pc in pcs:
        rec = [r for r in pc["rec"]]
        far = lambda r: r["soc"] > .3 and r["dram"] > .3
        def g(x): return x is not None and GND.match(x[1]) and x[0] <= .3
        def wide(x): return x is not None and GND.match(x[1]) and .3 < x[0] <= 1.5
        preds = {
            "NOGUARD": lambda r: far(r) and not (r["c"][0] == "G" or r["c"][1] == "G"),
            "ONESIDE": lambda r: far(r) and (r["c"].count("G") == 1) and (r["c"].count("S") == 0),
            "SS": lambda r: far(r) and r["c"] == "SS",
            "wide": lambda r: far(r) and any(wide(x) for x in r["sd"]) and not any(g(x) for x in r["sd"]),
        }
        for k, p in preds.items():
            for a, b in runs(rec, p):
                L = b["s"] - a["s"] + STEP; tot[k] += 1; length[k] += L
                print("%-8s %-14s %.2f mm  (%.2f,%.2f)->(%.2f,%.2f)  nbrs %s" % (k, net, L, *a["p"], *b["p"], [x[1] if x else None for x in a["sd"]]))
print({k: (tot[k], round(length[k], 1)) for k in tot})
