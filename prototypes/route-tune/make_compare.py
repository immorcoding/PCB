"""PROTOTYPE (throwaway, issue 21): write compare.html and fill the AUTO blocks of README.md.

    D:\\KiCad\\bin\\python.exe make_compare.py              (after the variants are built with build.py)
    options:  --render        redraw every comparison picture (default: only the missing / outdated ones)
              --no-remeasure  do not rerun review/remeasure.py (reuse the result in out/compare_extra.json)

Adapted from prototypes/length-tuning/make_compare.py and fill_readme.py. One script does both, so the page
and the README cannot disagree. Every number comes from out/<variant>/metrics.json (and tune.json for the
per-block list). Three supplementary numbers are measured here from the saved boards, the same way for every
variant, and are labelled as such: bus length under each package body, the hull with the package outlines
shrunk by 0.1 mm, and the finding count of the independent re-measurement (review/remeasure.py).

Pictures: the variants' own pictures use per-variant extra views and one variant redefines "north", so this
script draws its own set with lib/render.draw: the SAME frame and scale for every variant
(out/<variant>/cmp_<frame>_<layer>.png). Pictures are qualitative only (PROC-14).

A variant whose metrics.json is older than its sources stops the script (rebuild it with build.py first).
"""
import glob, html, json, math, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
import pcbnew                                               # noqa: E402
import metrics as libmetrics, render                        # noqa: E402
from common import BODY, NAME, NETS, LNUM, Lp, mm, short, in_rect, track_pts, check_lock   # noqa: E402

VARIANTS = [  # key, label on the page
    ("0_base", "0 底板"),
    ("1_baseline", "1 基线：走完再补"),
    ("2_detour_first", "2 先绕后补"),
    ("3_under_sdram", "3 蛇形在 SDRAM 下"),
    ("4_combined", "4 综合（0.3）"),
    ("4b_combined_p05", "4b 综合（0.5）"),
    ("5_no_detour", "5 不绕远，蛇形成块"),
]
KEYS = [k for k, _ in VARIANTS]
BASELINE = "1_baseline"
COORD = ["2_detour_first", "3_under_sdram", "4_combined", "4b_combined_p05", "5_no_detour"]      # the coordinated variants
NEW, REF = "5_no_detour", "4_combined"      # the variant built after the user's verdict of 2026-11-17, and the one it is derived from
GROUPS = [
    ("基线、综合、不绕远", ["1_baseline", "4_combined", "5_no_detour"]),
    ("综合 对 不绕远", ["4_combined", "5_no_detour"]),
    ("蛇形在 SDRAM 下 对 不绕远", ["3_under_sdram", "5_no_detour"]),
    ("基线和三种协调做法", ["1_baseline", "2_detour_first", "3_under_sdram", "4_combined"]),
    ("全部 %d 块" % len(KEYS), KEYS),
    ("底板 → 基线", ["0_base", "1_baseline"]),
    ("基线 对 综合方案", ["1_baseline", "4_combined"]),
    ("基线 对 蛇形在 SDRAM 下", ["1_baseline", "3_under_sdram"]),
    ("腿间距 0.3 对 0.5（同样的走线）", ["4_combined", "4b_combined_p05"]),
]
FRAMES = [  # key, label, x0, y0, x1, y1, px per mm : identical for every variant
    ("whole", "整组线", 6.5, 2.5, 32.5, 28.5, 40),
    ("gap", "两颗芯片之间", 17.0, 2.5, 25.0, 28.5, 80),
    ("sdram", "SDRAM 封装下面", 21.5, 8.0, 31.5, 24.0, 100),
    ("mcu", "MCU 下方和左下角", 7.0, 15.5, 23.5, 28.5, 75),
]
LAYERS = [("all", "三层叠在一起", ("L1", "L4", "L6")), ("L1", "L1（顶层）", ("L1",)), ("L4", "L4（内层）", ("L4",)), ("L6", "L6（底层）", ("L6",))]
EXTRA = os.path.join(HERE, "out", "compare_extra.json")
order = lambda n: (0, 0) if "CLK" in n else (2, int(n[-1])) if "NBL" in n else (1, int(re.sub(r"\D", "", n) or 0))


# ---------------------------------------------------------------- inputs
def sources(key):
    """Files a variant's metrics.json must not be older than."""
    d = os.path.join(HERE, "variants", key)
    src = glob.glob(os.path.join(d, "*.py"))
    text = "".join(open(f, encoding="utf-8").read() for f in src)
    if "plan4" in text:
        src.append(os.path.join(HERE, "variants", "4_combined", "plan4.py"))
        text += open(src[-1], encoding="utf-8").read()
    for f in glob.glob(os.path.join(HERE, "lib", "*.py")):
        if os.path.basename(f) != "bundle.py" or "bundle" in text:
            src.append(f)
    return src


def load_all():
    M, T = {}, {}
    for key in KEYS:
        f = os.path.join(HERE, "out", key, "metrics.json")
        if not os.path.isfile(f):
            raise SystemExit("%s: no metrics.json. Build it first: D:/KiCad/bin/python.exe build.py %s" % (key, key))
        stale = [os.path.relpath(s, HERE) for s in sources(key) if os.path.getmtime(s) > os.path.getmtime(f) + 1]
        if stale:
            raise SystemExit("%s: metrics.json is older than %s. Rebuild: D:/KiCad/bin/python.exe build.py %s" % (key, ", ".join(stale), key))
        M[key] = json.load(open(f, encoding="utf-8"))
        T[key] = json.load(open(os.path.join(HERE, "out", key, "tune.json"), encoding="utf-8"))
    return M, T


def under_body(B):
    """Bus track length (mm) whose centre line lies inside each package outline, per layer. Supplementary."""
    out = {r: {"L1": 0.0, "L4": 0.0, "L6": 0.0} for r in BODY}
    for t in B.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T or not t.GetNetname().startswith("/FMC_"):
            continue
        l = LNUM[t.GetLayer()]
        pl = track_pts(t, 0.02)
        for a, c in zip(pl, pl[1:]):
            n = max(1, int(math.dist(a, c) / 0.025))
            for i in range(n):
                p = (a[0] + (c[0] - a[0]) * (i + 0.5) / n, a[1] + (c[1] - a[1]) * (i + 0.5) / n)
                for r, R in BODY.items():
                    if in_rect(p, R):
                        out[r][l] += math.dist(a, c) / n
    return {r: {**{l: round(v, 2) for l, v in d.items()}, "total": round(sum(d.values()), 2)} for r, d in out.items()}


def hull_shrunk(B, by=0.1):
    """lib/metrics.space() again with both package outlines shrunk by 0.1 mm: how much the hull depends on
    copper that runs just inside an outline (review finding on 3_under_sdram). Supplementary."""
    keep = dict(libmetrics.BODY)
    try:
        libmetrics.BODY = {r: (R[0] + by, R[1] + by, R[2] - by, R[3] - by) for r, R in keep.items()}
        s = libmetrics.space(B)
    finally:
        libmetrics.BODY = keep
    return {"hull": s["bus_hull_area_mm2"], "bbox": s["bus_bbox_mm"], "swept": s["bus_swept_area_mm2"]["all"]}


def remeasure(key):
    """Run the reviewers' independent re-measurement (no lib/, no pcbnew) and return its finding count."""
    r = subprocess.run([sys.executable, os.path.join(HERE, "review", "remeasure.py"), key], cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"FINDINGS \((\d+)\)", r.stdout or "")
    lines = (r.stdout or "").split("FINDINGS", 1)[-1].strip().splitlines()[1:] if m else []
    return {"findings": int(m.group(1)) if m else None, "lines": [l.strip() for l in lines if l.strip()][:20]}


