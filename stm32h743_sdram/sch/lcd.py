"""Page 7: LCD FPC connector, touch links, backlight boost (SPEC 2.2, 2.3, 3, 4, 10).

Sources (PDFs in datasheet/, read from rendered page images, text layer as cross-check, PROC-14):
  [OM]  Omron XF3M/XF2M catalogue G146-E1-05 (0325): p.6 "Dual sided Contact", 0.5 mm pitch, 0.5 A, FPC 0.3 mm
        thick; p.7 dimension drawing and "PCB Dimensions (TOP VIEW)".
  [RK]  Rocktech RK043FN48H-CT672B spec v1.0 2015-03-09 (mirror wiki.kewl.org): p.6 VDD 3.0-3.6 V, backlight
        VF 15/16/17 V at IF 40 mA; p.11 pin table; p.12 timing; p.15 power sequence; p.16 outline: LED circuit
        5 in series x 2 strings, FPC pitch 0.8 mm (P 0.8 x 39 = 31.2).
  [IN]  Innolux AT043TN24 V.7, spec A043-24-TT-71 ver 02 2018-04-12 (mirror community.nxp.com): p.2-4 pin
        tables; p.5 LED 25 mA abs max; p.6 VDD 3.1-3.5 V, IVDD 17 / 25 mA, backlight VL 25.2/27.9/31.5 V at
        IL 18/20/22 mA; p.7 power sequence; p.20 FPC 0.5 x 39 = 19.5, width 20.5, thickness 0.3 mm.
  [TPS] TI TPS61169 SNVSA40B (rev. June 2024): p.3 pins; p.4 abs max (SW 40 V, CTRL 7 V), recommended L 4.7-10 uH,
        CI >= 1 uF, CO 1-10 uF, PWM 5-100 kHz; p.5 VREF 188/204/220 mV, CTRL VH 1.2 V, VL 0.4 V, internal
        pull-down 300 k, low > 2.5 ms = shutdown, fSW 0.75/1.2/1.5 MHz, ILIM 1.2/1.8/2.4 A (0.72 A in soft start),
        OVP 36/37.5/39 V; p.8 open-LED protection; p.9 ILED = VFB / RSET, VFB = duty x 204 mV; p.11 typical
        application (4.7 uH, CIN 4.7 uF, COUT 1 uF, RSET 10.2 ohm = 20 mA); p.12 equations 3-5, inductor table,
        diode (onsemi NSR0240 recommended); p.13 COUT 1-4.7 uF.
  [L]   Coilcraft LPS4018, Document 435-1 rev. 02/23/22 p.1: LPS4018-472MR_ 4.7 uH +-20 %, DCR 0.125 ohm max,
        Isat 1.8 A (10 % drop), Irms 1.3 A (20 C rise), SRF 65 MHz.
  [D]   Diodes Inc B160S1F DS37031 rev. 5-2 (Mar 2018) p.1-2: SOD123F, cathode band = pad 1, VRRM 60 V, IO 1 A,
        IFSM 30 A, VF 0.53 V typ at 1 A, IR 20 uA typ / 200 uA max at 60 V 25 C, 45 pF at 4 V. (60 V: user 2026-11-20.)

J701 Omron XF2M-4015-1A. [OM] p.7: seen from above with the solder tails up and the FPC opening down,
terminal 1 is at the left end. Stock footprint Omron_XF2M-4015-1A_1x40-1MP_P0.5mm_Horizontal compared with the
PCB drawing: pads 0.25 x 1.1 at 0.5 pitch, A = 19.5; hold-down pads 1.7 x 1.5, F = 21.1, G = 24.5, 2.6 between
the rows; pad 1 at the left with the opening down. All equal. Its description says "top-side contacts"; the
catalogue says dual-sided (p.6). The footprint has pads 1..40 and two pads "MP"; the project symbol has the same.
Connector pad k carries panel pin 41 - k (SPEC 10). Pin names in the symbol are "P<panel pin> <signal>".

Panel pins, [RK] p.11 / [IN] p.2-3 (identical unless two names are given):
  1 LED cathode, 2 LED anode, 3 GND, 4 VDD, 5-12 R0-R7, 13-20 G0-G7, 21-28 B0-B7, 29 GND, 30 DCLK, 31 DISP
  (1 = on, 0 = standby), 32 HSYNC / NC, 33 VSYNC / NC, 34 DE, 35 GND / NC, 36 GND,
  37 RESET / X1, 38 INT / Y1, 39 SCL / X2, 40 SDA / Y2 (Rocktech capacitive touch / Innolux resistive touch).

Choices:
  - Unused colour bits R0-R2, G0-G1, B0-B2 go to GND at the connector. Neither datasheet says what to do with
    them; they are CMOS inputs and must not float. GND costs 3 % of full scale (white = 248/252/248) and keeps
    eight lines out of the 0.5 mm breakout; tying them to the MSBs would add a second load and a stub to eight
    LTDC lines that already cross.
  - R705 pulls DISP low: the panel stays in standby while PG14 floats during reset. [IN] p.7 order is VDD,
    interface signals, DISP, then the LED supply at least 160 ms after DISP.
  - R706 pulls CTRL low (PB5 floats during reset): backlight off. The chip has 300 k inside as well ([TPS] p.5).
  - R708 = 10.2 ohm (TI example value, user 2026-11-20): 204 mV / 10.2 = 20.0 mA (18.4 .. 21.6 mA over the VREF range). 5.1 ohm gives 40 mA, for the
    Rocktech panel only (two strings); the Innolux string is rated 22 mA, 25 mA absolute.
  - R707 (DNP). [TPS] p.8: with the LED string open the output rises to the OVP threshold, then the chip
    latches off until CTRL is toggled; the output falls back to VIN. A dummy load is not needed for
    protection. The position is kept (SPEC 4) across the LED string, LED_A to LED_K, where it can stand in
    for the panel on the bench: 330 ohm regulates at 20.4 mA x 340 = 6.9 V, 0.14 W. A value that lets the
    output reach OVP while FB stays above 30 mV (about 1.8 k to 13 k) would defeat the protection.
  - C705 2.2 uF 50 V: output reaches 39 V with no panel; 2.2 uF so that about 1 uF is left at 28 V bias
    (the bias figure is from memory, not from a Murata curve).

Inductor arithmetic ([TPS] eq. 3-5; VIN = 5 V, VOUT = VLED + 0.2 V):
  ripple if continuous, dI = 1 / (L x fSW x (1/(VOUT - VIN) + 1/VIN)); input current IDC = VOUT x IOUT / (VIN x eff).
  Rocktech 16.2 V: 4.7 uH, 1.2 MHz -> dI = 0.61 A; IDC = 0.076 A at 20 mA (eff 0.85), 0.15 A at 40 mA.
  Innolux 28.1 V:  4.7 uH, 1.2 MHz -> dI = 0.73 A; IDC = 0.13 A at 20 mA.
  IDC < dI / 2 in every case, so the converter runs discontinuous and the peak is sqrt(2 x IDC x dI):
  Rocktech 20 mA 0.31 A, Rocktech 40 mA 0.43 A, Innolux 20 mA 0.44 A.
  Worst case (L - 20 %, fSW 0.75 MHz, eff 0.8): Innolux 31.7 V 22 mA -> IDC 0.17 A, dI 1.49 A, peak 0.72 A;
  Rocktech 17.2 V 40 mA -> IDC 0.17 A, dI 1.26 A, peak 0.66 A.
  LPS4018-472: Isat 1.8 A, 2.5 times the worst peak and equal to the typical switch limit (1.8 A).
  10 uH would halve the ripple (0.29 / 0.34 A, peak 0.21 / 0.30 A at 20 mA) but [TPS] p.12 recommends
  4.7 uH for inputs of 5 V and above (peak current and loop stability) and its application circuit uses 4.7 uH.
  D701: mean current = LED current (20-40 mA); worst peak 0.72 A against 1 A average rating; VRRM 60 V against OVP 39 V max.
"""
from .common import FP, NC, symbol

