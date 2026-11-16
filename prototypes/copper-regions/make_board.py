"""PROTOTYPE (throwaway, issue 16): placeholder H7 test board for trying copper regions on.

    D:\\KiCad\\bin\\python.exe make_board.py        -> out/0_base/h7cu.kicad_pcb (+ .kicad_pro, .kicad_dru)

No schematic: nets are put straight onto pads. 85 x 75 mm, R2 corners, four M3 holes, six layers.
Pin numbers of the MCU, the regulators and the PHY are read from the KiCad symbol libraries.
PLACEHOLDERS, NOT CHECKED AGAINST ANY DATASHEET: SDRAM balls, codec pins, LCD / RJ45 / SD pins,
and every position. Coordinates are local mm (board file mm - 100), origin at the top left corner.
"""
import os, shutil
import pcbnew
from probe import sym_pins, KI

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "0_base")
W, H, R = 85.0, 75.0, 2.0
FromMM, mm = pcbnew.FromMM, pcbnew.ToMM
P = lambda x, y: pcbnew.VECTOR2I(FromMM(x + 100), FromMM(y + 100))

os.makedirs(OUT, exist_ok=True)
for ext in ("kicad_pro", "kicad_dru"):
    shutil.copy(os.path.join(HERE, "base", "h7cu." + ext), os.path.join(OUT, "h7cu." + ext))
shutil.copy(os.path.join(HERE, "base", "empty6.kicad_pcb"), os.path.join(OUT, "h7cu.kicad_pcb"))
B = pcbnew.LoadBoard(os.path.join(OUT, "h7cu.kicad_pcb"))
FPS = {}


def net(name):
    n = B.FindNet(name)
    if n is None:
        n = pcbnew.NETINFO_ITEM(B, name); B.Add(n)
    return n


def put(ref, spec, x, y, rot=0, nets=None, value=""):
    lib, name = spec.split(":")
    fp = pcbnew.FootprintLoad(os.path.join(KI, "footprints", lib + ".pretty"), name)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetReference(ref); fp.SetValue(value or name[:18])
    fp.SetPosition(P(x, y)); fp.SetOrientationDegrees(rot)
    B.Add(fp)
    nets = nets or {}
    for pad in fp.Pads():
        n = nets.get(pad.GetNumber(), nets.get("*"))
        if n:
            pad.SetNet(net(n.replace("#", pad.GetNumber())))
    FPS[ref] = fp
    return fp


def pad(ref, num):
    for p in FPS[ref].Pads():
        if p.GetNumber() == num:
            return mm(p.GetPosition().x) - 100, mm(p.GetPosition().y) - 100
    raise KeyError(ref + "." + num)


def padnet(ref, num):
    for p in FPS[ref].Pads():
        if p.GetNumber() == num:
            return p.GetNetname()


def via(netname, x, y, dia=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(B); v.SetPosition(P(x, y))
    v.SetWidth(pcbnew.F_Cu, FromMM(dia)); v.SetDrill(FromMM(drill))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net(netname)); B.Add(v)


def track(netname, a, c, w=0.3, layer=pcbnew.F_Cu):
    s = pcbnew.PCB_TRACK(B); s.SetStart(P(*a)); s.SetEnd(P(*c)); s.SetWidth(FromMM(w))
    s.SetLayer(layer); s.SetNet(net(netname)); B.Add(s)


def tap(ref, num, dx, dy, dia=0.6, drill=0.3, w=0.3):
    """A via beside a pad, joined to it by a short track: the pad's way down to its plane."""
    x, y = pad(ref, num)
    via(padnet(ref, num), x + dx, y + dy, dia, drill)
    track(padnet(ref, num), (x, y), (x + dx, y + dy), w)


# ---------------------------------------------------------------- outline, holes, rule areas
def edge_line(a, c):
    s = pcbnew.PCB_SHAPE(B); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(P(*a)); s.SetEnd(P(*c))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FromMM(0.1)); B.Add(s)


def edge_arc(centre, start, end):
    for deg in (90, -90):
        s = pcbnew.PCB_SHAPE(B); s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetCenter(P(*centre)); s.SetStart(P(*start)); s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(deg, pcbnew.DEGREES_T))
        e = s.GetEnd()
        if abs(mm(e.x) - 100 - end[0]) < 0.001 and abs(mm(e.y) - 100 - end[1]) < 0.001:
            s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FromMM(0.1)); B.Add(s)
            return
    raise RuntimeError("arc")


