"""Pictures of the placement: pads and courtyards of the board, the whole board and chosen windows.

    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\place_view.py dump [board]     writes out/layout/place_view.json
    python stm32h743_sdram/place_view.py draw [x0 y0 x1 y1 name]             writes out/layout/placement.png (or <name>.png)

Two steps because KiCad's Python has no matplotlib. Local mm (board-file mm minus 100). Top pads red,
bottom pads blue, through-hole grey; courtyards as outlines (bottom dashed); references at the centre.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "layout")
JS = os.path.join(OUT, "place_view.json")


def dump(path):
    import pcbnew
    b = pcbnew.LoadBoard(path)
    mm = lambda v: v / 1e6 - 100
    parts = []
    for fp in b.GetFootprints():
        bot = fp.GetLayer() == pcbnew.B_Cu
        cy = fp.GetCourtyard(pcbnew.B_CrtYd if bot else pcbnew.F_CrtYd)
        bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False, False)
        pads = []
        for p in fp.Pads():
            r = p.GetBoundingBox()
            pads.append([mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom()),
                         "th" if p.HasHole() else ("b" if p.IsOnLayer(pcbnew.B_Cu) else "t"), p.GetNetname()])
        parts.append(dict(ref=fp.GetReference(), bot=bot, pos=[mm(fp.GetPosition().x), mm(fp.GetPosition().y)],
                          box=[mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())], pads=pads))
    e = b.GetBoardEdgesBoundingBox()
    os.makedirs(OUT, exist_ok=True)
    json.dump(dict(edge=[mm(e.GetLeft()), mm(e.GetTop()), mm(e.GetRight()), mm(e.GetBottom())], parts=parts), open(JS, "w"))
    print("wrote", JS, len(parts), "parts")


def draw(win=None, name="placement"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    d = json.load(open(JS))
    x0, y0, x1, y1 = win or d["edge"]
    scale = 14.0 / (x1 - x0)
    fig, ax = plt.subplots(figsize=(14, 14 * (y1 - y0) / (x1 - x0)))
    ax.add_patch(Rectangle((d["edge"][0], d["edge"][1]), d["edge"][2] - d["edge"][0], d["edge"][3] - d["edge"][1], fill=False, lw=1.5))
    col = {"t": "#d9534f", "b": "#3b7dd8", "th": "#777777"}
    for p in d["parts"]:
        bx = p["box"]
        if bx[2] < x0 or bx[0] > x1 or bx[3] < y0 or bx[1] > y1:
            continue
        ax.add_patch(Rectangle((bx[0], bx[1]), bx[2] - bx[0], bx[3] - bx[1], fill=False, lw=0.6, ls="--" if p["bot"] else "-",
                               ec="#3b7dd8" if p["bot"] else "#b8860b"))
        for a, b_, c, e, kind, net in p["pads"]:
            ax.add_patch(Rectangle((a, b_), c - a, e - b_, fc=col[kind], ec="none", alpha=0.75))
            if win and (c - a) * scale > 0.25 and net:
                ax.text((a + c) / 2, (b_ + e) / 2, net.replace("FMC_", ""), fontsize=4, ha="center", va="center")
        ax.text((bx[0] + bx[2]) / 2, bx[1] - 0.05 if win else (bx[1] + bx[3]) / 2, p["ref"], fontsize=6 if win else 4.5,
                ha="center", va="bottom" if win else "center", color="#1a3f7a" if p["bot"] else "black")
    ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_aspect("equal"); ax.grid(True, lw=0.2)
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=110, bbox_inches="tight")
    print(os.path.join(OUT, name + ".png"))


if __name__ == "__main__":
    if sys.argv[1] == "dump":
        dump(sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "stm32h743_sdram.kicad_pcb"))
    else:
        a = sys.argv[2:]
        draw([float(v) for v in a[:4]] if len(a) >= 4 else None, a[4] if len(a) > 4 else "placement")
