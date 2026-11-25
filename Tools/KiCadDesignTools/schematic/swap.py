"""The memory part whose data bits may be swapped (board.toml [schematic.swap]): its ball map and the swap table, for
the page that draws it (sch/<page>.py) and the netlist check (schematic.check, check 3).

    [schematic.swap]
    ref = "U2"                      # the part, its page, the byte lanes, the MCU-side net names (schematic.check)
    page = "main"
    table = "swap.csv"              # columns sdram (DQn, DQMn: the part's signal) and net (the MCU-side net)
    columns = [1, 2, 3, 7, 8, 9]    # the ball columns of the page's grid, left to right
    balls = 90                      # balls in the grid (a check of the transcription)
    nc_as = { H3 = "A12" }          # optional: NC balls wired as a signal (the H743: A12 of the 512 Mb parts)

The page keeps the part's ball grid as the datasheet prints it (BALLS: one line per row, the row letter, then one
signal name per column) and gives it here in one line:

    def ball_map():
        return balls_of(BALLS)           # from Tools.KiCadDesignTools.schematic.swap import ball_map as balls_of

The board comes from schematic.sheet.configure(cfg) (schematic.generate calls it before the pages are imported), or
from the cfg argument.
"""
import csv

from Tools.KiCadDesignTools.core import config
from Tools.KiCadDesignTools.schematic import sheet


def _board(cfg):
    cfg = cfg or sheet.CFG
    if cfg is None:
        raise config.ConfigError("schematic.swap: no board (schematic.sheet.configure(cfg) first, or pass cfg)")
    return cfg


def ball_map(grid, cfg=None):
    """{ball: signal name} of the swapped part from its grid (BALLS) and [schematic.swap] columns, balls, nc_as."""
    cfg = _board(cfg)
    cols = cfg.need("schematic.swap.columns")
    out = {}
    for line in grid.strip().splitlines():
        row, *names = line.split()
        if len(names) != len(cols):
            raise config.ConfigError("schematic.swap: row %s of the ball grid has %d names for %d columns %s"
                                     % (row, len(names), len(cols), cols))
        for col, name in zip(cols, names):
            out["%s%d" % (row, col)] = name
    n = cfg.get("schematic.swap.balls")
    if n is not None and len(out) != n:
        raise config.ConfigError("schematic.swap: %d balls in the grid, [schematic.swap] balls = %d" % (len(out), n))
    for ball, sig in (cfg.get("schematic.swap.nc_as") or {}).items():
        if out.get(ball) != "NC":
            raise config.ConfigError("schematic.swap: nc_as %s: the grid has %s there, not NC" % (ball, out.get(ball)))
        out[ball] = sig
    return out


def swap_table(cfg=None):
    """{signal of the part (DQn, DQMn): MCU-side net} from [schematic.swap] table (default swap.csv)."""
    cfg = _board(cfg)
    with open(cfg.path(cfg.get("schematic.swap.table", "swap.csv")), encoding="utf-8") as f:
        return {r["sdram"]: r["net"] for r in csv.DictReader(f)}
