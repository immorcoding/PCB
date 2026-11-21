"""Page 1: power input and the five rails (SPEC 4, 2.3, 5; test points of SPEC 10).

    J101 -> F101 -> Q101 (reverse polarity) -> D102 (TVS) -> +12V -> U101 -> +5V -> U102 -> +3V3
                                                                     +5V -> U103 -> +3V3A (EN from +3V3)
                                                                     +3V3 -> U104 -> +1V8 (EN from +3V3A)

Datasheets are in datasheet/ (not committed). Tables were read off the rendered page (PROC-14); "p." is the
PDF page. Parts marked [sel] were selected on this page and wait for the user's decision.

U101 LMR51420XFDDCR [sel: suffix]  (TI SLUSEF6C)
  p.3  ordering: X = 500 kHz PFM, XF = 500 kHz FPWM, Y = 1.1 MHz PFM, YF = 1.1 MHz FPWM. XF chosen.
  p.3  pins 1 GND, 2 SW, 3 VIN, 4 FB, 5 EN, 6 CB: identical, pin for pin, to the stock symbol
       Regulator_Switching:LMR51430 (compared by script). The project symbol h743:LMR51420 repeats it.
  p.4  abs max VIN 38 V, EN VIN + 0.3 V, FB 5.5 V; recommended VIN 4.5-36 V. "EN can be tied to VIN" (p.3).
  p.5  VFB 0.591 / 0.600 / 0.609 V; soft start 4 ms; tON(min) 70 ns; high-side limit 2.7 / 3.5 / 5.1 A.
  p.16 table 9-1, 500 kHz, 5 V: L 10 uH, COUT 2 x 22 uF, RFBT 100 k, RFBB 13.7 k.
  p.18 eq.11  LMIN = (VINmax - VOUT) / (IOUT x K) x VOUT / (VINmax x fSW), K = 0.2-0.6:
         (18 - 5) / (2 x 0.4) x 5 / (18 x 500k) = 9.0 uH -> 10 uH.
       eq.10  ripple = 5 x (VIN - 5) / (VIN x 10u x 500k) = 0.58 A at 12 V, 0.72 A at 18 V (K = 0.36).
         Peak 2.36 A at 2 A, 1.54 A at the budget maximum 1.175 A.
       "Saturation current must be higher than the peak current limit": 7.0 A > 5.1 A.
  p.18 eq.9   VOUT = 0.6 x (1 + 100 / 13.7) = 4.98 V; with VFB and 1 % resistors 4.87-5.09 V.
  p.18 eq.14  COUT > 0.5 x 8 x dI / (fSW x dV): load dump 1.2 A, dV 250 mV -> 38 uF effective.
         3 x 22 uF 25 V X7R 1210, about 18 uF each at 5 V bias -> about 54 uF.
       Overshoot bound for the TPS62A02 (abs max 6.5 V): all the energy of the inductor at the highest
         current limit into COUT: sqrt(5.0^2 + 10u x 5.1^2 / 54u) = 5.46 V.
  p.19 CIN 4.7 uF or more, rated twice VIN, plus 0.1 uF: 2 x 4.7 uF 50 V X7R + 100 nF 50 V.
       CBOOT 0.1 uF, 16 V or more, X7R / X5R, between CB and SW.
  Duty: on time at 18 V = 5 / 18 / 500k = 556 ns (min 70 ns).

U102 TPS62A02PDDCR  (TI SLUSEG9E)
  p.3  TPS62A02PDDCR = 2 A, SOT-23-6, PSM / PWM. DDC pins: 1 EN, 2 GND, 3 SW, 4 VIN, 5 PG, 6 FB
       (= stock symbol TPS62A02PDDC). EN must not float. PG open drain; unused: open or GND.
  p.4  abs max VIN, EN, PG 6.5 V; recommended VIN 2.5-5.5 V; L 1.0 uH effective; COUT 10 uF min at 1.8 V and above.
  p.5  EN rising 1.2 V max, falling 0.4 V min, leakage 100 nA; VFB 0.6 V +-1.5 %; 2.4 MHz; soft start 1 ms;
       high-side limit 2.7 / 3.4 A.
  p.12 eq.2   R1 = R2 x (VOUT / 0.6 - 1), R2 not above 100 k: R2 22.1 k -> R1 99.5 k -> 100 k,
         VOUT = 0.6 x (1 + 100 / 22.1) = 3.315 V.
       table 8-3: VOUT 1.8 V and above: 1 uH with 22 uF is the recommended combination (2 x 22 uF also checked).
  p.13 CIN 4.7 uF is enough -> 10 uF 16 V (about half left at 5 V bias).
  Ripple = 3.3 x (1 - 0.66) / (1u x 2.4M) = 0.47 A; peak 1.34 A at the budget maximum 1.105 A.

U103 TPS7A2033PDBVR, U104 TPS7A2018PDBVR  (TI SBVS338H)
  p.4  DBV pins 1 IN, 2 GND, 3 EN, 4 N/C (no internal connection), 5 OUT (= stock symbol TPS7A20xxxDBV).
       EN has an internal 500 k pull-down until it is high: a 10 k series resistor loses 2 %.
  p.5  abs max IN, EN 6.5 V; recommended IN 1.6-6.0 V; CIN 1 uF; COUT 1-200 uF, 0.47 uF effective minimum.
  p.42, 45  both orderables are SOT-23 (DBV) 5, Active (the text layer puts them on the X2SON rows).
  EN thresholds 0.3 V min low, 0.9 V max high (p.9, text layer only).
  U103 dissipates (5 - 3.3) x 0.066 A = 0.11 W.

J101 Same Sky PJ-102AH [sel]  (drawing 09/12/2024)
  p.1  24 Vdc, 5 A, 2.0 mm centre pin, right angle, through hole. p.2 schematic: 1 centre pin, 2 sleeve
       contact, 3 switch contact (closed to 2 with no plug). Pad pattern = stock footprint (1 at 0/0, 2 at 0/6, 3 at 4.7/3).
F101 Bourns SF-1206S200-2 [sel]  (SF-1206S p.1)
  Slow blow, 2 A, 63 Vdc, breaks 50 A, 0.041 ohm, melting I2t 0.339 A2s; 100 % for 4 h min, 250 % for 5 s max.
  Load 0.94 A at 7 V = 47 %. Plug-in inrush: 0.5 x 9.5 uF x 18^2 / 0.2 ohm = 0.008 A2s = 2 % of the melting I2t.
Q101 Vishay Si2319DDS-T1-GE3 [sel]  (doc 79400 rev B)
  p.1  SOT-23: 1 G, 2 S, 3 D. VDS -40 V, VGS +-20 V, ID -2.7 A (25 C ambient), RthJA 130 C/W max.
  p.2  RDS(on) 0.075 ohm max at -10 V, 0.100 ohm max at -4.5 V; VGS(th) -1 to -2.5 V.
  Drain to the input, source to +12V: the body diode conducts first, then the channel. 0.94 A x 0.1 ohm = 0.09 V, 0.09 W.
  Reversed input: gate and source both at 0 V, VDS = -18 V.
D101 Vishay BZT52C12-E3-08 [sel]  (doc 86342 rev 1.1 p.2)
  SOD-123, 500 mW, 11.4-12.6 V at 5 mA, 100 nA at 9 V. Holds VGS under 13 V (limit 20 V) up to the TVS
  clamp voltage: (29.2 - 12) / 100 k = 0.17 mA.
D102 Vishay SMBJ18A-E3/52 [sel]  (doc 88392 p.2)
  Unidirectional, SMB, stand-off 18 V, breakdown 20.0-22.1 V at 1 mA, clamp 29.2 V at 20.5 A, 1 uA at 18 V.
  29.2 V is under the LMR51420's 38 V and the P-MOS's 40 V.
L101 Vishay IHLP2525CZER100M01 [sel]  (doc 34104 p.1)
  10 uH +-20 %, DCR 102 typ / 105 max mohm, heat rating 3 A, saturation 7.0 A, SRF 16 MHz, 6.9 x 6.5 x 3.0 mm.
L102 Vishay IHLP1616BZER1R0M11 [sel]  (doc 34196 p.1)
  1.0 uH +-20 %, DCR 24 typ / 27 max mohm, heat rating 4.5 A, saturation 5.0 A, SRF 64 MHz, 4.5 x 4.1 x 2.0 mm.
D103 Vishay VLMG1300-GS08 [sel]  (doc 82437 rev 1.6 p.1)
  0603 yellow green, VF 2.0 typ / 2.4 max at 20 mA, 35 mcd. (3.3 - 1.9) / 470 = 3 mA.
TP109-TP111 Keystone 5001 [sel]  (catalogue M65 p.56): black, loop 2.5 mm, mounting hole 1.0 mm.

Not on this page: the backlight boost (lcd page) and the LED_A test point.
"""
from .common import FP, NC, P, U, symbol

