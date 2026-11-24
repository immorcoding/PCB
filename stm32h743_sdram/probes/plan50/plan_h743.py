"""The 50-mil byte-lane plan of the H743 SDRAM bus (2026-11-24, user: inside each byte lane longest - shortest <= 1.27 mm,
SPEC 9): hand waypoints of the nets that change, drawn on the board as it was before the redraw (commit 6eac9ae).
Plan data for Tools.KiCadDesignTools.planning.plan (its module text has the API); routes_sdram.py draws this plan.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.planning.plan stm32h743_sdram stm32h743_sdram\\probes\\plan50\\plan_h743.py <board at 6eac9ae> --out <dir>

Local mm. 'L' / 'R' of a block = hump side seen along the direction of travel (travelling east: L = north). Zone tags
(Z3, ZN1, Z0a, ...) name the tuning zones of the paper plan. Was out/plan50/plan.py + lanes12.py (git-ignored).
"""
import csv, os


def plan(P):
    pre, tail, tuned, fixed, Net, N = P.pre, P.tail, P.tuned, P.fixed, P.Net, P.N

    # =========================================================================== lane 3 (byte 3, north-west)
    # T3 = FMC_D24 (kept on its present way, two chamfers enlarged)
    T3 = 28.35
    A3T = T3 - 0.25

    def d24():
        n = pre("FMC_D24", (44.225, 35.375))
        n.to((49.4, 35.375), (50.2, 36.175), (50.2, 42.15), (51.4, 43.35))
        return tail(n, (54.65, 43.35))
    fixed("FMC_D24", d24())
    fixed("FMC_NBL3", tail(pre("FMC_NBL3", (37.45, 30.3)).to((46.207, 30.3), (47.257, 31.35), (51.02, 31.35), (51.25, 31.58)), (51.25, 34.6)))

    P.pad_net.update({("U301", "D3"): "FMC_D31", ("U301", "D2"): "FMC_D28"})
    X0 = 48.55                  # first arc of every block of the L4 strip zone Z3

    def d27(a):
        n = pre("FMC_D27", (43.9, 33.75))
        n.to((46.45, 33.75), (46.85, 33.35), (46.85, 30.8), (47.25, 30.4))
        n.block((52.25, 30.4), "R", 5, a, start=X0 - 47.25, tag="Z3")
        n.to((52.85, 31.0), (54.2, 31.0)).hop("L1", (54.6, 31.4))
        return n
    tuned("FMC_D27", d27, A3T, 5)

    def d25(a):
        n = pre("FMC_D25", (44.55, 34.4))
        n.to((46.7, 34.4), (47.1, 34.0), (47.1, 32.4), (47.5, 32.0))
        n.block((52.25, 32.0), "R", 5, a, start=X0 - 47.5, tag="Z3")
        n.to((52.85, 32.6), (54.2, 32.6)).hop("L1", (54.6, 33.0))
        return n
    tuned("FMC_D25", d25, A3T, 5)

    def d28(a):
        n = Net("FMC_D28").track("L1", [(36.75, 33.75), (37.075, 34.075)])
        n.hop("L4", (37.4, 34.4), (37.4, 34.75), (37.7, 35.05), (46.6, 35.05), (47.85, 33.8))
        n.block((52.25, 33.8), "R", 5, a, start=X0 - 47.85, tag="Z3")
        n.to((52.65, 33.4), (54.2, 33.4)).hop("L1", (54.6, 33.8))
        return n
    tuned("FMC_D28", d28, A3T, 5)

    def d31(a):
        n = Net("FMC_D31").track("L1", [(36.75, 35.05), (37.075, 35.375)])
        n.hop("L4", (37.4, 35.7), (46.3, 35.7), (47.0, 35.0))
        n.block((51.75, 35.0), "R", 4, a, start=X0 - 47.0, tag="Z3")
        n.to((52.95, 33.8), (55.4, 33.8), (55.8, 33.4)).hop("L1", (55.4, 33.8))
        return n
    tuned("FMC_D31", d31, A3T, 4)

    def d26(a):
        n = pre("FMC_D26", (44.55, 33.1))
        n.to((46.2, 33.1), (46.6, 32.7), (46.6, 29.9), (47.0, 29.5))
        n.block((55.85, 29.5), "R", 3, a, start=X0 - 47.0, tag="Z3")
        n.to((56.25, 29.9), (56.25, 33.7), (55.75, 34.2), (54.2, 34.2)).hop("L1", (54.6, 34.6))
        return n
    tuned("FMC_D26", d26, A3T, 3)

    def cke0():
        n = Net("FMC_SDCKE0").track("L1", [(37.4, 35.7), (37.725, 36.025)])
        n.hop("L4", (38.05, 36.35), (46.3, 36.35), (46.65, 36.0), (50.2, 36.0), (52.0, 37.8))
        return tail(n, (53.8, 37.8))
    fixed("FMC_SDCKE0", cke0())
    fixed("FMC_A3", pre("FMC_A3", (55.7, 29.3)).to((55.75, 29.3), (56.15, 29.7), (56.15, 34.65), (55.4, 35.4)))
    fixed("FMC_A6", pre("FMC_A6", (55.95, 29.05)).to((56.0, 29.05), (56.4, 29.45), (56.4, 35.2), (55.4, 36.2)))

    # L1 river zone ZN1 (x 46 - 50.5, between the river and FMC_D3's row): the data lanes step south, D29 / D30 / D2 tuned
    def d29(a):
        n = pre("FMC_D29", (34.35, 29.8))
        n.to((46.415, 29.8), (46.785, 30.17))
        n.block((51.52, 30.17), "L", 2, a, start=0.75, tag="ZN1")
        n.to((52.75, 31.4), (53.8, 31.4))
        return n
    tuned("FMC_D29", d29, A3T, 2)

    def d30(a):
        n = pre("FMC_D30", (37.05, 30.05))
        n.to((46.31, 30.05), (46.73, 30.47))
        n.block((51.32, 30.47), "R", 3, a, start=0.8, tag="ZN1")
        n.to((53.05, 32.2), (53.8, 32.2))
        return n
    tuned("FMC_D30", d30, A3T, 3)

    # =========================================================================== lane 0 (byte 1, south-west)
    fixed("FMC_NBL0", tail(pre("FMC_NBL0", (37.85, 30.55)).to((46.104, 30.55), (47.154, 31.6), (50.77, 31.6), (51.0, 31.83)), (51.0, 38.0)))
    T0 = round(P.length(N["FMC_NBL0"]), 2)
    A0T = T0 - 0.3

    def d2(a):
        n = pre("FMC_D2", (42.575, 30.8))
        n.to((46.0, 30.8), (47.1, 31.9))
        n.block((50.57, 31.9), "R", 3, a, start=0.7, tag="ZN1")
        n.to((50.75, 32.08))
        return tail(n, (50.75, 38.6))
    tuned("FMC_D2", d2, A0T, 3)

    def d3(a):
        n = pre("FMC_D3", (45.525, 32.775))
        n.hop("L1", (46.3, 32.775))
        n.block((50.15, 32.775), "R", 4, a, start=0.7, tag="ZN1")
        return tail(n, (50.45, 33.075))
    tuned("FMC_D3", d3, A0T, 4)

    # L3 strip zone Z0a (south half of the strip): D1 / D0 below A12 (A12 and BA1 keep their present blocks), six humps each from x 47.6
    def d1(a):
        n = pre("FMC_D1", (45.3, 39.6))
        n.to((46.42, 40.72))
        n.block((51.9, 40.72), "R", 6, a, start=47.6 - 46.42, tag="Z0a")
        n.to((52.82, 39.8))
        return tail(n, (55.8, 39.8))
    tuned("FMC_D1", d1, A0T, 6)

    def d0(a):
        n = pre("FMC_D0", (44.55, 40.25))
        n.to((45.1, 40.25), (46.9, 42.05))
        n.block((51.3, 42.05), "R", 5, a, start=0.7, tag="Z0a")
        n.to((52.75, 40.6))
        return tail(n, (54.2, 40.6))
    tuned("FMC_D0", d0, A0T, 5)

    # L3 south zone Z0b (x 46.95 - 50, south of the MCU / strip): the south river spread out, D6 / D7 / D4 tuned, D5 by its way
    X0B = 47.25

    def d6(a):
        n = pre("FMC_D6", (41.6, 43.6))
        n.to((44.732, 43.6), (44.932, 43.8))
        n.block((50.35, 43.8), "R", 4, a, start=X0B - 44.932, tag="Z0b")
        n.to((53.15, 41.0))
        return tail(n, (55.0, 41.0))
    tuned("FMC_D6", d6, A0T, 4)

    def d7(a):
        n = pre("FMC_D7", (40.95, 43.85))
        n.to((44.628, 43.85), (45.548, 44.77))
        n.block((50.53, 44.77), "R", 4, a, start=X0B - 45.548, tag="Z0b")
        return tail(n, (53.1, 42.2))
    tuned("FMC_D7", d7, A0T, 4)

    def d4(a):
        n = pre("FMC_D4", (40.625, 44.1))
        n.to((44.524, 44.1), (46.524, 46.1))
        n.block((50.5, 46.1), "R", 4, a, start=X0B - 46.524, tag="Z0b")
        return tail(n, (53.6, 43.0))
    tuned("FMC_D4", d4, A0T, 4)
    fixed("FMC_D5", tail(pre("FMC_D5", (40.3, 44.35)).to((44.42, 44.35), (47.27, 47.2), (50.3, 47.2), (53.15, 44.35)), (55.2, 44.35)))
    fixed("FMC_A8", tail(pre("FMC_A8", (39.975, 44.6)).to((44.316, 44.6), (47.166, 47.45), (50.55, 47.45), (53.4, 44.6)), (55.8, 44.6)))
    fixed("FMC_A9", tail(pre("FMC_A9", (39.325, 44.85)).to((44.212, 44.85), (47.062, 47.7), (50.8, 47.7), (53.65, 44.85)), (56.2, 44.85)))
    fixed("FMC_A7", tail(pre("FMC_A7", (39.0, 45.1)).to((44.108, 45.1), (46.958, 47.95), (51.05, 47.95), (53.9, 45.1)), (56.6, 45.1)))
    fixed("FMC_SDNRAS", tail(pre("FMC_SDNRAS", (38.675, 45.35)).to((44.004, 45.35), (46.854, 48.2), (51.3, 48.2), (54.15, 45.35)), (57.0, 45.35)))
    fixed("FMC_SDNWE", tail(pre("FMC_SDNWE", (34.2, 45.6)).to((43.9, 45.6), (46.75, 48.45), (51.55, 48.45), (54.4, 45.6)), (57.4, 45.6)))
    P.drop_segs += [("LCD_G2", "L3", (32.36, 45.88), (48.7, 45.88)), ("LCD_G2", "L3", (48.7, 45.88), (49.1, 46.28)), ("LCD_G2", "L3", (49.1, 46.28), (49.1, 64.8))]
    P.moved["LCD_G2"] = Net("LCD_G2").track("L3", [(32.36, 45.88), (43.8, 45.88), (46.62, 48.7), (48.9, 48.7), (49.1, 48.9), (49.1, 64.8)])

    # =========================================================================== lane 2 (byte 2, north-east)
    P.pad_net.update({("U301", "A8"): "FMC_D19", ("U301", "A9"): "FMC_D16", ("U301", "B9"): "FMC_D17",
                      ("U301", "R8"): "FMC_D11", ("U301", "R9"): "FMC_D12"})
    # D16 / D17 keep their south exits and run as the lowest lanes of the L4 band south of the SDRAM (below lane 1's
    # zone), cut the south-east corner on a 3 mm diagonal and go straight into their vias from the east side:
    # D17 -> B9, D16 -> A9 (D19 -> A8). T2 = D16.
    Y17, Y16 = 46.78, 47.03
    # NBL2: two humps of 0.5 on its L4 river lane (first arc x 48.8); T2 = NBL2
    _n = pre("FMC_NBL2", (40.05, 29.0))
    _n.block((56.7, 29.0), "L", 2, 0.5, start=48.8 - 40.05, tag="ZN4")
    fixed("FMC_NBL2", tail(_n, (57.1, 29.4)))
    T2 = round(P.length(N["FMC_NBL2"]), 2)
    A2T = T2 - 0.3

    def d16(ch):
        return pre("FMC_D16", (43.25, 40.25)).to((43.25, Y16 - 0.3), (43.55, Y16), (62.0 - ch, Y16), (62.0, Y16 - ch), (62.0, 32.4), (60.6, 31.0)).hop("L1", (60.2, 31.4))
    CH = 3.0
    while CH > 0.6 and P.length(d16(CH)) < T2 - 0.25:
        CH = round(CH - 0.05, 2)
    fixed("FMC_D16", d16(CH))

    def d17(a):
        n = pre("FMC_D17", (43.9, 40.25)).to((43.9, Y17 - 0.3), (44.2, Y17))
        n.block((61.75 - CH, Y17), "L", 2, a, start=56.7 - 44.2, tag="Z1b")
        return n.to((61.75, Y17 - CH), (61.75, 32.95), (60.6, 31.8)).hop("L1", (60.2, 32.2))
    tuned("FMC_D17", d17, A2T, 2)
    # the L4 river lanes north of NBL2 step JG north over its block (A1 first, clear of LCD_BL_PWM's diagonal)
    JG = 0.55
    for k, (name, y, x0, x1) in enumerate([("FMC_A1", 27.75, 32.05, 58.45), ("FMC_A2", 28.0, 32.95, 58.15), ("FMC_SDNE0", 28.25, 33.2, 57.39),
                                           ("FMC_A0", 28.5, 33.45, 57.16), ("FMC_NBL1", 28.75, 39.65, 56.93)]):
        xs, xe = 47.0 + 0.104 * k, 51.616 - 0.104 * k
        fixed(name, tail(pre(name, (x0, y)).to((xs, y), (xs + JG, y - JG), (xe, y - JG), (xe + JG, y)), (x1, y)))

    # D18 / D20: blocks on their north legs in the L3 strip (humps east), then the present way south of the cap vias
    def d18(a):
        n = pre("FMC_D18", (43.25, 37.0)).to((47.65, 37.0), (48.25, 36.4))        # 0.6 corner: D20's corner then clears the clock via
        n.block((48.25, 29.72), "R", 7, a, start=1.4, tag="Z2s")
        return tail(n.to((48.65, 29.32)), (56.72, 29.32))
    tuned("FMC_D18", d18, A2T, 7)
    X20 = round(48.25 + N["FMC_D18"].blocks[0]["amp"] + 0.35, 2)

    def d20(a):
        n = pre("FMC_D20", (44.55, 38.3)).to((44.875, 37.975), (47.075, 37.975), (X20, 37.975 - (X20 - 47.075)))
        n.block((X20, 29.97), "R", 6, a, start=0.7, tag="Z2s")
        n.to((X20 + 0.4, 29.57), (56.22, 29.57), (57.55, 30.9), (57.55, 32.75), (58.2, 33.4))
        return n.hop("L1", (58.6, 33.8))
    tuned("FMC_D20", d20, A2T, 6)

    # D19 / D21 / D22 / D23: north past TP111 (y 25.2 - 25.95), zone Z2n on L3 north of the cap vias, first arcs at X0N
    Y19, Y21, Y22, Y23, X0N = 25.75, 24.6, 23.5, 22.5, 53.6

    def d19(a):
        n = pre("FMC_D19", (47.6, 36.35)).to((48.0, 35.95), (48.0, 26.35), (48.4, 25.95), (50.5, 25.95), (50.7, Y19))
        n.block((59.0, Y19), "L", 7, a, start=X0N - 50.7, tag="Z2n")
        return n.to((59.4, Y19 + 0.4), (59.4, 30.6), (59.8, 31.0)).hop("L1", (59.4, 31.4))
    tuned("FMC_D19", d19, A2T, 7)

    def d21(a):
        n = pre("FMC_D21", (47.35, 35.05)).to((47.75, 34.65), (47.75, 26.1), (48.15, 25.7), (50.4, 25.7), (50.4 + 25.7 - Y21, Y21))
        n.block((60.7, Y21), "L", 8, a, start=X0N - (50.4 + 25.7 - Y21), tag="Z2n")
        return tail(n.to((61.1, Y21 + 0.4)), (61.1, 33.0))
    tuned("FMC_D21", d21, A2T, 8)

    def d22(a):
        n = pre("FMC_D22", (47.1, 34.4)).to((47.5, 34.0), (47.5, 25.85), (47.9, 25.45), (50.3, 25.45), (50.3 + 25.45 - Y22, Y22))
        n.block((60.95, Y22), "L", 6, a, start=X0N - (50.3 + 25.45 - Y22), tag="Z2n")
        return tail(n.to((61.35, Y22 + 0.4)), (61.35, 33.4))
    tuned("FMC_D22", d22, A2T, 6)

    def d23(a):
        n = pre("FMC_D23", (46.85, 33.75)).to((47.25, 33.35), (47.25, 25.6), (47.65, 25.2), (50.2, 25.2), (50.2 + 25.2 - Y23, Y23))
        n.block((61.2, Y23), "L", 2, a, start=X0N - (50.2 + 25.2 - Y23), tag="Z2n")
        return tail(n.to((61.6, Y23 + 0.4)), (61.6, 34.6))
    tuned("FMC_D23", d23, A2T, 2)

    # =========================================================================== lane 1 (byte 0, south-east)
    T1 = round(P.length(N["FMC_NBL1"]), 2)
    A1T = T1 - 0.3
    fixed("FMC_BA0", tail(pre("FMC_BA0", (49.4, 38.625)).to((49.65, 38.625), (49.95, 38.925), (49.95, 43.45), (50.35, 43.85)), (57.0, 43.85)))
    YD13, YD14 = 45.5, 45.75

    def d13(a):
        n = Net("FMC_D13").track("L1", [(44.55, 40.9), (46.0, 40.9)])
        n.block((49.4, 40.9), "L", 4, a, start=0.3, tag="Z1a")
        return tail(n.to((49.7, 41.2), (49.7, YD13 - 0.3), (50.0, YD13), (57.3, YD13), (57.7, YD13 - 0.4)), (57.7, 41.1))
    tuned("FMC_D13", d13, A1T, 4)

    def d14(a):
        n = Net("FMC_D14").track("L1", [(43.9, 40.9), (44.225, 41.225), (46.0, 41.225)])
        n.block((49.15, 41.225), "R", 3, 2.0, start=0.6, tag="Z1a")
        n.to((49.45, 41.525), (49.45, YD14 - 0.3), (49.75, YD14))
        n.block((57.6, YD14), "R", 3, a, start=0.7, tag="Z1c")
        return tail(n.to((58.0, YD14 - 0.4)), (58.0, 41.6))
    _t = d14(0.6)
    fixed("FMC_D14", d14(P.amp_for(A1T - (P.length(_t) - _t.blocks[1]["adds"]), 3)), A1T)

    # L4 band south of the SDRAM: D15's block (x 47.75 - 51.35), then D10's (x 53.0 - 55.4); A4 / A5 stay where they are
    def d15(a):
        n = pre("FMC_D15", (46.75, 42.45)).to((46.75, 45.05), (47.05, 45.35))
        n.block((52.05, 45.35), "R", 6, a, start=0.7, tag="Z1b")
        return tail(n.to((52.84, 46.14), (56.06, 46.14), (57.25, 44.95)), (57.25, 41.0))
    tuned("FMC_D15", d15, A1T, 6)

    def d10(a):
        n = pre("FMC_D10", (47.0, 39.25)).to((47.0, 44.8), (47.3, 45.1))
        n.block((56.6, 45.1), "R", 4, a, start=53.0 - 47.3, tag="Z1b")
        return tail(n.to((57.0, 44.7)), (57.0, 40.2))
    tuned("FMC_D10", d10, A1T, 4)

    # L1 south river: zone Z1s (first arcs x 43.5; D8's at 44.05), then the lanes below D13 / D14; D11 -> R8 and
    # D12 -> R9 from the south; the south-east corner is cut early to stay 0.2 mm off the +12V pour corner (61.7, 46.6)
    X1S = 43.5
    Z12, Z9, Z8, ZA11 = 44.85, 46.2, 47.24, 48.16
    F11, F12, F9, F8, FA11 = 46.78, 47.03, 47.28, 47.53, 47.78

    def d11(a):
        n = pre("FMC_D11", (42.575, 44.6))
        n.block((47.9, 44.6), "L", 5, a, start=X1S - 42.575, tag="Z1s")
        return n.to((47.9 + F11 - 44.6, F11), (59.1, F11), (59.4, F11 - 0.3), (59.4, 42.6))
    tuned("FMC_D11", d11, A1T, 5)

    def d12(a):
        n = pre("FMC_D12", (42.25, 44.85))
        n.block((47.81, Z12), "R", 6, a, start=X1S - 42.25, tag="Z1s")
        return n.to((47.81 + F12 - Z12, F12), (59.8, F12), (60.2, F12 - 0.4), (60.2, 42.6))
    tuned("FMC_D12", d12, A1T, 6)

    def d9(a):
        n = pre("FMC_D9", (41.6, 45.1)).to((41.7, 45.1), (41.7 + Z9 - 45.1, Z9))
        n.block((2.592 + Z9, Z9), "R", 6, a, start=X1S - (41.7 + Z9 - 45.1), tag="Z1s")
        return tail(n.to((2.592 + F9, F9), (107.238 - F9, F9), (61.65, 107.238 - 61.65)), (61.65, 42.5))
    tuned("FMC_D9", d9, A1T, 6)

    def d8(a):
        n = pre("FMC_D8", (41.275, 45.35)).to((41.5, 45.35), (41.5 + Z8 - 45.35, Z8))
        n.block((2.238 + Z8, Z8), "R", 4, a, start=0.7, tag="Z1s")
        return tail(n.to((2.238 + F8, F8), (107.592 - F8, F8), (61.85, 107.592 - 61.85)), (61.85, 41.85))
    tuned("FMC_D8", d8, A1T, 4)
    fixed("FMC_A11", tail(pre("FMC_A11", (40.35, 46.3)).hop("L1", (42.1, 46.3), (42.1 + ZA11 - 46.3, ZA11), (49.0, ZA11), (49.0 + ZA11 - FA11, FA11),
                                                         (107.946 - FA11, FA11), (62.1, 107.946 - 62.1)), (62.1, 37.25)))


