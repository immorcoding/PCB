"""Search the bottom-side positions of the BGA decoupling (SPEC 4, 6; LAY-2, LAY-5) on the SDRAM sketch board.

    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\decap_search.py [<board with the sketch tracks>]

Default board: out/sketch/rot0/stm32h743_sdram.kicad_pcb (written by the line-order build, constraint 1 of stop 4).
Prints PLACE entries (the old place.py table, now place.toml [parts]); place.toml stays the source (this script only proposes).

Rules it keeps, on L6 (B.Cu, where these parts sit):
  - pads clear of every L6 track and every via of another net: 0.10 mm inside the BGA rule areas (rule 0.09),
    0.13 mm outside (0.127), and 0.21 mm from a via hole (hole to copper 0.20); courtyards do not overlap
  - every ball of the BGA keeps at least one free via site (the four ball-gap points around it) that no
    pad of another net covers and no via or track of another net blocks: the power and ground balls need
    one for their dog-bone via, the inner signal balls for their escape (SPEC 7)
  - each 100 nF lands with its rail pad within 2.5 mm of a supply ball (LAY-2); greedy set cover: the next
    capacitor goes where it covers the most uncovered balls, ties broken by the short-track cost below; the
    capacitors left over go to the balls whose nearest capacitor is farthest
Cost of a position: distance rail pad - target ball, plus rail pad - nearest usable via site of a rail ball,
plus GND pad - nearest usable via site of a GND ball (the short leads to dog-bone vias of LAY-5).
"""
import math, os, sys
import pcbnew
from pcbnew import ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out", "sketch", "rot0", "stm32h743_sdram.kicad_pcb")
OX, OY = 100.0, 100.0
STEP = 0.05
CLR_IN, CLR_OUT = 0.10, 0.13
VIA_D, VIA_CLR, VIA_PITCH = 0.30, 0.09, 0.425      # small via in the rule areas; least centre distance to a foreign via
LIMIT = 2.5
HOLE_CLR = 0.21                                    # hole to copper 0.20 + 0.01
LIMIT_BULK = 5.0                                   # bulk parts (VCAP, 1 uF, bead): no LAY-2 limit, kept close

# what goes where: (refs, rail net, BGA ref); a cap may also go to any ball of its rail
# order matters (greedy): the single-ball rails first, the VDD capacitors have slack (worst 0.93 of 2.5 mm)
GROUPS = [
    (["C218"], "VCAP1", "U201", False),
    (["C219"], "VCAP2", "U201", False),
    (["C220", "C222"], "VDDA_MCU", "U201", True),
    (["C%d" % i for i in range(201, 216)], "+3V3_MCU", "U201", True),     # 100 nF, one per VDD ball
    (["C221", "C223"], "VDDA_MCU", "U201", False),
    (["C216"], "+3V3_MCU", "U201", False),                                  # 1 uF for VDD33USB, near any VDD ball
    (["FB201"], "VDDA_MCU", "U201", False),                                 # bead: +3V3_MCU pad to a VDD site
    (["C%d" % i for i in range(301, 309)], "+3V3_SDRAM", "U301", True),
]


def L(p):
    return (ToMM(p.x) - OX, ToMM(p.y) - OY)


def seg_rect_dist(a, b, r):
    """Distance from segment a-b to the axis-aligned rectangle r = (x0, y0, x1, y1); 0 when they meet."""
    x0, y0, x1, y1 = r
    def pr(p):
        dx = max(x0 - p[0], 0, p[0] - x1); dy = max(y0 - p[1], 0, p[1] - y1)
        return math.hypot(dx, dy)
    # sample-free exact enough: endpoints, the closest point of the segment to the rectangle centre, and corners
    best = min(pr(a), pr(b))
    for c in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        best = min(best, seg_pt(c, a, b))
    # crossing: a segment through the rectangle with both ends outside
    if best > 0:
        n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.05))
        for k in range(n + 1):
            t = k / n
            if pr((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)) == 0:
                return 0.0
    return best


