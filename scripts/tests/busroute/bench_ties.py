"""A shared group on the busroute benchmark board (check.py copies it next to a board that already holds the main
group): two ground chains for one net, one with its own track width, and a free via. GND is also on the main
group's via field (its four stitching vias); a shared group must leave those and replace only its own copper.
The last chain is a 45 degree piece on the 0.1 um grid but off the 0.001 mm one (track_shape.py must not call it off-grid).
"""
BOARD = "bench.kicad_pcb"
ORIGIN = (100, 100)
GROUP = "ties"
SHARED = True
OPEN_ENDS = True
YIELD_NETS = ["GND"]
DRC_IGNORE = {"isolated_copper": "the benchmark's ground pours have no pad of their net",
              "via_dangling": "the ties end in the open on this synthetic board"}


def routes(job):
    job.stitch.append(("GND", (6.0, 26.0)))
    return {"GND": [[("L1", [(3.0, 25.0), (4.0, 25.0)], 0.25), ("via", (4.0, 25.0), (0.45, 0.2))],
                    [("L6", [(8.0, 25.0), (8.0, 26.0), (8.5, 26.5)])],
                    [("L1", [(10.0005, 25.0), (10.1005, 25.1)])]]}      # 45 degrees off the 0.001 mm grid
