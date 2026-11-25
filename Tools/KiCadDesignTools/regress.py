"""Run every tool benchmark (PROC-15): Tools/KiCadDesignTools/tests/<tool>/check.py, each on its own small board.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.regress [name ...]
    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.regress --board demo [--keep]

Each check prints one `OK ...` or `FAIL ...` line and exits 0 on pass; nothing is written into the repo. The checks run
one after the other, each through core/heavy.py's run (below normal priority on four cores), this run holding the
machine-wide heavy lock (the checks' own heavy commands take it again: re-entrant).

--board demo: a whole board built from its data (not part of the default run: about 12 minutes). The template folder
(templates/demo_board) is copied by the driver's init into a scratch folder out/regress/<name> of the repository
(git-ignored; board folders are imported as packages, so it has to be inside the repository), every driver step is
run on the copy one after the other (project, rules --skip-match, sch, pcb-update, layout, route --skip-match, rules
--skip-match again (the length windows of the routed bus), finish --no-render; regress holds the heavy lock, each
step takes it again), and its numbers are checked against the expected values stored
with the bench (tests/<board bench>/expected.json): step exit codes, the rule fixture, the schematic checks, the final
DRC with schematic parity by type, unconnected items, the byte lane's spread and the address window (DRC-measured
lengths of the route step's bus build). The copy is deleted afterwards unless --keep.
"""
import collections, json, os, re, shutil, sys, time

from Tools.KiCadDesignTools.core import heavy

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.join(HERE, "tests")
REPO = os.path.dirname(os.path.dirname(HERE))
# whole-board benches: name -> template folder (relative to the repository), expected values
BOARDS = {"demo": ("templates/demo_board", os.path.join(TESTS, "demo_board", "expected.json"))}
SCRATCH = "out/regress"
# the rules step twice: its length-window rules (len_rules) are measured on the routed bus, so a board routed for the
# first time gets them on the second run, before the final DRC of the finish step judges them
STEPS = [("project", []), ("rules", ["--skip-match"]), ("sch", []), ("pcb-update", []), ("layout", []), ("route", ["--skip-match"]),
         ("rules", ["--skip-match"]), ("finish", ["--no-render"])]
TOL = 0.005                          # mm: lengths against the stored values


def main(names):
    names = names or sorted(d for d in os.listdir(TESTS) if os.path.isfile(os.path.join(TESTS, d, "check.py")))
    failed = []
    for n in names:
        t = time.time()
        r = heavy.kicad_py("Tools.KiCadDesignTools.tests.%s.check" % n, encoding="utf-8", errors="replace")
        out = [l for l in (r.stdout + r.stderr).splitlines() if "image handler" not in l]
        ok = r.returncode == 0
        print("%-12s %5.1f s  %s" % (n, time.time() - t, out[0] if ok and out else "FAIL (exit %d)" % r.returncode))
        if not ok:
            failed.append(n)
            print("\n".join("    " + l for l in out))
    print("%d benchmarks, %d failed" % (len(names), len(failed)))
    return 1 if failed else 0


# ---------------------------------------------------------------------------------------------------- whole boards
def measured(d, name):
    """The numbers of a built board folder `d` (its out/ reports) that the bench compares."""
    from Tools.KiCadDesignTools.core import config
    cfg = config.load(d)
    O = os.path.join(d, "out")
    m = {}
    rf = os.path.join(O, cfg.get("build.out.rules", "rules"), "rules_fixture.txt")
    first = open(rf, encoding="utf-8").readline() if os.path.isfile(rf) else ""
    k = re.search(r"(\d+) 个用例，(\d+) 项不符", first)
    m["fixture"] = [int(k.group(1)), int(k.group(2))] if k else None
    sc = os.path.join(O, cfg.get("build.out.sch", "sch"), "sch_check.txt")
    last = open(sc, encoding="utf-8").read().strip().splitlines()[-1:] if os.path.isfile(sc) else []
    m["sch_check"] = last[0] if last else None
    erc = os.path.join(O, cfg.get("build.out.sch", "sch"), "erc.rpt")
    k = re.search(r"ERC messages: (\d+)", open(erc, encoding="utf-8", errors="replace").read()) if os.path.isfile(erc) else None
    m["erc"] = int(k.group(1)) if k else None
    fd = os.path.join(O, cfg.get("build.out.finish", "finish"), "drc.json")
    if os.path.isfile(fd):
        j = json.load(open(fd, encoding="utf-8"))
        m["drc"] = dict(sorted(collections.Counter(v["type"] for v in j["violations"]).items()))
        m["unconnected"] = len(j["unconnected_items"])
        m["parity"] = dict(sorted(collections.Counter(v["type"] for v in j.get("schematic_parity", [])).items()))
    # lengths as DRC measured them in the bus group's build of the route step
    bus = cfg.get("route.table.bus", cfg.groups[0]["name"] if cfg.groups else None)
    mj = os.path.join(O, cfg.get("build.out.route", "route"), bus or "", "metrics.json")
    if bus and os.path.isfile(mj):
        L = json.load(open(mj, encoding="utf-8"))["length"]
        drc = L.get("drc") or {}
        sw = cfg.get("schematic.swap", {})
        # every byte lane k ([schematic.swap] lanes: data bits 8k..8k+7 and mask k); the widest lane's spread
        lanes = [["%s%d" % (sw["data_net"], i) for i in range(8 * k, 8 * k + 8)] + ["%s%d" % (sw["mask_net"], k)]
                 for k in range(sw["lanes"])] if sw else []
        if lanes and all(n in drc for lane in lanes for n in lane):
            m["lane_spread"] = max(round(max(drc[n] for n in lane) - min(drc[n] for n in lane), 4) for lane in lanes)
        clock = cfg.get("tune_sites.clock", [])
        addr = cfg.get("tune_sites.addr", [])
        lg = json.load(open(os.path.join(d, "length_groups.json"), encoding="utf-8"))
        g = next((g for g in lg.get("groups", []) if g["rule"] == cfg.get("length.window_rule")), None)
        if clock and addr and g and all(n in drc for n in clock + addr):
            ref = sum(drc[n] for n in clock)
            lo, hi = ref + g["lo"], min(ref + g["hi"], g.get("cap", 1e9))
            m["clock"] = round(ref, 4)
            m["window"] = [round(lo, 4), round(hi, 4)]
            m["addr_margin"] = round(min(min(drc[n] - lo, hi - drc[n]) for n in addr), 4)
    return m


