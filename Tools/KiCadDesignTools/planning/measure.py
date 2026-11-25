"""Length of nets on a board, traced pad to pad through tracks, arcs and vias (length-matching plans).

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.planning.measure <board dir> [board] [--nets N ...|--group G ...]
                                                                       [--json OUT] [--txt OUT]

board: a copy of the board (default: the board folder's own). Nets: --nets by name, --group by group (lane0 ..
laneN, data, addr, clock, bus), default the whole bus. Prints one line per net and the group lines (lanes: shortest
- longest and spread, routed and natural; the clock sum and the address lines against it, with the window of
length_groups.json); --json writes every net's record (the plan reads the same records), --txt the printed text.

What is measured (per net, a two-pad net):
  length    track segments + exact arc lengths + via heights, each via counted for the layers the route really
            changes between (KiCad's BOARD_STACKUP::GetLayerDistance, from core/stackup and [board] stackup)
  natural   the length with every serpentine block replaced by its chord
  blocks    serpentine blocks: runs of 3 or more arcs in which consecutive arcs are at most one segment apart and no
            via lies between them; per block the layer, ends, chord, added length and arc radius
  layers    track length per layer
  pieces    the route as polylines per layer (arcs as points every 0.03 mm), in order from the start pad: what
            planning/plan.py copies when a plan keeps a net or part of it
The trace starts at the net's pad on the first part of [length] start_refs that has one (else its first pad) and
follows the copper from there; `ok` = it ends on the other pad with every item of the net used.

The bus (board.toml): byte lanes from [schematic.swap] (lane k = <data_net>8k .. 8k+7 + <mask_net>k), the address /
command lines and the clock's pieces from [tune_sites] addr / clock, the address window from the length_groups.json
group named by [length] window_rule (lo / hi mm relative to the clock sum).
"""
import json, math, os, sys
from collections import defaultdict

ARC_STEP = 0.03            # points of an arc in `pieces`
MIN_ARCS = 3               # a serpentine block has at least this many arcs (single arcs are corners)


# ----------------------------------------------------------------------------- arcs
def arc_geom(a, m, b):
    """centre, radius, swept angle (signed) of the arc a -> m -> b."""
    ax, ay, bx, by, cx, cy = a[0], a[1], m[0], m[1], b[0], b[1]
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None, None, 0.0
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    a0 = math.atan2(ay - uy, ax - ux)
    a1 = math.atan2(by - uy, bx - ux)
    a2 = math.atan2(cy - uy, cx - ux)

    def norm(x):
        while x < 0:
            x += 2 * math.pi
        while x >= 2 * math.pi:
            x -= 2 * math.pi
        return x
    s02 = norm(a2 - a0)
    s01 = norm(a1 - a0)
    sweep = s02 if s01 <= s02 else s02 - 2 * math.pi
    return (ux, uy), r, sweep


def arc_len(arc):
    c, r, sw = arc_geom(arc["a"], arc["m"], arc["b"])
    if c is None:
        return math.hypot(arc["b"][0] - arc["a"][0], arc["b"][1] - arc["a"][1])
    return abs(sw) * r


def arc_points(arc, step=ARC_STEP):
    c, r, sw = arc_geom(arc["a"], arc["m"], arc["b"])
    if c is None:
        return [arc["a"], arc["b"]]
    n = max(2, int(abs(sw) * r / step) + 1)
    a0 = math.atan2(arc["a"][1] - c[1], arc["a"][0] - c[0])
    return [(c[0] + r * math.cos(a0 + sw * i / n), c[1] + r * math.sin(a0 + sw * i / n)) for i in range(n + 1)]


