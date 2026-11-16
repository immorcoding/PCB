"""Build the length-rule test board `lentest.kicad_pcb` (+ .kicad_pro, expected.json).

Every net has a length that is known from the geometry alone (turtle path: lines +
circular arcs), so each DRC length/skew result can be checked against `expected.json`.

Run with KiCad's Python:  D:\\KiCad\\bin\\python.exe -I make_board.py <outdir>
Layer stack and via heights are written by hand (pcbnew's Python API hides the stackup).
"""
import json, math, os, re, shutil, sys
import pcbnew
from pcbnew import VECTOR2I, FromMM

OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
TEMPLATE_PRO = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else None
STEM = "lentest"
b = pcbnew.CreateEmptyBoard()
b.SetCopperLayerCount(6)
mm = FromMM
V = lambda x, y: VECTOR2I(mm(x), mm(y))
LAYERS = {"F": pcbnew.F_Cu, "In1": pcbnew.In1_Cu, "In2": pcbnew.In2_Cu,
          "In3": pcbnew.In3_Cu, "In4": pcbnew.In4_Cu, "B": pcbnew.B_Cu}
W = 0.1  # track width

expected = {}      # net -> dict(track=..., vias=[(x, y, layerA, layerB)], pad_to_die=...)
nets = {}


def net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(b, name)
        b.Add(n)
        nets[name] = n
        expected[name] = {"track": 0.0, "vias": [], "pad_to_die": 0.0, "routes": []}
    return nets[name]


def add_line(n, layer, p0, p1):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(V(*p0)); t.SetEnd(V(*p1)); t.SetWidth(mm(W))
    t.SetLayer(LAYERS[layer]); t.SetNet(net(n)); b.Add(t)
    expected[n]["track"] += math.dist(p0, p1)


def add_arc(n, layer, p0, pm, p1, length):
    a = pcbnew.PCB_ARC(b)
    a.SetStart(V(*p0)); a.SetMid(V(*pm)); a.SetEnd(V(*p1)); a.SetWidth(mm(W))
    a.SetLayer(LAYERS[layer]); a.SetNet(net(n)); b.Add(a)
    expected[n]["track"] += length
    return a


def add_via(n, pos, layers=("F", "B")):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(V(*pos)); v.SetWidth(mm(0.45)); v.SetDrill(mm(0.2))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(LAYERS[layers[0]], LAYERS[layers[1]])
    v.SetNet(net(n)); b.Add(v)
    expected[n]["vias"].append(list(pos))


class Turtle:
    """Polyline of lines and arcs with analytically known length."""
    def __init__(self, n, layer, x, y, heading_deg=0.0):
        self.n, self.layer, self.p, self.h = n, layer, (x, y), math.radians(heading_deg)

    def line(self, length):
        if length <= 1e-9:
            return self
        q = (self.p[0] + length * math.cos(self.h), self.p[1] + length * math.sin(self.h))
        add_line(self.n, self.layer, self.p, q); self.p = q
        return self

    def arc(self, r, turn_deg):
        d = math.radians(turn_deg); s = 1 if d > 0 else -1
        c = (self.p[0] - s * r * math.sin(self.h), self.p[1] + s * r * math.cos(self.h))
        a0 = math.atan2(self.p[1] - c[1], self.p[0] - c[0])
        pt = lambda a: (c[0] + r * math.cos(a), c[1] + r * math.sin(a))
        p1, pm = pt(a0 + d), pt(a0 + d / 2)
        add_arc(self.n, self.layer, self.p, pm, p1, r * abs(d))
        self.p, self.h = p1, self.h + d
        return self

    def to(self, q):
        """straight line to q (any direction); heading follows"""
        self.h = math.atan2(q[1] - self.p[1], q[0] - self.p[0])
        add_line(self.n, self.layer, self.p, q); self.p = q
        return self


