"""E06-E09: what skew / length rules can express for the SDRAM-style requirements.

Lengths (from E01): D0 50.000  D1 51.657  D2 53.425  SDCLK 50.828  (D3 52.862 D8 54.500 ...)

  E06  skew group {SDCLK, D0, D2}: reference is the LONGEST net (D2), not the clock
  E07  per-net length windows generated around the clock length (+-2.5 mm, and "not shorter than clock")
  E08  two rules at once on the same nets (class length max + group skew): both reported?
  E09  rule order: class rule first, per-net exception later (later wins)
  E10  fromTo(): path rules, and a path across a series resistor (two nets)

    D:\\KiCad\\bin\\python.exe -I run_skew.py
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run_drc import run
from parse_report import blocks, net_of

LEN = {}
rc, con, text = run(None, dru_text='(version 1)\n(rule "p" (constraint length (max 1mm)))\n')
for b in blocks(text):
    if b.code == "length_out_of_range":
        LEN[net_of(b)] = b.numbers[-1]
CLK = LEN["/SDCLK"]


def go(name, dru, note, show=("length_out_of_range", "skew_out_of_range", "too_many_vias")):
    rc, con, text = run(None, dru_text=dru)
    open(os.path.join(HERE, "rules", name + ".kicad_dru"), "w", encoding="utf-8").write(dru)
    open(os.path.join(HERE, "results", name + ".rpt"), "w", encoding="utf-8").write(text)
    print(f"--- {name}: {note}")
    for b in blocks(text):
        if b.code in show:
            extra = ""
            if b.code == "skew_out_of_range":
                n = b.numbers          # max skew, actual skew, target length, actual length
                extra = f" skew={n[1]:+.4f} (limit {n[0]}), reference length {n[2]:.4f}, own {n[3]:.4f}"
            else:
                extra = f" nums={b.numbers}"
            print(f"   {b.code:20s} rule={b.rule:22s} net={net_of(b):12s}{extra}")
    return text


# E06: reference = longest of the group
go("e06_skew_group_clock_d0_d2", '''(version 1)
(rule "skew_clk_d0_d2"
  (condition "A.NetName == '/SDCLK' || A.NetName == '/SDRAM_D0' || A.NetName == '/SDRAM_D2'")
  (constraint skew (max 2.5mm)))
''', f"group SDCLK {CLK:.3f} / D0 {LEN['/SDRAM_D0']:.3f} / D2 {LEN['/SDRAM_D2']:.3f}; true +-2.5 about SDCLK would flag only D2 (+2.597)")

# E07: generated windows around the clock
lo, hi = CLK - 2.5, CLK + 2.5
rules = ["(version 1)"]
for n in ["/SDRAM_D0", "/SDRAM_D1", "/SDRAM_D2", "/SDRAM_D3", "/SDRAM_D8", "/SDRAM_D9", "/SDRAM_D10"]:
    rules.append(f'(rule "win_{n[1:]}"\n  (condition "A.NetName == \'{n}\'")\n'
                 f'  (constraint length (min {lo:.4f}mm) (opt {CLK:.4f}mm) (max {hi:.4f}mm)))')
go("e07_generated_windows", "\n".join(rules) + "\n",
   f"window {lo:.3f}..{hi:.3f} around SDCLK {CLK:.3f}; D0 (50.0) is -0.83 -> fine, D10 (57.7) +6.9 -> flag, D2 +2.597 -> flag")

# E07c: the same window as ONE rule over the whole group (only the numbers come from the clock)
go("e07c_one_window_rule_for_group", f'''(version 1)
(rule "sdram_data_window"
  (condition "A.NetName == '/SDRAM_D*'")
  (constraint length (min {lo:.4f}mm) (opt {CLK:.4f}mm) (max {hi:.4f}mm)))
''', f"one rule for D0..D10 (incl. the 70 mm D7): window {lo:.3f}..{hi:.3f}; expect D2, D7, D8, D10 flagged, nothing under {lo:.3f}")

# E07b: "data not shorter than clock" as a min
go("e07b_min_clock", f'''(version 1)
(rule "not_shorter_than_clock"
  (condition "A.NetName == '/SDRAM_D*'")
  (constraint length (min {CLK:.4f}mm)))
''', f"every D* net must be >= SDCLK {CLK:.3f}: D0 (50.000) and D6 (50.285) are shorter, D4 (51.116) is not")

# E08: two rules on the same nets (length and skew), different rules
go("e08_length_and_skew_together", '''(version 1)
(rule "grp_len"
  (condition "A.NetClass == 'SDRAM'")
  (constraint length (max 52mm)))
(rule "grp_skew"
  (condition "A.NetClass == 'SDRAM' && A.NetName != '/SDRAM_D7'")
  (constraint skew (max 7mm)))
''', "length max 52 and skew max 7 on overlapping sets: both must report")

# E09: order
go("e09_order_later_wins", '''(version 1)
(rule "class_len"
  (condition "A.NetClass == 'SDRAM'")
  (constraint length (max 60mm)))
(rule "exception_D7"
  (condition "A.NetName == '/SDRAM_D7'")
  (constraint length (max 75mm)))
''', "class max 60 first, D7 exception 75 later: D7 (70) must NOT be reported")
go("e09b_order_earlier_loses", '''(version 1)
(rule "exception_D7"
  (condition "A.NetName == '/SDRAM_D7'")
  (constraint length (max 75mm)))
(rule "class_len"
  (condition "A.NetClass == 'SDRAM'")
  (constraint length (max 60mm)))
''', "reverse order: the class rule is later, so it wins for D7: D7 (70) reported")

# E10: fromTo
go("e10_fromto_path", '''(version 1)
(rule "path_J1_J2_row1"
  (condition "A.fromTo('J1-1', 'J2-1')")
  (constraint length (max 49mm)))
(rule "path_J1_J2_row4_with_vias"
  (condition "A.fromTo('J1-4', 'J2-4')")
  (constraint length (max 52mm)))
''', "path rules: D0 (50.0 > 49) and D3 (52.86 > 52) must be reported")
go("e10b_fromto_across_resistor", '''(version 1)
(rule "span_the_resistor"
  (condition "A.fromTo('J1-13', 'J2-13')")
  (constraint length (max 1mm)))
(rule "seg_a"
  (condition "A.fromTo('J1-13', 'R1-1')")
  (constraint length (max 1mm)))
(rule "seg_b"
  (condition "A.fromTo('R1-2', 'J2-13')")
  (constraint length (max 1mm)))
''', "J1-13 -> R1.1 is /CLK2_A (3.2 mm), R1.2 -> J2-13 is /CLK2_B (45.2 mm); can one rule span both?")
go("e10d_branch_net_whole_vs_path", '''(version 1)
(rule "whole_net"
  (condition "A.NetName == '/TBR'")
  (constraint length (max 1mm)))
''', "/TBR has a 5 mm stub: whole-net rule sums all copper (expect 55.0)")
go("e10e_branch_net_path_only", '''(version 1)
(rule "path_only"
  (condition "A.fromTo('J1-16', 'J2-16')")
  (constraint length (max 1mm)))
''', "same net, fromTo J1-16 -> J2-16: stub excluded? (expect 50.0 if path only)")
go("e10c_fromto_group_skew", '''(version 1)
(rule "path_skew_all_rows"
  (condition "A.fromTo('J1-*', 'J2-*') && A.NetName != '/SDRAM_D7'")
  (constraint skew (max 4mm)))
''', "skew over all J1-*/J2-* paths (D7 excluded); reference = longest")
