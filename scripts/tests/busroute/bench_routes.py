"""Routes of the busroute benchmark board (copied next to the board by check.py; see check.py for the board).

Twelve nets between U1 (UFBGA 0.65 mm, centre 13, 12) and U2 (BGA-90 0.8 mm, centre 27, 15.9):
  trunk   L1, six lanes: FMC_D0..D3 leave U1 east (ring 0 straight, ring 1 through a channel), cross the 3 mm
          strip on a diagonal (pitch 0.325 -> 0.2298 -> 0.4: per-leg gaps, two corners) and enter U2 on its
          west side (column 1 straight, column 2 through a channel)
  south   L1, FMC_D4 / D5 leave U1 south, turn east below it and JOIN the trunk on its diagonal
  under   L4, FMC_D6..D9: ring 2 and ring 3 balls, dog-bone vias, 0.65 -> 0.4 pitch, ending in a staggered
          field of 0.30 / 0.15 vias inside the SDRAM rule area with four ground stitching vias beside it
  top     L1, the same four nets from their vias into the U2 balls
  hand    FMC_D10 (L1 only) and FMC_D11 (L1 - L6 - L1, a 0.45 / 0.20 via outside and a 0.30 / 0.15 via inside
          a rule area) written as plain coordinate lists
BUSROUTE_BENCH selects a variant: ok; hand / main10 (the two halves as separate groups); and the negative
cases order, pitch, viapad, channel.
"""
import os
from busroute import Bundle

VARIANT = os.environ.get("BUSROUTE_BENCH", "ok")
BOARD = "bench.kicad_pcb"
ORIGIN = (100, 100)
GROUP = "hand" if VARIANT == "hand" else "main"
REF = ["FMC_D0"]
GROUPS = {"trunk": ["FMC_D%d" % i for i in range(6)], "under": ["FMC_D%d" % i for i in range(6, 10)], "hand": ["FMC_D10", "FMC_D11"]}
VIA_TARGET = 2
VIEWS = [("bus", 14.5, 9.5, 26.0, 20.5, 90)]
DRC_IGNORE = {}


def routes(job):
    hand = {"FMC_D10": [("L1", ["U1.H15", (19.5, 12.0), (21.2, 10.3), "U2.A1"])],
            "FMC_D11": [("L1", ["U1.G15", (19.4, 11.35)]), ("via", (19.4, 11.35)),
                        ("L6", [(19.4, 11.35), (20.5, 11.35), (20.65, 11.5), (23.0, 11.5)]), ("via", (23.0, 11.5)),
                        ("L1", [(23.0, 11.5), (24.2, 11.5), "U2.B2"])]}
    if VARIANT == "viapad":                                 # the second via of D11 lands on ball B1
        hand["FMC_D11"][2:] = [("L6", [(19.4, 11.35), (23.55, 11.35), (23.8, 11.1)]), ("via", (23.8, 11.1)), ("L1", [(23.8, 11.1), "U2.B2"])]
    if VARIANT == "hand":
        return hand
    req = {"N15": "E", "N14": "E+:L1" if VARIANT == "channel" else "E+", "P15": "E", "P14": "E-:L1" if VARIANT == "channel" else "E+", "R13": "S", "R12": "S",
           "L12": "E", "M12": "E", "L13": "E", "M13": "E"}
    fm = job.fanout("U1").escape(req, inner="L4")
    fr = job.fanout("U2").escape({"J1": "W", "J2": "W+", "K1": "W", "K2": "W+", "M1": "W", "M2": "W+"})
    job.refused(fm); job.refused(fr)
    job.notes += [fm.text(), fr.text()]
    m, r = fm.by_net(), fr.by_net()
    bus = job.bus()
    if VARIANT != "main10":
        bus.keep(hand)

    south = Bundle("south", ["FMC_D4", "FMC_D5"], "L1", anchor="FMC_D4",
                   path=[(16.25, 18.0), (16.25, 18.5), (16.55, 18.8), (21.0, 18.8)], pitch=0.3, gaps={0: 0.65, 1: 0.2298})
    bus.add(south, start={n: m[n] for n in south.nets if n in m})

    order = ["FMC_D0", "FMC_D1", "FMC_D2", "FMC_D3", "FMC_D4", "FMC_D5"]
    if VARIANT == "order":
        order[1], order[2] = order[2], order[1]
    trunk = Bundle("trunk", order, "L1", anchor="FMC_D0",
                   path=[(19.0, 15.25), (19.2, 15.25), (20.65, 16.7), (22.0, 16.7)],
                   pitch=0.2 if VARIANT == "pitch" else 0.2298, gaps={0: 0.325, 2: [0.4, 0.4, 0.4, 1.2, 0.4]},
                   span={"FMC_D4": (1, 2), "FMC_D5": (1, 2)})
    bus.add(trunk, start={n: m[n] for n in order if n in m and n not in south.nets}, end={n: r[n].reversed() for n in order})

    under = Bundle("under", ["FMC_D6", "FMC_D7", "FMC_D8", "FMC_D9"], "L4", anchor="FMC_D6",
                   path=[(19.0, 13.3), (19.6, 13.3), (20.6, 14.3), (23.0, 14.3)], pitch=0.4 / 2 ** 0.5, gaps={0: 0.65, 2: 0.4})
    bus.add(under, start={n: m[n] for n in under.nets})
    field = bus.vias(under, at=1.7, gnd="GND")              # two rows 0.7 mm apart, chosen by the tool
    job.notes.append("via field: %d rows, step %.2f, via %g / %g, ground vias %s" % (field.rows, field.step, field.size[0], field.size[1], field.gnd))
    top = Bundle("top", under.nets, "L1", anchor="FMC_D6", path=[(22.3, 14.3), (24.0, 14.3)], pitch=0.4)
    bus.add(top, end={"FMC_D6": "U2.F1", "FMC_D7": [(24.2, 14.7), "U2.F2"], "FMC_D8": "U2.G1", "FMC_D9": [(24.2, 15.5), "U2.G2"]})
    return bus.routes()
