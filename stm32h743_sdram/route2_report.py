"""The metrics table of stop 7 (build.sh route2): everything route1 builds, then the groups of ROUTE2_GROUPS written to
the real board, one KiCad refill and DRC. One table in the eight groups of PROC-4 (columns in docs/tools.md); every
number from the board file, the refilled DRC report and the scripts' outputs.

    ROUTE2_GROUPS="local routes_local.py\\nlocal_eth routes_local_eth.py" \\
        D:\\KiCad\\bin\\python.exe stm32h743_sdram\\route2_report.py <board> <out dir>

The SDRAM group's part is route1_report.py's table, unchanged (it reads the same files in <out dir>). Added here:
  [每组]   one row per routes file on the board (sdram, power, power_bga and every ROUTE2_GROUPS entry): nets,
           connected pad to pad as read back from the board file, segments / arcs / vias in the file, DRC
           unconnected and other items touching the group's nets (refilled DRC), track_shape.py items on its nets
  [差分对] the Ethernet pairs: DRC-measured length of each line, intra-pair difference, the pair rules' DRC items
  [布局]   place_check.py (place_check.txt, as the layout step runs it) and the copper sketch check (sketch_check.txt)
Reads <out dir>/<group>/metrics.json of each ROUTE2_GROUPS entry (the group build: lengths as DRC measures them, the
serpentines). Writes <out dir>/table.txt (the SDRAM part also as table_route1.txt); exit 1 when a hard number is off.
"""
import collections, contextlib, io, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import route1_report as R1                                  # noqa: E402

PAIRS = [("ETH_TX_P", "ETH_TX_N"), ("ETH_RX_P", "ETH_RX_N")]
PAIR_TYPES = ("diff_pair_gap_out_of_range", "diff_pair_uncoupled_length_too_long", "skew_out_of_range")


def groups_env():
    out = []
    for line in os.environ.get("ROUTE2_GROUPS", "").splitlines():
        if line.split():
            name, f = line.split()[:2]
            out.append((name, f))
    return out


