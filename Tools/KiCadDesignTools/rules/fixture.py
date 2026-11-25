"""Prove that every rule of a board does what it says (RUL-2: a clean DRC report proves nothing).

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.rules.fixture <board dir> <out dir>

Builds a fixture board from the board's own empty board (Tools.KiCadDesignTools.project.make_project: its layers
and real stackup), its .kicad_pro and its .kicad_dru; the board's rules_cases.py (build(f, cfg)) places rule areas
named like the real ones and, per case, a few objects that either obey or deliberately break one rule. DRC is run
twice: with the rule file as it is (phase "static") and after Tools.KiCadDesignTools.rules.len_rules has generated
the length windows (phase "window"). The violations of each case must be exactly the expected set. Three things DRC
cannot report are measured instead (rules_cases.py says where and what to expect): the pour-to-track distance next
to and inside a rule area, the pour connection of a through-hole and an SMD pad, and the via height that KiCad adds
to a net length.

Writes <out dir>/fixture.kicad_pcb (.kicad_pro, .kicad_dru) for looking at in KiCad and
<out dir>/rules_fixture.txt; exit code 0 = every case as expected.
"""
import json, math, os, shutil, sys
import pcbnew
from pcbnew import VECTOR2I, FromMM as mm

from Tools.KiCadDesignTools.core import config, heavy, stackup
from Tools.KiCadDesignTools.project import make_project
from Tools.KiCadDesignTools.rules import drc_probe, dru_match, len_rules

V = lambda x, y: VECTOR2I(mm(x), mm(y))
# Violation types that say nothing about the rules under test (loose track ends on a board without parts).
IGNORE = {"track_dangling", "via_dangling", "isolated_copper", "lib_footprint_issues", "lib_footprint_mismatch",
          "missing_courtyard", "silk_overlap", "silk_over_copper", "silk_edge_clearance", "text_height", "text_thickness"}


def layer_map(cfg):
    """{"L1": pcbnew.F_Cu, ...} from the board's copper layers."""
    return {l.L: getattr(pcbnew, l.kicad.replace(".", "_")) for l in cfg.layers}


class Fixture:
    def __init__(self, base_pcb, L):
        self.b = pcbnew.LoadBoard(base_pcb)
        self.L = L
        self.nets, self.owner, self.expect, self.what = {}, {}, {}, {}
        self.cur = None

    def case(self, cid, what, static=(), window=None):
        """Start a case. static / window: expected {(violation type, rule name or None)} per phase."""
        self.cur = cid
        self.what[cid] = what
        self.expect[cid] = {"static": set(static), "window": set(static if window is None else window)}

    def own(self, item):
        self.owner[item.m_Uuid.AsString()] = self.cur
        return item

    def net(self, name):
        if name not in self.nets:
            n = pcbnew.NETINFO_ITEM(self.b, name); self.b.Add(n); self.nets[name] = n
        return self.nets[name]

    def trk(self, net, p, q, w, layer="L1"):
        t = pcbnew.PCB_TRACK(self.b)
        t.SetStart(V(*p)); t.SetEnd(V(*q)); t.SetWidth(mm(w)); t.SetLayer(self.L[layer]); t.SetNet(self.net(net))
        self.b.Add(t)
        return self.own(t)

    def run(self, net, length, x, y, w=0.1016, layer="L1", chunk=100.0):
        """A net of the given total length as parallel straight pieces (KiCad sums every track of a net)."""
        while length > 1e-9:
            d = min(chunk, length)
            self.trk(net, (x, y), (x + d, y), w, layer)
            length -= d; y += 0.5
        return y

    def via(self, net, x, y, dia=0.45, drill=0.2, a="L1", c="L6", strip_inner=False):
        v = pcbnew.PCB_VIA(self.b)
        v.SetPosition(V(x, y)); v.SetWidth(pcbnew.F_Cu, mm(dia)); v.SetDrill(mm(drill))
        v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(self.L[a], self.L[c]); v.SetNet(self.net(net))
        if strip_inner:
            v.SetRemoveUnconnected(True); v.SetKeepStartEnd(True)
        self.b.Add(v)
        return self.own(v)

    def pad(self, ref, net, x, y, dia, drill=0.0, layer="L1"):
        fp = pcbnew.FOOTPRINT(self.b)
        fp.SetReference(ref); fp.SetValue(ref); fp.SetPosition(V(x, y))
        p = pcbnew.PAD(fp)
        p.SetNumber("1"); p.SetShape(pcbnew.PAD_SHAPE_CIRCLE); p.SetSize(V(dia, dia)); p.SetPosition(V(x, y))
        if drill:
            p.SetAttribute(pcbnew.PAD_ATTRIB_PTH); p.SetDrillSize(V(drill, drill)); p.SetLayerSet(p.PTHMask())
        else:
            p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
            ls = pcbnew.LSET(); ls.AddLayer(self.L[layer]); p.SetLayerSet(ls)
        p.SetNet(self.net(net)); fp.Add(p); self.b.Add(fp)
        self.own(fp); self.own(p)
        return p

    def area(self, name, box):
        z = pcbnew.ZONE(self.b)
        z.SetIsRuleArea(True); z.SetZoneName(name); z.SetLayerSet(pcbnew.LSET.AllCuMask())
        for f in ("SetDoNotAllowTracks", "SetDoNotAllowVias", "SetDoNotAllowPads", "SetDoNotAllowZoneFills", "SetDoNotAllowFootprints"):
            getattr(z, f)(False)
        self._outline(z, box); self.b.Add(z)

    def pour(self, net, layer, box, clearance):
        z = pcbnew.ZONE(self.b)
        z.SetLayer(self.L[layer]); z.SetNet(self.net(net)); z.SetLocalClearance(mm(clearance)); z.SetMinThickness(mm(0.2))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_NEVER)
        self._outline(z, box); self.b.Add(z)
        return z

    @staticmethod
    def _outline(z, box):
        x1, y1, x2, y2 = box
        ch = pcbnew.SHAPE_LINE_CHAIN()
        for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
            ch.Append(mm(x), mm(y))
        ch.SetClosed(True)
        z.Outline().AddOutline(ch)

    def edge(self, box):
        x1, y1, x2, y2 = box
        for p, q in (((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)), ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))):
            s = pcbnew.PCB_SHAPE(self.b); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(V(*p)); s.SetEnd(V(*q)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); self.b.Add(s)


