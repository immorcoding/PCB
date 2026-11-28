"""PROTOTYPE (issue 59, throwaway): dump EVB1's real tracks, vias and pads around the T-branch band, for drawing.

    python rk3568_ddr3_core/probes/survey/run_heavy.py 900 <log> D:\\KiCad\\bin\\python.exe evb1_tracks.py <board.brd> <out.json>

Board coordinates (KiCad import, mm, y down). In memory only: no save, no DRC, no fill.
"""
import json
import sys

import pcbnew

brd, out = sys.argv[1], sys.argv[2]
b = pcbnew.PCB_IO_MGR.Load(pcbnew.PCB_IO_MGR.ALLEGRO, brd)
MM = 1e-6
WIN = (125.5, -84.0, 144.5, -72.0)


def inwin(x, y, g=0.0):
    return WIN[0] - g <= x <= WIN[2] + g and WIN[1] - g <= y <= WIN[3] + g


tracks, vias, pads = [], [], []
for t in b.GetTracks():
    net = str(t.GetNetname())
    if t.Type() == pcbnew.PCB_VIA_T:
        p = t.GetPosition()
        if inwin(p.x * MM, p.y * MM):
            vias.append({"net": net, "x": round(p.x * MM, 4), "y": round(p.y * MM, 4),
                         "pad": round(t.GetWidth(pcbnew.F_Cu) * MM, 3), "drill": round(t.GetDrillValue() * MM, 3)})
        continue
    s, e = t.GetStart(), t.GetEnd()
    if not (inwin(s.x * MM, s.y * MM, 1.0) or inwin(e.x * MM, e.y * MM, 1.0)):
        continue
    d = {"net": net, "layer": str(b.GetLayerName(t.GetLayer())), "w": round(t.GetWidth() * MM, 4),
         "a": [round(s.x * MM, 4), round(s.y * MM, 4)], "b": [round(e.x * MM, 4), round(e.y * MM, 4)]}
    if t.Type() == pcbnew.PCB_ARC_T:
        m = t.GetMid()
        d["mid"] = [round(m.x * MM, 4), round(m.y * MM, 4)]
    tracks.append(d)
for f in b.GetFootprints():
    for p in f.Pads():
        q = p.GetPosition()
        if inwin(q.x * MM, q.y * MM):
            sz = p.GetSize(pcbnew.F_Cu if f.GetLayer() == pcbnew.F_Cu else pcbnew.B_Cu)
            pads.append({"ref": str(f.GetReference()), "num": str(p.GetNumber()), "net": str(p.GetNetname()), "x": round(q.x * MM, 4), "y": round(q.y * MM, 4),
                         "sx": round(sz.x * MM, 3), "sy": round(sz.y * MM, 3), "side": "TOP" if f.GetLayer() == pcbnew.F_Cu else "BOTTOM",
                         "rot": round(p.GetOrientationDegrees(), 1)})
json.dump({"window": WIN, "tracks": tracks, "vias": vias, "pads": pads}, open(out, "w", encoding="utf-8"))
print(len(tracks), "tracks", len(vias), "vias", len(pads), "pads")
