#!/bin/sh
# Build steps of the STM32H743 + SDRAM board. Each step can be run alone; reports go to <out dir>.
#   sh stm32h743_sdram/build.sh rules [out dir]     project file, rule fixture, canary and rule matching
#   sh stm32h743_sdram/build.sh sch [out dir]       schematic: generate, ERC, netlist checks, review
#   sh stm32h743_sdram/build.sh layout [out dir]    placement (place.py) and the stop-4 metrics table
#   sh stm32h743_sdram/build.sh copper [out dir]    stop 5: pours, power groups on the board and on the sketch copy
#   sh stm32h743_sdram/build.sh route1 [out dir]    stop 6 part A: SDRAM group on the board, power groups after it, table
#   sh stm32h743_sdram/build.sh route2 [out dir]    stop 7: route1, then the groups of ROUTE2_GROUPS on the board, table
#   sh stm32h743_sdram/build.sh finish [out dir]    stop 8: fiducials, inner ground pours and clean-up, ground stitching,
#                                                   silkscreen, teardrops, final checks
#   sh stm32h743_sdram/build.sh finish-checks       stop 8: rules that match nothing (dru_match, 30-40 min), once
#                                                   (after route2; FINISH_BOARD=<copy> runs it on a copy)
#   sh stm32h743_sdram/build.sh publish             release pictures with net names into stm32h743_sdram/publish/
#                                                   (publish.py; reads a copy of the board, about 15 minutes)
# Stage 1 of the Tools/ consolidation (2026-11-24): the generic tools moved from scripts/ to Tools/KiCadDesignTools/;
# Tools.KiCadDesignTools.build (board.toml) runs the same steps.
set -e
D=$(cd "$(dirname "$0")" && pwd); R=$(dirname "$D"); N=stm32h743_sdram
PY=/d/KiCad/bin/python.exe
STEP=${1:-rules}; O=${2:-$D/out/$STEP}
mkdir -p "$O"; O=$(cd "$O" && pwd)
# the tools are modules of Tools/KiCadDesignTools (python -m Tools.KiCadDesignTools.<category>.<tool>): run from the repository root
cd "$R"
quiet() { grep -v "image handler" || true; }
# route2: the groups written to the real board after route1's, one per line "<GROUP> <routes file>", built in this order.
# A routes file reads the board to build on from LOCAL_BOARD (route2 sets it to the real board). Add a group = add a line.
ROUTE2_GROUPS="
local routes_local.py
local_eth routes_local_eth.py
mcu_east routes_mcu_east.py
mcu_south routes_mcu_south.py
mcu_nw routes_mcu_nw.py
mcu_sw routes_mcu_sw.py
mcu_w routes_mcu_west.py
"

case "$STEP" in
rules)
  T0=$(date +%s)
  $PY "$D/make_project.py" 2>&1 | quiet
  # 1. every rule behaves as written (fixture board with the project's own rules and stackup)
  $PY "$D/rules_fixture.py" "$O" > "$O/fixture.log" 2>&1 && FX=0 || FX=$?
  head -1 "$O/rules_fixture.txt"
  grep "^FAIL" "$O/rules_fixture.txt" || true
  # 2. the real board: rule file loaded, rules that match nothing, length windows current
  $PY -m Tools.KiCadDesignTools.rules.dru_canary "$D/$N.kicad_pcb" 2>&1 | quiet | tee "$O/canary.txt"
  # SKIP_DRU_MATCH=1: leave out the rule matching on the real board (one DRC per rule, one at a time: about 8 minutes),
  # as route2 does; `build.sh finish-checks` runs it once at the end. The fixture still matches every rule on its board.
  if [ -n "$SKIP_DRU_MATCH" ]; then
    echo "dru_match skipped (SKIP_DRU_MATCH): run build.sh finish-checks once at the end" | tee "$O/dru_match.txt"; DM=-
  else
    $PY -m Tools.KiCadDesignTools.rules.dru_match "$D/$N.kicad_pcb" --json "$O/dru_match.json" > "$O/dru_match.txt" 2>&1 && DM=0 || DM=$?
    tail -1 "$O/dru_match.txt"
  fi
  $PY -m Tools.KiCadDesignTools.rules.len_rules "$D/$N.kicad_pcb" 2>&1 | quiet | tee "$O/len_rules.txt"
  echo "rules step: $(( $(date +%s) - T0 )) s; fixture exit $FX, dru_match exit $DM (2 = the board has no objects yet)"
  exit $FX
  ;;
