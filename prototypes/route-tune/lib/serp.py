"""PROTOTYPE (issue 21): arc serpentines, adapted from the length-tuning prototype's meander.py.

Same drawing as there (segments + PCB_ARCs, every joint tangent, never a 45-degree trapezoid, no piece
shorter than 0.1 mm). What changed for this ticket:
  - the leg pitch is per serpentine (0.5 or 0.3 mm; bend radius r = pitch / 2);
  - humps of one serpentine may have different heights;
  - any straight board track on L1 / L4 / L6 may carry one, also a 0.09 track inside a rule area
    (under the SDRAM body on L4 / L6); such a serpentine must stay inside that rule area, and on L1
    every serpentine stays out of the ball fields;
  - a serpentine is either written out by the variant (TUNING entry with "at") or found by the
    automatic filler ("auto").

Shapes (u along the track from its MCU-side end, v sideways; r = pitch / 2, a = amplitude = sideways
distance from the original centre line to the centre line at the top of a hump):
  hump(a)     arc 90 out, leg a-2r, arc 180, leg a-2r, arc 90 back. Uses 2*pitch of track, adds 2a - (8-2pi)r.
  chain(a[])  humps alternating left / right, legs run straight through the original line (double-sided).
              Uses pitch*(n+1) of track, adds 2*sum(a) - (4-pi)r(n+1).
  bump(th)    three arcs, lower than 2r: for an amount smaller than the lowest hump.
A leg is either absent (a = 2r) or at least 0.105 mm long (0.1 exactly rounds below DRC's min_segment on a diagonal).

Hard limits while placing (common.SERP, a variant may override them with CLEAR = {...}, an entry with
"clr" / "end" / "area_gap"; never below the DRC clearance of the place):
  end       straight kept between the end of the board track (a bend, a via, a width change) and the first arc
  clr       serpentine copper to all other copper on the layer, vias on any layer, pads on L1
  area_gap  a serpentine on a 0.1016 track keeps this far from every rule-area edge;
            a serpentine on a 0.09 track keeps all its copper inside the rule area it is in
  edge      to the board edge;   field: on L1 the centre line stays this far from every ball centre
"""
import heapq, json, math
import numpy as np
import pcbnew
from common import (AREAS, BODY, SERP, MINSEG, W_IN, W_OUT, CLR_IN, CLR_OUT, LID, LNUM, REF, WINDOW, NETS,
                    P, Lp, mm, full, short, in_rect, arc_pts)
import lengths

Q = math.pi / 2
SAMPLE = 0.02
LEG_MIN = MINSEG + 0.005                                    # a leg of exactly 0.1 mm on a 45-degree track rounds to 0.0999999 in nm and DRC flags it
COMPASS = ["E", "SE", "S", "SW", "W", "NW", "N", "NE"]     # y is down, so +y is south
COMPASS_ZH = {"E": "东", "SE": "东南", "S": "南", "SW": "西南", "W": "西", "NW": "西北", "N": "北", "NE": "东北", "both": "两"}


# ---------------------------------------------------------------- shapes
class Turtle:
    def __init__(self, start=(0.0, 0.0), heading=0.0):
        self.p, self.h, self.prims, self.len = start, heading, [], 0.0

    def fwd(self, d):
        if d < 1e-9:
            return
        q = (self.p[0] + d * math.cos(self.h), self.p[1] + d * math.sin(self.h))
        self.prims.append(("seg", self.p, q)); self.p = q; self.len += d

    def arc(self, r, ang):                                  # ang > 0 turns towards +v
        sg = 1 if ang > 0 else -1
        c = (self.p[0] - sg * r * math.sin(self.h), self.p[1] + sg * r * math.cos(self.h))
        a0 = math.atan2(self.p[1] - c[1], self.p[0] - c[0])
        pt = lambda t: (c[0] + r * math.cos(a0 + t), c[1] + r * math.sin(a0 + t))
        q = pt(ang)
        self.prims.append(("arc", self.p, pt(ang / 2), q, c, r, a0, ang)); self.p = q; self.h += ang; self.len += r * abs(ang)


def emit(T, el, sd, r):
    """Draw one element with the turtle; sd = +1 / -1 picks the side of the first hump."""
    if el[0] == "hump":
        a = el[1]
        T.arc(r, Q * sd); T.fwd(a - 2 * r); T.arc(r, -Q * sd); T.arc(r, -Q * sd); T.fwd(a - 2 * r); T.arc(r, Q * sd)
    elif el[0] == "bump":
        rb, th = el[1], el[2]
        T.arc(rb, th * sd); T.arc(rb, -2 * th * sd); T.arc(rb, th * sd)
    elif el[0] == "U":                                      # test shape only: one hump of a chain, from leg to leg
        a = el[1]
        T.h = Q * sd; T.fwd(a - r); T.arc(r, -Q * sd); T.arc(r, -Q * sd); T.fwd(a - r)
    else:                                                   # chain
        amps = el[1]
        T.arc(r, Q * sd); T.fwd(amps[0] - 2 * r)
        for i, a in enumerate(amps):
            T.arc(r, -Q * sd); T.arc(r, -Q * sd)
            if i < len(amps) - 1:
                T.fwd(a + amps[i + 1] - 2 * r); sd = -sd
            else:
                T.fwd(a - 2 * r); T.arc(r, Q * sd)


