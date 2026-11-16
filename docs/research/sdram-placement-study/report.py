"""从 results.json 生成：results.csv、SVG、README.md 里 <!--BEGIN:xxx--> ... <!--END:xxx--> 之间的表。
README 的其余文字（方法、假设、结论、局限）是手写的；表里的数字全部来自 results.json，也就是 study.py 的输出。"""
import csv
import json
import re
from pathlib import Path

import numpy as np

import balldata as bd
import core

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results.json"
README = HERE / "README.md"
SVG_DIR = HERE / "svg"

ORDER = ("both", "straight")
HEADLINE = "both"          # 前三名 SVG 用哪个口径："both"（综合）或 "straight"（直线飞线，规格口径）
TIER_NAME = {"a": "(a) 不换位", "b": "(b) 字节内换位", "c": "(c) 字节内+通道互换"}
SLUG = {"右": "right", "下": "bottom", "左": "left", "上": "top",
        "右偏下": "right_shiftdown", "右偏上": "right_shiftup", "左偏下": "left_shiftdown", "左偏上": "left_shiftup",
        "下偏右": "bottom_shiftright", "下偏左": "bottom_shiftleft", "上偏右": "top_shiftright", "上偏左": "top_shiftleft",
        "右下角": "corner_br", "左下角": "corner_bl", "右上角": "corner_tr", "左上角": "corner_tl"}
GROUP_COLOR = {"byte0": "#0072B2", "byte1": "#D55E00", "byte2": "#009E73", "byte3": "#CC79A7",
               "addr": "#E69F00", "cmd": "#56B4E9", "clk": "#000000"}
BUS_COLOR = {"SDRAM": "#4c78a8", "LTDC": "#e45756", "QSPI": "#54a24b", "SDMMC": "#f58518", "RMII": "#b279a2"}
FONT = "Microsoft YaHei, PingFang SC, Noto Sans CJK SC, Source Han Sans SC, sans-serif"


# ------------------------------------------------------------------ 读取、排名
def load():
    data = json.loads(RESULTS.read_text(encoding="utf8"))
    return data["records"]


def key_of(r, obj):
    m = r["m"]
    return (m["x_both"], m["wl_total"]) if obj == "both" else (m["x_eff"], m["le_total"])


def pool_for(recs, obj):
    """某个口径下参与排名的分配：a 档（对两种口径相同）加该口径优化出的 b、c 档。"""
    return [r for r in recs if r["obj"] in ("-", obj)]


def ranked(recs, obj):
    return sorted(pool_for(recs, obj), key=lambda r: key_of(r, obj))


def label(r):
    return f"{r['pos']}，转{r['rot']}°，间距{r['gap']:g}"


def pl_of(r):
    hx, hy = (4.0, 6.5) if r["rot"] in (0, 180) else (6.5, 4.0)
    return core.Placement(r["pos"], r["gap"], r["rot"], r["cx"], r["cy"], hx, hy)


def baseline(recs, obj):
    """基准：ST 一一对应（a 档）、放右边（'右'，居中）、间距 5 mm，四个旋转里按该口径的排名取最好的。"""
    c = [r for r in recs if r["tier"] == "a" and r["pos"] == "右" and r["gap"] == 5.0]
    return sorted(c, key=lambda r: key_of(r, obj))[0]


