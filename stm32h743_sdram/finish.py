"""Finishing of the STM32H743 + SDRAM board (stop 8, FIN-1 to FIN-4): fiducials, ground stitching vias, silkscreen,
teardrops. Run by `sh stm32h743_sdram/build.sh finish` after route2; every sub-step is repeatable (strip first).

    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\finish.py strip      <board>                remove what finish wrote last time
    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\finish.py fiducials  <board>                three fiducials and their keep-outs
    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\finish.py stitch     <refilled board> <out>  ground stitching vias (text write)
    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\finish.py pieces     <refilled board> <out> <name>   GND pour pieces and their vias
    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\finish.py silk       <board> <out>          references to Fab, labels, icons, title
    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\finish.py teardrops  <board>                teardrops outside the BGA areas (text write)

Local mm = board-file mm - 100 (x right, y down). The board file is written by text where copper is added (vias,
teardrop settings: no pcbnew save, so no stale fill can pull a via's net, docs/tools.md) and by pcbnew SaveBoard for
footprints and drawings (the project file's bytes are kept: make_project.py is its source). What finish wrote is
listed in <board>.finish.json, so that `strip` can take exactly that away again.
"""
import json, math, os, re, subprocess, sys, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
OX, OY = 100.0, 100.0
KICAD_CLI = r"D:\KiCad\bin\kicad-cli.exe"
RES = 20                                  # raster: px per mm (0.05 mm)

# ---------------------------------------------------------------------------------------------------- fiducials
# JLCPCB (https://jlcpcb.com/help/article/how-to-add-edge-rails-fiducials-for-pcb-assembly-order, read 2026-11-23):
# 1 mm bare copper, solder-mask opening twice the copper (2 mm), three to four along the board edges, at least
# 3.35 mm from the board edge including the keep-out. KiCad's Fiducial_1mm_Mask2mm (pad clearance 0.6) plus an F.Cu
# keep-out of 3 mm diameter (no track, via or pour). Centres chosen in free corners of the top side (not under a
# part, not in a routed lane; checked by `fiducials`), keep-out edge >= 3.35 mm from the edge.
FIDUCIALS = {"FID1": (8.8, 14.4), "FID2": (75.5, 67.0), "FID3": (6.0, 64.5)}   # top left, bottom right, bottom left
# the bottom carries parts too (35 SMD, the 0402 decoupling under both BGAs): the same three on the bottom, so that each
# assembly side has its own set (kicad-happy FD-001 on the first run: no fiducials on B.Cu)
FIDUCIALS_B = {"FID4": (8.8, 14.4), "FID5": (75.5, 67.0), "FID6": (6.0, 64.5)}
FID_KO = 1.5                              # keep-out radius


def P(x, y):
    import pcbnew
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


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
def strip_vias_text(path):
    """Remove the stitching vias of the last run (positions in <board>.finish.json) from the file text."""
    rec = record(path)
    want = {(round(x + OX, 4), round(y + OY, 4)) for x, y in rec.get("vias", [])}
    if not want:
        return 0
    text = open(path, encoding="utf-8", newline="").read()
    pat = re.compile(r"\t\(via\r?\n\t\t\(at ([-\d.]+) ([-\d.]+)\)\r?\n(?:\t\t[^\n]*\r?\n)*?\t\)\r?\n")
    n = 0

    def drop(m):
        nonlocal n
        if (round(float(m.group(1)), 4), round(float(m.group(2)), 4)) in want and '(net "GND")' in m.group(0):
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


def strip(path):
    import pcbnew
    nv = strip_vias_text(path)
    nt = teardrops_off_text(path)
    b = pcbnew.LoadBoard(path)
    silk = (pcbnew.F_SilkS, pcbnew.B_SilkS)
    old = [d for d in b.GetDrawings() if d.GetLayer() in silk]
    fps = [fp for fp in b.GetFootprints() if fp.GetReference().startswith("FID")]
    zones = [z for z in b.Zones() if (z.GetIsRuleArea() and z.GetZoneName().startswith("FIN_")) or z.IsTeardropArea()]
    for item in old + fps + zones:
        b.Remove(item)
    save_board(b, path)
    print("strip: %d stitching vias, %d silkscreen drawings, %d fiducials, %d keep-outs / teardrop areas removed; teardrops off on %d pads / vias"
          % (nv, len(old), len(fps), len(zones), nt))


# ---------------------------------------------------------------------------------------------------- fiducials
def fiducials(path):
    import pcbnew
    b = pcbnew.LoadBoard(path)
    lib = r"D:\KiCad\share\kicad\footprints\Fiducial.pretty"
    sides = [(r, xy, "F") for r, xy in FIDUCIALS.items()] + [(r, xy, "B") for r, xy in FIDUCIALS_B.items()]
    for ref, (x, y), side in sides:
        fp = pcbnew.FootprintLoad(lib, "Fiducial_1mm_Mask2mm")
        fp.SetReference(ref)
        fp.SetValue("Fiducial")
        fp.SetPosition(P(x, y))
        fp.SetBoardOnly(True)                     # not in the schematic: no parity item
        fp.SetExcludedFromBOM(True)
        fp.SetExcludedFromPosFiles(True)
        fp.Reference().SetLayer(pcbnew.F_Fab)
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.5), pcbnew.FromMM(0.5)))
        fp.Reference().SetTextThickness(pcbnew.FromMM(0.08))
        fp.Reference().SetPosition(P(x, y + 1.6))
        b.Add(fp)
        if side == "B":                                   # after Add: flipping a footprint that has no board crashes pcbnew
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        z = pcbnew.ZONE(b)
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
        edge = min(x, y, 85.0 - x, 75.0 - y) - FID_KO
        if edge < 3.35:
            hits.append("%s: keep-out %.2f mm from the board edge (JLCPCB: 3.35)" % (ref, edge))
    save_board(b, path)
    print("fiducials: %s; in the keep-outs: %s" % (", ".join("%s %s (%.2f, %.2f)" % (r, sd, x, y) for r, (x, y), sd in sides),
                                                  "; ".join(hits) or "nothing"))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "strip":
        strip(sys.argv[2])
    elif cmd == "fiducials":
        fiducials(sys.argv[2])
    elif cmd == "stitch":
        import finish_stitch
        finish_stitch.main(sys.argv[2], sys.argv[3], pieces_only="--pieces" in sys.argv)
    elif cmd == "pieces":
        import finish_stitch
        finish_stitch.pieces_report(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "silk":
        import finish_silk
        finish_silk.main(sys.argv[2], sys.argv[3])
    elif cmd == "teardrops":
        import finish_td
        finish_td.main(sys.argv[2])
    else:
        sys.exit(__doc__)
