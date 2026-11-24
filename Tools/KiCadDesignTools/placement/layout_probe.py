"""Placement checks of a board that are measured rather than routed (LAY-2 rails, LAY-3); the board's trials are
board.toml [probe].

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.placement.layout_probe <board dir> [--pcb <board>] [--json <out.json>]

Reads the board file and the copper sketch ([copper] sketch; nothing is written). Distances are straight lines between
pad centres (crystals, hot loops) or Manhattan lengths ball to pad (buses: an upper bound for a route without detours,
not counting the escape inside the BGA); they decide whether a part is close enough, not the routing.

  rails      every pad of a copper-class net that has drawn regions in the sketch: does a region of its net
             reach it (any of nine points spread over the pad inside the region) (outer-layer pour on its own side, or
             a region on the power layer ([layers] roles), which it reaches by a via). [probe] plane_net counts as
             covered where no power block (sketch region on the power layer) is.
  crystals   ball - crystal pad and crystal pad - load capacitor ([probe.crystals]); the crystal parts inside the L1
             window the SDRAM sketch keeps free ([probe] xtal_window, open to the west)
  loops      the high-current loops of the switchers ([probe.loops]): input capacitor to VIN and GND pins (bucks),
             switch pin - diode - output capacitor - GND pin (boost), switch pin - inductor
  buses      per bus and net: Manhattan ball to the far pad, against the limits ([probe.buses], [probe] net_limit)
  lcd fan    straight paths ball to connector pad of every net the MCU shares with [probe.lcd_fan] connector: the
             parts whose courtyard they cross, and how far the switch node ([probe.lcd_fan] switch_net pads) stays
             from them
"""
import json, math, os, sys
import pcbnew
from pcbnew import ToMM

from Tools.KiCadDesignTools.copper import cu_sketch
from Tools.KiCadDesignTools.core import config


