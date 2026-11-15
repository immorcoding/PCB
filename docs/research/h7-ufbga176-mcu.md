# STM32H7 UFBGA176+25 候选型号调研（工单 #2）

日期 2026-11-15。问题见 GitHub issue #2：在 UFBGA176+25（10 × 10 mm，0.65 mm 球距）封装的 STM32H7 里，哪一颗最适合"STM32H7 + 32 位 BGA SDRAM 六层测试板"。所有规格书都是 2026-11-15 从 ST 官网下载的当前版本，页码是 PDF 页脚上的页码。链接用文末的引用名，每条结论后面标了出处。

## 0. 结论

- **推荐 STM32H743IIK6。** 当前倾向得到证实。
- 淘汰一半候选：**H745、H735、H7A3…Q、H7B3…Q 在这个封装上都是 SMPS 球图，FMC 只引出 24 位数据线（没有 D24–D31、NBL2、NBL3），做不了 32 位 SDRAM。** 这是这次调研最重要的发现；H735 的规格书自己写明了这一点。
- **H743 / H742 / H750 / H753 四个系列的球图完全相同**（LDO 供电，FMC 32 位全部引出），可以在同一块板上互换；差别只在 Flash 和有没有加密。
- H7A3 / H7B3 **不带 Q 的型号**球图与 H743 只差一个球（C8：VDD 换成 VDDMMC），FMC 32 位也全齐，是第二选择；但我查到的 H7B3 官方 32 位 SDRAM 板（H7B3I-EVAL）是 SMPS 型的 TFBGA225，不是 LDO 球图，参考原理图对不上。
- **核对过的 ST 评估板里，没有一块用 UFBGA176+25 的 H743 / H750 / H753 / H745 / H7A3 / H7B3。** 用这个封装的只有 STM32H735G-DK，它没有 SDRAM，且 H735 只能 24 位，不能做参考。32 位 SDRAM 的官方原理图来源是 STM32H753I-EVAL（MB1246-H753，TFBGA240+25，8M×32 SDRAM），它的 MCU 与 H743 同一个硅片家族，只是封装不同（球号和电源脚数量不同，FMC 的端口引脚是否全部落在 UFBGA176+25 的 57 个信号脚上，见 §4 和 §9）。
- H735G-DK 的"UFBGA / TFBGA"之争以 MCU 规格书为准：**UFBGA176+25，封装代码 A0E7**；UM2679 自己前后写法不一致（见 §7）。

## 1. 怎么查的

| 步骤 | 做法 |
|---|---|
| 规格书 | 下载 7 份：[DS12110][ds-h743]（H742/H743）、[DS12556][ds-h750]（H750）、[DS12117][ds-h753]（H753）、[DS12923][ds-h745]（H745）、[DS13312][ds-h735]（H735）、[DS13195][ds-h7a3]（H7A3）、[DS13139][ds-h7b3]（H7B3），转成文本读 |
| 球图 | 规格书里的"UFBGA176+25 ballout"图（H743 p.60、H750 p.56、H753 p.60、H745 p.55、H735 p.62、H7A3 p.45–46、H7B3 p.47–48）。用脚本读出每行的文字，与 KiCad 10 自带符号库 `MCU_ST_STM32H7.kicad_sym` 的引脚表逐行比对 |
| 比对结果 | 九张图（含 H7A3 / H7B3 各两种）的 GPIO 在每一行上都与符号库一致（只有 PC14/PC15/PH0/PH1 因为图里分成多行写，脚本没抓到，手工核对一致）；H743 / H750 / H753 的整行（A、B、C、D、M、N、P、R 八行，120 个球）逐球顺序也一致；H743 的 140 个 GPIO 球里 102 个另外在规格书 Table 9 引脚表里按"球号在引脚名前"核对通过，其余 38 个因为表格换行脚本没解析出来，其中 SDRAM 用到的都对照图手工看过 |
| 其他 | ST 产品页（状态、订货号、文档列表）、应用笔记 AN4938 / AN5419 / AN5307 / AN5293、勘误表 ES0392 / ES0445 / ES0491 / ES0478、评估板页面和 MB1246 原理图 |

KiCad 符号库本身不是一手资料，只用来把图里的文字变成可以脚本比对的表；结论以规格书为准，规格书和符号库不一致的地方会单独写出来（目前没有发现）。

## 2. 逐颗对比

### 2.1 球图、IO 和 FMC