def compare(m, want):
    """-> [problems]: exact for counts and texts, TOL for lengths; addr_margin must stay >= 0."""
    bad = []
    for k, w in want.items():
        if k == "steps" or k.startswith("_"):          # the step codes are compared by the caller; "_": a note
            continue
        g = m.get(k)
        if isinstance(w, float) or (isinstance(w, list) and w and isinstance(w[0], float)):
            ws, gs = (w, g) if isinstance(w, list) else ([w], [g])
            if g is None or len(ws) != len(gs) or any(abs(a - b) > TOL for a, b in zip(ws, gs)):
                bad.append("%s: %s, expected %s" % (k, g, w))
        elif g != w:
            bad.append("%s: %s, expected %s" % (k, g, w))
    if m.get("addr_margin") is not None and m["addr_margin"] < 0:
        bad.append("an address line outside the window by %.3f mm" % -m["addr_margin"])
    return bad


def board(name, keep=False):
    from Tools.KiCadDesignTools import build
    if name not in BOARDS:
        print("no whole-board bench %s (%s)" % (name, ", ".join(sorted(BOARDS))))
        return 2
    src, exp = BOARDS[name]
    want = json.load(open(exp, encoding="utf-8"))
    bname = os.path.basename(src)
    parent = os.path.join(REPO, *SCRATCH.split("/"))
    d = os.path.join(parent, bname)
    rel = SCRATCH + "/" + bname
    if os.path.exists(d):
        shutil.rmtree(d)
    T0 = time.time()
    if build.init(bname, src, SCRATCH) != 0:
        print("FAIL board %s: init refused" % name)
        return 1
    codes, times = {}, {}
    for step, flags in STEPS:
        t = time.time()
        r = heavy.kicad_py("Tools.KiCadDesignTools.build", rel, step, *flags)
        os.makedirs(os.path.join(d, "out"), exist_ok=True)
        with open(os.path.join(d, "out", "regress_%s%s.log" % (step, "2" if step in codes else "")), "wb") as f:
            f.write(r.stdout + r.stderr)
        key = step if step not in codes else step + "2"
        codes[key], times[key] = r.returncode, round(time.time() - t)
        print("  %-10s exit %d  %4d s" % (key, r.returncode, times[key]))
        heavy.rest(20)
    m = measured(d, name)
    m["steps"] = codes
    bad = compare(m, want)
    bad += ["step %s: exit %s, expected %s" % (s, codes.get(s), c) for s, c in want.get("steps", {}).items() if codes.get(s) != c]
    total = time.time() - T0
    head = "%s board %s: %d s; lane spread %s mm, clock %s mm, window %s, address margin %s mm; DRC %s, unconnected %s, parity %s" % (
        "FAIL" if bad else "OK", name, total, m.get("lane_spread"), m.get("clock"), m.get("window"), m.get("addr_margin"), m.get("drc"),
        m.get("unconnected"), m.get("parity"))
    print(head)
    for b in bad:
        print("    " + b)
    json.dump(dict(m, seconds=round(total), step_seconds=times), open(os.path.join(parent, "%s_measured.json" % name), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    if not keep:
        shutil.rmtree(d, ignore_errors=True)
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass
    argv = sys.argv[1:]
    if "--board" in argv:
        k = argv.index("--board")
        if k + 1 >= len(argv):
            sys.exit(__doc__)
        heavy.low_priority()
        # the whole bench under the heavy lock: every driver step takes it again (re-entrant, PCB_HEAVY_TOKEN)
        with heavy.HeavyLock("Tools.KiCadDesignTools.regress --board %s" % argv[k + 1]):
            sys.exit(board(argv[k + 1], keep="--keep" in argv))
    heavy.low_priority()
    with heavy.HeavyLock("Tools.KiCadDesignTools.regress"):
        sys.exit(main(argv))
