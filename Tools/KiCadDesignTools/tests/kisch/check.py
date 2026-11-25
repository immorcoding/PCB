"""Regression benchmark for schematic/kisch.py (multi-page schematic generator).

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.tests.kisch.check [--keep]

Builds a 3-page flat design from stock-library parts in a temp directory,
upgrades it with kicad-cli, runs ERC and exports the netlist, then compares
the full net -> (ref, pin) map and the ERC violation count with the expected
values below. Prints one line, `OK ...` or `FAIL ...` (details follow a FAIL);
exit code 0 = pass. Nothing is written into the repository. `--keep` leaves
the temp directory in place (it is also kept after a FAIL).
"""
import json, os, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
from Tools.KiCadDesignTools.core import heavy
from Tools.KiCadDesignTools.schematic import kisch
from Tools.KiCadDesignTools.schematic.kisch import Design, Sch

PROJECT = "bench"
U = 2.54
FP_R = "Resistor_SMD:R_0603_1608Metric"


def P(i, j):
    return (round(i * U, 4), round(j * U, 4))


# ------------------------------------------------------------------ expected
# Net name -> pins, exactly as kicad-cli 10.0.8 exports them.
#   power symbol            -> the symbol's value            (+5V, GND)
#   global label            -> the bare label text           (SIG_A, SIG_B)
#   local label on a page   -> /<page name>/<label>          (/power/MID, /io/MID)
#   no name, several pins   -> Net-(<ref>-<pin name or PadN>)
#   no name, one pin (NC)   -> unconnected-(<ref>-<pin name>-Pad<N>)
EXPECTED_NETS = {
    "+5V": {("J1", "1"), ("R1", "1"), ("R5", "1"), ("R6", "2")},
    "GND": {("J1", "2"), ("R2", "2"), ("R4", "2"), ("J2", "2"), ("R7", "2")},
    "SIG_A": {("J1", "3"), ("R3", "1")},
    "SIG_B": {("R5", "2"), ("J2", "1")},
    "/power/MID": {("R1", "2"), ("R2", "1")},
    "/io/MID": {("R3", "2"), ("R4", "1")},
    "Net-(R6-Pad1)": {("R6", "1"), ("R7", "1")},
    "unconnected-(J1-Pin_4-Pad4)": {("J1", "4")},
    "unconnected-(J2-Pin_3-Pad3)": {("J2", "3")},
}
EXPECTED_ERC = 0
EXPECTED_SHEETS = {"/", "/power/", "/io/", "/mem/"}                  # sheet paths in the netlist
EXPECTED_PAGES = {"power": "1", "io": "2", "mem": "3"}                # page numbers in the root file
EXPECTED_R5 = {"footprint": FP_R, "value": "4k7", "MPN": "RC0603FR-074K7L"}


