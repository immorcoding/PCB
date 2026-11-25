"""Regression benchmark for core/uuids.py (deterministic uuids of the board writers).

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.tests.uuids.check

make(key) is uuid5 in the module's namespace, and two keys are pinned to the values every committed board was built
with: a changed namespace or key scheme would give every board file new uuids (and a new item order). Keys().unique
numbers repeats key, key#2, key#3. With KiCad's python, stamp() and stamp_footprint() put those uuids on pcbnew
items (skipped, and said so, under a Python without pcbnew). Prints one line, `OK ...` or `FAIL ...`; exit code
0 = pass. Nothing is written.
"""
import sys, uuid

from Tools.KiCadDesignTools.core import uuids

PINNED = {"place:outline:seg:0": "7c6b9fb1-67d3-5c37-adbb-ee86de044cf0",
          "stitch:via:110.25,52.8": "d28342f3-ae7d-5e23-ae28-cf185f4acd1e"}


def main():
    bad = []
    for k, v in PINNED.items():
        if uuids.make(k) != v:
            bad.append("make(%r) = %s, pinned %s" % (k, uuids.make(k), v))
    if uuids.make("a") != str(uuid.uuid5(uuids.NS, "a")) or uuids.make("a") == uuids.make("b"):
        bad.append("make is not uuid5 in NS, or two keys share a uuid")
    keys = uuids.Keys()
    got = [keys.unique(k) for k in ("v", "v", "w", "v")]
    if got != ["v", "v#2", "w", "v#3"]:
        bad.append("Keys.unique: %s" % got)
    try:
        import pcbnew
    except ImportError:
        pcbnew = None
    note = "stamp skipped (no pcbnew)"
    if pcbnew is not None:
        b = pcbnew.BOARD()
        t = uuids.stamp(pcbnew.PCB_TRACK(b), "bench:track")
        if t.m_Uuid.AsString() != uuids.make("bench:track"):
            bad.append("stamp: %s" % t.m_Uuid.AsString())
        fp = pcbnew.FOOTPRINT(b)
        for i in range(2):
            p = pcbnew.PAD(fp); p.SetNumber(str(i + 1)); fp.Add(p)
        uuids.stamp_footprint(fp, "bench:fp")
        want = [uuids.make("bench:fp")] + [uuids.make("bench:fp/pad/%d" % i) for i in range(2)]
        have = [fp.m_Uuid.AsString()] + [p.m_Uuid.AsString() for p in fp.Pads()]
        fields = {f.GetName(): f.m_Uuid.AsString() for f in fp.GetFields()}
        if have != want or fields.get("Reference") != uuids.make("bench:fp/field/Reference"):
            bad.append("stamp_footprint: %s, fields %s" % (have, fields))
        note = "stamp and stamp_footprint on pcbnew items"
    if bad:
        print("FAIL uuids: %d problem(s)" % len(bad))
        print("\n".join(bad))
        return 1
    print("OK uuids: pinned keys unchanged, uuid5 in NS, Keys.unique; %s" % note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
