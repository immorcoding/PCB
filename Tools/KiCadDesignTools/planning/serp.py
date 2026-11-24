"""Serpentine geometry for length plans, and the block rules a planned block must keep.

    points(p0, p1, side, n, amp, pitch, start)  the polyline of a straight p0 -> p1 carrying a one-sided block of n
                                                humps of height amp towards side "L" / "R" (of the travel, y down)
    added(n, amp, pitch)                        what such a block adds: n (2 amp - 0.858 pitch)
    amp_for(need, n, pitch)                     the height that adds `need` with n humps
    block_rules(plan, P)                        per planned block: straight before / after, height window,
                                                axis-parallel, outside the rule areas on the layers that ask it,
                                                the largest height the neighbours allow and the capacity there

The geometry is busroute tune.py's (RTE-2): arcs of radius pitch / 2, a block takes 2 pitch n of straight and adds
n (2a - (4 - pi) p), with 4 - pi written 0.858 as RTE-2 writes it. The limits are the routes file's TUNING
(busroute tune.DEFAULTS where it says nothing): keep (straight at each end of a block), amp .. amp_max (height
window), clr (serpentine copper to other copper), area_gap (to a rule-area edge); and board.toml [plan]
block_free_layers (layers whose blocks stay outside the rule areas).
"""
import math

from Tools.KiCadDesignTools.planning.check import dist, pt_seg, seg_seg, seg_hits_box, in_box

HUMP_LOSS = 0.858          # 4 - pi as RTE-2 writes it: a hump of height a and pitch p adds 2a - 0.858 p
STEP_DEG = 15              # polyline step of the arcs, degrees
HEAD_REACH = 2.6           # neighbours above the hump tops are searched this far
END_SLACK = 0.3            # ... and this far beyond the block's ends along it
RAY = 3.0                  # a rule area counts when it lies within this distance in front of the tops


def points(p0, p1, side, n, amp, pitch, start, step_deg=STEP_DEG):
    """Polyline of a straight p0 -> p1 carrying a one-sided block of n humps of amplitude amp towards `side`
    ('L' or 'R' of the travel direction), the first arc starting `start` mm after p0. Returns (points, added, x_end)
    where x_end is the station where the block ends (start + 2*pitch*n)."""
    L = dist(p0, p1)
    ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
    # left normal in screen coordinates (y down): travelling east (1,0), left = north = (0,-1)
    nx, ny = (uy, -ux) if side == "L" else (-uy, ux)
    r = pitch / 2
    if amp < 2 * r - 1e-9:
        raise ValueError("amplitude %.3f below 2r" % amp)
    need = start + 2 * pitch * n
    if need > L + 1e-9:
        raise ValueError("block of %d humps needs %.3f mm of straight, have %.3f" % (n, need, L))
    loc = [(0.0, 0.0)]

    def arc(cx, cy, a0, a1):
        k = max(2, int(abs(a1 - a0) / step_deg))
        for i in range(1, k + 1):
            a = math.radians(a0 + (a1 - a0) * i / k)
            loc.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    s = start
    for i in range(n):
        loc.append((s, 0.0))
        # local frame: x along travel, y towards the hump side
        arc(s, r, -90, 0)                    # quarter arc turning up, ends at (s + r, r)
        loc.append((s + r, amp - r))
        arc(s + 2 * r, amp - r, 180, 0)      # top semicircle: y = amp - r + r sin(a) >= amp - r
        loc.append((s + 3 * r, r))
        arc(s + 4 * r, r, 180, 270)          # quarter arc back onto the base line, ends at (s + 4r, 0)
        s += 2 * pitch
    loc.append((L, 0.0))
    pts = [(p0[0] + x * ux + y * nx, p0[1] + x * uy + y * ny) for x, y in loc]
    out = [pts[0]]
    for p in pts[1:]:
        if dist(p, out[-1]) > 1e-9:
            out.append(p)
    return out, n * (2 * amp - HUMP_LOSS * pitch), need


def added(n, amp, pitch):
    return n * (2 * amp - HUMP_LOSS * pitch)


def amp_for(need, n, pitch):
    return (need / n + HUMP_LOSS * pitch) / 2


# ----------------------------------------------------------------------------- block rules
def _flatpts(net):
    res = []
    for it in net.items:
        if it[0] == "t":
            for q in it[2]:
                if not res or dist(res[-1][1], q) > 1e-6 or res[-1][0] != it[1]:
                    res.append((it[1], q))
    return res


