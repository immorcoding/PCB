"""The copper table of the copper step (PROC-4, docs/tools.md), after the refill.

    python -m Tools.KiCadDesignTools.copper.copper_table <board dir> <board> <out dir>

cu_sketch measure (read from <out dir>/measure.json), the copper-class nets' unconnected pads counted by pcbnew's own
connectivity on the refilled board (kicad-cli lists at most 499 unconnected items, and the signal nets are not routed
yet), split into this task and part B (BGA balls and the bottom parts under them); per rail the feed vias against
the rule of the power group; ground vias; the loop and crystal ground vias (U56, U54); DRC by type; the power group
on the line-order sketch copy (<out dir>/sketch_power/metrics.json); part B (the BGA power group: balls, sharing,
decoupling, VCAP / VDDA_MCU, the sketch copy's DRC and slots.txt). Writes <out dir>/table.txt and prints it; exit 1
when a copper-class net of this task is not connected. COPPER_SECONDS (environment): the step's time so far.

board.toml [copper.table]: nets (the copper-class nets), rails ([label, [feed pads], vias required]), no_vias (the
line for the rails without supply vias), loops (ground pads of the switcher loops), crystal_ground, ground_skip /
ground_skip_refs (ground pads that need no via of their own), part_a / part_b (the routes modules of the power
groups: PART_B, PLANE_NETS of the first, POWER of the second), decap_skip (balls left out of the 100 nF distance),
clusters (nets listed piece by piece), bga_areas (the BGA rule areas); [power] ground; the power plane is the layer of
role "power".
"""
import collections, json, os, sys

from Tools.KiCadDesignTools.copper.power_ties import power_plane


def clusters(board, nets):
    """{net: [[pad names] per connected piece]} from pcbnew's connectivity of the board as saved (fills included)."""
    import pcbnew
    c = board.GetConnectivity()
    out = {}
    for net in nets:
        pads = [p for f in board.GetFootprints() for p in f.Pads() if p.GetNetname() == net]
        name = {id(p): "%s.%s" % (p.GetParentFootprint().GetReference(), p.GetNumber()) for p in pads}
        key = lambda p: (p.GetParentFootprint().GetReference(), p.GetNumber(), p.GetPosition().x, p.GetPosition().y)
        seen, groups = set(), []
        for p in pads:
            if key(p) in seen:
                continue
            grp = [p] + [q for q in c.GetConnectedItems(p) if q.Type() == pcbnew.PCB_PAD_T and q.GetNetname() == net]
            ks = {key(q) for q in grp}
            new = [q for q in pads if key(q) in ks and key(q) not in seen]
            seen |= ks
            groups.append(sorted({"%s.%s" % (q.GetParentFootprint().GetReference(), q.GetNumber()) for q in new} | {name[id(p)]}))
        out[net] = groups
    return out


def copper_nets(cfg):
    """The copper-class nets of the board ([copper.table] nets)."""
    return list(cfg.need("copper.table.nets"))


