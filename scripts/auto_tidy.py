"""Straighten the autorouter's tracks (the JSON written by auto_tracks.py), in place.

    D:\\KiCad\\bin\\python.exe scripts\\auto_tidy.py <board.kicad_pcb> <auto_tracks.json> [--clearance 0.16] [--dry]

<board> is a board that holds the hand-routed copper and the autorouted copper, with the
hand-routed copper KiCad-locked (what `route.py --no-pour` writes). Pads, vias, locked
tracks, rule areas and the board edge are taken from it as obstacles.

For each autorouted net and layer the tracks are split into runs between fixed points: a
pad, a via, a junction of three or more tracks, or the end of a hand-routed track. Fixed
points do not move. Each run is rebuilt greedily from as few pieces as possible, where a
piece is a straight segment or a straight-diagonal-straight dog-leg on the 45-degree grid,
and is accepted only if it keeps the clearance to every obstacle and to the other nets'
autorouted tracks (as they stand at that moment), and turns by at most 45 degrees where it
meets the track before it or a track at the fixed point. A run that cannot be improved is
left as it was.

This is geometry on bounding boxes, not a design-rule check: run DRC afterwards.
"""
import json, math, sys
import pcbnew

args = sys.argv[1:]
CLR = float(args[args.index("--clearance") + 1]) if "--clearance" in args else 0.16
board_path, json_path = args[0], args[1]
EDGE = 0.35
mm = pcbnew.ToMM
b = pcbnew.LoadBoard(board_path)
L = lambda v: (round(mm(v.x) - 100, 4), round(mm(v.y) - 100, 4))
items = json.load(open(json_path, encoding="utf-8"))
auto_segs = [o for o in items if o["k"] == "seg"]
auto_vias = [o for o in items if o["k"] == "via"]


def key(p):
    return (round(p[0], 3), round(p[1], 3))


# ---------------------------------------------------------------- obstacles
rects = {"F.Cu": [], "B.Cu": []}        # (x0, y0, x1, y1, net)
circles = []                            # (x, y, r, net)  vias: both layers
hand = {"F.Cu": [], "B.Cu": []}         # (a, b, halfwidth, net)
pad_pts = {"F.Cu": {}, "B.Cu": {}}      # pad centre -> net
for fp in b.GetFootprints():
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        r = (mm(bb.GetLeft()) - 100, mm(bb.GetTop()) - 100, mm(bb.GetRight()) - 100, mm(bb.GetBottom()) - 100, p.GetNetname())
        for name, lid in (("F.Cu", pcbnew.F_Cu), ("B.Cu", pcbnew.B_Cu)):
            if p.IsOnLayer(lid) or p.HasHole():
                rects[name].append(r)
                pad_pts[name][key(L(p.GetPosition()))] = p.GetNetname()
    for z in fp.Zones():                # keep-outs carried by a footprint (antenna)
        if z.GetIsRuleArea() and z.GetDoNotAllowTracks():
            bb = z.GetBoundingBox()
            r = (mm(bb.GetLeft()) - 100, mm(bb.GetTop()) - 100, mm(bb.GetRight()) - 100, mm(bb.GetBottom()) - 100, None)
            for name, lid in (("F.Cu", pcbnew.F_Cu), ("B.Cu", pcbnew.B_Cu)):
                if z.IsOnLayer(lid):
                    rects[name].append(r)
for z in b.Zones():
    if z.GetIsRuleArea() and z.GetDoNotAllowTracks():
        bb = z.GetBoundingBox()
        r = (mm(bb.GetLeft()) - 100, mm(bb.GetTop()) - 100, mm(bb.GetRight()) - 100, mm(bb.GetBottom()) - 100, None)
        for name, lid in (("F.Cu", pcbnew.F_Cu), ("B.Cu", pcbnew.B_Cu)):
            if z.IsOnLayer(lid):
                rects[name].append(r)
via_pts = {}
# route.py --no-pour locks the replayed autorouter tracks as well: tell them apart by the JSON
in_json = {(s["net"], s["layer"], frozenset((key(s["a"]), key(s["b"])))) for s in auto_segs}
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        c = L(t.GetPosition())
        circles.append((c[0], c[1], mm(t.GetWidth(pcbnew.F_Cu)) / 2, t.GetNetname()))
        via_pts[key(c)] = t.GetNetname()
    else:
        name = b.GetLayerName(t.GetLayer())
        a, c = L(t.GetStart()), L(t.GetEnd())
        if (t.GetNetname(), name, frozenset((key(a), key(c)))) not in in_json:
            hand[name].append((a, c, mm(t.GetWidth()) / 2, t.GetNetname()))
