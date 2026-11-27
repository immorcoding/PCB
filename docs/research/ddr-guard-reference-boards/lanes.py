"""lanes.py <dump.json> <net regex for data>: per-net layer lengths, endpoints, GND net names, SoC/DRAM pad positions."""
import sys, json, re, math, collections
d = json.load(open(sys.argv[1]))
rx = re.compile(sys.argv[2])
L = lambda t: math.hypot(t["a"][0] - t["b"][0], t["a"][1] - t["b"][1])
gndn = collections.Counter(t["net"] for t in d["tracks"] if re.search(r"GND|VSS", t["net"], re.I))
print("GND-like track nets:", gndn.most_common(6))
print("GND via counts:", sum(1 for v in d["vias"] if re.search(r"GND|VSS", v["net"], re.I)), "of", len(d["vias"]))
print("unnamed track nets:", sum(1 for t in d["tracks"] if t["net"] == ""))
nets = sorted({t["net"] for t in d["tracks"] if rx.search(t["net"])})
for n in nets:
    bl = collections.defaultdict(float)
    for t in d["tracks"]:
        if t["net"] == n: bl[t["l"]] += L(t)
    pads = [(p["ref"], p["n"], round(p["p"][0], 2), round(p["p"][1], 2)) for p in d["pads"] if p["net"] == n and not p["ref"].startswith(("R", "C"))]
    vs = sum(1 for v in d["vias"] if v["net"] == n)
    ws = sorted({round(t["w"], 3) for t in d["tracks"] if t["net"] == n})
    print(n, {k: round(v, 1) for k, v in bl.items()}, "vias", vs, "w", ws, pads)
