"""The model half of the bga_plan benchmark (system Python: numpy, scipy, scikit-image). Called by check.py.

    python scripts/tests/bga_plan/model_check.py <out.json>

1. synthetic: a 6 x 6 ball field (0.65 pitch, 0.30 pads), every ball its own net with a far pad to the south, four
   foreign vias on the four ball gaps round ball C3. Known answer: C3 is enclosed (no ball gap left, no way
   between a via and a ball), the other 35 balls get out.
2. units: the staircases of the slot cuts, the RTE-2 capacity formula, the order rows on a three-net case.
3. real: the dump of the real board at commit 08ca4e9 (stop 7, real_08ca4e9.json.gz):
   a) each of the 22 routed MCU nets with its own copper left out must have a way (ok, or detour for the one
      that is routed with 4 vias on the board): the model must not be stricter than the board;
   b) the 18 balls the stop-7 report lists as without a way out, judged together in the report's order with
      the crystal strip reserved (each found route is copper for the next). The verdicts are pinned in
      expected.json; the routes found are written out for check.py, which replays them through busroute.
"""
import gzip, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "..", "stm32h743_sdram"))
sys.path.insert(0, BOARD_DIR)
import bga_check as C                                       # noqa: E402
import bga_plan as P                                        # noqa: E402

KNOWN = "K15 D15 E15 G15 H15 J15 J14 G14 F14 M11 N12 N3 N4 P3 P4 R2 R4 R5".split()
ROUTED = ("ETH_MDC ETH_MDIO FDCAN1_RX FDCAN1_TX I2C4_SCL I2C4_SDA LCD_B3 LCD_DE LCD_G4 LCD_G5 QSPI_BK1_IO0 QSPI_BK1_IO1 QSPI_BK1_IO2 "
          "QSPI_BK1_IO3 QSPI_CLK RMII_CRS_DV RMII_REF_CLK RMII_RXD0 RMII_RXD1 TP_RST USART1_RX USART1_TX").split()


def synthetic():
    rows = "ABCDEF"
    pads, width = [], {}
    for j in range(6):
        for i in range(6):
            net = "S_%s%d" % (rows[j], i + 1)
            x, y = round(i * 0.65, 4), round(j * 0.65, 4)
            pads.append({"ref": "U201", "num": "%s%d" % (rows[j], i + 1), "net": net, "pos": [x, y], "layers": ["L1"], "smd": True, "hole": 0.0, "shape": "circle",
                         "r": 0.15, "box": [x - 0.15, y - 0.15, x + 0.15, y + 0.15], "poly": None})
            pads.append({"ref": "J1", "num": str(j * 6 + i + 1), "net": net, "pos": [x, 30.0], "layers": ["L1"], "smd": True, "hole": 0.0, "shape": "circle",
                         "r": 0.3, "box": [x - 0.3, 29.7, x + 0.3, 30.3], "poly": None})
            width[net] = 0.1016
    cx, cy = 2 * 0.65, 2 * 0.65
    vias = [["X", [round(cx + dx, 4), round(cy + dy, 4)], 0.3, 0.15] for dx in (-0.325, 0.325) for dy in (-0.325, 0.325)]
    geo = {"pads": pads, "vias": vias, "tracks": [], "zones": [], "keepouts": [], "areas": {"BGA_MCU": {"rect": [-1.45, -1.45, 4.7, 4.7], "layers": ["L1"]}},
           "rules": {"w_area": 0.09, "clr_area": 0.09, "via_area": [0.3, 0.15], "hole_clr": 0.2, "hole_hole": 0.254, "area_names": ["BGA_MCU"]}, "width": width}
    r = C.check_state(geo, 3.0, window=(-4.0, -4.0, 7.25, 7.25))
    return {v["ball"]: v["verdict"] for k, v in r.items() if not k.startswith("_")}


def units():
    out = {}
    st = P.staircases(((3.0 - 0.3 - 0.254) / 0.65) ** 2 + 1e-9)
    out["staircases_3.0"] = [len(st), max(len(p) for p in st), sorted({p[-1] for p in st})]
    st = P.staircases(((3.5 - 0.3 - 0.254) / 0.65) ** 2 + 1e-9)
    out["staircases_3.5"] = [len(st), max(len(p) for p in st), sorted({p[-1] for p in st})]
    out["rte2"] = [P.tune_capacity(6.0, 0.5), P.tune_capacity(6.0, 2.0), P.tune_capacity(1.9, 0.5)]
    # order rows: three positions; the net at position 0 may aim at 0 or 180, the one at 1 at 90, the one at 2 at 0 or 180:
    # the cheapest picks 180, 90, 0 (inverted twice); with the rows the answer must rise: 0, 90, 180
    lp = P.LP()
    a0, a1 = lp.var(5.0), lp.var(1.0)
    b = lp.var(0.0)
    c0, c1 = lp.var(1.0), lp.var(5.0)
    lp.row([a0, a1], [1, 1], 1, 1); lp.row([b], [1], 1, 1); lp.row([c0, c1], [1, 1], 1, 1)
    P.order_rows(lp, [[(a0, 0.0, 0.0), (a1, 180.0, 180.0)], [(b, 90.0, 90.0)], [(c0, 0.0, 0.0), (c1, 180.0, 180.0)]])
    x = lp.solve(10).x
    out["order"] = [int(round(v)) for v in (x[a0], x[a1], x[b], x[c0], x[c1])]
    return out


def real():
    geo = json.load(gzip.open(os.path.join(HERE, "real_08ca4e9.json.gz"), "rt", encoding="utf-8"))
    net = {p["num"]: p["net"] for p in geo["pads"] if p["ref"] == "U201"}
    one = C.check_state(geo, 3.0, ROUTED)
    routed = {n: [one[n]["verdict"], one[n]["vias"]] for n in ROUTED}
    order = [net[b] for b in KNOWN]
    j = C.check_state(geo, 3.0, order, joint=True, reserve=[(None, ("L1",), (29.0, 33.5, 34.0, 38.5))])
    known = {j[n]["ball"]: [j[n]["verdict"], j[n]["vias"], j[n]["chain"]] for n in order}
    pieces = {}
    for n in order:
        v = j[n]
        if v["pieces"] and v["verdict"] != "slot" and not v["grid"]:
            p = [list(x) for x in v["pieces"]]
            p[0][1] = ["U201." + v["ball"]] + list(p[0][1][1:])
            pieces[n] = p
    return {"routed": routed, "known": known, "pieces": pieces, "seconds": [one["_meta"]["seconds"], j["_meta"]["seconds"]]}


if __name__ == "__main__":
    res = {"synthetic": synthetic(), "units": units()}
    if "--no-real" not in sys.argv:
        res["real"] = real()
    json.dump(res, open(sys.argv[1], "w", encoding="utf-8"), indent=0)