sch)
  # generate all pages, upgrade to the KiCad 10 format, ERC, netlist, PDF; then check the netlist
  T0=$(date +%s)
  sh "$R/Tools/KiCadDesignTools/schematic/sch_build.sh" "$D" "$O" 2>&1 | quiet > "$O/sch_build.log" || { cat "$O/sch_build.log"; exit 1; }
  head -1 "$O/sch_build.log"; grep "ERC messages" "$O/sch_build.log"
  grep -E "^\[" "$O/erc.rpt" | sort | uniq -c || true
  $PY "$D/sch_check.py" "$O/$N.net" 2>&1 | quiet > "$O/sch_check.txt" && SC=0 || SC=$?
  grep -v "^$" "$O/sch_check.txt" | cut -c1-400
  # kicad-happy schematic review (RUL-9); findings are triaged by hand before they are reported
  KH="$HOME/.claude/plugins/marketplaces/kicad-happy/skills/kicad/scripts/analyze_schematic.py"
  if [ -f "$KH" ]; then
    ( cd "$O" && python "$KH" "$D/$N.kicad_sch" --text --stage schematic > "$O/kicad_happy_sch.txt" 2> "$O/kicad_happy_sch.err" ) || true
    echo "kicad-happy: $(grep -c "^  \[" "$O/kicad_happy_sch.txt") findings in $O/kicad_happy_sch.txt"
  else
    echo "kicad-happy analyzer not found: schematic review not run"
  fi
  echo "sch step: $(( $(date +%s) - T0 )) s; sch_check exit $SC"
  exit $SC
  ;;
layout)
  # stop 4: place every part (place.py), then the placement table: SDRAM sketch still valid (constraint 1),
  # placement metrics (LAY-2, 5, 6, 8), ways out of the fine-pitch parts (LAY-2), copper sketch (LAY-1),
  # measured trial checks (LAY-3). One KiCad process at a time; about 2 minutes.
  T0=$(date +%s)
  $PY "$D/place.py" 2>&1 | quiet
  $PY -m Tools.KiCadDesignTools.routing.busroute.build "$D/routes_sdram.py" --sketch --out "$D/out/sketch/rot0" > "$O/sketch_build.txt" 2>&1 && SB=0 || SB=$?
  echo "== SDRAM line-order sketch on the placed board (constraint 1)"
  grep -E "^\[间距\]|^结论" "$O/sketch_build.txt" || tail -3 "$O/sketch_build.txt"
  grep -E "^  ! " "$O/sketch_build.txt" || true
  echo "== placement (placement/place_check)"
  $PY -m Tools.KiCadDesignTools.placement.place_check "$D/$N.kicad_pcb" --allow-under U201,U301 \
    --edge J101=R --edge J501=L --edge J601=T --edge J602=T --edge J701=B --edge J801=T --edge J802=R \
    --edge J803=T --edge J804=B --not-supply U101.5,U103.5,U104.5 --silk-refs "^(TP|JP|J80[234])" \
    --json "$O/place_check.json" > "$O/place_check.txt" 2>&1 && PC=0 || PC=$?
  quiet < "$O/place_check.txt" | grep -v "keep-out \["
  echo "== ways out of the fine-pitch parts (placement/escape_check)"
  # on the sketch build's copy (it carries the SDRAM tracks): the two BGAs against the open board around the
  # sketch, the other fine-pitch parts 3 mm around themselves
  SK="$D/out/sketch/rot0/$N.kicad_pcb"
  $PY -m Tools.KiCadDesignTools.placement.escape_check "$SK" --ref U201 --ref U301 --window 27 25 66 51 \
    --json "$O/escape_bga.json" 2>&1 | quiet
  $PY -m Tools.KiCadDesignTools.placement.escape_check "$SK" --ref U501 --ref U601 --ref U701 --ref J701 --ref U401 \
    --json "$O/escape_parts.json" 2>&1 | quiet
  echo "== copper region sketch (copper/cu_sketch check)"
  $PY -m Tools.KiCadDesignTools.copper.cu_sketch check "$D/copper.sketch" --board "$D/$N.kicad_pcb" 2>&1 | quiet | tail -40
  echo "== measured trial checks (layout_probe.py)"
  $PY "$D/layout_probe.py" --json "$O/layout_probe.json" 2>&1 | quiet
  echo "layout step: $(( $(date +%s) - T0 )) s; sketch build exit $SB, place_check exit $PC"
  ;;