SOT23_6 = "Package_TO_SOT_SMD:SOT-23-6"
SOT23_5 = "Package_TO_SOT_SMD:SOT-23-5"
C1210 = "Capacitor_SMD:C_1210_3225Metric"
TI = "Texas Instruments"
VISHAY = "Vishay"


def _diode(sh, lib, ref, val, i, j, fp, top, bot, top_pin, **kw):
    """A vertical two-pin part whose library symbol is drawn horizontally (Device:D_Zener, Device:LED).
    top_pin is the pin number that ends up on top; the other one is on the bottom."""
    x, y = P(i, j)
    rot = 270 if top_pin == "1" else 90
    just = "left" if rot == 270 else "right"       # a symbol turned by 90 mirrors the justification of its fields
    return sh.ic(lib, ref, val, i, j, fp, {top_pin: top, "2" if top_pin == "1" else "1": bot}, rot=rot, stub=1,
                 ref_at=(x + 1.0 * U, y - 0.5 * U, just), val_at=(x + 1.0 * U, y + 0.5 * U, just), **kw)


def _below(i, j, half_h):
    """Value text position under a box of half height `half_h` grid units, right of the GND pin."""
    x, y = P(i, j)
    return (x + 0.5 * U, y + (half_h + 0.8) * U, "left")