edge_line((R, 0), (W - R, 0)); edge_line((W, R), (W, H - R)); edge_line((W - R, H), (R, H)); edge_line((0, H - R), (0, R))
edge_arc((R, R), (0, R), (R, 0)); edge_arc((W - R, R), (W - R, 0), (W, R))
edge_arc((W - R, H - R), (W, H - R), (W - R, H)); edge_arc((R, H - R), (R, H), (0, H - R))

for i, (x, y) in enumerate(((4, 4), (81, 4), (4, 71), (81, 71)), 1):
    put("H%d" % i, "MountingHole:MountingHole_3.2mm_M3_Pad", x, y, 0, {"1": "GND"})

MCU, RAM = (38.0, 37.0), (52.0, 37.0)
for name, (cx, cy), (hw, hh) in (("BGA_MCU", MCU, (6.0, 6.0)), ("BGA_SDRAM", RAM, (5.0, 7.5))):   # package + 1 mm
    z = pcbnew.ZONE(B); z.SetIsRuleArea(True); z.SetZoneName(name)
    ls = pcbnew.LSET()
    for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu):
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    for k in ("SetDoNotAllowTracks", "SetDoNotAllowVias", "SetDoNotAllowPads", "SetDoNotAllowZoneFills", "SetDoNotAllowFootprints"):
        getattr(z, k)(False)
    o = z.Outline(); o.NewOutline()
    for x, y in ((cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)):
        o.Append(P(x, y))
    B.Add(z)

# ---------------------------------------------------------------- the two BGAs and their vias
POWER = ("GND", "+3V3", "+5V", "+3V3A", "VDDA_MCU")
pins = sym_pins("MCU_ST_STM32H7.kicad_sym", "STM32H743IIKx")
mcu_nets = {}
for num, nm in pins.items():
    if nm in ("VDD", "VBAT", "VDD33_USB", "PDR_ON"):
        mcu_nets[num] = "+3V3"
    elif nm in ("VSS", "VSSA", "VREF-"):
        mcu_nets[num] = "GND"
    elif nm in ("VDDA", "VREF+"):
        mcu_nets[num] = "VDDA_MCU"
    elif nm == "VCAP":
        mcu_nets[num] = "VCAP_" + num
    else:
        mcu_nets[num] = nm.split("/")[0]
put("U1", "Package_BGA:UFBGA-201_10x10mm_Layout15x15_P0.65mm", MCU[0], MCU[1], 0, mcu_nets, "STM32H743IIK6")

# 90-ball SDRAM, 3.3 V: ball map written from memory of the common 90-ball pinout. PLACEHOLDER.
ram_pwr = {"+3V3": "A7 F9 L7 R7 B2 B7 C9 D9 E1 L1 M9 N9 P2 P7", "GND": "A3 F1 L3 R3 B3 B8 C1 D1 E9 L9 M1 N1 P3 P8"}
ram_nets = {"*": "SD_#"}
for n, balls in ram_pwr.items():
    for b in balls.split():
        ram_nets[b] = n
put("U2", "Package_BGA:BGA-90_8.0x13.0mm_Layout2x3x15_P0.8mm", RAM[0], RAM[1], 0, ram_nets, "IS42S32800J")

sites = set()


def dogbone(ref, p, pitch, order):
    x, y = mm(p.GetPosition().x) - 100, mm(p.GetPosition().y) - 100
    for sx, sy in order:
        s = (round(x + sx * pitch / 2, 3), round(y + sy * pitch / 2, 3))
        if s not in sites:
            sites.add(s)
            via(p.GetNetname(), s[0], s[1], 0.30, 0.15)
            track(p.GetNetname(), (x, y), s, 0.15 if p.GetNetname() in POWER else 0.09)
            return
    print("no via site for", ref, p.GetNumber())


