"""Survey of serpentine sites for the SDRAM bus (RTE-2): for every net that has to be lengthened, its straight pieces
outside the rule areas and the room beside them, read from the board file.

    python -m Tools.KiCadDesignTools.routing.tune_sites <board dir> [board] [--spread 5] [--margin 0.3] [--window 20]
                                                        [--natural <metrics.json>] [--json out.json]

board: default the board folder's own board file. board.toml [tune_sites]: layers (the SDRAM's signal layers), clock
(the clock's pieces, summed), addr (address / command nets), area_prefix (the rule areas the sites keep out of), box
(x0 y0 x1 y1: the board less the edge clearance); the byte lanes from [schematic.swap] (data_net, mask_net, lanes:
8 data bits and one mask per lane); [power] ground (its pours are no obstacle); the origin from [board] origin.
Lengths: track (arcs by their true length) plus the height between the layers a via joins (the via heights of the
board's stackup, Tools.KiCadDesignTools.core.stackup: KiCad 10's Python does not expose the stackup list);
--natural takes the lengths from a busroute metrics.json instead (its tuning "natural", i.e. without the
serpentines; e.g. out/route2/sdram/metrics.json).
Needs:
  byte lane k (D8k..D8k+7, NBLk): (longest of the lane - spread + margin) - length
  address / command against the clock C = the clock's pieces summed: the clock is aimed at (longest address - window +
  margin), each address at (that clock - window + margin); the clock's row is its pieces' straights (pitch 0.5 there).
For each straight of 2.5 mm or more at the outside width: per side, the largest gain of ONE block of equal humps
(pitch 0.3, clock 0.5; 0.7 mm kept at both ends, amplitude 0.5 to 2.0, RTE-2: n * (2a - 0.858 p)) that fits between
the foreign copper found there (0.19 mm kept), and the nets that limit it. Neighbours that also need length compete
for the same room: the table is a budget, not a plan. Coordinates are local mm (board mm - origin). Run it on a build
without the serpentines (the routes file with NOTUNE=1).
"""
import sys, math, json, re, os
import pcbnew

from Tools.KiCadDesignTools.core import config, stackup

KEEP, CLR, AMAX, REACH = 0.7, 0.19, 2.0, 2.3


def dseg(px, py, s):
    x1, y1, x2, y2 = s[:4]
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - x1 - t * dx, py - y1 - t * dy)


def block_gain(prof, P):
    """prof = [(station, amax)] every 0.2 mm. Best single block: (gain, s0, s1, a, n)."""
    best = (0, 0, 0, 0, 0)
    for h in (0.5, 0.6, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0):
        i = 0
        while i < len(prof):
            if prof[i][1] >= h:
                j = i
                while j + 1 < len(prof) and prof[j + 1][1] >= h:
                    j += 1
                run = prof[j][0] - prof[i][0]
                n = int((run + 1e-9) / (2 * P))
                g = n * (2 * h - 0.858 * P)
                if n >= 1 and g > best[0]:
                    best = (g, prof[i][0], prof[j][0], h, n)
                i = j + 1
            else:
                i += 1
    return best


