#!/usr/bin/env python
"""SDRAM 摆放和换位的飞线级对比。用法：

    python study.py run [--workers 12] [--quick]   # 校验数据 -> 搜索 -> 评估 -> 自检 -> results.json -> 出报告
    python study.py report                        # 只用 results.json 重出 results.csv、SVG 和 README 里的表
    python study.py optcheck                      # 抽几个摆法，用大量随机起点检查换位搜索有没有被更好的解打败
    python study.py verify                        # 手算用例 + 球位校验反例 + 用当前代码重新评估 results.json 里的全部分配

依赖：numpy、scipy（linear_sum_assignment）。数据和校验见 balldata.py，几何和搜索见 core.py，
表格和 SVG 见 report.py。不打开、不生成任何 KiCad 工程，只读 KiCad 自带的封装和符号文件做球位核对。
"""
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

import balldata as bd
import core

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results.json"


def _work(args):
    idx, params = args
    pos, gap, rot, cx, cy, hx, hy = params
    pl = core.Placement(pos, gap, rot, cx, cy, hx, hy)
    t0 = time.time()
    sol = core.solve(pl, seed=idx)
    recs = []
    plan = [("a", "-", sol["a"])]
    for obj in core.OBJECTIVES:
        for tier in ("b", "c"):
            plan.append((tier, obj, sol[obj][tier]))
    for tier, obj, s in plan:
        lm = core.check_assignment(s["perm"], tier)          # 57 根都配上、字节内不串、NBL 跟着走
        m = core.evaluate(pl, s["perm"])
        # 搜索里用的矩阵和评估用的独立算法对账
        if obj == "both":
            want = core.BIG * m["x_both"] + m["wl_total"]
        else:                                                # a 档的 cost 记的是 straight 口径
            want = core.BIG * m["x_eff"] + m["le_total"]
        assert abs(want - s["cost"]) < 1e-6, (pl.key, tier, obj, want, s["cost"])
        recs.append({"pos": pl.pos, "gap": pl.gap, "rot": pl.rot, "cx": pl.cx, "cy": pl.cy, "tier": tier, "obj": obj,
                     "perm": s["perm"], "lm": lm, "m": m})
    return idx, recs, time.time() - t0


def run(workers=12, quick=False):
    iss, facts = bd.verify_all()
    print("球位数据校验：", facts)
    if iss:
        print("数据对不上，停止：")
        for i in iss:
            print("  -", i)
        sys.exit(1)
    print("球位数据校验通过（0 个问题）。")
    pls = core.make_placements()
    for p in pls:
        core.check_placement(p)
    if quick:
        pls = [p for p in pls if p.gap == 5 and p.pos in ("右", "下", "右下角") and p.rot in (0, 90)]
    tasks = [(i, (p.pos, p.gap, p.rot, p.cx, p.cy, p.hx, p.hy)) for i, p in enumerate(pls)]
    print(f"{len(tasks)} 个摆法 x 5 个分配（a, b/c x 2 种目标），{workers} 个进程")
    t0 = time.time()
    out = {}
    with Pool(workers) as pool:
        for n, (idx, recs, dt) in enumerate(pool.imap_unordered(_work, tasks), 1):
            out[idx] = recs
            if n % 8 == 0 or n == len(tasks):
                print(f"  {n}/{len(tasks)}  用时 {time.time() - t0:.0f}s", flush=True)
    records = [r for i in sorted(out) for r in out[i]]
    # 全体自检
    n_chk = 0
    for r in records:
        core.check_assignment(r["perm"], r["tier"])
        n_chk += 1
    print(f"自检：{n_chk} 个分配全部通过（57 根配齐、字节内 8 位不串字节、NBL 跟着走、固定线没换）")
    RESULTS.write_text(json.dumps({"data_facts": facts, "records": records}, ensure_ascii=False), encoding="utf8")
    print("已写", RESULTS)
    return records


