"""PROTOTYPE (issue 16): switch a variant's rule file to one pad connection style for every pad.

    D:\\KiCad\\bin\\python.exe pad_rules.py <file.kicad_dru> thermal|solid

thermal: SMD pads get thermal relief too (rule smd_solid replaced)
solid:   through-hole pads get solid connection too (rule tht_thermal replaced)
"""
import re, sys

path, mode = sys.argv[1:3]
s = open(path, encoding="utf-8").read()
if mode == "thermal":
    s, n = re.subn(r'\(rule "smd_solid".*?\(constraint zone_connection solid\)\)',
                   '(rule "smd_thermal"\n'
                   '  (condition "A.Type == \'Pad\' && A.Pad_Type == \'SMD\'")\n'
                   '  (constraint zone_connection thermal_reliefs)\n'
                   '  (constraint thermal_spoke_width (min 0.254mm))\n'
                   '  (constraint thermal_relief_gap (min 0.254mm)))', s, flags=re.S)
else:
    s, n = re.subn(r'\(rule "tht_thermal".*?\(constraint min_resolved_spokes 2\)\)',
                   '(rule "tht_solid"\n'
                   '  (condition "A.Type == \'Pad\' && A.Pad_Type == \'Through-hole\'")\n'
                   '  (constraint zone_connection solid))', s, flags=re.S)
assert n == 1, "rule not found"
open(path, "w", encoding="utf-8", newline="\n").write(s)
print(path, "->", mode)
