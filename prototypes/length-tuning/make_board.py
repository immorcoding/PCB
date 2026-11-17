"""PROTOTYPE (throwaway, issue 15): base board for the length-tuning trial. No serpentines here.

    D:\\KiCad\\bin\\python.exe make_board.py   -> out/0_base/lentune.kicad_pcb (+ .kicad_pro, .kicad_dru, routes.json)

Six layers, 40 x 30 mm, MCU (UFBGA-201) and SDRAM (BGA-90) 5 mm apart edge to edge, one rule area round
each (package + 1 mm), ground pours on L2 and L5. No schematic: nets are put straight onto pads.
Nine nets: FMC_D8..D15 (SDRAM byte lane 1) and FMC_SDCLK, rough-routed (not length matched).

The script is the source (PROC-13): change ROUTES below, not the board file.
Coordinates are local mm (board file mm - 100), origin at the top left corner of the board, y down.
"""
import json, os, re, shutil
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "0_base")
KI = r"D:\KiCad\share\kicad"
NAME = "lentune"
W, H = 40.0, 30.0
MCU, RAM = (13.0, 12.0), (27.0, 15.9)                  # centres; the SDRAM sits 3.9 mm lower than the MCU
AREAS = {"BGA_MCU": (7.0, 6.0, 19.0, 18.0), "BGA_SDRAM": (22.0, 8.4, 32.0, 23.4)}   # package outline + 1 mm
W_IN, W_OUT = 0.09, 0.1016                             # profile C: track width inside / outside the rule areas
VIA_BGA = (0.30, 0.15)                                 # via inside a rule area (diameter, drill)
L1, L4 = "F.Cu", "In3.Cu"

# MCU side: port pin of each net (ball numbers are read from the KiCad symbol STM32H743IIKx below).
MCU_PINS = {"/FMC_D8": "PE11", "/FMC_D9": "PE12", "/FMC_D10": "PE13", "/FMC_D11": "PE14", "/FMC_D12": "PE15",
            "/FMC_D13": "PD8", "/FMC_D14": "PD9", "/FMC_D15": "PD10", "/FMC_SDCLK": "PG8"}
# SDRAM side: ball of each net. Bits are swapped inside byte lane 1 (DQ8..DQ15) so that nothing crosses
# (issue 12 allows this). Ball names come from the 90-ball map in research/sdram-32bit-bga, NOT from a
# KiCad symbol (the KiCad library has no 90-ball SDRAM symbol).
RAM_BALLS = {"/FMC_D8": ("R2", "DQ15"), "/FMC_D9": ("R1", "DQ13"), "/FMC_D10": ("L2", "DQ8"),
             "/FMC_D11": ("M2", "DQ10"), "/FMC_D12": ("P1", "DQ11"), "/FMC_D13": ("N3", "DQ14"),
             "/FMC_D14": ("M3", "DQ9"), "/FMC_D15": ("N2", "DQ12"), "/FMC_SDCLK": ("J1", "CLK")}
GND_BALLS = {"U1": "M9", "U2": "L3"}                   # one VSS ball per chip gets a via, to tie L2 and L5 together

