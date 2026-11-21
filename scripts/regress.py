"""Run every tool benchmark (PROC-15): scripts/tests/<tool>/check.py, each on its own small board.

    D:\\KiCad\\bin\\python.exe scripts\\regress.py [name ...]

Each check prints one `OK ...` or `FAIL ...` line and exits 0 on pass; nothing is written into the repo.
"""
import os, subprocess, sys, time

TESTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests")


def main(names):
    names = names or sorted(d for d in os.listdir(TESTS) if os.path.isfile(os.path.join(TESTS, d, "check.py")))
    failed = []
    for n in names:
        t = time.time()
        r = subprocess.run([sys.executable, os.path.join(TESTS, n, "check.py")], capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = [l for l in (r.stdout + r.stderr).splitlines() if "image handler" not in l]
        ok = r.returncode == 0
        print("%-12s %5.1f s  %s" % (n, time.time() - t, out[0] if ok and out else "FAIL (exit %d)" % r.returncode))
        if not ok:
            failed.append(n)
            print("\n".join("    " + l for l in out))
    print("%d benchmarks, %d failed" % (len(names), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
