"""Count the SDRAM pins, check the QSPI option table against the pin DB, list free pins.
Usage: python -I base.py <balls.json>   (-I drops the script dir from sys.path, so it is added back below)"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F401,F403

balls = load(sys.argv[1])
P2B = pin_of(balls)

# --- SDRAM ---
sd = {}
for s in SDRAM_SIGS:
    c = sig_pins(balls, s)
    assert len(c) == 1, (s, c)           # no choice: exactly one pin
    sd[s] = c[0]
for s, p in SDRAM_CHOICE.items():
    c = [x for x in sig_pins(balls, s) if x[0] == p]
    assert len(c) == 1, (s, p)
    sd[s] = c[0]
print('SDRAM signals:', len(sd), ' (D32 + A0-A12 13 + BA2 + NBL4 + 3 cmd + 3 chosen)')
print('  A0-A11 only:', len(sd) - 1)
pins = [v[0] for v in sd.values()]
assert len(set(pins)) == len(pins)
print('rings:', sorted(Counter(ring(v[1]) for v in sd.values()).items()))
print('edges:', sorted(Counter(edge(v[1]) for v in sd.values()).items()))

# --- QSPI option table vs DB ---
bad = 0
for s, opts in QSPI_OPT.items():
    have = {p: (b, a) for p, b, a in sig_pins(balls, s)}
    for o in opts:
        if o not in have:
            print('QSPI option NOT in DB', s, o)
            bad += 1
    extra = set(have) - set(opts)
    if extra:
        print('DB has extra options for', s, extra)
print('QSPI option table check: missing', bad)
clash = [(s, o) for s, opts in QSPI_OPT.items() for o in opts if o in pins]
print('QSPI options that are SDRAM pins:', clash)

# --- free pins ---
used = set(pins) | set(SWD.values()) | set(HSE.values()) | set(LSE.values())
gpio = [p for p in P2B if p.startswith('P') and p[1] in 'ABCDEFGHI' and p[2:].isdigit() or p in ('PC2_C', 'PC3_C')]
print('GPIO balls in DB:', len(gpio))
free = sorted((p for p in gpio if p not in used), key=lambda p: P2B[p])
print('free after SDRAM(57)+SWD+HSE+LSE:', len(free))
for p in free:
    print(' ', p, P2B[p], 'ring', ring(P2B[p]), edge(P2B[p]))