# Routes. Each net: a list of pieces; a piece is (layer, [points]) or ("via", (x, y)).
# "U1" / "U2" stand for the pad centre of the net on that chip. Track width is not written here: a
# segment that touches a rule area gets 0.09, any other 0.1016 (so the width changes at the first bend
# outside the area, as profile C says).
ROUTES = {
    # --- L1, leaving the MCU to the east, then down the 3 mm corridor between the two rule areas
    # SDCLK's vertical is at x = 21.25 (0.35 from D15, 0.75 from the SDRAM rule area) so that a 0.5 mm hump to the
    # east keeps a full clearance (0.127) to the rule-area edge; at x = 21.4 it came within 0.049 mm (review finding).
    "/FMC_SDCLK": [(L1, ["U1", (17.225, 12.325), (20.75, 12.325), (21.25, 12.825), (21.25, 16.2), (21.75, 16.7), "U2"])],
    "/FMC_D15": [(L1, ["U1", (20.4, 15.25), (20.9, 15.75), (20.9, 19.0), (21.4, 19.5), (24.2, 19.5), "U2"])],
    "/FMC_D13": [(L1, ["U1", (19.3, 15.9), (19.8, 16.4), (19.8, 19.8), (20.3, 20.3), (25.0, 20.3), "U2"])],
    # --- L1, leaving the MCU to the south, then east below the MCU
    "/FMC_D12": [(L1, ["U1", (14.95, 18.7), (15.45, 19.2), (18.7, 19.2), (20.2, 20.7), "U2"])],
    "/FMC_D8": [(L1, ["U1", (14.625, 16.225), (14.625, 19.5), (15.125, 20.0), (19.0, 20.0), (20.1, 21.1),
                      (24.2, 21.1), "U2"])],
    "/FMC_D9": [(L1, ["U1", (14.3, 20.3), (14.8, 20.8), (19.3, 20.8), (20.0, 21.5), "U2"])],
    # --- dog-bone via in the MCU, L4 across the corridor, second via beside the SDRAM ball.
    # The via of a net sits on the side its L4 track leaves from: no net doubles back under its own ball
    # (review finding: D11 and D14 used to). D10 and D11 turn 90 degrees at the MCU via and D14 at the SDRAM
    # via: the row a straight exit would need is taken by the neighbour's via (RTE-11: explained, not changed).
    "/FMC_D10": [(L1, ["U1", (15.275, 15.575)]), ("via", (15.275, 15.575)),
                 (L4, [(15.275, 15.575), (15.6, 15.25), (19.1, 15.25), (21.75, 17.9), (22.6, 17.9)]),
                 ("via", (22.6, 17.9)), (L1, [(22.6, 17.9), (24.2, 17.9), "U2"])],
    "/FMC_D11": [(L1, ["U1", (15.275, 16.225)]), ("via", (15.275, 16.225)),
                 (L4, [(15.275, 16.225), (15.6, 15.9), (19.1, 15.9), (21.9, 18.7), (22.6, 18.7)]),
                 ("via", (22.6, 18.7)), (L1, [(22.6, 18.7), (24.2, 18.7), "U2"])],
    "/FMC_D14": [(L1, ["U1", (17.225, 16.225)]), ("via", (17.225, 16.225)),
                 (L4, [(17.225, 16.225), (17.55, 16.55), (19.1, 16.55), (21.65, 19.1), (24.6, 19.1), (25.0, 19.5)]),
                 ("via", (25.0, 19.5)), (L1, [(25.0, 19.5), "U2"])],
}
GND_TAPS = {"U1": (13.975, 14.925), "U2": (26.2, 18.3)}   # via beside the VSS ball named in GND_BALLS

# JLC06161H-3313E (research/jlc-6layer-capability, section 5). The L3-L4 dielectric is really
# 7628 0.2104 + bare core 0.7 + 7628 0.2104; written as one layer of 1.1208 (only the height matters here).
STACK = """		(stackup
			(layer "F.SilkS" (type "Top Silk Screen"))
			(layer "F.Paste" (type "Top Solder Paste"))
			(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
			(layer "F.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 1" (type "prepreg") (thickness 0.0994) (material "3313") (epsilon_r 4.1) (loss_tangent 0.02))
			(layer "In1.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 2" (type "core") (thickness 0.1) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
			(layer "In2.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 3" (type "prepreg") (thickness 1.1208) (material "7628+core+7628") (epsilon_r 4.4) (loss_tangent 0.02))
			(layer "In3.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 4" (type "core") (thickness 0.1) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
			(layer "In4.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 5" (type "prepreg") (thickness 0.0994) (material "3313") (epsilon_r 4.1) (loss_tangent 0.02))
			(layer "B.Cu" (type "copper") (thickness 0.035))
			(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
			(layer "B.Paste" (type "Bottom Solder Paste"))
			(layer "B.SilkS" (type "Bottom Silk Screen"))
			(copper_finish "None")
			(dielectric_constraints no)
		)
"""


