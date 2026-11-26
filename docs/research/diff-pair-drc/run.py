"""Issue #44: build the fixture and run one DRC per rule set, one at a time, through core.heavy.

    python docs/research/diff-pair-drc/run.py            (from the repository root, the system python)

Writes board/ (dpdrc.kicad_pcb, .kicad_pro, predict.json), rules/<set>.kicad_dru, results/<set>.json and
results/summary.txt (DRC value next to the prediction, per pair).
"""
import json, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, REPO)
from Tools.KiCadDesignTools.core import heavy  # noqa: E402

BOARD = os.path.join(HERE, "board")
TEMPLATE = os.path.join(REPO, "templates", "C-bga-065", "C-bga-065.kicad_pro")
COUPLING = "A.inDiffPair('/E1*') || A.inDiffPair('/E2*') || A.inDiffPair('/E5*')"

GAP_WINDOW = f'(rule "dp_gap"\n  (condition "{COUPLING}")\n  (constraint diff_pair_gap (min 0.14mm) (max 0.2mm)))\n'
GAP_MIN = f'(rule "dp_gap"\n  (condition "{COUPLING}")\n  (constraint diff_pair_gap (min 0.14mm)))\n'
UNC_TIGHT = f'(rule "dp_unc"\n  (condition "{COUPLING}")\n  (constraint diff_pair_uncoupled (max 0.0001mm)))\n'
UNC_LOOSE = f'(rule "dp_unc"\n  (condition "{COUPLING}")\n  (constraint diff_pair_uncoupled (max 50mm)))\n'
SKEW = '''(rule "e3_skew"
  (condition "A.inDiffPair('/E3*')")
  (constraint skew (max 0.0001mm) (within_diff_pairs)))
(rule "e3_len"
  (condition "A.inDiffPair('/E3*')")
  (constraint length (max 0.001mm)))
(rule "e4a_skew_one_net"
  (condition "A.NetName == '/E4A_P'")
  (constraint skew (max 0.0001mm) (within_diff_pairs)))
(rule "e4b_skew_both"
  (condition "A.inDiffPair('/E4B')")
  (constraint skew (max 0.0001mm) (within_diff_pairs)))
(rule "e4c_skew_lone"
  (condition "A.NetName == '/E4C_P'")
  (constraint skew (max 0.0001mm) (within_diff_pairs)))
(rule "e4_len"
  (condition "A.NetName == '/E4A_P' || A.NetName == '/E4A_N' || A.NetName == '/E4C_P'")
  (constraint length (max 0.001mm)))
'''
SETS = {
    "rs1_window_unc": GAP_WINDOW + UNC_TIGHT,       # uncoupled readout, gap window 0.14-0.2
    "rs2_minonly_unc": GAP_MIN + UNC_TIGHT,         # uncoupled readout, no upper gap limit
    "rs3_window_only": GAP_WINDOW,                  # gap reports without an uncoupled rule
    "rs4_window_unc_loose": GAP_WINDOW + UNC_LOOSE, # are gap violations reported when the budget holds?
    "rs5_skew_length": SKEW,                        # E3, E4
}


def build():
    if os.path.isdir(BOARD):
        shutil.rmtree(BOARD)
    r = heavy.kicad_py(os.path.join(HERE, "make_board.py"), BOARD, TEMPLATE, check=True)
    print(heavy.decode(r.stdout).strip())


def drc(name, text):
    os.makedirs(os.path.join(HERE, "rules"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    open(os.path.join(HERE, "rules", name + ".kicad_dru"), "w", encoding="utf-8").write("(version 1)\n" + text)
    work = os.path.join(HERE, "work", name)
    os.makedirs(work, exist_ok=True)
    for ext in (".kicad_pcb", ".kicad_pro"):
        shutil.copy(os.path.join(BOARD, "dpdrc" + ext), os.path.join(work, "dpdrc" + ext))
    shutil.copy(os.path.join(HERE, "rules", name + ".kicad_dru"), os.path.join(work, "dpdrc.kicad_dru"))
    out = os.path.join(HERE, "results", name + ".json")
    argv = ("pcb", "drc", "--severity-all", "--units", "mm", "--format", "json", "-o", out,
            os.path.join(work, "dpdrc.kicad_pcb"))
    print("kicad-cli " + " ".join(argv))
    heavy.kicad_cli(*argv, outputs=[out])
    shutil.rmtree(work, ignore_errors=True)
    return json.load(open(out, encoding="utf-8"))


NUM = re.compile(r"([-\d.]+) mm")


def case_of(desc):
    m = re.search(r"\[/(E\d[A-Z]\d?)_[PN]\]", desc)
    return m.group(1) if m else None


def summarize(results, pred):
    lines = []
    interesting = ("diff_pair", "skew", "length_out_of_range", "clearance", "track_dangling")
    for name, rep in results.items():
        lines.append("=" * 100)
        lines.append(f"{name}")
        counts = {}
        for v in rep.get("violations", []):
            counts[v["type"]] = counts.get(v["type"], 0) + 1
        lines.append("  counts: " + ", ".join(f"{k} {n}" for k, n in sorted(counts.items())))
        for v in rep.get("violations", []):
            if not any(v["type"].startswith(t) for t in interesting) or v["type"] == "track_dangling":
                continue
            items = " | ".join(f'{it["description"]} @({it["pos"]["x"]:.4f},{it["pos"]["y"]:.4f})'
                               for it in v.get("items", []))
            lines.append(f"  [{v['type']}] {v['description']}  ::  {items}")
    lines.append("=" * 100)
    lines.append("predictions (source reading of 3.4, no 'other copper between' test):")
    for case, p in pred.items():
        row = f"  {case:5s} lenP {p['len_P']:.6f} lenN {p['len_N']:.6f}"
        for tag in ("window", "min_only"):
            if tag in p:
                row += f"  {tag}: uncoupled {p[tag]['uncoupled']:.6f} coupled {p[tag]['coupled']:.6f}"
        lines.append(row + "   # " + p["note"])
    return "\n".join(lines)


def main():
    build()
    pred = json.load(open(os.path.join(BOARD, "predict.json"), encoding="utf-8"))
    results = {}
    for name, text in SETS.items():
        results[name] = drc(name, text)
    s = summarize(results, pred)
    open(os.path.join(HERE, "results", "summary.txt"), "w", encoding="utf-8").write(s + "\n")
    print(s)
    left = heavy.running()
    print("processes still running:", left or "none")


if __name__ == "__main__":
    main()
