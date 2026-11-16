# QSPI NOR Flash 选型调研（WSON-8，3.3 V，单颗四线）

日期 2026-11-16。问题：六层测试板（STM32H743IIK6 + IS42S32800J-6BLI 32 位 SDRAM）要外挂一颗 QSPI NOR Flash：单颗、Quad SPI（CLK、NCS、IO0–IO3 共 6 个信号）、WSON-8、3.3 V；只做设计验证，不看库存和价格，优先 Micron，其次 Winbond、Macronix、ISSI。页码都是 PDF 页码（不是页脚印的页码；Winbond 和 Micron 镜像的页脚页码比 PDF 页码小 0–1）。

## 0. 结论

- **推荐 Micron MT25QL128ABA1EW9-0SIT**：128 Mbit，3 V（2.7–3.6 V），W-PDFN-8 **8 × 6 mm**，1.27 mm 间距，STR 模式最高 133 MHz。**条件：生命周期我没能核实**（Micron 官网的零件页是 JS 渲染，读不到状态；Micron 2026-01 的停产通知 PCN 36228 打不开，搜索摘要说它列了同系列的 MT25QL256ABA1EW7-0SIT 和 MT25QL512ABB8ESF-0SIT，128 Mbit 在不在里面不知道）。订货前请在浏览器里打开 Micron 零件页确认状态，见 §4.1。
- **备选 1：Winbond W25Q128JVEIQ**（WSON-8 8 × 6）。EP 尺寸和 Micron 的完全一样，QE 位出厂固定为 1（QUADSPI 不用先写状态寄存器）。ST 官方的社区文章把它和 Micron 这颗同列为 STM32F746G-DISCO 上用过的 128 Mbit QSPI NOR。注意：2025-02 的新版规格书（Rev D）只列了 `…IM`（QE = 0，要软件置位），`…IQ` 只在 2021 年的 Rev I 里；`IQ` 现在还订不订得到我没核实。
- **备选 2：Macronix MX25L12833FZ2I-10G**（WSON-8 8 × 6）。规格书是 2026-09-01 的 Rev 1.1，三家里最新。EP 比另两家大（4.7 × 4.6 mm），默认 Quad IO 读只有 84 MHz，要 133 MHz 需配 10 个 dummy 周期且 VCC ≥ 3.0 V。
- **三家 8 × 6 的 8 个引脚定义逐脚相同**（1 CS、2 IO1、3 IO2、4 GND、5 IO0、6 CLK、7 IO3、8 VCC），间距 1.27 mm，引脚长宽在公差内重合。**8 × 6 与 6 × 5 是两种不同的封装，焊盘不互通。** 同一尺寸内，外围 8 个焊盘兼容，只有中间的散热焊盘（EP）尺寸各家不同；EP 在三家里都不接内部信号，可以悬空或接地，所以一个封装能装三家的料（§3）。
- **选 8 × 6 而不是 6 × 5 的理由**：8 × 6 里 Micron 与 Winbond 的 EP 完全相同（3.4 × 4.3 mm），KiCad 官方库有现成的匹配封装；6 × 5 里三家的 EP 各不相同（3.0 × 3.0、3.4 × 4.3、3.4 × 4.0）。代价是占板面积大（48 mm² 对 30 mm²）。6 × 5 三家都有（`MT25QL128ABA1EW7-0SIT`、`W25Q128JVPIQ`、`MX25L12833FZNI-10G`），布局放不下再换。这是个尺寸选项，由你定（PROC-8）。
- **H743 的 QUADSPI Bank1 在 UFBGA176+25 上每个信号有 2–3 个可选引脚（§7），与 32 位 SDRAM 的 57 个 FMC 引脚没有任何直接冲突。** 只有一处要避开：PB6（NCS 的备选）同时是 FMC_SDNE1，SDRAM 若用第 2 个 bank 就不能用它。ST 自己的 H7 板用的组合（PF6/PF7/PF8 或 PD11/PF9/PF10/PG6/PB2）都在表里。
- **ST 的 H7 官方板没有一块用「单颗 WSON-8」的 QSPI Flash**：H743I-EVAL、H753I-EVAL、H745I-DISCO、H750B-DK 都是双颗（两个 512 Mbit，或一个 1 Gbit 双 die），料号是 Micron MT25QL512ABB8ESF-0SIT / MT25TL01GHBB8ESF-0SIT（SO16 封装，按料号规则推断）；H735G-DK 是单颗 Macronix MX25LM51245G，但它是 Octo-SPI，不是 QSPI。

## 1. 怎么查的

