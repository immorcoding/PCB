"""PROTOTYPE (issue 15): geometry of the tuned nets read from the board file. These are the things DRC
and scripts/track_shape.py do not look at; every number in the README's "tightest spots" comes from here.

    D:\\KiCad\\bin\\python.exe geo_check.py <variant dir>      -> geo.json, geo.txt (Chinese)

Per board, for the /FMC_* nets:
  area_gap      smallest copper gap from an ARC, and from a serpentine leg, to a rule-area edge
  net_gap       smallest copper gap from a serpentine piece (arc or leg) to copper of another net on the
                same layer (track, arc, via, pad), with the place; also the smallest gap of all tracks
  lead          straight left between a BEND (a joint where the direction changes without an arc) and the
                first arc of a serpentine; "sharp_arc" counts the ones below 0.35 mm (design-rules.md
                calls a segment under 0.35 mm with 90 degrees of turning around it "sharp";
                track_shape.py ignores arcs and cannot see this)
  sweep         smallest / largest arc angle
  thin_outside  length of 0.09 track that lies outside both rule areas, per net
  via_turn      change of direction across each via (180 = the track doubles back under itself)
  off_grid      track ends, not on an arc, whose coordinates are not a multiple of 1 um
Coordinates are local mm (board file mm - 100).
"""
import collections, json, math, os, sys
import pcbnew

NAME = "lentune"
SHARP = 0.35
mm = pcbnew.ToMM
Lp = lambda v: (mm(v.x) - 100, mm(v.y) - 100)


def arc_geom(t):
    (x0, y0), (xm, ym), (x1, y1) = Lp(t.GetStart()), Lp(t.GetMid()), Lp(t.GetEnd())
    cx, cy = Lp(t.GetCenter()); r = math.hypot(x0 - cx, y0 - cy)
    a0, am, a1 = (math.atan2(y - cy, x - cx) for x, y in ((x0, y0), (xm, ym), (x1, y1)))
    d = (a1 - a0) % (2 * math.pi)
    if (am - a0) % (2 * math.pi) > d:
        d -= 2 * math.pi
    return (cx, cy), r, a0, d


def arc_pts(t, step=0.004):
    (cx, cy), r, a0, d = arc_geom(t)
    n = max(4, int(abs(d) * r / step))
    return [(cx + r * math.cos(a0 + d * i / n), cy + r * math.sin(a0 + d * i / n)) for i in range(n + 1)]


def d_pt_seg(p, a, c):
    vx, vy = c[0] - a[0], c[1] - a[1]
    L2 = vx * vx + vy * vy
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L2))
    return math.hypot(p[0] - a[0] - t * vx, p[1] - a[1] - t * vy)


def d_seg_seg(a, b, c, d):
    def ccw(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    if ccw(a, b, c) * ccw(a, b, d) < 0 and ccw(c, d, a) * ccw(c, d, b) < 0:
        return 0.0
    return min(d_pt_seg(a, c, d), d_pt_seg(b, c, d), d_pt_seg(c, a, b), d_pt_seg(d, a, b))


def d_poly_rect(pts, R):
    """Smallest distance from a polyline to an axis-aligned rectangle (0 when it touches or is inside)."""
    x0, y0, x1, y1 = R
    best = 1e9
    edges = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    for a, c in zip(pts, pts[1:]):
        if x0 <= a[0] <= x1 and y0 <= a[1] <= y1:
            return 0.0
        for e in edges:
            best = min(best, d_seg_seg(a, c, e[0], e[1]))
    return best


def clip_outside(a, c, rects, n=2000):
    """Length of segment a-c that lies outside every rectangle (sampled, 2000 steps)."""
    out = 0
    for i in range(n):
        t = (i + 0.5) / n
        x, y = a[0] + (c[0] - a[0]) * t, a[1] + (c[1] - a[1]) * t
        if not any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in rects):
            out += 1
    return math.dist(a, c) * out / n


