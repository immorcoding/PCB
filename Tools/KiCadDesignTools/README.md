# KiCadDesignTools

The workspace's own schematic and board tools. Everything runs from the repository root with KiCad's python
(`D:\KiCad\bin\python.exe`, not on PATH; `KICAD_BIN` overrides the folder, see `core/paths.py`):

    D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.<category>.<tool> <args>
    D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.build <board dir> <step> [--dry-run]
    D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.build init NAME [--from DIR] [--parent DIR]   (a new board folder)
    D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.regress            (every benchmark, PROC-15)
    D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.regress --board demo   (the demo board built from its data, ~12 min)

No tool edits `sys.path`; board files (routes files, schematic pages) import
`from Tools.KiCadDesignTools.routing.busroute import ...`. busroute loads a routes file of a board folder as a module
of that folder's package (`<board>.<stem>`; `<board>.probes.<stem>` for the trial files in `probes/`). The rules the
tools serve are in `docs/shape/`, their numbers in `docs/rule-profiles/` and each board's `SPEC.md`; the KiCad /
pcbnew pitfalls are numbered K1, K2 ... in [docs/tools.md](../../docs/tools.md) ("已知的坑"), and the column "Pitfalls"
below points there. Arguments in detail: each module's docstring.

A board folder holds data only: `board.toml` (layer roles, template, net classes, every step's parameters), `place.toml`,
`silk.toml`, `rules_cases.py`, `bga_block.toml`, `copper.sketch`, `length_groups.json`, `routes_*.py`, `sch/<page>.py`,
`SPEC.md`, `unverified.md`, `pins.csv`, `swap.csv`, `probes/` (trials, not built by the driver). A number that another
board would choose differently lives there, not in a module (stage-3 rule); numbers of the rule profile that a tool
needs are given by the board too, see "Board values" at the end.

Status (2026-11-24, branch `tools-consolidation`): stages 1-3 moved `scripts/` and the H743 board folder's scripts here
and their constants into the board's data files; the driver calls Tools modules only. H1 fixed bugs found on the way,
H3 added the length-planning tools (`planning/`), H4 the profile-C template (`templates/C-bga-065/`), `spec_check`, the
demo board (`templates/demo_board/`), `build init` / `pcb-update` and `regress --board demo`; H2 (stage 4) brought
`docs/` up to date and moved the last profile numbers out of code.

## Tools

`...` = `Tools.KiCadDesignTools`. Rules: ids of `docs/shape/` (detail in "规则对照" below). Benchmark: folder under
`tests/` run by `regress`; "demo" = the whole-board bench `regress --board demo`.

| Category | Tool | Command | When | Rules | Benchmark | Pitfalls |
|---|---|---|---|---|---|---|
| (driver) | `build` | `-m ...build <board dir> <step> [--out DIR] [--skip-match] [--upto GROUP] [--no-render] [--dry-run]`; `... <board dir> compare <out A> <out B>`; `... init NAME [--from DIR] [--parent DIR]` | every build step of a board: project, rules, sch, pcb-update, layout, copper, route, finish, checks, publish, all, compare; init: a new board folder from a template folder (default `templates/demo_board`) | PROC-1, 2, 4, 6, 13; FIN-4 | `--dry-run`; demo | K2, K28, K30 |
| (driver) | `regress` | `-m ...regress [name ...]`; `--board demo [--keep]` | after a change to any tool or to a rule file (RUL-2) | PROC-15, RUL-2 | (it runs them) | K30 |
| core | `paths` | (library) | KiCad, Edge and repository paths (`KICAD_BIN`) | | | |
| core | `config` | `-m ...core.config <board dir>` | read and check `board.toml` (layer roles -> L1..Ln, KiCad names), the board's data files and modules | | | K27 |
| core | `heavy` | (library) | every kicad-cli / KiCad-python launch: below-normal priority on four cores, one at a time (machine-wide lock, re-entrant), a pause between them, exit codes checked (`run`, `kicad_cli`, `kicad_py`); KiCad lock files | PROC-6, RUL-4 | `tests/heavy` | K2, K30 |
| core | `stackup` | (library) | a fab stackup from `data/stackups/<name>.toml` (`[board] stackup`): thickness, via heights | | `tests/planning` | K15 |
| core | `uuids` | (library) | deterministic uuids (uuid5 of a stable key) for what the board writers add: the same build gives the same board file | PROC-13 | | |
| core | `boardtext` | `-m ...core.boardtext <board dir> unfill/strip/orphans <board> [GROUP ...]` | text edits of a `.kicad_pcb`: copper rows of the layer table; drop the saved fills; remove what busroute groups wrote (`<board>.busroute.json`); remove copper no group owns | RTE-12 | | K20, K25, K44, K50, K51 |
| project | `make_project` | `-m ...project.make_project <board dir> [--new-pcb]` | `.kicad_pro` from the profile's template (`templates/<[board] template>/`) plus `board.toml` (`[project]`, `[netclasses]`, `[netclass_patterns]`), empty board with the stackup, derived footprints (`[[footprints.derived]]`), layer table; lists template rule names missing from the board's rule file | RUL-1, RUL-11, PROC-13 | demo | K2, K12, K33 |
| project | `spec_check` | `-m ...project.spec_check <board dir> [--profile <md>]` (any Python >= 3.11) | SPEC.md's table 本板取值 against the profile's table 布局和走线的取值 and the data files it names; the layout step runs it first | PROC-8, RUL-1 | `tests/spec_check` | |
| rules | `fixture` | `-m ...rules.fixture <board dir> <out>` | every rule breaks and passes on a fixture board (cases: `<board dir>/rules_cases.py`); the rules step | RUL-2 | (it is one); demo | K1, K12, K57 |
| rules | `dru_canary` | `-m ...rules.dru_canary <board>` | the rule file is loaded (prints `OK`) | RUL-2, FIN-4 | `tests/drc_tools` | K1 |
| rules | `dru_match` | `-m ...rules.dru_match <board> [--json F]` | every rule matches something (one DRC per rule, slow; the driver's `checks`) | RUL-2 | `tests/drc_tools` | K13, K14 |
| rules | `drc_probe` | (library) | DRC on a copy with another rule file, report parsing, net lengths by probe rules | RUL-2 | `tests/drc_tools` | K13, K14, K24, K31 |
| rules | `len_rules` | `-m ...rules.len_rules <board> [--check]` | length-window rules from `length_groups.json` into the generated block of the `.kicad_dru` | RTE-2, RTE-14 | `tests/drc_tools` | K15, K57 |
| rules | `impedance` | `-m ...rules.impedance [--layer L]` | trace impedance on the JLC06161H-3313E stackup (2D field solver; computed, the fab's calculator rules) | RUL-3 | `tests/impedance` | |
| schematic | `kisch` | (library) | schematic writer: one sheet or pages (`Design.page`), global labels; see docs/tools.md "原理图分页" | RUL-6, RUL-8 | `tests/kisch` | K18, K19 |
| schematic | `sheet` | (library) | page-drawing helpers for the board's `sch/<page>.py` (stubs to power symbols or global labels, page-numbered references, grid units, two-pin parts; `[schematic]` power_symbols, footprints, power_copies) | RUL-6, RUL-8 | demo | K18, K19 |
| schematic | `swap` | (library) | the swapped memory part's ball map (the page's grid `BALLS`, `[schematic.swap]` columns, balls, nc_as) and swap table (`[schematic.swap] table`), for its page's `ball_map()` (one line) and `schematic.check` | RUL-6 | demo | |
| schematic | `generate` | `-m ...schematic.generate <board dir> [page ...] [--out DIR]` | the multi-page schematic from `[schematic] pages`, project symbol library, sym-lib-table | PROC-13 | demo | K19 |
| schematic | `build` | `-m ...schematic.build <board dir> <out> [--page NAME ...]` | generate, upgrade, ERC, netlist, PDF; `--page`: some pages alone in `<out>`; a folder without board.toml runs its own `gen_sch.py` | RUL-6 | demo | K17 |
| schematic | `check` | `-m ...schematic.check <board dir> <netlist>` | netlist against the drawing's intent, the pin table (`[schematic.pin_table]`), the SDRAM byte lanes (`[schematic.swap]`) | RUL-6 | demo | |
| schematic | `net2pcb` | `-m ...schematic.net2pcb <netlist> <board>` | netlist into the board (KiCad's "Update PCB from Schematic"; the driver's `pcb-update`) | | demo | K3, K12, K50 |
| placement | `place` | `-m ...placement.place <board dir> [--pcb <copy>] [--rot <angle>]` | every part, outline, holes, rule areas and F.Cu no-pour areas from `place.toml`; parks unlisted parts below the board; `--pcb`/`--rot`: trials on a copy | LAY-1, LAY-7, RTE-1, PROC-13 | demo | K3, K32, K33, K36 |
| placement | `layout_probe` | `-m ...placement.layout_probe <board dir> [--pcb <board>] [--json <out>]` | measured trials: rails against the copper sketch, crystals, switcher loops, bus lengths, LCD fan (`[probe]`; every trial but the rails optional) | LAY-3, RUL-7 | demo | |
| placement | `place_check` | `-m ...placement.place_check <board> --limit MM --ground NET [--edge REF=SIDE ...] [--allow-under ...] [--not-supply ...] [--json F]` | placement metrics: placed / parked, overlaps, hole and footprint keep-outs, edges, bottom under top pads, decoupling distance against `--limit` (the driver passes `[layout] decap_limit` and `[power] ground`), room for silk | LAY-2, 5, 6, 8 | `tests/place_check` | K35, K55 |
| placement | `escape_check` | `-m ...placement.escape_check <board dir> <board> --ref U1 [...] [--window x0 y0 x1 y1] [--layers ...] [--debug U1.A1 <png>]` | a way out for each pad of fine-pitch parts (up to two vias), on the line-order sketch copy (`[[layout.escape]]`, `[[route.escape]]`); layers, ground net, origin and the rule values from the board folder | LAY-2, RTE-13 | `tests/place_check` | K37, K43 |
| placement | `via_spots` | `-m ...placement.via_spots <board> near X,Y[,R] ... --net NET` or `... grid PITCH --net NET` | legal via spots of the net NET (ignores footprint keep-outs, profile A note) | PWR-5 | | |
| copper | `cu_sketch` | `-m ...copper.cu_sketch check/apply/read/measure ...` | copper region sketch: check, write zones (`cu:` / `cu-whole:` only), read back after hand edits, measures | PWR-3, 4, 7, 8, 9, LAY-1 | `tests/cu_sketch` | K4, K6, K20, K21, K23 |
| copper | `plane_slots` | `-m ...copper.plane_slots <board dir> <refilled board> <out> [--window NAME x0 y0 x1 y1] [--layers L5] [--stem S] [--part-b F]` | plane slots (merged antipads) listed over `[copper.slots] report`, cut-off own-net vias, the BGA blocks' feed necks | RTE-5 | | K4 |
| copper | `copper_table` | `-m ...copper.copper_table <board dir> <board> <out>` | the copper step's table: copper-class connectivity by pcbnew on the refilled board, feed vias per rail, ground vias, part B (BGA balls, bottom decoupling against `[layout] decap_limit`) (`[copper.table]`) | PROC-4, PWR-6, LAY-2 | | K24 |
| copper | `power_ties` | (library) | the power group's site planner for `routes_power.py`: vias, ties, hops beside pads (`[power]`, layer roles) | PWR-2, PWR-5 | | K26 |
| copper | `bga_power` | (library) | BGA supply / ground fan-out and bottom decoupling for `routes_power_bga.py` (`[bga.<ref>]`, `[power.bga]`) | PWR-5, LAY-5 | demo | K26, K41, K42 |
| copper | `pour_islands` | `-m ...copper.pour_islands <board> <zone> ...` | pour pieces without a via or through-hole pad | PWR-6 | | K22 |
| routing | `busroute` | `-m ...routing.busroute.build <routes.py> [--fast] [--sketch] [--out DIR] [--write-board] [--tuning-budget] ...` | bundles, BGA fan-out, layer-change via arrays, serpentines and their budget, geometry checks, board writing, DRC, lengths, metrics, pictures; the routes file format is in `busroute/job.py` | RTE-2, 3, 4, 7, 13, 15, RTE-5 | `tests/busroute` | K25, K38, K40, K41, K45-K49, K52, K53, K56, K58 |
| routing | `busroute.*` | (library) | `board` (board reader), `build` (command), `bundle` (bundles, slots), `checks` (geometry, via counts, lengths), `fanout` (BGA fan-out rules), `geom`, `job` (routes file loader and stages), `metrics` (the bus table), `profile` (widths, clearances, vias from `.kicad_pro` / `.kicad_dru`; profile-C class defaults only as fallback; `slot_max` 1.5 for via fields, see RTE-5), `render` (pictures), `routes` (routes helpers), `tune` (arc serpentines, RTE-2 / RTE-7) | as above | `tests/busroute` | as above |
| routing | `fan_plan` | (library) | a BGA block plan (`place.toml [fan]`, `bga_fan.json`) as busroute pieces for the routes files | RTE-13, RTE-4 | demo | K26 |
| routing | `tune_sites` | `-m ...routing.tune_sites <board dir> [board] [--spread S] [--window W] [--margin M] [--natural M] [--json F]` | room for serpentines beside each straight of the bus nets, on a build without serpentines (`NOTUNE=1` for the build, not for this tool) (`[tune_sites]`; the bus routes file's `TUNING`) | RTE-2 | | |
| planning | `bga_dump` | `-m ...planning.bga_dump <board dir> [board] [--out geo.json]` (KiCad's python) | a board as geo.json (pads, vias, tracks, zones, rule areas, keep-outs, stack, rule values) for the BGA planners | RTE-13 | | K29 |
| planning | `bga_fan` | `-m ...planning.bga_fan <board dir> --geo <geo.json> --out <dir> [--slot-max] [--time] [--only] [--staged] [--fixa]` (system python: numpy, scipy) | offline BGA block plan (the H743's `bga_fan.json`): supply / ground vias, bottom decoupling, MCU signal fan-out, one MILP on the ball lattice (`bga_block.toml [block]`, `[fan]`). Environment switches for experiments only (the module's docstring; a build sets none): `FAN_NOSUP`, `FAN_NOSIG`, `FAN_NOCAP`, `FAN_NOSIGSLOT`, `FAN_NOSTAIR`, `FAN_ROUNDS`, `FAN_UNALLOC`, `FAN_CAPOPT`, and the what-ifs over the data `FAN_REACH`, `FAN_DROP`, `FAN_NOFEED`, `FAN_SIDES_FREE` | RTE-13, LAY-5; RTE-5 (see 规则对照) | | K29 |
| planning | `bga_plan` | `-m ...planning.bga_plan <board dir> dump/plan/check ...` (system python: numpy, scipy, scikit-image) | offline whole-BGA model with the SDRAM line order (`try/fanout-first`; reads `probes/line_order/balls_identity.json` through `bga_block.toml`) | RTE-13 | | K29 |
| planning | `bga_grid` | (library) | exact clearance fields on a 0.025 mm grid, via sites, plane-slot chains, grid escapes (layers from `board.toml`, rule values from the geo's dump of the rule files, plane clearance and minimum width from the copper sketch) | | | |
| planning | `measure` | `-m ...planning.measure <board dir> [board] [--nets N ... or --group G ...] [--json F] [--txt F]` | net lengths pad to pad (tracks, exact arcs, via heights), natural length, serpentine blocks, per layer; byte lanes, clock sum, address window | RTE-2, RTE-14 | `tests/planning` | K15, K45, K53 |
| planning | `check` | `-m ...planning.check <board dir> [board] [--nets ... or --group ...] [--free DATA.py] [--json F]` | exact clearance check of planned paths against the board's copper; `free_area` per region | RTE-2 | `tests/planning` | |
| planning | `serp` | (library) | serpentine geometry of a plan (tune.py's RTE-2 humps) and the block rules (end straights, height window, outside rule areas) | RTE-2, RTE-7 | `tests/planning` | K46, K47 |
| planning | `plan` | `-m ...planning.plan <board dir> <plan data .py> [board] [--out DIR] [-v]` | a length plan on paper (example `stm32h743_sdram/probes/plan50/plan_h743.py`) (`[plan]`) | RTE-2, RTE-7, RTE-13 | `tests/planning` | |
| finishing | `finish` | `-m ...finishing.finish <board dir> strip/fiducials/pours/clean/report/stitch/pieces/silk/teardrops <board> [<out> ...]` | the finish step's sub-steps: strip what the last run wrote (`<board>.finish.json`), fiducials, dispatch to the modules below | FIN-4, PWR-5 | demo | K22, K28 |
| finishing | `pour` | (library; `finish pours/clean/report`) | inner ground pours, keep-outs over the BGA rule areas and serpentines, clean-up of narrow copper and small pieces, pour report (`[finish.pour]`) | PWR-5, FIN-4 | demo | K22, K23 |
| finishing | `stitch` | (library; `finish stitch/pieces`) | ground stitching vias: piece anchors, then greedy coverage (`[finish.stitch]`) | PWR-5, FIN-4 | demo | K22 |
| finishing | `silk` | (library; `finish silk`) | references to Fab, fine-pitch mask expansion, labels, glyphs, title blocks (`silk.toml`) | FIN-1, FIN-2, FIN-3 | demo | K8 |
| finishing | `teardrops` | `-m ...finishing.teardrops <board>` or `<board dir> <board>` | teardrops (last): every pad and via, or outside `[finish.teardrops] skip_boxes` | FIN-4 | demo | K7 |
| finishing | `silk_refs` | `-m ...finishing.silk_refs ...` | reference designators on sparse boards | FIN-1 | | |
| views | `pcb_view`, `layer_view` | `-m ...views.<tool> ...` | pictures with tracks and ratsnest; one layer with a coordinate grid (qualitative only) | PROC-14, RTE-6 | | |
| views | `copper_view` | `-m ...views.copper_view <board dir> <board> <out> [L1 ...] [--scale] [--window ... --name] [--slots] [--via-labels]` | the filled copper per layer (`[copper_view]`) | PROC-14 | | K31 |
| views | `place_view` | `-m ...views.place_view <board dir> dump [board]` (KiCad's python), then `... draw [x0 y0 x1 y1 name]` (matplotlib) | pads and courtyards of the placement, whole board or a window | PROC-14 | | |
| views | `finish_view` | `-m ...views.finish_view <board dir> <board> <out>` (Edge) | the silkscreen over copper, both sides, close-ups of `[finish.view] close` | FIN-2, PROC-14 | | K31 |
| views | `sketch_view` | `-m ...views.sketch_view <board dir> <out>` (matplotlib) | the copper sketch per layer with the package bodies, rule areas and holes of `place.toml` | LAY-1, PROC-14 | | |
| views | `publish` | `-m ...views.publish <board dir> [--rest 20] [--stage all/dump/svg/png] [--only ...]` (Edge) | release pictures with net names: every copper layer, outer layers with silkscreen, close-ups, layers stacked (`[publish]`) | PROC-11, PROC-14 | | K31 |
| analysis | `route_table` | `-m ...analysis.route_table <board dir> <board> <out>` (env ROUTE2_GROUPS) | the route step's table: the bus group's lengths, serpentines, vias against the limit, order, copper, slots (listed over `[route.table] slot_list`), escape; one row per routes file, gap crossings, pairs, placement (`[route.table]`) | PROC-4, RTE-5, RTE-8, PROC-12 | demo | K24, K28 |
| analysis | `track_shape` | `-m ...analysis.track_shape <board>`; `track_shape.run(board)` -> the report parsed (route_table, busroute metrics) | track shapes DRC does not check (non-45, steps, small chamfers, crowded bends, arcs) | RTE-8, 9, 10, 11 | `tests/track_shape` | K48, K59, K60 |
| analysis | `board_diff` | `-m ...analysis.board_diff <a> <b>` | two board files item by item (uuids aside, fills as areas) | LAY-10, PROC-13 | | |
| analysis | `compare_runs` | `-m ...analysis.compare_runs <out A> <out B>` | two builds' reports number by number (the driver's `compare`) | PROC-4, LAY-10 | | |
| third_party | `auto_tracks`, `auto_clean`, `auto_tidy` | `-m ...third_party.<tool> ...` | KiCadRoutingTools output: to JSON for replay, clean-up, straighten (by exception only) | RTE-4 | | docs/tools.md "用 KiCadRoutingTools 时" |

Benchmarks (`tests/`): `busroute` (`check.py` with `bench_routes`, `bench_tune`, `bench_ties`, `bench_obstacles`;
fixture board in `fixture/`), `cu_sketch`, `drc_tools` (canary, matching, probes, length windows), `impedance` (closed
forms and published numbers), `kisch`, `place_check` (place_check and escape_check), `planning` (measure, check, serp,
plan), `spec_check` (with `fixture/routes_bus.py`), `track_shape`; `demo_board/expected.json` for `regress --board demo`.

Whole-board bench: `regress --board demo` copies `templates/demo_board` with `build init` into `out/regress/` (git-ignored,
inside the repository: board folders are imported as packages), runs project, rules --skip-match, sch, pcb-update,
layout, route --skip-match and finish --no-render on the copy, and checks the step exit codes, the rule fixture, the
schematic checks, the final DRC with schematic parity by type, unconnected items, the byte lane's spread and the
address window against `tests/demo_board/expected.json`; not part of the default run (about 12 minutes).

Several older tools read `sys.argv` when imported (script style); run them only as commands.

## Board values

Numbers the rules put into the rule profile (`docs/rule-profiles/<profile>.md`, table 布局和走线的取值) or the board's
SPEC reach the tools through the board's data, never through a module constant. `project.spec_check` compares the
SPEC's table 本板取值 with these sources (which side rules: `templates/C-bga-065/README.md`).

| Value (rule) | Where the tools read it | Tools |
|---|---|---|
| layer roles, signal-layer count (PROC-8) | `board.toml [layers] roles` | all (`core.config`) |
| small decoupling to its supply ball, upper limit (LAY-2) | `board.toml [layout] decap_limit` (since H2; was `place_check --limit` default 2.5 and a constant 2.5 in `copper_table`) | `place_check --limit` (passed by the driver), `copper_table` |
| serpentine pitch per class, start amplitude, end straights, clearances (RTE-7, RTE-2) | routes file `TUNING` (`pitch`, `amp`, `amp_max`, `keep`, `end`, `clr`, `area_gap`, `radius`) | `busroute.tune`, `planning.serp` / `plan`; `tune.DEFAULTS` is only the fallback for a key a `TUNING` leaves out (every routes file in the repository writes all of them) |
| byte-lane skew, address window (RTE-14) | rule file (`<lane_rule>N` skew), `length_groups.json` (windows), routes file `TUNING` groups | `len_rules`, `busroute`, `planning.measure`, `route_table` |
| via-count limit and which nets (RTE-5) | rule file (`sdram_via_max`), routes file `VIA_LIMIT` | `busroute.checks` / `metrics`, `route_table` (the "nets using the limit" list follows the limit since H2) |
| power-plane block gap (PWR-8), outer pour minimum width (PWR-5) | `copper.sketch` (`gap`, `minwidth`), `board.toml [finish.pour] min_width` | `cu_sketch`, `finishing.pour` |
| rule values: track width, clearance and via inside the rule areas; outside them the narrowest net class (width, clearance, smallest class via); hole to copper, hole to hole, plated part holes (RUL-1) | the board's `.kicad_pro` / `.kicad_dru` (written by `make_project` from `templates/<template>/`), read by `core.config` `cfg.rules()` (busroute's `Profile`; `w_out()`, `clr_out()`, `via_out_min()`, `pth_hole_hole`); the BGA planners from the geo's dump of the same files (since R2; were constants 0.09 / 0.127 / 0.1016 / 0.30 / 0.45 / 0.2 / 0.254 / 0.45 in the modules) | `escape_check`, `bga_power`, `power_ties`, `bga_grid` / `bga_fan`, `tune_sites` (class width) |
| the planes' zone clearance and minimum width (PWR-8) | `copper.sketch` (`plane_clearance`, `minwidth`), `cfg.copper_plane()` (since R2; were 0.127 / 0.2 in `bga_power`, `bga_grid`) | `bga_power`, `plane_slots`, `bga_grid` / `bga_fan` / `bga_plan` |
| the ground net, the bus nets | `board.toml [power] ground`, `bus_prefix` (since R2 also: `escape_check`, `place_check --ground` from the driver, `bga_fan`; `via_spots --net` for boards without a board.toml) | as listed |
| the BGA power planner's own choices: via pitch, stub limit, own ground via distance (LAY-5), dog-bone / stub / VCAP widths, 90-degree sharing | `board.toml [power.bga]` (since R2; were module constants and the switch `BGA_SHARE90`; `BGA_PARITY` dropped: `[bga.<ref>] parity` is the source) | `bga_power`, `copper_table` (`gnd_via_max`), `bga_fan` (dog-bone width of a fixed stage) |
| serpentine survey: keep, clearance, amplitudes, pitch per net, area gap, margin, each lane's spread, the address window; shortest straight | the bus routes file's `TUNING` (group of `[route.table] bus`), `[route.table] straight` (since R2; were constants in `tune_sites`, the `--spread` / `--window` defaults 5 / 20) | `tune_sites` |
| BGA block planner: VDDA filter out of the state, capacitor rewards (FAN_CAPOPT) | `bga_block.toml [fan] novdda.drop`, `cap_bonus` (since R2; were `FAN_NOVDDA` and C218 / C219 in code) | `bga_fan` |
| byte lanes | `board.toml [schematic.swap] lanes` (since R2 also `regress`: the widest lane's spread) | `regress --board`, `tune_sites`, `route_table`, `measure` |
| plane slots: no limit (RTE-5) | report thresholds only: `[copper.slots] report`, `[route.table] slot_mark` and `slot_list` (since H2; was a constant 2.5 in `route_table`) | `plane_slots`, `route_table`; exceptions that still limit: busroute's via-field check (`Profile.slot_max = 1.5` in code, `PROFILE` can override) and `planning.bga_fan` (`bga_block.toml [block] slot_max`), see 规则对照, RTE-5 |

## 规则对照

`docs/shape/` 的每条规则（2026-11-24 的各区域文件）对哪个工具、覆盖到什么程度。状态：**覆盖**（工具做了规则要的可算部分）、**部分**、**未覆盖**（没有工具；做法类、交流类的规则大多如此，不一定要有工具）、**不一致**（工具做的和规则说的相反）。规则正文点着已经不存在的路径时（RUL-2、PWR-6、RTE-8、PROC-15）在说明里注明，状态按工具算。规则里的数值在 `docs/rule-profiles/C-bga-065.md` 的“布局和走线的取值”和板子的 SPEC，工具从哪里读见上一节。

| 规则 | 工具 | 状态 | 说明 |
|---|---|---|---|
| RUL-1 从模板起；规则值只写在规则文档和规则文件 | `project.make_project`、`templates/C-bga-065/`、`project.spec_check` | 不一致 | 从模板起已覆盖；“别处不重复”和 SPEC 的“本板取值”表、走线文件的 `TUNING` / `VIA_LIMIT`、`length_groups.json` 冲突（同一个数几处都有，由 `spec_check` 对着查），收件箱已记。工具代码里的规则数值副本 R2（2026-11-24）已去掉：`escape_check`、`bga_power`、`power_ties`、`bga_grid` / `bga_fan`、`tune_sites` 从板子的 `.kicad_pro` / `.kicad_dru` 读（`cfg.rules()`；规则区外取最窄的网络类），平面的铺铜间距和最小宽度从 `copper.sketch` 读；没有另建规格档数据文件（规格档的这些数已经在模板生成的工程文件和规则文件里，再写一份就是副本） |
| RUL-11 方案阶段选规格档 | `board.toml [board] profile`、`spec_check` | 部分 | 选档是人定的；`spec_check` 按所选档的表查 SPEC |
| RUL-12 BGA 按球距列计算表 | — | 未覆盖 | 计算表在规格档里手写；没有按焊盘和规则算余量的工具 |
| RUL-2 金丝雀、每条规则匹配到对象、基准板、改规则后跑回归 | `rules.dru_canary`、`rules.dru_match`、`rules.fixture`、`regress`；驱动的 `rules`、`checks` | 覆盖 | 正文点的 `scripts/dru_canary.py` 已不存在（收件箱已有改路径的提议） |
| RUL-3 按叠层算阻抗，用户在板厂计算器上核 | `rules.impedance` | 部分 | 只有 JLC06161H-3313E 一种叠层，写死在模块里（`data/stackups/` 有同一叠层的数据，没接上）；板厂计算器那一半是人做 |
| RUL-4 改 `.kicad_pro` 后在用户关 KiCad 后读回核对 | `core.heavy.kicad_lock`、驱动 | 部分 | 有锁文件就不写；“关掉之后读回核对”没有工具 |
| RUL-5 例外先问用户 | — | 未覆盖 | 交流类 |
| RUL-6 ERC 干净、网表逐网络核对、大芯片引脚对官方表 | `schematic.build`、`schematic.check` | 覆盖 | 意图对网表、`[schematic.pin_table]`、`[schematic.swap]` |
| RUL-7 连接器引脚分配对照布局草图 | `placement.layout_probe`（LCD 扇出） | 部分 | 只量直连线穿过哪些器件；引脚分配本身不算 |
| RUL-9 kicad-happy 原理图审查 | 驱动的 `sch`（`[schematic] review`） | 部分 | 自动跑分析脚本并计数；甄别是人做 |
| RUL-10 引脚和参数对规格书 PDF 核对 | — | 未覆盖 | 读规格书是子任务的事（`pdftotext`、`pdftoppm`） |
| RUL-8 文字不带换行、符号在 1.27 网格 | `schematic.kisch`（`text()` 转义）、`schematic.sheet`（网格单位） | 覆盖 | |
| LAY-2 去耦距离、出线通道、电源能否连成一块 | `placement.place_check`、`placement.escape_check`、`copper.cu_sketch`、`copper.copper_table` | 覆盖 | 距离上限从 `board.toml [layout] decap_limit` 读（H2 起）；`escape_check` 的层、地网络、原点和线宽 / 间距 / 过孔 R2 起从板目录读（层用途、`[power] ground`、`cfg.rules()`），不再有默认的 L1 L4 L6；出线只按单个引脚判，没有容量（信号已记） |
| LAY-3 交审查前试走四类网络 | `placement.layout_probe`、`probes/routes_probe_*.py`（busroute 试走） | 部分 | `layout_probe` 量距离和直线，真正的试走要另写走线文件；以太网差分对这类没在探针里 |
| LAY-9 布局验收跑 kicad-happy `emc` | — | 未覆盖 | 驱动不跑 `emc` |
| LAY-6 封装禁布区和板边开槽 | `placement.place_check`（keepout、edge） | 覆盖 | |
| LAY-1 先画铜皮草图，器件围着摆 | `copper.cu_sketch check`、`views.sketch_view`、驱动的 `layout`（草图检查） | 部分 | 先后顺序是做法；工具只查草图本身 |
| LAY-4 阵列间隔够过一根线、大电容间放得下过孔 | — | 未覆盖 | `place_check` 只查重叠，不查间隔够不够走线 |
| LAY-5 背面不压顶面焊盘；BGA 背面小封装贴过孔 | `place_check`（under、`--allow-under`）、`copper.bga_power`、`planning.bga_fan`、`copper_table`（短线长度） | 覆盖 | 封装大小（0402）不由工具查；背面短线上限、电容自己的地过孔距离（0.7 / 1.0）R2 起在 `board.toml [power.bga]`（`stub_max`、`gnd_via_max`；`copper_table` 也读后者），还没有规则说它们归规格档（收件箱已记） |
| LAY-7 焊盘坐标从板文件读 | 全部读板的工具（`planning.bga_dump`、`views.place_view dump`） | 覆盖 | |
| LAY-8 排针测试点旁留丝印位置 | `place_check`（silk） | 覆盖 | 只报，不判失败 |
| LAY-10 大动开 try 分支，两边同一张表对比 | `analysis.compare_runs`（驱动 `compare`）、`analysis.board_diff` | 部分 | 分支和选择是人做 |
| PWR-1 网络分成走线类和铜皮类，列表给用户 | `board.toml [copper.table] nets`、网络类 `PWR` 的匹配 | 部分 | 分类表是数据；确认是人做 |
| PWR-2 铜皮类不进布线器、不先拉线 | 驱动的 `copper` 一步在 `route` 之前，电源组（`routes_power*.py`）只写焊盘到铜皮的短线和过孔 | 覆盖 | |
| PWR-3 铜皮外形手工定，只用 0/45/90 | `copper.cu_sketch check` | 覆盖 | |
| PWR-4 按草图分块，不自动分割 | `copper.cu_sketch apply` | 覆盖 | 没有自动分割的工具 |
| PWR-7 草图是文本，检查通过才生成，手改后先读回 | `copper.cu_sketch check/apply/read` | 覆盖 | |
| PWR-8 电源层块间缝是草图参数，数值在规格档 | `copper.cu_sketch`（`gap`）、`spec_check` | 覆盖 | |
| PWR-5 地：整层加外层和内层信号层铺地，禁铺区，清碎铜，每片有地过孔；地不走线 | `finishing.finish`（`pours`、`clean`、`stitch`、`pieces`）、`copper.bga_power` / `power_ties`（焊盘旁打孔） | 覆盖 | |
| PWR-6 连没连上以 KiCad 填充为准；`pour_islands` 补孔 | 驱动（`kicad-cli ... --refill-zones`）、`copper.pour_islands`、`copper.copper_table`（pcbnew 连通） | 覆盖 | 正文点的 `scripts/pour_islands.py` 已不存在（收件箱已有提议） |
| PWR-9 铺铜焊盘连接沿用规则文件；插件焊盘整个包住 | `copper.cu_sketch check`（th-pad，`th_margin`） | 覆盖 | `th_margin` 0.3 是工具作者定的草图参数默认值（信号已记） |
| RTE-5 约定量化进 SPEC；过孔数上限只给有时序要求的线；换参考面配地过孔；平面槽不设上限 | `busroute`（`VIA_LIMIT`、换层地过孔）、`analysis.route_table`、`copper.plane_slots`、`planning.bga_fan` | 不一致 | 过孔上限和地过孔覆盖；槽长在报表里只报（`slot_mark` / `slot_list` / `report`），但还有两处当上限用：`busroute` 换层过孔阵的 `SLOT` 检查（`busroute/profile.py` 的 `Profile.slot_max = 1.5`，代码里的数，走线文件可用 `PROFILE` 改；超了构建失败；现在两块板都是 `SLOT 0`），离线规划器 `planning.bga_fan` 的 `bga_block.toml [block] slot_max = 3.0`（含 BGA 下方，重新规划时会按它拒绝）。去掉要改 `metrics.json` 里的 `slot_max`，没有改，收件箱请主会话定 |
| RTE-6 走完第一个区域就给局部图 | `busroute` 的图、`views.*` | 部分 | 出图有；什么时候给是做法 |
| RTE-1 线序当迭代问题，位置、转向、出线层、可交换位当变量 | `placement.place --rot`、`busroute --sketch`、`planning.bga_plan` | 部分 | 线序分配脚本 `line_order.py` 已删（T1 搁置），换位要手写进 `swap.csv` 和走线文件 |
| RTE-2 按量预留补线空间、公式、块两头直线、长度窗口规则、长度表每次构建 | `busroute.tune`（`--tuning-budget`）、`routing.tune_sites`、`planning.*`、`rules.len_rules`、`route_table` | 覆盖 | `tune_sites` 的块两头直线、间距、摆幅、腿距、余量、各字节组的 spread 和地址窗口 R2 起读总线走线文件的 `TUNING`（和 busroute 补线的目标一致），最短直线读 `[route.table] straight` |
| RTE-7 圆弧蛇形、半径为腿距一半、按类别的腿距和摆幅、单侧、块内等高、不留矮尾弯 | `busroute.tune`、`planning.serp`、`spec_check`（`TUNING` 对 SPEC） | 覆盖 | 数值在走线文件 `TUNING`；`tune.DEFAULTS` 只是缺项时的退路 |
| RTE-15 按时序窗口等长，时钟也补，超窗列出 | `busroute.tune`（`ref` 组先补基准）、`busroute.metrics`、`route_table` | 覆盖 | |
| RTE-13 线序草图一步定四样（BGA 出线、线序、等长区域、其余总线），合格条件算出来 | `busroute --sketch`、`routing.fan_plan`、`planning.bga_fan`、`copper.bga_power`、`planning.plan` / `check` / `measure`、`placement.escape_check` | 部分 | 四样各有工具，没有一条命令出“一起合格”的结论；(2) 线序由确定性脚本分配没有通用工具（`line_order.py` 已删） |
| RTE-14 先算时序预算；按接口分组；数值写 SPEC | `length_groups.json` + `rules.len_rules`、`spec_check` | 部分 | 时序预算本身没有工具 |
| RTE-8 DRC 未连接为 0；`track_shape` 达标 | 驱动的 DRC、`analysis.track_shape`、`route_table` | 覆盖 | 正文点的 `scripts/track_shape.py` 已不存在（收件箱已有提议） |
| RTE-9 线形清单每处看图再下结论 | `analysis.track_shape`（逐处坐标）、`views.layer_view` | 部分 | 看图是人做 |
| RTE-10 1–2 mm 短线摆件对齐走一段直线 | `copper.power_ties`（直线或一个 45° 弯）、`track_shape`（crowded） | 部分 | 器件对齐由摆位数据决定，没有专门检查 |
| RTE-11 分叉只在焊盘中心；T/Y 分叉和过孔处 90° 改掉或解释 | DRC `corner_angle`、`busroute.checks`（VIATURN 列出） | 部分 | 只列出，不判失败 |
| RTE-3 局部电路逐根写坐标 | `busroute`（`routes_local*.py` 写坐标） | 覆盖 | |
| RTE-4 默认不用自动布线器；扇出、总线、零散线都由脚本 | `busroute`、`routing.fan_plan`、`planning.bga_fan`；例外 `third_party.*` | 覆盖 | |
| RTE-12 手改之后受影响的自动走线重跑 | 驱动的 `route`（剥掉全部组再按顺序重建）、`core.boardtext strip/orphans` | 覆盖 | |
| FIN-1 位号全留或全不留，放 Fab 层 | `finishing.silk` | 覆盖 | |
| FIN-2 功能标注；3D 渲染查遮挡 | `finishing.silk`（`silk.toml` 的标注）、驱动 `finish` 的渲染、`views.finish_view` | 部分 | 遮挡是人看图 |
| FIN-3 丝印字号由 Claude 定，以板厂下限为限 | `silk.toml [sizes]` | 部分 | 没有对 `design-rules.md` 丝印下限的检查 |
| FIN-4 收尾顺序（铺地 → 地过孔 → 丝印 → 泪滴 → 渲染）；带一致性的 DRC、金丝雀、甄别 kicad-happy | 驱动的 `finish`（`finishing.finish`、`teardrops`、`dru_canary`） | 覆盖 | 顺序一致；kicad-happy 在收尾不重跑，甄别是人做 |
| PROC-1 阶段顺序 | 驱动的步骤 | 部分 | 驱动的 `layout` 一步先按 `place.toml` 摆全部器件、再在副本上建线序草图；“草图在摆其余器件之前”只在设计过程里成立，重建时没有单独的草图一步 |
| PROC-2 每阶段可算的完成标准，不达标不进下一步 | 各步的表和退出码、`spec_check`（layout 前） | 部分 | 驱动不拿上一步的结论挡下一步（`spec_check` 除外） |
| PROC-3 两轮无改善就停；轮数上限 | `route_table`（`ROUND`）、`compare_runs` | 部分 | 上限的式子没有工具算 |
| PROC-7 先做小一档 | — | 未覆盖 | 做法类（演示板是工具的小一档） |
| PROC-8 SPEC 定稿，数据另存，可算判据 | `project.spec_check`、`templates/demo_board/SPEC.md` | 部分 | 判据逐条报是人做 |
| PROC-9 阶段之间交用户审查 | — | 未覆盖 | 交流类 |
| PROC-10 守不住当场说 | — | 未覆盖 | 交流类 |
| PROC-11 交付附审查清单 | `views.publish`（图） | 部分 | 清单手写 |
| PROC-12 提交前核对走线数和未连接数 | `route_table`、`finish` 的 DRC 报告 | 部分 | 没有提交前自动核对 |
| PROC-13 改脚本不改文件；手改后先问 | 板目录只放数据、`core.uuids`、写板前查锁文件 | 部分 | 没有手改检测（backlog T10） |
| PROC-14 图片只定性；数从文件算 | `views.*` 只出图，数都在表里 | 部分 | 甄别和抽查是人做 |
| PROC-4 每次构建同一张八组指标表，变差先解释 | `copper_table`、`route_table`、`place_check`、`compare_runs` | 部分 | 分在三张表；没有一张八组的整表，`compare_runs` 比数但不标“变差” |
| PROC-5 写新工具前先调研 | — | 未覆盖 | 做法类 |
| PROC-6 全量 ≤ 10 分钟、快速 ≤ 1 分钟；一次一个重进程 | 驱动（分步、计时、`core.heavy` 的锁和低优先级）、`busroute --fast` | 部分 | 一次一个重进程已覆盖；H743 的全量（`all`）超过 10 分钟（2026-11-24 的 `route` 一步 691 s，`finish` 约 500 s），工具只报时间 |
| PROC-15 原型转正重写、配基准、一条命令回归 | `Tools/KiCadDesignTools/`、`tests/`、`regress` | 覆盖 | 正文还写 `scripts/`（收件箱已有提议）；`plane_slots`、`copper_table`、`layout_probe`、`tune_sites`、`finishing.*`、`views.*` 没有自己的基准（`finishing.*` 和多数步骤由 `regress --board demo` 整板覆盖） |

合计（65 条）：覆盖 26、部分 28、未覆盖 9（RUL-12、RUL-5、RUL-10、LAY-9、LAY-4、PROC-7、PROC-9、PROC-10、PROC-5）、不一致 2（RUL-1、RTE-5）。
