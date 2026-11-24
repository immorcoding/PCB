"""The demo board's one schematic page: STM32H743 + SDRAM with one byte lane (SPEC 2, 3, 4).

Drawn by Tools.KiCadDesignTools.schematic.generate (board.toml [schematic] pages). The MCU's used balls come from
../pins.csv (ball -> signal); every other IO ball is marked no-connect, so ERC has nothing to say about them. The
SDRAM's data bits follow ../swap.csv (DQn -> FMC net); its unused balls are no-connect too.

Choices (SPEC 2.2, 4; unverified.md):
  - one rail +3V3 from J1; every VDD, VDD33USB, VBAT, PDR_ON, VDDA and VREF+ ball on +3V3, VSS, VSSA, VREF- on GND
  - VCAP1 / VCAP2 left open (no-connect): tying them to +3V3 or GND would short the core regulator; the circuit is not
    meant to run (SPEC 1), the two 2.2 uF capacitors a working board needs are left out (unverified U2)
  - BOOT0 straight to GND (boot from flash), NRST to a test pad (internal pull-up)
  - HSE: the H743 board's crystal and load capacitors (ABM8 25 MHz, 15 pF)
  - decoupling: four 100 nF under U1, two under U2 (0402, bottom), one 4.7 uF at J1
"""
import csv, os
from Tools.KiCadDesignTools.schematic.sheet import NC, FP, symbol

HERE = os.path.dirname(os.path.abspath(__file__))
FP_MCU = "Package_BGA:UFBGA-201_10x10mm_Layout15x15_P0.65mm"
FP_SDRAM = "demo:BGA-90_8.0x13.0mm_Layout2x3x15_P0.8mm_Pad0.33mm"
HDR = "Connector_PinHeader_2.54mm:PinHeader_1x%02d_P2.54mm_Vertical"

# non-IO balls of the MCU (KiCad symbol MCU_ST_STM32H7:STM32H743IIKx, pin names)
SUPPLY = {"VDD": "+3V3", "VSS": "GND", "VBAT": "+3V3", "VDD33_USB": "+3V3", "VDDA": "+3V3", "VREF+": "+3V3",
          "VSSA": "GND", "VREF-": "GND", "F13": NC, "M10": NC}

# SDRAM ISSI IS42S32800J ball map (datasheet Rev C p.4, top view; the H743 board's page sdram.py): rows A..R, columns
# 1 2 3 | 7 8 9
BALLS = """
A DQ26 DQ24 VSS   VDD  DQ23 DQ21
B DQ28 VDDQ VSSQ  VDDQ VSSQ DQ19
C VSSQ DQ27 DQ25  DQ22 DQ20 VDDQ
D VSSQ DQ29 DQ30  DQ17 DQ18 VDDQ
E VDDQ DQ31 NC    NC   DQ16 VSSQ
F VSS  DQM3 A3    A2   DQM2 VDD
G A4   A5   A6    A10  A0   A1
H A7   A8   NC    NC   BA1  A11
J CLK  CKE  A9    BA0  CS   RAS
K DQM1 NC   NC    CAS  WE   DQM0
L VDDQ DQ8  VSS   VDD  DQ7  VSSQ
M VSSQ DQ10 DQ9   DQ6  DQ5  VDDQ
N VSSQ DQ12 DQ14  DQ1  DQ3  VDDQ
P DQ11 VDDQ VSSQ  VDDQ VSSQ DQ4
R DQ13 DQ15 VSS   VDD  DQ0  DQ2
"""
# the SDRAM signals the demo connects (one byte lane, four address lines, one bank address, the clock)
CONTROL = {"CLK": "FMC_SDCLK_R", "BA0": "FMC_BA0", "A0": "FMC_A0", "A1": "FMC_A1", "A2": "FMC_A2", "A3": "FMC_A3"}


def ball_map():
    """{ball: datasheet signal name} of the SDRAM (schematic.check reads the byte lane from it)."""
    out = {}
    for line in BALLS.strip().splitlines():
        row, *names = line.split()
        for col, name in zip((1, 2, 3, 7, 8, 9), names):
            out["%s%d" % (row, col)] = name
    assert len(out) == 90
    return out


def swap_table():
    """{SDRAM signal (DQn, DQMn): MCU-side net} from ../swap.csv."""
    return {r["sdram"]: r["net"] for r in csv.DictReader(open(os.path.join(HERE, "..", "swap.csv"), encoding="utf-8"))}


def mcu_nets():
    """{ball or pin name: net}: the pins.csv balls on their signals, the supply pins, every other ball no-connect."""
    rows = list(csv.DictReader(open(os.path.join(HERE, "..", "pins.csv"), encoding="utf-8")))
    nets = {r["ball"]: r["signal"] for r in rows if r["group"] != "FREE"}
    return nets


