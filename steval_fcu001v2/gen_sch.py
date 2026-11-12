"""Generate steval_fcu001v2.kicad_sch.

    D:\\KiCad\\bin\\python.exe steval_fcu001v2\\gen_sch.py

Re-capture of ST's STEVAL-FCU001V2 flight controller schematic (schematic pack
Rev 2, June 2024, in ref/). Reference designators follow ST's so the result can
be checked against ref/steval-fcu001v2-schematic.pdf and the ST BOM.

Every pin gets a short stub with a net label or a power symbol; there are no
long wires. Connectivity is checked from the exported netlist.

Differences from the ST drawing (see README.md for the reasons):
  V_USB -> VBUS, VBAT+ -> +BATT          (stock KiCad power symbols)
  USB_DP/USB_DM -> USB_D+/USB_D-         (KiCad differential pair naming)
  DP/DM -> USB_CONN_D+/USB_CONN_D-
  MOTORn- -> MOTORn_N
  R25 (0R between two ground symbols) is dropped: one GND net.
  Motor headers P1/P4/P2/P5 -> solder pads MP1..MP8; Pn_2 -> Mn_OUT.

Once the schematic is edited by hand in KiCad, the .kicad_sch is the source of
truth and re-running this script would overwrite those edits.

Coordinates are in units of 2.54 mm; P(i, j) converts to mm.
"""
import math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
from kisch import Sch, find, find_all, xform

U = 2.54
def P(i, j): return (round(i * U, 4), round(j * U, 4))

POWER = {"GND", "VDD", "+BATT", "VBUS"}
NC = None

FP_C = "Capacitor_SMD:C_0402_1005Metric"
FP_R = "Resistor_SMD:R_0402_1005Metric"
FP_R0603 = "Resistor_SMD:R_0603_1608Metric"
FP_LED = "LED_SMD:LED_0603_1608Metric"
FP_SOD323 = "Diode_SMD:D_SOD-323"
FP_H2 = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Horizontal"
FP_V4 = "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical"
FP_V6 = "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical"
FP_MPAD = "Connector_Wire:SolderWirePad_1x01_SMD_1.5x3mm"
FP_FET ="Package_SON:VSON-8_3.3x3.3mm_P0.65mm_NexFET"

s = Sch("steval_fcu001v2", "STEVAL-FCU001V2 flight controller (re-capture)", paper="A3",
        rev="A", date="2026-11-12")


# ---- helpers -------------------------------------------------------------
def pin_dirs(part):
    """{pin number: (dx, dy)} unit vector pointing away from the symbol body, in
    schematic coordinates, taking the part rotation into account."""
    out = {}
    for unit in find_all(s.libsyms[part.lib_id], "symbol"):
        for p in find_all(unit, "pin"):
            a = math.radians(float(find(p, "at")[3]))
            dx, dy = xform(-round(math.cos(a)), -round(math.sin(a)), part.rot)
            out[str(find(p, "number")[1])] = (dx, dy)
    return out

PWR_ROT = {  # (is GND, direction) -> power symbol rotation
    (True, (-1, 0)): 270, (True, (1, 0)): 90, (True, (0, -1)): 180, (True, (0, 1)): 0,
    (False, (-1, 0)): 90, (False, (1, 0)): 270, (False, (0, -1)): 0, (False, (0, 1)): 180,
}
LBL_ROT = {(-1, 0): 180, (1, 0): 0, (0, -1): 90, (0, 1): 270}

