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
  feeds     the vias that join a local pour or a link resistor to its L5 block or to the other outer layer:
            at least 1 per 0.5 A of the rail and at least 2 per regulator output, link side and block feed
  supply    one via to its L5 block beside every other pad of +3V3, +5V, +3V3A (pull-ups, enables, test pads)
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

# ---- feeds: (pad, count, how). plane = the via lands in the pad net's L5 block; 1.2 A / 1.1 A rails take 3.
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
    ("pour", "U501.19", "L1_VDDA_PHY_N", {}), ("pour", "U501.1", "L1_VDDA_PHY_S", {}),
    ("hop", "R105.1", "L1_3V3_REG", {}),          # feedback divider's top (R102.1's is FIXED below)
    ("pad", "R402.1", "R401.1", {}), ("reach", "R401.1", "L1_3V3_QSPI", {}),       # pull-ups on the bottom
]
# VDDA_PHY (stop 7): each L1 piece drops to the L6 region by a via near these points (copper.sketch)
VDDA_PHY_FEEDS = [("L1_VDDA_PHY_N", (19.35, 48.1), 1), ("L1_VDDA_PHY_W", (18.1, 53.1), 1), ("L1_VDDA_PHY_S", (20.2, 54.75), 1)]
# +3V3_PHY (stop 7): PHY pin 9 (VDDIO) and the MDIO pull-up R503 by a via each into L6_3V3_PHY, which feeds the L1 pour
# by two vias between C504 and C505
PHY_3V3_VIAS = ["U501.9", "R503.1"]
PHY_3V3_FEED = ((26.15, 52.45), 1)              # one site between C504 and C505 (pin 9 and R503 draw a few mA)
# ---- fixed chains, written as given (checked like every other site): R102.1, the 5 V divider's top (R102 turned at
# stop 7: R102.1 north), hops on L6 along y 39.9 (north of C104's ground via) into L1_5V_REG, so that FB_5V's own L6 hop from
# U101.4 to the divider (routes_local.py, y 41.45) stays south of it
FIXED = [("R102.1", [("L1", ["R102.1", (65.0, 39.9)]), ("via", (65.0, 39.9)),
                     ("L6", [(65.0, 39.9), (77.5, 39.9), (78.4, 40.8)]), ("via", (78.4, 40.8))]),
         # stop 7 compose: the bead's VDDA_PHY via west of it (one: the PHY's analog supply draws tens of mA; a second
         # one has no site off the lanes without a 90-degree turn at a via), south of C506 (into the L6 block's widened east
         # end); C506's and C508's ground vias where they stood at stop 7 (with the lanes box the search put them on
         # VDDCR's / PHY_XI's L1 ties); the searched sites stood on the L4 lanes of LCD_B6 / B7 / DISP (x 27.14-27.6)
         # and USER_KEY (x 28.4)
         ("FB501.2", [("L1", ["FB501.2", (27.9, 56.9), (27.5, 57.3), (26.45, 57.3)]), ("via", (26.45, 57.3))]),
         ("C506.2", [("L1", ["C506.2", (26.725, 54.525)]), ("via", (26.725, 54.525))]),
         ("C508.2", [("L1", ["C508.2", (25.5, 57.795)]), ("via", (25.5, 57.795))]),
         # R501.2 (PHY_NRST pull-down's ground pad): PHY_NRST, REF_CLK and MDC box its L1 ground piece in; a via in it
         ("R501.2", [("L1", ["R501.2", (23.41, 46.1)]), ("via", (23.41, 46.1))])]
FIXED_PADS = {pad for pad, _ in FIXED}
# ---- ground
GND_REG = ["U101.1", "U102.2", "U103.2", "U104.2", "U701.2"]                  # regulator / switcher ground pins
GND_TIGHT = {"U101.1": 0.5, "C104.2": 0.5, "U701.2": 0.5, "C705.2": 0.5, "C102.2": 0.6}    # loop closures (U56)
GND_IC = ["U401.4", "U401.9", "U601.6", "U601.17", "U601.21", "U601.26", "U801.2", "D801.3", "D102.2",
          "Y501.2", "Y501.4", "Y201.2", "Y201.4"]
GND_CONN = ("J601", "J602", "J701", "J801", "J803")
GND_ISLAND = ["R101.2", "R708.2"]     # pads whose L1 ground pour piece KiCad's refill leaves on its own (pour_islands.py)
# L5 +5V: the strip under the top connectors and the leg down to R112 are 3 mm wide; no via of another net may cut
# them (a ground via of J801 left 1.7 mm at the strip's east end in the first build)
PROTECT = [("+5V", (33.5, 5.5, 64.0, 8.5)), ("+5V", (33.5, 8.5, 36.5, 22.5)),
           # stop 7: the escape lanes of the PHY's MCU-bound pins (13-18 north, 7 / 8 / 11 / 12 east) take no via of the
           # power group except the +3V3_PHY vias of pin 9 and R503 that the east lanes pass
           ("-", (20.95, 44.0, 22.6, 48.1)), ("+3V3_PHY", (24.8, 48.9, 27.0, 52.0)),
           # stop 7 compose: the L4 lanes of LCD_B6 / B7 / DISP down the strip between the PHY and USER_KEY
           # (routes_mcu_west.py, x 27.14-27.6) take no via (FB501's VDDA_PHY vias and a ground via stood there)
           ("-", (27.16, 44.3, 27.6, 66.0))]


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
    # VDDA_PHY: the three L1 pieces down to the L6 region, the bead and the bulk capacitor into it
    for region, near, n in VDDA_PHY_FEEDS:
        P.feed("VDDA_PHY", near, n, outer=("L1", "L6"), radius=0.8, spacing=0.6, label=region)
    P.tie_via("C501.1", outer=("L6",), lmax=1.2)      # FB501.2: FIXED (its via)
    done |= {"FB501.2", "C501.1"}
    # +3V3_PHY: pin 9 and R503 by their own via into the L6 strip; the strip into the L1 pour
    for pad in PHY_3V3_VIAS:
        P.tie_via(pad, outer=("L6",), lmax=1.2)
    P.feed("+3V3_PHY", PHY_3V3_FEED[0], PHY_3V3_FEED[1], outer=("L1", "L6"), radius=1.2, spacing=0.6, label="L1_3V3_PHY - L6 strip")
    # ground of the hot loops first (U56), then the ties, then every other ground and supply via
    P.via_in_pad("U601.33", 3, 3, 1.0)
    gnd = [p for ref in sorted(b.by_ref) if ref not in PART_B for p in b.by_ref[ref] if p.net == "GND" and p.hole <= 0]
    for p in gnd:
        if p.name in GND_TIGHT or p.name in GND_REG:
            P.tie_via(p, lmax=1.6, pad_edge_max=GND_TIGHT.get(p.name, 1.0))
    for pad, pieces in FIXED:
        P.fixed(pad, pieces)
    for kind, pad, to, kw in TIES:
        if kind == "pour":
            P.tie_pour(pad, to, **kw)
        elif kind == "pad":
            P.tie_pad(pad, to, **kw)
        elif kind == "hop":
            P.hop(pad, to, "L6", **dict({"lmax_a": 1.5, "lmax_mid": 14.0}, **kw))
        else:
            P.hop(pad, to, "L6", lmax_a=0, lmax_mid=10.0, **kw)
    for p in gnd:
        if p.ref.startswith("C") and p.name not in GND_TIGHT and p.name not in FIXED_PADS:
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


