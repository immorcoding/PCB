"""PROTOTYPE (throwaway, issue 15): lengthen nets to a common length with ARC serpentines (RTE-7).

    D:\\KiCad\\bin\\python.exe meander.py <src variant dir> <dst variant dir>
            [--amp 0.5] [--r 0.25] [--mode single|double] [--where middle|mcu|sdram] [--trim last|even]
            [--goal equal|window] [--end 0.35] [--clr 0.2] [--area-gap 0.127]
            [--nets /FMC_] [--ref /FMC_SDCLK] [--target <mm>]
    D:\\KiCad\\bin\\python.exe meander.py --window-only <variant dir>     (only writes the length window rule)

The source board is copied to <dst>, every net whose name starts with --nets is lengthened to the
target (default: the longest natural length in the group, as measured by KiCad's DRC through
len_table.probe), and the length window rule of issue 14 is appended to <dst>/lentune.kicad_dru.
A serpentine replaces part of a straight segment by straight pieces and PCB_ARCs; every joint is
tangent, there is no 45-degree trapezoid, no piece shorter than 0.1 mm.

Shapes (u along the track, v sideways; r = corner radius, A = amplitude):
  hump(a)    arc 90 out, leg a-2r, arc 90, arc 90, leg a-2r, arc 90 back.  4r of track, gain 2a - 1.717r.
             a is the sideways distance from the original centre line to the centre line at the top
             of the hump (KiCad's tuning tool means the same by "amplitude"); leg spacing is 2r.
  bump(th)   three arcs (th out, 2*th back, th in), th < 90 deg: a hump lower than 2r.  gain 4r(th - sin th).
  chain      humps alternating left / right, the legs run straight through the original line
             (double-sided).  2r of track per hump, gain 2*sum(a) - 0.858r*(n+1).
Hitting the target exactly:
  single-sided  --trim last (default): full humps at A, then one trimmed element: a lower hump, or a
                bump (two when the rest falls between a bump and the lowest hump with legs).
                --trim even: the smallest number of humps, all lowered to the same height.
  double-sided  one chain of equal humps: the largest count that does not overshoot, all raised evenly above A
                (issue 12 says "amplitude 0.5 and up"). If that does not fit: one hump more, the first and
                last at A and the inner ones lowered evenly. A need below about 1.64 mm (A = 0.5: three humps 0.5, 0.25, 0.5)
                cannot be a chain and is drawn single-sided.
Goal: --goal equal (default) brings every net to the longest natural length. --goal window only touches
the reference net (the clock): it is brought to the middle of the other nets' natural range, which puts
every net inside the +-2.5 mm window of issue 12 with the fewest serpentines.
Placement, all hard limits (nothing is drawn that breaks one; what does not fit is reported as "missing"):
only on segments at the outside width (0.1016) and on straights of at least 2.5 mm;
--area-gap  copper to a rule-area edge, default 0.127 (one outside clearance; the review found 0.025);
--clr       copper to every other copper on the layer (tracks, arcs, vias, pads) and to the net's own other
            tracks, default 0.19 (1.5 x the rule value 0.127; the review found 0.141 next to a neighbour);
--end       straight left between a bend and the first arc, default 0.35 (design-rules.md calls a segment
            shorter than that with 90 degrees of turning around it "sharp"; the review found 0.1);
0.254 mm to the board edge.
A leftover so small that raising the full humps by at most 0.05 mm absorbs it is absorbed that way
(no extra dimple); the same raise is tried when the exact shape does not fit. If the whole length does not fit, the largest part that fits is drawn (humps at A, or lower in
0.05 steps when A itself has no room) and the rest is reported as "missing".
Coordinates are local mm (board file mm - 100).
"""
import argparse, heapq, json, math, os, shutil, sys
import pcbnew
import len_table

