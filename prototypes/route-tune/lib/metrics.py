"""PROTOTYPE (issue 21): the one metrics script every variant goes through (never computed by hand).

collect(...) -> dict written to out/<key>/metrics.json;  table(dict) -> Chinese text written to tune.txt.

Definitions (also in the top-level README, in Chinese):
  length_mm        the net's length as KiCad's DRC measures it (probe rule): pad centre to pad centre, track +
                   arcs + the height of each via between the layers it joins.
  direct_mm        shortest 0/45/90-degree path between the two pad centres in plan view, ignoring every obstacle
                   and the board thickness: max(dx, dy) + (sqrt(2) - 1) * min(dx, dy).
  serpentine_mm    length added by serpentines = sum of (drawn length - straight replaced) over the net's blocks.
  route_mm         length_mm - serpentine_mm: the net with its serpentines pulled straight (via height included).
  detour_mm        route_mm - direct_mm: what the routing itself adds over the direct line (includes via_mm).
  serpentine_under_sdram_mm   serpentine_mm weighted by the share of each block's copper inside the SDRAM package outline.
  bus_hull_area_mm2  area of the convex hull of the centre lines of all bus copper (tracks, arcs, serpentines, via
                   centres; all three layers projected on one plane) that lies outside the two package outlines.
  bus_bbox_mm      width and height of the bounding box of the same points.
  bus_swept_area_mm2  area of the union of that same copper grown by half its width + 0.127 mm (one clearance),
                   rasterised at 0.05 mm: all layers projected ("all") and per layer. Unlike the hull it does not
                   count empty space between far-apart tracks, so it reacts to serpentines and spacing.
  channel_width_mm extent, in y (across the MCU->SDRAM direction), of the bus centre lines inside the strip between
                   the two rule areas (19 <= x <= 22): max y - min y; also per layer.
  copper_area_by_layer_mm2    sum of length * width of the bus tracks per layer (whole net, also under the packages).
"""
import collections, math
import numpy as np
import pcbnew
import lengths
from common import (NETS, REF, WINDOW, LEN_MAX, BODY, AREAS, CORRIDOR, LNUM, CLR_OUT, Lp, mm, short, in_rect, octile, track_pts)


def _hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def space(B):
    pts = []                                                # (x, y, layer, grow radius) outside both package outlines
    area = collections.defaultdict(float)
    for t in B.GetTracks():
        if not t.GetNetname().startswith("/FMC_"):
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            p = Lp(t.GetPosition())
            if not any(in_rect(p, R) for R in BODY.values()):
                for l in ("L1", "L4", "L6"):
                    pts.append((p[0], p[1], l, mm(t.GetWidth(pcbnew.F_Cu)) / 2 + CLR_OUT))
            continue
        l, w = LNUM[t.GetLayer()], mm(t.GetWidth())
        area[l] += mm(t.GetLength()) * w
        pl = track_pts(t, 0.02)
        for a, c in zip(pl, pl[1:]):
            n = max(1, int(math.dist(a, c) / 0.025))
            for i in range(n + 1):
                p = (a[0] + (c[0] - a[0]) * i / n, a[1] + (c[1] - a[1]) * i / n)
                if not any(in_rect(p, R) for R in BODY.values()):
                    pts.append((p[0], p[1], l, w / 2 + CLR_OUT))
    xy = [(round(p[0], 3), round(p[1], 3)) for p in pts]
    h = _hull(xy)
    hull_area = abs(sum(h[i][0] * h[(i + 1) % len(h)][1] - h[(i + 1) % len(h)][0] * h[i][1] for i in range(len(h)))) / 2 if len(h) >= 3 else 0.0
    xs, ys = [p[0] for p in xy], [p[1] for p in xy]
    out = {"bus_hull_area_mm2": round(hull_area, 2), "bus_bbox_mm": [round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3)],
           "bus_bbox_corners": [round(min(xs), 3), round(min(ys), 3), round(max(xs), 3), round(max(ys), 3)]}
    # swept area: raster 0.05 mm
    cell = 0.05
    x0, y0 = min(xs) - 0.5, min(ys) - 0.5
    nx, ny = int((max(xs) - x0 + 0.5) / cell) + 2, int((max(ys) - y0 + 0.5) / cell) + 2
    grids = {l: np.zeros((ny, nx), dtype=bool) for l in ("L1", "L4", "L6")}
    A = np.array([(p[0], p[1], p[3]) for p in pts]); lay = np.array([p[2] for p in pts])
    k = int(0.3 / cell) + 1
    for l, G in grids.items():
        S = A[lay == l]
        if not len(S):
            continue
        ix = ((S[:, 0] - x0) / cell).astype(int); iy = ((S[:, 1] - y0) / cell).astype(int)
        for dx in range(-k, k + 1):
            for dy in range(-k, k + 1):
                cx = (ix + dx + 0.5) * cell + x0; cy = (iy + dy + 0.5) * cell + y0
                m = (cx - S[:, 0]) ** 2 + (cy - S[:, 1]) ** 2 <= S[:, 2] ** 2
                G[np.clip(iy[m] + dy, 0, ny - 1), np.clip(ix[m] + dx, 0, nx - 1)] = True
    out["bus_swept_area_mm2"] = {"all": round(float((grids["L1"] | grids["L4"] | grids["L6"]).sum()) * cell * cell, 2),
                                 **{l: round(float(G.sum()) * cell * cell, 2) for l, G in grids.items()}}
    ch = [p for p in pts if CORRIDOR[0] <= p[0] <= CORRIDOR[1]]
    out["channel_width_mm"] = round(max(p[1] for p in ch) - min(p[1] for p in ch), 3) if ch else 0.0
    out["channel_y_range"] = [round(min(p[1] for p in ch), 3), round(max(p[1] for p in ch), 3)] if ch else None
    out["channel_width_by_layer_mm"] = {}
    for l in ("L1", "L4", "L6"):
        c2 = [p[1] for p in ch if p[2] == l]
        out["channel_width_by_layer_mm"][l] = round(max(c2) - min(c2), 3) if c2 else 0.0
    out["copper_area_by_layer_mm2"] = {l: round(v, 3) for l, v in sorted(area.items())}
    return out


