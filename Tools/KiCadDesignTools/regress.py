"""Run every tool benchmark (PROC-15): Tools/KiCadDesignTools/tests/<tool>/check.py, each on its own small board.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.regress [name ...]

Each check prints one `OK ...` or `FAIL ...` line and exits 0 on pass; nothing is written into the repo. The checks run
one after the other, below normal priority on four cores, holding the machine-wide heavy lock (core/heavy.py).
"""
import os, subprocess, sys, time

from Tools.KiCadDesignTools.core import heavy

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.join(HERE, "tests")
REPO = os.path.dirname(os.path.dirname(HERE))


def main(names):
    names = names or sorted(d for d in os.listdir(TESTS) if os.path.isfile(os.path.join(TESTS, d, "check.py")))
    failed = []
    for n in names:
        t = time.time()
        r = subprocess.run([sys.executable, "-m", "Tools.KiCadDesignTools.tests.%s.check" % n], cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = [l for l in (r.stdout + r.stderr).splitlines() if "image handler" not in l]
        ok = r.returncode == 0
        print("%-12s %5.1f s  %s" % (n, time.time() - t, out[0] if ok and out else "FAIL (exit %d)" % r.returncode))
        if not ok:
            failed.append(n)
            print("\n".join("    " + l for l in out))
    print("%d benchmarks, %d failed" % (len(names), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    heavy.low_priority()
    with heavy.HeavyLock("Tools.KiCadDesignTools.regress"):
        sys.exit(main(sys.argv[1:]))