def copper(board, layer):
    """Filled copper of all pours on a (KiCad) layer, as one simplified polygon set."""
    ps = pcbnew.SHAPE_POLY_SET()
    for z in board.Zones():
        if not z.GetIsRuleArea() and z.IsOnLayer(layer):
            ps.Append(z.GetFilledPolysList(layer))
    ps.Simplify()
    return ps


def measure(pcb, cases, L):
    """[(case, text, ok)] for what DRC cannot report."""
    b = pcbnew.LoadBoard(pcb)
    cu = copper(b, L[cases.POUR_LAYER])
    inside = lambda x, y: cu.Contains(V(x, y))
    lo, hi = cases.POUR_GAP_RANGE
    out = []
    for cid, (x, y, w) in cases.POUR_GAPS:
        # first distance from the track edge at which copper starts, 0.01 mm steps
        d = next((k / 100 for k in range(1, 60) if inside(x, y + w / 2 + k / 100)), None)
        out.append((cid, "铺地离走线边 %s mm（%s）" % (d, cases.POUR_GAP_NOTE), d is not None and lo <= d <= hi))
    for cid, (x, y, r), want in cases.PAD_CONNECTIONS:
        hits = sum(inside(x + (r + 0.12) * math.cos(a * math.pi / 8), y + (r + 0.12) * math.sin(a * math.pi / 8)) for a in range(16))
        kind = "solid" if hits == 16 else "thermal" if 0 < hits < 16 else "isolated"
        out.append((cid, "焊盘外 0.12 mm 一圈 16 个点里 %d 个是铜：%s" % (hits, {"solid": "全连接", "thermal": "花焊盘", "isolated": "没连上"}[kind]), kind == want))
    return out


def classify(report, f):
    """{case: {(type, rule)}} and the violations that belong to no case."""
    got, stray = {c: set() for c in f.expect}, []
    for v in report["violations"]:
        if v["type"] in IGNORE:
            continue
        cases = {f.owner[i["uuid"]] for i in v["items"] if i.get("uuid") in f.owner}
        if not cases:
            stray.append("%s %s" % (v["type"], v["description"]))
        for c in cases:
            got[c].add((v["type"], drc_probe.rule_of(v)))
    return got, stray


