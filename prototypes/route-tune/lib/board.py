"""PROTOTYPE (issue 21): build the untuned board of a variant from its routes.py.

build(variant module, out dir) writes <out>/routetune.kicad_pcb (+ .kicad_pro, .kicad_dru, routes.json):
six layers, the two BGAs, one rule area round each (package + 1 mm, all copper layers), ground pours on
L2 and L5 (filled later by kicad-cli --refill-zones), the JLC06161H-3313E stackup with real thicknesses,
and the 19 nets drawn exactly as ROUTES says. No schematic: nets are put straight onto pads.

Track width is NOT written in routes.py. Along each layer piece the part that lies inside a rule area,
plus W_CHANGE (0.3 mm) of track beyond the area edge, is 0.09; everything else is 0.1016. The cut is
made on the straight (never at a bend) and is moved onto a route point when it would leave a piece
shorter than 0.1 mm. (The length-tuning prototype changed width at the first bend outside the area,
which left 2-4 mm of 0.09 track outside and no wide straight to tune on.)
"""
import importlib.util, json, math, os, shutil
import pcbnew
import balls
from common import (ROOT, KI, NAME, BOARD, AREAS, BODY, FOOTPRINT, W_IN, W_OUT, W_CHANGE, VIA_IN, VIA_OUT, MINSEG,
                    LID, SIGNAL_LAYERS, NETS, P, Lp, mm, full, in_rect, area_of, check_lock)

# JLC06161H-3313E (research/jlc-6layer-capability, section 5). The L3-L4 dielectric is really
# 7628 0.2104 + bare core 0.7 + 7628 0.2104; written as one layer of 1.1208 (only the height matters here).
STACK = """		(stackup
			(layer "F.SilkS" (type "Top Silk Screen"))
			(layer "F.Paste" (type "Top Solder Paste"))
			(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
			(layer "F.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 1" (type "prepreg") (thickness 0.0994) (material "3313") (epsilon_r 4.1) (loss_tangent 0.02))
			(layer "In1.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 2" (type "core") (thickness 0.1) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
			(layer "In2.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 3" (type "prepreg") (thickness 1.1208) (material "7628+core+7628") (epsilon_r 4.4) (loss_tangent 0.02))
			(layer "In3.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 4" (type "core") (thickness 0.1) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
			(layer "In4.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 5" (type "prepreg") (thickness 0.0994) (material "3313") (epsilon_r 4.1) (loss_tangent 0.02))
			(layer "B.Cu" (type "copper") (thickness 0.035))
			(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
			(layer "B.Paste" (type "Bottom Solder Paste"))
			(layer "B.SilkS" (type "Bottom Silk Screen"))
			(copper_finish "None")
			(dielectric_constraints no)
		)
"""
# Height KiCad's DRC adds for one via between two signal layers (measured with the probe rule on this
# stackup; lengths.py re-checks the sum against DRC on every full build).
VIA_H = {("L1", "L4"): 1.3932, ("L4", "L6"): 0.2572, ("L1", "L6"): 1.6504}   # all three measured against DRC (L4-L6 by the review's scratch variant)


def via_height(a, b):
    return 0.0 if a == b else VIA_H[tuple(sorted((a, b)))]


