"""PROTOTYPE review (issue 21): own raster of the "swept area" (bus copper outside the two package outlines,
grown by half the width + 0.127 mm, 0.05 mm grid, three layers merged). Also thin (0.09) track length per layer
that lies outside both package outlines. Usage: python swept.py <key> [...]"""
import os, sys, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recheck4 as R
G = 0.05
for key in sys.argv[1:]:
    B = R.load(os.path.join(R.ROOT, "out", key, "routetune.kicad_pcb"))
    M = json.load(open(os.path.join(R.ROOT, "out", key, "metrics.json"), encoding="utf-8"))
    grid = np.zeros((int(40 / G), int(30 / G)), bool)
    thin = {}
    for s in B["segs"] + B["arcs"]:
        if not s["net"].startswith("/FMC_"):
            continue
        pp = R.seg_pts(s["a"], s["b"], 0.02) if "m" not in s else R.arc_pts(s, 0.02)
        out = [p for p in pp if not R.inrect(p, R.BODY["U1"]) and not R.inrect(p, R.BODY["U2"])]
        if abs(s["w"] - 0.09) < 1e-6 and len(pp) > 1:
            L = math.hypot(s["b"][0] - s["a"][0], s["b"][1] - s["a"][1]) * len(out) / len(pp)
            if R.LAY[s["layer"]] == "L1" and not R.inrect(pp[len(pp) // 2], (7, 6, 19, 18)):
                thin[s["net"][5:]] = thin.get(s["net"][5:], 0.0) + L
        r = s["w"] / 2 + 0.127
        k = int(r / G) + 1
        for x, y in out:
            i, j = int(x / G), int(y / G)
            for a in range(i - k, i + k + 1):
                for b in range(j - k, j + k + 1):
                    if (a + 0.5) * G - x and math.hypot((a + 0.5) * G - x, (b + 0.5) * G - y) <= r:
                        grid[a, b] = True
    print("%-18s swept %.1f mm2 (metrics %s); 0.09 track on L1 outside the MCU rule area and outside both bodies, per net: %s" % (
        key, grid.sum() * G * G, M["space"]["bus_swept_area_mm2"]["all"], {k: round(v, 2) for k, v in sorted(thin.items()) if v > 1.0}))