def collect(key, var, info, tune, B, measured, matched, drc, can, shape, geo):
    g = lengths.geometric(B)
    pads = info["pads"]
    blocks = collections.defaultdict(list)
    for b in tune["blocks"]:
        blocks[b["net"]].append(b)
    clk = measured.get(REF)
    nets = collections.OrderedDict()
    for n in NETS:
        bl = blocks[n]
        L = measured.get(n)
        serp_mm = sum(b["gain"] for b in bl)
        direct = octile(pads["U1 " + n], pads["U2 " + n])
        d = None if L is None or clk is None else L - clk
        note = []
        if n in tune["missing"]:
            note.append("自动补线没补够，还差 %.3f mm" % tune["missing"][n])
        if d is not None and abs(d) > WINDOW + 1e-6:
            note.append("比窗口%s %.3f mm" % ("上限长" if d > 0 else "下限短", abs(d) - WINDOW))
        nets[n] = {
            "length_mm": L, "length_by_geometry_mm": round(g[n]["length"], 4),
            "delta_to_sdclk_mm": None if d is None else round(d, 4),
            "in_window": d is not None and abs(d) <= WINDOW + 1e-6 and L <= LEN_MAX,
            "vias": g[n]["vias"], "via_mm": round(g[n]["via_mm"], 4), "layers": g[n]["layers"],
            "mcu_ball": info["mcu_balls"][n], "sdram_pin": info["swap"][n][0], "sdram_ball": info["swap"][n][1],
            "direct_mm": round(direct, 4),
            "route_mm": None if L is None else round(L - serp_mm, 4),
            "detour_mm": None if L is None else round(L - serp_mm - direct, 4) + 0.0,
            "serpentine_mm": round(serp_mm, 4), "n_serpentines": len(bl), "n_humps": sum(b["humps"] + b["bumps"] for b in bl),
            "pitch_mm": sorted({b["pitch"] for b in bl}), "max_amplitude_mm": max((a for b in bl for a in b["amps"]), default=0.0),
            "amplitudes_mm": [b["amps"] for b in bl],
            "serpentine_where": ["%s %s side, (%.2f, %.2f) to (%.2f, %.2f)%s" % (b["layer"], b["side"], b["from"][0], b["from"][1], b["to"][0], b["to"][1],
                                                                              ", inside a rule area" if b["inside_area"] else "") for b in bl],
            "serpentine_under_sdram_mm": round(sum(b["gain"] * b["under_sdram"] for b in bl), 4),
            "why": var.WHY.get(n, var.WHY.get(short(n), "")), "tuning_note": "；".join(note)}
    ok = [n for n in NETS if nets[n]["length_mm"] is not None]
    deltas = {n: nets[n]["delta_to_sdclk_mm"] for n in ok}
    out_nets = {n: round(abs(v) - WINDOW, 4) for n, v in deltas.items() if abs(v) > WINDOW + 1e-6}
    tot_serp = sum(nets[n]["serpentine_mm"] for n in NETS)
    under = sum(nets[n]["serpentine_under_sdram_mm"] for n in NETS)
    totals = {
        "window_L_mm": clk, "window_mm": [None if clk is None else round(clk - WINDOW, 4), None if clk is None else round(clk + WINDOW, 4)],
        "in_window_count": sum(1 for n in NETS if nets[n]["in_window"]), "nets": len(NETS),
        "worst_delta_mm": max(deltas.values(), key=abs) if deltas else None,
        "worst_net": max(deltas, key=lambda n: abs(deltas[n])) if deltas else None,
        "out_of_window_by_mm": out_nets,
        "longest_mm": max(nets[n]["length_mm"] for n in ok) if ok else None, "shortest_mm": min(nets[n]["length_mm"] for n in ok) if ok else None,
        "total_length_mm": round(sum(nets[n]["length_mm"] for n in ok), 3),
        "total_direct_mm": round(sum(nets[n]["direct_mm"] for n in NETS), 3),
        "total_detour_mm": round(sum(nets[n]["detour_mm"] for n in ok), 3),
        "total_serpentine_mm": round(tot_serp, 3),
        "n_serpentines": sum(nets[n]["n_serpentines"] for n in NETS), "n_humps": sum(nets[n]["n_humps"] for n in NETS),
        "nets_with_serpentine": sum(1 for n in NETS if nets[n]["n_serpentines"]),
        "max_vias": max(nets[n]["vias"] for n in NETS), "total_vias": sum(nets[n]["vias"] for n in NETS),
        "nets_over_2_vias": [short(n) for n in NETS if nets[n]["vias"] > 2],
        "serpentine_under_sdram_mm": round(under, 3), "serpentine_under_sdram_share": round(under / tot_serp, 4) if tot_serp else 0.0,
        "max_abs_geometry_minus_drc_mm": round(max((abs(nets[n]["length_by_geometry_mm"] - nets[n]["length_mm"]) for n in ok), default=0.0), 5),
        "over_60mm": [short(n) for n in ok if nets[n]["length_mm"] > LEN_MAX]}
    # every DRC item must be explained: length_out_of_range = a net outside the window (expected, listed above)
    unexplained = [i for i in drc["items"] if i["type"] != "length_out_of_range"]
    s = geo["serp"]
    chk = {
        "drc": {"kicad": drc["kicad"], "unconnected": drc["unconnected"], "violations": drc["violations"], "by_type": drc["by_type"],
                "length_out_of_range_matches_out_of_window": drc["by_type"].get("length_out_of_range", 0) == len(out_nets),
                "unexplained": unexplained, "unconnected_items": drc["unconnected_items"]},
        "rule_file_canary": can,
        "rules_matched": {"per_length_rule": matched, "ok": bool(matched) and all(v == len(NETS) for v in matched.values())},
        "track_shape": shape,
        "geometry": {"clearance_violations": geo["clearance_violations"], "path_problems": geo["path_problems"], "min_gap_all": geo["min_gap_all"],
                     "off_grid_exact": geo["off_grid_exact"], "thin_outside_mm": geo["thin_outside_mm"], "via_turn_90_or_more": geo["via_turn_90_or_more"],
                     "arcs": s["arcs"], "arc_radii_mm": s["radii"], "arc_sweep_deg": [s["sweep_min"], s["sweep_max"]]},
        "serpentine_clearances": {"limits_used": tune["clear"], "smallest_to_other_net": s["min_gap_to_other_net"],
                                  "smallest_to_rule_area_edge_from_outside": s["min_gap_to_area_edge_outside"],
                                  "shortest_straight_between_bend_and_arc": s["lead_min"], "leads_below_0.35": s["leads_below_0.35"],
                                  "pairs_below_0.3": s["pairs_below_0.3"]},
        "conventions": info["breakout_notes"], "ball_check": info["ball_notes"], "tuning_notes": tune["notes"]}
    return {"variant": key, "description": var.DESCRIPTION, "lanes_swapped": info["lanes_swapped"], "pitch": tune["pitch"],
            "nets": nets, "totals": totals, "space": space(B), "checks": chk}


