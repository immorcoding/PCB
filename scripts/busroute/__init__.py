"""busroute: script-written routing for buses (project rules RTE-4, RTE-13; rule profile C).

    board.py     snapshot of a .kicad_pcb (pads, rule areas, outline, existing copper, stackup); the writer
    profile.py   the numbers: widths, clearances, vias, limits, read from the .kicad_pro / .kicad_dru
    routes.py    the routes format; width and via size by position; lengths by geometry
    geom.py      exact 0/45/90 geometry on a 0.1 um grid
    bundle.py    Bundle / Bus: lanes, fans, joins, widen, per-leg gaps, spans, via fields (layer change)
    fanout.py    BGA escape leads by rule
    checks.py    the checks without KiCad
    metrics.py   DRC, DRC lengths, track_shape, canary; metrics.json and the text table
    render.py    PNG views
    job.py       one build of one group (the routes file is described there)
    build.py     the command line

Benchmark: scripts/tests/busroute/check.py (run by scripts/regress.py).
"""
from .geom import RouteError
from .board import Board
from .profile import Profile
from .bundle import Bundle, Bus, PitchError
from .fanout import Fanout, Lead