def attach(part, nets, stub=2):
    """Connect every pin of `part`. nets: {pin number: net name | NC}. A pin
    number missing from `nets` is an error unless its type is no_connect."""
    dirs = pin_dirs(part)
    types = {p[0]: p[4] for p in part._pins}
    by_pt = {}
    for num, _name, pt in part.pins():
        if num not in nets:
            if types[num] == "no_connect":
                continue
            raise KeyError(f"{part.ref}: pin {num} has no net assigned")
        prev = by_pt.setdefault(pt, (nets[num], dirs[num]))
        if prev[0] != nets[num]:
            raise ValueError(f"{part.ref}: stacked pins at {pt} on different nets")
    ends = {}                                    # (net, dir) -> [stub end points]
    for pt, (net, d) in by_pt.items():
        if net is NC:
            s.nc(pt)
            continue
        end = (round(pt[0] + d[0] * stub * U, 4), round(pt[1] + d[1] * stub * U, 4))
        s.wire(pt, end)
        if net in POWER:
            ends.setdefault((net, d), []).append(end)
        else:
            s.label(net, end, LBL_ROT[d])
    for (net, d), pts in ends.items():
        # neighbouring pins (one grid step apart) on the same rail share one symbol
        pts.sort()
        group = [pts[0]]
        for pt in pts[1:] + [None]:
            if pt and abs(pt[0] - group[-1][0]) + abs(pt[1] - group[-1][1]) <= U + 1e-6:
                group.append(pt)
                continue
            if len(group) > 1:
                s.wire(group[0], group[-1])
            g0 = group[0]
            # sideways symbols: put the net name beyond the symbol, clear of the stub
            kw = {"val_at": (g0[0] + d[0] * 2.4 * U, g0[1])} if d[0] else {}
            s.power(net, g0, PWR_ROT[(net == "GND", d)], **kw)
            group = [pt]

def two(lib, ref, val, i, j, fp, top, bot, rot=0, tx=0.8, **kw):
    """Vertical 2-pin part centred on (i, j); `top`/`bot` are the nets on the
    upper and lower pin."""
    x, y = P(i, j)
    part = s.sym(lib, ref, val, x, y, rot, fp,
                 ref_at=(x + tx * U, y - 0.5 * U, "left"), val_at=(x + tx * U, y + 0.5 * U, "left"), **kw)
    nets = {}
    for num, _n, pt in part.pins():
        nets[num] = top if pt[1] < y else bot
    attach(part, nets, stub=1)
    return part

def C(ref, val, i, j, top, bot="GND"): return two("Device:C", ref, val, i, j, FP_C, top, bot)
def R(ref, val, i, j, top, bot, fp=FP_R, **kw): return two("Device:R", ref, val, i, j, fp, top, bot, **kw)

def ic(lib, ref, val, i, j, fp, nets, **kw):
    part = s.sym(lib, ref, val, *P(i, j), 0, fp, **kw)
    attach(part, nets)
    return part

def title(text, i, j):
    s.text(text, P(i, j), size=1.8, bold=True)


# ======================================================================
# Row A: USB, charger, regulator, clock, reset
# ======================================================================
title("USB", 6, 7)
# ST fits Molex 47590-0001 (micro-AB, sits in a board-edge cut-out). 47346-0001 is the
# plain surface-mount micro-B from the same maker: same five contacts, straight board edge.
ic("Connector:USB_B_Micro", "CN1", "Micro_USB_B 47346-0001", 10, 17,
   "Connector_USB:USB_Micro-B_Molex_47346-0001",
   {"1": "VBUS", "2": "USB_CONN_D-", "3": "USB_CONN_D+", "4": NC, "5": "GND", "SH": "USB_SHIELD"})
ic("Power_Protection:USBLC6-2P6", "U3", "USBULC6-2M6", 30, 17,
   "Package_SON:Texas_USON-6_1x1.45mm_P0.5mm_SMD",
   {"1": "USB_D+", "6": "USB_CONN_D+", "3": "USB_D-", "4": "USB_CONN_D-", "2": "GND", "5": "USBLC_VBUS"})

# unidirectional TVS, cathode (pin 1) on VBUS
two("Device:D_Zener", "D5", "ESDA7P60-1U1M", 20, 26, "Diode_SMD:ST_QFN-2L_1.6x1.0mm", "VBUS", "GND", rot=270)

title("Li-Ion charger", 44, 7)
ic("Battery_Management:MCP73831-2-OT", "U4", "STC4054GR", 52, 17, "Package_TO_SOT_SMD:TSOT-23-5",
   {"1": "CHG_STAT", "2": "GND", "3": "+BATT", "4": "VBUS", "5": "CHG_PROG"})

title("3.3 V LDO", 66, 7)
ic("Regulator_Linear:LD39015M33R", "U6", "LD39015M33R", 74, 17, "Package_TO_SOT_SMD:SOT-23-5",
   {"1": "+BATT", "2": "GND", "3": "+BATT", "5": "VDD"})

