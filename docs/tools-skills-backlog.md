# 工具和 skill 候选清单（项目收尾时处理）

用户 2026-11-21 说：这个项目里有几样东西可以做成工具，规则也可以固化成 skill；这件事等板子做完再做，现在只收集整理。本文就是这份收集，H743 板交付、合回 `main` 之后处理。处理时每一项先拿给用户定做不做、怎么做，本文不是已批准的计划。

整理时的状态：分支 `integration-h743`，commit `9b07db5`，停点 3（两张草图）进行中。

## 现状（2026-11-24，分支 `tools-consolidation`）

H743 板交付、合回 `main` 之后做了一轮工具整合（合并前由用户审 PR）：`scripts/` 和 `stm32h743_sdram/` 里的脚本全部搬进 `Tools/KiCadDesignTools/<类别>/`，从仓库根以 `python -m Tools.KiCadDesignTools.<类别>.<工具>` 运行，板目录只留数据（`board.toml`、`place.toml`、`silk.toml`、`rules_cases.py`、`bga_block.toml`、`routes_*.py`、`sch/<页>.py`），构建由驱动 `python -m Tools.KiCadDesignTools.build <板目录> <步骤>` 跑。工具清单和规则对照在 [Tools/KiCadDesignTools/README.md](../Tools/KiCadDesignTools/README.md)，命令的坑在 [tools.md](tools.md)。下面各节的原文保留（路径是当时的），每个候选下加了一行“现状”。

| 项 | 现状 | 在哪 / 哪个提交 |
|---|---|---|
| T1 线序分配 | **搁置**：没有通用化；`line_order.py` 已删（最后在 `a889ac4`），它的结果留档在 `stm32h743_sdram/probes/line_order/`（`balls_identity.json` 仍由 `planning.bga_plan` 读） | 删除：`ff313ff` |
| T2 busroute 去依赖、差分对、蛇形 | **部分**：去依赖做完（基准自带夹具 `tests/busroute/fixture/`）；蛇形和按量预留在整合前做完（`routing/busroute/tune.py`）；差分对没做（以太网两对按两根网络写、`route_table` 报对内差） | `1c356fb`（阶段 1） |
| T3 新工程生成 | **做完**：两条路都走了，规格档 C 的模板 `templates/C-bga-065/`，加通用生成器 `project.make_project`（模板 + `board.toml`）；H743 的工程文件逐字节不变 | `b89692b`（3A）、`45bf65e`（H4a） |
| T4 规则基准板 | **做完**：框架 `rules.fixture`，用例表是板目录的 `rules_cases.py`；和 `tests/drc_tools` 没有合并框架 | `b89692b`（3A） |
| T5 原理图画法层和网表核对 | **做完**：画法 `schematic/sheet.py`，生成 `schematic.generate`（`[schematic] pages`），核对 `schematic.check`（意图、引脚表 `[schematic.pin_table]`、换位 `[schematic.swap]`，后两项可选），单页试画 `schematic.build --page`（代替 `try_page.sh`）；`kisch.py` 文档里的错路径已改 | `5da90d6`（3B） |
| T6 阻抗 | **部分**：叠层有了数据文件（`Tools/KiCadDesignTools/data/stackups/JLC06161H-3313E.toml`，`core/stackup.py`，长度测量用它的过孔高度），`rules.impedance` 仍用自己写死的表 | `0922b81`（H3） |
| T7 指标表汇总 | **部分**：每步一张表（`copper.copper_table`、`analysis.route_table`，布局的 `place_check` / `layout_probe`），两次构建按数字比用 `analysis.compare_runs`（驱动的 `compare`）；没有一条命令出八组的整表 | `6f59732`（3D）、`0366db2`（3G） |
| T8 铜皮草图读回、视图 | **部分**：`read --sketch` 能读回 `whole`（整合前）；视图是 `views.sketch_view`，外形和规则区仍从 `place.toml` 取，不从板文件读，没并进 `cu_sketch` | `091faea`（3C） |
| T9 摆位辅助和粗筛 | **部分**：`placement.place` 通用（坐标在 `place.toml`，`--pcb` / `--rot` 试转向）；飞线交叉数粗筛没做 | `091faea`（3C） |
| T10 手改检测 | **搁置**：没做。写板的程序改成确定的 uuid 之后同一构建的板文件逐字节相同，比对摘要的前提有了 | `ef36bbd` |
| T11 分步构建骨架 | **做完**：驱动 `build.py`（步骤、计时、报告目录、退出码、低优先级和重活锁、`--dry-run`、`init`、`pcb-update`、`compare`），`build.sh` 只是薄壳；整板基准 `regress --board demo`（演示板 `templates/demo_board/`） | `1c2c342`（阶段 2）、`dfbb1ab`、`562c6cf`、`78ac4a3` |
| S1–S11 skill | **搁置**：一个都没写。整合后命令都是 `python -m Tools.KiCadDesignTools....`，skill 可以只指向 README 的工具表和规则对照、tools.md 的坑编号（K1…） | — |