def table(r):
    """Chinese text summary (tune.txt)."""
    t, sp, ck = r["totals"], r["space"], r["checks"]
    f = lambda v, p="%.3f": "—" if v is None else p % v
    o = ["方案 %s：%s" % (r["variant"], r["description"]), ""]
    o.append("| 网络 | MCU 球 → SDRAM | 长度 (DRC) | 比 SDCLK | 窗口内 | 过孔 | 各层长度 | 直连最短 | 不算蛇形的走线 | 绕远 | 蛇形补的 | 蛇形处数 / 弯数 | 腿间距 | 最大摆幅 | SDRAM 下的蛇形 |")
    o.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for n, d in r["nets"].items():
        o.append("| %s | %s → %s %s | %s | %s | %s | %d | %s | %.3f | %s | %s | %.3f | %d / %d | %s | %s | %.3f |" % (
            short(n), d["mcu_ball"], d["sdram_ball"], d["sdram_pin"], f(d["length_mm"]), f(d["delta_to_sdclk_mm"], "%+.3f"), "是" if d["in_window"] else "否",
            d["vias"], "，".join("%s %.2f" % kv for kv in d["layers"].items()), d["direct_mm"], f(d["route_mm"]), f(d["detour_mm"]), d["serpentine_mm"],
            d["n_serpentines"], d["n_humps"], "/".join("%.2f" % p for p in d["pitch_mm"]) or "—", ("%.2f" % d["max_amplitude_mm"]) if d["n_serpentines"] else "—",
            d["serpentine_under_sdram_mm"]))
    o += ["", "单位 mm。长度由 KiCad 的 DRC 量（探针规则），含过孔高度。"]
    o.append("窗口：SDCLK = %s，允许 %s 到 %s。在窗口内 %d / %d；离 SDCLK 最远的是 %s（%s）。" % (
        f(t["window_L_mm"]), f(t["window_mm"][0]), f(t["window_mm"][1]), t["in_window_count"], t["nets"], short(t["worst_net"] or ""), f(t["worst_delta_mm"], "%+.3f")))
    if t["out_of_window_by_mm"]:
        o.append("超出窗口的：%s。" % "，".join("%s 超 %.3f" % (short(n), v) for n, v in t["out_of_window_by_mm"].items()))
    o.append("绕远合计 %.3f，蛇形补的合计 %.3f（%d 处、%d 个弯，%d 根线有蛇形），其中在 SDRAM 封装下面的占 %.1f%%。过孔最多 %d 个/根，共 %d 个。" % (
        t["total_detour_mm"], t["total_serpentine_mm"], t["n_serpentines"], t["n_humps"], t["nets_with_serpentine"],
        100 * t["serpentine_under_sdram_share"], t["max_vias"], t["total_vias"]))
    o.append("脚本按几何算的长度和 DRC 量的最多差 %.4f mm。" % t["max_abs_geometry_minus_drc_mm"])
    o += ["", "占用的空间（两颗封装外形以外的总线铜，三层叠在一起看）："]
    o.append("- 凸包面积 %.2f mm²；外包矩形 %.2f × %.2f mm。" % (sp["bus_hull_area_mm2"], sp["bus_bbox_mm"][0], sp["bus_bbox_mm"][1]))
    a = sp["bus_swept_area_mm2"]
    o.append("- 扫过的面积（线宽加一个间距）：三层合并 %.2f mm²；L1 %.2f，L4 %.2f，L6 %.2f。" % (a["all"], a["L1"], a["L4"], a["L6"]))
    w = sp["channel_width_by_layer_mm"]
    o.append("- 两个规则区之间那一条（x 19–22）里，总线上下占 %.3f mm（y %s 到 %s）；L1 %.3f，L4 %.3f，L6 %.3f。" % (
        sp["channel_width_mm"], f(sp["channel_y_range"][0], "%.2f"), f(sp["channel_y_range"][1], "%.2f"), w["L1"], w["L4"], w["L6"]))
    o += ["", "检查："]
    d = ck["drc"]
    o.append("- DRC（KiCad %s）：未连接 %d，违规 %d（%s）。%s" % (
        d["kicad"], d["unconnected"], d["violations"], "，".join("%s %d" % kv for kv in d["by_type"].items()) or "无",
        "除长度超窗外没有别的。" if not d["unexplained"] else "没有解释的 %d 条：%s" % (len(d["unexplained"]), "；".join("%s @ (%.2f, %.2f)" % (i["type"], i["at"][0], i["at"][1]) for i in d["unexplained"][:12]))))
    o.append("- 规则生效检查：%s。长度规则各匹配到的网络数：%s（应为 19）。" % ("OK" if ck["rule_file_canary"]["ok"] else "失败：" + ck["rule_file_canary"]["text"],
                                                            "，".join("%s %d" % kv for kv in ck["rules_matched"]["per_length_rule"].items())))
    s = ck["track_shape"]
    o.append("- track_shape.py：非 45° %s，阶梯线 %s，小倒角直角 %s，2 mm 内 3 个以上折弯 %s，短于 0.1 的线段 %s（它不认识圆弧）。" % (
        s["off-grid"], s["staircase"], s["sharp"], s["crowded"], s["tiny"]))
    for l in s["lines"][:12]:
        o.append("    " + l)
    gm = ck["geometry"]
    if s["off-grid"]:
        o.append("  （track_shape.py 先把坐标取整到 1 µm 再算角度，斜线上很短的蛇形直腿会被它算偏 0.2–0.4°；按板文件里的纳米坐标重算，偏离 0°/45°/90° 超过 0.05° 的线段是 %d 段。）" % len(gm["off_grid_exact"]))
    o.append("- 脚本从板文件量的：间距不够的 %d 处，网络不是一条从球到球的单线的 %d 处；不同网络之间最近 %s。" % (
        len(gm["clearance_violations"]), len(gm["path_problems"]),
        "—" if not gm["min_gap_all"] else "%.3f（%s 对 %s，%s）" % (gm["min_gap_all"]["gap"], gm["min_gap_all"]["net"], gm["min_gap_all"]["other"], gm["min_gap_all"]["layer"])))
    if gm["thin_outside_mm"]:
        o.append("- 规则区外的 0.09 线（每根）：%s。" % "，".join("%s %.2f" % kv for kv in gm["thin_outside_mm"].items()))
    if gm["via_turn_90_or_more"]:
        o.append("- 过孔两侧走向成 90° 以上的：%s。" % "，".join("%s (%.2f, %.2f) %.0f°" % (v["net"], v["at"][0], v["at"][1], v["turn"]) for v in gm["via_turn_90_or_more"]))
    sc = ck["serpentine_clearances"]
    if gm["arcs"]:
        m, a2 = sc["smallest_to_other_net"], sc["smallest_to_rule_area_edge_from_outside"]
        o.append("- 蛇形：圆弧 %d 个，半径 %s，圆心角 %s°–%s°；离别的网络最近 %s；规则区外的蛇形离规则区边最近 %s；拐点到第一个圆弧最短 %s（短于 0.35 的 %d 处）。" % (
            gm["arcs"], "/".join("%.3f" % x for x in gm["arc_radii_mm"]), gm["arc_sweep_deg"][0], gm["arc_sweep_deg"][1],
            "—" if not m else "%.3f（%s 对 %s，%s，在 %.2f, %.2f）" % (m["gap"], m["net"], m["other"], m["layer"], m["at"][0], m["at"][1]),
            "—" if not a2 else "%.3f（%s）" % (a2["gap"], a2["net"]), f(sc["shortest_straight_between_bend_and_arc"]), len(sc["leads_below_0.35"])))
        o.append("  画的时候守的限制：离拐点 %.3f，离别的铜 %.3f，离规则区边 %.3f。" % (sc["limits_used"]["end"], sc["limits_used"]["clr"], sc["limits_used"]["area_gap"]))
    for c in ck["conventions"]:
        o.append("- 没照约定：" + c)
    for c in ck["tuning_notes"]:
        o.append("- 补线备注：" + c)
    o += ["", "每根线为什么这样走："]
    for n, d in r["nets"].items():
        o.append("- %s：%s%s" % (short(n), d["why"], ("（" + d["tuning_note"] + "）") if d["tuning_note"] else ""))
    o += ["", "构建用时 %s 秒。" % r.get("build_seconds", "—")]
    return "\n".join(o) + "\n"
