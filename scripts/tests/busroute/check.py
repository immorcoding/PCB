"""Regression benchmark of scripts/busroute (PROC-15).

    D:\\KiCad\\bin\\python.exe scripts\\tests\\busroute\\check.py [--keep]

Builds a 40 x 30 mm six-layer board in a temp folder from the H743 project's own files (stackup and empty
board from stm32h743_sdram/make_project.py, its .kicad_pro, its .kicad_dru): U1 = the stock
UFBGA-201 0.65 mm footprint, U2 = the project's 90-ball 0.8 mm footprint (0.33 mm pads), one rule area round
each (BGA_MCU, BGA_SDRAM: package + 1 mm), ground pours on L2 and L5. Then routes the twelve nets of
bench_routes.py and expects:

  full build        no finding, DRC clean for the group, the rule canary OK, every net connected pad to pad
                    (pcbnew), the board file equal to the model, geometry length = DRC length within 0.002 mm,
                    the pinned length and via count of every net, the pinned lanes of the fan-out
  again             a second build is byte-identical
  two groups        the ten bundle nets and the two hand nets built as separate groups on one board give
                    the same copper as the single build (a group build does not disturb other nets)
  negative cases    two lanes that must cross (ORDER), a pitch below the clearance (PitchError with the
                    missing 0.0286 mm), a via on a ball pad (VIAPAD), a channel used twice (CHANNEL)

Prints one line, `OK ...` or `FAIL ...`; exit code 0 = pass. --keep leaves the temp folder.
"""
import os, shutil, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", ".."))
ROOT = os.path.dirname(SCRIPTS)
PROJ = os.path.join(ROOT, "stm32h743_sdram")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, PROJ)
import pcbnew                                               # noqa: E402
import make_project                                         # noqa: E402
from busroute import job, Board                             # noqa: E402

OX = OY = 100.0
MCU, RAM = (13.0, 12.0), (27.0, 15.9)
AREAS = {"BGA_MCU": (7.0, 6.0, 19.0, 18.0), "BGA_SDRAM": (22.0, 8.4, 32.0, 23.4)}
PADS = {"FMC_D0": ("N15", "J1"), "FMC_D1": ("N14", "J2"), "FMC_D2": ("P15", "K1"), "FMC_D3": ("P14", "K2"),
        "FMC_D4": ("R13", "M1"), "FMC_D5": ("R12", "M2"), "FMC_D6": ("L12", "F1"), "FMC_D7": ("M12", "F2"),
        "FMC_D8": ("L13", "G1"), "FMC_D9": ("M13", "G2"), "FMC_D10": ("H15", "A1"), "FMC_D11": ("G15", "B2")}
# net: (length mm by geometry, vias). Via heights on this stackup: L1-L4 1.3932, L1-L6 1.6504.
EXPECT = {'FMC_D0': (6.8506, 0), 'FMC_D1': (8.632, 0), 'FMC_D2': (6.9127, 0), 'FMC_D3': (8.6941, 0), 'FMC_D4': (9.7485, 0), 'FMC_D5': (11.3395, 0),
          'FMC_D6': (11.6699, 2), 'FMC_D7': (12.532, 2), 'FMC_D8': (10.8127, 2), 'FMC_D9': (11.6749, 2), 'FMC_D10': (6.9542, 0), 'FMC_D11': (10.5786, 2)}
LANES = """fan-out of U1: 10 leads drawn, 0 refused
  side E on L1, left to right going out (4): FMC_D0[N15 straight]  FMC_D1[N14 channel]  FMC_D2[P15 straight]  FMC_D3[P14 channel]
  side E on L4, left to right going out (4): FMC_D6[L12 via]  FMC_D7[M12 via]  FMC_D8[L13 via]  FMC_D9[M13 via]
  side S on L1, left to right going out (2): FMC_D4[R13 straight]  FMC_D5[R12 straight]
fan-out of U2: 6 leads drawn, 0 refused
  side W on L1, left to right going out (6): FMC_D5[M2 channel]  FMC_D4[M1 straight]  FMC_D3[K2 channel]  FMC_D2[K1 straight]  FMC_D1[J2 channel]  FMC_D0[J1 straight]
via field: 2 rows, step 0.70, via 0.3 / 0.15, ground vias [(22.3, 13.85), (23.0, 13.85), (22.3, 15.95), (23.0, 15.95)]"""
# DRC item types that say nothing about the routes on this synthetic board.
IGNORE = {"lib_footprint_issues": "the two footprints are loaded from library folders, the board has no fp-lib-table",
          "lib_footprint_mismatch": "the BGA pads get solder-mask margin 0 as on the real board, which differs from the library",
          "silk_over_copper": "reference text of the footprints is where the generator put it",
          "silk_overlap": "same", "silk_edge_clearance": "same",
          "isolated_copper": "the two ground pours have no pad of their net on this board (2 items, with and without the stitching vias)"}


