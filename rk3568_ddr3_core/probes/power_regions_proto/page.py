"""PROTOTYPE (issue 52): the comparison page. draw.py calls write(res)."""
import collections, html
from pathlib import Path

import model as M
import rails as R

HERE = Path(__file__).resolve().parent
CSS = """
body{font:14px/1.55 "Microsoft YaHei","Segoe UI",sans-serif;margin:0;background:#f6f6f3;color:#1c1c1c}
header{padding:18px 28px 6px}h1{font-size:20px;margin:0 0 4px}h2{font-size:16px;margin:22px 0 8px}
.warn{background:#fff4d6;border-left:4px solid #d9a400;padding:8px 12px;margin:10px 0;max-width:1100px}
.tabs{display:flex;gap:6px;padding:0 28px;position:sticky;top:0;background:#f6f6f3;border-bottom:1px solid #ccc;z-index:2}
.tabs button{font:inherit;padding:9px 16px;border:1px solid #bbb;border-bottom:none;background:#e6e6e1;cursor:pointer;border-radius:6px 6px 0 0}
.tabs button.on{background:#fff;font-weight:bold}
section{display:none;padding:10px 28px 30px}section.on{display:block}
.imgs{display:flex;gap:14px;flex-wrap:wrap}.imgs img{width:min(48%,760px);border:1px solid #bbb;background:#fff}
table{border-collapse:collapse;margin:6px 0 14px;background:#fff}td,th{border:1px solid #c9c9c4;padding:4px 9px;text-align:left;vertical-align:top}
th{background:#ecece7}td.n{text-align:right;font-variant-numeric:tabular-nums}.bad{color:#b3261e;font-weight:bold}.ok{color:#1a7f37}
.sw{display:inline-block;width:11px;height:11px;margin-right:5px;vertical-align:-1px}
p,li{max-width:1100px}code{background:#eee;padding:0 3px}
"""
COL = {"VCC_DDR": "#d9822b", "VDD_CPU": "#d33f49", "VDD_LOGIC": "#3a7bd5", "VDD_GPU": "#2e9e6b", "VDD_NPU": "#8e5bd0",
       "VDDA_0V9": "#b0a030", "VCCA_1V8": "#3aa8b8", "VCC_3V3": "#c05a9c", "VCC_1V8": "#6b8e23"}


def sw(net):
    return f'<span class="sw" style="background:{COL.get(net, "#444")}"></span>{html.escape(net)}'


def frac(a, b):
    return f'<span class="{"ok" if a == b else "bad"}">{a} / {b}</span>'


