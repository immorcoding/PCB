"""PROTOTYPE (issue 59, throwaway): how the official EVB1 builds the DDR4 address/control/clock T-branch points.
Reads the Allegro .brd with KiCad's importer (in memory only: no save, no DRC, no fill) and writes JSON. Run it
through core.heavy, one at a time:

    python rk3568_ddr3_core/probes/survey/run_heavy.py 900 <log> D:\\KiCad\\bin\\python.exe evb1_tee.py <board.brd> <out.json>

Method: per net family (DDR4_X plus DDR4_X_A / DDR4_X_B, which the 0-ohm parts separate) a copper graph is built
from tracks (arc length for arcs), vias (all copper layers of the via) and pads; a 2-pad R is a zero-length edge.
Shortest path from the SoC ball to each DRAM ball; the branch point is the last node the two paths share.
Frame (stated in the output): "board" = KiCad import coords in mm (y down); "soc" = mm from the SoC package centre,
u along ball row A (column 1 -> 28), v from row A to row AH (as evb1_power.py). Distances are frame independent.
Not handled: a track joining another track mid-segment (not at a vertex) and copper zones/shapes as connections.
"""
import collections, heapq, json, math, re, statistics, sys
import pcbnew

brd, out = sys.argv[1], sys.argv[2]
b = pcbnew.PCB_IO_MGR.Load(pcbnew.PCB_IO_MGR.ALLEGRO, brd)
MM = 1e-6
cu = list(b.GetEnabledLayers().CuStack())
lname = lambda l: str(b.GetLayerName(l))
LAYERS = [lname(l) for l in cu]
lidx = {l: i for i, l in enumerate(cu)}
xy = lambda p: (p.x * MM, p.y * MM)
R3 = lambda v: round(v, 3)

fps = {f.GetReference(): f for f in b.GetFootprints()}
soc = fps["U1000"]
DRAMS = ["U3300", "U3301"]
spads = {p.GetNumber(): p for p in soc.Pads()}
a1, a28, ah1, ah28 = (xy(spads[k].GetPosition()) for k in ("A1", "A28", "AH1", "AH28"))
cx, cy = (a1[0] + ah28[0]) / 2, (a1[1] + ah28[1]) / 2
def unit(a, c):
    d = math.dist(a, c)
    return ((c[0] - a[0]) / d, (c[1] - a[1]) / d)
ex, ey = unit(a1, a28), unit(a1, ah1)
def socf(p):
    return ((p[0] - cx) * ex[0] + (p[1] - cy) * ex[1], (p[0] - cx) * ey[0] + (p[1] - cy) * ey[1])
ball_u = [socf(xy(p.GetPosition())) for p in soc.Pads() if re.match(r"^[A-Z]{1,2}\d+$", str(p.GetNumber())) and int(re.sub(r"\D", "", str(p.GetNumber()))) <= 28]
SOC_HALF = (max(abs(q[0]) for q in ball_u), max(abs(q[1]) for q in ball_u))

def rect_dist(p, lo, hi):
    dx = max(lo[0] - p[0], 0, p[0] - hi[0]); dy = max(lo[1] - p[1], 0, p[1] - hi[1])
    return math.hypot(dx, dy)

# ---- families
allnets = sorted(str(n) for n in b.GetNetsByName().keys())
base_re = re.compile(r"^DDR4_(A\d+(_\w+)?|ACTN|BA\d|BG0|BG1|CKE|CS0N|ODT0|RESETN|CLKP|CLKN)$")
bases = [n for n in allnets if base_re.match(n)]
fams = {}
for n in bases:
    fams[n] = [n] + [n + s for s in ("_A", "_B") if n + s in allnets]
net_to_fam = {m: n for n, ms in fams.items() for m in ms}

# ---- collect copper
vias_all, segs_all = [], []
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        try:
            w = t.GetWidth(cu[0]) * MM
        except TypeError:
            w = t.GetWidth() * MM
        lo, hi = lidx[t.TopLayer()], lidx[t.BottomLayer()]
        vias_all.append({"net": str(t.GetNetname()), "x": xy(t.GetPosition())[0], "y": xy(t.GetPosition())[1],
                         "pad": round(w, 3), "drill": round(t.GetDrillValue() * MM, 3), "l0": min(lo, hi), "l1": max(lo, hi)})
    else:
        s, e = xy(t.GetStart()), xy(t.GetEnd())
        segs_all.append({"net": str(t.GetNetname()), "layer": lidx.get(t.GetLayer(), -1), "s": s, "e": e,
                         "len": t.GetLength() * MM, "w": t.GetWidth() * MM, "arc": t.Type() == pcbnew.PCB_ARC_T})

