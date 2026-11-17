#!/bin/sh
# PROTOTYPE (issue 15): rebuild everything. Run from anywhere:   sh build.sh      (about 6 minutes)
#   5 mm package gap (the agreed layout). Serpentine keep-offs are hard limits: 0.35 mm of straight between a
#   bend and the first arc, 0.19 mm to other copper, 0.127 mm to a rule-area edge (see meander.py).
#   out/0_base                   nine nets rough-routed, no serpentines
#   out/1_A05_single             the agreed default: r 0.25, amplitude 0.5, one side, middle of the straight
#   out/2_A10_single             amplitude 1.0, one side (fewer, taller humps), last hump trimmed
#   out/2b_A10_single_even       amplitude up to 1.0, one side, all humps lowered to the same height
#   out/3_A05_double             amplitude 0.5 and up, both sides of the track, all humps of a chain equal
#   out/4_window_only_clk        only SDCLK is lengthened (double-sided), to the middle of the others: +-2.5 mm window met
#   out/5_A05_double_tight       like 3 but with the keep-offs of the first build (0.1 / 0.127 / 0.025): what they cost
#   8 mm package gap (EXTRA, not the agreed layout)
#   out/6_gap8_base              no serpentines
#   out/7_gap8_A05_single  8_gap8_A10_single  8b_gap8_A10_single_even  9_gap8_A05_double    the parameter sets on it
#   out/9m_gap8_A05_double_near_mcu  9s_gap8_A05_double_near_sdram     like 9, pushed to the MCU / SDRAM end
set -e
HERE=$(cd "$(dirname "$0")" && pwd -W 2>/dev/null || pwd)
PY="D:/KiCad/bin/python.exe"; CLI="D:/KiCad/bin/kicad-cli.exe"
export MSYS2_ARG_CONV_EXCL='*'          # Git Bash would rewrite net names that start with '/'
export PYTHONIOENCODING=utf-8
cd "$HERE"

if ls out/*/~*.lck >/dev/null 2>&1; then
    echo "KiCad has one of the boards under out/ open (~*.lck). Close it first; nothing was rebuilt."; exit 1
fi

finish() {    # $1 = variant dir: rules canary, refill + DRC, track shape, length table, pictures, result table
    $PY ../../scripts/dru_canary.py "out/$1/lentune.kicad_pcb" > "out/$1/canary.txt" 2>&1 || true
    $CLI pcb drc --refill-zones --save-board --severity-all --format json -o "out/$1/drc.json" "out/$1/lentune.kicad_pcb" >/dev/null 2>&1 || true
    $PY drc_summary.py "out/$1" > "out/$1/drc_summary.txt"
    $PY ../../scripts/track_shape.py "out/$1/lentune.kicad_pcb" > "out/$1/track_shape.txt" 2>&1 || true
    $PY pour_check.py "out/$1" > "out/$1/pour_check.txt" 2>&1 || true
    $PY geo_check.py "out/$1" > /dev/null
    $PY len_table.py "out/$1" > /dev/null
    if [ ! -f "out/$1/tune.json" ]; then $PY room.py "out/$1" > /dev/null; fi      # free room: base boards only
    $PY render.py "out/$1" > /dev/null
    echo "== $1"
    cat "out/$1/drc_summary.txt" "out/$1/pour_check.txt"
    $PY tune_table.py "out/$1"
}
tune() {      # $1 = source dir, $2 = variant dir, rest = meander.py options
    src=$1; dst=$2; shift 2
    rm -rf "out/$dst"
    $PY meander.py "out/$src" "out/$dst" "$@" > "out/$dst.log" 2>&1 || { cat "out/$dst.log"; exit 1; }
    mv "out/$dst.log" "out/$dst/meander.log"
    finish "$dst"
}

$PY make_board.py > /dev/null
$PY meander.py --window-only out/0_base        # window rule against SDCLK's natural length: must raise violations
finish 0_base
tune 0_base 1_A05_single
tune 0_base 2_A10_single --amp 1.0
tune 0_base 2b_A10_single_even --amp 1.0 --trim even
tune 0_base 3_A05_double --mode double
tune 0_base 4_window_only_clk --mode double --goal window
tune 0_base 5_A05_double_tight --mode double --end 0.1 --clr 0.127 --area-gap 0.025

$PY make_wide.py > /dev/null
$PY meander.py --window-only out/6_gap8_base
finish 6_gap8_base
tune 6_gap8_base 7_gap8_A05_single
tune 6_gap8_base 8_gap8_A10_single --amp 1.0
tune 6_gap8_base 8b_gap8_A10_single_even --amp 1.0 --trim even
tune 6_gap8_base 9_gap8_A05_double --mode double
tune 6_gap8_base 9m_gap8_A05_double_near_mcu --mode double --where mcu
tune 6_gap8_base 9s_gap8_A05_double_near_sdram --mode double --where sdram

$PY make_compare.py || true
$PY fill_readme.py || true
