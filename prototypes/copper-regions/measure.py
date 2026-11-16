"""PROTOTYPE (issue 16): the same numbers for every variant, read from the board KiCad filled.

    D:\\KiCad\\bin\\python.exe measure.py <variant dir>      (needs h7cu.kicad_pcb refilled by kicad-cli, and drc.json)

Writes metrics.json and prints a table. Per zone: outline edges off the 0/45/90 grid, pieces of fill,
pieces nothing feeds, copper of the net the fill does not reach, and the "neck": the widest strip of
copper that still joins everything the fill reaches (found by shrinking the fill until it falls apart).
Per layer: the gap between fills of different nets. From drc.json: violations by type, and what is
left unconnected on the copper-class nets.
"""
import collections, json, math, os, re, sys
import pcbnew
from culib import *

vdir = sys.argv[1]
B = pcbnew.LoadBoard(os.path.join(vdir, "h7cu.kicad_pcb"))


def edge_report(z):
    off, shortest, n = 0, 1e9, 0
    o = z.Outline()
    chains = []
    for i in range(o.OutlineCount()):
        chains.append(o.Outline(i))
        chains += [o.Hole(i, h) for h in range(o.HoleCount(i))]
    for ch in chains:
        pts = chain_pts(ch)
        for k in range(len(pts)):
            (x1, y1), (x2, y2) = pts[k], pts[(k + 1) % len(pts)]
            d = math.hypot(x2 - x1, y2 - y1)
            if d < 1e-6:
                continue
            n += 1; shortest = min(shortest, d)
            a = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 45
            if min(a, 45 - a) > 0.05:
                off += 1
    return n, off, round(shortest, 3)


def group(fill_pieces, anc, w):
    """Shrink the fill by w/2 and say which shrunken piece each anchor still hangs on (None = none)."""
    out = []
    subs = []
    for one in fill_pieces:
        d = pcbnew.SHAPE_POLY_SET(one)
        if w > 0:
            d.Deflate(FromMM(w / 2), ROUND, FromMM(0.01))
        subs += pieces(d)
    for pt, reach, _kind, _label in anc:
        hit = None
        for k, s in enumerate(subs):
            if s.Collide(pt, FromMM(reach + w / 2 + 0.02)):
                hit = k; break
        out.append(hit)
    return out


def neck(fill_pieces, anc):
    """Widest w at which every anchor reached at w = 0 is still on one piece. None if fewer than 2."""
    if len(anc) < 2:
        return None
    def ok(w):
        g = group(fill_pieces, anc, w)
        return len(set(g)) == 1 and None not in g
    if not ok(0.05):
        return 0.0
    lo, hi = 0.05, 6.0
    if ok(hi):
        return hi
    for _ in range(9):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if ok(mid) else (lo, mid)
    return round(lo, 2)


def gap(a, c):
    """Smallest distance between two fills, by growing the one with fewer vertices."""
    if a.TotalVertices() > c.TotalVertices():
        a, c = c, a
    def touch(g):
        t = pcbnew.SHAPE_POLY_SET(a); t.Inflate(FromMM(g), ROUND, ERR); t.BooleanIntersection(c)
        return t.OutlineCount() > 0 and t.Area() > 1e6
    if not touch(5.0):
        return None
    lo, hi = 0.0, 5.0
    for _ in range(12):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if touch(mid) else (mid, hi)
    return round(hi, 3)


rows, fills = [], collections.defaultdict(list)
for z in zones(B):
    lid = z.GetLayer(); net = z.GetNetname()
    fill = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(lid))
    fill.Simplify()        # KiCad stores the fill fractured (holes joined to the outline by slits); shrinking that cuts along the slits
    fp = pieces(fill)
    anc = anchors(B, net, lid)
    where = group(fp, anc, 0)
    reached = [a for a, k in zip(anc, where) if k is not None]
    fed = set(k for k in where if k is not None)
    n, off, shortest = edge_report(z)
    main = collections.Counter(k for k in where if k is not None).most_common(1)
    main_anc = [a for a, k in zip(anc, where) if main and k == main[0][0]]
    main_piece = [fp[main[0][0]]] if main else []
    main_anc = [a for a in main_anc if a[2] != "th"]            # through-hole pads hang on thermal spokes: not the fill's neck
    outside = [a for a in main_anc if not in_bga(*L(a[0]))]
    if net == "GND":                                           # whole-layer ground: pieces and unfed pieces say enough
        main_anc, outside = [], []
    nk, nkx = neck(main_piece, main_anc), neck(main_piece, outside)
    first = []
    if nkx is not None and nkx < 6:                           # which anchors let go just above the neck
        g = group(main_piece, outside, nkx + 0.12)
        big = collections.Counter(k for k in g if k is not None).most_common(1)
        first = [a[3] for a, k in zip(outside, g) if not big or k != big[0][0]][:6]
    rows.append({
        "zone": z.GetZoneName(), "net": net, "layer": LNUM[lid], "prio": z.GetAssignedPriority(),
        "outline_edges": n, "off_angle_edges": off, "shortest_edge": shortest,
        "clearance": round(mm(z.GetLocalClearance() or 0), 3), "min_width": round(mm(z.GetMinThickness()), 3),
        "area": round(fill.Area() / 1e12, 1), "pieces": len(fp), "unfed_pieces": len(fp) - len(fed),
        "anchors_on_main": len(main_anc), "anchors_on_other_pieces": len(reached) - len(main_anc),
        "neck": nk, "neck_outside_bga": nkx, "neck_at": first,
        "_fill": fill})
    fills[lid].append(rows[-1])

