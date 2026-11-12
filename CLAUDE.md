# PCB 工作区

KiCad 10 硬件设计。分工：Claude 完成原理图、布局、布线；用户（Altium 背景，KiCad 新手）负责审查。交付时附上审查清单，概念用 AD 的对应说法解释。

## 设计规则

规则的唯一来源是 `docs/design-rules.md`（AD `common.RUL` 的迁移对照、取舍原因、已知陷阱）。新建工程、修改规则、布局前定差分参数时先读它。

- **新工程**：复制 `templates/common/` 下的 `common.kicad_pro` / `.kicad_pcb` / `.kicad_dru`，三个改成同一工程名。
- **规则是否生效**：每次新建工程或改动 `.kicad_dru` 后跑金丝雀，输出 `OK` 才算完成：
  `D:\KiCad\bin\python.exe scripts\dru_canary.py <工程>.kicad_pcb`
  KiCad 遇到 `.kicad_dru` 语法错误会静默跳过整个文件，DRC 报告干净不代表规则在工作。

## 改板循环

坐标文件（`.kicad_pcb` / `.kicad_sch`）是 source of truth。每轮：重新读文件 → 修改 → `kicad-cli pcb drc` + kicad-happy 分析 → 渲染图片。图片只做定性判断（拥挤、环路、地平面被割），坐标和尺寸一律从文件读、用脚本算。
分析器的发现先甄别真伪再报给用户（例：金手指被报"离板边太近"属误报）。

## 工具位置

- KiCad 10.0.8：`D:\KiCad\bin\`（`kicad-cli.exe`，带 pcbnew 的 `python.exe`），不在 PATH 上。
- KiCadRoutingTools（布局/自动布线）：`Tools/KiCadRoutingTools/`，独立 git 仓库，已 gitignore。它的脚本和 skill 假定 cwd 是该目录，用 `.venv/Scripts/python.exe -X utf8` 运行。
- kicad-happy（审查/EMC/BOM/JLC）：项目级插件，见 `.claude/settings.json`。SPICE 暂不可用（未装独立 ngspice）。
