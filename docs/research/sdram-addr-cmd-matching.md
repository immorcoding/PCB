# 调研：SDR SDRAM 地址 / 命令线要不要等长，容差取多少

调研日期 2026-11-23。分支 `research/sdram-addr-cmd-matching`，不合并，不改 `docs/shape/`，没有改板文件、没有跑 KiCad。

问题：`stm32h743_sdram` 板（STM32H743 UFBGA176+25 + 一颗 IS42S32800J，SDCLK 100 MHz，CL3，点对点）里，地址 / 命令组（A0-A12、BA0 / BA1、RAS、CAS、WE、CKE0、NE0，共 20 根）现在不等长，只限 60 mm。用户建议也做组内等长，容差取数据线的几倍。主会话提案是组内 ±15 mm。

已有结论不重做：`origin/research/bus-timing-budget` 的 `docs/research/bus-timing-budget.md` 已经算过 SDRAM 读 / 写方向的预算，得到"写方向地址、命令比时钟长最多 +2000 ps（290 mm）"。本文在它的基础上：(1) 重新核对了 ISSI 和 DS12110 的表（渲染页，不是文字层）；(2) 补了它没算的保持方向、边沿降额、SDCLK 周期下限、时钟串阻；(3) 查了厂商指南、从业者说法和两块真实板。

## 标记

- **[已读]**：这次打开了原文，在那里读到。
- **[推导]**：用 [已读] 的数算出来，假设写在旁边。
- **[未核]**：只在搜索摘要里见过，或来源是无署名转载，或页面抓不到。
- **[原文缺项]**：原文就没有这个数。

## 1. 时序计算

### 1.1 输入

| 参数 | 值 | 来源 | 状态 |
|---|---|---|---|
| SDCLK 周期 T | 10 ns（100 MHz）；半周期 T/2 = 5 ns | 题设 | |
| SDCLK 周期下限 tw(SDCLK) min | 2·Tfmc_ker_ck − 1 ns（fmc_ker_ck = 200 MHz 时 9 ns） | DS12110 Rev 11 Table 70 / 72，第 161、163 页 | [已读] |
| 地址有效 td(SDCLKL_Add)，写，max | 1.5 ns（rev Y 和 rev V 相同，无 min） | DS12110 Table 72（第 163 页）、Table 169（第 268 页） | [已读]，渲染页 |
| 地址有效 td(SDCLKL_Add)，读，max | 1.5 ns | DS12110 Table 70（第 161 页） | [已读]，渲染页 |
| 地址保持 th(SDCLKL_Add) | 表里没有。波形图（Figure 34 / 85）画了 th(SDCLKL_AddC)，Table 70 / 72 / 169 没给值 | 同上 | [原文缺项] |
| SDNWE td max / th min | 1.5 ns / 0.5 ns | Table 72、169 | [已读] |
| SDNE（片选）td max / th min | 1.5 ns / 0.5 ns | 同上 | [已读] |
| SDNRAS td max / th min | 1 ns / 0.5 ns | 同上 | [已读] |
| SDNCAS td max / th min | 1 ns / 0.5 ns（第二行误印为 td，按 hold 读） | 同上 | [已读] |
| CKE、NBL 的时序 | 表里没有 | | [原文缺项] |
| 测试条件 | OSPEEDRy = 11；SDRAM 时序在 20 pF 负载下标；"Guaranteed by characterization results" | DS12110 第 145、160 页（rev Y），前人调研读过第 266 页（rev V） | [已读]（第 145 页），其余沿用前人 |
| ISSI tAS / tAH | 1.5 ns / 1.0 ns，-6、-7、-75E 三档相同 | IS42S32800J Rev C 02/2025 第 16 页，渲染页 | [已读] |
| ISSI tCMS / tCMH（CS、RAS、CAS、WE、DQM） | 1.5 ns / 1.0 ns，三档相同 | 同上 | [已读] |
| ISSI tCKS / tCKH（CKE） | 1.5 ns / 1.0 ns，三档相同 | 同上 | [已读] |
| ISSI tDS / tDH（数据，对照） | 1.5 ns / 1.0 ns，三档相同 | 同上 | [已读] |
| ISSI 输入边沿注 | 输入时序在 tT = 1 ns 下测；边沿更慢时要加 (tT/2 − 0.5) ns；参考电平 1.4 V | 同上，Notes 2、3 | [已读] |
| 传播延迟 | 取 6.9 ps/mm（带状线，沿用前人报告，也在题设 6.0-7.0 之内）；微带 5.8 ps/mm 时 mm 数多 19% | bus-timing-budget §1.1 | [推导] |

