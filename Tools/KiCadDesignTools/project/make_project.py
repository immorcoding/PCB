"""Create a board's KiCad project files from its template and board.toml (RUL-1).

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.project.make_project <board dir>            writes .kicad_pro; .kicad_pcb only if missing
    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.project.make_project <board dir> --new-pcb  also replaces the board with an empty one

Starts from templates/<[board] template>/ and applies the board's data (board.toml):

  .kicad_pro   board-level floors ([project.floors]), track widths, via sizes, differential pairs ([project]), net
               classes ([netclasses]) and the net-class membership ([netclass_patterns], partly from pins.csv)
  .kicad_pcb   empty board with the copper layers of [layers] and the fab stackup [board] stackup
               (Tools/KiCadDesignTools/data/stackups/; true thicknesses: KiCad's length rules add the height of every
               via, so a default stackup gives wrong lengths); on an existing board only the copper rows of the layer
               table are brought to [layers] (core.boardtext.sync_layers)
  <lib>.pretty, fp-lib-table   footprints derived from KiCad's stock ones ([[footprints.derived]])

The rule file <name>.kicad_dru is written by hand and is not touched here.
The .kicad_pro is always regenerated (edit board.toml, not the file; KiCad also rewrites the file when the user closes
the project, RUL-4). The board is never overwritten without --new-pcb (PROC-13).
"""
import csv, json, os, re, sys

from Tools.KiCadDesignTools.core import boardtext, config, paths, stackup


def template(cfg):
    t = cfg.need("board.template")
    return os.path.join(paths.TEMPLATES, t, t)


def layers(cfg):
    """The copper rows of the layer table: (KiCad id, name, type, user name or None), top to bottom."""
    return [(l.id, l.kicad, l.kicad_type, l.user) for l in cfg.layers]


def stackup_text(st):
    out = ['\t\t(stackup', '\t\t\t(layer "F.SilkS" (type "Top Silk Screen"))', '\t\t\t(layer "F.Paste" (type "Top Solder Paste"))']
    n = 0
    for r in st.rows:
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


def sync_layers(cfg, path):
    """Bring the copper rows of an existing board's layer table to [layers]. True when it wrote."""
    return boardtext.sync_layers(path, layers(cfg))


def make_pcb(cfg, path):
    st = stackup.for_board(cfg)
    s = open(template(cfg) + ".kicad_pcb", encoding="utf-8").read()
    s = re.sub(r"\(thickness [\d.]+\)", "(thickness %g)" % st.thickness(), s, count=1)
    cu = boardtext.layer_rows(layers(cfg))
    s, k = re.subn(r'\t\t\(0 "F\.Cu" signal\)\n\t\t\(2 "B\.Cu" signal\)\n', lambda m: cu, s, count=1)
    assert k == 1, "template layer table not found"
    assert "(stackup" not in s
    s, k = re.subn(r"\t\(setup\n", lambda m: "\t(setup\n" + stackup_text(st), s, count=1)
    assert k == 1
    # pad_to_mask_clearance stays at the template value (0.1016); the two BGAs get 0 on the footprint when placed.
    open(path, "w", encoding="utf-8", newline="\n").write(s)


def net_patterns(cfg):
    """[(net class, pattern)]: the pins.csv rows of the listed groups, then [netclass_patterns] nets."""
    np = cfg.get("netclass_patterns", {})
    groups = np.get("groups", {})
    pats = []
    if np.get("pins"):
        for row in csv.DictReader(open(cfg.path(np["pins"]), encoding="utf-8")):
            cls = groups.get(row["group"])
            if cls and row["signal"]:
                pats.append((cls, row["signal"]))
    pats += [tuple(p) for p in np.get("nets", [])]
    return pats


