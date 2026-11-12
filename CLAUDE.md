# PCB 工作区

KiCad 10 硬件设计。分工：Claude 完成原理图、布局、布线；用户（Altium 背景，KiCad 新手）负责审查。交付时附上审查清单，概念用 AD 的对应说法解释。

## 设计规则

规则的唯一来源是 `docs/design-rules.md`（AD `common.RUL` 的迁移对照、取舍原因、已知陷阱）。新建工程、修改规则、布局前定差分参数时先读它。

- **新工程**：复制 `templates/common/` 下的 `common.kicad_pro` / `.kicad_pcb` / `.kicad_dru`，三个改成同一工程名。
- **规则是否生效**：每次新建工程或改动 `.kicad_dru` 后跑金丝雀，输出 `OK` 才算完成：
  `D:\KiCad\bin\python.exe scripts\dru_canary.py <工程>.kicad_pcb`
  KiCad 遇到 `.kicad_dru` 语法错误会静默跳过整个文件，DRC 报告干净不代表规则在工作。
- **用户开着 KiCad 时改 `.kicad_pro` 会丢**：KiCad 关闭工程时用内存里的旧设置覆盖文件（2026-11-12 丢过一次 USB2 网络类）。改完网络类/规则后，在用户下次关闭 KiCad 之后重新读回核对；工程目录下有 `~*.lck` 说明 KiCad 正开着。

## 原理图

没有现成的原理图生成工具，用 `scripts/kisch.py`（从官方符号库取符号、按引脚坐标连线）。每个工程一个 `gen_sch.py`，参考 `stm32f411_minsys/gen_sch.py`。
构建并检查：`sh scripts/sch_build.sh <工程目录> <输出目录>`（生成 → 升级到 KiCad 10 格式 → ERC → 网表 → PDF）。
连接关系以导出的网表为准，逐网络核对；版面用 `pdftoppm -r 200 -png -x -y -W -H` 裁剪放大看文字重叠。
用户在 KiCad 里手工改过原理图之后，`.kicad_sch` 是 source of truth，不要再跑 `gen_sch.py` 覆盖。

## 改板循环

坐标文件（`.kicad_pcb` / `.kicad_sch`）是 source of truth。每轮：重新读文件 → 修改 → `kicad-cli pcb drc` + kicad-happy 分析 → 渲染图片。图片只做定性判断（拥挤、环路、地平面被割），坐标和尺寸一律从文件读、用脚本算。
分析器的发现先甄别真伪再报给用户（例：金手指被报"离板边太近"属误报）。

## 走线

自动布线器（KiCadRoutingTools）不认识拐角规则，也不会少用底层：全板交给它得不到合规结果（2026-11-12 实测）。做法是混合：关键网络（晶振、USB、电源、去耦、GND、必须换层的控制线）写成工程里的 `route.py` 手工走，其余 GPIO 再交给布线器，最后清理拐角。参考 `stm32f411_minsys/route.py`。

- **pcbnew 的坑**：`board.Remove()` 之后，同一进程里 `board.Zones()`、`GetFootprints()` 等集合会返回无类型对象，访问即报错或崩溃。先读完需要的数据再删；删完要继续用就另存、重新 `LoadBoard`（另存到临时目录，别覆盖工程文件）。
- **铺铜以 KiCad 自己的填充为准**：`kicad-cli pcb drc --refill-zones` 的未连接数才算数。
- **泪滴**：Python API 不暴露泪滴参数，用 `scripts/teardrops.py <板>`（写入文件后由 `kicad-cli` 生成），放在走线和铺铜定稿之后。

## 工具位置

- KiCad 10.0.8：`D:\KiCad\bin\`（`kicad-cli.exe`，带 pcbnew 的 `python.exe`），不在 PATH 上。
- KiCadRoutingTools（布局/自动布线）：`Tools/KiCadRoutingTools/`，独立 git 仓库，已 gitignore。它的脚本和 skill 假定 cwd 是该目录，用 `.venv/Scripts/python.exe -X utf8` 运行。
- kicad-happy（审查/EMC/BOM/JLC）：项目级插件，见 `.claude/settings.json`。SPICE 暂不可用（未装独立 ngspice）。
