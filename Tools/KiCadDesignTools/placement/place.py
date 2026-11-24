"""Placement of a board from its table <board dir>/place.toml: outline, mounting holes, rule areas and every part.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.placement.place <board dir> [--pcb <other board file>] [--rot <angle>]

--pcb and --rot are for trials on a copy of the board (line-order sketches of other rotations of the part placed
beside another, the SDRAM of stm32h743_sdram).

Local frame (mm): origin at [board] origin of board.toml, x right, y down. Rotations are KiCad footprint orientations
in degrees (counter-clockwise seen from the top). Re-running moves every part listed in [parts] back to its table
position, redraws Edge.Cuts (a rectangle with rounded corners, [outline]), the rule areas ([rule_areas]: package
body + margin) and their F.Cu no-pour keep-outs, and parks every part that is not listed in rows below the board.
A fourth element "B" puts a part on the bottom. [shifts] adds a block's (dx, dy) to the parts it lists; [fan] names
the BGA block plan (bga_fan.json) whose decoupling caps and placed parts replace the table's positions. The project
file next to the board keeps its bytes (SaveBoard rewrites it).
"""
import json, math, os, sys

from Tools.KiCadDesignTools.core import config

EDGE_WIDTH = 0.1                      # Edge.Cuts line width, mm
PARK_BELOW, PARK_ROW, PARK_GAP = 12.0, 160.0, 1.0   # parked rows: start below the board, row length, gap between parts


class Plan:
    """The board's place.toml resolved: parts in placing order, outline, rule areas. Pure Python (no pcbnew), so
    the views can read it too."""

    def __init__(self, cfg, rot=None, fan=True):
        d = cfg.datafile("place.toml")
        if not d:
            raise config.ConfigError("%s: no place.toml" % cfg.dir)
        self.cfg = cfg
        o = d["outline"]
        self.width, self.height, self.corner_r = o["width"], o["height"], o["corner_r"]
        self.holes = list(d.get("holes", {}).get("refs", []))
        self.bodies = {k: tuple(v) for k, v in d.get("bodies", {}).items()}
        self.margin = d.get("rule_areas", {}).get("margin", 0.0)
        self.mask_zero = tuple(d.get("pads", {}).get("mask_margin_zero", []))
        self.park_skip = tuple(d.get("park", {}).get("skip", []))
        self.turned = None            # (name, table centre, rotation) of the part --rot turns (the first one beside another)
        shift = {}
        for blk in d.get("shifts", {}).values():
            for ref in blk.get("refs", []):
                shift[ref] = tuple(blk["d"])
        place = {}
        for ref, v in d["parts"].items():
            if isinstance(v, dict):   # beside another part: east of it, `gap` between the package bodies, centres level
                r = v["rot"]
                first = self.turned is None
                if first and rot is not None:
                    r = rot
                place[ref] = (*self.beside(place, v["east_of"], ref, v["gap"], r), r)
                if first:
                    self.turned = (v.get("name", ref), place[ref][:2], r)
                continue
            x, y, *rest = v
            if ref in shift:
                dx, dy = shift[ref]
                x, y = round(x + dx, 4), round(y + dy, 4)
            place[ref] = (x, y, *rest)
        # rule areas: the parts' table positions (before the block plan), the bodies at their rotation
        self.areas = []
        for a in d.get("rule_areas", {}).get("areas", []):
            x, y = place[a["ref"]][:2]
            self.areas.append(dict(name=a["name"], ref=a["ref"], label=a.get("label", a["ref"]), no_pour=a.get("no_pour"),
                                   centre=(x, y), size=self.size(a["ref"], place[a["ref"]][2])))
        if fan and d.get("fan", {}).get("file"):
            path = cfg.path(d["fan"]["file"])
            if os.path.isfile(path):
                for _ref, _r in json.load(open(path, encoding="utf-8")).items():
                    for _c in (_r or {}).get("caps", []):
                        place[_c["ref"]] = (_c["pos"][0], _c["pos"][1], _c["rot"] % 360, "B")
                    for _ref2, _v in (_r or {}).get("placed", {}).items():
                        place[_ref2] = tuple(_v)
        self.place = place

    def size(self, ref, rot):
        b = self.bodies[ref]
        return b if rot % 180 == 0 else (b[1], b[0])

    def beside(self, place, of, ref, gap, rot):
        w = self.size(ref, rot)[0]
        return (place[of][0] + self.bodies[of][0] / 2 + gap + w / 2, place[of][1])


def outline(board, plan, V):
    import pcbnew
    from pcbnew import FromMM as mm
    w, h, r = plan.width, plan.height, plan.corner_r
    def seg(p, q):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(*p)); s.SetEnd(V(*q)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(EDGE_WIDTH)); board.Add(s)
    def arc(c, a0):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_ARC)
        pt = lambda a: (c[0] + r * math.cos(math.radians(a)), c[1] + r * math.sin(math.radians(a)))
        s.SetArcGeometry(V(*pt(a0)), V(*pt(a0 + 45)), V(*pt(a0 + 90)))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(EDGE_WIDTH)); board.Add(s)
    seg((r, 0), (w - r, 0)); seg((w, r), (w, h - r)); seg((w - r, h), (r, h)); seg((0, h - r), (0, r))
    arc((r, r), 180); arc((w - r, r), 270); arc((w - r, h - r), 0); arc((r, h - r), 90)