# ------------------------------------------------------------------ CSV
def write_csv(recs):
    cols = ["pos", "rot", "gap", "tier", "obj", "lane_map",
            "x_eff", "x_tt", "x_ll", "x_xl", "x_all", "x_data", "x_ac", "x_mixed",
            "le_total", "le_max", "le_min", "le_range", "lm_total", "lm_max", "lm_min", "lm_range",
            "wl_total", "wl_max", "wl_min", "wl_range", "detour", "n_hug",
            "wx_eff", "wx_tt", "wx_ll", "wx_all", "wx_data", "wx_ac", "x_both", "bundle"]
    for g in core.GROUPS:
        cols += [f"g_{g}_le_min", f"g_{g}_le_max"]
    cols += ["exit_R", "exit_B", "exit_L", "exit_T"]
    for e in "上右下左":
        cols += [f"pass_{e}_top", f"pass_{e}_l4"]
    for b in bd.BUS_ORDER:
        cols += [f"{b}_hit_same", f"{b}_hit_any", f"{b}_pairs_same"]
    cols += ["perm"]
    with open(HERE / "results.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in recs:
            m = r["m"]
            row = [r["pos"], r["rot"], r["gap"], r["tier"], r["obj"], "".join(map(str, r["lm"]))]
            for c in cols[6:]:
                if c in m:
                    v = m[c]
                    row.append(f"{v:.3f}" if isinstance(v, float) else v)
                elif c.startswith("pass_"):
                    _, e, lay = c.split("_")
                    row.append(m["pass"][e][0 if lay == "top" else 1])
                elif c.startswith("exit_"):
                    row.append(m["exit_edges"][{"R": "右", "B": "下", "L": "左", "T": "上"}[c[5]]])
                elif c.endswith(("_hit_same", "_hit_any", "_pairs_same")):
                    bus, kind = c.split("_", 1)
                    row.append(m["bus"][bus][kind])
                elif c == "perm":
                    row.append(" ".join(map(str, r["perm"])))
            w.writerow(row)


# ------------------------------------------------------------------ README 自动块
def set_block(text, name, body):
    pat = re.compile(rf"(<!--BEGIN:{name}-->)(.*?)(<!--END:{name}-->)", re.S)
    if not pat.search(text):
        raise KeyError(f"README 里没有 <!--BEGIN:{name}--> 块")
    return pat.sub(lambda m: m.group(1) + "\n" + body.strip("\n") + "\n" + m.group(3), text)


def f1(x):
    return f"{x:.1f}"


def table(header, rows, align=None):
    out = ["| " + " | ".join(header) + " |"]
    out.append("|" + "|".join(["---"] * len(header)) + "|")
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def tier_cell(r):
    return TIER_NAME[r["tier"]] + ("" if r["tier"] != "c" else f"（通道 {''.join(map(str, r['lm']))}）")


def rank_rows_straight(rs):
    rows = []
    for i, r in rs:
        m = r["m"]
        rows.append([i, label(r), tier_cell(r),
                     f"{m['x_eff']}（顶{m['x_tt']} / L4 {m['x_ll']}）",
                     f"{m['x_all']}（数据{m['x_data']} / 地址命令{m['x_ac']} / 混合{m['x_mixed']}）",
                     f"{f1(m['le_total'])} / {f1(m['le_max'])} / {f1(m['le_min'])} / {f1(m['le_range'])}",
                     f"{f1(m['lm_total'])} / {f1(m['lm_max'])} / {f1(m['lm_min'])} / {f1(m['lm_range'])}"])
    return table(["名次", "摆法", "换位档", "有效交叉（同层）", "全部交叉", "直线 总长 / 最长 / 最短 / 极差 mm",
                  "曼哈顿 总长 / 最长 / 最短 / 极差 mm"], rows)


def rank_rows_wrap(rs):
    rows = []
    for i, r in rs:
        m = r["m"]
        mixed = m["wx_eff"] - m["wx_data"] - m["wx_ac"]
        rows.append([i, label(r), tier_cell(r),
                     f"{m['x_both']}（直线 {m['x_eff']} + 绕行 {m['wx_eff']}）",
                     f"{m['wx_eff']}（顶{m['wx_tt']} / L4 {m['wx_ll']}）",
                     f"{m['wx_data']} / {m['wx_ac']} / {mixed}",
                     f"{f1(m['wl_total'])} / {f1(m['wl_max'])} / {f1(m['wl_min'])} / {f1(m['wl_range'])}",
                     f"{f1(m['detour'])}", m["n_hug"], m["bundle"]])
    return table(["名次", "摆法", "换位档", "综合交叉（同层）", "绕行有效交叉（同层）", "其中 数据内 / 地址命令内 / 混合",
                  "绕行 总长 / 最长 / 最短 / 极差 mm", "比直线多绕 mm", "贴边绕行的线数", "最宽线束（根）"], rows)


def build_rank_block(recs):
    out = []
    for obj in ("both", "straight"):
        rk = ranked(recs, obj)
        base = baseline(recs, obj)
        base_rank = rk.index(base) + 1
        top = [(i + 1, r) for i, r in enumerate(rk[:6])]
        title = {"straight": "按直线飞线排名（规格口径：同层交叉数优先，再比直线总长）",
                 "both": "按综合口径排名（同层直线交叉 + 同层绕行交叉之和优先，再比绕行总长）"}[obj]
        out.append(f"**{title}**；共 {len(rk)} 个候选，下表前 6 名加基准。")
        rows = top + [(f"基准（第 {base_rank} 名）", base)]
        out.append("")
        out.append(rank_rows_straight(rows) if obj == "straight" else rank_rows_wrap(rows))
        out.append("")
        out.append("同一批候选的另一套数字：")
        out.append("")
        out.append(rank_rows_wrap(rows) if obj == "straight" else rank_rows_straight(rows))
        out.append("")
    return "\n".join(out)


def build_tier_block(recs):
    """各换位档的最好成绩和改善。"""
    rows = []
    for obj in ORDER:
        rk = ranked(recs, obj)
        base = baseline(recs, obj)
        for tier in "abc":
            best = [r for r in rk if r["tier"] == tier][0]
            m, mb = best["m"], base["m"]
            if obj == "both":
                e, l, e0, l0 = m["x_both"], m["wl_total"], mb["x_both"], mb["wl_total"]
            else:
                e, l, e0, l0 = m["x_eff"], m["le_total"], mb["x_eff"], mb["le_total"]
            rows.append([core.OBJ_LABEL[obj], TIER_NAME[tier], label(best) + (f"，通道 {''.join(map(str, best['lm']))}" if tier == "c" else ""),
                         e, f"{(e - e0) / e0 * 100:+.0f}%", f1(l), f"{(l - l0) / l0 * 100:+.1f}%"])
    return table(["口径", "换位档", "该档最好的摆法", "有效交叉", "对基准", "总长 mm", "对基准"], rows)


def build_group_block(recs):
    out = []
    for obj in ORDER:
        rk = ranked(recs, obj)
        base = baseline(recs, obj)
        sel = [(i + 1, r) for i, r in enumerate(rk[:6])] + [(f"基准", base)]
        rows = []
        for i, r in sel:
            m = r["m"]
            cells = [i, label(r), tier_cell(r)]
            for g in core.GROUPS:
                lo, hi = m[f"g_{g}_le_min"], m[f"g_{g}_le_max"]
                cells.append(f"{lo:.1f}–{hi:.1f}" if g != "clk" else f"{lo:.1f}")
            rows.append(cells)
        out.append(f"{core.OBJ_LABEL[obj]}的前 6 名和基准（直线长度 mm，最短–最长）：")
        out.append("")
        out.append(table(["名次", "摆法", "换位档"] + [core.GROUP_LABEL[g] for g in core.GROUPS], rows))
        out.append("")
    return "\n".join(out)



def _by_placement(recs):
    by = {}
    for r in recs:
        by.setdefault((r["pos"], r["gap"], r["rot"]), {})[(r["tier"], r["obj"])] = r
    return by


def build_swap_block(recs):
    by = _by_placement(recs)
    out = []
    # 1. 128 个摆法上的平均效果
    rows = []
    for obj, kx, kl in (("straight", "x_eff", "le_total"), ("both", "x_both", "wl_total")):
        for tier in "bc":
            red, lenr, cnt_better = [], [], 0
            for d in by.values():
                a, t = d[("a", "-")]["m"], d[(tier, obj)]["m"]
                red.append(1 - t[kx] / a[kx])
                lenr.append(t[kl] / a[kl] - 1)
                if tier == "c" and t[kx] < d[("b", obj)]["m"][kx]:
                    cnt_better += 1
            red, lenr = np.array(red), np.array(lenr)
            extra = ""
            if tier == "c":
                n_b = sum(1 for d in by.values() if d[("c", obj)]["m"][kx] < d[("b", obj)]["m"][kx])
                extra = f"{n_b} / {len(by)}"
            rows.append([core.OBJ_LABEL[obj], TIER_NAME[tier],
                         f"{red.mean() * 100:.0f}%（{np.median(red) * 100:.0f}% 中位，{red.min() * 100:.0f}% 到 {red.max() * 100:.0f}%）",
                         f"{lenr.mean() * 100:+.1f}%（{lenr.min() * 100:+.1f}% 到 {lenr.max() * 100:+.1f}%）", extra or "—"])
    out.append("128 个摆法上，换位对同层交叉数和总长的平均影响（相对同一摆法的 (a) 档；括号里是中位数和范围）：")
    out.append("")
    out.append(table(["口径", "换位档", "有效交叉平均降低", "总长平均变化", "(c) 比 (b) 更少交叉的摆法数"], rows))
    out.append("")
    # 2. 几个具体摆法
    keys = []
    for obj in ORDER:
        for r in ranked(recs, obj)[:3]:
            k = (r["pos"], r["gap"], r["rot"])
            if k not in keys:
                keys.append(k)
    b = baseline(recs, HEADLINE)
    kb = (b["pos"], b["gap"], b["rot"])
    if kb not in keys:
        keys.append(kb)
    rows = []
    for k in keys:
        d = by[k]
        cells = [f"{k[0]}，转{k[2]}°，间距{k[1]:g}"]
        a = d[("a", "-")]["m"]
        cells.append(f"{a['x_eff']} / {a['le_total']:.1f}")
        for obj, kx, kl in (("straight", "x_eff", "le_total"),):
            for tier in "bc":
                m = d[(tier, obj)]["m"]
                cells.append(f"{m[kx]} / {m[kl]:.1f}" + (f"（{''.join(map(str, d[(tier, obj)]['lm']))}）" if tier == "c" else ""))
        cells.append(f"{a['x_both']} / {a['wl_total']:.1f}")
        for tier in "bc":
            m = d[(tier, "both")]["m"]
            cells.append(f"{m['x_both']} / {m['wl_total']:.1f}" + (f"（{''.join(map(str, d[(tier, 'both')]['lm']))}）" if tier == "c" else ""))
        rows.append(cells)
    out.append("几个具体摆法上，三档的对比（规格口径格式：同层直线交叉 / 直线总长 mm；综合口径格式：直线交叉 + 绕行交叉 / 绕行总长 mm；(c) 后括号 = 通道对应）：")
    out.append("")
    out.append(table(["摆法", "(a) 规格", "(b) 规格", "(c) 规格", "(a) 综合", "(b) 综合", "(c) 综合"], rows))
    return chr(10).join(out)


def build_pareto_block(recs):
    out = []
    for obj, kx, kl, nx, nl in (("straight", "x_eff", "le_total", "同层直线交叉", "直线总长"),
                                ("both", "x_both", "wl_total", "直线 + 绕行同层交叉", "绕行总长")):
        pool = pool_for(recs, obj)
        pts = sorted(pool, key=lambda r: (r["m"][kx], r["m"][kl]))
        front, best = [], 1e18
        for r in pts:
            if r["m"][kl] < best - 1e-9:
                front.append(r)
                best = r["m"][kl]
        rows = [[label(r), tier_cell(r), r["m"][kx], f1(r["m"][kl]), r["m"]["x_eff"], r["m"]["wx_eff"],
                 f1(r["m"]["le_total"]), f1(r["m"]["wl_total"])] for r in front]
        out.append(f"{core.OBJ_LABEL[obj]}：{nx}和{nl}的取舍（只列没有被别的候选在这两项上同时压过的）：")
        out.append("")
        out.append(table(["摆法", "换位档", nx, nl + " mm", "同层直线交叉", "同层绕行交叉", "直线总长 mm", "绕行总长 mm"], rows))
        out.append("")
    return chr(10).join(out)


def build_pos_block(recs):
    """每个位置（16 个）上最好的 (a) 和最好的 (c)，综合口径。"""
    out = []
    rows = []
    by_pos = {}
    for r in pool_for(recs, "both"):
        by_pos.setdefault(r["pos"], {}).setdefault(r["tier"], []).append(r)
    for pos in SLUG:
        cells = [pos]
        for tier in "ac":
            b = min(by_pos[pos][tier], key=lambda r: key_of(r, "both"))
            m = b["m"]
            cells.append(f"转{b['rot']}°，间距{b['gap']:g}" + (f"，通道 {''.join(map(str, b['lm']))}" if tier == "c" else ""))
            cells.append(f"{m['x_both']}（直线{m['x_eff']} + 绕行{m['wx_eff']}）")
            cells.append(f"{f1(m['le_total'])} / {f1(m['wl_total'])}")
            if tier == "c":
                cells.append(" / ".join(f"{m['bus'][bu]['hit_same']}" for bu in bd.BUS_ORDER))
        rows.append(cells)
    out.append("每个位置上，综合口径下最好的 (a) 和最好的 (c)（长度格式：直线 / 绕行，mm；最后一列 = 被横穿的 LTDC / QSPI / SDMMC / RMII 出线数，总数 20 / 6 / 6 / 9）：")
    out.append("")
    out.append(table(["位置", "最好的 (a)", "(a) 综合交叉", "(a) 总长", "最好的 (c)", "(c) 综合交叉", "(c) 总长", "(c) 被横穿的总线出线数"], rows))
    return chr(10).join(out)



def wiring_table(r):
    """一个分配的接线：每个 MCU 字节通道接到哪个 SDRAM 字节、每一位接到哪一位，与 ST 对位不同的标 *。"""
    perm = r["perm"]
    rows = []
    for m in range(4):
        s_lane = perm[32 + m] - 32
        cells = [f"字节 {m}（D{8 * m}–D{8 * m + 7}，NBL{m}）", f"字节 {s_lane}（DQ{8 * s_lane}–DQ{8 * s_lane + 7}，DQM{s_lane}）"]
        bits = []
        for b in range(8):
            q = perm[8 * m + b] - 8 * s_lane
            std = (8 * m + b) % 8
            bits.append(f"D{8 * m + b}→DQ{8 * s_lane + q}" + ("" if q == b else "*"))
        cells.append(" ".join(bits))
        rows.append(cells)
    return table(["MCU 字节通道", "接到 SDRAM", "位对位（* = 字节内的位号和 MCU 一侧不同）"], rows)


def build_wiring_block(recs):
    out = []
    picks = [("综合口径第 1 名", ranked(recs, "both")[0])]
    for pos, rot, gap, tier, obj, tag in (("右", 180, 5.0, "c", "both", "同在右边、转 180°、(c)（综合口径最优分配）"),
                                          ("右", 0, 5.0, "b", "both", "基准摆法（右、转 0°）上只做字节内换位 (b)")):
        for r in recs:
            if (r["pos"], r["rot"], r["gap"], r["tier"], r["obj"]) == (pos, rot, gap, tier, obj):
                picks.append((tag, r))
    for tag, r in picks:
        m = r["m"]
        out.append(f"**{tag}**：{label(r)}，{tier_cell(r)}。同层直线交叉 {m['x_eff']}、直线总长 {m['le_total']:.1f} mm；"
                   f"绕行同层交叉 {m['wx_eff']}、绕行总长 {m['wl_total']:.1f} mm。地址、BA、命令、时钟全部按 ST 对位（A0→A0 … SDCLK→CLK）。")
        out.append("")
        out.append(wiring_table(r))
        out.append("")
    return chr(10).join(out)


# ------------------------------------------------------------------ 各边和其它总线
def edge_table():
    sym = bd.parse_symbol()
    gpio = [b for b, (nm, _) in sym.items() if __import__("re").match(r"P[A-K]\d", nm)]
    rows_by_edge = {e: {"GPIO": 0, "SDRAM": 0, "LTDC": 0, "QSPI": 0, "SDMMC": 0, "RMII": 0} for e in ["上", "下", "左", "右", "角"]}
    for b in gpio:
        rows_by_edge[bd.mcu_edge(b)]["GPIO"] += 1
    for s, port, b, ring in bd.mcu_signals():
        rows_by_edge[bd.mcu_edge(b)]["SDRAM"] += 1
    for bus, lst in bd.bus_signals().items():
        for s, port, b, ring in lst:
            rows_by_edge[bd.mcu_edge(b)][bus] += 1
    rows = []
    tot = {k: 0 for k in rows_by_edge["上"]}
    for e in ["上", "下", "左", "右", "角"]:
        d = rows_by_edge[e]
        used = sum(d[k] for k in ("SDRAM", "LTDC", "QSPI", "SDMMC", "RMII"))
        rows.append([e, d["GPIO"], d["SDRAM"], d["LTDC"], d["QSPI"], d["SDMMC"], d["RMII"], used, d["GPIO"] - used])
        for k in d:
            tot[k] += d[k]
    used = sum(tot[k] for k in ("SDRAM", "LTDC", "QSPI", "SDMMC", "RMII"))
    rows.append(["合计", tot["GPIO"], tot["SDRAM"], tot["LTDC"], tot["QSPI"], tot["SDMMC"], tot["RMII"], used, tot["GPIO"] - used])
    return table(["最近的边", "GPIO 球", "SDRAM", "LTDC", "QSPI", "SDMMC", "RMII", "以上合计", "剩余 GPIO 球"], rows), rows_by_edge


def build_bus_block(recs):
    t, _ = edge_table()
    out = ["各边的 GPIO 球数和五组信号占用（按球离哪条封装边最近算，拐角上两条边一样近的球单列为「角」；"
           "上视图，A 行在上、1 列在左）：", "", t, ""]
    for obj in ORDER:
        rk = ranked(recs, obj)
        base = baseline(recs, obj)
        sel = [(i + 1, r) for i, r in enumerate(rk[:6])] + [("基准", base)]
        rows = []
        for i, r in sel:
            m = r["m"]
            ee = m["exit_edges"]
            pa = m["pass"]
            cells = [i, label(r), tier_cell(r), f"右{ee['右']} / 下{ee['下']} / 左{ee['左']} / 上{ee['上']}",
                     " ".join(f"{e}{pa[e][0]}+{pa[e][1]}" for e in "右下左上")]
            for b in bd.BUS_ORDER:
                x = m["bus"][b]
                cells.append(f"{x['hit_same']}/{x['n']}（{x['pairs_same']}）")
            rows.append(cells)
        out.append(f"{core.OBJ_LABEL[obj]}的前 6 名和基准：SDRAM 线从 MCU 哪条边出，以及被 SDRAM 绕行折线横穿的出线走廊数 "
                   "（格式：被横穿的线数/该总线总线数（横穿次数）；只数同一出线层上的）：")
        out.append("")
        out.append(table(["名次", "摆法", "换位档", "SDRAM 线的出线边（根）", "绕行线束经过各边中点（顶层+L4，根）"]
                         + [f"{b} 被横穿" for b in bd.BUS_ORDER], rows))
        out.append("")
    return "\n".join(out)


def build_all_block(recs):
    out = []
    for obj in ORDER:
        out.append(f"#### {core.OBJ_LABEL[obj]}")
        out.append("")
        out.append("每格：有效交叉 / 总长 mm" + ("（直线交叉 / 直线总长）" if obj == "straight" else "（直线交叉 + 绕行交叉 / 绕行总长）")
                   + "；(c) 格后面括号里是 MCU 字节 0–3 接到 SDRAM 的哪个字节。")
        out.append("")
        rows = []
        by = {}
        for r in recs:
            by.setdefault((r["pos"], r["gap"], r["rot"]), {})[(r["tier"], r["obj"])] = r
        for (pos, gap, rot), d in sorted(by.items(), key=lambda kv: (list(SLUG).index(kv[0][0]), kv[0][1], kv[0][2])):
            cells = [pos, rot, f"{gap:g}"]
            for tier in "abc":
                r = d[("a", "-")] if tier == "a" else d[(tier, obj)]
                m = r["m"]
                e, l = (m["x_both"], m["wl_total"]) if obj == "both" else (m["x_eff"], m["le_total"])
                c = f"{e} / {l:.1f}"
                if tier == "c":
                    c += f"（{''.join(map(str, r['lm']))}）"
                cells.append(c)
            rows.append(cells)
        out.append(table(["位置", "转", "间距 mm", "(a) 不换位", "(b) 字节内换位", "(c) 字节内+通道互换"], rows))
        out.append("")
    return "\n".join(out)


# ------------------------------------------------------------------ SVG
def _fmt(x):
    return f"{x:.2f}"


def draw_svg(r, path, header, mode="straight"):
    """画一张草图。mode='straight'：直线飞线；mode='wrap'：绕行折线（courtyard 外按绕行模型）。"""
    pl = pl_of(r)
    perm = r["perm"]
    S = 26.0                                   # px / mm
    mcu_pads = bd.parse_pads(bd.FP_MCU)
    sdr_world = pl.sdr_all_world()
    sdr_map = bd.sdr_map()
    A = core.MCU_XY
    B = pl.sdr_world()[np.asarray(perm)]
    x0, y0, x1, y1 = pl.body_rect()
    xmin = min(-core.COURTYARD, x0) - 1.2
    xmax = max(core.COURTYARD, x1) + 1.2
    ymin = min(-core.COURTYARD, y0) - 1.2
    ymax = max(core.COURTYARD, y1) + 1.2
    head_h = 118
    W = (xmax - xmin) * S
    H = (ymax - ymin) * S + head_h
    W = max(W, 1010)

    def X(x):
        return (x - xmin) * S

    def Y(y):
        return (y - ymin) * S + head_h

    o = []
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" viewBox="0 0 {W:.0f} {H:.0f}" '
             f'font-family="{FONT}">')
    o.append(f'<rect width="100%" height="100%" fill="#ffffff"/>')
    # 标题
    for i, line in enumerate(header):
        weight = ' font-weight="bold"' if i == 0 else ""
        o.append(f'<text x="12" y="{22 + i * 19}" font-size="{15 if i == 0 else 12.5}" fill="#222"{weight}>{_esc(line)}</text>')
    # 图例
    lx, ly = 12, 22 + len(header) * 19 + 4
    cx = lx
    for g in core.GROUPS:
        o.append(f'<line x1="{cx}" y1="{ly}" x2="{cx + 20}" y2="{ly}" stroke="{GROUP_COLOR[g]}" stroke-width="3"/>')
        name = {"byte0": "字节0", "byte1": "字节1", "byte2": "字节2", "byte3": "字节3", "addr": "地址", "cmd": "命令", "clk": "时钟"}[g]
        o.append(f'<text x="{cx + 24}" y="{ly + 4}" font-size="11.5" fill="#222">{name}</text>')
        cx += 24 + 14 * len(name) + 10
    cx += 6
    o.append(f'<line x1="{cx}" y1="{ly}" x2="{cx + 26}" y2="{ly}" stroke="#444" stroke-width="2"/>')
    o.append(f'<text x="{cx + 30}" y="{ly + 4}" font-size="11.5" fill="#222">实线=外两圈（顶层出）</text>')
    cx += 30 + 11.5 * 10 + 12
    o.append(f'<line x1="{cx}" y1="{ly}" x2="{cx + 26}" y2="{ly}" stroke="#444" stroke-width="2" stroke-dasharray="5 3"/>')
    o.append(f'<text x="{cx + 30}" y="{ly + 4}" font-size="11.5" fill="#222">虚线=内两圈（L4 出）</text>')

    # 封装外形
    o.append(f'<rect x="{X(-5):.1f}" y="{Y(-5):.1f}" width="{10 * S:.1f}" height="{10 * S:.1f}" fill="#f6f6f6" stroke="#888" stroke-width="1.2"/>')
    o.append(f'<rect x="{X(-6):.1f}" y="{Y(-6):.1f}" width="{12 * S:.1f}" height="{12 * S:.1f}" fill="none" stroke="#bbb" stroke-width="0.8" stroke-dasharray="4 3"/>')
    o.append(f'<rect x="{X(x0):.1f}" y="{Y(y0):.1f}" width="{(x1 - x0) * S:.1f}" height="{(y1 - y0) * S:.1f}" fill="#f6f6f6" stroke="#888" stroke-width="1.2"/>')
    o.append(f'<text x="{X(0):.1f}" y="{Y(-6.25):.1f}" font-size="11" fill="#777" text-anchor="middle">MCU UFBGA176+25（本体 10x10，虚线 = courtyard ±6）</text>')
    o.append(f'<text x="{X(pl.cx):.1f}" y="{Y(y0) - 5:.1f}" font-size="11" fill="#777" text-anchor="middle">SDRAM 90 球 8x13，转 {pl.rot}°</text>')

    # 线
    for k in range(core.N):
        g = core.GROUPS[core.GROUP_ID[k]]
        dash = ' stroke-dasharray="5 3"' if core.LAYER[k] == 1 else ""
        if mode == "wrap":
            d = core.wire_desc(A[k], B[k], core._MCU_EDGES[k])
            pts = d["pts"]
            pstr = " ".join(f"{X(p[0]):.1f},{Y(p[1]):.1f}" for p in pts)
            o.append(f'<polyline points="{pstr}" fill="none" stroke="{GROUP_COLOR[g]}" stroke-width="1.1" opacity="0.8"{dash}/>')
        else:
            o.append(f'<line x1="{X(A[k][0]):.1f}" y1="{Y(A[k][1]):.1f}" x2="{X(B[k][0]):.1f}" y2="{Y(B[k][1]):.1f}" '
                     f'stroke="{GROUP_COLOR[g]}" stroke-width="1.1" opacity="0.8"{dash}/>')

    # MCU 球
    used = {core.MCU_BALL[k]: core.GROUPS[core.GROUP_ID[k]] for k in range(core.N)}
    other = {b for rows in bd.bus_signals().values() for _, _, b, _ in rows}
    for name, (x, y, d) in mcu_pads.items():
        if name in used:
            o.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{0.17 * S:.1f}" fill="{GROUP_COLOR[used[name]]}" stroke="#fff" stroke-width="0.6"/>')
        elif name in other:
            o.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{0.15 * S:.1f}" fill="#bdbdbd" stroke="#888" stroke-width="0.6"/>')
        else:
            o.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{0.11 * S:.1f}" fill="#e3e3e3" stroke="#c4c4c4" stroke-width="0.5"/>')
    # SDRAM 球（颜色 = 接到它的 MCU 网络所在的组，字节通道互换能直接看出来）
    sdr_color = {core.SDR_BALL[perm[k]]: GROUP_COLOR[core.GROUPS[core.GROUP_ID[k]]] for k in range(core.N)}
    for ball, (x, y) in sdr_world.items():
        if ball in sdr_color:
            o.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{0.2 * S:.1f}" fill="{sdr_color[ball]}" stroke="#fff" stroke-width="0.6"/>')
        else:
            o.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{0.17 * S:.1f}" fill="#e3e3e3" stroke="#c4c4c4" stroke-width="0.5"/>')
    # A1 标记
    ax, ay = mcu_pads["A1"][:2]
    o.append(f'<text x="{X(ax) - 4:.1f}" y="{Y(ay) - 9:.1f}" font-size="10" fill="#333" text-anchor="end">A1</text>')
    sx, sy = sdr_world["A1"]
    o.append(f'<circle cx="{X(sx):.1f}" cy="{Y(sy):.1f}" r="{0.34 * S:.1f}" fill="none" stroke="#333" stroke-width="1"/>')
    o.append(f'<text x="{X(sx):.1f}" y="{Y(sy) - 0.45 * S:.1f}" font-size="10" fill="#333" text-anchor="middle">A1</text>')
    o.append("</svg>")
    Path(path).write_text("\n".join(o), encoding="utf8")


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def header_for(r, title, obj):
    m = r["m"]
    l0 = f"{title}：SDRAM 在 MCU 的「{r['pos']}」，转 {r['rot']}°，间距 {r['gap']:g} mm，{TIER_NAME[r['tier']]}" \
         + (f"，通道 {''.join(map(str, r['lm']))}" if r["tier"] == "c" else "")
    l1 = (f"直线飞线：总长 {m['le_total']:.1f} mm（最长 {m['le_max']:.1f} / 最短 {m['le_min']:.1f}），同层交叉 {m['x_eff']}"
          f"（顶 {m['x_tt']} / L4 {m['x_ll']}），全部交叉 {m['x_all']}")
    l2 = (f"绕行模型：总长 {m['wl_total']:.1f} mm（比直线多 {m['detour']:.1f}），同层交叉 {m['wx_eff']}"
          f"（顶 {m['wx_tt']} / L4 {m['wx_ll']}），贴边绕行 {m['n_hug']} 根")
    l3 = f"优化口径：{core.OBJ_LABEL[obj] if obj in core.OBJ_LABEL else '不换位，无优化'}；MCU 固定在原点，上视图 A1 在左上"
    return [l0, l1, l2, l3]


