"""Regression benchmark for analysis/compare_runs.py (two builds' reports compared number by number, pure text).

    python -m Tools.KiCadDesignTools.tests.compare_runs.check

Two small out trees in a temp directory (a busroute group's metrics.json, a DRC report, a rule fixture report, a
table with a time and a path in it): the same numbers with other times, paths and timing keys compare equal; a DRC
type count, a net length beyond --tol, a fixture FAIL line and a file on one side only are reported; empty trees give
exit 2. Directions (PROC-4): a tree "worse" that moves one item of each kind the wrong way (lower is better: DRC by
type, unconnected, track_shape, geometry findings, vias of a net in a group with a via limit, a lane's spread, tuning
shortfall, decoupling over the limit, a pour piece without a via in pieces_*.json and pour_islands.txt, a rule that
matches nothing; higher is better: nets built, the verdict ok, balls with a way out) and one of each the right way
(better), plus plain measurements (a net length, the reference group's span, a via count in a group without a limit, a
slot length): exactly the wrong-way items are listed under "变差 / worse", before the file list, exit 1; --report-only
exits 0; better and plain differences alone exit 0. Prints one line, `OK ...` or `FAIL ...` (details follow a FAIL);
exit code 0 = pass. Nothing is written into the repository.
"""
import contextlib, io, json, os, shutil, sys, tempfile

from Tools.KiCadDesignTools.analysis import compare_runs


