"""PROTOTYPE (issue 16): turn a copper region sketch into KiCad zones. The shapes come from the sketch;
this script only checks them and writes them.

    D:\\KiCad\\bin\\python.exe sketch2zones.py <board in> <sketch.txt> <board out> [gap=<mm>] [chamfer=off]

Checks, before anything is written (any failure stops the run):
  - every edge of every drawn outline is at 0, 45 or 90 degrees (PWR-3)
  - no outline crosses itself; no drawn part is narrower than its minimum width
  - blocks of different nets on one plane layer are at least `gap` apart
  - a pour has pads of its own net under it, and no pad of another net
The background of a plane layer is what is left of the board after every block is grown by `gap`.
"""
import math, sys
import pcbnew
from culib import *

src, sketch, dst = sys.argv[1:4]
opts = dict(a.split("=") for a in sys.argv[4:])
B = pcbnew.LoadBoard(src)
errors, notes = [], []


def parse(path):
    items, cur, plane = [], None, None
    for raw in open(path, encoding="utf-8"):
        line = raw.split("#")[0].strip()
        if not line:
            continue
        w = line.split()
        if w[0] in ("plane", "background", "block", "ground", "pour"):
            kv = dict(t.split("=") for t in w if "=" in t)
            pos = [t for t in w[1:] if "=" not in t]
            if w[0] == "plane":
                plane = {"layer": pos[0], "gap": float(opts.get("gap", kv["gap"])), "minw": float(kv["minw"])}
                cur = None
                continue
            it = {"kind": w[0], "pts": [], **{k: float(v) for k, v in kv.items()}}
            if w[0] in ("background", "block"):
                it.update(layer=plane["layer"], net=pos[0], name=pos[1], gap=plane["gap"])
                it.setdefault("minw", plane["minw"])
            elif w[0] == "ground":
                it.update(layer=pos[0], net="GND", name=pos[1])
            else:
                it.update(layer=pos[0], net=pos[1], name=pos[2])
            if opts.get("chamfer") == "off":
                it.pop("chamfer", None)
            items.append(it); cur = it
        else:
            cur["pts"] += [tuple(float(v) for v in t.split(",")) for t in w]
    return items


def chamfered(pts, c):
    """Cut every right-angle corner at 45 degrees; the cut is at most 0.3 of either edge next to it."""
    out, n = [], len(pts)
    for i in range(n):
        p, a, q = pts[i - 1], pts[i], pts[(i + 1) % n]
        la, lb = math.dist(p, a), math.dist(a, q)
        ux, uy = (p[0] - a[0]) / la, (p[1] - a[1]) / la
        vx, vy = (q[0] - a[0]) / lb, (q[1] - a[1]) / lb
        if abs(ux * vx + uy * vy) > 1e-6:                  # not a right angle: leave it
            out.append(a); continue
        k = min(c, 0.3 * la, 0.3 * lb)
        out += [(round(a[0] + ux * k, 4), round(a[1] + uy * k, 4)), (round(a[0] + vx * k, 4), round(a[1] + vy * k, 4))]
    return out


def poly(pts):
    ps = pcbnew.SHAPE_POLY_SET(); ps.NewOutline()
    for x, y in pts:
        ps.Append(FromMM(x + 100), FromMM(y + 100))
    return ps


def narrowest(ps, limit):
    """Width of the narrowest part of a shape, found by opening it (shrink then grow back); None if >= limit."""
    area = ps.Area()
    def lost(w):
        t = pcbnew.SHAPE_POLY_SET(ps); t.Deflate(FromMM(w / 2), MITRE, ERR); t.Inflate(FromMM(w / 2), MITRE, ERR)
        return area - t.Area() > 0.02e12
    if not lost(limit):
        return None
    lo, hi = 0.0, limit
    for _ in range(10):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if lost(mid) else (mid, hi)
    return round(hi, 2)


def check_outline(it):
    pts = it["pts"]
    for i in range(len(pts)):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % len(pts)]
        dx, dy = abs(x2 - x1), abs(y2 - y1)
        if dx < 1e-6 and dy < 1e-6:
            errors.append("%s: vertex %d repeated at (%g, %g)" % (it["name"], i + 1, x1, y1))
        elif not (dx < 1e-6 or dy < 1e-6 or abs(dx - dy) < 1e-6):
            errors.append("%s: edge (%g, %g) -> (%g, %g) is at %.1f degrees" % (it["name"], x1, y1, x2, y2, math.degrees(math.atan2(dy, dx))))
    ps = poly(pts)
    if ps.IsSelfIntersecting():
        errors.append("%s: outline crosses itself" % it["name"])
    lim = it.get("minw", 0.3)
    w = narrowest(ps, lim)
    if w is not None:
        errors.append("%s: narrowest part is %.2f mm, below its minimum width %.2f" % (it["name"], w, lim))
    return ps


