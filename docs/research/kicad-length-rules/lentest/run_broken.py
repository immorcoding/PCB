"""E10: what happens when a length rule is written wrong?

Each case = one valid canary rule (D7 > 60 mm, must fire if the file is loaded) + one rule
with a defect.  We record: does the canary still fire (file loaded?), does the defective
rule fire (it should: it targets the same D7 / the SDRAM class), what the console says.

    D:\\KiCad\\bin\\python.exe -I run_broken.py
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run_drc import run
from parse_report import blocks, net_of

CANARY = '''(rule "canary_D7"
  (condition "A.NetName == '/SDRAM_D7'")
  (constraint length (max 60mm)))
'''

# name -> (defective rule text, what the defect is)
CASES = {
    "b00_control_ok": ('''(rule "target"
  (condition "A.NetClass == 'SDRAM'")
  (constraint length (max 52mm)))''', "no defect; control (nets > 52 mm fire)"),
    "b01_netclass_typo": ('''(rule "target"
  (condition "A.NetClass == 'SDRAMM'")
  (constraint length (max 52mm)))''', "netclass name misspelt (valid syntax)"),
    "b02_netname_no_slash": ('''(rule "target"
  (condition "A.NetName == 'SDRAM_D*'")
  (constraint length (max 52mm)))''', "net name without the leading '/'"),
    "b03_unknown_function": ('''(rule "target"
  (condition "A.hasNetclas('SDRAM')")
  (constraint length (max 52mm)))''', "function name misspelt: hasNetclas"),
    "b04_unknown_property": ('''(rule "target"
  (condition "A.NetClas == 'SDRAM'")
  (constraint length (max 52mm)))''', "property name misspelt: NetClas"),
    "b05_missing_paren": ('''(rule "target"
  (condition "A.NetClass == 'SDRAM'")
  (constraint length (max 52mm))''', "missing closing parenthesis"),
    "b06_unknown_constraint": ('''(rule "target"
  (condition "A.NetClass == 'SDRAM'")
  (constraint lenght (max 52mm)))''', "constraint name misspelt: lenght"),
    "b07_space_in_unit": ('''(rule "target"
  (condition "A.NetClass == 'SDRAM'")
  (constraint length (max 52 mm)))''', "unit separated by a space: 52 mm"),
    "b08_no_unit": ('''(rule "target"
  (condition "A.NetClass == 'SDRAM'")
  (constraint length (max 52)))''', "no unit: 52 means 52 nm"),
    "b09_single_equals": ('''(rule "target"
  (condition "A.NetClass = 'SDRAM'")
  (constraint length (max 52mm)))''', "single = in the condition"),
    "b10_lowercase_property": ('''(rule "target"
  (condition "A.netclass == 'SDRAM'")
  (constraint length (max 52mm)))''', "property name in lower case"),
    "b11_trailing_comment": ('''(rule "target"
  (condition "A.NetClass == 'SDRAM'")
  (constraint length (max 52mm)))   # trailing comment''', "comment after the closing paren (known trap)"),
    "b12_degree_unit_on_skew": ('''(rule "target"
  (condition "A.NetClass == 'SDRAM'")
  (constraint skew (max 2.5deg)))''', "wrong unit kind on skew"),
}

os.makedirs(os.path.join(HERE, "rules"), exist_ok=True)
os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
# "file loaded" = the canary fired OR the defective rule fired.  (When the defective rule also matches
# D7 it overrides the canary for D7 -- later rule wins -- so canary=False alone does not mean "not loaded".)
print(f"{'case':26s} {'loaded':7s} {'canary':7s} {'target':7s} {'blocks':7s} console")
for name, (body, why) in CASES.items():
    dru = os.path.join(HERE, "rules", name + ".kicad_dru")
    open(dru, "w", encoding="utf-8").write("(version 1)\n# " + why + "\n" + CANARY + "\n" + body + "\n")
    rc, console, text = run(dru)
    open(os.path.join(HERE, "results", name + ".rpt"), "w", encoding="utf-8").write(text)
    bl = blocks(text)
    canary = any(b.rule == "canary_D7" for b in bl)
    target = sorted({net_of(b) for b in bl if b.rule == "target"})
    con = " / ".join(l for l in console.strip().splitlines() if "drc.rpt" not in l)
    loaded = canary or len(target) > 0
    print(f"{name:26s} {str(loaded):7s} {str(canary):7s} {len(target):<7d} {len(bl):<7d} rc={rc} {con}")
    if 0 < len(target) <= 4:
        print("      target nets:", target)
