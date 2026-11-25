"""A length-matching plan on paper: planned paths of a bus's nets (hand waypoints, serpentine blocks sized for their
targets), the rest copied from the board, lengths, an exact clearance check and the block rules.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.planning.plan <board dir> <plan data .py> [board] [--out DIR] [-v]

board: the board the plan starts from (default the board folder's own); its present routes are what `pre`, `tail`
and kept nets copy. Writes into DIR (default <board dir>/out/plan):
  plan.json          lengths of every bus net, the violations, each changed net's items and blocks, moved other nets
  plan.txt           every changed net vertex by vertex (blocks as one line: humps, height, side, ends, added)
  plan_summary.json  lane spreads, the clock and the address lines against it, vias above the routes file's
  plan_summary.txt   VIA_TARGET, every block against the block rules (planning/serp.py) with its room, per zone
                     need and capacity, total serpentine; then what the data module's summary() adds
and prints the lane spreads and the violations (closest per pair of nets and kind).

The plan data file is a Python module (hand data, no tool logic) with
  def plan(P)                    draws the plan through P (a Plan):
      P.Net(name)                    an empty planned net; .track(layer, pts), .via(p), .to(*pts), .hop(layer, *pts),
                                     .block(p1, side, n, amp, pitch=None, start=None, tag="") (a straight from the
                                     current end to p1 carrying n humps, the first arc `start` after the end; pitch and
                                     start default to the routes file's TUNING pitch / keep)
      P.pre(name, pt)                a net holding the present route from its start to the vertex at pt
      P.tail(net, pt)                append the present route from the vertex at pt to its end
      P.legs(start, spec, end)       octilinear vertices from legs [(dir, c)]
      P.tuned(name, build, target, n)    build(amp) -> Net with one block of n humps; amp solved for the target
      P.fixed(name, net, target=None)    a planned net as drawn
      P.length(net)                  the planned length (blocks by the RTE-2 formula, via heights from the stackup)
      P.amp_for(need, n, pitch=None) the height that adds need with n humps
      P.N                            the planned nets so far (name -> Net)
      P.pad_net                      {(ref, pad): net}: pads the plan gives another net (a pin swap)
      P.drop_segs                    [(net, layer, a, b)]: other nets' segments the plan replaces
      P.moved                        {name: Net}: other nets the plan re-draws (checked, not counted)
  def summary(P, rows, lines, out)   optional: more summary lines / JSON keys (e.g. a new swap table)
  FREE = {...}                    optional: regions for planning/check.py --free
Nets of the bus that the plan does not draw are copied from the board unchanged (kept: their measured length).

Board data: the bus from planning/measure.py (board.toml [schematic.swap], [tune_sites], [length]); [plan] routes =
the routes module whose TUNING (block limits, default pitch), YIELD_NETS (pours that give way) and VIA_TARGET apply;
[plan] block_free_layers = layers whose blocks must stay outside the rule areas; [plan] label_strip = prefix left out
of net names in the summary.
"""
import json, math, os, sys
from collections import defaultdict

from Tools.KiCadDesignTools.planning import check as C, measure, serp
from Tools.KiCadDesignTools.planning.check import dist

AMP0 = 0.6                 # trial height when a block's height is solved (the natural length does not depend on it)