def make_svgs(recs):
    SVG_DIR.mkdir(exist_ok=True)
    for f in SVG_DIR.glob("*.svg"):
        f.unlink()
    rk = ranked(recs, HEADLINE)
    made = []
    for i, r in enumerate(rk[:3], 1):
        name = f"rank{i}_{SLUG[r['pos']]}_rot{r['rot']}_g{r['gap']:g}_{r['tier']}"
        obj = HEADLINE if r["tier"] != "a" else "-"
        for mode in ("straight", "wrap"):
            p = SVG_DIR / f"{name}{'_wrap' if mode == 'wrap' else ''}.svg"
            draw_svg(r, p, header_for(r, f"第 {i} 名（{core.OBJ_LABEL[HEADLINE]}）", obj), mode)
            made.append(p.name)
    b = baseline(recs, HEADLINE)
    name = f"baseline_{SLUG[b['pos']]}_rot{b['rot']}_g{b['gap']:g}_a"
    for mode in ("straight", "wrap"):
        p = SVG_DIR / f"{name}{'_wrap' if mode == 'wrap' else ''}.svg"
        draw_svg(b, p, header_for(b, "基准（ST 逐位对接、不换位、放右边）", "-"), mode)
        made.append(p.name)
    make_bus_svg()
    made.append("mcu_buses.svg")
    return made


