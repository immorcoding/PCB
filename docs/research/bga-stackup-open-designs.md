# 开源 / 公开资料的 BGA + 并口存储板：层数与叠层调研

调研日期 2026-11-22。目的：六层板（L1 信号 / L2 GND / L3 电源面 / L4 信号 / L5 GND / L6 信号，只用通孔）上，STM32H743 UFBGA176+25（0.65 mm）加 90 球 0.8 mm 的 32 位 SDRAM（57 根 FMC 线）扇出不完，用户想加一层信号层。这里查别人公开的设计怎么排层。

标记：**已核实** = 读了一手来源（板文件、厂商文档、设计者自己的文章）；**未核实** = 推断或二手来源。找不到的写"未找到"。

方法说明：KiCad 板文件（OrangeCrab、ULX3S、Logicbone、ButterStick、Antmicro）从 GitHub 取原始 `.kicad_pcb`（2026-11-22 的 HEAD），用脚本数了每层走线条数和长度、过孔类型、铜皮（zone）所在层和网络、BGA 范围内的电容在哪一面。"存储器走线分层"的统计方法：取存储芯片所有焊盘上的网络（去掉 GND 和 3V3），统计这些网络的走线长度在各层的分布；这个集合里含有存储器自己的电源网络（如 VTT、VREF），所以数值是近似，用来看"哪几层承载了存储总线"，不是精确的线长。所有统计脚本不在仓库里（临时文件）。

## 1. 对比表

