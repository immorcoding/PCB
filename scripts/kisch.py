"""Minimal KiCad schematic writer.

`Sch` writes one flat sheet. `Design` writes a flat multi-page design: a root
file holding one sheet symbol per page and one file per page; pages connect
through global labels (`glabel`) and power symbols, never through hierarchical
pins. Local labels (`label`) stay inside their page.

Pulls symbols out of the stock KiCad libraries, places them, and connects
pins with wires / labels / power symbols. Pin coordinates are computed from
the library geometry, so every wire end lands exactly on a pin.

The output is written in the KiCad 9 file format; run
`kicad-cli sch upgrade` afterwards to bring it to the installed version.
Connectivity must always be confirmed from the exported netlist
(see scripts/sch_check.py), never from this script's intent.

Coordinates: mm, schematic convention (Y grows downward). Keep everything on
the 1.27 mm grid.
"""
import os, re, uuid

SYMBOL_DIR = r"D:\KiCad\share\kicad\symbols"
_NS = uuid.UUID("6f1d3c52-8a0e-4c57-9b7e-51a7c0de0001")
GLABEL_SHAPES = ("input", "output", "bidirectional", "tri_state", "passive")


# ---------------------------------------------------------------- s-expr
class Q(str):
    """A quoted string atom."""


def parse(text):
    pos, n = 0, len(text)
    stack, cur = [], []
    while pos < n:
        c = text[pos]
        if c == "(":
            stack.append(cur); cur = []; pos += 1
        elif c == ")":
            done = cur; cur = stack.pop(); cur.append(done); pos += 1
        elif c == '"':
            j = pos + 1; buf = []
            while text[j] != '"':
                if text[j] == "\\":
                    buf.append(text[j:j + 2]); j += 2
                else:
                    buf.append(text[j]); j += 1
            cur.append(Q("".join(buf))); pos = j + 1
        elif c.isspace():
            pos += 1
        else:
            j = pos
            while j < n and not text[j].isspace() and text[j] not in "()":
                j += 1
            cur.append(text[pos:j]); pos = j
    return cur[0]


def dump(node, ind=0):
    if not isinstance(node, list):
        return f'"{node}"' if isinstance(node, Q) else str(node)
    if all(not isinstance(c, list) for c in node):
        return "(" + " ".join(dump(c) for c in node) + ")"
    pad = "\t" * (ind + 1)
    out = "(" + dump(node[0])
    for c in node[1:]:
        out += ("\n" + pad + dump(c, ind + 1)) if isinstance(c, list) else (" " + dump(c))
    return out + "\n" + "\t" * ind + ")"


def find(node, key):
    return next((c for c in node if isinstance(c, list) and c and c[0] == key), None)