| 型号（UFBGA176+25） | 球图组（§3） | 端口 IO 数 | FMC 数据位宽（此封装） | 32 位 SDRAM |
|---|---|---|---|---|
| STM32H743IIK6 | L | 140 | 32 位（D0–D31、NBL0–3 全有） | 可以 |
| STM32H750IBK6 | L | 140 | 32 位 | 可以 |
| STM32H753IIK6 | L | 140 | 32 位 | 可以 |
| STM32H7A3IIK6 / H7B3IIK6（无 Q） | L'（只差 C8） | 140 | 32 位 | 可以 |
| STM32H745IIK6 | S | 128（外加 4 个 `_C` 模拟球） | 24 位（D24–D31、NBL2/3 没有） | **不行** |
| STM32H735IGK6 | S | 128 | 24 位（规格书明说） | **不行** |
| STM32H7A3IIK6Q / H7B3IIK6Q | S | 128（外加 4 个 `_C`） | 24 位 | **不行** |

出处：

- 球图和 GPIO 数：各规格书的 ballout 图，见 §1。LDO 型的图里端口 A–H 各 16 个加 PI0–PI11 共 12 个，合计 140（PC2、PC3 在这个封装上只以 PC2_C、PC3_C 的形式出现）；SMPS 型只有 A–H 端口，128 个。规格书 Table 2 的 GPIO 行：H743 / H753 的 II 一列写 140（[DS12110][ds-h743]、[DS12117][ds-h753]，p.20 前后），H735 的 IGK 一列写 128（[DS13312][ds-h735] p.19–20），与数图一致。
- H735 的 24 位：[DS13312][ds-h735] p.1 "up to 24-bit data bus"；Table 2 里 24 位 SDRAM 控制器一行只有 STM32H735IGK 一列打勾，脚注 1 写"24 位 SDRAM 控制器是 32 位控制器，只有 24 位数据线、没有 NBL2-3，可用于图形用途，访问对齐的 32 位字时忽略高 8 位"（p.21）。
- H745 和 H7A3/H7B3 的 Q 型：规格书封面仍写"up to 32-bit data bus"（[DS12923][ds-h745] p.1），那是整个系列最大封装的指标。此封装的球图（[DS12923][ds-h745] Figure 8 p.55；[DS13195][ds-h7a3] Figure 16 p.45；[DS13139][ds-h7b3] Figure 17 p.47）里没有任何 PI 端口的球；规格书引脚表里 FMC_D24–D27 在 PI0–PI3、D28/D29 在 PI6/PI7、D30/D31 在 PI9/PI10、NBL2/NBL3 在 PI4/PI5（[DS12923][ds-h745] Table 9），所以这个封装上这些信号没有球。
- 无 Q 的 H7A3/H7B3：图里有 PI0–PI11（[DS13195][ds-h7a3] Figure 17 p.46；[DS13139][ds-h7b3] Figure 18 p.48）。
- H7A3 规格书 Table 2 的 GPIO 行里，SMPS 组的 IIK 一列是 128（与图一致）；无 SMPS 组对应的一列看起来是 138（PDF 转文字后列头对不齐，按列的先后推断），我数图得到 140，差 2，疑似 PC2_C / PC3_C 计不计。没有进一步核对，不影响结论。

### 2.2 供电、Flash、文档

| 型号 | 供电（此封装） | 片内 Flash | RAM / 主频 | 订货号确认 |
|---|---|---|---|---|
| H743IIK6 | 只有 LDO；VCAP × 2 | 2 MB | 约 1 MB / 480 MHz | [ST 产品页][pg-h743] |
| H750IBK6 | 只有 LDO；VCAP × 2 | **128 KB** | 1 MB / 480 MHz | [ST 产品页][pg-h750] |
| H753IIK6 | 只有 LDO；VCAP × 2 | 2 MB | 1 MB / 480 MHz，带加密 | [ST 产品页][pg-h753] |
| H745IIK6 | SMPS 加 LDO；VCAP × 3、VDDLDO × 3 | 2 MB | 1 MB / M7 480 MHz + M4 240 MHz | [ST 产品页][pg-h745] |
| H735IGK6 | SMPS 加 LDO；VCAP × 3、VDDLDO × 3 | 1 MB | 564 KB / 550 MHz | [ST 产品页][pg-h735] |
| H7A3IIK6（Q 为 SMPS） | 无 Q：LDO；有 Q：SMPS 加 LDO | 2 MB | 1.4 MB / 280 MHz | [ST 产品页][pg-h7a3] |
| H7B3IIK6（Q 为 SMPS） | 同上 | 2 MB | 1.4 MB / 280 MHz，带加密 | [ST 产品页][pg-h7b3] |

出处：

