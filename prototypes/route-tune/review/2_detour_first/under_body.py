"""PROTOTYPE review (issue 21): bus track length under each package body, per variant (copper the space numbers do not count)."""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recheck as R
for key in sys.argv[1:]:
    d, segs, arcs, vias, pads, cu, zones = R.load(key)
    tot, under = {}, {"U1": {}, "U2": {}}
    for s in segs:
        if not s["net"].startswith("/FMC_"):
            continue
        L = math.hypot(s["b"][0] - s["a"][0], s["b"][1] - s["a"][1]); l = R.LAY[s["layer"]]
        tot[l] = tot.get(l, 0) + L
        for u, B in R.BODY.items():
            under[u][l] = under[u].get(l, 0) + R.clip_len_inside(s["a"], s["b"], B)
    f = lambda dct: " ".join("%s %.1f" % kv for kv in sorted(dct.items()))
    print("%-18s track (no arcs): %s | under SDRAM body: %s (sum %.1f) | under MCU body: %s | arcs %d" % (
        key, f(tot), f(under["U2"]), sum(under["U2"].values()), f(under["U1"]), len(arcs)))
