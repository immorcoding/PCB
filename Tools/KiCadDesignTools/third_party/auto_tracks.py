"""Pull the autorouter's copper out of a routed board into a JSON file a route.py can replay.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.third_party.auto_tracks <routed.kicad_pcb> <out.json> [--merge]

With --merge, <out.json> is kept and only the nets found in the routed board are replaced
in it (for re-running a few nets with everything else locked).

The route.py hands the autorouter a copy whose hand-routed copper is KiCad-locked, so
every unlocked track and via in the result is the autorouter's. Coordinates are written
in the project's local frame (board mm - 100).
"""
import json, sys
import pcbnew

b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM
L = lambda v: [round(mm(v.x) - 100, 4), round(mm(v.y) - 100, 4)]
out = []
for t in b.GetTracks():
    if t.IsLocked():
        continue
    if t.Type() == pcbnew.PCB_VIA_T:
        out.append({"k": "via", "net": t.GetNetname(), "at": L(t.GetPosition()),
                    "d": round(mm(t.GetWidth(pcbnew.F_Cu)), 4), "drill": round(mm(t.GetDrill()), 4)})
    elif t.Type() == pcbnew.PCB_TRACE_T:
        out.append({"k": "seg", "net": t.GetNetname(), "a": L(t.GetStart()), "b": L(t.GetEnd()),
                    "w": round(mm(t.GetWidth()), 4), "layer": b.GetLayerName(t.GetLayer())})
    else:
        raise SystemExit(f"unexpected track type {t.Type()} on {t.GetNetname()} (arc?)")
nets = sorted({o["net"] for o in out})
if "--merge" in sys.argv:
    out += [o for o in json.load(open(sys.argv[2], encoding="utf-8")) if o["net"] not in nets]
out.sort(key=lambda o: (o["net"], o["k"], json.dumps(o)))
json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), indent=0)
print(len([o for o in out if o["k"] == "seg"]), "segments,", len([o for o in out if o["k"] == "via"]), "vias on",
      len(nets), "nets")
