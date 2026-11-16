"""PROTOTYPE (issue 16): read the zones of a board back into sketch text.

    D:\\KiCad\\bin\\python.exe zones2sketch.py <board> > sketch_readback.txt

For the other way of writing a sketch: draw or drag the zone outlines in KiCad, save, then read them
back so the sketch file stays the source (PROC-13). Whole-layer ground and the plane background are
written as `ground` / `background` lines; everything else comes back with its vertices as drawn
(corner cuts are already in the vertices, so no chamfer= is written).
"""
import sys
import pcbnew
from culib import *

B = pcbnew.LoadBoard(sys.argv[1])
edge = pcbnew.SHAPE_POLY_SET(); B.GetBoardPolygonOutlines(edge, True)
board_area = edge.Area()
by_layer = {}
for z in zones(B):
    by_layer.setdefault(z.GetLayer(), []).append(z)

print("# read back from %s" % sys.argv[1])
for lid, _name, _num in LAYERS:
    zs = by_layer.get(lid, [])
    whole = [z for z in zs if z.Outline().Area() > 0.8 * board_area]          # covers the board: ground or background
    rest = [z for z in zs if z not in whole]
    inner = lid not in (pcbnew.F_Cu, pcbnew.B_Cu)
    if inner and rest:
        gap = 0.5
        print("\nplane %s gap=%.2f minw=%.2f" % (LNAME[lid], gap, mm(rest[0].GetMinThickness())))
        for z in whole:
            print("background %s %s" % (z.GetNetname(), z.GetZoneName()))
    else:
        for z in whole:
            print("ground %s %s minw=%.2f clr=%.3f" % (LNAME[lid], z.GetZoneName(), mm(z.GetMinThickness()), mm(z.GetLocalClearance() or 0)))
    for z in rest:
        if inner:
            print("\nblock %s %s" % (z.GetNetname(), z.GetZoneName()))
        else:
            print("\npour %s %s %s minw=%.2f clr=%.3f" % (LNAME[lid], z.GetNetname(), z.GetZoneName(), mm(z.GetMinThickness()), mm(z.GetLocalClearance() or 0)))
        pts = chain_pts(z.Outline().Outline(0))
        for i in range(0, len(pts), 6):
            print("  " + "   ".join("%g,%g" % (round(x, 3), round(y, 3)) for x, y in pts[i:i + 6]))
