"""Heavy-process discipline (the PC hard-reset twice on 2026-11-23 under parallel KiCad load).

Every kicad-cli and KiCad-python launch of the package goes through run() (or one of its two shorthands), however
the tool was started: by the driver, by regress, by hand, or by another tool.

    run(argv, ...)          one heavy command in the foreground, from start to end:
                            - priority: the calling process goes to below-normal priority on four cores
                              (low_priority); the child is created below normal (creationflags) and gets the
                              four-core affinity mask itself
                            - one at a time: the machine-wide lock (HeavyLock) is held while it runs; re-entrant, in
                              one process and across processes (a holder puts its token into the environment
                              variable PCB_HEAVY_TOKEN, so its children find the lock theirs and do not wait for
                              their own parent); waits up to WAIT seconds for another holder
                            - a gap: it starts no earlier than GAP seconds after the previous heavy command ended
                              (or as long as that one ran, when it ran shorter), in whatever process that ran (the
                              end time is kept in a file next to the lock); PCB_HEAVY_GAP=<seconds> or gap= changes it
                            - the exit code: with check=True a command that did not run through raises HeavyError:
                              an exit code outside `ok` (ok=None: any code), a timeout, or an expected output file
                              (outputs=[...], removed before the run) missing afterwards. Without check the caller
                              reads returncode (TIMED_OUT = 124 after a timeout) and .missing
    kicad_cli(*args)        run([KICAD_CLI, *args]) with check=True: kicad-cli exits 0 when it ran, whatever DRC / ERC
                            found (violations give a non-zero code only with --exit-code-violations, then 5 is
                            accepted too)
    kicad_py(module, *args) run([KICAD_PY, "-m", module, *args]) from the repository root (a path that does not start
                            with "Tools." runs as a script), check=False: the tools' exit codes are their verdicts,
                            the caller judges them
    low_priority()          this process to below-normal priority on four cores (inherited by its children); the
                            driver and regress call it once at their start
    HeavyLock(what, wait)   the lock itself, for a driver or regress that holds it around a whole run (wait=0: give up
                            at once when another run holds it)
    rest(seconds)           a pause between heavy commands (the finish step's 20 s after each refill)
    kicad_lock(folder)      the KiCad lock files (*.lck, hidden ones too) in a board folder: KiCad has the project open,
                            so nothing may write the board or the project file
    running(names)          the processes of those names that are running now (tasklist), e.g. a stray kicad-cli.exe

Windows only for the priority and the affinity (ctypes, kernel32); elsewhere low_priority() only lowers the nice value.
"""
import json, os, subprocess, sys, tempfile, threading, time, uuid

from Tools.KiCadDesignTools.core import paths

BELOW_NORMAL = 0x00004000
CORES = 4
LOCK_FILE = os.path.join(tempfile.gettempdir(), "pcb_tools_heavy.lock")
LAST_FILE = os.path.join(tempfile.gettempdir(), "pcb_tools_heavy.last")    # when the last heavy command ended, how long it ran
TOKEN_VAR = "PCB_HEAVY_TOKEN"
GAP = 2.0             # seconds between the end of one heavy command and the start of the next (PCB_HEAVY_GAP); a
                      # command that ran shorter is followed by a pause as long as it ran
WAIT = 3600.0         # seconds run() waits for another holder of the lock
TIMED_OUT = 124
VIOLATIONS = 5        # kicad-cli's exit code for "ran, found violations" (only with --exit-code-violations)
PIPE, STDOUT, DEVNULL = subprocess.PIPE, subprocess.STDOUT, subprocess.DEVNULL


class HeavyError(RuntimeError):
    """A heavy command that did not run through. returncode: its exit code (TIMED_OUT, or 0 when only an output is
    missing); output: the tail of what it printed."""

    def __init__(self, message, returncode=None, output=""):
        super().__init__(message)
        self.returncode, self.output = returncode, output


