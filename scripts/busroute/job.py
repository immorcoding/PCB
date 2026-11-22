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
    SHARED = True           the group owns no net: it replaces only what it wrote itself last time (found by
                            position, recorded in <board>.busroute.json), so the copper other groups put on the
                            same nets stays (ground and power ties next to the bus groups)
    ALLOW_VIA_ON = ["U601.33"]     pads that may carry a via (approved via-in-pad exceptions)
    ROUND = 3               the optimisation round, for the metrics table (PROC-3)
    TUNING = {              length tuning: arc serpentines on the sites (tune.py has the shapes and the limits)
        "groups": {"lane0": {"nets": [...], "spread": 5.0}, ...},   # longest - shortest of a group must end <= spread
        "margin": 0.3,      # each short net is aimed at (longest of its group - spread + margin)
        "radius": 0.25, "amp": 0.5, "amp_max": 2.0,                 # largest bend radius; hump height from amp up to amp_max
        "pitch": {"default": 0.3, "FMC_SDCLK_R": 0.5},              # leg centre distance, per net; bends are pitch / 2
        "end": 0.35, "clr": 0.19, "area_gap": 0.127,                # straight between a corner and the first arc; copper to
                                                                    # other copper; copper to a rule-area edge
        "keep": 0.7}        # (optional) straight left at both ends of a block inside its site (RTE-2)
                            Sites: Bundle.slot(net, leg, s0, length, side, free, pitch) on a bundle lane, and
                            job.slot(net, layer, p0, p1, side="R"|"L"|"both", pitch=None) on any straight piece of a
                            net's route (hand-written ones too). A net's sites are used in the order they were written.
                            A net that cannot reach its target is a TUNE finding "missing X mm at site ..." (RTE-15).
                            Not with SHARED. `build.py <routes> --tuning-budget` prints targets, needs and the RTE-2
                            capacity of every site at amp and amp_max, and draws nothing.
"""
import importlib.util, json, os, shutil, sys, time
from .geom import RouteError
from .board import Board, write, old_items
from .profile import Profile
from .routes import F, resolve, expand, lengths
from .checks import geometry, length_findings, is_hard, SHAPE_KINDS
from .bundle import Bus, SEQ
from .fanout import Fanout
from . import metrics, tune


class Job:
    def __init__(self, board, profile, sketch):
        self.board, self.profile, self.sketch = board, profile, sketch
        self.buses, self.stitch, self.findings, self.notes, self.sites = [], [], [], [], []

    def fanout(self, ref):
        return Fanout(self.board, self.profile, ref)

    def bus(self, **kw):
        b = Bus(self.board, self.profile, sketch=self.sketch, **kw)
        self.buses.append(b)
        return b

    def slot(self, net, layer, p0, p1, side="R", pitch=None):
        """A serpentine site on the straight piece of `net`'s route on `layer` from p0 to p1 (local mm; any two
        points of one straight segment). side: humps to the right ("R") or left ("L") of p0 -> p1 on the picture,
        or "both"; pitch: None = TUNING's pitch for the net. Used only when the routes file has TUNING."""
        s = tune.Site(net, layer, p0, p1, side, pitch, seq=next(SEQ))
        self.sites.append(s)
        return s

    def all_sites(self):
        return sorted([tune.from_slot(s) for b in self.buses for bd in b.bundles for s in bd.slots] + self.sites, key=lambda s: s.seq)

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


