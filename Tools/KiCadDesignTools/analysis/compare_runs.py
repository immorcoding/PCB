"""Compare the reports of two builds of a board (two out/ trees), number by number.

    python -m Tools.KiCadDesignTools.analysis.compare_runs <out A> <out B> [--json OUT] [--tol 1e-4] [--show N]

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
file, default 40) and a count per file; exit code 0 = no difference, 1 = differences, 2 = nothing to compare.
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
                res[os.path.relpath(p, root)] = flat(json.load(open(p, encoding="utf-8")))
            except Exception as e:
                res[os.path.relpath(p, root)] = {"error": str(e)}
    for name in TEXT_FILES + ["rules_fixture.txt"]:
        for p in sorted(glob.glob(os.path.join(root, "**", name), recursive=True)):
            res[os.path.relpath(p, root)] = text_probe(p)
    return res


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
    a = ap.parse_args(argv)
    A, B = collect(a.a), collect(a.b)
    if not A and not B:
        print("nothing to compare in %s / %s" % (a.a, a.b))
        return 2
    report, ndiff = {}, 0
    print("compare_runs: A = %s\n              B = %s" % (a.a, a.b))
    for f in sorted(set(A) | set(B)):
        if f not in A or f not in B:
            print("%-48s only in %s" % (f, "A" if f in A else "B"))
            report[f] = {"only_in": "A" if f in A else "B"}
            continue
        x, y = A[f], B[f]
        rows = [(k, x.get(k), y.get(k)) for k in sorted(set(x) | set(y)) if not same(x.get(k), y.get(k), a.tol)]
        report[f] = {"keys": len(set(x) | set(y)), "differences": [[k, p, q] for k, p, q in rows]}
        print("%-48s %5d values, %d different" % (f, len(set(x) | set(y)), len(rows)))
        for k, p, q in rows[:a.show]:
            print("    %s: %r -> %r" % (k, p, q))
        if len(rows) > a.show:
            print("    ... %d more" % (len(rows) - a.show))
        ndiff += len(rows)
    if a.json:
        json.dump(report, open(a.json, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    files_one_side = sum(1 for f in report if "only_in" in report[f])
    print("result: %d differing values in %d files; %d files on one side only"
          % (ndiff, sum(1 for f in report if report[f].get("differences")), files_one_side))
    return 1 if ndiff else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
