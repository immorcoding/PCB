"""PROTOTYPE (throwaway, issue 52): facts the power-copper sketches are drawn against.

Frame: mm, origin at the SoC centre, x to the right (east), y down (south); ball A1 is at -x -y (north-west).
Everything here is read from files, nothing is typed in by hand except the DDR3 ball map (JEDEC, checked
against the Micron data sheet in issue 34) and RAIL_OF (the reference schematic's rail of each supply pin).
"""
import json, math, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LIB = ROOT / "lib"
PINS = json.loads((LIB / "rk3568_pins.json").read_text(encoding="utf-8"))
FP = (LIB / "rk3568_ddr3_core.pretty" / "BGA-636_19x19mm_Layout28x28_P0.65mm.kicad_mod").read_text(encoding="utf-8")
SOC_XY = {m.group(1): (float(m.group(2)), float(m.group(3)))
          for m in re.finditer(r'\(pad "([A-Z]+\d+)" smd \w+\s*\(at ([-\d.]+) ([-\d.]+)', FP)}
FAN = json.loads((ROOT / "probes" / "survey" / "out" / "fan3" / "fan.json").read_text(encoding="utf-8"))["U1"]
FAN_ORIGIN = (20.0, 20.0)          # the survey board has the SoC centre there

PITCH = 0.65
SOC_HALF, SOC_FIELD = 9.5, 8.775
MARGIN = 1.0                       # rule area = outline + 1 mm (issue 48)
GAP = 7.5                          # ball field to ball field (issue 34)
DDR_BODY = (9.0, 14.0)             # keep-out, largest candidate body
BOARD = (-26.0, -26.0, 17.0, 17.0)  # ASSUMED outline x0 y0 x1 y1 (the board outline is still open on the map)

# via kinds: (pad diameter, hole); a foreign via cuts hole/2 + HOLE_CU out of a plane (unused inner pads are removed)
VIA_SUPPLY, VIA_SIGNAL, VIA_OUT, VIA_PWR_OUT = (0.4, 0.2), (0.30, 0.15), (0.4, 0.2), (0.5, 0.3)
HOLE_CU = 0.2
MINW = 0.2                         # narrowest copper that counts as connected (the sketch's minwidth)

ROWS = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "P", "R", "T", "U", "V", "W", "Y",
        "AA", "AB", "AC", "AD", "AE", "AF", "AG", "AH"]


def rc(ball):
    m = re.match(r"([A-Z]+)(\d+)", ball)
    return ROWS.index(m.group(1)), int(m.group(2)) - 1


def ring(ball):
    r, c = rc(ball)
    return min(r, c, 27 - r, 27 - c) + 1


def base(name):
    return re.sub(r"_\d+$", "", name)


# ---- rails: supply pin group -> rail at the ball. Filled from the reference schematic (see FACTS.md). -------------
RAIL_OF = {}          # set by rails.py


def load_rails():
    import rails
    RAIL_OF.update(rails.RAIL_OF)


SUPPLY_TYPES = ("PI", "API")


def soc_balls():
    """[(ball, x, y, kind, net)] kind: 'pwr', 'gnd', 'sig', 'nc'; net is the rail for 'pwr'."""
    out = []
    for p in PINS:
        b, n, t = p["ball"], p["name"], p["type"]
        x, y = SOC_XY[b]
        g = base(n)
        if g in RAIL_OF:
            out.append((b, x, y, "pwr", RAIL_OF[g]))
        elif t in ("G", "AG"):
            out.append((b, x, y, "gnd", "GND"))
        else:
            out.append((b, x, y, "sig", n))
    return out


def soc_vias():
    """Via sites of the survey fan-out (bga_fan, H743 logic on 636 balls): every supply and ground ball, and the
    signal balls from ring 3 inwards (rings 1 and 2 leave on the top layer, as on the official board).
    -> [(x, y, kind, net, ball)] kind 'pwr' | 'gnd' | 'sig'."""
    kinds = {b: (k, net) for b, _, _, k, net in soc_balls()}
    out = []
    for b, d in FAN["supply"].items():
        k, net = kinds[b]
        if k == "sig":      # the survey treated a few analogue pins as supplies; keep them as signal vias
            k = "sig"
        out.append((d["via"][0] - FAN_ORIGIN[0], d["via"][1] - FAN_ORIGIN[1], k, net, b))
    for b, d in FAN["signal"].items():
        if ring(b) >= 3:
            k, net = kinds[b]
            out.append((d["via"][0] - FAN_ORIGIN[0], d["via"][1] - FAN_ORIGIN[1], k if k != "sig" else "sig", net, b))
    return out


