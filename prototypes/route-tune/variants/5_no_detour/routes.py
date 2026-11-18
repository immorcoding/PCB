"""PROTOTYPE (issue 21) variant 5_no_detour: 4_combined without the deliberate detours.

The bus is described as bundles in plan5.py; PLAN.md has the numbers behind it. Data / DQM serpentines at
leg pitch 0.3 mm, SDCLK at 0.5 mm.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plan5

DESCRIPTION = "不绕远的综合方案：去掉 4_combined 的两个 U 形弯和时钟单独绕的那一圈，缺的长度全部用等高蛇形块补；蛇形集中在两个区（SDRAM 西半边底下、MCU 下方的表层），时钟单独一块在窄条里。"

_r = plan5.make()
SWAP, ROUTES, TUNING = _r["SWAP"], _r["ROUTES"], _r["TUNING"]
PITCH = {"default": 0.3, "SDCLK": 0.5}
VIEWS = [("zoneA", 21.5, 13.5, 31.5, 23.0, 110), ("zoneB", 12.5, 16.5, 25.5, 23.0, 110), ("clock", 16.0, 10.5, 25.0, 18.5, 110)]
WHY = plan5.why(_r)
