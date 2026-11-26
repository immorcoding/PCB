# PCB 工作区

KiCad 10 硬件设计。分工：Claude 完成原理图、布局、布线；用户（Altium 背景，KiCad 新手）负责审查。交付时附上审查清单，概念用 AD 的对应说法解释。

已做完的板子：`stm32f411_minsys/`（双层）、`steval_fcu001v2/`（四层，40 × 40 mm）、`stm32h743_sdram/`（六层，0.65 mm BGA 加 SDRAM；布局和走线做法的范例）。

## 去哪里找什么

- **该怎么做**（流程、验收标准、约定）：`docs/shape/`，见下面的 Project shape。
- **规则的数值**（和 AD 的对照、规则文件的坑）：[docs/design-rules.md](docs/design-rules.md)；按板型分的三套规格档（A 通用、B 0.8 mm BGA、C 0.65 mm 及以下 BGA）在 `docs/rule-profiles/`。随板子变的取值（层数、去耦距离、蛇形参数、等长容差等）不写在规则里：起点值在规格档的“布局和走线的取值”一节，每块板的值在它的 `SPEC.md` 第 7.2 节“本板取值”表。
- **工具**：全部在 `Tools/KiCadDesignTools/`，索引、每个数值放在哪、规则对照表在 [Tools/KiCadDesignTools/README.md](Tools/KiCadDesignTools/README.md)；踩过的坑在 [docs/tools.md](docs/tools.md)。板子目录只放数据（`board.toml`、`place.toml`、`silk.toml`、线束和原理图页），不放工具逻辑。
- **构建**：`python -m Tools.KiCadDesignTools.build <板子目录> <步骤>`（`--dry-run` 只打印命令）；改了工具或规则文件后跑 `python -m Tools.KiCadDesignTools.regress`。
- **起新板**：`build init <名字>` 从 `templates/demo_board/` 复制数据文件和 SPEC 样板（那块演示板只是工具链的试验件，只取它的文件结构），工程模板在 `templates/<规格档>/`。

KiCad 10.0.8 在 `D:\KiCad\bin\`（`kicad-cli.exe`，带 pcbnew 的 `python.exe`），不在 PATH 上。

这台电脑在多核持续满载时会硬复位。KiCad 的 DRC、铺铜、渲染、出图一次只跑一个，都经过构建入口或 `core/heavy`（低优先级、四个核、排队）；不要绕开它直接起 `kicad-cli`，不要并行跑。派构建类子任务时把这一条写进交代，并要求交回时没有进程在跑。

## 模型和思考程度

用户 2026-11-21 定，为了省 token。主会话不读手册页面图和草图、板图图片，这些交给子任务，只收结论、数字和页码或坐标。派子任务时按下表写明 `model` 和 `effort`。

| 任务 | 谁做 | 模型 | 思考程度 |
|---|---|---|---|
| 和用户对话、定方案、设计规则、审子任务结果 | 主会话 | Fable | 会话设置 |
| 线序草图的分配（每个球的过孔位、每根线走哪层从哪边绕、补线区）：用确定性脚本算，不交给子任务搜索 | 主会话 | Fable | 会话设置 |
| 没有先例的新工具或新算法（主会话先写清接口和基准） | 子任务 | Fable | high |
| 读手册页面图取数（引脚表、时序、尺寸）；关键数字主会话抽查一处 | 子任务 | Sonnet | medium |
| 网上调研（器件、工艺、应用笔记） | 子任务 | Sonnet | medium |
| 看草图和板图找问题（交叉、绕远、异常），回清单和坐标 | 子任务 | Sonnet | medium |
| 走线和布局的整齐度评判 | 子任务 | Opus | high |
| 按既定格式写原理图页面 | 子任务 | Sonnet | medium |
| 按已分好的层和方向写线束，构建到通过 | 子任务 | Opus | high |
| 按已有工具做等长规划（量长度、找补线区、排蛇形）；报做不到或两轮后仍差得远，换 Fable 重排，不让它反复小修 | 子任务 | Opus | high |
| 给已有基准的工具加功能、改脚本 | 子任务 | Opus | high |
| 按铜皮草图摆器件 | 子任务 | Opus | high |
| 独立复核（规则、网表对手册、交付前检查） | 子任务 | Opus | high |
| 机械性批量改动（文档同步、填表、改名） | 子任务 | Haiku | low |

表里没有的任务，按出错代价就近套一行；拿不准就问用户。

后台同时运行的子任务最多 3 个（用户 2026-11-26 定）。要派的更多时分批：先派 3 个，有一个交回再派下一个。

## Project shape

Current standards, one file per area, rules grouped under titles. Before planning, specifying or changing anything that touches an area, read its file (once split, its index and the title files involved), hand those files to any subagent you start, and raise any Proposed items with the user.
Levels: **exploring** is a bet (follow it, note friction); **provisional** is likely to hold (ask before breaking it); **settled** is proven (enforced).
Add a dated line to the area's Signals when a rule decides part of your change, gets in your way or is broken by code, and when the user corrects you; subagents report these, and you write them. Decisions that should bind the project go through the `shape-your-project` skill: at the end of a grill, wayfinder session or retro, gather them, with repeated corrections, and take them through together.
Area files change only on `main` (the writer branch); on any other branch, write those lines and any drafts to `docs/shape/inbox/<branch>.md` instead. Right after a merge brings an inbox to `main`, drain it through the skill.

- [推进流程](docs/shape/process.md): 阶段顺序、完成标准、回退、审查交接、指标和工具
- [规则与原理图](docs/shape/rules-and-schematic.md): 起工程、确认规则生效、原理图完成标准
- [布局](docs/shape/layout.md): 围着铜皮摆器件，按走线和供电验收
- [电源与铜皮](docs/shape/power-copper.md): 铜皮类网络先规划，外形只用 45°/90°
- [走线](docs/shape/routing.md): 约定、线序、等长、线形、手工和自动的分工
- [收尾](docs/shape/finishing.md): 丝印、泪滴、最后的检查

## Agent skills

### Issue tracker

Issues and specs live as GitHub issues in `immorcoding/PCB` (remote `origin`, public; license CC BY-NC-SA 4.0, see `LICENSE` and `README.md`), through the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default roles, each a GitHub label equal to its name. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root, created only when needed. See `docs/agents/domain.md`.