文字层的 ISSI 表列是乱的（tDS / tDH / tAS / tAH 的行和值错位），上面的值是渲染页读的。`pdftotext` 直接出的 DS12110 Table 70 / 72 也错位（min / max 列串行），同样以渲染页为准。

### 1.2 模型

MCU 在 SDCLK 下降沿后 td 内输出地址，SDRAM 在 T/2 之后的 SDCLK 上升沿采样。令 s = 地址线延迟 − 时钟线延迟（地址线比时钟线长为正）：

- 建立（地址晚于时钟）：`s ≤ T/2 − td(Add)max − tAS`
- 保持（地址早于时钟）：`s ≥ −(T/2 + th(Add)min − tAH)`

地址的 th min 表里没有，下面按 0 算（保守），同表的控制信号是 0.5 ns。

### 1.3 余量

| 情形 | 建立方向上限 s ≤ | 保持方向下限 s ≥ | 说明 |
|---|---|---|---|
| 名义（T/2 = 5 ns，tT = 1 ns，th(Add) = 0） | 5 − 1.5 − 1.5 = **+2000 ps（290 mm）** | −(5 + 0 − 1.0) = **−4000 ps（−580 mm）** | 与前人报告一致 |
| 命令信号（WE、NE、RAS、CAS，th = 0.5） | WE、NE：+2000 ps；RAS、CAS：+2500 ps | −4500 ps | tCMS = 1.5、tCMH = 1.0 |
| CKE（tCKS = 1.5） | 表里没有 CKE 的 td，按地址取 +2000 ps | 未知 | [原文缺项]，按地址类推 |
| 降额 1：SDCLK 周期取下限 9 ns（T/2 = 4.5 ns） | +1500 ps（217 mm） | −3500 ps | 两侧各少 500 ps |
| 降额 2：SDRAM 输入边沿 2 ns（加 (2/2 − 0.5) = 0.5 ns） | 再少 500 ps | 再少 500 ps | 假设；边沿实际多慢没有 IBIS，[未核] |
| 降额 1 + 2 叠加 | **+1000 ps（145 mm）** | **−3000 ps（−435 mm）** | 最坏的组合 |
| 时钟串阻（题设：MCU 端一颗 0402，阻值按 33 Ω 假设）使 SDRAM 处时钟晚到 δ | 上限加 δ | 下限收紧 δ | δ 约 33 Ω × (SDRAM CLK 引脚 2-4 pF + 12.9 mm × 0.138 pF/mm ≈ 1.8 pF) ≈ 0.2 ns，[推导]，粗估；建立方向不计它是偏保守，保持方向要扣 |

换算：所有 mm 用 6.9 ps/mm；用 6.0 或 7.0 ps/mm，名义上限是 333 或 286 mm；用 5.8 ps/mm（微带）是 345 mm。

### 1.4 本板的实际余量

现在布出来的地址 / 命令线都比时钟长（A12 = 13.6 mm，比 12.9 mm 的时钟长 0.7 mm；A6 = 59.0 mm，长 46.1 mm），所以**只有建立方向相关，保持方向不会碰**（要地址比时钟短 435 mm 以上才会碰，板子只有 40 mm 量级）。

| 地址线比时钟长 | 延迟（6.9 ps/mm） | 对名义上限 2000 ps 的余量 | 对最坏组合 1000 ps 的余量 |
|---|---|---|---|
| +0.7 mm（A12） | 5 ps | 1995 ps | 995 ps |
| +46.1 mm（A6） | 318 ps（5.8 时 267 ps） | **1682 ps（约 244 mm）** | **682 ps（约 99 mm）** |