同一轮删掉或挪走的板目录文件（都不再被任何工具读，内容在 git 历史里）：

- `stm32h743_sdram/line_order.py`：最后在 `a889ac4`。
- `stm32h743_sdram/decap_search.py`（停点 4 的背面去耦位置搜索，结果已在 `place.toml`）：最后在 `c38fa0d`。
- `stm32h743_sdram/patches/`（`nn_patch.md`、`sw_bga_fan_patch.json`，停点 7 走线子任务的补丁建议，用上的已在 `routes_mcu_nw.py` / `routes_mcu_sw.py` 的 `PATCH` 里）：最后在 `c38fa0d`。
- `stm32h743_sdram/routes_probe_*.py` 四个试走文件和 `line_order/` 挪进 `stm32h743_sdram/probes/`（`ff313ff`）。

标记：**核** = 读代码或文档核过（文件和行号能对上）；**推** = 我的推断，没跑过、没对过。没标的是从 `docs/tools.md`、`docs/shape/` 转述的。

## 0. 处理时的前提

- 先用 `shape-your-project` 清空 `docs/shape/inbox/integration-h743.md`，规则定下来之后再写 skill：skill 引用规则编号，规则还在变时写进 skill 的内容会马上过期。
- 每个工具动手前按 PROC-5 查一遍现成的，记下为什么不用；按 PROC-15 重写进 `scripts/`（现在是 `Tools/KiCadDesignTools/<类别>/`），不直接搬，配一块小基准板和预期指标，挂到 `scripts/regress.py`（现在是 `python -m Tools.KiCadDesignTools.regress`）上。
- 这台电脑在 12 个进程的重负载下会硬复位（用户 2026-11-21）。批量计算先筛：候选按不换位的飞线交叉数粗筛到两个，两个各开一个进程并行算；要避免的是不筛就开十几个进程。不需要规定"默认单进程"。工具的默认值和文档按这个口径写。

## 1. 现有脚本一览

（整理时的表，路径是当时的；现在的清单见 `Tools/KiCadDesignTools/README.md`。）

| 脚本 | 在哪 | 通用程度 | 基准（PROC-15） |
|---|---|---|---|
| `dru_canary.py`、`dru_match.py`、`drc_probe.py`、`len_rules.py` | `scripts/` | 已通用（输入是任意板子和它的规则文件、`length_groups.json`）**核** | `scripts/tests/drc_tools/check.py` **核** |
| `kisch.py`、`sch_build.sh` | `scripts/` | 已通用；`SYMBOL_DIR` 写死 `D:\KiCad\...`（本机环境，可接受）**核** | `scripts/tests/kisch/check.py` **核** |
| `cu_sketch.py` | `scripts/` | 已通用（草图格式、检查、写入、读回、指标）**核** | `scripts/tests/cu_sketch/check.py`，自建 40 × 30 mm 板 **核** |
| `busroute/` | `scripts/` | 库本身通用，数字从 `.kicad_pro` / `.kicad_dru` 读 **核**；基准依赖板目录（见 T2） | `scripts/tests/busroute/check.py` **核** |
| `impedance.py` | `scripts/` | 叠层表写死 JLC06161H-3313E **核** | `scripts/tests/impedance/check.py` |
| `net2pcb.py`、`track_shape.py`、`pcb_view.py`、`layer_view.py`、`via_spots.py`、`pour_islands.py`、`teardrops.py`、`silk_refs.py` | `scripts/` | 前两块板写的，按板文件工作 | 没有 |
| `auto_tracks.py`、`auto_clean.py`、`auto_tidy.py` | `scripts/` | 配 KiCadRoutingTools 用 | 没有；见第 5 节 |
| `line_order.py` | `stm32h743_sdram/` | 绑这块板（见 T1）**核** | 没有 **核** |
| `make_project.py`、`rules_fixture.py`、`sch_check.py`、`gen_sch.py`、`sch/common.py`、`place.py`、`sketch_view.py`、`build.sh`、`sch/try_page.sh` | `stm32h743_sdram/` | 各有一部分通用（见 T3–T11） | `rules_fixture.py` 本身就是规则的基准板（69 个用例） |

## 2. 工具候选

