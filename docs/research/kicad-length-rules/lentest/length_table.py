"""Prototype: turn a project's .kicad_dru into a length table, using KiCad's own DRC as the measurer.

Two probe runs, because KiCad matches `length` rules only against other `length` rules and `skew`
rules only against other `skew` rules (a net can belong to one of each):
  length probe: every rule that has a `length` constraint -> same name / (layer) / (condition),
                constraint `length (max 0.001mm)`; every matched net is reported with its length.
  skew probe:   every rule that has a `skew` constraint   -> constraint `skew (max 0.0001mm)`;
                every group member except the longest is reported (with its length and the
                group's reference length = the longest member).
A rule that matched nothing is reported EMPTY -- that is how a typo in a net class / net name /
area name shows up (KiCad itself says nothing).  A skew rule with a single member also looks empty.

    D:\\KiCad\\bin\\python.exe -I length_table.py <board.kicad_pcb> [rules.kicad_dru]

The rules file defaults to the one next to the board.  Nothing is written next to the board.
"""
import os, re, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from parse_report import blocks, net_of

CLI = r"D:\KiCad\bin\kicad-cli.exe"


def top_level_rules(text):
    """[(name, body_text)] for each top-level (rule ...) -- paren balanced, '#' lines and strings aware."""
    out, depth, i, n = [], 0, 0, len(text)
    start = None
    while i < n:
        c = text[i]
        if c == "#" and (i == 0 or text[i - 1] == "\n"):
            i = text.find("\n", i)
            i = n if i < 0 else i
            continue
        if c in "\"'":
            j = text.find(c, i + 1)
            i = (n if j < 0 else j) + 1
            continue
        if c == "(":
            if depth == 0:
                start = i
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0 and start is not None:
                blk = text[start:i + 1]
                m = re.match(r"\(rule\s+(\"[^\"]*\"|'[^']*'|\S+)", blk)
                if m:
                    out.append((m.group(1).strip("\"'"), blk))
        i += 1
    return out


def clause(blk, key):
    m = re.search(r"\(%s\s" % key, blk)
    if not m:
        return None
    depth, i = 0, m.start()
    while i < len(blk):
        c = blk[i]
        if c in "\"'":
            j = blk.find(c, i + 1); i = (len(blk) if j < 0 else j) + 1; continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return blk[m.start():i + 1]
        i += 1
    return None


def probe_text(dru_text, kind):
    """kind = 'length' or 'skew'; returns (probe file text, rule names in order)"""
    limit = "(constraint length (max 0.001mm))" if kind == "length" else "(constraint skew (max 0.0001mm))"
    probes, names = ["(version 1)"], []
    for name, blk in top_level_rules(dru_text):
        if not re.search(r"\(constraint\s+%s\b" % kind, blk):
            continue
        parts = [f'(rule "{name}"']
        for key in ("layer", "condition"):
            c = clause(blk, key)
            if c:
                parts.append("  " + c)
        parts.append("  " + limit + ")")
        probes.append("\n".join(parts))
        names.append(name)
    return "\n".join(probes) + "\n", names


def drc(pcb, dru_text):
    stem = os.path.splitext(pcb)[0]
    tmp = tempfile.mkdtemp(prefix="lentable_")
    try:
        base = os.path.basename(stem)
        for ext in (".kicad_pcb", ".kicad_pro"):
            if os.path.exists(stem + ext):
                shutil.copy(stem + ext, os.path.join(tmp, base + ext))
        open(os.path.join(tmp, base + ".kicad_dru"), "w", encoding="utf-8").write(dru_text)
        out = os.path.join(tmp, "o.rpt")
        subprocess.run([CLI, "pcb", "drc", "--severity-all", "--units", "mm", "-o", out,
                        os.path.join(tmp, base + ".kicad_pcb")], capture_output=True)
        return open(out, encoding="utf-8", errors="replace").read()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(pcb, dru=None):
    pcb = os.path.abspath(pcb)
    dru = dru or os.path.splitext(pcb)[0] + ".kicad_dru"
    text = open(dru, encoding="utf-8").read()

    probe, names = probe_text(text, "length")
    rpt = drc(pcb, probe)
    got = {n: {} for n in names}
    for b in blocks(rpt):
        if b.code == "length_out_of_range" and b.rule in got:
            got[b.rule][net_of(b)] = b.numbers[-1]
    for n in names:
        rows = got[n]
        if not rows:
            print(f"[length] rule {n!r}: EMPTY -- matched no routed net (typo in the condition? net not routed?)")
            continue
        print(f"[length] rule {n!r}: {len(rows)} nets, longest {max(rows.values()):.4f}, "
              f"shortest {min(rows.values()):.4f}, spread {max(rows.values()) - min(rows.values()):.4f}")
        for net, ln in sorted(rows.items()):
            print(f"    {net:24s} {ln:10.4f}")

    probe, names = probe_text(text, "skew")
    rpt = drc(pcb, probe)
    got = {n: {} for n in names}
    ref = {}
    for b in blocks(rpt):
        if b.code == "skew_out_of_range" and b.rule in got:
            got[b.rule][net_of(b)] = b.numbers[3]       # max, skew, reference length, own length
            ref[b.rule] = b.numbers[2]
    for n in names:
        rows = got[n]
        if not rows:
            print(f"[skew]   rule {n!r}: EMPTY or single-member group -- nothing to compare")
            continue
        print(f"[skew]   rule {n!r}: {len(rows) + 1} members; reference (longest) length {ref[n]:.4f}; others:")
        for net, ln in sorted(rows.items()):
            print(f"    {net:24s} {ln:10.4f}   skew {ln - ref[n]:+.4f}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
