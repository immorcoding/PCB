"""The rule fixture cases of this board's own rules (Tools.KiCadDesignTools.rules.fixture, RUL-2): for every rule of
stm32h743_sdram.kicad_dru that is not the profile's a case that breaks it and one that obeys it, and what is measured
instead of DRC. The profile's 15 rules are tested by templates/C-bga-065/rules_cases.py ([board] template); the
fixture calls the two hooks below from there, in its case order.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.rules.fixture stm32h743_sdram <out dir>

widths(f, cfg, X) and cases(f, cfg, X) place the objects on the fixture board f (layers by L name, mm; X: the x of the
cases outside the rule areas); a case's expected violations per phase are {(violation type, rule name or None)}:
static = the hand-written rules only, window = after len_rules.
"""

# this board's wording of a profile case: L3 became a signal layer here on 2026-11-23
WHAT = {"w17": "默认类 0.09 在 L3 区外：低于 0.1016（和 w18 的 L4 相同）"}


def widths(f, cfg, X):
    W = "track_width"
    f.case("w14", "总线类（RMII）0.1016 在区外"); f.trk("RMII_TX_EN", (X, 35), (X + 8, 35), 0.1016)
    f.case("w15", "总线类（RMII）0.09 在区外", {(W, "bus_width")}); f.trk("RMII_TX_EN", (X, 36), (X + 8, 36), 0.09)


