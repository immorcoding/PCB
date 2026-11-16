"""球位数据和校验。

数据来源（都在远程分支上，`git show origin/research/<名>:docs/research/<名>.md`）：
  - 调研 h7-peripheral-pinmux：第 2.2 节（SDRAM 57 脚的 端口:球(圈)）、第 2.4 节（RMII 9 脚）、
    第 2.5 节（QSPI，取"套 A"一列）、第 3.1 节（套 A 的 LTDC 20 脚、SDMMC1 6 脚）。
  - 调研 sdram-32bit-bga：第 2 节（90 球 SDRAM 共用球图，ISSI IS42S32800J）。
  - 调研 bga-fanout-practice：MCU 为 UFBGA176+25，15x15 网格、0.65 mm 球距，行 A–R 跳过 I、O、Q，
    A1 在上视图左上；圈号 0 = 最外圈。

本文件只放数据和校验，不做任何几何计算。`verify_all()` 把数据和 KiCad 自带的两个封装、
符号 STM32H743IIKx 逐项对照，对不上的收集成列表返回，不猜、不修。
"""
import os
import re
from pathlib import Path

# ---------------------------------------------------------------- 路径
def _find_kicad():
    for c in (os.environ.get("KICAD_DIR"), r"D:\KiCad\share\kicad"):
        if c and Path(c).is_dir():
            return Path(c)
    raise FileNotFoundError("找不到 KiCad 的 share/kicad 目录，设环境变量 KICAD_DIR")


KICAD = _find_kicad()
FP_DIR = KICAD / "footprints" / "Package_BGA.pretty"
FP_MCU = FP_DIR / "UFBGA-201_10x10mm_Layout15x15_P0.65mm.kicad_mod"
FP_SDR = FP_DIR / "BGA-90_8.0x13.0mm_Layout2x3x15_P0.8mm.kicad_mod"
SYM_MCU = KICAD / "symbols" / "MCU_ST_STM32H7.kicad_sym"
SYM_NAME = "STM32H743IIKx"

ROWS = "ABCDEFGHJKLMNPR"          # 15 行，跳过 I、O、Q（MCU 和 SDRAM 相同）
MCU_PITCH = 0.65
MCU_COLS = list(range(1, 16))
SDR_PITCH = 0.8
SDR_COLS = [1, 2, 3, 7, 8, 9]
SDR_COL_X = {1: -3.2, 2: -2.4, 3: -1.6, 7: 1.6, 8: 2.4, 9: 3.2}

# ---------------------------------------------------------------- MCU 信号表
# 每行：信号 端口 球 圈（圈来自调研报告，校验时与按球号算出的圈对照）
SDRAM_TXT = """
D0 PD14 M14 1
D1 PD15 L14 1
D2 PD0 B12 1
D3 PD1 C12 2
D4 PE7 R8 0
D5 PE8 P8 1
D6 PE9 P9 1
D7 PE10 R9 0
D8 PE11 P10 1
D9 PE12 R10 0
D10 PE13 N11 2
D11 PE14 P11 1
D12 PE15 R11 0
D13 PD8 P15 0
D14 PD9 P14 1
D15 PD10 N15 0
D16 PH8 M12 3
D17 PH9 M13 2
D18 PH10 L13 2
D19 PH11 L12 3
D20 PH12 K12 3
D21 PH13 E12 3
D22 PH14 E13 2
D23 PH15 D13 2
D24 PI0 E14 1
D25 PI1 D14 1
D26 PI2 C14 1
D27 PI3 C13 2
D28 PI6 C3 2
D29 PI7 C2 1
D30 PI9 D3 2
D31 PI10 E3 2
A0 PF0 E2 1
A1 PF1 H3 2
A2 PF2 H2 1
A3 PF3 J2 1
A4 PF4 J3 2
A5 PF5 K3 2
A6 PF12 P6 1
A7 PF13 N6 2
A8 PF14 R7 0
A9 PF15 P7 1
A10 PG0 N7 2
A11 PG1 M7 3
A12 PG2 L15 0
BA0 PG4 K14 1
BA1 PG5 K13 2
NBL0 PE0 A4 0
NBL1 PE1 A3 0
NBL2 PI4 D4 3
NBL3 PI5 C4 2
SDCLK PG8 H14 1
SDNCAS PG15 B7 1
SDNRAS PF11 R6 0
SDNWE PH5 J4 3
SDCKE0 PH2 F4 3
SDNE0 PH3 G4 3
"""

