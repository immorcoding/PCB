"""Page 2: MCU STM32H743IIK6, UFBGA176+25 (SPEC 2.1, 3, 4).

IO assignment comes from ../pins.csv (ball -> signal); the 13 free IOs are left unconnected.
The supply, reset, boot and oscillator circuits are filled in by build(); the facts they rest on:

FACTS (DS12110 Rev 11, Jan 2026; AN4938 Rev 7; AN2867 Rev 25; read from rendered pages, 2026-11-20)
  Balls     All 201 balls of the KiCad symbol STM32H743IIKx equal DS12110 Figure 10 (p.60): 0 differences.
  VDD       100 nF per VDD ball (13) + one 4.7 uF for the package (DS Figure 15 p.102). VBAT tied to VDD with
            100 nF (AN4938 p.12). VDD33USB: 1 uF + 100 nF, must be supplied even when USB is unused (DS Table 11
            note 1 p.103). PDR_ON high = internal supervisor on (AN4938 p.17).
  VCAP      2.2 uF, ESR < 100 mOhm, on each ball (DS Table 15 p.106). AN4938 p.12 also says "connect VCAP1 pin
            to VCAP2 pin"; the two balls (F13, M10) are kept as two nets here as the SPEC has them, each with
            its own capacitor -- open question for the user (they are one node inside the package).
  VDDA      100 nF + 1 uF, from VDD through a ferrite bead (AN4938 p.13); VREF+ may be tied to VDDA (AN4938
            p.12) and gets its own 100 nF + 1 uF. VREF- and VSSA to ground (DS Figure 15).
  NRST      Permanent internal pull-up 30 / 40 / 50 kOhm (DS Table 55 p.144): no external pull-up; 100 nF to
            ground and a push-button (DS Figure 23).
  BOOT0     No internal pull documented; 10 k to ground. BOOT0 = 0 boots from user flash (AN4938 Table 2 p.25).
  HSE       4-48 MHz, Gm_crit_max 1.5 mA/V (DS Table 34 p.125). Abracon ABM8 25 MHz with CL 10 pF, ESR 50 Ohm
            max, C0 3 pF max: gm_crit = 4 * 50 * (2 pi 25e6)^2 * (13 pF)^2 = 0.83 mA/V, margin 1.8 (the standard
            18 pF version would need 2.18 mA/V and fail). Load capacitors 2 * CL - Cstray = 20 - 5 = 15 pF;
            pads 1 and 3 are the crystal, 2 and 4 the case (ABM8 datasheet p.2). Same part as the PHY crystal.
  LSE       Gm_crit_max 0.5 / 0.75 / 1.7 / 2.7 uA/V for LSEDRV 00..11 (DS Table 35 p.126). Abracon
            ABS07-32.768KHZ-7-T (CL 7 pF, ESR 70 kOhm max, C0 2 pF max; on AN2867's list of crystals validated
            for STM32H7, Table 7 p.38): gm_crit = 0.80 .. 0.96 uA/V, so firmware must select LSEDRV = 10
            (medium high, margin 1.8) or 11; the two lower drive levels do not start it reliably.
            Load capacitors 2 * 7 - 4 = 10 pF.
  PC13..15  Backup-domain IOs: 3 mA and 2 MHz at most (DS Table 52 p.140, Table 53 note 2 p.142); toggling PC13
            (PHY_NRST here, static) can disturb the LSE (AN2867 7.4).
  Free IOs  PA15 (JTDI) and PB4 (NJTRST) are JTAG pins with internal pull-ups after reset; left unconnected.
  SDCLK     One 0402 series resistor at the MCU ball, 22-33 Ohm, value settled at bring-up (SPEC 9).
"""
import csv, os
from Tools.KiCadDesignTools.schematic.sheet import NC, FP

HERE = os.path.dirname(os.path.abspath(__file__))
FP_MCU = "Package_BGA:UFBGA-201_10x10mm_Layout15x15_P0.65mm"

# Non-IO balls of the UFBGA176+25 package (KiCad symbol MCU_ST_STM32H7:STM32H743IIKx; see FACTS for the
# comparison with DS12110).
SUPPLY = {
    "VDD": "+3V3",          # 13 balls
    "VSS": "GND",           # 37 balls
    "VBAT": "+3V3",         # no backup battery (SPEC 5)
    "VDD33_USB": "+3V3",    # USB not used; the ball still needs its supply (SPEC 4)
    "PDR_ON": "+3V3",       # internal power-on reset enabled (SPEC 2.1)
    "VDDA": "VDDA_MCU", "VREF+": "VDDA_MCU",
    "VSSA": "GND", "VREF-": "GND",
    "F13": "VCAP1", "M10": "VCAP2",
    "BOOT0": "BOOT0", "NRST": "NRST",
}


def io_nets():
    nets = {}
    for r in csv.DictReader(open(os.path.join(HERE, "..", "pins.csv"), encoding="utf-8")):
        nets[r["ball"]] = r["signal"] if r["group"] != "FREE" else NC
    return nets


