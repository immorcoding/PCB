# 规则与原理图

工程怎么起、设计规则怎么确认生效、原理图怎样算做完。规则的数值、和 AD 的对照、板厂覆盖值在 [design-rules.md](../design-rules.md)；命令和工具的坑在 [tools.md](../tools.md)。

Next id: RUL-13

## Pillars

- DRC 报告干净不等于规则在工作；规则生效要单独证明。
- 连接关系以导出的网表为准，不以图为准。

## design-rules

工程级规则的建立、覆盖和例外。

### Rules

- **RUL-1** · provisional · 新工程从所选规格档的模板起（A 档是 `templates/common/` 加板厂覆盖）；规则值只写在 `docs/design-rules.md`、`docs/rule-profiles/` 和工程的规则文件里，别处不重复。 _Why:_ 模板保留 AD `common.RUL` 的原值，板厂和层数的差异放在工程里才看得出改了什么。
- **RUL-11** · exploring · 方案阶段选定规格档（`docs/rule-profiles/`）；没有合适的就先新建一档交用户批准，不从低一档的数值改起。 _Why:_ 给四层板加的过孔下限 0.45 mm 被带到下一块板上，把用户原本够用的 0.8 mm BGA 规则挤过了临界点；六层废弃板的规则是边做边叠出来的。
- **RUL-12** · exploring · 用到 BGA 或更密封装的板子，规则阶段先按球距列计算表（焊盘间过线、球间过孔、孔到焊盘、过孔间过线、孔到线），和板厂下限对照得出需要的例外；例外在布局开始前定完。 _Why:_ 六层废弃板上规则区、小过孔、区内线宽都是走线中途加的。
- **RUL-2** · provisional · 新建工程或改动 `.kicad_dru` 之后跑金丝雀（`scripts/dru_canary.py`），输出 `OK` 才算完成。 _Why:_ `.kicad_dru` 有任何语法错误，KiCad 会静默跳过整个文件，DRC 照常输出。
- **RUL-3** · provisional · 布局前按板厂的叠层数据算差分阻抗，为每种接口建网络类并填线宽和间距。 _Why:_ 模板里故意没填；阻抗取决于叠层。
- **RUL-4** · provisional · 改了 `.kicad_pro`（网络类、规则）之后，在用户下次关闭 KiCad 之后重新读回核对。 _Why:_ KiCad 关闭工程时用内存里的旧设置覆盖文件，丢过一次 USB2 网络类。
- **RUL-5** · exploring · 规则的例外（盘中孔、更小的过孔、扩大规则区）先问用户，批准后写进规则文件并注明日期和原因。 _Why:_ 六层废弃板上把 BGA 规则区向外扩 4 mm 是自己定的，超出了用户批准的范围。

## schematic

原理图的完成标准和约定。

### Rules

- **RUL-6** · provisional · 原理图的完成标准：ERC 干净，导出的网表逐网络核对过；大芯片的引脚对照官方引脚表用脚本比。 _Why:_ 图上看着连了不等于网表里连了。
- **RUL-7** · provisional · 排针和连接器的引脚分配对照布局草图定。 _Why:_ 双层板的两排电源脚放在了对角，+5V 绕板一圈。
- **RUL-9** · exploring · 原理图的完成标准里还包括：跑 kicad-happy 的 `kicad` skill 做原理图审查（电源树、稳压电路、网络追踪），发现逐条甄别真伪后再报给用户。 _Why:_ 六层废弃板上一次都没用过它，引脚核对是自己写脚本做的；它原来只排在收尾阶段。
- **RUL-10** · exploring · 方案和原理图阶段，有规格书 PDF 的器件用 kicad-happy 的 `datasheets` skill 提取引脚和电气参数来核对，核对不了的才记入"未核对项"。 _Why:_ 手工读规格书慢，也容易漏；未核对项越少，交付时用户要查的越少。
- **RUL-8** · provisional · 写进原理图的文字不带没转义的换行；符号坐标落在 1.27 mm 网格上。 _Why:_ 带换行的文字会让同一页后面的标签全部连不上；不在网格上每个端点报一条 `endpoint_off_grid`。

## Signals