eb = b.GetBoardEdgesBoundingBox()
EX0, EY0, EX1, EY1 = mm(eb.GetLeft()) - 100 + EDGE, mm(eb.GetTop()) - 100 + EDGE, mm(eb.GetRight()) - 100 - EDGE, mm(eb.GetBottom()) - 100 - EDGE


# ---------------------------------------------------------------- geometry
def d_pt_seg(p, a, c):
    vx, vy = c[0] - a[0], c[1] - a[1]
    k = ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / (vx * vx + vy * vy or 1e-12)
    k = max(0.0, min(1.0, k))
    return math.hypot(p[0] - a[0] - k * vx, p[1] - a[1] - k * vy)


def cross(a, c, e, f):
    def o(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return (o(a, c, e) * o(a, c, f) < 0) and (o(e, f, a) * o(e, f, c) < 0)


def d_seg_seg(a, c, e, f):
    if cross(a, c, e, f):
        return 0.0
    return min(d_pt_seg(a, e, f), d_pt_seg(c, e, f), d_pt_seg(e, a, c), d_pt_seg(f, a, c))


def d_seg_rect(a, c, r):
    x0, y0, x1, y1 = r[:4]
    if (x0 <= a[0] <= x1 and y0 <= a[1] <= y1) or (x0 <= c[0] <= x1 and y0 <= c[1] <= y1):
        return 0.0
    cs = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return min(d_seg_seg(a, c, cs[i], cs[(i + 1) % 4]) for i in range(4))


def clear(a, c, hw, net, layer, others):
    """True if segment a-c (half width hw) of `net` keeps CLR to everything else on `layer`."""
    for p in (a, c):
        if not (EX0 <= p[0] <= EX1 and EY0 <= p[1] <= EY1):
            return False
    lo = (min(a[0], c[0]) - 1.2, min(a[1], c[1]) - 1.2); hi = (max(a[0], c[0]) + 1.2, max(a[1], c[1]) + 1.2)
    for r in rects[layer]:
        if r[4] == net or r[2] < lo[0] - 2.5 or r[0] > hi[0] + 2.5 or r[3] < lo[1] - 2.5 or r[1] > hi[1] + 2.5:
            continue
        if d_seg_rect(a, c, r) < hw + (CLR if r[4] is not None else 0.0):
            return False
    for x, y, rad, n in circles:
        if n != net and lo[0] - rad <= x <= hi[0] + rad and lo[1] - rad <= y <= hi[1] + rad:
            if d_pt_seg((x, y), a, c) < hw + rad + CLR:
                return False
    for e, f, w2, n in hand[layer] + others:
        if n != net and d_seg_seg(a, c, e, f) < hw + w2 + CLR:
            return False
    return True


def turn(d1, d2):
    """Angle in degrees between two directions given as vectors."""
    a = math.degrees(math.atan2(d1[1], d1[0]) - math.atan2(d2[1], d2[0]))
    return abs((a + 180) % 360 - 180)


def pieces(a, c):
    """Candidate polylines from a to c on the 45-degree grid, shortest description first."""
    dx, dy = c[0] - a[0], c[1] - a[1]
    adx, ady = abs(dx), abs(dy)
    if adx < 1e-3 or ady < 1e-3 or abs(adx - ady) < 1e-3:
        return [[a, c]]
    sx, sy = (1 if dx > 0 else -1), (1 if dy > 0 else -1)
    d = min(adx, ady)
    out = []
    rest = (dx - sx * d, dy - sy * d)                 # the straight part, along one axis
    for t in (0.0, 1.0, 0.5, 0.25, 0.75):             # share of the straight part before the diagonal
        p1 = (a[0] + rest[0] * t, a[1] + rest[1] * t)
        p2 = (p1[0] + sx * d, p1[1] + sy * d)
        pts = [a]
        for p in (p1, p2, c):
            if math.hypot(p[0] - pts[-1][0], p[1] - pts[-1][1]) > 1e-3:
                pts.append((round(p[0], 4), round(p[1], 4)))
        if all(math.hypot(q[0] - p[0], q[1] - p[1]) >= 0.2 for p, q in zip(pts, pts[1:])) or len(pts) == 2:
            out.append(pts)
    return out


# ---------------------------------------------------------------- runs
def others_for(net, layer):
    return [(tuple(s["a"]), tuple(s["b"]), s["w"] / 2, s["net"]) for s in auto_segs
            if s["layer"] == layer and s["net"] != net]


def same_net_dirs(net, layer, pt, exclude):
    """Directions of this net's other tracks leaving `pt` on `layer` (hand tracks and autorouted)."""
    out = []
    for e, f, _w, n in hand[layer]:
        if n == net:
            if key(e) == key(pt): out.append((f[0] - e[0], f[1] - e[1]))
            if key(f) == key(pt): out.append((e[0] - f[0], e[1] - f[1]))
    for s in auto_segs:
        if s["net"] == net and s["layer"] == layer and id(s) not in exclude:
            if key(s["a"]) == key(pt): out.append((s["b"][0] - s["a"][0], s["b"][1] - s["a"][1]))
            if key(s["b"]) == key(pt): out.append((s["a"][0] - s["b"][0], s["a"][1] - s["b"][1]))
    return out


before = sum(1 for s in auto_segs)
len_before = sum(math.hypot(s["b"][0] - s["a"][0], s["b"][1] - s["a"][1]) for s in auto_segs)
changed_runs = kept_runs = 0
for net in sorted({s["net"] for s in auto_segs}):
    for layer in ("F.Cu", "B.Cu"):
        mine = [s for s in auto_segs if s["net"] == net and s["layer"] == layer]
        if not mine:
            continue
        deg = {}
        for s in mine:
            for end in ("a", "b"):
                deg.setdefault(key(s[end]), []).append(s)
        hand_ends = {key(p) for e, f, _w, n in hand[layer] if n == net for p in (e, f)}

        own_pads = [r for r in rects[layer] if r[4] == net]

        def fixed(k):
            # a point inside one of the net's own pads is where the track connects to it,
            # whether or not it is the pad centre
            return (len(deg[k]) != 2 or k in via_pts or k in hand_ends
                    or any(r[0] <= k[0] <= r[2] and r[1] <= k[1] <= r[3] for r in own_pads))

        used = set()
        for start in [k for k in deg if fixed(k)]:
            for first in deg[start]:
                if id(first) in used:
                    continue
                run, pts, k = [], [start], start
                s = first
                while True:
                    used.add(id(s)); run.append(s)
                    k = key(s["b"]) if key(s["a"]) == k else key(s["a"])
                    pts.append(k)
                    if fixed(k):
                        break
                    s = next(x for x in deg[k] if id(x) not in used)
                if len(run) < 2 and len(pieces(pts[0], pts[-1])) and len(pts) == 2:
                    kept_runs += 1
                    continue
                hw = max(x["w"] for x in run) / 2
                ids = {id(x) for x in run}
                obst = others_for(net, layer)
                new = [pts[0]]
                prev_dirs = same_net_dirs(net, layer, pts[0], ids)        # tracks to respect at the start
                end_dirs = same_net_dirs(net, layer, pts[-1], ids)
                i, ok = 0, True
                while i < len(pts) - 1:
                    for j in range(len(pts) - 1, i, -1):
                        done = False
                        for cand in pieces(pts[i], pts[j]):
                            d_first = (cand[1][0] - cand[0][0], cand[1][1] - cand[0][1])
                            d_last = (cand[-2][0] - cand[-1][0], cand[-2][1] - cand[-1][1])
                            if any(turn(d_first, d) < 134.5 for d in prev_dirs):
                                continue
                            if j == len(pts) - 1 and any(turn(d_last, d) < 134.5 for d in end_dirs):
                                continue
                            if all(clear(p, q, hw, net, layer, obst) for p, q in zip(cand, cand[1:])):
                                new += cand[1:]
                                prev_dirs = [d_last]
                                i = j; done = True
                                break
                        if done:
                            break
                    else:
                        # nothing fits from here: keep the original segment and carry on after it,
                        # unless that would put a sharp corner where the rebuilt part meets it
                        d0 = (pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
                        if i > 0 and any(turn(d0, d) < 134.5 for d in prev_dirs):
                            ok = False
                            break
                        new.append(pts[i + 1])
                        prev_dirs = [(-d0[0], -d0[1])]
                        i += 1
                if not ok or len(new) - 1 >= len(run):
                    kept_runs += 1
                    continue
                w = max(x["w"] for x in run)
                for x in run:
                    auto_segs.remove(x)
                for p, q in zip(new, new[1:]):
                    auto_segs.append({"k": "seg", "net": net, "a": [p[0], p[1]], "b": [q[0], q[1]], "w": w, "layer": layer})
                changed_runs += 1

len_after = sum(math.hypot(s["b"][0] - s["a"][0], s["b"][1] - s["a"][1]) for s in auto_segs)
print(f"runs rebuilt {changed_runs}, left alone {kept_runs}; segments {before} -> {len(auto_segs)}; "
      f"length {len_before:.0f} -> {len_after:.0f} mm")
if "--dry" not in args:
    out = auto_vias + auto_segs
    out.sort(key=lambda o: (o["net"], o["k"], json.dumps(o)))
    json.dump(out, open(json_path, "w", encoding="utf-8"), indent=0)