def unit_tests():
    """几何函数的手算用例。"""
    cp = core.cross_pairs
    A = np.array
    # 线段相交：X 形相交；T 形端点相碰不算；平行不算；共线重叠算；共线不重叠不算
    assert cp(A([[0, 0]]), A([[2, 2]]), A([[0, 2]]), A([[2, 0]]))[0, 0]
    assert not cp(A([[0, 0]]), A([[2, 0]]), A([[1, 0]]), A([[1, 2]]))[0, 0]
    assert not cp(A([[0, 0]]), A([[2, 0]]), A([[0, 1]]), A([[2, 1]]))[0, 0]
    assert cp(A([[0, 0]]), A([[2, 0]]), A([[1, 0]]), A([[3, 0]]))[0, 0]
    assert not cp(A([[0, 0]]), A([[1, 0]]), A([[2, 0]]), A([[3, 0]]))[0, 0]
    # 绕行路径：左边的球 (-4.55, 0) 到右边很远的点 (14, 0)：出线 1.45 + 6 + 12 + sqrt(8^2+6^2)
    tot, edge, pts = core.wrap_path((-4.55, 0.0), (14.0, 0.0), ["左"])
    assert abs(tot - (1.45 + 6 + 12 + 10)) < 1e-9 and edge == "左", (tot, edge)
    # 能直接出的：右边的球 (4.55, 0) 到 (14, 0)，直线 9.45
    tot, edge, pts = core.wrap_path((4.55, 0.0), (14.0, 0.0), ["右"])
    assert abs(tot - 9.45) < 1e-9
    # 线序冲突：A 从上边 (-3, -6) 贴边到右上角再出去；B 在 A 贴边区间内的 (3, -6) 直接向外 -> 必冲突；C 在区间外 (-5.5, -6) -> 不冲突
    da = core.wire_desc((-3.0, -4.55), (14.0, -3.0), ["上"])
    db = core.wire_desc((3.0, -4.55), (14.0, -8.0), ["上"])
    dc = core.wire_desc((-5.5, -4.55), (14.0, -9.0), ["上"])
    assert da["dir"] == 1 and db["dir"] == 0 and dc["dir"] == 0, (da["dir"], db["dir"], dc["dir"])
    W = core.wrap_conflict(*core.desc_arrays([da, db, dc]))
    assert W[0, 1] and W[1, 0] and not W[0, 2] and not W[1, 2], W
    print("几何手算用例：通过")
    # 球位校验的反例：故意改错一个球号、一个圈号、一个端口，校验必须全部报出
    keep = (bd.SDRAM_TXT, bd.BUS_TXT["LTDC"])
    try:
        bd.SDRAM_TXT = bd.SDRAM_TXT.replace("D4 PE7 R8 0", "D4 PE7 R9 0").replace("NBL0 PE0 A4 0", "NBL0 PE0 A4 1")
        bd.BUS_TXT["LTDC"] = bd.BUS_TXT["LTDC"].replace("LTDC_R3 PB0 R5 0", "LTDC_R3 PB1 R5 0")
        iss, _ = bd.verify_all()
    finally:
        bd.SDRAM_TXT, bd.BUS_TXT["LTDC"] = keep
    text = " ".join(iss)
    assert len(iss) >= 5 and "报告圈号" in text and "报告端口" in text and "被多个信号占用" in text, iss
    print(f"球位校验反例：故意改错 3 处，报出 {len(iss)} 个问题：通过")


def verify():
    """用当前代码把 results.json 里的 640 个分配重新评估一遍，核对：自检条件、指标和存下来的一致。"""
    unit_tests()
    data = json.loads(RESULTS.read_text(encoding="utf8"))
    iss, facts = bd.verify_all()
    assert not iss, iss
    bad = 0
    for r in data["records"]:
        hx, hy = (4.0, 6.5) if r["rot"] in (0, 180) else (6.5, 4.0)
        pl = core.Placement(r["pos"], r["gap"], r["rot"], r["cx"], r["cy"], hx, hy)
        core.check_placement(pl)
        lm = core.check_assignment(r["perm"], r["tier"])
        assert lm == r["lm"]
        m = core.evaluate(pl, r["perm"])
        for k in ("x_eff", "x_all", "x_both", "wx_eff", "bundle"):
            if m[k] != r["m"][k]:
                bad += 1
                print("不一致", pl.key, r["tier"], r["obj"], k, m[k], r["m"][k])
        for k in ("le_total", "lm_total", "wl_total"):
            if abs(m[k] - r["m"][k]) > 1e-6:
                bad += 1
                print("不一致", pl.key, r["tier"], r["obj"], k, m[k], r["m"][k])
    print(f"重新评估 {len(data['records'])} 个分配：不一致 {bad} 处；球位校验 {facts}")
    return bad


def optcheck(n_starts=150):
    """抽几个摆法，对 b 和 c 档用大量随机起点再搜一遍，看有没有比 solve() 给的解更好的。"""
    data = json.loads(RESULTS.read_text(encoding="utf8"))
    recs = data["records"]
    keys = [("右", 5.0, 0), ("下偏右", 5.0, 90), ("左", 10.0, 180), ("右下角", 5.0, 270)]
    rng = np.random.default_rng(2024)
    worse = 0
    for pos, gap, rot in keys:
        pl = [p for p in core.make_placements() if p.pos == pos and p.gap == gap and p.rot == rot][0]
        univ = core.build_universe(pl.sdr_world())
        for obj in core.OBJECTIVES:
            C, L = univ[obj]
            for tier in ("b", "c"):
                rec = [r for r in recs if r["pos"] == pos and r["gap"] == gap and r["rot"] == rot
                       and r["tier"] == tier and r["obj"] == obj][0]
                m = rec["m"]
                have = core.BIG * (m["x_both"] if obj == "both" else m["x_eff"]) + (m["wl_total"] if obj == "both" else m["le_total"])
                best = np.inf
                if tier == "b":
                    lms = [[0, 1, 2, 3]]
                else:
                    import itertools
                    lms = [list(x) for x in itertools.permutations(range(4))]
                per = max(1, n_starts // len(lms))
                for lm in lms:
                    inits = [[rng.permutation(8) for _ in range(4)] for _ in range(per)]
                    r = core._search(C, L, lm, inits)
                    best = min(best, r[0])
                verdict = "没有更好" if best >= have - 1e-6 else f"找到更好的：{best:.1f} < {have:.1f}"
                if best < have - 1e-6:
                    worse += 1
                print(f"{pos}|{gap:g}|{rot} {obj:8s} {tier}: solve={have:.1f}  随机起点最好={best:.1f}  -> {verdict}")
    print("被更好的解打败的次数：", worse)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        w = 12
        if "--workers" in sys.argv:
            w = int(sys.argv[sys.argv.index("--workers") + 1])
        run(workers=w, quick="--quick" in sys.argv)
        import report
        report.make_all()
    elif cmd == "report":
        import report
        report.make_all()
    elif cmd == "optcheck":
        optcheck()
    elif cmd == "verify":
        sys.exit(1 if verify() else 0)
    else:
        print(__doc__)
