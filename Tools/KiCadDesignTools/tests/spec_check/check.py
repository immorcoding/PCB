"""Regression benchmark for project/spec_check.py.

    python -m Tools.KiCadDesignTools.tests.spec_check.check        (any Python >= 3.11; no KiCad)

Exit 0 = pass. Prints one OK / FAIL line first (Tools.KiCadDesignTools.regress shows it), then one line per case.
Each case copies fixture/ (a board folder: board.toml, SPEC.md with a complete table "本板取值", the data files it names,
its own copy of the profile table) into a temp folder outside the repository, changes one thing and runs spec_check:
  A  complete table, every data source agrees -> exit 0, 14 sources compared
  B  one row's value empty -> exit 1;  C  one row missing -> exit 1;  J  the via-count item not split -> exit 1
  D  the SPEC contradicts the rule file;  E  the copper sketch contradicts the SPEC;  F  the layer roles differ;
     I  a source key that does not exist -> exit 1 each
  G  B with [board] spec_table = false -> exit 0 with warnings;  H  a data file not written yet -> exit 0, noted
  K  a row 不适用 -> exit 0
  L  the real profile C parses; templates/demo_board/SPEC.md is complete against it (exit 0)
Nothing is written into the repository.
"""
import contextlib, io, os, re, shutil, sys, tempfile

from Tools.KiCadDesignTools.core import paths
from Tools.KiCadDesignTools.project import spec_check

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixture")
results = []


def run(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = spec_check.main(argv)
    return code, buf.getvalue()


def case(label, change=None, want_code=0, want=(), not_want=()):
    tmp = tempfile.mkdtemp(prefix="spec_check_")
    try:
        d = os.path.join(tmp, "board")
        shutil.copytree(FIX, d, ignore=shutil.ignore_patterns("__pycache__"))
        if change:
            change(d)
        code, out = run([d, "--profile", os.path.join(d, "profile.md")])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [w for w in want if not re.search(w, out)] + ["(unwanted) " + w for w in not_want if re.search(w, out)]
    ok = code == want_code and not bad
    results.append((ok, "%s  exit %d (want %d)%s" % (label, code, want_code, "; missing: " + " | ".join(bad) if bad else "")))
    if not ok:
        results.append((False, "    " + out.replace("\n", "\n    ")))
    return out


def edit(name, old, new, count=1):
    def f(d):
        p = os.path.join(d, name)
        s = open(p, encoding="utf-8").read()
        assert old in s, (name, old)
        open(p, "w", encoding="utf-8", newline="\n").write(s.replace(old, new, count))
    return f


def both(*fs):
    def f(d):
        for g in fs:
            g(d)
    return f


out = case("A complete", want=[r"结论：齐全，和数据文件一致"], not_want=[r"FAIL"])
n = len(re.findall(r"，一致", out))
results.append((n == 14, "A  sources compared and agreeing: %d (want 14)" % n))

empty_amp = edit("SPEC.md", "| 蛇形起始摆幅 | 0.5 mm |", "| 蛇形起始摆幅 |  |")
case("B empty value", empty_amp, 1, [r"FAIL  空：蛇形起始摆幅"])
case("C missing row", edit("SPEC.md", "| 电源层块间的缝 | 0.5 mm | `copper.sketch:gap` | |\n", ""), 1, [r"FAIL  缺：电源层块间的缝"])
case("D SPEC contradicts the rule file", edit("SPEC.md", "不超过 1.27 mm（50 mil）", "不超过 1.0 mm"), 1,
     [r"FAIL  不一致：数据线组内等长：字节通道 0 .*kicad_dru:bench_lane0\.skew\.max 是 1\.27"])
case("E data contradicts the SPEC", edit("copper.sketch", "gap 0.5", "gap 0.6"), 1, [r"FAIL  不一致：电源层块间的缝.*copper\.sketch:gap 是 0\.6"])
case("F layer roles differ", edit("board.toml", '"signal", "power", "signal"]', '"signal", "ground", "signal"]'), 1,
     [r"FAIL  不一致：信号层数.*board\.toml:layers\.roles"])
case("I source key missing", edit("length_groups.json", '"bench_window"', '"other_window"'), 1,
     [r"FAIL  读不了：地址命令对时钟 .*no element with rule=bench_window"])
case("J via-count item not split", edit("SPEC.md", "| 过孔数上限：哪些线 | D0–D7、DM0、CK | — | |\n", ""), 1, [r"FAIL  缺：过孔数上限 要分成"])
case("G spec_table = false", both(empty_amp, edit("board.toml", 'template = "C-bga-065"', 'template = "C-bga-065"\nspec_table = false')), 0,
     [r"warn  空：蛇形起始摆幅", r"只警告"], [r"FAIL"])
case("H routes file not written yet", lambda d: os.remove(os.path.join(d, "routes_bus.py")), 0,
     [r"数据源 routes_bus\.py:TUNING\.amp：routes_bus\.py 还没有，没比", r"结论：齐全"])
case("K 不适用", edit("SPEC.md", "| 平面上过孔避让连成的槽 | 不设长度上限，只报数 |", "| 平面上过孔避让连成的槽 | 不适用 |"), 0, [r"      平面上过孔避让连成的槽：不适用"])

real = os.path.join(paths.REPO, "docs", "rule-profiles", "C-bga-065.md")
items = spec_check.profile_items(real)
results.append(("信号层数" in items and "过孔数上限" in items and len(items) >= 12, "L  real profile C: %d items" % len(items)))
code, out = run([os.path.join(paths.REPO, "templates", "demo_board"), "--profile", real])
results.append((code == 0 and "结论：齐全" in out, "L  templates/demo_board/SPEC.md against the real profile: exit %d" % code))

fails = [r for r in results if not r[0]]
print("%s spec_check: %d checks, %d failed" % ("OK" if not fails else "FAIL", sum(1 for r in results if not r[1].startswith("    ")), len(fails)))
for ok, line in results:
    print(("ok    " if ok else "FAIL  ") + line if not line.startswith("    ") else line)
sys.exit(1 if fails else 0)
