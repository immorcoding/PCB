"""PROTOTYPE review (issue 21): extra checks for 5_no_detour on top of review/remeasure.py and
review/4_combined/recheck4.py (whose board reader is reused; nothing from lib/, no pcbnew).

Usage: D:/KiCad/bin/python.exe review/5_no_detour/recheck5.py [key ...]      (default: 5_no_detour 4_combined 1_baseline)
Prints per board: swept area (own raster), hull with the package outlines inset 0.1 mm, bus length under the
SDRAM body per layer (segments and arcs), and for the first key also:
 - per net: in-plane detour = length - serpentine gain - via heights - octilinear direct distance, and how far
   the route with the serpentines taken out runs west / north (against the bus direction), split by where
 - vias: in the strip x 19..22, outside the package bodies
 - serpentine blocks: start / end line, row pitch and free gap to the next row, lead before / after,
   equal height inside the block, SDCLK pitch, clock height against the data heights
"""
import json, math, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "4_combined"))
import recheck4 as R

G = 0.05


def bus_items(B):
    return [s for s in B["segs"] + B["arcs"] if s["net"].startswith("/FMC_")]


def pts_of(s, step=0.01):
    return R.arc_pts(s, step) if "m" in s else R.seg_pts(s["a"], s["b"], step)


def length_of(s):
    if "m" in s:
        c, rad, a1, sw = R.arc_geom(s)
        return abs(sw) * rad
    return math.hypot(s["b"][0] - s["a"][0], s["b"][1] - s["a"][1])


def space(B, inset=0.0):
    b1 = (R.BODY["U1"][0] + inset, R.BODY["U1"][1] + inset, R.BODY["U1"][2] - inset, R.BODY["U1"][3] - inset)
    b2 = (R.BODY["U2"][0] + inset, R.BODY["U2"][1] + inset, R.BODY["U2"][2] - inset, R.BODY["U2"][3] - inset)
    pts = []
    grid = {l: np.zeros((int(40 / G), int(30 / G)), bool) for l in ("L1", "L4", "L6")}
    for s in bus_items(B):
        out = [p for p in pts_of(s, 0.02) if not R.inrect(p, b1) and not R.inrect(p, b2)]
        pts += out
        r = s["w"] / 2 + 0.127
        k = int(r / G) + 1
        g = grid[R.LAY[s["layer"]]]
        for x, y in out:
            i, j = int(x / G), int(y / G)
            for a in range(i - k, i + k + 1):
                for b in range(j - k, j + k + 1):
                    if math.hypot((a + 0.5) * G - x, (b + 0.5) * G - y) <= r:
                        g[a, b] = True
    for v in B["vias"]:
        if v["net"].startswith("/FMC_") and not R.inrect(v["p"], b1) and not R.inrect(v["p"], b2):
            pts.append(v["p"])
    allg = grid["L1"] | grid["L4"] | grid["L6"]
    return {"hull": R.hull_area(pts), "swept": allg.sum() * G * G, "swept_by": {l: round(float(g.sum() * G * G), 1) for l, g in grid.items()}}


def under_body(B):
    out = {}
    for s in bus_items(B):
        pp = pts_of(s, 0.005)
        if len(pp) < 2:
            continue
        frac = sum(1 for p in pp if R.inrect(p, R.BODY["U2"])) / len(pp)
        out[R.LAY[s["layer"]]] = out.get(R.LAY[s["layer"]], 0.0) + length_of(s) * frac
    return out


def octi(a, b):
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)


def where(p):
    if R.inrect(p, R.BODY["U2"]):
        return "under SDRAM body"
    if R.inrect(p, R.BODY["U1"]):
        return "under MCU body"
    return "open board"