def table(cfg, board_path, odir):
    import pcbnew
    from Tools.KiCadDesignTools.copper import cu_sketch
    T = cfg.need("copper.table")
    RP = cfg.module(T["part_a"])
    GND = cfg.need("power.ground")
    L = []
    m = json.load(open(os.path.join(odir, "measure.json"), encoding="utf-8"))
    L.append(cu_sketch.measure_text(m))
    # ---- connectivity of the copper-class nets
    b = pcbnew.LoadBoard(board_path)
    part_b = lambda name: name.split(".")[0] in RP.PART_B
    cl = clusters(b, copper_nets(cfg))
    mine, theirs = {}, {}
    for net, groups in cl.items():
        if len(groups) < 2:
            continue
        main = max(groups, key=lambda g: (not all(part_b(x) for x in g), len(g)))
        for g in groups:
            if g is main:
                continue
            (theirs if all(part_b(x) for x in g) else mine).setdefault(net, []).append(g)
    n_mine = sum(len(v) for v in mine.values())
    n_b = sum(len(v) for v in theirs.values())
    L.append("")
    L.append("铜皮类未连接（pcbnew 连通块，填充后的板）: 本任务 %d，B 部分（BGA 球和其下背面件）%d" % (n_mine, n_b))
    for net, gs in sorted(mine.items()):
        L.append("  本任务 %-11s %s" % (net, "  ".join("[%s]" % " ".join(g[:6]) for g in gs)))
    for net, gs in sorted(theirs.items()):
        L.append("  B 部分 %-11s %d 块: %s" % (net, len(gs), " ".join(x for g in gs for x in g)[:160]))
    # ---- feed vias per rail
    RAILS = [(label, list(pads), need) for label, pads, need in T["rails"]]
    sites = json.load(open(os.path.join(odir, "power_sites.json"), encoding="utf-8"))
    per_pad = collections.Counter(s["pad"] for s in sites["done"] if s["kind"] == "feed" or _own_via(s))
    L.append("")
    L.append("供电过孔（每 0.5 A 至少 1 个；稳压器输出、跳线电阻每侧、分块入口至少 2 个）:")
    for label, pads, need in RAILS:
        got = sum(per_pad[p] for p in pads)
        L.append("  %-44s %d / %d %s" % (label, got, need, "ok" if got >= need else "MISS"))
    L.append(T["no_vias"])
    plane_nets = tuple(RP.PLANE_NETS)
    single = [s for s in sites["done"] if _own_via(s) and s["net"] in plane_nets and s["pad"] not in {p for _, ps, _ in RAILS for p in ps}]
    L.append("  其余 %s 焊盘各 1 个过孔到 %s: %d 个焊盘" % (" / ".join(plane_nets), power_plane(cfg), len({s["pad"] for s in single})))
    # ---- ground
    skip_pads, skip_refs = set(T.get("ground_skip", [])), set(T.get("ground_skip_refs", []))
    g = [s for s in sites["done"] if s["net"] == GND]
    own = sorted({s["pad"] for s in g if _own_via(s)})
    gpads = [("%s.%s" % (f.GetReference(), p.GetNumber()), p) for f in b.GetFootprints() for p in f.Pads() if p.GetNetname() == GND]
    cand = [n for n, p in gpads if not p.HasHole() and not part_b(n) and n not in skip_pads and n.split(".")[0] not in skip_refs]
    rely = sorted(set(cand) - set(own))
    far = [s for s in g if s["kind"] == "via" and s["pad"].startswith("C") and s.get("edge", 0) > 1.0]
    L.append("")
    L.append("地: 过孔 %d 个（焊盘旁 %d，散热焊盘内 %d）；有自己过孔的焊盘 %d；靠铺地的焊盘 %d：%s" % (
        len(g), sum(1 for s in g if _own_via(s)), sum(1 for s in g if s["kind"] == "in pad"), len(own), len(rely), " ".join(rely)))
    L.append("  电容地过孔离焊盘边超过 1.0 mm: %s" % (" ".join("%s %.2f" % (s["pad"], s["edge"]) for s in far) or "0"))
    miss = [l for l in sites["log"] if l.startswith("NO ")]
    L.append("  找不到位置的: %d%s" % (len(miss), "".join("\n    " + l for l in miss)))
    L.append("环路的地过孔（U56，焊盘边到过孔中心 mm）: " + "  ".join(
        "%s %s" % (p, " ".join("%.2f" % s["edge"] if "edge" in s else _site(s) for s in g if s["pad"] == p) or "-") for p in T["loops"]))
    L.append("晶振外壳地（U54）: " + "  ".join("%s %s" % (p, next((_site(s) for s in g if s["pad"] == p), "没有位置"))
                                          for p in T["crystal_ground"]))
    # ---- DRC of the refilled board
    d = json.load(open(os.path.join(odir, "drc.json"), encoding="utf-8"))
    by = collections.Counter(v["type"] for v in d["violations"])
    L.append("")
    L.append("DRC（填充后的真板）: %s；未连接 %d 条（kicad-cli 最多列 499 条，信号线还没走）" % (
        " ".join("%s %d" % kv for kv in sorted(by.items())), len(d.get("unconnected_items", []))))
    # ---- the sketch copy
    sk = os.path.join(odir, "sketch_power", "metrics.json")
    if os.path.isfile(sk):
        s = json.load(open(sk, encoding="utf-8"))
        cg = s.get("drc_counted_group", {})
        L.append("线序草图副本上的电源组: 拦住构建的发现 %d，本组的 DRC 项 %s" % (
            sum(1 for f in s.get("findings", []) if f.get("hard")), " ".join("%s %d" % kv for kv in sorted(cg.items())) or "0"))
    L += part_b_text(cfg, b, odir)
    L.append("耗时 %s" % os.environ.get("COPPER_SECONDS", "-"))
    txt = "\n".join(L)
    open(os.path.join(odir, "table.txt"), "w", encoding="utf-8").write(txt + "\n")
    print(txt)
    return 1 if n_mine else 0


def _site(s):
    """A ground entry of the power group's log as the table shows it: a via with the distance from the pad edge to its
    centre, or an entry without a via of its own (a FIXED chain of the routes file: no edge) with its kind, position
    and length."""
    if "edge" in s:
        return "via (%.2f, %.2f) 焊盘边 %.2f" % (s["at"][0], s["at"][1], s["edge"])
    return "%s (%.2f, %.2f)%s" % (s["kind"], s["at"][0], s["at"][1], " 线长 %.2f" % s["len"] if s.get("len") is not None else "")


