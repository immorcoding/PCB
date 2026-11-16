"""PROTOTYPE (issue 16): write compare.html, a page that flips between the variants on the same view.

    D:\\KiCad\\bin\\python.exe make_compare.py        (after build.sh; reads out/*/metrics.json)

Open compare.html by double click. Left / right arrows change the variant, up / down the view.
"""
import html, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
VARIANTS = [
    ("a_sketch", "A 草图 + 脚本", "外形由草图给出（sketch.txt），脚本只检查和生成。L3 块间缝 0.5 mm。"),
    ("b_krt", "B 现成工具", "KiCadRoutingTools 0.24.0 的 route_planes.py：自动分割 L3、四层铺地。它没有外层局部铜皮的功能。"),
    ("a_gap10", "A 缝 1.0", "同 A，L3 块间缝改成 1.0 mm。"),
    ("a_solid", "A 全部全连接", "同 A，插件焊盘也全连接（现行规则是插件花焊盘、贴片全连接）。"),
    ("a_thermal", "A 全部花焊盘", "同 A，贴片焊盘也用花焊盘。"),
]
VIEWS = [
    ("L3", "L3 电源层，全板"),
    ("L3_mcu", "L3，MCU 和 SDRAM 下方"),
    ("L1", "L1，全板"),
    ("L1_power", "L1，电源区"),
    ("L1_audio", "L1，音频区"),
    ("L2_mcu", "L2 地层，MCU 和 SDRAM 下方"),
]


def table(m):
    if not m:
        return "<p>没有数据</p>"
    rows = ["<tr><th>层</th><th>网络</th><th>铺铜区</th><th>外形边数</th><th>不在 45° 格上的边</th><th>面积 mm²</th>"
            "<th>碎片数</th><th>没有来源的碎片</th><th>最窄连接 mm</th><th>最窄处在</th></tr>"]
    for r in sorted(m["zones"], key=lambda r: (r["layer"], -r["area"])):
        nk = r["neck_outside_bga"]
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%d</td><td class='%s'>%d</td><td>%.1f</td><td>%d</td><td>%d</td><td>%s</td><td>%s</td></tr>" % (
            r["layer"], html.escape(r["net"]), html.escape(r["zone"] or "（无名）"), r["outline_edges"],
            "bad" if r["off_angle_edges"] else "", r["off_angle_edges"], r["area"], r["pieces"], r["unfed_pieces"],
            "—" if nk is None else ("≥ 6" if nk >= 6 else "%.2f" % nk), html.escape(" ".join(r["neck_at"]))))
    gaps = "，".join("%s %s / %s：%.3f" % (g["layer"], g["a"], g["b"], g["gap"]) for g in m["gaps"]
                    if g["layer"] == "L3" or "GND" not in (g["a"], g["b"]))
    gnd = [g["gap"] for g in m["gaps"] if g["layer"] == "L1" and "GND" in (g["a"], g["b"])]
    d = m["drc"]
    un = "，".join("%s %d" % kv for kv in d.get("unconnected_copper_nets", {}).items()) or "0"
    vio = "，".join("%s %d" % kv for kv in d.get("violations", {}).items())
    miss = "，".join("%s %s %d/%d" % (u["layer"], u["net"], u["not_reached"], u["copper"]) for u in m["not_reached"] if u["not_reached"]) or "无"
    return ("<table>%s</table><p><b>不同网络的铜之间的最小距离（mm）</b>：%s%s</p>"
            "<p><b>铜皮类网络的未连接（KiCad DRC，重新填充后）</b>：%s　<b>本网络的过孔 / 插件脚没落在自己铜皮里</b>：%s</p>"
            "<p><b>DRC 各项</b>：%s</p>") % (
        "".join(rows), gaps, ("；L1 局部铜皮到铺地 %.3f" % min(gnd)) if gnd else "", un, miss, vio)


data = {}
for key, _, _ in VARIANTS:
    p = os.path.join(HERE, "out", key, "metrics.json")
    data[key] = table(json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None)

page = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>铜皮区域原型：草图脚本 对 现成工具</title>
<style>
 body { margin: 0; font: 14px/1.5 "Microsoft YaHei", "Segoe UI", sans-serif; background: #f4f4f1; color: #1c1c1a; }
 header { padding: 10px 16px; background: #fff; border-bottom: 1px solid #d8d8d2; }
 header b { font-size: 16px; } header span { color: #666; margin-left: 10px; }
 #views { padding: 8px 16px; display: flex; flex-wrap: wrap; gap: 6px; }
 #views button, #bar button { font: inherit; padding: 4px 10px; border: 1px solid #b9b9b0; background: #fff; border-radius: 4px; cursor: pointer; }
 #views button.on { background: #1c1c1a; color: #fff; border-color: #1c1c1a; }
 #stage { padding: 0 16px; overflow: auto; } #stage img { max-width: 100%; height: auto; background: #fff; border: 1px solid #d8d8d2; }
 #stage.full img { max-width: none; }
 #note { padding: 6px 16px; color: #444; }
 #metrics { padding: 4px 16px 90px; overflow-x: auto; }
 table { border-collapse: collapse; background: #fff; } th, td { border: 1px solid #d8d8d2; padding: 2px 8px; text-align: right; white-space: nowrap; }
 th { background: #ecece7; } td:nth-child(-n+3), td:last-child { text-align: left; } td.bad { background: #f6c9c0; font-weight: bold; }
 #bar { position: fixed; left: 50%; bottom: 14px; transform: translateX(-50%); background: #1c1c1a; color: #fff; padding: 8px 12px;
        border-radius: 22px; box-shadow: 0 4px 14px rgba(0,0,0,.35); display: flex; align-items: center; gap: 10px; white-space: nowrap; }
 #bar button { background: #3a3a36; color: #fff; border-color: #55554f; border-radius: 14px; } #bar button.on { background: #e2683c; border-color: #e2683c; }
 #bar small { color: #bbb; }
</style></head><body>
<header><b>铜皮区域原型（一次性，issue 16）</b><span>同一块占位板，同一组视图。← → 换方案，↑ ↓ 换视图，点图切换原始大小。图只作定性参考，数字见下表。</span></header>
<div id="views"></div><div id="note"></div><div id="stage"><img id="img" alt=""></div><div id="metrics"></div>
<div id="bar"></div>
<script>
const VARIANTS = __VARIANTS__, VIEWS = __VIEWS__, TABLES = __TABLES__;
const q = new URLSearchParams(location.search);
let v = Math.max(0, VARIANTS.findIndex(x => x[0] === q.get('variant'))), w = Math.max(0, VIEWS.findIndex(x => x[0] === q.get('view')));
function show() {
  document.getElementById('img').src = 'out/' + VARIANTS[v][0] + '/' + VIEWS[w][0] + '.png';
  document.getElementById('note').textContent = VARIANTS[v][1] + '：' + VARIANTS[v][2];
  document.getElementById('metrics').innerHTML = TABLES[VARIANTS[v][0]];
  document.getElementById('views').innerHTML = VIEWS.map((x, i) => `<button class="${i === w ? 'on' : ''}" onclick="w=${i};show()">${x[1]}</button>`).join('');
  document.getElementById('bar').innerHTML = '<small>方案</small>' + VARIANTS.map((x, i) => `<button class="${i === v ? 'on' : ''}" onclick="v=${i};show()">${x[1]}</button>`).join('');
  history.replaceState(null, '', '?variant=' + VARIANTS[v][0] + '&view=' + VIEWS[w][0]);
}
document.addEventListener('keydown', e => {
  if (e.key === 'ArrowRight') v = (v + 1) % VARIANTS.length; else if (e.key === 'ArrowLeft') v = (v + VARIANTS.length - 1) % VARIANTS.length;
  else if (e.key === 'ArrowDown') w = (w + 1) % VIEWS.length; else if (e.key === 'ArrowUp') w = (w + VIEWS.length - 1) % VIEWS.length; else return;
  e.preventDefault(); show();
});
document.getElementById('img').onclick = () => document.getElementById('stage').classList.toggle('full');
show();
</script></body></html>
"""
page = (page.replace("__VARIANTS__", json.dumps(VARIANTS, ensure_ascii=False)).replace("__VIEWS__", json.dumps(VIEWS, ensure_ascii=False))
        .replace("__TABLES__", json.dumps(data, ensure_ascii=False)))
open(os.path.join(HERE, "compare.html"), "w", encoding="utf-8").write(page)
print("wrote compare.html")
