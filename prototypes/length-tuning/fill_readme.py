"""PROTOTYPE (issue 15): fill the result tables of README.md from the json files of the build, so that the
README cannot drift from the boards (review finding: one figure in the README was wrong).

    D:\\KiCad\\bin\\python.exe fill_readme.py      (last step of build.sh)

Every block between  <!-- AUTO:name -->  and  <!-- /AUTO -->  in README.md is replaced. The text
outside the blocks is hand-written; the numbers it quotes are listed in the blocks next to it.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
V5 = ["1_A05_single", "2_A10_single", "2b_A10_single_even", "3_A05_double", "4_window_only_clk", "5_A05_double_tight"]
V8 = ["7_gap8_A05_single", "8_gap8_A10_single", "8b_gap8_A10_single_even", "9_gap8_A05_double", "9m_gap8_A05_double_near_mcu",
      "9s_gap8_A05_double_near_sdram"]
BASES = ["0_base", "6_gap8_base"]
short = lambda v: v.split("_")[0]
s = lambda n: n.replace("/FMC_", "").replace("FMC_", "")
order = lambda n: (0, 0) if "CLK" in n else (1, int(re.sub(r"\D", "", n) or 0))


def load(v, name):
    return json.load(open(os.path.join(HERE, "out", v, name), encoding="utf-8"))


T = {v: load(v, "tune_table.json") for v in BASES + V5 + V8}
LEN = {v: load(v, "lengths.json")["nets"] for v in BASES + V5 + V8}


def summary():
    out = ["| 方案 | 到目标的 | 没到目标的（差多少） | 补完后最长最短差 | 对 SDCLK 超出 ±2.5 的 | 整弯 / 小弯 / 圆弧 | 脚本算的和 DRC 实测最多差 | DRC 未连接 / 超窗 / 其他 |",
           "|---|---|---|---|---|---|---|---|"]
    for v in V5 + V8:
        t = T[v]; rows = t["rows"]; d = t["drc"]
        miss = "，".join("%s %.3f" % (s(r["net"]), r["missing"]) for r in rows if r["missing"] > 0.0005) or "无"
        over = "，".join("%s %+.3f" % (s(r["net"]), r["to_ref"]) for r in rows if abs(r["to_ref"]) > 2.5) or "无"
        if t["params"]["goal"] == "window":
            reach = "只补 SDCLK，到位"
        else:
            reach = "%d / %d" % (len(rows) - t["summary"]["not_reached"], len(rows))
        out.append("| `%s` | %s | %s | %.3f | %s | %d / %d / %d | %.4f | %d / %d / %d |" % (
            v, reach, miss, t["summary"]["spread_after"], over, sum(r["humps"] for r in rows), sum(r["bumps"] for r in rows), t["arcs"]["arcs"],
            t["summary"]["max_abs_diff"], d["unconnected"], len(d["length"]), sum(d["other"].values())))
    return out


def geo():
    out = ["| 方案 | 拐点到第一个圆弧，最短 | 短于 0.35 的 | 蛇形到别的网络的铜，最近 | 蛇形到规则区边，最近 | 圆弧圆心角 | 最短直线段 / 最短圆弧 | `track_shape.py` 五项 | 规则生效检查 |",
           "|---|---|---|---|---|---|---|---|---|"]
    for v in V5 + V8:
        t = T[v]; g = t["geo"]; n = g["serp_net_gap"]; a = g["area_gap"]["arc"]
        ts = dict(re.findall(r"(off-grid|staircase|sharp|crowded|tiny \(< 0\.1 mm\)): (\d+)", t["track_shape"]))
        out.append("| `%s` | %.3f | %d 处 | %.3f（%s 对 %s） | %.3f（%s） | %.1f°–%.1f° | %.3f / %.3f | %s | %s |" % (
            v, g["lead_min"], g["sharp_arc"], n["gap"], s(n["net"]), s(n["other"]), a["gap"], s(a["net"]), g["sweep_min"], g["sweep_max"],
            t["arcs"]["shortest_segment"], t["arcs"]["shortest_arc"], " / ".join(ts[k] for k in ("off-grid", "staircase", "sharp", "crowded", "tiny (< 0.1 mm)")),
            "OK" if t["canary"].startswith("OK") else "**没生效**"))
    return out


def lengths(variants, base):
    out = ["| 网络 | 自然 | " + " | ".join(short(v) for v in variants) + " |", "|---|---|" + "---|" * len(variants)]
    for n in sorted(LEN[base], key=order):
        out.append("| %s | %.3f | %s |" % (s(n), LEN[base][n]["length"], " | ".join("%.3f" % LEN[v][n]["length"] for v in variants)))
    return out


def humps(variants):
    out = ["| 网络 | 要补 | " + " | ".join(short(v) for v in variants) + " |", "|---|---|" + "---|" * len(variants)]
    names = [r["net"] for r in T[variants[0]]["rows"]]
    for i, n in enumerate(names):
        cells = []
        for v in variants:
            r = T[v]["rows"][i]
            side = "；".join(re.sub(r" \(.*", "", w) for w in r["where"].split("；")) if r["where"] != "—" else ""
            cells.append("—" if r["amps"] == "—" else "%s（%s）" % (r["amps"], side))
        out.append("| %s | %.3f | %s |" % (s(n), T[variants[0]]["rows"][i]["need"], " | ".join(cells)))
    return out


def default():
    out = ["| 网络 | 自然长度 | 要补 | 实补（脚本算） | DRC 实测 | 脚本−DRC | 离目标 | 没补上 | 整弯 | 小弯 | 各弯摆幅 | 蛇形在哪 | 过孔 | 对 SDCLK |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in T["1_A05_single"]["rows"]:
        where = "；".join(re.sub(r" \(.*", "", w) for w in r["where"].split("；"))
        out.append("| %s | %.3f | %.3f | %.3f | %.4f | %+.4f | %+.3f | %.3f | %d | %d | %s | %s | %d | %+.3f |" % (
            s(r["net"]), r["natural"], r["need"], r["added"], r["drc"], r["diff"], r["err"], r["missing"], r["humps"], r["bumps"], r["amps"], where,
            r["vias"], r["to_ref"]))
    return out


def window():
    names = lambda d: "（%s）" % "，".join(s(k) for k in sorted(d, key=order)) if d else ""
    out = ["| 板 | L（SDCLK 的长度） | 这份规则套在没补的板上，DRC 报超窗 | 套在补完的板上 |", "|---|---|---|---|"]
    for b in BASES:
        d = T[b]["drc"]["length"]
        out.append("| `%s`（没补） | %.4f | %d 根%s | — |" % (b, LEN[b]["/FMC_SDCLK"]["length"], len(d), names(d)))
    for v in V5 + V8:
        t = T[v]
        out.append("| `%s` | %.4f | %d 根%s | %d 根%s |" % (v, t["window_L"], len(t["window_before"]), names(t["window_before"]),
                                                      len(t["drc"]["length"]), names(t["drc"]["length"])))
    return out


def natural():
    out = ["| 网络 | 5 mm 板长度 | 8 mm 板长度 | 过孔数 | 5 mm 板各层 | 比最长 | 比 SDCLK |", "|---|---|---|---|---|---|---|"]
    for n in sorted(LEN["0_base"], key=order):
        a, b = LEN["0_base"][n], LEN["6_gap8_base"][n]
        out.append("| %s | %.3f | %.3f | %d | %s | %+.3f | %+.3f |" % (s(n), a["length"], b["length"], a["vias"],
                   "，".join("%s %.3f" % kv for kv in sorted(a["layers"].items())), a["to_longest"], a["to_ref"]))
    return out


def base_geo():
    out = ["| 项目 | `0_base`（5 mm） | `6_gap8_base`（8 mm） |", "|---|---|---|"]
    g5, g8 = T["0_base"]["geo"], T["6_gap8_base"]["geo"]
    nets = sorted(set(g5["thin_outside"]) | set(g8["thin_outside"]), key=order)
    out.append("| 规则区外的 0.09 mm 线，每根的长度 | %s | %s |" % tuple(
        "，".join("%s %.2f" % (s(n), g["thin_outside"].get(n, 0)) for n in nets) for g in (g5, g8)))
    out.append("| 其中最长 | %.2f | %.2f |" % (max(g5["thin_outside"].values()), max(g8["thin_outside"].values())))
    out.append("| 过孔两侧走向的夹角（0 = 直穿，180 = 折回） | %s | %s |" % tuple(
        "，".join("%s %.0f°" % (s(v["net"]), v["turn"]) for v in sorted(g["via_turn"], key=lambda v: (order(v["net"]), v["at"][0]))) for g in (g5, g8)))
    out.append("| 这组线离别的网络的铜最近 | %.3f（%s 对 %s） | %.3f（%s 对 %s） |" % (
        g5["all_net_gap"]["gap"], s(g5["all_net_gap"]["net"]), s(g5["all_net_gap"]["other"]),
        g8["all_net_gap"]["gap"], s(g8["all_net_gap"]["net"]), s(g8["all_net_gap"]["other"])))
    out.append("| 不在 1 µm 网格上的线端 | %d | %d |" % (len(g5["off_grid"]), len(g8["off_grid"])))
    out.append("| 铺地到信号过孔焊盘（铺铜设 0.20） | %s | %s |" % tuple(
        "，".join(re.search(r"min ([\d.]+)", l).group(1) for l in T[b]["pour"]) for b in BASES))
    out.append("| DRC 未连接 / 长度超窗 / 其他 | %s | %s |" % tuple(
        "%d / %d / %d" % (T[b]["drc"]["unconnected"], len(T[b]["drc"]["length"]), sum(T[b]["drc"]["other"].values())) for b in BASES))
    out.append("| `track_shape.py` | %s | %s |" % tuple("；".join(l.strip() for l in T[b]["track_shape"].splitlines()) for b in BASES))
    return out


def room():
    r = load("0_base", "room.json")
    out = ["| 网络 | 补到最长要加 | 每根直线段取较宽一侧，估算最多能补 | 摆幅只用 0.5 时能补 |", "|---|---|---|---|"]
    for n in sorted(r["need_to_longest"], key=order):
        b = r["total"].get(n, {"gain": 0, "gain_a05": 0})
        out.append("| %s | %.3f | %.2f | %.2f |" % (s(n), r["need_to_longest"][n], b["gain"], b["gain_a05"]))
    return out


def tight():
    out = ["| 方案 | 蛇形到别的网络的铜，0.3 mm 以内的每一处（mm，括号里是位置） |", "|---|---|"]
    for v in V5 + V8:
        seen, cells = set(), []
        for p in T[v]["geo"]["pairs"]:
            k = frozenset((p["net"], p["other"]))
            if k in seen:
                continue
            seen.add(k); cells.append("%s 对 %s %.3f (%.2f, %.2f)" % (s(p["net"]), s(p["other"]), p["gap"], p["at"][0], p["at"][1]))
        out.append("| `%s` | %s |" % (v, "；".join(cells) or "无"))
    return out


BLOCKS = {"summary": summary, "geo": geo, "lengths5": lambda: lengths(V5, "0_base"), "lengths8": lambda: lengths(V8, "6_gap8_base"),
          "humps5": lambda: humps(V5), "humps8": lambda: humps(V8), "default": default, "window": window, "natural": natural,
          "base_geo": base_geo, "room": room, "tight": tight}
p = os.path.join(HERE, "README.md")
text = open(p, encoding="utf-8").read()
done = []


def fill(m):
    done.append(m.group(1))
    return "<!-- AUTO:%s -->\n%s\n<!-- /AUTO -->" % (m.group(1), "\n".join(BLOCKS[m.group(1)]()))


text = re.sub(r"<!-- AUTO:(\w+) -->.*?<!-- /AUTO -->", fill, text, flags=re.S)
open(p, "w", encoding="utf-8", newline="\n").write(text)
sys.stdout.reconfigure(encoding="utf-8")
print("README.md: filled %d blocks (%s); not used: %s" % (len(done), ", ".join(done), ", ".join(sorted(set(BLOCKS) - set(done))) or "none"))
