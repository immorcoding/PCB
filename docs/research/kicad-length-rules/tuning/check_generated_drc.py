"""After make_generated.py: does DRC treat a net with a (generated) tuning pattern the same?

    D:\\KiCad\\bin\\python.exe -I check_generated_drc.py <out dir from make_generated.py>
"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lentest"))
from parse_report import blocks, net_of

out = os.path.abspath(sys.argv[1])
for name in ("lentest_gen", "lentest_gen_up"):
    pcb = os.path.join(out, name + ".kicad_pcb")
    if name == "lentest_gen_up":      # the upgraded copy needs the project + rule files next to it
        for ext in (".kicad_pro", ".kicad_dru"):
            src = os.path.join(out, "lentest_gen" + ext)
            with open(src, "rb") as s, open(os.path.join(out, name + ext), "wb") as d:
                d.write(s.read())
    rpt = os.path.join(out, name + ".rpt")
    subprocess.run([r"D:\KiCad\bin\kicad-cli.exe", "pcb", "drc", "--severity-all", "--units", "mm", "-o", rpt, pcb],
                   capture_output=True)
    text = open(rpt, encoding="utf-8", errors="replace").read()
    d9 = [b.numbers[-1] for b in blocks(text) if b.code == "length_out_of_range" and "/SDRAM_D9" in b.nets]
    print(name, "-> /SDRAM_D9 DRC length:", d9, "| violation blocks:", len(blocks(text)))
