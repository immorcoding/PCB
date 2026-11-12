# PCB 工作区

KiCad 10 硬件设计。分工：Claude 完成原理图、布局、布线；用户（Altium 背景，KiCad 新手）负责审查。交付时附上审查清单，概念用 AD 的对应说法解释。

## 流程

下面是一块双层测试板（`stm32f411_minsys/`，2026-11-12）走通的顺序，当作起点。层数、板厂、密度不同的板子，先和用户确认哪些步骤和约定要调整；四层及以上还没有实测经验，遇到和这里不符的情况以实际为准，做完后回来更新这一节。

阶段之间交给用户审查；分支和提交按用户当时的要求来。

1. **方案**：器件选型、接口、板型、叠层列成选项给用户定。没有规格书可核对的引脚和参数记入"未核对项"，一直带到交付。
2. **规则**：从 `templates/common/` 起工程，按板厂和层数加工程级覆盖。完成标准：金丝雀输出 `OK`。
3. **原理图**：完成标准是 ERC 干净、导出的网表逐网络核对过。排针和连接器的引脚分配对照布局草图定（测试板的两排电源脚放在了对角，结果 +5V 绕板一圈）。
4. **布局**：坐标写在工程的 `place.py`。交审查前先试走关键网络（晶振、高速差分、电源主干、去耦），把试走暴露的问题在这一阶段改掉（测试板走线中途改了 5 处布局）。
5. **走线**：动手前和用户定各层的用途和约定，能量化的给出数字（例：双层板底层允许走哪些网络、总长多少）。走线中发现约定守不住、或需要改规则和布局时，当场告诉用户原因和数字。完成标准：`kicad-cli pcb drc --refill-zones --severity-all` 未连接为 0，剩余项逐条有解释。
6. **收尾**：地过孔、丝印位号、泪滴、渲染图，然后带 `--schematic-parity` 重跑 DRC、重跑金丝雀、甄别 kicad-happy 的发现。
7. **交付**：审查清单写明 DRC 剩余项、没守住的约定及数字、过程中改过的规则和布局、未核对项、图片路径；提醒用户在 KiCad 里"文件 → 还原"重新载入。

提交前核对板文件里的走线数和未连接数与刚报告的一致（提交过一次没有走线的板子）。

## 设计规则

规则的唯一来源是 `docs/design-rules.md`（AD `common.RUL` 的迁移对照、取舍原因、已知陷阱、板厂覆盖）。新建工程、修改规则、布局前定差分参数时先读它。

- **新工程**：复制 `templates/common/` 下的 `common.kicad_pro` / `.kicad_pcb` / `.kicad_dru`，三个改成同一工程名。
- **规则是否生效**：每次新建工程或改动 `.kicad_dru` 后跑金丝雀，输出 `OK` 才算完成：
  `D:\KiCad\bin\python.exe scripts\dru_canary.py <工程>.kicad_pcb`
  KiCad 遇到 `.kicad_dru` 语法错误会静默跳过整个文件，DRC 报告干净不代表规则在工作。
- **用户开着 KiCad 时改 `.kicad_pro` 会丢**：KiCad 关闭工程时用内存里的旧设置覆盖文件（2026-11-12 丢过一次 USB2 网络类）。改完网络类/规则后，在用户下次关闭 KiCad 之后重新读回核对；工程目录下有 `~*.lck` 说明 KiCad 正开着。

## 原理图

没有现成的原理图生成工具，用 `scripts/kisch.py`（从官方符号库取符号、按引脚坐标连线）。每个工程一个 `gen_sch.py`，参考 `stm32f411_minsys/gen_sch.py`。
构建并检查：`sh scripts/sch_build.sh <工程目录> <输出目录>`（生成 → 升级到 KiCad 10 格式 → ERC → 网表 → PDF）。
连接关系以导出的网表为准；版面用 `pdftoppm -r 200 -png -x -y -W -H` 裁剪放大看文字重叠。
用户在 KiCad 里手工改过原理图之后，`.kicad_sch` 是 source of truth，不要再跑 `gen_sch.py` 覆盖。

## 改板循环

坐标文件（`.kicad_pcb` / `.kicad_sch`）是 source of truth。每轮：重新读文件 → 修改 → `kicad-cli pcb drc` + kicad-happy 分析 → 渲染图片。图片只做定性判断（拥挤、环路、地平面被割），坐标和尺寸一律从文件读、用脚本算。
分析器的发现先甄别真伪再报给用户（例：金手指被报"离板边太近"属误报）。

## 走线

`scripts/` 下的工具：`net2pcb.py`（网表进板）、`pcb_view.py`（带走线和飞线的示意图）、`via_spots.py`（找合法过孔位置）、`silk_refs.py`（整理位号）、`teardrops.py`（泪滴）。用法见各文件开头。

双层板上的做法（参考 `stm32f411_minsys/route.py`）：关键网络写进工程的 `route.py` 手工走，其余 GPIO 交给 KiCadRoutingTools，最后清理拐角。原因是布线器不认识拐角规则，也不会少用底层，全板交给它得不到合规结果；密的地方它还会走不通（测试板 30 根 GPIO 只走通 13 根），剩下的用坐标脚本补。有内层平面的板子这个分工是否还合适，要重新试。

- **pcbnew 的坑**：`board.Remove()` 之后，同一进程里 `board.Zones()`、`GetFootprints()` 等集合会返回无类型对象，访问即报错或崩溃。先读完需要的数据再删；删完要继续用就另存、重新 `LoadBoard`（另存到临时目录，别覆盖工程文件）。
- **铺铜以 KiCad 自己的填充为准**：`kicad-cli pcb drc --refill-zones` 的未连接数才算数。
- **泪滴**：Python API 不暴露泪滴参数，用 `scripts/teardrops.py <板>`（写入文件后由 `kicad-cli` 生成），放在走线和铺铜定稿之后。

## 工具位置

- KiCad 10.0.8：`D:\KiCad\bin\`（`kicad-cli.exe`，带 pcbnew 的 `python.exe`），不在 PATH 上。
- KiCadRoutingTools（布局/自动布线）：`Tools/KiCadRoutingTools/`，独立 git 仓库，已 gitignore。它的脚本和 skill 假定 cwd 是该目录，用 `.venv/Scripts/python.exe -X utf8` 运行。
- kicad-happy（审查/EMC/BOM/JLC）：项目级插件，见 `.claude/settings.json`。SPICE 暂不可用（未装独立 ngspice）。