# ---------------------------------------------------------------------------------------------------- priority
def _kernel32():
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.GetCurrentProcess.restype = wintypes.HANDLE                  # the pseudo-handle -1: a 64-bit value on x64
    k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
    k.OpenProcess.restype = wintypes.HANDLE
    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    return k


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
    k = _kernel32()
    h = k.GetCurrentProcess()
    pr = k.SetPriorityClass(h, BELOW_NORMAL)
    mask = (1 << cores) - 1
    ok = k.SetProcessAffinityMask(h, mask)
    return "below-normal priority%s, affinity 0x%X%s" % ("" if pr else " (refused)", mask,
                                                         "" if ok else " (refused, error %d)" % ctypes.get_last_error())


def _limit_child(proc, cores):
    """The child's own priority class and affinity (not only what it inherits)."""
    if os.name != "nt":
        return
    k = _kernel32()
    h = int(proc._handle)
    k.SetPriorityClass(h, BELOW_NORMAL)
    k.SetProcessAffinityMask(h, (1 << cores) - 1)


def _alive(pid):
    if os.name == "nt":
        from ctypes import wintypes, byref
        k = _kernel32()
        h = k.OpenProcess(0x1000, False, pid)                      # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = wintypes.DWORD()
        try:
            return bool(k.GetExitCodeProcess(h, byref(code))) and code.value == 259     # STILL_ACTIVE
        finally:
            k.CloseHandle(h)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------------------------------- the lock
_thread_lock = threading.RLock()     # threads of one process: one heavy command at a time as well
_depth = 0                           # HeavyLock nesting in this process


def _holder():
    try:
        return json.load(open(LOCK_FILE, encoding="utf-8"))
    except Exception:
        return {}


class HeavyLock:
    """with HeavyLock("build stm32h743_sdram route"): ...   -- one heavy run at a time on this machine.

    Re-entrant: inside a with-block of this process, and in a child process of the holder (the holder's token in
    PCB_HEAVY_TOKEN names the lock file's content). Another holder: wait up to `wait` seconds, then SystemExit."""

    def __init__(self, what, wait=0.0):
        self.what, self.wait = what, wait
        self.owner, self.old_token = False, None

    def __enter__(self):
        global _depth
        _thread_lock.acquire()
        try:
            if _depth == 0:
                tok = os.environ.get(TOKEN_VAR)
                h = _holder()
                if not (tok and h.get("token") == tok and _alive(int(h.get("pid", 0)))):
                    self._acquire()
            _depth += 1
        except BaseException:
            _thread_lock.release()
            raise
        return self

    def _acquire(self):
        t0, told = time.time(), False
        token = "%d:%s" % (os.getpid(), uuid.uuid4().hex[:12])
        while True:
            try:
                fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, json.dumps({"pid": os.getpid(), "what": self.what, "since": time.strftime("%H:%M:%S"),
                                         "token": token}).encode())
                os.close(fd)
                self.owner, self.old_token = True, os.environ.get(TOKEN_VAR)
                os.environ[TOKEN_VAR] = token                     # children inherit it: the lock is theirs too
                return
            except FileExistsError:
                other = _holder()
                if other.get("pid") and not _alive(int(other["pid"])):
                    try:
                        os.remove(LOCK_FILE)                      # a stale lock of a process that died
                    except OSError:
                        pass
                    continue
                if time.time() - t0 >= self.wait:
                    raise SystemExit("another heavy run holds %s: %s (pid %s, since %s)"
                                     % (LOCK_FILE, other.get("what", "?"), other.get("pid", "?"), other.get("since", "?")))
                if not told:
                    print("waiting for the heavy lock: %s (pid %s, since %s)" % (other.get("what", "?"), other.get("pid", "?"),
                                                                                 other.get("since", "?")), file=sys.stderr, flush=True)
                    told = True
                time.sleep(2)

    def __exit__(self, *exc):
        global _depth
        _depth -= 1
        try:
            if self.owner:
                if _holder().get("token") == os.environ.get(TOKEN_VAR):
                    try:
                        os.remove(LOCK_FILE)
                    except OSError:
                        pass
                if self.old_token is None:
                    os.environ.pop(TOKEN_VAR, None)
                else:
                    os.environ[TOKEN_VAR] = self.old_token
                self.owner = False
        finally:
            _thread_lock.release()
        return False


# ---------------------------------------------------------------------------------------------------- the gap
def gap_seconds(gap=None):
    if gap is not None:
        return float(gap)
    try:
        return float(os.environ.get("PCB_HEAVY_GAP", GAP))
    except ValueError:
        return GAP