def _own_via(s):
    """True when the power group's log entry puts a via of its own beside the pad: a searched via, or a FIXED chain of
    the routes file that ends in a via (its "at")."""
    return s["kind"] == "via" or (s["kind"] == "fixed" and s.get("at") is not None)


def _others(x):
    """The balls a shared via is shared with: the log writes a list of names, or one name as a string."""
    return [x] if isinstance(x, str) else list(x)


def part_b_text(cfg, b, odir):
    """Part B of stop 5 (the BGA power group) on the real board: balls, vias, sharing, the bottom decoupling, VCAP and
    VDDA_MCU, and the sketch copy's DRC and plane slots (U31)."""
    import pcbnew
    T = cfg.need("copper.table")
    RB = cfg.module(T["part_b"])
    L = [""]
    path = os.path.join(odir, "power_bga_sites.json")
    if not os.path.isfile(path):
        return L + ["B 部分: 没有 power_bga_sites.json"]
    s = json.load(open(path, encoding="utf-8"))
    kinds = collections.Counter(k for n, p, sz, k in s["vias"])
    L.append("B 部分（routes_power_bga.py）: 过孔 %d 个（球的 %d：球间位 %d、封装外圈外侧 %d、空球位 %d；电容和磁珠自己的 %d）" % (
        len(s["vias"]), kinds["ball"] + kinds["ball lane"] + kinds["ball edge"], kinds["ball"], kinds["ball lane"], kinds["ball edge"],
        kinds["own"] + kinds["tie"]))
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    for ref, nets in RB.POWER.items():
        balls = [p for p in fps[ref].Pads() if p.GetNetname() in nets]
        per = collections.Counter(p.GetNetname() for p in balls)
        names = {"%s.%s" % (ref, p.GetNumber()) for p in balls}
        sh = [x for x in s["shared"] if x[0] in names]
        ns = [k for k in s["nosite"] if k in names]
        vias = {tuple(v) for k, v in s["ball_via"].items() if k in names}
        L.append("  %s: 球 %d（%s），过孔 %d；共用过孔 %d：%s；没有位置 %d%s" % (
            ref, len(balls), " ".join("%s %d" % kv for kv in sorted(per.items())), len(vias), len(sh),
            " ".join("%s->%s" % (x[0].split(".")[1], "+".join(o.split(".")[1] for o in _others(x[2]))) for x in sh) or "-", len(ns),
            "".join("\n    %s: %s" % (k, s["nosite"][k][:230]) for k in ns)))
    GND = cfg.need("power.ground")
    caps = s["caps"]
    kc = collections.Counter(c["kind"] for c in caps.values())
    stubs = [(c.get("stub") or 0.0, k) for k, c in caps.items() if "stub" in c["kind"]]
    worst = max(stubs) if stubs else (0.0, "-")
    L.append("背面去耦（焊盘 %d 个）: %s；最长短线（焊盘边外的长度）%.3f mm（%s）" % (
        len(caps), "  ".join("%s %d" % kv for kv in sorted(kc.items())), worst[0], worst[1]))
    gown = [c for c in caps.values() if c["net"] == GND and c["kind"] != "pour" and not c.get("balls")]
    L.append("  电容地焊盘：和地球共用过孔 %d 个，自己的地过孔 %d 个（焊盘边到过孔中心最远 %.2f mm，超过 1.0 mm 的 %d）" % (
        sum(1 for c in caps.values() if c["net"] == GND and c.get("balls")), len(gown),
        max([c.get("edge", 0) for c in gown] or [0]), sum(1 for c in gown if c.get("edge", 0) > 1.0)))
    supply_own = sorted(k for k, c in caps.items() if c["net"] != GND and c["kind"].startswith("own"))
    L.append("  电源焊盘没有落到球的过孔、用自己的过孔到 L5 的 %d 个: %s" % (len(supply_own), " ".join(supply_own) or "-"))
    small = [(f.GetReference(), p) for r, f in fps.items() if r.startswith("C") and f.GetValue().replace(" ", "").lower() in ("100n", "100nf", "0.1u", "0.1uf")
             for p in f.Pads()]
    rows = []
    skip = tuple(T["decap_skip"])
    for ref, nets in RB.POWER.items():
        for p in fps[ref].Pads():
            n = p.GetNetname()
            if n in nets and n not in skip:
                d = min((pcbnew.ToMM((q.GetPosition() - p.GetPosition()).EuclideanNorm()) for r, q in small if q.GetNetname() == n), default=99)
                rows.append((round(d, 2), "%s.%s" % (ref, p.GetNumber())))
    L.append("  每个电源球到最近 100 nF 的距离（LAY-2）: 最远 %.2f mm（%s），超过 2.5 mm 的 %d" % (max(rows)[0], max(rows)[1], sum(1 for r in rows if r[0] > 2.5)))
    cl = clusters(b, list(T["clusters"]))
    L.append("  %s 连通块: %s" % (" / ".join(T["clusters"]), "  ".join("%s %d（%s）" % (n, len(g), " | ".join(" ".join(x) for x in g)[:110]) for n, g in cl.items())))
    L += pours_in_areas(b, RB.POWER, tuple(T["bga_areas"]))
    sd = os.path.join(odir, "sketch_drc.json")
    if os.path.isfile(sd):
        d = json.load(open(sd, encoding="utf-8"))
        by = collections.Counter(v["type"] for v in d["violations"])
        hard = {k: n for k, n in by.items() if k in ("clearance", "hole_clearance", "annular_width", "copper_edge_clearance", "hole_to_hole",
                                                         "track_angle", "via_diameter", "track_width", "isolated_copper", "starved_thermal", "shorting_items")}
        L.append("线序草图副本（两组电源 + SDRAM 草图，填充后）DRC: %s；其中间距/孔/焊环/板边/线宽/角度/孤铜类 %s" % (
            " ".join("%s %d" % kv for kv in sorted(by.items())), " ".join("%s %d" % kv for kv in sorted(hard.items())) or "0"))
    sp = os.path.join(odir, "slots.txt")
    if os.path.isfile(sp):
        L += open(sp, encoding="utf-8").read().rstrip("\n").split("\n")
    return L


