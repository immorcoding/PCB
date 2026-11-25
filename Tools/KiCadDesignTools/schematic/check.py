"""Check the exported netlist of the schematic against what was intended (RUL-6: the netlist decides).

    python -m Tools.KiCadDesignTools.schematic.check <board dir> <netlist.net> [--pages a b ...]

The drawing's intent is collected by generating the pages again into <netlist folder>/_check_regen.

1. Intent: every page module records pin -> net while drawing (Sheet.nets). The netlist must contain
   exactly those nets with exactly those pins: a stub that missed its pin, two labels that merged, or a
   net that split shows up here.
2. Pin table (board.toml [schematic.pin_table]: file with the columns port, ball, group, signal; ref; page): every
   assigned MCU ball is on the net named by its signal; the balls of group FREE are unconnected; the occupancy
   (assigned / all rows) is counted here, not typed in. Only when that page is drawn.
3. Data-bit swap ([schematic.swap]): each SDRAM byte lane carries the eight data bits of one MCU byte, and its DQM is
   that byte's mask net (SPEC 9). The page module named there gives ball_map() {ball: DQn, DQMn ...} (one line:
   Tools.KiCadDesignTools.schematic.swap.ball_map of its grid; the page wires [schematic.swap] table through
   schematic.swap.swap_table). Only when that page is drawn.
4. Single-pin nets and names used on one page only, as lists for review (not failures).
Exit code 0 = checks 1-3 pass.
"""
import csv, os, re, sys

from Tools.KiCadDesignTools.core import config
from Tools.KiCadDesignTools.schematic import generate, kisch


def read_netlist(path):
    """{net name: {(ref, pin)}} without power-symbol and flag references."""
    doc = kisch.parse(open(path, encoding="utf-8").read())
    out = {}
    for net in kisch.find_all(kisch.find(doc, "nets"), "net"):
        name = str(kisch.find(net, "name")[1])
        pins = {(str(kisch.find(n, "ref")[1]), str(kisch.find(n, "pin")[1])) for n in kisch.find_all(net, "node")}
        out[name] = {p for p in pins if not p[0].startswith("#")}
    return out


def main(argv):
    cfg = config.load(argv[0])
    net_path = argv[1]
    only = argv[argv.index("--pages") + 1:] if "--pages" in argv else None
    scratch = os.path.join(os.path.dirname(os.path.abspath(net_path)), "_check_regen")
    sheets = generate.main(cfg, only, scratch)    # regenerate into a scratch folder just to collect the intent
    got = read_netlist(net_path)
    sys.stdout.reconfigure(encoding="utf-8")
    bad = 0

    # 1. intent
    want, page_of = {}, {}
    for sh in sheets:
        for net, pins in sh.nets.items():
            want.setdefault(net, set()).update(pins)
            page_of.setdefault(net, set()).add(sh.page.name)
    named = {n: p for n, p in got.items() if not n.startswith("unconnected-")}
    diffs = []
    for net in sorted(set(want) | set(named)):
        a, b = want.get(net, set()), named.get(net, set())
        if a != b:
            diffs.append("%s: 原理图意图有而网表没有 %s；网表有而意图没有 %s" % (net, sorted(a - b) or "无", sorted(b - a) or "无"))
    print("1. 网表对意图：%d 个网络，%d 个引脚，%d 处不符" % (len(want), sum(len(p) for p in want.values()), len(diffs)))
    print("\n".join("   " + d for d in diffs[:40]))
    bad += len(diffs)

    pin_net = {pin: net for net, pins in got.items() for pin in pins}
    # 2. pins.csv
    pt = cfg.get("schematic.pin_table")
    if pt and any(sh.page.name == pt["page"] for sh in sheets):
        rows = list(csv.DictReader(open(cfg.path(pt["file"]), encoding="utf-8")))
        wrong, used = [], 0
        for r in rows:
            net = pin_net.get((pt["ref"], r["ball"]), "")
            if r["group"] == "FREE":
                if not net.startswith("unconnected-"):
                    wrong.append("%s %s 应悬空，实际在 %s" % (r["port"], r["ball"], net))
            else:
                used += 1
                if net != r["signal"]:
                    wrong.append("%s %s 应是 %s，实际 %s" % (r["port"], r["ball"], r["signal"], net or "没有这个引脚"))
        print("2. %s 对网表：%d 个 IO，占用 %d / %d = %.1f%%，%d 处不符" % (pt["file"], len(rows), used, len(rows), 100.0 * used / len(rows), len(wrong)))
        print("\n".join("   " + w for w in wrong[:40]))
        bad += len(wrong)

    # 3. swap.csv
    sw = cfg.get("schematic.swap")
    if sw and any(sh.page.name == sw["page"] for sh in sheets):
        balls = cfg.module("sch." + sw["page"]).ball_map()
        D, M, lanes = sw["data_net"], sw["mask_net"], sw["lanes"]
        sig_net = {sig: pin_net.get((sw["ref"], ball)) for ball, sig in balls.items() if sig.startswith("DQ")}
        errs = []
        for lane in range(lanes):
            nets = [sig_net["DQ%d" % k] for k in range(8 * lane, 8 * lane + 8)]
            bits = sorted(int(re.sub(r"\D", "", n.replace(D, ""))) if n and n.startswith(D) else -1 for n in nets)
            byte = bits[0] // 8 if bits[0] >= 0 else -1
            if bits != list(range(8 * byte, 8 * byte + 8)):
                errs.append("字节通道 %d 上的网络不是同一个字节的 8 位：%s" % (lane, nets))
            elif sig_net["DQM%d" % lane] != "%s%d" % (M, byte):
                errs.append("字节通道 %d 接的是字节 %d，DQM 应是 %s%d，实际 %s" % (lane, byte, M, byte, sig_net["DQM%d" % lane]))
        moved = sum(1 for k in range(8 * lanes) if sig_net["DQ%d" % k] != "%s%d" % (D, k))
        print("3. 换位表对网表：%d 个字节通道，%d 处不符；和不换位相比挪动了 %d 位" % (lanes, len(errs), moved))
        print("\n".join("   " + e for e in errs))
        bad += len(errs)

    # 4. for review
    single = sorted(n for n, p in named.items() if len(p) == 1)
    print("4. 只有一个引脚的命名网络 %d 个：%s" % (len(single), "、".join(single) or "无"))
    nc = sorted(n for n in got if n.startswith("unconnected-"))
    print("   标了不连接的引脚 %d 个" % len(nc))
    print("%s：%d 处不符" % ("FAIL" if bad else "OK", bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
