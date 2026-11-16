"""几何、候选、换位搜索、指标计算。没有输出格式的代码（表格和 SVG 在 report.py）。

坐标：mm，x 向右，y 向下（KiCad 板坐标）。MCU（UFBGA176+25）固定在原点、旋转 0（上视图 A1 在左上）。
SDRAM（IS42S32800J，90 球）按"位置 + 旋转 + 间距"摆放，都在顶层。旋转角按 KiCad 的习惯：逆时针为正。
"""
import itertools
import heapq
import math
import numpy as np
from scipy.optimize import linear_sum_assignment

import balldata as bd

# ------------------------------------------------------------------ 信号表（一次性算好）
SIGS = bd.mcu_signals()                       # (信号, 端口, 球, 圈)，57 项
N = len(SIGS)
SIG_NAME = [s[0] for s in SIGS]
MCU_BALL = [s[2] for s in SIGS]
MCU_XY = np.array([bd.mcu_xy(b) for b in MCU_BALL])
MCU_RING = np.array([bd.mcu_ring(b) for b in MCU_BALL])
LAYER = (MCU_RING >= 2).astype(int)           # 0 = 顶层（外两圈：圈 0、1），1 = L4（内两圈：圈 2、3）
_PIN_BALL = bd.sdr_pin_ball()
SDR_PIN = [bd._sdr_pin_name(s) for s in SIG_NAME]
SDR_BALL = [_PIN_BALL[p] for p in SDR_PIN]
SDR_LOC = np.array([bd.sdr_xy(b) for b in SDR_BALL])   # 封装内坐标，下标 = 与 MCU 信号同序的 SDRAM 引脚

GROUPS = ["byte0", "byte1", "byte2", "byte3", "addr", "cmd", "clk"]
GROUP_LABEL = {"byte0": "字节0 (D0-7+NBL0)", "byte1": "字节1 (D8-15+NBL1)", "byte2": "字节2 (D16-23+NBL2)",
               "byte3": "字节3 (D24-31+NBL3)", "addr": "地址 (A0-A12, BA0-1)", "cmd": "命令 (CKE/CS/RAS/CAS/WE)",
               "clk": "时钟 (SDCLK)"}


def _group(k):
    s = SIG_NAME[k]
    if k < 32:
        return k // 8
    if s.startswith("NBL"):
        return int(s[3])
    if s.startswith("A") or s.startswith("BA"):
        return 4
    if s == "SDCLK":
        return 6
    return 5


GROUP_ID = np.array([_group(k) for k in range(N)])
IS_DATA = np.arange(N) < 36                   # 数据 = DQ0-31 + NBL0-3；其余是地址、命令、时钟
IDENT = np.arange(N)                          # ST 一一对应

MCU_HALF = 5.0                                # MCU 本体 10 x 10
COURTYARD = 6.0                               # MCU 封装库里的 courtyard 半宽（绕行路径的障碍）
SDR_BODY = (8.0, 13.0)                        # SDRAM 本体 8 x 13（旋转 0 时 宽 x 高）

TIERS = ["a", "b", "c"]
TIER_LABEL = {"a": "(a) 不换位", "b": "(b) 字节内换位", "c": "(c) 字节内 + 字节通道互换"}
BIG = 1e4                                     # 目标 = BIG * 有效交叉数 + 总长(mm)


# ------------------------------------------------------------------ 候选摆法
def _rot(p, rot):
    x, y = p[..., 0], p[..., 1]
    c, s = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}[rot]
    return np.stack([x * c + y * s, -x * s + y * c], axis=-1)   # y 向下坐标系里的"逆时针"