结论：**紧的方向是地址晚于时钟（SDRAM 处的建立），但本板离它还差一个数量级以上**；最长一根用掉名义窗口的 16%，最坏降额组合下用掉 32%。

### 1.5 组内差要不要紧

每根地址 / 命令线是**各自**对 SDCLK 采样的：SDRAM 没有"地址线之间"的时序要求，只有每根对 CLK 的 tAS / tAH。所以组内差本身不是一个独立的约束，它只通过"每根都在窗口里"起作用。窗口总宽（上限 − 下限）名义 6.0 ns，最坏降额后 4.0 ns，折成地址线两两之间最多可以差 4.0-6.0 ns，即 580-870 mm，比板子大得多。

没有计入的东西（前人报告 §1.4 同样没计）：串扰、同步开关噪声、时钟抖动、封装内部走线差、MCU 各输出脚之间的偏斜（td max 是对整个器件的包络，已含）、过冲。下表把三个候选容差折成 ps，和窗口比：

| 组内容差 | 折算 ps（6.9） | 占名义窗口 6000 ps | 占最坏窗口 4000 ps | 需要加的蛇形（主会话估计） |
|---|---|---|---|---|
| ±10 mm（spread 20 mm） | ±69 ps | 2.3% | 3.5% | 约 110 mm，9 根 |
| ±15 mm（spread 30 mm） | ±104 ps | 3.5% | 5.2% | 约 38 mm，4 根 |
| ±20 mm（spread 40 mm） | ±138 ps | 4.6% | 6.9% | 约 7 mm，2 根 |
| 现状（spread 45.5 mm） | 314 ps | 5.2% | 7.9% | 0 |

三个候选在电气上都远远没有用到窗口，**现状也没有**。区别只是"和哪条规则看齐"（见第 5 节）。

## 2. 厂商指南

要的是 SDR SDRAM（不是 DDR）的地址 / 命令数字。结果：**没有找到任何一家专门写 SDR SDRAM 地址 / 命令对时钟的容差**，下面是找到的最接近的。

