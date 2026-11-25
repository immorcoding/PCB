"""Finishing of a board (stop 8, FIN-1 to FIN-4): fiducials, inner ground pours and their clean-up (finishing.pour),
ground stitching vias (finishing.stitch), silkscreen (finishing.silk), teardrops (finishing.teardrops). Run by the
build driver's finish step after the route step; every sub-step is repeatable (strip first).

    python -m Tools.KiCadDesignTools.finishing.finish <board dir> strip      <board>                remove what finish wrote last time
    python -m Tools.KiCadDesignTools.finishing.finish <board dir> fiducials  <board>                fiducials and their keep-outs
    python -m Tools.KiCadDesignTools.finishing.finish <board dir> pours      <board> <out>          inner ground pours and the pour keep-outs
    python -m Tools.KiCadDesignTools.finishing.finish <board dir> clean      <refilled board> <out> shape|anchor   keep-outs over narrow
                                                                          ground copper and small pieces (shape, before the stitching) or
                                                                          over inner pieces no via holds (anchor, after it); exit 10:
                                                                          some were added, refill again
    python -m Tools.KiCadDesignTools.finishing.finish <board dir> report     <refilled board> <out> <name>   pour pieces, narrow copper,
                                                                          return paths over the power-plane gaps
    python -m Tools.KiCadDesignTools.finishing.finish <board dir> stitch     <refilled board> <out> [--pieces]   ground stitching vias (text write)
    python -m Tools.KiCadDesignTools.finishing.finish <board dir> pieces     <refilled board> <out> <name>   ground pour pieces and their vias
    python -m Tools.KiCadDesignTools.finishing.finish <board dir> silk       <board> <out>          references to Fab, labels, icons, title
    python -m Tools.KiCadDesignTools.finishing.finish <board dir> teardrops  <board>                teardrops outside the skip boxes (text write)

Local mm = board-file mm - [board] origin (x right, y down). The board file is written by text where copper is added
(vias, teardrop settings: no pcbnew save, so no stale fill can pull a via's net, docs/tools.md) and by pcbnew SaveBoard
for footprints and drawings (the project file's bytes are kept: make_project is its source). What finish wrote is
listed in <board>.finish.json, so that `strip` can take exactly that away again.

board.toml [finish] pour_layers (the layers with ground pours), [finish.fiducials] (footprint, keep-out radius, the
fab's minimum edge distance of the keep-out, top / bottom {reference: [x, y]}), [finish.pour], [finish.stitch],
[finish.teardrops]; silk.toml for the silkscreen; [power] ground; the board extent from place.toml [outline].
"""
import json, math, os, re, sys

from Tools.KiCadDesignTools.core import config, paths, uuids


def side_file(path):
    return os.path.splitext(path)[0] + ".finish.json"


def record(path):
    f = side_file(path)
    return json.load(open(f, encoding="utf-8")) if os.path.isfile(f) else {}


def save_record(path, rec):
    json.dump(rec, open(side_file(path), "w", encoding="utf-8"), indent=1)


def save_board(board, path):
    import pcbnew
    pro = os.path.splitext(path)[0] + ".kicad_pro"
    keep = open(pro, "rb").read() if os.path.isfile(pro) else None
    pcbnew.SaveBoard(path, board)
    if keep is not None:
        open(pro, "wb").write(keep)


# ---------------------------------------------------------------------------------------------------- strip
def strip_vias_text(path, origin, ground):
    """Remove the stitching vias of the last run (positions in <board>.finish.json) from the file text."""
    OX, OY = origin
    rec = record(path)
    want = {(round(x + OX, 4), round(y + OY, 4)) for x, y in rec.get("vias", [])}
    if not want:
        return 0
    text = open(path, encoding="utf-8", newline="").read()
    pat = re.compile(r"\t\(via\r?\n\t\t\(at ([-\d.]+) ([-\d.]+)\)\r?\n(?:\t\t[^\n]*\r?\n)*?\t\)\r?\n")
    n = 0
    net = '(net "%s")' % ground

    def drop(m):
        nonlocal n
        if (round(float(m.group(1)), 4), round(float(m.group(2)), 4)) in want and net in m.group(0):
            n += 1
            return ""
        return m.group(0)
    text = pat.sub(drop, text)
    open(path, "w", encoding="utf-8", newline="").write(text)
    rec["vias"] = []
    save_record(path, rec)
    return n


