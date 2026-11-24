"""Build driver: one board folder, one step; the board's data is <board dir>/board.toml.

    python -m Tools.KiCadDesignTools.build <board dir> <step> [--out DIR] [--skip-match] [--upto GROUP] [--no-render] [--dry-run]
    python -m Tools.KiCadDesignTools.build <board dir> compare <out A> <out B>

Run it from the repository root, with KiCad's python (D:\\KiCad\\bin\\python.exe) or any Python >= 3.11; every tool
it starts runs under KiCad's python (Tools.KiCadDesignTools.core.paths.KICAD_PY), the Tools modules as `python -m Tools.KiCadDesignTools.<...>` from the
repository root. Reports go to <out>/<step folder>/, <out> = <board dir>/out unless --out is given.

  project     the project file, the derived footprints, the board's layer table (project.make_project)
  rules       project, rule fixture board, canary, rule matching on the board (--skip-match: left out, run `checks`
              once at the end), length-window rules
  sch         schematic: generate, upgrade, ERC, netlist, PDF; netlist checks ([scripts] sch_check); kicad-happy review
  layout      placement, the line-order sketch on a copy, placement / escape / copper-sketch checks, measured trials
  copper      placement, pours, the power groups on the board and on the sketch copy, refill, measures, pictures, table
  route       every [[route.group]] stripped, placement, pours, the groups rebuilt in order (--upto GROUP: only up to
              that one), refill, DRC, measures, plane slots, escape check, canary, pictures, placement check, table
  finish      after every route: fiducials, inner pours and clean-up, stitching, silkscreen, teardrops, final DRC with
              schematic parity, canary, pictures (FINISH_BOARD=<copy> runs it on a copy, as build.sh did)
  checks      every rule of the rule file matches something (one DRC per rule, one at a time: about 30 minutes)
  publish     release pictures with net names ([scripts] publish)
  all         rules, sch, route, finish
  compare     compare_runs on two out trees, and board_diff on the board copies they hold (<name>.kicad_pcb)
  init NAME, pcb-update: not yet (stages 3 and 5 of the Tools/ consolidation)

Every step first looks for KiCad's lock files in the board folder (hidden ones too) and stops when one is there,
runs below normal priority on four cores (inherited by every child) and holds the machine-wide heavy lock, so that
only one KiCad process runs at a time (Tools.KiCadDesignTools.core.heavy). --dry-run prints the commands instead of running them.

Stage 2 of the consolidation: the steps still call the board folder's own scripts ([scripts] in board.toml) with the
arguments stm32h743_sdram/build.sh gave them; stage 3 replaces those with Tools modules and data files.
"""
import json, os, re, shutil, subprocess, sys, time, collections

from Tools.KiCadDesignTools.core import config, heavy, paths

STEPS = ("project", "rules", "sch", "pcb-update", "layout", "copper", "route", "finish", "checks", "publish", "all",
         "compare", "init")
PROJECT = "Tools.KiCadDesignTools.project.make_project"      # the project file, after every SaveBoard too
KH = os.path.join(os.path.expanduser("~"), ".claude", "plugins", "marketplaces", "kicad-happy", "skills", "kicad", "scripts",
                  "analyze_schematic.py")


def fw(p):
    """Paths as build.sh handed them to the tools (Git Bash turns /e/x into E:/x): forward slashes."""
    return os.path.abspath(p).replace("\\", "/")


# ---------------------------------------------------------------------------------------------------- output filters
def _lines(data, keep):
    parts = data.split(b"\n")
    if parts and parts[-1] == b"":
        parts.pop()
    return b"".join(p + b"\n" for p in parts if keep(p))


def quiet(data):
    """build.sh's quiet(): grep -v "image handler"."""
    return _lines(data, lambda l: b"image handler" not in l)


def q2(data):
    """build.sh's q2() (finish step): the SWIG leak notice cut out, then no "image handler" lines and no empty lines."""
    data = re.sub(rb"swig/python detected a memory leak[^.\n]*found\.", b"", data)
    return _lines(data, lambda l: b"image handler" not in l and len(l) > 0)


def text(data):
    return data.decode("utf-8", "replace").replace("\r\n", "\n")


def grep(data, pattern, invert=False):
    rx = re.compile(pattern)
    return [l for l in text(data).splitlines() if bool(rx.search(l)) != invert]


# every child below normal priority whatever the driver's own class; the affinity (four cores) is inherited from
# the driver (heavy.low_priority)
CHILD_FLAGS = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)


class Stop(Exception):
    def __init__(self, code, why=""):
        super().__init__(why)
        self.code = code


