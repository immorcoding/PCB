"""Survey of serpentine sites for the SDRAM byte lanes (stop 6, RTE-2): for every net that has to be lengthened,
its straight pieces outside the rule areas and the room beside them, read from the board file.

    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\tune_sites.py [board] [--spread 5] [--margin 0.3] [--json out.json]

need(net) = (longest of its lane - spread + margin) - its length. For each straight of 2.5 mm or more at the outside
width: per side, the largest gain of ONE block of equal humps (pitch 0.3, 0.7 mm kept at both ends, amplitude 0.5 to
2.0, RTE-2: n * (2a - 0.858 p)) that fits between the foreign copper found there (0.19 mm kept), and the nets that
limit it. Neighbours that also need length compete for the same room: the table is a budget, not a plan.
Coordinates are local mm (board mm - 100).
"""
import sys, math, json, re, os
import pcbnew

A = [a for a in sys.argv[1:] if a.endswith(".kicad_pcb")]
def opt(name, d):
    return float(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else d
BOARD = A[0] if A else "stm32h743_sdram/stm32h743_sdram.kicad_pcb"
SPREAD, MARGIN = opt("--spread", 5.0), opt("--margin", 0.3)
P, KEEP, CLR, AMAX, REACH = 0.3, 0.7, 0.19, 2.0, 2.3
mm = pcbnew.ToMM
b = pcbnew.LoadBoard(os.path.abspath(BOARD))
LAY = {pcbnew.F_Cu: "L1", pcbnew.In3_Cu: "L4", pcbnew.B_Cu: "L6"}
loc = lambda v: (mm(v.x) - 100, mm(v.y) - 100)

segs, circ, rect, zones = {l: [] for l in LAY.values()}, {l: [] for l in LAY.values()}, {l: [] for l in LAY.values()}, {l: [] for l in LAY.values()}
length = {}
for t in b.GetTracks():
    n = t.GetNetname()
    if t.Type() == pcbnew.PCB_VIA_T:
        x, y = loc(t.GetPosition())
        for l in LAY.values():
            circ[l].append((x, y, mm(t.GetWidth(pcbnew.F_Cu)) / 2, n))
    else:
        l = LAY.get(t.GetLayer())
        if l:
            (x1, y1), (x2, y2) = loc(t.GetStart()), loc(t.GetEnd())
            segs[l].append((x1, y1, x2, y2, mm(t.GetWidth()), n))
for fp in b.GetFootprints():
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        r = (mm(bb.GetLeft()) - 100, mm(bb.GetTop()) - 100, mm(bb.GetRight()) - 100, mm(bb.GetBottom()) - 100, p.GetNetname() or fp.GetReference())
        for lid, l in LAY.items():
            if p.IsOnLayer(lid):
                rect[l].append(r)
areas = []
for z in b.Zones():
    if z.GetIsRuleArea():
        if z.GetZoneName().startswith("BGA_"):
            bb = z.GetBoundingBox()
            areas.append((mm(bb.GetLeft()) - 100, mm(bb.GetTop()) - 100, mm(bb.GetRight()) - 100, mm(bb.GetBottom()) - 100, z.GetZoneName()))
        continue
    if z.GetNetname() == "GND":
        continue
    for lid, l in LAY.items():
        if z.IsOnLayer(lid):
            zones[l].append((z.Outline(), z.GetNetname()))

# lengths as the project counts them: read from the last route1 table if present, else track length only
def net_lengths():
    L = {}
    for l in LAY.values():
        for s in segs[l]:
            L[s[5]] = L.get(s[5], 0) + math.hypot(s[2] - s[0], s[3] - s[1])
    return L
LEN = net_lengths()
VIAH = 1.3932 * 0 + 0.0            # via height is added below from the stackup spans actually crossed
# vias: add the height between the layers the net's tracks use at that via
Z = {"L1": 0.0, "L4": 1.3932, "L6": 1.6154}
try:
    st = b.GetDesignSettings().GetStackupDescriptor()
    z, zs, cu = 0.0, {}, 0
    for it in st.GetList():
        if it.GetType() == pcbnew.BS_ITEM_TYPE_COPPER:
            zs[it.GetBrdLayerId()] = z + mm(it.GetThickness()) / 2
        if it.GetType() in (pcbnew.BS_ITEM_TYPE_COPPER, pcbnew.BS_ITEM_TYPE_DIELECTRIC):
            z += sum(mm(it.GetThickness(i)) for i in range(it.GetSublayersCount()))
    Z = {l: zs[lid] for lid, l in LAY.items()}
except Exception as e:
    print("stackup not read (%s): default layer heights" % e)
for l0 in LAY.values():
    pass
ends = {}
for l in LAY.values():
    for s in segs[l]:
        for p in ((s[0], s[1]), (s[2], s[3])):
            ends.setdefault((s[5], round(p[0], 3), round(p[1], 3)), set()).add(l)
for (n, x, y), ls in ends.items():
    if len(ls) > 1 and any(abs(c[0] - x) < 1e-3 and abs(c[1] - y) < 1e-3 for c in circ["L1"]):
        zz = [Z[l] for l in ls]
        LEN[n] = LEN.get(n, 0) + max(zz) - min(zz)

lanes = {k: ["FMC_D%d" % i for i in range(8 * k, 8 * k + 8)] + ["FMC_NBL%d" % k] for k in range(4)}
need, target = {}, {}
for k, ns in lanes.items():
    mx = max(LEN[n] for n in ns)
    target[k] = mx - SPREAD + MARGIN
    for n in ns:
        if LEN[n] < target[k] - 1e-6:
            need[n] = target[k] - LEN[n]


def dseg(px, py, s):
    x1, y1, x2, y2 = s[:4]
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - x1 - t * dx, py - y1 - t * dy)


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
                if o.Contains(pcbnew.VECTOR2I(pcbnew.FromMM(x + 100), pcbnew.FromMM(y + 100)), -1, pcbnew.FromMM(0.0508 + 0.2)):
                    hit = zn + "(zone)"; break
        if not hit and not (0.3 < x < 84.7 and 0.3 < y < 74.7):
            hit = "edge"
        if hit:
            return t, hit
        t = t2
    return REACH, None