def rule_areas(board, plan):
    import pcbnew
    from pcbnew import FromMM as mm
    OX, OY = plan.cfg.origin
    areas = [(a["name"], (a["centre"], a["size"]), pcbnew.LSET.AllCuMask(), False) for a in plan.areas]
    f_cu = pcbnew.LSET(); f_cu.AddLayer(pcbnew.F_Cu)
    areas += [(a["no_pour"], (a["centre"], a["size"]), f_cu, True) for a in plan.areas if a["no_pour"]]
    for name, ((cx, cy), (bw, bh)), layers, no_fill in areas:
        z = pcbnew.ZONE(board)
        z.SetIsRuleArea(True); z.SetZoneName(name); z.SetLayerSet(layers)
        for f in ("SetDoNotAllowTracks", "SetDoNotAllowVias", "SetDoNotAllowPads", "SetDoNotAllowFootprints"):
            getattr(z, f)(False)
        z.SetDoNotAllowZoneFills(no_fill)
        hx, hy = bw / 2 + plan.margin, bh / 2 + plan.margin
        ch = pcbnew.SHAPE_LINE_CHAIN()
        for x, y in ((cx - hx, cy - hy), (cx + hx, cy - hy), (cx + hx, cy + hy), (cx - hx, cy + hy)):
            ch.Append(mm(OX + x), mm(OY + y))
        ch.SetClosed(True)
        z.Outline().AddOutline(ch)
        board.Add(z)


def park(board, fps, plan):
    """Parts without a position yet: rows below the board, left to right by reference, on the top side."""
    import pcbnew
    from pcbnew import VECTOR2I, FromMM as mm, ToMM
    OX, OY = plan.cfg.origin
    x, y, row_h = 0.0, plan.height + PARK_BELOW, 0.0
    key = lambda fp: (fp.GetReference().rstrip("0123456789"), int("".join(ch for ch in fp.GetReference() if ch.isdigit()) or 0))
    for fp in sorted(fps, key=key):
        fp.SetOrientationDegrees(0)
        bb = fp.GetBoundingBox(False)
        w, h = ToMM(bb.GetWidth()) + PARK_GAP, ToMM(bb.GetHeight()) + PARK_GAP
        if x + w > PARK_ROW:
            x, y, row_h = 0.0, y + row_h, 0.0
        c = fp.GetPosition()
        fp.SetPosition(VECTOR2I(c.x + mm(OX + x) - bb.GetLeft(), c.y + mm(OY + y) - bb.GetTop()))
        x += w; row_h = max(row_h, h)


def main(argv):
    if not argv or argv[0].startswith("--"):
        print(__doc__)
        return 2
    cfg = config.load(argv[0])
    PCB = cfg.pcb
    if "--pcb" in argv:
        PCB = os.path.abspath(argv[argv.index("--pcb") + 1])
    rot = int(argv[argv.index("--rot") + 1]) if "--rot" in argv else None
    plan = Plan(cfg, rot)
    PLACE = plan.place
    import pcbnew
    from pcbnew import VECTOR2I, FromMM as mm
    OX, OY = cfg.origin
    V = lambda x, y: VECTOR2I(mm(OX + x), mm(OY + y))
    board = pcbnew.LoadBoard(PCB)
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    missing = sorted(set(PLACE) - set(fps))
    if missing:
        sys.exit("not on the board (run net2pcb first): " + " ".join(missing))
    for ref, (x, y, rot_, *side) in PLACE.items():
        fp = fps[ref]
        if (fp.GetLayer() == pcbnew.B_Cu) != bool(side):
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(rot_)
        fp.SetPosition(V(x, y))
    for ref in plan.mask_zero:
        for pad in fps[ref].Pads():
            pad.SetLocalSolderMaskMargin(0)
    park(board, [fp for ref, fp in fps.items() if ref not in PLACE and not ref.startswith(plan.park_skip)], plan)
    # Everything that is read from the board is read above: after the first board.Remove() pcbnew's
    # collections are unusable in this process (docs/tools.md), so the old outline and rule areas are
    # listed first, removed together, and only then are the new ones added.
    names = {a["name"] for a in plan.areas} | {a["no_pour"] for a in plan.areas if a["no_pour"]}
    old = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    old += [z for z in board.Zones() if z.GetIsRuleArea() and z.GetZoneName() in names]
    for item in old:
        board.Remove(item)
    outline(board, plan, V)
    rule_areas(board, plan)
    # SaveBoard also rewrites the project file next to the board (pcbnew's defaults filled in, classes reordered;
    # same rules). project.make_project is that file's source: keep its bytes.
    pro = os.path.splitext(PCB)[0] + ".kicad_pro"
    keep = open(pro, "rb").read() if os.path.isfile(pro) else None
    pcbnew.SaveBoard(PCB, board)
    if keep is not None:
        with open(pro, "wb") as f:
            f.write(keep)
    msg = "placed %d parts, parked %d; board %g x %g mm" % (len(PLACE), len(fps) - len(PLACE), plan.width, plan.height)
    if plan.turned:
        name, (x, y), r = plan.turned
        msg += "; %s at (%.2f, %.2f) rot %d" % (name, x, y, r)
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
