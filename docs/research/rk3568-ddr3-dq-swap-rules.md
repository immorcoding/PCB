# 调研：RK3568 接 DDR3 时数据线能怎样换位

对应 issue #51。日期 2026-11-27。背景：摆位已定（SoC 不转，颗粒在西边和北边），不换位时每个字节组内约 30 对连线交叉。本篇只回答“资料允许什么”，不做布线方案。

## 结论

| 问题 | 结论 | 依据（一手资料） | 备注 |
|---|---|---|---|
| (a) 字节组内 DQ 位任意对调 | 允许 | HDG 第 14 页“For DDR3/DDR3L”；CHK 项 6 | 两份都写 DDR3 支持字节内换位，没写任何位固定。DRAM 侧：写均衡和 MPR 的反馈位是 DQ0（低字节）、DQ8（高字节）（Micron 数据手册第 130、152 页），资料没有说明 SoC 的 PHY 是否只看对应位（见下“风险”）。 |
| (b) DM、DQS 跟着整个字节组换 | 资料未明说，倾向允许（推断） | HDG 第 14 页写“整组字节互换（entire group swap between Byte）”；HDG 第 186 页写“DM/DQS does not support exchange”（出现在 DDR4 四片的注里） | “整组”没有逐字写出包含 DM 和 DQS；第 186 页那句是 DDR4 段落，语境是分支等长，不是 DDR3 的换位规则。 |
| (c) 两颗颗粒之间的字节组对调 | 资料未明说（HDG 的“字节间整组互换”字面上没有限定在同一颗粒内） | HDG 第 14 页；CHK 项 6 与之矛盾 | **HDG 与 CHK 不一致**：HDG 写字节间可整组换；CHK 项 6 写“DDR3 支持重新调整顺序，但是只限 Byte 内”。 |
| (d) 必须固定的位 | 资料未说明有固定位（DDR3 无；ECC 字节固定） | HDG 第 14 页 | 只有两条固定：ECC 字节不能和别的字节互换；CA 顺序不能换。DDR3 数据位没有列出固定位。 |

建议：(c) 在动手前问瑞芯微（FAE）或沿用 CHK 的保守口径（只在字节内换位，整组字节不动）。(a) 可以用。(b) 若要做，必须把 DQS、DM 和该字节的 8 根 DQ 一起搬，并确认引导程序配置（见第 4 节）。

## 1. 一手资料说了什么（原文口径，不含推断）

资料来源：留档分支 `integration-rk3568` 的 `rk3568_minsys/refs/`（只读取，没有检出）。HDG 页码用页脚页码，和已有笔记 `rk3568-ddr3-layout-requirements.md` 同口径。

### 1.1 HDG V1.2（RK3568 Hardware Design Guide, 2022-01-26）

- 第 12 至 13 页，表 2-5“RK3568 DDR PHY I/O map”：PHY 引脚 DDR_DQ0_A…DDR_DQ15_A、DDR_DQ0_B…DDR_DQ15_B 与 DDR3 信号名一一对应（DDR_DQn_A 对应 DDR3_DQn，其余依序到 DQ31）；字节 0 到 3 各自带 DM 和 DQSP/N。这是“参考分配”。同一张表里 DDR4 一列的位序是打乱的（DDR_DQ0_A 对 DDR4_DQL0，DQ1 对 DQL2，DQ2 对 DQL4，DQ3 对 DQL6，DQ4 对 DQL7，DQ5 对 DQL5，DQ6 对 DQL3，DQ7 对 DQL1），LPDDR3 一列也是打乱的。（表中文字抽取后列位错位，DDR3 一列取值以位名顺序为准，建原理图时对原表再看一遍。）
- 第 14 页，表 2-5 之后的说明：
  - “For DDR3/DDR3L: Support the entire group swap between Byte; support DQ swap within Byte; The CA sequence cannot be swapped and must be allocated according to the schematic design.”
  - 同页：16 位总宽的模板，以及 16/32 位兼容的模板，“must use the template provided by RK, and no difference is allowed”。
  - 同页 DDR3/DDR3L 加 ECC：“ECC Byte is fixed, cannot swap with other Bytes; Support the entire group swap among other bytes; Support DQ swap within Byte; The CA sequence cannot be swapped.”
  - 对照：DDR4 同样写“整组可换、字节内 DQ 可换”，但 DDR4 加 ECC 以及 LPDDR4/4X 一条是“全部 DQ 和 CA 不能换，按参考图”；LPDDR3 是 D0–D7 对应关系及其 DQS、DM 不能调整，其余字节可整组换、字节内可换。
