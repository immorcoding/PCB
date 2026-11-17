"""PROTOTYPE (issue 21) variant 4_combined: routes and tuning planned together, every means used.

The bus is described as bundles in plan4.py (shared with 4b_combined_p05). Data / DQM serpentines at
pitch 0.3 mm. See PLAN.md for the numbers behind the plan.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plan4

DESCRIPTION = "综合方案：先算每根线缺多少，缺 10 mm 以上的靠绕远（L1 两束线各绕一个 U 形弯），缺几 mm 的在 SDRAM 底下（L6）放一块等高蛇形；数据线腿间距 0.3。"

_r = plan4.make(data_pitch=0.3)
SWAP, ROUTES, TUNING = _r["SWAP"], _r["ROUTES"], _r["TUNING"]
PITCH = {"default": 0.3, "SDCLK": 0.5}
VIEWS = [("gapu", 16.5, 3.0, 25.5, 20.5, 90), ("southu", 7.5, 16.5, 23.0, 22.5, 90), ("under", 21.5, 13.5, 31.5, 23.0, 110)]
WHY = plan4.why(_r)
