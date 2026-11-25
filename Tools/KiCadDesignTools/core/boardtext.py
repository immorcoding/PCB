"""Edits of a .kicad_pcb file as TEXT (no pcbnew): only the lines named change, every other byte stays.

    layer_rows(rows)          the copper rows of a board's layer table, rows = [(id, name, type, user name or None)]
    sync_layers(path, rows)   bring the copper rows of an existing board's layer table to rows
    unfill(path)              drop the saved fill of every zone
    strip(path, groups, origin)    remove what those busroute groups wrote last time (<board>.busroute.json)
    orphans(path, origin)     remove every track, arc and via left on the board

    python -m Tools.KiCadDesignTools.core.boardtext <board dir> unfill <board>
    python -m Tools.KiCadDesignTools.core.boardtext <board dir> strip <board> GROUP ...
    python -m Tools.KiCadDesignTools.core.boardtext <board dir> orphans <board>

The board folder gives the origin (board.toml [board] origin: local mm = board-file mm - origin).

unfill   drops the saved fill of every zone from the board file (text, nothing else changes). Run before any
         copper is added: pcbnew gives a via that lies in another net's stale fill that net when the board is
         loaded (docs/tools.md), and kicad-cli's refill loads the board first.
strip    removes what those busroute groups wrote last time, so that the driver's route step can rebuild them in
         their order (the SDRAM bus first, the power groups after it, against the bus).
orphans  removes every track, arc and via left on the board; the route step runs it right after stripping all its
         groups, when what is left belongs to no routes file.
"""
import json, os, re, sys


def layer_rows(rows):
    return "".join('\t\t(%d "%s" %s%s)\n' % (i, n, t, ' "%s"' % u if u else "") for i, n, t, u in rows)


def sync_layers(path, rows):
    """Bring the copper rows of an existing board's layer table to rows (type and user name); the stackup and
    every object stay. Text edit, nothing else in the file changes. True when it wrote."""
    s = open(path, encoding="utf-8", newline="").read()
    eol = "\r\n" if "\r\n" in s[:2000] else "\n"
    pat = "".join(r'\t\t\(%d "%s" (?:signal|power|mixed|jumper)(?: "[^"]*")?\)\r?\n' % (i, re.escape(n)) for i, n, _, _ in rows)
    m = re.search(pat, s)
    assert m, "copper rows of the layer table not found in %s" % path
    new = layer_rows(rows).replace("\n", eol)
    if m.group(0) == new:
        return False
    open(path, "w", encoding="utf-8", newline="").write(s[:m.start()] + new + s[m.end():])
    return True


def unfill(path):
    text = open(path, encoding="utf-8", newline="").read()
    lines = text.split("\n")
    out, i, n = [], 0, 0
    while i < len(lines):
        if re.match(r"^\t\t\(filled_polygon\r?$", lines[i]):
            j = i + 1
            while not re.match(r"^\t\t\)\r?$", lines[j]):
                j += 1
            i, n = j + 1, n + 1
            continue
        out.append(lines[i])
        i += 1
    if n:
        open(path, "w", encoding="utf-8", newline="").write("\n".join(out))
    print("unfill: %d filled polygons removed from %s" % (n, os.path.basename(path)))


def strip(path, groups, origin):
    """Remove what the busroute groups `groups` wrote into the board last time (as recorded in <board>.busroute.json),
    so that the groups can be rebuilt from scratch in their order (the SDRAM bus first, the power groups after it,
    against the bus). The board's busroute module does the writing (pcbnew)."""
    from Tools.KiCadDesignTools.routing.busroute.board import write, Board
    side = os.path.splitext(path)[0] + ".busroute.json"
    rec = json.load(open(side, encoding="utf-8")) if os.path.isfile(side) else {"groups": {}}
    cu = None
    for g in groups:
        if g not in rec["groups"]:
            print("strip: no group %s recorded in %s" % (g, os.path.basename(side)))
            continue
        if cu is None:
            cu = Board(path, origin).cu
        shared = "segs" in rec["groups"][g]
        w = write(path, path, g, [], [], [], origin, cu, shared=shared)
        print("strip: group %s, %d items removed" % (g, w["removed"]))


def orphans(path, origin):
    """Remove the tracks, arcs and vias no routes file writes. The route step runs it right after stripping every
    group, so whatever copper is left is owned by no group record and would never be rebuilt (2026-11-23: a +3V3_MCU
    via at (40.325, 33.425) and its 0.57 mm L6 stub, left from stop 5 (commit 21a8970), one dangling track end). Text
    edit of the board file; every removed item is listed (local coordinates)."""
    text = open(path, encoding="utf-8", newline="").read()
    lines = text.split("\n")
    out, i, gone = [], 0, []
    while i < len(lines):
        m = re.match(r"^\t\((segment|arc|via)\r?$", lines[i])
        if m:
            j = i + 1
            while not re.match(r"^\t\)\r?$", lines[j]):
                j += 1
            body = " ".join(l.strip() for l in lines[i:j + 1])
            pos = re.search(r"\((?:start|at) ([-\d.]+) ([-\d.]+)\)", body)
            net = re.search(r'\(net "([^"]*)"\)', body)
            lay = re.search(r'\(layers? "([^"]+)"', body)
            gone.append("%s %s %s (%.3f, %.3f)" % (m.group(1), net.group(1) if net else "?", lay.group(1) if lay else "?",
                                                   float(pos.group(1)) - origin[0], float(pos.group(2)) - origin[1]))
            i = j + 1
            continue
        out.append(lines[i])
        i += 1
    if gone:
        open(path, "w", encoding="utf-8", newline="").write("\n".join(out))
    print("orphans: %d item(s) owned by no group removed%s" % (len(gone), "".join("\n  " + g for g in gone)))


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(argv) < 3 or argv[1] not in ("unfill", "strip", "orphans"):
        print(__doc__)
        return 2
    from Tools.KiCadDesignTools.core import config
    cfg = config.load(argv[0])
    cmd, path = argv[1], argv[2]
    if cmd == "unfill":
        unfill(path)
    elif cmd == "strip":
        strip(path, argv[3:], cfg.origin)
    else:
        orphans(path, cfg.origin)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
