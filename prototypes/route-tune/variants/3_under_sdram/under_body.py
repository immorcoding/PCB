"""PROTOTYPE (issue 21): length of bus copper inside the SDRAM package outline, per layer (the space metrics do not count it).
Run from prototypes/route-tune:  D:/KiCad/bin/python.exe variants/3_under_sdram/under_body.py 3_under_sdram 1_baseline"""
import sys, json, math, pcbnew
def under(key):
    B = pcbnew.LoadBoard("out/%s/routetune.kicad_pcb" % key)
    tot = {}
    for t in B.GetTracks():
        if t.GetClass() == "PCB_VIA" or not t.GetNetname().startswith("/FMC_"): continue
        L = pcbnew.ToMM(t.GetLength()); a = t.GetStart(); c = t.GetEnd()
        n = 40; ins = 0
        for i in range(n):
            f = (i + .5) / n
            if t.GetClass() == "PCB_ARC":
                m = t.GetMid(); x = pcbnew.ToMM(m.x) - 100; y = pcbnew.ToMM(m.y) - 100
            else:
                x = pcbnew.ToMM(a.x + (c.x - a.x) * f) - 100; y = pcbnew.ToMM(a.y + (c.y - a.y) * f) - 100
            if 23 <= x <= 31 and 9.4 <= y <= 22.4: ins += 1
        ln = B.GetLayerName(t.GetLayer())
        tot[ln] = tot.get(ln, 0) + L * ins / n
    return {k: round(v, 1) for k, v in tot.items()}, round(sum(tot.values()), 1)
for k in sys.argv[1:]:
    print(k, under(k))
