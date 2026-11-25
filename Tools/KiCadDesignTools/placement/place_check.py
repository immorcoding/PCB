"""Placement metrics (LAY-2, LAY-5, LAY-6, LAY-8): what is placed, overlaps, keep-outs, edges, decoupling distances.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.placement.place_check <board> [options] [--json <out.json>]

Options:
  --edge REF=SIDE         connector REF belongs on board side L, R, T or B (repeatable). Its courtyard may
                          cross that side, and the table reports how far its body (F.Fab / B.Fab outline,
                          courtyard when there is none) stands back from the edge (negative = sticks out).
  --hole-keepout MM       radius of the keep-out around each mounting hole centre (default 6). Holes are
                          footprints whose reference starts with --holes (default H) and that have a hole of
                          at least 2.5 mm.
  --allow-under REF,...   bottom parts may sit under the pads of these top parts (agreed BGA decoupling, LAY-5)
  --rail REGEX            nets that count as supply rails for decoupling (default: starts with + or contains
                          VDD or VCAP)
  --ic REGEX              references that are ICs (default ^U)
  --not-supply REF.PIN,.. IC pins on a rail that are not supply inputs (regulator outputs, enables tied to a rail)
  --small NF              capacitors up to this value are the per-pin decoupling (default 100)
  --limit MM              per-pin distance limit for those (required: the rule profile's value, which the board
                          gives in board.toml [layout] decap_limit; the build driver passes it, LAY-2)
  --ground NET            the ground net: a decoupling capacitor has one pad on it (required: board.toml [power]
                          ground; the build driver passes it)
  --silk MM              text height for LAY-8 (default 1.0, the board's silk minimum); a character is taken
                          as 0.9 x this wide. Reported, not enforced (the silk itself is the finishing stage)
  --silk-refs REGEX       parts that need room (default ^(J|TP|JP))
  --origin X Y            subtract this from board coordinates in the report (default 100 100)

What it measures (all from the board file; nothing is written to it):
  parts      placed = courtyard centre inside the board outline; parked = the rest (listed)
  outside    placed parts whose courtyard leaves the outline (edge connectors may cross their own side)
  overlap    courtyard pairs on the same side whose intersection is larger than 0.001 mm2 (a part without a
             courtyard uses its bounding box and is listed as such)
  hole       courtyards closer than --hole-keepout to a mounting hole centre
  keepout    footprint and board rule areas (LAY-6): pads of other parts inside one that forbids pads, and
             courtyards of other parts inside one that forbids footprints; areas that forbid tracks, vias or
             fills are listed so that routing respects them
  edge       per --edge part: body distance to its side, and whether it is on that side at all
  under      bottom pads whose outline overlaps a top pad of another part (LAY-5), except under --allow-under
  decoupling per IC supply pin (pad on a --rail net): distance from the pad centre to the rail pad of the
             nearest capacitor of at most --small nF that has a --ground pad; per capacitor on a rail: distance to
             the nearest IC pin of its rail. Pins on rails that have no small capacitor at all are counted
             separately (bulk-only rails such as VCAP).
  silk       LAY-8, room for labels: a test point (TP*) needs a box for its value (its net name), one text line
             high, beside its courtyard on at least one side, inside the outline and clear of other courtyards;
             a header or connector (J*, JP*) needs --silk of free space to every other courtyard on its side,
             and to the board edge unless it is an --edge part
Exit code 1 when any of outside, overlap, hole, keepout (pads / footprints), under is not zero.
"""
import argparse, json, math, re, sys
import pcbnew
from pcbnew import ToMM

AREA_EPS = 0.001          # mm2