- 封面特性：[DS12110][ds-h743] p.1（H743 "up to 2 MB flash"、"up to 1 MB RAM"）、[DS12556][ds-h750] p.1（"128 Kbytes of flash memory"）、[DS12117][ds-h753] p.1、[DS12923][ds-h745] p.1、[DS13312][ds-h735] p.1、[DS13195][ds-h7a3] p.1、[DS13139][ds-h7b3] p.1。
- 型号命名：订货号里 "K" 就是 UFBGA 0.65 mm 球距，"I"（作封装字母）才是 0.5 mm；"6" 为 −40…85 ℃。H743 见 [DS12110][ds-h743] §9 p.346；H750 p.326；H753 p.346；H745 §8 p.240；H735 §8 p.279。H7A3/H7B3 的订货码里 "Q = with SMPS，空白 = without SMPS"（[DS13195][ds-h7a3] §8 p.221；[DS13139][ds-h7b3] §8 p.222）。H745、H735 的 UFBGA176+25 没有无 SMPS 的型号。
- 状态：以上订货号在 ST 产品页均为 Active，长期供货承诺到 2036-01（见各产品页）。H745 与 H735 另有 IIK3（−40…125 ℃）版本。
- H735 封装名：规格书用 "UFBGA(176+25) package information (A0E7)"（[DS13312][ds-h735] §7.10 p.276）。

## 3. 球图分组与互换

只有两种球图，其余型号落在这两种之一，或者只差一个球。比较方法见 §1。表里的 H755、H725、H730、H7B0 没有在候选名单里，也没有读它们的规格书，分组只来自 KiCad 符号库，仅供参考。

| 球图组 | 型号 | 与 L 的差别 |
|---|---|---|
| **L（LDO 型）** | H742、H743（IIK/IGK）、H750IBK、H753IIK | — |
| **L'** | H7A3IIK/IGK、H7B3IIK（无 Q） | 只有 C8 不同：L 里是 VDD，L' 里是 VDDMMC |
| **S（SMPS 型）** | H745、H755、H735、H725、H730、H7A3…Q、H7B3…Q、H7B0…Q | 201 个球里 169 个不同（几乎整张图重排） |

- L 组内：H743 / H750 / H753 的规格书里该图的 ST 图号都是 MSv41912V3，每个球的内容相同；FMC SDRAM 的 57 个信号落在完全相同的球上（脚本逐信号比对）。**可以在同一块板、同一份网表上互换，只换 BOM。** 区别只在片内 Flash（H750 只有 128 KB）、加密（H750、H753 有）。
- L' 与 L：FMC 信号位置全部相同。C8 在 H7A3/H7B3 上是 VDDMMC，"不用时接到 VDD"（[DS13195][ds-h7a3] 供电方案一节，VDDMMC 条目），所以接 VDD 的话在球级别是兼容的。ST 在迁移指南里也说 H74x/75x 与 H7A3/7Bx 引脚对引脚兼容，仅 UFBGA176+25 等封装的 BYPASS_REG 位置（球 L4，H7 上是 VSS）有限制（[AN5293][an5293] §4.2 p.12–13）。但外设和复用功能不同，固件不通用，这里不当成"可互换"。
- S 组不能和 L 组互换：[AN5293][an5293] §4.1 明确写 SMPS 封装与旧封装不兼容。S 组内 H745 与 H735 的球图完全相同（脚本比对 0 个球不同），H7A3/H7B3 的 Q 型与它们只差一个球（D5：VDD 或 VDDMMC）。
- UFBGA176+25 的球阵：15 × 15 的 4 圈外环共 176 个球，再加中心 5 × 5 的 25 个球（F6–K10）。两种球图里这 25 个都是 VSS（读 KiCad 符号库，图里这一块也全是 VSS）。

## 4. 32 位 SDRAM 的 FMC 引脚（H743 / L 组球图）

32 位 SDRAM 用到：数据 D0–D31（32）、地址 A0–A12（13，128 Mbit 的 x32 只用到 A0–A11）、BA0/BA1（2）、字节掩码 NBL0–NBL3（4）、SDCLK、SDNCAS、SDNRAS、SDNWE、SDCKE、SDNE（6），共 **57** 个信号，占这个封装 140 个 GPIO 的约 41%；要达到"MCU 引脚占用六成以上"，即 84 个，还要再用 27 个以上。

H743IIK6 上每个信号的位置（球号来自符号库，已按 §1 的方法与规格书核对；括号里是端口）：