class Net:
    """A planned net: ordered items ['t', layer, [pts], serp_flag] and ['v', (x, y)]."""

    def __init__(self, name, plan=None):
        self.name = name
        self.plan = plan
        self.items = []
        self.blocks = []        # dicts describing serpentine blocks
        self.kept = False

    # --- building
    def track(self, layer, pts, serp=False):
        pts = [(round(p[0], 4), round(p[1], 4)) for p in pts]
        if self.items and self.items[-1][0] == "t" and self.items[-1][1] == layer and self.items[-1][3] == serp and dist(self.items[-1][2][-1], pts[0]) < 1e-6:
            self.items[-1][2].extend(pts[1:])
        else:
            self.items.append(["t", layer, list(pts), serp])
        return self

    def via(self, p):
        self.items.append(["v", (round(p[0], 4), round(p[1], 4))])
        return self

    def end(self):
        for it in reversed(self.items):
            if it[0] == "t":
                return it[2][-1]
            return it[1]

    def layer(self):
        for it in reversed(self.items):
            if it[0] == "t":
                return it[1]
        return self.plan.rules.layers[0]

    def to(self, *pts, layer=None):
        return self.track(layer or self.layer(), [self.end()] + list(pts))

    def hop(self, layer, *pts):
        """via at the current end, continue on `layer`."""
        p = self.end()
        self.via(p)
        return self.track(layer, [p] + list(pts))

    def block(self, p1, side, n, amp, pitch=None, start=None, tag=""):
        """straight from the current end to p1 with a block of n humps (first arc `start` mm after the current end)."""
        pitch = self.plan.pitch if pitch is None else pitch
        start = self.plan.keep if start is None else start
        p0 = self.end()
        pts, added, used = serp.points(p0, p1, side, n, amp, pitch, start)
        lay = self.layer()
        L = dist(p0, p1)
        ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
        a = (p0[0] + ux * start, p0[1] + uy * start)
        b = (p0[0] + ux * used, p0[1] + uy * used)
        ia = min(range(len(pts)), key=lambda i: dist(pts[i], a))
        ib = max(range(len(pts)), key=lambda i: (dist(pts[i], b) < 1e-6, i))
        if ia > 0:
            self.track(lay, pts[:ia + 1])
        self.track(lay, pts[ia:ib + 1], serp=True)
        if ib < len(pts) - 1:
            self.track(lay, pts[ib:])
        self.blocks.append({"net": self.name, "layer": lay, "from": [round(a[0], 3), round(a[1], 3)], "to": [round(b[0], 3), round(b[1], 3)],
                            "side": side, "n": n, "amp": round(amp, 3), "pitch": pitch, "adds": round(added, 3), "tag": tag,
                            "straight": [[round(p0[0], 3), round(p0[1], 3)], [round(p1[0], 3), round(p1[1], 3)]]})
        return self

    # --- from the board
    def keep_present(self, strip_serp=False, upto=None):
        """Copy the net's present route (optionally with the serpentine blocks replaced by their chords);
        upto = (x, y): stop at the point of the present path nearest to (x, y) (a vertex)."""
        r = self.plan.present(self.name)
        prev = None
        for (lay, w, pts) in r["pieces"]:
            pts = [tuple(p) for p in pts]
            if prev is not None and lay != prev:
                self.via(pts[0])
            prev = lay
            self.track(lay, pts)
        if strip_serp and r["blocks"]:
            self._strip(r["blocks"])
        if upto is not None:
            self._cut(upto)
        self.kept = upto is None and not strip_serp
        return self

    def _strip(self, blocks):
        for b in blocks:
            p0, p1 = tuple(b["from"]), tuple(b["to"])
            for it in self.items:
                if it[0] != "t":
                    continue
                pts = it[2]
                i0 = min(range(len(pts)), key=lambda i: dist(pts[i], p0))
                i1 = min(range(len(pts)), key=lambda i: dist(pts[i], p1))
                if dist(pts[i0], p0) < 0.01 and dist(pts[i1], p1) < 0.01 and i0 != i1:
                    lo, hi = min(i0, i1), max(i0, i1)
                    it[2] = pts[:lo + 1] + pts[hi:]
                    break

    def _cut(self, p):
        best = None
        for k, it in enumerate(self.items):
            if it[0] != "t":
                continue
            for i, q in enumerate(it[2]):
                d = dist(q, p)
                if best is None or d < best[0]:
                    best = (d, k, i)
        d, k, i = best
        if d > 0.05:
            raise ValueError("%s: cut point %s not on the present path (nearest %.3f)" % (self.name, p, d))
        self.items = self.items[:k + 1]
        self.items[k][2] = self.items[k][2][:i + 1]
        if len(self.items[k][2]) < 2:
            self.items = self.items[:k]

    # --- results
    def polyline_length(self):
        """Length with the polyline arcs (slightly below the true arcs)."""
        L, prev = 0.0, None
        for it in self.items:
            if it[0] == "t":
                if prev is not None and prev != it[1]:
                    L += self.plan.via_h(prev, it[1])
                prev = it[1]
                L += sum(dist(it[2][i], it[2][i + 1]) for i in range(len(it[2]) - 1))
        return L

    def n_vias(self):
        return sum(1 for it in self.items if it[0] == "v")

    def layers(self):
        d = defaultdict(float)
        for it in self.items:
            if it[0] == "t":
                d[it[1]] += sum(dist(it[2][i], it[2][i + 1]) for i in range(len(it[2]) - 1))
        return dict(d)


