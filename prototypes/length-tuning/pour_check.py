"""PROTOTYPE (issue 15): is the ground pour on L2 / L5 really filled, and at the pour's own clearance?

    D:\\KiCad\\bin\\python.exe pour_check.py <variant dir>

The copper-regions prototype (issue 16) found that a clearance rule written with intersectsArea()
alone makes every pour that overlaps a rule area fill at 0.09 mm. The canary cannot see that, so one
real distance is measured here: from the pad of each signal via to the nearest pour copper on L2 and
L5 (the pour is set to 0.2 mm). Reads the fill that kicad-cli saved (--refill-zones --save-board).
"""
import math, os, sys
import pcbnew

mm, FromMM = pcbnew.ToMM, pcbnew.FromMM
B = pcbnew.LoadBoard(os.path.join(sys.argv[1], "lentune.kicad_pcb"))
for z in B.Zones():
    if z.GetIsRuleArea():
        continue
    lid = z.GetLayer()
    fill = z.GetFilledPolysList(lid)
    gaps = []
    for t in B.GetTracks():
        if t.Type() != pcbnew.PCB_VIA_T or t.GetNetname() == "GND":
            continue
        c, r = t.GetPosition(), mm(t.GetWidth(lid)) / 2
        d = r
        while d < r + 1.0:                                   # walk outwards in 0.5 um steps on 16 spokes (the review measured 0.2005 exactly)
            d += 0.0005
            if any(fill.Contains(pcbnew.VECTOR2I(c.x + FromMM(d * math.cos(a * math.pi / 8)), c.y + FromMM(d * math.sin(a * math.pi / 8))))
                   for a in range(16)):
                break
        gaps.append(d - r)
    print("%s %s: filled area %.1f mm2, %d outline(s); signal via pad to pour: min %.4f, max %.4f mm (pour clearance 0.200)" % (
        z.GetZoneName(), B.GetLayerName(lid), fill.Area() / 1e12, fill.OutlineCount(), min(gaps), max(gaps)))
