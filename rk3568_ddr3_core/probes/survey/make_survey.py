"""One-off (probe): put U1 = the RK3568 BGA-636 on the survey board and give every ball its net.

    D:\\KiCad\\bin\\python.exe -m rk3568_ddr3_core.probes.survey.make_survey      (from the repository root)

Nets from rk3568_ddr3_core/lib/rk3568_pins.json:
  type G / AG                 -> GND
  type PI / API               -> the name without its trailing _<n> (VDD_CPU_3 -> VDD_CPU)
  type "" (empty)             -> the same, when that stripped name is a PI / API supply name (the table leaves the
                                 type of VCCIO5_2, VCCIO6_2, HDMI_TX_AVDD_0V9_2, MULTI_PHY_AVDD_0V9_2,
                                 PCIE30_AVDD_0V9_2 empty); otherwise a signal
  everything else             -> a net of its own named by the full name (a duplicate name gets _<ball>; none in the
                                 table); NC balls none (none in the table)
The part is placed at the board centre afterwards by placement.place (place.toml). Prints the counts.
"""
import collections, json, os, re, sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "..", "lib")
FP_LIB = os.path.join(LIB, "rk3568_ddr3_core.pretty")
FP_NAME = "BGA-636_19x19mm_Layout28x28_P0.65mm"
PCB = os.path.join(HERE, "rk3568_survey.kicad_pcb")


def nets_of(pins):
    supply = {re.sub(r"_\d+$", "", p["name"]) for p in pins if p["type"] in ("PI", "API")}
    count = collections.Counter(p["name"] for p in pins)
    out, kind = {}, {}
    for p in pins:
        t, n = p["type"], p["name"]
        base = re.sub(r"_\d+$", "", n)
        if t in ("G", "AG"):
            out[p["ball"]], kind[p["ball"]] = "GND", "ground"
        elif t in ("PI", "API") or (t == "" and base in supply):
            out[p["ball"]], kind[p["ball"]] = base, "power"
        elif n.upper() == "NC":
            out[p["ball"]], kind[p["ball"]] = None, "nc"
        else:
            out[p["ball"]] = n if count[n] == 1 else "%s_%s" % (n, p["ball"])
            kind[p["ball"]] = "signal"
    return out, kind


def main():
    pins = json.load(open(os.path.join(LIB, "rk3568_pins.json"), encoding="utf-8"))
    net_of, kind = nets_of(pins)
    board = pcbnew.LoadBoard(PCB)
    for fp in list(board.GetFootprints()):
        if fp.GetReference() == "U1":
            board.Remove(fp)
    fp = pcbnew.FootprintLoad(FP_LIB, FP_NAME)
    fp.SetReference("U1")
    fp.SetValue("RK3568")
    board.Add(fp)
    nets = {}
    for name in sorted({n for n in net_of.values() if n}):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni
    done = 0
    for pad in fp.Pads():
        n = net_of.get(pad.GetNumber())
        if n:
            pad.SetNet(nets[n])
            done += 1
    pro = os.path.splitext(PCB)[0] + ".kicad_pro"
    keep = open(pro, "rb").read() if os.path.isfile(pro) else None       # K33: SaveBoard rewrites the project file
    pcbnew.SaveBoard(PCB, board)
    if keep is not None:
        open(pro, "wb").write(keep)
    k = collections.Counter(kind.values())
    print("U1: %d pads, %d with a net; balls: %s; nets: %d (GND 1, supplies %d, signals %d)" % (
        len(list(fp.Pads())), done, dict(k), len(nets),
        len({net_of[b] for b in net_of if kind[b] == "power"}), len({net_of[b] for b in net_of if kind[b] == "signal"})))


if __name__ == "__main__":
    sys.exit(main())
