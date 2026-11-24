"""Regression benchmark for rules/dru_match.py, rules/len_rules.py and rules/dru_canary.py.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.tests.drc_tools.check

Builds a four-net board in a temp directory with a rule file that has one misspelt net name, and
expects: the canary says the file is loaded; dru_match names exactly the misspelt rule as empty;
len_rules writes a window of 9.5 .. 14.5 mm around a 12 mm clock (two pieces, 2 + 10 mm, summed) and
DRC then reports exactly the one net outside it; a fixed skew rule (max 2 mm over D0 12 / D1 15 mm) is written
as given and DRC reports the shorter net; --check says the block is current, and stale after
the clock is made longer. Prints one line, `OK ...` or `FAIL ...`; exit code 0 = pass.
"""
import os, shutil, subprocess, sys, tempfile
import pcbnew
from pcbnew import VECTOR2I, FromMM as mm

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
from Tools.KiCadDesignTools.rules import drc_probe, dru_match, len_rules

DRU = """(version 1)
(rule "corner_angle"
  (constraint track_angle (min 135)))
(rule "data_width"
  (condition "A.Type == 'Track' && A.NetName == 'D*'")
  (constraint track_width (min 0.1mm)))
(rule "typo_net"
  (condition "A.NetName == 'CLOCK'")
  (constraint length (max 60mm)))
(rule "pair_rule"
  (condition "A.Type != 'Zone' && B.Type != 'Zone' && A.NetName == 'CLK'")
  (constraint clearance (min 0.1mm)))
%s
# (nothing generated yet)
%s
""" % (len_rules.BEGIN, len_rules.END)
GROUPS = ('{"groups": [{"rule": "d_window", "members": "A.NetName == \'D*\'", "ref": ["CLK", "CLK_R"], "lo": -2.5, "hi": 2.5}], "sums": [], '
          '"fixed": [{"rule": "d_spread", "members": "A.NetName == \'D*\'", "constraint": "skew (max 2mm)", "why": "bench"}]}')


def board(path, clk_r):
    b = pcbnew.CreateEmptyBoard()
    for i, (name, length) in enumerate((("CLK", 2.0), ("CLK_R", clk_r), ("D0", 12.0), ("D1", 15.0))):
        n = pcbnew.NETINFO_ITEM(b, name); b.Add(n)
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(VECTOR2I(0, mm(i))); t.SetEnd(VECTOR2I(mm(length), mm(i))); t.SetWidth(mm(0.2)); t.SetLayer(pcbnew.F_Cu); t.SetNet(n)
        b.Add(t)
    pcbnew.SaveBoard(path, b)


def run(script, *args):
    r = subprocess.run([sys.executable, "-m", "Tools.KiCadDesignTools.rules." + script[:-3]] + list(args), cwd=REPO, capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout


def main():
    tmp = tempfile.mkdtemp(prefix="drc_tools_")
    pcb = os.path.join(tmp, "t.kicad_pcb")
    fails = []
    def want(ok, text):
        if not ok:
            fails.append(text)
    try:
        board(pcb, 10.0)
        open(os.path.join(tmp, "t.kicad_dru"), "w", encoding="utf-8", newline="\n").write(DRU)
        open(os.path.join(tmp, "length_groups.json"), "w", encoding="utf-8").write(GROUPS)
        code, out = run("dru_canary.py", pcb)
        want(code == 0, "canary: " + out)
        rows, loaded = dru_match.match(pcb)
        got = {r["rule"]: (r["matched"], r["note"]) for r in rows}
        want(loaded, "dru_match: unconditional probe matched nothing")
        want(got == {"corner_angle": (None, "unconditional"), "data_width": (2, ""), "typo_net": (0, ""),
                     "pair_rule": (1, "A side only")}, "dru_match rows: %r" % got)
        code, out = run("dru_match.py", pcb)
        want(code == 1 and "1 empty: typo_net" in out, "dru_match exit %d: %s" % (code, out))
        code, out = run("len_rules.py", pcb)
        text = open(os.path.join(tmp, "t.kicad_dru"), encoding="utf-8").read()
        want(code == 0 and "(constraint length (min 9.5000mm) (opt 12.0000mm) (max 14.5000mm))" in text, "len_rules block: %s\n%s" % (out, text[-400:]))
        want('(rule "d_spread"\n  (condition "A.NetName == \'D*\'")\n  (constraint skew (max 2mm)))' in text, "fixed rule not written:\n%s" % text[-400:])
        drc = drc_probe.run_drc(pcb)
        bad = sorted(drc_probe.net_of(v["items"][0]) for v in drc["violations"] if v["type"] == "length_out_of_range")
        want(bad == ["D1"], "nets outside the window: %r" % bad)
        skew = sorted(drc_probe.net_of(v["items"][0]) for v in drc["violations"] if v["type"] == "skew_out_of_range")
        want(skew == ["D0"], "fixed skew rule (D0 12 mm, D1 15 mm, max 2 mm): skew violations on %r" % skew)
        code, out = run("len_rules.py", pcb, "--check")
        want(code == 0, "--check on a current block: exit %d %s" % (code, out))
        board(pcb, 11.0)
        code, out = run("len_rules.py", pcb, "--check")
        want(code == 1, "--check after the clock grew: exit %d %s" % (code, out))
    finally:
        if fails:
            print("FAIL drc_tools (%d); temp dir kept: %s" % (len(fails), tmp))
            print("\n".join("  " + f for f in fails))
        else:
            shutil.rmtree(tmp, ignore_errors=True)
            print("OK drc_tools: canary, dru_match (1 empty rule found), len_rules (window 9.5..14.5 mm, fixed skew rule, stale check)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
