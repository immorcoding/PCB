"""Plane slots (U31) on a refilled board: antipad chains in the plane fills, cut-off vias, the BGA blocks' feed necks.

    python -m Tools.KiCadDesignTools.copper.plane_slots <board dir> <refilled board> <out dir>
                    [--window NAME X0 Y0 X1 Y1 ...] [--part-b <power_bga_sites.json>] [--layers L5] [--stem NAME]

Per plane layer and window: the voids of the plane fill that hold vias (antipads merged into slots), their length
(farthest two points), the nets whose tracks on the neighbouring signal layers cross them, and whether the part-B
vias (routes_power_bga.py) make them longer; vias of the plane's own net that the fill does not hold on its main
piece (cut off); the narrowest connection of the BGA blocks on the power plane between their feed vias and the ball
field. Writes <out dir>/<stem>.json and <stem>.txt (default stem "slots") and prints the text.
--window (repeatable): instead of the default windows; --part-b: the vias counted as part B (default
<out dir>/<[copper.slots] part_b>); --layers: only these plane layers (comma-separated).

board.toml [copper.slots]: windows (default {name: [x0, y0, x1, y1]}, local mm), ref_layers ({plane layer: its
neighbouring signal layers}), report (slots longer than this are listed, mm), blocks ({net of a BGA block on the power
plane: its rule area}), part_b (default part-B file, relative to the out folder). The power plane is the layer of
role "power" ([layers]); the origin is [board] origin; the planes' zone clearance and minimum width (when two antipads
join) are the copper sketch's ([copper] sketch: plane_clearance, minwidth).
"""
import collections, json, math, os, sys

from Tools.KiCadDesignTools.copper.power_ties import power_plane


