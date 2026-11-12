"""Draw a placement picture of a board: outline, courtyards, pads, ratsnest.

    D:\\KiCad\\bin\\python.exe scripts\\pcb_view.py <board.kicad_pcb> <out.png> [--no-rats] [--scale 36]

For qualitative review only (crowding, signal flow, crossings). Zone boxes and
labels are taken from Cmts.User. The ratsnest is a per-net minimum spanning
tree over pad centres; GND is skipped (it goes to the pour).
"""
import sys, math
import pcbnew
from PIL import Image, ImageDraw, ImageFont

mm = pcbnew.ToMM


def net_colour(name):
    n = name.lstrip("/")
    if n.startswith(("+", "VBUS", "VBAT")): return (220, 60, 50)
    if n.startswith("USB_"): return (40, 110, 230)
    if "OSC" in n: return (200, 120, 0)
    if n in ("NRST", "BOOT0", "SWDIO", "SWCLK"): return (150, 60, 190)
    return (110, 120, 130)


def main(path, out, rats=True, scale=36):
    b = pcbnew.LoadBoard(path)
    bb = b.GetBoardEdgesBoundingBox()
    x0, y0 = mm(bb.GetLeft()) - 2, mm(bb.GetTop()) - 2
    W, H = int((mm(bb.GetWidth()) + 4) * scale), int((mm(bb.GetHeight()) + 4) * scale)
    img = Image.new("RGB", (W, H), (250, 250, 247)); d = ImageDraw.Draw(img, "RGBA")
    try:
        font = ImageFont.truetype("arial.ttf", int(scale * 0.62)); big = ImageFont.truetype("arialbd.ttf", int(scale * 0.8))
    except OSError:
        font = big = ImageFont.load_default()
    X = lambda v: ((mm(v.x) - x0) * scale, (mm(v.y) - y0) * scale)

    def shape(s, colour, width):
        t = s.GetShape()
        if t == pcbnew.SHAPE_T_SEGMENT:
            d.line([X(s.GetStart()), X(s.GetEnd())], fill=colour, width=width)
        elif t == pcbnew.SHAPE_T_ARC:
            c = X(s.GetCenter()); r = mm(s.GetRadius()) * scale
            a0 = math.degrees(math.atan2(X(s.GetStart())[1] - c[1], X(s.GetStart())[0] - c[0]))
            a1 = math.degrees(math.atan2(X(s.GetEnd())[1] - c[1], X(s.GetEnd())[0] - c[0]))
            if s.GetArcAngle().AsDegrees() < 0: a0, a1 = a1, a0
            d.arc([c[0] - r, c[1] - r, c[0] + r, c[1] + r], a0, a1, fill=colour, width=width)

    for s in b.GetDrawings():
        if s.GetLayer() == pcbnew.Edge_Cuts and isinstance(s, pcbnew.PCB_SHAPE):
            shape(s, (20, 20, 20), 3)

    nets = {}
    for fp in b.GetFootprints():
        back = fp.GetLayer() == pcbnew.B_Cu
        cy = fp.GetCourtyard(pcbnew.B_CrtYd if back else pcbnew.F_CrtYd)
        for i in range(cy.OutlineCount()):
            o = cy.Outline(i)
            pts = [X(o.CPoint(k)) for k in range(o.PointCount())]
            d.polygon(pts, fill=(255, 225, 150, 70) if not back else (150, 200, 255, 70), outline=(190, 140, 40))
        for p in fp.Pads():
            c = X(p.GetPosition())
            box = p.GetBoundingBox()
            w, h = mm(box.GetWidth()) * scale / 2, mm(box.GetHeight()) * scale / 2
            col = net_colour(p.GetNetname()) if p.GetNetname() and p.GetNetname() != "GND" else (70, 70, 70)
            if p.GetNetname() == "": col = (190, 190, 190)
            try:
                poly = p.GetEffectivePolygon(pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu, pcbnew.ERROR_INSIDE)
                o = poly.Outline(0)
                d.polygon([X(o.CPoint(k)) for k in range(o.PointCount())], fill=col + (200,))
            except Exception:
                d.rectangle([c[0] - w, c[1] - h, c[0] + w, c[1] + h], fill=col + (200,))
            if p.GetNetname() and p.GetNetname() != "GND":
                nets.setdefault(p.GetNetname(), []).append(c)
    for layer, col in ((pcbnew.B_Cu, (40, 90, 220, 170)), (pcbnew.F_Cu, (210, 40, 40, 200))):
        for t in b.GetTracks():
            if t.Type() == pcbnew.PCB_TRACE_T and t.GetLayer() == layer:
                d.line([X(t.GetStart()), X(t.GetEnd())], fill=col, width=max(1, int(mm(t.GetWidth()) * scale)))
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            c = X(t.GetPosition()); r = 0.3 * scale
            d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=(30, 30, 30, 255), outline=(240, 200, 0))
    if rats:
        for name, pts in nets.items():
            pts = list(dict.fromkeys(pts))
            done, rest = [pts[0]], pts[1:]
            while rest:
                a, c = min(((a, c) for a in done for c in rest), key=lambda e: math.dist(*e))
                d.line([a, c], fill=net_colour(name) + (170,), width=max(1, scale // 18))
                done.append(c); rest.remove(c)
    for s in b.GetDrawings():
        if s.GetLayer() == pcbnew.Cmts_User:
            if isinstance(s, pcbnew.PCB_SHAPE): shape(s, (0, 140, 90), 2)
            elif isinstance(s, pcbnew.PCB_TEXT):
                d.text(X(s.GetPosition()), s.GetText(), fill=(0, 120, 80), font=big, anchor="lm")
    for fp in b.GetFootprints():
        c = X(fp.GetPosition())
        d.text(c, fp.GetReference(), fill=(0, 0, 0), font=font, anchor="mm",
               stroke_width=2, stroke_fill=(255, 255, 255))
    img.save(out)
    print("wrote", out, img.size)


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    sc = int(sys.argv[sys.argv.index("--scale") + 1]) if "--scale" in sys.argv else 36
    if "--scale" in sys.argv: a.remove(str(sc))
    main(a[0], a[1], "--no-rats" not in sys.argv, sc)