def build(sh):
    # ---------------------------------------------------------------- MCU
    sh.title("MCU STM32H743IIK6 (UFBGA176+25): one SDRAM byte lane, HSE, USART1; every other IO no-connect", 4, 4)
    nets = dict(SUPPLY)
    nets.update(mcu_nets())
    mcu = sh.page.sym("MCU_ST_STM32H7:STM32H743IIKx", "U1", "STM32H743IIK6", 76.2, 149.86, 0, FP_MCU,
                      fields={"MPN": "STM32H743IIK6", "Manufacturer": "STMicroelectronics"})
    names = {}
    for num, name, *_ in mcu._pins:
        names.setdefault(name, []).append(num)
    full = {}
    for num, name, *_ in mcu._pins:
        full[num] = nets.get(num, nets.get(name, nets.get(name.split("/")[0], NC)))
    sh.attach(mcu, full, stub=3)

    # ---------------------------------------------------------------- SDRAM
    balls, swap = ball_map(), swap_table()
    by_sig = {}
    for ball, sig in balls.items():
        by_sig.setdefault(sig, []).append(ball)
    one = lambda sig: by_sig[sig][0]
    order = lambda sigs, typ: [(one(s), s, typ) for s in sigs]
    left = (order(["CLK", "CKE", "CS", "RAS", "CAS", "WE"], "input") + [None] + order(["BA0", "BA1"], "input") + [None]
            + order(["A%d" % k for k in range(12)], "input") + [(b, "NC", "no_connect") for b in sorted(by_sig["NC"])])
    right = []
    for byte in range(4):
        right += order(["DQ%d" % k for k in range(8 * byte, 8 * byte + 8)], "bidirectional") + order(["DQM%d" % byte], "input") + [None]
    top = [(b, s, "power_in") for s in ("VDD", "VDDQ") for b in sorted(by_sig[s])]
    bottom = [(b, s, "power_in") for s in ("VSS", "VSSQ") for b in sorted(by_sig[s])]
    lib = symbol("IS42S32800J-6BL", left=left, right=right[:-1], top=top, bottom=bottom, ref="U", footprint=FP_SDRAM,
                 description="256 Mb SDRAM 8M x 32, 3.3 V, 166 MHz, 90-ball TF-BGA")

    def net_of(sig):
        if sig in swap:
            return swap[sig]
        if sig in CONTROL:
            return CONTROL[sig]
        return {"VDD": "+3V3", "VDDQ": "+3V3", "VSS": "GND", "VSSQ": "GND"}.get(sig, NC)

    sh.title("SDRAM IS42S32800J: byte lane 0 (swap.csv), A0-A3, BA0, CLK; the rest no-connect", 70, 4)
    sh.ic(lib, "U2", "IS42S32800J-6BLI", 100, 48, FP_SDRAM, {b: net_of(s) for b, s in balls.items()}, stub=3,
          fields={"MPN": "IS42S32800J-6BLI", "Manufacturer": "ISSI"})

    # ---------------------------------------------------------------- the rest
    x = 128
    sh.title("SDCLK series resistor (at the MCU)", x, 6)
    sh.two("Device:R", "R1", "33R", x + 6, 12, FP["R0402"], "FMC_SDCLK", "FMC_SDCLK_R", horizontal=True)

    sh.title("HSE 25 MHz", x, 18)
    sh.ic("Device:Crystal_GND24", "Y1", "25MHz 10pF", x + 6, 26, "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
          {"1": "HSE_IN", "3": "HSE_OUT", "2": "GND", "4": "GND"},
          fields={"MPN": "ABM8-25.000MHZ-10-D2X-T", "Manufacturer": "Abracon"})
    sh.C("C1", "15pF", x + 16, 26, "HSE_IN", fp=FP["C0402"])
    sh.C("C2", "15pF", x + 22, 26, "HSE_OUT", fp=FP["C0402"])

    sh.title("Decoupling under the BGAs (bottom, 0402): U1 C3-C6, U2 C7-C8", x, 36)
    sh.caps(3, ["100nF"] * 6, x + 2, 42, "+3V3", step=5, fp=FP["C0402"])

    sh.title("+3V3 input", x, 52)
    sh.ic("Connector_Generic:Conn_01x02", "J1", "+3V3 1x2 2.54mm", x + 6, 60, HDR % 2, {"1": "+3V3", "2": "GND"}, stub=3)
    sh.C("C9", "4.7uF", x + 16, 60, "+3V3", fp=FP["C0805"])
    sh.flag("+3V3", x + 24, 57)
    sh.flag("GND", x + 28, 57)

    sh.title("Debug UART (USART1): 1 GND, 2 TX, 3 RX, 4 3V3", x, 70)
    sh.ic("Connector_Generic:Conn_01x04", "J2", "UART 1x4 2.54mm", x + 6, 80, HDR % 4,
          {"1": "GND", "2": "USART1_TX", "3": "USART1_RX", "4": "+3V3"}, stub=3)

    sh.title("Reset test pad (NRST has an internal pull-up)", x, 92)
    sh.tp("TP1", "NRST", x + 6, 98, kind="TP_1.0")
