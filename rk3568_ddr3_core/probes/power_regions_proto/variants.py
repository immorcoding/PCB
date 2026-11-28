"""PROTOTYPE (issue 52): the candidate L3 partitions, drawn by hand.

Vertices are in ball pitches (k = mm / 0.65) from the SoC centre, x east, y south; 'N' 'E' 'S' 'W' stand for the
assumed board edges. Inside the ball field every border runs on a line of ball-gap points (integer k), i.e. on a
row of via sites: draw.py pulls each block back by half the gap from the drawn border, so two blocks that share
a border end up `gap` apart with that row of via sites in the gap, and the via rows next to it keep their pads
fully inside the copper. Only 0 / 45 / 90 degree edges (PWR-3).
"""
N, E, S, W = "N", "E", "S", "W"

# ---- the partition of the ball field, shared by all variants (it follows from where the balls are) --------------
#   VCC_DDR : rows H-J west of column 15, columns 9-10 down to row M        -> everything north-west
#   VDD_CPU : J15, K15-K18, L15-L18, M17 (notch)                            -> north-east
#   VDD_NPU : M19, N19, P18-P20                                             -> east
#   VDD_LOGIC: columns 12-13 (rows L-T) and column 16 (rows N-T), joined over the ground balls of the centre
#   VDD_GPU : R13, T13, U11-U13                                             -> south
CORE_DDR = [(1, -6), (0, -6), (0, -5), (-4, -5), (-4, -2)]            # from its east border down to its south-west end
CORE_CPU_W = [(-1, -3), (-1, -5), (0, -5), (0, -6), (1, -6)]          # CPU west side, south to north
CORE_CPU_S = [(4, -3), (4, -2), (1, -2), (1, -3), (-1, -3)]           # CPU south side with the M17 notch, east to west
CORE_LOGIC_N = [(-4, -5), (-1, -5), (-1, -3), (1, -3), (1, -2), (3, -2), (3, 1)]
CORE_GPU = [(-4, 2), (-2, 2), (-2, 0), (0, 0)]                        # GPU's border with LOGIC, west to east

V1 = {
    "key": "near",
    "title": "方案 1　就近出边",
    "blurb": "五路大电源各自朝最近的空边直出：VCC_DDR 占西北（两颗颗粒和 SoC 的 DDR 球在同一块里，到北边和西边），"
             "VDD_CPU 向东北，VDD_NPU 向东，VDD_LOGIC 向东南，VDD_GPU 向南。L3 余下的西南角铺地。"
             "17 路小电源不在 L3 上分块：球的过孔到背面电容，再照官方 EVB1 的做法从 L4 走线出球区（图上的虚线只表示方向和长度）。",
    "regions": [
        ("VCC_DDR", "L3", [(W, N), (7, N), (7, -16.5), (1, -16.5)] + CORE_DDR + [(-20, -2), (-22, 0), (-22, 3), (W, 3)]),
        ("VDD_CPU", "L3", [(7, N), (E, N), (E, -8), (19, -8), (14, -3)] + CORE_CPU_S + CORE_CPU_W[1:] + [(1, -16.5), (7, -16.5)]),
        ("VDD_NPU", "L3", [(4, -3), (14, -3), (19, -8), (E, -8), (E, 1), (3, 1), (3, -2), (4, -2)]),
        ("VDD_LOGIC", "L3", CORE_LOGIC_N + [(E, 1), (E, S), (0, S), (0, 0), (-2, 0), (-2, 2), (-4, 2)]),
        ("VDD_GPU", "L3", CORE_GPU + [(0, S), (-12, S), (-12, 25), (-4, 17)]),
    ],
    "rest": "GND",
    "small": "l4",              # small rails: L4 tracks out of the ball field, as on EVB1
    "entry": {"VCC_DDR": "北边、西边", "VDD_CPU": "北边东段、东边北段", "VDD_NPU": "东边", "VDD_LOGIC": "东边南段、南边东段", "VDD_GPU": "南边"},
}

# variant 2: everything arrives from the south-east corner (where a PMIC would sit on the full board, diagonally
# opposite the DRAM corner); small rails get landing strips on L3 outside the SoC, grouped by voltage
V2 = {
    "key": "diag",
    "title": "方案 2　朝东南角汇聚，小电源在球区外落到 L3",
    "blurb": "按完整板子上 PMIC 放在东南角（DDR 的对角）来画：五路大电源都从东边和南边进来，VCC_DDR 多一条沿西边下到南边的带子；"
             "东北角和西南角不再给大电源。小电源出球区后在东侧、南侧各落到一条 L3 的窄条上（按电压分组），球区内仍是 L4 走线，出了规则区就打孔落到窄条上。",
    "regions": [
        ("VCC_DDR", "L3", [(W, N), (7, N), (7, -16.5), (1, -16.5)] + CORE_DDR + [(-20, -2), (-22, 0), (-22, 3), (-30, 3), (-30, S), (W, S)]),
        ("VDD_CPU", "L3", [(1, -16.5), (7, -16.5), (10, -19.5), (E, -19.5), (E, -8), (19, -8), (14, -3)] + CORE_CPU_S + CORE_CPU_W[1:]),
        ("VDD_NPU", "L3", [(4, -3), (14, -3), (19, -8), (E, -8), (E, 1), (3, 1), (3, -2), (4, -2)]),
        ("VDD_LOGIC", "L3", CORE_LOGIC_N + [(17, 1), (17, 8), (E, 8), (E, S), (8, S), (8, 17), (0, 9), (0, 0), (-2, 0), (-2, 2), (-4, 2)]),
        ("VDD_GPU", "L3", CORE_GPU + [(0, 9), (8, 17), (8, S), (-4, S)]),
        # landing strips outside the SoC rule area (k > 16.2)
        ("VDDA_0V9", "L3", [(17, 1), (E, 1), (E, 4.5), (17, 4.5)]),
        ("VCCA_1V8", "L3", [(17, 4.5), (E, 4.5), (E, 8), (17, 8)]),
        ("VCC_3V3", "L3", [(-12, 17), (-4, 17), (-4, S), (-12, S)]),
        ("VCC_1V8", "L3", [(-20, 17), (-12, 17), (-12, S), (-20, S)]),
    ],
    "rest": "GND",
    "small": "strips",
    "entry": {"VCC_DDR": "南边西端（沿西边上来）", "VDD_CPU": "东边北段", "VDD_NPU": "东边", "VDD_LOGIC": "东边南段、南边东段", "VDD_GPU": "南边",
              "VDDA_0V9": "东边", "VCCA_1V8": "东边", "VCC_3V3": "南边", "VCC_1V8": "南边"},
}

VARIANTS = [V1, V2]
