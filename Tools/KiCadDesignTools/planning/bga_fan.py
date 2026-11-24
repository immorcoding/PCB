"""Whole-BGA block of an MCU + SDRAM board (written for the STM32H743 + SDRAM board, layer order signal / GND /
signal / signal / power / signal; try/sgsps, SPEC 6 and 14, stop 3.2 - 3.4): every supply / ground ball of both BGAs
on a via of its own, the bottom decoupling on those vias, and the fan-out of every non-SDRAM signal ball of the MCU,
decided together by one mixed integer program (scipy / HiGHS) on the half-pitch ball lattice, against the SDRAM bus
as it is on the board.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.planning.bga_dump <board dir> <base board> --out <geo.json>   (pcbnew: the state)
    python -m Tools.KiCadDesignTools.planning.bga_fan <board dir> --geo <geo.json> --out <dir> [--slot-max 3.0] [--time 120]  (system Python)

The base board is the real board with the groups power_bga, mcu_east, mcu_south (and the newer MCU groups) stripped
and no fill (core.boardtext unfill / strip); its bottom parts (H743: C201-C219 and C301-C308) are taken out of the
state and placed here. Writes <dir>/fan.json (the board's bga_fan.json: read by routes_power_bga.py, placement.place
and the MCU route files), fan.txt and fan.log.

The board's data: <board dir>/bga_block.toml [block] and [fan] (packages, power nets, window, the capacitors and
their kinds, the crystal balls, exits the SDRAM bus leaves open, each net's sides and target, the +3V3_MCU feed and
island sites, off-lattice vias), board.toml (layers, [power] ground, [bga.<ref>] supply). Defaults (--slot-max,
--only) come from there too.

Taken over from bga_plan (branch try/fanout-first): the lattice, the capacitor candidates (step 3), the options of
a ball (dog-bone and a straight run on an inner layer to the edge of the rule area) and the exact clearance fields of
bga_grid, now with four signal layers (L1 L3 L4 L6) and the planes L2 (ground) and L5 (power blocks).

The program (per package, the MCU with everything, the SDRAM with its supply balls and capacitors):
  supply    one site of the four round each supply / ground ball (no sharing: one via per site)
  signal    one option per non-SDRAM signal ball: dog-bone via at one of its four gap sites, then on L3, L4 or L6 one
            diagonal step to a ball line and straight along it to the rule-area edge; only exits that the SDRAM bus
            leaves open outside the area (EXITS) are offered. Crystals: L1 straight west, fixed, no via.
  points    one thing per lattice point and layer (one track between two vias / balls), capacitor pads block L6
  caps      each bottom part on two sites in line over a via of each of its nets (a ball's via, else one of its own),
            every 3.3 V ball with a 100 nF supply pad within CAP_REACH
  slots     no chain of joined plane clearance holes (L2: every via but GND; L5: every via but the block's net)
            longer than --slot-max: added lazily, exact (bga_grid.Slots over the fixed vias and the chosen ones)
"""
import argparse, json, math, os, time

import numpy as np
from Tools.KiCadDesignTools.core import config
from Tools.KiCadDesignTools.planning import bga_grid as G
from Tools.KiCadDesignTools.planning.bga_plan import Lattice, LP, sample_ok, ball_options, cap_candidate, CAP_GEOM, r4, staircases

DIRS = {"E": (1, 0), "W": (-1, 0), "S": (0, 1), "N": (0, -1)}
UNALLOC, W_OUT, W_IN = float(os.environ.get("FAN_UNALLOC", "400")), 0.25, 0.15
DONE = set()                                          # signal balls fixed by an earlier pass (with_fixed)
NOSIGSLOT = bool(os.environ.get("FAN_NOSIGSLOT"))     # signal vias left out of the slot rule (stage A of the staged run)
FREE_SIDES = os.environ.get("FAN_SIDES_FREE", "").split()

# The board's values, set by setup(cfg) from bga_block.toml [block] / [fan] and board.toml (H743 values in the comments).
MCU = SDRAM = None               # the two packages (U201, U301)
POWER = None                     # supply and ground nets: [power] ground, [bga.<ref>] supply of both, [block] other_power
SUPPLY33 = None                  # the two packages' supply nets (+3V3_MCU, +3V3_SDRAM)
GROUND = None
WINDOW = None                    # the planning window x0 y0 x1 y1
MCU_CAPS = None                  # parts taken out of the state and placed here (C201-C219), with SD_CAPS (C301-C308)
SD_CAPS = None
CAP_KINDS = None                 # {ref: [(kind, size, net, count)]}; FAN_DROP="C218 C219" leaves kinds out
CAP_REF = None                   # {ref: {kind: [references in naming order]}}
TIED = None                      # nets whose capacitor sits on the ball's own via (no via of its own): VCAP1, VCAP2
ISLAND = None                    # [(site, net)]: a via of that net there ends up on an island of its power-plane block
FEED = None                      # sites that hold no via of another net than the MCU's supply (its block's feed)
EXTRA = None                     # off-lattice vias for balls whose four gap sites the bus takes:
                                 # ball -> [(via, L1 points between ball and via, layer, run from the via to the area edge, side)]
CAP_REACH = None                 # every 3.3 V ball has a 100 nF this close (supply pad centre); FAN_REACH overrides
CAP_FAR = None                   # every 100 nF this close to some 3.3 V ball (LAY-2)
CAP_FAR_OTHER = None             # the other parts (1 uF, VCAP) this close to a ball of their net
XTAL_BALLS = None                # crystal ball -> net
XTAL_BOX = None                  # L1 kept for the crystals
XTAL_END_X = None                # the crystal lines' reserve runs straight west to this x
XTAL_W = None
EXITS = None                     # exits the SDRAM bus leaves open outside the MCU's rule area: side -> {layer: [(lo, hi)]}
TARGET = None                    # net -> where it is going (a point beyond the SDRAM bands, for the estimate only)
DEFAULT_TARGET = None
IMPORTANT = None                 # net prefixes that prefer IMPORTANT_LAYER (next to the ground plane, SPEC 6)
IMPORTANT_LAYER = None
SIDES = None                     # net -> the MCU sides it may leave through; nets not listed: any side
NOVDDA = None                    # FAN_NOVDDA: the VDDA filter's parts, zone and net taken out of the state
SLOT_MAX = None                  # --slot-max default
AREA = None                      # {ref: its BGA rule area name} (place.toml [rule_areas])
BUS_W = None                     # the bus width the options are checked at
INNER = None                     # the layers of a run after a via: the signal layers but the top one