def legs(start, spec, end):
    """Octilinear polyline: start point, legs [(dir, c)] (E/W: y = c, N/S: x = c, SE/NW: x - y = c, NE/SW: x + y = c),
    end = station on the last leg (x for E/W/diagonals, y for N/S). Returns the vertices after start."""
    def form(d, c):
        return {"E": (0, 1), "W": (0, 1), "N": (1, 0), "S": (1, 0), "SE": (1, -1), "NW": (1, -1), "NE": (1, 1), "SW": (1, 1)}[d] + (c,)
    pts = []
    for k in range(len(spec) - 1):
        a1, b1, e1 = form(*spec[k])
        a2, b2, e2 = form(*spec[k + 1])
        det = a1 * b2 - a2 * b1
        pts.append((round((e1 * b2 - e2 * b1) / det, 4), round((a1 * e2 - a2 * e1) / det, 4)))
    d, c = spec[-1]
    if d in ("E", "W"):
        pts.append((end, c))
    elif d in ("N", "S"):
        pts.append((c, end))
    elif d in ("SE", "NW"):
        pts.append((end, round(end - c, 4)))
    else:
        pts.append((end, round(c - end, 4)))
    return pts


class Plan:
    """The context a plan data module draws through (see the module text)."""
    legs = staticmethod(legs)

    def __init__(self, cfg, board, rules):
        self.cfg, self.board, self.rules = cfg, board, rules
        self.G = measure.groups(cfg)
        self.via_h = measure.via_heights(cfg)
        pitch = rules.limits["pitch"]
        self.pitch = pitch["default"] if isinstance(pitch, dict) else pitch
        self.keep = rules.limits["keep"]
        self._present = {}
        self.N, self.target, self.moved = {}, {}, {}
        self.pad_net, self.drop_segs = {}, []

    def present(self, name):
        """The net's measured record on the board (planning/measure.py)."""
        if name not in self._present:
            self._present[name] = measure.measure_net(self.board, name, self.G["start_refs"], self.rules.layers, self.via_h)
        return self._present[name]

    def Net(self, name):
        return Net(name, self)

    def length(self, net):
        """Length with the serpentine blocks counted by the formula (the polyline arcs are a chord approximation)."""
        L, prev = 0.0, None
        for it in net.items:
            if it[0] == "t":
                if prev is not None and prev != it[1]:
                    L += self.via_h(prev, it[1])
                prev = it[1]
                if it[3]:
                    continue                      # serpentine piece: counted below
                pts = it[2]
                L += sum(dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
        for b in net.blocks:
            L += 2 * b["pitch"] * b["n"] + b["adds"]
        return L

    def amp_for(self, need, n, pitch=None):
        return serp.amp_for(need, n, self.pitch if pitch is None else pitch)

    def tuned(self, name, build, target, n, pitch=None, amp0=AMP0):
        """build(amp) -> Net with exactly one block whose amplitude is solved for the target length."""
        t = build(amp0)
        nat = self.length(t) - sum(b["adds"] for b in t.blocks)
        net = build(self.amp_for(target - nat, n, pitch))
        self.N[name] = net
        self.target[name] = target
        return net

    def fixed(self, name, net, target=None):
        self.N[name] = net
        self.target[name] = target
        return net

    # --- present routes as flat lists
    def flat(self, name, strip=True):
        """Present route as a flat list: ('p', layer, (x, y)) / ('v', (x, y)); serpentine blocks replaced by chords."""
        n = self.Net(name).keep_present(strip_serp=strip)
        out = []
        for it in n.items:
            if it[0] == "v":
                out.append(("v", it[1]))
            else:
                for p in it[2]:
                    if out and out[-1][0] == "p" and out[-1][1] == it[1] and dist(out[-1][2], p) < 1e-6:
                        continue
                    out.append(("p", it[1], p))
        res = []                               # drop collinear middle points
        for k, e in enumerate(out):
            if e[0] == "p" and res and res[-1][0] == "p" and k + 1 < len(out) and out[k + 1][0] == "p" and res[-1][1] == e[1] == out[k + 1][1]:
                a, b, c = res[-1][2], e[2], out[k + 1][2]
                if abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) < 1e-6 and (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]) > 0:
                    continue
            res.append(e)
        return res

    @staticmethod
    def _idx(fl, pt, tol=0.03):
        best = min(range(len(fl)), key=lambda i: dist(fl[i][-1], pt))
        if dist(fl[best][-1], pt) > tol:
            raise ValueError("no present vertex near %s (nearest %s)" % (pt, fl[best][-1]))
        return best

    def pre(self, name, pt, strip=True):
        """Net with the present route from its start up to the vertex at pt."""
        fl = self.flat(name, strip)
        i = self._idx(fl, pt)
        while fl[i][0] == "v":
            i += 1
        n = self.Net(name)
        self._emit(n, fl[:i + 1])
        return n

    def tail(self, n, pt, strip=True):
        """Append the present route from the vertex at pt to its end (drawn to pt first when the net ends elsewhere)."""
        fl = self.flat(n.name, strip)
        i = self._idx(fl, pt)
        while fl[i][0] == "v":
            i -= 1
        if dist(n.end(), fl[i][2]) > 1e-6:
            if n.layer() != fl[i][1]:
                raise ValueError("%s: tail on %s, net is on %s" % (n.name, fl[i][1], n.layer()))
            n.to(fl[i][2])
        self._emit(n, fl[i:])
        return n

    @staticmethod
    def _emit(n, fl):
        cur = []
        lay = None
        for e in fl:
            if e[0] == "v":
                if cur and len(cur) > 1:
                    n.track(lay, cur)
                cur = []
                n.via(e[1])
            else:
                if lay is not None and e[1] != lay and cur:
                    if len(cur) > 1:
                        n.track(lay, cur)
                    cur = []
                lay = e[1]
                cur.append(e[2])
        if len(cur) > 1:
            n.track(lay, cur)

    def show(self, name):
        return " ".join(("V(%.3f,%.3f)" % e[1]) if e[0] == "v" else "%s(%.3f,%.3f)" % (e[1], e[2][0], e[2][1]) for e in self.flat(name))

    # --- the check
    def report(self, movable=()):
        """Copy the undrawn bus nets, build the copper, check. -> (rows (name, length, vias, kept, blocks), violations, Prims)."""
        bus = self.G["bus"]
        for n in bus:
            if n not in self.N:
                self.N[n] = self.Net(n).keep_present()
                self.target.setdefault(n, None)
        P = C.board_prims(self.board, self.rules, bus, movable=movable, drop=self.drop_segs, pad_net=self.pad_net)
        for n in list(self.N.values()) + list(self.moved.values()):
            C.net_prims(P, self.rules, n)
        viol = C.check(P, list(self.N) + list(self.moved))
        rows = []
        for name in bus:
            n = self.N[name]
            L = self.present(name)["len"] if n.kept else self.length(n)
            rows.append((name, L, n.n_vias(), n.kept, n.blocks))
        return rows, viol, P


