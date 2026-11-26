"""First survey of the RK3568 BGA-636: balls per ring, the RUL-12 pitch table, and how many signal balls
three signal layers (top, one inner, bottom) can take out of the ball field.

    python rk3568_ddr3_core/probes/survey/ring_capacity.py [--time 120] [--out DIR]

System python (numpy, scipy). One process, one solve at a time. A probe, not a tool (PROC-15): numbers for the
layer-count decision only.

Inputs: lib/rk3568_ddr3_core.pretty/BGA-636_*.kicad_mod (pad positions and diameter), lib/rk3568_pins.json.

Capacity model (a count on the ball lattice, not a routed board):
  * top layer: tracks run on the cell-centre lattice, between the pads. A strip of one pitch between two
    neighbouring ball positions takes cap[n] tracks, n = how many of the two positions carry a pad.
  * inner / bottom layer: tracks run on the ball lattice, between the through vias, which sit at cell centres.
    The same strip rule with the via keep-out (pad + clearance, or hole + hole-to-copper, whichever is larger).
  * every power and ground ball gets a via at one of its four cell centres (share = balls of one net per via);
    a signal ball either leaves on the top layer without a via, or gets a via and leaves on one other layer.
  * a via blocks its cell centre on the top layer. Bottom-side decoupling capacitors are not modelled.
  * done = reached the outside of the 28 x 28 field. Nothing is said about order, length or pairs staying together.
"""
import argparse
import collections
import json
import math
import os
import re
import sys
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "..", "lib")
FP = os.path.join(LIB, "rk3568_ddr3_core.pretty", "BGA-636_19x19mm_Layout28x28_P0.65mm.kicad_mod")
PINS = os.path.join(LIB, "rk3568_pins.json")
N = 28
PITCH = 0.65

RULESETS = {
    # track, clearance, via pad, via hole, pad-to-via floor, hole-to-copper
    "规格档 C 区内": dict(w=0.09, s=0.09, via=0.30, hole=0.15, pad_via=0.10, h2c=0.20),
    "嘉立创下限": dict(w=0.09, s=0.09, via=0.25, hole=0.15, pad_via=0.10, h2c=0.20),
}


# ---------------------------------------------------------------- data
def load():
    txt = open(FP, encoding="utf-8").read()
    pads = {}
    dia = set()
    for m in re.finditer(r'\(pad "(\w+)" smd circle \(at ([-\d.]+) ([-\d.]+)\) \(size ([\d.]+) ', txt):
        pads[m.group(1)] = (float(m.group(2)), float(m.group(3)))
        dia.add(float(m.group(4)))
    assert len(pads) == 636 and len(dia) == 1, (len(pads), dia)
    pins = {p["ball"]: p for p in json.load(open(PINS, encoding="utf-8"))}
    assert set(pins) == set(pads)
    x0 = min(x for x, _ in pads.values())
    y0 = min(y for _, y in pads.values())
    grid = {}
    for b, (x, y) in pads.items():
        c, r = (x - x0) / PITCH, (y - y0) / PITCH
        assert abs(c - round(c)) < 1e-6 and abs(r - round(r)) < 1e-6, b   # orthogonal lattice
        grid[b] = (round(c), round(r))
    assert max(c for c, _ in grid.values()) == N - 1 and max(r for _, r in grid.values()) == N - 1
    return grid, pins, dia.pop()


POWER_T = {"PI", "API"}
GROUND_T = {"G", "AG"}


def classify(pins):
    """ball -> ('gnd' | 'pwr' | 'sig', net). Typeless balls with a supply's name are supply balls."""
    stems = {re.sub(r"_\d+$", "", p["name"]) for p in pins.values() if p["type"] in POWER_T}
    out = {}
    for b, p in pins.items():
        stem = re.sub(r"_\d+$", "", p["name"])
        if p["type"] in GROUND_T:
            out[b] = ("gnd", "GND")
        elif p["type"] in POWER_T or (p["type"] == "" and stem in stems):
            out[b] = ("pwr", stem)
        else:
            out[b] = ("sig", p["name"])
    return out


