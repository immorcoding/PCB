"""PROTOTYPE (issue 21) variant 2_detour_first: lengths by ROUTING first, serpentines last and few.

Plan (see PLAN.md, written before routing):
  * the two byte lanes are swapped on the SDRAM side: MCU D8-15 (south-east corner, nearest the SDRAM) go to the
    FAR columns, D0-7 to the near columns; NBL1 (outer ball A3) -> DQM0 (K9), NBL0 -> DQM1 (K1)
  * the longest net (NBL1 -> K9) is made as short as it can be: one 45-degree line under the SDRAM body (on L4, see below)
  * W  (L1, 7 lanes: SDCLK D1 D0 | D6 D7 D5 D4): south along the MCU, round the SDRAM's south-west corner,
       into the near columns from below and from the west flank (nested U: outer lanes loop wide and enter low)
  * E  (L6, 8 lanes: D15 D14 D13 | D10 D11 D12 D8 D9, D10 on L4 in its lane): U round the SDRAM's bottom edge,
       north up the ball-free middle strip, east along the rows to vias beside the far balls
  * T  (NBL1 on L4, NBL0 and D2 on L6: three evenly spaced lanes round the MCU's top-right corner; D3 alone on L4)
The loop depth is what sets the length; no via in the corridor, 2 vias per net at most.
Format: lib/README.md. Coordinates are local mm, y down.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib"))
from bundle import Bundle, Bus

DESCRIPTION = "先绕后补：两个字节通道对调，三束线按要补的长度排内外圈、从 SDRAM 下边绕进去，长度基本靠走线凑齐，蛇形只补剩下的。"

L1, L4, L6 = "L1", "L4", "L6"
P = 0.2286                                  # lane pitch outside the rule areas: 0.1016 track + 0.127 clearance
PITCH = {"default": 0.5}                    # every serpentine at 0.5 mm leg pitch
BOARD = (40, 30)
VIEWS = [("loop", 12.0, 15.0, 31.5, 29.0, 55), ("wflank", 18.0, 16.0, 26.5, 28.5, 110), ("emid", 25.0, 17.0, 31.0, 26.0, 130),
         ("top", 9.0, 4.5, 31.0, 18.5, 55)]

SWAP = {
    "FMC_SDCLK": "CLK", "FMC_NBL0": "DQM1", "FMC_NBL1": "DQM0",
    # MCU lane 0 -> SDRAM near columns (DQ8-15)
    "FMC_D1": "DQ8", "FMC_D0": "DQ10", "FMC_D2": "DQ9", "FMC_D6": "DQ12", "FMC_D7": "DQ11", "FMC_D5": "DQ15", "FMC_D4": "DQ14", "FMC_D3": "DQ13",
    # MCU lane 1 -> SDRAM far columns (DQ0-7)
    "FMC_D15": "DQ7", "FMC_D14": "DQ5", "FMC_D13": "DQ6", "FMC_D10": "DQ3", "FMC_D11": "DQ1", "FMC_D12": "DQ4", "FMC_D8": "DQ0", "FMC_D9": "DQ2",
}

# ---------------------------------------------------------------- the knobs that set the lengths
YB = 25.65           # W: y of SDCLK's lane on the bottom run (the innermost lane); the other six lie south of it
XC = 20.2            # W: x of SDCLK's lane on the run down the corridor; the other six lie west of it
YE = 23.95           # E: y of D15's lane on the bottom run (just outside the SDRAM's rule area)
CS = 3.2             # E: chamfer of the corner below the MCU (D11's lane): the long diagonal trims the five outer lanes
X2 = 20.3            # T: x of D2's run down the corridor
Y3 = 23.2            # D3: y of its run below the SDRAM's corner

bus = Bus(SWAP)

# ---- D3 (L4, alone): dog-bone via, east out of the MCU, down the whole corridor, round to the via south of R1
bus.keep({"FMC_D3": [(L1, ["U1", (15.925, 9.075)]), ("via", (15.925, 9.075)),
                     (L4, [(15.925, 9.075), (20.2, 9.075), (20.8, 9.675), (20.8, Y3 - 0.6), (21.4, Y3), (23.3, Y3), (23.8, Y3 - 0.5), (23.8, 22.3)]),
                     ("via", (23.8, 22.3)), (L1, [(23.8, 22.3), "U2"])]})

# ================================================================ W: L1, seven lanes round the SDRAM's south-west corner
# w_south: D6 D7 D5 D4 leave the MCU southwards, run east just below its rule area and turn south beside the
# corridor, where they become the four outer lanes of w_loop (same lines: they simply run on).
GG = 0.9142                                                 # D6 | D7: flank group and column group stay this far apart from the bottom run on
X7 = round(XC - 4 * P, 4)                                   # D7 is the anchor lane
YS7 = 19.15
CA = 0.6                                                    # chamfer of D7's two corners below the MCU
south = Bundle("w_south", ["D6", "D7", "D5", "D4"], L1, anchor="D7", pitch=P, gaps={0: 0.325},
               path=[(13.65, 17.0), (13.65, round(YS7 - CA, 4)), (round(13.65 + CA, 4), YS7), (round(X7 - CA, 4), YS7), (X7, round(YS7 + CA, 4)), (X7, 22.0)])
bus.add(south, start={"D6": ["U1", (13.975, 16.225)], "D7": "U1", "D5": ["U1", (13.325, 16.225)], "D4": "U1"})
Y7 = round(YB + 3 * P + GG, 4)
C1, C2 = 1.2, 1.2
wloop = Bundle("w_loop", ["SDCLK", "D1", "D0", "D6", "D7", "D5", "D4"], L1, anchor="D7", pitch=P,
               gaps={1: [P, P, P, 0.7, P, P], 2: [P, P, P, GG, P, P], 3: [P, P, P, 1.2, 0.35, 0.35],     # diagonal gaps chosen so that every corner nests by the same step
                     4: [P, P, P, GG, 0.4, 0.4]},           # flank lanes x 22.6 .. 23.2858, then the ball columns 24.2 / 24.6 / 25.0
               path=[(X7, 21.0), (X7, round(Y7 - C1, 4)), (round(X7 + C1, 4), Y7), (round(24.2 - C2, 4), Y7), (24.2, round(Y7 - C2, 4)), (24.2, 21.0)])
bus.add(wloop, start={"SDCLK": ["U1", (17.225, 12.325), (19.45, 12.325)],
                      "D1": ["U1", (17.225, 13.625), (19.45, 13.625)],
                      "D0": ["U1", (17.225, 14.275), (19.45, 14.275)]},
        end={"SDCLK": [(23.3, 17.2), "U2"],
             "D1": [(23.3, 17.9), (24.2, 17.9), "U2"],
             "D0": [(23.5, 18.7), (24.2, 18.7), "U2"],
             "D6": [(23.6, 20.3), (24.2, 20.3), "U2"],
             "D7": [(24.2, 21.1), "U2"],
             "D5": "U2",
             "D4": [(25.0, 20.3), "U2"]})

# ================================================================ E: L6 (D10 on L4), eight lanes round the SDRAM's bottom edge
# e_east: the three vias in the MCU's east edge band (staggered 0.4 x 0.325) leave eastwards on L6 at the ball pitch,
# turn south beside the corridor (nested corner) and become the three inner lanes of e_loop.
east = Bundle("e_east", ["D15", "D14", "D13"], L6, anchor="D15", pitch=P, gaps={0: 0.325},
              path=[(18.6, 15.25), (19.15, 15.25), (20.05, 16.15), (20.05, round(YE - 0.8, 4)), (20.85, YE)])   # corners 0.15 mm outside the rule area: the width changes at the bend
bus.add(east, start={"D15": {"pieces": [(L1, ["U1", (18.5, 15.25)])]}, "D13": {"pieces": [(L1, ["U1", (18.5, 15.9)])]},
                     "D14": {"pieces": [(L1, ["U1", (17.225, 15.575), (18.1, 15.575)])]}})
Y11 = round(YE + 4 * P, 4)
esouth = Bundle("e_south", ["D10", "D11", "D12", "D8", "D9"], L6, anchor="D11", pitch=P, gaps={0: 0.325},
                path=[(15.275, 17.6), (15.275, round(Y11 - CS, 4)), (round(15.275 + CS, 4), Y11), (19.5, Y11)])
bus.add(esouth, start={"D10": {"pieces": [(L1, ["U1", (15.275, 15.575)])]},
                       "D11": {"pieces": [(L1, ["U1", (15.275, 16.225), (15.275, 17.3)])]},
                       "D12": {"pieces": [(L1, ["U1", (14.95, 17.7)])]},
                       "D8": {"pieces": [(L1, ["U1", (14.625, 16.225), (14.625, 17.3)])]},
                       "D9": {"pieces": [(L1, ["U1", (14.3, 17.7)])]}})
Y9 = round(YE + 7 * P, 4)
CE = round(Y9 - 21.9, 4)                                    # D9's diagonal ends exactly on its row: it turns east without a run north
E_NETS = ["D15", "D14", "D13", "D10", "D11", "D12", "D8", "D9"]
eloop = Bundle("e_loop", E_NETS, L6, anchor="D9", pitch=P, span={"D9": (0, 1), "D8": (0, 1), "D12": (0, 1)},
               path=[(21.0, Y9), (round(27.6 - CE, 4), Y9), (27.6, 21.9), (27.6, 20.0)])
E_END = {"D9": (21.9, (29.8, 21.9)), "D8": (21.1, (29.0, 21.1)), "D12": (20.3, (29.8, 20.3)), "D11": (19.9, (28.0, 19.9)),
         "D10": (19.5, (29.0, 19.5)), "D13": (19.1, (28.0, 19.1)), "D14": (18.7, (29.0, 18.7)), "D15": (17.9, (29.0, 17.9))}
e_end = {}
for k, n in enumerate(E_NETS):
    row, via = E_END[n]
    j = 7 - k                                               # lanes counted from the outer one (D9)
    if n in ("D9", "D8", "D12"):                            # the three outer lanes leave the diagonal straight onto their row
        x = round(27.6 + 21.9 - j * 0.3233 - row, 4)        # where the lane's diagonal (x + y = 49.5 - j * 0.3233) meets the row
    else:                                                   # the five inner lanes run north up the ball-free middle strip first
        x = round(27.6 - j * P + (0.7 if n == "D11" else 0.3), 4)   # D11: a longer stub, its run north is the shortest of the five
    e_end[n] = {"pieces": [(L6, [(x, row), via]), ("via", via), (L1, [via, "U2"])]}
bus.add(eloop, end=e_end)

# ================================================================ T: L6 round the MCU's top-right corner
top = Bundle("t_nbl", ["NBL1", "NBL0"], L6, anchor="NBL1", pitch=P, gaps={2: [0.4]}, span={"NBL1": (0, 1)},
             path=[(11.5, 5.29), (17.99, 5.29), (24.6, 11.9), (24.6, 16.5)])       # NBL1's diagonal is the line x - y = 12.7 through its via
bus.add(top, start={"NBL1": {"pieces": [(L1, ["U1", (9.75, 6.5)])]}, "NBL0": {"pieces": [(L1, ["U1", (10.4, 6.5)])]}},
        end={"NBL1": {"pieces": [("via", (29.8, 17.1)), (L1, [(29.8, 17.1), "U2"])]},
             "NBL0": {"pieces": [("via", (24.2, 17.1)), (L1, [(24.2, 17.1), "U2"])]}})
YT2 = round(5.29 + 2 * P, 4)
# D2's diagonal is the third lane of the NBL pair's diagonal (x - y = 12.7, 12.3767, 12.0534: one lane pitch apart,
# 0.3233 in x), so the three run round the corner as one evenly spaced bundle before D2 turns south.
KD2 = round(12.7 - 2 * 0.3233, 4)
XD2 = round(YT2 + KD2, 4)                                   # where D2's top run meets that diagonal
d2 = Bundle("t_d2", ["D2"], L6, anchor="D2", pitch=P,
            path=[(16.5, YT2), (XD2, YT2), (X2, round(X2 - KD2, 4)), (X2, 18.1), (round(X2 + 0.6, 4), 18.7), (24.0, 18.7)])
bus.add(d2, start={"D2": {"pieces": [(L1, ["U1", (15.925, 7.775), (15.925, 6.5)])]}},
        end={"D2": {"pieces": [("via", (25.0, 18.7)), (L1, [(25.0, 18.7), "U2"])]}})

ROUTES = bus.routes()
# D10 leaves its dog-bone via on L4 (inner-ring ball): its lane of the E bundle is drawn on L4 instead of L6.
# bundle.py has one layer per bundle, so the lane is generated with the others and re-layered here.
# NBL1 (the longest net) is put on L4 as well: two L1-L4 vias are 0.514 mm shorter than two L1-L6 vias.
for _n in ("FMC_D10", "FMC_NBL1"):
    ROUTES[_n] = [((L4 if pc[0] == L6 else pc[0]),) + tuple(pc[1:]) for pc in ROUTES[_n]]
print(bus.report())
print("  (D10 and NBL1 are on L4: their two vias are L1-L4, 0.514 mm shorter in total than the table above says)")

TUNING = bus.tuning()

# Serpentines: none. Every net is inside the window by routing alone, so no slot is filled (TUNING is empty).
# The convention would be: one block per site, equal height inside a block, pitch 0.5; exceptions to equal height: none.

WHY = {
    "FMC_SDCLK": "故意绕远：直连只有 8.8 mm，要做到约 27.4 mm（最长的 NBL1 减 2.5）。它是 L1 上 W 束最里面一根：出 MCU 后沿窄条向南，在 SDRAM 左下角外面兜一个 U 形，再贴着 SDRAM 左侧向北一直走到 J1；兜的深度（底边 y=25.65）就是按它的长度定的，没有蛇形。",
    "FMC_D1": "故意绕远：W 束第 2 根，跟着 SDCLK 兜同一个 U 形，在 K、L 两行之间的通道（y=17.9）拐进去到 L2；比 SDCLK 少走的那一段正好让它落在窗口中间偏下。",
    "FMC_D0": "故意绕远：W 束第 3 根，在 L、M 两行之间的通道（y=18.7）进去到 M2；原计划走 y=19.5 那条通道，算出来短 0.8 mm，改到高一行的通道补上。",
    "FMC_D6": "故意绕远：从 MCU 下边出来先贴着 MCU 向东，再和上面三根并成一束向南，U 形兜回来后在 N、P 两行之间的通道进 N2；它是 19 根里最短的一根（比 SDCLK 短 2.07），余量 0.43 mm。",
    "FMC_D7": "故意绕远：W 束外面三根里最靠里的一根，从 SDRAM 下边沿第 1、2 列之间直着向北进 P1；它和 D6 之间在底边留了 0.91 mm（和进球时两组线的间隔一样），等于让外面三根多兜 1.4 mm，否则它会短出窗口。",
    "FMC_D5": "故意绕远：W 束外数第 2 根，从 SDRAM 下边直着向北进 R2。",
    "FMC_D4": "故意绕远：W 束最外一根，兜得最深（底边 y=27.71），从第 2、3 列之间向北进 N3；是 L1 上最长的一根（比 SDCLK 长 1.20）。",
    "FMC_D3": "第 3 圈的球，狗骨孔下 L4；故意不在近处上来，而是沿窄条一路向南，到 SDRAM 左下角外面拐回来，在 R1 球正下方打孔：这一趟正好 25.95 mm，不用蛇形。L4 的窄条里只有它，留着整条直线可以补线，但没用上。",
    "FMC_D2": "球在 MCU 上边，换 L6 后先斜着上到 y=5.75，和两根 NBL 并排向东，再作为第三根、隔一个线距跟着它们的斜线绕过 MCU 右上角，到 x=20.3 离开斜线沿窄条向南，在 L、M 两行之间向东到 M3 旁的过孔；过孔后先上去再下来的这一小段比贴着 MCU 直走多约 0.6 mm，再加上选了远一个球的 M3，才离窗口下限有 1.2 mm 余量。",
    "FMC_NBL0": "球在 MCU 左上角，L6 沿 MCU 上边向东，和 NBL1 并排斜穿窄条，到 x=24.2 后在 SDRAM 封装下面向南到 K1 旁的过孔；自然长度 26.9 mm，就在窗口中间。",
    "FMC_NBL1": "19 根里躲不掉的最长一根（A3 到最远的 K9，直连 24.6 mm），它定了窗口上限，所以只求短：在 MCU 边上打孔后走 L4（两个过孔比走 L6 短 0.51 mm），一条 45° 斜线从 SDRAM 封装下面直接穿到 K9 旁的过孔，29.75 mm（0_base 里同样去 K9 的那根是 34.9 mm）。",
    "FMC_D15": "两个字节通道对调后去 SDRAM 远侧。E 束最里面一根：在 MCU 右边打孔换 L6，沿窄条向南，从 SDRAM 下边绕进封装中间没有球的那一条，向北走到最高的一行（y=17.9）再向东到 L8 旁的过孔。",
    "FMC_D14": "E 束第 2 根，走法同 D15，在 y=18.7 向东到 M8 旁的过孔；它的过孔和 D15、D13 的错开 0.4 mm 排在 MCU 右边的边带里。",
    "FMC_D13": "E 束第 3 根，在 y=19.1 向东到 M7 旁的过孔，向东那段只有 1.2 mm，所以是 E 束里最短的（比 SDCLK 短 2.04，离窗口下限 0.46）；整束的底边定在 y=23.95 而不是紧贴规则区，就是为了给它留这点余量。",
    "FMC_D10": "第 3 圈的球，狗骨孔下 L4；在 E 束里占第 4 个位置（L6 的线束在这里空出一根线的位置，平面上看 8 根等距），在 y=19.5 向东到 N8 旁的过孔。这一根是 bundle.py 按 L6 生成后改到 L4 的。",
    "FMC_D11": "E 束第 5 根，MCU 下边打孔换 L6，一段长斜线到底边，绕进 SDRAM 中间后在 y=19.9 向东到 N7 旁的过孔；进行的那个 45° 小斜段比别的长（0.7 mm），免得拐角挤在一起。",
    "FMC_D12": "E 束外数第 3 根：底边之后的斜线直接接到 y=20.3 这一行向东，不再向北走，到 P9 旁的过孔。",
    "FMC_D8": "E 束外数第 2 根：斜线直接接到 y=21.1 这一行，到 R8 旁的过孔。",
    "FMC_D9": "E 束最外一根：兜得最远但进得最低，斜线直接接到 y=21.9 这一行，到 R9 旁的过孔；外面五根在 MCU 下方用一段长斜线（倒角 3.2 mm）拐弯，比直角拐弯少走约 1.9 mm，不然会偏长。",
}
