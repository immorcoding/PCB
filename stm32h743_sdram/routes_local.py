"""Local circuits of the STM32H743 + SDRAM board that do not touch the MCU (stop 7, routing two): power-area
control nets, CAN line side, LCD link resistors, backlight sense, key and user LEDs, audio analog side. Every net
is written by hand with coordinates (RTE-3); no autorouter. The Ethernet PHY side is routes_local_eth.py.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.routing.busroute.build stm32h743_sdram\\routes_local.py --fast
    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.routing.busroute.build stm32h743_sdram\\routes_local.py --out stm32h743_sdram\\out\\local

BOARD defaults to the read-only snapshot of the committed board; LOCAL_BOARD=<board> builds the same description on
another board (the real one: LOCAL_BOARD=stm32h743_sdram.kicad_pcb). Coordinates are local mm (board mm - 100).

Conventions (user decisions for stop 7): L1 where possible; a layer change outside the BGA areas is a 0.45 / 0.2
via and the far part is on L6 (L4 for the one long enable, EN_3V3A); 0 / 45 / 90 degree segments, junctions only
at pad centres (a net with three or more pads is a list of pad-to-pad chains); ground never gets a track (the
pads have their vias from stop 5 or rely on the L1 pour); widths are the net-class widths (Default 0.2032 mm).

Why each net goes the way it does (one line each). Stop 7 moved R807, D103, R102 / R103, R701-R704, R808 / R809
and SW801 so that their links are straight (RTE-10; place.py):
  BOOT_5V    U101.6 45 degrees down to C101.1's column, straight down into it (1.7 mm)
  FB_5V      the divider's FB pads face each other (R102 / R103 turned): R103.1 - R102.2 straight on L1; the +12V
             column (x 65.55-67) stands between the divider and U101.4, so that link hops on L6 (2 vias), south of
             the +5V_REG hop of R102.1 (routes_power.py draws that one along y 39.9).
  FB_3V3     R105.2 - R106.1 one diagonal between the two resistors; R105.2 up to U102.6
  EN_3V3     U102.1 - R104.2 - TP106 on L1
  EN_3V3A    U102.5 sits between +5V (pin 4) and FB (pin 6) with EN_3V3 east of the IC: to R108.2 by a via under
             the IC body and L4; west to TP107 on L4 at y 22.3 (north of the SDRAM loops and the decoupling vias),
             TP107 - U103.3 on L1
  EN_1V8     TP108 - R109.2 - U104.3 on L1, south of R113 / C112 and their vias
  RPP_GATE   D101.2 - Q101.1 inside the pocket of the +12V pour; R101 sits in the next pocket south of the +12V
             band (y 54.95-56.7): one hop on L6
  LED_3V3    R107.2 straight up into D103.2 (D103 turned)
  CAN        CANH from D801.1 east, then L6 down into J802.1 (through-hole) under CANL; R807.1 - J802.1 straight
             east on L1 (R807 turned: CANH north, CAN_TERM south); CANL D801.2 - J802.2 on L1 (stepped under D801.3's
             ground via), J802.2 - JP801.2 east of J802.1; CAN_TERM R807.2 45 degrees down into JP801.1 on L1
  LCD_P37-40 the link resistors now in the order of the connector pins: four L1 fan lines, no via
  LED_K      U701.3 is boxed by SW_BL, C705 and the LED_A band: out west, down between SW_BL and C705, L6 under
             the band to R708.1 (Kelvin tap on its north side); J701.40 - R708.1 and R707.2 - R708.1 on L1
  KEY_SW, LED1_A, LED2_A  short straight L1 links (SW801, R808 / R809 aligned with their pads)
  HPROUT     west past the decoupling column (between C606's and C608's vias, y 26.4) into C614.1
  HPLOUT     its capacitor C613 is beyond C614: up the 0.5 mm lane between the C605 / C609 and C606 columns
             (x 14.33), west at y 22.1 under C614's body (between its pads), 45 degrees down into C613.1
  HP_L_JACK  C613.2 - R604.1 - J601.T, north of R605
  HP_R_JACK  R605.1 - C614.2; C614.2 east at y 17.3 under C611's ground via, north between J601.T and the
             jack's locating hole (x 14.9), 45 degrees into J601.R
  LINE2L/R, LINEIN_L/R  the short capacitor and divider links north of the codec
  LINEIN_L_JACK  R606.2 up and 45 degrees into J602.T;  LINEIN_R_JACK R607.2 north to y 11.1, east under the
             line-in jack, 45 degrees into J602.R
  GND        one ground via at R605.2 (its L1 pour piece is closed in by HP_L_JACK and HP_R_JACK)
Vias are kept 1.05 mm (centre) from vias of other nets, so 0.2 mm of plane copper stays between the antipads.
"""
import os