NAME = "lentune"
CLR, EDGE, AREA_GAP, END, STEP, SAMPLE, MINSEG, W_OUT = 0.19, 0.254, 0.127, 0.35, 0.05, 0.02, 0.1, 0.1016   # CLR, AREA_GAP, END: see --clr, --area-gap, --end
MIN_RUN = 2.5                                              # no serpentine on a straight shorter than this (short stubs next to a bend look crammed)
STRETCH = 0.05                                              # humps may exceed A by this much when that alone closes the gap
Q = math.pi / 2
COMPASS = ["东", "东南", "南", "西南", "西", "西北", "北", "东北"]
mm = pcbnew.ToMM
Lp = lambda v: (mm(v.x) - 100, mm(v.y) - 100)
P = lambda p: pcbnew.VECTOR2I(int(round((p[0] + 100) * 1e6)), int(round((p[1] + 100) * 1e6)))
LNUM = {pcbnew.F_Cu: "L1", pcbnew.In3_Cu: "L4"}


# ---------------------------------------------------------------- shapes
class Turtle:
    def __init__(self):
        self.p, self.h, self.prims, self.len = (0.0, 0.0), 0.0, [], 0.0

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
    if el[0] == "hump":
        a = el[1]
        T.arc(r, Q * sd); T.fwd(a - 2 * r); T.arc(r, -Q * sd); T.arc(r, -Q * sd); T.fwd(a - 2 * r); T.arc(r, Q * sd)
    elif el[0] == "bump":
        rb, th = el[1], el[2]
        T.arc(rb, th * sd); T.arc(rb, -2 * th * sd); T.arc(rb, th * sd)
    else:                                                   # chain
        amps = el[1]
        T.arc(r, Q * sd); T.fwd(amps[0] - 2 * r)
        for i, a in enumerate(amps):
            T.arc(r, -Q * sd); T.arc(r, -Q * sd)
            if i < len(amps) - 1:
                T.fwd(a + amps[i + 1] - 2 * r); sd = -sd
            else:
                T.fwd(a - 2 * r); T.arc(r, Q * sd)


def measure(el, r):
    """(track used along the original line, length gained) of one element."""
    T = Turtle(); emit(T, el, 1, r)
    assert abs(T.p[1]) < 1e-9 and abs(math.sin(T.h)) < 1e-9, "element does not come back tangent"
    return T.p[0], T.len - T.p[0]


def bisect(f, lo, hi):
    for _ in range(80):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if f(m) < 0 else (lo, m)
    return (lo + hi) / 2


def bump(g, r):
    th = bisect(lambda t: 4 * r * (t - math.sin(t)) - g, 1e-6, Q)
    if r * th >= MINSEG:
        return ("bump", r, th)
    th = bisect(lambda t: 4 * MINSEG * (1 - math.sin(t) / t) - g, 1e-6, Q)      # keep every arc 0.1 mm long: larger radius
    return ("bump", MINSEG / th, th)


def trim_elems(rem, amax, r):
    """Elements that add exactly `rem`, none higher than amax, no piece shorter than 0.1 mm."""
    gmin = (2 * math.pi - 4) * r                              # hump of amplitude 2r (no legs)
    if rem < 5e-4:
        return []
    if rem <= gmin + 1e-9:
        return [bump(rem, r)]
    a = (rem + (8 - 2 * math.pi) * r) / 2
    if rem >= gmin + 2 * MINSEG and a <= amax + 1e-9:
        return [("hump", a)]
    if rem <= 2 * gmin:
        return [bump(rem / 2, r), bump(rem / 2, r)]
    return [("hump", 2 * r)] + trim_elems(rem - gmin, amax, r)


