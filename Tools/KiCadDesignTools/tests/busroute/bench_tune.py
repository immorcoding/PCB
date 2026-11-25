"""Routes of the tuning benchmark (copied next to the board by check.py; the board is check.make_board with TUNE_PADS).

  lane1   L1, a five-lane bundle FMC_D8..D12 from the south row of U1 (R13..R9) down, east below both rule
          areas (lane pitch 0.9) and up into the south row of U2 (R1, P1, R2, P2, R3; P1 / P2 through channels).
          The inner lanes are shorter (natural spread 9.4 mm); the three short ones have a site on the east leg
          (Bundle.slot, all starting at station 1.2, humps north): D8 six humps, D9 two humps under D8's, D10 a
          bump. Spread 4.2: check.py's skew rule bench_lane1 (5 mm, it wins over the project's sdram_lane1, 1.27 mm
          since 2026-11-24) covers exactly these five nets.
          On the east leg D11 runs 0.25 mm south of D10 (the lane pitch of the H743 board: 0.148 mm edge to edge, below
          clr 0.19): D10's bump is drawn all the same, it comes no closer to D11 than the straight it replaces.
  hand    L1, FMC_A0..A3 written by hand (bus.keep) from the north row of U1 over the top to the north row
          of U2, nested; A0 is the longest. Free-standing sites (job.slot): A1 double-sided ("both", pitch 0.5),
          A2 on a straight too short for its need at amp 0.5 (the amplitude is raised), A3 (in the group in
          variant "short" only) on a straight far too short: drawn what fits, the rest reported missing.
  ref     (variant "ref") a reference group: A0 A1 within -16 .. -12.5 mm of the sum A3 + A2 (the reference in two pieces,
          as a clock split by a series resistor). The reference grows first by 30.1284 + 12.5 + 0.3 - 38.6068 = 4.3216, on
          A3's site (written first: 2 humps, 3.105) and the rest on A2's; then A1 is aimed at the reached sum - 16 + 0.3.
          With BENCH_TUNE_OBSTACLES (a copy of the board with a GND track on L1 north of A2's site, check.py) the board's
          other copper is an obstacle as well (TUNE_OBSTACLES): A2's block slides east past that track.
  humps   (variant "humps", fast check only) as "tune", D10's site with humps=1: one hump of height amp (0.5, adds 0.7425)
          instead of the bump, 0.5003 more than D10 needs (a NOTE), still inside the lane's window.
BUSROUTE_BENCH selects the variant: tune (default), short, plain (no TUNING: the natural lengths), ref, humps.
"""
import os
from Tools.KiCadDesignTools.routing.busroute import Bundle

VARIANT = os.environ.get("BUSROUTE_BENCH", "tune")
BOARD = "bench.kicad_pcb"
ORIGIN = (100, 100)
GROUP = "tune"
LANE1 = ["FMC_D8", "FMC_D9", "FMC_D10", "FMC_D11", "FMC_D12"]
HAND = ["FMC_A0", "FMC_A1", "FMC_A2", "FMC_A3"]
GROUPS = {"lane1": LANE1, "hand": HAND}
VIEWS = [("tune", 7.0, 0.0, 33.0, 30.0, 40)]
DRC_IGNORE = {"isolated_copper": "the benchmark's ground pours have no pad of their net"}
TUNE_OBSTACLES = os.environ.get("BENCH_TUNE_OBSTACLES") or None

if VARIANT != "plain":
    TUNING = {
        "groups": {"lane1": {"nets": LANE1, "spread": 4.2},
                   "hand": {"nets": HAND if VARIANT == "short" else HAND[:3], "spread": 2.0}},
        "margin": 0.3, "radius": 0.25, "amp": 0.5, "amp_max": 2.0,
        "pitch": {"default": 0.3, "FMC_A1": 0.5},
        "end": 0.35, "clr": 0.19, "area_gap": 0.127,
    }
if VARIANT == "ref":
    TUNING["groups"]["hand"] = {"nets": ["FMC_A0", "FMC_A1"], "ref": ["FMC_A3", "FMC_A2"], "lo": -16.0, "hi": -12.5}


def routes(job):
    fm = job.fanout("U1").escape({b: "S" for b in ("R9", "R10", "R11", "R12", "R13")})
    fr = job.fanout("U2").escape({"R1": "S", "P1": "S+", "R2": "S", "P2": "S+", "R3": "S"})
    job.refused(fm); job.refused(fr)
    m, r = fm.by_net(), fr.by_net()
    bus = job.bus()
    hand = {"FMC_A0": [("L1", ["U1.A9", (13.65, 2.5), (14.65, 1.5), (29.2, 1.5), (30.2, 2.5), "U2.A9"])],
            "FMC_A1": [("L1", ["U1.A10", (14.3, 3.7), (15.3, 2.7), (28.4, 2.7), (29.4, 3.7), "U2.A8"])],
            "FMC_A2": [("L1", ["U1.A11", (14.95, 4.9), (15.95, 3.9), (27.6, 3.9), (28.6, 4.9), "U2.A7"])],
            "FMC_A3": [("L1", ["U1.A12", (15.6, 6.1), (16.6, 5.1), (24.4, 5.1), (25.4, 6.1), "U2.A3"])]}
    bus.keep(hand)
    lane = Bundle("lane1", LANE1, "L1", anchor="FMC_D8",
                  path=[(16.25, 18.0), (16.25, 23.9), (16.85, 24.5), (23.2, 24.5), (23.8, 23.9), (23.8, 23.4)],
                  pitch=0.9, gaps={0: 0.65, 1: 0.8, 2: [0.9, 0.9, 0.25, 0.9], 3: 0.6, 4: 0.4})
    lane.slot("FMC_D8", 2, 1.2, 5.0, side="L")                  # all humps north, the three blocks start on one line:
    lane.slot("FMC_D9", 2, 1.2, 2.8, side="L")                  # D9's humps fit under D8's (0.9 lane pitch)
    lane.slot("FMC_D10", 2, 3.8, 2.2, side="L",                 # D10 needs less than one hump: a bump, where D11 runs 0.25 below
              humps=1 if VARIANT == "humps" else None)     # (variant humps: one whole hump all the same)
    bus.add(lane, start={n: m[n] for n in LANE1}, end={n: r[n].reversed() for n in LANE1})
    if VARIANT == "ref":                                    # the reference's pieces in this order: A3's site first
        job.slot("FMC_A3", "L1", (17.6, 5.1), (20.6, 5.1), side="L")
    job.slot("FMC_A1", "L1", (16.0, 2.7), (19.6, 2.7), side="both")
    job.slot("FMC_A2", "L1", (21.0, 3.9), (25.4, 3.9), side="L")
    if VARIANT != "ref":
        job.slot("FMC_A3", "L1", (17.6, 5.1), (20.6, 5.1), side="L")
    return bus.routes()