| 信号 | 引脚 : 球 |
|---|---|
| D0–D3 | PD14:M14　PD15:L14　PD0:B12　PD1:C12 |
| D4–D12 | PE7:R8　PE8:P8　PE9:P9　PE10:R9　PE11:P10　PE12:R10　PE13:N11　PE14:P11　PE15:R11 |
| D13–D15 | PD8:P15　PD9:P14　PD10:N15 |
| D16–D23 | PH8:M12　PH9:M13　PH10:L13　PH11:L12　PH12:K12　PH13:E12　PH14:E13　PH15:D13 |
| D24–D31 | PI0:E14　PI1:D14　PI2:C14　PI3:C13　PI6:C3　PI7:C2　PI9:D3　PI10:E3 |
| A0–A5 | PF0:E2　PF1:H3　PF2:H2　PF3:J2　PF4:J3　PF5:K3 |
| A6–A9 | PF12:P6　PF13:N6　PF14:R7　PF15:P7 |
| A10–A12 | PG0:N7　PG1:M7　PG2:L15 |
| BA0 / BA1 | PG4:K14　PG5:K13 |
| NBL0–NBL3 | PE0:A4　PE1:A3　PI4:D4　PI5:C4 |
| SDCLK / SDNCAS / SDNRAS | PG8:H14　PG15:B7　PF11:R6 |
| SDCKE0（三选一） | PH2:F4　PC5:P5　PC3_C:M5 |
| SDNE0（三选一） | PH3:G4　PC4:N5　PC2_C:M4 |
| SDNWE（三选一） | PH5:J4　PC0:M2　PA7:R3 |
| SDCKE1 / SDNE1（第二个 bank） | PB5:A6 或 PH7:N12　/　PB6:B6 或 PH6:M11 |

要点：

- 在这个封装里，除 SDCKE / SDNE / SDNWE 外，每个信号只有一个引脚，没有选择余地。EVAL 板用的是 TFBGA240+25，它还有 PJ、PK 端口，我没有核对 EVAL 的 SDRAM 是否只用了这 57 个脚；MB1246 原理图的 SDRAM 页（第 5 页）是矢量文字，没能读出具体网络（见 §9）。
- H750 / H753 / H742 和 H7A3 / H7B3 无 Q 的 FMC 信号位置与上表完全一致（脚本逐信号比对）。
- 此封装上没有 PC2、PC3 的普通球，只有 PC2_C、PC3_C（[DS12110][ds-h743] Table 9 注 3、4）。勘误表指出：只有 PC2_C/PC3_C 的封装上以太网 MII 不能用，要用 RMII（[ES0392][es0392] §2.2.27 p.17）；`Pxy_C` 脚在模拟开关闭合时的拉灌电流限制为 1 mA（§2.2.26，同页）。**SDCKE0 / SDNE0 建议用 PH2 / PH3，不用 `_C` 脚。**
- SDRAM 时钟上限（电气特性章节，20 pF）：H743 / H750 / H753 的 rev V 部分、H745、H7A3、H7B3 在 2.7–3.6 V 下 FMC_SDCLK ≤ 110 MHz，1.8–1.9 V 下 100 MHz（[DS12110][ds-h743] p.266；[DS12556][ds-h750] p.256；[DS12923][ds-h745] p.170；[DS13195][ds-h7a3] p.136；[DS13139][ds-h7b3] p.137）；H743 / H750 / H753 的 rev Y 部分是 100 MHz（[DS12110][ds-h743] p.160）。H735 只有 95 / 90 / 85 MHz（2.7–3.6 / 1.8–1.9 / 1.62–1.8 V，[DS13312][ds-h735] p.188）。H750 封面写"同步模式 133 MHz"，H743 封面写 100 MHz，与各自电气特性章节的 SDRAM 上限都对不上；以电气特性为准。

## 5. 供电方式和对电源树的影响

**L 组（H743 / H750 / H753，以及 L' 组）**

- 只有一个 I/O 电源 VDD（13 个球，C5 C7 C8 C9 F3 G3 G13 J12 J13 K4 N8 N9 N10），1.62–3.6 V；核心电压由内部 LDO 产生，外部只需要 VCAP 两个球（F13、M10）各接 2.2 µF、ESR < 100 mΩ（[DS12110][ds-h743] §6.3.2 p.106，§7.3.2 p.211；AN4938 另要求把 VCAP1 与 VCAP2 互连，[AN4938][an4938] §2.2 p.12）。
- VDDLDO 在这个封装上不引出，内部接到 VDD；VDD50USB 不引出，内部接到 VDD33USB（[DS12110][ds-h743] Table 9 注 6、8，p.88）。USB 要用的话，VDD33USB（H13）要自己供 3.3 V。
- 其余供电球：VDDA（R1）、VSSA（M1）、VREF+（P1）、VREF−（N1）、VBAT（C1）、VDD33USB（H13）。PDR_ON（C6）、BOOT0（D6）、NRST（J1）。
- 对六层测试板的影响：外部电源树最简单，主电源一路 3.3 V（SDRAM 也是 3.3 V 的话），加上 VDDA、VBAT、VDD33USB 的滤波分支，没有电感和开关节点。

