"""Check the exported netlist of the schematic against what was intended (RUL-6: the netlist decides).

    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\sch_check.py <netlist.net> [--pages a b ...]

1. Intent: every page module records pin -> net while drawing (Sheet.nets). The netlist must contain
   exactly those nets with exactly those pins: a stub that missed its pin, two labels that merged, or a
   net that split shows up here.
2. pins.csv: every assigned MCU ball is on the net named by its signal; the free balls are unconnected;
   the occupancy (assigned / 140) is counted here, not typed in.
3. swap.csv: each SDRAM byte lane carries the eight data bits of one MCU byte, and its DQM is that
   byte's NBL (SPEC 9).
4. Single-pin nets and names used on one page only, as lists for review (not failures).
Exit code 0 = checks 1-3 pass.
"""
import csv, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import kisch
import gen_sch

MCU = "U201"
SDRAM = "U301"


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
    net_path = argv[0]
    only = argv[argv.index("--pages") + 1:] if "--pages" in argv else None
    scratch = os.path.join(os.path.dirname(os.path.abspath(net_path)), "_check_regen")
    sheets = gen_sch.main(only, scratch)          # regenerate into a scratch folder just to collect the intent
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
    if any(sh.page.name == "mcu" for sh in sheets):
        rows = list(csv.DictReader(open(os.path.join(HERE, "pins.csv"), encoding="utf-8")))
        wrong, used = [], 0
        for r in rows:
            net = pin_net.get((MCU, r["ball"]), "")
            if r["group"] == "FREE":
                if not net.startswith("unconnected-"):
                    wrong.append("%s %s 应悬空，实际在 %s" % (r["port"], r["ball"], net))
            else:
                used += 1
                if net != r["signal"]:
                    wrong.append("%s %s 应是 %s，实际 %s" % (r["port"], r["ball"], r["signal"], net or "没有这个引脚"))
        print("2. pins.csv 对网表：%d 个 IO，占用 %d / %d = %.1f%%，%d 处不符" % (len(rows), used, len(rows), 100.0 * used / len(rows), len(wrong)))
        print("\n".join("   " + w for w in wrong[:40]))
        bad += len(wrong)

    # 3. swap.csv
    if any(sh.page.name == "sdram" for sh in sheets):
        from sch import sdram
        balls = sdram.ball_map()
        sig_net = {sig: pin_net.get((SDRAM, ball)) for ball, sig in balls.items() if sig.startswith("DQ")}
        errs = []
        for lane in range(4):
            nets = [sig_net["DQ%d" % k] for k in range(8 * lane, 8 * lane + 8)]
            bits = sorted(int(re.sub(r"\D", "", n.replace("FMC_D", ""))) if n and n.startswith("FMC_D") else -1 for n in nets)
            byte = bits[0] // 8 if bits[0] >= 0 else -1
            if bits != list(range(8 * byte, 8 * byte + 8)):
                errs.append("字节通道 %d 上的网络不是同一个字节的 8 位：%s" % (lane, nets))
            elif sig_net["DQM%d" % lane] != "FMC_NBL%d" % byte:
                errs.append("字节通道 %d 接的是字节 %d，DQM 应是 FMC_NBL%d，实际 %s" % (lane, byte, byte, sig_net["DQM%d" % lane]))
        moved = sum(1 for k in range(32) if sig_net["DQ%d" % k] != "FMC_D%d" % k)
        print("3. 换位表对网表：4 个字节通道，%d 处不符；和不换位相比挪动了 %d 位" % (len(errs), moved))
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