def plans(rem, A, r, mode, trim="last"):
    """Candidate element lists for ONE straight run, best first: the exact ones, then partial ones by falling gain."""
    c = (4 - math.pi) * r
    gfull = lambda a: 2 * a - 2 * c                         # one single-sided hump of amplitude a
    gain_chain = lambda n, a=A: 2 * n * a - c * (n + 1)
    out = []
    n = 1
    while gain_chain(n) < rem - 1e-9:
        n += 1
    if mode == "double" and n >= 3:
        for m in range(n, 1, -1):                           # equal humps, raised evenly: the largest count whose end legs
            a_eq = (rem + c * (m + 1)) / (2 * m)            # (a - 2r) are either absent or at least 0.1 mm long (min_segment)
            if a_eq >= A - 1e-9 and a_eq <= 2 * A + 1e-9 and (abs(a_eq - 2 * r) < 1e-6 or a_eq - 2 * r >= MINSEG):
                out.append([("chain", [max(a_eq, 2 * r)] * m)]); break
        for m in (n, n + 1, n + 2):                         # one hump more: ends at A, inner ones lowered evenly
            d = (gain_chain(m) - rem) / (2 * (m - 2))
            if A - d + A - 2 * r >= MINSEG - 1e-9 and A - d >= r:
                out.append([("chain", [A] + [A - d] * (m - 2) + [A])]); break
    k = int((rem + 1e-9) / gfull(A))
    if trim == "even" and mode != "double":                 # all elements the same height (humps, or bumps when low)
        gmin, N = (2 * math.pi - 4) * r, max(1, math.ceil(rem / gfull(A) - 1e-9))
        for N in range(N, N + 6):
            g = rem / N
            if g <= gmin + 1e-9:
                out.append([bump(g, r)] * N); break
            if g >= gmin + 2 * MINSEG:
                out.append([("hump", (g + 2 * c) / 2)] * N); break
    else:                                                   # also what a double-sided request falls back to
        up = (rem - k * gfull(A)) / (2 * k) if k else 1e9
        if 1e-9 < up <= STRETCH:                            # a small leftover: raise the humps a little instead of adding a
            out.append([("hump", A + up)] * k)              # dimple (a 0.07 mm bump showed up in the first rebuild)
        out.append([("hump", A)] * k + trim_elems(rem - k * gfull(A), A, r))
    for j in range(k, 0, -1):
        up = (rem - j * gfull(A)) / (2 * j)
        if up <= STRETCH and A + up - 2 * r >= MINSEG:
            out.append([("hump", A + up)] * j)
    # partial: the largest gain that fits, humps at A or lower in 0.05 steps (never below 2r)
    part = []
    amps = [A - 0.05 * i for i in range(int(round((A - 2 * r) / 0.05)) + 1)]
    amps = [a for a in amps if abs(a - 2 * r) < 1e-9 or a - 2 * r >= MINSEG - 1e-9]
    for a in amps:
        for j in range(1, 9):
            if gfull(a) * j <= rem + 1e-9:
                part.append((gfull(a) * j, 1, a, [("hump", a)] * j))
            if mode == "double" and j >= 2 and gain_chain(j, a) <= rem + 1e-9:
                part.append((gain_chain(j, a), 2, a, [("chain", [a] * j)]))
    out += [els for _, _, _, els in sorted(part, key=lambda t: (-t[0], -t[1], -t[2]))]
    return out


# ---------------------------------------------------------------- board
class Scene:
    def __init__(self, B):
        self.B = B
        self.areas = []
        for z in B.Zones():
            if z.GetIsRuleArea():
                bb = z.GetBoundingBox()
                self.areas.append(Lp(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop())) + Lp(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom())))
        eb = B.GetBoardEdgesBoundingBox()
        self.edge = Lp(pcbnew.VECTOR2I(eb.GetLeft(), eb.GetTop())) + Lp(pcbnew.VECTOR2I(eb.GetRight(), eb.GetBottom()))
        self.pads = []
        for fp in B.GetFootprints():
            for p in fp.Pads():
                self.pads.append((p.GetNetname(), Lp(p.GetPosition()), max(mm(p.GetSizeX()), mm(p.GetSizeY())) / 2, fp.GetReference()))
        self.rescan()

    def rescan(self):
        self.lines, self.rounds, self.items = [], [], []    # lines: (net, layer, a, c, half width, track object)
        for t in self.B.GetTracks():
            n = t.GetNetname()
            if t.Type() == pcbnew.PCB_VIA_T:
                self.rounds.append((n, None, Lp(t.GetPosition()), mm(t.GetWidth(pcbnew.F_Cu)) / 2))
            elif t.Type() == pcbnew.PCB_ARC_T:
                pts = arc_poly(t)
                for a, c in zip(pts, pts[1:]):
                    self.lines.append((n, t.GetLayer(), a, c, mm(t.GetWidth()) / 2, None))
            else:
                self.lines.append((n, t.GetLayer(), Lp(t.GetStart()), Lp(t.GetEnd()), mm(t.GetWidth()) / 2, t))
            if t.Type() != pcbnew.PCB_VIA_T:
                self.items.append(t)
        for n, c, rad, _ in self.pads:
            self.rounds.append((n, pcbnew.F_Cu, c, rad))

    def path_pos(self, net):
        """{node: distance along the copper from the net's U1 pad}, and the distance of the U2 pad."""
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


