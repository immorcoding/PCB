# route-tune prototype: how to write a variant

Throwaway prototype for issue 21. This file is for the agents who add variants. Shared code lives in
`lib/` and `build.py`; **a variant is one folder `variants/<key>/` with one file `routes.py`, and adding
a variant must not touch anything else.** If the shared code is wrong or missing something, report it
instead of patching it in place (other agents are building against it at the same time).

## Commands

```
D:/KiCad/bin/python.exe build.py <key> --fast     # 1-4 s: board + serpentines, lengths and gaps by geometry, no kicad-cli
D:/KiCad/bin/python.exe build.py <key>            # 10-20 s: + DRC (pours refilled), DRC-measured lengths, checks, metrics.json, tune.txt, 20 pictures
D:/KiCad/bin/python.exe build.py <key> --force    # draw explicit serpentines even where they break a limit, to look at them
D:/KiCad/bin/python.exe build.py --summary        # out/summary.md over every out/*/metrics.json
```

Run from `prototypes/route-tune/`. pcbnew prints a dozen "Adding duplicate image handler" lines on
import; ignore them (`2>&1 | grep -v "image handler"`). A build writes only `out/<key>/` (plus a
short-lived `out/_tmp/probe_*` folder), so different variants can be built in parallel; do not build
the same key twice at once. If KiCad has `out/<key>/` open (`~*.lck`), the build stops without writing.

Iterate with `--fast`: it prints the length table (natural, added, total, distance to SDCLK, in window
or not), every same-layer gap below the DRC clearance (`CLEARANCE ...`), every net that is not a single
pad-to-pad line (`PATH ...`), and stops with an exact message when a route point is off 0/45/90 or a
serpentine does not fit. The geometry gap check samples the bus tracks only; **DRC in the full build is
the authority**, run it before you believe a layout.

## Coordinates and the fixed layout

Local mm = board-file mm - 100. Origin at the board's top-left corner, x right, **y down** ("N" is up
on the pictures and means smaller y). Constants are in `lib/common.py`:

| thing | value |
|---|---|
| MCU U1 (UFBGA-201, 15x15, 0.65 pitch, pad 0.30) | centre (13.0, 12.0); outline x 8-18, y 7-17; rule area x 7-19, y 6-18 |
| SDRAM U2 (BGA-90, 0.8 pitch, pad 0.40) | centre (27.0, 15.9); outline x 23-31, y 9.4-22.4; rule area x 22-32, y 8.4-23.4 |
| strip between the rule areas ("corridor") | x 19-22 |
| MCU ball (row r of ABCDEFGHJKLMNPR = 0..14, col c = 1..15) | (13 + (c-8)*0.65, 12 + (r-7)*0.65) |
| SDRAM ball (cols 1,2,3,7,8,9 -> x 23.8, 24.6, 25.4, 28.6, 29.4, 30.2) | y = 10.3 + 0.8*r |
| board | 40 x 30; a variant may set `BOARD = (w, h)` (grows to the right / down) |

Ball numbers are checked on every build against the KiCad symbol STM32H743IIKx and both footprints
(`lib/balls.py`); the SDRAM functions come from the research ball map (KiCad has no symbol for it).

## routes.py

```python
DESCRIPTION = "一句中文：这个方案是什么"          # shown in tables
SWAP   = {"FMC_D0": "DQ3", ..., "FMC_NBL0": "DQM0", "FMC_SDCLK": "CLK"}   # all 19 nets -> SDRAM pin NAME
ROUTES = {"FMC_D10": [("L1", ["U1", (15.275, 15.575)]), ("via", (15.275, 15.575)),
                      ("L4", [(15.275, 15.575), (19.1, 15.575), (22.225, 18.7), (25.0, 18.7)]), ("via", (25.0, 18.7)),
                      ("L1", [(25.0, 18.7), "U2"])], ...}
TUNING = [...]                                     # serpentines, see below; [] for none
WHY    = {"FMC_D10": "一句中文：为什么这样走"}     # one sentence per net, goes into metrics.json and tune.txt
# optional:
PITCH  = {"default": 0.3, "SDCLK": 0.5}            # leg pitch per net (default 0.5 everywhere)
CLEAR  = {"clr": 0.19, "end": 0.35, "area_gap": 0.127}   # serpentine hard limits (defaults shown)
BOARD  = (40, 30);  VIEWS = [("name", x0, y0, x1, y1, px_per_mm)]   # extra crops, 4 pictures each
GND_TAPS = {"U1": (13.975, 14.925), "U2": (26.0, 10.3)}             # via beside the VSS balls M9 / A3
```

