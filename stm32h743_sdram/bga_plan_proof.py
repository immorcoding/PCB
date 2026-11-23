"""The proof of a bga_plan.py plan: draw it with scripts/busroute on a copy of the board (never the real file).

    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\bga_plan_proof.py base
        out/plan/base/: a copy of the real board with the fills removed and the groups sdram, power_bga, mcu_east
        and mcu_south stripped (copper_report.py); its dump is out/plan/geo.json, the planner's state.
    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\bga_plan_proof.py build out/plan/<N>/plan.json [--fast] [--no-slots]
        out/plan/<N>/proof/board0   the base copy with the SDRAM and the bottom parts where the plan puts them
        out/plan/<N>/routes_plan_power.py, routes_plan_signals.py   generated routes files (SKETCH, OPEN_ENDS)
        out/plan/<N>/proof/power, proof/signals   the two busroute builds, the second on the first's board
        out/plan/<N>/proof/slots    the plane slots of the refilled final copy (copper_report.py slots)
        out/plan/<N>/proof/summary.json and a one-screen summary on stdout
The plan counts only when the signals build has no GAP / PITCH / HOLE / VIAPAD / CROSS / PATH finding.
"""
import json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
N = "stm32h743_sdram"
PY = sys.executable
CLI = os.path.join(os.path.dirname(sys.executable), "kicad-cli.exe")
BASE = os.path.join(HERE, "out", "plan", "base")
GROUPS = ["sdram", "power_bga", "mcu_east", "mcu_south"]


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, **kw)
    out = (r.stdout + r.stderr).decode("utf-8", "replace")
    return r.returncode, "\n".join(l for l in out.splitlines() if "image handler" not in l)


def base():
    os.makedirs(BASE, exist_ok=True)
    for ext in (".kicad_pcb", ".kicad_pro", ".kicad_dru", ".busroute.json"):
        shutil.copyfile(os.path.join(HERE, N + ext), os.path.join(BASE, N + ext))
    b = os.path.join(BASE, N + ".kicad_pcb")
    print(run([PY, os.path.join(HERE, "copper_report.py"), "unfill", b])[1])
    print(run([PY, os.path.join(HERE, "copper_report.py"), "strip", b] + GROUPS)[1])
    sys.path.insert(0, HERE)
    import bga_plan_dump
    bga_plan_dump.dump(b, os.path.join(HERE, "out", "plan", "geo.json"))


