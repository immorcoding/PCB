"""Place reference designators on the silkscreen so they do not sit on pads,
on each other, on other parts' silk or over the board edge.

    D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.finishing.silk_refs <board.kicad_pcb>

For every footprint it tries a ring of positions around the part (two text
angles) and keeps the nearest free one. A reference with no free spot is hidden
from the silkscreen (it is still on the Fab layer). Text is 0.8 x 0.8 mm, 0.15 mm
thick, the project minimum. Vias are ignored: they are tented.
"""
import sys
import pcbnew

mm, MM = pcbnew.ToMM, pcbnew.FromMM
GAP = 0.15


def box(bb, grow=0.0):
    return (mm(bb.GetLeft()) - grow, mm(bb.GetTop()) - grow, mm(bb.GetRight()) + grow, mm(bb.GetBottom()) + grow)


def hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def main(path):
    b = pcbnew.LoadBoard(path)
    e = box(b.GetBoardEdgesBoundingBox(), -0.4)                       # stay 0.4 mm inside the outline
    obst = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            for silk, cu in ((pcbnew.F_SilkS, pcbnew.F_Cu), (pcbnew.B_SilkS, pcbnew.B_Cu)):
                if p.IsOnLayer(cu):
                    obst[silk].append((box(p.GetBoundingBox(), GAP), fp.GetReference()))
        for g in fp.GraphicalItems():
            if g.GetLayer() in obst and not isinstance(g, pcbnew.PCB_TEXT):
                obst[g.GetLayer()].append((box(g.GetBoundingBox(), 0.05), fp.GetReference()))
    placed, hidden = 0, []
    order = sorted(b.GetFootprints(), key=lambda f: -f.GetCourtyard(pcbnew.F_CrtYd if f.GetLayer() == pcbnew.F_Cu else pcbnew.B_CrtYd).BBox().GetArea())
    for fp in order:
        ref = fp.Reference()
        silk = pcbnew.F_SilkS if fp.GetLayer() == pcbnew.F_Cu else pcbnew.B_SilkS
        ref.SetLayer(silk); ref.SetVisible(True)
        ref.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8))); ref.SetTextThickness(MM(0.15))
        ref.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER); ref.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        cy = box(fp.GetCourtyard(pcbnew.F_CrtYd if silk == pcbnew.F_SilkS else pcbnew.B_CrtYd).BBox())
        cx, cyc = (cy[0] + cy[2]) / 2, (cy[1] + cy[3]) / 2
        hw, hh = (cy[2] - cy[0]) / 2, (cy[3] - cy[1]) / 2
        cands = []
        for ang in (0, 90):
            ref.SetTextAngleDegrees(ang); ref.SetPosition(pcbnew.VECTOR2I(MM(cx), MM(cyc)))
            tb = box(ref.GetBoundingBox())
            tw, th = (tb[2] - tb[0]) / 2, (tb[3] - tb[1]) / 2
            for extra in (0.1, 0.5, 0.9, 1.4):
                for k in range(-4, 5):
                    f = k / 4
                    cands += [(ang, cx + f * hw, cyc - hh - th - extra + 0.3), (ang, cx + f * hw, cyc + hh + th + extra - 0.3),
                              (ang, cx - hw - tw - extra + 0.3, cyc + f * hh), (ang, cx + hw + tw + extra - 0.3, cyc + f * hh)]
        cands.sort(key=lambda c: (abs(c[1] - cx) + abs(c[2] - cyc), c[0]))
        for ang, x, y in cands:
            ref.SetTextAngleDegrees(ang); ref.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
            tb = box(ref.GetBoundingBox(), 0.05)
            if tb[0] < e[0] or tb[1] < e[1] or tb[2] > e[2] or tb[3] > e[3]:
                continue
            if any(hit(tb, o) for o, _ in obst[silk]):
                continue
            obst[silk].append((box(ref.GetBoundingBox(), GAP), fp.GetReference()))
            placed += 1
            break
        else:
            ref.SetVisible(False); hidden.append(fp.GetReference())
        val = fp.Value()
        if val.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            val.SetVisible(False)
    pcbnew.SaveBoard(path, b)
    print(f"references placed: {placed}; hidden (no free spot): {' '.join(sorted(hidden)) or 'none'}")


if __name__ == "__main__":
    main(sys.argv[1])