| # | 设计 | MCU / FPGA 封装与间距 | 存储器 | 层数 | 叠层顺序（板文件里的顺序） | 信号层数 | 存储总线所在层 | 电源怎么分 | 过孔 | 厂家 | 核实 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Antmicro STM32H7 HDMI board（STM32H747XIH6） | TFBGA 289 焊盘位（240+25），0.8 mm | 144 针 SODIMM SDRAM（板外），另有 eMMC、NOR | 8 | F.Cu 信号 / In1 GND / In2 信号(+GND 铜皮) / In3 GND / In4 电源铜皮 / In5 信号(+铜皮) / In6 GND / B.Cu 信号 | 4（F、In2、In5、B） | SODIMM 网络在 F、B、In5；MCU 网络四层都有，In2 最多 | In4 一层放多块电源铜皮（+5V、+3V3、DVDD 等，只有 5 条走线）；外层和 In2、In5 也有电源/GND 铜皮 | 全通孔，0.45/0.2 mm 1308 个，0.35/0.2 mm 382 个，0.6/0.2 mm 13 个，无盲埋孔 | 未找到 | 层数、叠层顺序、过孔、电容位置已核实 |
| 2 | ButterStick r1.0（ECP5-85 + 2 片 DDR3L） | caBGA381，0.8 mm（DDR3 为 96 球，0.8 mm） | 2 × MT41K64M16（DDR3L） | 8 | F.Cu 信号 / In1 GND / In2 信号 / In3 电源 / In4 电源 / In5 信号 / In6 GND / B.Cu 信号 | 4（F、In2、In5、B） | 两片 DDR3 都在 F、In2、In5、B 四层；In3、In4 只有零星走线 | In3、In4 两层电源面都按网络分割（In3：3V3、2V5、VDDA、1.35V DRAM 等；In4：VDDTX、VDDRX、1V2 等）；外层和 B.Cu 另有铜皮 | 全通孔，0.45/0.2 mm 629 个，0.4/0.2 mm 534 个 | 叠层里写了介质厚度（板文件 stackup），厂家未找到 | 已核实 |
| 3 | Logicbone（ECP5UM-85 + 2 片 DDR3） | caBGA381，0.8 mm；DDR3 为 78 球 FBGA，0.8 mm | 2 × DDR3 | 8（Gerber 文件名可数出 8 层铜） | F.Cu 信号 / Gnd1 / Sig1 信号 / Pwr1 电源 / Gnd2 / Sig2 信号 / Gnd3 / B.Cu 信号 | 4（F、Sig1、Sig2、B） | 两片 DDR3 都在 F、Sig1、Sig2、B 四层 | Pwr1 一层放全部电源铜皮（VCORE、VDDR、VTT、1V8、3V3、ETH 1V2 等） | 全通孔，0.5/0.2 mm 658 个，无盲埋孔 | 未找到 | 已核实 |
| 4 | OrangeCrab r0.2.1（ECP5-25/85 + 1 片 DDR3L x16） | csfBGA285，**0.5 mm**（板文件里的封装 0.5 mm 步距）；DDR3L 为 96 球，0.8 mm | 1 × MT41K64M16 | 6 | F.Cu 信号 / In1 GND / In2 信号 / In3 混合（电源铜皮，少量走线）/ In4 GND / B.Cu 信号 | 3 + In3 混合 | F、In2、B 三层；In3 仅少量（电源类网络） | In3 放全部电源铜皮（3.3V、1.1V、2.5V、1.35V、VBATT、VSYS、RAM_VDD、RAM_VDDQ、VREF 等）；开关电源在外层铜皮 | 全通孔，0.3/0.15 mm 273 个，0.28/0.15 mm 168 个 | 未找到（作者说叠层待厂家确认） | 已核实 |
| 5 | ULX3S（ECP5-85 + 16 位 SDRAM） | caBGA381，0.8 mm（封装名 BGA-381_pitch0.8mm）；SDRAM 是 TSOP，不是 BGA | MT48LC16M16 / MT48LC32M16，16 位 | 4 | F.Cu / In1 / In2 / B.Cu（板文件 stackup：四层铜，每层介质 0.48 mm） | 4 层都有走线，但 SDRAM 几乎全在外层 | SDRAM 网络：F.Cu 840 mm，B.Cu 93 mm，内层无 | In1 放电源铜皮（+3V3、+2V5、+1V1 等）并有 197 条走线；In2 放 GND 铜皮并有 848 条走线（GPIO、WiFi 线）；B.Cu 铺 GND | 通孔，0.419/0.2 mm 488 个，另有大孔 | 未找到 | 已核实 |
| 6 | BeagleBone Black（AM3358 ZCZ + DDR3） | 324 球，0.8 mm（来自 TI 数据手册，我没取） | DDR3 x16 | 6 | 官方手册只写"PCB Layers: 6"；顺序"信号-地-信号-信号-电源-信号"来自论坛提问者 | 如顺序属实则 4 | 未找到 | 未找到 | 未找到（Allegro .brd 43 MB 未解析） | 未找到 | 层数已核实；顺序**未核实** |
| 7 | NXP MIMXRT1050-EVKB（RT1052，同设计用于 RT1060 EVK） | MAPBGA 196，0.8 mm（手册未明写，数据手册信息，**未核实**） | 16 位 SDRAM（256 Mbit） | 4 | L1 元件面 / L2 GND / L3 电源 / L4 焊接面（NXP HDG 与 EVK 页面） | 2 | SDRAM 数据组走顶层，地址控制组走底层（HDG 7.3） | L3 整层电源面 | 通孔；BGA 区 14/8 mil（约 0.36/0.20 mm），线宽 4 mil，线距 3.79 mil；普通区 18/8 mil | NXP 验证板用 Isola FR4，厂家未写 | 已核实 |
| 8 | Hackaday "Open STM32 Minimal Display Board"（**没有做出来**） | ST TFBGA216 + MT48LC4M32B（VFBGA-90） | 32 位 SDRAM，两芯片间 57 根线 | 计划 4 层，6 层也可但贵 | 无 | 4 层的话 2 | 无 | 无 | 无 | OSH Park 提到过 | 已核实（设计者原文），但设计中止 |
| 9 | ST STM32H735G-DK | UFBGA176+25，0.65 mm（我没核实） | SDRAM 等 | 6（论坛贴出 Cu1–Cu4、Cu6，缺 Cu5） | 论坛贴出介质：Cu1 42 µm / 100 µm 芯板 / Cu2 / 100 µm 半固化 / Cu3 / 946 µm 芯板 / Cu4 / 100 µm 半固化 /…/ Cu6 | 未找到 | 未找到 | 未找到 | 未找到 | 未找到 | **未核实**（论坛二手，且贴子说引用的是 Altium 文件） |
| 10 | ST AN4938 Rev 7 推荐叠层（H74xI/G、H75xI/G） | 指南，不是板 | — | 6（4 层或 6 层为最低配置；"8 层可能用于多片 SDRAM/SRAM/NOR/LCD 的很密的板"） | 6 层示例：Top 高速信号+GND / Inner1 GND / Inner2 电源 / Inner3 低速信号 / Inner4 GND / Bottom 高速信号+GND | 3 | 高速信号在 Top 和 Bottom | 一整层电源面 | 未写 | — | 已核实（厂商文档） |