def load_variant(key):
    """Import variants/<key>/routes.py as a module (its folder is put on sys.path so it can import siblings)."""
    path = os.path.join(ROOT, "variants", key, "routes.py")
    if not os.path.isfile(path):
        raise SystemExit("no variant: " + path)
    spec = importlib.util.spec_from_file_location("routes_" + key.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for attr in ("DESCRIPTION", "SWAP", "ROUTES", "TUNING", "WHY"):
        if not hasattr(mod, attr):
            raise SystemExit("%s: %s is missing" % (path, attr))
    return mod


def base_routes(key):
    """ROUTES / SWAP / WHY of another variant, deep-copied: for variants that start from an existing one."""
    import copy
    m = load_variant(key)
    return copy.deepcopy(m.ROUTES), dict(m.SWAP), dict(m.WHY)


def _clip(a, c, R):
    """Parameter interval (t0, t1) of segment a-c inside rectangle R, or None."""
    t0, t1 = 0.0, 1.0
    for p, q in ((-(c[0] - a[0]), a[0] - R[0]), (c[0] - a[0], R[2] - a[0]), (-(c[1] - a[1]), a[1] - R[1]), (c[1] - a[1], R[3] - a[1])):
        if p == 0:
            if q < 0:
                return None
        elif p < 0:
            t0 = max(t0, q / p)
        else:
            t1 = min(t1, q / p)
    return (t0, t1) if t0 <= t1 else None


def split_widths(pts):
    """[(a, c, width)] for one layer piece: thin inside the rule areas and W_CHANGE of track beyond them."""
    seglen = [math.dist(a, c) for a, c in zip(pts, pts[1:])]
    cum = [0.0]
    for l in seglen:
        cum.append(cum[-1] + l)
    thin = []                                               # arclength intervals inside an area
    for i, (a, c) in enumerate(zip(pts, pts[1:])):
        for R in AREAS.values():
            iv = _clip(a, c, R)
            if iv:                                          # the extra W_CHANGE never passes the end of this segment: a thin
                thin.append((max(cum[i], cum[i] + iv[0] * seglen[i] - W_CHANGE),    # piece must itself touch the rule area,
                             min(cum[i + 1], cum[i] + iv[1] * seglen[i] + W_CHANGE)))   # or DRC flags its width
    thin.sort()
    merged = []
    for s0, s1 in thin:
        s0, s1 = max(0.0, s0), min(cum[-1], s1)
        if merged and s0 <= merged[-1][1] + MINSEG + 1e-9:  # a wide gap shorter than 0.1 mm is not worth two width changes
            merged[-1][1] = max(merged[-1][1], s1)
        else:
            merged.append([s0, s1])
    cuts = set()
    for iv in merged:                                       # move a cut onto a route point when it is within 0.1 mm of it
        for k in (0, 1):
            near = min(cum, key=lambda s: abs(s - iv[k]))
            if abs(near - iv[k]) < MINSEG + 1e-6:
                iv[k] = near
            cuts.add(round(iv[k], 9))
    is_thin = lambda s: any(s0 - 1e-9 <= s <= s1 + 1e-9 for s0, s1 in merged)
    out = []
    for i, (a, c) in enumerate(zip(pts, pts[1:])):
        inner = sorted(s for s in cuts if cum[i] + 1e-6 < s < cum[i + 1] - 1e-6)
        stops = [cum[i]] + inner + [cum[i + 1]]
        ux, uy = (c[0] - a[0]) / seglen[i], (c[1] - a[1]) / seglen[i]
        q = [a]
        for s in inner:                                     # cut point on a 1 um grid, still exactly on the 0/45/90 line
            d = s - cum[i]
            step = round(d * abs(ux) * 1000) / 1000 if abs(ux) > 1e-9 else 0.0
            if abs(ux) > 1e-9 and abs(uy) > 1e-9:
                q.append((round(a[0] + math.copysign(step, ux), 6), round(a[1] + math.copysign(step, uy), 6)))
            elif abs(ux) > 1e-9:
                q.append((round(a[0] + math.copysign(step, ux), 6), a[1]))
            else:
                q.append((a[0], round(a[1] + math.copysign(round(d * 1000) / 1000, uy), 6)))
        q.append(c)
        for j in range(len(q) - 1):
            out.append((q[j], q[j + 1], W_IN if is_thin((stops[j] + stops[j + 1]) / 2) else W_OUT))
    return out


def resolve(routes, pads):
    """Replace 'U1' / 'U2' by pad centres, check each net: connected pad to pad, only 0/45/90 segments,
    layer changes only at vias. Returns {net: [piece dicts]}; raises SystemExit with the exact place."""
    out = {}
    for net, pieces in routes.items():
        net = full(net)
        res, where, layer = [], None, None
        for pc in pieces:
            if pc[0] == "via":
                xy = tuple(pc[1])
                if where is None or math.dist(where, xy) > 1e-6:
                    raise SystemExit("%s: via at %s is not at the end of the piece before it (%s)" % (net, xy, where))
                size = tuple(pc[2]) if len(pc) > 2 else (VIA_IN if area_of(xy) else VIA_OUT)
                res.append({"via": list(xy), "size": list(size)})
                layer = None
                continue
            lay, pts = pc[0], [pads[(p, net)] if isinstance(p, str) else (float(p[0]), float(p[1])) for p in pc[1]]
            if lay not in SIGNAL_LAYERS:
                raise SystemExit("%s: layer %s is not a signal layer (L1, L4, L6)" % (net, lay))
            if where is not None and math.dist(where, pts[0]) > 1e-6:
                raise SystemExit("%s: piece on %s starts at %s but the net was at %s" % (net, lay, pts[0], where))
            if layer is not None:
                raise SystemExit("%s: two track pieces in a row without a via (%s then %s)" % (net, layer, lay))
            for a, c in zip(pts, pts[1:]):
                dx, dy = abs(c[0] - a[0]), abs(c[1] - a[1])
                if max(dx, dy) < MINSEG - 1e-9:
                    raise SystemExit("%s %s: segment %s -> %s is shorter than 0.1 mm" % (net, lay, a, c))
                if min(dx, dy) > 1e-6 and abs(dx - dy) > 1e-6:
                    raise SystemExit("%s %s: segment %s -> %s is not at 0/45/90 degrees (dx %.4f, dy %.4f)" % (net, lay, a, c, dx, dy))
            for a, b2, c in zip(pts, pts[1:], pts[2:]):     # no 90-degree or sharper corner, no straight-through point
                d1 = math.atan2(b2[1] - a[1], b2[0] - a[0]); d2 = math.atan2(c[1] - b2[1], c[0] - b2[0])
                turn = abs((math.degrees(d2 - d1) + 180) % 360 - 180)
                if turn > 45.5:
                    raise SystemExit("%s %s: %.0f-degree corner at %s (only 45-degree bends are allowed)" % (net, lay, turn, b2))
            res.append({"layer": lay, "points": [list(p) for p in pts]})
            where, layer = pts[-1], lay
        first = [p for p in res if "layer" in p][0]["points"][0]
        if math.dist(first, pads[("U1", net)]) > 1e-6 or math.dist(where, pads[("U2", net)]) > 1e-6:
            raise SystemExit("%s: the route must start at 'U1' and end at 'U2'" % net)
        out[net] = res
    missing = sorted(set(NETS) - set(out))
    if missing:
        raise SystemExit("ROUTES has no route for: %s" % ", ".join(missing))
    return out


def breakout_notes(resolved, mcu_ball):
    """Check the fixed breakout convention; returns a list of English warnings (empty = all kept)."""
    notes = []
    fld = (8.45 - 0.15, 7.45 - 0.15, 17.55 + 0.15, 16.55 + 0.15)   # MCU ball field
    for net, pieces in resolved.items():
        vias = [p for p in pieces if "via" in p]
        lays = [p["layer"] for p in pieces if "layer" in p]
        r = balls.ring(mcu_ball[net])
        first_via_in_field = bool(vias) and in_rect(vias[0]["via"], fld)
        if r >= 2 and not (first_via_in_field and len(lays) > 1 and lays[1] == "L4"):
            notes.append("%s (MCU ring %d, inner): should use a dog-bone via and leave on L4" % (net, r))
        if r <= 1 and first_via_in_field:
            notes.append("%s (MCU ring %d, outer): should leave the ball field on L1, but its first via is inside the field" % (net, r))
        if len(vias) > 3:
            notes.append("%s: %d vias, the hard cap is 3" % (net, len(vias)))
    return notes


def build(var, out_dir):
    """Write the untuned board. Returns info dict (also saved as routes.json)."""
    FromMM = pcbnew.FromMM
    W, H = getattr(var, "BOARD", BOARD)
    os.makedirs(out_dir, exist_ok=True)
    check_lock(out_dir)
    for ext in ("kicad_pro", "kicad_dru"):
        shutil.copy(os.path.join(ROOT, "base", NAME + "." + ext), os.path.join(out_dir, NAME + "." + ext))
    pcb = os.path.join(out_dir, NAME + ".kicad_pcb")
    shutil.copy(os.path.join(ROOT, "base", "empty6.kicad_pcb"), pcb)
    B = pcbnew.LoadBoard(pcb)

    def net(name):
        n = B.FindNet(name)
        if n is None:
            n = pcbnew.NETINFO_ITEM(B, name); B.Add(n)
        return n

    for a, c in (((0, 0), (W, 0)), ((W, 0), (W, H)), ((W, H), (0, H)), ((0, H), (0, 0))):
        s = pcbnew.PCB_SHAPE(B); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(P(a)); s.SetEnd(P(c))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FromMM(0.1)); B.Add(s)

    for name, (x0, y0, x1, y1) in AREAS.items():           # rule areas (AD: Room), all copper layers, nothing forbidden
        z = pcbnew.ZONE(B); z.SetIsRuleArea(True); z.SetZoneName(name)
        ls = pcbnew.LSET()
        for l in LID.values():
            ls.AddLayer(l)
        z.SetLayerSet(ls)
        for k in ("SetDoNotAllowTracks", "SetDoNotAllowVias", "SetDoNotAllowPads", "SetDoNotAllowZoneFills", "SetDoNotAllowFootprints"):
            getattr(z, k)(False)
        o = z.Outline(); o.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            o.Append(P((x, y)))
        B.Add(z)

    mcu_ball, notes = balls.verify(FOOTPRINT["U1"][0], FOOTPRINT["U2"][0])
    swap, lanes_swapped = balls.check_swap(var.SWAP)
    ram_ball = {n: b for n, (_, b) in swap.items()}
    pads = {}
    for ref, (spec, xy, value) in FOOTPRINT.items():
        lib, name = spec.split(":")
        fp = pcbnew.FootprintLoad(os.path.join(KI, "footprints", lib + ".pretty"), name)
        fp.SetFPID(pcbnew.LIB_ID(lib, name)); fp.SetReference(ref); fp.SetValue(value)
        fp.SetPosition(P(xy)); B.Add(fp)
        by_num = {p.GetNumber(): p for p in fp.Pads()}
        for n, b in (mcu_ball if ref == "U1" else ram_ball).items():
            by_num[b].SetNet(net("/" + n))
            q = Lp(by_num[b].GetPosition()); pads[(ref, n)] = (round(q[0], 4), round(q[1], 4))
        g = by_num[balls.GND_BALLS[ref]]; g.SetNet(net("GND"))
        q = Lp(g.GetPosition()); pads[(ref, "GND")] = (round(q[0], 4), round(q[1], 4))

    def via(netname, xy, size):
        v = pcbnew.PCB_VIA(B); v.SetPosition(P(xy)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetWidth(pcbnew.F_Cu, FromMM(size[0])); v.SetDrill(FromMM(size[1]))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net(netname)); B.Add(v)

    def seg(netname, layer, a, c, w):
        s = pcbnew.PCB_TRACK(B); s.SetStart(P(a)); s.SetEnd(P(c)); s.SetWidth(FromMM(w))
        s.SetLayer(LID[layer]); s.SetNet(net(netname)); B.Add(s)

    resolved = resolve(var.ROUTES, pads)
    for n, pieces in resolved.items():
        for pc in pieces:
            if "via" in pc:
                via("/" + n, pc["via"], pc["size"])
            else:
                pc["widths"] = []
                for a, c, w in split_widths([tuple(p) for p in pc["points"]]):
                    seg("/" + n, pc["layer"], a, c, w); pc["widths"].append([list(a), list(c), w])
    gnd_taps = getattr(var, "GND_TAPS", {"U1": (13.975, 14.925), "U2": (26.0, 10.3)})
    for ref, xy in gnd_taps.items():                        # ground ball -> via beside it (ties L2 and L5 together)
        via("GND", xy, VIA_IN); seg("GND", "L1", pads[(ref, "GND")], xy, 0.15)

    for layer in ("In1.Cu", "In4.Cu"):                     # ground pours on L2 and L5; filled by kicad-cli --refill-zones
        z = pcbnew.ZONE(B); z.SetZoneName("GND_" + layer[:3]); z.SetLayer(B.GetLayerID(layer)); z.SetNet(net("GND"))
        z.SetAssignedPriority(0); z.SetLocalClearance(FromMM(0.2)); z.SetMinThickness(FromMM(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        o = z.Outline(); o.NewOutline()
        for x, y in ((0, 0), (W, 0), (W, H), (0, H)):
            o.Append(P((x, y)))
        B.Add(z)

    pcbnew.SaveBoard(pcb, B)
    text = open(pcb, encoding="utf-8").read()              # pcbnew's Python API hides the stackup: write it as text
    assert "(stackup" not in text
    text = text.replace("\t(setup\n", "\t(setup\n" + STACK, 1)
    open(pcb, "w", encoding="utf-8").write(text)
    info = {"board": [W, H], "areas": AREAS, "body": BODY, "mcu_balls": mcu_ball, "swap": {n: list(v) for n, v in swap.items()},
            "lanes_swapped": lanes_swapped, "pads": {"%s %s" % k: list(v) for k, v in pads.items()},
            "routes": resolved, "ball_notes": notes, "breakout_notes": breakout_notes(resolved, mcu_ball)}
    json.dump(info, open(os.path.join(out_dir, "routes.json"), "w", encoding="utf-8"), indent=1)
    return info
