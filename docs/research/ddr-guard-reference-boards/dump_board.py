"""Run with KiCad python via heavy.run: dump_board.py <in.brd> <out.json>.
Loads an Allegro .brd in memory only and dumps copper facts (mm) to JSON."""
import sys, json, pcbnew

src, dst = sys.argv[1], sys.argv[2]
b = pcbnew.PCB_IO_MGR.Load(pcbnew.PCB_IO_MGR.ALLEGRO, src)
mm = lambda v: v / 1e6
def pt(p): return [mm(p.x), mm(p.y)]

out = {"layers": {}, "tracks": [], "arcs": [], "vias": [], "zones": [], "pads": [], "fps": [], "shapes": []}
for i in b.GetEnabledLayers().Seq():
    out["layers"][int(i)] = b.GetLayerName(i)
for t in b.GetTracks():
    ty = t.GetClass()
    net = t.GetNetname()
    if ty == "PCB_VIA":
        try:
            w = mm(t.GetWidth(t.TopLayer()))
        except Exception:
            w = mm(t.GetWidth())
        out["vias"].append({"p": pt(t.GetPosition()), "w": w, "d": mm(t.GetDrillValue()), "net": net,
                            "l0": b.GetLayerName(t.TopLayer()), "l1": b.GetLayerName(t.BottomLayer())})
    elif ty == "PCB_ARC":
        out["arcs"].append({"a": pt(t.GetStart()), "b": pt(t.GetEnd()), "m": pt(t.GetMid()), "w": mm(t.GetWidth()),
                            "l": b.GetLayerName(t.GetLayer()), "net": net})
    else:
        out["tracks"].append({"a": pt(t.GetStart()), "b": pt(t.GetEnd()), "w": mm(t.GetWidth()),
                              "l": b.GetLayerName(t.GetLayer()), "net": net})

def polys(sps):
    r = []
    for i in range(sps.OutlineCount()):
        o = sps.Outline(i)
        r.append({"o": [pt(o.CPoint(k)) for k in range(o.PointCount())],
                  "h": [[pt(sps.Hole(i, h).CPoint(k)) for k in range(sps.Hole(i, h).PointCount())]
                        for h in range(sps.HoleCount(i))]})
    return r

for z in b.Zones():
    zd = {"net": z.GetNetname(), "layers": [b.GetLayerName(l) for l in z.GetLayerSet().Seq()],
          "name": z.GetZoneName(), "outline": polys(z.Outline()), "filled": {}}
    for l in z.GetLayerSet().Seq():
        try:
            f = z.GetFilledPolysList(l)
            zd["filled"][b.GetLayerName(l)] = polys(f) if f.OutlineCount() else []
        except Exception as e:
            zd["filled"][b.GetLayerName(l)] = "err %s" % e
    out["zones"].append(zd)
for d in b.GetDrawings():
    try:
        l = d.GetLayer()
        if pcbnew.IsCopperLayer(l):
            bb = d.GetBoundingBox()
            out["shapes"].append({"cls": d.GetClass(), "l": b.GetLayerName(l),
                                  "net": d.GetNetname() if hasattr(d, "GetNetname") else "",
                                  "bbox": [mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetWidth()), mm(bb.GetHeight())]})
    except Exception:
        pass
for f in b.GetFootprints():
    bb = f.GetBoundingBox(False)
    out["fps"].append({"ref": f.GetReference(), "val": f.GetValue(), "p": pt(f.GetPosition()),
                       "side": b.GetLayerName(f.GetLayer()),
                       "bbox": [mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetWidth()), mm(bb.GetHeight())],
                       "npads": len(f.Pads())})
    for p in f.Pads():
        s = p.GetSize()
        out["pads"].append({"ref": f.GetReference(), "n": p.GetNumber(), "p": pt(p.GetPosition()),
                            "net": p.GetNetname(), "s": [mm(s.x), mm(s.y)],
                            "smd": p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD, "side": b.GetLayerName(f.GetLayer())})
bb = b.GetBoardEdgesBoundingBox()
out["edge"] = [mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetWidth()), mm(bb.GetHeight())]
json.dump(out, open(dst, "w"))
print("tracks", len(out["tracks"]), "arcs", len(out["arcs"]), "vias", len(out["vias"]), "zones", len(out["zones"]),
      "pads", len(out["pads"]), "shapes", len(out["shapes"]))
