"""Regression benchmark for scripts/impedance.py.

    D:\\KiCad\\bin\\python.exe scripts\\tests\\impedance\\check.py

Exit 0 = pass. Prints one OK / FAIL line first (scripts/regress.py shows it), then
one line per check. Checks:
  A  mask-free rectangular microstrip against the Hammerstad-Jensen closed form
  B  the widths published in docs/research/jlc-6layer-capability.md section 6
     (branch research/jlc-6layer-capability), which came from an unsaved solver
  C  values of this solver pinned on 2026-11-20, so a change to the model or the
     grid shows up; update them only together with a reason
  D  the answer does not move when the grid is refined or the box is enlarged
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
import impedance as imp

HJ_TOL = 0.015          # relative
NOTE_TOL = 0.004        # mm on width
PIN_TOL = 0.05          # ohm
CONV_TOL = 0.003        # relative

fails, lines = [], []


def check(label, got, want, tol, unit, relative=False):
    err = abs(got - want) / want if relative else abs(got - want)
    ok = err <= tol
    shown = "%.2f %%" % (100 * (got - want) / want) if relative else "%+.4f %s" % (got - want, unit)
    lines.append("%s  %-46s got %8.4f  want %8.4f %s  diff %s" % ("ok  " if ok else "FAIL", label, got, want, unit, shown))
    if not ok:
        fails.append(label)


t0 = time.time()

# A: closed form. h = 0.0994, Er 4.1, t = 1.6 mil, no mask, rectangular trace.
for w in (0.10, 0.17, 0.25):
    ref = imp.hammerstad_jensen(w, 0.0994, 4.1, 1.6 * imp.MIL)[0]
    check("A microstrip w=%.2f vs Hammerstad-Jensen" % w, imp.z0("L1", w, mask="none", etch=0.0), ref, HJ_TOL, "ohm", True)

# B: the research note. L1 gaps are the grid-aligned ones the note really used.
check("B 50 ohm width L1", imp.width_for_z0("L1", 50), 0.156, NOTE_TOL, "mm")
check("B 50 ohm width L4", imp.width_for_z0("L4", 50), 0.125, NOTE_TOL, "mm")
for gap, w in ((0.0994, 0.110), (0.1243, 0.128), (0.1491, 0.141), (0.1988, 0.157)):
    check("B 90 ohm diff width L1 gap %.4f" % gap, imp.width_for_zdiff("L1", 90, gap), w, NOTE_TOL, "mm")
for gap, w in ((0.10, 0.091), (0.125, 0.104), (0.15, 0.113), (0.20, 0.125)):
    check("B 90 ohm diff width L4 gap %.3f" % gap, imp.width_for_zdiff("L4", 90, gap), w, NOTE_TOL, "mm")

# C: pinned values of this solver (default grid, intl mask set, 1.6 / 0.6 mil copper).
check("C Z0    L1 w=0.157", imp.z0("L1", 0.157), 50.034, PIN_TOL, "ohm")
check("C Zdiff L1 w=0.11 gap=0.15", imp.zdiff("L1", 0.11, 0.15), 99.56, PIN_TOL, "ohm")
check("C Z0    L4 w=0.127", imp.z0("L4", 0.127), 49.962, PIN_TOL, "ohm")
check("C Z0    L3 w=0.127 (same build as L4, 2026-11-23)", imp.z0("L3", 0.127), 49.962, PIN_TOL, "ohm")
check("C Zdiff L4 w=0.09 gap=0.15", imp.zdiff("L4", 0.09, 0.15), 99.346, PIN_TOL, "ohm")
check("C Zdiff L1 w=0.11 gap=0.15, 0.035 copper", imp.zdiff("L1", 0.11, 0.15, copper=0.035), 101.38, PIN_TOL, "ohm")
check("C Zdiff L1 w=0.11 gap=0.15, domestic mask", imp.zdiff("L1", 0.11, 0.15, mask="domestic"), 98.41, PIN_TOL, "ohm")

# D: convergence. Default grid against a grid twice as fine and a box twice as large.
for label, f in (("Z0 L1 w=0.157", lambda **k: imp.z0("L1", 0.157, **k)),
                 ("Zdiff L1 0.11/0.15", lambda **k: imp.zdiff("L1", 0.11, 0.15, **k)),
                 ("Zdiff L4 0.09/0.15", lambda **k: imp.zdiff("L4", 0.09, 0.15, **k))):
    base = f()
    check("D %s, grid twice as fine" % label, base, f(res=imp.RES / 2), CONV_TOL, "ohm", True)
    check("D %s, box twice as large" % label, base, f(box=imp.BOX * 2), CONV_TOL, "ohm", True)

dt = time.time() - t0
if fails:
    print("FAIL impedance: %d of %d checks failed in %.1f s: %s" % (len(fails), len(lines), dt, "; ".join(fails)))
else:
    print("OK impedance: %d checks passed in %.1f s" % (len(lines), dt))
print("\n".join(lines))
sys.exit(1 if fails else 0)
