"""Pairwise hard conflicts: signals whose only remaining pin (after removing SDRAM / SWD / HSE / LSE
pins) is the same for two peripherals, plus the pairs the full solver cannot place together.
Usage: python -I conflicts.py <balls.json>"""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F401,F403
from solve import Ctx, PERIPH, UARTS  # noqa: E402

ctx = Ctx(load(sys.argv[1]))
pool = ['ETH', 'SD1', 'SD1CTL', 'SD2', 'ULPI', 'LCD565', 'LCD888X', 'DCMI8', 'DCMI10X', 'DCMI12X', 'SAI1', 'CAN1', 'CAN2']
fixed = {}
for n in pool:
    for lab, sg in PERIPH[n]:
        c = ctx.cand(sg, ctx.reserved)
        if len(c) == 1:
            fixed.setdefault(c[0][0], []).append((n, lab))
print('pins that are the ONLY choice of some signal, shared by two peripherals:')
for p, v in sorted(fixed.items()):
    if len({n for n, _ in v}) > 1:
        print(' ', p, ctx.p2b[p], v)
print('\npairs the solver cannot place together (with QSPI + a debug UART):')
for a, b in itertools.combinations(pool, 2):
    if ctx.solve([a, b], UARTS[0]) is None and not any(ctx.solve([a, b], u) for u in UARTS):
        print('  ', a, '+', b)