# ----------------------------------------------------------------------------- outputs
def write_plan(Pl, rows, viol, odir):
    L = {r[0]: r[1] for r in rows}
    out = {"lengths": {r[0]: round(r[1], 3) for r in rows}, "violations": viol, "nets": {}, "moved_others": {}}
    for name, n in list(Pl.N.items()) + list(Pl.moved.items()):
        if n.kept:
            continue
        d = {"items": [[it[0], it[1], [list(q) for q in it[2]], bool(it[3])] if it[0] == "t" else ["v", list(it[1])] for it in n.items],
             "blocks": n.blocks, "vias": n.n_vias(), "target": Pl.target.get(name)}
        (out["moved_others"] if name in Pl.moved else out["nets"])[name] = d
    json.dump(out, open(os.path.join(odir, "plan.json"), "w", encoding="utf-8"), indent=1)
    with open(os.path.join(odir, "plan.txt"), "w", encoding="utf-8") as f:
        for name, n in list(Pl.N.items()) + list(Pl.moved.items()):
            if n.kept:
                continue
            print("%s  len %.2f  vias %d" % (name, L.get(name, 0), n.n_vias()), file=f)
            for it in n.items:
                if it[0] == "v":
                    print("    via (%.3f, %.3f)" % it[1], file=f)
                elif not it[3]:
                    print("    %s %s" % (it[1], " ".join("(%.3f, %.3f)" % q for q in it[2])), file=f)
                else:
                    b = [b for b in n.blocks if abs(b["from"][0] - it[2][0][0]) < 1e-3 and abs(b["from"][1] - it[2][0][1]) < 1e-3][0]
                    print("    %s block %s: %d humps, amplitude %.3f, side %s, from (%.3f, %.3f) to (%.3f, %.3f), adds %.2f" % (
                        it[1], b["tag"], b["n"], b["amp"], b["side"], b["from"][0], b["from"][1], b["to"][0], b["to"][1], b["adds"]), file=f)


