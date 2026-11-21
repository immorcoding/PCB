"""BGA fan-out by rule: escape leads from chosen balls to the edge of the package's rule area.

    fo = Fanout(board, profile, "U201")
    res = fo.escape({"M14": "E", "L14": None, "C12": "N:via", ...}, inner="L4", l1_depth=1)
    res.leads["M14"].pieces         route pieces from the pad outwards (give a Lead to Bus.add as a start
                                    terminal, lead.reversed() as an end terminal)
    res.lanes("E", "L1")            the lanes at the edge, LEFT to RIGHT seen along the way out: the order a
                                    bundle that takes them over has to have
    res.refused                     {ball: why it could not be drawn}

A request is None (nearest side, automatic) or "<side>[+|-][:mode][@layer]": side N / E / S / W; + / - = prefer
the line on the higher / lower side (higher x for N and S, higher y for E and W); mode straight, L1, via, aisle;
@layer = the inner layer of this ball's dog-bone (instead of `inner`), e.g. "E+:via@L6" or "S@L4".
A mode is binding (no other mode is tried); a sign together with a mode is binding too (only that line).
keep = {net: route pieces} drawn before (other fan-outs, hand leads): obstacles for every candidate.

The rules (h = half the ball pitch; "depth" = balls between this one and the edge on its way out):
  straight  depth 0: one segment from the pad straight out, on the pad's layer.
  L1        depth 1 .. l1_depth: 45 degrees onto the channel line midway between two ball rows (h to one
            side), then straight out between the pads.
  via       dog-bone: h * sqrt(2) of track at 45 degrees to a via at the centre of four balls, then on the
            `inner` layer (a name, or several in order of preference) 45 degrees onto a ball-row line and
            straight out. On an inner layer the vias of all
            dog-bones sit on the channel lines, so a track on a ball-row line runs exactly midway between
            two rows of vias: with 0.30 / 0.15 vias at 0.65 pitch that is the 0.205 mm hole-to-track case
            (limit 0.2): the track must be centred, which it is by construction. First choice is the via on
            the way out with the track going straight on through it (no turn at the via) onto the NEXT row's
            line; then the ball's own row line (90 degrees at the via); then the two vias behind the ball.
  aisle     towards a gap of two or more missing rows: a straight stub one pitch into the gap.
Capacity assumed (Profile.tracks_per_channel = 1): one track per channel line on the pad layer, one track
per ball-row line on an inner layer, per side; a line is never given twice. A via is only ever placed at
the centre of four ball positions and never where any pad is. A lead that cannot be drawn with the
clearances of the place (checked against every pad, track and via on the board and the leads already drawn)
is refused with the reason; with automatic requests the generator runs twice (preferring + and then -) and
keeps the run with fewer refusals.
"""
import math
from .geom import G, R2, DIRS, RouteError, dot, right, fpt, ipt
from .routes import split_widths, via_size
from .checks import Scene

SIDES = ("N", "E", "S", "W")


class Lead:
    def __init__(self, net, ball, side, kind, layer, pieces, lat, depth, via=None, turn=0):
        self.net, self.ball, self.side, self.kind, self.layer, self.pieces = net, ball, side, kind, layer, pieces
        self.lat, self.depth, self.via, self.turn = lat, depth, via, turn
        self.end = pieces[-1][1][-1]

    def reversed(self):
        """The same lead written towards the pad (for the end terminal of a bundle)."""
        rp = [(pc[0], pc[1]) + tuple(pc[2:]) if pc[0] == "via" else (pc[0], list(pc[1])[::-1]) for pc in self.pieces[::-1]]
        return Lead(self.net, self.ball, self.side, self.kind, self.layer, rp, self.lat, self.depth, self.via, self.turn)