items = parse(sketch)
board_box = [(-2, -2), (87, -2), (87, 77), (-2, 77)]
for it in items:
    if it["kind"] in ("block", "pour"):
        if "chamfer" in it:
            it["pts"] = chamfered(it["pts"], it["chamfer"])
        it["poly"] = check_outline(it)
    elif it["kind"] == "ground":
        it["pts"] = board_box; it["poly"] = poly(board_box)

for it in items:                                            # block to block distance on a plane layer
    if it["kind"] != "block":
        continue
    for ot in items:
        if ot["kind"] == "block" and ot is not it and ot["layer"] == it["layer"] and ot["net"] != it["net"] and id(ot) > id(it):
            t = pcbnew.SHAPE_POLY_SET(it["poly"]); t.Inflate(FromMM(it["gap"] - 0.001), MITRE, ERR); t.BooleanIntersection(ot["poly"])
            if t.OutlineCount() and t.Area() > 1e6:
                errors.append("%s and %s are closer than the gap %.2f mm" % (it["name"], ot["name"], it["gap"]))

for it in items:                                            # background = board - every block grown by gap
    if it["kind"] != "background":
        continue
    bg = poly(board_box)
    for ot in items:
        if ot["kind"] == "block" and ot["layer"] == it["layer"]:
            t = pcbnew.SHAPE_POLY_SET(ot["poly"]); t.Inflate(FromMM(it["gap"]), MITRE, ERR)
            bg.BooleanSubtract(t)
    it["poly"] = bg
    edge = pcbnew.SHAPE_POLY_SET(); B.GetBoardPolygonOutlines(edge, True)
    inside = pcbnew.SHAPE_POLY_SET(bg); inside.BooleanIntersection(edge)
    w = narrowest(inside, 1.0)
    notes.append("%s: %d outline(s), %d cut-out(s); narrowest part inside the board %s" % (
        it["name"], bg.OutlineCount(), sum(bg.HoleCount(i) for i in range(bg.OutlineCount())),
        "at least 1.0 mm" if w is None else "%.2f mm" % w))

for it in items:                                            # pads under a local pour
    if it["kind"] != "pour":
        continue
    own, foreign = [], []
    for fp in B.GetFootprints():
        for p in fp.Pads():
            if p.IsOnLayer(LID[it["layer"]]) and it["poly"].Contains(p.GetPosition()):
                (own if p.GetNetname() == it["net"] else foreign).append("%s.%s[%s]" % (fp.GetReference(), p.GetNumber(), p.GetNetname()))
    if not own:
        errors.append("%s: no pad of %s under it" % (it["name"], it["net"]))
    if foreign:
        errors.append("%s: pads of other nets under it: %s" % (it["name"], " ".join(foreign)))
    notes.append("%s: covers %s" % (it["name"], " ".join(o.split("[")[0] for o in own)))

for n in notes:
    print("  " + n)
if errors:
    print("SKETCH REJECTED, nothing written:")
    for e in errors:
        print("  " + e)
    sys.exit(1)

net = lambda name: B.FindNet(name)
for it in items:
    assert net(it["net"]) is not None, "no net " + it["net"]
    ps = it["poly"]
    keep = [i for i in range(ps.OutlineCount()) if abs(ps.Outline(i).Area()) > 5e12]        # drop leftovers under 5 mm2
    if len(keep) < ps.OutlineCount():
        print("  %s: dropped %d leftover piece(s) under 5 mm2" % (it["name"], ps.OutlineCount() - len(keep)))
    for i in keep:
        z = pcbnew.ZONE(B); z.SetZoneName(it["name"] if len(keep) == 1 else "%s_%d" % (it["name"], i + 1))
        z.SetLayer(LID[it["layer"]]); z.SetNet(net(it["net"]))
        z.SetAssignedPriority({"background": 0, "ground": 0, "block": 1, "pour": 2}[it["kind"]])
        z.SetLocalClearance(FromMM(it.get("clr", 0.127 if it["kind"] in ("background", "block") else 0.2)))
        z.SetMinThickness(FromMM(it.get("minw", 0.3) if it["kind"] != "pour" else it.get("minw", 0.25)))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)       # the .kicad_dru decides: through-hole thermal, SMD solid
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        o = z.Outline(); o.RemoveAllContours(); o.AddOutline(ps.Outline(i))
        for h in range(ps.HoleCount(i)):
            o.AddHole(ps.Hole(i, h), 0)
        z.SetIsFilled(False)
        B.Add(z)
pcbnew.SaveBoard(dst, B)
print("sketch accepted: %d zones written to %s" % (len(zones(B)), dst))
