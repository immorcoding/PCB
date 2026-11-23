"""MCU north and west balls, formal routing (stop 7): SAI1 to the codec, the codec reset, SWD and NRST to the debug
header / reset key, BOOT0, the SD card lines CMD / D3 / D1 / CD and CAN_STB. Each ball leaves as the BGA block plan
(bga_fan.json) puts it (dog-bone, inner-layer run to the rule-area edge, on to the gate row at y 27.6 / the west
gates at x 30.0); from there every net is written by hand with coordinates (RTE-3).

    LOCAL_BOARD=<board> D:\\KiCad\\bin\\python.exe scripts\\busroute\\build.py stm32h743_sdram\\routes_mcu_nw.py --fast
    (build.sh route2 builds it on the real board after routes_mcu_south.py)

Territory (shared with the south / west agent, stop 7): the L4 band x 27.5-44, y 25.4-27.45 and the west corridor
x 27.5-30.6, y 25.4-40 belong to the other group on L4: this group crosses them on L1 / L3 / L6 only and puts no
via there (every via is outside both boxes, or north of y 25.05).

North of the gate row (y 27.6), the power vias of R203 / C217 at y 26.2-27.15 leave three windows for lanes
through the band (x 39.0-40.0, 41.57-41.62, 42.43-43.87); vias are allowed east of x 44.35:
  SWD     SWO (L3) to L1 at (41.0, 24.6), SWCLK (L3) east on y 26.85 to L1 at (44.85, 26.85), SWDIO (L6, lane
          x 45.2 since c8) north-east to L1 at (45.5, 26.95); three L1 lanes north (x 42.3 -> 44.5, 44.85, 45.5)
          east of the reset key and into the header's signal pads from the east (westmost lane to the southmost pad)
  BOOT0   L6 straight north to a via at (39.35, 24.5), L1 into R202.1 and on to TP201
  SD      (stop 7 c8) the pull-ups R804 R805 R801 | R802 R803 R806 stand in contact order in a row at y 19.2
          (signal pad north); each line comes up by a via Va south-west of its pull-up's signal pad (y 19.365),
          L1 into the pad and one L1 piece north into its contact (CK: a via in line with contact 5). The lines
          reach their vias from the north (U-turns, so each layer keeps its order without a crossing):
            L3  CMD (lane x 42.6) and D3 (x 46.3, east of the SWD vias) north to rows y 18.5 / 18.75, east, down
            L6  D1 / D0 / D2 jog west into the window between the R203 / C217 vias (x 42.9 / 43.2 / 43.5); D2 then
                steps east to x 45.9 (west of the FDCAN lanes); CK leaves L3 by a via (43.75, 24.4) between D0
                and D2; north to rows y 18.0 (D1), 18.25 (D0), 18.5 (CK), 18.75 (D2), east, down
          Lengths (SPEC 9: D0-D3 and CMD between CK and CK + 5 mm): arc serpentines (TUNING) on CK's L6 lane
          (east), D2's / D3's rows (south) and CMD's row (north); 1 + 1 vias per line (CK 1 + 2)
  SD_CD   L6 north at x 41.6, east along y 13.5 under the socket (north of CAN_STB's row), one via to L3 at
          (59.45, 13.5) to pass CAN_STB's row, L3 down and east into its Va (60.025, 19.615) beside R806 (0.25 below the row: C803 / U801 / J801 leave no room in it) (3 vias)
  CAN_STB L6 north at x 42.6, east along y 14.3 (north of the FDCAN_TX via) to a via north of U801.8
"""
import os
from fan_leads import plan, lead, ext

