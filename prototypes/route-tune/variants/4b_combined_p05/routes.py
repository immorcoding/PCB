"""PROTOTYPE (issue 21) variant 4b_combined_p05: the SAME routes as 4_combined, every serpentine at pitch 0.5 mm.

Nothing is typed here: the bus description is variants/4_combined/plan4.py. Where a block does not fit at
0.5 the net is left short and the missing length is written into its WHY sentence.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "4_combined"))
import plan4

DESCRIPTION = "综合方案的对照：走线和 4_combined 完全相同，只把所有蛇形的腿间距从 0.3 改成 0.5。"

_r = plan4.make(data_pitch=0.5)
SWAP, ROUTES, TUNING = _r["SWAP"], _r["ROUTES"], _r["TUNING"]
PITCH = {"default": 0.5, "SDCLK": 0.5}
VIEWS = [("gapu", 16.5, 3.0, 25.5, 20.5, 90), ("southu", 7.5, 16.5, 23.0, 22.5, 90), ("under", 21.5, 13.5, 31.5, 23.0, 110)]
WHY = plan4.why(_r)
