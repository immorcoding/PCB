"""Obstacles the fast check must see (copied next to the benchmark board by check.py, which adds part X1 there):
X1 has two through-hole pads that share the number SH (shield tabs) and an F.Cu keep-out inside the footprint
(a "shield contact area"). FMC_D10's hand route of bench_routes.py passes over the first SH pad (the one
Board.pads does not keep under "X1.SH") and through the keep-out: the fast build must report both.
"""
BOARD = "bench.kicad_pcb"
ORIGIN = (100, 100)
GROUP = "obstacles"


def routes(job):
    return {"FMC_D10": [("L1", ["U1.H15", (19.5, 12.0), (21.2, 10.3), "U2.A1"])]}