def cases(f, cfg, X):
    W = "track_width"
    # ---- Ethernet pair (width and gap of the project's pair, board.toml [project.diff_pairs.ETH])
    eth = cfg.need("project.diff_pairs.ETH")
    ew, eg = eth["width"], eth["gap"]
    f.case("e01", "差分对 %g / %g，两根等长" % (ew, eg)); f.pair("ETH_TX_P", "ETH_TX_N", X, 68, ew, eg, 10)
    f.case("e02", "差分对：对内间距 0.14、对内差 2 mm、另有一段线宽 0.15",
           {(W, "eth_width"), ("skew_out_of_range", "eth_skew"), ("diff_pair_gap_out_of_range", "eth_gap")})
    f.trk("ETH_RX_P", (X, 70), (X + 10, 70), ew); f.trk("ETH_RX_N", (X, 70 + ew + 0.14), (X + 13, 70 + ew + 0.14), ew)
    f.trk("ETH_RX_P", (X, 72), (X + 1, 72), 0.15)

    # ---- lengths and via counts. Every net is on its own rows from y = 80 down, x = 5.
    LEN, SK, VC = "length_out_of_range", "skew_out_of_range", "too_many_vias"
    y = 80.0
    def net_len(cid, what, net, length, static=(), window=None):
        nonlocal y
        f.case(cid, what, static, window)
        y = f.run(net, length, 5, y) + 0.5
    net_len("l01", "SDCLK 串阻前一段 3 mm", "FMC_SDCLK", 3)
    net_len("l02", "SDCLK 串阻后一段 17 mm（合计 20 mm，由脚本报）", "FMC_SDCLK_R", 17)
    # byte lanes: longest minus shortest <= 1.27 mm (user 2026-11-24, 50 mil; 20 mm from 2026-11-23, 5 mm before)
    net_len("l03", "通道 0 数据线 24.5 mm：比本组最长的短 0.5 mm，在 1.27 mm 之内，不报", "FMC_D0", 24.5)
    net_len("l04", "通道 0 数据线 24 mm：比本组最长的短 1.0 mm，在 1.27 mm 之内，不报", "FMC_D1", 24)
    net_len("l05", "通道 0 的 NBL0 25 mm：本组最长，证明 NBL 在组里", "FMC_NBL0", 25)
    net_len("l06", "通道 0 数据线 23.5 mm：比本组最长的短 1.5 mm，超过 1.27 mm", "FMC_D2", 23.5, {(SK, "sdram_lane0")})
    net_len("l07", "通道 1 数据线 35 mm：比通道 0 最长的长 10 mm，不同组不比", "FMC_D8", 35)
    net_len("l08", "通道 1 数据线 34 mm：比本组最长的短 1.0 mm，在 1.27 mm 之内，不报", "FMC_D9", 34)
    net_len("l0n", "通道 1 数据线 33.5 mm：比 D8 短 1.5 mm，超过 1.27 mm", "FMC_D11", 33.5, {(SK, "sdram_lane1")})
    net_len("l09", "通道 2 数据线 30.5 mm：比 D17 短 1.5 mm，超过 1.27 mm", "FMC_D16", 30.5, {(SK, "sdram_lane2")})
    net_len("l0a", "通道 2 数据线 32 mm：本组最长，不报", "FMC_D17", 32)
    net_len("l0p", "通道 2 数据线 31 mm：比 D17 短 1.0 mm，在 1.27 mm 之内，不报", "FMC_D18", 31)
    net_len("l0b", "通道 3 的 NBL3 40 mm", "FMC_NBL3", 40)
    net_len("l0c", "通道 3 数据线 38.5 mm：比 NBL3 短 1.5 mm，超过 1.27 mm", "FMC_D24", 38.5, {(SK, "sdram_lane3")})
    net_len("l0o", "通道 3 数据线 39 mm：比 NBL3 短 1.0 mm，在 1.27 mm 之内，不报", "FMC_D25", 39)
    net_len("l0d", "地址线 61 mm：超过 60 mm；生成段的 sdram_addr_window（时钟 ± 20 mm，上限仍 60）压过 sdram_len_max", "FMC_A0", 61,
            {(LEN, "sdram_len_max")}, {(LEN, "sdram_addr_window")})
    net_len("l0e", "地址线 8 mm：比时钟（20 mm）短 12 mm，在 20 mm 之内，不报", "FMC_A1", 8)
    net_len("l0k", "地址线 41 mm：比时钟长 21 mm：只有生成段时报（用户 2026-11-23 定 ± 20 mm）", "FMC_A4", 41, (), {(LEN, "sdram_addr_window")})
    net_len("l0l", "命令线 SDNWE 39 mm：比时钟长 19 mm，不报（命令线也在组里，见 l0m）", "FMC_SDNWE", 39)
    net_len("l0m", "命令线 SDCKE0 42 mm：比时钟长 22 mm，生成段报", "FMC_SDCKE0", 42, (), {(LEN, "sdram_addr_window")})
    f.case("l0f", "地址线 14 mm 加 4 个 L1–L4 过孔（最后一个只接一层）：地址线不限过孔数；长度 14 + 3 × 过孔高度")
    for i in range(4):
        f.trk("FMC_A2", (5 + 3.5 * i, y), (5 + 3.5 * i + 3.5, y), 0.1016, "L1" if i % 2 == 0 else "L4")
        f.via("FMC_A2", 5 + 3.5 * i + 3.5, y, a="L1", c="L4")
    y += 1.5
    net_len("l10", "QSPI 时钟 20 mm", "QSPI_CLK", 20)
    net_len("l11", "QSPI IO 22 mm", "QSPI_BK1_IO0", 22)
    net_len("l12", "QSPI IO 26 mm：比时钟长 6 mm", "QSPI_BK1_IO1", 26, (), {(LEN, "qspi_window")})
    net_len("l13", "QSPI IO 31 mm：超过 30 mm", "QSPI_BK1_IO2", 31, {(LEN, "qspi_len_max")}, {(LEN, "qspi_window")})
    net_len("l14", "QSPI 片选 35 mm：不限等长，也不限长度（用户 2026-11-23）：只有手写段时报 qspi_len_max，生成段的 qspi_ncs_no_cap 压过它", "QSPI_BK1_NCS", 35, {(LEN, "qspi_len_max")}, set())
    net_len("l20", "SD 时钟 20 mm", "SDMMC1_CK", 20)
    net_len("l21", "SD 数据 22 mm", "SDMMC1_D0", 22)
    net_len("l22", "SD 数据 19 mm：比时钟短", "SDMMC1_D1", 19, (), {(LEN, "sdmmc_window")})
    net_len("l23", "SD 命令 26 mm：比时钟长 6 mm", "SDMMC1_CMD", 26, (), {(LEN, "sdmmc_window")})
    net_len("l30", "RMII 时钟 41 mm：超过 40 mm", "RMII_REF_CLK", 41, {(LEN, "rmii_refclk_len_max")})
    net_len("l31", "RMII RXD0 40 mm：比时钟短", "RMII_RXD0", 40, (), {(LEN, "rmii_rx_min")})
    net_len("l32", "RMII RXD1 42 mm", "RMII_RXD1", 42)
    net_len("l33", "RMII TXD0 61 mm：超过 60 mm（另：时钟加最长 TXD = 102 > 100，由脚本报）", "RMII_TXD0", 61, {(LEN, "rmii_len_max")})
    net_len("l34", "RMII TXD1 59 mm", "RMII_TXD1", 59)
    net_len("l40", "LTDC 100 mm", "LCD_R3", 100)
    net_len("l41", "LTDC 121 mm：超过 120 mm", "LCD_R4", 121, {(LEN, "ltdc_len_max")})
    net_len("l42", "LTDC 75 mm：比最长的（R4 121 mm）短 46 mm：只有手写段时报 ltdc_spread（30），生成段的 ltdc_spread_60（用户 2026-11-23 按电气值定 60 mm）压过它，不报", "LCD_R5", 75, {(SK, "ltdc_spread")}, set())
    net_len("l44", "LTDC 60 mm：比最长的（R4 121 mm）短 61 mm：手写段报 ltdc_spread（30），生成段的 ltdc_spread_60 也报", "LCD_R7", 60, {(SK, "ltdc_spread")}, {(SK, "ltdc_spread_60")})
    f.case("l0g", "通道 1 数据线 4 个 L1–L4 过孔：超过 3 个（长度 30.4 + 3 × 过孔高度 = 34.58，比 D8 短 0.42，在通道 1 的 1.27 mm 之内）", {(VC, "sdram_via_max")})
    for i in range(4):
        f.trk("FMC_D10", (5 + 7.6 * i, y), (5 + 7.6 * i + 7.6, y), 0.1016, "L1" if i % 2 == 0 else "L4")
        f.via("FMC_D10", 5 + 7.6 * i + 7.6, y, a="L1", c="L4")
    y += 1.5
    f.case("l43", "LTDC 4 个过孔：不限过孔数")
    for i in range(4):
        f.trk("LCD_R6", (5 + 25 * i, y), (5 + 25 * i + 25, y), 0.1016, "L1" if i % 2 == 0 else "L6")
        f.via("LCD_R6", 5 + 25 * i + 25, y)
    y += 1.5
    f.case("l0h", "地址线 14 mm 加 4 个通孔、L1–L3 换层（最后一个只接一层）：长度 14 + 3 × L1–L3 过孔高度（真板上的过孔都是通孔）")
    for i in range(4):
        f.trk("FMC_A3", (5 + 3.5 * i, y), (5 + 3.5 * i + 3.5, y), 0.1016, "L1" if i % 2 == 0 else "L3")
        f.via("FMC_A3", 5 + 3.5 * i + 3.5, y)
    y += 1.5


# ---- what DRC cannot report, measured on the filled fixture board
# via height KiCad adds to a net length: (case, net, track length mm, vias counted, layer pair, note). {whole} in the
# note: the via height through the whole board.
VIA_LENGTHS = [
    ("l0f", "FMC_A2", 14, 3, ("L1", "L4"), "换层的过孔按 L1–L4 的高度计入，只接一层的不计"),
    ("l0h", "FMC_A3", 14, 3, ("L1", "L3"), "通孔在 L1–L3 换层只计 L1–L3 的高度，不是整板 {whole:.4f}"),
]
# what len_rules must report on the fixture (its script-only checks): (texts its output must hold, exit code or None, line)
LEN_RULES = [
    (("rmii_refclk_plus_longest_txd: 102.0000 mm", "超出 2.0000"), 1, "len_rules.py 报出时钟加最长 TXD 超出 100 mm（故意的）"),
    (("sdclk_total: 20.0000 mm",), None, "len_rules.py 把 SDCLK 串阻两侧相加得 20 mm"),
]