另外查过、但**不可比**的（不是 BGA 或没有板文件）：industrial-edge-gateway（STM32H743 LQFP144，4 层，无板文件）、phancak/STM32H7_Board（STM32H7S3 LQFP176，4 层，8 位 SDRAM）、h730duino（QSPI PSRAM）、BasicCode/STM32MP151_Dev_Board_PCB（用 SoM，2 层）。

## 2. 各设计的细节与来源

### 2.1 Antmicro STM32H7 HDMI board（最接近的 H7 BGA 实例）
- 来源：板文件 https://github.com/antmicro/stm32h7-hdmi-board/blob/HEAD/stm32h7-hdmi-board.kicad_pcb（KiCad 9 格式，45 MB）；项目页 https://openhardware.antmicro.com/boards/stm32h7-hdmi-board
- 已核实：八层铜 F.Cu、In1–In6、B.Cu，全部标为 signal 类型；铜皮层位：GND 铜皮在 In1、In3、In6（整层）以及 In2、In5 的部分；电源铜皮（+5V、+3V3、DVDD、AVDD、V3P3 等）在 In4；In2 和 In5 是实际走线的内层（In2 约 5260 mm，In5 约 4500 mm），In4 只有 5 条走线。这样信号层数是 F、In2、In5、B 共 4 层，电源只有 In4 一层且兼放少量走线。
- MCU 是 STM32H747XIH6，封装焊盘 TFBGA-289-265 17x17 布局，0.8 mm（已核实，封装名）。注意：**0.8 mm，不是 0.65 mm**。
- 存储：SDRAM 在板外的 SODIMM 上，不是板上的 90 球 BGA；SODIMM 网络 109 个：F.Cu 639 mm、B.Cu 3437 mm、In5 1841 mm（不走 In2）。MCU 的全部网络（含所有外设）：F 1462 / B 1560 / In5 2387 / In2 3806 mm。
- 过孔全通孔：0.45/0.2 mm 为主，0.35/0.2 mm 382 个（应是 BGA 区），无盲埋孔。
- 电容：MCU 焊盘范围内 26 个电容在 B.Cu（底面）；F.Cu 上 BGA 边外 6 mm 内只有 2 个。
- 没有两层相邻的信号层：In2（信号）夹在 In1 与 In3 两层 GND 之间，In5 夹在 In4 电源与 In6 GND 之间。
- 厂家：未找到。README 很短，未提。

### 2.2 ButterStick r1.0
- 来源：https://github.com/butterstick-fpga/butterstick-hardware/blob/HEAD/hardware/ButterStick_r1.0/ButterStick.kicad_pcb
- 已核实：八层，类型 F signal / In1 power / In2 signal / In3 power / In4 power / In5 signal / In6 signal / B signal；铜皮：In1 整层 GND，In6 整层 GND（所以 In6 虽标 signal，实际无走线），In3 切成 7 块电源，In4 切成 6 块电源加一块 GND。走线条数：F 5223、In2 5461、In5 4186、B 4350，In3 180、In4 87。
- 两片 DDR3L：U11 F 296 / In2 518 / In5 615 / B 375 mm；U12 F 340 / In2 518 / In5 615 / B 334 mm（数据共用的网络计两次，实际两片分了各自的网络，但分层比例一致）。四个信号层都被用来走存储。
- 过孔 0.45/0.2 与 0.4/0.2 mm，全通孔；电容：FPGA 范围内 39 个在 B.Cu。
- FPGA 是 ECP5UM5G-85 caBGA381，0.8 mm。

