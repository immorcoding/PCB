"""PROTOTYPE (issue 21): net lengths, two ways.

geometric(B)   fast, no kicad-cli: per net the sum of segments and arcs per layer, plus the height of each
               via between the two layers its tracks are on (board.VIA_H). Used by the fast mode and by the
               tuner while it works.
probe(vdir)    KiCad's own number (the probe-rule method of the length-tuning prototype): the board is
               copied to a temp folder next to a rule file holding only `length (max 0.001mm)` with the
               condition of the project's length rule; kicad-cli then reports every matched net with the
               length it measured. This is the number every table uses; a full build compares the two.
"""
import collections, math, os, re, shutil, subprocess, tempfile
import pcbnew
from board import via_height
from common import CLI, NAME, LNUM, Lp, mm, ROOT


def geometric(B, prefix="/FMC_"):
    """{net (no slash): {"length", "track", "via_mm", "vias", "arcs", "layers": {L1: mm, ...}}}"""
    g = collections.defaultdict(lambda: {"layers": collections.defaultdict(float), "vias": 0, "arcs": 0, "via_mm": 0.0})
    ends = collections.defaultdict(lambda: collections.defaultdict(set))   # net -> rounded xy -> layers
    vias = collections.defaultdict(list)
    for t in B.GetTracks():
        n = t.GetNetname()
        if not n.startswith(prefix):
            continue
        n = n.lstrip("/")
        if t.Type() == pcbnew.PCB_VIA_T:
            g[n]["vias"] += 1; vias[n].append(Lp(t.GetPosition()))
            continue
        l = LNUM[t.GetLayer()]
        g[n]["layers"][l] += mm(t.GetLength()); g[n]["arcs"] += t.Type() == pcbnew.PCB_ARC_T
        for p in (t.GetStart(), t.GetEnd()):
            q = Lp(p); ends[n][(round(q[0], 4), round(q[1], 4))].add(l)
    out = {}
    for n, d in g.items():
        for v in vias[n]:
            ls = sorted(ends[n].get((round(v[0], 4), round(v[1], 4)), ()))
            if len(ls) >= 2:
                d["via_mm"] += via_height(ls[0], ls[-1])
        tr = sum(d["layers"].values())
        out[n] = {"length": tr + d["via_mm"], "track": tr, "via_mm": d["via_mm"], "vias": d["vias"], "arcs": d["arcs"],
                  "layers": {l: round(v, 4) for l, v in sorted(d["layers"].items())}}
    return out


def length_rules(dru_text):
    """[(rule name, condition clause text)] of every rule that has a length constraint."""
    out = []
    for m in re.finditer(r'\(rule\s+"([^"]+)"(.*?)(?=\n\(rule|\Z)', dru_text, re.S):
        if re.search(r"\(constraint\s+length\b", m.group(2)):
            c = re.search(r'\(condition\s+"[^"]*"\)', m.group(2))
            out.append((m.group(1), c.group(0) if c else ""))
    return out


def _run_probe(vdir, rules):
    """{rule: {net: mm}} for the given [(name, condition)] rules, all in ONE rule file (a later length rule
    with the same condition replaces an earlier one, so pass one rule at a time to test each)."""
    text = "(version 1)\n" + "".join('(rule "%s"\n  %s\n  (constraint length (max 0.001mm)))\n' % r for r in rules)
    os.makedirs(os.path.join(ROOT, "out", "_tmp"), exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="probe_", dir=os.path.join(ROOT, "out", "_tmp"))
    try:
        for ext in (".kicad_pcb", ".kicad_pro"):
            shutil.copy(os.path.join(vdir, NAME + ext), os.path.join(tmp, NAME + ext))
        open(os.path.join(tmp, NAME + ".kicad_dru"), "w", encoding="utf-8").write(text)
        rpt = os.path.join(tmp, "o.rpt")
        subprocess.run([CLI, "pcb", "drc", "--severity-all", "--units", "mm", "-o", rpt, os.path.join(tmp, NAME + ".kicad_pcb")], capture_output=True)
        lines = open(rpt, encoding="utf-8", errors="replace").read().splitlines()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    got = {r[0]: {} for r in rules}
    cur = None
    for line in lines:                                      # the wording is localised: key on code, Rule: line, numbers
        m = re.match(r"^\[(\w+)\]: (.*)$", line)
        if m:
            cur = {"code": m.group(1), "nums": [float(x) for x in re.findall(r"(-?\d+(?:\.\d+)?) mm", m.group(2))]}
            continue
        m = re.match(r"^\s+Rule: (.*?); \w+\s*$", line)
        if m and cur:
            cur["rule"] = m.group(1)
            continue
        m = re.search(r"\[(/[^\]]*)\]", line) if line.startswith("    @") else None
        if m and cur and cur["code"] == "length_out_of_range" and cur.get("rule") in got:
            got[cur["rule"]][m.group(1).lstrip("/")] = cur["nums"][-1]
    return got


def probe(vdir):
    """({net: length mm as KiCad's DRC measures it}, {rule name: number of nets it matched}).
    Every length rule of the project's rule file is probed on its own, so "matched 0 nets" really means
    the condition is wrong (and not that a later rule replaced it)."""
    rules = length_rules(open(os.path.join(vdir, NAME + ".kicad_dru"), encoding="utf-8").read())
    lengths, matched = {}, {}
    seen = {}
    for name, cond in rules:
        if cond not in seen:
            seen[cond] = _run_probe(vdir, [(name, cond)])[name]
        matched[name] = len(seen[cond])
        if len(seen[cond]) > len(lengths):
            lengths = seen[cond]
    return lengths, matched
