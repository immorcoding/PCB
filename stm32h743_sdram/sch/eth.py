"""Page 5: Ethernet PHY and RJ45 (SPEC 2.2, 3, 4, 5, 9).

Sources, read off the rendered pages (PROC-14); page numbers are PDF pages:
  [L] Microchip LAN8742A/LAN8742Ai DS00001989A (2015), datasheet/DS_LAN8742_00001989A.pdf
  [W] Wuerth 7499010211A WE-RJ45LAN rev 003.000 (2023-07-11), datasheet/7499010211A.pdf
  [A] Abracon ABM8 (revised 07-29-20), abracon.com/Resonators/abm8.pdf
  [B] Bourns MH series chip ferrite beads (rev 12/18), bourns.com/docs/Product-Datasheets/mh.pdf

U501 LAN8742A-CZ-TR, 24-VQFN. Pin numbers [L] p.6 (Figure 2-1) = stock symbol Interface_Ethernet:LAN8742A:
  1 VDD2A, 2 LED2/nINTSEL, 3 LED1/REGOFF, 4 XTAL2, 5 XTAL1/CLKIN, 6 VDDCR, 7 RXD1/MODE1, 8 RXD0/MODE0,
  9 VDDIO, 10 RXER/PHYAD0, 11 CRS_DV/MODE2, 12 MDIO, 13 MDC, 14 nINT/REFCLKO, 15 nRST, 16 TXEN, 17 TXD0,
  18 TXD1, 19 VDD1A, 20 TXN, 21 TXP, 22 RXN, 23 RXP, 24 RBIAS, 25 (exposed pad) VSS.
Supplies [L] p.103: VDDIO 1.62-3.6 V, VDD1A / VDD2A 3.0-3.6 V, VDDCR 1.14-1.26 V, magnetics 2.25-3.6 V.
  VDDIO = +3V3. VDD1A, VDD2A, the four 49.9 ohm terminations and both transformer centre taps hang on
  VDDA_PHY = +3V3 through FB501 ([L] p.55 Figure 3-23, single supply). VDDCR comes from the internal
  regulator (fed from VDD2A) and gets 1 uF + 470 pF only ([L] p.13, p.53 Figure 3-21); nothing else on it.
  The values of C_BYPASS and C_F are not given in [L] (it points to a reference schematic): 100 nF per
  pin plus 1 uF per rail is convention, not a datasheet value.
  Current, REF_CLK out, regulator on, typical ([L] p.105 Table 5-5): 102 mA at 100BASE-TX and 139 mA at
  10BASE-T including the magnetics; maximum values are not specified.
Straps, latched at power-on and at the rising edge of nRST ([L] p.30-32, p.7-10; internal resistors are
50 uA typical, p.15):
  nINTSEL (pin 2, internal pull-up)   -> 0 by R504 10 k to GND: pin 14 is REFCLKO, the 50 MHz RMII clock
                                         made from the 25 MHz crystal (p.32 Table 3-6, p.39 Figure 3-15).
                                         There is no nINT then. LED2 becomes active high.
  REGOFF  (pin 3, internal pull-down) -> 0, nothing fitted beyond the LED to GND: internal 1.2 V
                                         regulator on (p.31, p.38 Figure 3-14). LED1 is active high.
  PHYAD0  (pin 10 RXER, internal pull-down) -> 0 by R502 10 k to GND: SMI address 0 (p.30).
  MODE[2:0] (pins 11, 7, 8, internal pull-ups) -> 111, nothing fitted: all capable, auto-negotiation
                                         (p.31 Table 3-4). The MCU pins on these nets are high-impedance
                                         while the PHY latches (they are inputs to the MAC).
  A strap that is pulled high goes to VDDIO, except REGOFF and nINTSEL, which go to VDD2A (p.30);
  neither is pulled high here.
Reset [L] p.11, p.109: nRST has an internal pull-up. R501 4.7 k to GND holds the PHY in reset until the
  MCU drives PHY_NRST high: 60 uA (50 uA pull-up + 10 uA leakage, p.107) x 4.7 k = 0.28 V, below the
  lowest falling threshold 0.64 V (p.107 Table 5-7); a 10 k would sit at 0.6 V. PC13 then sources
  3.3 V / 4.7 k = 0.7 mA (its limit is 3 mA). Firmware: release no sooner than 25 ms after the supplies
  are up (tpurstd), low for at least 100 us (trstia), rising edge monotonic.
REFCLKO [L] p.34, p.110 Table 5-12: "not part of the RMII specification", a timing analysis is required.
  toval 7.0 ns max, toinvld 3.0 ns min, TXD / TXEN setup 7.5 ns, hold 2.0 ns, for a 10-25 pF load. These
  are the numbers the length rules in SPEC section 9 were derived from. REFCLKO stops in the power-down modes.
RBIAS [L] p.12: 12.1 k 1 % to ground. MDIO [L] p.11: internal pull-up only; R503 1.5 k to VDDIO added.
Crystal [L] p.114 Figure 5-8, Table 5-17 (the 100 uW circuit): CL 8-12 pF, C0 5 pF max, ESR 80 ohm max,
  drive 100 uW, tolerance + stability about +-45 ppm, and Rs = 500 ohm (495-505) in series with XTAL2.
  Y501 Abracon ABM8-25.000MHZ-10-D2X-T [A] p.1: CL 10 pF, C0 3.0 pF max, ESR 50 ohm max (20-29.999 MHz),
  drive 10 uW typical / 100 uW max, +-20 ppm at 25 C, +-20 ppm over -40..+85 C, ageing +-2 ppm first year.
  Pads 1 and 3 are the crystal, 2 and 4 the lid / ground ([A] p.2).
  Load capacitors: CL = (Cext + Cpin + Cpcb) / 2, so Cext = 2 x 10 - 3 (pin, [L] p.114) - 2 (track and
  pads, estimate) = 15 pF, C0G. With Cpcb anywhere in 1-3 pF the crystal sees 9.5-10.5 pF.
  R506 499 ohm 0.5 % = 496.5-501.5 ohm, inside 495-505 (1 % would reach 494).
FB501 Bourns MH1608-221Y [B] p.1: 220 ohm +-25 % at 100 MHz, 100 mohm max, 2 A, 0603 ([B] p.5).
  139 mA x 0.1 ohm = 14 mV drop.

J501 Wuerth 7499010211A, RJ45 with magnetics, through hole, tab down. Pins [W] p.2 (schematic):
  1 TD+, 2 TD-, 4 CTD (transmit centre tap), 3 RD+, 6 RD-, 5 CRD (receive centre tap);
  8 = the common end of the internal 4 x 75 ohm + 1 nF line termination; 7 has no connection;
  9 (+) / 10 green LED, left; 12 (+) / 11 yellow LED, right; SH = shield tabs (2).
  The stock symbol Connector:RJ45_Wuerth_7499010211A and footprint Connector_RJ:RJ45_Wuerth_7499010211A_Horizontal
  use the same pin numbers; the footprint holes match [W] p.1 (8 x 0.9, 4 x 1.03, 2 x 1.6 plated, 2 x 3.25 unplated).
  Transformers 1:1, isolation 2250 V DC ([W] p.3). Centre taps: straight to VDDA_PHY with 100 nF each ([L] p.55).
  LEDs [W] p.3: VF 1.8-2.4 V at 20 mA. 270 ohm ([L] p.38, p.39) gives (3.3 - 2.1) / 270 = 4.4 mA.
  Green = LED1 = link / activity, yellow = LED2 = 100 Mbit/s (reset defaults, [L] p.36).
  Pin 8 and the shield go to GND through R513 (0 ohm): the board has one ground and no chassis net.
"""
from .common import FP, NC, P, U

