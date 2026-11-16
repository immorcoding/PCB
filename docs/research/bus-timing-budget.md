# 调研：并行总线等长容差的时序依据

调研日期 2026-11-16。分支 `research/bus-timing-budget`，不合并，不改 `docs/shape/`。

问题：六层测试板（嘉立创 JLC06161H-3313E 叠层）上，STM32H743IIK6（UFBGA176+25）挂着 SDRAM（IS42S32800J-6BLI，FMC，SDCLK 最高 100 MHz）、QSPI Flash（W25Q128JVEIM）、LTDC RGB565 到 40 脚 FPC、SDMMC1（只跑 3.3 V，≤ 50 MHz）、以太网 RMII + LAN8742A。要给每条总线定等长分组和容差，需要知道电气上实际允许多少偏差，好区分"电气必须"和"为了练流程而取紧"。

已有结论不重查：AN4938 §9.4.2 写 SDRAM 数据组内 ±10 mm、SDCLK 对各组 ±10 mm、走线 < 120 mm；ST 的 MB1381 写 100 mil。

## 等级标记

每个数后面标一个等级。

| 标记 | 含义 |
|---|---|
| **[原文]** | 这次打开了文件，在页面上读到这个数（文字层加渲染图核对）。来源在第 9 节，带表号和页码。 |
| **[推导]** | 我用 [原文] 的数加上第 1 节的模型算出来的。模型里的假设写在第 1 节。 |
| **[未核]** | 没有读到原文，或只在搜索摘要里见过。集中列在第 8 节。 |

ps 和 mm 的换算见第 1.1 节。**表里的 mm 一律用带状线 6.9 ps/mm 折算**（偏保守，微带 5.8 ps/mm 时长度更长，括号里给）。

## 0. 结论

### 0.1 结论表

两种硅版本的数值不同时，写成"Rev Y / Rev V"。DS12110 把电气特性分成 rev Y 和 rev V 两套（见 1.3），我没法确认手上的芯片是哪一版，所以较差的那套当最坏情形。所有数都是 [推导]，输入是 [原文]，没有一项含串阻、串扰、抖动、封装内部延迟（见 1.4）。

"往返和"指从 MCU 到器件的时钟线延迟加上数据线（取最长一根）延迟，读方向只有这个和有限制，差不限制。"差"指同一器件处数据线延迟减去时钟线延迟。

| 总线和条件 | 项 | 允许值 | 折算 mm（带状线；微带） | 主要依据 |
|---|---|---|---|---|
| **SDRAM** 100 MHz，CL3，-6 档 | 读：往返和 | ≤ 1600 ps | ≤ 232 mm（276） | DS12110 Table 70 / 167 tsu = 3 ns；ISSI tAC3 = 5.4 ns |
| | 写：数据线比时钟线长 | ≤ +500 ps（Rev Y）/ +2500 ps（Rev V） | 72 mm（86）/ 362 mm（431） | DS12110 Table 72 / 169 td(Data)；ISSI tDS |
| | 写：地址、命令线比时钟线长 | ≤ +2000 ps | 290 mm（345） | Table 72 / 169 td(Add) = 1.5 ns；tAS = tCMS = 1.5 ns |
| | 写：数据线比时钟线短 | ≤ 4000 ps | 580 mm（690） | th(Data) = 0；tDH = 1.0 ns |
| SDRAM 100 MHz，**CL2** | 读：往返和 | ≤ 500 ps | ≤ 72 mm（86） | tAC2 = 6.5 ns |
| SDRAM 80 MHz，CL3 | 读：往返和 | ≤ 4100 ps | ≤ 594 mm（707） | 同上，T = 12.5 ns |
| | 写：数据线比时钟线长 | ≤ +1750 ps（Y）/ +3750 ps（V） | 254 mm / 543 mm | |
| SDRAM 66.7 MHz，CL3 | 读：往返和 | ≤ 6600 ps | ≤ 957 mm | T = 15 ns |
| **QSPI** 100 MHz，SSHIFT = 1 | 读：往返和 | ≤ 2000 ps | ≤ 290 mm（345） | DS12110 Table 171 ts(IN) = 2 ns；W25Q128JV tCLQV = 6 ns |
| | 写：数据线比时钟线长 | ≤ +2000 ps | 290 mm | tv(OUT) = 2 ns；tDVCH = 1 ns |
| | 写：数据线比时钟线短 | ≤ 3000 ps（V）/ 3500 ps（Y） | 435 mm / 507 mm | th(OUT)；tCHDX = 2 ns |
| QSPI 133 MHz，SSHIFT = 1 | 读：往返和 | **−481 ps（按保证值无余量）** | — | 同上，T = 7.52 ns |
| | 写：数据线比时钟线长 | ≤ +759 ps | 110 mm（131） | |
| | 写：数据线比时钟线短 | ≤ 1759 ps（V）/ 2259 ps（Y） | 255 mm / 327 mm | |
| **SDMMC1** HS 50 MHz | 读：往返和 | ≤ 3500 ps（V）/ 3000 ps（Y） | ≤ 507 mm / 435 mm | Table 199（V）/ 100（Y）tISU；SD 规范 tODLY = 14 ns |
| | 写：数据线比时钟线长 | ≤ +9000 ps | 1304 mm | tOV = 5 ns；卡 tISU = 6 ns |
| | 写：数据线比时钟线短 | ≤ 1000 ps（V）/ **0 ps（Y）** | 145 mm / **0 mm** | tOH = 3 / 2 ns；卡 tIH = 2 ns |
| **LTDC** 480 × 272，≤ 12 MHz | 数据线相对时钟 | −29.7 … +29.2 ns | −4300 … +4227 mm | Table 190 / 92；RK043FN48H Tdsu = Tdhd = 12 ns |
| LTDC 800 × 480，40 MHz | 数据线相对时钟 | −2.5 … +2.0 ns（面板 10 ns） | −362 … +290 mm | 同上；Newhaven ASXP-T Tdsu = Tdhd = 10 ns |
| LTDC 800 × 480，33.3 MHz | 数据线相对时钟 | −5.0 … +4.5 ns | −727 … +654 mm | |
| **RMII** 50 MHz，PHY 出 REF_CLK | TX：REF_CLK 线 + TXD / TX_EN 线 | ≤ 1000 ps（Y）/ 1500 ps（V） | ≤ 145 mm / 217 mm | Table 105 / 204 td(TXD)；LAN8742A tsu = 7.5 ns |
| | RX：RXD 线减 REF_CLK 线 | ≥ 0 ps（Y）/ ≥ −1000 ps（V）；≤ +11000 ps | ≥ 0 mm / ≥ −145 mm | tih(RXD) = 3 / 2 ns；PHY toinvld = 3.0 ns |
| RMII 50 MHz，外部时钟给两端 | TX：（MCU 时钟线 + TXD 线）−PHY 时钟线 | ≤ 4500 ps（Y）/ 5000 ps（V） | 652 mm / 725 mm | tsu = 4.0 ns |
| | RX：（PHY 时钟线 − MCU 时钟线）+ RXD 线 | 0 … +3000 ps（Y）；−1000 … +3000 ps（V） | 0 … 435 mm | toval = 15.0 ns |

**读这张表的三个要点**：

1. 表里没有一项要求 mm 级的等长。最紧的一项是 SDRAM 写方向 Rev Y 数据线（+500 ps = 72 mm），比 ST 的 ±10 mm（±69 ps）宽一个数量级。ST 的 ±10 mm 和 MB1381 的 100 mil（2.54 mm，17.5 ps）不是从这些时序表推出来的，应当当作"把第 1.4 节没算的东西打包进去"的经验值。
2. 真正卡电气的是**总长**（读方向往返和）和**方向**（SDMMC Rev Y 的时钟线不能比数据线长；RMII 的 REF_CLK 不能比 RXD 长），不是线与线之间的差。
3. 两处结果会改变设计决定：SDRAM 在 100 MHz 下**必须用 CL3**（CL2 的往返和只有 72 mm）；QSPI 在 133 MHz 下按数据手册保证值**算不通**（−481 ps），要按 ≤ 104 MHz 规划。