# ---------------------------------------------------------------------------------------------------- the runner
class Runner:
    """Runs (or, with dry=True, prints) the commands of one step, one at a time, from the repository root."""

    def __init__(self, dry):
        self.dry = dry

    def show(self, argv, env=None, out=None, append=False, note=""):
        e = " ".join("%s=%s" % (k, _q(str(v).replace("\n", "\\n"))) for k, v in (env or {}).items())
        cmd = " ".join(_q(a) for a in argv)
        red = (" >> " if append else " > ") + _q(out) if out else ""
        print("%s%s%s%s" % (e + " " if e else "", cmd, red, ("   # " + note) if note else ""))

    def run(self, argv, out=None, append=False, filt=None, env=None, timeout=None, note=""):
        """-> (exit code, output bytes after the filter). The output goes to `out` (a file) when given."""
        argv = [str(a) for a in argv]
        if self.dry:
            self.show(argv, env, out, append, note)
            return 0, b""
        e = dict(os.environ)
        e.update({k: str(v) for k, v in (env or {}).items()})
        try:
            r = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=e, creationflags=CHILD_FLAGS,
                               cwd=paths.REPO, timeout=timeout)
            data, rc = r.stdout, r.returncode
        except subprocess.TimeoutExpired as x:
            data, rc = x.stdout or b"", 124
        if filt:
            data = filt(data)
        if out:
            os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
            with open(out, "ab" if append else "wb") as f:
                f.write(data)
        return rc, data

    def py(self, target, *args, **kw):
        """A Tools module ("Tools.KiCadDesignTools.x.y") or a script file, under KiCad's python."""
        if target.startswith("Tools.KiCadDesignTools."):
            return self.run([paths.KICAD_PY, "-m", target] + list(args), **kw)
        return self.run([paths.KICAD_PY, target] + list(args), **kw)

    def cli(self, *args, **kw):
        return self.run([paths.KICAD_CLI] + list(args), **kw)

    def copy(self, a, b):
        if self.dry:
            print("cp %s %s" % (_q(a), _q(b)))
        else:
            shutil.copyfile(a, b)

    def move(self, a, b):
        if self.dry:
            print("mv -f %s %s" % (_q(a), _q(b)))
        elif os.path.exists(a):
            os.replace(a, b)

    def remove(self, *files):
        if self.dry:
            print("rm -f %s" % " ".join(_q(f) for f in files))
            return
        for f in files:
            if os.path.exists(f):
                os.remove(f)

    def write(self, path, content):
        if self.dry:
            print("echo %s > %s" % (_q(content.rstrip("\n")), _q(path)))
        else:
            with open(path, "w", encoding="utf-8") as f:            # text mode: CRLF on Windows, as tee wrote it
                f.write(content)

    def rest(self, seconds):
        if self.dry:
            print("# rest %d s" % seconds)
        else:
            heavy.rest(seconds)


def _q(s):
    s = str(s)
    return s if s and re.fullmatch(r"[\w@%+=:,./\\-]+", s) else "'" + s.replace("'", "'\\''") + "'"


def echo(lines):
    for l in lines:
        print(l)