# ---- DDR3 x16, 96 balls, top view; columns 1 2 3 | 7 8 9 ---------------------------------------------------------
DDR_ROWS = """A: VDDQ DQ13 DQ15 | DQ12 VDDQ VSS
B: VSSQ VDD VSS | UDQS# DQ14 VSSQ
C: VDDQ DQ11 DQ9 | UDQS DQ10 VDDQ
D: VSSQ VDDQ UDM | DQ8 VSSQ VDD
E: VSS VSSQ DQ0 | LDM VSSQ VDDQ
F: VDDQ DQ2 LDQS | DQ1 DQ3 VSSQ
G: VSSQ DQ6 LDQS# | VDD VSS VSSQ
H: VREFDQ VDDQ DQ4 | DQ7 DQ5 VDDQ
J: NC VSS RAS# | CK VSS NC
K: ODT VDD CAS# | CK# VDD CKE
L: NC CS# WE# | A10 ZQ NC
M: VSS BA0 BA2 | NC VREFCA VSS
N: VDD A3 A0 | A12 BA1 VDD
P: VSS A5 A2 | A1 A4 VSS
R: VDD A7 A9 | A11 A6 VDD
T: VSS RESET# A13 | A14 A8 VSS"""
DDR_ALL = []      # (ball, function, x, y, via x, via y) in the chip's own frame
for i, line in enumerate(DDR_ROWS.splitlines()):
    row, rest = line.split(":")
    for col, fn in zip((1, 2, 3, 7, 8, 9), rest.replace("|", " ").split()):
        x, y = (col - 5) * 0.8, (i - 7.5) * 0.8
        sx = 1 if col <= 3 else -1          # dog-bone towards the centre gap
        DDR_ALL.append((f"{row}{col}", fn, x, y, x + 0.4 * sx, y + 0.4))


def rot(p, deg):
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    return (p[0] * c + p[1] * s, -p[0] * s + p[1] * c)


def _ddr3_fn(name):
    for part in name.split("/"):
        if part.startswith("DDR3_"):
            return part[5:]


def chips():
    """Placement decided in issue 34 (variant 'l-wide'): {'A': (cx, cy, rot), 'B': ...}."""
    soc = {}
    for p in PINS:
        if p["part"] == "F" and _ddr3_fn(p["name"]):
            soc[_ddr3_fn(p["name"])] = p["ball"]
    def cen(k, axis):
        fns = [f"DQ{8 * k + i}" for i in range(8)] + [f"DM{k}", f"DQS{k}P", f"DQS{k}N"]
        return [SOC_XY[soc[f]][axis] for f in fns]
    d0 = cen(0, 1) + cen(1, 1); d1 = cen(2, 0) + cen(3, 0)
    off = -SOC_FIELD - GAP - 3.2
    return {"A": (off, sum(d0) / len(d0) - 3.2, 180), "B": (sum(d1) / len(d1) - 3.2, off, 270)}


def chip_balls(c):
    """[(ball, function, x, y, via x, via y)] in the board frame."""
    cx, cy, r = chips()[c]
    out = []
    for b, fn, x, y, vx, vy in DDR_ALL:
        px, py = rot((x, y), r); qx, qy = rot((vx, vy), r)
        out.append((b, fn, cx + px, cy + py, cx + qx, cy + qy))
    return out


def chip_poly(c, grow=0.0):
    cx, cy, r = chips()[c]
    w, h = DDR_BODY[0] / 2 + grow, DDR_BODY[1] / 2 + grow
    return [(cx + x, cy + y) for x, y in (rot(p, r) for p in ((-w, -h), (w, -h), (w, h), (-w, h)))]


def branch_vias():
    """T-branch via sites of the placement prototype (issue 34), one per address / control / clock net."""
    f = HERE / "placement_l_wide.json"
    return [(t["split"][0], t["split"][1], t["net"]) for t in json.loads(f.read_text(encoding="utf-8"))["t"]]


DDR_RAIL = {"VDD": "VCC_DDR", "VDDQ": "VCC_DDR", "VSS": "GND", "VSSQ": "GND"}


def all_vias():
    """Every through via the sketch has to live with: [(x, y, hole, pad, net, what)]."""
    out = []
    for x, y, k, net, b in soc_vias():
        d, h = VIA_SUPPLY if k != "sig" else VIA_SIGNAL
        out.append((x, y, h, d, net if k != "sig" else "sig:" + b, "soc:" + b))
    for c in "AB":
        for b, fn, x, y, vx, vy in chip_balls(c):
            if fn == "NC":
                continue
            net = DDR_RAIL.get(fn, f"sig:{c}.{fn}")
            out.append((vx, vy, VIA_OUT[1], VIA_OUT[0], net, f"ddr{c}:{b}"))
    for x, y, n in branch_vias():
        out.append((x, y, VIA_OUT[1], VIA_OUT[0], "sig:T." + n, "branch:" + n))
    return out