**S 组（H745 / H735 / H7A3…Q / H7B3…Q）**

- 多出 VDDSMPS（G1，必须与 VDD 同电压，接 4.7 µF）、VLXSMPS（F1，接 2.2 µH 电感加 220 pF）、VFBSMPS（G2，接 10 µF）、VSSSMPS（F2）；VDDLDO × 3（A3、A13、R14，互连并接 4.7 µF）；VCAP × 3（第三个不需要额外电容）；另外还有 VDD50USB（E15）引出（[AN4938][an4938] §2.2 p.12–13；[DS12923][ds-h745] §3.5.1 p.24；[DS13312][ds-h735] §3.8.1 p.26；球位来自符号库）。
- 要在 BGA 旁边放一只电感和开关节点。供电配置（LDO / SMPS / 直连）没有专用引脚，靠软件在启动时选择，启动时 LDO 和 SMPS 默认都是打开的（[AN5293][an5293] §4.2 p.12，该处讲的是 H74x/75x 与 H7A3/7Bx 的 SMPS 封装）。
- 这一组的球图与 L 不兼容，也不能做 32 位 SDRAM，所以对这块板没有意义，只记下事实。

## 6. 片内 Flash 与启动

- H743IIK6、H753IIK6：2 MB 片内 Flash（[DS12110][ds-h743] p.1），程序放得下，不需要外挂 Flash；BOOT0 球是 D6。启动地址和启动流程细节要读参考手册，这次没有读（§9 第 1 条）。
- **H750IBK6：只有 128 KB Flash**（[DS12556][ds-h750] p.1、订货码 B = 128 Kbytes，§9 p.326）。只能放很小的引导程序，正常应用要外挂 QSPI 或从别处加载到 RAM。这块板只做设计验证、不烧固件，对它不是障碍，但"不外挂 Flash 就能跑"这一条它不满足。
- H745IIK6：2 MB，但是双核（M7 + M4），启动流程更复杂；H735IGK6 1 MB；H7A3/H7B3 IIK6 2 MB。
- "128 KB 只够引导程序"是我从容量做的判断，不是规格书的原话。

## 7. ST 官方参考板

核对了下面六块 ST 评估板的官网页面，**其中没有一块用 UFBGA176+25 的 H743 / H750 / H753 / H745 / H7A3 / H7B3。**（没有穷举 ST 的全部评估板。）

| 评估板 | MCU 与封装（页面原文） | SDRAM | 状态 | 能不能当参考 |
|---|---|---|---|---|
| [STM32H753I-EVAL][board-h753i-eval]（MB1246-H753-E03） | STM32H753XIH6，TFBGA240+25 | 8M×32 位 | Active | **最接近**：同一硅片家族，32 位 SDRAM，SDRAM 的 FMC 接法可以参照；球号和电源脚不同，球图不能照搬 |
| [STM32H743I-EVAL][board-h743i-eval]（MB1246-H743） | STM32H743XIH6，TFBGA240+25 | 8M×32 位 | Obsolete，页面推荐换成 H753I-EVAL | 同上，只是停产 |
| [STM32H735G-DK][board-h735g-dk]（MB1520） | STM32H735IGK6，UFBGA176+25 | **无 SDRAM**，只有 128 Mbit HyperRAM 与 512 Mbit OctoSPI NOR | 页面未取到 | 封装对得上，其余对不上 |
| [STM32H750B-DK][board-h750b-dk] | STM32H750XBH6，TFBGA240+25 | 128 Mbit，位宽页面没写 | Obsolete | 否 |
| [STM32H745I-DISCO][board-h745i-disco] | STM32H745XIH6，TFBGA240+25 | 128 Mbit，位宽页面没写 | Active | 否 |
| [STM32H7B3I-EVAL][board-h7b3i-eval] | STM32H7B3LIH6Q，TFBGA225 | 8M×32 位 | Active | SMPS 型，不是 LDO 球图 |

- AN4938 里的参考原理图是 "STM32H753XI reference schematic"（Figure 18，TFBGA240，[AN4938][an4938] §2.2 p.12 的引用）。
- **H735G-DK 的封装名之争**：[ST 产品页][board-h735g-dk]和 UM2679 §1（Features）写 "UFBGA176+25"，同一份 [UM2679][um2679] 的 §6.1 写 "TFBGA176+25"。MCU 规格书（[DS13312][ds-h735] 封面、Figure 11、§7.10 p.276）和订货码（K = UFBGA 0.65 mm）都是 UFBGA176+25，封装代码 A0E7，10 × 10 mm、0.65 mm，没有 TFBGA176。**按 MCU 规格书，UM2679 §6.1 应是笔误。**
- 本次只下载了 MB1246 的原理图（H743 与 H753 两个版本，各 18 页）；其中 SDRAM 页（第 5 页）转成文字后是乱码，没有读出具体网络；第 2 页的顶层图能看到 FMC_NBL0–NBL3 四根字节掩码，说明该板的 SDRAM 是 32 位。

