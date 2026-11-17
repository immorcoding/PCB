"""PROTOTYPE (issue 15): how much room each net has beside its straight runs for length compensation (RTE-2).

    D:\\KiCad\\bin\\python.exe room.py <variant dir>     -> room.txt (Chinese table), room.json

For every straight segment that lies wholly outside the rule areas (those are the 0.1016 mm segments)
and is at least 1 mm long, the script walks along it in 0.05 mm steps and, on each side, pushes a
point sideways until a track of the same width there would be closer than 0.19 mm to other copper
on that layer (tracks of other nets, vias, pads on L1), closer than 0.127 mm to a rule area, or within
0.254 mm of the board edge. That distance is the largest centre-line swing (amplitude) at that spot.

Gain estimate: the run is cut into 1 mm pieces (one hump of radius 0.25 mm is 4 r = 1 mm long); a
piece whose amplitude A is at least 0.5 mm adds 2 A - 1.717 r. Two nets that face each other across
the same gap are both credited with it, so the figures are upper bounds, not a plan.
All numbers are read from the board file (PROC-14).
"""
import json, math, os, sys
import pcbnew

NAME = "lentune"
CLR, EDGE, R, PERIOD, A_MIN, A_CAP, END, AREA_GAP = 0.19, 0.254, 0.25, 1.0, 0.5, 2.0, 0.35, 0.127   # the same keep-offs as meander.py
LNUM = {pcbnew.F_Cu: "L1", pcbnew.In3_Cu: "L4"}
mm = pcbnew.ToMM
Lp = lambda v: (mm(v.x) - 100, mm(v.y) - 100)
COMPASS = ["东", "东南", "南", "西南", "西", "西北", "北", "东北"]


def d_seg(p, a, c):
    vx, vy = c[0] - a[0], c[1] - a[1]
    L2 = vx * vx + vy * vy
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L2))
    return math.hypot(p[0] - a[0] - t * vx, p[1] - a[1] - t * vy)


