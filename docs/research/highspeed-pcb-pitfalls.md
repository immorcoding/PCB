# 高速板 PCB 设计坑单（DDR3 为主）

调研票：[#27](https://github.com/immorcoding/PCB/issues/27)，属于地图 [#26](https://github.com/immorcoding/PCB/issues/26)（RK3568 + 两颗 16 位 DDR3、8 层、0.65 mm 球距 BGA）。日期：2026-11-26。瑞芯微自己的资料由另一张票负责，这里不重复。

## 0. 怎么读这份文件

- 每条写四样：**出处**（文档名、章节或页码、链接）、**数值或做法**、**适用条件**、**对应仓库规则**（`docs/shape/` 的条目号，或 `docs/rule-profiles/C-bga-065.md`；状态分“已有 / 缺失 / 冲突 / 需用户定”）。
- 不同来源说法不一的地方并列写，不替用户挑。第 3 节专门汇总了这些分歧。
- 单位：原文是 mil 的，括号里换成 mm（1 mil = 0.0254 mm）。原文是 ps 的，只在来源自己给了换算时才换；我自己换的写明“我的换算”。
- **核实程度**（第 8 节有清单）：
  - “读原文”：我把 PDF 下载后转成文本逐段读过（TI SPRABI1D、TI SPRAAR7J、TI SPRAAV0A、TI SPRAAG6D、ST AN5122、Micron TN-41-13、NXP AN5097）。
  - “抓取摘要”：网页版文档（Intel/Altera 的 EMIF 手册、AMD 的 UG583 和 UG863、Johnson 的文章、Simonovich 的文章）是用抓取工具取回的摘要，没有逐字对照原页，数字在引用前请抽查。这类条目标了“（摘要）”。
- 速率假设：RK3568 的 DDR3 速率这里没有确认（在瑞芯微那张票里）。下面的数值多数来自 DDR3-1066 到 1600 的文档，换速率要重算。

## 1. 最重要的 10 条坑

| # | 坑 | 数值（出处） | 仓库状态 |
|---|---|---|---|
| 1 | 参考面有缝或有洞：DDR3 的线下面不许有平面分割 | “no splits are allowed under any DDR3 routes”（TI SPRABI1D §6.3.1.3）；离参考面洞边 ≥ 1.5 × 线宽（TI SPRAAR7J §3.2） | 缺失，且与 RTE-5 / PWR-8 有张力，见 H-02 |
| 2 | 换层处没有回流过孔 | 地过孔离信号过孔：≤ 50 mil（1.27 mm）（AMD UG583 / UG863，摘要）；≤ 200 mil（5.08 mm）（TI SPRAAR7J §2.4）；ST 用 100 nF 换层电容（AN5122 §5.6） | RTE-5 有“要配”，没有数值，见 H-01 |
| 3 | 过孔数不一致、数据线过孔多 | 数据线每根最多 2 个、同组数量相同、同字节组走同一层（TI SPRABI1D §6.3.1.6）；每个过孔最多当 20 ps 看（Micron TN-41-13 p.12） | C 档写“3 个”，冲突，见 H-03 |
| 4 | 线距按“线宽”还是“到参考面距离”算，各家不一样 | Intel：DQ、地址边到边 ≥ 3H，时钟 ≥ 5H；TI：中心距 ≥ 5W，含蛇形；ST：边到边 ≥ 3S（S 是到参考面距离）（见 H-04） | RTE-7 的 3H / 5H 按“腿中心距”定义，和 Intel 的“边到边”差一个线宽，需核对 |
| 5 | 等长容差各家差一个数量级 | 字节组内：TI ±10 mil（0.254 mm）；Micron ±0.5 mm；ST ±40 mil（1.016 mm）；AMD ±10 ps（±58 mil，1.47 mm）（见 H-06） | 数值不在规则里，C 档的 50 mil / ±20 mm 是 SDRAM 的值，DDR3 要重定 |
| 6 | 微带和带状线速度不同：同样长度，外层快约 10% | Micron TN-41-13 p.11：外层传播延迟约小 10%；TI SPRABI1D 要求按“等效带状线长度”匹配 | 缺失：RTE-2 / RTE-14 只按几何长度，不分层 |
| 7 | 时钟线必须比选通线长（fly-by 加写均衡） | ST：DQS 比 CK 短 0 到 590 mil（14.986 mm）；Intel：每个器件 CK − DQS > 0（摘要）；NXP（DDR4）：时钟比选通长 | RTE-14 有“方向要求”的说法，没有这条具体内容 |
| 8 | fly-by 的支线（stub）长度和端接位置 | 地址 / 命令支线 < 80 mil（2.03 mm），时钟支线 < 40 mil（1.02 mm）（TI SPRABI1D 表 6-2、6-6）；端接放在最后一颗之后、离终点 ≤ 500 mil（12.7 mm）（§6.2.1） | 缺失；RTE-11 禁线上分叉，与 fly-by 的支线冲突，见 H-07 |
| 9 | VREF 做得不干净 | 精度 VDD/2 ±1%（JEDEC，经 TI SPRABI1D §4.7.4 转引）；每个 VREF 脚旁 0.01 µF + 0.1 µF，源头一个 0.1 µF，线宽 ≥ 30 mil（0.762 mm），离别的网络 ≥ 15 mil（0.381 mm）（§6.3.1.8） | 缺失 |
| 10 | 叠层：相邻信号层、过孔残桩 | Intel：不用相邻信号层；TI SPRAAR7J：相邻信号层互相垂直；数据层靠近底面以缩短过孔残桩（TI SPRABI1D §6.3.1.2） | 缺失；H743 的 L3 / L4 就是相邻信号层 |

## 2. 坑单

### 2.1 回流路径和换参考面（地过孔）

**H-01 换层时给信号一条回流通路**

- 出处与数值，并列：
  - TI SPRAAR7J（2023-02）§2.4 和图 2-11（读原文）：信号全程要保持同一个 GND 参考；换不了就把两层 GND 用过孔连起来，缝合过孔对称放，离信号换层过孔中心 ≤ 200 mil（5.08 mm），“越近越好”。这份文件讲的是 USB3、PCIe 等高速差分，不是 DDR3。
  - AMD UG863（Versal，DDR4 / DDR5，摘要）：信号过孔换层且参考面电压相同时，缝合过孔在 50 mil（1.27 mm）以内；参考面电压不同时，换层处 300 mil（7.6 mm）内放一颗 0.1 µF；每个 fly-by 层间过孔旁 50 mil 内一个地过孔；任何走线离地过孔 ≤ 50 mil。同页给了一组仿真：有缝合过孔眼高 180 mV，没有 99 mV（DDR4 地址线）。
  - AMD UG583（UltraScale，DDR3 / DDR4，General Memory Routing Guidelines 第 11 条，摘要）：“Any signal layer switching via needs to have one ground via within a 50 mil perimeter range.”
  - ST AN5122 Rev 3 §5.6（读原文，4 层板）：信号从顶层换到底层时，在过孔旁放一颗 100 nF，一端接 L2 GND，另一端接 L3 VDD_DDR，“absolutely necessary”；多根线同时换层放不下时，一组过孔共用一颗，“放得下几颗放几颗”。
  - Micron TN-41-13 p.10（读原文）：“If anything is overlooked, it will be the current return path.” 二维板级仿真器假设理想回流，看不出问题，要靠目视检查。
- 适用条件：50 mil 和 200 mil 的差别来自文件针对的速率（DDR4 / DDR5 与 USB3 / PCIe）；DDR3-1066 到 1600 夹在中间，没有哪份文件直接给 DDR3 的数。ST 的做法适用于“信号换层时参考面从 GND 变成电源”的 4 层板；8 层板上换层两端若都是地参考，用地过孔而不是电容。
- 对应规则：**RTE-5** 已有“换参考面的地方配地过孔”，**没有距离数值**，需用户定（建议起点 50 mil，理由：它是 DDR3 / DDR4 文件里唯一直接对 DDR 给出的数，且 0.65 mm 球阵里放得下，放不下的地方单独列出）。**PWR-5**（地用整层加外层铺地、地不走线、焊盘旁直接打孔）与 Micron“VSS 单独过孔、到球的线尽量宽”一致。

**H-02 跨分割和参考面的洞**

- 出处与数值：
  - TI SPRABI1D（2022-07）§6.3.1.3（读原文）：“no splits are allowed under any DDR3 routes”；DDR3 的 IO 电源面在 DDR3 走线区外可以开缝；别的信号不得以 DDR3 的 IO 电源面为参考；必须穿过走线通道的别的信号要放在自己的层上，并用整块地面隔开。
  - TI SPRABI1D §6.3.1.2：IO 电源面可以做地址 / 命令 / 控制线的参考面，条件是电容分布在整个面上给出低阻抗回流。数据线必须“adjacent to a solid ground plane”（§6.3.1.6）。
  - TI SPRAAR7J §2.4、§3.2：线离参考面的洞边 > 1.5 × 线宽；离参考面边缘 ≥ 90 mil（2.29 mm；原文符号在文本提取里丢了，按上下文读作“至少”）；实在要过缝，放 ≤ 1 µF 的缝合电容在过缝处旁边；TI 不建议高速信号以电源面为参考。
  - TI SPRAAG6D（DDR2，C6457）§4.1：每个 DDR2 走线层旁边都要有完整连续的地面；DDR2 区内不许开地面缝；电源面不能当信号回流。
  - NXP AN5097（DDR4，读原文）：不得走过缝和洞；离参考面边缘 30–40 mil（0.76–1.02 mm）；线压在过孔反焊盘上不超过半个线宽。
  - AMD UG863（摘要）：离参考面边缘和洞边 ≥ 30 mil（0.76 mm），出线区例外。
  - ST AN5122 §5.5、§6.5.1（读原文，4 层板）：底层走地址 / 控制线、L3 是 VDD_DDR 整面，必须盖住底层所有 DDR 线；底层这些线的参考面是电源面。
- 适用条件：参考面做电源面还是地面，各家不同（TI 的 DDR3 文件允许地址线以 IO 电源面为参考，ST 的 4 层板必须这样，TI 的高速差分文件和 DDR2 文件不允许）。
- 对应规则：**缺失**：没有一条规则说“DDR 线下面的参考面不能有缝、不能压在电源块之间的缝上”。**PWR-8**（电源层块间留 0.5 mm 缝）会在 8 层板的电源层上做出缝，DDR 线若以那一层为参考就是跨分割，需要在叠层定下来时写明哪些层只当地参考。**RTE-5**“过孔避让连成的槽不设长度上限，BGA 下方更不设”是用户 2026-11-23 定的；上面的来源（离洞边 ≥ 1.5 × 线宽、DDR3 线下无分割）与它有张力，**需用户知情**：这里只报告，不改变用户的决定。

### 2.2 过孔残桩

“残桩”有两种，不要混：**过孔桶残桩**（信号离开过孔后多出来的那段桶），和 **fly-by 支线**（主干到每颗 DRAM 球的那一小段线，见 H-07）。

**H-03 过孔桶残桩和过孔数**

- 出处与数值：
  - TI SPRAAR7J §3.6–3.7（读原文，高速差分，不是 DDR3）：残桩 < 15 mil（0.381 mm），更长的要背钻。
  - TI SPRABI1D §6.3.1.3（读原文，DDR3）：数据组不许有“中点过孔”；同一路径同一段上的线过孔数必须相同；盲孔、埋孔、微孔和背钻在标准速率下“不要求”，可以用来消除残桩。§6.3.1.2：“Data-group routing should be on layers close to the bottom of the board to minimize stubs”（SoC 在顶面时，层越靠底，通孔残桩越短）。§6.3.1.6：数据线每个字节组内每根线过孔数相同，**最多两个**；同字节组走同一层。
  - Micron TN-41-13 p.12（读原文）：匹配的线过孔数尽量相同；一个过孔最多按 20 ps 考虑（含 Z 方向和 LC 延迟）。
  - Simonovich，*Via Stubs – Are They All Bad?*，Signal Integrity Journal，2017-03-10（摘要）：四分之一波长谐振 f₀ = c / (4 · L · √Dk_eff)（c ≈ 11.8 in/ns）；他的例子 270 mil 残桩、Dk_eff 6.16 给出 4.4 GHz 的凹陷；经验：第一个凹陷应落在奈奎斯特频率的第 7 次谐波以上；他明说经验数“不能用来签核”。
  - 我的换算（不是来源的数）：按他的“第 7 次谐波”规则，DDR3-1066（奈奎斯特 533 MHz）允许的残桩约 8–10 mm，DDR3-1600 约 6.5 mm；1.6 mm 左右板厚的通孔残桩最长不到 1.6 mm，远在这个数以内，所以 DDR3 速率下残桩的主要问题是电容和多出来的过孔延迟，不是谐振；背钻对 DDR3 不是必需的（和 TI 的“不要求”一致）。**这是推论，没有 DDR3 专用的残桩数值来源。**
- 适用条件：通孔板（嘉立创没有盲埋孔的叠层）上，从顶面出来的 DDR 线越靠近底层，通孔残桩越短；但 BGA 背面还有去耦电容和 DRAM（若放背面），要和 LAY-5 一起考虑。
- 对应规则：**冲突**：C 档表里“过孔数上限：只对 SDRAM 数据线和时钟设，3 个”，TI DDR3 是数据线 ≤ 2 个。**RTE-5**“过孔数上限只给有时序要求的线”已有，数值按板定（SPEC 第 7.2 节）。“同组过孔数相同”**缺失**（RTE-5 只有上限）。残桩长度和层选择（数据线选靠底层）**缺失**。

### 2.3 串扰和线距

**H-04 线距的依据**

并列（同一个量，各家的写法）：

| 来源 | 写法 | 换算 / 备注 |
|---|---|---|
| Intel EMIF 手册 §2.6.4 Spacing Guidelines（摘要） | DQ / DQS / DM：边到边（air-gap）≥ 3H；地址 / 命令 / 控制：≥ 3H；时钟对之间或时钟对到别的线：≥ 5H；H 是该线到最近回流面的垂直距离 | “These guidelines are recommendations, not hard requirements” |
| TI SPRABI1D §6.3.1.3（读原文） | 中心距 ≥ 5W（含蛇形）；4W 可用但不适合 1066 MT/s 以上；DDR3 线之间另有 ≥ 6W 的隔离；别的信号不进 DDR3 走线通道 | 5W 中心距 = 4W 边到边（我的换算） |
| ST AN5122 §5.1（读原文） | “S-3S”：到参考面距离为 S，邻线边到边 ≥ 3S；有余地就放到 4S、10S；BGA 下面不适用，冲突的线段要尽量短；避免 S-1S | 4 层板，S 是线到参考面的距离 |
| TI SPRAAG6D §6.4（DDR2，读原文） | 地址 / 控制：中心距 ≥ 3w；时钟对到别的线：≥ 4w；别的网络类到地址 / 控制：4w（w 是最小线宽 5 mil） | DDR2 |
| NXP AN5097（DDR4，读原文） | 方案 1（40 Ω，线宽 7–8 mil）：同类 1.5–2.0×，对非 DDR 4×；方案 2（50 Ω，5–6 mil）：同类 3×（5 mil）或 2.5×（6 mil）；时钟对到任何线 ≥ 25 mil（0.635 mm）；蛇形平行段之间 ≥ 25 mil | 倍数的基准在文件里没写清是线宽还是间距，按原文抄 |
| Johnson，*Mitigating Crosstalk*（sigcon.com，摘要） | 有完整参考面时，间距大于 H 后串扰随间距大致平方下降，间距加倍串扰降到约 1/4 | 没有出现“3W”字样；没有查到 3W 规则的一手出处 |
| TI SPRAAV0A §5.3（读原文） | 间距放到最小间距的 2–3 倍，串扰“大幅下降”；每个走线层旁要有整块地面；允许在密集器件的出线区放松 | |

- 适用条件：BGA 出线区里间距由工艺定（C 档 0.09 / 0.09 mm），所有来源都允许放松，但 ST 要求“放松的线段尽量短”。
- 对应规则：**RTE-7 / C 档表**“蛇形腿中心距：时钟 5H、数据 3H”与 Intel 的 5H / 3H 数字一致，但 RTE-7 写的是“腿中心距”，Intel 是“边到边”，相差一个线宽；TI 的 5W 是中心距。H 取 0.1 mm、W 取 0.1 mm 时（举例，不是本板的值），数据线的三种算法折成中心距分别是：RTE-7 的 3H 为 0.3 mm、Intel 的 3H 边到边为 0.4 mm、TI 的 5W 为 0.5 mm：**需要在 SPEC 里写明定义**。“线间距总规则”和“放松段总长上限”**缺失**（现有的是蛇形间距和规则区内的 0.09）。

### 2.4 差分对（CK、DQS）

**H-05 阻抗、耦合、对内偏差、补偿位置**

- 阻抗，并列：
  - TI SPRABI1D（KeyStone）：单端 50 Ω ±5%，差分 100 Ω ±5%（CK 和 DQS）。
  - ST AN5122 §5.3：单端 55 Ω ±10%，差分 100 Ω ±10%。
  - Micron TN-41-13 p.15–16：DQ 总线 40 Ω 附近、驱动 34 或 40 Ω“余量最大”，也可用 45、50、60 Ω；DQS 差分线若与 DQ 同宽，差分阻抗略小于 2 倍单端，造成上升时间差和偏移；若把差分线做细到差分阻抗等于 2 倍单端，则没有偏移；外层与内层飞行时间差约 10%。
  - NXP AN5097（DDR4）：差分 75–95 Ω；单端 40–50 Ω 两个方案。
- 对内偏差：
  - TI SPRABI1D §6.3.1.6、§6.3.1.7：DQS 对、CK 对“length-matched with ±1 mils of each other”（表 6-4、6-6：±1 mil = ±0.0254 mm）。原文措辞没有说清是对内还是对间，表里写的是“Skew between DQS pairs”；读成对内偏差的可能性大，但**没有确认**。
  - AMD UG583 DDR3 SDRAM Routing Constraints（摘要）：dqs_p / dqs_n 与 ck_p / ck_n 对内偏差 2 ps = 12 mil（0.30 mm，基于 169.5 ps/in）。
  - Intel EMIF 手册（摘要）：P 对 N ±2 ps，对与对之间 ±5 ps，平行布线。
  - NXP AN5097（DDR4）：时钟 P–N ±5 mil（0.127 mm）；DQS 对 ±5 mil。
  - **ST AN5122 §5.2：“Intra-pair length equalization is not allowed”**；对内间距保持不变；对的长度取 N 和 P 的平均值（读原文，没有说明原因）。这和上面几家直接冲突，或者是指“不单独给一根补长而破坏间距”，原文没有解释，**不要自己挑**。
- 补偿位置：TI SPRAAR7J §2.3 和图 2-5（读原文）：对内补偿用蛇形，“尽量靠近失配的一端”；§3.3：差分对出 BGA 在离封装 0.25 in（6.35 mm）内完成，偏离对称的段要尽量短；§3.11：弯角 > 135°，图上标了 1.5 × 和 5 × 线宽，图的含义文本里读不出来。
- 其他：
  - 过孔：每个成员过孔数相同、尽量等间距（TI SPRAAR7J §3.9）；P 和 N 不要分到两层，选通对走在和它那一字节组同一层（NXP AN5097）；字节组数据线、DQS 同层（AMD UG583 第 9 条，摘要）。
  - 线宽：出 BGA 后保持线宽不变（TI SPRAAR7J §3.2）。
  - 玻纤编织：差分对两条线下面的玻纤和树脂比例不同会产生对内偏差（TI SPRAAR7J §2.1）；办法有旋转图形 10°–35°、走之字形、选 1080 / 2116 这类更密的玻纤布。TI 的例子是 USB3 速率，DDR3 速率下是否要紧**没有来源**。
- 适用条件：几家的对内容差差一个数量级（0.0254 mm 到 0.30 mm），与速率和对内走线长度有关；需要用 RK3568 的时序预算定。
- 对应规则：**RUL-3** 已有“按板厂叠层算差分阻抗，建网络类”；差分对的对内间距、对内等长、同层、过孔对称、出 BGA 距离**都缺失**，地图里“差分对布线、对内等长”新工具清单要补这些口径；仓库里对内等长目前只有 A 档的 USB2 一例，用 `(constraint skew …)` 加 `(within_diff_pairs)`（见 `docs/rule-profiles/A-general.md` 第 26 行）；RTE-2 说的“等长不用 skew”针对的是组间等长，两者不矛盾。**两家（TI、ST）在“对内补偿的做法”上互相冲突**，建议地图里原型先按 TI 做，同时记下 ST 的说法让用户定。

### 2.5 等长

**H-06 分组、容差、方向、长度的计法**

- 分组：
  - 按字节组（DQ[7:0]、DM、DQS 对）分，地址 / 命令 / 控制与时钟成另一组：TI SPRABI1D §6.3.1.3 表 6-1；Intel（摘要）；NXP AN5097；ST AN5122 §6.1–6.2。
  - ST AN5122 §6.1（读原文）：两颗 16 位 DDR3 用 fly-by 时，“不要对所有字节用同一个板上等长”，第一颗的两个字节一起匹配，第二颗的两个字节一起匹配；第二颗的字节组与第一颗的字节组之间差 ≤ 1300 mil（33.02 mm）；地址 / 命令、CK 同样两颗之间 ≤ 1300 mil（§6.3）。
- 容差（字节组内的数据线）：
  - TI SPRABI1D 表 6-4：同字节组 ±10 mil（±0.254 mm）。
  - Micron TN-41-13 p.10：数据位周期的 1%（±0.5%）：800 MHz 时钟下 ±0.5 mm；10 ps 约 1.5 mm（60 mil，内层 6.5 ps/mm）。他们明说数值是任意取的，“有不确定因素时取更紧的”。
  - ST AN5122 §6.1：DQ、DM 对 DQS ±40 mil（±1.016 mm）。
  - AMD UG583（摘要）：DQ / DM 对 DQS ±10 ps = ±58 mil（±1.47 mm）；例子里写 ±5 ps = ±29 mil。
  - Intel（摘要）：字节组内 ±10 ps，从 FPGA 封装球到 SDRAM 封装球量；“不要指望 FPGA 帮你纠超过 20 ps 的数据组偏差”；换算：按 Micron 的 6.5 ps/mm，10 ps 约 1.5 mm（我的换算）。
  - NXP AN5097（DDR4）：数据线对其选通线 20 mil（0.508 mm），1600 MT/s 以上 ±5 mil（0.127 mm）。
- 容差（地址 / 命令 / 控制对时钟）：
  - TI SPRABI1D 表 6-2、6-3：每颗 SDRAM 分段对时钟 ±20 mil（±0.508 mm）；支线之间 ±10 mil（0.254 mm）。
  - ST AN5122 §6.3：地址 / 控制比 CK 短 0 到 40 mil（1.016 mm）。
  - Micron TN-41-13 p.10：每个网络的分支之间 1 mm 内。
  - AMD UG583（摘要）：±8 ps = ±47 mil（±1.19 mm）。
  - Intel（摘要）：每个分立器件处对时钟 ±20 ps（约 3 mm，我的换算）。
  - NXP AN5097（DDR4）：对时钟 ±10 mil；时钟对对地址 / 命令 / 控制 25 mil。
- 方向和总长：
  - ST AN5122 §6.1：DQS 比 CK 短 0 到 590 mil（14.986 mm），CK 必须最长；§6.3：CK 最长 4.72 in（12 cm）。
  - Intel（摘要）：每个器件 CK_i − DQS_i > 0（写均衡需要）；CK + DQS 在各组之间的总偏差 < 1 tCK；第一颗到最后一颗的飞行时间差 < 0.69 tCK（DDR3-1066 约 1.29 ns，按 6.67 ps/mm 约 190 mm，我的换算，所以 ST 的 33 mm 严得多）；Intel 的最大走线长度：地址 / 命令 / 控制 / 时钟 FPGA 到第一颗 7 in，DQ / DQS 到第一颗 5 in。
  - AMD UG583（摘要）：地址 / 命令 / 控制总长上限 6.15 in（1 个负载）到 12.15 in（9 个负载）；数据 7.0 in。
  - TI SPRABI1D §6.3.1.9：写均衡能纠的“命令延迟 − 数据延迟”上限 2500 ps，不随速率变，反相时钟时减半个周期。
- 长度怎么计：
  - 计入封装内引线：ST（“substrate length + via length + board track length”）、Intel（800 MHz 以上）、AMD（取封装延迟的中值）。
  - 过孔数相同或把过孔当长度（Micron 最多 20 ps / 个，TI 要求数量相同）。
  - 微带与带状线：Micron p.11：外层大约快 10%；TI SPRABI1D §6.3.1.3：“All length-matching is based on an equivalent stripline length”，长线都应走带状线。NXP（DDR4 8M Nano 帖子）：用延时匹配，不用物理长度。AMD：169.5 ps/in（6.67 ps/mm）基于它的叠层，别的叠层要换算。
- 蛇形：
  - ST AN5122 §5.2 和图 10：**不推荐 serpentine**（会引起“正交传播”，信号完整性变差），优先用“switchback”图形；图形内部同样遵守 S-3S（图本身是图片，没读到具体形状）。
  - NXP AN5097（DDR4）：并行蛇形段之间 ≥ 25 mil（0.635 mm）。
  - TI SPRABI1D：中心距 ≥ 5W，含蛇形。Intel：3H / 5H。
  - Johnson，*Serpentine Delays*，EDN 2001-02（摘要）：耦合的短回折会让延迟比几何长度小，最多是近端串扰系数的 2 倍（一个短回折），蛇形整体最多 4 倍；例子 8 mil 线 / 8 mil 间距 / 离参考面 5 mil，NEXT 约 6%，所以最多约 12% 和 24%（后两个数是摘要抓取时的换算，未核对）；耦合段长度超过上升沿约 1/3 的往返延迟就开始畸变，1 ns 上升沿大约 1 in 单程，100 ps 约 0.1 in；建议避免长的耦合回折。**没有查到蛇形振幅的下限或摆幅与间距比例的来源。**
- 引脚交换：TI SPRABI1D：地址线不能交换，同字节组内数据位可交换；NXP（DDR4）：位交换只在 nibble 内、字节交换任意；ST：4 个字节可互换，字节内的位可互换。具体到 RK3568 看瑞芯微票。
- 适用条件：DDR3-1066 到 1600；字节组内容差这里的取值最松 1.47 mm、最紧 0.0254 mm（差分）/ 0.127 mm（NXP DDR4），都是文件里的数，不是推荐。
- 对应规则：**RTE-14** 已有“按字节通道分组、地址命令另设窗口、先算时序预算”，与 ST / TI / Intel 一致；**RTE-2 / RTE-15** 已有“按量预留补线空间”；**RTE-7**（圆弧蛇形）与 ST“不推荐 serpentine”**冲突**（ST 的 switchback 没读到图，不能判断两者是不是同一个东西）；**缺失**：按层速度补偿（外层 vs 内层）、过孔长度计入、封装引线计入（地图工具清单里已有这一项）、方向要求的具体值（CK 比 DQS 长）、两颗 fly-by 之间的相对长度上限、总长上限。C 档表里“数据线组内 50 mil”“地址命令对时钟 ±20 mm”是 SDRAM 的值，**与上面所有 DDR3 的值都差一个数量级**，C 档表自己已写“换接口（DDR）时逐项重定”，所以不算冲突，但不能照搬。

### 2.6 T 型和 fly-by 拓扑

**H-07 拓扑选择和支线**

- 并列：
  - TI SPRABI1D §3.1：DDR2 用平衡 T；DDR3 改成 fly-by，因为 T 有多段支线、skew 不一；fly-by 的代价是每颗器件的延迟不同，靠读写均衡补；TI **“不建议在没有均衡的情况下用 DDR3”**（§6.2.2：那样“只是一个有 DDR2 缺点的 DDR2 布局”）。
  - ST AN5122 §2.1、§3.1–3.2：两颗 16 位 DDR3 用 fly-by；单颗用点对点（每根地址线串 33 Ω、不端接）。
  - Micron TN-41-13 p.16–20（读原文）：点对点系统里地址 / 命令 / 控制的四种终端方案：树形带 VTT 电阻、树形不加串阻、树形加串阻、fly-by。表 8（DDR3-1333 仿真）：树形 VTT 抖动 5 ps、电压余量 140 mV；树形不加串阻 28 ps / 510 mV；树形加串阻 33 ps / 560 mV；fly-by 5 ps / 100 mV。树形加串阻或不加串阻“在不需要 VTT 电源的情况下提供可接受的信号质量”；fly-by“布线容易，但要 VTT 电源和端接，并在时钟和数据之间引入 skew”。树形的各分支要 1 mm 内匹配。写均衡“只有在 4 颗以上同侧、时钟菊花链时才有用”（p.13）。Micron 写明仿真值“不是推荐”，要自己仿真。
  - Intel EMIF 手册 §2.6.5.1（摘要）：用 ×16 器件，少负载；支线越短越好；第一颗到最后一颗飞行时间差 < 0.69 tCK；“双 fly-by”（中途分叉）会多一个不连续点，两个分支要等长，分叉前的主干要比分支长；一切要仿真。
  - AMD UG583（摘要）：DDR3 章节只有 fly-by；T 型分支只出现在 QDR II+ 章节。
  - NXP AN5097（DDR4）：地址 / 命令 / 控制 / 时钟用 fly-by，从 0 号芯片到 n 号芯片，终点接端接电阻。
- 支线长度：TI SPRABI1D 表 6-2、6-3、6-6：地址 / 命令 / 控制支线 < 80 mil（2.03 mm）、支线之间 ±10 mil（0.254 mm）；时钟对支线 < 40 mil（1.02 mm）。
- 适用条件：两颗 16 位 DDR3 时，Micron 的“树形”是点对点（一个控制器两颗器件）里被评估过的方案；TI、ST、Intel、AMD 都按 fly-by 写。RK3568 自己推荐哪种在瑞芯微那张票里。
- 对应规则：**冲突**：**RTE-11** “分叉只放在焊盘中心；线上的 T 型、Y 型分叉和过孔处的 90° 转弯要么改掉，要么逐条解释”。fly-by 的每颗器件处、T 型的分叉点，都是主干上的分叉（通常落在过孔上）；这条规则要给它们开例外，或在 SPEC 里逐条解释。支线长度、支线偏差**缺失**。分叉拓扑是否要新工具是地图 #26 的待定项，这份调研的结论是“来源两边都有，取决于 SoC 的写均衡能力和是否两颗以上”，不替用户选。

### 2.7 端接和 VREF

**H-08 端接、VTT、VREF**

- 地址 / 命令 / 控制端接，并列：
  - TI SPRABI1D §6.2.1、§6.2.5（读原文）：fly-by 终点放 39–42 Ω 接 VTT（首选 39 Ω，1%），端接放在最后一颗 SDRAM 之后，走线到电阻 ≤ 500 mil（12.7 mm）；时钟每条用 39 Ω 串 0.1 µF 接 VDDQ；“外部端接可能不需要，只有完整仿真才能确定”；DDR3 不需要数据线串阻或主动端接；元件 1%，0402 或更小。
  - ST AN5122 §3.1：fly-by 的地址 / 命令总线 56 Ω 接 VTT（原文的 Ω 符号在文本提取里丢了，按上下文读作 56 Ω）；差分时钟用一颗 100 Ω 跨在 CLK_N / CLK_P 之间。单颗点对点：不端接，33 Ω 串阻放在 SoC 一侧。
  - Micron TN-41-13：点对点时可用串阻代替 VTT；写均衡可以不依赖；DDR3 数据线靠片上端接（ODT），不需要外部。
  - TI SPRAAV0A（DDR2 年代的文件）：片上端接以外的端接对 EMI 有用；可以先留位置，焊 0 Ω，EMI 测试后再决定。
- VTT：
  - TI SPRABI1D §6.3.1.8：VTT 稳压器靠近 SDRAM 的 VTT 脚，VTT 岛放在元件面信号层；每个 VTT 脚旁至少一颗 0.1 µF，岛上至少一颗 10–22 µF 低 ESR 陶瓷；§8.1.2：VTT 噪声“不能超过 ±2% 或 1.5 mV”（原文这个数字自相矛盾，0.75 V 的 2% 是 15 mV，不是 1.5 mV，原文可能是 15 mV，**没有确认**）。
  - ST AN5122 §6.5.2：VTT 当电源看；因为 VDD_DDR 整面占着 L3，VTT 在底层做成岛；每两颗 RTT 电阻一颗高频电容；VTT 稳压器靠近 RTT；岛周围留间距。
  - NXP AN5097（DDR4）：每 4 颗电阻至少一颗低 ESL 或两颗普通去耦；岛两端各一颗 4.7 µF 和一颗 47–220 µF；岛放在存储通道末端；岛的线约 150 mil（3.8 mm）宽。
- VREF：
  - 精度：TI SPRABI1D §4.7.4：JEDEC 要求 VDD/2 ±1%（1.5 V 时 0.7425–0.7575 V，转引自 JESD79-3C p.129；我没有读 JEDEC 原文），分压电阻要优于 1%。§8.1.1：VREFCA 和 VREFDQ 都从 VDD/2 来，噪声峰峰“不能超过 ±2% 或 1.5 mV”（同样的数字问题）。
  - 去耦和走线：TI §6.3.1.8：VREF 在 SDRAM 处去耦，不在源头；每个 VREF 脚一颗 0.01 µF 加一颗 0.1 µF（0402 或更小），源头一颗 0.1 µF；到 VREF 脚的线宽至少 30 mil（0.762 mm）、越短越好；离别的网络至少 15 mil（0.381 mm）；VREF 全部走顶层，用地隔离。
  - ST AN5122 §3.4：每颗器件各有独立的 VREFCA、VREFDQ 发生器：2 kΩ ±1% 分压加本地 100 nF，尽量靠近对应的球；或者外部芯片出一路共用，每颗本地 100 nF。
  - NXP AN5097（DDR4）：离别的线 20–25 mil（0.51–0.64 mm），可以的话两侧加地线；源头和每个目的脚各 0.1 µF；分压两颗电阻同值、1%。
  - TI SPRAAG6D（DDR2）：线宽 20 mil；VREF 上 4–5 颗去耦。
- ZQ 和杂项（ST AN5122 §3.3，读原文）：每颗 DDR 和 SoC 的 ZQ 各一颗 240 Ω ±1% 到 GND，线尽量短、远离干扰源；RESET# 和 CKE 各 10 kΩ 下拉。
- 对应规则：**缺失**：布局和走线规则里没有端接、VTT、VREF 的任何条目。`rules-and-schematic.md` 的原理图完成标准（我没有逐条核对）是否覆盖，**没有核查**。

### 2.8 去耦和电源完整性

**H-09 去耦**

- 出处与数值：
  - Micron TN-41-13 p.8–10（读原文）：DRAM 片上有电容，不必每个电源脚对配一颗；每侧四颗电容，一颗在球阵上四分之一处居中、一颗在下四分之一处居中；离器件“尽量近”，过孔放在电容靠器件的一侧；核心用 0.1 µF 或 1.0 µF（电源在同一块板上且别处电容多用 0.1 µF，复杂或电源在别的板用 1.0 µF）；IO 侧要的是短路径和足够多的过孔；VSS / VSSQ、VDD / VDDQ 用单独过孔是好习惯但不是硬性；过孔到球的线越宽越好；电容处可以多孔。
  - ST AN5122 §5.7–5.8（读原文）：大电容 10–100 µF 不必近；高频电容必须尽量靠近电源球；“少而位置最优”好过多而位置差。电流环面积：顶层电容走直接电源线，面积 0.1 × D（D = 5 mm 时约 0.5 mm²）；背面电容在球正下方，面积 1.5 × D（D = 1 mm 时约 1.5 mm²）；原文结论：顶层 15 mm 外的电容与背面球正下方的电容效率相当。这是 ST 4 层板的几何，不能直接搬到 8 层板（L2 到顶层的距离不同）。
  - TI SPRAAV0A §5.4、FAQ（读原文）：用许多个小电容并联，每个封装越小电感越小；去耦过孔做大（只要不切断平面）；多留电容焊位，事后加焊位几乎不可能；表里给最少个数和到器件的最大距离（针对器件的数据手册）。
  - TI SPRABI1D §6.3.1.3：去耦电容的线宽尽量宽、支线尽量短；SoC、SDRAM 和去耦电容共用同一个地参考。§8.1：SoC 和 SDRAM 用同一路 1.5 V，容差 ±5%。
  - Intel（摘要）：每个 VDDQ 脚一颗 0.1 µF 加一颗 0.01 µF；VTT 每隔一个脚一颗 0.1 µF（摘要里写的是“0.1F”，应为 µF）。
  - ST AN5122 §6.5.1：VDD_DDR 面到稳压器、SoC 和每颗存储器的连接要用多个过孔。
- 适用条件：个数和容值要看 RK3568 和所选 DDR3 颗粒的设计指南，这里没有 RK3568 数据。
- 对应规则：**LAY-2**（去耦到电源球的距离上限 2.5 mm，大电容不设上限）、**LAY-5**（BGA 背面去耦用小封装，贴着过孔）已有；ST 的环面积对比为“背面球下去耦”提供了依据（背面球正下方的电感大于顶层近处，但 BGA 约束下常常只有这一种位置）；TI 要求去耦线宽尽量宽、Micron 要求线宽尽量宽：C 档的 `stub_max`（0.7 mm）约束了长度，**线宽没有规则**；VTT 去耦和 VREF 去耦**缺失**（H-08）。

### 2.9 叠层选择

**H-10 叠层**

- 出处与数值：
  - TI SPRABI1D §6.3.1.2（读原文）：上下对称；高速信号层夹在地面之间；IO 电源面可以当地址 / 命令 / 控制的参考；电源和地尽量整块无缝，DDR3 走线区外可以开缝；一般 50 Ω；至少四个走线层：两层地址 / 命令 / 控制，两层数据；数据层靠近底面以缩短残桩；“终端应用板通常至少 8 层，高性能板 12 层以上”。
  - TI SPRAAR7J §3.12（读原文）：至少 6 层；6、8、10 层的示例叠层；脚注：直接相邻的信号层“Route directly adjacent signal layers at a 90° offset to each other”；§3.2：差分对尽量走顶层或底层、旁边有地层，**TI 不建议高速差分走带状线**（这一句与 TI SPRABI1D“长线应走带状线以降低 EMI 和 skew”针对的对象不同，一个是 USB3 / PCIe 等差分，一个是 DDR3 单端和 DDR3 差分；两者并列）。
  - TI SPRAAV0A、SPRAAG6D：每个 DDR 走线层旁边都要有完整的地面；两个走线层可以共用一个地面（一个在上、一个在下）；六层板是最低叠层。
  - Intel EMIF 手册（摘要）：避免相邻信号层，走线放在地层或电源层之间；信号层靠近地和电源。
  - AMD UG863（摘要）：不要用两个相邻的走线层；fly-by 信号最多用两层。
  - ST AN5122 §5.4（读原文，4 层板）：顶层给最敏感的线（数据），L2 整块地，L3 整块 VDD_DDR，底层给地址 / 控制线。
  - Micron TN-46-14（六层叠层，Rev. B 2008）：**我没有拿到原文**，只在搜索结果里看到它存在。
- 适用条件：8 层、嘉立创、无盲埋孔时，层间距由板厂叠层定（C 档表：JLC06161H-3313E 是六层）。
- 对应规则：**缺失**：没有“相邻信号层必须互相垂直或避免”的规则；C 档表第 57 行的 H743 板层序是 信号 / 地 / 信号 / 信号 / 电源 / 信号，L3 和 L4 是相邻信号层，按 Intel / AMD / TI 的说法是被警告的结构（那块板的 SPEC 里是否写了垂直走向，我没有查）。8 层 DDR3 板的叠层要在此之前定，且“哪些层只当参考、哪一层是电源块”要和 H-02 一起写进 SPEC。

### 2.10 BGA 扇出

**H-11 扇出**

- 出处与数值：
  - TI SPRAAV0A FAQ（读原文）：BGA 焊盘尺寸要和板厂、贴片厂商量，“推荐的焊盘尺寸一般不等于球径”，面积与封装焊盘相近；出线区允许放松线距。
  - TI SPRAAG6D §5：DDR2 的例子，焊盘 14 mil、阻焊开窗 20 mil；出线过孔 8 mil 孔 / 18 mil 盘，狗骨出线（这是 0.8 mm 球距一类 BGA 的 DDR2 年代，仅供参考）。
  - TI SPRABI1D §6.3.1.3：BGA 出线用的微带段要尽量短，长线走带状线。
  - AMD UG583（摘要）：出线按“焊盘之间过两根线”假设；只过一根时可以用 39 Ω 的线；两根时线要短以减少耦合。数据线和选通线同组同层，出线区例外。
  - NXP AN5097（DDR4）：先走最外边（最长）的字节组，因为它决定内侧字节组要补多少；相邻字节组交替放到不同层，便于出线；布线顺序：数据、地址 / 命令、控制、时钟、电源。
  - TI SPRAAR7J §3.3、§3.8：差分对出 BGA 在 0.25 in（6.35 mm）内完成；高速信号的过孔反焊盘越大越好（30 mil = 0.76 mm 给出明显好处）。
  - ST AN5122 §5.1：S-3S 在 BGA 下面不适用，冲突的段要尽量短。
- 适用条件：C 档是 0.65 mm 球距、0.30 / 0.15 mm 过孔、0.09 mm 线；TI 30 mil 的反焊盘在这个球阵里放不下，所以只能理解成“出了球阵再这样”。
- 对应规则：**RTE-13**（线序草图含 BGA 出线、等长补线区）、**C 档“数值”表**（区内 0.09 / 0.09、过孔 0.30 / 0.15）已有，与上面“出线区放松”一致；**缺失**：“放松线段总长要尽量短”的检查；NXP 的“先走最长字节组”和“相邻字节组交替层”是线序经验，RTE-13 的“确定性脚本分配”没有写这些，可以作为分配脚本的约束候选，不替用户定。

## 3. 来源互相不一致的地方（汇总）

| 项目 | 说法 A | 说法 B | 说法 C |
|---|---|---|---|
| 换层地过孔距离 | ≤ 50 mil（AMD UG583 / UG863） | ≤ 200 mil（TI SPRAAR7J） | 用 100 nF 换层电容，不用过孔（ST AN5122，4 层板、参考面变电源） |
| 差分对内补偿 | 用蛇形，靠近失配端（TI SPRAAR7J §2.3） | 对内不许补，用 N、P 平均长（ST AN5122 §5.2） | — |
| 差分对内偏差 | ±1 mil（TI SPRABI1D，措辞含糊） | 2 ps = 12 mil（AMD） | ±5 mil（NXP DDR4） |
| 线距 | 边到边 3H / 5H（Intel） | 中心距 5W、4W 不超 1066 MT/s（TI） | 边到边 3S（ST）；DDR2：中心距 3w / 4w（TI SPRAAG6D） |
| 蛇形 | 间距 ≥ 25 mil（NXP DDR4）；≥ 5W 含蛇形（TI） | 不推荐 serpentine，用 switchback（ST） | 耦合的回折会让延迟变小，长度别超 1/3 上升沿往返（Johnson，摘要） |
| 字节组内容差 | ±10 mil（TI）；±0.5 mm（Micron） | ±40 mil（ST） | ±10 ps ≈ 1.47–1.5 mm（AMD、Intel） |
| 地址对时钟 | ±20 mil（TI）；0 到 40 mil 短（ST） | ±8 ps 约 1.19 mm（AMD）；±20 ps 约 3 mm（Intel） | 分支 1 mm（Micron） |
| 参考面 | 电源面可做地址线参考（TI SPRABI1D、ST 4 层板） | 电源面不能当回流（TI SPRAAR7J、TI SPRAAG6D DDR2） | — |
| 端接电阻 | 39–42 Ω 接 VTT（TI） | 56 Ω 接 VTT（ST） | 不端接 / 串阻（ST 单颗、Micron 点对点） |
| 拓扑（两颗） | fly-by（TI、ST、Intel、AMD、NXP） | 树形也可，抖动更大、不需要 VTT（Micron，点对点） | — |
| 阻抗 | 单端 50 Ω ±5%、差分 100 Ω ±5%（TI） | 55 Ω ±10%、100 Ω ±10%（ST） | DQ 40 Ω 附近余量最大（Micron）；40 或 50 Ω 两个方案（NXP DDR4） |
| VREF 线宽和间距 | 线宽 ≥ 30 mil，间距 ≥ 15 mil（TI） | 间距 20–25 mil（NXP DDR4） | 线宽 20 mil（TI DDR2） |
| 时钟与选通长度 | DQS 比 CK 短 0–590 mil（ST） | CK − DQS > 0（Intel、NXP） | — |
| 高速差分走带状线 | TI SPRAAR7J：不建议 | TI SPRABI1D：长线应走带状线 | 对象不同（SerDes 差分与 DDR3） |
| 过孔残桩 | < 15 mil，更长要背钻（TI SPRAAR7J，SerDes） | 标准速率不要求背钻（TI SPRABI1D，DDR3） | — |

## 4. 与仓库规则冲突或缺失（汇总）

**冲突或张力（需要用户知情或决定）**

1. **RTE-11**（分叉只放焊盘中心，线上的 T 型和 Y 型分叉要么改掉要么逐条解释）与 fly-by 的支线和任何 T 型拓扑冲突（H-07）。
2. **C 档表“过孔数上限 3 个”**与 TI DDR3 数据线“最多 2 个、同组相同”（H-03）。
3. **RTE-7 / C 档“蛇形腿中心距 3H / 5H”**与 Intel 同数字不同定义（边到边），且与 ST“不推荐 serpentine”冲突（H-04、H-06）。
4. **RTE-5 的“平面槽不设长度上限，BGA 下方更不设”**（用户定）与 TI“DDR3 线下无分割”“离洞边 ≥ 1.5 × 线宽”、AMD / NXP“离参考面边缘 30 mil 以上”有张力；只报告，不改（H-02）。
5. **PWR-8**（电源层块间 0.5 mm 缝）和 DDR 线的参考面：若 DDR 线以电源层为参考就是跨分割（H-02）。
6. **C 档表的等长数值**（数据 50 mil、地址对时钟 ±20 mm）是 SDRAM 的值，DDR3 来源给的是 0.0254–1.5 mm（数据）、0.5–3 mm（地址）；C 档表已声明换接口要重定，所以这是“待重定”，不是违规（H-06）。

**缺失**

1. 换层地过孔的距离数值（RTE-5 只有“要配”）。
2. DDR 线下参考面完整性（无缝、无洞、离洞边距离）、哪些层只当地参考。
3. 过孔残桩长度、走线层选择（数据靠底层）、同组过孔数相同。
4. 微带 / 带状线速度补偿（外层快约 10%）、过孔长度计入、封装引线计入（工具清单已有后者）。
5. fly-by 支线长度（< 80 mil 地址、< 40 mil 时钟）和支线偏差；两颗器件之间的相对长度上限；总长上限；CK 比 DQS 长的具体范围。
6. 差分对：对内间距恒定、对内偏差、同层、过孔对称、出 BGA 距离、对间距。
7. 端接、VTT 岛及其去耦、VREF 的精度、去耦、线宽、间距、层；ZQ、RESET#、CKE 的处理。
8. 相邻信号层的规则；叠层对称。
9. 总线距规则和“出线区放松线段要尽量短”的检查。
10. 去耦线宽（现有的只有距离和支线长度）。

**已有且与来源一致**

- RTE-14（按字节通道分组、先算时序预算、方向要求和总长上限一起写）；RTE-2 / RTE-15（按量预留补线空间）；RTE-13（线序草图含补线区）；PWR-5（地不拉线、焊盘旁打孔）；LAY-2 / LAY-5（去耦距离和背面小封装）；RUL-3（按叠层算差分阻抗）；C 档区内 0.09 / 0.09 与“出线区允许放松”。

## 5. 没查到、或来源不够硬的部分

- **没有拿到原文**：Micron TN-46-14（点对点系统的端接、布局、走线，含六层叠层）；Micron TN-41-08；JEDEC JESD79-3 本身（VREF ±1% 是 TI 转引的）；NXP 的 DDR3 / i.MX 硬件开发指南（NXP 搜到的是 DDR4 的 AN5097 和 LPDDR4 的摘录）；TI SPRABN2（AM335x 的 DDR 指南，只读到通用部分）；Micron TN-41-13 我读的是 Hackaday 上的转存（https://cdn.hackaday.io/files/19354828041536/tn4113_ddr3_point_to_point_design.pdf），没有对照 micron.com 的官方文件。
- **只有摘要，没有逐字核对**：Intel / Altera EMIF 手册的间距、长度匹配、fly-by 页（我取到了 3H / 5H、±10 ps、±20 ps、0.69 tCK，Intel 摘要里“差分对之间至少 2 倍线宽、GSSG 布局”一条不确定，没写进上面的表）；AMD UG583 的 DDR3 约束页和通用约束页（取到前 14 条，其余没读）、UG863；Johnson 的两篇文章；Simonovich 的文章。
- **没有找到一手出处**：“3W 规则”本身（Johnson 的文章讲的是“间距加倍、串扰降到 1/4”，没有提 3W；Altium、Cadence 的页面提到 3W，但它们不是芯片厂或原作者）；蛇形的振幅或高度与间距的比例；DDR3 专用的过孔残桩长度限值（只有 SerDes 的 15 mil 和 DDR3 的“不要求背钻”）；DDR3 BGA 出线（0.65 mm 球距）的专用做法；地过孔距离在 DDR3 上的专用数值；哪个来源首次提出“VTT 噪声 ±2% 或 1.5 mV”里 1.5 mV 与 15 mV 的问题（TI 原文自相矛盾）。
- **文本提取里丢了的符号**：TI SPRAAR7J 中“离参考面边缘 90 mil”前的比较符、ST 的 56 Ω 的 Ω 符号；已按上下文读，标了“按上下文”。
- **图读不到**：ST AN5122 图 10（等长图形）、TI SPRAAR7J 图 3-10（弯角的 1.5× 和 5×）、AMD 的 fly-by 终端图（图里才有支线长度和电阻值）。
- 搜索结果里有一条把“3/Gbps、0.3/Gbps 残桩规则”归给 Bogatin，我取回 Simonovich 的文章后没有找到这两个数，**没有采用**。

## 6. 来源清单

读原文：

- TI SPRABI1D，*DDR3 Design Requirements for KeyStone Devices*，2018-01，2022-07 修订：https://www.ti.com/lit/pdf/sprabi1
- TI SPRAAR7J，*High-Speed Interface Layout Guidelines*，2018-11，2023-02 修订：https://www.ti.com/lit/pdf/spraar7
- TI SPRAAV0A，*Understanding TI's PCB Routing Rule-Based DDR Timing Specification*，2008-07：https://www.ti.com/lit/pdf/spraav0
- TI SPRAAG6D，*TMS320C6457/TCI6484/TCI6487/88 DDR2 Implementation Guidelines*，2006-12，2010-01 修订：https://www.ti.com/lit/pdf/spraag6
- ST AN5122 Rev 3，*STM32MP1 Series DDR memory routing guidelines*：https://www.st.com/resource/en/application_note/an5122-stm32mp1-series-ddrmemory-routing-guidelines-stmicroelectronics.pdf
- Micron TN-41-13 Rev B 08/13，*DDR3 Point-to-Point Design Support*（转存）：https://cdn.hackaday.io/files/19354828041536/tn4113_ddr3_point_to_point_design.pdf
- NXP AN5097 Rev 1 2016-07，*Hardware and Layout Design Considerations for DDR4 SDRAM Memory Interfaces*（DDR4，只作参考）：https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/imx-processors/188384/1/AN5097.pdf

摘要核实：

- Intel / Altera，*External Memory Interface Handbook Volume 2*（683385）§2.6：https://docs.altera.com/r/docs/683385/current ，子页：[Length Matching Rules](https://docs.altera.com/r/docs/683385/current/length-matching-rules?contentId=~Zjrw1_IWcjmkPOeb~BEMA)、[Spacing Guidelines](https://docs.altera.com/r/docs/683385/current/spacing-guidelines?contentId=jJ6sSOHplI26bDPq9Hf0ew)、[Fly-By Network Design](https://docs.altera.com/r/docs/683385/current/fly-by-network-design-for-clock-command-and-address-signals?contentId=OLQV4DDW00tXJqrAPbeneQ)、[Layout Guidelines for DDR3 SDRAM Interfaces](https://docs.altera.com/r/docs/683385/current/layout-guidelines-for-ddr3-sdram-interfaces?contentId=CH6YpIj_a2V6OT6tYFpgXA)
- AMD UG583（UltraScale，v1.29，2025-12-23）：[DDR3 SDRAM Routing Constraints](https://docs.amd.com/r/en-US/ug583-ultrascale-pcb-design/DDR3-SDRAM-Routing-Constraints)、[General Memory Routing Guidelines](https://docs.amd.com/r/en-US/ug583-ultrascale-pcb-design/General-Memory-Routing-Guidelines)
- AMD UG863（Versal）：[Required Memory Routing Guidelines for All Interfaces](https://docs.amd.com/r/en-US/ug863-versal-pcb-design/Required-Memory-Routing-Guidelines-for-All-Interfaces)
- Howard Johnson，[Mitigating Crosstalk](https://www.sigcon.com/Pubs/news/6_01.htm)，[Serpentine Delays](https://www.sigcon.com/Pubs/edn/serpentine.htm)（EDN，2001-02）
- Lambert Simonovich，[Via Stubs – Are They All Bad?](https://signalintegrityjournal.com/blogs/7-voice-of-the-experts-signal-integrity/post/355-via-stubs-are-they-all-bad)，Signal Integrity Journal，2017-03-10

## 7. 建议接下来做的（只是提议，不是决定）

1. 地图 #26 的“高速规则写进 `docs/shape` 和规格档”一项：上面第 4 节的“缺失”清单可以直接当目录；数值要等瑞芯微那张票和时序预算出来再定。
2. 需要用户定的三件事：换层地过孔距离（H-01）；对内补偿按 TI 还是 ST 的说法（H-05）；RTE-11 给 fly-by 分叉开例外的写法（H-07）。
3. 叠层定稿前先决定哪些层只当地参考、数据线放在哪几层（H-02、H-03、H-10）。
