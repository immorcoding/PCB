"""Q3 probe: what does pcbnew's Python API expose about tuning patterns (PCB_GENERATOR)?

    D:\\KiCad\\bin\\python.exe -I probe_generators.py <board.kicad_pcb>

Loads a board that contains a `(generated ... (type tuning_pattern))` object (KiCad's own QA
test board, kept OUTSIDE the repo) and lists what the Python bindings can see and do.
"""
import sys
import pcbnew

b = pcbnew.LoadBoard(sys.argv[1])
gens = b.Generators()
print("Generators() ->", type(gens).__name__, "of length", len(gens))
for g in gens:
    print("element type:", type(g).__name__)
    print("  public attributes:", [n for n in dir(g) if not n.startswith("_")])
    for meth in ("GetClass", "GetItems", "Update", "GetGeneratorType", "m_Uuid"):
        print(f"  has {meth}:", hasattr(g, meth))
print("classes in pcbnew whose name contains GENERATOR / TUNING / MEANDER:",
      [n for n in dir(pcbnew) if any(s in n.upper() for s in ("GENERATOR", "TUNING", "MEANDER"))
       and n.upper() == n and n not in ("PCB_GENERATOR_T",)])
print("BOARD methods mentioning Generator:", [n for n in dir(pcbnew.BOARD) if "enerator" in n])
print("board design settings exposing meander defaults:",
      [n for n in dir(b.GetDesignSettings()) if "Meander" in n])
ms = b.GetDesignSettings().m_SingleTrackMeanderSettings
print("m_SingleTrackMeanderSettings attributes:", [n for n in dir(ms) if n.startswith("m_")])