- 第 186 页，§3.2.3.5 DDR4 的注（四片 16 位 DDR4 共用 DQ/DM/DQS 时，可调整 cs1 组的 DQ 顺序使分支最短）：“DM/DQS does not support exchange, branches must be equal in length strictly”。这条在 DDR4 段落里，没有出现在 DDR3 小节（第 179 至 181 页）。

### 1.2 CHK（Schematic and PCB Review Checklist V1.0 CN，工作表 DRAM）

- 项 6（工作表第 6 行）：“请根据不同的DDR颗粒类型，选择相应的定义好的DQ顺序，其中DDR4/LPDDR4/LPDDR4x/LPDDR3不支持重新调整顺序，务必按参考图分配接，DDR3支持重新调整顺序，但是只限Byte内。”
- 项 7：CA 顺序全部不支持重新调整。
- 与 HDG 第 14 页不一致之处：HDG 写 DDR3 可“整组字节互换”，CHK 写“只限 Byte 内”。CHK 版本较早（V1.0）；HDG 是 V1.2，但两者都没有给出理由。

### 1.3 DRAM 侧：Micron DDR3L 数据手册（MT41K256M16 等，4Gb_DDR3L.pdf Rev. P 5/17，文档页码）

这是 DRAM 厂家的手册，用来说明 DRAM 对换位的容忍度；JEDEC JESD79-3 原文本次没有取到（见第 5 节）。

- 第 130 至 131 页，写均衡（Write Leveling）：“The prime DQ for a x16 configuration is DQ0 for the lower byte and DQ8 for the upper byte. It outputs the status of CK sampled by LDQS and UDQS. All other DQ … continue to drive LOW. Two prime DQ on a x16 enable each byte lane to be leveled independently.”
- 第 152 页，MPR：“The MPR JEDEC definition enables either a prime DQ (DQ0 on a x4 and a x8; on a x16, DQ0 = lower byte and DQ8 = upper byte) to output the MPR data with the remaining DQs driven LOW, or for all DQs to output the MPR data.” 第 153 页：预定义读图案是重复的 0-1（0,1,0,1…）。
- 同一份手册没有出现“DQ 位换位”或类似词句（搜索 swap、order 无关匹配）。

### 1.4 瑞芯微引导程序 rkbin（`rockchip-linux/rkbin`，2026-11-27 读取，页面经摘要工具转述，不是逐字核对）

- `tools/ddrbin_param.txt` 列有键：`ddr3_bytes_map`、`ddr2_bytes_map`、`ddr4_bytes_map`、`lp2/lp3/lp4_bytes_map`、`lp3_dq0_7_map`、`lp2_dq0_7_map`、`ddr4_cs0_dq0_dq15_map` 等；LPDDR4/5 有 `byteN_swap`、`byteN_dqM_swap`、CA 换位键。没有 `ddr3_dq*_map` 这类 DDR3 位级映射键。
- `tools/ddrbin_tool_user_guide.txt`：`ddr*_bytes_map`“The bytes remap in PHY”；`lp*_dq*_*_map`、`ddr*_cs*_dq*_dq*_map`“The dq remap in PHY”；模板信息一节写“实际换位值取决于 PCB 走线，必须和硬件设计一致，来自原理图里的 DDR Template Config 表”。该文档的平台支持表只列了 RK3572 支持模板信息，没有说 RK3568 的 DDR3 支持哪些键。

## 2. 资料没有说的（明说）

- RK3568 数据手册 V1.2（ds.txt）：没有关于 DDR 换位的信息。
- 瑞芯微高速 PCB 设计指南（HS，V10，2021-4-12）：没有关于 DQ、字节换位的信息（全文无 swap、exchange 相关内容；DDR3 只有第 32 至 34 页的布线要求表）。
- RK3568 TRM（DDRC、DDRPHY 章）：本次没有取得，未检索到可用的公开原文。
- 瑞芯微 DDR3 参考原理图：本次资料里没有 DDR3 参考原理图的页面（只有 DDR4 的 EVB1，以及 LPDDR4X 模板）。HDG 里的 DDR3 参考图是图片，没有抽出逐位走线。因此“参考板实际做过哪些换位”没有一手证据。
- 写均衡、MPR 训练时 RK3568 的 PHY 看哪一位：资料没有说明。
- RK3568 的 rkbin DDR 程序是否支持 `ddr3_bytes_map` 以及它的取值编码：资料没有说明。