| 资料 | 取得方式 | 读到的程度 |
|---|---|---|
| STM32H743 规格书 [DS12110 Rev 11][ds-h743]（2026-01，357 页） | `curl` 访问 st.com 返回 HTTP 567（反爬挑战页），**没有绕过**；改用 WebFetch 工具，st.com 直接给出了 PDF（6.7 MB）。`pdftotext` 转文字，表格页用 `pdftoppm` 转图看 | Table 9、Table 10、QUADSPI 时序表逐项读过 |
| Winbond W25Q128JV [Rev D][ds-w25q-d]（2025-02-04）和 [Rev I][ds-w25q-i]（2021-08-23） | `curl` 从 winbond.com 下载，成功 | 封装、引脚、订货号、时钟、QE 位读过原文；封装图看了图 |
| Macronix [MX25L12833F Rev 1.1][ds-mx]（2026-09-01） | `curl` 从 mxic.com.tw（Macronix 自己的域名）下载，成功 | 封装、引脚、订货号、AC 表、Table 1 读过原文，图都看了 |
| Micron MT25QL128ABA 规格书（[LCSC 镜像][ds-mt-mirror]） | Micron 官网的规格书链接已失效（KiCad 库里引用的 URL 返回 404）。读的是 LCSC 的镜像（`atta.szlcsc.com`），文件页眉写 `Rev. K 04/19`，**不是官网下载，也未必是最新版** | 订货号规则、引脚、两种 W-PDFN 封装图、VCC、时钟读过原文 |
| ISSI | `www.issi.com` 返回 Incapsula 反爬页，**没有绕过** | 只有搜索摘要，全部未核实 |
| [Micron 零件页][pg-mt]、[Macronix 零件页][pg-mx]、[Winbond 零件页][pg-winbond] | 页面能下载（HTTP 200），但状态、规格是 JS 加载，静态页里没有。Micron 页面自己调用的数据接口，我试了一次，被权限系统拦下，没有重试，也没有换别的办法去取 | 生命周期、IBIS 都读不到 |
| [Micron PCN 36228][pcn-36228] | `mouser.com` 连接超时（`curl` 两次、WebFetch 一次），`media.digikey.com` 的路径 404 | 没读到，只有搜索摘要 |
| ST 官方板：[UM2198][um2198]、[UM2488][um2488] | WebFetch 下载 ST 的 PDF，转文字读 | 正文读过，两份手册都没有写 Flash 的订货号 |
| ST 官方板的 BSP 头文件（[H743I-EVAL][bsp-h743i]、[H750B-DK][bsp-h750b]、[H745I-DISCO][bsp-h745i]、[H735G-DK][bsp-h735g]）、[ST 社区文章][st-kb] | WebFetch 读 ST 官方 GitHub 的 raw 文件和 community.st.com 的页面，**读法是 WebFetch 的摘要**（小模型提取），不是我逐行读的原文 | 来源是一手，读法是摘要，见 §5、§9 |
| KiCad 10.0.8 库 | 直接解析 `D:\KiCad\share\kicad\` 下的 `.kicad_sym`、`.kicad_mod` | 名字、焊盘坐标、引脚名读过 |
| FMC 引脚表 | [`origin/research/h7-ufbga176-mcu` 的 §4][prev-h7]（那份调研的结论，不是一手） | 冲突检查时我又对着 DS12110 Table 10 看了每个 QUADSPI 备选引脚的 AF12 列，见 §7 |

没有写新工具：转文字、转图用 `pdftotext`、`pdftoppm`，查 KiCad 库用一次性的内联 Python（读符号文件，没有落成文件）。没有调用 kicad-happy 的 `datasheets` skill（原因见 §9）。

下文标记：**[V]** 读过厂商自己域名下的原文；**[M]** 读过原文但文件是第三方镜像；**[S]** 只有搜索摘要、WebFetch 摘要或经销商页面；**[I]** 我的推断。

## 2. 对比表

三家都按 8 × 6 mm 的订货号列。6 × 5 mm 的订货号在 §3。

| 项 | Micron MT25QL128ABA1EW9-0SIT | Winbond W25Q128JVEIQ | Macronix MX25L12833FZ2I-10G | ISSI IS25LP128F-JKLE |
|---|---|---|---|---|
| 容量 | 128 Mbit [M] | 128 Mbit [V] | 128 Mbit [V] | 128 Mbit [S] |
| 封装 | W-PDFN-8 8 × 6（Micron 又叫 MLP8），代码 W9 [M] | WSON-8 8 × 6，封装代码 E [V] | 8-land WSON 8 × 6，后缀 Z2 [V] | WSON-8 6 × 5（后缀 JK，未核实）[S] |
| 引脚间距 | 1.27 mm [M] | 1.27 mm [V] | 1.27 mm [V] | 1.27 mm 未核实 |
| 散热焊盘（EP） | 有，3.4 × 4.3 mm，内部接 VSS [M] | 有，3.4 × 4.3 mm，不接内部信号 [V] | 有，4.7 × 4.6 mm，要悬空或接 GND [V] | 未核实 |
| 引脚 | 1 S#、2 DQ1、3 W#/DQ2、4 VSS、5 DQ0、6 C、7 DQ3/HOLD#、8 VCC [M] | 1 /CS、2 DO(IO1)、3 /WP(IO2)、4 GND、5 DI(IO0)、6 CLK、7 /HOLD 或 /RESET(IO3)、8 VCC [V] | 1 CS#、2 SO/SIO1、3 WP#/SIO2、4 GND、5 SI/SIO0、6 SCLK、7 RESET#/SIO3、8 VCC [V] | 未核实 |
| 电压 | 2.7–3.6 V [M] | 2.7–3.6 V；133 MHz 需 3.0–3.6 V [V] | 2.7–3.6 V；Quad IO 133 MHz 需 3.0–3.6 V [V] | 2.3–3.6 V [S] |
| 最高时钟 | 133 MHz（STR，所有命令）；90 MHz（DTR）[M] | 133 MHz（3.0–3.6 V）；104 MHz（2.7–3.0 V）；DTR 66/52 MHz [V] | 封面 133 MHz；默认 Quad IO 读 84 MHz，8 个 dummy 104 MHz，10 个 dummy 133 MHz（VCC ≥ 3.0 V）[V] | 133 或 166 MHz，各页互相矛盾 [S] |
| JEDEC ID | 厂商 20h，型号 BAh（3 V），容量 18h [M] | IQ：EF 40 18；IM：EF 70 18 [V] | 未读 | 未读 |
| 生命周期 | **未核实**（§4.1） | **未核实**（§4.2） | **未核实**（§4.3） | **未核实**（§4.4） |
| 规格书 | 镜像 Rev K 04/19，93 页 [M] | Rev I 2021-08 / Rev D 2025-02 [V] | Rev 1.1 2026-09-01，91 页 [V] | 没读到 |
| IBIS | 没找到 | 没找到 | 没找到 | 没找到 |
| KiCad 符号 | 无 3 V 的；`MT25QUxxxxxx1xW7` 是 1.8 V 款，引脚相同 | `W25Q128JVE`（8 × 6）、`W25Q128JVP`（6 × 5） | 无 128 Mbit；`MX25L3233FZN`（32 Mbit，6 × 5，引脚相同） | 无 |
| KiCad 封装 | `Package_SON:WSON-8-1EP_8x6mm_P1.27mm_EP3.4x4.3mm` | 同左 | 同左（EP 比器件小，见 §3） | — |
| ST 板上用过 | STM32F412G / F413H / F469I / F746G-DISCO、F7508-DK（128 Mbit，W9）[S] | STM32F746G-DISCO [S] | H735G-DK 用的是另一颗 Octo-SPI，没有 128 Mbit QSPI [S] | 无 |

## 3. WSON-8 的尺寸和焊盘兼容

三家都是 8 个外围焊盘加一个中间的 EP，引脚排列、间距相同。尺寸都来自规格书的封装图（单位 mm，括号里是 min–max）：

| 封装 | 厂商 | 本体 D × E | 引脚宽 b | 引脚长 L | EP（沿 D × 沿 E） | 来源 |
|---|---|---|---|---|---|---|
| 6 × 5 | Micron W7 | 6 ± 0.1 × 5 ± 0.1 | 0.4 ± 0.05 | 0.6 ± 0.05 | 3.0 ± 0.1 × 3.0 ± 0.1 | [Micron 镜像][ds-mt-mirror] p.20 [M] |
| 6 × 5 | Winbond P | 6.00 × 5.00 | 0.40（0.35–0.48） | 0.60（0.55–0.65） | 3.40 × 4.30 | [Rev D][ds-w25q-d] p.96 [V] |
| 6 × 5 | Macronix ZN | 6.00 × 5.00 | 0.40（0.35–0.48） | 0.60（0.55–0.65） | 3.40 × 4.00 | [Rev 1.1][ds-mx] p.88 [V] |
| 8 × 6 | Micron W9 | 8 ± 0.1 × 6 ± 0.1 | 0.4 ± 0.05 | 0.5 ± 0.05 | 3.4 ± 0.1 × 4.3 ± 0.1 | [Micron 镜像][ds-mt-mirror] p.21 [M] |
| 8 × 6 | Winbond E | 8.00 × 6.00 | 0.40（0.35–0.48） | 0.50（0.45–0.55） | 3.40 × 4.30 | [Rev D][ds-w25q-d] p.97 [V] |
| 8 × 6 | Macronix Z2 | 8.00 × 6.00 | 0.40（0.35–0.48） | 0.50（0.45–0.55） | 4.70 × 4.60 | [Rev 1.1][ds-mx] p.89 [V] |

结论：

- **6 × 5 和 8 × 6 不能互换**，是两种封装。AD 里这两个是两个不同的 Footprint。
- **同一尺寸内，外围 8 个焊盘三家重合**（间距 1.27、引脚宽 0.4、引脚长 0.5 或 0.6、同侧首尾两脚中心距 3.81）。EP 各家不同，但 EP 不接任何信号：Micron 的 EP 内部连 VSS，"可以悬空或接 VSS，不能接别的电压或信号"（镜像 p.12–13）；Winbond 写"不接内部信号，悬空或接 GND，**避免在焊盘下放过孔**"（Rev D p.96–97）；Macronix 写"悬空或接 GND，**不要接别的电压或信号，避免在焊盘下放过孔或走线**"（p.88–89）。所以 PCB 上一个封装就能装三家。
- 8 × 6：KiCad 官方 `Package_SON:WSON-8-1EP_8x6mm_P1.27mm_EP3.4x4.3mm` 的 EP 与 Micron、Winbond 的 EP 完全一致；Macronix 的 EP（4.7 × 4.6）比 PCB 焊盘大，焊接上没问题 [I]，没有按 IPC 重算过。外围焊盘 0.65 × 0.5 mm，中心在 x = ±3.75 mm、y = ±1.905 mm，引脚实际落在 x = 3.5–4.0 mm，焊盘里外各多 0.075 mm [I]。
- 6 × 5：要装三家，用 EP 最小的 `Package_DFN_QFN:W-PDFN-8-1EP_6x5mm_P1.27mm_EP3x3mm`（Micron 的封装图，EP 3 × 3）最稳 [I]；Winbond 的 `Package_SON:WSON-8-1EP_6x5mm_P1.27mm_EP3.4x4.3mm` 外围焊盘是 0.75 × 0.5 mm（x = ±2.7），Micron 版是 1.05 × 0.4 mm（x = ±2.85），两者在 x = 2.325–3.075 mm 重合 [I]。
- 不管哪种尺寸，EP 下面**不放过孔、不走线**（三家规格书里至少两家明确要求），EP 悬空或接地。

## 4. 逐颗说明

### 4.1 Micron MT25QL128ABA1EW9-0SIT（推荐）

- **订货号**：`MT 25Q L 128 A BA 1 E W9 - 0 S IT`。`L` = 2.7–3.6 V，`128` = 128 Mbit，`A` = 1 个 die / 1 个 S#，`BA` = 第 2 代 Rev A，`1` = 第 7 脚是 HOLD#（`3` = RESET#，`8` = 两者都有，8 脚封装没有 `8`），`E` = 64 KB 扇区，`W9` = 8 脚 W-PDFN 8 × 6，`0` = 标准安全，`S` = 标准，`IT` = −40…+85 ℃（[镜像][ds-mt-mirror] p.2）[M]。6 × 5 的同款是 `…1EW7-0SIT`。
- **引脚、EP、封装图**：[镜像][ds-mt-mirror] p.12–13、p.20–21 [M]。第 7 脚在 Quad 模式下是 DQ3；"用单线或双线命令时，DQ3 必须由主机驱动为高电平，或在 PCB 上加外部上拉，防止 HOLD# 或 RESET# 悬空"（p.12）。
- **电气**：VCC 2.7–3.6 V（p.81，Table 39）；时钟 STR 133 MHz、DTR 90 MHz（p.1、p.85 Table 44）[M]。H743 的 QUADSPI 在 2.7–3.6 V、负载 20 pF 下最高 133 MHz（SDR）、100 MHz（DDR），两边能对上（[DS12110][ds-h743] p.270 Table 171、p.271 Table 172；rev Y 部分的 p.164 Table 74、p.165 Table 75 同值）[V]。
- **生命周期：未核实**。
  - [Micron 零件页][pg-mt]（W7 款；W9 款在同目录下 `mt25ql128aba1ew9-0sit`）能打开，但状态和规格是 JS 加载，静态页里没有。我没有去抓页面背后的数据接口（试了一次，被权限系统拦下，没有再试）。
  - 经销商页面（DigiKey、Microchip USA、Avaq 等）显示 Active，来自搜索摘要，**不是一手** [S]。
  - **风险信号**：搜索摘要说 Micron 2026-01-30 的 [PCN 36228][pcn-36228]（停产 "60s NOR"）列了 MT25QL256ABA1EW7-0SIT、MT25QL512ABB8ESF-0SIT 以及几颗 MT25QU01G，最后下单日 2026-08-31、最后发货日 2027-09-01 [S]。同系列同封装（W7）的 256 Mbit 在名单里；128 Mbit 在不在，我没读到原文。MT25QL512ABB8ESF 恰好是 ST 官方 H7 板用的那颗（§5）。
  - 另外 Micron 的"已停产零件"目录里有 `MT25QL128ABA1EW7-MSIT`（后缀 `-M`，不是 `-0`）[S]。
  - 结论：**订货前请你在浏览器里打开 Micron 零件页确认是 Production**。如果不是，直接换备选 1，PCB 不用改。
- **规格书版本**：我读的是 LCSC 镜像的 Rev K（2019-04）。Micron 官网这份 PDF 的地址已变（KiCad 库里引用的旧地址 404），官网最新版没读到；搜索摘要提到 Farnell 上有 Rev E（2024-07）的 ABB（Rev B die）版，没打开。
- **IBIS**：没找到，Micron 零件页的"资源"区读不到。**未核实**。
- **KiCad**：库里没有 3 V 的 MT25QL 符号。`Memory_Flash:MT25QUxxxxxx1xW7` 是 1.8 V 款（描述写 "1.8V"），引脚编号和名字与 3 V 款相同（1 ~S、2 DQ1、3 ~W/DQ2、4 VSS、5 DQ0、6 C、7 ~RESET/DQ3、8 VCC、9 PAD），可以拿来用但要改 Value 和描述。

### 4.2 Winbond W25Q128JVEIQ（备选 1）

- **订货号**（[Rev I][ds-w25q-i] p.75–76）：`W25Q128JV` + `E`（WSON-8 8 × 6）+ `I`（−40…+85 ℃）+ `Q`。`Q` = QE 位在状态寄存器 2 里**固定为 1**，与 FV 系列向后兼容；`M` = QE = 0（可编程），使用新的器件 ID，对应 2025 年的 Rev D（W25Q128JV-DTR）[V]。6 × 5 的同款是 `W25Q128JVPIQ`。
- **ID 与 QE**：IQ 的 ID 是 EF 40 18，IM 是 EF 70 18（Rev I p.22）；QE = 1 时第 3、7 脚是 IO2、IO3，/HOLD 功能关闭（Rev I p.17）[V]。接 QUADSPI 的话，`IQ` 免去先写 QE 位的步骤；固件要按 `IQ` 或 `IM` 的 ID 来识别。
- **引脚、封装、EP**：[Rev D][ds-w25q-d] p.7、p.96–97 [V]。
- **电气**：2.7–3.6 V；**133 MHz 要 VCC 3.0–3.6 V**，2.7–3.0 V 时 104 MHz；DTR 3.0–3.6 V 66 MHz、2.7–3.0 V 52 MHz；03h 读命令 50 MHz（Rev D p.86 Table 9.2、p.91 Table 9.6）[V]。3.3 V 供电没问题。
- **生命周期：未核实**。[Winbond 零件目录页][pg-winbond]能打开，但内容是 JS 加载。Rev D 发布于 2025-02，说明还在维护；`IQ` 订货号只出现在 2021 的 Rev I 里，2025 的 Rev D 只列 `IM/JM`，**`IQ` 现在是否仍可订未核实**。
- **IBIS**：没找到。**未核实**。
- **KiCad**：`Memory_Flash:W25Q128JVE`（`Package_SON:WSON-8-1EP_8x6mm_P1.27mm_EP3.4x4.3mm`）、`W25Q128JVP`（`Package_SON:WSON-8-1EP_6x5mm_P1.27mm_EP3.4x4.3mm`）。符号引脚：1 ~CS、2 DO/IO1、3 ~WP/IO2、4 GND、5 DI/IO0、6 CLK、7 ~HOLD/~RESET/IO3、8 VCC、9 EP（passive）。符号里的规格书链接是 2018 年的 Rev C，旧了。

### 4.3 Macronix MX25L12833FZ2I-10G（备选 2）

- **订货号**（[Rev 1.1][ds-mx] p.84–85）：`MX 25 L 12833F Z2 I 10 G`，`L` = 3 V，`Z2` = 8 脚 WSON 8 × 6，`ZN` = 8 脚 WSON 6 × 5，`I` = −40…+85 ℃，`10` = 104 MHz 速度级，`G` = 无卤。订货表页眉写"最新的产品选择请联系 Macronix 销售"[V]。规格书同一页组合里还有 `M2`（8 脚 SOP）和 `M`（16 脚 SOP）。
- **引脚**：第 7 脚是 `RESET#/SIO3`，没外接时有内部上拉；注意它在非 Quad 模式下是 RESET# 而不是 HOLD#（p.6）[V]。
- **电气**：2.7–3.6 V 单电源（p.4）。时钟：封面写"所有协议最高 133 MHz"（p.4）；AC 表（p.77 Table 18）里 Quad 读最大 84 MHz 是"默认 dummy 周期下的值"，要更高频率按 Table 1（p.5）配 dummy 周期：Quad IO 快读 6 个 dummy → 84 MHz（默认），8 个 → 104 MHz，10 个 → 120 MHz，VCC 在 3.0–3.6 V 时 133 MHz [V]。**订货号后缀 `-10` 是 104 MHz 速度级**，所以按 104 MHz 用最稳。
- **生命周期：未核实**。[Macronix 零件页][pg-mx]静态页里状态和规格都是 "Loading…"；页上有一个 "End of Life (EOL)" 标签，我读不出它指什么。规格书 Rev 1.1 是 2026-09-01 发布的，说明这颗还在维护；DigiKey 的搜索摘要里它的前代 `MX25L12835FZNI-10G` 有的页面标成了"不推荐新设计"[S]。
- **IBIS**：没找到。
- **KiCad**：没有 128 Mbit 的符号。`Memory_Flash:MX25L3233FZN`（32 Mbit、3 V、WSON 6 × 5、EP 3.4 × 4）引脚相同，但第 7 脚叫 `~HOLD/SIO3`，要改成 `RESET#/SIO3`。

