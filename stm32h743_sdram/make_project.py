"""Create the KiCad project files of the STM32H743 + SDRAM board from the common template (RUL-1).

    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\make_project.py            writes .kicad_pro; .kicad_pcb only if missing
    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\make_project.py --new-pcb  also replaces the board with an empty one

Profile C (docs/rule-profiles/C-bga-065.md) has no template of its own, so this starts from
templates/common/ and applies the profile C values and the board's own data:

  .kicad_pro   board-level floors, net classes, and the net-class membership taken from pins.csv
  .kicad_pcb   empty six-layer board with the JLC06161H-3313E stackup (true thicknesses: KiCad's
               length rules add the height of every via, so a default stackup gives wrong lengths)

The rule file stm32h743_sdram.kicad_dru is written by hand and is not touched here.
The .kicad_pro is always regenerated (edit this script, not the file; KiCad also rewrites the file
when the user closes the project, RUL-4). The board is never overwritten without --new-pcb (PROC-13).
"""
import csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NAME = "stm32h743_sdram"
TEMPLATE = os.path.join(ROOT, "templates", "common", "common")

# ---- board-level floors (.kicad_pro "rules"). These are the absolute minimums anywhere on the board,
# i.e. the values inside the BGA rule areas; the stricter outside values are in the .kicad_dru.
FLOORS = {
    "min_clearance": 0.09,               # inside rule areas; outside 0.127 comes from the net classes
    "min_track_width": 0.09,             # inside rule areas; outside 0.1016 (rule signal_width)
    "min_via_diameter": 0.3,             # inside rule areas; outside 0.45 (rule via_size)
    "min_through_hole_diameter": 0.15,   # inside rule areas; outside 0.2 (rule via_size)
    "min_via_annular_width": 0.075,      # (0.30 - 0.15) / 2
    "min_hole_clearance": 0.2,           # JLC: via hole to copper 0.2; plated pad holes 0.3 (rule pth_hole_clearance)
    "min_hole_to_hole": 0.254,           # project value (AD HoleToHoleClearance); JLC via 0.2
    "min_copper_edge_clearance": 0.254,
    "min_text_height": 1.0,
    "min_text_thickness": 0.15,
    "solder_mask_to_copper_clearance": 0.0,
    "use_height_for_length_calcs": True,  # off = via heights are 0 and via_count rules silently stop working
}

# ---- net classes. name: (track width, via diameter, via drill, priority).  Clearance is 0.127 everywhere.
# Bus classes exist so that length / via-count rules can address a whole bus; their width outside the
# rule areas is the general minimum, as in the routing prototype (issue 21).
CLASSES = {
    "Default": (0.2032, 0.45, 0.2, 2147483647),
    "PWR":     (0.3048, 0.6, 0.3, 0),
    "XTAL":    (0.254, 0.45, 0.2, 1),
    "SDRAM":   (0.1016, 0.45, 0.2, 10),
    "QSPI":    (0.1016, 0.45, 0.2, 11),
    "SDMMC":   (0.1016, 0.45, 0.2, 12),
    "LTDC":    (0.1016, 0.45, 0.2, 13),
    "RMII":    (0.1016, 0.45, 0.2, 14),
    "ETH100":  (None, 0.45, 0.2, 15),     # 100 ohm pair PHY - RJ45, width / gap from ETH_PAIR
}
ETH_PAIR = (0.11, 0.15)   # width, gap in mm on L1: 99.6 ohm calculated with scripts/impedance.py, not confirmed on the fab calculator

# pins.csv group -> net class. Net names are the pins.csv signal names (global labels, no '/' prefix).
GROUP_CLASS = {"SDRAM_DATA": "SDRAM", "SDRAM_ADDR": "SDRAM", "SDRAM_CLK": "SDRAM", "QSPI": "QSPI",
               "SDMMC": "SDMMC", "LTDC": "LTDC", "HSE": "XTAL", "LSE": "XTAL"}
RMII_NETS = ["RMII_REF_CLK", "RMII_CRS_DV", "RMII_RXD0", "RMII_RXD1", "RMII_TX_EN", "RMII_TXD0", "RMII_TXD1"]
# Nets that are not MCU pins. FMC_SDCLK_R is the SDRAM side of the SDCLK series resistor.
EXTRA = [("SDRAM", "FMC_SDCLK_R"), ("XTAL", "PHY_XI"), ("XTAL", "PHY_XO"), ("XTAL", "PHY_XO_R"),
         ("ETH100", "ETH_TX_P"), ("ETH100", "ETH_TX_N"), ("ETH100", "ETH_RX_P"), ("ETH100", "ETH_RX_N"),
         # copper-type and short-and-wide nets of SPEC section 5 that the template patterns do not catch
         ("PWR", "SW_*"), ("PWR", "LED_A"), ("PWR", "VCAP*"), ("PWR", "VDDCR")]