title("HSE 16 MHz", 86, 7)
ic("Device:Crystal_GND24", "Y1", "16MHz", 92, 17, "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
   {"1": "OSC_IN", "3": "OSC_OUT", "2": "GND", "4": "GND"},
   ref_at=(92 * U, 14 * U), val_at=(92 * U, 15 * U))

title("Reset / test points", 100, 7)
ic("Switch:SW_Push_Shielded", "S1", "KMR231GLFS", 106, 17,
   "Button_Switch_SMD:SW_Push_1P1T-SH_NO_CK_KMR2xxG", {"1": "NRST", "2": "GND", "SH": "GND"},
   ref_at=(106 * U, 13 * U), val_at=(106 * U, 14 * U))
for n, net in enumerate(["SWDIO", "SWCLK", "NRST"]):
    x = 100 + 4 * n
    ic("Connector:TestPoint", f"TP{n + 1}", "TP", x, 26, "TestPoint:TestPoint_Pad_D1.0mm", {"1": net},
       ref_at=((x + 0.8) * U, 24 * U, "left"), hide_value=True)

# ======================================================================
# Row B: sensors and BLE module
# ======================================================================
title("Pressure sensor (SPI2)", 6, 33)
ic("Sensor_Pressure:LPS22HH", "U7", "LPS22HH", 14, 45, "Package_LGA:ST_HLGA-10_2x2mm_P0.5mm_LayoutBorder3x2y",
   {"1": "VDD", "10": "VDD", "2": "S2_CLK", "4": "S2_SDI", "5": "S2_SDO", "6": "LPS22HH_CS", "7": NC,
    "3": "GND", "8": "GND", "9": "GND"})

title("IMU (SPI2)", 34, 33)
ic("Sensor_Motion:LSM6DSL", "U8", "LSM6DSR", 46, 45, "Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y",
   {"1": "S2_SDO", "2": "VDD", "3": "VDD", "4": NC, "5": "VDD", "8": "VDD", "6": "GND", "7": "GND",
    "9": NC, "12": "LSM6DSR_CS", "13": "S2_CLK", "14": "S2_SDI"},
   ref_at=(40 * U, 38 * U, "left"), val_at=(40 * U, 39 * U, "left"))

title("BLE module (SPI1)", 66, 33)
ic("RF_Bluetooth:SPBTLE-RF", "U1", "BLUENRG-M0A", 84, 45, "RF_Module:ST_SPBTLE",
   {"1": NC, "2": NC, "3": NC, "4": "BLE_IRQ", "5": "VDD", "6": "GND", "7": "S1_CLK", "8": "S1_MISO",
    "9": "S1_MOSI", "10": "BLE_CS", "11": "BLE_RSTN"},
   ref_at=(77 * U, 38.5 * U, "left"), val_at=(77 * U, 39.5 * U, "left"))

# ======================================================================
# MCU
# ======================================================================
title("MCU", 122, 22)
ic("MCU_ST_STM32F4:STM32F401CCUx", "U2", "STM32F401CCU6", 138, 45,
   "Package_DFN_QFN:QFN-48-1EP_7x7mm_P0.5mm_EP5.6x5.6mm",
   {"1": "VDD", "2": "LPS22HH_CS", "3": "USB_MONITOR", "4": NC, "5": "OSC_IN", "6": "OSC_OUT",
    "7": "NRST", "8": "GND", "9": "VDD", "10": "TIM2_CH1", "11": "TIM2_CH2", "12": "TIM2_CH3",
    "13": "TIM2_CH4", "14": "BLE_IRQ", "15": "S1_CLK", "16": "S1_MISO", "17": "S1_MOSI",
    "18": "BLE_CS", "19": "VBAT_SENSE", "20": "BLE_RSTN", "21": "I2C2_SCL", "22": "VCAP1",
    "23": "GND", "24": "VDD", "25": NC, "26": "S2_CLK", "27": "S2_SDO", "28": "S2_SDI",
    "29": "LSM6DSR_CS", "30": "USART1_TX", "31": "USART1_RX", "32": "USB_D-", "33": "USB_D+",
    "34": "SWDIO", "35": "GND", "36": "VDD", "37": "SWCLK", "38": NC, "39": "I2C2_SDA",
    "40": "LED2", "41": "LED1", "42": "MOTOR1", "43": "MOTOR2", "44": "GND", "45": "MOTOR3",
    "46": "MOTOR4", "47": "GND", "48": "VDD", "49": "GND"})

