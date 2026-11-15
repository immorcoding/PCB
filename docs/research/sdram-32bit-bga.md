# 调研：32 位 BGA 封装 SDR SDRAM 的大厂型号

票据：[immorcoding/PCB#3](https://github.com/immorcoding/PCB/issues/3)（地图 #1）。调研日期 2026-11-15。

范围：STM32H7（UFBGA176+25，FMC，3.3 V IO）后面挂的 32 位数据宽度、BGA 封装的 SDRAM。库存和价格不看。1.8 V 的低功耗 SDR（LPSDR）不在范围内，原因见 [第 6 节](#6-对本项目的含义)。

## 证据等级

每条结论后面标一个等级，读的时候先看等级。

| 等级 | 含义 |
|---|---|
| **A** | 这次我自己打开了厂商/ST 的一手来源（官网页面、官方 PDF、官方 IBIS 文件）并读到了原文。 |
| **B** | 文件是厂商原版（页眉有厂商名和版本号），但我读的是第三方镜像或本机缓存的副本，没能从厂商官网重新取到。 |
| **C** | 只在搜索结果摘要里见到厂商页面的内容，页面本身打不开（反爬、JS 渲染），没读到原文。 |
| **D** | 没能核对。 |

## 1. 结论

1. **所有 3.3 V、32 位、BGA 的 SDR SDRAM 用同一张球图**：90 球，8 × 13 mm，球距 0.8 mm，每行 6 球（第 1、2、3 列和第 7、8、9 列，中间 4–6 列没有球），共 15 行（A–R，跳过 I、O、Q）。128 Mb 和 256 Mb 的 Micron、ISSI、Alliance、Winbond 逐球一致；512 Mb 只在 H3 多一个 A12（128/256 Mb 上 H3 是 NC）。换厂家、换容量都不用改封装和扇出。（A、B，见第 2 节）
2. **Micron 的 x32 SDR 不能选**：官网把 MT48LC4M32B2 的 B5/F5/P 各变体都放在"SDRAM obsolete / Obsolete part catalogs"下。Micron 优先的原则在这一类器件上落空。（A，见第 3.1 节）
3. **ST 自己的板子里，用满 32 位数据线的，用的是 ISSI**：STM32H743I/H753I-EVAL 是 IS42S32800J-6BLI，STM32H747I-DISCO 的原理图写 IS42S32800G-6BLI。（A，见第 4 节）
4. **推荐 ISSI IS42S32800J-6BLI**（256 Mb，8M × 32，90 球 TF-BGA，166 MHz，工业级温度）。理由：ST 官方板同款、官方原理图可照抄；ISSI 数据手册 2025 年 2 月还在出新版；KiCad 官方封装库里的 BGA-90 封装就是照着它的数据手册做的。球图兼容备选见第 7 节。

## 2. 共用球图

以 Micron 128 Mb 数据手册 Figure 3（Top View）为基准，ISSI IS42S32800J、IS42S32400F 的球图和 Alliance AS4C8M32SA、AS4C4M32S、AS4C16M32SB 的球图都用脚本从各自 PDF 的文字层解析，和这张表逐球比对：除 AS4C16M32SB 的 H3 外，全部一致（A，脚本比对，见第 8 节）。Micron 256 Mb（MT48LC8M32B2）和 Winbond W9812G2KB 的球图图像与此表目视一致，没有做脚本比对（B）。

| 行 | 1 | 2 | 3 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|
| A | DQ26 | DQ24 | VSS | VDD | DQ23 | DQ21 |
| B | DQ28 | VDDQ | VSSQ | VDDQ | VSSQ | DQ19 |
| C | VSSQ | DQ27 | DQ25 | DQ22 | DQ20 | VDDQ |
| D | VSSQ | DQ29 | DQ30 | DQ17 | DQ18 | VDDQ |
| E | VDDQ | DQ31 | NC | NC | DQ16 | VSSQ |
| F | VSS | DQM3 | A3 | A2 | DQM2 | VDD |
| G | A4 | A5 | A6 | A10 | A0 | A1 |
| H | A7 | A8 | **NC（512 Mb 为 A12）** | NC | BA1 | A11 |
| J | CLK | CKE | A9 | BA0 | CS# | RAS# |
| K | DQM1 | NC | NC | CAS# | WE# | DQM0 |
| L | VDDQ | DQ8 | VSS | VDD | DQ7 | VSSQ |
| M | VSSQ | DQ10 | DQ9 | DQ6 | DQ5 | VDDQ |
| N | VSSQ | DQ12 | DQ14 | DQ1 | DQ3 | VDDQ |
| P | DQ11 | VDDQ | VSSQ | VDDQ | VSSQ | DQ4 |
| R | DQ13 | DQ15 | VSS | VDD | DQ0 | DQ2 |

球数核对：DQ 32，DQM 4，A0–A11 共 12，BA0/BA1 共 2，CLK/CKE/CS#/RAS#/CAS#/WE# 共 6，VDD 4、VSS 4、VDDQ 10、VSSQ 10，NC 6（E3、E7、H3、H7、K2、K3），合计 90。

小差别：K2 在 Micron 的 128 Mb 球图上标 NU（Micron 的说明是"No connect: These pins should be left unconnected"），在 ISSI、Alliance、Winbond 上标 NC。ST 的原理图两种都按 NC 画。

由这张表推出的、和线序有关的事实（脚本从表里算出，A 级来源的二次推导）：

- 四个字节通道各占一个角：DQ0–7 在右下（L–R 行，7–9 列），DQ8–15 在左下（L–R 行，1–3 列），DQ16–23 在右上（A–E 行，7–9 列），DQ24–31 在左上（A–E 行，1–3 列）。
- DQM0/DQM1 在 K 行两端，DQM2/DQM3 在 F 行两端。
- 地址、命令、时钟全部集中在 F–K 这条中间带。
- 因此 DQ 的出线方向是"上半部 DQ16–31 往上，下半部 DQ0–15 往下"，地址/命令线从中间带往左右出。这对 FMC 一侧的线序约定有用，留给线序那张票用。

封装尺寸：

- Micron：90 球 VFBGA，8 × 13 mm，球阵 6.40 × 11.20 mm，球距 0.80 mm，球径 0.45 mm（回流前 0.42，对应 0.40 的 SMD 球焊盘），厚度 1.00 mm 以内，**推荐 PCB 焊盘 0.33 ± 0.025 mm**。（B，[Micron 128 Mb 数据手册 Figure 5][micron-128]）
- ISSI：90 球 TF-BGA，8.00 × 13.00 mm 本体，0.8 mm 球距，厚度 1.20 mm 以内，球径 0.40/0.45/0.50（最小/标称/最大，从封装图里的小字表读出，分辨率有限），参考 JEDEC MO-207。数据手册没有给推荐焊盘。（B，[ISSI IS42S32800J 数据手册][issi-800j] 第 4、59 页）
- Alliance：90 球 FBGA，8 × 13 × 1.2 mm（最大），0.80 mm 球距，没给推荐焊盘。（A，[AS4C8M32SA 数据手册][alliance-8m32sa-ds]）
- Winbond：TFBGA 90，8 × 13 mm，没给推荐焊盘。（A，[W9812G2KB 数据手册][winbond-w9812g2kb]）

## 3. 逐厂逐颗

### 3.1 Micron

| 型号 | 容量 | 封装 | 速度/电压 | 状态 | 证据 |
|---|---|---|---|---|---|
| MT48LC4M32B2（B5=90 球 VFBGA 无铅，F5=90 球 VFBGA 含铅，P=86 脚 TSOP II 无铅，TG=86 脚 TSOP II） | 128 Mb，4M × 32 | 90 球 VFBGA 8 × 13 mm | -6A/-6 为 167 MHz，-7 为 143 MHz；3.3 V ± 0.3 V；LVTTL | **官网列在"SDRAM obsolete / Obsolete part catalogs"** | 数据手册 B；状态 A（页面标题和面包屑） |
| MT48LC8M32B2（B5/F5=90 球 FBGA） | 256 Mb，8M × 32 | 90 球 FBGA 8 × 13 mm | PC100，3.3 V ± 0.3 V | 官网 obsolete 目录里我只看到它的 TSOP 变体 MT48LC8M32B2TG-7-IT-F；B5/F5 的状态没看到 | 数据手册 B（Rev. B 10/04）；状态 C |
| MT48LC2M32B2（B5） | 64 Mb | 90 球 | — | 官网 obsolete 目录有 B5-6A-J、P-5-J 等 | C |

要点：

- MT48LC4M32B2 的各变体（B5-6A-L、F5-6A-L、P-6A-L、B5-6A-IT-L、B5-6A-AIT-L 等）在 micron.com 的 `/products/obsolete/obsolete-sdram/part-catalog/part-detail/` 路径下，页面标题是"Obsolete part detail"。我打开了 [MT48LC4M32B2B5-6A-L 的页面][micron-obsolete-b5]，面包屑是"SDRAM obsolete > Obsolete part catalogs"；页面的规格和文档区是 JS 渲染的，没加载出来，所以没有停产日期和替代型号。（A，仅限标题和面包屑；日期 D）
- Micron 官网的 SDRAM 有源目录页（`/products/memory/dram-components/sdram/part-catalog`）我打开时表格是空的，没能列出任何在产的 x32 SDR 型号，所以"Micron 没有在产的 x32 SDR BGA"是推断（所有我查到的 x32 BGA 型号都在 obsolete 目录里），不是亲眼看到的清单。（D）
- 数据手册：我猜的几个 micron.com PDF 路径都 404，没有从 Micron 官网取到；读的是镜像上的 `128mb_x32_sdram.pdf`（文档号 09005aef80872800，Rev. V 03/16）和 256 Mb 的 Rev. B 10/04。内容页眉是 Micron 的，所以算 B。（[128 Mb 镜像][micron-128]，[256 Mb 镜像][micron-256]）
- IBIS：没找到 Micron SDR x32 的 IBIS 文件。（D）

### 3.2 ISSI

| 型号 | 容量 | 封装 | 速度/电压 | 状态 | IBIS | 证据 |
|---|---|---|---|---|---|---|
| **IS42S32800J**（-6BL、-6BLI、-7BL、-7BLI、-75EBLI；车规 IS45S32800J-…BLA1/A2） | 256 Mb，8M × 32 | 90 球 TF-BGA 8 × 13 mm，0.8 mm | -6 为 166 MHz（CL3），-7 为 143 MHz（CL3），-75E 为 133 MHz（CL2）；CL2 时 -6/-7 为 100 MHz；3.3 V（3.0–3.6 V）；LVTTL；4096 次刷新/64 ms | 数据手册 Rev. C 2025-02-25；ISSI SDR 页状态 Prod，页面带 Long-Term Support 字样 | 官网有 BGA 的 IBIS 文件（`42s16160j-83200j-32800j_b.ibs`），我没能打开 | 数据手册 B；状态 C；IBIS C |
| IS42S32400F（-6BL、-6BLI、-7BL、-7BLI）和 IS42S32400J | 128 Mb，4M × 32 | 同上 | 同上（-6 166 MHz，-7 143 MHz，-75E 133 MHz） | F 的数据手册是 2024 年 6 月版；J 版数据手册我没找到（ST 的 H750B-DK 原理图用的是 IS42S32400J-6BL） | 没查 | 数据手册 B（仅 F） |
| IS42S32160F（-6BL、-6BLI、-7BLI） | 512 Mb，16M × 32 | 90 球 TF-BGA | 166/143/133 MHz | ISSI SDR 页状态 Prod | 官网有 `42s16320f-86400f-32160f_b.ibs`（搜索摘要） | C |

要点：

- ISSI 官网有反爬（Incapsula），我从命令行和 WebFetch 都只得到验证页，**没有尝试绕过**。所以 ISSI 的数据手册副本不是这次从 issi.com 取的：它来自本任务较早一次被中断的运行留在本机临时目录里的文件，来源 URL 没有记录；我核对了内容：页眉是 ISSI，IS42S32800J 为 60 页、Rev. C、02/25/2025，IS42S32400F 为 60 页、2024 年 6 月。官方路径是 `http://www.issi.com/WW/pdf/42-45S32800J.pdf`（KiCad 的封装描述里引用的就是这个地址）。（B）
- ISSI 订货表（IS42S32800J，Rev. C 第 58 页）：后缀 `-6` = 166 MHz，`-7` = 143 MHz，`-75E` = 133 MHz；`B` = 90 球 BGA，`L` = 无铅（SnAgCu 球）；`I` = 工业级（-40 到 +85 °C），不带 `I` = 商业级（0 到 +70 °C）；`A1` = 车规 -40 到 +85 °C，`A2` = 车规 -40 到 +105 °C。（B）
- 状态：ISSI 的 [SDR SDRAM 产品页][issi-sdr] 在搜索摘要里显示 IS42S32800J 为 8M × 32、3.3 V、166/143/133、TSOP2(86) 和 BGA(90)、状态 Prod，并带 Long-Term Support；IS42S32160F 也是 Prod。我没能打开这个页面，所以是 C 级。数据手册 2025 年还出了新版，是旁证。
- 球图：IS42S32800J 和 IS42S32400F 的 Pin Configuration（第 4 页，PACKAGE CODE B）用脚本解析 PDF 文字层，与第 2 节的表逐球一致。（B，脚本比对）

### 3.3 Alliance Memory

| 型号 | 容量 | 封装 | 速度/电压 | 状态 | 数据手册 | IBIS | 证据 |
|---|---|---|---|---|---|---|---|
| **AS4C8M32SA**（-6BIN、-7BIN、-7BCN） | 256 Mb，8M × 32 | 90 球 TFBGA，8 × 13 × 1.2 mm | 166/143 MHz；3.3 V ± 0.3 V；LVTTL | 列在 Alliance 的有源"Synchronous DRAMs"目录，不在 EOL 页 | Rev 1.0，2016 年 11 月（[PDF][alliance-8m32sa-ds]） | **有**，已下载并读了文件头：IBIS 5.0，`[Source] Alliance Memory,Inc.`，2017-02-23（[AS4C8M32SA-6BIN_Ibis_I.ibs][alliance-8m32sa-ibis]）；-7BCN 也有；-7BIN 没有 | A |
| AS4C4M32S（-6BIN、-7BCN） | 128 Mb，4M × 32 | 90 球 TFBGA，8 × 13 × 1.2 mm | 166/143 MHz；3.3 V | 有源目录；它的 86 脚 TSOP 变体已 EOL（PCN-31072015） | Rev 3.0，2014 年 5 月（[PDF][alliance-4m32s-ds]），文件头仍标 Advanced | 有，已下载 -6BIN 的文件头（2016-06-28）；-7BCN 有链接未下载 | A |
| AS4C16M32SB（-6BCN、-6BIN） | 512 Mb，16M × 32 | 90 球 FBGA，8 × 13 × 1.2 mm | 只有 166 MHz，只支持 CL3；3.3 V；8192 次刷新/64 ms | 有源目录 | Rev 1.0，2023 年 2 月（[PDF][alliance-16m32sb-ds]） | 页面标了 IBIS 链接，我没取到目标地址 | A |

要点：

- Alliance 的产品页不写生命周期状态；上表"有源目录"的意思只是这几个型号列在 Synchronous DRAMs 目录里、不在 EOL 页上，是从页面位置推出来的，不是 Alliance 的明文声明。（A，推断）
- 命名容易混：AS4C4M32S 是 90 球 TFBGA 而 AS4C4M32SA 是 TSOP；AS4C8M32S 是 TSOP 而 AS4C8M32SA 才是 90 球 TFBGA。以 Alliance [Synchronous DRAMs 目录页][alliance-sdram] 的表为准。（A）
- EOL 页列出 AS4C8M32S-7BCN / -6BIN（TFBGA）的 PCN，文件名是"…AS4C8M32S-6BIN-7BCN-to-AS4C8M32SA-6_7BIN-6_7BCN-with-comparisons.pdf"，即换成 SA 版。（A，[EOL 页][alliance-eol]；PCN 内容没读）
- AS4C8M32MSB、AS4C16M32MSA 是 1.7–1.95 V 的移动版 SDR，不是 3.3 V 器件，不适用。（A，[LPSDR 页][alliance-lpsdr]）
- 球图：AS4C8M32SA、AS4C4M32S、AS4C16M32SB 的 Figure 1 用脚本解析文字层并和第 2 节的表比对，前两者一致，AS4C16M32SB 只有 H3 = A12 不同。（A）

### 3.4 Winbond

| 型号 | 容量 | 封装 | 速度/电压 | 状态 | 数据手册 | IBIS | 证据 |
|---|---|---|---|---|---|---|---|
| W9812G2KB（-6、-6I） | 128 Mb，4M × 32 | TFBGA 90，8 × 13 mm | 166 MHz（CL3）；3.3 V ± 0.3 V；-6 为 0 到 70 °C，-6I 为 -40 到 85 °C | Winbond 2026 年产品手册里 Mass Production 一栏打勾 | Rev A01，2017-02-23，43 页（[PDF][winbond-w9812g2kb]） | 没找到 | A |
| W9864G2JB（-6、-7，及 -6I/-7I） | 64 Mb | TFBGA 90，8 × 13 mm | 166/143 MHz | 同一张表里 Mass Production 一栏是 `*`，手册没有解释 `*` | 没读 | 没找到 | A（表），其余 D |

要点：

- **W9812G2KB 是双芯片封装（DDP）**：数据手册写"Dual-Die-Package (DDP), two pieces of 64M bits chip sealed in one package"，两颗 4M × 16 的 64 Mb 芯片叠在一起，一颗接 DQ0–15，一颗接 DQ16–31，地址和命令线并联。IDD、输出摆率、球电容和单颗不同。对 FMC 来说不影响用法，但时钟、地址线上的负载是两颗芯片。（A）
- Winbond 2026 年产品手册的 SDRAM 表里，256 Mb 只有 x16 的 W9825G6，没有 x32 的 256 Mb 型号（W9825G2JB 在经销商页面上被标为停产，那不是一手来源，未核）。（A，产品手册第 36–37 页；W9825G2JB 状态 D）
- 数据手册 Rev A01 之后我没找到新版。（D）
- 球图：目视与第 2 节一致（文字层是乱序的，没法用脚本比）。（A，目视）
- 来源页：[Winbond 2026 Customized Memory Solution 产品手册][winbond-guide]（第 40–41 页 PDF 页码，手册页码 36–37）。

## 4. ST 官方板用的是哪一颗

| 板子（主板号） | SDRAM | 数据线接法 | 来源 | 证据 |
|---|---|---|---|---|
| STM32H743I-EVAL / H753I-EVAL（MB1246，Rev E-03，2022-05-23） | **IS42S32800J-6BLI**（U15），之前的版本是 IS42S32800G-6BLI | D0–D31 全接，FMC_NBL0–3 全接，SDNE1，SDCKE1 | [MB1246 原理图第 5 页][st-mb1246]；[UM2198][st-um2198] 表 70 板版本历史"Memory IS42S32800G-6BLI replaced by IS42S32800J-6BLI without impact on firmware"（第 79 页）；UM2198 说 8M × 32 位 SDRAM 接在 FMC 的 SDRAM bank1 | A |
| STM32H747I-DISCO（MB1248，Rev D-04，2024-04-03） | U7，原理图上写 **IS42S32800G-6BLI**，下面另写 IS42S32160D-6BLI | D0–D31 全接；符号上 H3 画成 A12（128/256 Mb 上这个球是 NC） | [MB1248 原理图第 5 页][st-mb1248]；[UM2411 第 6.8 节][st-um2411]写"U7 8M x 32bit SDRAM … SDRAM Bank1" | A |
| STM32H750B-DK（MB1381，Rev B-04，2024-09-27） | U7 **IS42S32400J-6BL**（128 Mb） | **只接 D0–D15**；DQ16–DQ31 各经 10 kΩ 下拉，DQM2/DQM3 下拉；原理图写着"Matched Net Lengths [Tolerance = 100mil]" | [MB1381 原理图第 9 页][st-mb1381] | A |
| STM32F746G-DISCO（MB1191） | 原来是 Micron **MT48LC4M32B2B5**，后来换成 ISSI **IS42S32400F-6BL** | **只用低 16 位**，DQ16–31 经 10 kΩ 下拉（UM1907 写"Only the lowest 16-bit data is used (64-Mbit accessible)"） | [UM1907][st-um1907] 第 6.13 节和表 15 板版本历史（换件那一条在合并单元格里，我没法确定它属于哪一行修订，在 F746NGH6-E01 附近） | A |

要点：

- **用满 32 位的只有 MB1246（H743I/H753I-EVAL）和 MB1248（H747I-DISCO）**，两块都是 ISSI 256 Mb。H750B-DK 和 F746G-DISCO 虽然用的是 32 位的器件，但总线只接了一半，作为线序参照没有意义。
- STM32H745I-DISCO 与 H750B-DK 共用 MB1381，是搜索摘要里 UM2488 的说法，我没有核对。（C）
- STM32H747I-EVAL / H757I-EVAL 没有查。（D）
- UM2198 说最初的 STM32H743I-EVAL / H753I-EVAL 已经停产，现行的是 EVAL2；MB1246 原理图的变体写 H753、版本 E-03，我没核对 EVAL2 的板号与它的关系。（A，停产说法；板号关系 D）
- MB1246 第 5 页和 MB1248 第 5 页的 SDRAM 部分用的网络名一致（SDNWE、SDNCAS、SDNRAS、SDNE1、SDCKE1、SDCLK、FMC_NBL0–3、D[0..31]），按网络名在 KiCad 里重画这一页的工作量很小。（A）

## 5. KiCad 库里有什么

库：`D:\KiCad\share\kicad\`（KiCad 10.0.8）。

- **符号**：`symbols/Memory_RAM.kicad_sym` 里**没有**这一类器件。我用关键字（IS42S32、MT48LC4M32、MT48LC8M32、AS4C4M32、AS4C8M32、AS4C16M32、W9812G2、W9825G2）搜了整个符号目录，一个都没有；库里的 SDR SDRAM 符号全是 16 位或 8 位的（MT48LC16M16A2、MT48LC32M8A2、MT48LC64M4A2、AS4C4M16SA、IS42S16400J、W9812G6KH），32 位宽的只有 LPDDR4/4X（BGA-200）。**需要自画符号**，球表在第 2 节。（A）
- **封装**：`footprints/Package_BGA.pretty/BGA-90_8.0x13.0mm_Layout2x3x15_P0.8mm.kicad_mod` 存在，描述写"BGA-90, http://www.issi.com/WW/pdf/42-45S32800J.pdf"，即按 ISSI IS42S32800J 的数据手册做的。我用脚本核对：90 个圆形焊盘，名称恰好是 A–R（跳过 I、O、Q）× {1,2,3,7,8,9}，x 坐标 ±1.6/±2.4/±3.2，15 个不同的 y，A1 在 (-3.2, -5.6)，**焊盘直径 0.4 mm**。球阵尺寸 6.4 × 11.2 mm，与 Micron 的封装图一致。（A，脚本）

## 6. 对本项目的含义

1. **速度等级不是选型因素**。STM32H742/H743 数据手册（[DS12110 Rev 11，2026 年 1 月][st-ds12110]）写 FMC_SDCLK 最高 100 MHz（VDD 1.8–3.6 V，20 pF 负载），同时说 FMC 同步访问的最高时钟是 FMC 内核时钟除以 2。-6 和 -7 的 CL2 都支持 100 MHz，用哪个等级都够。（A）
2. **3.3 V**：MCU 的 IO 是 3.3 V，所以 1.8 V 的 LPSDR（Alliance AS4C8M32MSB/AS4C16M32MSA，1.7–1.95 V）和 Micron 的 1.8 V 移动版不适用。（A，Alliance 页）
3. **焊盘直径要重新核对规格档 B 里的假设**。`docs/rule-profiles/B-bga-080.md` 的球距计算表假设焊盘直径 0.4 mm，"要对器件规格书核实"。核实结果：Micron 数据手册给的推荐 PCB 焊盘是 **0.33 ± 0.025 mm**；ISSI、Alliance、Winbond 的数据手册没有给推荐焊盘，只给球径 0.40–0.50 mm（ISSI）；KiCad 的封装用 0.4 mm。焊盘取 0.33 时两个焊盘之间的空隙是 0.8 − 0.33 = 0.47 mm（0.4 时是 0.40 mm），影响 B 档表里"两个焊盘之间过一根线"的余量。选哪个焊盘直径要在规则阶段定。（B）
4. **H3 球接 A12**：ST 的 MB1248 把 H3 接 FMC 的 A12，这样 128/256 Mb 和 512 Mb（IS42S32160）都能焊。这块板如果想保留换 512 Mb 的余地，H3 要引到 A12；只用 256 Mb 则 H3 可以不接。（A，MB1248 第 5 页和 Alliance AS4C16M32SB 球图）
5. **字节通道在四个角**（见第 2 节）。DQ 的线序约定可以按"四个字节通道 + 中间带的地址/命令"来分组。ST 的 MB1381 对这条总线写的等长容差是 100 mil（约 2.54 mm），可以作为一个参照，不是本项目的规则。（A，MB1381 第 9 页）
6. **W9812G2KB 是双芯片**：如果以后拿它当 -6I 的备选，要把时钟/地址线上的双负载计入仿真。（A）

## 7. 推荐

**推荐：ISSI IS42S32800J-6BLI**

- 256 Mb（8M × 32），90 球 TF-BGA，8 × 13 mm，0.8 mm 球距，3.3 V，166 MHz（CL3），工业级温度。
- ST 官方 STM32H743I-EVAL / H753I-EVAL（MB1246 Rev E-03）用的就是这一颗，数据线 D0–D31 全接，官方 PDF 原理图可以直接参照。（A）
- ISSI 数据手册 Rev. C（2025-02-25）有球图、封装图、完整订货表；ISSI 的 SDR 产品页给的状态是 Prod；官方有 BGA 的 IBIS 文件（C）。
- KiCad 官方封装 `BGA-90_8.0x13.0mm_Layout2x3x15_P0.8mm` 就是为它做的，只缺符号。

**球图兼容、可以互换的备选**（同一块 PCB，第 2 节的表原样适用）：

| 备选 | 容量 | 说明 |
|---|---|---|
| ISSI IS42S32400F-6BLI / IS42S32400J-6BLI | 128 Mb | ISSI 同系列的小一档，ST 的 F746G-DISCO 和 H750B-DK 用过。 |
| Alliance AS4C8M32SA-6BIN | 256 Mb | 数据手册和 IBIS 都在 Alliance 官网公开，我都取到并读了（A）。是和推荐型号最接近的同容量备选。 |
| Alliance AS4C4M32S-6BIN | 128 Mb | 同上，数据手册版本较老（Rev 3.0，2014 年）。 |
| Winbond W9812G2KB-6I | 128 Mb | 双芯片封装，Winbond 2026 年手册标明量产；没有 IBIS。 |
| ISSI IS42S32160F-6BLI、Alliance AS4C16M32SB-6BIN | 512 Mb | 球图只在 H3 多一个 A12。想留 512 Mb 的余地，H3 要接 FMC 的 A12。 |
| Micron MT48LC4M32B2B5-6A / MT48LC8M32B2B5 | 128/256 Mb | 球图一致，但**已在 Micron 的 obsolete 目录**，只作历史参照，不作选择。 |

不选 Micron 的原因是生命周期，不是球图。

## 8. 已核实和没能核实

### 已核实（A，这次自己读到原文）

- 第 2 节的球图：Alliance 三份数据手册的文字层脚本解析，与 Micron 128 Mb 球图（目视转录）逐球一致，差别只有 AS4C16M32SB 的 H3；ISSI IS42S32800J / IS42S32400F 的文字层脚本解析与之一致（B，因为这两份 PDF 是本机缓存副本）。
- ST 官方板的 SDRAM 型号：MB1246 E-03（IS42S32800J-6BLI，32 位全接）、MB1248 D-04（原理图写 IS42S32800G-6BLI，32 位全接）、MB1381 B-04（IS42S32400J-6BL，只接 16 位）、UM1907 的换件记录（MT48LC4M32B2B5 换成 IS42S32400F-6BL，只用 16 位）、UM2198 的换件记录（IS42S32800G 换成 IS42S32800J）。原理图 PDF 都是这次从 st.com 取的，MB1246 的文件我取了两次，哈希一致。
- Alliance：三款 90 球 x32 的数据手册、AS4C8M32SA 和 AS4C4M32S-6BIN 的 IBIS 文件头、有源目录与 EOL 页、1.8 V 移动版的电压。
- Winbond：W9812G2KB 数据手册 Rev A01 的 DDP 说明和球图，2026 年产品手册里 W9812G2KB 的量产标记。
- Micron：MT48LC4M32B2B5-6A-L 页面标题和面包屑为 obsolete。
- STM32H743 数据手册：FMC_SDCLK 最高 100 MHz。
- KiCad：符号库没有 32 位 SDR SDRAM；BGA-90 封装的描述、焊盘数量、名称、坐标、直径。

### 没能核实

| 项目 | 原因 | 影响 |
|---|---|---|
| ISSI 数据手册、产品页、IBIS 在 issi.com 上的当前状态 | 官网有反爬，我没有绕过；数据手册副本来自较早一次被中断的运行，来源 URL 没记录；"Prod"和"Long-Term Support"来自搜索结果摘要 | 推荐型号的生命周期是 C 级。**用户下单前应在 issi.com 上确认 IS42S32800J-6BLI 的状态。** |
| ISSI IS42S32800J 的 IBIS 文件内容 | 打不开 | 仿真前要自己下载并核对封装寄生参数；Alliance AS4C8M32SA 的 IBIS 已核，可作代用 |
| Micron 官网上 x32 SDR 的有源清单、MT48LC4M32B2 的停产日期和替代型号、Micron IBIS | 页面 JS 渲染没加载出来；官网 PDF 路径猜不中 | "Micron 没有在产的 x32 BGA SDR"是推断 |
| Micron 数据手册当前版本 | 读的是镜像，版本 Rev. V 03/16 | 不影响球图结论 |
| ISSI IS42S32400J 的数据手册 | 没找到；ISSI 文件里只有 F | H750B-DK 用的 J 版细节未核 |
| ISSI IS42S32160F 的数据手册和球图 | 没取到；球图结论靠 Alliance AS4C16M32SB 和 ST MB1248 的符号推断 | 512 Mb 的 H3 = A12 对 ISSI 是推断 |
| Alliance AS4C16M32SB 的 IBIS | 页面没给出目标地址 | — |
| Winbond W9825G2JB（256 Mb x32）的官方状态；W9864G2JB 的 `*` 含义 | 官网产品手册没列，没有图例 | 不影响推荐 |
| STM32H747I-EVAL / H757I-EVAL、STM32H745I-DISCO 用的 SDRAM | 没取到对应原理图 | 只影响"ST 板用没用"的列表完整性 |
| UFBGA176+25 的 FMC_D0–D31 引脚是否全部可用 | 不在这张票的范围内，没查 | 归 MCU 引脚分配那张票 |
| 各厂商的价格、库存 | 按要求不看 | — |

### 工具与方法说明

- 球图的文字层大多是乱序的，我从渲染出来的图里目视转录了 Micron 的表，再用脚本（`pdftotext` 解析后逐球比对）核对了 ISSI 和 Alliance；Winbond 的文字层乱序、无法脚本比对，只是目视。
- 没有用 kicad-happy 的 `datasheets` skill 提取引脚（这是一张调研票，没有工程缓存）；到原理图阶段应当用它对第 2 节的表再核一遍。

## 来源

厂商一手来源：

[micron-128]: https://datasheet.chipsmall.com/MT48LC4M32B2P-6-G/673525.pdf
[micron-256]: https://datasheet.sic-components.com/MT48LC8M32B2.pdf
[micron-obsolete-b5]: https://www.micron.com/products/obsolete/obsolete-sdram/part-catalog/part-detail/mt48lc4m32b2b5-6a-l
[issi-800j]: http://www.issi.com/WW/pdf/42-45S32800J.pdf
[issi-sdr]: https://www.issi.com/US/product-dram-SDR.shtml
[alliance-sdram]: https://www.alliancememory.com/product/synchronous-drams/
[alliance-eol]: https://www.alliancememory.com/product/eol-sdram/
[alliance-lpsdr]: https://www.alliancememory.com/product/lpsdr-sdram-mobile-sdr/
[alliance-8m32sa-ds]: https://www.alliancememory.com/wp-content/uploads/Alliance-Memory_256M-SDRAM_AS4C8M32SA-6_7BINBCN-A-die_rev-1.0-November-2016.pdf
[alliance-8m32sa-ibis]: https://www.alliancememory.com/wp-content/uploads/AS4C8M32SA-6BIN_Ibis_I.ibs
[alliance-4m32s-ds]: https://www.alliancememory.com/wp-content/uploads/128M-AS4C4M32S-TFBGA_V3.0.pdf
[alliance-16m32sb-ds]: https://www.alliancememory.com/wp-content/uploads/AllianceMemory_512Mb_AS4C16M32SB-6BxN_Datasheet_16Feb2023_ver1.0.pdf
[winbond-w9812g2kb]: https://www.winbond.com/resource-files/w9812g2kb_a01_20170223.pdf
[winbond-guide]: https://www.winbond.com/export/sites/winbond/product-selection-guide/file/2026-Winbond-Customized-Memory-Solution.pdf

ST 来源：

[st-mb1246]: https://www.st.com/resource/en/schematic_pack/mb1246-h753-e03_schematic.pdf
[st-mb1248]: https://www.st.com/resource/en/schematic_pack/mb1248-h747i-d04-schematic.pdf
[st-mb1381]: https://www.st.com/resource/en/schematic_pack/mb1381-h750xb-b04.pdf
[st-um2198]: https://www.st.com/resource/en/user_manual/dm00385071-evaluation-boards-with-stm32h743xi-and-stm32h753xi-mcus-stmicroelectronics.pdf
[st-um2411]: https://www.st.com/resource/en/user_manual/um2411-discovery-kit-with-stm32h747xi-mcu-stmicroelectronics.pdf
[st-um1907]: https://www.st.com/resource/en/user_manual/dm00190424.pdf
[st-ds12110]: https://www.st.com/resource/en/datasheet/stm32h743vi.pdf

- [Micron 128 Mb x32 SDRAM 数据手册（镜像）][micron-128]：文档号 09005aef80872800，Rev. V 03/16，第 1 页选项和速度、第 10 页球图、第 13 页封装图。
- [Micron 256 Mb x32 SDRAM 数据手册（镜像）][micron-256]：Rev. B 10/04，第 5 页球图。
- [Micron obsolete 页面：MT48LC4M32B2B5-6A-L][micron-obsolete-b5]；同一目录下的其他变体：[F5-6A-L](https://www.micron.com/products/obsolete/obsolete-sdram/part-catalog/part-detail/mt48lc4m32b2f5-6a-l)、[MT48LC8M32B2TG-7-IT-F](https://www.micron.com/products/obsolete/obsolete-sdram/part-catalog/part-detail/mt48lc8m32b2tg-7-it-f)（这两页只在搜索结果里见到标题）。
- [ISSI IS42S32800J / IS45S32800J 数据手册][issi-800j]：Rev. C 02/25/2025，第 4 页球图、第 58 页订货表、第 59 页封装图。
- [ISSI SDR SDRAM 产品页][issi-sdr]：只见到搜索摘要。ISSI IBIS：`https://www.issi.com/WW/models/ibis/42s16160j-83200j-32800j_b.ibs`，只见到搜索摘要。
- [Alliance Synchronous DRAMs 目录][alliance-sdram]，[AS4C8M32SA 页](https://www.alliancememory.com/datasheets/as4c8m32sa/)，[AS4C4M32S 页](https://www.alliancememory.com/AS4C4M32S/)，[AS4C16M32SB 页](https://www.alliancememory.com/AS4C16M32SB/)，[EOL 页][alliance-eol]，[LPSDR 页][alliance-lpsdr]。
- [Winbond W9812G2KB 数据手册][winbond-w9812g2kb]：Rev A01，2017-02-23；[Winbond 2026 产品手册][winbond-guide]。
- [STM32H7xxI-EVAL MB1246 原理图][st-mb1246]，[STM32H747I-DISCO MB1248 原理图][st-mb1248]，[STM32H750B-DK MB1381 原理图][st-mb1381]。
- [UM2198][st-um2198]（Rev 5，2025 年 12 月），[UM2411][st-um2411]（Rev 8，2026 年 7 月），[UM1907][st-um1907]（Rev 8，2026 年 9 月），[STM32H742/H743 数据手册 DS12110 Rev 11][st-ds12110]。
- KiCad 本机库：`D:\KiCad\share\kicad\symbols\Memory_RAM.kicad_sym`，`D:\KiCad\share\kicad\footprints\Package_BGA.pretty\BGA-90_8.0x13.0mm_Layout2x3x15_P0.8mm.kicad_mod`。
