"""xsec.py <dump.json> <layer> <axis x|y> <value> <lo> <hi> [signal-regex]
Cross-section: cut the layer along the line axis=value, from lo to hi on the other axis; list every copper object crossed
(tracks: crossing interval of the full-width track; vias: chord; GND zone fill as 'zone'), with net, width and gap to the previous."""
import sys, json, re, math

def cut(d, layer, axis, val, lo, hi):
    ai = 0 if axis == "x" else 1; bi = 1 - ai
    objs = []
    for t in d["tracks"]:
        if t["l"] != layer: continue
        a, b = t["a"], t["b"]
        if (a[ai] - val) * (b[ai] - val) > 0 and abs(a[ai] - val) > t["w"] and abs(b[ai] - val) > t["w"]: continue
        dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy)
        if L < 1e-9: continue
        # point where centerline meets the cut line
        da = a[ai] - val; db = b[ai] - val
        if da == db: continue                      # parallel to cut: only counts if it lies on it, skip
        s = da / (da - db)
        if not -1e-9 <= s <= 1 + 1e-9: continue
        c = a[bi] + s * (b[bi] - a[bi])
        # angle between track and cut line -> chord length of the track strip along the cut
        cosang = abs(((b[ai] - a[ai]) / L))        # component along cut-normal
        chord = t["w"] / cosang if cosang > 1e-6 else t["w"]
        if lo <= c <= hi:
            objs.append((c - chord / 2, c + chord / 2, "trk", t["net"], t["w"], round(math.degrees(math.acos(min(1, cosang))), 1)))
    for v in d["vias"]:
        off = abs(v["p"][ai] - val)
        if off < v["w"] / 2 and lo <= v["p"][bi] <= hi:
            h = math.sqrt((v["w"] / 2) ** 2 - off ** 2); c = v["p"][bi]
            objs.append((c - h, c + h, "via", v["net"], v["w"], 0))
    objs.sort()
    return objs

if __name__ == "__main__":
    d = json.load(open(sys.argv[1])); layer, axis, val, lo, hi = sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5]), float(sys.argv[6])
    prev = None
    for o in cut(d, layer, axis, val, lo, hi):
        gap = "" if prev is None else "gap %.3f" % (o[0] - prev)
        print("%8.3f..%8.3f  %s %-18s w=%.3f ang=%s  %s" % (o[0], o[1], o[2], o[3], o[4], o[5], gap)); prev = max(prev or -1e9, o[1])