### 4.4 ISSI IS25LP128F-JKLE（未核实）

`www.issi.com` 的规格书下载被 Incapsula 拦截，没有绕过，所以只有搜索摘要：DigiKey 页写 8-WSON (6 × 5)、2.3–3.6 V、Active，时钟 133 / 166 MHz 各页不一致；一份非 ISSI 官方的规格书 PDF 标 Rev.A7 2022-02-20 [S]。其余项全部未核实，不推荐在没读到规格书的情况下选它。KiCad 官方库里没有它的 3 V 符号（`IS25WP256D-xM` 是 1.8 V、SOIC-16）。

## 5. ST 官方 H7 板的 QSPI Flash

| 板 | Flash | 封装 | 单颗 / 双颗 | 来源 |
|---|---|---|---|---|
| STM32H743I-EVAL / H753I-EVAL（MB1246，及 EVAL2） | Micron MT25QL512ABB8ESF-0SIT × 2，或 MT25TL01GHBB8ESF-0SIT（1 Gbit）× 1；两种都有可能，我没查到哪个是现行贴法 | `ESF` 按 MT25Q 料号规则是 SO16 300 mil [I]；MT25TL01G 的封装没读规格书 | **双**（twin Quad-SPI） | [UM2198][um2198] Rev 5 p.19（"1-Gbit twin Quad-SPI NOR flash 或两颗 512 Mbit"，没写订货号）[V]；订货号来自[ST 社区文章][st-kb]；[BSP 头文件][bsp-h743i] `#include mt25tl01g.h` [S] |
| STM32H745I-DISCO、STM32H750B-DK（[UM2488][um2488] 同一本手册） | 同上，默认两颗 512 Mbit（U1、U2），也可贴一颗 1 Gbit（U1） | 同上 | **双** | UM2488 Rev 10 p.15 Table 6 [V]；BSP 注释 `/* MT25TL01G Micron memory */`（[H750B-DK][bsp-h750b]、[H745I-DISCO][bsp-h745i]）、社区文章 [S] |
| STM32H735G-DK（MB1520） | Macronix MX25LM51245G（512 Mbit **Octo-SPI**），另有 HyperRAM S70KL1281 | 没读到（UM2679 超过 WebFetch 的 10 MB 限制，`curl` 被 st.com 拦） | **单**，但不是 QSPI | [BSP 头文件][bsp-h735g] `stm32h735g_discovery_ospi.h` [S] |

