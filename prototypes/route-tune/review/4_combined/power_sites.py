"""PROTOTYPE review (issue 21): how many SDRAM power / ground balls still have a free via site next to them.

A via site = centre of four balls (or the same offset into the ball-free middle / outside the outer columns).
A site is free when a 0.30 mm via there keeps 0.09 mm to every bus track on L1, L4, L6, to every bus via and
to every ball pad. Usage: python power_sites.py <key> [<key> ...]
"""
import os, sys, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recheck4 as R

POWER = [b for b, f in R.SDR_FUNC.items() if f in ("VDD", "VSS", "VDDQ", "VSSQ")]
COLX = {1: 23.8, 2: 24.6, 3: 25.4, 7: 28.6, 8: 29.4, 9: 30.2}

for key in sys.argv[1:]:
    B = R.load(os.path.join(R.ROOT, "out", key, "routetune.kicad_pcb"))
    P = []
    for s in B["segs"] + B["arcs"]:
        if s["net"].startswith("/FMC_"):
            pp = R.seg_pts(s["a"], s["b"], 0.01) if "m" not in s else R.arc_pts(s, 0.01)
            P += [(x, y, s["w"] / 2) for x, y in pp]
    P = np.array(P)
    vias = [v for v in B["vias"] if v["net"].startswith("/FMC_")]
    pads = [p for p in B["pads"] if p["ref"] == "U2"]
    blocked = []
    for b in sorted(POWER):
        bx, by = COLX[int(b[1:])], 10.3 + 0.8 * R.ROWS.index(b[0])
        free = 0
        for dx in (-0.4, 0.4):
            for dy in (-0.4, 0.4):
                x, y = bx + dx, by + dy
                if not R.inrect((x, y), R.BODY["U2"], -0.2):
                    continue
                ok = float(np.min(np.hypot(P[:, 0] - x, P[:, 1] - y) - P[:, 2])) >= 0.15 + 0.09 - 1e-6
                ok = ok and all(math.hypot(v["p"][0] - x, v["p"][1] - y) >= 0.15 + v["d"] / 2 + 0.09 - 1e-6 for v in vias)
                ok = ok and all(math.hypot(p["p"][0] - x, p["p"][1] - y) >= 0.15 + p["d"] / 2 + 0.09 - 1e-6 for p in pads)
                free += ok
        if free == 0:
            blocked.append(b + " " + R.SDR_FUNC[b])
    print("%-18s power/ground balls: %d, with no free via site left: %d %s" % (key, len(POWER), len(blocked), blocked))
