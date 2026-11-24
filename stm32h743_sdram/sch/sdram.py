"""Page 3: SDRAM ISSI IS42S32800J-6BLI, 8M x 32, 90-ball TF-BGA 8 x 13 mm, 0.8 mm pitch (SPEC 2.1, 9).

Ball map: ISSI datasheet IS42S32800J / IS45S32800J Rev C (2025-02-25) page 4, read from the rendered
page and cross-checked with the text layer; pin descriptions on the same page. Package drawing page 59.
  - 15 rows A..R (no I, O, Q), columns 1-3 and 7-9.
  - H3 is NC on this 256 Mb part and is A12 on the 512 Mb parts of the same ball-out: FMC_A12 is wired
    to it so that a 512 Mb part fits without a board change (SPEC 2.1). The other NC balls (E3, E7, H7,
    K2, K3) stay unconnected.
  - DQM0..3 gate bytes DQ0-7, DQ8-15, DQ16-23, DQ24-31.

Data bits may be swapped on the SDRAM side only (SPEC 9): any order inside a byte, whole bytes
exchanged, the DQM follows its byte. Net names follow the MCU side. ../swap.csv is the single source:
this page reads it, prints it, and sch_check.py verifies the netlist against it.

Footprint: h743:BGA-90_8.0x13.0mm_Layout2x3x15_P0.8mm_Pad0.33mm (stock footprint, pads 0.40 -> 0.33).
Decoupling: one 100 nF per two supply balls plus one bulk capacitor is a starting value; whether they fit
in the 5 mm gap to the MCU is checked at placement (unverified item U21).
"""
import csv, os
from .common import NC, symbol

HERE = os.path.dirname(os.path.abspath(__file__))

# rows A..R, columns 1 2 3 | 7 8 9, exactly as printed in the datasheet's top view
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


def ball_map():
    """{ball: datasheet signal name}; H3 becomes 'A12' (NC on 256 Mb)."""
    out = {}
    for line in BALLS.strip().splitlines():
        row, *names = line.split()
        for col, name in zip((1, 2, 3, 7, 8, 9), names):
            out["%s%d" % (row, col)] = name
    assert len(out) == 90 and out["H3"] == "NC"
    out["H3"] = "A12"
    return out


def swap_table():
    """{SDRAM signal (DQn, DQMn): MCU-side net} from ../swap.csv."""
    rows = list(csv.DictReader(open(os.path.join(HERE, "..", "swap.csv"), encoding="utf-8")))
    return {r["sdram"]: r["net"] for r in rows}


CONTROL = {"CLK": "FMC_SDCLK_R", "CKE": "FMC_SDCKE0", "CS": "FMC_SDNE0", "RAS": "FMC_SDNRAS", "CAS": "FMC_SDNCAS",
           "WE": "FMC_SDNWE", "BA0": "FMC_BA0", "BA1": "FMC_BA1"}


def net_of(sig, swap):
    if sig in swap:
        return swap[sig]
    if sig in CONTROL:
        return CONTROL[sig]
    if sig[0] == "A" and sig[1:].isdigit():
        return "FMC_" + sig
    return {"VDD": "+3V3", "VDDQ": "+3V3", "VSS": "GND", "VSSQ": "GND", "NC": NC}[sig]


def build(sh):
    balls, swap = ball_map(), swap_table()
    by_sig = {}
    for ball, sig in balls.items():
        by_sig.setdefault(sig, []).append(ball)
    one = lambda sig: by_sig[sig][0]
    order = lambda sigs, typ: [(one(s), "A12/NC" if s == "A12" else s, typ) for s in sigs]
    left = (order(["CLK", "CKE", "CS", "RAS", "CAS", "WE"], "input") + [None]
            + order(["BA0", "BA1"], "input") + [None] + order(["A%d" % k for k in range(13)], "input"))
    right = []
    for byte in range(4):
        right += order(["DQ%d" % k for k in range(8 * byte, 8 * byte + 8)], "bidirectional") + order(["DQM%d" % byte], "input") + [None]
    nc = [(b, "NC", "no_connect") for b in sorted(by_sig["NC"])]
    left += [None] + nc
    top = [(b, s, "power_in") for s in ("VDD", "VDDQ") for b in sorted(by_sig[s])]
    bottom = [(b, s, "power_in") for s in ("VSS", "VSSQ") for b in sorted(by_sig[s])]
    lib = symbol("IS42S32800J-6BL", left=left, right=right[:-1], top=top, bottom=bottom, ref="U",
                 footprint="h743:BGA-90_8.0x13.0mm_Layout2x3x15_P0.8mm_Pad0.33mm",
                 description="256 Mb SDRAM 8M x 32, 3.3 V, 166 MHz, 90-ball TF-BGA")

    sh.title("SDRAM 256 Mbit (8M x 32), SDCLK 100 MHz, CL3", 6, 8)
    sh.title("Bring-up link", 90, 60)
    sh.link("R301", "+3V3", "+3V3_SDRAM", 96, 66)
    sh.rails = {"+3V3": "+3V3_SDRAM"}
    nets = {ball: net_of(sig, swap) for ball, sig in balls.items()}
    sh.ic(lib, "U301", "IS42S32800J-6BLI", 50, 56, "h743:BGA-90_8.0x13.0mm_Layout2x3x15_P0.8mm_Pad0.33mm", nets,
          stub=3, fields={"MPN": "IS42S32800J-6BLI", "Manufacturer": "ISSI", "Alternate": "Alliance AS4C8M32SA-6BIN"})
    sh.title("Decoupling: VDD x 4, VDDQ x 8", 90, 8)
    sh.caps(301, ["100nF"] * 8, 92, 16, "+3V3")
    sh.caps(309, ["10uF"], 92, 30, "+3V3")
    sh.note("H3 is NC on the 256 Mb part and A12 on a 512 Mb part with the same ball-out: FMC_A12 is wired to it.", 90, 42)
    sh.note("SDCLK: one 0402 series resistor near the MCU (MCU page); this page sees FMC_SDCLK_R.", 90, 44)
    sh.note("Data bits are swapped on this side only; net names follow the MCU. Table = swap.csv:", 90, 48)
    for byte in range(4):
        sigs = ["DQ%d" % k for k in range(8 * byte, 8 * byte + 8)] + ["DQM%d" % byte]
        sh.note("  ".join("%s=%s" % (s, swap[s].replace("FMC_", "")) for s in sigs), 90, 50 + 2 * byte)