# copper of each net that no fill of that net reaches, per layer the net is poured on
unreached = []
for lid, zs in fills.items():
    for net in sorted(set(r["net"] for r in zs)):
        allp = []
        for r in zs:
            if r["net"] == net:
                allp += pieces(r["_fill"])
        if lid in (pcbnew.F_Cu, pcbnew.B_Cu) and net != "GND":
            continue                                           # a local pour serves only the pads under it
        anc = [a for a in anchors(B, net, lid) if a[2] != "smd" or lid in (pcbnew.F_Cu, pcbnew.B_Cu)]
        miss = [a[3] for a, k in zip(anc, group(allp, anc, 0)) if k is None]
        unreached.append({"layer": LNUM[lid], "net": net, "copper": len(anc), "not_reached": len(miss), "which": miss[:40]})

gaps = []
for lid, zs in fills.items():
    for i in range(len(zs)):
        for j in range(i + 1, len(zs)):
            a, c = zs[i], zs[j]
            if a["net"] == c["net"] or a["_fill"].OutlineCount() == 0 or c["_fill"].OutlineCount() == 0:
                continue
            if lid in (pcbnew.F_Cu, pcbnew.B_Cu) and "GND" in (a["net"], c["net"]) and LNUM[lid] != "L1":
                continue
            g = gap(a["_fill"], c["_fill"])
            if g is not None:
                gaps.append({"layer": LNUM[lid], "a": a["net"], "b": c["net"], "gap": g})

drc = {}
p = os.path.join(vdir, "drc.json")
if os.path.exists(p):
    d = json.load(open(p, encoding="utf-8"))
    drc["violations"] = dict(collections.Counter(v["type"] for v in d["violations"]))
    un = collections.Counter()
    for it in d["unconnected_items"]:
        nets = set(re.findall(r"\[([^\]]+)\]", " ".join(i["description"] for i in it["items"])))
        for n in nets & set(COPPER_NETS):
            un[n] += 1
    drc["unconnected_total"] = len(d["unconnected_items"])
    drc["unconnected_copper_nets"] = dict(un)

for r in rows:
    del r["_fill"]
json.dump({"zones": rows, "not_reached": unreached, "gaps": gaps, "drc": drc},
          open(os.path.join(vdir, "metrics.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)

print("%-4s %-8s %-12s %4s %5s %4s %8s %6s %5s %6s %6s %6s  %s" % (
    "lay", "net", "zone", "prio", "edges", "off", "area", "pieces", "unfed", "onmain", "neck", "neckX", "neckX is at"))
for r in sorted(rows, key=lambda r: (r["layer"], -r["area"])):
    print("%-4s %-8s %-12s %4d %5d %4d %8.1f %6d %5d %6d %6s %6s  %s" % (
        r["layer"], r["net"], r["zone"][:12], r["prio"], r["outline_edges"], r["off_angle_edges"], r["area"], r["pieces"],
        r["unfed_pieces"], r["anchors_on_main"], r["neck"], r["neck_outside_bga"], " ".join(r["neck_at"])))
print("copper not reached by its own net's fill:")
for u in unreached:
    print("  %-3s %-8s %3d of %3d  %s" % (u["layer"], u["net"], u["not_reached"], u["copper"], " ".join(u["which"][:8])))
print("gaps:", "  ".join("%s %s|%s %.3f" % (g["layer"], g["a"], g["b"], g["gap"]) for g in gaps))
print("drc:", drc)