BOARD = os.environ.get("LOCAL_BOARD", "out/probe_east/base/stm32h743_sdram.kicad_pcb")
ORIGIN = (100, 100)
GROUP = "local"
VIA_LIMIT = 4
YIELD_NETS = ["GND", "+12V"]  # the L1 / L6 ground pours give way to the tracks; so does the +12V pour round RPP_GATE
                              # (its fill keeps the zone clearance to the track and stays one piece, DRC clean)
OPEN_ENDS = True              # opt1: EN_3V3A branches at a via (R108's chain starts at the via (67.25, 32.4))
DRC_IGNORE = {"solder_mask_bridge": "mask webs between fine-pitch pads of the footprints (QFN, FPC), there before this group"}
VIEWS = [("power", 60.0, 28.0, 80.0, 62.0, 40), ("can", 66.0, 7.0, 84.0, 28.0, 45), ("lcd", 10.0, 54.0, 60.0, 74.0, 30),
         ("top", 28.0, 14.0, 70.0, 36.0, 25),
         ("audio", 2.0, 4.0, 34.0, 31.0, 35)]

NETS = ["BOOT_5V", "FB_5V", "FB_3V3", "EN_1V8", "EN_3V3", "EN_3V3A", "RPP_GATE", "LED_3V3", "CANH", "CANL", "CAN_TERM",
        "LCD_P37", "LCD_P38", "LCD_P39", "LCD_P40", "LED_K", "KEY_SW", "LED1_A", "LED2_A",
        "HPLOUT", "HPROUT", "HP_L_JACK", "HP_R_JACK", "LINE2L", "LINE2R", "LINEIN_L", "LINEIN_R", "LINEIN_L_JACK", "LINEIN_R_JACK"]


def V(x, y):
    return ("via", (x, y), (0.45, 0.2))