def measure_and_render(M, force, do_remeasure):
    old = json.load(open(EXTRA, encoding="utf-8")) if os.path.isfile(EXTRA) else {}
    X = {}
    for key in KEYS:
        out = os.path.join(HERE, "out", key)
        check_lock(out)
        pcb = os.path.join(out, NAME + ".kicad_pcb")
        B = pcbnew.LoadBoard(pcb)
        X[key] = {"under_body_mm": under_body(B), "outline_shrunk_0.1": hull_shrunk(B)}
        if do_remeasure or key not in old or "remeasure" not in old[key]:
            X[key]["remeasure"] = remeasure(key)
        else:
            X[key]["remeasure"] = old[key]["remeasure"]
        n = 0
        for fk, _, x0, y0, x1, y1, sc in FRAMES:
            for lk, _, show in LAYERS:
                f = os.path.join(out, "cmp_%s_%s.png" % (fk, lk))
                if force or not os.path.isfile(f) or os.path.getmtime(f) < max(os.path.getmtime(pcb), os.path.getmtime(os.path.join(HERE, "lib", "render.py"))):
                    render.draw(B, show, x0, y0, x1, y1, sc, f); n += 1
        print("%s: %d pictures drawn, remeasure findings %s" % (key, n, X[key]["remeasure"]["findings"]))
    json.dump(X, open(EXTRA, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return X


# ---------------------------------------------------------------- derived numbers (all from metrics.json / tune.json)
def unequal_blocks(m):
    """Serpentine blocks whose humps are not all the same height (convention of 2026-11-17)."""
    out = []
    for n in NETS:
        for a in m["nets"][n]["amplitudes_mm"]:
            if max(a) - min(a) > 0.0015:
                out.append((short(n), a))
    return out


def blocks(t):
    """One row per serpentine block (tune.json): straight used, height, gain, footprint = straight x width."""
    out = []
    for b in t["blocks"]:
        used = math.dist(b["from"], b["to"])
        width = max(b["amps"]) * (2 if b["side"] == "both" else 1)
        out.append({"net": short(b["net"]), "layer": b["layer"], "side": b["side"], "pitch": b["pitch"], "humps": b["humps"] + b["bumps"],
                    "amps": b["amps"], "gain": b["gain"], "used": used, "width": width, "foot": used * width, "under": b["under_sdram"],
                    "inside": b["inside_area"]})
    return sorted(out, key=lambda r: order(r["net"]))


def comp(m):
    """Where the length comes from: direct + via height + in-plane detour + serpentine = total."""
    t = m["totals"]
    via = sum(v["via_mm"] for v in m["nets"].values())
    return {"direct": t["total_direct_mm"], "via": via, "plane": t["total_detour_mm"] - via, "serp": t["total_serpentine_mm"], "total": t["total_length_mm"]}


def rel(v, base, unit="", prec=1):
    d = v - base
    return "%+.*f%s（%+.0f%%）" % (prec, d, unit, 100 * d / base) if base else "—"


SIDE = {"N": "北", "S": "南", "E": "东", "W": "西", "NE": "东北", "NW": "西北", "SE": "东南", "SW": "西南", "both": "两侧交替"}


def rows(M, X):
    """The comparison table: [(label, [cell per variant], [bad flag per variant])]. Plain text cells."""
    R = []

    def add(label, fn, bad=None):
        R.append((label, [fn(M[k], X[k], k) for k in KEYS], [bool(bad and bad(M[k], X[k], k)) for k in KEYS]))

    b = M[BASELINE]["space"]
    r4 = M[REF]["space"]
    T = lambda m: m["totals"]
    S = lambda m: m["space"]
    C = lambda m: m["checks"]
    add("在窗口内（±2.5 mm，共 19 根）", lambda m, x, k: "%d / %d" % (T(m)["in_window_count"], T(m)["nets"]), lambda m, x, k: T(m)["in_window_count"] < T(m)["nets"])
    add("离 SDCLK 最远的一根", lambda m, x, k: "%s %+.3f" % (short(T(m)["worst_net"]), T(m)["worst_delta_mm"]), lambda m, x, k: abs(T(m)["worst_delta_mm"]) > 2.5)
    add("离窗口边最近还剩", lambda m, x, k: "%.3f" % (2.5 - abs(T(m)["worst_delta_mm"])) if abs(T(m)["worst_delta_mm"]) <= 2.5 else "超出 %.3f" % (abs(T(m)["worst_delta_mm"]) - 2.5))
    add("SDCLK 长度（窗口）", lambda m, x, k: "%.3f（%.3f–%.3f）" % (T(m)["window_L_mm"], T(m)["window_mm"][0], T(m)["window_mm"][1]))
    add("最长 / 最短", lambda m, x, k: "%.3f / %.3f" % (T(m)["longest_mm"], T(m)["shortest_mm"]))
    add("凸包面积 mm²", lambda m, x, k: "%.1f" % S(m)["bus_hull_area_mm2"])
    add("　比基线", lambda m, x, k: "—" if k == BASELINE else rel(S(m)["bus_hull_area_mm2"], b["bus_hull_area_mm2"]))
    add("　比 4_combined", lambda m, x, k: "—" if k == REF else rel(S(m)["bus_hull_area_mm2"], r4["bus_hull_area_mm2"]))
    add("外包矩形 宽 × 高", lambda m, x, k: "%.2f × %.2f" % tuple(S(m)["bus_bbox_mm"]))
    add("窄条里上下占（通道宽度）", lambda m, x, k: "%.2f" % S(m)["channel_width_mm"])
    add("　比基线", lambda m, x, k: "—" if k == BASELINE else rel(S(m)["channel_width_mm"], b["channel_width_mm"], prec=2))
    add("　比 4_combined", lambda m, x, k: "—" if k == REF else rel(S(m)["channel_width_mm"], r4["channel_width_mm"], prec=2))
    add("　其中 L1 / L4 / L6", lambda m, x, k: " / ".join("%.2f" % S(m)["channel_width_by_layer_mm"][l] for l in ("L1", "L4", "L6")))
    add("扫过的面积 mm²（三层合并）", lambda m, x, k: "%.1f" % S(m)["bus_swept_area_mm2"]["all"])
    add("　比基线", lambda m, x, k: "—" if k == BASELINE else rel(S(m)["bus_swept_area_mm2"]["all"], b["bus_swept_area_mm2"]["all"]))
    add("　比 4_combined", lambda m, x, k: "—" if k == REF else rel(S(m)["bus_swept_area_mm2"]["all"], r4["bus_swept_area_mm2"]["all"]))
    add("　其中 L1 / L4 / L6", lambda m, x, k: " / ".join("%.1f" % S(m)["bus_swept_area_mm2"][l] for l in ("L1", "L4", "L6")))
    add("蛇形处数 / 弯数", lambda m, x, k: "%d / %d" % (T(m)["n_serpentines"], T(m)["n_humps"]))
    add("蛇形补的长度合计", lambda m, x, k: "%.2f" % T(m)["total_serpentine_mm"])
    add("绕远合计（含过孔高度）", lambda m, x, k: "%.2f" % T(m)["total_detour_mm"])
    add("　其中过孔高度 / 平面内", lambda m, x, k: "%.1f / %.1f" % (comp(m)["via"], comp(m)["plane"]))
    add("SDRAM 封装下面的蛇形占比", lambda m, x, k: "%.0f%%" % (100 * T(m)["serpentine_under_sdram_share"]) if T(m)["n_serpentines"] else "—")
    add("腿间距：数据 / SDCLK", lambda m, x, k: "%.1f / %.1f" % (m["pitch"]["default"], m["pitch"].get("SDCLK", m["pitch"]["default"])) if T(m)["n_serpentines"] else "—")
    add("最大摆幅", lambda m, x, k: "%.2f" % max(v["max_amplitude_mm"] for v in m["nets"].values()) if T(m)["n_serpentines"] else "—")
    add("块内不等高的蛇形块", lambda m, x, k: ("%d（%s）" % (len(unequal_blocks(m)), "、".join(n for n, _ in unequal_blocks(m))) if unequal_blocks(m) else "0"),
        lambda m, x, k: bool(unequal_blocks(m)))
    add("过孔：每根最多 / 合计", lambda m, x, k: "%d / %d" % (T(m)["max_vias"], T(m)["total_vias"]), lambda m, x, k: T(m)["max_vias"] > 3)
    add("DRC：未连接 / 长度超窗 / 其他", lambda m, x, k: "%d / %d / %d" % (C(m)["drc"]["unconnected"], C(m)["drc"]["by_type"].get("length_out_of_range", 0), len(C(m)["drc"]["unexplained"])),
        lambda m, x, k: C(m)["drc"]["unconnected"] or C(m)["drc"]["unexplained"] or C(m)["drc"]["by_type"].get("length_out_of_range", 0))
    add("规则文件生效 / 长度规则匹配的网络数", lambda m, x, k: "%s / %s" % ("OK" if C(m)["rule_file_canary"]["ok"] else "没生效", "，".join(str(v) for v in C(m)["rules_matched"]["per_length_rule"].values())),
        lambda m, x, k: not (C(m)["rule_file_canary"]["ok"] and C(m)["rules_matched"]["ok"]))
    add("track_shape.py：非 45° / 阶梯 / 小倒角直角 / 2 mm 内 3 个以上折弯 / 短线", lambda m, x, k: " / ".join(str(C(m)["track_shape"][i]) for i in ("off-grid", "staircase", "sharp", "crowded", "tiny")),
        lambda m, x, k: any(C(m)["track_shape"][i] for i in ("staircase", "sharp", "tiny")) or (C(m)["track_shape"]["off-grid"] and C(m)["geometry"]["off_grid_exact"]))
    add("带圆弧的几何检查：间距不够 / 不是单线 / 纳米级非 0-45-90 / 过孔处折回", lambda m, x, k: " / ".join(str(len(C(m)["geometry"][i])) for i in ("clearance_violations", "path_problems", "off_grid_exact", "via_turn_90_or_more")),
        lambda m, x, k: any(C(m)["geometry"][i] for i in ("clearance_violations", "path_problems", "off_grid_exact", "via_turn_90_or_more")))
    sc = lambda m: C(m)["serpentine_clearances"]
    add("蛇形到别的网络，最近", lambda m, x, k: "%.3f（%s 对 %s，%s）" % (sc(m)["smallest_to_other_net"]["gap"], sc(m)["smallest_to_other_net"]["net"], sc(m)["smallest_to_other_net"]["other"], sc(m)["smallest_to_other_net"]["layer"]) if sc(m)["smallest_to_other_net"] else "—")
    add("规则区外的蛇形到规则区边，最近", lambda m, x, k: "%.3f（%s）" % (sc(m)["smallest_to_rule_area_edge_from_outside"]["gap"], sc(m)["smallest_to_rule_area_edge_from_outside"]["net"]) if sc(m)["smallest_to_rule_area_edge_from_outside"] else "—")
    add("拐点到第一个圆弧，最短", lambda m, x, k: "%.3f" % sc(m)["shortest_straight_between_bend_and_arc"] if sc(m)["shortest_straight_between_bend_and_arc"] else "—")
    add("不同网络之间最近（整块板）", lambda m, x, k: "%.3f（%s 对 %s，%s）" % tuple(C(m)["geometry"]["min_gap_all"][i] for i in ("gap", "net", "other", "layer")))
    add("独立重量 review/remeasure.py 的出入", lambda m, x, k: "没跑成" if x["remeasure"]["findings"] is None else "%d 处" % x["remeasure"]["findings"], lambda m, x, k: x["remeasure"]["findings"] != 0)
    add("补充：SDRAM 封装下面的总线长度（L1 / L4 / L6）", lambda m, x, k: "%.1f（%s）" % (x["under_body_mm"]["U2"]["total"], " / ".join("%.1f" % x["under_body_mm"]["U2"][l] for l in ("L1", "L4", "L6"))))
    add("补充：封装外形内缩 0.1 mm 再算的凸包 mm²", lambda m, x, k: "%.1f" % x["outline_shrunk_0.1"]["hull"])
    add("　比基线同口径", lambda m, x, k: "—" if k == BASELINE else rel(x["outline_shrunk_0.1"]["hull"], X[BASELINE]["outline_shrunk_0.1"]["hull"]))
    add("　比 4_combined 同口径", lambda m, x, k: "—" if k == REF else rel(x["outline_shrunk_0.1"]["hull"], X[REF]["outline_shrunk_0.1"]["hull"]))
    add("完整构建一次（秒）", lambda m, x, k: "%s" % m.get("build_seconds", "—"), lambda m, x, k: (m.get("build_seconds") or 0) > 600)
    return R


# ---------------------------------------------------------------- HTML pieces
E = html.escape


def metrics_html(R):
    h = ["<table id='mt'><thead><tr><th>指标（mm、mm²）</th>%s</tr></thead><tbody>" % "".join("<th data-v='%s'>%s</th>" % (k, E(l)) for k, l in VARIANTS)]
    for label, cells, bad in R:
        h.append("<tr><td>%s</td>%s</tr>" % (E(label), "".join("<td data-v='%s'%s>%s</td>" % (k, " class='bad'" if bd else "", E(c)) for k, c, bd in zip(KEYS, cells, bad))))
    return "".join(h) + "</tbody></table>"


def net_table(m, t):
    T, C = m["totals"], m["checks"]
    h = ["<table class='nets'><thead><tr><th>网络</th><th>MCU 球 → SDRAM</th><th>长度<br>(DRC)</th><th>比 SDCLK</th><th>过孔</th><th>各层长度</th><th>直连<br>最短</th>"
         "<th>不算蛇形<br>的走线</th><th>绕远</th><th>蛇形<br>补的</th><th>处 / 弯</th><th>腿间距</th><th>各块的摆幅</th><th>SDRAM 下<br>的蛇形</th><th>为什么这样走</th></tr></thead><tbody>"]
    for n in NETS:
        v = m["nets"][n]
        amps = "；".join("%d × %.3f" % (len(a), a[0]) if max(a) - min(a) <= 0.0015 else "不等高：" + "、".join("%.2f" % x for x in a) for a in v["amplitudes_mm"]) or "—"
        why = v["why"] + ("　【%s】" % v["tuning_note"] if v["tuning_note"] else "")
        h.append("<tr><td>%s</td><td>%s → %s %s</td><td>%.3f</td><td class='%s'>%+.3f</td><td>%d</td><td>%s</td><td>%.3f</td><td>%.3f</td><td>%.3f</td><td>%.3f</td><td>%d / %d</td><td>%s</td>"
                 "<td class='%s'>%s</td><td>%.3f</td><td class='why'>%s</td></tr>" % (
                     short(n), v["mcu_ball"], v["sdram_ball"], v["sdram_pin"], v["length_mm"], "" if v["in_window"] else "bad", v["delta_to_sdclk_mm"], v["vias"],
                     "，".join("%s %.2f" % kv for kv in v["layers"].items()), v["direct_mm"], v["route_mm"], v["detour_mm"], v["serpentine_mm"], v["n_serpentines"], v["n_humps"],
                     "、".join("%.1f" % p for p in v["pitch_mm"]) or "—", "bad" if "不等高" in amps else "", E(amps), v["serpentine_under_sdram_mm"], E(why)))
    ts = C["track_shape"]
    cm = comp(m)
    foot = ("<p>窗口：SDCLK = %.3f，允许 %.3f 到 %.3f；在窗口内 %d / %d。长度合计 %.1f = 直连最短 %.1f + 过孔高度 %.1f + 平面内绕远 %.1f + 蛇形 %.1f。</p>"
            "<p><b>track_shape.py</b>（不认识圆弧）：非 45° %d，阶梯 %d，小倒角直角 %d，2 mm 内 3 个以上折弯 %d，短线 %d。%s</p>") % (
        T["window_L_mm"], T["window_mm"][0], T["window_mm"][1], T["in_window_count"], T["nets"], cm["total"], cm["direct"], cm["via"], cm["plane"], cm["serp"],
        ts["off-grid"], ts["staircase"], ts["sharp"], ts["crowded"], ts["tiny"],
        ("报出来的几处：" + "；".join(E(l.replace("/FMC_", "")) for l in ts["lines"])) if ts["lines"] else "")
    return "".join(h) + "</tbody></table>" + foot


def caption(m):
    T, S = m["totals"], m["space"]
    return "窗口内 %d / %d；凸包 %.1f mm²，窄条里上下占 %.2f；蛇形 %d 处 %.1f mm；绕远 %.1f mm" % (
        T["in_window_count"], T["nets"], S["bus_hull_area_mm2"], S["channel_width_mm"], T["n_serpentines"], T["total_serpentine_mm"], T["total_detour_mm"])


def equal_note(M):
    parts = []
    for k, l in VARIANTS:
        u = unequal_blocks(M[k])
        n = M[k]["totals"]["n_serpentines"]
        parts.append("<li><b>%s</b>：%s</li>" % (E(l), "没有蛇形" if not n else "%d 块全部块内等高，例外 0 处" % n if not u else
                                               "%d 块里 %d 块不等高（%s）。这不是约定允许的那种例外：基线用的是自动补线，是在“块内等高”这条更正之前写的，没有重做，原样留作对照。"
                                               % (n, len(u), "；".join("%s：%s" % (a, "、".join("%.2f" % x for x in b)) for a, b in u))))
    return "<ul>%s</ul>" % "".join(parts)


PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>走线和等长一起规划：对比页</title>
<style>
 :root { --bg: #f4f4f1; --panel: #ffffff; --ink: #1c1c1a; --mute: #63635e; --line: #d8d8d2; --head: #ecece7; --accent: #c2512a; --on: #1c1c1a; --onink: #ffffff;
         --bad: #f6c9c0; --badink: #5a1608; --dim: 0.42; }
 @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg: #171715; --panel: #222220; --ink: #e9e8e2; --mute: #a3a29a; --line: #3b3b37; --head: #2c2c29;
         --accent: #e98a5f; --on: #e9e8e2; --onink: #171715; --bad: #6a2a1c; --badink: #ffd9cf; } }
 :root[data-theme="dark"] { --bg: #171715; --panel: #222220; --ink: #e9e8e2; --mute: #a3a29a; --line: #3b3b37; --head: #2c2c29; --accent: #e98a5f; --on: #e9e8e2; --onink: #171715;
         --bad: #6a2a1c; --badink: #ffd9cf; }
 * { box-sizing: border-box; }
 body { margin: 0; font: 14px/1.55 "Microsoft YaHei", "Segoe UI", sans-serif; background: var(--bg); color: var(--ink); }
 header { padding: 10px 16px; background: var(--panel); border-bottom: 1px solid var(--line); display: flex; gap: 12px; align-items: baseline; flex-wrap: wrap; }
 header b { font-size: 16px; } header span { color: var(--mute); flex: 1 1 420px; }
 .row { padding: 6px 16px 0; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
 .row small { color: var(--mute); width: 3.5em; }
 button { font: inherit; color: var(--ink); padding: 4px 10px; border: 1px solid var(--line); background: var(--panel); border-radius: 4px; cursor: pointer; }
 button.on { background: var(--on); color: var(--onink); border-color: var(--on); }
 #mode button.on, #pick button.on { background: var(--accent); border-color: var(--accent); color: #fff; }
 #note { padding: 8px 16px 4px; color: var(--mute); }
 #stage { padding: 0 16px; overflow: auto; }
 #stage.single img { max-width: 100%; max-height: 84vh; background: #fff; border: 1px solid var(--line); cursor: zoom-in; }
 #stage.single.full img { max-width: none; max-height: none; cursor: zoom-out; }
 #strip { display: grid; gap: 8px; align-items: start; }
 #strip figure { margin: 0; background: var(--panel); border: 1px solid var(--line); min-width: 0; }
 #strip img { width: 100%; display: block; cursor: pointer; background: #fff; }
 #strip figcaption { padding: 4px 8px; font-size: 12px; line-height: 1.4; border-bottom: 1px solid var(--line); color: var(--mute); }
 #strip figcaption b { font-size: 14px; color: var(--ink); }
 section { padding: 6px 16px 0; } section h2 { font-size: 15px; margin: 14px 0 6px; }
 section p, section li { max-width: 110em; } ul { margin: 4px 0; padding-left: 1.4em; }
 .scroll { overflow-x: auto; }
 table { border-collapse: collapse; background: var(--panel); } th, td { border: 1px solid var(--line); padding: 2px 8px; text-align: right; white-space: nowrap; }
 th { background: var(--head); } td:first-child, th:first-child { text-align: left; } td.bad { background: var(--bad); color: var(--badink); font-weight: bold; }
 #mt td:first-child { white-space: normal; min-width: 17em; max-width: 26em; }
 #mt .dim { opacity: var(--dim); }
 td.why { white-space: normal; text-align: left; min-width: 34em; max-width: 60em; }
 details { margin: 6px 0; } summary { cursor: pointer; font-weight: bold; }
 footer { padding: 16px; color: var(--mute); }
</style></head><body>
<header><b>走线和等长一起规划：对比页（一次性原型，issue 21）</b>
<span>← → 换组或换方案，↑ ↓ 换层，[ ] 换取景。图只作定性参考，数字都由脚本从板文件和 DRC 报告里量（单位 mm、mm²）。红底 = 没达标或要留意。</span>
<button id="theme" onclick="theme()">深色 / 浅色</button></header>
<div class="row" id="mode"></div><div class="row" id="pick"></div><div class="row" id="frames"></div><div class="row" id="layers"></div>
<div id="note"></div><div id="stage"></div>
<section><h2>指标表（每个方案一列，同一个脚本算；当前没在看的方案变淡）</h2><div class="scroll">__METRICS__</div>
<p>怎么读：<b>空间三项（凸包、外包矩形、窄条里上下占）只数两颗封装外形以外的总线铜</b>，三层叠在一个平面上；封装下面的线不算，所以另列了“SDRAM 封装下面的总线长度”。
凸包会把相距很远的线之间的空地也算进去；“扫过的面积”是每段铜各自外扩“半个线宽加 0.127”后合并的面积，不算空地。
基线只有一部分线进了窗口，它的面积是“没做完”的面积。各项的准确定义在 README.md。</p>
<p>track_shape.py 先把坐标取整到 1 µm 再算角度，而且不认识圆弧：它在基线上报的“非 45°”是蛇形在斜线上的短腿取整造成的，按纳米坐标重算的那一行（带圆弧的几何检查）才是准的。
“2 mm 内 3 个以上折弯”各处的位置和原因在单张模式的表下面和各方案自己的说明里。</p></section>
<section><h2>蛇形等高的约定和各方案的例外</h2>
<p>约定（2026-11-17）：同一个蛇形块（一段直线上的一串弯）里各弯等高，单侧双侧都一样；不同的块、不同的线可以不一样高；例外只有被邻线的蛇形挡住的地方（面对它的弯可以矮，或者把块拆成两段各自等高）；不为凑准长度留矮的尾弯，改调整块的高度。
腿间距：SDCLK 0.5 mm，数据和 DQM 按方案是 0.3 或 0.5 mm；圆弧半径是腿间距的一半。</p>__EQUAL__</section>
<section id="nets"></section>
<footer>由 make_compare.py 生成，数字来自各方案的 out/&lt;方案&gt;/metrics.json。KiCad 工程：out/&lt;方案&gt;/routetune.kicad_pro。</footer>
<script>
const VARIANTS = __VARIANTS__, GROUPS = __GROUPS__, FRAMES = __FRAMES__, LAYERS = __LAYERS__, TABLES = __TABLES__;
const q = new URLSearchParams(location.search);
const idx = (a, k, d) => { const i = a.findIndex(x => x[0] === k); return i < 0 ? d : i; };
let mode = q.get('variant') ? 'single' : 'strip';
let v = idx(VARIANTS, q.get('variant'), 0), g = Math.min(GROUPS.length - 1, Math.max(0, parseInt(q.get('group') || '0') || 0)),
    f = idx(FRAMES, q.get('frame'), 0), w = idx(LAYERS, q.get('layer'), 0);
const V = k => VARIANTS.find(x => x[0] === k);
function theme() {
  const r = document.documentElement, dark = r.dataset.theme ? r.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  r.dataset.theme = dark ? 'light' : 'dark';
  try { localStorage.setItem('rt-theme', r.dataset.theme); } catch (e) {}
}
try { const t = localStorage.getItem('rt-theme'); if (t) document.documentElement.dataset.theme = t; } catch (e) {}
function btn(text, on, js) { return `<button class="${on ? 'on' : ''}" onclick="${js}">${text}</button>`; }
function img(k) { return `out/${k}/cmp_${FRAMES[f][0]}_${LAYERS[w][0]}.png`; }
function netBlock(k, open) {
  const x = V(k);
  return `<details ${open ? 'open' : ''}><summary>${x[1]}：每根线的数字和“为什么这样走”</summary><p>${x[2]}　KiCad 工程：out/${k}/routetune.kicad_pro</p><div class="scroll">${TABLES[k]}</div></details>`;
}
function show() {
  document.getElementById('mode').innerHTML = '<small>看法</small>' + btn('并排', mode === 'strip', "mode='strip';show()") + btn('单张 + 表', mode === 'single', "mode='single';show()");
  document.getElementById('frames').innerHTML = '<small>取景</small>' + FRAMES.map((x, i) => btn(x[1], i === f, `f=${i};show()`)).join('');
  document.getElementById('layers').innerHTML = '<small>层</small>' + LAYERS.map((x, i) => btn(x[1], i === w, `w=${i};show()`)).join('');
  const stage = document.getElementById('stage');
  let shown;
  if (mode === 'strip') {
    shown = GROUPS[g][1];
    document.getElementById('pick').innerHTML = '<small>哪一组</small>' + GROUPS.map((x, i) => btn(x[0], i === g, `g=${i};show()`)).join('');
    document.getElementById('note').textContent = '同一个取景、同一个比例、同一层。L1 红、L4 蓝、L6 绿；灰框是封装外形，绿色虚线是规则区（AD 的 Room）。点图进入那个方案的单张和逐根的表。';
    stage.className = '';
    stage.innerHTML = `<div id="strip" style="grid-template-columns: repeat(${shown.length}, 1fr)">` + shown.map(k =>
      `<figure><figcaption><b>${V(k)[1]}</b><br>${V(k)[3]}</figcaption><img src="${img(k)}" alt="${k}" onclick="v=${VARIANTS.findIndex(x => x[0] === k)};mode='single';show()"></figure>`).join('') + '</div>';
    document.getElementById('nets').innerHTML = '<h2>逐根的表（点开）</h2>' + shown.map(k => netBlock(k, false)).join('');
    try { history.replaceState(null, '', '?group=' + g + '&frame=' + FRAMES[f][0] + '&layer=' + LAYERS[w][0]); } catch (e) {}
  } else {
    shown = [VARIANTS[v][0]];
    document.getElementById('pick').innerHTML = '<small>方案</small>' + VARIANTS.map((x, i) => btn(x[1], i === v, `v=${i};show()`)).join('');
    document.getElementById('note').textContent = VARIANTS[v][1] + '：' + VARIANTS[v][2] + '　' + VARIANTS[v][3] + '。点图放大到原始大小。';
    stage.className = 'single';
    stage.innerHTML = `<img src="${img(VARIANTS[v][0])}" alt="" onclick="this.parentNode.classList.toggle('full')">`;
    document.getElementById('nets').innerHTML = '<h2>逐根的表</h2>' + netBlock(VARIANTS[v][0], true);
    try { history.replaceState(null, '', '?variant=' + VARIANTS[v][0] + '&frame=' + FRAMES[f][0] + '&layer=' + LAYERS[w][0]); } catch (e) {}
  }
  document.querySelectorAll('#mt [data-v]').forEach(c => c.classList.toggle('dim', !shown.includes(c.dataset.v)));
}
document.addEventListener('keydown', e => {
  const step = d => { if (mode === 'strip') g = (g + d + GROUPS.length) % GROUPS.length; else v = (v + d + VARIANTS.length) % VARIANTS.length; };
  if (e.key === 'ArrowRight') step(1); else if (e.key === 'ArrowLeft') step(-1);
  else if (e.key === 'ArrowDown') w = (w + 1) % LAYERS.length; else if (e.key === 'ArrowUp') w = (w + LAYERS.length - 1) % LAYERS.length;
  else if (e.key === ']') f = (f + 1) % FRAMES.length; else if (e.key === '[') f = (f + FRAMES.length - 1) % FRAMES.length; else return;
  e.preventDefault(); show();
});
show();
</script></body></html>
"""


def write_page(M, T, R):
    variants = [[k, l, M[k]["description"], caption(M[k])] for k, l in VARIANTS]
    page = (PAGE.replace("__METRICS__", metrics_html(R)).replace("__EQUAL__", equal_note(M))
            .replace("__VARIANTS__", json.dumps(variants, ensure_ascii=False)).replace("__GROUPS__", json.dumps(GROUPS, ensure_ascii=False))
            .replace("__FRAMES__", json.dumps([[a, b] for a, b, *_ in FRAMES], ensure_ascii=False))
            .replace("__LAYERS__", json.dumps([[a, b] for a, b, _ in LAYERS], ensure_ascii=False))
            .replace("__TABLES__", json.dumps({k: net_table(M[k], T[k]) for k in KEYS}, ensure_ascii=False).replace("</", "<\\/")))
    open(os.path.join(HERE, "compare.html"), "w", encoding="utf-8", newline="\n").write(page)
    print("wrote compare.html (%d kB)" % (len(page.encode("utf-8")) // 1024))


# ---------------------------------------------------------------- README blocks (markdown)
def md_metrics(M, X, R):
    o = ["| 指标（mm、mm²） | " + " | ".join("`%s`" % k for k in KEYS) + " |", "|---|" + "---|" * len(KEYS)]
    for label, cells, bad in R:
        o.append("| %s | %s |" % (label.replace("　", "↳ "), " | ".join(("**%s**" % c) if b else c for c, b in zip(cells, bad))))
    return o


def md_variants(M, X, R):
    o = ["| 目录 | 是什么 | KiCad 工程 | 这个方案自己的说明 |", "|---|---|---|---|"]
    for k in KEYS:
        rd = "variants/%s/README.md" % k
        o.append("| `%s` | %s | `out/%s/routetune.kicad_pro` | %s |" % (k, M[k]["description"], k, "`%s`" % rd if os.path.isfile(os.path.join(HERE, rd)) else "本文件"))
    return o


def md_space(M, X, R):
    b = M[BASELINE]
    bs = b["space"]
    o = ["基线 `%s`：窗口内 %d / %d，凸包 %.1f mm²，外包矩形 %.2f × %.2f，窄条里上下占 %.2f mm，扫过的面积 %.1f mm²，SDRAM 封装下面的总线 %.1f mm。" % (
        BASELINE, b["totals"]["in_window_count"], b["totals"]["nets"], bs["bus_hull_area_mm2"], bs["bus_bbox_mm"][0], bs["bus_bbox_mm"][1], bs["channel_width_mm"],
        bs["bus_swept_area_mm2"]["all"], X[BASELINE]["under_body_mm"]["U2"]["total"]), "",
         "| 协调版 | 窗口内 | 凸包面积 | 比基线 | 外形内缩 0.1 mm 的凸包，比基线同口径 | 窄条里上下占 | 比基线 | 扫过的面积 | 比基线 | SDRAM 封装下面的总线 | 比基线 |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in COORD:
        m, s = M[k], M[k]["space"]
        o.append("| `%s` | %d / %d | %.1f | %s | %.1f，%s | %.2f | %s | %.1f | %s | %.1f | %s |" % (
            k, m["totals"]["in_window_count"], m["totals"]["nets"], s["bus_hull_area_mm2"], rel(s["bus_hull_area_mm2"], bs["bus_hull_area_mm2"], " mm²"),
            X[k]["outline_shrunk_0.1"]["hull"], rel(X[k]["outline_shrunk_0.1"]["hull"], X[BASELINE]["outline_shrunk_0.1"]["hull"], " mm²"),
            s["channel_width_mm"], rel(s["channel_width_mm"], bs["channel_width_mm"], " mm", 2),
            s["bus_swept_area_mm2"]["all"], rel(s["bus_swept_area_mm2"]["all"], bs["bus_swept_area_mm2"]["all"], " mm²"),
            X[k]["under_body_mm"]["U2"]["total"], rel(X[k]["under_body_mm"]["U2"]["total"], X[BASELINE]["under_body_mm"]["U2"]["total"], " mm")))
    o += ["", "正数 = 比基线多占，负数 = 比基线省。"]
    return o


def md_means(M, X, R):
    c0 = comp(M["0_base"])
    o = ["| 方案 | 直连最短合计 | 过孔高度 | 平面内绕远 | 蛇形补的 | 长度合计 | 比底板多出来的长度 | 其中靠走法（直连 + 过孔 + 绕远的变化） | 其中靠蛇形 |", "|---|---|---|---|---|---|---|---|---|"]
    for k in KEYS:
        c = comp(M[k])
        more = c["total"] - c0["total"]
        o.append("| `%s` | %.1f | %.1f | %.1f | %.1f | %.1f | %s | %s | %s |" % (
            k, c["direct"], c["via"], c["plane"], c["serp"], c["total"], "—" if k == "0_base" else "%.1f" % more,
            "—" if k == "0_base" else "%.1f（%.0f%%）" % (more - c["serp"], 100 * (more - c["serp"]) / more),
            "—" if k == "0_base" else "%.1f（%.0f%%）" % (c["serp"], 100 * c["serp"] / more)))
    return o


def md_blocks(M, X, R, T):
    o = ["| 方案 | 网络 | 层 | 朝向 | 腿间距 | 弯数 × 摆幅 | 补了 | 占原线的长度 | 占的宽度 | 占地（长 × 宽） | 每补 1 mm 占地 | 在 SDRAM 封装下面的比例 |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    tot = []
    for k in KEYS:
        bl = blocks(T[k])
        for r in bl:
            amp = "%d × %.3f" % (len(r["amps"]), r["amps"][0]) if max(r["amps"]) - min(r["amps"]) <= 0.0015 else "不等高：" + "、".join("%.2f" % a for a in r["amps"])
            o.append("| `%s` | %s | %s | %s | %.1f | %s | %.3f | %.2f | %.2f | %.2f | %.2f | %.0f%% |" % (
                k, r["net"], r["layer"], SIDE.get(r["side"], r["side"]), r["pitch"], amp, r["gain"], r["used"], r["width"], r["foot"], r["foot"] / r["gain"], 100 * r["under"]))
        if bl:
            tot.append("`%s`：%d 块，共补 %.2f mm，占地合计 %.2f mm²，平均每补 1 mm 占 %.2f mm²" % (k, len(bl), sum(r["gain"] for r in bl), sum(r["foot"] for r in bl),
                                                                                    sum(r["foot"] for r in bl) / sum(r["gain"] for r in bl)))
    return o + ["", "占原线的长度 = 蛇形块首尾两点的距离；占的宽度 = 最高的弯的摆幅（两侧交替的乘 2）；占地 = 两者相乘，是蛇形块自己的外包矩形，不含它到邻线的间距。", ""] + ["- " + t for t in tot]


def md_clear(M, X, R):
    o = ["| 方案 | 蛇形到别的网络的铜，最近 | 规则区外的蛇形到规则区边，最近 | 拐点到第一个圆弧，最短（短于 0.35 的处数） | 圆弧半径 | 不同网络之间最近（整块板，含非蛇形） | 那个位置的 DRC 间距 |", "|---|---|---|---|---|---|---|"]
    for k in KEYS:
        c, g = M[k]["checks"]["serpentine_clearances"], M[k]["checks"]["geometry"]
        if not M[k]["totals"]["n_serpentines"]:
            o.append("| `%s` | 没有蛇形 | — | — | — | %.3f（%s 对 %s，%s） | %.3f |" % (k, g["min_gap_all"]["gap"], g["min_gap_all"]["net"], g["min_gap_all"]["other"], g["min_gap_all"]["layer"], g["min_gap_all"]["need"]))
            continue
        n, a = c["smallest_to_other_net"], c["smallest_to_rule_area_edge_from_outside"]
        o.append("| `%s` | %.3f（%s 对 %s，%s；那里 DRC 要 %.3f） | %s | %.3f（%d 处） | %s | %.3f（%s 对 %s，%s） | %.3f |" % (
            k, n["gap"], n["net"], n["other"], n["layer"], n["need"], "%.3f（%s）" % (a["gap"], a["net"]) if a else "没有蛇形在规则区外",
            c["shortest_straight_between_bend_and_arc"], len(c["leads_below_0.35"]), "、".join("%.2f" % r for r in g["arc_radii_mm"]),
            g["min_gap_all"]["gap"], g["min_gap_all"]["net"], g["min_gap_all"]["other"], g["min_gap_all"]["layer"], g["min_gap_all"]["need"]))
    lim = M[KEYS[0]]["checks"]["serpentine_clearances"]["limits_used"]
    return o + ["", "画的时候守的限制（各方案相同）：拐点到第一个圆弧 %.2f，蛇形到别的铜 %.2f，规则区外的蛇形到规则区边 %.3f，到板边 %.3f，L1 上蛇形中心线到球心 %.1f。" % (
        lim["end"], lim["clr"], lim["area_gap"], lim["edge"], lim["field"])]


def md_equal(M, X, R):
    o = []
    for k in KEYS:
        u, n = unequal_blocks(M[k]), M[k]["totals"]["n_serpentines"]
        if not n:
            o.append("- `%s`：没有蛇形。" % k)
        elif not u:
            o.append("- `%s`：%d 块全部块内等高，例外 0 处。" % (k, n))
        else:
            o.append("- `%s`：%d 块里 **%d 块不等高**（%s）。不属于约定允许的例外，原因见下面一段。" % (
                k, n, len(u), "；".join("%s：%s" % (a, "、".join("%.2f" % x for x in b)) for a, b in u)))
    return o


def md_conclusion(M, X, R):
    b, bs = M[BASELINE], M[BASELINE]["space"]
    o = ["- 基线 `%s`（走完再补）：%d / %d 根在窗口内，离 SDCLK 最远的 %s 差 %+.3f mm；蛇形 %d 处共 %.1f mm；凸包 %.1f mm²，窄条里上下占 %.2f mm。" % (
        BASELINE, b["totals"]["in_window_count"], b["totals"]["nets"], short(b["totals"]["worst_net"]), b["totals"]["worst_delta_mm"], b["totals"]["n_serpentines"],
        b["totals"]["total_serpentine_mm"], bs["bus_hull_area_mm2"], bs["channel_width_mm"])]
    for k in COORD:
        m, s, t = M[k], M[k]["space"], M[k]["totals"]
        dh = s["bus_hull_area_mm2"] - bs["bus_hull_area_mm2"]
        dsw = s["bus_swept_area_mm2"]["all"] - bs["bus_swept_area_mm2"]["all"]
        dch = s["channel_width_mm"] - bs["channel_width_mm"]
        word = lambda d: "多占" if d > 0 else "省"
        o.append("- `%s`：%d / %d 根在窗口内。凸包 %.1f mm²，比基线%s %.1f mm²（%.0f%%）；扫过的面积 %.1f mm²，%s %.1f mm²（%.0f%%）；窄条里上下占 %.2f mm，%s %.2f mm（%.0f%%）。"
                 "蛇形 %d 处共 %.1f mm（基线 %.1f），绕远合计 %.1f mm（基线 %.1f）；SDRAM 封装下面的总线 %.1f mm（基线 %.1f）。" % (
                     k, t["in_window_count"], t["nets"], s["bus_hull_area_mm2"], word(dh), abs(dh), abs(100 * dh / bs["bus_hull_area_mm2"]),
                     s["bus_swept_area_mm2"]["all"], word(dsw), abs(dsw), abs(100 * dsw / bs["bus_swept_area_mm2"]["all"]),
                     s["channel_width_mm"], word(dch), abs(dch), abs(100 * dch / bs["channel_width_mm"]),
                     t["n_serpentines"], t["total_serpentine_mm"], b["totals"]["total_serpentine_mm"], t["total_detour_mm"], b["totals"]["total_detour_mm"],
                     X[k]["under_body_mm"]["U2"]["total"], X[BASELINE]["under_body_mm"]["U2"]["total"]))
    n, r = M[NEW], M[REF]
    less = lambda a, c, unit, prec=1: "%s %.*f%s（%.0f%%）" % ("省" if a < c else "多占", prec, abs(a - c), unit, abs(100 * (a - c) / c))
    o.append("- **`%s` 对 `%s`（去掉特意绕远以后）**：凸包%s，扫过的面积%s，其中表层 L1 从 %.1f 降到 %.1f mm²；窄条里上下占%s。"
             "蛇形从 %d 块 %.1f mm 变成 %d 块 %.1f mm，平面内绕远从 %.1f 降到 %.1f mm；SDRAM 封装下面的总线从 %.1f 变成 %.1f mm，过孔从 %d 个变成 %d 个。" % (
                 NEW, REF, less(n["space"]["bus_hull_area_mm2"], r["space"]["bus_hull_area_mm2"], " mm²"),
                 less(n["space"]["bus_swept_area_mm2"]["all"], r["space"]["bus_swept_area_mm2"]["all"], " mm²"),
                 r["space"]["bus_swept_area_mm2"]["L1"], n["space"]["bus_swept_area_mm2"]["L1"],
                 less(n["space"]["channel_width_mm"], r["space"]["channel_width_mm"], " mm", 2),
                 r["totals"]["n_serpentines"], r["totals"]["total_serpentine_mm"], n["totals"]["n_serpentines"], n["totals"]["total_serpentine_mm"],
                 comp(r)["plane"], comp(n)["plane"], X[REF]["under_body_mm"]["U2"]["total"], X[NEW]["under_body_mm"]["U2"]["total"],
                 r["totals"]["total_vias"], n["totals"]["total_vias"]))
    return o


def md_nodetour(M, X, R, T):
    """What taking the deliberate detours out changed: NEW against REF and against the baseline."""
    ks = [NEW, REF, BASELINE]
    bl = {k: blocks(T[k]) for k in ks}
    o = ["| 项 | `%s` | `%s` | `%s` | 比 `%s` | 比基线 |" % (NEW, REF, BASELINE, REF), "|---|---|---|---|---|---|"]

    def row(label, fn, prec=1, unit=""):
        v = [fn(k) for k in ks]
        o.append("| %s | %s | %s | %s |" % (label, " | ".join("%.*f" % (prec, x) for x in v), rel(v[0], v[1], unit, prec), rel(v[0], v[2], unit, prec)))

    def text(label, fn):
        o.append("| %s | %s | | |" % (label, " | ".join(fn(k) for k in ks)))

    text("在窗口内", lambda k: "%d / %d" % (M[k]["totals"]["in_window_count"], M[k]["totals"]["nets"]))
    row("凸包面积 mm²", lambda k: M[k]["space"]["bus_hull_area_mm2"], 1, " mm²")
    row("封装外形内缩 0.1 mm 再算的凸包 mm²", lambda k: X[k]["outline_shrunk_0.1"]["hull"], 1, " mm²")
    row("窄条里上下占 mm", lambda k: M[k]["space"]["channel_width_mm"], 2, " mm")
    row("扫过的面积 mm²（三层合并）", lambda k: M[k]["space"]["bus_swept_area_mm2"]["all"], 1, " mm²")
    row("↳ 其中 L1（表层）", lambda k: M[k]["space"]["bus_swept_area_mm2"]["L1"], 1, " mm²")
    text("蛇形：块 / 弯", lambda k: "%d / %d" % (M[k]["totals"]["n_serpentines"], M[k]["totals"]["n_humps"]))
    row("蛇形补的长度 mm", lambda k: M[k]["totals"]["total_serpentine_mm"], 1, " mm")
    row("↳ 其中补在 SDRAM 封装下面的 mm", lambda k: M[k]["totals"]["serpentine_under_sdram_mm"], 1, " mm")
    row("蛇形块自己的占地合计 mm²（长 × 宽）", lambda k: sum(r["foot"] for r in bl[k]), 1, " mm²")
    row("平面内绕远 mm", lambda k: comp(M[k])["plane"], 1, " mm")
    row("过孔高度 mm", lambda k: comp(M[k])["via"], 1, " mm")
    row("长度合计 mm", lambda k: comp(M[k])["total"], 1, " mm")
    text("过孔：每根最多 / 合计", lambda k: "%d / %d" % (M[k]["totals"]["max_vias"], M[k]["totals"]["total_vias"]))
    row("SDRAM 封装下面的总线 mm", lambda k: X[k]["under_body_mm"]["U2"]["total"], 1, " mm")
    o += ["", "负数 = `%s` 更小或更少。百分比的分母是被比的那一块。" % NEW, ""]

    c0, s0 = comp(M["0_base"]), M["0_base"]["space"]["bus_swept_area_mm2"]["all"]
    o.append("整块板的账（对不考虑等长的底板 `0_base`：扫过 %.1f mm²、总长 %.1f mm；封装下面的铜不算在面积里）：" % (s0, c0["total"]))
    o.append("")
    for k in (BASELINE, REF, NEW):
        dl, ds = comp(M[k])["total"] - c0["total"], M[k]["space"]["bus_swept_area_mm2"]["all"] - s0
        part = M[k]["totals"]["in_window_count"] < M[k]["totals"]["nets"]
        o.append("- `%s`：多出 %.1f mm 长度，多扫 %.1f mm²，平均每多 1 mm 多扫 %.2f mm²%s。" % (
            k, dl, ds, ds / dl, "（只有 %d / %d 根进窗口）" % (M[k]["totals"]["in_window_count"], M[k]["totals"]["nets"]) if part else ""))
    n = bl[NEW]
    data, clk = [r for r in n if r["net"] != "SDCLK"], [r for r in n if r["net"] == "SDCLK"]
    top, und = [r for r in n if r["layer"] == "L1"], [r for r in n if r["under"] > 0.5]
    o += ["", "`%s` 的蛇形块：数据线 %d 块，摆幅 %.2f–%.2f，每补 1 mm 占 %.2f–%.2f mm²%s。表层（L1）上的蛇形 %d 块共补 %.1f mm，SDRAM 封装下面 %d 块共补 %.1f mm。" % (
        NEW, len(data), min(r["amps"][0] for r in data), max(r["amps"][0] for r in data), min(r["foot"] / r["gain"] for r in data), max(r["foot"] / r["gain"] for r in data),
        "；时钟 %d 块，单边摆幅 %.2f，整块 %.2f × %.2f mm，每补 1 mm 占 %.2f mm²" % (len(clk), clk[0]["amps"][0], clk[0]["width"], clk[0]["used"], clk[0]["foot"] / clk[0]["gain"]) if clk else "",
        len(top), sum(r["gain"] for r in top), len(und), sum(r["gain"] for r in und))]
    return o


def md_sizing(M, X, R, T):
    """The sizing rule of NEW checked against what was built: straight used and length gained, per block."""
    o = ["| 网络 | 层 | 单侧 / 双侧 | 弯数 n | 摆幅 a | 腿间距 p | 所在的直线段长 | 公式：块占直线 | 实际占 | 这一段上块以外还剩 | 公式：补长 | 实际补 | 差 |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    worst, spare = 0.0, []
    k = 4 - math.pi                                    # length lost per hump to the four quarter arcs, in units of the leg pitch
    for b in sorted(T[NEW]["blocks"], key=lambda b: order(short(b["net"]))):
        n, a, p, both = b["humps"] + b["bumps"], max(b["amps"]), b["pitch"], b["side"] == "both"
        used = math.dist(b["from"], b["to"])
        f_used = p * (n + 1) if both else 2 * p * n
        f_gain = 2 * n * a - k / 2 * p * (n + 1) if both else n * (2 * a - k * p)
        worst = max(worst, abs(f_gain - b["gain"]), abs(f_used - used))
        spare.append(b["run_length"] - used)
        o.append("| %s | %s | %s | %d | %.3f | %.1f | %.2f | %.2f | %.2f | %.2f | %.3f | %.3f | %+.3f |" % (
            short(b["net"]), b["layer"], "双侧" if both else "单侧", n, a, p, b["run_length"], f_used, used, b["run_length"] - used, f_gain, b["gain"], b["gain"] - f_gain))
    N = M[NEW]["totals"]["nets"]
    return o + ["", "公式（圆弧半径是腿间距的一半）：单侧一块占直线 2·p·n，补 n·(2a − %.3f·p)；双侧一块占直线 p·(n + 1)，补 2·n·a − %.3f·p·(n + 1)。" % (k, k / 2),
                "", "公式和板上量到的最多差 %.3f mm（表里的摆幅只记到 0.001）。"
                "“所在的直线段”是同一线宽的一段直线（换线宽的地方算断开，所以它不一定是拐弯到拐弯的距离）；块以外还剩的，两头合计最少 %.2f mm，最多 %.2f mm。" % (worst, min(spare), max(spare)),
                "", "轮数上限的暂定式 5 + N·log2(N)/7：N = %d 时是 %.1f 轮。" % (N, 5 + N * math.log2(N) / 7)]


def md_base(M, X, R):
    m = M["0_base"]
    o = ["| 网络 | MCU 球 → SDRAM | 自然长度 | 直连最短 | 过孔 | 各层 | 比 SDCLK | 要进“最长的一根 − 5 mm”以上还差 |", "|---|---|---|---|---|---|---|---|"]
    floor = m["totals"]["longest_mm"] - 5.0
    for n in NETS:
        v = m["nets"][n]
        o.append("| %s | %s → %s %s | %.3f | %.3f | %d | %s | %+.3f | %s |" % (
            short(n), v["mcu_ball"], v["sdram_ball"], v["sdram_pin"], v["length_mm"], v["direct_mm"], v["vias"], "，".join("%s %.2f" % kv for kv in v["layers"].items()),
            v["delta_to_sdclk_mm"], "%.1f" % (floor - v["length_mm"]) if v["length_mm"] < floor else "0"))
    d = [v["direct_mm"] for v in m["nets"].values()]
    return o + ["", "自然长度最长 %.3f、最短 %.3f，相差 %.1f mm；连直连最短也从 %.1f 到 %.1f，相差 %.1f mm，而窗口总共只有 5 mm 宽。" % (
        m["totals"]["longest_mm"], m["totals"]["shortest_mm"], m["totals"]["longest_mm"] - m["totals"]["shortest_mm"], min(d), max(d), max(d) - min(d))]


def md_build(M, X, R):
    return ["| 方案 | 完整构建（秒） | 独立重量的出入 |", "|---|---|---|"] + [
        "| `%s` | %s | %s |" % (k, M[k].get("build_seconds", "—"), "没跑成" if X[k]["remeasure"]["findings"] is None else "%d 处" % X[k]["remeasure"]["findings"]) for k in KEYS]


def fill_readme(M, T, X, R):
    BL = {"conclusion": md_conclusion, "variants": md_variants, "metrics": md_metrics, "space": md_space, "means": md_means,
          "blocks": lambda M, X, R: md_blocks(M, X, R, T), "nodetour": lambda M, X, R: md_nodetour(M, X, R, T),
          "sizing": lambda M, X, R: md_sizing(M, X, R, T), "clearances": md_clear, "equal": md_equal, "base": md_base, "build": md_build}
    p = os.path.join(HERE, "README.md")
    text = open(p, encoding="utf-8").read()
    done = []

    def fill(m):
        done.append(m.group(1))
        return "<!-- AUTO:%s -->\n%s\n<!-- /AUTO -->" % (m.group(1), "\n".join(BL[m.group(1)](M, X, R)))

    text = re.sub(r"<!-- AUTO:(\w+) -->.*?<!-- /AUTO -->", fill, text, flags=re.S)
    open(p, "w", encoding="utf-8", newline="\n").write(text)
    print("README.md: filled %d blocks (%s); not used: %s" % (len(done), ", ".join(done), ", ".join(sorted(set(BL) - set(done))) or "none"))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    M, T = load_all()
    X = measure_and_render(M, "--render" in sys.argv, "--no-remeasure" not in sys.argv)
    R = rows(M, X)
    write_page(M, T, R)
    fill_readme(M, T, X, R)
    print()
    print("\n".join(md_metrics(M, X, R)))


if __name__ == "__main__":
    main()