def measure(els, r):
    """(track used along the original line, length gained) of a list of elements."""
    T = Turtle()
    for el in els:
        emit(T, el, 1, r)
    assert abs(T.p[1]) < 1e-9 and abs(math.sin(T.h)) < 1e-9, "element does not come back tangent"
    return T.p[0], T.len - T.p[0]


def _bisect(f, lo, hi):
    for _ in range(80):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if f(m) < 0 else (lo, m)
    return (lo + hi) / 2


def bump(g, r):
    """A dimple that adds g (< the gain of the lowest hump)."""
    th = _bisect(lambda t: 4 * r * (t - math.sin(t)) - g, 1e-6, Q)
    if r * th >= MINSEG:
        return ("bump", r, th)
    th = _bisect(lambda t: 4 * MINSEG * (1 - math.sin(t) / t) - g, 1e-6, Q)      # keep every arc 0.1 mm long: larger radius
    return ("bump", MINSEG / th, th)


def legal_amp(a, r):
    """An amplitude is legal when its leg (a - 2r) is absent or at least 0.1 mm long."""
    return abs(a - 2 * r) < 1e-6 or a - 2 * r >= LEG_MIN - 1e-9


def solve_heights(amax, need, kind, r):
    """Heights (<= amax[i] each) of len(amax) humps that add exactly `need`, as level as possible.
    Returns a list, or None when these humps cannot add exactly that much."""
    n = len(amax)
    K = n * (8 - 2 * math.pi) * r if kind == "hump" else (4 - math.pi) * r * (n + 1)
    S = (need + K) / 2                                      # required sum of amplitudes
    if S > sum(amax) + 1e-9:
        return None
    must = (lambda i: True) if kind == "hump" else (lambda i: i in (0, n - 1))   # humps whose own leg must be legal
    order = []                                              # indices to pin at 2r, from the ends inwards
    lo, hi = 0, n - 1
    while lo <= hi:
        order.append(hi); hi -= 1
        if lo <= hi:
            order.append(lo); lo += 1
    for npin in range(n + 1):
        pinned = set(order[:npin])
        free = [i for i in range(n) if i not in pinned]
        rest = S - 2 * r * len(pinned)
        if not free:
            if abs(rest) < 1e-7:
                return [2 * r] * n
            continue
        if rest < 2 * r * len(free) - 1e-9 or rest > sum(amax[i] for i in free) + 1e-9:
            continue
        h = _bisect(lambda x: sum(min(amax[i], x) for i in free) - rest, 2 * r, max(amax) + 1e-6)
        amps = [2 * r if i in pinned else min(amax[i], h) for i in range(n)]
        if all(legal_amp(amps[i], r) for i in range(n) if must(i)):
            return amps
    return None


# ---------------------------------------------------------------- board scene
def _d_pts_segs(Pn, A, C):
    """Distances (N, M) from N points to M segments."""
    V = C - A
    L2 = (V * V).sum(1)
    L2 = np.where(L2 == 0, 1.0, L2)
    W = Pn[:, None, :] - A[None, :, :]
    t = np.clip((W * V[None, :, :]).sum(2) / L2[None, :], 0.0, 1.0)
    D = W - t[:, :, None] * V[None, :, :]
    return np.sqrt((D * D).sum(2))


