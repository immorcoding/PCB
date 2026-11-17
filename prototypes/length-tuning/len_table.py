"""PROTOTYPE (issue 15): length table of the nine nets, measured by KiCad's own DRC (probe-rule method).

    D:\\KiCad\\bin\\python.exe len_table.py <variant dir> [--ref /FMC_SDCLK]
        -> <variant dir>/lengths.txt (Chinese table) and lengths.json

Method (research for issue 14, lentest/length_table.py): the board and project are copied to a temp
folder next to a rule file that holds one probe rule, `length (max 0.001mm)`, with the same condition
as the project's length rule. kicad-cli then reports every matched net with its length. A rule that
matches no net shows up as EMPTY. The geometric sum (segments + arcs, read with pcbnew) is printed
beside it as a cross-check; the difference is the height of the vias as KiCad counts it.
"""
import collections, json, math, os, re, shutil, subprocess, sys, tempfile
import pcbnew

CLI = r"D:\KiCad\bin\kicad-cli.exe"
NAME = "lentune"
LNUM = {pcbnew.F_Cu: "L1", pcbnew.In1_Cu: "L2", pcbnew.In2_Cu: "L3", pcbnew.In3_Cu: "L4", pcbnew.In4_Cu: "L5", pcbnew.B_Cu: "L6"}


def length_rules(dru_text):
    """[(rule name, condition clause text)] of every rule that has a length constraint."""
    out = []
    for m in re.finditer(r'\(rule\s+"([^"]+)"(.*?)(?=\n\(rule|\Z)', dru_text, re.S):
        if re.search(r"\(constraint\s+length\b", m.group(2)):
            c = re.search(r'\(condition\s+"[^"]*"\)', m.group(2))
            out.append((m.group(1), c.group(0) if c else ""))
    return out


def probe(vdir):
    """{rule: {net: length mm}} as reported by kicad-cli with probe rules."""
    rules = length_rules(open(os.path.join(vdir, NAME + ".kicad_dru"), encoding="utf-8").read())
    text = "(version 1)\n" + "".join('(rule "%s"\n  %s\n  (constraint length (max 0.001mm)))\n' % r for r in rules)
    tmp = tempfile.mkdtemp(prefix="lentable_")
    try:
        for ext in (".kicad_pcb", ".kicad_pro"):
            shutil.copy(os.path.join(vdir, NAME + ext), os.path.join(tmp, NAME + ext))
        open(os.path.join(tmp, NAME + ".kicad_dru"), "w", encoding="utf-8").write(text)
        rpt = os.path.join(tmp, "o.rpt")
        subprocess.run([CLI, "pcb", "drc", "--severity-all", "--units", "mm", "-o", rpt,
                        os.path.join(tmp, NAME + ".kicad_pcb")], capture_output=True)
        lines = open(rpt, encoding="utf-8", errors="replace").read().splitlines()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    got = {r[0]: {} for r in rules}
    cur = None
    for line in lines:                                    # the wording is localised: key on code, Rule: line, numbers
        m = re.match(r"^\[(\w+)\]: (.*)$", line)
        if m:
            cur = {"code": m.group(1), "nums": [float(x) for x in re.findall(r"(-?\d+(?:\.\d+)?) mm", m.group(2))]}
            continue
        m = re.match(r"^\s+Rule: (.*?); \w+\s*$", line)
        if m and cur:
            cur["rule"] = m.group(1)
            continue
        m = re.search(r"\[(/[^\]]*)\]", line) if line.startswith("    @") else None
        if m and cur and cur["code"] == "length_out_of_range" and cur.get("rule") in got:
            got[cur["rule"]][m.group(1)] = cur["nums"][-1]
    return got


def lengths(vdir):
    """{net: length mm} of the group. Of several length rules on the same nets only the last one reports
    (a later rule replaces an earlier one), so take the rule that matched the most nets."""
    return max(probe(vdir).values(), key=len)


def geometry(vdir):
    """Per net, read from the board: track length per layer (segments + arcs), via count, arc count."""
    B = pcbnew.LoadBoard(os.path.join(vdir, NAME + ".kicad_pcb")); mm = pcbnew.ToMM
    g = collections.defaultdict(lambda: {"layers": collections.defaultdict(float), "vias": 0, "arcs": 0})
    for t in B.GetTracks():
        n = t.GetNetname()
        if t.Type() == pcbnew.PCB_VIA_T:
            g[n]["vias"] += 1
        else:
            g[n]["layers"][LNUM[t.GetLayer()]] += mm(t.GetLength())
            g[n]["arcs"] += t.Type() == pcbnew.PCB_ARC_T
    return g


def main(vdir, ref="/FMC_SDCLK"):
    got, geo = probe(vdir), geometry(vdir)
    out, js = [], {"ref": ref, "nets": {}}
    conds = dict(length_rules(open(os.path.join(vdir, NAME + ".kicad_dru"), encoding="utf-8").read()))
    for rule, rows in got.items():
        if not rows:
            later = [r for r in got if got[r] and conds[r] == conds[rule]]
            if later:
                out += ["规则 %s：条件和后面的规则 %s 相同，被它取代（同一批网络，后写的长度规则生效），下表就是这批网络。" % (rule, later[-1]), ""]
            else:
                out.append("规则 %s：EMPTY，没有匹配到任何网络（条件写错了，或者线没走）" % rule)
            continue
        longest = max(rows.values()); clk = rows.get(ref)
        out.append("规则 %s：%d 根网络，最长 %.3f，最短 %.3f，极差 %.3f mm" % (rule, len(rows), longest, min(rows.values()), longest - min(rows.values())))
        out.append("")
        out.append("| 网络 | 长度 (DRC) | 走线几何和 | 过孔计入 | 过孔数 | 圆弧数 | 层和各层长度 | 比最长 | 比 %s |" % ref.lstrip("/"))
        out.append("|---|---|---|---|---|---|---|---|---|")
        key = lambda n: (0, 0) if n == ref else (1, int(re.sub(r"\D", "", n) or 0))
        for n in sorted(rows, key=key):
            tr = sum(geo[n]["layers"].values())
            layers = "，".join("%s %.3f" % (l, v) for l, v in sorted(geo[n]["layers"].items()))
            out.append("| %s | %.3f | %.3f | %.3f | %d%s | %d | %s | %+.3f | %s |" % (
                n.lstrip("/"), rows[n], tr, rows[n] - tr, geo[n]["vias"], "（3 个，单独标出）" if geo[n]["vias"] >= 3 else "",
                geo[n]["arcs"], layers, rows[n] - longest, "%+.3f" % (rows[n] - clk) if clk is not None else "—"))
            js["nets"][n] = {"length": rows[n], "track": round(tr, 4), "via_part": round(rows[n] - tr, 4), "vias": geo[n]["vias"],
                             "arcs": geo[n]["arcs"], "layers": {l: round(v, 4) for l, v in geo[n]["layers"].items()},
                             "to_longest": round(rows[n] - longest, 4), "to_ref": round(rows[n] - clk, 4) if clk is not None else None}
        out.append("")
    out.append("长度口径：焊盘中心到焊盘中心的走线（直线和圆弧）加过孔实际穿过的层间高度，由 kicad-cli 的 DRC 量出（探针规则），单位 mm。")
    out.append("“走线几何和”是脚本直接从板文件把每段线加起来的，用来对照；两者之差就是 KiCad 计入的过孔高度。")
    open(os.path.join(vdir, "lengths.txt"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    json.dump(js, open(os.path.join(vdir, "lengths.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[a.index("--ref") + 1] if "--ref" in a else "/FMC_SDCLK")