copper)
  # stop 5, power and copper: placement, the pours of copper.sketch, the power group (routes_power.py, part A:
  # vias and short ties outside the BGAs) and the BGA power group (routes_power_bga.py, part B: supply and ground
  # balls, bottom decoupling) on the real board, KiCad's own refill (PWR-6), then the copper table. Both groups
  # are built on the SDRAM line-order sketch copy too, to prove them legal next to the bus; that copy is refilled
  # and the plane slots under the BGAs (U31) are measured there. One KiCad process at a time.
  T0=$(date +%s)
  BRD="$D/$N.kicad_pcb"; SK="$D/out/sketch/rot0/$N.kicad_pcb"
  echo "== placement and pours"
  $PY "$D/copper_report.py" unfill "$BRD" 2>&1 | quiet                  # no stale fill may decide a via's net
  $PY "$D/place.py" 2>&1 | quiet
  $PY -m Tools.KiCadDesignTools.copper.cu_sketch check "$D/copper.sketch" --board "$BRD" 2>&1 | quiet > "$O/sketch_check.txt" || { cat "$O/sketch_check.txt"; exit 1; }
  head -1 "$O/sketch_check.txt"; grep -E "^\s+(ERROR|warning)" "$O/sketch_check.txt" || true
  $PY -m Tools.KiCadDesignTools.copper.cu_sketch apply "$D/copper.sketch" "$BRD" 2>&1 | quiet | grep -v "^warning: a ~" || true
  echo "== SDRAM line-order sketch on a copy of the board (the obstacles of the power group)"
  $PY "$D/copper_report.py" unfill "$SK" 2>&1 | quiet
  $PY -m Tools.KiCadDesignTools.routing.busroute.build "$D/routes_sdram.py" --sketch --out "$D/out/sketch/rot0" --no-refill --no-pictures > "$O/sketch_build.txt" 2>&1 && SB=0 || SB=$?
  grep -E "^\[间距\]|^结论" "$O/sketch_build.txt" || tail -3 "$O/sketch_build.txt"
  echo "== power group on the board"
  POWER_LOG="$O/power_sites.txt" $PY -m Tools.KiCadDesignTools.routing.busroute.build "$D/routes_power.py" --write-board --ignore-lock --no-refill --no-pictures \
    --out "$O/power" > "$O/power_build.txt" 2>&1 && PB=0 || PB=$?
  grep -E "^写入|^\[间距\]|^结论|^ERROR" "$O/power_build.txt" || tail -5 "$O/power_build.txt"
  grep -E "^(NO |feed .*SHORT)" "$O/power_sites.txt" || true
  echo "== BGA power group on the board (part B: supply and ground balls, bottom decoupling)"
  POWER_BGA_LOG="$O/power_bga_sites.txt" $PY -m Tools.KiCadDesignTools.routing.busroute.build "$D/routes_power_bga.py" --write-board --ignore-lock --no-refill --no-pictures \
    --out "$O/power_bga" > "$O/power_bga_build.txt" 2>&1 && PG=0 || PG=$?
  grep -E "^写入|^\[间距\]|^结论|^ERROR" "$O/power_bga_build.txt" || tail -5 "$O/power_bga_build.txt"
  grep -E "^(NO |LOST)" "$O/power_bga_sites.txt" | cut -c1-300 || true
  echo "== refill and save (kicad-cli), measure"
  /d/KiCad/bin/kicad-cli.exe pcb drc --refill-zones --save-board --severity-all --units mm --format json -o "$O/drc.json" "$BRD" > /dev/null 2>&1 || true
  $PY -m Tools.KiCadDesignTools.copper.cu_sketch measure "$BRD" --drc "$O/drc.json" --json "$O/measure.json" --skip-areas BGA_MCU,BGA_SDRAM > "$O/measure.txt" 2>&1 || true
  $PY -m Tools.KiCadDesignTools.copper.pour_islands "$BRD" "cu-whole:L1_GND" "cu-whole:L6_GND" 2>&1 | quiet > "$O/pour_islands.txt" || true
  grep -v " 0 without" "$O/pour_islands.txt" || true
  echo "== power groups on the line-order sketch copy (after routes_sdram.py), refill there, plane slots (U31)"
  POWER_BOARD="$SK" POWER_LOG="$O/sketch_power/power_sites.txt" $PY -m Tools.KiCadDesignTools.routing.busroute.build "$D/routes_power.py" --write-board \
    --no-refill --no-pictures --out "$O/sketch_power" > "$O/sketch_power_build.txt" 2>&1 && SP=0 || SP=$?
  grep -E "^\[间距\]|^结论|^ERROR" "$O/sketch_power_build.txt" || tail -5 "$O/sketch_power_build.txt"
  POWER_BOARD="$SK" POWER_BGA_LOG="$O/sketch_power_bga/power_bga_sites.txt" $PY -m Tools.KiCadDesignTools.routing.busroute.build "$D/routes_power_bga.py" --write-board \
    --no-refill --no-pictures --out "$O/sketch_power_bga" > "$O/sketch_power_bga_build.txt" 2>&1 && SG=0 || SG=$?
  grep -E "^\[间距\]|^结论|^ERROR" "$O/sketch_power_bga_build.txt" || tail -5 "$O/sketch_power_bga_build.txt"
  /d/KiCad/bin/kicad-cli.exe pcb drc --refill-zones --save-board --severity-all --units mm --format json -o "$O/sketch_drc.json" "$SK" > /dev/null 2>&1 || true
  $PY "$D/copper_report.py" slots "$SK" "$O" 2>&1 | quiet | tail -12
  $PY -m Tools.KiCadDesignTools.placement.escape_check "$SK" --ref U201 --ref U301 --window 27 25 66 51 --json "$O/escape_bga.json" 2>&1 | quiet > "$O/escape.txt"
  $PY -m Tools.KiCadDesignTools.placement.escape_check "$SK" --ref U501 --ref U601 --ref U701 --ref J701 --ref U401 --json "$O/escape_parts.json" 2>&1 | quiet >> "$O/escape.txt"
  echo "== escape check on the sketch copy (now | stop 4, out/layout/table.txt)"
  grep -E "^U[0-9]|^J[0-9]" "$O/escape.txt" | while read -r line; do
    ref=$(echo "$line" | cut -d' ' -f1); echo "$line"; grep -E "^$ref " "$D/out/layout/table.txt" | sed 's/^/  was: /'; done
  echo "== pictures of the filled layers (qualitative review only)"
  $PY "$D/copper_view.py" "$BRD" "$O" L1 L2 L3 L5 L6 2>&1 | quiet | tr '\n' ' '; echo
  # close-ups of the two BGAs on the sketch copy (it carries the SDRAM sketch's tracks and vias, as U31 is measured)
  $PY "$D/copper_view.py" "$SK" "$O" L1 L2 L3 L5 L6 --scale 40 --window 33 30 47 45 --name mcu 2>&1 | quiet | tr '\n' ' '; echo
  $PY "$D/copper_view.py" "$SK" "$O" L1 L2 L3 L5 L6 --scale 40 --window 51 28.5 63 45.5 --name sdram 2>&1 | quiet | tr '\n' ' '; echo
  # the longest L2 slot under the MCU marked, every via labelled with its net (for the reviewer)
  $PY "$D/copper_view.py" "$SK" "$O" L2 --scale 90 --window 36 36 46 45 --name slot_mcu --slots "$O/slots.json" --via-labels 2>&1 | quiet | tr '\n' ' '; echo
  mv -f "$O/L2_slot_mcu.png" "$O/slot_L2_mcu.png"
  $PY "$D/make_project.py" > /dev/null 2>&1                               # SaveBoard rewrote the project file: its source is this script
  echo "== copper table"
  COPPER_SECONDS="$(( $(date +%s) - T0 )) s" $PY "$D/copper_report.py" table "$BRD" "$O" 2>&1 | quiet && CT=0 || CT=$?
  echo "copper step: $(( $(date +%s) - T0 )) s; sketch build exit $SB, power build exit $PB / $PG (BGA), sketch-copy power build exit $SP / $SG (BGA), table exit $CT"
  ;;