def pours_in_areas(b, power, areas):
    """Zone fills inside the BGA rule areas, from the saved fills: L1 must have none (user 2026-11-22, the F.Cu
    keep-outs NOPOUR_L1_* of the placement); L6 is listed per fill piece with the pads and vias of its net it joins
    there (left as it is, for the user to decide). Also the supply and ground balls of the packages (power = {ref:
    [nets]}) that are not on the main connected piece of their net."""
    import pcbnew
    ids = list(b.GetEnabledLayers().CuStack())
    rect = {z.GetZoneName(): z.Outline() for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName() in areas}
    mm2 = lambda s: s.Area() / 1e12
    pads = [("%s.%s" % (f.GetReference(), p.GetNumber()), p) for f in b.GetFootprints() for p in f.Pads()]
    vias = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    l1, l6 = {}, []
    for z in b.Zones():
        if z.GetIsRuleArea() or not z.IsOnCopperLayer() or z.GetLayer() not in (ids[0], ids[-1]):
            continue
        lay = z.GetLayer()
        fill = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(lay)); fill.Simplify()
        for an, R in rect.items():
            F = pcbnew.SHAPE_POLY_SET(fill); F.BooleanIntersection(R); F.Simplify()
            if lay == ids[0]:
                l1[an] = l1.get(an, 0.0) + mm2(F)
                continue
            for k in range(F.OutlineCount()):
                one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(F.Outline(k))
                for h in range(F.HoleCount(k)):
                    one.AddHole(F.Hole(k, h))
                if mm2(one) < 0.01:
                    continue
                joined = []
                for name, p in pads:
                    if p.GetNetname() != z.GetNetname() or not p.IsOnLayer(lay):
                        continue
                    o = p.GetEffectivePolygon(lay, pcbnew.ERROR_INSIDE).Outline(0)
                    if any(one.Contains(o.CPoint(i)) for i in range(o.PointCount())) or one.Contains(p.GetPosition()):
                        joined.append(name)
                nv = sum(1 for v in vias if v.GetNetname() == z.GetNetname() and one.Collide(v.GetPosition(), int(v.GetWidth(lay) / 2)))
                l6.append((an, z.GetZoneName(), z.GetNetname(), mm2(one), joined, nv))
    out = ["  BGA 区内的 L1 铺铜（place.py 的 F.Cu 禁铺区 NOPOUR_L1_*，填充后）: %s" % "  ".join("%s %.3f mm2" % kv for kv in sorted(l1.items()))]
    out.append("  BGA 区内的 L6 铺铜（保留；每块: 面积、连到的本网络焊盘、本网络过孔数）:")
    for an, zn, net, a, joined, nv in sorted(l6, key=lambda r: (r[0], r[1], -r[3])):
        out.append("    %-9s %-20s %-9s %7.2f mm2  焊盘 %s  过孔 %d" % (an, zn, net, a, " ".join(sorted(joined)) or "-", nv))
    # supply and ground balls off the main piece of their net
    lost = []
    for net, groups in clusters(b, sorted({n for ns in power.values() for n in ns})).items():
        main = max(groups, key=len)
        lost += ["%s(%s)" % (x, net) for g in groups if g is not main for x in g if x.split(".")[0] in power and len(groups) > 1]
    out.append("  电源和地球不在本网络主连通块上的: %d %s" % (len(lost), " ".join(lost)))
    return out


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(argv) != 3:
        print(__doc__)
        return 2
    from Tools.KiCadDesignTools.core import config
    return table(config.load(argv[0]), argv[1], argv[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
