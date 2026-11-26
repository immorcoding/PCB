# 调研：DDR3 颗粒选型（2 × 16 位，RK3568）

对应 issue #29（地图 #26）。调研日期 2026-11-26。本文只回答“选哪颗”，不含布局和走线。

约定：页码都是 PDF 页，和各文档页脚的印刷页码一致。“未核实”表示没有一手资料可对；“间接”表示只来自分销商或社区页面。

## 结论摘要

1. RK3568 支持 DDR3 和 DDR3L，32 位数据宽度，最多 2 个片选。两颗 16 位组成 32 位是受支持的配置：瑞芯微硬件设计指南的电源一节直接写了“two 16bit DDR3/3L”，拓扑一节给出 DDR3/DDR3L 的 16 位颗粒布线要求。
2. 数据手册写“兼容 DDR3-2133 / DDR3L-2133”。指南和手册里没有给出 DDR3 实际量产的最高速率。要等颗粒列表或 FAE 确认，不要按 2133 做预算。
3. 官方 DDR 支持列表（`Rockchip_Support_List_DDR`）没有取到。它放在瑞芯微 Redmine 上，需要登录；本仓库的留档分支里也没有这份表。所以“列表上有哪些 16 位 DDR3/3L 颗粒”这一问没有答案，需要用户或 FAE 把表给我们。
4. 推荐 Micron MT41K256M16TW-107:P（4 Gb、x16、DDR3L-1866、1.35 V、96 球 FBGA 8 × 14 mm、0.8 mm 球距，LCSC C253882）。理由：规格书能直接取到球图、封装图和时序页码；球图是 JEDEC x16 标准球图；有现货。代价：单价比三星和海力士高；它是否在瑞芯微列表上未核实。
5. 最大的未决事项：支持列表。选型在拿到列表之前只能算“候选”。

## 1. RK3568 对 DDR3 / DDR3L 的支持

| 事实 | 出处 |
|---|---|
| DDR 控制器支持 DDR3 / DDR3L / DDR4 / LPDDR2 / LPDDR3 / LPDDR4 / LPDDR4X，兼容 JEDEC；“Compatible with DDR3-2133/DDR3L-2133/LPDDR3-2133/DDR4-3200/LPDDR4-3200/LPDDR4X-3200” | RK3568 Datasheet Rev 1.2（2021-06）第 8 页，1.2.5 节。留档分支 `rk3568_minsys/refs/ds.txt`；原件 `rk3568_minsys/refs/RK3568_Datasheet_V1.2-20210601.pdf` |
| 32 位数据宽度，2 个片选，DDR3/DDR3L/DDR4 总寻址 8 GB；DDR3/3L/4 支持 8 位 ECC | 同上，第 8 页；硬件设计指南 V1.2 第 12 页 2.1.7.1 |
| DDR3/DDR3L 的 DQ 字节组可整组互换，字节内 DQ 可互换；CA 顺序不能换，必须按原理图设计分配。16 位和 16/32 位兼容的模板必须用瑞芯微的模板，不允许有差别 | 硬件设计指南 V1.2 第 14 页（留档 `rk3568_minsys/refs/hdg_en.txt` 第 1682–1690 行） |
| DDR3：DDRPHY_VDDQ 和 DDRPHY_VDDQL 都是 1.5 V；DDR3L：都是 1.35 V | 硬件设计指南 V1.2 第 22 页 2.1.7.5 |
| 两颗 16 位 DDR3/3L：1 A 的 DC/DC 够用；三颗以上建议 2 A 以上 | 硬件设计指南 V1.2 第 44 页 2.2.2.8（“a single LPDDR3 or … or two 16bit DDR3/3L or two 16bit DDR4, 1A DC/DC can be selected”） |
| 拓扑：DDR3/DDR3L 4 颗 16 位 2 片选，DQ 用 T 型（一驱二），CA 用双 T（一驱四）；加 ECC 共 6 颗 16 位 2 片选，CA 用 fly-by，末端 39 Ω 接 VTT。**文中没有写“2 颗 16 位 1 片选”这一种**（DDR4 的“two 16bit 1CS”倒是写了：DQ 点对点，CA T 型，第 19 页） | 硬件设计指南 V1.2 第 18–19 页 2.1.7.4 |
| 布线数值（阻抗 50 Ω ±10%、差分 100 Ω ±10%、DQ–DQS 600 mil 以内、CK–CS/CKE/ODT 30 mil 以内等） | RK3568 High Speed PCB Design Guide V10（2021-04-12）第 32–34 页，表 21–23。留档 `rk3568_minsys/refs/hs.txt`；原件在 `rk3568_minsys/refs/official/RK3568_Official Release/01_Common Document/Rockchip_RK3568_High_Speed_PCB_Design_Guide_V10_EN_2021-4-12.pdf` |
| DDR_RZQ 经 120 Ω 1% 接地；颗粒 ZQ 经 240 Ω 1% 接地；VREFCA 用两个 1 kΩ 1% 分压；VREFDQ 默认 0.75 V（DDR3）/ 0.675 V（DDR3L），可由寄存器调 | 硬件设计指南 V1.2 第 15–16 页 |

