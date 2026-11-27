"""PROTOTYPE (throwaway): placement options for RK3568 + 2 x DDR3 (issue 34).

    python rk3568_ddr3_core/probes/placement_proto/draw.py

Writes placement_variants.html and metrics.json next to this file.
Lengths are ball-to-ball octilinear estimates (45/90 shortest path, obstacles
ignored), not routed lengths. Nothing here went through DRC.
"""
import json, math, re, statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = HERE.parents[1] / "lib"
PINS = json.loads((LIB / "rk3568_pins.json").read_text(encoding="utf-8"))
PKG = json.loads((LIB / "rk3568_pin_length_mm.json").read_text(encoding="utf-8"))
FP = (LIB / "rk3568_ddr3_core.pretty" / "BGA-636_19x19mm_Layout28x28_P0.65mm.kicad_mod").read_text(encoding="utf-8")
SOC_XY = {m.group(1): (float(m.group(2)), float(m.group(3)))
          for m in re.finditer(r'\(pad "([A-Z]+\d+)" smd \w+\s*\(at ([-\d.]+) ([-\d.]+)', FP)}

BRANCH_MAX = 15.24      # 600 mil, Rockchip limit per T branch
BAND = 7.51             # guarded byte-lane band width (issue 47)
SOC_HALF, SOC_FIELD = 9.5, 8.775
DDR_BODY = (9.0, 14.0)  # keep-out, largest candidate body
MARGIN = 1.0            # rule area = outline + 1 mm

# JEDEC DDR3 x16, 96 balls, top view; columns 1 2 3 | 7 8 9
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
DDR = {}          # function -> local (x, y); power balls keyed by ball name
DDR_ALL = []      # (ball, function, x, y)
for i, line in enumerate(DDR_ROWS.splitlines()):
    row, rest = line.split(":")
    names = rest.replace("|", " ").split()
    for col, fn in zip((1, 2, 3, 7, 8, 9), names):
        x, y = (col - 5) * 0.8, (i - 7.5) * 0.8
        DDR_ALL.append((f"{row}{col}", fn, x, y))
        if fn not in ("VDD", "VDDQ", "VSS", "VSSQ", "NC"):
            DDR[fn] = (x, y)

# ---- SoC DDR3 functions -------------------------------------------------
def ddr3_fn(name):
    for part in name.split("/"):
        if part.startswith("DDR3_"):
            return part[5:]
    return None

SOC = {}   # DDR3 function -> ball
for p in PINS:
    if p["part"] == "F":
        fn = ddr3_fn(p["name"])
        if fn:
            SOC[fn] = p["ball"]
SOC_CLASS = {}  # ball -> class for drawing
for p in PINS:
    b, n = p["ball"], p["name"]
    fn = ddr3_fn(n) if p["part"] == "F" else None
    if fn and re.match(r"(DQ\d+|DM\d|DQS\dP|DQS\dN)$", fn):
        k = int(re.search(r"\d+", fn).group())
        SOC_CLASS[b] = f"b{k // 8 if fn.startswith('DQ') and not fn.startswith('DQS') else k}"
    elif fn in ("CLKP", "CLKN"):
        SOC_CLASS[b] = "ck"
    elif fn and fn not in ("ODT1", "CS1n"):
        SOC_CLASS[b] = "ac"
    elif n.startswith("DDRPHY_VDDQ"):
        SOC_CLASS[b] = "vq"
    else:
        SOC_CLASS[b] = "o"

def byte_nets(k):
    """SoC byte k -> list of (soc function, role) ; role is DQ index 0-7, 'DM', 'DQSP', 'DQSN'."""
    out = [(f"DQ{8 * k + i}", i) for i in range(8)]
    return out + [(f"DM{k}", "DM"), (f"DQS{k}P", "DQSP"), (f"DQS{k}N", "DQSN")]

