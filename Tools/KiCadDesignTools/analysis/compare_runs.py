"""Compare the reports of two builds of a board (two out/ trees), number by number.

    python -m Tools.KiCadDesignTools.analysis.compare_runs <out A> <out B> [--json OUT] [--tol 1e-4] [--show N] [--report-only]

<out A> / <out B> are the folders the build steps wrote into (each holding rules/, sch/, route2/, finish/ ... as far as
they were run). What is compared, where both runs have the file:

  route2/<group>/metrics.json   per net: DRC length, via count; the group's DRC counts by type, unconnected, track_shape
                                counts, built copper, tuning shortfalls, findings, verdict
  */drc.json, finish/drc_*.json DRC items by type, unconnected, schematic parity by type
  measure.json, slots*.json, place_check.json, escape_*.json, pieces_*.json, power*_sites.json
                                every number and string in the file (paths, timings and the board name left out)
  pour_islands.txt, canary.txt, rules_fixture.txt (first line and FAIL lines), sch_check.txt, orphans.txt, table.txt,
  drc_summary.txt, stitch*.txt, silk.txt, len_rules.txt
                                the lines, with times ("12 s", "build 3.4 s") taken out

Numbers are equal when they differ by no more than --tol. Prints every difference as "key: A -> B" (up to --show per
file, default 40) and a count per file.

Worse (PROC-4): an item with a direction (direction() below) that moved the wrong way is listed first, in a section
"变差 / worse" (file, key, A -> B), and marked "!" in its file's list. Lower is better: unconnected items and paths
that are not pad to pad, DRC and schematic-parity counts by type, track_shape defect counts (not segments, arcs),
busroute geometry findings, findings and hard findings, the vias of each net of a group with a via limit, the spread
of a length group (not a reference group, whose window is to the clock), tuning shortfalls, decoupling parts over the
limit and the other placement problem lists (overlap, outside, holes, keep-outs, under, parked, spacing), pour pieces
without a via (pieces_*.json bucket 0, pour_islands.txt), rules that match nothing (dru_match.json), unconnected
copper of the copper measure. Higher is better: nets built (busroute built.nets), a group's verdict ok, balls with a
way out (escape_*.json: every status but blocked). Everything else (lengths, positions, slot lengths, text lines) is
a plain measurement: listed when it differs, never "worse". A count missing on one side counts as 0.

Exit code 1 = something got worse (0 with --report-only), 0 = nothing worse (differences are listed), 2 = nothing to
compare.
"""
import argparse, collections, glob, json, os, re, sys

SKIP_KEYS = {"board", "file", "routes_file", "seconds", "build_seconds", "sources", "path", "out", "json", "pcb",
             "kicad_pro", "kicad_dru", "date", "time", "source", "date_iso", "kicad_version", "host"}
TIME_RE = re.compile(r"\b\d+(?:\.\d+)?\s*s\b|\b\d+(?:\.\d+)? seconds\b|\d+m\d+(?:\.\d+)?s")
PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\s,;'\"]*|/[a-z]/[^\s,;'\"]*")
JSON_FILES = ["measure.json", "slots.json", "slots_l5.json", "place_check.json", "escape_bga.json", "escape_parts.json",
              "pieces_before.json", "pieces_after.json", "power_sites.json", "power_bga_sites.json", "layout_probe.json",
              "length_groups.json", "dru_match.json"]
TEXT_FILES = ["pour_islands.txt", "canary.txt", "sch_check.txt", "orphans.txt", "table.txt", "drc_summary.txt",
              "stitch.txt", "stitch2.txt", "silk.txt", "len_rules.txt", "pieces_before.txt", "pieces_after.txt",
              "dru_match.txt", "slots.txt", "slots_l5.txt", "measure.txt", "escape.txt", "sketch_check.txt"]


def flat(obj, pre="", out=None):
    out = {} if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in SKIP_KEYS or k.endswith("_seconds"):
                continue
            flat(v, "%s.%s" % (pre, k) if pre else str(k), out)
    elif isinstance(obj, list):
        out[pre + ".#"] = len(obj)
        for i, v in enumerate(obj):
            flat(v, "%s[%d]" % (pre, i), out)
    elif isinstance(obj, str):
        out[pre] = PATH_RE.sub("<path>", obj)
    else:
        out[pre] = obj
    return out


