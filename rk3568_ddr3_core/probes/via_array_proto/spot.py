"""PROTOTYPE (issue 53, throwaway): recompute one EVB1 number from the dumped data as a spot check."""
import json
import math
import os

e = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "evb1_via_array.json"), encoding="utf-8"))
a = [x for x in e["vias"] if x["kind"] == "sig" and "DQSU" in x["net"]]
print([(x["net"], x["u"], x["v"], x["pad"], x["drill"]) for x in a])
print("pair via centre distance", [round(math.dist((p["u"], p["v"]), (q["u"], q["v"])), 3) for i, p in enumerate(a) for q in a[i + 1:]])
print("vias by kind", {k: sum(1 for x in e["vias"] if x["kind"] == k) for k in ("sig", "gnd", "other")}, "tracks", len(e["tracks"]))
