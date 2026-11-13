"""Report the track shapes a layout reviewer objects to, which DRC does not see.

    D:\\KiCad\\bin\\python.exe scripts\\track_shape.py <board.kicad_pcb> [--bends N] [--within MM] [--chamfer MM]

Tracks are followed from one fixed point (pad, via, junction, track end) to the next, and
each such run is checked for:

  off-grid      a segment that is not at 0 / 45 / 90 degrees
  staircase     four or more consecutive segments shorter than 0.45 mm whose overall
                direction is off the grid (many tiny on-grid steps drawing a slanted line)
  crowded       N or more bends (default 3) within MM of track (default 2.0)
  tiny          a segment shorter than 0.1 mm
  sharp         a segment shorter than CHAMFER (default 0.35 mm, --chamfer MM) across which
                the track turns 90 degrees or more: two 45-degree corners so close together
                that they read as a right angle. DRC's track_angle compares neighbouring
                segments only and passes these.

Arcs are not counted as bends. Coordinates are local (board mm - 100). Exit code 0 always:
this is a report, the judgement is the reviewer's.
"""
import sys, math, collections
import pcbnew

args = sys.argv[1:]
NB = int(args[args.index("--bends") + 1]) if "--bends" in args else 3
WITHIN = float(args[args.index("--within") + 1]) if "--within" in args else 2.0
CHAMFER = float(args[args.index("--chamfer") + 1]) if "--chamfer" in args else 0.35
b = pcbnew.LoadBoard(args[0]); mm = pcbnew.ToMM
L = lambda v: (round(mm(v.x) - 100, 3), round(mm(v.y) - 100, 3))
segs = collections.defaultdict(list)
vias = collections.defaultdict(set)
arcs = 0
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        vias[t.GetNetname()].add(L(t.GetPosition()))
    elif t.Type() == pcbnew.PCB_ARC_T:
        arcs += 1
    else:
        segs[(t.GetNetname(), b.GetLayerName(t.GetLayer()))].append((L(t.GetStart()), L(t.GetEnd())))
pads = collections.defaultdict(list)
for fp in b.GetFootprints():
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        pads[p.GetNetname()].append((mm(bb.GetLeft()) - 100, mm(bb.GetTop()) - 100, mm(bb.GetRight()) - 100, mm(bb.GetBottom()) - 100))


def ang(a, c):
    return math.degrees(math.atan2(c[1] - a[1], c[0] - a[0])) % 180


def off(a, c):
    return min(abs(ang(a, c) - k) for k in (0, 45, 90, 135, 180))


rep = collections.defaultdict(list)
tiny = collections.Counter()
for (net, layer), ss in sorted(segs.items()):
    for a, c in ss:
        if off(a, c) > 0.2 and math.dist(a, c) > 0.05:
            rep["off-grid"].append(f"{net} {layer} {a} -> {c}: {ang(a, c):.1f} deg, {math.dist(a, c):.2f} mm")
        if math.dist(a, c) < 0.1 - 1e-6:
            tiny[net] += 1
    node = collections.defaultdict(list)
    for i, (a, c) in enumerate(ss):
        node[a].append(i); node[c].append(i)

    def fixed(p):
        return (len(node[p]) != 2 or p in vias[net]
                or any(r[0] <= p[0] <= r[2] and r[1] <= p[1] <= r[3] for r in pads[net]))

    seen = set()
    for start in [p for p in node if fixed(p)]:
        for i0 in node[start]:
            if i0 in seen:
                continue
            chain, p, i = [], start, i0
            while True:
                seen.add(i); a, c = ss[i]
                q = c if a == p else a
                chain.append((p, q)); p = q
                nxt = [j for j in node[p] if j not in seen]
                if fixed(p) or not nxt:
                    break
                i = nxt[0]
            k = 0
            while k < len(chain):
                j = k
                while j < len(chain) and math.dist(*chain[j]) < 0.45:
                    j += 1
                if j - k >= 4 and off(chain[k][0], chain[j - 1][1]) > 2:
                    a, c = chain[k][0], chain[j - 1][1]
                    rep["staircase"].append(f"{net} {layer} {a} -> {c}: {j - k} segments over {math.dist(a, c):.2f} mm at {ang(a, c):.1f} deg")
                k = max(j, k + 1)
            for k in range(1, len(chain) - 1):
                d = [math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) for p, q in (chain[k - 1], chain[k + 1])]
                turn = abs((d[1] - d[0] + 180) % 360 - 180)
                if math.dist(*chain[k]) < CHAMFER and turn > 89:
                    rep["sharp"].append(f"{net} {layer} at {chain[k][0]}: turns {turn:.0f} deg across a {math.dist(*chain[k]):.3f} mm segment")
            pos, bends = 0.0, []
            for k, (p0, p1) in enumerate(chain):
                if k and abs((ang(*chain[k - 1]) - ang(p0, p1) + 90) % 180 - 90) > 1:
                    bends.append((pos, p0))
                pos += math.dist(p0, p1)
            k = 0
            while k < len(bends):
                grp = [x for x in bends[k:] if x[0] - bends[k][0] <= WITHIN]
                if len(grp) >= NB:
                    rep["crowded"].append(f"{net} {layer} from {grp[0][1]}: {len(grp)} bends in {grp[-1][0] - grp[0][0]:.2f} mm")
                    k += len(grp)
                else:
                    k += 1
n_seg = sum(len(v) for v in segs.values())
print(f"{n_seg} segments, {arcs} arcs")
for kind in ("off-grid", "staircase", "sharp", "crowded"):
    print(f"{kind}: {len(rep[kind])}")
    for line in rep[kind]:
        print("   ", line)
print("tiny (< 0.1 mm):", sum(tiny.values()), dict(tiny))
