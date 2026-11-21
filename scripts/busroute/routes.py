"""The routes format, and how a route becomes board copper.

A route is, per net, a list of pieces from one pad to another:

    ROUTES = {"FMC_D10": [("L1", ["U201.N11", (15.275, 15.575)]),      # a track piece: layer, points
                          ("via", (15.275, 15.575)),                    # or ("via", (x, y), (diameter, drill))
                          ("L4", [(15.275, 15.575), (19.1, 15.575), (22.225, 18.7)]), ...]}

Points are local mm on the 0.1 um grid; a string is a pad: "REF.PAD", or "REF" = the net's only pad on
that part. Each piece starts where the one before ended; layers change only at a via; segments are exactly
0/45/90 degrees and corners exactly 45 degrees.

Track width and via size are NOT written (profile C): inside a rule area, and for `extend` (0.3 mm) of
straight beyond its edge, a track is `w_area` (0.09); elsewhere it has its net class width. The cut is on
the straight, never at a bend, and a thin piece always touches the area itself (a 0.09 piece that does not
is a DRC width error). A via is small (0.30 / 0.15) only when all of it is inside a rule area.
"""
import math
from .geom import RouteError, ipt, dir_of, turn, shape_errors, sharp_errors, clip, in_rect, R2


def F(kind, text, net=None, at=None, **kw):
    """A finding. kind decides whether it stops a build (see checks.HARD)."""
    d = {"kind": kind, "net": net, "text": text, "at": [round(at[0], 4), round(at[1], 4)] if at else None}
    d.update(kw)
    return d


def resolve(board, profile, routes, open_ok=False):
    """-> ({net: [piece]}, findings). piece = ("L1", [(x, y), ...]) | ("via", (x, y), size or None).
    Raises RouteError for what cannot be read at all (unknown pad, unknown layer, off-grid coordinate)."""
    out, finds = {}, []
    for net, pieces in routes.items():
        if net not in board.nets:
            raise RouteError("%s: no such net on the board" % net)
        res, where, layer, ends = [], None, None, []
        for pc in pieces:
            if pc[0] == "via":
                xy = (float(pc[1][0]), float(pc[1][1])); ipt(xy)
                if where is None or math.dist(where, xy) > 1e-7:
                    finds.append(F("PATH", "via at %s is not at the end of the piece before it (%s)" % (xy, where), net, xy))
                res.append(("via", xy, tuple(pc[2]) if len(pc) > 2 and pc[2] else None))
                layer = None
                continue
            lay = pc[0]
            if lay not in board.cu:
                raise RouteError("%s: unknown layer %r (the board has %s)" % (net, lay, " ".join(board.layers)))
            pts = []
            for k, p in enumerate(pc[1]):
                if isinstance(p, str):
                    try:
                        pad = board.pad(p, net)
                    except KeyError as e:
                        raise RouteError("%s: %s" % (net, e.args[0]))
                    if pad.net != net:
                        finds.append(F("PATH", "%s is a pad of net %s" % (pad.name, pad.net or "(none)"), net, pad.pos))
                    if pad.layers is not None and lay not in pad.layers:
                        finds.append(F("PATH", "pad %s is not on %s" % (pad.name, lay), net, pad.pos))
                    ends.append((pad.name, len(res), k))
                    p = pad.pos
                pts.append((float(p[0]), float(p[1])))
            ip = [ipt(p) for p in pts]
            if where is not None and math.dist(where, pts[0]) > 1e-7:
                finds.append(F("PATH", "piece on %s starts at %s but the net was at %s" % (lay, pts[0], where), net, pts[0], layer=lay))
            if layer is not None:
                finds.append(F("PATH", "two track pieces in a row without a via (%s then %s)" % (layer, lay), net, pts[0]))
            for kind, text, at in shape_errors(ip, profile.min_seg) + sharp_errors(ip, profile.chamfer):
                finds.append(F(kind, text, net, at, layer=lay))
            res.append((lay, pts))
            where, layer = pts[-1], lay
        tr = [p for p in res if p[0] != "via"]
        if not tr:
            raise RouteError("%s: the route has no track piece" % net)
        for k, pc in enumerate(res):                        # change of direction across a via (RTE-11)
            if pc[0] == "via" and 0 < k < len(res) - 1 and res[k - 1][0] != "via" and res[k + 1][0] != "via":
                d1 = dir_of(ipt(res[k - 1][1][-2]), ipt(res[k - 1][1][-1])) if len(res[k - 1][1]) > 1 else None
                d2 = dir_of(ipt(res[k + 1][1][0]), ipt(res[k + 1][1][1])) if len(res[k + 1][1]) > 1 else None
                if d1 and d2 and turn(d1, d2) >= 2:
                    finds.append(F("VIATURN", "the track turns %d degrees across the via at %s" % (45 * turn(d1, d2), pc[1]), net, pc[1]))
        first, last = tr[0][1][0], tr[-1][1][-1]
        pads = board.net_pads(net)
        at_pad = lambda p: [q.name for q in pads if math.dist(q.pos, p) < 1e-7]
        a, b = at_pad(first), at_pad(last)
        kind = "OPEN" if open_ok else "PATH"
        if not a:
            finds.append(F(kind, "the route does not start on a pad of the net (starts at %s)" % (first,), net, first))
        if not b:
            finds.append(F(kind, "the route does not end on a pad of the net (ends at %s)" % (last,), net, last))
        if a and b and a == b:
            finds.append(F("PATH", "the route starts and ends on the same pad %s" % a[0], net, first))
        if len(pads) > 2 and not open_ok:
            finds.append(F("PATH", "the net has %d pads, a route joins two of them" % len(pads), net, first))
        out[net] = res
    return out, finds


