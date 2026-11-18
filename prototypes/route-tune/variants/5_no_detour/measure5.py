"""PROTOTYPE (issue 21) variant 5_no_detour: extra numbers for README.md, measured from the built boards.
Run from prototypes/route-tune:  D:/KiCad/bin/python.exe variants/5_no_detour/measure5.py
 - per net: how far the route (serpentines taken out) runs against its own direction (west / north), per layer
 - hull with the package outlines shrunk by 0.1 mm, and bus length under the SDRAM body (same code as make_compare.py)
"""
import importlib.util, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "lib"))
sys.path.insert(0, ROOT)
import pcbnew
import board

key = "5_no_detour"
var = board.load_variant(key)
out = {}
bus = var._r["bus"]
for net, pieces in sorted(bus.final.items()):
    west = north = 0.0
    lay = {}
    for pc in pieces:
        if pc[0] == "via":
            continue
        for a, c in zip(pc[1], pc[1][1:]):
            w, n = max(0.0, a[0] - c[0]), max(0.0, a[1] - c[1])
            west += w; north += n
            if w or n:
                lay[pc[0]] = lay.get(pc[0], 0.0) + max(w, n)
    out[net] = {"west": round(west, 3), "north": round(north, 3), "by_layer": {k: round(v, 3) for k, v in lay.items()}}
    print("%-10s west %.3f  north %.3f  %s" % (net, west, north, out[net]["by_layer"]))
print("sum west %.2f  north %.2f" % (sum(v["west"] for v in out.values()), sum(v["north"] for v in out.values())))

spec = importlib.util.spec_from_file_location("mc", os.path.join(ROOT, "make_compare.py"))
mc = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mc)
    extra = {}
    for k in ("5_no_detour", "4_combined", "3_under_sdram", "1_baseline"):
        B = pcbnew.LoadBoard(os.path.join(ROOT, "out", k, "routetune.kicad_pcb"))
        extra[k] = {"under_body": mc.under_body(B), "hull_shrunk_0.1": mc.hull_shrunk(B)}
        print(k, extra[k])
except Exception as e:                                   # make_compare.py is not ours: report, do not patch
    print("make_compare helpers not usable:", e)
    extra = None
json.dump({"backwards": out, "extra": extra}, open(os.path.join(ROOT, "out", key, "extra5.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
