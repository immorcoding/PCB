"""PROTOTYPE (issue 21): the checks of a built board.

geometry(B)        read from the board file with numpy (no kicad-cli, about a second): same-layer gaps between
                   different nets (and whether any is below the DRC clearance of the place), every net a single
                   pad-to-pad path (no T junction, no loose end), and the things neither DRC nor
                   scripts/track_shape.py look at: serpentine copper to other nets / to rule-area edges, straight
                   left between a bend and the first arc, arc radii and sweep, 0.09 track outside the rule areas,
                   change of direction across vias.  This is the successor of the length-tuning geo_check.py.
run_drc(vdir)      kicad-cli pcb drc --refill-zones --save-board --severity-all  -> drc.json + summary
canary(vdir)       scripts/dru_canary.py: proves the rule file is loaded
track_shape(vdir)  scripts/track_shape.py (it does not know arcs: its zeros say nothing about serpentines)
"""
import collections, json, math, os, re, subprocess
import numpy as np
import pcbnew
from common import (CLI, PY, NAME, REPO_SCRIPTS, AREAS, CLR_IN, CLR_OUT, W_OUT, LNUM, Lp, mm, short, in_rect, arc_geom, arc_pts)
from serp import _d_pts_segs

SHARP = 0.35


def _touches_area(pts, hw):
    for R in AREAS.values():
        for p in pts:
            if in_rect(p, R, hw):
                return True
    return False


