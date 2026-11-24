#!/bin/sh
# Thin wrapper (2026-11-24): the build steps of this board are run by the driver, which reads board.toml:
#   D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.build stm32h743_sdram <step> [--out DIR] [--skip-match] [--dry-run]
# This script keeps the old step names working:
#   sh stm32h743_sdram/build.sh rules|sch|layout|copper|route2|finish|finish-checks|publish [out root]
# route2 -> route, finish-checks -> checks; SKIP_DRU_MATCH=1 -> --skip-match; FINISH_BOARD=<copy> is read by the driver.
# The second argument is now the out ROOT (the driver writes <root>/<step folder>), not the step's folder.
# route1 has no driver step (route --upto power_bga builds the same groups; its table is the full route table).
set -e
D=$(cd "$(dirname "$0")" && pwd); R=$(dirname "$D")
STEP=${1:-rules}
case "$STEP" in
  route2) STEP=route ;;
  finish-checks) STEP=checks ;;
  route1) echo "route1: use the driver's route step with --upto power_bga"; exit 2 ;;
esac
OUT=${2:-}; [ $# -ge 2 ] && shift 2 || shift $#     # further arguments go to the driver (e.g. --dry-run)
set -- "$STEP" ${OUT:+--out "$OUT"} ${SKIP_DRU_MATCH:+--skip-match} "$@"
cd "$R"
exec /d/KiCad/bin/python.exe -m Tools.KiCadDesignTools.build stm32h743_sdram "$@"
