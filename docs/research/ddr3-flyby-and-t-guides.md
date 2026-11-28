# 调研：RK3568 + 两颗 16 位 DDR3 的 fly-by 与 T 型设计指南

日期 2026-11-28。接 `research/rk3568-ddr3-layout-requirements`（下称“前一份调研”）。用户的问题：有没有 fly-by 的设计指南可看，fly-by 对这块板是不是 T 型之外的真选项。后来加了范围：T 型的设计指南也同样收齐。本文只列事实和待定点，不推荐。

## 0. 怎么读

- 核实程度标记：**已核** = 本次打开了原文（PDF 文本或页面图）；**转引** = 取自仓库里别的调研分支，那份调研称读过原文，本次没有重新核对；**未核实** = 没有拿到一手原文。
- 资料来源与页码口径（Rockchip 文件取自留档分支 `integration-rk3568` 的 `rk3568_minsys/refs/`，原文件没有提交进 main）：

| 简称 | 文件 | 页码口径 |
|---|---|---|
| HDG | `RK3568_Hardware_Design_Guide_V1.2_EN.pdf`，Rev V1.2，2022 | 页脚页码（PDF 页序 = 页脚 + 19） |
| HS | `Rockchip_RK3568_High_Speed_PCB_Design_Guide_V10_EN_2021-4-12.pdf` | 页脚页码 = PDF 页序 |
| CHK | `Rockchip_RK3568_Schematic_and_PCB_Review_Checklist_V1.0_CN.xlsx`，工作表 `DRAM` | “序号”列 |
| EVB1 原理图 | `refs/evb1/RK_EVB1_RK3568_DDR4P216SD6_V10_20200908.pdf`，Rev V1.0，2020-09-23 | 第 25 页 / 共 50 页（“33.DRAM-DDR4_2x16bit_96P”） |
| Micron TN-41-13 | `tn-41-13.pdf` Rev. B 08/13，下载自 hackaday.io 镜像（`cdn.hackaday.io/files/19354828041536/tn4113_ddr3_point_to_point_design.pdf`），文档页脚页码 | 页脚页码 |
| TI SPRABI1D | “DDR3 Design Requirements for KeyStone Devices”，2018-01 起，2022-07 修订（ti.com/lit/an/sprabi1d/sprabi1d.pdf） | 章节号 |
| NXP HDG | IMX6DQ6SDLHDG Rev. 3（06/2018），NXP 社区附件 | 页脚页码 |
| TI AM335x | SPRS717L（2011-10 起，2020-03 修订）数据手册 §7.7.2.3；SPRABN2A（2019-12）原理图检查表 §2.6.2 | 章节号 |

- 速率：RK3568 的 DDR3 实际速率这里没有定。下面各来源的数值对应的速率各不相同，已在表里写出。
- 页面图、原理图图形：HDG 第 18、19、179 至 181 页、HS 第 33、36 页是本次看了页面图的（100 dpi）。

## 摘要

**已经确定**

1. Rockchip 对 RK3568 DDR3 的两种拓扑都写了：DDR3/DDR3L 4 颗 16 位 2CS 用 T（数据一驱二，CA 双 T 一驱四）；DDR3/DDR3L + ECC 共 6 颗 16 位 2CS，CA 用 fly-by（HDG 第 18、19 页）。**两颗 16 位、单片选的 DDR3 没有单独写**（前一份调研已指出，本次复核仍然成立）。
2. Rockchip 的 DDR3 fly-by 有明确数值：末端 39 Ω 接 VTT（HDG 第 19 页）；HS 第 30 页“R1 取 39 Ω 或 43 Ω，BI1 支线尽量短”；控制线 M 段阻抗 43 Ω（HS 表 25）；CSn/CKE/ODT 对 CLK 容差 60 mil（比 T 型的 30 mil 松）。**没有**给支线长度数字、没有给颗粒间距数字。
3. 检查表 CHK 项 44 对 DDR3 fly-by 写的是“请直接套用 Rockchip 提供的 DDR 参考模板”。本地没有这个模板，官方包里只有 LP4X 模板。
4. Rockchip 的 T 型规则（DDR3）：L2a、L2b 各 < 600 mil、互差 ≤ 20 mil、CLK 的 RC 在分支点（HDG 第 179 至 181 页；CHK 项 43）。分叉点位置、过孔还是走线层、主干与支线阻抗差异、过孔数，Rockchip 文件里**都没有写**。
5. 官方 EVB1 是 2 × 16 位 **DDR4**，用 T 型，CA 借 L4（内层）；原理图上 CLK、CKE、CS0n、ODT0 在每个分支起点各有一颗 0 Ω（共 10 颗）；CHK 项 15 和 HDG 第 19 页明文写 DDR4 T 型要在分支点串电阻，DDR3 的对应条目（CHK 项 13、HDG 第 18 页）**没有**这句话。
6. 通用来源对“两颗点对点 DDR3”：Micron TN-41-13 明说树形（T）可用，且可以不要 VTT；TI、ST、Intel、AMD 的 DDR3 文档都按 fly-by 写。NXP i.MX6 的 T 型限 4 颗，fly-by 要端接电阻，没有两颗专门的数字。

**没有确定**