def geometry(B, prefix="/FMC_"):
    items = []                                              # every copper piece: dict
    for t in B.GetTracks():
        n = t.GetNetname()
        if t.Type() == pcbnew.PCB_VIA_T:
            c = Lp(t.GetPosition()); hw = mm(t.GetWidth(pcbnew.F_Cu)) / 2
            items.append({"k": "via", "net": n, "layer": None, "pts": [c, c], "hw": hw, "name": short(n) + " via"})
        else:
            arc = t.Type() == pcbnew.PCB_ARC_T
            items.append({"k": "arc" if arc else "seg", "net": n, "layer": LNUM[t.GetLayer()], "pts": arc_pts(t, 0.01) if arc else [Lp(t.GetStart()), Lp(t.GetEnd())],
                          "hw": mm(t.GetWidth()) / 2, "t": t, "name": short(n)})
    for fp in B.GetFootprints():
        for p in fp.Pads():
            c = Lp(p.GetPosition())
            items.append({"k": "pad", "net": p.GetNetname() or ("pad %s.%s" % (fp.GetReference(), p.GetNumber())), "layer": "L1",
                          "pts": [c, c], "hw": max(mm(p.GetSizeX()), mm(p.GetSizeY())) / 2, "name": "%s.%s" % (fp.GetReference(), p.GetNumber())})
    for i, it in enumerate(items):
        it["i"] = i; it["area"] = _touches_area(it["pts"], it["hw"])
    tracks = [it for it in items if it["k"] in ("seg", "arc") and it["net"].startswith(prefix)]

    # ---- joints (exact nm end points): serpentine legs, leads, path check
    at = collections.defaultdict(list)
    for it in tracks:
        for p in (it["t"].GetStart(), it["t"].GetEnd()):
            at[(it["net"], it["layer"], p.x, p.y)].append(it)
    other = lambda it, p: [o for o in at[(it["net"], it["layer"], p.x, p.y)] if o is not it]
    leads = []
    for it in tracks:
        if it["k"] == "arc":
            it["serp"] = True
            continue
        t = it["t"]
        ends = [(p, other(it, p)) for p in (t.GetStart(), t.GetEnd())]
        n_arc = sum(1 for _, o in ends if any(x["k"] == "arc" for x in o))
        it["serp"] = n_arc == 2
        if n_arc == 1:
            (p, o), = [(p, o) for p, o in ends if not any(x["k"] == "arc" for x in o)]
            if o and o[0]["k"] == "seg":                    # the far end is a bend (a width change on a straight has no turn)
                a, c = it["pts"]; q0, q1 = o[0]["pts"]
                d1 = math.atan2(c[1] - a[1], c[0] - a[0]); d2 = math.atan2(q1[1] - q0[1], q1[0] - q0[0])
                turn = abs(math.degrees(math.asin(max(-1, min(1, math.sin(d1 - d2))))))
                if turn > 1:
                    leads.append({"net": short(it["net"]), "len": round(mm(t.GetLength()), 4), "at": [round(mm(p.x) - 100, 3), round(mm(p.y) - 100, 3)]})

    # ---- every net one simple path from its U1 pad to its U2 pad
    path_bad = []
    deg = collections.defaultdict(lambda: collections.defaultdict(int))
    for it in tracks:
        for p in (it["t"].GetStart(), it["t"].GetEnd()):
            deg[it["net"]][(it["layer"], p.x, p.y)] += 1
    padpos = collections.defaultdict(set)
    for fp in B.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname().startswith(prefix):
                padpos[p.GetNetname()].add(("L1", p.GetPosition().x, p.GetPosition().y))
    viapos = collections.defaultdict(set)
    for v in items:
        if v["k"] == "via":
            q = pcbnew.VECTOR2I(int(round((v["pts"][0][0] + 100) * 1e6)), int(round((v["pts"][0][1] + 100) * 1e6)))
            viapos[v["net"]].add((q.x, q.y))
    for n, d in deg.items():
        for key, k in d.items():
            want = 1 if (key in padpos[n] or (key[1], key[2]) in viapos[n]) else 2
            if k != want:
                path_bad.append("%s %s: %d track ends meet at (%.3f, %.3f), expected %d (%s)" % (
                    short(n), key[0], k, mm(key[1]) - 100, mm(key[2]) - 100, want, "T junction" if k > want else "loose end"))
        if len(padpos[n] & set(d)) != 2:
            path_bad.append("%s: the tracks do not reach both pads" % short(n))

    # ---- same-layer gaps between different nets (numpy: sample points of the bus tracks against all pieces)
    netid = {}
    nid = lambda n: netid.setdefault(n, len(netid))
    viol, pairs = {}, {}
    all_min, serp_min = None, None
    for layer in ("L1", "L4", "L6"):
        segs = [(a, c, it) for it in items if it["k"] in ("seg", "arc") and it["layer"] == layer for a, c in zip(it["pts"], it["pts"][1:])]
        rnds = [it for it in items if it["k"] in ("via", "pad") and it["layer"] in (None, layer)]
        pts = []
        for it in tracks:
            if it["layer"] != layer:
                continue
            for a, c in zip(it["pts"], it["pts"][1:]):
                n = max(1, int(math.dist(a, c) / 0.02))
                pts += [(a[0] + (c[0] - a[0]) * i / n, a[1] + (c[1] - a[1]) * i / n, it) for i in range(n + 1)]
        if not pts:
            continue
        PX = np.array([(p[0], p[1]) for p in pts]); Pn = np.array([nid(p[2]["net"]) for p in pts])
        Phw = np.array([p[2]["hw"] for p in pts]); Par = np.array([p[2]["area"] for p in pts]); Pse = np.array([p[2]["serp"] for p in pts])
        Pit = [p[2] for p in pts]
        tgt = []
        if segs:
            tgt.append((np.array([s[0] for s in segs]), np.array([s[1] for s in segs]), [s[2] for s in segs]))
        if rnds:
            C = np.array([r["pts"][0] for r in rnds]); tgt.append((C, C, rnds))
        for A, Cc, its in tgt:
            Tn = np.array([nid(x["net"]) for x in its]); Thw = np.array([x["hw"] for x in its]); Tar = np.array([x["area"] for x in its])
            for s in range(0, len(PX), 1500):
                e = min(len(PX), s + 1500)
                D = _d_pts_segs(PX[s:e], A, Cc) - Phw[s:e, None] - Thw[None, :]
                D = np.where(Pn[s:e, None] == Tn[None, :], 1e9, D)
                need = np.where(Par[s:e, None] | Tar[None, :], CLR_IN, CLR_OUT)
                j = D.argmin(1); g = D[np.arange(e - s), j]
                for i in np.argwhere(g < 0.3).ravel():
                    p, o, gap = Pit[s + i], its[j[i]], float(g[i])
                    rec = {"gap": round(gap, 4), "net": short(p["net"]), "other": o["name"], "layer": layer, "at": [round(float(PX[s + i][0]), 3), round(float(PX[s + i][1]), 3)],
                           "need": float(need[i, j[i]]), "serp": bool(Pse[s + i])}
                    if all_min is None or gap < all_min["gap"]:
                        all_min = rec
                    if rec["serp"]:
                        if serp_min is None or gap < serp_min["gap"]:
                            serp_min = rec
                        k = (rec["net"], rec["other"], layer)
                        if k not in pairs or gap < pairs[k]["gap"]:
                            pairs[k] = rec
                for i, jj in np.argwhere(D < need - 1e-4):   # one line per pair of nets and layer: the worst spot
                    k = tuple(sorted((short(Pit[s + i]["net"]), its[jj]["name"]))) + (layer,)
                    if k not in viol or D[i, jj] < viol[k]["gap"]:
                        viol[k] = {"gap": round(float(D[i, jj]), 4), "need": float(need[i, jj]), "net": short(Pit[s + i]["net"]), "other": its[jj]["name"],
                                   "layer": layer, "at": [round(float(PX[s + i][0]), 3), round(float(PX[s + i][1]), 3)]}
    viol = sorted(viol.values(), key=lambda v: v["gap"])

    # ---- serpentine copper outside the rule areas: gap to the area edges
    area_gap = None
    for it in tracks:
        if not it["serp"] or it["hw"] * 2 < W_OUT - 1e-6:
            continue
        for name, R in AREAS.items():
            for p in it["pts"]:
                dx = max(R[0] - p[0], 0, p[0] - R[2]); dy = max(R[1] - p[1], 0, p[1] - R[3])
                d = math.hypot(dx, dy) - it["hw"]
                if area_gap is None or d < area_gap["gap"]:
                    area_gap = {"gap": round(d, 4), "net": short(it["net"]), "area": name, "at": [round(p[0], 3), round(p[1], 3)]}

    off_grid = []                                           # straight pieces off 0/45/90, measured on the nm coordinates
    for it in tracks:                                       # (track_shape.py rounds to 1 um first and misreads short diagonal legs)
        if it["k"] == "seg":
            t = it["t"]; dx, dy = t.GetEnd().x - t.GetStart().x, t.GetEnd().y - t.GetStart().y
            ang = math.degrees(math.atan2(dy, dx)) % 45
            dev = min(ang, 45 - ang)
            if dev > 0.05 and math.hypot(dx, dy) > 5e4:
                off_grid.append({"net": short(it["net"]), "layer": it["layer"], "at": [round(v, 3) for v in it["pts"][0]], "deg_off": round(dev, 3), "len": round(mm(t.GetLength()), 4)})

    arcs = [arc_geom(it["t"]) for it in tracks if it["k"] == "arc"]
    sweeps = [abs(math.degrees(a[3])) for a in arcs]
    radii = sorted({round(a[1], 3) for a in arcs})

    thin = collections.defaultdict(float)                   # 0.09 track outside both rule areas
    for it in tracks:
        if it["k"] == "seg" and it["hw"] * 2 < W_OUT - 1e-6:
            a, c = it["pts"]; L = math.dist(a, c); n = max(1, int(L / 0.01))
            out = sum(1 for i in range(n) if not any(in_rect((a[0] + (c[0] - a[0]) * (i + .5) / n, a[1] + (c[1] - a[1]) * (i + .5) / n), R) for R in AREAS.values()))
            thin[short(it["net"])] += L * out / n

    via_turn = []                                           # 0 = straight through in plan view, 180 = doubles back
    for v in items:
        if v["k"] != "via" or not v["net"].startswith(prefix):
            continue
        dirs = []
        for it in tracks:
            if it["net"] == v["net"] and it["k"] == "seg":
                for i in (0, 1):
                    if math.dist(it["pts"][i], v["pts"][0]) < 1e-6:
                        o = it["pts"][1 - i]
                        dirs.append(math.atan2(o[1] - v["pts"][0][1], o[0] - v["pts"][0][0]))
        if len(dirs) == 2:
            dd = abs((dirs[0] - dirs[1] + math.pi) % (2 * math.pi) - math.pi)
            via_turn.append({"net": short(v["net"]), "at": [round(v["pts"][0][0], 3), round(v["pts"][0][1], 3)], "turn": round(180 - math.degrees(dd), 1)})

    return {"clearance_violations": viol, "path_problems": path_bad, "min_gap_all": all_min, "off_grid_exact": off_grid,
            "serp": {"arcs": len(arcs), "radii": radii, "sweep_min": round(min(sweeps), 2) if sweeps else None, "sweep_max": round(max(sweeps), 2) if sweeps else None,
                     "min_gap_to_other_net": serp_min, "pairs_below_0.3": sorted(pairs.values(), key=lambda r: r["gap"])[:40],
                     "min_gap_to_area_edge_outside": area_gap,
                     "lead_min": min((l["len"] for l in leads), default=None), "leads_below_0.35": [l for l in leads if l["len"] < SHARP - 1e-6]},
            "thin_outside_mm": {n: round(v, 3) for n, v in sorted(thin.items()) if v > 0.005},
            "via_turn": via_turn, "via_turn_90_or_more": [v for v in via_turn if v["turn"] >= 89]}