def sym_pins(libfile, name):
    """{pin name: pin number} of a KiCad library symbol (follows one level of 'extends')."""
    text = open(os.path.join(KI, "symbols", libfile), encoding="utf-8").read()

    def block(n):
        i = text.find('\t(symbol "%s"\n' % n)
        if i < 0:
            raise SystemExit("no symbol " + n)
        depth, j = 0, i
        while True:
            c = text[j]
            depth += (c == "(") - (c == ")")
            if c == ")" and depth == 0:
                return text[i:j + 1]
            j += 1

    blk = block(name)
    m = re.search(r'\(extends "([^"]+)"', blk)
    if m:
        blk = block(m.group(1))
    return {m.group(1): m.group(2) for m in re.finditer(r'\(name "([^"]*)".*?\(number "([^"]*)"', blk, re.S)}


def touches_area(a, c, half):
    """True if the segment a-c, as copper of half-width `half`, touches a rule area (what intersectsArea sees)."""
    for x0, y0, x1, y1 in AREAS.values():
        x0, y0, x1, y1 = x0 - half, y0 - half, x1 + half, y1 + half
        t0, t1, ok = 0.0, 1.0, True
        for p, q in ((-(c[0] - a[0]), a[0] - x0), (c[0] - a[0], x1 - a[0]), (-(c[1] - a[1]), a[1] - y0), (c[1] - a[1], y1 - a[1])):
            if p == 0:
                ok = ok and q >= 0
            elif p < 0:
                t0 = max(t0, q / p)
            else:
                t1 = min(t1, q / p)
        if ok and t0 <= t1:
            return True
    return False