def make_fp(ref, x, y, pads):
    """pads: list of (number, px, py, netname, w, h, die_mm)"""
    fp = pcbnew.FOOTPRINT(b)
    fp.SetReference(ref); fp.SetValue(ref); fp.SetPosition(V(x, y))
    for (num, px, py, nn, w, h, die) in pads:
        p = pcbnew.PAD(fp)
        p.SetNumber(str(num)); p.SetShape(pcbnew.PAD_SHAPE_RECT)
        p.SetSize(V(w, h)); p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        p.SetLayerSet(p.SMDMask()); p.SetPosition(V(px, py))
        if nn:
            p.SetNet(net(nn))
        if die:
            p.SetPadToDieLength(mm(die))
            expected[nn]["pad_to_die"] += die
        fp.Add(p)
    b.Add(fp)


XA, XB = 0.0, 50.0        # J1 / J2 pad columns
j1, j2 = [], []


def row(num, name, y, die_a=0.0, die_b=0.0):
    net(name)
    j1.append((num, XA, y, name, 0.6, 0.6, die_a))
    j2.append((num, XB, y, name, 0.6, 0.6, die_b))


# ---- nets -------------------------------------------------------------------
# D0: straight, 50.000 mm centre to centre, F.Cu
row(1, "/SDRAM_D0", 0)
Turtle("/SDRAM_D0", "F", XA, 0).line(50)

# D1: 45 degree detour, 10 + 2*sqrt2 + 26 + 2*sqrt2 + 10 = 51.657
row(2, "/SDRAM_D1", 4)
t = Turtle("/SDRAM_D1", "F", XA, 4)
for q in [(10, 4), (12, 2), (38, 2), (40, 4), (50, 4)]:
    t.to(q)

# D2: two semicircles (r 1.5, one down one up), lines in between: 10 + pi*1.5 + 5 + pi*1.5 + 29
row(3, "/SDRAM_D2", 8)
n = "/SDRAM_D2"
add_line(n, "F", (0, 8), (10, 8))
add_arc(n, "F", (10, 8), (11.5, 9.5), (13, 8), math.pi * 1.5)
add_line(n, "F", (13, 8), (18, 8))
add_arc(n, "F", (18, 8), (19.5, 6.5), (21, 8), math.pi * 1.5)
add_line(n, "F", (21, 8), (50, 8))

# D3: F.Cu -> via (through) -> B.Cu -> via -> F.Cu ; 10 + 30 + 10 on tracks, two F-B vias
row(4, "/SDRAM_D3", 12)
n = "/SDRAM_D3"
add_line(n, "F", (0, 12), (10, 12)); add_via(n, (10, 12), ("F", "B"))
add_line(n, "B", (10, 12), (40, 12)); add_via(n, (40, 12), ("F", "B"))
add_line(n, "F", (40, 12), (50, 12))
expected[n]["routes"] = [["F", "B"]]

# D4: same, middle part on In2.Cu (through vias, only F..In2 is used by the signal)
row(5, "/SDRAM_D4", 16)
n = "/SDRAM_D4"
add_line(n, "F", (0, 16), (10, 16)); add_via(n, (10, 16), ("F", "B"))
add_line(n, "In2", (10, 16), (40, 16)); add_via(n, (40, 16), ("F", "B"))
add_line(n, "F", (40, 16), (50, 16))
expected[n]["routes"] = [["F", "In2"]]

# D5: middle part on In4.Cu
row(6, "/SDRAM_D5", 20)
n = "/SDRAM_D5"
add_line(n, "F", (0, 20), (10, 20)); add_via(n, (10, 20), ("F", "B"))
add_line(n, "In4", (10, 20), (40, 20)); add_via(n, (40, 20), ("F", "B"))
add_line(n, "F", (40, 20), (50, 20))
expected[n]["routes"] = [["F", "In4"]]

# D6: middle part on In1.Cu
row(7, "/SDRAM_D6", 24)
n = "/SDRAM_D6"
add_line(n, "F", (0, 24), (10, 24)); add_via(n, (10, 24), ("F", "B"))
add_line(n, "In1", (10, 24), (40, 24)); add_via(n, (40, 24), ("F", "B"))
add_line(n, "F", (40, 24), (50, 24))
expected[n]["routes"] = [["F", "In1"]]