def arc_poly(t, step=0.03):
    (x0, y0), (xm, ym), (x1, y1) = Lp(t.GetStart()), Lp(t.GetMid()), Lp(t.GetEnd())
    cx, cy = Lp(t.GetCenter()); r = math.hypot(x0 - cx, y0 - cy)
    a0, am, a1 = (math.atan2(y - cy, x - cx) for x, y in ((x0, y0), (xm, ym), (x1, y1)))
    d = (a1 - a0) % (2 * math.pi)
    if (am - a0) % (2 * math.pi) > d:
        d -= 2 * math.pi
    n = max(3, int(abs(d) * r / step))
    return [(cx + r * math.cos(a0 + d * i / n), cy + r * math.sin(a0 + d * i / n)) for i in range(n + 1)]


def d_seg(p, a, c):
    vx, vy = c[0] - a[0], c[1] - a[1]
    L2 = vx * vx + vy * vy
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L2))
    return math.hypot(p[0] - a[0] - t * vx, p[1] - a[1] - t * vy)


class Run:
    """One straight segment of the net that may carry a serpentine; a = the end nearer the MCU."""
    def __init__(self, sc, net, t, pos, node, A, r):
        self.sc, self.net, self.t, self.r = sc, net, t, r
        a, c = Lp(t.GetStart()), Lp(t.GetEnd())
        self.flip = pos.get(node(a), 0) > pos.get(node(c), 0)
        self.a, self.c = (c, a) if self.flip else (a, c)
        self.L = math.dist(a, c); self.w = mm(t.GetWidth()); self.layer = t.GetLayer()
        self.U = ((self.c[0] - self.a[0]) / self.L, (self.c[1] - self.a[1]) / self.L)
        self.N = (-self.U[1], self.U[0])
        self.pos = min(pos.get(node(a), 0), pos.get(node(c), 0))
        reach = max(A, 2 * r) + 1.0
        x0, x1 = min(a[0], c[0]) - reach, max(a[0], c[0]) + reach
        y0, y1 = min(a[1], c[1]) - reach, max(a[1], c[1]) + reach
        box = lambda p: x0 <= p[0] <= x1 and y0 <= p[1] <= y1
        self.near_lines = [(n == net, a2, c2, hw) for n, l, a2, c2, hw, obj in sc.lines
                           if l == self.layer and obj is not t and (box(a2) or box(c2) or d_seg(((x0 + x1) / 2, (y0 + y1) / 2), a2, c2) < reach * 3)]
        self.near_rounds = [(c2, rad) for n, l, c2, rad in sc.rounds if n != net and l in (None, self.layer) and box(c2)]
        self.memo = {}

    def world(self, u, v):
        return (self.a[0] + u * self.U[0] + v * self.N[0], self.a[1] + u * self.U[1] + v * self.N[1])

    def side_name(self, sd):
        return COMPASS[int(round(math.degrees(math.atan2(self.N[1] * sd, self.N[0] * sd)) / 45)) % 8]

    def ok(self, el, sd, off):
        key = (json.dumps(el), sd, round(off, 4))
        if key not in self.memo:
            self.memo[key] = self._ok(el, sd, off)
        return self.memo[key]

    def _ok(self, el, sd, off):
        T = Turtle(); emit(T, el, sd, self.r)
        hw, e, r = self.w / 2, self.sc.edge, self.r
        for pr in T.prims:
            if pr[0] == "seg":
                if math.dist(pr[1], pr[2]) < MINSEG - 1e-6:   # never draw a piece DRC's min_segment would flag
                    return False
                n = max(1, int(math.dist(pr[1], pr[2]) / SAMPLE))
                pts = [(pr[1][0] + (pr[2][0] - pr[1][0]) * i / n, pr[1][1] + (pr[2][1] - pr[1][1]) * i / n) for i in range(n + 1)]
            else:
                _, _, _, _, c, rr, a0, ang = pr
                n = max(2, int(rr * abs(ang) / SAMPLE))
                pts = [(c[0] + rr * math.cos(a0 + ang * i / n), c[1] + rr * math.sin(a0 + ang * i / n)) for i in range(n + 1)]
            for u, v in pts:
                q = self.world(off + u, v)
                if not (e[0] + EDGE + hw <= q[0] <= e[2] - EDGE - hw and e[1] + EDGE + hw <= q[1] <= e[3] - EDGE - hw):
                    return False
                for x0, y0, x1, y1 in self.sc.areas:
                    g = hw + AREA_GAP
                    if x0 - g < q[0] < x1 + g and y0 - g < q[1] < y1 + g:
                        return False
                for same, a2, c2, hw2 in self.near_lines:
                    if same and abs(v) < r - 1e-6:           # still on (or hugging) the original line
                        continue
                    if d_seg(q, a2, c2) < hw + hw2 + CLR + 0.002:
                        return False
                for c2, rad in self.near_rounds:
                    if math.dist(q, c2) < hw + rad + CLR + 0.002:
                        return False
        return True

    def search(self, els, sd, where):
        """Offset from the MCU end at which the block fits on side sd, or None."""
        bases = [measure(el, self.r)[0] for el in els]
        Lb = sum(bases)
        key = {"mcu": lambda o: o, "sdram": lambda o: -o, "middle": lambda o: abs(o + Lb / 2 - self.L / 2)}[where]
        for end in (END,):                                  # straight kept between a bend and the first arc: a hard limit
            last = self.L - end - Lb
            if last < end - 1e-9:
                continue
            cand = [end + k * STEP for k in range(int((last - end) / STEP + 1e-9) + 1)] + [last]
            for o in sorted(set(cand), key=key):
                x, good = o, True
                for el, b in zip(els, bases):
                    if not self.ok(el, sd, x):
                        good = False; break
                    x += b
                if good:
                    return o, key(o)
        return None

    def commit(self, els, sd, off):
        """Replace the segment by lead + serpentine + tail. Returns the length gained (analytic)."""
        B, t = self.sc.B, self.t
        T = Turtle(); T.p = (off, 0.0)
        for el in els:
            emit(T, el, sd, self.r)
        end_u = T.p[0]
        pa, pc = (t.GetEnd(), t.GetStart()) if self.flip else (t.GetStart(), t.GetEnd())
        net, layer, w = t.GetNet(), t.GetLayer(), t.GetWidth()
        B.Remove(t)

        def seg(p, q):
            s = pcbnew.PCB_TRACK(B); s.SetStart(p); s.SetEnd(q); s.SetWidth(w); s.SetLayer(layer); s.SetNet(net); B.Add(s)

        W = lambda p: P(self.world(p[0], p[1]))
        seg(pa, W((off, 0.0)))
        for pr in T.prims:
            if pr[0] == "seg":
                seg(W(pr[1]), W(pr[2]))
            else:
                a = pcbnew.PCB_ARC(B); a.SetStart(W(pr[1])); a.SetMid(W(pr[2])); a.SetEnd(W(pr[3]))
                a.SetWidth(w); a.SetLayer(layer); a.SetNet(net); B.Add(a)
        seg(W((end_u, 0.0)), pc)
        return T.len - (end_u - off), self.world(off, 0), self.world(end_u, 0)


