"""PROTOTYPE (issue 59, throwaway): where the 27 T nets sit, and the free corner."""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "placement_proto"))
import draw as P  # noqa: E402

v = [x for x in P.VARIANTS if x.key == "l-wide"][0]
print("chips", v.chips)


def ring(xy):
    return round((P.SOC_FIELD - max(abs(xy[0]), abs(xy[1]))) / 0.65) + 1


rows = []
for fn in P.AC:
    b = P.SOC[fn]
    s = v.soc[b]
    a = v.chip("A", P.AC[fn])
    c = v.chip("B", P.AC[fn])
    ball = [x[0] for x in P.DDR_ALL if x[1] == P.AC[fn]][0]
    rows.append((fn, b, s, ring(s), ball, a, c))
for fn, b, s, rg, ball, a, c in sorted(rows, key=lambda r: math.atan2(r[2][1] + 8.775, r[2][0] + 8.775)):
    print(f"{fn:7s} soc {b:5s} ({s[0]:7.2f},{s[1]:7.2f}) ring {rg}  ddr {ball:3s} A ({a[0]:7.2f},{a[1]:7.2f}) "
          f"B ({c[0]:7.2f},{c[1]:7.2f}) pkg {P.PKG.get(b, 0):.2f}")
print(len(rows), "nets; ring histogram", {k: sum(1 for r in rows if r[3] == k) for k in sorted({r[3] for r in rows})})
for c in "AB":
    print(c, "body", [tuple(round(q, 2) for q in p) for p in v.polys()[c]])
A = np.array([r[5] for r in rows])
B = np.array([r[6] for r in rows])
for ang in (90, -90):
    t = math.radians(ang)
    R = np.array([[math.cos(t), -math.sin(t)], [math.sin(t), math.cos(t)]])
    cs = np.linalg.solve(np.eye(2) - R, (B - A @ R.T).T).T
    print(ang, "rotation centre spread", cs.std(axis=0).round(3), "mean", cs.mean(axis=0).round(3))