# Part choices (see FACTS in the docstring for the arithmetic and sources)
HSE = dict(value="25MHz 10pF", mpn="ABM8-25.000MHZ-10-D2X-T", mfr="Abracon", load="15pF",
           fp="Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm")
LSE = dict(value="32.768kHz 7pF", mpn="ABS07-32.768KHZ-7-T", mfr="Abracon", load="10pF",
           fp="Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm")
BEAD = dict(value="220R@100MHz 2A", mpn="MH1608-221Y", mfr="Bourns")
RESET_SW = dict(mpn="B3U-1000P", mfr="Omron", fp="Button_Switch_SMD:SW_SPST_B3U-1000P")


def build(sh):
    x0 = 84
    nets = io_nets()
    nets.update(SUPPLY)
    sh.title("Bring-up link", x0, 97)
    sh.link("R203", "+3V3", "+3V3_MCU", x0 + 8, 101, flag_at=(x0 + 24, 99))
    sh.rails = {"+3V3": "+3V3_MCU"}
    sh.title("MCU STM32H743IIK6 (UFBGA176+25): IO from pins.csv, 127 of 140 used, 13 free IOs unconnected", 6, 4)
    sh.ic("MCU_ST_STM32H7:STM32H743IIKx", "U201", "STM32H743IIK6", 40, 62, FP_MCU, nets, stub=3,
          fields={"MPN": "STM32H743IIK6", "Manufacturer": "STMicroelectronics", "Alternate": "STM32H753IIK6, STM32H750IBK6"})

    x = x0
    sh.title("VDD decoupling: 100 nF per VDD ball (13) + VBAT + VDD33USB, bulk 4.7 uF, 1 uF at VDD33USB", x, 10)
    sh.caps(201, ["100nF"] * 8, x + 2, 18, "+3V3", step=6)
    # every capacitor under the BGA is 0402 (user 2026-11-23, try/sgsps: 0603 pads do not fit between the ball vias)
    sh.caps(209, ["100nF"] * 7 + ["1uF"], x + 2, 30, "+3V3", step=6, fp=FP["C0402"])
    sh.caps(217, ["4.7uF"], x + 50, 18, "+3V3")

    sh.title("VCAP: 2.2 uF each, ESR < 0.1 Ohm", x, 40)
    sh.C("C218", "2.2uF", x + 2, 48, "VCAP1", fp=FP["C0402"])
    sh.C("C219", "2.2uF", x + 12, 48, "VCAP2", fp=FP["C0402"])

    sh.title("Analog supply: VDDA and VREF+ from +3V3 through a bead", x + 30, 40)
    sh.two("Device:FerriteBead", "FB201", BEAD["value"], x + 32, 48, "Inductor_SMD:L_0603_1608Metric", "+3V3", "VDDA_MCU",
           fields={"MPN": BEAD["mpn"], "Manufacturer": BEAD["mfr"]})
    sh.caps(220, ["100nF", "1uF", "100nF", "1uF"], x + 42, 48, "VDDA_MCU", step=6, fp=FP["C0402"])
    sh.flag("VDDA_MCU", x + 68, 48)

    sh.title("Reset and boot", x, 60)
    sh.ic("Switch:SW_Push", "SW201", "RESET", x + 6, 68, RESET_SW["fp"], {"1": "NRST", "2": "GND"},
          fields={"MPN": RESET_SW["mpn"], "Manufacturer": RESET_SW["mfr"]})
    sh.C("C224", "100nF", x + 18, 68, "NRST")
    sh.R("R202", "10k", x + 30, 68, "BOOT0", "GND")
    sh.tp("TP201", "BOOT0", x + 38, 66, kind="TP_1.0")

    sh.title("HSE 25 MHz", x, 78)
    sh.ic("Device:Crystal_GND24", "Y201", HSE["value"], x + 10, 88, HSE["fp"],
          {"1": "HSE_IN", "3": "HSE_OUT", "2": "GND", "4": "GND"}, fields={"MPN": HSE["mpn"], "Manufacturer": HSE["mfr"]})
    sh.C("C225", HSE["load"], x + 22, 88, "HSE_IN", fp=FP["C0402"])
    sh.C("C226", HSE["load"], x + 32, 88, "HSE_OUT", fp=FP["C0402"])

    sh.title("LSE 32.768 kHz", x + 42, 78)
    sh.ic("Device:Crystal", "Y202", LSE["value"], x + 48, 88, LSE["fp"],
          {"1": "LSE_IN", "2": "LSE_OUT"}, fields={"MPN": LSE["mpn"], "Manufacturer": LSE["mfr"]})
    sh.C("C227", LSE["load"], x + 58, 88, "LSE_IN", fp=FP["C0402"])
    sh.C("C228", LSE["load"], x + 68, 88, "LSE_OUT", fp=FP["C0402"])

    sh.title("SDCLK series resistor (at the MCU ball)", x + 46, 60)
    sh.two("Device:R", "R201", "33R", x + 56, 68, FP["R0402"], "FMC_SDCLK", "FMC_SDCLK_R", horizontal=True)