def run_drc(vdir):
    """Refill the pours, save the board, run the full DRC. Returns the summary dict (also drc.json on disk)."""
    pcb = os.path.join(vdir, NAME + ".kicad_pcb")
    subprocess.run([CLI, "pcb", "drc", "--refill-zones", "--save-board", "--severity-all", "--format", "json",
                    "-o", os.path.join(vdir, "drc.json"), pcb], capture_output=True)
    d = json.load(open(os.path.join(vdir, "drc.json"), encoding="utf-8"))
    by = collections.Counter(v["type"] for v in d["violations"])
    items = []
    for v in d["violations"]:
        it = v["items"][0] if v["items"] else {}
        items.append({"type": v["type"], "severity": v["severity"], "at": [round(it.get("pos", {}).get("x", 100) - 100, 3), round(it.get("pos", {}).get("y", 100) - 100, 3)],
                      "what": " / ".join(i.get("description", "") for i in v["items"]), "text": v.get("description", "")})
    return {"kicad": d.get("kicad_version", "?"), "unconnected": len(d["unconnected_items"]), "violations": len(d["violations"]),
            "by_type": dict(sorted(by.items())), "schematic_parity": len(d.get("schematic_parity", [])), "items": items,
            "unconnected_items": [" / ".join(i.get("description", "") for i in u["items"]) for u in d["unconnected_items"]]}