def diff_pairs(pins, kind):
    """Pairs by name: some alias of one ball turns into an alias of another by one P->N (or DP->DM) swap."""
    alias = {}
    for b, p in pins.items():
        if kind[b][0] != "sig":
            continue
        names = p["name"].split("/")
        if p["partname"] == "DDR" and len(names) > 1:      # this board is DDR3: only that alias makes a pair
            names = [a for a in names if a.startswith("DDR3_")]
        for a in names:
            if a and a != "-":
                alias.setdefault(a, b)
    pairs = {}
    for a, b in alias.items():
        cands = {a[:i] + "N" + a[i + 1:] for i, ch in enumerate(a) if ch == "P"}
        cands |= {a[:i] + "DM" + a[i + 2:] for i in range(len(a) - 1) if a[i:i + 2] == "DP"}
        for c in cands:
            o = alias.get(c)
            if o and o != b and re.search(r"(DQS|CLK|CK|TX|RX|D\d|DP|REFCLK|SS|AUX)", a):
                pairs[frozenset((b, o))] = (a, c)
    # one ball in one pair only
    seen, out = set(), []
    for k, v in sorted(pairs.items(), key=lambda kv: kv[1]):
        if not (k & seen):
            seen |= k
            out.append((tuple(sorted(k)), v))
    return out


def ring_of(c, r):
    return min(c, r, N - 1 - c, N - 1 - r) + 1


# ---------------------------------------------------------------- RUL-12 table
def strip_caps(w, s, half):
    """Tracks through a one-pitch strip flanked by 0, 1, 2 obstacles of half-width `half` (clearance included)."""
    caps = []
    for n in (0, 1, 2):
        free = PITCH - n * half
        k = 0
        while True:
            need = (k + 1) * w + k * s + (s if n == 0 else s / 2 if n == 1 else 0)
            if need > free + 1e-9:
                break
            k += 1
        caps.append(k)
    return caps


def rul12(pad, rs):
    w, s, via, hole = rs["w"], rs["s"], rs["via"], rs["hole"]
    diag = PITCH * math.sqrt(2) / 2
    gap = PITCH - pad
    vgap = PITCH - via
    rows = [
        ("两个焊盘之间过一根线", f"空隙 {gap:.2f}；{w} + 2 × {s} = {w + 2 * s:.2f}", gap - (w + 2 * s), 0),
        ("两个焊盘之间过两根线", f"2 × {w} + 3 × {s} = {2 * w + 3 * s:.2f}", gap - (2 * w + 3 * s), 0),
        ("四个球中间放过孔（焊盘到过孔）", f"{diag:.3f} − {pad / 2:.3f} − {via / 2:.3f}", diag - pad / 2 - via / 2,
         rs["pad_via"]),
        ("过孔的孔到焊盘", f"{diag:.3f} − {pad / 2:.3f} − {hole / 2:.3f}", diag - pad / 2 - hole / 2, rs["h2c"]),
        ("两个过孔之间过一根线（铜到铜）", f"空隙 {vgap:.2f}；{w + 2 * s:.2f}", vgap - (w + 2 * s), 0),
        ("过孔的孔到那根线（线居中）", f"{PITCH / 2:.3f} − {hole / 2:.3f} − {w / 2:.3f}",
         PITCH / 2 - hole / 2 - w / 2, rs["h2c"]),
        ("两个过孔之间过两根线（孔到线）", f"({PITCH} − {hole} − 2 × {w} − {s}) / 2",
         (PITCH - hole - 2 * w - s) / 2, rs["h2c"]),
    ]
    return [(n, f, v, lim, v - lim) for n, f, v, lim in rows]


