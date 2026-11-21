"""Generate the schematic of the STM32H743 + SDRAM board (multi-page, flat).

    sh stm32h743_sdram/build.sh sch                      (generate, upgrade, ERC, netlist, PDF, checks)
    sh stm32h743_sdram/sch/try_page.sh <out dir> <page>  (one page alone, in a scratch folder)

Writes stm32h743_sdram.kicad_sch (root, one sheet symbol per page) and one file per page, the project
symbol library h743.kicad_sym and sym-lib-table. One module per page in sch/; shared helpers and the
drawing conventions are in sch/common.py. Nets cross pages through global labels and power symbols;
a net has the same bare name everywhere.

Once the schematic is edited by hand in KiCad the files are the truth: ask before running this again (PROC-13).
"""
import importlib, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import kisch
from sch import common

NAME = "stm32h743_sdram"
# (module, page number = hundreds digit of its references, title)
PAGES = [("power", 1, "Power: input, 5 V, 3.3 V, LDOs"),
         ("mcu", 2, "MCU STM32H743IIK6"),
         ("sdram", 3, "SDRAM 8M x 32"),
         ("qspi", 4, "QSPI flash"),
         ("eth", 5, "Ethernet PHY and RJ45"),
         ("audio", 6, "Audio codec and jacks"),
         ("lcd", 7, "LCD connector, touch, backlight"),
         ("io", 8, "microSD, CAN, debug, misc")]


def main(only=None, out=HERE):
    d = kisch.Design(NAME, "STM32H743 + SDRAM six-layer test board", rev="A", date="2026-11-20")
    sheets, missing = [], []
    for mod, num, title in PAGES:
        if only and mod not in only:
            continue
        try:
            m = importlib.import_module("sch." + mod)
        except ModuleNotFoundError as e:
            if e.name != "sch." + mod:
                raise
            missing.append(mod)
            continue
        sh = common.Sheet(d.page(mod, title), num)
        m.build(sh)
        sheets.append(sh)
    os.makedirs(out, exist_ok=True)
    kisch.write_library(os.path.join(out, "h743.kicad_sym"), [common.SYMBOLS[k] for k in sorted(common.SYMBOLS)])
    open(os.path.join(out, "sym-lib-table"), "w", encoding="utf-8", newline="\n").write(
        '(sym_lib_table\n\t(version 7)\n\t(lib (name "h743") (type "KiCad") (uri "${KIPRJMOD}/h743.kicad_sym") (options "") (descr "Project symbols"))\n)\n')
    d.save(out)
    print("%d pages, %d parts, %d project symbols%s" % (len(sheets), len(d.parts), len(common.SYMBOLS),
                                                        "; pages not written yet: " + ", ".join(missing) if missing else ""))
    return sheets


if __name__ == "__main__":
    a = sys.argv[1:]
    o = HERE
    if "--out" in a:                       # a scratch build of some pages, away from the project files
        k = a.index("--out"); o = os.path.abspath(a[k + 1]); a = a[:k] + a[k + 2:]
    main(a or None, o)
