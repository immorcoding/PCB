"""PROTOTYPE (issue 53, throwaway): via arrays where part of a DDR3 byte lane changes between L1 and L6.

Arrangements: A two-row stagger with every via in its own lane slot; B vias moved onto the guard-strip
positions; C chevron about the DQS pair; S one slanted line (numbers only, not drawn).
Each is worked for three real cases taken from the RK3568 ball map (see where.py).

Run: python draw.py   -> writes via_array_variants.html and metrics.json next to this file, prints the checks.
Frame: x along the lane from the SoC ball-field edge (0) to the DRAM ball-field edge (7.5), y across. mm, to scale.
Lines are drawn straight in their lane slots; the spread out of the ball fields is not drawn.
"""
import json
import math
import os

W = 0.15                  # outer-layer 50 ohm
DW, DG = 0.104, 0.15      # DQS pair
GS, SS, GW = 0.15, 0.30, 0.40   # guard-signal gap, DQ-DQ gap, guard strip width (issue 47)
PAD, DRILL = 0.40, 0.20   # layer-change via outside the ball field (issue 48)
VV = 0.80                 # signal via to signal via, centres (issue 48)
VG = 0.60                 # via to via of another net, centres (pad edge to pad edge 0.20)
PAIR_VV = 0.60            # the two vias of one pair (issue 37)
RET = 0.635               # return via within 25 mil
APAD = 0.60               # plane clearance hole: 0.8 centres leave 0.2 of copper
HALO = PAD / 2 + GS       # pour pulls back 0.15 from a signal pad
POUR_MIN = 0.25           # a strip narrower than this is counted as cut
D = 7.5
RULE_SOC, RULE_RAM = 1.7, 2.3
X0 = RULE_SOC + 0.15 + PAD / 2   # first via row: pad edge 0.15 past the rule-area edge
XA, XB = 0.9, 6.9         # drawn window
PATTERN = "WSSWSSWDWSSWSSWSW"

# (key, title, nets in lane order top to bottom with the DQS pair at the 'D' slot, nets that change, from, to)
CASES = [
    ("b1", "情形 1 · 字节组 1 走 L6：外圈的 3 根 DQ 和 DQS 对在球区外换层",
     "内圈 6 根（DM1、DQ10、11、13、14、15）在球区里已经下到 L6，从过孔阵中间穿过。字节组 2 的数目相同。",
     ["DQ8", "DQ15", "DQ9", "DQ11", "DQS1", "DQ12", "DQ13", "DQ10", "DQ14", "DM1"],
     {"DQ8", "DQ9", "DQ12", "DQS1"}, "L1", "L6"),
    ("b0", "情形 2 · 字节组 0 走 L6（最坏情形）：外圈的 7 根 DQ 和 DQS 对在球区外换层",
     "内圈只有 DQ7、DM0 两根已在 L6。字节组 3 的数目相同。这是过孔最多的情形，用来看排法撑不撑得住。",
     ["DQ1", "DQ3", "DQ4", "DQ6", "DQS0", "DQ0", "DQ2", "DQ5", "DQ7", "DM0"],
     {"DQ1", "DQ3", "DQ4", "DQ6", "DQ0", "DQ2", "DQ5", "DQS0"}, "L1", "L6"),
    ("b0up", "情形 3 · 字节组 0 走 L1：内圈的 DQ7、DM0 从 L6 回到 L1",
     "其余 9 根从球区出来就一直在 L1。这两根各有两个过孔，同组别的线没有过孔。",
     ["DQ1", "DQ3", "DQ4", "DQ6", "DQS0", "DQ0", "DQ2", "DQ5", "DQ7", "DM0"],
     {"DQ7", "DM0"}, "L6", "L1"),
]
VARIANTS = [("A", "A · 两排交错，过孔在线自己的位置上"),
            ("B", "B · 过孔挪到地铜条的位置上"),
            ("C", "C · 人字形，过孔在线自己的位置上"),
            ("D", "D · 同 A，但每排最多 2 个过孔"),
            ("S", "一条斜线")]
DRAWN = ("A", "B", "C", "D")


def lane():
    objs, y, prev = [], 0.0, None
    for c in PATTERN:
        if prev is not None:
            y += GS if (c == "W" or prev == "W") else SS
        wid = GW if c == "W" else (W if c == "S" else 2 * DW + DG)
        objs.append((c, y + wid / 2, wid))
        y += wid
        prev = c
    return [(c, yc - y / 2, wid) for c, yc, wid in objs], y


def base(n):
    return n[:-2] if n.endswith(("_P", "_N")) else n


