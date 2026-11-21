"""Page 6: audio codec and the two 3.5 mm jacks (SPEC 2.2, 3, 4, 5).

TLV320AIC3104IRHBR, TI SLAS510G (Feb 2021), read from the rendered pages:
  Pins, RHB package (p.5-6, Table 7-1; thermal pad to DRVSS, note under Figure 7-1; pad 33 on drawing p.100):
    1 MCLK in, 2 BCLK io, 3 WCLK io, 4 DIN in, 5 DOUT out, 6 DVSS, 7 IOVDD (1.1-3.6 V), 8 SCL, 9 SDA,
    10 MIC1LP/LINE1LP, 11 MIC1LM/LINE1LM, 12 MIC1RP/LINE1RP, 13 MIC1RM/LINE1RM, 14 MIC2L/LINE2L/MICDET,
    15 MICBIAS, 16 MIC2R/LINE2R, 17 AVSS1, 18 DRVDD, 19 HPLOUT, 20 HPLCOM, 21 DRVSS, 22 HPRCOM, 23 HPROUT,
    24 DRVDD, 25 AVDD, 26 AVSS2, 27 LEFT_LOP, 28 LEFT_LOM, 29 RIGHT_LOP, 30 RIGHT_LOM, 31 RESET (active low),
    32 DVDD (1.525-1.95 V), 33 thermal pad.
  Supplies (p.7, 8.3): AVDD / DRVDD 2.7-3.6 V, DVDD 1.525-1.95 V, IOVDD 1.1-3.6 V. Absolute maximum AVDD to
    DRVDD is +-0.1 V (p.7, 8.1): AVDD and both DRVDD pins must be the same net (+3V3A), with nothing in series.
  No strap pins: the control port is I2C only and the address is fixed at 0011000 = 0x18 (p.45, 10.5.1); the
    part has no address or mode-select pin (pin table p.5-6), so there is nothing to strap.
  I2S direction: BCLK and WCLK are inputs after reset (slave; page 0 register 8 bits D7, D6 default 0, p.50).
    The MCU is the clock master: SAI1 block A = master transmitter (drives MCLK_A, SCK_A, FS_A, SD_A),
    block B = receiver synchronous with block A (uses A's clocks internally, only SD_B comes out to a pin).
    So SAI1_SD_A -> DIN (pin 4), DOUT (pin 5) -> SAI1_SD_B. DS12110 Rev 11 p.49 (3.34) confirms that the two
    sub-blocks can each be transmitter or receiver and run synchronously with each other; the register-level
    description (RM0433) could not be fetched, see the report (U27).
  Reset (p.22, 10.3.1): a hardware reset is required after power-up, RESET low for at least 10 ns once the
    supplies are valid; at least 1 nF from RESET to DVSS against ESD-induced resets. R603 pulls RESET low so
    the codec stays in reset while PG9 is still high-impedance; firmware drives it high.
  Decoupling (p.88, Figure 11-1): 0.1 uF + 1 uF on AVDD, on each DRVDD pin, on DVDD and on IOVDD, plus one
    10 uF on the analog rail.
  Headphone output (p.88, Figure 11-1): HPLOUT / HPROUT single-ended through a series capacitor to tip / ring,
    sleeve to ground. Figure 11-1 shows 100 uF, Figure 11-4 (p.90) 220 uF; 220 uF gives 45 Hz into the minimum
    16 ohm load (p.7) and 23 Hz into 32 ohm. The capless mode (HPLCOM / HPRCOM driving the sleeve at the
    common-mode voltage, p.42 Figure 10-18) is not used: the sleeve would sit at 1.35 V, and plugging the jack
    into grounded equipment would short it to the board ground. Output common mode is positive (1.35 V setting in the p.9-10 test conditions, programmable, p.34), so the
    capacitor's + side faces the codec. HPLCOM / HPRCOM stay unconnected; firmware sets page 0 register 14
    for AC-coupled drive (p.40, p.54).
  Line input (p.88, Figure 11-1): MIC2L/LINE2L and MIC2R/LINE2R, single-ended, 0.47 uF in series (the figure's
    "FM tuner" stereo line source). Full scale is 0.707 Vrms (p.7), input resistance 20 kohm at 0 dB input
    level (p.8), and the pins have clamp diodes to AVDD / AVSS (p.41, 10.3.8). A consumer line source is up to
    2 Vrms, so each channel has a 10k / 5.6k divider (x 0.36) in front of the capacitor; this is a design
    choice, not from the datasheet. High-pass corner with 0.47 uF: about 14 Hz.
  Unused pins: line inputs not selected are high-impedance by default (p.41); powered-down line outputs are
    high-impedance (p.39), powered-down high-power outputs are high-impedance or weakly driven (p.40); MICBIAS
    is powered down by default (register 25, p.58). They are left unconnected. The datasheet has no explicit
    "leave open" statement for unused pins.
  Supply sequence (p.91, section 12): IOVDD first, AVDD / DRVDD second, DVDD last (AVDD to DVDD 0-5 ms), RESET
    low until all are stable, analog supplies >= DVDD at all times. Power-up follows the enable chain of
    SPEC 4; power-down is not controlled (U29).

SJ-3523-SMT, Same Sky drawing sj-352x-smt.pdf rev 1.07 p.2: terminal 1 = sleeve, 2 = tip, 3 = ring, 4 not
  populated on the -3523 (no switch). The stock footprint Jack_3.5mm_CUI_SJ-3523-SMT_Horizontal has pads named
  S, T, R at the positions and sizes of lands 1, 2, 3 of the recommended layout (2.8 x 2.2, 2.8 x 2.8,
  2.8 x 2.2 mm; two 1.7 mm locating holes 7 mm apart) and no land 4; the stock symbol AudioJack3 uses the same
  pin numbers S, T, R.

293D227X96R3D2TE3, Vishay 293D (doc 40002, rev 02-Jul-2025) p.1 ordering code, p.5 ratings: 220 uF, 6.3 V,
  case D (7343-31), max leakage 13.2 uA at rated voltage. R604 / R605 hold the jack side at 0 V.
"""
from .common import FP, NC, P, kisch, symbol

