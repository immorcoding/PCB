"""Placement checks of the STM32H743 + SDRAM board that are measured rather than routed (LAY-2 rails, LAY-3).

    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\layout_probe.py [--json <out.json>]

Reads the board file and copper.sketch (nothing is written). Distances are straight lines between pad centres
(crystals, hot loops) or Manhattan lengths ball to pad (buses: an upper bound for a route without detours,
not counting the escape inside the BGA); they decide whether a part is close enough, not the routing.

  rails      every pad of a copper-class net that has drawn regions in the sketch: does a region of its net
             reach it (any of nine points spread over the pad inside the region) (outer-layer pour on its own side, or an L5 block, which it reaches by a via).
             +3V3 counts as covered where no other L5 block is (the rest of L5 is +3V3).
  crystals   ball - crystal pad and crystal pad - load capacitor; the crystal parts inside the L1 window the
             SDRAM sketch keeps free (x 29-34, y 33.5-38.5, open to the west)
  loops      the high-current loops of the three switchers: input capacitor to VIN and GND pins (bucks),
             switch pin - diode - output capacitor - GND pin (boost), switch pin - inductor
  buses      per bus and net: Manhattan ball to the far pad, against the limits of SPEC 9
  lcd fan    straight paths ball to FPC pad of every net the MCU shares with J701: the parts whose courtyard
             they cross, and how far the boost's switch node (SW_BL pads) stays from them
"""
import json, math, os, sys
import pcbnew
from pcbnew import ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))                     # interim (Tools/ consolidation stage 1): the repository root, for Tools.KiCadDesignTools
from Tools.KiCadDesignTools.copper import cu_sketch

PCB = os.path.join(HERE, "stm32h743_sdram.kicad_pcb")
SKETCH = os.path.join(HERE, "copper.sketch")
OX, OY = 100.0, 100.0
XTAL_WINDOW = (29.0, 33.5, 34.0, 38.5)

LOOPS = {
    "U101 5 V buck": [("VIN", "U101", "3", "C104", "+12V"), ("GND", "U101", "1", "C104", "GND"),
                      ("SW", "U101", "2", "L101", "SW_5V"), ("bulk", "U101", "3", "C102", "+12V")],
    "U102 3.3 V buck": [("VIN", "U102", "4", "C108", "+5V"), ("GND", "U102", "2", "C108", "GND"),
                        ("SW", "U102", "3", "L102", "SW_3V3")],
    "U701 backlight boost": [("VIN", "U701", "5", "C704", "+5V_BL"), ("SW", "U701", "1", "D701", "SW_BL"),
                             ("SW-L", "U701", "1", "L701", "SW_BL"), ("diode-Cout", "D701", "1", "C705", "LED_A"),
                             ("Cout-GND", "U701", "2", "C705", "GND")],
}
BUSES = {
    "LTDC": (["LCD_R%d" % i for i in range(3, 8)] + ["LCD_G%d" % i for i in range(2, 8)] + ["LCD_B%d" % i for i in range(3, 8)]
             + ["LCD_CLK", "LCD_DE", "LCD_HSYNC", "LCD_VSYNC"], "J701", 120.0, 30.0),
    "QSPI": (["QSPI_CLK", "QSPI_BK1_IO0", "QSPI_BK1_IO1", "QSPI_BK1_IO2", "QSPI_BK1_IO3"], "U401", 30.0, None),
    "RMII": (["RMII_REF_CLK", "RMII_CRS_DV", "RMII_RXD0", "RMII_RXD1", "RMII_TX_EN", "RMII_TXD0", "RMII_TXD1"], "U501", 60.0, None),
    "SDMMC": (["SDMMC1_CK", "SDMMC1_CMD", "SDMMC1_D0", "SDMMC1_D1", "SDMMC1_D2", "SDMMC1_D3"], "J801", None, None),
    "SAI": (["SAI1_MCLK_A", "SAI1_SCK_A", "SAI1_FS_A", "SAI1_SD_A", "SAI1_SD_B"], "U601", None, None),
    "CAN": (["FDCAN1_TX", "FDCAN1_RX"], "U801", None, None),
    "SWD": (["SWDIO", "SWCLK", "SWO"], "J803", None, None),
    "UART": (["USART1_TX", "USART1_RX"], "J804", None, None),
}
NET_LIMIT = {"RMII_REF_CLK": 40.0}


