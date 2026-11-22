"""Power group of the two BGAs (stop 5, power and copper, part B): the supply and ground balls of U201 (MCU) and
U301 (SDRAM), each by a dog-bone to a 0.30 / 0.15 via at a ball-gap point and so to its plane (GND: L2 / L5,
+3V3_MCU / +3V3_SDRAM: their L3 blocks), and the bottom decoupling under them (pad over a via, or an L6 stub).

    sh stm32h743_sdram/build.sh copper          (the whole step; this group follows routes_power.py)
    D:\\KiCad\\bin\\python.exe scripts\\busroute\\build.py stm32h743_sdram\\routes_power_bga.py --fast

A second SHARED group beside `power` (part A): it replaces only its own copper of the last build. Sites are
searched by bga_power.py against the pads, part A's copper and the SDRAM line-order sketch (tracks and vias of the
FMC nets on out/sketch/rot0), so the group comes out the same on the real board and on the sketch copy
(POWER_BOARD=<that board> builds it there). Ground is not routed (user 2026-11-21): a ball goes to its via and
nothing else. VCAP1 / VCAP2 are track class: their capacitor pads take the widest stub that fits.
"""
import json, os
from bga_power import BgaPlanner, WIDE_W, VIA_OUT
from busroute.board import old_items

BOARD = os.environ.get("POWER_BOARD", "stm32h743_sdram.kicad_pcb")
ORIGIN = (100, 100)
GROUP = "power_bga"
SHARED = True                 # GND and the rails get copper from part A too: replace only our own
OPEN_ENDS = True              # dog-bones of a shared via and L6 stubs end at vias
YIELD_NETS = ["GND"]          # the L1 / L6 ground pours give way to the dog-bones and stubs
VIA_LIMIT = 10000
PROFILE = {"area_free_classes": ["PWR"]}     # the .kicad_dru lets PWR tracks be wider than 0.09 in the rule areas
ALLOW_VIA_ON = []             # the capacitor pads over a via (approved via-in-pad under the BGAs), filled by routes()
DRC_IGNORE = {"via_dangling": "this build does not refill the pours; build.sh copper judges connectivity on the refilled board",
              "solder_mask_bridge": "mask webs between fine-pitch pads of the footprints (QFN, FPC), there before this group"}
HERE = os.path.dirname(os.path.abspath(__file__))
SKETCH_BOARD = os.path.join(HERE, "out", "sketch", "rot0", "stm32h743_sdram.kicad_pcb")
POWER = {"U201": ["GND", "+3V3_MCU", "VDDA_MCU", "VCAP1", "VCAP2"], "U301": ["GND", "+3V3_SDRAM"]}
PARTS = ["C%d" % i for i in range(201, 224) if i != 217] + ["FB201"] + ["C%d" % i for i in range(301, 309)]
# ball-gap sites no via of this group may take: kept for a signal ball's way out (escape_check, stop 4 numbers)
FORBID = []
# no via of another net in these boxes: where the L3 tongue of +3V3_MCU (x 39.6-44.2) enters the MCU's ball field,
# between the SDRAM sketch's vias, down to the first supply vias (row C)
PROTECT = [("+3V3_MCU", (40.0, 30.5, 43.2, 33.1))]


def routes(job):
    b = job.board
    ob = SKETCH_BOARD if os.path.isfile(SKETCH_BOARD) else None
    caps = [n for ref in PARTS for n in b.fp.get(ref, {}).get("pads", [])]
    P = BgaPlanner(b, job.profile, os.path.join(HERE, "copper.sketch"), POWER, caps, ob, skip_items=old_items(b.path, GROUP), forbid=FORBID,
                   protect=PROTECT)
    P.place_balls("U201")
    P.place_balls("U301")
    P.connect_caps(widths_for={"VCAP1": WIDE_W, "VCAP2": WIDE_W})
    ALLOW_VIA_ON[:] = sorted(P.allow)
    job.stitch += P.extras
    job.notes += P.log
    log = os.environ.get("POWER_BGA_LOG", os.path.join(HERE, "out", "copper", "power_bga_sites.txt"))
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        f.write("power_bga group sites on %s\n" % b.path)
        f.write("\n".join(P.log) + "\n")
    with open(os.path.splitext(log)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump({"board": b.path, "done": P.done, "ball_via": {k: list(v) for k, v in P.ball_via.items()},
                   "shared": P.shared, "nosite": P.nosite, "caps": P.cap_conn, "allow": sorted(P.allow),
                   "vias": [[n, list(p), list(s), k] for n, p, s, k in P.mine], "log": P.log}, f, indent=0)
    return P.chains