def setup(cfg):
    """Read the board's values (see the globals above) and configure bga_grid."""
    global MCU, SDRAM, POWER, SUPPLY33, GROUND, WINDOW, MCU_CAPS, SD_CAPS, CAP_KINDS, CAP_REF, TIED, ISLAND, FEED
    global EXTRA, CAP_REACH, CAP_FAR, CAP_FAR_OTHER, XTAL_BALLS, XTAL_BOX, XTAL_END_X, XTAL_W, EXITS, TARGET
    global DEFAULT_TARGET, IMPORTANT, IMPORTANT_LAYER, SIDES, NOVDDA, SLOT_MAX, INNER, AREA, BUS_W
    G.configure(cfg)
    blk = cfg.datafile("bga_block.toml")
    if not blk.get("block") or not blk.get("fan"):
        raise config.ConfigError("%s: bga_block.toml [block] and [fan] are needed by bga_fan" % cfg.dir)
    b, f = blk["block"], blk["fan"]
    MCU, SDRAM = b["mcu"], b["sdram"]
    SUPPLY33 = (cfg.need("bga.%s.supply" % MCU), cfg.need("bga.%s.supply" % SDRAM))
    GROUND = cfg.need("power.ground")
    POWER = (GROUND,) + SUPPLY33 + tuple(b["other_power"])
    WINDOW = tuple(f["window"])
    MCU_CAPS = list(f["mcu_caps"])
    SD_CAPS = list(b["sdram_caps"])
    CAP_KINDS = {r: [(k["name"], k["size"], k["net"], k["count"]) for k in v] for r, v in f["cap_kinds"].items()}
    CAP_REF = {r: dict({"100n": list(b["caps_100n"][r])}, **{k[0]: [k[0]] for k in v if k[0] != "100n"}) for r, v in CAP_KINDS.items()}
    for _k in os.environ.get("FAN_DROP", "").split():
        CAP_KINDS[MCU] = [c for c in CAP_KINDS[MCU] if c[0] != _k]
    TIED = tuple(f["tied"])
    ISLAND = [(tuple(i["site"]), i["net"]) for i in f["island"]]
    FEED = [] if os.environ.get("FAN_NOFEED") else [(x, y) for x in f["feed"]["x"] for y in f["feed"]["y"]]
    EXTRA = {ball: [(tuple(e["via"]), [tuple(q) for q in e["mid"]], e["layer"], [tuple(q) for q in e["run"]], e["side"]) for e in v]
             for ball, v in f["extra"].items()}
    CAP_REACH = float(os.environ.get("FAN_REACH", f["cap_reach"]))
    CAP_FAR, CAP_FAR_OTHER = f["cap_far"], f["cap_far_other"]
    XTAL_BALLS = dict(b["xtal_balls"])
    XTAL_BOX = tuple(b["xtal_box"])
    XTAL_END_X = f["xtal_end_x"]
    XTAL_W = b["xtal_width"]
    EXITS = {side: {l: [tuple(r) for r in rs] for l, rs in v.items()} for side, v in f["exits"].items()}
    TARGET = {n: tuple(t["at"]) for t in f["targets"].values() for n in t["nets"]}
    DEFAULT_TARGET = tuple(f["default_target"])
    IMPORTANT = tuple(f["important"])
    IMPORTANT_LAYER = f["important_layer"]
    SIDES = dict(f["sides"])
    NOVDDA = f["novdda"]
    SLOT_MAX = b["slot_max"]
    INNER = G.LAYERS[1:]
    AREA = {a["ref"]: a["name"] for a in cfg.datafile("place.toml")["rule_areas"]["areas"]}
    BUS_W = b["bus_width"]
    return cfg


def is_signal(net):
    return bool(net) and net not in POWER and not net.startswith("+") and not net.startswith("unconnected-")


def cap_shifted(lat, s, g, size, da, dp):
    """cap_candidate with the part moved da along its axis and dp across it (both sites must stay under their
    pads): the blocked L6 points, the via sites beside the pads and the probe points recomputed."""
    cc = cap_candidate(lat, s, g, size)
    if not da and not dp:
        return cc
    ax = (1, 0) if cc["rot"] in (0, 180) else (0, 1)
    sx, sy = ax[0] * da + ax[1] * dp, ax[1] * da + ax[0] * dp
    rects = [(r[0] + sx, r[1] + sy, r[2] + sx, r[3] + sy) for r in cc["rects"]]
    for site, r in zip((s, g), rects):
        q = lat.xy(*site)
        if not (r[0] < q[0] < r[2] and r[1] < q[1] < r[3]):
            return None
    body = (min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects), max(r[3] for r in rects))
    bl, bv, probe = [], [], []
    u_lo, v_lo = lat.uv((body[0] - 0.4, body[1] - 0.4)); u_hi, v_hi = lat.uv((body[2] + 0.4, body[3] + 0.4))
    for uu in range(u_lo, u_hi + 1):
        for vv in range(v_lo, v_hi + 1):
            q = lat.xy(uu, vv)
            dd = min(math.hypot(max(r[0] - q[0], 0, q[0] - r[2]), max(r[1] - q[1], 0, q[1] - r[3])) for r in rects)
            if dd < 0.135 - 1e-6:
                bl.append((uu, vv))
            if dd < 0.275 - 1e-6 and (uu, vv) not in (s, g) and uu % 2 and vv % 2:
                bv.append((uu, vv))
            if body[0] - 0.25 <= q[0] <= body[2] + 0.25 and body[1] - 0.25 <= q[1] <= body[3] + 0.25:
                probe.append((uu, vv))
    return dict(cc, pos=(r4(cc["pos"][0] + sx), r4(cc["pos"][1] + sy)), pads=[(r4(p[0] + sx), r4(p[1] + sy)) for p in cc["pads"]],
                rects=rects, body=body, bl=bl, bv=bv, probe=probe)


