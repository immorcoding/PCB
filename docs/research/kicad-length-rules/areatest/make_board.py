"""Build `areatest.kicad_pcb`: one rule area named "bga" (x 0..20, y 0..20 mm) and tracks that sit
inside it, outside it, cross its edge, or change width at / after the edge.  Used to see how
A.intersectsArea / A.insideArea / A.enclosedByArea behave in track_width rules.

    D:\\KiCad\\bin\\python.exe -I make_board.py <outdir> <template .kicad_pro>
"""
import json, math, os, shutil, sys
import pcbnew
from pcbnew import VECTOR2I, FromMM

OUT = os.path.abspath(sys.argv[1]); TEMPLATE_PRO = os.path.abspath(sys.argv[2])
mm = FromMM
V = lambda x, y: VECTOR2I(mm(x), mm(y))
b = pcbnew.CreateEmptyBoard()
b.SetCopperLayerCount(4)
nets = {}


def net(n):
    if n not in nets:
        it = pcbnew.NETINFO_ITEM(b, n); b.Add(it); nets[n] = it
    return nets[n]


def seg(n, p0, p1, w, layer=pcbnew.F_Cu):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(V(*p0)); t.SetEnd(V(*p1)); t.SetWidth(mm(w)); t.SetLayer(layer); t.SetNet(net(n)); b.Add(t)


def arc(n, p0, pm, p1, w):
    a = pcbnew.PCB_ARC(b)
    a.SetStart(V(*p0)); a.SetMid(V(*pm)); a.SetEnd(V(*p1)); a.SetWidth(mm(w))
    a.SetLayer(pcbnew.F_Cu); a.SetNet(net(n)); b.Add(a)


# the rule area (a zone with the rule-area flag), all copper layers, nothing forbidden
z = pcbnew.ZONE(b)
z.SetIsRuleArea(True)
z.SetZoneName("bga")
z.SetLayerSet(pcbnew.LSET.AllCuMask())
for f in ("SetDoNotAllowTracks", "SetDoNotAllowVias", "SetDoNotAllowPads", "SetDoNotAllowZoneFills",
          "SetDoNotAllowFootprints"):
    getattr(z, f)(False)
ol = pcbnew.SHAPE_LINE_CHAIN()
for p in [(0, 0), (20, 0), (20, 20), (0, 20)]:
    ol.Append(V(*p))
ol.SetClosed(True)
z.Outline().AddOutline(ol)
b.Add(z)

seg("/a1_in_0.09", (5, 5), (15, 5), 0.09)
seg("/a2_in_0.1016", (5, 7), (15, 7), 0.1016)
seg("/a3_out_0.09", (25, 5), (35, 5), 0.09)
seg("/a4_out_0.1016", (25, 7), (35, 7), 0.1016)
seg("/a5_cross_0.09", (15, 10), (25, 10), 0.09)                    # one segment across x=20
seg("/a6_cross_0.1016", (15, 12), (25, 12), 0.1016)
seg("/a7_split_at_edge", (10, 15), (20, 15), 0.09)                 # 0.09 up to the edge ...
seg("/a7_split_at_edge", (20, 15), (30, 15), 0.1016)               # ... 0.1016 from the edge
seg("/a8_split_1mm_out", (10, 17), (21, 17), 0.09)                 # 0.09 ends 1 mm outside the edge
seg("/a8_split_1mm_out", (21, 17), (30, 17), 0.1016)
seg("/a9_split_0.06_out", (10, 19), (20.06, 19), 0.09)             # ends 0.06 mm outside the edge
seg("/a9_split_0.06_out", (20.06, 19), (30, 19), 0.1016)
arc("/b1_arc_in_0.05", (2, 3), (4, 4.5), (6, 3), 0.05)            # inside the area (y 0..20)
arc("/b2_arc_out_0.05", (25, 25), (27, 27), (29, 25), 0.05)        # outside
arc("/b3_arc_in_0.09", (8, 3), (10, 4.5), (12, 3), 0.09)           # inside
arc("/b5_arc_cross_0.09", (17, 3), (20, 4.5), (23, 3), 0.09)       # crosses the edge x=20
seg("/b4_seg_in_0.05", (2, 1), (12, 1), 0.05)                      # inside, far too thin

os.makedirs(OUT, exist_ok=True)
pcb = os.path.join(OUT, "areatest.kicad_pcb")
pcbnew.SaveBoard(pcb, b)
pro = json.load(open(TEMPLATE_PRO, encoding="utf-8"))
json.dump(pro, open(os.path.join(OUT, "areatest.kicad_pro"), "w", encoding="utf-8"), indent=2)
print("wrote", pcb, "nets", len(nets))