def canary(vdir):
    r = subprocess.run([PY, os.path.join(REPO_SCRIPTS, "dru_canary.py"), os.path.join(vdir, NAME + ".kicad_pcb")], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return {"ok": r.returncode == 0, "text": (r.stdout or r.stderr).strip()}


def track_shape(vdir):
    r = subprocess.run([PY, os.path.join(REPO_SCRIPTS, "track_shape.py"), os.path.join(vdir, NAME + ".kicad_pcb")], capture_output=True, text=True, encoding="utf-8", errors="replace")
    txt = r.stdout
    open(os.path.join(vdir, "track_shape.txt"), "w", encoding="utf-8").write(txt + r.stderr)
    out = {"script": os.path.join(REPO_SCRIPTS, "track_shape.py").replace("\\", "/")}
    for k in ("off-grid", "staircase", "sharp", "crowded"):
        m = re.search(r"^%s: (\d+)" % k, txt, re.M)
        out[k] = int(m.group(1)) if m else None
    m = re.search(r"^tiny \(< 0.1 mm\): (\d+)", txt, re.M)
    out["tiny"] = int(m.group(1)) if m else None
    m = re.search(r"^(\d+) segments, (\d+) arcs", txt, re.M)
    out["segments"], out["arcs"] = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    out["lines"] = [l.strip() for l in txt.splitlines() if l.startswith("    ")]
    return out