def compute(mod, board, profile, sketch, job=None, budget=False):
    """The geometry stage. -> dict(resolved, segs, vias, arcs, lens, natural, tuning, findings, job).
    budget=True: stop after the natural lengths and return the tuning budget (tune.Tuning.budget) as "budget"."""
    shared = bool(getattr(mod, "SHARED", False))
    job = job or Job(board, profile, sketch)
    R = mod.routes(job)
    extras = list(job.stitch) + [s for b in job.buses for s in b.stitch]
    open_ok = bool(getattr(mod, "OPEN_ENDS", False))
    resolved, f1 = resolve(board, profile, R, open_ok)
    segs, vias = expand(board, profile, resolved, extras)
    lens = natural = lengths(board, resolved)
    opts = {"via_limit": getattr(mod, "VIA_LIMIT", None), "len_max": getattr(mod, "LEN_MAX", None), "yield_nets": getattr(mod, "YIELD_NETS", ()),
            "allow_via_on": getattr(mod, "ALLOW_VIA_ON", ()), "shared": shared,
            "skip_items": old_items(board.path, mod.GROUP) if shared else None}
    arcs, tun, f3 = [], None, []
    spec = getattr(mod, "TUNING", None)
    if spec or budget:
        if not spec:
            raise RouteError("%s has no TUNING: nothing to budget" % mod.GROUP)
        if shared:
            raise RouteError("TUNING cannot be used in a SHARED group")
        T = tune.Tuning(spec, board, profile, resolved, segs, vias, lens, job.all_sites(), opts)
        if budget:
            return {"budget": T.budget(), "natural": natural, "job": job}
        tun = T.run()
        segs, arcs, lens, f3 = T.segs, T.arcs, T.lens, T.findings
    f2, _ = geometry(board, profile, resolved, segs, vias, opts, arcs=arcs)
    for f in f2:                                            # a gap between two lanes of one bundle is a pitch problem: say which leg
        if f["kind"] == "GAP" and f.get("other") in resolved:
            ctx = next((c for c in (b.context(f["net"], f["other"], f["at"]) for b in job.buses) if c), None)
            if ctx:
                f["kind"], f["text"] = "PITCH", "%s; %s" % (ctx, f["text"])
    seen = {(f["kind"], f["net"], tuple(f["at"] or ())) for f in f1}
    gen = [p for b in job.buses for p in b.problems if not (p["kind"] in SHAPE_KINDS and (p["kind"], p["net"], tuple(p["at"] or ())) in seen)]
    finds = job.findings + gen + f1 + f2 + f3 + length_findings(profile, lens, opts)
    missing = [n for n in getattr(mod, "NETS", []) if n not in resolved]
    for n in missing:
        finds.append(F("PATH", "%s is in NETS but has no route" % n, n))
    for f in finds:
        f["hard"] = is_hard(f, sketch)
    return {"resolved": resolved, "segs": segs, "vias": vias, "arcs": arcs, "lens": lens, "natural": natural, "tuning": tun,
            "findings": finds, "job": job, "missing": missing}


def budget(routes_file, log=print):
    """Planning mode (--tuning-budget): targets, needs and site capacities by RTE-2's formula; draws and writes
    nothing. -> (budget dict, exit code 0 = every net's sites can take its need at amp_max, 1 = not, 2 = error)."""
    t0 = time.time()
    routes_file = os.path.abspath(routes_file)
    mod = load(routes_file)
    pcb = os.path.normpath(os.path.join(os.path.dirname(routes_file), mod.BOARD))
    board = Board(pcb, getattr(mod, "ORIGIN", (0.0, 0.0)))
    profile = Profile.from_project(pcb, getattr(mod, "PROFILE", None))
    try:
        c = compute(mod, board, profile, bool(getattr(mod, "SKETCH", False)), budget=True)
    except RouteError as e:
        log("ERROR %s: %s" % (type(e).__name__, e))
        return {"error": str(e)}, 2
    b = c["budget"]
    b["seconds"] = round(time.time() - t0, 2)
    log(metrics.budget_table(b, mod.GROUP, os.path.basename(routes_file)))
    return b, 0 if not b["short"] else 1


