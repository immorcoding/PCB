# 规则与原理图

工程怎么起、设计规则怎么确认生效、原理图怎样算做完。规则的数值、和 AD 的对照、板厂覆盖值在 [design-rules.md](../design-rules.md)；命令和工具的坑在 [tools.md](../tools.md)。

Next id: RUL-9

## Pillars

- DRC 报告干净不等于规则在工作；规则生效要单独证明。
- 连接关系以导出的网表为准，不以图为准。

## design-rules

工程级规则的建立、覆盖和例外。

### Rules

- **RUL-1** · provisional · 新工程从 `templates/common/` 的三个文件起，按板厂和层数加工程级覆盖；规则值只写在 `docs/design-rules.md` 和工程的规则文件里，别处不重复。 _Why:_ 模板保留 AD `common.RUL` 的原值，板厂和层数的差异放在工程里才看得出改了什么。
- **RUL-2** · provisional · 新建工程或改动 `.kicad_dru` 之后跑金丝雀（`scripts/dru_canary.py`），输出 `OK` 才算完成。 _Why:_ `.kicad_dru` 有任何语法错误，KiCad 会静默跳过整个文件，DRC 照常输出。
- **RUL-3** · provisional · 布局前按板厂的叠层数据算差分阻抗，为每种接口建网络类并填线宽和间距。 _Why:_ 模板里故意没填；阻抗取决于叠层。
- **RUL-4** · provisional · 改了 `.kicad_pro`（网络类、规则）之后，在用户下次关闭 KiCad 之后重新读回核对。 _Why:_ KiCad 关闭工程时用内存里的旧设置覆盖文件，丢过一次 USB2 网络类。
- **RUL-5** · exploring · 规则的例外（盘中孔、更小的过孔、扩大规则区）先问用户，批准后写进规则文件并注明日期和原因。 _Why:_ 六层废弃板上把 BGA 规则区向外扩 4 mm 是自己定的，超出了用户批准的范围。

## schematic

原理图的完成标准和约定。

### Rules

- **RUL-6** · provisional · 原理图的完成标准：ERC 干净，导出的网表逐网络核对过；大芯片的引脚对照官方引脚表用脚本比。 _Why:_ 图上看着连了不等于网表里连了。
- **RUL-7** · provisional · 排针和连接器的引脚分配对照布局草图定。 _Why:_ 双层板的两排电源脚放在了对角，+5V 绕板一圈。
- **RUL-8** · provisional · 写进原理图的文字不带没转义的换行；符号坐标落在 1.27 mm 网格上。 _Why:_ 带换行的文字会让同一页后面的标签全部连不上；不在网格上每个端点报一条 `endpoint_off_grid`。
