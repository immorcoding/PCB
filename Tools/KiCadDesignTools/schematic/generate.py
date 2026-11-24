"""Generate a board's multi-page schematic (flat) from its page modules.

    python -m Tools.KiCadDesignTools.schematic.generate <board dir> [page ...] [--out DIR]
    python -m Tools.KiCadDesignTools.schematic.build <board dir> <out>       (generate, upgrade, ERC, netlist, PDF)

Writes <name>.kicad_sch (root, one sheet symbol per page) and one file per page, the project symbol library
<lib>.kicad_sym and sym-lib-table, into the board folder; with pages named and --out DIR, a scratch build of those
pages away from the project files. The pages are board.toml [schematic] pages in order, each a module
<board dir>/sch/<page>.py with build(sh); the drawing helpers and conventions are in
Tools.KiCadDesignTools.schematic.sheet. Nets cross pages through global labels and power symbols; a net has the same
bare name everywhere.

Once the schematic is edited by hand in KiCad the files are the truth: ask before running this again (PROC-13).
"""
import os, sys

from Tools.KiCadDesignTools.core import config
from Tools.KiCadDesignTools.schematic import kisch, sheet


def pages(cfg):
    """[(module, page number = hundreds digit of its references, title)] in [schematic] pages order."""
    return [(p["name"], p["number"], p["title"]) for p in cfg.need("schematic.pages")]


def main(cfg, only=None, out=None):
    """Draw the pages (only: those names) and write the files into `out` (default the board folder) -> the Sheets."""
    out = out or cfg.dir
    sheet.configure(cfg)
    lib = sheet.LIB
    d = kisch.Design(cfg.name, cfg.get("schematic.title") or cfg.need("board.title"), rev=cfg.need("board.rev"),
                     date=cfg.need("schematic.date"))
    sheets, missing = [], []
    for mod, num, title in pages(cfg):
        if only and mod not in only:
            continue
        try:
            m = cfg.module("sch." + mod)
        except ModuleNotFoundError as e:
            if e.name != cfg.package + ".sch." + mod:
                raise
            missing.append(mod)
            continue
        sh = sheet.Sheet(d.page(mod, title), num)
        m.build(sh)
        sheets.append(sh)
    os.makedirs(out, exist_ok=True)
    kisch.write_library(os.path.join(out, lib + ".kicad_sym"), [sheet.SYMBOLS[k] for k in sorted(sheet.SYMBOLS)])
    open(os.path.join(out, "sym-lib-table"), "w", encoding="utf-8", newline="\n").write(
        '(sym_lib_table\n\t(version 7)\n\t(lib (name "%s") (type "KiCad") (uri "${KIPRJMOD}/%s.kicad_sym") (options "") (descr "Project symbols"))\n)\n'
        % (lib, lib))
    d.save(out)
    print("%d pages, %d parts, %d project symbols%s" % (len(sheets), len(d.parts), len(sheet.SYMBOLS),
                                                        "; pages not written yet: " + ", ".join(missing) if missing else ""))
    return sheets


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    o = None
    if "--out" in a:                       # a scratch build of some pages, away from the project files
        k = a.index("--out"); o = os.path.abspath(a[k + 1]); a = a[:k] + a[k + 2:]
    main(config.load(a[0]), a[1:] or None, o)
