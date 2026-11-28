"""PROTOTYPE (issue 52): how the official EVB1 feeds the RK3568's supplies. Reads the Allegro .brd with KiCad's
importer (in memory only: no save, no DRC, no fill) and prints JSON. Run it through core.heavy, one at a time:

    python ../survey/run_heavy.py 900 <log> D:\\KiCad\\bin\\python.exe evb1_power.py <board.brd> <out.json>

Coordinates in the output are in the SoC's own ball frame: mm from the package centre, x along row A from
column 1 to 28, y from row A to row AH (so they compare with our board, where the SoC is not turned).
"""
import collections, json, math, sys
import pcbnew

brd, out = sys.argv[1], sys.argv[2]
b = pcbnew.PCB_IO_MGR.Load(pcbnew.PCB_IO_MGR.ALLEGRO, brd)
MM = 1e-6
soc = max(b.GetFootprints(), key=lambda f: len(f.Pads()))
pads = {p.GetNumber(): p for p in soc.Pads()}
def xy(p):
    return (p.x * MM, p.y * MM)
a1, a28, ah1 = xy(pads["A1"].GetPosition()), xy(pads["A28"].GetPosition()), xy(pads["AH1"].GetPosition())
ah28 = xy(pads["AH28"].GetPosition())
cx, cy = (a1[0] + ah28[0]) / 2, (a1[1] + ah28[1]) / 2
def unit(a, c):
    d = math.dist(a, c)
    return ((c[0] - a[0]) / d, (c[1] - a[1]) / d)
ex, ey = unit(a1, a28), unit(a1, ah1)
def fr(p):
    return (round((p[0] - cx) * ex[0] + (p[1] - cy) * ex[1], 3), round((p[0] - cx) * ey[0] + (p[1] - cy) * ey[1], 3))
HALF = 9.5
def inside(q, grow=0.0):
    return abs(q[0]) <= HALF + grow and abs(q[1]) <= HALF + grow

layers = [b.GetLayerName(l) for l in b.GetEnabledLayers().CuStack()]
lname = lambda l: b.GetLayerName(l)
ballnet = {n: p.GetNetname() for n, p in pads.items()}
nets_on_soc = collections.Counter(ballnet.values())

res = {"soc": soc.GetReference(), "pads": len(pads), "layers": layers, "soc_rot": soc.GetOrientationDegrees(),
       "ballnet": ballnet}

# vias inside the package outline, by net: count, drill, pad
vias = collections.defaultdict(list)
tracks = collections.defaultdict(lambda: collections.defaultdict(float))
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        q = fr(xy(t.GetPosition()))
        if inside(q, 1.0):
            try:
                w = t.GetWidth(pcbnew.F_Cu) * MM
            except TypeError:
                w = t.GetWidth() * MM
            vias[t.GetNetname()].append((q[0], q[1], round(t.GetDrillValue() * MM, 3), round(w, 3)))
    else:
        s, e = fr(xy(t.GetStart())), fr(xy(t.GetEnd()))
        if inside(s, 1.0) and inside(e, 1.0):
            tracks[t.GetNetname()][lname(t.GetLayer())] += t.GetLength() * MM
res["vias"] = {n: v for n, v in vias.items()}
res["tracks_in_soc"] = {n: {l: round(x, 2) for l, x in d.items()} for n, d in tracks.items()}

# zones: every zone of a net that is on a SoC ball; its layer, outline box in the SoC frame, area, clearance
zones = []
for z in b.Zones():
    net = z.GetNetname()
    if net not in nets_on_soc:
        continue
    ol = z.Outline()
    pts = []
    for i in range(ol.OutlineCount()):
        o = ol.Outline(i)
        for k in range(o.PointCount()):
            pts.append(fr(xy(o.CPoint(k))))
    if not pts:
        continue
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    box = (min(xs), min(ys), max(xs), max(ys))
    if box[2] < -HALF - 12 or box[0] > HALF + 12 or box[3] < -HALF - 12 or box[1] > HALF + 12:
        continue
    d = {"net": net, "layers": [lname(l) for l in z.GetLayerSet().CuStack()], "box": box, "pts": len(pts),
         "outline_area": round(ol.Area() * MM * MM, 1), "filled": bool(z.IsFilled()),
         "covers_centre_of": []}
    try:
        d["clearance"] = round(z.GetLocalClearance().value() * MM, 3) if z.GetLocalClearance() is not None else None
    except Exception as e:      # the binding differs between versions
        d["clearance"] = repr(e)[:60]
    try:
        d["min_width"] = round(z.GetMinThickness() * MM, 3)
    except Exception:
        pass
    # which SoC balls of this net lie inside the outline
    n_in = 0
    for n, p in pads.items():
        if ballnet[n] == net and ol.Contains(p.GetPosition()):
            n_in += 1
    d["own_balls_inside"] = n_in
    d["poly"] = pts if len(pts) <= 60 else None
    zones.append(d)
res["zones"] = zones

# two-pad parts inside the outline: side, nets, position
caps = []
for f in b.GetFootprints():
    if len(f.Pads()) != 2:
        continue
    q = fr(xy(f.GetPosition()))
    if inside(q, 2.0):
        ns = sorted(p.GetNetname() for p in f.Pads())
        pp = [fr(xy(p.GetPosition())) for p in f.Pads()]
        caps.append({"ref": f.GetReference(), "side": lname(f.GetLayer()), "nets": ns, "at": q,
                     "pad_pitch": round(math.dist(pp[0], pp[1]), 3),
                     "pad_size": [round(f.Pads()[0].GetSize().x * MM, 3), round(f.Pads()[0].GetSize().y * MM, 3)] if hasattr(f.Pads()[0], "GetSize") else None})
res["two_pad_parts"] = caps
json.dump(res, open(out, "w", encoding="utf-8"), indent=1)
print("ok", len(pads), "pads;", sum(len(v) for v in vias.values()), "vias in outline;", len(zones), "zones;", len(caps), "two-pad parts")
