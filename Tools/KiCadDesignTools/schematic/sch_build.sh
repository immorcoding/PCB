#!/bin/sh
# Regenerate, upgrade, ERC, netlist and PDF for a generated schematic.
#   sh Tools/KiCadDesignTools/schematic/sch_build.sh <project_dir> <out_dir>      (from the repository root)
# Works for a single sheet (kisch.Sch) and for a multi-page design
# (kisch.Design: root <name>.kicad_sch plus one <name>_<page>.kicad_sch per page).
# ERC, netlist and PDF are taken from the root and cover every page.
set -e
K=/d/KiCad/bin/kicad-cli.exe
mkdir -p "$2"
D=$(cd "$1" && pwd); N=$(basename "$D"); O=$(cd "$2" && pwd)
# gen_sch.py runs as a module of its board folder from the repository root (it imports Tools.KiCadDesignTools.*)
R=$(cd "$(dirname "$0")/../../.." && pwd)
MOD=$(echo "${D#"$R"/}" | tr / .).gen_sch
( cd "$R" && /d/KiCad/bin/python.exe -m "$MOD" )
# `sch upgrade` converts only the file it is given, so each page is upgraded too.
# The page list comes from the sheet symbols of the root.
$K sch upgrade "$D/$N.kicad_sch" >/dev/null
PAGES=$(sed -n 's/.*(property "Sheetfile" "\([^"]*\)".*/\1/p' "$D/$N.kicad_sch")
for P in $PAGES; do
  $K sch upgrade "$D/$P" >/dev/null
done
# A page file the root no longer points to is a leftover from a renamed or removed page.
if [ -n "$PAGES" ]; then
  for F in "$D/${N}_"*.kicad_sch; do
    [ -e "$F" ] || continue
    echo "$PAGES" | grep -qxF "$(basename "$F")" || echo "WARNING: $F is not a page of $N.kicad_sch (stale?)"
  done
fi
$K sch erc --severity-all -o "$O/erc.rpt" "$D/$N.kicad_sch" >/dev/null
grep -E "ERC messages|^\[|; (error|warning)" "$O/erc.rpt" || true
$K sch export netlist --format kicadsexpr -o "$O/$N.net" "$D/$N.kicad_sch" >/dev/null
$K sch export pdf -o "$O/$N.pdf" "$D/$N.kicad_sch" >/dev/null