### 2.3 Logicbone
- 来源：https://github.com/oskirby/logicbone/blob/HEAD/logicbone.kicad_pcb ；Gerber 文件名（F_Cu、Gnd1、Sig1、Pwr1、Gnd2、Sig2、Gnd3、B_Cu 共 8 个铜层文件）：https://github.com/oskirby/logicbone/tree/HEAD/gerbers
- 已核实：层顺序见表；IC1 = ECP5UM-CABGA381（0.8 mm），IC2、IC3 = DDR3 FBGA-78（0.8 mm）。两片 DDR3 的网络分布几乎一样：F 约 250–270 mm、Sig1 约 380–410 mm、Sig2 约 430–455 mm、B 约 247 mm，Pwr1 147 mm（电源类网络）。
- Pwr1 层放所有电源铜皮；Sig2 层放一块 VBUS。没有两层相邻信号层：Sig1 夹在 Gnd1 与 Pwr1 之间，Sig2 夹在 Gnd2 与 Gnd3 之间。
- 过孔：658 个 0.5/0.2 mm，全通孔。电容：BGA 范围内 43 个在 B.Cu。

### 2.4 OrangeCrab r0.2.1（六层的实例）
- 来源：https://github.com/orangecrab-fpga/orangecrab-hardware/blob/main/hardware/orangecrab_r0.2.1/OrangeCrab.kicad_pcb ；README https://github.com/orangecrab-fpga/orangecrab-hardware/blob/main/hardware/orangecrab_r0.2.1/README.md ；审查清单 https://github.com/orangecrab-fpga/orangecrab-hardware/blob/main/hardware/orangecrab_r0.1/review/layout-checklist.md
- 已核实：六层 F.Cu、In1–In4、B.Cu。铜皮：GND 在 In1、In4；In3 上有十来块电源铜皮（3.3V、1.1V ×2、2.5V、1.35V、RAM_VDD、RAM_VDDQ、VREF、VBATT、USB VBUS、VSYS）。走线条数：F 2595、B 2021、In2 2391、In3 258（257 mm）、In1 10、In4 5。所以：信号层 F、In2、B 三层，In3 是"电源铜皮 + 少量走线"的混合层。
- 唯一的 DDR3L 芯片 U4（96 球 0.8 mm，x16）的网络分布：F 230 mm / In2 400 mm / B 212 mm / In3 40 mm。存储总线用了三个信号层，In3 仅少量。
- FPGA：csfBGA285，焊盘步距 0.5 mm（板里的封装），用 0.3/0.15 mm 与 0.28/0.15 mm 通孔，全通孔，无盲埋孔。审查清单里作者写"No ViP available. Larger tracks used to help reduce inductance"，"0.15mm vias are un-avoidable. Design has been Checked by manufacturer"。
- 电容：FPGA 焊盘范围内 27 个电容在 B.Cu。
- 相邻信号层：In2（信号）与 In3（电源铜皮 + 少量走线）相邻，In3 以电源为主。
- 说明：该板 FPGA 的 IO 用得不多（Feather 外形，约 20 个用户 IO），所以它只能证明"一个 x16 DDR3 + 少量 IO 的六层板，三个信号层够"，不能代表 127 个 IO 都用上的情形。

### 2.5 ULX3S（四层的实例）
- 来源：https://github.com/emard/ulx3s/blob/HEAD/ulx3s.kicad_pcb ；README https://github.com/emard/ulx3s/blob/HEAD/README.md
- 已核实：四层铜，每层之间介质 0.48 mm（板文件 stackup）；FPGA 为 BGA-381_pitch0.8mm；SDRAM 是 MT48LC16M16A2TG（TSOP，16 位，不是 BGA）。SDRAM 网络几乎全在 F.Cu（840 mm），B.Cu 只有 93 mm。In1 放电源铜皮并有一些走线，In2 放 GND 铜皮并走了 GPIO/WiFi 线 848 条。
- 通孔 0.419/0.2 mm 488 个。电容：FPGA 范围内 11 个在 B.Cu。厂家未找到。
- 与本案差别：SDRAM 是 TSOP 且只有 16 位，不是 BGA，FPGA 的球可以随意分配引脚，所以不能代表 MCU 的固定 FMC 引脚。