def block_gain(prof):
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


out = []
for net in sorted(need, key=lambda n: (int(re.sub(r"\D", "", n) or 0) // 8 if "NBL" not in n else int(n[-1]), n)):
    rows = []
    for l in LAY.values():
        for s in segs[l]:
            if s[5] != net or s[4] < 0.1:
                continue
            x1, y1, x2, y2 = s[:4]
            L = math.hypot(x2 - x1, y2 - y1)
            if L < 2.5:
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
                g = block_gain(prof)
                res[side] = (g, sorted(blk, key=lambda k: -blk[k])[:3])
            rows.append((l, (round(x1, 2), round(y1, 2)), (round(x2, 2), round(y2, 2)), round(L, 2), res))
    cap = sum(max(r[4]["R"][0][0], r[4]["L"][0][0]) for r in rows)
    out.append(dict(net=net, length=round(LEN[net], 3), need=round(need[net], 2), cap_alone=round(cap, 1), straights=[
        dict(layer=r[0], a=r[1], b=r[2], len=r[3], **{sd: dict(gain=round(r[4][sd][0][0], 1), s0=round(r[4][sd][0][1], 1), s1=round(r[4][sd][0][2], 1),
             amp=r[4][sd][0][3], n=r[4][sd][0][4], limits=r[4][sd][1]) for sd in "RL"}) for r in rows]))

print("targets: " + "  ".join("lane%d %.2f" % (k, target[k]) for k in target) + "   total need %.1f mm, %d nets" % (sum(need.values()), len(need)))
for o in out:
    print("%-9s len %.2f need %5.2f  capacity alone %5.1f %s" % (o["net"], o["length"], o["need"], o["cap_alone"], "" if o["cap_alone"] >= o["need"] else "  << SHORT"))
    for s in o["straights"]:
        print("    %s %s-%s %.2f mm | R +%.1f (%dx%.2f @%.1f-%.1f) %s | L +%.1f (%dx%.2f @%.1f-%.1f) %s" % (
            s["layer"], s["a"], s["b"], s["len"], s["R"]["gain"], s["R"]["n"], s["R"]["amp"], s["R"]["s0"], s["R"]["s1"], ",".join(s["R"]["limits"]),
            s["L"]["gain"], s["L"]["n"], s["L"]["amp"], s["L"]["s0"], s["L"]["s1"], ",".join(s["L"]["limits"])))
if "--json" in sys.argv:
    json.dump(out, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)
