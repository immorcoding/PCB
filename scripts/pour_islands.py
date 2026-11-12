"""List the pieces of an outer-layer pour that have no via or through-hole pad of their net.

    D:\\KiCad\\bin\\python.exe scripts\\pour_islands.py <board> [zone name ...]

A piece like that hangs on surface-mount pads only, so those pads are not connected to the
rest of the net (DRC reports it as zone-to-zone "unconnected"). For each one this prints
its bounding box and the pads in it, in local coordinates (board mm - 100), so a via can be
added next to one of them.
"""
import sys
import pcbnew

b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM
names = set(sys.argv[2:])
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
L = lambda v: (round(mm(v.x) - 100, 2), round(mm(v.y) - 100, 2))
for z in b.Zones():
    if z.GetIsRuleArea() or (names and z.GetZoneName() not in names):
        continue
    layer, net = z.GetLayer(), z.GetNetname()
    if layer not in (pcbnew.F_Cu, pcbnew.B_Cu):
        continue
    anchors = [t.GetPosition() for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == net]
    smd = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() != net:
                continue
            if p.HasHole():
                anchors.append(p.GetPosition())
            elif p.IsOnLayer(layer):
                smd.append((f"{fp.GetReference()}.{p.GetNumber()}", p.GetPosition()))
    polys = z.GetFilledPolysList(layer)
    n = 0
    for i in range(polys.OutlineCount()):
        one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(polys.Outline(i))
        for h in range(polys.HoleCount(i)):
            one.AddHole(polys.Hole(i, h))
        if any(one.Contains(pcbnew.VECTOR2I(a.x, a.y)) for a in anchors):
            continue
        bb = one.BBox()
        pads = [f"{name}{L(pos)}" for name, pos in smd if one.Collide(pcbnew.VECTOR2I(pos.x, pos.y), pcbnew.FromMM(0.4))]
        n += 1
        print(f"{z.GetZoneName()} piece {i}: x[{mm(bb.GetLeft())-100:.2f},{mm(bb.GetRight())-100:.2f}] "
              f"y[{mm(bb.GetTop())-100:.2f},{mm(bb.GetBottom())-100:.2f}] area {one.Area()/1e12:.2f} mm2  pads: {' '.join(pads) or '-'}")
    print(f"{z.GetZoneName()}: {polys.OutlineCount()} pieces, {n} without a via or through-hole pad")