def teardrops_off_text(path):
    """Switch the teardrop setting of every pad and via off again (a refill would otherwise rebuild the teardrops of the
    last run before the stitching and the silkscreen are redone)"""
    text = open(path, encoding="utf-8", newline="").read()
    out, i, n = [], 0, 0
    while True:
        k = text.find("(teardrops", i)
        if k < 0:
            out.append(text[i:])
            break
        d, j = 0, k
        while True:
            c = text[j]
            if c == "(":
                d += 1
            elif c == ")":
                d -= 1
                if d == 0:
                    break
            j += 1
        block = text[k:j + 1]
        if "(enabled yes)" in block:
            block = block.replace("(enabled yes)", "(enabled no)")
            n += 1
        out.append(text[i:k] + block)
        i = j + 1
    open(path, "w", encoding="utf-8", newline="").write("".join(out))
    return n


def strip(cfg, path):
    import pcbnew
    nv = strip_vias_text(path, cfg.origin, cfg.need("power.ground"))
    nt = teardrops_off_text(path)
    b = pcbnew.LoadBoard(path)
    silk = (pcbnew.F_SilkS, pcbnew.B_SilkS)
    old = [d for d in b.GetDrawings() if d.GetLayer() in silk]
    fps = [fp for fp in b.GetFootprints() if fp.GetReference().startswith("FID")]
    # FIN_: the fiducials' and the pours' keep-outs and the inner ground pours (finishing.pour)
    zones = [z for z in b.Zones() if z.GetZoneName().startswith("FIN_") or z.IsTeardropArea()]
    for item in old + fps + zones:
        b.Remove(item)
    save_board(b, path)
    print("strip: %d stitching vias, %d silkscreen drawings, %d fiducials, %d pours / keep-outs / teardrop areas removed; teardrops off on %d pads / vias"
          % (nv, len(old), len(fps), len(zones), nt))