def tree(root, length=24.5, drc_extra=0, fail_line=False, seconds=12, path="E:/x/out", extra_file=False, k=0, plain=False):
    """k = 0: the base values; k = +1: every directional item of the direction cases one step worse; k = -1: one step
    better. plain: only plain measurements changed."""
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
    # the direction cases: one item of each kind (base, worse with k = +1, better with k = -1), plain measurements
    j = max(k, 0)
    w("route/bus/metrics.json", {
        "length": {"drc": {"FMC_D0": 30.0 + (1.0 if plain else 0.0)}, "nets": {"FMC_D0": {"vias": 2 + k, "length": 30.0}},
                   "groups": {"lane0": {"spread": 0.4 + 0.1 * k}, "addr": {"spread": 39.0 + (2.0 if plain else 0.0)}}},
        "tuning": {"groups": {"lane0": {}, "addr": {"kind": "ref"}}, "missing": {"FMC_D0": 0.05 + 0.05 * k} if k >= 0 else {}},
        "connectivity": {"drc_unconnected_group": 1 + k, "drc_by_type_group": {"clearance": 1 + k}},
        "shape": {"track_shape": {"sharp": 1 + k, "segments": 100 + (5 if plain else 0)}, "geometry": {"CORNER": 1 + k}},
        "built": {"nets": 10 - k}, "vias": {"limit": 3}, "findings": [{}] * (1 + k), "hard_findings": 1 + k, "ok": k <= 0})
    w("route/free/metrics.json", {"length": {"nets": {"X": {"vias": 4 + (3 if plain else 0), "length": 5.0}}}, "vias": {"limit": None}})
    w("layout/place_check.json", {"parts": {"placed": 20 - k, "parked": []},
                                  "decoupling": {"per_ic": {"U1": {"over": [["C1", 3.1]] * (1 + k), "worst": 3.1}}}})
    w("route/escape_bga.json", {"U1": {"A1": {"status": "out" if k <= 0 else "blocked", "vias": 1},
                                       "A2": {"status": "local" if k < 0 else "blocked", "vias": 0}}})
    w("finish/pieces_after.json", {"L1": {"0": 1 + k, "1": 5}})
    w("finish/pour_islands.txt", "cu-whole:L1_GND: 13 pieces, %d without a via or through-hole pad\n" % (1 + k))
    w("finish/dru_match.json", {"loaded": True, "rules": [{"rule": "a", "matched": 3}, {"rule": "b", "matched": 0 if k >= 0 else 2},
                                                          {"rule": "c", "matched": 0 if k > 0 else 1}]})
    w("route/slots.json", {"slots": [{"length": 2.0 + (0.7 if plain else 0.0)}]})


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
        tree(p("worse"), k=1)
        tree(p("better"), k=-1)
        tree(p("plain"), plain=True)

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

        # directions: exactly the wrong-way items are "worse", listed first; --report-only; better / plain exit 0
        J = lambda *a: os.path.join(*a)
        want_worse = {J("route", "bus", "metrics.json"): {"vias.FMC_D0", "spread.lane0", "tuning_missing.FMC_D0", "conn.drc_unconnected_group",
                                                          "drc_group.clearance", "track_shape.sharp", "geometry.CORNER", "built.nets",
                                                          "findings", "hard_findings", "ok"},
                      J("layout", "place_check.json"): {"decoupling.per_ic.U1.over.#", "parts.placed"},
                      J("route", "escape_bga.json"): {"escaped.U1"},
                      J("finish", "pieces_after.json"): {"L1.0"},
                      J("finish", "pour_islands.txt"): {"without_via.cu-whole:L1_GND"},
                      J("finish", "dru_match.json"): {"empty_rules"}}
        rc, out = run(p("a"), p("worse"), "--json", p("worse.json"))
        j = json.load(open(p("worse.json"), encoding="utf-8"))
        got = {f: {k for k, _, _ in v["worse"]} for f, v in j.items() if v.get("worse")}
        lines = out.splitlines()
        head = next((i for i, l in enumerate(lines) if l.startswith("变差 / worse: ")), None)
        first_file = next((i for i, l in enumerate(lines) if "values," in l), None)
        n_listed = len([l for l in lines[head + 1:first_file] if l.startswith("  ")]) if head is not None and first_file else -1
        if rc != 1 or got != want_worse or head is None or first_file is None or head > first_file or n_listed != 17 \
                or "变差 / worse: 17" not in out or "  ! built.nets: 10 -> 9" not in out:
            bad.append("worse: exit %d, worse %s, section at line %s before the files at %s, %d listed; expected %s\n%s"
                       % (rc, got, head, first_file, n_listed, want_worse, out))
        rc, out = run(p("a"), p("worse"), "--report-only")
        if rc != 0 or "变差 / worse: 17" not in out:
            bad.append("--report-only: exit %d, expected 0 with the 17 items listed\n%s" % (rc, out[:600]))
        rc, out = run(p("a"), p("better"), "--json", p("better.json"))
        j = json.load(open(p("better.json"), encoding="utf-8"))
        ndiff = sum(len(v.get("differences", [])) for v in j.values())
        if rc != 0 or "变差 / worse: 0" not in out or ndiff < 15:
            bad.append("better: exit %d, %d differences; expected 0 and at least 15 differences, none worse\n%s" % (rc, ndiff, out))
        rc, out = run(p("a"), p("plain"), "--json", p("plain.json"))
        j = json.load(open(p("plain.json"), encoding="utf-8"))
        got = {f: {k for k, _, _ in v["differences"]} for f, v in j.items() if v.get("differences")}
        want = {J("route", "bus", "metrics.json"): {"len_drc.FMC_D0", "span.addr", "track_shape.segments"},
                J("route", "free", "metrics.json"): {"vias.X"}, J("route", "slots.json"): {"slots[0].length"}}
        if rc != 0 or "变差 / worse: 0" not in out or got != want:
            bad.append("plain measurements: exit %d, differences %s; expected 0 and %s\n%s" % (rc, got, want, out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        print("FAIL compare_runs: %d of 8 checks" % len(bad))
        print("\n".join(bad))
        return 1
    print("OK compare_runs: times / paths / timing keys left out; DRC count, length over --tol, fixture FAIL, one-sided file found; empty trees; "
          "17 wrong-way items of 17 kinds listed first as worse (exit 1, --report-only 0); better and plain differences exit 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