### 2.6 BeagleBone Black
- 来源：官方 SRM（仓库里的旧版）https://github.com/beagleboard/beaglebone-black/blob/HEAD/docs/OLD_BBB_SRM.pdf ，第 9.1 节"PCB Layers: 6，PCB thickness: .062""（已核实，我用 pdftotext 取出）。
- Allegro 板文件 `ALLEGRO/BeagleBone Black_PCB_RevD_250403.brd`（43 MB 二进制，未解析）；`MFG/` 有 lyr1.art–lyr6.art 六个 Gerber：https://github.com/beagleboard/beaglebone-black/tree/HEAD/MFG 。我数了每个 Gerber 的绘制数，但没法据此判断哪层是整面平面，所以没有得出层功能。
- 设计者 Gerald Coley 在邮件列表说："The six layer design was dictated by needing enough layers to make all the connections."（已核实，原话；https://groups.google.com/g/beagleboard/c/OUpHBFIA1uc ）。同一贴里提问者 Alexandre 把叠层写成"signal-gnd-signal-signal-vcc-signal"，这是提问者自己的描述，**未核实**；Coley 说叠层在 CircuitCo 的 PCB 文件包的 PDF 里（这个 PDF 我没找到）。
- 若提问者属实，BBB 就是"六层、4 个信号层、只有一层 GND 一层电源"的例子，其中 L3、L4 两个信号层相邻。

### 2.7 NXP MIMXRT1050-EVKB / RT1060-EVK（四层 + 16 位 SDRAM）
- 来源：NXP《Hardware Development Guide for the MIMXRT1050/MIMXRT1060》Rev.0, 08/2018，第 7 章 https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/imxrt/26466/1/NXP_iMX_RT1060_HDG.pdf ；MCUXpresso 板页面（"4-layer through-hole USB-powered PCB"）https://mcuxpresso.nxp.com/mcuxsdk/25.03.00/html/boards/RT/evkbmimxrt1060/index.html
- 已核实（HDG 7.1）："The recommended stackup is four layers"；7.2：小电容与大电容放在 CPU 的底面，BGA 区域通孔 14/8 mil、线宽 4 mil、线距 3.79 mil，其余区域 18/8 mil、5/7 mil；7.3："Because the RT1050-EVK is a 4-layer board design, both routing groups refer to the GND plane"，数据组走顶层（参考第 2 层），地址控制组走底层（参考第 3 层）。
- 差别：16 位 SDRAM（约 30 根线），196 球 0.8 mm，IO 少；证明"4 层 2 个信号层 + 底面去耦"在小得多的存储总线上可行。

### 2.8 Hackaday "Open STM32 Minimal Display Board"（与本案同一问题）
- 来源：设计者自己的日志 https://hackaday.io/project/169173/log/173152-bga-fun （2020-01-20，作者 Andy）。
- 已核实（原文摘录）：用标准设计规则可以把 ST 的 TFBGA216 完全扇出，4 层板；准备用 MT48LC4M32B（ST 开发板用的同一款，VFBGA-90），"ends up being 57 total connections between the two devices"；"once you start to try to route out an SDRAM chip with a standard pinout ... the idea of using a BGA starts to fall apart"；最后放弃 BGA。作者目标是 4 层，6 层也可行但贵；OSH Park 规则更严（5 mil 线宽线距，18 mil 过孔）。
- 意义：57 根线、同一款 90 球 SDRAM，与本案完全一样，设计者在 4 层上放弃。