def main(argv):
    if not argv or argv[0].startswith("--"):
        print(__doc__)
        return 2
    cfg = config.load(argv[0])
    argv = argv[1:]
    P = cfg.need("probe")
    PCB = cfg.pcb
    SKETCH = cfg.path(cfg.need("copper.sketch"))
    OX, OY = cfg.origin
    XTAL_WINDOW = P["xtal_window"]
    MCU, GND, PLANE = P["mcu"], P["ground"], P["plane_net"]
    LOOPS = {k: [tuple(x) for x in v] for k, v in P["loops"].items()}
    BUSES = {k: (v["nets"], v["to"], v.get("limit"), v.get("spread")) for k, v in P["buses"].items()}
    NET_LIMIT = P.get("net_limit", {})
    BY_NET = set(P.get("loop_pad_by_net", []))
    FAN_J, SW_NET = P["lcd_fan"]["connector"], P["lcd_fan"]["switch_net"]
    ol = cfg.datafile("place.toml")["outline"]
    BW, BH = ol["width"], ol["height"]
    NL = len(cfg.layers)
    power = [i + 1 for i, l in enumerate(cfg.layers) if l.role == "power"]
    via_layers = tuple(power)       # a pad reaches the power blocks by a via

    board = pcbnew.LoadBoard(argv[argv.index("--pcb") + 1] if "--pcb" in argv else PCB)
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    L = lambda v: (ToMM(v.x) - OX, ToMM(v.y) - OY)
    pad = lambda ref, num: next(p for p in fps[ref].Pads() if p.GetNumber() == num)
    net_pad = lambda ref, net: [p for p in fps[ref].Pads() if p.GetNetname() == net]
    R = {}

    # ---- rails against the sketch
    sk = cu_sketch.load_sketch(SKETCH, NL)
    drawn = {}
    for r in sk.regions:
        if not r.whole:
            drawn.setdefault(r.net, []).append(r)
    blocks = [r for r in sk.regions if r.layer in power and not r.whole]      # the power blocks (L5 since 2026-11-23)
    nm = lambda p: (int(round(p[0] * 1e6)), int(round(p[1] * 1e6)))
    def on(r, p):
        return cu_sketch.inside(nm(p), [r.pts]) >= 0          # 1 inside, 0 on the edge, -1 outside
    rails = {}
    for net in sorted(set(drawn) | {PLANE}):
        if net == GND:
            continue
        pads, off = 0, []
        for f in board.GetFootprints():
            c = L(f.GetPosition())
            if not (0 <= c[0] <= BW and 0 <= c[1] <= BH):
                continue
            side = NL if f.GetLayer() == pcbnew.B_Cu else 1
            for p in f.Pads():
                if p.GetNetname() != net:
                    continue
                pads += 1
                xy = L(p.GetPosition())
                bb = p.GetBoundingBox()
                x0, y0 = ToMM(bb.GetLeft()) - OX, ToMM(bb.GetTop()) - OY
                x1, y1 = ToMM(bb.GetRight()) - OX, ToMM(bb.GetBottom()) - OY
                pts = [(x0 + (x1 - x0) * i / 4, y0 + (y1 - y0) * j / 4) for i in (1, 2, 3) for j in (1, 2, 3)]
                if net == PLANE:
                    ok = not any(on(r, xy) for r in blocks)
                else:
                    ok = any(on(r, q) for r in drawn[net] if r.layer in (side,) + via_layers for q in pts)
                if not ok:
                    off.append("%s.%s" % (f.GetReference(), p.GetNumber()))
        rails[net] = {"pads": pads, "off": off}
    R["rails"] = rails

    # ---- crystals
    xt = {}
    for name, c_ in P["crystals"].items():
        ref, caps, balls = c_["ref"], tuple(c_["caps"]), tuple(c_["balls"])
        d = {}
        for b in balls:
            bp = pad(MCU, b)
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
            if ra in BY_NET:
                a = L(net_pad(ra, net)[0].GetPosition())
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
            bp = net_pad(MCU, n)
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

    # ---- LCD fan: straight paths ball -> FPC pad of every net the MCU shares with the connector; parts they cross;
    # the boost's switch node (pads of the switch net) against the easternmost path
    def seg_box_dist(a, b, box):
        x0, y0, x1, y1 = box
        best = 1e9
        n = 60
        for k in range(n + 1):
            t = k / n
            p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            best = min(best, math.hypot(max(x0 - p[0], 0, p[0] - x1), max(y0 - p[1], 0, p[1] - y1)))
        return best
    mcu = {p.GetNetname(): L(p.GetPosition()) for p in fps[MCU].Pads() if p.GetNetname()}
    segs = [(n, mcu[n], L(p.GetPosition())) for p in fps[FAN_J].Pads() for n in [p.GetNetname()] if n in mcu and n != GND]
    crossed = []
    for f in board.GetFootprints():
        ref = f.GetReference()
        if ref in (MCU, FAN_J) or f.GetLayer() == pcbnew.B_Cu:
            continue
        cy = f.GetCourtyard(pcbnew.F_CrtYd).BBox()
        box = (ToMM(cy.GetLeft()) - OX, ToMM(cy.GetTop()) - OY, ToMM(cy.GetRight()) - OX, ToMM(cy.GetBottom()) - OY)
        if any(seg_box_dist(a, b, box) == 0 for _, a, b in segs):
            crossed.append(ref)
    sw = []
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() == SW_NET:
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
    print("[lcd fan]   %d MCU-to-%s lines, easternmost path x %.2f; switch node (%s pads) %.2f mm from the nearest path (%s); "
          "parts whose courtyard a straight path crosses: %s" % (F["lines"], FAN_J, F["east_x"], SW_NET, F["sw_node_min_dist"],
                                                                 F["sw_node_nearest"], " ".join(F["parts_crossed"]) or "none"))
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w", encoding="utf-8") as f:
            json.dump(R, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
