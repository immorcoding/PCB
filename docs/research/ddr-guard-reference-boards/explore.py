"""explore.py <dump.json>: overview of layers, big parts, DDR-like nets."""
import sys, json, re, collections
d = json.load(open(sys.argv[1]))
print("layers", d["layers"]); print("edge", d["edge"])
big = sorted(d["fps"], key=lambda f: -f["npads"])[:12]
for f in big: print(f["ref"], f["val"], f["npads"], f["side"], [round(x, 1) for x in f["bbox"]])
cnt = collections.Counter((t["l"], t["net"] == "") for t in d["tracks"]); print(cnt)
pat = re.compile(r"DQ|DM|CLK|CK|DQS|DDR", re.I)
nets = collections.Counter(t["net"] for t in d["tracks"] if pat.search(t["net"]))
print(len(nets)); print(sorted(nets)[:400])
w = collections.Counter((t["l"], round(t["w"], 4)) for t in d["tracks"]); print(sorted(w.items(), key=lambda x: -x[1])[:25])
v = collections.Counter((round(x["w"], 3), round(x["d"], 3)) for x in d["vias"]); print(v)
print("zones top:", collections.Counter((z["net"], tuple(z["layers"])) for z in d["zones"]).most_common(12))
print("filled nonempty:", sum(1 for z in d["zones"] for l, f in z["filled"].items() if f and not isinstance(f, str)))
