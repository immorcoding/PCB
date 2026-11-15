# PCB 工作区

KiCad 10 硬件设计。分工：Claude 完成原理图、布局、布线；用户（Altium 背景，KiCad 新手）负责审查。交付时附上审查清单，概念用 AD 的对应说法解释。

已做完的板子：`stm32f411_minsys/`（双层）、`steval_fcu001v2/`（四层，40 × 40 mm）。

## 去哪里找什么

- **该怎么做**（流程、验收标准、约定）：`docs/shape/`，见下面的 Project shape。
- **规则的数值**（和 AD 的对照、规则文件的坑）：[docs/design-rules.md](docs/design-rules.md)；按板型分的三套规格档（A 通用、B 0.8 mm BGA、C 0.65 mm 及以下 BGA）在 `docs/rule-profiles/`。
- **工具的命令、用法和坑**：[docs/tools.md](docs/tools.md)。

KiCad 10.0.8 在 `D:\KiCad\bin\`（`kicad-cli.exe`，带 pcbnew 的 `python.exe`），不在 PATH 上。

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

Issues and specs live as markdown files under `.scratch/<feature>/`, tracked in git. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default roles, each label equal to its name, written on the `Status:` line of the issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root, created only when needed. See `docs/agents/domain.md`.