def pad_info(f, p):
    ls = [lidx[l] for l in p.GetLayerSet().CuStack() if l in lidx]
    sz = p.GetSize()
    return {"ref": f.GetReference(), "num": str(p.GetNumber()), "net": str(p.GetNetname()), "pos": xy(p.GetPosition()),
            "size": [R3(sz.x * MM), R3(sz.y * MM)], "layers": ls}

# ---- per family graph
class G:
    def __init__(self):
        self.nodes = []          # (x, y, layer)
        self.adj = collections.defaultdict(list)   # n -> [(m, length, kind, info)]
        self.snap = []           # (x, y, r, kind, info, [layers]) for vias/pads
    def node(self, x, y, l, tol=0.004):
        for i, (nx, ny, nl) in enumerate(self.nodes):
            if nl == l and abs(nx - x) < tol and abs(ny - y) < tol:
                return i
        self.nodes.append((x, y, l)); return len(self.nodes) - 1
    def edge(self, a, c, ln, kind, info=None):
        self.adj[a].append((c, ln, kind, info)); self.adj[c].append((a, ln, kind, info))

def dijkstra(g, src):
    dist = {src: (0.0, 0)}; prev = {}
    pq = [(0.0, 0, src)]
    while pq:
        d, v, u = heapq.heappop(pq)
        if dist.get(u, (1e18, 0)) < (d, v):
            continue
        for m, ln, kind, info in g.adj[u]:
            nd = (d + ln, v + (1 if kind == "via" else 0))
            if nd < dist.get(m, (1e18, 0)):
                dist[m] = nd; prev[m] = (u, ln, kind, info); heapq.heappush(pq, (nd[0], nd[1], m))
    return dist, prev

def path_to(prev, src, dst):
    seq = []; n = dst
    while n != src:
        u, ln, kind, info = prev[n]
        seq.append((u, n, ln, kind, info)); n = u
    return seq[::-1]

fam_parts = collections.defaultdict(dict)       # fam -> ref -> footprint
all_pads_fam = collections.defaultdict(list)
for ref, f in fps.items():
    for p in f.Pads():
        n = str(p.GetNetname())
        if n in net_to_fam:
            all_pads_fam[net_to_fam[n]].append(pad_info(f, p))
            if ref not in ("U1000",) + tuple(DRAMS):
                fam_parts[net_to_fam[n]][ref] = f