Net names are written without the leading slash (`FMC_D8`; `D8` also works in TUNING and PITCH); on the
board they are `/FMC_D8`. To start from another variant: `ROUTES, SWAP, WHY = board.base_routes("0_base")`
(deep copies; see `variants/1_baseline/routes.py` for the two import lines).

**SWAP** is checked: D0-7 must land in one SDRAM lane and D8-15 in the other, NBLx follows its lane to
DQMx, SDCLK goes to CLK. The resulting table is in `out/<key>/routes.json` and in `tune.txt`.

**ROUTES**: per net a list of pieces from the MCU pad to the SDRAM pad. A piece is
`("L1" | "L4" | "L6", [points])` or `("via", (x, y))` or `("via", (x, y), (diameter, drill))`.
`"U1"` / `"U2"` stand for the net's pad centre. Each track piece must start where the previous one
ended and a via sits exactly on that point. Checked with an exact error message: only 0/45/90 segments,
no segment under 0.1 mm, no corner sharper than 45 degrees of turn, layer changes only at a via.
A via inside a rule area is 0.30/0.15, outside 0.45/0.20, chosen automatically. All vias are through
vias: **a via blocks its spot on L1, L4 and L6**.

**Track width is not written.** Inside a rule area and for 0.3 mm of track beyond its edge the track is
0.09, elsewhere 0.1016; the cut is on the straight. One route segment therefore becomes two or three
board tracks. A serpentine sits on ONE board track: the wide part of a straight that crosses an area
edge is shorter than the segment you wrote (SDCLK's 6.2 mm diagonal has 3.34 mm of wide track).

Conventions that are reported, not enforced (`checks.conventions` in metrics.json): MCU ring 0/1 balls
leave the ball field on L1, ring 2/3 balls (only D3 = C12 and D10 = N11 here) use a dog-bone via and
leave on L4; at most 3 vias per net (target 2).

## TUNING

A list, applied in order. Three kinds of entry.

1. A serpentine written out: `{"net": "D8", "at": (19.5, 21.1), ...}`. `at` is any point on the straight
   it sits on (within 0.05 mm of the track; add `"layer": "L6"` when two layers of the net overlap in
   plan view).

   | key | meaning |
   |---|---|
   | `side` | `"N" "S" "E" "W" "NE" "NW" "SE" "SW"` = the board direction the humps point to; `"both"` = double-sided chain (legs cross the original line), with `"first": "N"` for the side of the first hump; `"auto"` (default) |
   | `amps: [0.8, 0.8, 0.6]` | hump heights, drawn exactly (heights may differ). Or `n: 3, amp: 0.8`. Each height is exactly the pitch or at least pitch + 0.105; inside a `"both"` chain only the first and last hump are bound by that (inner ones: any height >= pitch) |
   | `add: 2.5` / `to: 31.2` | add this many mm / bring the net to this length: heights are solved: as many humps as the straight takes (low and long before tall and short), as level as possible, each at most `amp_max` (default 2.0) and at most what fits there. Add `n: 3` to fix the number of humps and solve only the heights |
   | `pitch` | leg pitch for this serpentine (else `PITCH`). SDCLK below 0.5 is refused, anything below 0.3 is refused |
   | `where` | `"middle"` (default), `"mcu"`, `"sdram"`, or a number = mm from the track's MCU-side end to the first arc (the number works only with `amps` / `n + amp`; with `add` / `to` it is ignored and the block is centred) |
   | `clr`, `end`, `area_gap` | override a hard limit for this one (never below the DRC clearance of the place) |

   If it does not fit, the build stops and says which limit broke and where (and first prints the
   `CLEARANCE (routes, before tuning)` / `PATH` lines of the routes themselves, so a crossing in ROUTES is
   not hidden behind a failed serpentine). `--force` draws it anyway.
   With `add` / `to` at pitch 0.3 the solver prefers many low humps and, because heights between 0.30
   and 0.405 are illegal, mixes pitch-high humps (no legs) with slightly taller ones, e.g.
   `[0.3, 0.3, 0.451, 0.451, 0.3, 0.3, 0.3]` for +3.0. Give `n` (fewer humps) or `amps` when you want
   fewer, taller humps.
   Several serpentines on one straight: write several entries; each later one lands on the piece of
   track left before or after the earlier one, so give it an `at` on that piece.
2. `{"auto": "net", "net": "D8", "add": 3.0}` (or `"to": 31.2`): the filler finds room on any straight of
   that net. Options: `outside_only` (default True; False also allows 0.09 tracks inside the rule areas,
   i.e. under the SDRAM on L4/L6), `min_run` (2.5), `amp_pref` (1.0), `amp_max` (2.0), `layers`,
   `sides` (`("single", "chain")`), `where`.
3. `{"auto": "window"}`: the baseline's policy. The clock is lengthened towards (longest net - 2.5), then
   every net still below the window is lengthened to its lower edge + 0.05. Same options as 2.

Amplitude a = distance from the original centre line to the centre line at the top of the hump; radius
= pitch / 2. A single-sided hump uses 2 x pitch of track and adds 2a - 0.858 x pitch; a chain of n uses
pitch x (n + 1) and adds 2 x sum(a) - 0.429 x pitch x (n + 1). Lowest amplitude = pitch (no legs); the
next legal one is pitch + 0.105 (see pitfalls). At pitch 0.5 a 1 mm hump adds 1.571 mm, at pitch 0.3
a 1 mm hump adds 1.742 mm in 0.6 mm of track.

Hard limits while placing (`lib/serp.py`): 0.35 mm of straight between the end of the board track (bend,
via, width change) and the first arc; 0.19 mm copper to copper against everything else on the layer,
vias on any layer, pads on L1; a serpentine on 0.1016 track keeps 0.127 mm from every rule-area edge;
a serpentine on 0.09 track (inside a rule area) keeps all its copper inside that area; 0.254 mm to the
board edge; on L1 the centre line stays 0.6 mm from every ball centre.

## What a full build writes to out/<key>/

`routetune.kicad_pro / .kicad_pcb / .kicad_dru` (open the .kicad_pro in KiCad), `metrics.json` (the one
metrics file: nets, totals, space, checks, build_seconds), `tune.txt` (the same as Chinese tables),
`tune.json` (every serpentine block: place, side, heights, gain), `routes.json` (resolved routes, swap
table, pads), `geo.json`, `drc.json`, `track_shape.txt`, and 20 pictures `<view>_<L1|L4|L6|all>.png` for
the views bus, corridor, sdram, south, north. Look at the pictures (Read the PNG) after every full build.

"Done" for a board: `checks.drc.unconnected == 0`, `checks.drc.unexplained == []` (everything left is
`length_out_of_range` = a net outside the window, listed in `totals.out_of_window_by_mm`),
`checks.rule_file_canary.ok`, `checks.rules_matched.ok` (each length rule, probed on its own, matches 19
nets), `checks.geometry.clearance_violations == []`, `path_problems == []`, `off_grid_exact == []`,
`totals.max_abs_geometry_minus_drc_mm` about 0, `checks.drc.length_out_of_range_matches_out_of_window`
true, and `python review/remeasure.py <key>` printing `FINDINGS (0)`.

## Independent check (review)

`python review/remeasure.py <key>` (any Python, no pcbnew, nothing from `lib/`) re-reads the saved board
as text and runs its own DRC length probe: lengths (segments + arcs + via heights from the stackup)
against DRC and metrics.json, via counts, per-layer lengths, direct_mm, hull / bbox / channel width,
same-layer crossings and gaps, 0/45/90 and tangent arc joints, T junctions and loose ends, widths against
the rule areas, via sizes, ball numbers against the KiCad symbol, the swap table (whole lanes only, DQM
follows, CLK), rule-area rectangles and layers. It prints `FINDINGS (0)` on 0_base, 1_baseline and on a
scratch variant that had 0.3 and 0.5 pitch, unequal humps, serpentines on L4 and L6 under the SDRAM and
an L4-L6 via. Run it on your variant after the full build; a finding there is a defect to report.
Three different variants were built at the same time and gave the same metrics.json as built alone
(17-23 s each under load instead of 12-17 s); the only differences were the `at` coordinates of three
entries in the diagnostic list `pairs_below_0.3`, where two spots tie for the same gap.

## Pitfalls already hit

- **A 0.09 track must touch a rule area**, or DRC reports `track_width`. That is why the extra 0.3 mm of
  thin track never runs past a bend, and why a serpentine on a thin track may not leave its area. The
  0.3 mm just outside an area edge is dead for serpentines on either side.
- **A leg of exactly 0.1 mm on a 45-degree track** is stored as 0.0999999 and DRC flags
  `track_segment_length`. Legs are 0 or at least 0.105 (amplitude = pitch, or >= pitch + 0.105).
- **`scripts/track_shape.py` rounds to 1 um before taking angles** and reports short serpentine legs on
  diagonal tracks as "off-grid 134.7 deg". `checks.geometry.off_grid_exact` redoes it on the nm
  coordinates; tune.txt prints both. track_shape.py also does not know arcs at all.
- **Via heights as DRC counts them** on this stackup: L1-L4 1.3932, L1-L6 1.6504, L4-L6 0.2572, all
  three measured against DRC (L4-L6 by the review, on a net with three vias L1-L6-L4-L1). DRC attaches a
  via at the outer surface of L1 / L6 and at the mid-plane of an inner layer. Note L1-L6 + L6-L4 + L4-L1
  = 2 x L1-L6: a third via under the SDRAM costs no extra via length.
- **A via whose two tracks leave in opposite directions** (the track doubles back, e.g. via east of a
  ball reached from the west) shows up in `checks.geometry.via_turn_90_or_more`. The issue-15 review
  counted that as a finding; put the via on the side the track arrives from.
- **Rows under the SDRAM on L4/L6**: vias sit at the centre of four balls (x 24.2, 25.0, 29.0, 29.8 or
  in the ball-free middle x 25.8-28.2; y = 17.1, 17.9, 18.7 ...). A 0.09 track passes a 0.30 via at 0.4 mm
  centre distance with 0.205 mm gap, so inner-layer tracks can run on the ball rows AND on the channel
  rows (0.4 mm pitch), but a via on a row blocks that row on all three layers.
- **MCU edge band** (between package edge and rule-area edge): 0.30 vias at 0.65 pitch in a line, or
  staggered at 0.325 x 0.4. The staggered pattern leaves 0.205 mm from a neighbour's track to the via
  hole (limit 0.2): do not tighten it.
- **The space numbers count only copper outside the two package OUTLINES** (not the rule areas). A hump
  that sticks out from under the SDRAM body into the 1 mm band between body and rule-area edge is
  counted again (the scratch test's bbox grew from 13.25 to 18.59 mm wide that way); copper that stays
  under the body is not counted at all. That is the agreed definition; say so when you compare.
- **A straight that only clips a rule-area corner** (NBL0 and D2 on L6 at the MCU's top-right corner)
  becomes 0.09 for that stretch plus 0.3 mm each side: a short neck in the middle of a diagonal. DRC
  accepts it; it splits the diagonal into separate board tracks for serpentines.
- **Same-layer overlap in plan view is normal** (L1 lane-1 rows sit exactly above L6 lane-0 rows at
  y 20.3 and 21.1). In `*_all.png` the layers are drawn translucent so both show.
- **`at` picks the nearest board track of that net on any layer** unless `layer` is given.
- **The automatic filler puts one serpentine per board track** and never returns to its leftovers.
- **Length window rule**: `build.py` appends `sdram_window` with L = SDCLK's length after tuning. It
  replaces `sdram_len_max` for the same nets (a later length rule wins), so the probe tests each length
  rule alone.
- Git Bash heredocs mangled Python source with `'''` and backslashes; write files with the editor.
- No series resistor on SDCLK in this prototype (the real board will have one near the MCU).