def find_all(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def fmt(v):
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# ---------------------------------------------------------------- library
_lib_text = {}


def _raw_symbol(lib, name):
    if lib not in _lib_text:
        with open(os.path.join(SYMBOL_DIR, lib + ".kicad_sym"), encoding="utf-8") as f:
            _lib_text[lib] = f.read()
    text = _lib_text[lib]
    m = re.search(r'\n\t\(symbol "' + re.escape(name) + r'"\s', text)
    if not m:
        raise KeyError(f"{lib}:{name} not found")
    start = m.start() + 2
    depth, i, in_str = 0, start, False
    while True:
        c = text[i]
        if in_str:
            if c == "\\": i += 1
            elif c == '"': in_str = False
        elif c == '"': in_str = True
        elif c == "(": depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    return parse(text[start:i + 1])


def load_symbol(lib_id):
    """Return the symbol s-expr, flattened if it `extends` another one."""
    lib, name = lib_id.split(":")
    sym = _raw_symbol(lib, name)
    ext = find(sym, "extends")
    if ext:
        parent = load_symbol(f"{lib}:{ext[1]}")
        pname = ext[1]
        body = [c for c in parent[2:] if not (isinstance(c, list) and c[0] == "property")]
        props = {p[1]: p for p in find_all(parent, "property")}
        props.update({p[1]: p for p in find_all(sym, "property")})
        units = []
        for c in body:
            if isinstance(c, list) and c[0] == "symbol":
                c = [c[0], Q(name + c[1][len(pname):])] + c[2:]
            units.append(c)
        head = [c for c in units if not (isinstance(c, list) and c[0] == "symbol")]
        tail = [c for c in units if isinstance(c, list) and c[0] == "symbol"]
        sym = ["symbol", Q(name)] + head + list(props.values()) + tail
    return sym


def symbol_pins(sym):
    """[(number, name, x, y, electrical_type)] in library coordinates (Y up)."""
    pins = []
    for unit in find_all(sym, "symbol"):
        for p in find_all(unit, "pin"):
            at = find(p, "at")
            pins.append((str(find(p, "number")[1]), str(find(p, "name")[1]),
                         float(at[1]), float(at[2]), p[1]))
    return pins


# ---------------------------------------------------------------- geometry
def xform(px, py, rot):
    """Library (Y-up) offset -> schematic (Y-down) offset for a rotation."""
    return {0: (px, -py), 90: (-py, -px), 180: (-px, py), 270: (py, px)}[rot]


class Part:
    def __init__(self, sch, lib_id, ref, x, y, rot, pins):
        self.sch, self.lib_id, self.ref, self.x, self.y, self.rot = sch, lib_id, ref, x, y, rot
        self._pins = pins

    def pin(self, key):
        key = str(key)
        hits = [p for p in self._pins if p[0] == key] or [p for p in self._pins if p[1] == key]
        if not hits:
            raise KeyError(f"{self.ref}: no pin {key}")
        pts = {(p[2], p[3]) for p in hits}
        if len(pts) != 1:
            raise KeyError(f"{self.ref}: pin {key} is ambiguous")
        px, py = pts.pop()
        dx, dy = xform(px, py, self.rot)
        return (round(self.x + dx, 4), round(self.y + dy, 4))

    def pins(self):
        return [(p[0], p[1], self.pin(p[0])) for p in self._pins]


class Sch:
    def __init__(self, project, title="", paper="A3", rev="A", date=""):
        self.project, self.title, self.paper, self.rev, self.date = project, title, paper, rev, date
        self.libsyms, self.items, self.parts = {}, [], []
        self.wires, self.pin_pts = [], []
        self._n, self._pwr = 0, 0
        self._ukey = project                  # prefix of every uuid seed
        self.root = self._uuid("root")        # uuid of this file
        self._inst_path = "/" + self.root     # hierarchy path of the symbols

    def _uuid(self, tag=None):
        self._n += 1
        return str(uuid.uuid5(_NS, f"{self._ukey}/{tag or self._n}/{self._n if tag is None else ''}"))

    def _next_pwr(self):
        self._pwr += 1
        return self._pwr

    # -- symbols
    def sym(self, lib_id, ref, value, x, y, rot=0, footprint="", fields=None,
            ref_at=None, val_at=None, hide_value=False, in_bom=True, on_board=True, dnp=False):
        if lib_id not in self.libsyms:
            s = load_symbol(lib_id)
            s[1] = Q(lib_id)
            self.libsyms[lib_id] = s
        lsym = self.libsyms[lib_id]
        part = Part(self, lib_id, ref, x, y, rot, symbol_pins(lsym))
        self.parts.append(part)
        ang = 0 if rot in (0, 180) else 90
        node = ["symbol", ["lib_id", Q(lib_id)], ["at", fmt(x), fmt(y), str(rot)], ["unit", "1"],
                ["exclude_from_sim", "no"], ["in_bom", "yes" if in_bom else "no"],
                ["on_board", "yes" if on_board else "no"], ["dnp", "yes" if dnp else "no"],
                ["uuid", Q(self._uuid())]]
        values = {"Reference": ref, "Value": value}
        if footprint:
            values["Footprint"] = footprint
        values.update(fields or {})
        placed = {"Reference": ref_at, "Value": val_at}
        seen = set()
        for lp in find_all(lsym, "property"):
            name = str(lp[1]); seen.add(name)
            val = values.get(name, str(lp[2]))
            lat = find(lp, "at")
            eff = find(lp, "effects") or ["effects", ["font", ["size", "1.27", "1.27"]]]
            eff = [e for e in eff if not (isinstance(e, list) and e[0] == "hide")]
            hidden = name not in ("Reference", "Value") or (name == "Value" and hide_value) \
                or (name == "Reference" and ref.startswith("#"))
            if placed.get(name):
                px, py = placed[name][0], placed[name][1]
                just = placed[name][2] if len(placed[name]) > 2 else None
                eff = ["effects", ["font", ["size", "1.27", "1.27"]]] + ([["justify", just]] if just else [])
                at = ["at", fmt(px), fmt(py), str(ang)]
            else:
                dx, dy = xform(float(lat[1]), float(lat[2]), rot)
                at = ["at", fmt(x + dx), fmt(y + dy), str(ang if rot else int(float(lat[3])))]
            if hidden:
                eff = eff + [["hide", "yes"]]
            node.append(["property", Q(name), Q(val), at, eff])
        for name, val in values.items():
            if name not in seen:
                node.append(["property", Q(name), Q(val), ["at", fmt(x), fmt(y), "0"],
                             ["effects", ["font", ["size", "1.27", "1.27"]], ["hide", "yes"]]])
        for num in sorted({p[0] for p in part._pins}):
            node.append(["pin", Q(num), ["uuid", Q(self._uuid())]])
        node.append(["instances", ["project", Q(self.project),
                     ["path", Q(self._inst_path), ["reference", Q(ref)], ["unit", "1"]]]])
        self.items.append(node)
        for p in part._pins:
            self.pin_pts.append(part.pin(p[0]))
        return part

    def power(self, name, pt, rot=0, **kw):
        return self.sym(f"power:{name}", f"#PWR{self._next_pwr():03d}", name, pt[0], pt[1], rot, **kw)

    def flag(self, pt, rot=0):
        return self.sym("power:PWR_FLAG", f"#FLG{self._next_pwr():03d}", "PWR_FLAG", pt[0], pt[1], rot)

    # -- connectivity
    def wire(self, *pts):
        for a, b in zip(pts, pts[1:]):
            a = (round(a[0], 4), round(a[1], 4)); b = (round(b[0], 4), round(b[1], 4))
            if a == b:
                continue
            if a[0] != b[0] and a[1] != b[1]:
                raise ValueError(f"diagonal wire {a} -> {b}")
            self.wires.append((a, b))
            self.items.append(["wire", ["pts", ["xy", fmt(a[0]), fmt(a[1])], ["xy", fmt(b[0]), fmt(b[1])]],
                               ["stroke", ["width", "0"], ["type", "default"]], ["uuid", Q(self._uuid())]])

    def label(self, name, pt, rot=0):
        just = {0: ["left", "bottom"], 180: ["right", "bottom"], 90: ["left", "bottom"], 270: ["right", "bottom"]}[rot]
        self.items.append(["label", Q(name), ["at", fmt(pt[0]), fmt(pt[1]), str(rot)],
                           ["effects", ["font", ["size", "1.27", "1.27"]], ["justify"] + just],
                           ["uuid", Q(self._uuid())]])

    def glabel(self, name, pt, rot=0, shape="passive"):
        """Global label: joins every page of a `Design`; the net is called `name`.

        shape: input, output, bidirectional, tri_state or passive (outline only,
        ERC does not look at it).
        """
        if shape not in GLABEL_SHAPES:
            raise ValueError(f"glabel shape {shape!r}")
        just = {0: "left", 180: "right", 90: "left", 270: "right"}[rot]
        self.items.append(["global_label", Q(name), ["shape", shape], ["at", fmt(pt[0]), fmt(pt[1]), str(rot)],
                           ["effects", ["font", ["size", "1.27", "1.27"]], ["justify", just]],
                           ["uuid", Q(self._uuid())],
                           ["property", Q("Intersheetrefs"), Q("${INTERSHEET_REFS}"),
                            ["at", fmt(pt[0]), fmt(pt[1]), "0"],
                            ["effects", ["font", ["size", "1.27", "1.27"]], ["hide", "yes"]]]])

    def nc(self, pt):
        self.items.append(["no_connect", ["at", fmt(pt[0]), fmt(pt[1])], ["uuid", Q(self._uuid())]])

    def text(self, s, pt, size=1.27, bold=False):
        font = ["font", ["size", fmt(size), fmt(size)]] + ([["bold", "yes"]] if bold else [])
        s = s.replace("\r", "").replace("\n", "\\n")   # a raw newline breaks the labels after it (RUL-8)
        self.items.append(["text", Q(s), ["exclude_from_sim", "no"], ["at", fmt(pt[0]), fmt(pt[1]), "0"],
                           ["effects", font, ["justify", "left", "bottom"]], ["uuid", Q(self._uuid())]])

    def box(self, x1, y1, x2, y2):
        self.items.append(["rectangle", ["start", fmt(x1), fmt(y1)], ["end", fmt(x2), fmt(y2)],
                           ["stroke", ["width", "0"], ["type", "dash"]], ["fill", ["type", "none"]],
                           ["uuid", Q(self._uuid())]])

    def _junctions(self):
        ends = {}
        for a, b in self.wires:
            for p in (a, b):
                ends[p] = ends.get(p, 0) + 1
        for p in self.pin_pts:
            ends[p] = ends.get(p, 0) + 1
        out = set()
        for p, n in ends.items():
            if n >= 3:
                out.add(p)
            for a, b in self.wires:
                if p in (a, b):
                    continue
                if (a[0] == b[0] == p[0] and min(a[1], b[1]) < p[1] < max(a[1], b[1])) or \
                   (a[1] == b[1] == p[1] and min(a[0], b[0]) < p[0] < max(a[0], b[0])):
                    out.add(p)
        return sorted(out)

    def _doc(self, is_root=True):
        root = _header(self.root, self.paper, self.title, self.date, self.rev)
        root.append(["lib_symbols"] + list(self.libsyms.values()))
        for p in self._junctions():
            root.append(["junction", ["at", fmt(p[0]), fmt(p[1])], ["diameter", "0"],
                         ["color", "0", "0", "0", "0"], ["uuid", Q(self._uuid())]])
        root += self.items
        if is_root:
            root.append(["sheet_instances", ["path", Q("/"), ["page", Q("1")]]])
        root.append(["embedded_fonts", "no"])
        return root

    def save(self, path):
        _write(path, self._doc())


def _header(file_uuid, paper, title, date, rev):
    return ["kicad_sch", ["version", "20250114"], ["generator", Q("eeschema")],
            ["generator_version", Q("9.0")], ["uuid", Q(file_uuid)], ["paper", Q(paper)],
            ["title_block", ["title", Q(title)], ["date", Q(date)], ["rev", Q(rev)]]]


def _write(path, doc):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(dump(doc) + "\n")


# ---------------------------------------------------------------- multi-page
class Page(Sch):
    """One page of a `Design`; same drawing API as `Sch`. Made by Design.page()."""

    def __init__(self, design, name, title, paper):
        self.design, self.name = design, name
        Sch.__init__(self, design.project, title, paper, design.rev, design.date)
        self._n = 0
        self._ukey = f"{design.project}/page:{name}"
        self.root = self._uuid("root")
        self.sheet_uuid = self._uuid("sheet")          # the sheet symbol in the root file
        self._inst_path = f"/{design.root}/{self.sheet_uuid}"
        self.file = f"{design.project}_{name}.kicad_sch"

    def _next_pwr(self):
        return self.design._next_pwr()

    def save(self, path):
        raise RuntimeError("pages are written by Design.save()")


class Design:
    """A flat multi-page schematic.

        d = Design("board", "Board title", rev="A", date="2026-11-20")
        p = d.page("power", "Power input")      # same API as Sch
        ...
        d.save(project_dir)

    Writes `<project>.kicad_sch` (the root: one sheet symbol per page, nothing
    else) and `<project>_<page>.kicad_sch` for each page. Pages are numbered
    1..N in the order they were created; the root is page 0. Nets cross pages
    through `glabel` and power symbols only. `#PWR`/`#FLG` numbers are shared
    by all pages; a reference used twice is an error.
    """
    COLS, X0, Y0, DX, DY, W, H = 4, 25.4, 38.1, 63.5, 38.1, 50.8, 20.32   # sheet symbol grid, mm

    def __init__(self, project, title="", rev="A", date="", paper="A4"):
        self.project, self.title, self.rev, self.date, self.paper = project, title, rev, date, paper
        self.pages, self._pwr = [], 0
        self.root = str(uuid.uuid5(_NS, f"{project}/root/"))

    def _next_pwr(self):
        self._pwr += 1
        return self._pwr

    def page(self, name, title="", paper="A3"):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError(f"page name {name!r}: letters, digits, _ and - only (it becomes a file name "
                             f"and the prefix of the page's local net names)")
        if any(p.name.lower() == name.lower() for p in self.pages):
            raise ValueError(f"duplicate page name {name!r}")
        page = Page(self, name, title or name, paper)
        self.pages.append(page)
        return page

    @property
    def parts(self):
        return [part for page in self.pages for part in page.parts]

    def files(self):
        """File names written by save(): the root first, then the pages in order."""
        return [self.project + ".kicad_sch"] + [p.file for p in self.pages]

    def _check_refs(self):
        seen = {}
        for page in self.pages:
            for part in page.parts:
                if part.ref in seen:
                    raise ValueError(f"reference {part.ref} used on page {seen[part.ref]} and on page {page.name}")
                seen[part.ref] = page.name

    def _root_doc(self):
        def uid(tag):
            return str(uuid.uuid5(_NS, f"{self.project}/rootitem:{tag}/"))

        font = ["font", ["size", "1.27", "1.27"]]
        root = _header(self.root, self.paper, self.title, self.date, self.rev)
        root.append(["lib_symbols"])
        for k, page in enumerate(self.pages):
            x = self.X0 + (k % self.COLS) * self.DX
            y = self.Y0 + (k // self.COLS) * self.DY
            label = f"{k + 1}  {page.title}".replace("\r", "").replace("\n", " ")
            root.append(["text", Q(label), ["exclude_from_sim", "no"],
                         ["at", fmt(x + 2.54), fmt(y + self.H / 2 + 1.27), "0"],
                         ["effects", font, ["justify", "left", "bottom"]], ["uuid", Q(uid("text:" + page.name))]])
            root.append(["sheet", ["at", fmt(x), fmt(y)], ["size", fmt(self.W), fmt(self.H)],
                         ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"], ["dnp", "no"],
                         ["stroke", ["width", "0.1524"], ["type", "solid"]],
                         ["fill", ["color", "0", "0", "0", "0.0000"]],
                         ["uuid", Q(page.sheet_uuid)],
                         ["property", Q("Sheetname"), Q(page.name), ["at", fmt(x), fmt(y - 0.7116), "0"],
                          ["effects", font, ["justify", "left", "bottom"]]],
                         ["property", Q("Sheetfile"), Q(page.file), ["at", fmt(x), fmt(y + self.H + 0.5846), "0"],
                          ["effects", font, ["justify", "left", "top"]]],
                         ["instances", ["project", Q(self.project),
                                        ["path", Q("/" + self.root), ["page", Q(str(k + 1))]]]]])
        root.append(["sheet_instances", ["path", Q("/"), ["page", Q("0")]]])
        root.append(["embedded_fonts", "no"])
        return root

    def save(self, directory):
        """Write the root and every page into `directory`; returns the root path."""
        if not self.pages:
            raise ValueError("design has no pages")
        self._check_refs()
        _write(os.path.join(directory, self.project + ".kicad_sch"), self._root_doc())
        for page in self.pages:
            _write(os.path.join(directory, page.file), page._doc(is_root=False))
        return os.path.join(directory, self.project + ".kicad_sch")


if __name__ == "__main__":
    import sys
    for lib_id in sys.argv[1:]:
        print(lib_id)
        for num, name, x, y, typ in sorted(symbol_pins(load_symbol(lib_id)), key=lambda p: (p[2], -p[3])):
            print(f"  {num:>4} {name:<28} ({x:g}, {y:g}) {typ}")