# D7: deliberately too long: 5 + 10 + 40 + 10 + 5 = 70, F.Cu
row(8, "/SDRAM_D7", 28)
t = Turtle("/SDRAM_D7", "F", XA, 28)
for q in [(5, 28), (5, 38), (45, 38), (45, 28), (50, 28)]:
    t.to(q)

# D8: straight 50, pad-to-die 3.0 mm on J1 pad, 1.5 mm on J2 pad (4.5 total if counted)
row(9, "/SDRAM_D8", 44, die_a=3.0, die_b=1.5)
Turtle("/SDRAM_D8", "F", XA, 44).line(50)

# SDCLK: 10 + sqrt2 + 28 + sqrt2 + 10 = 50.828
row(10, "/SDCLK", 48)
t = Turtle("/SDCLK", "F", XA, 48)
for q in [(10, 48), (11, 49), (39, 49), (40, 48), (50, 48)]:
    t.to(q)

# D9: round-cornered meander with the project's numbers: r 0.25 quarter arcs, amplitude 0.5
# (arc up, arc across, arc down; no straight legs), 5 bumps. Total length is computed below.
row(11, "/SDRAM_D9", 54)
R, WTOP, GAP, BUMPS = 0.25, 0.5, 0.75, 5
t = Turtle("/SDRAM_D9", "F", XA, 54)
t.line(5)
for i in range(BUMPS):
    t.arc(R, -90).arc(R, 90).line(WTOP).arc(R, 90).arc(R, -90)   # up, over, down (no legs)
    if i < BUMPS - 1:
        t.line(GAP)
# each bump advances x by 4R + WTOP = 1.5? (arcs: R each in x, plus top run) -> finish the baseline
t.to((XB, 54))

# D10: meander with straight legs: r 0.25, legs 1.0 (amplitude 1.5), 3 bumps
row(12, "/SDRAM_D10", 60)
t = Turtle("/SDRAM_D10", "F", XA, 60)
t.line(5)
for i in range(3):
    t.arc(R, -90).line(1.0).arc(R, 90).line(WTOP).arc(R, 90).line(1.0).arc(R, -90)
    if i < 2:
        t.line(GAP)
t.to((XB, 60))

# SDCLK with a series resistor: /CLK2_A  J1.13 -> R1.1 ; /CLK2_B  R1.2 -> J2.13
net("/CLK2_A"); net("/CLK2_B")
j1.append((13, XA, 66, "/CLK2_A", 0.6, 0.6, 0.0))
j2.append((13, XB, 66, "/CLK2_B", 0.6, 0.6, 0.0))
make_fp("R1", 4, 66, [(1, 3.2, 66, "/CLK2_A", 0.8, 0.9, 0.0), (2, 4.8, 66, "/CLK2_B", 0.8, 0.9, 0.0)])
Turtle("/CLK2_A", "F", XA, 66).to((3.2, 66))
Turtle("/CLK2_B", "F", 4.8, 66).to((XB, 66))

# QSPI class nets (second net class, same pad columns)
row(14, "/QSPI_CLK", 70); Turtle("/QSPI_CLK", "F", XA, 70).line(50)
row(15, "/QSPI_IO0", 74)
t = Turtle("/QSPI_IO0", "F", XA, 74)
for q in [(10, 74), (12, 72), (38, 72), (40, 74), (50, 74)]:
    t.to(q)

# T-branch net: main path 50 mm (J1.16 -> J2.16) plus a 5 mm dangling stub off the middle.
# Total copper 55 mm; the pad-to-pad path is 50 mm.
row(16, "/TBR", 78)
Turtle("/TBR", "F", XA, 78).line(25).line(25)
add_line("/TBR", "F", (25, 78), (25, 83))

make_fp("J1", XA, 0, j1)
make_fp("J2", XB, 0, j2)