def make_pro(cfg, path):
    d = json.load(open(template(cfg) + ".kicad_pro", encoding="utf-8"))
    ds = d["board"]["design_settings"]
    for k, v in cfg.need("project.floors").items():
        assert k in ds["rules"], k
        ds["rules"][k] = v
    pr = cfg.need("project")
    pairs = pr.get("diff_pairs", {})
    ds["track_widths"] = list(pr["track_widths"])
    ds["via_dimensions"] = [{"diameter": v["diameter"], "drill": v["drill"]} for v in pr["via_dimensions"]]
    ds["diff_pair_dimensions"] = [{"gap": 0.0, "via_gap": 0.0, "width": 0.0}] + \
                                 [{"gap": p["gap"], "via_gap": p["via_gap"], "width": p["width"]} for p in pairs.values()]
    ns = d["net_settings"]
    base = next(c for c in ns["classes"] if c["name"] == "Default")
    classes = []
    for name, nc in cfg.need("netclasses").items():
        c = dict(base, name=name, via_diameter=nc["via_diameter"], via_drill=nc["via_drill"], priority=nc["priority"],
                 clearance=nc["clearance"])
        if nc.get("diff_pair"):
            p = pairs[nc["diff_pair"]]
            c.update(track_width=p["width"], diff_pair_width=p["width"], diff_pair_gap=p["gap"])
        else:
            c["track_width"] = nc["track_width"]
        classes.append(c)
    ns["classes"] = classes
    # Template patterns first (PWR and XTAL by name), then this board's. Wildcards: only '*' works.
    pats = [p for p in ns["netclass_patterns"]]
    have = {(p["netclass"], p["pattern"]) for p in pats}
    for cls, pat in net_patterns(cfg):
        if (cls, pat) not in have:
            pats.append({"netclass": cls, "pattern": pat}); have.add((cls, pat))
    ns["netclass_patterns"] = pats
    d["meta"]["filename"] = cfg.name + ".kicad_pro"
    d["pcbnew"]["last_paths"]["step"] = ""
    json.dump(d, open(path, "w", encoding="utf-8", newline="\n"), indent=2, ensure_ascii=False)
    return len(pats)


def make_footprints(cfg):
    """The board's footprint library <lib>.pretty: footprints derived from KiCad's stock ones ([[footprints.derived]]),
    and fp-lib-table naming it. -> the new footprint names."""
    name = cfg.need("board.lib")
    lib = os.path.join(cfg.dir, name + ".pretty")
    os.makedirs(lib, exist_ok=True)
    made = []
    for fp in cfg.get("footprints.derived", []):
        s = open(os.path.join(paths.KICAD_FP, fp["lib"] + ".pretty", fp["footprint"] + ".kicad_mod"), encoding="utf-8").read()
        a, b = fp["pad_size"]
        old, new = "(size %g %g)" % (a, a), "(size %g %g)" % (b, b)
        assert s.count(old) == fp["pads"], "stock footprint changed"
        s = s.replace(old, new).replace('(footprint "%s"' % fp["footprint"], '(footprint "%s"' % fp["name"], 1)
        assert '(footprint "%s"' % fp["name"] in s
        open(os.path.join(lib, fp["name"] + ".kicad_mod"), "w", encoding="utf-8", newline="\n").write(s)
        made.append(fp["name"])
    open(os.path.join(cfg.dir, "fp-lib-table"), "w", encoding="utf-8", newline="\n").write(
        '(fp_lib_table\n\t(version 7)\n\t(lib (name "%s") (type "KiCad") (uri "${KIPRJMOD}/%s.pretty") '
        '(options "") (descr "Project footprints"))\n)\n' % (name, name))
    return made


def main(argv):
    if not argv or argv[0].startswith("--"):
        print(__doc__)
        return 2
    cfg = config.load(argv[0])
    NAME = cfg.name
    stem = os.path.join(cfg.dir, NAME)
    if any(f.endswith(".lck") for f in os.listdir(cfg.dir)):
        sys.exit("KiCad has this project open (lock file present): close it first, it would overwrite the .kicad_pro")
    st = stackup.for_board(cfg)
    n = make_pro(cfg, stem + ".kicad_pro")
    print("wrote %s.kicad_pro: %d net classes, %d patterns" % (NAME, len(cfg.need("netclasses")), n))
    if "--new-pcb" in argv[1:] or not os.path.exists(stem + ".kicad_pcb"):
        make_pcb(cfg, stem + ".kicad_pcb")
        print("wrote %s.kicad_pcb: empty, %d copper layers, stackup %.4f mm" % (NAME, len(cfg.layers), st.thickness()))
    else:
        print("kept the existing %s.kicad_pcb (pass --new-pcb to replace it with an empty board)%s" % (
            NAME, "; its layer table rewritten to LAYERS" if sync_layers(cfg, stem + ".kicad_pcb") else ""))
    made = make_footprints(cfg)
    print("wrote %s.pretty/%s.kicad_mod and fp-lib-table" % (cfg.need("board.lib"), ", ".join(made)))
    vh = cfg.get("project.via_heights", [])
    if vh:
        print("via heights counted in net lengths: %s mm" % ", ".join(
            "%s-%s %.4f" % (a, b, st.via_height(cfg.kicad(a), cfg.kicad(b))) for a, b in vh))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