class Result:
    def __init__(self, ref, leads, refused, notes):
        self.ref, self.leads, self.refused, self.notes = ref, leads, refused, notes

    def lanes(self, side=None, layer=None):
        """[Lead] at the edge, left to right seen along the way out, for one side / layer (or all, grouped)."""
        out = []
        for s in SIDES if side is None else (side,):
            R = right(DIRS[s])
            ls = [l for l in self.leads.values() if l.side == s and l.kind != "aisle" and (layer is None or l.layer == layer)]
            out += sorted(ls, key=lambda l: (l.layer, dot(R, l.end)))
        return out

    def routes(self):
        return {l.net: l.pieces for l in self.leads.values()}

    def by_net(self):
        return {l.net: l for l in self.leads.values()}

    def text(self):
        o = ["fan-out of %s: %d leads drawn, %d refused" % (self.ref, len(self.leads), len(self.refused))]
        for s in SIDES:
            for lay in sorted({l.layer for l in self.leads.values() if l.side == s}):
                ls = self.lanes(s, lay)
                if ls:
                    o.append("  side %s on %s, left to right going out (%d): %s" % (s, lay, len(ls), "  ".join("%s[%s %s]" % (l.net, l.ball, l.kind) for l in ls)))
            a = [l for l in self.leads.values() if l.side == s and l.kind == "aisle"]
            if a:
                o.append("  side %s, stubs into the aisle (%d): %s" % (s, len(a), "  ".join("%s[%s]" % (l.net, l.ball) for l in a)))
        for b, why in sorted(self.refused.items()):
            o.append("  REFUSED %s: %s" % (b, why))
        return "\n".join(o)