def _cap(sh, ref, val, i, j, top, fp, rating):
    sh.C(ref, val, i, j, top, fp=fp, fields={"Rating": rating})


def build(sh):
    lmr = symbol("LMR51420", ref="U", footprint=SOT23_6,
                 datasheet="https://www.ti.com/lit/ds/symlink/lmr51420.pdf",
                 description="4.5-36 V, 2 A synchronous buck converter, SOT-23-6 (pins as LMR51430)",
                 left=[(3, "VIN", "power_in"), (5, "EN", "input")],
                 right=[(6, "CB", "passive"), (2, "SW", "power_out"), (4, "FB", "input")],
                 bottom=[(1, "GND", "power_in")])

    # ---- input: jack, fuse, reverse-polarity P-MOS, TVS
    sh.title("Input 12 V (7-18 V, centre positive): fuse, reverse-polarity P-MOS, TVS", 6, 9)
    sh.note("Q101: drain to the input, source to +12V; body diode conducts first, then the channel. Reversed input: gate = source = 0 V, the FET stays off.", 6, 11)
    sh.note("D101 holds VGS under 13 V (limit 20 V).  D102 SMBJ18A: stand-off 18 V, clamps 29.2 V at 20.5 A (LMR51420 abs max 38 V, Q101 40 V).  No series links in any rail.", 6, 13)
    sh.ic("Connector:Barrel_Jack_Switch", "J101", "PJ-102AH 5.5x2.1", 14, 23,
          "Connector_BarrelJack:BarrelJack_CUI_PJ-102AH_Horizontal",
          {"1": "+12V_JACK", "2": "GND", "3": "GND"}, fields={"MPN": "PJ-102AH", "Manufacturer": "Same Sky"})
    sh.two("Device:Fuse", "F101", "2A slow 63V", 36, 22, "Fuse:Fuse_1206_3216Metric", "+12V_JACK", "+12V_IN",
           horizontal=True, fields={"MPN": "SF-1206S200-2", "Manufacturer": "Bourns"})
    sh.ic("Transistor_FET:Q_PMOS_GSD", "Q101", "Si2319DDS", 58, 23, "Package_TO_SOT_SMD:SOT-23",
          {"3": "+12V_IN", "2": "+12V", "1": "RPP_GATE"}, rot=90,
          ref_at=(P(58, 23)[0] + 1.0 * U, P(58, 23)[1] + 0.6 * U, "right"),
          val_at=(P(58, 23)[0] + 1.0 * U, P(58, 23)[1] + 1.6 * U, "right"),
          fields={"MPN": "Si2319DDS-T1-GE3", "Manufacturer": VISHAY})
    _diode(sh, "Device:D_Zener", "D101", "BZT52C12", 74, 23, "Diode_SMD:D_SOD-123", "+12V", "RPP_GATE", "1",
           fields={"MPN": "BZT52C12-E3-08", "Manufacturer": VISHAY})
    sh.R("R101", "100k", 84, 23, "RPP_GATE", "GND")
    _diode(sh, "Device:D_Zener", "D102", "SMBJ18A", 94, 23, "Diode_SMD:D_SMB", "+12V", "GND", "1",
           fields={"MPN": "SMBJ18A-E3/52", "Manufacturer": VISHAY})
    sh.tp("TP101", "+12V", 106, 21)
    sh.flag("+12V", 114, 21)

    # ---- +12V -> +5V
    # bulk capacitor at the input: damps the hot-plug ringing of the cable against the ceramic capacitors
    sh.two("Device:C_Polarized", "C114", "100uF 35V", 122, 22, "Capacitor_SMD:CP_Elec_6.3x7.7", "+12V", "GND", first="1",
           fields={"Rating": "aluminium electrolytic, 35 V"})
    # 0 ohm links (user 2026-11-20): each regulator output and each LDO input can be opened for bring-up
    sh.title("Bring-up links: regulator outputs", 128, 9)
    sh.link("R110", "+5V_REG", "+5V", 134, 15, "R1206")
    sh.link("R111", "+3V3_REG", "+3V3", 150, 15, "R1206")

    sh.title("+12V to +5V, 2 A: LMR51420XF (500 kHz, forced PWM)", 6, 35)
    sh.rails = {"+5V": "+5V_REG"}
    sh.note("VOUT = 0.6 V x (1 + R102 / R103) = 4.98 V.  L101: ripple 0.58 A at 12 V, 0.72 A at 18 V; saturation 7 A is above the 5.1 A current limit.  EN tied to VIN (always on).", 6, 37)
    sh.note("C105-C107: about 54 uF at 5 V bias; the worst overshoot (inductor energy at current limit) stays near 5.5 V, the TPS62A02 abs max is 6.5 V.  SW_5V, +12V, +5V: copper regions.", 6, 39)
    sh.ic(lmr, "U101", "LMR51420XFDDCR", 18, 49, SOT23_6,
          {"3": "+12V", "5": "+12V", "6": "BOOT_5V", "2": "SW_5V", "4": "FB_5V", "1": "GND"},
          val_at=_below(18, 49, 3),
          fields={"MPN": "LMR51420XFDDCR", "Manufacturer": TI})
    sh.two("Device:L", "L101", "10uH 3A", 38, 49, "Inductor_SMD:L_Vishay_IHLP-2525", "SW_5V", "+5V",
           horizontal=True, fields={"MPN": "IHLP2525CZER100M01", "Manufacturer": VISHAY})
    sh.C("C101", "100nF", 48, 49, "BOOT_5V", "SW_5V", fields={"Rating": "X7R 25V"})
    sh.R("R102", "100k 1%", 56, 49, "+5V", "FB_5V")
    sh.R("R103", "13.7k 1%", 64, 49, "FB_5V", "GND")
    _cap(sh, "C102", "4.7uF/50V", 74, 49, "+12V", FP["C1206"], "X7R 50V")
    _cap(sh, "C103", "4.7uF/50V", 81, 49, "+12V", FP["C1206"], "X7R 50V")
    _cap(sh, "C104", "100nF/50V", 88, 49, "+12V", FP["C0603"], "X7R 50V")
    _cap(sh, "C105", "22uF/25V", 96, 49, "+5V", C1210, "X7R 25V")
    _cap(sh, "C106", "22uF/25V", 103, 49, "+5V", C1210, "X7R 25V")
    _cap(sh, "C107", "22uF/25V", 110, 49, "+5V", C1210, "X7R 25V")
    sh.rails = {}
    sh.tp("TP102", "+5V", 118, 47)

    # ---- +5V -> +3V3
    sh.title("+5V to +3V3, 2 A: TPS62A02 (2.4 MHz); enabled by +5V", 6, 60)
    sh.note("VOUT = 0.6 V x (1 + R105 / R106) = 3.315 V.  VIN abs max 6.5 V, recommended 5.5 V max.  PG (open drain) is not used.", 6, 62)
    sh.note("Enable chain: +5V -> EN_3V3, +3V3 -> EN_3V3A, +3V3A -> EN_1V8, each through 10 k so the 1.0 mm pad can be pulled to GND on the bench.", 6, 64)
    sh.ic("Regulator_Switching:TPS62A02PDDC", "U102", "TPS62A02PDDCR", 18, 74, SOT23_6,
          {"4": "+5V", "1": "EN_3V3", "3": "SW_3V3", "6": "FB_3V3", "5": NC, "2": "GND"},
          val_at=_below(18, 74, 2),
          fields={"MPN": "TPS62A02PDDCR", "Manufacturer": TI})
    sh.two("Device:L", "L102", "1uH 4.5A", 38, 74, "Inductor_SMD:L_Vishay_IHLP-1616", "SW_3V3", "+3V3_REG",
           horizontal=True, fields={"MPN": "IHLP1616BZER1R0M11", "Manufacturer": VISHAY})
    sh.R("R104", "10k", 48, 74, "+5V", "EN_3V3")
    sh.R("R105", "100k 1%", 56, 74, "+3V3_REG", "FB_3V3")
    sh.R("R106", "22.1k 1%", 64, 74, "FB_3V3", "GND")
    _cap(sh, "C108", "10uF/16V", 74, 74, "+5V", FP["C0805"], "X7R 16V")
    _cap(sh, "C109", "22uF/16V", 81, 74, "+3V3_REG", FP["C1206"], "X7R or X5R 16V")
    sh.tp("TP103", "+3V3", 89, 72)
    sh.tp("TP106", "EN_3V3", 96, 72, kind="TP_1.0")
    sh.R("R107", "470R", 114, 74, "+3V3", "LED_3V3")
    _diode(sh, "Device:LED", "D103", "green", 122, 74, FP["LED0603"], "LED_3V3", "GND", "2",
           fields={"MPN": "VLMG1300-GS08", "Manufacturer": VISHAY})

    # ---- LDOs
    sh.title("+5V to +3V3A (codec AVDD / DRVDD) and +3V3 to +1V8 (codec DVDD): TPS7A20, 300 mA", 6, 85)
    sh.note("Power-up order for the codec: +3V3 (IOVDD), then +3V3A, then +1V8.  Power-down order is not controlled.  U103 dissipates about 0.11 W.", 6, 87)
    sh.title("Bring-up links: LDO inputs", 128, 60)
    sh.link("R112", "+5V", "+5V_LDO", 134, 66, "R0805")
    sh.link("R113", "+3V3", "+3V3_LDO", 150, 66, "R0805")
    for ref, val, i, vin, en, out, r, cin, cout in (
            ("U103", "TPS7A2033PDBVR", 18, "+5V_LDO", "EN_3V3A", "+3V3A", "R108", "C110", "C111"),
            ("U104", "TPS7A2018PDBVR", 82, "+3V3_LDO", "EN_1V8", "+1V8", "R109", "C112", "C113")):
        sh.ic("Regulator_Linear:TPS7A20xxxDBV", ref, val, i, 95, SOT23_5,
              {"1": vin, "3": en, "5": out, "2": "GND"}, val_at=_below(i, 95, 2),
              fields={"MPN": val, "Manufacturer": TI})
        sh.R(r, "10k", i + 14, 95, {"EN_3V3A": "+3V3", "EN_1V8": "+3V3A"}[en], en)
        _cap(sh, cin, "1uF", i + 22, 95, vin, FP["C0603"], "X7R 10V")
        _cap(sh, cout, "2.2uF", i + 29, 95, out, FP["C0603"], "X7R 10V")
    sh.tp("TP104", "+3V3A", 55, 93)
    sh.tp("TP107", "EN_3V3A", 62, 93, kind="TP_1.0")
    sh.tp("TP105", "+1V8", 119, 93)
    sh.tp("TP108", "EN_1V8", 126, 93, kind="TP_1.0")

    # ---- ground test loops and the ground flag
    sh.title("GND test loops, GND flag", 130, 35)
    sh.note("Power area, next to the codec,", 130, 37)
    sh.note("next to MCU and SDRAM.", 130, 39)
    for k, ref in enumerate(("TP109", "TP110", "TP111")):
        sh.ic("Connector:TestPoint", ref, "GND", 132 + 6 * k, 47, FP["TP_LOOP"], {"1": "GND"}, stub=1,
              fields={"MPN": "5001", "Manufacturer": "Keystone"})
    sh.flag("GND", 151, 47)