def detail(key):
    B = R.load(os.path.join(R.ROOT, "out", key, "routetune.kicad_pcb"))
    nets = sorted(set(s["net"] for s in B["segs"] if s["net"].startswith("/FMC_")))
    print("\n-- %s: in-plane detour and backward travel (serpentines replaced by their chord)" % key)
    print("net     length  serp   vias_mm  direct  in-plane detour | west  north  (where the backward pieces are)")
    blocks = {}
    tot_w = tot_n = 0.0
    for n in nets:
        m = R.measure(B, n)
        bl = R.blocks_of(m["path"])
        blocks[n] = bl
        gain = sum(b["gain"] for b in bl)
        pads = {p["ref"]: p["p"] for p in B["pads"] if p["net"] == n}
        direct = octi(pads["U1"], pads["U2"])
        det = m["length"] - gain - m["via_mm"] - direct
        west = north = 0.0
        wh = {}
        for o in R.skeleton(B, n):
            if o[0] == "via":
                continue
            a, b = o[1], o[2]
            w, nn = max(0.0, a[0] - b[0]), max(0.0, a[1] - b[1])
            west += w; north += nn
            if w > 1e-6 or nn > 1e-6:
                k = "%s %s" % (o[0], where(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)))
                wh[k] = wh.get(k, 0.0) + max(w, nn)
        tot_w += west; tot_n += north
        print("%-6s %7.3f %6.3f  %5.3f  %7.3f  %6.3f %s | %5.2f %5.2f  %s" % (
            n[5:], m["length"], gain, m["via_mm"], direct, det, "**" if det > 2.0 else "  ", west, north,
            ", ".join("%s %.2f" % kv for kv in sorted(wh.items()))))
    print("sum west %.2f, north %.2f" % (tot_w, tot_n))

    print("\n-- vias")
    strip = [(v["net"][5:], v["p"]) for v in B["vias"] if v["net"].startswith("/FMC_") and R.STRIP[0] < v["p"][0] < R.STRIP[1]]
    off = [(v["net"][5:], v["p"]) for v in B["vias"] if v["net"].startswith("/FMC_") and where(v["p"]) == "open board"]
    areas = [a["rect"] for a in B["areas"].values()]
    noarea = [(v["net"][5:], v["p"]) for v in B["vias"] if v["net"].startswith("/FMC_") and not any(R.inrect(v["p"], a) for a in areas)]
    print("in the strip x 19..22: %d %s; outside both rule areas: %d; outside both package bodies (in the 1 mm band): %d %s" % (
        len(strip), strip, len(noarea), len(off), off))

    print("\n-- serpentine blocks")
    rows = []
    for n in nets:
        for b in blocks[n]:
            hs = [abs(h) for h in b["humps"]]
            eq = max(hs) - min(hs) < 0.002
            x0, x1 = sorted((b["start"][0], b["end"][0])); y0, y1 = sorted((b["start"][1], b["end"][1]))
            rows.append((b["layer"], round(y0, 3), n[5:], b, hs, eq))
            print("%-6s %s  from (%.3f, %.3f) to (%.3f, %.3f)  %d x %.3f %s  pitch %s  lead %.3f / %.3f  width %.4f  %s" % (
                n[5:], b["layer"], b["start"][0], b["start"][1], b["end"][0], b["end"][1], len(hs), max(hs),
                "both sides" if b["both"] else "one side", b["pitch"], b["lead_before"], b["lead_after"], b["w"],
                "" if eq else "UNEQUAL %s" % hs))
            if not eq:
                R.finding("%s: block with unequal humps %s" % (n, hs))
            if n == "/FMC_SDCLK" and b["pitch"] != [0.5]:
                R.finding("SDCLK leg pitch %s" % b["pitch"])
            if n != "/FMC_SDCLK" and b["pitch"] != [0.3]:
                R.finding("%s leg pitch %s" % (n, b["pitch"]))
            if len(hs) < 3:
                R.finding("%s: block of %d humps (wart)" % (n, len(hs)))
    for lay in ("L1", "L4", "L6"):
        rr = sorted([r for r in rows if r[0] == lay and not r[3]["both"]], key=lambda r: r[1])
        for a, b in zip(rr, rr[1:]):
            if abs(a[3]["start"][0] - b[3]["start"][0]) < 0.01:
                print("  %s rows %s (y %.3f) -> %s (y %.3f): pitch %.3f, free gap above the lower block's humps %.3f, start line x %.3f, ends x %.3f / %.3f" % (
                    lay, a[2], a[1], b[2], b[1], b[1] - a[1], b[1] - a[1] - max(b[4]), a[3]["start"][0], a[3]["end"][0], b[3]["end"][0]))
    data = [max(r[4]) for r in rows if r[2] != "SDCLK"]
    clk = [max(r[4]) for r in rows if r[2] == "SDCLK"]
    if clk:
        print("clock hump %.3f (block width %.3f); data humps %.3f .. %.3f, mean %.3f; clock / tallest data = %.2f, / mean = %.2f" % (
            clk[0], 2 * clk[0], min(data), max(data), sum(data) / len(data), clk[0] / max(data), clk[0] / (sum(data) / len(data))))
    # SDCLK: thin track by place
    thin = {}
    for s in B["segs"] + B["arcs"]:
        if s["net"] == "/FMC_SDCLK" and abs(s["w"] - 0.09) < 1e-6:
            pp = pts_of(s, 0.005)
            for p in pp:
                k = "inside MCU area" if R.inrect(p, (7, 6, 19, 18)) else ("inside SDRAM area" if R.inrect(p, (22, 8.4, 32, 23.4)) else "outside the areas")
                thin[k] = thin.get(k, 0.0) + length_of(s) / len(pp)
    print("SDCLK 0.09 track: %s" % {k: round(v, 2) for k, v in thin.items()})
    M = json.load(open(os.path.join(R.ROOT, "out", key, "metrics.json"), encoding="utf-8"))
    clkL = M["nets"]["FMC_SDCLK"]["length_mm"] if "nets" in M and "FMC_SDCLK" in M["nets"] and "length_mm" in M["nets"]["FMC_SDCLK"] else None
    return B


def main():
    keys = sys.argv[1:] or ["5_no_detour", "4_combined", "1_baseline"]
    for k in keys:
        B = R.load(os.path.join(R.ROOT, "out", k, "routetune.kicad_pcb"))
        M = json.load(open(os.path.join(R.ROOT, "out", k, "metrics.json"), encoding="utf-8"))
        s0, s1, ub = space(B), space(B, 0.1), under_body(B)
        print("%-16s hull %.1f (metrics %.1f)  hull with outlines inset 0.1: %.1f  swept %.1f (metrics %.1f) by layer %s  under SDRAM body %.1f (%s)" % (
            k, s0["hull"], M["space"]["bus_hull_area_mm2"] if "bus_hull_area_mm2" in M["space"] else float("nan"), s1["hull"], s0["swept"],
            M["space"]["bus_swept_area_mm2"]["all"], s0["swept_by"], sum(ub.values()), " ".join("%s %.1f" % kv for kv in sorted(ub.items()))))
    detail(keys[0])
    print("\nFINDINGS (%d)" % len(R.FIND))
    for f in R.FIND:
        print("  " + f)


if __name__ == "__main__":
    main()