results = {}
for fam, members in fams.items():
    mset = set(members)
    g = G()
    pads = all_pads_fam[fam]
    vs = [v for v in vias_all if v["net"] in mset]
    # via + pad nodes first
    via_nodes = []
    for v in vs:
        ns = [g.node(v["x"], v["y"], l, 1e-6) for l in range(v["l0"], v["l1"] + 1)]
        for a, c in zip(ns, ns[1:]):
            g.edge(a, c, 0.0, "via", (round(v["x"], 3), round(v["y"], 3)))
        g.snap.append((v["x"], v["y"], max(v["pad"] / 2, 0.05), "via", v, list(range(v["l0"], v["l1"] + 1))))
    pad_nodes = {}
    for p in pads:
        ns = [g.node(p["pos"][0], p["pos"][1], l, 1e-6) for l in p["layers"]]
        for a, c in zip(ns, ns[1:]):
            g.edge(a, c, 0.0, "padstack")
        pad_nodes[(p["ref"], p["num"])] = ns
        g.snap.append((p["pos"][0], p["pos"][1], max(min(p["size"]) / 2, 0.05), "pad", p, p["layers"]))
    def endpoint(pt, layer):
        best = None
        for sx, sy, r, kind, info, ls in g.snap:
            if layer in ls and math.hypot(sx - pt[0], sy - pt[1]) <= r + 0.01:
                d = math.hypot(sx - pt[0], sy - pt[1])
                if best is None or d < best[0]:
                    best = (d, sx, sy)
        if best:
            return g.node(best[1], best[2], layer, 1e-6)
        return g.node(pt[0], pt[1], layer)
    track_len = 0.0
    for s in segs_all:
        if s["net"] in mset and s["layer"] >= 0:
            a = endpoint(s["s"], s["layer"]); c = endpoint(s["e"], s["layer"])
            g.edge(a, c, s["len"], "track", (lname(cu[s["layer"]]), s["w"]))
            track_len += s["len"]
    # 2-pad parts (0 ohm / R) as zero-length edges
    for ref, f in fam_parts[fam].items():
        ps = [p for p in f.Pads()]
        if len(ps) == 2 and ref[0] == "R":
            k0, k1 = (ref, str(ps[0].GetNumber())), (ref, str(ps[1].GetNumber()))
            for a in pad_nodes.get(k0, [])[:1]:
                for c in pad_nodes.get(k1, [])[:1]:
                    g.edge(a, c, 0.0, "part", ref)
    # source / targets
    src_pads = [p for p in pads if p["ref"] == "U1000"]
    dst_pads = [p for p in pads if p["ref"] in DRAMS]
    r = {"family": members, "track_length_total": R3(track_len), "n_vias_family": len(vs), "soc_ball": None, "targets": {}}
    if not src_pads or not dst_pads:
        r["error"] = "no soc ball or no dram ball"; results[fam] = r; continue
    sp = src_pads[0]
    r["soc_ball"] = {"num": sp["num"], "net": sp["net"], "pos_board": [R3(sp["pos"][0]), R3(sp["pos"][1])]}
    s_node = pad_nodes[(sp["ref"], sp["num"])][0]
    dist, prev = dijkstra(g, s_node)
    paths = {}
    for dp in dst_pads:
        key = dp["ref"] + "." + dp["num"]
        tn = None
        for n in pad_nodes[(dp["ref"], dp["num"])]:
            if n in dist and (tn is None or dist[n] < dist[tn]):
                tn = n
        if tn is None:
            r["targets"][key] = {"error": "unreachable", "net": dp["net"]}; continue
        paths[key] = (tn, path_to(prev, s_node, tn), dp)
    padn = {x for v in pad_nodes.values() for x in v}
    r["dangling_track_ends"] = sum(1 for n, a in g.adj.items() if n not in padn and len(a) == 1 and a[0][2] == "track")
    if len(paths) >= 2:
        keys = list(paths)
        pa, pb = paths[keys[0]][1], paths[keys[1]][1]
        k = 0
        while k < min(len(pa), len(pb)) and pa[k][:2] == pb[k][:2]:
            k += 1
        dnode = pa[k - 1][1] if k else s_node
        trunk, ba, bb = pa[:k], pa[k:], pb[k:]
        def via_groups(sq):
            vg, last = [], None
            for e in sq:
                if e[3] == "via":
                    la, lb = g.nodes[e[0]][2], g.nodes[e[1]][2]
                    if last is not None and vg and vg[-1]["xy"] == list(e[4]) and last == "via":
                        vg[-1]["to"] = LAYERS[lb]
                    else:
                        vg.append({"xy": list(e[4]), "from": LAYERS[la], "to": LAYERS[lb]})
                last = e[3] if e[3] in ("via", "track") else last
            return vg
        def sect(sq):
            tl = sum(e[2] for e in sq if e[3] == "track")
            vg = via_groups(sq)
            return {"length": R3(tl), "vias": len(vg), "via_list": vg,
                    "parts": [e[4] for e in sq if e[3] == "part"],
                    "layers_track": sorted({e[4][0] for e in sq if e[3] == "track"}, key=LAYERS.index),
                    "first_layer": next((e[4][0] for e in sq if e[3] == "track"), None),
                    "last_layer": next((e[4][0] for e in reversed(sq) if e[3] == "track"), None)}
        bx, by, bl = g.nodes[dnode]
        # classify branch point
        kind, kinfo = "junction", None
        for sx, sy, rr, kd, info, ls in g.snap:
            if math.hypot(sx - bx, sy - by) < 1e-3:
                kind = kd
                kinfo = ({"ref": info["ref"], "num": info["num"], "net": info["net"], "size": info["size"]} if kd == "pad"
                         else {"pad": info["pad"], "drill": info["drill"], "net": info["net"], "layers": [LAYERS[info["l0"]], LAYERS[info["l1"]]]})
                break
        # every via/pad that sits at the divergence xy
        r["branch"] = {"kind": kind, "info": kinfo, "pos_board": [R3(bx), R3(by)], "node_layer": LAYERS[bl],
                       "pos_soc": [R3(v) for v in socf((bx, by))],
                       "dist_to_target_balls_straight": {kk: R3(math.hypot(paths[kk][2]["pos"][0] - bx, paths[kk][2]["pos"][1] - by)) for kk in keys}}
        r["trunk"] = sect(trunk)
        r["branches"] = {keys[0]: sect(ba), keys[1]: sect(bb)}
        r["branch_length_diff"] = R3(abs(r["branches"][keys[0]]["length"] - r["branches"][keys[1]]["length"]))
        r["total_path"] = {kk: R3(sum(e[2] for e in paths[kk][1])) for kk in keys}
        r["coverage_check"] = "paths total %.3f vs track sum %.3f (difference = stubs/unused copper)" % (
            r["trunk"]["length"] + r["branches"][keys[0]]["length"] + r["branches"][keys[1]]["length"], track_len)
        # parts on the way (all footprint refs touching the family besides U)
    r["parts"] = sorted(fam_parts[fam])
    if len(dst_pads) > 2:
        r["extra_dram_pads"] = [d["ref"] + "." + d["num"] for d in dst_pads]
    results[fam] = r

