"""parts.py <dump.json> <ref> ...: pad bbox (ball field), pad pitch and fp bbox of the given refs."""
import sys, json
import numpy as np
d = json.load(open(sys.argv[1]))
for ref in sys.argv[2:]:
    P = np.array([p["p"] for p in d["pads"] if p["ref"] == ref]); f = [x for x in d["fps"] if x["ref"] == ref][0]
    xs = np.unique(np.round(P[:, 0], 3)); ys = np.unique(np.round(P[:, 1], 3))
    s = [p["s"] for p in d["pads"] if p["ref"] == ref][0]
    print(ref, f["val"], f["side"], "pads", len(P), "padbbox x %.2f..%.2f y %.2f..%.2f" % (P[:, 0].min(), P[:, 0].max(), P[:, 1].min(), P[:, 1].max()),
          "padsize", s, "fp bbox", [round(v, 2) for v in f["bbox"]], "uniq x", len(xs), "uniq y", len(ys), "minstep x %.3f y %.3f" % (np.diff(xs).min() if len(xs) > 1 else 0, np.diff(ys).min() if len(ys) > 1 else 0))
