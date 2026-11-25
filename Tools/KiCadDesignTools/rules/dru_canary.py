"""Prove a project's .kicad_dru is actually loaded by KiCad's DRC.

KiCad silently ignores the WHOLE .kicad_dru on any syntax error, so a clean
DRC report proves nothing. This copies the project to a temp dir, adds one
90-degree bend, runs kicad-cli DRC, and expects the `corner_angle` rule
(from templates/common/common.kicad_dru) to fire.

Run with KiCad's bundled Python (it needs pcbnew):
    D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.rules.dru_canary path\to\board.kicad_pcb
Exit 0 = rules loaded; exit 1 = rules NOT loaded (or no corner_angle rule).
"""
import os, shutil, sys, tempfile
import pcbnew

from Tools.KiCadDesignTools.core import heavy

def main(board_path):
    board_path = os.path.abspath(board_path)
    stem = os.path.splitext(board_path)[0]
    dru = stem + ".kicad_dru"
    if not os.path.isfile(dru):
        print(f"FAIL: no rules file next to the board: {dru}"); return 1
    tmp = tempfile.mkdtemp(prefix="dru_canary_")
    try:
        name = os.path.basename(stem)
        for ext in (".kicad_pcb", ".kicad_pro", ".kicad_dru"):
            if os.path.isfile(stem + ext):
                shutil.copy(stem + ext, os.path.join(tmp, name + ext))
        pcb = os.path.join(tmp, name + ".kicad_pcb")
        b = pcbnew.LoadBoard(pcb); mm = pcbnew.FromMM
        net = pcbnew.NETINFO_ITEM(b, "DRU_CANARY"); b.Add(net)
        for (x1, y1, x2, y2) in [(-50, -50, -40, -50), (-40, -50, -40, -40)]:
            t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1))); t.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
            t.SetWidth(mm(0.2)); t.SetLayer(pcbnew.F_Cu); t.SetNet(net); b.Add(t)
        pcbnew.SaveBoard(pcb, b)
        rpt = os.path.join(tmp, "drc.rpt")
        heavy.kicad_cli("pcb", "drc", "--severity-all", pcb, "-o", rpt, outputs=[rpt])     # failed to run: HeavyError
        text = open(rpt, encoding="utf-8", errors="replace").read()
        if "Rule: corner_angle" in text:  # locale-independent line; the message line is translated
            print("OK: custom rules loaded (corner_angle fired on the canary bend)"); return 0
        print("FAIL: custom rules NOT loaded -- syntax error somewhere in", dru)
        print("      known traps: '135deg' (write 135), 'min_resolved_spokes (min 2)' (write 2)")
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
