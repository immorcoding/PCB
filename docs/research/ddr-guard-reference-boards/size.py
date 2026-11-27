"""size.py <dump.json> <analysis.json> <soc-ref> <dram-ref>...: SoC-to-DRAM ball-field distance and how close the lane copper runs to the ball fields."""
import sys, json, math
import numpy as np
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import analyze_lane as al
d = json.load(open(sys.argv[1])); res = json.load(open(sys.argv[2])); soc = sys.argv[3]
Hs = al.hull([p["p"] for p in d["pads"] if p["ref"] == soc and p["smd"]])
for ref in sys.argv[4:]:
    P = np.array([p["p"] for p in d["pads"] if p["ref"] == ref]); R = (P[:, 0].min() - .19, P[:, 1].min() - .19, P[:, 0].max() + .19, P[:, 1].max() + .19)
    # distance between hull polygon (SoC ball field incl. ball radius 0.15) and DRAM ball rectangle: min over DRAM rect corners/edge samples
    S = [p["p"] for p in d["pads"] if p["ref"] == ref]
    best = min(al.hull_dist(Hs, q) for q in S) - .15 - .19     # edge to edge ball fields (outer edges of ball copper)
    print(ref, "DRAM ball rect x %.2f..%.2f y %.2f..%.2f" % (R[0], R[2], R[1], R[3]), " SoC ball-field hull edge to nearest DRAM ball edge: %.2f mm (%.0f mil)" % (best, best / .0254))
allr = [r for pcs in res.values() for pc in pcs for r in pc["rec"]]
near = [r for r in allr if r["dram"] > .3 and r["dram"] < 3]
nearS = [r for r in allr if r["soc"] > .3 and r["soc"] < 3]
print("lane signal samples running within 3 mm of a DRAM ball-field edge: n=%d (%.1f mm); distance (signal centre to rect edge) min/median %.2f/%.2f" % (len(near), len(near) * .05, min(r["dram"] for r in near), np.median([r["dram"] for r in near])))
print("lane signal samples within 3 mm of SoC hull edge: n=%d; min/median %.2f/%.2f" % (len(nearS), min(r["soc"] for r in nearS), np.median([r["soc"] for r in nearS])))