route1|route2)
  # stop 6 part A, routing one: the real board rebuilt from scripts in this order: placement, pours, the SDRAM group
  # (routes_sdram.py), then the power group and the BGA power group against it (their vias see the bus as obstacles:
  # SDRAM_OBSTACLES=the board itself), KiCad's refill (PWR-6), DRC, plane slots over the whole bus region (U31),
  # escape check (U59), pictures, one metrics table (route1_report.py, PROC-4). One KiCad process at a time.
  # route2 (stop 7) does all of that and, before the refill, writes the groups of ROUTE2_GROUPS to the board (each
  # against everything before it); then the placement check of the layout step and route2_report.py's table.
  T0=$(date +%s)
  BRD="$D/$N.kicad_pcb"
  ls "$D"/~*.lck > /dev/null 2>&1 && { echo "KiCad has the project open (~*.lck): nothing written"; exit 2; }
  $PY "$D/make_project.py" 2>&1 | quiet | grep "layer table" || true    # the board's layer table follows make_project.LAYERS
  G2=""; [ "$STEP" = route2 ] && G2=$(echo "$ROUTE2_GROUPS" | awk 'NF { printf "%s ", $1 }')
  echo "== placement and pours (the groups are stripped first, then rebuilt in order)"
  $PY "$D/copper_report.py" unfill "$BRD" 2>&1 | quiet
  # the SDRAM group's serpentines need the other groups' copper as obstacles (tune.py, TUNE_OBSTACLES in
  # routes_sdram.py): a copy of the board as the last build left it, without the SDRAM group's own copper
  cp "$BRD" "$O/obstacles.kicad_pcb"; cp "$D/$N.busroute.json" "$O/obstacles.busroute.json"
  $PY "$D/copper_report.py" strip "$O/obstacles.kicad_pcb" sdram 2>&1 | quiet
  $PY "$D/copper_report.py" strip "$BRD" sdram power power_bga $G2 2>&1 | quiet
  # route2 strips every group: what copper is left belongs to no script (removed, listed)
  [ "$STEP" = route2 ] && $PY "$D/copper_report.py" orphans "$BRD" 2>&1 | quiet | tee "$O/orphans.txt"
  $PY "$D/place.py" 2>&1 | quiet
  $PY -m Tools.KiCadDesignTools.copper.cu_sketch check "$D/copper.sketch" --board "$BRD" 2>&1 | quiet > "$O/sketch_check.txt" || { cat "$O/sketch_check.txt"; exit 1; }
  $PY -m Tools.KiCadDesignTools.copper.cu_sketch apply "$D/copper.sketch" "$BRD" 2>&1 | quiet | grep -v "^warning: a ~" || true
  echo "== SDRAM group on the board"
  SDRAM_TUNE_OBSTACLES="$O/obstacles.kicad_pcb" \
  $PY -m Tools.KiCadDesignTools.routing.busroute.build "$D/routes_sdram.py" --write-board --no-refill --no-pictures --out "$O/sdram" > "$O/sdram_build.txt" 2>&1 && SB=0 || SB=$?
  grep -E "^写入|^\[间距\]|^结论|^ERROR|^  ! " "$O/sdram_build.txt" || tail -5 "$O/sdram_build.txt"
  echo "== power group on the board (after the bus)"
  SDRAM_OBSTACLES="$BRD" POWER_LOG="$O/power_sites.txt" $PY -m Tools.KiCadDesignTools.routing.busroute.build "$D/routes_power.py" --write-board --no-refill --no-pictures \
    --out "$O/power" > "$O/power_build.txt" 2>&1 && PB=0 || PB=$?
  grep -E "^写入|^\[间距\]|^结论|^ERROR|^  ! [A-Z]" "$O/power_build.txt" | grep -v "! DRC     unconnected" || tail -5 "$O/power_build.txt"
  grep -E "^(NO |feed .*SHORT)" "$O/power_sites.txt" || true
  echo "== BGA power group on the board (after the bus)"
  SDRAM_OBSTACLES="$BRD" POWER_BGA_LOG="$O/power_bga_sites.txt" $PY -m Tools.KiCadDesignTools.routing.busroute.build "$D/routes_power_bga.py" --write-board --no-refill --no-pictures \
    --out "$O/power_bga" > "$O/power_bga_build.txt" 2>&1 && PG=0 || PG=$?
  grep -E "^写入|^\[间距\]|^结论|^ERROR|^  ! [A-Z]" "$O/power_bga_build.txt" | grep -v "! DRC     unconnected" || tail -5 "$O/power_bga_build.txt"
  grep -E "^(NO |LOST)" "$O/power_bga_sites.txt" | cut -c1-300 || true
  if [ "$STEP" = route2 ]; then
    echo "$ROUTE2_GROUPS" | while read -r G F; do
      [ -n "$G" ] || continue
      echo "== group $G ($F) on the board"
      LOCAL_BOARD="$BRD" $PY -m Tools.KiCadDesignTools.routing.busroute.build "$D/$F" --write-board --no-refill --no-pictures --out "$O/$G" > "$O/${G}_build.txt" 2>&1 || true
      grep -E "^写入|^结论|^ERROR|^  ! [A-Z]" "$O/${G}_build.txt" | grep -v "! DRC     unconnected" || tail -5 "$O/${G}_build.txt"
    done
  fi
  echo "== refill and save (kicad-cli), DRC, measure"
  /d/KiCad/bin/kicad-cli.exe pcb drc --refill-zones --save-board --severity-all --units mm --format json -o "$O/drc.json" "$BRD" > /dev/null 2>&1 || true
  $PY "$D/make_project.py" > /dev/null 2>&1                               # SaveBoard rewrote the project file: its source is this script
  $PY -m Tools.KiCadDesignTools.copper.cu_sketch measure "$BRD" --drc "$O/drc.json" --json "$O/measure.json" --skip-areas BGA_MCU,BGA_SDRAM > "$O/measure.txt" 2>&1 || true
  # plane slots over the whole bus region (both BGAs, the west layer changes, the strip between the packages)
  $PY "$D/copper_report.py" slots "$BRD" "$O" --window BUS 27 25 66 51 --part-b "$O/power_bga_sites.json" 2>&1 | quiet | tail -8
  # the power plane L5 over the whole board: the antipad chains inside each of the five blocks (slots_l5.json / .txt)
  $PY "$D/copper_report.py" slots "$BRD" "$O" --window BOARD -1 -1 86 76 --layers L5 --stem slots_l5 --part-b "$O/power_bga_sites.json" 2>&1 | quiet | grep "每块最长" || true
  # ground: L2 is the only plane; every L1 / L6 ground pour piece must hold a via or a through-hole pad of GND
  $PY -m Tools.KiCadDesignTools.copper.pour_islands "$BRD" "cu-whole:L1_GND" "cu-whole:L6_GND" 2>&1 | quiet > "$O/pour_islands.txt" || true
  cat "$O/pour_islands.txt"
  $PY -m Tools.KiCadDesignTools.placement.escape_check "$BRD" --ref U201 --ref U301 --window 27 25 66 51 --json "$O/escape_bga.json" 2>&1 | quiet > "$O/escape.txt"
  $PY -m Tools.KiCadDesignTools.rules.dru_canary "$BRD" 2>&1 | quiet > "$O/canary.txt" || true
  # SKIP_DRU_MATCH=1: leave out the rule matching (one DRC per rule, one at a time: 7-8 minutes); run it once at the end
  # with `build.sh finish-checks` (2026-11-23: the PC hard-reset under parallel load, so heavy steps are kept few)
  if [ -n "$SKIP_DRU_MATCH" ]; then
    echo "dru_match skipped (SKIP_DRU_MATCH): run build.sh finish-checks once at the end" > "$O/dru_match.txt"
  else
    $PY -m Tools.KiCadDesignTools.rules.dru_match "$BRD" --json "$O/dru_match.json" > "$O/dru_match.txt" 2>&1 || true
  fi
  echo "== pictures (qualitative review only)"
  $PY "$D/copper_view.py" "$BRD" "$O" L1 L3 L4 L6 --scale 40 --window 29 26 66 50 --name bus 2>&1 | quiet | tr '\n' ' '; echo
  $PY "$D/copper_view.py" "$BRD" "$O" L1 L2 L3 L4 L6 --scale 90 --window 36 37 46 47 --name mcu_south --via-labels 2>&1 | quiet | tr '\n' ' '; echo
  $PY "$D/copper_view.py" "$BRD" "$O" L1 L3 L6 --scale 80 --window 51 28.5 63 45.5 --name sdram --via-labels 2>&1 | quiet | tr '\n' ' '; echo
  # the two planes (L2 ground, L5 the power blocks) over the bus region, and L5 over the whole board with its longest slot
  $PY "$D/copper_view.py" "$BRD" "$O" L2 L5 --scale 40 --window 27 25 66 51 --name planes --slots "$O/slots.json" 2>&1 | quiet | tr '\n' ' '; echo
  $PY "$D/copper_view.py" "$BRD" "$O" L5 --scale 14 --name board --slots "$O/slots_l5.json" 2>&1 | quiet | tr '\n' ' '; echo
  if [ "$STEP" = route2 ]; then
    # the Ethernet block (L1 / L4 / L6) and the areas of the stop-7 part moves, from the refilled board
    $PY "$D/copper_view.py" "$BRD" "$O" L1 L4 L6 --scale 45 --window 0 38 32 63 --name phy --via-labels 2>&1 | quiet | tr '\n' ' '; echo
    $PY "$D/copper_view.py" "$BRD" "$O" L1 L6 --scale 45 --window 60 8 82 28 --name can 2>&1 | quiet | tr '\n' ' '; echo
    $PY "$D/copper_view.py" "$BRD" "$O" L1 L6 --scale 60 --window 61 36 70 47 --name fb5v --via-labels 2>&1 | quiet | tr '\n' ' '; echo
    $PY "$D/copper_view.py" "$BRD" "$O" L1 --scale 45 --window 11 58 36 73 --name user_lcd 2>&1 | quiet | tr '\n' ' '; echo
    echo "== placement (placement/place_check, as in the layout step)"
    $PY -m Tools.KiCadDesignTools.placement.place_check "$BRD" --allow-under U201,U301 \
      --edge J101=R --edge J501=L --edge J601=T --edge J602=T --edge J701=B --edge J801=T --edge J802=R \
      --edge J803=T --edge J804=B --not-supply U101.5,U103.5,U104.5 --silk-refs "^(TP|JP|J80[234])" \
      --json "$O/place_check.json" > "$O/place_check.txt" 2>&1 && PC=0 || PC=$?
    grep -E "^\[(outside|overlap|keepout|under)\]" "$O/place_check.txt" || true
    echo "== route2 table"
    ROUTE2_GROUPS="$ROUTE2_GROUPS" ROUTE2_SECONDS="$(( $(date +%s) - T0 )) s" $PY "$D/route2_report.py" "$BRD" "$O" > "$O/table.log" 2>&1 && RT=0 || RT=$?
    quiet < "$O/table.log" | sed -n '1,/^== SDRAM/p'
    echo "route2 step: $(( $(date +%s) - T0 )) s; sdram build exit $SB, power build exit $PB / $PG (BGA), place_check exit $PC, table exit $RT"
  else
    echo "== route1 table"
    ROUTE1_SECONDS="$(( $(date +%s) - T0 )) s" $PY "$D/route1_report.py" "$BRD" "$O" > "$O/table.log" 2>&1 && RT=0 || RT=$?
    quiet < "$O/table.log"
    echo "route1 step: $(( $(date +%s) - T0 )) s; sdram build exit $SB, power build exit $PB / $PG (BGA), table exit $RT"
  fi
  ;;
