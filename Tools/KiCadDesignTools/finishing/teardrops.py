r"""Enable teardrops on every pad and via of a board, then let KiCad build them.

    D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.finishing.teardrops <board.kicad_pcb>
    D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.finishing.teardrops <board dir> <board.kicad_pcb>

pcbnew's Python API does not expose teardrop settings, so the `(teardrops ...)`
block is written into the file directly; `kicad-cli pcb drc --refill-zones
--save-board` then generates the teardrop areas (they are stored as zones).
Run it last, after routing and pours are final. Prints how many teardrop zones
the saved board holds.

With the board folder first (the finish step of a board with board.toml, also
`finishing.finish <board dir> teardrops <board>`): the same, but not inside the
boxes of [finish.teardrops] skip_boxes (local mm x0 y0 x1 y1; on the H743 the
two BGA rule areas, where the 0.09 mm tracks run between 0.30 mm vias and balls
at the area's 0.09 mm clearance and a teardrop would widen the track into that
gap). Vias inside a box, the pads of footprints whose position is inside one
(the BGAs and the parts under them) and the pads of footprints with their own
keep-outs get the setting off.
"""
import os, subprocess, sys
from Tools.KiCadDesignTools.core import paths
from Tools.KiCadDesignTools.schematic.kisch import parse, dump, find, Q

KICAD_CLI = paths.KICAD_CLI
TD = ["teardrops", ["best_length_ratio", "0.5"], ["max_length", "1"], ["best_width_ratio", "1"],
      ["max_width", "2"], ["curved_edges", "no"], ["filter_ratio", "0.9"], ["enabled", "yes"],
      ["allow_two_segments", "yes"], ["prefer_zone_connections", "yes"]]
OFF = [x if x[0] != "enabled" else ["enabled", "no"] for x in TD]


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


# ---------------------------------------------------------------------------------------------------- with skip boxes
def put(node, on):
    old = find(node, "teardrops")
    if old is not None:
        node.remove(old)
    at = next(i for i, x in enumerate(node) if isinstance(x, list) and x and x[0] in ("net", "uuid", "pinfunction", "pintype"))
    node.insert(at, list(TD if on else OFF))


def board_teardrops(cfg, path):
    """Teardrops on every pad and via outside the boxes of [finish.teardrops] skip_boxes (board-file mm = local +
    origin) and outside footprints with their own keep-outs; off on the rest."""
    OX, OY = cfg.origin
    areas = [(x0 + OX, y0 + OY, x1 + OX, y1 + OY) for x0, y0, x1, y1 in cfg.need("finish.teardrops.skip_boxes")]

    def inside(x, y):
        return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in areas)
    tree = parse(open(path, encoding="utf-8").read())
    n_on = n_off = 0
    for c in tree:
        if not isinstance(c, list) or not c:
            continue
        if c[0] == "via":
            at = find(c, "at")
            on = not inside(float(at[1]), float(at[2]))
            put(c, on)
            n_on, n_off = n_on + on, n_off + (not on)
        elif c[0] == "footprint":
            at = find(c, "at")
            # off in a footprint that carries its own keep-outs (the H743's J501 shield contact areas, J801's): a
            # teardrop is copper the keep-out forbids (DRC items_not_allowed on the RJ45 shield pads)
            own_ko = any(isinstance(z, list) and z and z[0] == "zone" for z in c)
            on = not inside(float(at[1]), float(at[2])) and not own_ko
            for p in c:
                if isinstance(p, list) and p and p[0] == "pad":
                    put(p, on)
                    n_on, n_off = n_on + on, n_off + (not on)
    open(path, "w", encoding="utf-8", newline="\n").write(dump(tree) + "\n")
    subprocess.run([KICAD_CLI, "pcb", "drc", "--refill-zones", "--save-board", "--severity-all", "-o", os.devnull, path],
                   capture_output=True)
    text = open(path, encoding="utf-8").read()
    print("teardrops: enabled on %d pads / vias, off on %d (BGA areas); teardrop areas in the saved board: %d"
          % (n_on, n_off, text.count("(teardrop") - n_on - n_off))


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 1 and not os.path.isdir(a[0]):
        main(a[0])
    elif len(a) == 2:
        from Tools.KiCadDesignTools.core import config
        board_teardrops(config.load(a[0]), a[1])
    else:
        sys.exit(__doc__)