def main(vdir):
    B = pcbnew.LoadBoard(os.path.join(vdir, NAME + ".kicad_pcb"))
    areas, tracks, rounds = [], [], []            # rects; (net, layer, a, c, w); (net, layer or None, centre, radius)
    for z in B.Zones():
        if z.GetIsRuleArea():
            bb = z.GetBoundingBox()
            areas.append(Lp(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop())) + Lp(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom())))
    eb = B.GetBoardEdgesBoundingBox()
    board = Lp(pcbnew.VECTOR2I(eb.GetLeft(), eb.GetTop())) + Lp(pcbnew.VECTOR2I(eb.GetRight(), eb.GetBottom()))
    for t in B.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            rounds.append((t.GetNetname(), None, Lp(t.GetPosition()), mm(t.GetWidth(pcbnew.F_Cu)) / 2))
        elif t.Type() == pcbnew.PCB_ARC_T:
            tracks.append((t.GetNetname(), t.GetLayer(), Lp(t.GetStart()), Lp(t.GetMid()), mm(t.GetWidth()), True))
            tracks.append((t.GetNetname(), t.GetLayer(), Lp(t.GetMid()), Lp(t.GetEnd()), mm(t.GetWidth()), True))
        else:
            tracks.append((t.GetNetname(), t.GetLayer(), Lp(t.GetStart()), Lp(t.GetEnd()), mm(t.GetWidth()), False))
    for fp in B.GetFootprints():
        for p in fp.Pads():
            rounds.append((p.GetNetname(), pcbnew.F_Cu, Lp(p.GetPosition()), mm(p.GetSizeX()) / 2))

    def clear(q, net, layer, half):
        if not (board[0] + EDGE + half <= q[0] <= board[2] - EDGE - half and board[1] + EDGE + half <= q[1] <= board[3] - EDGE - half):
            return False
        g = half + (AREA_GAP if layer != -1 else 0)         # layer -1: "does the segment itself touch an area"
        for x0, y0, x1, y1 in areas:
            if x0 - g < q[0] < x1 + g and y0 - g < q[1] < y1 + g:
                return False
        for n, l, a, c, w, _ in tracks:
            if n != net and l == layer and d_seg(q, a, c) < w / 2 + half + CLR:
                return False
        for n, l, c, r in rounds:
            if n != net and l in (None, layer) and math.dist(q, c) < r + half + CLR:
                return False
        return True

    need = {}
    lj = os.path.join(vdir, "lengths.json")
    if os.path.exists(lj):
        need = {n: -v["to_longest"] for n, v in json.load(open(lj, encoding="utf-8"))["nets"].items()}
    rows, js = [], {}
    for net, layer, a, c, w, is_arc in tracks:
        L = math.dist(a, c)
        if is_arc or net == "GND" or layer not in LNUM or L < 1.0:
            continue
        if any(not clear((a[0] + (c[0] - a[0]) * k / 20, a[1] + (c[1] - a[1]) * k / 20), "", -1, w / 2) for k in range(21)):
            continue                                # the segment itself touches a rule area: no tuning there
        ux, uy = (c[0] - a[0]) / L, (c[1] - a[1]) / L
        sides = []
        for nx, ny in ((uy, -ux), (-uy, ux)):
            prof, s = [], END
            while s <= L - END + 1e-9:              # stay 0.35 mm away from the bend at each end
                p = (a[0] + ux * s, a[1] + uy * s)
                d = 0.0
                while d < A_CAP and clear((p[0] + nx * (d + 0.01), p[1] + ny * (d + 0.01)), net, layer, w / 2):
                    d += 0.01
                prof.append(d); s += 0.05
            n_h = int(len(prof) * 0.05 / PERIOD + 1e-6)
            amps = [min(prof[int(i * PERIOD / 0.05): int((i + 1) * PERIOD / 0.05) + 1]) for i in range(n_h)]
            gain = sum(2 * A - 1.717 * R for A in amps if A >= A_MIN)
            gain05 = sum(2 * A_MIN - 1.717 * R for A in amps if A >= A_MIN)
            name = COMPASS[int(round(math.degrees(math.atan2(ny, nx)) / 45)) % 8]
            sides.append({"side": name, "min": round(min(prof), 2), "max": round(max(prof), 2), "humps": [round(A, 2) for A in amps],
                          "gain": round(gain, 2), "gain_a05": round(gain05, 2)})
        rows.append((net, LNUM[layer], a, c, L, sides))
        js.setdefault(net, []).append({"layer": LNUM[layer], "from": [round(v, 3) for v in a], "to": [round(v, 3) for v in c],
                                       "length": round(L, 3), "sides": sides})
    order = lambda n: (0, 0) if "CLK" in n else (1, int("".join(ch for ch in n if ch.isdigit()) or 0))
    rows.sort(key=lambda r: (order(r[0]), -r[4]))
    out = ["| 网络 | 层 | 直线段（起点 → 终点） | 段长 | 侧 | 这一侧能摆多宽（最小–最大） | 每 1 mm 一个弯能摆的幅度 | 最多能补 | 摆幅只用 0.5 时能补 |",
           "|---|---|---|---|---|---|---|---|---|"]
    best = {}
    for net, lay, a, c, L, sides in rows:
        for sd in sides:
            out.append("| %s | %s | (%.2f, %.2f) → (%.2f, %.2f) | %.2f | %s | %.2f–%.2f%s | %s | %.2f | %.2f |" % (
                net.replace("/", ""), lay, a[0], a[1], c[0], c[1], L, sd["side"], sd["min"], sd["max"],
                "（2.0 封顶）" if sd["max"] >= A_CAP - 0.011 else "", " ".join("%.2f" % A for A in sd["humps"]) or "—", sd["gain"], sd["gain_a05"]))
        b = best.setdefault(net, {"gain": 0.0, "gain_a05": 0.0})
        b["gain"] += max(sd["gain"] for sd in sides); b["gain_a05"] += max(sd["gain_a05"] for sd in sides)
    out += ["", "| 网络 | 补到最长那根要加 | 所有直线段取较宽的一侧，最多能补 | 摆幅只用 0.5 时能补 | 够不够 |", "|---|---|---|---|---|"]
    for net in sorted(need, key=order):
        b = best.get(net, {"gain": 0.0, "gain_a05": 0.0})
        ok = "不用补" if need[net] < 0.005 else ("够（0.5 就够）" if b["gain_a05"] >= need[net] else ("够，但摆幅要大于 0.5" if b["gain"] >= need[net] else "不够"))
        out.append("| %s | %.3f | %.2f | %.2f | %s |" % (net.replace("/", ""), need[net], b["gain"], b["gain_a05"], ok))
        js.setdefault(net, [])
    out += ["", "口径：只看整段都在规则区外、长度不小于 1 mm 的直线段；两端各离拐点 0.35 mm。“能摆多宽”是蛇形中心线离原线的最大距离，",
            "已经扣掉到别的铜 0.19 mm、到规则区边 0.127 mm、到板边 0.254 mm（和 meander.py 守的一样）。估算按半径 0.25 mm、每 1 mm 一个弯，一个弯多出 2 × 摆幅 − 0.43 mm。",
            "面对面的两根线会把同一块空地各算一次，所以“最多能补”是上限，不是方案；单位 mm。"]
    open(os.path.join(vdir, "room.txt"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    json.dump({"need_to_longest": need, "segments": js, "total": best}, open(os.path.join(vdir, "room.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1])
