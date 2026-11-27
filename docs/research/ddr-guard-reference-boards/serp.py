"""serp.py <analysis.json>: find serpentine (meander) sections along each net = runs where the path heading reverses (>=150 deg
change within 1.0 mm of path) repeatedly. Prints per net: number of U-turns, region bbox, leg lengths and leg gaps (centre to centre)."""
import sys, json, math
import numpy as np
res = json.load(open(sys.argv[1]))
for net, pcs in res.items():
    for pi, pc in enumerate(pcs):
        P = np.array([r["p"] for r in pc["rec"]]); S = np.array([r["s"] for r in pc["rec"]])
        if len(P) < 30: continue
        k = 10   # 0.5 mm lookback for heading
        hd = np.degrees(np.arctan2(P[k:, 1] - P[:-k, 1], P[k:, 0] - P[:-k, 0]))
        # U-turn: heading differs by >=150 deg between points 1.0 mm apart in path
        j = 20
        turns = []
        for i in range(len(hd) - j):
            dh = abs((hd[i + j] - hd[i] + 180) % 360 - 180)
            if dh >= 150: turns.append(i + k // 2 + j // 2)
        # merge turn indices
        ev = []
        for t in turns:
            if not ev or t - ev[-1][-1] > 20: ev.append([t])
            else: ev[-1].append(t)
        centres = [int(np.mean(e)) for e in ev]
        if len(centres) >= 2:
            pts = P[centres]; legs = np.diff(S[centres])
            print("%-14s piece%d  U-turns %d  at path s=%s  region x %.2f..%.2f y %.2f..%.2f  leg lengths %s" % (
                net, pi, len(centres), np.round(S[centres], 1).tolist(), pts[:, 0].min(), pts[:, 0].max(), pts[:, 1].min(), pts[:, 1].max(), np.round(legs, 2).tolist()))
