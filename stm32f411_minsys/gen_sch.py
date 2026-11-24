"""Generate stm32f411_minsys.kicad_sch (STM32F411CEU6 minimal system board).

    D:\\KiCad\\bin\\python.exe stm32f411_minsys\\gen_sch.py

Used to create the first version of the schematic. Once the schematic is
edited by hand in KiCad, the .kicad_sch is the source of truth and re-running
this script would overwrite those edits.

All coordinates are in units of 2.54 mm (100 mil); P(i, j) converts to mm.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
from Tools.KiCadDesignTools.schematic.kisch import Sch

U = 2.54
def P(i, j): return (round(i * U, 4), round(j * U, 4))

FP_C = "Capacitor_SMD:C_0603_1608Metric"
FP_R = "Resistor_SMD:R_0603_1608Metric"
FP_LED = "LED_SMD:LED_0603_1608Metric"
FP_SW = "Button_Switch_SMD:SW_SPST_TS-1088-xR020"

s = Sch("stm32f411_minsys", "STM32F411CEU6 Minimal System", paper="A3", rev="A", date="2026-11-12")


# ---- part helpers (i, j = centre in grid units) --------------------------
def vert(lib, ref, val, i, j, fp, **kw):
    """2-pin part drawn vertically, pin 1 on top (i, j-1.5), pin 2 at (i, j+1.5)."""
    x, y = P(i, j)
    return s.sym(lib, ref, val, x, y, 0, fp,
                 ref_at=(x + U, y - 0.5 * U, "left"), val_at=(x + U, y + 0.5 * U, "left"), **kw)

def C(ref, val, i, j): return vert("Device:C", ref, val, i, j, FP_C)
def R(ref, val, i, j): return vert("Device:R", ref, val, i, j, FP_R)

def horiz(lib, ref, val, i, j, fp, rot, ref_at, val_at):
    x, y = P(i, j)
    return s.sym(lib, ref, val, x, y, rot, fp, ref_at=P(*ref_at), val_at=P(*val_at))

def title(text, i, j):
    s.text(text, P(i, j), size=1.8, bold=True)

def stub_label(pt, name, direction, length=2):
    """Wire stub from a pin plus a net label at its far end. direction: 'L' or 'R'."""
    dx = -length * U if direction == "L" else length * U
    end = (round(pt[0] + dx, 4), pt[1])
    s.wire(pt, end)
    s.label(name, end, 180 if direction == "L" else 0)


# ======================================================================
# 1. USB-C input and 3.3 V regulator
# ======================================================================
title("USB-C / 5V -> 3.3V", 8, 12)
s.box(*P(6, 13), *P(60, 37))

J1 = s.sym("Connector:USB_C_Receptacle_USB2.0_16P", "J1", "USB-C 16P", *P(14, 24), 0,
           "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12")
# VBUS -> D1 -> +5V
D1 = horiz("Device:D_Schottky", "D1", "B5819WS", 29.5, 18, "Diode_SMD:D_SOD-323", 180,
           (29.5, 16), (29.5, 17))
s.wire(J1.pin("A4"), D1.pin("A"))
s.power("VBUS", P(26, 18))
# +5V rail to the LDO
U2 = s.sym("Regulator_Linear:ME6211C33M5", "U2", "ME6211C33M5", *P(41, 19), 0,
           "Package_TO_SOT_SMD:SOT-23-5")
s.wire(D1.pin("K"), U2.pin("1"))
s.power("+5V", P(33, 18))
C1 = C("C1", "1uF", 34, 19.5)
s.power("GND", C1.pin("2"))
s.wire(U2.pin("3"), P(37, 19), P(37, 18))          # CE tied to VIN
s.power("GND", U2.pin("2"))
s.nc(U2.pin("4"))
# +3V3 rail
s.wire(U2.pin("5"), P(54, 18))
C2 = C("C2", "1uF", 46, 19.5)
C3 = C("C3", "10uF", 50, 19.5)
s.power("GND", C2.pin("2")); s.power("GND", C3.pin("2"))
s.power("+3V3", P(48, 18))
R3 = R("R3", "1k", 54, 19.5)                         # power LED
D2 = horiz("Device:LED", "D2", "PWR", 54, 22.5, FP_LED, 90, (56.5, 22), (56.5, 23))
s.power("GND", D2.pin("K"))
# CC pull-downs (5.1k -> UFP / device)
R1 = horiz("Device:R", "R1", "5.1k", 23.5, 20, FP_R, 90, (22.6, 19), (24.6, 19))
R2 = horiz("Device:R", "R2", "5.1k", 23.5, 21, FP_R, 90, (22.6, 22), (24.6, 22))
s.wire(J1.pin("A5"), R1.pin("1"))
s.wire(J1.pin("B5"), R2.pin("1"))
s.wire(R1.pin("2"), P(27, 20), P(27, 21), R2.pin("2"))
s.wire(P(27, 21), P(27, 22))
s.power("GND", P(27, 22))
# D+/D-: both orientations tied together
s.wire(J1.pin("A7"), P(21, 23), P(21, 24), J1.pin("B7"))
s.wire(P(21, 24), P(23, 24)); s.label("USB_D-", P(23, 24))
s.wire(J1.pin("A6"), P(21, 25), P(21, 26), J1.pin("B6"))
s.wire(P(21, 26), P(23, 26)); s.label("USB_D+", P(23, 26))
s.nc(J1.pin("A8")); s.nc(J1.pin("B8"))
s.wire(J1.pin("A1"), P(14, 34))
s.wire(J1.pin("SH"), P(11, 34), P(14, 34))
s.power("GND", P(14, 34))

# ======================================================================
# 2. Decoupling, VDDA filter, VBAT
# ======================================================================
title("Decoupling / VDDA / VBAT", 8, 41)
s.box(*P(6, 42), *P(60, 62))

s.wire(P(10, 46), P(34, 46))                         # +3V3 rail
s.wire(P(10, 49), P(46, 49))                         # GND rail
s.power("+3V3", P(10, 46)); s.power("GND", P(10, 49))
for n, (ref, val) in enumerate([("C4", "4.7uF"), ("C5", "100nF"), ("C6", "100nF"), ("C7", "100nF")]):
    C(ref, val, 13 + 5 * n, 47.5)
FB1 = horiz("Device:FerriteBead", "FB1", "600R@100MHz", 35.5, 46, "Inductor_SMD:L_0603_1608Metric", 90,
            (35.5, 43), (35.5, 44))
s.wire(FB1.pin("2"), P(50, 46))                      # +3.3VA rail
C("C8", "1uF", 41, 47.5)
C("C9", "100nF", 46, 47.5)
s.power("+3.3VA", P(50, 46))
s.flag(P(44, 46))

# VBAT: fed from +3V3 through a diode, can be overridden from the header
D3 = horiz("Device:D", "D3", "1N4148WS", 15.5, 56, "Diode_SMD:D_SOD-323", 180, (15.5, 54), (15.5, 55))
s.wire(P(11, 56), D3.pin("A"))
s.power("+3V3", P(11, 56))
s.wire(D3.pin("K"), P(28, 56)); s.label("VBAT", P(28, 56))
C10 = C("C10", "100nF", 20, 57.5)
s.power("GND", C10.pin("2"))
s.flag(P(25, 56))

# ======================================================================
# 3. HSE crystal
# ======================================================================
title("HSE 8MHz", 8, 66)
s.box(*P(6, 67), *P(30, 82))

Y1 = s.sym("Device:Crystal_GND24", "Y1", "8MHz CL=20pF", *P(18, 72), 0,
           "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
           ref_at=(18 * U, 69 * U), val_at=(18 * U, 70 * U))
C11 = C("C11", "27pF", 13, 74.5)
C12 = C("C12", "27pF", 23, 74.5)
s.wire(Y1.pin("1"), P(13, 72), C11.pin("1"))
s.wire(Y1.pin("3"), P(23, 72), C12.pin("1"))
s.wire(P(13, 72), P(11, 72)); s.label("OSC_IN", P(11, 72), 180)
s.wire(P(23, 72), P(25, 72)); s.label("OSC_OUT", P(25, 72))
s.wire(C11.pin("2"), C12.pin("2"))
s.wire(Y1.pin("2"), P(18, 76))
s.power("GND", P(18, 76))

# ======================================================================
# 4. Reset / boot / user LED
# ======================================================================
title("Reset / Boot / LED", 34, 66)
s.box(*P(32, 67), *P(72, 82))

SW1 = horiz("Switch:SW_Push", "SW1", "RESET", 38, 72, FP_SW, 90, (35.5, 71.5), (35.5, 72.5))
C13 = C("C13", "100nF", 43, 71.5)
s.wire(SW1.pin("2"), C13.pin("1"))
s.wire(C13.pin("1"), P(45, 70)); s.label("NRST", P(45, 70))
s.wire(C13.pin("2"), P(43, 74), SW1.pin("1"))
s.wire(P(38, 74), P(38, 75))
s.power("GND", P(38, 75))

SW2 = horiz("Switch:SW_Push", "SW2", "BOOT0", 52, 72, FP_SW, 90, (49.5, 71.5), (49.5, 72.5))
s.power("+3V3", SW2.pin("2"))
R4 = R("R4", "10k", 52, 76.5)
s.wire(SW2.pin("1"), R4.pin("1"))
s.power("GND", R4.pin("2"))
s.wire(P(52, 74.5), P(54, 74.5)); s.label("BOOT0", P(54, 74.5))

R5 = R("R5", "10k", 61, 73.5)                        # PB2 = BOOT1 pull-down
s.wire(R5.pin("1"), P(61, 71)); s.label("PB2", P(61, 71), 90)
s.power("GND", R5.pin("2"))

R6 = R("R6", "1k", 67, 71.5)                         # user LED on PC13, active low
s.power("+3V3", R6.pin("1"))
D4 = horiz("Device:LED", "D4", "USER", 67, 74.5, FP_LED, 90, (69.5, 74), (69.5, 75))
s.wire(D4.pin("K"), P(67, 77), P(65, 77)); s.label("PC13", P(65, 77), 180)

# ======================================================================
# 5. MCU
# ======================================================================
title("MCU", 62, 12)
U1 = s.sym("MCU_ST_STM32F4:STM32F411CEUx", "U1", "STM32F411CEU6", *P(90, 38), 0)

left = {"NRST": "NRST", "BOOT0": "BOOT0", "PH0": "OSC_IN", "PH1": "OSC_OUT"}
right = {"PA11": "USB_D-", "PA12": "USB_D+", "PA13": "SWDIO", "PA14": "SWCLK"}
for num, name, pt in U1.pins():
    if name.startswith(("PB", "PC", "PH")) or name in ("NRST", "BOOT0"):
        stub_label(pt, left.get(name, name), "L")
    elif name.startswith("PA"):
        stub_label(pt, right.get(name, name), "R")

# supplies
s.wire(U1.pin("1"), P(88, 18)); s.label("VBAT", P(88, 18), 90)
s.wire(U1.pin("24"), P(89, 19), P(91, 19), U1.pin("48"))
s.wire(U1.pin("36"), P(90, 19), P(90, 18))
s.power("+3V3", P(90, 18))
s.wire(U1.pin("9"), P(92, 20), P(94, 20), P(94, 18))
s.power("+3.3VA", P(94, 18))
s.wire(U1.pin("23"), P(90, 55))
s.wire(U1.pin("8"), P(91, 55), P(90, 55))
s.power("GND", P(90, 55))
# VCAP1
C14 = C("C14", "4.7uF", 79, 53.5)
s.wire(U1.pin("22"), P(79, 51), C14.pin("1"))
s.power("GND", C14.pin("2"))

# ======================================================================
# 6. Connectors
# ======================================================================
title("SWD", 64, 57)
J2 = s.sym("Connector_Generic:Conn_01x04", "J2", "SWD", *P(70, 60), 0,
           "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Horizontal")

def header_pin(part, num, net):
    pt = part.pin(num)
    if net.startswith("+") or net == "GND":
        end = (round(pt[0] - U, 4), pt[1])
        s.wire(pt, end)
        s.power(net, end, 270 if net == "GND" else 90, val_at=(end[0] - 2.5 * U, end[1]))
    else:
        stub_label(pt, net, "L")

for n, net in enumerate(["+3V3", "SWDIO", "SWCLK", "GND"], 1):
    header_pin(J2, n, net)

title("Pin headers", 112, 12)
J3 = s.sym("Connector_Generic:Conn_01x20", "J3", "P1", *P(122, 28), 0,
           "Connector_PinHeader_2.54mm:PinHeader_1x20_P2.54mm_Vertical")
J4 = s.sym("Connector_Generic:Conn_01x20", "J4", "P2", *P(142, 28), 0,
           "Connector_PinHeader_2.54mm:PinHeader_1x20_P2.54mm_Vertical")
P1 = ["VBAT", "PC13", "PC14", "PC15", "NRST", "PA0", "PA1", "PA2", "PA3", "PA4",
      "PA5", "PA6", "PA7", "PB0", "PB1", "PB2", "PB10", "+3V3", "GND", "+5V"]
P2 = ["+3V3", "GND", "+5V", "PB9", "PB8", "PB7", "PB6", "PB5", "PB4", "PB3",
      "PA15", "USB_D+", "USB_D-", "PA10", "PA9", "PA8", "PB15", "PB14", "PB13", "PB12"]
for n, net in enumerate(P1, 1): header_pin(J3, n, net)
for n, net in enumerate(P2, 1): header_pin(J4, n, net)

# ======================================================================
# 7. PWR_FLAGs (tell ERC these nets are driven: VBUS/GND by the USB cable,
#    +5V through D1)
# ======================================================================
title("PWR_FLAG", 112, 44)
for k, net in enumerate(["VBUS", "+5V"]):
    i = 114 + 5 * k
    s.power(net, P(i, 48)); s.wire(P(i, 48), P(i, 50)); s.flag(P(i, 50), 180)
s.flag(P(124, 48)); s.wire(P(124, 48), P(124, 50)); s.power("GND", P(124, 50))

s.text("Y1 load caps: C = 2 x (CL - Cstray), Cstray ~ 5-7 pF. Recalculate for the crystal actually purchased.",
       P(8, 85))
s.text("PA9 is NOT wired to VBUS: disable USB VBUS sensing in firmware (NOVBUSSENS).", P(8, 87))

out = os.path.join(HERE, "stm32f411_minsys.kicad_sch")
s.save(out)
print("wrote", out, "-", len(s.parts), "symbols")
