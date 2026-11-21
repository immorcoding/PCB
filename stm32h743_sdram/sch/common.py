"""Shared drawing helpers for the schematic pages of the STM32H743 + SDRAM board.

A page module (sch/<page>.py) defines   build(sh)   where `sh` is a Sheet. Style, same on every page:

  - Every pin gets a short stub that ends in a power symbol or a GLOBAL label. There are no long wires
    and no local labels, so every named net has the same bare name on every page ("FMC_D0", "FB_5V").
  - Nets in POWER use the stock power symbols; any other rail (VDDA_MCU, +12V_IN, LED_A ...) is a label.
  - Coordinates are grid units of 2.54 mm: P(i, j). Everything stays on the 1.27 mm grid (RUL-8).
  - References are page-numbered: page n uses R<n>01.., C<n>01.., U<n>01.. (see PAGES in gen_sch.py).
  - A pin left out of `nets` is an error unless the symbol marks it no_connect; write NC explicitly.

Connectivity is judged from the exported netlist (RUL-6), never from the drawing.
"""
import math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
import kisch
from kisch import find, find_all, xform

U = 2.54
NC = None
LIB = "h743"                         # project symbol library (h743.kicad_sym) and footprint library (h743.pretty)
POWER = {"GND", "+3V3", "+5V", "+12V", "+3V3A", "+1V8"}      # nets drawn with stock power symbols

FP = {
    "C0402": "Capacitor_SMD:C_0402_1005Metric", "C0603": "Capacitor_SMD:C_0603_1608Metric",
    "C0805": "Capacitor_SMD:C_0805_2012Metric", "C1206": "Capacitor_SMD:C_1206_3216Metric",
    "R0402": "Resistor_SMD:R_0402_1005Metric", "R0603": "Resistor_SMD:R_0603_1608Metric",
    "R0805": "Resistor_SMD:R_0805_2012Metric",
    "L0603": "Inductor_SMD:L_0603_1608Metric", "L0805": "Inductor_SMD:L_0805_2012Metric",
    "LED0603": "LED_SMD:LED_0603_1608Metric",
    "TP_1.5": "TestPoint:TestPoint_Pad_D1.5mm", "TP_1.0": "TestPoint:TestPoint_Pad_D1.0mm",
    "TP_LOOP": "TestPoint:TestPoint_Loop_D2.50mm_Drill1.0mm",
}

PWR_ROT = {  # (is GND, direction away from the pin) -> power symbol rotation
    (True, (-1, 0)): 270, (True, (1, 0)): 90, (True, (0, -1)): 180, (True, (0, 1)): 0,
    (False, (-1, 0)): 90, (False, (1, 0)): 270, (False, (0, -1)): 0, (False, (0, 1)): 180,
}
LBL_ROT = {(-1, 0): 180, (1, 0): 0, (0, -1): 90, (0, 1): 270}


def P(i, j):
    return (round(i * U, 4), round(j * U, 4))


def cap_fp(value):
    """Default capacitor footprint by value: up to 100 nF 0402, up to 4.7 uF 0603, 10 uF 0805, above 1206."""
    v = value.lower().split()[0]         # "470nF X7R" -> "470nf"; "4.7 uF" must be written "4.7uF"
    num = float("".join(ch for ch in v if ch.isdigit() or ch == ".") or 0)
    uf = num * (1e-6 if "pf" in v or v.endswith("p") else 1e-3 if "nf" in v or v.endswith("n") else 1)
    return FP["C0402"] if uf <= 0.1 else FP["C0603"] if uf <= 4.7 else FP["C0805"] if uf <= 10 else FP["C1206"]