## 3. 推断（不是资料原文，标明）

1. 字节内任意换位在 DRAM 侧是安全的：DRAM 对读写数据按位透明，读写走同一条换位，数据还原；DRAM 只在写均衡和 MPR 时区分 DQ0/DQ8，那时其余 DQ 驱动低电平（Micron 第 130、152 页），所以 SoC 侧若把所有位或各位的反馈综合起来看，位置不影响结果。DQ0（DQ8）换位后，是否破坏 SoC 的训练，取决于 PHY，资料没有说。HDG 明写字节内可换，所以认为 PHY 对此有处理，但这是对 HDG 的信任，不是看到的机制。
2. DDR4 一列在表 2-5 里就是打乱的（见 1.1），说明 PHY 对每种颗粒类型有一套固定的、可重新映射的位关系；DDR3 一列是顺序的参考分配。这支持“PHY 不绑定位序”，但不能由此推出 DDR3 位序可以随便换。
3. 第 14 页“整组字节互换”：整组应当指 DQ0–7、DM、DQS 一起搬，否则 DM 或 DQS 对不上对应的字节，写出的字节会被错误屏蔽。这一点是推断，原文没有逐字写。
4. 第 186 页“DM/DQS does not support exchange”：放在 DDR4 四片共线的注里，意思更可能是 DM/DQS 不能在不同字节之间或与 DQ 位互换，而不是 DDR3 整组换位的禁令；但这是读法，不是原文定义。
5. 两颗颗粒之间对调字节组（问题 c）：HDG 的“字节间整组互换”没有写同颗粒或跨颗粒，字面上不排除；但 CHK 项 6 给出的口径更窄。如果跨颗粒对调，DRAM 侧会遇到：片选、CA、CLK 是两颗共用的 T 型分支（见已有笔记第 2 节），两颗颗粒的 16 位通道是对称的，对数据通路没有影响。风险在于 SoC 的字节到颗粒的映射要靠 `ddr3_bytes_map` 之类的引导程序配置，而配置能否表示这种映射，资料没有说。
6. 一个同颗粒内的字节对调（颗粒的 LDQS 接 SoC 的高字节）：DRAM 侧由 MR1 写均衡对低、高字节各自独立校准（Micron 第 130 页“each byte lane to be leveled independently”），在 DRAM 看来没有区别；写数据按字节选通（DM、DQS）不依赖字节号。这仍然靠 SoC 侧支持。

## 4. 对本项目的含义

- 先按 HDG 第 14 页做的最保守的事：**字节内 DQ 换位**。资料两处（HDG、CHK）一致允许，且不改动引导程序里的字节映射。
- 字节间整组换（含两颗颗粒之间）：HDG 与 CHK 不一致，且引导程序的字节映射键 `ddr3_bytes_map` 的支持情况未查明。要做就先问瑞芯微 FAE 两件事：RK3568 的 DDR3 是否支持 `ddr3_bytes_map`；跨颗粒对调是否允许。
- 不要动：CA 顺序；ECC 字节；16 位及 16/32 位兼容模板的差异（必须用瑞芯微模板）。
- 建原理图时在注里写明哪个 DRAM 的 DQ0、DQ8 接了 SoC 的哪一位，方便以后查写均衡和 MPR 的问题。

## 5. 没做到的

- JEDEC JESD79-3 原文没有取到（需注册下载）；用 Micron 数据手册的转述代替，该手册引用的就是“MPR JEDEC definition”。
- 没有 RK3568 TRM 的 DDRPHY 章节；没有取到 DDR3 的瑞芯微参考原理图；Radxa 等第三方板的原理图（ROCK 3A/3B、CM3 用的是 DDR4 或 LPDDR4）不是 DDR3，没有用。
- 网上论坛（TI E2E、NXP 社区）对“最低位 DQ0 必须留在最低位”有相反说法，只能作线索，不是一手资料，也不是 Rockchip 的：有人说 JEDEC 要求每个字节组的最低位固定，也有 TI 工程师说 PHY 把所有 DQ 按位或后找反馈所以任意位都可以。RK3568 属于哪一种，资料没有说。