def chip_fn(role, upper):
    if role == "DM":
        return "UDM" if upper else "LDM"
    if role == "DQSP":
        return "UDQS" if upper else "LDQS"
    if role == "DQSN":
        return "UDQS#" if upper else "LDQS#"
    return f"DQ{role + (8 if upper else 0)}"

AC = {"CLKP": "CK", "CLKN": "CK#", "CKE": "CKE", "ODT0": "ODT", "CS0n": "CS#", "RASn": "RAS#",
      "CASn": "CAS#", "WEn": "WE#", "BA0": "BA0", "BA1": "BA1", "BA2": "BA2", "RESETn": "RESET#"}
AC.update({f"A{i}": f"A{i}" for i in range(15)})   # A15 is NC on a 4 Gb part
TIGHT = ("CLKP", "CLKN", "CKE", "ODT0", "CS0n")

# ---- geometry -----------------------------------------------------------
def rot(p, deg):
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    return (p[0] * c + p[1] * s, -p[0] * s + p[1] * c)

def octd(a, b):
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)

def cen(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))

class Variant:
    def __init__(self, key, title, blurb, soc_rot, chips, notes):
        self.key, self.title, self.blurb, self.soc_rot, self.chips, self.notes = key, title, blurb, soc_rot, chips, notes
        self.soc = {b: rot(xy, soc_rot) for b, xy in SOC_XY.items()}

    def chip(self, c, fn):
        cx, cy, r = self.chips[c]
        x, y = rot(DDR[fn], r)
        return (cx + x, cy + y)

    def chip_pt(self, c, local):
        cx, cy, r = self.chips[c]
        x, y = rot(local, r)
        return (cx + x, cy + y)

    def in_soc_field(self, p, grow=SOC_HALF + MARGIN + 0.5 - SOC_FIELD):   # split vias stay outside the SoC rule area
        x, y = rot(p, -self.soc_rot)
        return abs(x) < SOC_FIELD + grow and abs(y) < SOC_FIELD + grow

    def polys(self):
        out = {"soc": [rot(p, self.soc_rot) for p in ((-SOC_HALF, -SOC_HALF), (SOC_HALF, -SOC_HALF), (SOC_HALF, SOC_HALF), (-SOC_HALF, SOC_HALF))]}
        for c in "AB":
            w, h = DDR_BODY[0] / 2, DDR_BODY[1] / 2
            out[c] = [self.chip_pt(c, p) for p in ((-w, -h), (w, -h), (w, h), (-w, h))]
        return out

    def analyse(self):
        m = {"key": self.key, "title": self.title, "bytes": [], "lines": []}
        # data: chip A takes SoC bytes 0,1 ; chip B takes 2,3 ; lower/upper picked by total length
        for c, ks in (("A", (0, 1)), ("B", (2, 3))):
            best = None
            for swap in (False, True):
                tot, rows = 0, []
                for k, upper in zip(ks, (swap, not swap)):
                    nets = []
                    for fn, role in byte_nets(k):
                        a, b = self.soc[SOC[fn]], self.chip(c, chip_fn(role, upper))
                        nets.append({"net": fn, "a": a, "b": b, "pcb": octd(a, b), "pkg": PKG.get(SOC[fn], 0.0)})
                    tot += sum(n["pcb"] for n in nets)
                    rows.append((k, upper, nets))
                if best is None or tot < best[0]:
                    best = (tot, rows)
            for k, upper, nets in best[1]:
                pcb = [n["pcb"] for n in nets]
                elec = [n["pcb"] + n["pkg"] for n in nets]
                m["bytes"].append({"byte": k, "chip": c, "half": "高" if upper else "低", "n": len(nets),
                                   "pcb_min": min(pcb), "pcb_med": st.median(pcb), "pcb_max": max(pcb),
                                   "elec_spread": max(elec) - min(elec),
                                   "tune_total": sum(max(elec) - e for e in elec),
                                   "a_cen": cen([n["a"] for n in nets]), "b_cen": cen([n["b"] for n in nets])})
                for n in nets:
                    m["lines"].append((f"b{k}", n["a"], n["b"]))
        # T nets: split point by grid search, minimising trunk + 2 * longer branch
        xs = [p[0] for poly in self.polys().values() for p in poly]; ys = [p[1] for poly in self.polys().values() for p in poly]
        grid = [(x * 0.25, y * 0.25) for x in range(int(min(xs) * 4) - 8, int(max(xs) * 4) + 9)
                for y in range(int(min(ys) * 4) - 8, int(max(ys) * 4) + 9)]
        grid = [g for g in grid if not self.in_soc_field(g)]
        m["t"] = []
        for fn, cf in AC.items():
            s0, a, b = self.soc[SOC[fn]], self.chip("A", cf), self.chip("B", cf)
            sp = min(grid, key=lambda g: octd(s0, g) + 2 * max(octd(g, a), octd(g, b)))
            m["t"].append({"net": fn, "soc": s0, "split": sp, "a": a, "b": b, "trunk": octd(s0, sp),
                           "ba": octd(sp, a), "bb": octd(sp, b), "pkg": PKG.get(SOC[fn], 0.0)})
        t = m["t"]
        br = [max(x["ba"], x["bb"]) for x in t]
        m["t_sum"] = {"n": len(t), "trunk_med": st.median(x["trunk"] for x in t), "trunk_max": max(x["trunk"] for x in t),
                      "branch_med": st.median(br), "branch_max": max(br), "over": sum(b > BRANCH_MAX for b in br),
                      "mis_med": st.median(abs(x["ba"] - x["bb"]) for x in t), "mis_max": max(abs(x["ba"] - x["bb"]) for x in t),
                      "path_med": st.median(x["trunk"] + max(x["ba"], x["bb"]) for x in t),
                      "path_min": min(x["trunk"] + max(x["ba"], x["bb"]) + x["pkg"] for x in t),
                      "path_max": max(x["trunk"] + max(x["ba"], x["bb"]) + x["pkg"] for x in t)}
        ck = [x for x in t if x["net"] == "CLKP"][0]
        m["ck"] = {"trunk": ck["trunk"], "ba": ck["ba"], "bb": ck["bb"], "split": ck["split"]}
        # gaps and area
        socf = [self.soc[b] for b in SOC_XY]
        gaps = {}
        for c in "AB":
            cb = [self.chip_pt(c, (x, y)) for _, _, x, y in DDR_ALL]
            gaps[c] = min(math.dist(p, q) for p in cb for q in socf if SOC_CLASS[[k for k, v in self.soc.items() if v == q][0]] != "o" or True)
        m["gap"] = gaps
        pts = [p for poly in self.polys().values() for p in poly]
        x0, x1 = min(p[0] for p in pts) - MARGIN, max(p[0] for p in pts) + MARGIN
        y0, y1 = min(p[1] for p in pts) - MARGIN, max(p[1] for p in pts) + MARGIN
        m["bbox"] = (x0, y0, x1, y1); m["w"], m["h"] = x1 - x0, y1 - y0; m["area"] = (x1 - x0) * (y1 - y0)
        # DDR part of the block: chips + the SoC's DDR corner balls + split points
        dd = [p for c in "AB" for p in self.polys()[c]] + [self.soc[b] for b, k in SOC_CLASS.items() if k != "o"] + [x["split"] for x in t]
        m["ddr_w"] = max(p[0] for p in dd) - min(p[0] for p in dd); m["ddr_h"] = max(p[1] for p in dd) - min(p[1] for p in dd)
        return m