- RK3568 DDR PHY 是否对 DDR3 做写均衡、rkbin DDR 固件里拓扑是否可配置：本次**没有找到一手资料**（HDG、数据手册、HS 里没有 “leveling” 一词；rkbin 固件是闭源二进制；U-Boot 原生驱动的 RFC 补丁我没能打开）。
- Rockchip 有没有 RK3568 的 DDR3 参考设计或 DDR3 模板：本次没找到（与前一份调研一致）。
- ST AN5122（两颗 16 位 DDR3 fly-by 的最直接来源）、NXP i.MX6 的两颗 DDR3 专门章节、JEDEC JESD79-3 / DIMM 设计规范：原文本次拿不到或没有。
- 带 L 形布局（一颗在 SoC 西侧、一颗在北侧）能否做 fly-by 链：没有找到任何来源直接讨论，见第 4 节。

## 1. Rockchip 的立场（fly-by）

| 问题 | 事实 | 出处 | 核实 |
|---|---|---|---|
| 官方是否写了 DDR3 fly-by | 写了，但只用于 ECC 配置：“For DDR3/DDR3L+ ECC six 16bit 2CS, DQ uses T topology (one drive two), CA uses Fly-by topology (one drive six).” | HDG 第 18 页 §2.1.7.4；图 2-20（第 19 页）；HS 第 36、37 页图 DRAM0a 至 DRAM2b | 已核（文字加页面图） |
| 官方是否写了“两颗 16 位 DDR3”的拓扑 | 没有。唯一直接提到“两颗 16 位 DDR3/3L”的是电源容量（1 A DC/DC，HDG 第 44 页）。DDR4 有“two 16bit 1CS：DQ 点对点，CA 用 T（一驱二）”（HDG 第 19 页，图 2-21）；DDR3 的 4 颗 2CS 配置里每个 DQ 驱两颗（两个 rank），不是点对点 | HDG 第 18、19、44 页 | 已核 |
| fly-by 端接 | “Clock, control, address line signal matching mode: add 39ohm resistor to the VTT power at the end.”（DDR4 fly-by 同句，并加“选 VTT 芯片要支持 DDR4”） | HDG 第 19 页（DDR3）、第 20 页（DDR4） | 已核 |
| 端接电阻值 | “For Fly_by topology, R1 recommend 39ohm or 43ohm. BI1 trace length shall be kept as short as possible.” R1 在图里是末端到 VTT 的电阻；BI1 是每颗 DRAM 的支线；T3 是链末端到 R1 的一段 | HS 第 30 页建议 16；HS 第 36 页图 | 已核 |
| fly-by 的阻抗 | 控制信号：M 段（SoC 出来到第一颗之前的主干）43 Ω ±10%，其余 50 Ω ±10%；命令/地址：M 段 50 Ω | HS 表 25、26（第 36、37 页）；HDG 表 3-7、3-8（第 183、184 页） | 已核 |
| fly-by 的长度容差 | CSn/CKE/ODT 对 CLK：< 60 mil；其他 CA 对 CLK：< 600 mil；CLKP/N < 12 mil；CLK 对 DQS < 1500 mil。图里的 M、BO1、BI1、BI2、T3 各段**没有**给长度上限或颗粒间距 | HS 表 24 至 26；HDG 表 3-5 至 3-8；HDG 第 182 至 184 页 | 已核（HS 表 24 的文本行序错乱，数值与 HDG 表 3-6 一致） |
| CLK 的 2 pF | fly-by 时在 RK3568 端的 CLKP/N 之间预留 2 pF，是否贴按调试，布局时尽量靠近 RK3568；没有 RC | HDG 第 19 页；CHK 项 14 | 已核 |
| 检查表对 DDR3 fly-by | 项 14：“选择DDR3+ECC时：采用Fly-by拓扑，末端端接电阻不可删除……”；项 44：“DDR3 采用Fly-by拓扑：请直接套用Rockchip提供的DDR参考模板。”；项 34（DDR4）同句 | CHK 项 14、34、44 | 已核 |
| 官方模板 | 官方包 `02_DDR Template` 只有 LP4X 模板；DDR3 模板本地没有，网上也没找到（前一份调研 §8） | 前一份调研 | 转引 |
| 写均衡（write leveling）在 RK3568 DDR PHY | 本地的 HDG V1.2、数据手册（ds.txt）、HS 里 grep “leveling” 为零。JEDEC 要求 DDR3 颗粒本身支持写均衡（i.MX6 HDG §3.6.1 引 JESD79-3E “Write Leveling” 一节，要求每字节 D0 的位序固定）；RK3568 控制器端是否实现、固件是否使用，没有一手资料 | 本地 grep；NXP HDG 第 43 页 | **未核实** |
| rkbin DDR 固件 | 公开的是闭源二进制 `rk3568_ddr_*MHz_vX.XX.bin`，配 `ddrbin_tool` 和 `ddrbin_param.txt` 改参数（Barebox RK35xx 文档、Radxa 论坛）。参数表里有没有“拓扑”或“均衡开关”：没有看到 | barebox.org/doc/latest/boards/rk35xx.html；forum.radxa.com 的 rkddr 帖 | **未核实**（只读到使用说明，没读到参数项） |
| 其他 Rockchip 芯片 | RK3288 技术手册列有 DDR3 写均衡支持（Radxa 论坛帖转述，帖子里写均衡没被触发，无结论）；RK3399 的 coreboot/U-Boot 驱动里有 write leveling 流程和 PHY 位（Rockchip 工程师提交 “improve write leveling flow”）。这是别的芯片，不能直接推到 RK3568 | forum.radxa.com/t/rk3288-ddr3-write-leveling-support/1524；coreboot-gerrit 2016-06 “rk3399: fix sdram training issue” | 转述自搜索摘要，**未核实** |
| 使用 fly-by 的 Rockchip 参考板 | HDG 里 6 颗 ECC 的 fly-by 只有框图；EVB1 是 DDR4 的 T 型；LP4X 模板点对点。RK3566 / RK3588 / RK3399 / RK3288 的 DDR3 fly-by 参考板：本次**没有查到** | — | **未核实** |
| 有无 VTT 的 Rockchip 参考 | ECC fly-by 带 VTT（39 Ω）；T 型两颗不带 VTT（HDG 图 2-18、HS 第 33、34 页图里没有端接） | 同上 | 已核 |

