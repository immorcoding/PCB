"""PROTOTYPE (issue 21) variant _bundle_demo: NOT a candidate, only the proof that lib/bundle.py works.

The eight L1 nets (SDCLK and byte lane 1) are written as two bundles instead of eight coordinate lists:
  south   D11 D12 D8 D9: south out of the MCU, S -> SE -> E below the MCU, then they MERGE into the trunk
  trunk   SDCLK D15 D14 D13 D11 D12 D8 D9: E -> SE across the corridor -> E into the SDRAM rows
A third bundle on L6 (D6 D7 D5 D4, via to via) shows terminals on another layer. The other seven nets are
0_base's hand routes, kept as they are. Four tuning slots are filled with equal-height blocks.
The lengths are NOT brought into the window here (that is the variants' job).
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib"))
import board
from bundle import Bundle, Bus

DESCRIPTION = "演示（不是候选方案）：L1 的 8 根线用 lib/bundle.py 按线束生成，4 处等高蛇形；只为证明工具能用，没有把长度调进窗口。"

BASE, SWAP, BASE_WHY = board.base_routes("0_base")
L1_NETS = ["FMC_SDCLK", "FMC_D15", "FMC_D14", "FMC_D13", "FMC_D11", "FMC_D12", "FMC_D8", "FMC_D9"]   # lane order, north to south
L6_NETS = ["FMC_D6", "FMC_D7", "FMC_D5", "FMC_D4"]
PITCH = {"default": 0.3, "SDCLK": 0.5}
VIEWS = [("demo", 13.5, 11.5, 26.0, 22.5, 100), ("demo_south", 15.5, 17.5, 22.0, 21.5, 220)]

bus = Bus(SWAP)
bus.keep({n: r for n, r in BASE.items() if n not in L1_NETS + L6_NETS})

# ---- south: four lanes out of the MCU's south edge (0.325 apart there), 0.30 apart on the run below the MCU
#      (a lane that carries a serpentine needs 0.294 to the neighbour BEHIND the humps too: serpentine clearance 0.19)
south = Bundle("south", ["D11", "D12", "D8", "D9"], "L1", anchor="D11",
               path=[(15.275, 16.6), (15.275, 17.3), (16.275, 18.3), (21.0, 18.3)],
               pitch=0.30, gaps={0: 0.325, 1: 0.2298})
# room for serpentines on the east run (stations in mm from x = 16.275): D12, D8, D9 run 0.70 mm further south
# from the corner on (s0=None: no jog out) and come back at 3.6; D9 steps another 0.70 aside for D8's block
# and back (two jogs). The two blocks are staggered along the run.
south.widen(2, None, 3.6, after="D11", by=0.70)
south.widen(2, 1.75, 2.95, after="D8", by=0.70)
slot_d11 = south.slot("D11", 2, s0=0.45, length=1.3, side="R", pitch=0.3)
slot_d8 = south.slot("D8", 2, s0=1.75, length=1.2, side="R", pitch=0.3)
bus.add(south, start={"D11": ["U1", (15.275, 16.225)], "D12": "U1", "D8": ["U1", (14.625, 16.225)], "D9": "U1"})

# ---- trunk: D15 / D14 / D13 leave east at the ball pitch (leg 0), all eight share the diagonal (leg 1, 0.23)
#      and arrive on the SDRAM's rows (leg 2: gaps = the row pattern, so no fan is needed there)
trunk = Bundle("trunk", L1_NETS, "L1", anchor="D14",
               path=[(18.2, 15.575), (19.2, 15.575), (22.325, 18.7), (23.4, 18.7)],
               pitch=0.2298, gaps={0: 0.325, 1: [0.5, 0.3, 0.2298, 0.2298, 0.2298, 0.2298, 0.2298], 2: [1.2, 0.8, 0.8, 0.8, 0.4, 0.4, 0.4]},
               span={n: (1, 2) for n in ("SDCLK", "D11", "D12", "D8", "D9")})
slot_d14 = trunk.slot("D14", 1, s0=1.25, length=1.25, side="R", free=0.85, pitch=0.3)     # D13 steps aside
slot_clk = trunk.slot("SDCLK", 1, s0=0.2, length=1.2, side="L", pitch=0.5, amp_cap=1.0)   # outer lane, nothing to move
bus.add(trunk,
        start={"SDCLK": ["U1", (17.225, 12.325), (17.9, 12.325)], "D15": "U1", "D14": ["U1", (17.225, 15.575)], "D13": "U1"},
        end={"SDCLK": "U2", "D15": [(24.2, 17.9), "U2"], "D14": [(24.2, 18.7), "U2"], "D13": [(24.2, 19.5), "U2"],
             "D11": [(25.0, 20.3), "U2"], "D12": "U2", "D8": [(24.2, 21.1), "U2"], "D9": "U2"})

# ---- under: four lanes on L6 from vias in the MCU's south edge band to vias beside the SDRAM balls
under = Bundle("under", ["D6", "D7", "D5", "D4"], "L6", anchor="D6",
               path=[(13.975, 17.7), (13.975, 18.4), (15.475, 19.9), (27.0, 19.9)],
               pitch=0.3, gaps={0: 0.325, 2: [0.4, 0.8, 0.8]})
bus.add(under,
        start={"D6": {"pieces": [("L1", ["U1", (13.975, 16.225), (13.975, 17.7)])]}, "D7": {"pieces": [("L1", ["U1", (13.65, 17.3)])]},
               "D5": {"pieces": [("L1", ["U1", (13.325, 16.225), (13.325, 17.7)])]}, "D4": {"pieces": [("L1", ["U1", (13.0, 17.3)])]}},
        end={"D6": {"pieces": [("L1", [(28.0, 19.9), "U2"])]}, "D7": {"pieces": [("L1", [(29.8, 20.3), "U2"])]},
             "D5": {"pieces": [("L1", [(29.0, 21.1), "U2"])]}, "D4": {"pieces": [("L1", [(29.8, 21.9), "U2"])]}})

ROUTES = bus.routes()
print(bus.report())

# ---- serpentines: one equal-height block per slot (the height of the whole block is what is adjusted)
for s, kw in ((slot_d11, {"amp": 0.6}), (slot_d8, {"add": 1.6}), (slot_d14, {"amp": 0.5}), (slot_clk, {"amp": 0.9})):
    e = s.fill(**kw)
    print("  slot %-5s %s side %-2s  %d x %.3f mm  -> +%.3f mm" % (e["net"], e["layer"], e["side"], e["n"], e["amp"], e["gain"]))
TUNING = bus.tuning()

WHY = dict(BASE_WHY)
WHY.update({
    "FMC_SDCLK": "线束 trunk 的最外一根：从球向东出球区，一小段 45° 加一段向南的直线并到斜线束的最外侧，再沿 J 行直进 CLK 球；蛇形 1 个弯（腿间距 0.5），朝外侧（东北），旁边没有线要让。",
    "FMC_D15": "trunk 第 2 根：向东直出，在窄条里和 D14、D13 一起斜向东南，到 L 行上面的通道向东进 L2 球。",
    "FMC_D14": "trunk 的基准线（线束中心线就画在它上面）：斜穿窄条后直进 M 行上面的通道；窄条里放 2 个等高的弯，朝西南，D13 用两个 45° 折线让开。",
    "FMC_D13": "trunk 第 4 根：在窄条里向西南让出 D14 蛇形的位置，过了蛇形再折回来，进 N2 球。",
    "FMC_D11": "线束 south 的基准线：向南出 MCU，斜向东南后在 MCU 下方向东走，再并入 trunk 的斜线段；向东那一段上放 2 个等高的弯，朝南，D12、D8、D9 一起向南让开。",
    "FMC_D12": "south 第 2 根：跟着 D11 走，在 D11 的蛇形那一段向南让开 0.7 mm，之后折回并入 trunk，直进 P1 球。",
    "FMC_D8": "south 第 3 根：让开 D11 的蛇形以后自己也放 2 个等高的弯（朝南，D9 再让 0.7 mm），位置和 D11 的那一块前后错开。",
    "FMC_D9": "south 最外一根：先后为 D11、D8 的蛇形让两次，再分两次折回，并入 trunk 后直进 R1 球。",
    "FMC_D6": "线束 under（L6）第 1 根：走法和 0_base 相同，只是改由线束生成：MCU 下边打孔换 L6，向南、斜向东南、再向东到 N7 球旁的过孔。",
    "FMC_D7": "under 第 2 根，同 D6，到 P9 球。",
    "FMC_D5": "under 第 3 根，同 D6，到 R8 球。",
    "FMC_D4": "under 第 4 根，同 D6，到 R9 球。",
})