| 来源 | 原文数字 | 相对什么 | 适用 | 状态 | URL |
|---|---|---|---|---|---|
| ST AN4938 Rev 7 §9.4.2 第 41 页（H74x / H75x） | "Match the clock traces to each signal trace in the address and command groups to within ±10 mm (with maximum of <= 20 mm)"；"Match the clock traces to the data/address group traces within ±10 mm"；数据组内 ±10 mm；走线 < 120 mm；时钟"Avoid using serpentine routing" | 地址 / 命令每根对**时钟**；数据组内；组内不单列 | FMC SDRAM，本芯片 | [已读]，本地 PDF 文字层，措辞和 AN4661 一致 | 本地 `stm32h743_sdram/datasheet/AN4938_Rev7.pdf` |
| ST AN4661 Rev 5 §8.4.3 第 46 页（F7） | 同上，逐字相同的四条（数据 ±10 mm，时钟对数据 / 地址 ±10 mm，时钟对每根地址 / 命令 ±10 mm 且最大 ≤ 20 mm） | 同上 | STM32F7 FMC | [已读]，文字层 | https://www.st.com/resource/en/application_note/an4661-getting-started-with-stm32f76xxx-and-stm32f77xxx-hardware-development-stmicroelectronics.pdf |
| NXP MIMXRT105060HDUG Rev 4（2019-10）§7.4 第 18 页（i.MX RT1050 / 1060，SEMC，最高 166 MHz） | "Ideally, route all signals at the same length as the EVK board ... (±50 mils)"；分两组：数据 + DM、地址 + 控制，分走顶层和底层 | 所有 SDRAM 信号彼此（没有写比较对象）；±50 mil = ±1.27 mm | SDR SDRAM（SEMC） | [已读]，渲染页 | https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/imxrt/23845/1/MIMXRT105060HDUG.pdf |
| Microchip AN2717（SAMA5D2 动态存储器实现指南）§3 | "The length difference between any address/control signal and CK/CKn should not exceed 400 mils"；字节通道内 50 mil；通道之间 0.5 inch；数据对 CK 500 mil；CK / CKn 之间 20 mil | 地址 / 控制对**时钟**（400 mil = 10.2 mm） | 该页含 DQS / 差分 CK，是 DDR 系（SAMA5D2 的 DDR2 / LPDDR），**不是 SDR 指南**，只作对照 | [已读]（抓取后的页面摘要，非渲染页） | https://onlinedocs.microchip.com/oxy/GUID-BCEA4067-D69A-4529-81CC-133D9195C03C-en-US-4/GUID-C33E36ED-2752-4075-9EE6-5DBA2F0D2B36.html |
| ST MB1381（H750B-DK）原理图第 9 页 | "Matched Net Lengths [Tolerance = 100mil]" 圈住 SDRAM_A、SDRAM_D、SDNE1、SDCKE1、SDNCAS、SDNRAS、SDNWE、SDCLK | 没写比较对象 | 同芯片家族 | 沿用 bus-timing-budget §2.4，本次没重读 | 见前人报告 |
| Intel / Altera EMIF 手册（DDR2 / DDR3 / DDR4） | 地址 / 命令对时钟 ±20 ps 每颗存储器；DDR2 双 DIMM 例子 "+250 mils (+5 mm) or ±50 ps" | 对时钟 | **DDR，不是 SDR** | [未核]（搜索摘要） | https://www.intel.com/content/www/us/en/docs/programmable/683741/21-3-19-2-4/length-matching-rules.html |
| TI DDR3 fly-by（SPRABI1D） | 地址 / 命令对时钟 ±20 mil | 对时钟 | **DDR3，不是 SDR** | [未核]（搜索摘要） | https://ti.com/document-viewer/lit/html/SPRABI1D/GUID-38C1FBC8-87AC-4342-ABFF-E765AA788D6D |
| Renesas（IDT）AN-302（RC32355 + SDRAM，2001） | 时钟线额外长度"adds skew at approximately 185 ps per inch" | 时钟线（有缓冲器），不是地址 | 50-75 MHz SDRAM，讲的是时钟缓冲器方案 | [已读]（PDF 文字层，只读了时钟一段） | https://www.renesas.com/us/en/document/apn/302-connecting-rc32355-sdram-system |
| Micron | 没找到 SDR SDRAM 的布线笔记。Micron 256Mb SDR 数据手册脚注提到 TN-48-05，内容没核实；TN-46-14（点对点硬件技巧）按 Microchip 页面的说法是 DDR 系 | | | [未核]，"not found" | |
| ISSI、Alliance Memory、Infineon / Cypress、Lattice | 没找到 SDR SDRAM 的布线应用笔记 | | | "not found" | |
| TI | 没找到 SDR 专用笔记；TI E2E 论坛上有一条 RM48 的回答，见第 3 节 | | | | |

要点：

1. 凡是有数字的 SDR 来源，**数字都是对时钟的，不是地址组内部的**。ST 写的是"每根地址 / 命令线对时钟 ±10 mm（最大 ≤ 20 mm）"。主会话的"组内 ±15 mm"没有任何厂商原文对应。
2. NXP 的 ±50 mil 是各来源里最紧的，但它也说"Ideally"，且指的是照抄 EVK 板的走线。
3. ST 的 ±10 mm 没有写推导。bus-timing-budget 已指出它比时序窗口紧一个数量级，应当是把串扰、抖动、封装差等打包的经验值。本次重算后窗口余量更大，结论不变。

## 3. 从业者说法

分两类：**给了带数的经验规则**；**说影响很小、走短就行**。

### 3.1 给了数的