def seg_dist(p, a, b):
    ax, ay, bx, by = *a, *b
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def spots(u, x, ys=None):
    n, yc, c = u
    if c == "D":
        return [(n + "_P", x, yc - PAIR_VV / 2), (n + "_N", x, yc + PAIR_VV / 2)]
    return [(n, x, yc if ys is None else ys)]


def clash(v, others):
    return any(base(v[0]) != base(o[0]) and math.dist(v[1:], o[1:]) < VV - 1e-9 for o in others)


def place(case, var):
    key, _, _, nets, chg, src, dst = case
    objs, width = lane()
    strips = [yc for c, yc, _ in objs if c == "W"]
    sigs = [(n, yc, c) for n, (c, yc, _) in zip(nets, [o for o in objs if o[0] != "W"])]
    units = [u for u in sigs if u[0] in chg]      # one unit = one single line or one pair
    ypair = next(yc for n, yc, c in sigs if c == "D")
    vias, step = [], None

    def all_ok(xs):
        v = []
        for u, x in zip(units, xs):
            for sp in spots(u, x):
                if clash(sp, v):
                    return None
                v.append(sp)
        return v

    if var == "A":
        for step in (0.70, 0.75, 0.80):
            vias = all_ok([X0 + (i % 2) * step for i in range(len(units))])
            if vias:
                break
    elif var in ("C", "S"):
        for step in (1.0, 1.25, 0.70 / 0.45, 2.0):
            if var == "S":
                xs = [X0 + step * (u[1] - units[0][1]) for u in units]
            else:
                near = min(abs(u[1] - ypair) for u in units)
                xs = [X0 + step * (abs(u[1] - ypair) - near) for u in units]
            vias = all_ok(xs)
            if vias:
                break
    elif var == "D":   # like A, but no row holds more than two vias (Rockchip: at most 2 DQ vias side by side)
        step, rows = 0.70, {}
        for u in sorted(units, key=lambda u: (u[2] != "D", u[1])):
            for row in range(12):
                sp = spots(u, X0 + row * step)
                if rows.get(row, 0) + len(sp) <= 2 and not any(clash(v, vias) for v in sp):
                    vias += sp
                    rows[row] = rows.get(row, 0) + len(sp)
                    break
    else:   # B: each single line steps sideways onto a neighbouring guard strip; rows 0.80 apart, lowest row that fits
        step = 0.80
        for u in sorted(units, key=lambda u: (u[2] != "D", u[1])):
            opts = [None] if u[2] == "D" else [s for s in strips if abs(s - u[1]) < 0.45]
            for row in range(6):
                hit = next((sp for ys in opts for sp in [spots(u, X0 + row * step, ys)] if not any(clash(v, vias) for v in sp)), None)
                if hit:
                    vias += hit
                    break
    assert vias and len(vias) == sum(2 if u[2] == "D" else 1 for u in units), (key, var)

    # copper: every line as (net, layer, width, points)
    vxy = {v[0]: v[1:] for v in vias}
    lines = []
    for n, yc, c in sigs:
        if c == "S":
            if n in chg:
                x, y = vxy[n]
                j = abs(y - yc)
                lines.append((n, src, W, [(XA, yc), (x - j, yc), (x, y)]))
                lines.append((n, dst, W, [(x, y), (x + j, yc), (XB, yc)]))
            else:
                lines.append((n, dst, W, [(XA, yc), (XB, yc)]))
            continue
        for tag, sg in (("_P", -1), ("_N", 1)):
            yl = yc + sg * (DW + DG) / 2
            if n in chg:
                x, y = vxy[n + tag]
                f = abs(y - yl)
                lines.append((n + tag, src, DW, [(XA, yl), (x - 0.10 - f, yl), (x - 0.10, y), (x, y)]))
                lines.append((n + tag, dst, DW, [(x, y), (x + 0.10, y), (x + 0.10 + f, yl), (XB, yl)]))
            else:
                lines.append((n + tag, dst, DW, [(XA, yl), (XB, yl)]))

    # return vias on the guard strips: reuse one within RET, else a new one 0.60 away, incoming side first
    gnd, noret = [], []
    for n, x, y in sorted(vias, key=lambda v: v[1]):
        if any(math.dist((x, y), g) <= RET for g in gnd):
            continue
        done = False
        for ys in sorted(strips, key=lambda s: abs(s - y)):
            dy = abs(ys - y)
            if dy > VG:
                break
            dx = math.sqrt(VG * VG - dy * dy) + 0.002
            for cand in ((x - dx, ys), (x + dx, ys)):
                if all(math.dist(cand, v[1:]) >= VG - 1e-9 for v in vias) and \
                        all(math.dist(cand, g) >= VG - 1e-9 for g in gnd) and \
                        all(min(seg_dist(cand, a, b) for a, b in zip(ln[3], ln[3][1:]))
                            >= PAD / 2 + ln[2] / 2 + 0.15 - 1e-6 for ln in lines):
                    gnd.append(cand)
                    done = True
                    break
            if done:
                break
        if not done:
            noret.append(n)

    vv = [math.dist(a[1:], b[1:]) for i, a in enumerate(vias) for b in vias[i + 1:] if base(a[0]) != base(b[0])]
    ret = [min(math.dist(v[1:], g) for g in gnd) if gnd else 9 for v in vias]
    tr = [min(seg_dist(v[1:], a, b) for a, b in zip(ln[3], ln[3][1:])) - PAD / 2 - ln[2] / 2
          for v in vias for ln in lines if base(ln[0]) != base(v[0])]
    neck, cut, cuts = GW, 0.0, 0
    for ys in strips:
        x, was = XA, False
        while x < XB:
            lo, hi = ys - GW / 2, ys + GW / 2
            for n, vx, vy in vias:
                h2 = HALO * HALO - (x - vx) ** 2
                if h2 > 0:
                    r = math.sqrt(h2)
                    if abs(vy - ys) < 1e-6:
                        lo = hi
                    elif vy < ys:
                        lo = max(lo, vy + r)
                    else:
                        hi = min(hi, vy - r)
            wdt = max(0.0, hi - lo)
            if wdt < POUR_MIN:
                cut += 0.01
                cuts += not was
                was = True
            else:
                neck = min(neck, wdt)
                was = False
            x += 0.01
    xlo = min(v[1] for v in vias) - PAD / 2
    xhi = max(v[1] for v in vias) + PAD / 2
    jog = max(abs(v[2] - yc) for v in vias for n, yc, c in sigs if n == v[0]) if any(c == "S" and n in chg for n, yc, c in sigs) else 0
    m = {"case": key, "var": var, "sig_vias": len(vias), "gnd_vias": len(gnd), "step": round(step, 2),
         "rows": len({round(v[1], 3) for v in vias}), "length": round(xhi - xlo, 2), "x_end": round(xhi, 2),
         "left_straight": round(D - RULE_RAM - xhi, 2), "min_vv": round(min(vv), 3) if vv else None,
         "max_ret": round(max(ret), 3), "no_return": noret, "min_pad_track": round(min(tr), 3),
         "strip_neck": round(neck, 3), "strip_cuts": cuts, "strip_cut_mm": round(cut, 2), "jog": round(jog, 3)}
    m["fails"] = [t for t, bad in (
        ("信号过孔中心距 < 0.8", vv and min(vv) < VV - 1e-9),
        ("有信号过孔 0.635 内没有地过孔", max(ret) > RET or noret),
        ("过孔盘到别的线 < 0.15", min(tr) < 0.15 - 1e-6),
        ("伸进颗粒规则区", xhi > D - RULE_RAM)) if bad]
    return dict(width=width, vias=vias, gnd=gnd, lines=lines, m=m)