# ---------------------------------------------------------------------------------------------------- the steps
class Build:
    def __init__(self, cfg, out_root, dry=False, skip_match=False, upto=None, render=True):
        self.cfg, self.dry, self.skip_match, self.upto, self.render = cfg, dry, skip_match, upto, render
        self.r = Runner(dry)
        self.D = fw(cfg.dir)
        self.N = cfg.name
        self.BRD = self.D + "/" + self.N + ".kicad_pcb"
        self.out_root = fw(out_root)

    # helpers ---------------------------------------------------------------------------------------------------
    def out(self, step):
        folder = self.cfg.get("build.out.%s" % step, step)
        O = self.out_root + "/" + folder
        if not self.dry:
            os.makedirs(O, exist_ok=True)
        return O

    def script(self, key):
        rel = self.cfg.need("scripts.%s" % key)
        return self.D + "/" + rel

    def L(self, text_):
        print(text_)

    def pr(self, data, n=None):
        lines = text(data).splitlines()
        echo(lines if n is None else lines[:n])

    def group(self, name):
        for g in self.cfg.groups:
            if g["name"] == name:
                return g
        raise config.ConfigError("no [[route.group]] named %s" % name)

    def busroute(self, routes, flags, O_group, log, env=None, after=()):
        """busroute.build <routes> <flags> --out <O_group> <after> (build.sh's order; build.py takes flags anywhere)."""
        args = [self.D + "/" + routes] + flags + ["--out", O_group] + list(after)
        return self.r.py("Tools.KiCadDesignTools.routing.busroute.build", *args, out=log, env=env)

    def escape(self, board, run, out, append):
        args = [board]
        for ref in run["refs"]:
            args += ["--ref", ref]
        if run.get("window"):
            args += ["--window"] + [_num(v) for v in run["window"]]
        return args

    def view(self, board, O, v):
        args = [board, O] + list(v["layers"])
        if "scale" in v:
            args += ["--scale", _num(v["scale"])]
        if v.get("window"):
            args += ["--window"] + [_num(x) for x in v["window"]]
        if v.get("name"):
            args += ["--name", v["name"]]
        if v.get("slots"):
            args += ["--slots", O + "/" + v["slots"]]
        if v.get("via_labels"):
            args += ["--via-labels"]
        rc, data = self.r.py(self.script("copper_view"), *args, filt=quiet)
        if data:
            print(" ".join(text(data).splitlines()) + " ")
        if v.get("rename"):
            a, b = v["rename"]
            self.r.move(O + "/" + a, O + "/" + b)

    def place_check(self, O, show):
        lay = self.cfg.get("layout", {})
        args = [self.BRD]
        if lay.get("allow_under"):
            args += ["--allow-under", ",".join(lay["allow_under"])]
        for ref, side in (lay.get("edges") or {}).items():
            args += ["--edge", "%s=%s" % (ref, side)]
        if lay.get("not_supply"):
            args += ["--not-supply", ",".join(lay["not_supply"])]
        if lay.get("silk_refs"):
            args += ["--silk-refs", lay["silk_refs"]]
        args += ["--json", O + "/place_check.json"]
        rc, data = self.r.py("Tools.KiCadDesignTools.placement.place_check", *args, out=O + "/place_check.txt")
        echo(show(data))
        return rc

    def project_quiet(self):
        """The project file again after a SaveBoard (KiCad rewrites it; its source is make_project and board.toml)."""
        self.r.py(PROJECT, self.D)

    def match_skipped(self, O, tee=True):
        msg = "dru_match skipped (SKIP_DRU_MATCH): run build.sh finish-checks once at the end"
        self.r.write(O + "/dru_match.txt", msg + "\n")
        if tee:
            print(msg)

    # steps -----------------------------------------------------------------------------------------------------
    def step_project(self):
        rc, data = self.r.py(PROJECT, self.D, filt=quiet)
        self.pr(data)
        return rc

    def step_rules(self):
        O, T0 = self.out("rules"), time.time()
        rc, data = self.r.py(PROJECT, self.D, filt=quiet)
        self.pr(data)
        # 1. every rule behaves as written (fixture board with the project's own rules and stackup)
        FX, _ = self.r.py("Tools.KiCadDesignTools.rules.fixture", self.D, O, out=O + "/fixture.log")
        if not self.dry and os.path.isfile(O + "/rules_fixture.txt"):
            lines = open(O + "/rules_fixture.txt", encoding="utf-8").read().splitlines()
            echo(lines[:1] + [l for l in lines if l.startswith("FAIL")])
        # 2. the real board: rule file loaded, rules that match nothing, length windows current
        rc, data = self.r.py("Tools.KiCadDesignTools.rules.dru_canary", self.BRD, filt=quiet, out=O + "/canary.txt")
        self.pr(data)
        if self.skip_match:
            self.match_skipped(O)
            DM = "-"
        else:
            DM, data = self.r.py("Tools.KiCadDesignTools.rules.dru_match", self.BRD, "--json", O + "/dru_match.json", out=O + "/dru_match.txt")
            echo(text(data).splitlines()[-1:])
        rc, data = self.r.py("Tools.KiCadDesignTools.rules.len_rules", self.BRD, filt=quiet, out=O + "/len_rules.txt")
        self.pr(data)
        print("rules step: %d s; fixture exit %s, dru_match exit %s (2 = the board has no objects yet)" % (time.time() - T0, FX, DM))
        return FX

    def step_sch(self):
        O, T0 = self.out("sch"), time.time()
        rc, data = self.r.run(["sh", fw(os.path.join(paths.PACKAGE, "schematic", "sch_build.sh")), self.D, O], filt=quiet,
                              out=O + "/sch_build.log", note="Git Bash sh")
        self.pr(data, 1)
        echo(grep(data, "ERC messages"))
        if not self.dry and os.path.isfile(O + "/erc.rpt"):
            c = collections.Counter(l for l in open(O + "/erc.rpt", encoding="utf-8", errors="replace").read().splitlines() if l.startswith("["))
            echo("%7d %s" % (n, l) for l, n in sorted(c.items()))
        SC, data = self.r.py(self.script("sch_check"), O + "/" + self.N + ".net", filt=quiet, out=O + "/sch_check.txt")
        echo(l[:400] for l in text(data).splitlines() if l)
        if self.cfg.get("schematic.review", False):
            if os.path.isfile(KH):
                # kicad-happy's analyzer (RUL-9) under the system Python, in the out folder (it makes analysis/ there)
                self.r.run([shutil.which("python") or "python", KH, self.D + "/" + self.N + ".kicad_sch", "--text", "--stage",
                            "schematic"], note="cwd %s; stdout > kicad_happy_sch.txt, stderr > kicad_happy_sch.err" % O) if self.dry \
                    else self._kicad_happy(O)
            else:
                print("kicad-happy analyzer not found: schematic review not run")
        print("sch step: %d s; sch_check exit %s" % (time.time() - T0, SC))
        return SC

    def _kicad_happy(self, O):
        py = shutil.which("python") or "python"
        with open(O + "/kicad_happy_sch.txt", "wb") as so, open(O + "/kicad_happy_sch.err", "wb") as se:
            subprocess.run([py, KH, self.D + "/" + self.N + ".kicad_sch", "--text", "--stage", "schematic"], stdout=so, stderr=se,
                           stdin=subprocess.DEVNULL, cwd=O)
        n = sum(1 for l in open(O + "/kicad_happy_sch.txt", encoding="utf-8", errors="replace") if l.startswith("  ["))
        print("kicad-happy: %d findings in %s/kicad_happy_sch.txt" % (n, O))

    def step_layout(self):
        O, T0 = self.out("layout"), time.time()
        lay = self.cfg.need("layout")
        sk = lay["sketch"]
        SKO = self.D + "/" + sk["out"]
        SK = SKO + "/" + self.N + ".kicad_pcb"
        rc, data = self.r.py(self.script("place"), filt=quiet)
        self.pr(data)
        SB, data = self.busroute(sk["routes"], ["--sketch"], SKO, O + "/sketch_build.txt")
        print("== line-order sketch on the placed board")
        echo(grep(data, r"^\[间距\]|^结论") or text(data).splitlines()[-3:])
        echo(grep(data, r"^  ! "))
        print("== placement (Tools.KiCadDesignTools.placement.place_check)")
        PC = self.place_check(O, lambda d: grep(quiet(d), r"keep-out \[", invert=True))
        print("== ways out of the fine-pitch parts (Tools.KiCadDesignTools.placement.escape_check)")
        for run in lay.get("escape", []):
            rc, data = self.r.py("Tools.KiCadDesignTools.placement.escape_check", *self.escape(SK, run, None, False), "--json", O + "/" + run["json"], filt=quiet)
            self.pr(data)
        print("== copper region sketch (Tools.KiCadDesignTools.copper.cu_sketch check)")
        rc, data = self.r.py("Tools.KiCadDesignTools.copper.cu_sketch", "check", self.D + "/" + self.cfg.need("copper.sketch"), "--board", self.BRD, filt=quiet)
        echo(text(data).splitlines()[-40:])
        print("== measured trial checks")
        rc, data = self.r.py(self.script("layout_probe"), "--json", O + "/layout_probe.json", filt=quiet)
        self.pr(data)
        print("layout step: %d s; sketch build exit %s, place_check exit %s" % (time.time() - T0, SB, PC))
        return 0

    def step_copper(self):
        O, T0 = self.out("copper"), time.time()
        cu, lay = self.cfg.need("copper"), self.cfg.need("layout")
        BRD = self.BRD
        SKO = self.D + "/" + lay["sketch"]["out"]
        SK = SKO + "/" + self.N + ".kicad_pcb"
        CR = self.script("copper_report")
        sketch = self.D + "/" + cu["sketch"]
        print("== placement and pours")
        self.r.py(CR, "unfill", BRD, filt=quiet)
        self.r.py(self.script("place"), filt=quiet)
        rc, data = self.r.py("Tools.KiCadDesignTools.copper.cu_sketch", "check", sketch, "--board", BRD, filt=quiet, out=O + "/sketch_check.txt")
        rc, data = self.r.py("Tools.KiCadDesignTools.copper.cu_sketch", "apply", sketch, BRD, filt=quiet)
        echo(grep(data, r"^warning: a ~", invert=True))
        print("== line-order sketch on a copy of the board (the obstacles of the power groups)")
        self.r.py(CR, "unfill", SK, filt=quiet)
        SB, data = self.busroute(lay["sketch"]["routes"], ["--sketch"], SKO, O + "/sketch_build.txt", after=["--no-refill", "--no-pictures"])
        echo(grep(data, r"^\[间距\]|^结论") or text(data).splitlines()[-3:])
        codes = []
        for g in cu.get("group", []):
            print("== group %s on %s" % (g["name"], g.get("board", "board")))
            env = {k: self._fill(v, O, SK) for k, v in (g.get("env") or {}).items()}
            flags = ["--write-board"] + list(g.get("flags", [])) + ["--no-refill", "--no-pictures"]
            rc, data = self.busroute(g["file"], flags, O + "/" + g["out"], O + "/" + g["out"] + "_build.txt", env=env)
            codes.append(rc)
            echo(grep(data, r"^写入|^\[间距\]|^结论|^ERROR") or text(data).splitlines()[-5:])
            if g.get("after") == "refill_board":
                print("== refill and save (kicad-cli), measure")
                self.r.cli("pcb", "drc", "--refill-zones", "--save-board", "--severity-all", "--units", "mm", "--format", "json", "-o",
                           O + "/drc.json", BRD)
                self.r.py("Tools.KiCadDesignTools.copper.cu_sketch", "measure", BRD, "--drc", O + "/drc.json", "--json", O + "/measure.json",
                          "--skip-areas", ",".join(cu["skip_areas"]), out=O + "/measure.txt")
                rc, data = self.r.py("Tools.KiCadDesignTools.copper.pour_islands", BRD, *cu["pour_check"], filt=quiet, out=O + "/pour_islands.txt")
                echo(grep(data, " 0 without", invert=True))
        self.r.cli("pcb", "drc", "--refill-zones", "--save-board", "--severity-all", "--units", "mm", "--format", "json", "-o",
                   O + "/sketch_drc.json", SK)
        rc, data = self.r.py(CR, "slots", SK, O, filt=quiet)
        echo(text(data).splitlines()[-12:])
        first = True
        for run in lay.get("escape", []):
            self.r.py("Tools.KiCadDesignTools.placement.escape_check", *self.escape(SK, run, None, False), "--json", O + "/" + run["json"], filt=quiet,
                      out=O + "/escape.txt", append=not first)
            first = False
        print("== pictures of the filled layers (qualitative review only)")
        for v in cu.get("views", []):
            self.view(SK if v.get("board") == "sketch" else BRD, O, v)
        self.project_quiet()
        print("== copper table")
        rc, data = self.r.py(CR, "table", BRD, O, filt=quiet, env={"COPPER_SECONDS": "%d s" % (time.time() - T0)})
        self.pr(data)
        print("copper step: %d s; sketch build exit %s, group exits %s" % (time.time() - T0, SB, codes))
        return 0

    def _fill(self, v, O, SK=None, obstacles=None):
        return (v.replace("{out}", O).replace("{board}", self.BRD).replace("{sketch}", SK or "")
                 .replace("{obstacles}", obstacles or ""))

    def step_route(self):
        O, T0 = self.out("route"), time.time()
        BRD, rt = self.BRD, self.cfg.need("route")
        groups = self.cfg.groups
        names = [g["name"] for g in groups]
        if self.upto and self.upto not in names:
            raise config.ConfigError("--upto %s: no such group (%s)" % (self.upto, ", ".join(names)))
        build = names[:names.index(self.upto) + 1] if self.upto else names
        rc, data = self.r.py(PROJECT, self.D, filt=quiet)
        echo(grep(data, "layer table"))
        print("== placement and pours (the groups are stripped first, then rebuilt in order)")
        CR = self.script("copper_report")
        self.r.py(CR, "unfill", BRD, filt=quiet)
        obst_group = rt.get("obstacles_group")
        OBST = O + "/obstacles.kicad_pcb"
        if obst_group:
            # the serpentines of this group need the other groups' copper as obstacles (tune.py, TUNE_OBSTACLES): a copy
            # of the board as the last build left it, without the group's own copper
            self.r.copy(BRD, OBST)
            self.r.copy(self.D + "/" + self.N + ".busroute.json", O + "/obstacles.busroute.json")
            self.r.py(CR, "strip", OBST, obst_group, filt=quiet)
        self.r.py(CR, "strip", BRD, *names, filt=quiet)
        if rt.get("orphans", True):
            rc, data = self.r.py(CR, "orphans", BRD, filt=quiet, out=O + "/orphans.txt")
            self.pr(data)
        self.r.py(self.script("place"), filt=quiet)
        sketch = self.D + "/" + self.cfg.need("copper.sketch")
        rc, data = self.r.py("Tools.KiCadDesignTools.copper.cu_sketch", "check", sketch, "--board", BRD, filt=quiet, out=O + "/sketch_check.txt")
        rc, data = self.r.py("Tools.KiCadDesignTools.copper.cu_sketch", "apply", sketch, BRD, filt=quiet)
        echo(grep(data, r"^warning: a ~", invert=True))
        codes = {}
        for g in groups:
            if g["name"] not in build:
                continue
            print("== group %s (%s) on the board" % (g["name"], g["file"]))
            env = {k: self._fill(v, O, obstacles=OBST) for k, v in (g.get("env") or {}).items()}
            rc, data = self.busroute(g["file"], ["--write-board", "--no-refill", "--no-pictures"], O + "/" + g["name"],
                                     O + "/" + g["name"] + "_build.txt", env=env)
            codes[g["name"]] = rc
            echo(grep(data, r"^写入|^\[间距\]|^结论|^ERROR|^  ! [A-Z]") or text(data).splitlines()[-5:])
        print("== refill and save (kicad-cli), DRC, measure")
        self.r.cli("pcb", "drc", "--refill-zones", "--save-board", "--severity-all", "--units", "mm", "--format", "json", "-o",
                   O + "/drc.json", BRD)
        self.project_quiet()
        cu = self.cfg.need("copper")
        self.r.py("Tools.KiCadDesignTools.copper.cu_sketch", "measure", BRD, "--drc", O + "/drc.json", "--json", O + "/measure.json", "--skip-areas",
                  ",".join(cu["skip_areas"]), out=O + "/measure.txt")
        for s in rt.get("slots", []):
            args = ["slots", BRD, O, "--window", s["name"]] + [_num(v) for v in s["window"]]
            if s.get("layers"):
                args += ["--layers"] + list(s["layers"])
            if s.get("stem"):
                args += ["--stem", s["stem"]]
            if s.get("part_b"):
                args += ["--part-b", O + "/" + s["part_b"]]
            rc, data = self.r.py(CR, *args, filt=quiet)
            echo(grep(data, s["show"]) if s.get("show") else text(data).splitlines()[-int(s.get("tail", 8)):])
        rc, data = self.r.py("Tools.KiCadDesignTools.copper.pour_islands", BRD, *cu["pour_check"], filt=quiet, out=O + "/pour_islands.txt")
        self.pr(data)
        first = True
        for run in rt.get("escape", []):
            self.r.py("Tools.KiCadDesignTools.placement.escape_check", *self.escape(BRD, run, None, False), "--json", O + "/" + run["json"], filt=quiet,
                      out=O + "/escape.txt", append=not first)
            first = False
        self.r.py("Tools.KiCadDesignTools.rules.dru_canary", BRD, filt=quiet, out=O + "/canary.txt")
        if self.skip_match:
            self.match_skipped(O, tee=False)
        else:
            self.r.py("Tools.KiCadDesignTools.rules.dru_match", BRD, "--json", O + "/dru_match.json", out=O + "/dru_match.txt")
        print("== pictures (qualitative review only)")
        for v in rt.get("views", []):
            self.view(BRD, O, v)
        print("== placement (Tools.KiCadDesignTools.placement.place_check, as in the layout step)")
        PC = self.place_check(O, lambda d: grep(d, r"^\[(outside|overlap|keepout|under)\]"))
        print("== route table")
        listed = "\n" + "".join("%s %s\n" % (g["name"], g["file"]) for g in groups if g.get("in_report") and g["name"] in build)
        RT, data = self.r.py(self.script("route_report"), BRD, O, out=O + "/table.log",
                             env={rt.get("report_env", "ROUTE2_GROUPS"): listed, "ROUTE2_SECONDS": "%d s" % (time.time() - T0)})
        lines = text(quiet(data)).splitlines()
        for l in lines:
            print(l)
            if l.startswith("== SDRAM"):
                break
        print("route step: %d s; group exits %s, place_check exit %s, table exit %s" % (time.time() - T0, codes, PC, RT))
        return 0

    def step_finish(self):
        O, T0 = self.out("finish"), time.time()
        fin = self.cfg.need("finish")
        copy = os.environ.get("FINISH_BOARD")
        BRD = fw(copy) if copy else self.BRD
        rest = int(fin.get("rest", 20))
        F = self.script("finish")
        CR = self.script("copper_report")

        def refill(js):
            self.r.cli("pcb", "drc", "--refill-zones", "--save-board", "--severity-all", "--units", "mm", "--format", "json", "-o", js, BRD)
            self.r.rest(rest)

        def p(rc_data):
            self.pr(rc_data[1])
            return rc_data[0]
        self.r.remove(O + "/clean_shape.txt", O + "/clean_anchor.txt")
        print("== strip, fiducials")
        p(self.r.py(CR, "unfill", BRD, filt=q2))
        p(self.r.py(F, "strip", BRD, filt=q2))
        # the fiducials stay first: their keep-outs must be on the board before the pours, the vias and the silkscreen
        p(self.r.py(F, "fiducials", BRD, filt=q2))
        print("== pours on the inner signal layers, pour keep-outs, clean-up of narrow copper and small pieces")
        p(self.r.py(F, "pours", BRD, O, filt=q2))
        refill(O + "/drc_pour.json")
        for P in range(1, int(fin.get("clean_passes", 2)) + 1):
            CL, data = self.r.py(F, "clean", BRD, O, "shape", out=O + "/clean.log")
            self.pr(q2(data))
            if self.dry:
                print("# exit 10 (keep-outs added): refill %s/drc_clean%d.json and run the next pass" % (O, P))
            if CL != 10:
                break
            refill(O + "/drc_clean%d.json" % P)
        print("== ground stitching vias")
        p(self.r.py(F, "pieces", BRD, O, "before", filt=q2))
        p(self.r.py(F, "stitch", BRD, O, filt=q2))
        refill(O + "/drc_stitch.json")
        p(self.r.py(F, "stitch", BRD, O, "--pieces", filt=q2))      # the pieces the first pass's vias made or left on one via
        refill(O + "/drc_stitch2.json")
        # an inner piece the stitching could not hold (no legal site) goes by a keep-out
        CL, data = self.r.py(F, "clean", BRD, O, "anchor", out=O + "/clean.log")
        self.pr(q2(data))
        if self.dry:
            print("# exit 10 (keep-outs added): refill %s/drc_anchor.json" % O)
        if CL == 10:
            refill(O + "/drc_anchor.json")
        p(self.r.py(F, "pieces", BRD, O, "after", filt=q2))
        rc, data = self.r.py("Tools.KiCadDesignTools.copper.pour_islands", BRD, *self.cfg.need("copper.pour_check"), filt=q2, out=O + "/pour_islands.txt")
        self.pr(data)
        p(self.r.py(F, "report", BRD, O, "after", filt=q2))
        print("== silkscreen")
        p(self.r.py(CR, "unfill", BRD, filt=q2))
        p(self.r.py(F, "silk", BRD, O, filt=q2))
        print("== teardrops")
        p(self.r.py(F, "teardrops", BRD, filt=q2))
        self.r.rest(rest)
        if not copy:
            self.project_quiet()                                    # SaveBoard may have rewritten the project file
        print("== final DRC (schematic parity), canary, rules matching nothing")
        self.r.cli("pcb", "drc", "--refill-zones", "--save-board", "--severity-all", "--schematic-parity", "--units", "mm", "--format",
                   "json", "-o", O + "/drc.json", BRD)
        self.r.rest(rest)
        if not copy:
            self.project_quiet()
        self.drc_summary(O + "/drc.json", O + "/drc_summary.txt")
        rc, data = self.r.py("Tools.KiCadDesignTools.rules.dru_canary", BRD, filt=quiet, out=O + "/canary.txt")
        self.pr(data)
        s = fin.get("slots")
        if s:
            # the planes after the new ground vias: no plane-net via cut off, feed necks, longest slots
            args = ["slots", BRD, O, "--window", s["name"]] + [_num(v) for v in s["window"]] + ["--stem", s["stem"]]
            if s.get("part_b"):
                args += ["--part-b", self.out_root + "/" + self.cfg.get("build.out.route", "route") + "/" + s["part_b"]]
            rc, data = self.r.py(CR, *args, filt=quiet)
            echo(grep(data, s["show"]))
        print("== pictures")
        rd = fin.get("render") or {}
        # 3D renders (user 2026-11-24): only under the limits every child gets here (below-normal priority, the
        # driver's four cores, one heavy run), a pause before and after each; --no-render or render.enabled = false
        # leaves them out
        sides = rd.get("sides", ["top", "bottom"]) if (rd.get("enabled", True) and self.render) else []
        if not sides:
            print("3D renders left out (--no-render / [finish] render.enabled = false)")
        elif not self.dry:
            self.r.rest(rest)
        for side in sides:
            rc, _ = self.r.cli("pcb", "render", "--side", side, "--width", rd.get("width", 1600), "--height", rd.get("height", 1410),
                               "--quality", rd.get("quality", "basic"), "--background", "opaque", "-o", O + "/render_%s.png" % side, BRD,
                               timeout=int(rd.get("timeout", 180)))
            if rc:
                print("render %s failed or took over %d s" % (side, int(rd.get("timeout", 180))))
            self.r.rest(rest)
        p(self.r.py(self.script("finish_view"), BRD, O, filt=q2))
        print("finish step: %d s" % (time.time() - T0))
        return 0

    def drc_summary(self, js, out):
        if self.dry:
            print("# DRC summary of %s > %s" % (js, out))
            return
        d = json.load(open(js, encoding="utf-8"))
        c = collections.Counter(v["type"] for v in d["violations"])
        p = collections.Counter(v["type"] for v in d.get("schematic_parity", []))
        s = ("DRC by type: %s\nunconnected: %d\nschematic parity by type: %s\n"
             % (", ".join("%s %d" % kv for kv in sorted(c.items())) or "none", len(d["unconnected_items"]),
                ", ".join("%s %d" % kv for kv in sorted(p.items())) or "none"))
        print(s, end="")
        self.r.write(out, s)

    def step_checks(self):
        O, T0 = self.out("checks"), time.time()
        rc, data = self.r.py("Tools.KiCadDesignTools.rules.dru_match", self.BRD, "--json", O + "/dru_match.json", out=O + "/dru_match.txt")
        echo(text(data).splitlines()[-1:])
        print("checks step: %d s" % (time.time() - T0))
        return 0

    def step_publish(self):
        T0 = time.time()
        rc, data = self.r.py(self.script("publish"), "--rest", int(self.cfg.get("publish.rest", 20)), filt=quiet)
        self.pr(data)
        print("publish step: %d s" % (time.time() - T0))
        return rc

    def step_all(self):
        code = 0
        for s in ("rules", "sch", "route", "finish"):
            print("==== %s" % s)
            code = getattr(self, "step_" + s)() or code
        return code


