"""PROTOTYPE (issue 15): write compare.html. Two modes: a strip that shows the same view of several
variants side by side, and a single variant with its tables.

    D:\\KiCad\\bin\\python.exe make_compare.py        (after build.sh; reads out/*/tune_table.json, lengths.json, geo.txt)

Open compare.html by double click. Left / right arrows change the group (side by side) or the variant
(single), up / down the view. Every number on the page is read from the json files of the build.
"""
import html, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
VARIANTS = [
    ("0_base", "0 底板（5 mm）", "封装间距 5 mm（约定值），没有蛇形。"),
    ("1_A05_single", "1 摆幅 0.5 单侧", "约定的默认参数：半径 0.25、摆幅 0.5、单侧、放在直线段中间。"),
    ("2_A10_single", "2 摆幅 1.0 单侧", "摆幅 1.0、单侧；整弯都是 1.0，最后一个压低凑数。"),
    ("2b_A10_single_even", "2b 摆幅 ≤1.0 单侧等高", "同 2，但所有弯压到一样高。"),
    ("3_A05_double", "3 摆幅 0.5 起 双侧", "左右交替，腿直接穿过原线；一串弯等高。要补的不到约 1.64 mm 的线放不下双侧，仍是单侧。"),
    ("4_window_only_clk", "4 只补时钟", "不补到一样长：只把 SDCLK 补到其余 8 根的正中（双侧），其余不动。±2.5 mm 的约定已经满足。"),
    ("5_A05_double_tight", "5 同 3，但间距放松", "对照用：拐点到圆弧 0.1、到别的铜 0.127、到规则区边 0.025（第一版的做法）。补得更齐，但挤。"),
    ("6_gap8_base", "6 底板（8 mm）", "额外的对照，不是约定的布局：SDRAM 右移 3 mm。没有蛇形。"),
    ("7_gap8_A05_single", "7 间距 8：0.5 单侧", "间距 8 mm 的板上用默认参数。"),
    ("8_gap8_A10_single", "8 间距 8：1.0 单侧", "间距 8 mm，摆幅 1.0、单侧，最后一个弯压低。"),
    ("8b_gap8_A10_single_even", "8b 间距 8：≤1.0 等高", "间距 8 mm，摆幅不超过 1.0、单侧、所有弯等高。"),
    ("9_gap8_A05_double", "9 间距 8：双侧，中间", "间距 8 mm，摆幅 0.5 起、双侧，放在直线段中间。"),
    ("9m_gap8_A05_double_near_mcu", "9m 同 9，靠 MCU", "同 9，蛇形尽量靠 MCU 一端（先用离 MCU 近的直线段，再往那一端推）。"),
    ("9s_gap8_A05_double_near_sdram", "9s 同 9，靠 SDRAM", "同 9，蛇形尽量靠 SDRAM 一端。"),
]
GROUPS = [
    ("5 mm：四组参数", ["1_A05_single", "2_A10_single", "2b_A10_single_even", "3_A05_double"]),
    ("5 mm：补线前后", ["0_base", "1_A05_single", "3_A05_double"]),
    ("5 mm：补齐、只补时钟、放松间距", ["3_A05_double", "4_window_only_clk", "5_A05_double_tight"]),
    ("8 mm：四组参数", ["7_gap8_A05_single", "8_gap8_A10_single", "8b_gap8_A10_single_even", "9_gap8_A05_double"]),
    ("8 mm：位置（靠 MCU / 中间 / 靠 SDRAM）", ["9m_gap8_A05_double_near_mcu", "9_gap8_A05_double", "9s_gap8_A05_double_near_sdram"]),
]
VIEWS = [
    ("crop_corridor", "L1 局部：两个规则区之间"),
    ("crop_south", "L1 局部：MCU 下方"),
    ("crop_L4", "L4 局部：斜穿的三根"),
    ("crop_both", "L1 + L4 叠在一起：两个规则区之间"),
    ("group", "整组（L1 红、L4 蓝）"),
    ("L1", "L1"),
    ("L4", "L4"),
]
order = lambda n: (0, 0) if "CLK" in n else (1, int(re.sub(r"\D", "", n) or 0))