不确定或查不到：

- DDR3 的实际最高速率。数据手册只写“兼容 DDR3-2133”。瑞芯微 rkbin 里的 DDR 初始化二进制按频率分（920 / 1056 / 1332 / 1560 MHz，v1.26，[rkbin/bin/rk35](https://github.com/rockchip-linux/rkbin/tree/master/bin/rk35)），没有发布说明，看不出每种内存类型对应的上限。
- 官方 DDR3 参考设计。官方发布包的 `02_DDR Template` 目录只有 LPDDR4X 模板（`RK3568_Template_LP4XD200P132SD6_43x28_1600MHz`），官方 EVB1 是 DDR4（`RK_EVB1_RK3568_DDR4P216SD6`）。仓库里没有 DDR3 的原理图或 PCB 模板可抄。硬件设计指南第 14 页要求 16 位模板“必须用瑞芯微的模板”，所以要向 FAE 要 DDR3 模板。
- 开源 U-Boot 的 RK3568 内存初始化目前只确认了 LPDDR4（[U-Boot 邮件列表 2026-05](https://lists.denx.de/pipermail/u-boot/2026-May/618885.html)，间接）。DDR3 初始化要靠瑞芯微的 DDR 二进制。这块板只做 PCB，不影响选型，但以后点亮时要记得。

## 2. 官方支持列表

- 指南第 25 页 2.1.7.6：“For the DDR support list, please refer to the document `Rockchip_Support_List_DDR`, which can be downloaded from Rockchip redmine platform”，网址 `https://redmine.rockchip.com.cn/projects/fae/documents`。
- 实际访问：`https://redmine.rock-chips.com/documents/50` 只返回登录页。网上搜不到这份表的公开副本。留档分支里没有。
- 所以：**列表上有哪些 16 位 DDR3/DDR3L 颗粒，未能取得**。下面的候选是按“JEDEC x16、4 Gb、96 球、国内能买到”挑的，不是按列表挑的。
- 间接线索：Radxa 论坛有人把 ROCK 3A 的颗粒换成“列表上的型号”后仍报 DDR 未知设备错误（[论坛帖](https://forum.radxa.com/t/rock-3a-ram-chips/13426)），说明启动用的 DDR 二进制和颗粒之间有绑定，列表以外的颗粒有风险。

下一步（需要用户）：让 FAE 或有 Redmine 账号的人把 `Rockchip_Support_List_DDR` 发来，核对下面五个型号。

## 3. 候选型号

共同点：都是 4 Gb（256M × 16）、DDR3L（1.35 V，可向下兼容 1.5 V）、96 球 FBGA。价格和库存来自 jlcsearch（LCSC / JLC 零件库的社区镜像，[接口](https://jlcsearch.tscircuit.com/components/list.json?search=256M16)），2026-11-26 取得；页面没写币种，只能当相对大小看，下单前以 LCSC 页面为准。LCSC 官网页面抓取不到价格和库存。

| 型号 | LCSC | 速度等级 / 温度 | 电压 | 封装（规格书） | 库存 | 单价（1 件起 → 大量档） | 规格书核实 |
|---|---|---|---|---|---|---|---|
| Micron MT41K256M16TW-107:P | [C253882](https://www.lcsc.com/product-detail/C253882.html) | DDR3L-1866，0–95 ℃ | 1.283–1.45 V，向下兼容 1.5 V ±0.075 V | 96 球，8 × 14 mm，球距 0.8 mm，厚 1.1 ±0.1 mm | 1186 | 22.71 → 17.57（100 件起） | 是，见第 4 节 |
| Micron MT41K256M16TW-107 IT:P | [C367428](https://www.lcsc.com/product-detail/C367428.html) | DDR3L-1866，-40–95 ℃ | 同上 | 同上 | 1796 | 21.42 → 20.34（30 件起） | 同上（同一份规格书） |
| Nanya NT5CC256M16ER-EK | [C428584](https://www.lcsc.com/product-detail/C428584.html) | DDR3L-1866，0–95 ℃（-EKI 为工业级） | DDR3L 1.35 V（-0.067/+0.1 V），向下兼容 DDR3 1.5 V | 96 球，8.00 × 13.00 mm，球距 0.80 mm | 61 | 25.67 → 20.34 | 是，见下 |
| Samsung K4B4G1646E-BYMA | [C2940213](https://lcsc.com/product-detail/DDR-SDRAM_Samsung-K4B4G1646E-BYMA_C2940213.html) | DDR3L-1866，0–95 ℃ | 1.283–1.45 V（LCSC 页，间接） | 96 球，LCSC 页写 7.5 × 13.3（间接，未对三星规格书） | 1909 | 16.46 → 12.49 | 否：三星官网规格书链接取不到 |
| SK hynix H5TC4G63EFR-RDA | [C41349555](https://lcsc.com/product-detail/DDR-SDRAM_SK-HYNIX-H5TC4G63EFR-RDA_C41349555.html) | DDR3L-1866（RD 档，间接） | 1.35 V（间接） | 96 球，尺寸未核实 | 1000 | 9.67 → 7.59 | 否：没找到海力士官方规格书；有分销商称该型号已是“难找”料（间接） |
| Alliance AS4C256M16D3LC-12BCN | [C1012881](https://www.lcsc.com/product-detail/C1012881.html) | DDR3L，LCSC 写 933 MHz，别处写 800 MHz（自相矛盾） | 1.283–1.45 V | 96 球，7.5 × 13.5 mm | 页面未显示 | 页面未显示 | 否：官网规格书链接下载到的是网页，不是 PDF |

Nanya 规格书：DDR3(L)-4Gb E-Die NT5CB(C)512M8EQ / NT5CB(C)256M16ER，Version 2.8（2024-01），[LCSC 托管副本](https://atta.szlcsc.com/upload/public/pdf/source/20260613/41AFF3E597838AD4DFBF1329B1416170.pdf)（非 Nanya 官网，未对官网核对）。第 1 页：96 球 TFBGA 8.00 × 13.00 mm、球距 0.80；第 2 页订货表：NT5CC = DDR3L，NT5CB = 1.5 V DDR3；第 5 页：96 球 x16 球图；速度表 P.134–136。

其余在 LCSC 上看到但不推荐的：Nanya NT5CB256M16ER-FL（[C2841154](https://www.lcsc.com/product-detail/C2841154.html)）是 1.5 V 的 DDR3，不是 DDR3L；F60C1A0004-M79R（C516350，库存 126，单价 4.77）厂家不明，只有 0–85 ℃；Micron 8 Gb 的 MT41K512M16 系列是 1 颗 8 Gb，容量翻倍但贵得多。

其他厂（长鑫 CXMT、紫光、Winbond、ISSI、Zentel 等）：本轮没有查到可靠的 16 位 DDR3L 4 Gb 型号和货源，没有写入候选，不等于不存在。

### 球图和封装是不是 JEDEC 标准

- 球图：是。x16 96 球是 JEDEC 标准的 9 列（1–3、7–9 有球，4–6 空）× 16 行（A–T，无 I、O、Q、S）排布。Micron（[规格书](#4-推荐型号micron-mt41k256m16tw-107p)第 17 页）和 Nanya（第 5 页）的 A–T 行球名逐位一致，例如 A 行都是 VDDQ、DQU5/DQ13、DQU7/DQ15、DQU4/DQ12、VDDQ、VSS。Samsung、Hynix、Alliance 未对规格书，按 JEDEC 惯例应一致，需核实。
- 封装：球距都是 0.8 mm，球阵列范围一样（Micron 图 13：横向 6.4 CTR，纵向 12 CTR），**只有本体尺寸不同**：Micron TW 8 × 14，Nanya 8 × 13，Alliance 和 Micron LY 7.5 × 13.5（Micron 的 HA 是 9 × 14）。同一份焊盘图可以换用，丝印框和禁布区按最大本体（8 × 14，旧版 Micron 9 × 14）画才能互换。注意按 Rev. P 规格书第 1 页，x16 的 96 球封装随芯片版本变：Rev E 是 9 × 14，Rev N 是 7.5 × 13.5，Rev P 是 8 × 14；买到的批次要看标记。
- 球径：Micron 图 13 注明焊球 ⌀0.47（回流后），焊盘按 ⌀0.42 SMD 焊盘给出，与本仓库 0.8 mm 球距的 BGA 规格档（B 档）对得上。

## 4. 推荐型号：Micron MT41K256M16TW-107:P

理由：

1. 一手资料齐全：规格书（4Gb_DDR3L.pdf，Rev. P 5/17）直接给了 TW 封装的球图、封装图、速度等级和 AC 参数，下面每一项都有页码。
2. 标准球图，0.8 mm 球距，8 × 14 mm，96 球，焊盘好画；LCSC 有现货（1186 件）。
3. DDR3L-1866 的速度等级留足余量：RK3568 若按 DDR3-1333/1600 跑，不会被颗粒卡住。
4. 同一份规格书覆盖商业级（:P）和工业级（IT:P、AT:P）。

缺点和风险：

- 价格比三星、海力士高。
- 是否在瑞芯微支持列表上：未核实（本文最大的洞）。
- 如果要省钱或列表上没有它，备选顺序：Nanya NT5CC256M16ER-EK（规格书已核实，但库存只有 61）→ Samsung K4B4G1646E-BYMA（库存多、便宜，规格书待核实）。

规格书：`Micron 4Gb: x4, x8, x16 DDR3L SDRAM, 4Gb_DDR3L.pdf, Rev. P 5/17`（Micron 文档号 09005aef85af8fa8，217 页）。取到的副本：[TI E2E 托管](https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/791/MT41K256M16-MT41K512M8-MT41K1G4-_2800_4Gb-DDR3L-SDRAM_2900_.pdf)。Micron 官网的链接对自动下载返回网页，没有从官网取到；换成官网最新版后页码可能变，**写 SPEC 前要对最新版重核页码**。

| 内容 | PDF 页 |
|---|---|
| 特性、选项（TW = 96 球 8 mm × 14 mm，Rev. P）、速度等级表 1 | 1 |
| 寻址表 2（256M16：行 A0–A14、列 A0–A9、8 个 bank） | 2 |
| 96 球 x16 球图（俯视，图 7） | 17 |
| 96 球 x16 球名说明（表 4） | 20–21 |
| 封装图 TW（图 13：8 ±0.1 × 14 ±0.1，0.8 TYP，96 × ⌀0.47，高 1.1 ±0.1，A1 标记） | 27 |
| 另两种 96 球封装：HA（图 11）、LY（图 12） | 25、26 |
| 热阻、输入输出电容 | 29–31 |
| DDR3L 1.35 V 直流条件（VDD、VDDQ：1.283 / 1.35 / 1.45 V）；注 6：1.5 V 下按 DDR3 规格工作；注 7：从 DDR3L 换到 DDR3 供电只能在复位期间换 | 48 |
| DDR3L-1600 / 1866 / 2133 速度档表 | 79 / 80 / 81 |
| AC 特性总表 58（1066–1866）：例如 tDQSQ 为 200 / 150 / 125 / 100 ps（1066 / 1333 / 1600 / 1866）；tDQSS ±0.25 tCK；tDQSCK ±400 / 300 / 255 / 225 ps | 82–89（tDQSQ、tDQSS、tDQSCK 在第 83 页） |
| AC 特性表 59（速度扩展，含 2133） | 92–101 |
| 建立/保持时间降额（CA：tIS/tIH） | 103–104 |
| 数据建立/保持与降额（tDS/tDH） | 109 |
| VDD 电压切换（图 51，第 48 页注 7 引用其第 138 页） | 138 |

时序参数里写进 SPEC 的等长预算，用瑞芯微高速指南的数值（第 32–34 页），颗粒的 tDQSQ 等只作交叉核对。

## 5. 注意事项

1. **DDR3 与 DDR3L 的供电**：RK3568 的 DDRPHY_VDDQ 和 DDRPHY_VDDQL 跟着颗粒走，DDR3 为 1.5 V，DDR3L 为 1.35 V（指南第 22 页）。PHY 的这两路和颗粒的 VDD、VDDQ 要同一电压（Micron 第 48 页注 1：VDD 与 VDDQ 必须同电平才能保证 AC 时序）。所以验证板上 VCC_DDR 是一张铜皮、一个电压，别让 SoC 和颗粒各用一路。
2. 选 DDR3L 颗粒（如 MT41K）时可以按 1.35 V 或 1.5 V 供电，两者都在规格内（Micron 第 48 页）。想少改一次，设计成 1.35 V，同时在文档里写明电源的反馈电阻要跟着改：指南第 22 页提醒用 RK809-5 时要同步改 BUCK3 的 FB3（引脚 27）分压，用分立 DC/DC 时同样要改。本板没有 PMIC，只画到带 VCC_DDR 网络名的铜皮；这条放进 SPEC 的接口说明。
3. **选 DDR3（1.5 V）颗粒（如 Nanya NT5CB）会把电压锁死在 1.5 V**，之后想换 DDR3L 要改电源。不推荐。
4. **VREF 和 VTT**：VREFCA 用两个 1 kΩ 1% 电阻分压（指南第 16 页）；VREFDQ 由 SoC 提供，网络名 VREF_DDR_DQ；CA 若用 fly-by 要末端 39 Ω 接 VTT（指南第 19 页）。验证板“窄而全”，这些电阻要画。
5. **拓扑要向瑞芯微确认**：指南没有“两颗 16 位 DDR3、1 个片选”的拓扑图（只有 4 颗 2 片选和 6 颗带 ECC 两种）。DDR4 的“两颗 16 位 1 片选”是 DQ 点对点、CA 用 T 型（第 19 页）；DDR3 的对应做法按这个推断，但**这是推断，不是文档原话**。地图 #26 里“分叉拓扑（T 型或 fly-by）”的待定项正好落在这里。
6. **模板限制**：指南第 14 页要求 16 位和 16/32 位兼容的设计必须用瑞芯微的模板，而仓库里只有 LPDDR4X 模板。需要问 FAE 要 DDR3 的 2 × 16 位模板（原理图和 PCB），这会决定颗粒位置和 CA 分叉。
7. **DQ 字节组映射**：DDR3/DDR3L 可整组互换字节，字节内 DQ 可互换，CA 不能换（第 14 页）。两颗颗粒的 DQ 位序在规格书球图里是固定的，布线时有互换自由，可以用来缩短等长。
8. **封装版本**：同一型号的不同芯片版本本体尺寸不同（见上，Rev E 9 × 14、Rev N 7.5 × 13.5、Rev P 8 × 14）。焊盘图一样，禁布区按大的画；买到的批次看标记。
9. **DDR 初始化二进制**：瑞芯微的 DDR 初始化二进制按颗粒和频率生成，换不在列表上的颗粒可能起不来（上面的 Radxa 帖子，间接）。这是拿到列表后优先核对的理由。

## 6. 未查到或不确定的清单

- 官方支持列表的内容（需要 Redmine 账号）。
- RK3568 上 DDR3/DDR3L 的实测最高速率。
- Samsung、Hynix、Alliance 的一手规格书，以及它们的封装尺寸。
- LCSC 实时价格和币种（jlcsearch 没写币种）。
- 长鑫、紫光等国产 DDR3L 16 位型号。
- DDR3 的 2 × 16 位 1 片选拓扑和模板。
- Micron 官网最新版规格书的页码（本文的页码对的是 Rev. P 5/17）。

## 7. 来源清单

- RK3568 Datasheet Rev 1.2（2021-06）：留档分支 `integration-rk3568` 的 `rk3568_minsys/refs/RK3568_Datasheet_V1.2-20210601.pdf`，文字版 `ds.txt`。
- RK3568 Hardware Design Guide V1.2（EN）：同分支 `rk3568_minsys/refs/RK3568_Hardware_Design_Guide_V1.2_EN.pdf`，文字版 `hdg_en.txt`。
- RK3568 High Speed PCB Design Guide V10：同分支 `rk3568_minsys/refs/hs.txt` 和官方发布包。
- Micron 4Gb DDR3L SDRAM，Rev. P 5/17：[TI E2E 托管副本](https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/791/MT41K256M16-MT41K512M8-MT41K1G4-_2800_4Gb-DDR3L-SDRAM_2900_.pdf)。
- Nanya DDR3(L)-4Gb E-Die，Version 2.8：[LCSC 托管副本](https://atta.szlcsc.com/upload/public/pdf/source/20260613/41AFF3E597838AD4DFBF1329B1416170.pdf)。
- 库存和价格：[jlcsearch](https://jlcsearch.tscircuit.com/components/list.json?search=256M16)、[jlcsearch FBGA-96](https://jlcsearch.tscircuit.com/components/list.json?search=DDR3L&package=FBGA-96&limit=50)；LCSC 页面：[C253882](https://www.lcsc.com/product-detail/C253882.html)、[C1012881](https://www.lcsc.com/product-detail/C1012881.html)。
- rkbin DDR 二进制清单：[rockchip-linux/rkbin](https://github.com/rockchip-linux/rkbin/tree/master/bin/rk35)。
- Radxa 论坛：[Rock 3a RAM chips](https://forum.radxa.com/t/rock-3a-ram-chips/13426)；U-Boot 邮件列表：[RK3568 SDRAM 初始化补丁](https://lists.denx.de/pipermail/u-boot/2026-May/618885.html)。
