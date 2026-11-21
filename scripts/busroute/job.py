"""One build of one group: routes file -> geometry checks -> (full build) board file, DRC, metrics, pictures.

The routes file is a Python file in the board's folder:

    BOARD  = "stm32h743_sdram.kicad_pcb"      # relative to the routes file
    ORIGIN = (100, 100)                       # local mm = board-file mm - ORIGIN
    GROUP  = "sdram"                          # the build owns the nets it returns: their old tracks are replaced
    def routes(job):                          # job.board, job.profile, job.sketch, job.fanout(ref), job.bus()
        ...
        return {net: pieces}                  # the routes format (routes.py)
    # optional:
    NETS = [...]            nets that must be routed (a missing one is reported)
    REF = ["FMC_SDCLK", "FMC_SDCLK_R"]        reference of the length table (pieces summed)
    GROUPS = {"data": [...], "addr": [...]}   length groups (default: one group with every net)
    LEN_MAX, VIA_LIMIT, VIA_TARGET            default: the limits of the net class in the .kicad_dru; target none
    VIEWS = [("name", x0, y0, x1, y1, px_per_mm)]
    SKETCH = True           line-order sketch: shape findings are listed but do not fail the build
    OPEN_ENDS = True        routes may end in the open (a fan-out on its own)
    YIELD_NETS = ["GND"]    nets whose pours give way to tracks
    PROFILE = {...}         overrides of profile.Profile
    DRC_IGNORE = {"type": "why"}   DRC item types that do not count against this group
    ROUND = 3               the optimisation round, for the metrics table (PROC-3)
    TUNING                  not yet: serpentines come with the tuning stage (Bus.tuning() lists the sites)
"""
import importlib.util, json, os, shutil, sys, time
from .geom import RouteError
from .board import Board, write
from .profile import Profile
from .routes import F, resolve, expand, lengths
from .checks import geometry, length_findings, is_hard, SHAPE_KINDS
from .bundle import Bus
from .fanout import Fanout
from . import metrics


class Job:
    def __init__(self, board, profile, sketch):
        self.board, self.profile, self.sketch = board, profile, sketch
        self.buses, self.stitch, self.findings, self.notes = [], [], [], []

    def fanout(self, ref):
        return Fanout(self.board, self.profile, ref)

    def bus(self, **kw):
        b = Bus(self.board, self.profile, sketch=self.sketch, **kw)
        self.buses.append(b)
        return b

    def refused(self, result):
        """Report the leads a fan-out could not draw as findings of this build."""
        for ball, why in sorted(result.refused.items()):
            kind = why.split(" ", 1)[0] if why.split(" ", 1)[0] in ("CHANNEL", "VIAPAD", "GAP") else "FAN"
            p = self.board.pads.get("%s.%s" % (result.ref, ball))
            self.findings.append(F(kind if kind != "GAP" else "FAN", "fan-out %s.%s (%s) refused: %s" % (result.ref, ball, p.net if p else "?", why), p.net if p else None, p.pos if p else None))


def load(path):
    spec = importlib.util.spec_from_file_location("busroute_routes_" + os.path.splitext(os.path.basename(path))[0], path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.dirname(os.path.abspath(path)))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    for a in ("BOARD", "GROUP", "routes"):
        if not hasattr(mod, a):
            raise RouteError("%s: %s is missing" % (path, a))
    return mod


