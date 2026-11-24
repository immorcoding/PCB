"""Heavy-process discipline (the PC hard-reset twice on 2026-11-23 under parallel KiCad load).

    low_priority()       this process to below-normal priority on four cores; children (kicad-cli, KiCad's python.exe)
                         inherit both, so a driver calls it once at its start
    HeavyLock(name)      a machine-wide lock file: only one driver (build, regress) runs KiCad work at a time; a second
                         one waits or gives up (the file names the holder's PID and command)
    rest(seconds)        a pause between heavy commands (build.sh's finish step pauses 20 s after each refill)
    kicad_lock(folder)   the KiCad lock files (*.lck, hidden ones too) in a board folder: KiCad has the project open,
                         so nothing may write the board or the project file
    running(names)       the processes of those names that are running now (tasklist), e.g. a stray kicad-cli.exe

Windows only for the priority and the affinity (ctypes, kernel32); elsewhere low_priority() only lowers the nice value.
"""
import json, os, subprocess, sys, tempfile, time

BELOW_NORMAL = 0x00004000
CORES = 4
LOCK_FILE = os.path.join(tempfile.gettempdir(), "pcb_tools_heavy.lock")


def low_priority(cores=CORES):
    """Below-normal priority and an affinity of `cores` logical processors for this process (inherited by children).
    Returns a short description of what was set."""
    if os.name != "nt":
        try:
            os.nice(10)
        except Exception:
            pass
        return "nice +10"
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.GetCurrentProcess.restype = wintypes.HANDLE                  # the pseudo-handle -1: a 64-bit value on x64
    k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
    h = k.GetCurrentProcess()
    pr = k.SetPriorityClass(h, BELOW_NORMAL)
    mask = (1 << cores) - 1
    ok = k.SetProcessAffinityMask(h, mask)
    return "below-normal priority%s, affinity 0x%X%s" % ("" if pr else " (refused)", mask,
                                                         "" if ok else " (refused, error %d)" % ctypes.get_last_error())


def _alive(pid):
    if os.name == "nt":
        r = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/NH"], capture_output=True)
        return str(pid).encode() in r.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class HeavyLock:
    """with HeavyLock("build stm32h743_sdram route"): ...   -- one heavy driver at a time on this machine."""

    def __init__(self, what, wait=0.0):
        self.what, self.wait, self.held = what, wait, False

    def __enter__(self):
        t0 = time.time()
        while True:
            try:
                fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, json.dumps({"pid": os.getpid(), "what": self.what, "since": time.strftime("%H:%M:%S")}).encode())
                os.close(fd)
                self.held = True
                return self
            except FileExistsError:
                try:
                    other = json.load(open(LOCK_FILE, encoding="utf-8"))
                except Exception:
                    other = {}
                if other.get("pid") and not _alive(int(other["pid"])):
                    os.remove(LOCK_FILE)                      # a stale lock of a process that died
                    continue
                if time.time() - t0 >= self.wait:
                    raise SystemExit("another heavy run holds %s: %s (pid %s, since %s)"
                                     % (LOCK_FILE, other.get("what", "?"), other.get("pid", "?"), other.get("since", "?")))
                time.sleep(5)

    def __exit__(self, *exc):
        if self.held:
            try:
                os.remove(LOCK_FILE)
            except OSError:
                pass
        return False


def rest(seconds=20):
    if seconds > 0:
        time.sleep(seconds)


def kicad_lock(folder):
    """KiCad's lock files in `folder` (listdir sees hidden files too)."""
    try:
        return sorted(f for f in os.listdir(folder) if f.endswith(".lck"))
    except OSError:
        return []


def running(names=("kicad-cli.exe", "kicad.exe", "pcbnew.exe")):
    if os.name != "nt":
        return []
    r = subprocess.run(["tasklist", "/NH"], capture_output=True)
    out = r.stdout.decode("utf-8", "replace").lower()
    return [n for n in names if n.lower() in out]
