"""Regression benchmark for analysis/compare_runs.py (two builds' reports compared number by number, pure text).

    python -m Tools.KiCadDesignTools.tests.compare_runs.check

Two small out trees in a temp directory (a busroute group's metrics.json, a DRC report, a rule fixture report, a
table with a time and a path in it): the same numbers with other times, paths and timing keys compare equal; a DRC
type count, a net length beyond --tol, a fixture FAIL line and a file on one side only are reported; empty trees give
exit 2. Prints one line, `OK ...` or `FAIL ...` (details follow a FAIL); exit code 0 = pass. Nothing is written into
the repository.
"""
import contextlib, io, json, os, shutil, sys, tempfile

from Tools.KiCadDesignTools.analysis import compare_runs


def tree(root, length=24.5, drc_extra=0, fail_line=False, seconds=12, path="E:/x/out", extra_file=False):
    def w(rel, data):
        p = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))
    w("route/sdram/metrics.json", {
        "board": path + "/b.kicad_pcb", "build_seconds": seconds,
        "length": {"drc": {"FMC_D0": length, "FMC_D1": 24.0}, "nets": {"FMC_D0": {"vias": 2, "length": length}}},
        "connectivity": {"drc_unconnected_group": 0, "drc_by_type_group": {"track_dangling": 1}},
        "vias": {"max": 2, "total": 9}, "findings": [], "ok": True})
    w("finish/drc.json", {"violations": [{"type": "silk_over_copper"}] * (3 + drc_extra), "unconnected_items": [],
                          "schematic_parity": [{"type": "footprint_symbol_mismatch"}]})
    w("rules/rules_fixture.txt", "规则基准板：59 个用例，%d 项不符\nok   w01 默认类\n%s" % (
        1 if fail_line else 0, "FAIL w02 低于 0.1016\n" if fail_line else "ok   w02 低于 0.1016\n"))
    w("route/table.txt", "route step: %d s\nboard %s/b.kicad_pcb\nlane spread 0.6 mm\n" % (seconds, path))
    if extra_file:
        w("route/orphans.txt", "orphans: 0 item(s) owned by no group removed\n")


def run(*argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = compare_runs.main(list(argv))
    return rc, buf.getvalue()


def main():
    tmp = tempfile.mkdtemp(prefix="compare_runs_")
    bad = []
    try:
        p = lambda n: os.path.join(tmp, n)
        tree(p("a"))
        tree(p("same"), seconds=99, path="D:/elsewhere/out")      # times, paths, *_seconds left out
        tree(p("b"), length=24.5002, drc_extra=1, fail_line=True, extra_file=True)
        os.makedirs(p("empty1")); os.makedirs(p("empty2"))

        rc, out = run(p("a"), p("same"))
        if rc != 0 or "result: 0 differing values" not in out:
            bad.append("times and paths: exit %d, expected 0\n%s" % (rc, out))
        rc, out = run(p("a"), p("b"), "--json", p("ab.json"))
        j = json.load(open(p("ab.json"), encoding="utf-8"))
        diff = {f: {k for k, _, _ in v.get("differences", [])} for f, v in j.items()}
        m = os.path.join("route", "sdram", "metrics.json")
        want = {m: {"len_drc.FMC_D0", "len_geom.FMC_D0"}, os.path.join("finish", "drc.json"): {"violations.silk_over_copper"},
                os.path.join("rules", "rules_fixture.txt"): {"line0000", "line0001"}}
        got = {f: k for f, k in diff.items() if k}
        if rc != 1 or got != want or j.get(os.path.join("route", "orphans.txt")) != {"only_in": "B"}:
            bad.append("differences: exit %d, got %s, one side %s; expected %s and orphans.txt only in B\n%s"
                       % (rc, got, j.get(os.path.join("route", "orphans.txt")), want, out))
        rc, out = run(p("a"), p("b"), "--tol", "1e-3", "--json", p("tol.json"))
        j = json.load(open(p("tol.json"), encoding="utf-8"))
        if [k for k, _, _ in j[m]["differences"]]:
            bad.append("--tol 1e-3: the 0.0002 mm length still reported: %s" % j[m]["differences"])
        rc, out = run(p("empty1"), p("empty2"))
        if rc != 2:
            bad.append("nothing to compare: exit %d, expected 2\n%s" % (rc, out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        print("FAIL compare_runs: %d of 4 checks" % len(bad))
        print("\n".join(bad))
        return 1
    print("OK compare_runs: times / paths / timing keys left out; DRC count, length over --tol, fixture FAIL, one-sided file found; empty trees")
    return 0


if __name__ == "__main__":
    sys.exit(main())