### 2.9 ST 厂商文档与 ST 评估板
- ST AN4938 Rev 7（STM32H74xI/G、H75xI/G 硬件开发）9.1 节：https://www.st.com/resource/en/application_note/an4938-getting-started-with-stm32h74xig-and-stm32h75xig-mcu-hardware-development-stmicroelectronics.pdf （已核实：我用 web fetch 工具取得文件后 pdftotext）。原文："The minimum configuration that can be used is a four- or six-layer stack-up. An eight-layer boards may be required for very dense PCBs that have multiple SDRAM/SRAM/NOR/LCD components."六层示例见表第 10 行。9.3 节图 22："Decoupling capacitor and STM32 MCU on the opposite sides of the package (BGA package)"，即 BGA 的去耦电容放对面。
- ST 用户手册 UM2198（H743I-EVAL）全文无"layer / PCB / stack"字样（已核实，我检索了文本）。所以 ST 评估板的层数只能从设计包里看（见"未能读取的来源"）。
- ST 社区贴 H735G-DK：提问者从 Altium 文件里读出 Cu1、Cu2、Cu3、Cu4、Cu6 的厚度，没有读到 Cu5，推测是六层；被标为采纳答案的社区用户 LCE（不是 ST 官方说法）建议"forget about their specific board stack"，并说"I really like 6-layer boards, with 2 GND-planes, 1 underneath top and bottom each"。https://community.st.com/stm32-mcus-boards-and-hardware-tools-26/stm32h735g-dk-stackup-151565 （**未核实**，论坛）。
- ST 社区贴 H7S78-DK：ST 员工称叠层与阻抗表在 MB1736 制造文件里的 `MB1736D_Gerber.PDF` "Drill Drawing" 页；贴子称 Altium 工程里的叠层没配置。https://community.st.com/stm32-mcus-boards-and-hardware-tools-26/stm32h7s78-dk-actual-pcb-stackup-octo-spi-hexa-spi-impedance-166989

### 2.10 指针（非一手，仅供线索）
- FEDEVEL 论坛 2025-07，STM32H7 + 0.8 mm SDRAM，提问者想用"6 层（3 个走线层）或最多 8 层，只用通孔"，回复里没有给出层数建议：https://fedevel.com/forum/schematic-design-pcb-layout/need-guidance-and-tips-on-routing-sdram-bga
- Phil's Lab #78（六层混合信号板，含 STM32H7 与 SDRAM，设计文件没有给出链接）：https://fedevel.com/blog/mini-6-layer-mixed-signal-hardware-design-walkthrough-phils-lab-78 ——页面只写"6-Layer"，不含叠层顺序、过孔或文件链接。

## 3. 对 0.65 mm 201 球 MCU + 90 球 SDRAM 六层板意味着什么

数的是上面表里有板文件或厂商文档的设计（不含没做出来的第 8 行、未核实的第 9 行）：

- **三个或更少信号层就够的**：OrangeCrab（六层，3 个信号层 + 1 个电源混合层，x16 DDR3，IO 少）、ULX3S（四层，SDRAM 只在外层，16 位 TSOP）、NXP RT1050-EVKB（四层，2 个信号层，16 位 SDRAM）。三个都有一个共同点：存储总线只有 16 位，并且主芯片的 IO 少或引脚可自由分配。
- **四个或更多信号层的**：Antmicro H7 HDMI、ButterStick、Logicbone，**全是八层板**（BBB 若按论坛的说法是六层 4 个信号层，但未核实）。三个八层板都是"4 个信号层 + 2 层 GND 以上 + 1–2 层电源/铜皮层"，没有一个是靠"把电源面改成信号层"得到第四个信号层的。
- **六层 vs 八层**：已核实的六层板只有 OrangeCrab（和 ST AN4938 的示例）；已核实的八层板有 3 个。有 4 个信号层的已核实设计全部是八层。
- **不用整层电源面时的做法**：OrangeCrab 把 In3 做成"电源铜皮层"（全部电源切成块，加少量走线）；ButterStick 用两层切割电源面；Logicbone 用一层；Antmicro 用 In4 一层加外层/内层铜皮；ULX3S 用 In1 的铜皮。没有一个设计是"没有任何电源面，靠外层铜皮和走线供电"。所有设计都是电源铜皮放在内层，BGA 的电源球靠通孔连到内层铜皮。
- **与用户假设相矛盾或需要修正的地方**：
  1. "加一个信号层"在六层板上意味着要把现有的 GND 或电源面让出来：已核实的资料里没有"六层四个信号层"的例子。用户回忆的"自己的六层板有四个信号层"可能是 BBB 那样的"信号-地-信号-信号-电源-信号"，这个叠层在论坛说法里出现过，但官方一手资料没有确认，ST 的六层示例是三个信号层（Top、Inner3 低速、Bottom）。
  2. ST AN4938 明说"很密的 SDRAM/SRAM/NOR/LCD 板可能需要八层"，本案 127 个 IO + 57 根 FMC 线 + LTDC，正属于这一类。
  3. 所有已核实的 0.8 mm BGA 设计（Antmicro、ButterStick、Logicbone）用的过孔主要是 0.4–0.5/0.2 mm（Antmicro 另有 0.35/0.2 mm）（比本案 BGA 区的 0.30/0.15 mm 大），MCU 的 0.65 mm 间距比它们都小；只有 OrangeCrab（0.5 mm 间距）用 0.3/0.15 mm，但 IO 很少。
  4. 没有一个设计用了盲埋孔、微孔或盘中孔（KiCad 板文件里已核实全部是通孔；OrangeCrab 作者明说没有 ViP），所以"只用通孔"不是特殊限制。
  5. 去耦电容放在 BGA 底面正下方是通例（五个 KiCad 板，BGA 范围内的电容全在 B.Cu：11 / 26 / 27 / 39 / 43 个；ST AN4938、NXP HDG 都这样建议）。这些设计里 B.Cu 照样用于走线（ButterStick、Antmicro 的存储总线在 B.Cu 上有大量走线），我没有量化电容吃掉了多少通道，板文件里看不出来。
  6. 相邻的两个信号层：已核实的设计里**没有**两个纯信号层相邻（每个信号层都夹在 GND/电源之间）；OrangeCrab 的 In2 与 In3 相邻，但 In3 是电源铜皮层。BBB 的 L3、L4 相邻属未核实。所以"相邻信号层怎么处理（正交走线等）"在这些设计里没有现成答案。
  7. 与本案最接近的失败案例是 Hackaday 那块：同一款 90 球 SDRAM、同样 57 根线，设计者在四层上放弃了 BGA；没有六层的反例或正例。