CODEC_FP = "Package_DFN_QFN:Texas_RHB0032E_VQFN-32-1EP_5x5mm_P0.5mm_EP3.45x3.45mm"
JACK_FP = "Connector_Audio:Jack_3.5mm_CUI_SJ-3523-SMT_Horizontal"
TANT_D = "Capacitor_Tantalum_SMD:CP_EIA-7343-31_Kemet-D"


def codec_symbol():
    _ = None
    return symbol(
        "TLV320AIC3104IRHB", ref="U", footprint=CODEC_FP,
        datasheet="https://www.ti.com/lit/ds/symlink/tlv320aic3104.pdf",
        description="Stereo audio codec, I2S, I2C control, VQFN-32 (pins from SLAS510G p.5-6)",
        left=[_, (1, "MCLK", "input"), (2, "BCLK", "bidirectional"), (3, "WCLK", "bidirectional"),
              (4, "DIN", "input"), (5, "DOUT", "output"), _,
              (8, "SCL", "bidirectional"), (9, "SDA", "bidirectional"), _,
              (31, "~{RESET}", "input"), _, _, _, _, _, _, _, _],
        right=[(10, "MIC1LP/LINE1LP", "passive"), (11, "MIC1LM/LINE1LM", "passive"),
               (12, "MIC1RP/LINE1RP", "passive"), (13, "MIC1RM/LINE1RM", "passive"),
               (14, "MIC2L/LINE2L/MICDET", "passive"), (16, "MIC2R/LINE2R", "passive"),
               (15, "MICBIAS", "passive"), _,
               (19, "HPLOUT", "passive"), (20, "HPLCOM", "passive"),
               (22, "HPRCOM", "passive"), (23, "HPROUT", "passive"), _,
               (27, "LEFT_LOP", "passive"), (28, "LEFT_LOM", "passive"),
               (29, "RIGHT_LOP", "passive"), (30, "RIGHT_LOM", "passive"), _, _],
        top=[(7, "IOVDD", "power_in"), _, _, (32, "DVDD", "power_in"), _, _,
             (25, "AVDD", "power_in"), (18, "DRVDD", "power_in"), (24, "DRVDD", "power_in")],
        bottom=[(6, "DVSS", "power_in"), (17, "AVSS1", "power_in"), (26, "AVSS2", "power_in"),
                (21, "DRVSS", "power_in"), (33, "EP", "power_in")])


