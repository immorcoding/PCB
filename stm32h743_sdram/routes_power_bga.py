"""Power group of the two BGAs (the BGA block, SPEC 14 stop 3.2 / 3.3; layer order signal / GND / signal / signal /
power / signal): every supply and ground ball of U201 (MCU) and U301 (SDRAM) on a 0.30 / 0.15 via of its own by an
L1 dog-bone (GND: the L2 plane, +3V3_MCU / +3V3_SDRAM: their L5 blocks), and the bottom decoupling over those vias.

    sh stm32h743_sdram/build.sh route2          (the whole board; this group follows routes_power.py)
    D:\\KiCad\\bin\\python.exe scripts\\busroute\\build.py stm32h743_sdram\\routes_power_bga.py --fast

The sites come from the BGA block plan bga_fan.json (bga_fan.py: one mixed integer program over the ball lattice
for the supply vias, the capacitor places and the fan-out of the MCU's signal balls, with the plane-slot rule
exact); this file only draws them and checks each piece against the board (bga_power.BgaPlanner). A capacitor pad
lies over a via of its net (a ball's or one of its own, the approved via-in-pad under the BGAs); the VDDA filter
parts and the VCAP capacitors are joined by BgaPlanner.connect_caps (pour, stub or own via) as before. Ground is not
routed (user 2026-11-21): a ball goes to its via and nothing else. A SHARED group beside `power` (part A).
"""
import json, os
from bga_power import BgaPlanner, WIDE_W, VIA_IN, BONE_W, r4
from busroute.board import old_items

BOARD = os.environ.get("POWER_BOARD", "stm32h743_sdram.kicad_pcb")
ORIGIN = (100, 100)
GROUP = "power_bga"
SHARED = True                 # GND and the rails get copper from part A too: replace only our own
OPEN_ENDS = True              # the capacitors' own vias and L6 stubs end at vias
YIELD_NETS = ["GND"]          # the L1 / L6 ground pours give way to the dog-bones and stubs
VIA_LIMIT = 10000
PROFILE = {"area_free_classes": ["PWR"]}     # the .kicad_dru lets PWR tracks be wider than 0.09 in the rule areas
ALLOW_VIA_ON = []             # the capacitor pads over a via (approved via-in-pad under the BGAs), filled by routes()
DRC_IGNORE = {"via_dangling": "this build does not refill the pours; build.sh route2 judges connectivity on the refilled board",
              "solder_mask_bridge": "mask webs between fine-pitch pads of the footprints (QFN, FPC), there before this group"}
HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = os.environ.get("BGA_FAN", os.path.join(HERE, "bga_fan.json"))
OBSTACLES = os.environ.get("SDRAM_OBSTACLES", "")
POWER = {"U201": ["GND", "+3V3_MCU", "VDDA_MCU", "VCAP1", "VCAP2"], "U301": ["GND", "+3V3_SDRAM"]}
PARTS = ["C%d" % i for i in range(201, 224) if i != 217] + ["FB201"] + ["C%d" % i for i in range(301, 309)]


def routes(job):
    b = job.board
    plan = json.load(open(PLAN, encoding="utf-8"))
    ob = OBSTACLES if os.path.isfile(OBSTACLES) else None
    caps = [n for ref in PARTS for n in b.fp.get(ref, {}).get("pads", [])]
    P = BgaPlanner(b, job.profile, os.path.join(HERE, "copper.sketch"), POWER, caps, ob, skip_items=old_items(b.path, GROUP))
    for ref in ("U201", "U301"):
        r = plan[ref]
        for num, v in sorted(r["supply"].items(), key=lambda kv: (kv[1]["ball"][1], kv[1]["ball"][0])):
            ball = b.pads["%s.%s" % (ref, num)]
            if not v["via"]:
                P.log.append("NO SITE  %s %s: the plan has no via for it" % (ball.name, ball.net))
                P.nosite[ball.name] = "no site in the plan"
                continue
            s = (r4(v["via"][0]), r4(v["via"][1]))
            why = P.via_why(ball.net, s, VIA_IN)
            w = next((w for w in BONE_W if P.seg_why(ball.net, "L1", ball.pos, s, w) is None), None)
            if why or w is None:
                P.log.append("LOST     %s %s: planned via (%.3f, %.3f) %s" % (ball.name, ball.net, s[0], s[1], why or "dog-bone not free"))
                P.nosite[ball.name] = why or "dog-bone"
                continue
            P._bone(ball, s, w, new_via=True, kind="ball")
        for key, net in sorted(r["own"].items()):
            p = tuple(r4(float(c)) for c in key.split(","))
            why = P.via_why(net, p, VIA_IN, pads_ok=[n for n in caps])
            if why:
                P.log.append("LOST     own via of %s at (%.3f, %.3f): %s" % (net, p[0], p[1], why))
                continue
            P._put_via(net, p, VIA_IN, "own")
            P.extras.append((net, p))
            P.log.append("own      %-11s via (%.3f, %.3f) under a capacitor pad" % (net, p[0], p[1]))
    P.connect_caps(widths_for={"VCAP1": WIDE_W, "VCAP2": WIDE_W})
    ALLOW_VIA_ON[:] = sorted(P.allow)
    job.stitch += P.extras
    job.notes += P.log
    log = os.environ.get("POWER_BGA_LOG", os.path.join(HERE, "out", "route2", "power_bga_sites.txt"))
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        f.write("power_bga group sites on %s (plan %s)\n" % (b.path, PLAN))
        f.write("\n".join(P.log) + "\n")
    with open(os.path.splitext(log)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump({"board": b.path, "done": P.done, "ball_via": {k: list(v) for k, v in P.ball_via.items()},
                   "shared": P.shared, "nosite": P.nosite, "caps": P.cap_conn, "allow": sorted(P.allow),
                   "vias": [[n, list(p), list(s), k] for n, p, s, k in P.mine], "log": P.log}, f, indent=0)
    return P.chains