## 2. 通用 fly-by 设计指南（与 Rockchip 之外）

这一节的数字主要用于对照，不是 Rockchip 对 RK3568 的要求。

| 来源 | 链序与支线 | 端接 | 长度匹配 | 层、过孔、阻抗 | 适用速率 / 负载 | 核实 |
|---|---|---|---|---|---|---|
| **JEDEC JESD79-3**（DDR3） | 规范要求 DDR3 颗粒支持写均衡，DIMM 上 CA/CK 走 fly-by | — | — | — | — | **未核实**（付费或需注册，没有拿到原文；仅由 Micron TN-41-13 第 4 页间接确认“DDR3 架构假定菊花链/fly-by，支持 JEDEC DDR3 模块必须支持 fly-by”） |
| **Micron TN-41-13**（Rev. B 08/13，点对点设计） | 第 4 页：“DDR3 point-to-point designs … do not have to be implemented using a fly-by architecture.” 点对点可用 DDR2 树形（“minimal timing skew concerns; command/address/control buses that likely do not require termination”）或 DDR3 fly-by（“significant timing skew between clock and data buses; … require termination”）。同页：即使点对点里用了 fly-by，“generally better to hard code the skews rather than use the write-leveling feature” | 第 16 页：fly-by 的“最后一颗接 VTT”；表 8（DDR3-1333 仿真）fly-by：抖动 5 ps、孔径 1.37 ns、电压余量 100 mV；图 7（第 20 页）画了 fly-by 结构 | 第 10 页：数据位周期 1%（±0.5%），800 MHz 时约 ±1 mm（6.5 ps/mm，外层约快 10%）；“选 1 mm 完全是任意的”。第 9 页写均衡：时钟链式四颗时每颗相差 150 至 200 ps，第一与最后相差 450 至 600 ps；“只有同面 4 颗以上、时钟菊花链时才有用”，训练式读写微调为首选 | — | 仿真是 DDR3-1333；Micron 写明“必须自己仿真” | 已核 |
| **TI SPRABI1D**（KeyStone，DDR3-1333/1600，最多 9 个负载） | §3.1：DDR2 用平衡 T，DDR3 改 fly-by；T 的缺点是“varying amount of additional skew because of … multiple stubs”；fly-by 的代价“delay is different at each SDRAM … handled through read and write leveling”。支线：地址/命令/控制 < 80 mil、支线间偏差 ±10 mil（表 6-2、6-3）；时钟对支线 < 40 mil（表 6-6） | §6.2.1：端接 39 至 42 Ω 接 VTT（首选 39 Ω 1%），放在最后一颗之后，走线到电阻 ≤ 500 mil；时钟每路 39 Ω 串 0.1 µF 接 VDDQ；“External terminations may not be required — the only way to determine … is to perform complete simulations”。§6.2.2：“TI does not recommend the use of DDR3 without leveling” | 地址/命令对时钟 ±20 mil；每段过孔数相同；地址线不许交换 | 地址/命令 50 Ω 单端；走相邻完整地或电源面；走线用靠近中心/上层的层以减少过孔偏斜 | §6.5.1：KeyStone I 验证到 1333 MT/s、KeyStone II 到 1600 MT/s，最多 9 个负载，“fewer than nine loads should all operate at … or below” | 已核 |
| **TI AM335x 数据手册 SPRS717L** §7.7.2.3.4.1 | 两颗 DDR3 = 两颗 x8 组成一个 16 位 bank；图 7-52、7-53：A1、A2、A3 到末端 AT，末端 Rtt 接 Vtt（CK 末端 Rcp + Cac 到 VDDS_DDR）；同面或镜像 | 表 7-68 第 19、20 行 Rcp、Rtt；脚注 13：“Source termination (series resistor at driver) is specifically not allowed.” | 表 7-68：A3（支线）最长约 25 mil，A1+A2 最长约 2500 mil，CACLM 为 Manhattan 最长距离 + 300 mil。表格列在文本抽取里错位，数值与列的对应**把握中等** | 阻抗见表 7-62（未取）；跨层要加旁路电容 | 速度等级未取 | 已核（章节、图；表值列对位中等） |
| **TI SPRABN2A**（AM335x 原理图检查表）§2.6.2 | “For point-to-point DDR3 topologies (single x16 DDR3 IC), VTT termination is not needed.” “Designs using two x8 DDR3 IC’s may wish to consider using a termination regulator [TPS51200].” | 时钟端接到 VDDS_DDR 加交流耦合电容；不要对 DDR_RESET 端接；无 VTT 时 VREF 用 10 kΩ 1% 分压 | — | 文中没有提 T 或 fly-by 字样 | — | 已核 |
| **NXP i.MX6 HDG**（Rev. 3）§3.6.3 | “Fly-by … DDR controller provides address mirroring when using two chip selects …”；图 3-11、3-12（8 颗，4 GB）；§3.6.7 八颗 fly-by 布线示例，注明“SABRE SD 板不用八颗，截图来自验证板” | “Bus termination resistors are required.”（没给阻值） | 见第 3 节表（同一张按字节组匹配表） | 示例 8 层板 | 没有两颗 fly-by 的专门数字 | 已核（图为图片，数字未读） |
| **ST AN5122**（STM32MP1，Rev 3，2019-02） | 转引（前一调研称读过原文）：两颗 16 位 DDR3 用 fly-by；第二颗字节组与第一颗字节组差 ≤ 1300 mil（§6.1）；地址/命令、CK 两颗之间 ≤ 1300 mil（§6.3） | 转引：地址/命令总线 56 Ω 接 VTT（符号在抽取里丢失，按上下文）；差分时钟跨一颗 100 Ω；§6.5.2 VTT 当电源处理、每两颗 RTT 电阻一颗高频电容 | 转引：DQS 比 CK 短 0 至 590 mil（CK 必须最长）；CK 最长 4.72 in；地址/控制比 CK 短 0 至 40 mil；DQ/DM 对 DQS ±40 mil；“不推荐 serpentine” | — | 本次 ST 网站对脚本访问返回验证页，**没能重新打开原文**；仅用搜索摘要确认章节标题：§2.1“32-bit DDR3/DDR3L interface”、§3.1“Standard fly-by topology”、§3.2“Cost-optimized point-to-point topology”、§6“Memory layout rules” | 转引，**未核实** |
| **Intel EMIF 手册** §2.6.5.1；**AMD UG583** | 转引摘要：Intel——×16 少负载、支线越短越好、第一颗到最后一颗飞行时间差 < 0.69 tCK、“双 fly-by”（中途分叉）会多一个不连续点，两分支要等长且分叉前主干长于分支；AMD——DDR3 章节只有 fly-by，T 分支只在 QDR II+ 章节出现；地址/命令/控制总长上限 6.15 in（1 个负载）至 12.15 in（9 个负载） | — | Intel：每颗 CK − DQS > 0（写均衡需要）；AMD：±8 ps | AMD UG863：fly-by 最多用两层，每个层间过孔 50 mil 内一个地过孔 | — | 转引（来源为网页摘要），**未核实** |
| **NXP AN5097**（DDR4） | 转引：DDR4 地址/命令/控制/时钟用 fly-by，终点端接 | — | 对时钟 ±10 mil | — | DDR4，不是 DDR3 | 转引，**未核实** |

