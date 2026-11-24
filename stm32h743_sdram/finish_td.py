"""Teardrops of the STM32H743 + SDRAM board (finish.py teardrops; FIN-4, last copper step).

As scripts/teardrops.py (the earlier boards: every pad and via, KiCad's teardrop parameters written into the file
because pcbnew's Python API does not expose them, then kicad-cli refills and saves, which builds the teardrop
areas), but not inside the two BGA rule areas: there the 0.09 mm tracks run between 0.30 mm vias and balls at the
area's 0.09 mm clearance, and a teardrop would widen the track into that gap. Pads of the two BGAs and of the parts
under them, and vias inside the areas, keep teardrops off; so do the pads of footprints with their own keep-outs (J501, J801). Prints the count of teardrop areas in the saved board.
"""
import os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from kisch import parse, dump, find
import teardrops as TDS

OX, OY = 100.0, 100.0
# the rule areas of place.py (body + 1 mm), board-file mm
AREAS = [(34.0 + OX, 31.0 + OY, 46.0 + OX, 43.0 + OY), (52.0 + OX, 29.5 + OY, 62.0 + OX, 44.5 + OY)]
OFF = [x if x[0] != "enabled" else ["enabled", "no"] for x in TDS.TD]


def inside(x, y):
    return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in AREAS)


def put(node, on):
    old = find(node, "teardrops")
    if old is not None:
        node.remove(old)
    at = next(i for i, x in enumerate(node) if isinstance(x, list) and x and x[0] in ("net", "uuid", "pinfunction", "pintype"))
    node.insert(at, list(TDS.TD if on else OFF))


def main(path):
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
            # off in a footprint that carries its own keep-outs (J501's shield contact areas, J801's): a teardrop is
            # copper the keep-out forbids (DRC items_not_allowed on the RJ45 shield pads)
            own_ko = any(isinstance(z, list) and z and z[0] == "zone" for z in c)
            on = not inside(float(at[1]), float(at[2])) and not own_ko
            for p in c:
                if isinstance(p, list) and p and p[0] == "pad":
                    put(p, on)
                    n_on, n_off = n_on + on, n_off + (not on)
    open(path, "w", encoding="utf-8", newline="\n").write(dump(tree) + "\n")
    subprocess.run([TDS.KICAD_CLI, "pcb", "drc", "--refill-zones", "--save-board", "--severity-all", "-o", os.devnull, path],
                   capture_output=True)
    text = open(path, encoding="utf-8").read()
    print("teardrops: enabled on %d pads / vias, off on %d (BGA areas); teardrop areas in the saved board: %d"
          % (n_on, n_off, text.count("(teardrop") - n_on - n_off))


if __name__ == "__main__":
    main(sys.argv[1])
