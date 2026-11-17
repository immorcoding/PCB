"""PROTOTYPE (issue 15): one-screen summary of a kicad-cli DRC json report.

    D:\\KiCad\\bin\\python.exe drc_summary.py <variant dir>      (reads drc.json there)
"""
import collections, json, os, sys

d = json.load(open(os.path.join(sys.argv[1], "drc.json"), encoding="utf-8"))
sys.stdout.reconfigure(encoding="utf-8")
print("DRC (KiCad %s): unconnected %d, violations %d, schematic parity %d" % (
    d.get("kicad_version", "?"), len(d["unconnected_items"]), len(d["violations"]), len(d.get("schematic_parity", []))))
for (typ, sev), n in sorted(collections.Counter((v["type"], v["severity"]) for v in d["violations"]).items()):
    print("  %3d x %s (%s)" % (n, typ, sev))
for v in d["violations"][:40]:
    it = v["items"][0] if v["items"] else {}
    print("    %s @ (%.3f, %.3f) %s" % (v["type"], it.get("pos", {}).get("x", 0) - 100, it.get("pos", {}).get("y", 0) - 100, it.get("description", "")))
for u in d["unconnected_items"]:
    print("    unconnected:", " / ".join(i.get("description", "") for i in u["items"]))
