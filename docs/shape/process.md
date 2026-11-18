# 推进流程

一块板子按什么顺序做、每一步怎样算做完、什么时候停下来回退、怎么交给用户审查，以及工具和构建怎么管。

依据里说的"六层废弃板"是 2026-11 中止的 RK3568 + LPDDR4X 板，留档在分支 `integration-rk3568`（不合并）；"双层板""四层板"是 `stm32f411_minsys/` 和 `steval_fcu001v2/`。

Next id: PROC-16

## Pillars

- 上游的问题回到上游改，不在下游补。
- 每一步的"做完"都能用数字说清。
- 反馈回路要快：等一小时才知道结果的做法本身就是问题。
- Claude 画，用户审；用户看不到的东西等于没做。

## stages

阶段顺序、完成标准和回退。

### Rules

- **PROC-1** · provisional · 阶段顺序：方案 → 规则 → 原理图 → 电源树和铜皮区域草图 → 布局 → 电源与铜皮 → 信号走线 → 收尾 → 交付。 _Why:_ 六层废弃板把电源放在信号之后处理，电源面划不出整块。
- **PROC-2** · provisional · 每个阶段有可算的完成标准，不达标不进下一阶段；发现是上游阶段的问题，回退到那个阶段改。 _Why:_ 六层废弃板的布局不合格仍进了走线，后面全在补。
- **PROC-3** · provisional · 连续两轮构建的指标没有实质改善，就停下来向用户报告根因和回退方案，不继续小修。走线优化另有轮数上限 5 + N·log₂N ÷ 7（N 是一起走的网络数，按总线组算）：达标或到上限就停，推进下一步，没达标的列给用户；不设"线束走向先给用户过目"这一关。 _Why:_ 六层废弃板后期每轮只降几项未连接，仍做了十几轮才停；H7 的走线原型上 19 根线用了 5 轮和 11 轮，用户要上限随网络数增长且不是线性的，并指出走向定了走线中仍会改、布完之前也难判断。 _Source:_ [走线和等长原型](https://github.com/immorcoding/PCB/issues/21)、[工具路线票](https://github.com/immorcoding/PCB/issues/19)
- **PROC-7** · exploring · 没做过的板型（层数、封装、接口），先做规模小一档的。 _Why:_ 从四层 STM32 直接跳到六层 BGA 加 LPDDR4，同时遇到了扇出、线序、电源面三类新问题。
- **PROC-8** · provisional · 方案阶段把器件选型、接口、板型、叠层列成选项给用户定；板子尺寸按器件占地估出两三档给用户选，定了再布局；没有规格书可核对的引脚和参数记入"未核对项"，一直带到交付。定稿写成板目录里的 `SPEC.md`，文件为准，脚本要读的内容另存数据文件（引脚表、未核对项）；写明这块板验证什么和可算的判据，交付时逐条报；每节标"已定"（改之前先问用户，批准后记入变更记录）或"起点"（直接改，交接时报告并同步改正文）。 _Why:_ 四层板布局后缩了两次尺寸，每次整板重摆；H7 测试板的决定散在十三张票里，画板的 agent 读文件比读票可靠，没有判据交付时说不清这块板测到了什么。 _Source:_ [定稿票](https://github.com/immorcoding/PCB/issues/20)

## review

和用户的交接：审查、报告、提交。

### Rules

- **PROC-9** · provisional · 阶段之间交给用户审查；分支和提交按用户当时的要求来。 _Why:_ 分工是 Claude 画、用户审（Altium 背景，KiCad 新手）；概念用 AD 的对应说法解释。
- **PROC-10** · provisional · 做的过程中发现约定守不住，或者需要改规则、改布局，当场告诉用户原因和数字，不等到交付。 _Why:_ 六层废弃板上扩大规则区、改过孔尺寸都是做了以后才报的。
- **PROC-11** · provisional · 交付时附审查清单：DRC 剩余项、没守住的约定及数字、过程中改过的规则和布局、未核对项、图片路径；提醒用户在 KiCad 里"文件 → 还原"重新载入。 _Why:_ 用户靠这份清单审查，不逐个文件看。
- **PROC-12** · provisional · 提交前核对板文件里的走线数和未连接数与刚报告的一致。 _Why:_ 提交过一次没有走线的板子。
- **PROC-13** · provisional · 脚本生成的板子和原理图，改脚本不改文件；用户在 KiCad 里手工改过之后，文件才是准的，再跑脚本前先问用户。 _Why:_ 重跑脚本会把用户的手工改动冲掉。
- **PROC-14** · provisional · 图片只做定性判断（拥挤、环路、平面被割）；坐标和尺寸一律从文件读、用脚本算；分析工具的发现先甄别真伪再报给用户。 _Why:_ 四层板上按封装方向心算引脚行号错了一格；分析器把金手指报成"离板边太近"是误报。

## tooling

指标、工具选型和构建速度。

### Rules

- **PROC-4** · exploring · 每次构建输出同一张指标表，八组：连通、线形（含圆弧）、等长、过孔、线序、铜皮、规则生效、耗时和轮数，各组的列在 [tools.md](../tools.md)；任何一项比上次差，先解释或回退。 _Why:_ 六层废弃板上放宽走线规则让开路从 35 段降到 20 段，夹角项却从 98 条涨到 182 条，没有东西拦住这种交换。
- **PROC-5** · exploring · 写新工具前先调研现成的，并记下为什么不用。 _Why:_ 六层废弃板上自研的协商布线、盘中孔、电源面补桥，和已公开的 Claude Code KiCad skill 的做法高度重合。 _Source:_ <https://github.com/Novin3dp/claude-KiCad-pcb-designer-skill>
- **PROC-6** · exploring · 全量重建超过 10 分钟、快速构建（只重建正在调的那组，不重新铺铜）超过 1 分钟，先解决构建速度再继续；构建按阶段分步，没改的步骤不重跑；每轮优化用快速构建，阶段交接前跑全量。 _Why:_ 六层废弃板的重建从 6 分钟涨到 70 分钟，后期每试一个想法要等一小时。
- **PROC-15** · exploring · 原型里的脚本转正时重写进 `scripts/`，不直接搬；每个工具配一块小基准板和预期指标，一条命令跑完全部回归；在用到它的那个阶段开头写。 _Why:_ 六层废弃板的工具没有回归基线，改一处不知道坏了哪里；原型脚本是一次性的，带着已知缺口。 _Source:_ [工具路线票](https://github.com/immorcoding/PCB/issues/19)

## Signals

- 2026-11-15 · PROC-7、PROC-8 · 定了 H7 测试板的范围和地图终点：比 RK3568 小一档，地图只走到方案定稿（[地图](https://github.com/immorcoding/PCB/issues/1)）。
- 2026-11-15 · PROC-8 · 用户纠正：器件优先选大厂、资料齐全的，不按立创库存选；目前只做设计验证，真打板时用户自己采购。
- 2026-11-15 · PROC-8 · 用户纠正：测试板上的器件不能太少，MCU 引脚占用要在六成以上，否则测不到线序的影响。
- 2026-11-15 · PROC-8 · 用户纠正：测试板的电源也不能太简单，否则验证不了电源那部分流程（铜皮类网络、电源面分块、降压环路）。
- 2026-11-15 · PROC-14 · 碍事：ST 原理图 PDF 是 Altium 导出的，文字层里网络名和位号是乱的，调研 agent 只能看渲染图读数值，再用文字层核对器件型号和阻容值（[调研票](https://github.com/immorcoding/PCB/issues/4)）。从 PDF 取值的情况这条规则没覆盖。
- 2026-11-16 · PROC-8 · 起作用：MCU、SDRAM、QSPI Flash 的型号、封装尺寸和替换料逐题列给用户定；在产状态没能在官网核实的三颗料记入未核对项（[决定票](https://github.com/immorcoding/PCB/issues/7)）。
- 2026-11-16 · PROC-8 · 起作用："大厂优先"和"资料齐全优先"冲突时用户选了后者：Flash 没按 Micron 优先，定了规格书新、KiCad 有现成符号的 Winbond（[决定票](https://github.com/immorcoding/PCB/issues/7)）。
- 2026-11-16 · PROC-5 · 缺口：调研笔记放哪里没有写明，几次都按惯例放在 `research/<名字>` 分支的 `docs/research/`；`tools.md` 也没记厂商网站对自动下载的限制（ST 的 PDF 用 curl 拿不到、WebFetch 能拿到，ISSI 有反爬，Micron 零件页是 JS 渲染）。
- 2026-11-15 · PROC-5 · 被违反：调研 agent 为了算阻抗临时写了一个二维场求解脚本（没提交），事先没查 KiCad 自带的 PCB Calculator 这类现成工具（[调研票](https://github.com/immorcoding/PCB/issues/5)）。
- 2026-11-16 · PROC-5 · 起作用：外设引脚复用的调研先找到 ST 的开放引脚库（STM32_open_pin_data）批量查备选功能，没从 PDF 解析；多外设联合分配没有现成工具，才写了一个约 100 行的回溯求解脚本（[调研票](https://github.com/immorcoding/PCB/issues/8)）。
- 2026-11-16 · PROC-8 · 缺口："引脚占用六成"没说口径。按 IO 数三套组合是 74–77%，按信号球只有 53–55%；前面票里的 SDRAM 脚数也数错了一个（57 写成 58），占用数要用脚本从引脚表数（[调研票](https://github.com/immorcoding/PCB/issues/8)）。
- 2026-11-16 · PROC-8 · 起作用："电源不能太简单"落实为 12 V 输入、串联两颗降压加一颗背光升压、两颗 LDO，稳压器型号和网络分类逐题列给用户定；TVS 和防反接 MOS 的型号、几项估算电流记入未核对项（[决定票](https://github.com/immorcoding/PCB/issues/11)）。
- 2026-11-16 · PROC-8 · 起作用：板子尺寸按 KiCad 库封装的 courtyard 加块内余量估出三档（75 × 65、85 × 75、100 × 80 mm，器件块占 88% / 67% / 54%），用户选了中档；尺寸按面积估、不按分区，块换位置估算仍成立（[决定票](https://github.com/immorcoding/PCB/issues/13)）。
- 2026-11-16 · PROC-9 · 用户纠正：布局里的"大动"从集成分支另开 `try/<改什么>` 分支，两边各跑同一张指标表（PROC-4），连同对比图给用户选，选中的合回，没选中的留档；大动指碰到分区要守住的三条、一次挪两个及以上的块或改板框尺寸、改层用途或背面规则；小改直接在集成分支上改并报告。打算作为跨板的约定走 shape 流程（[决定票](https://github.com/immorcoding/PCB/issues/13)）。
- 2026-11-16 · PROC-8 · 起作用：口径、外设组合、每个外设的器件和接口分三轮（18 题）列给用户定；"六成"的口径定为按 IO 数（÷ 140），最终 127 / 140；没在官网核到的规格书和靠推断的参数八条记入未核对项（[决定票](https://github.com/immorcoding/PCB/issues/9)）。
- 2026-11-16 · PROC-8 · 用户纠正：认领票时我只读了正文、没读评论，第一轮推荐的套 B 和评论里记的讨论倾向（套 A 加音频、分立电源）相冲突，用户指出后那一轮作废重问。读票要连评论一起读（`gh issue view --json body,comments`），这一点现在没有写在任何规则里。
- 2026-11-16 · PROC-8 · 起作用：方案阶段的假设被规格书推翻一次。问用户时假定 ST 那块 4.3 寸屏是 40 脚 0.5 mm 排线，核对后发现外形图标的是 0.8 mm，ST 是直接焊在板上；改问一次后定为 0.5 mm 通用脚序的座。
- 2026-11-16 · PROC-5 · 缺口（接上一条同类信号）：Microchip 官网对 curl 和 WebFetch 都返回 403，只能读第三方镜像；TI 的规格书 curl 能直接下；`kicad-happy:digikey` 需要 `DIGIKEY_CLIENT_ID` / `DIGIKEY_CLIENT_SECRET`，环境里没有。这些还没记进 `tools.md`。
- 2026-11-16 · PROC-14 · 起作用：外设器件有没有现成的符号和封装，是让调研 agent 直接查 KiCad 库文件得出的（LAN8742A 的符号 24 脚逐脚对过规格书），没有凭记忆说。
- 2026-11-16 · PROC-8 · 起作用：各票散着的未核对项收成一张 65 条的表，核掉 14 条，剩 25 条按"是否挡住原理图"排了优先级，三条必须先核的都要用户手动下载（[任务票](https://github.com/immorcoding/PCB/issues/18)）。
- 2026-11-16 · PROC-14 · 碍事：TI 订货表是多列表格，`pdftotext` 把行错配（TPS62A02PDDCR 被读成 DRL 封装，图上是 DDC），数值只能渲染成图读；"数值从文件读、图片只做定性"没覆盖这种情况（[任务票](https://github.com/immorcoding/PCB/issues/18)）。
- 2026-11-16 · PROC-5 · 缺口（第三次）：厂商下载限制仍没记进 `tools.md`。实测 TI、Winbond、Vishay 的 PDF 用 curl 能下；ST 要用 WebFetch；ISSI 返回占位页；Microchip、Hirose、we-online 返回 403（[任务票](https://github.com/immorcoding/PCB/issues/18)）。
- 2026-11-16 · PROC-5 · 起作用：长度规则的调研先查了 KiCadRoutingTools、`pns_drive` 和 GitHub 上的同类项目，确认没有能在命令行加圆弧蛇形的现成工具，才定为自己写；唯一自写的是约 100 行的长度表原型（[调研票](https://github.com/immorcoding/PCB/issues/14)）。
- 2026-11-16 · PROC-7 · 用户的意见：SDRAM 之后的下一块先做 DDR3（单颗、点对点），再碰 LPDDR4X；RK3568 直接上 LPDDR4X 跳得太陡。
- 2026-11-16 · PROC-8 · 碍事：连接器这张票开票时列的五项里有三项（SWD 座类型、串口单独引出、CAN 端子加跳线）在外设清单那张票里已经定过，开票前没有对照已结票的结论（[连接器票](https://github.com/immorcoding/PCB/issues/17)）。
- 2026-11-16 · PROC-5 · 起作用：写铜皮草图脚本之前先查了现成工具。本地的 KiCadRoutingTools 有自动分割，拿来和草图脚本并排做了原型，用户看过后否决；仓库外查到的（Novin3dp 的 Claude skill、几个 KiCad MCP 服务器、kipy、kicad-skip、ViaStitching 一类插件、KiKit、Freerouting）都要调用者自己给外形（[原型票](https://github.com/immorcoding/PCB/issues/16)）。
- 2026-11-16 · PROC-6 · 碰到：铜皮原型的测量脚本有一轮单版跑了 10 分钟以上没结束（对整层铺地做收缩运算）；停下来先改成只对电源块和局部铜皮算，单版降到 11 秒，五版一整套约 2.5 分钟（[原型票](https://github.com/immorcoding/PCB/issues/16)）。
- 2026-11-16 · PROC-14 · 起作用，也差点出错：图只用来判断形状，数字由脚本从板文件算；但"最窄连接"第一次算出来是 0.65 mm，实际 1.57 mm，原因是 KiCad 存的填充带切缝。脚本算出来的数也要对着图核一遍量级（[原型票](https://github.com/immorcoding/PCB/issues/16)）。
- 2026-11-18 · PROC-3、PROC-4、PROC-6、PROC-15 · 用户在 [工具路线票](https://github.com/immorcoding/PCB/issues/19) 上逐条同意后改写或新增。轮数上限的式子只有 19 根线的两个数据点（5 轮、11 轮），57 根的 52 轮是外推；快速构建 1 分钟、全量 10 分钟在真板规模上没测过。每块板记下实际轮数和耗时再校。
- 2026-11-17 · PROC-14 · 起作用：走线参考图的每条说法由第二个 agent 对着图和板文件复核，五个方向共改掉约 60 处（[走线和等长原型](https://github.com/immorcoding/PCB/issues/21)）。
- 2026-11-18 · PROC-8 · 起作用：十三张决定票的结论汇成一份方案定稿（`stm32h743_sdram/SPEC.md`，配 `pins.csv`、`unverified.md`），用户分两轮确认十二题、看过初稿后批准；用户同日同意把这个形式写进 PROC-8（[定稿票](https://github.com/immorcoding/PCB/issues/20)）。
- 2026-11-18 · PROC-8 · 碍事：连接器那张票把排线座从 Hirose FH12 换成 Omron XF2M 之后，未核对项清单里"画原理图前必须核"的那条仍写 FH12；后面的票改了前面的结论，没有回头改汇总表，写定稿时才对上。
- 2026-11-18 · PROC-9 · 起作用，也被我说错一次：H7 测试板定了九个停点，到停点提交并推送、在跟踪 issue 上发审查评论、用户批准后才继续；我第一版把线序草图并进了布局停点，RTE-13 写的是它和铜皮区域草图并行、在摆其余器件之前，自己对规则时改回（[跟踪 issue](https://github.com/immorcoding/PCB/issues/22)）。
- 2026-11-18 · PROC-14 · 起作用：`pins.csv` 由脚本生成并逐个对 KiCad 符号的球号，查出调研报告把 HSE 的 G1 / H1 写成 1 圈（实际是最外圈），并核掉了"LSE 的球是否在最外圈"这条未核对项。
- 2026-11-18 · PROC-5 · 缺口：`gh` 一次瞬时错误（`Post "https://api.github.com/graphql": EOF`）留下一个空文件，随后被 `gh issue edit --body-file` 写成了地图 issue 的正文；从 GitHub 的编辑历史（GraphQL `userContentEdits`）取回。改 issue 正文前要先确认文件非空，这一条 `tools.md` 里没有。