### 0.2 每条总线一句结论

| 总线 | 电气上需要蛇形补长吗 | 电气允许的最大偏差 | 取更紧的值就是"练流程" |
|---|---|---|---|
| SDRAM | 不需要；要控制的是总长和 SDCLK 的电容负载 | 写方向数据线比时钟线长最多 72 mm（Rev Y，100 MHz）；读方向时钟线加最长数据线 ≤ 232 mm（CL3） | ±10 mm（ST）和更紧的值都是余量或练习 |
| QSPI | 不需要；133 MHz 不成立，按 ≤ 104 MHz 做 | 100 MHz：读往返和 ≤ 290 mm；写数据线比时钟线长最多 290 mm | 同上 |
| SDMMC1 | 不需要；**注意方向**：Rev Y 上时钟线不要比数据线长 | 读往返和 ≤ 435 mm（Y）；写数据线可以比时钟线长到 1304 mm，但短不得超过 0 mm（Y）/ 145 mm（V） | 同上 |
| LTDC | 不需要；480 × 272 完全没有 mm 级电气要求，800 × 480 在 40 MHz 约 −362 … +290 mm | 480 × 272：±4 m 量级；800 × 480 @ 40 MHz：−2.5 … +2.0 ns | 同上；要求固件把像素时钟极性设成面板采样沿的对侧 |
| RMII | 不需要蛇形；**要管 REF_CLK 线**：PHY 出时钟时 REF_CLK 线加 TXD 线 ≤ 145 mm，REF_CLK 线不得长过 RXD 线（Rev Y） | 见上表 | 同上 |

最后一列的意思：电气上只要不超过表里的值就成立，再往紧取是工程余量（ST 做法）或练流程，由你定。

## 1. 方法和假设

### 1.1 延迟换算

你给的值：带状线约 6.9 ps/mm，微带约 5.8 ps/mm。用叠层交叉检查（输入来自 `research/jlc-6layer-capability` 报告 §5：3313 半固化片 εr 4.1、7628 为 4.4、芯板 4.6、阻焊 3.8，L1 到 L2 间距 0.0994 mm）：

- 带状线 / 全嵌入介质：t_pd = √εr / c（c = 0.2998 mm/ps）。εr = 4.1 / 4.4 / 4.6 时分别为 6.75 / 7.00 / 7.15 ps/mm。[推导]
- L1/L6 微带：用 Hammerstad 公式的有效介电常数，εr = 4.1、h = 0.0994 mm、w = 0.156 mm（该报告算的 50 Ω 线宽）得 εeff = 3.08，t_pd = 5.85 ps/mm（不含阻焊）。[推导]

和你给的 6.9 / 5.8 对得上（差在 ±4 % 内）。下面全部用 6.9 / 5.8。叠层的 εr 是嘉立创反推值，不是板料原值。

换算备用：±10 mm = ±69 ps（带状线）/ ±58 ps（微带）；100 mil = 2.54 mm = 17.5 ps / 14.7 ps；50 Ω 线的单位电容 C′ = t_pd / Z0 = 0.138 pF/mm（带状线）。

### 1.2 时序模型

符号：T = 时钟周期；t_clk = 时钟线（MCU 到器件）延迟；t_dat = 数据、地址或命令线延迟；tsu、th 是接收端要求；td、th(out) 是发送端保证值（min 或 max 取最坏）。所有延迟只算 PCB 走线，不含封装内部。

**读方向**（器件发，MCU 收，MCU 在时钟上升沿采样，器件在时钟边沿发出数据）：

- 建立：t_clk + t_dat + (器件输出延迟 max) + tsu ≤ T，即 `t_clk + t_dat ≤ T − 器件输出延迟 − tsu`。这个限制的是**和**，不是差。
- 保持：t_clk + t_dat + (器件输出保持 min) ≥ th。器件输出保持 min 都是正数（SDRAM tOH = 2.5 ns，QSPI tCLQX = 1.5 ns，SD tOH = 2.5 ns），而 MCU 的 th 要求 0 到 1 ns，所以读保持在这些总线上总是满足。[推导]

**写方向**（MCU 发，器件收，MCU 在时钟边沿的对侧沿发出，器件在下一个时钟沿采样，所以有半个周期）：令 s = t_dat − t_clk，则

`−(T/2 + th(out) − 器件 th) ≤ s ≤ T/2 − td(out) − 器件 tsu`

出处：SDRAM 控制器输出在 SDCLK 下降沿变化（RM0433 Rev 9 第 863 页）；QUADSPI 在 SDR 模式下 IO 只在 CLK 下降沿跳变（RM0433 第 887 页）；DS12110 的 SDRAM、QUADSPI 时序图也是这样画的。[原文] 其余总线的发出沿在各节写明。

### 1.3 硅版本

DS12110 Rev 11（2026-01）把电气特性分成 **rev Y**（第 6 章，第 101 页起）和 **rev V**（第 7 章，第 205 页起）两套，且数字不同。第 22 页（Table 2 的脚注 3）写"最高 480 MHz 只能在 revision V 的器件上得到"。**我没有核实 STM32H743IIK6 现货是哪一版**，所以两套都算，较差的写在前面。本文用到的数里，两套有差别的是：SDRAM 写数据输出有效时间（3 ns 对 1 ns）、SDMMC 输入建立（3 对 2.5 ns）和输出保持（2 对 3 ns）、RMII 的收发时间（见 6.1）、QSPI 输出保持（0.5 对 0 ns）、LTDC 同步信号输出保持（0.5 对 0 ns）。

DS12110 的 FMC、QUADSPI、SDMMC、LTDC 数值都是在 OSPEEDRy[1:0] = 11（RMII 是 10）、I/O 补偿单元打开的条件下测的（第 145、164、196、248、295、308、312 页）。**固件必须配成同样的条件，这些数才成立。** [原文]

### 1.4 没有计入的东西

这张表只有"数据手册 AC 表加走线延迟"一项预算，没算：

- 串联电阻对边沿的影响（ST 在 MCU 侧串 33 Ω，见 2.5；按 33 Ω 乘约 10 pF 估边沿慢约 0.3 ns，会吃掉 SDRAM 读建立余量，[推导]，粗估）；
- 反射、串扰、过冲、同步开关噪声、时钟抖动；
- MCU 封装内部走线、SDRAM 封装内部走线的延迟差（没有一手数据）；
- AC 表的测量电平不同（ISSI 用 1.4 V，ST 用 0.5 VDD）、负载条件不同（ISSI 的 tAC 在 50 pF 下测，ST 在 20 或 30 pF 下测）；
- 数据手册的 min 和 max 同时取最坏组合，本身偏保守。

所以表里的上限是"时序预算算到零"的位置，不是应当用到的位置。

## 2. SDRAM（FMC ↔ IS42S32800J-6BLI）

### 2.1 MCU 侧：DS12110 的 SDRAM 时序

条件（第 160 页 rev Y、第 266 页 rev V）：SDCLK 最高值 rev Y 为 100 MHz（1.8 V < VDD < 3.6 V，20 pF），rev V 为 110 MHz（2.7 V < VDD < 3.6 V，20 pF）。这些数都标"Guaranteed by characterization results"。[原文]

