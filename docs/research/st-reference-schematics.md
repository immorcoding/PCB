# ST 官方参考原理图和使用条款

调研票 [#4](https://github.com/immorcoding/PCB/issues/4)，地图 [#1](https://github.com/immorcoding/PCB/issues/1)。调研日期 2026-11-15。分支 `research/st-reference-schematics`，不合并。

问题：STM32H7（UFBGA176+25，倾向 STM32H743IIK6）加 32 位 BGA SDRAM 的六层测试板，原理图要按网络名在 KiCad 里从 ST 官方板的 PDF 重画。(1) 哪几块官方板分别提供 MCU 最小系统、32 位 SDRAM、USB-C / SWD / 晶振 / 复位这类通用电路；(2) ST 对评估板设计文件的使用条款；(3) ST 硬件设计应用笔记对去耦、VCAP、晶振、复位、BOOT 的硬性要求。

## 0. 结论

1. **没有 ST 官方板用 STM32H743IIK6（UFBGA176+25）。** 唯一同封装的官方板是 MB1520（STM32H735G-DK，STM32H735IGK6），但它是另一颗芯片：球位表、电源脚（SMPS、VDDLDO、三个 VCAP、VDD50USB）都和 H743 不同，而且 H735 的 FMC 最多 24 位数据、没有 NBL2/NBL3，**做不了 32 位 SDRAM**。所以"按 ST 官方板重画"对 MCU 核心只能做到按网络名和电路拓扑抄，球号一律从 H743 数据手册的引脚表来，不能从任何 ST 板的 PDF 来（见第 3 节）。
2. **(a) MCU 核心电路**：拓扑和数值抄 AN4938 图 18（第 36 页）；实板对照抄 **MB1246 H743-E03 的第 3、4 页**（同一颗 H743 芯片，TFBGA240+25）；MB1520 的第 3、4 页只当旁证。
3. **(b) 32 位 SDRAM 电路**：抄 **MB1246 H743-E03 第 5 页**（U15 IS42S32800J-6BLI，D0–D31 全接）加第 3 页的 33 Ω 串阻。MB1381 的 SDRAM 页是 32 位芯片按 16 位用，MB1332 是 16 位芯片，都不是 32 位总线的接法。
4. **(c) 通用电路**：USB-C 设备（CC 加 ESD）抄 **MB1737 第 10 页左上角**；SWD / Tag-Connect 抄 **MB1520 第 15 页（TAG）加第 17 页的 ESD**；HSE 晶振、LSE 晶振、NRST、BOOT0、PDR_ON、VCAP、VDDA / VREF+、VBAT 抄 **MB1246 H743-E03 第 3、4 页**，细节见第 6 节。
5. **使用条款**：评估板 PDF 第 1 页写明受 **Open Platform License Agreement（OPLA）** 约束。**LICENSE 条款允许"use, modify, copy and distribute"，目的限于"evaluating, testing, and developing application boards based on ST products"**，所以在自己的板子上复用并重画这些电路是允许的；**RESTRICTIONS 条款禁止把 Reference Material 本身出售、出租或另行分发，也不许用 ST 的名称和商标为衍生产品背书**。详见第 7 节。
6. **应用笔记**：H74x/H75x 对应的是 **AN4938**（Rev 7，2024-10），**不是 AN5419**。AN5419 是 H723/733、H725/735、H730 的。两份笔记的数值有差别，不能混用。AN4938 的硬性要求清单见第 8 节。

## 1. 怎么查的，标记含义

PDF 下载到临时目录（不在仓库里），用 `pdftotext` 取文字层，用 `pdftoppm` 把页面渲染成图后逐页看。ST 的原理图是 Altium 导出的 PDF，文字层里网络名和位号被重复、打散，所以数值以渲染图为准，再用文字层核对器件型号和数值是否出现。

- **【核】**：在一手来源（ST 的 PDF、数据手册、应用笔记、用户手册）里读到，标了页号或图号。
- **【图】**：只从渲染图上读到（位号对应到哪个引脚这类关系，文字层给不出）。器件型号和数值已用文字层核对过的会写"文字层核对"。
- **【未核】**：没有在一手来源里确认，集中列在第 10 节。

## 2. 候选板和原理图 PDF

| 板 | 用途 | MCU / 封装 | 原理图 PDF | 版本 | SDRAM |
|---|---|---|---|---|---|
| MB1246 H743-E03（STM32H743I-EVAL2） | MCU 核心、32 位 SDRAM、复位 / BOOT / 晶振 | STM32H743XIH6，TFBGA240+25 | [mb1246-h743-e03_schematic.pdf](https://www.st.com/resource/en/schematic_pack/mb1246-h743-e03_schematic.pdf) | 第 1 页：Revision E-03，2022-05-23，共 18 页；产品页：v1.0，2022-09-13 | U15 IS42S32800J-6BLI，8M×32 位（第 5 页；UM2198 Rev 5 第 79 页） |
| MB1246 H753-E03 | 同上，H753 变体 | STM32H753XIH6，TFBGA240+25 | [mb1246-h753-e03_schematic.pdf](https://www.st.com/resource/en/schematic_pack/mb1246-h753-e03_schematic.pdf) | 同上 | 同上 |
| MB1520 C-03（STM32H735G-DK） | 同封装旁证、TAG 页、USB 页 | STM32H735IGK6，UFBGA176+25 | [mb1520-h735i-c03-schematic.pdf](https://www.st.com/resource/en/schematic_pack/mb1520-h735i-c03-schematic.pdf) | 第 1 页：Revision C-03，2024-12-19，共 19 页；产品页：v1.0，2025-01-15 | 无 SDRAM，第 10 页是 HyperRAM（产品页：128 Mbit） |
| MB1381 B-04（STM32H750B-DK） | SDRAM 的另一种接法 | STM32H750XBH6，TFBGA240+25 | [mb1381-h750xb-b04.pdf](https://www.st.com/resource/en/schematic_pack/mb1381-h750xb-b04.pdf) | 第 1 页：Revision B-04，2024-09-27，共 19 页；产品页：v1.0，2024-11-04 | U7 IS42S32400J-6BL（第 9 页），按 16 位用 |
| MB1332 C-03（STM32H7B3I-DK） | 16 位 SDRAM 对照 | STM32H7B3LIH6Q，TFBGA225（第 3 页标题） | [mb1332-h7b3i-c03-schematic.pdf](https://www.st.com/resource/en/schematic_pack/mb1332-h7b3i-c03-schematic.pdf) | 第 1 页：Revision C-03，2023-12-11，共 17 页 | U14 IS42S16800F-6BLI，16 位（第 5 页） |
| MB1737 B-02（NUCLEO-H7S3L8） | 只取 USB-C 电路 | STM32H7S3L8（H7R/S 系列，不是 H743） | [mb1737-h7s3l8-b02-schematic.pdf](https://www.st.com/resource/en/schematic_pack/mb1737-h7s3l8-b02-schematic.pdf) | 第 1 页：Revision B-02，2023-09-07，共 11 页 | — |

- 【核】MB1246 H743 与 H753 两个变体的第 3、4、5 页，文字层逐行比对只差"Variant"一行，网络和器件相同。H743 变体更贴近目标芯片，建议引用 H743 的链接。
- 【核】STM32H743I-EVAL 的产品页把它标为 Obsolete 并推荐 STM32H753I-EVAL；UM2198 Rev 5 说 MB1246 RevE 对应现行的 EVAL2 版本（第 79 页的版本表有 H743-E03 / H753-E03）。
- 【核】本次读过的所有 PDF（MB1246 两个变体、MB1332、MB1381、MB1520、MB1737）第 1 页都带 OPLA 文字，见第 7 节。
- 产品页上的版本号和日期来自对 st.com 产品页的抓取摘要，没有在 PDF 里再核；PDF 内部的 Revision 和日期是【核】。

## 3. 关键发现：H743IIK6 和 H735IGK6 的 UFBGA176+25 球位完全不同

来源：DS12110 Rev 11 图 10（第 60 页，STM32H742xI/G 和 H743xI/G）；DS13312 Rev 4 图 11（第 62 页，STM32H735xG）。两张都渲染成图读过。

| 项 | H743xI（DS12110） | H735xG（DS13312，MB1520 用的芯片） |
|---|---|---|
| A1 球 | PE3 | VSS |
| VCAP 球 | 2 个：F14、M10 | 3 个：A4、A14、R13 |
| VDDLDO 球 | 没有 | 3 个：A3、A13、R14 |
| SMPS 球 | 没有 | VLXSMPS、VSSSMPS、VDDSMPS、VFBSMPS（F1、F2、G1、G2） |
| USB 供电球 | 只有 VDD33USB（H13） | VDD50USB（E15）和 VDD33USB（F13） |
| PI 口 | PI0–PI11 都有 | 一个都没有 |
| PDR_ON / BOOT0 / NRST | C6 / D6 / J1 | D4 / C5 / L1 |
| OSC_IN / OSC_OUT（PH0 / PH1） | G1 / H1 | J1 / K1 |
| VREF- | N1（有，要接 VSSA） | L4（有） |
| FMC 数据宽度 | 8 / 16 / 32 位（DS12110 §3.15，第 36 页） | 最多 24 位，"without NBL2-3"（DS13312 第 21 页表注 1 和第 35 页 FMC 一节） |
| VDD 球数 | 13 个（按图 10 数得） | 未数 |

- 【核】H743 的 FMC 32 位数据口 D24–D31 在 PI 口上（PI0–PI3、PI6、PI7、PI9、PI10），所以 H735 的 UFBGA176+25 没有 PI 口就不可能有 32 位总线。MB1520 用 HyperRAM 而不是 SDRAM，与此一致。
- 【核】DS12110 表 2 注 1：SDRAM "is not available on the LQFP100 or TFBGA100 packages"，UFBGA176+25 不在排除之列。
- 【核】MB1246 用的 TFBGA240+25 是 H743 同一颗芯片，电源和外设电路的拓扑可以直接参照，但球号不同，**球号一律从 DS12110 表 9 的 UFBGA176+25 列取**（对应 RUL-6：大芯片引脚对官方引脚表用脚本比）。
- 【图】13 个 VDD 球是数图 10 得到的：C5、C7、C8、C9、F3、G3、G13、J12、J13、K4、N8、N9、N10。后面的"13 个 100 nF"依赖这个数，建议原理图阶段用引脚表脚本复核。

地图里的"已定：以 ST 官方板的 PDF 为准"对 MCU 核心做不到字面照抄；如果想要 1:1 抄 MB1520，就得换成 H735IGK6，但那样没有 32 位 FMC，和"SDRAM 用 32 位"的已定项冲突。选择权在用户，见第 9 节。

## 4. (a) MCU 核心电路：抄哪里

| 内容 | 来源 | 说明 |
|---|---|---|
| 最小系统的拓扑和数值（电源、复位、BOOT、晶振、JTAG、去耦） | AN4938 Rev 7 图 18（第 36 页）和表 8、表 9（第 35 页） | ST 自己的 H74x/H75x 最小系统，参照芯片 H753XI TFBGA240+25 【核】 |
| 同一颗芯片的实板实现 | MB1246 H743-E03 第 3 页（MCU I/O）、第 4 页（电源） | 第 3 页含 HSE / LSE / NRST / BOOT0 / PDR_ON；第 4 页含 VDD 去耦、VDDA、VREF+、VBAT、VDD33USB、VCAP |
| 同封装旁证 | MB1520 第 3 页（MCU IOs）、第 4 页（MCU POWER） | 只看 NRST / BOOT0 / PDR_ON / LSE / ESD 的做法；**不要**用第 4 页的电源，里面是 H735 的 SMPS、VDDLDO、三个 VCAP |
| 球号和 MCU 符号的引脚表 | DS12110 表 9（UFBGA176+25 列）和图 10 | 不来自任何 ST 板 |

把 MB1246 第 4 页改到 UFBGA176+25 时要改的地方：
- VDDLDO、VDDSMPS、VLXSMPS、VFBSMPS、VDDDSI、VCAPDSI 这些脚在 H743IIK6 上没有，整块删掉；SMPS / LDO 模式表和阻焊桥（SB）都不要。
- VCAP 只有两个球（F14、M10），各配 2.2 µF（第 6 节 VCAP 行）。MB1246 有三个 VCAP 球，布了 C18、C22、C30 三个 2.2 µF；旁边还有 4.7 µF 的 C15、C28 位置，图上带红叉，应是 SMPS 模式才贴，没有逐个确认【图】。
- 没有 VDD50USB，MB1246 里 SB19 连到 VDD_MCU 的那一路不需要。VDD33USB 在 H13。
- VDD 去耦数量按 13 个球算（MB1246 是 20 个球，20 个 100 nF 加一个 4.7 µF 【图】，文字层核对 100 nF 和 4.7 µF 都出现）。

## 5. (b) 32 位 SDRAM 电路

### 5.1 MB1246 H743-E03：真正的 32 位总线

【核】第 5 页标题"SRAM & FLASH & SDRAM"：

- U15 **IS42S32800J-6BLI**，90 球，数据口 DQ0–DQ31 全接 D0–D31，DQM0–DQM3 接 FMC_NBL0–NBL3（NBL0 / NBL1 在 PE0 / PE1，NBL2 / NBL3 在 PI4 / PI5）。型号出处：第 5 页文字层；UM2198 Rev 5 第 79 页版本表写明 "IS42S32800G-6BLI replaced by IS42S32800J-6BLI"；UM2198 特性页写 "8 M×32bit SDRAM"。
- 地址：A0–A11 接总线的 A0–A11；**BA0 接 A14、BA1 接 A15**（网络名，对应 PG4 / PG5 的 FMC_BA0 / BA1）。
- 控制：SDNWE = PH5，SDNCAS = PG15，SDNRAS = PF11，SDNE1 = PH6，SDCKE1 = PH7（中间串 R282，0 Ω），SDCLK = PG8。
- 去耦：电源 3V3，标"Place close SDRAM"，**14 个 100 nF**（C142–C145、C149–C152、C156–C161，一一对应 14 个供电球：10 个 VDDQ 加 4 个 VDD），没有大电容。【图】数得，文字层核对整页 100 nF 共 20 个，减去 SRAM 和 NOR 的 5 个和 C33 恰为 14。
- SDRAM 侧**没有串联电阻**（唯一的 R282 是 SDCKE1 上的 0 Ω），也没有端接。
- 第 3 页（MCU I/O）：多数 FMC 脚与总线之间有 **33 Ω 串阻**（例：PG8 一路 R268，PF0 一路 R224，PH2 / PH3 一路 R228 / R235）；NBL0–NBL3（PE0、PE1、PI4、PI5）直连，没有串阻。【图】没有逐根枚举，不能说"所有 FMC 脚"。
- 注意：总线 D[0..31]、A[0..23] 上同时挂着 SRAM（U16）和 NOR（U12），拓扑和等长情况与"只挂一颗 SDRAM"不同，不能照抄走线拓扑，只抄接法和电源。

### 5.2 MB1381 B-04：32 位芯片按 16 位用

【核】第 9 页：U7 IS42S32400J-6BL（4M×32，从型号和产品页"128-Mbit SDRAM"得出，没有对 ISSI 规格书）。

- MCU 只给 SDRAM_D[0..15]、NBL0 / NBL1；DQ16–DQ31 每根经 10 kΩ 接地，DQM2 / DQM3 经 10 kΩ 接地【图】。**所以这页不是 32 位总线的接法**，只能参考"x32 芯片上不用的字节怎么处理"。
- 地址 SDRAM_A[0..11]、BA0 / BA1、SDNE1、SDCKE1、SDCLK 等；第 3 页上数据、地址、BA、NBL、SDNWE / SDNRAS / SDNCAS / SDNE1 / SDCKE1 和 SDCLK（R80）都可见 33 Ω 串阻【图】（文字层有 "33R" 字样）。
- 去耦：14 个 100 nF（文字层核对）。

### 5.3 MB1332 C-03：16 位芯片

【核】第 5 页：U14 IS42S16800F-6BLI（8M×16），D0–D15、A0–A11、BA 接 A14 / A15、SDCKE1 = PH7（串 R67 0 Ω）、SDNE1 = PH6、SDCLK = PG8；去耦 7 个 100 nF 加 1 个 4.7 µF（C14）（文字层核对数量）。

### 5.4 对 SDRAM 型号票（#3）的交接

三块板的 SDRAM 型号都是 ISSI：IS42S32800J-6BLI（256 Mbit x32）、IS42S32400J-6BL（128 Mbit x32）、IS42S16800F-6BLI（128 Mbit x16）。**型号取自原理图，没有对 ISSI 规格书核对**，那是 #3 的事。

## 6. (c) 通用电路：每个电路抄哪块板哪一页

| 电路 | 最佳来源 | 读到的内容 |
|---|---|---|
| **USB-C 设备（CC 电阻 + ESD）** | **MB1737 第 10 页左上角**（ST-LINK 部分） | 【核】CN5 USB_C_12401826E412A；CC1、CC2 各经 5K1 到地（R93、R90，文字层有两处 "5K1"）；VBUS 上 U20 ESDA25P35-1U1M；D+ / D- 经 U21 ECMF2-40A100N6（共模滤波加 ESD）；CC 另经 100K 加 10 nF（R92 / C44、R89 / C43）接到 ST-LINK 芯片的 ADC 引脚（探测用，设备端非必须）【图】 |
| 同上，主控侧的 USB-C | MB1737 第 8 页 | 【核】双角色 USB-C，TCPP03（U8）加两颗 STL40DN3LLH5 做 UCPD 供电路径，CC 线上 560 pF；对"只做设备"偏重，只取 VBUS 的 ESDA25P35-1U1M、D+ / D- 的 ECMF2-40A100N6 和 C8（2.2 µF）的接法 |
| H743 / H735 / H750 / H7B3 的官方板 | 无 USB-C | 【核】MB1520 第 7 页是 Micro-AB（47590-0001）加 USBLC6-4SC6 加 VBUS 开关 STMPS2151STR；MB1246 用 Micro-AB（UM2198 特性页"3 USB interfaces with Micro-AB connector"） |
| **SWD / Tag-Connect** | **MB1520 第 15 页（TAG）** | 【图】CN21 只有封装（划了叉，不贴），注明 "Only footprint with Cable: TC2050-IDC-NL"；脚位：1 = 3V3，2 = JTMS（PA13），3 = GND，4 = JTCK（PA14），5 = GND，6 = JTDO / TRACESWO（PB3），7 = 无连接（键位），8 = JTDI（PA15），9 = NJTRST（PB4），10 = NRST；每根线串 22 Ω（R152、R153、R147、R148、R150、R151，文字层核对 22R）；页内注 "Place this connector close to STDC, they will share the same ESD components" |
| 同上的 ESD | MB1520 第 17 页 | 【核】STDC14 接口上 U16 / U18 ESDALC6V1W5，U34 ESDALC6V1-1U2（JTDI）；STDC14 的 SWD 线串 22 Ω |
| 20 针 JTAG 的上下拉 | AN4938 图 16（第 31 页）、图 18（第 36 页） | 【核】10 k 上下拉，nSRST 接 NRST |
| **HSE 晶振 + 负载电容** | **MB1246 H743-E03 第 3 页** | 【核】X1 NX3225HA-25MHz-EXS00A-CH00343，C8 / C9 各 3.9 pF（文字层核对两个 3.9pF），OSC_IN / OUT 各串 0 Ω（R15 / R16）。AN4938 图 18 同样是 25 MHz、3.9 pF，无串阻。MB1520 和 MB1381 用的是 3.3 V 有源晶振加 51 Ω，不是晶体加电容，不要抄这一路 |
| **LSE 晶振 + 负载电容** | **MB1246 H743-E03 第 3 页** | 【核】X2 NX3215SA-32.768KHZ-EXS00A-MU00525，C10 / C11 各 1.5 pF，串 0 Ω（R17 / R18）；MB1520（X2，C48 / C45 1.5 pF，R62 / R54 0R）、MB1381（X2，C62 / C70 1.5 pF，R93 / R98 0R）和 AN4938 图 18 也是 1.5 pF |
| **NRST** | **MB1246 H743-E03 第 3 页** | 【核】按键 B1（TD-0341）、100 nF 到地（C94）、ESDALC6V1-1U2（D19）；MB1520 第 3 页：C32 100 nF（"Capacitor close to MCU"）、U31 ESDA7P60-1U1M、按键 B1；AN4938 图 18：C7 100 nF 加按键 B1 |
| **BOOT0** | MB1246 H743-E03 第 3 页 | 【图】R3 10 K 下拉，拨动开关 SW1 可接 3V3；MB1520 第 3 页 R149 10K 下拉加滑动开关 SW1；MB1381 第 3 页 R143 10K 下拉（R144 不贴）；AN4938 图 18 同样 10 K（R5）加开关 SW1 |
| **PDR_ON** | MB1246 H743-E03 第 3 页 | 【图】R247 10K 上拉到 3V3（R249 不贴）；MB1520 第 3 页 R63 10K 上拉（R64 不贴）；AN4938 图 18：R6 10K 上拉，R7 不贴 |
| **VCAP** | AN4938 §2.2（第 12 页）；DS12110 §6.3.2 表 15（第 106 页）；实板 MB1246 第 4 页 | 【核】每个 VCAP 2.2 µF（典型值，±20 % 可接受），ESR < 100 mΩ；"Two external capacitors can be connected to VCAP pins"；旁路稳压器时改成两个 100 nF。MB1246 布 C18、C22、C30 三个 2.2 µF（三个球）【图】 |
| **VDDA / VREF+ 滤波** | MB1246 第 4 页；MB1520 第 4 页；AN4938 图 18 | 【图】MB1246：VDD_MCU 经 R2（0 Ω）到 VDDA，VDDA 经 R216（0 Ω）到 VREF+；VDDA 上 C107 1 µF 加 C109 100 nF，VREF+ 上 C106 1 µF 加 C110 100 nF。MB1520：VDD_MCU 经磁珠 L5（FCM1608KF-601T03）到 VDDA，R139（0 Ω）到 VREF+；VDDA 上 C123 1 µF 加 C122 100 nF，VREF+ 上 C120 10 µF 加 C121 100 nF。AN4938 图 18 同样用 FCM1608KF-601T03 磁珠和 0 Ω（R4） |
| **VBAT** | MB1246 第 4 页 | 【图】JP11 三脚排针，在 +3V3 和 BT1（CR1220 座）之间选；AN4938 §2.2：不用电池时必须接外部电源，例如经 100 nF 接 VDD |
| **VDD33USB** | MB1246 第 4 页 | 【图】SB22 闭合到 VDD_MCU，加 C29 1 µF X5R 0603；UFBGA176+25 的 H743 没有 VDD50USB 球 |

MB1246 第 4 页的 USB 供电、MB1246 第 9、10 页的 USB OTG 电路、RS232 等没有读（本板用不到）。

## 7. 使用条款

### 7.1 哪份协议

【核】每份 ST 评估板原理图 PDF 的第 1 页都印着 **OPEN PLATFORM LICENSE AGREEMENT**，并写 "The complete Open Platform License Agreement can be found on www.st.com/opla"，还写 "The use of the Reference Material automatically implies the acceptance of the Agreement terms and conditions"。本次读过的 6 份 PDF 全部如此：MB1246 H743 与 H753、MB1332、MB1381、MB1520、MB1737。

全文来自 [st.com/opla](https://www.st.com/opla)，重定向到 [open_platform_license_agreement.pdf](https://www.st.com/resource/en/license_agreement/open_platform_license_agreement.pdf)。3 页，PDF 元数据标题是 "Open Reference Material License Agreement v5"，页脚写 "Aug 2016"（第 1 页）和 "September 2016"（第 2、3 页）。

产品页（STM32H735G-DK、STM32H743I-EVAL、STM32H750B-DK、NUCLEO-H7S3L8）只有站点使用条款和销售条款的链接，**没有**单独的设计文件许可证。MB1520 等还提供 Altium 工程 ZIP（如 `mb1520_bdp.zip`），本次没有下载，里面有没有另外的许可证文件【未核】。

### 7.2 条款原文和对本项目的含义

【核】LICENSE：

> ST grants You the right to use, modify, copy and distribute the Reference Material for the purpose of evaluating, testing, and developing application boards based on ST products.

【核】RESTRICTIONS：

> Except as otherwise permitted herein, the Reference Material may not be offered for sale, sold, leased or otherwise distributed. You may not use the name, logo, or any other trademark of ST or any other STMicroelectronics company to endorse or promote products derived from the Reference Material without ST's prior written permission.

OWNERSHIP 条款：Reference Material 的所有权仍归 ST，用户"agree to prevent any unauthorized copying"。NO WARRANTY：按"AS IS"提供，用户自己判断是否适合。LIMITATION OF LIABILITIES：ST 的责任上限是购买价。TERMINATION：违约时 ST 可终止，用户须销毁或归还全部副本。适用瑞士法，日内瓦法院管辖。

对本项目（以下是我的解读，不是法律意见）：

- **允许复用**：这块板的目的是验证设计，属于"evaluating, testing, and developing application boards based on ST products"，在自己的板子上按网络名重画 ST 的电路、改数值、复制，都在 LICENSE 条款内。
- **不要放进成品里的东西**：ST 的 Logo、名称、图框（title block 里有 ST 标志）不要带进我们的原理图和丝印，更不要用来给我们的板子背书。
- **不要转手 ST 的文件本身**：PDF 和 Altium 工程不要打包出售或发布。仓库现在是私有的；如果将来公开仓库，公开的内容里有 ST 文件的逐页复制不合适，自己重画的原理图是否算"distribute the Reference Material"条款没有明说，LICENSE 条款的"distribute"和 RESTRICTIONS 条款的"otherwise distributed"之间有张力【未核】。
- **不要把 ST 派生内容再授权给别人**：这些材料不能重新放在 GPL 之类的开源许可证下。（地图里的"立创开源平台上同类板是 GPL-3.0，只看不导入"与此无关，不冲突。）
- **量产出售**：协议只说"developing application boards"，没有明说量产出售板子的情况；本项目只做设计验证，不涉及，【未核】。
- **AN4938 图 18 的许可**：应用笔记末尾只有通用声明 "No license, express or implied, to any intellectual property right is granted by ST herein"，没有提 OPLA。把图 18 当参考电路按功能重画（本项目本来就这样做）没有问题；不要原样复制图。UM2198 的末页同样是这条通用声明。

## 8. AN4938 对 H74x / H75x 的硬性要求

文档：[AN4938 Rev 7，2024-10](https://www.st.com/resource/en/application_note/an4938-getting-started-with-stm32h74xig-and-stm32h75xig-mcu-hardware-development-stmicroelectronics.pdf)，46 页。**适用 H742、H743/753、H745/755、H747/757、H750 Value**（第 1 页表 1）。页号是文档印刷页号。"必须"指原文用了 must / mandatory / shall，"推荐"指原文是 recommended 或示例。

| 项 | 要求 | 位置 | 级别 |
|---|---|---|---|
| VDD 范围 | 1.71–3.6 V；降到 1.62 V 要外部电源监控器且 PDR_ON 接 VSS | §2.1 第 7 页；§2.3.6 第 17 页 | 必须 |
| VDD 去耦 | 每个 VDD 脚一个 100 nF 陶瓷；整个封装另加一个 ≥4.7 µF 的钽或陶瓷；去耦电容放在脚的下方或尽量靠近 | §2.2 第 12 页；§7.4 第 32 页 | 必须 |
| VDDA | 两个电容：100 nF 陶瓷加 1 µF 钽或陶瓷；VDDA 最低电压按外设：ADC / 比较器 1.62 V，DAC 1.8 V，OPAMP 2.0 V | §2.2 第 12 页；§2.1.1 第 7–8 页 | 必须 |
| VREF+ / VREF- | VREF+ 可接 VDDA；单独供电时要 100 nF 加 1 µF，且必须低于 VDDA；**VREF- 有这个脚时必须外部接到 VSSA**（UFBGA176+25 有 VREF-） | §2.1.1 第 7 页；§2.2 第 12 页 | 必须 |
| VCAP | 每个 VCAP 脚 2.2 µF 陶瓷，ESR < 100 mΩ；VCAP1 与 VCAP2 连在一起。DS12110 表 15：2.2 µF ±20 %，ESR < 100 mΩ；旁路稳压器时改为两个 100 nF | §2.2 第 12 页；DS12110 §6.3.2 第 106 页 | 必须 |
| VDDLDO | 有这个脚的封装要连到一起，并接 4.7 µF（H743 的 UFBGA176+25 没有此脚） | §2.2 第 12 页 | 必须（不适用） |
| VDD33USB（UFBGA176+25 有，没有 VDD50USB） | 3.0–3.6 V；**必须接一个外部电容**（§2.2 在 VDD50USB 与 VDD33USB 相连的情形写 100 nF 加 1 µF；MB1246 只用了 1 µF）；若是独立电源，要最后上电、最先断电，上下电过程中 VDD33USB < VDD + 300 mV | §2.1.2 第 8 页；§2.2 第 12 页 | 必须 |
| VBAT | 不用电池也**必须**接到外部电源，例如经 100 nF 接 VDD；PDR_ON 接 VSS 时必须接到 VDD；VBAT 与 VDD 压差大时有电流倒灌风险，建议加低压降二极管 | §2.2 第 12 页；§2.1.3 第 10 页；§2.3.6 第 18 页 | 必须 |
| PDR_ON | 接高电平启用内部电源监控；接 VSS 时必须由外部监控器管 NRST（例：STM1061N16 加 100 nF） | §2.3.1 第 15 页；§2.3.6 第 17–18 页 | 必须 |
| NRST | 低电平有效，内部有上拉；AN 没有规定外部元件，参考设计加 100 nF 和按键 | 图 6 第 17 页；图 18 第 36 页 | 推荐 |
| BOOT0 | 要有确定电平；图 14 给出下拉加开关的接法，"Resistor values are given only as a typical example" | §5.2 第 26 页 | 必须有电平，阻值推荐 |
| HSE | 4–48 MHz；CL1 / CL2 取 5–25 pF 的高质量陶瓷，两者串联等于晶体规定的负载电容，选值时要计入 PCB 和 MCU 引脚电容（粗估 10 pF）；靠近振荡脚。需要精确以太网、USB HS、I2S、SAI 时用 25 MHz | §4.1.2 第 22 页 | 推荐（靠近是必须） |
| LSE | 32.768 kHz，靠近引脚，负载电容按晶体调；OSC32_IN / OUT 兼作 GPIO 时不建议同时用作 RTC 和 GPIO | §4.2 第 22–23 页 | 推荐 |
| SWD / JTAG | 引脚 PA13 / PA14 / PA15 / PB3 / PB4。内部：NJTRST、JTDI、JTMS 上拉，TCK 下拉；外部接到别的电压会漏电；TCK 在 JTAG 口被释放前不能翻转 | §6.3 第 29–31 页 | 必须 |
| 未用引脚 | 不要悬空，上拉或下拉，未用外设关掉 | §7.6 第 33 页 | 推荐 |
| 叠层 | 最好多层板，GND 和 VDD 各一层；最少四层或六层；SDRAM / SRAM / NOR / LCD 很多的密集板可能要八层 | §7.1 第 32 页；§9.1 第 37 页 | 推荐 |
| 六层叠层示例 | L1 高速信号加 GND，L2 GND，L3 电源，L4 低速信号，L5 GND，L6 高速信号加 GND（**与规格档 C 的叠层顺序相同**） | 图 20 第 38 页（渲染图核对） | 示例 |
| BGA 去耦位置 | 去耦电容放在 PCB 的**另一面**，尽量靠近电源和地球；尽量多的 VDD / GND 对都加；电容焊盘用宽而短的线或过孔接平面。原文 "The following recommendations shall be followed" | §9.3 第 38–39 页，图 21、22 | 必须（shall） |
| FMC / SDRAM 走线（§9.4.2，第 41 页） | 阻抗 50 Ω ±10 %；单根走线 < 120 mm，超过必须端接；数据线与地址 / 控制线走不同层，同层则相隔至少 5 mm；数据组（一个字节通道，8 根数据加 DQM）组内长度差 ±10 mm；SDCLK 走内层，与其他信号至少 3 倍线宽，少过孔，不蛇形；SDCLK 与数据 / 地址组长度差 ±10 mm；SDCLK 与地址、命令组每根信号 ±10 mm（最大 ≤ 20 mm）；容性：3.3 V 下单根 ≤ 20 pF、整个 FMC 总负载 ≤ 30 pF（1.8 V 为 15 / 20 pF）；参考平面用 GND 或 PWR（PWR 要在电源和地之间加 10 nF 缝合电容） | §9.4.2 第 41 页 | 必须 |
| 表 8"必需元件"（TFBGA240+25 的参考设计） | 20 个 100 nF、1 个 4.7 µF、2 个 2.2 µF | 第 35 页 | 按 UFBGA176+25 的球数折算 |

按这张表，UFBGA176+25 的 H743IIK6 至少要：13 个 100 nF 加 1 个 4.7 µF（VDD）；VDDA 的 100 nF 加 1 µF；VREF+ 的 100 nF 加 1 µF（若不直接接 VDDA）；两个 2.2 µF（VCAP）；VDD33USB 的 100 nF 加 1 µF；VBAT 的 100 nF（接 VDD 时）；VREF- 接 VSSA；PDR_ON 接高。

### 8.1 另外几份"Getting started"笔记的对应关系

| 芯片系列 | 笔记 | 状态 |
|---|---|---|
| H742 / H743 / H750 / H753 / H745 / H755 / H747 / H757 | **AN4938** | 本次读过全文 |
| H723 / H733 / H725 / H735 / H730 | **AN5419** Rev 3（2026-01），52 页 | 读过全文。数值与 AN4938 不同：VBAT 要 1 µF 加 100 nF；VDDLDO 要 4.7 µF 加 100 nF；有 SMPS 要 VDDSMPS、电感、VFBSMPS 等；第三个 VCAP 不加电容。SDRAM 走线要求与 AN4938 基本相同 |
| H7A3 / H7B3 / H7B0 | AN5307 | 只从搜索结果的标题得知，没有打开【未核】 |
| H7R / H7S | AN5935 | 只从搜索结果的标题得知，没有打开【未核】 |

"AN5419 对应 H74x/H75x"这个说法有误：AN5419 的标题是 "Getting started with STM32H723/733, STM32H725/735 and STM32H730 MCU hardware development"，PDF 的"Reference documents"一栏也写的是 RM0468 和 H72x / H73x 数据手册。

## 9. 对其他票和对 docs/shape 的影响

- **MCU 选型**：H743IIK6 保留 32 位 FMC，但没有 1:1 的 ST 参考板；换 H735IGK6 能 1:1 抄 MB1520，但没有 32 位 FMC（DS13312）。这会改变地图里"SDRAM 用 32 位"的已定项，应让用户知道取舍。
- **SDRAM 线序票**（地图的"未指定"项）可以直接吃第 8 节 §9.4.2 的数字：±10 mm 数据组内、±10 mm / 最大 20 mm 的时钟对地址命令、数据与地址控制异层或 ≥5 mm、50 Ω ±10 %。
- **规格档 C**（`docs/rule-profiles/C-bga-065.md`）的叠层与 AN4938 图 20 同序。另外 DS12110 表 217（第 339 页，UFBGA176+25 的 PCB 设计规则示例）给的是：Dpad 0.300 mm，Dsm 典型 0.400 mm（取决于阻焊对位公差），钢网开口 0.300 mm，钢网厚度 0.100–0.125 mm，焊盘引出线宽 0.100 mm。规格档 C 的球距计算表用的焊盘直径是 0.35 mm、区内线宽 0.09 mm，与 ST 的示例不同，做球距计算表（RUL-12）时要对这个数。
- **未核对项**累积到地图（PROC-8）：第 10 节。

## 10. 未核对项

1. **USB Type-C 的 CC 5.1 kΩ**：只在 MB1737 第 10 页看到 R93 / R90 的 5K1，没有对照 USB Type-C 规范原文（usb.org）。
2. **TC2050-IDC 的脚位**：从 MB1520 第 15 页的渲染图读出，没有对照 Tag-Connect 官方资料。
3. **FMC 信号到 UFBGA176+25 具体球号的映射**：只核到 DS12110 §3.15 支持 32 位、表 2 注 1 允许 SDRAM、图 10 里有 PH8–PH15 和 PI0–PI11，没有把 D0–D31、A0–A12、BA0 / BA1、NBL0–3、SDNWE / SDNRAS / SDNCAS / SDCLK / SDNE / SDCKE 逐个对到球号；MB1246 用的端口在 UFBGA176+25 上是否都有球，也没有逐个核。归引脚分配票。
4. **SDRAM 型号**：只取自原理图，没对 ISSI 规格书（#3）。IS42S32400J 是 128 Mbit 是从型号和产品页"128-Mbit SDRAM"推的。
5. **SDNE1 / SDCKE1 属于 FMC 的哪个 bank**：MB1246 用 SDNE1 / SDCKE1，UM2198 把它叫"SDRAM bank1"，没有到 RM0433 核对 bank 编号。
6. **13 个 VDD 球**：数图 10 得到，没有用脚本从表 9 复核。
7. **H742 / H753 等同封装的球位表**：只读了 H743（DS12110）和 H735（DS13312）的 UFBGA176+25 球位，其他系列没有读；H723 / H733 / H725 / H730 的 FMC 数据宽度只读了 H735 的数据手册（24 位）。
8. **Altium 工程 ZIP**（`mb1520_bdp.zip`、MB1737 的 `mb1737-bdp.zip` 等）里有没有额外的许可证，没有下载。
9. **OPLA 对"量产出售按此派生的板子"的态度，以及"公开发布自己重画的原理图"是否算分发**：协议没有明说，以上是我的解读，不是法律意见。
10. **AN5307（H7A3 / 7B3 / 7B0）、AN5935（H7R / 7S）**：没有打开。
11. **MB1246 的 USB OTG HS / FS、RS232、ST-LINK 等页没有读**。
12. 第 5、6 节里【图】标记的位号与网络的对应关系，只从渲染图读出，文字层只核对了型号和数值。

## 11. 来源

ST 原理图（见第 2 节表）：MB1246 H743-E03、H753-E03、MB1520 C-03、MB1381 B-04、MB1332 C-03、MB1737 B-02。

- [Open Platform License Agreement（st.com/opla）](https://www.st.com/resource/en/license_agreement/open_platform_license_agreement.pdf)
- [AN4938 Rev 7，H74x/H75x 硬件入门](https://www.st.com/resource/en/application_note/an4938-getting-started-with-stm32h74xig-and-stm32h75xig-mcu-hardware-development-stmicroelectronics.pdf)
- [AN5419 Rev 3，H723/733/725/735/730 硬件入门](https://www.st.com/resource/en/application_note/an5419-getting-started-with-stm32h723733-stm32h725735-and-stm32h730-mcu-hardware-development-stmicroelectronics.pdf)
- [DS12110 Rev 11，STM32H742xI/G、STM32H743xI/G 数据手册](https://www.st.com/resource/en/datasheet/stm32h743ii.pdf)
- [DS13312 Rev 4，STM32H735xG 数据手册](https://www.st.com/resource/en/datasheet/stm32h735ig.pdf)
- [UM2198 Rev 5，STM32H743I / H753I-EVAL 用户手册](https://www.st.com/resource/en/user_manual/dm00385071-evaluation-boards-with-stm32h743xi-and-stm32h753xi-mcus-stmicroelectronics.pdf)
- 产品页：[STM32H743I-EVAL](https://www.st.com/en/evaluation-tools/stm32h743i-eval.html)、[STM32H735G-DK](https://www.st.com/en/evaluation-tools/stm32h735g-dk.html)、[STM32H750B-DK](https://www.st.com/en/evaluation-tools/stm32h750b-dk.html)、[NUCLEO-H7S3L8](https://www.st.com/en/evaluation-tools/nucleo-h7s3l8.html)
