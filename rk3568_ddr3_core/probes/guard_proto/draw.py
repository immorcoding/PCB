"""PROTOTYPE (issue 47, throwaway): draw one DDR3 byte lane on L1 with three guard styles.

Run: python draw.py   -> writes guard_variants.html next to this file and prints the numbers.
x runs from the SoC ball-field edge (0) to the DRAM ball-field edge (D). mm, to scale.
The two ends (how lines leave the ball fields) are schematic: equal pitch, one 45 degree step.
"""
import math
import os

W = 0.15                 # outer-layer 50 ohm
W_IN = 0.1016            # inside the rule areas
DW, DG = 0.104, 0.15     # DQS pair
GS = 0.15                # guard to signal, 1 x W
SS = 0.30                # DQ to DQ, 2 x W
D = 7.5                  # ball field to ball field (EVB1 to DRAM B: 7.51)
RULE_SOC, RULE_RAM = 1.7, 2.3   # rule area reach beyond the ball field (outline + 1 mm)
P0, P1 = 0.40, 0.50      # schematic exit pitch at the SoC / entry pitch at the DRAM
STUB = 0.3
SIGS = ["DQ0", "DQ2", "DQ4", "DQ6", "DQS", "DQ1", "DQ3", "DQ5", "DQ7", "DM"]

# (key, title, pattern, {guard letter: (width, via pad, via drill)}, note)
VARIANTS = [
    ("A", "A 全部宽地线：0.40 mm，线上直接打 0.4 / 0.2 过孔",
     "WSSWSSWDWSSWSSWSW", {"W": (0.40, 0.40, 0.20)},
     "每条地线都有过孔；信号线全程直线。"),
    ("B", "B 照官方板：宽地线（0.40，带过孔）和窄地线（0.15，中间不打孔）交替",
     "WSSNSSWDWSSNSSWSW", {"W": (0.40, 0.40, 0.20), "N": (0.15, None, None)},
     "窄地线只能在两头接地（接到球区里的地球或其过孔），中间没有过孔。"),
    ("C", "C 全部用小过孔：地线 0.30 mm，线上打 0.30 / 0.15 过孔",
     "WSSWSSWDWSSWSSWSW", {"W": (0.30, 0.30, 0.15)},
     "规则区外用 0.30 / 0.15 过孔，和已定的“区外过孔 0.4 / 0.2”不同，要用户同意。"),
]


def layout(pattern, guards):
    objs, y, prev = [], 0.0, None
    for c in pattern:
        if prev is not None:
            y += GS if (c in guards or prev in guards) else SS
        wid = guards[c][0] if c in guards else (W if c == "S" else 2 * DW + DG)
        objs.append([c, y + wid / 2, wid])
        y += wid
        prev = c
    for o in objs:
        o[1] -= y / 2
    return objs, y


def build(pattern, guards):
    objs, width = layout(pattern, guards)
    sig = [o for o in objs if o[0] not in guards]
    n = len(sig)
    tracks, vias, xin, xout = [], [], {}, {}
    for i, o in enumerate(sig):
        ys = (i - (n - 1) / 2) * P0
        ye = (i - (n - 1) / 2) * P1
        yt = o[1]
        a = STUB + abs(yt - ys)
        b = D - STUB - abs(yt - ye)
        xin[id(o)], xout[id(o)] = a, b
        pts = [(0, ys), (STUB, ys), (a, yt), (b, yt), (D - STUB, ye), (D, ye)]
        offs = [0.0] if o[0] == "S" else [-(DW + DG) / 2, (DW + DG) / 2]
        for off in offs:
            tracks.append(("sig", [(x, yy + off) for x, yy in pts], W if o[0] == "S" else DW, SIGS[i]))
    stats = {"width": width, "fan_soc": max(xin.values()), "fan_ram": D - min(xout.values()),
             "vias": 0, "max_gap": 0.0, "unvia": 0}
    for k, o in enumerate(objs):
        if o[0] not in guards:
            continue
        nb = [p for p in (objs[k - 1] if k else None, objs[k + 1] if k + 1 < len(objs) else None) if p]
        x0 = max(xin[id(p)] for p in nb) + 0.25
        x1 = min(xout[id(p)] for p in nb) - 0.25
        gw, pad, drill = guards[o[0]]
        tracks.append(("gnd", [(x0, o[1]), (x1, o[1])], gw, "GND"))
        if pad:
            nseg = max(1, math.ceil((x1 - x0) / 2.54))
            for j in range(nseg + 1):
                vias.append((x0 + (x1 - x0) * j / nseg, o[1], pad, drill))
            stats["vias"] += nseg + 1
            stats["max_gap"] = max(stats["max_gap"], (x1 - x0) / nseg)
        else:
            stats["unvia"] += 1
            stats["unvia_len"] = x1 - x0
    return tracks, vias, stats


