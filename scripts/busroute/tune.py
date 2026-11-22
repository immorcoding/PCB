"""Length tuning: arc serpentines on the straights a routes file names as sites (project rules RTE-2, RTE-7, RTE-15).

The routes file (job.py) gives

    TUNING = {"groups": {"lane0": {"nets": [...], "spread": 5.0}, ...},
              "margin": 0.3, "radius": 0.25, "amp": 0.5, "amp_max": 2.0,
              "pitch": {"default": 0.3, "FMC_SDCLK_R": 0.5},
              "end": 0.35, "clr": 0.19, "area_gap": 0.127, "keep": 0.7}

and the sites: Bundle.slot(net, leg, s0, length, side, free, pitch) on a bundle lane, job.slot(net, layer, p0, p1,
side, pitch) on any straight piece of a net's route (a hand-written one too). A net may have several sites; they
are used in the order they were written.

What is drawn (all numbers mm):
  target(group) = longest natural length of the group - spread + margin; need(net) = max(0, target - natural).
                  Lengths as routes.lengths counts them (track + the layers a via really crosses). The longest net of
                  a group is never lengthened.
  pitch p         centre distance of neighbouring legs: the site's pitch, else TUNING pitch[net], else pitch["default"].
  radius          every bend has radius r = p / 2 (semicircular tops and bottoms, as RTE-2's formula assumes);
                  `radius` is the largest radius allowed, a pitch above 2 x radius is refused.
  single side     n humps of one height a (centre line to the centre line of the hump top) towards the site's side:
                  arc 90 out, leg a - 2r, arc 180, leg a - 2r, arc 180 (bottom) ... arc 90 back in.
                  Takes 2pn of the straight and adds n (2a - (4 - pi) p) = n (2a - 0.858 p)             (RTE-2)
  "both"          n humps of one height alternating sides, the legs cross the line: takes p (n + 1),
                  adds 2na - 0.429 p (n + 1).
  a               the lowest height >= amp that adds exactly the need with as many humps as the site takes; raised
                  above amp only when the site is too short at amp, never above amp_max. A leg is absent (a = 2r)
                  or at least min_seg + 0.005 long.
  small           a need below one hump of height amp is one element: a bump (three arcs th, -2th, th, radius r)
                  when it is below a hump of height 2r, else one lower hump (or, when that hump's legs would be
                  shorter than min_seg + 0.005, a leg-less hump of a larger radius). Never a lower tail hump in a block.
  partial         when no block adds the whole need, the one that adds the most is drawn (as many humps as the
                  site takes, the tallest height >= amp that keeps the limits) and the rest goes to the net's next site.
  keep            straight left between the block and each end of the site (RTE-2: 0.7); never below `end`.
  placement       the block starts `keep` after the site's p0 (blocks of one bundle start on one line, RTE-7) and
                  slides towards p1 in 0.05 steps while a limit is broken; nets are drawn neediest first.
Hard limits (what breaks one is not drawn; a need that does not fit becomes a TUNE finding "missing X mm"; a net that
is short of its target but inside the window [longest - spread, longest] all the same is only a NOTE):
  `end` straight between a corner (via, pad) of the route and the first arc; no piece shorter than min_seg;
  `clr` from the serpentine copper to every other copper on the layer (tracks, arcs, pads, vias, the net's own
  other pieces; the net's own copper is ignored closer than r to the site's line), never below the DRC clearance of
  the place; via holes keep the hole clearance; `area_gap` from every rule-area edge; the board-edge clearance;
  outside keep-outs and other nets' pours (YIELD_NETS excepted). Tested on the centre line sampled every 0.01 mm.
  A sample that is no closer to another net's copper than the straight it replaces (at the same station u, v = 0)
  is not held to `clr`: the neighbours of a bundle lane at the lane pitch (0.25 here: 0.148 mm edge to edge, legal
  for DRC, below clr) stay where they are on the side away from the humps (2026-11-22, stop 6 of the H743 board).
  Only the obstacles and pours near each trial element are tested (bounding box + the largest clearance).

Output: the group's segments with the serpentines cut in, PCB arcs (net, layer, start, mid, end, width), the new
lengths, a report for the metrics table and the findings (TUNE, ARC). Points are rounded to 1 nm, as written.
"""
import math
from .geom import RouteError, pt_seg, seg_poly_dist
from .checks import Scene, Item
from .routes import F

Q = math.pi / 2
STEP = 0.01               # sampling of the serpentine copper for the clearance tests
SLIDE = 0.05              # offset step when a block is moved along its site
NM = 6                    # rounding of written points (1 nm)
DEFAULTS = {"margin": 0.3, "radius": 0.25, "amp": 0.5, "amp_max": 2.0, "pitch": {"default": 0.3},
            "end": 0.35, "clr": 0.19, "area_gap": 0.127, "keep": 0.7}


class Site:
    """A straight of `net` on `layer` from p0 to p1 that may carry a serpentine; humps towards side R (right of
    p0 -> p1 on the picture, y down), L or both."""
    def __init__(self, net, layer, p0, p1, side="R", pitch=None, label=None, seq=0):
        if side not in ("R", "L", "both"):
            raise RouteError("site of %s: side must be 'R', 'L' or 'both', not %r" % (net, side))
        self.net, self.layer, self.side, self.pitch, self.seq = net, layer, side, pitch, seq
        self.p0, self.p1 = (float(p0[0]), float(p0[1])), (float(p1[0]), float(p1[1]))
        self.label = label or "site %s (%g, %g)-(%g, %g)" % (layer, self.p0[0], self.p0[1], self.p1[0], self.p1[1])
        self.L = math.dist(self.p0, self.p1)
        if self.L < 1e-6:
            raise RouteError("%s of %s has no length" % (self.label, net))
        self.U = ((self.p1[0] - self.p0[0]) / self.L, (self.p1[1] - self.p0[1]) / self.L)
        self.N = (-self.U[1], self.U[0])

    def world(self, u, v):
        return (self.p0[0] + u * self.U[0] + v * self.N[0], self.p0[1] + u * self.U[1] + v * self.N[1])

    def local(self, p):
        dx, dy = p[0] - self.p0[0], p[1] - self.p0[1]
        return dx * self.U[0] + dy * self.U[1], dx * self.N[0] + dy * self.N[1]


