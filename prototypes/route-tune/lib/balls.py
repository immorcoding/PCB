"""PROTOTYPE (issue 21): ball data of the two chips for the 19 nets, checked against the KiCad libraries.

Sources (same as the length-tuning prototype and the placement study):
  MCU   FMC function -> port: research h7-peripheral-pinmux (table copied in
        origin/research/sdram-placement-study:docs/research/sdram-placement-study/balldata.py).
        port -> ball: read from the KiCad symbol STM32H743IIKx at build time and compared with that table.
  SDRAM 90-ball map of IS42S32800J: origin/research/sdram-32bit-bga:docs/research/sdram-32bit-bga.md,
        section 2 (compared there with the ISSI datasheet). KiCad has no symbol for it, so only the
        pad NAMES and POSITIONS are checked against the KiCad footprint, not the functions.
"""
import os, re
from common import KI, NETS, full

# net -> (port, ball) as listed by the research; verify() compares the ball with the KiCad symbol
MCU_PINS = {
    "FMC_D0": ("PD14", "M14"), "FMC_D1": ("PD15", "L14"), "FMC_D2": ("PD0", "B12"), "FMC_D3": ("PD1", "C12"),
    "FMC_D4": ("PE7", "R8"), "FMC_D5": ("PE8", "P8"), "FMC_D6": ("PE9", "P9"), "FMC_D7": ("PE10", "R9"),
    "FMC_D8": ("PE11", "P10"), "FMC_D9": ("PE12", "R10"), "FMC_D10": ("PE13", "N11"), "FMC_D11": ("PE14", "P11"),
    "FMC_D12": ("PE15", "R11"), "FMC_D13": ("PD8", "P15"), "FMC_D14": ("PD9", "P14"), "FMC_D15": ("PD10", "N15"),
    "FMC_NBL0": ("PE0", "A4"), "FMC_NBL1": ("PE1", "A3"), "FMC_SDCLK": ("PG8", "H14"),
}
ROWS = "ABCDEFGHJKLMNPR"
SDR_COLS = [1, 2, 3, 7, 8, 9]
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
GND_BALLS = {"U1": "M9", "U2": "A3"}                       # one VSS ball per chip gets a via (ties L2 and L5 together)


def sdr_map():
    """{ball: pin name} of the 90-ball SDRAM."""
    out = {}
    for line in SDR_MAP_TXT.strip().splitlines():
        p = line.split()
        for col, nm in zip(SDR_COLS, p[1:]):
            out[p[0] + str(col)] = nm
    return out


def sdr_ball(pin):
    """SDRAM pin name ('DQ13', 'DQM0', 'CLK') -> ball."""
    hits = [b for b, n in sdr_map().items() if n == pin]
    assert len(hits) == 1, "SDRAM pin %s: %d balls" % (pin, len(hits))
    return hits[0]


def ring(ball):
    """MCU ring of a ball, 0 = outermost."""
    r, c = ROWS.index(ball[0]), int(ball[1:])
    return min(r, 14 - r, c - 1, 15 - c)


def sym_pins(libfile, name):
    """{pin name: pin number} of a KiCad library symbol (follows one level of 'extends')."""
    text = open(os.path.join(KI, "symbols", libfile), encoding="utf-8").read()

    def block(n):
        i = text.find('\t(symbol "%s"\n' % n)
        if i < 0:
            raise SystemExit("no symbol " + n)
        depth, j = 0, i
        while True:
            c = text[j]
            depth += (c == "(") - (c == ")")
            if c == ")" and depth == 0:
                return text[i:j + 1]
            j += 1

    blk = block(name)
    m = re.search(r'\(extends "([^"]+)"', blk)
    if m:
        blk = block(m.group(1))
    return {m.group(1): m.group(2) for m in re.finditer(r'\(name "([^"]*)".*?\(number "([^"]*)"', blk, re.S)}


def fp_pads(lib_name):
    """{pad name: (x, y, size)} of a KiCad footprint 'Lib:Name'."""
    lib, name = lib_name.split(":")
    txt = open(os.path.join(KI, "footprints", lib + ".pretty", name + ".kicad_mod"), encoding="utf-8").read()
    return {m.group(1): (float(m.group(2)), float(m.group(3)), float(m.group(4)))
            for m in re.finditer(r'\(pad "([^"]+)" smd circle\s*\(at ([-\d.]+) ([-\d.]+)\)\s*\(size ([\d.]+)', txt)}


