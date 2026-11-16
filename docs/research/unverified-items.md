# 未核对项清单（H7 六层测试板方案阶段）

对应票：[#18][i18]（地图 [#1][i1] 的子票）。整理日期 2026-11-16。分支 `research/unverified-items`，只存档不合并，不改 `docs/shape/`。本文是方案定稿里 PROC-8 要求的"未核对项"一节的底稿，**不做任何设计决定，不改已定结论**。

## 0. 怎么读这份清单

- 来源：地图 #1 "Decisions so far" 指到的已关闭票 [#2][i2]–[#13][i13]（正文和全部评论都读了，含 #7 下对 SDRAM 脚数的更正），以及 `origin/research/*` 十个分支的调研报告。"第 N 条"指那张票评论或报告"未核对项 / 未验证"一节的第 N 条。
- 阶段：原理图 / 规则 / 布局 / 电源铜皮 / 走线 / 只影响真打板（只做设计验证、不打板时不会碰到的事）。
- 谁核实：**用户手动下载**（官网对自动下载 403 或反爬，不绕过）/ **Claude 再查** / **等实物或板厂**。
- 本次核对的方法：TI、Winbond、Vishay 的规格书用 `curl` 直接下载；ST 的 PDF 用 WebFetch（它把 PDF 存到本地，我复制到独立目录再读）；PDF 转文字用 `pdftotext`，多列表格的文字层会错列，订货表一律渲染成图再读；读 PDF 的 Python 都带 `-I`。下载的文件放在工作树外的独立目录，不提交。外部请求里没有带用户名、邮箱、仓库名。

## 1. 统计

| 类别 | 条数 |
|---|---|
| 合并去重后共 | **65** |
| 本次核掉（§3，读了原文） | 14 |
| 已被后续票核实、推翻，或转成别的票（§4） | 12 |
| 已不相关（§5） | 14 |
| **仍未核对（§2）** | **25**（其中 U05、U10、U11、U13 本次有推进，但没了结） |

按谁能核实分（仍未核对的 25 条）：用户手动下载或在浏览器里查 12 条（U01–U04、U10–U12、U14–U18，需要的文件见 §6），等板厂或实物 4 条（U13、U19、U20、U23），Claude 再查或在对应阶段做 9 条（U05–U09、U21、U22、U24、U25）。

## 2. 仍未核对

"本次进展"写在"是什么"里。优先级见 §8。

### 2.1 器件规格书和选型（影响原理图）

| 编号 | 是什么 | 来源 | 阶段 | 谁核实 | 不核实的后果 |
|---|---|---|---|---|---|
| U01 | **LAN8742A 官方现行规格书从没读到**（Microchip 官网 403，本次 `curl` 再试仍 403）。现用的是第三方镜像：SMSC Rev 1.1（2013-05-21，DESY 站）和 DS00001989A（2015）。没核的参数：VDD1A / VDD2A / VDDIO 范围；VDDCR 外接（1 µF + 470 pF 取自 ST 原理图）；strap 脚（2 脚 nINTSEL、3 脚 REGOFF、10 脚 PHYAD0、7 / 8 / 11 脚 MODE）；14 脚 REFCLKO 模式（规格书注明不属 RMII 规范，要做时序分析，没做）；去耦 CBYPASS 数值（图里没给）；24 脚 QFN 的脚距（记忆是 0.5 mm）和推荐焊盘（KiCad 库焊盘 0.875 × 0.25，镜像推荐 0.85 × 0.30）；在产状态（DigiKey 标 Active，官网没读到）。KiCad 符号 24 脚的名字与 #9 的描述一致，但符号本身也是按同一份镜像画的，不算独立核对 | [#8][i8] 第 1 条；[#9][i9] 第 1、5 条；[#11][i11] 第 4 条；[pinmux §10.2-11][r-pinmux]；[power §4.1、§6-5][r-power]；[bus §8][r-bus] | 原理图（焊盘 → 布局） | 用户手动下载 | PHY 页的 strap、复位、供电接错，真上电才暴露 |
| U02 | **Würth 7499010211A（带集成变压器的 RJ45）规格书从没读到**（we-online.com 403，本次再试仍 403；Arrow 的副本上次超时，本次也连不上）。"带集成变压器"只是从 KiCad 库描述判断。没核：引脚定义（TD± / RD± / 中心抽头 / LED）、中心抽头电压、LED 的 VF / IF / 极性、封装图。布局估算用的 courtyard 18.9 × 22.2 mm 来自 KiCad 库 | [#9][i9] 第 2 条；[#11][i11] 第 4 条；[power §6-6][r-power]；[#13][i13] | 原理图；布局（外形） | 用户手动下载 | LED 限流和中心抽头接错；外形与尺寸估算不符 |
| U03 | **三个连接器的规格书和在产状态没有任何核对记录**（#9 的器件表直接定了型号，来源里没写读过规格书；本行是本表补列的）：Hirose FH12-40S-0.5SH（40 脚、0.5 mm FPC）、Hirose DM3AT-SF-PEJM5（microSD）、CUI（现 Same Sky）SJ-3523-SMT（3.5 mm 立体声座）。#13 的外形取自 KiCad 库 courtyard：FPC 26.1 × 7.9、microSD 15.7 × 17.7、音频座 11.2 × 18.0 mm。Hirose 官网本次 WebFetch 返回 403；Same Sky 我猜的两个直链 404，没再试。**FH12 要特别看**：搜索结果摘要说基础料号 FH12-40S-0.5SH 在 Octopart 标 obsolete、(54) 后缀停产、(55) 后缀在 DigiKey 加拿大站现货为 0（只见摘要，没打开页面，见 §7） | [#9][i9] 器件表；[#13][i13] 尺寸依据；本次搜索 | 原理图（脚位、开关脚、订货后缀）；布局（外形、焊盘） | 用户手动下载 | 脚位或卡检测 / 插头检测开关脚接错；订货后缀错；外形与尺寸估算偏 |
| U04 | **ISSI IS42S32800J 官方数据手册没从官网取到**（issi.com 反爬，本次请求返回约 1.1 KB 的占位页，不绕过）。手上是：本机缓存的副本（来源 URL 没记录，B 级）、Alliance 官方的同球图手册（A 级）、Micron 镜像。没核：90 球球名表逐球对 ISSI 原文（KiCad 里没有 32 位 SDRAM 符号，要自画）；H3 在 256 Mb 上是 NC、512 Mb 是 A12（对 ISSI 是推断，IS42S32160F 手册没取到，Alliance 和 ST 原理图已核）；封装图推荐焊盘（规则表用 Micron 的 0.33 mm，ISSI 没给推荐值）；AC 表（时序预算用的是镜像 Rev B1 2021-12，官网最新是 Rev C 2025-02-25）。本次读到 Alliance 官网目录页列有 AS4C8M32SA（256 Mb、8M × 32、90 球 TFBGA、商业级和工业级），无 EOL 标记 | [#3][i3]；[#4][i4] 第 4 条；[#6][i6]；[#7][i7] 第 6 条；[#10][i10]；[sdram §8][r-sdram]；[bus §8][r-bus]；[power §6-4][r-power] | 原理图（符号）；规则（焊盘） | 用户手动下载 | 自画符号的球名若与 ISSI 原文不一致，SDRAM 页接错；焊盘推荐值不同，规则区计算表要重算（#10 的 SDRAM 过孔间过线只有 0.006 mm 余量）；AC 表变了，#12 的余量要重算 |
| U05 | **没有型号、没读规格书的件**（#11 第 1 条只写了 TVS 和防反接 MOS，本行补全）：防反接 P-MOS（含栅极稳压管）、TVS（SMBJ18A 一类，具体型号未选）、贴片保险丝、5.5 × 2.1 mm DC 座、LMR51420 的订货后缀（X / Y × 有无 F，决定 500 kHz 还是 1.1 MHz、PFM 还是强制 PWM，也决定电感值）、背光升压的肖特基（按 40 V 耐压）、三个开关环路的电感、两颗磁珠、HSE / LSE / PHY 的晶振。本次进展：TVS 的钳位电压核掉了（V06），LMR51420 的后缀含义核掉了（V04） | [#11][i11] 第 1 条；[power §2f、§6-10、§6-11][r-power] | 原理图 | Claude 选型并读规格书，型号交用户定（PROC-8） | 原理图做不完 |
| U06 | **KiCad 库的符号和封装只核对了存在和引脚号，没核焊盘尺寸**。已知三处要处理：(1) SDRAM 库封装 `BGA-90_…_P0.8mm` 的焊盘是 0.40 mm，规则表按 0.33 mm，画封装时要改；(2) LAN8742A 库封装焊盘略窄（见 U01）；(3) 其余封装（SOT-23-6 / -5、SC70-5、SOIC-8、WSON-8 8 × 6、`Texas_RHB0032E_VQFN-32` 的 EP 3.45 × 3.45、RJ45、FH12、DM3AT、SJ-3523）没对厂家图纸。本次进展：库里的符号 / 封装是否存在核掉了（V14）；TLV320AIC3104 的 VQFN-32 封装 EP 3.45 与 TI 封装图的 3.45 一致，焊盘没核 | [#11][i11] 第 7 条；[power §6-17][r-power]；[sdram §5、§6][r-sdram]；[#6][i6]；[#10][i10]；[#9][i9] | 原理图（选封装）；布局 | Claude（TI 的图纸能下）；Hirose / CUI / Würth / Microchip 的见 U01–U03 | 封装焊盘错，DRC 干净也装不上 |
| U07 | **ST 原理图里位号与网络的对应是从渲染图读的**（Altium 导出的 PDF 文字层是乱的，只核对了型号和数值）。抄 MB1246 第 3–5 页、MB1520 的电路时会遇到 | [#4][i4] 第 8 条；PROC-14 的 Signals | 原理图 | Claude 画图时逐网络对图读；用户审 | 抄错连接 |
| U08 | **负载预算里的估算项**：FMC 翻转电流、SDRAM 典型值（ISSI 只给最大值）、PHY 最大值（只有典型值）、LCD 逻辑电流、耳机动态电流、MCU VDDA 电流、LED 电流、12 V 侧输入电流、保险丝取值 | [#11][i11] 第 2 条；[power §6-15][r-power] | 原理图（稳压器和保险丝余量） | Claude 能补一部分；其余等实物 | 稳压器已按"最大 × 1.5"取 2 A 级，影响小 |
| U09 | **电源环路没算、没审**：纹波、效率、热；电感和输出电容取值；TPS61169 外围（电感 4.7–10 µH、肖特基和输出电容按 40 V）；各规格书的"推荐布局图"只确认存在，没审内容 | [#11][i11] 第 6 条；[power §6-13、§6-14][r-power] | 原理图（选值）；电源铜皮（环路布局） | Claude（TI 规格书能下，本次已下载 6 份） | 电感饱和、纹波超标、环路面积偏大 |

### 2.2 在产状态和采购

| 编号 | 是什么 | 来源 | 阶段 | 谁核实 | 不核实的后果 |
|---|---|---|---|---|---|
| U10 | **IS42S32800J-6BLI 的在产状态**。只有搜索摘要（Prod、Long-Term Support）。本次进展：Alliance 官网目录列有同球图的替换系列 AS4C8M32SA，无 EOL 标记（页面不列带 -6BIN 后缀的完整料号） | [#3][i3]；[#7][i7] 第 1 条；[power §6-12][r-power] | 只影响真打板 | 用户在 issi.com 上看（反爬） | 采购时才发现；已有同封装替换料 |
| U11 | **W25Q128JVEIM 的在产状态**。官网产品页是 JS 渲染，读不到。本次进展：Winbond 官网规格书 Rev D（2025-02-04）§11.1 的订货表列有 `W25Q128JVEIM`（E = WSON-8 8 × 6），表上写"具体供货请联系 Winbond" | [#7][i7] 第 2、3 条；[qspi §4.2、§9-2][r-qspi] | 只影响真打板 | 用户在 winbond.com 上看 | 同上；有同封装替换料 |
| U12 | **替换料 Flash 的状态**：Micron MT25QL128ABA1EW9-0SIT（PCN 36228 原文没读到，128 Mb 在不在停产名单里不清楚；规格书只读到 2019 年 Rev K 的镜像）；Macronix MX25L12833F（零件页上有"End of Life (EOL)"标签，含义没读出）。Micron 零件页是 JS 渲染 | [#7][i7] 第 2、4 条；[qspi §4.1、§4.3、§9-1、§9-3、§9-6][r-qspi] | 只影响真打板 | 用户 | 替换料可能已停产，换料时才知道 |
| U13 | **芯片是 rev Y 还是 rev V**：400 MHz 对 480 MHz；85 ℃ 时 VDD 最大电流 400 对 327 mA；SDRAM 写、SDMMC、RMII 的时序两版不同，已按较差的一版算。本次进展：DS12110 p.22 脚注 3 "480 MHz 只在 rev V 上"，p.349 订货码 "A = Advanced mission profile (VOS1, 480 MHz)"，都没说 `STM32H743IIK6` 对应哪一版 | [#2][i2] 第 6 条；[#11][i11] 第 3 条；[#12][i12] 记入项；[power §6-1][r-power]；[bus §8][r-bus] | 只影响真打板 | 等实物（封装顶面的版本标记） | 只影响余量，不影响连接 |

### 2.3 固件、协议和外部文档

| 编号 | 是什么 | 来源 | 阶段 | 谁核实 | 不核实的后果 |
|---|---|---|---|---|---|
| U14 | **RM0433（3329 页）和勘误 ES0392 没读**：FMC / SDRAM 章节里和封装有关的说明、SDRAM 与 SRAM 共总线的时序限制、RPIPE 的机理、QUADSPI 章节（dummy 周期、SSHIFT）和勘误里的 QUADSPI 条目、SAI 主从与时钟（codec 一侧已核，见 V03）、启动流程；固件必须把 IO 速度档配成 DS 测时序的条件（OSPEEDR = 11、补偿单元开），LTDC 像素时钟的 IO 速度档也没查 | [#2][i2] 第 1 条；[#8][i8] 第 9、10 条；[#9][i9] 第 5 条；[qspi §9-10][r-qspi]；[bus §1.3、§8][r-bus] | 只影响真打板（固件） | 用户手动下载（ST 的 `curl` 被拦；页数多，预计超出 WebFetch 的 10 MB 限制，没试） | 固件配置时才暴露；不挡原理图、布局、走线 |
| U15 | **SD 卡规范读的是 v3.01（2010）的简化版和论坛附件**，新版高速模式的时序没对（sdcard.org 返回 403） | [bus §8][r-bus]；[power §6-9][r-power]；[#12][i12] 记入项 | 走线（SDMMC 的"CK 到 CK + 5 mm"规则） | 用户手动下载 | 小：#12 算出的往返和上限是 435 mm，余量大 |
| U16 | **面板（Rocktech RK043FN48H、Innolux AT043TN24 V.7）的规格书都是非官网镜像**：FPC 脚距 0.8 mm 只有外形图一处依据；"通用脚序"只对了两份；35 脚定义不一致；"RGB565 只接高位"是推断；采样沿和时序图没读清；Innolux 只读了 V.7（其他版本背光差很大）；LCD 上电时序图 T1–T6 没解读。本板只放 40 脚 0.5 mm 的 FPC 座，不焊面板 | [#8][i8] 第 4 条；[#9][i9] 第 3 条；[#11][i11] 第 4、5 条；[#12][i12] 记入项；[power §4.3、§6-7、§6-8][r-power]；[bus §8][r-bus] | 只影响真打板（座的脚序在原理图阶段按现有两份镜像先画） | 用户（向面板供应商要官方版） | 真接面板时脚序、采样沿、背光电流不符 |
| U17 | **OPLA 的解读不是法律意见**："公开发布自己重画的原理图"算不算分发协议没明说；Altium 工程 ZIP 里有没有额外许可证没下载。仓库现在私有 | [#4][i4] 第 7 条；[stref §10][r-stref] | 只影响真打板（公开发布时） | 用户 | 公开仓库时的合规风险 |

### 2.4 板厂（嘉立创）

| 编号 | 是什么 | 来源 | 阶段 | 谁核实 | 不核实的后果 |
|---|---|---|---|---|---|
| U18 | **阻抗线宽全是计算值**：50 Ω 单端 L1 / L6 0.156 mm、L4 0.125 mm，是自己写的二维有限体积法算的（校验对 Hammerstad–Jensen 低 0.4–0.8%，估计和计算器差 ±0.01 mm）；嘉立创计算器（jlcpcb.com 和 tools.jlc.com）没能驱动；叠层的 Er 是嘉立创反推值（ps / mm 有 ±4%）。**新增缺口**：#5 只算了 50 Ω 单端和 90 Ω 差分，板上没有 USB，但以太网 TX± / RX±（PHY 到 RJ45）要 100 Ω 差分，没人算过 | [#5][i5]；[#1][i1]；[bus §8][r-bus]；[jlc §6][r-jlc] | 规则（RUL-3，走线前） | 用户在浏览器里用计算器（选 JLC06161H-3313E） | 阻抗偏几 Ω；测试板影响小 |
| U19 | **嘉立创规则文字的歧义**：(a) "开窗 1:1"是不是指 CAM 不再补偿；"开窗到邻线 ≥ 0.09"量哪条边；(b) 塞孔范围 0.15–0.55 mm 指孔径还是外径，盘中孔焊盘 0.35 mm 的要求和同页示例（0.15 / 0.25）矛盾；(c) 0.45 / 0.2 过孔收不收费（国际站两页写法不一致）；(d) 六层填孔时过孔铜到 BGA 焊盘的下限（公布的 0.10 mm 只有 2 / 4 层油墨塞孔的表）；(e) DFM 是否按插件孔焊环 0.15 检查过孔焊环 0.075；(f) 国内站外层孔到走线下限（D2 写 0.2，D3 写 0.3）；(g) 孔到线 0.005 mm 的余量只对名义值成立（钻孔位置 ±0.075，线宽 ±20%） | [#5][i5]；[#6][i6] 第 2 条；[#10][i10]；[jlc §8][r-jlc]；[fanout §十][r-fanout] | 规则；只影响真打板 | 等板厂（客服，或下单时的 DFM"确认生产稿"） | 真打板时 DFM 改孔或开窗、加价、良率问题 |
| U20 | **嘉立创金额和国内站**：0.15 mm 孔加价金额、铜浆塞孔、选 3313E 是否收费或影响交期、国际站 ±10% 阻抗是否收费、国内站 3313E 叠层和各层 Er（只在 `tools.jlc.com` 的接口里）、国际站规格页和叠层页没有更新日期、嘉立创贴片对 0.65 mm BGA 的要求 / 钢网厚度 / 表面处理（BGA 焊点 0.2–0.25 mm 只能沉金） | [#5][i5]；[#6][i6]；[#10][i10]；[jlc §4、§8][r-jlc]；[fanout §十-7][r-fanout] | 只影响真打板 | 等板厂（报价、客服） | 预算和交期 |

### 2.5 布局和走线的估算（Claude 在对应阶段验）

| 编号 | 是什么 | 来源 | 阶段 | 谁核实 | 不核实的后果 |
|---|---|---|---|---|---|
| U21 | **扇出出线容量只是计数，没试走；摆位对比只是飞线估计**：环 0 有 56 个缝容纳环 1 的 48 个球；绕行模型是调研 agent 自己加的、假设很强；只覆盖套 A；FPC 座位置没定；5 / 10 mm 的间隔里放不放得下 MCU 背面去耦过孔和 SDRAM 去耦端接没查；背面去耦"两个焊盘都用短线接球间位狗骨头孔"是调研的方案（ST 用盲孔） | [#6][i6]；[#10][i10]；[#8][i8] 第 6、8 条；[#12][i12]；[placement §十二][r-placement]；[fanout §十-13][r-fanout] | 布局（#12 的线序草图验收，LAY-3 试走） | Claude | 比估计更挤时回退，改尺寸、层数或摆位 |
| U22 | **面积估算和平面完整性是定性判断**：各块面积按封装外框加经验余量估（器件块约 4300 mm²，占 85 × 75 mm 的 67%），没有摆过；球阵下 70–80 个通孔对 L2 / L3 的影响、"L4 跨 L3 分块缝基本没影响"、背面去耦对 L6 通道的占用，都没算 | [#13][i13] 记入项；[#6][i6]；[fanout §十-4][r-fanout] | 布局；电源铜皮 | Claude（指标表，PROC-4） | 布局回退或改板框（"大动"开 `try/` 分支） |
| U23 | **时序和信号完整性**：IBIS 都没用上（MCU 的 IBIS 在 ST 产品页，没下载；ISSI 的打不开；Alliance 的已核，可代用；三颗 Flash 的找不到）；时序预算只含数据手册 AC 表加走线延迟，没计入串阻（ST 在 MCU 侧串 33 Ω，粗估吃掉读建立余量约 0.3 ns）、反射、串扰、抖动、同步开关噪声、封装内部延迟、过孔；AC 表测量电平和负载条件不同；DS12110 没给 SDRAM 地址保持和 NBL 时序；W25Q128JV 只给 tCLQV 最大值（30 pF），"133 MHz 不成立"只能说按保证值 | [#2][i2] 第 7、9 条；[#3][i3]；[#7][i7] 第 5 条；[bus §1.4、§8][r-bus] | 走线 | 仿真（IBIS）和等实物 | 余量被吃掉时才在真板上出现；#12 已取 CL3、≤ 100 MHz、每根 ≤ 60 mm 留余量 |
| U24 | **KiCad 里能不能给过孔去掉未连接内层的焊盘**、选项叫什么，没核对。嘉立创指南里这样做可以让 0.09 mm 的线从两个过孔之间走 | [jlc §9][r-jlc] | 规则；走线（L4 出线） | Claude（KiCad 10 里试） | 内层过孔焊盘占空间，L4 出线可能少一个通道 |
| U25 | **ST 官方板清单没穷举**（核对的 6 块里没有 UFBGA176+25 的 H743 / H750 / H753），H747I-EVAL、H757I-EVAL 的 SDRAM 没查 | [#2][i2] 第 7 条；[mcu §7][r-mcu]；[#3][i3] | 原理图（参考来源） | Claude | 可能漏掉更接近的官方参考 |

## 3. 本次核掉

PDF 页码是 PDF 页码（不是页脚印的页码）。TI 订货附录的日期是附录自带的日期，不是今天。

| 编号 | 核掉什么 | 原未核对项 | 读的 URL | 页和原文 / 数值 | 结论 |
|---|---|---|---|---|---|
| V01 | **TLV320AIC3104 在产** | [power §6-12][r-power]（没查状态） | <https://www.ti.com/product/TLV320AIC3104>（WebFetch）；<https://www.ti.com/lit/ds/symlink/tlv320aic3104.pdf> | 产品页状态 "ACTIVE"（无日期）。SLAS510G p.95 订货附录（9-Nov-2025）："TLV320AIC3104IRHBR  Active  Production  VQFN (RHB) \| 32  3000 \| LARGE T&R … -40 to 85  AC3104I" | 在产（官网产品页和规格书订货附录一致） |
| V02 | **TCAN1042HGVDR 在产、引脚、STB 行为、VIO 范围** | [#9][i9] 第 7 条（分销库存没查，库存不看）；[#9][i9] 决定 6（"引脚同位"）；[pinmux §6.4][r-pinmux] | <https://www.ti.com/product/TCAN1042HGV>（WebFetch）；<https://www.ti.com/lit/ds/symlink/tcan1042h.pdf>（SLLSES7D） | 产品页 "ACTIVE"。p.33 订货附录（9-Nov-2025）："TCAN1042HGVDR  Active  Production  SOIC (D) \| 8  2500 \| LARGE T&R … -55 to 125  1042V"。p.5 表 6-1 和图 6-3（D 封装，V 款）：1 TXD、2 GND、3 VCC、4 RXD、5 VIO、6 CANL、7 CANH、8 STB（"Standby Mode control input (active high)"）。p.21 §9.3.7.2："the internal pull ups on TXD and STB are pulled up to VIO"。p.29："VIO, designed for a range between 3 V and 5.5 V"；VCC 4.5–5.5 V。p.1：SOIC 本体 4.90 × 3.91 mm | 在产；引脚与 MCP2562 逐位相同（1 TXD 2 VSS 3 VDD 4 RXD 5 VIO 6 CANL 7 CANH 8 STBY）；STB 悬空 = 待机、必须拉低，#9 成立；VIO 3.3 V 在范围内。SOIC-8 的焊盘图纸没核（仍归 U06） |
| V03 | **TLV320AIC3104 的参数（转述 → 原文）和 RθJA 矛盾** | [#9][i9] 第 6 条；[#9][i9]（"脚距和其余参数是转述"） | 同 V01 的规格书 | p.45："responds to the I2C address of 0011000"（= 0x18，#9 成立）。p.22 §10.3.1："requires a hardware reset after power up … RESET pin must be driven low for at least 10 ns"；"recommended to add at least a 1-nF capacitor connected between the RESET pin and DVSS"。p.5 注："Connect device thermal pad to DRVSS"（p.92 同）。p.99："5 x 5, 0.5 mm pitch VQFN"。p.1：AVDD 2.7–3.6 V、DVDD 1.525–1.95 V、IOVDD 1.1–3.6 V。p.91 §12：IOVDD 先、AVDD / DRVDD 其次、DVDD 最后，"analog supplies should be greater than or equal to DVDD at all times"，表 12-1 t2（AVDD 到 DVDD）0–5 ms。p.12–13：有 I2S 从机的电流和时序。**RθJA：p.7 绝对最大额定值表写 44 °C/W，p.8 表 8.4 写 31.9 °C/W** | #9 的各项描述成立。RθJA 两个值是规格书自己互相矛盾，不是读错；本板 codec 耗散 < 0.1 W，不影响设计 |
| V04 | **LMR51420 订货后缀**（原按订货表顺序推断） | [#11][i11] 第 1 条；[power §6-11][r-power] | <https://www.ti.com/lit/ds/symlink/lmr51420.pdf>（SLUSEF6C） | p.3 §5 器件对照表（渲染成图读）：LMR51420**X**DDCR 500 kHz PFM；XFDDCR 500 kHz FPWM；**Y**DDCR 1.1 MHz PFM；YFDDCR 1.1 MHz FPWM。p.3 表 6-1：1 GND、2 SW、3 VIN、4 FB、5 EN、6 CB。p.26 订货附录（31-Oct-2025）四个后缀全部 Active Production，SOT-23-THIN (DDC) \| 6。p.4 §7.1：VIN 绝对最大 38 V，EN 不超过 VIN + 0.3 V | X = 500 kHz、Y = 1.1 MHz、有 F = 强制 PWM，推断成立；引脚与 `LMR51430` 符号相同。选哪个后缀仍是 U05 |
| V05 | **TI 订货号与封装、TPS61169 脚距** | [power §2d][r-power]（"订货表的封装列在提取的文本里错位，靠型号后缀判断"）；[pinmux §6.5][r-pinmux]（TPS61169 脚距没读到） | <https://www.ti.com/lit/ds/symlink/tps62a02.pdf>；`tps7a20.pdf`；`tps61169.pdf` | TPS62A02：p.21 订货附录（7-Oct-2025，渲染成图读）"TPS62A02PDDCR  Active  Production  SOT-23-THIN (DDC) \| 6  3000"，p.3 表 5-1 的 SOT23-6：1 EN、2 GND、3 SW、4 VIN、5 PG、6 FB。TPS7A20：p.45（31-Oct-2026，图）"TPS7A2033PDBVR  Active  Production  SOT-23 (DBV) \| 5"，p.42（图）"TPS7A2018PDBVR  Active  Production  SOT-23 (DBV) \| 5"。TPS61169：p.18（20-Aug-2026）"TPS61169DCKR  Active  Production  SC70 (DCK) \| 5"，p.21 封装图 DCK0005A "2X 0.65" | 订货号与封装的对应成立（文字层会把这几行错配成 X2SON / DRL，不能信）；TPS61169 脚距 0.65 mm。另：TPS62A02 的 VIN / EN / PG 绝对最大 6.5 V（p.4），与 #11 的"+5V 不能有过冲"一致 |
| V06 | **TVS 钳位电压**（#11 凭记忆写） | [#11][i11] 第 1 条（"两个钳位值凭记忆"）；[power §6-10][r-power] | <https://www.vishay.com/docs/88392/smbj.pdf>（Vishay SMBJ5.0A–SMBJ188A，Rev 09-Jan-2024） | p.2 表：SMBJ18A  VWM 18 V，VBR 20.0–22.1 V，IPP 20.5 A，**VC 29.2 V**；SMBJ24A  VWM 24 V，IPP 15.4 A，**VC 38.9 V** | "18 V 档约 30 V、24 V 档约 39 V"成立，24 V 档高过 LMR51420 的绝对最大 38 V，"不写到 24 V"的理由成立。具体 TVS 型号仍未选（U05） |
| V07 | **MCU 球图的电源球和特殊球**：13 个 VDD 球（数图得到）、E–L 行电源球、VDDLDO 和 VDD50USB 无球 | [#4][i4] 第 5 条；[#2][i2] 第 3 条；[#8][i8] 第 2 条（PC14 / PC15 / PH0 / PH1 拆行没比） | <https://www.st.com/resource/en/datasheet/stm32h743ii.pdf>（DS12110 Rev 11，WebFetch）；KiCad 10.0.8 的 `MCU_ST_STM32H7.kicad_sym` | 表 9 p.64–88 的 UFBGA176+25 列，脚本（`-I`）逐球对 `STM32H743IIKx` 符号：VDD 13 个 {C5, C7, C8, C9, F3, G3, G13, J12, J13, K4, N8, N9, N10}，VSS 37 个，VCAP 2 个 {F13（p.81）, M10（p.73）}，两边完全相同；VBAT C1、PDR_ON C6、BOOT0 D6、NRST J1、VSSA M1、VREF− N1、VREF+ P1、VDDA R1、VDD33USB H13（p.78）；VDDLDO 行该列为 "-"，注 6、8："the VDDLDO pin is internally tied to VDD"、"VDD50USB pin is internally tied to VDD33USB"。拆行的 12 个手工核：PC14 E1、PC15 F1、PH0 G1、PH1 H1、PA13 A15、PA14 A14、PA15 A13、PB3 A10、PB4 A9、PC2_C M4、PC3_C M5（后两个在表 9 以 "M4(4)"、"M5(4)" 出现） | 符号的 201 个球（140 个 GPIO + 61 个非 GPIO）与表 9 逐球一致：#8 比了 138 个 GPIO，本次补了其余 63 个。RUL-6 的"大芯片引脚对照官方引脚表用脚本比"在方案阶段已经做完 |
| V08 | **LSE、HSE 的球在最外圈** | [#10][i10]（"LSE 的球 PC14 / PC15 是否在最外圈"） | DS12110 p.60 图 10；表 9（见 V07） | PC14 = E1、PC15 = F1、PH0 = G1、PH1 = H1，都在第 1 列 | 都在最外圈（环 0），#10 的"晶振不加区内例外"成立 |
| V09 | **VCAP 接法**（规格书写"两颗 2.2 µF"，AN4938 写"两脚互连"） | [#2][i2] 第 4 条 | <https://www.st.com/resource/en/application_note/an4938-getting-started-with-stm32h74xig-and-stm32h75xig-mcu-hardware-development-stmicroelectronics.pdf>（AN4938 Rev 7，WebFetch） | p.12 §2.2："both VCAP1 and VCAP2 pins must be connected to a 2.2 µF ceramic capacitor with a low ESR (< 100 mΩ). Connect VCAP1 pin to VCAP2 pin"。p.36 图 18（渲染读）：三个 VCAP 球接到同一个节点，节点上并两颗 2.2 µF（C4、C5）到地 | 本封装两个 VCAP 球（F13、M10）并成一个网络，挂两颗 2.2 µF、ESR < 100 mΩ 的陶瓷电容，与 #11 一致 |
| V10 | **AN4938 与 DS12110 的 tRSTTEMPO 不一致** | [power §6-16][r-power] | AN4938（同上）；DS12110（同 V07） | AN4938 p.15 图 4 注 1："tRSTTEMPO is approximately 2.6 ms … Refer to the device datasheets for the actual values"。DS12110 表 17 p.107（rev Y）和 p.212（rev V）：tRSTTEMPO 典型 377 µs | AN4938 自己说以数据手册为准，取 377 µs；MCU 用片内上电复位，不影响设计 |
| V11 | **PC13 / PC14 / PC15 / PI8 的速度限制**（#8 写"3 MHz"，规格书文本里没找到） | [#8][i8] 第 4 条；#9（PHY 复位接 PC13） | DS12110 | 表 53 注 2，p.142（rev Y）和 p.246（rev V）："The frequency of the GPIOs that can be supplied in VBAT mode (PC13, PC14, PC15 and PI8) is limited to 2 MHz"。表 52，p.140：输出电流 IIO = ±3 mA | 实为 **2 MHz**、3 mA，不是 3 MHz；PHY 复位是慢速线，#9 的用法成立 |
| V12 | **辅助脚功能抽查**：PB5 = TIM3_CH2（背光 PWM）、PB3 = SWO | [#9][i9] 第 4 条（"来自调研报告，画原理图时对规格书"） | DS12110 表 9 | p.86：PB5 的 UFBGA176+25 球 A6，备选功能列表含 TIM3_CH2；PB3 的行写 "PB3(JTDO/TRACESWO)"，球 A10 | 这两个成立；其余辅助脚是普通 GPIO。AF 编号（PB5 是 AF2）仍是 #8 看图的结果，见 S03 |
| V13 | **W25Q128JVEIQ 现在还能不能订** | [#7][i7] 第 3 条 | <https://www.winbond.com/resource-files/W25Q128JV_DTR%20RevD%2012232024%20Plus.pdf>（Rev D，2025-02-04） | p.102（印刷页 101）§11.1 有效料号表：WSON-8 8 × 6（E）只列 `W25Q128JVEJM`、`W25Q128JVEIM`；没有 `…IQ` | 2025 版规格书不列 `IQ`，不能依赖它；定 `IM` 的选择不受影响 |
| V14 | **KiCad 库里有没有符号和封装** | [#9][i9]（没有 TLV320AIC3104、TCAN1042、TPS61169 的符号）；[#11][i11]（没有 LMR51420）；[#3][i3]（没有 32 位 SDRAM 符号） | 本机 `D:\KiCad\share\kicad\`（KiCad 10.0.8） | 符号：没有 TLV320AIC3104（`Audio.kicad_sym` 里只有 TLV320AIC3100）、TCAN1042、TPS61169、LMR51420、IS42S32800J；有 LAN8742A、TPS62A02、TPS7A20、W25Q128JVE、MCP2562、TPS61165。封装都在：`Hirose_FH12-40S-0.5SH_1x40-1MP_P0.50mm_Horizontal`、`microSD_HC_Hirose_DM3AT-SF-PEJM5`、`Jack_3.5mm_CUI_SJ-3523-SMT_Horizontal`、`RJ45_Wuerth_7499010211A_Horizontal`、`BGA-90_8.0x13.0mm_Layout2x3x15_P0.8mm`、`UFBGA-201_10x10mm_Layout15x15_P0.65mm`、`WSON-8-1EP_8x6mm_P1.27mm_EP3.4x4.3mm`、`SOT-353_SC-70-5`、`SOIC-8_3.9x4.9mm_P1.27mm`、`Texas_RHB0032E_VQFN-32-1EP_5x5mm_P0.5mm_EP3.45x3.45mm` | 五个符号要自画；封装不用自画（焊盘尺寸仍是 U06） |

## 4. 已被后续票核实、推翻，或转成别的票

划掉的是原来的未核对项，后面写在哪里核实的。

| 编号 | 原未核对项 | 来源 | 在哪里解决 |
|---|---|---|---|
| S01 | ~~FMC 各信号到 UFBGA176+25 球号的映射没逐个核；MB1246 用的端口在本封装上是否都有球~~ | [#4][i4] 第 3 条；[#2][i2] 第 2、3 条；[mcu §4][r-mcu] | [#8][i8] / [pinmux §10.1-1、2、4][r-pinmux]：引脚库与 KiCad 符号 201 个球 0 处不一致；138 个 GPIO 球号与 DS12110 表 9 全部一致；三套用到的 301 组（引脚、信号）都在备选功能里；57 个 SDRAM 信号各占一个球 |
| S02 | ~~SDRAM 连 A12 是 58 个脚还是 57 个~~ | [#7][i7] 评论 | [#8][i8] §1.1：57（地址 13 + BA 2 + 数据 32 + NBL 4 + 控制 6）；#7 下 2026-11-16 的更正评论；三颗芯片共占 63 个 |
| S03 | ~~AF 编号没脚本核对 / 没重核~~ | [#8][i8] 第 3 条；[#9][i9] 第 4 条 | [pinmux §10.1-3][r-pinmux]：DS12110 表 10 p.89–99 渲染成图逐页看，和 CubeMX 开放引脚库互证；[#9][i9] 又对表 9、10 重核了 SAI1、I2C4 的七个脚。**核实方式是人工看图**，表 10 的文字层是乱的，没法脚本化 |
| S04 | ~~MB1246 的 SDRAM 页转文字是乱码，SDCKE0 / SDNE0 / SDNWE 用哪个备选脚、有没有串阻~~ | [#2][i2] 第 2 条 | [sdram §4][r-sdram]、[stref §5.1][r-stref]：MB1246 第 5 页 U15 IS42S32800J-6BLI，D0–D31 和 NBL0–3 全接，用 SDNE1 / SDCKE1，14 颗 100 nF，SDRAM 侧无串阻；33 Ω 串阻在第 3 页。本板的 SDNE0 / SDCKE0 由 #7、#8 定 |
| S05 | ~~H742 / H750 / H753 等同封装的球位表没读~~ | [#4][i4] 第 6 条 | [#2][i2] / [mcu §3][r-mcu]：读了七份规格书，H743 / H750 / H753 球图和全部 FMC 引脚位置完全相同 |
| S06 | ~~SDRAM 一侧每个电源球要几个电容，厂家没写~~ | [#6][i6] 第 9 条 | [stref §5.1][r-stref]：参照 MB1246 第 5 页的 14 颗 100 nF；成了布局选择，不再是待核实项 |
| S07 | ~~SDRAM 型号只取自原理图，没对 ISSI 规格书~~ | [#4][i4] 第 4 条 | [#3][i3] 读过本机副本（B 级）；官方原文仍缺，见 U04 |
| S08 | ~~阻焊开窗 0.38 mm、NSMD 是否推荐、嘉立创"开窗 1:1"~~ | [#6][i6]（建议开窗 0.38） | [#10][i10] 定 BGA 阻焊扩展 0（开窗等于焊盘 0.30）；已写进 `docs/rule-profiles/C-bga-065.md`。DS12110 表 217（p.339）只给 Dpad 0.300、Dsm 0.400 典型，没写 NSMD 字样。与 ST 示例的差别见 §7 |
| S09 | ~~辅助脚只是示例、没检查和布局的关系；求解器没考虑 PHY 和连接器位置~~ | [#8][i8] 第 6、7 条 | [#9][i9] 的辅助脚表取代了示例，并约定布局时可在空脚间调换、换了当场报告 |
| S10 | ~~丝印字高下限（FIN-3 的"板厂能不能印清楚没核对"）~~ | [jlc §7-7][r-jlc]；FIN-3 的 Signals | [#5][i5]：嘉立创两个站都写字高 ≥ 1.0 mm。**`design-rules.md` 的 0.8 mm 还没改，收尾阶段要处理** |
| S11 | ~~KiCad 长度规则在命令行 DRC 里是否生效~~ | [#12][i12] 记入项 | 转成 [#14][i14]（未关闭） |
| S12 | ~~区内 0.09 / 区外 0.1016 两套线宽怎么切换、DRC 怎么检查~~ | [#10][i10] | 转成"工具路线"[#19][i19]（未关闭） |

## 5. 已不相关

| 编号 | 原未核对项 | 来源 | 为什么不再相关 |
|---|---|---|---|
| N01 | USB Type-C 的 CC 5.1 kΩ 对规范 | [#4][i4] 第 1 条 | [#9][i9] 不放 USB（放弃 ULPI；串口引到 4 脚排针，不放 USB 转串口） |
| N02 | TC2050-IDC 脚位对 Tag-Connect 官方资料 | [#4][i4] 第 2 条 | [#9][i9] 调试用 2 × 5、1.27 mm 贴片排针（Cortex Debug 脚序） |
| N03 | MB1246 的 USB OTG、RS232、ST-LINK 页没读 | [#4][i4] 第 11 条 | 同上，板上没有这些 |
| N04 | USB3320C 规格书、VDD1.8 是否外供、套 B 的 1.8 / 2.8 / 1.5 V 轨 | [#8][i8] 第 1 条；[pinmux §6.2、§7][r-pinmux] | 套 B 未选，ULPI 放弃（[#9][i9]） |
| N05 | SD 电平转换器（IP4856、ST6G3244ME、TXS02612、TXS0206A）的封装和停产状态；套 C | [#8][i8] 第 2 条；[pinmux §6.3][r-pinmux] | SD 卡只跑 3.3 V、不放电平转换器（[#9][i9]） |
| N06 | 摄像头器件（OV5640、OV2640、MT9V034、AR0130、AR0144）的状态和规格书；24 脚 FPC 摄像头模块的板级供电 | [#8][i8] 第 3、4 条；[pinmux §6.5][r-pinmux] | 套 B 未选，板上不用 DCMI |
| N07 | 未入选器件的未核项：备选 PHY（DP83825I、DP83826、KSZ8081）、CAN（MCP2562FD 只读到 2014 年 Rev A 镜像、TCAN332 / 337、ISO1042 和 SN6505B 隔离方案）、codec（WM8994、CS43L22、SGTL5000）、外挂 SRAM（IS61WV、CY62157）、SDMMC2、eMMC、RGB888、FDCAN2 的可行性只靠求解器 | [#8][i8] 第 8 条；[pinmux §10.2-8、13–16][r-pinmux]；[#9][i9] 第 7 条 | [#9][i9] 定了 LAN8742A、TCAN1042HGVDR、TLV320AIC3104；外挂 SRAM 被 I2C4 和 SAI1 堵死，其余没入选。MCP2562 只借符号（引脚同位，见 V02） |
| N08 | 已淘汰 MCU 型号相关：H7A3 / H7B3 无 Q 型的 GPIO 数 138 对 140、硅版本和勘误；AN5307、AN5935 没打开；H723 / H733 / H725 / H730 的 FMC 宽度没读 | [#2][i2] 第 5、6 条；[#4][i4] 第 6、10 条 | [#2][i2]、[#7][i7] 已选定 H743IIK6，这些型号淘汰 |
| N09 | 已淘汰 SDRAM / Flash 型号相关：Micron 的 SDRAM 停产日期和替代型号、IBIS、镜像 Rev V；"Micron 没有在产的 x32 BGA SDR"是推断；Winbond W9825G2JB 和 W9864G2JB 的状态；ISSI IS42S32400J 手册；H747I-EVAL、H757I-EVAL、H745I-DISCO 用哪颗；EVAL2 的板号；ISSI IS25LP128F；ST 社区文章和 BSP 头文件读的是 WebFetch 摘要；H743I-EVAL 现行 Flash 贴法和封装；F746G-DISCO 上 Micron 与 Winbond 是否同位 | [#3][i3]；[sdram §8][r-sdram]；[qspi §9][r-qspi] | 型号已定 ISSI（[#7][i7]）和 Winbond，这些只是选型期的旁证 |
| N10 | 库存类：TCAN1042HGVDR 的分销库存；各器件价格和库存 | [#9][i9] 第 7 条；地图 Notes | 地图约定不看库存，真打板时用户自己采购 |
| N11 | `SDNE1` / `SDCKE1` 属于 FMC 哪个 bank；UM2198 第 73 页的 QSPI 引脚没看 | [#4][i4] 第 5 条；[pinmux §10.2-5][r-pinmux] | 本板用 SDNE0 / SDCKE0（bank 1）；QSPI 引脚由 #7、#9 定且对表 9、10 核过 |
| N12 | 嘉立创 HDI（6 层 1 + 4 + 1）能否兼容 3313E、价格 | [#6][i6] 第 3 条 | [#6][i6]、[#10][i10] 用标准叠层加狗骨头孔，不走 HDI |
| N13 | 备选稳压器和保护的未读项：TPS563201 的 UVLO、TLV755P 的 PSRR 和压差、LM74700-Q1 只看了订货表、ADI LT3465 是否推荐新设计 | [power §6-11、§6-12][r-power] | [#11][i11] 没选它们 |
| N14 | 90 Ω 差分线宽表（#5）；800 × 480 面板典型值；RMII 联盟规格书时序；ST 的 ±10 mm 和 100 mil 的来历、AN4938 §9.4.1 的"250 ps @ 10 mm"、MB1381 的 Altium 规则本体、MB1246 第 2 页的"90MHz clock" | [#5][i5]；[bus §8][r-bus] | 板上没有 USB，用不到 90 Ω（但以太网 100 Ω 没算，见 U18）；面板不焊；RMII 联盟规格书没被引用；#12 的容差是自定的，不引用 ST 的经验值 |

## 6. 需要用户手动下载的规格书

官网对自动下载返回 403 或反爬时不绕过。"本次试过"指本次的请求结果。

| 器件 | 文档 | 官网页面 | 要核的参数 | 对应 |
|---|---|---|---|---|
| Microchip LAN8742A / LAN8742Ai | 现行数据手册（镜像是 DS00001989A 2015 和 SMSC Rev 1.1 2013） | <https://www.microchip.com/en-us/product/LAN8742A>（本次试过，403） | 脚距和推荐焊盘；VDD1A / VDD2A / VDDIO / VDDCR 范围和外接电容；2、3、7、8、10、11 脚的 strap；REFCLKO 模式与 50 MHz 输出时序；复位时序（25 ms）；CBYPASS 数值；生命周期 | U01 |
| Würth 7499010211A | 数据手册 | 系列页 <https://www.we-online.com/en/components/products/WE-LAN-RJ45>；直链 <https://www.we-online.com/katalog/datasheet/7499010211A.pdf>（本次试过，403） | 引脚定义（TD± / RD± / 中心抽头 / LED）；中心抽头电压；LED 的 VF、IF、极性；封装图和外形 | U02 |
| Hirose FH12-40S-0.5SH（订货号 `FH12-40S-0.5SH(55)`） | 产品图纸和目录 | <https://www.hirose.com/en/product/series/FH12>（本次试过，403） | 订货后缀和在产状态；脚位编号；触点方向和 KiCad 封装是否一致；推荐焊盘和外形 | U03 |
| Hirose DM3AT-SF-PEJM5 | 产品图纸 | Hirose 官网 DM3 系列页（地址没核，请搜索料号） | 8 + 2 个触点的定义（卡检测开关脚、外壳脚）；推荐焊盘；外形 | U03 |
| Same Sky（原 CUI Devices）SJ-3523-SMT | 数据手册和图纸 | <https://www.sameskydevices.com>（请搜索料号；我猜的两个直链 404） | 触点和开关脚定义；推荐焊盘；外形；订货后缀 -TR | U03 |
| ISSI IS42S32800J / IS45S32800J | 数据手册 Rev. C（2025-02-25） | 手册 <https://www.issi.com/WW/pdf/42-45S32800J.pdf>；产品页 <https://www.issi.com/US/product-dram-SDR.shtml>（本次试过，只返回反爬占位页） | 90 球球名表；H3 在 256 Mb 上是否 NC；封装图的球径和推荐焊盘；-6 档 AC 表（tAC、tOH、tDS、tDH）；在产状态；IBIS（<https://www.issi.com/WW/models/ibis/42s16160j-83200j-32800j_b.ibs>，来自 sdram 报告）；IS42S32160F 手册（512 Mb，H3 = A12） | U04、U10、U23 |
| Winbond W25Q128JVEIM | 产品页 | <https://www.winbond.com/hq/product/code-storage-flash-memory/serial-nor-flash/?__locale=en&partNo=W25Q128JV>（JS 渲染，读不到） | 生命周期（规格书 Rev D 已列该料号） | U11 |
| Micron MT25QL128ABA1EW9-0SIT | 零件页；PCN 36228（2026-01-30，Mouser 链接 <https://www.mouser.com/PCN/Micron_Technology_PCN_36228.pdf> 之前超时） | <https://sg.micron.com/products/storage/nor-flash/serial-nor/part-catalog/part-detail/mt25ql128aba1ew9-0sit>（JS 渲染） | 生命周期；128 Mb 在不在停产名单；当前规格书版本；IBIS | U12 |
| Macronix MX25L12833F | 零件页 | <https://www.macronix.com/en-us/products/NOR-Flash/Serial-NOR/Pages/spec.aspx?p=MX25L12833F>（JS 渲染） | "End of Life (EOL)"标签的含义 | U12 |
| ST STM32H743 | RM0433；勘误 ES0392 | <https://www.st.com/resource/en/reference_manual/rm0433-stm32h742-stm32h743753-and-stm32h750-value-line-advanced-armbased-32bit-mcus-stmicroelectronics.pdf>；<https://www.st.com/resource/en/errata_sheet/es0392-stm32h742xig-stm32h743xig-stm32h750xb-stm32h753xi-device-errata-stmicroelectronics.pdf>（`curl` 被拦；RM0433 太大，没试 WebFetch） | FMC SDRAM 章节（RPIPE、SDCLK 分频、时序寄存器）；QUADSPI 章节和勘误条目；SAI1 的主从和 MCLK；启动 | U14 |
| Rocktech RK043FN48H-CT672B；Innolux AT043TN24 | 官方规格书（各版本） | 向面板供应商要。现用镜像：<https://wiki.kewl.org/_media/boards:rk043fn48h-ct672b-v1.0.pdf>、NXP 社区转载的 V.7 | FPC 脚距；40 脚定义（35 脚）；DCLK 采样沿；背光 VF / IF；上电时序 T1–T6 | U16 |
| SD Association | Physical Layer Specification Part 1（最新版） | <https://www.sdcard.org>（返回 403；下载页地址没核） | 50 MHz 高速模式的 tODLY、tOH、tISU、tIH | U15 |

不是规格书、需要用户在浏览器里做的事：

| 事项 | 地址 | 做什么 | 对应 |
|---|---|---|---|
| 嘉立创阻抗计算器 | <https://jlcpcb.com/pcb-impedance-calculator>；国内 `tools.jlc.com` | 6 层、1.6 mm、内层 0.5 oz、外层 1 oz、选 `JLC06161H-3313E`，核 50 Ω 单端（L1 / L6 0.156 mm，L4 0.125 mm）并算以太网 100 Ω 差分 | U18 |
| 嘉立创客服 / DFM | — | 问 U19 的 (a)–(g)；0.15 mm 孔加价金额（U20） | U19、U20 |

## 7. 与已定结论矛盾

**没有发现硬矛盾**，即没有一处规格书数值和已定结论直接冲突。本次逐项对过、全部成立的：#9 的 CAN STB 行为、引脚同位、VIO 3.3 V；codec 的 I2C 地址 0x18、硬复位、散热焊盘接 DRVSS、上电顺序；#11 的 TVS 钳位、LMR51420 绝对最大 38 V、TPS62A02 绝对最大 6.5 V、VCAP 接法、13 个 VDD 球；#10 的"晶振不加区内例外"；PC13 作 PHY 复位的慢速用法。

下面是应当知道的偏离和一处疑似项：

| 项 | 规格书或应用笔记写的 | 已定结论 | 说明 |
|---|---|---|---|
| 阻焊开窗 | DS12110 表 217（p.339）：Dpad 0.300，Dsm 0.400 典型（取决于阻焊对位公差） | [#10][i10]：BGA 阻焊扩展 0（开窗 0.30 = 焊盘） | 有意的偏离，原因是嘉立创"开窗 1:1、开窗到邻线 ≥ 0.09"，C 档第 25 行已写明 ST 的 0.40 会让开窗边到邻线只剩 0.08。备案 |
| 走线阻抗 | AN4938 p.41：50 Ω ± 10% | [#10][i10]：区内线 0.09 mm；[#5][i5] 算出 L1 / L6 约 63 Ω、L4 约 57 Ω | 区内短段高过 ±10%，#5 已指出"出区后要变宽"。备案 |
| 数据线与地址线分层 | AN4938 p.41："place data tracks on the different layers from the address and control lanes, if possible … isolated from each other by at least 5 mm" | [#12][i12] 明确"不采用" | 有意的偏离（"if possible"，0.65 mm BGA 做不到）。备案 |
| **SDCLK 走层** | AN4938 p.41："Placing the clock (SDCLK) signal on an internal layer, minimizes the noise (EMI). Route the clock signal at least 3x of the trace away from other signals" | [#12][i12]：外两圈走 L1，内两圈走 L4。SDCLK 是 PG8（球 H14，第 2 圈），会在 L1 | **#12 没单独讨论这一条**，不确定是有意还是没注意。这是 EMI 建议，不是电气硬要求；建议线序草图验收时一起看，并问用户 |
| **FH12-40S-0.5SH 在产**（疑似，未证实） | 搜索摘要：Octopart 标基础料号 obsolete，(54) 后缀停产，(55) 后缀在 DigiKey 加拿大站现货 0 | [#9][i9] 选了这颗 | 只见到搜索摘要，没打开页面；Hirose 官网 403。页面：<https://octopart.com/part/hirose-electric/FH12-40S-0.5SH>、<https://www.digikey.ca/en/products/detail/hirose-electric-co-ltd/FH12-40S-0-5SH-55/1110328>、<https://www.digikey.ca/en/products/detail/hirose-electric-co-ltd/FH12-40S-0-5SH-54/4283343>。见 U03 |

## 8. 优先级：不核实会不会挡住原理图阶段

**P0：画原理图之前必须核掉**（对应那一页只能靠这份文档，现有来源是镜像或没有；都需要用户下载，可以一次下完）

1. **U01 LAN8742A 官方规格书**：strap 脚、REFCLKO、VDDCR 外接、焊盘。
2. **U02 Würth 7499010211A 规格书**：RJ45 的脚位、LED、中心抽头。
3. **U03 三个连接器**（FH12、DM3AT、SJ-3523）：脚位、开关脚、订货后缀；FH12 的在产状态要先看。

**P1：画原理图的过程中核或选**（Claude 能做的在做对应页时顺手做；需要文件的，用户在审查原理图前补）

- **U05** 待选型件：TVS、防反接 MOS、保险丝、DC 座、LMR51420 后缀、肖特基、电感、磁珠、晶振。Claude 选型并读规格书，型号交用户定。
- **U04** ISSI 官方手册：画 SDRAM 符号时先用 Alliance 官方球表（各家 3.3 V 的 90 球球图相同，已核），RUL-6 的完成标准前补上 ISSI 原文；焊盘推荐值在规则阶段前补上。
- **U06** KiCad 封装焊盘：选封装时对厂家图纸，SDRAM 封装焊盘改成 0.33 mm。
- **U07** ST 原理图位号与网络：抄电路时逐网络对图读。
- **U08、U09** 负载估算和电源环路：选电感电容时用 TI 规格书的公式和示例。
- **U16** 面板：FPC 座的脚序先按现有两份镜像画，用户审查时确认。
- #7 已定的"SDRAM 连 A12、原理图注明 256 Mb 上 H3 是 NC"不需要等 U04，按 #7 做。

**P2：可以带着走**（后面的阶段或真打板才用到）

- 规则和走线前：U18 阻抗（RUL-3，走线前核）、U24 过孔去焊盘（走线 L4 出线前试）、U15 SD 规范。
- 布局阶段：U21 扇出和摆位、U22 面积和平面、U23 时序和信号完整性。
- 只影响真打板：U10–U13 在产状态和硅版本、U14 RM0433 和固件、U17 OPLA、U19–U20 嘉立创工艺和价格、U25 ST 官方板清单。

## 9. 没读到、没把握的来源

- **报告没有读全**：[fanout][r-fanout] 只读了结论、第九至十一节；[stref][r-stref] 只读了第 9–11 节；[bus][r-bus] 只读了第 0–1 节、第 6.3 节后半、第 7–8 节；[pinmux][r-pinmux] 读了第 0、6–10 节；[placement][r-placement] 只读了局限和自检两节；[sdram][r-sdram] 读了第 4–8 节；[mcu][r-mcu] 读了第 5–11 节。没读的部分是推导过程和数字表，我用 `grep` 扫过"未核 / 没读 / 没查 / 推断"这类字样，没发现未列入的项，但没读的部分里可能还有漏掉的。
- **没读 `research/*` 分支里的脚本和 SVG**（pinmux 的 `check_ds.py` 只读了，用来对表 9）。
- **没读 `docs/shape/` 里 layout、power-copper、routing、finishing 四个文件的细则**，只读了 `process.md`、`rules-and-schematic.md` 全文和另外四个文件的规则标题。
- **TI 订货附录的状态是附录日期当天的**（见 §3 各行的日期），产品页的 "ACTIVE" 是本次读到的，两者都不等于库存。
- **Hirose FH12 的在产问题只是搜索摘要**，没打开任何一个页面。
- **U10 里 Alliance 目录页的读取是 WebFetch 的摘要**，不是原文。
- TCAN1042 的 SOIC-8 封装图纸在 PDF 里是矢量图，文字层读不到，没核。
- 把握不大的一点：V07 里"拆行的 12 个手工核"是对着 `pdftotext -raw` 的文本读的，表 9 拆行处的列对齐我是按行内顺序判断的；与 KiCad 符号全部一致，所以出错的可能性小，但不是独立于符号的第二个来源。

[i1]: https://github.com/immorcoding/PCB/issues/1
[i2]: https://github.com/immorcoding/PCB/issues/2
[i3]: https://github.com/immorcoding/PCB/issues/3
[i4]: https://github.com/immorcoding/PCB/issues/4
[i5]: https://github.com/immorcoding/PCB/issues/5
[i6]: https://github.com/immorcoding/PCB/issues/6
[i7]: https://github.com/immorcoding/PCB/issues/7
[i8]: https://github.com/immorcoding/PCB/issues/8
[i9]: https://github.com/immorcoding/PCB/issues/9
[i10]: https://github.com/immorcoding/PCB/issues/10
[i11]: https://github.com/immorcoding/PCB/issues/11
[i12]: https://github.com/immorcoding/PCB/issues/12
[i13]: https://github.com/immorcoding/PCB/issues/13
[i14]: https://github.com/immorcoding/PCB/issues/14
[i18]: https://github.com/immorcoding/PCB/issues/18
[i19]: https://github.com/immorcoding/PCB/issues/19
[r-mcu]: https://github.com/immorcoding/PCB/blob/research/h7-ufbga176-mcu/docs/research/h7-ufbga176-mcu.md
[r-sdram]: https://github.com/immorcoding/PCB/blob/research/sdram-32bit-bga/docs/research/sdram-32bit-bga.md
[r-stref]: https://github.com/immorcoding/PCB/blob/research/st-reference-schematics/docs/research/st-reference-schematics.md
[r-jlc]: https://github.com/immorcoding/PCB/blob/research/jlc-6layer-capability/docs/research/jlc-6layer-capability.md
[r-fanout]: https://github.com/immorcoding/PCB/blob/research/bga-fanout-practice/docs/research/bga-fanout-practice.md
[r-qspi]: https://github.com/immorcoding/PCB/blob/research/qspi-flash/docs/research/qspi-flash.md
[r-pinmux]: https://github.com/immorcoding/PCB/blob/research/h7-peripheral-pinmux/docs/research/h7-peripheral-pinmux.md
[r-power]: https://github.com/immorcoding/PCB/blob/research/power-budget/docs/research/power-budget.md
[r-bus]: https://github.com/immorcoding/PCB/blob/research/bus-timing-budget/docs/research/bus-timing-budget.md
[r-placement]: https://github.com/immorcoding/PCB/blob/research/sdram-placement-study/docs/research/sdram-placement-study/README.md