def summary(Pl, rows, viol, P, data, odir):
    cfg, G = Pl.cfg, Pl.G
    pre = cfg.get("plan.label_strip", "")
    lab = lambda n: n[len(pre):] if pre and n.startswith(pre) else n
    target = getattr(Pl.rules.module, "VIA_TARGET", None)
    L = {r[0]: r[1] for r in rows}
    V = {r[0]: r[2] for r in rows}
    out = {"violations": len(viol), "lanes": {}, "blocks": [], "zones": {}}
    lines = []
    for k, lane in G["lanes"].items():
        ls = {n: round(L[n], 2) for n in lane}
        out["lanes"][k] = {"min": min(ls.values()), "max": max(ls.values()), "spread": round(max(ls.values()) - min(ls.values()), 2), "nets": ls}
        lines.append("lane %d: %.2f - %.2f spread %.2f   %s" % (k, min(ls.values()), max(ls.values()), max(ls.values()) - min(ls.values()),
                                                              " ".join("%s %.2f" % (lab(n), v) for n, v in ls.items())))
    if G["clock"] and G["addr"]:
        clk = sum(L[n] for n in G["clock"])
        ad = {n: round(L[n] - clk, 2) for n in G["addr"]}
        out["clock"] = round(clk, 2)
        out["address_vs_clock"] = ad
        lines.append("clock %.2f; address vs clock %.2f (%s) .. %+.2f (%s); longest net %.2f (%s)" % (
            clk, min(ad.values()), min(ad, key=ad.get), max(ad.values()), max(ad, key=ad.get), max(L.values()), max(L, key=L.get)))
    if target is not None:
        lines.append("vias: " + ", ".join("%s %d" % (lab(n), V[n]) for n in G["data"] + G["clock"] if V[n] > target) +
                     " (all other data / %s / clock nets <= %d)" % (lab(cfg.get("schematic.swap.mask_net", "")), target))
        out["vias_over_%d" % target] = {n: V[n] for n in G["data"] + G["clock"] if V[n] > target}
    out["max_len"] = round(max(L.values()), 2)
    free = set(cfg.get("plan.block_free_layers", []))
    out["blocks"] = serp.block_rules(Pl.N, P, Pl.rules, free)
    for r in sorted(out["blocks"], key=lambda r: (r["zone"], r["from"][1], r["from"][0])):
        z = out["zones"].setdefault(r["zone"], {"need": 0.0, "capacity": 0.0, "nets": []})
        z["need"] = round(z["need"] + r["need"], 2)
        z["capacity"] = round(z["capacity"] + r["capacity"], 2)
        z["nets"].append(r["net"])
        lines.append("%-4s %-9s %s n%d a%.2f need %5.2f | a_max %.2f cap %5.2f (%s) | first arc (%.2f, %.2f) end (%.2f, %.2f) side %s | ends %.2f / %.2f %s" % (
            r["zone"], lab(r["net"]), r["layer"], r["n"], r["amp"], r["need"], r["amp_max"], r["capacity"], r["limited_by"], r["from"][0], r["from"][1],
            r["to"][0], r["to"][1], r["side"], r["straight_before"], r["straight_after"], "" if r["rules_ok"] else " <-- CHECK"))
    for zname, z in out["zones"].items():
        lines.append("zone %-4s need %6.2f mm, capacity %6.2f mm (each block alone at its largest amplitude), %d blocks" % (zname, z["need"], z["capacity"], len(z["nets"])))
    lines.append("total serpentine added in data lanes: %.1f mm" % sum(r["need"] for r in out["blocks"]))
    if hasattr(data, "summary"):
        data.summary(Pl, rows, lines, out)
    json.dump(out, open(os.path.join(odir, "plan_summary.json"), "w", encoding="utf-8"), indent=1)
    open(os.path.join(odir, "plan_summary.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return lines


def run(cfg, board_path, data_path, odir, verbose=False):
    from Tools.KiCadDesignTools.routing.busroute.board import Board
    board = Board(board_path, cfg.origin, fills=True)
    rules = C.Rules.of(cfg, board)
    Pl = Plan(cfg, board, rules)
    Pl.board_path, Pl.out_dir = board_path, odir
    data = C.load_data(data_path)
    data.plan(Pl)
    rows, viol, P = Pl.report(C.movable_vias(board_path))
    os.makedirs(odir, exist_ok=True)
    L = {r[0]: r[1] for r in rows}
    if verbose:
        for r in rows:
            if not r[3]:
                print("%-12s %7.2f (was %6.2f) vias %d  %s" % (r[0], r[1], Pl.present(r[0])["len"], r[2],
                      "; ".join("%s %s n%d a%.2f +%.2f" % (b["tag"], b["layer"], b["n"], b["amp"], b["adds"]) for b in r[4])))
    for k, lane in Pl.G["lanes"].items():
        ls = [L[n] for n in lane]
        print("lane %d: %.2f - %.2f spread %.2f  shortest %s longest %s" % (k, min(ls), max(ls), max(ls) - min(ls),
              min(lane, key=lambda n: L[n]), max(lane, key=lambda n: L[n])))
    write_plan(Pl, rows, viol, odir)
    print("violations:", len(viol))
    for k, v in C.aggregate(viol):
        print("  ", k, v)
    lines = summary(Pl, rows, viol, P, data, odir)
    print("\n".join(lines))
    return Pl, rows, viol


def main(argv):
    import argparse
    from Tools.KiCadDesignTools.core import config
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(prog="python -m Tools.KiCadDesignTools.planning.plan", description=__doc__.split("\n\n")[0])
    ap.add_argument("board_dir")
    ap.add_argument("data")
    ap.add_argument("board", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("-v", action="store_true")
    a = ap.parse_args(argv)
    cfg = config.load(a.board_dir)
    odir = a.out or cfg.path(os.path.join("out", "plan"))
    _, _, viol = run(cfg, os.path.abspath(a.board or cfg.pcb), a.data, odir, a.v)
    return 1 if viol else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
