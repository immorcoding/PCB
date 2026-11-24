"""The rule fixture cases of this board (Tools.KiCadDesignTools.rules.fixture, RUL-2): for every rule of
stm32h743_sdram.kicad_dru a case that breaks it and one that obeys it, and what is measured instead of DRC.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.rules.fixture stm32h743_sdram <out dir>

build(f, cfg) places the objects on the fixture board f (layers by L name, mm); a case's expected violations per
phase are {(violation type, rule name or None)}: static = the hand-written rules only, window = after len_rules.
"""

MCU = (10, 10, 22, 22)        # rule area BGA_MCU, x1 y1 x2 y2
RAM = (30, 10, 40, 25)        # rule area BGA_SDRAM


def build(f, cfg):
    f.edge((0, 0, 110, 150))
    f.area("BGA_MCU", MCU); f.area("BGA_SDRAM", RAM)
    W, C = "track_width", "clearance"
    X = 50.0                                  # x of the cases outside the rule areas

    # ---- track width
    f.case("w01", "默认类 0.2032 在区外"); f.trk("N1", (X, 30), (X + 8, 30), 0.2032)
    f.case("w02", "默认类 0.09 在区外：低于 0.1016", {(W, "signal_width")}); f.trk("N2", (X, 31), (X + 8, 31), 0.09)
    f.case("w03", "0.09 整段在 MCU 区内"); f.trk("N3", (12, 12), (16, 12), 0.09)
    f.case("w04", "0.1016 整段在 MCU 区内：区内只能 0.09", {(W, "bga_width_inside")}); f.trk("N4", (12, 13), (16, 13), 0.1016)
    f.case("w05", "0.09 跨过 MCU 区的边"); f.trk("N5", (20, 14), (23, 14), 0.09)
    f.case("w06", "0.09 出区 0.3 mm 后换成 0.1016（脚本的换宽做法）")
    f.trk("N6", (19, 15), (22.3, 15), 0.09); f.trk("N6", (22.3, 15), (26, 15), 0.1016)
    f.case("w07", "PWR 类 0.127 在区外：低于 0.1524", {(W, "pwr_width")}); f.trk("+3V3", (X, 32), (X + 8, 32), 0.127)
    f.case("w08", "PWR 类 0.3 整段在 MCU 区内（电源线在区内不限 0.09）"); f.trk("+3V3", (12, 16), (16, 16), 0.3)
    f.case("w09", "晶振线 0.254 从区内直接出区"); f.trk("HSE_IN", (10.6, 18), (8, 18), 0.254)
    f.case("w10", "晶振线 0.2 在区内：晶振线固定 0.254，没有区内例外", {(W, "xtal_width")}); f.trk("HSE_OUT", (12, 19), (16, 19), 0.2)
    f.case("w11", "默认类 1.0 在区外：超过 0.8128", {(W, "signal_width")}); f.trk("N7", (X, 33.5), (X + 8, 33.5), 1.0)
    f.case("w12", "0.09 整段在 SDRAM 区内"); f.trk("N8", (32, 12), (36, 12), 0.09)
    f.case("w13", "0.1016 整段在 SDRAM 区内", {(W, "bga_width_inside")}); f.trk("N9", (32, 13), (36, 13), 0.1016)
    f.case("w14", "总线类（RMII）0.1016 在区外"); f.trk("RMII_TX_EN", (X, 35), (X + 8, 35), 0.1016)
    f.case("w15", "总线类（RMII）0.09 在区外", {(W, "bus_width")}); f.trk("RMII_TX_EN", (X, 36), (X + 8, 36), 0.09)

    f.case("w16", "0.05 跨过 MCU 区的边：碰到规则区也不能低于 0.09", {(W, "bga_width")}); f.trk("N17", (20, 17), (23, 17), 0.05)
    # L3 (In2.Cu) is a signal layer since 2026-11-23: no rule names a layer, so a track there is checked as on L4 (In3.Cu)
    f.case("w17", "默认类 0.09 在 L3 区外：低于 0.1016（和 w18 的 L4 相同）", {(W, "signal_width")}); f.trk("N18", (X, 37), (X + 8, 37), 0.09, "L3")
    f.case("w18", "默认类 0.09 在 L4 区外：低于 0.1016", {(W, "signal_width")}); f.trk("N19", (X, 38), (X + 8, 38), 0.09, "L4")
    f.case("w19", "0.1016 整段在 MCU 区内、L3 上：区内只能 0.09", {(W, "bga_width_inside")}); f.trk("N70", (12, 14), (16, 14), 0.1016, "L3")

    # ---- vias
    D, H, A = "via_diameter", "drill_out_of_range", "annular_width"
    f.case("v01", "过孔 0.45 / 0.2 在区外"); f.via("N10", X, 40)
    f.case("v02", "小过孔 0.30 / 0.15 在区外", {(D, "via_size"), (H, "via_size"), (A, "via_size")}); f.via("N11", X + 2, 40, 0.30, 0.15)
    f.case("v03", "小过孔 0.30 / 0.15 整个在 MCU 区内"); f.via("N12", 12, 20, 0.30, 0.15)
    f.case("v04", "小过孔压在 MCU 区的边上：不算区内", {(D, "via_size"), (H, "via_size"), (A, "via_size")}); f.via("N13", 22.0, 20, 0.30, 0.15)
    f.case("v05", "0.25 / 0.15 在区内：小于批准的 0.30", {(D, "bga_via"), (A, "bga_via")}); f.via("N14", 14, 20, 0.25, 0.15)
    f.case("v06", "小过孔整个在 SDRAM 区内"); f.via("N15", 32, 20, 0.30, 0.15)
    f.case("v07", "0.30 / 0.10 在区内：孔小于 0.15", {(H, "bga_via")}); f.via("N16", 16, 20, 0.30, 0.10)

    # ---- clearance (edge to edge)
    def pair(na, nb, x, y, w, gap, length=4, layer="L1"):
        f.trk(na, (x, y), (x + length, y), w, layer); f.trk(nb, (x, y + w + gap), (x + length, y + w + gap), w, layer)
    f.case("c01", "区内两根 0.09 的线，间距 0.10"); pair("N20", "N21", 17, 11, 0.09, 0.10, 3)
    f.case("c02", "区内间距 0.08：低于 0.09", {(C, "bga_clearance")}); pair("N22", "N23", 17, 12, 0.09, 0.08, 3)
    f.case("c03", "区外间距 0.10：低于网络类的 0.127", {(C, "Default")}); pair("N24", "N25", X, 44, 0.1016, 0.10)
    f.case("c04", "区外间距 0.13"); pair("N26", "N27", X, 45, 0.1016, 0.13)
    f.case("c05", "L3 区外间距 0.10：低于网络类的 0.127（同 c03）", {(C, "Default")}); pair("N28", "N29", X, 46.5, 0.1016, 0.10, layer="L3")

    # ---- corners, short segments
    f.case("k01", "90° 拐角", {("track_angle", "corner_angle")})
    f.trk("N30", (X, 48), (X + 3, 48), 0.2); f.trk("N30", (X + 3, 48), (X + 3, 50), 0.2)
    f.case("k02", "45° 拐角")
    f.trk("N31", (X + 6, 48), (X + 9, 48), 0.2); f.trk("N31", (X + 9, 48), (X + 11, 50), 0.2)
    f.case("s01", "0.05 mm 的短线段", {("track_segment_length", "min_segment")})
    f.trk("N32", (X, 52), (X + 3, 52), 0.2); f.trk("N32", (X + 3, 52), (X + 3.05, 52), 0.2); f.trk("N32", (X + 3.05, 52), (X + 6, 52), 0.2)

    # ---- holes
    f.case("h01", "过孔的孔到内层走线 0.19（过孔在该层没有焊盘）：低于 0.2", {("hole_clearance", None)})
    f.via("N40", X, 56, strip_inner=True); f.trk("N41", (X - 2, 56 + 0.1 + 0.19 + 0.0508), (X + 2, 56 + 0.1 + 0.19 + 0.0508), 0.1016, "L4")
    f.case("h02", "过孔的孔到内层走线 0.21")
    f.via("N42", X + 6, 56, strip_inner=True); f.trk("N43", (X + 4, 56 + 0.1 + 0.21 + 0.0508), (X + 8, 56 + 0.1 + 0.21 + 0.0508), 0.1016, "L4")
    f.case("h08", "过孔的孔到 L3 走线 0.19（同 h01 的 L4）：低于 0.2", {("hole_clearance", None)})
    f.via("N71", X + 12, 56, strip_inner=True); f.trk("N72", (X + 10, 56 + 0.1 + 0.19 + 0.0508), (X + 14, 56 + 0.1 + 0.19 + 0.0508), 0.1016, "L3")
    f.case("h09", "过孔的孔到 L3 走线 0.21")
    f.via("N73", X + 18, 56, strip_inner=True); f.trk("N74", (X + 16, 56 + 0.1 + 0.21 + 0.0508), (X + 20, 56 + 0.1 + 0.21 + 0.0508), 0.1016, "L3")
    f.case("h03", "插件孔（孔 1.0、盘 1.2）到走线 0.25：插件孔要 0.3", {("hole_clearance", "pth_hole_clearance")})
    f.pad("H3", "N44", X, 60, 1.2, 1.0); f.trk("N45", (X - 2, 60 + 0.5 + 0.25 + 0.0508), (X + 2, 60 + 0.5 + 0.25 + 0.0508), 0.1016)
    f.case("h04", "插件孔到走线 0.32")
    f.pad("H4", "N46", X + 6, 60, 1.2, 1.0); f.trk("N47", (X + 4, 60 + 0.5 + 0.32 + 0.0508), (X + 8, 60 + 0.5 + 0.32 + 0.0508), 0.1016)
    f.case("h05", "两个插件孔孔边到孔边 0.40：低于 0.45", {("hole_to_hole", "pth_hole_to_hole")})
    f.pad("H5A", "N48", X, 64, 1.2, 1.0); f.pad("H5B", "N48", X + 1.4, 64, 1.2, 1.0)
    f.case("h06", "两个插件孔孔边到孔边 0.50")
    f.pad("H6A", "N49", X + 6, 64, 1.2, 1.0); f.pad("H6B", "N49", X + 7.5, 64, 1.2, 1.0)

    f.case("h07", "孔径 3.5 mm：超过 3.3", {("drill_out_of_range", "hole_range")}); f.pad("H7", "N50", X + 14, 62, 5.0, 3.5)

    # ---- Ethernet pair (width and gap of the project's pair, board.toml [project.diff_pairs.ETH])
    eth = cfg.need("project.diff_pairs.ETH")
    ew, eg = eth["width"], eth["gap"]
    f.case("e01", "差分对 %g / %g，两根等长" % (ew, eg)); pair("ETH_TX_P", "ETH_TX_N", X, 68, ew, eg, 10)
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

    # ---- pour on L6 over the whole board, clearance 0.2: distance to tracks, pad connections
    f.case("z00", "整板铺地（L6，间距 0.2），盖住两个规则区")
    f.pour("GND", "L6", (1, 1, 109, 149), 0.2)
    f.case("z01", "区外的走线到铺地"); f.trk("N60", (70, 20), (80, 20), 0.2, "L6")
    f.case("z02", "MCU 区内的走线到铺地"); f.trk("N61", (12, 21), (18, 21), 0.09, "L6")
    f.case("z03", "接地的插件焊盘：花焊盘"); f.pad("Z3", "GND", 70, 26, 1.7, 1.0)
    f.case("z04", "接地的贴片焊盘（L6）：全连接"); f.pad("Z4", "GND", 78, 26, 1.5, layer="L6")


# ---- what DRC cannot report, measured on the filled fixture board
POUR_LAYER = "L6"                                    # the layer of the pour above (z00)
# first copper beyond a track's edge: (case, (x, y, track width) on the track), accepted range mm, note
POUR_GAPS = [("z01", (75, 20, 0.2)), ("z02", (15, 21, 0.09))]
POUR_GAP_RANGE = (0.19, 0.22)
POUR_GAP_NOTE = "铺铜区设 0.2；规则区的 0.09 不该用到铺铜上"
# pour connection of a pad: (case, (x, y, pad radius), "thermal" | "solid")
PAD_CONNECTIONS = [("z03", (70, 26, 0.85), "thermal"), ("z04", (78, 26, 0.75), "solid")]
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
# rules proven by a measurement above instead of a violation (left out of "rules no case triggered")
MEASURED_RULES = {"tht_thermal", "smd_solid"}
