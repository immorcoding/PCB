"""PROTOTYPE (throwaway, issue 59): the T-branch band drawn like a board.

    python rk3568_ddr3_core/probes/tee_array_proto/strip.py

Each candidate is straightened (along the band = left to right, the SoC on the left) and its tracks are drawn at
real width: trunks on L1 (red) and L6 (blue), both branches on L4 (yellow). The official EVB1 is drawn from its
board file at the same scale. Tracks are placed by a small constructive router and checked for spacing by script;
this is not KiCad output and did not go through DRC. Writes tee_array_variants.html (the page) next to this file.
"""
import itertools
import json
import math
import re
from pathlib import Path

import draw as D

HERE = Path(__file__).resolve().parent
K = 46                                    # px per mm, all strips
W4, W1 = 0.134, 0.15                      # L4 branch, outer-layer trunk
CLR = 0.10                                # clearance inside the band
LANE = 0.45                               # trunk pitch beside the band
COL = {"bg": "#0b0f10", "L1": "#ff4136", "L6": "#3d7bff", "L4": "#f5c518", "via": "#d9d2b0", "gnd": "#2fae9a", "txt": "#c9d6d2",
       "dim": "#39474a", "chip": "#1c2a2c"}
SHORT = D.SHORT


def seg_pt(p, a, b):
    L = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2
    t = 0 if L == 0 else max(0, min(1, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / L))
    return math.dist(p, (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))


