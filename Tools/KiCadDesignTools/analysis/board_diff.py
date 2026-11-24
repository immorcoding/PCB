"""Compare two KiCad board files item by item, without KiCad (pure text).

    python -m Tools.KiCadDesignTools.analysis.board_diff <a.kicad_pcb> <b.kicad_pcb> [--json OUT] [--show N] [--fill-tol MM2]
                                        [--ignore KIND[,KIND...]]

Both files are parsed as S-expressions. Every (uuid ...) and (tstamp ...) is dropped and every number is rounded to
1e-4 mm, so that two builds that differ only in the random ids of their objects compare equal. Then the top-level items
are compared as multisets per kind (footprint, segment, arc, via, zone, gr_line, gr_text, ..., and "header" for the
layer table, setup and the rest): a footprint with its position, rotation, side, attributes, pads and texts; tracks,
arcs and vias with their net; a zone with its outline and settings. A zone's fill (filled_polygon) is not compared as
coordinates but as its area per layer (shoelace on the outline points), so a refill that moves a slit does not count;
fills that differ by more than --fill-tol mm^2 (default 0.01) are listed.

Prints per kind the counts in A and B and how many items are only in A / only in B, then up to --show N (default 10)
of them per kind with a short description (reference and position for footprints, net and ends for copper).
Exit code 0 = no difference (outside --ignore), 1 = differences, 2 = a file could not be read.
"""
import argparse, collections, json, math, re, sys

TOKEN = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')
NUM = re.compile(r"^-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?$")
DROP = {"uuid", "tstamp"}


def parse(text):
    """Nested lists; atoms are strings (quoted ones keep their quotes)."""
    stack, cur = [], []
    for m in TOKEN.finditer(text):
        t = m.group(0)
        if t == "(":
            stack.append(cur)
            cur = []
        elif t == ")":
            done = cur
            cur = stack.pop()
            cur.append(done)
        else:
            cur.append(t)
    if stack:
        raise ValueError("unbalanced parentheses")
    return cur


def num(t):
    v = round(float(t), 4)
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def canon(node, skip=()):
    if isinstance(node, list):
        if node and isinstance(node[0], str) and (node[0] in DROP or node[0] in skip):
            return None
        parts = [canon(c, skip) for c in node]
        return "(" + " ".join(p for p in parts if p is not None) + ")"
    return num(node) if NUM.match(node) else node


def head(node):
    return node[0] if isinstance(node, list) and node and isinstance(node[0], str) else None


def child(node, name):
    for c in node:
        if head(c) == name:
            return c
    return None


def children(node, name):
    return [c for c in node if head(c) == name]


def pts(node):
    p = child(node, "pts")
    out = []
    for xy in children(p or [], "xy"):
        out.append((float(xy[1]), float(xy[2])))
    return out


def area(poly):
    s = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        s += x0 * y1 - x1 * y0
    return abs(s) / 2


def unq(s):
    return s[1:-1] if s and s.startswith('"') else s


def describe(kind, node):
    try:
        if kind == "footprint":
            ref = next((unq(c[2]) for c in children(node, "property") if len(c) > 2 and unq(c[1]) == "Reference"), "?")
            at = child(node, "at") or []
            lay = child(node, "layer") or ["", "?"]
            return "%s %s at (%s) %s" % (ref, unq(node[1]), " ".join(at[1:]), unq(lay[1]))
        if kind in ("segment", "arc", "via"):
            net = child(node, "net")
            ends = [" ".join(c[1:]) for c in node if head(c) in ("start", "end", "at", "mid")]
            lay = child(node, "layer") or child(node, "layers") or []
            return "%s %s %s" % (unq(net[1]) if net else "-", " ".join(unq(x) for x in lay[1:]), " | ".join(ends))
        if kind == "zone":
            name = child(node, "name")
            net = child(node, "net_name") or child(node, "net")
            lay = child(node, "layer") or child(node, "layers") or []
            return "%s net %s on %s" % (unq(name[1]) if name else "(no name)", unq(net[1]) if net and len(net) > 1 else "-",
                                       " ".join(unq(x) for x in lay[1:]))
    except Exception:
        pass
    s = canon(node)
    return s[:160] + ("..." if len(s) > 160 else "")