# ---- array analysis
bp = {f: r["branch"] for f, r in results.items() if "branch" in r}
pts = {f: tuple(v["pos_board"]) for f, v in bp.items()}
viapts = {f: p for f, p in pts.items() if bp[f]["kind"] == "via"}
def nn_stats(P):
    ks = list(P)
    d = [min(math.dist(P[a], P[c]) for c in ks if c != a) for a in ks]
    return {"n": len(ks), "nn_min": R3(min(d)), "nn_median": R3(statistics.median(d)), "nn_max": R3(max(d))} if len(ks) > 1 else {"n": len(ks)}
def bbox(P):
    xs = [p[0] for p in P.values()]; ys = [p[1] for p in P.values()]
    return [R3(min(xs)), R3(min(ys)), R3(max(xs)), R3(max(ys))]
arr = {"all_branch_points": nn_stats(pts), "bbox_all": bbox(pts) if pts else None,
       "via_branch_points": nn_stats(viapts) if viapts else None, "bbox_via": bbox(viapts) if viapts else None,
       "kinds": dict(collections.Counter(v["kind"] for v in bp.values()))}
if pts:
    bb = arr["bbox_all"]
    arr["window_grown_0p7"] = [R3(bb[0] - 0.7), R3(bb[1] - 0.7), R3(bb[2] + 0.7), R3(bb[3] + 0.7)]
    W = arr["window_grown_0p7"]
    # distances to SoC field edge and the two DRAMs
    dram_geo = {}
    for ref in DRAMS:
        P = [xy(p.GetPosition()) for p in fps[ref].Pads()]
        lo = (min(q[0] for q in P), min(q[1] for q in P)); hi = (max(q[0] for q in P), max(q[1] for q in P))
        dram_geo[ref] = {"ball_field_box_board": [R3(lo[0]), R3(lo[1]), R3(hi[0]), R3(hi[1])], "centre": [R3(fps[ref].GetPosition().x * MM), R3(fps[ref].GetPosition().y * MM)]}
    arr["dram_geometry"] = dram_geo
    axis_y = (dram_geo["U3300"]["centre"][1] + dram_geo["U3301"]["centre"][1]) / 2
    arr["dram_axis_y_board"] = R3(axis_y)
    arr["soc_field_half_uv"] = [R3(SOC_HALF[0]), R3(SOC_HALF[1])]
    arr["per_point"] = {}
    for f, p in pts.items():
        q = socf(p)
        d = {"soc_field_edge_dist": R3(rect_dist(q, (-SOC_HALF[0], -SOC_HALF[1]), SOC_HALF)),
             "axis_offset_y": R3(p[1] - axis_y)}
        for ref in DRAMS:
            g_ = dram_geo[ref]["ball_field_box_board"]
            d["dist_to_" + ref + "_ball_box"] = R3(rect_dist(p, (g_[0], g_[1]), (g_[2], g_[3])))
        arr["per_point"][f] = d
    # rows analysis: cluster x and y
    def clusters(vals, tol=0.15):
        vs_ = sorted(vals); cl = [[vs_[0]]]
        for v in vs_[1:]:
            (cl[-1].append(v) if v - cl[-1][-1] <= tol else cl.append([v]))
        return [(R3(statistics.mean(c)), len(c)) for c in cl]
    arr["x_clusters_tol0.15"] = clusters([p[0] for p in pts.values()])
    arr["y_clusters_tol0.15"] = clusters([p[1] for p in pts.values()])
    # vias in the window
    gnd = lambda n: n.upper().startswith(("GND", "VSS", "AGND"))
    grown = [W[0] - 1.5, W[1] - 1.5, W[2] + 1.5, W[3] + 1.5]
    wv = []
    for v in vias_all:
        if grown[0] <= v["x"] <= grown[2] and grown[1] <= v["y"] <= grown[3]:
            wv.append({"net": v["net"], "x": R3(v["x"]), "y": R3(v["y"]), "pad": v["pad"], "drill": v["drill"],
                       "layers": [LAYERS[v["l0"]], LAYERS[v["l1"]]],
                       "in_window_0p7": W[0] <= v["x"] <= W[2] and W[1] <= v["y"] <= W[3],
                       "family": net_to_fam.get(v["net"]), "gnd": gnd(v["net"])})
    arr["window_vias"] = wv
    G_ = [v for v in vias_all if gnd(v["net"])]
    arr["gnd_nearest_to_branch_point"] = {}
    for f, p in pts.items():
        dd = sorted(math.hypot(v["x"] - p[0], v["y"] - p[1]) for v in G_)
        arr["gnd_nearest_to_branch_point"][f] = R3(dd[0]) if dd else None
    inw = [v for v in wv if v["gnd"] and v["in_window_0p7"]]
    sig_in = [v for v in wv if v["family"] and v["in_window_0p7"]]
    oth_in = [v for v in wv if not v["gnd"] and not v["family"] and v["in_window_0p7"]]
    arr["counts_in_window"] = {"gnd_vias": len(inw), "family_vias": len(sig_in), "branch_point_vias": len(viapts),
                               "other_net_vias": len(oth_in), "other_nets": sorted({v["net"] for v in oth_in}),
                               "ratio_gnd_to_branch_vias": R3(len(inw) / max(len(viapts), 1))}
    # other-net tracks crossing window (sampled)
    cross = collections.defaultdict(lambda: collections.defaultdict(float))
    for s in segs_all:
        if s["net"] in net_to_fam or s["layer"] < 0:
            continue
        n = max(2, int(math.dist(s["s"], s["e"]) / 0.05))
        hit = 0
        for i in range(n + 1):
            x = s["s"][0] + (s["e"][0] - s["s"][0]) * i / n; y = s["s"][1] + (s["e"][1] - s["s"][1]) * i / n
            if W[0] <= x <= W[2] and W[1] <= y <= W[3]:
                hit += 1
        if hit:
            cross[s["net"]][LAYERS[s["layer"]]] += s["len"] * hit / (n + 1)
    arr["other_net_tracks_in_window_mm"] = {n: {l: R3(x) for l, x in d.items()} for n, d in cross.items()}
    # same, inside the bare bbox of the branch points (no margin): what actually crosses the array
    cross2 = collections.defaultdict(lambda: collections.defaultdict(float))
    for s in segs_all:
        if s["net"] in net_to_fam or s["layer"] < 0:
            continue
        n = max(2, int(math.dist(s["s"], s["e"]) / 0.05)); hit = 0
        for i in range(n + 1):
            x = s["s"][0] + (s["e"][0] - s["s"][0]) * i / n; y = s["s"][1] + (s["e"][1] - s["s"][1]) * i / n
            if bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3]:
                hit += 1
        if hit:
            cross2[s["net"]][LAYERS[s["layer"]]] += s["len"] * hit / (n + 1)
    arr["other_net_tracks_in_bbox_mm"] = {n: {l: R3(x) for l, x in d.items()} for n, d in cross2.items()}
    # R/C pad to nearest family via distances
    fv = [v for v in vias_all if v["net"] in net_to_fam]
    pv = {}
    for fam_, refs_ in fam_parts.items():
        for ref_, f_ in refs_.items():
            for p_ in f_.Pads():
                pn = str(p_.GetNetname())
                if pn in net_to_fam:
                    pp_ = xy(p_.GetPosition())
                    cand = sorted((math.hypot(v["x"] - pp_[0], v["y"] - pp_[1]), v["net"], R3(v["x"]), R3(v["y"])) for v in fv if v["net"] == pn or net_to_fam.get(v["net"]) == net_to_fam[pn])
                    pv[ref_ + "." + str(p_.GetNumber())] = {"net": pn, "nearest_family_vias": [[R3(c[0]), c[1], c[2], c[3]] for c in cand[:2]]}
    arr["part_pad_to_via"] = pv
    fam_in = collections.defaultdict(lambda: collections.defaultdict(float))
    for s in segs_all:
        if s["net"] in net_to_fam and s["layer"] >= 0:
            fam_in[LAYERS[s["layer"]]][net_to_fam[s["net"]]] += 0
    # inter-via ground positions relative to signal vias: pairs
