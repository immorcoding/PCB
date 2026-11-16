# 走线

信号怎么走：约定、线序、等长、线形、哪些手工画、自动布线器怎么用。线形的数值标准在 [design-rules.md](../design-rules.md) 的"走线形状"一节；自动布线器的具体用法在 [tools.md](../tools.md)。

Next id: RTE-15

## Pillars

- 线序和等长都要在布局阶段就留好余地，走完再补是补不回来的。
- DRC 干净不等于整齐；整齐有自己的检查。
- 连通和整齐都要；拿一个换另一个要摆到指标表上给用户看。

## Open questions

- 等长补线由谁做：H7 测试板上先试 Claude 用脚本画圆弧、第一组给用户看；用户不认可就改成用户在 KiCad 的交互工具里拉。试完再定成规则。
- KiCad 的等长工具和自定义规则里的长度、偏差约束能不能从脚本用？还没查证。

## conventions

动手前的约定和给用户看的时机。

### Rules

- **RTE-5** · provisional · 动手前和用户定各层的用途和约定，能量化的给出数字（例：底层允许走哪些网络、总长多少）。 _Why:_ 约定没有数字就没法说守没守住。
- **RTE-6** · provisional · 走完第一个区域就把局部图给用户看走线风格，用户说了"最后一起看"也给。 _Why:_ 四层板全部走完才交，DRC 干净但被判不整齐，返工三轮。

## order-and-length

线序和等长。

### Rules

- **RTE-1** · provisional · 线序当迭代问题处理：布局阶段就把器件位置和旋转、出线层、可交换的位当变量，先出线序草图再定布局。 _Why:_ 用户 2026-11-15 的复盘；六层废弃板的 DDR 第一版让 35 根线绕封装一圈，多绕 20–50 mm，改进线方式后才降下来。
- **RTE-2** · provisional · 要等长的网络，走线时就在旁边留出补长的空间；长度表每次构建输出。 _Why:_ 六层废弃板有一对 DQS 对内差 0.499 mm，两条腿旁边都没有放圆弧的地方。
- **RTE-7** · provisional · 等长补偿用圆弧蛇形，不用 45° 梯形小弯；接口本身不要求等长时（如 USB 全速）先问用户要不要补。 _Why:_ 四层板用户认可的那一版是圆弧（半径 0.25 mm、摆幅 0.5 mm）。
- **RTE-13** · exploring · 线序草图在 KiCad 里画：摆好总线两端的器件，画出扇出和通道走向（不要求线形达标）。合格条件是换位后同一层没有交叉、每根不超过约定的最大长度、输出各等长组的自然长度差并标出补线位置；它和 LAY-1 的电源铜皮草图并行做，两张都合格、用户看过之后才摆其余器件。 _Why:_ RTE-1 要求先出草图但没说怎么算合格，H7 测试板的摆位对比只能自己发明飞线口径，两个口径的名次只有第一名一致。 _Source:_ [线序和等长票](https://github.com/immorcoding/PCB/issues/12)
- **RTE-14** · exploring · 定等长容差之前先算时序预算，写明每个数是电气必须还是为练流程取紧；方向要求（如时钟线不长于数据线）和总长上限跟容差写在一起。 _Why:_ H7 测试板上只看应用笔记的 ±10 mm 会漏掉三件事：QSPI 的 133 MHz 按规格书不成立，SDMMC 和 RMII 卡的是方向而不是容差，SDRAM 要 CL3 才撑得住总长。 _Source:_ [时序预算](https://github.com/immorcoding/PCB/blob/research/bus-timing-budget/docs/research/bus-timing-budget.md)

## shape

线形和完成标准。

### Rules

- **RTE-8** · provisional · 走线的完成标准有两条：`kicad-cli pcb drc --refill-zones --severity-all` 未连接为 0、剩余项逐条有解释；`scripts/track_shape.py` 按 design-rules.md"走线形状"达标，没达标的逐处列给用户。 _Why:_ 四层板上每段线都在 0°/45°/90°、DRC 干净，仍被判不整齐。
- **RTE-9** · provisional · 线形清单里剩下的每一处都要看图再下结论，不能按类别概括。 _Why:_ 四层板上把 13 处连续折弯一概说成"绕焊盘"，其中 2 处是小倒角直角，被用户看出来了。
- **RTE-10** · provisional · 1–2 mm 的短线（电容到引脚、引脚到过孔）把器件摆到和引脚对齐，走一段直线；不为了每个端点都 45° 进出而在 1 mm 里折三四次。 _Why:_ 四层板返工时用户指出的问题之一。
- **RTE-11** · provisional · 分叉只放在焊盘中心；线上的 T 型、Y 型分叉和过孔处的 90° 转弯要么改掉，要么逐条解释。 _Why:_ `corner_angle` 对线上的三向分叉一律报错。

## hand-and-auto

手工和自动的分工。

### Rules

- **RTE-3** · exploring · 晶振、反馈、开关节点这类局部电路手工画，不进自动布线。 _Why:_ 六层废弃板上自动结果把 32.768 kHz 晶振线绕了 PMIC 大半圈。
- **RTE-4** · exploring · 通用自动布线器的结果不直接采用：先在当板上试一小组并看线形；要用就按 tools.md 的做法（手工铜皮锁住、不许缩尺寸、分批、拉直后自查），0.5 mm 间距 IC 的扇出手工做。 _Why:_ 双层板 30 根 GPIO 只走通 13 根；四层板上它的线被判不整齐；六层废弃板 30 根通 25 根，有一根横穿半块板。
- **RTE-12** · provisional · 手工改动（挪器件、加手工线）之后，受影响的自动走线要重跑。 _Why:_ 存下来的自动结果是按当时的布局和铜皮走的，不重跑 DRC 会报短路或交叉。

## Signals
- 2026-11-15 · RTE-1 · 起作用：H743 的 53 个固定 FMC 引脚分布在 MCU 四边，其中 23 个在内两圈，SDRAM 的位置和线序必须一起定（[调研票](https://github.com/immorcoding/PCB/issues/6)）。
- 2026-11-15 · RTE-4 · 没覆盖：规则只说 0.5 mm 间距 IC 的扇出手工做，0.65 mm BGA 的扇出没提；调研 agent 建议同样手工做（[调研票](https://github.com/immorcoding/PCB/issues/6)）。
- 2026-11-16 · RTE-1 · 起作用：外设的引脚分配把出线位置当成变量来选（圈数最少、QSPI 聚成一簇），并标出 MCU 左边 E4–J4 五个内圈球和 QSPI 簇要和 SDRAM 一起排（[调研票](https://github.com/immorcoding/PCB/issues/8)）。
- 2026-11-16 · RTE-7 · 起作用：LTDC、QSPI、SDMMC、RMII 电气上都不需要等长，逐条问了用户；用户定 LTDC 不补蛇形但长度差不能太离谱（取 30 mm），SDRAM 为练流程取 ±2.5 mm（[线序和等长票](https://github.com/immorcoding/PCB/issues/12)）。
- 2026-11-16 · RTE-2 · 起作用：摆位对比给出字节内长度极差 5.2–12.3 mm，换位不会让它变小，±2.5 mm 要靠蛇形补，布局时要留位置（同上）。