def turn(a, b, c):
    """0 for a straight line a-b-c, 1 for 45 degrees ... 4 for a reversal (in steps of 45 degrees)."""
    a1 = math.atan2(b[1] - a[1], b[0] - a[0]); a2 = math.atan2(c[1] - b[1], c[0] - b[0])
    d = abs(math.degrees(a2 - a1)) % 360
    return round(min(d, 360 - d) / 45.0)


def with_fixed(geo, fixA, ref=None):
    """The geo with a stage-A result built in: its supply and own vias, the supply dog-bones (L1, 0.2) and the
    capacitor pads (L6), so that the signal stage sees them as ordinary copper."""
    g = dict(geo)
    g["vias"] = list(geo["vias"]); g["tracks"] = list(geo["tracks"]); g["pads"] = list(geo["pads"])
    for num, v in fixA["supply"].items():
        if not v["via"]:
            continue
        g["vias"].append([v["net"], list(v["via"]), 0.3, 0.15])
        g["tracks"].append([v["net"], G.TOP, list(v["ball"]), list(v["via"]), 0.2])
    for num, v in fixA.get("signal", {}).items():              # signal fan-outs placed by an earlier pass
        g["vias"].append([v["net"], list(v["via"]), 0.3, 0.15])
        g["tracks"].append([v["net"], G.TOP, list(v["ball"]), list(v["via"]), 0.09])
        run = [v["via"]] + [q for q in v["run"] if q != v["via"]]
        for a_, b_ in zip(run, run[1:]):
            g["tracks"].append([v["net"], v["layer"], list(a_), list(b_), 0.09])
        DONE.add(num)
    for k, net in fixA["own"].items():
        g["vias"].append([net, [float(c) for c in k.split(",")], 0.3, 0.15])
    for c in fixA["caps"]:
        hl, hw = CAP_GEOM[c["size"]][1:]
        horiz = c["rot"] % 180 == 0
        ax, ay = (hl, hw) if horiz else (hw, hl)
        for i, (q, net) in enumerate(zip(c["pads"], c["nets"])):
            box = [q[0] - ax, q[1] - ay, q[0] + ax, q[1] + ay]
            g["pads"].append({"ref": "fix" + c["ref"], "num": str(i + 1), "net": net, "pos": list(q), "layers": [G.BOTTOM], "smd": True, "hole": 0.0,
                              "shape": "rect", "r": 0.0, "box": box, "poly": [[box[0], box[1]], [box[2], box[1]], [box[2], box[3]], [box[0], box[3]]]})
    return g


def state(geo):
    g = dict(geo)
    gone = set(MCU_CAPS + SD_CAPS)
    if os.environ.get("FAN_NOVDDA"):                # the VDDA filter moved out of the ball field (west of the MCU)
        gone |= set(NOVDDA["parts"])
        g["zones"] = [z for z in geo["zones"] if z["name"] != NOVDDA["zone"]]
        g["tracks"] = [t for t in geo["tracks"] if t[0] != NOVDDA["net"]]
        g["vias"] = [v for v in geo["vias"] if v[0] != NOVDDA["net"]]
    g["pads"] = [p for p in geo["pads"] if p["ref"] not in gone]
    return g


def site_ok_fixed(f, cc, fixed_vias):
    """Capacitor pads against the state: L6 copper 0.09 away, foreign holes 0.2 away (fixed vias are all foreign:
    the state has no supply via)."""
    d6 = f.D[G.BOTTOM]
    for (x0, y0, x1, y1) in cc["rects"]:
        j0, j1, i0, i1 = f._win((x0, y0, x1, y1), 0.0)
        X, Y = np.meshgrid(f.xs[i0:i1], f.ys[j0:j1])
        inside = (X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1)
        if inside.any() and (d6[j0:j1, i0:i1][inside] < 0.09 - 1e-4).any():
            return False
        for n, p, d, h in fixed_vias:
            dx = max(x0 - p[0], 0.0, p[0] - x1); dy = max(y0 - p[1], 0.0, p[1] - y1)
            if math.hypot(dx, dy) < h / 2 + 0.2 - 1e-6 or math.hypot(dx, dy) < d / 2 + 0.09 - 1e-6:
                return False
    return True


