"""Power group of the STM32H743 + SDRAM board (stop 5, power and copper, part A): every via and short tie of the
copper-class nets (SPEC 5) outside the two BGA rule areas. The pours themselves come from copper.sketch.

    sh stm32h743_sdram/build.sh copper          (the whole step: sketch, this group, refill, measures)
    D:\\KiCad\\bin\\python.exe scripts\\busroute\\build.py stm32h743_sdram\\routes_power.py --fast

The sites are searched by power_ties.py at build time against the pads, the copper.sketch regions and the
SDRAM line-order sketch (tracks and vias of the `sdram` group on out/sketch/rot0), so the group comes out the
same on the real board and on the sketch copy (POWER_BOARD=<that board> builds it there). Nothing is placed in
the BGA rule areas; the supply and ground balls of U201 / U301, their dog-bones and the bottom decoupling
under them (PART_B) are routes_power_bga.py (part B, a second shared group).

What is drawn, in this order (earlier items take the better sites):
  feeds     the vias that join a local pour or a link resistor to its L3 block or to the other outer layer:
            at least 1 per 0.5 A of the rail and at least 2 per regulator output, link side and block feed
  supply    one via to its L3 block beside every other pad of +3V3, +5V, +3V3A (pull-ups, enables, test pads)
  ties      the pads the sketch leaves to a short track (QFN pins, feedback tops, pull-ups on the bottom)
  ground    ground is not routed (user 2026-11-21): its own via beside every capacitor ground pad (pad edge to
            via centre <= 1.0 mm), regulator and IC ground pin and SMD connector ground; resistor and LED ground
            pads rely on the L1 / L6 ground pour (a via is added where the refill leaves one unconnected)
Via 0.45 / 0.2 everywhere (outside the rule areas); ties are 0.3048 mm (PWR class) or 80 % of a narrow pad.
"""
import json, os
from power_ties import Planner

BOARD = os.environ.get("POWER_BOARD", "stm32h743_sdram.kicad_pcb")
ORIGIN = (100, 100)
GROUP = "power"
SHARED = True                 # GND and the rails get copper from other groups too (part B): replace only our own
OPEN_ENDS = True              # ties end at vias and in pours
YIELD_NETS = ["GND"]          # the L1 / L6 ground pours give way to ties
VIA_LIMIT = 10000
DRC_IGNORE = {"via_dangling": "this build does not refill the pours; build.sh copper judges connectivity on the refilled board",
              "solder_mask_bridge": "mask webs between fine-pitch pads of the footprints (QFN, FPC), there before this group"}
ALLOW_VIA_ON = ["U601.33"]    # codec exposed pad: thermal vias, approved like the PHY's (stop 4 round 2)
HERE = os.path.dirname(os.path.abspath(__file__))
SKETCH_BOARD = os.path.join(HERE, "out", "sketch", "rot0", "stm32h743_sdram.kicad_pcb")
# the board whose FMC_ tracks and vias are the obstacles of this group: the line-order sketch copy (build.sh copper),
# or, once the bus is on the real board (build.sh route1), that board itself: SDRAM_OBSTACLES=<board>
OBSTACLES = os.environ.get("SDRAM_OBSTACLES", SKETCH_BOARD)
VIA = (0.45, 0.2)

PART_B = {"U201", "U301", "FB201"} | {"C%d" % i for i in range(201, 224)} - {"C217", "C224", "C225", "C226", "C227", "C228"} \
    | {"C%d" % i for i in range(301, 309)}

# ---- feeds: (pad, count, how). plane = the via lands in the pad net's L3 block; 1.2 A / 1.1 A rails take 3.
FEEDS = [
    ("R110.2", 3, "plane"),        # +5V_REG -> R110 -> +5V (1.2 A)
    ("R111.2", 3, "plane"),        # +3V3_REG -> R111 -> +3V3 (1.1 A)
    ("U102.4", 2, "plane"),        # 3.3 V buck input from the +5V band (about 0.8 A)
    ("C108.1", 1, "plane"),
    ("R112.1", 2, "plane"),        # links from the plane to local pours
    ("R710.1", 2, "plane"),
    ("R814.1", 2, "plane"),
    ("R203.1", 2, "plane"), ("R203.2", 2, "plane"), ("C217.1", 1, "plane"),
    ("R301.1", 2, "plane"), ("R301.2", 2, "plane"), ("C309.1", 1, "plane"),
    ("R404.1", 2, "plane"), ("R514.1", 2, "plane"), ("R610.1", 2, "plane"), ("R709.1", 2, "plane"),
    ("R812.1", 2, "plane"), ("R813.1", 2, "plane"), ("R113.1", 2, "plane"),
    ("U103.5", 1, "plane"), ("C111.1", 1, "plane"),     # +3V3A LDO output into its block (2 together)
]
# ---- other supply pads of the plane nets: one via each
PLANE_NETS = ("+3V3", "+5V", "+3V3A")
# ---- ties of pads to their pour or to a pad (sketch: "reached by a short track")
TIES = [   # (kind, pad, target, options)
    ("pour", "C101.2", "L1_SW_5V", {"lmax": 3.5}),                  # bootstrap capacitor to the switch node
    ("pour", "U101.5", "L1_12V", {}),                                  # enable tied to the input
    ("pour", "U601.32", "L1_1V8", {}), ("pour", "U601.7", "L1_3V3_AUD", {}),
    ("pour", "U501.9", "L1_3V3_PHY", {}), ("pour", "R503.1", "L1_3V3_PHY", {"w": 0.2}),
    ("pour", "U501.19", "L1_VDDA_PHY", {}), ("pour", "C503.1", "L1_VDDA_PHY", {}), ("pad", "U501.1", "C503.1", {}),
    ("hop", "R102.1", "L1_5V_REG", {}), ("hop", "R105.1", "L1_3V3_REG", {}),          # feedback dividers' tops
    ("pad", "R402.1", "R401.1", {}), ("reach", "R401.1", "L1_3V3_QSPI", {}),       # pull-ups on the bottom
]
# VDDA_PHY: the L6 strip under the PHY joins the L1 column (west end) and FB501's VDDA pad (east end)
VDDA_PHY_WEST = (18.2, 56.4)
# ---- ground
GND_REG = ["U101.1", "U102.2", "U103.2", "U104.2", "U701.2"]                  # regulator / switcher ground pins
GND_TIGHT = {"U101.1": 0.5, "C104.2": 0.5, "U701.2": 0.5, "C705.2": 0.5, "C102.2": 0.6}    # loop closures (U56)
GND_IC = ["U401.4", "U401.9", "U601.6", "U601.17", "U601.21", "U601.26", "U801.2", "D801.3", "D102.2",
          "Y501.2", "Y501.4", "Y201.2", "Y201.4"]
