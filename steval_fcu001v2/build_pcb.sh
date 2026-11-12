#!/bin/sh
# Rebuild the board from the scripts, in the only order that works:
#   place.py   positions, outline, crystal keep-out, footprint attributes
#   route.py   hand-routed copper + the autorouter's nets (auto_tracks.json) + pours
#   silk_refs  reference designators
#   teardrops  last: route.py removes every non-rule-area zone, teardrops included
# then DRC with schematic parity. Run from the repository root:
#   sh steval_fcu001v2/build_pcb.sh <report dir>
set -e
PY=/d/KiCad/bin/python.exe
B=steval_fcu001v2/steval_fcu001v2.kicad_pcb
O=${1:-.}
q() { grep -v "image handler\|swig/python\|memory leak" || true; }
$PY steval_fcu001v2/place.py 2>&1 | q
$PY steval_fcu001v2/route.py 2>&1 | q
$PY scripts/silk_refs.py $B 2>&1 | q
$PY scripts/teardrops.py $B 2>&1 | q
/d/KiCad/bin/kicad-cli.exe pcb drc --refill-zones --severity-all --schematic-parity -o "$O/drc.rpt" $B >/dev/null 2>&1
grep "^\*\* Found" "$O/drc.rpt"
grep "^\[" "$O/drc.rpt" | sed 's/(.*//' | sort | uniq -c | sort -rn