- 这些板都是双 bank 并行（BK1 + BK2 共享 CLK/NCS），**没有一块是"单颗 QSPI、WSON-8"**，所以没有现成的 H7 参考原理图可以照搬。最接近的 ST 单颗 128 Mbit QSPI 参考是 F7 / F4 的 Discovery 板（STM32F746G-DISCO 等），[ST 社区文章][st-kb]列的是 Micron `MT25QL128ABA1EW9-0SIT`（8 × 6 W-PDFN），F746G-DISCO 的行里同时出现 Winbond `W25Q128JVEIQ`（ST 把它们标成同一类，我推测是同一位置的两种供货）[S][I]。
- ST 社区文章（"Memories compatible with QUADSPI, OCTOSPI, HSPI, and XSPI interfaces"）自己写明表里是"ST 官方板上用过的存储器的例子"，不是测试或认证清单；表里没有任何 Macronix MX25L128 或 ISSI 行 [S]。
- ST 官方板的 BSP 用的 QUADSPI 引脚（[H743I-EVAL][bsp-h743i]、[H750B-DK][bsp-h750b]、[H745I-DISCO][bsp-h745i]；每个都是 [DS12110][ds-h743] Table 10 里合法的组合）：H743I-EVAL 的 Bank1：CLK = PB2、NCS = PG6、IO0 = PF8、IO1 = PF9、IO2 = PF7、IO3 = PF6；H750B-DK / H745I-DISCO 的 Bank1：CLK = PF10、NCS = PG6、IO0 = PD11、IO1 = PF9、IO2 = PF7、IO3 = PF6（Bank2：IO0 = PH2、IO1 = PH3、IO2 = PG9、IO3 = PG14）[S]。