def variant(r):
    o = [f"<p>{html.escape(r['blurb'])}</p>",
         f'<div class="imgs"><a href="out/{r["key"]}_board.png"><img src="out/{r["key"]}_board.png"></a>'
         f'<a href="out/{r["key"]}_core.png"><img src="out/{r["key"]}_core.png"></a></div>',
         "<h2>L3 上的块</h2><table><tr><th>网络</th><th>从哪条板边进来（边上的宽度 mm）</th><th>面积 mm²</th>"
         "<th>SoC 的球：L3 上接到板边<br>过孔 0.4 / 0.2，铜最窄 0.2</th><th>同上<br>区内过孔 0.30 / 0.15，铜最窄 0.1</th>"
         "<th>颗粒的电源过孔接上</th><th>瑞芯微要求的宽度<br>球区附近 / 外围</th></tr>"]
    for b in r["blocks"]:
        c = b.get("core")
        g = R.BIG.get(b["net"])
        edge = "、".join(f"{k}边 {v}" for k, v in b["edge"].items())
        o.append(f"<tr><td>{sw(b['net'])}</td><td>{html.escape(r['entry'].get(b['net'], ''))}<br>{edge}</td><td class=n>{b['area']}</td>"
                 + (f"<td>{frac(c['big']['fed'], c['balls'])}" + (f"<br>断开：{' '.join(c['big']['unfed'])}" if c['big']['unfed'] else "") + "</td>"
                    f"<td>{frac(c['small']['fed'], c['balls'])}</td>" if c else "<td>球区外的窄条</td><td>—</td>")
                 + (f"<td>{frac(b['ddr_joined'], b['ddr_vias'])}</td>" if b["ddr_vias"] else "<td>—</td>")
                 + (f"<td>{g[1]:.2f} / {g[2]:.2f} mm；外围换层过孔 &gt; {g[3]}</td>" if g else "<td>—</td>") + "</tr>")
    o.append("</table>")
    e = r["exits"]
    o.append(f"<h2>小电源（17 路、41 个球）</h2><p>每个球一个过孔到背面电容。出球区的走线共 {e['n']} 根，合计约 {e['total']} mm（直线估算，没有绕障），"
             f"最长 {e['max']} mm（{e['longest'][0]} 的 {e['longest'][1]}）；按出去的方向：" + "、".join(f"{k} {v} 根" for k, v in e["sides"].items()) + "。</p>")
    o.append("<table><tr><th>网络</th><th>球数</th><th>出线合计 mm</th><th>背面电容（放上 / 要放）</th></tr>")
    for n, (ln, k) in e["by_net"].items():
        got, want = r["caps"].get(n, [0, 0])
        o.append(f"<tr><td>{sw(n)}</td><td class=n>{k}</td><td class=n>{ln}</td><td>{frac(got, want)}</td></tr>")
    o.append("</table>")
    o.append("<h2>大电源的背面电容（球区正下方，焊盘压在过孔上）</h2><table><tr><th>网络</th><th>放上 / 参考原理图里“芯片背面”的个数</th></tr>")
    for n in R.BIG:
        got, want = r["caps"][n]
        o.append(f"<tr><td>{sw(n)}</td><td>{frac(got, want)}</td></tr>")
    o.append(f"</table><p>电容按“一个焊盘在本路电源的过孔上、另一个在相邻的地过孔上”找位置：对角相邻 0.92 mm 放 0402，正交相邻 0.65 mm 放 0201。"
             f"这一版共 {sum(r['cap_sizes'].values())} 颗（{'、'.join(f'{k} {v} 颗' for k, v in r['cap_sizes'].items())}）。"
             f"在自己的块里找不到过孔位的大电源球：{' '.join(r['no_site']) or '无'}（它们贴着块的边界，过孔位要由扇出工具和块的边界一起定）。</p>")
    return "\n".join(o)


