#!/bin/sh
# Build steps of the STM32H743 + SDRAM board. Each step can be run alone; reports go to <out dir>.
#   sh stm32h743_sdram/build.sh rules [out dir]     project file, rule fixture, canary and rule matching
#   sh stm32h743_sdram/build.sh sch [out dir]       schematic: generate, ERC, netlist checks, review
#   sh stm32h743_sdram/build.sh layout [out dir]    placement (place.py) and the stop-4 metrics table
# Later stages add their steps here (schematic, sketches, placement, copper, routing).
set -e
D=$(cd "$(dirname "$0")" && pwd); R=$(dirname "$D"); N=stm32h743_sdram
PY=/d/KiCad/bin/python.exe
STEP=${1:-rules}; O=${2:-$D/out/$STEP}
mkdir -p "$O"
quiet() { grep -v "image handler" || true; }

case "$STEP" in
rules)
  T0=$(date +%s)
  $PY "$D/make_project.py" 2>&1 | quiet
  # 1. every rule behaves as written (fixture board with the project's own rules and stackup)
  $PY "$D/rules_fixture.py" "$O" > "$O/fixture.log" 2>&1 && FX=0 || FX=$?
  head -1 "$O/rules_fixture.txt"
  grep "^FAIL" "$O/rules_fixture.txt" || true
  # 2. the real board: rule file loaded, rules that match nothing, length windows current
  $PY "$R/scripts/dru_canary.py" "$D/$N.kicad_pcb" 2>&1 | quiet | tee "$O/canary.txt"
  $PY "$R/scripts/dru_match.py" "$D/$N.kicad_pcb" --json "$O/dru_match.json" > "$O/dru_match.txt" 2>&1 && DM=0 || DM=$?
  tail -1 "$O/dru_match.txt"
  $PY "$R/scripts/len_rules.py" "$D/$N.kicad_pcb" 2>&1 | quiet | tee "$O/len_rules.txt"
  echo "rules step: $(( $(date +%s) - T0 )) s; fixture exit $FX, dru_match exit $DM (2 = the board has no objects yet)"
  exit $FX
  ;;
sch)
  # generate all pages, upgrade to the KiCad 10 format, ERC, netlist, PDF; then check the netlist
  T0=$(date +%s)
  sh "$R/scripts/sch_build.sh" "$D" "$O" 2>&1 | quiet > "$O/sch_build.log" || { cat "$O/sch_build.log"; exit 1; }
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
  $PY "$R/scripts/busroute/build.py" "$D/routes_sdram.py" --sketch --out "$D/out/sketch/rot0" > "$O/sketch_build.txt" 2>&1 && SB=0 || SB=$?
  echo "== SDRAM line-order sketch on the placed board (constraint 1)"
  grep -E "^\[间距\]|^结论" "$O/sketch_build.txt" || tail -3 "$O/sketch_build.txt"
  grep -E "^  ! " "$O/sketch_build.txt" || true
  echo "== placement (scripts/place_check.py)"
  $PY "$R/scripts/place_check.py" "$D/$N.kicad_pcb" --allow-under U201,U301 \
    --edge J101=R --edge J501=L --edge J601=T --edge J602=T --edge J701=B --edge J801=T --edge J802=R \
    --edge J803=T --edge J804=B --not-supply U101.5,U103.5,U104.5 --silk-refs "^(TP|JP|J80[234])" \
    --json "$O/place_check.json" > "$O/place_check.txt" 2>&1 && PC=0 || PC=$?
  quiet < "$O/place_check.txt" | grep -v "keep-out \["
  echo "== ways out of the fine-pitch parts (scripts/escape_check.py)"
  # on the sketch build's copy (it carries the SDRAM tracks): the two BGAs against the open board around the
  # sketch, the other fine-pitch parts 3 mm around themselves
  SK="$D/out/sketch/rot0/$N.kicad_pcb"
  $PY "$R/scripts/escape_check.py" "$SK" --ref U201 --ref U301 --window 27 25 66 51 \
    --json "$O/escape_bga.json" 2>&1 | quiet
  $PY "$R/scripts/escape_check.py" "$SK" --ref U501 --ref U601 --ref U701 --ref J701 --ref U401 \
    --json "$O/escape_parts.json" 2>&1 | quiet
  echo "== copper region sketch (scripts/cu_sketch.py check)"
  $PY "$R/scripts/cu_sketch.py" check "$D/copper.sketch" --board "$D/$N.kicad_pcb" 2>&1 | quiet | tail -40
  echo "== measured trial checks (layout_probe.py)"
  $PY "$D/layout_probe.py" --json "$O/layout_probe.json" 2>&1 | quiet
  echo "layout step: $(( $(date +%s) - T0 )) s; sketch build exit $SB, place_check exit $PC"
  ;;
*) echo "unknown step: $STEP"; exit 2 ;;
esac
