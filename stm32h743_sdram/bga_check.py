"""bga_plan.py check: the verdict of the grid model (bga_grid.py) per MCU signal ball for a given state.

State = a geo.json (bga_plan.py dump of any board, routed or not). Every MCU signal ball that is not an SDRAM
ball is judged on its own against everything else that is on the board (leave one out: the net's own tracks and
vias do not count, so a ball that is routed on the board must come out "ok" unless the model is too strict):

  ok       a path of at most VIA_MAX vias to its target, not longer than the straight estimate + DETOUR
  detour   a path exists only with more vias or more length than that ("only by a detour")
  slot     a path exists only through a via site that joins plane clearance holes into a chain longer than
           --slot-max ("only with a slot above X mm"); the chain it needs is given
  blocked  no path over L1 / L4 / L6 at all
Target of a net: its other pads when they are inside the window, else the edge of the window on the side(s)
where they are (the gate towards the destination). The verdicts are per ball; they do not add up to a capacity
statement (two balls may be "ok" through the same channel): that is the planner's job.
"""
import json, math, os, sys, time
import numpy as np
import bga_grid as G

MCU, SDRAM = "U201", "U301"
WINDOW = (27.0, 23.0, 64.0, 51.0)
VIA_MAX = 3
DETOUR = 15.0
TOL = G.STEP / 2             # the judged state is a real board: its copper is not on the grid (bga_grid.Field.track_free)
POWER = ("GND", "+3V3_MCU", "+3V3_SDRAM", "VDDA_MCU", "VCAP1", "VCAP2")


def is_signal(net):
    return bool(net) and net not in POWER and not net.startswith("unconnected-") and not net.startswith("+")


def half_lattice(pads, area, shrink):
    """The half-pitch lattice of a BGA inside its rule area: ball positions, ball-gap points and the points
    between two neighbouring balls, continued to the edge of the area."""
    xs = sorted({p["pos"][0] for p in pads}); ys = sorted({p["pos"][1] for p in pads})
    pitch = min(b - a for a, b in zip(xs, xs[1:]))
    h = pitch / 2
    out = []
    kx0 = int(math.ceil((area[0] + shrink - xs[0]) / h - 1e-9)); kx1 = int(math.floor((area[2] - shrink - xs[0]) / h + 1e-9))
    ky0 = int(math.ceil((area[1] + shrink - ys[0]) / h - 1e-9)); ky1 = int(math.floor((area[3] - shrink - ys[0]) / h + 1e-9))
    for kx in range(kx0, kx1 + 1):
        for ky in range(ky0, ky1 + 1):
            out.append((round(xs[0] + kx * h, 4), round(ys[0] + ky * h, 4)))
    return out


def candidate_sites(geo, field, fine=0.05):
    """Via candidates: the half-pitch lattices of the two BGAs inside their rule areas, and every point of a
    0.05 mm grid (a real board's vias are not on the lattice). Small vias where they are wholly inside a rule
    area, 0.45 / 0.2 elsewhere."""
    sites = set()
    for ref, an in ((MCU, "BGA_MCU"), (SDRAM, "BGA_SDRAM")):
        pads = [p for p in geo["pads"] if p["ref"] == ref]
        if pads and an in geo["areas"]:
            sites.update(half_lattice(pads, geo["areas"][an]["rect"], field.via_in[0] / 2))
    m = int(round(0.3 / G.STEP))
    for i in range(m, field.nx - m):
        if abs(round(field.xs[i] / fine) * fine - field.xs[i]) > 1e-6:
            continue
        for j in range(m, field.ny - m):
            if abs(round(field.ys[j] / fine) * fine - field.ys[j]) < 1e-6:
                sites.add((round(float(field.xs[i]), 4), round(float(field.ys[j]), 4)))
    return sorted(s for s in sites if field.inside(s, 0.3))