def make_board(tmp):
    pcb = os.path.join(tmp, "bench.kicad_pcb")
    make_project.make_pcb(pcb)                              # empty six-layer board with the real stackup
    b = pcbnew.LoadBoard(pcb)
    mm = pcbnew.FromMM
    V = lambda x, y: pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))
    nets = {}

    def net(name):
        if name not in nets:
            nets[name] = pcbnew.NETINFO_ITEM(b, name); b.Add(nets[name])
        return nets[name]
    for a, c in (((0, 0), (40, 0)), ((40, 0), (40, 30)), ((40, 30), (0, 30)), ((0, 30), (0, 0))):
        s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(V(*a)); s.SetEnd(V(*c))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); b.Add(s)
    for name, (x0, y0, x1, y1) in AREAS.items():           # rule areas as stm32h743_sdram/place.py draws them
        z = pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetZoneName(name); z.SetLayerSet(pcbnew.LSET.AllCuMask())
        for f in ("SetDoNotAllowTracks", "SetDoNotAllowVias", "SetDoNotAllowPads", "SetDoNotAllowZoneFills", "SetDoNotAllowFootprints"):
            getattr(z, f)(False)
        ch = pcbnew.SHAPE_LINE_CHAIN()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            ch.Append(mm(OX + x), mm(OY + y))
        ch.SetClosed(True); z.Outline().AddOutline(ch); b.Add(z)
    libs = {"U1": (os.path.join(make_project.KICAD_FP, "Package_BGA.pretty"), "UFBGA-201_10x10mm_Layout15x15_P0.65mm", MCU),
            "U2": (os.path.join(PROJ, "h743.pretty"), make_project.SDRAM_FP + "_Pad0.33mm", RAM)}
    for ref, (lib, name, xy) in libs.items():
        fp = pcbnew.FootprintLoad(lib, name)
        fp.SetReference(ref); fp.SetPosition(V(*xy)); b.Add(fp)
        by = {p.GetNumber(): p for p in fp.Pads()}
        for p in fp.Pads():
            p.SetLocalSolderMaskMargin(0)
        for n, balls in PADS.items():
            by[balls[0 if ref == "U1" else 1]].SetNet(net(n))
    for layer in (pcbnew.In1_Cu, pcbnew.In4_Cu):            # ground planes; filled by the DRC run
        z = pcbnew.ZONE(b); z.SetZoneName("GND_%d" % layer); z.SetLayer(layer); z.SetNet(net("GND"))
        z.SetLocalClearance(mm(0.2)); z.SetMinThickness(mm(0.2)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        ch = pcbnew.SHAPE_LINE_CHAIN()
        for x, y in ((0.5, 0.5), (39.5, 0.5), (39.5, 29.5), (0.5, 29.5)):
            ch.Append(mm(OX + x), mm(OY + y))
        ch.SetClosed(True); z.Outline().AddOutline(ch); b.Add(z)
    pcbnew.SaveBoard(pcb, b)
    make_project.make_pro(os.path.join(tmp, "bench.kicad_pro"))      # after SaveBoard (it writes a default .kicad_pro)
    shutil.copy(os.path.join(PROJ, make_project.NAME + ".kicad_dru"), os.path.join(tmp, "bench.kicad_dru"))
    shutil.copy(os.path.join(HERE, "bench_routes.py"), os.path.join(tmp, "bench_routes.py"))
    return pcb


def run(folder, variant, out=None, fast=False, pictures=False):
    os.environ["BUSROUTE_BENCH"] = variant
    log = []
    m, code = job.run(os.path.join(folder, "bench_routes.py"), fast=fast, out=out, pictures=pictures, log=log.append)
    return m, code, "\n".join(log)


def copper(pcb):
    b = Board(pcb, (OX, OY))
    return sorted((t[:5] for t in b.tracks), key=repr), sorted(b.vias, key=repr)


def main(argv):
    t0 = time.time()
    tmp = tempfile.mkdtemp(prefix="busroute_")
    fails = []

    def want(ok, text):
        if not ok:
            fails.append(text)
    try:
        pcb = make_board(tmp)
        o1, o2, oa, ob = (os.path.join(tmp, d) for d in ("out1", "out2", "outA", "outB"))
        m, code, log = run(tmp, "ok", o1, pictures=True)
        if "error" in m:
            want(False, "the benchmark routes could not be built: " + m["error"])
            raise StopIteration
        hard = [f for f in m["findings"] if f["hard"]]
        want(not hard, "geometry findings: " + "; ".join("%s %s" % (f["kind"], f["text"]) for f in hard))
        c = m["connectivity"]
        left = {k: v for k, v in c["drc_by_type_group"].items() if k not in IGNORE}
        want(not left, "DRC items on the group: %r %r" % (left, [i for i in c["drc_group_items"] if i["type"] in left][:6]))
        want(c["drc_unconnected_group"] == 0 and c["pcbnew"]["fully_connected"] == 12, "connectivity: %r, DRC unconnected %d" % (c["pcbnew"], c["drc_unconnected_group"]))
        other = {k: v for k, v in c["drc_by_type_board"].items() if k not in IGNORE}
        want(not other and c["drc_unconnected_board"] == 0, "DRC items on the board: %r, unconnected %d" % (other, c["drc_unconnected_board"]))
        want(m["rules"]["canary"] and m["rules"]["canary"]["ok"], "rule canary: %r" % (m["rules"],))
        want(m["written"]["matches_model"], "the board file does not hold the copper the model has")
        d = m["length"]["max_abs_geometry_minus_drc"]
        want(d is not None and d <= 0.002 and not m["length"]["not_measured_by_drc"], "geometry against DRC lengths: max %r, unmeasured %r" % (d, m["length"]["not_measured_by_drc"]))
        got = {n: (v["length"], v["vias"]) for n, v in m["length"]["nets"].items()}
        want(got == EXPECT, "lengths / vias changed:\nEXPECT = %r" % (got,))
        lanes = "\n".join(n for n in m["notes"])
        want(lanes == LANES, "fan-out lanes / via field changed:\nLANES = %r" % (lanes,))
        ts = m["shape"]["track_shape"]
        want(all(ts[k] == 0 for k in ("off-grid", "staircase", "sharp", "tiny")), "track_shape: %r" % ({k: ts[k] for k in ("off-grid", "staircase", "sharp", "crowded", "tiny")},))
        want(m["vias"]["stitching"] == 4 and m["vias"]["max"] == 2 and not m["vias"]["over_limit"], "vias: %r" % (m["vias"],))
        want(code == 0 and m["ok"], "the full build did not pass (exit %d)" % code)
        want(len(m.get("pictures", [])) == 4 and all(os.path.getsize(os.path.join(o1, p)) > 20000 for p in m["pictures"]), "pictures: %r" % (m.get("pictures"),))

        m2, code2, _ = run(tmp, "ok", o2)
        same = open(os.path.join(o1, "bench.kicad_pcb"), "rb").read() == open(os.path.join(o2, "bench.kicad_pcb"), "rb").read()
        want(same and code2 == 0 and m2["length"]["nets"] == m["length"]["nets"], "a second build is not identical")

        ma, codea, _ = run(tmp, "main10", oa)              # the bundle nets alone, then the hand nets onto that board
        shutil.copy(os.path.join(HERE, "bench_routes.py"), os.path.join(oa, "bench_routes.py"))
        mb, codeb, _ = run(oa, "hand", ob)
        want(codea == 0 and codeb == 0, "group builds: exit %d and %d" % (codea, codeb))
        want(copper(os.path.join(ob, "bench.kicad_pcb")) == copper(os.path.join(o1, "bench.kicad_pcb")), "two group builds do not give the copper of the single build")
        want(mb.get("connectivity", {}).get("drc_by_type_board", {}).keys() <= IGNORE.keys() and mb["connectivity"]["drc_unconnected_board"] == 0,
             "DRC after the two group builds: %r" % (mb.get("connectivity", {}).get("drc_by_type_board"),))

        neg = {}
        for v in ("order", "pitch", "viapad", "channel"):
            mv, cv, lv = run(tmp, v, fast=True)
            neg[v] = (mv, cv, lv)
        mv, cv, lv = neg["order"]
        kinds = {f["kind"] for f in mv.get("findings", []) if f["hard"]}
        want(cv == 1 and "ORDER" in kinds and "CROSS" in kinds and "lane FMC_D2 is left of lane FMC_D1 in the bundle but its terminal" in lv, "negative case order: exit %d\n%s" % (cv, lv[-1500:]))
        mv, cv, lv = neg["pitch"]
        want(cv == 2 and mv.get("error_type") == "PitchError" and "PITCH trunk leg 1 (SE): lanes FMC_D0 | FMC_D1 are 0.2000 mm centre to centre, 0.2286 needed" in lv
             and "0.0286 mm missing" in lv, "negative case pitch: exit %d\n%s" % (cv, lv[-1500:]))
        mv, cv, lv = neg["viapad"]
        want(cv == 1 and any(f["kind"] == "VIAPAD" and "is on pad U2.B1" in f["text"] for f in mv.get("findings", [])), "negative case viapad: exit %d\n%s" % (cv, lv[-1500:]))
        mv, cv, lv = neg["channel"]
        want(cv == 2 and any(f["kind"] == "CHANNEL" and "U1.P14" in f["text"] and "already carries FMC_D1 (N14)" in f["text"] for f in mv.get("findings", [])),
             "negative case channel: exit %d\n%s" % (cv, lv[-1500:]))
    except StopIteration:
        pass
    finally:
        keep = "--keep" in argv or fails
        if fails:
            print("FAIL busroute (%d); temp dir kept: %s" % (len(fails), tmp))
            print("\n".join("  " + f for f in fails))
        else:
            print("OK busroute: 12 nets (ring 0-3 fan-out, bundle with corner and per-leg gaps, join, via field), DRC clean, "
                  "geometry = DRC lengths, 2 builds identical, 2 groups = 1 build, 4 negative cases; %.0f s%s" % (time.time() - t0, "; kept " + tmp if keep else ""))
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