# isolated geometry nets (no pads): arcs of various angle / radius, known length
iso = [("/ARC_30deg_r0.25", 0.25, 30), ("/ARC_90deg_r0.25", 0.25, 90), ("/ARC_225deg_r2", 2.0, 225),
       ("/ARC_340deg_r1", 1.0, 340), ("/ARC_5deg_r100", 100.0, 5)]
for k, (nm, r, ang) in enumerate(iso):
    Turtle(nm, "F", 70, 4 + 12 * k).line(1.0).arc(r, ang).line(1.0)

# ---- save board -------------------------------------------------------------
os.makedirs(OUT, exist_ok=True)
pcb_path = os.path.join(OUT, STEM + ".kicad_pcb")
pcbnew.SaveBoard(pcb_path, b)

# stackup: distinct dielectric thicknesses so every via height is distinguishable
STACK = """		(stackup
			(layer "F.SilkS" (type "Top Silk Screen"))
			(layer "F.Paste" (type "Top Solder Paste"))
			(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
			(layer "F.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 1" (type "prepreg") (thickness 0.1) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In1.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 2" (type "core") (thickness 0.4) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In2.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 3" (type "prepreg") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In3.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 4" (type "core") (thickness 0.5) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In4.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 5" (type "prepreg") (thickness 0.1) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "B.Cu" (type "copper") (thickness 0.035))
			(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
			(layer "B.Paste" (type "Bottom Solder Paste"))
			(layer "B.SilkS" (type "Bottom Silk Screen"))
			(copper_finish "None")
			(dielectric_constraints no)
		)
"""
text = open(pcb_path, encoding="utf-8").read()
if "(stackup" in text:
    text = re.sub(r"\t\t\(stackup.*?\n\t\t\)\n", STACK, text, count=1, flags=re.S)
else:
    text = text.replace("\t(setup\n", "\t(setup\n" + STACK, 1)
open(pcb_path, "w", encoding="utf-8").write(text)

# ---- project file: net classes by name pattern -----------------------------
pro = {}
if TEMPLATE_PRO:
    pro = json.load(open(TEMPLATE_PRO, encoding="utf-8"))
ns = pro.setdefault("net_settings", {})
default = next(c for c in ns["classes"] if c["name"] == "Default") if ns.get("classes") else None
if default is None:
    default = {"name": "Default", "clearance": 0.127, "track_width": 0.1, "via_diameter": 0.45,
               "via_drill": 0.2, "diff_pair_gap": 0.15, "diff_pair_width": 0.15,
               "diff_pair_via_gap": 0.25, "microvia_diameter": 0.3, "microvia_drill": 0.1,
               "priority": 2147483647, "tuning_profile": "", "bus_width": 6, "wire_width": 6,
               "line_style": 0, "pcb_color": "rgba(0, 0, 0, 0.000)",
               "schematic_color": "rgba(0, 0, 0, 0.000)"}
classes = [default]
for i, nm in enumerate(["SDRAM", "QSPI"]):
    c = dict(default); c["name"] = nm; c["priority"] = i; classes.append(c)
ns["classes"] = classes
ns["netclass_patterns"] = [
    {"netclass": "SDRAM", "pattern": "/SDRAM_*"},
    {"netclass": "SDRAM", "pattern": "/SDCLK*"},
    {"netclass": "SDRAM", "pattern": "/CLK2_*"},
    {"netclass": "QSPI", "pattern": "/QSPI_*"},
]
ns["netclass_assignments"] = None
ns.setdefault("meta", {"version": 5})
pro.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {})
pro["board"]["design_settings"]["rules"]["use_height_for_length_calcs"] = True
json.dump(pro, open(os.path.join(OUT, STEM + ".kicad_pro"), "w", encoding="utf-8"), indent=2)

for k, v in expected.items():
    v["track"] = round(v["track"], 6)
json.dump(expected, open(os.path.join(OUT, "expected.json"), "w", encoding="utf-8"), indent=1)
print("wrote", pcb_path, "nets:", len(nets))
