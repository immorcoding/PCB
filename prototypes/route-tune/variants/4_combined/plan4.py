"""PROTOTYPE (issue 21) variants 4_combined / 4b_combined_p05: one description of the bus, two serpentine pitches.

make(data_pitch) returns everything a routes.py needs. The ROUTES are identical for both pitches; only the
serpentine blocks differ (data / DQM pitch 0.3 or 0.5; SDCLK has no serpentine at all in this plan).

Idea (numbers in PLAN.md): the longest net (NBL0, MCU top-left corner -> SDRAM far column) is made as short
as it can be; that fixes the clock length (NBL0 - 2.5) and the lower edge of the window (NBL0 - 5).
Nets that need +10 mm and more get it from the ROUTE (two nested U-turn bundles on L1), nets that need a few
mm get one equal-height serpentine block, placed under the SDRAM body on L6 wherever possible.
Coordinates: local mm, y down (lib/README.md).
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib"))
from bundle import Bundle, Bus, BundleError

L1, L4, L6 = "L1", "L4", "L6"


def dg(k):
    """Gap on a diagonal leg that moves a lane line by k mm in x (or y)."""
    return k / 2 ** 0.5 - 1e-7


# Swap table = 0_base's (lanes not swapped). Checked against the needs: lane 1 (MCU south / south-east balls)
# stays on the near columns, lane 0 on the far columns; see PLAN.md for the alternative that was computed.
SWAP = {
    "FMC_SDCLK": "CLK", "FMC_NBL0": "DQM0", "FMC_NBL1": "DQM1",
    "FMC_D15": "DQ8", "FMC_D14": "DQ10", "FMC_D13": "DQ12", "FMC_D10": "DQ9",
    "FMC_D11": "DQ14", "FMC_D12": "DQ11", "FMC_D8": "DQ15", "FMC_D9": "DQ13",
    "FMC_D3": "DQ7", "FMC_D2": "DQ5", "FMC_D1": "DQ6", "FMC_D0": "DQ3",
    "FMC_D6": "DQ1", "FMC_D7": "DQ4", "FMC_D5": "DQ0", "FMC_D4": "DQ2",
}

# ---- knobs found by "compute, build fast, look" (see PLAN.md for the rounds)
TOP_D14 = 6.06          # y of D14 (the anchor lane) on the top run of the gap U-turn
TOP_CLK_GAP = 1.96      # SDCLK runs this far outside D15 on the top run (0.5 on the two vertical runs)
WEST_D11 = 8.85        # x where D11 (inner lane) turns round in the U-turn below the MCU
MARGIN = 0.45           # serpentines aim at (lower window edge + MARGIN)


def make(data_pitch=0.3, verbose=True):
    bus = Bus(SWAP)

    # ---------------------------------------------------------------- L1, gap between the chips: SDCLK D15 D14 D13
    # east out of the MCU, north up the gap, round, south down the gap, east into the SDRAM rows J, L/M.. channels.
    # Lane 0 (SDCLK) is the outer lane of the U-turn; it joins on the northward run.
    T = TOP_D14
    gap = Bundle("gap", ["SDCLK", "D15", "D14", "D13"], L1, anchor="D14",
                 path=[(17.225, 15.575), (19.5, 15.575), (20.1, 14.975), (20.1, T + 0.51), (20.61, T),
                       (21.34, T), (21.85, T + 0.51), (21.85, 18.1), (22.45, 18.7), (24.2, 18.7)],
                 pitch=0.4,
                 gaps={0: 0.325, 1: [0.5, 0.36, 0.36], 2: [0.5, 0.4, 0.4], 3: [dg(TOP_CLK_GAP + 0.24), 0.4, 0.4], 4: [TOP_CLK_GAP, 0.4, 0.4],
                       5: [dg(TOP_CLK_GAP + 0.24), 0.4, 0.4], 6: [0.5, 0.4, 0.4], 7: [dg(1.7), dg(1.2), dg(1.2)], 8: [1.2, 0.8, 0.8]},
                 span={"SDCLK": (2, 8)})
    bus.add(gap,
            start={"SDCLK": ["U1", (17.225, 12.325), (18.6, 12.325)], "D15": "U1", "D14": ["U1", (17.225, 15.575)], "D13": "U1"},
            end={"SDCLK": "U2", "D15": [(24.2, 17.9), "U2"], "D14": [(24.2, 18.7), "U2"], "D13": [(24.2, 19.5), "U2"]})

    # ---------------------------------------------------------------- L1, below the MCU: D11 D12 D8 D9
    # south out of the MCU, west along its south edge, round, east again straight onto the SDRAM rows.
    yw = 19.35                                              # D11 (inner lane) on the westward run; D9 is 0.9 north of it
    south = Bundle("south", ["D11", "D12", "D8", "D9"], L1, anchor="D11",
                   path=[(15.275, 16.6), (15.275, yw - 0.9), (14.375, yw), (WEST_D11 + 0.275, yw), (WEST_D11, yw + 0.275),
                         (WEST_D11, 20.3 - 0.275), (WEST_D11 + 0.275, 20.3), (25.0, 20.3)],
                   pitch=0.3, gaps={0: 0.325, 6: 0.4})
    bus.add(south,
            start={"D11": ["U1", (15.275, 16.225)], "D12": "U1", "D8": ["U1", (14.625, 16.225)], "D9": "U1"},
            end={"D11": [(25.0, 20.3), "U2"], "D12": "U2", "D8": [(24.2, 21.1), "U2"], "D9": "U2"})

    # ---------------------------------------------------------------- L6: NBL0 and D2, one diagonal from above the MCU
    # straight under the SDRAM to the far column (this is what makes the longest net short)
    top = Bundle("top6", ["NBL0", "D2"], L6, anchor="NBL0",
                 path=[(10.4, 6.5), (10.75, 6.15), (18.85, 6.15), (29.8, 17.1), (29.8, 18.0)],
                 pitch=dg(0.4), gaps={1: 0.35, 3: 1.2}, span={"NBL0": (0, 2), "D2": (1, 3)})
    bus.add(top,
            start={"NBL0": {"pieces": [(L1, ["U1", (10.4, 6.5)])]}, "D2": {"pieces": [(L1, ["U1", (15.925, 7.775), (15.925, 6.9)])]}},
            end={"NBL0": {"pieces": [(L1, [(29.8, 17.1), "U2"])]}, "D2": {"pieces": [(L1, [(29.0, 18.7), "U2"])]}})

    # ---------------------------------------------------------------- L4: NBL1 round the MCU corner, D3 out of the MCU,
    # together down the SDRAM's edge band (leaves the gap on L4 free for D10's serpentine)
    n1 = Bundle("top4", ["NBL1"], L4, anchor="NBL1", path=[(9.75, 6.5), (10.1, 6.15), (18.0, 6.15)], pitch=0.3)
    bus.add(n1, start={"NBL1": {"pieces": [(L1, ["U1", (9.75, 6.5)])]}})
    down = Bundle("down4", ["NBL1", "D3"], L4, anchor="D3",
                  path=[(15.925, 9.075), (21.5, 9.075), (22.3, 9.875), (22.3, 16.8), (23.0, 17.5), (28.6, 17.5)],
                  pitch=0.4, gaps={0: 3.575, 1: dg(0.775), 3: dg(0.8), 4: 0.4}, span={"NBL1": (1, 3)})
    bus.add(down, start={"D3": {"pieces": [(L1, ["U1", (15.925, 9.075)])]}},
            end={"NBL1": {"pieces": [(L1, [(23.4, 17.1), "U2"])]}, "D3": {"pieces": [(L1, [(29.0, 17.9), "U2"])]}})

    # ---------------------------------------------------------------- L4: D10 (third ball ring, dog-bone via), alone
    d10 = Bundle("d10", ["D10"], L4, anchor="D10",
                 path=[(15.275, 14.925), (20.25, 14.925), (20.5, 15.175), (20.5, 18.45), (20.75, 18.7), (25.0, 18.7)], pitch=0.3)
    s_d10 = d10.slot("D10", 2, s0=0.36, length=3.275 - 0.72, side="both", pitch=data_pitch, amp_cap=1.31)
    bus.add(d10, start={"D10": {"pieces": [(L1, ["U1", (15.275, 14.925)])]}}, end={"D10": {"pieces": [(L1, [(25.0, 18.7), "U2"])]}})

    # ---------------------------------------------------------------- L6: D1 D0 from the MCU's east edge, under the SDRAM
    # above the data rows (room for their two blocks side by side), then down the ball-free middle strip
    east = Bundle("east6", ["D1", "D0"], L6, anchor="D0",
                  path=[(18.5, 14.275), (19.6, 14.275), (21.825, 16.5), (27.1, 16.5), (27.8, 17.2), (27.8, 19.2), (28.1, 19.5), (29.0, 19.5)],
                  pitch=0.4, gaps={0: 0.65, 1: 0.65, 2: 1.2, 3: dg(1.1), 4: 0.4}, span={"D1": (0, 4)})
    s_d1 = east.slot("D1", 2, s0=0.6, length=3.65, side="L", pitch=data_pitch, amp_cap=1.25)
    s_d0 = east.slot("D0", 2, s0=0.6, length=4.0, side="L", pitch=data_pitch)
    bus.add(east,
            start={"D1": {"pieces": [(L1, ["U1", (17.225, 13.625), (18.5, 13.625)])]}, "D0": {"pieces": [(L1, ["U1", (17.225, 14.275), (18.5, 14.275)])]}},
            end={"D1": {"pieces": [(L1, [(28.2, 18.7), "U2"])]}, "D0": {"pieces": [(L1, [(29.0, 19.5), "U2"])]}})

    # ---------------------------------------------------------------- L6: D6 D7 D5 D4 from the MCU's south edge
    under = Bundle("under6", ["D6", "D7", "D5", "D4"], L6, anchor="D6",
                   path=[(13.975, 17.7), (13.975, 18.4), (15.475, 19.9), (27.0, 19.9)],
                   pitch=0.3, gaps={0: 0.325, 2: [0.4, 0.8, 0.8]})
    s_d6 = under.slot("D6", 2, s0=7.0, length=4.3, side="L", pitch=data_pitch, amp_cap=0.8)
    s_d7 = under.slot("D7", 2, s0=7.0, length=6.2, side="R", pitch=data_pitch)
    s_d5 = under.slot("D5", 2, s0=7.0, length=3.3, side="R", pitch=data_pitch)
    s_d4 = under.slot("D4", 2, s0=10.7, length=2.4, side="L", pitch=data_pitch)       # same row gap as D5's block, further east
    bus.add(under,
            start={"D6": {"pieces": [(L1, ["U1", (13.975, 16.225), (13.975, 17.7)])]}, "D7": {"pieces": [(L1, ["U1", (13.65, 17.3)])]},
                   "D5": {"pieces": [(L1, ["U1", (13.325, 16.225), (13.325, 17.7)])]}, "D4": {"pieces": [(L1, ["U1", (13.0, 17.3)])]}},
            end={"D6": {"pieces": [(L1, [(28.0, 19.9), "U2"])]}, "D7": {"pieces": [(L1, [(29.8, 20.3), "U2"])]},
                 "D5": {"pieces": [(L1, [(29.0, 21.1), "U2"])]}, "D4": {"pieces": [(L1, [(29.8, 21.9), "U2"])]}})

    routes = bus.routes(strict=not os.environ.get("RT4_LOOSE"))
    if verbose:
        print(bus.report())

    # ---------------------------------------------------------------- serpentines: one equal-height block per slot,
    # sized from the lengths just computed: bring the net to (SDCLK - 2.5 + MARGIN)
    Ls = {n: v["total"] for n, v in bus.lengths().items()}
    clk = Ls["FMC_SDCLK"]
    goal = clk - 2.5 + MARGIN
    slots = {"FMC_D10": s_d10, "FMC_D1": s_d1, "FMC_D0": s_d0, "FMC_D6": s_d6, "FMC_D7": s_d7, "FMC_D5": s_d5, "FMC_D4": s_d4}
    blocks, missing = {}, {}
    for net, s in slots.items():
        need = goal - Ls[net]
        if need <= 0:
            continue
        try:
            if s.side != "both" and need <= 2 * 1.1416 * s.pitch:
                e = s.fill(amp=s.pitch, n=2)                # never a lone hump: two of the lowest (leg-less) humps instead
            else:
                e = s.fill(add=need)
        except BundleError as err:                          # does not fit at this pitch: take what the site holds, record the rest
            g = s.geometry()
            both = s.side == "both"
            p = s.pitch
            nmax = int((g["length"] + 1e-6) / p) - 1 if both else int((g["length"] + 1e-6) / (2 * p))
            cap = min(g["amp_max"].get(1, s.amp_cap), g["amp_max"].get(-1, s.amp_cap)) if both else g["amp_max"].get(1 if s.side == "R" else -1, s.amp_cap)
            import math
            per = (lambda k: 2 * k * p - (4 - math.pi) * p / 2 * (k + 1)) if both else (lambda k: k * (2 * p - (8 - 2 * math.pi) * p / 2))
            ks = [k for k in range(2 if both else 1, nmax + 1) if per(k) >= need and p <= cap + 1e-9]
            try:                                            # lowest legal humps (height = pitch), just enough of them; else all the site holds
                e = s.fill(amp=p, n=ks[0]) if ks else s.fill(amp=(p if cap < p + 0.105 else int(cap * 1000) / 1000.0), n=nmax)
            except BundleError as err2:
                e = None
                if verbose:
                    print("  slot %s: nothing fits at pitch %.1f (%s)" % (net, p, str(err2).splitlines()[0]))
            missing[net] = round(need - (e["gain"] if e else 0.0), 3)
        if e:
            blocks[net] = e
            if verbose:
                print("  slot %-4s %s side %-4s %d x %.3f mm pitch %.1f -> +%.3f mm (wanted +%.3f)" % (
                    e["net"], e["layer"], e["side"], e["n"], e["amp"], e["pitch"], e["gain"], need))
    if verbose:
        print("  SDCLK %.3f  window %.3f .. %.3f  serpentine goal %.3f" % (clk, clk - 2.5, clk + 2.5, goal))
        for n in sorted(Ls):
            tot = Ls[n] + (blocks[n]["gain"] if n in blocks else 0.0)
            if abs(tot - clk) > 2.5:
                print("  OUT %-9s %.3f (%+.3f to SDCLK)" % (n, tot, tot - clk))
    return {"SWAP": SWAP, "ROUTES": routes, "TUNING": bus.tuning(), "blocks": blocks, "missing": missing, "lengths": Ls, "bus": bus}


def why(r):
    """One Chinese sentence per net; the block sizes are taken from what was actually placed."""
    def blk(net, where):
        e = r["blocks"].get(net)
        if not e:
            return "没有蛇形。"
        miss = r["missing"].get(net)
        t = "%s放 1 块等高蛇形：%d 个弯、高 %.2f mm、腿间距 %.1f，补 %.2f mm" % (where, e["n"], e["amp"], e["pitch"], e["gain"])
        return t + ("（这个间距下放不满，还差 %.2f mm）。" % miss if miss and miss > 0.005 else "。")
    return {
        "FMC_NBL0": "19 根里最远的一根，它的长度决定了时钟要多长：故意走最短的路，L6 沿 MCU 上边的边带向东，再一条 45° 斜线从 SDRAM 底下直插 K9 球旁的过孔，不沿窄条绕；没有蛇形。",
        "FMC_D2": "和 NBL0 并排（L6），从 MCU 上边出来走同一条斜线，到 M8 球旁的过孔，长度自然落在窗口里；没有蛇形。",
        "FMC_NBL1": "走 L4，在 MCU 上边和 NBL0 上下重叠，绕过右上角后贴着 SDRAM 左边的边带向下到 K1 球，把窄条中间的 L4 让给 D10；长度自然在窗口里，没有蛇形。",
        "FMC_D3": "第 3 圈的球，狗骨孔下 L4，向东出 MCU 后和 NBL1 并排沿 SDRAM 左边的边带向下，再沿 K 行横穿到 L8 球旁的过孔（L4 上从 K 行的球正下方走，不是走行间）；没有蛇形。",
        "FMC_SDCLK": "故意绕远：缺 18 mm，窄条里放不下这么大的 0.5 间距蛇形，所以做成 L1 上 U 形线束的最外圈（向北绕到 MCU 上边以北，y=3.70，再折回进 J1 球）；顶上比 D15 多高出 1.96 mm、单独一根，是因为它的球比数据球靠北 3.25 mm，不多绕这一段就比 D14 短 5 mm、出窗口；折回后向下的一段在 SDRAM 规则区的边带里，线宽 0.09；没有蛇形、没有过孔。",
        "FMC_D15": "故意绕远：和 SDCLK、D14、D13 一起在两个芯片之间的窄条里向北绕一个 U 形弯再下来进 L2 球（L1，无过孔），缺的 16 mm 全部由走线补上；折回后向下的一段在 SDRAM 规则区的边带里（线宽 0.09，约 10 mm）；没有蛇形。",
        "FMC_D14": "故意绕远：U 形线束的基准线，从球间通道向东出来后向北绕 U 形弯，再进 M2 球；是这一束里最长的一根（比 SDCLK 长 2.1 mm）；没有蛇形。",
        "FMC_D13": "故意绕远：U 形线束的最内圈，圈子最小，拐弯处每段只有 0.4 mm；进 N2 球；没有蛇形。",
        "FMC_D11": "故意绕远：和 D12、D8、D9 一束从 MCU 下边出来，先贴着 MCU 下边向西走到左下角，折回来再向东直进 SDRAM 的行间通道（N3 球），缺的 11 mm 由走线补上；它是这个 U 形弯的最内圈；没有蛇形。",
        "FMC_D12": "故意绕远：MCU 下边那一束的第 2 根，折回后沿 P 行直进 P1 球；是这一束里最短的一根，向西走多远就是按它定的；没有蛇形。",
        "FMC_D8": "故意绕远：MCU 下边那一束的第 3 根，折回后沿 P、R 两行之间进 R2 球；没有蛇形。",
        "FMC_D9": "故意绕远：MCU 下边那一束的最外圈，折回后沿 R 行直进 R1 球；没有蛇形。",
        "FMC_D10": "第 3 圈的球只能走 L4，单独一根，没有线束可跟：从 MCU 向东出来，在窄条正中向南走一段直线，" + blk("FMC_D10", "这段直线上") + "两侧各留 1.3 mm 是特意给它留的（NBL1、D3 为此改走 SDRAM 的边带）。",
        "FMC_D1": "MCU 右边的球，L1 出到封装边打孔换 L6；不走数据行，改从 SDRAM 底下靠上的空档向东，再沿没有球的中间通道向南到 M7 球；" + blk("FMC_D1", "SDRAM 底下那段向东的直线上") + "弯朝北，上方是空的。",
        "FMC_D0": "同 D1，在它南边 1.2 mm 处并排走（这 1.2 mm 就是给蛇形留的），到 N8 球；" + blk("FMC_D0", "SDRAM 底下") + "弯朝北，夹在 D1 和它自己之间。",
        "FMC_D6": "MCU 下边的球，打孔换 L6，沿 N 行直着向东到 N7 球旁的过孔（L6 上从 N 行的球正下方走，比 L1 那束线靠北 0.4 mm）；" + blk("FMC_D6", "SDRAM 底下") + "弯朝北，因为原来走在它北边的 D0、D1 已经挪到上面去了。",
        "FMC_D7": "同 D6，下面一根，到 P9 球；" + blk("FMC_D7", "SDRAM 底下") + "弯朝南，放在它和 D5 之间 0.8 mm 的行距里。",
        "FMC_D5": "同 D6，再下面一根，到 R8 球；" + blk("FMC_D5", "SDRAM 底下") + "弯朝南，放在它和 D4 之间的行距里。",
        "FMC_D4": "同 D6，最下面一根，到 R9 球；只差 0.6 mm，" + blk("FMC_D4", "SDRAM 底下") + "弯朝北，和 D5 的那块放在同一条行距里、前后错开，不伸出 SDRAM 外形。",
    }