## 8. 文档齐全度

| 型号 | 规格书 | 参考手册 | 勘误表 | 硬件设计应用笔记 |
|---|---|---|---|---|
| H743 / H750 / H753 | DS12110 / DS12556 / DS12117，2026-01 | [RM0433][rm0433] | [ES0392][es0392] Rev 16（2026-10） | [AN4938][an4938] Rev 7（2024-10） |
| H745 | DS12923 Rev 3，2026-01 | [RM0399][rm0399] | [ES0445][es0445] Rev 7（2026-10） | AN4938（同一份，含 H745/H755/H747/H757） |
| H735 | DS13312 Rev 4，2023-11 | [RM0468][rm0468] | [ES0491][es0491] Rev 9（2024-06） | [AN5419][an5419] Rev 3（2026-01） |
| H7A3 / H7B3 | DS13195 / DS13139 Rev 8，2022-05 | [RM0455][rm0455] | [ES0478][es0478] Rev 12（2025-07） | [AN5307][an5307] Rev 6（2022-03）；迁移指南 [AN5293][an5293] |

- 全部齐全，但 H7A3 / H7B3 的规格书和硬件笔记明显比 H743 家族老（2022 年 vs 2026 年）。
- 参考手册只确认链接有效（HTTP 200），内容没有读。
- ST 产品页对每个型号都提供 IBIS 模型包（STM32H7 IBIS v5.1）、SVD 和 BSDL，可用于以后做 SDRAM 总线的信号完整性（产品页见 §2.2 表）。
- **FMC / SDRAM 的 PCB 布局规则只在 AN4938 和 AN5307 里有 x32 的说明**：AN4938 §9.4.2（p.41）把 SDRAM 信号分成地址、命令、控制、数据四组，要求阻抗 50 Ω ± 10%、走线长 < 120 mm、数据组组内等长 ± 10 mm、SDCLK 与数据 / 地址 / 命令各自匹配 ± 10 mm（最大不超过 20 mm）、数据线与地址 / 控制线分层或相隔 5 mm 以上、3.3 V 下单根走线电容 20 pF 以内、总负载 30 pF 以内。AN5419（H735）只写到 x8 和 x16（两组数据通道），没有 x32，与 H735 只有 24 位吻合。
- 勘误表里的 FMC / SDRAM 条目：[ES0392][es0392] §2.6（p.22–23）共 7 项，和 SDRAM 有关的是：同步存储器突发读尾部多两次空读（无功能影响、无办法）、不支持非对齐地址读（要用编译选项保证对齐）、TRCD / TXSR 与 TWR 两条是文档错误；没有影响 SDRAM 功能的硅缺陷。[ES0445][es0445] 的 FMC 小节是 §2.7（p.21–23），另有一条只对 H745 的 Cortex-M4 字节或半字访问 FMC 可能读错（§2.3.14，p.17）。

## 9. 已验证与未验证

**已在一手资料里验证**

- 七个型号在 UFBGA176+25 的订货号存在、状态 Active（ST 产品页）。
- 封装：10 × 10 mm、0.65 mm 球距、封装代码 A0E7；ST 给的焊盘示例 Dpad = 0.300 mm、阻焊开口 Dsm = 0.400 mm 典型（[DS12110][ds-h743] §8.8 Table 217 p.339，其余六份规格书的同名表相同）。
- 球图分两组（L 与 S），L' 与 L 只差 C8；H743 / H750 / H753 的 FMC 信号位置完全一致。
- H735 / H745 / H7A3…Q / H7B3…Q 在此封装上 FMC 只有 24 位（H735 为规格书明说，其余三个依据球图里没有 PI 端口）。
- L 组 FMC 的 57 个 SDRAM 信号全部引出，且各自在 H743 / H750 / H753 / H7A3 / H7B3 上的球相同。
- 各型号 Flash 容量、供电结构、VCAP 数量、SDRAM 时钟上限。
- 没有 ST 官方板使用本封装的这些型号（只核对了 §7 表里的六块板，没有穷举 ST 的全部评估板页面）。

**没有验证，或只有间接依据**