## 6. KiCad 10 官方库里有什么

库路径：`D:\KiCad\share\kicad\symbols\Memory_Flash.kicad_sym`、`footprints\Package_SON.pretty`、`footprints\Package_DFN_QFN.pretty`。

| 需要 | 库里的名字 | 说明 |
|---|---|---|
| Winbond 128 Mbit 符号 | `Memory_Flash:W25Q128JVE`、`W25Q128JVP`、`W25Q128JVS`（SOIC-8），都继承 `W25Q32JVZP` | `JVE` 的 Footprint 字段是 8 × 6，`JVP` 的是 6 × 5 |
| Micron 符号 | `Memory_Flash:MT25QUxxxxxx1xW7` | 1.8 V 款，Footprint 字段 `Package_DFN_QFN:W-PDFN-8-1EP_6x5mm_P1.27mm_EP3x3mm`；引脚 3、7 的类型是 `input`，不是 `bidirectional` |
| Macronix 符号 | `Memory_Flash:MX25L3233FZN`（32 Mbit） | 无 128 Mbit 的；还有 `MX25R3235FZN…`（低压款） |
| ISSI 符号 | 无可用 | `IS25WP256D-xM` 是 1.8 V SOIC-16 |
| 8 × 6、EP 3.4 × 4.3 封装 | `Package_SON:WSON-8-1EP_8x6mm_P1.27mm_EP3.4x4.3mm` | 描述里引用的是 GigaDevice 规格书；焊盘尺寸与 Micron W9、Winbond E 的封装图吻合 |
| 6 × 5、EP 3.4 × 4.3 | `Package_SON:WSON-8-1EP_6x5mm_P1.27mm_EP3.4x4.3mm` | 来自 Winbond 规格书 |
| 6 × 5、EP 3.4 × 4 | `Package_SON:WSON-8-1EP_6x5mm_P1.27mm_EP3.4x4mm`（Microchip 的图）、`Package_DFN_QFN:WDFN-8-1EP_6x5mm_P1.27mm_EP3.4x4mm` | 与 Macronix ZN 的 EP 吻合 |
| 6 × 5、EP 3 × 3 | `Package_DFN_QFN:W-PDFN-8-1EP_6x5mm_P1.27mm_EP3x3mm` | Micron W7 的封装图 |

