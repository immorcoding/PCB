"""Power group of the two BGAs: every supply and ground ball of U1 (MCU) and U2 (SDRAM) on a 0.30 / 0.15 via of its
own by an L1 dog-bone (GND: the L2 plane; +3V3: the L5 block; VCAP1 / VCAP2: no plane, the via only carries the ball to
its capacitor's pad on L6), and the bottom decoupling C3-C8 and the VCAP capacitors C10 / C11 over those vias.

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.build templates/demo_board route   (after the bus group)
    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.routing.busroute.build templates\\demo_board\\routes_power_bga.py --fast

The sites are chosen by copper.bga_power.BgaPlanner on the board as the bus group left it (its tracks and vias are
obstacles): per ball one of the four ball-gap points round it (a capacitor pad of the ball's net over it first, no
signal ball's last free site, no plane slot grown), else a neighbour's via of the same net; then each capacitor pad
in-pad over a via of its net, an L6 stub to one, or a via of its own. Ground is not routed (a ball goes to its via
and nothing else). A SHARED group: it replaces only what it wrote itself.
"""
import json, os
from Tools.KiCadDesignTools.copper.bga_power import BgaPlanner, WIDE_W
from Tools.KiCadDesignTools.routing.busroute.board import old_items

BOARD = os.environ.get("BOARD", "demo_board.kicad_pcb")
ORIGIN = (100, 100)
GROUP = "power_bga"
SHARED = True                 # GND and +3V3 get copper from other groups too: replace only our own
OPEN_ENDS = True              # the dog-bones end at vias
YIELD_NETS = ["GND"]          # the L1 / L6 ground pours give way to the dog-bones and stubs
VIA_LIMIT = 10000
PROFILE = {"area_free_classes": ["PWR"]}     # the rule file lets PWR tracks be wider than 0.09 in the rule areas
ALLOW_VIA_ON = []             # the capacitor pads over a via (the profile's via-in-pad exception), filled by routes()
DRC_IGNORE = {"via_dangling": "this build does not refill the pours; the route step judges connectivity on the refilled board"}
HERE = os.path.dirname(os.path.abspath(__file__))
POWER = {"U1": ["GND", "+3V3", "VCAP1", "VCAP2"], "U2": ["GND", "+3V3"]}   # per package: the nets whose balls get a via here
PARTS = ["C3", "C4", "C5", "C6", "C7", "C8", "C10", "C11"]   # the bottom decoupling and the VCAP capacitors under the packages


def routes(job):
    b = job.board
    caps = [n for ref in PARTS for n in b.fp.get(ref, {}).get("pads", [])]
    P = BgaPlanner(b, job.profile, os.path.join(HERE, "copper.sketch"), POWER, caps, skip_items=old_items(b.path, GROUP))
    for ref in POWER:
        P.place_balls(ref)
    P.connect_caps(widths_for={"VCAP1": WIDE_W, "VCAP2": WIDE_W})    # a VCAP stub, if one is needed: short and wide
    ALLOW_VIA_ON[:] = sorted(P.allow)
    job.stitch += P.extras
    job.notes += P.log
    log = os.environ.get("POWER_BGA_LOG", os.path.join(HERE, "out", "route", "power_bga_sites.txt"))
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        f.write("power_bga group sites on %s\n" % b.path)
        f.write("\n".join(P.log) + "\n")
    with open(os.path.splitext(log)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump({"board": b.path, "done": P.done, "ball_via": {k: list(v) for k, v in P.ball_via.items()},
                   "shared": P.shared, "nosite": P.nosite, "caps": P.cap_conn, "allow": sorted(P.allow),
                   "vias": [[n, list(p), list(s), k] for n, p, s, k in P.mine], "log": P.log}, f, indent=0)
    return P.chains
