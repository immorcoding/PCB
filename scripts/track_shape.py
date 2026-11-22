"""Report the track shapes a layout reviewer objects to, which DRC does not see.

    D:\\KiCad\\bin\\python.exe scripts\\track_shape.py <board.kicad_pcb> [--bends N] [--within MM] [--chamfer MM]

Tracks are followed from one fixed point (pad, via, junction, track end) to the next, and
each such run is checked for:

  off-grid      a segment that is not at 0 / 45 / 90 degrees
  staircase     four or more consecutive segments shorter than 0.45 mm whose overall
                direction is off the grid (many tiny on-grid steps drawing a slanted line)
  crowded       N or more bends (default 3) within MM of track (default 2.0)
  tiny          a segment (or an arc) shorter than 0.1 mm
  sharp         a segment shorter than CHAMFER (default 0.35 mm, --chamfer MM) across which
                the track turns 90 degrees or more: two 45-degree corners so close together
                that they read as a right angle. DRC's track_angle compares neighbouring
                segments only and passes these.

Arcs (serpentines) are part of the runs. An arc is not a bend; a joint where the direction changes
(between two segments, or a segment and an arc that do not meet tangentially) is. For `sharp`, the
turn across a short segment is taken from the start of the piece before it to the end of the piece
after it, so a corner followed within CHAMFER by an arc that turns on the same way is reported; a
short segment between two tangent arcs (a serpentine leg) is not, as long as neither end is a
corner. When the board has arcs, one more line counts the arc joints that are not tangent (> 1 degree).
Coordinates are local (board mm - 100). Exit code 0 always: this is a report, the judgement is the reviewer's.
"""
import sys, math, collections
import pcbnew

args = sys.argv[1:]
NB = int(args[args.index("--bends") + 1]) if "--bends" in args else 3
WITHIN = float(args[args.index("--within") + 1]) if "--within" in args else 2.0
CHAMFER = float(args[args.index("--chamfer") + 1]) if "--chamfer" in args else 0.35
TANGENT = 1.0                                                        # degrees: an arc joint within this is tangent
b = pcbnew.LoadBoard(args[0]); mm = pcbnew.ToMM
L = lambda v: (round(mm(v.x) - 100, 4), round(mm(v.y) - 100, 4))     # 0.1 um: the grid busroute draws on
L6 = lambda v: (mm(v.x) - 100, mm(v.y) - 100)
segs = collections.defaultdict(list)
arcs_by = collections.defaultdict(list)                              # (net, layer) -> [(start, end, (start, mid, end) exact)]
vias = collections.defaultdict(set)
arcs = 0
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        vias[t.GetNetname()].add(L(t.GetPosition()))
    elif t.Type() == pcbnew.PCB_ARC_T:
        arcs += 1
        arcs_by[(t.GetNetname(), b.GetLayerName(t.GetLayer()))].append((L(t.GetStart()), L(t.GetEnd()), (L6(t.GetStart()), L6(t.GetMid()), L6(t.GetEnd()))))
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


def circle(s, m, e):
    """(centre, radius, start angle, signed sweep) of the arc through s, m, e."""
    d = 2 * (s[0] * (m[1] - e[1]) + m[0] * (e[1] - s[1]) + e[0] * (s[1] - m[1]))
    if abs(d) < 1e-15:                                               # degenerate (straight) arc: no turning
        return s, math.dist(s, e) / 2, 0.0, 0.0
    ux =((s[0] ** 2 + s[1] ** 2) * (m[1] - e[1]) + (m[0] ** 2 + m[1] ** 2) * (e[1] - s[1]) + (e[0] ** 2 + e[1] ** 2) * (s[1] - m[1])) / d
    uy = ((s[0] ** 2 + s[1] ** 2) * (e[0] - m[0]) + (m[0] ** 2 + m[1] ** 2) * (s[0] - e[0]) + (e[0] ** 2 + e[1] ** 2) * (m[0] - s[0])) / d
    a0, am, a1 = (math.atan2(p[1] - uy, p[0] - ux) for p in (s, m, e))
    sw = (a1 - a0) % (2 * math.pi)
    if (am - a0) % (2 * math.pi) > sw:
        sw -= 2 * math.pi
    return (ux, uy), math.hypot(s[0] - ux, s[1] - uy), a0, sw


def L_(p):
    return (round(p[0], 4), round(p[1], 4))


def arc_run(item):
    """(start angle, signed sweep) of an arc item in the direction the run goes through it."""
    a, c, (s, m, e) = item
    _, _, a0, sw = circle(s, m, e)
    if math.dist(a, L_(s)) > 1e-6:                                  # the run enters at the arc's end
        a0, sw = a0 + sw, -sw
    return a0, sw