# ---------------------------------------------------------------- the model
class Model:
    def __init__(self):
        self.n = 0
        self.lb, self.ub, self.integ, self.obj = [], [], [], []
        self.rows, self.cols, self.vals, self.lo, self.hi = [], [], [], [], []
        self.m = 0

    def var(self, lb=0.0, ub=1.0, integer=False, obj=0.0):
        self.lb.append(lb); self.ub.append(ub); self.integ.append(1 if integer else 0); self.obj.append(obj)
        self.n += 1
        return self.n - 1

    def con(self, terms, lo, hi):
        acc = collections.defaultdict(float)
        for v, k in terms:
            acc[v] += k
        for v, k in acc.items():
            self.rows.append(self.m); self.cols.append(v); self.vals.append(k)
        self.lo.append(lo); self.hi.append(hi)
        self.m += 1

    def solve(self, limit):
        a = coo_matrix((self.vals, (self.rows, self.cols)), shape=(self.m, self.n)).tocsr()
        t = time.time()
        res = milp(-np.array(self.obj), constraints=LinearConstraint(a, self.lo, self.hi),
                   integrality=np.array(self.integ), bounds=Bounds(self.lb, self.ub),
                   options={"time_limit": limit, "disp": False, "mip_rel_gap": 0.0})
        return res, time.time() - t


def sites_of(c, r):
    """The four cell centres around ball (c, r); site (i, j) lies between columns i-1, i and rows j-1, j."""
    return [(c, r), (c + 1, r), (c, r + 1), (c + 1, r + 1)]


