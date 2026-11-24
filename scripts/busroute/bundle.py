"""Bundles: write a bus, not N coordinate lists.

    bus = Bus(board, profile)                         # obstacles: every pad, track and via of other nets
    bus.keep({net: pieces})                           # hand-written routes: passed through, used as obstacles
    b = Bundle("trunk", ["FMC_SDCLK", "FMC_D15", ...], "L1",      # lane order: lane 0 = LEFT seen along the travel direction
               path=[(18.2, 15.575), (19.2, 15.575), (22.325, 18.7), (23.4, 18.7)],   # centre path, corners exactly 45 degrees
               pitch=0.2298,                          # centre-to-centre spacing on every leg not named in gaps
               gaps={0: 0.325, 2: [1.2, 0.8, 0.8]},   # per leg: one pitch, or N-1 gaps
               anchor="FMC_D14",                      # the lane that sits ON the path ("centre": the middle of the bundle)
               span={"FMC_SDCLK": (1, 2)})            # a lane that exists only on legs 1..2 (joins late / leaves early)
    b.widen(leg, s0, s1, after="FMC_D14", by=0.6)     # lanes right of D14 step aside between stations s0 and s1
    bus.add(b, start={net: terminal}, end={net: terminal})
    f = bus.vias(b, at=2.0, gnd="GND")                # the open lanes of b end in a staggered field of vias ...
    bus.add(Bundle("under", nets, "L4", ...))         # ... and a bundle on another layer starts from them
    ROUTES = bus.routes()                             # bus.problems lists ORDER / FAN / SHAPE / SLOT findings

Terminals: "REF.PAD" or "REF" (the net's pad there); (x, y); a list of points = a lead on the bundle's layer
in travel order; a list of route pieces (or a fan-out Lead) = pieces that end (start terminal) or begin (end
terminal) where the bundle takes over: a last / first piece on the bundle's layer is used as the lead, any
other layer gets a via.

A net without a start whose route so far ends open on the same layer JOINS (its last line runs on until it
meets its lane); one that ended in a via field starts from its via. A net without an end stays open.

Lanes are pieces of lines on the 0.1 um grid, so segments are exactly 0/45/90, corners exactly 45 degrees,
neighbours exactly parallel and corners nest by themselves. On a diagonal leg a gap is rounded UP to the grid.
Stations s are mm along a leg from the leg's first path point.

Errors come at once and say how much is missing: bus.add() raises PitchError when two lanes are closer than
track width + clearance of the place; bus.vias() when a lane cannot pass its neighbour's via.
"""
import itertools, math
from .geom import (G, R2, NAME, RouteError, sgn, dot, right, diag, unit, ipt, fpt, dir_of, turn, Line, through, meet, at_uv,
                   clean, ilen, shape_errors, sharp_errors, in_rect, pt_seg)
from .routes import F, split_widths, via_size
from .checks import Scene

BIG = 10 ** 12
SEQ = itertools.count()                                     # creation order of serpentine sites (Slot, job.slot)


class PitchError(RouteError):
    pass


