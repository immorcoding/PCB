"""Regression benchmark for core/heavy.py: the limiter every kicad-cli and KiCad-python launch goes through.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.tests.heavy.check

This process is first put back to normal priority on every core (a tool started by hand), then expects:
  - a child started by heavy.run reads its own priority class BELOW_NORMAL (0x4000) and affinity mask 0xF;
  - the lock is re-entrant: nested in this process, and in a child that takes it again with wait=0 (it finds the
    holder's token); a child without the token gives up at once (another run holds the lock); the lock file is as it
    was afterwards (removed, or still the outer holder's when regress holds it);
  - exit codes: exit 3 with check=True raises HeavyError (returncode 3); a missing output file raises; a timeout
    returns 124; kicad-cli DRC on a board file that does not exist raises HeavyError (failed to run);
  - the gap: a command starts no earlier than the gap after the previous one ended (1.5 s after one that ran 2 s,
    0.3 s after one that ran 0.3 s: the pause is never longer than the previous command ran).
Prints one line, `OK ...` or `FAIL ...`; exit code 0 = pass. About 15 s (one kicad-cli start).
"""
import json, os, shutil, sys, tempfile, time

from Tools.KiCadDesignTools.core import heavy, paths

PY = sys.executable
PROBE = r"""
import ctypes, json, os, time
from ctypes import wintypes
k = ctypes.WinDLL("kernel32")
k.GetCurrentProcess.restype = wintypes.HANDLE
k.GetPriorityClass.argtypes = [wintypes.HANDLE]
k.GetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
h = k.GetCurrentProcess()
pm, sm = ctypes.c_size_t(), ctypes.c_size_t()
k.GetProcessAffinityMask(h, ctypes.byref(pm), ctypes.byref(sm))
print(json.dumps({"priority": k.GetPriorityClass(h), "affinity": pm.value, "t": time.time(),
                  "token": os.environ.get("PCB_HEAVY_TOKEN")}))
"""
TAKE = r"""
from Tools.KiCadDesignTools.core import heavy
with heavy.HeavyLock("bench child", wait=0):
    print("taken")
"""
NORMAL = 0x20


def normal_priority():
    """This process as a tool started by hand: normal priority, every core."""
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32")
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
    k.GetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
    h = k.GetCurrentProcess()
    pm, sm = ctypes.c_size_t(), ctypes.c_size_t()
    k.GetProcessAffinityMask(h, ctypes.byref(pm), ctypes.byref(sm))
    k.SetPriorityClass(h, NORMAL)
    k.SetProcessAffinityMask(h, sm.value)


def probe(**kw):
    r = heavy.run([PY, "-c", PROBE], check=True, text=True, **kw)
    return json.loads(r.stdout)


def main(argv):
    t0 = time.time()
    os.environ["PCB_HEAVY_GAP"] = "0"                    # no pauses here except where the gap is the test
    fails = []
    tmp = tempfile.mkdtemp(prefix="heavy_")
    try:
        # 1. priority and affinity of the child, read by the child itself
        normal_priority()
        p = probe()
        if p["priority"] != heavy.BELOW_NORMAL or p["affinity"] != 0xF:
            fails.append("child priority 0x%X, affinity 0x%X; expected 0x4000, 0xF" % (p["priority"], p["affinity"]))
        if not p["token"]:
            fails.append("the child got no lock token")
        # 2. re-entrancy
        before = os.path.exists(heavy.LOCK_FILE) and heavy._holder().get("token")
        with heavy.HeavyLock("bench", wait=0):
            with heavy.HeavyLock("bench nested", wait=0):
                r = heavy.run([PY, "-c", TAKE], cwd=paths.REPO, text=True)
                if r.returncode != 0 or "taken" not in r.stdout:
                    fails.append("a child of the holder could not take the lock: exit %d %s" % (r.returncode, heavy._tail(r.stderr)))
                r = heavy.run([PY, "-c", TAKE], cwd=paths.REPO, text=True, env={heavy.TOKEN_VAR: ""})
                if r.returncode == 0 or "another heavy run holds" not in r.stderr:
                    fails.append("a child without the token took the lock: exit %d %s" % (r.returncode, r.stdout.strip()))
            if not os.path.exists(heavy.LOCK_FILE):
                fails.append("the nested exit removed the lock")
        after = os.path.exists(heavy.LOCK_FILE) and heavy._holder().get("token")
        if after != before:
            fails.append("lock file after the run: %r, before: %r" % (after, before))
        # 3. exit codes: ran vs failed to run
        try:
            heavy.run([PY, "-c", "import sys; sys.exit(3)"], check=True)
            fails.append("exit 3 with check=True did not raise")
        except heavy.HeavyError as e:
            if e.returncode != 3:
                fails.append("HeavyError.returncode %r, expected 3" % e.returncode)
        try:
            heavy.run([PY, "-c", "pass"], check=True, outputs=[os.path.join(tmp, "never.json")])
            fails.append("a missing output did not raise")
        except heavy.HeavyError:
            pass
        r = heavy.run([PY, "-c", "import time; time.sleep(30)"], timeout=1)
        if r.returncode != heavy.TIMED_OUT or not r.timed_out:
            fails.append("timeout: exit %d, expected %d" % (r.returncode, heavy.TIMED_OUT))
        try:
            heavy.kicad_cli("pcb", "drc", "--format", "json", "-o", os.path.join(tmp, "drc.json"), os.path.join(tmp, "missing.kicad_pcb"),
                            outputs=[os.path.join(tmp, "drc.json")])
            fails.append("kicad-cli DRC of a missing board did not raise")
        except heavy.HeavyError as e:
            cli_exit = e.returncode
        # 4. the gap
        heavy.run([PY, "-c", "import time; time.sleep(2)"])
        end = time.time()
        p = probe(gap=1.5)
        if not 1.45 <= p["t"] - end:
            fails.append("a command started %.2f s after one of 2 s, gap 1.5 s" % (p["t"] - end))
        heavy.run([PY, "-c", "import time; time.sleep(0.3)"])
        end = time.time()
        p = probe(gap=1.5)
        if not 0.25 <= p["t"] - end < 1.4:
            fails.append("a command started %.2f s after one of 0.3 s, gap 1.5 s (expected about 0.3 s)" % (p["t"] - end))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if fails:
        print("FAIL heavy (%d)" % len(fails))
        print("\n".join("  " + f for f in fails))
        return 1
    print("OK heavy: child below normal on 0xF, lock re-entrant (in process and in a child), exclusive without the token, "
          "exit / missing output / timeout / kicad-cli on a missing board (exit %s) caught, gap kept; %.0f s" % (cli_exit, time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