注：前一份调研的“转引”条目都在 `research/highspeed-pcb-pitfalls`（`docs/research/highspeed-pcb-pitfalls.md` §2.5 至 §2.7），那份文件自己写了哪些是读原文、哪些是网页摘要，本文沿用它的标注。

## 3. 两颗芯片时：T 与 fly-by 各个来源怎么说

| 来源 | 对“两颗”的说法 | 核实 |
|---|---|---|
| Rockchip HDG / HS / CHK | 两颗 DDR3 单片选没有直接条目；T 型数值见第 5 节；fly-by 数值只在 6 颗 ECC 条目下 | 已核 |
| Micron TN-41-13 表 8（DDR3-1333，点对点，一个控制器 + 两颗至四颗，Figure 4 画了 DRAM #1、#2、#4） | 树形加 VTT：抖动 5 ps、电压余量 140 mV；树形无串阻无 VTT：28 ps、510 mV；树形加 10 Ω 串阻：33 ps、560 mV；fly-by：5 ps、100 mV。文字：树形加串阻或不加串阻“acceptable signal quality without having to provide VTT power”；fly-by “ease of layout at the expense of VTT power and termination; it also induces a skew between the clock and the data bus”。“Micron 的仿真值不是推荐，要自己仿真”。第 4 页：点对点系统树形的“minimal timing skew concerns” | 已核 |
| TI SPRABI1D | 全文按 fly-by + VTT + 写均衡写；§6.2.2 不推荐不用均衡的 DDR3（“nothing more than a DDR2 layout with all of the negative implications associated with DDR2 and none of the benefits of DDR3”）；没有两颗 T 的数字 | 已核 |
| TI AM335x（两颗 x8 一个 16 位 bank） | 用的是带末端 Vtt 的 A1/A2/A3 链，不是 T | 已核 |
| NXP i.MX6 HDG §3.6.2 / §3.6.3 | T：“Termination resistors not required. Short routing lengths and on-chip drive strength control. Your design is limited to 4 DDR chips.” fly-by：“Bus termination resistors are required.” 4 颗 2 GB 示例用平衡 T（§3.6.4：“Have a balanced routing for the T connection. Avoid having many layer transitions. Do not cross split reference planes”）。NXP 社区回帖（官方人员，非文档）：4 颗以下建议 T，超过则 fly-by；也说过只贴一颗的 T 总线，未用的支线会反射，fly-by 更合适 | 文档已核；回帖为搜索摘要，**未核实** |
| ST AN5122 | 两颗 16 位 DDR3 用 fly-by（§2.1、§3.1）；单颗点对点是“成本优化” | 转引，**未核实** |
| 第三方（Altium、PCBWay、Design007 文章） | 2 至 4 颗两种都可用，4 颗以上建议 fly-by；Design007 说两颗时 fly-by 与双 T 都可，DDP 颗粒时双 T 余量更好。这是博客类二手来源 | 搜索摘要，**未核实**（二手） |

