"""Page 8: microSD, CAN, SWD and debug UART connectors, user LEDs and key, mounting holes (SPEC 2.2, 3, 4, 10).

Datasheet checks (RUL-10). "img" = read off the rendered page, "text" = text layer only.

microSD socket J801, Hirose DM3AT-SF-PEJM5 (drawing CL0609-0031-0-00 sheet 1, img; DM3 catalog p.1-2):
  contacts #1 DAT2, #2 CD/DAT3, #3 CMD, #4 VDD, #5 CLK, #6 VSS, #7 DAT0, #8 DAT1 (top view on sheet 1).
  Card detection switch between contacts (A) and (B): open with no card, closed with a card inserted
  (table on sheet 1); the catalog calls it normally open. It is not tied to the shell.
  Recommended land pattern against the stock footprint Connector_Card:microSD_HC_Hirose_DM3AT-SF-PEJM5:
  eight 0.7 x 1.2 pads at 1.1 pitch = pads 1..8 (#1 is 3.2 mm right of the centre line), the 0.7 x 1.2 pad
  0.95 beyond #8 = pad 9 = switch (B), the 1.0 x 0.8 side pad = pad 10 = switch (A), four shell tabs = "SH".
  All fourteen pad positions and sizes agree with the drawing. Symbol Connector:Micro_SD_Card_Det_Hirose_DM3AT
  uses the same numbers (1..8, 9 DET_B, 10 DET_A, SH).
  Circuit: 3.3 V only, 4-bit. 47k pull-ups on CMD and DAT0..3 (AN4938 9.4.1 asks for pull-ups on CMD and data;
  the MCU's internal ones are off until firmware turns them on, external ones keep the bus defined from
  power-up). Nothing on CK. DET_A to GND, DET_B to SD_CD with 10k to +3V3: SD_CD low = card inserted.
  Not checked: the 10..100k range of the SD specification (sdcard.org refuses download) - 47k is the usual value.

CAN transceiver U801, TI TCAN1042HGVDR (SLLSES7D): pins p.5 Figure 6-3 / Table 6-1 (img):
  1 TXD, 2 GND, 3 VCC, 4 RXD, 5 VIO, 6 CANL, 7 CANH, 8 STB (active high). The borrowed symbol
  Interface_CAN_LIN:MCP2562-E-SN has the same eight functions on the same numbers (VSS = GND, VDD = VCC, STBY = STB).
  VCC 4.5..5.5 V, VIO 3..5.5 V (p.8, img). TXD and STB have internal pull-ups to VIO (p.20-21, text): with PD5
  floating the part is in standby. Supply: 4.7 uF bulk + 100 nF on VCC, 100 nF on VIO (p.31, text).
CAN ESD D801, TI ESD2CAN24DBZRQ1 (SLVSFW5D): SOT-23, 1 and 2 = IO, 3 = GND (p.3, img); VRWM +/-24 V,
  bidirectional, line capacitance 3 pF typ / 5 pF max, clamp 37 V at 5.7 A 8/20 us (p.6, img).
  Drawn with Power_Protection:NUP2105L (1, 2 = lines, 3 = common), the same pinout.
Termination R807 120R 0805 (0.125 W class; worst case 3 V differential = 75 mW) in series with jumper JP801.

SWD header J803, Samtec FTSH-105-01-L-DV-K (print FTSH-1XX-XX-XXX-DV sheet 2 Fig 2 for the -K shroud; footprint
  print rev H sheet 1, img): 2 x 5, 1.27 mm, pad 01 and 02 face each other at one end, odd numbers in one row.
  Stock footprint PinHeader_2x05_P1.27mm_Vertical_SMD has the same numbering and pitch; its pads are
  2.4 x 0.74 at +/-1.95, Samtec recommends 2.79 x 0.74 at +/-2.035 (0.28 mm longer on the outside), and it has
  no outline for the 5.08 mm wide shroud. Pin order is the ARM 10-pin Cortex debug order as fixed in SPEC 10.
UART header J804 and jumper JP801: 2.54 mm straight pin strip, Samtec HTSW-1xx-07-L-S (catalog p.1, text).
LEDs D802 / D803, Vishay TLMG1100-GS15 (green) / TLMS1100-GS15 (red), 0603 (doc 83173 p.1, 12, img):
  VF 1.8 / 2.1 / 2.4 V at 20 mA. Active high: pin - 470R - LED - GND, about 3 mA.
Key SW801, Omron B3U-1000P (B3U datasheet p.1-2, img): SPST-NO, 1..50 mA at 3..12 V DC, bounce 5 ms max, pads
  0.8 x 1.7 at +/-1.7 (stock footprint 0.9 x 1.7 at +/-1.7). Key to +3V3, 3.3k pull-down (1 mA through the
  contact), then 10k + 100nF to PA0: USER_KEY high = pressed.
Terminal J802, Phoenix Contact PT 1,5/3-3,5-H (1984620): datasheet NOT read (site refuses download).
"""
from .common import FP, NC