# 套 A 的其它总线。信号名按 KiCad 符号里的备选功能名写（报告里 LTDC 写作 LCD_*，ETH_RMII_* 对应符号里的 ETH_*）。
BUS_TXT = {
    # 报告 3.1：LTDC RGB565，20 脚
    "LTDC": """
LTDC_R3 PB0 R5 0
LTDC_R4 PA5 P4 1
LTDC_R5 PA9 E15 0
LTDC_R6 PB1 R4 0
LTDC_R7 PG6 J15 0
LTDC_G2 PA6 P3 1
LTDC_G3 PG10 B10 1
LTDC_G4 PB10 R12 0
LTDC_G5 PB11 R13 0
LTDC_G6 PC7 G15 0
LTDC_G7 PD3 D11 3
LTDC_B3 PA8 F15 0
LTDC_B4 PA10 D15 0
LTDC_B5 PA3 R2 0
LTDC_B6 PB8 A5 0
LTDC_B7 PB9 B4 1
LTDC_CLK PG7 J14 1
LTDC_DE PF10 L1 0
LTDC_HSYNC PC6 H15 0
LTDC_VSYNC PA4 N4 2
""",
    # 报告 2.5，"套 A"一列
    "QSPI": """
QUADSPI_CLK PB2 M6 3
QUADSPI_BK1_NCS PB6 B6 1
QUADSPI_BK1_IO0 PF8 L3 2
QUADSPI_BK1_IO1 PF9 L2 1
QUADSPI_BK1_IO2 PF7 K1 0
QUADSPI_BK1_IO3 PF6 K2 1
""",
    # 报告 3.1：SDMMC1 4 位
    "SDMMC": """
SDMMC1_CK PC12 A12 0
SDMMC1_CMD PD2 D12 3
SDMMC1_D0 PC8 G14 1
SDMMC1_D1 PC9 F14 1
SDMMC1_D2 PC10 B14 1
SDMMC1_D3 PC11 B13 1
""",
    # 报告 2.4：RMII 9 脚
    "RMII": """
ETH_REF_CLK PA1 N2 1
ETH_CRS_DV PA7 R3 0
ETH_RXD0 PC4 N5 2
ETH_RXD1 PC5 P5 1
ETH_TX_EN PG11 B9 1
ETH_TXD0 PG13 A8 0
ETH_TXD1 PG12 B8 1
ETH_MDC PC1 M3 2
ETH_MDIO PA2 P2 1
""",
}
BUS_ORDER = ["LTDC", "QSPI", "SDMMC", "RMII"]
BUS_COUNT = {"LTDC": 20, "QSPI": 6, "SDMMC": 6, "RMII": 9}

# ---------------------------------------------------------------- SDRAM 球表
# 报告 sdram-32bit-bga 第 2 节，行 × 列(1 2 3 7 8 9)。H3 在 128/256 Mb 上是 NC，512 Mb 上是 A12；
# 本研究按 ST 的接法把它当 A12 用（57 脚里的 A12 要有地方接）。
SDR_MAP_TXT = """
A DQ26 DQ24 VSS VDD DQ23 DQ21
B DQ28 VDDQ VSSQ VDDQ VSSQ DQ19
C VSSQ DQ27 DQ25 DQ22 DQ20 VDDQ
D VSSQ DQ29 DQ30 DQ17 DQ18 VDDQ
E VDDQ DQ31 NC NC DQ16 VSSQ
F VSS DQM3 A3 A2 DQM2 VDD
G A4 A5 A6 A10 A0 A1
H A7 A8 A12 NC BA1 A11
J CLK CKE A9 BA0 CS# RAS#
K DQM1 NC NC CAS# WE# DQM0
L VDDQ DQ8 VSS VDD DQ7 VSSQ
M VSSQ DQ10 DQ9 DQ6 DQ5 VDDQ
N VSSQ DQ12 DQ14 DQ1 DQ3 VDDQ
P DQ11 VDDQ VSSQ VDDQ VSSQ DQ4
R DQ13 DQ15 VSS VDD DQ0 DQ2
"""

