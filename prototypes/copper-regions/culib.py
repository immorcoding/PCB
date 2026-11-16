"""PROTOTYPE shared helpers (issue 16): layers, colours, polygon conversion, anchors."""
import pcbnew

mm, FromMM = pcbnew.ToMM, pcbnew.FromMM
ERR = FromMM(0.002)
MITRE = pcbnew.CORNER_STRATEGY_ALLOW_ACUTE_CORNERS
ROUND = pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS
LAYERS = [(pcbnew.F_Cu, "F.Cu", "L1"), (pcbnew.In1_Cu, "In1.Cu", "L2"), (pcbnew.In2_Cu, "In2.Cu", "L3"),
          (pcbnew.In3_Cu, "In3.Cu", "L4"), (pcbnew.In4_Cu, "In4.Cu", "L5"), (pcbnew.B_Cu, "B.Cu", "L6")]
LID = {name: lid for lid, name, _ in LAYERS}
LNAME = {lid: name for lid, name, _ in LAYERS}
LNUM = {lid: num for lid, _, num in LAYERS}
COPPER_NETS = ["GND", "+3V3", "+5V", "+3V3A", "+12V", "+12V_IN", "SW_5V", "+1V8"]
COLOUR = {"GND": (150, 158, 150), "+3V3": (226, 104, 60), "+5V": (52, 120, 210), "+3V3A": (150, 80, 190),
          "+12V": (176, 30, 44), "+12V_IN": (150, 100, 40), "SW_5V": (0, 150, 136), "+1V8": (60, 160, 70)}
BGA = {"BGA_MCU": (32.0, 31.0, 44.0, 43.0), "BGA_SDRAM": (47.0, 29.5, 57.0, 44.5)}      # rule areas, local mm


def L(v):
    """Board point -> local mm."""
    return mm(v.x) - 100, mm(v.y) - 100


def V(x, y):
    return pcbnew.VECTOR2I(FromMM(x + 100), FromMM(y + 100))


def chain_pts(ch):
    return [L(ch.CPoint(i)) for i in range(ch.PointCount())]


def pieces(ps):
    """Each outline of a SHAPE_POLY_SET, with its holes, as a SHAPE_POLY_SET of its own."""
    out = []
    for i in range(ps.OutlineCount()):
        one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(ps.Outline(i))
        for h in range(ps.HoleCount(i)):
            one.AddHole(ps.Hole(i, h))
        out.append(one)
    return out


def in_bga(x, y):
    return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in BGA.values())


def anchors(board, net, lid):
    """Copper of a net that a pour on this layer is meant to join: (point, reach mm, kind, label)."""
    out = []
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == net:
            out.append((t.GetPosition(), mm(t.GetWidth(pcbnew.F_Cu)) / 2, "via", "via(%.2f,%.2f)" % L(t.GetPosition())))
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() != net:
                continue
            label = "%s.%s" % (fp.GetReference(), p.GetNumber())
            if p.HasHole():
                out.append((p.GetPosition(), max(mm(p.GetSizeX()), mm(p.GetSizeY())) / 2 + 0.3, "th", label))
            elif p.IsOnLayer(lid):
                out.append((p.GetPosition(), min(mm(p.GetSizeX()), mm(p.GetSizeY())) / 2, "smd", label))
    return out


def zones(board):
    return [z for z in board.Zones() if not z.GetIsRuleArea()]
