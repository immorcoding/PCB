# KiCadDesignTools

The workspace's own schematic and board tools. Everything runs from the repository root with KiCad's python
(`D:\KiCad\bin\python.exe`, not on PATH; `KICAD_BIN` overrides the folder, see `core/paths.py`):

    D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.<category>.<tool> <args>
    D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.build <board dir> <step> [--dry-run]
    D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.regress            (every benchmark, PROC-15)

No tool edits `sys.path`; board files (routes files, schematic pages) import
`from Tools.KiCadDesignTools.routing.busroute import ...`. busroute loads a routes file of a board folder as a module
of that folder's package (`<board>.<stem>`). Commands, usage and the known pitfalls are in
`docs/tools.md` (its paths still say `scripts/` until stage 4 of the consolidation); the rules the tools serve are in
`docs/shape/`.

Status (2026-11-24, branch `tools-consolidation`): stages 1-2 done: the generic tools moved here from `scripts/`, the
benchmarks carry their own fixtures, `build.py` reads `<board dir>/board.toml`. Stage 3 (batches A-G) moved the H743
board folder's scripts that the driver called here, their constants into its data files; the driver calls Tools
modules only (no `[scripts]` section any more).

| Category | Tool | Command | When | Rules | Benchmark |
|---|---|---|---|---|---|
| core | `paths` | (library) | KiCad, Edge and repository paths | | |
| core | `config` | `-m ...core.config <board dir>` | read and check `board.toml` (layer roles -> L1..Ln, KiCad names) | | |
| core | `heavy` | (library) | low priority on four cores, one heavy run at a time, KiCad lock files, pauses | | |
| core | `stackup` | (library) | a fab stackup from `data/stackups/<name>.toml` (`[board] stackup`): thickness, via heights | | |
| core | `uuids` | (library) | deterministic uuids (uuid5 of a stable key) for what the board writers add: the same build gives the same board file | | |
| core | `boardtext` | `-m ...core.boardtext <board dir> unfill/strip/orphans <board> [GROUP ...]` | text edits of a `.kicad_pcb`: copper rows of the layer table; drop the saved fills; remove what busroute groups wrote (`<board>.busroute.json`); remove copper no group owns | | |
| project | `make_project` | `-m ...project.make_project <board dir> [--new-pcb]` | `.kicad_pro` from the profile's template (`templates/<[board] template>/`: floors, widths, vias, Default / PWR / XTAL) plus the board's (`[project]`, `[netclasses]`, `[netclass_patterns]`), empty board with the stackup, derived footprints (`[[footprints.derived]]`), layer table; the template's rule file copied when the board has none, its rule names looked for in the board's | RUL-1, PROC-13 | |
| project | `spec_check` | `-m ...project.spec_check <board dir> [--profile <md>]` | SPEC.md's table 本板取值: every item of the profile's table 布局和走线的取值 filled (a value or 不适用), each 数据源 reference agreeing with its data file (`[board] profile`, `spec_table = false`: warnings only); the layout step runs it first | PROC-8 | `tests/spec_check` |
| rules | `fixture` | `-m ...rules.fixture <board dir> <out>` | every rule breaks and passes on a fixture board (cases: `<board dir>/rules_cases.py`) | RUL-2 | (it is one) |
| (driver) | `build` | `-m ...build <board dir> <step>` | rules, sch, layout, copper, route, finish, checks, publish, all, compare | PROC-4, PROC-6 | `--dry-run` |
| rules | `dru_canary` | `-m ...rules.dru_canary <board>` | the rule file is loaded | RUL-2 | `tests/drc_tools` |
| rules | `dru_match` | `-m ...rules.dru_match <board> [--json]` | every rule matches something (one DRC per rule, slow) | RUL-2 | `tests/drc_tools` |
| rules | `drc_probe` | (library) | DRC on a copy with another rule file, report parsing, net lengths | | `tests/drc_tools` |
| rules | `len_rules` | `-m ...rules.len_rules <board> [--check]` | length-window rules from `length_groups.json` | RTE-2 | `tests/drc_tools` |
| rules | `impedance` | `-m ...rules.impedance` | trace impedance on the JLC06161H-3313E stackup (computed; the fab's calculator rules, RUL-3) | RUL-3 | `tests/impedance` |
| schematic | `kisch` | (library) | schematic generation (one sheet or pages) | RUL-6 | `tests/kisch` |
| schematic | `sheet` | (library) | page-drawing helpers for the board's `sch/<page>.py` (stubs to power symbols or global labels, page-numbered references, grid units; `[schematic]` power_symbols, footprints, power_copies) | RUL-6, 8 | |
| schematic | `generate` | `-m ...schematic.generate <board dir> [page ...] [--out DIR]` | the multi-page schematic from `[schematic]` pages, project symbol library, sym-lib-table | PROC-13 | |
| schematic | `build` | `-m ...schematic.build <board dir> <out> [--page NAME ...]` | generate, upgrade, ERC, netlist, PDF; `--page`: some pages alone in `<out>`; a folder without board.toml runs its own `gen_sch.py` | RUL-6 | |
| schematic | `check` | `-m ...schematic.check <board dir> <netlist>` | netlist against the drawing's intent, the pin table (`[schematic.pin_table]`), the SDRAM byte lanes (`[schematic.swap]`) | RUL-6 | |
| schematic | `net2pcb` | `-m ...schematic.net2pcb <netlist> <board>` | netlist into the board | | |
| placement | `place` | `-m ...placement.place <board dir> [--pcb <copy>] [--rot <angle>]` | every part, outline, holes, rule areas and F.Cu no-pour areas from `<board dir>/place.toml`; parks unlisted parts below the board; `--pcb`/`--rot`: trials on a copy | LAY-1, PROC-13 | |
| placement | `layout_probe` | `-m ...placement.layout_probe <board dir> [--pcb <board>] [--json <out>]` | measured trials: rails against the copper sketch, crystals, switcher loops, bus lengths, LCD fan (board.toml `[probe]`) | LAY-2, 3 | |
| placement | `place_check` | `-m ...placement.place_check <board> [...]` | placement metrics | LAY-2, 5, 6, 8 | `tests/place_check` |
| placement | `escape_check` | `-m ...placement.escape_check <board> --ref U1 [...]` | ways out of fine-pitch parts | LAY-2 | `tests/place_check` |
| placement | `via_spots` | `-m ...placement.via_spots ...` | legal via spots (ignores footprint keep-outs) | | |
| copper | `cu_sketch` | `-m ...copper.cu_sketch check/apply/read/measure ...` | copper region sketch: check, write zones, read back, measures | PWR-3, 6, 7 | `tests/cu_sketch` |
| copper | `plane_slots` | `-m ...copper.plane_slots <board dir> <refilled board> <out> [--window NAME x0 y0 x1 y1] [--layers L5] [--stem S] [--part-b F]` | plane slots (merged antipads), cut-off own-net vias, the BGA blocks' feed necks (`[copper.slots]`) | U31 | |
| copper | `copper_table` | `-m ...copper.copper_table <board dir> <board> <out>` | the copper step's table: copper-class connectivity, feed vias per rail, ground vias, part B (`[copper.table]`) | PROC-4 | |
| copper | `power_ties`, `bga_power` | (library) | the power groups' site planners for the routes files: vias, ties, hops beside pads; BGA supply/ground fan-out and bottom decoupling (`[power]`, `[bga.<ref>]`, layer roles) | PWR | |
| copper | `pour_islands` | `-m ...copper.pour_islands <board> <zone> ...` | pour pieces without a via or through-hole pad | PWR-6 | |
| routing | `fan_plan` | (library) | a BGA block plan (`place.toml [fan]`) as busroute pieces for the routes files | | |
| routing | `tune_sites` | `-m ...routing.tune_sites <board dir> [board] [--spread 5] [--window 20] [--natural M] [--json F]` | room for serpentines beside each straight of the SDRAM nets (`[tune_sites]`) | RTE-2 | |
| routing | `busroute` | `-m ...routing.busroute.build <routes.py> [--fast] [--write-board] ...` | bundles, BGA fan-out, serpentines, metrics | RTE-2, 7, 13 | `tests/busroute` |
| planning | `bga_dump` | `-m ...planning.bga_dump <board dir> [board] [--out geo.json]` (KiCad's python) | a board as geo.json (pads, vias, tracks, zones, rule areas, keep-outs, stack, rule values) for the BGA planners | | |
| planning | `bga_fan` | `-m ...planning.bga_fan <board dir> --geo <geo.json> --out <dir> [--slot-max] [--time] [--only] [--staged] [--fixa]` (system python: numpy, scipy) | offline BGA block plan (the H743's `bga_fan.json`): supply / ground vias, bottom decoupling, MCU signal fan-out, one MILP on the ball lattice (`bga_block.toml [block]`, `[fan]`) | U31, LAY-2 | |
| planning | `bga_plan` | `-m ...planning.bga_plan <board dir> dump/plan/check ...` (system python: numpy, scipy, scikit-image) | offline whole-BGA model with the SDRAM line order (try/fanout-first; `check` needs `bga_check`, not in the repository) (`bga_block.toml [block]`, `[plan]`) | | |
| planning | `bga_grid` | (library) | exact clearance fields on a 0.025 mm grid, via sites, plane-slot chains, grid escapes (layers from `board.toml`) | | |
| planning | `measure` | `-m ...planning.measure <board dir> [board] [--nets N ... or --group G ...] [--json F] [--txt F]` | net lengths pad to pad (tracks, exact arcs, via heights from `core/stackup`), natural length, serpentine blocks, length per layer; byte lanes, clock sum, address lines against the window (`[schematic.swap]`, `[tune_sites]`, `[length]`, `length_groups.json`) | RTE-2 | `tests/planning` |
| planning | `check` | `-m ...planning.check <board dir> [board] [--nets ... or --group ...] [--free DATA.py] [--json F]` | exact clearance check of planned paths against the board's copper (pads as polygons, zone fills, holes; values from the `.kicad_pro` / `.kicad_dru` and the routes file's TUNING); the command checks the present routes; `free_area`: free copper per region at a clearance (raster) | RTE-2 | `tests/planning` |
| planning | `serp` | (library) | serpentine geometry of a plan (points, added length, height for a need; tune.py's RTE-2 humps) and the block rules: end straights, height window, axis-parallel, outside the rule areas, room above the humps | RTE-2 | `tests/planning` |
| planning | `plan` | `-m ...planning.plan <board dir> <plan data .py> [board] [--out DIR] [-v]` | a length plan on paper: hand waypoints and blocks of a plan data file (example `stm32h743_sdram/probes/plan50/plan_h743.py`), the rest of the bus copied from the board; plan.json / plan.txt / plan_summary.json / plan_summary.txt (`[plan]`) | RTE-2, 7 | `tests/planning` |
| finishing | `finish` | `-m ...finishing.finish <board dir> strip/fiducials/pours/clean/report/stitch/pieces/silk/teardrops <board> [<out> ...]` | the finish step's sub-steps: strip what the last run wrote (`<board>.finish.json`), fiducials (`[finish.fiducials]`), dispatch to the modules below | FIN-1..4 | |
| finishing | `pour` | (library; `finish pours/clean/report`) | inner ground pours, keep-outs over the BGA rule areas and serpentines, clean-up of narrow copper and small pieces, pour report (`[finish.pour]`, `[finish] pour_layers`) | FIN, PWR | |
| finishing | `stitch` | (library; `finish stitch/pieces`) | ground stitching vias: piece anchors, then greedy coverage (`[finish.stitch]`) | FIN-4 | |
| finishing | `silk` | (library; `finish silk`) | references to Fab, fine-pitch mask expansion, labels, glyphs, title blocks (`<board dir>/silk.toml`) | FIN-1..3 | |
| finishing | `teardrops` | `-m ...finishing.teardrops <board>` or `<board dir> <board>` | teardrops (last): every pad and via (earlier boards), or outside `[finish.teardrops] skip_boxes` and footprints with own keep-outs | FIN | |
| finishing | `silk_refs` | `-m ...finishing.silk_refs ...` | reference designators on sparse boards | FIN | |
| views | `pcb_view`, `layer_view` | `-m ...views.<tool> ...` | pictures (qualitative only) | PROC-14 | |
| views | `copper_view` | `-m ...views.copper_view <board dir> <board> <out> [L1 ...] [--scale] [--window ... --name] [--slots] [--via-labels]` | the filled copper per layer (`[copper_view]`) | PROC-14 | |
| views | `place_view` | `-m ...views.place_view <board dir> dump [board]` (KiCad's python), then `... draw [x0 y0 x1 y1 name]` (matplotlib) | pads and courtyards of the placement, whole board or a window, into `<board dir>/out/layout/` | PROC-14 | |
| views | `finish_view` | `-m ...views.finish_view <board dir> <board> <out>` (Edge) | the silkscreen over copper, both sides, close-ups of `[finish.view] close` | PROC-14 | |
| views | `sketch_view` | `-m ...views.sketch_view <board dir> <out>` (matplotlib) | the copper sketch per layer with the package bodies, rule areas and holes of `place.toml` | PROC-14 | |
| views | `publish` | `-m ...views.publish <board dir> [--rest 20] [--stage all/dump/svg/png] [--only ...]` (Edge) | release pictures with net names: every copper layer, outer layers with silkscreen, close-ups, layers stacked (`[publish]`) | PROC-14 | |
| analysis | `route_table` | `-m ...analysis.route_table <board dir> <board> <out>` (env ROUTE2_GROUPS) | the route step's table: the bus group's lengths, serpentines, vias, order, copper, escape; one row per routes file, gap crossings, pairs, placement (`[route.table]`) | PROC-4 | |
| analysis | `track_shape` | `-m ...analysis.track_shape <board>` | track shapes DRC does not check | RTE-8 | `tests/track_shape` |
| analysis | `board_diff` | `-m ...analysis.board_diff <a> <b>` | two board files item by item (uuids aside, fills as areas) | | |
| analysis | `compare_runs` | `-m ...analysis.compare_runs <out A> <out B>` | two builds' reports number by number | | |
| third_party | `auto_tracks`, `auto_clean`, `auto_tidy` | `-m ...third_party.<tool> ...` | KiCadRoutingTools output (RTE-4: by exception) | RTE-4 | |

`...` = `Tools.KiCadDesignTools`. Several older tools read `sys.argv` when imported (script style); run them only as
commands.
