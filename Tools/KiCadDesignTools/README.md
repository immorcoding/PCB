# KiCadDesignTools

The workspace's own schematic and board tools. Everything runs from the repository root with KiCad's python
(`D:\KiCad\bin\python.exe`, not on PATH; `KICAD_BIN` overrides the folder, see `core/paths.py`):

    D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.<category>.<tool> <args>
    D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.build <board dir> <step> [--dry-run]
    D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.regress            (every benchmark, PROC-15)

No tool edits `sys.path`; board files (routes files, schematic pages) import
`from Tools.KiCadDesignTools.routing.busroute import ...`. Commands, usage and the known pitfalls are in
`docs/tools.md` (its paths still say `scripts/` until stage 4 of the consolidation); the rules the tools serve are in
`docs/shape/`.

Status (2026-11-24, branch `tools-consolidation`): stages 1-2 done: the generic tools moved here from `scripts/`, the
benchmarks carry their own fixtures, `build.py` reads `<board dir>/board.toml`. The H743 board folder still holds
its own mixed scripts (placement, copper report, finish, reports), which the driver calls; stage 3 splits them into
modules here plus data files.

| Category | Tool | Command | When | Rules | Benchmark |
|---|---|---|---|---|---|
| core | `paths` | (library) | KiCad, Edge and repository paths | | |
| core | `config` | `-m ...core.config <board dir>` | read and check `board.toml` (layer roles -> L1..Ln, KiCad names) | | |
| core | `heavy` | (library) | low priority on four cores, one heavy run at a time, KiCad lock files, pauses | | |
| (driver) | `build` | `-m ...build <board dir> <step>` | rules, sch, layout, copper, route, finish, checks, publish, all, compare | PROC-4, PROC-6 | `--dry-run` |
| rules | `dru_canary` | `-m ...rules.dru_canary <board>` | the rule file is loaded | RUL-2 | `tests/drc_tools` |
| rules | `dru_match` | `-m ...rules.dru_match <board> [--json]` | every rule matches something (one DRC per rule, slow) | RUL-2 | `tests/drc_tools` |
| rules | `drc_probe` | (library) | DRC on a copy with another rule file, report parsing, net lengths | | `tests/drc_tools` |
| rules | `len_rules` | `-m ...rules.len_rules <board> [--check]` | length-window rules from `length_groups.json` | RTE-2 | `tests/drc_tools` |
| rules | `impedance` | `-m ...rules.impedance` | trace impedance on the JLC06161H-3313E stackup (computed; the fab's calculator rules, RUL-3) | RUL-3 | `tests/impedance` |
| schematic | `kisch` | (library) | schematic generation (one sheet or pages) | RUL-6 | `tests/kisch` |
| schematic | `sch_build.sh` | `sh Tools/KiCadDesignTools/schematic/sch_build.sh <board dir> <out>` | generate, upgrade, ERC, netlist, PDF | RUL-6 | |
| schematic | `net2pcb` | `-m ...schematic.net2pcb <netlist> <board>` | netlist into the board | | |
| placement | `place_check` | `-m ...placement.place_check <board> [...]` | placement metrics | LAY-2, 5, 6, 8 | `tests/place_check` |
| placement | `escape_check` | `-m ...placement.escape_check <board> --ref U1 [...]` | ways out of fine-pitch parts | LAY-2 | `tests/place_check` |
| placement | `via_spots` | `-m ...placement.via_spots ...` | legal via spots (ignores footprint keep-outs) | | |
| copper | `cu_sketch` | `-m ...copper.cu_sketch check/apply/read/measure ...` | copper region sketch: check, write zones, read back, measures | PWR-3, 6, 7 | `tests/cu_sketch` |
| copper | `pour_islands` | `-m ...copper.pour_islands <board> <zone> ...` | pour pieces without a via or through-hole pad | PWR-6 | |
| routing | `busroute` | `-m ...routing.busroute.build <routes.py> [--fast] [--write-board] ...` | bundles, BGA fan-out, serpentines, metrics | RTE-2, 7, 13 | `tests/busroute` |
| finishing | `teardrops` | `-m ...finishing.teardrops <board>` | teardrops (last; earlier boards) | FIN | |
| finishing | `silk_refs` | `-m ...finishing.silk_refs ...` | reference designators on sparse boards | FIN | |
| views | `pcb_view`, `layer_view` | `-m ...views.<tool> ...` | pictures (qualitative only) | PROC-14 | |
| analysis | `track_shape` | `-m ...analysis.track_shape <board>` | track shapes DRC does not check | RTE-8 | `tests/track_shape` |
| analysis | `board_diff` | `-m ...analysis.board_diff <a> <b>` | two board files item by item (uuids aside, fills as areas) | | |
| analysis | `compare_runs` | `-m ...analysis.compare_runs <out A> <out B>` | two builds' reports number by number | | |
| third_party | `auto_tracks`, `auto_clean`, `auto_tidy` | `-m ...third_party.<tool> ...` | KiCadRoutingTools output (RTE-4: by exception) | RTE-4 | |

`...` = `Tools.KiCadDesignTools`. Several older tools read `sys.argv` when imported (script style); run them only as
commands.