def _num(v):
    """A number of board.toml as build.sh wrote it on the command line (27, 28.5, -1): write ints as ints there."""
    return str(v)


def compare(a, b, name):
    from Tools.KiCadDesignTools.analysis import board_diff, compare_runs
    code = compare_runs.main([a, b])
    pa, pb = os.path.join(a, name + ".kicad_pcb"), os.path.join(b, name + ".kicad_pcb")
    if os.path.isfile(pa) and os.path.isfile(pb):
        code = board_diff.main([pa, pb]) or code
    else:
        print("board_diff: no %s.kicad_pcb in both folders" % name)
    return code


def main(argv):
    flags = {"--dry-run": False, "--skip-match": False, "--no-render": False}
    out = upto = None
    args = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in flags:
            flags[a] = True
        elif a in ("--out", "--upto"):
            if i + 1 >= len(argv):
                print("%s needs a value" % a)
                return 2
            out, upto = (argv[i + 1], upto) if a == "--out" else (out, argv[i + 1])
            i += 1
        elif a.startswith("--"):
            print("unknown option %s\n" % a + __doc__)
            return 2
        else:
            args.append(a)
        i += 1
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)     # progress shows in a log file as it happens
    except Exception:
        pass
    if args[:1] == ["init"]:
        print("init: not yet (stage 5 of the Tools/ consolidation: a new board folder from templates/)")
        return 2
    if len(args) < 2 or args[1] not in STEPS:
        print(__doc__)
        return 2
    try:
        cfg = config.load(args[0])
    except config.ConfigError as e:
        print("board.toml: %s" % e)
        return 2
    step = args[1]
    if step == "compare":
        if len(args) != 4:
            print("compare needs two out folders")
            return 2
        return compare(args[2], args[3], cfg.name)
    if step == "pcb-update":
        print("pcb-update: not yet (stage 3 of the Tools/ consolidation)")
        return 2
    if len(args) != 2:
        print(__doc__)
        return 2
    b = Build(cfg, out or os.path.join(cfg.dir, "out"), dry=flags["--dry-run"], skip_match=flags["--skip-match"], upto=upto,
              render=not flags["--no-render"])
    if flags["--dry-run"]:
        print("# dry run: %s %s (out %s)" % (cfg.name, step, b.out_root))
        return getattr(b, "step_" + step.replace("-", "_"))()
    locks = heavy.kicad_lock(cfg.dir)
    if locks and not (step == "finish" and os.environ.get("FINISH_BOARD")):
        print("KiCad has the project open (%s): nothing written" % ", ".join(locks))
        return 2
    others = heavy.running(("kicad-cli.exe",))
    if others:
        print("a KiCad process is running already (%s): one at a time" % ", ".join(others))
        return 2
    print("# %s" % heavy.low_priority())
    with heavy.HeavyLock("Tools.KiCadDesignTools.build %s %s" % (cfg.name, step)):
        try:
            return getattr(b, "step_" + step.replace("-", "_"))()
        except Stop as s:
            return s.code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