def opts(argv):
    p = argparse.ArgumentParser()
    p.add_argument("board")
    p.add_argument("--edge", action="append", default=[])
    p.add_argument("--hole-keepout", type=float, default=6.0)
    p.add_argument("--holes", default="H")
    p.add_argument("--allow-under", default="")
    p.add_argument("--rail", default=r"^\+|VDD|VCAP")
    p.add_argument("--ic", default=r"^U")
    p.add_argument("--not-supply", default="")
    p.add_argument("--small", type=float, default=100.0)
    p.add_argument("--limit", type=float, required=True)
    p.add_argument("--ground", required=True)
    p.add_argument("--silk", type=float, default=1.0)
    p.add_argument("--silk-refs", default=r"^(J|TP|JP)")
    p.add_argument("--origin", nargs=2, type=float, default=[100.0, 100.0])
    p.add_argument("--json")
    return p.parse_args(argv)


def cap_nf(value):
    """'4.7uF/50V' -> 4700.0, '15pF C0G' -> 0.015; None when the value is not a capacitance."""
    m = re.match(r"\s*([0-9]*\.?[0-9]+)\s*([pnuµm]?)F", value)
    if not m:
        return None
    return float(m.group(1)) * {"p": 1e-3, "n": 1.0, "u": 1e3, "µ": 1e3, "m": 1e6, "": 1e9}[m.group(2)]


# ------------------------------------------------------------------------------------------- plain geometry (mm)

def poly_pts(chain):
    return [(ToMM(chain.CPoint(i).x), ToMM(chain.CPoint(i).y)) for i in range(chain.PointCount())]


def seg_dist(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    L = ax * ax + ay * ay
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / L))
    return math.hypot(p[0] - a[0] - t * ax, p[1] - a[1] - t * ay)