| 参数 | rev Y（Table 70 读 / Table 72 写，第 161、163 页） | rev V（Table 167 读 / Table 169 写，第 267、268 页） |
|---|---|---|
| SDCLK 周期 tw(SDCLK) | 2·Tfmc_ker_ck − 1 … 2·Tfmc_ker_ck + 0.5 ns | 同 |
| **读**数据建立 tsu(SDCLKH_Data) | min 3 ns | min 3 ns |
| **读**数据保持 th(SDCLKH_Data) | min 0 ns | min 0 ns |
| **读**地址有效 td(SDCLKL_Add) | max 1.5 ns | max 1.5 ns |
| **读**片选 td / th | max 1.5 / min 0.5 ns | 同 |
| **读**SDNRAS td / th | max 1 / min 0.5 ns | 同 |
| **读**SDNCAS td / th | max 0.5 / min 0 ns | 同 |
| **写**数据输出有效 td(SDCLKL_Data) | **max 3 ns** | **max 1 ns** |
| **写**数据输出保持 th(SDCLKL_Data) | min 0 ns | min 0 ns |
| **写**地址有效 td(SDCLKL_Add) | max 1.5 ns | max 1.5 ns |
| **写**SDNWE td / th | max 1.5 / min 0.5 ns | 同 |
| **写**片选 td / th | max 1.5 / min 0.5 ns | 同 |
| **写**SDNRAS td / th | max 1 / min 0.5 ns | 同 |
| **写**SDNCAS td / th | max 1 / min 0.5 ns（表里第二个 SDNCAS 行误写成 td，按 hold 读） | 同 |

注意：表里**没有**地址保持时间，也**没有** NBL（DQM）的时序，虽然波形图（Figure 35 / 85）画了 td(SDCLKL_NBL)。下面写方向的地址保持用同表命令信号的 0.5 ns 代替。[原文，缺项是原文的缺项]

### 2.2 SDRAM 侧：IS42S32800J -6 档的 AC 表

读自 ISSI 数据手册 Rev. B1（2021-12-01）第 16 页"AC ELECTRICAL CHARACTERISTICS"，文件是第三方镜像（见 8、9 节）。[原文，镜像]

| 参数 | -6 档 | 说明 |
|---|---|---|
| tCK3 / tCK2（最小时钟周期） | 6 ns / 10 ns | CL3 最高 166 MHz，CL2 最高 100 MHz |
| **tAC3 / tAC2**（从 CLK 到输出，最大） | **5.4 ns / 6.5 ns** | 第 1 页"KEY TIMING PARAMETERS"同值 |
| **tOH3 / tOH2**（输出保持，最小） | 2.5 ns / 2.5 ns | |
| tDS / tDH（数据输入建立 / 保持） | 1.5 ns / 1.0 ns | |
| tAS / tAH（地址建立 / 保持） | 1.5 ns / 1.0 ns | |
| tCMS / tCMH（CS、RAS、CAS、WE、DQM 建立 / 保持） | 1.5 ns / 1.0 ns | |
| tCKS / tCKH（CKE 建立 / 保持） | 1.5 ns / 1.0 ns | |
| tCH / tCL（时钟高 / 低电平宽度） | 2.5 ns / 2.5 ns | |
| tLZ / tHZ3 / tHZ2 | 0 / 2.5…5.4 / 2.5…6.5 ns | |

注 2：输入时间是在边沿时间 tT = 1 ns 下测的，边沿更慢要加 (tT/2 − 0.5) ns；注 3：参考电平 1.4 V（第 16 页）。第 18 页"AC TEST CONDITIONS"：输出负载是 50 Ω 串 50 pF 到 1.4 V；输入 0 到 3.0 V、边沿 1 ns。第 14 页电容：CLK 输入 Cin1 = 2.0 到 4.0 pF，其他输入 Cin2 = 1.5 到 4.0 pF，DQ 的 Ci/o = 4.0 到 6.0 pF。[原文]

-7 档的 tAC3、tOH、tDS 等数与 -6 档相同，只有 tCK3 是 7 ns。

### 2.3 余量计算

**读（SDRAM → MCU）**：往返和上限 = T − tAC − tsu。

| SDCLK | T | CL | tAC | 往返和上限 | 带状线 | 微带 |
|---|---|---|---|---|---|---|
| 100 MHz | 10 ns | 3 | 5.4 | **1600 ps** | 232 mm | 276 mm |
| 100 MHz | 10 ns | 2 | 6.5 | **500 ps** | 72 mm | 86 mm |
| 80 MHz | 12.5 ns | 3 | 5.4 | 4100 ps | 594 mm | 707 mm |
| 80 MHz | 12.5 ns | 2 | 6.5 | 3000 ps | 435 mm | 517 mm |
| 66.7 MHz | 15 ns | 3 | 5.4 | 6600 ps | 957 mm | 1138 mm |
| 66.7 MHz | 15 ns | 2 | 6.5 | 5500 ps | 797 mm | 948 mm |

[推导] 输入：tsu = 3 ns（两套硅版本相同）。读保持余量 = t_clk + t_dat + tOH − th ≥ 2.5 ns，永远满足。80 MHz 对应 fmc_ker_ck = 240 MHz 取 ÷3（SDCLK 只能是 fmc_ker_ck 的 2 或 3 分频，RM0433 第 873 页），66.7 MHz 对应 200 MHz 取 ÷3。

**写（MCU → SDRAM）**：s = t_dat − t_clk 的窗口。上限 = T/2 − td(out) − 器件建立；下限 = −(T/2 + th(out) − 器件保持)。

100 MHz（T/2 = 5 ns）：

| 信号 | 上限（s ≤） | 带状线 | 下限（s ≥） | 带状线 |
|---|---|---|---|---|
| 数据，rev Y | +500 ps（5 − 3 − 1.5） | 72 mm | −4000 ps（−(5 + 0 − 1.0)） | −580 mm |
| 数据，rev V | +2500 ps（5 − 1 − 1.5） | 362 mm | −4000 ps | −580 mm |
| 地址、SDNWE、SDNE | +2000 ps（5 − 1.5 − 1.5） | 290 mm | −4500 ps（−(5 + 0.5 − 1.0)） | −652 mm |
| SDNRAS、SDNCAS（写） | +2500 ps（5 − 1 − 1.5） | 362 mm | −4500 ps | −652 mm |

80 MHz（T/2 = 6.25 ns）：数据 rev Y 上限 +1750 ps（254 mm），rev V +3750 ps（543 mm），地址 +3250 ps（471 mm），下限数据 −5250 ps。66.7 MHz（T/2 = 7.5 ns）：数据 rev Y +3000 ps（435 mm），rev V +5000 ps（725 mm），地址 +4500 ps，下限数据 −6500 ps。[推导]

所以同一字节通道内、数据对时钟的差，窗口总宽（上限 − 下限）rev Y 是 4.5 ns（652 mm），rev V 是 6.5 ns（942 mm）。数据线之间的错位 = 窗口里放得下的部分。

**对 ST 的 ±10 mm 的判断**：±10 mm = ±69 ps，是最紧的单边上限（rev Y 数据线，+500 ps）的 14 %，是窗口总宽（4.5 ns）的 3 %。**电气上不需要这么紧；它大概是把串扰、抖动、封装差打包后的余量**（ST 没有写推导，[未核]）。

**对 AN4938 的 120 mm 的判断**：时钟线和最长数据线都跑满 120 mm 时往返和 = 240 mm = 1656 ps，比 CL3 的 1600 ps 多 56 ps。按 -6 档 AC 表的保证值，这个长度在 100 MHz 下刚好不成立，但 tAC 是在 50 pF 负载下测的，实际负载更轻时 tAC 会小一些（没有 IBIS 可核，[未核]）。**所以 100 MHz 下不要把两根线都做到 120 mm；本板是 BGA 对 BGA，走线远短于此，用不上。**

**CL2 在 100 MHz 下不可用于长线**：往返和只有 500 ps（72 mm）。固件要设 CL3（ISSI 的 -6 档在 100 MHz 下支持 CL3，因为 tCK3 最小 6 ns）。ST 的 H743I-EVAL 驱动也是 CL3（见 2.4）。[推导]

**SDCLK 的电容负载**：DS12110 的 SDRAM 时序是在 20 pF 下测的（第 160、266 页），AN4938 写 3.3 V 下单线走线电容 ≤ 20 pF、总负载 ≤ 30 pF（第 41 页）。SDRAM 的 CLK 引脚 2 到 4 pF（第 14 页）。按 C′ = 0.138 pF/mm（1.1），时钟线最长约 (20 − 4) / 0.138 = 116 mm。[推导，粗估]