# ----------------------------------------------------------------------------- the bus of a board
def groups(cfg):
    """{"lanes": {k: nets}, "data", "addr", "clock", "bus": nets, "window": (lo, hi) or None, "start_refs"}."""
    sw = cfg.get("schematic.swap") or {}
    nl = sw.get("lanes", 0)
    dn, mn = sw.get("data_net", ""), sw.get("mask_net", "")
    lanes = {k: ["%s%d" % (dn, i) for i in range(8 * k, 8 * k + 8)] + ["%s%d" % (mn, k)] for k in range(nl)}
    data = ["%s%d" % (dn, i) for i in range(8 * nl)] + ["%s%d" % (mn, k) for k in range(nl)]
    addr = list(cfg.get("tune_sites.addr", []))
    clock = list(cfg.get("tune_sites.clock", []))
    window = None
    rule = cfg.get("length.window_rule")
    if rule:
        lg = json.load(open(cfg.path("length_groups.json"), encoding="utf-8"))
        g = [g for g in lg.get("groups", []) if g.get("rule") == rule]
        if not g:
            raise ValueError("length_groups.json has no group %r ([length] window_rule)" % rule)
        window = (g[0]["lo"], g[0]["hi"])
    return {"lanes": lanes, "data": data, "addr": addr, "clock": clock, "bus": data + addr + clock, "window": window,
            "start_refs": list(cfg.get("length.start_refs", []))}


def select(G, nets=None, names=None):
    if nets:
        return list(nets)
    if not names:
        return list(G["bus"])
    out = []
    for g in names:
        if g.startswith("lane") and g[4:].isdigit() and int(g[4:]) in G["lanes"]:
            out += G["lanes"][int(g[4:])]
        elif g in ("data", "addr", "clock", "bus"):
            out += G[g]
        else:
            raise SystemExit("unknown group %r (lane0 .. lane%d, data, addr, clock, bus)" % (g, len(G["lanes"]) - 1))
    return out


def via_heights(cfg):
    """via_h(la, lb) for L names, from the board's stackup."""
    from Tools.KiCadDesignTools.core import stackup
    st = stackup.for_board(cfg)
    cache = {}

    def via_h(la, lb):
        k = tuple(sorted((la, lb)))
        if k not in cache:
            cache[k] = st.via_height(cfg.kicad(k[0]), cfg.kicad(k[1]))
        return cache[k]
    return via_h


# ----------------------------------------------------------------------------- trace
def key(p):
    return (round(p[0], 3), round(p[1], 3))


def trace(board, net, start_refs, layers, via_h):
    """Ordered path of the net from its start pad to the other end: [("seg"|"arc", item, reversed, length) |
    ("via", (x, y), from layer, to layer, height)]."""
    items = [("seg", {"a": a, "b": b, "w": w, "layer": lay}) for (n, lay, a, b, w, is_arc) in board.tracks if n == net and not is_arc]
    items += [("arc", {"a": s, "m": m, "b": e, "w": w, "layer": lay}) for (n, lay, s, m, e, w) in board.arc_items if n == net]
    vias = {key(v[1]): v for v in board.vias if v[0] == net}
    pads = board.net_pads(net)
    adj = defaultdict(list)
    for i, (k, it) in enumerate(items):
        adj[(key(it["a"]), it["layer"])].append((i, 0))
        adj[(key(it["b"]), it["layer"])].append((i, 1))
    start = None
    for r in start_refs:
        hit = [p for p in pads if p.ref == r]
        if hit:
            start = hit[0]
            break
    if start is None:
        start = pads[0]
    rest = [p for p in pads if p is not start]
    end = rest[0] if rest else start
    pos = key(start.pos)
    cand = [l for l in (layers if start.layers is None else [l for l in layers if l in start.layers]) if adj[(pos, l)]]
    layer = cand[0] if cand else layers[0]
    used = set()
    path = []
    total = 0.0
    nv = 0
    while True:
        cand = [(i, e) for (i, e) in adj[(pos, layer)] if i not in used]
        if not cand:
            if pos in vias:                       # a layer change through a via
                nxt = [(l, [(i, e) for (i, e) in adj[(pos, l)] if i not in used]) for l in layers if l != layer]
                nxt = [(l, c) for l, c in nxt if c]
                if nxt:
                    l2 = nxt[0][0]
                    h = via_h(layer, l2)
                    path.append(("via", vias[pos][1], layer, l2, h))
                    total += h
                    nv += 1
                    layer = l2
                    continue
            break
        i, e = cand[0]
        used.add(i)
        k, it = items[i]
        L = math.hypot(it["b"][0] - it["a"][0], it["b"][1] - it["a"][1]) if k == "seg" else arc_len(it)
        path.append((k, it, e == 1, L))
        total += L
        pos = key(it["a"] if e == 1 else it["b"])
    ok = (pos == key(end.pos)) and len(used) == len(items) and len(pads) == 2
    return {"net": net, "path": path, "len": total, "vias": nv, "ok": ok, "start": start, "end": end, "unused": len(items) - len(used),
            "all_vias": len(vias), "pads": len(pads)}


