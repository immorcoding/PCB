"""PROTOTYPE helper: print pad numbers / positions of library footprints and pin names of library symbols.

    D:\\KiCad\\bin\\python.exe probe.py fp  <Lib:Name> ...
    D:\\KiCad\\bin\\python.exe probe.py sym <LibFile.kicad_sym> <SymbolName> [name-regex]
"""
import os, re, sys
import pcbnew

KI = r"D:\KiCad\share\kicad"
mm = pcbnew.ToMM


def sym_pins(libfile, name):
    """{pin number: pin name} of a library symbol (follows one level of 'extends')."""
    text = open(os.path.join(KI, "symbols", libfile), encoding="utf-8").read()

    def block(n):
        i = text.find('\t(symbol "%s"\n' % n)
        if i < 0:
            raise SystemExit("no symbol " + n)
        depth, j = 0, i
        while True:
            c = text[j]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return text[i:j + 1]
            j += 1

    blk = block(name)
    m = re.search(r'\(extends "([^"]+)"', blk)
    if m:
        blk = block(m.group(1))
    pins = {}
    for m in re.finditer(r'\(name "([^"]*)".*?\(number "([^"]*)"', blk, re.S):
        pins[m.group(2)] = m.group(1)
    return pins


if __name__ == "__main__":
    if sys.argv[1] == "sym":
        pins = sym_pins(sys.argv[2], sys.argv[3])
        rx = re.compile(sys.argv[4]) if len(sys.argv) > 4 else None
        by = {}
        for num, nm in pins.items():
            if rx is None or rx.search(nm):
                by.setdefault(nm, []).append(num)
        print(sys.argv[3], len(pins), "pins")
        for nm in sorted(by):
            print("  %-14s %s" % (nm, " ".join(sorted(by[nm]))))
    else:
        for spec in sys.argv[2:]:
            lib, name = spec.split(":")
            fp = pcbnew.FootprintLoad(os.path.join(KI, "footprints", lib + ".pretty"), name)
            bb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
            print("%s  courtyard x[%.2f,%.2f] y[%.2f,%.2f]  pads %d" % (
                spec, mm(bb.GetLeft()), mm(bb.GetRight()), mm(bb.GetTop()), mm(bb.GetBottom()), len(fp.Pads())))
            pads = list(fp.Pads())
            if len(pads) <= 48:
                for p in pads:
                    print("   %-4s (%7.3f,%7.3f) %4.2fx%4.2f %s" % (
                        p.GetNumber(), mm(p.GetPosition().x), mm(p.GetPosition().y), mm(p.GetSizeX()), mm(p.GetSizeY()),
                        "TH" if p.HasHole() else "smd"))
