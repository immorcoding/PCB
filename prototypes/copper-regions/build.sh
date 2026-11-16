#!/bin/sh
# PROTOTYPE (issue 16): rebuild everything. Run from this directory:   sh build.sh
#   out/0_base     placeholder board, no pours
#   out/a_sketch   variant A: sketch.txt -> sketch2zones.py
#   out/a_gap10    variant A with the gap between L3 blocks at 1.0 mm instead of 0.5
#   out/a_thermal  variant A with thermal relief on SMD pads too (rule smd_solid replaced)
#   out/a_solid    variant A with solid connection on through-hole pads too (rule tht_thermal replaced)
#   out/b_krt      variant B: KiCadRoutingTools route_planes.py (ground pours + spine split of L3)
set -e
HERE=$(cd "$(dirname "$0")" && pwd -W 2>/dev/null || pwd)
PY="D:/KiCad/bin/python.exe"; CLI="D:/KiCad/bin/kicad-cli.exe"
KRT="E:/Projects/claude_workspace/PCB/Tools/KiCadRoutingTools"      # lives in the main checkout only (gitignored)
cd "$HERE"

$PY make_board.py | head -2

variant() {   # $1 = dir name; copies the project files next to the board
    mkdir -p "out/$1"; cp out/0_base/h7cu.kicad_pro out/0_base/h7cu.kicad_dru "out/$1/"
}
finish() {    # refill with KiCad itself (PWR-6), DRC, numbers, pictures
    $PY ../../scripts/dru_canary.py "out/$1/h7cu.kicad_pcb" > "out/$1/canary.txt" 2>&1 || true
    $CLI pcb drc --refill-zones --save-board --severity-all --format json -o "out/$1/drc.json" "out/$1/h7cu.kicad_pcb" >/dev/null 2>&1 || true
    $PY measure.py "out/$1" > "out/$1/metrics.txt"; $PY render.py "out/$1" >/dev/null
    $PY ../../scripts/pour_islands.py "out/$1/h7cu.kicad_pcb" > "out/$1/pour_islands.txt" 2>&1 || true
    echo "== $1   (rules canary: $(tail -1 "out/$1/canary.txt"))"; cat "out/$1/metrics.txt"
}

variant a_sketch;  $PY sketch2zones.py out/0_base/h7cu.kicad_pcb sketch.txt out/a_sketch/h7cu.kicad_pcb
variant a_gap10;   sed 's/29\.7,/29.2,/g' sketch.txt > out/a_gap10/sketch_gap10.txt     # +3V3A pulled back so the blocks are 1.0 apart
$PY sketch2zones.py out/0_base/h7cu.kicad_pcb out/a_gap10/sketch_gap10.txt out/a_gap10/h7cu.kicad_pcb gap=1.0 | tail -1
variant a_thermal; $PY sketch2zones.py out/0_base/h7cu.kicad_pcb sketch.txt out/a_thermal/h7cu.kicad_pcb | tail -1
variant a_solid;   $PY sketch2zones.py out/0_base/h7cu.kicad_pcb sketch.txt out/a_solid/h7cu.kicad_pcb | tail -1
$PY pad_rules.py out/a_thermal/h7cu.kicad_dru thermal
$PY pad_rules.py out/a_solid/h7cu.kicad_dru solid

variant b_krt; rm -f out/b_krt/h7cu.kicad_pcb out/b_krt/tmp.kicad_pcb
cp out/0_base/h7cu.kicad_pro out/b_krt/tmp.kicad_pro; cp out/0_base/h7cu.kicad_dru out/b_krt/tmp.kicad_dru
( cd "$KRT" && export MSYS2_ARG_CONV_EXCL='*' &&
  .venv/Scripts/python.exe -X utf8 py_router/route_planes.py "$HERE/out/0_base/h7cu.kicad_pcb" "$HERE/out/b_krt/tmp.kicad_pcb" \
      --nets GND GND --plane-layers F.Cu B.Cu --zone-clearance 0.2 --min-thickness 0.3 \
      --escalation off --fab-tier standard --no-thermal-vias > "$HERE/out/b_krt/krt_outer.log" 2>&1 &&
  .venv/Scripts/python.exe -X utf8 py_router/route_planes.py "$HERE/out/b_krt/tmp.kicad_pcb" "$HERE/out/b_krt/h7cu.kicad_pcb" \
      --nets GND "+3V3|+5V|+3V3A" GND --plane-layers In1.Cu In2.Cu In4.Cu --min-thickness 0.15 \
      --escalation off --fab-tier standard --no-thermal-vias > "$HERE/out/b_krt/krt_inner.log" 2>&1 )
rm -f out/b_krt/tmp.kicad_pcb out/b_krt/tmp.kicad_pro out/b_krt/tmp.kicad_dru out/b_krt/tmp.kicad_prl
grep -E "Spine split|Creating zone|Closed .* soft joint" out/b_krt/krt_inner.log || true

for v in a_sketch a_gap10 a_thermal a_solid b_krt; do finish $v; done
$PY zones2sketch.py out/a_sketch/h7cu.kicad_pcb > out/a_sketch/sketch_readback.txt     # the sketch as read back from the board
$PY make_compare.py