def main(board_path, odir):
    from busroute.board import Board
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        bad1 = R1.main(board_path, odir)
    t1 = open(os.path.join(odir, "table.txt"), encoding="utf-8").read()
    open(os.path.join(odir, "table_route1.txt"), "w", encoding="utf-8").write(t1)
    t1 = t1.replace("== 走线一 A 部分（build.sh route1）：SDRAM 组写入真板，两组电源在它之后重建，KiCad 填充后量 ==",
                    "== SDRAM 组（route1 的表，同一块板、同一次填充和 DRC）==")
    t1 = re.sub(r"\[构建\] route1 一步 .*", "[构建] 见文末", t1)
    bad = ["SDRAM part"] if bad1 else []
    L = []
    A = L.append
    A("== 走线二（build.sh route2）：route1 的全部，再把各组局部走线写入真板，KiCad 填充后量 ==")
    A("板：%s" % board_path)
    b = Board(board_path, (100, 100))
    side = json.load(open(os.path.splitext(board_path)[0] + ".busroute.json", encoding="utf-8"))
    d = json.load(open(os.path.join(odir, "drc.json"), encoding="utf-8"))

    def net_of(it):
        m = re.search(r"\[([^\]]+)\]", it.get("description", ""))
        return m.group(1) if m else None
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "track_shape.py"), board_path], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    shape_lines, kind = collections.defaultdict(list), None
    for l in r.stdout.splitlines():
        m = re.match(r"^(off-grid|staircase|sharp|crowded|arc-joint): (\d+)", l)
        if m:
            kind = m.group(1); continue
        if l.startswith("tiny"):
            kind = None
        if l.startswith("    ") and kind:
            shape_lines[l.split()[0]].append("%s: %s" % (kind, l.strip()))
    # ---- per group
    A("")
    A("[每组] 板上每个走线描述文件一行（连通从板文件读回；DRC 是最后一次填充后的全板报告里碰到本组网络的项）")
    A("       %-10s %-22s %5s %9s %6s %5s %5s %7s  %-34s %s" % ("组", "文件", "网络", "焊盘连通", "线段", "圆弧", "过孔", "DRC未连", "DRC 其他项（本组）", "线形项"))
    rows = [("sdram", "routes_sdram.py"), ("power", "routes_power.py"), ("power_bga", "routes_power_bga.py")] + groups_env()
    gm = {}
    for name, f in rows:
        g = side["groups"].get(name)
        if g is None:
            A("       %-10s %-22s 板上没有这一组" % (name, f))
            bad.append("group %s missing" % name)
            continue
        mp = os.path.join(odir, name, "metrics.json")
        m = json.load(open(mp, encoding="utf-8")) if os.path.isfile(mp) else None
        gm[name] = m
        shared = "segs" in g
        nets = sorted(m["length"]["nets"]) if m else sorted(g["nets"])
        if shared:                      # a shared group owns no net: count its own copper as recorded
            segs = len(g.get("segs", []))
            vias = len([v for v in g.get("extras", [])]) + (m["built"]["vias"] - m["built"]["stitching_vias"] if m else 0)
            conn_txt, conn_bad = "—（共用）", False
            arcs = 0
            mine = lambda v: False
            dnets = set()
        else:
            nset = set(nets)
            conn = b.connectivity(nset)
            full = [n for n, (a, c) in conn.items() if a == c and a > 1]
            open_n = sorted(nset - set(full))
            conn_txt, conn_bad = "%d/%d" % (len(full), len(nets)), bool(open_n)
            segs = sum(1 for t in b.tracks if t[0] in nset and not t[5])
            arcs = sum(1 for a in b.arc_items if a[0] in nset)
            vias = sum(1 for v in b.vias if v[0] in nset) + len(g.get("extras", []))
            dnets = nset
            mine = lambda v: any(net_of(i) in dnets for i in v["items"])
            if open_n:
                bad.append("%s open: %s" % (name, " ".join(open_n)))
        ug = [v for v in d["unconnected_items"] if mine(v)]
        other = collections.Counter(v["type"] for v in d["violations"] if mine(v))
        shp = collections.Counter(s.split(":")[0] for n in dnets for s in shape_lines.get(n, []))
        A("       %-10s %-22s %5d %9s %6d %5d %5d %7s  %-34s %s" % (
            name, f, len(nets), conn_txt, segs, arcs, vias, len(ug) if not shared else "—",
            (" ".join("%s %d" % kv for kv in sorted(other.items())) or "0") if not shared else "—",
            " ".join("%s %d" % kv for kv in sorted(shp.items())) or "0"))
        if ug:
            bad.append("%s unconnected %d" % (name, len(ug)))
        hard = {k: n for k, n in other.items() if k in R1.HARD_DRC}
        if hard:
            bad.append("%s DRC %s" % (name, " ".join(hard)))
    # the shape items of the local groups, one by one (RTE-9: each is looked at and given its reason in the report)
    loc = [n for name, _ in groups_env() if gm.get(name) for n in gm[name]["length"]["nets"]]
    items = [s for n in sorted(loc) for s in shape_lines.get(n, [])]
    A("       局部组的线形项（逐条）：%s" % ("无" if not items else ""))
    for s in items:
        A("         " + s)
    if any(s.startswith(("sharp", "off-grid", "staircase")) for s in items):
        bad.append("shape")
    # vias and lengths of the local groups
    for name, _ in groups_env():
        m = gm.get(name)
        if not m:
            continue
        nv = {n: x["vias"] for n, x in m["length"]["nets"].items()}
        lc = m["length"].get("check") or {}
        A("       %-10s 过孔每根最多 %d、合计 %d（上限 %s）；最长 %s %.3f mm；几何长度对 DRC：有长度规则的最大相差 %s，只报告的 %s" % (
            name, max(nv.values()) if nv else 0, sum(nv.values()), m["vias"]["limit"],
            max(m["length"]["nets"], key=lambda n: m["length"]["nets"][n]["length"]), max(x["length"] for x in m["length"]["nets"].values()),
            "—" if lc.get("max_ruled") is None else "%.4f" % lc["max_ruled"],
            "，".join("%s %+.4f" % kv for kv in (lc.get("notes") or {}).items()) or "无"))
        if lc and not lc.get("ok", True):
            bad.append("%s length check" % name)
    # ---- the Ethernet pairs
    A("")
    A("[差分对] 以太网两对（100 Ω，L1，线宽 0.1194、对内间距 0.2032；对内差上限 1.27 mm，eth_skew）")
    lens = {}
    for name, _ in groups_env():
        m = gm.get(name)
        if m:
            lens.update(m["length"].get("drc") or {})
            tu = m.get("tuning") or {}
            for blk in tu.get("blocks", []):
                if blk["net"].startswith("ETH_"):
                    A("       蛇形 %-9s L1 (%.3f, %.3f)-(%.3f, %.3f) %d × %.3f %s，补 %.3f" % (
                        blk["net"], blk["from"][0], blk["from"][1], blk["to"][0], blk["to"][1], blk["humps"] or blk["bumps"], blk["amp"], blk["side"], blk["gain"]))
    for p, n in PAIRS:
        if p in lens and n in lens:
            A("       %-9s %.3f mm  %-9s %.3f mm  对内差 %.3f mm" % (p, lens[p], n, lens[n], abs(lens[p] - lens[n])))
            if abs(lens[p] - lens[n]) > 1.27:
                bad.append("pair skew %s" % p)
        else:
            A("       %s / %s: 没有 DRC 长度" % (p, n))
    pv = [v for v in d["violations"] if v["type"] in PAIR_TYPES and any((net_of(i) or "").startswith("ETH_") for i in v["items"])]
    A("       差分对的 DRC 项（间隙、未耦合长度、对内差）：%d" % len(pv))
    for v in pv[:10]:
        A("         ! %s: %s" % (v["type"], v["description"]))
    if pv:
        bad.append("pair DRC")
    # ---- placement and copper sketch
    A("")
    A("[布局] place_check.py（参数同 layout 一步）：")
    pc = os.path.join(odir, "place_check.txt")
    if os.path.isfile(pc):
        for l in open(pc, encoding="utf-8", errors="replace").read().splitlines():
            if re.match(r"^\[(parts|outside|overlap|hole|keepout|under|edge|silk)\]", l) or re.match(r"^\s+U(501|101|102|601|801)\s+pins", l):
                A("       " + l.strip())
            if re.match(r"^\[(outside|overlap|hole|under)\]\s+[1-9]", l) or re.match(r"^\[keepout\]\s+[1-9]", l):
                bad.append("placement " + l.split("]")[0][1:])
    else:
        A("       没跑")
        bad.append("placement not run")
    sc = os.path.join(odir, "sketch_check.txt")
    if os.path.isfile(sc):
        first = open(sc, encoding="utf-8", errors="replace").read().splitlines()[:1]
        A("       铜皮草图检查：%s" % (first[0] if first else "—"))
        if first and not re.search(r": 0 error", first[0]):
            bad.append("copper sketch")
    A("[构建] route2 一步 %s；第 %s 轮" % (os.environ.get("ROUTE2_SECONDS", "-"), os.environ.get("ROUND", "-")))
    A("")
    A("结论：%s" % ("通过" if not bad else "不通过：" + "，".join(bad)))
    txt = "\n".join(L) + "\n\n" + t1
    open(os.path.join(odir, "table.txt"), "w", encoding="utf-8").write(txt)
    print(txt)
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main(sys.argv[1], sys.argv[2]))