def main(board_dir, out):
    cfg = config.load(board_dir)
    cases = cfg.module("rules_cases")
    L = layer_map(cfg)
    st = stackup.for_board(cfg)
    os.makedirs(out, exist_ok=True)
    stem = os.path.join(out, "fixture")
    base = os.path.join(out, "base.kicad_pcb")
    make_project.make_pcb(cfg, base)
    f = Fixture(base, L)
    cases.build(f, cfg)
    pcbnew.SaveBoard(stem + ".kicad_pcb", f.b)
    os.remove(base)
    # after SaveBoard: pcbnew writes a default .kicad_pro next to a board it saves
    shutil.copy(cfg.pro, stem + ".kicad_pro")
    # the static phase is the hand-written part only: the real board's generated block (its windows and fixed rules)
    # is emptied here and regenerated for the fixture by len_rules before the window phase
    dru = open(cfg.dru, encoding="utf-8").read()
    i, j = len_rules.begin_index(dru), dru.index(len_rules.END)
    open(stem + ".kicad_dru", "w", encoding="utf-8", newline="\n").write(dru[:i] + len_rules.BEGIN + "\n" + dru[j:])
    shutil.copy(os.path.join(cfg.dir, "length_groups.json"), os.path.join(out, "length_groups.json"))
    # fill the pour once and keep it in the board file
    heavy.kicad_cli("pcb", "drc", "--refill-zones", "--save-board", "--severity-all", "--format", "json",
                    "-o", os.path.join(out, "fill.json"), stem + ".kicad_pcb", outputs=[os.path.join(out, "fill.json")])
    os.remove(os.path.join(out, "fill.json"))

    lines, bad = [], 0
    def check(ok, text):
        nonlocal bad
        bad += not ok
        lines.append(("ok   " if ok else "FAIL ") + text)

    canary = heavy.kicad_py("Tools.KiCadDesignTools.rules.dru_canary", os.path.abspath(stem + ".kicad_pcb"), text=True)
    check(canary.returncode == 0, "金丝雀：" + canary.stdout.strip())

    static = classify(drc_probe.run_drc(stem + ".kicad_pcb"), f)
    lr = heavy.kicad_py("Tools.KiCadDesignTools.rules.len_rules", os.path.abspath(stem + ".kicad_pcb"), encoding="utf-8")
    lines.append(lr.stdout.strip())
    for texts, code, what in cases.LEN_RULES:
        check(all(t in lr.stdout for t in texts) and (code is None or lr.returncode == code), what)
    window = classify(drc_probe.run_drc(stem + ".kicad_pcb"), f)

    for phase, (got, stray) in (("static", static), ("window", window)):
        for s in sorted(set(stray)):
            check(False, "[%s] 不属于任何用例的违规：%s" % (phase, s))
    show = lambda s: "、".join("%s（%s）" % (t, r or "板级 / 网络类") for t, r in sorted(s, key=str)) or "无违规"
    for cid in f.expect:
        e, gs, gw = f.expect[cid], static[0][cid], window[0][cid]
        ok = gs == e["static"] and gw == e["window"]
        text = "%s %s：%s" % (cid, f.what[cid], show(gw))
        if e["static"] != e["window"]:
            text += "；生成窗口前：%s" % show(gs)
        if not ok:
            text += "  <-- 预期 %s；生成窗口前预期 %s，实际 %s" % (show(e["window"]), show(e["static"]), show(gs))
        check(ok, text)

    for cid, text, ok in measure(stem + ".kicad_pcb", cases, L):
        check(ok, "%s 实测：%s" % (cid, text))
    got = drc_probe.measure_lengths(stem + ".kicad_pcb", {cid: "A.NetName == '%s'" % net for cid, net, *_ in cases.VIA_LENGTHS})
    whole = st.via_height(cfg.layers[0].kicad, cfg.layers[-1].kicad)
    for cid, net, base_len, n, (la, lb), note in cases.VIA_LENGTHS:
        h = st.via_height(cfg.kicad(la), cfg.kicad(lb))
        d = got[cid].get(net)
        check(d is not None and abs(d - (base_len + n * h)) < 0.0005,
              "%s 实测：KiCad 量到 %s mm，按叠层算 %s + %d × %.4f = %.4f mm（%s）" % (
                  cid, d, base_len, n, h, base_len + n * h, note.format(whole=whole)))

    rows, loaded = dru_match.match(stem + ".kicad_pcb")
    empty = [r["rule"] for r in rows if r["matched"] == 0]
    check(loaded and not empty, "基准板上每条规则都匹配到对象：%d 条规则，空匹配 %d 条%s" % (len(rows), len(empty), "（" + "、".join(empty) + "）" if empty else ""))
    never = sorted({n for n, _, _ in drc_probe.parse_rules(open(stem + ".kicad_dru", encoding="utf-8").read())}
                   - {r for ph in (static, window) for s in ph[0].values() for _, r in s} - set(cases.MEASURED_RULES))
    lines.append("没有被任何用例触发过的规则：%s" % ("、".join(never) if never else "无"))
    lines.insert(0, "规则基准板：%d 个用例，%d 项不符" % (len(f.expect), bad))
    open(os.path.join(out, "rules_fixture.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(lines))
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