### 2.4 RPIPE 对走线延迟的意义

[原文] RM0433 Rev 9：

- 第 873 页，FMC_SDCRx 的 RPIPE[1:0]："These bits define the delay, in fmc_ker_ck clock cycles, for reading data after CAS latency. 00: No fmc_ker_ck clock cycle delay; 01: One; 10: Two; 11: reserved."
- 第 865 页：读 FIFO 存放 CAS 延迟期间和 RPIPE 延迟期间提前读出的数据，条数 = CAS Latency + 1 + (RPIPE DIV2)。
- 第 863 页：SDRAM 控制器所有输出在 SDCLK 下降沿变化。
- RM0433 里 RPIPE 只出现在 SDRAM 一章（第 865、866 页的读 FIFO 说明、第 873 页的寄存器描述、Figure 121 的标题）和修订历史里，**没有一处**把它和 PCB 走线延迟联系起来；DS12110 全文 grep RPIPE 零处。

[原文] ST 的 H743I-EVAL BSP（`stm32h743i_eval_sdram.c` 第 210 到 214 行）：CASLatency = 3，SDClockPeriod = FMC_SDRAM_CLOCK_PERIOD_2（SDCLK = fmc_ker_ck ÷ 2），ReadBurst = ENABLE，**ReadPipeDelay = RPIPE_DELAY_0**。

[推导] 如果 RPIPE 的作用是把读数据的采样点往后推 Δ（= 1 个 fmc_ker_ck，÷2 时是 T/2 = 5 ns），则采样时刻从 T 变成 T + Δ，建立余量增加 Δ，但保持要求变成 `往返和 ≥ Δ − tOH + th = 5 − 2.5 + 0 = 2.5 ns`（约 360 mm），小板上做不到。所以**走线短时 RPIPE = 0**，RPIPE 只对往返延迟 ≥ 2.5 ns 的长线有意义。这个推导假定 RPIPE 移动的是采样点，**RM0433 没有写是移动采样点还是采样之后再流水，[未核]**。

### 2.5 ST 官方板怎么做

**MB1246（STM32H743I-EVAL / H753I-EVAL，Rev E-03，2022-05-23，原理图 18 页）** [原文，读图]：

- 第 5 页（SRAM & FLASH & SDRAM）：U15 IS42S32800J-6BLI，D0 到 D31 全接。SDRAM 侧文字层里没有 33R、22R、10R 等串阻字样；前人报告（`research/st-reference-schematics` §5.1）读到的唯一串阻是 SDCKE1 上 R282 的 0 Ω。**SDRAM 侧没有串联电阻或排阻，也没有端接。**
- 第 3 页（MCU）：多数 FMC 引脚到总线之间在 **MCU 一侧**有 33 Ω 串阻（图上标 33），NBL0、NBL1 没有。我只在低分辨率渲染图上看到串阻的分布，没有逐根枚举，[图]。这条总线上同时挂着 SRAM（U16）和 NOR（U12），拓扑不同于本板的单颗 SDRAM。
- 第 2 页（Top，方块图）：FMC 一组红线（A[0..23]、D[0..31]、SDCLK、SDNE1、SDNRAS、SDNCAS、SDNWE）外面画了一个椭圆，标 **"Same length"**，旁注 "90MHz clock"；NBL0 到 NBL3 和 SDCKE1 是蓝线，不在椭圆里。**没有写数值容差。** 同一页 QSPI 一组标 "Same length"（"133MHz clock"），SD 卡一组标 "Same length"（"208MHz clock"），ULPI 一组标 "Same length"（"60MHz clock"）。
- 全 18 页只有第 16 页（ST-LINK 的 USB）有写成数值的 "Matched Net Lengths [Tolerance = 0.2mm]" 和 "Impedance Constraint [Min = 85 Max = 95]"。
- BSP 的 SDCLK 是 fmc_ker_ck ÷ 2。Top 页写 90 MHz，我没法把它和 BSP 的时钟配置对上，[未核]。

**MB1381（STM32H750B-DK，Rev B-04，2024-09-27，原理图 22 页）：100 mil 的原文和范围** [原文，读图]：

- 第 9 页（SDRAM）右上角，红字 "Matched Net Lengths [Tolerance = 100mil]"，下面是红圈 "i" 标记，圈里写 "SDRAM"。红圈标在：SDRAM_A[0..11] 总线、SDRAM_D[0..15] 总线，以及 SDNE1、SDCKE1、SDNCAS、SDNRAS、SDNWE、SDCLK 六根线。渲染图上 BA0、BA1、NBL0、NBL1 旁边没有标记。**所指的范围是名为 SDRAM 的这一组网络，规则文字没有写比较对象，也没有写推导。** 红圈 "i" 在 AD 里应当是网络指令（Net Class / Parameter Set 一类），我没有 AD 工程文件，规则怎么写的看不到，[未核]。
- 同样的 100 mil 注记还出现在第 5 页（Ethernet，这块板是 **MII + LAN8740Ai**，不是 RMII）、第 6 页（PoE，4 处）、第 10 页（eMMC）、第 11 页（QSPI，11 根线：CS1、CS2、CLK、IO0 到 IO7，渲染图上 11 个红圈）、第 12 页（LCD4.3：LCD_R / G / B[0..7]、HSYNC、VSYNC、CLK，DE 和 DISP 没标）和第 17 页（ST-LINK）。**这块板对 SDRAM、QSPI、LCD 用的是同一个数 100 mil，没有按总线频率区分，这说明 100 mil 是通用经验值，不是每条总线各自推出来的。**
- MB1381 的 SDRAM 只接 D0 到 D15（DQ16 到 DQ31 经 10 kΩ 下拉，见 `research/sdram-32bit-bga` §4）。第 11 页 QSPI 的 R65、R69、R30、R31 等也是 33R 串阻；第 12 页 LCD 这一页的 RGB 线上没有画串阻（MCU 一侧的第 3 页我没看）。

**AN4938 Rev 7**（第 41 页 §9.4.2）[原文]：

- 参考平面 GND 或 PWR（PWR 要加 10 nF 缝合电容）；走线阻抗 50 Ω ± 10 %；走线长度 < 120 mm，超过要端接。
- 数据组内长度差 ±10 mm；时钟对数据 / 地址组 ±10 mm；时钟对地址和命令组每根线 ±10 mm（上限 ≤ 20 mm）。
- 数据线与地址 / 控制线放不同层，同层要隔 5 mm；SDCLK 放内层，离其他信号至少 3 倍线宽，过孔尽量少，**不要蛇形**。
- 走线电容：3.3 V 时单线 20 pF，总负载不超过 30 pF。

## 3. QSPI（QUADSPI ↔ W25Q128JVEIM）

### 3.1 数值

MCU 侧：DS12110 QUADSPI SDR 模式，**rev V Table 171（第 270 页）、rev Y Table 74（第 164 页）**，条件 2.7 V < VDD < 3.6 V、CL = 20 pF、OSPEEDRy = 11、I/O 补偿打开 [原文]：

| 参数 | rev V | rev Y |
|---|---|---|
| 时钟频率 | 133 MHz | 133 MHz |
| 数据输入建立 ts(IN)（2.7 到 3.6 V） | min 2 ns | min 2 ns |
| 数据输入保持 th(IN)（2.7 到 3.6 V） | min 1 ns | min 1 ns |
| 数据输出有效 tv(OUT) | typ 1，max 2 ns | typ 1.5，max 2 ns |
| 数据输出保持 th(OUT) | min 0 ns | min 0.5 ns |

DDR 模式（rev V Table 172，第 271 页）最高 100 MHz，ts 2.5 / th 1 ns，tv(OUT) max 6 ns（DHHC = 0）。**本文不算 DDR。**