def build(out_dir=OUT, routes=ROUTES):
    FromMM, mm = pcbnew.FromMM, pcbnew.ToMM
    P = lambda x, y: pcbnew.VECTOR2I(int(round((x + 100) * 1e6)), int(round((y + 100) * 1e6)))   # FromMM truncates (29.2 -> 29.199999)
    os.makedirs(out_dir, exist_ok=True)
    if any(f.startswith("~") and f.endswith(".lck") for f in os.listdir(out_dir)):
        raise SystemExit("KiCad has %s open (~*.lck found): close it first, nothing was written" % out_dir)
    for ext in ("kicad_pro", "kicad_dru"):
        shutil.copy(os.path.join(HERE, "base", NAME + "." + ext), os.path.join(out_dir, NAME + "." + ext))
    pcb = os.path.join(out_dir, NAME + ".kicad_pcb")
    shutil.copy(os.path.join(HERE, "base", "empty6.kicad_pcb"), pcb)
    B = pcbnew.LoadBoard(pcb)
    LID = {n: B.GetLayerID(n) for n in ("F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu")}

    def net(name):
        n = B.FindNet(name)
        if n is None:
            n = pcbnew.NETINFO_ITEM(B, name); B.Add(n)
        return n

    # outline
    for a, c in (((0, 0), (W, 0)), ((W, 0), (W, H)), ((W, H), (0, H)), ((0, H), (0, 0))):
        s = pcbnew.PCB_SHAPE(B); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(P(*a)); s.SetEnd(P(*c))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FromMM(0.1)); B.Add(s)

    # rule areas (AD: Room), all copper layers, nothing forbidden
    for name, (x0, y0, x1, y1) in AREAS.items():
        z = pcbnew.ZONE(B); z.SetIsRuleArea(True); z.SetZoneName(name)
        ls = pcbnew.LSET()
        for l in LID.values():
            ls.AddLayer(l)
        z.SetLayerSet(ls)
        for k in ("SetDoNotAllowTracks", "SetDoNotAllowVias", "SetDoNotAllowPads", "SetDoNotAllowZoneFills", "SetDoNotAllowFootprints"):
            getattr(z, k)(False)
        o = z.Outline(); o.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            o.Append(P(x, y))
        B.Add(z)

    # the two BGAs; only the nine nets and one ground ball each carry a net
    pins = sym_pins("MCU_ST_STM32H7.kicad_sym", "STM32H743IIKx")
    mcu_ball = {n: pins[p] for n, p in MCU_PINS.items()}
    FPS, PADS = {}, {}
    for ref, spec, (x, y), value, balls in (
            ("U1", "Package_BGA:UFBGA-201_10x10mm_Layout15x15_P0.65mm", MCU, "STM32H743IIK6", mcu_ball),
            ("U2", "Package_BGA:BGA-90_8.0x13.0mm_Layout2x3x15_P0.8mm", RAM, "IS42S32800J", {n: b for n, (b, _) in RAM_BALLS.items()})):
        lib, name = spec.split(":")
        fp = pcbnew.FootprintLoad(os.path.join(KI, "footprints", lib + ".pretty"), name)
        fp.SetFPID(pcbnew.LIB_ID(lib, name)); fp.SetReference(ref); fp.SetValue(value)
        fp.SetPosition(P(x, y)); B.Add(fp)
        by_num = {p.GetNumber(): p for p in fp.Pads()}
        for n, b in balls.items():
            by_num[b].SetNet(net(n))
            PADS[(ref, n)] = (round(mm(by_num[b].GetPosition().x) - 100, 4), round(mm(by_num[b].GetPosition().y) - 100, 4))
        by_num[GND_BALLS[ref]].SetNet(net("GND"))
        PADS[(ref, "GND")] = (round(mm(by_num[GND_BALLS[ref]].GetPosition().x) - 100, 4), round(mm(by_num[GND_BALLS[ref]].GetPosition().y) - 100, 4))
        FPS[ref] = fp

    def via(netname, xy, size=VIA_BGA):
        v = pcbnew.PCB_VIA(B); v.SetPosition(P(*xy)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetWidth(pcbnew.F_Cu, FromMM(size[0])); v.SetDrill(FromMM(size[1]))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net(netname)); B.Add(v)

    def seg(netname, layer, a, c, w):
        s = pcbnew.PCB_TRACK(B); s.SetStart(P(*a)); s.SetEnd(P(*c)); s.SetWidth(FromMM(w))
        s.SetLayer(LID[layer]); s.SetNet(net(netname)); B.Add(s)

    dump = {}
    for n, pieces in routes.items():
        dump[n] = []
        for kind, data in pieces:
            if kind == "via":
                via(n, data); dump[n].append({"via": list(data)})
                continue
            pts = [PADS[(p, n)] if isinstance(p, str) else p for p in data]
            widths = []
            for a, c in zip(pts, pts[1:]):
                w = W_IN if touches_area(a, c, W_OUT / 2) else W_OUT
                seg(n, kind, a, c, w); widths.append(w)
            dump[n].append({"layer": kind, "points": [list(p) for p in pts], "widths": widths})
    for ref, xy in GND_TAPS.items():                       # ground ball -> via beside it
        via("GND", xy); seg("GND", L1, PADS[(ref, "GND")], xy, 0.15)

    # ground pours on L2 and L5 (reference planes); filled later by kicad-cli --refill-zones
    for layer in ("In1.Cu", "In4.Cu"):
        z = pcbnew.ZONE(B); z.SetZoneName("GND_" + layer[:3]); z.SetLayer(LID[layer]); z.SetNet(net("GND"))
        z.SetAssignedPriority(0); z.SetLocalClearance(FromMM(0.2)); z.SetMinThickness(FromMM(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        o = z.Outline(); o.NewOutline()
        for x, y in ((0, 0), (W, 0), (W, H), (0, H)):
            o.Append(P(x, y))
        B.Add(z)

    pcbnew.SaveBoard(pcb, B)
    text = open(pcb, encoding="utf-8").read()              # pcbnew's Python API hides the stackup: write it as text
    assert "(stackup" not in text
    text = text.replace("\t(setup\n", "\t(setup\n" + STACK, 1)
    open(pcb, "w", encoding="utf-8").write(text)
    json.dump({"areas": AREAS, "board": [W, H], "mcu_balls": mcu_ball, "ram_balls": RAM_BALLS, "routes": dump},
              open(os.path.join(out_dir, "routes.json"), "w", encoding="utf-8"), indent=1)
    return mcu_ball


if __name__ == "__main__":
    balls = build()
    print("wrote", os.path.join(OUT, NAME + ".kicad_pcb"))
    for n in ROUTES:
        print("  %-11s MCU %-4s %-4s -> SDRAM %-3s %s" % (n, MCU_PINS[n], balls[n], RAM_BALLS[n][0], RAM_BALLS[n][1]))
