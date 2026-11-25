"""Regression benchmark for core/boardtext.py (text edits of a .kicad_pcb: every byte but the named lines stays).

    python -m Tools.KiCadDesignTools.tests.boardtext.check

A small hand-written board in a temp directory, with LF and with CRLF line ends: layer_rows; sync_layers rewrites
only the copper rows of the layer table (and nothing the second time); unfill removes exactly the filled polygons;
orphans removes every segment, arc and via and lists them in local coordinates. The result files are compared byte
for byte with the expected text. `strip` needs pcbnew and a busroute record: the busroute bench and the demo board
cover it. Prints one line, `OK ...` or `FAIL ...` (details follow a FAIL); exit code 0 = pass. Nothing is written
into the repository.
"""
import contextlib, io, os, shutil, sys, tempfile

from Tools.KiCadDesignTools.core import boardtext

LAYERS = '''\t(layers
\t\t(0 "F.Cu" signal)
\t\t(4 "In1.Cu" signal)
\t\t(2 "B.Cu" signal)
\t\t(9 "F.Adhes" user "F.Adhesive")
\t)
'''
LAYERS_NEW = '''\t(layers
\t\t(0 "F.Cu" signal)
\t\t(4 "In1.Cu" power "L2_GND")
\t\t(2 "B.Cu" signal)
\t\t(9 "F.Adhes" user "F.Adhesive")
\t)
'''
FOOT = '''\t(footprint "R_0402"
\t\t(layer "F.Cu")
\t\t(at 110 105)
\t)
'''
COPPER = '''\t(segment
\t\t(start 101 102)
\t\t(end 103 102)
\t\t(width 0.2)
\t\t(layer "F.Cu")
\t\t(net "SIG")
\t\t(uuid "aaaaaaaa-0000-0000-0000-000000000001")
\t)
\t(arc
\t\t(start 103 102)
\t\t(mid 103.5 102.2)
\t\t(end 104 102.5)
\t\t(width 0.2)
\t\t(layer "B.Cu")
\t\t(net "SIG")
\t\t(uuid "aaaaaaaa-0000-0000-0000-000000000002")
\t)
\t(via
\t\t(at 104 102.5)
\t\t(size 0.45)
\t\t(drill 0.2)
\t\t(layers "F.Cu" "B.Cu")
\t\t(net "SIG")
\t\t(uuid "aaaaaaaa-0000-0000-0000-000000000003")
\t)
'''
ZONE = '''\t(zone
\t\t(net "GND")
\t\t(layer "B.Cu")
\t\t(name "cu:GND")
\t\t(polygon
\t\t\t(pts
\t\t\t\t(xy 100 100) (xy 120 100) (xy 120 120) (xy 100 120)
\t\t\t)
\t\t)
{fill}\t)
'''
FILL = '''\t\t(filled_polygon
\t\t\t(layer "B.Cu")
\t\t\t(pts
\t\t\t\t(xy 101 101) (xy 119 101) (xy 119 119) (xy 101 119)
\t\t\t)
\t\t)
'''


def text(layers=LAYERS, copper=COPPER, fills=2):
    return "(kicad_pcb\n\t(version 20250114)\n" + layers + FOOT + copper + ZONE.format(fill=FILL * fills) + ")\n"


def quiet(f, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = f(*a)
    return r, buf.getvalue()


def main():
    tmp = tempfile.mkdtemp(prefix="boardtext_")
    bad = []
    rows = [(0, "F.Cu", "signal", None), (4, "In1.Cu", "power", "L2_GND"), (2, "B.Cu", "signal", None)]
    try:
        if boardtext.layer_rows(rows) != '\t\t(0 "F.Cu" signal)\n\t\t(4 "In1.Cu" power "L2_GND")\n\t\t(2 "B.Cu" signal)\n':
            bad.append("layer_rows: %r" % boardtext.layer_rows(rows))
        for eol in ("\n", "\r\n"):
            tag = "LF" if eol == "\n" else "CRLF"
            p = os.path.join(tmp, "b_%s.kicad_pcb" % tag)
            put = lambda s: open(p, "w", encoding="utf-8", newline="").write(s.replace("\n", eol))
            get = lambda: open(p, encoding="utf-8", newline="").read()
            # sync_layers: only the copper rows change; a second run writes nothing
            put(text())
            w1 = boardtext.sync_layers(p, rows)
            w2 = boardtext.sync_layers(p, rows)
            if (w1, w2) != (True, False) or get() != text(layers=LAYERS_NEW).replace("\n", eol):
                bad.append("%s sync_layers: wrote %s, %s (expected True, False) or the text differs" % (tag, w1, w2))
            # unfill: the two filled polygons out, the zone outline and everything else byte for byte
            put(text())
            _, out = quiet(boardtext.unfill, p)
            if get() != text(fills=0).replace("\n", eol) or "2 filled polygons removed" not in out:
                bad.append("%s unfill: %r, or the text differs" % (tag, out))
            _, out = quiet(boardtext.unfill, p)
            if "0 filled polygons removed" not in out:
                bad.append("%s unfill a second time: %r" % (tag, out))
            # orphans: the segment, the arc and the via out, listed in local mm (origin 100, 100)
            put(text())
            _, out = quiet(boardtext.orphans, p, (100.0, 100.0))
            want = ["orphans: 3 item(s) owned by no group removed", "  segment SIG F.Cu (1.000, 2.000)",
                    "  arc SIG B.Cu (3.000, 2.000)", "  via SIG F.Cu (4.000, 2.500)"]
            if get() != text(copper="").replace("\n", eol) or out.splitlines() != want:
                bad.append("%s orphans: %r, or the text differs" % (tag, out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        print("FAIL boardtext: %d problem(s)" % len(bad))
        print("\n".join(bad))
        return 1
    print("OK boardtext: layer_rows; sync_layers, unfill, orphans byte for byte, LF and CRLF")
    return 0


if __name__ == "__main__":
    sys.exit(main())
