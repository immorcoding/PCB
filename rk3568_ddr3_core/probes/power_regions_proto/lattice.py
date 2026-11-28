"""PROTOTYPE (issue 52): print the via lattice of the SoC with the rail of each supply via.
Site index = coordinate / 0.65 (the ball-gap points). '.' ground, 's' signal via (ring 3 inwards)."""
import collections, sys
import model as M

M.load_rails()
balls = M.soc_balls()
c = collections.Counter(n for _, _, _, k, n in balls if k == "pwr")
BIG = ["VDD_CPU", "VDD_LOGIC", "VDD_GPU", "VDD_NPU", "VCC_DDR"]
S = "CLGNDabcdefghijklmnopqrstuvw"
sym = {}
for n in BIG + sorted(set(c) - set(BIG)):
    sym[n] = S[len(sym)]


def lattice():
    grid = {}
    for x, y, k, n, b in M.soc_vias():
        key = (round(y / 0.65), round(x / 0.65))
        assert abs(y / 0.65 - key[0]) < 0.01 and abs(x / 0.65 - key[1]) < 0.01, (x, y)
        assert key not in grid, (key, b)
        grid[key] = sym[n] if k == "pwr" else ("." if k == "gnd" else "s")
    return grid


if __name__ == "__main__":
    print(len(c), "rails,", sum(c.values()), "balls")
    print(collections.Counter(k for _, _, k, _, _ in M.soc_vias()))
    print(M.chips())
    g = lattice()
    lo, hi = (-14, 15) if "all" in sys.argv else (-9, 11)
    print("    " + "".join(f"{j:3d}" for j in range(lo, hi)))
    for i in range(lo, hi):
        print(f"{i:3d} " + "".join("  " + g.get((i, j), " ") for j in range(lo, hi)))
    for n, s in sym.items():
        print(s, n, c[n])
