"""Does every rule of a .kicad_dru match at least one object on the board? (RUL-2)

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.rules.dru_match <board>.kicad_pcb [--json out.json]

A misspelt net class, net name, rule area or function leaves the rule file loaded (the canary in
dru_canary.py stays green) while that one rule matches nothing. This copies every rule's condition into
a probe rule whose constraint is an assertion that always fails, runs kicad-cli DRC on a copy of the
board once per rule, and counts the objects each probe reports.

Limits, stated in the output:
  - A rule without a condition applies to everything; it is listed as "unconditional", not probed.
  - An assertion sees one object, so clauses that mention B are dropped from the probe when the condition
    is a plain chain of &&; the A side is proven, the pairing is not. Other uses of B are "not probed".
  - Matching objects is not the same as measuring something: a length rule also needs routed tracks
    (the length table reports that).
Exit code: 0 = no empty rule, 1 = at least one rule matches nothing, 2 = the board has no objects (nothing can match).
A condition with a syntax error disables its own probe file and so shows up as EMPTY.
"""
import json, os, re, sys
from Tools.KiCadDesignTools.rules import drc_probe


def split_and(cond):
    """Top-level && clauses of a condition, or None if it cannot be split safely."""
    parts, depth, cur, i, quote = [], 0, "", 0, False
    while i < len(cond):
        ch = cond[i]
        if ch == "'":
            quote = not quote
        if not quote:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif depth == 0 and cond.startswith("&&", i):
                parts.append(cur.strip()); cur = ""; i += 2
                continue
            elif depth == 0 and cond.startswith("||", i):
                return None
        cur += ch; i += 1
    return parts + [cur.strip()]


def probe_condition(cond):
    """(condition to probe or None, note)"""
    if not re.search(r"\bB\.", cond):
        return cond, ""
    parts = split_and(cond)
    if parts is None:
        return None, "not probed (B inside ||)"
    keep = [p for p in parts if not re.search(r"\bB\.", p)]
    if not keep:
        return None, "not probed (only B clauses)"
    return " && ".join(keep), "A side only"


def match(board_path):
    """[{rule, constraints, matched (int or None), note}] and whether probing works at all on this board.
    One DRC run per rule (in parallel): of several assertion rules that match the same object KiCad
    reports only one, so the probes cannot share a rule file."""
    from concurrent.futures import ThreadPoolExecutor
    dru = os.path.splitext(board_path)[0] + ".kicad_dru"
    rules = drc_probe.parse_rules(open(dru, encoding="utf-8").read())
    probe = '(version 1)\n(rule "probe"\n%s  (constraint assertion "A.Type == \'no_such_type\'"))\n'
    rows, jobs = [], [probe % ""]            # job 0: no condition, fires on every object = probing works
    for name, cond, cons in rules:
        row = {"rule": name, "constraints": cons, "matched": None, "note": "", "job": None}
        if cond is None:
            row["note"] = "unconditional"
        else:
            pc, row["note"] = probe_condition(cond)
            if pc is not None:
                row["job"] = len(jobs)
                jobs.append(probe % ('  (condition "%s")\n' % pc))
        rows.append(row)
    count = lambda text: sum(v["type"] == "assertion_failure" for v in drc_probe.run_drc(board_path, text)["violations"])
    # One DRC at a time by default: every kicad-cli DRC is multi-threaded and takes over 1 GB on a routed board;
    # eight of them at once hard-reset the PC twice on 2026-11-23. DRU_MATCH_JOBS raises it for small boards.
    with ThreadPoolExecutor(max_workers=max(1, int(os.environ.get("DRU_MATCH_JOBS", "1")))) as ex:
        counts = list(ex.map(count, jobs))
    for row in rows:
        j = row.pop("job")
        if j is not None:
            row["matched"] = counts[j]
    return rows, counts[0] > 0


def main(argv):
    board = argv[0]
    rows, loaded = match(board)
    sys.stdout.reconfigure(encoding="utf-8")
    empty = [r for r in rows if r["matched"] == 0]
    for r in rows:
        n = "-" if r["matched"] is None else str(r["matched"])
        print("%-22s %7s  %s%s" % (r["rule"], n, "EMPTY  " if r["matched"] == 0 else "", r["note"]))
    if "--json" in argv:
        json.dump({"loaded": loaded, "rules": rows}, open(argv[argv.index("--json") + 1], "w", encoding="utf-8"), indent=1)
    if not loaded:
        print("FAIL: an unconditional probe matched nothing: the board has no objects to match")
        return 2
    print("%d rules, %d probed, %d empty%s" % (len(rows), sum(r["matched"] is not None for r in rows), len(empty),
                                               ": " + ", ".join(r["rule"] for r in empty) if empty else ""))
    return 1 if empty else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
