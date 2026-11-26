# PCB

用 KiCad 10 做的几块 STM32 板子，以及配套的一套 Python 设计工具。原理图、布局、走线、丝印、DRC 都由脚本从数据文件生成，可以重复构建。

> **实验性项目。** 这些板子主要用来验证设计流程和工具，**都没有打样验证过**，可能有错误。不保证可用，使用后果自负。
>
> **Experimental.** These boards exist to test a design flow and its tools. None has been fabricated or verified; they may contain errors. No warranty of any kind; use at your own risk.

## 板子

| 目录 | 内容 | 层数 | 看点 |
|---|---|---|---|
| [`stm32f411_minsys/`](stm32f411_minsys/) | STM32F411 最小系统板，约 53.6 mm 长，双排针 | 2 | 工具链的第一块板 |
| [`steval_fcu001v2/`](steval_fcu001v2/) | 按 ST 评估板 STEVAL-FCU001V2（小四轴飞控）的原理图重新录入，自己画的 40 × 40 mm 板 | 4 | 整层地、电源层分块 |
| [`stm32h743_sdram/`](stm32h743_sdram/) | STM32H743 BGA（0.65 mm 间距）加 SDRAM | 6 | BGA 扇出、并行总线线序和分组等长、电源层按草图分块；布局和走线做法的范例 |

每块板的目录只放数据：原理图页、`board.toml`、`place.toml`、`silk.toml`、走线描述等；H743 板的设计依据在 [`stm32h743_sdram/SPEC.md`](stm32h743_sdram/SPEC.md)。

## 仓库结构

```
Tools/KiCadDesignTools/   设计工具：原理图生成、布局、总线走线、等长规划、铺铜、检查、构建入口
templates/                新板模板（common 通用、C-bga-065 用于 0.65 mm BGA、demo_board 工具链试验件）
docs/design-rules.md      设计规则的数值，以及和 Altium 规则的对照
docs/rule-profiles/       三套规格档：A 通用、B 0.8 mm BGA、C 0.65 mm 及以下 BGA
docs/shape/               流程和约定：推进流程、规则与原理图、布局、电源与铜皮、走线、收尾
docs/tools.md             KiCad / pcbnew 踩过的坑
```

工具的完整索引见 [`Tools/KiCadDesignTools/README.md`](Tools/KiCadDesignTools/README.md)。

## 使用

需要 KiCad 10（用它自带的 Python，里面有 `pcbnew` 模块）。下面假设 KiCad 装在 `D:\KiCad`，装在别处时设环境变量 `KICAD_BIN` 指向它的 `bin` 目录。命令都在仓库根目录下运行：

```powershell
# 构建一块板的某一步（--dry-run 只打印要执行的命令）
D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.build stm32h743_sdram <步骤> [--dry-run]

# 从模板新建一块板
D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.build init <名字>

# 改了工具或规则文件后，跑全部基准测试
D:\KiCad\bin\python.exe -m Tools.KiCadDesignTools.regress
```

DRC、铺铜、渲染这类重活由构建入口排队，一次只跑一个、限四个核、低优先级。建议不要绕过构建入口直接并行调用 `kicad-cli`。

## 协议 / License

Copyright © 2026 Immor

本仓库的原创内容（原理图、PCB、构建脚本、工具代码、文档）采用 [知识共享 署名-非商业性使用-相同方式共享 4.0 国际](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh-hans)（CC BY-NC-SA 4.0）协议，全文见 [LICENSE](LICENSE)：

- 可以学习、复制、修改，但必须**署名**并注明来源链接；
- **不得用于商业目的**（包括销售板子或成品，或把设计用在商业产品里）；
- 修改后再发布的作品必须使用**相同协议**。

如需商用授权，请先联系作者。

Original content in this repository (schematics, PCB layouts, build scripts, tool code and documentation) is licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). See [LICENSE](LICENSE). For commercial use, contact the author first.

### 例外 / Exceptions

以下第三方内容**不在**上述协议范围内，版权归原作者，按原作者的条款使用：

- `steval_fcu001v2/ref/` 下的 PDF：STMicroelectronics 的文档；
- `steval_fcu001v2/` 的电路（原理图、位号、BOM）：根据 ST 公开的 STEVAL-FCU001V2 资料重新录入，原设计受 ST 的许可条款约束。本仓库只对自己画的 PCB 布局和工具代码授权。

Third-party material listed above is excluded and remains under its owners' terms.