def seg_pt(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    l2 = ax * ax + ay * ay
    t = 0 if l2 == 0 else max(0, min(1, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / l2))
    return math.hypot(p[0] - a[0] - t * ax, p[1] - a[1] - t * ay)


def rect_pt(r, p):
    return math.hypot(max(r[0] - p[0], 0, p[0] - r[2]), max(r[1] - p[1], 0, p[1] - r[3]))


class Grid:
    """Spatial hash of obstacles: ('seg', a, b, half width, net) and ('disc', c, radius, net)."""
    def __init__(self, cell=1.0):
        self.cell, self.d = cell, {}

    def keys(self, x0, y0, x1, y1):
        c = self.cell
        for i in range(int(math.floor(x0 / c)), int(math.floor(x1 / c)) + 1):
            for j in range(int(math.floor(y0 / c)), int(math.floor(y1 / c)) + 1):
                yield (i, j)

    def add(self, ob):
        if ob[0] == "seg":
            _, a, b, hw, _n = ob
            box = (min(a[0], b[0]) - hw, min(a[1], b[1]) - hw, max(a[0], b[0]) + hw, max(a[1], b[1]) + hw)
        else:
            _, c, r, _n = ob
            box = (c[0] - r, c[1] - r, c[0] + r, c[1] + r)
        for k in self.keys(*box):
            self.d.setdefault(k, []).append(ob)

    def near(self, box, m):
        seen = set()
        for k in self.keys(box[0] - m, box[1] - m, box[2] + m, box[3] + m):
            for ob in self.d.get(k, ()):
                if id(ob) not in seen:
                    seen.add(id(ob))
                    yield ob


def main():
    board = pcbnew.LoadBoard(BOARD)
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    areas = []
    for z in board.Zones():
        if z.GetIsRuleArea() and z.GetZoneName().startswith("BGA_"):
            bb = z.GetBoundingBox()
            areas.append((ToMM(bb.GetLeft()) - OX, ToMM(bb.GetTop()) - OY, ToMM(bb.GetRight()) - OX, ToMM(bb.GetBottom()) - OY))
    in_area = lambda p: any(a[0] <= p[0] <= a[2] and a[1] <= p[1] <= a[3] for a in areas)

    # obstacles on L6 for pads, and on every layer for via sites
    l6, anyl = Grid(), Grid()
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            c, r = L(t.GetPosition()), ToMM(t.GetWidth(pcbnew.F_Cu)) / 2
            # hole to copper 0.20 binds before pad clearance: keep pads drill/2 + 0.21 from the centre
            r = max(r, ToMM(t.GetDrillValue()) / 2 + HOLE_CLR - CLR_IN)
            ob = ("disc", c, r, t.GetNetname())
            l6.add(ob); anyl.add(ob)
            continue
        ob = ("seg", L(t.GetStart()), L(t.GetEnd()), ToMM(t.GetWidth()) / 2, t.GetNetname())
        anyl.add(ob)
        if t.GetLayer() == pcbnew.B_Cu:
            l6.add(ob)
    top = Grid()              # LAY-5: no bottom pad under a top pad, except under the two BGAs
    for f in board.GetFootprints():
        if f.GetLayer() == pcbnew.F_Cu and f.GetReference() not in ("U201", "U301"):
            for p in f.Pads():
                if p.IsOnLayer(pcbnew.F_Cu):
                    bb = p.GetBoundingBox()
                    r = (ToMM(bb.GetLeft()) - OX, ToMM(bb.GetTop()) - OY, ToMM(bb.GetRight()) - OX, ToMM(bb.GetBottom()) - OY)
                    top.add(("disc", ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2), 0.0, None))
                    top.d.setdefault("rects", []).append(r)
    top_rects = top.d.pop("rects", [])
    top = Grid()
    for r in top_rects:
        top.add(("seg", (r[0], (r[1] + r[3]) / 2), (r[2], (r[1] + r[3]) / 2), (r[3] - r[1]) / 2, None))
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH or (f.GetLayer() == pcbnew.B_Cu and f.GetReference() not in sum((g[0] for g in GROUPS), [])
                                                              and abs(ToMM(f.GetPosition().x) - OX) < 90):
                bb = p.GetBoundingBox()
                ob = ("rect", (ToMM(bb.GetLeft()) - OX, ToMM(bb.GetTop()) - OY, ToMM(bb.GetRight()) - OX, ToMM(bb.GetBottom()) - OY), p.GetNetname())
                l6.add(("disc", ((ob[1][0] + ob[1][2]) / 2, (ob[1][1] + ob[1][3]) / 2),
                        max(ob[1][2] - ob[1][0], ob[1][3] - ob[1][1]) / 2, p.GetNetname()))

    # balls and their via sites
    balls = {}
    for ref in ("U201", "U301"):
        f = fps[ref]
        pts = [L(p.GetPosition()) for p in f.Pads()]
        pitch = min(abs(a[0] - b[0]) for a in pts for b in pts if abs(a[0] - b[0]) > 0.1)
        h = pitch / 2
        for p in f.Pads():
            n = p.GetNetname()
            if not n or n.startswith("unconnected"):
                continue
            c = L(p.GetPosition())
            balls[(ref, p.GetNumber())] = {"net": n, "xy": c, "sites": [(round(c[0] + sx * h, 4), round(c[1] + sy * h, 4))
                                                                         for sx in (-1, 1) for sy in (-1, 1)]}
    ball_pads = {}
    for (ref, num), b in balls.items():
        ball_pads.setdefault(b["xy"], b["net"])

    def site_free(s, net):
        """A via of `net` can stand at s: no foreign via closer than VIA_PITCH, no foreign track within
        via radius + clearance + its half width, on any layer; ball pads are 0.46 mm away and always clear."""
        box = (s[0], s[1], s[0], s[1])
        for ob in anyl.near(box, 0.6):
            if ob[-1] == net:
                continue
            if ob[0] == "disc" and math.dist(ob[1], s) < VIA_PITCH:
                return False
            if ob[0] == "seg" and seg_pt(s, ob[1], ob[2]) < VIA_D / 2 + VIA_CLR + ob[3]:
                return False
        return True

    for b in balls.values():
        b["free"] = [s for s in b["sites"] if site_free(s, b["net"])]

    placed_pads = []          # (rect, net) of the bottom pads chosen so far
    placed_cy = []            # courtyard rects
    out = {}

    templ = {}

    def template(f):
        """Pad offsets and sizes at orientation 0, and the courtyard size (read once per footprint). Bottom
        and top give the same pad positions for these two-pad parts at a given orientation (checked)."""
        ref = f.GetReference()
        if ref not in templ:
            o = f.GetOrientationDegrees()
            f.SetOrientationDegrees(0)
            pads = []
            for p in f.Pads():
                sz = p.GetSize(pcbnew.F_Cu)
                pads.append((ToMM(p.GetPosition().x - f.GetPosition().x), ToMM(p.GetPosition().y - f.GetPosition().y),
                             ToMM(sz.x), ToMM(sz.y), p.GetNetname()))
            cy = f.GetCourtyard(pcbnew.F_CrtYd if f.GetLayer() == pcbnew.F_Cu else pcbnew.B_CrtYd).BBox()
            f.SetOrientationDegrees(o)
            templ[ref] = (pads, (ToMM(cy.GetWidth()), ToMM(cy.GetHeight())))
        return templ[ref]

    def pad_rects(f, x, y, rot):
        """Pads of footprint f placed at (x, y) rot (degrees, 0 or 90): rects in local mm."""
        rs = []
        for ox_, oy_, w, h, net in template(f)[0]:
            if rot:
                ox_, oy_, w, h = oy_, -ox_, h, w
            rs.append(((x + ox_ - w / 2, y + oy_ - h / 2, x + ox_ + w / 2, y + oy_ + h / 2), net))
        return rs

    def court(f, x, y, rot):
        w, h = template(f)[1]
        if rot:
            w, h = h, w
        return (x - w / 2, y - h / 2, x + w / 2, y + h / 2)

    def legal(rects, cy):
        for r, net in rects:
            m = CLR_IN if in_area(((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)) else CLR_OUT
            for ob in l6.near(r, m + 0.5):
                if ob[-1] == net:
                    continue
                if ob[0] == "disc" and rect_pt(r, ob[1]) < ob[2] + m:
                    return False
                if ob[0] == "seg" and seg_rect_dist(ob[1], ob[2], r) < ob[3] + m:
                    return False
            for ob in top.near(r, 0.5):
                if seg_rect_dist(ob[1], ob[2], r) < ob[3]:
                    return False
            for pr_, pn in placed_pads:
                if pn != net and (max(pr_[0] - r[2], r[0] - pr_[2], pr_[1] - r[3], r[1] - pr_[3]) < m):
                    return False
        for c in placed_cy:
            if c[0] < cy[2] and cy[0] < c[2] and c[1] < cy[3] and cy[1] < c[3]:
                return False
        return True

    def covers(rects, s, net):
        """A pad of another net covers via site s (pad within via radius + clearance)."""
        return any(pn != net and rect_pt(r, s) < VIA_D / 2 + VIA_CLR for r, pn in rects)

    def keeps_sites(rects):
        allr = rects + placed_pads
        for b in balls.values():
            if not b["free"]:
                continue
            if any(rect_pt(r, s) < 1.0 for r, _ in rects for s in b["free"]):
                if all(covers(allr, s, b["net"]) for s in b["free"]):
                    return False
        return True

    def usable_sites(net):
        return [s for b in balls.values() if b["net"] == net for s in b["free"] if not covers(placed_pads, s, net)]

    report = []
    for refs, rail, bga, small in GROUPS:
        f0 = fps[refs[0]]
        targets = [b for (r, _), b in balls.items() if r == bga and b["net"] == rail]
        if rail == "VDDA_MCU" and refs[0] == "FB201":
            targets = [b for (r, _), b in balls.items() if r == bga and b["net"] in ("VDDA_MCU",)]
        lim = LIMIT if small else LIMIT_BULK
        xs = [b["xy"][0] for b in targets]; ys = [b["xy"][1] for b in targets]
        cand = []
        x = min(xs) - lim
        while x <= max(xs) + lim:
            y = min(ys) - lim
            while y <= max(ys) + lim:
                for rot in (0, 90):
                    cand.append((round(x, 3), round(y, 3), rot))
                y += STEP
            x += STEP
        nearest = {id(b): 99.0 for b in targets}
        for ref in refs:
            f = fps[ref]
            best = None
            rail_sites = usable_sites(rail if ref != "FB201" else "+3V3_MCU")
            gnd_sites = usable_sites("GND")
            other_sites = gnd_sites if ref != "FB201" else usable_sites("VDDA_MCU")
            scored = []
            for (x, y, rot) in cand:
                rects = pad_rects(f, x, y, rot)
                rp = [r for r, n in rects if n == rail]
                if not rp:
                    continue
                rc = ((rp[0][0] + rp[0][2]) / 2, (rp[0][1] + rp[0][3]) / 2)
                d = {id(b): math.dist(rc, b["xy"]) for b in targets}
                if min(d.values()) > lim:
                    continue
                other = [r for r, n in rects if n != rail][0]
                oc = ((other[0] + other[2]) / 2, (other[1] + other[3]) / 2)
                if small:
                    newly = sum(1 for b in targets if nearest[id(b)] > LIMIT and d[id(b)] <= LIMIT)
                    worst = max(min(nearest[id(b)], d[id(b)]) for b in targets)
                    key0 = (-newly, worst)
                else:
                    key0 = (0, 0)
                sr = min((math.dist(rc, s) for s in rail_sites), default=9)
                sg = min((math.dist(oc, s) for s in other_sites), default=9)
                cost = min(d.values()) + sr + sg
                scored.append((key0 + (round(cost, 3),), x, y, rot, rects, min(d.values()), sr, sg))
            scored.sort(key=lambda c: c[0])
            for key, x, y, rot, rects, dm, sr, sg in scored:
                cy = court(f, x, y, rot)
                if legal(rects, cy) and keeps_sites(rects):
                    best = (key, x, y, rot, rects, cy, dm, sr, sg)
                    break
            if best is None:
                report.append("%s: no legal position" % ref)
                continue
            key, x, y, rot, rects, cy, dmin, sr, sg = best
            placed_pads.extend(rects); placed_cy.append(cy)
            rp = [r for r, n in rects if n == rail][0]
            rc = ((rp[0] + rp[2]) / 2, (rp[1] + rp[3]) / 2)
            for b in targets:
                nearest[id(b)] = min(nearest[id(b)], math.dist(rc, b["xy"]))
            out[ref] = (x, y, rot)
            report.append("%-6s (%6.2f, %6.2f) rot %3d  rail pad to ball %.2f, to rail via site %.2f, other pad to its site %.2f"
                          % (ref, x, y, rot, dmin, sr, sg))
        if small:
            report.append("  %s %s: nearest capacitor per ball, worst %.2f mm, over %.1f: %d of %d" % (
                bga, rail, max(nearest.values()), LIMIT, sum(1 for v in nearest.values() if v > LIMIT), len(targets)))
    print("\n".join(report))
    lost = [k for k, b in balls.items() if b["free"] and all(covers(placed_pads, s, b["net"]) for s in b["free"])]
    none = [k for k, b in balls.items() if not b["free"]]
    print("balls with no free via site from the SDRAM sketch already: %d %s" % (len(none), " ".join("%s.%s" % k for k in sorted(none))))
    print("balls whose last free site a capacitor pad covers: %d %s" % (len(lost), " ".join("%s.%s" % k for k in lost)))
    print("\n    # PLACE entries (bottom side)")
    for ref, (x, y, rot) in out.items():
        print('    "%s": (%.2f, %.2f, %d, "B"),' % (ref, x, y, rot))


if __name__ == "__main__":
    main()