### T1 线序分配（`stm32h743_sdram/line_order.py`，690 行）

用户的话（2026-11-21）：这块板做完后转正成通用工具；用户设想它也用于 DDR 和 CPU 核心的扇出连接；DDR 要把一个差分对当成一个整体来分配（同层、相邻、同一种绕法）。

**现在做什么**（**核**）：确定性地给 SDRAM 总线每根线定"走哪层（L1 / L4 / L6）、从 MCU 哪边绕、接 SDRAM 哪个球"，允许字节内换位和字节通道互换（NBL 跟着字节走）。命令 `dump`（KiCad 的 Python 读球位写 `out/sketch/balls.json`）、`scan`（4 个转向 × 24 种通道映射，每种一行）、`solve <rot> <map> [out]`（一种情况的全表、交叉、长度，写 `line_order.txt/json` 和 `swap.csv`）。两条求解路：默认 `Chains`（动态规划，只用 numpy）；`--time > 0` 时走 scipy 的 `milp`（要系统 Python，scipy ≥ 1.9）。

**用户定的口径和代码的对照**：

| 口径 | 代码现状 |
|---|---|
| 判交叉：只有带焊盘的那面（L1）按两端顺序一致严格判；内层按通道容量，顺序不一致的线列出来 | `Chains.solve` 已按此做（commit `39c6b78`），列出的线记在 `loose` 里 **核**；`milp` 路径的文档字符串仍写"内层也要求同样的顺序，比需要的严"（第 21–22 行）**核**，两条路口径不一致 |
| 候选摆法先用不换位的飞线交叉数粗筛，只细算最少的两种 | 没有实现：`scan` 是全部 96 种都细算；仓库的 `*.py` 里没有飞线交叉的计数 **核**（以前的摆位对比在分支 `research/sdram-placement-study`） |
| 粗筛后两个候选各开一个进程并行 | `--jobs` 默认 1，注释写"电脑在重负载下复位"**核**；没有"先筛再并行两个"的流程 |
| DDR 的差分对当一个整体 | 没有 **核** |

**还绑着这块板的地方**（**核**，都在第 30–46 行的常量和 `Model` 里）：

- 位号 `U201` / `U301`、网络前缀 `FMC_`、`FMC_SDCLK_R` 当成 `FMC_SDCLK` 的一段、字节号从网络名解析（`FMC_D<n>` 的 n // 8、`FMC_NBL<k>`），换位表输出的列名 `DQ` / `DQM`。
- MCU 的球阵几何：0.65 球距、15 × 15 的中心偏移 4.55、出线深度最多 4 圈、`MCU_HALF = 6.5`（封装 5 + 规则区 1 + 0.5）；`under()` 里按这颗 UFBGA176+25 的空环写的行号（E–K 行、L 行）。
- SDRAM 的几何：`SD_HALF = (4.0, 6.5)`、中间过道、"第 1–2 列从外侧进、内列从过道两端进"的规则（`_entries` 里的 1.4、1.2、2.0）。
- SDRAM 只放在 MCU 东侧（`sc = mc.x + 5 + gap + hw`），只能改转向、间距、上下偏移。
- 层名 `L1 / L4 / L6` 和各自的角色、`UNDER_LAYERS = ("L4",)`。
- 容量常数 `OPENING_CAP`、`OPENING_CAP_INNER`、`UNDER_CAP`、`EAST_CHANNELS`、`LEN_CAP`、`DETOUR_CAP` 和代价权重：都是这块板量出来或定的。

**通用化要做的**：

1. 输入改成描述文件：两端（或多端）器件的位号、参与的网络、换位规则（组内任意换、组可整体互换、跟随关系如 NBL → DQM、DQS 跟字节）、差分对清单（整体分配）、可用的层和角色（带焊盘的面严格判、内层按容量）、候选摆法（转向、所在边、间距、偏移）。
2. 球位直接从板文件读（`busroute.Board` 已经能读），封装几何（球距、圈数、空环、过道）从焊盘坐标推出来，不写常数。
3. 容量从 `busroute.Fanout` 的出线规律算（它知道每边、每层有几条通道），不再手填常数。
4. 粗筛：不换位的飞线交叉数排序，只细算最少的两种，两种各一个进程并行。
5. 两条求解路留一条，或者把口径统一（见第 7 节问题）。
6. 输出除了表和换位表，再出一份能直接喂给 `busroute --sketch` 的线束描述骨架（**推**：这样从分配到草图不用手抄）。
7. "CPU 核心的扇出连接"要先和用户对一下指的是什么（第 7 节）。