def seg_seg(a, b, c, d):
    def o(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    if o(a, b, c) * o(a, b, d) < 0 and o(c, d, a) * o(c, d, b) < 0:
        return 0.0
    return min(seg_pt(a, c, d), seg_pt(b, c, d), seg_pt(c, a, b), seg_pt(d, a, b))


def route(s0, lat0, lat_end, obs, used, key, half_w, trk_gap, stats):
    """From a via straight out across the band to lat_end, shifting along s (45 degrees) to pass between vias."""
    dirn = 1 if lat_end > lat0 else -1
    clr = D.VIA_R + CLR + half_w
    between = sorted((o for o in obs if (o[1] - lat0) * dirn > 0.05 and (lat_end - o[1]) * dirn > 0.0 and abs(o[0] - s0) < 3.0),
                     key=lambda o: o[1] * dirn)
    groups = []
    for o in between:
        if groups and abs(o[1] - groups[-1][-1][1]) < 0.25:
            groups[-1].append(o)
        else:
            groups.append([o])
    pts, cur_s, cur_lat = [(s0, lat0)], s0, lat0
    for g in groups:
        k = (key, round(g[0][1], 1))
        blocked = [(o[0] - clr, o[0] + clr) for o in g] + [(u - trk_gap, u + trk_gap) for u in used.get(k, [])]

        def ok(x):
            return all(not (lo + 1e-9 < x < hi - 1e-9) for lo, hi in blocked)
        cands = [cur_s] + [e for lo, hi in blocked for e in (lo, hi)]
        s_new = min((x for x in cands if ok(x)), key=lambda x: abs(x - cur_s))
        entry, leave = g[0][1] - dirn * clr, g[-1][1] + dirn * clr
        dlt = abs(s_new - cur_s)
        if dlt > 1e-6:
            a = entry - dirn * dlt
            if (a - cur_lat) * dirn < 0:
                a = cur_lat
                stats["steep"] += 1
            if abs(a - cur_lat) > 1e-6:
                pts.append((cur_s, a))
            pts.append((s_new, entry))
        cur_s, cur_lat = s_new, leave
        pts.append((cur_s, cur_lat))
        used.setdefault(k, []).append(s_new)
    return pts, cur_s


def layout(m):
    sig = [{"net": r["net"], "s": D.SL[tuple(r["via"])][0], "lat": D.SL[tuple(r["via"])][1], "layer": r["trunk_layer"]} for r in m["rows"]]
    gnd = [D.SL[tuple(g)] for g in m["gnds"]]
    spare = [D.SL[tuple(p)] for p in m["unused"]]
    obs_all = [(v["s"], v["lat"], v["net"]) for v in sig] + [(g[0], g[1], "GND") for g in gnd]
    edge = max(abs(o[1]) for o in obs_all) + 0.2
    stats = {"steep": 0}
    tracks, used = [], {}                                     # (layer, net, [pts])
    via_xy = {r["net"]: tuple(r["via"]) for r in m["rows"]}
    for v in sorted(sig, key=lambda v: v["s"]):
        for pts in D.TPL[via_xy[v["net"]]]:
            sgn = 1 if pts[-1][1] > 0 else -1
            tracks.append(("L4", v["net"], pts[:-1] + [(pts[-1][0], sgn * (edge + 0.45))]))
    head = min(v["s"] for v in sig) - 2.3
    lanes = {}
    for L in ("L1", "L6"):
        for side in (-1, 1):
            grp = sorted((v for v in sig if v["layer"] == L and (v["lat"] < 0) == (side < 0) and v["net"] not in D.CK), key=lambda v: v["s"])
            for i, v in enumerate(grp):
                lane = side * (edge + 0.55 + i * LANE + (LANE / 2 if L == "L6" else 0))
                tracks.append((L, v["net"], [(v["s"], v["lat"]), (v["s"], lane - side * 0.25), (v["s"] - 0.25, lane), (head, lane)]))
                lanes[(L, side)] = max(lanes.get((L, side), 0), abs(lane))
    for v in sig:
        if v["net"] in D.CK:
            tracks.append(("L1", v["net"], [(v["s"], v["lat"]), (head, v["lat"])]))
    # spacing check: track to track on one layer, track to via
    viol = []
    segs = [(L, n, a, b) for L, n, pts in tracks for a, b in zip(pts, pts[1:])]
    for (L1, n1, a, b), (L2, n2, c, d) in itertools.combinations(segs, 2):
        if L1 == L2 and n1 != n2:
            w = W4 if L1 == "L4" else W1
            dd = seg_seg(a, b, c, d)
            if dd < w + CLR - 1e-6:
                viol.append((L1, n1, n2, round(dd, 3), a))
    for L, n, a, b in segs:
        w = W4 if L == "L4" else W1
        for o in obs_all:
            if o[2] != n and seg_pt((o[0], o[1]), a, b) < D.VIA_R + CLR + w / 2 - 1e-6:
                viol.append((L, n, o[2] + "@via", round(seg_pt((o[0], o[1]), a, b), 3), (o[0], o[1])))
    pairs = {(v[0], tuple(sorted((v[1], v[2])))) for v in viol}
    return {"sig": sig, "gnd": gnd, "spare": spare, "tracks": tracks, "edge": edge, "head": head, "lanes": lanes,
            "viol": viol, "viol_pairs": len(pairs), "steep": stats["steep"]}


def strip_svg(m, lay):
    s0, s1 = lay["head"] - 0.6, max(v["s"] for v in lay["sig"]) + 1.3
    half = max([lay["edge"] + 1.0] + list(lay["lanes"].values())) + 0.7
    X = lambda s: (s - s0) * K
    Y = lambda lat: (lat + half) * K
    Wd, Ht = (s1 - s0) * K, 2 * half * K
    o = [f'<svg viewBox="0 0 {Wd:.0f} {Ht:.0f}" role="img" aria-label="{m["title"]}" xmlns="http://www.w3.org/2000/svg" '
         f'style="min-width:{Wd * 0.8:.0f}px;width:100%;background:{COL["bg"]}" font-family="Consolas,monospace">']
    gs, gw = m["gate_s"], m["passage"] / 2
    for sgn in (-1, 1):                                        # the two chip corners at the passage
        y0, y1 = (0, Y(-gw)) if sgn < 0 else (Y(gw), Ht)
        o.append(f'<rect x="{X(gs - 1.1):.1f}" y="{y0:.1f}" width="{2.2 * K:.1f}" height="{y1 - y0:.1f}" fill="#31464a" stroke="#6f8a8f" stroke-width="1.5"/>')
        o.append(f'<text x="{X(gs):.1f}" y="{(y0 + y1) / 2 + 5:.1f}" fill="#e8f0ee" font-size="13" text-anchor="middle" stroke="#31464a" stroke-width="4" paint-order="stroke">颗粒 {"A" if sgn < 0 else "B"} 的角</text>')
    o.append(f'<line x1="0" y1="{Y(0):.1f}" x2="{Wd:.0f}" y2="{Y(0):.1f}" stroke="{COL["dim"]}" stroke-dasharray="2 6"/>')
    for s, txt in ((m["seg0"], "拐 45°"), (m["centre_s"], "等长中心")):
        if s0 < s < s1:
            o.append(f'<line x1="{X(s):.1f}" y1="0" x2="{X(s):.1f}" y2="{Ht:.0f}" stroke="{COL["dim"]}" stroke-dasharray="2 6"/>')
            o.append(f'<text x="{X(s) + 4:.1f}" y="{Ht - 6:.0f}" fill="{COL["txt"]}" font-size="11">{txt}</text>')
    rc = (m["s_ck"] - 2.05, m["s_ck"] - 0.3)
    o.append(f'<rect class="L6" x="{X(rc[0]):.1f}" y="{Y(-0.6):.1f}" width="{(rc[1] - rc[0]) * K:.1f}" height="{1.2 * K:.1f}" fill="{COL["L6"]}" fill-opacity="0.18" stroke="{COL["L6"]}" stroke-dasharray="5 3"/>')
    o.append(f'<text class="L6" x="{X(sum(rc) / 2):.1f}" y="{Y(0) + 4:.1f}" fill="{COL["L6"]}" font-size="10" text-anchor="middle">背面 RC</text>')
    for L in ("L6", "L1", "L4"):
        w = (W4 if L == "L4" else W1) * K
        for LL, n, pts in lay["tracks"]:
            if LL == L:
                o.append(f'<polyline class="{L}" points="{" ".join(f"{X(p[0]):.1f},{Y(p[1]):.1f}" for p in pts)}" fill="none" stroke="{COL[L]}" '
                         f'stroke-width="{w:.1f}" stroke-linejoin="round" stroke-linecap="round" opacity="{0.8 if L == "L6" else 0.95}"/>')
    for p in lay["spare"]:
        o.append(f'<circle cx="{X(p[0]):.1f}" cy="{Y(p[1]):.1f}" r="{D.VIA_R * K:.1f}" fill="none" stroke="{COL["via"]}" stroke-width="1.6" stroke-dasharray="4 3"/>')
    for g in lay["gnd"]:
        o.append(f'<circle cx="{X(g[0]):.1f}" cy="{Y(g[1]):.1f}" r="{D.VIA_R * K:.1f}" fill="{COL["gnd"]}"/>')
    for v in lay["sig"]:
        o.append(f'<circle cx="{X(v["s"]):.1f}" cy="{Y(v["lat"]):.1f}" r="{D.VIA_R * K:.1f}" fill="{COL["via"]}" stroke="{COL[v["layer"]]}" stroke-width="3.2"/>')
        o.append(f'<text x="{X(v["s"]):.1f}" y="{Y(v["lat"]) + 2.6:.1f}" fill="#111" font-size="7.2" font-weight="700" text-anchor="middle">{SHORT.get(v["net"], v["net"])}</text>')
    for L, n1, n2, dd, a in lay["viol"]:
        o.append(f'<circle cx="{X(a[0]):.1f}" cy="{Y(a[1]):.1f}" r="9" fill="none" stroke="#ff00ff" stroke-width="1.5"/>')
    xr = X(s1) - 8
    o.append(f'<text x="{xr:.1f}" y="18" fill="{COL["L4"]}" font-size="13" text-anchor="end">↑ 黄色分支去颗粒 A</text>')
    o.append(f'<text x="{xr:.1f}" y="{Ht - 10:.0f}" fill="{COL["L4"]}" font-size="13" text-anchor="end">↓ 黄色分支去颗粒 B</text>')
    o.append(f'<text x="8" y="{Y(0) - 8:.1f}" fill="{COL["txt"]}" font-size="13">← 主干从 SoC 来</text>')
    # dimension between two neighbouring vias of the upper row, and a pointer to a ground via
    row = sorted((v for v in lay["sig"] if v["lat"] < 0 and v["net"] not in D.CK), key=lambda v: v["s"])
    pair = next(((a, b) for a, b in zip(row, row[1:]) if b["s"] - a["s"] < 1.05 and a["s"] > m["seg0"] + 3), None)
    if pair:
        a, b = pair
        yy = Y(a["lat"]) - 20
        o.append(f'<path d="M{X(a["s"]):.1f},{yy:.1f}H{X(b["s"]):.1f}M{X(a["s"]):.1f},{yy - 5:.1f}v10M{X(b["s"]):.1f},{yy - 5:.1f}v10" stroke="#fff" stroke-width="1.2" fill="none"/>')
        o.append(f'<text x="{(X(a["s"]) + X(b["s"])) / 2:.1f}" y="{yy - 6:.1f}" fill="#fff" font-size="12" text-anchor="middle" stroke="{COL["bg"]}" stroke-width="4" paint-order="stroke">{b["s"] - a["s"]:.2f} mm</text>')
    gin = [q for q in lay["gnd"] if abs(q[1]) < 0.1 and q[0] > m["seg0"] + 3]
    if gin:
        q = gin[0]
        o.append(f'<text x="{X(q[0]):.1f}" y="{Y(q[1]) + 4:.1f}" fill="#06231f" font-size="8" font-weight="700" text-anchor="middle">地</text>')
    o.append(f'<line x1="8" y1="{Ht - 10:.0f}" x2="{8 + K}" y2="{Ht - 10:.0f}" stroke="{COL["txt"]}" stroke-width="2"/><text x="{8 + K / 2}" y="{Ht - 15:.0f}" fill="{COL["txt"]}" font-size="11" text-anchor="middle">1 mm</text>')
    o.append("</svg>")
    return "\n".join(o)


ADDR = re.compile(r"^DDR4_(A\d|BA|BG|CKE|CS|ODT|ACT|RESET|CLK)")


def evb1_svg():
    d = json.loads((HERE / "evb1_tracks.json").read_text(encoding="utf-8"))
    x0, y0, x1, y1 = 126.3, -83.2, 143.2, -72.6
    X = lambda x: (x - x0) * K
    Y = lambda y: (y - y0) * K
    Wd, Ht = (x1 - x0) * K, (y1 - y0) * K
    o = [f'<svg viewBox="0 0 {Wd:.0f} {Ht:.0f}" role="img" aria-label="官方 EVB1 的分叉过孔带" xmlns="http://www.w3.org/2000/svg" '
         f'style="min-width:{Wd * 0.8:.0f}px;width:100%;background:{COL["bg"]}" font-family="Consolas,monospace">']
    lay = {"TOP": "L1", "BOTTOM": "L6", "L4-S1": "L4"}
    for want in ("L6", "L1", "L4"):
        for t in d["tracks"]:
            L = lay.get(t["layer"])
            if L != want:
                continue
            addr = bool(ADDR.match(t["net"]))
            pts = [t["a"]] + ([t["mid"]] if "mid" in t else []) + [t["b"]]
            col = COL[L] if addr else COL["dim"]
            o.append(f'<polyline class="{L}" points="{" ".join(f"{X(p[0]):.1f},{Y(p[1]):.1f}" for p in pts)}" fill="none" stroke="{col}" '
                     f'stroke-width="{max(t["w"], 0.09) * K:.1f}" stroke-linecap="round" opacity="{0.9 if addr else 0.28}"/>')
    for p in d["pads"]:
        if p["ref"].startswith(("R", "C")):
            L = "L1" if p["side"] == "TOP" else "L6"
            o.append(f'<rect class="{L}" x="{X(p["x"] - p["sx"] / 2):.1f}" y="{Y(p["y"] - p["sy"] / 2):.1f}" width="{p["sx"] * K:.1f}" height="{p["sy"] * K:.1f}" '
                     f'fill="{COL[L]}" fill-opacity="0.55" stroke="{COL[L]}"/>')
    for v in d["vias"]:
        addr = bool(ADDR.match(v["net"]))
        fill = COL["gnd"] if v["net"] == "GND" else COL["via"] if addr else COL["dim"]
        o.append(f'<circle cx="{X(v["x"]):.1f}" cy="{Y(v["y"]):.1f}" r="{v["pad"] / 2 * K:.1f}" fill="{fill}"/>')
        if addr:
            lab = re.sub(r"_(WEN|CASN|RASN)$", "", v["net"].replace("DDR4_", "")).replace("CLKP", "CK+").replace("CLKN", "CK-").replace("RESETN", "RST")
            lab = re.sub(r"0?N?(_[AB])$", r"\1", lab)[:5]
            o.append(f'<text x="{X(v["x"]):.1f}" y="{Y(v["y"]) + 2.4:.1f}" fill="#111" font-size="6.4" font-weight="700" text-anchor="middle">{lab}</text>')
    o.append(f'<text x="{Wd - 8:.0f}" y="18" fill="{COL["L4"]}" font-size="13" text-anchor="end" stroke="{COL["bg"]}" stroke-width="4" paint-order="stroke">↑ 黄色分支去上面一颗颗粒</text>')
    o.append(f'<text x="{Wd - 8:.0f}" y="{Ht - 10:.0f}" fill="{COL["L4"]}" font-size="13" text-anchor="end" stroke="{COL["bg"]}" stroke-width="4" paint-order="stroke">↓ 黄色分支去下面一颗颗粒</text>')
    o.append(f'<text x="8" y="18" fill="{COL["txt"]}" font-size="13" stroke="{COL["bg"]}" stroke-width="4" paint-order="stroke">← 主干从 SoC 来</text>')
    o.append(f'<line x1="8" y1="{Ht - 10:.0f}" x2="{8 + K}" y2="{Ht - 10:.0f}" stroke="{COL["txt"]}" stroke-width="2"/><text x="{8 + K / 2}" y="{Ht - 15:.0f}" fill="{COL["txt"]}" font-size="11" text-anchor="middle">1 mm</text>')
    o.append("</svg>")
    return "\n".join(o)


TOGGLE = '''<div class="tog" role="group" aria-label="显示哪些层">
<label><input type="checkbox" id="t-l1" checked> <i style="background:#ff4136"></i>L1 主干</label>
<label><input type="checkbox" id="t-l4" checked> <i style="background:#f5c518"></i>L4 分支</label>
<label><input type="checkbox" id="t-l6" checked> <i style="background:#3d7bff"></i>L6 主干和背面器件</label>
</div>
<style>
.tog{display:flex;flex-wrap:wrap;gap:8px 22px;font-size:.92rem;position:sticky;top:env(safe-area-inset-top,0px);background:var(--bg);padding:8px 0;z-index:5}
.tog i{display:inline-block;width:20px;height:5px;margin-right:6px;vertical-align:middle}
.tog input{accent-color:var(--accent)}
main.h1 .L1,main.h4 .L4,main.h6 .L6{display:none}
.cap{font-size:.9rem;color:var(--muted);max-width:none}
.cap b{color:var(--fg)}
</style>
<script>
for (const [id, c] of [["t-l1","h1"],["t-l4","h4"],["t-l6","h6"]]) {
  document.getElementById(id).addEventListener("change", e => document.querySelector("main").classList.toggle(c, !e.target.checked));
}
</script>'''


def main():
    D.NO_RATS = True
    cands = D.CANDS()
    head = (HERE.parent / "via_array_proto" / "page.tmpl.html").read_text(encoding="utf-8").split("<main>")[0].replace("字节组换层过孔阵", "T 型分叉过孔阵")
    body = [(HERE / "intro.html").read_text(encoding="utf-8"), TOGGLE,
            '<section><h2>先看官方板：EVB1 的分叉过孔带（实际走线）</h2>'
            '<p>从官方板文件里读出来按比例画的，不是示意。灰色是不相干的线。白色过孔是分叉点：主干从顶层（红）或底层（蓝）过来，在过孔上换到 L4（黄），向上、向下各出一支。'
            '左边带红、蓝小方块的是 0 Ω 和 CK 的端接电阻。</p>'
            f'<div class="scroll">{evb1_svg()}</div></section>']
    out = []
    for m in cands:
        lay = layout(m)
        out.append((m, lay))
        chk = "间距都够" if not lay["viol"] else f'<span class="bad">有 {lay["viol_pairs"]} 处间距不够（图上紫圈）</span>'
        body.append(
            f'<section><h2>{m["title"]}</h2><p>{m["blurb"]}</p><div class="scroll">{strip_svg(m, lay)}</div>'
            f'<p class="cap">带长 <b>{m["len"]:.1f} mm</b>　地过孔 <b>{m["gnd"]}</b> 个，0.635 mm 内没有地过孔的信号过孔 <b>{m["gnd_over"]}</b> 个　'
            f'分支估算最长 <b>{m["branch"][1]:.1f} mm</b>（上限 15.24）　两分支天然差中位 <b>{m["mis_med"]:.2f} mm</b>　'
            f'脚本查线到线、线到过孔盘 0.10 mm：{chk}{"；有 %d 处拐弯陡于 45°" % lay["steep"] if lay["steep"] else ""}</p>'
            f'<ul>{"".join(f"<li>{n}</li>" for n in m["notes"])}</ul></section>')
        print(m["title"], "| viol pairs", lay["viol_pairs"], "segments", len(lay["viol"]), "steep", lay["steep"], "| lanes", {k: round(v, 2) for k, v in lay["lanes"].items()},
              "| edge", round(lay["edge"], 2))
        for v in lay["viol"][:12]:
            print("   ", v)
        D.show(m)
    body.append('<section><h2>带子在板上的位置</h2><p>上面的图是把带子拉直了画的。它在板上的走向是：从 A1 角外向北穿过两颗颗粒的角之间，再斜 45° 向西北。下图是候选 B 在板上的位置，米色、黄色的圆是分叉过孔，青色是地过孔，蓝色虚线框是背面的 RC。</p>'
                + D.svg(cands[1]) + '</section>')
    body.append((HERE / "outro.html").read_text(encoding="utf-8"))
    (HERE / "tee_array_variants.html").write_text(head + "<main>\n" + "\n".join(body) + "\n</main>\n", encoding="utf-8")
    slim = [{k: v for k, v in m.items() if k not in ("blurb", "notes")} | {"spacing_violations": lay["viol_pairs"], "steep": lay["steep"]} for m, lay in out]
    (HERE / "metrics.json").write_text(json.dumps(slim, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