BOARD = os.environ.get("LOCAL_BOARD", "stm32h743_sdram.kicad_pcb")
ORIGIN = (100, 100)
GROUP = "mcu_nw"
OPEN_ENDS = True
YIELD_NETS = ["GND"]
VIA_LIMIT = 6
DRC_IGNORE = {"solder_mask_bridge": "mask webs between fine-pitch pads of the footprints (QFN, FPC), there before this group"}
PROFILE = {"area_free_classes": ["XTAL"]}    # the crystal lines keep 0.254 inside the rule area (SPEC 7)
VIEWS = [("nw", 28.0, 25.0, 47.0, 44.0, 60), ("north", 36.0, 0.0, 63.0, 29.0, 30), ("sd", 49.0, 12.0, 63.0, 24.0, 60),
         ("gates", 38.0, 23.0, 47.5, 28.5, 90), ("codec", 18.0, 22.0, 35.0, 31.0, 60), ("can", 58.0, 12.0, 71.0, 18.0, 60),
         ("west", 22.0, 24.0, 35.0, 40.0, 50), ("swd", 37.0, 1.0, 47.0, 16.0, 60)]
NETS_NW = ["SAI1_SD_B", "SAI1_MCLK_A", "SAI1_FS_A", "SAI1_SCK_A", "SAI1_SD_A", "SWO", "SWCLK", "SWDIO", "SDMMC1_CMD",
           "SDMMC1_D3", "SDMMC1_D1", "SD_CD", "CODEC_NRST", "NRST", "BOOT0", "CAN_STB", "SDMMC1_CK", "SDMMC1_D0",
           "SDMMC1_D2"]
SD_DATA = ["SDMMC1_CMD", "SDMMC1_D0", "SDMMC1_D2", "SDMMC1_D3"]
# SPEC 9: D0-D3 and CMD between CK and CK + 5 mm. D1 is the longest line (deepest ball, easternmost contact but CD's):
# CK is tuned up to D1 - SPREAD_CK + margin (D1 never lengthened), the other data lines and CMD up to D0 - SPREAD_D +
# margin, which lands them 0.3 mm above CK (D0 - D1 = -1.25 in the fast build)
SPREAD_CK = float(os.environ.get("SD_SPREAD_CK", "4.7"))
SPREAD_D = float(os.environ.get("SD_SPREAD_D", "3.15"))
TUNING = {"groups": {"sdmmc_ck": {"nets": ["SDMMC1_CK", "SDMMC1_D1"], "spread": SPREAD_CK},
                     "sdmmc_d": {"nets": SD_DATA, "spread": SPREAD_D}},
          "margin": 0.3, "radius": 0.15, "amp": 0.5, "amp_max": 2.0, "pitch": {"default": 0.3},
          "end": 0.35, "clr": 0.19, "area_gap": 0.127, "keep": 0.7}
GATE_N, GATE_W = 27.6, 30.0
THIN = 0.1016


def V(x, y):
    return ("via", (x, y))


def thin(pieces):
    return [pc if pc[0] == "via" or len(pc) > 2 else (pc[0], pc[1], THIN) for pc in pieces]


def ball(net):
    return next(num for num, v in plan()["U201"]["signal"].items() if v["net"] == net)


def out(net, pts):
    """The planned lead of `net` (ball -> exit at the rule-area edge) continued on its layer through pts."""
    return ext(lead(ball(net)), pts)


def gate(net):
    e = plan()["U201"]["signal"][ball(net)]["exit"]
    return (e[0], GATE_N)


# ---- SD card (c8): each line's via Va south-west of its pull-up's signal pad; L1 into the pad, then into the contact
SD_VA = {"SDMMC1_D2": (50.925, 19.365), "SDMMC1_D3": (52.325, 19.365), "SDMMC1_CMD": (53.75, 19.365),
         "SDMMC1_D0": (57.325, 19.365), "SDMMC1_D1": (58.675, 19.365), "SD_CD": (60.025, 19.615)}
SD_PU = {"SDMMC1_D2": ("R804.2", [(51.6, 18.29), (52.225, 17.665)], "J801.1"),
         "SDMMC1_D3": ("R805.2", [(53.0, 18.29), (53.325, 17.965)], "J801.2"),
         "SDMMC1_CMD": ("R801.2", [], "J801.3"),
         "SDMMC1_D0": ("R802.2", [(58.0, 18.29), (58.825, 17.465)], "J801.7"),
         "SDMMC1_D1": ("R803.2", [(59.35, 18.29), (59.925, 17.715)], "J801.8"),
         "SD_CD": ("R806.2", [(60.7, 18.54), (60.875, 18.365)], "J801.9")}