class Scene:
    def __init__(self, B, clear=None):
        self.B = B
        self.clear = dict(SERP); self.clear.update(clear or {})
        eb = B.GetBoardEdgesBoundingBox()
        self.edge = Lp(pcbnew.VECTOR2I(eb.GetLeft(), eb.GetTop())) + Lp(pcbnew.VECTOR2I(eb.GetRight(), eb.GetBottom()))
        self.pads = []                                      # (net, centre, radius, ref)
        for fp in B.GetFootprints():
            for p in fp.Pads():
                self.pads.append((p.GetNetname(), Lp(p.GetPosition()), max(mm(p.GetSizeX()), mm(p.GetSizeY())) / 2, fp.GetReference()))
        self.pad_xy = np.array([p[1] for p in self.pads])
        self.rescan()

    def rescan(self):
        self.lines, self.rounds, self.items = [], [], []    # lines: (net, layer, a, c, half width, track object or None)
        for t in self.B.GetTracks():
            n = t.GetNetname()
            if t.Type() == pcbnew.PCB_VIA_T:
                self.rounds.append((n, None, Lp(t.GetPosition()), mm(t.GetWidth(pcbnew.F_Cu)) / 2))
                continue
            if t.Type() == pcbnew.PCB_ARC_T:
                pts = arc_pts(t, 0.03)
                for a, c in zip(pts, pts[1:]):
                    self.lines.append((n, t.GetLayer(), a, c, mm(t.GetWidth()) / 2, None))
            else:
                self.lines.append((n, t.GetLayer(), Lp(t.GetStart()), Lp(t.GetEnd()), mm(t.GetWidth()) / 2, t))
            self.items.append(t)
        for n, c, rad, _ in self.pads:
            self.rounds.append((n, pcbnew.F_Cu, c, rad))

    def path_pos(self, net):
        """{node: copper distance from the net's U1 pad} and the node function. Layer changes cost nothing here."""
        node = lambda p: (round(p[0], 4), round(p[1], 4))
        adj = {}
        for t in self.B.GetTracks():
            if t.GetNetname() != net or t.Type() == pcbnew.PCB_VIA_T:
                continue
            a, c = node(Lp(t.GetStart())), node(Lp(t.GetEnd()))
            adj.setdefault(a, []).append((c, mm(t.GetLength()))); adj.setdefault(c, []).append((a, mm(t.GetLength())))
        ends = {ref: node(c) for n, c, _, ref in self.pads if n == net}
        dist, heap = {ends["U1"]: 0.0}, [(0.0, ends["U1"])]
        while heap:
            d, p = heapq.heappop(heap)
            if d > dist.get(p, 1e9):
                continue
            for q, l in adj.get(p, []):
                if d + l < dist.get(q, 1e9):
                    dist[q] = d + l; heapq.heappush(heap, (d + l, q))
        return dist, dist.get(ends["U2"], 0.0), node