class Bundle:
    def __init__(self, name, nets, layer, path, pitch, gaps=None, anchor="centre", span=None, min_seg=None):
        self.name, self.layer, self.min_seg, self.nets = name, layer, min_seg, list(nets)
        if len(set(self.nets)) != len(self.nets):
            raise RouteError("%s: a net is listed twice" % name)
        n = len(self.nets)
        self.path = [ipt(p) for p in path]
        self.legs = []
        for k, (a, c) in enumerate(zip(self.path, self.path[1:])):
            D = dir_of(a, c)
            if D is None:
                raise RouteError("%s: path leg %d (%s -> %s) is not at 0/45/90 degrees" % (name, k, fpt(a), fpt(c)))
            self.legs.append({"D": D, "N": right(D), "sc": R2 if diag(D) else 1.0, "U0": dot(D, a), "U1": dot(D, c), "Vc": dot(right(D), a)})
        for k in range(len(self.legs) - 1):
            t = turn(self.legs[k]["D"], self.legs[k + 1]["D"])
            if t != 1:
                raise RouteError("%s: the corner between leg %d and leg %d is %d degrees (must be 45; write a 90-degree turn as two legs)" % (name, k, k + 1, 45 * t))
        gaps = gaps or {}
        ia = None if anchor == "centre" else self.nets.index(anchor)
        for k, leg in enumerate(self.legs):
            g = gaps.get(k, pitch)
            g = [g] * (n - 1) if isinstance(g, (int, float)) else list(g)
            if len(g) != n - 1:
                raise RouteError("%s: gaps[%d] needs %d values (one per pair of neighbouring lanes)" % (name, k, n - 1))
            leg["gv"] = [int(math.ceil(x * G * leg["sc"] - 1e-6)) for x in g]
            pos = [0]
            for x in leg["gv"]:
                pos.append(pos[-1] + x)
            ref = pos[ia] if ia is not None else (pos[0] + pos[-1]) // 2
            leg["V"] = [leg["Vc"] + p - ref for p in pos]
        self.span = {net: (0, len(self.legs) - 1) for net in self.nets}
        for net, sp in (span or {}).items():
            self.span[net] = tuple(sp)
        self.events, self.slots = [], []

    def idx(self, net):
        return self.nets.index(net) if isinstance(net, str) else int(net)

    def on_leg(self, k):
        """Lane numbers present on leg k, in order."""
        return [i for i, n in enumerate(self.nets) if self.span[n][0] <= k <= self.span[n][1]]

    def U(self, leg, s):
        L = self.legs[leg]
        return L["U0"] + int(round(s * G * L["sc"]))

    def spacing(self, leg, i, j, U=None):
        """Centre distance in mm between lanes i and j on a leg (at station U when widened)."""
        L = self.legs[leg]
        U = L["U0"] if U is None else U
        return abs((L["V"][j] + self.shift(leg, j, U)) - (L["V"][i] + self.shift(leg, i, U))) / G / L["sc"]

    # ---- stepping aside
    def widen(self, leg, s0, s1, after, by, side=1):
        """Between stations s0 and s1 of a leg the gap next to lane `after` grows by `by` mm: with side=+1 ("R")
        the lanes right of it move right, with side=-1 ("L") the lanes left of it move left, on nested 45-degree
        jogs. s0=None: wide from the start of the leg (no jog out); s1=None: wide to the end of the leg."""
        L = self.legs[leg]
        e = {"leg": leg, "U0": -BIG if s0 is None else self.U(leg, s0), "U1": BIG if s1 is None else self.U(leg, s1), "j": self.idx(after),
             "side": 1 if side in (1, "R") else -1, "dV": int(math.ceil(by * G * L["sc"] - 1e-6)), "open0": s0 is None, "open1": s1 is None}
        if e["U1"] <= e["U0"] or e["dV"] <= 0:
            raise RouteError("%s: widen on leg %d needs s1 > s0 and by > 0" % (self.name, leg))
        self.events.append(e)
        return e

    def _hits(self, e, i):
        return i > e["j"] if e["side"] > 0 else i < e["j"]

    def shift(self, leg, i, U, skip=None):
        return sum(e["side"] * e["dV"] for e in self.events
                   if e is not skip and e["leg"] == leg and self._hits(e, i) and e["U0"] <= U <= e["U1"])

    def lane_lines(self, net):
        """The lines one lane runs on, in order: lane pieces and the jogs between them."""
        i, out = self.idx(net), []
        f, l = self.span[self.nets[i]]
        for k in range(f, l + 1):
            L = self.legs[k]
            D, N = L["D"], L["N"]
            tag = "%s leg %d (%s) lane %s" % (self.name, k, NAME[D], self.nets[i])
            trans = []                                      # (station where the jog begins, sideways move, parity nudge)
            base = L["V"][i] + sum(e["side"] * e["dV"] for e in self.events if e["leg"] == k and self._hits(e, i) and e["open0"])
            for e in self.events:
                if e["leg"] != k or not self._hits(e, i):
                    continue
                j0 = e["j"] + e["side"]                     # the first lane that moves
                for which, Uref in (("out", e["U0"] - 1), ("in", e["U1"] + 1)):
                    if e["open0" if which == "out" else "open1"]:
                        continue
                    Uin = Uref + (1 if which == "out" else -1) * 2
                    spread = abs((L["V"][i] + self.shift(k, i, Uin, e)) - (L["V"][j0] + self.shift(k, j0, Uin, e)))
                    t = int(math.ceil(spread * (R2 - 1))) + abs(i - j0)     # nested: outer lanes earlier out, later in
                    if which == "out":
                        trans.append((e["U0"] - e["dV"] - t, e["side"] * e["dV"], -1))
                    else:
                        trans.append((e["U1"] + t, -e["side"] * e["dV"], 1))
            trans.sort()
            cur, lo = base, None
            for Ub, dV, nudge in trans:
                if diag(D) and (Ub - cur) % 2:              # on a diagonal a grid point needs station and offset of equal parity
                    Ub += nudge
                out.append(Line(D, cur, lo, Ub, "lane", tag, (self, k)))
                Dj = (sgn(D[0] + sgn(dV) * N[0]), sgn(D[1] + sgn(dV) * N[1]))
                out.append(through(Dj, at_uv(D, Ub, cur), kind="jog", tag=tag + " jog", leg=(self, k)))
                cur += dV; lo = Ub + abs(dV)
            out.append(Line(D, cur, lo, None, "lane", tag, (self, k)))
        return out

    def lane_point(self, net, leg, s):
        """Integer point of a lane at a station (widen events included)."""
        i, L = self.idx(net), self.legs[leg]
        U = self.U(leg, s)
        V = L["V"][i] + self.shift(leg, i, U)
        if diag(L["D"]) and (U - V) % 2:
            U += 1
        return at_uv(L["D"], U, V)

    # ---- serpentine sites (drawn by the tuning stage, tune.py, when the routes file has TUNING)
    def slot(self, net, leg, s0, length, side="R", free=None, pitch=None, humps=None):
        """A serpentine site: `length` mm of straight on lane `net` from station s0 of `leg`, humps towards
        "R" / "L" (higher / lower lane numbers) or "both". With free = mm the neighbours on that side step aside
        (widen) so that their centre line is `free` away over the site. pitch = leg centre distance of the
        serpentine (None: TUNING's pitch for the net); humps = exactly that many humps (tune.py). Returns a Slot;
        bus.tuning() lists them."""
        i, L = self.idx(net), self.legs[leg]
        if free is not None:
            for sd in ((1, -1) if side == "both" else ((1,) if side == "R" else (-1,))):
                j = i + sd
                if 0 <= j < len(self.nets):
                    have = L["gv"][min(i, j)] / G / L["sc"]
                    if free > have + 1e-9:
                        self.widen(leg, s0, s0 + length, after=i, by=free - have, side=sd)
        s = Slot(self, i, leg, s0, length, side, pitch, humps)
        self.slots.append(s)
        return s


