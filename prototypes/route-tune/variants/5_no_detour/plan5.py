"""PROTOTYPE (issue 21) variant 5_no_detour: the bus of 4_combined without the two L1 U-turns.

Every net takes a path that never turns back on the board surface; what it lacks comes from serpentine blocks
that sit in two zones (numbers in PLAN.md):
  zone A  under the SDRAM's west half: a comb of east-west rows at 1.0 mm pitch.
          L4: D3 (no block), D10, D15, D14, D13   L6: D1, D0 above the comb, D6, D7 inside it.
          All blocks start on one vertical line (X_START) and point north.
  zone B  L1, below the MCU: D11, D12, D8, D9 as four rows, blocks on one start line, pointing north.
  SDCLK   L1, one double-sided block on a north-south run in the middle of the strip (leg pitch 0.5).
Coordinates: local mm, y down (lib/README.md).
"""
import math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib"))
from bundle import Bundle, Bus, BundleError

L1, L4, L6 = "L1", "L4", "L6"
R2 = math.sqrt(2.0)


def dg(k):
    """Gap on a diagonal leg that moves a lane line by k mm in x (or y)."""
    return k / R2 - 1e-7


# Lanes not swapped. Inside lane 1 the bits follow the order in which the tracks arrive (PLAN.md):
# rows of the comb north to south -> L2, M2, M3, N3; surface rows north to south -> N2, P1, R2, R1.
SWAP = {
    "FMC_SDCLK": "CLK", "FMC_NBL0": "DQM0", "FMC_NBL1": "DQM1",
    "FMC_D10": "DQ8", "FMC_D15": "DQ10", "FMC_D14": "DQ9", "FMC_D13": "DQ14",      # L2, M2, M3, N3
    "FMC_D11": "DQ12", "FMC_D12": "DQ11", "FMC_D8": "DQ15", "FMC_D9": "DQ13",      # N2, P1, R2, R1
    "FMC_D3": "DQ7", "FMC_D2": "DQ5", "FMC_D1": "DQ6", "FMC_D0": "DQ3",            # L8, M8, M7, N8
    "FMC_D6": "DQ1", "FMC_D7": "DQ4", "FMC_D5": "DQ0", "FMC_D4": "DQ2",            # N7, P9, R8, R9
}

# ---------------------------------------------------------------- knobs (PLAN.md says where each number comes from)
CLK_MARGIN = 2.175      # SDCLK is brought to (longest net - CLK_MARGIN): 0.325 mm left to the upper window edge
LOW_MARGIN = 0.325      # data blocks bring a net to (lower window edge + LOW_MARGIN)
X_START = 23.05         # zone A: first arc of every block (0.05 mm inside the package outline: the whole block is under the body)
COMB = ["D10", "D15", "D14", "D13"]                 # L4 rows, north to south
ROW0, ROW_PITCH = 18.5, 1.0                         # D3's row is at 17.5: the comb continues it at the same pitch
ROW = {n: round(ROW0 + ROW_PITCH * k, 4) for k, n in enumerate(COMB)}
VIA_X = {n: 26.65 for n in COMB}                    # one column of vias: block end (26.05) + 0.35 straight + 0.2 end piece + 0.05
VIA_Y = {n: round(ROW[n] - 0.2, 4) for n in COMB}                     # the row ends with a 0.2 mm 45-degree piece into the via
X_S = 21.5              # x of D10 (outer lane) on the north-south run of the comb's feed in the strip
B_ROW0 = 19.0           # zone B: y of D11's row; the others follow at B_GAPS (= hump height + 0.30, see PLAN.md)
B_GAPS = [1.13, 0.97, 0.99]   # = hump height of the lower row + 0.30: the free strip between the blocks is the same everywhere
B_XR = 15.55            # zone B: every row starts here (after the 45-degree corner)
B_START = 16.25         # zone B: first arc of every block
B_N = 8                 # zone B: humps per block
B_LEAD = 23.1           # zone B: x where every row has reached its SDRAM row
CLK_X = 20.5            # SDCLK's north-south run in the strip
CLK_N = 6               # humps of the clock block (leg pitch 0.5)
L6_ROWS = [0.9, 0.9, 0.4]   # D6 D7 D5 D4 under the SDRAM: 19.9, 20.8, 21.7, 22.1 (D7 midway between two comb vias, the others 0.4 mm clear)
HUMPS = {"D10": 5, "D15": 5, "D14": 5, "D13": 5, "D1": 5, "D0": 5, "D6": 4, "D7": 4}