def from_slot(s):
    g = s.geometry()
    return Site(g["net"], g["layer"], g["from"], g["to"], g["side"], s.pitch,
                "slot %s leg %d s %g..%g" % (g["bundle"], g["leg"], s.s0, s.s0 + s.length), s.seq)


# ---------------------------------------------------------------- shapes (u along the site, v towards side +1)
class Turtle:
    def __init__(self, u=0.0):
        self.p, self.h, self.prims = (u, 0.0), 0.0, []

    def fwd(self, d):
        if d < 1e-9:
            return
        q = (self.p[0] + d * math.cos(self.h), self.p[1] + d * math.sin(self.h))
        self.prims.append(("seg", self.p, q)); self.p = q

    def arc(self, r, ang):                                  # ang > 0 turns towards +v
        sg = 1 if ang > 0 else -1
        c = (self.p[0] - sg * r * math.sin(self.h), self.p[1] + sg * r * math.cos(self.h))
        a0 = math.atan2(self.p[1] - c[1], self.p[0] - c[0])
        pt = lambda t: (c[0] + r * math.cos(a0 + t), c[1] + r * math.sin(a0 + t))
        q = pt(ang)
        self.prims.append(("arc", self.p, pt(ang / 2), q, r)); self.p = q; self.h += ang


def draw(el, u0=0.0, sd=1):
    """Primitives of one element from (u0, 0) heading +u. el = ("single", n, a, r) | ("both", n, a, r) | ("bump", rb, th)."""
    T = Turtle(u0)
    if el[0] == "single":
        _, n, a, r = el
        T.arc(r, Q * sd)
        for i in range(n):
            T.fwd(a - 2 * r); T.arc(r, -2 * Q * sd); T.fwd(a - 2 * r)
            T.arc(r, (2 * Q if i < n - 1 else Q) * sd)
    elif el[0] == "both":
        _, n, a, r = el
        T.arc(r, Q * sd); T.fwd(a - 2 * r)
        for i in range(n):
            T.arc(r, -2 * Q * sd)
            if i < n - 1:
                T.fwd(2 * a - 2 * r); sd = -sd
        T.fwd(a - 2 * r); T.arc(r, Q * sd)
    else:
        _, rb, th = el
        T.arc(rb, th * sd); T.arc(rb, -2 * th * sd); T.arc(rb, th * sd)
    return T.prims, T.p[0] - u0


def base_of(el):
    if el[0] == "single":
        return 2 * el[1] * 2 * el[3]
    if el[0] == "both":
        return 2 * el[3] * (el[1] + 1)
    return 4 * el[1] * math.sin(el[2])


def gain_of(el):
    """Length added by an element (exact, unrounded)."""
    if el[0] == "single":
        _, n, a, r = el
        return n * (2 * a - (8 - 2 * math.pi) * r)
    if el[0] == "both":
        _, n, a, r = el
        return 2 * n * a - (4 - math.pi) * r * (n + 1)
    _, rb, th = el
    return 4 * rb * (th - math.sin(th))


def _bisect(f, lo, hi):
    for _ in range(80):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if f(m) < 0 else (lo, m)
    return (lo + hi) / 2


def bump(g, r, min_piece):
    """The small element that adds g: three arcs (th, -2th, th); radius r when g is at most a hump of height 2r
    (each arc at least min_piece long, else a larger radius), above that a hump of height 2rb without legs."""
    if g <= (2 * math.pi - 4) * r + 1e-12:
        th = _bisect(lambda t: 4 * r * (t - math.sin(t)) - g, 1e-6, Q)
        if r * th >= min_piece:
            return ("bump", r, th)
        th = _bisect(lambda t: 4 * min_piece * (1 - math.sin(t) / t) - g, 1e-6, Q)
        return ("bump", min_piece / th, th)
    return ("bump", g / (2 * math.pi - 4), Q)


def humps(el):
    """(count, height) of an element for the reports."""
    if el[0] in ("single", "both"):
        return el[1], el[2]
    return 1, el[1] * (1 - math.cos(el[2])) * 2


# ---------------------------------------------------------------- arcs from three points
def circle(s, m, e):
    """(centre, radius, start angle, signed sweep) of the arc through s, m, e."""
    d = 2 * (s[0] * (m[1] - e[1]) + m[0] * (e[1] - s[1]) + e[0] * (s[1] - m[1]))
    if abs(d) < 1e-15:
        return None
    ux = ((s[0] ** 2 + s[1] ** 2) * (m[1] - e[1]) + (m[0] ** 2 + m[1] ** 2) * (e[1] - s[1]) + (e[0] ** 2 + e[1] ** 2) * (s[1] - m[1])) / d
    uy = ((s[0] ** 2 + s[1] ** 2) * (e[0] - m[0]) + (m[0] ** 2 + m[1] ** 2) * (s[0] - e[0]) + (e[0] ** 2 + e[1] ** 2) * (m[0] - s[0])) / d
    r = math.hypot(s[0] - ux, s[1] - uy)
    a0, am, a1 = (math.atan2(p[1] - uy, p[0] - ux) for p in (s, m, e))
    sw = (a1 - a0) % (2 * math.pi)
    if (am - a0) % (2 * math.pi) > sw:
        sw -= 2 * math.pi
    return (ux, uy), r, a0, sw


def arc_len(s, m, e):
    c = circle(s, m, e)
    return math.dist(s, e) if c is None else c[1] * abs(c[3])


def arc_points(s, m, e, step):
    c = circle(s, m, e)
    if c is None:
        return [s, e]
    (ux, uy), r, a0, sw = c
    n = max(2, int(math.ceil(abs(sw) * r / step)))
    return [s] + [(ux + r * math.cos(a0 + sw * i / n), uy + r * math.sin(a0 + sw * i / n)) for i in range(1, n)] + [e]


def arc_dirs(s, m, e):
    """Unit travel directions at the start and at the end of the arc s -> m -> e."""
    (ux, uy), r, a0, sw = circle(s, m, e)
    sg = 1 if sw > 0 else -1
    a1 = a0 + sw
    return (-sg * math.sin(a0), sg * math.cos(a0)), (-sg * math.sin(a1), sg * math.cos(a1))


def chords(s, m, e, step=0.02):
    """Chord segments of an arc and the largest sagitta (to grow their half width by)."""
    pts = arc_points(s, m, e, step)
    c = circle(s, m, e)
    sag = 0.0 if c is None else max(c[1] - math.sqrt(max(0.0, c[1] ** 2 - (math.dist(a, b) / 2) ** 2)) for a, b in zip(pts, pts[1:]))
    return list(zip(pts, pts[1:])), sag