def compute(mod, board, profile, sketch, job=None):
    """The geometry stage. -> dict(resolved, segs, vias, lens, findings, job)."""
    job = job or Job(board, profile, sketch)
    R = mod.routes(job)
    extras = list(job.stitch) + [s for b in job.buses for s in b.stitch]
    open_ok = bool(getattr(mod, "OPEN_ENDS", False))
    resolved, f1 = resolve(board, profile, R, open_ok)
    segs, vias = expand(board, profile, resolved, extras)
    lens = lengths(board, resolved)
    opts = {"via_limit": getattr(mod, "VIA_LIMIT", None), "len_max": getattr(mod, "LEN_MAX", None), "yield_nets": getattr(mod, "YIELD_NETS", ())}
    f2, _ = geometry(board, profile, resolved, segs, vias, opts)
    for f in f2:                                            # a gap between two lanes of one bundle is a pitch problem: say which leg
        if f["kind"] == "GAP" and f.get("other") in resolved:
            ctx = next((c for c in (b.context(f["net"], f["other"], f["at"]) for b in job.buses) if c), None)
            if ctx:
                f["kind"], f["text"] = "PITCH", "%s; %s" % (ctx, f["text"])
    seen = {(f["kind"], f["net"], tuple(f["at"] or ())) for f in f1}
    gen = [p for b in job.buses for p in b.problems if not (p["kind"] in SHAPE_KINDS and (p["kind"], p["net"], tuple(p["at"] or ())) in seen)]
    finds = job.findings + gen + f1 + f2 + length_findings(profile, lens, opts)
    missing = [n for n in getattr(mod, "NETS", []) if n not in resolved]
    for n in missing:
        finds.append(F("PATH", "%s is in NETS but has no route" % n, n))
    for f in finds:
        f["hard"] = is_hard(f, sketch)
    return {"resolved": resolved, "segs": segs, "vias": vias, "lens": lens, "findings": finds, "job": job, "missing": missing}


