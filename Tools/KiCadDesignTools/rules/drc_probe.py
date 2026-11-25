"""Shared helpers: run kicad-cli DRC on a copy of a board with a chosen rule file, and read .kicad_dru text.

Used by dru_match.py (does every rule match something?) and len_rules.py (DRC as the length gauge).
The board, its .kicad_pro and the rule text are copied to a temp folder, so the project is never touched.
Report wording is localised; only violation types, quoted rule names and numbers are parsed.
"""
import json, os, re, shutil, tempfile

from Tools.KiCadDesignTools.core import heavy


def run_drc(board_path, dru_text=None, refill=False):
    """DRC report (dict, kicad-cli JSON) of the board with `dru_text` as its rule file
    (None = the project's own .kicad_dru)."""
    stem = os.path.splitext(os.path.abspath(board_path))[0]
    tmp = tempfile.mkdtemp(prefix="drc_probe_")
    try:
        for ext in (".kicad_pcb", ".kicad_pro"):
            if os.path.isfile(stem + ext):
                shutil.copy(stem + ext, os.path.join(tmp, "b" + ext))
        if dru_text is None and os.path.isfile(stem + ".kicad_dru"):
            dru_text = open(stem + ".kicad_dru", encoding="utf-8").read()
        if dru_text is not None:
            open(os.path.join(tmp, "b.kicad_dru"), "w", encoding="utf-8", newline="\n").write(dru_text)
        rpt = os.path.join(tmp, "drc.json")
        args = ["pcb", "drc", "--severity-all", "--units", "mm", "--format", "json", "-o", rpt]
        # a non-zero exit or no report: heavy.HeavyError (a RuntimeError), as the missing report was before
        heavy.kicad_cli(*args + (["--refill-zones"] if refill else []) + [os.path.join(tmp, "b.kicad_pcb")], outputs=[rpt])
        return json.load(open(rpt, encoding="utf-8"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def rule_of(violation):
    """Name of the custom rule a violation cites, or None (board setting / net class)."""
    m = re.search(r"'([^']+)'", violation["description"])
    if not m and violation["type"].startswith("diff_pair"):      # these print the rule name bare: "(eth_gap min gap ..."
        m = re.search(r"\(([A-Za-z_]\w*) ", violation["description"])
    return m.group(1) if m else None


def numbers(violation):
    """All 'N mm' numbers of the description, in order (limit(s) first, the actual value last)."""
    return [float(x) for x in re.findall(r"(-?\d+(?:\.\d+)?) mm", violation["description"])]


def net_of(item):
    """Net name from an item description like 'Track [NET] on F.Cu' (any language)."""
    m = re.search(r"\[([^\]]*)\]", item["description"])
    return m.group(1) if m else None


def strip_comments(dru_text):
    return "\n".join(l for l in dru_text.splitlines() if not l.lstrip().startswith("#"))


def parse_rules(dru_text):
    """[(name, condition or None, [constraint names])] in file order."""
    out = []
    for m in re.finditer(r'\(rule\s+"([^"]+)"(.*?)(?=\n\(rule\s|\Z)', strip_comments(dru_text), re.S):
        c = re.search(r'\(condition\s+"([^"]*)"\)', m.group(2))
        out.append((m.group(1), c.group(1) if c else None, re.findall(r"\(constraint\s+(\w+)", m.group(2))))
    return out


def measure_lengths(board_path, conditions):
    """{key: {net: length mm}} for a dict {key: rule condition}; lengths as KiCad's DRC counts them.
    Each condition gets a probe rule `length (max 0.001mm)`; of several probes matching the same net only
    the last one reports (later length rules win), so conditions should not overlap."""
    keys = list(conditions)
    text = "(version 1)\n" + "".join('(rule "probe_%d"\n  (condition "%s")\n  (constraint length (max 0.001mm)))\n'
                                     % (i, conditions[k]) for i, k in enumerate(keys))
    got = {k: {} for k in keys}
    for v in run_drc(board_path, text)["violations"]:
        r = rule_of(v)
        if v["type"] == "length_out_of_range" and r and r.startswith("probe_"):
            got[keys[int(r[6:])]][net_of(v["items"][0])] = numbers(v)[-1]
    return got
