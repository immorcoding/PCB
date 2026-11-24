"""Prove that every rule of this board does what it says (RUL-2: a clean DRC report proves nothing).

    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\rules_fixture.py <out dir>

Builds a fixture board from the project's own empty board (so it has the real stackup), its .kicad_pro
and its .kicad_dru: two rule areas named like the real ones and, per case, a few objects that either
obey or deliberately break one rule. DRC is run twice: with the rule file as it is (phase "static")
and after scripts/len_rules.py has generated the length windows (phase "window"). The violations of
each case must be exactly the expected set. Three things DRC cannot report are measured instead:
the pour-to-track distance next to and inside a rule area, the pour connection of a through-hole and
an SMD pad, and the via height that KiCad adds to a net length.

Writes <out dir>/fixture.kicad_pcb (.kicad_pro, .kicad_dru) for looking at in KiCad and
<out dir>/rules_fixture.txt; exit code 0 = every case as expected.
"""
import json, math, os, shutil, subprocess, sys
import pcbnew
from pcbnew import VECTOR2I, FromMM as mm

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))                     # interim (Tools/ consolidation stage 1): the repository root, for Tools.KiCadDesignTools
sys.path.insert(0, HERE)
from Tools.KiCadDesignTools.rules import drc_probe, dru_match, len_rules
import make_project

NAME = "stm32h743_sdram"
PY = sys.executable
L = {"L1": pcbnew.F_Cu, "L2": pcbnew.In1_Cu, "L3": pcbnew.In2_Cu, "L4": pcbnew.In3_Cu, "L5": pcbnew.In4_Cu, "L6": pcbnew.B_Cu}
V = lambda x, y: VECTOR2I(mm(x), mm(y))
MCU = (10, 10, 22, 22)        # rule area BGA_MCU, x1 y1 x2 y2
RAM = (30, 10, 40, 25)        # rule area BGA_SDRAM
# Violation types that say nothing about the rules under test (loose track ends on a board without parts).
IGNORE = {"track_dangling", "via_dangling", "isolated_copper", "lib_footprint_issues", "lib_footprint_mismatch",
          "missing_courtyard", "silk_overlap", "silk_over_copper", "silk_edge_clearance", "text_height", "text_thickness"}


class Fixture:
    def __init__(self, base_pcb):
        self.b = pcbnew.LoadBoard(base_pcb)
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
        t.SetStart(V(*p)); t.SetEnd(V(*q)); t.SetWidth(mm(w)); t.SetLayer(L[layer]); t.SetNet(self.net(net))
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
        v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(L[a], L[c]); v.SetNet(self.net(net))
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
            ls = pcbnew.LSET(); ls.AddLayer(L[layer]); p.SetLayerSet(ls)
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
        z.SetLayer(L[layer]); z.SetNet(self.net(net)); z.SetLocalClearance(mm(clearance)); z.SetMinThickness(mm(0.2))
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


