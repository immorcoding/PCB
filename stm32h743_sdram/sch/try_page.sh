#!/bin/sh
# Build one or more pages alone in a scratch folder: generate, upgrade, ERC, netlist, PDF.
#   sh stm32h743_sdram/sch/try_page.sh <out dir> <page> [page ...]
# Nothing in the project folder is written. ERC errors about pins driven from other pages are expected.
set -e
K=/d/KiCad/bin/kicad-cli.exe
D=$(cd "$(dirname "$0")/.." && pwd); N=stm32h743_sdram
O=$1; shift
mkdir -p "$O"
cp "$D/$N.kicad_pro" "$D/fp-lib-table" "$O/"; cp -r "$D/h743.pretty" "$O/"
/d/KiCad/bin/python.exe "$D/gen_sch.py" "$@" --out "$O"
for F in "$O"/$N*.kicad_sch; do $K sch upgrade "$F" >/dev/null; done
$K sch erc --severity-all -o "$O/erc.rpt" "$O/$N.kicad_sch" >/dev/null
grep -E "ERC messages" "$O/erc.rpt"
grep -E "^\[" "$O/erc.rpt" | sort | uniq -c
$K sch export netlist --format kicadsexpr -o "$O/$N.net" "$O/$N.kicad_sch" >/dev/null
$K sch export pdf -o "$O/$N.pdf" "$O/$N.kicad_sch" >/dev/null
echo "netlist: $O/$N.net   pdf: $O/$N.pdf (page 1 is the root)"