def metrics_probe(m):
    """The numbers of one busroute group build."""
    r = {}
    L = m.get("length") or {}
    for n, v in sorted((L.get("drc") or {}).items()):
        r["len_drc." + n] = v
    for n, v in sorted((L.get("nets") or {}).items()):
        r["vias." + n] = v.get("vias")
        r["len_geom." + n] = v.get("length")
    c = m.get("connectivity") or {}
    for k in ("paths_not_pad_to_pad", "open_ends_listed", "drc_unconnected_group", "drc_unconnected_board"):
        r["conn." + k] = c.get(k)
    for k, v in sorted((c.get("drc_by_type_group") or {}).items()):
        r["drc_group." + k] = v
    for k, v in sorted((c.get("drc_by_type_board") or {}).items()):
        r["drc_board." + k] = v
    ts = ((m.get("shape") or {}).get("track_shape") or {})
    for k, v in sorted(ts.items()):
        if k not in ("lines", "group"):
            r["track_shape." + k] = v
    for k, v in sorted(((m.get("shape") or {}).get("geometry") or {}).items()):
        r["geometry." + k] = v
    for k, v in sorted((m.get("built") or {}).items()):
        r["built." + k] = v
    for k, v in sorted(((m.get("tuning") or {}).get("missing") or {}).items()):
        r["tuning_missing." + k] = v
    v = m.get("vias") or {}
    for k in ("max", "total", "stitching"):
        r["via_stats." + k] = v.get(k)
    r["via_limit"] = v.get("limit")                       # vias.<net> count as "lower is better" when there is one
    refs = {g for g, t in ((m.get("tuning") or {}).get("groups") or {}).items() if (t or {}).get("kind") == "ref"}
    for g, t in sorted((L.get("groups") or {}).items()):  # a reference group's spread is its window to the clock
        if isinstance(t, dict) and t.get("spread") is not None:
            r[("span." if g in refs else "spread.") + g] = t["spread"]
    r["findings"] = len(m.get("findings") or [])
    r["hard_findings"] = m.get("hard_findings")
    r["ok"] = m.get("ok")
    return r


def drc_probe(d):
    r = {}
    for k, v in sorted(collections.Counter(x["type"] for x in d.get("violations", [])).items()):
        r["violations." + k] = v
    r["unconnected"] = len(d.get("unconnected_items", []))
    for k, v in sorted(collections.Counter(x["type"] for x in d.get("schematic_parity", [])).items()):
        r["parity." + k] = v
    return r


def text_probe(path):
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    if os.path.basename(path) == "rules_fixture.txt":
        lines = lines[:1] + [l for l in lines if l.startswith("FAIL")]
    out = {}
    for i, l in enumerate(l for l in lines if l.strip()):
        out["line%04d" % i] = PATH_RE.sub("<path>", TIME_RE.sub("<t>", l.rstrip()))
    return out


def collect(root):
    """{relative file: {key: value}} for every file this tool knows in the out tree."""
    res = {}
    for p in sorted(glob.glob(os.path.join(root, "**", "metrics.json"), recursive=True)):
        try:
            res[os.path.relpath(p, root)] = metrics_probe(json.load(open(p, encoding="utf-8")))
        except Exception as e:
            res[os.path.relpath(p, root)] = {"error": str(e)}
    for p in sorted(glob.glob(os.path.join(root, "**", "drc*.json"), recursive=True)):
        rel = os.path.relpath(p, root)
        if os.path.basename(p) == "drc_summary.json":
            continue
        try:
            res[rel] = drc_probe(json.load(open(p, encoding="utf-8")))
        except Exception as e:
            res[rel] = {"error": str(e)}
    for name in JSON_FILES:
        for p in sorted(glob.glob(os.path.join(root, "**", name), recursive=True)):
            try:
                d = json.load(open(p, encoding="utf-8"))
                res[os.path.relpath(p, root)] = dict(flat(d), **derived(name, d))
            except Exception as e:
                res[os.path.relpath(p, root)] = {"error": str(e)}
    for name in TEXT_FILES + ["rules_fixture.txt"]:
        for p in sorted(glob.glob(os.path.join(root, "**", name), recursive=True)):
            res[os.path.relpath(p, root)] = text_probe(p)
            if name == "pour_islands.txt":
                for l in open(p, encoding="utf-8", errors="replace"):
                    m = POUR_RE.match(l.strip())
                    if m:
                        res[os.path.relpath(p, root)]["without_via." + m.group(1)] = int(m.group(2))
    return res


POUR_RE = re.compile(r"(\S+): \d+ pieces?, (\d+) without a via")


def derived(name, d):
    """Counts a JSON report holds only as lists: balls with a way out per package (escape_*.json), rules that match
    nothing (dru_match.json)."""
    out = {}
    if name.startswith("escape_") and isinstance(d, dict):
        for ref, balls in d.items():
            if isinstance(balls, dict) and balls and all(isinstance(b, dict) and "status" in b for b in balls.values()):
                out["escaped." + ref] = sum(1 for b in balls.values() if b["status"] != "blocked")
    if name == "dru_match.json" and isinstance(d, dict) and isinstance(d.get("rules"), list):
        out["empty_rules"] = sum(1 for r in d["rules"] if not r.get("matched"))
    return out


# ---------------------------------------------------------------------------------------------------- direction
LOWER, HIGHER = "lower", "higher"
TS_DEFECTS = {"off-grid", "staircase", "sharp", "crowded", "tiny", "arc-joint"}
PLACE_LISTS = {"outside", "overlap", "no_courtyard", "hole", "keepout", "under"}
COUNT_HEADS = {"conn", "drc_group", "drc_board", "geometry", "track_shape", "tuning_missing", "violations", "parity",
               "without_via", "findings", "hard_findings", "unconnected", "empty_rules"}