def make_bus_svg():
    S = 40.0
    pads = bd.parse_pads(bd.FP_MCU)
    cat = {}
    for s, port, b, ring in bd.mcu_signals():
        cat[b] = "SDRAM"
    for bus, lst in bd.bus_signals().items():
        for s, port, b, ring in lst:
            cat[b] = bus
    sym = bd.parse_symbol()
    gpio = {b for b, (nm, _) in sym.items() if re.match(r"P[A-K]\d", nm)}
    W, H = 760, 700
    mx, my = 140, 130
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
         '<rect width="100%" height="100%" fill="#ffffff"/>',
         '<text x="12" y="22" font-size="15" font-weight="bold" fill="#222">MCU 球阵：SDRAM 和四组其它总线（套 A）各占哪些球</text>',
         '<text x="12" y="41" font-size="12" fill="#444">上视图，A1 在左上。灰空心 = 其它 GPIO（含空闲）；更小的点 = 电源/地；虚线框 = 圈 2、3（内两圈，L4 出线）。</text>']
    lx = 12
    for k in ["SDRAM", "LTDC", "QSPI", "SDMMC", "RMII"]:
        n = {"SDRAM": 57, "LTDC": 20, "QSPI": 6, "SDMMC": 6, "RMII": 9}[k]
        o.append(f'<circle cx="{lx + 6}" cy="62" r="6" fill="{BUS_COLOR[k]}"/>')
        o.append(f'<text x="{lx + 16}" y="66" font-size="12" fill="#222">{k} {n}</text>')
        lx += 100

    def X(x):
        return mx + (x + 4.875) * S

    def Y(y):
        return my + (y + 4.875) * S

    # 圈 2、3 的范围：外边界 ±(7-2)*0.65... 圈 r 的球在 |x|或|y| = (7-r)*0.65；内两圈 = 圈 2 以内
    inner = (7 - 2) * 0.65 + 0.33
    o.append(f'<rect x="{X(-inner):.1f}" y="{Y(-inner):.1f}" width="{2 * inner * S:.1f}" height="{2 * inner * S:.1f}" fill="none" stroke="#999" stroke-width="1" stroke-dasharray="5 4"/>')
    o.append(f'<rect x="{X(-4.875):.1f}" y="{Y(-4.875):.1f}" width="{9.75 * S:.1f}" height="{9.75 * S:.1f}" fill="none" stroke="#666" stroke-width="1.2"/>')
    for name, (x, y, d) in pads.items():
        c = cat.get(name)
        if c:
            o.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{0.27 * S:.1f}" fill="{BUS_COLOR[c]}"/>')
        elif name in gpio:
            o.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{0.22 * S:.1f}" fill="#fff" stroke="#999" stroke-width="1"/>')
        else:
            o.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{0.1 * S:.1f}" fill="#999"/>')
    # 行列标
    for i, rl in enumerate(bd.ROWS):
        o.append(f'<text x="{mx - 22}" y="{Y((i - 7) * 0.65) + 4:.1f}" font-size="11" fill="#555" text-anchor="middle">{rl}</text>')
    for c in range(1, 16):
        o.append(f'<text x="{X((c - 8) * 0.65):.1f}" y="{my - 18}" font-size="11" fill="#555" text-anchor="middle">{c}</text>')
    # 各边计数
    t, byedge = edge_table()
    o.append(f'<text x="{X(0):.1f}" y="{my - 38}" font-size="12" fill="#222" text-anchor="middle">上边 GPIO {byedge["上"]["GPIO"]}：SDRAM {byedge["上"]["SDRAM"]} LTDC {byedge["上"]["LTDC"]} QSPI {byedge["上"]["QSPI"]} SDMMC {byedge["上"]["SDMMC"]} RMII {byedge["上"]["RMII"]}</text>')
    yb = my + 9.75 * S + 28
    o.append(f'<text x="{X(0):.1f}" y="{yb:.1f}" font-size="12" fill="#222" text-anchor="middle">下边 GPIO {byedge["下"]["GPIO"]}：SDRAM {byedge["下"]["SDRAM"]} LTDC {byedge["下"]["LTDC"]} QSPI {byedge["下"]["QSPI"]} SDMMC {byedge["下"]["SDMMC"]} RMII {byedge["下"]["RMII"]}</text>')
    for edge, xx, anchor in (("左", 12, "start"), ("右", W - 12, "end")):
        d = byedge[edge]
        for i, line in enumerate([f"{edge}边 GPIO {d['GPIO']}", f"SDRAM {d['SDRAM']}", f"LTDC {d['LTDC']}", f"QSPI {d['QSPI']}",
                                  f"SDMMC {d['SDMMC']}", f"RMII {d['RMII']}"]):
            o.append(f'<text x="{xx}" y="{my + 150 + i * 18}" font-size="12" fill="#222" text-anchor="{anchor}">{line}</text>')
    d = byedge["角"]
    o.append(f'<text x="{X(0):.1f}" y="{yb + 22:.1f}" font-size="12" fill="#222" text-anchor="middle">拐角（两条边一样近）GPIO {d["GPIO"]}：SDRAM {d["SDRAM"]} LTDC {d["LTDC"]} QSPI {d["QSPI"]} SDMMC {d["SDMMC"]} RMII {d["RMII"]}</text>')
    o.append("</svg>")
    (SVG_DIR / "mcu_buses.svg").write_text("\n".join(o), encoding="utf8")