finish)
  # stop 8, finishing (FIN-1 to FIN-4), on the board route2 left: strip what the last finish wrote, fiducials and their
  # keep-outs, ground pours on L3 / L4 with their keep-outs and the clean-up of narrow copper and small pieces on every
  # pour layer (finish_pour.py, user 2026-11-24), refill, ground stitching vias (text write), refill, silkscreen (references to Fab, fine-pitch mask
  # expansion, labels, glyphs, title), teardrops outside the BGA areas (refill and save), then the final checks:
  # DRC with schematic parity, canary, rules that match nothing, pour pieces, pictures. Repeatable; route2 removes
  # the stitching vias again (orphans) and keeps the rest, so run finish after every route2. finish.py has the details.
  T0=$(date +%s)
  BRD="${FINISH_BOARD:-$D/$N.kicad_pcb}"                                 # FINISH_BOARD: a copy to try it on
  # the lock files of the open project only stop a run on the real board (a copy in another folder is safe to write)
  [ -z "$FINISH_BOARD" ] && ls "$D"/~*.lck > /dev/null 2>&1 && { echo "KiCad has the project open (~*.lck): nothing written"; exit 2; }
  CLI=/d/KiCad/bin/kicad-cli.exe
  q2() { sed 's/swig\/python detected a memory leak[^.]*found\.//g' | grep -v "image handler" | grep . || true; }
  # one heavy process at a time with a pause after each (the PC hard-reset under full load, 2026-11-23); run the whole
  # step at low priority on four cores: cmd //c "start /low /affinity F /wait /b sh stm32h743_sdram/build.sh finish"
  rest() { sleep 20; }
  refill() { $CLI pcb drc --refill-zones --save-board --severity-all --units mm --format json -o "$1" "$BRD" > /dev/null 2>&1 || true; rest; }
  rm -f "$O"/clean_shape.txt "$O"/clean_anchor.txt
  echo "== strip, fiducials"
  $PY "$D/copper_report.py" unfill "$BRD" 2>&1 | q2
  $PY "$D/finish.py" strip "$BRD" 2>&1 | q2
  # the fiducials stay first: their keep-outs must be on the board before the pours, the vias and the silkscreen
  $PY "$D/finish.py" fiducials "$BRD" 2>&1 | q2
  echo "== ground pours on L3 / L4, pour keep-outs, clean-up of narrow copper and small pieces (finish_pour.py)"
  $PY "$D/finish.py" pours "$BRD" "$O" 2>&1 | q2
  refill "$O/drc_pour.json"
  # narrow spikes / slivers / long necks and small pieces without a pad: keep-outs, refill; a second pass for what the
  # first one's cuts left (each pass only adds keep-outs)
  for P in 1 2; do
    $PY "$D/finish.py" clean "$BRD" "$O" shape > "$O/clean.log" 2>&1 && CL=0 || CL=$?; q2 < "$O/clean.log"
    [ "$CL" = 10 ] || break
    refill "$O/drc_clean$P.json"
  done
  echo "== ground stitching vias"
  $PY "$D/finish.py" pieces "$BRD" "$O" before 2>&1 | q2
  $PY "$D/finish.py" stitch "$BRD" "$O" 2>&1 | q2
  refill "$O/drc_stitch.json"
  $PY "$D/finish.py" stitch "$BRD" "$O" --pieces 2>&1 | q2             # the pieces the first pass's vias made or left on one via
  refill "$O/drc_stitch2.json"
  # an inner piece the stitching could not hold (no legal site) goes by a keep-out
  $PY "$D/finish.py" clean "$BRD" "$O" anchor > "$O/clean.log" 2>&1 && CL=0 || CL=$?; q2 < "$O/clean.log"
  [ "$CL" = 10 ] && refill "$O/drc_anchor.json"
  $PY "$D/finish.py" pieces "$BRD" "$O" after 2>&1 | q2
  $PY -m Tools.KiCadDesignTools.copper.pour_islands "$BRD" "cu-whole:L1_GND" "cu-whole:L6_GND" 2>&1 | q2 > "$O/pour_islands.txt" || true
  cat "$O/pour_islands.txt"
  $PY "$D/finish.py" report "$BRD" "$O" after 2>&1 | q2
  echo "== silkscreen"
  $PY "$D/copper_report.py" unfill "$BRD" 2>&1 | q2
  $PY "$D/finish.py" silk "$BRD" "$O" 2>&1 | q2
  echo "== teardrops"
  $PY "$D/finish.py" teardrops "$BRD" 2>&1 | q2
  rest
  [ -z "$FINISH_BOARD" ] && $PY "$D/make_project.py" > /dev/null 2>&1   # SaveBoard may have rewritten the project file
  echo "== final DRC (schematic parity), canary, rules matching nothing"
  $CLI pcb drc --refill-zones --save-board --severity-all --schematic-parity --units mm --format json -o "$O/drc.json" "$BRD" > /dev/null 2>&1 || true
  rest
  [ -z "$FINISH_BOARD" ] && $PY "$D/make_project.py" > /dev/null 2>&1
  python -c "