# ---- JLC06161H-3313E, values read 2026-11-15 from jlcpcb.com/impedance (research note, issue 5).
# (kind, name, thickness mm, material, Er). L3-L4 is one dielectric made of three sublayers.
STACKUP = [
    ("mask", "F.Mask", 0.01524, "Solder mask", 3.8),
    ("cu", "F.Cu", 0.035), ("di", "prepreg", [(0.0994, "3313", 4.1)]),
    ("cu", "In1.Cu", 0.0152), ("di", "core", [(0.1, "Core", 4.6)]),
    ("cu", "In2.Cu", 0.0152), ("di", "prepreg", [(0.2104, "7628", 4.4), (0.7, "Core (no copper)", 4.6), (0.2104, "7628", 4.4)]),
    ("cu", "In3.Cu", 0.0152), ("di", "core", [(0.1, "Core", 4.6)]),
    ("cu", "In4.Cu", 0.0152), ("di", "prepreg", [(0.0994, "3313", 4.1)]),
    ("cu", "B.Cu", 0.035),
    ("mask", "B.Mask", 0.01524, "Solder mask", 3.8),
]
LAYERS = [(0, "F.Cu", "signal", None), (4, "In1.Cu", "power", "L2_GND"), (6, "In2.Cu", "power", "L3_PWR"),
          (8, "In3.Cu", "signal", "L4_SIG"), (10, "In4.Cu", "power", "L5_GND"), (2, "B.Cu", "signal", None)]


def board_thickness():
    t = 0.0
    for row in STACKUP:
        if row[0] == "cu":
            t += row[2]
        elif row[0] == "di":
            t += sum(s[0] for s in row[2])
    return round(t, 4)


def via_height(a, b):
    """Height KiCad adds to a net's length for a via between copper layers a and b (BOARD_STACKUP::GetLayerDistance):
    everything strictly between, plus the full thickness of an outer end layer and half of an inner end layer."""
    names = [r[1] if r[0] == "cu" else None for r in STACKUP]
    i, j = sorted((names.index(a), names.index(b)))
    h = 0.0
    for k in range(i, j + 1):
        r = STACKUP[k]
        if r[0] == "di":
            h += sum(s[0] for s in r[2])
        elif r[0] == "cu":
            end = k in (i, j)
            h += r[2] / 2 if end and r[1] not in ("F.Cu", "B.Cu") else r[2]
    return round(h, 4)


def stackup_text():
    out = ['\t\t(stackup', '\t\t\t(layer "F.SilkS" (type "Top Silk Screen"))', '\t\t\t(layer "F.Paste" (type "Top Solder Paste"))']
    n = 0
    for r in STACKUP:
        if r[0] == "mask":
            side = "Top" if r[1].startswith("F") else "Bottom"
            out.append('\t\t\t(layer "%s" (type "%s Solder Mask") (thickness %g) (material "%s") (epsilon_r %g) (loss_tangent 0))'
                       % (r[1], side, r[2], r[3], r[4]))
        elif r[0] == "cu":
            out.append('\t\t\t(layer "%s" (type "copper") (thickness %g))' % (r[1], r[2]))
        else:
            n += 1
            subs = " addsublayer ".join('(thickness %g) (material "%s") (epsilon_r %g) (loss_tangent 0.02)' % s for s in r[2])
            out.append('\t\t\t(layer "dielectric %d" (type "%s") %s)' % (n, r[1], subs))
    out += ['\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))', '\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen"))',
            '\t\t\t(copper_finish "ENIG")', '\t\t\t(dielectric_constraints yes)', '\t\t)']
    return "\n".join(out) + "\n"


def make_pcb(path):
    s = open(TEMPLATE + ".kicad_pcb", encoding="utf-8").read()
    s = re.sub(r"\(thickness [\d.]+\)", "(thickness %g)" % board_thickness(), s, count=1)
    cu = "".join('\t\t(%d "%s" %s%s)\n' % (i, n, t, ' "%s"' % u if u else "") for i, n, t, u in LAYERS)
    s, k = re.subn(r'\t\t\(0 "F\.Cu" signal\)\n\t\t\(2 "B\.Cu" signal\)\n', lambda m: cu, s, count=1)
    assert k == 1, "template layer table not found"
    assert "(stackup" not in s
    s, k = re.subn(r"\t\(setup\n", lambda m: "\t(setup\n" + stackup_text(), s, count=1)
    assert k == 1
    # pad_to_mask_clearance stays at the template value (0.1016); the two BGAs get 0 on the footprint when placed.
    open(path, "w", encoding="utf-8", newline="\n").write(s)


def net_patterns():
    pats = []
    for row in csv.DictReader(open(os.path.join(HERE, "pins.csv"), encoding="utf-8")):
        cls = GROUP_CLASS.get(row["group"])
        if cls and row["signal"]:
            pats.append((cls, row["signal"]))
    pats += [("RMII", n) for n in RMII_NETS] + EXTRA
    return pats