库里**没有**带"Micron"前缀的 8 × 6 封装；Micron W9 用上面的 `WSON-8-1EP_8x6mm_…EP3.4x4.3mm`。

## 7. STM32H743 QUADSPI Bank1 的可选引脚（UFBGA176+25）

来源：[DS12110 Rev 11][ds-h743]，Table 10（复用功能表）p.89–97 逐页看图，Table 9（引脚和球号）p.64–86 读文字，两张表一致；球号再与 KiCad 的 `STM32H743IIKx` 符号逐个比对，16 个全部相同 [V]。

| 信号 | 可选引脚（球号，AF） | 在 Table 10 的页 |
|---|---|---|
| QUADSPI_CLK | PF10（L1，AF9）、PB2（M6，AF9） | p.95、p.90 |
| QUADSPI_BK1_NCS | PG6（J15，AF10）、PB6（B6，AF10）、PB10（R12，AF9） | p.96、p.90、p.91 |
| QUADSPI_BK1_IO0 | PF8（L3，AF10）、PD11（N14，AF9）、PC9（F14，AF9） | p.95、p.93、p.92 |
| QUADSPI_BK1_IO1 | PF9（L2，AF10）、PD12（N13，AF9）、PC10（B14，AF9） | p.95、p.93、p.92 |
| QUADSPI_BK1_IO2 | PF7（K1，AF9）、PE2（A2，AF9） | p.95、p.94 |
| QUADSPI_BK1_IO3 | PF6（K2，AF9）、PD13（M15，AF9）、PA1（N2，AF9） | p.95、p.93、p.89 |

Table 9 里这些引脚所在页：PE2 p.64、PF6–PF10 p.66、PA1 p.68、PB2 p.71、PB10 p.73、PD11–PD13 p.76、PG6 p.78、PC9 p.79、PC10 p.82、PB6 p.86。PI / PJ / PK 端口没有 QUADSPI 功能（p.98–100）。

**与 32 位 SDRAM 的冲突**：SDRAM 要用的 FMC 引脚按 `h7-ufbga176-mcu.md` §4 是 57 个（D0–D31、A0–A11、BA0/1、NBL0–3、SDCLK、SDNCAS、SDNRAS、SDNWE、SDCKE0、SDNE0）。

- **没有任何一个 QUADSPI Bank1 备选引脚是 SDRAM 的固定引脚。** 我对着 Table 10 把 16 个备选引脚的 AF12（FMC）列逐个看了一遍：PA1、PB2、PB10、PF6–PF10 的 AF12 是 `-`；PC9、PC10 的 AF12 是 SDMMC1；其余有 FMC 功能的只有下面这些，都不是 SDRAM 用的：
  - PD11 = FMC_A16、PD12 = FMC_A17、PD13 = FMC_A18、PE2 = FMC_A23（NOR / PSRAM 的高位地址，SDRAM 用不到）
  - PG6 = FMC_NE3（NOR / PSRAM 片选）
  - **PB6 = FMC_SDNE1**（SDRAM 第 2 个 bank 的片选）。SDRAM 用 SDNE0（bank 1）就没事；若以后改用 bank 2，PB6 要让出来。