SD = "Connector_Card:microSD_HC_Hirose_DM3AT-SF-PEJM5"
HDR = "Connector_PinHeader_2.54mm:PinHeader_1x%02d_P2.54mm_Vertical"
HOLE = "MountingHole:MountingHole_3.2mm_M3_Pad_Via"


def build(sh):
    # ---------------------------------------------------------------- microSD
    sh.box(6, 8, 80, 50)
    sh.title("microSD on SDMMC1, 4-bit, 3.3 V only", 7, 10)
    sh.link("R812", "+3V3", "+3V3_SD", 66, 38, "R0603", flag_at=(80, 34))
    sh.rails = {"+3V3": "+3V3_SD"}
    sh.ic("Connector:Micro_SD_Card_Det_Hirose_DM3AT", "J801", "DM3AT-SF-PEJM5", 30, 26, SD, {
        "1": "SDMMC1_D2", "2": "SDMMC1_D3", "3": "SDMMC1_CMD", "4": "+3V3", "5": "SDMMC1_CK", "6": "GND",
        "7": "SDMMC1_D0", "8": "SDMMC1_D1",
        "10": "GND", "9": "SD_CD", "SH": "GND",
    }, stub=3, fields={"MPN": "DM3AT-SF-PEJM5", "Manufacturer": "Hirose"})
    for k, net in enumerate(["SDMMC1_CMD", "SDMMC1_D0", "SDMMC1_D1", "SDMMC1_D2", "SDMMC1_D3"]):
        sh.R("R%d" % (801 + k), "47k", 46 + 5 * k, 17, "+3V3", net)
    sh.R("R806", "10k", 73, 17, "+3V3", "SD_CD")
    sh.C("C801", "100nF", 50, 36, "+3V3")
    sh.C("C802", "10uF", 56, 36, "+3V3", fields={"Rating": "10 V X5R or better"})
    sh.note("Card detect: switch DET_A - DET_B closes when a card is in. SD_CD (PD4) low = card inserted, high (R806) = empty.", 7, 44)
    sh.note("R801-R805 hold CMD and DAT0-3 high from power-up. No pull, no series part on CK. C801, C802 at the socket VDD pin.", 7, 46)
    sh.note("Socket pads: 1-8 card contacts, 9 / 10 detect switch, SH = four shell tabs, grounded.", 7, 48)

    # ---------------------------------------------------------------- CAN
    sh.box(84, 8, 155, 50)
    sh.title("CAN (FDCAN1), not isolated", 85, 10)
    sh.note("Bring-up links, CAN:", 120, 91)
    sh.link("R813", "+3V3", "+3V3_CAN", 128, 94, "R0603", flag_at=(142, 92))
    sh.link("R814", "+5V", "+5V_CAN", 128, 98, "R0603", flag_at=(150, 92))
    sh.rails = {"+3V3": "+3V3_CAN", "+5V": "+5V_CAN"}
    sh.ic("Interface_CAN_LIN:MCP2562-E-SN", "U801", "TCAN1042HGVDR", 102, 26, "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", {
        "1": "FDCAN1_TX", "4": "FDCAN1_RX", "8": "CAN_STB", "5": "+3V3", "3": "+5V", "2": "GND",
        "7": "CANH", "6": "CANL",
    }, stub=3, fields={"MPN": "TCAN1042HGVDR", "Manufacturer": "Texas Instruments"})
    sh.ic("Power_Protection:NUP2105L", "D801", "ESD2CAN24", 120, 24, "Package_TO_SOT_SMD:SOT-23", {
        "1": "CANH", "2": "CANL", "3": "GND",
    }, fields={"MPN": "ESD2CAN24DBZRQ1", "Manufacturer": "Texas Instruments"})
    sh.ic("Connector:Screw_Terminal_01x03", "J802", "CAN 3.5mm", 146, 22,
          "TerminalBlock_Phoenix:TerminalBlock_Phoenix_PT-1,5-3-3.5-H_1x03_P3.50mm_Horizontal", {
              "1": "CANH", "2": "CANL", "3": "GND",
          }, stub=3, fields={"MPN": "1984620 (PT 1,5/3-3,5-H)", "Manufacturer": "Phoenix Contact"})
    sh.R("R807", "120R", 122, 38, "CANH", "CAN_TERM", fp=FP["R0805"], horizontal=True,
         fields={"Rating": "0805, 1 %, 0.125 W"})
    sh.ic("Jumper:Jumper_2_Open", "JP801", "TERM", 144, 38, HDR % 2, {"1": "CAN_TERM", "2": "CANL"},
          fields={"MPN": "HTSW-102-07-L-S", "Manufacturer": "Samtec"})
    sh.C("C803", "100nF", 90, 39, "+5V")
    sh.C("C804", "4.7uF", 96, 39, "+5V", fields={"Rating": "16 V X5R or better"})
    sh.C("C805", "100nF", 104, 39, "+3V3")
    sh.note("STB has an internal pull-up: U801 stays in standby until PD5 (CAN_STB) drives it low. TXD is pulled up too (recessive).", 85, 46)
    sh.note("J802 pin 1 CANH, 2 CANL, 3 GND. JP801 closed = 120R across the bus. D801 next to J802. VCC = +5V, VIO = +3V3.", 85, 48)

    # ---------------------------------------------------------------- SWD
    sh.box(6, 54, 50, 104)
    sh.rails = {}
    sh.title("SWD, ARM 10-pin 1.27 mm", 7, 56)
    x, y = 22 * 2.54, 78 * 2.54
    sh.ic("Connector:Conn_ARM_JTAG_SWD_10", "J803", "FTSH-105-01-L-DV-K", 22, 78,
          "Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical_SMD", {
              "1": "+3V3", "2": "SWDIO", "4": "SWCLK", "6": "SWO", "8": NC, "10": "NRST",
              "3": "GND", "5": "GND", "9": "GND",
          }, stub=3, fields={"MPN": "FTSH-105-01-L-DV-K", "Manufacturer": "Samtec"},
          ref_at=(x - 2 * 2.54, y - 6.5 * 2.54, "right"), val_at=(x - 2 * 2.54, y - 5.5 * 2.54, "right"))
    sh.note("1 VTref, 2 SWDIO, 4 SWCLK, 6 SWO, 10 NRST,", 7, 98)
    sh.note("3 / 5 / 9 GND, 7 key (no pin function), 8 NC.", 7, 100)
    sh.note("Shrouded and keyed (-K).", 7, 102)

    # ---------------------------------------------------------------- debug UART
    sh.box(54, 54, 84, 104)
    sh.title("Debug UART (USART1)", 55, 56)
    sh.ic("Connector_Generic:Conn_01x04", "J804", "UART 1x4 2.54mm", 74, 70, HDR % 4, {
        "1": "GND", "2": "USART1_TX", "3": "USART1_RX", "4": "+3V3",
    }, stub=3, fields={"MPN": "HTSW-104-07-L-S", "Manufacturer": "Samtec"})
    sh.note("Left to right on the board:", 55, 92)
    sh.note("1 GND, 2 TX (PB14, MCU out),", 55, 94)
    sh.note("3 RX (PB15, MCU in), 4 3V3.", 55, 96)
    sh.note("3V3 = level reference for the", 55, 98)
    sh.note("adapter only, not a supply input.", 55, 100)

    # ---------------------------------------------------------------- LEDs and key
    sh.box(88, 54, 155, 90)
    sh.title("User LEDs and key", 89, 56)
    for k, (net, mpn, colour) in enumerate([("LED1", "TLMG1100-GS15", "green"), ("LED2", "TLMS1100-GS15", "red")]):
        j = 61 + 6 * k
        sh.R("R%d" % (808 + k), "470R", 100, j, net, net + "_A", horizontal=True)
        x, y = 120 * 2.54, j * 2.54
        sh.ic("Device:LED", "D%d" % (802 + k), colour, 120, j, FP["LED0603"], {"2": net + "_A", "1": "GND"},
              rot=180, stub=1, fields={"MPN": mpn, "Manufacturer": "Vishay"},
              ref_at=(x, y - 2.0 * 2.54, None), val_at=(x, y + 1.5 * 2.54, None))
    sh.note("LED1 = PH6, LED2 = PH7.", 130, 61)
    sh.note("High = on, about 3 mA.", 130, 63)
    sh.ic("Switch:SW_Push", "SW801", "B3U-1000P", 100, 78, "Button_Switch_SMD:SW_SPST_B3U-1000P", {
        "1": "+3V3", "2": "KEY_SW",
    }, fields={"MPN": "B3U-1000P", "Manufacturer": "Omron"})
    sh.R("R810", "3.3k", 114, 81, "KEY_SW", "GND")
    sh.R("R811", "10k", 130, 78, "KEY_SW", "USER_KEY", horizontal=True)
    sh.C("C806", "100nF", 147, 81, "USER_KEY")
    sh.note("USER_KEY (PA0) high = pressed. R810 pulls down (1 mA through the contact); R811 + C806 = 1 ms filter, firmware still debounces.", 89, 88)

    # ---------------------------------------------------------------- mounting holes
    sh.box(88, 92, 117, 104)
    sh.title("Mounting holes M3, plated, GND", 89, 94)
    for k in range(4):
        part = sh.page.sym("Mechanical:MountingHole_Pad", "H%d" % (801 + k), "M3", (93 + 6 * k) * 2.54, 98 * 2.54, 0, HOLE)
        sh.attach(part, {"1": "GND"}, stub=1)