# ======================================================================
# Row C: connectors and motor switches
# ======================================================================
title("Connectors", 6, 62)
def conn(ref, val, n, i, fp, nets, lib=None):
    lib = lib or f"Connector_Generic:Conn_01x{n:02d}"
    ic(lib, ref, val, i, 69, fp, {str(k + 1): net for k, net in enumerate(nets)},
       ref_at=(i * U, 64 * U), val_at=(i * U, 74.5 * U))

conn("BT1", "Battery", 2, 12, FP_H2, ["+BATT", "GND"])
# Motor outputs: bare solder pads instead of ST's 2-pin headers P1/P4/P2/P5
# (MP1/MP2 = motor 1 +/-, MP3/MP4 = motor 2, ...). One pad per part so the
# pads can go on either side of the board.
for n in range(4):
    for k, (sign, net) in enumerate([("+", "+BATT"), ("-", f"M{n + 1}_OUT")]):
        i = 22 + 12 * n + 6 * k
        ic("Connector_Generic:Conn_01x01", f"MP{2 * n + k + 1}", f"M{n + 1}{sign}", i, 69, FP_MPAD, {"1": net},
           ref_at=(i * U, 67 * U), val_at=(i * U, 71 * U))
conn("P3", "I2C", 4, 72, FP_V4, ["VDD", "I2C2_SDA", "I2C2_SCL", "GND"])
conn("P7", "USART", 4, 84, FP_V4, ["VDD", "GND", "USART1_RX", "USART1_TX"])
conn("P6", "FC_Signal", 6, 96, FP_V6, ["+BATT", "TIM2_CH1", "TIM2_CH2", "TIM2_CH3", "TIM2_CH4", "GND"])
conn("P8", "SWD", 10, 110, "Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical_SMD",
     ["VDD", "SWDIO", "GND", "SWCLK", "GND", NC, "GND", NC, "GND", "NRST"],
     lib="Connector_Generic:Conn_02x05_Odd_Even")

title("Mounting holes", 100, 48)
for n in range(4):                    # not on the ST schematic
    i = 102 + 4 * n
    ic("Mechanical:MountingHole", f"H{n + 1}", "M3", i, 53, "MountingHole:MountingHole_3.2mm_M3", {},
       ref_at=(i * U, 51 * U), hide_value=True)

title("Motor low-side switches", 122, 68)
for n in range(4):
    i = 124 + 10 * n
    ic("Transistor_FET:Q_NMOS_SSSGD_AvalancheRated", f"Q{n + 1}", "STL10N3LLH5", i, 77, FP_FET,
       {"1": "GND", "2": "GND", "3": "GND", "4": f"M{n + 1}_GATE", "5": f"MOTOR{n + 1}_N"},
       ref_at=((i + 2) * U, 78.5 * U, "left"), val_at=((i + 2) * U, 79.5 * U, "left"))

# ======================================================================
# Rows D/E: two-pin parts, grouped by function
# ======================================================================
title("MCU decoupling / crystal load", 118, 7)
for k, (ref, val, top) in enumerate([("C3", "100nF", "VDD"), ("C4", "100nF", "VDD"), ("C5", "100nF", "VDD"),
                                     ("C6", "100nF", "VDD"), ("C7", "1uF", "VDD"), ("C11", "4.7uF", "VCAP1"),
                                     ("C8", "15pF", "OSC_IN"), ("C9", "15pF", "OSC_OUT")]):
    C(ref, val, 121 + 5 * k, 15, top)