n_sig = n_pwr = 0
for p in FPS["U1"].Pads():                      # rings 3, 4 and the centre block: via outwards; ring 2 power balls: inwards
    i = round((mm(p.GetPosition().x) - 100 - MCU[0]) / 0.65); j = round((mm(p.GetPosition().y) - 100 - MCU[1]) / 0.65)
    ring = 8 - max(abs(i), abs(j))
    sx, sy = (1 if i >= 0 else -1), (1 if j >= 0 else -1)
    out = [(sx, sy), (sx, -sy), (-sx, sy), (-sx, -sy)]
    power = p.GetNetname() in POWER
    if ring >= 3:
        dogbone("U1", p, 0.65, out); n_pwr += power; n_sig += not power
    elif p.GetNetname() in ("GND", "+3V3"):
        dogbone("U1", p, 0.65, out[::-1]); n_pwr += 1
print("U1 dog-bone vias: %d signal, %d power/ground" % (n_sig, n_pwr))
for p in FPS["U2"].Pads():                      # SDRAM: signals leave on the top layer; power balls get a via
    if p.GetNetname() in POWER:
        sx = -1 if mm(p.GetPosition().x) - 100 > RAM[0] else 1          # towards the empty centre channel
        sy = 1 if mm(p.GetPosition().y) - 100 >= RAM[1] else -1
        dogbone("U2", p, 0.8, [(sx, sy), (sx, -sy), (-sx, sy), (-sx, -sy)])

# ---------------------------------------------------------------- audio corner (top left)
JACK = "Connector_Audio:Jack_3.5mm_CUI_SJ-3523-SMT_Horizontal"
put("J2", JACK, 14, 9.5, 0, {"S": "GND", "T": "HP_L", "R": "HP_R"})
put("J3", JACK, 26, 9.5, 0, {"S": "GND", "T": "LINE_L", "R": "LINE_R"})
codec = {"*": "AU_#", "33": "GND", "": "GND", "4": "+1V8", "5": "GND", "6": "+3V3",
         "18": "+3V3A", "19": "GND", "21": "+3V3A", "22": "GND", "24": "+3V3A", "27": "+3V3A", "28": "GND"}   # PLACEHOLDER pins
put("U6", "Package_DFN_QFN:QFN-32-1EP_5x5mm_P0.5mm_EP3.45x3.45mm", 20, 25, 0, codec, "TLV320AIC3104")
put("U4", "Package_TO_SOT_SMD:SOT-23-5", 29, 23, 180, {"1": "+5V", "2": "GND", "3": "EN_3V3A", "5": "+3V3A"}, "TPS7A2033")
put("C41", "Capacitor_SMD:C_0603_1608Metric", 32.7, 23.95, 0, {"1": "+5V", "2": "GND"})
put("C42", "Capacitor_SMD:C_0603_1608Metric", 25.3, 23.95, 0, {"1": "GND", "2": "+3V3A"})
put("U5", "Package_TO_SOT_SMD:SOT-23-5", 12.5, 25.5, 0, {"1": "+3V3", "2": "GND", "3": "EN_1V8", "5": "+1V8"}, "TPS7A2018")
put("C51", "Capacitor_SMD:C_0603_1608Metric", 15.4, 23.6, 90, {"1": "+1V8", "2": "GND"})
put("C52", "Capacitor_SMD:C_0603_1608Metric", 8.8, 24.55, 0, {"1": "GND", "2": "+3V3"})
tap("C41", "1", 0, 1.35); tap("C41", "2", 1.35, 0); tap("C42", "2", 0, 1.35); tap("C42", "1", 0, 1.35)
track("+5V", pad("U4", "1"), pad("C41", "1"), 0.4); track("+3V3A", pad("U4", "5"), pad("C42", "2"), 0.4)
track("+3V3", pad("U5", "1"), pad("C52", "2"), 0.4)
for n in ("18", "21", "24"):
    tap("U6", n, 1.3, 0, 0.45, 0.2, 0.25)
tap("U6", "27", 0, -1.3, 0.45, 0.2, 0.25); tap("U6", "6", -1.35, 0, 0.45, 0.2, 0.25); via("GND", 20, 25, 0.45, 0.2)
tap("C52", "2", 0, -1.35); tap("C52", "1", 0, -1.35); tap("C51", "2", 0, -1.35)

