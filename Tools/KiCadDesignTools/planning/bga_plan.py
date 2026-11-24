"""Whole-BGA planner of an MCU + SDRAM board (written for the STM32H743 + SDRAM board): supply vias, bottom
decoupling, the fan-out of all MCU signal balls and the SDRAM line order decided together, by one deterministic
model (user decision 2026-11-22, issue #22: "BGA first, everything of the BGA decided together").

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.planning.bga_plan <board dir> dump [board] --out out/plan/geo.json   (needs pcbnew)
    python -m Tools.KiCadDesignTools.planning.bga_plan <board dir> plan --geo out/plan/geo.json --sdram-pos X Y --sdram-rot R
                                            [--slot-max 3.0] [--name N] [--lanes 0123] [--no-draw]  (system Python)
                                            [--order rows|rivers|none] [--time S]
    python -m Tools.KiCadDesignTools.planning.bga_plan <board dir> check --geo GEO [--plan PLAN.json] [--slot-max 3.0] [--joint] [--nets a,b]
    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.planning.bga_plan <board dir> check --board <routed board>   (dump, then the same)

The board's data: <board dir>/bga_block.toml [block] and [plan] (the packages, power nets, windows, gates, the
capacitors the plan places, the SDRAM clock and its series resistor, length limits), board.toml (layers, [power]
ground and bus_prefix, [bga.<ref>] supply, [schematic.swap] the byte lanes) and place.toml (the SDRAM body, the
rule areas and their margin). Defaults (--slot-max, --lanes) come from there too.

dump   every pad, via, track, zone, rule area and keep-out of a board as geo.json (local mm = file mm - origin).
plan   one candidate: writes out/plan/<N>/plan.json and plan.txt. The geo must be the dump of a copy of the board
       with the SDRAM, MCU-signal and power-BGA groups stripped (bga_plan_proof.py base makes it; that script and
       bga_check.py are on branch try/fanout-first, not in this package).
check  the grid model's verdict per MCU signal ball for a state (bga_check.py, see above: planning.bga_check when
       it is brought over; without it this check stops with a message). With --plan the state is the geo plus the
       plan's copper and every planned net is re-checked against all the others (check_plan: this package only).

The model (plan), in the order the user set (issue #22, 2026-11-22). Every step is a mixed-integer program
(scipy / HiGHS, deterministic) over the same lattice; no trial routing decides anything.
  lattice   Each BGA is a half-pitch lattice inside its rule area. Balls sit on (even, even) points, via sites on
            (odd, odd) points (ball gaps, continued two rows beyond the array). A point holds one thing per
            layer: a via (all layers), or one track of that layer. That is the channel rule of profile C: one
            0.09 track between two balls on L1, one between two 0.30 vias on L4 / L6.
  options   Every ball has a finite list of ways to the edge of the rule area: L1 straight out, L1 through a ball
            gap and along the gap line, or a dog-bone via and a straight run on L4 / L6 along a ball line (row or
            column, either direction, also right across the field); in the SDRAM's aisle also one turn. An
            option is dropped when the state's copper (pads of other parts, the fixed VDDA parts under the MCU,
            keep-outs, the crystal strip) is in its way (bga_grid.Field, exact distances).
  step 2    solve_power: every supply / ground ball takes one of its four gap sites; sharing a via with a
            neighbour of the same net costs SHARE_COST; no chain of joined plane clearance holes longer than
            --slot-max (linear cuts over every staircase of neighbouring sites whose ends are farther apart
            than the limit allows, per plane class: L2 / L5 everything but GND, L3 everything but the block's own
            net); a matching keeps one free site for every signal ball of the inner rows.
  step 3    place_caps: each bottom capacitor on a pair of sites in line (0402 one pitch, 0603 two) with a via of
            each of its nets under its pads (the ball vias of step 2, else a via of its own); pads may not
            overlap, every 3.3 V ball needs a 100 nF within CAP_REACH; the L6 points and via sites under the pads
            are closed for the signals. The VDDA parts (C220 - C223, FB201) stay where they are.
  step 4    The fan-out of every MCU signal ball: one option per ball, one thing per lattice point and layer, the
            slot cuts again with the supply vias as constants, no two neighbouring L1 lanes at a Default-class or
            crystal width, byte-lane spread in the objective. Targets: an SDRAM net goes east (either way round
            the MCU), any other net to a gate on the planning window (N / NE / SE / S / SW / NW), the crystals
            straight west on L1 at 0.254. What ties the nets together outside the field, by --order:
            fence   (default; user decision 2026-11-22: the SDRAM may use L1, L4 and L6, the other buses change
                    layer as often as they need, but no section of the outline may be closed on all three layers)
                    solve_mcu_fence: the outline is cut into 12 sections (3 a side). 1. the fan-out with no limit;
                    2. per section the SDRAM keeps the one or two layers that answer used most there, the rest
                    is free (L1 always free along the crystals); 3. the fan-out inside that pattern: an SDRAM
                    lane keeps off the free layers of every section it leaves in or passes, another ball leaves
                    on a free layer of its section (so it crosses the bands without a via); 4. while balls are
                    left without a place, the section with most of them gets every other choice tried (one
                    fan-out each, PLAN_TRIALS in all). Only the SDRAM nets carry order rows (which way round,
                    and the stretch of the SDRAM's outline their balls can be entered on). What is left is
                    the report: plan.txt SECTIONS lists per section the free layers, the SDRAM lanes per layer
                    and the balls that lost their way. Each fan-out is optimal in 5 - 40 s.
            planA   layer plan A (SDRAM on L1 + L4 only, superseded), order rows on L1 and L6.
            rows / rivers / fence-mip / none   the order as one program: exact rows on every layer, one target
                    per half side, the fence rule with pass variables, or left out. HiGHS 1.2.0 (scipy 1.13)
                    does not finish the first three in minutes; they are kept for a newer solver (LP.solve is
                    the one place that calls it).
  step 5    solve_sdram: per layer (L1 first), which SDRAM ball each net ends on (bits free inside a byte lane,
            lanes as wholes by --lanes, NBL with its lane, the rest fixed: SPEC 9) and how it comes in, the
            entries in the order of the exits (order_rows), one thing per lattice point and layer.
  step 6    the other buses end at their gates in the same program as step 4.
Drawing (the proof, not the allocation): the lattice parts are written as they are; between the exit and the
target each SDRAM net and crystal is drawn by the grid verifier on its allocated layer, outside the rule areas, in
the order of the exits, against everything drawn before it; the other buses are then drawn one by one over all
three layers with 0.45 / 0.2 vias on a 0.5 mm grid outside the rule areas (slot limit kept; vias counted per
net). A net the verifier cannot draw is reported as a failure of the
plan (never re-allocated here). A second pass reserves a tuning zone (RTE-2) beside the longest straight of
each byte-lane net that needs length. bga_plan_proof.py then builds the plan with scripts/busroute on a copy.
"""
import itertools, json, math, os, sys, time

from Tools.KiCadDesignTools.core import config
from Tools.KiCadDesignTools.planning import bga_grid

REACH = float(os.environ.get("PLAN_REACH", 200.0))   # a net leaves the MCU within this angle of its target (no winding round the package)
VIA_COST = 3.0
SHARE_COST = 6.0
UNALLOC = 400.0
W_SPREAD = 1.5
DIRS = {"E": (1, 0), "W": (-1, 0), "S": (0, 1), "N": (0, -1)}
# The method assumes the SDRAM east of the MCU (its entries on the target circle round 90 degrees, sd_entry_theta,
# the entry estimates of solve_sdram): its direction, the MCU side facing it and the SDRAM side facing the MCU.
SD_ANGLE, SD_SIDE, SD_NEAR = 90.0, "E", "W"

# The board's values, set by setup(cfg) from bga_block.toml [block] / [plan], board.toml and place.toml (H743 values
# in the comments).
MCU = SDRAM = None                     # the two packages (U201, U301)
POWER = None                           # supply and ground nets: [power] ground, [bga.<ref>] supply of both, [block] other_power
SUPPLY33 = None                        # the two packages' supply nets (+3V3_MCU, +3V3_SDRAM)
WINDOW = None                          # the planning window x0 y0 x1 y1
SD_HALF = None                         # SDRAM body half size at rotation 0 (place.toml [bodies]); the rule area is the body + MARGIN
MARGIN = None                          # place.toml [rule_areas] margin
AREA = None                            # {ref: its BGA rule area name} (place.toml [rule_areas])
NOPOUR = None                          # {ref: its F.Cu no-pour area name}
SD_ZONE = None                         # the SDRAM's block on the power plane, moved with it: (power-role layer, SDRAM supply)
MCU_CAPS = None                        # parts re-placed by the plan (and taken out of the state with the SDRAM's)
SD_CAPS = None
CAP_100N = None                        # {ref: the 100 nF parts (SPEC 4)} in the order they are named
CAP_KINDS = None                       # {ref: [(kind, size, net, count, tie)]}
CAP_REACH = None
XTAL = None                            # the crystal nets
XTAL_BOX = None                        # L1 kept for the crystals: no other track, no via
XTAL_GATE = None                       # the gate (side) the crystals leave through, straight
XTAL_PREFIXES = None                   # nets drawn at the crystal width
XTAL_W = None
GATES = None                           # gate -> its direction (clockwise from north, degrees)
ORDER_OF = None                        # the direction a gate counts as in the order
GATE_SECTOR = None                     # gate -> the angles of the planning window's edge it owns
GATE_HINT = None                       # net -> gate, where the far pad does not decide it
SD_THETA = None                        # the SDRAM's entries on the target circle
PERIM = None                           # length of one turn round the MCU's rule area, for the estimates
DEST_FAR = None                        # estimate: distance of a net without a far pad
EST_REACH = None                       # estimate: what of the distance to the far pad the fan-out already covers
LAYERS = None                          # the plan's three routing layers, the SDRAM's order first
TOP = BOTTOM = None                    # outer layers (balls and crystals on the top, capacitors on the bottom)
GROUND = None
BUS = None                             # the SDRAM bus's net prefix
DATA, MASK, NLANES = None, None, None  # SDRAM data / byte-mask net prefixes and the number of byte lanes
IDENTITY = None                        # the SDRAM's pin functions (line_order.py's identity dump)
CLOCK = CLOCK_R = CLOCK_RES = None     # the SDRAM clock, its piece after the series resistor, the resistor
BUS_W = None                           # the bus width every signal is drawn at up to its gate
DEFAULT_W = None                       # a net's width outside the rule areas when the geo has none
SLOT_MAX = None                        # --slot-max default
SLOT_REPORT = None                     # a second slot length the report lists chains over
LANE_WINDOW = LANE_MARGIN = None       # byte-lane target = longest - window + margin
GROUND_FAR = None                      # signal vias farther than this from a ground via are listed
SPEC = None                            # length limits of the estimates ([plan.spec])
SEEDS = None                           # whole layer patterns of the fence mode ([plan.seeds])
XTAL_SEC_SIDE = None                   # index of the crystals' side in "ESWN" (the sections)


def setup(cfg):
    """Read the board's values (see the globals above) and configure bga_grid."""
    global MCU, SDRAM, POWER, SUPPLY33, WINDOW, SD_HALF, MARGIN, AREA, NOPOUR, SD_ZONE, MCU_CAPS, SD_CAPS, CAP_100N
    global CAP_KINDS, CAP_REACH, XTAL, XTAL_BOX, XTAL_GATE, XTAL_PREFIXES, XTAL_W, GATES, ORDER_OF, GATE_SECTOR
    global GATE_HINT, SD_THETA, PERIM, DEST_FAR, EST_REACH, LAYERS, TOP, BOTTOM, GROUND, BUS
    global DATA, MASK, NLANES, IDENTITY, CLOCK, CLOCK_R, CLOCK_RES, BUS_W, DEFAULT_W, SLOT_MAX, SLOT_REPORT
    global LANE_WINDOW, LANE_MARGIN, GROUND_FAR, SPEC, SEEDS, XTAL_SEC_SIDE
    bga_grid.configure(cfg)
    blk = cfg.datafile("bga_block.toml")
    if not blk.get("block") or not blk.get("plan"):
        raise config.ConfigError("%s: bga_block.toml [block] and [plan] are needed by bga_plan" % cfg.dir)
    b, p = blk["block"], blk["plan"]
    place = cfg.datafile("place.toml")
    MCU, SDRAM = b["mcu"], b["sdram"]
    SUPPLY33 = (cfg.need("bga.%s.supply" % MCU), cfg.need("bga.%s.supply" % SDRAM))
    GROUND = cfg.need("power.ground")
    POWER = (GROUND,) + SUPPLY33 + tuple(b["other_power"])
    WINDOW = tuple(p["window"])
    w, h = place["bodies"][SDRAM]
    SD_HALF = (w / 2, h / 2)
    MARGIN = place["rule_areas"]["margin"]
    AREA = {a["ref"]: a["name"] for a in place["rule_areas"]["areas"]}
    NOPOUR = {a["ref"]: a["no_pour"] for a in place["rule_areas"]["areas"] if a.get("no_pour")}
    SD_ZONE = (bga_grid.PWR_PLANE, SUPPLY33[1])
    MCU_CAPS = list(p["mcu_caps"])
    SD_CAPS = list(b["sdram_caps"])
    CAP_100N = {r: list(v) for r, v in b["caps_100n"].items()}
    CAP_KINDS = {r: [(k["name"], k["size"], k["net"], k["count"], k.get("tie")) for k in v] for r, v in p["cap_kinds"].items()}
    CAP_REACH = p["cap_reach"]
    XTAL = tuple(b["xtal_balls"].values())
    XTAL_BOX = tuple(b["xtal_box"])
    XTAL_GATE = p["xtal_gate"]
    XTAL_PREFIXES = tuple(b["xtal_prefixes"])
    XTAL_W = b["xtal_width"]
    GATES = dict(p["gates"])
    ORDER_OF = dict(p["order_of"])
    GATE_SECTOR = {k: tuple(v) for k, v in p["gate_sector"].items()}
    GATE_HINT = dict(p["gate_hint"])
    SD_THETA = tuple(p["sdram_theta"])
    PERIM = p["perim"]
    DEST_FAR, EST_REACH = p["dest_far"], p["est_reach"]
    LAYERS = tuple(p["layers"])
    TOP, BOTTOM = bga_grid.TOP, bga_grid.BOTTOM
    BUS = cfg.need("power.bus_prefix")
    DATA, MASK, NLANES = cfg.need("schematic.swap.data_net"), cfg.need("schematic.swap.mask_net"), cfg.need("schematic.swap.lanes")
    IDENTITY = cfg.path(p["identity"])
    CLOCK, CLOCK_R = p["clock"]
    CLOCK_RES = p["clock_resistor"]
    BUS_W, DEFAULT_W = b["bus_width"], p["default_width"]
    SLOT_MAX = b["slot_max"]
    SLOT_REPORT = p["slot_report"]
    LANE_WINDOW, LANE_MARGIN = p["lane_window"], p["lane_margin"]
    GROUND_FAR = p["ground_far"]
    SPEC = p["spec"]
    SEEDS = dict(p.get("seeds", {}))
    XTAL_SEC_SIDE = "ESWN".index(XTAL_GATE)
    return cfg


def is_signal(net):
    return bool(net) and net not in POWER and not net.startswith("unconnected-") and not net.startswith("+")


def is_data(net):
    """An SDRAM data bit (FMC_D<n>)."""
    return net.startswith(DATA) and net[len(DATA):].isdigit()


def lane_of(net):
    """The byte lane of a data bit or byte mask, else None."""
    return int(net[len(DATA):]) // 8 if is_data(net) else int(net[len(MASK):]) if net.startswith(MASK) else None


def r4(v):
    return round(float(v), 4)


# ---------------------------------------------------------------- the state: parts moved or taken off
def rot_pt(p, c, deg):
    """KiCad's footprint rotation (positive = anticlockwise on the screen, y down) of p about c."""
    th = math.radians(deg)
    x, y = p[0] - c[0], p[1] - c[1]
    return (x * math.cos(th) + y * math.sin(th), -x * math.sin(th) + y * math.cos(th))


def moved_pads(geo, ref, pos, rot):
    """The pads of `ref` with the footprint at pos / rot (degrees) instead of where the geo has it."""
    f = geo["fp"][ref]
    c0, d = f["pos"], rot - f["rot"]
    out = []
    for p in geo["pads"]:
        if p["ref"] != ref:
            continue
        q = dict(p)
        t = lambda pt: [r4(pos[0] + rot_pt(pt, c0, d)[0]), r4(pos[1] + rot_pt(pt, c0, d)[1])]
        q["pos"] = t(p["pos"])
        b = p["box"]
        cs = [t(c) for c in ((b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]))]
        q["box"] = [min(c[0] for c in cs), min(c[1] for c in cs), max(c[0] for c in cs), max(c[1] for c in cs)]
        q["poly"] = [t(c) for c in p["poly"]] if p["poly"] else None
        out.append(q)
    return out


def sdram_area(pos, rot):
    hw, hh = (SD_HALF if rot % 180 == 0 else SD_HALF[::-1])
    return [r4(pos[0] - hw - MARGIN), r4(pos[1] - hh - MARGIN), r4(pos[0] + hw + MARGIN), r4(pos[1] + hh + MARGIN)]


