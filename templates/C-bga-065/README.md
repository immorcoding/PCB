# 规格档 C 的工程模板（0.65 mm 球距 BGA，六层）

规格档 C（[docs/rule-profiles/C-bga-065.md](../../docs/rule-profiles/C-bga-065.md)）的起点文件，相当于 AD 里的工程模板加一份导入好的 `.RUL`。新板在 `board.toml` 里写 `[board] template = "C-bga-065"`，就从这里起（RUL-1）。2026-11-24 从 H743 板（`stm32h743_sdram/`，本档第一块板）提出来：那块板原来从 `templates/common/` 起，C 档的数值写在它的 `board.toml` 里。

| 文件 | 内容 | `make_project` 怎么用 |
|---|---|---|
| `C-bga-065.kicad_pro` | 本档的板级下限（规则区内的值：线 0.09、间距 0.09、过孔 0.30 / 0.15、焊环 0.075；孔到铜 0.2；按层高算长度打开）、线宽表、过孔表，三个网络类 Default（0.2032，过孔 0.45 / 0.2）、PWR（0.3048，0.6 / 0.3）、XTAL（0.254），PWR 和 XTAL 的按名匹配；其余照 `templates/common/` | 每次都从它重新生成板子的 `.kicad_pro`：再加上 `board.toml` 的总线网络类、差分对、网络类匹配；`[project.floors]`、`track_widths`、`via_dimensions`、同名网络类只在这块板和本档不同时才写 |
| `C-bga-065.kicad_dru` | 本档不分板的 15 条规则：线宽（通用、PWR、晶振）、两个 BGA 规则区的线宽 / 间距 / 小过孔、孔、插件孔间距、拐角、最短线段、铺铜连接。规则区名写的是 `BGA_MCU`、`BGA_SDRAM` | 板子还没有规则文件时复制一份，以后是板子自己的，手改，不再覆盖；每次检查这 15 条的名字在板子的规则文件里都还在，缺的列出来（警告，板子可能有意删掉）。H743 板的规则文件不是从这里生成的，15 条和它同名的规则逐条相同，`make_project` 报“holds every rule name” |
| `C-bga-065.kicad_pcb` | 六层空板：层序信号 / 地 / 信号 / 信号 / 电源 / 信号（H743 板的层用途和层名），嘉立创 JLC06161H-3313E 的叠层真值 | 新板或 `--new-pcb` 时从它生成空板：铜层表换成 `board.toml` 的 `[layers]`，叠层换成 `[board] stackup` 的；已有的板只改铜层表 |
| `meta/info.html` | KiCad 模板选择器里的说明 | 不用；在 KiCad 里“从模板新建”时能看到 |

不在模板里的（按板定，写进板子的 `SPEC.md` 和 `board.toml`）：总线网络类、差分对的线宽和间距、长度和等长规则、过孔数规则、规则区的名字和范围、例外（RUL-5）。

## 本板取值和数据源

规格档“布局和走线的取值”表里的每一项，每块板在 `SPEC.md` 的“本板取值”表里给出值或“不适用”（样板：[templates/demo_board/SPEC.md](../demo_board/SPEC.md) 第 7.2 节）。`python -m Tools.KiCadDesignTools.project.spec_check <板目录>` 检查这张表齐不齐；“数据源”一栏写了文件的，再把 SPEC 的值和文件里的值对一遍，不一致就失败。构建的 layout 一步先跑它，退出 1 就停。`SPEC.md` 早于这张表的板（H743）在 `board.toml` 写 `[board] spec_table = false`，只警告。

同一个数在 SPEC 和数据文件里各有一份，只能有一个为准，另一份由 `spec_check` 对着查。原则：SPEC 为准（PROC-8：文件为准，用户批的是它），数据文件是工具读的副本；规则文件管的数例外，以规则文件为准（RUL-1：规则值写在规则文件里），SPEC 那一行是抄给人看的。逐项：

| 项目 | 为准的一份 | `spec_check` 对着查的副本 | 说明 |
|---|---|---|---|
| 信号层数（各层用途） | SPEC | `board.toml:layers.roles` | `make_project` 和所有工具按 `roles` 认层 |
| 小去耦到电源球的距离上限 | SPEC | — | 工具里是 `place_check --limit` 的默认值 2.5 和 `copper_table` 的常数 2.5（代码，不是数据文件），没有接到 SPEC |
| BGA 背面去耦的封装 | SPEC | — | 原理图页按它选封装，没有单独的数据 |
| 蛇形腿中心距（每类一行） | SPEC | 走线文件 `TUNING.pitch`（`default` 是数据线，按网络名的是时钟） | busroute 的蛇形按 `TUNING` 画 |
| 蛇形起始摆幅 | SPEC | 走线文件 `TUNING.amp` | |
| 蛇形块两头的直线 | SPEC | 走线文件 `TUNING.keep` | |
| 数据线组内等长（每组一行） | 规则文件 `<组>.skew.max` | SPEC | 规则 `sdram_lane0` 一类；走线文件 `TUNING` 里的 `spread` 是排线目标，不是容差，不比 |
| 地址命令对时钟 | `length_groups.json` 的窗口 `lo` / `hi` | SPEC；走线文件 `TUNING.groups.addr.hi` | `len_rules` 按 `length_groups.json` 生成规则文件里的窗口规则 |
| 过孔数上限：哪些线 | 规则文件（`sdram_via_max` 的条件） | — | 文字，不比 |
| 过孔数上限：个数 | 规则文件 `sdram_via_max.via_count.max` | SPEC；走线文件 `VIA_LIMIT` | |
| 电源层块间的缝 | SPEC | `copper.sketch:gap` | `cu_sketch` 按草图的参数生成铺铜区 |
| 外层铺铜最小铜宽 | SPEC | `copper.sketch` 铺地区的 `minwidth`（和局部铜皮的默认 `minwidth`） | |
| 平面上过孔避让连成的槽 | SPEC | — | “不设上限”；`[copper.slots] report` 只是列出的门槛，不是上限 |

改值的顺序：先改为准的一份（SPEC 的“已定”项先问用户），再改副本，`spec_check` 通过才算改完。