# MCU 信号 -> SDRAM 引脚名
def _sdr_pin_name(sig):
    if sig.startswith("D") and sig[1:].isdigit():
        return "DQ" + sig[1:]
    if sig.startswith("NBL"):
        return "DQM" + sig[3:]
    if sig.startswith("BA") or (sig.startswith("A") and sig[1:].isdigit()):
        return sig
    return {"SDCLK": "CLK", "SDCKE0": "CKE", "SDNE0": "CS#",
            "SDNRAS": "RAS#", "SDNCAS": "CAS#", "SDNWE": "WE#"}[sig]


# ---------------------------------------------------------------- 解析
def _parse_rows(txt):
    out = []
    for line in txt.strip().splitlines():
        p = line.split()
        out.append(p)
    return out


def ball_rc(ball):
    """球号 -> (行索引 0..14, 列 1..15)；行字母不在 ROWS 里就抛错。"""
    m = re.fullmatch(r"([A-R])(\d+)", ball)
    if not m or m.group(1) not in ROWS:
        raise ValueError(f"非法球号 {ball}")
    return ROWS.index(m.group(1)), int(m.group(2))


def mcu_xy(ball):
    """MCU 球的坐标 (mm)，封装中心为原点，x 向右，y 向下（KiCad 板坐标），上视图 A1 在左上。"""
    r, c = ball_rc(ball)
    return ((c - 8) * MCU_PITCH, (r - 7) * MCU_PITCH)


def mcu_ring(ball):
    r, c = ball_rc(ball)
    return min(r, 14 - r, c - 1, 15 - c)


def mcu_edge(ball):
    """最近的封装边：'上' '下' '左' '右'；两条边一样近（拐角）返回 '角'。"""
    r, c = ball_rc(ball)
    d = {"上": r, "下": 14 - r, "左": c - 1, "右": 15 - c}
    m = min(d.values())
    w = [k for k, v in d.items() if v == m]
    return w[0] if len(w) == 1 else "角"


def mcu_edge_updown_first(ball):
    """拐角球两条边一样近时，上、下边优先于左、右边（用来复现调研 pinmux 第 2.2 和 8.1 节的各边计数）。"""
    c = mcu_edge_candidates(ball)
    for e in ("上", "下", "左", "右"):
        if e in c:
            return e


def mcu_edge_candidates(ball):
    r, c = ball_rc(ball)
    d = {"上": r, "下": 14 - r, "左": c - 1, "右": 15 - c}
    m = min(d.values())
    return [k for k, v in d.items() if v == m]


def sdr_map():
    """{球号: 引脚名}，90 项。"""
    out = {}
    for p in _parse_rows(SDR_MAP_TXT):
        row, names = p[0], p[1:]
        assert len(names) == 6, p
        for col, nm in zip(SDR_COLS, names):
            out[f"{row}{col}"] = nm
    return out


def sdr_xy(ball):
    """SDRAM 球的封装内坐标 (mm)，封装中心为原点，A1 在 (-3.2, -5.6)。"""
    r, c = ball_rc(ball)
    return (SDR_COL_X[c], -5.6 + SDR_PITCH * r)


def mcu_signals():
    """[(信号, 端口, 球, 圈)]，57 项，顺序 = D0..D31, NBL0..3, A0..A12, BA0, BA1, SDCLK, SDCKE0, SDNE0, SDNRAS, SDNCAS, SDNWE。"""
    rows = {p[0]: (p[1], p[2], int(p[3])) for p in _parse_rows(SDRAM_TXT)}
    order = ([f"D{i}" for i in range(32)] + [f"NBL{i}" for i in range(4)]
             + [f"A{i}" for i in range(13)] + ["BA0", "BA1", "SDCLK", "SDCKE0", "SDNE0", "SDNRAS", "SDNCAS", "SDNWE"])
    assert sorted(order) == sorted(rows), "SDRAM 信号表和顺序表对不上"
    return [(s, rows[s][0], rows[s][1], rows[s][2]) for s in order]


def sdr_pin_ball():
    """{SDRAM 引脚名: 球号}，只含 57 个信号脚。"""
    m = sdr_map()
    inv = {}
    for b, nm in m.items():
        if nm in ("NC", "VSS", "VDD", "VDDQ", "VSSQ"):
            continue
        assert nm not in inv, f"SDRAM 引脚 {nm} 重复"
        inv[nm] = b
    return inv


def bus_signals():
    """{总线: [(信号, 端口, 球, 圈)]}。"""
    out = {}
    for k in BUS_ORDER:
        out[k] = [(p[0], p[1], p[2], int(p[3])) for p in _parse_rows(BUS_TXT[k])]
    return out


