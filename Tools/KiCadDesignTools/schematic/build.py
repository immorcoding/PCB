"""Build a generated schematic: generate, upgrade to the installed KiCad, ERC, netlist, PDF.

    python -m Tools.KiCadDesignTools.schematic.build <board dir> <out dir>
    python -m Tools.KiCadDesignTools.schematic.build <board dir> <out dir> --page NAME [--page NAME ...]

A board folder with board.toml is drawn by Tools.KiCadDesignTools.schematic.generate (its [schematic] pages); a folder
without one (stm32f411_minsys, steval_fcu001v2) runs its own gen_sch.py as a module of the repository
(`python -m <board>.gen_sch`), which writes into the board folder. Works for a single sheet (kisch.Sch) and for a
multi-page design (kisch.Design: root <name>.kicad_sch plus one <name>_<page>.kicad_sch per page): `sch upgrade`
converts only the file it is given, so the root and every page named by the root's sheet symbols are upgraded. ERC,
netlist and PDF are taken from the root and cover every page: <out>/erc.rpt, <out>/<name>.net, <out>/<name>.pdf.
Prints the generator's line, a warning for each page file the root no longer points to, and the ERC summary lines.

--page: those pages alone, generated into <out dir> together with copies of the project file, fp-lib-table and
<lib>.pretty; nothing in the board folder is written. Prints the ERC messages counted by type; ERC errors about pins
driven from other pages are expected.

Runs below normal priority on four cores (core.heavy.low_priority); kicad-cli and KiCad's python through core.heavy.run.
"""
import collections, glob, os, re, shutil, sys

from Tools.KiCadDesignTools.core import config, heavy, paths
from Tools.KiCadDesignTools.schematic import generate


def _run(argv, stdout=None, cwd=None):
    """A child process (core.heavy.run: below normal, four cores, the heavy lock); its output passes unless `stdout`
    says otherwise, a failure stops the build (as `set -e` did)."""
    r = heavy.run(argv, stdout=stdout, stderr=None, cwd=cwd)
    if r.returncode:
        raise SystemExit(r.returncode)


def echo(lines):
    for l in lines:
        print(l)


def cli(*args):
    """kicad-cli with its standard output dropped."""
    _run([paths.KICAD_CLI] + list(args), stdout=heavy.DEVNULL)


def board_dir(path):
    if not os.path.isabs(path) and not os.path.exists(path):
        path = os.path.join(paths.REPO, path)
    return os.path.abspath(path)


def sheet_files(root):
    """The page files the root's sheet symbols point to, in file order (none for a single sheet)."""
    out = []
    with open(root, encoding="utf-8") as f:
        for line in f:
            m = re.findall(r'\(property "Sheetfile" "([^"]*)"', line)
            if m:
                out.append(m[-1])
    return out


def build(board, out, pages=()):
    D = board_dir(board)
    O = os.path.abspath(out)
    os.makedirs(O, exist_ok=True)
    if os.path.isfile(os.path.join(D, "board.toml")):
        cfg = config.load(D)
        N = cfg.name
        if pages:                                      # a scratch build of some pages in <out dir>
            shutil.copyfile(cfg.pro, os.path.join(O, os.path.basename(cfg.pro)))
            if os.path.isfile(os.path.join(D, "fp-lib-table")):
                shutil.copyfile(os.path.join(D, "fp-lib-table"), os.path.join(O, "fp-lib-table"))
            pretty = cfg.need("board.lib") + ".pretty"
            if os.path.isdir(os.path.join(D, pretty)):
                shutil.copytree(os.path.join(D, pretty), os.path.join(O, pretty), dirs_exist_ok=True)
            generate.main(cfg, list(pages), O)
            D = O
        else:
            generate.main(cfg)
    else:
        if pages:
            raise SystemExit("--page needs a board.toml with [schematic] pages in %s" % D)
        N = os.path.basename(D)
        rel = os.path.relpath(D, paths.REPO)
        if rel.startswith(".."):
            raise SystemExit("%s is not inside the repository %s" % (D, paths.REPO))
        _run([paths.KICAD_PY, "-m", rel.replace(os.sep, ".").replace("/", ".") + ".gen_sch"], cwd=paths.REPO)
    root = os.path.join(D, N + ".kicad_sch")
    cli("sch", "upgrade", root)
    files = sheet_files(root)
    for p in files:
        cli("sch", "upgrade", os.path.join(D, p))
    # a page file the root no longer points to is a leftover from a renamed or removed page
    if files:
        for f in sorted(glob.glob(os.path.join(D, glob.escape(N) + "_*.kicad_sch"))):
            if os.path.basename(f) not in files:
                print("WARNING: %s is not a page of %s.kicad_sch (stale?)" % (f, N))
    rpt = os.path.join(O, "erc.rpt")
    cli("sch", "erc", "--severity-all", "-o", rpt, root)
    lines = open(rpt, encoding="utf-8", errors="replace").read().splitlines()
    if pages:                                          # the summary line, then the messages counted by type
        echo(l for l in lines if "ERC messages" in l)
        echo("%7d %s" % (n, l) for l, n in sorted(collections.Counter(l for l in lines if l.startswith("[")).items()))
    else:
        rx = re.compile(r"ERC messages|^\[|; (error|warning)")
        echo(l for l in lines if rx.search(l))
    net, pdf = os.path.join(O, N + ".net"), os.path.join(O, N + ".pdf")
    cli("sch", "export", "netlist", "--format", "kicadsexpr", "-o", net, root)
    cli("sch", "export", "pdf", "-o", pdf, root)
    if pages:
        print("netlist: %s   pdf: %s (page 1 is the root)" % (net, pdf))
    return 0


def main(argv):
    pages = []
    while "--page" in argv:
        k = argv.index("--page")
        pages.append(argv[k + 1])
        argv = argv[:k] + argv[k + 2:]
    if len(argv) != 2:
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8")
    heavy.low_priority()
    return build(argv[0], argv[1], pages)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
