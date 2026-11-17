"""PROTOTYPE (throwaway, issue 21): constants and small helpers shared by every lib module.

Coordinates everywhere are LOCAL mm: board file mm - 100, origin at the top left corner of the
board, x to the right, y DOWN (as in KiCad). The MCU is on the left, the SDRAM on the right.
"""
import math, os
import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # prototypes/route-tune
KI = r"D:\KiCad\share\kicad"
CLI = r"D:\KiCad\bin\kicad-cli.exe"
PY = r"D:\KiCad\bin\python.exe"
# scripts/track_shape.py and dru_canary.py: the main checkout's copies are newer than the worktree's; fall back to the worktree
_MAIN = os.path.normpath(os.path.join(ROOT, "..", "..", "..", "..", "..", "scripts"))
REPO_SCRIPTS = _MAIN if os.path.isfile(os.path.join(_MAIN, "track_shape.py")) else os.path.normpath(os.path.join(ROOT, "..", "..", "scripts"))
NAME = "routetune"                                         # file stem of the board in every out/<key>/

# ---- fixed layout (same in every variant; taken from the length-tuning prototype) ----
BOARD = (40.0, 30.0)                                       # default outline; a variant may set BOARD = (w, h)
MCU, RAM = (13.0, 12.0), (27.0, 15.9)                      # package centres, no rotation
BODY = {"U1": (8.0, 7.0, 18.0, 17.0), "U2": (23.0, 9.4, 31.0, 22.4)}            # package outlines (x0, y0, x1, y1)
AREAS = {"BGA_MCU": (7.0, 6.0, 19.0, 18.0), "BGA_SDRAM": (22.0, 8.4, 32.0, 23.4)}   # rule areas = outline + 1 mm
CORRIDOR = (19.0, 22.0)                                    # x range of the strip between the two rule areas
FOOTPRINT = {"U1": ("Package_BGA:UFBGA-201_10x10mm_Layout15x15_P0.65mm", MCU, "STM32H743IIK6"),
             "U2": ("Package_BGA:BGA-90_8.0x13.0mm_Layout2x3x15_P0.8mm", RAM, "IS42S32800J")}
W_IN, W_OUT = 0.09, 0.1016                                 # track width inside / outside the rule areas
W_CHANGE = 0.3                                             # the width changes this far outside a rule-area edge (along the track)
VIA_IN, VIA_OUT = (0.30, 0.15), (0.45, 0.20)               # via (diameter, drill) inside / outside a rule area
CLR_IN, CLR_OUT = 0.09, 0.127                              # DRC clearance inside / outside the rule areas
MINSEG = 0.1                                               # DRC rule min_segment
LAYERS = {"L1": "F.Cu", "L2": "In1.Cu", "L3": "In2.Cu", "L4": "In3.Cu", "L5": "In4.Cu", "L6": "B.Cu"}
SIGNAL_LAYERS = ("L1", "L4", "L6")
LID = {"L1": pcbnew.F_Cu, "L2": pcbnew.In1_Cu, "L3": pcbnew.In2_Cu, "L4": pcbnew.In3_Cu, "L5": pcbnew.In4_Cu, "L6": pcbnew.B_Cu}
LNUM = {v: k for k, v in LID.items()}
NETS = ["FMC_SDCLK"] + ["FMC_D%d" % i for i in range(16)] + ["FMC_NBL0", "FMC_NBL1"]   # the 19 nets, table order
REF = "FMC_SDCLK"
WINDOW, LEN_MAX = 2.5, 60.0                                # every net within +-WINDOW of REF; each net at most LEN_MAX

# ---- serpentine keep-offs (defaults of the length-tuning prototype; a variant may override with CLEAR = {...}) ----
SERP = {"end": 0.35,        # straight kept between a 45-degree bend and the first arc
        "clr": 0.19,        # serpentine copper to any other copper (other nets, and the net's own other pieces)
        "area_gap": 0.127,  # serpentine copper OUTSIDE a rule area to that area's edge
        "edge": 0.254,      # to the board edge
        "field": 0.6}       # on L1: centre line no closer than this to any ball centre (stay out of the ball fields)

mm = pcbnew.ToMM


def Lp(v):
    """pcbnew VECTOR2I -> local mm tuple."""
    return (mm(v.x) - 100, mm(v.y) - 100)


def P(p):
    """local mm tuple -> pcbnew VECTOR2I (rounded to 1 nm; FromMM truncates)."""
    return pcbnew.VECTOR2I(int(round((p[0] + 100) * 1e6)), int(round((p[1] + 100) * 1e6)))


def full(net):
    """'D8' / 'FMC_D8' / '/FMC_D8' -> 'FMC_D8' (the name used in routes.py and in every table)."""
    net = net.lstrip("/")
    return net if net.startswith("FMC_") else "FMC_" + net


def short(net):
    return net.lstrip("/").replace("FMC_", "")


def check_lock(d):
    if os.path.isdir(d) and any(f.startswith("~") and f.endswith(".lck") for f in os.listdir(d)):
        raise SystemExit("KiCad has a board open in %s (~*.lck found): close it first, nothing was written" % d)


def in_rect(p, R, grow=0.0):
    return R[0] - grow <= p[0] <= R[2] + grow and R[1] - grow <= p[1] <= R[3] + grow


def area_of(p):
    """Name of the rule area that contains point p, or None."""
    for n, R in AREAS.items():
        if in_rect(p, R):
            return n
    return None


def octile(a, c):
    """Shortest length of a 0/45/90-degree path between two points, ignoring obstacles."""
    dx, dy = abs(a[0] - c[0]), abs(a[1] - c[1])
    return max(dx, dy) - min(dx, dy) + min(dx, dy) * math.sqrt(2)


def arc_geom(t):
    """(centre, radius, start angle, signed sweep) of a PCB_ARC in local mm."""
    (x0, y0), (xm, ym), (x1, y1) = Lp(t.GetStart()), Lp(t.GetMid()), Lp(t.GetEnd())
    cx, cy = Lp(t.GetCenter()); r = math.hypot(x0 - cx, y0 - cy)
    a0, am, a1 = (math.atan2(y - cy, x - cx) for x, y in ((x0, y0), (xm, ym), (x1, y1)))
    d = (a1 - a0) % (2 * math.pi)
    if (am - a0) % (2 * math.pi) > d:
        d -= 2 * math.pi
    return (cx, cy), r, a0, d


def arc_pts(t, step=0.02):
    (cx, cy), r, a0, d = arc_geom(t)
    n = max(4, int(abs(d) * r / step))
    return [(cx + r * math.cos(a0 + d * i / n), cy + r * math.sin(a0 + d * i / n)) for i in range(n + 1)]


def track_pts(t, step=0.02):
    """Centre-line polyline of a track segment or arc."""
    return arc_pts(t, step) if t.Type() == pcbnew.PCB_ARC_T else [Lp(t.GetStart()), Lp(t.GetEnd())]