# --------------------------------------------------------------------- build
def build():
    d = Design(PROJECT, "kisch benchmark", rev="A", date="2026-11-20")

    def R(page, ref, val, i, j, **kw):
        x, y = P(i, j)
        return page.sym("Device:R", ref, val, x, y, 0, FP_R,
                        ref_at=(x + U, y - 0.5 * U, "left"), val_at=(x + U, y + 0.5 * U, "left"), **kw)

    def stub(page, pt, direction, n=2):
        end = (round(pt[0] + (-n if direction == "L" else n) * U, 4), pt[1])
        page.wire(pt, end)
        return end

    # ---- page 1: connector, both power nets and their PWR_FLAGs, a divider
    p = d.page("power", "Power input")
    p.text("Power input\nsecond line (newline must not break the page)", P(8, 10), size=1.8, bold=True)
    p.box(*P(6, 12), *P(60, 40))
    J1 = p.sym("Connector_Generic:Conn_01x04", "J1", "IN", *P(30, 20), 0,
               "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical")
    p.power("+5V", stub(p, J1.pin("1"), "L"), 90)
    p.power("GND", stub(p, J1.pin("2"), "L"), 270)
    p.glabel("SIG_A", stub(p, J1.pin("3"), "L"), 180, shape="output")
    p.nc(J1.pin("4"))
    R1 = R(p, "R1", "10k", 40, 20)
    R2 = R(p, "R2", "10k", 40, 30)
    p.power("+5V", R1.pin("1"))
    p.label("MID", stub(p, R1.pin("2"), "R"))            # joined to R2 by name, same page
    p.label("MID", stub(p, R2.pin("1"), "R"))
    p.power("GND", R2.pin("2"))
    for k, net in enumerate(["+5V", "GND"]):
        i = 50 + 5 * k
        p.power(net, P(i, 20), 0 if net == "+5V" else 180)
        p.wire(P(i, 20), P(i, 22))
        p.flag(P(i, 22), 180)

    # ---- page 2: the other end of SIG_A, a second, separate "MID", custom field
    p = d.page("io", "IO")
    R3 = R(p, "R3", "1k", 20, 20)
    R4 = R(p, "R4", "1k", 30, 20)
    p.glabel("SIG_A", stub(p, R3.pin("1"), "L"), 180, shape="input")
    p.wire(R3.pin("2"), P(20, 23), P(30, 23))
    p.label("MID", P(22, 23))
    p.wire(R4.pin("1"), P(30, 17), P(35, 17), P(35, 23), P(30, 23))
    p.power("GND", R4.pin("2"))
    R5 = R(p, "R5", "4k7", 45, 20, fields={"MPN": "RC0603FR-074K7L"})
    p.power("+5V", R5.pin("1"))
    p.glabel("SIG_B", stub(p, R5.pin("2"), "R"), 0)

    # ---- page 3: the other end of SIG_B, an unnamed net, a no-connect
    p = d.page("mem", "Memory", paper="A4")
    J2 = p.sym("Connector_Generic:Conn_01x03", "J2", "OUT", *P(30, 20), 0,
               "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical")
    p.glabel("SIG_B", stub(p, J2.pin("1"), "L"), 180, shape="bidirectional")
    p.power("GND", stub(p, J2.pin("2"), "L"), 270)
    p.nc(J2.pin("3"))
    R6 = R(p, "R6", "100R", 45, 20)
    R7 = R(p, "R7", "100R", 55, 20)
    p.power("+5V", R6.pin("2"), 180)
    p.power("GND", R7.pin("2"))
    p.wire(R6.pin("1"), P(45, 17), P(55, 17), R7.pin("1"))
    return d


def generate(directory):
    d = build()
    d.save(directory)
    return d


# --------------------------------------------------------------------- tools
def cli(*args):
    r = heavy.kicad_cli(*args, check=False, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"kicad-cli {' '.join(args)}\n{r.stdout}{r.stderr}")
    return r.stdout


def read_netlist(path):
    """-> ({net: {(ref, pin)}}, {ref: {footprint, value, fields...}}, {sheet path})"""
    with open(path, encoding="utf-8") as f:
        root = kisch.parse(f.read())
    nets = {}
    for net in kisch.find_all(kisch.find(root, "nets"), "net"):
        nodes = {(str(kisch.find(n, "ref")[1]), str(kisch.find(n, "pin")[1])) for n in kisch.find_all(net, "node")}
        nets[str(kisch.find(net, "name")[1])] = nodes
    comps = {}
    for c in kisch.find_all(kisch.find(root, "components"), "comp"):
        info = {"value": str(kisch.find(c, "value")[1]), "footprint": str((kisch.find(c, "footprint") or [0, ""])[1])}
        for fld in kisch.find_all(kisch.find(c, "fields") or [], "field"):
            info[str(kisch.find(fld, "name")[1])] = str(fld[2]) if len(fld) > 2 else ""
        comps[str(kisch.find(c, "ref")[1])] = info
    sheets = {str(kisch.find(s, "name")[1]) for s in kisch.find_all(kisch.find(root, "design"), "sheet")}
    return nets, comps, sheets


