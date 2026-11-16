"""Print the length / skew / via_count blocks of a saved report, one line per block.

    D:\\KiCad\\bin\\python.exe -I summarize.py results\\<name>.rpt [more.rpt ...]
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from parse_report import blocks, net_of

WANT = ("length_out_of_range", "skew_out_of_range", "too_many_vias", "via_count_out_of_range")
for path in sys.argv[1:]:
    text = open(path, encoding="utf-8", errors="replace").read()
    print("==", os.path.basename(path))
    n = 0
    for b in blocks(text):
        if b.code in WANT:
            n += 1
            print(f"  {b.code:20s} rule={b.rule!r:28s} net={net_of(b):16s} nums={b.numbers}")
            if b.code == "skew_out_of_range":
                print("      ", b.detail)
    other = {}
    for b in blocks(text):
        if b.code not in WANT:
            other[b.code] = other.get(b.code, 0) + 1
    print(f"  -> {n} length/skew blocks; other violations: {other}")