1. 参考手册（RM0433 等）没有读，FMC / SDRAM 章节里和封装有关的说明、SDRAM 时序寄存器的限制都没核对。
2. MB1246 原理图 SDRAM 页没读出来，ST 在 EVAL 上选了 SDCKE0 / SDNE0 / SDNWE 的哪个备选引脚、有没有串联电阻、端接做法，都未确认。
3. 球图里 E–L 行的列位置：球号以符号库为准，规格书表格只自动核对了 102 / 140 个 GPIO 球；电源球（VSS / VDD / VCAP）只核对了全图的个数，E–L 行没有逐球核对位置。
4. VCAP 电容的接法：规格书写"两颗 2.2 µF 外接电容可以接在 VCAP 脚上"，AN4938 写"两脚都要接 2.2 µF，并把两脚连起来"，细节（一颗还是两颗）以 AN4938 Figure 18 的参考原理图为准，没有看这张图。
5. H7A3 / H7B3 无 SMPS 型的 GPIO 数：规格书 Table 2 看起来是 138（列对应是推断的），我数图是 140，差 2（疑似 PC2_C / PC3_C 计不计），没有核对。
6. H7A3 / H7B3 的硅版本、勘误（ES0478）与 32 位 FMC 的相互影响没有读。
7. 480 MHz 需要 rev V 硅片和 VOS0；订货号里的 "A" 选项（Advanced mission profile）与交货硅版本，没有核对。这块板只做设计验证，影响很小。
8. SDRAM 时钟 100–110 MHz 只是 MCU 侧上限，具体 SDRAM 芯片的时序没有看（属于别的工单）。
9. IBIS 模型包没有下载，没有做任何信号完整性分析。
10. 没有调用 kicad-happy 的 `datasheets` skill；我直接用脚本读 PDF 并与符号库比对，原因是这次是跨七份规格书的球图比对，没有工程可挂缓存。

## 10. 顺带发现（对后续工单有用）

- **焊盘直径**：规格档 C（`docs/rule-profiles/C-bga-065.md`）的球距计算表按焊盘直径 0.35 mm 算；ST 规格书的示例焊盘是 0.300 mm（上文 §9），KiCad 库封装 `Package_BGA:UFBGA-201_10x10mm_Layout15x15_P0.65mm` 的焊盘也是 0.30 mm 圆形，201 个焊盘与上述符号的球号一一对应（脚本核对，符号里的 Footprint 字段就指向它）。按 0.30 mm 算，两个焊盘之间的空隙是 0.35 mm（表里 0.65 − 0.35 = 0.30 mm），与焊盘半径有关的几行余量都会变大。是否把计算表改成 0.30 mm 留给规则阶段（RUL-12）决定；这条不影响选型。
- KiCad 自带的 `STM32H743IIKx`、`STM32H750IBKx`、`STM32H753IIKx` 符号可以直接用，球图与规格书一致。
- 如果选 L 组，SDRAM 的 NBL2/NBL3 在 PI4/PI5，数据 D24–D31 在 PI0–PI3、PI6、PI7、PI9、PI10：这 8 + 2 个球集中在规格书俯视图的上边：左侧 C2、C3、C4、D3、D4、E3，右侧 C13、C14、D14、E14，数据线 D24–D31 加 NBL2/3 的扇出和等长分组要按这两个角来。D0–D23 分散在四边（见 §4 表）：SDRAM 放在 MCU 哪一边，会让这 10 个信号绕得最远。
- 若要做以太网：L 组只能用 RMII（[ES0392][es0392] §2.2.27，见 §4）。

## 11. 推荐

**STM32H743IIK6。**

1. 球图是 L 组：FMC 的 32 位数据线、NBL0–3、全部地址和控制信号都引出，能做 32 位 SDRAM。同组的 H750、H753，以及球图近乎相同的 H7A3 / H7B3（无 Q）也能做；候选里其余四种（H745、H735、H7A3…Q、H7B3…Q）不能。
2. 2 MB 片内 Flash，不外挂 Flash 就能启动，这点 H750 做不到。
3. LDO 供电，只要 3.3 V 主电源加两颗 VCAP 电容，没有电感和开关节点，对"电源面按草图分块"这个验证目标最干净。
4. 文档最全：规格书（2026-01 Rev 11）、RM0433、ES0392、AN4938（含 FMC SDRAM 布局规则），ST 的 32 位 SDRAM 官方参考原理图（STM32H753I-EVAL，MB1246）与它同一个硅片家族。
5. 如果采购时 H743IIK6 不好买，**H753IIK6 可以不改板直接换**（同球图、同 FMC 引脚，只多加密模块）；H750IBK6 也能直接换，但只有 128 KB Flash。

不选 H745 / H735 / H7A3…Q / H7B3…Q：此封装只有 24 位 FMC。不选 H7A3 / H7B3 无 Q：技术上可行，但主频 280 MHz、规格书和硬件笔记是 2022 年的，ST 的官方 32 位 SDRAM 板（H7B3I-EVAL）是 SMPS 型，参考原理图对不上。

