"""E04/E05: via heights vs. stackup / "use height" switch, via_count, pad-to-die.

Uses the E01 probe rule (every net reported with its length) on three versions of the board:
  A  as built (explicit stackup, use_height_for_length_calcs = true)
  B  stackup block removed from the .kicad_pcb (KiCad builds a default stackup)
  C  use_height_for_length_calcs = false in the .kicad_pro
and a via_count rule on A and C.

    D:\\KiCad\\bin\\python.exe -I run_variants.py
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run_drc import run
from parse_report import blocks

exp = json.load(open(os.path.join(HERE, "expected.json"), encoding="utf-8"))
PROBE = '(version 1)\n(rule "probe_all_lengths" (constraint length (max 1mm)))\n'
VIACNT = ('(version 1)\n(rule "via_cnt" (condition "A.NetClass == \'SDRAM\'") '
          '(constraint via_count (max 1)))\n')


def no_stackup(t):
    return re.sub(r"\t\t\(stackup.*?\n\t\t\)\n", "", t, count=1, flags=re.S)


def height_off(t):
    d = json.loads(t)
    d["board"]["design_settings"]["rules"]["use_height_for_length_calcs"] = False
    return json.dumps(d, indent=2)


def lengths(text):
    got = {}
    for b in blocks(text):
        if b.code == "length_out_of_range":
            for n in set(b.nets):
                got[n] = b.numbers[-1]
    return got


variants = {"A explicit stackup, height on": {}, "B no stackup block": {"pcb_edit": no_stackup},
            "C height off": {"pro_edit": height_off}}
res = {}
for k, kw in variants.items():
    rc, con, text = run(None, dru_text=PROBE, **kw)
    res[k] = lengths(text)
    open(os.path.join(HERE, "results", "e04_" + k[0] + ".rpt"), "w", encoding="utf-8").write(text)

print(f"{'net':12s} {'trk':>8s} | " + " | ".join(f"{k[:1]}: total  via" for k in variants))
for n in ["/SDRAM_D0", "/SDRAM_D3", "/SDRAM_D4", "/SDRAM_D5", "/SDRAM_D6", "/SDRAM_D8"]:
    row = f"{n:12s} {exp[n]['track']:8.4f} | "
    cells = []
    for k in variants:
        t = res[k][n]
        cells.append(f"{t:8.4f} {t - exp[n]['track']:7.4f}")
    print(row + " | ".join(cells))

for label, kw in (("A", {}), ("C", {"pro_edit": height_off})):
    rc, con, text = run(None, dru_text=VIACNT, **kw)
    open(os.path.join(HERE, "results", f"e05_via_count_{label}.rpt"), "w", encoding="utf-8").write(text)
    hits = sorted({n for b in blocks(text) if b.code == "too_many_vias" or "via" in b.code and "count" in b.code
                   for n in set(b.nets)})
    codes = sorted({b.code for b in blocks(text) if "via" in b.code})
    print(f"via_count max 1, variant {label}: nets flagged = {hits}; via-related codes: {codes}")