def build(sh):
    sh.title("Audio: TLV320AIC3104 codec (I2S slave on SAI1, I2C4 address 0x18), headphone out, line in", 6, 8)

    # ---- codec
    sh.title("Codec", 34, 13)
    sh.ic(codec_symbol(), "U601", "TLV320AIC3104IRHBR", 62, 46, CODEC_FP, {
        "1": "SAI1_MCLK_A", "2": "SAI1_SCK_A", "3": "SAI1_FS_A",
        "4": "SAI1_SD_A",                 # DIN  <- block A, master transmitter
        "5": "SAI1_SD_B",                 # DOUT -> block B, synchronous receiver
        "8": "I2C4_SCL", "9": "I2C4_SDA", "31": "CODEC_NRST",
        "10": NC, "11": NC, "12": NC, "13": NC, "15": NC,
        "14": "LINE2L", "16": "LINE2R",
        "19": "HPLOUT", "23": "HPROUT", "20": NC, "22": NC,
        "27": NC, "28": NC, "29": NC, "30": NC,
        "7": "+3V3", "32": "+1V8", "25": "+3V3A", "18": "+3V3A", "24": "+3V3A",
        "6": "GND", "17": "GND", "26": "GND", "21": "GND", "33": "GND",
    }, stub=3, fields={"MPN": "TLV320AIC3104IRHBR", "Manufacturer": "Texas Instruments"},
        val_at=(P(66, 59)[0], P(66, 59)[1], "left"))

    # ---- I2C pull-ups, reset
    sh.title("I2C4 pull-ups", 8, 13)
    sh.R("R601", "2.2k", 12, 20, "+3V3", "I2C4_SCL")
    sh.R("R602", "2.2k", 20, 20, "+3V3", "I2C4_SDA")
    sh.title("Codec reset", 8, 35)
    sh.R("R603", "10k", 12, 46, "CODEC_NRST", "GND")
    sh.C("C612", "1nF", 20, 46, "CODEC_NRST")

    # ---- decoupling, one group per supply pin (Figure 11-1)
    sh.title("Codec decoupling: IOVDD (7)   DVDD (32)   AVDD (25), DRVDD (18), DRVDD (24), bulk", 8, 70)
    sh.caps(601, ["100nF", "1uF"], 10, 78, "+3V3", step=5)
    sh.caps(603, ["100nF", "1uF"], 24, 78, "+1V8", step=5)
    sh.caps(605, ["100nF", "1uF", "100nF", "1uF", "100nF", "1uF", "10uF"], 38, 78, "+3V3A", step=5)

    # ---- headphone output
    sh.title("Headphone output, AC-coupled", 98, 13)
    hp = {"MPN": "293D227X96R3D2TE3", "Manufacturer": "Vishay"}
    sh.two("Device:C_Polarized", "C613", "220uF 6.3V", 104, 26, TANT_D, "HPLOUT", "HP_L_JACK", fields=hp)
    sh.two("Device:C_Polarized", "C614", "220uF 6.3V", 116, 26, TANT_D, "HPROUT", "HP_R_JACK", fields=hp)
    sh.R("R604", "4.7k", 128, 26, "HP_L_JACK", "GND")
    sh.R("R605", "4.7k", 138, 26, "HP_R_JACK", "GND")
    jack = {"MPN": "SJ-3523-SMT-TR", "Manufacturer": "Same Sky"}
    sh.ic("Connector_Audio:AudioJack3", "J601", "SJ-3523-SMT", 144, 42, JACK_FP,
          {"T": "HP_L_JACK", "R": "HP_R_JACK", "S": "GND"}, rot=180, fields=jack)

    # ---- line input
    sh.title("Line input, 2 Vrms max at the jack, divided to 0.7 Vrms", 98, 55)
    sh.ic("Connector_Audio:AudioJack3", "J602", "SJ-3523-SMT", 144, 64, JACK_FP,
          {"T": "LINEIN_L_JACK", "R": "LINEIN_R_JACK", "S": "GND"}, rot=180, fields=jack)
    sh.C("C615", "470nF X7R", 108, 74, "LINE2L", "LINEIN_L", fp=FP["C0603"], horizontal=True)
    sh.R("R606", "10k", 132, 74, "LINEIN_L", "LINEIN_L_JACK", horizontal=True)
    sh.C("C616", "470nF X7R", 108, 80, "LINE2R", "LINEIN_R", fp=FP["C0603"], horizontal=True)
    sh.R("R607", "10k", 132, 80, "LINEIN_R", "LINEIN_R_JACK", horizontal=True)
    sh.R("R608", "5.6k", 102, 93, "LINEIN_L", "GND")
    sh.R("R609", "5.6k", 112, 93, "LINEIN_R", "GND")

    # ---- notes
    n = [
        "U601 pins: TI SLAS510G p.5-6. Thermal pad (33) to DRVSS = GND. I2C address fixed 0x18, no strap pins. AVDD and DRVDD: same net.",
        "I2S: MCU is master. SAI1 block A (master TX) drives MCLK, SCK, FS and SD_A -> DIN; DOUT -> SD_B (block B, synchronous RX).",
        "R603 holds the codec in reset until firmware drives CODEC_NRST (PG9) high; a hard reset after power-up is required (p.22).",
        "R601, R602: the only pull-ups on I2C4 (codec 0x18 here, touch panel 0x38 on the LCD page).",
        "C613, C614: tantalum, + to the codec (output common mode 1.35 V). 220 uF: 45 Hz into 16 ohm, 23 Hz into 32 ohm.",
        "HPLCOM, HPRCOM, line outputs, LINE1 inputs, MICBIAS: not used, left open (powered down = high impedance).",
        "Supply order (p.91): IOVDD (+3V3), then AVDD / DRVDD (+3V3A), then DVDD (+1V8); set by the enable chain on the power page.",
        "Jacks J601, J602: T = tip = left, R = ring = right, S = sleeve = GND (Same Sky terminals 2, 3, 1).",
    ]
    for k, s in enumerate(n):
        sh.note(s, 6, 89 + 2 * k)