def build(f):
    f.edge((0, 0, 110, 150))
    f.area("BGA_MCU", MCU); f.area("BGA_SDRAM", RAM)
    W, C = "track_width", "clearance"
    X = 50.0                                  # x of the cases outside the rule areas

    # ---- track width
    f.case("w01", "默认类 0.2032 在区外"); f.trk("N1", (X, 30), (X + 8, 30), 0.2032)
    f.case("w02", "默认类 0.09 在区外：低于 0.1016", {(W, "signal_width")}); f.trk("N2", (X, 31), (X + 8, 31), 0.09)
    f.case("w03", "0.09 整段在 MCU 区内"); f.trk("N3", (12, 12), (16, 12), 0.09)
    f.case("w04", "0.1016 整段在 MCU 区内：区内只能 0.09", {(W, "bga_width_inside")}); f.trk("N4", (12, 13), (16, 13), 0.1016)
    f.case("w05", "0.09 跨过 MCU 区的边"); f.trk("N5", (20, 14), (23, 14), 0.09)
    f.case("w06", "0.09 出区 0.3 mm 后换成 0.1016（脚本的换宽做法）")
    f.trk("N6", (19, 15), (22.3, 15), 0.09); f.trk("N6", (22.3, 15), (26, 15), 0.1016)
    f.case("w07", "PWR 类 0.127 在区外：低于 0.1524", {(W, "pwr_width")}); f.trk("+3V3", (X, 32), (X + 8, 32), 0.127)
    f.case("w08", "PWR 类 0.3 整段在 MCU 区内（电源线在区内不限 0.09）"); f.trk("+3V3", (12, 16), (16, 16), 0.3)
    f.case("w09", "晶振线 0.254 从区内直接出区"); f.trk("HSE_IN", (10.6, 18), (8, 18), 0.254)
    f.case("w10", "晶振线 0.2 在区内：晶振线固定 0.254，没有区内例外", {(W, "xtal_width")}); f.trk("HSE_OUT", (12, 19), (16, 19), 0.2)
    f.case("w11", "默认类 1.0 在区外：超过 0.8128", {(W, "signal_width")}); f.trk("N7", (X, 33.5), (X + 8, 33.5), 1.0)
    f.case("w12", "0.09 整段在 SDRAM 区内"); f.trk("N8", (32, 12), (36, 12), 0.09)
    f.case("w13", "0.1016 整段在 SDRAM 区内", {(W, "bga_width_inside")}); f.trk("N9", (32, 13), (36, 13), 0.1016)
    f.case("w14", "总线类（RMII）0.1016 在区外"); f.trk("RMII_TX_EN", (X, 35), (X + 8, 35), 0.1016)
    f.case("w15", "总线类（RMII）0.09 在区外", {(W, "bus_width")}); f.trk("RMII_TX_EN", (X, 36), (X + 8, 36), 0.09)

    f.case("w16", "0.05 跨过 MCU 区的边：碰到规则区也不能低于 0.09", {(W, "bga_width")}); f.trk("N17", (20, 17), (23, 17), 0.05)
    # L3 (In2.Cu) is a signal layer since 2026-11-23: no rule names a layer, so a track there is checked as on L4 (In3.Cu)
    f.case("w17", "默认类 0.09 在 L3 区外：低于 0.1016（和 w18 的 L4 相同）", {(W, "signal_width")}); f.trk("N18", (X, 37), (X + 8, 37), 0.09, "L3")
    f.case("w18", "默认类 0.09 在 L4 区外：低于 0.1016", {(W, "signal_width")}); f.trk("N19", (X, 38), (X + 8, 38), 0.09, "L4")
    f.case("w19", "0.1016 整段在 MCU 区内、L3 上：区内只能 0.09", {(W, "bga_width_inside")}); f.trk("N70", (12, 14), (16, 14), 0.1016, "L3")

    # ---- vias
    D, H, A = "via_diameter", "drill_out_of_range", "annular_width"
    f.case("v01", "过孔 0.45 / 0.2 在区外"); f.via("N10", X, 40)
    f.case("v02", "小过孔 0.30 / 0.15 在区外", {(D, "via_size"), (H, "via_size"), (A, "via_size")}); f.via("N11", X + 2, 40, 0.30, 0.15)
    f.case("v03", "小过孔 0.30 / 0.15 整个在 MCU 区内"); f.via("N12", 12, 20, 0.30, 0.15)
    f.case("v04", "小过孔压在 MCU 区的边上：不算区内", {(D, "via_size"), (H, "via_size"), (A, "via_size")}); f.via("N13", 22.0, 20, 0.30, 0.15)
    f.case("v05", "0.25 / 0.15 在区内：小于批准的 0.30", {(D, "bga_via"), (A, "bga_via")}); f.via("N14", 14, 20, 0.25, 0.15)
    f.case("v06", "小过孔整个在 SDRAM 区内"); f.via("N15", 32, 20, 0.30, 0.15)
    f.case("v07", "0.30 / 0.10 在区内：孔小于 0.15", {(H, "bga_via")}); f.via("N16", 16, 20, 0.30, 0.10)

    # ---- clearance (edge to edge)
    def pair(na, nb, x, y, w, gap, length=4, layer="L1"):
        f.trk(na, (x, y), (x + length, y), w, layer); f.trk(nb, (x, y + w + gap), (x + length, y + w + gap), w, layer)
    f.case("c01", "区内两根 0.09 的线，间距 0.10"); pair("N20", "N21", 17, 11, 0.09, 0.10, 3)
    f.case("c02", "区内间距 0.08：低于 0.09", {(C, "bga_clearance")}); pair("N22", "N23", 17, 12, 0.09, 0.08, 3)
    f.case("c03", "区外间距 0.10：低于网络类的 0.127", {(C, "Default")}); pair("N24", "N25", X, 44, 0.1016, 0.10)
    f.case("c04", "区外间距 0.13"); pair("N26", "N27", X, 45, 0.1016, 0.13)
    f.case("c05", "L3 区外间距 0.10：低于网络类的 0.127（同 c03）", {(C, "Default")}); pair("N28", "N29", X, 46.5, 0.1016, 0.10, layer="L3")

    # ---- corners, short segments
    f.case("k01", "90° 拐角", {("track_angle", "corner_angle")})
    f.trk("N30", (X, 48), (X + 3, 48), 0.2); f.trk("N30", (X + 3, 48), (X + 3, 50), 0.2)
    f.case("k02", "45° 拐角")
    f.trk("N31", (X + 6, 48), (X + 9, 48), 0.2); f.trk("N31", (X + 9, 48), (X + 11, 50), 0.2)
    f.case("s01", "0.05 mm 的短线段", {("track_segment_length", "min_segment")})
    f.trk("N32", (X, 52), (X + 3, 52), 0.2); f.trk("N32", (X + 3, 52), (X + 3.05, 52), 0.2); f.trk("N32", (X + 3.05, 52), (X + 6, 52), 0.2)

    # ---- holes
    f.case("h01", "过孔的孔到内层走线 0.19（过孔在该层没有焊盘）：低于 0.2", {("hole_clearance", None)})
    f.via("N40", X, 56, strip_inner=True); f.trk("N41", (X - 2, 56 + 0.1 + 0.19 + 0.0508), (X + 2, 56 + 0.1 + 0.19 + 0.0508), 0.1016, "L4")
    f.case("h02", "过孔的孔到内层走线 0.21")
    f.via("N42", X + 6, 56, strip_inner=True); f.trk("N43", (X + 4, 56 + 0.1 + 0.21 + 0.0508), (X + 8, 56 + 0.1 + 0.21 + 0.0508), 0.1016, "L4")
    f.case("h08", "过孔的孔到 L3 走线 0.19（同 h01 的 L4）：低于 0.2", {("hole_clearance", None)})
    f.via("N71", X + 12, 56, strip_inner=True); f.trk("N72", (X + 10, 56 + 0.1 + 0.19 + 0.0508), (X + 14, 56 + 0.1 + 0.19 + 0.0508), 0.1016, "L3")
    f.case("h09", "过孔的孔到 L3 走线 0.21")
    f.via("N73", X + 18, 56, strip_inner=True); f.trk("N74", (X + 16, 56 + 0.1 + 0.21 + 0.0508), (X + 20, 56 + 0.1 + 0.21 + 0.0508), 0.1016, "L3")
    f.case("h03", "插件孔（孔 1.0、盘 1.2）到走线 0.25：插件孔要 0.3", {("hole_clearance", "pth_hole_clearance")})
    f.pad("H3", "N44", X, 60, 1.2, 1.0); f.trk("N45", (X - 2, 60 + 0.5 + 0.25 + 0.0508), (X + 2, 60 + 0.5 + 0.25 + 0.0508), 0.1016)
    f.case("h04", "插件孔到走线 0.32")
    f.pad("H4", "N46", X + 6, 60, 1.2, 1.0); f.trk("N47", (X + 4, 60 + 0.5 + 0.32 + 0.0508), (X + 8, 60 + 0.5 + 0.32 + 0.0508), 0.1016)
    f.case("h05", "两个插件孔孔边到孔边 0.40：低于 0.45", {("hole_to_hole", "pth_hole_to_hole")})
    f.pad("H5A", "N48", X, 64, 1.2, 1.0); f.pad("H5B", "N48", X + 1.4, 64, 1.2, 1.0)
    f.case("h06", "两个插件孔孔边到孔边 0.50")
    f.pad("H6A", "N49", X + 6, 64, 1.2, 1.0); f.pad("H6B", "N49", X + 7.5, 64, 1.2, 1.0)

    f.case("h07", "孔径 3.5 mm：超过 3.3", {("drill_out_of_range", "hole_range")}); f.pad("H7", "N50", X + 14, 62, 5.0, 3.5)

    # ---- Ethernet pair
    ew, eg = make_project.ETH_PAIR
    f.case("e01", "差分对 %g / %g，两根等长" % (ew, eg)); pair("ETH_TX_P", "ETH_TX_N", X, 68, ew, eg, 10)
    f.case("e02", "差分对：对内间距 0.14、对内差 2 mm、另有一段线宽 0.15",
           {(W, "eth_width"), ("skew_out_of_range", "eth_skew"), ("diff_pair_gap_out_of_range", "eth_gap")})
    f.trk("ETH_RX_P", (X, 70), (X + 10, 70), ew); f.trk("ETH_RX_N", (X, 70 + ew + 0.14), (X + 13, 70 + ew + 0.14), ew)
    f.trk("ETH_RX_P", (X, 72), (X + 1, 72), 0.15)

    # ---- lengths and via counts. Every net is on its own rows from y = 80 down, x = 5.
    LEN, SK, VC = "length_out_of_range", "skew_out_of_range", "too_many_vias"
    y = 80.0
    def net_len(cid, what, net, length, static=(), window=None):
        nonlocal y
        f.case(cid, what, static, window)
        y = f.run(net, length, 5, y) + 0.5
    net_len("l01", "SDCLK 串阻前一段 3 mm", "FMC_SDCLK", 3)
    net_len("l02", "SDCLK 串阻后一段 17 mm（合计 20 mm，由脚本报）", "FMC_SDCLK_R", 17)
    # byte lanes: longest minus shortest <= 1.27 mm (user 2026-11-24, 50 mil; 20 mm from 2026-11-23, 5 mm before)
    net_len("l03", "通道 0 数据线 24.5 mm：比本组最长的短 0.5 mm，在 1.27 mm 之内，不报", "FMC_D0", 24.5)
    net_len("l04", "通道 0 数据线 24 mm：比本组最长的短 1.0 mm，在 1.27 mm 之内，不报", "FMC_D1", 24)
    net_len("l05", "通道 0 的 NBL0 25 mm：本组最长，证明 NBL 在组里", "FMC_NBL0", 25)
    net_len("l06", "通道 0 数据线 23.5 mm：比本组最长的短 1.5 mm，超过 1.27 mm", "FMC_D2", 23.5, {(SK, "sdram_lane0")})
    net_len("l07", "通道 1 数据线 35 mm：比通道 0 最长的长 10 mm，不同组不比", "FMC_D8", 35)
    net_len("l08", "通道 1 数据线 34 mm：比本组最长的短 1.0 mm，在 1.27 mm 之内，不报", "FMC_D9", 34)
    net_len("l0n", "通道 1 数据线 33.5 mm：比 D8 短 1.5 mm，超过 1.27 mm", "FMC_D11", 33.5, {(SK, "sdram_lane1")})
    net_len("l09", "通道 2 数据线 30.5 mm：比 D17 短 1.5 mm，超过 1.27 mm", "FMC_D16", 30.5, {(SK, "sdram_lane2")})
    net_len("l0a", "通道 2 数据线 32 mm：本组最长，不报", "FMC_D17", 32)
    net_len("l0p", "通道 2 数据线 31 mm：比 D17 短 1.0 mm，在 1.27 mm 之内，不报", "FMC_D18", 31)
    net_len("l0b", "通道 3 的 NBL3 40 mm", "FMC_NBL3", 40)
    net_len("l0c", "通道 3 数据线 38.5 mm：比 NBL3 短 1.5 mm，超过 1.27 mm", "FMC_D24", 38.5, {(SK, "sdram_lane3")})
    net_len("l0o", "通道 3 数据线 39 mm：比 NBL3 短 1.0 mm，在 1.27 mm 之内，不报", "FMC_D25", 39)
    net_len("l0d", "地址线 61 mm：超过 60 mm；生成段的 sdram_addr_window（时钟 ± 20 mm，上限仍 60）压过 sdram_len_max", "FMC_A0", 61,
            {(LEN, "sdram_len_max")}, {(LEN, "sdram_addr_window")})
    net_len("l0e", "地址线 8 mm：比时钟（20 mm）短 12 mm，在 20 mm 之内，不报", "FMC_A1", 8)
    net_len("l0k", "地址线 41 mm：比时钟长 21 mm：只有生成段时报（用户 2026-11-23 定 ± 20 mm）", "FMC_A4", 41, (), {(LEN, "sdram_addr_window")})
    net_len("l0l", "命令线 SDNWE 39 mm：比时钟长 19 mm，不报（命令线也在组里，见 l0m）", "FMC_SDNWE", 39)
    net_len("l0m", "命令线 SDCKE0 42 mm：比时钟长 22 mm，生成段报", "FMC_SDCKE0", 42, (), {(LEN, "sdram_addr_window")})
    f.case("l0f", "地址线 14 mm 加 4 个 L1–L4 过孔（最后一个只接一层）：地址线不限过孔数；长度 14 + 3 × 过孔高度")
    for i in range(4):
        f.trk("FMC_A2", (5 + 3.5 * i, y), (5 + 3.5 * i + 3.5, y), 0.1016, "L1" if i % 2 == 0 else "L4")
        f.via("FMC_A2", 5 + 3.5 * i + 3.5, y, a="L1", c="L4")
    y += 1.5
    net_len("l10", "QSPI 时钟 20 mm", "QSPI_CLK", 20)
    net_len("l11", "QSPI IO 22 mm", "QSPI_BK1_IO0", 22)
    net_len("l12", "QSPI IO 26 mm：比时钟长 6 mm", "QSPI_BK1_IO1", 26, (), {(LEN, "qspi_window")})
    net_len("l13", "QSPI IO 31 mm：超过 30 mm", "QSPI_BK1_IO2", 31, {(LEN, "qspi_len_max")}, {(LEN, "qspi_window")})
    net_len("l14", "QSPI 片选 35 mm：不限等长，也不限长度（用户 2026-11-23）：只有手写段时报 qspi_len_max，生成段的 qspi_ncs_no_cap 压过它", "QSPI_BK1_NCS", 35, {(LEN, "qspi_len_max")}, set())
    net_len("l20", "SD 时钟 20 mm", "SDMMC1_CK", 20)
    net_len("l21", "SD 数据 22 mm", "SDMMC1_D0", 22)
    net_len("l22", "SD 数据 19 mm：比时钟短", "SDMMC1_D1", 19, (), {(LEN, "sdmmc_window")})
    net_len("l23", "SD 命令 26 mm：比时钟长 6 mm", "SDMMC1_CMD", 26, (), {(LEN, "sdmmc_window")})
    net_len("l30", "RMII 时钟 41 mm：超过 40 mm", "RMII_REF_CLK", 41, {(LEN, "rmii_refclk_len_max")})
    net_len("l31", "RMII RXD0 40 mm：比时钟短", "RMII_RXD0", 40, (), {(LEN, "rmii_rx_min")})
    net_len("l32", "RMII RXD1 42 mm", "RMII_RXD1", 42)
    net_len("l33", "RMII TXD0 61 mm：超过 60 mm（另：时钟加最长 TXD = 102 > 100，由脚本报）", "RMII_TXD0", 61, {(LEN, "rmii_len_max")})
    net_len("l34", "RMII TXD1 59 mm", "RMII_TXD1", 59)
    net_len("l40", "LTDC 100 mm", "LCD_R3", 100)
    net_len("l41", "LTDC 121 mm：超过 120 mm", "LCD_R4", 121, {(LEN, "ltdc_len_max")})
    net_len("l42", "LTDC 75 mm：比最长的（R4 121 mm）短 46 mm：只有手写段时报 ltdc_spread（30），生成段的 ltdc_spread_60（用户 2026-11-23 按电气值定 60 mm）压过它，不报", "LCD_R5", 75, {(SK, "ltdc_spread")}, set())
    net_len("l44", "LTDC 60 mm：比最长的（R4 121 mm）短 61 mm：手写段报 ltdc_spread（30），生成段的 ltdc_spread_60 也报", "LCD_R7", 60, {(SK, "ltdc_spread")}, {(SK, "ltdc_spread_60")})
    f.case("l0g", "通道 1 数据线 4 个 L1–L4 过孔：超过 3 个（长度 30.4 + 3 × 过孔高度 = 34.58，比 D8 短 0.42，在通道 1 的 1.27 mm 之内）", {(VC, "sdram_via_max")})
    for i in range(4):
        f.trk("FMC_D10", (5 + 7.6 * i, y), (5 + 7.6 * i + 7.6, y), 0.1016, "L1" if i % 2 == 0 else "L4")
        f.via("FMC_D10", 5 + 7.6 * i + 7.6, y, a="L1", c="L4")
    y += 1.5
    f.case("l43", "LTDC 4 个过孔：不限过孔数")
    for i in range(4):
        f.trk("LCD_R6", (5 + 25 * i, y), (5 + 25 * i + 25, y), 0.1016, "L1" if i % 2 == 0 else "L6")
        f.via("LCD_R6", 5 + 25 * i + 25, y)
    y += 1.5
    f.case("l0h", "地址线 14 mm 加 4 个通孔、L1–L3 换层（最后一个只接一层）：长度 14 + 3 × L1–L3 过孔高度（真板上的过孔都是通孔）")
    for i in range(4):
        f.trk("FMC_A3", (5 + 3.5 * i, y), (5 + 3.5 * i + 3.5, y), 0.1016, "L1" if i % 2 == 0 else "L3")
        f.via("FMC_A3", 5 + 3.5 * i + 3.5, y)
    y += 1.5

    # ---- pour on L6 over the whole board, clearance 0.2: distance to tracks, pad connections
    f.case("z00", "整板铺地（L6，间距 0.2），盖住两个规则区")
    f.pour("GND", "L6", (1, 1, 109, 149), 0.2)
    f.case("z01", "区外的走线到铺地"); f.trk("N60", (70, 20), (80, 20), 0.2, "L6")
    f.case("z02", "MCU 区内的走线到铺地"); f.trk("N61", (12, 21), (18, 21), 0.09, "L6")
    f.case("z03", "接地的插件焊盘：花焊盘"); f.pad("Z3", "GND", 70, 26, 1.7, 1.0)
    f.case("z04", "接地的贴片焊盘（L6）：全连接"); f.pad("Z4", "GND", 78, 26, 1.5, layer="L6")