def _r(p):
    return (round(p[0], NM), round(p[1], NM))


def _dist(q, o):
    """Distance from point q to the centre geometry of an obstacle item (its half width not taken off)."""
    if o.kind == "seg":
        return pt_seg(q, o.a, o.b)[0]
    if o.kind == "round":
        return math.dist(q, o.a)
    return seg_poly_dist(q, q, o.poly)[0]


# ---------------------------------------------------------------- settings
class Settings:
    def __init__(self, d):
        if not isinstance(d, dict) or "groups" not in d:
            raise RouteError("TUNING needs a dict with 'groups'")
        bad = set(d) - set(DEFAULTS) - {"groups"}
        if bad:
            raise RouteError("TUNING: unknown key(s) %s" % ", ".join(sorted(bad)))
        v = dict(DEFAULTS); v.update(d)
        self.groups = {}
        for g, spec in d["groups"].items():
            if "nets" not in spec or "spread" not in spec:
                raise RouteError("TUNING group %s needs 'nets' and 'spread'" % g)
            self.groups[g] = {"nets": list(spec["nets"]), "spread": float(spec["spread"])}
        seen = {}
        for g, spec in self.groups.items():
            for n in spec["nets"]:
                if n in seen:
                    raise RouteError("TUNING: %s is in group %s and in group %s" % (n, seen[n], g))
                seen[n] = g
        self.group_of = seen
        for k in ("margin", "radius", "amp", "amp_max", "end", "clr", "area_gap", "keep"):
            setattr(self, k, float(v[k]))
        self.pitch = v["pitch"] if isinstance(v["pitch"], dict) else {"default": float(v["pitch"])}
        if "default" not in self.pitch:
            raise RouteError("TUNING pitch needs a 'default'")
        if self.keep < self.end - 1e-9:
            raise RouteError("TUNING: keep %.3f is below end %.3f (the straight at a block's ends is never shorter than end)" % (self.keep, self.end))
        if self.amp_max < self.amp - 1e-9:
            raise RouteError("TUNING: amp_max %.3f is below amp %.3f" % (self.amp_max, self.amp))
        for g, spec in self.groups.items():
            if spec["spread"] < self.margin:
                raise RouteError("TUNING group %s: spread %.3f is below the margin %.3f" % (g, spec["spread"], self.margin))

    def pitch_of(self, net, given=None):
        return float(given if given is not None else self.pitch.get(net, self.pitch["default"]))

    def r_of(self, p, net):
        if p / 2 > self.radius + 1e-9:
            raise RouteError("TUNING %s: pitch %.3f needs bends of radius %.3f (semicircles, RTE-2), above radius %.3f" % (net, p, p / 2, self.radius))
        return p / 2

    def describe(self):
        return {"groups": self.groups, "margin": self.margin, "radius": self.radius, "amp": self.amp, "amp_max": self.amp_max,
                "pitch": self.pitch, "end": self.end, "clr": self.clr, "area_gap": self.area_gap, "keep": self.keep}


def capacity(L, p, a, side, keep):
    """RTE-2: what a site of straight length L takes at height a (no clearance test). -> (humps, mm)."""
    room = L - 2 * keep
    if side == "both":
        n = max(0, int(math.floor(room / p + 1e-9)) - 1)
        return n, (2 * n * a - (4 - math.pi) / 2 * p * (n + 1)) if n else 0.0
    n = max(0, int(math.floor(room / (2 * p) + 1e-9)))
    return n, n * (2 * a - (4 - math.pi) * p)