# ---------------------------------------------------------------- left edge: RJ45, PHY, QSPI flash, SWD
rj = {"*": "ETH_#", "4": "VDDA_PHY", "5": "VDDA_PHY", "8": "GND", "SH": "GND"}        # PLACEHOLDER pins
put("J5", "Connector_RJ:RJ45_Wuerth_7499010211A_Horizontal", 17.3, 36, 270, rj)
phy = {"*": "PHY_#", "1": "VDDA_PHY", "19": "VDDA_PHY", "6": "VDDCR", "9": "+3V3", "25": "GND", "": "GND"}
put("U7", "Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm", 27.5, 41, 0, phy, "LAN8742A")
tap("U7", "9", 0, 1.3, 0.45, 0.2, 0.25); via("GND", 27.5, 41, 0.45, 0.2)
qspi = {"*": "QSPI_#", "8": "+3V3", "4": "GND", "9": "GND", "": "GND"}
put("U3", "Package_SON:WSON-8-1EP_8x6mm_P1.27mm_EP3.4x4.3mm", 26, 56, 0, qspi, "W25Q128JV")
tap("U3", "8", 1.4, 0, 0.45, 0.2, 0.25); via("GND", 26, 56, 0.45, 0.2)
put("J6", "Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical_SMD", 13, 64.5, 0,
    {"*": "SWD_#", "1": "+3V3", "3": "GND", "5": "GND", "9": "GND"})
tap("J6", "1", -2.2, 0, 0.45, 0.2, 0.25)

# ---------------------------------------------------------------- bottom edge: LCD FPC, backlight boost input
lcd = {"*": "LCD_#", "1": "LED_K", "2": "LED_A", "3": "GND", "4": "+3V3", "29": "GND", "36": "GND", "MP": "GND"}   # PLACEHOLDER
put("J7", "Connector_FFC-FPC:Hirose_FH12-40S-0.5SH_1x40-1MP_P0.50mm_Horizontal", 42, 70, 0, lcd)
tap("J7", "4", 0, -1.7, 0.45, 0.2, 0.25)
put("L3", "Inductor_SMD:L_1008_2520Metric", 59.5, 69.3, 0, {"1": "+5V", "2": "SW_BL"})
put("C31", "Capacitor_SMD:C_0603_1608Metric", 59.2, 66.6, 0, {"1": "+5V", "2": "GND"})
tap("C31", "1", -1.4, 0); tap("C31", "2", 1.4, 0); track("+5V", pad("L3", "1"), pad("C31", "1"), 0.4)