- SDRAM 的备选控制引脚（SDCKE0：PH2 / PC5 / PC3_C；SDNE0：PH3 / PC4 / PC2_C；SDNWE：PH5 / PC0 / PA7）也都不在 Bank1 备选里。
- 不用的 Bank2（仅供参考）：BK2_IO0–IO3 在 PE7–PE10（与 SDRAM 的 D4–D7 冲突）或 PH2、PH3、PG9、PG14，BK2_NCS 在 PC11。PH2、PH3 同时是 SDCKE0、SDNE0 的首选，所以真要用双 bank，PH2 / PH3 得让给 SDRAM。这块板是单颗，不涉及。

**布局相关的事实（不是结论，布局阶段再定）** [I]：

- **PF6–PF10 对应 K1、K2、L1、L2、L3，五个球相邻**，一次拿到 CLK + IO0–IO3，是 ST 自己 H743I-EVAL、H750B-DK 的做法；NCS 的三个备选（PG6 = J15、PB6 = B6、PB10 = R12）都离这一簇很远，球图上最近的是 PB6。NCS 不是时序关键线，长一点没问题。
- 这一簇紧挨 SDRAM 的地址线 A3–A5（PF3 = J2、PF4 = J3、PF5 = K3），两组信号会在同一侧抢出线通道。
- 另一种凑法：IO0 = PD11（N14）、IO1 = PD12（N13）、IO3 = PD13（M15）、NCS = PG6（J15），也比较集中，但 IO2 只能是 PF7（K1）或 PE2（A2），都在另一侧；PD 口附近 PD8–PD10、PD14–PD15 已经是 SDRAM 的 D13–D15、D0、D1。
- QUADSPI 的时钟：2.7–3.6 V、20 pF 下 SDR 最高 133 MHz，数据输入建立 / 保持时间 2 / 1 ns（[DS12110][ds-h743] p.270，Table 171，rev V 部分）[V]。

## 8. 设计注意（来自规格书的部分标了页码，其余是我的建议）

- 第 7 脚：三家都是 Quad 模式下的 IO3，在非 Quad 模式下 Micron 是 HOLD#（`…1…` 后缀）、Winbond 是 /HOLD 或 /RESET、Macronix 是 RESET#。Micron 规格书明说，用单线 / 双线命令时 DQ3 必须由主机拉高或外加上拉（镜像 p.12）[M]。第 3 脚（WP# / IO2）同理。QUADSPI 启动前、复位后这些脚是浮空的，**建议第 3、7 脚和 NCS 各加上拉到 3.3 V** [I]，阻值留到原理图阶段。
- Winbond `IQ` 的 QE 位固定为 1，QUADSPI 直接可用；Micron 和 Macronix 需要固件按各自规格书配置 Quad 模式和 dummy 周期；三家的 JEDEC ID 不同，ST 的 BSP、外部下载算法（loader）都按料号写，换厂商要换固件配置 [I]。
- Macronix 要 10 个 dummy 周期、VCC ≥ 3.0 V 才到 133 MHz；Winbond 133 MHz 也要 VCC ≥ 3.0 V。3.3 V 供电都够。
- EP 悬空或接地，下面不放过孔、不走线（§3）。

## 9. 已验证与未验证

**已验证（读过一手原文，括号里是来源和页码）**

- H743 QUADSPI Bank1 全部备选引脚、AF 号、球号（DS12110 Rev 11 Table 9 p.64–86、Table 10 p.89–97）；QUADSPI SDR 133 MHz / DDR 100 MHz（p.164、p.270）。
- 备选引脚与 SDRAM 引脚没有直接冲突（对着 Table 10 的 AF12 列逐个看过；SDRAM 引脚清单本身取自 `h7-ufbga176-mcu.md` §4）。
- Winbond W25Q128JV 的两种 WSON-8 封装尺寸、引脚、订货号规则、QE 位、JEDEC ID、VCC 与时钟的关系（Rev D p.6–7、p.86、p.91、p.96–97、p.101；Rev I p.17、p.22、p.70–71、p.75–76）。
- Macronix MX25L12833F 的两种 WSON-8 封装尺寸、引脚、订货号规则、AC 表和 Table 1（Rev 1.1 p.4–6、p.77–78、p.84–85、p.88–89）。
- ST 的两本用户手册：UM2198 Rev 5 p.19、UM2488 Rev 10 p.15，写的是"双颗 / 两颗 512 Mbit 或一颗 1 Gbit"，没有订货号。
- KiCad 库里的符号名、封装名、焊盘坐标、符号引脚（本机文件）。

**读过原文，但来源是镜像（[M]）**

- Micron MT25QL128ABA 的订货号规则、引脚、W7 / W9 封装、VCC、时钟、第 7 脚上拉要求、EP 说明：LCSC 镜像，Rev K 2019-04，不是官网下载，不一定是最新版。

**未验证（只有搜索摘要、WebFetch 摘要、经销商页面，或根本没找到）**