def inside(p, pts):
    c = False
    for i in range(len(pts)):
        (x1, y1), (x2, y2) = pts[i], pts[i - 1]
        if (y1 > p[1]) != (y2 > p[1]) and p[0] < x1 + (p[1] - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def point_poly_dist(p, pts):
    """0 inside, else the distance to the outline."""
    if inside(p, pts):
        return 0.0
    return min(seg_dist(p, pts[i - 1], pts[i]) for i in range(len(pts)))


def segs_cross(p1, p2, q1, q2):
    d = lambda a, b, c: (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    d1, d2, d3, d4 = d(q1, q2, p1), d(q1, q2, p2), d(p1, p2, q1), d(p1, p2, q2)
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0) and d1 * d2 < 0 and d3 * d4 < 0


def poly_poly_dist(a, b):
    """Least distance between two simple polygons (0 when they touch or overlap, also when they cross with no
    vertex of one inside the other, like a plus sign)."""
    if any(inside(p, b) for p in a) or any(inside(p, a) for p in b):
        return 0.0
    if any(segs_cross(a[i - 1], a[i], b[j - 1], b[j]) for i in range(len(a)) for j in range(len(b))):
        return 0.0
    d = min(seg_dist(p, b[i - 1], b[i]) for p in a for i in range(len(b)))
    return min(d, min(seg_dist(p, a[i - 1], a[i]) for p in b for i in range(len(a))))


# ------------------------------------------------------------------------------------------- the board

class Part:
    def __init__(self, fp):
        self.fp = fp
        self.ref = fp.GetReference()
        self.bottom = fp.GetLayer() == pcbnew.B_Cu
        cy = fp.GetCourtyard(pcbnew.B_CrtYd if self.bottom else pcbnew.F_CrtYd)
        self.has_cy = cy.OutlineCount() > 0
        if self.has_cy:
            self.poly = pcbnew.SHAPE_POLY_SET(cy)
        else:
            bb = fp.GetBoundingBox(False)
            self.poly = pcbnew.SHAPE_POLY_SET()
            ch = pcbnew.SHAPE_LINE_CHAIN()
            for x, y in ((bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetTop()), (bb.GetRight(), bb.GetBottom()),
                         (bb.GetLeft(), bb.GetBottom())):
                ch.Append(x, y)
            ch.SetClosed(True)
            self.poly.AddOutline(ch)
        self.pts = [pt for k in range(self.poly.OutlineCount()) for pt in poly_pts(self.poly.Outline(k))]
        self.outlines = [poly_pts(self.poly.Outline(k)) for k in range(self.poly.OutlineCount())]
        bb = self.poly.BBox()
        self.bbox = (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
        self.centre = ((self.bbox[0] + self.bbox[2]) / 2, (self.bbox[1] + self.bbox[3]) / 2)


def pad_poly(pad, layer):
    ps = pad.GetEffectivePolygon(layer, pcbnew.ERROR_INSIDE)
    return [poly_pts(ps.Outline(k)) for k in range(ps.OutlineCount())]


def fab_bbox(fp, bottom):
    layer = pcbnew.B_Fab if bottom else pcbnew.F_Fab
    box = None
    for g in fp.GraphicalItems():
        if g.GetLayer() == layer and g.GetClass() != "PCB_TEXT" and g.GetClass() != "PCB_FIELD":
            bb = g.GetBoundingBox()
            w = ToMM(g.GetWidth()) / 2 if hasattr(g, "GetWidth") else 0.0      # the box includes half the stroke
            b = (ToMM(bb.GetLeft()) + w, ToMM(bb.GetTop()) + w, ToMM(bb.GetRight()) - w, ToMM(bb.GetBottom()) - w)
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    return box


def measure(a):
    board = pcbnew.LoadBoard(a.board)
    ox, oy = a.origin
    L = lambda p: (round(p[0] - ox, 3), round(p[1] - oy, 3))
    out = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(out, True)
    edge = poly_pts(out.Outline(0))
    ex0, ey0 = min(p[0] for p in edge), min(p[1] for p in edge)
    ex1, ey1 = max(p[0] for p in edge), max(p[1] for p in edge)
    parts = [Part(fp) for fp in board.GetFootprints()]
    placed = [p for p in parts if inside(p.centre, edge)]
    parked = sorted(p.ref for p in parts if p not in placed)
    R = {"board": a.board, "parts": {"total": len(parts), "placed": len(placed), "parked": parked}}
    edges = {}
    for e in a.edge:
        ref, side = e.split("=")
        edges[ref] = side.upper()

    # outside the outline (edge connectors may cross their own side only)
    bad = []
    for p in placed:
        side = edges.get(p.ref)
        for x, y in p.pts:
            if inside((x, y), edge) or point_poly_dist((x, y), edge) < 1e-4:
                continue
            ok = side and ((side == "L" and x < ex0 + 1e-6) or (side == "R" and x > ex1 - 1e-6) or
                           (side == "T" and y < ey0 + 1e-6) or (side == "B" and y > ey1 - 1e-6))
            if not ok:
                bad.append(p.ref)
                break
    R["outside"] = sorted(set(bad))

    # courtyard overlaps, same side
    ov, nocy = [], sorted(p.ref for p in placed if not p.has_cy)
    for i, p in enumerate(placed):
        for q in placed[i + 1:]:
            if p.bottom != q.bottom:
                continue
            if p.bbox[2] <= q.bbox[0] or q.bbox[2] <= p.bbox[0] or p.bbox[3] <= q.bbox[1] or q.bbox[3] <= p.bbox[1]:
                continue
            s = pcbnew.SHAPE_POLY_SET(p.poly)
            s.BooleanIntersection(q.poly)
            area = s.Area() / 1e12
            if area > AREA_EPS:
                ov.append((p.ref, q.ref, round(area, 3)))
    R["overlap"] = ov
    R["no_courtyard"] = nocy

    # mounting-hole keep-out
    holes = []
    for p in placed:
        if p.ref.startswith(a.holes) and any(ToMM(pd.GetDrillSize().x) >= 2.5 for pd in p.fp.Pads()):
            holes.append((p.ref, (ToMM(p.fp.GetPosition().x), ToMM(p.fp.GetPosition().y))))
    hk = []
    for p in placed:
        if any(p.ref == h for h, _ in holes):
            continue
        for h, c in holes:
            d = min(point_poly_dist(c, o) for o in p.outlines)
            if d < a.hole_keepout - 1e-6:
                hk.append((p.ref, h, round(d, 3)))
    R["hole"] = hk
    R["hole_keepout_mm"] = a.hole_keepout

    # rule areas (footprint and board) - LAY-6
    areas = []
    for p in placed:
        for z in p.fp.Zones():
            if z.GetIsRuleArea():
                areas.append((p.ref, z))
    for z in board.Zones():
        if z.GetIsRuleArea():
            areas.append(("board", z))
    ko, ko_info = [], []
    for owner, z in areas:
        flags = [n for n, f in (("pads", z.GetDoNotAllowPads()), ("footprints", z.GetDoNotAllowFootprints()),
                                ("tracks", z.GetDoNotAllowTracks()), ("vias", z.GetDoNotAllowVias()),
                                ("fills", z.GetDoNotAllowZoneFills())) if f]
        if not flags:
            continue
        zo = [poly_pts(z.Outline().Outline(k)) for k in range(z.Outline().OutlineCount())]
        layers = [l for l in z.GetLayerSet().Seq()]
        zb = z.GetBoundingBox()
        ko_info.append({"owner": owner, "name": z.GetZoneName(), "forbids": flags,
                        "layers": [board.GetLayerName(l) for l in layers],
                        "box": [*L((ToMM(zb.GetLeft()), ToMM(zb.GetTop()))), *L((ToMM(zb.GetRight()), ToMM(zb.GetBottom())))]})
        for p in placed:
            if p.ref == owner:
                continue
            if "footprints" in flags and any(poly_poly_dist(o, zz) == 0 for o in p.outlines for zz in zo):
                ko.append((p.ref, owner, z.GetZoneName() or "keep-out", "footprint"))
                continue
            if "pads" in flags:
                for pd in p.fp.Pads():
                    for l in layers:
                        if pd.IsOnLayer(l) and any(poly_poly_dist(pp, zz) == 0 for pp in pad_poly(pd, l) for zz in zo):
                            ko.append((p.ref, owner, z.GetZoneName() or "keep-out", "pad " + pd.GetNumber()))
                            break
    R["keepout"] = ko
    R["keepout_areas"] = ko_info

    # connectors on their edge
    ed = {}
    for ref, side in edges.items():
        p = next((q for q in placed if q.ref == ref), None)
        if p is None:
            ed[ref] = {"side": side, "placed": False}
            continue
        body = fab_bbox(p.fp, p.bottom) or p.bbox
        gap = {"L": body[0] - ex0, "R": ex1 - body[2], "T": body[1] - ey0, "B": ey1 - body[3]}
        nearest = min(gap, key=gap.get)
        ed[ref] = {"side": side, "placed": True, "body_gap": round(gap[side], 3), "nearest_side": nearest}
    R["edge"] = ed

    # LAY-5: bottom pads under top pads
    allow = set(r for r in a.allow_under.split(",") if r)
    tops = [(p.ref, pd, pad_poly(pd, pcbnew.F_Cu)) for p in placed if not p.bottom for pd in p.fp.Pads()
            if pd.IsOnLayer(pcbnew.F_Cu) and p.ref not in allow]
    under = []
    for p in placed:
        if not p.bottom:
            continue
        for pd in p.fp.Pads():
            if not pd.IsOnLayer(pcbnew.B_Cu) or pd.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                continue
            bp = pad_poly(pd, pcbnew.B_Cu)
            for ref, tp, tpp in tops:
                if ref == p.ref:
                    continue
                if any(poly_poly_dist(x, y) == 0 for x in bp for y in tpp):
                    under.append((p.ref + "." + pd.GetNumber(), ref + "." + tp.GetNumber()))
    R["under"] = under

    # decoupling
    rail = re.compile(a.rail)
    icre = re.compile(a.ic)
    caps = []
    for p in placed:
        if not p.ref.startswith("C"):
            continue
        nf = cap_nf(p.fp.GetValue())
        pads = list(p.fp.Pads())
        nets = [pd.GetNetname() for pd in pads]
        if nf is None or len(pads) != 2 or a.ground not in nets:
            continue
        rp = pads[0] if nets[1] == a.ground else pads[1]
        if not rail.search(rp.GetNetname()):
            continue
        c = rp.GetPosition()
        caps.append({"ref": p.ref, "nf": nf, "net": rp.GetNetname(), "xy": (ToMM(c.x), ToMM(c.y)), "bottom": p.bottom})
    pins = []
    skip = set(x for x in a.not_supply.split(",") if x)
    for p in placed:
        if not icre.search(p.ref):
            continue
        for pd in p.fp.Pads():
            n = pd.GetNetname()
            if n and rail.search(n) and "%s.%s" % (p.ref, pd.GetNumber()) not in skip:
                c = pd.GetPosition()
                pins.append({"ic": p.ref, "pin": pd.GetNumber(), "net": n, "xy": (ToMM(c.x), ToMM(c.y))})
    small_nets = set(c["net"] for c in caps if c["nf"] <= a.small + 1e-9)
    per_ic = {}
    for pn in pins:
        cand = [c for c in caps if c["net"] == pn["net"] and c["nf"] <= a.small + 1e-9]
        d, cref = (None, None)
        if cand:
            best = min(cand, key=lambda c: math.dist(c["xy"], pn["xy"]))
            d, cref = round(math.dist(best["xy"], pn["xy"]), 3), best["ref"]
        pn.update(dist=d, cap=cref)
        s = per_ic.setdefault(pn["ic"], {"pins": 0, "bulk_only": 0, "le1": 0, "le_limit": 0, "over": [], "worst": 0.0})
        if pn["net"] not in small_nets:
            s["bulk_only"] += 1
            continue
        s["pins"] += 1
        s["worst"] = max(s["worst"], d)
        if d <= 1.0:
            s["le1"] += 1
        if d <= a.limit + 1e-9:
            s["le_limit"] += 1
        else:
            s["over"].append((pn["pin"], pn["net"], d, cref))
    for c in caps:
        own = [pn for pn in pins if pn["net"] == c["net"]]
        if own:
            best = min(own, key=lambda pn: math.dist(c["xy"], pn["xy"]))
            c.update(pin=best["ic"] + "." + best["pin"], dist=round(math.dist(c["xy"], best["xy"]), 3))
        else:
            c.update(pin=None, dist=None)
    R["decoupling"] = {"limit": a.limit, "small_nf": a.small, "per_ic": per_ic,
                       "caps": [{k: (L(v) if k == "xy" else v) for k, v in c.items()} for c in caps]}

    # silk room (reported only)
    sr = re.compile(a.silk_refs)
    silk = []
    near = lambda p, q, m: not (q.bbox[0] > p.bbox[2] + m or q.bbox[2] < p.bbox[0] - m or q.bbox[1] > p.bbox[3] + m or q.bbox[3] < p.bbox[1] - m)
    for p in placed:
        if not sr.search(p.ref):
            continue
        others = [q for q in placed if q is not p and q.bottom == p.bottom and near(p, q, 6)]
        if p.ref.startswith("TP"):
            text = p.fp.GetValue()
            w, h = len(text) * 0.9 * a.silk + 0.3, a.silk + 0.3
            x0, y0, x1, y1 = p.bbox
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            boxes = {"N": (cx - w / 2, y0 - h, cx + w / 2, y0), "S": (cx - w / 2, y1, cx + w / 2, y1 + h),
                     "W": (x0 - w, cy - h / 2, x0, cy + h / 2), "E": (x1, cy - h / 2, x1 + w, cy + h / 2)}
            ok = []
            for side, b in boxes.items():
                pts = [(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])]
                if not all(inside(q_, edge) for q_ in pts):
                    continue
                # blocked by a courtyard that overlaps the box with area (touching edges is fine)
                if any(min(x for x, _ in oo) < b[2] - 1e-6 and max(x for x, _ in oo) > b[0] + 1e-6 and
                       min(y for _, y in oo) < b[3] - 1e-6 and max(y for _, y in oo) > b[1] + 1e-6 and
                       poly_poly_dist(pts, oo) == 0
                       for q in others for oo in q.outlines):
                    continue
                ok.append(side)
            silk.append((p.ref, "".join(ok) or "-", not ok))
        else:
            d, who = min(((poly_poly_dist(o, oo), q.ref) for q in others for o in p.outlines for oo in q.outlines), default=(99.0, ""))
            de = 99.0 if p.ref in edges else min(min(p.bbox[0] - ex0, ex1 - p.bbox[2]), min(p.bbox[1] - ey0, ey1 - p.bbox[3]))
            if de < d:
                d, who = de, "edge"
            silk.append((p.ref, "%.2f %s" % (d, who), d < a.silk))
    R["silk"] = silk
    R["silk_mm"] = a.silk
    return R


def report(R):
    P = R["parts"]
    print("[parts]     placed %d / %d; parked %d%s" % (P["placed"], P["total"], len(P["parked"]),
                                                       (": " + " ".join(P["parked"])) if P["parked"] else ""))
    print("[outside]   %d %s" % (len(R["outside"]), " ".join(R["outside"])))
    print("[overlap]   %d %s" % (len(R["overlap"]), " ".join("%s/%s(%.3f)" % o for o in R["overlap"])))
    if R["no_courtyard"]:
        print("            no courtyard (bounding box used): " + " ".join(R["no_courtyard"]))
    print("[hole]      %d within %.1f mm of a hole centre %s" % (len(R["hole"]), R["hole_keepout_mm"],
                                                              " ".join("%s~%s(%.2f)" % h for h in R["hole"])))
    print("[keepout]   %d pads or parts in forbidding areas %s" % (len(R["keepout"]), " ".join("%s@%s" % (k[0], k[1]) for k in R["keepout"])))
    for k in R["keepout_areas"]:
        if k["owner"] != "board":
            print("            %s keep-out %s on %s forbids %s" % (k["owner"], k["box"], ",".join(k["layers"]), ",".join(k["forbids"])))
    print("[edge]      " + "  ".join("%s %s %s" % (r, e["side"], ("%+.2f" % e["body_gap"]) + ("" if e["nearest_side"] == e["side"] else " (nearest side %s)" % e["nearest_side"]))
                                    if e["placed"] else "%s not placed" % r for r, e in sorted(R["edge"].items())))
    print("[under]     %d bottom pads under top pads %s" % (len(R["under"]), " ".join("%s<%s" % u for u in R["under"])))
    D = R["decoupling"]
    print("[decoupling] per supply pin, nearest capacitor <= %g nF (limit %.1f mm):" % (D["small_nf"], D["limit"]))
    for ic, s in sorted(D["per_ic"].items()):
        print("            %-5s pins %3d  <=1mm %3d  <=%.1fmm %3d  worst %.2f%s%s" % (
            ic, s["pins"], s["le1"], D["limit"], s["le_limit"], s["worst"],
            ("  bulk-only rails %d" % s["bulk_only"]) if s["bulk_only"] else "",
            ("  over: " + " ".join("%s(%s %.2f %s)" % o for o in s["over"])) if s["over"] else ""))
    far = sorted((c for c in D["caps"] if c["dist"] is not None), key=lambda c: -c["dist"])
    print("            capacitors to their nearest pin: %d; farthest %s" % (
        len(D["caps"]), " ".join("%s %.2f" % (c["ref"], c["dist"]) for c in far[:6])))
    flag = [s for s in R["silk"] if s[2]]
    print("[silk]      %d headers / test points; %d without room (test point: no side for its name; header: under %.1f mm "
          "to the next part or edge) %s" % (len(R["silk"]), len(flag), R["silk_mm"],
                                            " ".join("%s(%s)" % (s[0], s[1]) for s in flag)))


def main(argv):
    a = opts(argv)
    R = measure(a)
    report(R)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(R, f, indent=1, ensure_ascii=False)
    hard = len(R["outside"]) + len(R["overlap"]) + len(R["hole"]) + len(R["keepout"]) + len(R["under"])
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