class Sites:
    """The candidates as arrays, their legality against given fields and (lazily) the plane chain each would make."""

    def __init__(self, geo, field, sites, slots):
        self.f, self.sites, self.slots = field, sites, slots
        self.index = {s: k for k, s in enumerate(sites)}
        self.P = np.array(sites)
        self.I = np.round((self.P[:, 0] - field.x0) / G.STEP).astype(int); self.J = np.round((self.P[:, 1] - field.y0) / G.STEP).astype(int)
        small = np.zeros(len(sites), bool); inA = np.zeros(len(sites), bool)
        r = field.via_in[0] / 2
        for a in field.areas:
            small |= (self.P[:, 0] >= a[0] + r - 1e-9) & (self.P[:, 0] <= a[2] - r + 1e-9) & (self.P[:, 1] >= a[1] + r - 1e-9) & (self.P[:, 1] <= a[3] - r + 1e-9)
            inA |= (self.P[:, 0] >= a[0] - 1e-9) & (self.P[:, 0] <= a[2] + 1e-9) & (self.P[:, 1] >= a[1] - 1e-9) & (self.P[:, 1] <= a[3] + 1e-9)
        self.d = np.where(small, field.via_in[0], field.via_out[0]); self.h = np.where(small, field.via_in[1], field.via_out[1])
        self.clr = np.where(inA, field.clr_area, field.clr_out)
        self.need = np.maximum(self.d / 2 + self.clr, self.h / 2 + field.hole_clr)
        self.chain = {}
        from scipy.spatial import cKDTree
        self.tree = cKDTree(np.array([v[1] for v in slots.vias])) if slots.vias else None

    def legal(self, D, H, own_pads=()):
        """May a via stand at each candidate? D / H: the net's opened fields; own_pads: Items of the net's own
        pads, which a via must keep off like any other pad (no via on a pad)."""
        ok = H[self.J, self.I] >= self.h / 2 + self.f.hole_hole - G.EPS
        for l in G.LAYERS:
            ok &= D[l][self.J, self.I] >= self.need - G.EPS
        for it in own_pads:
            b = it.box
            near = np.nonzero(ok & (self.P[:, 0] > b[0] - 1) & (self.P[:, 0] < b[2] + 1) & (self.P[:, 1] > b[1] - 1) & (self.P[:, 1] < b[3] + 1))[0]
            if len(near):
                d = G.item_dist(it, self.P[near, 0], self.P[near, 1])
                ok[near[d < self.need[near] - G.EPS]] = False
        return ok

    def chain_of(self, k):
        """Longest plane chain through a signal via at candidate k (cached)."""
        if k not in self.chain:
            p, d = self.sites[k], float(self.d[k])
            if self.tree is None or not self.tree.query_ball_point(p, 1.0):
                self.chain[k] = d + 2 * G.PLANE_CLR
            else:
                self.chain[k] = self.slots.with_via("<signal>", p, d)
        return self.chain[k]

    def within(self, ok, slot_max):
        idx = np.nonzero(ok)[0]
        keep = np.array([self.chain_of(int(k)) <= slot_max + 1e-6 for k in idx], bool)
        out = np.zeros(len(self.sites), bool)
        out[idx[keep]] = True
        return out


def net_targets(geo, net, field, ball):
    """([(layer, point)], straight estimate, description) of the net's target as seen from `ball`."""
    others = [p for p in geo["pads"] if p["net"] == net and not (p["ref"] == MCU)]
    ends, desc, est = [], [], []
    b = ball["pos"]
    for p in others:
        q = p["pos"]
        if field.inside(q, 0.2):
            lays = p["layers"] or list(G.LAYERS)
            for l in lays:
                if l in G.LAYERS:
                    ends.append((l, tuple(q)))
            desc.append("%s.%s" % (p["ref"], p["num"]))
            est.append(_oct(b, q))
            continue
        sides = []
        if q[1] > field.y1 - 0.2: sides.append("S")
        if q[1] < field.y0 + 0.2: sides.append("N")
        if q[0] < field.x0 + 0.2: sides.append("W")
        if q[0] > field.x1 - 0.2: sides.append("E")
        for s in sides:
            ends += gate_cells(field, s)
            desc.append("gate " + s)
            est.append({"S": field.y1 - b[1], "N": b[1] - field.y0, "W": b[0] - field.x0, "E": field.x1 - b[0]}[s])
    return ends, (min(est) if est else 0.0), sorted(set(desc))


def gate_cells(field, side, inset=0.2, step=0.1):
    out = []
    if side in "NS":
        y = field.y0 + inset if side == "N" else field.y1 - inset
        x = field.x0 + inset
        while x <= field.x1 - inset:
            out += [(l, (round(x, 4), round(y, 4))) for l in G.LAYERS]
            x += step
    else:
        x = field.x0 + inset if side == "W" else field.x1 - inset
        y = field.y0 + inset
        while y <= field.y1 - inset:
            out += [(l, (round(x, 4), round(y, 4))) for l in G.LAYERS]
            y += step
    return out


def _oct(a, b):
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)


def path_items(net, pieces, field):
    """The copper of a planned or found route as Items (for the next net of a joint run)."""
    out = []
    for pc in pieces:
        if pc[0] == "via":
            d, h = field.via_size(pc[1])
            out.append(G.Item(net, ("L1", "L2", "L3", "L4", "L5", "L6"), "round", a=tuple(pc[1]), r=d / 2, hole=h / 2, tag="via"))
        else:
            pts = [p for p in pc[1] if not isinstance(p, str)]
            for p, q in zip(pts, pts[1:]):
                w = field.w_area if (field.is_area(p) and field.is_area(q)) else field.geo["width"].get(net, 0.2032)
                out.append(G.Item(net, (pc[0],), "seg", a=tuple(p), b=tuple(q), r=w / 2, tag="track"))
    return out


