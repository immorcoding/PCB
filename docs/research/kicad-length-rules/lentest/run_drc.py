"""Run kicad-cli DRC on lentest.* with one rule file, save the report.

    D:\\KiCad\\bin\\python.exe -I run_drc.py rules\\<name>.kicad_dru [board_stem]

Copies <stem>.kicad_pcb / .kicad_pro next to a temp copy of the rule file (named <stem>.kicad_dru),
runs `kicad-cli pcb drc --severity-all`, writes results\\<name>.rpt.
Nothing is written next to the source board.  `run()` is also imported by the other scripts;
pcb_edit / pro_edit are optional callables that rewrite the board text / project JSON text
(used for the "no stackup" and "height off" variants).
"""
import os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CLI = r"D:\KiCad\bin\kicad-cli.exe"


def run(dru_path, stem="lentest", fmt="report", extra=(), pcb_edit=None, pro_edit=None, dru_text=None):
    tmp = tempfile.mkdtemp(prefix="lentest_")
    try:
        for ext, edit in ((".kicad_pcb", pcb_edit), (".kicad_pro", pro_edit)):
            src = os.path.join(HERE, stem + ext)
            dst = os.path.join(tmp, stem + ext)
            if edit:
                t = open(src, encoding="utf-8").read()
                open(dst, "w", encoding="utf-8").write(edit(t))
            else:
                shutil.copy(src, dst)
        if dru_text is not None:
            open(os.path.join(tmp, stem + ".kicad_dru"), "w", encoding="utf-8").write(dru_text)
        elif dru_path:
            shutil.copy(dru_path, os.path.join(tmp, stem + ".kicad_dru"))
        out = os.path.join(tmp, "drc." + ("json" if fmt == "json" else "rpt"))
        p = subprocess.run([CLI, "pcb", "drc", "--severity-all", "--format", fmt, "--units", "mm",
                            *extra, "-o", out, os.path.join(tmp, stem + ".kicad_pcb")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        text = open(out, encoding="utf-8", errors="replace").read() if os.path.exists(out) else ""
        return p.returncode, p.stdout + p.stderr, text
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    dru = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != "-" else None
    stem = sys.argv[2] if len(sys.argv) > 2 else "lentest"
    rc, console, text = run(dru, stem)
    name = os.path.splitext(os.path.basename(dru))[0] if dru else "no_dru"
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    open(os.path.join(HERE, "results", name + ".rpt"), "w", encoding="utf-8").write(text)
    print("exit code", rc, "| report ->", os.path.join("results", name + ".rpt"))
    print("console:", " / ".join(l for l in console.strip().splitlines() if "drc.rpt" not in l))
    print("violation blocks:", len(re.findall(r"^\[", text, re.M)))