代价清单（只列各来源写了的）：

| 项 | fly-by | T |
|---|---|---|
| 额外器件 | VTT 稳压器 + 每根 CA/CTRL 一个末端电阻（Rockchip 39 或 43 Ω；TI 39 至 42 Ω；ST 56 Ω 转引）；时钟端接。TI SPRABI1D §6.3.1.8：VTT 稳压器靠近 SDRAM 的 VTT 脚，每个 VTT 脚旁至少一颗 0.1 µF，岛上至少一颗 10 至 22 µF（转引） | Rockchip：CLK 在分支点 2 × 49.9 Ω + 100 pF（HDG 图 2-19、3-42）；无 VTT |
| 软件/训练依赖 | 依赖写均衡或固件固定偏斜（Micron：同面 4 颗以下“hard code the skews”更好；TI：不均衡不推荐） | Micron：几乎不依赖 |
| 偏斜限制 | CK 对 DQS：CK 必须不短于 DQS（ST 转引 DQS 比 CK 短 0 至 590 mil；Intel 转引每颗 CK − DQS > 0；Rockchip 只给 CLK 对 DQS < 1500 mil，没写方向） | Rockchip：CLK 对 DQS < 1500 mil，同样没写方向 |
| 速度 | TI：1333 / 1600 MT/s 验证到 9 个负载 | Micron：仿真到 DDR3-1333；NXP：T 限 4 颗，没给速率；Rockchip 的 T 型两颗数据没有速率上限说明（前一份调研） |
| 布线难点 | 支线极短（TI < 80 mil / < 40 mil）；链末端留空间放电阻与 VTT 岛 | 支线 ≤ 600 mil（Rockchip）、分支匹配 20 mil（Rockchip）或 1 mm（Micron）、分叉点要有位置 |

## 4. fly-by 对我们这块板会改变什么（事实，不是决定）

前提：RK3568 + 两颗 MT41K256M16TW-107:P（96 球），一颗在 SoC 西侧、一颗在北侧（L 形），地址端朝向 SoC 的 A1 角，球区间隙 7.5 mm。

| 项 | 事实 | 出处 | 核实 |
|---|---|---|---|
| 多出的器件 | 一路 VTT（0.75 V，DDR3L 为 0.675 V）稳压器及去耦；CA/CTRL 末端电阻：地址线 A0 至 A14（MT41K256M16 是 15 根行地址，A0–A14）、BA0–2、RAS、CAS、WE、CS0、CKE、ODT 共约 24 根，加 CLK 的端接（HDG 写 CLK 与控制、地址同样 39 Ω 接 VTT；TI 是 39 Ω + 0.1 µF）。阻值：Rockchip 39 或 43 Ω | HDG 第 19 页；HS 第 30 页；TI SPRABI1D §6.2.1。信号根数是我按 DDR3 引脚数的计数 | 阻值已核；根数是我的计数，**未核实** |
| 电阻位置 | 放在链的末端，最后一颗之后（TI：走线到电阻 ≤ 500 mil；Rockchip：T3 段，没给数字）。末端电阻要靠 VTT 岛 | TI §6.2.1；HS 第 36 页图 | 已核 |
| 对布局的约束 | 链上顺序：SoC → 第一颗 → 第二颗 → 电阻；每颗的支线极短（TI < 80 mil）。Rockchip 的 fly-by 图是三颗上下排成一列，沿一条竖直主干 | HDG 图 2-20；TI 表 6-2 | 已核（图） |
| L 形布局与 fly-by 的兼容性 | **没有找到任何来源直接讨论 L 形**。来源里能确认的是：Intel（转引）“双 fly-by 中途分叉”要求两分支等长且主干长于分支；TI AM335x 图 7-54/7-56 同面与镜像两种；Rockchip 图都是直线排列。链的第一颗到第二颗之间多走的长度要由读写时序补偿（TI §6.3.1.9：写均衡能纠正的“命令延迟减数据延迟”上限 2500 ps，转引；ST 转引两颗字节组间 ≤ 1300 mil） | 同左 | 转引与推断，**未核实** |
| 软件 | 需要 RK3568 的 DDR 固件对这种拓扑做偏斜补偿：写均衡是否实现、参数是否可配，没有一手资料 | 第 1 节 | **未核实** |
| 官方模板 | Rockchip 对 DDR3 fly-by 要求直接套官方模板（CHK 项 44）；本地没有，要向 Rockchip 索取 | CHK 项 44 | 已核（条目），模板存在与否**未核实** |