def split_widths(pts, areas, w_in, w_out, extend, min_seg):
    """[(a, c, width)] for one layer piece: thin inside the rule areas and `extend` of track beyond them."""
    out = []
    if w_in >= w_out - 1e-9:
        return [(a, c, w_out) for a, c in zip(pts, pts[1:])]
    for a, c in zip(pts, pts[1:]):
        L = math.dist(a, c)
        thin = []
        for R in areas.values():
            iv = clip(a, c, R)
            if iv:
                thin.append([max(0.0, iv[0] * L - extend), min(L, iv[1] * L + extend)])
        thin.sort()
        merged = []
        for iv in thin:
            if merged and iv[0] <= merged[-1][1] + min_seg + 1e-9:   # a wide gap under min_seg is not worth two width changes
                merged[-1][1] = max(merged[-1][1], iv[1])
            else:
                merged.append(iv)
        cuts = []
        for iv in merged:                                   # a cut closer than min_seg to a route point moves onto it
            s0 = 0.0 if iv[0] < min_seg + 1e-6 else iv[0]
            s1 = L if L - iv[1] < min_seg + 1e-6 else iv[1]
            cuts.append((s0, s1))
        ux, uy = (c[0] - a[0]) / L, (c[1] - a[1]) / L
        k = R2 if abs(ux) > 1e-9 and abs(uy) > 1e-9 else 1.0

        def at(s):                                          # the point at arclength s, on a 1 um grid and exactly on the line
            if s <= 0.0:
                return a
            if s >= L:
                return c
            st = round(s / k * 1000) / 1000
            sx = (ux > 1e-9) - (ux < -1e-9)
            sy = (uy > 1e-9) - (uy < -1e-9)
            return (round(a[0] + sx * st, 6), round(a[1] + sy * st, 6))
        pos = 0.0
        for s0, s1 in cuts:
            if s0 > pos:
                out.append((at(pos), at(s0), w_out))
            out.append((at(s0), at(s1), w_in))
            pos = s1
        if pos < L:
            out.append((at(pos), c, w_out))
    return out


def via_size(profile, areas, net, p):
    r = profile.via_area[0] / 2
    if any(in_rect(p, R, -r) for R in areas.values()):
        return tuple(profile.via_area)
    return tuple(profile.via_out(net))


def expand(board, profile, resolved, extras=()):
    """-> (segs [(net, layer, a, c, width)], vias [(net, p, diameter, drill, owned)]) in a fixed order."""
    areas = board.rule_areas(profile.area_names)
    segs, vias = [], []
    for net in sorted(resolved):
        for pc in resolved[net]:
            if pc[0] == "via":
                d, h = pc[2] or via_size(profile, areas, net, pc[1])
                vias.append((net, pc[1], d, h, True))
            else:
                segs += [(net, pc[0], a, c, w) for a, c, w in split_widths(pc[1], areas, profile.w_area, profile.width(net), profile.extend, profile.min_seg)]
    for net, p in extras:
        d, h = via_size(profile, areas, net, p)
        vias.append((net, (float(p[0]), float(p[1])), d, h, False))
    return segs, vias


def lengths(board, resolved):
    """{net: {"length", "track", "via_mm", "vias", "layers": {L: mm}, "direct", "ends"}} by geometry: track centre
    lines plus, for every via, the height between the layers of the pieces before and after it (KiCad's rule;
    a via that does not change layer adds nothing but is counted)."""
    out = {}
    for net, pieces in resolved.items():
        lay, vias, vmm, prev = {}, 0, 0.0, None
        for pc in pieces:
            if pc[0] == "via":
                vias += 1
                continue
            lay[pc[0]] = lay.get(pc[0], 0.0) + sum(math.dist(a, c) for a, c in zip(pc[1], pc[1][1:]))
            if prev and prev != pc[0]:
                vmm += board.via_height(prev, pc[0])
            prev = pc[0]
        tr = [p for p in pieces if p[0] != "via"]
        a, c = tr[0][1][0], tr[-1][1][-1]
        dx, dy = abs(a[0] - c[0]), abs(a[1] - c[1])
        t = sum(lay.values())
        out[net] = {"length": round(t + vmm, 4), "track": round(t, 4), "via_mm": round(vmm, 4), "vias": vias,
                    "layers": {k: round(v, 4) for k, v in sorted(lay.items())},
                    "direct": round(max(dx, dy) - min(dx, dy) + min(dx, dy) * R2, 4), "ends": [list(a), list(c)]}
    return out