| 谁 | 说法 | 数字 | 来源 | 状态 |
|---|---|---|---|---|
| Zachariah Peterson（Altium，文章 2021-06-22） | 对比表中 SDRAM 一栏 "Yes (very generous, ~400-500 mils tolerance in some products)"；"the length matching requirements are much easier"（因为边沿慢） | 400-500 mil = 10.2-12.7 mm，没写对什么 | https://resources.altium.com/p/using-sdram-vs-ddr-ram-your-pcb-design | [已读] |
| everdrone（FEDEVEL 论坛，2025-07-29，STM32H7 SDRAM BGA 贴） | 转述 ST H7 应用笔记："the address command and control lines should stay within a 20mm margin of each other"，对时钟"a 10mm margin"。他自己说"there's no way to keep the margin below 10mm with such a short clock line"，问要不要给时钟加蛇形 | 20 mm 组内、10 mm 对时钟 | https://courses.fedevel.com/forum/schematic-design-pcb-layout/need-guidance-and-tips-on-routing-sdram-bga | [已读] 贴子；他对 ST 笔记的转述和笔记原文不同（原文是"对时钟 ±10 mm，最大 ≤ 20 mm"），**说明 ST 这句话容易被读成"组内 20 mm"**，不是 ST 的原文 |
| 无署名 Scribd 文档 "Sdram-Routing" | "DQ signals ±10 mm, Address bus ±10 mm, control ±10 mm, clock to SDRAM ±5 mm"，6 ps/mm | | https://www.scribd.com/document/1070406306/Sdram-Routing | [未核]，没有署名也没有出处，只作"网上常见数字"的证据 |

### 3.2 说影响小、走短就行

| 谁 | 说法 | 来源 | 状态 |
|---|---|---|---|
| Robert Feranec（FEDEVEL，2015-09-10，答 SDR SDRAM 贴） | 被问到"你按时钟算最短最长走线吗"时答："I do not have any SDRAM length matching requirements"；主张的是系列端接加仿真："passing that simulation is usually enough to feel confident about the layout" | https://fedevel.com/forum/schematic-design-pcb-layout/82-sdr-sdram-layout-recommendations | [已读] |
| Vangelis Fortounas（ST 社区，2021-04-24，F746 + IS42S32400，最佳答案） | "I wouldn't worry about the exact length matching, since Data-Address Setup and Hold times for this memory allow not so tight skew"；重点是"traces as short as possible"；估 66 ps/cm | https://community.st.com/t5/stm32-mcus-touchgfx-and-gui/best-pcb-design-of-fmc-for-stm32f746-and-is42s32400-sdram/m-p/204135 | [已读]；不是 ST 员工 |
| STOne-32（ST 技术版主，2025-03-08） | "Particular attention to Clock signal impedance matching with receiver ( Memory)"，"all data should be with same length Matching"；没有提地址 | https://community.st.com/t5/stm32-mcus-products/fmc-to-connect-external-sdram-do-i-need-length-or-impedance/m-p/780550 | [已读] |
| EEVblog "SDRAM Layout for newbies" | stmdude：尽量短、不打过孔；Bassman59："It's not the frequency of the signal, it's its rise time that matters for signal integrity"；没有数字 | https://www.eevblog.com/forum/eda/sdram-layout-for-newbies/ | [已读] |
| Cadence 论坛一条回答 | "No length-matching is required, since it's a synchronous system, not a source-synchronous DDR. Length matching comes from timing analysis." | https://community.cadence.com/cadence_technology_forums/pcb-design/f/pcb-design/6574/how-to-route-high-speed-sdram | [未核]（页面 403，只有搜索摘要） |
| TI E2E，RM48 SDRAM（TI 工程师） | 说不用操心等长，把走线缩短 | https://e2e.ti.com/support/microcontrollers/arm-based-microcontrollers-group/arm-based-microcontrollers/f/arm-based-microcontrollers-forum/520381/rm48-sdram-layout-considerations | [未核]（页面 403，只有摘要） |

### 3.3 分布

- 有数字的一边：厂商文档（ST、NXP、Microchip）加 Altium 的文章，数字落在 **±1.3 到 ±12.7 mm 对时钟**，且都带"generous / ideally"一类措辞。
- 说无所谓的一边：Feranec、ST 社区里的一条最佳答案、Cadence 一条回答、TI 一条回答，共同点是"这是同步系统，看 setup / hold 时间，走短"。
- 没找到：Phil's Lab、Rick Hartley、Eric Bogatin、Sierra Circuits 对 SDR SDRAM 地址线的论述（搜索无结果，"not found"）。
- 没有任何来源给出"SDR SDRAM 地址 / 命令组内部等长 ±15 mm"或"组内 ±10 / ±20 mm"。