def capacity(grid, kind, top_caps, in_caps, layers, share, outer_only, limit, pairs=()):
    """layers: names of the non-top signal layers. outer_only: balls that may not use layers[0] (the inner one)."""
    assert top_caps[0] - top_caps[1] == top_caps[1] - top_caps[2] and in_caps[0] - in_caps[1] == in_caps[1] - in_caps[2]
    M = Model()
    at = {cr: b for b, cr in grid.items()}
    sig = [b for b in grid if kind[b][0] == "sig"]
    sup = [b for b in grid if kind[b][0] != "sig"]
    S = [(i, j) for i in range(N + 1) for j in range(N + 1)]           # cell centres (via sites, top nodes)
    P = [(c, r) for c in range(-1, N + 1) for r in range(-1, N + 1)]    # ball lattice, one step beyond the field
    site_terms = collections.defaultdict(list)                         # site -> [(var, 1)] making up v[s]

    # supply vias
    u = {}
    for b in sup:
        net = kind[b][1]
        av = []
        for s in sites_of(*grid[b]):
            a = M.var(integer=True)
            av.append(a)
            if (s, net) not in u:
                u[s, net] = M.var(integer=True)
                site_terms[s].append((u[s, net], 1.0))
            u.setdefault(("balls", s, net), []).append(a)
        M.con([(a, 1.0) for a in av], 1, 1)
    for k, lst in list(u.items()):
        if k[0] == "balls":
            _, s, net = k
            M.con([(a, 1.0) for a in lst] + [(u[s, net], -float(share))], -np.inf, 0)

    # signal choices
    t = {b: M.var(integer=True, obj=1.0) for b in sig}
    z = {}
    for b in sig:
        terms = [(t[b], 1.0)]
        for s in sites_of(*grid[b]):
            for L in layers:
                if L == layers[0] and b in outer_only:
                    continue
                z[b, s, L] = M.var(integer=True, obj=1.0)
                terms.append((z[b, s, L], 1.0))
                site_terms[s].append((z[b, s, L], 1.0))
        M.con(terms, -np.inf, 1)
    for s in S:
        if site_terms[s]:
            M.con(site_terms[s], -np.inf, 1)       # one via per site; v[s] is this sum

    def v_terms(s, k):
        return [(var, k * c) for var, c in site_terms.get(s, [])]

    # top layer: nodes S, sink = sites on the rim
    bal = collections.defaultdict(list)
    thru = collections.defaultdict(list)
    for (i, j) in S:
        for (di, dj) in ((1, 0), (0, 1)):
            o = (i + di, j + dj)
            if o[0] > N or o[1] > N:
                continue
            # the two ball positions flanking the crossing
            fl = [(i, j - 1), (i, j)] if di else [(i - 1, j), (i, j)]
            cap = top_caps[sum(1 for q in fl if q in at)]
            f1, f2 = M.var(ub=cap), M.var(ub=cap)
            M.con([(f1, 1.0), (f2, 1.0)], -np.inf, cap)
            bal[(i, j)] += [(f1, -1.0), (f2, 1.0)]; bal[o] += [(f1, 1.0), (f2, -1.0)]
            thru[(i, j)] += [(f2, 1.0)]; thru[o] += [(f1, 1.0)]
    for b in sig:
        tt = []
        for s in sites_of(*grid[b]):
            x = M.var()
            tt.append((x, 1.0))
            bal[s].append((x, 1.0)); thru[s].append((x, 1.0))
        M.con(tt + [(t[b], -1.0)], 0, 0)
    big = 4 * top_caps[0]
    for s in S:
        rim = s[0] in (0, N) or s[1] in (0, N)
        if rim:
            out = M.var(ub=np.inf)
            bal[s].append((out, -1.0))
        M.con(bal[s], 0, 0)
        if site_terms[s]:
            M.con(thru[s] + v_terms(s, float(big)), -np.inf, big)      # a via closes the cell centre

    # inner / bottom layers: nodes P, sink = the lattice points outside the field
    for L in layers:
        bal = collections.defaultdict(list)
        for (c, r) in P:
            for (dc, dr) in ((1, 0), (0, 1)):
                o = (c + dc, r + dr)
                if o[0] > N or o[1] > N:
                    continue
                fl = [(c + 1, r), (c + 1, r + 1)] if dc else [(c, r + 1), (c + 1, r + 1)]
                f1, f2 = M.var(ub=in_caps[0]), M.var(ub=in_caps[0])
                terms = [(f1, 1.0), (f2, 1.0)]
                for q in fl:
                    terms += v_terms(q, float(in_caps[0] - in_caps[1]))
                M.con(terms, -np.inf, in_caps[0])
                bal[(c, r)] += [(f1, -1.0), (f2, 1.0)]; bal[o] += [(f1, 1.0), (f2, -1.0)]
        for (b, s, LL), zv in z.items():
            if LL != L:
                continue
            ws = []
            for q in ((s[0] - 1, s[1] - 1), (s[0], s[1] - 1), (s[0] - 1, s[1]), (s[0], s[1])):
                x = M.var()
                ws.append((x, 1.0))
                bal[q].append((x, 1.0))
            M.con(ws + [(zv, -1.0)], 0, 0)
        for p in P:
            if p[0] in (-1, N) or p[1] in (-1, N):
                out = M.var(ub=np.inf)
                bal[p].append((out, -1.0))
            M.con(bal[p], 0, 0)

    # a pair leaves together or not at all, on the same layer
    for (a, b), _ in pairs:
        if a in t and b in t:
            M.con([(t[a], 1.0), (t[b], -1.0)], 0, 0)
            for L in layers:
                ta = [(z[k], 1.0) for k in z if k[0] == a and k[2] == L]
                tb = [(z[k], -1.0) for k in z if k[0] == b and k[2] == L]
                M.con(ta + tb, 0, 0)

    res, dt = M.solve(limit)
    info = dict(vars=M.n, cons=M.m, seconds=round(dt, 1), status=int(res.status), message=str(res.message))
    if res.x is None:
        return info, None
    x = res.x
    how = {}
    for b in sig:
        if x[t[b]] > 0.5:
            how[b] = "top"
    for (b, s, L), zv in z.items():
        if x[zv] > 0.5:
            how[b] = L
    info["escaped"] = len(how)
    info["bound"] = float(-res.mip_dual_bound) if getattr(res, "mip_dual_bound", None) is not None else None
    info["vias"] = int(round(sum(x[var] for s in S for var, _ in site_terms.get(s, []))))
    return info, how


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--time", type=float, default=120)
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--skip-model", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    grid, pins, pad = load()
    kind = classify(pins)
    pairs = diff_pairs(pins, kind)
    L = []
    P = L.append

    P(f"# RK3568 BGA-636 首次摸底：按圈统计和容量\n")
    P(f"来源：`{os.path.relpath(FP, os.path.join(HERE, '..', '..', '..'))}`（636 个焊盘，直径 {pad}，"
      f"球阵正交、球距 {PITCH}，{N} × {N} 格共 {N * N} 位，缺 {N * N - 636} 位）和 `lib/rk3568_pins.json`。\n")
    cnt = collections.Counter(k for k, _ in kind.values())
    P(f"合计：信号 {cnt['sig']}，电源 {cnt['pwr']}，地 {cnt['gnd']}；差分对 {len(pairs)} 对（按名字配）。\n")

    P("## 按圈统计（第 1 圈是最外圈）\n")
    P("| 圈 | 格位 | 有球 | 缺位 | 信号 | 电源 | 地 | 差分对的球 | DDR3 数据组的球 | DDR 其余信号 |")
    P("|---|---|---|---|---|---|---|---|---|---|")
    inpair = {b for pr, _ in pairs for b in pr}
    ddr_data = {b for b, p in pins.items() if kind[b][0] == "sig" and re.search(r"DDR3_(DQ\d|DM\d|DQS\d)", p["name"])}
    ddr_rest = {b for b, p in pins.items() if kind[b][0] == "sig" and p["partname"] == "DDR"} - ddr_data
    tot = collections.Counter()
    for k in range(1, N // 2 + 1):
        side = N - 2 * (k - 1)
        slots = side * side - (side - 2) ** 2 if side > 1 else 1
        bs = [b for b, (c, r) in grid.items() if ring_of(c, r) == k]
        row = dict(slots=slots, balls=len(bs), sig=sum(kind[b][0] == "sig" for b in bs),
                   pwr=sum(kind[b][0] == "pwr" for b in bs), gnd=sum(kind[b][0] == "gnd" for b in bs),
                   pair=sum(b in inpair for b in bs), dd=sum(b in ddr_data for b in bs),
                   dr=sum(b in ddr_rest for b in bs))
        tot.update(row)
        P(f"| {k} | {slots} | {row['balls']} | {slots - row['balls']} | {row['sig']} | {row['pwr']} | {row['gnd']} | "
          f"{row['pair']} | {row['dd']} | {row['dr']} |")
    P(f"| 合计 | {tot['slots']} | {tot['balls']} | {tot['slots'] - tot['balls']} | {tot['sig']} | {tot['pwr']} | "
      f"{tot['gnd']} | {tot['pair']} | {tot['dd']} | {tot['dr']} |\n")
    cum = 0
    line = []
    for k in range(1, N // 2 + 1):
        cum += sum(1 for b, (c, r) in grid.items() if ring_of(c, r) == k and kind[b][0] == "sig")
        line.append(f"{k} 圈内 {cum}")
    P("信号球累计（从外往里）：" + "，".join(line) + "。\n")

    P("差分对：\n")
    P("| 球 | 名字 | 所在圈 |")
    P("|---|---|---|")
    for (a, b), (na, nb) in pairs:
        P(f"| {a} / {b} | {na} / {nb} | {ring_of(*grid[a])} / {ring_of(*grid[b])} |")
    P("")

    caps = {}
    for name, rs in RULESETS.items():
        P(f"## 球距计算表（RUL-12）：{name}\n")
        P(f"线 {rs['w']}、间距 {rs['s']}、过孔 {rs['via']} / {rs['hole']}，焊盘 {pad}，球距 {PITCH}（mm）。\n")
        P("| 检查项 | 算式 | 结果 | 下限 | 余量 |")
        P("|---|---|---|---|---|")
        for n, f, v, lim, mar in rul12(pad, rs):
            P(f"| {n} | {f} | {v:.3f} | {lim if lim else '—'} | {mar:+.3f}{'（不行）' if mar < -1e-9 else ''} |")
        top = strip_caps(rs["w"], rs["s"], pad / 2 + rs["s"])
        inn = strip_caps(rs["w"], rs["s"], max(rs["via"] / 2 + rs["s"], rs["hole"] / 2 + rs["h2c"]))
        caps[name] = (top, inn)
        P(f"\n一个球距宽的通道能过的线数（两侧有 0 / 1 / 2 个障碍）：外层焊盘之间 {top}，内层和底层过孔之间 {inn}"
          f"（过孔的禁区半宽取 过孔半径 + 间距 和 孔半径 + 孔到铜 中较大的 "
          f"{max(rs['via'] / 2 + rs['s'], rs['hole'] / 2 + rs['h2c']):.3f}）。\n")
    same = len({json.dumps(v) for v in caps.values()}) == 1
    P(f"两套规则的通道容量{'相同' if same else '不同'}：{caps}。\n")

    P("## 按圈的粗算\n")
    top, inn = caps["规格档 C 区内"]
    P(f"满阵的口径：外层两个焊盘之间过 {top[2]} 根，所以顶层不打孔能出第 1、2 圈；内层和底层两个过孔之间过 "
      f"{inn[2]} 根，每层再带走 2 圈。三个信号层按满阵算带 6 圈。\n")

    if not args.skip_model:
        P("## 格点模型（整数规划，三个信号层：顶层、一个内层、底层）\n")
        P("每个电源和地的球都打一个通孔（占四球中间的位置），信号球要么顶层直接出，要么打一个孔从另一层出；"
          "只算能不能出到球阵外，不管线序、等长，也不算底层去耦电容占的地方。\n")
        P("| 情形 | 信号球 | 出得去 | 出不去 | 顶层 | 内层 | 底层 | 过孔数 | 上界 | 变量 / 约束 | 耗时 s | 求解状态 |")
        P("|---|---|---|---|---|---|---|---|---|---|---|---|")
        nsig = cnt["sig"]
        results = {}
        cases = [
            ("电源地每球一孔", 1, set(), ()),
            ("同网络两球共用一孔", 2, set(), ()),
            ("同上，DDR3 数据组只走外层", 2, ddr_data, ()),
            ("同上，差分对同层同出", 2, ddr_data, pairs),
        ]
        for label, share, outer, prs in cases:
            for rname in (["规格档 C 区内"] if same else list(caps)):
                tcap, icap = caps[rname]
                info, how = capacity(grid, kind, tcap, icap, ["inner", "bottom"], share, outer, args.time, prs)
                key = label + ("" if same else f"（{rname}）")
                results[key] = dict(info=info, how=how)
                if how is None:
                    P(f"| {key} | {nsig} | 无解 | | | | | | | {info['vars']} / {info['cons']} | {info['seconds']} | "
                      f"{info['message']} |")
                    continue
                c = collections.Counter(how.values())
                P(f"| {key} | {nsig} | {info['escaped']} | {nsig - info['escaped']} | {c['top']} | {c['inner']} | "
                  f"{c['bottom']} | {info['vias']} | {info['bound']:.0f} | {info['vars']} / {info['cons']} | "
                  f"{info['seconds']} | {info['status']} {info['message'][:40]} |")
                left = sorted(b for b in grid if kind[b][0] == "sig" and b not in how)
                if left:
                    P(f"\n出不去的球（{key}）：" + "，".join(f"{b}（{ring_of(*grid[b])} 圈）" for b in left) + "\n")
                print(key, info, flush=True)
        json.dump(results, open(os.path.join(args.out, "ring_capacity.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    open(os.path.join(args.out, "ring_capacity.md"), "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