# ---------------------------------------------------------------- KiCad 库解析
def parse_pads(path):
    txt = Path(path).read_text(encoding="utf8")
    pads = {}
    for m in re.finditer(r'\(pad "([^"]+)" smd circle\s*\(at ([-\d.]+) ([-\d.]+)\)\s*\(size ([\d.]+)', txt):
        pads[m.group(1)] = (float(m.group(2)), float(m.group(3)), float(m.group(4)))
    return pads


def parse_symbol(path=SYM_MCU, name=SYM_NAME):
    """{球号: (引脚名, [备选功能])}"""
    txt = Path(path).read_text(encoding="utf8")
    i = txt.index(f'(symbol "{name}"')
    j = txt.index('\n\t(symbol "', i + 10)
    blk = txt[i:j]
    out = {}
    for c in re.split(r"\n\t\t\t\(pin ", blk)[1:]:
        nm = re.search(r'\(name "([^"]*)"', c).group(1)
        num = re.search(r'\(number "([^"]*)"', c).group(1)
        out[num] = (nm, re.findall(r'\(alternate "([^"]*)"', c))
    return out


# ---------------------------------------------------------------- 校验
def verify_all(verbose=True):
    """返回 (问题列表, 事实字典)。问题列表为空 = 全部对上。"""
    issues = []
    facts = {}

    # 1. MCU 封装：201 个焊盘，名字和坐标与网格公式一致
    pads = parse_pads(FP_MCU)
    facts["mcu_pads"] = len(pads)
    if len(pads) != 201:
        issues.append(f"MCU 封装焊盘数 {len(pads)} != 201")
    for nm, (x, y, d) in pads.items():
        try:
            ex, ey = mcu_xy(nm)
        except ValueError:
            issues.append(f"MCU 封装里有非网格球号 {nm}")
            continue
        if abs(x - ex) > 1e-6 or abs(y - ey) > 1e-6:
            issues.append(f"MCU 封装焊盘 {nm} 坐标 ({x},{y}) 与公式 ({ex:.3f},{ey:.3f}) 不符")
    facts["mcu_pad_dia"] = sorted({d for _, _, d in pads.values()})

    # 2. SDRAM 封装：90 个焊盘，坐标与公式一致，名字集合 = 球表
    sp = parse_pads(FP_SDR)
    smap = sdr_map()
    facts["sdr_pads"] = len(sp)
    if set(sp) != set(smap):
        issues.append(f"SDRAM 封装焊盘名与球表不一致：只在封装 {sorted(set(sp) - set(smap))}，只在球表 {sorted(set(smap) - set(sp))}")
    for nm, (x, y, d) in sp.items():
        if nm in smap:
            ex, ey = sdr_xy(nm)
            if abs(x - ex) > 1e-6 or abs(y - ey) > 1e-6:
                issues.append(f"SDRAM 封装焊盘 {nm} 坐标 ({x},{y}) 与公式 ({ex},{ey}) 不符")
    facts["sdr_pad_dia"] = sorted({d for _, _, d in sp.values()})

    # 3. SDRAM 球表计数：和报告里的"球数核对"一致
    cnt = {}
    for nm in smap.values():
        k = re.sub(r"\d+$", "", nm)
        cnt[k] = cnt.get(k, 0) + 1
    facts["sdr_counts"] = cnt
    want = {"DQ": 32, "DQM": 4, "A": 13, "BA": 2, "CLK": 1, "CKE": 1, "CS#": 1, "RAS#": 1, "CAS#": 1, "WE#": 1,
            "VDD": 4, "VSS": 4, "VDDQ": 10, "VSSQ": 10, "NC": 5}
    for k, v in want.items():
        if cnt.get(k, 0) != v:
            issues.append(f"SDRAM 球表 {k} 计数 {cnt.get(k, 0)}，期望 {v}（H3 按 A12 计，所以 NC 是 5 不是 6）")

    # 4. 57 个 MCU 信号：和 SDRAM 引脚一一能配上
    sigs = mcu_signals()
    sp_ball = sdr_pin_ball()
    for s, port, ball, ring in sigs:
        if _sdr_pin_name(s) not in sp_ball:
            issues.append(f"MCU 信号 {s} 对应的 SDRAM 引脚 {_sdr_pin_name(s)} 在球表里找不到")
    used = {_sdr_pin_name(s) for s, *_ in sigs}
    if used != set(sp_ball):
        issues.append(f"SDRAM 信号脚 {sorted(set(sp_ball) - used)} 没有 MCU 信号对应")
    facts["n_sig"] = len(sigs)
    if len(sigs) != 57:
        issues.append(f"SDRAM 信号数 {len(sigs)} != 57")
    # 圈分布和报告 h7-peripheral-pinmux 第 2.2 节一致：0 圈 11、1 圈 20、2 圈 17、3 圈 9（内两圈 26）
    rc = {r: sum(1 for _s, _p, b, _r in sigs if mcu_ring(b) == r) for r in range(4)}
    facts["sdram_ring_counts"] = rc
    if rc != {0: 11, 1: 20, 2: 17, 3: 9}:
        issues.append(f"SDRAM 按圈分布 {rc} 与报告的 {{0: 11, 1: 20, 2: 17, 3: 9}} 不一致")
    ec = {}
    for s, port, b, ring in sigs:
        ec[mcu_edge(b)] = ec.get(mcu_edge(b), 0) + 1
    facts["sdram_edge_counts"] = ec     # 拐角球单列；下面按"上下优先"的归属规则和报告对照
    ec2 = {}
    for s, port, b, ring in sigs:
        ec2[mcu_edge_updown_first(b)] = ec2.get(mcu_edge_updown_first(b), 0) + 1
    if ec2 != {"下": 18, "右": 18, "左": 12, "上": 9}:
        issues.append(f"SDRAM 按边分布（拐角上下优先）{ec2} 与报告的 下 18、右 18、左 12、上 9 不一致")
    facts["sdram_edge_counts_updown_first"] = ec2

    # 5. MCU 信号球：存在于封装、圈号和报告一致、端口名与 KiCad 符号一致、备选功能里有对应的信号名
    sym = parse_symbol()
    facts["sym_pins"] = len(sym)
    gpio_balls = [b for b, (nm, _) in sym.items() if re.match(r"P[A-K]\d", nm)]
    facts["gpio_balls"] = len(gpio_balls)
    if len(gpio_balls) != 140:
        issues.append(f"符号里 GPIO 球 {len(gpio_balls)} != 140")

    def check_row(tag, sig, port, ball, ring, alt_name):
        if ball not in pads:
            issues.append(f"[{tag}] {sig}: 球 {ball} 不在 MCU 封装里")
            return
        if mcu_ring(ball) != ring:
            issues.append(f"[{tag}] {sig}: 报告圈号 {ring}，按球号算 {mcu_ring(ball)}")
        if ball not in sym:
            issues.append(f"[{tag}] {sig}: 球 {ball} 不在符号里")
            return
        nm, alts = sym[ball]
        if not nm.startswith(port):
            issues.append(f"[{tag}] {sig}: 报告端口 {port}，符号里 {ball} 是 {nm}")
        if alt_name not in alts:
            issues.append(f"[{tag}] {sig}: 符号里 {ball}({nm}) 的备选功能没有 {alt_name}")

    seen = {}
    for s, port, ball, ring in sigs:
        check_row("SDRAM", s, port, ball, ring, "FMC_" + s)
        seen.setdefault(ball, []).append(("SDRAM", s))
    for bus, rows in bus_signals().items():
        if len(rows) != BUS_COUNT[bus]:
            issues.append(f"[{bus}] 脚数 {len(rows)} != {BUS_COUNT[bus]}")
        for s, port, ball, ring in rows:
            check_row(bus, s, port, ball, ring, s)
            seen.setdefault(ball, []).append((bus, s))
    for ball, lst in seen.items():
        if len(lst) > 1:
            issues.append(f"球 {ball} 被多个信号占用：{lst}")
    facts["balls_used_by_buses"] = sum(len(v) for v in seen.values())
    gc = {}
    for b in gpio_balls:
        gc[mcu_edge_updown_first(b)] = gc.get(mcu_edge_updown_first(b), 0) + 1
    facts["gpio_edge_counts_updown_first"] = gc
    if gc != {"下": 41, "左": 29, "右": 32, "上": 38}:
        issues.append(f"GPIO 按边分布（拐角上下优先）{gc} 与报告 8.1 节的 下 41、左 29、右 32、上 38 不一致")
    return issues, facts


if __name__ == "__main__":
    iss, fa = verify_all()
    print("事实：", fa)
    print("问题数：", len(iss))
    for i in iss:
        print("  -", i)