## 4. 真实板

只统计 `(segment ...)` 和 `(arc ...)` 的长度，不含过孔深度、焊盘到过孔的短桩、封装内部。脚本 `netlen2.py` 放在工作目录之外，输入文件放在单独的临时目录，用 `python -I` 运行。两块板的文件都是 GitHub 上的原始 `.kicad_pcb`。

### 4.1 ULX3S（emard/ulx3s，v3.1.7，commit `6a92cec6b177191c5b0f80e260013a1f8ec147dd`，`ulx3s.kicad_pcb`，4.5 MB）

16 位 SDR SDRAM（README 写 MT48LC32M16；PCB 封装值 MT48LC16M16A2TG，TSOP-II 54）。工作时钟频率没有核实（[未核]）。四层。

| 组 | 根数 | 最短 | 最长 | 组内差 |
|---|---|---|---|---|
| 地址 + 命令（A0-A12、BA0、BA1、nCS、nRAS、nCAS、nWE、CKE） | 20 | 22.15 mm（nWE） | 32.87 mm（A3） | **10.7 mm** |
| SDRAM_CLK | 1 | 24.32 mm | | 相对地址 / 命令：**−2.2 到 +8.6 mm** |
| 数据 D0-D15 | 16 | 16.55 mm（D15） | 22.90 mm（D4） | 6.4 mm |
| DQM0 / DQM1 | 2 | 22.33 / 22.44 mm | | |

ULX3S 的地址 / 命令线没有蛇形痕迹，组内差 10.7 mm，时钟落在地址组的中间偏短一侧。这是"布得短就自然差得少"的例子，不是有意按容差调的（没有证据说作者按某个数调过，[未核]）。

### 4.2 Antmicro STM32H7 HDMI Board（antmicro/stm32h7-hdmi-board，KiCad 9.0，rev 1.0.0，2026-04-01，commit `bc07c51c77eebd053504ec112637fbef24138bd6`，`stm32h7-hdmi-board.kicad_pcb`，45.6 MB）

SDRAM 通过 SO-DIMM 插座（Bus_SDRAM_SODIMM_TE_390112-1）接出，所以长度是 MCU 到插座，不是到存储器颗粒；SDRAM 型号没核实。32 位数据线。每根线在 MCU 侧有一颗串阻（网络名 `SDRAM_xx_R`），下面把串阻两侧的长度加起来。

| 组 | 根数 | 最短 | 最长 | 组内差 |
|---|---|---|---|---|
| 地址 + BA（A0-A12、BA0、BA1） | 15 | 97.7 mm（A11） | 99.9 mm（A0、A4） | **2.2 mm** |
| 命令 / 控制（SDNCAS、SDNE0、SDNE1、SDNRAS、SDNWE、SDCKE0、SDCKE1） | 7 | 98.2 mm | 99.9 mm | 1.7 mm |
| SDCLK | 1 | 87.2 mm | | 比地址 / 命令短 **10.5 到 12.7 mm** |
| 数据 D0-D31 | 32 | 106.9 mm（D12） | 125.6 mm（D30） | 18.7 mm |
| NBL0-3 | 4 | 116.0 mm | 119.7 mm | |

这块板把地址 / 命令线互相调到 ±1.1 mm 以内（约 99.5 mm，是调过的），但**时钟比它们短 10-13 mm 没有补**，数据线差 18.7 mm 也没有调紧。也就是说作者做的是"地址 / 命令组内等长"而不是"对时钟等长"。作者的意图没有文档，[未核]。线很长（约 100 mm），接近 ST 的 120 mm 上限。

### 4.3 没做的

- 第三块板没找到合适的（GitHub 搜索 `IS42S32800` 只命中看起来是自动生成的仓库，没有采用）。i.MX RT + SDR SDRAM 的 KiCad 板没找到，"not done"。
- 两块板都没有算过孔、没有换算成 ps。
- ST 评估板（MB1246 / MB1381 等）是 Altium 文件，没有取。