def main(vdir):
    B = pcbnew.LoadBoard(os.path.join(vdir, NAME + ".kicad_pcb"))
    areas = {}
    for z in B.Zones():
        if z.GetIsRuleArea():
            bb = z.GetBoundingBox()
            areas[z.GetZoneName()] = Lp(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop())) + Lp(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
    rects = list(areas.values())
    items = []                                              # dict per copper piece
    for t in B.GetTracks():
        n = t.GetNetname()
        if t.Type() == pcbnew.PCB_VIA_T:
            items.append({"k": "via", "net": n, "layer": None, "pts": [Lp(t.GetPosition())] * 2, "hw": mm(t.GetWidth(pcbnew.F_Cu)) / 2})
        elif t.Type() == pcbnew.PCB_ARC_T:
            items.append({"k": "arc", "net": n, "layer": t.GetLayer(), "pts": arc_pts(t), "hw": mm(t.GetWidth()) / 2, "t": t})
        else:
            items.append({"k": "seg", "net": n, "layer": t.GetLayer(), "pts": [Lp(t.GetStart()), Lp(t.GetEnd())], "hw": mm(t.GetWidth()) / 2, "t": t})
    for fp in B.GetFootprints():
        for p in fp.Pads():
            items.append({"k": "pad", "net": p.GetNetname() or ("pad " + fp.GetReference() + "." + p.GetNumber()), "layer": pcbnew.F_Cu,
                          "pts": [Lp(p.GetPosition())] * 2, "hw": max(mm(p.GetSizeX()), mm(p.GetSizeY())) / 2,
                          "name": fp.GetReference() + "." + p.GetNumber()})
    for it in items:
        xs, ys = [p[0] for p in it["pts"]], [p[1] for p in it["pts"]]
        it["bb"] = (min(xs) - it["hw"], min(ys) - it["hw"], max(xs) + it["hw"], max(ys) + it["hw"])
    tracks = [it for it in items if it["k"] in ("seg", "arc") and it["net"].startswith("/FMC_")]

    # joints: exact nm end points
    at = collections.defaultdict(list)
    for it in tracks:
        t = it["t"]
        for p in (t.GetStart(), t.GetEnd()):
            at[(it["net"], it["layer"], p.x, p.y)].append(it)

    def other(it, p):
        return [o for o in at[(it["net"], it["layer"], p.x, p.y)] if o is not it]

    # which straight pieces belong to a serpentine: legs (arc at both ends) ; leads (arc at one end)
    leads, off_grid = [], []
    for it in tracks:
        if it["k"] != "seg":
            continue
        t = it["t"]
        ends = [(p, other(it, p)) for p in (t.GetStart(), t.GetEnd())]
        n_arc = sum(1 for _, o in ends if any(x["k"] == "arc" for x in o))
        it["serp"] = n_arc == 2
        for p, o in ends:
            if not any(x["k"] == "arc" for x in o) and (p.x % 1000 or p.y % 1000):
                off_grid.append("%s (%.6f, %.6f)" % (it["net"], mm(p.x) - 100, mm(p.y) - 100))
        if n_arc == 1:
            (p, o), = [(p, o) for p, o in ends if not any(x["k"] == "arc" for x in o)]
            if o and o[0]["k"] == "seg":                    # the far end is a bend (or a width change on a straight)
                a, c = it["pts"]; q0, q1 = o[0]["pts"]
                d1 = math.atan2(c[1] - a[1], c[0] - a[0]); d2 = math.atan2(q1[1] - q0[1], q1[0] - q0[0])
                turn = abs(math.degrees(math.asin(max(-1, min(1, math.sin(d1 - d2))))))
                if turn > 1:
                    leads.append({"net": it["net"], "len": round(mm(t.GetLength()), 4), "at": [round(mm(p.x) - 100, 3), round(mm(p.y) - 100, 3)]})
    for it in tracks:
        it.setdefault("serp", it["k"] == "arc")

    # gap to rule-area edges (pieces that do not touch an area)
    area_gap = {"arc": None, "leg": None}
    for it in tracks:
        if not it["serp"]:
            continue
        for name, R in areas.items():
            d = d_poly_rect(it["pts"], R) - it["hw"]
            key = "arc" if it["k"] == "arc" else "leg"
            mid = it["pts"][len(it["pts"]) // 2]
            if area_gap[key] is None or d < area_gap[key]["gap"]:
                area_gap[key] = {"gap": round(d, 4), "net": it["net"], "area": name, "at": [round(mid[0], 3), round(mid[1], 3)]}

    # gap to other nets, same layer
    def gap(a, b):
        if a["bb"][0] > b["bb"][2] + 0.6 or b["bb"][0] > a["bb"][2] + 0.6 or a["bb"][1] > b["bb"][3] + 0.6 or b["bb"][1] > a["bb"][3] + 0.6:
            return None
        best, where = 1e9, None
        for p, q in zip(a["pts"], a["pts"][1:]):
            for r, s in zip(b["pts"], b["pts"][1:]):
                d = d_seg_seg(p, q, r, s)
                if d < best:
                    best, where = d, ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
        return best - a["hw"] - b["hw"], where

    pairs = collections.defaultdict(lambda: None)           # (net, other) -> smallest serpentine gap
    serp_min, all_min = None, None
    for a in tracks:
        for b in items:
            if b is a or b["net"] == a["net"] or (b["layer"] is not None and b["layer"] != a["layer"]):
                continue
            if b["k"] in ("seg", "arc") and b["net"].startswith("/FMC_") and id(b) < id(a) and not a["serp"]:
                continue                                    # plain track pairs once
            g = gap(a, b)
            if g is None:
                continue
            rec = {"gap": round(g[0], 4), "net": a["net"], "other": b.get("name") or b["net"], "other_kind": b["k"],
                   "at": [round(g[1][0], 3), round(g[1][1], 3)]}
            if all_min is None or rec["gap"] < all_min["gap"]:
                all_min = rec
            if a["serp"]:
                if serp_min is None or rec["gap"] < serp_min["gap"]:
                    serp_min = rec
                k = (a["net"], rec["other"])
                if pairs[k] is None or rec["gap"] < pairs[k]["gap"]:
                    pairs[k] = rec

    # arcs
    sweeps = [abs(math.degrees(arc_geom(it["t"])[3])) for it in tracks if it["k"] == "arc"]

    # 0.09 track outside the areas
    thin = collections.defaultdict(float)
    for it in tracks:
        if it["k"] == "seg" and it["hw"] * 2 < 0.1:
            thin[it["net"]] += clip_outside(it["pts"][0], it["pts"][1], rects)

    # direction change across vias
    via_turn = []
    for v in items:
        if v["k"] != "via" or not v["net"].startswith("/FMC_"):
            continue
        dirs = []
        for it in tracks:
            if it["net"] == v["net"] and it["k"] == "seg":
                for i in (0, 1):
                    if math.dist(it["pts"][i], v["pts"][0]) < 1e-6:
                        o = it["pts"][1 - i]
                        dirs.append(math.atan2(o[1] - v["pts"][0][1], o[0] - v["pts"][0][0]))
        if len(dirs) == 2:                                   # 0 = straight through in plan view, 180 = doubles back
            dd = abs((dirs[0] - dirs[1] + math.pi) % (2 * math.pi) - math.pi)
            via_turn.append({"net": v["net"], "at": [round(v["pts"][0][0], 3), round(v["pts"][0][1], 3)], "turn": round(180 - math.degrees(dd), 1)})

    res = {"arcs": len(sweeps), "sweep_min": round(min(sweeps), 2) if sweeps else None, "sweep_max": round(max(sweeps), 2) if sweeps else None,
           "area_gap": area_gap, "serp_net_gap": serp_min, "all_net_gap": all_min,
           "pairs": sorted((v for v in pairs.values() if v and v["gap"] < 0.3), key=lambda r: r["gap"]),
           "leads": sorted(leads, key=lambda r: r["len"]), "sharp_arc": sum(1 for l in leads if l["len"] < SHARP - 1e-6),
           "lead_min": min((l["len"] for l in leads), default=None),
           "thin_outside": {n: round(v, 3) for n, v in sorted(thin.items()) if v > 0.005},
           "via_turn": via_turn, "off_grid": off_grid}
    json.dump(res, open(os.path.join(vdir, "geo.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    s = lambda n: n.replace("/FMC_", "")
    out = []
    if sweeps:
        g = area_gap["arc"]
        out.append("- 蛇形的铜离规则区边最近：圆弧 %.3f mm（%s，%s，在 (%.2f, %.2f)）%s。" % (
            g["gap"], s(g["net"]), g["area"], g["at"][0], g["at"][1],
            "；直腿 %.3f mm" % area_gap["leg"]["gap"] if area_gap["leg"] else ""))
        g = serp_min
        out.append("- 蛇形的铜离别的网络最近：%.3f mm（%s 对 %s，在 (%.2f, %.2f)）。0.3 mm 以内的还有：%s。" % (
            g["gap"], s(g["net"]), s(g["other"]), g["at"][0], g["at"][1],
            "；".join("%s 对 %s %.3f" % (s(p["net"]), s(p["other"]), p["gap"]) for p in res["pairs"][1:8]) or "无"))
        out.append("- 拐点到第一个圆弧之间留的直线：最短 %s mm；短于 %.2f mm 的 %d 处%s。" % (
            "%.3f" % res["lead_min"] if leads else "—", SHARP, res["sharp_arc"],
            "（%s）" % "，".join("%s %.3f" % (s(l["net"]), l["len"]) for l in res["leads"] if l["len"] < SHARP - 1e-6) if res["sharp_arc"] else ""))
        out.append("- 圆弧 %d 个，圆心角 %.1f°–%.1f°。" % (len(sweeps), min(sweeps), max(sweeps)))
    g = all_min
    out.append("- 这组线（含没有蛇形的部分）离别的网络的铜最近 %.3f mm（%s 对 %s，在 (%.2f, %.2f)）。" % (
        g["gap"], s(g["net"]), s(g["other"]), g["at"][0], g["at"][1]))
    out.append("- 规则区外的 0.09 mm 线：%s。" % ("，".join("%s %.2f" % (s(n), v) for n, v in res["thin_outside"].items()) or "无"))
    out.append("- 过孔两侧走向的夹角（0 = 直穿，180 = 原路折回）：%s。" % ("，".join("%s %.0f°" % (s(v["net"]), v["turn"]) for v in via_turn) or "无过孔"))
    out.append("- 不在 1 µm 网格上的线端（圆弧端点除外）：%d 个%s。" % (len(off_grid), "（%s）" % "；".join(off_grid[:4]) if off_grid else ""))
    open(os.path.join(vdir, "geo.txt"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1])