**基准**：现在没有（PROC-15 的缺口：它在停点 3 已经在用）。转正时要两块：一块十几根线、答案能手算的小板；一块把 H743 这次的结果（转向、通道映射、每层根数、`loose` 数、各组长度差）钉住当回归。

**规模**：大。**依赖**：T2（`Board`、`Fanout`）、T9 的粗筛；DDR 部分依赖 T2 的差分对。

**现状（2026-11-24）**：搁置。`line_order.py` 删除（最后在 `a889ac4`），没有通用化，也没有基准；分配表留档在 `stm32h743_sdram/probes/line_order/`。离线的整块 BGA 模型 `planning.bga_plan` 带一版 SDRAM 线序（`try/fanout-first`），不是这里要的通用工具。

### T2 `busroute`：去掉对板目录的依赖，补差分对和蛇形

**现在**（**核**）：线束、BGA 扇出、换层过孔阵、几何检查、写板、DRC、长度、指标、出图，约 2600 行，带基准。

**还绑着的**：

- 基准 `scripts/tests/busroute/check.py` 从 `stm32h743_sdram/` 导入 `make_project`（建叠层和空板、`SDRAM_FP`），拷那块板的 `.kicad_dru` 和 `h743.pretty` **核**。板目录一挪或一改，`scripts/` 的回归就坏。
- `Profile` 的类默认值是规格档 C 的数（区内 0.09、过孔 0.30 / 0.15），项目文件里读不到时用它们 **核**；换档的板子要确认都能从文件读到。
- 没有差分对（全包里搜不到 diff pair 的处理）**核**；`job.py` 里 `TUNING` 写着"not yet"，蛇形还没做 **核**。

**要做的**：基准改用 `scripts/tests/` 下自带的叠层和封装；差分对（对内间距、对内等长、整体扇出）；蛇形和按量预留（RTE-2、RTE-7，停点 6 本来就要写，收尾时看它是否已经通用）。

**规模**：去依赖小；差分对中到大；蛇形在本项目里做。**依赖**：T3（叠层来源）。

**现状（2026-11-24）**：去依赖做完（阶段 1，`1c356fb`：基准的叠层、工程文件、规则文件和 BGA-90 封装冻结进 `tests/busroute/fixture/`）；`Profile` 的类默认值仍是 C 档的数，只在文件里读不到时用；蛇形和按量预留做完（`tune.py`、`--tuning-budget`、`humps=`）；差分对没做。

### T3 新工程生成（`stm32h743_sdram/make_project.py`，224 行）

**现在**（**核**）：从 `templates/common/` 加规格档 C 的数生成 `.kicad_pro`（板级下限、网络类、按 `pins.csv` 归类）和带真实叠层的空板。

**绑着的**：工程名、`FLOORS` 的取值、叠层 JLC06161H-3313E、网络类和 `pins.csv` 的格式、SDRAM 封装名。

**要做的**：两条路二选一（第 7 节问题）：(a) 补一份规格档 C 的模板文件，`RUL-1` 的"从模板起"直接成立；(b) 改成通用生成器，输入"规格档 + 叠层 + 网络类表"。RUL-1 的信号已经两次碰到"C 档没有模板"（2026-11-16、2026-11-20）。

**规模**：小到中。**被依赖**：T2 基准、T4、T6。

**现状（2026-11-24）**：做完，(a)(b) 都做了。`templates/C-bga-065/`（`45bf65e`）是 C 档的模板；`project.make_project <板目录>`（`b89692b`）从 `[board] template` 加 `board.toml` 的 `[project]`、`[netclasses]`、`[netclass_patterns]`、`[[footprints.derived]]` 生成工程文件、空板和派生封装，叠层从 `[board] stackup`。第 7 节问题 5 因此不用再问。

### T4 规则基准板（`stm32h743_sdram/rules_fixture.py`，369 行）

**现在**（**核**）：用板子自己的空板、`.kicad_pro`、`.kicad_dru` 搭基准板，每条规则一个违规用例和一个合规用例，DRC 跑两遍（静态、生成等长窗口后），另外量铺铜间距、焊盘连接方式、过孔高度。RUL-2 的"规则阶段板上还没有对象"就是靠它解决的（inbox 信号）。

**绑着的**：规则区名和坐标（`BGA_MCU`、`BGA_SDRAM`）、层映射、每个用例本身。

**要做的**：拆成通用框架（搭板、放对象、跑 DRC、比违规集合、三项测量）加每块板的用例表；用例表和规则文件放在一起。和 `scripts/tests/drc_tools/` 思路相同，范围不同，框架可以共用（第 4 节）。

**规模**：中。**依赖**：T3。