PHY_FP = "Package_DFN_QFN:VQFN-24-1EP_4x4mm_P0.5mm_EP2.5x2.5mm"
RJ45_FP = "Connector_RJ:RJ45_Wuerth_7499010211A_Horizontal"
XTAL_FP = "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm"


def attach_pins(sh, part, nets, stub):
    """sh.attach for some of the pins of `part` (it insists on all of them): lets one pin have a longer stub."""
    every = part._pins
    part._pins = [p for p in every if p[0] in nets]
    try:
        sh.attach(part, nets, stub)
    finally:
        part._pins = every


def build(sh):
    # ---- PHY
    sh.title("Ethernet PHY LAN8742A: RMII, 50 MHz REF_CLK out of pin 14", 6, 8)
    x, y = P(44, 44)
    u = sh.page.sym("Interface_Ethernet:LAN8742A", "U501", "LAN8742A-CZ-TR", x, y, 0, PHY_FP,
                    ref_at=(x + 4 * U, y - 13 * U, "left"), val_at=(x + 4 * U, y - 12 * U, "left"),
                    fields={"MPN": "LAN8742A-CZ-TR", "Manufacturer": "Microchip"})
    nets = {
        "17": "RMII_TXD0", "18": "RMII_TXD1", "16": "RMII_TX_EN",
        "8": "RMII_RXD0", "7": "RMII_RXD1", "11": "RMII_CRS_DV", "10": "PHY_RXER",
        "12": "ETH_MDIO", "13": "ETH_MDC", "15": "PHY_NRST", "14": "RMII_REF_CLK",
        "5": "PHY_XI", "4": "PHY_XO",
        "21": "ETH_TX_P", "20": "ETH_TX_N", "23": "ETH_RX_P", "22": "ETH_RX_N",
        "24": "PHY_RBIAS", "3": "ETH_LED1", "2": "ETH_LED2",
        "6": "VDDCR", "19": "VDDA_PHY", "1": "VDDA_PHY", "25": "GND",
    }
    assert set(nets) | {"9"} == {p[0] for p in u._pins}
    attach_pins(sh, u, nets, 3)
    attach_pins(sh, u, {"9": "+3V3"}, 9)         # VDDIO: its +3V3 symbol clears the labels of the three pins beside it
    sh.note("Pin 14 = REFCLKO (strap nINTSEL = 0): no interrupt line to the MCU.", 6, 62)
    sh.note("RXER is not routed to the MCU.  Exposed pad 25 = VSS, the only ground pin.", 6, 64)

    # ---- supplies
    sh.title("PHY supplies", 80, 8)
    x, y = P(84, 22)
    fb = sh.page.sym("Device:FerriteBead", "FB501", "220R@100MHz 2A", x, y, 0, FP["L0603"],
                     ref_at=(x + 1.5 * U, y - 0.5 * U, "left"), val_at=(x + 1.5 * U, y + 0.5 * U, "left"),
                     fields={"MPN": "MH1608-221Y", "Manufacturer": "Bourns"})
    sh.attach(fb, {"1": "+3V3", "2": "VDDA_PHY"}, stub=1)
    sh.caps(501, ["1uF", "100nF", "100nF"], 98, 22, "VDDA_PHY", step=6)    # bulk, VDD1A, VDD2A
    sh.flag("VDDA_PHY", 116, 20)
    sh.caps(504, ["100nF", "1uF"], 123, 22, "+3V3", step=6)                # VDDIO
    sh.caps(506, ["1uF", "470pF"], 136, 22, "VDDCR", step=6)               # internal 1.2 V regulator output
    sh.flag("VDDCR", 148, 20)
    sh.note("C502: VDD1A.  C503: VDD2A.  C504, C505: VDDIO.  C506, C507: VDDCR, 1.2 V from the internal regulator, no other load.", 80, 32)

    # ---- straps, reset, bias
    sh.title("Reset, straps, bias", 80, 36)
    sh.R("R501", "4.7k", 84, 50, "PHY_NRST", "GND")
    sh.R("R502", "10k", 92, 50, "PHY_RXER", "GND")
    sh.R("R503", "1.5k", 100, 50, "+3V3", "ETH_MDIO")
    sh.R("R504", "10k", 108, 50, "ETH_LED2", "GND")
    sh.R("R505", "12.1k 1%", 116, 50, "PHY_RBIAS", "GND")
    sh.note("R501: PHY held in reset until the MCU (PC13) drives high.  R502: PHYAD0 = 0.  R504: nINTSEL = 0.", 80, 60)
    sh.note("REGOFF = 0 and MODE[2:0] = 111 by the internal resistors: regulator on, auto-negotiation.", 80, 62)

    # ---- line side
    sh.title("Line termination", 6, 68)
    sh.note("49.9R 1% from each line to VDDA_PHY.", 6, 70)
    for k, net in enumerate(["ETH_TX_P", "ETH_TX_N", "ETH_RX_P", "ETH_RX_N"]):
        sh.R("R%d" % (507 + k), "49.9R 1%", 9 + 7 * k, 84, "VDDA_PHY", net)
    sh.note("ETH_TX_P / _N and ETH_RX_P / _N: 100 ohm differential pairs.", 6, 98)

    # ---- crystal
    sh.title("25 MHz crystal, 100 uW circuit", 40, 68)
    sh.note("CL 10 pF = (15 + 3 pin + 2 track) / 2.  R506 = Rs, 495-505 ohm.", 40, 70)
    sh.ic("Device:Crystal_GND24", "Y501", "25MHz 10pF", 50, 84, XTAL_FP,
          {"1": "PHY_XI", "3": "PHY_XO_R", "G": "GND"},
          ref_at=(50 * U, 80.5 * U, None), val_at=(50 * U, 81.5 * U, None),
          fields={"MPN": "ABM8-25.000MHZ-10-D2X-T", "Manufacturer": "Abracon"})
    sh.C("C508", "15pF C0G", 61, 84, "PHY_XI", fp=FP["C0402"])
    sh.C("C509", "15pF C0G", 68, 84, "PHY_XO_R", fp=FP["C0402"])
    sh.R("R506", "499R 0.5%", 75, 84, "PHY_XO", "PHY_XO_R")

    # ---- RJ45
    sh.title("RJ45 with magnetics", 82, 68)
    sh.ic("Connector:RJ45_Wuerth_7499010211A", "J501", "7499010211A", 104, 78, RJ45_FP, {
        "1": "ETH_TX_P", "2": "ETH_TX_N", "4": "VDDA_PHY",
        "3": "ETH_RX_P", "6": "ETH_RX_N", "5": "VDDA_PHY",
        "7": NC, "8": "ETH_SHIELD", "SH": "ETH_SHIELD",
        "9": "ETH_LED1", "10": "ETH_LED1_K", "12": "ETH_LED2", "11": "ETH_LED2_K",
    }, stub=3, fields={"MPN": "7499010211A", "Manufacturer": "Wurth Elektronik"})
    sh.caps(510, ["100nF", "100nF"], 84, 96, "VDDA_PHY", step=6)      # centre taps CTD, CRD
    sh.R("R511", "270R", 97, 96, "ETH_LED1_K", "GND")
    sh.R("R512", "270R", 104, 96, "ETH_LED2_K", "GND")
    sh.R("R513", "0R", 116, 96, "ETH_SHIELD", "GND", fp=FP["R0805"])
    sh.flag("ETH_SHIELD", 122, 88)
    sh.note("C510, C511: centre taps, pins 4 and 5.", 128, 72)
    sh.note("Pin 8: internal 4 x 75R + 1 nF.", 128, 74)
    sh.note("9 (+) / 10: green, left, link / activity.", 128, 84)
    sh.note("12 (+) / 11: yellow, right, 100 Mbit/s.", 128, 86)
    sh.note("R513: pin 8 and shield to GND.", 128, 88)
