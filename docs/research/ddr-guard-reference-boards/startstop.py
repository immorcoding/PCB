"""startstop.py <analysis.json> [net-regex]: for each net piece that runs from a SoC ball to a DRAM ball on this layer: where does GND *track*
guard copper first / last appear on either side (>= 0.5 mm of continuous presence), as signed distance to the SoC ball-field hull
(negative = inside the ball field) and to the DRAM ball rectangle, plus the largest guard-free gap (no GND track within 0.30 mm on
either side) between the first and the last guard sample, and the spacing between the two lines in the guard-free stretch."""
import sys, json, re
import numpy as np
STEP = .05
res = json.load(open(sys.argv[1]))
if len(sys.argv) > 2: res = {k: v for k, v in res.items() if re.search(sys.argv[2], k)}
GND = re.compile(r"^(GND|VSS)", re.I)
def gtrk(r): return any(x and GND.match(x[1]) and x[2] in ("trk", "arc") and x[0] <= .3 for x in r["sd"])
F, L = [], []
for net, pcs in res.items():
    for pc in pcs:
        rec = pc["rec"]
        if len(rec) < 60: continue
        # orient: the end near the SoC first
        if rec[0]["soc"] > rec[-1]["soc"]: rec = rec[::-1]
        if rec[0]["soc"] > 3 or rec[-1]["dram"] > 3: continue     # not a SoC-to-DRAM piece
        flags = [gtrk(r) for r in rec]
        def first(fl):
            for i in range(len(fl) - 10):
                if all(fl[i:i + 10]): return i
        i0 = first(flags); i1 = first(flags[::-1])
        if i0 is None or i1 is None: print(net, "no guard track >= 0.5 mm"); continue
        i1 = len(rec) - 1 - i1
        gap = 0; best = 0
        for f in flags[i0:i1 + 1]:
            gap = 0 if f else gap + 1; best = max(best, gap)
        F.append(rec[i0]["soc"]); L.append(rec[i1]["dram"])
        print("%-15s len %5.1f  first guard-track: s=%.2f soc-hull dist %+.2f (%.2f,%.2f) | last: dram-rect dist %+.2f (%.2f,%.2f) | longest guard-free gap in between %.2f mm" % (
            net, len(rec) * STEP, rec[i0]["s"], rec[i0]["soc"], *rec[i0]["p"], rec[i1]["dram"], *rec[i1]["p"], best * STEP))
if F: print("first-guard distance to SoC hull (mm) min/med/max %.2f/%.2f/%.2f ; last-guard distance to DRAM rect %.2f/%.2f/%.2f" % (min(F), np.median(F), max(F), min(L), np.median(L), max(L)))