def erc_violations(root_sch, out):
    cli("sch", "erc", "--severity-all", "--format", "json", "-o", out, root_sch)
    with open(out, encoding="utf-8") as f:
        rep = json.load(f)
    found = []
    for sheet in rep.get("sheets", []):
        for v in sheet.get("violations", []):
            where = ", ".join(i.get("description", "") for i in v.get("items", []))
            found.append(f"{sheet.get('path')}: [{v.get('severity')}] {v.get('type')}: {v.get('description')} ({where})")
    return found


def root_pages(root_sch):
    """{sheet name: (page number, project name)} from the sheet symbols of a root file."""
    with open(root_sch, encoding="utf-8") as f:
        root = kisch.parse(f.read())
    pages = {}
    for sh in kisch.find_all(root, "sheet"):
        name = next(str(p[2]) for p in kisch.find_all(sh, "property") if p[1] == "Sheetname")
        proj = kisch.find(kisch.find(sh, "instances"), "project")
        pages[name] = (str(kisch.find(kisch.find(proj, "path"), "page")[1]), str(proj[1]))
    return pages


def read(path):
    with open(path, "rb") as f:
        return f.read()


# ---------------------------------------------------------------------- main
def run(tmp):
    fails = []
    a, b, c = (os.path.join(tmp, n) for n in ("a", "b", "c"))
    for x in (a, b, c):
        os.makedirs(x)

    # 1. generation: file layout, determinism (same process and a fresh process
    #    with another hash seed)
    d = generate(a)
    files = d.files()
    want_files = [PROJECT + ".kicad_sch"] + [f"{PROJECT}_{n}.kicad_sch" for n in ("power", "io", "mem")]
    if files != want_files or sorted(os.listdir(a)) != sorted(want_files):
        fails.append(f"files written: {sorted(os.listdir(a))}, expected {want_files}")
    generate(b)
    r = heavy.kicad_py("Tools.KiCadDesignTools.tests.kisch.check", "--generate", c, env={"PYTHONHASHSEED": "12345"}, text=True)
    if r.returncode != 0:
        fails.append("generation in a fresh process failed:\n" + r.stdout + r.stderr)
    for other in (b, c):
        for f in want_files:
            if not os.path.exists(os.path.join(other, f)) or read(os.path.join(a, f)) != read(os.path.join(other, f)):
                fails.append(f"not deterministic: {f} differs between {a} and {other}")
    for f in want_files:
        if b"\n\n" in read(os.path.join(a, f)) or b"\r" in read(os.path.join(a, f)):
            fails.append(f"{f}: raw line break inside the file body")

    # 2. the API guards
    for what, fn in (("duplicate reference", _dup_ref), ("duplicate page", _dup_page), ("bad page name", _bad_page)):
        try:
            fn()
            fails.append(f"{what}: no error raised")
        except ValueError:
            pass

    # 3. KiCad: upgrade every file, ERC and netlist from the root
    #    (`sch upgrade` on the root leaves the page files in the old format)
    root = os.path.join(a, PROJECT + ".kicad_sch")
    with open(os.path.join(a, PROJECT + ".kicad_pro"), "w") as f:
        f.write("{}")                      # a project file, so KiCad knows the project name
    for f in want_files:
        cli("sch", "upgrade", os.path.join(a, f))
    pages = root_pages(root)
    if pages != {n: (num, PROJECT) for n, num in EXPECTED_PAGES.items()}:
        fails.append(f"root sheet symbols (name -> page, project): {pages}, expected pages {EXPECTED_PAGES}")
    for f in want_files:
        if b"(generator_version \"9.0\")" in read(os.path.join(a, f)):
            fails.append(f"{f}: still in the KiCad 9 format after sch upgrade")
    erc = erc_violations(root, os.path.join(tmp, "erc.json"))
    if len(erc) != EXPECTED_ERC:
        fails.append(f"ERC: {len(erc)} violations, expected {EXPECTED_ERC}\n    " + "\n    ".join(erc))
    net_path = os.path.join(tmp, PROJECT + ".net")
    cli("sch", "export", "netlist", "--format", "kicadsexpr", "-o", net_path, root)
    nets, comps, sheets = read_netlist(net_path)
    for name in sorted(set(nets) | set(EXPECTED_NETS)):
        got, want = nets.get(name), EXPECTED_NETS.get(name)
        if got != want:
            fails.append(f"net {name!r}: got {sorted(got) if got is not None else 'missing'}, "
                         f"expected {sorted(want) if want is not None else 'no such net'}")
    want_refs = {ref for pins in EXPECTED_NETS.values() for ref, _ in pins}
    if set(comps) != want_refs:
        fails.append(f"components: got {sorted(comps)}, expected {sorted(want_refs)}")
    for key, want in EXPECTED_R5.items():
        if comps.get("R5", {}).get(key) != want:
            fails.append(f"R5 {key}: got {comps.get('R5', {}).get(key)!r}, expected {want!r}")
    if sheets != EXPECTED_SHEETS:
        fails.append(f"netlist sheets: got {sorted(sheets)}, expected {sorted(EXPECTED_SHEETS)}")

    # 4. the single-sheet API still produces a loadable schematic with the same nets
    single = os.path.join(tmp, "single")
    os.makedirs(single)
    s = Sch("single", "single sheet")
    r1 = s.sym("Device:R", "R1", "1k", *P(20, 20), 0, FP_R)
    r2 = s.sym("Device:R", "R2", "1k", *P(30, 20), 0, FP_R)
    s.power("+5V", r1.pin("1")); s.power("GND", r2.pin("2"))
    s.wire(r1.pin("2"), P(20, 23), P(25, 23)); s.label("MID", P(25, 23))
    s.wire(r2.pin("1"), P(30, 17), P(35, 17)); s.label("MID", P(35, 17))
    s.power("+5V", P(40, 20)); s.wire(P(40, 20), P(40, 22)); s.flag(P(40, 22), 180)
    s.power("GND", P(45, 20), 180); s.wire(P(45, 20), P(45, 22)); s.flag(P(45, 22), 180)
    sp = os.path.join(single, "single.kicad_sch")
    s.save(sp)
    cli("sch", "upgrade", sp)
    erc1 = erc_violations(sp, os.path.join(tmp, "erc_single.json"))
    if erc1:
        fails.append("single sheet ERC:\n    " + "\n    ".join(erc1))
    cli("sch", "export", "netlist", "--format", "kicadsexpr", "-o", os.path.join(tmp, "single.net"), sp)
    nets1 = read_netlist(os.path.join(tmp, "single.net"))[0]
    want1 = {"+5V": {("R1", "1")}, "GND": {("R2", "2")}, "/MID": {("R1", "2"), ("R2", "1")}}
    if nets1 != want1:
        fails.append(f"single sheet nets: got {nets1}, expected {want1}")

    return fails, len(nets), len(comps), len(erc)


def _dup_ref():
    d = Design("x")
    d.page("a").sym("Device:R", "R1", "1k", *P(10, 10))
    d.page("b").sym("Device:R", "R1", "1k", *P(10, 10))
    d._check_refs()


def _dup_page():
    d = Design("x")
    d.page("a"); d.page("A")


def _bad_page():
    Design("x").page("a b")


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--generate":
        generate(sys.argv[2])
        return 0
    keep = "--keep" in sys.argv[1:]
    tmp = tempfile.mkdtemp(prefix="kisch_check_")
    try:
        fails, n_nets, n_comps, n_erc = run(tmp)
    except Exception as e:                                   # tool failure counts as a failure
        fails, n_nets, n_comps, n_erc = [f"{type(e).__name__}: {e}"], 0, 0, 0
    if fails:
        print(f"FAIL kisch: {len(fails)} problem(s); files kept in {tmp}")
        for f in fails:
            print("  - " + f)
        return 1
    print(f"OK kisch: 3 pages, {n_comps} parts, {n_nets} nets match, ERC {n_erc} violations, "
          f"output deterministic, single-sheet API intact")
    if keep:
        print("kept " + tmp)
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