def power():
    R = {}
    R["BOOT_5V"] = [("L1", ["U101.6", (68.52, 44.6075), "C101.1"])]
    R["FB_5V"] = [
        [("L1", ["R103.1", "R102.2"])],
        [("L1", ["U101.4", (67.8625, 41.45)]), V(67.8625, 41.45),
         ("L6", [(67.8625, 41.45), (64.96, 41.45), (64.3, 42.11)]), V(64.3, 42.11),
         ("L1", [(64.3, 42.11), "R102.2"])],
    ]
    R["FB_3V3"] = [
        [("L1", ["U102.6", (68.01, 33.7025), "R105.2"])],
        [("L1", ["R105.2", (68.01, 35.38), "R106.1"])],
    ]
    R["EN_3V3"] = [
        [("L1", ["U102.1", (71.51, 34.2225), "R104.2"])],
        [("L1", ["R104.2", (73.4, 35.2), "TP106.1"])],
    ]
    R["EN_3V3A"] = [
        # U102.5 -> west -> L4 north, west at y 22.3 (north of the SDRAM loops and the decoupling vias), up to TP107
        [("L1", ["U102.5", (67.25, 32.4)]), V(67.25, 32.4),
         ("L4", [(67.25, 32.4), (66.75, 31.9), (66.75, 22.8), (66.25, 22.3), (39.6, 22.3), (39.1, 21.8), (39.1, 16.9),
                 (38.6, 16.4)]), V(38.6, 16.4),
         ("L1", [(38.6, 16.4), "TP107.1"])],
        [("L1", ["TP107.1", (36.0, 18.0), (31.1375, 18.0), (30.6375, 18.5), "U103.3"])],
        # opt1 (review 1): R108's branch leaves the west via (67.25, 32.4) on L4, south first (no turn-back across the
        # via) and east along y 33.0 (was U102.5 -> a second via under the IC body (69.5, 32.4) -> L4: one via less;
        # a branch at the via, accepted for this enable line)
        # stop 8 (review 2, b4): R108's leg leaves the via south-east on the line of the arriving NW leg (one straight
        # diagonal through the via, 2 bends fewer; was S 0.35 then SE 0.25)
        [("L4", [(67.25, 32.4), (67.85, 33.0), (73.61, 33.0), (74.11, 33.5)]), V(74.11, 33.5),
         ("L1", [(74.11, 33.5), "R108.2"])],
    ]
    R["EN_1V8"] = [
        [("L1", ["TP108.1", (10.51, 32.51), "R109.2"])],
        [("L1", ["R109.2", (13.4, 33.4), (13.9, 33.9), (18.1, 33.9), (18.8625, 33.1375), "U104.3"])],
    ]
    R["RPP_GATE"] = [
        [("L1", ["D101.2", (65.3625, 52.75), "Q101.1"])],
        [("L1", ["R101.1", (63.6, 58.71)]), V(63.6, 58.71),
         ("L6", [(63.6, 58.71), (63.1, 58.21), (63.1, 54.25), (63.6, 53.75)]), V(63.6, 53.75),
         ("L1", [(63.6, 53.75), "D101.2"])],
    ]
    R["LED_3V3"] = [("L1", ["R107.2", "D103.2"])]
    return R


def can():
    R = {}
    R["CANH"] = [
        [("L1", ["U801.7", (70.4, 16.365), (70.715, 16.05), "D801.1"])],
        [("L1", ["D801.1", (76.5, 16.05)]), V(76.5, 16.05),
         ("L6", [(76.5, 16.05), (77.0, 16.55), (77.0, 18.95), "J802.1"])],
        [("L1", ["R807.1", "J802.1"])],
    ]
    R["CANL"] = [
        [("L1", ["U801.6", (70.4, 17.635), (70.715, 17.95), "D801.2"])],
        [("L1", ["D801.2", (72.3, 17.95), (72.5, 18.15), (77.0, 18.15), (77.65, 17.5), "J802.2"])],
        [("L1", ["J802.2", (81.0, 19.45), (81.0, 23.74), "JP801.2"])],
    ]
    R["CAN_TERM"] = [("L1", ["R807.2", (71.9, 23.4), (74.7, 26.2), "JP801.1"])]
    return R


