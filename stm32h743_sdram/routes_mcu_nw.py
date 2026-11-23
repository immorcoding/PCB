"""MCU north and west balls (the BGA block, SPEC 14 stop 3.4): the 32 signal balls whose buses are routed later (SAI1,
SWD, SDMMC1 CK / CMD / D2 / D3 / CD, RMII transmit side, the reset and control lines, six LCD lines, QSPI NCS), each
fanned out as the BGA block plan (bga_fan.json) puts it: dog-bone, inner-layer run to the edge of the rule area, and on
the same layer straight on to a GATE clear of the SDRAM bus, where the next routing step takes it over (open ends).
The crystals are drawn complete on L1 (no via, 0.254), as routes_probe_xtal.py proved.

    LOCAL_BOARD=<board> D:\\KiCad\\bin\\python.exe scripts\\busroute\\build.py stm32h743_sdram\\routes_mcu_nw.py --fast
    (build.sh route2 builds it on the real board after routes_mcu_south.py)

Gates (local mm): north exits (L3 / L6) run on north under the SDRAM's L1 river (y 28.8-30.8) and L4 river
(y 27.75-29.5) to y = GATE_N; west exits run on west under the SDRAM's west lanes (L1 x 30.65-33.75, L4 x 30.9-33.05)
to x = GATE_W. Balls the plan could not place are listed in OPEN (no copper; reasons in the plan text).
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
VIEWS = [("nw", 28.0, 25.0, 47.0, 44.0, 60)]
GATE_N, GATE_W = 27.6, 30.0          # north: clear of the +3V3 / +3V3_MCU vias at y 26.2-27.15
NETS_NW = ["SAI1_SD_B", "SAI1_MCLK_A", "SAI1_FS_A", "SAI1_SCK_A", "SAI1_SD_A", "SWO", "SWCLK", "SWDIO", "SDMMC1_CK",
           "SDMMC1_CMD", "SDMMC1_D2", "SDMMC1_D3", "SD_CD", "RMII_TXD0", "RMII_TXD1", "RMII_TX_EN", "CODEC_NRST", "PHY_NRST",
           "NRST", "BOOT0", "CAN_STB", "LCD_B6", "LCD_B7", "LCD_G3", "LCD_G7", "LCD_BL_PWM", "LCD_DISP", "QSPI_BK1_NCS"]
THIN = 0.1016


def gates():
    """{net: (ball, side, layer, gate point)} of the planned north / west balls."""
    out = {}
    for num, v in plan()["U201"]["signal"].items():
        if v["net"] not in NETS_NW:
            continue
        e = tuple(v["exit"])
        if v["side"] == "N":
            g = (e[0], GATE_N)
        elif v["side"] == "W" and e[1] in NW_TURN:
            g = (NW_TURN[e[1]][-1][0], GATE_N)
        elif v["side"] == "W":
            g = (GATE_W, e[1])
        elif v["side"] == "S":
            g = (e[0], 45.5)
        else:
            g = (47.0, e[1])
        out[v["net"]] = (num, v["side"], v["layer"], g)
    return out


OPEN = sorted(n for n in NETS_NW if n not in {v["net"] for v in plan()["U201"]["signal"].values()})


def thin(pieces):
    return [pc if pc[0] == "via" or len(pc) > 2 else (pc[0], pc[1], THIN) for pc in pieces]


# west exits above row D: the SDRAM's west vias (A10 (30.65, 32.8), A6 (31.15, 31.9), A3 (32.1, 31.6), D28 (33.3, 33.25),
# the ground returns (29.95, 32.2), (34.15, 32.95)) close the way west, so these lanes turn north just outside the
# rule area (one lane per 0.25 mm, the northmost exit outermost) and run north to the north gates
NW_TURN = {31.8: [(33.6, 31.4)], 32.45: [(33.35, 31.8)], 33.75: [(32.85, 33.75), (32.6, 33.5)]}


def path_to_gate(side, exit_, g):
    if side == "W" and exit_[1] in NW_TURN:
        pts = NW_TURN[exit_[1]]
        return pts + [(pts[-1][0], GATE_N)]
    return [g]


def routes(job):
    R = {}
    for net, (num, side, layer, g) in gates().items():
        e = tuple(plan()["U201"]["signal"][num]["exit"])
        R[net] = thin(ext(lead(num), path_to_gate(side, e, g)))
    # crystals: L1 only, 0.254, ball - crystal pad - load capacitor (routes_probe_xtal.py)
    R.update({
        "LSE_IN": [("L1", ["U201.E1", (31.9, 35.05), (30.4, 33.55), "Y202.1", "C227.1"], 0.254)],
        "LSE_OUT": [("L1", ["U201.F1", (34.6, 35.7), (34.45, 35.55), (30.0, 35.55), "Y202.2", "C228.1"], 0.254)],
        "HSE_IN": [("L1", ["U201.G1", (34.0, 36.35), (33.9, 36.45), (32.0, 36.45), "Y201.1", "C225.1"], 0.254)],
        "HSE_OUT": [("L1", ["U201.H1", (34.6, 37.0), (33.15, 38.45), (33.15, 39.2), "Y201.3", (32.25, 41.02), "C226.1"], 0.254)],
    })
    return R
