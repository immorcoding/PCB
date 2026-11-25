"""Page-drawing helpers for a multi-page generated schematic (kisch.Design), one module per page.

A page module (<board dir>/sch/<page>.py) defines   build(sh)   where `sh` is a Sheet; it imports what it needs
from here (`from Tools.KiCadDesignTools.schematic.sheet import FP, NC, P, U, symbol, kisch`). The pages are listed
in the board's board.toml [schematic] and drawn by Tools.KiCadDesignTools.schematic.generate. Style, same on every
page:

  - Every pin gets a short stub that ends in a power symbol or a GLOBAL label. There are no long wires
    and no local labels, so every named net has the same bare name on every page ("FMC_D0", "FB_5V").
  - Nets in POWER use the stock power symbols; any other rail (VDDA_MCU, +12V_IN, LED_A ...) is a label.
  - Coordinates are grid units of 2.54 mm: P(i, j). Everything stays on the 1.27 mm grid (RUL-8).
  - References are page-numbered: page n uses R<n>01.., C<n>01.., U<n>01.. ([schematic] pages in board.toml).
  - A pin left out of `nets` is an error unless the symbol marks it no_connect; write NC explicitly.

The board's values come from board.toml through configure(cfg), which generate calls before it imports the pages:
  LIB      [board] lib: the project symbol library (<lib>.kicad_sym) and footprint library (<lib>.pretty)
  POWER    [schematic] power_symbols: nets drawn with power symbols
  FP       [schematic.footprints]: short name -> footprint; the helpers use the keys C0402 C0603 C0805 C1206
           (cap_fp), R0402 (R), R0603 R0805 (link), TP_1.5 (tp)
  COPIES   [schematic.power_copies]: a power net without a stock symbol -> the stock one copied under its name
  CFG      the board itself (Tools.KiCadDesignTools.schematic.swap reads [schematic.swap] through it)
FP and POWER are filled in place, so `from ...sheet import FP` in a page sees the board's table.

Connectivity is judged from the exported netlist (RUL-6, Tools.KiCadDesignTools.schematic.check), never from the
drawing.
"""
import math

from Tools.KiCadDesignTools.schematic import kisch
from Tools.KiCadDesignTools.schematic.kisch import find, find_all, xform

U = 2.54
NC = None
LIB = None                           # project symbol library and footprint library ([board] lib)
POWER = set()                        # nets drawn with power symbols ([schematic] power_symbols)
FP = {}                              # footprints by short name ([schematic.footprints])
COPIES = {}                          # power net -> stock power symbol it is a renamed copy of ([schematic.power_copies])
CFG = None                           # the board (core.config), for schematic.swap


def configure(cfg):
    """The board's library name, power nets, footprint table and power-symbol copies from board.toml."""
    global LIB, CFG
    CFG = cfg
    LIB = cfg.need("board.lib")
    POWER.clear()
    POWER.update(cfg.need("schematic.power_symbols"))
    FP.clear()
    FP.update(cfg.need("schematic.footprints"))
    COPIES.clear()
    COPIES.update(cfg.get("schematic.power_copies", {}))


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
        self.rails = {}                      # supply renaming in force, e.g. {"+3V3": "+3V3_SD"}; see link()

    # ---- low level
    def pin_dirs(self, part):
        """{pin number: unit vector pointing away from the body}, schematic coordinates, rotation applied."""
        out = {}
        for unit in find_all(self.page.libsyms[part.lib_id], "symbol"):
            for p in find_all(unit, "pin"):
                a = math.radians(float(find(p, "at")[3]))
                out[str(find(p, "number")[1])] = xform(-round(math.cos(a)), -round(math.sin(a)), part.rot)
        return out

    def attach(self, part, nets, stub=2, raw=False):
        """Connect every pin of `part`. nets: {pin number or unique pin name: net name | NC}.
        Net names go through self.rails (a block fed through a 0 ohm link) unless raw=True."""
        if not raw:
            nets = {k: self.rails.get(v, v) for k, v in nets.items()}
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
        """A power symbol for a net in POWER. A net in COPIES has no stock symbol (e.g. +3V3A): the project library
        has a copy of the stock one (power:+3V3) under that name (the net name of a power symbol is its value)."""
        if net in COPIES:
            lib_id = LIB + ":" + net
            if lib_id not in SYMBOLS:
                src = COPIES[net]

                def ren(node):
                    if isinstance(node, list):
                        return [ren(c) for c in node]
                    if isinstance(node, str) and (node == src or node.startswith(src + "_")):
                        return type(node)(net + node[len(src):])
                    return node
                SYMBOLS[lib_id] = ren(kisch.load_symbol("power:" + src))
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

    def caps(self, first, values, i, j, net, bot="GND", step=4, fp=None):
        """A row of decoupling capacitors from grid (i, j) to the right: C<first>, C<first+1> ...
        values: list of value strings; fp: one footprint for the whole row (default: by value, cap_fp)."""
        for k, v in enumerate(values):
            self.C("C%d" % (first + k), v, i + k * step, j, net, bot, fp=fp)

    def tp(self, ref, net, i, j, kind="TP_1.5"):
        """A test point on `net` (pad pointing down from (i, j))."""
        part = self.page.sym("Connector:TestPoint", ref, net, *P(i, j), 0, FP[kind])
        self.attach(part, {"1": net}, stub=1)
        return part

    def link(self, ref, src, dst, i, j, size="R0805", flag_at=None):
        """A 0 ohm link from rail `src` to the block rail `dst` (user 2026-11-20: one at the supply entry of
        every block, so that blocks can be powered one at a time during bring-up), with the PWR_FLAG the
        block rail needs. Horizontal at grid (i, j); the flag sits 8 units below, or at flag_at=(i, j). After this call set
        sh.rails = {src: dst} for the parts of the block."""
        x, y = P(i, j)
        part = self.page.sym("Device:R", ref, "0R", x, y, 90, FP[size], ref_at=(x, y - 1.0 * U, None), val_at=(x, y + 1.0 * U, None),
                             fields={"Rating": "jumper, 2 A or more" if size != "R0603" else "jumper, 1 A or more"})
        nets = {}
        for num, _n, pt in part.pins():
            nets[num] = src if pt[0] < x else dst
        assert len(set(nets.values())) == 2
        self.attach(part, nets, stub=1, raw=True)
        saved, self.rails = self.rails, {}
        self.flag(dst, *(flag_at or (i, j + 8)))
        self.rails = saved
        return part

    def flag(self, net, i, j):
        """PWR_FLAG on a net that is driven through a label or a passive part (keeps ERC's
        'power input not driven' quiet). One per net on the whole design."""
        x, y = P(i, j)
        self.page.flag((x, y))
        end = (x, round(y + U, 4))
        self.page.wire((x, y), end)
        net = self.rails.get(net, net)
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
    """Define a rectangular project symbol (see kisch.box_symbol) and return its lib id "<lib>:<name>"."""
    lib_id = "%s:%s" % (LIB, name)
    if lib_id not in SYMBOLS:
        SYMBOLS[lib_id] = kisch.box_symbol(name, **kw)
        kisch.register_symbol(lib_id, SYMBOLS[lib_id])
    return lib_id