class Sheet:
    def __init__(self, page, number):
        self.page, self.number = page, number
        self.nets = {}                       # net -> [(ref, pin number)] as intended by this page (for self-checks)

    # ---- low level
    def pin_dirs(self, part):
        """{pin number: unit vector pointing away from the body}, schematic coordinates, rotation applied."""
        out = {}
        for unit in find_all(self.page.libsyms[part.lib_id], "symbol"):
            for p in find_all(unit, "pin"):
                a = math.radians(float(find(p, "at")[3]))
                out[str(find(p, "number")[1])] = xform(-round(math.cos(a)), -round(math.sin(a)), part.rot)
        return out

    def attach(self, part, nets, stub=2):
        """Connect every pin of `part`. nets: {pin number or unique pin name: net name | NC}."""
        dirs = self.pin_dirs(part)
        types = {p[0]: p[4] for p in part._pins}
        names = {}
        for p in part._pins:
            names.setdefault(p[1], []).append(p[0])
        by_num = {}
        for key, net in nets.items():
            key = str(key)
            if key in types:
                nums = [key]
            elif key in names:
                nums = names[key]            # a pin name covers every pin with that name (stacked power pins)
            else:
                raise KeyError(f"{part.ref}: no pin {key}")
            for n in nums:
                if n in by_num and by_num[n] != net:
                    raise ValueError(f"{part.ref}: pin {n} assigned twice")
                by_num[n] = net
        by_pt = {}
        for num, _name, pt in part.pins():
            if num not in by_num:
                if types[num] == "no_connect":
                    continue
                raise KeyError(f"{part.ref}: pin {num} ({_name}) has no net assigned")
            net = by_num[num]
            if net is not NC:
                self.nets.setdefault(net, []).append((part.ref, num))
            prev = by_pt.setdefault(pt, (net, dirs[num]))
            if prev[0] != net:
                raise ValueError(f"{part.ref}: stacked pins at {pt} on different nets")
        ends = {}
        for pt, (net, d) in by_pt.items():
            if net is NC:
                self.page.nc(pt)
                continue
            end = (round(pt[0] + d[0] * stub * U, 4), round(pt[1] + d[1] * stub * U, 4))
            self.page.wire(pt, end)
            if net in POWER:
                ends.setdefault((net, d), []).append(end)
            else:
                self.page.glabel(net, end, LBL_ROT[d])
        for (net, d), pts in ends.items():       # neighbouring pins on the same rail share one power symbol
            pts.sort()
            group = [pts[0]]
            for pt in pts[1:] + [None]:
                if pt and abs(pt[0] - group[-1][0]) + abs(pt[1] - group[-1][1]) <= U + 1e-6:
                    group.append(pt)
                    continue
                if len(group) > 1:
                    self.page.wire(group[0], group[-1])
                g0 = group[0]
                kw = {"val_at": (g0[0] + d[0] * 2.4 * U, g0[1])} if d[0] else {}
                self.power(net, g0, PWR_ROT[(net == "GND", d)], **kw)
                group = [pt]

    def power(self, net, pt, rot=0, **kw):
        """A power symbol for a net in POWER. +3V3A has no stock symbol: the project library has a copy of
        power:+3V3 under that name (the net name of a power symbol is its value)."""
        if net == "+3V3A":
            lib_id = LIB + ":+3V3A"
            if lib_id not in SYMBOLS:
                def ren(node):
                    if isinstance(node, list):
                        return [ren(c) for c in node]
                    if isinstance(node, str) and (node == "+3V3" or node.startswith("+3V3_")):
                        return type(node)("+3V3A" + node[4:])
                    return node
                SYMBOLS[lib_id] = ren(kisch.load_symbol("power:+3V3"))
                kisch.register_symbol(lib_id, SYMBOLS[lib_id])
            return self.page.sym(lib_id, "#PWR%03d" % self.page._next_pwr(), net, pt[0], pt[1], rot, **kw)
        return self.page.power(net, pt, rot, **kw)

    # ---- parts
    def ic(self, lib, ref, val, i, j, fp, nets, rot=0, stub=2, **kw):
        """A multi-pin part with its centre at grid (i, j). kw: fields={"MPN": ...}, dnp=True ..."""
        part = self.page.sym(lib, ref, val, *P(i, j), rot, fp, **kw)
        self.attach(part, nets, stub)
        return part

    def two(self, lib, ref, val, i, j, fp, a, b, horizontal=False, first=None, **kw):
        """A two-pin part centred on (i, j). Vertical: net `a` on the upper pin, `b` on the lower.
        horizontal=True: `a` on the left pin, `b` on the right. The symbol is rotated as needed (R and C
        have vertical pins in the library, D and LED horizontal ones). For a polarised part say which pin
        is the upper / left one with first=<pin number or name>, e.g. first="A" puts the anode on net `a`."""
        x, y = P(i, j)
        pins = kisch.symbol_pins(kisch.load_symbol(lib))
        if len({p[0] for p in pins}) != 2:
            raise ValueError(f"{ref}: {lib} is not a two-pin symbol")
        rot = None
        for r in (0, 90, 180, 270):
            pos = {p[0]: xform(p[2], p[3], r) for p in pins}
            (xa, ya), (xb, yb) = pos.values()
            if (abs(ya - yb) > 1e-6 or xa == xb) if horizontal else (abs(xa - xb) > 1e-6 or ya == yb):
                continue
            head = min(pos, key=lambda n: pos[n][0 if horizontal else 1])
            if first is None or str(first) in (head, next(p[1] for p in pins if p[0] == head)):
                rot = r
                break
        if rot is None:
            raise ValueError(f"{ref}: cannot orient {lib} with first={first!r}")
        if horizontal:
            at = dict(ref_at=(x, y - 1.0 * U, None), val_at=(x, y + 1.0 * U, None))
        else:
            at = dict(ref_at=(x + 0.8 * U, y - 0.5 * U, "left"), val_at=(x + 0.8 * U, y + 0.5 * U, "left"))
        at.update(kw)
        part = self.page.sym(lib, ref, val, x, y, rot, fp, **at)
        nets = {}
        for num, _n, pt in part.pins():
            head = pt[0] < x if horizontal else pt[1] < y
            nets[num] = a if head else b
        if len(set(nets.values())) != 2 and a != b:
            raise ValueError(f"{ref}: both pins ended up on one net")
        self.attach(part, nets, stub=1)
        return part

    def C(self, ref, val, i, j, top, bot="GND", fp=None, **kw):
        return self.two("Device:C", ref, val, i, j, fp or cap_fp(val), top, bot, **kw)

    def R(self, ref, val, i, j, a, b, fp=None, **kw):
        return self.two("Device:R", ref, val, i, j, fp or FP["R0402"], a, b, **kw)

    def caps(self, first, values, i, j, net, bot="GND", step=4):
        """A row of decoupling capacitors from grid (i, j) to the right: C<first>, C<first+1> ...
        values: list of value strings."""
        for k, v in enumerate(values):
            self.C("C%d" % (first + k), v, i + k * step, j, net, bot)

    def tp(self, ref, net, i, j, kind="TP_1.5"):
        """A test point on `net` (pad pointing down from (i, j))."""
        part = self.page.sym("Connector:TestPoint", ref, net, *P(i, j), 0, FP[kind])
        self.attach(part, {"1": net}, stub=1)
        return part

    def flag(self, net, i, j):
        """PWR_FLAG on a net that is driven through a label or a passive part (keeps ERC's
        'power input not driven' quiet). One per net on the whole design."""
        x, y = P(i, j)
        self.page.flag((x, y))
        end = (x, round(y + U, 4))
        self.page.wire((x, y), end)
        if net in POWER:
            self.power(net, end, PWR_ROT[(net == "GND", (0, 1))])
        else:
            self.page.glabel(net, end, 270)

    # ---- annotation
    def title(self, text, i, j):
        self.page.text(text, P(i, j), size=1.8, bold=True)

    def note(self, text, i, j):
        self.page.text(text, P(i, j))

    def box(self, i1, j1, i2, j2):
        self.page.box(*P(i1, j1), *P(i2, j2))