GND_CONN = ("J601", "J602", "J701", "J801", "J803")
GND_ISLAND = ["R101.2", "R708.2"]     # pads whose L1 ground pour piece KiCad's refill leaves on its own (pour_islands.py)
# L3 +5V: the strip under the top connectors and the leg down to R112 are 3 mm wide; no via of another net may cut
# them (a ground via of J801 left 1.7 mm at the strip's east end in the first build)
PROTECT = [("+5V", (33.5, 5.5, 64.0, 8.5)), ("+5V", (33.5, 8.5, 36.5, 22.5))]


def routes(job):
    job.profile.classes["PWR"]["via"] = VIA                  # PWR class default is 0.6 / 0.3; this board uses 0.45 / 0.2
    ob = OBSTACLES if os.path.isfile(OBSTACLES) else None
    nets = sorted(n for n in job.board.nets if n.startswith("FMC_")) if ob else []
    P = Planner(job.board, job.profile, os.path.join(HERE, "copper.sketch"), ob, nets, VIA, ALLOW_VIA_ON, PROTECT)
    b = job.board
    done = set()
    # feeds
    for pad, n, how in FEEDS:
        for _ in range(n):
            P.tie_via(pad, plane=True, lmax=1.8)
        done.add(pad)
    # the VDDA_PHY strip on L6
    P.feed("VDDA_PHY", VDDA_PHY_WEST, 2, outer=("L1", "L6"), radius=1.5, label="column - L6 strip")
    for _ in range(2):
        P.tie_via("FB501.2", outer=("L6",), lmax=1.8)
    done.add("FB501.2")
    # ground of the hot loops first (U56), then the ties, then every other ground and supply via
    P.via_in_pad("U601.33", 3, 3, 1.0)
    gnd = [p for ref in sorted(b.by_ref) if ref not in PART_B for p in b.by_ref[ref] if p.net == "GND" and p.hole <= 0]
    for p in gnd:
        if p.name in GND_TIGHT or p.name in GND_REG:
            P.tie_via(p, lmax=1.6, pad_edge_max=GND_TIGHT.get(p.name, 1.0))
    for kind, pad, to, kw in TIES:
        if kind == "pour":
            P.tie_pour(pad, to, **kw)
        elif kind == "pad":
            P.tie_pad(pad, to, **kw)
        elif kind == "hop":
            P.hop(pad, to, "L6", lmax_a=1.5, lmax_mid=14.0, **kw)
        else:
            P.hop(pad, to, "L6", lmax_a=0, lmax_mid=10.0, **kw)
    for p in gnd:
        if p.ref.startswith("C") and p.name not in GND_TIGHT:
            P.tie_via(p, lmax=1.6, pad_edge_max=1.0)
    for name, p in sorted(b.pads.items()):
        if p.net in PLANE_NETS and name not in done and p.ref not in PART_B and p.hole <= 0:
            P.tie_via(name, plane=True, lmax=1.6)
            done.add(name)
    for p in gnd:
        if p.name in GND_IC or p.name in GND_ISLAND:
            P.tie_via(p, lmax=2.5)
        elif p.ref in GND_CONN:
            P.tie_via(p, lmax=2.0)
    for line in P.log:
        job.notes.append(line)
    log = os.environ.get("POWER_LOG", os.path.join(HERE, "out", "copper", "power_sites.txt"))
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        f.write("power group sites on %s\n" % job.board.path)
        f.write("\n".join(P.log) + "\n")
    with open(os.path.splitext(log)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump({"board": job.board.path, "done": P.done, "log": P.log}, f, indent=0)
    out ={n: chains for n, chains in P.chains.items()}
    job.stitch += P.extras
    return out


