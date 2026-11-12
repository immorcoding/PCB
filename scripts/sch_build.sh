#!/bin/sh
# Regenerate, upgrade, ERC, netlist and PDF for a generated schematic.
#   sh scripts/sch_build.sh <project_dir> <out_dir>
set -e
K=/d/KiCad/bin/kicad-cli.exe
D=$1; N=$(basename "$D"); O=$2
/d/KiCad/bin/python.exe "$D/gen_sch.py"
$K sch upgrade "$D/$N.kicad_sch" >/dev/null
$K sch erc --severity-all -o "$O/erc.rpt" "$D/$N.kicad_sch" >/dev/null
grep -E "ERC messages|^\[|; (error|warning)" "$O/erc.rpt" || true
$K sch export netlist --format kicadsexpr -o "$O/$N.net" "$D/$N.kicad_sch" >/dev/null
$K sch export pdf -o "$O/$N.pdf" "$D/$N.kicad_sch" >/dev/null
