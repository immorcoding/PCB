"""The rule fixture cases of the demo board's own rules (Tools.KiCadDesignTools.rules.fixture, RUL-2): bus_width,
sdram_len_max, sdram_via_max, sdram_lane0 and the generated sdram_addr_window, each broken once and obeyed once, and
what is measured instead of DRC. The profile's 15 rules are tested by templates/C-bga-065/rules_cases.py ([board]
template); the fixture calls the two hooks below from there, in its case order.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.rules.fixture templates/demo_board <out dir>

widths(f, cfg, X) and cases(f, cfg, X) place the objects on the fixture board f (layers by L name, mm; X: the x of the
cases outside the rule areas); a case's expected violations per phase are {(violation type, rule name or None)}:
static = the hand-written rules only, window = after len_rules.
"""
from Tools.KiCadDesignTools.core import stackup


def widths(f, cfg, X):
    W = "track_width"
    f.case("w14", "总线类（SDRAM）0.1016 在区外"); f.trk("FMC_BA0", (X, 35), (X + 8, 35), 0.1016)
    f.case("w15", "总线类（SDRAM）0.09 在区外", {(W, "bus_width")}); f.trk("FMC_BA0", (X, 36), (X + 8, 36), 0.09)


def cases(f, cfg, X):
    # ---- lengths and via counts. Every net is on its own rows from y = 80 down, x = 5.
    LEN, SK, VC = "length_out_of_range", "skew_out_of_range", "too_many_vias"
    h14 = stackup.for_board(cfg).via_height(cfg.kicad("L1"), cfg.kicad("L4"))
    y = 80.0
    def net_len(cid, what, net, length, static=(), window=None):
        nonlocal y
        f.case(cid, what, static, window)
        y = f.run(net, length, 5, y) + 0.5
    net_len("l01", "SDCLK 串阻前一段 3 mm", "FMC_SDCLK", 3)
    net_len("l02", "SDCLK 串阻后一段 17 mm（合计 20 mm，由 len_rules 报）", "FMC_SDCLK_R", 17)
    # byte lane 0: longest minus shortest <= 1.27 mm (SPEC 7.2)
    net_len("l03", "通道 0 数据线 24.5 mm：比本组最长的短 0.5 mm，不报", "FMC_D0", 24.5)
    net_len("l04", "通道 0 数据线 24 mm：比本组最长的短 1.0 mm，不报", "FMC_D1", 24)
    net_len("l05", "通道 0 的 NBL0 25 mm：本组最长，证明 NBL 在组里", "FMC_NBL0", 25)
    net_len("l06", "通道 0 数据线 23.5 mm：比本组最长的短 1.5 mm，超过 1.27 mm", "FMC_D2", 23.5, {(SK, "sdram_lane0")})
    # address lines against the clock (generated window: 20 +- 10 mm, cap 30)
    net_len("l0d", "地址线 31 mm：超过 30 mm；生成段的 sdram_addr_window（时钟 ± 10 mm，上限 30）压过 sdram_len_max", "FMC_A0", 31,
            {(LEN, "sdram_len_max")}, {(LEN, "sdram_addr_window")})
    net_len("l0k", "地址线 8 mm：比时钟（20 mm）短 12 mm：只有生成段时报", "FMC_A1", 8, (), {(LEN, "sdram_addr_window")})
    f.case("l0f", "地址线 14 mm 加 4 个 L1–L4 过孔（最后一个只接一层）：地址线不限过孔数；长度 14 + 3 × 过孔高度")
    for i in range(4):
        f.trk("FMC_A2", (5 + 3.5 * i, y), (5 + 3.5 * i + 3.5, y), 0.1016, "L1" if i % 2 == 0 else "L4")
        f.via("FMC_A2", 5 + 3.5 * i + 3.5, y, a="L1", c="L4")
    y += 1.5
    f.case("l0h", "地址线 14 mm 加 4 个通孔、L1–L3 换层（最后一个只接一层）：长度 14 + 3 × L1–L3 过孔高度（真板上的过孔都是通孔）")
    for i in range(4):
        f.trk("FMC_A3", (5 + 3.5 * i, y), (5 + 3.5 * i + 3.5, y), 0.1016, "L1" if i % 2 == 0 else "L3")
        f.via("FMC_A3", 5 + 3.5 * i + 3.5, y)
    y += 1.5
    # four L1-L4 vias on a lane net: too many (3 allowed); its length (4 pieces + 3 via heights) 24.3 mm keeps it in the lane
    t = (24.3 - 3 * h14) / 4
    f.case("l0g", "通道 0 数据线 4 个 L1–L4 过孔：超过 3 个（长度 24.3 mm，在本组 1.27 mm 之内）", {(VC, "sdram_via_max")})
    for i in range(4):
        f.trk("FMC_D3", (5 + t * i, y), (5 + t * i + t, y), 0.1016, "L1" if i % 2 == 0 else "L4")
        f.via("FMC_D3", 5 + t * i + t, y, a="L1", c="L4")
    y += 1.5
    # FMC_BA0 carries the 16 mm of w14 / w15: inside the window, no report


# ---- what DRC cannot report, measured on the filled fixture board
VIA_LENGTHS = [
    ("l0f", "FMC_A2", 14, 3, ("L1", "L4"), "换层的过孔按 L1–L4 的高度计入，只接一层的不计"),
    ("l0h", "FMC_A3", 14, 3, ("L1", "L3"), "通孔在 L1–L3 换层只计 L1–L3 的高度，不是整板 {whole:.4f}"),
]
LEN_RULES = [
    (("sdclk_total: 20.0000 mm",), None, "len_rules 把 SDCLK 串阻两侧相加得 20 mm"),
]