# panel pin -> (Rocktech name, Innolux name, net).  LCD_P37..40 are the panel side of the 0 ohm links.
PANEL = {
    1: ("K (LED-)", "VLED-", "LED_K"), 2: ("A (LED+)", "VLED+", "LED_A"), 3: ("GND", "GND", "GND"), 4: ("VDD", "VDD", "+3V3_LCD"),
    29: ("GND", "GND", "GND"), 30: ("DCLK", "CLK", "LCD_CLK"), 31: ("DISP", "DISP", "LCD_DISP"),
    32: ("HSYNC", "NC", "LCD_HSYNC"), 33: ("VSYNC", "NC", "LCD_VSYNC"), 34: ("DE", "DE", "LCD_DE"),
    35: ("GND", "NC", NC), 36: ("GND", "GND", "GND"),
    37: ("RESET", "X1", "LCD_P37"), 38: ("INT", "Y1", "LCD_P38"), 39: ("SCL", "X2", "LCD_P39"), 40: ("SDA", "Y2", "LCD_P40"),
}
for _base, _col, _first in ((5, "R", 3), (13, "G", 2), (21, "B", 3)):      # first colour bit driven by the MCU
    for _b in range(8):
        PANEL[_base + _b] = ("%s%d" % (_col, _b),) * 2 + ("LCD_%s%d" % (_col, _b) if _b >= _first else "GND",)