Flash 侧：Winbond W25Q128JV-DTR **Rev D（2025-02-04，PDF 第 91 页，页脚印 90）** §9.6 [原文]：FR = 133 MHz（3.0 到 3.6 V，除 03h 读和 DTR 指令）；104 MHz（2.7 到 3.0 V）；**tCLQV（CLK 低到输出有效）max 6 ns；tCLQX（输出保持）min 1.5 ns；tDVCH（数据输入建立）min 1 ns；tCHDX（数据输入保持）min 2 ns**。§9.5（PDF 第 90 页）AC 测量条件的负载电容为 30 pF。

采样沿：RM0433 第 887 页：SDR 模式下 QUADSPI 驱动 IO 只在 CLK 下降沿跳变，接收时假定 Flash 也在 CLK 下降沿发数据，SSHIFT = 0 时用**下一个（上升）沿**采样；第 892 页、第 900 页：SSHIFT = 1 时"移到再下一个沿"（采样点晚半个周期，用来补外部信号延迟）。ST 的 H743I-EVAL BSP（`stm32h743i_eval_qspi.c`）：STR 模式 ClockPrescaler = 1（注释"max 108 MHz"），SampleShifting = HALFCYCLE。[原文]

### 3.2 余量计算

**读（Flash → MCU）**：

- SSHIFT = 0：数据在 T/2 + t_rt + tCLQV 到达，要在 T 前再留 ts(IN)：`t_rt ≤ T/2 − 8 ns`，t_rt 取 0 也要 T ≥ 16 ns，即 **只在 ≤ 62.5 MHz 才成立**。[推导]
- SSHIFT = 1：`t_rt ≤ T − tCLQV − ts(IN) = T − 8 ns`。

| QUADSPI 时钟 | T | 往返和上限 | 带状线 | 微带 |
|---|---|---|---|---|
| 133 MHz | 7.519 ns | **−481 ps** | 不成立 | 不成立 |
| 104 MHz | 9.615 ns | 1615 ps | 234 mm | 279 mm |
| 100 MHz | 10 ns | **2000 ps** | 290 mm | 345 mm |
| 80 MHz | 12.5 ns | 4500 ps | 652 mm | 776 mm |
| 66.7 MHz | 15 ns | 7000 ps | 1014 mm | 1207 mm |

[推导] 读保持：t_rt + tCLQX − th(IN) = t_rt + 0.5 ns ≥ 0.5 ns，总满足。

**133 MHz 为负的含义**：是 tCLQV 的最坏值（6 ns，30 pF）加 ts(IN) 的最坏值（2 ns）已经超过一个周期（7.52 ns），走线长度为 0 也不成立。ST 的 BSP 在 STR 模式的预分频注释里写"max 108 MHz"（那是针对它板上的 Micron Flash，不是本板的 W25Q128JV），只能说明 ST 自己也没有用 133 MHz。**数据手册的保证值只说明"不能保证"，不是"一定不通"**：轻负载下实际 tCLQV 通常更小，我没有一手数据去证明，[未核]。本板按 ≤ 104 MHz 规划才有数据手册支撑。

**写（MCU → Flash）**：s = t_dat − t_clk，上限 = T/2 − tv(OUT) − tDVCH，下限 = −(T/2 + th(OUT) − tCHDX)。

| QUADSPI 时钟 | 上限（s ≤） | 带状线 | 下限（s ≥） | 带状线 |
|---|---|---|---|---|
| 133 MHz | +759 ps | 110 mm（微带 131） | −1759 ps（V）/ −2259 ps（Y） | −255 mm / −327 mm |
| 104 MHz | +1808 ps | 262 mm | −2808 ps（V）/ −3308 ps（Y） | −407 mm / −479 mm |
| 100 MHz | +2000 ps | 290 mm | −3000 ps（V）/ −3500 ps（Y） | −435 mm / −507 mm |
| 80 MHz | +3250 ps | 471 mm | −4250 ps（V）/ −4750 ps（Y） | −616 mm / −688 mm |

[推导] nCS 的 tSLCH / tCHSL / tCHSH / tSHCH（都是 3 ns）以及 /HOLD 时序没有算。

### 3.3 小结

最紧的是 133 MHz 的写上限 +759 ps（110 mm）和读往返和（负值）。±10 mm（69 ps）是 +759 ps 的 9 %。AN4938 的 120 mm 单线上限跑满时（时钟线 120 mm + 数据线 120 mm = 240 mm = 1656 ps），在 100 MHz 下读成立（上限 2000 ps），在 133 MHz 下不成立。AN4938 §9.4.3（第 42 页）要求 QUADSPI 数据组内 ±10 mm，走线 < 120 mm，时钟不蛇形，不要把数据放多层，时钟离其他信号 3 倍线宽 [原文]；它没有写时钟对数据的差。

## 4. SDMMC1（高速模式 50 MHz，3.3 V）

### 4.1 数值

MCU 侧：DS12110 **rev V Table 199（第 308、309 页）、rev Y Table 100（第 196 页）**，条件 CL = 30 pF、OSPEEDRy = 11、I/O 补偿打开、VOS1（rev V）[原文]：

| 参数（HS 模式，f_PP ≥ 50 MHz） | rev V | rev Y |
|---|---|---|
| 时钟频率 f_PP 最大 | 133 MHz | 125 MHz |
| 输入建立 tISU | min 2.5 ns | min 3 ns |
| 输入保持 tIH | min 0.5 ns | min 0.5 ns |
| 输出有效 tOV | typ 3.5，max 5 ns | typ 3.5，max 5 ns |
| 输出保持 tOH | min 3 ns | min 2 ns |
| 输入有效窗口 tIDW | min 3 ns | min 3 ns |

SD 默认模式（25 MHz，rev V）：tISUD 2.5、tIHD 0.5、tOVD max 2、tOHD min 0（第 309 页）。

卡侧：SD Specifications Part 1 Physical Layer Specification **Version 3.01（2010-02-18）Table 6-6 "Bus Timing – Parameters Values (High Speed)"**（PDF 第 170 到 171 页，页脚印 154 到 155）[原文，第三方副本，带保密水印]：f_PP 0 到 50 MHz；tWL、tWH ≥ 7 ns；输入 CMD、DAT：**tISU ≥ 6 ns，tIH ≥ 2 ns**（C_CARD ≤ 10 pF）；输出：**tODLY ≤ 14 ns**（CL ≤ 40 pF），**tOH ≥ 2.5 ns**（CL ≤ 15 pF）；每线总电容 ≤ 40 pF（1 张卡）。表下脚注 1："为满足严格的时序，主机只应驱动一张卡。"

时序图（DS12110 Figure 107，第 310 页）：HS 模式下输出在 CK 上升沿之后 tOV 变化，保持到下一个 CK 上升沿之后 tOH；输入在 CK 上升沿前 tISU、后 tIH。[原文]

### 4.2 余量计算

**读（卡 → MCU）**：往返和上限 = T − tODLY − tISU = 20 − 14 − tISU = 3500 ps（rev V，507 mm）/ 3000 ps（rev Y，435 mm）。读保持：往返和 + 2.5 − 0.5 ≥ 2.0 ns，总满足。[推导]

**写（MCU → 卡）**：s = t_dat − t_clk；上限 = T − tOV − 卡 tISU = 20 − 5 − 6 = **+9000 ps（1304 mm）**；下限 = 卡 tIH − tOH = 2 − 3 = **−1000 ps（rev V，−145 mm）**，2 − 2 = **0 ps（rev Y）**。[推导]

**rev Y 的 0 ps 下限的含义**：最坏情形下，数据线的延迟不能比时钟线短，**即时钟线不能比 DAT / CMD 线长**；rev V 允许时钟线比数据线长 145 mm。这是方向要求，不是等长要求。实际余量比 0 大，因为 min 值取的是最坏角，我没有典型值可用，[未核]。做法上等价于：**SDMMC_CK 不要比 D0 到 D3、CMD 长**（AD 里相当于给 CK 设一个"不长于"的长度规则，而不是 Matched Lengths）。