def place(plan, board0):
    """Move the SDRAM, its rule areas and L3 block, and the bottom parts to where the plan has them."""
    import pcbnew
    pro = board0[:-len(".kicad_pcb")] + ".kicad_pro"
    keep = open(pro, "rb").read()
    b = pcbnew.LoadBoard(board0)
    V = lambda x, y: pcbnew.VECTOR2I(pcbnew.FromMM(100.0 + x), pcbnew.FromMM(100.0 + y))
    sd = plan["sdram"]
    u = b.FindFootprintByReference("U301")
    u.SetPosition(V(*sd["pos"]))
    u.SetOrientationDegrees(sd["rot"])
    A = sd["area"]
    for z in b.Zones():
        if z.GetZoneName() in ("BGA_SDRAM", "NOPOUR_L1_SDRAM", "cu:L3_3V3_SDRAM"):
            o = z.Outline()
            bb = o.BBox()
            cur = [pcbnew.ToMM(bb.GetLeft()) - 100, pcbnew.ToMM(bb.GetTop()) - 100, pcbnew.ToMM(bb.GetRight()) - 100, pcbnew.ToMM(bb.GetBottom()) - 100]
            new = list(A)
            if z.GetZoneName() == "cu:L3_3V3_SDRAM":           # the block keeps its strip to the north (the feed)
                new[1] = min(cur[1], A[1]) if abs(cur[0] - A[0]) < 1e-6 else A[1] - (29.5 - cur[1])
            if all(abs(a_ - c_) < 1e-6 for a_, c_ in zip(cur, new)):
                continue
            o.RemoveAllContours()
            o.NewOutline()
            for x, y in ((new[0], new[1]), (new[2], new[1]), (new[2], new[3]), (new[0], new[3])):
                o.Append(V(x, y))
    # the swap: every SDRAM ball carries the net the plan ends on it; data balls the plan left open take the
    # lane's remaining nets in order, so the netlist stays a permutation inside each byte lane (SPEC 9)
    want = {d["sd_ball"]: (n if n != "FMC_SDCLK" else "FMC_SDCLK_R") for n, d in plan["signals"].items() if d.get("sd_ball")}
    pads = {p.GetNumber(): p for p in u.Pads()}
    lane_of = lambda n: ("D", int(n[5:]) // 8) if (n.startswith("FMC_D") and n[5:].isdigit()) else None
    data_balls = sorted(k for k, p in pads.items() if lane_of(p.GetNetname()))
    data_nets = sorted(p.GetNetname() for p in pads.values() if lane_of(p.GetNetname()))
    left_nets = [n for n in data_nets if n not in want.values()]
    left_balls = [k for k in data_balls if k not in want]
    by_lane_balls = {}
    for k in left_balls:                                            # an open ball keeps a net of the lane it had
        by_lane_balls.setdefault(lane_of(pads[k].GetNetname()), []).append(k)
    for n in left_nets:
        lst = by_lane_balls.get(lane_of(n)) or next((v for v in by_lane_balls.values() if v), None)
        want[lst.pop(0)] = n
    netinfo = b.GetNetInfo()
    for k, n in sorted(want.items()):
        if pads[k].GetNetname() != n:
            pads[k].SetNet(netinfo.GetNetItem(n))
    moved = []
    for c in plan["caps"]:
        f = b.FindFootprintByReference(c["ref"])
        if f is None:
            raise SystemExit("no part %s on the board" % c["ref"])
        f.SetPosition(V(*c["pos"]))
        f.SetOrientationDegrees(c["rot"])
        moved.append(c["ref"])
    pcbnew.SaveBoard(board0, b)
    open(pro, "wb").write(keep)
    # read back: the pads are where the plan thinks they are
    b = pcbnew.LoadBoard(board0)
    worst = 0.0
    for c in plan["caps"]:
        f = b.FindFootprintByReference(c["ref"])
        for p in f.Pads():
            k = int(p.GetNumber()) - 1
            q = p.GetPosition()
            d = max(abs(pcbnew.ToMM(q.x) - 100 - c["pads"][k][0]), abs(pcbnew.ToMM(q.y) - 100 - c["pads"][k][1]))
            if p.GetNetname() != c["nets"][k]:
                raise SystemExit("%s.%s is on %s, the plan has %s" % (c["ref"], p.GetNumber(), p.GetNetname(), c["nets"][k]))
            worst = max(worst, d)
    if worst > 0.002:
        raise SystemExit("bottom parts are not where the plan has their pads (worst %.4f mm)" % worst)
    return moved


POWER_PY = '''"""Generated by bga_plan_proof.py from %(plan)s: supply / ground ball vias and the bottom parts' own vias. Do not edit."""
import json
BOARD = %(board)r
ORIGIN = (100, 100)
GROUP = "plan_power"
SKETCH = True
SHARED = True
OPEN_ENDS = True
YIELD_NETS = ["GND"]
PROFILE = {"area_free_classes": ["PWR"]}
ALLOW_VIA_ON = %(allow)r
VIEWS = %(views)r


def routes(job):
    P = json.load(open(%(plan)r, encoding="utf-8"))
    out = {}
    for net, chains in P["power_routes"].items():
        out[net] = [[("via", tuple(pc[1])) if pc[0] == "via" else (pc[0], [q if isinstance(q, str) else tuple(q) for q in pc[1]]) + tuple(pc[2:3]) for pc in ch] for ch in chains]
    return out
'''

SIGNAL_PY = '''"""Generated by bga_plan_proof.py from %(plan)s: every planned signal net (sketch). Do not edit."""
import json
BOARD = %(board)r
ORIGIN = (100, 100)
GROUP = "plan_signals"
SKETCH = True
OPEN_ENDS = True
YIELD_NETS = ["GND"]
NETS = %(nets)r
GROUPS = %(groups)r
VIEWS = %(views)r
PROFILE = {"area_free_classes": ["XTAL"]}        # the crystal tracks keep 0.254 inside the rule area (no exception: SPEC 7)


def routes(job):
    P = json.load(open(%(plan)r, encoding="utf-8"))
    out = {}
    for net, d in P["signals"].items():
        if not d["drawn"]:
            continue
        for n2, pcs in d["routes"].items():
            out[n2] = [("via", tuple(pc[1])) if pc[0] == "via" else (pc[0], [q if isinstance(q, str) else tuple(q) for q in pc[1]]) for pc in pcs]
    return out
'''


def build(plan_path, fast=False, slots=True):
    plan_path = os.path.abspath(plan_path)
    plan = json.load(open(plan_path, encoding="utf-8"))
    D = os.path.dirname(plan_path)
    proof = os.path.join(D, "proof")
    b0 = os.path.join(proof, "board0")
    shutil.rmtree(proof, ignore_errors=True)
    os.makedirs(b0)
    for ext in (".kicad_pcb", ".kicad_pro", ".kicad_dru", ".busroute.json"):
        shutil.copyfile(os.path.join(BASE, N + ext), os.path.join(b0, N + ext))
    place(plan, os.path.join(b0, N + ".kicad_pcb"))
    A = plan["sdram"]["area"]
    views = [("mcu", 33.0, 30.0, 47.0, 44.0, 90), ("sdram", A[0] - 1, A[1] - 1, A[2] + 1, A[3] + 1, 80), ("all", 26.0, 22.0, 70.0, 52.0, 30)]
    allow = sorted("%s.%d" % (c["ref"], k + 1) for c in plan["caps"] for k in range(2)) + [
        "C218.1", "C218.2", "C219.1", "C219.2", "C220.1", "C220.2", "C221.1", "C222.1", "C222.2", "C223.1", "FB201.1", "FB201.2"]   # the fixed parts under the MCU
    rp = os.path.join(D, "routes_plan_power.py")
    open(rp, "w", encoding="utf-8", newline="\n").write(POWER_PY % dict(plan=plan_path.replace("\\", "/"), board="proof/board0/%s.kicad_pcb" % N, allow=allow, views=views))
    nets = sorted(n2 for d in plan["signals"].values() if d["drawn"] for n2 in d["routes"])
    lanes = {"lane%s" % k: sorted(n for n in t["members"] if plan["signals"][n]["drawn"]) for k, t in plan["tuning"].items()}
    rs = os.path.join(D, "routes_plan_signals.py")
    open(rs, "w", encoding="utf-8", newline="\n").write(SIGNAL_PY % dict(plan=plan_path.replace("\\", "/"), board="proof/power/%s.kicad_pcb" % N, nets=nets,
                                                                          groups={k: v for k, v in lanes.items() if v}, views=views))
    summary = {"plan": plan["name"]}
    bp = os.path.join(ROOT, "scripts", "busroute", "build.py")
    for name, rf in (("power", rp), ("signals", rs)):
        out = os.path.join(proof, name)
        cmd = [PY, bp, rf, "--sketch", "--out", out] + (["--no-refill", "--no-pictures"] if name == "power" else []) + (["--fast"] if fast and name == "signals" else [])
        code, text = run(cmd)
        os.makedirs(out, exist_ok=True)
        open(os.path.join(out, "build.txt"), "w", encoding="utf-8").write(text)
        mj = os.path.join(out, "metrics.json")
        summary[name] = {"exit": code, "tail": text.splitlines()[-1] if text else ""}
        hard = [l for l in text.splitlines() if l.startswith("  ! ")]
        summary[name]["hard_findings"] = len(hard)
        summary[name]["hard_kinds"] = sorted({l.split()[1] for l in hard})
        summary[name]["lines"] = [l for l in text.splitlines() if l.startswith("[") or l.startswith("结论")]
        print("== %s: exit %d, %d findings that stop a build %s" % (name, code, len(hard), summary[name]["hard_kinds"]))
        for l in hard[:25]:
            print(l)
        for l in summary[name]["lines"]:
            print("   " + l)
        if name == "power" and not os.path.isfile(os.path.join(out, N + ".kicad_pcb")):
            print(text[-3000:])
            raise SystemExit("the power build wrote no board")
    final = os.path.join(proof, "signals", N + ".kicad_pcb")
    if slots and not fast and os.path.isfile(final):
        sd = os.path.join(proof, "slots")
        os.makedirs(sd, exist_ok=True)
        code, text = run([CLI, "pcb", "drc", "--refill-zones", "--save-board", "--severity-all", "--format", "json", "-o", os.path.join(sd, "drc.json"), final])
        code, text = run([PY, os.path.join(HERE, "copper_report.py"), "slots", final, sd, "--window", "BUS", "26", "22", "70", "52"])
        open(os.path.join(sd, "slots_run.txt"), "w", encoding="utf-8").write(text)
        sj = os.path.join(sd, "slots.json")
        if os.path.isfile(sj):
            s = json.load(open(sj, encoding="utf-8"))
            summary["slots"] = {"longest": {k: v["length"] for k, v in s["longest"].items()}, "cut_off": len(s["cut_off"]),
                                "over_3.0": [[r["layer"], r["length"], r["ends"]] for r in s["slots"] if r["length"] > 3.0]}
            print("== slots (refilled copy): longest %s, cut-off vias %d, over 3.0 mm: %d" % (summary["slots"]["longest"], summary["slots"]["cut_off"], len(summary["slots"]["over_3.0"])))
        else:
            print(text[-1500:])
    json.dump(summary, open(os.path.join(proof, "summary.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return summary


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "base":
        base()
    elif len(a) >= 2 and a[0] == "build":
        build(a[1], fast="--fast" in a, slots="--no-slots" not in a)
    else:
        print(__doc__)
        sys.exit(2)