class Fan:
    def __init__(self, geo, slot_max, log=print):
        self.log, self.slot_max = log, slot_max
        self.geo = g = state(geo)
        t0 = time.time()
        reserve = [G.Item("<xtal>", (G.TOP,), "poly", poly=[(XTAL_BOX[0], XTAL_BOX[1]), (XTAL_BOX[2], XTAL_BOX[1]),
                                                           (XTAL_BOX[2], XTAL_BOX[3]), (XTAL_BOX[0], XTAL_BOX[3])], tag="reserve")]
        self.pads = {(p["ref"], p["num"]): p for p in g["pads"]}
        for ball, net in XTAL_BALLS.items():                  # the crystal lines: L1 straight west, 0.254 wide
            p = self.pads[(MCU, ball)]["pos"]
            reserve.append(G.Item(net, (G.TOP,), "seg", a=tuple(p), b=(XTAL_END_X, p[1]), r=XTAL_W / 2, tag="reserve"))
        self.field = G.Field(g, WINDOW, items=G.scene_items(g, extra=reserve))
        self.lat = {MCU: Lattice(MCU, [p for p in g["pads"] if p["ref"] == MCU], g["areas"][AREA[MCU]]["rect"]),
                    SDRAM: Lattice(SDRAM, [p for p in g["pads"] if p["ref"] == SDRAM], g["areas"][AREA[SDRAM]]["rect"])}
        x0, y0, x1, y1 = WINDOW
        self.fixed_vias = [(n, tuple(p), d, h) for n, p, d, h in g["vias"] if x0 <= p[0] <= x1 and y0 <= p[1] <= y1]
        log("state: %d items, %d fixed vias in the window, field %.1f s" % (len(self.field.items), len(self.fixed_vias), time.time() - t0))

    # ---------------------------------------------------------------- candidates
    def supply_candidates(self, ref):
        f, lat = self.field, self.lat[ref]
        out, self.pmask = {}, getattr(self, "pmask", {})
        opened = {}
        for uv, pad in sorted(lat.balls.items()):
            net = pad["net"]
            if net not in POWER:
                continue
            if net not in opened:
                opened[net] = f.opened(net)
                self.pmask[net] = f.track_free(G.TOP, BUS_W, *opened[net])
            D, H = opened[net]
            c = []
            for dg in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                s = (uv[0] + dg[0], uv[1] + dg[1])
                p = lat.xy(*s)
                if not lat.inside(*s) or not f.is_area(p, f.via_in[0] / 2):
                    continue
                if f.via_ok(p, D, H) and sample_ok(f, self.pmask[net], [lat.xy(*uv), p], lat.pad_r + 0.17):
                    c.append(s)
            # a ball beside an empty ball position (outside the array, the MCU's ball-free ring, the SDRAM's aisle):
            # a via on that position, straight out along the ball's own line
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (uv[0] + 2 * d[0], uv[1] + 2 * d[1])
                if q in lat.balls or not lat.inside(*q):
                    continue
                p = lat.xy(*q)
                if f.is_area(p, f.via_in[0] / 2) and f.via_ok(p, D, H) and sample_ok(f, self.pmask[net], [lat.xy(*uv), p], lat.pad_r + 0.17):
                    c.append(("xy", p))
            out[pad["num"]] = (uv, net, c)
        return out

    def exit_ok(self, side, layer, e):
        rng = EXITS.get(side, {}).get(layer)
        if not rng:
            return False
        c = e[0] if side in ("N", "S") else e[1]
        return any(lo - 1e-6 <= c <= hi + 1e-6 for lo, hi in rng)

    def signal_options(self):
        f, lat = self.field, self.lat[MCU]
        masks = {l: f.track_free(l, BUS_W) for l in G.LAYERS}
        ok = {}

        def via_ok(s):
            if s not in ok:
                p = lat.xy(*s)
                ok[s] = f.is_area(p, f.via_in[0] / 2) and f.via_ok(p)
            return ok[s]
        out = {}
        for uv, pad in sorted(lat.balls.items()):
            net = pad["net"]
            if not is_signal(net) or net.startswith("FMC_") or pad["num"] in XTAL_BALLS or pad["num"] in DONE:
                continue
            opts = []
            for o in ball_options(lat, f, masks, via_ok, uv, inner=INNER):
                if o["via"] is None or not self.exit_ok(o["side"], o["layer"], o["exit"]) or (o["side"] not in SIDES.get(net, "NESW") and net not in FREE_SIDES):
                    continue
                tgt = TARGET.get(net, DEFAULT_TARGET)
                o["cost"] = (W_IN * o["len"] + W_OUT * (abs(o["exit"][0] - tgt[0]) + abs(o["exit"][1] - tgt[1]))
                             + (0.6 if net.startswith(IMPORTANT) and o["layer"] != IMPORTANT_LAYER else 0.0)
                             + (0.4 if not net.startswith(IMPORTANT) and o["layer"] == IMPORTANT_LAYER else 0.0)
                             + 0.3 * turn(o["l1"][0], o["l1"][-1], o["run"][1]))
                opts.append(o)
            # a via on the empty ball position next to the ball (outside the array, the ball-free ring), straight
            # out along the ball's own line on L1, and on along that line on an inner layer to the area edge
            for dn, d in DIRS.items():
                q = (uv[0] + 2 * d[0], uv[1] + 2 * d[1])
                if q in lat.balls or not lat.inside(*q):
                    continue
                p = lat.xy(*q)
                if not (f.is_area(p, f.via_in[0] / 2) and f.via_ok(p) and sample_ok(f, masks[G.TOP], [tuple(pad["pos"]), p], lat.pad_r + 0.17)):
                    continue
                e, side = lat.edge_point(q[0], q[1], d)
                for layer in INNER:
                    if side not in SIDES.get(net, "NESW") or not self.exit_ok(side, layer, e) or not sample_ok(f, masks[layer], [p, e]):
                        continue
                    tgt = TARGET.get(net, DEFAULT_TARGET)
                    ln = 0.65 + math.dist(p, e)
                    opts.append({"layer": layer, "via": ("xy", p), "l1": [tuple(pad["pos"]), p], "run": [p, e], "side": side, "exit": e, "len": ln,
                                 "nodes": {layer: lat.run(q[0], q[1], d)},
                                 "cost": W_IN * ln + W_OUT * (abs(e[0] - tgt[0]) + abs(e[1] - tgt[1])) + 0.2
                                 + (0.6 if net.startswith(IMPORTANT) and layer != IMPORTANT_LAYER else 0.0)})
            # an east-edge ball (column 15): L1 straight east along its row out of the rule area to a 0.45 via just
            # outside it (between the SDRAM's L1 lanes leaving east), then L6 (free of the bus outside the fields)
            if uv[0] == max(u for u, v in lat.balls):
                p = (r4(lat.area[2] + 0.45), r4(pad["pos"][1]))
                if f.via_ok(p) and sample_ok(f, masks[G.TOP], [tuple(pad["pos"]), p], lat.pad_r + 0.17) and "E" in SIDES.get(net, "NESW"):
                    tgt = TARGET.get(net, DEFAULT_TARGET)
                    ln = math.dist(pad["pos"], p)
                    opts.append({"layer": G.BOTTOM, "via": ("xy", p), "l1": [tuple(pad["pos"]), p], "run": [p, p], "side": "E", "exit": p, "len": ln,
                                 "nodes": {G.TOP: [q for q in lat.run(uv[0], uv[1], (1, 0))[1:]]},
                                 "cost": W_IN * ln + W_OUT * (abs(p[0] - tgt[0]) + abs(p[1] - tgt[1])) + 0.3})
            for via, mid, layer, run, side in EXTRA.get(pad["num"], []):
                bx = tuple(pad["pos"])
                if not (f.via_ok(via) and sample_ok(f, masks[G.TOP], [bx] + list(mid) + [via], lat.pad_r + 0.17)
                        and sample_ok(f, masks[layer], [via] + list(run))):
                    self.log("  extra via of %s at %s on %s: not free" % (pad["num"], via, layer))
                    continue
                tgt = TARGET.get(net, DEFAULT_TARGET)
                ln = sum(math.dist(a, b) for a, b in zip([bx] + list(mid) + [via] + list(run), (list(mid) + [via] + list(run))))
                opts.append({"layer": layer, "via": ("xy", via), "l1": [bx] + list(mid) + [via], "run": [via] + list(run), "side": side,
                             "exit": run[-1], "len": ln, "nodes": {},
                             "cost": W_IN * ln + W_OUT * (abs(run[-1][0] - tgt[0]) + abs(run[-1][1] - tgt[1]))})
            out[pad["num"]] = (uv, net, opts)
        return out

    def xy(self, lat, s):
        return tuple(s[1]) if s[0] == "xy" else lat.xy(*s)

    # ---------------------------------------------------------------- the program
    def foreign(self, ref, net, plane):
        if plane == G.GND_PLANE:
            return net != GROUND
        return net != (SUPPLY33[0] if ref == MCU else SUPPLY33[1])

    def solve(self, ref, time_limit=120.0, stage=None, fixA=None):
        """stage None: everything in one program. "A": supply vias and capacitors, each signal ball keeping one of
        its option sites free (counted in the slot rows; its cheapest option there as the cost). "B": the signal
        fan-out with the supply vias and capacitors of fixA (an "A" result) fixed."""
        f, lat = self.field, self.lat[ref]
        t0 = time.time()
        PB = self.supply_candidates(ref) if not os.environ.get("FAN_NOSUP") else {}
        SO = self.signal_options() if ref == MCU and not os.environ.get("FAN_NOSIG") else {}
        if stage == "A":
            SO = {num: (uv, net, [dict(via=s_, cost=min(o["cost"] for o in opts if o["via"] == s_), nodes={}, run=[], layer="-",
                                       side="-", exit=[0, 0], len=0.0) for s_ in sorted({o["via"] for o in opts}, key=str)])
                  for num, (uv, net, opts) in SO.items()}
        if stage == "B":
            for num in PB:
                v = fixA["supply"].get(num, {}).get("via")
                PB[num] = (PB[num][0], PB[num][1], [s_ for s_ in PB[num][2] if v and lat.xy(*s_) == tuple(v)])
        self.log("%s: %d supply balls (%d without a site), %d signal balls (%d without an option), %d options, %.1f s" % (
            ref, len(PB), sum(1 for v in PB.values() if not v[2]), len(SO), sum(1 for v in SO.values() if not v[2]),
            sum(len(v[2]) for v in SO.values()), time.time() - t0))
        caps = self.cap_candidates(ref, PB) if not os.environ.get("FAN_NOCAP") else []
        if stage == "B":
            want = {(tuple(c["pos"]), c["rot"]) for c in fixA["caps"]}
            caps = [cc for cc in caps if (tuple(cc["pos"]), cc["rot"]) in want]
            self.log("  stage B: %d of %d capacitors of stage A found among the candidates" % (len(caps), len(want)))
        pos = lambda s: tuple(s[1]) if s and s[0] == "xy" else lat.xy(*s)
        # fixed vias standing exactly on a lattice site (constants of the staircase rows; no new via there)
        fixed_at = {}
        for n, p, d, h in self.fixed_vias:
            uv = lat.uv(p)
            if uv[0] % 2 and uv[1] % 2 and math.dist(lat.xy(*uv), p) < 1e-3:
                fixed_at[uv] = n
        reach = (self.slot_max - f.via_in[0] - 2 * G.PLANE_CLR) / lat.pitch
        paths = (staircases(reach * reach + 1e-9) if G.merge_dist(f.via_in[0], f.via_in[0]) > lat.pitch and not os.environ.get("FAN_NOSTAIR")
                 and self.slot_max < 10 else [])        # no slot limit (user 2026-11-23): --slot-max 0 or large
        all_pts = [(uu, vv) for uu in range(lat.u0, lat.u1 + 1) for vv in range(lat.v0, lat.v1 + 1)]
        cuts = []
        for rnd in range(int(os.environ.get("FAN_ROUNDS", "30"))):
            lp = LP()
            X, Y, NEW, C = {}, {}, {}, {}
            at_site = {}                                  # site -> [(var, net)]
            near_extra = []                               # (var, [sites]) an off-lattice via excludes
            pts = {}                                       # (layer, (u, v)) -> [var]
            for num, (uv, net, cands) in sorted(PB.items()):
                if not cands:
                    continue
                vs = []
                for s_ in cands:
                    v = lp.var(0.0 if s_[0] != "xy" else 0.2, name="x")
                    X[(num, s_)] = v
                    at_site.setdefault(s_, []).append((v, net))
                    vs.append(v)
                    if s_[0] == "xy":
                        q = lat.uv(s_[1])
                        for l in G.LAYERS:
                            pts.setdefault((l, q), []).append(v)
                        near_extra.append((v, [q2 for q2 in lat.via_sites() if math.dist(lat.xy(*q2), s_[1]) < 0.44]))
                sl = lp.var(2 * UNALLOC, name="nosupply")
                lp.row(vs + [sl], [1.0] * (len(vs) + 1), 1.0, 1.0)
            for num, (uv, net, opts) in sorted(SO.items()):
                vs = []
                for k, o in enumerate(opts):
                    v = lp.var(o["cost"], name="y")
                    Y[(num, k)] = v
                    at_site.setdefault(o["via"], []).append((v, net))
                    if o["via"][0] == "xy":
                        vp = o["via"][1]
                        near_extra.append((v, [q for q in lat.via_sites() if math.dist(lat.xy(*q), vp) < 0.44]))
                        for a_, b_ in zip(o["run"], o["run"][1:]):
                            for q in all_pts:
                                qx = lat.xy(*q)
                                if float(G._seg_d(np.array(qx[0]), np.array(qx[1]), a_, b_)) < 0.2:
                                    pts.setdefault((o["layer"], q), []).append(v)
                    for l, nodes in o["nodes"].items():
                        for q in nodes:
                            pts.setdefault((l, q), []).append(v)
                    vs.append(v)
                sl = lp.var(UNALLOC, name="unalloc")
                lp.row(vs + [sl], [1.0] * (len(vs) + 1), 1.0, 1.0)
            # capacitors: each pad over a via of its net (a ball's, or one of its own; VCAP: the ball's)
            cover, by_kind = {}, {}
            for k, cc in enumerate(caps):
                v = lp.var(0.3 * cc["nearest"] + 0.0001 * k - ((600.0 if cc["kind"] in ("C218", "C219") else 300.0) if os.environ.get("FAN_CAPOPT") else 0.0), name="cap")
                C[k] = v
                by_kind.setdefault(cc["kind"], []).append(v)
                for s_, net in ((cc["s"], cc["nets"][0]), (cc["g"], GROUND)):
                    have = [w for w, n_ in at_site.get(s_, []) if n_ == net and lp.names[w] in ("x", "y")]
                    if net not in TIED:
                        if (s_, net) not in NEW:
                            NEW[(s_, net)] = lp.var(2.5, name="new")
                            at_site.setdefault(s_, []).append((NEW[(s_, net)], net))
                        have = have + [NEW[(s_, net)]]
                    lp.row([v] + have, [1.0] + [-1.0] * len(have), -np.inf, 0.0)
                for q in cc["bl"]:
                    pts.setdefault((G.BOTTOM, q), []).append(v)
                for q in cc["bv"]:
                    qx = lat.xy(*q)
                    dd = [math.hypot(max(r_[0] - qx[0], 0, qx[0] - r_[2]), max(r_[1] - qx[1], 0, qx[1] - r_[3])) for r_ in cc["rects"]]
                    near_ = [cc["nets"][i] for i in (0, 1) if dd[i] < 0.275 - 1e-6]
                    pts.setdefault(("bv", q), []).append((v, near_[0] if len(near_) == 1 else None))
                for num in cc["serves"]:
                    cover.setdefault(num, []).append(v)
            for kind, cnt in ([] if os.environ.get("FAN_NOCAP") else [(k_[0], k_[3]) for k_ in CAP_KINDS[ref]]):
                vs = by_kind.get(kind, [])
                if len(vs) < cnt:
                    self.log("  ! %s %s: only %d candidates for %d parts" % (ref, kind, len(vs), cnt))
                lp.row(vs, [1.0] * len(vs), 0.0 if os.environ.get("FAN_CAPOPT") else min(cnt, len(vs)), cnt)
            for num, (uv, net, cands) in sorted(PB.items()):
                if net in SUPPLY33:
                    sl = lp.var(80.0, name="uncovered")
                    lp.row(cover.get(num, []) + [sl], [1.0] * (len(cover.get(num, [])) + 1), 1.0, np.inf)
            for s_, lst in sorted(at_site.items(), key=lambda kv: str(kv[0])):
                vs = [v for v, n_ in lst]
                if s_ in fixed_at:
                    lp.row(vs, [1.0] * len(vs), 0.0, 0.0)
                else:
                    lp.row(vs, [1.0] * len(vs), -np.inf, 1.0)
            if ref == MCU:
                for q, bad_net in ISLAND:
                    vs = [v for v, n_ in at_site.get(lat.uv(q), []) if n_ == bad_net]
                    if vs:
                        lp.row(vs, [1.0] * len(vs), -np.inf, 0.0)
                for q in FEED:
                    key = lat.uv(q)
                    vs = [v for v, n_ in at_site.get(key, []) if n_ != SUPPLY33[0]]
                    if vs:
                        lp.row(vs, [1.0] * len(vs), -np.inf, 0.0)
            for v, qs in near_extra:
                for q in qs:
                    vs = [w for w, n_ in at_site.get(q, [])]
                    if vs:
                        lp.row([v] + vs, [1.0] * (len(vs) + 1), -np.inf, 1.0)
            for (l, q), vs in sorted(pts.items(), key=lambda kv: str(kv[0])):
                if l == "bv":                              # beside a pad: only a via of that pad's net
                    for c, ok_net in vs:
                        vias = [v for v, n_ in at_site.get(q, []) if n_ != ok_net]
                        if vias:
                            lp.row([c] + vias, [1.0] * (len(vias) + 1), -np.inf, 1.0)
                    continue
                if len(vs) > 1:
                    lp.row(vs, [1.0] * len(vs), -np.inf, 1.0)
            probe = {}
            for k, cc in enumerate(caps):
                for q in cc["probe"]:
                    probe.setdefault(q, []).append(C[k])
            for q, vs in sorted(probe.items()):
                if len(vs) > 1:
                    lp.row(vs, [1.0] * len(vs), -np.inf, 1.0)
            # plane slots: staircase rows over the site lattice (fixed vias on sites as constants) ...
            nst = 0
            for pl in G.PLANES:
                fv = {}
                for s_, lst in at_site.items():
                    if s_[0] == "xy":
                        continue
                    vs = [v for v, n_ in lst if self.foreign(ref, n_, pl) and not (NOSIGSLOT and lp.names[v] == "y")]
                    if vs:
                        fv[s_] = vs
                for s_, n_ in fixed_at.items():
                    if self.foreign(ref, n_, pl):
                        fv[s_] = True
                for s_ in sorted(fv):
                    for path in paths:
                        cols, const = [], 0
                        for dx, dy in path:
                            q = (s_[0] + 2 * dx, s_[1] + 2 * dy)
                            if q not in fv:
                                cols = None
                                break
                            if fv[q] is True:
                                const += 1
                            else:
                                cols += fv[q]
                        if cols is None or not cols:
                            continue
                        if len(path) - 1.0 - const < 0:
                            self.log("  ! fixed vias alone make a chain over the limit from %s on %s" % (lat.xy(*s_), pl))
                            continue
                        lp.row(cols, [1.0] * len(cols), -np.inf, len(path) - 1.0 - const)
                        nst += 1
            # ... and the cuts found by the exact check: not every one of these site / plane choices together
            for cut in cuts:
                cols = []
                for s_, pl in cut:
                    cols += [v for v, n_ in at_site.get(s_, []) if self.foreign(ref, n_, pl)]
                lp.row(cols, [1.0] * len(cols), -np.inf, len(cut) - 1.0)
            t1 = time.time()
            res = lp.solve(time_limit)
            if res.x is None:
                self.log("  ! %s round %d: no solution (status %s)" % (ref, rnd + 1, res.status))
                return None
            x = res.x
            chosen = {}
            for s_, lst in at_site.items():
                for v, n_ in lst:
                    if x[v] > 0.5 and not (NOSIGSLOT and lp.names[v] == "y"):
                        chosen[s_] = n_
            vias = [(n, p, d) for n, p, d, h in self.fixed_vias] + [(n_, pos(s_), f.via_in[0]) for s_, n_ in chosen.items()]
            S = G.Slots(self.geo, vias)
            bad = [c for c in S.longest() if c[0] > self.slot_max + 1e-6]
            mine = {tuple(map(float, pos(s_))): s_ for s_ in chosen}
            new_cuts = set()
            for ln, pl, mem in bad:
                got = self.path_cuts(S, pl, mem, mine)
                if got:
                    new_cuts.update(got)
                else:
                    self.log("  ! fixed vias alone make a %.2f mm chain on %s: %s" % (ln, pl, mem[:4]))
            new_cuts = [c for c in new_cuts if c not in cuts]
            self.log("  %s round %d: %d vars, %d rows (%d staircase), objective %.2f, %.1f s; chains over %.2f: %d (%s)" % (
                ref, rnd + 1, len(lp.c), len(lp.lo), nst, res.fun, time.time() - t1, self.slot_max, len(bad),
                ", ".join("%.2f %s" % (b_[0], b_[1]) for b_ in bad[:6])))
            if not new_cuts:
                break
            cuts += new_cuts
        r = {"supply": {}, "signal": {}, "caps": [], "own": {}, "unalloc": [], "uncovered": [], "cuts": len(cuts),
             "longest": [(c[0], c[1], [[n_, list(p)] for n_, p in c[2]]) for c in S.longest()[:12]]}
        for (num, s_), v in X.items():
            if x[v] > 0.5:
                r["supply"][num] = {"net": PB[num][1], "ball": list(lat.xy(*PB[num][0])), "via": list(pos(s_))}
        for num, (uv, net, cands) in PB.items():
            if num not in r["supply"]:
                r["supply"][num] = {"net": net, "ball": list(lat.xy(*uv)), "via": None}
        for num, (uv, net, opts) in SO.items():
            if stage == "A":
                pick = [k for k in range(len(opts)) if x[Y[(num, k)]] > 0.5]
                r.setdefault("reserved", {})[num] = list(pos(opts[pick[0]]["via"])) if pick else None
                continue
            pick = [k for k in range(len(opts)) if x[Y[(num, k)]] > 0.5]
            if not pick:
                r["unalloc"].append([num, net])
                continue
            o = opts[pick[0]]
            r["signal"][num] = {"net": net, "ball": list(lat.xy(*uv)), "via": list(pos(o["via"])), "layer": o["layer"],
                                "side": o["side"], "run": [list(p) for p in o["run"]], "exit": list(o["exit"]), "len": round(o["len"], 3)}
        refs = {k: list(v) for k, v in CAP_REF[ref].items()}
        for k, cc in enumerate(caps):
            if x[C[k]] > 0.5:
                name = refs[cc["kind"]].pop(0)
                r["caps"].append({"ref": name, "size": cc["size"], "pos": list(cc["pos"]), "rot": cc["rot"], "nets": list(cc["nets"]),
                                  "pads": [list(p) for p in cc["pads"]], "sites": [list(lat.xy(*cc["s"])), list(lat.xy(*cc["g"]))],
                                  "serves": cc["serves_d"]})
        for (s_, net), v in NEW.items():
            if x[v] > 0.5:
                r["own"]["%s,%s" % lat.xy(*s_)] = net
        for num, (uv, net, cands) in PB.items():
            if net in SUPPLY33:
                if not [c for c in r["caps"] if num in c["serves"] and c["ref"] in CAP_REF[ref]["100n"]]:
                    r["uncovered"].append(num)
        self.log("%s: %d / %d supply balls on a via of their own, %d signal balls placed, %d not (%s), %d capacitors, %d own vias, %d uncovered, %.1f s" % (
            ref, sum(1 for v in r["supply"].values() if v["via"]), len(PB), len(r["signal"]), len(r["unalloc"]),
            " ".join(a_ for a_, b_ in r["unalloc"]), len(r["caps"]), len(r["own"]), len(r["uncovered"]), time.time() - t0))
        return r

    def path_cuts(self, S, pl, mem, mine, most=12):
        """Cuts for every pair of members of a chain over the limit whose distance alone is over it (shortest joined
        run between them, the choices on it that are not fixed); up to `most`, farthest pairs first."""
        pts = [tuple(map(float, p)) for n_, p in mem]
        d = {v[1]: v for v in S.vias}
        pad = max(d[p][2] for p in pts)
        lim = self.slot_max - pad - 2 * G.PLANE_CLR
        pairs = sorted(((math.dist(a, b), a, b) for i, a in enumerate(pts) for b in pts[i + 1:] if math.dist(a, b) > lim + 1e-9), reverse=True)
        out = set()
        for dist, a, b in pairs:
            prev, todo = {a: None}, [a]
            while todo:
                c = todo.pop(0)
                if c == b:
                    break
                for o in pts:
                    if o not in prev and math.dist(o, c) < G.merge_dist(d[o][2], d[c][2]) - 1e-9:
                        prev[o] = c
                        todo.append(o)
            if b not in prev:
                continue
            path, c = [], b
            while c is not None:
                path.append(c)
                c = prev[c]
            cut = tuple(sorted(((mine[p], pl) for p in path if p in mine), key=str))
            if cut:
                out.add(cut)
            if len(out) >= most:
                break
        return out

    def path_cut(self, S, pl, mem, mine):
        """For a chain over the limit: the shortest run of joined vias between its two farthest members, as the
        (site, plane) choices among them that are not fixed. None when only fixed vias make it."""
        pts = [tuple(map(float, p)) for n_, p in mem]
        best = max(((a, b) for i, a in enumerate(pts) for b in pts[i + 1:]), key=lambda ab: math.dist(*ab))
        d = {v[1]: v for v in S.vias}
        prev, todo = {best[0]: None}, [best[0]]
        while todo:
            c = todo.pop(0)
            if c == best[1]:
                break
            for o in pts:
                if o not in prev and math.dist(o, c) < G.merge_dist(d[o][2], d[c][2]) - 1e-9:
                    prev[o] = c
                    todo.append(o)
        if best[1] not in prev:
            return None
        path, c = [], best[1]
        while c is not None:
            path.append(c)
            c = prev[c]
        cut = tuple(sorted(((mine[p], pl) for p in path if p in mine), key=str))
        return cut or None

    def cap_candidates(self, ref, PB):
        f, lat = self.field, self.lat[ref]
        out = []
        supply = [(num, lat.xy(*uv), net) for num, (uv, net, c) in sorted(PB.items()) if net in SUPPLY33 + TIED]
        tied_sites = {net: {s for num, (uv, n_, c) in PB.items() if n_ == net for s in c} for net in TIED}
        site_ok = {}
        for name, size, net, count in CAP_KINDS[ref]:
            step = 2 if size == "0402" else 4
            near = [b for num, b, n_ in supply if n_ == net]
            for s in lat.via_sites():
                ps = lat.xy(*s)
                if not f.is_area(ps, f.via_in[0] / 2) or not any(math.dist(ps, b) <= CAP_FAR + 0.6 for b in near):
                    continue
                if net in TIED and s not in tied_sites[net]:
                    continue
                for dn, d in sorted(DIRS.items()):
                    g = (s[0] + step * d[0], s[1] + step * d[1])
                    if not lat.inside(*g) or not f.is_area(lat.xy(*g), f.via_in[0] / 2):
                        continue
                    for site, n_ in ((s, net), (g, GROUND)):
                        if (site, n_) not in site_ok:
                            D, H = f.opened(n_) if n_ not in getattr(self, "_op", {}) else self._op[n_]
                            self.__dict__.setdefault("_op", {})[n_] = (D, H)
                            site_ok[(site, n_)] = f.via_ok(lat.xy(*site), D, H)
                    if not (site_ok[(s, net)] and site_ok[(g, GROUND)]):
                        continue
                    shifts = [(0.0, 0.0)] + ([(da, dp) for da in (-0.175, -0.1, 0.0, 0.1, 0.175) for dp in (-0.05, 0.0, 0.05) if da or dp] if size == "0603"
                                             else [(da, dp) for da in (-0.15, 0.0, 0.15) for dp in (-0.1, 0.0, 0.1) if da or dp] if ref == SDRAM else [])
                    for da, dp in shifts:
                        cc = cap_shifted(lat, s, g, size, da, dp)
                        if cc and site_ok_fixed(f, cc, self.fixed_vias):
                            break
                    else:
                        continue
                    serves = {num: round(math.dist(cc["pads"][0], b), 3) for num, b, n_ in supply if n_ == net and math.dist(cc["pads"][0], b) <= CAP_REACH}
                    nearest = min((math.dist(cc["pads"][0], b) for num, b, n_ in supply if n_ == net), default=9.0)
                    if name == "100n" and nearest > CAP_FAR:
                        continue
                    if name != "100n" and nearest > CAP_FAR_OTHER:
                        continue
                    cc = dict(cc, kind=name, nets=(net, GROUND), serves=sorted(serves) if name == "100n" else [], serves_d=serves, nearest=nearest)
                    out.append(cc)
        self.log("  %s: %d capacitor candidates" % (ref, len(out)))
        return out