# ---- parts
partsout = {}
for fam, refs in fam_parts.items():
    for ref, f in refs.items():
        if ref in partsout:
            continue
        partsout[ref] = {"value": str(f.GetValue()), "package": str(f.GetFPID().GetLibItemName()), "side": lname(f.GetLayer()),
                         "pos_board": [R3(f.GetPosition().x * MM), R3(f.GetPosition().y * MM)], "rot": f.GetOrientationDegrees(),
                         "pads": [{"num": str(p.GetNumber()), "net": str(p.GetNetname()), "pos_board": [R3(xy(p.GetPosition())[0]), R3(xy(p.GetPosition())[1])],
                                   "size": [R3(p.GetSize().x * MM), R3(p.GetSize().y * MM)]} for p in f.Pads()],
                         "families": sorted(k for k, v in fam_parts.items() if ref in v)}
        peers = {}
        for p in f.Pads():
            pn = str(p.GetNetname())
            if pn not in net_to_fam and not pn.upper().startswith(("GND", "VSS")):
                peers[pn] = sorted(q.GetParentFootprint().GetReference() + ":" + str(q.GetParentFootprint().GetValue()) for q in b.GetPads() if str(q.GetNetname()) == pn)
        if peers:
            partsout[ref]["other_net_peers"] = peers