def direction(f, key, x, y):
    """LOWER / HIGHER when a smaller / larger value of `key` in report file `f` is better, None for a plain
    measurement. x, y: both runs' values of that file (a group's via limit)."""
    name = os.path.basename(f)
    head = key.split(".", 1)[0]
    if name == "metrics.json":
        if head in ("conn", "drc_group", "drc_board", "geometry", "tuning_missing", "spread") or key in ("findings", "hard_findings"):
            return LOWER
        if head == "track_shape":
            return LOWER if key.split(".", 1)[1] in TS_DEFECTS else None
        if head == "vias":
            return LOWER if x.get("via_limit") is not None or y.get("via_limit") is not None else None
        if key in ("built.nets", "ok"):
            return HIGHER
        return None
    if name.startswith("drc") and name.endswith(".json"):
        return LOWER if head in ("violations", "parity", "unconnected") else None
    if name == "place_check.json":
        if re.fullmatch(r"decoupling\.per_ic\.[^.]+\.over\.#", key) or key in ("parts.parked.#", "spacing.count"):
            return LOWER
        if key == "parts.placed":
            return HIGHER
        return LOWER if key.endswith(".#") and key[:-2] in PLACE_LISTS else None
    if name.startswith("pieces_") and name.endswith(".json"):
        return LOWER if re.fullmatch(r"[^.]+\.0", key) else None
    if name == "pour_islands.txt":
        return LOWER if head == "without_via" else None
    if name == "dru_match.json":
        return LOWER if key == "empty_rules" else None
    if name.startswith("escape_") and name.endswith(".json"):
        return HIGHER if head == "escaped" else None
    if name == "measure.json":
        return LOWER if key in ("drc.unconnected_copper", "drc.unconnected_total") or re.fullmatch(r"zones\[\d+\]\.unconnected_pieces", key) else None
    return None


def worse(f, key, p, q, x, y, tol):
    """True when the value moved the wrong way from p (run A) to q (run B)."""
    d = direction(f, key, x, y)
    if d is None:
        return False
    if p is None or q is None:                            # a count missing on one side is 0; anything else: no verdict
        if not (key.split(".", 1)[0] in COUNT_HEADS or key.endswith(".#") or os.path.basename(f).startswith("pieces_")):
            return False
        p, q = p or 0, q or 0
    if isinstance(p, bool) or isinstance(q, bool):
        p, q = bool(p), bool(q)
        return (p and not q) if d == HIGHER else (q and not p)
    if not isinstance(p, (int, float)) or not isinstance(q, (int, float)):
        return False
    return q > p + tol if d == LOWER else q < p - tol


def same(x, y, tol):
    if isinstance(x, bool) or isinstance(y, bool):
        return x == y
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        return abs(x - y) <= tol
    return x == y


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--json")
    ap.add_argument("--tol", type=float, default=1e-4)
    ap.add_argument("--show", type=int, default=40)
    ap.add_argument("--report-only", action="store_true", help="exit 0 even when something got worse")
    a = ap.parse_args(argv)
    A, B = collect(a.a), collect(a.b)
    if not A and not B:
        print("nothing to compare in %s / %s" % (a.a, a.b))
        return 2
    report, ndiff, bad, body = {}, 0, [], []
    for f in sorted(set(A) | set(B)):
        if f not in A or f not in B:
            body.append("%-48s only in %s" % (f, "A" if f in A else "B"))
            report[f] = {"only_in": "A" if f in A else "B"}
            continue
        x, y = A[f], B[f]
        rows = [(k, x.get(k), y.get(k)) for k in sorted(set(x) | set(y)) if not same(x.get(k), y.get(k), a.tol)]
        wr = [(k, p, q) for k, p, q in rows if worse(f, k, p, q, x, y, a.tol)]
        bad += [(f, k, p, q, direction(f, k, x, y)) for k, p, q in wr]
        wk = {k for k, _, _ in wr}
        report[f] = {"keys": len(set(x) | set(y)), "differences": [[k, p, q] for k, p, q in rows], "worse": [[k, p, q] for k, p, q in wr]}
        body.append("%-48s %5d values, %d different%s" % (f, len(set(x) | set(y)), len(rows), ", %d worse" % len(wr) if wr else ""))
        for k, p, q in rows[:a.show]:
            body.append("  %s %s: %r -> %r" % ("!" if k in wk else " ", k, p, q))
        if len(rows) > a.show:
            body.append("    ... %d more" % (len(rows) - a.show))
        ndiff += len(rows)
    print("compare_runs: A = %s\n              B = %s" % (a.a, a.b))
    print("变差 / worse: %d" % len(bad))
    for f, k, p, q, d in bad:
        print("  %s  %s: %r -> %r  (%s is better)" % (f, k, p, q, d))
    print("\n".join(body))
    if a.json:
        json.dump(report, open(a.json, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    files_one_side = sum(1 for f in report if "only_in" in report[f])
    print("result: %d differing values in %d files, %d worse; %d files on one side only"
          % (ndiff, sum(1 for f in report if report[f].get("differences")), len(bad), files_one_side))
    return 1 if bad and not a.report_only else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