class Slot:
    def __init__(self, b, i, leg, s0, length, side, pitch, humps=None):
        self.b, self.i, self.leg, self.s0, self.length, self.side, self.pitch, self.net = b, i, leg, s0, length, side, pitch, b.nets[i]
        self.humps = humps
        self.seq = next(SEQ)                                # sites of a net are used in the order they were written

    def geometry(self):
        """Where the site is: end points, the board direction of each side, the free width to the neighbours."""
        b, L = self.b, self.b.legs[self.leg]
        p0, p1 = b.lane_point(self.i, self.leg, self.s0), b.lane_point(self.i, self.leg, self.s0 + self.length)
        if b.shift(self.leg, self.i, dot(L["D"], p0)) != b.shift(self.leg, self.i, dot(L["D"], p1)):
            raise RouteError("slot %s on %s leg %d: the lane itself jogs inside the site" % (self.net, b.name, self.leg))
        Um, free = (dot(L["D"], p0) + dot(L["D"], p1)) // 2, {}
        for sd in (1, -1):
            j = self.i + sd
            while 0 <= j < len(b.nets) and not (b.span[b.nets[j]][0] <= self.leg <= b.span[b.nets[j]][1]):
                j += sd
            if 0 <= j < len(b.nets):
                free["R" if sd > 0 else "L"] = round(b.spacing(self.leg, self.i, j, Um), 4)
        N = L["N"]
        return {"net": self.net, "bundle": b.name, "leg": self.leg, "layer": b.layer, "from": fpt(p0), "to": fpt(p1), "length": round(ilen(p0, p1), 4),
                "side": self.side, "pitch": self.pitch, "dir": {"R": NAME[N], "L": NAME[(-N[0], -N[1])]}, "free": free}


class ViaField:
    def __init__(self, points, gnd, rows, step, size):
        self.points, self.gnd, self.rows, self.step, self.size = points, gnd, rows, step, size