AN4938 §9.4.1（第 40 页）[原文]：参考平面 GND 或 PWR；50 Ω ± 10 %；"保持数据与时钟的长度相等"；"数据与时钟的最大偏差应小于 250 ps @ 10 mm"（**原文如此，这句话和下面 10 mm 的说法在数量上对不上：10 mm 只有 69 ps**，我没法解释，按原文引用）；走线 < 120 mm，超过要端接；走线电容 ≤ 20 pF（3.3 V）、≤ 15 pF（1.8 V）；走线电感 < 16 nH；CMD 和数据线要有推荐的上拉；**数据线之间、数据与 CK、CK 与 CMD 的不一致 < 10 mm**；数据线之间过孔数量相同。

## 5. LTDC（RGB565 → 40 脚 FPC）

### 5.1 数值

MCU 侧：DS12110 **rev V Table 190（第 295 页，Figure 95 在第 296 页）、rev Y Table 92（第 185 页）**，条件 CL = 30 pF、OSPEEDRy = 11、I/O 补偿打开、24 位像素（用 RGB565 不会让时序更差，[推导]）[原文]：

| 参数 | rev V | rev Y |
|---|---|---|
| LTDC 时钟最高 | 150 MHz（2.7 到 3.6 V，20 pF）/ 133 MHz（2.7 到 3.6 V）/ 90 MHz（1.62 到 3.6 V） | 同 |
| 数据输出有效 tv(DATA)，2.7 到 3.6 V | max 0.5 ns（1.62 到 3.6 V 时 5 ns） | max 0.5 ns |
| 数据输出保持 th(DATA) | min 0 ns | min 0 ns |
| HSYNC / VSYNC / DE 输出有效 | max 0.5 ns | max 0.5 ns |
| HSYNC / VSYNC / DE 输出保持 | min 0 ns | min 0.5 ns |
| 时钟占空比 | 45 到 55 % | 同 |

AN4861 Rev 7（第 47 页）[原文]：像素时钟低于 40 MHz（SVGA）时简单的 3.3 V 信号就够；负载和线长缩小可到 83 MHz；建议 LTDC GPIO 设最高速度 OSPEEDRy = 11。其 §4.1 Table 5 写"数据由显示器在 LCD_CLK 的上升沿**或**下降沿读取"。AN4861 没有给走线长度要求，只让去看 AN4661、AN4488（F7、F4 的）。

面板侧：

| 面板 | 像素时钟 | 数据建立 / 保持 | 来源 |
|---|---|---|---|
| Rocktech RK043FN48H-CT672B（480 × 272，OTA5180A） | 5 / 9 / 12 MHz（min / typ / max） | **Tdsu ≥ 12 ns，Tdhd ≥ 12 ns**（DE、HSYNC、VSYNC 也是 12 ns） | Rocktech 规格书 v1.0（2015-03-09），PDF 第 12 页 §7.1 和第 13 页 §7.3.1；该文件是第三方镜像 |
| Newhaven NHD-7.0-800480AF-ASXP-T（800 × 480，ST7277） | 23 / 25 / 27 MHz | **Tdsu ≥ 10 ns，Tdhd ≥ 10 ns**；引脚表写 DCLK "Falling Edge"（输入数据在时钟下降沿采样） | Newhaven 规格书，PDF 第 9 页（页脚印 8）和第 5 页（页脚印 4） |

RK043FN48H 的规格书自己写"详细时序见 OTA5180A 规格书"，OTA5180A 的规格书我没取到。其他 800 × 480 面板（DWIN LN80480T070IA9098：33.3 MHz typ，8 ns；AMPIRE AM-800480HTMQW-T00H：28 到 40 MHz，8 ns；LM700：33.26 MHz，6 ns）只在搜索摘要里见到，**没有读到原文**，[未核]。

ST 的 H743I-EVAL BSP（`stm32h743i_eval_lcd.c` 第 504 到 507 行）把 `PCPolarity` 设为 `LTDC_PCPOLARITY_IPC`（反相像素时钟）。[原文]

### 5.2 余量计算

输出在时钟的一个沿变化，面板在对侧沿采样（半个周期），则 s = t_dat − t_clk 的窗口：上限 = T/2 − tv(DATA) − 面板 Tdsu，下限 = −(T/2 + th(DATA) − 面板 Tdhd)。[推导]

| 面板和像素时钟 | T/2 | 上限 | 下限 |
|---|---|---|---|
| 480 × 272，12 MHz，12 ns | 41.7 ns | +29.2 ns（4227 mm） | −29.7 ns（−4300 mm） |
| 480 × 272，9 MHz，12 ns | 55.6 ns | +43.1 ns | −43.6 ns |
| 800 × 480，40 MHz，10 ns | 12.5 ns | **+2.0 ns（290 mm；微带 345）** | **−2.5 ns（−362 mm；微带 −431）** |
| 800 × 480，33.3 MHz，10 ns | 15 ns | +4.5 ns（654 mm） | −5.0 ns（−727 mm） |
| 800 × 480，40 MHz，8 ns | 12.5 ns | +4.0 ns（580 mm） | −4.5 ns（−652 mm） |

**必须由固件配对的一条**：如果 MCU 和面板在**同一个沿**上动作（即不是半周期路径），则保持方向 th(DATA) = 0 对面板 Tdhd = 10 到 12 ns，需要数据线多出 10 到 12 ns 的延迟，也就是 1.5 到 1.7 m 线，做不到。所以必须把 PCPOL 设成使 MCU 的变化沿和面板的采样沿相反（ST 的 BSP 设的是 IPC）。RK043FN48H 规格书的时序图我没读清是哪个沿，[未核]。

### 5.3 小结

480 × 272 在 9 到 12 MHz 下，电气上没有任何 mm 级要求。800 × 480 在 40 MHz 下，窗口是 −2.5 到 +2.0 ns（约 ±300 mm），仍然不要求 mm 级等长。**LTDC 线上没有时钟对数据的短线要求，要求的是负载和固件的极性。** 数据手册的 CL 是 30 pF，对应 0.138 pF/mm 约 217 mm 减去面板和 FPC 的输入电容（没有一手数据）。[推导，粗估]

## 6. 以太网 RMII（LAN8742A）

### 6.1 数值

MCU 侧：DS12110 **rev V Table 204（第 313 页）、rev Y Table 105（第 201 页）**，条件 OSPEEDRy = 10、CL = 20 pF（第 312、200 页）[原文]：

| 参数 | rev V | rev Y |
|---|---|---|
| 接收数据建立 tsu(RXD) | min 2 ns | min 2 ns |
| 接收数据保持 tih(RXD) | min 2 ns | min 3 ns |
| 载波侦听建立 / 保持 tsu / tih(CRS) | min 1.5 / 1.5 ns | min 2.5 / 2 ns |
| 发送使能有效 td(TXEN) | 7 / 8 / 9.5 ns（min / typ / max） | 4 / 4.5 / 7 ns |
| 发送数据有效 td(TXD) | 8 / 9 / 11 ns | 7 / 7.5 / 11.5 ns |

时序图（Figure 112 / 60）：TX 输出在 REF_CLK 上升沿后 td 变化；RX 输入以 REF_CLK 上升沿为中心取建立、保持。

PHY 侧：LAN8742A **Rev 1.1（2013-05-21，SMSC）**§5.6.4，第 123 页 Table 5.12 和第 125 页 Table 5.13、5.14（页脚印 123、125）[原文，第三方镜像]；测量条件：系统负载 10 到 25 pF。

| 参数 | REF_CLK Out 模式（nINTSEL 拉低，25 MHz 晶振，PHY 出 50 MHz） | REF_CLK In 模式（外部 50 MHz 到 CLKIN） |
|---|---|---|
| RXD / CRS_DV 输出有效（相对上升沿）toval | max 7.0 ns | max 15.0 ns |
| RXD / CRS_DV 输出变为无效 toinvld | min 3.0 ns | min 3.0 ns |
| TXD / TXEN 建立 tsu | min 7.5 ns | min 4.0 ns |
| TXD / TXEN 保持 tihold | min 2.0 ns | min 1.5 ns |
| 时钟 | 周期 20 ns，高低各 40 到 60 % | 50 MHz，漂移 ±50 ppm，占空比 40 到 60 %，抖动 150 ps p-p |