def check_state(geo, slot_max=3.0, nets=None, window=None, log=None, joint=False, reserve=()):
    """-> {net: dict(ball, verdict, vias, length, estimate, chain, target, routed, grid)} for the MCU's non-SDRAM
    signal balls (or the given nets, in the given order when joint).
    joint: each found route becomes copper for the nets after it (one deterministic order; a lower bound on
    how many can be drawn together, not a proof that the others cannot).
    reserve: [(net or None, layers, (x0, y0, x1, y1))] boxes kept free of every other net's tracks and vias."""
    t0 = time.time()
    extra = [G.Item(n or "<reserved>", tuple(ls), "poly", poly=[(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])], tag="reserve") for n, ls, b in reserve]
    field = G.Field(geo, window or WINDOW, items=G.scene_items(geo, extra=extra))
    slots = G.Slots(geo, [(n, p, d) for n, p, d, h in geo["vias"]])
    S = Sites(geo, field, candidate_sites(geo, field), slots)
    maze = G.Maze(field)
    balls = {p["net"]: p for p in geo["pads"] if p["ref"] == MCU and is_signal(p["net"])}
    routed = {n for n, *_ in geo["tracks"]}
    out = {}
    order = list(nets) if nets else sorted(n for n in balls if not n.startswith("FMC_"))
    for net in order:
        ball = balls[net]
        D, H = field.opened(net)
        width = geo["width"].get(net, 0.2032)
        legal = S.legal(D, H, [it for it in field.items if it.net == net and it.tag not in ("via", "track")])
        ends, est, desc = net_targets(geo, net, field, ball)
        start = [("L1", tuple(ball["pos"]))]
        res = {"ball": ball["num"], "routed": net in routed, "estimate": round(est, 2), "target": desc, "chain": None, "grid": False}
        got = None
        for kind, tol in (("ok", 0.0), ("ok", TOL), ("slot", TOL)):
            masks = {l: field.track_free(l, width, D, H, tol=tol) for l in G.LAYERS}
            sel = S.within(legal, slot_max) if kind == "ok" else legal
            vol = maze.volume(masks, S, sel)
            got = maze.route(vol, start, ends)
            if got:
                pieces, length, vias = G.path_pieces(got[1])
                pieces = [pc if pc[0] == "via" else (pc[0], G.tidy(field, pc[1], masks[pc[0]])) for pc in pieces]
                length = sum(math.dist(a, b) for pc in pieces if pc[0] != "via" for a, b in zip(pc[1], pc[1][1:]))
                res.update(vias=vias, length=round(length, 2), pieces=pieces, grid=tol > 0)
                if kind == "slot":
                    used = [pc[1] for pc in pieces if pc[0] == "via"]
                    res["chain"] = round(max(S.chain_of(S.index[p]) for p in used), 3)
                    res["verdict"] = "slot"
                else:
                    res["verdict"] = "ok" if vias <= VIA_MAX and length <= est + DETOUR else "detour"
                break
        if not got:
            res.update(verdict="blocked", vias=None, length=None, pieces=None)
        out[net] = res
        if joint and got and res["verdict"] != "slot":
            new = path_items(net, res["pieces"], field)
            for it in new:
                field.items.append(it)
                field._stamp(it, field.D, field.H)
                b = it.box
                for cx in range(int(math.floor(b[0] - G.CAP)), int(math.floor(b[2] + G.CAP)) + 1):
                    for cy in range(int(math.floor(b[1] - G.CAP)), int(math.floor(b[3] + G.CAP)) + 1):
                        field.cells.setdefault((cx, cy), []).append(len(field.items) - 1)
                if it.tag == "via":
                    slots.add(net, it.a, it.r * 2)
            S.chain.clear()
            from scipy.spatial import cKDTree
            S.tree = cKDTree(np.array([v[1] for v in slots.vias])) if slots.vias else None
        if log:
            log("%-4s %-14s %-8s vias %s len %s est %s%s%s" % (ball["num"], net, res["verdict"], res["vias"], res["length"], res["estimate"],
                                                             (" chain %.2f" % res["chain"]) if res["chain"] else "", " (grid tolerance)" if res["grid"] else ""))
    out["_meta"] = {"seconds": round(time.time() - t0, 1), "slot_max": slot_max, "window": list(window or WINDOW), "joint": bool(joint)}
    return out


def table(res):
    lines = ["ball net            verdict  vias  length  estimate  chain  target"]
    for net, r in sorted((k, v) for k, v in res.items() if not k.startswith("_")):
        lines.append("%-4s %-14s %-8s %-4s  %-6s  %-8s  %-5s  %s" % (r["ball"], net, r["verdict"] + ("~" if r.get("grid") else ""), "-" if r["vias"] is None else r["vias"],
                     "-" if r["length"] is None else r["length"], r["estimate"], r["chain"] or "-", ", ".join(r["target"])))
    c = {}
    for k, v in res.items():
        if not k.startswith("_"):
            c[v["verdict"]] = c.get(v["verdict"], 0) + 1
    lines.append("total: " + ", ".join("%s %d" % kv for kv in sorted(c.items())))
    return "\n".join(lines)


if __name__ == "__main__":
    a = sys.argv[1:]
    geo = json.load(open(a[a.index("--geo") + 1], encoding="utf-8"))
    sm = float(a[a.index("--slot-max") + 1]) if "--slot-max" in a else 3.0
    nets = a[a.index("--nets") + 1].split(",") if "--nets" in a else None
    r = check_state(geo, sm, nets, log=print)
    print(table(r))