**现状（2026-11-24）**：做完（`b89692b`）：`rules.fixture <板目录> <输出目录>` 是框架，用例表是板目录的 `rules_cases.py`（和规则文件放在一起）；演示板有自己的一份。和 `tests/drc_tools` 没有共用框架。

### T5 原理图：画法层和网表核对（`sch/common.py`、`sch_check.py`、`build.sh sch`、`sch/try_page.sh`）

**现在**（**核**）：`sch/common.py` 定了一套画法（每个脚短线接电源符号或全局标号、无本地标号、按页编号的位号、网格单位、两脚件方向的修正）；`sch_check.py` 做三件事：画图时记下的"脚 → 网络"对网表、MCU 球对 `pins.csv`、SDRAM 字节对 `swap.csv`；`try_page.sh` 单独试一页。

**绑着的**：`sch_check.py` 的 `MCU = "U201"`、`SDRAM = "U301"` 和 `swap.csv` 的检查是这块板的；`common.py` 的 `POWER` 集合、`FP` 表、库名 `h743`。

**另外发现**（**核**）：`scripts/kisch.py` 文档字符串第 15 行说网表核对在 `scripts/sch_check.py`，那个文件不存在，实际在 `stm32h743_sdram/sch_check.py`。

**要做的**：画法层并进 `kisch`（或 `scripts/kisch_style.py`），"意图对网表"和"引脚表对网表"两项提成通用检查，换位检查做成可选插件；`try_page.sh` 和 `sch_build.sh` 合一。

**规模**：中。**依赖**：无。

**现状（2026-11-24）**：做完（`5da90d6`）：画法层是 `schematic/sheet.py`（不并进 `kisch`），`schematic.check` 的三项检查由 `board.toml` 的 `[schematic.pin_table]`、`[schematic.swap]` 开关，`schematic.build <板目录> <输出> --page <页>` 代替 `try_page.sh` 和 `sch_build.sh`。

### T6 阻抗（`scripts/impedance.py`）

**现在**（**核**）：二维场解，叠层表 `STACKUP` 写死 JLC06161H-3313E，`--layer` 只能选这张表里的层。

**要做的**：叠层从 `.kicad_pcb` 的叠层段或一张表读。算法不动。板厂计算器仍然为准（RUL-3）。

**规模**：小。**依赖**：T3（叠层的单一来源）。

**现状（2026-11-24）**：部分。叠层的单一来源有了（`data/stackups/<名>.toml`，`core/stackup.py`，`board.toml` 的 `[board] stackup`），`rules.impedance` 还没改成读它。

### T7 指标表汇总（PROC-4）

**现在**：八组指标散在几处：`busroute/metrics.py`（本组的连通、线形、长度、过孔、金丝雀）**核**、`cu_sketch.py measure`（铜皮）**核**、`dru_match.py`（空匹配）、`track_shape.py`（线形）、`build.sh` 的耗时。没有一个命令出整张表（**推**：按 `docs/tools.md` 的列表对过，没找到汇总脚本）。

**要做的**：一个命令读板文件和 DRC 报告，调上面这些（不重写），出同一张表并和上次比，变差的项标出来。

**规模**：中。**依赖**：T2、T8。

**现状（2026-11-24）**：部分。铜皮一步和走线一步各出一张表（`copper.copper_table`、`analysis.route_table`），`analysis.compare_runs` 按数字比两次构建；“变差的项标出来”和八组合一张表没做。

### T8 铜皮草图：补读回、并入视图（`cu_sketch.py`、`sketch_view.py`）

**现在**：`whole` 和区里的开孔读不回来（inbox 信号，PWR-7）；`sketch_view.py` 单独画图，BGA 外形和规则区从 `place.py` 取 **核**。

**要做的**：读回补全；视图做成 `cu_sketch.py view`，外形和规则区从板文件读。PWR-8、PWR-9 里工具作者自定的数（外层 0.2 mm、焊盘外扩 0.3 mm）等用户定了再改默认值。

**规模**：小到中。**依赖**：无。

**现状（2026-11-24）**：部分。读回 `whole` 已能做（`read --sketch`）；视图是 `views.sketch_view <板目录> <输出>`，外形和规则区读 `place.toml`，没有并进 `cu_sketch`。PWR-8、PWR-9 的工具自定数（0.2、0.3）仍是草图参数的默认值。

### T9 摆位辅助和候选粗筛（`place.py` 的通用部分）

**现在**（**核**）：`place.py` 是这块板的坐标表，另带几样通用的事：画板框（圆角）、按封装外扩画规则区、把还没摆的器件停在板外、`--pcb <副本> --rot <角度>` 在副本上试别的转向。