LINKS = [("R701", 37, "TP_RST"), ("R702", 38, "TP_INT"), ("R703", 39, "I2C4_SCL"), ("R704", 40, "I2C4_SDA")]


def _pin_name(p):
    rk, inx, _net = PANEL[p]
    rk = {"K (LED-)": "LED-", "A (LED+)": "LED+"}.get(rk, rk)
    return "P%d %s" % (p, rk if rk == inx or p <= 2 else rk + "/" + inx)


def build(sh):
    # ---- connector
    sh.title("LCD FPC connector: pad k = panel pin 41 - k", 6, 9)
    sh.title("Bring-up links: panel 3.3 V, backlight 5 V", 62, 9)
    sh.link("R709", "+3V3", "+3V3_LCD", 68, 15, "R0603")
    sh.link("R710", "+5V", "+5V_BL", 84, 15)
    sh.rails = {"+3V3": "+3V3_LCD", "+5V": "+5V_BL"}
    pads = [(k, _pin_name(41 - k), "passive") for k in range(1, 41)]
    j701 = symbol("XF2M-4015-1A_LCD", right=pads + [None, ("MP", "MP", "passive")], ref="J",
                  description="Omron XF2M-4015-1A, 40 pin 0.5 mm FPC connector, dual-sided contacts; pin names are the panel pins")
    nets = {str(k): PANEL[41 - k][2] for k in range(1, 41)}
    nets["MP"] = "GND"
    sh.ic(j701, "J701", "XF2M-4015-1A", 14, 34.5, "Connector_FFC-FPC:Omron_XF2M-4015-1A_1x40-1MP_P0.5mm_Horizontal",
          nets, stub=3, fields={"MPN": "XF2M-4015-1A", "Manufacturer": "Omron"})
    sh.note("Pin number = connector pad; pin name = P<panel pin> <signal>.", 6, 60)
    sh.note("Pad 1 is at the left end, seen from above with the opening down.", 6, 62)
    sh.note("MP = the two hold-down pads.  Panel pin 35 is left open.", 6, 64)

    # ---- touch links
    sh.title("Touch links (0R)", 42, 9)
    for n, (ref, pin, net) in enumerate(LINKS):
        sh.R(ref, "0R", 52, 14 + 4 * n, "LCD_P%d" % pin, net, horizontal=True)
    sh.note("I2C4 pull-ups are on the audio page.", 40, 30)

    # ---- panel supply and DISP
    sh.title("Panel supply, DISP default", 40, 36)
    sh.R("R705", "10k", 46, 46, "LCD_DISP", "GND")
    sh.caps(701, ["100nF", "4.7uF"], 58, 46, "+3V3", step=7)

    # ---- backlight boost
    sh.title("Backlight boost: +5V to the LED string, constant current, PWM dimming", 40, 58)
    u701 = symbol("TPS61169", left=[(5, "VIN", "power_in"), (4, "CTRL", "input"), (2, "GND", "power_in")],
                  right=[(1, "SW", "passive"), None, (3, "FB", "input")],
                  description="TI TPS61169 38 V boost WLED driver, SC70-5")
    sh.C("C703", "4.7uF", 44, 70, "+5V")
    sh.C("C704", "100nF", 50, 70, "+5V")
    sh.R("R706", "100k", 57, 70, "LCD_BL_PWM", "GND")
    sh.ic(u701, "U701", "TPS61169DCKR", 75, 70, "Package_TO_SOT_SMD:SOT-353_SC-70-5",
          {"5": "+5V", "4": "LCD_BL_PWM", "1": "SW_BL", "3": "LED_K", "2": "GND"},
          fields={"MPN": "TPS61169DCKR", "Manufacturer": "Texas Instruments"})
    sh.two("Device:L", "L701", "4.7uH 1.8A", 94, 65, "Inductor_SMD:L_Coilcraft_LPS4018", "+5V", "SW_BL", horizontal=True,
           fields={"MPN": "LPS4018-472MRC", "Manufacturer": "Coilcraft"})
    sh.ic("Device:D_Schottky", "D701", "B160S1F 60V 1A", 94, 74, "Diode_SMD:D_SOD-123F",
          {"2": "SW_BL", "1": "LED_A"}, rot=180, fields={"MPN": "B160S1F-7", "Manufacturer": "Diodes Inc"})
    sh.C("C705", "2.2uF 50V X7R", 108, 70, "LED_A", fp=FP["C1206"])
    sh.R("R707", "330R DNP", 120, 70, "LED_A", "LED_K", fp="Resistor_SMD:R_1206_3216Metric", dnp=True)
    sh.R("R708", "10.2R 1%", 130, 70, "LED_K", "GND", fp=FP["R0603"])
    sh.tp("TP701", "LED_A", 140, 70)

    # ---- per-pin table, one row per pin, one text item per cell
    sh.title("Pin table", 100, 9)
    cols = (100, 105, 111, 122, 133)
    for x, head in zip(cols, ("Pad", "Panel", "Rocktech RK043FN48H", "Innolux AT043TN24", "Net on this board")):
        sh.note(head, x, 11.5)
    for k in range(1, 41):
        p = 41 - k
        rk, inx, net = PANEL[p]
        if net is NC:
            net = "not connected"
        elif net.startswith("LCD_P"):
            ref, _p, far = LINKS[p - 37]
            net = "%s, %s 0R to %s" % (net, ref, far)
        elif net == "GND" and rk != "GND":
            net = "GND (colour bit not driven)"
        for x, cell in zip(cols, (str(k), str(p), rk, inx, net)):
            sh.note(cell, x, 12 + k)
    sh.note("Rocktech RK043FN48H-CT672B spec v1.0 p.11; Innolux AT043TN24 V.7 spec A043-24-TT-71 ver 02 p.2-3 (both read from mirror copies).", 100, 54.5)

    # ---- notes
    y = 84
    for line in (
        "Colour: RGB565 on the upper bits. Panel R0-R2, G0-G1, B0-B2 are tied to GND at the connector (CMOS inputs, must not float; the datasheets give no rule). Full white is 248/252/248.",
        "R705: DISP low = standby while PG14 floats in reset. Power-on order (Innolux p.7): VDD, LTDC signals within 100 ms, DISP high, backlight at least 160 ms after DISP; reverse order for power-off.",
        "R706: CTRL low = backlight off while PB5 floats in reset (the chip also has 300k inside). CTRL low for 2.5 ms = shutdown. PWM 5-100 kHz; LED current = duty x 204 mV / R708 (analog dimming).",
        "R708: 10.2R = 20.0 mA (18.4-21.6 mA), safe for both panels (Rocktech 2 strings x 5 LED, 16 V, 40 mA typ; Innolux 1 string, 27.9 V, 20 mA typ, 22 mA max). 5.1R = 40 mA: Rocktech only.",
        "No panel or open string: LED_A rises to the OVP threshold (36-39 V), then U701 latches off until CTRL goes low and high again. C705 is 50 V, D701 60 V. Without a panel LED_A sits at +5V minus the diode drop.",
        "R707 (DNP) is not needed for protection. It is a bench load in place of the LED string: 330R with R708 = 10R gives 6.9 V, 0.14 W. Do not fit 1.8k-13k: FB stays above 30 mV and the open-LED protection no longer trips.",
        "L701 4.7 uH: discontinuous at these loads; peak 0.31 A (Rocktech 20 mA), 0.44 A (Innolux 20 mA), 0.72 A worst case; Isat 1.8 A. D701: 1 A, VRRM 60 V.",
        "Innolux AT043TN24: pins 37-40 are the resistive touch film (X1, Y1, X2, Y2): remove R701-R704, or the film ties TP_RST to I2C4_SCL and TP_INT to I2C4_SDA. Its pins 32, 33 are NC (DE mode only).",
        "The connector takes a 0.5 mm pitch FPC, 20.5 mm wide, 0.3 mm thick, contacts on either side (Innolux drawing p.20 matches). The Rocktech -CT672B tail is 0.8 mm pitch (outline p.16) and does not fit; only its pin order is used.",
    ):
        sh.note(line, 6, y)
        y += 2