title("Passives, diodes, LEDs (each end labelled with its net)", 6, 79)
cells = [
    # USB
    ("C", "C12", "100nF", "VBUS", "GND"), ("C", "C23", "100nF", "USBLC_VBUS", "GND"),
    ("R", "R26", "1M", "USB_SHIELD", "GND"), ("C", "C13", "4.7nF", "USB_SHIELD", "GND"),
    ("R", "R27", "100k", "VBUS", "USB_MONITOR"), ("R", "R28", "100k", "USB_MONITOR", "GND"),
    # charger
    ("C", "C14", "1uF", "VBUS", "GND"), ("C", "C15", "100nF", "VBUS", "GND"),
    ("R", "R30", "5.1k", "CHG_PROG", "GND"), ("R", "R29", "510R", "VBUS", "LD3_A"),
    ("LED", "LD3", "RED", "LD3_A", "CHG_STAT"),
    # LDO
    ("C", "C16", "4.7uF", "+BATT", "GND"), ("C", "C18", "100nF", "+BATT", "GND"),
    ("C", "C17", "1uF", "VDD", "GND"),
    # battery sense
    ("R", "R10", "10k", "+BATT", "VBAT_SENSE"), ("R", "R11", "20k", "VBAT_SENSE", "GND"),
    ("C", "C2", "100nF", "VBAT_SENSE", "GND"),
    # MCU
    ("R", "R22", "100k", "VDD", "NRST"), ("C", "C10", "100nF", "NRST", "GND"),
    ("R", "R23", "10k", "VDD", "SWDIO"), ("R", "R24", "10k", "SWCLK", "GND"),
    ("R", "R20", "2.2k", "VDD", "LD1_A"), ("LED", "LD1", "RED", "LD1_A", "LED1"),
    ("R", "R21", "2.2k", "VDD", "LD2_A"), ("LED", "LD2", "RED", "LD2_A", "LED2"),
    # BLE, sensors
    ("C", "C1", "1uF", "VDD", "GND"), ("R", "R1", "47k", "BLE_IRQ", "GND"),
    ("C", "C19", "1uF", "VDD", "GND"), ("C", "C20", "100nF", "VDD", "GND"),
    ("C", "C21", "1uF", "VDD", "GND"), ("C", "C22", "100nF", "VDD", "GND"),
    # motors: gate resistor, gate pull-down, flyback diode, output select
    ("R", "R2", "1k", "MOTOR1", "M1_GATE"), ("R", "R4", "10k", "M1_GATE", "GND"),
    ("SK", "D1", "BAT60J", "+BATT", "MOTOR1_N"),
    ("R0", "R12", "0R", "MOTOR1_N", "M1_OUT"), ("DNP", "R14", "0R", "MOTOR1", "M1_OUT"),
    ("R", "R3", "1k", "MOTOR2", "M2_GATE"), ("R", "R5", "10k", "M2_GATE", "GND"),
    ("SK", "D2", "BAT60J", "+BATT", "MOTOR2_N"),
    ("R0", "R16", "0R", "MOTOR2_N", "M2_OUT"), ("DNP", "R18", "0R", "MOTOR2", "M2_OUT"),
    ("R", "R6", "1k", "MOTOR3", "M3_GATE"), ("R", "R7", "10k", "M3_GATE", "GND"),
    ("SK", "D3", "BAT60J", "+BATT", "MOTOR3_N"),
    ("R0", "R13", "0R", "MOTOR3_N", "M3_OUT"), ("DNP", "R15", "0R", "MOTOR3", "M3_OUT"),
    ("R", "R8", "1k", "MOTOR4", "M4_GATE"), ("R", "R9", "10k", "M4_GATE", "GND"),
    ("SK", "D4", "BAT60J", "+BATT", "MOTOR4_N"),
    ("R0", "R17", "0R", "MOTOR4_N", "M4_OUT"), ("DNP", "R19", "0R", "MOTOR4", "M4_OUT"),
]
for k, (kind, ref, val, top, bot) in enumerate(cells):
    i, j = 8 + 5 * (k % 30), 89 + 15 * (k // 30)
    if kind == "C":
        C(ref, val, i, j, top, bot)
    elif kind == "R":
        R(ref, val, i, j, top, bot)
    elif kind == "R0":                    # solder bridge: 0603, carries motor current
        R(ref, val, i, j, top, bot, fp=FP_R0603)
    elif kind == "DNP":
        R(ref, val, i, j, top, bot, dnp=True)
    elif kind == "LED":                   # anode on top
        two("Device:LED", ref, val, i, j, FP_LED, top, bot, rot=90, tx=1.7)
    elif kind == "SK":                    # cathode on top
        two("Diode:BAT60A", ref, val, i, j, FP_SOD323, top, bot, rot=270)

s.text("Source: ST schematic pack STEVAL-FCU001V2 Rev 2 (June 2024), see ref/. Deviations and unverified items: README.md.",
       P(6, 112))

out = os.path.join(HERE, "steval_fcu001v2.kicad_sch")
s.save(out)
print("wrote", out, "-", len(s.parts), "symbols")