# ---------------------------------------------------------------- top right: microSD, CAN
sd = {"*": "SDC_#", "4": "+3V3", "6": "GND", "SH": "GND"}
put("J4", "Connector_Card:microSD_HC_Molex_104031-0811", 64, 7.2, 180, sd)
tap("J4", "4", 0, 1.7, 0.45, 0.2, 0.25)
can = {"1": "CAN_TX", "2": "GND", "3": "+5V", "4": "CAN_RX", "5": "+3V3", "6": "CANL", "7": "CANH", "8": "CAN_STB"}
put("U11", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", 68.5, 22, 180, can, "TCAN1042HGV")
put("C61", "Capacitor_SMD:C_0603_1608Metric", 73.85, pad("U11", "3")[1], 0, {"1": "+5V", "2": "GND"})
tap("C61", "1", 0, -1.35); tap("C61", "2", 0, -1.35); track("+5V", pad("U11", "3"), pad("C61", "1"), 0.4); tap("U11", "5", -1.9, 0, 0.45, 0.2, 0.25)
put("J8", "TerminalBlock_Phoenix:TerminalBlock_Phoenix_PT-1,5-3-3.5-H_1x03_P3.50mm_Horizontal", 80.5, 15.5, 270,
    {"1": "CANH", "2": "CANL", "3": "GND"})

# ---------------------------------------------------------------- power area (right, below the SDRAM)
# DC jack -> fuse -> P-MOS -> TVS -> +12V -> buck 1 (LMR51420) -> +5V -> buck 2 (TPS62A02) -> +3V3
put("J1", "Connector_BarrelJack:BarrelJack_Horizontal", 71.3, 58, 180, {"1": "+12V_IN", "2": "GND", "3": "GND"})
put("F1", "Fuse:Fuse_1206_3216Metric", 66.6, 58, 0, {"1": "+12V_F", "2": "+12V_IN"})
put("Q1", "Package_TO_SOT_SMD:SOT-23", 62.2, 58, 0, {"1": "Q1_G", "2": "+12V", "3": "+12V_F"}, "P-MOS")
put("D1", "Diode_SMD:D_SMA", 57.5, 61.5, 0, {"1": "GND", "2": "+12V"}, "TVS")
put("C10", "Capacitor_SMD:C_1206_3216Metric", 55.7, 56.2, 0, {"1": "GND", "2": "+12V"})
buck1 = {"1": "GND", "2": "SW_5V", "3": "+12V", "4": "FB_5V", "5": "EN_5V", "6": "BOOT_5V"}
put("U8", "Package_TO_SOT_SMD:SOT-23-6", 60, 52, 270, buck1, "LMR51420")
put("C11", "Capacitor_SMD:C_1206_3216Metric", 60, 48.3, 0, {"1": "+12V", "2": "GND"})
put("L1", "Inductor_SMD:L_Changjiang_FNR4020S", 60, 44.6, 90, {"1": "SW_5V", "2": "+5V"})
put("C12", "Capacitor_SMD:C_0805_2012Metric", 58.9, 40.6, 90, {"1": "+5V", "2": "GND"})
put("C13", "Capacitor_SMD:C_0805_2012Metric", 61.1, 40.6, 90, {"1": "+5V", "2": "GND"})
buck2 = {"1": "EN_3V3", "2": "GND", "3": "SW_3V3", "4": "+5V", "5": "PG_3V3", "6": "FB_3V3"}
put("U9", "Package_TO_SOT_SMD:SOT-23-6", 66, 36.5, 270, buck2, "TPS62A02")
put("C21", "Capacitor_SMD:C_0805_2012Metric", 64.3, 39.7, 0, {"1": "GND", "2": "+5V"})
put("L2", "Inductor_SMD:L_1008_2520Metric", 62.8, 33.5, 90, {"1": "SW_3V3", "2": "+3V3"})
put("C22", "Capacitor_SMD:C_0805_2012Metric", 61.7, 29.7, 90, {"1": "+3V3", "2": "GND"})
put("C23", "Capacitor_SMD:C_0805_2012Metric", 63.9, 29.7, 90, {"1": "+3V3", "2": "GND"})
tap("L1", "2", 2.9, 0); tap("C13", "1", 1.8, 0)                     # +5V down to L3
tap("L2", "2", -2.0, 0); tap("C22", "1", -1.6, 0); tap("C23", "1", 1.6, 0)                # +3V3 down to L3
tap("C12", "2", -1.5, 0); tap("C21", "1", 0, -1.4)                  # ground
tap("C22", "2", 0, -1.35); tap("C23", "2", 0, -1.35)
tap("C11", "2", 1.6, 0); tap("C10", "1", -1.6, 0); tap("D1", "1", -2.2, 0)
track("+12V_F", pad("Q1", "3"), pad("F1", "1"), 0.6)

for name, (x, y), t in (("+5V", (70, 43), (1.6, 0)), ("+3V3", (58.5, 26), (0, 1.5)), ("+3V3A", (27.5, 28.2), (0, -1.5)),
                        ("+1V8", (13.2, 22.2), None), ("+12V", (56.9, 53.0), None)):
    put("TP_" + name.strip("+"), "TestPoint:TestPoint_Pad_D1.5mm", x, y, 0, {"1": name})
    if t:
        tap("TP_" + name.strip("+"), "1", t[0], t[1])

pcbnew.SaveBoard(os.path.join(OUT, "h7cu.kicad_pcb"), B)
vias = [t for t in B.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
print("footprints", len(B.GetFootprints()), "vias", len(vias), "nets", B.GetNetCount())
for ref, nums in (("U8", "123"), ("U9", "1234"), ("U4", "15"), ("U5", "15"), ("L1", "12"), ("C11", "12"), ("Q1", "23"), ("D1", "2"),
                  ("C10", "2"), ("J1", "1"), ("F1", "2"), ("C51", "1"), ("U6", "4"), ("C21", "2"), ("C12", "1"), ("C13", "1")):
    for n in nums:
        x, y = pad(ref, n)
        print("  %s.%s %-8s (%.3f, %.3f)" % (ref, n, padnet(ref, n), x, y))