COL = {"L1": "#e0564f", "L6": "#5b93e6", "dqs": "#f2b134", "pour": "#1d5a53", "bg": "#10161c", "gv": "#7fd6c8", "sv": "#f4f1e8"}


def panel(p, layer):
    s = 66
    h = p["width"] + 1.0
    o = [f'<svg viewBox="{XA * s:.0f} {-h / 2 * s:.0f} {(XB - XA) * s:.0f} {h * s:.0f}" xmlns="http://www.w3.org/2000/svg" '
         f'role="img" aria-label="{layer} 层" style="width:100%;background:{COL["bg"]}">']
    lines = [ln for ln in p["lines"] if ln[1] == layer]
    o.append(f'<rect x="{XA * s}" y="{-(p["width"] / 2 + 0.25) * s:.1f}" width="{(XB - XA) * s}" '
             f'height="{(p["width"] + 0.5) * s:.1f}" fill="{COL["pour"]}"/>')
    for n, _, w, pts in lines:
        d = " ".join(f"{x * s:.1f},{y * s:.1f}" for x, y in pts)
        o.append(f'<polyline points="{d}" fill="none" stroke="{COL["bg"]}" stroke-width="{(w + 2 * GS) * s:.2f}" stroke-linejoin="round"/>')
    for n, x, y in p["vias"]:
        o.append(f'<circle cx="{x * s:.1f}" cy="{y * s:.1f}" r="{HALO * s:.2f}" fill="{COL["bg"]}"/>')
    for x, lab, anc, dx in ((RULE_SOC, "SoC 规则区边", "start", 4), (D - RULE_RAM, "颗粒规则区边", "end", -4)):
        o.append(f'<line x1="{x * s}" y1="{-h / 2 * s}" x2="{x * s}" y2="{h / 2 * s}" stroke="#9fb0c0" stroke-dasharray="6 5"/>'
                 f'<text x="{x * s + dx}" y="{-h / 2 * s + 13}" fill="#c5d2de" font-size="12" text-anchor="{anc}">{lab}</text>')
    for n, _, w, pts in lines:
        d = " ".join(f"{x * s:.1f},{y * s:.1f}" for x, y in pts)
        col = COL["dqs"] if n.startswith("DQS") else COL[layer]
        o.append(f'<polyline points="{d}" fill="none" stroke="{col}" stroke-width="{w * s:.2f}" stroke-linejoin="round">'
                 f'<title>{n}，{w} mm，{layer}</title></polyline>')
        if not n.endswith("_N"):
            lab = base(n)
            if pts[0][0] == XA:
                o.append(f'<text x="{XA * s + 3}" y="{pts[0][1] * s - 6:.1f}" fill="#c5d2de" font-size="10">{lab}</text>')
            else:
                o.append(f'<text x="{XB * s - 32}" y="{pts[-1][1] * s - 6:.1f}" fill="#c5d2de" font-size="10">{lab}</text>')
    for x, y in p["gnd"]:
        o.append(f'<circle cx="{x * s:.1f}" cy="{y * s:.1f}" r="{PAD / 2 * s:.2f}" fill="{COL["gv"]}"><title>回流地过孔</title></circle>'
                 f'<circle cx="{x * s:.1f}" cy="{y * s:.1f}" r="{DRILL / 2 * s:.2f}" fill="{COL["bg"]}"/>')
    for n, x, y in p["vias"]:
        o.append(f'<circle cx="{x * s:.1f}" cy="{y * s:.1f}" r="{APAD / 2 * s:.2f}" fill="none" stroke="#c5d2de" '
                 f'stroke-width="1" stroke-dasharray="3 3"/>'
                 f'<circle cx="{x * s:.1f}" cy="{y * s:.1f}" r="{PAD / 2 * s:.2f}" fill="{COL["sv"]}"><title>{n} 换层过孔</title></circle>'
                 f'<circle cx="{x * s:.1f}" cy="{y * s:.1f}" r="{DRILL / 2 * s:.2f}" fill="{COL["bg"]}"/>')
    y0 = h / 2 * s - 10
    o.append(f'<line x1="{(XB - 1.2) * s}" y1="{y0}" x2="{(XB - 0.2) * s}" y2="{y0}" stroke="#fff" stroke-width="2"/>'
             f'<text x="{(XB - 1.2) * s}" y="{y0 - 5}" fill="#fff" font-size="12">1 mm</text>'
             f'<text x="{XA * s + 6}" y="{y0}" fill="#fff" font-size="15" font-weight="600">{layer}</text></svg>')
    return "\n".join(o)