def make_pro(path):
    d = json.load(open(TEMPLATE + ".kicad_pro", encoding="utf-8"))
    ds = d["board"]["design_settings"]
    for k, v in FLOORS.items():
        assert k in ds["rules"], k
        ds["rules"][k] = v
    ds["track_widths"] = [0.0, 0.09, 0.1016, 0.1524, 0.2032, 0.254, 0.3048, 0.508, 0.8128, 1.27, 2.54]
    ds["via_dimensions"] = [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.3, "drill": 0.15},
                            {"diameter": 0.45, "drill": 0.2}, {"diameter": 0.6, "drill": 0.3}]
    ds["diff_pair_dimensions"] = [{"gap": 0.0, "via_gap": 0.0, "width": 0.0},
                                  {"gap": ETH_PAIR[1], "via_gap": 0.25, "width": ETH_PAIR[0]}]
    ns = d["net_settings"]
    base = next(c for c in ns["classes"] if c["name"] == "Default")
    classes = []
    for name, (w, vd, vh, prio) in CLASSES.items():
        c = dict(base, name=name, via_diameter=vd, via_drill=vh, priority=prio, clearance=0.127)
        if name == "ETH100":
            c.update(track_width=ETH_PAIR[0], diff_pair_width=ETH_PAIR[0], diff_pair_gap=ETH_PAIR[1])
        else:
            c["track_width"] = w
        classes.append(c)
    ns["classes"] = classes
    # Template patterns first (PWR and XTAL by name), then this board's. Wildcards: only '*' works.
    pats = [p for p in ns["netclass_patterns"]]
    have = {(p["netclass"], p["pattern"]) for p in pats}
    for cls, pat in net_patterns():
        if (cls, pat) not in have:
            pats.append({"netclass": cls, "pattern": pat}); have.add((cls, pat))
    ns["netclass_patterns"] = pats
    d["meta"]["filename"] = NAME + ".kicad_pro"
    d["pcbnew"]["last_paths"]["step"] = ""
    json.dump(d, open(path, "w", encoding="utf-8", newline="\n"), indent=2, ensure_ascii=False)
    return len(pats)


KICAD_FP = os.path.join("D:" + os.sep, "KiCad", "share", "kicad", "footprints")
SDRAM_FP = "BGA-90_8.0x13.0mm_Layout2x3x15_P0.8mm"


def make_footprints():
    """Project footprint library h743.pretty: the stock 90-ball BGA with 0.33 mm pads instead of 0.40
    (SPEC 2.1; 0.33 is Micron's land for the same package, ISSI gives no land pattern)."""
    lib = os.path.join(HERE, "h743.pretty")
    os.makedirs(lib, exist_ok=True)
    s = open(os.path.join(KICAD_FP, "Package_BGA.pretty", SDRAM_FP + ".kicad_mod"), encoding="utf-8").read()
    new = SDRAM_FP + "_Pad0.33mm"
    assert s.count("(size 0.4 0.4)") == 90, "stock footprint changed"
    s = s.replace("(size 0.4 0.4)", "(size 0.33 0.33)").replace('(footprint "%s"' % SDRAM_FP, '(footprint "%s"' % new, 1)
    assert '(footprint "%s"' % new in s
    open(os.path.join(lib, new + ".kicad_mod"), "w", encoding="utf-8", newline="\n").write(s)
    open(os.path.join(HERE, "fp-lib-table"), "w", encoding="utf-8", newline="\n").write(
        '(fp_lib_table\n\t(version 7)\n\t(lib (name "h743") (type "KiCad") (uri "${KIPRJMOD}/h743.pretty") '
        '(options "") (descr "Project footprints"))\n)\n')
    return new


def main(argv):
    stem = os.path.join(HERE, NAME)
    if any(f.endswith(".lck") for f in os.listdir(HERE)):
        sys.exit("KiCad has this project open (lock file present): close it first, it would overwrite the .kicad_pro")
    n = make_pro(stem + ".kicad_pro")
    print("wrote %s.kicad_pro: %d net classes, %d patterns" % (NAME, len(CLASSES), n))
    if "--new-pcb" in argv or not os.path.exists(stem + ".kicad_pcb"):
        make_pcb(stem + ".kicad_pcb")
        print("wrote %s.kicad_pcb: empty, 6 copper layers, stackup %.4f mm" % (NAME, board_thickness()))
    else:
        print("kept the existing %s.kicad_pcb (pass --new-pcb to replace it with an empty board)" % NAME)
    print("wrote h743.pretty/%s.kicad_mod and fp-lib-table" % make_footprints())
    print("via heights counted in net lengths: L1-L4 %.4f, L1-L6 %.4f, L4-L6 %.4f mm"
          % (via_height("F.Cu", "In3.Cu"), via_height("F.Cu", "B.Cu"), via_height("In3.Cu", "B.Cu")))


if __name__ == "__main__":
    main(sys.argv[1:])