def copper(board, layer):
    """Filled copper of all pours on a layer, as one simplified polygon set."""
    ps = pcbnew.SHAPE_POLY_SET()
    for z in board.Zones():
        if not z.GetIsRuleArea() and z.IsOnLayer(L[layer]):
            ps.Append(z.GetFilledPolysList(L[layer]))
    ps.Simplify()
    return ps


def measure(pcb):
    """[(case, text, ok)] for what DRC cannot report."""
    b = pcbnew.LoadBoard(pcb)
    cu = copper(b, "L6")
    inside = lambda x, y: cu.Contains(V(x, y))
    out = []
    for cid, (x, y, w) in (("z01", (75, 20, 0.2)), ("z02", (15, 21, 0.09))):
        # first distance from the track edge at which copper starts, 0.01 mm steps
        d = next((k / 100 for k in range(1, 60) if inside(x, y + w / 2 + k / 100)), None)
        out.append((cid, "铺地离走线边 %s mm（铺铜区设 0.2；规则区的 0.09 不该用到铺铜上）" % d, d is not None and 0.19 <= d <= 0.22))
    for cid, (x, y, r), want in (("z03", (70, 26, 0.85), "thermal"), ("z04", (78, 26, 0.75), "solid")):
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


def main(out):
    os.makedirs(out, exist_ok=True)
    stem = os.path.join(out, "fixture")
    base = os.path.join(out, "base.kicad_pcb")
    make_project.make_pcb(base)
    f = Fixture(base)
    build(f)
    pcbnew.SaveBoard(stem + ".kicad_pcb", f.b)
    os.remove(base)
    # after SaveBoard: pcbnew writes a default .kicad_pro next to a board it saves
    shutil.copy(os.path.join(HERE, NAME + ".kicad_pro"), stem + ".kicad_pro")
    # the static phase is the hand-written part only: the real board's generated block (its windows and fixed rules)
    # is emptied here and regenerated for the fixture by len_rules.py before the window phase
    dru = open(os.path.join(HERE, NAME + ".kicad_dru"), encoding="utf-8").read()
    i, j = dru.index(len_rules.BEGIN), dru.index(len_rules.END)
    open(stem + ".kicad_dru", "w", encoding="utf-8", newline="\n").write(dru[:i] + len_rules.BEGIN + "\n" + dru[j:])
    shutil.copy(os.path.join(HERE, "length_groups.json"), os.path.join(out, "length_groups.json"))
    # fill the pour once and keep it in the board file
    subprocess.run([drc_probe.KICAD_CLI, "pcb", "drc", "--refill-zones", "--save-board", "--severity-all", "--format", "json",
                    "-o", os.path.join(out, "fill.json"), stem + ".kicad_pcb"], capture_output=True)
    os.remove(os.path.join(out, "fill.json"))

    lines, bad = [], 0
    def check(ok, text):
        nonlocal bad
        bad += not ok
        lines.append(("ok   " if ok else "FAIL ") + text)

    canary = subprocess.run([PY, "-m", "Tools.KiCadDesignTools.rules.dru_canary", os.path.abspath(stem + ".kicad_pcb")], cwd=os.path.dirname(HERE), capture_output=True, text=True)
    check(canary.returncode == 0, "金丝雀：" + canary.stdout.strip())

    static = classify(drc_probe.run_drc(stem + ".kicad_pcb"), f)
    lr = subprocess.run([PY, "-m", "Tools.KiCadDesignTools.rules.len_rules", os.path.abspath(stem + ".kicad_pcb")], cwd=os.path.dirname(HERE), capture_output=True, text=True, encoding="utf-8")
    lines.append(lr.stdout.strip())
    check("rmii_refclk_plus_longest_txd: 102.0000 mm" in lr.stdout and "超出 2.0000" in lr.stdout and lr.returncode == 1,
          "len_rules.py 报出时钟加最长 TXD 超出 100 mm（故意的）")
    check("sdclk_total: 20.0000 mm" in lr.stdout, "len_rules.py 把 SDCLK 串阻两侧相加得 20 mm")
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

    for cid, text, ok in measure(stem + ".kicad_pcb"):
        check(ok, "%s 实测：%s" % (cid, text))
    h = make_project.via_height("F.Cu", "In3.Cu")
    got = drc_probe.measure_lengths(stem + ".kicad_pcb", {"d4": "A.NetName == 'FMC_A2'", "d3": "A.NetName == 'FMC_A3'"})
    d4 = got["d4"].get("FMC_A2")
    check(d4 is not None and abs(d4 - (14 + 3 * h)) < 0.0005,
          "l0f 实测：KiCad 量到 %s mm，按叠层算 14 + 3 × %.4f = %.4f mm（换层的过孔按 L1–L4 的高度计入，只接一层的不计）" % (d4, h, 14 + 3 * h))
    h3 = make_project.via_height("F.Cu", "In2.Cu")
    d3 = got["d3"].get("FMC_A3")
    check(d3 is not None and abs(d3 - (14 + 3 * h3)) < 0.0005,
          "l0h 实测：KiCad 量到 %s mm，按叠层算 14 + 3 × %.4f = %.4f mm（通孔在 L1–L3 换层只计 L1–L3 的高度，不是整板 %.4f）" % (
              d3, h3, 14 + 3 * h3, make_project.via_height("F.Cu", "B.Cu")))

    rows, loaded = dru_match.match(stem + ".kicad_pcb")
    empty = [r["rule"] for r in rows if r["matched"] == 0]
    check(loaded and not empty, "基准板上每条规则都匹配到对象：%d 条规则，空匹配 %d 条%s" % (len(rows), len(empty), "（" + "、".join(empty) + "）" if empty else ""))
    never = sorted({n for n, _, _ in drc_probe.parse_rules(open(stem + ".kicad_dru", encoding="utf-8").read())}
                   - {r for ph in (static, window) for s in ph[0].values() for _, r in s} - {"tht_thermal", "smd_solid"})
    lines.append("没有被任何用例触发过的规则：%s" % ("、".join(never) if never else "无"))
    lines.insert(0, "规则基准板：%d 个用例，%d 项不符" % (len(f.expect), bad))
    open(os.path.join(out, "rules_fixture.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(lines))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