def sd_end(net, arr):
    """arr (pieces ending at Va) + via Va + L1 into the pull-up pad; second chain: pull-up pad -> contact."""
    va = SD_VA[net]
    pad, pts, con = SD_PU[net]
    return [arr + [V(*va), ("L1", [va, pad])], [("L1", [pad] + pts + [con])]]


def north():
    R = {}
    # ---- SWD to J803 (signal pads on its east column x 42.55: SWDIO 2.46, SWCLK 3.73, SWO 5.0)
    R["SWO"] = out("SWO", [gate("SWO"), (41.6, 27.3), (41.6, 25.2), (41.0, 24.6)]) + [
        V(41.0, 24.6), ("L1", [(41.0, 24.6), (41.95, 24.6), (42.3, 24.25), (42.3, 15.9), (44.5, 13.7), (44.5, 5.35),
                               (44.15, 5.0), "J803.6"])]
    R["SWCLK"] = out("SWCLK", [gate("SWCLK"), (43.25, 27.2), (43.6, 26.85), (44.85, 26.85)]) + [
        V(44.85, 26.85), ("L1", [(44.85, 26.85), (44.85, 4.08), (44.5, 3.73), "J803.4"])]
    R["SWDIO"] = out("SWDIO", [(45.2, 27.6), (45.5, 27.3), (45.5, 26.95)]) + [
        V(45.5, 26.95), ("L1", [(45.5, 26.95), (45.5, 3.16), (44.8, 2.46), "J803.2"])]
    # ---- BOOT0: R202.1 (pull-down) and TP201
    R["BOOT0"] = [out("BOOT0", [gate("BOOT0"), (39.35, 24.5)]) + [
        V(39.35, 24.5), ("L1", [(39.35, 24.5), (39.95, 23.9), "R202.1"])],
        [("L1", ["R202.1", (40.49, 22.11), "TP201.1"])]]
    # ---- SD lines (c8): north, east in rows north of the pull-up row, a 45-degree step down between the vias and
    # east into each via Va (no turn back at a via: the L1 leaves north-east into the pull-up)
    R["SDMMC1_CMD"] = sd_end("SDMMC1_CMD", out("SDMMC1_CMD", [(42.6, 18.85), (42.95, 18.5), (52.5, 18.5), (53.365, 19.365),
                                                              (53.75, 19.365)]))
    R["SDMMC1_D3"] = sd_end("SDMMC1_D3", out("SDMMC1_D3", [(43.9, 27.75), (44.25, 27.4), (45.95, 27.4), (46.3, 27.05),
                                                            (46.3, 19.1), (46.65, 18.75), (51.3, 18.75), (51.915, 19.365),
                                                            (52.325, 19.365)]))
    R["SDMMC1_D1"] = sd_end("SDMMC1_D1", out("SDMMC1_D1", [(43.25, 28.6), (42.9, 28.25), (42.9, 18.35), (43.25, 18.0),
                                                            (56.6, 18.0), (57.965, 19.365), (58.675, 19.365)]))
    R["SDMMC1_D0"] = sd_end("SDMMC1_D0", out("SDMMC1_D0", [(43.9, 28.9), (43.2, 28.2), (43.2, 18.6), (43.55, 18.25),
                                                            (56.1, 18.25), (57.215, 19.365), (57.325, 19.365)]))
    R["SDMMC1_D2"] = sd_end("SDMMC1_D2", out("SDMMC1_D2", [(44.55, 29.2), (43.5, 28.15), (43.5, 25.6), (45.9, 23.2),
                                                            (45.9, 19.1), (46.25, 18.75), (49.7, 18.75), (50.315, 19.365),
                                                            (50.925, 19.365)]))
    R["SD_CD"] = sd_end("SD_CD", out("SD_CD", [gate("SD_CD"), (41.6, 27.25), (41.6, 13.85), (41.95, 13.5), (59.45, 13.5)]) + [
        V(59.45, 13.5), ("L3", [(59.45, 13.5), (59.45, 19.19), (59.875, 19.615), (60.025, 19.615)])])
    # SDMMC1_CK (A12): L3 north between CMD and SWCLK, a via between the L6 lanes of D0 and D2, L6 north (serpentine
    # site, humps east), east in its row, down into its via in line with contact 5 (no pull-up)
    R["SDMMC1_CK"] = out("SDMMC1_CK", [(42.925, 25.225), (43.75, 24.4)]) + [
        V(43.75, 24.4), ("L6", [(43.75, 24.4), (43.75, 18.85), (44.1, 18.5), (55.3, 18.5), (56.165, 19.365), (56.625, 19.365)]),
        V(56.625, 19.365), ("L1", [(56.625, 19.365), "J801.5"])]
    # ---- CAN_STB: north, east along y 14.3, via north of U801.8
    R["CAN_STB"] = out("CAN_STB", [gate("CAN_STB"), (42.6, 16.0), (44.0, 14.6), (44.3, 14.3), (69.095, 14.3)]) + [
        V(69.095, 14.3), ("L1", [(69.095, 14.3), "U801.8"])]
    return R


