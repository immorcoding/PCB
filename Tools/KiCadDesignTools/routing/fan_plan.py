"""The MCU signal fan-out of a BGA block plan (bga_fan.json, the board's bga_fan.py) as busroute pieces, for the MCU
routes files (routes_mcu_east.py, routes_mcu_south.py, routes_mcu_nw.py, ...).

    from Tools.KiCadDesignTools.routing.fan_plan import plan, lead, ext, info

plan()          the plan (bga_fan.json) of the board whose routes file busroute is building: the file named by
                place.toml [fan] file in that routes file's board folder (busroute.job.ROUTES_FILE); BGA_FAN=<file>
                names another plan
lead(ball)      [(top, ["<ref>.<ball>", via]), ("via", via), (layer, [via, ..., exit])]: the dog-bone on the top layer
                and the straight run on the inner layer to the edge of the package's rule area, as planned; <ref> is
                place.toml [fan] ref (the MCU)
ext(pcs, pts)   the same pieces with the last one running on through pts (local mm)
info(ball)      the plan's record (net, via, layer, side, run, exit)
"""
import json, os

from Tools.KiCadDesignTools.core import config

_plans, _cfgs = {}, {}           # plan file -> plan, board folder -> configuration: read once per process


def _board():
    from Tools.KiCadDesignTools.routing.busroute import job
    if not job.ROUTES_FILE:
        raise config.ConfigError("fan_plan: no routes file is being built (busroute.job.load sets it)")
    d = os.path.dirname(job.ROUTES_FILE)
    if d not in _cfgs:
        _cfgs[d] = config.load(d)
    return _cfgs[d]


def _fan(cfg):
    fan = cfg.datafile("place.toml").get("fan") or {}
    if not fan.get("file") or not fan.get("ref"):
        raise config.ConfigError("%s: place.toml [fan] file and ref are needed by fan_plan" % cfg.dir)
    return fan


def plan():
    path = os.environ.get("BGA_FAN")
    if not path:
        cfg = _board()
        path = cfg.path(_fan(cfg)["file"])
    if path not in _plans:
        _plans[path] = json.load(open(path, encoding="utf-8"))
    return _plans[path]


def info(ball):
    return plan()[_fan(_board())["ref"]]["signal"][ball]


def lead(ball):
    cfg = _board()
    s = info(ball)
    via = tuple(s["via"])
    run = [tuple(p) for p in s["run"]]
    if run and run[0] != via:
        run = [via] + run
    return [(cfg.layers[0].L, [_fan(cfg)["ref"] + "." + ball, via]), ("via", via), (s["layer"], run)]


def ext(pcs, pts):
    pcs = [tuple(pc) for pc in pcs]
    lay, p = pcs[-1][0], list(pcs[-1][1])
    return pcs[:-1] + [(lay, p + [tuple(q) for q in pts])]