## 5. T 型的设计指南

### 5.1 Rockchip 自己的 T 型规则（RK3568 + DDR3）

| 项目 | 原文或读数 | 出处 | 核实 |
|---|---|---|---|
| 适用拓扑 | “For DDR3/DDR3L 4 16bit 2CS, DQ uses T topology (one drive two), CA uses double T topology (one drive four).”（图 2-18：CLK、CMD、CA 一路出来后分叉，Byte0,1 去一颗，Byte2,3 去另一颗，两颗 DDR 框内各有一个箭头端点，分叉点在两颗之间偏中） | HDG 第 18 页 | 已核（页面图） |
| 数据线 | 点对点（HS 第 32 页：SoC → Pkg → Brkout → L1 → SDRAM，没有分支） | HS 第 32 页 | 已核 |
| CLK / 控制 / 命令的结构 | HS 图：SoC → Pkg → Brkout → L1 → 分支点 → L2a、L2b 各到一颗 SDRAM；分支点用小圆圈画，没有标过孔还是走线分叉 | HS 第 33、34 页；HDG 图 3-41、3-43、3-44（第 179 至 181 页） | 已核（页面图） |
| 分支长度 | L2a、L2b 各“Less than 600mil, make sure the traces are as short as possible”；L2a 与 L2b 差“Less than or equal to 20mil” | HDG 表 3-2、3-3、3-4；HS 表 22、23；CHK 项 43 | 已核 |
| 主干（L1）长度 | 没有给上限 | 同上 | 已核（没有） |
| 分叉点位置 | 没有文字规定。图中分叉点在 L1 末端、两颗之间 | 同上 | 已核（没有） |
| 分叉用过孔还是层上走线 | 文件没有写 | 同上 | 已核（没有） |
| 主干与支线所用的层 | 没有 T 型专门的层规定；叠层建议“DDR 信号尽量放 TOP、Signal、Bottom 层”（HDG 第 177 页）；4 层板时 CSn/CKE/ODT 和其他 CA 在底层走 G-S-S-G（HDG 第 180、181 页） | HDG 第 177、180、181 页 | 已核 |
| 过孔数 | 通用规则：每个信号换层过孔控制在 2 个以内（3200 Mbps 下尽量不换层）；DQ 并排换层过孔 ≤ 2（HDG 第 178 页；CHK 项 67）。没有 T 型分叉过孔的专门说法 | HDG 第 178 页 | 已核 |
| 主干 / 支线阻抗 | 单端 50 Ω ±10%、差分 100 Ω ±10%，主干和支线**没有区别**（T 型表里没有 M 段 43 Ω；43 Ω 只出现在 fly-by 的控制线 M 段） | HDG 表 3-2 至 3-4；HS 表 21 至 23；对照 HS 表 25 | 已核 |
| CLK 的 RC | 每路 CLKP、CLKN 各串 49.9 Ω 1%（0402），汇到一颗 100 pF C0G 50 V（0402）接地；图 3-41 画成分支点处的第三条支路（Rtt、Ctt 接地）；文字：“RC circuit is placed at the branch point”；CHK 项 43：“CLKP/N之间的RC电路必须在分支点上”；CHK 项 13：“要求DDR3_CLKP/N之间的增加RC电路，可改善信号质量和降低EMI” | HDG 第 18、179 页；CHK 项 13、43 | 已核（页面图） |
| **文件间不一致 1** | 图 2-19、3-42 里红框注释是 “Place close to CLKP/N signal terminal”（靠近 CLKP/N 信号端），而文字和 CHK 项 43 写“在分支点”。“terminal”是指分支点还是 SoC 端，文件没有解释 | HDG 第 18、179 页 vs CHK 项 43 | 已核（歧义） |
| CKE / CS / ODT | 与 CLK 对齐 < 30 mil（T 型）；也走 L2a/L2b 分支，同样 ≤ 600 mil、互差 ≤ 20 mil；没有 RC；没有串电阻的说法 | HDG 表 3-3；HS 表 22；CHK 项 42 | 已核 |
| 其他 CA | 对 CLK < 600 mil（HS 的写法是 L1 段） | HDG 表 3-4；HS 表 23 | 已核 |
| 串联 0 Ω | DDR3 的 T 型条目**没有**写。DDR4 的 T 型写了：HDG 第 19 页“it is also necessary to connect resistors in series to DDR4 on the branch line, and the series resistor must be placed at the branch point to improve the quality of the clock signal”；CHK 项 15：“由于DDR4 CLK可支持到1600MHz，在分支点串接电阻不能删减，给改善信号质量预留一个手段”。DDR3 的 CHK 项 13、43 没有这一句 | HDG 第 19、20 页；CHK 项 13、15、43 | 已核 |
| 间距与回流过孔 | 通用：CLK 对其他线 ≥ 3 倍线宽、全程包地、地过孔每 200 mil 内一个；CA 之间 ≥ 2 倍线宽；换层处缝合地过孔 30 mil（HDG）/ 25 mil（HS、CHK）内。没有对分叉点的专门间距规定 | HDG 表 3-2、3-4，第 177、178 页；HS 第 23 页；CHK 项 67 | 已核 |
| HDG 与 CHK 不一致处 | ① CHK 项 42（前一份调研核对过）与 HDG 表 3-2 对“CA 对 CLK < 600 mil、CSn/CKE/ODT 对 CLK < 30 mil”一致；② 过孔缝合距离 HDG 写 30 mil、HS/CHK 写 25 mil；③ 参考面边距 HDG/CHK 40 mil、HS 第 28 页 12 mil（前一份调研）；④ RC 位置见上。T 型分支本身的数值（600 / 20 mil）HDG、HS、CHK 三处一致 | 见前一份调研 §3、§4 | 部分转引 |