- 2026-11-15 · RUL-5、RUL-11、RUL-12 · H7 测试板的地图里单独设了"定 BGA 区的规则例外"一张票，排在方案定稿之前（[地图](https://github.com/immorcoding/PCB/issues/1)）。
- 2026-11-15 · RUL-6 · 起作用：没有 ST 官方板用 UFBGA176+25 的 H743，MCU 符号的引脚表只能对照规格书 DS12110 的球表，不能照抄官方板的球号（[调研票](https://github.com/immorcoding/PCB/issues/4)）。
- 2026-11-15 · RUL-12 · 起作用：规格档里假设的焊盘直径和规格书对不上。UFBGA176+25 规格书推荐 0.30 mm（规格档 C 按 0.35 mm），90 球 SDRAM 只有 Micron 给了推荐值 0.33 mm（规格档 B 按 0.4 mm）；计算表要按规格书的焊盘重算（[调研票](https://github.com/immorcoding/PCB/issues/4)、[调研票](https://github.com/immorcoding/PCB/issues/3)）。
- 2026-11-15 · RUL-10 · 没用上：调研 agent 读 ST 原理图和球图时没用 `datasheets` skill，用的是 pdftotext 加渲染图；引脚级的核对留在了未核对项里（[调研票](https://github.com/immorcoding/PCB/issues/4)）。
- 2026-11-15 · RUL-3 · 碍事：嘉立创阻抗计算器是浏览器渲染、结果走后台接口，agent 驱动不了；调研里的 50 Ω / 90 Ω 线宽是按叠层数据自己算的，走线前还要人工在计算器上过一遍（[调研票](https://github.com/immorcoding/PCB/issues/5)）。
- 2026-11-15 · RUL-5、RUL-12 · 起作用：嘉立创对低于 3.5 mil 的线和 0.15 mm 的孔加价，元件孔到铜（0.28 / 0.3 mm）和过孔（0.2 mm）不是一个值，BGA 区阻焊扩展要为 0；这些都是规格档 C 没写、要在布局前定的例外或计算表输入（[调研票](https://github.com/immorcoding/PCB/issues/5)）。
- 2026-11-15 · RUL-10 · 又没用上：MCU 和 SDRAM 两张调研票也没用 `datasheets` skill，理由是跨规格书比球图时还没有 KiCad 工程可挂缓存，都是用脚本读 PDF（[调研票](https://github.com/immorcoding/PCB/issues/2)、[调研票](https://github.com/immorcoding/PCB/issues/3)）。方案阶段还没有工程时这条规则怎么执行，没有写明。
- 2026-11-16 · RUL-10 · 第三次没用上：QSPI Flash 的调研也没用 `datasheets` skill，用的是 pdftotext 加渲染图；这次我给调研 agent 的指示里写了"读 PDF 用现成的命令"，等于把它引开了，同样没有工程可挂缓存（[决定票](https://github.com/immorcoding/PCB/issues/7)）。
- 2026-11-15 · RUL-11、RUL-5 · 待定：规格档 C 的计算表按 0.30 mm 焊盘重算后余量变了，还多出阻焊开窗 0.38 mm、0.15 mm 孔加价、背面去耦过孔位置三项要用户批准的例外；是改规格档 C 还是新建一档，留给"定 BGA 区的规则例外"那张票（[调研票](https://github.com/immorcoding/PCB/issues/6)）。
- 2026-11-16 · RUL-12、RUL-5、RUL-11 · 起作用：H7 测试板的两张球距计算表在方案阶段列完，七项例外逐项经用户批准；沿用规格档 C 并按规格书焊盘改写，没有新建一档。计算表还暴露出 0.8 mm 的 SDRAM 按区外值过孔间过不了线（差 0.006 mm），也要画规则区（[决定票](https://github.com/immorcoding/PCB/issues/10)）。
- 2026-11-16 · RUL-10 · 第四次没用上：外设调研也没用 `datasheets` skill，调研 agent 的技能列表里没有它，也没有工程可挂缓存；Microchip、Nexperia 官网对自动下载返回 403，四份规格书没拿到，记入未核对项（[调研票](https://github.com/immorcoding/PCB/issues/8)）。这条规则在方案阶段的调研票上至今一次没执行成。
- 2026-11-16 · RUL-10 · 第五次没用上：这次两个调研 agent 的技能列表里都有 `kicad-happy:datasheets`，也都加载了，但都没跑它的提取流程。理由是：它是"本地 PDF 提取并缓存到工程"的流水线，不管下载；固定的提取结构不含 I2C 地址、各模式电流、在产状态；方案阶段没有工程目录可挂缓存。两个 agent 都改用 pdftotext 加渲染图，并给了页码（[决定票](https://github.com/immorcoding/PCB/issues/9)）。这条规则在方案阶段该怎么执行，仍然没有写明。
- 2026-11-16 · RUL-6 · 提前起作用：SAI1、I2C4 的七个脚和套 A 原有 108 个脚的球号，在方案阶段就对照 DS12110 的引脚表用脚本比过；AF 编号只重核了新增的七个脚，其余留在未核对项。
- 2026-11-16 · RUL-7 · 相关：12 个辅助脚里除 SWO、背光 PWM、按键外都是普通 GPIO，和用户约定布局时可以在空脚间调换、换了当场报告；连接器位置仍在地图的迷雾里。