class Placement:
    def __init__(self, pos, gap, rot, cx, cy, hx, hy):
        self.pos, self.gap, self.rot = pos, gap, rot
        self.cx, self.cy, self.hx, self.hy = cx, cy, hx, hy

    @property
    def key(self):
        return f"{self.pos}|{self.gap:g}|{self.rot}"

    def sdr_world(self):
        """SDRAM 57 个信号球的板坐标，顺序同 SIGS。"""
        return _rot(SDR_LOC, self.rot) + np.array([self.cx, self.cy])

    def sdr_all_world(self):
        """SDRAM 90 个球 {球号: (x, y)}。"""
        m = bd.sdr_map()
        out = {}
        for b in m:
            p = _rot(np.array(bd.sdr_xy(b)), self.rot) + np.array([self.cx, self.cy])
            out[b] = (float(p[0]), float(p[1]))
        return out

    def body_rect(self):
        return (self.cx - self.hx, self.cy - self.hy, self.cx + self.hx, self.cy + self.hy)

    def edge_gap(self):
        """本体边到边的间隙：x 向、y 向各一个（小于 0 说明在这个方向上投影重叠）。"""
        gx = abs(self.cx) - self.hx - MCU_HALF
        gy = abs(self.cy) - self.hy - MCU_HALF
        return gx, gy


SHIFT = 5.0   # "偏"某一侧：沿边方向挪 5 mm，SDRAM 中心对齐 MCU 本体的一条边


def make_placements(gaps=(5.0, 10.0), rots=(0, 90, 180, 270)):
    out = []
    for gap in gaps:
        for rot in rots:
            hx, hy = (SDR_BODY[0] / 2, SDR_BODY[1] / 2) if rot in (0, 180) else (SDR_BODY[1] / 2, SDR_BODY[0] / 2)
            R = MCU_HALF + gap + hx          # 放在左右时中心到原点的距离
            D = MCU_HALF + gap + hy          # 放在上下时
            spec = [
                ("右", R, 0), ("下", 0, D), ("左", -R, 0), ("上", 0, -D),
                ("右偏下", R, SHIFT), ("右偏上", R, -SHIFT), ("左偏下", -R, SHIFT), ("左偏上", -R, -SHIFT),
                ("下偏右", SHIFT, D), ("下偏左", -SHIFT, D), ("上偏右", SHIFT, -D), ("上偏左", -SHIFT, -D),
                ("右下角", R, D), ("左下角", -R, D), ("右上角", R, -D), ("左上角", -R, -D),
            ]
            for pos, cx, cy in spec:
                out.append(Placement(pos, gap, rot, cx, cy, hx, hy))
    return out


def check_placement(pl):
    """本体不重叠；边到边的间隙里至少有一个方向正好等于 gap（侧边位置），角位两个方向都等于 gap。"""
    gx, gy = pl.edge_gap()
    assert max(gx, gy) >= pl.gap - 1e-9, (pl.key, gx, gy)
    assert abs(max(gx, gy) - pl.gap) < 1e-9 or pl.pos.endswith("角"), (pl.key, gx, gy)
    if pl.pos.endswith("角"):
        assert abs(gx - pl.gap) < 1e-9 and abs(gy - pl.gap) < 1e-9, (pl.key, gx, gy)
    return True


# ------------------------------------------------------------------ 线段相交
def cross_pairs(P1, Q1, P2, Q2, tol=1e-9):
    """线段 (P1[i],Q1[i]) 与 (P2[j],Q2[j]) 是否真相交（端点相碰不算；共线重叠算）。返回 bool (n, m)。"""
    P1, Q1, P2, Q2 = (np.asarray(a, dtype=float) for a in (P1, Q1, P2, Q2))

    def orient(a, b, c):   # a,b: (n,2)  c: (m,2) -> (n,m)
        return ((b[:, None, 0] - a[:, None, 0]) * (c[None, :, 1] - a[:, None, 1])
                - (b[:, None, 1] - a[:, None, 1]) * (c[None, :, 0] - a[:, None, 0]))

    def sg(d):
        return np.where(np.abs(d) < tol, 0, np.sign(d))

    d1 = sg(orient(P1, Q1, P2))
    d2 = sg(orient(P1, Q1, Q2))
    d3 = sg(orient(P2, Q2, P1)).T
    d4 = sg(orient(P2, Q2, Q1)).T
    res = (d1 * d2 < 0) & (d3 * d4 < 0)
    col = (d1 == 0) & (d2 == 0) & (d3 == 0) & (d4 == 0)
    for i, j in np.argwhere(col):
        a, b, c, d = P1[i], Q1[i], P2[j], Q2[j]
        ax = 0 if abs(b[0] - a[0]) >= abs(b[1] - a[1]) else 1
        lo1, hi1 = sorted((a[ax], b[ax]))
        lo2, hi2 = sorted((c[ax], d[ax]))
        if min(hi1, hi2) - max(lo1, lo2) > 1e-9:
            res[i, j] = True
    return res