# west exits above row D (SAI): turn north just outside the rule area, one lane per 0.25 mm
NW_TURN = {31.8: [(33.6, 31.4)], 32.45: [(33.35, 31.8)], 33.75: [(32.85, 33.75), (32.6, 33.5)]}


# SAI1 to the codec's east pins (U601.5 SD_B 25.75, .4 SD_A 26.25, .3 FS 26.75, .2 SCK 27.25, .1 MCLK 27.75): the
# lanes come north from the west exits (L3 SD_B / SCK, L6 MCLK / FS / SD_A), change to L1 north of the L4 band
# (vias at y 24.7, west -> east in pin order; SD_B, which is east of SCK on L3, hooks round north to the westmost
# via at (31.0, 24.05)), and run west on L1 straight into the pins at 0.5 mm pitch, next to the L2 ground (no via in
# the band or the corridor; the codec's analog pins are on its other three sides)
SAI_IN = {   # net: (points after the gate, via)
    "SAI1_SD_B": ([(33.6, 24.4), (33.25, 24.05)], (31.0, 24.05)),
    "SAI1_SD_A": ([(32.6, 25.85), (31.65, 24.9)], (31.65, 24.7)),
    "SAI1_FS_A": ([(33.35, 25.95), (32.3, 24.9)], (32.3, 24.7)),
    "SAI1_SCK_A": ([(33.35, 25.5), (32.95, 25.1)], (32.95, 24.7)),
    "SAI1_MCLK_A": ([(33.6, 25.6), (34.25, 24.95)], (34.25, 24.7)),
}
SAI_L1 = {   # net: L1 points from the via to the pin
    "SAI1_SD_B": [(31.0, 25.25), (30.5, 25.75), "U601.5"],
    "SAI1_SD_A": [(31.65, 25.75), (31.15, 26.25), "U601.4"],
    "SAI1_FS_A": [(32.3, 26.25), (31.8, 26.75), "U601.3"],
    "SAI1_SCK_A": [(32.95, 26.75), (32.45, 27.25), "U601.2"],
    "SAI1_MCLK_A": [(34.25, 26.6), (33.1, 27.75), "U601.1"],
}


