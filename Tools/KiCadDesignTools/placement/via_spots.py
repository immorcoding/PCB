"""Find legal spots for ground vias: near given points, or on a stitching grid.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.placement.via_spots <board> near X,Y[,R] ... --net NET    (local mm = board mm - 100)
    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.placement.via_spots <board> grid PITCH --net NET

--net: the net the vias belong to, whose pours `grid` needs (the ground net: board.toml [power] ground; the two-layer
boards without a board.toml name it here). A spot is legal when a 0.6 mm via there keeps MARGIN to every track, via
and pad of another net on both copper layers, to board edges and rule areas, and does not
sit on any pad. For `grid`, both pours of --net must also be present at the spot.
Prints coordinates ready to paste into a route.py GND_VIAS list.
"""
import math, sys
import pcbnew

import os
MARGIN, R = float(os.environ.get("VIA_MARGIN", "0.2")), 0.3
if "--net" not in sys.argv[:-1]:
    sys.exit(__doc__)
NET = sys.argv[sys.argv.index("--net") + 1]     # the net the via belongs to
del sys.argv[sys.argv.index("--net"):sys.argv.index("--net") + 2]
b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
L = lambda v: (mm(v.x) - 100, mm(v.y) - 100)
segs, vias, pads = [], [], []
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        vias.append((L(t.GetPosition()), t.GetNetname()))
    else:
        segs.append((L(t.GetStart()), L(t.GetEnd()), mm(t.GetWidth()) / 2, t.GetNetname()))
for fp in b.GetFootprints():
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        pads.append((mm(bb.GetLeft()) - 100, mm(bb.GetTop()) - 100, mm(bb.GetRight()) - 100, mm(bb.GetBottom()) - 100, p.GetNetname()))
areas = [z for z in b.Zones() if z.GetIsRuleArea()]
pours = {z.GetLayer(): z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname() == NET}
edge = b.GetBoardEdgesBoundingBox()
ex0, ey0, ex1, ey1 = mm(edge.GetLeft()) - 100, mm(edge.GetTop()) - 100, mm(edge.GetRight()) - 100, mm(edge.GetBottom()) - 100


def dseg(p, a, c):
    vx, vy = c[0] - a[0], c[1] - a[1]
    k = max(0, min(1, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / (vx * vx + vy * vy or 1)))
    return math.hypot(p[0] - a[0] - k * vx, p[1] - a[1] - k * vy)


def ok(p, need_pour=False):
    if not (ex0 + 0.7 < p[0] < ex1 - 0.7 and ey0 + 0.7 < p[1] < ey1 - 0.7):
        return False
    for a, c, hw, n in segs:
        if n != NET and dseg(p, a, c) < R + hw + MARGIN:
            return False
    for q, n in vias:
        if math.dist(p, q) < (2 * R + MARGIN if n != NET else 1.0):
            return False
    for x0, y0, x1, y1, n in pads:
        dx, dy = max(x0 - p[0], 0, p[0] - x1), max(y0 - p[1], 0, p[1] - y1)
        if math.hypot(dx, dy) < R + (MARGIN if n != NET else 0.05):
            return False
    pt = pcbnew.VECTOR2I(pcbnew.FromMM(p[0] + 100), pcbnew.FromMM(p[1] + 100))
    if any(z.Outline().Contains(pt) for z in areas):
        return False
    if need_pour:
        for layer, z in pours.items():
            if not z.GetFilledPolysList(layer).Contains(pt, -1, pcbnew.FromMM(-R - 0.1)):
                return False
    return True


if sys.argv[2] == "near":
    for arg in sys.argv[3:]:
        v = [float(x) for x in arg.split(",")]
        x, y, rad = v[0], v[1], (v[2] if len(v) > 2 else 1.5)
        c = [(round(x + i * 0.05, 2), round(y + j * 0.05, 2)) for i in range(-40, 41) for j in range(-40, 41)
             if math.hypot(i, j) * 0.05 <= rad]
        c = sorted((q for q in c if ok(q)), key=lambda q: math.dist(q, (x, y)))
        print(arg, "->", c[:4] or "no legal spot")
else:
    pitch = float(sys.argv[3]); out = []
    y = ey0 + 1.5
    while y < ey1 - 1.0:
        x = ex0 + 1.5
        while x < ex1 - 1.0:
            p = (round(x, 2), round(y, 2))
            if ok(p, True) and all(math.dist(p, q) > pitch * 0.6 for q in out):
                out.append(p); vias.append((p, NET))
            x += pitch / 4
        y += pitch / 4
    print(out)