**要做的**：通用部分提成一个小库；加"候选摆法按不换位的飞线交叉数排序"（用户 2026-11-21：只细算最少的两种）。坐标表留在每块板（PROC-13）。注意 RTE-1 的信号：飞线排名不能代替试走，所以它只做粗筛。

**规模**：小到中。**被依赖**：T1。

**现状（2026-11-24）**：部分。通用部分在 `placement.place`（板框、规则区、停放、`--pcb` / `--rot`），坐标表是 `place.toml`；粗筛没做。

### T10 手改检测（PROC-13 的缺口）

**现在**：没有。inbox 信号：没有东西能发现用户在重新生成之前手改过某一页原理图，靠先问。

**要做的**（**推**）：生成时记下每个输出文件的摘要，下次生成前比对，变了就停下来报"这些文件被手改过"。原理图、`.kicad_pro`、`busroute` 写过的板子都能用。

**规模**：小。**依赖**：无。

**现状（2026-11-24）**：搁置。确定的 uuid（`ef36bbd`）让同一构建的板文件逐字节相同，可以作为摘要比对的基础。

### T11 分步构建骨架（`stm32h743_sdram/build.sh`）

**现在**（**核**）：按步骤（`rules`、`sch`）跑，每步计时、滤掉 KiCad 的噪声行、报告写到 `out/<步骤>`；kicad-happy 分析器找不到时给出提示。

**要做的**：通用部分（步骤分派、计时、报告目录、退出码）提成 `scripts/` 下的一份，每块板只列自己的步骤。可以和 T7 合做。

**规模**：小。

**现状（2026-11-24）**：做完：驱动 `Tools/KiCadDesignTools/build.py`（`1c2c342`），每块板只写 `board.toml`；`build.sh` 是薄壳（`dfbb1ab`）。指标表汇总（T7）没合进来。

### 已经通用、收尾时只需维护的

`dru_canary`、`dru_match`、`drc_probe`、`len_rules`、`regress`、`kisch`、`net2pcb`、`pcb_view`、`layer_view`、`via_spots`、`pour_islands`、`teardrops`、`silk_refs`。`track_shape.py` 还不认圆弧（RTE-8 信号），SPEC 第 11 节把"圆弧几何检查并进 `track_shape.py`"列为本项目要写的，停点 6 之后看是否已做。

**现状（2026-11-24）**：都在 `Tools/KiCadDesignTools/` 的类别下（阶段 1，`1c356fb`）；`analysis.track_shape` 认圆弧（2026-11-22，带基准）。

## 3. Skill 候选

**现状（2026-11-24）**：S1–S11 都还没写（搁置）。表里的脚本名是当时的；写的时候按 README 的工具表换成模块名，坑按 tools.md 的编号（K1…）引用。

共同原则：

- skill 写"什么时候做、按什么顺序、跑哪些脚本、交什么"，规则本身留在 `docs/shape/`，skill 里只写编号和文件路径，加载时去读。否则规则一改，skill 就和 shape 打架。
- 数值只在 `docs/design-rules.md`、`docs/rule-profiles/` 和工程的规则文件里（RUL-1），skill 不抄数。
- 命令和坑留在 `docs/tools.md`，skill 指过去。
- 每块板的决定留在板目录的 `SPEC.md`、`unverified.md`。
- 子任务能不能加载 skill 要先验证：`docs/tools.md` 记着 kicad-happy 的 skill 在子 agent 和后台会话里调不了。如果项目 skill 也一样，skill 只能给主会话用，子任务照 CLAUDE.md 的做法拿文件（第 7 节问题）。

一种组织法（**推**，第 7 节问用户）：一个 `pcb-board` skill，`SKILL.md` 只放阶段索引和停点流程，每个阶段一个子文件，用到哪个阶段读哪个；另外几个跨阶段的小 skill 单列（S8、S10、S11）。这样触发词不重叠。下面按阶段列内容，合并还是分开到时候再定。

