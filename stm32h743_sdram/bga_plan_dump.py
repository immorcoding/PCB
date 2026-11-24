"""bga_plan dump: the one part of the planner that needs pcbnew (through busroute's Board snapshot).

Writes geo.json: every pad (ball) of the two BGAs, every other pad, via, track, zone outline, rule area and
keep-out of the board, the stack heights and the rule values of the profile. Coordinates are local mm
(board-file mm - 100). The planner and the checker read only this file.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
ORIGIN = (100.0, 100.0)
MCU, SDRAM = "U201", "U301"


def r4(v):
    return round(float(v), 4)


def dump(board_path, out_path):
    from busroute.board import Board
    from busroute.profile import Profile
    b = Board(board_path, ORIGIN)
    pr = Profile.from_project(board_path)
    pads = []
    for p in b.all_pads():
        pads.append({"ref": p.ref, "num": p.num, "net": p.net, "pos": [r4(p.pos[0]), r4(p.pos[1])],
                     "layers": sorted(p.layers) if p.layers else None, "smd": bool(p.smd), "hole": r4(p.hole),
                     "shape": p.shape, "r": r4(p.r), "box": [r4(v) for v in p.box],
                     "poly": [[r4(x), r4(y)] for x, y in p.poly] if p.poly else None})
    geo = {"board": os.path.abspath(board_path).replace("\\", "/"), "origin": list(ORIGIN),
           "fp": {r: {"pos": [r4(f["pos"][0]), r4(f["pos"][1])], "rot": f["rot"], "lib": f["lib"]} for r, f in b.fp.items()},
           "pads": pads,
           "vias": [[n, [r4(p[0]), r4(p[1])], r4(d), r4(h)] for n, p, d, h in b.vias],
           "tracks": [[n, l, [r4(a[0]), r4(a[1])], [r4(c[0]), r4(c[1])], r4(w)] for n, l, a, c, w, _arc in b.tracks],
           "zones": [{"net": z["net"], "name": z["name"], "layers": z["layers"], "poly": [[r4(x), r4(y)] for x, y in z["poly"]]} for z in b.zones],
           "areas": {n: {"rect": [r4(v) for v in a["rect"]], "layers": a["layers"]} for n, a in b.areas.items()},
           "keepouts": [{"name": k["name"], "layers": k["layers"], "tracks": bool(k["tracks"]), "vias": bool(k["vias"]),
                         "poly": [[r4(x), r4(y)] for x, y in k["poly"]]} for k in b.keepouts],
           "edges": [[[r4(a[0]), r4(a[1])], [r4(c[0]), r4(c[1])]] for a, c in b.edges],
           "stack": b.stack, "layers": b.layers,
           "rules": {k: getattr(pr, k) for k in sorted(vars(pr)) if isinstance(getattr(pr, k), (int, float, str, list, tuple, dict))},
           "classes": {}}
    nets = sorted(n for n in b.nets if n)
    geo["classes"] = {n: pr.net_class(n) for n in nets}
    geo["width"] = {n: pr.width(n) for n in nets}
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    json.dump(geo, open(out_path, "w", encoding="utf-8"), indent=0, default=str)
    print("wrote %s: %d pads, %d vias, %d tracks, %d zones" % (out_path, len(pads), len(geo["vias"]), len(geo["tracks"]), len(geo["zones"])))


if __name__ == "__main__":
    a = sys.argv[1:]
    board = a[0] if a and not a[0].startswith("--") else os.path.join(HERE, "stm32h743_sdram.kicad_pcb")
    out = a[a.index("--out") + 1] if "--out" in a else os.path.join(HERE, "out", "plan", "geo.json")
    dump(board, out)
