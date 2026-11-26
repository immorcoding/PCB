"""One-off runner of the survey (probe): one command through core.heavy.run (below-normal priority, four cores, the
machine-wide lock), its output to a log file, then the exit code and the wall time.

    python rk3568_ddr3_core/probes/survey/run_heavy.py <timeout s> <log file> <argv ...>      (from the repository root)
"""
import os, subprocess, sys, time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from Tools.KiCadDesignTools.core import heavy  # noqa: E402


def main(argv):
    timeout, log, cmd = float(argv[0]), argv[1], argv[2:]
    os.makedirs(os.path.dirname(os.path.abspath(log)) or ".", exist_ok=True)
    t0 = time.time()
    with open(log, "wb") as f:
        r = heavy.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
    dt = time.time() - t0
    print("exit %s%s, %.1f s (incl. heavy lock / gap), log %s" % (r.returncode, " TIMED OUT" if r.timed_out else "", dt, log))
    return r.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