# ---------------------------------------------------------------------------------------------------- fiducials
def fiducials(cfg, path):
    """The fiducials of [finish.fiducials] (top ones on F.Cu, bottom ones flipped to B.Cu), each with a round keep-out
    on its copper layer (no track, via or pour); what already lies in a keep-out is listed, nothing is moved."""
    import pcbnew
    OX, OY = cfg.origin
    fid = cfg.need("finish.fiducials")
    FID_KO = fid["keepout_r"]
    outline = cfg.datafile("place.toml")["outline"]
    W, H = outline["width"], outline["height"]

    def P(x, y):
        return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))
    b = pcbnew.LoadBoard(path)
    nick, name = fid["footprint"].split(":")
    lib = os.path.join(paths.KICAD_FP, nick + ".pretty")
    # a set per assembly side; a board with parts on one side only has no bottom set
    sides = [(r, xy, "F") for r, xy in fid["top"].items()] + [(r, xy, "B") for r, xy in fid.get("bottom", {}).items()]
    for ref, (x, y), side in sides:
        fp = pcbnew.FootprintLoad(lib, name)
        fp.SetReference(ref)
        fp.SetValue("Fiducial")
        fp.SetPosition(P(x, y))
        fp.SetBoardOnly(True)                     # not in the schematic: no parity item
        fp.SetExcludedFromBOM(True)
        fp.SetExcludedFromPosFiles(True)
        uuids.stamp_footprint(fp, "finish:fiducial:%s" % ref)      # the library file has no uuids: pcbnew made random ones
        fp.Reference().SetLayer(pcbnew.F_Fab)
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.5), pcbnew.FromMM(0.5)))
        fp.Reference().SetTextThickness(pcbnew.FromMM(0.08))
        fp.Reference().SetPosition(P(x, y + 1.6))
        b.Add(fp)
        if side == "B":                                   # after Add: flipping a footprint that has no board crashes pcbnew
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        z = pcbnew.ZONE(b); uuids.stamp(z, "finish:keepout:FIN_FID_%s" % ref)
        z.SetIsRuleArea(True); z.SetZoneName("FIN_FID_%s" % ref)
        ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu if side == "F" else pcbnew.B_Cu); z.SetLayerSet(ls)
        z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowZoneFills(True)
        z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
        ch = pcbnew.SHAPE_LINE_CHAIN()
        for k in range(32):
            a = 2 * math.pi * k / 32
            ch.Append(pcbnew.FromMM(OX + x + FID_KO * math.cos(a)), pcbnew.FromMM(OY + y + FID_KO * math.sin(a)))
        ch.SetClosed(True)
        z.Outline().AddOutline(ch)
        b.Add(z)
    # what lies in a keep-out already (F.Cu tracks, vias, pads of other parts, courtyards): listed, nothing is moved
    mm = pcbnew.ToMM
    hits = []
    for ref, (x, y), side in sides:
        cu = pcbnew.F_Cu if side == "F" else pcbnew.B_Cu
        for t in b.GetTracks():
            if t.Type() == pcbnew.PCB_VIA_T:
                p = t.GetPosition()
                if math.hypot(mm(p.x) - OX - x, mm(p.y) - OY - y) < FID_KO + mm(t.GetWidth(pcbnew.F_Cu)) / 2:
                    hits.append("%s: via %s" % (ref, t.GetNetname()))
            elif t.GetLayer() == cu:
                sh = t.GetEffectiveShape(cu)
                if sh.Collide(pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y)), pcbnew.FromMM(FID_KO)):
                    hits.append("%s: %s track %s" % (ref, side, t.GetNetname()))
        for fp in b.GetFootprints():
            if fp.GetReference().startswith("FID"):
                continue
            for p in fp.Pads():
                if p.IsOnLayer(cu) and p.GetEffectiveShape(cu).Collide(
                        pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y)), pcbnew.FromMM(FID_KO)):
                    hits.append("%s: pad %s.%s" % (ref, fp.GetReference(), p.GetNumber()))
        edge = min(x, y, W - x, H - y) - FID_KO
        if edge < fid["edge_min"]:
            hits.append("%s: keep-out %.2f mm from the board edge (JLCPCB: %g)" % (ref, edge, fid["edge_min"]))
    save_board(b, path)
    print("fiducials: %s; in the keep-outs: %s" % (", ".join("%s %s (%.2f, %.2f)" % (r, sd, x, y) for r, (x, y), sd in sides),
                                                  "; ".join(hits) or "nothing"))


# ---------------------------------------------------------------------------------------------------- dispatcher
def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    cfg = config.load(argv[0])
    cmd, a = argv[1], argv[2:]
    if cmd == "strip":
        strip(cfg, a[0])
    elif cmd == "fiducials":
        fiducials(cfg, a[0])
    elif cmd in ("pours", "clean", "report"):
        from Tools.KiCadDesignTools.finishing import pour
        pour.setup(cfg)
        if cmd == "pours":
            pour.pours(a[0], a[1])
        elif cmd == "clean":
            return 10 if pour.clean(a[0], a[1], a[2] if len(a) > 2 else "anchor") else 0
        else:
            pour.report(a[0], a[1], a[2])
    elif cmd in ("stitch", "pieces"):
        from Tools.KiCadDesignTools.finishing import stitch
        stitch.setup(cfg)
        if cmd == "stitch":
            stitch.main(a[0], a[1], pieces_only="--pieces" in argv)
        else:
            stitch.pieces_report(a[0], a[1], a[2])
    elif cmd == "silk":
        from Tools.KiCadDesignTools.finishing import silk
        silk.setup(cfg)
        silk.main(a[0], a[1])
    elif cmd == "teardrops":
        from Tools.KiCadDesignTools.finishing import teardrops
        teardrops.board_teardrops(cfg, a[0])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