## 4. 未能读取的来源（需要人工下载）

- ST 评估板与 Discovery 的设计包（制造文件、Allegro/Altium 工程）：STM32H743I-EVAL MB1246、STM32H745I-DISCO、STM32H750B-DK、STM32H747I-DISCO、STM32F746G-DISCO、STM32F769I-DISCO、STM32H7B3I-DK、STM32H735G-DK、STM32H7S78-DK（MB1736，其 `MB1736D_Gerber.PDF` 的 Drill Drawing 页含叠层与阻抗表）。入口：各产品页 https://www.st.com/en/evaluation-tools/stm32h743i-eval.html 的 CAD Resources；需要登录或同意许可，我没有取。已核实它们的用户手册（UM2198）里没有层数。
- Arduino Portenta H7（STM32H747，BGA240）：只有原理图 PDF（https://docs.arduino.cc/resources/schematics/ABX00045-schematics.pdf），没有公开 PCB 文件，论坛上有人问过没答案：https://forum.arduino.cc/t/portenta-h7-carrier-boards-pcb-layouts/1387995
- OpenMV Cam H7 Plus：32 位版只公开了 PDF 原理图，PCB 文件需发邮件向 OpenMV 索取：https://forums.openmv.io/t/openmv-cam-h7-plus-board-design-file/6506
- Electro-Smith Daisy Seed：没有找到公开的 PCB 文件。
- BeagleBone Black：Allegro 板文件（43 MB）和 CircuitCo 的叠层 PDF 没有解析/找到；Rev C.1 SRM（https://cdn.sparkfun.com/datasheets/Dev/Beagle/BBB_SRM_C.pdf）返回 403。
- NXP i.MX RT1050/1060 EVK 的板文件、EVKB 用户手册第 2.7 节"PCB information"：未读（HDG 已读）。
- Olimex OLinuXino（A20-LIME2、A64、STMP157-LIME2）：仓库 https://github.com/OLIMEX/OLINUXINO/tree/HEAD/HARDWARE 里的 `.brd` 是 Eagle 二进制格式，我没有解析层数。
- MNT Reform（i.MX8M 模块）、Antmicro 其他板、PocketBeagle：没有查。
- Antmicro、ULX3S、Logicbone、ButterStick、OrangeCrab 的制造商与叠层厚度：除 ButterStick、ULX3S、Antmicro 板文件里的介质厚度外，没有找到厂家名。
- 已读取但站点拒绝机器访问：oreilly.com（403）、BBB SRM 的 SparkFun 镜像（403）。