def _straight_len(pts, i, step):
    """length of the collinear run from pts[i] going in direction step (same layer)."""
    j = i
    while 0 <= j + step < len(pts) and pts[j + step][0] == pts[i][0]:
        a, b, c = pts[i][1], pts[j][1], pts[j + step][1]
        if j != i and abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) > 1e-6:
            break
        j += step
    return dist(pts[i][1], pts[j][1])


def block_rules(nets, P, rules, free_layers=()):
    """One record per block of the planned nets (dict name -> Net; kept nets and nets without blocks skipped):
    zone tag, net, layer, humps, height, what it adds, the largest height the copper beyond the tops allows
    (amp_max: min(TUNING amp_max, amp + room - clr), room = the gap from the tops' line to the nearest other copper
    beyond it, or to a rule area in front of the humps less area_gap), the capacity at that height, the straight
    before / after, axis-parallel, rules_ok."""
    lim = rules.limits
    keep, amin, amax_cap, clr, gap_area = lim["keep"], lim["amp"], lim["amp_max"], lim["clr"], lim["area_gap"]
    out = []
    for name, n in nets.items():
        if n.kept or not n.blocks:
            continue
        pts = _flatpts(n)
        hw = rules.profile.width(name) / 2          # the track outside the rule areas
        for b in n.blocks:
            fa, ta = tuple(b["from"]), tuple(b["to"])
            i0 = min(range(len(pts)), key=lambda i: dist(pts[i][1], fa))
            i1 = max(range(len(pts)), key=lambda i: (dist(pts[i][1], ta) < 2e-3, i))
            before = _straight_len(pts, i0, -1)
            after = _straight_len(pts, i1, +1)
            ux, uy = ta[0] - fa[0], ta[1] - fa[1]
            axis = abs(ux) < 1e-6 or abs(uy) < 1e-6
            Ln = math.hypot(ux, uy)
            ux, uy = ux / Ln, uy / Ln
            nx, ny = (uy, -ux) if b["side"] == "L" else (-uy, ux)
            amp = b["amp"]
            top_a = (fa[0] + nx * amp, fa[1] + ny * amp)
            top_b = (ta[0] + nx * amp, ta[1] + ny * amp)
            gap = 9.9
            who = ""
            for q in P.near(b["layer"], top_a, top_b, HEAD_REACH):
                if q["net"] == name or q["kind"] == "hole":
                    continue
                # only copper lying beyond the tops (on the hump side, farther from the base line than the amplitude)
                mid = ((q["a"][0] + q["b"][0]) / 2, (q["a"][1] + q["b"][1]) / 2)
                off = (mid[0] - fa[0]) * nx + (mid[1] - fa[1]) * ny
                along = (mid[0] - fa[0]) * ux + (mid[1] - fa[1]) * uy
                if off < amp - 0.02 or along < -END_SLACK or along > Ln + END_SLACK:
                    continue
                d = seg_seg(top_a, top_b, q["a"], q["b"]) - q["hw"] - hw
                if d < gap:
                    gap, who = d, q["net"]
            extra = max(0.0, gap - clr)
            for box in rules.areas.values():
                if not in_box(fa, box) and not in_box(ta, box):
                    # distance from the tops to the box, if the humps point at it
                    cx = min(max(top_a[0], box[0]), box[2]), min(max(top_a[1], box[1]), box[3])
                    dbox = min(pt_seg(c, top_a, top_b) for c in [(box[0], box[1]), (box[0], box[3]), (box[2], box[1]), (box[2], box[3])] + [cx])
                    if seg_hits_box(top_a, (top_a[0] + nx * RAY, top_a[1] + ny * RAY), box) or seg_hits_box(top_b, (top_b[0] + nx * RAY, top_b[1] + ny * RAY), box):
                        e2 = max(0.0, dbox - gap_area - hw)
                        if e2 < extra:
                            extra, who = e2, "rule-area edge"
            amax = min(amax_cap, amp + extra)
            cap = b["n"] * (2 * amax - HUMP_LOSS * b["pitch"])
            ok = before >= keep - 1e-3 and after >= keep - 1e-3 and amin - 1e-6 <= amp <= amax_cap + 1e-6 and axis
            if b["layer"] in free_layers and (rules.in_area(fa) or rules.in_area(ta)):
                ok = False
            out.append({"zone": b["tag"], "net": name, "layer": b["layer"], "n": b["n"], "amp": amp, "need": b["adds"], "amp_max": round(amax, 3),
                        "capacity": round(cap, 2), "headroom_amp": round(amax - amp, 3), "limited_by": who if amax < amax_cap else "%.1f mm cap" % amax_cap,
                        "from": b["from"], "to": b["to"], "side": b["side"], "straight_before": round(before, 3), "straight_after": round(after, 3),
                        "axis_parallel": axis, "rules_ok": ok})
    return out
