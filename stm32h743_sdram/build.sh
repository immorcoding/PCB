#!/bin/sh
# Build steps of the STM32H743 + SDRAM board. Each step can be run alone; reports go to <out dir>.
#   sh stm32h743_sdram/build.sh rules [out dir]     project file, rule fixture, canary and rule matching
#   sh stm32h743_sdram/build.sh sch [out dir]       schematic: generate, ERC, netlist checks, review
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
*) echo "unknown step: $STEP"; exit 2 ;;
esac