1. **Micron MT25QL128ABA1EW9-0SIT 的生命周期**。官网零件页是 JS 渲染读不到；PCN 36228 没打开。搜索摘要说它列了 MT25QL256ABA1EW7-0SIT、MT25QL512ABB8ESF-0SIT，最后下单日 2026-08-31、最后发货日 2027-09-01，128 Mbit 在不在没读到原文。经销商页面显示 Active 不算一手。
2. **Winbond W25Q128JVEIQ 的生命周期和是否仍可订**；`IQ` 订货号在 2025 的 Rev D 里没列。
3. **Macronix MX25L12833FZ2I-10G 的生命周期**；零件页 JS 渲染，"End of Life (EOL)" 标签的含义没读出来。
4. **三家的 IBIS 模型是否公开**：规格书里都不提，网上搜不到；官网的资源页读不到。
5. **ISSI IS25LP128F-JKLE 的全部信息**（官网反爬，没绕过）。
6. Micron 规格书的最新版本和官网地址。
7. ST 社区文章的表、ST 官方 BSP 头文件的内容：来源是一手，但我读的是 WebFetch 的摘要，没有逐行读原文；建议打开链接再确认一次。
8. H743I-EVAL 现行贴的是 2 × MT25QL512 还是 1 × MT25TL01G；Flash 的封装（`ESF` = SO16 是按 MT25Q 的料号规则推断，MT25TL01G 的规格书没读）；H735G-DK 的 Flash 封装（UM2679 没读到）；MB1246 / MB1520 的原理图和 BOM 没读。
9. STM32F746G-DISCO 上 Micron 与 Winbond 是否是同一位置的两种供货（我的推测）。
10. RM0433 的 QUADSPI 章节、勘误表 ES0392 里 QUADSPI 相关条目没读（QUADSPI 的 IO 速度设置、补偿单元、dummy 周期限制等）。
11. 不同厂商同一封装的 PCB 焊盘按 IPC 重算：没做，兼容性结论来自封装图尺寸比对。
12. `datasheets` skill 没用（RUL-10）：这次是跨三家的封装和订货号比对，没有工程可挂缓存，且你指定了用现成命令读 PDF；规格书文字和表格我用 `pdftotext` 转文字后，关键表格和封装图都转图用眼睛看过。

## 10. 推荐

**Micron MT25QL128ABA1EW9-0SIT**，备选 **Winbond W25Q128JVEIQ**、**Macronix MX25L12833FZ2I-10G**，封装按 8 × 6 做（§0）。

1. 按你的厂商优先级：Micron 排第一；ST 自己所有的 H7 官方板都用 Micron 的 MT25Q / MT25T 系列，BSP 和 ST 的下载算法围绕它写，而且 ST 把这一颗 128 Mbit W9 列在多块 F4 / F7 Discovery 板上。
2. 封装一个，三个厂商共用：8 × 6，EP 3.4 × 4.3（Micron 与 Winbond 完全一致），引脚逐脚相同；换厂商只改 BOM 和固件配置，不改板。
3. KiCad 里直接用现成的 `Memory_Flash:W25Q128JVE`（符号）加 `Package_SON:WSON-8-1EP_8x6mm_P1.27mm_EP3.4x4.3mm`（封装）；Micron 的符号库里只有 1.8 V 款，要改字段，不推荐直接用。
4. **风险只有一个：Micron 这颗的生命周期我没能核实**（§4.1）。如果你在 Micron 官网看到状态不是 Production，或者落在 PCN 36228 的名单里，改用 Winbond `W25Q128JVEIQ`（或 `…EIM`）；这时规格书读得最全的两家是 Winbond 和 Macronix。

---

[ds-h743]: https://www.st.com/resource/en/datasheet/stm32h743ii.pdf
[um2198]: https://www.st.com/resource/en/user_manual/dm00385071-evaluation-boards-with-stm32h743xi-and-stm32h753xi-mcus-stmicroelectronics.pdf
[um2488]: https://www.st.com/resource/en/user_manual/um2488-discovery-kits-with-stm32h745xi-and-stm32h750xb-mcus-stmicroelectronics.pdf
[st-kb]: https://community.st.com/t5/stm32-mcus/memories-compatible-with-quadspi-octospi-hspi-and-xspi/ta-p/845854
[bsp-h743i]: https://raw.githubusercontent.com/STMicroelectronics/stm32h743i-eval-bsp/master/stm32h743i_eval_qspi.h
[bsp-h750b]: https://raw.githubusercontent.com/STMicroelectronics/stm32h750b-dk-bsp/master/stm32h750b_discovery_qspi.h
[bsp-h745i]: https://raw.githubusercontent.com/STMicroelectronics/stm32h745i-disco-bsp/master/stm32h745i_discovery_qspi.h
[bsp-h735g]: https://raw.githubusercontent.com/STMicroelectronics/stm32h735g-dk-bsp/master/stm32h735g_discovery_ospi.h
[ds-w25q-d]: https://www.winbond.com/resource-files/W25Q128JV_DTR%20RevD%2012232024%20Plus.pdf
[ds-w25q-i]: https://www.winbond.com/resource-files/W25Q128JV%20RevI%2008232021%20Plus.pdf
[pg-winbond]: https://www.winbond.com/hq/product/code-storage-flash-memory/serial-nor-flash/?__locale=en&partNo=W25Q128JV
[ds-mx]: https://www.mxic.com.tw/Lists/Datasheet/Attachments/9273/MX25L12833F,%203V,%20128Mb,%20v1.1.pdf
[pg-mx]: https://www.macronix.com/en-us/products/NOR-Flash/Serial-NOR-Flash/Pages/spec.aspx?p=MX25L12833F
[ds-mt-mirror]: https://atta.szlcsc.com/upload/public/pdf/source/20241204/2E556C1CEAD534606001D577F1BBC28D.pdf
[pg-mt]: https://sg.micron.com/products/storage/nor-flash/serial-nor/part-catalog/part-detail/mt25ql128aba1ew7-0sit
[pcn-36228]: https://www.mouser.com/PCN/Micron_Technology_PCN_36228.pdf
[prev-h7]: https://github.com/immorcoding/PCB/blob/research/h7-ufbga176-mcu/docs/research/h7-ufbga176-mcu.md