def text(res):
    out = []
    for ref, r in res.items():
        if not r:
            out.append("%s: no solution" % ref)
            continue
        out.append("== %s: supply %d (no site: %s), signal %d, unallocated %s, caps %d, own vias %d, uncovered %s, cuts %d" % (
            ref, len(r["supply"]), [k for k, v in r["supply"].items() if not v["via"]], len(r["signal"]), r["unalloc"], len(r["caps"]),
            len(r["own"]), r["uncovered"], r["cuts"]))
        out.append("longest chains: " + "; ".join("%.3f %s %d vias" % (a, b, len(c)) for a, b, c in r["longest"][:6]))
        for num, v in sorted(r["supply"].items()):
            out.append("  S %-4s %-10s ball (%.3f, %.3f) via %s" % (num, v["net"], v["ball"][0], v["ball"][1], v["via"]))
        for num, v in sorted(r["signal"].items(), key=lambda kv: (kv[1]["side"], kv[1]["layer"], kv[1]["exit"])):
            out.append("  G %-4s %-14s %s %s via (%.3f, %.3f) exit (%.3f, %.3f) len %.2f" % (num, v["net"], v["side"], v["layer"], v["via"][0], v["via"][1], v["exit"][0], v["exit"][1], v["len"]))
        for c in r["caps"]:
            out.append("  C %-5s %s (%.3f, %.3f) rot %d nets %s sites %s serves %s" % (c["ref"], c["size"], c["pos"][0], c["pos"][1], c["rot"], c["nets"], c["sites"], c["serves"]))
        for k, v in sorted(r["own"].items()):
            out.append("  own via %s %s" % (k, v))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m Tools.KiCadDesignTools.planning.bga_fan")
    ap.add_argument("board", help="board folder (board.toml, bga_block.toml)")
    ap.add_argument("--geo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--slot-max", type=float, default=None, help="default: bga_block.toml [block] slot_max")
    ap.add_argument("--time", type=float, default=120.0)
    ap.add_argument("--only", default=None, help="packages, comma-separated (default: the MCU and the SDRAM)")
    ap.add_argument("--staged", action="store_true", help="supply vias and capacitors first, then the signal fan-out")
    ap.add_argument("--fixa", help="signal stage only: the supply vias and capacitors of this result (fan.json) are fixed copper")
    a = ap.parse_args(argv)
    setup(config.load(a.board))
    if a.slot_max is None:
        a.slot_max = SLOT_MAX
    if a.only is None:
        a.only = "%s,%s" % (MCU, SDRAM)
    os.makedirs(a.out, exist_ok=True)
    log_f = open(os.path.join(a.out, "fan.log"), "w", encoding="utf-8")

    def log(s):
        print(s); log_f.write(s + "\n"); log_f.flush()
    geo = json.load(open(a.geo, encoding="utf-8"))
    if a.fixa:
        fixA = json.load(open(a.fixa, encoding="utf-8"))[MCU]
        geo = with_fixed(geo, fixA)
        os.environ["FAN_NOSUP"] = os.environ["FAN_NOCAP"] = "1"
    fan = Fan(geo, a.slot_max, log)
    res = {}
    for ref in a.only.split(","):
        if a.staged:
            ra = fan.solve(ref, a.time, "A")
            json.dump(ra, open(os.path.join(a.out, "fanA_%s.json" % ref), "w", encoding="utf-8"), indent=1)
            res[ref] = fan.solve(ref, a.time, "B", ra) if ref == MCU and ra else ra
        else:
            res[ref] = fan.solve(ref, a.time)
    json.dump(res, open(os.path.join(a.out, "fan.json"), "w", encoding="utf-8"), indent=1)
    open(os.path.join(a.out, "fan.txt"), "w", encoding="utf-8").write(text(res) + "\n")


if __name__ == "__main__":
    main()