def check_swap(swap):
    """swap = {net: SDRAM pin}. Returns (table {net: (pin, ball)}, lanes_swapped). Raises on a rule break:
    data bits may move inside a byte lane, the two lanes may trade places, DQM follows its lane."""
    swap = {full(n): p for n, p in swap.items()}
    assert sorted(swap) == sorted(NETS), "SWAP must name exactly the 19 nets: %s" % sorted(set(swap) ^ set(NETS))
    assert len(set(swap.values())) == 19, "SWAP: an SDRAM pin is used twice"
    assert swap["FMC_SDCLK"] == "CLK", "SDCLK must go to CLK"
    lane = {}
    for k in (0, 1):
        got = sorted(int(swap["FMC_D%d" % i][2:]) for i in range(8 * k, 8 * k + 8))
        assert got in (list(range(8)), list(range(8, 16))), "MCU byte lane %d is spread over both SDRAM lanes: %s" % (k, got)
        lane[k] = got[0] // 8
        assert swap["FMC_NBL%d" % k] == "DQM%d" % lane[k], "NBL%d must follow its lane to DQM%d" % (k, lane[k])
    assert lane[0] != lane[1]
    return {n: (p, sdr_ball(p)) for n, p in swap.items()}, lane[0] == 1


def verify(fp_mcu, fp_ram):
    """Compare the tables above with the KiCad symbol and footprints. Returns (mcu balls {net: ball}, notes)."""
    notes = []
    pins = sym_pins("MCU_ST_STM32H7.kicad_sym", "STM32H743IIKx")
    pm, pr = fp_pads(fp_mcu), fp_pads(fp_ram)
    assert len(pm) == 201 and len(pr) == 90, "pad counts %d / %d" % (len(pm), len(pr))
    balls = {}
    for n, (port, ball) in MCU_PINS.items():
        assert pins.get(port) == ball, "%s: research says %s = %s, KiCad symbol says %s" % (n, port, ball, pins.get(port))
        assert ball in pm, "%s: ball %s not in the MCU footprint" % (n, ball)
        r, c = ROWS.index(ball[0]), int(ball[1:])
        assert abs(pm[ball][0] - (c - 8) * 0.65) < 1e-6 and abs(pm[ball][1] - (r - 7) * 0.65) < 1e-6, "MCU pad %s is not where the grid formula puts it" % ball
        balls[n] = ball
    notes.append("MCU: 19 port->ball pairs equal the KiCad symbol STM32H743IIKx; pads on the 15x15 0.65 mm grid")
    smap = sdr_map()
    assert set(smap) == set(pr), "SDRAM ball names differ from the footprint: %s" % sorted(set(smap) ^ set(pr))
    colx = {1: -3.2, 2: -2.4, 3: -1.6, 7: 1.6, 8: 2.4, 9: 3.2}
    for b in smap:
        r, c = ROWS.index(b[0]), int(b[1:])
        assert abs(pr[b][0] - colx[c]) < 1e-6 and abs(pr[b][1] - (-5.6 + 0.8 * r)) < 1e-6, "SDRAM pad %s position" % b
    cnt = {}
    for nm in smap.values():
        k = re.sub(r"\d+$", "", nm); cnt[k] = cnt.get(k, 0) + 1
    assert cnt["DQ"] == 32 and cnt["DQM"] == 4 and cnt["CLK"] == 1, cnt
    notes.append("SDRAM: 90 ball names and positions equal the KiCad footprint; functions come from the research ball map (no KiCad symbol)")
    assert GND_BALLS["U1"] in mcu_vss_balls(), "MCU ground ball %s is not VSS in the KiCad symbol" % GND_BALLS["U1"]
    assert smap[GND_BALLS["U2"]] == "VSS", "SDRAM ground ball %s is %s" % (GND_BALLS["U2"], smap[GND_BALLS["U2"]])
    return balls, notes


def mcu_vss_balls():
    """All MCU ball numbers whose pin name is VSS (the symbol stacks several pins under one name)."""
    text = open(os.path.join(KI, "symbols", "MCU_ST_STM32H7.kicad_sym"), encoding="utf-8").read()
    i = text.find('\t(symbol "STM32H743IIKx"\n')
    j = text.find('\n\t(symbol "', i + 10)
    blk = text[i:j]
    m = re.search(r'\(extends "([^"]+)"', blk)
    if m:
        i = text.find('\t(symbol "%s"\n' % m.group(1)); j = text.find('\n\t(symbol "', i + 10); blk = text[i:j]
    return [num for nm, num in re.findall(r'\(name "([^"]*)".*?\(number "([^"]*)"', blk, re.S) if nm == "VSS"]