def planning_state(geo, sd_pos, sd_rot):
    """A copy of the geo with the SDRAM at its candidate place (pads, rule area, its power-plane block) and without the bottom
    parts the plan places itself."""
    g = dict(geo)
    gone = set(MCU_CAPS + SD_CAPS)
    g["pads"] = [p for p in geo["pads"] if p["ref"] not in gone and p["ref"] != SDRAM] + moved_pads(geo, SDRAM, sd_pos, sd_rot)
    g["fp"] = dict(geo["fp"]); g["fp"][SDRAM] = dict(geo["fp"][SDRAM], pos=list(sd_pos), rot=sd_rot)
    A = sdram_area(sd_pos, sd_rot)
    g["areas"] = {k: dict(v) for k, v in geo["areas"].items()}
    for k in (AREA[SDRAM], NOPOUR[SDRAM]):
        if k in g["areas"]:
            g["areas"][k]["rect"] = A
    zs = []
    for z in geo["zones"]:
        if SD_ZONE[0] in z["layers"] and z["net"] == SD_ZONE[1]:
            z = dict(z, poly=[[A[0], A[1]], [A[2], A[1]], [A[2], A[3]], [A[0], A[3]]])
        zs.append(z)
    g["zones"] = zs
    return g


# ---------------------------------------------------------------- lattice
class Lattice:
    """Half-pitch lattice of one BGA inside its rule area. (u, v): ball (0, 0) is the array's top-left ball."""

    def __init__(self, ref, pads, area):
        self.ref, self.area = ref, tuple(area)
        xs = sorted({p["pos"][0] for p in pads}); ys = sorted({p["pos"][1] for p in pads})
        self.pitch = round(min(min(b - a for a, b in zip(xs, xs[1:])), min(b - a for a, b in zip(ys, ys[1:]))), 4)
        self.h = self.pitch / 2
        self.x0, self.y0 = xs[0], ys[0]
        self.balls = {}
        for p in pads:
            self.balls[self.uv(p["pos"])] = p
        self.pad_r = pads[0]["r"]
        self.nu, self.nv = max(u for u, v in self.balls), max(v for u, v in self.balls)
        e = 1e-6
        self.u0 = int(math.ceil((area[0] - self.x0) / self.h - e)); self.u1 = int(math.floor((area[2] - self.x0) / self.h + e))
        self.v0 = int(math.ceil((area[1] - self.y0) / self.h - e)); self.v1 = int(math.floor((area[3] - self.y0) / self.h + e))

    def uv(self, p):
        return (int(round((p[0] - self.x0) / self.h)), int(round((p[1] - self.y0) / self.h)))

    def xy(self, u, v):
        return (r4(self.x0 + u * self.h), r4(self.y0 + v * self.h))

    def inside(self, u, v):
        return self.u0 <= u <= self.u1 and self.v0 <= v <= self.v1

    def edge_point(self, u, v, d):
        """Where the line from (u, v) in direction d leaves the rule area, and the side it leaves through."""
        x, y = self.xy(u, v)
        if d == (1, 0): return (self.area[2], y), "E"
        if d == (-1, 0): return (self.area[0], y), "W"
        if d == (0, 1): return (x, self.area[3]), "S"
        return (x, self.area[1]), "N"

    def run(self, u, v, d):
        """The lattice points from (u, v) (included) in direction d to the edge of the area."""
        out = []
        while self.inside(u, v):
            out.append((u, v))
            u, v = u + d[0], v + d[1]
        return out

    def via_sites(self):
        return [(u, v) for u in range(self.u0, self.u1 + 1) for v in range(self.v0, self.v1 + 1) if u % 2 and v % 2]


def sample_ok(field, mask, pts, skip_first=0.0):
    """Is the octilinear polyline (corners on the grid) free in the mask at every grid point it passes? Points
    nearer than skip_first to its first point are not looked at (the net's own ball pad)."""
    G = bga_grid
    p0 = pts[0]
    for a, b in zip(pts, pts[1:]):
        if not (field.inside(a) and field.inside(b)):
            return False
        J, I = G._line_cells(field, a, b)
        ok = mask[J, I]
        if skip_first > 0:
            ok = ok | (((field.xs[I] - p0[0]) ** 2 + (field.ys[J] - p0[1]) ** 2) < skip_first ** 2)
        if not ok.all():
            return False
    return True


def ball_options(lat, field, masks, via_ok, uv, l_turn=False, inner=None):
    """Every way of the ball at uv to the edge of the rule area that the state leaves open (inner: the layers of
    the runs after a dog-bone, default the plan's routing layers but the first; "L1" below is the top layer).
    -> [dict(layer, via (u, v) | None, nodes {layer: [(u, v)]}, l1 [(x, y)], run [(x, y)], side, exit (x, y), len)]"""
    if inner is None:
        inner = LAYERS[1:]
    T = bga_grid.TOP
    out = []
    bx = lat.xy(*uv)
    skip = lat.pad_r + 0.17                 # the net's own pad plus the track's need (0.135) and a grid step

    def add(layer, via, l1_pts, run_pts, nodes, side):
        ln = sum(math.dist(a, b) for a, b in zip(l1_pts, l1_pts[1:])) + sum(math.dist(a, b) for a, b in zip(run_pts, run_pts[1:]))
        out.append({"layer": layer, "via": via, "l1": l1_pts, "run": run_pts, "nodes": nodes, "side": side,
                    "exit": (run_pts or l1_pts)[-1], "len": ln})
    # L1 straight along the ball's own line, and with one turn (the SDRAM's aisle)
    for dn, d in DIRS.items():
        pts_uv = lat.run(uv[0], uv[1], d)[1:]
        e, side = lat.edge_point(uv[0], uv[1], d)
        if sample_ok(field, masks[T], [bx, e], skip):
            add(T, None, [bx, e], [], {T: pts_uv}, side)
        elif l_turn:
            for k in range(2, len(pts_uv)):
                c = pts_uv[k - 1]
                cx = lat.xy(*c)
                if not sample_ok(field, masks[T], [bx, cx], skip):
                    break
                for d2 in ((d[1], d[0]), (-d[1], -d[0])):
                    e2, side2 = lat.edge_point(c[0], c[1], d2)
                    if sample_ok(field, masks[T], [cx, e2]):
                        add(T, None, [bx, cx, e2], [], {T: pts_uv[:k] + lat.run(c[0], c[1], d2)[1:]}, side2)
    for dg in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        s = (uv[0] + dg[0], uv[1] + dg[1])
        if not lat.inside(*s):
            continue
        sx = lat.xy(*s)
        # L1 through the ball gap and on along the gap line
        for d in ((dg[0], 0), (0, dg[1])):
            e, side = lat.edge_point(s[0], s[1], d)
            if sample_ok(field, masks[T], [bx, sx, e], skip):
                add(T, None, [bx, sx, e], [], {T: lat.run(s[0], s[1], d)}, side)
        # a dog-bone via at the gap and a run on an inner layer
        if not via_ok(s) or not sample_ok(field, masks[T], [bx, sx], skip):
            continue
        for layer in inner:
            for eg in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                n = (s[0] + eg[0], s[1] + eg[1])
                if not lat.inside(*n):
                    continue
                nx_ = lat.xy(*n)
                for d in ((eg[0], 0), (0, eg[1])):
                    e, side = lat.edge_point(n[0], n[1], d)
                    if sample_ok(field, masks[layer], [sx, nx_, e]):
                        add(layer, s, [bx, sx], [sx, nx_, e], {layer: lat.run(n[0], n[1], d)}, side)
    return out


# ---------------------------------------------------------------- angles
def cw_angle(p, c):
    """Clockwise angle from north of p seen from c, degrees in [0, 360)."""
    return math.degrees(math.atan2(p[0] - c[0], -(p[1] - c[1]))) % 360.0


def lifts(theta, t, reach=200.0):
    """The lifts theta + 360 k within `reach` degrees of t."""
    out = []
    for k in (-2, -1, 0, 1, 2):
        v = theta + 360.0 * k
        if abs(v - t) <= reach:
            out.append(v)
    return out


def sd_entry_theta(area, p, west_is_near=True):
    """Target angle of an entry point p on the SDRAM's rule-area edge: its position along the outline from the
    middle of the far (east) side, going north, west, south, back east, mapped onto SD_THETA."""
    x0, y0, x1, y1 = area
    W, H = x1 - x0, y1 - y0
    yc = (y0 + y1) / 2
    e = 1e-6
    x, y = p
    if abs(x - x1) < e and y <= yc:
        s = yc - y
    elif abs(y - y0) < e:
        s = H / 2 + (x1 - x)
    elif abs(x - x0) < e:
        s = H / 2 + W + (y - y0)
    elif abs(y - y1) < e:
        s = H / 2 + W + H + (x - x0)
    else:
        s = H / 2 + W + H + W + (y1 - y)
    return SD_THETA[0] + (SD_THETA[1] - SD_THETA[0]) * s / (2 * (W + H))