---

[ds-h743]: https://www.st.com/resource/en/datasheet/stm32h743ii.pdf
[ds-h750]: https://www.st.com/resource/en/datasheet/stm32h750ib.pdf
[ds-h753]: https://www.st.com/resource/en/datasheet/stm32h753ii.pdf
[ds-h745]: https://www.st.com/resource/en/datasheet/stm32h745ii.pdf
[ds-h735]: https://www.st.com/resource/en/datasheet/stm32h735ig.pdf
[ds-h7a3]: https://www.st.com/resource/en/datasheet/stm32h7a3ii.pdf
[ds-h7b3]: https://www.st.com/resource/en/datasheet/stm32h7b3ii.pdf
[pg-h743]: https://www.st.com/en/microcontrollers-microprocessors/stm32h743ii.html
[pg-h750]: https://www.st.com/en/microcontrollers-microprocessors/stm32h750ib.html
[pg-h753]: https://www.st.com/en/microcontrollers-microprocessors/stm32h753ii.html
[pg-h745]: https://www.st.com/en/microcontrollers-microprocessors/stm32h745ii.html
[pg-h735]: https://www.st.com/en/microcontrollers-microprocessors/stm32h735ig.html
[pg-h7a3]: https://www.st.com/en/microcontrollers-microprocessors/stm32h7a3ii.html
[pg-h7b3]: https://www.st.com/en/microcontrollers-microprocessors/stm32h7b3ii.html
[an4938]: https://www.st.com/resource/en/application_note/an4938-getting-started-with-stm32h74xig-and-stm32h75xig-mcu-hardware-development-stmicroelectronics.pdf
[an5419]: https://www.st.com/resource/en/application_note/an5419-getting-started-with-stm32h723733-stm32h725735-and-stm32h730-value-line-hardware-development-stmicroelectronics.pdf
[an5307]: https://www.st.com/resource/en/application_note/dm00606249-getting-started-with-stm32h7a37b3-line-and-stm32h7b0-value-line-microcontroller-hardware-development-stmicroelectronics.pdf
[an5293]: https://www.st.com/resource/en/application_note/an5293-migration-guide-from-stm32f7-series-to-stmh74x75x-stm32h72x73x-and-stmh7a37bx-devices-stmicroelectronics.pdf
[es0392]: https://www.st.com/resource/en/errata_sheet/es0392-stm32h742xig-stm32h743xig-stm32h750xb-stm32h753xi-device-errata-stmicroelectronics.pdf
[es0445]: https://www.st.com/resource/en/errata_sheet/es0445-stm32h745xig-stm32h755xi-stm32h747xig-stm32h757xi-device-errata-stmicroelectronics.pdf
[es0491]: https://www.st.com/resource/en/errata_sheet/es0491-stm32h72xx73xx-device-errata-stmicroelectronics.pdf
[es0478]: https://www.st.com/resource/en/errata_sheet/es0478-stm32h7a3xig-stm32h7b0xb-and-stm32h7b3xi-device-errata-stmicroelectronics.pdf
[rm0433]: https://www.st.com/resource/en/reference_manual/rm0433-stm32h742-stm32h743753-and-stm32h750-value-line-advanced-armbased-32bit-mcus-stmicroelectronics.pdf
[rm0399]: https://www.st.com/resource/en/reference_manual/rm0399-stm32h745755-and-stm32h747757-advanced-armbased-32bit-mcus-stmicroelectronics.pdf
[rm0455]: https://www.st.com/resource/en/reference_manual/rm0455-stm32h7a3b3-and-stm32h7b0-value-line-advanced-armbased-32bit-mcus-stmicroelectronics.pdf
[rm0468]: https://www.st.com/resource/en/reference_manual/rm0468-stm32h723733-stm32h725735-and-stm32h730-value-line-advanced-armbased-32bit-mcus-stmicroelectronics.pdf
[um2679]: https://www.st.com/resource/en/user_manual/um2679-discovery-kit-with-stm32h735ig-mcu-stmicroelectronics.pdf
[board-h753i-eval]: https://www.st.com/en/evaluation-tools/stm32h753i-eval.html
[board-h743i-eval]: https://www.st.com/en/evaluation-tools/stm32h743i-eval.html
[board-h735g-dk]: https://www.st.com/en/evaluation-tools/stm32h735g-dk.html
[board-h750b-dk]: https://www.st.com/en/evaluation-tools/stm32h750b-dk.html
[board-h745i-disco]: https://www.st.com/en/evaluation-tools/stm32h745i-disco.html
[board-h7b3i-eval]: https://www.st.com/en/evaluation-tools/stm32h7b3i-eval.html