def l_variant(key, title, blurb, gap, slide, notes):
    """Chips along the west and north SoC edges, long axis parallel to the edge, address end at the A1 corner."""
    d0 = cen([SOC_XY[SOC[f]] for k in (0, 1) for f, _ in byte_nets(k)])[1]    # west-edge data centroid (y)
    d1 = cen([SOC_XY[SOC[f]] for k in (2, 3) for f, _ in byte_nets(k)])[0]    # north-edge data centroid (x)
    off = -SOC_FIELD - gap - 3.2
    return Variant(key, title, blurb, 0, {"A": (off, d0 - 3.2 - slide, 180), "B": (d1 - 3.2 - slide, off, 270)}, notes)


VARIANTS = [
    l_variant("l-tight", "方案 1　贴边 L 形，紧凑", "两颗各贴 SoC 的西边和北边，长边平行于 SoC 的边，地址端朝 A1 角；球区到球区 5.0 mm。", 5.0, 0.0,
              ["SoC 不转。没有官方实物对照，是按球位推出来的摆法。", "数据线最短；包地线带 7.51 mm 要在 5 mm 的空当里展开，第二个字节组多半要走 L6。",
               "分叉点落在两颗颗粒地址端之间的角上，L4。"]),
    l_variant("l-wide", "方案 2　贴边 L 形，留出补线区", "同样的朝向，球区到球区拉到 7.5 mm（包地原型用的间距），空当里放得下蛇形。", 7.5, 0.0,
              ["包地线带能在规则区外完全展开，蛇形有地方放。", "每边多占 2.5 mm；分支随之变长。"]),
    Variant("evb1", "方案 3　照官方 EVB1：SoC 转 45°，两颗并排", "颗粒的位置照搬官方 EVB1（2 × 16 位 DDR4，T 型）：SoC 转 45°，两颗并排在 A1 角外面，长轴顺着角的对角线，数据端朝 SoC，地址端朝外，中间留 11.9 mm 的走廊放分叉点。", -45,
            {"A": (-7.39, -21.81, 180), "B": (10.90, -21.81, 180)},   # EVB1 chip centres (-20.65,-10.20) / (-7.71,-23.13) in the SoC ball frame, turned 45 deg,
            ["两块官方板（EVB1、LP4X 模板）的 SoC 都是转 45° 摆的；这是唯一有官方实物可对照的方案。", "两颗朝向相同、左右并排，两条分支天然接近等长；官方把分叉过孔放在走廊里靠地址端的位置（图上的分叉点是按最短算的，比官方更靠近 SoC）。",
             "SoC 和颗粒必有一个不在正交方向上：现有的扇出、出线计数、规则区工具都按正交球阵写，要补“斜放的 BGA”这一项。",
             "外接矩形最长；SoC 两侧的三角形空地在完整的板上给别的器件用。"]),
    Variant("perp", "对照　颗粒垂直于边", "两颗的短边对着 SoC，数据端朝 SoC，地址端在远端。只作对照。", 0,
            {"A": (-SOC_FIELD - 5.0 - 6.0, -3.9, 270), "B": (-0.65, -SOC_FIELD - 5.0 - 6.0, 180)},
            ["数据线最短，但两颗的地址区相距约 30 mm，分支超过 600 mil 的上限。不推荐，只为说明为什么地址端要朝角。"]),
]