# ----------------------------------------------------------------------------- summary additions
# SDRAM ball -> its DQ name (the balls the plan gives another net)
PINS = {"A8": "DQ23", "A9": "DQ21", "B9": "DQ19", "R8": "DQ0", "R9": "DQ2", "D2": "DQ29", "D3": "DQ30"}
LTDC_PREFIX = "LCD_"
LTDC_NOT = ("LCD_BL_PWM", "LCD_DISP", "LCD_P38")      # LCD_ nets that are not LTDC signals


def summary(P, rows, lines, out):
    """The new swap table (swap_new.csv beside the outputs; from the swap.csv beside the board, else the board
    folder's) and the moved LCD_G2 against the LTDC group's track lengths."""
    src = os.path.join(os.path.dirname(P.board_path), "swap.csv")
    if not os.path.isfile(src):
        src = P.cfg.path("swap.csv")
    new = {PINS[k[1]]: v for k, v in P.pad_net.items()}
    sw = list(csv.reader(open(src, encoding="utf-8")))
    res = [sw[0]] + [[r[0], new.get(r[0], r[1])] for r in sw[1:]]
    with open(os.path.join(P.out_dir, "swap_new.csv"), "w", newline="", encoding="utf-8") as f:
        csv.writer(f, lineterminator="\n").writerows(res)
    out["swap_changes"] = {r[0]: [o[1], r[1]] for o, r in zip(sw[1:], res[1:]) if o[1] != r[1]}
    bad = [r for r in res[1:] if r[0].startswith("DQ") and not r[0].startswith("DQM") and len({(int(x[1][5:]) // 8) for x in res[1:] if x[0].startswith("DQ") and not x[0].startswith("DQM") and int(x[0][2:]) // 8 == int(r[0][2:]) // 8}) != 1]
    lines.append("swap changes (SDRAM pin: old -> new): " + ", ".join("%s: %s -> %s" % (k, a[4:], b[4:]) for k, (a, b) in out["swap_changes"].items()) +
                 "; bytes still whole: %s; nets used once: %s" % (not bad, len({r[1] for r in res[1:]}) == len(res) - 1))
    # LTDC: is the moved LCD_G2 the shortest or the longest of the group? (track lengths without vias or arcs)
    dist = lambda a, b: ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
    lcd = {}
    for (n, lay, a, b, w, is_arc) in P.board.tracks:
        if not is_arc and n.startswith(LTDC_PREFIX) and n not in LTDC_NOT:
            lcd[n] = lcd.get(n, 0) + dist(a, b)
    old = sum(dist(d[2], d[3]) for d in P.drop_segs)
    g2 = P.moved["LCD_G2"].items[0][2]
    delta = sum(dist(g2[i], g2[i + 1]) for i in range(len(g2) - 1)) - old
    srt = sorted(lcd.items(), key=lambda kv: kv[1])
    lines.append("LCD_G2 track %.2f -> %.2f mm (%+.2f); LTDC track lengths without vias: shortest %s %.2f, longest %s %.2f, LCD_G2 rank %d of %d" % (
        lcd["LCD_G2"], lcd["LCD_G2"] + delta, delta, srt[0][0], srt[0][1], srt[-1][0], srt[-1][1], [k for k, v in srt].index("LCD_G2") + 1, len(srt)))
    out["lcd_g2_delta"] = round(delta, 2)


# Free copper per region (planning/check.py --free): a cell is free when no copper of another net lies within 0.30 mm
# (track half width 0.05 + 0.19 to a hump + margin); L4 also keeps 0.5 mm off the L5 block edges (l5_gaps.json).
FREE = {"clearance": 0.30, "layers": ["L1", "L3", "L4"],
        "bands": {"L4": {"file": "l5_gaps.json", "width": 1.0}},
        "regions": {"north of SDRAM / strip (x 46.6-62, y 21.5-29.3)": (46.6, 21.5, 62.0, 29.3),
                    "strip between the packages (x 46.2-51.8, y 31-43)": (46.2, 31.0, 51.8, 43.0),
                    "east of SDRAM (x 62.2-66, y 28-46)": (62.2, 28.0, 66.0, 46.0),
                    "south of MCU / SDRAM (x 43-64, y 44.7-49.5)": (43.0, 44.7, 64.0, 49.5),
                    "SDRAM aisle (x 55.9-58.1, y 30-44)": (55.9, 30.0, 58.1, 44.0)}}