def run(routes_file, fast=False, sketch=False, out=None, write_board=False, refill=True, pictures=True, log=print, ignore_lock=False):
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
    resolved, segs, vias, arcs, lens, finds = c["resolved"], c["segs"], c["vias"], c["arcs"], c["lens"], c["findings"]
    hard = sum(1 for f in finds if f["hard"])
    nets = sorted(resolved)
    info = {"group": mod.GROUP, "board": pcb, "routes_file": routes_file, "mode": "sketch" if sketch else "final",
            "built": {"nets": len(nets), "segments": len(segs), "vias": len(vias), "stitching_vias": sum(1 for v in vias if not v[4])},
            "groups": getattr(mod, "GROUPS", None) or {"all": nets}, "ref": getattr(mod, "REF", None),
            "via_limit": getattr(mod, "VIA_LIMIT", None) or (profile.limit(nets[0], "via_max") if nets else None), "via_target": getattr(mod, "VIA_TARGET", None),
            "len_max": getattr(mod, "LEN_MAX", None), "not_routed": c["missing"], "profile": profile.describe()}
    extra = {"round": getattr(mod, "ROUND", None), "notes": c["job"].notes, "tuning_sites": [s for b in c["job"].buses for s in b.tuning()]}
    if c["tuning"] is not None:
        info["built"]["arcs"] = len(arcs)
        extra["tuning"] = c["tuning"]
        extra["tuning"]["natural"] = {n: v["length"] for n, v in c["natural"].items()}
        extra["tuning"]["caps"] = {n: getattr(mod, "LEN_MAX", None) or profile.limit(n, "length_max") for n in nets}
    if fast:
        m = metrics.collect(info, lens, finds, hard, None, extra)
        m["build_seconds"] = round(time.time() - t0, 2)
        m["ok"] = hard == 0
        log(metrics.table(m))
        return m, 0 if m["ok"] else 1
    stem = os.path.splitext(os.path.basename(pcb))[0]
    if write_board:
        if board.locked() and not ignore_lock:
            log("ERROR KiCad has this project open (~*.lck next to the board): nothing was written")
            return {"error": "locked"}, 2
        if board.locked():
            log("warning: KiCad has this project open (~*.lck): reload the board there (File > Revert)")
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
    shared = bool(getattr(mod, "SHARED", False))
    w = write(pcb, dst, mod.GROUP, segs, vias, nets, origin, board.cu, shared=shared, arcs=arcs)
    ext = metrics.external(dst, nets, refill=refill and bool(board.zones))
    after = Board(dst, origin)                              # what is in the file now
    key = lambda n, l, a, c, wd: (n, l, round(a[0], 5), round(a[1], 5), round(c[0], 5), round(c[1], 5), round(wd, 5))
    want = sorted(key(*s) for s in segs)
    got = sorted(key(n, l, a, c, wd) for n, l, a, c, wd, is_arc in after.tracks if n in resolved and not is_arc)
    akey = lambda n, l, a, m, c, wd: (n, l) + tuple(round(v, 5) for p in (a, m, c) for v in p) + (round(wd, 5),)
    awant, agot = sorted(akey(*x) for x in arcs), sorted(akey(*x) for x in after.arc_items if x[0] in resolved)
    arcs_same = awant == agot if not getattr(mod, "SHARED", False) else set(awant) <= set(agot)
    stitch_nets = {v[0] for v in vias if not v[4]}
    vwant = sorted((n, round(p[0], 5), round(p[1], 5), round(d, 5), round(h, 5)) for n, p, d, h, _ in vias)
    vhave = {(n, round(p[0], 5), round(p[1], 5), round(d, 5), round(h, 5)) for n, p, d, h in after.vias}
    conn = after.connectivity(set(resolved))
    ext["connectivity"] = {"nets": len(conn), "fully_connected": sum(1 for a, b in conn.values() if a == b and a > 1),
                           "open": sorted(n for n, (a, b) in conn.items() if a != b or a < 2),
                           "kicad_unconnected_before": board.kicad_unconnected, "kicad_unconnected_after": after.kicad_unconnected}
    if shared:                                              # other groups' copper on the same nets is not ours to count
        import collections
        same = not (collections.Counter(want) - collections.Counter(got)) and all(v in vhave for v in vwant)
    else:
        same = want == got and all(v in vhave for v in vwant) and sum(1 for v in after.vias if v[0] in resolved) == sum(1 for v in vias if v[4])
    same = same and arcs_same
    ignore = dict(getattr(mod, "DRC_IGNORE", {}) or {})
    m = metrics.collect(info, lens, finds, hard, ext, extra)
    open_ok = bool(getattr(mod, "OPEN_ENDS", False))
    if open_ok:
        ignore.setdefault("track_dangling", "OPEN_ENDS: the routes end in the open on purpose")
    counted = {k: n for k, n in ext["drc"]["by_type_group"].items() if k not in ignore}
    diff = m["length"]["max_abs_geometry_minus_drc"]
    m.update(written=dict(w, file=dst, matches_model=same), drc_ignored=ignore, drc_counted_group=counted)
    m["ok"] = (hard == 0 and same and not counted and (open_ok or (ext["drc"]["unconnected_group"] == 0 and not ext["connectivity"]["open"]))
               and (open_ok or diff is None or diff <= 0.002) and (ext["canary"] is None or ext["canary"]["ok"]))   # open routes have no pad-to-pad length
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
