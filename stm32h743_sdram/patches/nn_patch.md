# Patch proposals from the north / west routing agent (stop 7, try/sgsps @ 0677cdb)

Coordinates are local mm (board mm - 100). Nothing here is applied; the main session decides.

## 1. A12 (SDMMC1_CK): fan-out - VERIFIED on the snapshot (fast geometry check only, no DRC)

Why A12 has no site: its east sites (42.925, 32.125) / (42.925, 32.775) are on the L1 lane of FMC_D2 (ball B12),
which leaves north between A12 and A13 at x 42.925; its west sites (x 42.275) are the +3V3_MCU feed column.

Change (SDRAM group, routes_sdram.py, net FMC_D2, its first L1 piece; nothing else of FMC_D2 changes):

    old  U201.B12 -> (42.925, 32.775) -> (42.925, 31.1) -> (43.225, 30.8) -> (50.15, 30.8) -> ...
    new  U201.B12 -> (42.275, 32.775) -> (42.275, 31.1) -> (42.575, 30.8) -> (50.15, 30.8) -> ...

FMC_D2 then leaves between A11 (unconnected) and A12, over the feed column on L1 (no via there, the L5 feed is not
touched). FMC_D2 gets 0.65 mm longer (22.364 mm in the trial; lane 0 spread must be re-checked by the SDRAM table).

Then A12 in the plan (bga_fan.json signal entry, or fan_leads):

    SDMMC1_CK  ball A12 (42.6, 32.45), via (42.925, 32.125), layer L3, side N,
               run (42.925, 32.125) -> (42.925, 31.0), exit (42.925, 31.0)

The lane at x 42.925 sits between SDMMC1_CMD (L3 x 42.6) and SWCLK (L3 x 43.25) and runs north through the gate row
in the band window x 42.43-43.87. Trial: `out/nn/trial_a12.py` (on top of routes_mcu_nw.py, run to y 25.6): GAP 0,
HOLE 0, no crossing.

Open point for routing CK on: north of y 25.2, the SDMMC1_D1 via (43.25, 24.75) is 0.325 mm from x 42.925
(needs 0.40); CK must turn east before y 25.2 (row y ~25.3 between the D1 via and the SWCLK row y 26.85), and
SDMMC1_CMD turns east at y 24.0 west of it - so CK has to cross CMD on another layer (L6 at the turn) or CMD and D1
swap their turn order. CK's end is the via in front of J801.5 at (56.625, 17.39) (no pull-up): reachable from the
north on L3 (x 56.625, y 13-17.4 is free); not reachable from the south (the D3 L3 hop and the D1 L6 hop cross x
56.6 at y 18.05 / 19.0).

## 2. B14 (SDMMC1_D2), G14 (SDMMC1_D0): NOT solved, not verified

B14 (43.9, 33.1): all four sites are taken - (43.575, 32.775) SDMMC1_D3 (B13), (44.225, 32.775) FMC_D3's second
via (FMC_D3 hops L1 -> L3 at (42.925, 33.425), along row B on L3, back to L1 at (44.225, 32.775)), (43.575, 33.425)
FMC_D27, (44.225, 33.425) FMC_D26. Candidates looked at:
- B13 to (42.925, 32.775) (free on L1 once FMC_D2 moves, item 1) and B14 to (43.575, 32.775): B13's run then has
  no way north (A12's new via at (42.925, 32.125) directly north, SWCLK's L3 lane at x 43.25 east). Fails with item 1.
- FMC_D3 stays on L3 east along y 32.775 and returns to L1 outside the area (around x 49.6), freeing (44.225,
  32.775) for B14: B14's run would then need that same L3 row (its north is the SWDIO via (44.225, 32.125)). Fails.
- Left: B14 on L6 from (44.225, 32.775) needs FMC_D3's via moved and a free L6 path between SWDIO (43.9) and
  FDCAN1_TX (via (44.875, 33.425), L6 east at y 33.1): not checked.
G14 (43.9, 36.35): the probe of stop 7 (routes_probe_east.py) reached it through the SW site (43.575, 36.675), which
is now a +3V3_MCU via; L6 on rows D-K east has no free lane. Not checked further.

## 3. Gate-row conflicts with the other group (no patch possible from this side)

My L6 lanes BOOT0 (x 39.35) and SD_CD (x 41.95) come out of the tunnel under the SDRAM rivers on exactly the x of
the other group's L3 gates QSPI_BK1_NCS (39.35, 27.6) and LCD_G7 (41.95, 27.6). The other group's layer-change vias
must sit at y 27.0-27.35 (L4 river at y 27.75, "within 0.6 mm of the gate on its x"): such a via lands on my lane.
SD_CD jogs to x 41.6 at y 27.25 (still 0.35 mm from (41.95, 27.6)); BOOT0 cannot move (boxed on L6 by LCD_BL_PWM
38.05 / LCD_G3 40.65 and on every other layer by the rivers and the NCS lane). Besides: at x 38.7 and 41.95 the
other group's vias would also hit the power vias (38.587, 27.15) and (42.025, 26.925). One of the two groups has
to give way here; the main session decides (e.g. the plan swaps D6 BOOT0 and B6 QSPI_BK1_NCS layers, or NCS leaves
north on L3 past my BOOT0 via at (39.35, 24.5)).

## 4. Layout suggestion (optional, place.py / copper.sketch): microSD pull-ups

R801-R806 are in the order CMD, D0, D1, D2, D3, CD while the socket contacts are D2, D3, CMD, CK, D0, D1, CD, and
the L1 band of +3V3_SD (y 17.85-18.65) lies between pull-ups and socket. Every SD line therefore needs
Va -> pull-up -> Vb -> inner hop -> Vc -> contact (3 vias beyond the fan-out) and the hops differ by up to 5.6 mm
(D1: R803 x 54.3 -> contact 8 x 59.9), which spreads the SD lengths by 10.8 mm (SPEC 9 allows 5). Pull-ups in
contact order, each in line with its contact, and the +3V3_SD feed taken round the pull-up row (not between it and
the socket), would make every link one straight L1 piece and the lines equal within ~1 mm.