def _pause(gap):
    g = gap_seconds(gap)
    try:
        end, took = (float(x) for x in open(LAST_FILE, encoding="utf-8").read().split())
    except Exception:
        return
    g = min(g, took)
    w = end + g - time.time()
    if 0 < w <= g:
        time.sleep(w)


def _ended(t0):
    try:
        t = time.time()
        with open(LAST_FILE, "w", encoding="utf-8") as f:
            f.write("%.3f %.3f" % (t, t - t0))
    except OSError:
        pass


# ---------------------------------------------------------------------------------------------------- run
def _tail(data, n=20):
    if isinstance(data, bytes):
        data = data.decode("utf-8", "replace")
    return "\n".join((data or "").strip().splitlines()[-n:])


def run(argv, *, check=False, ok=(0,), outputs=(), env=None, cwd=None, timeout=None, stdout=PIPE, stderr=PIPE,
        input=None, text=False, encoding=None, errors=None, gap=None, wait=WAIT, cores=CORES):
    """One heavy command (see the module text) -> subprocess.CompletedProcess with .timed_out and .missing.

    env: variables set on top of this process's environment. stdout / stderr: as for subprocess (PIPE: captured,
    None: passed through, a file). outputs: files the command must write (removed first)."""
    argv = [str(a) for a in argv]
    low_priority(cores)
    with HeavyLock(" ".join(os.path.basename(a) if i == 0 else a for i, a in enumerate(argv[:4])), wait=wait):
        _pause(gap)
        for f in outputs:
            if os.path.exists(f):
                os.remove(f)
        e = dict(os.environ)                                      # now with the token of the lock
        e.update({k: str(v) for k, v in (env or {}).items()})
        for s in (sys.stdout, sys.stderr):                        # a child that writes to the same console comes after
            try:
                s.flush()
            except Exception:
                pass
        t0 = time.time()
        p = subprocess.Popen(argv, stdin=DEVNULL if input is None else PIPE, stdout=stdout, stderr=stderr, cwd=cwd, env=e,
                             creationflags=getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0), text=text,
                             encoding=encoding, errors=errors)
        timed_out = False
        try:
            _limit_child(p, cores)
            try:
                out, err = p.communicate(input, timeout=timeout)
            except subprocess.TimeoutExpired:
                p.kill()
                out, err = p.communicate()
                timed_out = True
        except BaseException:
            p.kill()
            p.wait()
            raise
        finally:
            _ended(t0)
    r = subprocess.CompletedProcess(argv, TIMED_OUT if timed_out else p.returncode, out, err)
    r.timed_out = timed_out
    r.missing = [f for f in outputs if not os.path.isfile(f)]
    if check and (timed_out or (ok is not None and r.returncode not in ok) or r.missing):
        why = ("timed out after %s s" % timeout if timed_out else
               "exit %d" % r.returncode if ok is not None and r.returncode not in ok else
               "no %s" % ", ".join(r.missing))
        said = "\n".join(x for x in (_tail(out), _tail(err)) if x)
        raise HeavyError("%s failed to run: %s%s" % (" ".join(argv), why, ("\n" + said) if said else ""), r.returncode, said)
    return r


def kicad_cli(*args, check=True, ok=None, **kw):
    """kicad-cli <args> through run(); check=True: a non-zero exit (5 too with --exit-code-violations) or a missing
    output raises HeavyError."""
    if ok is None:
        ok = (0, VIOLATIONS) if "--exit-code-violations" in args else (0,)
    return run([paths.KICAD_CLI] + [str(a) for a in args], check=check, ok=ok, **kw)


def kicad_py(target, *args, check=False, cwd=None, **kw):
    """KiCad's python on a Tools module ("Tools.KiCadDesignTools.x.y", run with -m from the repository root) or a
    script file, through run(); check=False: the exit code is the tool's verdict."""
    head = ["-m", target] if target.startswith("Tools.") else [target]
    return run([paths.KICAD_PY] + head + [str(a) for a in args], check=check, cwd=cwd or paths.REPO, **kw)


def rest(seconds=20):
    if seconds > 0:
        time.sleep(seconds)


# ---------------------------------------------------------------------------------------------------- KiCad's state
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
