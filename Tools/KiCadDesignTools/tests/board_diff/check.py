"""Regression benchmark for analysis/board_diff.py (two board files compared item by item, pure text).

    python -m Tools.KiCadDesignTools.tests.board_diff.check

Small hand-written .kicad_pcb texts in a temp directory: the same board with other uuids, numbers written differently
and items in another order compares identical; a moved track, a changed via and a zone fill whose area changed are
reported (with --ignore and --fill-tol); a file that is not a board gives exit 2. Prints one line, `OK ...` or
`FAIL ...` (details follow a FAIL); exit code 0 = pass. Nothing is written into the repository.
"""
import contextlib, io, json, os, shutil, sys, tempfile

from Tools.KiCadDesignTools.analysis import board_diff

HEAD = '''(kicad_pcb
\t(version 20250114)
\t(generator "pcbnew")
\t(general
\t\t(thickness 1.6)
\t)
\t(layers
\t\t(0 "F.Cu" signal)
\t\t(2 "B.Cu" signal)
\t)
\t(net 0 "")
'''
SEG = '''\t(segment
\t\t(start {x} 10)
\t\t(end 20 10)
\t\t(width 0.2)
\t\t(layer "F.Cu")
\t\t(net "SIG")
\t\t(uuid "{u}")
\t)
'''
VIA = '''\t(via
\t\t(at 20 10)
\t\t(size {size})
\t\t(drill 0.2)
\t\t(layers "F.Cu" "B.Cu")
\t\t(net "SIG")
\t\t(uuid "{u}")
\t)
'''
ZONE = '''\t(zone
\t\t(net "GND")
\t\t(net_name "GND")
\t\t(layer "B.Cu")
\t\t(uuid "{u}")
\t\t(name "cu:GND")
\t\t(polygon
\t\t\t(pts
\t\t\t\t(xy 0 0) (xy 30 0) (xy 30 30) (xy 0 30)
\t\t\t)
\t\t)
\t\t(filled_polygon
\t\t\t(layer "B.Cu")
\t\t\t(pts
\t\t\t\t(xy 1 1) (xy {fx} 1) (xy {fx} 29) (xy 1 29)
\t\t\t)
\t\t)
\t)
'''


def board(path, seg_x="10", via_size="0.45", fill_x="29", uuid="1", order=("seg", "via", "zone")):
    parts = {"seg": SEG.format(x=seg_x, u="aaaaaaaa-0000-0000-0000-00000000000" + uuid),
             "via": VIA.format(size=via_size, u="bbbbbbbb-0000-0000-0000-00000000000" + uuid),
             "zone": ZONE.format(fx=fill_x, u="cccccccc-0000-0000-0000-00000000000" + uuid)}
    open(path, "w", encoding="utf-8", newline="\n").write(HEAD + "".join(parts[k] for k in order) + ")\n")
    return path


def run(*argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = board_diff.main(list(argv))
    return rc, buf.getvalue()


def main():
    tmp = tempfile.mkdtemp(prefix="board_diff_")
    bad = []
    try:
        p = lambda n: os.path.join(tmp, n)
        a = board(p("a.kicad_pcb"))
        # other uuids, 10 written as 10.00001 (rounded to 1e-4 mm), items in another order: identical
        same = board(p("same.kicad_pcb"), seg_x="10.00001", uuid="2", order=("zone", "via", "seg"))
        moved = board(p("moved.kicad_pcb"), seg_x="11")
        via = board(p("via.kicad_pcb"), via_size="0.5")
        fill = board(p("fill.kicad_pcb"), fill_x="29.02")      # fill area +0.56 mm2, the zone itself unchanged
        small = board(p("small.kicad_pcb"), fill_x="29.0001")  # +0.0028 mm2: under the default tolerance
        open(p("not.kicad_pcb"), "w", encoding="utf-8").write("(kicad_sch (version 1))\n")

        rc, out = run(a, same)
        if rc != 0 or "identical" not in out:
            bad.append("uuids, rounding and order: exit %d, expected 0\n%s" % (rc, out))
        rc, out = run(a, moved, "--json", p("moved.json"))
        j = json.load(open(p("moved.json"), encoding="utf-8"))
        seg = j["kinds"].get("segment", {})
        if rc != 1 or len(seg.get("only_a", [])) != 1 or len(seg.get("only_b", [])) != 1 or j["different_kinds"] != 1:
            bad.append("moved track: exit %d, segment only A / B %s / %s, kinds %s (expected 1, 1 / 1, 1)\n%s"
                       % (rc, len(seg.get("only_a", [])), len(seg.get("only_b", [])), j["different_kinds"], out))
        elif "SIG F.Cu 10 10 | 20 10" not in seg["only_a"][0]:
            bad.append("moved track described as %r" % seg["only_a"][0])
        rc, out = run(a, via)
        if rc != 1 or "via" not in [l.split()[0] for l in out.splitlines() if l.endswith("DIFFERENT")]:
            bad.append("changed via: exit %d\n%s" % (rc, out))
        rc, out = run(a, via, "--ignore", "via")
        if rc != 0 or "(ignored)" not in out:
            bad.append("changed via, --ignore via: exit %d, expected 0\n%s" % (rc, out))
        rc, out = run(a, fill, "--json", p("fill.json"))
        j = json.load(open(p("fill.json"), encoding="utf-8"))
        if rc != 1 or len(j["fills"]) != 1 or abs(j["fills"][0]["b"] - j["fills"][0]["a"] - 0.56) > 1e-6:
            bad.append("fill area: exit %d, fills %s (expected one layer, +0.56 mm2)\n%s" % (rc, j["fills"], out))
        rc, out = run(a, fill, "--ignore", "fill")
        if rc != 0:
            bad.append("fill area, --ignore fill: exit %d, expected 0\n%s" % (rc, out))
        rc, out = run(a, fill, "--fill-tol", "1")
        if rc != 0:
            bad.append("fill area, --fill-tol 1: exit %d, expected 0\n%s" % (rc, out))
        rc, out = run(a, small)
        if rc != 0:
            bad.append("fill area under the default tolerance: exit %d, expected 0\n%s" % (rc, out))
        rc, out = run(a, p("not.kicad_pcb"))
        if rc != 2:
            bad.append("not a board: exit %d, expected 2\n%s" % (rc, out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        print("FAIL board_diff: %d of 9 checks" % len(bad))
        print("\n".join(bad))
        return 1
    print("OK board_diff: uuids / rounding / order equal; moved track, changed via, fill area found; --ignore, --fill-tol; not a board")
    return 0


if __name__ == "__main__":
    sys.exit(main())