# ---- drawing ------------------------------------------------------------
S = 11  # px per mm

def svg(v, m):
    x0, y0, x1, y1 = m["bbox"]
    pad = 3
    x0 -= pad; y0 -= pad; x1 += pad; y1 += pad + 2
    P = lambda p: f"{(p[0] - x0) * S:.1f},{(p[1] - y0) * S:.1f}"
    X = lambda x: (x - x0) * S
    Y = lambda y: (y - y0) * S
    o = [f'<svg viewBox="0 0 {(x1 - x0) * S:.0f} {(y1 - y0) * S:.0f}" role="img" aria-label="{v.title}">']
    polys = v.polys()
    # byte bands (under everything)
    for b in m["bytes"]:
        o.append(f'<line class="band b{b["byte"]}s" x1="{X(b["a_cen"][0]):.1f}" y1="{Y(b["a_cen"][1]):.1f}" x2="{X(b["b_cen"][0]):.1f}" y2="{Y(b["b_cen"][1]):.1f}" stroke-width="{BAND * S:.1f}"/>')
    # block bbox
    bx0, by0, bx1, by1 = m["bbox"]
    o.append(f'<rect class="bbox" x="{X(bx0):.1f}" y="{Y(by0):.1f}" width="{(bx1 - bx0) * S:.1f}" height="{(by1 - by0) * S:.1f}"/>')
    o.append(f'<text class="dim" x="{X((bx0 + bx1) / 2):.1f}" y="{Y(by1) + 16:.1f}" text-anchor="middle">外接矩形 {m["w"]:.1f} × {m["h"]:.1f} mm（含 1 mm 规则区）</text>')
    for k, poly in polys.items():
        o.append(f'<polygon class="body" points="{" ".join(P(p) for p in poly)}"/>')
    # balls
    for b, xy in v.soc.items():
        k = SOC_CLASS[b]
        o.append(f'<circle class="{k}" cx="{X(xy[0]):.1f}" cy="{Y(xy[1]):.1f}" r="{(0.15 if k == "o" else 0.22) * S:.1f}"/>')
    for c in "AB":
        for ball, fn, x, y in DDR_ALL:
            p = v.chip_pt(c, (x, y))
            o.append(f'<circle class="o" cx="{X(p[0]):.1f}" cy="{Y(p[1]):.1f}" r="{0.19 * S:.1f}"/>')
        # back-side decoupling zone = ball field ; end labels
        f = [v.chip_pt(c, p) for p in ((-3.6, -6.4), (3.6, -6.4), (3.6, 6.4), (-3.6, 6.4))]
        o.append(f'<polygon class="back" points="{" ".join(P(p) for p in f)}"/>')
        for txt, loc in (("数据端", (0, -3.2)), ("地址端", (0, 3.2)), (f"颗粒 {c}", (0, 0))):
            p = v.chip_pt(c, loc)
            o.append(f'<text class="lbl" x="{X(p[0]):.1f}" y="{Y(p[1]) + 4:.1f}" text-anchor="middle">{txt}</text>')
        for fn, cls in (("ZQ", "att"), ("VREFCA", "att"), ("VREFDQ", "att")):
            p = v.chip(c, fn)
            o.append(f'<rect class="att" x="{X(p[0]) - 3:.1f}" y="{Y(p[1]) - 3:.1f}" width="6" height="6"/>')
    # SoC back decoupling zone for DDRPHY_VDDQ
    vq = [v.soc[b] for b, k in SOC_CLASS.items() if k == "vq"]
    c0 = cen(vq)
    o.append(f'<circle class="back" cx="{X(c0[0]):.1f}" cy="{Y(c0[1]):.1f}" r="{2.6 * S:.1f}"/>')
    o.append(f'<text class="lbl" x="{X(c0[0]):.1f}" y="{Y(c0[1]) + 4:.1f}" text-anchor="middle">VDDQ 背面去耦</text>')
    sc = cen(list(polys["soc"]))
    o.append(f'<text class="lbl big" x="{X(sc[0] + 3):.1f}" y="{Y(sc[1] + 4):.1f}" text-anchor="middle">RK3568</text>')
    a1 = v.soc["A1"]
    o.append(f'<text class="lbl" x="{X(a1[0]):.1f}" y="{Y(a1[1]) - 8:.1f}" text-anchor="middle">A1</text>')
    # data ratsnest
    for cls, a, b in m["lines"]:
        o.append(f'<line class="rat {cls}s" x1="{X(a[0]):.1f}" y1="{Y(a[1]):.1f}" x2="{X(b[0]):.1f}" y2="{Y(b[1]):.1f}"/>')
    # T nets
    for t in m["t"]:
        cls = "cks" if t["net"] in ("CLKP", "CLKN") else "acs"
        over = " over" if max(t["ba"], t["bb"]) > BRANCH_MAX else ""
        o.append(f'<polyline class="rat {cls}" points="{P(t["soc"])} {P(t["split"])}"/>')
        o.append(f'<polyline class="rat br {cls}{over}" points="{P(t["a"])} {P(t["split"])} {P(t["b"])}"/>')
        o.append(f'<circle class="split {cls}" cx="{X(t["split"][0]):.1f}" cy="{Y(t["split"][1]):.1f}" r="{0.2 * S:.1f}"/>')
    ck = m["ck"]["split"]
    o.append(f'<rect class="rc" x="{X(ck[0]) - 9:.1f}" y="{Y(ck[1]) - 20:.1f}" width="18" height="11"/>')
    o.append(f'<text class="lbl" x="{X(ck[0]):.1f}" y="{Y(ck[1]) - 24:.1f}" text-anchor="middle">CK 的 RC</text>')
    o.append("</svg>")
    return "\n".join(o)