def load(path):
    tree = parse(open(path, encoding="utf-8").read())
    if not tree or head(tree[0]) != "kicad_pcb":
        raise ValueError("%s: not a kicad_pcb file" % path)
    items = collections.defaultdict(collections.Counter)
    desc = {}
    fills = {}
    header = []
    for node in tree[0][1:]:
        k = head(node)
        if k is None:
            continue
        if k in ("version", "generator", "generator_version"):
            continue
        if k in ("general", "paper", "title_block", "layers", "setup", "property", "net", "embedded_fonts"):
            header.append(canon(node))
            continue
        if k == "zone":
            key = canon(node, skip=("filled_polygon", "fill_segments"))
            items[k][key] += 1
            desc[(k, key)] = describe(k, node)
            per = collections.defaultdict(float)
            for fp in children(node, "filled_polygon"):
                lay = child(fp, "layer")
                per[unq(lay[1]) if lay else "?"] += area(pts(fp))
            fills.setdefault(key, []).append(dict(per))
            continue
        key = canon(node)
        items[k][key] += 1
        desc[(k, key)] = describe(k, node)
    items["header"][canon(["header"] + [h for h in header])] += 1
    return items, desc, fills


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--json")
    ap.add_argument("--show", type=int, default=10)
    ap.add_argument("--fill-tol", type=float, default=0.01)
    ap.add_argument("--ignore", default="")
    a = ap.parse_args(argv)
    ignore = {k for k in a.ignore.split(",") if k}
    try:
        A, dA, fA = load(a.a)
        B, dB, fB = load(a.b)
    except (OSError, ValueError) as e:
        print("cannot read: %s" % e)
        return 2
    report = {"a": a.a, "b": a.b, "kinds": {}, "fills": []}
    bad = 0
    print("board_diff: A = %s\n            B = %s" % (a.a, a.b))
    print("%-14s %7s %7s %8s %8s" % ("kind", "A", "B", "only A", "only B"))
    for k in sorted(set(A) | set(B)):
        ca, cb = A.get(k, collections.Counter()), B.get(k, collections.Counter())
        oa, ob = ca - cb, cb - ca
        na, nb = sum(oa.values()), sum(ob.values())
        report["kinds"][k] = {"a": sum(ca.values()), "b": sum(cb.values()), "only_a": [dA.get((k, x), x) for x in oa.elements()],
                              "only_b": [dB.get((k, x), x) for x in ob.elements()]}
        flag = "" if not (na or nb) else ("  (ignored)" if k in ignore else "  DIFFERENT")
        print("%-14s %7d %7d %8d %8d%s" % (k, sum(ca.values()), sum(cb.values()), na, nb, flag))
        if (na or nb) and k not in ignore:
            bad += 1
        if na or nb:
            for x in list(oa.elements())[:a.show]:
                print("    - A only: %s" % dA.get((k, x), x)[:200])
            for x in list(ob.elements())[:a.show]:
                print("    + B only: %s" % dB.get((k, x), x)[:200])
    # fills: zones present in both, area per layer
    nf = 0
    for key in sorted(set(fA) & set(fB)):
        la, lb = fA[key], fB[key]
        for i in range(min(len(la), len(lb))):
            for lay in sorted(set(la[i]) | set(lb[i])):
                x, y = la[i].get(lay, 0.0), lb[i].get(lay, 0.0)
                if abs(x - y) > a.fill_tol:
                    nf += 1
                    row = {"zone": dA.get(("zone", key), key)[:120], "layer": lay, "a": round(x, 4), "b": round(y, 4)}
                    report["fills"].append(row)
    tot_a = sum(sum(sum(d.values()) for d in v) for v in fA.values())
    tot_b = sum(sum(sum(d.values()) for d in v) for v in fB.values())
    print("fills: %d zone layers differ by more than %g mm2; total filled area A %.4f, B %.4f mm2%s"
          % (nf, a.fill_tol, tot_a, tot_b, "" if not nf else ("  (ignored)" if "fill" in ignore else "  DIFFERENT")))
    for r in report["fills"][:a.show]:
        print("    %s %s: A %.4f, B %.4f" % (r["zone"], r["layer"], r["a"], r["b"]))
    if nf and "fill" not in ignore:
        bad += 1
    report["different_kinds"] = bad
    if a.json:
        json.dump(report, open(a.json, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("result: %s" % ("identical (uuids and tstamps aside)" if not bad else "%d kind(s) differ" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
