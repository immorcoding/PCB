"""serp_lanes.py <dump.json> <layer> <net-regex> <soc-ref> <dram-map like _A=U3300,_B=U3300>: wiggle sections (see wiggle.py) of the lane nets that lie
>= 1.0 mm outside the SoC ball-field hull and the DRAM ball rectangle, with amplitude (offset range perpendicular to the section chord),
period (spacing of same-direction corners) and leg lengths."""
import sys, json, re, math
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import numpy as np
import analyze_lane as al

d = json.load(open(sys.argv[1])); layer, rx, soc = sys.argv[2:5]
drams = dict(x.split("=") for x in sys.argv[5].split(","))
H = al.hull([p["p"] for p in d["pads"] if p["ref"] == soc and p["smd"]])
R = {}
for suf, ref in drams.items():
    P = np.array([p["p"] for p in d["pads"] if p["ref"] == ref]); R[suf] = (P[:, 0].min() - .19, P[:, 1].min() - .19, P[:, 0].max() + .19, P[:, 1].max() + .19)
rxs = re.compile(rx)
for net in sorted({t["net"] for t in d["tracks"] if t["l"] == layer and rxs.search(t["net"])}):
    suf = next((s for s in R if net.endswith(s)), None)
    for path, rest in al.pieces([t for t in d["tracks"] if t["l"] == layer and t["net"] == net]):
        segs = [(np.array(t["a"]), np.array(t["b"])) for t in path if np.linalg.norm(np.array(t["b"]) - np.array(t["a"])) > 1e-6]
        corners = []
        for i in range(len(segs) - 1):
            h1 = math.degrees(math.atan2(*(segs[i][1] - segs[i][0])[::-1])); h2 = math.degrees(math.atan2(*(segs[i + 1][1] - segs[i + 1][0])[::-1]))
            dh = (h2 - h1 + 180) % 360 - 180
            if abs(dh) >= 40: corners.append((i, dh, segs[i][1]))
        merged = []
        for c in corners:
            if merged and merged[-1][0] + 1 == c[0] and np.sign(merged[-1][1]) == np.sign(c[1]): merged[-1] = (c[0], merged[-1][1] + c[1], c[2])
            else: merged.append(c)
        runs, run = [], merged[:1]
        for c in merged[1:]:
            if np.sign(c[1]) != np.sign(run[-1][1]) and np.linalg.norm(c[2] - run[-1][2]) <= 1.6: run.append(c)
            else: runs.append(run); run = [c]
        runs.append(run)
        for run in runs:
            if len(run) < 6: continue
            pts = np.array([r[2] for r in run]); ch = pts[-1] - pts[0]; L = np.linalg.norm(ch)
            if L < 1e-6: continue
            off = np.cross(ch / L, pts - pts[0]); amp = off.max() - off.min(); legs = [np.linalg.norm(pts[k + 1] - pts[k]) for k in range(len(pts) - 1)]
            if amp > 0.8 or L / sum(legs) < .85: continue
            m = pts.mean(0); dm = min(al.hull_dist(H, m), al.rect_dist(R[suf], m) if suf else 9)
            if dm < 1.0: continue
            cs = [r[1] for r in run]; period = np.mean([np.linalg.norm(pts[k + 2] - pts[k]) for k in range(len(pts) - 2)])
            print("%-14s corners %2d  centre (%.2f,%.2f)  section length %.2f mm  amplitude %.2f mm  period %.2f mm  legs med %.2f  dist to ball fields %.1f mm" % (net, len(run), m[0], m[1], L, amp, period, np.median(legs), dm))