def describe(els, r):
    humps, bumps, amps = 0, 0, []
    for el in els:
        if el[0] == "hump":
            humps += 1; amps.append(el[1])
        elif el[0] == "bump":
            bumps += 1; amps.append(2 * el[1] * (1 - math.cos(el[2])))
        else:
            humps += len(el[1]); amps += el[1]
    return humps, bumps, [round(a, 3) for a in amps]


def tune_net(sc, net, need, A, r, mode, where, trim):
    blocks, rem, used = [], need, set()
    while rem > 5e-3:                                       # a leftover of a few um is not worth a shape (it shows in the error column)
        sc.rescan()
        pos, total, node = sc.path_pos(net)
        runs = [Run(sc, net, t, pos, node, A, r) for t in sc.items
                if t.GetNetname() == net and t.Type() != pcbnew.PCB_ARC_T and mm(t.GetWidth()) >= W_OUT - 1e-6
                and t.GetLayer() in LNUM and mm(t.GetLength()) >= MIN_RUN]
        runs = [R for R in runs if (round(R.a[0], 3), round(R.a[1], 3), round(R.U[0], 3), round(R.U[1], 3)) not in used]
        order = {"mcu": lambda R: R.pos, "sdram": lambda R: -R.pos, "middle": lambda R: abs(R.pos + R.L / 2 - total / 2)}[where]
        runs.sort(key=order)
        done = False
        for els in plans(rem, A, r, mode, trim):
            for R in runs:
                best = None
                for sd in (1, -1):
                    hit = R.search(els, sd, where)
                    if hit and (best is None or hit[1] < best[1] - 1e-9):
                        best = (hit[0], hit[1], sd)
                if best:
                    off, _, sd = best
                    gain, p0, p1 = R.commit(els, sd, off)
                    humps, bumps, amps = describe(els, r)
                    for q in (R.a, R.c):                    # both leftovers of this segment are closed for more humps
                        used.add((round(q[0], 3), round(q[1], 3), round(R.U[0], 3), round(R.U[1], 3)))
                    used.add((round(p1[0], 3), round(p1[1], 3), round(R.U[0], 3), round(R.U[1], 3)))
                    blocks.append({"layer": LNUM[R.layer], "side": "两" if els[0][0] == "chain" else R.side_name(sd),
                                   "from": [round(v, 3) for v in p0], "to": [round(v, 3) for v in p1], "gain": round(gain, 5),
                                   "humps": humps, "bumps": bumps, "amps": amps, "run_length": round(R.L, 3)})
                    rem -= gain; done = True
                    break
            if done:
                break
        if not done:
            break
    return blocks, (rem if rem > 5e-3 else 0.0)