def comb_end(net):
    """Row end: 0.2 mm 45-degree piece up into the via, L1 north out of the via and west along the net's channel."""
    x, y = VIA_X[net], VIA_Y[net]
    back = {"D10": [(x, y), (x, 18.15), (round(x - 0.25, 4), 17.9), (25.0, 17.9), "U2"],        # channel K/L -> L2
            "D15": [(x, y), (x, 19.0), (round(x - 0.3, 4), 18.7), (25.0, 18.7), "U2"],          # channel L/M -> M2
            "D14": [(x, y), (x, round(y - 0.15, 4)), (round(25.4 + 0.2, 4), 19.1), "U2"],          # 45-degree diagonal into M3, parallel to D13
            "D13": [(x, y), (x, round(19.9 + (x - 25.4), 4)), "U2"]}[net]                       # diagonal into N3
    return {"pieces": [(L4, [(round(x - 0.2, 4), ROW[net]), (x, y)]), ("via", (x, y)), (L1, back)]}


def make(verbose=True):
    bus = Bus(SWAP)

    # ---------------------------------------------------------------- SDCLK, L1, by hand: one net, not a bundle.
    # North-east out of the ball (0.3 mm north: the run in the strip then starts as far north as it can),
    # east, down the middle of the strip, east into J1.
    yt = 11.675
    bus.keep({"FMC_SDCLK": [(L1, ["U1", (17.225, yt), (CLK_X - 0.3, yt), (CLK_X, yt + 0.3), (CLK_X, 16.4), (CLK_X + 0.3, 16.7), "U2"])]})

    # ---------------------------------------------------------------- L6: NBL0 and D2, the diagonal that sets the window
    top = Bundle("top6", ["NBL0", "D2"], L6, anchor="NBL0",
                 path=[(11.2, 6.65), (19.35, 6.65), (29.8, 17.1), (29.8, 18.0)],
                 pitch=0.33, gaps={1: dg(0.4), 2: 1.2}, span={"NBL0": (0, 1), "D2": (0, 2)})
    bus.add(top,
            start={"NBL0": {"pieces": [(L1, ["U1", (11.2, 6.65)])]},
                   "D2": {"pieces": [(L1, ["U1", (15.925, 7.775), (15.925, 7.23), (16.175, 6.98)])]}},
            end={"NBL0": {"pieces": [(L1, [(29.8, 17.1), "U2"])]}, "D2": {"pieces": [(L1, [(29.0, 18.7), "U2"])]}})

    # ---------------------------------------------------------------- L4: NBL1 over the MCU, with D3 down the SDRAM's
    # west edge band; D3 then runs east on the K row = the top row of the comb (no block)
    n1 = Bundle("top4", ["NBL1"], L4, anchor="NBL1", path=[(9.75, 6.5), (10.1, 6.15), (18.0, 6.15)], pitch=0.3)
    bus.add(n1, start={"NBL1": {"pieces": [(L1, ["U1", (9.75, 6.5)])]}})
    down = Bundle("down4", ["NBL1", "D3"], L4, anchor="D3",
                  path=[(15.925, 9.075), (21.5, 9.075), (22.3, 9.875), (22.3, 16.8), (23.0, 17.5), (28.6, 17.5)],
                  pitch=0.4, gaps={0: 3.575, 1: dg(0.775), 3: dg(0.8), 4: 0.4}, span={"NBL1": (1, 3)})
    bus.add(down, start={"D3": {"pieces": [(L1, ["U1", (15.925, 9.075)])]}},
            end={"NBL1": {"pieces": [(L1, [(23.4, 17.1), "U2"])]}, "D3": {"pieces": [(L1, [(29.0, 17.9), "U2"])]}})

    # ---------------------------------------------------------------- L4: the comb. D10 D15 D14 D13 east out of the MCU,
    # south down the strip as one tight group, east onto four rows 1.0 mm apart under the SDRAM.
    L0 = 1.3                                                # x extent of D10's first 45-degree piece
    comb = Bundle("comb4", COMB, L4, anchor="D10",
                  path=[(18.5, 14.76), (X_S - L0, 14.76), (X_S, 14.76 + L0), (X_S, ROW0 - 0.3), (X_S + 0.3, ROW0), (27.0, ROW0)],
                  pitch=0.325, gaps={0: [0.49, 0.325, 0.325], 3: dg(ROW_PITCH), 4: ROW_PITCH})
    s_comb = {n: comb.slot(n, 4, s0=X_START - (X_S + 0.3), length=0.6 * HUMPS[n] + 1e-6, side="L", pitch=0.3) for n in COMB}
    bus.add(comb,
            start={"D10": {"pieces": [(L1, ["U1", (15.275, 15.575)]), ("via", (15.275, 15.575)), (L4, [(15.275, 15.575), (15.6, 15.575), (16.415, 14.76)])]},
                   "D15": {"pieces": [(L1, ["U1", (18.3, 15.25)])]}, "D14": {"pieces": [(L1, ["U1", (17.225, 15.575), (18.7, 15.575)])]},
                   "D13": {"pieces": [(L1, ["U1", (18.3, 15.9)])]}},
            end={n: comb_end(n) for n in COMB})

    # ---------------------------------------------------------------- L6: D1 D0 from the MCU's east edge to two rows
    # above the comb (same 1.0 mm pitch), then down the ball-free middle strip
    east = Bundle("east6", ["D1", "D0"], L6, anchor="D0",
                  path=[(18.5, 14.275), (19.6, 14.275), (21.825, 16.5), (27.1, 16.5), (27.8, 17.2), (27.8, 19.2), (28.1, 19.5), (29.0, 19.5)],
                  pitch=0.4, gaps={0: 0.65, 1: 0.65, 2: 1.0, 3: dg(0.9), 4: 0.4}, span={"D1": (0, 4)})
    s_d1 = east.slot("D1", 2, s0=X_START - 21.825, length=0.6 * HUMPS["D1"] + 1e-6, side="L", pitch=0.3, amp_cap=1.25)
    s_d0 = east.slot("D0", 2, s0=X_START - 21.825, length=0.6 * HUMPS["D0"] + 1e-6, side="L", pitch=0.3)
    bus.add(east,
            start={"D1": {"pieces": [(L1, ["U1", (17.225, 13.625), (18.5, 13.625)])]}, "D0": {"pieces": [(L1, ["U1", (17.225, 14.275), (18.5, 14.275)])]}},
            end={"D1": {"pieces": [(L1, [(28.2, 18.7), "U2"])]}, "D0": {"pieces": [(L1, [(29.0, 19.5), "U2"])]}})

    # ---------------------------------------------------------------- L6: D6 D7 D5 D4 from the MCU's south edge
    under = Bundle("under6", ["D6", "D7", "D5", "D4"], L6, anchor="D6",
                   path=[(13.975, 17.7), (13.975, 18.4), (15.475, 19.9), (27.0, 19.9)],
                   pitch=0.3, gaps={0: 0.325, 2: L6_ROWS})
    s_d6 = under.slot("D6", 2, s0=X_START - 15.475, length=0.6 * HUMPS["D6"] + 1e-6, side="L", pitch=0.3, amp_cap=0.8)
    s_d7 = under.slot("D7", 2, s0=X_START - 15.475, length=0.6 * HUMPS["D7"] + 1e-6, side="L", pitch=0.3)
    y7, y5, y4 = 19.9 + L6_ROWS[0], 19.9 + L6_ROWS[0] + L6_ROWS[1], 19.9 + sum(L6_ROWS)
    bus.add(under,
            start={"D6": {"pieces": [(L1, ["U1", (13.975, 16.225), (13.975, 17.7)])]}, "D7": {"pieces": [(L1, ["U1", (13.65, 17.3)])]},
                   "D5": {"pieces": [(L1, ["U1", (13.325, 16.225), (13.325, 17.7)])]}, "D4": {"pieces": [(L1, ["U1", (13.0, 17.3)])]}},
            end={"D6": {"pieces": [(L1, [(28.0, 19.9), "U2"])]},
                 "D7": {"pieces": [(L6, [(round(29.0 - (y7 - 20.3), 4), y7), (29.0, 20.3), (29.8, 20.3)]), ("via", (29.8, 20.3)), (L1, [(29.8, 20.3), "U2"])]},
                 "D5": {"pieces": [(L6, [(round(29.0 - 0.4 - (y5 - 21.1), 4), y5), (28.6, 21.1), (29.0, 21.1)]), ("via", (29.0, 21.1)), (L1, [(29.0, 21.1), "U2"])]},
                 "D4": {"pieces": [(L6, [(round(29.8 - (y4 - 21.9), 4), y4), (29.8, 21.9)]), ("via", (29.8, 21.9)), (L1, [(29.8, 21.9), "U2"])]}})

    # ---------------------------------------------------------------- L1, zone B: D11 D12 D8 D9 south out of the MCU,
    # one 45-degree corner, four rows to the east; each row ends with one 45-degree piece onto its SDRAM row
    rows_b = [B_ROW0]
    for g in B_GAPS:
        rows_b.append(round(rows_b[-1] + g, 4))
    south = Bundle("south1", ["D11", "D12", "D8", "D9"], L1, anchor="D11",
                   path=[(15.275, 16.6), (15.275, 15.275 - B_XR + B_ROW0), (B_XR, B_ROW0), (22.0, B_ROW0)],
                   pitch=0.325, gaps={1: [dg(g) for g in B_GAPS], 2: B_GAPS})
    s_b = {n: south.slot(n, 2, s0=B_START - B_XR, length=0.6 * B_N + 1e-6, side="L", pitch=0.3) for n in ("D11", "D12", "D8", "D9")}
    bus.add(south,
            start={"D11": ["U1", (15.275, 16.225)], "D12": "U1", "D8": ["U1", (14.625, 16.225)], "D9": "U1"},
            end={"D11": [(B_LEAD, 20.3), (24.2, 20.3), "U2"], "D12": [(B_LEAD, 20.7), "U2"],
                 "D8": [(B_LEAD, 21.1), (24.2, 21.1), "U2"], "D9": [(B_LEAD, 21.5), "U2"]})

    routes = bus.routes(strict=not os.environ.get("RT5_LOOSE"))
    if verbose:
        print(bus.report())

    # ---------------------------------------------------------------- serpentines, sized from the lengths just computed
    Ls = {n: v["total"] for n, v in bus.lengths().items()}
    longest = max(Ls.values())
    t_clk = round(longest - CLK_MARGIN, 3)
    goal = round(t_clk - 2.5 + LOW_MARGIN, 3)
    slots = dict({"FMC_" + n: s for n, s in s_comb.items()}, **{"FMC_" + n: s for n, s in s_b.items()})
    slots.update({"FMC_D1": s_d1, "FMC_D0": s_d0, "FMC_D6": s_d6, "FMC_D7": s_d7})
    blocks, notes = {}, []
    for net, s in slots.items():
        need = goal - Ls[net]
        n = B_N if s.b.name == "south1" else HUMPS[net[4:]]
        if need <= 0:
            continue
        low = n * (2 * (0.3 + 0.105) - 0.858 * 0.3)         # the lowest block with legs at this hump count
        try:
            e = s.fill(amp=0.405, n=n) if need < low else s.fill(add=need, n=n)
        except BundleError as err:
            notes.append("%s: %s" % (net, str(err).splitlines()[0]))
            continue
        blocks[net] = e
        if verbose:
            print("  slot %-4s %s side %-2s %d x %.3f -> +%.3f (wanted +%.3f)  free %s" % (
                e["net"], e["layer"], e["side"], e["n"], e["amp"], e["gain"], need, {k: round(v, 3) for k, v in s.geometry()["amp_max"].items()}))
    tuning = bus.tuning()
    # the clock: one double-sided chain on the north-south run, heights solved by the builder for exactly t_clk
    tuning.append({"net": "SDCLK", "at": (CLK_X, 14.2), "layer": "L1", "side": "both", "first": "E", "pitch": 0.5, "n": CLK_N, "to": t_clk})
    if verbose:
        print("  longest %.3f  SDCLK natural %.3f -> %.3f (+%.3f)  window %.3f .. %.3f  data goal %.3f" % (
            longest, Ls["FMC_SDCLK"], t_clk, t_clk - Ls["FMC_SDCLK"], t_clk - 2.5, t_clk + 2.5, goal))
        for n in sorted(Ls):
            tot = t_clk if n == "FMC_SDCLK" else Ls[n] + (blocks[n]["gain"] if n in blocks else 0.0)
            flag = "OUT" if abs(tot - t_clk) > 2.5 else ("thin" if 2.5 - abs(tot - t_clk) < 0.3 else "")
            print("    %-9s natural %7.3f  total %7.3f  %+6.3f  %s" % (n, Ls[n], tot, tot - t_clk, flag))
        for t in notes:
            print("  NOT PLACED " + t)
    return {"SWAP": SWAP, "ROUTES": routes, "TUNING": tuning, "blocks": blocks, "lengths": Ls, "t_clk": t_clk, "goal": goal, "notes": notes, "bus": bus}