### 6.2 余量计算

两种时钟方案：

**A. REF_CLK 由 PHY 输出（Out 模式），给 MCU 的 REF_CLK 引脚。** t_clkM = PHY 的 REFCLKO 到 MCU 的线延迟；t_txd、t_rxd 为 TXD、RXD 线延迟。

- TX：MCU 在收到的 REF_CLK 沿后 td 发出，PHY 在它自己的 REF_CLK 沿采样：`t_clkM + t_txd ≤ T − td(TXD)max − tsu = 20 − 11.5 − 7.5 = 1000 ps`（rev Y，145 mm）；rev V：20 − 11 − 7.5 = 1500 ps（217 mm）。TXEN 用 td(TXEN)max（7 或 9.5 ns），余量更大。TX 保持满足（td min 7 ns 对 tihold 2 ns）。
- RX：PHY 在自己的 REF_CLK 沿后 toval ≤ 7.0 ns 发出，MCU 在收到的 REF_CLK 沿采样。建立：`t_rxd − t_clkM ≤ T − toval − tsu = 20 − 7 − 2 = 11000 ps`；保持：`t_rxd − t_clkM ≥ tih(RXD) − toinvld = 3 − 3.0 = 0 ps`（rev Y）/ `2 − 3.0 = −1000 ps`（rev V）。

所以 A 方案下：**REF_CLK 线（PHY 到 MCU）加 TXD 线 ≤ 145 mm（Rev Y）；REF_CLK 线不得比 RXD 线、CRS_DV 线长（Rev Y，余量 0）。** [推导]

**B. 外部 50 MHz 晶振给两端（In 模式），MCU 的 REF_CLK 引脚和 PHY 的 CLKIN 各一条线。** t_clkM、t_clkP 为到 MCU、到 PHY 的时钟线延迟。

- TX：`(t_txd + t_clkM) − t_clkP ≤ T − td(TXD)max − tsu = 20 − 11.5 − 4.0 = 4500 ps`（rev Y，652 mm）/ 5000 ps（rev V，725 mm）；下限 `≥ tihold − td(TXD)min = 1.5 − 7 = −5500 ps`（rev Y）/ −6500 ps（rev V）。
- RX：`(t_clkP − t_clkM) + t_rxd` 的窗口：建立 ≤ T − toval − tsu = 20 − 15 − 2 = 3000 ps；保持 ≥ tih − toinvld = 3 − 3.0 = 0 ps（Y）/ −1000 ps（V）。即窗口 0 到 +3000 ps（Y）/ −1000 到 +3000 ps（V），约 0 到 435 mm。[推导]

**TXD0、TXD1、TX_EN 之间、RXD0、RXD1、CRS_DV 之间的错位**：TX 只有最长那根的建立会限制，RX 的限制写在窗口里；以上窗口都在 145 mm 到 652 mm 量级，所以也不要求 mm 级等长。

### 6.3 小结

RMII 最该管的是**时钟线**：A 方案里 REF_CLK 线要短且不比 RXD 长，B 方案里两端时钟线尽量等长（窗口 3 ns 宽，容易满足）。AN4938 没有 RMII 一节；ST 的 MB1246 第 2 页（Top）里以太网一组没有标 "Same length"，MB1381 的以太网是 MII 不是 RMII（100 mil）。[原文，读图]

RMII 联盟规格书（REF_CLK 50 MHz ± 50 ppm，TX 建立 / 保持 4 / 2 ns，RX 输出延迟 2 到 14 ns 一类的数）我没有读到原文，**不要引用**，[未核]。

## 7. 给决定用的刻度

下面只是把事实放在一起，不是建议。

| 刻度 | ps（带状线） | 说明 |
|---|---|---|
| ST AN4938：±10 mm | ±69 ps | SDRAM 数据组内、时钟对数据 / 地址、QUADSPI 数据组内、SDMMC 的数据与 CK、CK 与 CMD |
| ST AN4938：时钟对地址 / 命令线，上限 ≤ 20 mm | ±138 ps | 同一条里"with maximum of ≤ 20 mm" |
| ST MB1381：100 mil（2.54 mm） | ±17.5 ps | SDRAM、QSPI、LCD、MII、eMMC 同一个数 |
| 电气允许，SDRAM 写数据线（rev Y，100 MHz，最紧一项） | +500 ps（+72 mm） | 另一侧 −4000 ps |
| 电气允许，QSPI 写（133 MHz，最紧一项） | +759 ps（+110 mm） | 另一侧 −1759 ps（V） |
| 电气允许，SDMMC 写（rev Y，最紧一项） | 下限 0 ps | 时钟线不得比数据线长 |
| 电气允许，RMII（A 方案，rev Y） | RX 下限 0 ps | REF_CLK 线不得比 RXD 线长 |

两个事实提醒：

- 在 SDRAM、QSPI 这类两侧都有窗口的总线上，±10 mm（69 ps）最多占去最紧单边上限的 14 %（SDRAM rev Y 写数据线）和 9 %（QSPI 133 MHz 写）。把它再取紧到 mm 以下（比如 ±1 mm = ±6.9 ps），时序上没有收益，换来的是蛇形线的占板面积、串扰和 KiCad 里调长度的工作量；这是"练流程"的取法。
- SDMMC（rev Y）和 RMII（A 方案）的限制是方向性的下限 0 ps，不是对称容差。AN4938 对 SDCLK、QUADSPI 时钟都写"避免蛇形"。这几条放在一起：时钟线（SDCLK、SDMMC_CK、REF_CLK、QUADSPI CLK）宜先定长度，不做蛇形，差额出现时补在数据线一侧。后一半是我从上面的方向性下限推出来的做法，不是原文。

## 8. 没核实

| 项目 | 原因 | 影响 |
|---|---|---|
| **手上 STM32H743IIK6 是 rev Y 还是 rev V** | 没有实物；DS12110 两套数值不同 | 取了较差情形；影响 SDRAM 写数据上限（500 对 2500 ps）、SDMMC 下限（0 对 −1000 ps）、RMII 的 RX 下限 |
| ISSI IS42S32800J 的 AC 表是否和最新版一致 | issi.com 返回反爬页（Incapsula），没有绕过；用的是 `cdn.components.ru` 镜像的 Rev. B1（2021-12-01），页眉是 ISSI；前人报告提到官网最新是 Rev. C（2025-02-25），没对照 | tAC、tOH、tDS、tDH 若有改动，余量要重算（-6 档这几项 ISSI 通常不变，但没证据） |
| SDRAM 的 IBIS、实际 tAC（轻负载） | 没取到 IBIS；tAC 在 50 pF 下测 | 读方向余量偏保守 |
| RPIPE 到底是移动采样点还是采样后流水 | RM0433 没写机理；DS12110 没提 RPIPE | 2.4 的推导依赖此假设 |
| DS12110 的 SDRAM 地址保持、NBL（DQM）时序 | 数据手册表里没有 | 用命令信号的保持值代替地址保持；NBL 没算 |
| DS12110 时序是否含 MCU 侧 33 Ω 串阻 | 数据手册只写 CL，没提串阻 | ST 的做法会吃掉 SDRAM 读建立余量约 0.3 ns（粗估） |
| MCU 和器件封装内部走线延迟差 | 没有一手数据 | 所有结果都没含 |
| W25Q128JV 在轻负载下的实际 tCLQV；133 MHz 是否真的不可用 | Rev D 只给 max 6 ns（30 pF） | 只能说"保证值不支持 133 MHz" |
| QUADSPI DDR（≤ 100 MHz）、nCS、/HOLD 时序 | 没算 | |
| SD 卡总线 tISU / tIH / tODLY / tOH | sdcard.org 返回 403；用的是 embdev.net 论坛附件里的 Version 3.01（2010-02-18）副本，页眉带 "Confidential" 和下载者水印 | 新版规范的高速模式数值没对照 |
| RK043FN48H 的采样沿和 OTA5180A 的时序 | 规格书 AC 表读到了，时序图没读清沿；OTA5180A 规格书没取到 | 5.2 里的"对侧沿"是假设；只有 Rocktech 能给准确答案 |
| 800 × 480 面板的典型值 | 只读到 Newhaven ASXP-T 一份原文；DWIN、AMPIRE、LM700 只有搜索摘要 | 窗口按 10 ns 和 8 ns 各算了一档 |
| LAN8742A 最新版数据手册 | microchip.com 的 PDF 返回 403（curl 和 WebFetch 都是），没有绕过；用的是 DESY 站点上的 Rev 1.1（2013-05-21，SMSC 页眉） | 新版数值没对照 |
| RMII 联盟规格书的时序数 | 没读 | 不引用 |
| 叠层的 εr | 嘉立创的反推值，不是板料原值；ps/mm 取你给的 6.9 / 5.8 并用 εr 交叉检查，差在 ±4 % 内 | 所有 mm 数有 ±4 % 的不确定 |
| 反射、串扰、抖动、同步开关噪声、过孔 | 没算 | 表里的上限是预算算到零的位置 |
| ST 的 ±10 mm、100 mil 的推导来历 | AN4938 和 MB1381 都没有写 | 只能当经验值引用 |
| MB1246 第 2 页 "90MHz clock" 和 BSP 的 SDCLK 的关系 | BSP 的 fmc_ker_ck 没查 | |
| AN4938 §9.4.1 "250 ps @ 10 mm" 的含义 | 原文如此，和同节的 10 mm 对不上 | 不引用这句 |
| MB1381 的 Altium 规则本体（红圈 "i"） | 没有 AD 工程文件，只能从 PDF 判断 | 100 mil 的比较对象（组内两两还是对时钟）不能确认 |

