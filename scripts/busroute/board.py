"""Board access: a plain-Python snapshot of a .kicad_pcb, and the writer that puts routes into the file.

Reading uses pcbnew (LoadBoard, nothing is changed). Writing does NOT: tracks and vias are top-level
blocks of the board file, so the writer edits the text. That keeps everything else byte-identical, makes
the output deterministic (UUIDs are derived from the content) and avoids two pcbnew pitfalls of
docs/tools.md (collections going bad after board.Remove(), SaveBoard writing a default .kicad_pro).

Coordinates in the snapshot are LOCAL mm (file mm - origin). Layers are called L1 .. Ln in stack order
(L1 = F.Cu, Ln = B.Cu); `Board.cu` maps them to KiCad's names.
"""
import json, math, os, re, uuid

NS = uuid.UUID("6f0c2b0e-5d0a-4a57-9d1c-627573726f75")       # namespace of the generated UUIDs


class Pad:
    __slots__ = ("ref", "num", "net", "pos", "shape", "r", "poly", "layers", "smd", "hole", "box")

    @property
    def name(self):
        return "%s.%s" % (self.ref, self.num)


class Board:
    def __init__(self, path, origin=(0.0, 0.0)):
        import pcbnew
        self.path, self.origin = os.path.abspath(path), (float(origin[0]), float(origin[1]))
        b = pcbnew.LoadBoard(self.path)
        ox, oy = self.origin
        mm = pcbnew.ToMM
        L = lambda v: (round(mm(v.x) - ox, 6), round(mm(v.y) - oy, 6))
        ids = list(b.GetEnabledLayers().CuStack())
        self.cu = {"L%d" % (i + 1): ("F.Cu" if i == 0 else "B.Cu" if i == len(ids) - 1 else "In%d.Cu" % i) for i in range(len(ids))}
        lname = {lid: "L%d" % (i + 1) for i, lid in enumerate(ids)}
        self.layers = list(self.cu)
        # plane layers: type "power" in the board's layer table (H743 board: L2 ground, L5 the power blocks); no route
        # may put a track there (routes.py). Every other copper layer is a routing layer.
        self.planes = {lname[l] for l in ids if b.GetLayerType(l) == pcbnew.LT_POWER}
        self.pads, self.by_ref, self.fp, self.dup_pads = {}, {}, {}, []
        for f in b.GetFootprints():
            ref = f.GetReference()
            self.fp[ref] = {"pos": L(f.GetPosition()), "rot": f.GetOrientationDegrees(), "lib": f.GetFPID().GetUniStringLibId(), "pads": []}
            for p in f.Pads():
                q = Pad()
                q.ref, q.num, q.net, q.pos = ref, p.GetNumber(), p.GetNetname(), L(p.GetPosition())
                cus = [lname[l] for l in p.GetLayerSet().CuStack() if l in lname]
                if not cus:
                    continue
                q.layers = None if len(cus) == len(ids) else set(cus)
                q.smd = p.GetDrillSizeX() == 0
                q.hole = mm(max(p.GetDrillSizeX(), p.GetDrillSizeY())) / 2
                lay0 = [l for l in p.GetLayerSet().CuStack() if l in lname][0]
                sx, sy = mm(p.GetSizeX()), mm(p.GetSizeY())
                bb = p.GetBoundingBox()
                q.box = (mm(bb.GetLeft()) - ox, mm(bb.GetTop()) - oy, mm(bb.GetRight()) - ox, mm(bb.GetBottom()) - oy)
                q.r, q.poly = max(sx, sy) / 2, None
                if p.GetShape(lay0) == pcbnew.PAD_SHAPE_CIRCLE and abs(sx - sy) < 1e-9 and p.GetOffset(lay0).x == 0 and p.GetOffset(lay0).y == 0:
                    q.shape = "circle"
                else:
                    q.shape = "poly"
                    try:
                        o = p.GetEffectivePolygon(lay0, pcbnew.ERROR_OUTSIDE).Outline(0)
                        q.poly = [L(o.CPoint(i)) for i in range(o.PointCount())]
                    except Exception:
                        q.poly = [(q.box[0], q.box[1]), (q.box[2], q.box[1]), (q.box[2], q.box[3]), (q.box[0], q.box[3])]
                if q.name in self.pads:                     # a second pad with the same number (shield tabs, mounting pads)
                    self.dup_pads.append(self.pads[q.name])  # stays a pad of its net for routes and connectivity
                self.pads[q.name] = q
                self.by_ref.setdefault(ref, []).append(q)
                self.fp[ref]["pads"].append(q.name)
        self.areas, self.keepouts, self.zones = {}, [], []
        # board zones, then the keep-outs that footprints carry (an RJ45's "shield contact area"): those count as
        # keep-outs only, named "REF:name"
        fzones = [(f.GetReference(), z) for f in b.GetFootprints() for z in f.Zones() if z.GetIsRuleArea()]
        for owner, z in [(None, z) for z in b.Zones()] + fzones:
            o = z.Outline()
            polys = [[L(o.Outline(k).CPoint(i)) for i in range(o.Outline(k).PointCount())] for k in range(o.OutlineCount())]
            lays = [lname[l] for l in z.GetLayerSet().Seq() if l in lname]
            if owner is not None:
                if z.GetDoNotAllowTracks() or z.GetDoNotAllowVias():
                    self.keepouts += [{"name": "%s:%s" % (owner, z.GetZoneName() or "keep-out"), "layers": lays, "poly": pl,
                                       "tracks": z.GetDoNotAllowTracks(), "vias": z.GetDoNotAllowVias()} for pl in polys]
            elif z.GetIsRuleArea():
                if z.GetDoNotAllowTracks() or z.GetDoNotAllowVias():
                    self.keepouts += [{"name": z.GetZoneName(), "layers": lays, "poly": pl, "tracks": z.GetDoNotAllowTracks(), "vias": z.GetDoNotAllowVias()} for pl in polys]
                elif z.GetZoneName():
                    xs, ys = [p[0] for p in polys[0]], [p[1] for p in polys[0]]
                    R = (min(xs), min(ys), max(xs), max(ys))
                    rect = len(polys) == 1 and all(p[0] in (R[0], R[2]) and p[1] in (R[1], R[3]) for p in polys[0])
                    self.areas[z.GetZoneName()] = {"rect": R, "is_rect": rect, "layers": lays}
            else:
                self.zones += [{"net": z.GetNetname(), "name": z.GetZoneName(), "layers": lays, "poly": pl} for pl in polys]
        self.tracks, self.vias, self.arcs, self.arc_items = [], [], 0, []
        for t in b.GetTracks():
            n = t.GetNetname()
            if t.Type() == pcbnew.PCB_VIA_T:
                self.vias.append((n, L(t.GetPosition()), mm(t.GetWidth(pcbnew.F_Cu)), mm(t.GetDrill())))
            elif t.Type() == pcbnew.PCB_ARC_T:
                self.arcs += 1
                self.arc_items.append((n, lname[t.GetLayer()], L(t.GetStart()), L(t.GetMid()), L(t.GetEnd()), mm(t.GetWidth())))
                pts = self._arc(L(t.GetStart()), L(t.GetMid()), L(t.GetEnd()))
                self.tracks += [(n, lname[t.GetLayer()], a, c, mm(t.GetWidth()), True) for a, c in zip(pts, pts[1:])]
            else:
                self.tracks.append((n, lname[t.GetLayer()], L(t.GetStart()), L(t.GetEnd()), mm(t.GetWidth()), False))
        self.edges = []
        for d in b.GetDrawings():
            if d.GetLayer() != pcbnew.Edge_Cuts or not hasattr(d, "GetShape"):
                continue
            s = d.GetShape()
            if s == pcbnew.SHAPE_T_SEGMENT:
                self.edges.append((L(d.GetStart()), L(d.GetEnd())))
            elif s == pcbnew.SHAPE_T_ARC:
                pts = self._arc(L(d.GetStart()), L(d.GetArcMid()), L(d.GetEnd()))
                self.edges += list(zip(pts, pts[1:]))
            elif s == pcbnew.SHAPE_T_RECT:
                (x0, y0), (x1, y1) = L(d.GetStart()), L(d.GetEnd())
                c = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
                self.edges += [(c[i], c[(i + 1) % 4]) for i in range(4)]
            elif s == pcbnew.SHAPE_T_CIRCLE:
                c, r = L(d.GetCenter()), mm(d.GetRadius())
                pts = [(c[0] + r * math.cos(k * math.pi / 24), c[1] + r * math.sin(k * math.pi / 24)) for k in range(49)]
                self.edges += list(zip(pts, pts[1:]))
        self.stack = self._stackup(open(self.path, encoding="utf-8").read(400000))
        self.nets = {p.net for p in self.pads.values()} | {t[0] for t in self.tracks} | {v[0] for v in self.vias} | {z["net"] for z in self.zones}
        self.kicad_unconnected = b.GetConnectivity().GetUnconnectedCount(False)

    def connectivity(self, nets):
        """{net: (pads of the net, pads joined to its first pad)} from the copper that is in the file: track
        ends that coincide, vias, pads that contain a track end. Independent of the route model (it reads the
        file), and needed because kicad-cli's DRC lists at most 499 unconnected items per board."""
        out = {}
        for n in sorted(nets):
            pads = self.net_pads(n)
            parent = {}

            def find(x):
                while parent.setdefault(x, x) != x:
                    parent[x] = parent[parent[x]]; x = parent[x]
                return x
            key = lambda lay, p: (lay, round(p[0], 5), round(p[1], 5))
            for t in self.tracks:
                if t[0] == n:
                    parent[find(key(t[1], t[2]))] = find(key(t[1], t[3]))
            ends = [k for k in list(parent)]
            for v in self.vias:
                if v[0] == n:
                    for lay in self.layers[1:]:
                        parent[find(key(lay, v[1]))] = find(key(self.layers[0], v[1]))
            for p in pads:
                for k in ends:
                    if (p.layers is None or k[0] in p.layers) and math.hypot(k[1] - p.pos[0], k[2] - p.pos[1]) <= (p.r if p.shape == "circle" else 1e-4):
                        parent[find(k)] = find(("pad", p.name))
            roots = [find(("pad", p.name)) for p in pads]
            out[n] = (len(pads), sum(1 for r in roots if r == roots[0]) if roots else 0)
        return out

    @staticmethod
    def _arc(a, m, c, step=0.05):
        """Polyline through an arc given by start, mid, end."""
        d = 2 * (a[0] * (m[1] - c[1]) + m[0] * (c[1] - a[1]) + c[0] * (a[1] - m[1]))
        if abs(d) < 1e-12:
            return [a, c]
        ux = ((a[0] ** 2 + a[1] ** 2) * (m[1] - c[1]) + (m[0] ** 2 + m[1] ** 2) * (c[1] - a[1]) + (c[0] ** 2 + c[1] ** 2) * (a[1] - m[1])) / d
        uy = ((a[0] ** 2 + a[1] ** 2) * (c[0] - m[0]) + (m[0] ** 2 + m[1] ** 2) * (a[0] - c[0]) + (c[0] ** 2 + c[1] ** 2) * (m[0] - a[0])) / d
        r = math.hypot(a[0] - ux, a[1] - uy)
        a0, am, a1 = (math.atan2(p[1] - uy, p[0] - ux) for p in (a, m, c))
        sweep = (a1 - a0) % (2 * math.pi)
        if (am - a0) % (2 * math.pi) > sweep:
            sweep -= 2 * math.pi
        n = max(2, int(abs(sweep) * r / step))
        return [a] + [(ux + r * math.cos(a0 + sweep * i / n), uy + r * math.sin(a0 + sweep * i / n)) for i in range(1, n)] + [c]

    @staticmethod
    def _stackup(text):
        """[(KiCad layer name or None for a dielectric, thickness mm)] from the board file's (stackup ...)."""
        m = re.search(r"\n\t\t\(stackup\n(.*?)\n\t\t\)\n", text, re.S)
        out = []
        for blk in re.split(r"\n\t\t\t\(layer ", "\n" + m.group(1))[1:] if m else []:
            name = re.match(r'"([^"]+)"', blk).group(1)
            th = sum(float(x) for x in re.findall(r"\(thickness ([\d.]+)", blk))
            if name.endswith(".Cu"):
                out.append((name, th))
            elif "dielectric" in name:
                out.append((None, th))
        return out

    def via_height(self, la, lb):
        """Length KiCad's DRC adds for a via between layers la and lb (L names): everything strictly between,
        plus the full thickness of an outer end layer and half of an inner end layer. 0 without a stackup."""
        if la == lb or not self.stack:
            return 0.0
        names = [n for n, _ in self.stack]
        i, j = sorted((names.index(self.cu[la]), names.index(self.cu[lb])))
        h = 0.0
        for k in range(i, j + 1):
            n, th = self.stack[k]
            h += th / 2 if (k in (i, j) and n not in ("F.Cu", "B.Cu")) else th
        return round(h, 6)

    # ---- lookups
    def pad(self, name, net=None):
        """Pad by "REF.NUM", or by "REF" plus the net (the net's only pad on that part)."""
        if name in self.pads:
            return self.pads[name]
        if name in self.by_ref and net is not None:
            hit = [p for p in self.by_ref[name] if p.net == net]
            if len(hit) == 1:
                return hit[0]
            raise KeyError("%s has %d pads on net %s" % (name, len(hit), net))
        raise KeyError("no pad %r on the board" % (name,))

    def all_pads(self):
        """Every pad, including those that share their number with another pad of the footprint (self.pads, keyed
        by "REF.NUM", keeps only the last of them): obstacles and connectivity must see them all."""
        return list(self.pads.values()) + self.dup_pads

    def net_pads(self, net):
        """Every pad of the net, including pads that share their number with another pad of the footprint (which
        self.pads, keyed by "REF.NUM", keeps only once: reach those by their coordinates in a route)."""
        return [p for p in self.all_pads() if p.net == net]

    def rule_areas(self, names=None):
        """{name: rectangle} of the rule areas that change track width and clearance."""
        out = {}
        for n, a in self.areas.items():
            if names is None or n in names:
                if not a["is_rect"]:
                    raise ValueError("rule area %s is not an axis-parallel rectangle: not supported" % n)
                out[n] = a["rect"]
        return out

    def locked(self):
        d = os.path.dirname(self.path)
        return any(f.startswith("~") and f.endswith(".lck") for f in os.listdir(d))