def heading(item, at_start):
    """Travel direction in degrees of a run item (p, q, arc) at its start (at_start) or at its end."""
    a, c, arc = item
    if arc is None:
        return math.degrees(math.atan2(c[1] - a[1], c[0] - a[0]))
    a0, sw = arc_run(item)
    t = a0 if at_start else a0 + sw
    sg = 1 if sw > 0 else -1
    return math.degrees(math.atan2(sg * math.cos(t), -sg * math.sin(t)))


def sweep(item):
    return 0.0 if item[2] is None else math.degrees(arc_run(item)[1])


def turn_deg(h1, h2):
    return (h2 - h1 + 180) % 360 - 180


def length(item):
    a, c, arc = item
    if arc is None:
        return math.dist(a, c)
    _, r, _, sw = circle(*arc)
    return r * abs(sw)


rep = collections.defaultdict(list)
tiny = collections.Counter()
for key in sorted(set(segs) | set(arcs_by)):
    net, layer = key
    ss = segs[key]
    for a, c in ss:
        if off(a, c) > 0.2 and math.dist(a, c) > 0.05:
            rep["off-grid"].append(f"{net} {layer} {a} -> {c}: {ang(a, c):.1f} deg, {math.dist(a, c):.2f} mm")
        if math.dist(a, c) < 0.1 - 1e-6:
            tiny[net] += 1
    edges = [(a, c, None) for a, c in ss] + list(arcs_by.get(key, []))
    for e in edges[len(ss):]:                                        # arcs
        if length(e) < 0.1 - 1e-6:
            tiny[net] += 1
    node = collections.defaultdict(list)
    for i, (a, c, _) in enumerate(edges):
        node[a].append(i); node[c].append(i)

    def fixed(p):
        return (len(node[p]) != 2 or p in vias[net]
                or any(r[0] <= p[0] <= r[2] and r[1] <= p[1] <= r[3] for r in pads[net]))

    seen = set()
    for start in [p for p in node if fixed(p)]:
        for i0 in node[start]:
            if i0 in seen:
                continue
            chain, items, p, i = [], [], start, i0
            while True:
                seen.add(i); a, c, arc = edges[i]
                q = c if a == p else a
                chain.append((p, q)); items.append((p, q, arc)); p = q
                nxt = [j for j in node[p] if j not in seen]
                if fixed(p) or not nxt:
                    break
                i = nxt[0]
            is_arc = [it[2] is not None for it in items]
            k = 0
            while k < len(chain):
                j = k
                while j < len(chain) and math.dist(*chain[j]) < 0.45 and not is_arc[j]:
                    j += 1
                if j - k >= 4 and off(chain[k][0], chain[j - 1][1]) > 2:
                    a, c = chain[k][0], chain[j - 1][1]
                    rep["staircase"].append(f"{net} {layer} {a} -> {c}: {j - k} segments over {math.dist(a, c):.2f} mm at {ang(a, c):.1f} deg")
                k = max(j, k + 1)
            joint = []                                               # joint[k - 1], between item k-1 and k: (corner?, signed turn deg)
            for k in range(1, len(items)):
                t = turn_deg(heading(items[k - 1], False), heading(items[k], True))
                if not is_arc[k - 1] and not is_arc[k]:
                    joint.append((True, t))
                else:
                    joint.append((abs(t) > TANGENT, t))
                    if abs(t) > TANGENT:
                        rep["arc-joint"].append(f"{net} {layer} at {items[k][0]}: an arc joint turns {abs(t):.1f} deg")
            for k in range(1, len(chain) - 1):
                if is_arc[k]:
                    continue
                if not is_arc[k - 1] and not is_arc[k + 1]:
                    d = [math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) for p, q in (chain[k - 1], chain[k + 1])]
                    turn = abs((d[1] - d[0] + 180) % 360 - 180)
                else:
                    if not (joint[k - 1][0] or joint[k][0]):
                        continue                                     # between two tangent arcs: a serpentine leg
                    turn = abs(sweep(items[k - 1]) + joint[k - 1][1] + joint[k][1] + sweep(items[k + 1]))
                if math.dist(*chain[k]) < CHAMFER and turn > 89:
                    rep["sharp"].append(f"{net} {layer} at {chain[k][0]}: turns {turn:.0f} deg across a {math.dist(*chain[k]):.3f} mm segment")
            pos, bends = 0.0, []
            for k, (p0, p1) in enumerate(chain):
                if k:
                    if not is_arc[k - 1] and not is_arc[k]:
                        if abs((ang(*chain[k - 1]) - ang(p0, p1) + 90) % 180 - 90) > 1:
                            bends.append((pos, p0))
                    elif joint[k - 1][0]:
                        bends.append((pos, p0))
                pos += length(items[k]) if is_arc[k] else math.dist(p0, p1)
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
if arcs:
    print(f"arc-joint: {len(rep['arc-joint'])}")
    for line in rep["arc-joint"]:
        print("   ", line)