def lcd():
    R = {}
    # P39 straight down (0.1 mm step right below its resistor); P40 hops over it on L6 between the two rows;
    # P38 and P37 go round the south ends of the pins of P40 / P39 (under the connector body, nested) and come up
    R["LCD_P40"] = [("L1", ["R704.1", (30.25, 68.51), (30.25, 68.725), "J701.1"])]
    R["LCD_P39"] = [("L1", ["R703.1", (31.75, 68.81), "J701.2"])]
    R["LCD_P38"] = [("L1", ["R702.1", (31.65, 67.9), (32.25, 68.5), "J701.3"])]
    R["LCD_P37"] = [("L1", ["R701.1", (32.85, 68.5), (32.75, 68.6), "J701.4"])]
    R["LED_K"] = [
        [("L1", ["U701.3", (54.15, 57.05), (53.65, 57.55), (53.65, 59.35)]), V(53.65, 59.35),
         ("L6", [(53.65, 59.35), (52.8, 60.2), (52.8, 63.0), (52.0, 63.8)]), V(52.0, 63.8),
         ("L1", [(52.0, 63.8), "R708.1"])],
        [("L1", ["J701.40", (50.75, 69.0), (52.0, 67.75), "R708.1"])],
        [("L1", ["R707.2", (56.6625, 64.925), (56.2625, 65.325), (52.7, 65.325), "R708.1"])],
    ]
    R["KEY_SW"] = [
        [("L1", ["SW801.2", "R810.1"])],
        [("L1", ["R810.1", "R811.1"])],
    ]
    R["LED1_A"] = [("L1", ["D802.2", "R808.2"])]
    R["LED2_A"] = [("L1", ["D803.2", "R809.2"])]
    return R


def audio():
    R = {}
    # HPROUT straight west past the decoupling column (between C606's and C608's vias) into C614.1; HPLOUT, whose
    # capacitor C613 is the far one, goes north of it: up the 0.5 mm lane between the C605 / C609 and C606
    # columns, west at y 22.1 under C614's body (between its pads) and down into C613.1
    R["HPROUT"] = [("L1", ["U601.23", (15.9715, 27.25), (15.1215, 26.4), (12.18, 26.4), (11.4, 25.62), "C614.1"])]
    R["HPLOUT"] = [("L1", ["U601.19", (15.97, 25.25), (15.26, 25.96), (14.7, 25.96), (14.3325, 25.5925),
                           (14.3325, 22.6), (13.8325, 22.1), (8.12, 22.1), "C613.1"])]
    R["HP_L_JACK"] = [
        [("L1", ["C613.2", (4.6, 17.41), "R604.1"])],
        [("L1", ["R604.1", (4.79, 16.2), (10.9, 16.2), "J601.T"])],
    ]
    R["HP_R_JACK"] = [
        [("L1", ["R605.1", (7.69, 17.17), "C614.2"])],
        [("L1", ["C614.2", (11.98, 17.3), (14.4, 17.3), (14.9, 16.8), (14.9, 9.4), (17.4, 6.9), "J601.R"])],
    ]
    R["LINE2R"] = [("L1", ["U601.16", "C616.1"])]
    R["LINE2L"] = [("L1", ["U601.14", (18.25, 22.525), "C615.1"])]
    R["LINEIN_L"] = [
        [("L1", ["C615.2", (19.5, 19.725), (19.765, 19.725), "R606.1"])],
        [("L1", ["R606.1", (21.59, 19.3), (22.39, 19.3), "R608.1"])],
    ]
    R["LINEIN_R"] = [
        [("L1", ["C616.2", (17.25, 20.04), "R607.1"])],
        [("L1", ["C616.2", (16.49, 19.465), "R609.1"])],
    ]
    R["LINEIN_L_JACK"] = [("L1", ["R606.2", (21.91, 17.19), "J602.T"])]
    R["LINEIN_R_JACK"] = [("L1", ["R607.2", (19.71, 11.6), (20.21, 11.1), (28.0, 11.1), "J602.R"])]
    return R


# ground pads that the refilled L1 pour no longer reaches because this group's tracks close round them: one 0.45 /
# 0.2 ground via at the pad (stop-5 convention), written as an extra (the group owns no ground copper)
GND_VIAS = [(9.5, 16.9)]      # R605.2 (HP_R load): boxed in by HP_L_JACK (north), R605.1 - C614.2 and C614.2 - J601.R


def routes(job):
    job.profile.classes["PWR"]["via"] = (0.45, 0.2)          # ground vias: this board's 0.45 / 0.2 (PWR class says 0.6 / 0.3)
    job.stitch += [("GND", p) for p in GND_VIAS]
    R = {}
    for part in (power, can, lcd, audio):
        R.update(part())
    return R
