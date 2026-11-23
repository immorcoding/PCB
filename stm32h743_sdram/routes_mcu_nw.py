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
  SWD     SWO (L3) to L1 at (41.0, 24.6), SWCLK (L3) east on y 26.85 to L1 at (44.85, 26.85), SWDIO (L6) east on
          y 27.3 to L1 at (45.5, 26.95); three L1 lanes north (x 42.3 -> 44.5, 44.85, 45.5) east of the reset key
          and into the header's signal pads from the east (westmost lane to the southmost pad)
  BOOT0   L6 straight north to a via at (39.35, 24.5), L1 into R202.1 and on to TP201
  SD      CMD (L3) and D1 (L6 -> L3 at (43.25, 24.75)) and D3 (L3) run north-east to x 45.2 / 45.75 / 46.3 and
          east above the test loop TP111 on L3 (y 21.4 / 21.95 / 22.5, slots for D0 and D2 between them); each
          net then: via Va beside its pull-up's signal pad -> L1 -> pull-up pad -> L1 north to via Vb -> inner
          layer -> via Vc in front of its socket contact -> L1 into the contact. The 3V3_SD band (y 17.85-18.65)
          between the pull-ups and the socket leaves no L1 way between them (pull-ups and contacts are in a
          different order, too): 1 + 3 vias per net
  SD_CD   L6 north at x 41.6 to y 13.5, east under the socket, L3 down into its Va (59.35, 20.99), the same
          pull-up -> contact hop, its contact via east of contact 9 (61.6, 16.6)
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
           "SDMMC1_D3", "SDMMC1_D1", "SD_CD", "CODEC_NRST", "NRST", "BOOT0", "CAN_STB"]
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


# ---- SD card: pull-up R80x (signal pad .2 at y 20.99) and socket contact; Va / Vb / Vc as in the header
SD = {  # net: (pull-up pad, Va, Vb, contact, Vc, layer of the Vb -> Vc hop, hop points between Vb and Vc)
    "SDMMC1_CMD": ("R801.2", (50.8, 20.99), (51.5, 20.1), "J801.3", (54.425, 17.39), "L6", [(54.21, 17.39)]),
    "SDMMC1_D1": ("R803.2", (55.0, 20.99), (54.3, 20.1), "J801.8", (59.925, 17.39), "L6",
                  [(55.4, 19.0), (59.35, 19.0), (59.925, 18.425)]),
    "SDMMC1_D3": ("R805.2", (57.8, 20.99), (57.1, 20.1), "J801.2", (53.325, 17.39), "L3",
                  [(57.1, 18.55), (56.6, 18.05), (53.985, 18.05)]),
    "SD_CD": ("R806.2", (59.35, 20.99), (58.5, 20.1), "J801.9", (61.6, 16.6), "L6",
              [(61.1, 20.1), (61.6, 19.6)]),
}


def sd_tail(net):
    """Chains after the arrival at Va: Va -> pull-up pad, pull-up pad -> Vb -> hop -> Vc -> contact."""
    pad, va, vb, con, vc, lay, hop = SD[net]
    last = [(vc[0], vc[1]), con] if net != "SD_CD" else [vc, (61.325, 16.325), con]
    return [("L1", [va, pad])], [("L1", [pad, vb]), V(*vb), (lay, [vb] + hop + [vc]), V(*vc), ("L1", last)]


def north():
    R = {}
    # ---- SWD to J803 (signal pads on its east column x 42.55: SWDIO 2.46, SWCLK 3.73, SWO 5.0)
    R["SWO"] = out("SWO", [gate("SWO"), (41.6, 27.3), (41.6, 25.2), (41.0, 24.6)]) + [
        V(41.0, 24.6), ("L1", [(41.0, 24.6), (41.95, 24.6), (42.3, 24.25), (42.3, 15.9), (44.5, 13.7), (44.5, 5.35),
                               (44.15, 5.0), "J803.6"])]
    R["SWCLK"] = out("SWCLK", [gate("SWCLK"), (43.25, 27.2), (43.6, 26.85), (44.85, 26.85)]) + [
        V(44.85, 26.85), ("L1", [(44.85, 26.85), (44.85, 4.08), (44.5, 3.73), "J803.4"])]
    R["SWDIO"] = out("SWDIO", [gate("SWDIO"), (44.2, 27.3), (45.15, 27.3), (45.5, 26.95)]) + [
        V(45.5, 26.95), ("L1", [(45.5, 26.95), (45.5, 3.16), (44.8, 2.46), "J803.2"])]
    # ---- BOOT0: R202.1 (pull-down) and TP201
    R["BOOT0"] = [out("BOOT0", [gate("BOOT0"), (39.35, 24.5)]) + [
        V(39.35, 24.5), ("L1", [(39.35, 24.5), (39.95, 23.9), "R202.1"])],
        [("L1", ["R202.1", (40.49, 22.11), "TP201.1"])]]
    # ---- SD lines: north-east, east above TP111 on L3, up into Va
    cmd = out("SDMMC1_CMD", [gate("SDMMC1_CMD"), (42.6, 24.35), (42.95, 24.0), (44.85, 24.0), (45.2, 23.65),
                             (45.2, 21.75), (45.55, 21.4), (50.39, 21.4), (50.8, 20.99)]) + [V(50.8, 20.99)]
    d1 = out("SDMMC1_D1", [gate("SDMMC1_D1"), (43.25, 24.75)]) + [
        V(43.25, 24.75), ("L3", [(43.25, 24.75), (45.4, 24.75), (45.75, 24.4), (45.75, 22.3), (46.1, 21.95),
                                 (54.04, 21.95), (55.0, 20.99)]), V(55.0, 20.99)]
    d3 = out("SDMMC1_D3", [(43.9, 27.75), (44.25, 27.4), (45.95, 27.4), (46.3, 27.05), (46.3, 22.85),
                           (46.65, 22.5), (56.29, 22.5), (57.8, 20.99)]) + [V(57.8, 20.99)]
    cd = out("SD_CD", [gate("SD_CD"), (41.6, 27.25), (41.6, 13.85), (41.95, 13.5), (59.35, 13.5)]) + [
        V(59.35, 13.5), ("L3", [(59.35, 13.5), (59.35, 20.99)]), V(59.35, 20.99)]
    for net, arr in (("SDMMC1_CMD", cmd), ("SDMMC1_D1", d1), ("SDMMC1_D3", d3), ("SD_CD", cd)):
        a, b = sd_tail(net)
        R[net] = [arr + a, b]
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
    # crystals: L1 only, 0.254, ball - crystal pad - load capacitor (routes_probe_xtal.py)
    R = {n: ([thin(c) for c in p] if p and isinstance(p[0], list) else thin(p)) for n, p in R.items()}
    R.update({
        "LSE_IN": [("L1", ["U201.E1", (31.9, 35.05), (30.4, 33.55), "Y202.1", "C227.1"], 0.254)],
        "LSE_OUT": [("L1", ["U201.F1", (34.6, 35.7), (34.45, 35.55), (30.0, 35.55), "Y202.2", "C228.1"], 0.254)],
        "HSE_IN": [("L1", ["U201.G1", (34.0, 36.35), (33.9, 36.45), (32.0, 36.45), "Y201.1", "C225.1"], 0.254)],
        "HSE_OUT": [("L1", ["U201.H1", (34.6, 37.0), (33.15, 38.45), (33.15, 39.2), "Y201.3", (32.25, 41.02), "C226.1"], 0.254)],
    })
    return R