def serp_blocks(tr):
    """Serpentine blocks: maximal runs of path items from an arc to an arc where consecutive arcs are separated by at
    most one segment (the hump legs) and no via."""
    path = tr["path"]
    idx = [i for i, it in enumerate(path) if it[0] == "arc"]
    blocks = []
    if not idx:
        return blocks
    run = [idx[0]]
    for i in idx[1:]:
        if i - run[-1] <= 2 and all(path[j][0] != "via" for j in range(run[-1], i)):
            run.append(i)
        else:
            blocks.append(run)
            run = [i]
    blocks.append(run)
    out = []
    for run in blocks:
        i0, i1 = run[0], run[-1]

        def ends(it):
            a, b = it[1]["a"], it[1]["b"]
            return (b, a) if it[2] else (a, b)
        p0 = ends(path[i0])[0]
        p1 = ends(path[i1])[1]
        chord = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        runlen = sum(path[j][3] for j in range(i0, i1 + 1))
        out.append({"i0": i0, "i1": i1, "chord": chord, "run": runlen, "arcs": len(run), "layer": path[i0][1]["layer"], "p0": p0, "p1": p1,
                    "r": arc_geom(path[i0][1]["a"], path[i0][1]["m"], path[i0][1]["b"])[1]})
    return out


def measure_net(board, net, start_refs, layers, via_h):
    """The record of one net (see the module text)."""
    tr = trace(board, net, start_refs, layers, via_h)
    sb = [b for b in serp_blocks(tr) if b["arcs"] >= MIN_ARCS]
    extra = sum(b["run"] - b["chord"] for b in sb)
    lay = {}
    for it in tr["path"]:
        if it[0] != "via":
            lay[it[1]["layer"]] = lay.get(it[1]["layer"], 0) + it[3]
    pts = []
    for it in tr["path"]:
        if it[0] == "via":
            continue
        a, b = it[1]["a"], it[1]["b"]
        if it[2]:
            a, b = b, a
        if it[0] == "arc":
            seq = arc_points(it[1])
            if it[2]:
                seq = seq[::-1]
        else:
            seq = [a, b]
        pts.append((it[1]["layer"], it[1]["w"], [(round(x, 4), round(y, 4)) for x, y in seq]))
    st, en = tr["start"], tr["end"]
    return {"len": round(tr["len"], 3), "natural": round(tr["len"] - extra, 3), "serp": round(extra, 3), "vias": tr["vias"], "ok": tr["ok"],
            "unused": tr["unused"], "all_vias": tr["all_vias"],
            "layers": {k: round(v, 2) for k, v in lay.items()},
            "via_list": [(round(it[1][0], 3), round(it[1][1], 3), it[2], it[3]) for it in tr["path"] if it[0] == "via"],
            "blocks": [{"layer": b["layer"], "humps_arcs": b["arcs"], "adds": round(b["run"] - b["chord"], 3), "chord": round(b["chord"], 3),
                        "from": [round(v, 3) for v in b["p0"]], "to": [round(v, 3) for v in b["p1"]], "r": round(b["r"], 3)} for b in sb],
            "from": [st.ref, st.num, [round(v, 3) for v in st.pos]],
            "to": [en.ref, en.num, [round(v, 3) for v in en.pos]],
            "pieces": pts}


