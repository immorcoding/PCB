"""Enable teardrops on every pad and via of a board, then let KiCad build them.

    D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.finishing.teardrops <board.kicad_pcb>

pcbnew's Python API does not expose teardrop settings, so the `(teardrops ...)`
block is written into the file directly; `kicad-cli pcb drc --refill-zones
--save-board` then generates the teardrop areas (they are stored as zones).
Run it last, after routing and pours are final. Prints how many teardrop zones
the saved board holds.
"""
import os, subprocess, sys
from Tools.KiCadDesignTools.schematic.kisch import parse, dump, find, Q

KICAD_CLI = r"D:\KiCad\bin\kicad-cli.exe"
TD = ["teardrops", ["best_length_ratio", "0.5"], ["max_length", "1"], ["best_width_ratio", "1"],
      ["max_width", "2"], ["curved_edges", "no"], ["filter_ratio", "0.9"], ["enabled", "yes"],
      ["allow_two_segments", "yes"], ["prefer_zone_connections", "yes"]]


def enable(node):
    n = 0
    for c in node:
        if not isinstance(c, list) or not c:
            continue
        if c[0] in ("pad", "via"):
            old = find(c, "teardrops")
            if old is not None:
                c.remove(old)
            at = next(i for i, x in enumerate(c) if isinstance(x, list) and x and x[0] in ("net", "uuid", "pinfunction", "pintype"))
            c.insert(at, list(TD))
            n += 1
        elif c[0] == "footprint":
            n += enable(c)
    return n


def main(path):
    tree = parse(open(path, encoding="utf-8").read())
    n = enable(tree)
    open(path, "w", encoding="utf-8", newline="\n").write(dump(tree) + "\n")
    subprocess.run([KICAD_CLI, "pcb", "drc", "--refill-zones", "--save-board", "--severity-all",
                    "-o", os.devnull, path], capture_output=True)
    text = open(path, encoding="utf-8").read()
    print(f"teardrops enabled on {n} pads/vias; teardrop zones in the saved board: {text.count('(teardrop')  - n}")


if __name__ == "__main__":
    main(sys.argv[1])