# ---- project symbols (parts that are not in the stock libraries)
SYMBOLS = {}


def symbol(name, **kw):
    """Define a rectangular project symbol (see kisch.box_symbol) and return its lib id "h743:<name>"."""
    lib_id = "%s:%s" % (LIB, name)
    if lib_id not in SYMBOLS:
        SYMBOLS[lib_id] = kisch.box_symbol(name, **kw)
        kisch.register_symbol(lib_id, SYMBOLS[lib_id])
    return lib_id


# ---- nets that cross pages. The name is the contract between page modules; the page in the comment
# owns the circuit that creates or terminates the net. MCU signals are the pins.csv signal names
# (FMC_*, QSPI_*, LCD_*, RMII_*, ETH_MDC, ETH_MDIO, SDMMC1_*, FDCAN1_*, SAI1_*, I2C4_*, USART1_*,
# SWDIO, SWCLK, SWO, and the auxiliary pins LCD_BL_PWM, USER_KEY, LCD_DISP, TP_INT, TP_RST, PHY_NRST,
# SD_CD, CAN_STB, CODEC_NRST, LED1, LED2); they are not repeated here.
SHARED_NETS = {
    "GND": "power symbol; one ground net, analog and digital are not split",
    "+12V": "power symbol; after reverse-polarity protection (power)",
    "+5V": "power symbol; LMR51420 output (power). Also feeds the CAN transceiver, backlight boost, analog LDO",
    "+3V3": "power symbol; TPS62A02 output (power)",
    "+3V3A": "power symbol; TPS7A2033 output (power); codec AVDD / DRVDD only",
    "+1V8": "power symbol; TPS7A2018 output (power); codec DVDD only",
    "VDDA_MCU": "label; +3V3 through a ferrite bead (mcu); VREF+ ties to it",
    "VDDA_PHY": "label; +3V3 through a ferrite bead (eth); PHY VDD1A / VDD2A",
    "NRST": "label; MCU reset (mcu: button, capacitor; io: SWD connector pin 10)",
    "FMC_SDCLK_R": "label; SDRAM side of the SDCLK series resistor (resistor on mcu page, pin on sdram page)",
    "I2C4_SCL": "pull-ups are on the audio page; the lcd page only taps it through 0 ohm links",
    "I2C4_SDA": "as I2C4_SCL",
}
