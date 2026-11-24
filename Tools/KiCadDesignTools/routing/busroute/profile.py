"""The numbers a route is drawn with: one block, read from the project files (rule profile C).

    Profile.from_project(board.kicad_pcb)   reads <board>.kicad_pro and <board>.kicad_dru next to the board

Where each number comes from:
  inside a rule area   track width, clearance, via        the .kicad_dru rules that test enclosedByArea /
                                                           intersectsArea (fallback: the board-level floors
                                                           of the .kicad_pro, which are the in-area values)
  outside              track width, clearance, via        the net class of the net (.kicad_pro)
  everywhere           hole to copper, hole to hole, copper to board edge (.kicad_pro), shortest segment,
                       via-count and length limits per net class (.kicad_dru)
  not in any file      `extend` (how far past a rule-area edge a track stays thin), `chamfer` (the `sharp`
                       rule of docs/design-rules.md), `lane_min_seg`, the plane numbers of a via field
A routes file may override any attribute with PROFILE = {"extend": 0.3, ...}.
"""
import fnmatch, json, os, re


class Profile:
    w_area = 0.09             # track width inside a rule area
    clr_area = 0.09           # clearance when either object touches a rule area
    via_area = (0.30, 0.15)   # via (diameter, drill) when the whole via is inside a rule area
    extend = 0.3              # the track stays thin for this much straight beyond the area edge
    hole_clr = 0.2            # via hole edge to copper of another net
    pth_hole_clr = 0.3        # plated pad hole edge to copper of another net
    hole_hole = 0.254         # hole edge to hole edge
    edge_clr = 0.254          # copper to board edge
    min_seg = 0.1             # DRC: shortest track segment
    lane_min_seg = 0.15       # shortest piece a generator may draw
    chamfer = 0.35            # `sharp`: two corners the same way closer than this read as a right angle
    plane_clr = 0.2           # a plane's clearance round a via of another net (antipad = via + 2 x this)
    plane_web = 0.1           # copper that must remain between two antipads
    slot_max = 1.5            # longest chain of merged antipads accepted in a via field, mm
    tracks_per_channel = 1    # tracks between two neighbouring pads / two neighbouring vias
    area_free_classes = ()    # net classes whose pieces with a given width keep it inside rule areas (the .kicad_dru
                              # lets them be wider there, e.g. PWR); every other track is w_area inside an area

    def __init__(self):
        self.classes = {"Default": {"width": 0.2, "clearance": 0.2, "via": (0.6, 0.3), "priority": 1 << 31}}
        self.patterns = []                                  # (pattern, class)
        self.area_names = None                              # None = every named rule area without a keep-out flag
        self.limits = {}                                    # class -> {"length_max": mm, "via_max": n}
        self.sources = {}
        self._cls = {}

    # ---- per net
    def net_class(self, net):
        if net not in self._cls:
            hit = [c for pat, c in self.patterns if fnmatch.fnmatchcase(net or "", pat) and c in self.classes]
            self._cls[net] = min(hit, key=lambda c: self.classes[c]["priority"]) if hit else "Default"
        return self._cls[net]

    def width(self, net):
        return self.classes[self.net_class(net)]["width"]

    def clr(self, net):
        return self.classes[self.net_class(net)]["clearance"]

    def via_out(self, net):
        return self.classes[self.net_class(net)]["via"]

    def limit(self, net, key):
        return self.limits.get(self.net_class(net), {}).get(key)

    # ---- reading
    @classmethod
    def from_project(cls, pcb_path, override=None):
        p = cls()
        stem = os.path.splitext(pcb_path)[0]
        if os.path.isfile(stem + ".kicad_pro"):
            d = json.load(open(stem + ".kicad_pro", encoding="utf-8"))
            r = d.get("board", {}).get("design_settings", {}).get("rules", {})
            p.w_area = r.get("min_track_width", p.w_area)
            p.clr_area = r.get("min_clearance", p.clr_area)
            p.via_area = (r.get("min_via_diameter", p.via_area[0]), r.get("min_through_hole_diameter", p.via_area[1]))
            p.hole_clr = p.pth_hole_clr = r.get("min_hole_clearance", p.hole_clr)
            p.hole_hole = r.get("min_hole_to_hole", p.hole_hole)
            p.edge_clr = r.get("min_copper_edge_clearance", p.edge_clr)
            ns = d.get("net_settings", {})
            for c in ns.get("classes", []):
                p.classes[c["name"]] = {"width": c.get("track_width", 0.2), "clearance": c.get("clearance", 0.2),
                                        "via": (c.get("via_diameter", 0.6), c.get("via_drill", 0.3)), "priority": c.get("priority", 1 << 31)}
            p.patterns = [(x["pattern"], x["netclass"]) for x in ns.get("netclass_patterns") or []]
            p.sources["kicad_pro"] = os.path.basename(stem + ".kicad_pro")
        if os.path.isfile(stem + ".kicad_dru"):
            p._read_dru(open(stem + ".kicad_dru", encoding="utf-8").read())
            p.sources["kicad_dru"] = os.path.basename(stem + ".kicad_dru")
        for k, v in (override or {}).items():
            if not hasattr(p, k):
                raise ValueError("PROFILE: unknown key %r" % k)
            setattr(p, k, v)
        return p

    def _read_dru(self, text):
        text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
        names = []
        for m in re.finditer(r'\(rule\s+"([^"]+)"(.*?)(?=\n\(rule\s|\Z)', text, re.S):
            body = m.group(2)
            c = re.search(r'\(condition\s+"([^"]*)"\)', body)
            cond = c.group(1) if c else ""
            cons = {}
            for k in re.finditer(r"\(constraint\s+(\w+)((?:\s*\(\w+\s+[-\d.]+(?:mm)?\))*)", body):
                cons[k.group(1)] = {a: float(b) for a, b in re.findall(r"\((\w+)\s+([-\d.]+)", k.group(2))}
            names += re.findall(r"(?:intersectsArea|enclosedByArea)\('([^']+)'\)", cond)
            inside, touch = "enclosedByArea" in cond, "intersectsArea" in cond
            tw = cons.get("track_width", {})
            if inside and "min" in tw and tw.get("min") == tw.get("max"):
                self.w_area = tw["min"]
            if touch and "min" in cons.get("clearance", {}):
                self.clr_area = cons["clearance"]["min"]
            if inside and "Via" in cond and "min" in cons.get("via_diameter", {}) and "min" in cons.get("hole_size", {}):
                self.via_area = (cons["via_diameter"]["min"], cons["hole_size"]["min"])
            if "min" in cons.get("track_segment_length", {}):
                self.min_seg = cons["track_segment_length"]["min"]
            if "Through-hole" in cond and "min" in cons.get("hole_clearance", {}):
                self.pth_hole_clr = cons["hole_clearance"]["min"]
            k = re.fullmatch(r"\s*A\.NetClass == '([^']+)'\s*", cond)
            if k:
                lim = self.limits.setdefault(k.group(1), {})
                if "max" in cons.get("length", {}):
                    lim["length_max"] = cons["length"]["max"]
                if "max" in cons.get("via_count", {}):
                    lim["via_max"] = int(cons["via_count"]["max"])
                if "max" in cons.get("skew", {}):              # within-pair or group skew: a length rule too
                    lim["skew_max"] = cons["skew"]["max"]
        if names and self.area_names is None:
            self.area_names = sorted(set(names))

    def describe(self):
        return {"w_area": self.w_area, "clr_area": self.clr_area, "via_area": list(self.via_area), "extend": self.extend,
                "hole_clr": self.hole_clr, "pth_hole_clr": self.pth_hole_clr, "hole_hole": self.hole_hole, "edge_clr": self.edge_clr,
                "min_seg": self.min_seg, "lane_min_seg": self.lane_min_seg, "chamfer": self.chamfer, "plane_clr": self.plane_clr,
                "plane_web": self.plane_web, "slot_max": self.slot_max, "tracks_per_channel": self.tracks_per_channel,
                "area_free_classes": list(self.area_free_classes),
                "area_names": self.area_names, "limits": self.limits, "sources": self.sources}