def facts():
    balls = collections.Counter(n for _, _, _, k, n in M.soc_balls() if k == "pwr")
    o = ["<h2>1　官方参考原理图里的电源轨（AIoT 参考设计）</h2><table><tr><th>网络</th><th>球数</th><th>峰值电流</th><th>画法</th></tr>"]
    for n in R.BIG:
        o.append(f"<tr><td>{sw(n)}</td><td class=n>{balls[n]}</td><td class=n>{R.BIG[n][0]} A</td><td>L3 分块</td></tr>")
    for n, ma in R.SMALL_MA.items():
        o.append(f"<tr><td>{html.escape(n)}</td><td class=n>{balls[n]}</td><td class=n>{'未给' if ma is None else str(ma) + ' mA'}</td><td>走线，背面电容</td></tr>")
    o.append("</table><p>共 22 路、85 个球；另有 VDD_CPU_COM（M15，CPU 电源的反馈脚，4 mil 线跟着铜皮走）和 DDR_VREFOUT（P8）是走线。"
             "<code>rk3568_pins.json</code> 的 <code>ref</code> 列和官方不一致的地方：VDD_LOGIC 和 VDD_GPU 是两路；PMU 的 0.9 V、1.8 V、3.3 V 各自独立；"
             "HDMI、eDP、MIPI 的模拟电源归 IMAGE 一组（MIPI 另经磁珠）；USB 的 0.9 V、1.8 V 经磁珠。</p>")
    o.append("""<h2>2　官方 EVB1 板上怎么做的（从 .brd 读出）</h2><ul>
<li>SoC 外形内 458 个过孔全是 0.4 / 0.2 mm；电源球一球一孔；地过孔 216 个对 212 个地球，没有减少。</li>
<li>五路大电源各有一大块 L3 铜皮伸进球区，再加背面球区正下方的小铜皮（2–8 mm²，每块连 2–6 个球）和顶层的连线（每路 6–27 mm）；
VDD_LOGIC、VDD_GPU、VDD_NPU 在 L3 上还各画了 10–16 mm 的线。L3 的底色是地。</li>
<li>方向（按 SoC 自己的球位坐标）：VCC_DDR 朝颗粒一侧，VDD_CPU 朝东北，VDD_LOGIC、VDD_GPU、VDD_NPU 朝南。</li>
<li>小电源每个脚一个网络，主要在内层信号层 L4 上走线出球区（外形内每根 3–11 mm），少数在 L3 上走线；背面只有过孔到电容的 0.2–0.7 mm。</li>
<li>背面两脚器件 75 颗，焊盘中心距 0.55 mm（0201）50 颗、0.9 mm（0402）20 颗、1.4 mm 5 颗。</li></ul>
<h2>3　这一版原型查出来的两件事</h2><ul>
<li><b>球区外圈的信号过孔会把 L3 堵死。</b>摸底时的扇出把信号过孔挨着排，NPU、LOGIC、GPU 三路在 L3 上到不了板边。封装在第 3–7 圈留了空行空列
（K、N、T、W 行和第 10、13、16、19 列，每边 4 条），就是给电源走的通道；瑞芯微指南也要求信号过孔排整齐、给电源铜皮让路。
两个方案都按“通道两侧的球把过孔打到背离通道的一侧”来算，这一条要写进扇出工具的输入。</li>
<li><b>按瑞芯微的 0.4 / 0.2 过孔，在嘉立创的规则下 L3 进不了电源核心区。</b>球距 0.65 mm，孔到铜 0.2 mm，两个相邻的异网络过孔之间只剩 0.05 mm。
VCC_DDR、VDD_CPU、VDD_NPU 的球连成片，靠自己的过孔连出去；VDD_LOGIC 的 10 个球被地球隔成 4 组，VDD_GPU 被围在中间，L3 上全断。
球区内改用已定的小过孔 0.30 / 0.15 时，相邻过孔之间有 0.10 mm 的铜，五路 44 个球全部接上，但这 0.10 mm 正好在板厂下限上。</li></ul>
<h2>4　假设和没有核对的</h2><ul>
<li>板框是假设的 43 × 43 mm（板框在地图上还没定），只用来说明每块铜皮到哪条边。</li>
<li>过孔位来自摸底的扇出（不是最终的扇出工具），只作 L3 上被打掉多少铜的替身；字节组换层的过孔阵还没定，没有画。</li>
<li>连通是 0.0125 mm 栅格模型算的，没有经过 KiCad 铺铜和 DRC；小电源的走线长度是直线估算。</li>
<li>磁珠接哪个网络是按参考原理图文字的顺序读的，没有对着图核对；EVB1 的数由脚本从导入的板子里读出，主会话没有另行抽查。</li>
<li>颗粒自己的去耦（每颗 16–17 颗，背面）和 VREF、ZQ 的器件没有画，位置已在摆位票里定。</li></ul>""")
    return "\n".join(o)


def write(res):
    tabs = "".join(f'<button data-k="{r["key"]}">{html.escape(r["title"])}</button>' for r in res) + '<button data-k="facts">事实和假设</button>'
    secs = "".join(f'<section id="{r["key"]}">{variant(r)}</section>' for r in res) + f'<section id="facts">{facts()}</section>'
    page = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>原型：验证板的电源铜皮区域草图</title><style>{CSS}</style></head><body>
<header><h1>原型：RK3568 + 两颗 DDR3 验证板的电源铜皮区域草图（L3 分块、过孔、背面去耦）</h1>
<div class="warn">一次性原型，不合并。图按真实球位 1:1 画；块的外形只有 45° 和 90°，两版的草图文本都过了 <code>cu_sketch check</code>（0 错误）。点图看大图。</div></header>
<div class="tabs">{tabs}</div>{secs}
<script>
const show=k=>{{document.querySelectorAll('section').forEach(s=>s.classList.toggle('on',s.id===k));
document.querySelectorAll('.tabs button').forEach(b=>b.classList.toggle('on',b.dataset.k===k));
history.replaceState(null,'','?v='+k)}};
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>show(b.dataset.k));
show(new URLSearchParams(location.search).get('v')||'{res[0]["key"]}');
</script></body></html>"""
    (HERE / "power_regions.html").write_text(page, encoding="utf-8")