def load(key, name):
    p = os.path.join(HERE, "out", key, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def geo_list(key):
    p = os.path.join(HERE, "out", key, "geo.txt")
    lines = open(p, encoding="utf-8").read().strip().splitlines() if os.path.exists(p) else []
    return "<ul>%s</ul>" % "".join("<li>%s</li>" % html.escape(l.lstrip("- ")) for l in lines)


def caption(key):
    t = load(key, "tune_table.json")
    if not t:
        return "没有数据"
    d = t["drc"]
    drc = "DRC 未连接 %d，超窗 %d，其他 %d" % (d["unconnected"], len(d["length"]), sum(d["other"].values()))
    if "rows" not in t:
        return "没有蛇形。" + drc
    s, g = t["summary"], t["geo"]
    n = len(t["rows"])
    return "到目标 %d / %d，最长最短差 %.3f；%s；拐点到圆弧最短 %s，蛇形到别的线最近 %.3f，到规则区边最近 %.3f" % (
        n - s["not_reached"], n, s["spread_after"], drc, "%.3f" % g["lead_min"] if g["lead_min"] is not None else "—",
        g["serp_net_gap"]["gap"], g["area_gap"]["arc"]["gap"])


def table(key):
    t, L = load(key, "tune_table.json"), load(key, "lengths.json")
    if not t or not L:
        return "<p>没有数据（先跑 sh build.sh）</p>"
    a = t["arcs"]
    checks = ("<p><b>DRC</b>：未连接 %d，长度超窗 %d%s，其他 %s。　<b>规则有没有生效</b>（故意放一个坏拐角，看规则报不报）：%s</p>"
              "<p><b>track_shape.py</b>：%s（它不检查圆弧，圆弧相关的见下面）</p>"
              "<p><b>脚本从板文件量的</b>（DRC 和 track_shape.py 都不查的）：</p>%s") % (
        t["drc"]["unconnected"], len(t["drc"]["length"]),
        "（%s）" % "，".join(k.lstrip("/") for k in sorted(t["drc"]["length"], key=order)) if t["drc"]["length"] else "",
        "，".join("%s %d" % kv for kv in t["drc"]["other"].items()) or "0",
        html.escape(t["canary"]), html.escape("；".join(l.strip() for l in t["track_shape"].splitlines())), geo_list(key))
    if "rows" not in t:
        rows = ["<tr><th>网络</th><th>自然长度</th><th>过孔</th><th>比最长</th><th>比 SDCLK</th><th>各层长度</th></tr>"]
        for n in sorted(L["nets"], key=order):
            v = L["nets"][n]
            rows.append("<tr><td>%s</td><td>%.3f</td><td>%d</td><td>%+.3f</td><td class='%s'>%+.3f</td><td>%s</td></tr>" % (
                n.lstrip("/"), v["length"], v["vias"], v["to_longest"], "bad" if abs(v["to_ref"]) > 2.5 else "", v["to_ref"],
                "，".join("%s %.3f" % kv for kv in sorted(v["layers"].items()))))
        return ("<table>%s</table><p><b>窗口规则</b>（每根对 SDCLK ±2.5 mm，L = 这块板上 SDCLK 的实测长度）：DRC 报 %d 根超窗（%s）。"
                "这证明规则是生效的。</p>%s") % ("".join(rows), len(t["drc"]["length"]),
                                         "，".join(k.lstrip("/") for k in sorted(t["drc"]["length"], key=order)), checks)
    rows = ["<tr><th>网络</th><th>自然长度</th><th>要补</th><th>实补<br>（脚本算）</th><th>DRC 实测</th><th>脚本−DRC</th><th>离目标</th><th>没补上</th>"
            "<th>整弯</th><th>小弯</th><th>各弯摆幅</th><th>过孔</th><th>对 SDCLK</th><th>蛇形在哪（层、侧、起点→终点）</th></tr>"]
    for r in t["rows"]:
        rows.append("<tr><td>%s</td><td>%.3f</td><td>%.3f</td><td>%.3f</td><td>%.4f</td><td>%+.4f</td><td class='%s'>%+.3f</td><td class='%s'>%.3f</td>"
                    "<td>%d</td><td>%d</td><td>%s</td><td>%d</td><td class='%s'>%+.3f</td><td>%s</td></tr>" % (
                        r["net"], r["natural"], r["need"], r["added"], r["drc"], r["diff"], "bad" if abs(r["err"]) > 0.01 else "", r["err"],
                        "bad" if r["missing"] > 0.0005 else "", r["missing"], r["humps"], r["bumps"], r["amps"], r["vias"],
                        "bad" if abs(r["to_ref"]) > 2.5 else "", r["to_ref"], html.escape(r["where"])))
    s, p = t["summary"], t["params"]
    wb = t["window_before"]
    goal = ("<b>目标</b> %.3f mm（组里最长的自然长度）。" if p["goal"] == "equal" else "<b>只动 SDCLK</b>，补到 %.3f mm（其余 8 根的正中）。") % t["target"]
    return ("<p>%s半径 %.2f，摆幅 %.2f 起，腿间距 %.2f。守的间距：拐点到第一个圆弧 %.2f，到别的铜 %.3f，到规则区边 %.3f。"
            "补完后最长最短差 <b>%.3f</b> mm，没补到目标的 <b>%d</b> 根。脚本算的长度和 DRC 实测最多差 %.4f mm。</p><table>%s</table>"
            "<p><b>窗口规则</b>（每根对 SDCLK ±2.5 mm，L = %.4f）：同一份规则套在没补的板上报 %d 根%s，补完后报 %d 根。</p>"
            "<p><b>圆弧</b>（脚本逐个检查）：%d 个，半径 %s，最短 %.3f mm，和相邻线段的切向最大偏差 %.4f°，没接上的端点 %d 个；最短直线段 %.3f mm。</p>%s") % (
        goal, p["r"], p["amp"], p["leg_spacing"], p["end"], p["clr"], p["area_gap"], s["spread_after"], s["not_reached"], s["max_abs_diff"], "".join(rows),
        t["window_L"], len(wb), "（%s）" % "，".join(k.lstrip("/") for k in sorted(wb, key=order)) if wb else "", len(t["drc"]["length"]),
        a["arcs"], "，".join("%s × %d" % kv for kv in a["radii"].items()), a["shortest_arc"], a["worst_tangent_deg"],
        a["ends_without_one_neighbour"], a["shortest_segment"], checks)


data = {key: table(key) for key, _, _ in VARIANTS}
caps = {key: caption(key) for key, _, _ in VARIANTS}
page = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>等长蛇形原型：脚本画的圆弧蛇形</title>
<style>
 body { margin: 0; font: 14px/1.5 "Microsoft YaHei", "Segoe UI", sans-serif; background: #f4f4f1; color: #1c1c1a; }
 header { padding: 10px 16px; background: #fff; border-bottom: 1px solid #d8d8d2; }
 header b { font-size: 16px; } header span { color: #666; margin-left: 10px; }
 .row { padding: 6px 16px 0; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
 .row small { color: #666; width: 3.5em; }
 button { font: inherit; padding: 4px 10px; border: 1px solid #b9b9b0; background: #fff; border-radius: 4px; cursor: pointer; }
 button.on { background: #1c1c1a; color: #fff; border-color: #1c1c1a; }
 #mode button.on, #pick button.on { background: #e2683c; border-color: #e2683c; }
 #note { padding: 8px 16px 4px; color: #444; }
 #stage { padding: 0 16px; overflow: auto; }
 #stage.single img { max-width: 100%; max-height: 82vh; background: #fff; border: 1px solid #d8d8d2; cursor: zoom-in; }
 #stage.single.full img { max-width: none; max-height: none; cursor: zoom-out; }
 #strip { display: grid; gap: 8px; align-items: start; }
 #strip figure { margin: 0; background: #fff; border: 1px solid #d8d8d2; }
 #strip img { width: 100%; display: block; cursor: pointer; }
 #strip figcaption { padding: 4px 8px; font-size: 12px; line-height: 1.4; border-bottom: 1px solid #e6e6e0; }
 #strip figcaption b { font-size: 14px; }
 #metrics { padding: 4px 16px 40px; overflow-x: auto; }
 table { border-collapse: collapse; background: #fff; } th, td { border: 1px solid #d8d8d2; padding: 2px 8px; text-align: right; white-space: nowrap; }
 th { background: #ecece7; } td:first-child, td:last-child { text-align: left; } td.bad { background: #f6c9c0; font-weight: bold; }
 ul { margin: 4px 0; }
</style></head><body>
<header><b>等长蛇形原型（一次性，issue 15）</b><span>← → 换组或换方案，↑ ↓ 换视图。图只作定性参考，数字都来自板文件（单位 mm）。表里红底 = 没补到目标或超出 ±2.5。
5 mm 和 8 mm 的图取景和比例不同，不能互相比大小。</span></header>
<div class="row" id="mode"></div><div class="row" id="pick"></div><div class="row" id="views"></div>
<div id="note"></div><div id="stage"></div><div id="metrics"></div>
<script>
const VARIANTS = __VARIANTS__, GROUPS = __GROUPS__, VIEWS = __VIEWS__, TABLES = __TABLES__, CAPS = __CAPS__;
const q = new URLSearchParams(location.search);
let mode = q.get('variant') ? 'single' : 'strip';
let v = Math.max(0, VARIANTS.findIndex(x => x[0] === q.get('variant'))), g = Math.min(GROUPS.length - 1, Math.max(0, parseInt(q.get('group') || '0'))),
    w = Math.max(0, VIEWS.findIndex(x => x[0] === q.get('view')));
const label = k => VARIANTS.find(x => x[0] === k);
function btn(text, on, js) { return `<button class="${on ? 'on' : ''}" onclick="${js}">${text}</button>`; }
function show() {
  document.getElementById('mode').innerHTML = '<small>看法</small>' + btn('并排', mode === 'strip', "mode='strip';show()") + btn('单张 + 表', mode === 'single', "mode='single';show()");
  document.getElementById('views').innerHTML = '<small>视图</small>' + VIEWS.map((x, i) => btn(x[1], i === w, `w=${i};show()`)).join('');
  const stage = document.getElementById('stage');
  if (mode === 'strip') {
    document.getElementById('pick').innerHTML = '<small>哪一组</small>' + GROUPS.map((x, i) => btn(x[0], i === g, `g=${i};show()`)).join('');
    document.getElementById('note').textContent = '同一个视图、同一个取景，点图进入那个方案的单张和长度表。';
    stage.className = '';
    stage.innerHTML = `<div id="strip" style="grid-template-columns: repeat(${GROUPS[g][1].length}, 1fr)">` + GROUPS[g][1].map(k =>
      `<figure><figcaption><b>${label(k)[1]}</b><br>${CAPS[k]}</figcaption><img src="out/${k}/${VIEWS[w][0]}.png" alt="${k}" onclick="v=${VARIANTS.findIndex(x => x[0] === k)};mode='single';show()"></figure>`).join('') + '</div>';
    document.getElementById('metrics').innerHTML = '';
    try { history.replaceState(null, '', '?group=' + g + '&view=' + VIEWS[w][0]); } catch (e) {}
  } else {
    document.getElementById('pick').innerHTML = '<small>方案</small>' + VARIANTS.map((x, i) => btn(x[1], i === v, `v=${i};show()`)).join('');
    document.getElementById('note').textContent = VARIANTS[v][1] + '：' + VARIANTS[v][2] + '　KiCad 工程：out/' + VARIANTS[v][0] + '/lentune.kicad_pro';
    stage.className = 'single';
    stage.innerHTML = `<img src="out/${VARIANTS[v][0]}/${VIEWS[w][0]}.png" alt="" onclick="this.parentNode.classList.toggle('full')">`;
    document.getElementById('metrics').innerHTML = TABLES[VARIANTS[v][0]];
    try { history.replaceState(null, '', '?variant=' + VARIANTS[v][0] + '&view=' + VIEWS[w][0]); } catch (e) {}
  }
}
document.addEventListener('keydown', e => {
  const step = d => { if (mode === 'strip') g = (g + d + GROUPS.length) % GROUPS.length; else v = (v + d + VARIANTS.length) % VARIANTS.length; };
  if (e.key === 'ArrowRight') step(1); else if (e.key === 'ArrowLeft') step(-1);
  else if (e.key === 'ArrowDown') w = (w + 1) % VIEWS.length; else if (e.key === 'ArrowUp') w = (w + VIEWS.length - 1) % VIEWS.length; else return;
  e.preventDefault(); show();
});
show();
</script></body></html>
"""
page = (page.replace("__VARIANTS__", json.dumps(VARIANTS, ensure_ascii=False)).replace("__VIEWS__", json.dumps(VIEWS, ensure_ascii=False))
        .replace("__GROUPS__", json.dumps(GROUPS, ensure_ascii=False)).replace("__CAPS__", json.dumps(caps, ensure_ascii=False))
        .replace("__TABLES__", json.dumps(data, ensure_ascii=False)))
open(os.path.join(HERE, "compare.html"), "w", encoding="utf-8").write(page)
print("wrote compare.html")