import json, collections, sys
d = json.load(open(sys.argv[1]))
c = collections.Counter(v['type'] for v in d['violations'])
p = collections.Counter(v['type'] for v in d.get('schematic_parity', []))
print('DRC by type:', ', '.join('%s %d' % kv for kv in sorted(c.items())) or 'none')
print('unconnected:', len(d['unconnected_items']))
print('schematic parity by type:', ', '.join('%s %d' % kv for kv in sorted(p.items())) or 'none')" "$(cygpath -m "$O/drc.json")" | tee "$O/drc_summary.txt"
  $PY -m Tools.KiCadDesignTools.rules.dru_canary "$BRD" 2>&1 | quiet | tee "$O/canary.txt"
  # the planes after the new ground vias: no plane-net via cut off, the L5 feed necks of the BGA blocks, longest slots
  $PY "$D/copper_report.py" slots "$BRD" "$O" --window BOARD -1 -1 86 76 --stem slots_board --part-b "$D/out/route2/power_bga_sites.json" 2>&1 \
    | quiet | grep -E "切断|L5 \+3V3_|每层最长" || true
  # rules/dru_match (one DRC per rule, about 30-40 minutes now that it runs one at a time) is not run here:
  # `build.sh finish-checks` runs it once, when asked
  echo "== pictures"
  # 3D: basic quality (no ray tracing: a full-load run reset the PC), 1600 px, 3 minutes at most each; the 2D
  # pictures below are the fallback
  for S in top bottom; do
    timeout 180 $CLI pcb render --side $S --width 1600 --height 1410 --quality basic --background opaque -o "$O/render_$S.png" "$BRD" > /dev/null 2>&1 || echo "render $S failed or took over 3 minutes"
    rest
  done
  $PY "$D/finish_view.py" "$BRD" "$O" 2>&1 | q2
  echo "finish step: $(( $(date +%s) - T0 )) s"
  ;;
finish-checks)
  # the slow check of the finished board, run once when asked: every rule of the rule file matches at least one object
  # (RUL-2; rules/dru_match, one DRC per rule, one at a time: about 30-40 minutes on the routed board). Run it at
  # low priority on four cores like finish.
  T0=$(date +%s)
  O=${2:-$D/out/finish}
  $PY -m Tools.KiCadDesignTools.rules.dru_match "$D/$N.kicad_pcb" --json "$O/dru_match.json" > "$O/dru_match.txt" 2>&1 || true
  tail -1 "$O/dru_match.txt"
  echo "finish-checks step: $(( $(date +%s) - T0 )) s"
  ;;
publish)
  # release pictures (per layer, close-ups, layers stacked) with net names; publish.py copies the board to
  # out/publish_work/ and runs every heavy command itself, one at a time, at low priority on four cores, 20 s apart
  T0=$(date +%s)
  $PY "$D/publish.py" --rest 20 2>&1 | quiet
  echo "publish step: $(( $(date +%s) - T0 )) s"
  ;;
*) echo "unknown step: $STEP"; exit 2 ;;
esac
