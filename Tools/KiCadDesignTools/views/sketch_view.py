"""Draw copper.sketch as pictures, one per layer that has drawn regions (for review; not a check).

    python -m Tools.KiCadDesignTools.views.sketch_view <board dir> <out dir>

Any Python >= 3.11 with matplotlib. Shows the board outline, the package bodies with their rule areas and the
mounting holes (from place.toml: [outline], [rule_areas], [holes]) and every drawn region of the copper sketch
([copper] sketch) with its net name; `whole` regions are named in the title only.
"""
import os, re, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle

from Tools.KiCadDesignTools.core import config
from Tools.KiCadDesignTools.placement.place import Plan


def read_sketch(path):
    regions, cur = [], None
    for raw in open(path, encoding="utf-8"):
        line = raw.split("#")[0].strip()
        if not line:
            continue
        w = line.split()
        if w[0] == "region":
            cur = {"name": w[1], "net": w[2], "layer": w[3], "whole": "whole" in w[4:], "pts": []}
            regions.append(cur)
        elif cur is not None and re.match(r"^-?[\d.]+,", w[0]):
            cur["pts"] += [tuple(float(v) for v in p.split(",")) for p in w]
    return regions


def main(cfg, out):
    os.makedirs(out, exist_ok=True)
    regions = read_sketch(cfg.path(cfg.need("copper.sketch")))
    plan = Plan(cfg, fan=False)
    W, H = plan.width, plan.height
    bodies = [(a["label"], a["centre"], a["size"]) for a in plan.areas]
    colours = {}
    palette = plt.get_cmap("tab20")
    for layer in sorted({r["layer"] for r in regions if not r["whole"]}):
        fig, ax = plt.subplots(figsize=(12, 12 * H / W))
        ax.add_patch(Rectangle((0, 0), W, H, fill=False, lw=1.5))
        for name, (cx, cy), (bw, bh) in bodies:
            ax.add_patch(Rectangle((cx - bw / 2, cy - bh / 2), bw, bh, fill=False, lw=1, ls="-", ec="0.3"))
            m = plan.margin
            ax.add_patch(Rectangle((cx - bw / 2 - m, cy - bh / 2 - m), bw + 2 * m, bh + 2 * m, fill=False, lw=0.6, ls="--", ec="0.5"))
            ax.text(cx, cy, name, ha="center", va="center", fontsize=8, color="0.3")
        for hx, hy in (plan.place[ref][:2] for ref in plan.holes):
            ax.add_patch(plt.Circle((hx, hy), 1.6, fill=False, ec="0.3"))
        for r in regions:
            if r["layer"] != layer or r["whole"]:
                continue
            col = colours.setdefault(r["net"], palette(len(colours) % 20))
            ax.add_patch(Polygon(r["pts"], closed=True, fc=col, ec="k", lw=0.6, alpha=0.55))
            xs, ys = [p[0] for p in r["pts"]], [p[1] for p in r["pts"]]
            small = (max(xs) - min(xs)) < 8
            if small:
                ax.text((min(xs) + max(xs)) / 2, min(ys) - 0.4, r["net"], ha="center", va="bottom", fontsize=6.5)
            else:                       # inside the first corner: the middle of an L-shaped block can lie outside it
                ax.text(xs[0] + 1.0, ys[0] + 1.6, r["net"], ha="left", va="center", fontsize=8)
        whole = [r["net"] for r in regions if r["layer"] == layer and r["whole"]]
        ax.set_title("%s: drawn regions; the rest of the layer is %s" % (layer, ", ".join(whole) or "empty"))
        ax.set_xlim(-2, W + 2); ax.set_ylim(H + 2, -2); ax.set_aspect("equal"); ax.grid(True, lw=0.3, alpha=0.5)
        ax.set_xticks(range(0, int(W) + 1, 5)); ax.set_yticks(range(0, int(H) + 1, 5))
        fig.savefig(os.path.join(out, "copper_%s.png" % layer), dpi=90, bbox_inches="tight")
        plt.close(fig)
        print(os.path.join(out, "copper_%s.png" % layer))


if __name__ == "__main__":
    main(config.load(sys.argv[1]), sys.argv[2])