| # | 名字（暂定） | 什么时候加载 | 带哪些规则和文档 | 调哪些脚本 |
|---|---|---|---|---|
| S1 | 方案 | 开一块新板、定器件 / 板型 / 叠层，写 `SPEC.md` | PROC-1、2、7、8；RUL-11、12；PWR-1；RTE-14；LAY-10；`SPEC.md` 的节结构（H743 的第 1–16 节可当骨架）、`unverified.md` 的表头和"谁核"口径 | `impedance.py`（估线宽）；问别人的问题用用户的 `/to-questionnaire` |
| S2 | 规则（停点 1） | 新建工程、改 `.kicad_dru` 或 `.kicad_pro` | RUL-1–5、11、12；`docs/design-rules.md` 的已知陷阱；`docs/rule-profiles/*`；tools.md 里 `SaveBoard` 写默认 `.kicad_pro`、`intersectsArea` 对铺铜区按整块判两条 | T3、`dru_canary`、`dru_match`、T4、`impedance`、`len_rules` |
| S3 | 原理图（停点 2） | 写或改原理图页、核网表 | RUL-6–10；PROC-13、14；tools.md 的 `kisch` 分页说明、两脚件方向、`+3V3A`；分页并行时公共模块只由主会话改、子任务发现公共代码的错当场上报（PROC-13 信号） | `kisch`、`sch_build.sh`、T5、kicad-happy 的 `analyze_schematic.py` |
| S4 | 草图（停点 3） | 摆两端器件、出线序草图和铜皮区域草图 | LAY-1、7；PWR-1、3、7、8、9；RTE-1、13、14、15；PROC-3；本文第 0 节的并行口径；inbox"待整理"里的交叉口径和粗筛（清 inbox 之后在 routing.md 里的编号） | T1、T9、`busroute --sketch --fast`、`cu_sketch check/apply` |
| S5 | 布局（停点 4） | 摆其余器件、布局验收 | LAY-2–10；FIN-1（位号留不留在这里问） | `place.py`（每板）、`pcb_view`、`via_spots`、kicad-happy 的 `emc`（LAY-9） |
| S6 | 电源与铜皮（停点 5） | 写铺铜区、查连通 | PWR-2–9 | `cu_sketch apply/measure/read`、`pour_islands`、`kicad-cli ... --refill-zones` |
| S7 | 走线（停点 6、7） | 扇出、总线、零散线、等长 | RTE-2–12、15；PROC-3（轮数上限）、PROC-6（构建时间） | `busroute`、`len_rules`、`track_shape`、蛇形（待写）；KiCadRoutingTools 只按 RTE-4 的例外用 |
| S8 | 停点交接 | 到停点、交付、提交板子之前 | PROC-4、9、10、11、12；`SPEC.md` 第 14 节"每个停点交什么"的七项（通用的部分）；用 AD 的说法解释；提醒"文件 → 还原" | T7、T11 |
| S9 | 收尾（停点 8） | 丝印、泪滴、最后检查 | FIN-1–4 | `teardrops`、`silk_refs` 或每板 `silk.py`、`--schematic-parity` 的 DRC、`dru_canary` |
| S10 | KiCad 脚本 | 写或改调用 pcbnew / `kicad-cli` 的脚本、手写 `.kicad_dru` | 只指向 `docs/tools.md` 的"已知的坑"和 `docs/design-rules.md` 的"已知陷阱"，不复制 | 无 |
| S11 | 读规格书 | 从 PDF 取引脚表、尺寸、时序（多由 Sonnet 子任务做） | PROC-14、RUL-10；tools.md 的厂商下载限制表；"拿不到的列地址请用户下载，不绕过" | `pdftotext`、`pdftoppm` |

**留在 `docs/shape/` 不进 skill 的**：每条规则的正文、级别、_Why_、_Source_、Signals、Open questions、References、`Next id`。规则的改动只走 `shape-your-project`。

## 4. 重叠

- **T1 和 `busroute.Fanout`**：都在算 BGA 出线容量，T1 用手填常数，`Fanout` 知道真实通道。通用化时 T1 用 `Fanout` 的数。
- **T1 的粗筛和 T9**：同一件事，放一处。
- **T4 和 `scripts/tests/drc_tools/`**：都是"搭板、放对象、比 DRC 结果"，框架共用。
- **T7 和 `busroute/metrics.py`、`cu_sketch measure`**：汇总只调用，不重写。
- **出图**：`pcb_view`、`layer_view`、`busroute/render.py`、`sketch_view.py` 四处各画各的（**推**：可以共用一个底图模块，收益不大，不急）。
- **S3 和 kicad-happy 的 `kicad` skill、S5 和 `emc`、S11 和 `datasheets`**：kicad-happy 的部分直接调用，不重写；我们的 skill 只写"什么时候跑、发现怎么甄别"（RUL-9、LAY-9、PROC-14）。
- **阶段 skill 和 CLAUDE.md 的"改哪个区域先读那个区域文件"**：skill 不另立一套读文件的规矩，照 CLAUDE.md。
- **S8 和每块板 `SPEC.md` 的停点表**：停点的个数和各停点的完成标准是每块板的事，留在 SPEC；skill 只带通用的交接内容。
- **S1 和用户的 `/to-questionnaire`、`/grilling`、`/prototype`**：S1 里遇到"只有别人能答"的问题指过去，不自己做问卷。