def run(routes_file, fast=False, sketch=False, out=None, write_board=False, refill=True, pictures=True, log=print):
    """-> (metrics dict, exit code). Exit code 0 = passed, 1 = findings, 2 = the description could not be built."""
    t0 = time.time()
    routes_file = os.path.abspath(routes_file)
    mod = load(routes_file)
    pcb = os.path.normpath(os.path.join(os.path.dirname(routes_file), mod.BOARD))
    sketch = sketch or bool(getattr(mod, "SKETCH", False))
    origin = getattr(mod, "ORIGIN", (0.0, 0.0))
    board = Board(pcb, origin)
    profile = Profile.from_project(pcb, getattr(mod, "PROFILE", None))
    jb = Job(board, profile, sketch)
    try:
        c = compute(mod, board, profile, sketch, jb)
    except RouteError as e:
        for f in jb.findings + [p for b in jb.buses for p in b.problems]:      # what was found before it stopped
            log("! %-7s %s" % (f["kind"], f["text"]))
        log("ERROR %s: %s" % (type(e).__name__, e))
        return {"error": str(e), "error_type": type(e).__name__, "findings": jb.findings}, 2
    resolved, segs, vias, lens, finds = c["resolved"], c["segs"], c["vias"], c["lens"], c["findings"]
    hard = sum(1 for f in finds if f["hard"])
    nets = sorted(resolved)
    info = {"group": mod.GROUP, "board": pcb, "routes_file": routes_file, "mode": "sketch" if sketch else "final",
            "built": {"nets": len(nets), "segments": len(segs), "vias": len(vias), "stitching_vias": sum(1 for v in vias if not v[4])},
            "groups": getattr(mod, "GROUPS", None) or {"all": nets}, "ref": getattr(mod, "REF", None),
            "via_limit": getattr(mod, "VIA_LIMIT", None) or (profile.limit(nets[0], "via_max") if nets else None), "via_target": getattr(mod, "VIA_TARGET", None),
            "len_max": getattr(mod, "LEN_MAX", None), "not_routed": c["missing"], "profile": profile.describe()}
    extra = {"round": getattr(mod, "ROUND", None), "notes": c["job"].notes, "tuning_sites": [s for b in c["job"].buses for s in b.tuning()]}
    if getattr(mod, "TUNING", None):
        log("ERROR TUNING is not implemented in this stage (serpentines are drawn by the tuning tool)")
        return {"error": "TUNING given"}, 2
    if fast:
        m = metrics.collect(info, lens, finds, hard, None, extra)
        m["build_seconds"] = round(time.time() - t0, 2)
        m["ok"] = hard == 0
        log(metrics.table(m))
        return m, 0 if m["ok"] else 1
    stem = os.path.splitext(os.path.basename(pcb))[0]
    if write_board:
        if board.locked():
            log("ERROR KiCad has this project open (~*.lck next to the board): nothing was written")
            return {"error": "locked"}, 2
        dst, out = pcb, out or os.path.join(os.path.dirname(pcb), "out", "busroute", mod.GROUP)
        os.makedirs(out, exist_ok=True)
    else:
        out = os.path.abspath(out or os.path.join(os.path.dirname(pcb), "out", "busroute", mod.GROUP))
        os.makedirs(out, exist_ok=True)
        dst = os.path.join(out, stem + ".kicad_pcb")
        if os.path.normcase(dst) == os.path.normcase(pcb):
            raise RouteError("--out is the board's own folder: use --write-board to write the board itself")
        for ext in (".kicad_pro", ".kicad_dru", ".busroute.json"):
            src = os.path.splitext(pcb)[0] + ext
            if os.path.isfile(src):
                shutil.copy(src, os.path.join(out, stem + ext))
            elif os.path.isfile(os.path.join(out, stem + ext)):
                os.remove(os.path.join(out, stem + ext))
    w = write(pcb, dst, mod.GROUP, segs, vias, nets, origin, board.cu)
    ext = metrics.external(dst, nets, refill=refill and bool(board.zones))
    after = Board(dst, origin)                              # what is in the file now
    key = lambda n, l, a, c, wd: (n, l, round(a[0], 5), round(a[1], 5), round(c[0], 5), round(c[1], 5), round(wd, 5))
    want = sorted(key(*s) for s in segs)
    got = sorted(key(n, l, a, c, wd) for n, l, a, c, wd, _ in after.tracks if n in resolved)
    stitch_nets = {v[0] for v in vias if not v[4]}
    vwant = sorted((n, round(p[0], 5), round(p[1], 5), round(d, 5), round(h, 5)) for n, p, d, h, _ in vias)
    vhave = {(n, round(p[0], 5), round(p[1], 5), round(d, 5), round(h, 5)) for n, p, d, h in after.vias}
    conn = after.connectivity(set(resolved))
    ext["connectivity"] = {"nets": len(conn), "fully_connected": sum(1 for a, b in conn.values() if a == b and a > 1),
                           "open": sorted(n for n, (a, b) in conn.items() if a != b or a < 2),
                           "kicad_unconnected_before": board.kicad_unconnected, "kicad_unconnected_after": after.kicad_unconnected}
    same = want == got and all(v in vhave for v in vwant) and sum(1 for v in after.vias if v[0] in resolved) == sum(1 for v in vias if v[4])
    ignore = dict(getattr(mod, "DRC_IGNORE", {}) or {})
    m = metrics.collect(info, lens, finds, hard, ext, extra)
    open_ok = bool(getattr(mod, "OPEN_ENDS", False))
    if open_ok:
        ignore.setdefault("track_dangling", "OPEN_ENDS: the routes end in the open on purpose")
    counted = {k: n for k, n in ext["drc"]["by_type_group"].items() if k not in ignore}
    diff = m["length"]["max_abs_geometry_minus_drc"]
    m.update(written=dict(w, file=dst, matches_model=same), drc_ignored=ignore, drc_counted_group=counted)
    m["ok"] = (hard == 0 and same and not counted and (open_ok or (ext["drc"]["unconnected_group"] == 0 and not ext["connectivity"]["open"]))
               and (diff is None or diff <= 0.002) and (ext["canary"] is None or ext["canary"]["ok"]))
    json.dump(ext["drc"], open(os.path.join(out, "drc_summary.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    if pictures:
        from . import render
        m["pictures"] = render.render(after, out, getattr(mod, "VIEWS", None), nets)
    m["build_seconds"] = round(time.time() - t0, 1)
    json.dump(m, open(os.path.join(out, "metrics.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    txt = metrics.table(m)
    if not same:
        txt += "\n! 板文件里的线和脚本算出的不一致（写入后读回比对失败）\n"
    open(os.path.join(out, "metrics.txt"), "w", encoding="utf-8").write(txt)
    log(txt)
    log("output: %s" % out)
    return m, 0 if m["ok"] else 1