def main(argv):
    board = pcbnew.LoadBoard(argv[argv.index("--pcb") + 1] if "--pcb" in argv else PCB)
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    L = lambda v: (ToMM(v.x) - OX, ToMM(v.y) - OY)
    pad = lambda ref, num: next(p for p in fps[ref].Pads() if p.GetNumber() == num)
    net_pad = lambda ref, net: [p for p in fps[ref].Pads() if p.GetNetname() == net]
    R = {}

    # ---- rails against the sketch
    sk = cu_sketch.load_sketch(SKETCH, 6)
    drawn = {}
    for r in sk.regions:
        if not r.whole:
            drawn.setdefault(r.net, []).append(r)
    l3_blocks = [r for r in sk.regions if r.layer == 5 and not r.whole]      # the power blocks (L5 since 2026-11-23)
    nm = lambda p: (int(round(p[0] * 1e6)), int(round(p[1] * 1e6)))
    def on(r, p):
        return cu_sketch.inside(nm(p), [r.pts]) >= 0          # 1 inside, 0 on the edge, -1 outside
    rails = {}
    for net in sorted(set(drawn) | {"+3V3"}):
        if net == "GND":
            continue
        pads, off = 0, []
        for f in board.GetFootprints():
            c = L(f.GetPosition())
            if not (0 <= c[0] <= 85 and 0 <= c[1] <= 75):
                continue
            side = 6 if f.GetLayer() == pcbnew.B_Cu else 1
            for p in f.Pads():
                if p.GetNetname() != net:
                    continue
                pads += 1
                xy = L(p.GetPosition())
                bb = p.GetBoundingBox()
                x0, y0 = ToMM(bb.GetLeft()) - OX, ToMM(bb.GetTop()) - OY
                x1, y1 = ToMM(bb.GetRight()) - OX, ToMM(bb.GetBottom()) - OY
                pts = [(x0 + (x1 - x0) * i / 4, y0 + (y1 - y0) * j / 4) for i in (1, 2, 3) for j in (1, 2, 3)]
                if net == "+3V3":
                    ok = not any(on(r, xy) for r in l3_blocks)
                else:
                    ok = any(on(r, q) for r in drawn[net] if r.layer in (side, 3) for q in pts)
                if not ok:
                    off.append("%s.%s" % (f.GetReference(), p.GetNumber()))
        rails[net] = {"pads": pads, "off": off}
    R["rails"] = rails

    # ---- crystals
    xt = {}
    for name, (ref, caps, balls) in {"HSE": ("Y201", ("C225", "C226"), ("G1", "H1")),
                                     "LSE": ("Y202", ("C227", "C228"), ("E1", "F1"))}.items():
        d = {}
        for b in balls:
            bp = pad("U201", b)
            n = bp.GetNetname()
            yp = net_pad(ref, n)[0]
            cp = [p for c in caps for p in net_pad(c, n)][0]
            d[n] = {"ball_to_crystal": round(math.dist(L(bp.GetPosition()), L(yp.GetPosition())), 2),
                    "crystal_to_cap": round(math.dist(L(yp.GetPosition()), L(cp.GetPosition())), 2)}
        parts_in = {}
        for r_ in (ref,) + caps:
            c = L(fps[r_].GetPosition())
            parts_in[r_] = XTAL_WINDOW[1] - 1.5 <= c[1] <= XTAL_WINDOW[3] + 2.5 and c[0] <= XTAL_WINDOW[2]
        xt[name] = {"nets": d, "near_window": parts_in}
    R["crystals"] = xt

    # ---- switcher loops
    loops = {}
    for name, items in LOOPS.items():
        out = []
        for what, ra, pa, rb, net in items:
            a = L(pad(ra, pa).GetPosition()) if pa else None
            if ra == "D701":
                a = L(net_pad("D701", net)[0].GetPosition())
            bpads = net_pad(rb, net)
            b = min((L(p.GetPosition()) for p in bpads), key=lambda q: math.dist(a, q))
            out.append((what, "%s-%s" % (ra, rb), round(math.dist(a, b), 2)))
        loops[name] = out
    R["loops"] = loops

    # ---- buses (Manhattan ball to the far pad)
    buses = {}
    for bus, (nets, far, lmax, spread) in BUSES.items():
        rows = []
        for n in nets:
            bp = net_pad("U201", n)
            fp_ = net_pad(far, n)
            if not bp or not fp_:
                rows.append((n, None))
                continue
            a, b = L(bp[0].GetPosition()), L(fp_[0].GetPosition())
            rows.append((n, round(abs(a[0] - b[0]) + abs(a[1] - b[1]), 1)))
        vals = [v for _, v in rows if v is not None]
        over = [n for n, v in rows if v is not None and ((lmax and v > lmax) or (n in NET_LIMIT and v > NET_LIMIT[n]))]
        buses[bus] = {"to": far, "min": min(vals), "max": max(vals), "spread": round(max(vals) - min(vals), 1),
                      "limit": lmax, "spread_limit": spread, "over": over, "nets": rows}
    R["buses"] = buses

    # ---- LCD fan: straight paths ball -> FPC pad of every net the MCU shares with J701; parts they cross; the
    # boost's switch node (pads of SW_BL) against the easternmost path
    def seg_box_dist(a, b, box):
        x0, y0, x1, y1 = box
        best = 1e9
        n = 60
        for k in range(n + 1):
            t = k / n
            p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            best = min(best, math.hypot(max(x0 - p[0], 0, p[0] - x1), max(y0 - p[1], 0, p[1] - y1)))
        return best
    mcu = {p.GetNetname(): L(p.GetPosition()) for p in fps["U201"].Pads() if p.GetNetname()}
    segs = [(n, mcu[n], L(p.GetPosition())) for p in fps["J701"].Pads() for n in [p.GetNetname()] if n in mcu and n != "GND"]
    crossed = []
    for f in board.GetFootprints():
        ref = f.GetReference()
        if ref in ("U201", "J701") or f.GetLayer() == pcbnew.B_Cu:
            continue
        cy = f.GetCourtyard(pcbnew.F_CrtYd).BBox()
        box = (ToMM(cy.GetLeft()) - OX, ToMM(cy.GetTop()) - OY, ToMM(cy.GetRight()) - OX, ToMM(cy.GetBottom()) - OY)
        if any(seg_box_dist(a, b, box) == 0 for _, a, b in segs):
            crossed.append(ref)
    sw = []
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() == "SW_BL":
                bb = p.GetBoundingBox()
                box = (ToMM(bb.GetLeft()) - OX, ToMM(bb.GetTop()) - OY, ToMM(bb.GetRight()) - OX, ToMM(bb.GetBottom()) - OY)
                sw.append((min(seg_box_dist(a, b, box) for _, a, b in segs), "%s.%s" % (f.GetReference(), p.GetNumber())))
    east = max(max(a[0], b[0]) for _, a, b in segs)
    R["lcd_fan"] = {"lines": len(segs), "east_x": round(east, 2), "parts_crossed": sorted(crossed),
                    "sw_node_min_dist": round(min(sw)[0], 2), "sw_node_nearest": min(sw)[1]}

    # ---- report
    tot = sum(v["pads"] for v in rails.values()); off = sum(len(v["off"]) for v in rails.values())
    print("[rails]     %d pads on copper-class nets with drawn regions, %d not on a region of their net%s" % (
        tot, off, "".join("\n            %s: %s" % (n, " ".join(v["off"])) for n, v in rails.items() if v["off"])))
    for name, v in xt.items():
        print("[crystal]   %s: %s; parts at the window: %s" % (name, ", ".join(
            "%s ball-crystal %.2f crystal-cap %.2f" % (n, d["ball_to_crystal"], d["crystal_to_cap"]) for n, d in v["nets"].items()),
            " ".join(k for k, ok in v["near_window"].items() if ok)))
    for name, v in loops.items():
        print("[loop]      %s: %s" % (name, ", ".join("%s %s %.2f" % x for x in v)))
    for bus, v in buses.items():
        print("[bus]       %-5s to %-4s Manhattan %5.1f .. %5.1f mm (spread %.1f)%s%s" % (
            bus, v["to"], v["min"], v["max"], v["spread"],
            ("; limit %g" % v["limit"]) + (", spread %g" % v["spread_limit"] if v["spread_limit"] else "") if v["limit"] else "",
            ("; OVER: " + " ".join(v["over"])) if v["over"] else ""))
    F = R["lcd_fan"]
    print("[lcd fan]   %d MCU-to-J701 lines, easternmost path x %.2f; switch node (SW_BL pads) %.2f mm from the nearest path (%s); "
          "parts whose courtyard a straight path crosses: %s" % (F["lines"], F["east_x"], F["sw_node_min_dist"],
                                                                 F["sw_node_nearest"], " ".join(F["parts_crossed"]) or "none"))
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w", encoding="utf-8") as f:
            json.dump(R, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