def why(r):
    """One Chinese sentence (or two) per net; block sizes are taken from what was actually placed."""
    def blk(net):
        e = r["blocks"]["FMC_" + net]
        return "%d 个等高的弯、摆幅 %.2f、腿间距 %.1f，补 %.2f mm" % (e["n"], e["amp"], e["pitch"], e["gain"])
    clk_add = r["t_clk"] - r["lengths"]["FMC_SDCLK"]
    back = {"D10": (2.05, "K、L 两行之间的通道进 L2"), "D15": (2.05, "L、M 两行之间的通道进 M2"),
            "D14": (1.25, "一条 45° 斜线进 M3（和 D13 的斜线平行）"), "D13": (1.25, "一条 45° 斜线进 N3")}
    yb = [B_ROW0]
    for g in B_GAPS:
        yb.append(round(yb[-1] + g, 4))
    low = r["t_clk"] - 2.5                                   # lower window edge
    nat = lambda net: r["lengths"]["FMC_" + net]
    tot = lambda net: nat(net) + (r["blocks"]["FMC_" + net]["gain"] if "FMC_" + net in r["blocks"] else 0.0)
    data_max = max(e["amp"] for e in r["blocks"].values())
    y7 = 19.9 + L6_ROWS[0]
    comb = lambda net, row, extra="": (
        "梳子第 %s 行（L4，y=%.1f）：从 MCU 右边出，在窄条里和另外三根并成一束向南，再向东进 SDRAM 底下自己的一行；行上一块蛇形：%s，朝北，从封装外形线里面 0.05 mm 起。"
        "行尾的过孔在封装中间没有球的那一条里（x=%.2f），比它的球多往东走了 %.2f mm，再从表层沿%s：这一来一回是为了给蛇形留出直线，算绕远，没有藏。%s" % (
            row, ROW[net], blk(net), VIA_X[net], back[net][0], back[net][1], extra))
    return {
        "FMC_NBL0": "19 根里最远的一根，窗口上沿由它定：从球斜着出到 MCU 上边打孔，L6 沿 MCU 上边向东，再一条 45° 斜线从 SDRAM 底下直插 K9 旁的过孔。比 4_combined 短 0.97 mm（出球改成斜线），所以整个窗口下移，其余的线都少补一截。没有蛇形。",
        "FMC_D2": "和 NBL0 并排（L6），走同一条斜线到 M8 旁的过孔，长度自然在窗口里（离下沿 %.2f mm）。没有蛇形。" % (nat("D2") - low),
        "FMC_NBL1": "同 4_combined：L4 沿 MCU 上边向东，绕过右上角后贴着 SDRAM 左边的边带向下到 K1。长度自然在窗口里，没有蛇形。",
        "FMC_D3": "同 4_combined：第 3 圈的球，狗骨孔下 L4，和 NBL1 并排沿 SDRAM 左边的边带向下，再沿 K 行向东到 L8 旁的过孔。它这一行（y=17.5）正好是下面那把“梳子”的第 0 行，行距同为 1.0 mm。没有蛇形。",
        "FMC_SDCLK": "表层直走，没有过孔，没有绕远：向东出 MCU，在窄条正中向南走 4.4 mm，再向东直进 J1。缺的 %.1f mm 全靠这段南北直线上的一块双侧蛇形：%d 个等高的弯、单边摆幅约 1.3（整块宽 2.6 mm，就是窄条能用的宽度）、腿间距 0.5、线宽 0.1016。"
                     "单边摆幅是最高的数据弯（%.2f）的 %.1f 倍，整块宽是它的 %.1f 倍，是这块板上最显眼的一块：时钟缺得最多、腿间距又不能密，要占的面积是定的（约 9 mm²），窄条里只能长成这样。" % (
                         clk_add, CLK_N, data_max, 1.295 / data_max, 2.59 / data_max),
        "FMC_D10": comb("D10", "1", "第 3 圈的球，用狗骨孔下 L4；出 MCU 前先向北让了 0.8 mm，绕开 D15、D14 的过孔。"),
        "FMC_D15": comb("D15", "2"),
        "FMC_D14": comb("D14", "3", "这一行比它的球靠南 1.4 mm，表层回程的斜线就是向北走回来的那一段。"),
        "FMC_D13": comb("D13", "4", "这一行比它的球靠南 1.6 mm，表层回程的斜线就是向北走回来的那一段。"),
        "FMC_D11": "表层直走，没有过孔：从 MCU 下边向南出来，拐一个 45° 弯向东，是 MCU 下方四行里最上面一行（y=%.2f），行上一块蛇形：%s，朝北；过了蛇形一条 45° 斜线落到 N、P 两行之间的通道进 N2。原来的 U 形弯没有了。四块蛇形同一条起始线、同一条结束线，块与块之间空着的宽度相同（0.30 mm）。" % (yb[0], blk("D11")),
        "FMC_D12": "同 D11，第 2 行（y=%.2f），%s，朝北；斜下到 P 行直进 P1。四根里它缺得最多，所以它的弯最高，它上面的行距（%.2f mm）就是按这个高度留的。" % (yb[1], blk("D12"), B_GAPS[0]),
        "FMC_D8": "同 D11，第 3 行（y=%.2f，正对 P、R 两行之间的通道，不用再拐），%s，朝北；直着进 R2。" % (yb[2], blk("D8")),
        "FMC_D9": "同 D11，最下面一行（y=%.2f），%s，朝北；过了蛇形斜上 %.2f mm 到 R 行进 R1。这一行比它的球靠南 %.2f mm，是四行蛇形排下来的结果。" % (yb[3], blk("D9"), yb[3] - 21.5, yb[3] - 21.5),
        "FMC_D1": "同 4_combined：MCU 右边的球，打孔换 L6，斜穿窄条到 SDRAM 底下靠上的一行（y=15.5），再沿没有球的中间通道向南到 M7 旁的过孔。行上一块蛇形：%s，朝北，和下面各块同一条起始线。" % blk("D1"),
        "FMC_D0": "同 D1，在它南边 1.0 mm 的一行（y=16.5），到 N8 旁的过孔。%s，朝北。" % blk("D0"),
        "FMC_D6": "同 4_combined：MCU 下边的球，打孔换 L6，沿 N 行向东到 N7 旁的过孔。%s，朝北，同一条起始线。" % blk("D6"),
        "FMC_D7": "同 D6，下面一行（y=%.1f，在梳子上下两个过孔的正中间），到 P9 旁的过孔。自然长度只比窗口下沿短 %.2f mm；不放 2 个弯的小疙瘩，放了和 D6 并排的一块：%s，比需要的多 %.1f mm，仍在窗口里（比时钟短 %.2f）。" % (
                      y7, low - nat("D7"), blk("D7"), tot("D7") - r["goal"], r["t_clk"] - tot("D7")),
        "FMC_D5": "同 D6，再下面一行（y=21.7），到 R8 旁的过孔。自然长度在窗口里（离下沿 %.2f mm），没有蛇形。" % (nat("D5") - low),
        "FMC_D4": "同 D6，最下面一行（y=22.1），到 R9 旁的过孔。自然长度在窗口里，没有蛇形。",
    }