## 5. 对本板的意义

### 5.1 电气上要不要等长

**100 MHz 下不需要。** 理由：

1. 窗口：地址 / 命令线比时钟长最多 +1000 ps（最坏降额，145 mm）到 +2000 ps（名义，290 mm），短最多 −3000 到 −4000 ps。本板范围是"长 0.7 到 46 mm"，即 5 到 318 ps，用掉最坏窗口的 32%。
2. 组内差不是约束：每根线只对 SDCLK 采样，窗口总宽 4-6 ns，两两最多可差 580-870 mm。
3. 保持方向：所有地址线都比时钟长，没有保持风险。
4. 前提：固件要把 FMC 配成 DS12110 测试条件（OSPEEDRy = 11、I/O 补偿打开），负载不超过 20 pF 的条件，CL3。这些在 SPEC 里已有。
5. 没算进去的东西（串扰、SSN、抖动）不是长度差能解决的，更像是靠间距、层、GND 过孔处理。

### 5.2 来源支持什么容差

- 有数字的 SDR / 同类来源（ST、NXP、Microchip、Altium）都是**对时钟**的，数值 ±1.3 到 ±12.7 mm（ST 写 ±10 mm 且最大 ≤ 20 mm）。它们都是经验值，不是时序推出来的。
- **组内**容差没有任何来源。若要"看齐"，最接近的是 ST 的"对时钟 ±10 mm"。**本板现在不满足这条**：时钟 12.9 mm，地址 / 命令最长 59.0 mm。主会话提案（组内 ±15 mm）也不会让它满足，因为问题在时钟这端。
- 要满足 ST 原文，要么把时钟拉长到地址组中位附近（约 36 mm，多 23 mm，不用蛇形，绕一下就行；但 ST 同时说时钟"avoid serpentine"，且数据线对时钟也要 ±10 mm，数据 12-52 mm 做不到），要么承认这条是经验值而不照办。这是设计取舍，不是电气需要。

### 5.3 三个候选容差

| 候选 | 和时序窗口的关系 | 和来源的关系 | 代价 |
|---|---|---|---|
| ±10 mm | 69 ps，占最坏窗口 3.5%，电气上没必要 | 数字上和 ST（±10 mm）、Altium（400-500 mil）、Microchip（400 mil）看齐，但那些是对时钟的 | 约 110 mm 蛇形，9 根 |
| ±15 mm | 104 ps，占 5.2%，电气上没必要 | 没有来源对应 | 约 38 mm，4 根 |
| ±20 mm | 138 ps，占 6.9%，电气上没必要 | 对应 ST 的"最大 ≤ 20 mm"，以及 everdrone 对 ST 的（误）读 | 约 7 mm，2 根 |
| 不等长，只限 60 mm | 现状已用最坏窗口的 32%（对时钟）、组内差 314 ps | Feranec 等"不需要"的一派 | 0 |

三个都在电气上"无害也无益"，选哪个取决于目的：

- 目的是"练等长流程、数字好看"：±15 mm 可以，不过它的数字没有来源支撑，写进 SPEC 时要说明是练习用。
- 目的是"和业界一条规则看齐"：规则是**对时钟**的，应当写成"每根地址 / 命令线与 SDCLK 的长度差 ≤ X mm"，而不是组内差。按这个写，±10 mm 做不到（时钟太短），±20 mm 对时钟也做不到（A6 比时钟长 46 mm）。
- 目的是"电气上稳"：不需要加任何蛇形，把 60 mm 上限和"每根线对时钟长 ≤ 约 100 mm"（对应最坏窗口的一半以内）写进去就够。

### 5.4 与主会话提案不一致的地方

1. 主会话提案是组内差。厂商和从业者给的数全是对时钟的，没有组内数字；组内差在 SDR 上不是时序约束（1.5 节）。
2. 提案的 ±15 mm 把时钟排除在外。若以后有人拿 ST 的"对时钟 ±10 mm"来审，这块板（对时钟 +0.7 到 +46 mm）通不过，和提案是否执行无关。
3. 如果要加蛇形，加在地址线上的 38 mm 只是形式上的整齐；对 SDRAM 采样没有影响，也不会改善时钟那端的差。
4. 提案里的"几倍于数据线"的比较没有时序基础：数据线真正的约束是写方向对时钟 +72 mm（前人报告，rev Y）和读方向往返和 ≤ 232 mm，不是 ±2.5 mm。