def west():
    R = {}
    for net, (pts, via) in SAI_IN.items():
        e = plan()["U201"]["signal"][ball(net)]["exit"]
        t = NW_TURN[e[1]]
        R[net] = out(net, t + [(t[-1][0], GATE_N)] + pts + [via]) + [V(*via), ("L1", [via] + SAI_L1[net])]
    # CODEC_NRST: off its lane 1.4 mm before the other group's PHY_NRST gate (30.0, 34.4), south between the two
    # crystal bodies (y 36.75), L6 north at x 27.15 (NRST runs on L3 west of it), into R603.1 from the north-west;
    # R603.1 west to a second via and on L6 to the via south-west of U601.31 (the pin opens to the south only:
    # pins 30 / 32 and the +1V8 pour box it in); C612.1 hangs below R603.1 (a 0.12 mm dog-leg: the pads are 0.03 mm
    # apart in x)
    R["CODEC_NRST"] = [out("CODEC_NRST", [(31.4, 34.4), (30.9, 34.9), (30.9, 36.25), (30.4, 36.75), (27.15, 36.75)]) + [
        V(27.15, 36.75), ("L6", [(27.15, 36.75), (27.15, 29.4), (25.95, 28.2), (23.75, 28.2)]), V(23.75, 28.2),
        ("L1", [(23.75, 28.2), (24.69, 28.2), "R603.1"])],
        [("L1", ["R603.1", (24.97, 28.72), (24.97, 29.6), "C612.1"])],
        [("L1", ["R603.1", (23.75, 28.6), (23.6, 28.75)]), V(23.6, 28.75), ("L6", [(23.6, 28.75), (22.95, 29.4), (19.75, 29.4)]),
         V(19.75, 29.4), ("L1", [(19.75, 29.4), (20.25, 28.9), "U601.31"])]]
    # NRST: west between the crystal bodies (y 37.2), L3 north at x 25.6, east along y 24.0 / 22.0 north of the SAI
    # vias, a via at (39.6, 14.6) west of the SWD lanes, L1 into C224.1 -> SW201.1 -> J803.10
    R["NRST"] = [out("NRST", [(33.55, 37.2), (26.1, 37.2), (25.6, 36.7), (25.6, 24.5), (26.1, 24.0), (29.7, 24.0),
                              (31.7, 22.0), (36.6, 22.0), (39.6, 19.0), (39.6, 14.6)]) + [
        V(39.6, 14.6), ("L1", [(39.6, 14.6), "C224.1"])],
        [("L1", ["C224.1", (41.52, 13.5), (40.3, 12.28), "SW201.1"])],
        [("L1", ["SW201.1", (40.3, 8.55), (41.31, 7.54), "J803.10"])]]
    return R


def routes(job):
    R = north()
    R.update(west())
    # serpentine sites of the SD lines (TUNING): CK on its L6 lane (humps east, D2's lane 2.15 mm east of it), D3 and D2
    # on their rows (humps south, free down to the FDCAN rows), CMD on its row (humps north)
    job.slot("SDMMC1_CK", "L6", (43.75, 23.0), (43.75, 18.85), side="R")
    job.slot("SDMMC1_D3", "L3", (46.65, 18.75), (51.3, 18.75), side="R")
    job.slot("SDMMC1_D2", "L6", (46.25, 18.75), (49.7, 18.75), side="R")
    job.slot("SDMMC1_CMD", "L3", (42.95, 18.5), (52.5, 18.5), side="L")
    # crystals: L1 only, 0.254, ball - crystal pad - load capacitor (routes_probe_xtal.py)
    R = {n: ([thin(c) for c in p] if p and isinstance(p[0], list) else thin(p)) for n, p in R.items()}
    R.update({
        "LSE_IN": [("L1", ["U201.E1", (31.9, 35.05), (30.4, 33.55), "Y202.1", "C227.1"], 0.254)],
        "LSE_OUT": [("L1", ["U201.F1", (34.6, 35.7), (34.45, 35.55), (30.0, 35.55), "Y202.2", "C228.1"], 0.254)],
        "HSE_IN": [("L1", ["U201.G1", (34.0, 36.35), (33.9, 36.45), (32.0, 36.45), "Y201.1", "C225.1"], 0.254)],
        "HSE_OUT": [("L1", ["U201.H1", (34.6, 37.0), (33.15, 38.45), (33.15, 39.2), "Y201.3", (32.25, 41.02), "C226.1"], 0.254)],
    })
    return R