## 9. 来源

页码都是 PDF 页码（DS12110、RM0433、AN4938、LAN8742A 的 PDF 页码和印刷页码相同；Winbond 的 PDF 页码比印刷页码大 1）。

**ST 一手来源**

- [DS12110 Rev 11（STM32H742xI/G、STM32H743xI/G 数据手册）](https://www.st.com/resource/en/datasheet/stm32h743vi.pdf)，2026-01，357 页：SDRAM 读 / 写时序 rev Y Table 70 / 71 / 72 / 73（第 161、162、163 页）、rev V Table 167 / 168 / 169 / 170（第 267、268 页起）；FMC 测量条件第 145 页（rev Y）、第 248 页（rev V）；SDRAM 时钟上限第 160 页、第 266 页；QUADSPI Table 74 / 75（第 164、165 页）、Table 171 / 172（第 270、271 页）；SDMMC Table 100（第 196 页）、Table 199 / 200（第 308、309 页），Figure 107 / 108 / 109（第 310 页）；LTDC Table 92（第 185 页）、Table 190（第 295 页），Figure 95 / 96（第 296 页）；以太网 Table 105（第 201 页）、Table 204（第 313 页），条件第 200 / 312 页。
- [RM0433 Rev 9](https://www.st.com/resource/en/reference_manual/rm0433-stm32h742-stm32h743753-and-stm32h750-value-line-advanced-armbased-32bit-mcus-stmicroelectronics.pdf)，3329 页：第 863 页（SDRAM 输出沿）、第 865 页（读 FIFO 与 RPIPE）、第 873 页（FMC_SDCRx：RPIPE、SDCLK、CAS）、第 887 页（QUADSPI SDR / DDR 沿）、第 892 页（延迟采样）、第 900 页（SSHIFT）、第 1217 页附近（LTDC_GCR 的 PCPOL，描述只有"active low / high"）。
- [AN4938 Rev 7](https://www.st.com/resource/en/application_note/an4938-getting-started-with-stm32h74xig-and-stm32h75xig-mcu-hardware-development-stmicroelectronics.pdf)：§9.4.1 SDMMC（第 40 页）、§9.4.2 FMC（第 41 页）、§9.4.3 QUADSPI（第 42 页）。
- [AN4861 Rev 7（LTDC）](https://www.st.com/resource/en/application_note/an4861-lcdtft-display-controller-ltdc-on-stm32-mcus-stmicroelectronics.pdf)：第 47 页。
- ST 原理图：[MB1246 H753 E-03](https://www.st.com/resource/en/schematic_pack/mb1246-h753-e03_schematic.pdf)（第 2、3、5、16 页）、[MB1381 H750XB B-04](https://www.st.com/resource/en/schematic_pack/mb1381-h750xb-b04.pdf)（第 5、9、11、12 页，及其余含 Matched Net Lengths 的第 6、10、17 页）。
- ST BSP：[stm32h743i_eval_sdram.c](https://raw.githubusercontent.com/STMicroelectronics/stm32h743i-eval-bsp/master/stm32h743i_eval_sdram.c)（第 210 到 214 行）、[stm32h743i_eval_qspi.c](https://raw.githubusercontent.com/STMicroelectronics/stm32h743i-eval-bsp/master/stm32h743i_eval_qspi.c)（第 115 到 116、151 行）、[stm32h743i_eval_lcd.c](https://raw.githubusercontent.com/STMicroelectronics/stm32h743i-eval-bsp/master/stm32h743i_eval_lcd.c)（第 504 到 507 行）。

**器件厂商**

- [Winbond W25Q128JV-DTR Rev D，2025-02-04](https://www.winbond.com/resource-files/W25Q128JV_DTR%20RevD%2012232024%20Plus.pdf)：§9.5（PDF 第 90 页）、§9.6（PDF 第 91 页）。从 winbond.com 取得。
- ISSI IS42S32800J / IS45S32800J 数据手册 Rev. B1，2021-12-01：[镜像（cdn.components.ru）](https://cdn.components.ru/media/PDF/205047.pdf)，第 1、14、16、18 页。官方地址 `https://www.issi.com/WW/pdf/42-45S32800J.pdf` 返回反爬页。
- LAN8742A / LAN8742Ai 数据手册 Rev. 1.1（2013-05-21）：[镜像（desy.de）](https://www.zeuthen.desy.de/~sulanke/Projects/ICECUBE/mDOM/mainboard/datasheets/eth_phy_LAN8742a.pdf)，第 123、125 页。
- [Rocktech RK043FN48H-CT672B 规格书 v1.0，2015-03-09（镜像：wiki.kewl.org）](https://wiki.kewl.org/_media/boards:rk043fn48h-ct672b-v1.0.pdf)，PDF 第 12、13 页。
- [Newhaven NHD-7.0-800480AF-ASXP-T 规格书](https://newhavendisplay.com/content/specs/NHD-7.0-800480AF-ASXP-T.pdf)，PDF 第 5、9 页。
- SD Specifications Part 1 Physical Layer Specification Version 3.01：[embdev.net 附件](https://embdev.net/attachment/520782/Part_1_Physical_Layer_Specification_Ver3.01_Final_100218.pdf)，PDF 第 170 到 171 页（Table 6-6）。同一版的 Simplified Specification（[utexas.edu 副本](https://www.cs.utexas.edu/~simon/378/resources/Part_1_Physical_Layer_Simplified_Specification_Ver_3.01_Final_100518.pdf)）把 §6.6、§6.7 总线时序留空，所以没用。

**本仓库前人报告**（`git show origin/research/<name>:docs/research/<name>.md`）

- `research/jlc-6layer-capability`（叠层 εr、50 Ω 线宽）、`research/sdram-32bit-bga`（SDRAM 选型、MB1381 的 100 mil 位置）、`research/st-reference-schematics`（MB1246 的 33 Ω 串阻、AN4938 的硬性要求）、`research/qspi-flash`（W25Q128JV 选型）。

**只在搜索摘要里见过，没有读原文**（见第 8 节）：DWIN LN80480T070IA9098、AMPIRE AM-800480HTMQW-T00H、LM700 的 800 × 480 面板数值；ISSI 官网的最新数据手册。
