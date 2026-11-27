"""PROTOTYPE (issue 37, throwaway): print where the DDR3 differential pairs sit on the RK3568 ball field."""
import json, re
from pathlib import Path

LIB = Path(__file__).resolve().parents[2] / "lib"
PINS = json.loads((LIB / "rk3568_pins.json").read_text(encoding="utf-8"))
PKG = json.loads((LIB / "rk3568_pin_length_mm.json").read_text(encoding="utf-8"))
FP = (LIB / "rk3568_ddr3_core.pretty" / "BGA-636_19x19mm_Layout28x28_P0.65mm.kicad_mod").read_text(encoding="utf-8")
XY = {m.group(1): (float(m.group(2)), float(m.group(3)))
      for m in re.finditer(r'\(pad "([A-Z]+\d+)" smd \w+\s*\(at ([-\d.]+) ([-\d.]+)', FP)}
name = {p["ball"]: p["name"] for p in PINS}


def short(n):
    for part in n.split("/"):
        if part.startswith("DDR3_"):
            return part[5:]
    return n[:9]


P = 0.65
key = lambda x, y: (round(x / P * 2), round(y / P * 2))
grid = {key(*xy): b for b, xy in XY.items()}
xs = sorted({k[0] for k in grid}); ys = sorted({k[1] for k in grid})
print("grid half-pitch index x", xs[0], xs[-1], "y", ys[0], ys[-1], "A1 at", XY["A1"], "balls", len(XY))
fn = {short(p["name"]): p["ball"] for p in PINS if p["part"] == "F"}
for a, b in [("DQS0P", "DQS0N"), ("DQS1P", "DQS1N"), ("DQS2P", "DQS2N"), ("DQS3P", "DQS3N"), ("CLKP", "CLKN")]:
    ba, bb = fn[a], fn[b]
    print(f"\n{a} {ba} {XY[ba]} pkg {PKG[ba]} | {b} {bb} {XY[bb]} pkg {PKG[bb]} | P-N {PKG[ba] - PKG[bb]:+.4f} mm")
    ka, kb = key(*XY[ba]), key(*XY[bb])
    i0, j0 = min(ka[0], kb[0]), min(ka[1], kb[1])
    for j in range(j0 - 6, j0 + 9, 2):
        row = []
        for i in range(i0 - 6, i0 + 9, 2):
            k = grid.get((i, j))
            row.append(f"{k}:{short(name.get(k, '?'))}" if k else ".")
        print("  " + " | ".join(f"{r:13s}" for r in row))