def evb1_block(here):
    path = os.path.join(here, "evb1_via_array.json")
    note = os.path.join(here, "evb1_note.html")
    text = open(note, encoding="utf-8").read() if os.path.exists(note) else ""
    if not os.path.exists(path):
        return text or "<p>官方板的实测数据还没有放进来。</p>"
    e = json.load(open(path, encoding="utf-8"))
    pts = [(v["u"], v["v"]) for v in e["vias"] if v["kind"] == "sig" and math.hypot(v["u"], v["v"]) < 2.5]
    u0, u1 = min(q[0] for q in pts) - 1.3, max(q[0] for q in pts) + 1.3   # window: the outside via group only
    v0, v1 = min(q[1] for q in pts) - 1.1, max(q[1] for q in pts) + 1.1
    s = 66
    out = []
    for layer, col in (("TOP", COL["L1"]), ("BOTTOM", COL["L6"])):
        o = [f'<svg viewBox="{u0 * s:.0f} {v0 * s:.0f} {(u1 - u0) * s:.0f} {(v1 - v0) * s:.0f}" role="img" '
             f'aria-label="EVB1 {layer}" xmlns="http://www.w3.org/2000/svg" style="width:100%;background:{COL["bg"]}">']
        if layer == "TOP":
            for q in e.get("pads", []):
                o.append(f'<circle cx="{q["u"] * s:.1f}" cy="{q["v"] * s:.1f}" r="{q["d"] / 2 * s:.1f}" fill="#6b5a2e"/>')
        for t in e["tracks"]:
            if t["layer"] != layer:
                continue
            d = " ".join(f"{x * s:.1f},{y * s:.1f}" for x, y in t["pts"])
            if t["width"] > 0.3:
                continue   # power tracks hide the lane
            c = COL["gv"] if t["net"].upper() in ("GND", "VSS") else (COL["dqs"] if "DQS" in t["net"] else col)
            o.append(f'<polyline points="{d}" fill="none" stroke="{c}" stroke-width="{t["width"] * s:.2f}" '
                     f'stroke-linejoin="round" stroke-linecap="round"><title>{t["net"]}</title></polyline>')
        for v in e["vias"]:
            c = {"gnd": COL["gv"], "sig": COL["sv"]}.get(v["kind"], "#6f7b85")
            o.append(f'<circle cx="{v["u"] * s:.1f}" cy="{v["v"] * s:.1f}" r="{v["pad"] / 2 * s:.2f}" fill="{c}">'
                     f'<title>{v["net"]}</title></circle><circle cx="{v["u"] * s:.1f}" cy="{v["v"] * s:.1f}" '
                     f'r="{v["drill"] / 2 * s:.2f}" fill="{COL["bg"]}"/>')
        o.append(f'<rect x="{u0 * s}" y="{v0 * s}" width="{(u1 - u0) * s}" height="24" fill="{COL["bg"]}"/>'
                 f'<line x1="{(u1 - 1.2) * s}" y1="{v0 * s + 16}" x2="{(u1 - 0.2) * s}" y2="{v0 * s + 16}" stroke="#fff" stroke-width="2"/>'
                 f'<text x="{(u1 - 1.2) * s - 6}" y="{v0 * s + 17}" fill="#fff" font-size="12" text-anchor="end">1 mm</text>'
                 f'<text x="{u0 * s + 6}" y="{v0 * s + 17}" fill="#fff" font-size="15" font-weight="600">{layer}</text></svg>')
        out.append("\n".join(o))
    return f'{text}<div class="two">{out[0]}{out[1]}</div>'


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    allm, body = [], []
    for case in CASES:
        rows, blocks = [], []
        for var, vt in VARIANTS:
            p = place(case, var)
            m = p["m"]
            allm.append(m)
            print(m)
            verdict = '<span class="ok">过</span>' if not m["fails"] else '<span class="bad">不过</span>：' + "；".join(m["fails"])
            rows.append(
                f'<tr><th>{vt.split(" · ")[0] if var in DRAWN else vt + "（不画）"}</th><td>{m["sig_vias"]} / {m["gnd_vias"]}</td>'
                f'<td>{m["rows"]}</td><td>{m["length"]:.2f}</td><td>{m["left_straight"]:.2f}</td>'
                f'<td>{m["min_vv"] if m["min_vv"] else "—"}</td><td>{m["max_ret"]:.2f}</td><td>{m["min_pad_track"]:.3f}</td>'
                f'<td>{m["strip_cuts"]} 处 / {m["strip_cut_mm"]:.2f}</td><td>{m["strip_neck"]:.3f}</td>'
                f'<td>{m["jog"]:.3f}</td><td class="l">{verdict}</td></tr>')
            if var in DRAWN:
                blocks.append(f'<h3>{vt}</h3><div class="two">{panel(p, "L1")}{panel(p, "L6")}</div>')
        body.append(
            f'<section><h2>{case[1]}</h2><p>{case[2]}</p><div class="scroll"><table><tr><th>排法</th><th>信号过孔 / 新加的地过孔</th>'
            f'<th>排数</th><th>过孔阵占长 mm</th><th>阵后到颗粒规则区还剩的直线 mm</th><th>信号过孔最小中心距（≥ 0.8）</th>'
            f'<th>最远的回流地过孔（≤ 0.635）</th><th>过孔盘到别的线（≥ 0.15）</th><th>地铜条被切断：处数 / 总长 mm</th>'
            f'<th>铜条没断处的最窄宽度</th><th>线横移 mm</th><th>脚本检查</th></tr>'
            f'{"".join(rows)}</table></div>{"".join(blocks)}</section>')
    json.dump(allm, open(os.path.join(here, "metrics.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tmpl = open(os.path.join(here, "page.tmpl.html"), encoding="utf-8").read()
    html = tmpl.replace("{{BODY}}", "\n".join(body)).replace("{{EVB1}}", evb1_block(here))
    out = os.path.join(here, "via_array_variants.html")
    open(out, "w", encoding="utf-8").write(html)
    print(out)


if __name__ == "__main__":
    main()
