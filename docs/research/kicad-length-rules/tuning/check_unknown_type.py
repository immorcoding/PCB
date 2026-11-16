"""Control for make_generated.py: does pcbnew count an UNKNOWN generator type as a generator too?
If yes, `len(Generators()) == 1` does not prove that the tuning_pattern was recognised.

    D:\\KiCad\\bin\\python.exe -I check_unknown_type.py <out dir of make_generated.py>
"""
import os, sys
import pcbnew

out = os.path.abspath(sys.argv[1])
src = os.path.join(out, "lentest_gen.kicad_pcb")
for label, old, new in (("tuning_pattern (as written)", "(type tuning_pattern)", "(type tuning_pattern)"),
                        ("bogus type", "(type tuning_pattern)", "(type bogus_pattern)")):
    t = open(src, encoding="utf-8").read().replace(old, new)
    p = os.path.join(out, "ctl.kicad_pcb")
    open(p, "w", encoding="utf-8").write(t)
    try:
        b = pcbnew.LoadBoard(p)
        print(f"{label:30s} -> loaded; Generators(): {len(b.Generators())}; tracks: {len(list(b.GetTracks()))}")
        q = os.path.join(out, "ctl_saved.kicad_pcb")
        pcbnew.SaveBoard(q, b)
        print("   saved copy contains '(generated':", "(generated" in open(q, encoding="utf-8").read(),
              "| type line:", [l.strip() for l in open(q, encoding="utf-8") if l.strip().startswith("(type ") and "pattern" in l])
    except Exception as e:
        print(f"{label:30s} -> LoadBoard raised: {e}")