# ---------------------------------------------------------------- the stage
class Tuning:
    def __init__(self, spec, board, profile, resolved, segs, vias, lens, sites, opts=None):
        self.S = Settings(spec)
        self.board, self.profile, self.resolved, self.opts = board, profile, resolved, opts or {}
        self.segs, self.vias, self.natural = list(segs), list(vias), lens
        self.sites = sorted(sites, key=lambda s: s.seq)
        self.arcs, self.blocks, self.findings = [], [], []
        self.areas = {n: board.areas[n] for n in board.rule_areas(profile.area_names)}
        self.leg_min = profile.min_seg + 0.005              # 0.1 exactly rounds below DRC's min_segment on a diagonal
        for s in self.sites:
            if s.layer not in board.cu:
                raise RouteError("%s of %s: unknown layer %r" % (s.label, s.net, s.layer))

    # ---- what each net needs
    def targets(self):
        out = {}
        for g, spec in self.S.groups.items():
            have = [n for n in spec["nets"] if n in self.natural]
            if not have:
                continue
            ref = max(have, key=lambda n: (self.natural[n]["length"], n))
            tgt = self.natural[ref]["length"] - spec["spread"] + self.S.margin
            out[g] = {"ref": ref, "longest": self.natural[ref]["length"], "spread": spec["spread"], "target": round(tgt, 4),
                      "nets": have, "missing_nets": [n for n in spec["nets"] if n not in self.natural],
                      "need": {n: round(max(0.0, tgt - self.natural[n]["length"]), 4) if n != ref else 0.0 for n in have}}
        return out

    def budget(self):
        """Per group: target, per net natural length, need, the capacity of each site at amp and amp_max (RTE-2)."""
        T = self.targets()
        out = {"settings": self.S.describe(), "groups": {}, "short": [], "sites_without_group": []}
        for g, t in T.items():
            rows = []
            for n in t["nets"]:
                sites = []
                for s in self.sites:
                    if s.net != n:
                        continue
                    p = self.S.pitch_of(n, s.pitch)
                    k0, c0 = capacity(s.L, p, self.S.amp, s.side, self.S.keep)
                    k1, c1 = capacity(s.L, p, self.S.amp_max, s.side, self.S.keep)
                    sites.append({"site": s.label, "layer": s.layer, "length": round(s.L, 4), "side": s.side, "pitch": p,
                                  "humps": k0, "cap_amp": round(c0, 4), "cap_amp_max": round(c1, 4)})
                cap = sum(x["cap_amp_max"] for x in sites)
                rows.append({"net": n, "natural": self.natural[n]["length"], "need": t["need"][n], "sites": sites,
                             "cap_amp": round(sum(x["cap_amp"] for x in sites), 4), "cap_amp_max": round(cap, 4)})
                if t["need"][n] > 1e-3 and cap < t["need"][n] - 1e-9:
                    out["short"].append({"net": n, "group": g, "need": t["need"][n], "cap_amp_max": round(cap, 4)})
            out["groups"][g] = dict(t, rows=rows)
        out["sites_without_group"] = [s.label + " (" + s.net + ")" for s in self.sites if s.net not in self.S.group_of]
        return out

    # ---- the obstacles
    def _scene(self, segs, arcs):
        """Every copper item the group's serpentines must keep clear of, with the group's own copper. Arc chords
        carry their block number in self._blk."""
        owned = set() if self.opts.get("shared") else set(self.resolved)
        sc = Scene(self.board, self.profile, skip_nets=owned, skip_items=self.opts.get("skip_items"))
        self._blk = {}
        legs = {(x[0], x[1], x[2], x[3]): b["id"] for b in self.blocks for x in b["segs"][1:-1]}
        for n, lay, a, c, w in segs:
            it = sc.seg(n, lay, a, c, w)
            sc.add(it)
            if (n, lay, a, c) in legs:
                self._blk[id(it)] = legs[(n, lay, a, c)]
        for n, p, d, h, _ in self.vias:
            sc.add(sc.via(n, p, d, h))
        for k, (n, lay, s, m, e, w) in enumerate(arcs):
            self._add_arc(sc, n, lay, s, m, e, w, self._arc_block.get(k))
        return sc

    def _add_arc(self, sc, n, lay, s, m, e, w, blk):
        cs, sag = chords(s, m, e)
        for a, c in cs:
            it = Item("seg", n, lay, a, c, w / 2 + sag, "arc of %s on %s" % (n, lay), new=True)
            sc.add(it)
            self._blk[id(it)] = blk

    def _need(self, net, o):
        pr = self.profile
        drc = pr.clr_area if o.area else max(pr.clr(net), pr.clr(o.net))
        return max(self.S.clr, drc)

    def _limits(self, site, hw, net, layer):
        """The tests one sample point must pass: a function (point, v, rline) -> None or (reason, gap)."""
        sc, S, pr = self.sc, self.S, self.profile
        x0, y0 = min(site.p0[0], site.p1[0]), min(site.p0[1], site.p1[1])
        x1, y1 = max(site.p0[0], site.p1[0]), max(site.p0[1], site.p1[1])
        reach = S.amp_max + 1.0
        box = Item("seg", None, layer, (x0 - reach, y0 - reach), (x1 + reach, y1 + reach), 0.0, "box")
        on_line = lambda p: abs((p[0] - site.p0[0]) * site.N[0] + (p[1] - site.p0[1]) * site.N[1]) < 1e-5
        obs = []
        for o in sc.near(box, 0.5):
            if o.layer is not None and o.layer != layer:
                continue
            if o.net == net and o.kind == "seg" and on_line(o.a) and on_line(o.b):
                continue                                    # the straight the block sits on
            obs.append(o)
        rects = [(nm, a["rect"]) for nm, a in self.areas.items() if layer in a["layers"]]
        edges = self.board.edges
        keep = [k for k in self.board.keepouts if k["tracks"] and layer in k["layers"]]
        zones = [z for z in self.board.zones if z["net"] != net and layer in z["layers"] and z["net"] not in self.opts.get("yield_nets", ())]

        def test(q, v, rline, base=None, obs=obs, zones=zones):
            for nm, R in rects:
                dx = max(R[0] - q[0], 0.0, q[0] - R[2])
                dy = max(R[1] - q[1], 0.0, q[1] - R[3])
                if math.hypot(dx, dy) < hw + S.area_gap - 1e-7:
                    return "closer than %.3f to the rule area %s" % (S.area_gap, nm), math.hypot(dx, dy) - hw
            for a, c in edges:
                if pt_seg(q, a, c)[0] < hw + pr.edge_clr - 1e-7:
                    return "closer than %.3f to the board edge" % pr.edge_clr, None
            for k in keep:
                if seg_poly_dist(q, q, k["poly"])[0] <= hw:
                    return "inside the keep-out %r" % k["name"], None
            for z in zones:
                if seg_poly_dist(q, q, z["poly"])[0] <= hw:
                    return "in the pour of %s" % (z["net"] or "no net"), None
            for o in obs:
                if o.net == net and abs(v) < rline - 1e-6:
                    continue                                # still on the original line
                if o.kind == "seg":
                    d = pt_seg(q, o.a, o.b)[0]
                elif o.kind == "round":
                    d = math.dist(q, o.a)
                else:
                    d = seg_poly_dist(q, q, o.poly)[0]
                need = self._need(net, o)
                if d - o.r - hw < need + 5e-4:
                    if base is not None and o.net != net and d >= _dist(base, o) - 1e-6:
                        continue                            # no closer than the straight it replaces (a lane neighbour)
                    who = o.desc if o.net != net else "its own " + o.desc
                    return "closer than %.3f to the %s" % (need, who), d - o.r - hw
                if o.hole > 0 and math.dist(q, o.a) - o.hole - hw < pr.hole_clr + 5e-4:
                    return "closer than %.3f to the hole of the %s" % (pr.hole_clr, o.desc), None
            return None
        test.obs, test.zones = obs, zones
        test.reach = hw + max([S.clr, pr.clr_area, pr.hole_clr] + [pr.clr(o.net) for o in obs if o.net]) + 0.01
        return test

    def _fits(self, site, el, u0, sd, hw, test):
        """None when the element drawn at u0 on side sd keeps every limit, else the reason."""
        prims, _ = draw(el, u0, sd)
        rline = el[3] if el[0] != "bump" else min(el[1], 0.05)        # own copper is ignored this close to the line
        pts = []
        for pr in prims:
            if pr[0] == "seg":
                L = math.dist(pr[1], pr[2])
                if L < self.profile.min_seg - 1e-7:
                    return "a straight piece of %.3f mm" % L
                n = max(1, int(math.ceil(L / STEP)))
                pts += [(pr[1][0] + (pr[2][0] - pr[1][0]) * i / n, pr[1][1] + (pr[2][1] - pr[1][1]) * i / n) for i in range(n + 1)]
            else:
                if arc_len(pr[1], pr[2], pr[3]) < self.profile.min_seg - 1e-7:
                    return "an arc of %.3f mm" % arc_len(pr[1], pr[2], pr[3])
                pts += arc_points(pr[1], pr[2], pr[3], STEP)
        # only the obstacles and pours near this element (speed: the site's list covers the whole site + amp_max)
        W = [site.world(u, v) for u, v in pts]
        bx0, by0 = min(p[0] for p in W), min(p[1] for p in W)
        bx1, by1 = max(p[0] for p in W), max(p[1] for p in W)
        rr = test.reach
        def close(o):
            if o.kind == "round":
                xs_, ys_ = (o.a[0],), (o.a[1],)
            elif o.kind == "seg":
                xs_, ys_ = (o.a[0], o.b[0]), (o.a[1], o.b[1])
            else:
                xs_, ys_ = [p[0] for p in o.poly], [p[1] for p in o.poly]
            m = rr + o.r + max(o.hole, 0.0)
            return min(xs_) - m <= bx1 and max(xs_) + m >= bx0 and min(ys_) - m <= by1 and max(ys_) + m >= by0
        obs = [o for o in test.obs if close(o)]
        zones = [z for z in test.zones if min(p[0] for p in z["poly"]) <= bx1 + rr and max(p[0] for p in z["poly"]) >= bx0 - rr
                 and min(p[1] for p in z["poly"]) <= by1 + rr and max(p[1] for p in z["poly"]) >= by0 - rr]
        for (u, v), q in zip(pts, W):
            bad = test(q, v, rline, site.world(u, 0.0), obs, zones)
            if bad:
                return bad[0]
        return None

    # ---- where a block may go on a site
    def _locate(self, site):
        """-> (u range allowed for a block [lo, hi], piece index finder) or a reason string."""
        net = site.net
        hit = None
        for pc in self.resolved.get(net, []):
            if pc[0] != site.layer:
                continue
            for a, c in zip(pc[1], pc[1][1:]):
                ua, va = site.local(a)
                uc, vc = site.local(c)
                if abs(va) < 1e-4 and abs(vc) < 1e-4 and min(ua, uc) <= 1e-4 and max(ua, uc) >= site.L - 1e-4:
                    hit = (min(ua, uc), max(ua, uc))
                    break
            if hit:
                break
        if not hit:
            return "is not on a straight of the route of %s on %s" % (net, site.layer)
        lo = max(self.S.keep, hit[0] + self.S.end)
        hi = min(site.L - self.S.keep, hit[1] - self.S.end)
        return (lo, hi)

    def _pieces(self, site):
        """[(index, lo, hi)] of the group segments of the site's net on its line (u range along the site)."""
        out = []
        for k, (n, lay, a, c, w) in enumerate(self.segs):
            if n != site.net or lay != site.layer:
                continue
            ua, va = site.local(a)
            uc, vc = site.local(c)
            if abs(va) <= 1e-5 and abs(vc) <= 1e-5:
                out.append((k, min(ua, uc), max(ua, uc)))
        return out

    def _piece(self, pieces, u0, u1):
        """Index of the group segment (one width) that holds [u0, u1] with min_seg to spare at both ends, or None."""
        m = self.profile.min_seg
        for k, lo, hi in pieces:
            if lo + m - 1e-7 <= u0 and u1 <= hi - m + 1e-7:
                return k
        return None

    def _offsets(self, rng, base):
        lo, hi = rng
        if hi - lo < base - 1e-9:
            return []
        out = [lo + SLIDE * i for i in range(int((hi - lo - base) / SLIDE + 1e-9) + 1)]
        if hi - base - out[-1] > 1e-6:
            out.append(hi - base)
        return out

    def _try(self, site, el, sides, rng, tests):
        """First (u0, sd) where el fits, scanning from the start of the site (blocks of one bundle start on one
        line, RTE-7). tests caches the limits per track width. -> ((u0, sd, piece), None) or (None, reason)."""
        base = base_of(el)
        why = "the site is %.2f mm, the block needs %.2f plus %.2f at each end" % (site.L, base, self.S.keep)
        if "pieces" not in tests:
            tests["pieces"] = self._pieces(site)
        for u0 in self._offsets(rng, base):
            k = self._piece(tests["pieces"], u0, u0 + base)
            if k is None:
                why = "no straight of one width holds the block"
                continue
            hw = self.segs[k][4] / 2
            if hw not in tests:
                tests[hw] = self._limits(site, hw, site.net, site.layer)
            for sd in sides:
                bad = self._fits(site, el, u0, sd, hw, tests[hw])
                if bad is None:
                    return (u0, sd, k), None
                why = bad
        return None, why

    def _legal(self, a, r):
        return abs(a - 2 * r) < 1e-9 or a - 2 * r >= self.leg_min - 1e-9

    def _exact(self, R, kind, r, nmax):
        """Elements that add exactly R, best first (RTE-7: the lowest height >= amp, raised only for a short site)."""
        S, out = self.S, []
        if kind == "single":
            K = (8 - 2 * math.pi) * r
            g = 2 * S.amp - K
            n0 = int(math.floor(R / g + 1e-9)) if g > 0 else 0
            for n in range(min(n0, nmax), 0, -1):
                a = (R / n + K) / 2
                if a <= S.amp_max + 1e-9 and self._legal(a, r):
                    out.append(("single", n, a, r))
        else:
            c = (4 - math.pi) * r
            n0 = int(math.floor((R + c) / (2 * S.amp - c) + 1e-9))
            for n in range(min(n0, nmax), 0, -1):
                a = (R + c * (n + 1)) / (2 * n)
                if a <= S.amp_max + 1e-9 and self._legal(a, r):
                    out.append(("both", n, a, r))
        if R < 2 * S.amp - (8 - 2 * math.pi) * r - 1e-9:   # less than one hump of height amp: one small element
            a1 = (R + (8 - 2 * math.pi) * r) / 2
            if a1 >= 2 * r - 1e-9 and self._legal(a1, r) and nmax >= 1:
                out.append(("single", 1, max(a1, 2 * r), r))
            else:
                out.append(bump(R, r, self.profile.min_seg))
        return out

    def _place(self, site, R):
        """Draw what fits of R mm on one site. -> (block dict or None, reason when not all of R was drawn)."""
        S = self.S
        p = S.pitch_of(site.net, site.pitch)
        r = S.r_of(p, site.net)
        if p < self.profile.width(site.net) + self.profile.clr(site.net) - 1e-9:
            raise RouteError("TUNING %s: pitch %.3f is below track width + clearance" % (site.net, p))
        rng = self._locate(site)
        if isinstance(rng, str):
            self.findings.append(F("TUNE", "%s: %s %s" % (site.net, site.label, rng), site.net, site.p0, layer=site.layer))
            return None, rng
        kind = "both" if site.side == "both" else "single"
        sides = (1, -1) if kind == "both" else ((1,) if site.side == "R" else (-1,))
        room = rng[1] - rng[0]
        nmax = int(math.floor(room / p - 1 + 1e-9)) if kind == "both" else int(math.floor(room / (2 * p) + 1e-9))
        tests, why = {}, None
        for el in self._exact(R, kind, r, nmax):
            hit, w = self._try(site, el, sides, rng, tests)
            if hit:
                return self._commit(site, el, hit, p), None
            why = why or w
        # partial: the most that fits, humps no lower than amp
        best = None
        K = (8 - 2 * math.pi) * r
        for n in range(nmax, 0, -1):
            a_hi = (R / n + K) / 2 if kind == "single" else (R + (4 - math.pi) * r * (n + 1)) / (2 * n)
            a_hi = min(a_hi, S.amp_max)
            grid = [S.amp] + [round(S.amp + 0.005 * i, 4) for i in range(1, int((a_hi - S.amp) / 0.005 + 1e-9) + 1)]
            grid = [a for a in grid if a <= a_hi + 1e-9 and self._legal(a, r)]
            if not grid:
                continue
            el_of = lambda a: (kind, n, a, r)
            if best and gain_of(el_of(grid[-1])) <= best[0] + 1e-9:
                continue
            hit, w = self._try(site, el_of(grid[0]), sides, rng, tests)
            if not hit:
                why = why or w
                continue
            lo, hi, good, stop = 0, len(grid) - 1, (grid[0], hit), None
            h2, w2 = self._try(site, el_of(grid[hi]), sides, rng, tests)
            if h2:
                good = (grid[hi], h2)
                stop = "%d humps of %.3f is the most the site takes%s" % (n, grid[hi], " (amp_max)" if grid[hi] >= S.amp_max - 1e-9 else "")
            else:
                stop = "%.3f high: %s" % (grid[hi], w2)
                while hi - lo > 1:
                    mid = (lo + hi) // 2
                    hm, wm = self._try(site, el_of(grid[mid]), sides, rng, tests)
                    if hm:
                        lo, good = mid, (grid[mid], hm)
                    else:
                        hi, stop = mid, "%.3f high: %s" % (grid[mid], wm)
            g = gain_of(el_of(good[0]))
            if best is None or g > best[0] + 1e-9:
                best = (g, el_of(good[0]), good[1], stop)
        if best is None:
            return None, why
        return self._commit(site, best[1], best[2], p), best[3]

    # ---- drawing
    def _commit(self, site, el, hit, p):
        u0, sd, k = hit
        n_, lay, a, c, w = self.segs[k]
        prims, base = draw(el, u0, sd)
        P0, P1 = _r(site.world(u0, 0.0)), _r(site.world(u0 + base, 0.0))
        forward = site.local(c)[0] > site.local(a)[0]
        first, last = (a, c) if forward else (c, a)         # first = the end nearer p0
        new_segs, new_arcs, plen = [], [], 0.0
        new_segs.append((site.net, lay, first, P0, w) if forward else (site.net, lay, P0, first, w))
        joint = P0
        for i, pr in enumerate(prims):
            end = P1 if i == len(prims) - 1 else _r(site.world(*pr[-2 if pr[0] == "arc" else 2]))
            if pr[0] == "seg":
                new_segs.append((site.net, lay, joint, end, w)); plen += math.dist(joint, end)
            else:
                mid = _r(site.world(*pr[2]))
                new_arcs.append((site.net, lay, joint, mid, end, w)); plen += arc_len(joint, mid, end)
            joint = end
        new_segs.append((site.net, lay, P1, last, w) if forward else (site.net, lay, last, P1, w))
        old = math.dist(a, c)
        gain = math.dist(first, P0) + plen + math.dist(P1, last) - old
        self.segs[k:k + 1] = new_segs
        bid = len(self.blocks)
        for x in new_arcs:
            self._arc_block[len(self.arcs)] = bid
            self.arcs.append(x)
            self._add_arc(self.sc, *x, bid)
        for x in new_segs[1:-1]:
            it = self.sc.seg(*x)
            self.sc.add(it); self._blk[id(it)] = bid
        cnt, h = humps(el)
        blk = {"id": bid, "net": site.net, "layer": lay, "site": site.label, "kind": el[0],
               "side": "both" if el[0] == "both" else ("R" if sd > 0 else "L"), "humps": cnt if el[0] != "bump" else 0,
               "bumps": 1 if el[0] == "bump" else 0, "amp": round(h, 4), "pitch": p, "r": round(el[3] if el[0] != "bump" else el[1], 4),
               "from": list(P0), "to": list(P1), "base": round(base, 4), "gain": round(gain, 6), "el": el, "u0": u0, "sd": sd,
               "site_p0": site.p0, "site_U": site.U, "site_N": site.N, "width": w,
               "arcs": list(range(len(self.arcs) - len(new_arcs), len(self.arcs))), "segs": new_segs}
        self.blocks.append(blk)
        return blk

    def run(self):
        """Draw the serpentines. -> report dict (also self.report); self.segs / self.arcs / self.lens hold the result."""
        T = self.targets()
        self._arc_block = {}
        self.sc = self._scene(self.segs, [])
        by_net = {}
        for s in self.sites:
            by_net.setdefault(s.net, []).append(s)
            if s.net not in self.S.group_of:
                self.findings.append(F("NOTE", "%s: %s is not in any TUNING group: not used" % (s.net, s.label), s.net, s.p0))
        for g, t in T.items():
            for n in t["missing_nets"]:
                self.findings.append(F("TUNE", "%s is in TUNING group %s but has no route" % (n, g), n))
        need = {n: t["need"][n] for t in T.values() for n in t["nets"]}
        added, missing, notes = {}, {}, {}
        for net in sorted(need, key=lambda n: (-need[n], n)):        # the neediest net picks its room first
            rem = need[net]
            if rem < 1e-4:
                continue
            tried = []
            for s in by_net.get(net, []):
                if rem < 1e-4:
                    break
                blk, why = self._place(s, rem)
                if blk:
                    rem -= blk["gain"]
                    added[net] = added.get(net, 0.0) + blk["gain"]
                    tried.append("%s took %.3f (%s)" % (s.label, blk["gain"], self._say(blk)) + ("; stopped: " + why if why else ""))
                else:
                    tried.append("%s took nothing: %s" % (s.label, why))
            if rem > 1e-3:
                missing[net] = round(rem, 4)
                where = "; ".join(tried) if tried else "no site"
                at = by_net[net][0].p0 if by_net.get(net) else None
                t = T[self.S.group_of[net]]
                inside = self.natural[net]["length"] + added.get(net, 0.0) >= t["longest"] - t["spread"] - 1e-6
                self.findings.append(F("NOTE" if inside else "TUNE", "%s: missing %.3f mm at site(s): %s (need %.3f)%s" % (
                    net, rem, where, need[net], "; inside the window all the same" if inside else ""), net, at))
            notes[net] = tried
        self.lens = {}
        for n, x in self.natural.items():
            y = dict(x, layers=dict(x["layers"]))
            add = sum(b["gain"] for b in self.blocks if b["net"] == n)
            if add:
                y["length"] = round(x["length"] + add, 4); y["track"] = round(x["track"] + add, 4)
                for b in self.blocks:
                    if b["net"] == n:
                        y["layers"][b["layer"]] = round(y["layers"].get(b["layer"], 0.0) + b["gain"], 4)
            y["tuned"] = round(add, 4)
            self.lens[n] = y
        self.findings += self.check()
        groups = {}
        for g, t in T.items():
            lo = t["longest"] - t["spread"]
            rows = {n: {"natural": self.natural[n]["length"], "need": t["need"][n], "added": round(added.get(n, 0.0), 4),
                        "length": self.lens[n]["length"], "to_window": round(self.lens[n]["length"] - lo, 4)} for n in t["nets"]}
            worst = min(t["nets"], key=lambda n: (rows[n]["to_window"], n))
            groups[g] = dict({k: t[k] for k in ("ref", "longest", "spread", "target")}, window=[round(lo, 4), t["longest"]],
                             inside=sum(1 for n in t["nets"] if lo - 1e-6 <= self.lens[n]["length"] <= t["longest"] + 1e-6), total=len(t["nets"]),
                             worst=[worst, rows[worst]["to_window"]], nets=rows,
                             blocks=sum(1 for b in self.blocks if b["net"] in t["nets"]),
                             added=round(sum(rows[n]["added"] for n in t["nets"]), 4),
                             missing={n: missing[n] for n in t["nets"] if n in missing})
        self.report = {"settings": self.S.describe(), "groups": groups, "missing": missing, "sites": notes,
                       "blocks": [{k: v for k, v in b.items() if k not in ("el", "segs", "arcs", "site_p0", "site_U", "site_N", "u0", "sd")}
                                  for b in self.blocks], "arcs": len(self.arcs), "geometry": self.geo}
        return self.report

    @staticmethod
    def _say(b):
        if b["bumps"]:
            return "one bump of %.3f on %s" % (b["amp"], b["side"])
        return "%d humps of %.3f on %s, pitch %g" % (b["humps"], b["amp"], b["side"], b["pitch"])

    # ---- the arc geometry checks (the written points, rounded as in the file)
    def check(self):
        """ARC findings: tangency at every joint, radius as asked, no piece under min_seg, one height per block,
        and the clearances (clr, area_gap, end) measured on the final copper. Also fills self.geo (the numbers)."""
        out = []
        tol_deg, tol_r, tol_h = 0.01, 1e-4, 1e-4
        geo = {"blocks": len(self.blocks), "arcs": len(self.arcs), "max_joint_deg": 0.0, "max_radius_error": 0.0, "shortest_piece": None,
               "max_height_spread": 0.0, "min_clr": None, "min_area_gap": None, "min_end": None}
        self._arc_block = {k: b["id"] for b in self.blocks for k in b["arcs"]}
        sc_final = self._scene(self.segs, self.arcs)
        self.sc = sc_final
        for b in self.blocks:
            net, lay, el = b["net"], b["layer"], b["el"]
            arcs = [self.arcs[k] for k in b["arcs"]]
            items, ia, isg = [], 0, 1
            items.append(("seg",) + self._oriented(b["segs"][0], b["from"], True))
            prims, _ = draw(el, b["u0"], b["sd"])
            for pr in prims:
                if pr[0] == "arc":
                    x = arcs[ia]; ia += 1
                    items.append(("arc", x[2], x[3], x[4]))
                else:
                    s = b["segs"][isg]; isg += 1
                    items.append(("seg", s[2], s[3]))
            items.append(("seg",) + self._oriented(b["segs"][-1], b["to"], False))
            want_r = el[3] if el[0] != "bump" else el[1]
            for it in items:
                L = math.dist(it[1], it[2]) if it[0] == "seg" else arc_len(it[1], it[2], it[3])
                geo["shortest_piece"] = L if geo["shortest_piece"] is None else min(geo["shortest_piece"], L)
                if L < self.profile.min_seg - 1e-7:
                    out.append(F("ARC", "%s: a %s of %.4f mm in the serpentine at (%.3f, %.3f) (shortest allowed %.2f)" % (net, it[0], L, it[1][0], it[1][1], self.profile.min_seg), net, it[1], layer=lay))
                if it[0] == "arc":
                    rr = circle(it[1], it[2], it[3])[1]
                    geo["max_radius_error"] = max(geo["max_radius_error"], abs(rr - want_r))
                    if abs(rr - want_r) > tol_r:
                        out.append(F("ARC", "%s: arc at (%.3f, %.3f) has radius %.4f, %.4f asked" % (net, it[1][0], it[1][1], rr, want_r), net, it[1], layer=lay))
            for x, y in zip(items, items[1:]):
                d1 = self._dir(x, False)
                d2 = self._dir(y, True)
                ang = math.degrees(math.acos(max(-1.0, min(1.0, d1[0] * d2[0] + d1[1] * d2[1]))))
                geo["max_joint_deg"] = max(geo["max_joint_deg"], ang)
                if ang > tol_deg:
                    p = x[2] if x[0] == "seg" else x[3]
                    out.append(F("ARC", "%s: the serpentine is not tangent at (%.4f, %.4f): %.3f degrees" % (net, p[0], p[1], ang), net, p, layer=lay))
            if el[0] in ("single", "both"):                 # every hump top at the same height
                U, N, o = b["site_U"], b["site_N"], b["site_p0"]
                tops = []
                for it in items:
                    if it[0] == "arc":
                        c = circle(it[1], it[2], it[3])
                        if abs(abs(c[3]) - math.pi) < 1e-3:
                            v = (it[2][0] - o[0]) * N[0] + (it[2][1] - o[1]) * N[1]
                            if abs(v) > el[3] * 1.5 or el[0] == "both":
                                tops.append(abs(v))
                spread = max(tops) - min(tops) if tops else 0.0
                geo["max_height_spread"] = max(geo["max_height_spread"], spread)
                if len(tops) != el[1] or spread > tol_h or abs(max(tops) - el[2]) > tol_h:
                    out.append(F("ARC", "%s: the humps of the block at (%.3f, %.3f) are not all %.4f high (%d tops, %.4f .. %.4f)" % (
                        net, b["from"][0], b["from"][1], el[2], len(tops), min(tops) if tops else 0, max(tops) if tops else 0), net, b["from"], layer=lay))
            gmin, amin = self._measure(b)                   # clearances on the final copper
            if gmin is not None:
                geo["min_clr"] = gmin if geo["min_clr"] is None else min(geo["min_clr"], gmin)
            if amin is not None:
                geo["min_area_gap"] = amin if geo["min_area_gap"] is None else min(geo["min_area_gap"], amin)
            if gmin is not None and gmin < self.S.clr - 1e-4:
                out.append(F("ARC", "%s: the serpentine at (%.3f, %.3f) comes %.4f mm from other copper (clr %.3f)" % (net, b["from"][0], b["from"][1], gmin, self.S.clr), net, b["from"], layer=lay))
            if amin is not None and amin < self.S.area_gap - 1e-4:
                out.append(F("ARC", "%s: the serpentine at (%.3f, %.3f) comes %.4f mm from a rule-area edge (area_gap %.3f)" % (net, b["from"][0], b["from"][1], amin, self.S.area_gap), net, b["from"], layer=lay))
            e = self._end_of(b)
            if e is not None:
                geo["min_end"] = e if geo["min_end"] is None else min(geo["min_end"], e)
                if e < self.S.end - 1e-4:
                    out.append(F("ARC", "%s: only %.4f mm of straight between a corner and the serpentine at (%.3f, %.3f) (end %.3f)" % (net, e, b["from"][0], b["from"][1], self.S.end), net, b["from"], layer=lay))
        for k in ("min_clr", "min_area_gap", "min_end", "shortest_piece", "max_joint_deg", "max_radius_error", "max_height_spread"):
            if geo[k] is not None:
                geo[k] = round(geo[k], 6)
        self.geo = geo
        return out

    @staticmethod
    def _oriented(seg, joint, lead):
        """A lead / tail segment as (start, end) in travel order (towards the block / away from it)."""
        a, c = seg[2], seg[3]
        if lead:
            return (a, c) if math.dist(c, joint) < 1e-9 else (c, a)
        return (a, c) if math.dist(a, joint) < 1e-9 else (c, a)

    @staticmethod
    def _dir(it, at_start):
        if it[0] == "seg":
            L = math.dist(it[1], it[2])
            return ((it[2][0] - it[1][0]) / L, (it[2][1] - it[1][1]) / L)
        d0, d1 = arc_dirs(it[1], it[2], it[3])
        return d0 if at_start else d1

    def _measure(self, b):
        """(smallest gap from the block's copper to other copper, smallest gap to a rule-area edge) on the final copper."""
        net, lay, hw = b["net"], b["layer"], b["width"] / 2
        pts = []
        for x in b["segs"][1:-1]:
            n = max(1, int(math.ceil(math.dist(x[2], x[3]) / STEP)))
            pts += [(x[2][0] + (x[3][0] - x[2][0]) * i / n, x[2][1] + (x[3][1] - x[2][1]) * i / n) for i in range(n + 1)]
        for k in b["arcs"]:
            x = self.arcs[k]
            pts += arc_points(x[2], x[3], x[4], STEP)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        box = Item("seg", None, lay, (min(xs), min(ys)), (max(xs), max(ys)), 0.0, "box")
        U, N, o = b["site_U"], b["site_N"], b["site_p0"]
        on_line = lambda p: abs((p[0] - o[0]) * N[0] + (p[1] - o[1]) * N[1]) < 1e-5
        obs = [x for x in self.sc.near(box, 1.0) if (x.layer is None or x.layer == lay) and self._blk.get(id(x)) != b["id"]
               and not (x.net == net and x.kind == "seg" and on_line(x.a) and on_line(x.b))]
        rline = b["el"][3] if b["el"][0] != "bump" else min(b["el"][1], 0.05)
        gmin, amin = None, None
        for q in pts:
            v = (q[0] - o[0]) * N[0] + (q[1] - o[1]) * N[1]
            u = (q[0] - o[0]) * U[0] + (q[1] - o[1]) * U[1]
            base = (o[0] + u * U[0], o[1] + u * U[1])
            for x in obs:
                if x.net == net and abs(v) < rline - 1e-6:
                    continue
                d = _dist(q, x)
                if x.net != net and d - x.r - hw < self.S.clr and d >= _dist(base, x) - 1e-6:
                    continue                                # no closer than the straight it replaces (_limits)
                g = d - x.r - hw
                gmin = g if gmin is None else min(gmin, g)
            for nm, a in self.areas.items():
                if lay in a["layers"]:
                    R = a["rect"]
                    g = math.hypot(max(R[0] - q[0], 0.0, q[0] - R[2]), max(R[1] - q[1], 0.0, q[1] - R[3])) - hw
                    amin = g if amin is None else min(amin, g)
        return gmin, amin

    def _end_of(self, b):
        """Straight between the block and the nearer end of the route's straight it sits on (a corner, via or pad)."""
        net, lay = b["net"], b["layer"]
        U, N, o = b["site_U"], b["site_N"], b["site_p0"]
        loc = lambda p: ((p[0] - o[0]) * U[0] + (p[1] - o[1]) * U[1], (p[0] - o[0]) * N[0] + (p[1] - o[1]) * N[1])
        u0, u1 = loc(b["from"])[0], loc(b["to"])[0]
        for pc in self.resolved.get(net, []):
            if pc[0] != lay:
                continue
            for a, c in zip(pc[1], pc[1][1:]):
                (ua, va), (uc, vc) = loc(a), loc(c)
                if abs(va) < 1e-4 and abs(vc) < 1e-4 and min(ua, uc) <= u0 + 1e-6 and max(ua, uc) >= u1 - 1e-6:
                    return min(u0 - min(ua, uc), max(ua, uc) - u1)
        return None
