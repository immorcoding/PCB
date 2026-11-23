"""The MCU signal fan-out of the BGA block plan (bga_fan.json, bga_fan.py) as busroute pieces, for the MCU route files
(routes_mcu_east.py, routes_mcu_south.py, routes_mcu_nw.py).

lead(ball)      [("L1", ["U201.<ball>", via]), ("via", via), (layer, [via, ..., exit])]: the dog-bone and the straight
                run on the inner layer to the edge of the MCU's rule area, as planned
ext(pcs, pts)   the same pieces with the last one running on through pts (local mm)
info(ball)      the plan's record (net, via, layer, side, run, exit)
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = os.environ.get("BGA_FAN", os.path.join(HERE, "bga_fan.json"))
_plan = None


def plan():
    global _plan
    if _plan is None:
        _plan = json.load(open(PLAN, encoding="utf-8"))
    return _plan


def info(ball):
    return plan()["U201"]["signal"][ball]


def lead(ball):
    s = info(ball)
    via = tuple(s["via"])
    run = [tuple(p) for p in s["run"]]
    if run and run[0] != via:
        run = [via] + run
    return [("L1", ["U201." + ball, via]), ("via", via), (s["layer"], run)]


def ext(pcs, pts):
    pcs = [tuple(pc) for pc in pcs]
    lay, p = pcs[-1][0], list(pcs[-1][1])
    return pcs[:-1] + [(lay, p + [tuple(q) for q in pts])]