# ------------------------------------------------------------------ 总入口
def make_all():
    recs = load()
    write_csv(recs)
    made = make_svgs(recs)
    print("SVG:", ", ".join(made))
    if README.exists():
        text = README.read_text(encoding="utf8")
        blocks = {"rank": build_rank_block, "tiers": build_tier_block, "swap": build_swap_block,
                  "pareto": build_pareto_block, "pos": build_pos_block, "wiring": build_wiring_block, "groups": build_group_block,
                  "buses": build_bus_block, "all": build_all_block}
        for name, fn in blocks.items():
            try:
                text = set_block(text, name, fn(recs))
            except KeyError as e:
                print("跳过：", e)
        README.write_text(text, encoding="utf8")
        print("已更新 README.md 里的自动块")
    else:
        print("README.md 还不存在，只写了 CSV 和 SVG")
    # 控制台摘要
    for obj in ORDER:
        rk = ranked(recs, obj)
        print(f"--- {core.OBJ_LABEL[obj]} 前 10 ---")
        for i, r in enumerate(rk[:10], 1):
            m = r["m"]
            print(f"{i:2d} {label(r)} {r['tier']} 通道{''.join(map(str, r['lm']))}  x_eff {m['x_eff']} le {m['le_total']:.1f} | wx_eff {m['wx_eff']} wl {m['wl_total']:.1f}")
        b = baseline(recs, obj)
        m = b["m"]
        print(f"基准 {label(b)} 第 {rk.index(b) + 1} 名: x_eff {m['x_eff']} le {m['le_total']:.1f} | wx_eff {m['wx_eff']} wl {m['wl_total']:.1f}")