def self_cross(P, Q):
    m = cross_pairs(P, Q, P, Q)
    np.fill_diagonal(m, False)
    return m


# ------------------------------------------------------------------ 绕 MCU 的路径（补充估计）
_CORNERS = [(-COURTYARD, -COURTYARD), (COURTYARD, -COURTYARD), (COURTYARD, COURTYARD), (-COURTYARD, COURTYARD)]


def _blocked(u, v, H=COURTYARD):
    """线段 uv 是否穿过开方块 (-H,H)^2 的内部。"""
    dx, dy = v[0] - u[0], v[1] - u[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, u[0] + H), (dx, H - u[0]), (-dy, u[1] + H), (dy, H - u[1])):
        if abs(p) < 1e-12:
            if q < 0:
                return False
        else:
            r = q / p
            if p < 0:
                t0 = max(t0, r)
            else:
                t1 = min(t1, r)
    if t1 - t0 <= 1e-9:
        return False
    tm = (t0 + t1) / 2
    mx, my = u[0] + tm * dx, u[1] + tm * dy
    return abs(mx) < H - 1e-9 and abs(my) < H - 1e-9


def _shortest_around(e, t):
    """从 courtyard 边上的点 e 到外面的点 t，不穿过 courtyard 内部的最短路径。返回 (长度, 点列)。"""
    nodes = [tuple(e)] + _CORNERS + [tuple(t)]
    n = len(nodes)
    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if not _blocked(nodes[i], nodes[j]):
                d = math.dist(nodes[i], nodes[j])
                adj[i].append((j, d))
                adj[j].append((i, d))
    dist = [math.inf] * n
    prev = [None] * n
    dist[0] = 0.0
    pq = [(0.0, 0)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            if d + w < dist[v]:
                dist[v] = d + w
                prev[v] = u
                heapq.heappush(pq, (dist[v], v))
    path = [n - 1]
    while path[-1] != 0:
        path.append(prev[path[-1]])
    return dist[n - 1], [nodes[i] for i in reversed(path)]


_EDGE_VEC = {"右": (1, 0), "下": (0, 1), "左": (-1, 0), "上": (0, -1)}


def _exit_point(a, edge):
    H = COURTYARD
    if edge == "右":
        return (H, a[1]), H - a[0]
    if edge == "左":
        return (-H, a[1]), a[0] + H
    if edge == "下":
        return (a[0], H), H - a[1]
    return (a[0], -H), a[1] + H


def wrap_path(a, t, edges):
    """球 a 先垂直出到最近的 courtyard 边（拐角的球两条边一样近，取更短的），再绕着 courtyard 走到 t。
    返回 (总长, 出线边, 点列)，点列第 0 项是球，第 1 项是 courtyard 边上的出线点。"""
    best = None
    for edge in edges:
        e, stub = _exit_point(a, edge)
        L, pts = _shortest_around(e, t)
        tot = stub + L
        if best is None or tot < best[0] - 1e-12:
            best = (tot, edge, [tuple(a)] + pts)
    return best


# ---- 绕行模型的线序冲突：折线沿 courtyard 贴边走的部分按"区间嵌套"判，离开 courtyard 后的直线段按几何判
PERIM = 8 * COURTYARD


def _perim_s(p):
    """courtyard 边界上的点 p 的周长坐标：左上角 0，顺时针（屏幕上看）增加，一圈 8*COURTYARD。"""
    H = COURTYARD
    x, y = p
    if abs(y + H) < 1e-9:
        return x + H
    if abs(x - H) < 1e-9:
        return 2 * H + (y + H)
    if abs(y - H) < 1e-9:
        return 4 * H + (H - x)
    if abs(x + H) < 1e-9:
        return 6 * H + (H - y)
    raise ValueError(f"点 {p} 不在 courtyard 边界上")


def wire_desc(a, t, edges):
    """一根线的绕行描述：长度、出线边、折线、贴边方向（+1 顺时针 / -1 逆时针 / 0 直接走）、
    起点周长坐标、贴边长度、离开 courtyard 的直线段 (F -> T)。"""
    tot, edge, pts = wrap_path(a, t, edges)
    nodes = pts[1:-1]                      # 出线点 + 沿途经过的 courtyard 角
    s0 = _perim_s(nodes[0])
    if len(nodes) == 1:
        d, ell, F = 0, 0.0, nodes[0]
    else:
        s1 = _perim_s(nodes[1])
        d = 1 if (s1 - s0) % PERIM < PERIM / 2 else -1
        ell = sum(math.dist(nodes[i], nodes[i + 1]) for i in range(len(nodes) - 1))
        F = nodes[-1]
        # 多根线在同一个角离开时：贴边更长的那根在外圈。把离开点沿角的外法线方向按贴边长度微挪，
        # 让"同一点出发的线段"按这个内外次序判相交（否则共用端点的线段一律不算相交，会漏掉线序反了的情况）。
        sx = 1.0 if F[0] > 0 else -1.0
        sy = 1.0 if F[1] > 0 else -1.0
        F = (F[0] + 1e-4 * ell * sx, F[1] + 1e-4 * ell * sy)
    return {"len": tot, "edge": edge, "pts": pts, "dir": d, "s": s0, "ell": ell, "F": F, "T": tuple(t)}


def desc_arrays(descs):
    return (np.array([d["dir"] for d in descs]), np.array([d["s"] for d in descs]),
            np.array([d["ell"] for d in descs]), np.array([d["F"] for d in descs]),
            np.array([d["T"] for d in descs]))


def wrap_conflict(dirs, s, ell, F, T, tol=1e-6):
    """绕行折线两两的线序冲突（不看层）。规则：
    1. 同方向（或其中一根直接走）贴边：一根的贴边区间严格嵌在另一根里面 -> 冲突（里面那根要么先出线时穿过外面那根，
       要么离开时穿过外面那根，必交叉一次）；区间错开、起点或终点相同 -> 不冲突。
    2. 反方向贴边：两段贴边区间有正长度重叠 -> 冲突。
    3. 离开 courtyard 之后的直线段（F->T）：几何真相交 -> 冲突。"""
    n = len(s)
    C = np.zeros((n, n), dtype=bool)
    for sign in (1, -1):
        idx = np.where((dirs == sign) | (dirs == 0))[0]
        if idx.size < 2:
            continue
        u = (sign * s[idx]) % PERIM
        l = ell[idx]
        delta = (u[:, None] - u[None, :]) % PERIM
        nested = (delta > tol) & (delta + l[:, None] < l[None, :] - tol)
        C[np.ix_(idx, idx)] |= nested | nested.T
    cw = np.where(dirs == 1)[0]
    ccw = np.where(dirs == -1)[0]
    if cw.size and ccw.size:
        a, la = s[cw], ell[cw]
        b, lb = (s[ccw] - ell[ccw]) % PERIM, ell[ccw]
        o1 = ((b[None, :] - a[:, None]) % PERIM) < la[:, None] - tol
        o2 = ((a[:, None] - b[None, :]) % PERIM) < lb[None, :] - tol
        ov = o1 | o2
        C[np.ix_(cw, ccw)] |= ov
        C[np.ix_(ccw, cw)] |= ov.T
    C |= cross_pairs(F, T, F, T)
    np.fill_diagonal(C, False)
    return C


# ------------------------------------------------------------------ 其它总线的出线走廊
def bus_corridors(bus_rows):
    """[(球号, 信号, 圈, [(P, Q, 边), ...])]：每个球一条或两条（拐角的球两条边一样近）候选走廊，
    走廊 = 从 MCU 本体边（±5）垂直向外 3 mm（到 ±8）的线段。"""
    out = []
    for sig, port, ball, ring in bus_rows:
        x, y = bd.mcu_xy(ball)
        cands = []
        for edge in bd.mcu_edge_candidates(ball):
            vx, vy = _EDGE_VEC[edge]
            if edge in ("右", "左"):
                p = (vx * MCU_HALF, y)
                q = (vx * (MCU_HALF + 3.0), y)
            else:
                p = (x, vy * MCU_HALF)
                q = (x, vy * (MCU_HALF + 3.0))
            cands.append((p, q, edge))
        out.append((ball, sig, ring, cands))
    return out


_BUS = bd.bus_signals()
_CORR = {b: bus_corridors(_BUS[b]) for b in bd.BUS_ORDER}
_MCU_EDGES = [bd.mcu_edge_candidates(b) for b in MCU_BALL]


# ------------------------------------------------------------------ 评估一个分配
def evaluate(pl, perm):
    """perm[k] = 与 MCU 信号 k 相连的 SDRAM 引脚下标。返回指标字典。"""
    perm = np.asarray(perm)
    A = MCU_XY
    B = pl.sdr_world()[perm]
    d = B - A
    Le = np.hypot(d[:, 0], d[:, 1])
    Lm = np.abs(d[:, 0]) + np.abs(d[:, 1])
    X = np.triu(self_cross(A, B), 1)
    lay = LAYER
    same = lay[:, None] == lay[None, :]
    r = {}

    def stats(L, pre):
        r[pre + "_total"] = float(L.sum())
        r[pre + "_max"] = float(L.max())
        r[pre + "_min"] = float(L.min())
        r[pre + "_range"] = float(L.max() - L.min())

    stats(Le, "le")
    stats(Lm, "lm")
    dd = IS_DATA[:, None] & IS_DATA[None, :]
    aa = (~IS_DATA)[:, None] & (~IS_DATA)[None, :]
    r["x_all"] = int(X.sum())
    r["x_data"] = int((X & dd).sum())
    r["x_ac"] = int((X & aa).sum())
    r["x_mixed"] = r["x_all"] - r["x_data"] - r["x_ac"]
    r["x_tt"] = int((X & same & (lay[:, None] == 0)).sum())
    r["x_ll"] = int((X & same & (lay[:, None] == 1)).sum())
    r["x_xl"] = int((X & ~same).sum())
    r["x_eff"] = r["x_tt"] + r["x_ll"]
    r["n_top"] = int((lay == 0).sum())
    r["n_l4"] = int((lay == 1).sum())
    # 按组
    for g, name in enumerate(GROUPS):
        m = GROUP_ID == g
        r[f"g_{name}_le_min"] = float(Le[m].min())
        r[f"g_{name}_le_max"] = float(Le[m].max())
        r[f"g_{name}_lm_min"] = float(Lm[m].min())
        r[f"g_{name}_lm_max"] = float(Lm[m].max())
        r[f"g_{name}_n"] = int(m.sum())
    # 绕行模型：长度、线序冲突
    descs = [wire_desc(A[k], B[k], _MCU_EDGES[k]) for k in range(N)]
    wl = np.array([d["len"] for d in descs])
    assert (wl >= Le - 1e-9).all(), "绕行长度比直线还短，路径算错了"
    stats(wl, "wl")
    W = np.triu(wrap_conflict(*desc_arrays(descs)), 1)
    r["wx_all"] = int(W.sum())
    r["wx_tt"] = int((W & same & (lay[:, None] == 0)).sum())
    r["wx_ll"] = int((W & same & (lay[:, None] == 1)).sum())
    r["wx_eff"] = r["wx_tt"] + r["wx_ll"]
    r["wx_data"] = int((W & same & dd).sum())
    r["wx_ac"] = int((W & same & aa).sum())
    r["n_hug"] = int(sum(d["dir"] != 0 for d in descs))          # 需要贴着 courtyard 绕一段的线
    r["detour"] = float((wl - Le).sum())
    exits = {e: 0 for e in _EDGE_VEC}
    for d in descs:
        exits[d["edge"]] += 1
    r["exit_edges"] = exits
    # 绕行线束：每条边的中点处有几根线贴着 courtyard 经过（顶层 / L4 分开数）。这是线束宽度的计数，不是通道容量。
    mids = {"上": PERIM / 8 * 1, "右": PERIM / 8 * 3, "下": PERIM / 8 * 5, "左": PERIM / 8 * 7}
    pas = {e: [0, 0] for e in mids}
    for k, d in enumerate(descs):
        if d["dir"] == 0:
            continue
        lo = d["s"] if d["dir"] == 1 else d["s"] - d["ell"]
        for e, x in mids.items():
            if (x - lo) % PERIM <= d["ell"]:
                pas[e][int(lay[k])] += 1
    r["pass"] = pas
    r["bundle"] = max(sum(v) for v in pas.values())
    r["x_both"] = r["x_eff"] + r["wx_eff"]
    polys = [(d["edge"], d["pts"]) for d in descs]
    # 其它总线：SDRAM 绕行折线（courtyard 外的部分）穿过它们的出线走廊的次数
    sp, sq, sl, sk = [], [], [], []
    for k, (edge, pts) in enumerate(polys):
        for a, b in zip(pts[1:-1], pts[2:]):     # 跳过球到出线点那一段（在 courtyard 里面）
            sp.append(a)
            sq.append(b)
            sl.append(lay[k])
            sk.append(k)
    sp, sq, sl, sk = np.array(sp), np.array(sq), np.array(sl), np.array(sk)
    bus_res = {}
    for bus in bd.BUS_ORDER:
        hit_same = hit_any = pairs_same = pairs_any = 0
        for ball, sig, ring, cands in _CORR[bus]:
            blay = 0 if ring <= 1 else 1
            best = None
            for p, q, edge in cands:
                c = cross_pairs(sp, sq, np.array([p]), np.array([q]))[:, 0]
                ks_any = set(sk[c].tolist())
                ks_same = set(sk[c & (sl == blay)].tolist())
                v = (len(ks_same), len(ks_any))
                if best is None or v < best:
                    best = v
            hit_same += int(best[0] > 0)
            hit_any += int(best[1] > 0)
            pairs_same += best[0]
            pairs_any += best[1]
        bus_res[bus] = {"hit_same": hit_same, "hit_any": hit_any, "pairs_same": pairs_same, "pairs_any": pairs_any,
                        "n": len(_CORR[bus])}
    r["bus"] = bus_res
    return r


# ------------------------------------------------------------------ 换位搜索
PERMS = np.array(list(itertools.permutations(range(8))), dtype=np.intp)   # 8! = 40320
PAIRS = list(itertools.combinations(range(8), 2))
FIXED_IDS = np.arange(1040, 1061)             # 21 根固定线：A0-12, BA0-1, SDCLK, SDCKE0, SDNE0, SDNRAS, SDNCAS, SDNWE
_B8 = np.arange(8)


def build_universe(sdr_world):
    """所有可能出现的线：数据 i->j（32x32，id = i*32+j）、NBL m->s（4x4，id = 1024+4m+s）、固定线（id = 1040+k-36）。
    返回 {'straight': (C, L), 'wrap': (C, L)}：C 是有效交叉矩阵（两根线冲突且出线层相同），L 是长度。
    straight = 直线飞线（线段真相交；长度为直线）；wrap = 绕行模型（线序冲突规则见 wrap_conflict；长度为绕行长度）。"""
    ii, jj = np.meshgrid(np.arange(32), np.arange(32), indexing="ij")
    mi, si = np.meshgrid(np.arange(4), np.arange(4), indexing="ij")
    src = np.concatenate([ii.ravel(), 32 + mi.ravel(), np.arange(36, N)])
    dst = np.concatenate([jj.ravel(), 32 + si.ravel(), np.arange(36, N)])
    P = MCU_XY[src]
    Q = sdr_world[dst]
    same = LAYER[src][:, None] == LAYER[src][None, :]
    Cs = self_cross(P, Q) & same
    Ls = np.hypot(*(Q - P).T)
    descs = [wire_desc(P[w], Q[w], _MCU_EDGES[src[w]]) for w in range(len(src))]
    Cw = wrap_conflict(*desc_arrays(descs)) & same
    Lw = np.array([d["len"] for d in descs])
    Cb = Cs.astype(np.int8) + Cw.astype(np.int8)
    return {"straight": (Cs, Ls), "wrap": (Cw, Lw), "both": (Cb, Lw)}


def state_ids(lm, pis):
    ids = list(FIXED_IDS)
    for m in range(4):
        s = lm[m]
        ids += list((8 * m + _B8) * 32 + 8 * s + np.asarray(pis[m]))
        ids.append(1024 + m * 4 + s)
    return np.array(ids)


def state_cost(C, L, ids):
    conf = int(C[np.ix_(ids, ids)].sum() // 2)
    return BIG * conf + float(L[ids].sum()), conf


def state_perm(lm, pis):
    perm = IDENT.copy()
    for m in range(4):
        s = lm[m]
        for b in range(8):
            perm[8 * m + b] = 8 * s + pis[m][b]
        perm[32 + m] = 32 + s
    return perm


def _lane_opt(C, L, others, m, s):
    wsub = (8 * m + _B8)[:, None] * 32 + (8 * s + _B8)[None, :]
    wn = 1024 + m * 4 + s
    flat = wsub.ravel()
    ext = C[np.ix_(flat, others)].sum(1) + C[flat, wn]
    E = BIG * ext.reshape(8, 8) + L[wsub]
    cost = E[_B8[None, :], PERMS].sum(1)
    P4 = C[wsub[:, :, None, None], wsub[None, None, :, :]]
    for b1, b2 in PAIRS:
        cost += BIG * P4[b1, PERMS[:, b1], b2, PERMS[:, b2]]
    i = int(np.argmin(cost))
    return PERMS[i]


def _search(C, L, lm, inits, max_sweeps=25):
    best = None
    for init in inits:
        pis = [np.array(p) for p in init]
        cur, _ = state_cost(C, L, state_ids(lm, pis))
        for _ in range(max_sweeps):
            changed = False
            for m in range(4):
                ids = state_ids(lm, pis)
                lane_ids = set((8 * m + _B8) * 32 + 8 * lm[m] + pis[m]) | {1024 + m * 4 + lm[m]}
                others = np.array([i for i in ids if i not in lane_ids])
                new = _lane_opt(C, L, others, m, lm[m])
                if not np.array_equal(new, pis[m]):
                    trial = [p.copy() for p in pis]
                    trial[m] = new
                    c2, _ = state_cost(C, L, state_ids(lm, trial))
                    if c2 < cur - 1e-9:
                        pis, cur, changed = trial, c2, True
            if not changed:
                break
        if best is None or cur < best[0] - 1e-9:
            best = (cur, list(lm), [p.copy() for p in pis])
    return best


def _hung_init(L, lm):
    out = []
    for m in range(4):
        wsub = (8 * m + _B8)[:, None] * 32 + (8 * lm[m] + _B8)[None, :]
        r, c = linear_sum_assignment(L[wsub])
        out.append(c[np.argsort(r)])
    return out


OBJECTIVES = ["straight", "both"]
OBJ_LABEL = {"straight": "直线飞线（规格口径）", "wrap": "绕行模型", "both": "综合口径"}
OBJ_DESC = {"straight": "先最少同层直线交叉，再最短直线总长",
            "both": "先最少（同层直线交叉 + 同层绕行交叉），再最短绕行总长"}


def _solve_obj(C, L, rng, n_random, top_k):
    ident_lm = [0, 1, 2, 3]
    ident_pis = [np.arange(8)] * 4
    ra = (state_cost(C, L, state_ids(ident_lm, ident_pis))[0], ident_lm, ident_pis)
    inits = [ident_pis, _hung_init(L, ident_lm)] + [[rng.permutation(8) for _ in range(4)] for _ in range(n_random)]
    rb = _search(C, L, ident_lm, inits)
    if rb[0] > ra[0]:
        rb = ra
    # c：24 种通道对应，先各跑一次（Hungarian 起点），再对最好的 top_k 种加几个起点；(b) 的解也算一个候选
    stage = []
    for lm in itertools.permutations(range(4)):
        lm = list(lm)
        stage.append(_search(C, L, lm, [_hung_init(L, lm)]))
    stage.sort(key=lambda t: t[0])
    cands = [rb]
    for cost, lm, pis in stage[:top_k]:
        more = [pis, ident_pis] + [[rng.permutation(8) for _ in range(4)] for _ in range(n_random)]
        cands.append(_search(C, L, lm, more))
    rc = min(cands, key=lambda t: t[0])
    assert rc[0] <= rb[0] + 1e-9 and rb[0] <= ra[0] + 1e-9
    return ra, rb, rc


def solve(pl, seed=0, n_random=3, top_k=4):
    """返回 {'a': 解, 'straight': {'b': 解, 'c': 解}, 'wrap': {'b': 解, 'c': 解}}，解 = {perm, lm, cost}。
    a = ST 一一对应；b = 字节内任意换；c = 字节内换 + 四个字节通道整体互换（NBL 跟着字节走）。
    目标 = 先最少有效交叉（同一出线层上的冲突），再最短总长；'straight' 和 'wrap' 是两种冲突和长度的算法。
    b、c 是启发式的局部最优（逐字节穷举 8! 种排列，反复扫到不再变好，多个起点），不保证全局最优；但保证 c <= b <= a。"""
    univ = build_universe(pl.sdr_world())
    out = {}
    for oi, obj in enumerate(OBJECTIVES):
        C, L = univ[obj]
        rng = np.random.default_rng(seed * 10 + oi)
        ra, rb, rc = _solve_obj(C, L, rng, n_random, top_k)
        if "a" not in out:
            out["a"] = {"perm": state_perm(ra[1], ra[2]).tolist(), "lm": [0, 1, 2, 3], "cost": float(ra[0])}
        out[obj] = {}
        for t, r in (("b", rb), ("c", rc)):
            out[obj][t] = {"perm": state_perm(r[1], r[2]).tolist(), "lm": [int(x) for x in r[1]], "cost": float(r[0])}
    return out


# ------------------------------------------------------------------ 自检
def check_assignment(perm, tier):
    """57 个信号都配上了；字节内的 8 位仍在同一个 SDRAM 字节里；NBL 跟着字节走；固定线没换。"""
    perm = list(perm)
    assert len(perm) == N, "线数不是 57"
    assert sorted(perm) == list(range(N)), "有 SDRAM 引脚被用了两次或没用"
    lane_map = []
    for m in range(4):
        tgt = {perm[8 * m + b] // 8 for b in range(8)}
        assert len(tgt) == 1, f"MCU 字节 {m} 的 8 位分到了 SDRAM 的多个字节 {tgt}"
        s = tgt.pop()
        assert perm[32 + m] == 32 + s, f"NBL{m} 没有跟着字节 {m} 走：接到了 SDRAM 引脚 {perm[32 + m]}"
        lane_map.append(s)
    assert sorted(lane_map) == [0, 1, 2, 3], "字节通道映射不是一一对应"
    for k in range(36, N):
        assert perm[k] == k, f"固定线 {SIG_NAME[k]} 被换了位"
    if tier == "a":
        assert perm == list(range(N)), "(a) 档不是 ST 一一对应"
    if tier == "b":
        assert lane_map == [0, 1, 2, 3], "(b) 档不应换字节通道"
    return lane_map
