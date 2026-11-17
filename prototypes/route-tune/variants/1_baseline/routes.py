"""PROTOTYPE (issue 21) variant 1_baseline: route first, then tune (the method of issue 15).

The routes are exactly those of 0_base. Then, net by net, the automatic filler looks for a straight
track OUTSIDE the rule areas (0.1016 wide, at least 2.5 mm long), nearest the middle of the net first,
and adds a serpentine at pitch 0.5 mm, single-sided where that is enough, aiming only at the
+-2.5 mm window: the clock first (towards longest - 2.5), then every net still below the window.
What does not fit is left and reported as "not fixed". Nothing is placed under the chips.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib"))
import board

DESCRIPTION = "基线：0_base 的走线不动，走完以后逐根在规则区外找直线段补蛇形（腿间距 0.5，只求满足 ±2.5 mm 窗口）。"

ROUTES, SWAP, WHY = board.base_routes("0_base")

PITCH = {"default": 0.5}                                    # SDCLK and data alike in the baseline
TUNING = [{"auto": "window", "outside_only": True, "min_run": 2.5, "amp_max": 2.0, "layers": ("L1", "L4", "L6")}]