for ref in list(partsout):
    for pn, lst in partsout[ref].get("other_net_peers", {}).items():
        for item in lst:
            r2 = item.split(":")[0]
            if r2 in partsout or r2 in ("U3300", "U3301", "U1000") or r2 not in fps:
                continue
            f = fps[r2]
            partsout[r2] = {"value": str(f.GetValue()), "side": lname(f.GetLayer()), "role": "peer on net " + pn,
                            "pos_board": [R3(f.GetPosition().x * MM), R3(f.GetPosition().y * MM)], "rot": f.GetOrientationDegrees(),
                            "pads": [{"num": str(p.GetNumber()), "net": str(p.GetNetname()), "pos_board": [R3(xy(p.GetPosition())[0]), R3(xy(p.GetPosition())[1])],
                                      "size": [R3(p.GetSize().x * MM), R3(p.GetSize().y * MM)]} for p in f.Pads()]}

res = {"board": "RK_EVB1_RK3568_DDR4P216SD6_V10_20200908GXL.brd (integration-rk3568)", "units": "mm", "layers": LAYERS,
       "frame": {"board": "KiCad import coordinates, mm, y grows downward (on screen)",
                 "soc": {"origin_board": [R3(cx), R3(cy)], "u_dir_board": [R3(ex[0]), R3(ex[1])], "v_dir_board": [R3(ey[0]), R3(ey[1])],
                         "note": "u along ball row A column 1->28, v row A->AH; origin = package centre"},
                 "rule": "all coordinates in this file are 'board' unless the key says soc/uv"},
       "soc": {"ref": "U1000", "pos_board": [R3(soc.GetPosition().x * MM), R3(soc.GetPosition().y * MM)], "rot": soc.GetOrientationDegrees()},
       "drams": {r: {"pos_board": [R3(fps[r].GetPosition().x * MM), R3(fps[r].GetPosition().y * MM)], "rot": fps[r].GetOrientationDegrees(),
                     "side": lname(fps[r].GetLayer())} for r in DRAMS},
       "nets": results, "array": arr, "parts": partsout}
json.dump(res, open(out, "w", encoding="utf-8"), indent=1)
print("ok", len(results), "families;", len(pts), "branch points;", len(partsout), "parts")