def slots(cfg, board_path, odir, windows=None, part_b=None, layers=None, stem="slots"):
    """U31 on a refilled board (the line-order sketch copy, or the board after the route step): per plane layer and
    window, the voids of the plane fill that hold vias, the cut-off own-net vias, the BGA blocks' necks on the power
    plane. Writes <out dir>/<stem>.json and <stem>.txt.
    layers: only these plane layers (default every layer of [copper.slots] ref_layers).
    windows: {name: (x0, y0, x1, y1)} instead of [copper.slots] windows (the route step measures the whole bus region);
    part_b: the power_bga_sites.json whose vias are counted as part B (default <out dir>/<[copper.slots] part_b>)."""
    import pcbnew
    from Tools.KiCadDesignTools.copper import cu_sketch
    sl = cfg.need("copper.slots")
    REF_LAYERS = sl["ref_layers"]
    PWR_PLANE = power_plane(cfg)
    BLOCKS = sl["blocks"]
    PLANE_CLR, MINWIDTH = cfg.copper_plane()          # the planes' zone clearance and minimum width (copper sketch)
    OX, OY = cfg.origin
    b = pcbnew.LoadBoard(board_path)
    ids = list(b.GetEnabledLayers().CuStack())
    lname = {lid: "L%d" % (i + 1) for i, lid in enumerate(ids)}
    lid = {v: k for k, v in lname.items()}
    mm = lambda v: v / 1e6
    loc = lambda p: (round(mm(p.x) - OX, 3), round(mm(p.y) - OY, 3))
    V = lambda x, y: pcbnew.VECTOR2I(int(round((x + OX) * 1e6)), int(round((y + OY) * 1e6)))
    sp = part_b or os.path.join(odir, *sl["part_b"].split("/"))
    mine = set()
    if os.path.isfile(sp):
        mine = {(n, round(p[0], 3), round(p[1], 3)) for n, p, s, k in json.load(open(sp, encoding="utf-8"))["vias"]}
    vias, tracks = [], collections.defaultdict(list)
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            vias.append((t.GetNetname(), loc(t.GetPosition()), mm(t.GetWidth(pcbnew.F_Cu))))
        elif t.Type() == pcbnew.PCB_TRACE_T:
            tracks[lname[t.GetLayer()]].append((t.GetNetname(), t.GetStart(), t.GetEnd()))
    areas = {z.GetZoneName(): z.Outline() for z in b.Zones() if z.GetIsRuleArea()}
    windows = windows or {k: tuple(v) for k, v in sl["windows"].items()}
    out = {"board": board_path, "slots": [], "longest": {}, "cut_off": [], "necks": {},
           "windows": ["%s (%g, %g)-(%g, %g)" % ((k,) + tuple(w)) for k, w in windows.items()]}
    for wname, (x0, y0, x1, y1) in windows.items():
        win = pcbnew.SHAPE_POLY_SET()
        ch = pcbnew.SHAPE_LINE_CHAIN()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            ch.Append(V(x, y))
        ch.SetClosed(True)
        win.AddOutline(ch)
        # only the board less a 0.3 mm rim: the fills stop 0.254 short of the edge, and a `whole` zone reaches 1 mm past
        # it, so a window over the edge would count that rim as one void round the board
        brd = pcbnew.SHAPE_POLY_SET()
        b.GetBoardPolygonOutlines(brd, True)
        brd.Deflate(300000, pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, 2000)
        win.BooleanIntersection(brd)
        for z in b.Zones():
            if z.GetIsRuleArea() or not z.IsOnCopperLayer():
                continue
            L = lname.get(z.GetLayer())
            if L not in REF_LAYERS or (layers and L not in layers):
                continue
            net = z.GetNetname()
            A = pcbnew.SHAPE_POLY_SET(z.Outline()); A.BooleanIntersection(win)
            if not A.OutlineCount():
                continue
            fill = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(z.GetLayer())); fill.Simplify()
            F = pcbnew.SHAPE_POLY_SET(fill); F.BooleanIntersection(win)
            void = pcbnew.SHAPE_POLY_SET(A); void.BooleanSubtract(F); void.Simplify()
            for k in range(void.OutlineCount()):
                o = void.Outline(k)
                pts = [loc(o.CPoint(i)) for i in range(o.PointCount())]
                one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(o)
                inside = [v for v in vias if v[0] != net and one.Contains(V(*v[1]))]
                if not inside:
                    continue
                far = max(((math.dist(p, q), p, q) for i, p in enumerate(pts) for q in pts[i + 1:]), default=(0, None, None))
                cross = set()
                for rl in REF_LAYERS[L]:
                    for n, a, c in tracks[rl]:
                        if one.Collide(pcbnew.SEG(a, c), 0):
                            cross.add(n)
                own = [v for v in inside if (v[0], round(v[1][0], 3), round(v[1][1], 3)) in mine]
                rest = [v for v in inside if v not in own]
                span = 0.0                                  # longest chain of the other vias alone (antipads merging)
                todo = list(range(len(rest)))
                while todo:
                    grp, st = set(), [todo.pop()]
                    while st:
                        i = st.pop(); grp.add(i)
                        for j in list(todo):
                            if math.dist(rest[i][1], rest[j][1]) < (rest[i][2] + rest[j][2]) / 2 + 2 * PLANE_CLR + MINWIDTH:
                                todo.remove(j); st.append(j)
                    m = [rest[i] for i in grp]
                    span = max(span, max((math.dist(a[1], c[1]) for a in m for c in m), default=0) + max(v[2] for v in m) + 2 * PLANE_CLR)
                row = {"window": wname, "layer": L, "zone": z.GetZoneName(), "net": net, "length": round(far[0], 3),
                       "ends": [far[1], far[2]], "vias": len(inside), "part_b_vias": len(own),
                       "without_part_b": round(span, 3), "via_nets": sorted({v[0] for v in inside}), "crossing": sorted(cross)}
                out["slots"].append(row)
            # vias of the plane's own net that are not on the main piece of its fill (cut off)
            pieces = cu_sketch.split(fill)
            if not pieces:
                continue
            main = max(range(len(pieces)), key=lambda i: pieces[i].Area())
            for v in vias:
                if v[0] == net and x0 <= v[1][0] <= x1 and y0 <= v[1][1] <= y1 and A.Contains(V(*v[1])):
                    if not pieces[main].Contains(V(*v[1])):
                        out["cut_off"].append({"layer": L, "zone": z.GetZoneName(), "net": net, "via": v[1], "part_b": (v[0], round(v[1][0], 3), round(v[1][1], 3)) in mine})
    out["slots"].sort(key=lambda r: (r["layer"], -r["length"]))
    for r in out["slots"]:
        k = r["layer"]
        if k not in out["longest"] or r["length"] > out["longest"][k]["length"]:
            out["longest"][k] = r
    # the BGA blocks on the power plane: narrowest connection between the feed vias (outside the rule area) and the ball field
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() not in BLOCKS or lname.get(z.GetLayer()) != PWR_PLANE or (layers and PWR_PLANE not in layers):
            continue
        net, area = z.GetNetname(), areas[BLOCKS[z.GetNetname()]]
        fill = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(z.GetLayer())); fill.Simplify()
        pieces = cu_sketch.split(fill)
        bb = area.BBox()
        centre = bb.GetCenter()
        feeds = [(t.GetPosition(), int(t.GetWidth(z.GetLayer()) / 2), "via", "feed via%s" % (loc(t.GetPosition()),), False) for t in b.GetTracks()
                 if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == net and not area.Contains(t.GetPosition())]
        balls = [(t.GetPosition(), int(t.GetWidth(z.GetLayer()) / 2)) for t in b.GetTracks()
                 if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == net and area.Contains(t.GetPosition())]
        main = max(pieces, key=lambda p: p.Area()) if pieces else None

        def reach(w):
            """Supply vias in the rule area that a strip of width w still joins to the feed vias."""
            d = pcbnew.SHAPE_POLY_SET(main)
            d.Deflate(int(w * 1e6 / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, 2000)
            subs = cu_sketch.split(d)
            fed = {k for k, s in enumerate(subs) for pt, r, *_ in feeds if s.Collide(pt, int(r + w * 1e6 / 2 + 20000))}
            return sum(1 for pt, r in balls if any(subs[k].Collide(pt, int(r + w * 1e6 / 2 + 20000)) for k in fed))
        lo, hi = 0.0, 5.0
        if main is not None and feeds and balls and reach(0.02):
            if reach(hi):
                lo = hi
            for _ in range(10):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if reach(mid) else (lo, mid)
        n2 = reach(2.0) if main is not None and feeds and balls else 0
        out["necks"][net] = {"pieces": len(pieces), "neck_mm": round(lo, 3), "feeds": len(feeds), "field_vias": len(balls),
                             "field_vias_at_2mm": n2,
                             "note": "the widest strip from the feed vias that still reaches a supply via in the rule area"}
    out["longest_zone"] = {}
    for r in out["slots"]:
        k = "%s %s" % (r["layer"], r["zone"])
        if k not in out["longest_zone"] or r["length"] > out["longest_zone"][k]["length"]:
            out["longest_zone"][k] = r
    json.dump(out, open(os.path.join(odir, stem + ".json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    txt = slots_text(out, sl["report"], PWR_PLANE)
    open(os.path.join(odir, stem + ".txt"), "w", encoding="utf-8").write(txt + "\n")
    print(txt)


def slots_text(s, report, plane):
    L = ["平面开槽（U31，填充后；窗口 %s）: 列出长于 %.1f mm 的" % (" ".join(s.get("windows", [])) or "规则区外扩 2 mm", report)]
    for r in s["slots"]:
        if r["length"] > report:
            L.append("  %-2s %-5s %-6.2f mm  (%.2f, %.2f)-(%.2f, %.2f)  过孔 %d（B 部分 %d，去掉它们后最长 %.2f）  过孔网络 %s  上方走线 %s" % (
                r["layer"], r["window"], r["length"], r["ends"][0][0], r["ends"][0][1], r["ends"][1][0], r["ends"][1][1], r["vias"], r["part_b_vias"],
                r["without_part_b"], " ".join(r["via_nets"][:8]) + (" …" if len(r["via_nets"]) > 8 else ""), " ".join(r["crossing"]) or "-"))
    L.append("  每块最长: " + "  ".join("%s %.2f mm (%.2f, %.2f)-(%.2f, %.2f)" % (k, v["length"], v["ends"][0][0], v["ends"][0][1], v["ends"][1][0], v["ends"][1][1])
                                     for k, v in sorted(s.get("longest_zone", {}).items())))
    L.append("  每层最长: " + "  ".join("%s %.2f mm (%s)" % (k, v["length"], v["window"]) for k, v in sorted(s["longest"].items())))
    L.append("  被切断的本网络过孔: %d%s" % (len(s["cut_off"]), "".join("\n    %s %s %s (%.2f, %.2f)%s" % (c["layer"], c["zone"], c["net"], c["via"][0], c["via"][1], " B 部分" if c["part_b"] else "") for c in s["cut_off"])))
    for net, n in s["necks"].items():
        L.append("  %s %-11s 块数 %d；供电过孔 %d 个到球区（区内 %d 个本网络过孔）的最窄连接 %.2f mm（能连到第一个的最宽铜带）；按 2.0 mm 宽的铜带能到的 %d 个" % (
            plane, net, n["pieces"], n["feeds"], n["field_vias"], n["neck_mm"], n["field_vias_at_2mm"]))
    return "\n".join(L)


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(argv) < 3:
        print(__doc__)
        return 2
    from Tools.KiCadDesignTools.core import config
    cfg = config.load(argv[0])
    a = argv[3:]
    win = {a[k + 1]: tuple(float(v) for v in a[k + 2:k + 6]) for k in range(len(a)) if a[k] == "--window"} or None
    slots(cfg, argv[1], argv[2], win, a[a.index("--part-b") + 1] if "--part-b" in a else None,
          a[a.index("--layers") + 1].split(",") if "--layers" in a else None, a[a.index("--stem") + 1] if "--stem" in a else "slots")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
