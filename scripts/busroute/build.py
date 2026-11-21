"""Build one routing group from its routes file.

    D:\\KiCad\\bin\\python.exe scripts\\busroute\\build.py <routes.py> [--fast] [--sketch] [--out DIR]
                                                         [--write-board] [--no-refill] [--no-pictures]

    --fast          geometry only: resolve the description, check it (crossings, gaps, holes, paths, via
                    count, lengths by geometry) and print the table. No file is written, kicad-cli is not run.
    (full build)    writes the board, runs DRC, measures the lengths with DRC, runs track_shape.py and the
                    rule canary, writes metrics.json, metrics.txt, drc_summary.json and the pictures.
    --sketch        line-order sketch (RTE-13): shape findings are listed but do not fail the build;
                    crossings and gaps still do. Same as SKETCH = True in the routes file.
    --out DIR       where a full build writes. Default: <board folder>/out/busroute/<GROUP>/.
    --write-board   write the tracks into the board file itself (PROC-13: only when the file is script-owned;
                    refused while KiCad has the project open). WITHOUT this flag the real board is never
                    touched: the build works on a copy of the .kicad_pcb / .kicad_pro / .kicad_dru in --out.
    --no-refill     do not refill the pours for the DRC run (quick build of one group, PROC-6)
    --no-pictures   skip the PNGs

Exit code 0 = passed, 1 = findings, 2 = the description could not be built. See job.py for the routes file,
routes.py for the route format, bundle.py and fanout.py for the generators.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.normcase(os.path.abspath(sys.path[0])) == os.path.normcase(HERE):
    sys.path.pop(0)                                         # the package's modules are not top-level modules
sys.path.insert(0, os.path.dirname(HERE))


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    flags = [a for a in argv if a.startswith("--")]
    out = None
    if "--out" in argv:
        k = argv.index("--out")
        out = argv[k + 1]
        args.remove(out)
    known = {"--fast", "--sketch", "--out", "--write-board", "--no-refill", "--no-pictures"}
    if len(args) != 1 or set(flags) - known:
        print(__doc__)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from busroute import job
    _, code = job.run(args[0], fast="--fast" in flags, sketch="--sketch" in flags, out=out, write_board="--write-board" in flags,
                      refill="--no-refill" not in flags, pictures="--no-pictures" not in flags)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