class Fanout:
    def __init__(self, board, profile, ref):
        self.board, self.profile, self.ref = board, profile, ref
        pads = board.by_ref.get(ref)
        if not pads:
            raise RouteError("fan-out: no part %s on the board" % ref)
        self.P = {p.num: ipt(p.pos) for p in pads}
        self.padof = {p.num: p for p in pads}
        xs, ys = sorted({q[0] for q in self.P.values()}), sorted({q[1] for q in self.P.values()})
        steps = [b - a for a, b in zip(xs, xs[1:])] + [b - a for a, b in zip(ys, ys[1:])]
        if not steps:
            raise RouteError("fan-out: %s is not a grid of pads" % ref)
        self.pitch = min(steps)
        if self.pitch % 2 or any(s % self.pitch for s in steps):
            raise RouteError("fan-out: the pads of %s are not on a regular grid (pitch %.4f)" % (ref, self.pitch / G))
        self.h = self.pitch // 2
        self.x0, self.y0 = xs[0], ys[0]
        self.nx, self.ny = (xs[-1] - xs[0]) // self.pitch + 1, (ys[-1] - ys[0]) // self.pitch + 1
        self.ij = {b: ((q[0] - self.x0) // self.pitch, (q[1] - self.y0) // self.pitch) for b, q in self.P.items()}
        self.occ = {v: k for k, v in self.ij.items()}
        self.areas = board.rule_areas(profile.area_names)
        f = (xs[0] / G, ys[0] / G, xs[-1] / G, ys[-1] / G)
        self.area = next((R for R in self.areas.values() if R[0] <= f[0] and R[1] <= f[1] and R[2] >= f[2] and R[3] >= f[3]), None)
        layers = {next(iter(p.layers)) for p in pads if p.layers}
        self.top = sorted(layers)[0] if layers else "L1"

    def ring(self, ball):
        i, j = self.ij[ball]
        return min(i, j, self.nx - 1 - i, self.ny - 1 - j)

    def depth(self, ball, side):
        """(balls between this ball and the edge on side `side`, missing positions right in front of it)."""
        i, j = self.ij[ball]
        d = DIRS[side]
        n, gap, front = 0, 0, True
        i, j = i + d[0], j + d[1]
        while 0 <= i < self.nx and 0 <= j < self.ny:
            if (i, j) in self.occ:
                n += 1; front = False
            elif front:
                gap += 1
            i, j = i + d[0], j + d[1]
        return n, (gap if n else 0)

    def nearest(self, ball):
        i, j = self.ij[ball]
        dist = {"N": j, "E": self.nx - 1 - i, "S": self.ny - 1 - j, "W": i}
        m = min(dist.values())
        tied = [s for s in SIDES if dist[s] == m]           # N, E, S, W: on a diagonal every ball of a corner takes the same side
        return min(tied, key=lambda s: (self.depth(ball, s)[0], SIDES.index(s)))

    def _edge(self, p, side, reach):
        d = DIRS[side]
        if reach is None and self.area is not None:
            R = [int(round(v * G)) for v in self.area]
            lim = {"E": R[2], "W": R[0], "S": R[3], "N": R[1]}[side]
        else:
            r = int(round((reach if reach is not None else 1.5 * self.pitch / G) * G))
            lim = {"E": self.x0 + (self.nx - 1) * self.pitch + r, "W": self.x0 - r, "S": self.y0 + (self.ny - 1) * self.pitch + r, "N": self.y0 - r}[side]
        return (lim, p[1]) if d[0] else (p[0], lim)

    def _candidates(self, ball, side, mode, pref, inner, l1_depth, reach, strict=False):
        """Yield (kind, layer, line key or None, pieces as integer points, via point or None, turn at via)."""
        P, h, d = self.P[ball], self.h, DIRS[side]
        l = (0, 1) if d[0] else (1, 0)                      # lateral axis: +y for E / W, +x for N / S
        lat = dot(l, P)
        depth, gap = self.depth(ball, side)
        add = lambda p, a, b: (p[0] + a * d[0] + b * l[0], p[1] + a * d[1] + b * l[1])
        sls = (pref,) if strict else (pref, -pref)
        modes = [mode] if mode else (["straight"] if depth == 0 else (["L1"] if depth <= l1_depth else []) + (["via"] if inner else []))
        for m in modes:
            if m == "straight":
                yield "straight", self.top, (side, self.top, lat), [(self.top, [P, self._edge(P, side, reach)])], None, 0
            elif m == "L1":
                for sl in sls:
                    q = add(P, h, sl * h)
                    yield "channel", self.top, (side, self.top, lat + sl * h), [(self.top, [P, q, self._edge(q, side, reach)])], None, 0
            elif m == "via":
                if not inner:
                    raise RouteError("fan-out %s.%s: mode via needs inner=<layer>" % (self.ref, ball))
                for lay in ((inner,) if isinstance(inner, str) else tuple(inner)):
                    for sd, own, turn in ((1, False, 0), (1, True, 2), (-1, False, 2)):
                        for sl in sls:
                            v = add(P, sd * h, sl * h)
                            q = add(v, h, -sl * h) if own else add(v, h, sl * h)
                            line = lat if own else lat + 2 * sl * h
                            yield "via", lay, (side, lay, line), [(self.top, [P, v]), ("via", v), (lay, [v, q, self._edge(q, side, reach)])], v, turn
            elif m == "aisle":
                yield "aisle", self.top, None, [(self.top, [P, add(P, 2 * h, 0)])], None, 0
            else:
                raise RouteError("fan-out %s.%s: unknown mode %r" % (self.ref, ball, m))

    def _try(self, sc, used, net, cand):
        """None when the candidate can be drawn (then it is added to the scene), else the reason."""
        kind, layer, key, pieces, v, turn, ball = cand
        pr = self.profile
        if key is not None and key in used:
            side, lay, lat = key
            what = "channel between two ball rows" if kind == "channel" else "ball-row line"
            return "CHANNEL the %s at %s = %.4f on %s, side %s, already carries %s (one track per line)" % (
                what, "y" if side in "EW" else "x", lat / G, lay, side, used[key])
        if v is not None:
            vf = fpt(v)
            for p in self.board.pads.values():
                if math.dist(p.pos, vf) < p.r:
                    return "VIAPAD the via at (%.4f, %.4f) would sit on pad %s" % (vf[0], vf[1], p.name)
        items = []
        for pc in pieces:
            if pc[0] == "via":
                p = fpt(pc[1])
                items.append(sc.via(net, p, *via_size(pr, self.areas, net, p)))
            else:
                items += [sc.seg(net, pc[0], a, c, w) for a, c, w in split_widths([fpt(p) for p in pc[1]], self.areas, pr.w_area, pr.width(net), pr.extend, pr.min_seg)]
        why = sc.conflict(items)
        if why:
            return "GAP " + why
        for it in items:
            sc.add(it)
        if key is not None:
            used[key] = "%s (%s)" % (net, ball)
        return None

    def _run(self, reqs, pref0, inner, l1_depth, reach, keep=None):
        sc = Scene(self.board, self.profile, skip_nets={self.padof[b].net for b in reqs} | set(keep or ()))
        for net, pieces in (keep or {}).items():            # routes drawn before: obstacles
            for pc in pieces:
                if pc[0] == "via":
                    p = (float(pc[1][0]), float(pc[1][1]))
                    sc.add(sc.via(net, p, *(tuple(pc[2]) if len(pc) > 2 and pc[2] else via_size(self.profile, self.areas, net, p))))
                else:
                    pts = [self.board.pad(q, net).pos if isinstance(q, str) else (float(q[0]), float(q[1])) for q in pc[1]]
                    for a, c, w in split_widths(pts, self.areas, self.profile.w_area, self.profile.width(net), self.profile.extend, self.profile.min_seg):
                        sc.add(sc.seg(net, pc[0], a, c, w))
        used, leads, refused, plan = {}, {}, {}, []
        for ball, spec in reqs.items():
            if ball not in self.P:
                raise RouteError("fan-out: %s has no pad %r" % (self.ref, ball))
            side, pref, mode, strict, lay = None, pref0, None, False, inner
            if spec:
                spec, _, at = spec.partition("@")
                if at:
                    if at not in self.board.cu:
                        raise RouteError("fan-out %s.%s: unknown layer %r" % (self.ref, ball, at))
                    lay = at
                s, _, mode = spec.partition(":")
                mode = mode or None
                if s.endswith(("+", "-")):
                    pref, s, strict = (1 if s[-1] == "+" else -1), s[:-1], mode is not None
                side = s or None
                if side is not None and side not in SIDES:
                    raise RouteError("fan-out %s.%s: side %r is not N, E, S or W" % (self.ref, ball, side))
            side = side or self.nearest(ball)
            plan.append((SIDES.index(side), self.depth(ball, side)[0], dot((0, 1) if DIRS[side][0] else (1, 0), self.P[ball]) * pref0, ball, side, pref, mode, strict, lay))
        for _, depth, _, ball, side, pref, mode, strict, lay in sorted(plan, key=lambda r: r[:4]):
            net = self.padof[ball].net
            if not net:
                refused[ball] = "the pad has no net"
                continue
            why = []
            for cand in self._candidates(ball, side, mode, pref, lay, l1_depth, reach, strict):
                r = self._try(sc, used, net, cand + (ball,))
                if r is None:
                    kind, layer, key, pieces, v, turn = cand
                    out = [("via", fpt(pc[1])) if pc[0] == "via" else (pc[0], [fpt(p) for p in pc[1]]) for pc in pieces]
                    R = right(DIRS[side])
                    leads[ball] = Lead(net, ball, side, kind, layer, out, dot(R, out[-1][1][-1]), depth, fpt(v) if v else None, 45 * turn)
                    break
                why.append(r)
            else:
                d, gap = self.depth(ball, side)
                refused[ball] = "; ".join(dict.fromkeys(why)) if why else ("%s side %s: %d balls in the way, escapes on %s are allowed to depth %d and no inner layer was given" % (
                    net, side, d, self.top, l1_depth))
        return leads, refused

    def escape(self, balls, inner=None, l1_depth=1, reach=None, keep=None):
        """balls = {pad number: request or None} (or a list of pad numbers: all automatic). See the module text."""
        reqs = dict(balls) if isinstance(balls, dict) else {b: None for b in balls}
        best = None
        for pref in (1, -1):
            leads, refused = self._run(reqs, pref, inner, l1_depth, reach, keep)
            score = (len(refused), sum(1 for l in leads.values() if l.turn), 0 if pref == 1 else 1)
            if best is None or score < best[0]:
                best = (score, leads, refused, pref)
            if not refused and not score[1]:
                break
        notes = ["automatic choices prefer the %s line (run %s)" % ("higher" if best[3] == 1 else "lower", "+" if best[3] == 1 else "-")]
        return Result(self.ref, best[1], best[2], notes)
