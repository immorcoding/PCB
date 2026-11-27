"""wiggle.py <dump.json> <layer> <net-regex>: find meander / wiggle (length-tuning) sections on the layer.
Walk each net's connected pieces; at each node where the heading changes >= 40 deg note the signed turn. A wiggle = >=4 consecutive corners
with alternating sign and legs <= 2.5 mm. Report net, board bbox of the section, number of bumps, amplitude (max perpendicular
deviation from the section's end-to-end chord) and leg lengths."""
import sys, json, re, math
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import numpy as np
import analyze_lane as al

def main(d, layer, rx):
    rxs = re.compile(rx); out = []
    for net in sorted({t["net"] for t in d["tracks"] if t["l"] == layer and rxs.search(t["net"])}):
        for path, rest in al.pieces([t for t in d["tracks"] if t["l"] == layer and t["net"] == net]):
            segs = [(np.array(t["a"]), np.array(t["b"])) for t in path if np.linalg.norm(np.array(t["b"]) - np.array(t["a"])) > 1e-6]
            if len(segs) < 5: continue
            corners = []                                 # (index of node, signed turn, location)
            for i in range(len(segs) - 1):
                h1 = math.degrees(math.atan2(*(segs[i][1] - segs[i][0])[::-1])); h2 = math.degrees(math.atan2(*(segs[i + 1][1] - segs[i + 1][0])[::-1]))
                dh = (h2 - h1 + 180) % 360 - 180
                if abs(dh) >= 40: corners.append((i, dh, segs[i][1]))
            # sequence of corners with alternating sign, merging 45+45 chamfer pairs into one 90
            merged = []
            for c in corners:
                if merged and merged[-1][0] + 1 == c[0] and np.sign(merged[-1][1]) == np.sign(c[1]): merged[-1] = (c[0], merged[-1][1] + c[1], c[2])
                else: merged.append(c)
            run = [merged[0]] if merged else []
            def flush(run):
                if len(run) >= 6:
                    pts = np.array([r[2] for r in run]); a, b = pts[0], pts[-1]; ch = b - a; L = np.linalg.norm(ch)
                    dev = np.abs(np.cross(ch / L, pts - a)).max() if L > 0 else 0
                    legs = [np.linalg.norm(pts[k + 1] - pts[k]) for k in range(len(pts) - 1)]
                    ratio = L / sum(legs)
                    if ratio < 0.85 or dev > 0.7: return
                    out.append((net, len(run), pts[:, 0].min(), pts[:, 0].max(), pts[:, 1].min(), pts[:, 1].max(), dev, legs))
            for c in merged[1:]:
                prev = run[-1]
                if np.sign(c[1]) != np.sign(prev[1]) and np.linalg.norm(c[2] - prev[2]) <= 2.5: run.append(c)
                else: flush(run); run = [c]
            flush(run)
    return out

if __name__ == "__main__":
    d = json.load(open(sys.argv[1]))
    for net, n, x0, x1, y0, y1, dev, legs in main(d, sys.argv[2], sys.argv[3]):
        print("%-14s corners %2d  x %.2f..%.2f y %.2f..%.2f  max dev from chord %.2f mm  legs min/med/max %.2f/%.2f/%.2f  chord/path %.2f" % (net, n, x0, x1, y0, y1, dev, min(legs), np.median(legs), max(legs), np.linalg.norm([x1-x0,y1-y0]) / sum(legs)))
