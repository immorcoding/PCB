# 收件箱：tools-consolidation

- 2026-11-24 · process · proposed · PROC-15 正文的“重写进 `scripts/`”改成“重写进 `Tools/KiCadDesignTools/<类别>/`，从仓库根以 `python -m Tools.KiCadDesignTools.<类别>.<工具>` 运行，任何文件都不改 `sys.path`；基准放 `Tools/KiCadDesignTools/tests/<工具>/check.py`，带自己的夹具，不从板目录取文件；`python -m Tools.KiCadDesignTools.regress` 一条命令跑完”。
- 2026-11-24 · power-copper · proposed · PWR-6 正文里的 `scripts/` 路径改成 `Tools/KiCadDesignTools/copper/`（`pour_islands.py`、`cu_sketch.py`）。
- 2026-11-24 · rules-and-schematic · proposed · RUL-2 正文里的 `scripts/dru_canary.py` 改成 `Tools/KiCadDesignTools/rules/dru_canary.py`（规则匹配 `rules/dru_match.py`）。
- 2026-11-24 · routing · proposed · RTE-8 正文里的 `scripts/track_shape.py` 改成 `Tools/KiCadDesignTools/analysis/track_shape.py`。
- 2026-11-24 · process · proposed · 每块板的构建步骤由 `python -m Tools.KiCadDesignTools.build <板目录> <步骤>` 跑，板目录只放数据（`board.toml` 等）；新板不再抄一份 `build.sh`。是否写成规则（放 PROC 哪一条）请主会话定。
- 2026-11-24 · process · cite · PROC-15 · 起作用：工具从 `scripts/` 搬进 `Tools/KiCadDesignTools/` 后 7 个基准全过；busroute、track_shape 两个基准原来运行时从 `stm32h743_sdram/` 取空板叠层、工程文件、规则文件和 0.33 mm 焊盘的 BGA-90 封装，冻结进 `tests/busroute/fixture/`（`tests/track_shape/fixture/`）后预期数字一个没改就通过。
- 2026-11-24 · process · cite · PROC-13 · 起作用：基线重建（现有脚本、未改动）和提交的板文件相比只有对象的 uuid 不同（缝合过孔、板上图形、光学定位点及其禁布区、place.py 的四个规则区），其余逐项相同，所以脚本仍是这块板的来源。
- 2026-11-24 · process · friction · PROC-4 · `build.sh route2` 的指标表在收尾过的板上出不来：route2 不剥收尾的 `FIN_` 区，`route1_report.py` 读规则区时遇到 `FIN_TUNE_L1_ETH_TX_N`（不是轴对齐矩形）报错，表这一步退出 1，`out/route2/table.txt` 停在旧的一版；基线和搬移后的构建都是这样（不是搬移引起的）。
- 2026-11-24 · rules-and-schematic · cite · RUL-1 · `board.toml` 的 `template` 仍写 `common`：规格档 C 没有自己的模板，第 5 阶段补 `templates/C-bga-065/`。
- 2026-11-24 · process · cite · PROC-13 · 起作用：板目录只剩数据（board.toml、place.toml、silk.toml、rules_cases.py、bga_block.toml、routes_*.py、sch/<页>.py），逻辑全部在 `Tools/KiCadDesignTools/`；所有写板的程序改成确定的 uuid（uuid5）后，连续两次全量构建的板文件逐字节相同，提交的板文件只换了一次 uuid（项的顺序随 uuid 变）。
- 2026-11-24 · process · friction · PROC-14 · 拆分时发现几处原有缺陷，没有当场修（结果不变是前提）：layout_probe 的电源块层仍按 L3 判（应为 L5）、铜皮表在当前电源组输出上会崩溃（两处）、bga_fan 的结果随 Python 字符串哈希种子变、bga_plan 移动的 SDRAM 电源块名还是旧层名。是否修、何时修请主会话定。