def f1(x):
    return f"{x:.1f}"


def page(ms):
    rows = []
    def row(label, fn, cls=""):
        rows.append(f'<tr class="{cls}"><th scope="row">{label}</th>' + "".join(f"<td>{fn(m)}</td>" for m in ms) + "</tr>")
    row("外接矩形（含 1 mm 规则区）", lambda m: f'{m["w"]:.1f} × {m["h"]:.1f} mm')
    row("外接矩形面积", lambda m: f'{m["area"]:.0f} mm²')
    row("DDR 部分的跨度（颗粒 + SoC 的 DDR 角 + 分叉点）", lambda m: f'{m["ddr_w"]:.1f} × {m["ddr_h"]:.1f} mm')
    row("球区到球区，SoC–颗粒 A / B", lambda m: f'{m["gap"]["A"]:.1f} / {m["gap"]["B"]:.1f} mm')
    for k in range(4):
        def fb(m, k=k):
            b = [x for x in m["bytes"] if x["byte"] == k][0]
            return f'{f1(b["pcb_min"])} / {f1(b["pcb_med"])} / {f1(b["pcb_max"])}<small>→ 颗粒 {b["chip"]} {b["half"]}字节；计入封装内引线后组内差 {f1(b["elec_spread"])}，要补 {f1(b["tune_total"])}</small>'
        row(f"字节组 {k} 线长，最短 / 中位 / 最长 mm", fb)
    row("数据线要补的蛇形合计", lambda m: f'{sum(b["tune_total"] for b in m["bytes"]):.0f} mm')
    row("主干（SoC 球到分叉点），中位 / 最长", lambda m: f'{f1(m["t_sum"]["trunk_med"])} / {f1(m["t_sum"]["trunk_max"])} mm')
    row("分支（分叉点到颗粒球），中位 / 最长", lambda m: f'{f1(m["t_sum"]["branch_med"])} / {f1(m["t_sum"]["branch_max"])} mm')
    row("分支超过 600 mil（15.24 mm）的网络", lambda m: (f'<b class="bad">{m["t_sum"]["over"]} / {m["t_sum"]["n"]}</b>' if m["t_sum"]["over"] else f'0 / {m["t_sum"]["n"]}'))
    row("两分支天然的差，中位 / 最大（要补到 0.25 mm 内）", lambda m: f'{f1(m["t_sum"]["mis_med"])} / {f1(m["t_sum"]["mis_max"])} mm')
    row("地址控制整条路径（含封装内引线），最短–最长", lambda m: f'{f1(m["t_sum"]["path_min"])}–{f1(m["t_sum"]["path_max"])} mm')
    row("CK：主干 / 分支 A / 分支 B", lambda m: f'{f1(m["ck"]["trunk"])} / {f1(m["ck"]["ba"])} / {f1(m["ck"]["bb"])} mm')
    EVB1 = ["45.4 × 30.2 mm", "1371 mm²", "28.8 × 29.9 mm（仅 DDR 信号铜）", "5.4 / 7.9 mm", "12.6 / 14.2 / 23.0", "12.7 / 14.2 / 23.7", "20.2 / 22.0 / 26.8", "11.1 / 14.7 / 19.1",
            "没有蛇形，靠绕远", "22.0 / 29.9 mm", "10.6 / 13.9 mm", "0 / 21", "0.06 / 0.31 mm", "24.3–43.8 mm（不含封装内引线）", "8.6 / 15.6 / 16.0 mm"]
    rows[:] = [r.replace("</tr>", f'<td class="ref">{e}</td></tr>') for r, e in zip(rows, EVB1)]
    head = "".join(f'<th scope="col">{v.title.split("　")[0]}<small>{v.title.split("　")[1]}</small></th>' for v in VARIANTS) + '<th scope="col">官方 EVB1 实测<small>走完的线长，DDR4</small></th>'
    tabs = "".join(f'<button type="button" id="tab-{v.key}" data-k="{v.key}" aria-pressed="{"true" if i == 0 else "false"}">{v.title.split("　")[0]}<small>{v.title.split("　")[1]}</small></button>' for i, v in enumerate(VARIANTS))
    panels = "".join(
        f'<section class="panel" id="p-{v.key}"{"" if i == 0 else " hidden"}><h2>{v.title}</h2><p class="blurb">{v.blurb}</p>'
        f'<div class="fig">{svg(v, m)}</div><ul class="notes">{"".join(f"<li>{n}</li>" for n in v.notes)}</ul></section>'
        for i, (v, m) in enumerate(zip(VARIANTS, ms)))
    return TEMPLATE.replace("{{TABS}}", tabs).replace("{{PANELS}}", panels).replace("{{HEAD}}", head).replace("{{ROWS}}", "\n".join(rows)).replace("{{FACTS}}", FACTS)