### 5.2 通用 T 型 / 树形来源

| 来源 | 分叉位置 | 支线上限 | 分支匹配 | 主干与支线阻抗 | 端接 | 速率与负载 | 层、过孔 | 核实 |
|---|---|---|---|---|---|---|---|---|
| **Micron TN-41-13**（Rev. B 08/13） | 第 4 页：“symmetrical tree layout”；图 4 至 6 的示意里：主干 250 mil（50 Ω）、每分支 100 mil 或 125 mil（50 Ω）、末端 DRAM（图为 4 个负载的例子，数字是示意不是规则） | 没有硬上限；“branches … within 1mm within each net” | 第 10 页：“make all related branches match to within 1mm within each net. Different nets may have different branch lengths as long as they are matched within a branch.” “选 1 mm 是任意的” | 图里全部 50 Ω | 四种：树形加 VTT、树形无串阻、树形加串阻（驱动阻抗与串阻之和“slightly less than the trace impedance”）、fly-by；点对点“树形加串阻或不加串阻无需 VTT”。数据线：串阻放传输线中间或用 ODT | DDR3-1333 仿真，一个控制器 + 两至四个负载 | 返回路径问题多靠目检（“Return Path”一节）；过孔数相同或把过孔当长度（约 20 ps/个）、外层比内层约快 10%，这两条数字取自 `research/highspeed-pcb-pitfalls`，本次未重新核对 | 已核（正文引文）；图中数字为示意，未核对页面图；过孔与外层速度两条为转引 |
| **TI SPRABI1D** §3.1.1 | 说 DDR2 用平衡 T，DDR3 不再用；T 的缺点是“multiple stubs and stub lengths”引入偏斜、多负载限制带宽 | 无 | 无 | 无 | 无 | — | — | 已核 |
| **NXP i.MX6 HDG** Rev 3 §3.6.2、§3.6.4、图 3-9 | 4 颗 2 GB 用平衡 T（“Note the balanced T routing.”）；T 型只限 4 颗 | 无（图） | 无具体数字；“Have a balanced routing for the T connection” | 50 Ω 单端、100 Ω 差分，“for the signals” 统一 | “Termination resistors not required.” | 4 颗；§3.6.6 给了 8 层板的 4 颗 T 型布线示例图（TOP、L6、BOTTOM），表 3-5 给了总长（数据 650 至 1030 mil、时钟约 2110 至 2120 mil，是示例） | 避免多次换层、不要跨分割参考面 | 已核（文字）；图中分叉位置与过孔排布未读 |
| NXP i.MX6 按字节组长度表 | 表 3-3：时钟/地址/命令组长度“Clock (min) − 200 mil 至 Clock (min)”，“2.25 inches is recommended”；数据按字节组不长于时钟；控制信号对时钟 ±50 mil；时钟组内 ±5 mil。表格文本被拆行，数值与行的对应把握中等 | — | — | — | — | — | — | 已核（对位中等） |
| **TI AM335x** | 不是 T（见第 2 节） | — | — | — | — | — | — | 已核 |
| **TI AM3x / ST / Intel / AMD** | 见第 2 节：都按 fly-by；Intel（转引）“双 fly-by”含中途分叉 | — | Intel 转引：两分支要等长、分叉前主干长于分支 | — | — | — | — | 转引 |
| **Allwinner / Amlogic / MediaTek** | 没有找到公开的一手 DDR3 布线指南 | — | — | — | — | — | — | **未核实** |
| **JEDEC DDR3 DIMM 原始卡（raw card）拓扑** | DIMM 上 CA/CK 走 fly-by + 在模块上终接，不是 T | — | — | — | — | — | — | **未核实**（没拿到 JEDEC 文件；Micron TN-41-13 第 4 页只作间接旁证） |
| 第三方（Altium、PCBWay 等） | “2^N 颗用双 T”；VTT 端接放在 T 的最远点 | — | — | — | — | 2 至 4 颗两种都可 | — | 搜索摘要，**未核实**（二手） |

### 5.3 参考板里 T 型分叉的实际做法