# ---------------------------------------------------------------- the bus: bundles + hand routes -> routes
class Bus:
    def __init__(self, board, profile, sketch=False, fan_step=0.05, fan_max=8.0):
        self.board, self.profile, self.sketch = board, profile, sketch
        self.areas = board.rule_areas(profile.area_names)
        self.min_seg, self.fan_step, self.fan_max = profile.lane_min_seg, fan_step, fan_max
        self.plan, self.kept, self.secs, self.bundles = {}, {}, [], []
        self.cont, self.stitch, self.fields = {}, [], []
        self.problems, self._routes = [], None

    # ---- input
    def _pt(self, net, p):
        if isinstance(p, str):
            return self.board.pad(p, net).pos
        return (float(p[0]), float(p[1]))

    def _raw(self, net, pieces):
        out = []
        for pc in pieces:
            if pc[0] == "via":
                out.append(("via", self._pt(net, pc[1])) + tuple(pc[2:]))
            else:
                out.append((pc[0], [self._pt(net, p) for p in pc[1]]))
        return out

    def keep(self, routes):
        """Routes written elsewhere (by hand, by the fan-out): returned unchanged by routes(), used as obstacles."""
        for net, pieces in routes.items():
            self.kept[net] = self._raw(net, pieces)

    @staticmethod
    def _is_pieces(spec):
        return isinstance(spec, (list, tuple)) and len(spec) > 0 and isinstance(spec[0], (list, tuple)) and len(spec[0]) >= 2 \
            and isinstance(spec[0][0], str) and isinstance(spec[0][1], (list, tuple)) and (spec[0][0] == "via" or isinstance(spec[0][1][0], (list, tuple, str)))

    def _terminal(self, net, spec, start, layer):
        """-> (raw pieces before / after, lead points on the bundle's layer in travel order)."""
        if hasattr(spec, "pieces"):
            spec = spec.pieces
        if isinstance(spec, dict):
            spec = spec["pieces"]
        if self._is_pieces(spec):
            raw = self._raw(net, spec)
            k = -1 if start else 0
            if raw[k][0] == layer:
                lead = raw[k][1]
                return (raw[:-1] if start else raw[1:]), [ipt(p) for p in lead]
            p = raw[k][1] if raw[k][0] == "via" else raw[k][1][k]
            return raw, [ipt(p)]
        if isinstance(spec, str) or (isinstance(spec, tuple) and not isinstance(spec[0], (tuple, list, str))):
            spec = [spec]
        return [], [ipt(self._pt(net, p)) for p in spec]

    def add(self, bundle, start=None, end=None):
        """Put a bundle on the bus. start / end = {net: terminal}. Raises PitchError at once when two of its
        lanes are closer than the place allows."""
        start, end = dict(start or {}), dict(end or {})
        for k in list(start) + list(end):
            if k not in bundle.nets:
                raise RouteError("%s: terminal given for %s, which is not a lane of this bundle" % (bundle.name, k))
        if bundle.layer not in self.board.cu:
            raise RouteError("%s: unknown layer %r" % (bundle.name, bundle.layer))
        if bundle.min_seg is None:
            bundle.min_seg = self.min_seg
        self._pitch_check(bundle)
        self._routes = None
        self.bundles.append(bundle)
        for net in bundle.nets:
            items = self.plan.setdefault(net, [])
            lines = bundle.lane_lines(net)
            open_sec = items[-1] if items and "lines" in items[-1] and items[-1]["end"] is None else None
            if net not in start and net in self.cont and not open_sec:
                start[net] = self.cont.pop(net)
            if net in start:
                if open_sec:
                    raise RouteError("%s: %s still runs open in bundle %s, it cannot start again" % (bundle.name, net, open_sec["bundles"][-1].name))
                raw, lead = self._terminal(net, start[net], True, bundle.layer)
                if raw:
                    items.append({"raw": raw})
                sec = {"net": net, "layer": bundle.layer, "lines": lines, "start": lead, "end": None, "bundles": [bundle]}
                items.append(sec); self.secs.append(sec)
            else:
                if not open_sec or open_sec["layer"] != bundle.layer:
                    raise RouteError("%s: %s has no start terminal, no via field behind it and no open lane on %s to join from" % (bundle.name, net, bundle.layer))
                sec = open_sec
                sec["lines"] = self._join(sec["lines"], lines)
                sec["bundles"].append(bundle)
            if net in end:
                raw, lead = self._terminal(net, end[net], False, bundle.layer)
                sec["end"] = lead
                if raw:
                    items.append({"raw": raw})

    def _join(self, A, B):
        """Chain two line lists of one net: leave A on the last piece that reaches the meeting point, enter B on
        the first piece that is still there (so a lane may join where the bundle is widened)."""
        m = self.min_seg * G
        ia = [k for k, l in enumerate(A) if l.kind == "lane"]
        ib = [k for k, l in enumerate(B) if l.kind == "lane"]
        for ka in reversed(ia):
            if A[ka].D != A[-1].D:
                break
            for kb in ib:
                if B[kb].D != B[0].D:
                    break
                a, b = A[ka], B[kb]
                if a.D == b.D:
                    if a.V == b.V:
                        return A[:ka + 1] + B[kb + 1:]
                    continue
                if turn(a.D, b.D) != 1:
                    raise RouteError("join: %s meets %s at %d degrees (must be 45)" % (a.tag, b.tag, 45 * turn(a.D, b.D)))
                X = meet(a, b)
                ua, ub = dot(a.D, X), dot(b.D, X)
                sa, sb = (R2 if diag(a.D) else 1.0), (R2 if diag(b.D) else 1.0)
                if (a.lo is None or ua >= a.lo + m * sa) and (a.hi is None or ua <= a.hi) and (b.hi is None or ub <= b.hi - m * sb) and (b.lo is None or ub >= b.lo):
                    return A[:ka + 1] + B[kb:]
        raise RouteError("join: %s cannot reach %s: they are parallel on different lines, or they meet inside a jog / less than %.2f mm after one "
                         "(end the widen earlier, or leave it open with s1=None)" % (A[-1].tag, B[0].tag, self.min_seg))

    # ---- the clearance of a place
    def _thin(self, p):
        return any(in_rect(p, R, self.profile.extend) for R in self.areas.values())

    def _lane_need(self, p, na, nb):
        """(needed centre distance of two parallel tracks at point p, the text of the sum)."""
        pr = self.profile
        if self._thin(p):
            return pr.w_area + pr.clr_area, "track %g + clearance %g inside a rule area" % (pr.w_area, pr.clr_area)
        w, c = (pr.width(na) + pr.width(nb)) / 2, max(pr.clr(na), pr.clr(nb))
        return w + c, "track %g + clearance %g outside the rule areas" % (w, c)

    def _pitch_check(self, b):
        bad = []
        for k, L in enumerate(b.legs):
            on = b.on_leg(k)
            a, c = fpt(b.path[k]), fpt(b.path[k + 1])
            n = max(1, int(math.dist(a, c) / 0.1))
            nx, ny = L["N"][0] / L["sc"], L["N"][1] / L["sc"]
            for i, j in zip(on, on[1:]):
                have = (L["V"][j] - L["V"][i]) / G / L["sc"]
                off = ((L["V"][i] + L["V"][j]) / 2 - L["Vc"]) / G / L["sc"]
                worst = None
                for t in range(n + 1):
                    p = (a[0] + (c[0] - a[0]) * t / n + nx * off, a[1] + (c[1] - a[1]) * t / n + ny * off)
                    need, why = self._lane_need(p, b.nets[i], b.nets[j])
                    if have < need - 1e-6 and (worst is None or need > worst[0]):
                        worst = (need, why, p)
                if worst:
                    bad.append("PITCH %s leg %d (%s): lanes %s | %s are %.4f mm centre to centre, %.4f needed (%s): %.4f mm missing, first at (%.3f, %.3f)" % (
                        b.name, k, NAME[L["D"]], b.nets[i], b.nets[j], have, worst[0], worst[1], worst[0] - have, worst[2][0], worst[2][1]))
        if bad:
            raise PitchError("\n".join(bad))

    # ---- layer change: a field of vias
    def vias(self, bundle, at, leg=None, rows=None, step=None, gnd=None, gnd_sides="LR", nets=None):
        """End the open lanes of `bundle` (or `nets`) in vias on their own lane lines on leg `leg` (default: the
        last leg). at = station of the first row in mm, or {net: station} for full control. The vias are
        staggered in `rows` rows `step` mm apart (lane i in row i mod rows) so that the antipads in the planes
        (via + 2 x plane_clr) keep plane_web of copper between them; rows / step are chosen for that when not
        given. gnd = name of the ground net: stitching vias beside the field, one per row on each side in
        gnd_sides ("L", "R" or "LR"). A bundle added afterwards on another layer starts from these vias.
        Raises PitchError when a lane cannot pass the via of its neighbour."""
        pr = self.profile
        k = len(bundle.legs) - 1 if leg is None else leg
        L = bundle.legs[k]
        lanes = [i for i in bundle.on_leg(k) if (nets is None or bundle.nets[i] in nets)]
        secs = {}
        for i in lanes:
            items = self.plan.get(bundle.nets[i], [])
            if not items or "lines" not in items[-1] or items[-1]["end"] is not None or items[-1]["bundles"][-1] is not bundle:
                raise RouteError("vias(%s): %s is not an open lane of that bundle (add the bundle first, without an end for it)" % (bundle.name, bundle.nets[i]))
            secs[i] = items[-1]
        U0 = bundle.U(k, at if not isinstance(at, dict) else min(at.values()))
        V = {i: L["V"][i] + bundle.shift(k, i, U0) for i in lanes}
        p0 = fpt(at_uv(L["D"], U0 + ((U0 - V[lanes[0]]) % 2 if diag(L["D"]) else 0), V[lanes[0]]))
        d, h = via_size(pr, self.areas, bundle.nets[lanes[0]], p0)
        inside = d == pr.via_area[0] and any(in_rect(p0, R) for R in self.areas.values())
        w = pr.w_area if inside else max(pr.width(bundle.nets[i]) for i in lanes)
        clr = pr.clr_area if inside else max(pr.clr(bundle.nets[i]) for i in lanes)
        pass_need = max(d / 2 + w / 2 + clr, h / 2 + w / 2 + pr.hole_clr)
        via_need = max(d + clr, h / 2 + d / 2 + pr.hole_clr, h + pr.hole_hole)     # via beside via: copper, hole to copper, hole to hole
        gaps = [(V[j] - V[i]) / G / L["sc"] for i, j in zip(lanes, lanes[1:])]
        A = d + 2 * pr.plane_clr + pr.plane_web
        if isinstance(at, dict):
            st = {i: bundle.U(k, at[bundle.nets[i]]) for i in lanes}
            rows, step = len(set(st.values())), None
        else:
            pmin = min(gaps) if gaps else A
            if rows is None:
                rows = 1 if pmin >= A - 1e-9 else int(math.ceil(A / pmin - 1e-9))
            if step is None:
                step = 0.0 if rows == 1 else math.ceil(math.sqrt(max(A * A - pmin * pmin, (d + clr) ** 2)) / 0.05 - 1e-9) * 0.05
            st = {i: bundle.U(k, at + (n % rows) * step) for n, i in enumerate(lanes)}
        bad = []
        for i, j in zip(lanes, lanes[1:]):
            have = (V[j] - V[i]) / G / L["sc"]
            if st[i] != st[j] and have < pass_need - 1e-6:
                bad.append("PITCH %s leg %d via field: lanes %s | %s are %.4f mm centre to centre, a track beside a %g / %g via needs %.4f "
                           "(via %g / 2 + track %g / 2 + clearance %g, hole %g / 2 + track / 2 + %g): %.4f mm missing; widen this leg with gaps={%d: ...}" % (
                               bundle.name, k, bundle.nets[i], bundle.nets[j], have, d, h, pass_need, d, w, clr, h, pr.hole_clr, pass_need - have, k))
        pts = {}
        for i in lanes:
            U = st[i]
            if diag(L["D"]) and (U - V[i]) % 2:
                U += 1
            pts[i] = at_uv(L["D"], U, V[i])
        for a in range(len(lanes)):
            for c in range(a + 1, len(lanes)):
                i, j = lanes[a], lanes[c]
                dd = ilen(pts[i], pts[j])
                if dd < via_need - 1e-6:
                    bad.append("PITCH %s leg %d via field: the vias of %s and %s are %.4f mm centre to centre, %.4f needed (the largest of via %g + clearance %g, "
                               "hole to copper %g, hole to hole %g): %.4f mm missing" % (bundle.name, k, bundle.nets[i], bundle.nets[j], dd, via_need, d, clr, pr.hole_clr, pr.hole_hole, via_need - dd))
        if bad:
            raise PitchError("\n".join(bad))
        comp = {i: i for i in lanes}                        # antipads that merge: chains of vias closer than A
        def root(x):
            while comp[x] != x:
                x = comp[x]
            return x
        for a in range(len(lanes)):
            for c in range(a + 1, len(lanes)):
                if ilen(pts[lanes[a]], pts[lanes[c]]) < A - 1e-6:
                    comp[root(lanes[a])] = root(lanes[c])
        groups = {}
        for i in lanes:
            groups.setdefault(root(i), []).append(i)
        for g in groups.values():
            ext = max(ilen(pts[a], pts[c]) for a in g for c in g) + d + 2 * pr.plane_clr
            if len(g) > 1 and ext > pr.slot_max + 1e-6:
                self.problems.append(F("SLOT", "%s leg %d via field: the antipads of %d vias (%s .. %s) merge into a slot %.2f mm long in the planes "
                                       "(via %g + 2 x %g plane clearance, %g web; longest accepted %.2f): use more rows or a longer step (rows=%d, step=%s now)" % (
                                           bundle.name, k, len(g), bundle.nets[g[0]], bundle.nets[g[-1]], ext, d, pr.plane_clr, pr.plane_web, pr.slot_max, rows,
                                           "%.2f" % step if step is not None else "explicit"), bundle.nets[g[0]], fpt(pts[g[0]])))
        for i in lanes:
            secs[i]["end"] = [pts[i]]
            self.cont[bundle.nets[i]] = fpt(pts[i])
        gpts = []
        if gnd:
            if gnd not in self.board.nets:
                raise RouteError("vias(%s): no net %r on the board for the stitching vias" % (bundle.name, gnd))
            g = int(math.ceil(math.ceil(max(via_need, pass_need) / 0.05 - 1e-9) * 0.05 * G * L["sc"] - 1e-6))
            for side in gnd_sides:
                Vg = V[lanes[0]] - g if side == "L" else V[lanes[-1]] + g
                for U in sorted(set(st.values())):
                    if diag(L["D"]) and (U - Vg) % 2:
                        U += 1
                    gpts.append(fpt(at_uv(L["D"], U, Vg)))
            self.stitch += [(gnd, p) for p in gpts]
        f = ViaField({bundle.nets[i]: fpt(pts[i]) for i in lanes}, gpts, rows, step, (d, h))
        self.fields.append(f)
        self._routes = None
        return f

    # ---- obstacles
    def _items(self, sc, net, layer, pts):
        return [sc.seg(net, layer, a, c, w) for a, c, w in
                split_widths(pts, self.areas, self.profile.w_area, self.profile.width(net), self.profile.extend, self.profile.min_seg)]

    def _put(self, sc, net, layer, ipts):
        pts = [fpt(p) for p in clean(ipts)]
        if len(pts) > 1:
            for it in self._items(sc, net, layer, pts):
                sc.add(it)

    def _put_pieces(self, sc, net, pieces):
        prev = None
        for pc in pieces:
            if pc[0] == "via":
                d, h = pc[2] if len(pc) > 2 and pc[2] else via_size(self.profile, self.areas, net, pc[1])
                sc.add(sc.via(net, pc[1], d, h))
            else:
                self._put(sc, net, pc[0], [ipt(p) for p in pc[1]])

    # ---- fans
    def _fan(self, sec, start, sc):
        """Connect the terminal of a section to its first (start) or last line: terminal, an optional straight
        along the lane direction, one 45-degree stub onto the lane line. The straight is the shortest that keeps
        shape and clearance. Returns the points in travel order."""
        net, layer = sec["net"], sec["layer"]
        line = sec["lines"][0 if start else -1]
        f = 1 if start else -1
        Df, N = (f * line.D[0], f * line.D[1]), line.N
        lead = sec["start"] if start else sec["end"]
        T = lead[-1] if start else lead[0]
        beyond = (lead[-2] if len(lead) > 1 else None) if start else (lead[1] if len(lead) > 1 else None)
        nxt = (sec["core"][0] if sec["core"] else None) if start else (sec["core"][-1] if sec["core"] else sec["start_pts"][-1])
        dV = line.V - dot(N, T)
        ul = unit(Df)
        ks = [0] + list(range(int(math.ceil(self.min_seg / ul)), int(self.fan_max / ul), max(1, int(round(self.fan_step / ul)))))
        first_bad, fallback = None, None
        b = sec["bundles"][0 if start else -1]
        for k in ks:
            q = (T[0] + k * Df[0], T[1] + k * Df[1])
            if dV == 0:
                if k:
                    break
                pts = [T]
            else:
                Dj = (sgn(Df[0] + sgn(dV) * N[0]), sgn(Df[1] + sgn(dV) * N[1]))
                try:
                    pts = [T, q, meet(through(Dj, q, tag="fan stub of " + net), line)]
                except RouteError:
                    continue
            if nxt is not None:
                room = (dot(Df, nxt) - dot(Df, pts[-1])) * ul
                if room < self.min_seg - 1e-7:
                    first_bad = first_bad or "the stub joins the lane %.3f mm before the lane's next corner at %s (needs %.2f): move the corner or the terminal" % (room, fpt(nxt), self.min_seg)
                    break
            poly = clean(([beyond] if beyond else []) + pts + ([nxt] if nxt else []))
            errs = shape_errors(poly, self.min_seg, free_first=beyond is not None) + sharp_errors(poly, self.profile.chamfer)
            if errs and not self.sketch:
                first_bad = first_bad or errs[0][1]
                continue
            fallback = fallback or pts
            why = sc.conflict(self._items(sc, net, layer, [fpt(p) for p in poly])) if len(poly) > 1 else None
            if why is None:
                return pts if start else pts[::-1]
            first_bad = first_bad or why
        self.problems.append(F("FAN", "%s %s %s: no stub from %s reaches the lane cleanly (%s)" % (b.name, "start" if start else "end", net, fpt(T), first_bad), net, fpt(T)))
        if fallback is None:
            fallback = [T] if dV == 0 else [T, meet(through((sgn(Df[0] + sgn(dV) * N[0]), sgn(Df[1] + sgn(dV) * N[1])), T, tag="fan stub of " + net), line)]
        return fallback if start else fallback[::-1]

    def _fan_group(self, bundle, start, sc):
        secs = [s for s in self.secs if s["bundles"][0 if start else -1] is bundle]
        rows = []
        for s in secs:
            line = s["lines"][0 if start else -1]
            T = s["start"][-1] if start else s["end"][0]
            rows.append((bundle.idx(s["net"]), line.V - dot(line.N, T), dot(line.N, T), s))
        rows.sort(key=lambda r: r[0])
        for (i, _, vt_i, si), (j, _, vt_j, sj) in zip(rows, rows[1:]):   # the order of the terminals against the lane order
            if si["lines"][0 if start else -1].D == sj["lines"][0 if start else -1].D and vt_i > vt_j:
                ti, tj = (si["start"][-1], sj["start"][-1]) if start else (si["end"][0], sj["end"][0])
                self.problems.append(F("ORDER", "%s %s: lane %s is left of lane %s in the bundle but its terminal %s is on the right of %s: they must cross "
                                       "(swap the lanes, or swap the pins where swapping is allowed)" % (
                                           bundle.name, "start" if start else "end", si["net"], sj["net"], fpt(ti), fpt(tj)), si["net"], fpt(ti), other=sj["net"]))
        order = ([r for r in rows if r[1] == 0] + sorted([r for r in rows if r[1] > 0], key=lambda r: -r[0])
                 + sorted([r for r in rows if r[1] < 0], key=lambda r: r[0]))   # movers to the right: rightmost first; to the left: leftmost first
        for _, _, _, s in order:
            pts = self._fan(s, start, sc)
            if start:
                s["start_pts"] = s["start"][:-1] + pts
                done = s["start_pts"] + s["core"][:1]
            else:
                s["end_pts"] = pts + s["end"][1:]
                done = (s["core"][-1:] or s["start_pts"][-1:]) + s["end_pts"]
            self._put(sc, s["net"], s["layer"], done)

    # ---- output
    def routes(self):
        """{net: pieces} (kept routes included). What went wrong is in bus.problems (findings); a description
        that cannot be turned into geometry at all raises RouteError."""
        if self._routes is not None:
            return self._routes
        self.problems = [p for p in self.problems if p["kind"] == "SLOT"]
        sc = Scene(self.board, self.profile, skip_nets=set(self.plan) | set(self.kept))
        for net, raw in self.kept.items():
            self._put_pieces(sc, net, raw)
        for net, items in self.plan.items():
            for it in items:
                if "raw" in it:
                    self._put_pieces(sc, net, it["raw"])
        for net, p in self.stitch:
            d, h = via_size(self.profile, self.areas, net, p)
            sc.add(sc.via(net, p, d, h))
        for s in self.secs:
            if s["end"] is None:
                raise RouteError("%s is left open at the end of %s (give it an end terminal, a via field or a bundle to run into)" % (s["net"], s["bundles"][-1].name))
            L = s["lines"]
            s["core"] = [meet(L[k], L[k + 1]) for k in range(len(L) - 1)]
            s.pop("start_pts", None); s.pop("end_pts", None)
            self._put(sc, s["net"], s["layer"], s["core"])
        for net, items in self.plan.items():                # the vias at layer changes between items
            flat = [("pt", it["layer"], fpt(it["start"][-1]), fpt(it["end"][0])) if "lines" in it else ("raw", it["raw"]) for it in items]
            prev = None                                     # (layer, point) where the net is
            for x in flat:
                if x[0] == "raw":
                    for pc in x[1]:
                        if pc[0] != "via":
                            if prev and prev[0] not in (None, pc[0]):
                                sc.add(sc.via(net, prev[1], *via_size(self.profile, self.areas, net, prev[1])))
                            prev = (pc[0], pc[1][-1])
                        else:
                            prev = (None, pc[1])
                else:
                    if prev and prev[0] not in (None, x[1]):
                        sc.add(sc.via(net, prev[1], *via_size(self.profile, self.areas, net, prev[1])))
                    prev = (x[1], x[3])
        for b in self.bundles:
            self._fan_group(b, True, sc)
        for b in self.bundles:
            self._fan_group(b, False, sc)
        out = {net: [tuple(pc) for pc in raw] for net, raw in self.kept.items()}
        for net, items in self.plan.items():
            flat = []
            for it in items:
                if "raw" in it:
                    flat += [(pc[0], pc[1]) + tuple(pc[2:]) if pc[0] == "via" else (pc[0], list(pc[1])) for pc in it["raw"]]
                    continue
                L = it["lines"]
                poly = clean(it["start_pts"] + it["core"] + it["end_pts"])
                names = " + ".join(b.name for b in it["bundles"])
                for kind, text, at in (shape_errors(poly, self.min_seg, free_first=len(it["start"]) > 1, free_last=len(it["end"]) > 1)
                                       + sharp_errors(poly, self.profile.chamfer)):
                    self.problems.append(F(kind, "%s (%s): %s" % (net, names, text), net, at, layer=it["layer"]))
                chain = it["start_pts"][-1:] + it["core"] + it["end_pts"][:1]
                for k, l in enumerate(L):                   # every piece must run forwards along its line
                    d = dot(l.D, chain[k + 1]) - dot(l.D, chain[k])
                    if d < 0:
                        self.problems.append(F("SHAPE", "%s: %s runs backwards by %.3f mm (the corners / jogs round it need more room)" % (net, l.tag, -d * unit(l.D)),
                                               net, fpt(chain[k]), layer=it["layer"]))
                flat.append((it["layer"], [fpt(p) for p in poly]))
            pieces = []
            for pc in flat:                                 # vias at layer changes, same-layer neighbours merged
                if pieces and pc[0] != "via" and pieces[-1][0] != "via":
                    if pieces[-1][0] == pc[0]:
                        merged = clean([ipt(p) for p in pieces[-1][1] + pc[1]])
                        pieces[-1] = (pc[0], [fpt(p) for p in merged]); continue
                    pieces.append(("via", pieces[-1][1][-1]))
                pieces.append(pc)
            out[net] = pieces
        self._routes = out
        return out

    # ---- numbers and context
    def lanes(self):
        """{net: "trunk(0) + under(2)"}: the bundles a net runs in and its lane number there."""
        out = {}
        for b in self.bundles:
            for i, n in enumerate(b.nets):
                out[n] = (out[n] + " + " if n in out else "") + "%s(%d)" % (b.name, i)
        return out

    def context(self, na, nb, at):
        """For a clearance finding between two nets: the bundle leg where both are lanes, nearest to `at`.
        -> text "bundle X leg k (dir): lanes A | B are d mm centre to centre", or None."""
        best = None
        for b in self.bundles:
            if na in b.nets and nb in b.nets:
                for k in range(len(b.legs)):
                    on = b.on_leg(k)
                    if b.idx(na) in on and b.idx(nb) in on:
                        d = pt_seg(at, fpt(b.path[k]), fpt(b.path[k + 1]))[0]
                        if best is None or d < best[0]:
                            L = b.legs[k]
                            U = dot(L["D"], ipt((round(at[0], 4), round(at[1], 4))))
                            best = (d, "%s leg %d (%s): lanes %s | %s are %.4f mm centre to centre" % (
                                b.name, k, NAME[L["D"]], na, nb, b.spacing(k, b.idx(na), b.idx(nb), U)))
        return best[1] if best else None

    def tuning(self):
        """The serpentine sites described on the bundles (drawn by tune.py when the routes file has TUNING)."""
        return [s.geometry() for b in self.bundles for s in b.slots]