def main(argv):
    if not argv or argv[0].startswith("--"):
        print(__doc__)
        return 2
    cfg = config.load(argv[0])
    argv = argv[1:]
    ts = cfg.need("tune_sites")
    OX, OY = cfg.origin
    A = [a for a in argv if a.endswith(".kicad_pcb")]

    def opt(name, d):
        return float(argv[argv.index(name) + 1]) if name in argv else d
    BOARD = A[0] if A else cfg.pcb
    SPREAD, MARGIN, WINDOW = opt("--spread", 5.0), opt("--margin", 0.3), opt("--window", 20.0)
    CLOCK = list(ts["clock"])
    ADDR = list(ts["addr"])
    GND = cfg.need("power.ground")
    BOX = ts["box"]
    mm = pcbnew.ToMM
    b = pcbnew.LoadBoard(os.path.abspath(BOARD))
    LAY = {getattr(pcbnew, cfg.kicad(L).replace(".", "_")): L for L in ts["layers"]}
    BOTTOM = cfg.layers[-1]
    BOTTOM_ID = getattr(pcbnew, BOTTOM.kicad.replace(".", "_"))
    loc = lambda v: (mm(v.x) - OX, mm(v.y) - OY)

    segs, circ, rect, zones = {l: [] for l in LAY.values()}, {l: [] for l in LAY.values()}, {l: [] for l in LAY.values()}, {l: [] for l in LAY.values()}
    LEN, ends = {}, {}
    for t in b.GetTracks():
        n = t.GetNetname()
        if t.Type() == pcbnew.PCB_VIA_T:
            x, y = loc(t.GetPosition())
            for l in LAY.values():
                circ[l].append((x, y, mm(t.GetWidth(pcbnew.F_Cu)) / 2, n))
            continue
        l = LAY.get(t.GetLayer())
        if t.GetLayer() not in LAY and t.GetLayer() != BOTTOM_ID:
            continue
        LEN[n] = LEN.get(n, 0.0) + mm(t.GetLength())
        for p in (loc(t.GetStart()), loc(t.GetEnd())):
            ends.setdefault((n, round(p[0], 3), round(p[1], 3)), set()).add(l or BOTTOM.L)
        if l and t.Type() != pcbnew.PCB_ARC_T:                  # arcs: length only; their room is not a site
            (x1, y1), (x2, y2) = loc(t.GetStart()), loc(t.GetEnd())
            segs[l].append((x1, y1, x2, y2, mm(t.GetWidth()), n))
        elif l:
            (x1, y1), (x2, y2) = loc(t.GetStart()), loc(t.GetEnd())
            mx, my = loc(t.GetMid())
            segs[l] += [(x1, y1, mx, my, mm(t.GetWidth()), n), (mx, my, x2, y2, mm(t.GetWidth()), n)]
    for fp in b.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            r = (mm(bb.GetLeft()) - OX, mm(bb.GetTop()) - OY, mm(bb.GetRight()) - OX, mm(bb.GetBottom()) - OY, p.GetNetname() or fp.GetReference())
            for lid, l in LAY.items():
                if p.IsOnLayer(lid):
                    rect[l].append(r)
    areas = []
    for z in b.Zones():
        if z.GetIsRuleArea():
            if z.GetZoneName().startswith(ts["area_prefix"]):
                bb = z.GetBoundingBox()
                areas.append((mm(bb.GetLeft()) - OX, mm(bb.GetTop()) - OY, mm(bb.GetRight()) - OX, mm(bb.GetBottom()) - OY, z.GetZoneName()))
            continue
        if z.GetNetname() == GND:
            continue
        for lid, l in LAY.items():
            if z.IsOnLayer(lid):
                zones[l].append((z.Outline(), z.GetNetname()))

    # via heights from the stackup (copper layer centre heights): the board's stackup file, as KiCad adds them
    st = stackup.for_board(cfg)
    top = cfg.layers[0]
    Z = {L: (0.0 if L == top.L else st.via_height(top.kicad, cfg.kicad(L))) for L in [top.L] + [L for L in LAY.values() if L != top.L] + [BOTTOM.L]}
    try:
        st = b.GetDesignSettings().GetStackupDescriptor()
        z, zs = 0.0, {}
        for it in st.GetList():
            if it.GetType() == pcbnew.BS_ITEM_TYPE_COPPER:
                zs[it.GetBrdLayerId()] = z + mm(it.GetThickness()) / 2
            if it.GetType() in (pcbnew.BS_ITEM_TYPE_COPPER, pcbnew.BS_ITEM_TYPE_DIELECTRIC):
                z += sum(mm(it.GetThickness(i)) for i in range(it.GetSublayersCount()))
        z0 = zs[pcbnew.F_Cu]
        Z = {L: zs[lid] - z0 for lid, L in list(LAY.items()) + [(BOTTOM_ID, BOTTOM.L)]}
    except Exception:                                       # KiCad 10's Python does not expose the stackup list
        pass
    vias = {(round(c[0], 3), round(c[1], 3)) for c in circ[top.L]}
    for (n, x, y), ls in ends.items():
        if len(ls) > 1 and (x, y) in vias:
            zz = [Z[l] for l in ls]
            LEN[n] = LEN.get(n, 0) + max(zz) - min(zz)
    src = "board (tracks, arcs, via heights)"
    if "--natural" in argv:
        m = json.load(open(argv[argv.index("--natural") + 1], encoding="utf-8"))
        nat = (m.get("tuning") or {}).get("natural") or {n: v["length"] for n, v in m["length"]["nets"].items()}
        LEN.update(nat)
        src = "natural lengths of " + argv[argv.index("--natural") + 1]

    sw = cfg.need("schematic.swap")
    lanes = {"lane%d" % k: ["%s%d" % (sw["data_net"], i) for i in range(8 * k, 8 * k + 8)] + ["%s%d" % (sw["mask_net"], k)] for k in range(sw["lanes"])}
    need, target, group = {}, {}, {}
    for g, ns in lanes.items():
        mx = max(LEN[n] for n in ns)
        target[g] = mx - SPREAD + MARGIN
        for n in ns:
            group[n] = g
            if LEN[n] < target[g] - 1e-6:
                need[n] = target[g] - LEN[n]
    clk = sum(LEN[n] for n in CLOCK)
    amax = max(ADDR, key=lambda n: LEN[n])
    clk_t = max(clk, LEN[amax] - WINDOW + MARGIN)
    target["clock"], target["addr"] = clk_t, clk_t - WINDOW + MARGIN
    for n in CLOCK:
        group[n] = "clock"
        if clk_t > clk + 1e-6:
            need[n] = clk_t - clk                               # shared by the two pieces
    for n in ADDR:
        group[n] = "addr"
        if LEN[n] < target["addr"] - 1e-6:
            need[n] = target["addr"] - LEN[n]

    def room(layer, net, px, py, nx, ny, obs):
        """Largest t (<= REACH) so that the centre line may go to p + n*t: copper edge (0.0508) + CLR clear of everything."""
        S, C, R, ZN = obs
        t, blocker = 0.0, None
        while t < REACH:
            t2 = t + 0.05
            x, y = px + nx * t2, py + ny * t2
            hit = None
            for s in S:
                if dseg(x, y, s) < s[4] / 2 + 0.0508 + CLR:
                    hit = s[5]; break
            if not hit:
                for c in C:
                    if math.hypot(x - c[0], y - c[1]) < c[2] + 0.0508 + CLR:
                        hit = c[3] + "(via)"; break
            if not hit:
                for r in R:
                    ddx = max(r[0] - x, 0, x - r[2]); ddy = max(r[1] - y, 0, y - r[3])
                    if math.hypot(ddx, ddy) < 0.0508 + CLR:
                        hit = r[4] + "(pad)"; break
            if not hit:
                for r in areas:
                    ddx = max(r[0] - x, 0, x - r[2]); ddy = max(r[1] - y, 0, y - r[3])
                    if math.hypot(ddx, ddy) < 0.0508 + 0.127:
                        hit = r[4]; break
            if not hit:
                for o, zn in ZN:
                    if o.Contains(pcbnew.VECTOR2I(pcbnew.FromMM(x + OX), pcbnew.FromMM(y + OY)), -1, pcbnew.FromMM(0.0508 + 0.2)):
                        hit = zn + "(zone)"; break
            if not hit and not (BOX[0] < x < BOX[2] and BOX[1] < y < BOX[3]):
                hit = "edge"
            if hit:
                return t, hit
            t = t2
        return REACH, None

    def in_area(x, y):
        return any(r[0] <= x <= r[2] and r[1] <= y <= r[3] for r in areas)

    ORDER = list(lanes) + ["clock", "addr"]
    out = []
    for net in sorted(need, key=lambda n: (ORDER.index(group[n]), [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", n)])):
        P = 0.5 if net in CLOCK else 0.3
        rows = []
        for l in LAY.values():
            for s in segs[l]:
                if s[5] != net or s[4] < 0.1:
                    continue
                x1, y1, x2, y2 = s[:4]
                L = math.hypot(x2 - x1, y2 - y1)
                if L < 2.5 or (in_area(x1, y1) and in_area(x2, y2) and in_area((x1 + x2) / 2, (y1 + y2) / 2)):
                    continue
                ux, uy = (x2 - x1) / L, (y2 - y1) / L
                bx0, by0, bx1, by1 = min(x1, x2) - 3, min(y1, y2) - 3, max(x1, x2) + 3, max(y1, y2) + 3
                inb = lambda x, y: bx0 <= x <= bx1 and by0 <= y <= by1
                obs = ([o for o in segs[l] if o[5] != net and (inb(o[0], o[1]) or inb(o[2], o[3]) or dseg((x1 + x2) / 2, (y1 + y2) / 2, o) < L / 2 + 3)],
                       [c for c in circ[l] if c[3] != net and inb(c[0], c[1])] + [(c[0], c[1], c[2], net) for c in circ[l] if c[3] == net and inb(c[0], c[1]) and min(math.hypot(c[0] - x1, c[1] - y1), math.hypot(c[0] - x2, c[1] - y2)) > 0.01],
                       [r for r in rect[l] if r[4] != net and r[2] >= bx0 and r[0] <= bx1 and r[3] >= by0 and r[1] <= by1],
                       zones[l])
                res = {}
                for side, (nx, ny) in (("R", (-uy, ux)), ("L", (uy, -ux))):
                    prof, blk = [], {}
                    st = KEEP
                    while st <= L - KEEP + 1e-9:
                        t, h = room(l, net, x1 + ux * st, y1 + uy * st, nx, ny, obs)
                        prof.append((st, min(AMAX, t)))
                        if h:
                            blk[h] = blk.get(h, 0) + 1
                        st += 0.2
                    g = block_gain(prof, P)
                    res[side] = (g, sorted(blk, key=lambda k: -blk[k])[:3])
                rows.append((l, (round(x1, 2), round(y1, 2)), (round(x2, 2), round(y2, 2)), round(L, 2), res))
        cap = sum(max(r[4]["R"][0][0], r[4]["L"][0][0]) for r in rows)
        out.append(dict(net=net, group=group[net], length=round(LEN[net], 3), need=round(need[net], 2), cap_alone=round(cap, 1), straights=[
            dict(layer=r[0], a=r[1], b=r[2], len=r[3], **{sd: dict(gain=round(r[4][sd][0][0], 1), s0=round(r[4][sd][0][1], 1), s1=round(r[4][sd][0][2], 1),
                 amp=r[4][sd][0][3], n=r[4][sd][0][4], limits=r[4][sd][1]) for sd in "RL"}) for r in rows]))

    l1, l3, l4 = ts["layers"][:3]
    print("lengths: %s; via heights %s-%s %.4f, %s-%s %.4f, %s-%s %.4f" % (src, l1, l3, Z[l3], l1, l4, Z[l4], l3, l4, Z[l4] - Z[l3]))
    print("targets: " + "  ".join("%s %.2f" % (k, target[k]) for k in ORDER) + "   (clock now %.3f, longest address %s %.3f)" % (clk, amax, LEN[amax]))
    print("total need %.1f mm, %d nets (the clock's need counted once)" % (sum(v for n, v in need.items() if n != CLOCK[0]), len(need)))
    for o in out:
        print("%-11s %-5s len %6.2f need %5.2f  capacity alone %5.1f %s" % (o["net"], o["group"], o["length"], o["need"], o["cap_alone"], "" if o["cap_alone"] >= o["need"] else "  << SHORT"))
        for s in o["straights"]:
            print("    %s %s-%s %.2f mm | R +%.1f (%dx%.2f @%.1f-%.1f) %s | L +%.1f (%dx%.2f @%.1f-%.1f) %s" % (
                s["layer"], s["a"], s["b"], s["len"], s["R"]["gain"], s["R"]["n"], s["R"]["amp"], s["R"]["s0"], s["R"]["s1"], ",".join(s["R"]["limits"]),
                s["L"]["gain"], s["L"]["n"], s["L"]["amp"], s["L"]["s0"], s["L"]["s1"], ",".join(s["L"]["limits"])))
    if "--json" in argv:
        json.dump(out, open(argv[argv.index("--json") + 1], "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
