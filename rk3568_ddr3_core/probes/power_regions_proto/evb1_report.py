"""PROTOTYPE (issue 52): summarise evb1_power.py's JSON per rail.   python evb1_report.py <evb1_power.json>"""
import collections, json, sys
import model as M

M.load_rails()
r = json.load(open(sys.argv[1], encoding="utf-8"))
print(r["soc"], r["pads"], "pads; layers", r["layers"], "; SoC turned", r["soc_rot"])
bn = r["ballnet"]
ours = {p["ball"]: M.RAIL_OF.get(M.base(p["name"])) for p in M.PINS}
kind = {b: k for b, _, _, k, _ in M.soc_balls()}
m = collections.defaultdict(collections.Counter)
for b, n in bn.items():
    if ours.get(b):
        m[ours[b]][n] += 1
gnd = collections.Counter(bn[b] for b in bn if kind.get(b) == "gnd").most_common(1)[0][0]
gv = r["vias"][gnd]
print("GND net", gnd, ": balls", sum(1 for b in bn if bn[b] == gnd), ", vias within the outline + 1 mm", len(gv))
print("via (drill, pad) all nets:", collections.Counter((v[2], v[3]) for vs in r["vias"].values() for v in vs).most_common(6))
for h in (2.0, 3.3, 4.6, 6.0):
    gb = sum(1 for b, x, y, k, _ in M.soc_balls() if k == "gnd" and abs(x) < h and abs(y) < h)
    pb = sum(1 for b, x, y, k, _ in M.soc_balls() if k == "pwr" and abs(x) < h and abs(y) < h)
    pv = sum(1 for n, vs in r["vias"].items() for v in vs if n != gnd and abs(v[0]) < h and abs(v[1]) < h)
    print(f"  within +-{h} mm: ground balls {gb}, EVB1 ground vias {sum(1 for v in gv if abs(v[0]) < h and abs(v[1]) < h)}; supply balls {pb}, all other vias {pv}")
zs = collections.defaultdict(list)
for z in r["zones"]:
    zs[z["net"]].append(z)
for rail, c in sorted(m.items(), key=lambda kv: -sum(kv[1].values())):
    for n, k in c.items():
        vs = r["vias"].get(n, [])
        tr = r["tracks_in_soc"].get(n, {})
        print(f"{rail:15s} EVB1 net {n:24s} balls {k:2d} vias {len(vs):2d} {collections.Counter((v[2], v[3]) for v in vs).most_common(2)} tracks mm {tr}")
        for z in sorted(zs.get(n, []), key=lambda z: -z["outline_area"])[:6]:
            print("      zone", z["layers"], "area", z["outline_area"], "own balls inside", z["own_balls_inside"],
                  "box", [round(t, 1) for t in z["box"]], "clr", z.get("clearance"), "minw", z.get("min_width"))
print("zones of GND:", [(z["layers"], z["outline_area"]) for z in sorted(zs.get(gnd, []), key=lambda z: -z["outline_area"])[:8]])
caps = r["two_pad_parts"]
print("two-pad parts within outline + 2 mm:", collections.Counter(c["side"] for c in caps), "pad pitch", collections.Counter(c["pad_pitch"] for c in caps).most_common(5))
