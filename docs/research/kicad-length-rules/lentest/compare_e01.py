"""E01 check: KiCad's DRC length per net vs. the analytic length in expected.json.

    D:\\KiCad\\bin\\python.exe -I compare_e01.py [results\\e01_probe_all_lengths.rpt]
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from parse_report import blocks

rpt = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results", "e01_probe_all_lengths.rpt")
exp = json.load(open(os.path.join(HERE, "expected.json"), encoding="utf-8"))
text = open(rpt, encoding="utf-8").read()

# one length_out_of_range block per net; the net comes from the items listed under it
got = {}
for b in blocks(text):
    if b.code != "length_out_of_range":
        continue
    nets = set(b.nets)
    # the block lists up to 4 items, all from the same net
    for n in nets:
        got[n] = b.numbers[-1]          # last "N mm" in the line = actual

print(f"{'net':22s} {'tracks(analytic)':>16s} {'DRC actual':>11s} {'diff':>9s}  vias  pad-to-die")
for n, e in exp.items():
    a = got.get(n)
    d = None if a is None else a - e["track"]
    print(f"{n:22s} {e['track']:16.4f} {a if a is not None else float('nan'):11.4f} "
          f"{d if d is not None else float('nan'):9.4f}  {len(e['vias'])}     {e['pad_to_die']}")