# ---------------------------------------------------------------- the model
class Model:
    def __init__(self, geo, sd_pos, sd_rot, slot_max=None, lane_map=None, log=print):
        slot_max = SLOT_MAX if slot_max is None else slot_max                 # defaults: bga_block.toml, [schematic.swap] lanes
        lane_map = tuple(range(NLANES)) if lane_map is None else lane_map
        import numpy as np
        G = bga_grid
        self.np, self.G, self.log = np, G, log
        self.geo0 = geo
        self.sd_pos, self.sd_rot, self.slot_max, self.lane_map = tuple(sd_pos), sd_rot, slot_max, tuple(lane_map)
        self.geo = g = planning_state(geo, sd_pos, sd_rot)
        t0 = time.time()
        reserve = [G.Item("<xtal>", (TOP,), "poly", poly=[(XTAL_BOX[0], XTAL_BOX[1]), (XTAL_BOX[2], XTAL_BOX[1]), (XTAL_BOX[2], XTAL_BOX[3]), (XTAL_BOX[0], XTAL_BOX[3])], tag="reserve")]
        self.field = G.Field(g, WINDOW, items=G.scene_items(g, extra=reserve))
        self.lat = {}
        for ref, an in ((MCU, AREA[MCU]), (SDRAM, AREA[SDRAM])):
            self.lat[ref] = Lattice(ref, [p for p in g["pads"] if p["ref"] == ref], g["areas"][an]["rect"])
        self.mc = tuple(g["fp"][MCU]["pos"])
        self.pads = {(p["ref"], p["num"]): p for p in g["pads"]}
        self.slots0 = G.Slots(g, [(n, p, d) for n, p, d, h in g["vias"]])
        self._bytes()
        log("state: %d items, field %.1f s" % (len(self.field.items), time.time() - t0))

    # ---- SDRAM pin functions (which byte a data ball belongs to) from the identity dump of line_order.py
    def _bytes(self):
        ident = json.load(open(IDENTITY))[SDRAM]["pads"]
        self.sd_fn = {}                                     # ball number -> ("D", byte) | ("NBL", byte) | ("FIX", net)
        for num, (x, y, net) in ident.items():
            if is_data(net):
                self.sd_fn[num] = ("D", int(net[len(DATA):]) // 8, net)
            elif net.startswith(MASK):
                self.sd_fn[num] = ("NBL", int(net[len(MASK):]), net)
            elif net.startswith(BUS):
                self.sd_fn[num] = ("FIX", net, net)

    def sd_balls_for(self, net):
        """The SDRAM balls an MCU net may end on (SPEC 9: bits free inside a lane, lanes as wholes by lane_map)."""
        if net == CLOCK:
            return []
        if is_data(net):
            byte = self.lane_map[int(net[len(DATA):]) // 8]
            return sorted(n for n, f in self.sd_fn.items() if f[0] == "D" and f[1] == byte)
        if net.startswith(MASK):
            byte = self.lane_map[int(net[len(MASK):])]
            return sorted(n for n, f in self.sd_fn.items() if f[0] == "NBL" and f[1] == byte)
        return sorted(n for n, f in self.sd_fn.items() if f[0] == "FIX" and f[1] == net)

    # ---- gates
    def gate_of(self, net):
        if net in XTAL:
            return XTAL_GATE
        if net in GATE_HINT:
            return GATE_HINT[net]
        dest = [p for p in self.geo["pads"] if p["net"] == net and p["ref"] != MCU]
        if not dest:
            return "N"
        far = max(dest, key=lambda p: math.dist(p["pos"], self.mc))
        th = cw_angle(far["pos"], self.mc)
        names = [k for k in GATES if k != XTAL_GATE]
        return min(names, key=lambda k: min(abs(th - GATES[k]), 360 - abs(th - GATES[k])))

    def dest_dist(self, net, gate):
        dest = [p for p in self.geo["pads"] if p["net"] == net and p["ref"] != MCU]
        if not dest:
            return DEST_FAR
        th = GATES[gate]
        best = min(dest, key=lambda p: min(abs(cw_angle(p["pos"], self.mc) - th), 360 - abs(cw_angle(p["pos"], self.mc) - th)))
        return math.dist(best["pos"], self.mc)

    # ---- options
    def build_options(self):
        G, f = self.G, self.field
        t0 = time.time()
        masks = {l: f.track_free(l, BUS_W) for l in LAYERS}
        self.masks0 = masks
        self.sites, self.psites, self.pmask, self.fix = {}, {}, {}, {}
        self.opts = {}                                      # (ref, ball num) -> [option]
        for ref, lat in self.lat.items():
            ok = {}
            for s in lat.via_sites():
                p = lat.xy(*s)
                ok[s] = f.is_area(p, f.via_in[0] / 2) and f.via_ok(p)
            self.sites[ref] = ok
            for net in sorted({p["net"] for p in lat.balls.values() if p["net"] in POWER}):
                D, H = f.opened(net)
                self.psites[(ref, net)] = {s: f.is_area(lat.xy(*s), f.via_in[0] / 2) and f.via_ok(lat.xy(*s), D, H) for s in ok}
                self.pmask[net] = f.track_free(TOP, BUS_W, D, H)
            for uv, pad in sorted(lat.balls.items()):
                if not is_signal(pad["net"]):
                    continue
                self.opts[(ref, pad["num"])] = ball_options(lat, f, masks, lambda s: ok.get(s, False), uv, l_turn=(ref == SDRAM))
        # the MCU side: angle of the exit, the target and the estimate
        m = self.lat[MCU]
        for (ref, num), ol in self.opts.items():
            if ref != MCU:
                for o in ol:
                    o["theta"] = sd_entry_theta(self.lat[SDRAM].area, o["exit"])
                continue
            net = self.pads[(ref, num)]["net"]
            for o in ol:
                o["t"] = cw_angle(o["exit"], self.mc)
        self.log("options: MCU %d for %d balls, SDRAM %d for %d balls, %.1f s" % (
            sum(len(v) for k, v in self.opts.items() if k[0] == MCU), sum(1 for k in self.opts if k[0] == MCU),
            sum(len(v) for k, v in self.opts.items() if k[0] == SDRAM), sum(1 for k in self.opts if k[0] == SDRAM), time.time() - t0))


# ---------------------------------------------------------------- the mixed-integer program
class LP:
    def __init__(self):
        self.lb, self.ub, self.c, self.int_, self.R, self.C, self.V, self.lo, self.hi = [], [], [], [], [], [], [], [], []
        self.names = []

    def var(self, cost=0.0, lb=0.0, ub=1.0, integer=True, name=None):
        self.lb.append(lb); self.ub.append(ub); self.c.append(cost); self.int_.append(1 if integer else 0); self.names.append(name)
        return len(self.c) - 1

    def row(self, cols, vals, lo, hi):
        r = len(self.lo)
        self.R.extend([r] * len(cols)); self.C.extend(cols); self.V.extend(vals); self.lo.append(lo); self.hi.append(hi)

    def solve(self, time_limit=120.0, gap=0.01):
        import numpy as np
        from scipy.optimize import milp, LinearConstraint, Bounds
        from scipy.sparse import coo_matrix
        A = coo_matrix((self.V, (self.R, self.C)), shape=(len(self.lo), len(self.c))).tocsr()
        res = milp(np.array(self.c), constraints=LinearConstraint(A, np.array(self.lo), np.array(self.hi)), integrality=np.array(self.int_) * (0 if os.environ.get('PLAN_RELAX') else 1),
                   bounds=Bounds(np.array(self.lb), np.array(self.ub)), options={"time_limit": time_limit, "mip_rel_gap": gap, "disp": bool(os.environ.get("PLAN_DISP"))})
        return res


CAP_GEOM = {"0402": (0.48, 0.28, 0.31), "0603": (0.775, 0.45, 0.475)}     # pad centre offset, pad half length, pad half width


def staircases(max_d2):
    """Every monotone lattice path (list of site offsets from (0, 0)) whose ends are just farther apart than the
    slot limit allows (squared distance in site pitches > max_d2) while one step back is still inside it: the
    minimal chains to forbid. One orientation each (the reverse path is the same set of sites)."""
    ends = set()
    n = int(math.sqrt(max_d2)) + 2
    for dx in range(0, n + 1):
        for dy in range(-n, n + 1):
            if dx * dx + dy * dy <= max_d2 or (dx == 0 and dy <= 0):
                continue
            back = [(dx - 1, dy)] if dx > 0 else []
            back += [(dx, dy - (1 if dy > 0 else -1))] if dy != 0 else []
            if any(a * a + b * b <= max_d2 for a, b in back):
                ends.add((dx, dy))
    paths = set()

    def walk(cur, end, acc):
        if cur == end:
            paths.add(tuple(acc))
            return
        if end[0] > cur[0]:
            walk((cur[0] + 1, cur[1]), end, acc + [(cur[0] + 1, cur[1])])
        if end[1] != cur[1]:
            sy = 1 if end[1] > cur[1] else -1
            walk((cur[0], cur[1] + sy), end, acc + [(cur[0], cur[1] + sy)])
    for e in sorted(ends):
        walk((0, 0), e, [(0, 0)])
    return sorted(paths)


def _dist_rects(q, rects):
    return min(math.hypot(max(r[0] - q[0], 0, q[0] - r[2]), max(r[1] - q[1], 0, q[1] - r[3])) for r in rects)


def cap_candidate(lat, s, g, size):
    """A two-pad part with its pads over the sites s and g (in line): centre, rotation, pad centres and rectangles,
    the lattice points its pads block on L6 and the via sites they cover."""
    off, hl, hw = CAP_GEOM[size]
    d = ((g[0] > s[0]) - (g[0] < s[0]), (g[1] > s[1]) - (g[1] < s[1]))
    sx, gx = lat.xy(*s), lat.xy(*g)
    c = ((sx[0] + gx[0]) / 2, (sx[1] + gx[1]) / 2)
    p1 = (c[0] - d[0] * off, c[1] - d[1] * off); p2 = (c[0] + d[0] * off, c[1] + d[1] * off)
    hx, hy = (hl, hw) if d[0] else (hw, hl)
    rects = [(p[0] - hx, p[1] - hy, p[0] + hx, p[1] + hy) for p in (p1, p2)]
    body = (min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects), max(r[3] for r in rects))
    bl, bv, probe = [], [], []
    u_lo, v_lo = lat.uv((body[0] - 0.4, body[1] - 0.4)); u_hi, v_hi = lat.uv((body[2] + 0.4, body[3] + 0.4))
    for uu in range(u_lo, u_hi + 1):
        for vv in range(v_lo, v_hi + 1):
            q = lat.xy(uu, vv)
            dd = _dist_rects(q, rects)
            if dd < 0.135 - 1e-6:
                bl.append((uu, vv))
            if dd < 0.275 - 1e-6 and (uu, vv) not in (s, g) and uu % 2 and vv % 2:
                bv.append((uu, vv))
            if body[0] - 0.25 <= q[0] <= body[2] + 0.25 and body[1] - 0.25 <= q[1] <= body[3] + 0.25:
                probe.append((uu, vv))
    return dict(size=size, pos=(r4(c[0]), r4(c[1])), rot={(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): -90}[d],
                pads=[(r4(p1[0]), r4(p1[1])), (r4(p2[0]), r4(p2[1]))], rects=rects, body=body, bl=bl, bv=bv, probe=probe, s=s, g=g)


def power_balls(self, ref):
    """{ball num: (uv, net, [legal sites])} of the supply and ground balls of a package."""
    lat, f, out = self.lat[ref], self.field, {}
    for uv, pad in sorted(lat.balls.items()):
        if pad["net"] not in POWER:
            continue
        cands = []
        for dg in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            s = (uv[0] + dg[0], uv[1] + dg[1])
            if self.psites[(ref, pad["net"])].get(s) and sample_ok(f, self.pmask[pad["net"]], [lat.xy(*uv), lat.xy(*s)], lat.pad_r + 0.17):
                cands.append(s)
        out[pad["num"]] = (uv, pad["net"], cands)
    return out


def slot_rows(self, lp, FA, FB):
    """The staircase cuts over the site indicators of the two plane classes."""
    G, m_lat = self.G, self.lat[MCU]
    d = self.field.via_in[0]
    if G.merge_dist(d, d) <= m_lat.pitch:
        return 0
    reach = (self.slot_max - d - 2 * G.PLANE_CLR) / m_lat.pitch
    paths = staircases(reach * reach + 1e-9)
    n = 0
    for dct in (FA, FB):
        for s in sorted(dct):
            for path in paths:
                cols, const = [], 0
                for dx, dy in path:
                    q = (s[0] + 2 * dx, s[1] + 2 * dy)
                    if q not in dct:
                        cols = None
                        break
                    if dct[q] is True:
                        const += 1
                    else:
                        cols.append(dct[q])
                if cols is None:
                    continue
                if not cols:
                    self.log("  ! fixed vias alone make a chain over the limit at %s" % (m_lat.xy(*s),))
                    continue
                lp.row(cols, [1.0] * len(cols), -float("inf"), len(path) - 1.0 - const)
                n += 1
    return n


def solve_power(self, ref, time_limit=60.0):
    """Steps 2 and 3 for one package. Step 2: a via for every supply / ground ball (sharing costs), with the plane
    slots kept and a free site left for every signal ball of the inner rows; supply vias with a ground via one
    site away are preferred (a capacitor fits there). Step 3: the bottom capacitors onto those vias."""
    np, f, lat = self.np, self.field, self.lat[ref]
    lp = LP()
    PB = power_balls(self, ref)
    PV, PA, VAT = {}, {}, {}

    def pv(s, net):
        if (s, net) not in PV:
            PV[(s, net)] = lp.var(0.3, name="pv")
            VAT.setdefault(s, []).append(PV[(s, net)])
        return PV[(s, net)]
    share = {}
    for num, (uv, net, cands) in sorted(PB.items()):
        if not cands:
            self.log("  ! supply ball %s.%s (%s) has no legal site" % (ref, num, net))
            continue
        vs = []
        for s in cands:
            v = lp.var(0.0, name="pa")
            PA[(num, s)] = v
            lp.row([v, pv(s, net)], [1.0, -1.0], -np.inf, 0.0)
            share.setdefault((s, net), []).append(v)
            vs.append(v)
        lp.row(vs, [1.0] * len(vs), 1.0, 1.0)
    for k, vs in sorted(share.items()):
        if len(vs) > 1:
            sh = lp.var(SHARE_COST, ub=3.0, integer=False, name="sh")
            lp.row(vs + [sh], [1.0] * len(vs) + [-1.0], -np.inf, 1.0)
    # a supply ball whose via has a ground via one site away takes a 0402 over the two
    gnd_sites = {s for (s, n) in PV if n == GROUND}
    for num, (uv, net, cands) in sorted(PB.items()):
        if net not in SUPPLY33:
            continue
        ws = []
        for s in cands:
            for d in DIRS.values():
                g = (s[0] + 2 * d[0], s[1] + 2 * d[1])
                if g in gnd_sites:
                    w = lp.var(0.0, integer=False, name="pair")
                    lp.row([w, PA[(num, s)]], [1.0, -1.0], -np.inf, 0.0)
                    lp.row([w, PV[(g, GROUND)]], [1.0, -1.0], -np.inf, 0.0)
                    ws.append(w)
        if ws:
            z = lp.var(-2.0, integer=False, name="paired")
            lp.row([z] + ws, [1.0] + [-1.0] * len(ws), -np.inf, 0.0)
    for s, vs in sorted(VAT.items()):
        if len(vs) > 1:
            lp.row(vs, [1.0] * len(vs), -np.inf, 1.0)
    # a free site for every signal ball of the inner rows (a matching, so that no two count on the same site)
    MT = {}
    if ref == MCU:
        for uv, pad in sorted(lat.balls.items()):
            if not is_signal(pad["net"]):
                continue
            if min(uv[0], lat.nu - uv[0], uv[1], lat.nv - uv[1]) // 2 < 2:
                continue
            vs = []
            for dg in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                s = (uv[0] + dg[0], uv[1] + dg[1])
                if self.sites[ref].get(s):
                    v = lp.var(0.0, name="mt")
                    MT[(pad["num"], s)] = v
                    vs.append(v)
            sl = lp.var(60.0, name="mt_slack")
            lp.row(vs + [sl], [1.0] * (len(vs) + 1), 1.0, 1.0)
    by_site = {}
    for (num, s), v in MT.items():
        by_site.setdefault(s, []).append(v)
    for s, vs in sorted(by_site.items()):
        lp.row(vs + VAT.get(s, []), [1.0] * (len(vs) + len(VAT.get(s, []))), -np.inf, 1.0)
    FA, FB = {}, {}
    n = 0
    if ref == MCU:
        for s in sorted(self.sites[ref]):
            l3 = self.slots0.l3_net(lat.xy(*s))
            sv = by_site.get(s, [])
            a = sv + [v for (ss, n_), v in sorted(PV.items()) if ss == s and n_ != GROUND]
            b = sv + [v for (ss, n_), v in sorted(PV.items()) if ss == s and n_ != l3]
            for dct, lst in ((FA, a), (FB, b)):
                if lst:
                    fv = lp.var(0.0, integer=False, name="f")
                    lp.row([fv] + lst, [1.0] + [-1.0] * len(lst), 0.0, 0.0)
                    dct[s] = fv
        n = slot_rows(self, lp, FA, FB)
    t1 = time.time()
    res = lp.solve(time_limit)
    self.log("  supply vias %s: %d variables, %d rows, status %s, objective %s, %.1f s" % (ref, len(lp.c), len(lp.lo), res.status, None if res.x is None else round(res.fun, 2), time.time() - t1))
    if res.x is None:
        return None
    x = res.x
    fix = {"pa": {}, "pv": {}, "caps": [], "blockL6": set(), "blockVia": set(), "own": {}}
    for (num, s), v in PA.items():
        if x[v] > 0.5:
            fix["pa"][num] = s
    for (s, net), v in PV.items():
        if x[v] > 0.5:
            fix["pv"][s] = net
    fix["matched"] = {s for (num, s), v in MT.items() if x[v] > 0.5}
    fix["mt_slack"] = int(round(sum(x[i] for i, nme in enumerate(lp.names) if nme == "mt_slack")))
    self.fix[ref] = fix
    return place_caps(self, ref, PB, time_limit)


def place_caps(self, ref, PB, time_limit=60.0):
    """Step 3: each two-pad bottom part on a pair of sites in line (0402: one pitch, 0603: two), both pads over a
    via of their net. Vias of step 2 are used where they are; a pad without one gets a via of its own (cost),
    never on a site a signal ball was promised, never joining a plane chain over the limit (checked after the
    solve; an offending candidate is taken out and the step repeated)."""
    np, f, lat, G = self.np, self.field, self.lat[ref], self.G
    fix = self.fix[ref]
    d6 = f.D[BOTTOM]
    supply = [(num, lat.xy(*uv), net) for num, (uv, net, c) in sorted(PB.items()) if net != GROUND]
    banned = set()
    for rnd in range(12):
        lp = LP()
        CAPV, cc_of, NEW = {}, {}, {}
        probe, cover, blockers = {}, {}, {}

        def site_var(s, net):
            """None when a via of `net` is there already; a variable for a new via; False when the site is not available."""
            if fix["pv"].get(s) == net:
                return None
            if s in fix["pv"] or s in fix["matched"] or not self.psites[(ref, net)].get(s):
                return False
            if (s, net) not in NEW:
                NEW[(s, net)] = lp.var(2.5, name="new")
            return NEW[(s, net)]
        for name, size, net, count, tie in CAP_KINDS[ref]:
            step = 2 if size == "0402" else 4
            if tie:
                sites = sorted({fix["pa"][num] for num, (uv, n, c) in PB.items() if n == tie and num in fix["pa"]})
            else:
                near = [lat.xy(*uv) for num, (uv, n, c) in PB.items() if n == net]
                sites = sorted(s for s, ok_ in self.psites[(ref, net)].items() if ok_ and any(math.dist(lat.xy(*s), b) <= CAP_REACH for b in near))
            vars_ = []
            for s in sites:
                for dn, d in sorted(DIRS.items()):
                    g = (s[0] + step * d[0], s[1] + step * d[1])
                    if (name, s, g) in banned:
                        continue
                    vs_, vg_ = site_var(s, net), site_var(g, GROUND)
                    if vs_ is False or vg_ is False:
                        continue
                    cc = cap_candidate(lat, s, g, size)
                    j0, j1, i0, i1 = f._win(cc["body"], 0.2)             # the pads against the state's L6 copper
                    if (d6[j0:j1, i0:i1] < 0.05).any():
                        continue
                    if any(q in fix["pv"] for q in cc["bv"]):            # a foreign via under or beside a pad
                        continue
                    nearest = min((math.dist(cc["pads"][0], b) for num, b, bn in supply if bn == net), default=0.0)
                    v = lp.var(0.3 * nearest + 0.4 * len([q for q in cc["bv"] if q in fix["matched"]]) + 0.001 * len(vars_), name="cap")
                    CAPV[(name, s, g)] = v
                    cc_of[v] = cc
                    vars_.append(v)
                    for w in (vs_, vg_):
                        if w is not None:
                            lp.row([v, w], [1.0, -1.0], -np.inf, 0.0)
                    for q in cc["probe"]:
                        probe.setdefault(q, []).append(v)
                    for q in cc["bv"]:
                        blockers.setdefault(q, []).append(v)
                    if name == "100n":
                        for num, bxy, bnet in supply:
                            if bnet == net and math.dist(cc["pads"][0], bxy) <= CAP_REACH:
                                cover.setdefault(num, []).append(v)
            if len(vars_) < count:
                self.log("  ! %s %s: only %d candidates for %d parts" % (ref, name, len(vars_), count))
            lp.row(vars_, [1.0] * len(vars_), min(count, len(vars_)), count)
        for q, vs in sorted(probe.items()):
            if len(vs) > 1:
                lp.row(vs, [1.0] * len(vs), -np.inf, 1.0)
        unc = []
        for num, bxy, bnet in supply:
            if bnet in SUPPLY33:
                vs = cover.get(num, [])
                sl = lp.var(80.0, name="uncovered")
                unc.append((num, sl))
                lp.row(vs + [sl], [1.0] * (len(vs) + 1), 1.0, np.inf)
        by_site = {}
        for (s, net), v in NEW.items():
            by_site.setdefault(s, []).append(v)
        for s, vs in sorted(by_site.items()):
            if len(vs) > 1:
                lp.row(vs, [1.0] * len(vs), -np.inf, 1.0)
            for c in blockers.get(s, []):                                  # no new via under another part's pads
                lp.row([c] + vs, [1.0] * (len(vs) + 1), -np.inf, 1.0)
        t1 = time.time()
        res = lp.solve(time_limit)
        if res.x is None:
            self.log("  ! capacitors %s: no placement (status %s)" % (ref, res.status))
            return fix
        x = res.x
        new = {s: net for (s, net), v in NEW.items() if x[v] > 0.5}
        # plane chains with the new vias (and the sites promised to signal balls)
        S = G.Slots(self.geo, [(n_, lat.xy(*s), f.via_in[0]) for s, n_ in list(fix["pv"].items()) + list(new.items())]
                    + [("<signal>", lat.xy(*s), f.via_in[0]) for s in fix["matched"]])
        bad = [c for c in S.longest() if c[0] > self.slot_max + 1e-6] if G.merge_dist(f.via_in[0], f.via_in[0]) > lat.pitch else []
        newxy = {lat.xy(*s): (s, net) for s, net in new.items()}
        hit = sorted({newxy[p] for ln, pl, mem in bad for n_, p in mem if p in newxy})
        if hit:
            for (name, s, g), v in CAPV.items():
                if x[v] > 0.5 and any(q in (s, g) for q, net in hit):
                    banned.add((name, s, g))
            continue
        self.log("  capacitors %s: %d variables, %d rows, round %d, status %s, objective %s, %.1f s; %d new vias" % (
            ref, len(lp.c), len(lp.lo), rnd + 1, res.status, round(res.fun, 2), time.time() - t1, len(new)))
        break
    k100 = 0
    for (name, s, g), cc in sorted(((k, cc_of[v]) for k, v in CAPV.items() if x[v] > 0.5), key=lambda kv: (kv[0][0] != "100n", kv[1]["pos"][1], kv[1]["pos"][0])):
        if name == "100n":
            refname = CAP_100N[ref][k100]; k100 += 1
        else:
            refname = name
        net = next(n_ for nm, sz, n_, cnt, tie in CAP_KINDS[ref] if nm == name)
        cc = dict(cc, ref=refname, kind=name, nets=(net, GROUND))
        fix["caps"].append(cc)
        fix["blockL6"].update(cc["bl"]); fix["blockVia"].update(cc["bv"])
    for s, net in sorted(new.items()):
        fix["pv"][s] = net
        fix["own"][s] = net
    fix["uncovered"] = [num for num, sl in unc if x[sl] > 0.5]
    return fix


def signal_options(self, ref):
    """The options of every signal ball of a package that the fixed supply vias and capacitors leave open."""
    fix = self.fix[ref]
    out = {}
    for (r, num), ol in sorted(self.opts.items()):
        if r != ref:
            continue
        keep = []
        for k, o in enumerate(ol):
            if o["via"] and (o["via"] in fix["pv"] or o["via"] in fix["blockVia"]):
                continue
            if any(p in fix["pv"] for p in o["nodes"].get(TOP, ())):
                continue
            if any(p in fix["blockL6"] for p in o["nodes"].get(BOTTOM, ())):
                continue
            keep.append(k)
        out[num] = keep
    return out


def node_rows(lp, node, vias_at):
    import numpy as np
    keys = set(p for (p, l) in node) | set(vias_at)
    for p in sorted(keys):
        va = vias_at.get(p, [])
        for l in LAYERS:
            tr = node.get((p, l), [])
            if len(tr) + len(va) > 1 and (tr or l == TOP):
                lp.row(tr + va, [1.0] * (len(tr) + len(va)), -np.inf, 1.0)


def order_rows(lp, seq, wrap=True):
    """seq: positions in order, each a list of (variable, lo, hi): the variable, when 1, puts a net with the target
    interval [lo, hi] at that position (at most one variable per position is 1). Rows that forbid every inversion:
    a net at an earlier position whose interval lies wholly above that of a net at a later position (lo > hi'),
    and, with wrap, a full turn between any two (lo - 360 > hi'). For every threshold tau (a value of hi):
    a_i = "some net at positions <= i lies above tau", b_i = "some net at positions >= i lies at or below tau",
    a_i + b_(i+1) <= 1. The sums are what the solver sees: no big-M."""
    inf = float("inf")
    taus = sorted({round(hi, 6) for pos in seq for v, lo, hi in pos})
    n = 0
    for tau in taus:
        above = [[v for v, lo, hi in pos if lo > tau + 1e-7] for pos in seq]
        below = [[v for v, lo, hi in pos if hi <= tau + 1e-7] for pos in seq]
        if any(above) and any(below):
            a_at, prev = [], None
            for vs in above:
                if vs:
                    a = lp.var(0.0, integer=False, name="ord")
                    lp.row([a] + vs, [1.0] + [-1.0] * len(vs), 0.0, inf)
                    if prev is not None:
                        lp.row([a, prev], [1.0, -1.0], 0.0, inf)
                    prev = a
                a_at.append(prev)
            b_at, prev = [None] * len(seq), None
            for i in range(len(seq) - 1, -1, -1):
                vs = below[i]
                if vs:
                    b = lp.var(0.0, integer=False, name="ord")
                    lp.row([b] + vs, [1.0] + [-1.0] * len(vs), 0.0, inf)
                    if prev is not None:
                        lp.row([b, prev], [1.0, -1.0], 0.0, inf)
                    prev = b
                b_at[i] = prev
            last = None
            for i in range(len(seq) - 1):
                if a_at[i] is not None and b_at[i + 1] is not None and (a_at[i], b_at[i + 1]) != last:
                    lp.row([a_at[i], b_at[i + 1]], [1.0, 1.0], -inf, 1.0)
                    last = (a_at[i], b_at[i + 1])
                    n += 1
        if wrap:
            far = [v for pos in seq for v, lo, hi in pos if lo - 360.0 > tau + 1e-7]
            low = [v for pos in seq for v, lo, hi in pos if hi <= tau + 1e-7]
            if far and low:
                cvar = lp.var(0.0, integer=False, name="ord")
                dvar = lp.var(0.0, integer=False, name="ord")
                for pos in seq:
                    vs = [v for v, lo, hi in pos if lo - 360.0 > tau + 1e-7]
                    if vs:
                        lp.row([cvar] + vs, [1.0] + [-1.0] * len(vs), 0.0, inf)
                    vs = [v for v, lo, hi in pos if hi <= tau + 1e-7]
                    if vs:
                        lp.row([dvar] + vs, [1.0] + [-1.0] * len(vs), 0.0, inf)
                lp.row([cvar, dvar], [1.0, 1.0], -inf, 1.0)
                n += 1
    return n


def plan_a(net, is_sd, o, th, cy):
    """Layer plan A (main session, 2026-11-22). -> None when the option is outside the plan, else the penalty
    (0 inside the plan; SOFT_L6 for an SDRAM net that leaves the MCU on L6, the plan's one soft point).
      SDRAM nets  leave on L1 or L4: east side straight across, north side clockwise (north-about), south side
                  anticlockwise (south-about), west side on L4 only, north-about above the MCU's centre line
                  and south-about below it.
      other nets  on L1 only straight outwards (within 60 degrees of their gate), else on L6 any way round; L4
                  outside the field is the SDRAM's."""
    lay, side, d = o["layer"], o["side"], th - o["t"]
    if is_sd:
        if side == SD_SIDE:
            ok = abs(d) <= 60.0
        elif side == "N":
            ok = 0.0 < d <= 185.0
        elif side == "S":
            ok = -185.0 <= d < 0.0
        else:
            ok = lay != LAYERS[0] and ((d > 0) == (o["exit"][1] < cy))
        if not ok:
            return None
        return 0.0 if lay in (LAYERS[0], LAYERS[1]) else SOFT_L6
    if lay == LAYERS[1]:
        return None
    if lay == LAYERS[0]:
        return 0.0 if abs(d) <= 60.0 else None
    return 0.0


FENCE_COST = 300.0                     # a section of the MCU outline with SDRAM lanes on all three layers
SEC_PER_SIDE = 3


def section_of(t, per_side=SEC_PER_SIDE):
    """Section of the MCU outline an angle lies in: sections start at the north-east corner (45 degrees) and count
    clockwise, per_side to a side (east 0 .., south, west, north)."""
    return int((((t - 45.0) % 360.0) / 90.0) * per_side + 1e-9) % (4 * per_side)


def section_name(s, per_side=SEC_PER_SIDE):
    side = "ESWN"[s // per_side]
    part = s % per_side
    ends = {"E": ("north", "south"), "S": ("east", "west"), "W": ("south", "north"), "N": ("west", "east")}[side]
    return "%s side %s" % (side, ends[0] if part == 0 else ends[1] if part == per_side - 1 else "middle")


def swept(t, th, per_side=SEC_PER_SIDE):
    """The sections a river from the exit angle t to the (lifted) target angle th passes or starts in."""
    lo, hi = min(t, th), max(t, th)
    out, a = [], lo
    while a <= hi + 1e-9:
        s = section_of(a, per_side)
        if s not in out:
            out.append(s)
        a += 2.0
    s = section_of(hi, per_side)
    if s not in out:
        out.append(s)
    return out


SOFT_L6, SOFT_SEG = 60.0, 150.0        # an SDRAM net on L6 outside the field; each stretch of the outline where that happens


def segment_of(t, per_side):
    """Index of the stretch of the MCU outline an exit at clockwise angle t lies on: each side is cut into
    per_side stretches of equal angle; stretch 0 starts at north (t = 0) and they count clockwise."""
    n = 4 * per_side
    return int(((t % 360.0) / 360.0) * n + 1e-9) % n


def solve_mcu(self, time_limit=90.0, prune=float(os.environ.get('PLAN_PRUNE', 30.0)), steps=None, order=None, per_side=2, sd_cap=24, free=None):
    # free: {section: set of layers} - the layers kept free of SDRAM lanes in each section of the outline (mode "fence")
    # order: "planA" = inside layer plan A (plan_a), the order rows only on L1 and L6; "rows" = the exact order rows
    # on every layer; "rivers" = one target per stretch of the outline; "none" = no order at all
    mode = order or getattr(self, "order_mode", "fence")
    order = mode == "rows"
    if mode == "none":
        steps = {}
    # steps: {(layer, exit point): target value} - a lane takes only nets of that target (no order rows needed);
    # order: put the order rows in instead (exact, but too slow for HiGHS 1.2 on the whole MCU)
    """Stage X: every MCU signal ball's option and its way round the MCU, with the supply vias and capacitors
    fixed: one thing per lattice point and layer, plane slots, one monotone chain of targets per layer."""
    np, f = self.np, self.field
    lp = LP()
    m_lat, s_lat, mc = self.lat[MCU], self.lat[SDRAM], self.mc
    fix = self.fix[MCU]
    keep = signal_options(self, MCU)
    gap_mm = max(0.0, s_lat.area[0] - m_lat.area[2])
    r201 = self.pads.get((CLOCK_RES, "1"))
    # the angles at which each SDRAM net can be entered, per layer (over its balls and their open options)
    keep_s = signal_options(self, SDRAM)
    span, sd_nets = {}, {}
    for (ref, num), ol in sorted(self.opts.items()):
        net = self.pads[(ref, num)]["net"]
        if ref != MCU or not net.startswith(BUS):
            continue
        for bn in self.sd_balls_of(net):
            for k in keep_s.get(bn, []):
                o = self.opts[(SDRAM, bn)][k]
                a = span.setdefault((net, o["layer"]), [o["theta"], o["theta"]])
                a[0], a[1] = min(a[0], o["theta"]), max(a[1], o["theta"])
        sd_nets[net] = num
    self.span, self.sd_nets = span, sd_nets
    X, U, info = {}, {}, {}
    node, vias_at, sigvia, slot_x, lane_len = {}, {}, {}, {}, {}
    self.support, self.cands = {}, {}
    seg_use, sd_layer, soft, sweeps, leaves = {}, {}, {}, {}, {}

    def reg(o, v):
        if o["via"]:
            vias_at.setdefault(o["via"], []).append(v)
            sigvia.setdefault(o["via"], []).append(v)
        for l, pts in o["nodes"].items():
            for p in pts:
                node.setdefault((p, l), []).append(v)
    for num, ks in sorted(keep.items()):
        net = self.pads[(MCU, num)]["net"]
        if net in XTAL:
            continue
        is_sd = net.startswith(BUS)
        gate = None if is_sd else self.gate_of(net)
        ddist = None if is_sd else self.dest_dist(net, gate)
        cand = []
        for k in ks:
            o = self.opts[(MCU, num)][k]
            if net == CLOCK and not (o["layer"] == TOP and o["side"] == SD_SIDE and r201 and abs(o["exit"][1] - r201["pos"][1]) < 0.01):
                continue
            if is_sd and (net, o["layer"]) not in span:
                continue
            ths = lifts(SD_ANGLE if is_sd else GATES[gate], o["t"], REACH)
            if mode == "fence" and not is_sd and ths:          # the other balls change layer as they need: one variant, the near way
                ths = [min(ths, key=lambda v_: abs(v_ - o["t"]))]
            for th in ths:
                arc = abs(th - o["t"])
                est = (max(0.0, arc - 45.0) / 360.0 * PERIM + gap_mm / 2) if is_sd else (arc / 360.0 * PERIM + max(0.0, ddist - EST_REACH))
                cost = o["len"] + est + (VIA_COST if o["via"] else 0.0) + (0.5 if o["layer"] == BOTTOM else 0.0)
                # the order is kept between the four directions only (the gates of one direction share a value)
                tho = th if is_sd else th - GATES[gate] + ORDER_OF[gate]
                if mode == "fence" and free is not None:
                    if is_sd:
                        if any(o["layer"] in free.get(s_, ()) for s_ in swept(o["t"], th)):
                            continue
                    elif o["layer"] not in free.get(section_of(o["t"]), LAYERS):
                        continue
                if mode == "planA":
                    pen = plan_a(net, is_sd, o, th, mc[1])
                    if pen is None:
                        continue
                    cost, tho = cost + pen, th
                    if pen > 0:
                        soft.setdefault((num, k, th), segment_of(o["t"], per_side))
                cand.append((cost, k, th, o["len"] + est, tho))
        best = min((c[0] for c in cand), default=0.0)
        vs = []
        for cost, k, th, ln, tho in cand:
            o = self.opts[(MCU, num)][k]
            if cost <= best + 15.0:
                sup = self.support.setdefault((o["layer"], o["exit"]), {})
                key = round(tho, 3)
                sup[key] = max(sup.get(key, 0.0), 0.0) + 0.0
                self.cands.setdefault(num, []).append((cost - best, o["layer"], o["exit"], key))
            if cost > best + prune:
                continue
            if steps is not None and abs(steps.get((o["layer"], o["exit"]), tho) - tho) > 1e-6:
                continue
            seg_use.setdefault((o["layer"], segment_of(o["t"], per_side), round(tho, 3)), [])
            v = lp.var(cost, name="x")
            X[(num, k, th)] = v
            info[v] = (num, net, k, th, ln)
            reg(o, v)
            seg_use[(o["layer"], segment_of(o["t"], per_side), round(tho, 3))].append(v)
            if is_sd:
                sd_layer.setdefault(o["layer"], []).append(v)
            if is_sd:
                lo_, hi_ = span[(net, o["layer"])]
                if mode == "fence":                    # where on the SDRAM's outline the net can come in at all (5 degree buckets)
                    lo_, hi_ = math.floor(lo_ / 5.0) * 5.0, math.ceil(hi_ / 5.0) * 5.0
                else:
                    lo_, hi_ = SD_ANGLE, SD_ANGLE         # the order among the SDRAM's entries is stage Y's
                slot_x.setdefault((o["layer"], o["exit"]), []).append((v, (th - SD_ANGLE + lo_, th - SD_ANGLE + hi_)))
                lane_len.setdefault(net, []).append((v, ln))
                for s_ in swept(o["t"], th):
                    sweeps.setdefault((o["layer"], s_), []).append(v)
            elif mode == "fence":
                leaves.setdefault((o["layer"], section_of(o["t"])), []).append(v)
            else:
                slot_x.setdefault((o["layer"], o["exit"]), []).append((v, (tho, tho)))
            vs.append(v)
        u = lp.var(UNALLOC, name="u")
        U[num] = u
        lp.row(vs + [u], [1.0] * (len(vs) + 1), 1.0, 1.0)
    # the crystals: straight west on L1 (against a field where the reserve is theirs)
    self.xtal_opts = {}
    Dx, Hx = f.opened("<xtal>")
    mx = f.track_free(TOP, XTAL_W, Dx, Hx)
    for uv, pad in sorted(m_lat.balls.items()):
        if pad["net"] in XTAL:
            e, side = m_lat.edge_point(uv[0], uv[1], DIRS[XTAL_GATE])
            o = {"layer": TOP, "via": None, "l1": [m_lat.xy(*uv), e], "run": [], "nodes": {TOP: m_lat.run(uv[0], uv[1], DIRS[XTAL_GATE])[1:]}, "side": XTAL_GATE,
                 "exit": e, "len": math.dist(m_lat.xy(*uv), e), "t": cw_angle(e, mc)}
            if not sample_ok(f, mx, o["l1"], m_lat.pad_r + 0.17):
                self.log("  ! crystal ball %s: its straight L1 way west is not free" % pad["num"])
            self.xtal_opts[pad["num"]] = o
            v = lp.var(0.0, lb=1.0, name="x")
            X[(pad["num"], -1, GATES[XTAL_GATE])] = v
            info[v] = (pad["num"], pad["net"], -1, GATES[XTAL_GATE], o["len"])
            reg(o, v)
            seg_use.setdefault((TOP, segment_of(o["t"], per_side), GATES[XTAL_GATE]), []).append(v)
            slot_x.setdefault((TOP, o["exit"]), []).append((v, (GATES[XTAL_GATE], GATES[XTAL_GATE])))
    node_rows(lp, node, vias_at)
    # two neighbouring L1 lanes (0.325 mm) cannot both leave the area at a Default-class or crystal width
    # (0.2032 + 0.127 > 0.325): at most one of the two carries such a net
    wide = {}
    for (num, k, th), v in X.items():
        net = self.pads[(MCU, num)]["net"]
        o = self.opts[(MCU, num)][k] if k >= 0 else self.xtal_opts[num]
        if o["layer"] == TOP and net_width(self.geo, net) > 0.15:
            wide.setdefault((o["side"], round(o["exit"][0] if o["side"] in "NS" else o["exit"][1], 3)), []).append(v)
    for side in "NESW":
        cs = sorted(cc for (s2, cc) in wide if s2 == side)
        for a_, b_ in zip(cs, cs[1:]):
            if b_ - a_ < m_lat.h + 0.01:
                vs = wide[(side, a_)] + wide[(side, b_)]
                lp.row(vs, [1.0] * len(vs), -np.inf, 1.0)
    # plane slots: the fixed supply vias are constants, signal vias variables
    FA, FB = {}, {}
    for s in sorted(self.sites[MCU]):
        l3 = self.slots0.l3_net(m_lat.xy(*s))
        if s in fix["pv"]:
            if fix["pv"][s] != GROUND:
                FA[s] = True
            if fix["pv"][s] != l3:
                FB[s] = True
            continue
        sv = sigvia.get(s, [])
        if sv:
            if len(sv) > 1:
                fv = lp.var(0.0, integer=False, name="f")
                lp.row([fv] + sv, [1.0] + [-1.0] * len(sv), 0.0, 0.0)
            else:
                fv = sv[0]
            FA[s] = fv; FB[s] = fv
    n = 0 if os.environ.get('PLAN_NOSLOT') else slot_rows(self, lp, FA, FB)
    # the order, as rivers: on each layer every stretch of the outline (a side cut into per_side pieces) carries
    # nets of one target direction and turn only, and these values rise clockwise round the MCU by at most one
    # full turn. w[layer, stretch, value] picks the value; cumulative sums keep them in order.
    nseg = 4 * per_side
    if mode == "rivers":
        for l in LAYERS:
            vals = sorted({v for (ll, sg, v) in seg_use if ll == l})
            if not vals:
                continue
            W = {}
            for sg in range(nseg):
                mine = sorted(v for (ll, s2, v) in seg_use if ll == l and s2 == sg)
                cand = mine if mine else vals[:1]
                ws = []
                for v in vals:
                    if True:
                        w = lp.var(0.0, name="w")
                        W[(sg, v)] = w
                        ws.append(w)
                lp.row(ws, [1.0] * len(ws), 1.0, 1.0)
                for v in mine:
                    xs = seg_use[(l, sg, v)]
                    for xv in xs:
                        lp.row([xv, W[(sg, v)]], [1.0, -1.0], -np.inf, 0.0)
            for sg in range(nseg - 1):
                for v in vals:                                  # value(sg) <= value(sg + 1): cum_next(v) <= cum_this(v)
                    a = [W[(sg, u)] for u in vals if u <= v and (sg, u) in W]
                    b = [W[(sg + 1, u)] for u in vals if u <= v and (sg + 1, u) in W]
                    if b:
                        lp.row(b + a, [1.0] * len(b) + [-1.0] * len(a), -np.inf, 0.0)
            for v in vals:                                      # value(last) <= value(first) + 360
                a = [W[(0, u)] for u in vals if u <= v and (0, u) in W]
                b = [W[(nseg - 1, u)] for u in vals if u <= v + 360.0 and (nseg - 1, u) in W]
                if a:
                    lp.row(a + b, [1.0] * len(a) + [-1.0] * len(b), -np.inf, 0.0)
        for l, vs in sorted(sd_layer.items()):
            lp.row(vs, [1.0] * len(vs), -np.inf, float(sd_cap))
    nord = 0
    if mode == "planA":                   # the soft point: SDRAM nets on L6, counted per stretch of the outline
        segv = {}
        for key, sg in sorted(soft.items()):
            if key in X:
                if sg not in segv:
                    segv[sg] = lp.var(SOFT_SEG, name="softseg")
                lp.row([X[key], segv[sg]], [1.0, -1.0], -np.inf, 0.0)
    self.fence_vars = {}
    if mode == "fence-mip":
        # no three-layer fence: in every section of the outline the SDRAM's lanes (leaving there or passing on their
        # way round) keep to two layers at most; a ball of another bus leaves the field on a layer that is free
        # of them in its section (it then crosses the bands without a via). A section that needs all three
        # layers costs FENCE_COST and is reported. The crystal strip: no SDRAM lane on L1 along the west side.
        PASS = {}
        for (l, s_), vs in sorted(sweeps.items()):
            pv_ = lp.var(0.0, name="pass")
            PASS[(l, s_)] = pv_
            for v in vs:
                lp.row([v, pv_], [1.0, -1.0], -np.inf, 0.0)
            if l == TOP and s_ // SEC_PER_SIDE == XTAL_SEC_SIDE and SEC_PER_SIDE > 1 and s_ % SEC_PER_SIDE != 0:
                lp.ub[pv_] = 0.0
        for s_ in range(4 * SEC_PER_SIDE):
            ps = [PASS[(l, s_)] for l in LAYERS if (l, s_) in PASS]
            if len(ps) == 3:
                fv = lp.var(FENCE_COST, name="fence")
                self.fence_vars[s_] = fv
                lp.row(ps + [fv], [1.0, 1.0, 1.0, -1.0], -np.inf, 2.0)
        for (l, s_), vs in sorted(leaves.items()):
            if (l, s_) in PASS:
                for v in vs:
                    lp.row([v, PASS[(l, s_)]], [1.0, 1.0], -np.inf, 1.0)
        self.PASS = PASS
    for l in (LAYERS if (order or mode == "fence") else (LAYERS[0], LAYERS[2]) if mode == "planA" else ()):
        sl = sorted((cw_angle(e, mc), e) for (ll, e) in slot_x if ll == l)
        nord += order_rows(lp, [[(v, tv[0], tv[1]) for v, tv in slot_x[(l, e)]] for t, e in sl])
    # byte-lane spreads (the MCU half of the estimate)
    for lane in range(NLANES):
        members = [n_ for n_ in sorted(sd_nets) if (is_data(n_) and int(n_[len(DATA):]) // 8 == lane) or n_ == MASK + "%d" % lane]
        hi_ = lp.var(W_SPREAD, lb=0.0, ub=500.0, integer=False, name="lmax")
        lo_ = lp.var(-W_SPREAD, lb=0.0, ub=500.0, integer=False, name="lmin")
        for n_ in members:
            tl = lane_len.get(n_, [])
            lp.row([hi_] + [v for v, _ in tl], [1.0] + [-ln for _, ln in tl], 0.0, np.inf)
            lp.row([lo_] + [v for v, _ in tl] + [U[sd_nets[n_]]], [1.0] + [-ln for _, ln in tl] + [-500.0], -np.inf, 0.0)
    t1 = time.time()
    res = lp.solve(time_limit)
    self.log("  MCU signals: %d variables, %d rows (%d slot cuts, %d order rows), status %s, objective %s, %.1f s" % (
        len(lp.c), len(lp.lo), n, nord, res.status, None if res.x is None else round(res.fun, 2), time.time() - t1))
    if res.x is None:
        return None
    x = res.x
    self.xsel, self.xlen = {}, {}
    for (num, k, th), v in X.items():
        if x[v] > 0.5:
            self.xsel[num] = (k, th)
            self.xlen[self.pads[(MCU, num)]["net"]] = info[v][4]
    self.x_unalloc = sorted(num for num, u in U.items() if x[u] > 0.5)
    self.x_tho = {num: round(th, 3) for num, (k, th) in self.xsel.items()}
    self.x_obj = res.fun
    self.soft_l6 = sorted((self.pads[(MCU, num)]["net"], num, soft[(num, k, th)]) for (num, k, th), v in X.items() if x[v] > 0.5 and (num, k, th) in soft)
    self.x_status = res.status
    self.fences = sorted(s_ for s_, fv in self.fence_vars.items() if x[fv] > 0.5)
    self.passes = sorted((l, s_) for (l, s_), pv_ in getattr(self, "PASS", {}).items() if x[pv_] > 0.5) if mode == "fence-mip" else []
    # what the answer uses: SDRAM lanes per (layer, section), other balls leaving per (layer, section)
    self.use_sd, self.use_other = {}, {}
    for num, (k, th) in self.xsel.items():
        o = self.opts[(MCU, num)][k] if k >= 0 else self.xtal_opts[num]
        if self.pads[(MCU, num)]["net"].startswith(BUS):
            for s_ in swept(o["t"], th):
                self.use_sd[(o["layer"], s_)] = self.use_sd.get((o["layer"], s_), 0) + 1
        else:
            key = (o["layer"], section_of(o["t"]))
            self.use_other[key] = self.use_other.get(key, 0) + 1
    return self.xsel


def ball_section(self, num):
    return section_of(cw_angle(self.pads[(MCU, num)]["pos"], self.mc))


def solve_mcu_fence(self, time_limit=60.0, trials=int(os.environ.get("PLAN_TRIALS", 8))):
    """Stage X without a three-layer fence, constructively (no big program for the order):
    1. the fan-out with no limit on where the SDRAM's lanes go;
    2. per section of the outline the layers that answer leaves free of SDRAM lanes stay free (at least one: the
       layer with most other balls leaving and fewest SDRAM lanes); west of the crystals L1 is always free;
    3. the fan-out again inside that pattern: an SDRAM lane keeps off the free layers of every section it leaves in
       or passes, another ball leaves on a free layer of its section;
    4. while balls are left without a place: for the section with most of them, each other choice of free layers
       is tried (a fan-out each) and the best kept. What is left is the report: the sections that would need a
       fence, and the balls that lose their way there."""
    log = self.log
    solve_mcu(self, time_limit, free=None)
    nsec = 4 * SEC_PER_SIDE
    free = {}
    subsets = [set(c) for k in (1, 2) for c in itertools.combinations(LAYERS, k)]   # one layer, then two
    for s_ in range(nsec):
        crystal = s_ // SEC_PER_SIDE == XTAL_SEC_SIDE and s_ % SEC_PER_SIDE != 0
        # the SDRAM keeps one or two layers of the section: the choice that keeps most of what the free answer did
        # there (its SDRAM lanes on the kept layers, the other balls' exits on the free ones)
        def keep_score(sd):
            return (sum(self.use_sd.get((l, s_), 0) for l in sd) + sum(self.use_other.get((l, s_), 0) for l in LAYERS if l not in sd), len(sd), sorted(sd))
        sd = max((x_ for x_ in subsets if not (crystal and TOP in x_)), key=keep_score)
        free[s_] = set(LAYERS) - sd
    def run(fr):
        solve_mcu(self, time_limit, free=fr)
        return (len(self.x_unalloc), self.x_obj), dict(self.xsel), dict(self.xlen), list(self.x_unalloc), dict(self.use_sd), dict(self.use_other)
    best = run(free)
    log("  free layers per section: %s -> %d balls without a place" % ({section_name(s_): "".join(sorted(v)) for s_, v in free.items()}, best[0][0]))
    # two whole patterns that put the SDRAM on three layers (the section rule above tends to end on two): the
    # SDRAM's layers per section, east 0-2 (north to south), south 3-5 (east to west), west 6-8 (south to north),
    # north 9-11 (west to east). Only for 3 sections a side.
    if SEC_PER_SIDE == 3:
        seeds = SEEDS                       # bga_block.toml [plan.seeds]
        for name_, pat in seeds.items():
            fr = {s_: set(LAYERS) - {pat[s_][k_:k_ + 2] for k_ in range(0, len(pat[s_]), 2)} for s_ in range(nsec)}
            for s_ in range(nsec):
                if s_ // SEC_PER_SIDE == XTAL_SEC_SIDE and s_ % SEC_PER_SIDE != 0:
                    fr[s_].add(TOP)
            got = run(fr)
            log("  pattern %s -> %d balls without a place" % (name_, got[0][0]))
            if got[0] < best[0]:
                best, free = got, fr
    tried = set()
    n = 0
    while best[3] and n < trials:
        cnt = {}
        for num in best[3]:
            cnt[ball_section(self, num)] = cnt.get(ball_section(self, num), 0) + 1
        todo = [s_ for s_ in sorted(cnt, key=lambda s_: (-cnt[s_], s_)) if s_ not in tried]
        if not todo:
            break
        s_ = todo[0]
        tried.add(s_)
        crystal = s_ // SEC_PER_SIDE == XTAL_SEC_SIDE and s_ % SEC_PER_SIDE != 0
        for alt in subsets:
            if alt == free[s_] or (crystal and TOP not in alt) or n >= trials:
                continue
            fr = dict(free); fr[s_] = alt
            got = run(fr)
            n += 1
            if got[0] < best[0]:
                best, free = got, fr
                log("  %s free on %s -> %d balls without a place" % (section_name(s_), "".join(sorted(alt)), best[0][0]))
    (key, self.xsel, self.xlen, self.x_unalloc, self.use_sd, self.use_other) = best
    self.free = free
    self.x_tho = {num: round(th, 3) for num, (k, th) in self.xsel.items()}
    return self.xsel


def step_functions(self, weight):
    """Per layer the monotone step function lane -> target value (clockwise round the MCU, at most one turn in
    all) that agrees best with `weight` {(layer, exit, value): score}: dynamic programming over the lanes in
    order, once per possible value of the first lane. -> {(layer, exit): value}"""
    mc = self.mc
    out = {}
    for l in LAYERS:
        sl = sorted((cw_angle(e, mc), e) for (ll, e) in self.support if ll == l)
        vals = sorted({v for (ll, e), d in self.support.items() if ll == l for v in d})
        if not sl or not vals:
            continue
        best = None
        for v0 in vals:
            allowed = [v for v in vals if v0 <= v <= v0 + 360.0 + 1e-6]
            f = {v: (weight.get((l, sl[0][1], v), 0.0) if v == v0 else -1e9) for v in allowed}
            back = []
            for t, e in sl[1:]:
                g, bk, run, arg = {}, {}, -1e18, None
                for v in allowed:
                    if f[v] > run:
                        run, arg = f[v], v
                    g[v] = run + weight.get((l, e, v), 0.0)
                    bk[v] = arg
                back.append(bk)
                f = g
            vend = max(allowed, key=lambda v: (f[v], -v))
            if best is None or f[vend] > best[0] + 1e-9:
                seq = [vend]
                for bk in reversed(back):
                    seq.append(bk[seq[-1]])
                best = (f[vend], seq[::-1])
        for (t, e), v in zip(sl, best[1]):
            out[(l, e)] = v
    return out


def solve_mcu_rounds(self, time_limit=45.0, rounds=4):
    """Stage X as relax and fix (deterministic): 1. the program without the order; 2. the step functions that
    agree best with its answer (and, more lightly, with every net's other good options); 3. the program again with
    every lane bound to its step's target; nets left without a place weigh more in the next round's steps."""
    solve_mcu(self, time_limit)
    log = self.log
    best = None
    boost = {}
    chosen = {num: (self.opts[(MCU, num)][k]["layer"] if k >= 0 else TOP, (self.opts[(MCU, num)][k] if k >= 0 else self.xtal_opts[num])["exit"], self.x_tho[num]) for num, (k, th) in self.xsel.items()}
    for rnd in range(rounds):
        weight = {}
        for num, lst in self.cands.items():
            b = boost.get(num, 1.0)
            for gap, layer, e, v in lst:
                weight[(layer, e, v)] = weight.get((layer, e, v), 0.0) + b * 2.0 * max(0.0, 1.0 - gap / 15.0)
        for num, (layer, e, v) in chosen.items():
            weight[(layer, e, v)] = weight.get((layer, e, v), 0.0) + 12.0
        for num, o in self.xtal_opts.items():
            weight[(TOP, o["exit"], GATES[XTAL_GATE])] = 1e6
        steps = step_functions(self, weight)
        solve_mcu(self, time_limit, steps=steps)
        un = list(self.x_unalloc)
        log("  round %d: %d balls without a place%s" % (rnd + 1, len(un), (": " + ", ".join(self.pads[(MCU, n)]["net"] for n in un)) if un else ""))
        key = (len(un), self.x_obj)
        if best is None or key < best[0]:
            best = (key, dict(self.xsel), dict(self.xlen), list(un), dict(steps))
        if not un:
            break
        chosen = {num: (self.opts[(MCU, num)][k]["layer"] if k >= 0 else TOP, (self.opts[(MCU, num)][k] if k >= 0 else self.xtal_opts[num])["exit"], self.x_tho[num]) for num, (k, th) in self.xsel.items()}
        for n in un:
            boost[n] = boost.get(n, 1.0) * 4.0
    (key, self.xsel, self.xlen, self.x_unalloc, self.steps) = best
    return self.xsel


def solve_sdram(self, time_limit=75.0, prune=9.0):
    """Stage Y: which SDRAM ball each net ends on and how it comes in, for the exits of stage X. One program per
    layer, L1 first (its entries are the scarce ones), each with what the layers before it left: on a layer the
    entries follow the exits round the MCU (order_rows), one thing per lattice point and layer, one net per ball."""
    np = self.np
    s_lat, m_lat = self.lat[SDRAM], self.lat[MCU]
    keep = signal_options(self, SDRAM)
    gap_mm = max(0.0, s_lat.area[0] - m_lat.area[2])
    sa = s_lat.area
    ex = {}
    for net, num in sorted(self.sd_nets.items()):
        if num in self.xsel:
            k, th = self.xsel[num]
            o = self.opts[(MCU, num)][k]
            ex[net] = (o["layer"], o["t"], int(round((th - SD_ANGLE) / 360.0)))
    self.ysel, self.y_unalloc, self.ylen = {}, [], {}
    used_ball, used_via, used_node = set(), set(), set()
    for layer in LAYERS:
        lp = LP()
        Y, U = {}, {}
        node, vias_at, ball_use, theta_of, lane_len = {}, {}, {}, {}, {}
        seq = sorted((t, n_) for n_, (ll, t, w) in ex.items() if ll == layer)
        for t, net in seq:
            cand = []
            for bn in self.sd_balls_of(net):
                if bn in used_ball:
                    continue
                for k in keep.get(bn, []):
                    o = self.opts[(SDRAM, bn)][k]
                    if o["layer"] != layer or (o["via"] and (o["via"] in used_via or any((o["via"], l) in used_node for l in LAYERS))):
                        continue
                    if any((p, l) in used_node or p in used_via for l, pts in o["nodes"].items() for p in pts):
                        continue
                    e = o["exit"]
                    b_est = 0.0 if o["side"] == SD_NEAR else (e[0] - sa[0]) if o["side"] in "NS" else (sa[2] - sa[0]) + min(e[1] - sa[1], sa[3] - e[1])
                    ln = o["len"] + b_est + gap_mm / 2
                    cand.append((ln + (VIA_COST if o["via"] else 0.0), bn, k, ln))
            best = min((c_[0] for c_ in cand), default=0.0)
            vs = []
            for cost, bn, k, ln in cand:
                if cost > best + prune:
                    continue
                o = self.opts[(SDRAM, bn)][k]
                v = lp.var(cost, name="y")
                Y[(net, bn, k)] = v
                if o["via"]:
                    vias_at.setdefault(o["via"], []).append(v)
                for l, pts in o["nodes"].items():
                    for p in pts:
                        node.setdefault((p, l), []).append(v)
                ball_use.setdefault(bn, []).append(v)
                th = o["theta"] + 360.0 * ex[net][2]
                theta_of.setdefault(net, []).append((v, th, th))
                lane_len.setdefault(net, []).append((v, ln))
                vs.append(v)
            u = lp.var(UNALLOC, name="u")
            U[net] = u
            lp.row(vs + [u], [1.0] * (len(vs) + 1), 1.0, 1.0)
        if not seq:
            continue
        for bn, vs in sorted(ball_use.items()):
            lp.row(vs, [1.0] * len(vs), -np.inf, 1.0)
        node_rows(lp, node, vias_at)
        nord = order_rows(lp, [theta_of.get(n_, []) for t, n_ in seq])
        for lane in range(NLANES):
            members = [n_ for t, n_ in seq if lane_of(n_) == lane]
            if len(members) < 2:
                continue
            hi_ = lp.var(W_SPREAD, lb=0.0, ub=500.0, integer=False, name="lmax")
            lo_ = lp.var(-W_SPREAD, lb=0.0, ub=500.0, integer=False, name="lmin")
            for n_ in members:
                tl = lane_len.get(n_, [])
                b0 = self.xlen.get(n_, 0.0)
                lp.row([hi_] + [v for v, _ in tl], [1.0] + [-ln for _, ln in tl], b0, np.inf)
                lp.row([lo_] + [v for v, _ in tl] + [U[n_]], [1.0] + [-ln for _, ln in tl] + [-500.0], -np.inf, b0)
        t1 = time.time()
        res = lp.solve(time_limit)
        self.log("  SDRAM entries %s: %d nets, %d variables, %d rows (%d order rows), status %s, objective %s, %.1f s" % (
            layer, len(seq), len(lp.c), len(lp.lo), nord, res.status, None if res.x is None else round(res.fun, 2), time.time() - t1))
        if res.x is None:
            self.y_unalloc += [n_ for t, n_ in seq]
            continue
        x = res.x
        for (net, bn, k), v in Y.items():
            if x[v] > 0.5:
                self.ysel[net] = (bn, k)
                o = self.opts[(SDRAM, bn)][k]
                used_ball.add(bn)
                if o["via"]:
                    used_via.add(o["via"])
                for l, pts in o["nodes"].items():
                    used_node.update((p, l) for p in pts)
        self.y_unalloc += sorted(n_ for n_, u in U.items() if x[u] > 0.5)
    return self.ysel


def sd_balls_of(self, net):
    if net == CLOCK:
        return sorted(n for n, fn in self.sd_fn.items() if fn[0] == "FIX" and fn[1] == CLOCK_R)
    return self.sd_balls_for(net)


Model.sd_balls_of = sd_balls_of
Model.solve_power = solve_power
Model.solve_mcu = lambda self, t=60.0: (solve_mcu_fence(self, min(t, 60.0)) if getattr(self, "order_mode", "fence") == "fence" else solve_mcu(self, t))
Model.solve_sdram = solve_sdram


# ---------------------------------------------------------------- drawing the allocation (the proof)
BONE_W = 0.2


def in_sector(a, lo, hi):
    return (lo <= a <= hi) if lo <= hi else (a >= lo or a <= hi)


def gate_points(field, mc, gate, inset=0.2, step=0.1):
    """Points on the edge of the planning window that belong to a gate (by their angle round the MCU)."""
    lo, hi = GATE_SECTOR[gate]
    out = []
    x0, y0, x1, y1 = field.x0 + inset, field.y0 + inset, field.x1 - inset, field.y1 - inset
    n = int(round((x1 - x0) / step)); m = int(round((y1 - y0) / step))
    for k in range(n + 1):
        for y in (y0, y1):
            p = (r4(x0 + k * step), r4(y))
            if in_sector(cw_angle(p, mc), lo, hi):
                out.append(p)
    for k in range(m + 1):
        for x in (x0, x1):
            p = (r4(x), r4(y0 + k * step))
            if in_sector(cw_angle(p, mc), lo, hi):
                out.append(p)
    return out


def layer_z(geo):
    z, out, k = 0.0, {}, 0
    for name, t in geo["stack"]:
        if name:
            k += 1
            out["L%d" % k] = z + t / 2
        z += t
    return out


def net_width(geo, net):
    """The width a net is drawn with outside the rule areas: its class width (crystals XTAL_W everywhere)."""
    return XTAL_W if net.startswith(XTAL_PREFIXES) else geo["width"].get(net, DEFAULT_W)


def piece_items(G, field, net, pieces, width=None):
    out = []
    width = width or net_width(field.geo, net)
    xtal = net.startswith(XTAL_PREFIXES)
    for pc in pieces:
        if pc[0] == "via":
            d, h = field.via_size(pc[1])
            out.append(G.Item(net, G.COPPER, "round", a=tuple(pc[1]), r=d / 2, hole=h / 2, tag="via"))
        else:
            w = pc[2] if len(pc) > 2 else None
            for p, q in zip(pc[1], pc[1][1:]):
                inside = field.is_area(p) and field.is_area(q)
                out.append(G.Item(net, (pc[0],), "seg", a=tuple(p), b=tuple(q), r=(w or (field.w_area if (inside and not xtal) else width)) / 2, tag="track"))
    return out


def add_items(field, items):
    for it in items:
        field.items.append(it)
        field._stamp(it, field.D, field.H)
        b = it.box
        for cx in range(int(math.floor(b[0] - 0.6)), int(math.floor(b[2] + 0.6)) + 1):
            for cy in range(int(math.floor(b[1] - 0.6)), int(math.floor(b[3] + 0.6)) + 1):
                field.cells.setdefault((cx, cy), []).append(len(field.items) - 1)


def mcu_pieces(lat, o):
    if o["via"]:
        return [(TOP, list(o["l1"])), ("via", lat.xy(*o["via"])), (o["layer"], list(o["run"]))]
    return [(TOP, list(o["l1"]))]


def sd_pieces(lat, o):
    if o["via"]:
        return [(o["layer"], list(o["run"])[::-1]), ("via", lat.xy(*o["via"])), (TOP, list(o["l1"])[::-1])]
    return [(TOP, list(o["l1"])[::-1])]


def join(a, b):
    """Two piece lists where a ends and b starts on the same layer at the same point -> one list."""
    if a and b and a[-1][0] != "via" and b[0][0] == a[-1][0]:
        return a[:-1] + [(a[-1][0], list(a[-1][1]) + list(b[0][1])[1:])] + b[1:]
    return a + b


def draw(self, zones=None):
    """Draw every allocated net. -> (nets {net: record}, power pieces, failures). zones: {net: (need mm)} byte-lane
    nets that reserve a tuning zone beside their longest straight outside the rule areas."""
    np, G = self.np, self.G
    from skimage.graph import MCP_Geometric
    t0 = time.time()
    geo = self.geo
    m_lat, s_lat, mc = self.lat[MCU], self.lat[SDRAM], self.mc
    # a fresh field: the state, the capacitors, the supply vias, every lattice part
    reserve = [G.Item("<xtal>", (TOP,), "poly", poly=[(XTAL_BOX[0], XTAL_BOX[1]), (XTAL_BOX[2], XTAL_BOX[1]), (XTAL_BOX[2], XTAL_BOX[3]), (XTAL_BOX[0], XTAL_BOX[3])], tag="reserve")]
    f = G.Field(geo, WINDOW, items=G.scene_items(geo, extra=reserve))
    power = {}                             # net -> [chain of pieces]
    for ref in (MCU, SDRAM):
        lat, fix = self.lat[ref], self.fix[ref]
        new = []
        for c in fix["caps"]:
            for k, r in enumerate(c["rects"]):
                new.append(G.Item(c["nets"][k], (BOTTOM,), "poly", poly=[(r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])], a=c["pads"][k], tag="%s.%d" % (c["ref"], k + 1)))
        done = set()
        for num, s in sorted(fix["pa"].items()):
            net = self.pads[(ref, num)]["net"]
            sx = lat.xy(*s)
            chain = [(TOP, ["%s.%s" % (ref, num), sx], BONE_W)]
            if s not in done:
                chain.append(("via", sx))
                done.add(s)
            power.setdefault(net, []).append(chain)
            new += piece_items(G, f, net, [(TOP, [lat.xy(*lat.uv(self.pads[(ref, num)]["pos"])), sx], BONE_W)] + ([("via", sx)] if len(chain) > 1 else []))
        for c in fix["caps"]:                               # a part's own via: a stub inside its pad, then the via
            for k, s in enumerate((c["s"], c["g"])):
                if s in fix["own"] and s not in done:
                    done.add(s)
                    power.setdefault(c["nets"][k], []).append([(BOTTOM, ["%s.%d" % (c["ref"], k + 1), lat.xy(*s)], BONE_W), ("via", lat.xy(*s))])
                    new += piece_items(G, f, c["nets"][k], [("via", lat.xy(*s))])
        add_items(f, new)
    nets = {}
    r201 = {k: self.pads.get((CLOCK_RES, k)) for k in ("1", "2")}
    for num, (k, th) in sorted(self.xsel.items()):
        net = self.pads[(MCU, num)]["net"]
        o = self.opts[(MCU, num)][k] if k >= 0 else self.xtal_opts[num]
        rec = {"net": net, "ball": num, "layer": o["layer"], "side": o["side"], "exit": tuple(o["exit"]), "t": o["t"], "theta": th,
               "via": m_lat.xy(*o["via"]) if o["via"] else None, "mcu": mcu_pieces(m_lat, o), "sd": None, "sd_ball": None, "outside": None, "fail": None}
        if net.startswith(BUS):
            rec["target"] = "SDRAM"
            if net in self.ysel:
                bn, k2 = self.ysel[net]
                o2 = self.opts[(SDRAM, bn)][k2]
                rec.update(sd=sd_pieces(s_lat, o2), sd_ball=bn, entry=tuple(o2["exit"]), entry_side=o2["side"], sd_via=s_lat.xy(*o2["via"]) if o2["via"] else None)
            else:
                rec["fail"] = "no SDRAM entry allocated"
        else:
            rec["target"] = self.gate_of(net)
        nets[net] = rec
    for net, rec in sorted(nets.items()):
        nm = CLOCK_R if net == CLOCK else net
        add_items(f, piece_items(G, f, net, rec["mcu"]) + (piece_items(G, f, nm, rec["sd"]) if rec["sd"] else []))
    interior = np.zeros((f.ny, f.nx), bool)
    X, Y = np.meshgrid(f.xs, f.ys)
    for a in f.areas:
        interior |= (X > a[0] + 1e-6) & (X < a[2] - 1e-6) & (Y > a[1] + 1e-6) & (Y < a[3] - 1e-6)
    del X, Y
    gates = {g: gate_points(f, mc, g) for g in GATE_SECTOR}
    self.zone_boxes = {}
    fails = []
    hop = getattr(self, "order_mode", "") == "fence"       # the other buses change layer as they need (drawn after the SDRAM)
    later = []
    def nest_key(rec):
        """Nested rivers: nets that go straight out first; of those going clockwise round the MCU the one nearest
        its target first (it takes the inside lane, the ones from farther back pass outside it); the same,
        mirrored, anticlockwise."""
        d = rec["theta"] - rec["t"]
        if abs(d) <= 30.0:
            return (0, rec["t"])
        return (1, -rec["t"]) if d > 0 else (2, rec["t"])
    for layer in LAYERS:
        order = sorted((nest_key(rec), net) for net, rec in nets.items() if rec["layer"] == layer and not rec["fail"])
        for t, net in order:
            rec = nets[net]
            if hop and rec["target"] != "SDRAM" and net not in XTAL:
                later.append((t, net))
                continue
            own = CLOCK_R if net == CLOCK else net
            start = rec["exit"]
            if net == CLOCK:
                # the series resistor: the MCU's part ends on its pad 1 (R201.1), the SDRAM's part starts on pad 2
                rec["mcu"] = join(rec["mcu"], [(TOP, [start, tuple(r201["1"]["pos"])])])
                add_items(f, piece_items(G, f, net, [(TOP, [start, tuple(r201["1"]["pos"])])]))
                start = tuple(r201["2"]["pos"])
            if rec["target"] == "SDRAM":
                ends = [rec["entry"]]
            elif net in XTAL:
                ends = [tuple(p["pos"]) for p in geo["pads"] if p["net"] == net and p["ref"] != MCU and f.inside(p["pos"], 0.2) and (p["layers"] is None or TOP in p["layers"])]
            else:
                ends = gates[rec["target"]]
            extra = [it for it in f.items if it.net == "<xtal>"] if net in XTAL else []
            D, H = f.opened(own, extra_own=extra)
            if net == CLOCK:
                D2, H2 = f.opened(net)
                for l in LAYERS:
                    D[l] = np.maximum(D[l], D2[l])
                H = np.maximum(H, H2)
            mask = f.track_free(layer, net_width(geo, own), D, H) & ~interior
            xs = [start[0]] + [e[0] for e in ends]; ys = [start[1]] + [e[1] for e in ends]
            j0, j1, i0, i1 = f._win((min(xs), min(ys), max(xs), max(ys)), 9.0)
            sub = np.where(mask[j0:j1, i0:i1], 1.0, np.inf)
            si, sj = f.ij(start)
            E = [(f.ij(e)[1] - j0, f.ij(e)[0] - i0) for e in ends]
            E = [e for e in E if 0 <= e[0] < sub.shape[0] and 0 <= e[1] < sub.shape[1] and np.isfinite(sub[e])]
            S0 = (sj - j0, si - i0)
            path = None
            if E and np.isfinite(sub[S0]):
                mcp = MCP_Geometric(sub, fully_connected=True)
                cost, _ = mcp.find_costs([S0], E, find_all_ends=False)
                best = min(E, key=lambda e: cost[e])
                if np.isfinite(cost[best]):
                    path = [f.pt(i + i0, j + j0) for j, i in mcp.traceback(best)]
            if path is None:
                rec["fail"] = "no way on %s from %s to %s" % (layer, start, "its SDRAM entry %s" % (rec.get("entry"),) if rec["target"] == "SDRAM" else "gate " + rec["target"])
                fails.append(net)
                continue
            pts = G.tidy(f, path, mask)
            rec["outside"] = [(layer, pts)]
            new = piece_items(G, f, own, rec["outside"])
            # a reserved tuning zone beside the longest straight of a byte-lane net that will need length
            if zones and zones.get(net, 0.0) > 0.0:
                zb = tuning_zone(self, f, D, layer, pts, zones[net])
                if zb:
                    self.zone_boxes[net] = zb
                    b = zb["box"]
                    new.append(G.Item(own, (layer,), "poly", poly=[(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])], tag="tuning zone"))
            add_items(f, new)
    if later:
        C = _optional("bga_check")
        from scipy.spatial import cKDTree
        sites = []
        x_ = math.ceil(f.x0 + 0.5)
        while x_ <= f.x1 - 0.5:
            y_ = math.ceil(f.y0 + 0.5)
            while y_ <= f.y1 - 0.5:
                if not f.is_area((x_, y_), -0.3):
                    sites.append((r4(x_), r4(y_)))
                y_ += 0.5
            x_ += 0.5
        allv = [(it.net, it.a, it.r * 2) for it in f.items if it.tag == "via"]
        slots = G.Slots(geo, allv)
        S = C.Sites(geo, f, sites, slots)
        maze = G.Maze(f, LAYERS)
        for t, net in sorted((nest_key(nets[n_]), n_) for t_, n_ in later):
            rec = nets[net]
            D, H = f.opened(net)
            w = net_width(geo, net)
            masks = {l: f.track_free(l, w, D, H) & ~interior for l in LAYERS}
            sel = S.within(S.legal(D, H), self.slot_max)
            vol = maze.volume(masks, S, sel)
            ends = [(l, p) for p in gates[rec["target"]] for l in LAYERS]
            got = maze.route(vol, [(rec["layer"], rec["exit"])], ends)
            if not got:
                rec["fail"] = "no way from %s (%s) to gate %s on any layer" % (rec["exit"], rec["layer"], rec["target"])
                fails.append(net)
                continue
            pcs, length, nv = G.path_pieces(got[1])
            pcs = [pc if pc[0] == "via" else (pc[0], G.tidy(f, pc[1], masks[pc[0]])) for pc in pcs]
            rec["outside"] = pcs
            add_items(f, piece_items(G, f, net, pcs))
            for pc in pcs:
                if pc[0] == "via":
                    slots.add(net, pc[1], f.via_size(pc[1])[0])
            S.chain.clear()
            S.tree = cKDTree(np.array([v_[1] for v_ in slots.vias]))
    self.draw_field = f
    self.log("  drawn in %.1f s: %d nets, %d not drawn" % (time.time() - t0, len(nets), len(fails) + sum(1 for r in nets.values() if r["fail"] and r["net"] not in fails)))
    return nets, power


TUNE_PITCH, TUNE_AMP, TUNE_AMP_MAX, TUNE_CLR, TUNE_KEEP = 0.3, 0.5, 2.0, 0.19, 0.7


def tune_capacity(length, amp, pitch=TUNE_PITCH):
    """RTE-2: n humps of height amp on a straight of `length` (0.7 mm kept straight at both ends) add
    n (2 amp - 0.858 pitch) and take 2 pitch n of the straight."""
    n = int(math.floor((length - 2 * TUNE_KEEP) / (2 * pitch) + 1e-9))
    return max(0, n), max(0, n) * max(0.0, 2 * amp - 0.858 * pitch)


def tuning_zone(self, f, D, layer, pts, need):
    """The box beside the longest axis-parallel straight of `pts` (outside the rule areas) that holds serpentine
    humps for `need` mm: side and height by what is free in the field now. -> dict(box, layer, amp, humps, capacity)."""
    np = self.np
    best = None
    for a, b in zip(pts, pts[1:]):
        if abs(a[0] - b[0]) > 1e-9 and abs(a[1] - b[1]) > 1e-9:
            continue
        L = math.dist(a, b)
        if L < 2 * TUNE_KEEP + 2 * TUNE_PITCH or f.is_area(a, -0.2) or f.is_area(b, -0.2):
            continue
        horiz = abs(a[1] - b[1]) < 1e-9
        for sgn in (1, -1):
            # free depth on this side: the largest h such that the strip of height h along the straight is clear
            lo, hi = 0.0, TUNE_AMP_MAX + TUNE_CLR + 0.06
            depth = 0.0
            h = 0.3
            while h <= hi + 1e-9:
                if horiz:
                    box = (min(a[0], b[0]) + TUNE_KEEP, a[1] + (0.12 if sgn > 0 else -h), max(a[0], b[0]) - TUNE_KEEP, a[1] + (h if sgn > 0 else -0.12))
                else:
                    box = (a[0] + (0.12 if sgn > 0 else -h), min(a[1], b[1]) + TUNE_KEEP, a[0] + (h if sgn > 0 else -0.12), max(a[1], b[1]) - TUNE_KEEP)
                j0, j1, i0, i1 = f._win(box, 0.0)
                if j1 <= j0 or i1 <= i0 or (D[layer][j0:j1, i0:i1] < 0.02).any() or any(f.is_area((x, y)) for x in (box[0], box[2]) for y in (box[1], box[3])):
                    break
                depth = h
                h += 0.05
            amp = min(TUNE_AMP_MAX, depth - TUNE_CLR - 0.05)
            if amp < TUNE_AMP:
                continue
            n, _ = tune_capacity(L, amp)
            if n < 1:
                continue
            # the smallest height that gives the need, else all there is
            want = min(amp, max(TUNE_AMP, (need / n + 0.858 * TUNE_PITCH) / 2))
            cap = n * (2 * want - 0.858 * TUNE_PITCH)
            key = (min(cap, need), -want)
            if best is None or key > best[0]:
                hh = want + TUNE_CLR + 0.05
                if horiz:
                    box = (min(a[0], b[0]) + TUNE_KEEP, a[1] + (0.12 if sgn > 0 else -hh), max(a[0], b[0]) - TUNE_KEEP, a[1] + (hh if sgn > 0 else -0.12))
                else:
                    box = (a[0] + (0.12 if sgn > 0 else -hh), min(a[1], b[1]) + TUNE_KEEP, a[0] + (hh if sgn > 0 else -0.12), max(a[1], b[1]) - TUNE_KEEP)
                best = (key, dict(layer=layer, box=[r4(v) for v in box], amp=round(want, 3), humps=n, capacity=round(cap, 2), straight=[list(a), list(b)]))
    return best[1] if best else None


Model.draw = draw


# ---------------------------------------------------------------- the plan as a table
def plen(pieces):
    return sum(math.dist(a, b) for pc in pieces if pc[0] != "via" for a, b in zip(pc[1], pc[1][1:]))


def assemble(self, nets, power):
    """Per-net pieces for busroute (pads by name), lengths with via heights, via counts."""
    z = layer_z(self.geo)
    out = {}
    for net, rec in sorted(nets.items()):
        parts = join(rec["mcu"], rec["outside"] or [])
        ok = rec["fail"] is None and (rec["outside"] is not None)
        if rec["target"] == "SDRAM" and rec["sd"] and ok:
            if net == CLOCK:
                a = [list(p) for p in rec["mcu"]]
                b = [list(p) for p in join(rec["outside"], rec["sd"])]
                a[0][1] = ["%s.%s" % (MCU, rec["ball"])] + list(a[0][1][1:]); a[-1][1] = list(a[-1][1][:-1]) + [CLOCK_RES + ".1"]
                b[0][1] = [CLOCK_RES + ".2"] + list(b[0][1][1:]); b[-1][1] = list(b[-1][1][:-1]) + ["%s.%s" % (SDRAM, rec["sd_ball"])]
                rec["routes"] = {CLOCK: a, CLOCK_R: b}
                parts = rec["mcu"] + join(rec["outside"], rec["sd"])
            else:
                parts = join(parts, rec["sd"])
                a = [list(p) for p in parts]
                a[0][1] = ["%s.%s" % (MCU, rec["ball"])] + list(a[0][1][1:]); a[-1][1] = list(a[-1][1][:-1]) + ["%s.%s" % (SDRAM, rec["sd_ball"])]
                rec["routes"] = {net: a}
        else:
            a = [list(p) for p in parts]
            a[0][1] = ["%s.%s" % (MCU, rec["ball"])] + list(a[0][1][1:])
            if net in XTAL and ok:
                end = a[-1][1][-1]
                pad = next((p for p in self.geo["pads"] if p["net"] == net and math.dist(p["pos"], end) < 1e-6), None)
                if pad:
                    a[-1][1] = list(a[-1][1][:-1]) + ["%s.%s" % (pad["ref"], pad["num"])]
            rec["routes"] = {net: a}
        vias = [pc[1] for pc in parts if pc[0] == "via"]
        lays = [pc[0] for pc in parts if pc[0] != "via"]
        vh = 0.0
        k = 0
        for i, pc in enumerate(parts):
            if pc[0] == "via":
                before = next((q[0] for q in reversed(parts[:i]) if q[0] != "via"), TOP)
                after = next((q[0] for q in parts[i + 1:] if q[0] != "via"), TOP)
                vh += abs(z[before] - z[after])
        rec["length"] = round(plen(parts) + vh, 3)
        rec["vias"] = len(vias)
        rec["drawn"] = ok and not (rec["target"] == "SDRAM" and not rec["sd"])
        out[net] = rec
    return out


def lane_table(nets):
    lanes = {}
    for net, rec in nets.items():
        if is_data(net):
            lanes.setdefault(int(net[len(DATA):]) // 8, []).append(net)
        elif net.startswith(MASK):
            lanes.setdefault(int(net[len(MASK):]), []).append(net)
    out = {}
    for lane, members in sorted(lanes.items()):
        drawn = [n for n in members if nets[n]["drawn"]]
        if not drawn:
            out[lane] = dict(members=sorted(members), longest=None, spread=None, target=None, need={})
            continue
        L = {n: nets[n]["length"] for n in drawn}
        longest = max(L.values())
        target = longest - LANE_WINDOW + LANE_MARGIN
        out[lane] = dict(members=sorted(members), longest=round(longest, 2), shortest=round(min(L.values()), 2), spread=round(longest - min(L.values()), 2),
                         target=round(target, 2), need={n: round(max(0.0, target - v), 2) for n, v in sorted(L.items()) if target - v > 0})
    return out


def run_plan(geo, sd_pos, sd_rot, slot_max=None, lane_map=None, name=None, out_dir=None, log=print, do_draw=True, tx=150.0, order="fence"):
    t0 = time.time()
    m = Model(geo, sd_pos, sd_rot, slot_max, lane_map, log)
    m.order_mode = order
    m.build_options()
    for ref in (MCU, SDRAM):
        if m.solve_power(ref, 60.0) is None:
            raise SystemExit("no supply via plan for %s" % ref)
    if m.solve_mcu(tx) is None:
        raise SystemExit("no fan-out found")
    m.solve_sdram()
    t_alloc = time.time() - t0
    nets, power = m.draw()
    nets = assemble(m, nets, power)
    lanes = lane_table(nets)
    zones = {}
    for lane, row in lanes.items():
        zones.update(row["need"])
    if zones and do_draw:
        nets2, power = m.draw(zones)
        nets2 = assemble(m, nets2, power)
        if sum(1 for r in nets2.values() if r["drawn"]) >= sum(1 for r in nets.values() if r["drawn"]):
            nets = nets2
            lanes = lane_table(nets)
        else:
            log("  the second drawing (with tuning zones) loses nets: the first is kept, no zone is reserved")
            m.zone_boxes = {}
    plan = plan_dict(m, nets, power, lanes, name, t_alloc, time.time() - t0)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        json.dump(plan, open(os.path.join(out_dir, "plan.json"), "w", encoding="utf-8"), indent=0)
        open(os.path.join(out_dir, "plan.txt"), "w", encoding="utf-8", newline="\n").write(plan_text(plan) + "\n")
    return plan, m


def plan_dict(m, nets, power, lanes, name, t_alloc, t_all):
    G, f = m.G, m.field
    geo = m.geo
    mlat, slat = m.lat[MCU], m.lat[SDRAM]
    supply, caps, vias_all = {}, [], []
    for ref in (MCU, SDRAM):
        lat, fix = m.lat[ref], m.fix[ref]
        users = {}
        for num, s in fix["pa"].items():
            users.setdefault(s, []).append(num)
        supply[ref] = {num: {"net": m.pads[(ref, num)]["net"], "site": list(lat.xy(*s)), "shared_with": sorted(n for n in users[s] if n != num)} for num, s in sorted(fix["pa"].items())}
        for s, net in sorted(fix["pv"].items()):
            vias_all.append((net, lat.xy(*s), f.via_in[0]))
        sb = [(num, lat.xy(*uv), pad["net"]) for uv, pad in sorted(lat.balls.items()) for num in [pad["num"]] if pad["net"] in POWER and pad["net"] != GROUND]
        for c in fix["caps"]:
            serves = sorted((round(math.dist(c["pads"][0], bxy), 2), num) for num, bxy, bnet in sb if bnet == c["nets"][0] and math.dist(c["pads"][0], bxy) <= CAP_REACH + 1e-6)
            caps.append({"ref": c["ref"], "package": ref, "kind": c["kind"], "size": c["size"], "pos": list(c["pos"]), "rot": c["rot"], "nets": list(c["nets"]),
                         "pads": [list(p) for p in c["pads"]], "on_sites": [list(lat.xy(*c["s"])), list(lat.xy(*c["g"]))],
                         "own_vias": [list(lat.xy(*q)) for q in (c["s"], c["g"]) if q in fix["own"]],
                         "covers_sites": [list(lat.xy(*q)) for q in c["bv"]], "serves": [[n, d] for d, n in serves]})
    sig = {}
    for net, r in sorted(nets.items()):
        way = "direct" if abs(r["theta"] - r["t"]) <= 100 else ("clockwise" if r["theta"] > r["t"] else "anticlockwise")
        d = {"ball": r["ball"], "layer": r["layer"], "side": r["side"], "exit": list(r["exit"]), "lane": r["exit"][1] if r["side"] in "EW" else r["exit"][0],
             "via": list(r["via"]) if r["via"] else None, "round": way, "target": r["target"], "vias": r["vias"], "length": r["length"],
             "drawn": bool(r["drawn"]), "fail": r["fail"], "routes": r["routes"]}
        if r["target"] == "SDRAM":
            d.update(sd_ball=r.get("sd_ball"), entry=list(r["entry"]) if r.get("entry") else None, entry_side=r.get("entry_side"),
                     sd_via=list(r["sd_via"]) if r.get("sd_via") else None)
            if r.get("sd_ball"):
                fn = m.sd_fn[r["sd_ball"]]
                d["sd_pin"] = fn[2].replace(BUS, "") if fn[0] == "FIX" else ("DQ" + fn[2][len(DATA):] if fn[0] == "D" else "DQM" + fn[2][len(MASK):])
        for pc in next(iter(r["routes"].values())) if False else []:
            pass
        sig[net] = d
        for pcs in r["routes"].values():
            for pc in pcs:
                if pc[0] == "via":
                    vias_all.append((net, tuple(pc[1]), f.via_size(pc[1])[0]))
    # rivers: per layer and MCU side, the nets in the order of their lanes
    rivers = {}
    for net, d in sig.items():
        rivers.setdefault(d["layer"], {}).setdefault(d["side"], []).append((d["lane"], net, d["target"]))
    rivers = {l: {s: [[n, round(c, 3), t] for c, n, t in sorted(v)] for s, v in sorted(sides.items())} for l, sides in sorted(rivers.items())}
    # plane slots of everything planned plus what the state already holds
    S = G.Slots(geo, [(n, p, d) for n, p, d, h in geo["vias"]] + vias_all)
    chains = S.longest((WINDOW[0], WINDOW[1], WINDOW[2], WINDOW[3]))
    slots = {"limit": m.slot_max, "longest": chains[0][0] if chains else 0.0,
             "over_limit": [[c[0], c[1], len(c[2])] for c in chains if c[0] > m.slot_max + 1e-6],
             "over_%g" % SLOT_REPORT: [[c[0], c[1], len(c[2])] for c in chains if c[0] > SLOT_REPORT + 1e-6],
             "top": [[c[0], c[1], [list(p) for n, p in c[2]]] for c in chains[:5]]}
    # ground return: distance from each signal via to the nearest ground via
    gnd = [p for n, p, d in vias_all if n == GROUND] + [tuple(p) for n, p, d, h in geo["vias"] if n == GROUND]
    far = []
    for n, p, d in vias_all:
        if n not in POWER:
            dd = min((math.dist(p, q) for q in gnd), default=99.0)
            if dd > GROUND_FAR:
                far.append([n, list(p), round(dd, 2)])
    # estimates and rules
    est = estimates(m, sig, lanes)
    zones = {n: z for n, z in sorted(getattr(m, "zone_boxes", {}).items())}
    tuning = {}
    for lane, row in lanes.items():
        need = row["need"]
        capa = {n: zones[n]["capacity"] for n in need if n in zones}
        short = {n: round(v - capa.get(n, 0.0), 2) for n, v in need.items() if v - capa.get(n, 0.0) > 0.01}
        tuning[str(lane)] = dict(row, need_total=round(sum(need.values()), 2), reserved=round(sum(min(capa.get(n, 0.0), need[n]) for n in need), 2),
                                 shortfall=short, zones={n: zones[n] for n in need if n in zones})
    unmet = []
    for ref in (MCU, SDRAM):
        n_power = sum(1 for p in m.lat[ref].balls.values() if p["net"] in POWER)
        if len(m.fix[ref]["pa"]) < n_power:
            unmet.append("%s: %d supply / ground balls without a via" % (ref, n_power - len(m.fix[ref]["pa"])))
        for num in m.fix[ref].get("uncovered", []):
            unmet.append("%s.%s: no 100 nF within %.1f mm" % (ref, num, CAP_REACH))
    for num in m.x_unalloc:
        unmet.append("%s (%s): no fan-out allocated" % (m.pads[(MCU, num)]["net"], num))
    for net, d in sig.items():
        if d["fail"]:
            unmet.append("%s (%s): %s" % (net, d["ball"], d["fail"]))
    unmet += est["violations"]
    if slots["over_limit"]:
        unmet.append("plane slots over %.1f mm: %s" % (m.slot_max, slots["over_limit"]))
    for lane, t in tuning.items():
        for n, v in t["shortfall"].items():
            unmet.append("lane %s %s: tuning short by %.2f mm" % (lane, n, v))
    sections = []
    if getattr(m, "free", None):
        for s_ in range(4 * SEC_PER_SIDE):
            lost = sorted("%s (%s)" % (m.pads[(MCU, num)]["net"], num) for num in m.x_unalloc if ball_section(m, num) == s_)
            sections.append({"section": section_name(s_), "free": sorted(m.free[s_]),
                             "sdram_lanes": {l: m.use_sd.get((l, s_), 0) for l in LAYERS}, "others_leaving": {l: m.use_other.get((l, s_), 0) for l in LAYERS},
                             "without_place": lost})
    n_sig = len(m.xsel) + len(m.x_unalloc)
    drawn = sum(1 for d in sig.values() if d["drawn"])
    score = {"signal_balls": n_sig, "allocated": len(m.xsel), "drawn": drawn,
             "sdram_nets": sum(1 for d in sig.values() if d["target"] == "SDRAM"), "sdram_drawn": sum(1 for d in sig.values() if d["target"] == "SDRAM" and d["drawn"]),
             "supply_balls": sum(len(v) for v in supply.values()), "supply_vias": sum(len(m.fix[r]["pv"]) for r in (MCU, SDRAM)),
             "shared": sum(1 for v in supply.values() for b in v.values() if b["shared_with"]),
             "slot_longest": slots["longest"], "sdram_longest": est["sdram_longest"], "lane_spreads": [tuning[k]["spread"] for k in sorted(tuning)],
             "tuning_need": round(sum(t["need_total"] for t in tuning.values()), 1), "tuning_reserved": round(sum(t["reserved"] for t in tuning.values()), 1),
             "vias_signal": sum(d["vias"] for d in sig.values()), "length_total": round(sum(d["length"] for d in sig.values()), 1),
             "unmet": len(unmet), "seconds_allocation": round(t_alloc, 1), "seconds_total": round(t_all, 1)}
    return {"name": name, "geo": geo.get("board"), "sdram": {"pos": list(m.sd_pos), "rot": m.sd_rot, "area": list(slat.area)}, "slot_max": m.slot_max,
            "lane_map": list(m.lane_map), "window": list(WINDOW), "supply": supply, "caps": caps, "signals": sig, "rivers": rivers,
            "gates": {g: {"angle": GATES[g], "sector": list(GATE_SECTOR[g])} for g in GATES}, "tuning": tuning, "estimates": est, "slots": slots,
            "ground_return_far": far, "power_routes": power, "sections": sections, "unmet": unmet, "score": score}


def estimates(m, sig, lanes):
    """Lengths against SPEC 9. Non-SDRAM nets end at their gate: the rest is the straight (octile) way from
    there to the far pad, so these are lower bounds for the finished board."""
    geo = m.geo
    def total(net):
        d = sig.get(net)
        if not d or not d["drawn"]:
            return None
        end = None
        for pc in reversed(d["routes"][net]):
            if pc[0] != "via":
                end = pc[1][-1]
                break
        if isinstance(end, str):
            return d["length"]
        dest = [p for p in geo["pads"] if p["net"] == net and p["ref"] != MCU]
        if not dest:
            return d["length"]
        th = GATES[d["target"]] if d["target"] in GATES else 0.0
        far = min(dest, key=lambda p: min(abs(cw_angle(p["pos"], m.mc) - th), 360 - abs(cw_angle(p["pos"], m.mc) - th)))
        dx, dy = abs(far["pos"][0] - end[0]), abs(far["pos"][1] - end[1])
        return round(d["length"] + max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy), 2)
    viol = []
    sp = SPEC
    sd = {n: d["length"] for n, d in sig.items() if d["target"] == "SDRAM" and d["drawn"]}
    for n, v in sorted(sd.items()):
        if v > sp["sdram_max"]:
            viol.append("%s: %.1f mm, over %g" % (n, v, sp["sdram_max"]))
    addr = {n: v for n, v in sd.items() if not is_data(n) and not n.startswith(MASK)}
    out = {"sdram_longest": round(max(sd.values()), 2) if sd else None, "sdram_longest_net": max(sd, key=sd.get) if sd else None,
           "sdram_lengths": {n: v for n, v in sorted(sd.items())},
           "address_min_max": [round(min(addr.values()), 2), round(max(addr.values()), 2)] if addr else None,
           "sdram_vias_3": sorted(n for n, d in sig.items() if d["target"] == "SDRAM" and d["vias"] >= 3),
           "vias_4_or_more": sorted([n, d["vias"]] for n, d in sig.items() if d["vias"] >= 4)}
    T = {n: total(n) for n in sig if sig[n]["target"] != "SDRAM"}
    out["to_destination"] = {n: v for n, v in sorted(T.items()) if v is not None}
    c = sp["ltdc"]                         # a parallel bus: spread and longest
    lt = {n: v for n, v in T.items() if n.startswith(c["prefix"]) and geo["classes"].get(n) == c["class"] and v is not None}
    if lt:
        out["ltdc"] = {"longest": max(lt.values()), "shortest": min(lt.values()), "spread": round(max(lt.values()) - min(lt.values()), 2), "nets": len(lt)}
        if out["ltdc"]["spread"] > c["spread"]:
            viol.append("%s: longest - shortest %.1f mm, over %g (%s %.1f, %s %.1f)" % (c["class"], out["ltdc"]["spread"], c["spread"], max(lt, key=lt.get), max(lt.values()), min(lt, key=lt.get), min(lt.values())))
        viol += ["%s: %.1f mm, over %g" % (n, v, c["max"]) for n, v in sorted(lt.items()) if v > c["max"]]
    c = sp["qspi"]                         # a clocked bus: longest, data lines (name contains `data`) within +-window of the clock
    q = {n: v for n, v in T.items() if n.startswith(c["prefix"]) and v is not None}
    if c["clock"] in q:
        out["qspi"] = q
        for n, v in sorted(q.items()):
            if v > c["max"]:
                viol.append("%s: %.1f mm, over %g" % (n, v, c["max"]))
            if c["data"] in n and abs(v - q[c["clock"]]) > c["window"]:
                viol.append("%s: %+.1f mm to %s, window +-%g" % (n, v - q[c["clock"]], c["clock"][len(c["prefix"]):], c["window"]))
    c = sp["sdmmc"]                        # a clocked bus: every other line within [lo, hi] of the clock
    s = {n: v for n, v in T.items() if n.startswith(c["prefix"]) and v is not None}
    if c["clock"] in s:
        out["sdmmc"] = s
        lo, hi = c["window"]
        for n, v in sorted(s.items()):
            if n != c["clock"] and not (lo <= v - s[c["clock"]] <= hi):
                viol.append("%s: %+.1f mm to %s, window %g..+%g" % (n, v - s[c["clock"]], c["clock"][len(c["prefix"]):], lo, hi))
    c = sp["rmii"]                         # a reference clock: longest, and the lines it samples not shorter
    r = {n: v for n, v in T.items() if n.startswith(c["prefix"]) and v is not None}
    if c["clock"] in r:
        out["rmii"] = r
        if r[c["clock"]] > c["max"]:
            viol.append("%s: %.1f mm, over %g" % (c["clock"], r[c["clock"]], c["max"]))
        for n in c["not_shorter"]:
            if n in r and r[n] < r[c["clock"]]:
                viol.append("%s: %.1f mm shorter than %s" % (n, r[c["clock"]] - r[n], c["clock"][len(c["prefix"]):]))
    out["violations"] = viol
    return out


def plan_text(P):
    L = []
    s = P["score"]
    L.append("plan %s: SDRAM at (%g, %g) rotation %g, slot limit %.1f mm" % (P["name"], P["sdram"]["pos"][0], P["sdram"]["pos"][1], P["sdram"]["rot"], P["slot_max"]))
    L.append("score: signal balls %d / %d allocated, %d drawn; SDRAM nets %d / %d pad to pad; supply balls %d on %d vias (%d balls share); "
             "longest slot %.2f mm; SDRAM longest %s mm; lane spreads %s; tuning need %.1f mm, reserved %.1f mm; signal vias %d; total length %.0f mm; "
             "not met %d; allocation %.0f s, with drawing %.0f s" % (
                 s["allocated"], s["signal_balls"], s["drawn"], s["sdram_drawn"], s["sdram_nets"], s["supply_balls"], s["supply_vias"], s["shared"],
                 s["slot_longest"], s["sdram_longest"], s["lane_spreads"], s["tuning_need"], s["tuning_reserved"], s["vias_signal"], s["length_total"],
                 s["unmet"], s["seconds_allocation"], s["seconds_total"]))
    L.append("")
    L.append("NOT MET (%d)" % len(P["unmet"]))
    L += ["  " + u for u in P["unmet"]] or ["  nothing"]
    if P.get("sections"):
        L.append("")
        L.append("SECTIONS of the MCU outline (clockwise from the north-east corner): layers kept free of SDRAM lanes; SDRAM lanes leaving or passing per layer; other balls leaving per layer; balls of the section without a place")
        for s in P["sections"]:
            L.append("  %-16s free %-8s SDRAM %s  others %s  %s" % (s["section"], "+".join(s["free"]), " ".join("%s %d" % kv for kv in s["sdram_lanes"].items()),
                     " ".join("%s %d" % kv for kv in s["others_leaving"].items()), ("LOST: " + ", ".join(s["without_place"])) if s["without_place"] else ""))
    L.append("")
    L.append("RIVERS: per layer and MCU side, lanes in order (lane coordinate on the rule-area edge, net, target)")
    for l, sides in P["rivers"].items():
        for sd, rows in sides.items():
            L.append("  %s %s (%d): " % (l, sd, len(rows)) + ", ".join("%s@%.3f>%s" % (n, c, t) for n, c, t in rows))
    L.append("")
    L.append("SIGNAL BALLS")
    L.append("  ball net              layer side exit              via site           round         target  SDRAM ball / pin  entry               vias length  drawn")
    for net, d in sorted(P["signals"].items(), key=lambda kv: kv[1]["ball"]):
        L.append("  %-4s %-16s %-5s %-4s (%7.3f, %7.3f) %-18s %-13s %-7s %-17s %-19s %-4d %-7.2f %s" % (
            d["ball"], net, d["layer"], d["side"], d["exit"][0], d["exit"][1], "(%.3f, %.3f)" % tuple(d["via"]) if d["via"] else "-", d["round"], d["target"],
            ("%s %s" % (d.get("sd_ball"), d.get("sd_pin", ""))) if d["target"] == "SDRAM" else "-",
            ("%s (%.2f, %.2f)" % (d["entry_side"], d["entry"][0], d["entry"][1])) if d.get("entry") else "-", d["vias"], d["length"],
            "yes" if d["drawn"] else "NO: %s" % d["fail"]))
    L.append("")
    L.append("SUPPLY AND GROUND BALLS (via site; balls sharing it)")
    for ref, balls in P["supply"].items():
        L.append("  %s: " % ref + "; ".join("%s %s (%.3f, %.3f)%s" % (b, v["net"], v["site"][0], v["site"][1], (" with " + ",".join(v["shared_with"])) if v["shared_with"] else "") for b, v in balls.items()))
    L.append("")
    L.append("BOTTOM PARTS (centre, rotation, pads over sites, own vias, sites covered, supply balls served within %.1f mm)" % CAP_REACH)
    for c in P["caps"]:
        L.append("  %-5s %s %s (%.3f, %.3f) rot %4d  sites %s  own vias %s  covers %s  serves %s" % (
            c["ref"], c["size"], "/".join(c["nets"]), c["pos"][0], c["pos"][1], c["rot"], c["on_sites"], c["own_vias"], c["covers_sites"],
            ", ".join("%s %.2f" % (n, d) for n, d in c["serves"]) or "-"))
    L.append("")
    L.append("BYTE LANES (lengths mm; target = longest - %g + %g; reserved = RTE-2 capacity of the zones, pitch %.1f, amplitude %.1f-%.1f)" % (LANE_WINDOW, LANE_MARGIN, TUNE_PITCH, TUNE_AMP, TUNE_AMP_MAX))
    for lane, t in P["tuning"].items():
        L.append("  lane %s: longest %s shortest %s spread %s target %s; need %.2f mm over %d nets, reserved %.2f; shortfall %s" % (
            lane, t["longest"], t.get("shortest"), t["spread"], t["target"], t["need_total"], len(t["need"]), t["reserved"], t["shortfall"] or "none"))
        for n, zb in t["zones"].items():
            L.append("    %s need %.2f: zone %s box %s amplitude %.2f x %d humps = %.2f mm" % (n, t["need"][n], zb["layer"], zb["box"], zb["amp"], zb["humps"], zb["capacity"]))
    e = P["estimates"]
    L.append("")
    L.append("ESTIMATES: SDRAM longest %s (%s); address / command / clock min %s max %s; SDRAM nets with 3 vias: %s; nets with 4 or more vias: %s" % (
        e["sdram_longest"], e["sdram_longest_net"], (e["address_min_max"] or [None, None])[0], (e["address_min_max"] or [None, None])[1], e["sdram_vias_3"] or "none", e["vias_4_or_more"] or "none"))
    for k in ("ltdc", "qspi", "sdmmc", "rmii"):
        if k in e:
            L.append("  %s: %s" % (k, e[k]))
    sl = P["slots"]
    L.append("")
    L.append("PLANE SLOTS: longest chain %.3f mm (limit %.1f); over the limit: %s; over %s: %s" % (sl["longest"], sl["limit"], sl["over_limit"] or "none", "%g" % SLOT_REPORT, sl["over_%g" % SLOT_REPORT] or "none"))
    L.append("GROUND RETURN: no net changes layer outside the rule areas; signal vias farther than %g mm from a ground via: %s" % (GROUND_FAR, P["ground_return_far"] or "none"))
    return "\n".join(L)


# ---------------------------------------------------------------- command line
def _optional(name):
    """A module of this package that is not in the repository (bga_check, bga_plan_proof: branch try/fanout-first)."""
    import importlib
    try:
        return importlib.import_module("Tools.KiCadDesignTools.planning." + name)
    except ModuleNotFoundError as e:
        if e.name != "Tools.KiCadDesignTools.planning." + name:
            raise
        raise SystemExit("bga_plan: this needs planning/%s.py, which is not in this repository (it is on branch "
                         "try/fanout-first as stm32h743_sdram/%s.py)" % (name, name))


def main(argv):
    if len(argv) < 2 or argv[1] not in ("dump", "plan", "check"):
        print(__doc__)
        return 2
    cfg = setup(config.load(argv[0]))
    argv = argv[1:]
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    if argv[0] == "dump":
        from Tools.KiCadDesignTools.planning import bga_dump
        board = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else cfg.pcb
        bga_dump.dump(board, opt("--out", bga_dump.default_out(cfg)), cfg.origin)
        return 0
    if argv[0] == "plan":
        geo = json.load(open(opt("--geo"), encoding="utf-8"))
        k = argv.index("--sdram-pos")
        pos = (float(argv[k + 1]), float(argv[k + 2]))
        rot = float(opt("--sdram-rot", 0))
        name = opt("--name", "x%g_y%g_r%g" % (pos[0], pos[1], rot))
        lanes = tuple(int(ch) for ch in opt("--lanes", "".join(str(i) for i in range(NLANES))))
        out = os.path.join(os.path.dirname(os.path.abspath(opt("--geo"))), name)
        plan, m = run_plan(geo, pos, rot, float(opt("--slot-max", SLOT_MAX)), lanes, name, out, do_draw="--no-draw" not in argv, tx=float(opt("--time", 150.0)),
                           order=opt("--order", "fence"))
        print(plan_text(plan).split("\n\nRIVERS")[0])
        print("wrote", os.path.join(out, "plan.txt"))
        return 0
    if "--board" in argv:
        from Tools.KiCadDesignTools.core import paths
        from Tools.KiCadDesignTools.planning import bga_dump
        import shutil, subprocess, tempfile
        gp = os.path.join(tempfile.mkdtemp(prefix="bga_plan_"), "geo.json")
        bga_dump.dump(opt("--board"), gp, cfg.origin)
        py = shutil.which("python") or shutil.which("python3")       # the model needs numpy / scipy / scikit-image: not KiCad's Python
        if not py or os.path.normcase(os.path.dirname(py)) == os.path.normcase(os.path.dirname(sys.executable)):
            print("no system Python on PATH; run (from %s):  python -m Tools.KiCadDesignTools.planning.bga_plan %s check --geo %s" % (paths.REPO, cfg.dir, gp))
            return 2
        rest = [a for i, a in enumerate(argv[1:]) if a != "--board" and argv[i] != "--board"]
        return subprocess.run([py, "-m", "Tools.KiCadDesignTools.planning.bga_plan", cfg.dir, "check", "--geo", gp] + rest, cwd=paths.REPO).returncode
    geo = json.load(open(opt("--geo"), encoding="utf-8"))
    if "--plan" in argv:
        return check_plan(geo, json.load(open(opt("--plan"), encoding="utf-8")))
    bga_check = _optional("bga_check")                       # the per-ball verdict only; check --plan does without it
    nets = opt("--nets").split(",") if "--nets" in argv else None
    r = bga_check.check_state(geo, float(opt("--slot-max", SLOT_MAX)), nets, log=None, joint="--joint" in argv)
    if "--out" in argv:
        json.dump(r, open(opt("--out"), "w", encoding="utf-8"), indent=0)
    print(bga_check.table(r))
    return 0


def check_plan(geo, plan):
    """The grid model's verdict for a plan: every planned net against the state plus all the other planned
    copper (its own left out). Prints one line per ball that is not clear."""
    import numpy as np
    G = bga_grid
    g = planning_state(geo, plan["sdram"]["pos"], plan["sdram"]["rot"])
    want = {d["sd_ball"]: (n if n != CLOCK else CLOCK_R) for n, d in plan["signals"].items() if d.get("sd_ball")}
    for p in g["pads"]:                                     # the swap: an SDRAM ball carries the net that ends on it
        if p["ref"] == SDRAM and p["num"] in want:
            p["net"] = want[p["num"]]
        elif p["ref"] == SDRAM and p["net"] in want.values():
            p["net"] = "<swapped away>"
    f = G.Field(g, WINDOW)
    padpos = {"%s.%s" % (p["ref"], p["num"]): tuple(p["pos"]) for p in g["pads"]}
    # the parts the plan places are not in the state: their pads as the plan names them in power_routes (<ref>.<k + 1>)
    padpos.update({"%s.%d" % (c["ref"], k + 1): tuple(p) for c in plan["caps"] for k, p in enumerate(c["pads"])})
    items = []
    for c in plan["caps"]:
        off, hl, hw = CAP_GEOM[c["size"]]
        horiz = c["rot"] in (0, 180)
        for k, p in enumerate(c["pads"]):
            hx, hy = (hl, hw) if horiz else (hw, hl)
            items.append(G.Item(c["nets"][k], (BOTTOM,), "poly", poly=[(p[0] - hx, p[1] - hy), (p[0] + hx, p[1] - hy), (p[0] + hx, p[1] + hy), (p[0] - hx, p[1] + hy)], a=tuple(p), tag=c["ref"]))
    fix = lambda pcs: [("via", tuple(pc[1])) if pc[0] == "via" else (pc[0], [padpos[q] if isinstance(q, str) else tuple(q) for q in pc[1]]) + ((pc[2],) if len(pc) > 2 else ()) for pc in pcs]
    for net, chains in plan["power_routes"].items():
        for ch in chains:
            items += piece_items(G, f, net, fix(ch))
    routes = {}
    for net, d in plan["signals"].items():
        for n2, pcs in d["routes"].items():
            routes[n2] = (d["ball"], fix(pcs))
            items += piece_items(G, f, n2, routes[n2][1])
    add_items(f, items)
    bad = 0
    for net, (ball, pcs) in sorted(routes.items()):
        D, H = f.opened(net, extra_own=[it for it in f.items if it.net == "<xtal>"])
        why = None
        for pc in pcs:
            if pc[0] == "via":
                if not f.via_ok(pc[1], D, H):
                    why = "via at %s is not legal" % (pc[1],)
            else:
                mask = f.track_free(pc[0], net_width(g, net), D, H)
                if not sample_ok(f, mask, pc[1]):
                    why = "track on %s is not clear" % pc[0]
            if why:
                break
        if why:
            bad += 1
            print("%-4s %-16s conflict: %s" % (ball, net, why))
    print("check of plan %s: %d routes, %d with a conflict, %d balls not drawn" % (plan["name"], len(routes), bad, sum(1 for d in plan["signals"].values() if not d["drawn"])))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
