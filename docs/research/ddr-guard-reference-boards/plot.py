"""plot.py <dump.json> <out.png> <layer> <xmin> <xmax> <ymin> <ymax> <signal-regex> [width_in]
To-scale copper plot: signals blue/orange (by net), GND tracks green, GND vias green circles, other vias grey, pads grey outlines,
GND zone filled polygons (light green) when the dump carries them."""
import sys, json, re, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon
from matplotlib.collections import LineCollection, PatchCollection

def main(dump, out, layer, x0, x1, y0, y1, rx, width=14):
    d = json.load(open(dump)); rx = re.compile(rx)
    gnd = re.compile(r"^(GND|VSS)", re.I)
    fig, ax = plt.subplots(figsize=(width, width * (y1 - y0) / (x1 - x0)), dpi=110)
    inb = lambda p: x0 - 2 <= p[0] <= x1 + 2 and y0 - 2 <= p[1] <= y1 + 2
    def seg(t, c, alpha=1):
        lw = t["w"] * 72 / 25.4 * width / (x1 - x0) * 25.4 / 1 / (1)  # points per mm scale below
    # linewidth in points: 1 mm of data = width*72/(x1-x0) / 1 inch... compute explicitly
    pts_per_mm = width * 72 / 25.4 / ((x1 - x0) / 25.4) / 25.4 * 25.4
    pts_per_mm = (width * 72) / (x1 - x0)
    # filled GND zones
    for z in d["zones"]:
        f = z["filled"].get(layer)
        if not f or isinstance(f, str) or not gnd.match(z["net"] or "GND") and z["net"]: continue
        if z["net"] and not gnd.match(z["net"]): continue
        for p in f:
            if any(inb(q) for q in p["o"][::3]):
                ax.add_patch(Polygon(p["o"], closed=True, fc="#bfe3bf", ec="none", alpha=.5, zorder=1))
                for h in p["h"]:
                    ax.add_patch(Polygon(h, closed=True, fc="white", ec="none", zorder=1.1))
    cols = {}
    for t in d["tracks"]:
        if t["l"] != layer or not (inb(t["a"]) or inb(t["b"])): continue
        if gnd.match(t["net"]): c, z = "#1a9a1a", 3
        elif rx.search(t["net"]): c, z = cols.setdefault(t["net"], plt.cm.tab20(len(cols) % 20)), 4
        else: c, z = "#c8c8c8", 2
        ax.plot([t["a"][0], t["b"][0]], [t["a"][1], t["b"][1]], color=c, lw=max(.4, t["w"] * pts_per_mm), solid_capstyle="round", zorder=z)
    for a in d["arcs"]:
        if a["l"] == layer and (inb(a["a"]) or inb(a["b"])):
            ax.plot([a["a"][0], a["m"][0], a["b"][0]], [a["a"][1], a["m"][1], a["b"][1]], color="red", lw=a["w"] * pts_per_mm, zorder=4)
    for v in d["vias"]:
        if inb(v["p"]) and v["l0"] == "TOP" or inb(v["p"]) and v["l1"] == "TOP" or inb(v["p"]):
            g = gnd.match(v["net"]) is not None
            ax.add_patch(Circle(v["p"], v["w"] / 2, fc="#1a9a1a" if g else ("#ff7f0e" if rx.search(v["net"]) else "#999"), ec="k", lw=.3, alpha=.8, zorder=5))
    for p in d["pads"]:
        if p["side"] == "TOP" and layer == "TOP" or p["side"] == "BOTTOM" and layer == "BOTTOM":
            if inb(p["p"]):
                ax.add_patch(Circle(p["p"], p["s"][0] / 2, fc="none", ec="#d62728" if rx.search(p["net"]) else "#777", lw=.6, zorder=6))
    import os
    cut = os.environ.get("CUT")            # e.g. "x=126": draw the cross-section line
    if cut:
        ax_, v = cut.split("="); v = float(v)
        (ax.axvline if ax_ == "x" else ax.axhline)(v, color="k", ls="--", lw=.8, zorder=9)
    ax.set_xlim(x0, x1); ax.set_ylim(y1, y0)  # y down as in the board file
    ax.set_aspect("equal"); ax.set_xlabel("x (mm)"); ax.set_ylabel("y (mm)"); ax.grid(alpha=.2)
    sx = x0 + (x1 - x0) * .05; sy = y1 - (y1 - y0) * .05
    ax.plot([sx, sx + 1], [sy, sy], "k-", lw=3); ax.text(sx, sy - (y1 - y0) * .03, "1 mm", fontsize=9)
    ax.set_title("%s  layer %s  (signals coloured by net; green = GND)" % (re.sub(r".*[\\/]", "", dump), layer))
    fig.savefig(out, bbox_inches="tight"); print("saved", out)

if __name__ == "__main__":
    a = sys.argv
    main(a[1], a[2], a[3], *map(float, a[4:8]), a[8], *(float(a[9]),) if len(a) > 9 else ())
