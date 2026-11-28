"""PROTOTYPE (issue 53, throwaway): ring and side of every DDR3 data ball on the RK3568, per byte lane."""
import json, re
from pathlib import Path

LIB = Path(__file__).resolve().parents[2] / "lib"
PINS = json.loads((LIB / "rk3568_pins.json").read_text(encoding="utf-8"))
FP = (LIB / "rk3568_ddr3_core.pretty" / "BGA-636_19x19mm_Layout28x28_P0.65mm.kicad_mod").read_text(encoding="utf-8")
XY = {m.group(1): (float(m.group(2)), float(m.group(3)))
      for m in re.finditer(r'\(pad "([A-Z]+\d+)" smd \w+\s*\(at ([-\d.]+) ([-\d.]+)', FP)}
P = 0.65
H = 13.5 * P


def short(n):
    for part in n.split("/"):
        if part.startswith("DDR3_"):
            return part[5:]
    return None


def ring(x, y):
    return round(min(H - abs(x), H - abs(y)) / P) + 1


def side(x, y):
    d = {"W": H + x, "E": H - x, "N": H + y, "S": H - y}
    return min(d, key=d.get)


def lanes():
    out = {}
    for p in PINS:
        s = short(p["name"])
        if not s:
            continue
        m = re.match(r"DQ(\d+)$", s)
        if m:
            b = int(m.group(1)) // 8
        else:
            m = re.match(r"(DQS|DM)(\d)", s)
            if not m:
                continue
            b = int(m.group(2))
        x, y = XY[p["ball"]]
        out.setdefault(b, []).append((ring(x, y), s, p["ball"], x, y, side(x, y)))
    return out


if __name__ == "__main__":
    L = lanes()
    for b in sorted(L):
        rows = sorted(L[b])
        cnt = {}
        for r in rows:
            cnt[r[0]] = cnt.get(r[0], 0) + 1
        print(f"byte {b}: rings {cnt} sides {sorted({r[5] for r in rows})}")
        for r in rows:
            print(f"   ring {r[0]} {r[1]:6s} {r[2]:5s} ({r[3]:+.3f}, {r[4]:+.3f}) {r[5]}")
