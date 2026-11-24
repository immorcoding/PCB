"""The rule fixture cases of the demo board (Tools.KiCadDesignTools.rules.fixture, RUL-2): for every rule of
demo_board.kicad_dru a case that breaks it and one that obeys it, and what is measured instead of DRC.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.rules.fixture templates/demo_board <out dir>

build(f, cfg) places the objects on the fixture board f (layers by L name, mm); a case's expected violations per
phase are {(violation type, rule name or None)}: static = the hand-written rules only, window = after len_rules.
The profile's 15 rules are tested as on the H743 board (stm32h743_sdram/rules_cases.py, the same cases); the board's
own: bus_width, sdram_len_max, sdram_via_max, sdram_lane0 and the generated sdram_addr_window.
"""
from Tools.KiCadDesignTools.core import stackup

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
    f.case("w14", "总线类（SDRAM）0.1016 在区外"); f.trk("FMC_BA0", (X, 35), (X + 8, 35), 0.1016)
    f.case("w15", "总线类（SDRAM）0.09 在区外", {(W, "bus_width")}); f.trk("FMC_BA0", (X, 36), (X + 8, 36), 0.09)
    f.case("w16", "0.05 跨过 MCU 区的边：碰到规则区也不能低于 0.09", {(W, "bga_width")}); f.trk("N17", (20, 17), (23, 17), 0.05)
    f.case("w17", "默认类 0.09 在 L3 区外：低于 0.1016", {(W, "signal_width")}); f.trk("N18", (X, 37), (X + 8, 37), 0.09, "L3")
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

    # ---- pour on L6 over the whole board, clearance 0.2: distance to tracks, pad connections
    f.case("z00", "整板铺地（L6，间距 0.2），盖住两个规则区")
    f.pour("GND", "L6", (1, 1, 109, 149), 0.2)
    f.case("z01", "区外的走线到铺地"); f.trk("N60", (70, 20), (80, 20), 0.2, "L6")
    f.case("z02", "MCU 区内的走线到铺地"); f.trk("N61", (12, 21), (18, 21), 0.09, "L6")
    f.case("z03", "接地的插件焊盘：花焊盘"); f.pad("Z3", "GND", 70, 26, 1.7, 1.0)
    f.case("z04", "接地的贴片焊盘（L6）：全连接"); f.pad("Z4", "GND", 78, 26, 1.5, layer="L6")


# ---- what DRC cannot report, measured on the filled fixture board
POUR_LAYER = "L6"
POUR_GAPS = [("z01", (75, 20, 0.2)), ("z02", (15, 21, 0.09))]
POUR_GAP_RANGE = (0.19, 0.22)
POUR_GAP_NOTE = "铺铜区设 0.2；规则区的 0.09 不该用到铺铜上"
PAD_CONNECTIONS = [("z03", (70, 26, 0.85), "thermal"), ("z04", (78, 26, 0.75), "solid")]
VIA_LENGTHS = [
    ("l0f", "FMC_A2", 14, 3, ("L1", "L4"), "换层的过孔按 L1–L4 的高度计入，只接一层的不计"),
    ("l0h", "FMC_A3", 14, 3, ("L1", "L3"), "通孔在 L1–L3 换层只计 L1–L3 的高度，不是整板 {whole:.4f}"),
]
LEN_RULES = [
    (("sdclk_total: 20.0000 mm",), None, "len_rules 把 SDCLK 串阻两侧相加得 20 mm"),
]
MEASURED_RULES = {"tht_thermal", "smd_solid"}
