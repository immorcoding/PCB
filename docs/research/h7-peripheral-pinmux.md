# 调研：外设组合和引脚复用的可行性（工单 #8）

日期 2026-11-16。票据：[immorcoding/PCB#8](https://github.com/immorcoding/PCB/issues/8)（地图 #1，被 #7 阻塞、阻塞 #9）。分支 `research/h7-peripheral-pinmux`，只存档不合并。

问题：STM32H743IIK6（UFBGA176+25）已接 32 位 SDRAM（FMC）和一颗 QSPI Flash 之后，哪些外设能同时分到引脚而不冲突，让 MCU 的引脚占用达到六成以上（84 / 140）。

标记：**[核]** 我亲自在规格书、ST 官方文档或数据库里读到；**[图]** 从渲染出来的页面图上读到；**[推]** 我自己的计算或判断；**[未核]** 来自搜索摘要、记忆或下游代理的转述，没有对照原文。第 10 节集中列出已验证和未验证。

## 0. 结论

**一处计数更正（要用户确认）**：SDRAM 是 **57** 个脚（A12 已含在内），不是 #7 写的 58。SDRAM + QSPI = 63（45.0%），到 84 还差 **21**；加上必需脚（SWD、HSE、LSE、调试串口共 8）后基础占用 71（50.7%），只差 13。（第 1.1 节）

**三套组合**（SDRAM 57 + QSPI 6 + 必需脚 8 + 外设；全部逐脚分配、逐脚核过冲突，见第 2–5 节）：

| | 套 A　显示型 | 套 B　摄像头 + USB 高速型 | 套 C　ST EVAL 同款子集 |
|---|---|---|---|
| 外设 | LTDC RGB565 20 + 以太网 RMII 9 + SDMMC1（4 位）6 + FDCAN1 2 | DCMI 12 位 15 + ULPI 12 + 以太网 RMII 9 | 以太网 RMII 9 + SDMMC1 6 加转换器控制 4 + ULPI 12 + FDCAN1 2 |
| 外设脚数 | 37 | 36 | 33 |
| QSPI（组内定） | CLK PB2、NCS PB6、IO0–3 = PF8 / PF9 / PF7 / PF6 | CLK PF10、NCS PB6、IO0–3 同左 | 同套 B |
| 调试串口 | USART1：PB14 / PB15 | USART1：PA9 / PA10 | USART1：PA9 / PA10 |
| **IO 占用（/ 140）** | **108（77.1%）** | **107（76.4%）** | **104（74.3%）** |
| 含辅助脚上限 | 118（84.3%） | 115（82.1%） | 110（78.6%） |
| 按球：信号球（/ 201） | 111（55.2%） | 110（54.7%） | 107（53.2%） |
| 按球：含 58 个电源地球 | 169（84.1%） | 168（83.6%） | 165（82.1%） |
| 额外电压轨 | 5 V（CAN）；背光升压到约 17 V；可选隔离 5 V | 1.8 V、2.8 V、1.5 V（摄像头）；5 V（USB VBUS）；ULPI 的 1.8 V 未核 | 1.8 V（SD 转换，但 IP4856 做不了）；2.9 V（EVAL 的 SD 卡电源）；5 V |
| 并行线（线序价值） | LTDC 20 条 + CLK、HSYNC、VSYNC、DE | DCMI 15 条（PIXCLK 反向）+ ULPI 12 条（60 MHz） | ULPI 12 条 + SDMMC 6 条 |
| 外设落在内两圈的信号 | 7 | 8 | 6 |
| 最挤的边（已用 / 容量） | 右 29 / 32 | 左 27 / 29 | 左 26 / 29 |
| ST 官方参考 | 此封装上没有 LTDC 参考 | ETH、ULPI 在 H743I-EVAL；DCMI 8 位接口在 H747I-DISCO | ETH、SD、ULPI、CAN 全在 H743I-EVAL（UM2198 表 68 逐脚一致） |
| 主要风险 | LTDC 的脚被迫散在四条边；SD 不能接转换器控制脚（UHS-I 做不了）；面板型号已被 ST 换过 | 并行摄像头传感器几乎都已停产；USB3320C 规格书没拿到 | IP4856 是 0.4 mm WLCSP，在嘉立创六层工艺外，4 根转换器脚没有对应器件 |

**推荐套 B**。理由：
1. **并行线最多、类型最全**：DCMI 12 位 + ULPI 8 位数据 + 时钟，两条同步总线、方向不同（PIXCLK 由传感器送入，ULPI 的 CK 由 PHY 送入且数据双向）；再加 SDRAM 的 57 条，三条总线的线序约定都能验。套 A 的 LTDC 线更多，但频率低（480 × 272 约 9 MHz），对时序约束松。[推]
2. **电源最丰富**：1.8 V、2.8 V、1.5 V 三路低压轨加 5 V，能验证"电源面分块、多轨去耦"；套 A 只有 5 V 和一个升压环路，套 C 只有 1.8 V / 2.9 V / 5 V。
3. **出线通道的压力在三套里居中**：外设对内两圈的增量 8 个，最挤的边是左边（27 / 29），套 A 的右边（29 / 32）更满。
4. **ETH 和 ULPI 与 ST 的 H743I-EVAL 引脚完全一致**，原理图可以照 MB1246 画；DCMI 的三根同步线（PA6、PA4、PB7）在 H747I-DISCO 原理图的摄像头页上也能看到（文字层乱码，只当旁证）。
5. 套 B 可以按需裁剪：DCMI 降到 8 位则 IO 合计 103（73.6%）；再去掉以太网到 94（67.1%）；仍可再加外挂 SRAM（+6 到 +8 脚）。
套 B 的短板：摄像头传感器要么停产要么没有官网规格书，建议板上只放 FPC 连接器和三路电源，传感器或模块外接；USB3320C 的规格书没有拿到，VDD1.8 是否要外供要用户从 Microchip 官网下载后核对。**如果用户更看重"全部照 ST 官方原理图画"，选套 C，但要先决定那 4 根转换器控制脚怎么办（第 6.3 节）；如果更看重一个真实的开关升压环路，选套 A。**

**对线序的价值（[推]）**：并行线条数 LTDC（20）> DCMI（15）> ULPI（12）> SDMMC1（6）；对时序最敏感的是 ULPI（60 MHz 同步，双向）和 SDMMC（50 MHz 起，UHS-I 到 208 MHz），以太网 RMII（50 MHz，2 位）和 CAN 没有价值。

**互斥关系**（第 9.1 节）：LTDC 和 ULPI、LTDC 和 DCMI 在这个封装上互斥（各有一两个信号只有同一个脚）；LTDC 和 SDMMC1 的转换器控制脚互斥；LTDC RGB888 和以太网互斥；ULPI 和 FDCAN2 互斥。所以"并行线最多"只能二选一：套 A（LTDC）或套 B（DCMI + ULPI）。

**其他发现**：
- 只要板上有以太网 RMII，SDCKE0 / SDNE0 就只能是 PH2 / PH3；SDNWE 在带 ULPI 的套里只能是 PH5（套 A 还可用 PC0）。三个都在内圈（F4、G4、J4）；#7 已定前两个，PH5 在这里补定。
- 套 B、C 的左边第 4 列 E4–J4 五个内圈球全部有信号（SDRAM 3 个 + ULPI 2 个），QSPI 簇（K1、K2、L1–L3）挨着 SDRAM 的 A0–A5，左边是三套里最需要和 SDRAM 一起排的地方。
- FDCAN1 的 PA11 / PA12 是 5 V 容忍脚（FT_u），可以直连 5 V 的 CAN 收发器 RXD 输出（TCAN1042 非 V 款的 RXD 高电平约 5 V）。
- H743I-EVAL（MB1246）原理图文字层里出现的器件：LAN8742A-CZ-TR、USB3320C-EZK、IP4856CX25/C、WM8994、MCP2562FD、IS61WV102416BLL-10MLI-TR，可以直接当本板外设器件的 ST 参考。

**未核对项（带到方案定稿，完整清单见第 10.2 节）**：
1. SDRAM 脚数 57 还是 58（本报告的更正，用户确认）。
2. Microchip 的 LAN8742A、USB3320C、MCP2562FD 和 Nexperia 的 IP4856 的规格书一份都没拿到（官网 403），VDD 范围、USB3320 的 VDD1.8 是否外供、LAN8742A 的脚距、生命周期全部未核。
3. 并行摄像头传感器的官方规格书和生命周期（OV5640、OV2640 只有非官网镜像；AR0144 完整规格书没拿到；MT9V034、AR0130 已停产或将停产）。
4. 24 脚 FPC 摄像头模块的板级供电要求（要不要在这块板上给 2.8 / 1.8 / 1.5 V）没查。
5. IP4856 的 0.4 mm WLCSP 超出规格档 C，套 C 的 4 根转换器控制脚没有可用器件（TXS02612RTW 不是 UHS-I）。
6. 面板 RK043FN48H 的 FPC 脚距、RGB565 只接高位的做法没在规格书里找到，ST 自己的板子已经换过型号。
7. 求解器的"最优"只是圈数之和最小加 QSPI 外框最小，没有考虑 PHY / 连接器的实际位置；引脚分配在布局阶段可以调（以太网 TX 侧有 PG14、PB11–PB13 备选，LTDC、DCMI 的多数信号有 2–4 个备选；RX 侧、MDC、MDIO、REF_CLK 和 ULPI 没有备选）。
8. 出线通道只做了定性分析，没有算容量。

## 1. 口径和基数

### 1.1 SDRAM 是 57 个脚，不是 58 个（需要用户确认）

#7 写"SDRAM 占 58 个脚（原 57 个加 A12）"。脚本从引脚库里数出的结果是 **57**，A12 已经在里面：

| 信号 | 个数 |
|---|---|
| D0–D31 | 32 |
| A0–A12 | 13（256 Mb 只用 A0–A11，A12 接 H3 球留给 512 Mb） |
| BA0、BA1 | 2 |
| NBL0–NBL3 | 4 |
| SDCLK、SDNCAS、SDNRAS、SDNWE、SDCKE0、SDNE0 | 6 |
| 合计 | **57** |

[核]（`base.py` 数出 57，A0–A11 单算是 56）。"58"的来源看起来是 #2 报告写"57 个信号"（A0–A12 已含）、#7 里 QSPI 报告的 §7 的清单写 A0–A11 却也写"57"，#7 再加了一次 A12。**更正后：SDRAM 57 + QSPI 6 = 63（45.0%），距 84 还差 21，不是 20。** 下面所有数字都按 57 算。

### 1.2 占用怎么数

- **必需脚**（任何组合都要留）：SWD 2（PA13、PA14）、HSE 2（PH0、PH1）、LSE 2（PC14、PC15）、调试串口 2。BOOT0（D6）、NRST（J1）、PDR_ON（C6）不是 GPIO 球，不占 140 个 IO，但算信号球。
- **基础占用** = SDRAM 57 + QSPI 6 + 必需脚 8 = **71（50.7%）**。离 84 还差 13，所以任何一个并行外设（LTDC 20 脚、DCMI 11 脚以上）加一两个小外设就达标；下面三套都远超 84，是为了让总线和电压轨够多。
- **三种口径**：
  - 按 IO：已用 GPIO 数 / 140。
  - 按球（信号球）：已用 GPIO + NRST + BOOT0 + PDR_ON，除以 201。
  - 按球（含电源地球）：再加全部 58 个电源 / 地 / VCAP 球（它们一定都接），除以 201。数据库里 Type = Power 的球正好 58 个。[核]
- **辅助脚**（PHY 复位、SD 卡检测、背光 PWM 之类）另外列，不计入下面的头条数字；每套末尾给出"含辅助脚"的上限。
- 201 = 140 GPIO + 3（NRST、BOOT0、PDR_ON）+ 58 电源地球。按"信号球 / 201"算，**三套都只有 53–55%，达不到六成**；要用六成做门槛，口径必须是"IO / 140"（目标 84 本来就是这么来的），或者含电源地球。这是 #9 要定的口径问题。

## 2. 三套共用的部分

### 2.1 引脚数据库和校验 [核]

- 引脚、球号、可选功能：ST 的 `STM32_open_pin_data`（GitHub，CubeMX 6.18.0 的子集）里 `mcu/STM32H743IIKx.xml` 和 `mcu/IP/GPIO-STM32H747_gpio_v1_0_Modes.xml`；球号与 KiCad 符号 `STM32H743IIKx` 逐球比对，201 个球 0 处不一致。
- 与 DS12110 Rev 11 Table 9 的 UFBGA176+25 列比对：138 个 GPIO 球全部一致（PC14、PC15、PH0、PH1 的行在文字里拆成多行，没自动比，球号 E1、F1、G1、H1 在前票里核过）。
- 三套里每个（引脚、信号）组合，信号名都出现在 DS12110 Table 9 该引脚的"备选功能"文字里（`check_ds.py`，301 组，0 个缺）。
- AF 编号：数据库里的 AF 号与 DS12110 Table 10（p.89–99）渲染出来的图逐页看过，三套用到的每个引脚的 AF 都对得上。
- 冲突由 `solve.py` 的回溯求解器保证：同一个球不被两个信号占用，也不占 SDRAM 的 57 个脚、SWD、HSE、LSE、QSPI 的 6 个脚、调试串口的 2 个脚。每套选出的方案，求解器是在"圈数之和最小，QSPI 六个球的外框最小"的目标下找的（外圈优先：外两圈顶层直出），不是随手挑的。

### 2.2 SDRAM 57 脚（固定，三套相同）

来源：DS12110 Table 9/10，AF12（FMC）；与 #2 报告 §4 的清单一致。表里括号是圈号（0 = 最外圈）。[核]

| 信号组 | 端口:球(圈) |
|---|---|
| D0–D7 | D0=PD14:M14(1)　D1=PD15:L14(1)　D2=PD0:B12(1)　D3=PD1:C12(2)　D4=PE7:R8(0)　D5=PE8:P8(1)　D6=PE9:P9(1)　D7=PE10:R9(0) |
| D8–D15 | D8=PE11:P10(1)　D9=PE12:R10(0)　D10=PE13:N11(2)　D11=PE14:P11(1)　D12=PE15:R11(0)　D13=PD8:P15(0)　D14=PD9:P14(1)　D15=PD10:N15(0) |
| D16–D23 | D16=PH8:M12(3)　D17=PH9:M13(2)　D18=PH10:L13(2)　D19=PH11:L12(3)　D20=PH12:K12(3)　D21=PH13:E12(3)　D22=PH14:E13(2)　D23=PH15:D13(2) |
| D24–D31 | D24=PI0:E14(1)　D25=PI1:D14(1)　D26=PI2:C14(1)　D27=PI3:C13(2)　D28=PI6:C3(2)　D29=PI7:C2(1)　D30=PI9:D3(2)　D31=PI10:E3(2) |
| A0–A6 | A0=PF0:E2(1)　A1=PF1:H3(2)　A2=PF2:H2(1)　A3=PF3:J2(1)　A4=PF4:J3(2)　A5=PF5:K3(2)　A6=PF12:P6(1) |
| A7–A12 | A7=PF13:N6(2)　A8=PF14:R7(0)　A9=PF15:P7(1)　A10=PG0:N7(2)　A11=PG1:M7(3)　A12=PG2:L15(0) |
| BA0/BA1、NBL0–3 | BA0=PG4:K14(1)　BA1=PG5:K13(2)　NBL0=PE0:A4(0)　NBL1=PE1:A3(0)　NBL2=PI4:D4(3)　NBL3=PI5:C4(2) |
| 命令和时钟 | SDCLK=PG8:H14(1)　SDNCAS=PG15:B7(1)　SDNRAS=PF11:R6(0)　SDNWE=**PH5**:J4(3)　SDCKE0=PH2:F4(3)　SDNE0=PH3:G4(3) |

圈分布：0 圈 11 个、1 圈 20 个、2 圈 17 个、3 圈 9 个，合计 57；其中内两圈（要打孔）26 个。按边：下 18、右 18、左 12、上 9。[推]（脚本按球号算）

**SDCKE0 / SDNE0 / SDNWE 的选择在三套里被外设锁死**：这三个信号各有三个可选脚，其中 PA7（SDNWE）、PC4（SDNE0）、PC5（SDCKE0）正好是以太网 RMII 的 CRS_DV、RXD0、RXD1 的唯一脚，PC0（SDNWE 的另一个）是 ULPI_STP 的唯一脚，PC2_C / PC3_C 有 1 mA 的限流（勘误 ES0392 §2.2.26）。所以只要板上有以太网，SDNE0 / SDCKE0 只剩 **PH3 / PH2**（PC2_C / PC3_C 限流不选）；SDNWE 在有 ULPI 的套（B、C）里只剩 **PH5**，在套 A（没有 ULPI）里还可以用 PC0（M2，1 圈）。三套统一取 PH5（也是 ST H743I-EVAL 的做法）。#7 已定 PH2 / PH3，这里补上 SDNWE = PH5。这三个球都在 3 圈（F4、G4、J4），要打孔。[核+推]

### 2.3 必需脚（三套相同）

| 功能 | 端口 | 球 | 圈 |
|---|---|---|---|
| SWDIO / SWCLK | PA13 / PA14 | A15 / A14 | 0 / 0 |
| HSE 晶振 | PH0 / PH1 | G1 / H1 | 1 / 1 |
| LSE 晶振 | PC14 / PC15 | E1 / F1 | 0 / 0 |

圈号由脚本按球号算，H0/H1 的行在 Table 9 里拆行，球号来自引脚库和前票。BOOT0 = D6、NRST = J1、PDR_ON = C6（非 GPIO）。调试串口因套而异（见各套）。

### 2.4 以太网 RMII（三套的引脚完全相同）

PHY 与 MCU 之间 9 根线。RX_ER 不接（RMII 可选，ST 板上 LAN8742A 的 RXER 脚经 10 kΩ 下拉、不接 MCU，见第 6.1 节）。TXD1 取 PG12 与 ST H743I-EVAL 一致（PG14 也行）。[核]

| 信号 | 端口 | 球 | 圈 | 边 | AF |
|---|---|---|---|---|---|
| ETH_RMII_REF_CLK | PA1 | N2 | 1 | 左 | 11 |
| ETH_RMII_CRS_DV | PA7 | R3 | 0 | 下 | 11 |
| ETH_RMII_RXD0 | PC4 | N5 | 2 | 下 | 11 |
| ETH_RMII_RXD1 | PC5 | P5 | 1 | 下 | 11 |
| ETH_RMII_TX_EN | PG11 | B9 | 1 | 上 | 11 |
| ETH_RMII_TXD0 | PG13 | A8 | 0 | 上 | 11 |
| ETH_RMII_TXD1 | PG12 | B8 | 1 | 上 | 11 |
| ETH_MDC | PC1 | M3 | 2 | 左 | 11 |
| ETH_MDIO | PA2 | P2 | 1 | 下/左 | 11 |

这 9 个信号分散在三个边：左（PA1、PC1）、下（PA7、PC4、PC5、PA2）、上（PG11–PG13）。TX 侧三根线在上边相邻的 A8、B8、B9，RX 侧在下边。这是封装给定的，改不了；PHY 的 RMII 线要绕半个 MCU。[推]

ST 官方板的对照：H743I-EVAL（UM2198 Table 68，p.71–75，RevE）用的就是 PA1、PA2、PA7、PC1、PC4、PC5、PG11、PG12、PG13，与上表一致。[图]

### 2.5 QSPI 的引脚（每套定一组）

选项表来自 #7（DS12110 Table 9/10，球号与 KiCad 符号一致），这里再对数据库核了一遍：16 个备选脚全部在库里，没有一个是 SDRAM 的脚。[核]

三套里 QSPI 的选择由求解器给出，目标是六个球靠在一起：

| 信号 | 套 A | 套 B、套 C |
|---|---|---|
| CLK | PB2（M6，3 圈，下） | PF10（L1，0 圈，左） |
| BK1_NCS | PB6（B6，1 圈，上） | PB6（B6，1 圈，上） |
| BK1_IO0 | PF8（L3，2 圈，左，AF10） | 同左 |
| BK1_IO1 | PF9（L2，1 圈，左，AF10） | 同左 |
| BK1_IO2 | PF7（K1，0 圈，左，AF9） | 同左 |
| BK1_IO3 | PF6（K2，1 圈，左，AF9） | 同左 |

- 套 A 里 PF10 要让给 LTDC_DE（DE 在这个封装上只有 PF10 和 PE13 两个脚，PE13 是 SDRAM 的 D10），所以 CLK 退到 PB2（M6）。如果 LCD 面板用 HSYNC/VSYNC 模式、不接 DE，CLK 就能回到 PF10。
- NCS 在三套里都是 PB6（B6）：PG6（J15）在套 A 被 LTDC_R7 占了，在套 B、C 里没被占，但 PB6 离 PF 簇的距离差不多，求解器取了 PB6。NCS 不是时序关键线。[推]
- PF6–PF9 是一簇相邻的球（K2、L2、L3 加 K1），紧挨着 SDRAM 的 A3–A5（J2、J3、K3），出线通道会抢，见第 8 节。

## 3. 套 A：显示型（LTDC RGB565 + 以太网 + SD 卡 + CAN FD）

**组成**：LTDC 20 脚（R3–R7、G2–G7、B3–B7、CLK、DE、HSYNC、VSYNC）、以太网 RMII 9 脚（第 2.4 节）、SDMMC1 4 位 6 脚、FDCAN1 2 脚、调试串口 2 脚（USART1 PB14/PB15，与 EVAL 相同）。

### 3.1 逐脚分配（本套独有的部分；以太网、QSPI、SDRAM、必需脚见第 2 节）

**LTDC**（20 脚）[核+图]

| 信号 | 端口 | 球 | 圈 | 边 | AF |
|---|---|---|---|---|---|
| LCD_R3 | PB0 | R5 | 0 | 下 | 9 |
| LCD_R4 | PA5 | P4 | 1 | 下 | 14 |
| LCD_R5 | PA9 | E15 | 0 | 右 | 14 |
| LCD_R6 | PB1 | R4 | 0 | 下 | 9 |
| LCD_R7 | PG6 | J15 | 0 | 右 | 14 |
| LCD_G2 | PA6 | P3 | 1 | 下 | 14 |
| LCD_G3 | PG10 | B10 | 1 | 上 | 9 |
| LCD_G4 | PB10 | R12 | 0 | 下 | 14 |
| LCD_G5 | PB11 | R13 | 0 | 下 | 14 |
| LCD_G6 | PC7 | G15 | 0 | 右 | 14 |
| LCD_G7 | PD3 | D11 | 3 | 上 | 14 |
| LCD_B3 | PA8 | F15 | 0 | 右 | 13 |
| LCD_B4 | PA10 | D15 | 0 | 右 | 12 |
| LCD_B5 | PA3 | R2 | 0 | 下 | 14 |
| LCD_B6 | PB8 | A5 | 0 | 上 | 14 |
| LCD_B7 | PB9 | B4 | 1 | 上 | 14 |
| LCD_CLK | PG7 | J14 | 1 | 右 | 14 |
| LCD_DE | PF10 | L1 | 0 | 左 | 14 |
| LCD_HSYNC | PC6 | H15 | 0 | 右 | 14 |
| LCD_VSYNC | PA4 | N4 | 2 | 下 | 14 |

**SDMMC1**（4 位 + CMD + CK，6 脚）[核+图]

| 信号 | 端口 | 球 | 圈 | 边 | AF |
|---|---|---|---|---|---|
| SDMMC1_CK | PC12 | A12 | 0 | 上 | 12 |
| SDMMC1_CMD | PD2 | D12 | 3 | 上/右 | 12 |
| SDMMC1_D0 | PC8 | G14 | 1 | 右 | 12 |
| SDMMC1_D1 | PC9 | F14 | 1 | 右 | 12 |
| SDMMC1_D2 | PC10 | B14 | 1 | 上/右 | 12 |
| SDMMC1_D3 | PC11 | B13 | 1 | 上 | 12 |

**FDCAN1**（2 脚）：FDCAN1_RX = PA11（C15，0 圈，AF9）、FDCAN1_TX = PA12（B15，0 圈，AF9）。[核+图]

**调试串口**：USART1_TX = PB14（R14，0 圈，AF4）、USART1_RX = PB15（R15，0 圈，AF4）。[核+图]

**辅助脚（示例，可换）**：LCD 背光 PWM = PB5（TIM3_CH2）、LCD 使能 = PG14、触摸 I2C = PD12 / PB7（I2C4，AF4 / AF6）、触摸中断 = PG3、ETH 复位 = PC13、ETH 中断 = PI8、SD 卡检测 = PE3、SD 卡电源使能 = PD7、CAN STB = PE2。共 10 个。PC13 和 PI8 属备份域供电，输出按 3 mA 标称（DS12110 Table 52），只适合慢速控制线。[核]

**SD 卡的限制**：套 A 的 SDMMC1 不能接 CKIN / CDIR / D0DIR / D123DIR 这四个电平转换器控制脚，因为 LTDC_B6 / B7 / HSYNC 在这个封装上只有 PB8 / PB9 / PC6 一个脚（见第 9.1 节冲突表）。所以 SD 卡只能走 3.3 V（默认速度 / 高速，≤ 50 MHz），不能做 UHS-I 的 1.8 V 切换；要 UHS-I 就改用 SDMMC1 并放弃 LTDC，或接自动方向的转换器（第 6.3 节，但 0.4 mm 的都做不了）。[推]

### 3.2 占用

| 项 | 脚数 |
|---|---|
| SDRAM | 57 |
| QSPI | 6 |
| 必需脚（SWD 2 + HSE 2 + LSE 2 + 调试串口 2） | 8 |
| LTDC | 20 |
| 以太网 | 9 |
| SDMMC1 | 6 |
| FDCAN1 | 2 |
| **IO 合计** | **108 / 140 = 77.1%** |
| 含辅助脚（+10） | 118 / 140 = 84.3% |
| 按球（信号球 = IO + 3）| 111 / 201 = 55.2% |
| 按球（含 58 个电源地球） | 169 / 201 = 84.1% |

[推]（`combos.py` 输出）

## 4. 套 B：摄像头 + USB 高速型（DCMI 12 位 + ULPI + 以太网）

**组成**：DCMI 15 脚（D0–D11 + HSYNC、VSYNC、PIXCLK，支持 8 / 10 / 12 位三档，前 8 位 + 3 根同步线 = 11 脚）、ULPI 12 脚、以太网 9 脚、调试串口 2 脚（USART1 PA9/PA10）。

### 4.1 逐脚分配

**DCMI**（15 脚）[核+图]

| 信号 | 端口 | 球 | 圈 | 边 | AF |
|---|---|---|---|---|---|
| DCMI_D0 | PC6 | H15 | 0 | 右 | 13 |
| DCMI_D1 | PC7 | G15 | 0 | 右 | 13 |
| DCMI_D2 | PG10 | B10 | 1 | 上 | 13 |
| DCMI_D3 | PC9 | F14 | 1 | 右 | 13 |
| DCMI_D4 | PE4 | B1 | 0 | 左 | 13 |
| DCMI_D5 | PD3 | D11 | 3 | 上 | 13 |
| DCMI_D6 | PB8 | A5 | 0 | 上 | 13 |
| DCMI_D7 | PE6 | B3 | 1 | 上 | 13 |
| DCMI_D8 | PC10 | B14 | 1 | 上/右 | 13 |
| DCMI_D9 | PC12 | A12 | 0 | 上 | 13 |
| DCMI_D10 | PD6 | B11 | 1 | 上 | 13 |
| DCMI_D11 | PD2 | D12 | 3 | 上/右 | 13 |
| DCMI_HSYNC | PA4 | N4 | 2 | 下 | 13 |
| DCMI_PIXCLK | PA6 | P3 | 1 | 下 | 13 |
| DCMI_VSYNC | PB7 | B5 | 1 | 上 | 13 |

**ULPI**（12 脚，套 B、套 C 相同）[核+图]

| 信号 | 端口 | 球 | 圈 | 边 | AF |
|---|---|---|---|---|---|
| OTG_HS_ULPI_CK | PA5 | P4 | 1 | 下 | 10 |
| OTG_HS_ULPI_D0 | PA3 | R2 | 0 | 下 | 10 |
| OTG_HS_ULPI_D1 | PB0 | R5 | 0 | 下 | 10 |
| OTG_HS_ULPI_D2 | PB1 | R4 | 0 | 下 | 10 |
| OTG_HS_ULPI_D3 | PB10 | R12 | 0 | 下 | 10 |
| OTG_HS_ULPI_D4 | PB11 | R13 | 0 | 下 | 10 |
| OTG_HS_ULPI_D5 | PB12 | P12 | 1 | 下 | 10 |
| OTG_HS_ULPI_D6 | PB13 | P13 | 1 | 下 | 10 |
| OTG_HS_ULPI_D7 | PB5 | A6 | 0 | 上 | 10 |
| OTG_HS_ULPI_DIR | PI11 | E4 | 3 | 左 | 10 |
| OTG_HS_ULPI_NXT | PH4 | H4 | 3 | 左 | 10 |
| OTG_HS_ULPI_STP | PC0 | M2 | 1 | 左 | 10 |

ULPI 的 12 个脚在这个封装上几乎没有选择：DIR 还可以用 PC2_C（M4），NXT 还可以用 PC3_C（M5），但 `_C` 脚限流 1 mA，不选。这组引脚与 ST H743I-EVAL（UM2198 Table 68）完全相同。[图]

**调试串口**：USART1_TX = PA9（E15，0 圈，AF7）、USART1_RX = PA10（D15，0 圈，AF7）。[核+图]

**辅助脚（示例，可换）**：摄像头 XCLK = PD13、摄像头 SCCB（I2C）= PD12 / PB9（I2C4，AF4 / AF6）、摄像头 PWDN = PD7、摄像头 RESET = PE2、ULPI 的 PHY 复位 = PE3、ETH 复位 = PC13、ETH 中断 = PI8。共 8 个。

### 4.2 占用

| 项 | 脚数 |
|---|---|
| SDRAM | 57 |
| QSPI | 6 |
| 必需脚 | 8 |
| DCMI（12 位） | 15 |
| ULPI | 12 |
| 以太网 | 9 |
| **IO 合计** | **107 / 140 = 76.4%** |
| 含辅助脚（+8） | 115 / 140 = 82.1% |
| 按球（信号球） | 110 / 201 = 54.7% |
| 按球（含电源地球） | 168 / 201 = 83.6% |

DCMI 降到 8 位（11 脚）则 IO 合计 103（73.6%）；10 位 105（75.0%）。[推]

## 5. 套 C：ST 评估板同款子集（以太网 + SD 卡带 1.8 V 转换 + ULPI + CAN FD）

**组成**：以太网 RMII 9 脚、SDMMC1 6 脚 + 电平转换控制 4 脚、ULPI 12 脚、FDCAN1 2 脚、调试串口 2 脚（USART1 PA9/PA10）。这四类外设在 ST 的 STM32H743I-EVAL（MB1246）上都有，引脚分配与评估板一致（QSPI 和调试串口除外），原理图可以直接按网络名照着画（#4 的结论）。

### 5.1 逐脚分配

以太网：第 2.4 节。ULPI：第 4.1 节。FDCAN1：PA11 / PA12，同套 A。

**SDMMC1**（10 脚）[核+图]

| 信号 | 端口 | 球 | 圈 | 边 | AF |
|---|---|---|---|---|---|
| SDMMC1_CK | PC12 | A12 | 0 | 上 | 12 |
| SDMMC1_CMD | PD2 | D12 | 3 | 上/右 | 12 |
| SDMMC1_D0 | PC8 | G14 | 1 | 右 | 12 |
| SDMMC1_D1 | PC9 | F14 | 1 | 右 | 12 |
| SDMMC1_D2 | PC10 | B14 | 1 | 上/右 | 12 |
| SDMMC1_D3 | PC11 | B13 | 1 | 上 | 12 |
| SDMMC1_CKIN | PB8 | A5 | 0 | 上 | 7 |
| SDMMC1_CDIR | PB9 | B4 | 1 | 上 | 7 |
| SDMMC1_D0DIR | PC6 | H15 | 0 | 右 | 8 |
| SDMMC1_D123DIR | PC7 | G15 | 0 | 右 | 8 |

后四个是外接电平转换器的方向 / 时钟回环信号，EVAL 的 IP4856CX25 就是这样接的（UM2198 Table 68 里 PB8 = SDIO_1_CKIN、PB9 = SDIO_1_CDIR、PC6 = D0DIR、PC7 = D123DIR）。[图]

**辅助脚（示例，可换）**：ETH 复位 = PC13、ETH 中断 = PI8、SD 卡检测 = PE3、SD 卡电源使能 = PD7、ULPI 的 PHY 复位 = PE2、CAN STB = PG14。共 6 个。EVAL 上 CAN 的 STB 用 PD3、SD 卡检测经 IO 扩展器。

### 5.2 占用

| 项 | 脚数 |
|---|---|
| SDRAM | 57 |
| QSPI | 6 |
| 必需脚 | 8 |
| 以太网 | 9 |
| SDMMC1（含 4 根转换器控制） | 10 |
| ULPI | 12 |
| FDCAN1 | 2 |
| **IO 合计** | **104 / 140 = 74.3%** |
| 含辅助脚（+6） | 110 / 140 = 78.6% |
| 按球（信号球） | 107 / 201 = 53.2% |
| 按球（含电源地球） | 165 / 201 = 82.1% |

## 6. 每个外设的大厂器件候选

器件数据来源说明：规格书页码是 PDF 页码。**Microchip 和 Nexperia 官网对命令行下载一律返回 403，LAN8742A、USB3320C、IP4856CX25 的规格书这次一份都没拿到**；这几颗的数据来自 ST 原理图和 ST 手册里的接法，标"未核"。TI、Infineon 的规格书是从官网读的，ISSI 的是第三方镜像（issi.com 有机器人验证）。我用子代理读了这些规格书，自己抽查了 DP83825I 的绝对最大值表和"integrated LDO"一句，与转述一致，其余是转述。

### 6.1 以太网 RMII PHY（三套都有）

| 器件 | 封装 / 间距 | 供电轨 | 备注 | 状态 |
|---|---|---|---|---|
| **Microchip LAN8742A-CZ-TR** | QFN-24，约 4 × 4 mm（脚距未核，记忆里是 0.5 mm） | VDD1A、VDD2A、VDDIO 接 3.3 V；VDDCR 只接 470 pF 加 1 µF，没有外部核心电压（ST 原理图的接法）；规格书里 VDD 各脚的范围未核 | ST 的 NUCLEO-H743ZI、H743I-EVAL、H747I-DISCO 三块官方板都用它（原理图文字层核对）；25 MHz 晶振，nINT / REFCLKO 脚输出 50 MHz 给 PA1；RXER 脚 10 kΩ 下拉、不接 MCU | 未核 |
| TI DP83825I | WQFN-24（RMQ），3.0 × 3.0 mm，焊盘间距 0.4 / 0.5 mm 混合（读图，p.96） | VDDA3V3 3.0–3.6 V（典型 3.3 V）；VDDIO 3.0–3.6 V 或 1.62–1.98 V；内部 LDO，不需要外部核心轨（p.5、p.18）；VDDIO 要先于 VDDA3V3 上电（p.8） | 25 MHz 晶振，Leader 模式从 pin 2 输出 50 MHz 给 MAC（p.3–4）；只有 RMII，没有 MII | Active（p.92，2026-01） |
| TI DP83826E/I | VQFN-32（RHB），5 × 5 mm | 同 DP83825I | MII + RMII；比 DP83825I 大，没有必要 | Active（p.106） |
| Microchip KSZ8081RNA | QFN-24，4 × 4 mm | 单 3.3 V，VDDIO 可选 1.8 / 2.5 / 3.3 V，内部 1.2 V | 全是搜索转述，没读规格书 | 未核 |

**额外电压轨：没有。** 两颗主选都是单 3.3 V + 内部稳压，VDDIO 要接 3.3 V 才能直连 H743 的 3.3 V 域。以太网只多一个 3.3 V 的模拟电源分支（PHY 的 VDDA 经磁珠滤波）和变压器 / RJ45 的中心抽头 3.3 V。[推]

### 6.2 USB 高速 ULPI PHY（套 B、套 C）

| 器件 | 封装 / 间距 | 供电轨 | 备注 | 状态 |
|---|---|---|---|---|
| **Microchip USB3320C-EZK** | QFN-32，5 × 5 mm（搜索转述；脚距未核，记忆里是 0.5 mm） | 在 ST 板上：VDD3.3 接 3.3 V；VDDIO 经 P-MOSFET 接 3.3 V（所以 ULPI 信号直连 H743 的 3.3 V 域）；两个 VDD1.8 脚（28、30）并在一起接板上的 +1V8 网络。**VDD1.8 到底是 PHY 内部稳压器的输出还是要外供，规格书没拿到，不能判断** | H743I-EVAL、H747I-DISCO 都用它；24 MHz 晶振（REFSEL[2:0] 全拉到 VDDIO）；RESETB 低有效；PHY 的 CLKOUT（60 MHz）经 33 Ω 送 MCU 的 PA5。USB3300、USB3340 的对比没查到 | 未核 |

**额外电压轨：可能有一路 1.8 V**（取决于 VDD1.8 是否要外供；ST 板上有一路 +1V8，LD1117S18TR 产生，同时给音频等其他电路用）。VBUS 5 V 要接 PHY 的 VBUS 脚并经 STMPS2151 之类的开关给 USB 口供电，所以还有一路 5 V 输入。[未核+推]

### 6.3 SD 卡（套 A、套 C 的 SDMMC1）

| 器件 | 封装 / 间距 | 供电轨 | 备注 | 状态 |
|---|---|---|---|---|
| NXP / Nexperia IP4856CX25/C（ST H743I-EVAL 用） | 25 球 WLCSP，球距 0.4 mm（搜索转述） | VCCA、VSUPPLY 接 3.3 V；片内带给卡侧的 LDO（VLDO 脚）；SEL 脚选 1.8 V / 2.9 V 卡侧电平；卡 VDD 在 EVAL 上是单独的 2.9 V（接法推断，规格书没拿到） | 方向控制脚 DIR_CMD、DIR_0、DIR_1_3 和 CLK_FB 对应 H743 的 CDIR、D0DIR、D123DIR、CKIN。**0.4 mm 球距 WLCSP 超出规格档 C（0.5 mm 及以下没有做过）**，在嘉立创六层板上做不了 | 论坛说 NRND 或停产，未核 |
| TI TXS02612RTW | QFN-24，4 × 4 mm，脚距 0.5 mm（p.20） | VCCA、VCCB0、VCCB1 各 1.1–3.6 V；无内置 LDO | SDIO 端口扩展器（一个主机口接两个 SD 口），时钟 ≤ 60 MHz，不到 UHS-I；没有 STM32 的方向控制接口 | Active（p.17，RTW） |
| TI TXS0206A | 20 球 DSBGA，1.96 × 1.56 mm，球距 0.4 mm（p.1） | VCCA、VCCB 各 1.1–3.6 V；无 LDO、无方向脚（自动方向，只有 EN） | 速率到不了 SDR50 / SDR104；同样是 0.4 mm | Active（p.25） |
| ST ST6G3244ME | 25 球 Flip Chip，球距 0.4 mm（搜索转述） | 主机侧 1.62–1.98 V、卡侧 3.0–5.0 V（搜索转述） | 主机侧不能接 H743 的 3.3 V；官网产品页已经没有 | 矛盾，未核 |

**结论**：能装进嘉立创六层工艺的转换器只有 TXS02612RTW（0.5 mm QFN），而它不是 UHS-I 级别的。所以套 C 里"带 1.8 V 转换"这件事在这块板上做不成 IP4856 同款；可选做法是：(a) 保留四根转换器控制脚，引到排针或测试点（占用数不变，功能没有）；(b) 去掉这四根脚，套 C 变成 100 / 140（71.4%）；(c) 用 TXS02612RTW 只做 3.3 V ↔ 1.8 V 的电平转换（不做 UHS-I）。这是 #9 要定的。[推]

**额外电压轨**：卡自身 3.3 V（EVAL 是单独的 2.9 V）；转换器的卡侧 1.8 V。套 A 没有转换器，SD 只用 3.3 V，没有额外轨。[推]

### 6.4 CAN FD（套 A、套 C）

| 器件 | 封装 / 间距 | 供电轨 | 备注 | 状态 |
|---|---|---|---|---|
| **Microchip MCP2562FD**（H743I-EVAL 用） | SOIC-8（1.27 mm）、3 × 3 DFN-8（0.65 mm）、PDIP-8（p.1、p.19、p.25） | VDD（pin 3）4.5–5.5 V；VIO（pin 5）1.8–5.5 V（p.9） | STBY（pin 8）悬空即待机，必须由 GPIO 拉低；数据速率 p.1 写到 8 Mbps，p.3 只保证到 5 Mbps；读到的是 2014 年的 Rev A | 官网 403，未核 |
| TI TCAN1042（后缀 H、G、V 的区别见规格书 p.1） | SOIC-8（D）1.27 mm；VSON-8（DRB）3 × 3 mm | VCC 4.5–5.5 V（p.8）；V 款的 VIO 3–5.5 V；**全系列没有 3.3 V 单电源款** | 非 V 款的 RXD 高电平驱动到 VCC（约 5 V，p.21）；H743 的 PA11 / PA12 的 I/O 类型是 FT_u（5 V 容忍，DS12110 Table 8、Table 9），所以可以直连 | 非 Q1 基础款是否可订没查到 |
| TI TCAN332 / TCAN337（同一份规格书） | SOIC-8（1.27 mm）、SOT-23-8（DCN，0.65 mm，读图） | VCC 3.0–3.6 V，**单 3.3 V**（p.5） | 非 G 款只到 1 Mbps，G 款到 5 Mbps；总线故障保护只有 ±14 V | Active（p.33–35） |
| TI ISO1042（隔离型） | SOIC-8 宽体 DWV 或 SOIC-16 DW，1.27 mm | VCC1 1.71–1.89 V 或 2.25–5.5 V；VCC2 4.5–5.5 V；VCC2 显性电流最大 73.4 mA（p.5、p.9） | 隔离 5000 VRMS；5 Mbps FD；没有模式脚 | Active（p.36） |
| TI SN6505B（隔离电源用推挽驱动） | SOT-23-6，0.95 mm | VCC 2.25–5.5 V；开关电流 1 A（p.4） | 参考电路：3.3 V 输入，变压器 1:2.2，两颗 MBR0520L，TPS76350 稳到 5 V，100 mA（p.22） | Active（p.36） |

**额外电压轨**：MCP2562FD 和 TCAN1042 要 5 V（4.5–5.5 V）；TCAN332/337 不要；ISO1042 的隔离侧要一路隔离的 5 V，要自己做一个推挽 + 变压器 + 整流 + LDO 的隔离电源——这条电源链是三套里"局部电路"最复杂的一块，对验证电源流程有价值，但变压器是定制件，这块板上放不放要定。[推]

### 6.5 LTDC（套 A）、DCMI（套 B）

**LCD（套 A）**：板上只需要一个 RGB 面板的 FPC 接口加背光升压；面板本身可以不焊。

| 器件 | 封装 | 关键参数 | 状态 / 备注 |
|---|---|---|---|
| **TI TPS61169**（背光升压，LED 驱动） | SC70-5（DCK），2.00 × 1.25 mm（p.1）；脚距没读到 | VIN 2.7–5.5 V；SW 绝对最大 40 V；OVP 36 / 37.5 / 39 V；开关频率 0.75 / 1.2 / 1.5 MHz；限流 1.2 / 1.8 / 2.4 A；CTRL 脚收 PWM 调光，5–100 kHz（p.1、p.4、p.5、p.9） | Active（p.18）。**不是 SOT-23-5** |
| TI TPS61165 | SOT-23-6（DBV）2.90 × 1.60 mm；WSON-6（DRV）2 × 2 mm | VIN 3–18 V；OVP 37 / 38 / 39 V；CTRL 支持 EasyScale 单线协议或 PWM（p.1、p.4、p.5） | Active（p.24）；VIN 下限 3 V，3.3 V 轨 −5% 时余量小 |
| Rocktech RK043FN48H-CT672B（ST 的 STM32F746G-DISCO / H735G-DK 同款 4.3 寸 480 × 272） | 40 脚 FPC（0.5 mm 脚距在规格书文字里没有，未核） | 逻辑 VDD 3.0 / 3.3 / 3.6 V；背光 VF 15 / 16 / 17 V、IF 典型 40 mA（640 mW）；24 位 RGB（RGB888 引脚，只接高位做 RGB565 是推断）+ DCLK、HSYNC、VSYNC、DE、DISP；电容触摸 FT5336：I2C + INT + RESET（p.4、p.6、p.11；非官网镜像，Version 1.0，2015） | ST 自己的板子上这块屏已经换过型：UM1907 Rev 8 表 15 换成 Kunjian HT043C、再换 GJX043A6-40DY、再换 GJX043A8-40DY；UM2488 Rev 10 表 19 换成 Rocktech RK043FN88H-CT661C，都"对固件有影响"——原型号可能不好买 |

背光是一串 LED，VF 约 16 V、40 mA（640 mW），两颗升压芯片的 OVP（≥ 36 V）都够；3.3 V 输入电流约 0.22 A（子代理按 85–90% 效率估的，推断）。面板的 RGB565 引脚对应：LCD_R3–R7 接面板 R3–R7，G2–G7 接 G2–G7，B3–B7 接 B3–B7，低位接地或复制高位（推断）。[核+推]

**摄像头（套 B）**：DCMI 是 8 / 10 / 12 / 14 位并行 + HSYNC + VSYNC + PIXCLK（PIXCLK 由传感器送给 MCU，是三条线里唯一反向的）。能找到的并行传感器几乎都已进入停产阶段，所以建议板上只放连接器和电源轨，传感器或模块外接。

| 器件 | 封装 | 供电轨 | 数据口 | 状态 / 备注 |
|---|---|---|---|---|
| OmniVision OV5640（5 MP；ST 没有官方板用它，常见 24 脚 FPC 模块） | 71 球 CSP，球距 0.5 mm（p.3、p.171）；**不能直接焊在这块板上** | AVDD 2.6 / 2.8 / 3.0 V；DVDD 1.425 / 1.5 / 1.575 V（有片内稳压器，p.3、p.166）；DOVDD 1.71 / 1.8 / 3.0 V；XVCLK 6–27 MHz | DVP 10 位并行（p.91） | 规格书是 acmesystems.it 上的 2011 年 v2.03 镜像，非官网；Toradex 2019 年的通知称它已 EOL（模块商的说法） |
| OmniVision OV2640 | 38 脚 CSP2 | AVDD 2.5 / 2.8 / 3.0 V；DVDD 1.24 / 1.3 / 1.36 V（片内稳压器，要 AVDD ≥ 2.65 V）；DOVDD 1.71 / 2.8 / 3.3 V | 8 / 10 位（p.1、p.6、p.10） | Espressif 托管的 2007 年 Preliminary v2.2，非官网；状态没查到 |
| onsemi MT9V034（752 × 480 全局快门） | 48 脚 CLCC 11.43 × 11.43 mm | **全部 3.3 V ± 0.3 V**（VDD、VAA、VAAPIX），不逼出额外轨；SYSCLK 13–27 MHz | 并行 10 位（p.2、p.4、p.5）；官网原件 Rev 9（2026-07） | 订货型号大多标 DISCONTINUED / Last Shipments，没有 Active（p.2、产品页） |
| onsemi AR0130CS（1.2 MP，卷帘快门） | PLCC48 11.43 mm 或 iLCC48 10 mm | VDD 1.7 / 1.8 / 1.95 V（外供，无片内稳压器）；VDD_IO 1.8 或 2.8 V 两档；VAA、VAA_PIX、VDD_PLL 2.5 / 2.8 / 3.1 V（p.32） | 12 位并行 | 多数型号 Obsolete，没有 Active |
| onsemi AR0144（1.2 MP，全局快门） | ODCSP-69 或 IBGA-63 | 只读到 EVB 手册的标称值：VDDIO 1.8 或 2.8 V、VDD 1.2 V、VAA 2.8 V（未读到完整规格书，数值未核） | 并行 12 位是搜索摘要，未核 | 型号多为 Lifetime / Last Shipments / Obsolete |

**额外电压轨**：OV5640 要 2.8 V（AVDD）、1.5 V（DVDD，可用片内稳压器，但 DOVDD 轨要为核心电流留 100 mA 以上）、1.8 V（DOVDD，也可 2.8 V）；OV2640 要 2.8 V + 1.3 V；MT9V034 只要 3.3 V；AR0130 要 1.8 V + 2.8 V。**24 脚 FPC 摄像头模块自己板上有没有 LDO，这块板要不要给 2.8 / 1.8 / 1.5 V，没查，未核。** 如果选 OV5640 型的接口，套 B 就多出三路低压轨。[核+推]

### 6.6 音频编解码器（SAI，没有放进三套；可加到套 A、套 C）

| 器件 | 封装 | 额外轨 | 状态 |
|---|---|---|---|
| Cirrus WM8994（ST H743I-EVAL、H747I-DISCO 用 WM8994ECS） | 72 球 W-CSP 4.5 × 4.0 mm，球距 0.5 mm（p.1、p.361）——**超出规格档 C 的范围** | AVDD2、CPVDD、LDO2VDD 必须外供 1.71–2.0 V（1.8 V，合计约 2–3 mA，p.12、p.31）；AVDD1 / DBVDD / SPKVDD 可用 3.3 V；内部 LDO 可生成 AVDD1 和 DCVDD | cirrus.com 标 Active |
| TI TLV320AIC3104 | VQFN-32（RHB），5 × 5 mm | DVDD 必须 1.525–1.95 V（约 2.5 mA，p.7、p.12）；AVDD、DRVDD 2.7–3.6 V；IOVDD 1.1–3.6 V | Active（p.95） |
| NXP SGTL5000 | QFN-20 3 × 3 mm（只有 I2C）、QFN-32 5 × 5 mm | VDDA、VDDIO 1.62–3.6 V；VDDD 新设计要外供 1.1–2.0 V（推荐 1.2 V；p.6、p.14） | NXP 页标 Active |
| Cirrus CS43L22 / CS42L51 | QFN-40（6 × 6 mm，0.5 mm）/ QFN-32 | VA、VD、+VHP 最大 2.63 V，3.3 V 不能直供，要 1.8 或 2.5 V（p.10、p.19，约 8 mA） | **官网标 Discontinued** |

SAI 只占 5 根线（MCLK、SCK、FS、SD_A、SD_B）加 2 根 I2C，对线序没有价值，价值在 1.8 V 轨（TLV320AIC3104 是最小的一路，SGTL5000 是 1.2 V 的低压轨）。[核]

### 6.7 可选的外挂 SRAM（FMC NOR/PSRAM 一侧）

| 器件 | 封装 / 间距 | 供电 | 地址线 | 备注 |
|---|---|---|---|---|
| **ISSI IS61WV102416BLL**（H743I-EVAL 用 IS61WV102416BLL-10MLI-TR，原理图文字层核对） | 读到的版本（Rev G，2014，第三方镜像）：48 球 mini BGA 9 × 11 mm，球距 0.75 mm；48 脚 TSOP Type I，0.5 mm | 单 VDD 2.4–3.6 V，没有 VDDQ | A0–A19（1M × 16），单个 CE、OE、WE、LB、UB | 新版 IS61/64WV102416FBLL 才有 6 × 8 mm BGA 和 54 脚 TSOP II；ISSI 官网读不到，状态未核 |
| ISSI IS61WV25616BLL（4 Mb） | 44 脚 TSOP Type II，0.8 mm；48 球 BGA 6 × 8 mm，0.75 mm | 单 VDD 2.4–3.6 V | A0–A17 | 状态未核 |
| Infineon CY62157EV30（8 Mb） | 44 脚 TSOP II，0.8 mm；48 球 VFBGA 6 × 8 mm，0.75 mm；48 脚 TSOP I | VCC 2.2–3.6 V（典型 3.0 V） | A0–A18 | 45 ns；官网标 "active and preferred"，"至少供货到 2033 年" |

SRAM 新增的 FMC 脚数：256K × 16 为 6 根（A13、A16、A17、NOE、NWE、NE）、512K × 16 为 7 根（再加 A18）、1M × 16 为 8 根（再加 A19）。没有 BGA 的选择：44 脚 TSOP II（IS61WV25616 或 CY62157）。**额外电压轨：没有**（单 3.3 V）。[推+核]

## 7. 额外电压轨汇总

除 MCU 自己的 3.3 V（VDD、VDDA、VDD33USB、VBAT 的几个滤波分支，#2）和 SDRAM / QSPI 的 3.3 V 之外，各外设带来的轨如下。电流量级取自规格书的典型值，用来判断这路轨是"小负载 LDO"还是"要开关电源"。电源树怎么搭是 #11 的事，这里只列需求。

| 套 | 额外轨 | 谁要 | 电流量级 | 说明 |
|---|---|---|---|---|
| **A** | 5 V（4.5–5.5 V） | CAN 收发器（MCP2562FD、TCAN1042） | 显性最大 70 mA（MCP2562FD IDD；TCAN1042 ICC 最大 70 mA） | 用 TCAN332/337 则不要 5 V，只要 3.3 V，但总线故障保护只有 ±14 V |
| A | 约 16–17 V（背光 LED 串，VF 15–17 V） | TPS61169 / TPS61165 升压 | 负载 40 mA，3.3 V 侧输入约 0.22 A（推断） | **一个真正的开关升压环路**（电感、二极管、反馈电阻、PWM 调光），是三套里唯一由外设逼出来的开关电源 |
| A | 隔离 5 V（可选） | ISO1042 + SN6505B + 变压器 + 肖特基 + LDO | VCC2 显性最大 73.4 mA（ISO1042 p.9）；SN6505 参考电路 100 mA | 隔离电源是一整条局部电路，但变压器是定制件；这块板放不放要定 |
| A | 3.3 V 模拟分支 | 以太网 PHY 的 VDDA | 小 | 磁珠 + 电容滤波 |
| **B** | 1.8 V | ULPI PHY（VDD1.8，是否要外供未核）；摄像头 DOVDD（OV5640 可选 1.8 V 或 2.8 V） | PHY 未核；摄像头 DOVDD 在用片内 DVDD 稳压器时要 60–110 mA | 摄像头的 1.8 V 和 PHY 的 1.8 V 可以合并成一路 |
| B | 2.8 V | 摄像头 AVDD（OV5640 2.6–3.0 V、OV2640 2.5–3.0 V） | 约 30–40 mA | 模拟轨，要低噪声 LDO |
| B | 1.5 V（或 1.3 V） | 摄像头 DVDD（OV5640 1.425–1.575 V，可用片内稳压器；OV2640 1.24–1.36 V） | 外供时约 98 mA（OV5640 表 8-3） | 用片内稳压器就不需要，但厂家在 2.8 V I/O 时推荐外供 |
| B | 5 V | USB 的 VBUS（PHY 的 VBUS 脚 + 对外供电开关 STMPS2151） | 取决于负载 | ST 板用 STMPS2151STR |
| **C** | 1.8 V | SD 卡电平转换的卡侧（UHS-I）；ULPI PHY 的 VDD1.8（未核） | 小 | IP4856 在这块板上用不了（0.4 mm WLCSP），见 6.3 |
| C | 2.9 V（ST EVAL 的做法） | SD 卡 VDD，IP4856 片内 LDO 的参考 | 小 | 不用 UHS-I 的话 3.3 V 就够 |
| C | 5 V | CAN 收发器；USB VBUS | 同上 | |

- **三套里电源最丰富的是套 B**（1.8 V、2.8 V、1.5 V 三路低压轨，加 5 V；DVDD 的 98 mA 是三套里最大的低压负载），但摄像头那三路轨在没有传感器的板上只是空载 LDO，而且并行传感器几乎都进入停产阶段（第 6.5 节）。套 A 的亮点是那个升压环路（真实的开关环路，可以接一个假负载电阻测）。套 C 的低压轨最少。
- 所有外设轨的电流都在几十毫安量级，只有背光的输入侧（0.22 A）和摄像头 DVDD（约 0.1 A）需要稍大一点的器件；没有一路逼出大电流降压。
- 以太网、ULPI、SD、DCMI、LTDC 的 IO 电压都可以是 3.3 V（H743 的 IO 只有一个 VDD，1.62–3.6 V），所以没有"MCU 一侧要 1.8 V"的情况。[核]（#2：L 组只有一个 VDD）


## 8. 引脚在封装上的位置，和 SDRAM 抢不抢出线通道

"圈"按 #6 的定义：0 圈是最外一圈（A、R 两行和第 1、15 列），往里依次到 3 圈（D、M 两行和第 4、12 列）；0–1 圈从顶层直接出线，2–3 圈要打孔、从 L4 出线（#6 的结论，下限两层信号层，保守三层）。边按上视图（A 行在上、1 列在左）。全部由脚本按球号算。[推]

### 8.1 数字

| 项 | 容量（140 个 GPIO 球） | SDRAM 57 | 套 A 全部已用 | 套 B 全部已用 | 套 C 全部已用 |
|---|---|---|---|---|---|
| 0 圈 | 50 | 11 | 38 | 34 | 35 |
| 1 圈 | 46 | 20 | 37 | 39 | 37 |
| 2 圈 | 26 | 17 | 21 | 21 | 20 |
| 3 圈 | 18 | 9 | 12 | 13 | 12 |
| 内两圈合计 | 44 | 26 | 33 | 34 | 32 |
| 下边 | 41 | 18 | 33 | 32 | 30 |
| 左边 | 29 | 12 | 23 | 27 | 26 |
| 右边 | 32 | 18 | 29 | 23 | 26 |
| 上边 | 38 | 9 | 23 | 25 | 22 |

"全部已用"= SDRAM + QSPI + 调试串口 + 外设 + SWD / HSE / LSE。拐角的球按其所属的第一条边算。

- 内两圈的 44 个 GPIO 球，三套用掉 32–34 个（73–77%），其中 SDRAM 占 26 个。套里新增的内圈信号只有 6–8 个：套 A 是 PC1、PC4、PA4、PF8（2 圈）和 PD3、PD2、PB2（3 圈）；套 B 是 PC1、PC4、PA4、PF8 和 PD3、PD2、PI11、PH4；套 C 是 PC1、PC4、PF8 和 PD2、PI11、PH4。也就是说外设几乎都落在外两圈，对"内圈要打孔"这件事增量不大，打孔压力主要来自 SDRAM 本身。
- 按边：没有一套轻松。最满的边是套 A 的右边（29 / 32）、套 B 的左边（27 / 29）、套 C 的左边（26 / 29）；上边三套都最空（22–25 / 38），SDRAM 在上边只有 9 个信号。

### 8.2 和 SDRAM 抢通道的热点

1. **左边 QSPI 簇和 SDRAM 地址线**：K1、K2、L1、L2、L3（QSPI）紧挨着 SDRAM 的 A0–A5（E2、H3、H2、J2、J3、K3）。左边 29 个球在套 B、C 里用掉 26–27 个，几乎满；套 A 因为 LTDC_DE 占了 PF10，QSPI_CLK 让到下边的 PB2。这是三套里风险最高的区域，QSPI 线要从 PF 簇往左出还是往里出，要和 SDRAM 地址线一起排。[推]
2. **左边 3 圈的一列**：E4（PI11 = ULPI_DIR，套 B、C）、F4（SDCKE0）、G4（SDNE0）、H4（PH4 = ULPI_NXT，套 B、C）、J4（SDNWE）是第 4 列里连续的五个球，全部有信号，要全部打孔往外引。套 A 没有 ULPI，E4、H4 空着。[推]
3. **下边**：以太网 RX 侧（PA7、PC4、PC5、PA2）加 ULPI 的 D0–D6（R2、R5、R4、R12、R13、P12、P13）和 PA5，与 SDRAM 的 D4–D12（R8–R11、P8–P11）、A6–A9、SDNRAS 同在下边。下边有 18 个 SDRAM 信号，套里再加 12–15 个，合计 30–33 / 41。SDRAM 若放在 MCU 的下边或右边，这两边会最挤。[推]
4. **套 A 的 LTDC 在右边和下边各有 11 和 15 个脚**（LTDC 在这个封装上被迫散在四条边，因为 FMC 占了 PH、PI 口），与 SDRAM 的右边 18 和下边 18 重合最多；套 B、C 的外设更均匀。[推]
5. **以太网 TX 侧在上边相邻的 A8、B8、B9**，不与 SDRAM 抢（上边只有 SDRAM 的 9 个）；但 RX 侧在下边，PHY 的位置要同时照顾上边和下边，倾向放在 MCU 的上、下之间的那一侧（左或右）。[推]
6. 套里的 SD 卡、DCMI 引脚大部分在上边和右上角（PC8–PC12、PD2、PD3、PB8、PB9 等），离 SDRAM 的主要出线方向远，是三套里和 SDRAM 最不冲突的部分。[推]

结论：**三套在"出线通道"上的风险差不多，都集中在左边 QSPI 簇和下边；套 A 因为 LTDC 的脚散得最开，整体最难排；套 C 最均匀。** 这些是定性判断，真正的通道容量要等 SDRAM 放在哪一边之后，再按 #6 的出线容量算。

## 9. 没有放进三套的其他外设

| 外设 | 脚数 | 引脚（球号、AF，DB 与 DS Table 9 核过成员） | 可行性 | 说明 |
|---|---|---|---|---|
| SAI 音频编解码器 | 5（+ I2C 2） | SAI1_MCLK_A = PE2（A2，AF6）或 PG7（J14，AF6）、SD_B = PE3（A1，AF6）、FS_A = PE4（B1，AF6）、SCK_A = PE5（B2，AF6）、SD_A = PE6（B3，AF6） | 与套 A、套 C 兼容（求解器：套 A + SAI1、套 C + SAI1 都有解）；与套 B 的 DCMI 冲突（PE4、PE6 是 DCMI 的 D4、D7） | 脚少，但要 1.8 V 之类额外电压轨（第 6.6、7 节） |
| 外挂 SRAM（FMC NOR/PSRAM 一侧，与 SDRAM 共用 D0–D15、A0–A12、NBL0/1） | 8 个新增（A13 = PG3、A16 = PD11、A17 = PD12、A18 = PD13、A19 = PE3、NOE = PD4、NWE = PD5、NE3 = PG10） | AF12 | 套 B、套 C 兼容；套 A 要把以太网 TXD1 改回 PG14、SRAM 的片选改用 NE4（PG12）才行 | 给 D0–D15 和 A0–A12 加第三个负载（SDRAM、SRAM 两个终点的分支），对线序拓扑有价值。ST 的 H743I-EVAL 就这么接（SRAM 是 ISSI IS61WV102416BLL，MB1246 原理图文字里有这个料号）。 |
| SDMMC2（4 位） | 6 | CK = PD6（B11）、CMD = PD7（A11）、D0 = PB14（R14）、D1 = PB15（R15）、D2 = PB3（A10，AF9）、D3 = PB4（A9，AF9），CK 另可 PC1（与 MDC 冲突）、CMD 另可 PA0 | 可行（ETH + ULPI + DCMI 8 位 + SD2 有解）；但 D2、D3 占用 PB3、PB4（复位后是 JTDO、NJTRST） | SDMMC2 没有 CKIN / CDIR / DxDIR 引脚，不能接 EVAL 那种带方向控制的转换器 |
| eMMC（SDMMC2 8 位） | 10 | 在 SDMMC2 上加 D4 = PB8、D5 = PB9、D6 = PC6、D7 = PC7 | ETH + ULPI + 8 位 SDMMC2 有解 | eMMC 常见封装是 BGA153 / 169，球距 0.5 mm，规格档 C 没覆盖；不建议 |
| LTDC RGB888 | 28 | 在 RGB565 上加 R0 = PG13、R1 = PA2、R2 = PA1 或 PC10、G0 = PB1 或 PE5、G1 = PE6、B0 = PE4 或 PG14、B1 = PG12 或 PA10、B2 = PA3 等 | 与以太网冲突（R1 的唯一脚 PA2 是 ETH_MDIO）；LCD565 + RGB888 + SD1 + CAN1 有解 | 并行线从 20 条加到 28 条，但面板和以太网二选一 |
| FDCAN2 | 2 | PB12 / PB13（AF9）或 PB5 / PB6（AF9） | 与 ULPI 冲突（PB12、PB13、PB5 是 ULPI 的 D5、D6、D7 的唯一脚） | 不选 |
| USB OTG FS（无外部 PHY） | 2 | PA11 / PA12（AF10） | 与 FDCAN1 冲突 | 脚太少，不选 |
| DFSDM、SPDIFRX、HRTIM、ADC / DAC 模拟脚 | 各 1–6 | — | 未逐个排 | 脚少且不并行；若要凑数，空闲的 PA0、PC13、PI8、PE2 等够用 |

H743 没有 OctoSPI / FMC 之外的并行 NOR 接口可选，所以 SDRAM + QSPI 之外的并行总线就只有 LTDC、DCMI、ULPI 三条。[核]（引脚库里没有 OCTOSPI 信号）

### 9.1 外设两两是否兼容（SDRAM + QSPI + 调试串口 + 必需脚都已占住）

`conflicts.py` 的结果：

| 不兼容的一对 | 原因（该信号在此封装上只剩一个脚） |
|---|---|
| LTDC RGB565 + ULPI | PA3：ULPI_D0 与 LCD_B5；PB0：ULPI_D1 与 LCD_R3 |
| LTDC RGB565 + DCMI | PA6：LCD_G2 与 DCMI_PIXCLK；PA4：LCD_VSYNC 与 DCMI_HSYNC |
| LTDC RGB565 + SDMMC1 的转换器控制脚 | PB8：CKIN 与 LCD_B6；PB9：CDIR 与 LCD_B7；PC6：D0DIR 与 LCD_HSYNC |
| LTDC RGB888 + 以太网 | PA2：ETH_MDIO 与 LCD_R1 |
| ULPI + FDCAN2 | PB12、PB13（FDCAN2）与 ULPI_D5、D6 |

其余两两组合（以太网、SDMMC1、SDMMC2、ULPI、LTDC、DCMI、SAI1、FDCAN1）都有解。LTDC 和 DCMI 互斥，所以"最多并行线"的组合只能二选一：套 A（LTDC）或套 B（DCMI + ULPI）。

## 10. 已验证和未验证

### 10.1 已验证（我亲自读到）

1. 引脚库与 KiCad 符号：201 个球的球号与引脚名 0 处不一致。
2. 引脚库与 DS12110 Rev 11 Table 9：138 个 GPIO 的 UFBGA176+25 球号全部一致；三套用到的 301 个（引脚、信号）组合，信号名都在 Table 9 该引脚的备选功能里。（`check_ds.py`）
3. AF 编号：DS12110 Table 10 p.89–99（渲染成图逐页看）里，三套用到的每个引脚的 AF 列与库一致；SDRAM 的 FMC 引脚全是 AF12。
4. SDRAM 的信号数是 57（含 A12），不是 58。QSPI 的 16 个备选脚在库里都有，没有一个是 SDRAM 的脚。
5. 三套的每个信号分到不同的球，没有占 SDRAM、SWD、HSE、LSE、QSPI、调试串口的脚（求解器断言 + 脚本复核）。
6. 外设两两冲突表（`conflicts.py`）和各组合的可行性（`solve.py`）。
7. ST H743I-EVAL 的实际引脚（UM2198 Rev 5，Table 68，p.71–75，渲染图）：RMII 九根、SDIO1 十根（含四根转换器控制）、ULPI 十二根、FDCAN1 的 PA11 / PA12、USART1 的 PB14 / PB15、QSPI_CLK 在 PB2、MCO1 在 PA8、CAN STB 在 PD3。
8. ST 官方板用了哪些器件（原理图 PDF 文字层里出现的料号）：MB1246（H743I-EVAL）：LAN8742A-CZ-TR（以太网）、USB3320C-EZK（ULPI）、IP4856CX25/C（SD 电平转换）、WM8994（音频）、MCP2562FD（CAN FD）、IS61WV102416BLL-10MLI-TR（SRAM）、IS42S32800J-6BLI、STMPS2151STR、LD3985M33R、LD1117S18TR；MB1248（H747I-DISCO）：LAN8742A-CZ-TR、USB3320C-EZK、WM8994ECS、同样的 STMPS2151STR，另有 8 位 DCMI 摄像头接口（PIXCLK = PA6、HSYNC = PA4、VSYNC = PB7，从文字层看到；位号对应有乱码，只当旁证）；MB1364（NUCLEO-H743ZI）：LAN8742A-CZ-TR。
9. 勘误 ES0392：只有 PC2_C / PC3_C 的封装上以太网 MII 不能用（§2.2.27），`Pxy_C` 脚限流（§2.2.26）；其余与 FMC、LTDC、DCMI、SDMMC、OTG_HS 有关的条目是软件层面的，没有哪一条要求改引脚。
10. PC13、PC14、PC15、PI8 的输出电压特性单列一张表，按 3 mA 标定（DS12110 Table 52）。
11. 引脚库不含 OCTOSPI 信号。

12. PA11、PA12（FDCAN1）的 I/O 类型是 FT_u，FT 即 5 V 容忍（DS12110 Table 8、Table 9）。
13. 器件规格书里我亲自抽查过的：DP83825I 的绝对最大值表（VDDIO 1.8 V 档 2.1 V）和"integrated LDO"一句；TPS61169 是 SC70-5、VIN 2.7–5.5 V；TLV320AIC3104 的 DVDD 1.525–1.95 V；WM8994 有 AVDD2 / CPVDD 脚；Rocktech 面板规格书的型号。其余器件数据是子代理读规格书后的转述，页码是它们给的，我没有逐条回查（所以第 6、7 节的器件参数整体算"子代理转述，已抽查"，不算我逐条核对）。

### 10.2 未验证

**引脚方面**

1. H743 的 SDRAM 脚数 58 与 57：本报告更正为 57，需要用户核对 #7 的口径。
2. PC14 / PC15 / PH0 / PH1 的球号 E1 / F1 / G1 / H1：Table 9 里这四行拆成多行，没有用脚本比；球号来自引脚库和 KiCad 符号（互相一致）和前票 #2。
3. AF 号我是逐页看 Table 10 的图，不是脚本比对；人眼看漏的可能性存在，但 CubeMX 数据库与图一致，两个来源互相印证。
4. PC13 / PI8 的"3 MHz"开关速度限制：规格书文本里没找到，只核到 Table 52 按 3 mA 标定。
5. UM2198 里 EVAL 的 QSPI 引脚（p.73）没看，只看了 p.71、72、74。
6. 辅助脚（PHY 复位、SD 卡检测、背光 PWM 等）只是从空闲脚里挑的示例，没有检查它们与布局的关系；PB3 / PB4 / PA15（复位后是 JTAG 功能）已排在最后。
7. 求解器的目标函数（圈数之和最小 + QSPI 外框最小）是我定的；它没有考虑 PHY、连接器、SDRAM 的实际位置。
8. 外挂 SRAM、SAI、SDMMC2、eMMC、RGB888 只用求解器检查了"能不能排下"，没有逐脚列表和 DS 成员校验。
9. 没有读 RM0433；没查 FMC 的 NOR/PSRAM 与 SDRAM 共总线时的时序限制和 NBL / NE 与 SRAM 的 LB / UB / CE 的对应关系（这是我对 FMC 的记忆）。
10. LTDC 引脚 AF 里的 PA8（B3，AF13）、PA10（B4，AF12）等看起来不规则的复用，已在 Table 10 的图上核到；但 LTDC 本身在这个封装上要不要特殊处理（像素时钟的 IO 速度档）没查。

**器件方面**

11. Microchip LAN8742A、USB3320C、KSZ8081RNA、MCP2562FD 的规格书：官网 403，LAN8742A 和 USB3320C 一份都没拿到（只有 ST 原理图上的接法），MCP2562FD 读到的是 2014 年的 Rev A（`ww1.microchip.com/downloads/en/DeviceDoc/20005284A.pdf`）。VDD 范围、VDDIO 范围、USB3320C 的 VDD1.8 是否外供、REFSEL 频率表、封装脚距、生命周期都没核。
12. NXP / Nexperia IP4856CX25/C 的规格书、封装尺寸、生命周期：没拿到；"0.4 mm 球距 WLCSP 25 球"和"NRND / 停产"是搜索转述。ST6G3244ME 全部是搜索转述，且论坛对生命周期说法矛盾。
13. TI DP83825I、DP83826、TXS0206A、TXS02612、TCAN1042、TCAN332/337、ISO1042、SN6505B、TPS61169、TPS61165、TLV320AIC3104 的规格书是官网原件，数据是子代理转述（已抽查几处）。DP83825I 的焊盘间距 0.4 / 0.5 mm 和 TCAN33x DCN 的 0.65 mm 是读渲染图得到的。TCAN1042 非 Q1 基础款是否可订没查到。
14. ISSI 的 IS61WV102416BLL（Rev G，2014）和 IS61WV25616BLL（Rev H，2012）是第三方镜像（issi.com 有机器人验证），生命周期没查到；新版 IS61/64WV102416FBLL 与 BLL 是否引脚兼容没核。
15. OV5640（acmesystems.it 镜像，v2.03，2011）、OV2640（Espressif 托管，v2.2 Preliminary，2007）都不是官网版本；官网状态没查到；"OV5640 已 EOL"只是 Toradex 的通知。onsemi AR0144 的完整规格书没拿到。
16. Cirrus WM8994 的 DBVDD1–3 是后继型号写法的记忆；CS43L22 规格书页页带 "Confidential Draft 3/4/10" 水印；SGTL5000 的 32 脚 5 × 5 mm 来自 NXP 产品页。
17. Rocktech RK043FN48H 的规格书是 wiki.kewl.org 上的非官网镜像（Version 1.0，2015）；0.5 mm FPC 脚距没在文字里；时序表是图。
18. 摄像头 FPC 模块的板级电源要求没查。
19. 背光升压的输入电流（约 0.22 A）是子代理按 85–90% 效率估的。
20. 没有调用 kicad-happy 的 `datasheets` skill：它装在 `~/.claude/plugins/marketplaces/kicad-happy/skills/datasheets`，但没有出现在这个会话的技能列表里，而且它按"项目里 `datasheets/` 目录的 PDF + 缓存"工作，这张调研票没有工程。规格书是用 `pdftotext` 加渲染页面图读的。

## 11. 依据和链接

- 规格书：[DS12110 Rev 11](https://www.st.com/resource/en/datasheet/stm32h743ii.pdf)（Table 9 p.64–88、Table 10 p.89–99、Table 52 p.140；本次 2026-11-16 从 ST 官网重新下载）。
- 勘误：[ES0392](https://www.st.com/resource/en/errata_sheet/es0392-stm32h742xig-stm32h743xig-stm32h750xb-stm32h753xi-device-errata-stmicroelectronics.pdf)。
- 引脚数据库：GitHub `STMicroelectronics/STM32_open_pin_data`（`mcu/STM32H743IIKx.xml`、`mcu/IP/GPIO-STM32H747_gpio_v1_0_Modes.xml`，提交 7d1f151，"Subset of official release STM32CubeMX 6.18.0"，2026-06-29）。
- ST 官方板：[UM2198](https://www.st.com/resource/en/user_manual/dm00385071-evaluation-boards-with-stm32h743xi-and-stm32h753xi-mcus-stmicroelectronics.pdf)（Table 68）、[MB1246 H743 原理图](https://www.st.com/resource/en/schematic_pack/mb1246-h743-e03_schematic.pdf)、[MB1248 H747I-DISCO 原理图](https://www.st.com/resource/en/schematic_pack/mb1248-h747i-d04-schematic.pdf)、[MB1364 NUCLEO-H743ZI 原理图](https://www.st.com/resource/en/schematic_pack/mb1364-h743zi-c01_schematic.pdf)。
- 前面的调研：`research/h7-ufbga176-mcu`（#2）、`research/bga-fanout-practice`（#6）、`research/st-reference-schematics`（#4）、`research/qspi-flash`（#7）、`research/sdram-32bit-bga`（#3）。
- 脚本：`docs/research/h7-peripheral-pinmux/`（`pindb.py` 建库、`base.py` 数 SDRAM 和核 QSPI 表、`solve.py` 求解器、`combos.py` 三套方案、`conflicts.py` 两两冲突、`check_ds.py` 对规格书文字、`report_tables.py` 出表、`q.py` 查信号）。输入是下载到临时目录的 ST 数据，脚本用 `python -I` 运行；PDF 和数据不提交。
- 器件规格书（读到的版本；TI、onsemi、Cirrus、Infineon 是官网件）：TI [TPS61169](https://www.ti.com/lit/ds/symlink/tps61169.pdf)（SNVSA40B）、[TPS61165](https://www.ti.com/lit/ds/symlink/tps61165.pdf)（SLVS790E）、[TLV320AIC3104](https://www.ti.com/lit/ds/symlink/tlv320aic3104.pdf)（SLAS510G）、DP83825I（SNLS638C）、DP83826（SNLS647I）、TXS0206A（SCES833B）、TXS02612（SCES682C）、TCAN1042H（SLLSES7D）、TCAN33x（SLLSEQ7F）、ISO1042（SLLSF09F）、SN6505A/B（SLLSEP9I）；[onsemi MT9V034](https://www.onsemi.com/pdf/datasheet/mt9v034-d.pdf)（Rev 9）；[Cirrus WM8994](https://statics.cirrus.com/pubs/proDatasheet/WM8994_Rev4.6.pdf)（Rev 4.6）；[Infineon CY62157EV30](https://www.infineon.com/assets/row/public/documents/10/49/infineon-cy62157ev30-mobl-8-mbit-512-k-16-static-ram-datasheet-en.pdf)（Rev *S）；[Microchip MCP2562FD](https://ww1.microchip.com/downloads/en/DeviceDoc/20005284A.pdf)（Rev A）。
- ST 用户手册（子代理从 ST 取得）：UM1907 Rev 8（F746G-DISCO，表 15 的面板换型记录）、UM2488 Rev 10（表 19）。