def svg(tracks, vias, width):
    s = 62
    h = max(width, 5.0) + 1.6
    out = [f'<svg viewBox="{-0.6 * s:.0f} {-h / 2 * s:.0f} {(D + 1.2) * s:.0f} {h * s:.0f}" '
           f'xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:980px;background:#10161c">']
    for x, lab in ((0, "SoC 球区边"), (RULE_SOC, "SoC 规则区边"), (D - RULE_RAM, "颗粒规则区边"), (D, "颗粒球区边")):
        out.append(f'<line x1="{x * s}" y1="{-h / 2 * s}" x2="{x * s}" y2="{h / 2 * s}" stroke="#5b6b7a" stroke-dasharray="6 5"/>')
        out.append(f'<text x="{x * s + 4}" y="{-h / 2 * s + 14}" fill="#9fb0c0" font-size="12">{lab}</text>')
    for kind, pts, w, name in tracks:
        col = "#e0564f" if kind == "sig" else "#3fa7d6"
        if name == "DQS":
            col = "#f2b134"
        p = " ".join(f"{x * s:.1f},{y * s:.1f}" for x, y in pts)
        out.append(f'<polyline points="{p}" fill="none" stroke="{col}" stroke-width="{w * s:.2f}" '
                   f'stroke-linejoin="round" stroke-linecap="round"><title>{name} {w} mm</title></polyline>')
    for x, y, pad, drill in vias:
        out.append(f'<circle cx="{x * s:.1f}" cy="{y * s:.1f}" r="{pad / 2 * s:.2f}" fill="#7fd0f0"/>'
                   f'<circle cx="{x * s:.1f}" cy="{y * s:.1f}" r="{drill / 2 * s:.2f}" fill="#10161c"/>')
    y0 = h / 2 * s - 12
    out.append(f'<line x1="0" y1="{y0}" x2="{s}" y2="{y0}" stroke="#fff" stroke-width="2"/>'
               f'<text x="{s + 6}" y="{y0 + 4}" fill="#fff" font-size="12">1 mm</text></svg>')
    return "\n".join(out)


def main():
    rows, blocks = [], []
    for key, title, pat, guards, note in VARIANTS:
        tracks, vias, st = build(pat, guards)
        un = f'{st["unvia"]} 条，各 {st["unvia_len"]:.1f} mm 无过孔' if st["unvia"] else "无"
        rows.append(f'<tr><td>{key}</td><td>{st["width"]:.2f}</td><td>{st["fan_soc"]:.2f} / {st["fan_ram"]:.2f}</td>'
                    f'<td>{st["vias"]}</td><td>{st["max_gap"]:.2f}</td><td>{un}</td></tr>')
        blocks.append(f"<h2>{title}</h2><p>{note}</p>{svg(tracks, vias, st['width'])}")
        print(key, {k: round(v, 2) for k, v in st.items()})
    html = f"""<!doctype html><html lang="zh"><meta charset="utf-8"><title>原型：表层数据线包地（issue 47）</title>
<style>body{{font:15px/1.6 system-ui,"Microsoft YaHei",sans-serif;max-width:1000px;margin:24px auto;padding:0 16px;color:#1c2630}}
table{{border-collapse:collapse}}td,th{{border:1px solid #b8c2cc;padding:4px 10px;text-align:right}}h2{{margin-top:36px}}
.k span{{display:inline-block;width:26px;height:6px;margin:0 6px 2px 14px}}</style>
<h1>原型（用完即弃）：一个字节组在 L1 上的三种包地画法</h1>
<p>一个字节组：DQ × 8、DM、一对 DQS。线宽 0.15 mm（DQS 0.104 / 0.15），地到信号 0.15，DQ 到 DQ 0.30。
两个球区相距 {D} mm（官方 EVB1 到第二颗颗粒是 7.51 mm）。按比例画；<b>两头从球区出来的一段是示意</b>（等间距、一个 45° 台阶），不是真实扇出。</p>
<p class="k"><span style="background:#e0564f"></span>DQ / DM<span style="background:#f2b134"></span>DQS 对<span style="background:#3fa7d6"></span>地线<span style="background:#7fd0f0;height:12px;width:12px;border-radius:6px"></span>地过孔</p>
<table><tr><th>版本</th><th>线带宽 mm</th><th>展开所需长度 SoC 侧 / 颗粒侧 mm</th><th>地过孔数</th><th>地过孔最大间隔 mm（上限 5.08）</th><th>没有过孔的地线</th></tr>
{''.join(rows)}</table>
<p>不包地、只按线距规则排是 4.56 mm 宽。规则区伸出球区：SoC 侧 {RULE_SOC} mm，颗粒侧 {RULE_RAM} mm；展开长度超过它，就是线带在规则区内没展开完。</p>
{''.join(blocks)}
</html>"""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard_variants.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(path)


if __name__ == "__main__":
    main()