| 板 | 事实 | 出处 | 核实 |
|---|---|---|---|
| **Rockchip EVB1**（RK3568 + 2 × 16 位 DDR4 96 球，6 层，T 型） | 板文件坐标（mm，y 向下为正）：CLK 的分叉过孔在 (128.93, −77.88)；两颗 DRAM 中心 (131.9, −87.31)、(131.9, −69.02)，球区各约 12.4 × 6.8 mm（A 的球区 y −90.70 至 −83.92）；所以分叉过孔落在两颗之间的走廊里，我按这些数算：离 A 球区边 ≈ 6.0 mm、离 B 球区边 ≈ 5.5 mm（B 的球区边由 A 对称推出，没有逐项核对）。路径：SoC 到分叉过孔 8.4 至 8.8 mm 在 TOP，之后走 L4（10.8 至 11.7 mm），到 DRAM 前 1.9 至 3.9 mm 回 TOP；分支段合计约 13 至 16 mm（约 500 至 610 mil，是我把两个范围端点相加，不是逐网络量值） | `research/ddr-guard-reference-boards` §0、§1；`research/rockchip-official-stackup` §2 | 转引（这两份调研从 `.brd` 读出），**未重新核对** |
| EVB1 的层与过孔 | CA 与 CLK 借内层 L4（约 18 至 20 mm 一段，换层过孔 3 至 4 个）；CLK 过孔 1 至 2 个；信号过孔 孔 0.2 / 盘 0.4 mm；所有过孔全是通孔；板子 200 mm 量级，空间宽松，不是紧凑板的范例 | `research/rockchip-official-stackup` §2.2、§2.3 | 转引 |
| EVB1 分叉处排列 | 分叉过孔旁“三根并排”（CLKP_B 与 CLKP_A 的分叉处，包地状态 SS 6.3%）。**过孔阵列形状、过孔间距、分叉旁回流地过孔的位置：两份调研都没有量出**；全板规律是信号过孔旁最近 GND 过孔中位 0.66 mm（EVB1 CA/数据通用） | `research/ddr-guard-reference-boards` §1、§7 | 转引；分叉点专门数据 **未核实** |
| EVB1 原理图（第 25 页，DDR4） | 每个分支起点一颗 0 Ω 5% 0402：CLKP_A/CLKP_B（R3302、R3303）、CLKN_A/CLKN_B（R3304、R3305）、CKE（R3306、R3307）、CS0n（R3308、R3309）、ODT0（R3310、R3311），共 10 颗；干线 CLK 上 R3300、R3301 各 49.9 Ω 1% 加 100 pF。其他地址线没有这类电阻。为什么留这些 0 Ω：没有文件解释，只有 HDG 第 19 页与 CHK 项 15 对 DDR4 T 型的一句“串电阻改善时钟质量/预留一个手段”。网表里这批电阻有两个 DNP 标记的别处器件（R3314、R3315、R3320），与分支电阻无关 | EVB1 原理图第 25 页（`pdftotext` 读出，位置未用页面图核对）；HDG 第 19 页；CHK 项 15 | 已核（原理图文本）；原因 **未核实** |
| 有 DDR3 的 Rockchip 双颗 T 型参考板 | 没有找到（官方包无 DDR3 模板，EVB1 是 DDR4）。第三方 Radxa ROCK 3A 用 DDR4，其余是 LPDDR4/4X | 前一份调研 §8 | 转引 |
| 开源 RK3568/RK3566 的两颗 DDR3 / DDR4 板，带已发布的布局文件 | 没有找到 | — | **未核实** |
| 开源两颗 DDR3 的 FPGA 板 | ButterStick r1.0（ECP5 + 2 × MT41K64M16，8 层）、Logicbone（ECP5 + 2 × DDR3，8 层）有板文件，已在 `research/bga-stackup-open-designs` 里统计过层数与长度，但**拓扑（T 还是 fly-by）、分叉位置没有分析** | `research/bga-stackup-open-designs` §表 | 未分析，**未核实** |

## 6. 待定点（只列问题，不选）

1. 两颗 16 位 1CS 的 DDR3 在 Rockchip 眼里归哪一档：沿用“4 颗 2CS 的 T”，还是 DDR4 两颗 1CS 的 T（带分支点串联电阻），还是 fly-by 模板。要问 Rockchip FAE，同时问有没有 DDR3 的 2 × 16 位模板（HDG 第 14 页要求兼容 16/32 位的设计用官方模板）。
2. DDR3 的 T 型要不要在分支点留串联 0 Ω（HDG 对 DDR3 没写，对 DDR4 写了，EVB1 DDR4 有 10 颗）。
3. HDG 图 2-19 / 3-42 的 “close to CLKP/N signal terminal” 指分支点还是 SoC 端。
4. RK3568 DDR PHY 对 DDR3 的写均衡支持，以及 rkbin 固件里拓扑相关的配置项。
5. 分叉点的实际几何（过孔阵列形状、间距、旁边回流过孔）在 Rockchip 文件里没有写，EVB1 的 `.brd` 里可以量，但前面两份调研没有量这一项。
6. L 形布局（一颗西、一颗北、地址端朝 SoC 的 A1 角）与 fly-by 链是否兼容，没有来源可查，要用时序预算（第一颗到第二颗的多出长度对 tCK 的比例）和仿真来答。
7. ST AN5122、NXP i.MX6 HDG 的两颗专门章节、JEDEC JESD79-3 的原文没有拿到，若这些要作为依据，需要用户提供 PDF 或有访问权限的人去读。
