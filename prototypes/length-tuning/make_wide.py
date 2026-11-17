"""PROTOTYPE (throwaway, issue 15): the same nine nets with the packages 8 mm apart instead of 5 mm.

    D:\KiCad\bin\python.exe make_wide.py      -> out/6_gap8_base/

Extra variant, NOT what issue 12 agreed (5 mm): it shows what more room buys. The SDRAM moves 3 mm
east (rule area x 25..35), the strip between the two rule areas is 6 mm instead of 3 mm, and the three
L1 nets that go down that strip are spread 1.8 mm apart instead of 0.5 / 1.1 mm.
One more deviation, on purpose: where a net leaves a rule area on a long straight, the width changes
0.3 mm outside the area ON the straight (points at x = 19.3, x = 24.7 and, south of the MCU, y = 18.3). Profile C says "at the first
bend outside the area"; with that, 3 to 5 mm of 0.09 track would lie outside the areas here and the
straight could not carry a serpentine (meander.py only uses 0.1016 segments).
"""
import os
import make_board as mb

L1, L4 = mb.L1, mb.L4
OUT = os.path.join(mb.HERE, "out", "6_gap8_base")
mb.RAM = (30.0, 15.9)
mb.AREAS["BGA_SDRAM"] = (25.0, 8.4, 35.0, 23.4)
mb.GND_TAPS["U2"] = (29.2, 18.3)
ROUTES = {
    "/FMC_SDCLK": [(L1, ["U1", (17.225, 12.325), (19.3, 12.325), (23.9, 12.325), (24.4, 12.825), (24.4, 16.2), (24.9, 16.7), "U2"])],
    "/FMC_D15": [(L1, ["U1", (19.3, 15.25), (22.1, 15.25), (22.6, 15.75), (22.6, 19.0), (23.1, 19.5), (24.7, 19.5), (27.2, 19.5), "U2"])],
    "/FMC_D13": [(L1, ["U1", (19.3, 15.9), (20.3, 15.9), (20.8, 16.4), (20.8, 19.8), (21.3, 20.3), (24.7, 20.3), (28.0, 20.3), "U2"])],
    "/FMC_D12": [(L1, ["U1", (14.95, 18.3), (14.95, 18.7), (15.45, 19.2), (18.7, 19.2), (20.2, 20.7), (24.7, 20.7), "U2"])],
    "/FMC_D8": [(L1, ["U1", (14.625, 16.225), (14.625, 18.3), (14.625, 19.5), (15.125, 20.0), (19.0, 20.0), (20.1, 21.1), (24.7, 21.1),
                      (27.2, 21.1), "U2"])],
    "/FMC_D9": [(L1, ["U1", (14.3, 18.3), (14.3, 20.3), (14.8, 20.8), (19.3, 20.8), (20.0, 21.5), (24.7, 21.5), "U2"])],
    "/FMC_D10": [(L1, ["U1", (15.275, 15.575)]), ("via", (15.275, 15.575)),
                 (L4, [(15.275, 15.575), (15.6, 15.25), (19.1, 15.25), (21.75, 17.9), (24.7, 17.9), (25.6, 17.9)]),
                 ("via", (25.6, 17.9)), (L1, [(25.6, 17.9), (27.2, 17.9), "U2"])],
    "/FMC_D11": [(L1, ["U1", (15.275, 16.225)]), ("via", (15.275, 16.225)),
                 (L4, [(15.275, 16.225), (15.6, 15.9), (19.1, 15.9), (21.9, 18.7), (24.7, 18.7), (25.6, 18.7)]),
                 ("via", (25.6, 18.7)), (L1, [(25.6, 18.7), (27.2, 18.7), "U2"])],
    "/FMC_D14": [(L1, ["U1", (17.225, 16.225)]), ("via", (17.225, 16.225)),
                 (L4, [(17.225, 16.225), (17.55, 16.55), (19.1, 16.55), (21.65, 19.1), (24.7, 19.1), (27.6, 19.1), (28.0, 19.5)]),
                 ("via", (28.0, 19.5)), (L1, [(28.0, 19.5), "U2"])],
}

if __name__ == "__main__":
    mb.build(OUT, ROUTES)
    print("wrote", os.path.join(OUT, mb.NAME + ".kicad_pcb"))
