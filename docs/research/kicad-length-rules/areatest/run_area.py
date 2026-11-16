"""Q5: track_width rules scoped by rule area.  For each rule set, list which tracks get a
track_width violation (net name + position of the flagged segment).

    D:\\KiCad\\bin\\python.exe -I run_area.py
"""
import os, re, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lentest"))
from parse_report import blocks

CLI = r"D:\KiCad\bin\kicad-cli.exe"
GLOBAL = '''(rule "signal_min"
  (condition "A.Type == 'Track'")
  (constraint track_width (min 0.1016mm)))
'''
SETS = {
 "q01_no_area_rule": ("(version 1)\n" + GLOBAL,
   "only the global min 0.1016 (the template's signal_width without the 0.8128 max)"),
 "q02_intersects_min": ("(version 1)\n" + GLOBAL + '''(rule "bga_min"
  (condition "A.Type == 'Track' && A.intersectsArea('bga')")
  (constraint track_width (min 0.09mm)))
''', "global min + later rule: tracks touching the area may be 0.09"),
 "q03_intersects_exact": ("(version 1)\n" + GLOBAL + '''(rule "bga_exact"
  (condition "A.Type == 'Track' && A.intersectsArea('bga')")
  (constraint track_width (min 0.09mm) (max 0.09mm)))
''', "inside = exactly 0.09, using intersectsArea (crossing / touching segments count as inside)"),
 "q04_insidearea_alias": ("(version 1)\n" + GLOBAL + '''(rule "bga_exact"
  (condition "A.Type == 'Track' && A.insideArea('bga')")
  (constraint track_width (min 0.09mm) (max 0.09mm)))
''', "same with the deprecated insideArea()"),
 "q05_enclosed_exact": ("(version 1)\n" + GLOBAL + '''(rule "bga_exact"
  (condition "A.Type == 'Track' && A.enclosedByArea('bga')")
  (constraint track_width (min 0.09mm) (max 0.09mm)))
''', "inside = exactly 0.09, using enclosedByArea (only fully-inside segments)"),
 "q06_split_three_way": ("(version 1)\n" + GLOBAL + '''(rule "crossing_any"
  (condition "A.Type == 'Track' && A.intersectsArea('bga') && !A.enclosedByArea('bga')")
  (constraint track_width (min 0.09mm)))
(rule "inside_exact"
  (condition "A.Type == 'Track' && A.enclosedByArea('bga')")
  (constraint track_width (min 0.09mm) (max 0.09mm)))
''', "three classes: fully inside = 0.09 exactly; crossing = >= 0.09; outside = global min"),
 "q07_wildcard_name": ("(version 1)\n" + GLOBAL + '''(rule "bga_exact"
  (condition "A.Type == 'Track' && A.intersectsArea('bg*')")
  (constraint track_width (min 0.09mm) (max 0.09mm)))
''', "area name with a wildcard"),
 "q08_area_name_typo": ("(version 1)\n" + GLOBAL + '''(rule "bga_exact"
  (condition "A.Type == 'Track' && A.intersectsArea('bgaa')")
  (constraint track_width (min 0.09mm) (max 0.09mm)))
''', "area name misspelt: does anything warn?"),
}


def run(dru_text):
    tmp = tempfile.mkdtemp(prefix="areatest_")
    try:
        for ext in (".kicad_pcb", ".kicad_pro"):
            shutil.copy(os.path.join(HERE, "areatest" + ext), os.path.join(tmp, "areatest" + ext))
        open(os.path.join(tmp, "areatest.kicad_dru"), "w", encoding="utf-8").write(dru_text)
        out = os.path.join(tmp, "o.rpt")
        subprocess.run([CLI, "pcb", "drc", "--severity-all", "--units", "mm", "-o", out,
                        os.path.join(tmp, "areatest.kicad_pcb")], capture_output=True)
        return open(out, encoding="utf-8", errors="replace").read()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
os.makedirs(os.path.join(HERE, "rules"), exist_ok=True)
for name, (dru, note) in SETS.items():
    open(os.path.join(HERE, "rules", name + ".kicad_dru"), "w", encoding="utf-8").write(dru)
    text = run(dru)
    open(os.path.join(HERE, "results", name + ".rpt"), "w", encoding="utf-8").write(text)
    print(f"--- {name}: {note}")
    flagged = []
    for b in blocks(text):
        if b.code == "track_width":
            for it in b.items:
                m = re.match(r"@\(([-\d.]+) mm, ([-\d.]+) mm\): .*?\[([^\]]*)\]", it)
                if m:
                    flagged.append((m.group(3), float(m.group(1)), float(m.group(2)), b.rule, b.numbers))
    seen = set()
    for n, x, y, rule, nums in sorted(flagged):
        key = (n, x, y)
        if key in seen:
            continue
        seen.add(key)
        print(f"   flagged {n:22s} at ({x:g},{y:g})  rule={rule}  nums={nums}")
    if not flagged:
        print("   (no track_width violations)")