## 6. 没读到 / 没做的

- DS12110 的 rev V 地址表这次只核了写表 Table 169（第 268 页）；读表 Table 167 沿用前人报告，没重读渲染页。
- 地址保持 th(SDCLKL_Add)、CKE 的时序在 DS12110 里没有，按 0 和按地址类推。
- 实际 SDRAM 输入边沿多慢没有 IBIS；边沿降额的 500 ps 是假设。
- 时钟串阻的阻值题设没给，33 Ω 是假设；δ ≈ 0.2 ns 是粗估。
- Micron TN-48-05、TN-46-14 的原文没取到；ISSI、Alliance、Infineon / Cypress、Lattice 没找到 SDR 布线笔记。
- Intel、TI 的 DDR 数字、Cadence 和 TI E2E 的回答、Scribd 文档只见过搜索摘要或无署名转载（[未核]）；st.com、TI E2E、Cadence 社区页面部分返回 403 或超时，没有绕过。
- Phil's Lab、Rick Hartley、Eric Bogatin、Sierra Circuits：搜索无结果。
- NXP HDUG 的 ±50 mil 是读渲染页的；它没写这个数相对什么（只说"all signals at the same length as the EVK board"）。
- 真实板只有两块，长度不含过孔和焊盘短桩；ULX3S 的工作频率、Antmicro 的 SDRAM 型号没核实。没找到 i.MX RT + SDR SDRAM 的 KiCad 板。

## 7. 来源

- ISSI IS42S32800J / IS45S32800J 数据手册 Rev. C（2025-02-25），第 16 页：本地 `stm32h743_sdram/datasheet/42-45S32800J.pdf`。
- ST DS12110 Rev 11：本地 `stm32h743_sdram/datasheet/DS12110_Rev11_stm32h743ii.pdf`，第 145、161、163、268 页。
- ST AN4938 Rev 7：本地 `stm32h743_sdram/datasheet/AN4938_Rev7.pdf`，第 41 页。
- ST AN4661 Rev 5：https://www.st.com/resource/en/application_note/an4661-getting-started-with-stm32f76xxx-and-stm32f77xxx-hardware-development-stmicroelectronics.pdf
- NXP MIMXRT105060HDUG Rev 4：https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/imxrt/23845/1/MIMXRT105060HDUG.pdf
- Microchip AN2717：https://onlinedocs.microchip.com/oxy/GUID-BCEA4067-D69A-4529-81CC-133D9195C03C-en-US-4/GUID-C33E36ED-2752-4075-9EE6-5DBA2F0D2B36.html
- Altium：https://resources.altium.com/p/using-sdram-vs-ddr-ram-your-pcb-design
- FEDEVEL：https://fedevel.com/forum/schematic-design-pcb-layout/82-sdr-sdram-layout-recommendations ；https://courses.fedevel.com/forum/schematic-design-pcb-layout/need-guidance-and-tips-on-routing-sdram-bga
- ST 社区：https://community.st.com/t5/stm32-mcus-touchgfx-and-gui/best-pcb-design-of-fmc-for-stm32f746-and-is42s32400-sdram/m-p/204135 ；https://community.st.com/t5/stm32-mcus-products/fmc-to-connect-external-sdram-do-i-need-length-or-impedance/m-p/780550
- EEVblog：https://www.eevblog.com/forum/eda/sdram-layout-for-newbies/
- Renesas AN-302：https://www.renesas.com/us/en/document/apn/302-connecting-rc32355-sdram-system
- ULX3S：https://github.com/emard/ulx3s ；Antmicro：https://github.com/antmicro/stm32h7-hdmi-board
- 前人报告：`git show origin/research/bus-timing-budget:docs/research/bus-timing-budget.md`