class Run:
    """One straight board track of a net that may carry a serpentine; a = the end nearer the MCU."""
    def __init__(self, sc, net, t, pos, node, reach, clear=None):
        self.sc, self.net, self.t = sc, net, t
        self.clear = dict(sc.clear); self.clear.update(clear or {})
        a, c = Lp(t.GetStart()), Lp(t.GetEnd())
        self.flip = pos.get(node(a), 0) > pos.get(node(c), 0)
        self.a, self.c = (c, a) if self.flip else (a, c)
        self.L = math.dist(a, c); self.w = mm(t.GetWidth()); self.layer = t.GetLayer()
        self.U = ((self.c[0] - self.a[0]) / self.L, (self.c[1] - self.a[1]) / self.L)
        self.N = (-self.U[1], self.U[0])
        self.pos = min(pos.get(node(a), 0), pos.get(node(c), 0))
        self.thin = self.w < W_OUT - 1e-6
        mid = ((a[0] + c[0]) / 2, (a[1] + c[1]) / 2)
        self.home = next((R for R in AREAS.values() if in_rect(mid, R)), None) if self.thin else None
        floor = CLR_IN if self.thin else CLR_OUT            # never below the DRC clearance of the place
        self.clr = max(self.clear["clr"], floor)
        x0, x1 = min(a[0], c[0]) - reach, max(a[0], c[0]) + reach
        y0, y1 = min(a[1], c[1]) - reach, max(a[1], c[1]) + reach
        hit = lambda p, q: not (max(p[0], q[0]) < x0 or min(p[0], q[0]) > x1 or max(p[1], q[1]) < y0 or min(p[1], q[1]) > y1)
        ln = [(n == net, a2, c2, hw) for n, l, a2, c2, hw, obj in sc.lines if l == self.layer and obj is not t and hit(a2, c2)]
        self.lA = np.array([x[1] for x in ln]).reshape(-1, 2); self.lC = np.array([x[2] for x in ln]).reshape(-1, 2)
        self.lhw = np.array([x[3] for x in ln]); self.lsame = np.array([x[0] for x in ln], dtype=bool)
        rd = [(n == net, c2, rad) for n, l, c2, rad in sc.rounds if l in (None, self.layer) and hit(c2, c2)]
        self.rC = np.array([x[1] for x in rd]).reshape(-1, 2); self.rr = np.array([x[2] for x in rd]); self.rsame = np.array([x[0] for x in rd], dtype=bool)
        self.memo = {}

    def world(self, u, v):
        return (self.a[0] + u * self.U[0] + v * self.N[0], self.a[1] + u * self.U[1] + v * self.N[1])

    def side_name(self, sd):
        return COMPASS[int(round(math.degrees(math.atan2(self.N[1] * sd, self.N[0] * sd)) / 45)) % 8]

    def side_sign(self, name):
        """'N' / 'SE' / ... -> +1 / -1 (the side of this run that points that way), or None if neither does."""
        for sd in (1, -1):
            if self.side_name(sd) == name:
                return sd
        return None

    def fits(self, el, sd, off, why=False):
        """True when element el drawn on side sd at offset off keeps every hard limit. With why=True
        returns (ok, reason text)."""
        key = (json.dumps(el), sd, round(off, 5))
        if not why and key in self.memo:
            return self.memo[key]
        res = self._fits(el, sd, off)
        self.memo[key] = res[0]
        return res if why else res[0]

    def _fits(self, el, sd, off):
        T = Turtle(start=(off, 0.0))
        emit(T, el, sd, self._r)
        uv = []
        for pr in T.prims:
            if pr[0] == "seg":
                d = math.dist(pr[1], pr[2])
                if d < LEG_MIN - 1e-6:                       # never draw a piece DRC's min_segment would flag
                    return False, "a straight piece of %.3f mm (shorter than 0.1)" % d
                n = max(1, int(d / SAMPLE))
                uv += [(pr[1][0] + (pr[2][0] - pr[1][0]) * i / n, pr[1][1] + (pr[2][1] - pr[1][1]) * i / n) for i in range(n + 1)]
            else:
                _, _, _, _, c, rr, a0, ang = pr
                if rr * abs(ang) < MINSEG - 1e-6:
                    return False, "an arc of %.3f mm (shorter than 0.1)" % (rr * abs(ang))
                n = max(2, int(rr * abs(ang) / SAMPLE))
                uv += [(c[0] + rr * math.cos(a0 + ang * i / n), c[1] + rr * math.sin(a0 + ang * i / n)) for i in range(n + 1)]
        uv = np.array(uv)
        q = np.array(self.a)[None, :] + uv[:, :1] * np.array(self.U)[None, :] + uv[:, 1:] * np.array(self.N)[None, :]
        hw, e, cl = self.w / 2, self.sc.edge, self.clear
        g = cl["edge"] + hw
        if (q[:, 0] < e[0] + g).any() or (q[:, 0] > e[2] - g).any() or (q[:, 1] < e[1] + g).any() or (q[:, 1] > e[3] - g).any():
            return False, "too close to the board edge"
        if self.thin:
            R = self.home
            if R is None or (q[:, 0] < R[0] + hw).any() or (q[:, 0] > R[2] - hw).any() or (q[:, 1] < R[1] + hw).any() or (q[:, 1] > R[3] - hw).any():
                return False, "a serpentine on a 0.09 track must stay inside its rule area"
        else:
            g = hw + cl["area_gap"]
            for name, R in AREAS.items():
                if ((q[:, 0] > R[0] - g) & (q[:, 0] < R[2] + g) & (q[:, 1] > R[1] - g) & (q[:, 1] < R[3] + g)).any():
                    return False, "closer than %.3f to rule area %s" % (cl["area_gap"], name)
        if self.layer == pcbnew.F_Cu and len(self.sc.pad_xy):
            d = np.sqrt(((q[:, None, :] - self.sc.pad_xy[None, :, :]) ** 2).sum(2))
            if (d < cl["field"]).any():
                return False, "inside a ball field on L1"
        off_line = np.abs(uv[:, 1]) >= self._r - 1e-6       # points that have left the original centre line
        if len(self.lA):
            D = _d_pts_segs(q, self.lA, self.lC) - (hw + self.lhw + self.clr + 0.002)[None, :]
            bad = (D < 0) & (off_line[:, None] | ~self.lsame[None, :])
            if bad.any():
                i, j = np.argwhere(bad)[0]
                return False, "closer than %.3f to %s track near (%.2f, %.2f)" % (self.clr, "its own" if self.lsame[j] else "another net's", q[i][0], q[i][1])
        if len(self.rC):
            D = np.sqrt(((q[:, None, :] - self.rC[None, :, :]) ** 2).sum(2)) - (hw + self.rr + self.clr + 0.002)[None, :]
            bad = (D < 0) & (off_line[:, None] | ~self.rsame[None, :])
            if bad.any():
                i, j = np.argwhere(bad)[0]
                return False, "closer than %.3f to a via or pad near (%.2f, %.2f)" % (self.clr, self.rC[j][0], self.rC[j][1])
        return True, ""

    # ---- automatic filling of this run
    def set_pitch(self, pitch):
        if getattr(self, "pitch", None) != pitch:
            self._r = pitch / 2; self.pitch = pitch; self.memo = {}

    def amax(self, el_of, sd, off, amp_max):
        """Largest legal amplitude (0.05 grid) for which el_of(a) fits at off, 0 if not even the lowest fits."""
        r = self._r
        if not self.fits(el_of(2 * r), sd, off):
            return 0.0
        grid = [2 * r] + [round(2 * r + 0.15 + 0.05 * i, 4) for i in range(int(max(0.0, amp_max - 2 * r - 0.15) / 0.05 + 1e-9) + 1)]
        grid = [a for a in grid if a <= amp_max + 1e-9]
        if self.fits(el_of(grid[-1]), sd, off):
            return grid[-1]
        lo, hi = 0, len(grid) - 1                           # grid[lo] fits, grid[hi] does not (taller never fits where lower fails)
        while hi - lo > 1:
            m = (lo + hi) // 2
            if self.fits(el_of(grid[m]), sd, off):
                lo = m
            else:
                hi = m
        return grid[lo]

    def options(self, need, amp_max, sides=("single", "chain"), where="middle", only_side=None, count=None):
        """Candidate serpentines on this run for adding `need`: [(complete, gain, kind, sd, off, els)], best first.
        Of the blocks that add exactly `need` the one with the MOST humps is taken (low and long before tall
        and short: amplitude grows only when the straight is too short); count = n forces exactly n humps."""
        r, p, end = self._r, self.pitch, self.clear["end"]
        out = []
        room = self.L - 2 * end
        center = {"middle": lambda k, m, n: abs(k + m / 2 - n / 2), "mcu": lambda k, m, n: k, "sdram": lambda k, m, n: -k}[where]
        for kind in sides:
            for sd in (1, -1):
                if only_side is not None and sd != only_side:
                    continue
                if kind == "single":
                    n = int((room + 1e-9) / (2 * p)); step = 2 * p; o0 = end + (room - n * step) / 2
                    am = [self.amax(lambda a: ("hump", a), sd, o0 + k * step, amp_max) for k in range(n)]
                else:
                    n = int((room - p + 1e-9) / p); step = p; o0 = end + (room - p - n * step) / 2
                    am = [self.amax(lambda a: ("U", a), sd * (-1) ** k, o0 + r + k * step, amp_max) for k in range(n)]
                if n < (1 if kind == "single" else 2):
                    continue
                ekind = "hump" if kind == "single" else "chain"
                make = (lambda amps: [("hump", a) for a in amps]) if kind == "single" else (lambda amps: [("chain", list(amps))])
                best = None
                for m in range(n, (1 if kind == "single" else 2) - 1, -1):   # the block with the most humps that adds exactly `need`
                    if count is not None and m != count:
                        continue
                    cands = []
                    for k in range(0, n - m + 1):
                        sub = am[k:k + m]
                        if min(sub) <= 0:
                            continue
                        cap = measure(make(sub), r)[1]
                        cands.append((center(k, m, n), k, cap))
                    full_ok = [c for c in cands if c[2] >= need - 1e-9]
                    if full_ok:
                        for _, k, cap in sorted(full_ok):
                            amps = solve_heights(am[k:k + m], need, ekind, r)
                            if amps:
                                best = (True, need, k, amps); break
                        if best:
                            break
                    for _, k, cap in cands:                 # remember the largest partial block
                        if best is None or (not best[0] and cap > best[1] + 1e-9):
                            best = (False, cap, k, am[k:k + m])
                if best:
                    done, gain, k, amps = best
                    sd0 = sd if kind == "single" else sd * (-1) ** k
                    els = make(amps)
                    out.append((done, measure(els, r)[1], kind, sd0, o0 + k * step, els))
        if need < (2 * math.pi - 4) * r + 1e-9 and need > 0.02:           # less than the lowest hump: one dimple
            el = bump(need, r)
            base = measure([el], r)[0]
            for sd in (1, -1):
                if only_side is not None and sd != only_side:
                    continue
                for off in sorted([end + i * 0.05 for i in range(int(max(0, room - base) / 0.05) + 1)], key=lambda o: abs(o + base / 2 - self.L / 2)):
                    if self.fits(el, sd, off):
                        out.append((True, need, "bump", sd, off, [el])); break
        out.sort(key=lambda o: (not o[0], -o[1] if not o[0] else 0, {"single": 0, "bump": 1, "chain": 2}[o[2]]))
        return out

    def commit(self, els, sd, off):
        """Replace the board track by lead + serpentine + tail. Returns the block record."""
        B, t, r = self.sc.B, self.t, self._r
        T = Turtle(start=(off, 0.0))
        for el in els:
            emit(T, el, sd, r)
        end_u = T.p[0]
        pa, pc = (t.GetEnd(), t.GetStart()) if self.flip else (t.GetStart(), t.GetEnd())
        net, layer, w = t.GetNet(), t.GetLayer(), t.GetWidth()
        B.Remove(t)

        def seg(p, q):
            s = pcbnew.PCB_TRACK(B); s.SetStart(p); s.SetEnd(q); s.SetWidth(w); s.SetLayer(layer); s.SetNet(net); B.Add(s)

        W = lambda p: P(self.world(p[0], p[1]))
        seg(pa, W((off, 0.0)))
        inside = total = 0.0
        for pr in T.prims:
            if pr[0] == "seg":
                seg(W(pr[1]), W(pr[2]))
                pts = [pr[1], pr[2]]
            else:
                a = pcbnew.PCB_ARC(B); a.SetStart(W(pr[1])); a.SetMid(W(pr[2])); a.SetEnd(W(pr[3]))
                a.SetWidth(w); a.SetLayer(layer); a.SetNet(net); B.Add(a)
                _, _, _, _, c, rr, a0, ang = pr
                n = max(4, int(rr * abs(ang) / 0.01))
                pts = [(c[0] + rr * math.cos(a0 + ang * i / n), c[1] + rr * math.sin(a0 + ang * i / n)) for i in range(n + 1)]
            for p0, p1 in zip(pts, pts[1:]):                 # share of the serpentine copper under the SDRAM body
                d = math.dist(p0, p1); total += d
                if in_rect(self.world((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2), BODY["U2"]):
                    inside += d
        seg(W((end_u, 0.0)), pc)
        amps, humps, bumps = [], 0, 0
        for el in els:
            if el[0] == "hump":
                humps += 1; amps.append(el[1])
            elif el[0] == "bump":
                bumps += 1; amps.append(2 * el[1] * (1 - math.cos(el[2])))
            else:
                humps += len(el[1]); amps += el[1]
        gain = T.len - (end_u - off)
        p0, p1 = self.world(off, 0), self.world(end_u, 0)
        return {"net": self.net.lstrip("/"), "layer": LNUM[layer], "kind": "chain" if els[0][0] == "chain" else "single",
                "side": "both" if els[0][0] == "chain" else self.side_name(sd), "pitch": round(2 * r, 4), "width": round(mm(w), 4),
                "from": [round(v, 3) for v in p0], "to": [round(v, 3) for v in p1], "gain": round(gain, 5),
                "humps": humps, "bumps": bumps, "amps": [round(a, 3) for a in amps], "run_length": round(self.L, 3),
                "under_sdram": round(inside / total, 4) if total else 0.0, "inside_area": self.thin}


# ---------------------------------------------------------------- placing
def pitch_of(net, pitch_cfg):
    """Leg pitch for a net: SDCLK is never tighter than 0.5; data / DQM nets take the variant's value."""
    p = pitch_cfg.get(short(net), pitch_cfg.get(full(net), pitch_cfg.get("default", 0.5))) if isinstance(pitch_cfg, dict) else float(pitch_cfg)
    if full(net) == REF and p < 0.5 - 1e-9:
        raise SystemExit("SDCLK serpentine pitch %.2f: the clock must not be tighter than 0.5 mm" % p)
    if p < 0.3 - 1e-9:
        raise SystemExit("%s: pitch %.2f is below 0.3 mm" % (net, p))
    return p


def _runs(sc, net, reach, min_run, outside_only, layers, used, clear=None):
    pos, total, node = sc.path_pos(net)
    out = []
    for t in sc.items:
        if t.GetNetname() != net or t.Type() == pcbnew.PCB_ARC_T or LNUM[t.GetLayer()] not in layers or mm(t.GetLength()) < min_run - 1e-9:
            continue
        if outside_only and mm(t.GetWidth()) < W_OUT - 1e-6:
            continue
        R = Run(sc, net, t, pos, node, reach, clear)
        if (round(R.a[0], 3), round(R.a[1], 3), round(R.U[0], 3), round(R.U[1], 3)) in used:
            continue
        out.append(R)
    return out, total


def auto_net(sc, net, need, pitch, amp_max=2.0, amp_pref=1.0, min_run=2.5, outside_only=True, layers=("L1", "L4", "L6"),
             sides=("single", "chain"), where="middle", clear=None, log=None):
    """Add `need` mm to a net wherever the hard limits allow: run by run (nearest the middle of the net
    first), single-sided before double-sided, as many humps as the straight takes and no taller than
    amp_pref; if no run can take it all that way, the same with humps up to amp_max; if still none, the
    run that takes the most is filled and the rest goes to the next run.
    Returns (blocks, missing mm)."""
    net = "/" + full(net)
    blocks, rem, used = [], need, set()
    while rem > 5e-3:
        sc.rescan()
        runs, total = _runs(sc, net, amp_max + 1.0, min_run, outside_only, layers, used, clear)
        runs.sort(key={"mcu": lambda R: R.pos, "sdram": lambda R: -R.pos, "middle": lambda R: abs(R.pos + R.L / 2 - total / 2)}[where])
        pick = None
        for cap in ([amp_pref] if amp_pref < amp_max - 1e-9 else []) + [amp_max]:
            pick = None
            for R in runs:
                R.set_pitch(pitch)
                for o in R.options(rem, cap, sides, where):
                    if o[0]:
                        pick = (R, o); break
                    if pick is None or (not pick[1][0] and o[1] > pick[1][1] + 1e-9):
                        pick = (R, o)
                if pick and pick[1][0]:
                    break
            if pick and pick[1][0]:
                break
        if pick is None or pick[1][1] < 0.02:
            break
        R, (done, gain, kind, sd, off, els) = pick
        b = R.commit(els, sd, off)
        for q in (R.a, R.c, tuple(b["to"])):                 # the leftovers of this track are closed for more humps
            used.add((round(q[0], 3), round(q[1], 3), round(R.U[0], 3), round(R.U[1], 3)))
        blocks.append(b); rem -= b["gain"]
        if log:
            log("  %s: +%.3f on %s, %s side, %d humps %s" % (short(net), b["gain"], b["layer"], b["side"], b["humps"], b["amps"]))
    return blocks, (rem if rem > 5e-3 else 0.0)


def explicit(sc, e, pitch_cfg, cur_len, force=False):
    """One serpentine written out by the variant. e (dict) keys:
       net, at (x, y) = any point on the straight it sits on, [layer]
       pitch            leg pitch (default: the variant's PITCH for that net)
       side             'N' 'S' 'E' 'W' 'NE' 'NW' 'SE' 'SW' (board directions), 'both' (double-sided), or 'auto'
       amps [a, ...]    hump heights, drawn exactly;  or  n + amp   n equal humps;
       add mm  /  to mm the amount to add / the net length to reach: the heights are solved (as many humps as
                        the straight takes, as level as possible, each at most amp_max, default 2.0, and at
                        most what fits); with n = the number of humps is fixed and only the heights are solved;
       where            'middle' (default), 'mcu', 'sdram', or the offset in mm from the MCU-side end of the track
       first            for side 'both': the side of the first hump (a board direction)
       clr / end / area_gap   override the hard limits for this serpentine
    Returns (block or None, message)."""
    net = "/" + full(e["net"])
    pitch = e.get("pitch") or pitch_of(net, pitch_cfg)
    pitch_of(net, {"default": pitch})
    r = pitch / 2
    clear = {k: e[k] for k in ("clr", "end", "area_gap") if k in e}
    sc.rescan()
    pos, total, node = sc.path_pos(net)
    lay = LID[e["layer"]] if e.get("layer") else None
    best = None
    for t in sc.items:
        if t.GetNetname() != net or t.Type() == pcbnew.PCB_ARC_T or (lay is not None and t.GetLayer() != lay):
            continue
        a, c = Lp(t.GetStart()), Lp(t.GetEnd())
        vx, vy = c[0] - a[0], c[1] - a[1]
        tt = max(0, min(1, ((e["at"][0] - a[0]) * vx + (e["at"][1] - a[1]) * vy) / (vx * vx + vy * vy)))
        d = math.hypot(e["at"][0] - a[0] - tt * vx, e["at"][1] - a[1] - tt * vy)
        if best is None or d < best[0]:
            best = (d, t)
    if best is None or best[0] > 0.05:
        raise SystemExit("TUNING %s: no straight track of the net within 0.05 mm of 'at' %s%s" % (short(net), e["at"], " on " + e["layer"] if e.get("layer") else ""))
    amp_max = e.get("amp_max", 2.0)
    R = Run(sc, net, best[1], pos, node, max(amp_max, max(e.get("amps", [0]) + [e.get("amp", 0)])) + 1.0, clear)
    R.set_pitch(pitch)
    side = e.get("side", "auto")
    where = e.get("where", "middle")
    tag = "TUNING %s at %s" % (short(net), tuple(e["at"]))
    if "amps" in e or ("n" in e and "amp" in e):
        amps = list(e["amps"]) if "amps" in e else [e["amp"]] * e["n"]
        chain = side == "both" and len(amps) > 1
        for i, a in enumerate(amps):                        # inside a chain the leg is shared by two humps (a + next - 2r >= 2r): any height >= pitch is fine there
            if a < 2 * r - 1e-9 or (not legal_amp(a, r) and not (chain and 0 < i < len(amps) - 1)):
                raise SystemExit("%s: amplitude %.3f is illegal for pitch %.2f (either exactly %.2f, or at least %.3f so that the leg is >= 0.105 mm)" % (tag, a, pitch, 2 * r, 2 * r + LEG_MIN))
        if side == "both":
            els = [("chain", amps)] if len(amps) > 1 else [("hump", amps[0])]
            sds = [R.side_sign(e["first"])] if e.get("first") else [1, -1]
        else:
            els = [("hump", a) for a in amps]
            sds = [1, -1] if side == "auto" else [R.side_sign(side)]
        if sds[0] is None:
            raise SystemExit("%s: side %s is not a side of this track (its sides are %s and %s)" % (tag, e.get("first") or side, R.side_name(1), R.side_name(-1)))
        base = measure(els, r)[0]
        end = R.clear["end"]
        if base > R.L - 2 * end + 1e-9:
            raise SystemExit("%s: the serpentine needs %.2f mm of straight plus %.2f at each end, the track is %.2f mm long" % (tag, base, end, R.L))
        if isinstance(where, (int, float)):
            offs = [float(where)]
        else:
            offs = sorted([end + i * 0.05 for i in range(int((R.L - 2 * end - base) / 0.05 + 1e-9) + 1)] + [R.L - end - base],
                          key={"middle": lambda o: abs(o + base / 2 - R.L / 2), "mcu": lambda o: o, "sdram": lambda o: -o}[where])
        reason = ""
        for off in offs:
            for sd in sds:
                x, ok = off, True
                for el in els:
                    ok, reason = R.fits(el, sd, x, why=True)
                    if not ok:
                        break
                    x += measure([el], r)[0]
                if ok:
                    return R.commit(els, sd, off), ""
        if force:
            return R.commit(els, sds[0], offs[0]), "FORCED although it breaks a limit: " + reason
        raise SystemExit("%s: does not fit anywhere on this track (%s). Lower it, move it, or run with --force to draw it anyway and look." % (tag, reason))
    need = e["add"] if "add" in e else e["to"] - cur_len
    if need < 5e-3:
        return None, "%s: nothing to add (%.3f)" % (tag, need)
    kinds = ("chain",) if side == "both" else (("single", "chain") if side == "auto" else ("single",))
    only = None if side in ("auto", "both") else R.side_sign(side)
    if side not in ("auto", "both") and only is None:
        raise SystemExit("%s: side %s is not a side of this track (its sides are %s and %s)" % (tag, side, R.side_name(1), R.side_name(-1)))
    opts = R.options(need, amp_max, kinds, where if isinstance(where, str) else "middle", only, e.get("n"))
    if not opts or not opts[0][0]:
        got = opts[0][1] if opts else 0.0
        if force and opts:
            done, gain, kind, sd, off, els = opts[0]
            return R.commit(els, sd, off), "PARTIAL: wanted +%.3f, only +%.3f fits on this track" % (need, gain)
        raise SystemExit("%s: +%.3f mm does not fit on this track (%.2f mm long, at most +%.3f with amp_max %.2f and pitch %.2f). "
                         "Use another track, raise amp_max, or run with --force to draw what fits." % (tag, need, R.L, got, amp_max, pitch))
    done, gain, kind, sd, off, els = opts[0]
    return R.commit(els, sd, off), ""


def run_tuning(B, var, log=print, force=False):
    """Apply the variant's TUNING list to board B (in memory). Returns the tune record."""
    pitch_cfg = getattr(var, "PITCH", {"default": 0.5})
    sc = Scene(B, getattr(var, "CLEAR", None))
    nat = {n: v["length"] for n, v in lengths.geometric(B).items()}
    cur = dict(nat)
    blocks, notes, missing = [], [], {}
    for e in var.TUNING:
        if "auto" not in e:
            n = full(e["net"])
            b, msg = explicit(sc, e, pitch_cfg, cur[n], force)
            if msg:
                notes.append(msg); log("  " + msg)
            if b:
                blocks.append(b); cur[n] += b["gain"]
                log("  %s: +%.3f on %s, %s side, %d humps %s" % (short(n), b["gain"], b["layer"], b["side"], b["humps"], b["amps"]))
            continue
        opt = dict(amp_max=2.0, amp_pref=1.0, min_run=2.5, outside_only=True, layers=("L1", "L4", "L6"), sides=("single", "chain"), where="middle")
        opt.update({k: v for k, v in e.items() if k in opt})
        if e["auto"] == "net":                              # {"auto": "net", "net": ..., "add": mm | "to": mm}
            n = full(e["net"])
            need = e["add"] if "add" in e else e["to"] - cur[n]
            bl, miss = auto_net(sc, n, need, pitch_of(n, pitch_cfg), log=log, **opt)
            blocks += bl; cur[n] += sum(b["gain"] for b in bl)
            if miss:
                missing[n] = round(miss, 4)
            continue
        assert e["auto"] == "window", "unknown auto mode %r" % e["auto"]
        # Route-first-then-tune: the clock first, towards (longest - WINDOW); then every net that is still
        # below the window, neediest first, only up to the lower edge of the window (+ margin).
        margin = e.get("margin", 0.05)
        goal = max(cur.values()) - WINDOW + margin
        if goal > cur[REF] + 5e-3:
            bl, miss = auto_net(sc, REF, goal - cur[REF], pitch_of(REF, pitch_cfg), log=log, **opt)
            blocks += bl; cur[REF] += sum(b["gain"] for b in bl)
            if miss:
                missing[REF] = round(miss, 4)
        low = cur[REF] - WINDOW + margin
        for n in sorted((n for n in cur if n != REF), key=lambda n: cur[n]):
            if low - cur[n] > 5e-3:
                bl, miss = auto_net(sc, n, low - cur[n], pitch_of(n, pitch_cfg), log=log, **opt)
                blocks += bl; cur[n] += sum(b["gain"] for b in bl)
                if miss:
                    missing[n] = round(miss, 4)
    return {"natural": {n: round(v, 4) for n, v in nat.items()}, "predicted": {n: round(v, 4) for n, v in cur.items()},
            "blocks": blocks, "notes": notes, "missing": missing, "clear": sc.clear,
            "pitch": pitch_cfg if isinstance(pitch_cfg, dict) else {"default": pitch_cfg}}