## 5. 不做成工具或 skill 的

| 东西 | 理由 |
|---|---|
| KiCadRoutingTools 的封装和 `auto_tracks` / `auto_clean` / `auto_tidy` 的通用化 | RTE-4 默认不用通用自动布线器；三块板上它的结果都被判不整齐或走不通。保持现状，不投入 |
| 电源面自动分割 | PWR-4，用户 2026-11-16 否决 |
| 替人画铜皮外形的工具 | 铜皮由人画（PWR-3、PWR-7，用户 2026-11-16 的反馈）；`cu_sketch` 文档字符串写明它不发明形状 |
| 搜索式的线序草图（停点 3 两个子任务各写的网格搜索、退火） | CLAUDE.md 的分工表：线序分配用确定性脚本算，不交给子任务搜索；两版都没画通 |
| 自动摆位 | 没有依据也没人要；坐标表留在每块板（PROC-13） |
| 把阻抗脚本做成通用场解工具 | 板厂计算器为准（RUL-3），只做 T6 的叠层参数化 |
| 重写 kicad-happy 已有的审查 | 见第 4 节 |
| 模型和思考程度的分工表做成 skill | 它要每次会话都生效，用户写在 CLAUDE.md 里，留在那里 |
| 轮数上限、构建时间上限写进代码当判据 | 它们是规则（PROC-3、PROC-6），工具只报数，停不停由规则和用户定 |
| 每块板的 `gen_sch.py` 页模块、`place.py` 坐标表、`SPEC.md` 内容 | 每块板的事 |
| 厂商下载限制、pcbnew 的坑 | 是事实，留在 `docs/tools.md`；S10、S11 只指过去 |

## 6. 建议的顺序

1. 清 inbox（`shape-your-project`），把停点 3 以后定的口径（交叉口径、粗筛、并行数、等长按字节通道）写进规则。
2. T2 的去依赖和 T3：`scripts/` 的回归不再依赖板目录；下一块 C 档的板子有起点。量小、阻挡后面所有事。
3. T1 线序分配（连同 T9 的粗筛），先配基准。用户点名要的，下一块板（PROC-7 信号：单颗 DDR3）就要用；DDR 的差分对要等 T2 的差分对。
4. T7 指标表汇总、T11 构建骨架：每个停点都要用。
5. T4、T5、T6、T8、T10：各自小，按下一块板用到的阶段排（PROC-15：在用到它的阶段开头写）。
6. Skill：先 S8（停点交接，每个停点都用）和 S2（规则，坑最多），再按阶段补。S4、S7 等 T1、T2 转正后再写，免得 skill 引用的命令还在变。写 skill 时用 `writing-for-agents`。

## 7. 只有用户能回答的问题

1. 线序分配工具的范围：只管"两颗器件之间一条总线"，还是要支持一对多（多颗 DDR、fly-by）？
2. "CPU 核心的扇出连接"指什么：应用处理器 BGA 出线到外围器件的分配，还是核心电源球的扇出和过孔分配？
3. DDR 的分配单位：除了差分对整体，DQS 是否跟着它的字节通道一起换、DM 跟字节走，和这次 NBL 的做法一样？
4. `line_order.py` 的两条求解路（默认的动态规划、要 scipy 的 `milp`）留哪条？`milp` 那条还按"内层也严格判"，要么改口径要么删。**不用再问**：`line_order.py` 已删（最后在 `a889ac4`）；通用的线序工具重写时只按用户定的口径（带焊盘的层严格判、内层按容量）写一条。
5. 规格档 C：补模板文件，还是把 `make_project.py` 做成通用生成器？**已定（2026-11-24 的整合）**：两样都做了，见 T3 的现状。
6. Skill 放哪里：本仓库 `.claude/skills/`（只这个工作区用），还是用户级 `~/.claude/skills/`（别的仓库也用）？
7. Skill 的粒度：一个 `pcb-board` 带分阶段子文件，还是每个阶段一个 skill？
8. 收尾时这份清单要不要按仓库的惯例拆成 GitHub issue（每个候选一张），还是保留这个文件逐条做？
9. KiCadRoutingTools 和 `auto_*` 三个脚本：留着不动，还是收尾时移出 `scripts/`？**已定（2026-11-24 的整合）**：`auto_*` 原样搬到 `Tools/KiCadDesignTools/third_party/`，不改、不加基准；KiCadRoutingTools 留在 `Tools/KiCadRoutingTools/`（gitignore）。