# ---------------------------------------------------------------- writer (text)
def _num(v):
    s = ("%.6f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _q(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def old_items(dst, group):
    """What `group` wrote into `dst` last time, as recorded beside it: (set of segment keys (net, KiCad layer,
    x0, y0, x1, y1) in local mm, set of via keys (net, x, y)). Only shared groups record their segments."""
    side = os.path.splitext(dst)[0] + ".busroute.json"
    rec = json.load(open(side, encoding="utf-8")) if os.path.isfile(side) else {"groups": {}}
    old = rec["groups"].get(group, {})
    return ({tuple(s) for s in old.get("segs", [])}, {tuple(v) for v in old.get("extras", [])})


def write(src, dst, group, segs, vias, owned, origin=(0.0, 0.0), cu=None, shared=False, arcs=()):
    """Copy board file `src` to `dst` (may be the same path) with the group's copper replaced.

    segs   [(net, layer L-name, (x, y), (x, y), width)]   local mm
    vias   [(net, (x, y), diameter, drill, owned_net: bool)]   an un-owned via is an extra (stitching)
    arcs   [(net, layer L-name, start, mid, end, width)]   track arcs (serpentines; written after the segments)
    owned  the nets this group owns: every existing track, arc and via of them is removed first

    Also removed: whatever the same group wrote last time (kept in <dst>.busroute.json), so a net that left
    the group and old stitching vias do not stay behind. Nothing else in the file is touched.
    shared: the group owns no net (`owned` is ignored): it removes only its own copper of last time, found by
    position, so other groups' copper on the same nets (ground, power) stays.
    Returns {"removed": n, "segments": n, "vias": n}."""
    text = open(src, encoding="utf-8", newline="").read()
    eol = "\r\n" if "\r\n" in text[:2000] else "\n"
    lines = text.split("\n")
    side = os.path.splitext(dst)[0] + ".busroute.json"
    rec = json.load(open(side, encoding="utf-8")) if os.path.isfile(side) else {"groups": {}}
    old = rec["groups"].get(group, {"nets": [], "extras": []})
    if shared:
        owned = []
    gone = set(owned) | set(old["nets"])
    old_extra = {(n, x, y) for n, x, y in old["extras"]}
    old_segs = {tuple(k) for k in old.get("segs", [])}
    ox, oy = origin
    out, i, removed, last = [], 0, 0, None
    while i < len(lines):
        m = re.match(r"^\t\((segment|arc|via)\r?$", lines[i])
        if not m:
            out.append(lines[i]); i += 1
            continue
        j = i
        while not re.match(r"^\t\)\r?$", lines[j]):
            j += 1
        blk = lines[i:j + 1]
        net = next((re.match(r'^\t\t\(net "(.*)"\)\r?$', l).group(1) for l in blk if l.startswith('\t\t(net "')), None)
        if net is not None:
            net = net.replace('\\"', '"').replace("\\\\", "\\")
        drop = net in gone
        if not drop and m.group(1) == "via" and old_extra:
            at = next(re.match(r"^\t\t\(at ([-\d.]+) ([-\d.]+)", l) for l in blk if l.startswith("\t\t(at "))
            drop = (net, round(float(at.group(1)) - ox, 6), round(float(at.group(2)) - oy, 6)) in old_extra
        if not drop and m.group(1) == "segment" and old_segs:
            st = next(re.match(r"^\t\t\(start ([-\d.]+) ([-\d.]+)", l) for l in blk if l.startswith("\t\t(start "))
            en = next(re.match(r"^\t\t\(end ([-\d.]+) ([-\d.]+)", l) for l in blk if l.startswith("\t\t(end "))
            ly = next(re.match(r'^\t\t\(layer "([^"]+)"', l) for l in blk if l.startswith("\t\t(layer "))
            drop = (net, ly.group(1), round(float(st.group(1)) - ox, 6), round(float(st.group(2)) - oy, 6),
                    round(float(en.group(1)) - ox, 6), round(float(en.group(2)) - oy, 6)) in old_segs
        if drop:
            removed += 1
        else:
            out += blk; last = len(out)
        i = j + 1
    new = []
    for k, (net, layer, a, c, w) in enumerate(segs):
        key = "%s|seg|%s|%s|%r|%r|%r|%d" % (group, net, layer, a, c, w, k)
        new += ["\t(segment", "\t\t(start %s %s)" % (_num(a[0] + ox), _num(a[1] + oy)), "\t\t(end %s %s)" % (_num(c[0] + ox), _num(c[1] + oy)),
                "\t\t(width %s)" % _num(w), '\t\t(layer "%s")' % cu[layer], '\t\t(net "%s")' % _q(net), '\t\t(uuid "%s")' % uuid.uuid5(NS, key), "\t)"]
    for k, (net, layer, a, m, c, w) in enumerate(arcs):
        key = "%s|arc|%s|%s|%r|%r|%r|%r|%d" % (group, net, layer, a, m, c, w, k)
        new += ["\t(arc", "\t\t(start %s %s)" % (_num(a[0] + ox), _num(a[1] + oy)), "\t\t(mid %s %s)" % (_num(m[0] + ox), _num(m[1] + oy)),
                "\t\t(end %s %s)" % (_num(c[0] + ox), _num(c[1] + oy)), "\t\t(width %s)" % _num(w), '\t\t(layer "%s")' % cu[layer],
                '\t\t(net "%s")' % _q(net), '\t\t(uuid "%s")' % uuid.uuid5(NS, key), "\t)"]
    top, bot = cu["L1"], cu["L%d" % len(cu)]
    for k, (net, p, d, h, _) in enumerate(vias):
        key = "%s|via|%s|%r|%r|%r|%d" % (group, net, p, d, h, k)
        new += ["\t(via", "\t\t(at %s %s)" % (_num(p[0] + ox), _num(p[1] + oy)), "\t\t(size %s)" % _num(d), "\t\t(drill %s)" % _num(h),
                '\t\t(layers "%s" "%s")' % (top, bot), '\t\t(net "%s")' % _q(net), '\t\t(uuid "%s")' % uuid.uuid5(NS, key), "\t)"]
    if eol == "\r\n":
        new = [l + "\r" for l in new]
    if last is None:                                        # no track left in the file: before the zones / the tail
        last = next((k for k, l in enumerate(out) if re.match(r"^\t\((zone|group|generated|embedded_fonts)\b", l)), None)
        if last is None:
            last = max(k for k, l in enumerate(out) if l.rstrip("\r") == ")")
    out[last:last] = new
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    open(dst, "w", encoding="utf-8", newline="").write("\n".join(out))
    rec["groups"][group] = {"nets": sorted(owned), "extras": [[n, round(p[0], 6), round(p[1], 6)] for n, p, d, h, own in vias if not own or shared]}
    if shared:
        rec["groups"][group]["segs"] = [[n, cu[lay], round(a[0], 6), round(a[1], 6), round(c[0], 6), round(c[1], 6)] for n, lay, a, c, w in segs]
    json.dump(rec, open(side, "w", encoding="utf-8", newline="\n"), indent=1, sort_keys=True)
    out_ = {"removed": removed, "segments": len(segs), "vias": len(vias)}
    if arcs:
        out_["arcs"] = len(arcs)
    return out_