WINDOW = """
# --- generated by meander.py (issue 14): every /FMC_* net within +-2.5 mm of %s, L = %.4f mm ---
# It comes after sdram_len_max and replaces it for these nets (a later length rule wins); max is far below 60 mm.
(rule "sdram_window"
  (condition "A.NetName == '/FMC_*'")
  (constraint length (min %.4fmm) (opt %.4fmm) (max %.4fmm)))
"""


def write_window(vdir, ref, L):
    p = os.path.join(vdir, NAME + ".kicad_dru")
    text = open(p, encoding="utf-8").read().split("\n# --- generated by meander.py")[0].rstrip("\n") + "\n"
    open(p, "w", encoding="utf-8").write(text + WINDOW % (ref, L, L - 2.5, L, L + 2.5))


def main():
    global END, CLR, AREA_GAP
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst", nargs="?")
    ap.add_argument("--amp", type=float, default=0.5); ap.add_argument("--r", type=float, default=0.25)
    ap.add_argument("--mode", default="single", choices=("single", "double"))
    ap.add_argument("--where", default="middle", choices=("middle", "mcu", "sdram"))
    ap.add_argument("--trim", default="last", choices=("last", "even"))
    ap.add_argument("--nets", default="/FMC_"); ap.add_argument("--ref", default="/FMC_SDCLK")
    ap.add_argument("--target", type=float); ap.add_argument("--window-only", action="store_true")
    ap.add_argument("--goal", default="equal", choices=("equal", "window")); ap.add_argument("--tol", type=float, default=2.5)
    ap.add_argument("--end", type=float, default=END); ap.add_argument("--clr", type=float, default=CLR)
    ap.add_argument("--area-gap", type=float, default=AREA_GAP)
    a = ap.parse_args()
    END, CLR, AREA_GAP = a.end, a.clr, a.area_gap
    sys.stdout.reconfigure(encoding="utf-8")
    for d in (a.src, a.dst):
        if d and os.path.isdir(d) and any(f.startswith("~") and f.endswith(".lck") for f in os.listdir(d)):
            raise SystemExit("KiCad has %s open (~*.lck found): close it first, nothing was written" % d)
    nat = {n: v for n, v in len_table.lengths(a.src).items() if n.startswith(a.nets)}
    if not nat:
        raise SystemExit("no net matched %s*: nothing to tune" % a.nets)
    if a.window_only:
        write_window(a.src, a.ref, nat[a.ref]); print("window rule written, L = %.4f" % nat[a.ref]); return
    assert 2 * a.r >= W_OUT + 0.127, "leg spacing 2r is below width + clearance"
    assert a.amp >= 2 * a.r, "amplitude below 2r"
    os.makedirs(a.dst, exist_ok=True)
    for ext in ("kicad_pcb", "kicad_pro", "kicad_dru"):
        shutil.copy(os.path.join(a.src, NAME + "." + ext), os.path.join(a.dst, NAME + "." + ext))
    pcb = os.path.join(a.dst, NAME + ".kicad_pcb")
    B = pcbnew.LoadBoard(pcb)
    sc = Scene(B)
    target = a.target or max(nat.values())
    goals = {n: target for n in nat}
    if a.goal == "window":                                  # only the reference net moves: to the middle of the others' range
        others = [v for n, v in nat.items() if n != a.ref]
        inside = max(others) - a.tol <= nat[a.ref] <= min(others) + a.tol
        target = nat[a.ref] if inside else max(nat[a.ref], (max(others) + min(others)) / 2)
        goals = dict(nat); goals[a.ref] = target
    res = {"src": os.path.relpath(a.src, os.path.dirname(os.path.abspath(__file__))).replace("\\", "/"),
           "amp": a.amp, "r": a.r, "mode": a.mode, "where": a.where, "trim": a.trim, "ref": a.ref, "target": round(target, 4),
           "goal": a.goal, "end": END, "clr": CLR, "area_gap": AREA_GAP,
           "leg_spacing": 2 * a.r, "nets": {}}
    for net in sorted(nat, key=lambda n: -(goals[n] - nat[n])):   # the neediest net picks its room first
        need = goals[net] - nat[net]
        blocks, missing = tune_net(sc, net, need, a.amp, a.r, a.mode, a.where, a.trim) if need > 5e-4 else ([], 0.0)
        added = sum(b["gain"] for b in blocks)
        res["nets"][net] = {"natural": nat[net], "goal_len": round(goals[net], 4), "need": round(need, 4), "added": round(added, 5), "missing": round(missing, 4),
                            "predicted": round(nat[net] + added, 4), "blocks": blocks}
        print("%-11s natural %.3f  need %.3f  added %.3f  missing %.3f  %s" % (
            net, nat[net], need, added, missing,
            "; ".join("%s %s侧 %d弯%s" % (b["layer"], b["side"], b["humps"], "+%d小弯" % b["bumps"] if b["bumps"] else "") for b in blocks)))
    pcbnew.SaveBoard(pcb, B)
    write_window(a.dst, a.ref, res["nets"][a.ref]["predicted"])
    res["window_L"] = res["nets"][a.ref]["predicted"]
    json.dump(res, open(os.path.join(a.dst, "tune.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