def measure(cfg, board, nets):
    """{net: record} of the nets on the Board (routing/busroute/board.py)."""
    G = groups(cfg)
    via_h = via_heights(cfg)
    layers = cfg.signal_layers()
    return {n: measure_net(board, n, G["start_refs"], layers, via_h) for n in nets}


def report(res, G):
    """The printed table: a line per net, the lanes, the clock and address lines, totals (lines)."""
    lines = ["%-12s %-5s %-4s %7s %7s %6s %4s  %-28s %s" % ("net", "from", "to", "len", "natural", "serp", "vias", "layers (mm)", "serpentine blocks")]
    for n, r in res.items():
        lines.append("%-12s %-5s %-4s %7.2f %7.2f %6.2f %4d  %-28s %s%s" % (
            n, r["from"][1], r["to"][1], r["len"], r["natural"], r["serp"], r["vias"],
            " ".join("%s %.1f" % kv for kv in sorted(r["layers"].items())),
            "; ".join("%s x%.2f-%.2f y%.2f-%.2f +%.2f" % (b["layer"], min(b["from"][0], b["to"][0]), max(b["from"][0], b["to"][0]),
                                                           min(b["from"][1], b["to"][1]), max(b["from"][1], b["to"][1]), b["adds"]) for b in r["blocks"]),
            "" if r["ok"] and not r["unused"] else "  !! trace incomplete (unused %d)" % r["unused"]))
    for k, lane in G["lanes"].items():
        if not all(n in res for n in lane):
            continue
        ls = [res[n]["len"] for n in lane]
        ns = [res[n]["natural"] for n in lane]
        lines.append("lane %d: routed %.2f - %.2f spread %.2f (longest %s) | natural %.2f - %.2f spread %.2f" % (
            k, min(ls), max(ls), max(ls) - min(ls), max(lane, key=lambda n: res[n]["len"]), min(ns), max(ns), max(ns) - min(ns)))
    if G["clock"] and G["addr"] and all(n in res for n in G["clock"] + G["addr"]):
        clk = sum(res[n]["len"] for n in G["clock"])
        al = [res[n]["len"] for n in G["addr"]]
        lines.append("clock %.2f (%s, natural %.2f); address %.2f - %.2f, vs clock %+.2f / %+.2f" % (
            clk, " + ".join("%s %.2f" % (n.split("_", 1)[-1], res[n]["len"]) for n in G["clock"]),
            sum(res[n]["natural"] for n in G["clock"]), min(al), max(al), min(al) - clk, max(al) - clk))
        if G["window"]:
            lo, hi = G["window"]
            out = [n for n in G["addr"] if not (clk + lo <= res[n]["len"] <= clk + hi)]
            lines.append("address window %+g .. %+g mm of the clock: %d / %d inside%s" % (
                lo, hi, len(G["addr"]) - len(out), len(G["addr"]), "; outside: " + " ".join(out) if out else ""))
    lines.append("total %.1f mm, serpentine total %.1f mm" % (sum(r["len"] for r in res.values()), sum(r["serp"] for r in res.values())))
    return lines


def main(argv):
    import argparse
    from Tools.KiCadDesignTools.core import config
    from Tools.KiCadDesignTools.routing.busroute.board import Board
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(prog="python -m Tools.KiCadDesignTools.planning.measure", description=__doc__.split("\n\n")[0])
    ap.add_argument("board_dir")
    ap.add_argument("board", nargs="?")
    ap.add_argument("--nets", nargs="+")
    ap.add_argument("--group", nargs="+")
    ap.add_argument("--json")
    ap.add_argument("--txt")
    a = ap.parse_args(argv)
    cfg = config.load(a.board_dir)
    G = groups(cfg)
    nets = select(G, a.nets, a.group)
    board = Board(os.path.abspath(a.board or cfg.pcb), cfg.origin)
    res = measure(cfg, board, nets)
    txt = "\n".join(report(res, G))
    print(txt)
    if a.json:
        json.dump(res, open(a.json, "w", encoding="utf-8"), indent=1)
    if a.txt:
        open(a.txt, "w", encoding="utf-8").write(txt + "\n")
    return 0 if all(r["ok"] and not r["unused"] for r in res.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