FACTS = ""
TEMPLATE = (HERE / "page.tmpl.html").read_text(encoding="utf-8") if (HERE / "page.tmpl.html").exists() else "{{TABS}}{{PANELS}}<table><tr><th></th>{{HEAD}}</tr>{{ROWS}}</table>{{FACTS}}"

if __name__ == "__main__":
    facts = HERE / "facts.html"
    if facts.exists():
        FACTS = facts.read_text(encoding="utf-8")
    ms = [v.analyse() for v in VARIANTS]
    (HERE / "placement_variants.html").write_text(page(ms), encoding="utf-8")
    slim = [{k: v for k, v in m.items() if k not in ("lines",)} for m in ms]
    (HERE / "metrics.json").write_text(json.dumps(slim, ensure_ascii=False, indent=1), encoding="utf-8")
    for m in ms:
        print(f'\n== {m["title"]}\n  bbox {m["w"]:.1f} x {m["h"]:.1f} = {m["area"]:.0f} mm2 ; DDR span {m["ddr_w"]:.1f} x {m["ddr_h"]:.1f} ; gap A {m["gap"]["A"]:.2f} B {m["gap"]["B"]:.2f}')
        for b in m["bytes"]:
            print(f'  byte {b["byte"]} -> {b["chip"]} {b["half"]}: pcb {b["pcb_min"]:.1f}/{b["pcb_med"]:.1f}/{b["pcb_max"]:.1f} spread(+pkg) {b["elec_spread"]:.1f} tune {b["tune_total"]:.1f}')
        t = m["t_sum"]
        print(f'  T: trunk med {t["trunk_med"]:.1f} max {t["trunk_max"]:.1f} ; branch med {t["branch_med"]:.1f} max {t["branch_max"]:.1f} over {t["over"]}/{t["n"]} ; mismatch med {t["mis_med"]:.2f} max {t["mis_max"]:.2f} ; path {t["path_min"]:.1f}-{t["path_max"]:.1f}')
        print(f'  CK trunk {m["ck"]["trunk"]:.1f} branches {m["ck"]["ba"]:.1f}/{m["ck"]["bb"]:.1f} split {m["ck"]["split"]}')
