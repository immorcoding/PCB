"""Tidy the corners in an autorouter result (the JSON written by auto_tracks.py), in place.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.third_party.auto_clean <auto_tracks.json> [--dry]

The autorouter does not know the corner rule (interior angle >= 135 degrees). At every
point where exactly two of its segments of one net meet on one layer at a sharper angle:

  staircase   both segments shorter than 0.35 mm and the far ends line up at 0/45/90 degrees:
              the pair becomes one straight segment
  corner      otherwise the corner is cut back by CUT (or a third of the shorter segment) on
              each side and bridged, turning one 90-degree bend into two 135-degree ones

T-junctions (three segments at a point) and bends at a via are left alone and listed; so is
anything that would need a segment off the 45-degree grid. Clearances are not checked here:
run DRC afterwards.
"""
import json, math, sys

CUT = 0.25
path = sys.argv[1]
items = json.load(open(path, encoding="utf-8"))
segs = [o for o in items if o["k"] == "seg"]
vias = {(o["net"], tuple(o["at"])) for o in items if o["k"] == "via"}


def key(p):
    return (round(p[0], 3), round(p[1], 3))


def ang(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def interior(b, a, c):
    """Angle at b between b->a and b->c."""
    d = abs((ang(b, a) - ang(b, c) + 180) % 360 - 180)
    return d


def on_grid(a, c):
    dx, dy = abs(c[0] - a[0]), abs(c[1] - a[1])
    return dx < 2e-3 or dy < 2e-3 or abs(dx - dy) < 2e-3


def length(s):
    return math.hypot(s["b"][0] - s["a"][0], s["b"][1] - s["a"][1])


changed, left = 0, []
for _ in range(12):                                    # a few passes: one fix can expose the next
    nodes = {}
    for s in segs:
        for end in ("a", "b"):
            nodes.setdefault((s["net"], s["layer"], key(s[end])), []).append((s, end))
    did = False
    touched = set()        # segments changed in this pass: their entries in `nodes` are stale
    for (net, layer, pt), ends in nodes.items():
        if len(ends) != 2 or (net, pt) in vias or any(id(e[0]) in touched for e in ends):
            continue
        (s1, e1), (s2, e2) = ends
        if s1 is s2:
            continue
        a = s1["b" if e1 == "a" else "a"]; c = s2["b" if e2 == "a" else "a"]; b = s1[e1]
        if interior(b, a, c) >= 134:
            continue
        l1, l2 = length(s1), length(s2)
        if l1 < 0.35 and l2 < 0.35 and on_grid(a, c) and key(a) != key(c):
            s1["a"], s1["b"] = list(a), list(c); s2["dead"] = True
            touched |= {id(s1), id(s2)}
            did = True; changed += 1
            continue
        if abs(interior(b, a, c) - 90) < 1 and on_grid(a, b) and on_grid(b, c):
            d = min(CUT, l1 / 3, l2 / 3)
            p1 = [round(b[0] + (a[0] - b[0]) * d / l1, 4), round(b[1] + (a[1] - b[1]) * d / l1, 4)]
            p2 = [round(b[0] + (c[0] - b[0]) * d / l2, 4), round(b[1] + (c[1] - b[1]) * d / l2, 4)]
            s1[e1], s2[e2] = p1, p2
            segs.append({"k": "seg", "net": net, "a": p1, "b": p2, "w": min(s1["w"], s2["w"]), "layer": layer})
            touched |= {id(s1), id(s2)}
            did = True; changed += 1
    segs = [s for s in segs if not s.get("dead")]
    if not did:
        break

nodes = {}
for s in segs:
    for end in ("a", "b"):
        nodes.setdefault((s["net"], s["layer"], key(s[end])), []).append((s, end))
for (net, layer, pt), ends in sorted(nodes.items()):
    pts = [e[0]["b" if e[1] == "a" else "a"] for e in ends]
    worst = min((interior(pt, p, q) for i, p in enumerate(pts) for q in pts[i + 1:]), default=180)
    if worst < 134:
        left.append(f"  {net} {layer} at {pt}: {len(ends)} segments, sharpest {worst:.0f} deg")

print(f"{changed} corners fixed; {len(left)} left:")
print("\n".join(left))
if "--dry" not in sys.argv:
    out = [o for o in items if o["k"] == "via"] + segs
    out.sort(key=lambda o: (o["net"], o["k"], json.dumps(o)))
    json.dump(out, open(path, "w", encoding="utf-8"), indent=0)
