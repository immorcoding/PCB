# 六层测试板电源树：事实调研报告

日期：2026-11-16。只调研，没有改仓库任何文件。

标记约定：
- **[读]** = 在规格书/官网页面里直接读到的（给出文档名、表号或页码）。
- **[估]** = 我的估算或推断，不是规格书里的数。
- **[镜像]** = 来自第三方转载，不是厂商原站。
- 规格书的本地副本没有随报告存档，来源链接见第 7 节。

---

## 0. 先说几个会影响决策的发现

1. **背光：两块面板的背光规格差很多，"16 V / 40 mA" 只对 Rocktech 成立。**
   - Rocktech RK043FN48H-CT672B：VF 15.0 / 16.0 / 17.0 V，IF 典型 40 mA，640 mW。[读][镜像] wiki.kewl.org 的 V1.0（2015-03-09）§3.2，无 IF 最大值。
   - Innolux AT043TN24 **V.7**：VL 25.2 / 27.9 / 31.5 V，IL 18 / 20 / 22 mA，典型 0.558 W。[读] Innolux 规格书 A043-24-TT-71，Version 02（2018-04-12）§3.3，NXP 社区转载。
   - 所以背光升压必须能出到 ≥ 31.5 V 并留 OVP 余量，两块面板的 Rset 不同（40 mA 对 20 mA）。TPS61169 的 OVP 36–39 V，能覆盖；TPS923611 这类 30 V 新品覆盖不了 Innolux V.7。
2. **两块面板的 40 脚定义不完全兼容。** [读] 引脚 1–31、34、36 相同（1=背光阴极，2=背光阳极，3=GND，4=VDD，5–28=RGB，29=GND，30=CLK，31=DISP）。差异：32/33 在 RK 上是 HSYNC/VSYNC，在 Innolux 上是 NC（DE 模式）；35 在 RK 是 GND，在 Innolux 是 NC；37–40 在 RK 是 RESET/INT/SCL/SDA（电容触摸），在 Innolux 是 X1/Y1/X2/Y2（4 线电阻触摸）。
3. **"3.3 V 模拟" LDO 不能由 3.3 V 数字轨供电**（3.3 V → 3.3 V 没有压差）。要么 LDO 从 5 V 进，要么用磁珠 + LC 从 3.3 V 数字轨滤波。所以 d 类里 3.3 V 模拟 LDO 的输入只能选 5 V。
4. **STM32H743 UFBGA176+25 没有 VDDLDO 球，也没有 VDD50USB 球**（DS12110 Table 9 注 6、注 8：不引出时 VDDLDO 在内部接 VDD，VDD50USB 在内部接 VDD33USB）。KiCad 自带符号 `MCU_ST_STM32H7:STM32H743IIKx` 的引脚也印证：只有 13 个 VDD、2 个 VCAP、1 个 VDD33_USB、VBAT、PDR_ON、VDDA、VREF+、VREF-、VSSA。
5. **STM32 数据手册分 "rev Y"（≤400 MHz）和 "rev V"（可到 480 MHz）两套电气特性。** 订货号 STM32H743IIK6 买到的是哪一版，要看芯片丝印，我没法确认。下表两套都给了，预算取较大者。
6. **AN4938 和 DS12110 在 tRSTTEMPO 上不一致**：AN4938 Rev 7 图 4 注写"约 2.6 ms"，DS12110 Rev 11 Table 17（rev Y）写典型 377 µs。以数据手册为准，对设计影响很小。

---

## 1. 各电压轨负载预算

### 1.1 3.3 V 数字轨（给所有 3.3 V 数字器件，含 MCU VDD、SDRAM、Flash、PHY+磁性、SD、LCD 逻辑、CAN VIO、LED）

| 器件 / 项目 | 典型 mA | 最大 mA | 出处 / 说明 |
|---|---|---|---|
| STM32H743 VDD（400 MHz，VOS1，外设全开，CoreMark，数据在 ITCM） | 165 | 400 | [读] DS12110 Rev 11 Table 20（rev Y，p.110）：400 MHz VOS1 外设全开 Typ 165；Max TJ=25 °C 220、85 °C 400、105 °C 500、125 °C 840。rev V 对应 Table 119（p.215）：Typ 167；Max 256 / 327 / 416 / 536。最大值取 TJ=85 °C 的 400（rev Y 较大者）。注：这是 VDD（含内部 LDO 给内核的电流），测试时 I/O 为模拟输入，不含 I/O 外部负载电流。Typ 对应的结温表头没写，我按 25 °C 理解 [估] |
| FMC / QSPI / SDMMC 等 I/O 翻转电流（不含在上一行） | 20 | 50 | [估] 32 根 DQ × ~10 pF × 3.3 V × 约 50 MHz 翻转，约 53 mA 满翻转，典型按 40 % 概率 |
| SDRAM IS42S32800J-6BLI | 100 | 190 | 最大 [读][镜像] ISSI Rev B1（2021-12）DC Characteristics 1：-6 档 Idd1=140、Idd4（BL=4，CL=3，所有 bank 激活，tck 最小）=190、Idd5（自刷新）=180 mA，输出开路，只给最大值。典型 [估]：H743 的 SDCLK 一般 ≤100 MHz，取 190 × 100/166 / 1.3 ≈ 90，进位到 100 |
| Flash W25Q128JV | 12 | 25 | [读] Winbond W25Q128JV Rev F（2018-03-27）§9.4 p.62：读 104 MHz 双/四线 ICC3 典型 12、最大 20；写状态/页编程/擦除 ICC4–7 典型 20、最大 25 |
| 以太网 PHY LAN8742A + 磁性（单 3.3 V 供电，内部 1.2 V 稳压开） | 102 | 150 | 典型 [读][镜像] SMSC LAN8742A Rev 1.1（2013-05-21）Table 5.5（REF_CLK 输出模式、稳压开）"含磁性"一列：100BASE-TX 有流量 102 mA，10BASE-T 有流量 139 mA，复位态 31 mA。REF_CLK 输入模式（Table 5.3）为 92 / 129 mA。规格书只给典型值；最大取 139 加约 8 % 余量 [估] |
| SD 卡（四线，3.3 V） | 100 | 200 | [读][镜像] SD Physical Layer Simplified Spec v3.01（2010，utexas.edu 转载）：§4.2.3.1 默认速度 / SDR12 卡工作电流 <100 mA（XPC=0）或 <150 mA（XPC=1）；§4.3.10.4 Function Group 4 电流限制默认 200 mA（可经 CMD6 设到 400/600/800 mA，仅 SDR50/SDR104/DDR50）；CSD 的 VDD_R/W_CURR_MAX 编码最大 200 mA（Table 5-11）。"按规范上限"取 200；典型取默认速度上限 100 |
| LCD 逻辑 VDD（含 RK 触摸 IC） | 20 | 40 | Innolux V.7 IVDD 典型 17 mA @3.3 V（规格书 p.6，无最大值）[读]；RK043FN48H 的面板功耗在规格书里写 T.B.D（§3.1）[读][镜像]，触摸 IC 电流未给。按 Innolux 的 17 mA 加触摸取 20 / 40 [估] |
| CAN 收发器 VIO | 0.09 | 0.3 | [读] TCAN1042 SLLSES7D Table 7.7：IIO 正常模式典型 90 µA，最大 300 µA |
| 音频 codec IOVDD | 0.1 | 0.1 | [估] 规格书只给 IDVDD 和 IDRVDD+IAVDD，没有单独的 IOVDD 电流；数字 I/O 电流可忽略 |
| 4 颗 LED（2 板载 + 2 RJ45 指示灯） | 12 | 32 | [估] 每颗 3 mA 典型 / 8 mA 最大，由限流电阻定。Würth 7499010211A 规格书我没读到（见未核对项） |
| 1.8 V LDO 的输入电流（= 1.8 V 负载，见 1.3） | 5.7 | 12 | 来自 1.3 节 |
| 其他（上拉、晶振、SWD） | 2 | 5 | [估] |
| **合计** | **≈ 540** | **≈ 1105** | |
| 建议稳压器额定电流（最大 × 1.5） | | **≈ 1.7 A → 取 2 A 级** | 若按 TJ=105 °C 取 MCU 500 mA，则最大 ≈ 1.2 A，× 1.5 ≈ 1.8 A，仍是 2 A 级 |

### 1.2 3.3 V 模拟轨（codec AVDD + DRVDD，MCU VDDA + VREF+）

| 器件 / 项目 | 典型 mA | 最大 mA | 出处 / 说明 |
|---|---|---|---|
| TLV320AIC3104 AVDD + DRVDD 静态：立体声 DAC → 单端耳机、无信号 | 6.7 | — | [读] SLAS510G Table 8.5（p.12）IDRVDD+IAVDD = 6.7 mA（DVDD 另算 2.3 mA）。该表只给典型值，无最大值 |
| 同上：立体声 ADC 录音 48 ksps | 4.31 | — | [读] 同表 |
| 同上：PLL 开启额外电流 | 1.4 | — | [读] 同表 |
| AIC3104 静态小计（DAC+ADC+PLL 同时开） | 12.4 | 20 | 典型 [读] 三项相加；最大 [估]（典型 × 1.6） |
| AIC3104 耳机负载动态电流 | 10 | 40 | [读] 每路最大输出功率：16 Ω 时 30 mW，32 Ω 时 15 mW（§8.5，§10.3.7）；耳机最小负载 16 Ω（Table 8.3）。电流 [估]：单端 AB 类，每路平均电源电流 ≈ Ipk/π；30 mW/16 Ω 时 Ipk ≈ 61 mA → 每路约 19 mA，两路约 39 mA。典型按日常听音取 10 |
| 线路输入 / 线路输出 | ≈ 0 | ≈ 0 | [读] 线路输出最小负载 10 kΩ（Table 8.3），可忽略 |
| MCU VDDA（含 3 个 ADC、VREFBUF） | 2 | 6 | [读] DS12110 rev V Table 174：ADC 消耗 VDDA 最大约 1.44 mA/个（16 位 25 MHz，BOOST=11 差分）；VREFBUF 自耗 16 µA 典型、30 µA 最大（Table 81）。rev Y 的 ADC 电流行我没提取到。总量 [估]：典型 1 个 ADC 在跑，最大 3 个 ADC + DAC/比较器余量 |
| **合计** | **≈ 24** | **≈ 66** | |
| 建议稳压器额定电流（最大 × 1.5） | | **≈ 100 mA → 取 150–300 mA 级** | 候选 LDO 为 250–300 mA，有富余 |

### 1.3 1.8 V 轨（只有 codec DVDD）

| 项目 | 典型 mA | 最大 mA | 出处 / 说明 |
|---|---|---|---|
| AIC3104 DVDD：DAC 回放 48 ksps | 2.3 | — | [读] SLAS510G Table 8.5 |
| AIC3104 DVDD：ADC 录音 48 ksps | 2.45 | — | [读] 同表（注 6：PLL 开时另加） |
| PLL 开启额外 DVDD 电流 | 0.9 | — | [读] 同表 |
| **合计** | **≈ 5.7** | **≈ 12** | 典型三项相加（DAC 与 ADC 同时开时两项有重叠，偏保守）；最大 [估] |
| 建议稳压器额定电流（最大 × 1.5） | | ≈ 20 mA | 实际选 250 mA 级 LDO 即可，量不是约束 |

DVDD 范围 1.525–1.95 V，标称 1.8 V [读] Table 8.3。

### 1.4 5 V 轨

| 项目 | 典型 mA | 最大 mA | 出处 / 说明 |
|---|---|---|---|
| 3.3 V 数字轨降压器的输入电流 | 395 | 850 | [估] 540 mA × 3.3 V / (0.90 × 5.0 V)；最大按 1105 mA × 3.3 V / (0.90 × 4.75 V) |
| 3.3 V 模拟 LDO 的输入电流 | 24 | 66 | LDO 输入电流 = 输出电流（+ 静态电流，可忽略） |
| 背光升压输入电流 | 150 | 190 | [估] RK：640 mW / 0.85 / 5 V ≈ 150；最大按 Innolux 31.5 V × 22 mA = 0.69 W 或 RK 17 V × 44 mA（IF 无最大值，取 +10 %）≈ 0.75 W，除以 0.82 和 4.75 V |
| CAN 收发器 VCC（5 V） | 10 | 70 | [读] TCAN1042 Table 7.6：平均功耗 52 mW（500 kbps，25 % 显性）→ 约 10 mA；最坏平均 124 mW（5.5 V，1 Mbps，50 % 显性，50 Ω）→ 约 22 mA。Table 7.7：显性 60 Ω 典型 40、最大 70 mA；隐性 1.5 / 2.5 mA。峰值取 70 |
| **合计** | **≈ 580** | **≈ 1175** | |
| 建议稳压器额定电流（最大 × 1.5） | | **≈ 1.8 A → 取 2 A 级** | 12 V 侧输入电流 [估]：5 V 轨最大功率约 5.9 W，除以 0.9 效率再除以输入电压：7 V 时 ≈ 0.94 A，12 V 时 ≈ 0.55 A，24 V 时 ≈ 0.27 A。保险丝要按 7 V 时的电流选 |

### 1.5 背光（LED 串，由升压恒流驱动）

| 面板 | 电压 | 电流 | 功率 | 出处 |
|---|---|---|---|---|
| RK043FN48H-CT672B | 15.0 / 16.0 / 17.0 V | 典型 40 mA（无最小/最大） | 640 mW 典型 | [读][镜像] wiki.kewl.org V1.0，§3.2 |
| AT043TN24 V.7 | 25.2 / 27.9 / 31.5 V | 18 / 20 / 22 mA | 558 mW 典型 | [读] Innolux A043-24-TT-71 Version 02，§3.3；单颗 LED 绝对最大 IF 25 mA，反向 1.2 V（§绝对最大额定值） |

按 TPS61169 的 FB 参考 204 mV（188–220 mV）：Rset = 204 mV / I，40 mA 时 5.1 Ω，20 mA 时 10 Ω（10.2 Ω）。 [估，公式出自规格书 §7.3 ILED = VFB / Rset]

---

## 2. 稳压器候选

所有电压/电流/频率/封装均来自对应 TI 数据手册（本地副本 `ds\*.pdf`），"在产"状态来自 2026-11-16 通过 WebFetch 读到的 ti.com 产品页（Active）。KiCad 库查询方式：Python 解析 `D:\KiCad\share\kicad\symbols\*.kicad_sym` 取符号的 Footprint 属性，再检查 `D:\KiCad\share\kicad\footprints\<库>.pretty\<名>.kicad_mod` 是否存在（均存在）。

### 2a. 12 V（7–24 V）→ 5 V，1–2 A 同步降压

| 项目 | **LMR51420**（首选） | TPS54202 | LMR33620 |
|---|---|---|---|
| 状态（ti.com） | Active，页面未提替代品 | Active；页面提示有新版 TPS542021（4.5–30 V，2 A） | Active；页面列出 LMR43620 等相近品 |
| 输入范围 [读] | 4.5–36 V，绝对最大 38 V | 4.5–28 V，绝对最大 30 V | 3.8–36 V，绝对最大 38 V |
| 输出电流 | 2 A | 2 A | 2 A |
| 开关频率 [读] | 500 kHz 或 1.1 MHz 固定（后缀 X/Y，按表顺序推断 X=500 kHz，Y=1.1 MHz，表格列错位）；PFM 或强制 PWM（后缀 F） | 500 kHz 固定，带展频，Eco-mode | 400 kHz / 1.4 MHz / 2.1 MHz（A/B/C 变体） |
| 封装 / 脚距 | SOT-23-THN（DDC）6 脚，0.95 mm | SOT-23-THN（DDC）6 脚，0.95 mm | HSOIC-8（DDA）1.27 mm，带散热焊盘；另有 VQFN-HR 12 脚 2×3 mm，0.5 mm 脚距（RNX） |
| 外置件 | 外置电感；同步整流，**无需外置续流管**；自举电容、反馈电阻 | 同左 | 同左 |
| 电感量 [估] | 12 V→5 V、500 kHz、2 A 时约 10–15 µH（TPS54202 规格书设计示例算出最小 13.7 µH，同类参考） | 10–15 µH | 随频率变，规格书有表 |
| KiCad 符号 | **无** `LMR51420`；`Regulator_Switching:LMR51430`（3 A，同封装）引脚完全一致（1 GND、2 SW、3 VIN、4 FB、5 EN、6 CB），规格书写明 LMR51420 与 TPS54202 / TPS54302 引脚兼容，可复制改值 | `Regulator_Switching:TPS54202DDC`（引脚 GND/SW/VIN/FB/EN/BOOT） | `Regulator_Switching:LMR33620ADDA / BDDA / CDDA` |
| KiCad 封装 | `Package_TO_SOT_SMD:SOT-23-6` | 同左 | `Package_SO:Texas_HSOP-8-1EP_3.9x4.9mm_P1.27mm_ThermalVias` |
| 规格书推荐布局图 [读] | 有（§9.4.2 Layout Example） | 有（§7.4.2） | 有（§10.2） |

选首选的理由：绝对最大 38 V，适合 24 V 输入加瞬态；SOT-23-6 好焊；与 TPS54202 引脚兼容，一个符号两个器件可换。TPS54202 的绝对最大只有 30 V，24 V 输入加 TVS 钳位后余量不够。LMR33620 封装大、散热好、频率选择多，但占板面积大。另一个可选：TPS62933（3.8–30 V，3 A，SOT583-8，0.5 mm 脚距，KiCad 有符号 `TPS62933` 和封装 `SOT-583-8`，Active），绝对最大 32 V。

### 2b / 2c. 5 V → 3.3 V，约 1.5–2 A 同步降压（c 类与 b 类同一批，已覆盖）

| 项目 | **TPS62A02**（首选，用 DDC 封装版 TPS62A02PDDCR） | TPS563201 | TPS62130A |
|---|---|---|---|
| 状态（ti.com） | Active，页面列出 TPS62A02A（强制 PWM）、TPS62A01（1 A） | Active；页面提示新版 TPS563203（4.2–17 V，3 A，SOT563，引脚不同） | Active；页面提示新版 TPS62903（引脚不同） |
| 输入范围 [读] | 2.5–5.5 V，绝对最大 6.5 V | 4.5–17 V，绝对最大 19 V | 3–17 V |
| 输出电流 | 2 A（TPS62A02；高端峰值限流 2.7–3.4 A） | 3 A | 3 A |
| 开关频率 [读] | 2.4 MHz（PWM 模式），轻载 PSM | 580 kHz，D-CAP2，TPS563201 是脉冲跳跃，TPS563208 是连续模式 | 2.5 MHz，DCS-Control |
| 封装 / 脚距 | SOT-23-THN（DDC）6 脚 0.95 mm；也有 SOT-563（DRL）0.5 mm 版 | SOT-23-THN（DDC）6 脚 0.95 mm | VQFN-16（RGT）3×3 mm，0.5 mm 脚距，带散热焊盘 |
| 外置件 | 外置电感（规格书标称有效电感 1.0 µH）；输出电容最小 10 µF，示例 22 µF；同步整流，**无续流管**；内部软启动约 1 ms（"EN 高到 VFB=0.56 V"）[读] | 外置电感；同步整流，无续流管；软启动 1.0 ms | 外置电感；同步整流，无续流管；软启动脚可编程 |
| KiCad 符号 | `Regulator_Switching:TPS62A02PDDC`（引脚 1 EN、2 GND、3 SW、4 VIN、5 PG、6 FB，与规格书 DDC 引脚表一致）；另有 `TPS62A02DRL` | `Regulator_Switching:TPS563201` / `TPS563208` | `Regulator_Switching:TPS62130A` |
| KiCad 封装 | `Package_TO_SOT_SMD:SOT-23-6`（DDC）/ `SOT-563`（DRL） | `Package_TO_SOT_SMD:SOT-23-6` | `Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.68x1.68mm_ThermalVias` |
| 规格书推荐布局图 [读] | 有（§8.4.2） | 有（§7.4.2） | 有（§11.2） |

首选理由：电流刚好 2 A，对应 1.5–2 A 的需求；2.4 MHz 电感小；SOT-23-6 脚距 0.95 mm 好焊；KiCad 符号和封装现成。注意它的输入绝对最大只有 6.5 V，只能接 5 V 轨，5 V 轨不能有过冲。TPS563201 的最小输入 4.5 V，5 V 轨掉到 4.5 V 附近会出问题（TPS563201 的 UVLO 数值我没读）。TPS62130A 是 QFN，贴装难度高一档，但 3 A 余量大。

### 2d. 低噪声 LDO

3.3 V 模拟（5 V 进，约 100–150 mA）和 1.8 V（3.3 V 进，几十 mA）：

| 项目 | **TPS7A20**（首选） | LP5907 | TLV755P |
|---|---|---|---|
| 状态（ti.com） | Active | Active；规格书首页写"更新的产品见 TPS7A20" | Active |
| 输入范围 [读] | 1.6–6.0 V | 2.2–5.5 V | 1.45–5.5 V |
| 输出电流 | 300 mA | 250 mA | 500 mA |
| 噪声 [读] | 7 µVrms（10 Hz–100 kHz，300 mA，无旁路电容） | < 6.5 µVrms（规格书表中 eN 在 IOUT=1 mA 时典型 10 µVrms，注意首页写 <6.5） | 71.5 µVrms（ti.com 页面），**不算低噪声**，只适合 1.8 V 数字 DVDD |
| PSRR [读] | 95 dB @1 kHz | 82 dB @1 kHz | 未读 |
| 压差 [读] | 300 mA 时最大 140 mV（3.3 V 输出）；DBV 封装 145 mV | 250 mA 时典型 120 mV，最大 200 mV（DSBGA 条件） | 未读 |
| 封装 / 脚距 | SOT-23-5（DBV）0.95 mm；另有 X2SON-4 0.4 mm 和 DSBGA，**这两种不能用** | SOT-23-5（DBV）0.95 mm；另有 X2SON、DSBGA，不能用 | SOT-23-5（DBV）0.95 mm；WSON-6（DRV）0.65 mm；X2SON，不能用 |
| 订货号（定电压） | 3.3 V：TPS7A2033PDBVR；1.8 V：TPS7A2018PDBVR（"P" 为带输出放电版，后缀 DBV = SOT-23-5；订货表的封装列在我提取的文本里错位，靠型号后缀判断） | LP5907MFX-3.3/NOPB；LP5907MFX-1.8/NOPB | TLV75518PDBVR 等（1.8 V 版） |
| 外置件 | 输入输出各 1 µF 陶瓷，无需旁路电容；无电感 | 1 µF / 1 µF | 同类 |
| KiCad 符号 | `Regulator_Linear:TPS7A20xxxDBV`（通用符号，引脚 1 IN、2 GND、3 EN、4 NC、5 OUT） | `Regulator_Linear:LP5907MFX-3.3`、`LP5907MFX-1.8`（引脚相同） | `Regulator_Linear:TLV75518PDBV` 等 |
| KiCad 封装 | `Package_TO_SOT_SMD:SOT-23-5` | 同左 | 同左（DBV）；`Package_SON:WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm`（DRV） |
| 规格书推荐布局图 [读] | 有（§7.4.2） | 有（§7.4.2） | 有（含 DBV） |

发热核对 [估]：5 V → 3.3 V 在 150 mA 时 LDO 耗散 (5−3.3) × 0.15 = 0.255 W；DBV（SOT-23-5）结到环境热阻 [读]：TPS7A20 为 187.1 °C/W，LP5907 为 193.4 °C/W（热信息表，我的文本提取里列有错位，按各自第一行 DBV 列判断）→ 150 mA 时温升约 48–49 °C（JEDEC 板），环境 85 °C 时结温会到约 134 °C，超过 125 °C 上限。但按 1.2 节的预算，最大负载只有约 66 mA，耗散 0.11 W，温升约 21 °C，典型 24 mA 时 0.04 W，都没有问题；只有当你真的要用满 150 mA 时才需要铺铜散热。

建议：3.3 V 模拟用 TPS7A2033（若想选更成熟的用 LP5907MFX-3.3）；1.8 V 用 TPS7A2018 或 LP5907MFX-1.8，输入来自 3.3 V 数字轨。

### 2e. 白光 LED 背光升压恒流驱动（5 V 进）

| 项目 | **TPS61169**（已知候选，核对通过） | TPS61165 | LT3465（ADI） |
|---|---|---|---|
| 状态 | Active（ti.com）；页面提示新版 TPS923610 / TPS923611（引脚不同） | Active；页面提示新版 TPS923611（30 V，1.8 A） | ADI 页面显示 "PRODUCTION"，没写是否推荐新设计 |
| 输入范围 | 2.7–5.5 V | 3–18 V | 2.7–16 V |
| 输出 / 开路 LED 保护 [读] | 驱动 LED 串最高 38 V；OVP 36 / 37.5 / 39 V（Table 7.5） | 38 V 开路 LED 保护（OVP 37–38 V） | 最大输出 30 V（ADI 页面），**不够 Innolux V.7 的 31.5 V** |
| 开关 / 电流限制 [读] | 1.2 MHz（0.75–1.5）；内部开关 40 V；限流 1.2 / 1.8 / 2.4 A；Rds(on) 0.35 Ω 典型 | 1.2 MHz，限流 0.96–1.2 A | 1.2 MHz（LT3465A 为 2.4 MHz） |
| 参考电压 / 设电流 | FB 204 mV（188–220）；Rset = 204 mV / I | FB 200 mV；Rset = 200 mV / I | 未读 |
| PWM 调光 [读] | CTRL 脚 PWM，推荐 5–100 kHz，占空比 1–100 %，CTRL 低 >2.5 ms 关断；不对 LED 电流做斩波，无音频噪声 | CTRL 脚 PWM（推荐 6.5–100 kHz）或 EasyScale 单线数字 | 未读 |
| 封装 / 脚距 | SC70-5（DCK），0.65 mm，2.0 × 1.25 mm（体型） | SOT-23-6（DBV）0.95 mm；WSON-6 2×2 mm 0.65 mm（DRV） | TSOT-23-6 |
| 外置件 | 外置电感（推荐 4.7–10 µH）+ **外置肖特基二极管**（耐压须超过 OVP）+ 输出电容（1–10 µF，建议 50 V 级） | 外置电感 + 肖特基 + **COMP 电容**（外部补偿） | 外置电感 + 肖特基 |
| 补偿 | 内部补偿 | 外部 COMP 电容 | 未读 |
| KiCad 符号 | **无** | `Driver_LED:TPS61165DBV`（引脚 1 VIN、2 CTRL、3 SW、4 GND、5 COMP、6 FB，与规格书 DBV 引脚表一致）、`TPS61165DRV` | `Driver_LED:LT3465`、`LT3465A` |
| KiCad 封装 | `Package_TO_SOT_SMD:SOT-353_SC-70-5` 存在（可手动配符号） | `Package_TO_SOT_SMD:SOT-23-6`；`Package_SON:WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm` | 未查 |
| 规格书推荐布局图 [读] | 有（§7.5.2） | 有（§11.2） | 未读 |

核对 TPS61169：Active，输入 2.7–5.5 V，OVP 约 37.5 V，输出可到 38 V，覆盖 RK（16 V）和 Innolux V.7（至 31.5 V，需 OVP 余量 ≥ 36 V 满足）；5 V 输入驱动 31.5 V × 22 mA 时输入电流约 170 mA，远低于限流 1.2 A。缺点：KiCad 无符号；SC70-5 体积小。TPS61165 的 KiCad 符号现成、封装大一点，但要外加 COMP 电容。

### 2f. 12 V 输入端保护（简短，器件未逐一读规格书）

常见做法（从输入端往里）：
1. **保险丝**：贴片保险丝或 PTC，按 7 V 时的输入电流选（见 1.4 节：最大约 0.94 A，取 2 A 级）。KiCad 有 `Fuse:Fuse_1206_3216Metric` 等封装。[估]
2. **防反接**，三种方案：
   - 串联肖特基：最简单，压降 0.4–0.5 V，7 V 输入时损失明显。
   - 串联 P-MOSFET + 栅极稳压管：压降小，但 24 V 输入时栅极要钳位。
   - **LM74700-Q1** 理想二极管控制器 + 外置 N-MOSFET：[读] SNOSD17G，输入 3.2–65 V，反向耐压 -65 V，20 mV 压降，SOT-23-6（DBV）/ SOT-23-8；订货表 Active；KiCad 有符号 `Power_Management:LM74700`（引脚 1 VCAP、2 GND、3 EN、4 CATHODE、5 GATE、6 ANODE）和封装 SOT-23-6。无过压保护。
3. **过压 / 浪涌**：
   - TVS：关断电压须 ≥ 24 V，如 SMBJ24A / SMAJ24A 类；封装 `Diode_SMD:D_SMB` / `D_SMA` 存在，符号用 `Device:D_TVS`。我凭记忆认为 SMBJ24A 的最大钳位约 38.9 V（15.4 A 时），略高于 LMR51420 的绝对最大 38 V；实际浪涌电流受源阻抗和保险丝限制，钳位会低一些，但要核对。**这条没有读到规格书。**
   - eFuse：**TPS2663x**（[读] SLVSE94G：4.5–60 V，67 V 绝对最大，6 A，31 mΩ，可配合外置 N-FET 做反接保护，有 35 V / 39 V 固定过压钳位变体 TPS26633 / TPS26635 或可调过压切断 TPS26630 / TPS26631；封装 VQFN-24 4×4 mm 0.5 mm 脚距（RGE）或 HTSSOP-20（PWP）；KiCad 有 `TPS26630RGE`、`TPS26631PWP` 等符号）。对测试板偏重。
   - 不要用 TPS25947：[读] 输入 2.7–23 V，绝对最大 28 V，24 V 输入超出推荐范围。

---

## 3. STM32H743 电源脚怎么接（UFBGA176+25）

来源：DS12110 Rev 11（2026-01）§3.5、§6.1.6、§6.3、Table 9/14/15/16/17；AN4938 Rev 7 §2。引脚号来自 KiCad 符号 `STM32H743IIKx`，我用 DS12110 Figure 10 的球图文本交叉核对过 VDD / VCAP / VDD33USB 的位置。

| 脚 | 本封装球 | 要求 [读] | 去耦 [读] |
|---|---|---|---|
| VDD | 13 个：C5 C7 C8 C9 F3 G3 G13 J12 J13 K4 N8 N9 N10 | 1.62–3.6 V（Table 14）。接 3.3 V 数字轨 | DS12110 Figure 15 / AN4938 §2.2：每个 VDD 脚 100 nF 陶瓷，另加整个封装共用 1 个 ≥4.7 µF（钽或陶瓷）。即 13 × 100 nF + 1 × 4.7 µF。电容容差 ±20 % 可接受（Figure 15 注 2）。电容要尽量靠近或贴在球下方背面（BGA 建议放在背面，AN4938 §9.3，图 21、22） |
| VDDLDO | **无此球**（内部接 VDD） | Table 14：VDDLDO ≤ VDD，1.62–3.6 V；本封装自动满足 | 不用单独处理；DS Figure 15 的 "VDDLDO 4.7 µF" 由 VDD 的 4.7 µF 覆盖 |
| VCAP | F13、M10（共 2 个） | 内核 LDO 输出（VOS 档位决定 1.0–1.35 V）；LDO 一直开（AN4938 §2.1.4） | Table 15：每个 VCAP 脚 2.2 µF（±20 % 可接受），ESR < 100 mΩ；两个 VCAP 脚相连；不要再接别的负载。若旁路内部稳压器，则换成 2 × 100 nF |
| VDDA / VSSA | R1 / M1 | 1.62–3.6 V；用 ADC 或比较器 ≥ 1.62 V，用 DAC ≥ 1.8 V，用 OPAMP ≥ 2.0 V，用 VREFBUF ≥ 1.8 V；不用任何模拟外设可到 0 V（Table 14）。可从 VDD 经磁珠供电（AN4938 §2.2 末尾）；参考设计用 0 Ω 做 VDDA 与 VREF+ 的星形连接，另有磁珠 FCM1608KF-601T03（Table 9） | 100 nF 陶瓷 + 1 µF（Figure 15，Figure 40/41） |
| VREF+ / VREF- | P1 / N1 | 可接 VDDA。VREF+ 必须 ≤ VDDA；用 ADC 且 VDDA > 2 V 时 VREF+ ≥ 2 V，否则 ≥ 1.62 V（AN4938 §2.2）。VREF- 接 VSSA（本封装才有这个球）。可经约 47 Ω 电阻从 VDDA 取（AN4938）。若用内部 VREFBUF：负载电容 0.5 / 1 / 1.5 µF，ESR ≤ 2 Ω（Table 81，p.174），VDDA 3.3 V 时 VSCALE=000 输出 2.5 V 的最低 VDDA 为 2.8 V | 不单独供电时：1 µF // 100 nF 放在 VREF+/VDDA 共用节点（Figure 41）；VREF+ 单独供电时：VREF+ 一组 1 µF // 100 nF，VDDA 另一组 1 µF // 100 nF（Figure 40） |
| VBAT | C1 | 1.2–3.6 V。无电池时**必须**接到外部电源，如经 100 nF 接 VDD（AN4938 §2.2）。若接电池且 VDD 上电快于 tRSTTEMPO，可能经内部二极管向 VBAT 倒灌电流；电池扛不住就串低压降二极管（AN4938 §2.1.3） | 100 nF |
| VDD33USB | H13 | Table 14：USB 使用时 3.0–3.6 V；**USB 不使用时 0–3.6 V**。AN4938 §2.1.2：不用 USB 时 GPIO 按 VDD 范围工作。ST 社区 FAQ 727887（WebFetch 读到）：不用 USB 时 VDD33USB 接 VDD，不影响功耗，固件里关闭 VDD33USB 电平检测并保持 USB PHY 关闭，DP/DM 不用 | AN4938 §2.2：100 nF + 1 µF（1 µF 的 ESR ≤ 600 mΩ），两种供电方式都需要 |
| VDD50USB | **无此球**（内部接 VDD33USB） | 本封装不用处理。FAQ 727887：该脚（有此脚的封装上）禁止悬空，不用时接 VDD33USB | 不适用 |
| PDR_ON | C6 | AN4938 §2.3.5：接 VDD（拉高）= 内部电源监视开；接 VSS = 关，此时必须有外部监视器 | 无 |

**上电 / 掉电时序 [读]**（DS12110 §3.5.1，Figure 3；AN4938 §2.1.2 Figure 2）：
- VDD < 1 V 时，其他电源（VDDA、VDD33USB、VDD50USB）必须保持 < VDD + 300 mV。
- VDD > 1 V 后，各电源相互独立。
- 掉电时，VDD 可以暂时低于其他电源，前提是提供给芯片的能量低于 1 mJ。
- Table 16（p.106）：VDD、VDDA、VDDUSB 的上升时间下限 0 µs/V、上限不限；下降时间下限 10 µs/V、上限不限。
- Table 17（p.107）：tRSTTEMPO 典型 377 µs（复位释放后的延时）；BOR0/POR/PDR 上升沿 1.62–1.71 V（典型 1.67 V），下降沿 1.58–1.68 V（典型 1.62 V）。
- VDDLDO 没有独立球，不存在 VDDLDO 与 VDD 的先后问题。

**对本板的含义 [估，推断自上面的 VDD<1 V 规则]**：若 VDDA 由从 5 V 取电的 LDO 提供，LDO 的启动比 3.3 V 降压器的软启动快（LP5907 / TPS7A20 数百 µs，TPS62A02 约 1 ms），VDDA 可能在 VDD 还没到 1 V 时就超过 VDD + 300 mV，违反上面第一条。做法：把模拟 LDO 的 EN 接到 3.3 V 数字轨（或其 PG）上，EN 门限高于 1 V，等 VDD 过 1 V 后再启动；或者把 VDDA 直接经磁珠接到 VDD。

---

## 4. 其他器件的电源要求

### 4.1 LAN8742A（SMSC Rev 1.1，2013-05-21，DESY 镜像；Microchip 官网 403）

| 脚 | 范围 / 要求 [读] |
|---|---|
| VDDIO | 1.8–3.3 V 可变 I/O 电源（Table 2.7）；上电后与磁性电源一样须保持在标称值 ±10 % 内（§5.2）。本板接 3.3 V |
| VDD1A | +3.3 V 模拟，通道 1；3.0–3.6 V（§5.2）；图 3.23 单电源接法：经铁氧体磁珠 + CBYPASS 供电 |
| VDD2A | +3.3 V 模拟，通道 2，**同时给内部 1.2 V 稳压器供电**（Table 2.7）；3.0–3.6 V |
| VDDCR | 内部 1.2 V 稳压器输出（默认开，REGOFF 悬空或接地）：规格书要求 **1 µF + 470 pF 并联到地**（Table 2.7、图 3.21）。若要外供 1.2 V，需把 REGOFF 脚（与 LED1 共用）经上拉电阻接 VDD2A，且 VDDIO 须 ≥ 标称的 80 %（3.3 V 时 2.64 V）之后才可给 VDDCR 加压（§3.7.3）；本板不用 |
| 磁性中心抽头 | 2.25–3.6 V（§5.2）；单电源时与 VDD1A/VDD2A 同接 3.3 V（图 3.23），双电源时可 2.5–3.3 V（图 3.24） |
| 去耦电容值 | 图 3.20–3.24 里只写 CBYPASS，**没给数值**，只有 VDDCR 的 1 µF + 470 pF 给了数值（未核对项） |

**上电顺序 [读]**（§5.6.2，Table 5.10）：VDDIO、VDD1A、VDD2A 和磁性电源可以按任意顺序上电，只要都在 tpon（最大 50 ms）内到达工作电平；掉电各路在 tpoff（最大 500 ms）内降到 0。上电后**必须**做硬件复位（§5.6.3，Table 5.11）：所有外部电源到工作电平之后，nRST 至少再保持 25 ms（tpurstd）才能释放；nRST 低脉宽 ≥ 100 µs（trstia）；配置脚在 nRST 释放前 ≥ 200 ns 建立（tcss），释放后保持 ≥ 1 ns（tcsh）。nRST 释放必须单调。仅在关闭内部稳压器时才有 VDDIO / VDDCR 的先后要求（VDDIO 须同时或晚于 VDDCR）。

### 4.2 TLV320AIC3104（SLAS510G，2021-02）

| 脚 | 范围 [读] |
|---|---|
| AVDD（脚 25） | 模拟 DAC 电源，2.7–3.6 V，标称 3.3 V（Table 7-1、Table 8.3） |
| DRVDD（脚 18） | 模拟 ADC 与输出驱动电源，2.7–3.6 V |
| DRVDD（脚 24） | 模拟输出驱动电源，2.7–3.6 V |
| DVDD（脚 32） | 数字内核，1.525–1.95 V，标称 1.8 V |
| IOVDD（脚 7） | 数字 I/O，1.1–3.6 V |
| 去耦 | Figure 11-1 典型电路：AVDD、DRVDD 各 0.1 µF + 1 µF；DVDD、IOVDD 各 0.1 µF + 1 µF（图上写成 0.1 mF / 1 mF，是 PDF 提取时 µ 丢失，按量级判断为 µF）；AVDD 上另有 10 µF |

**上电顺序 [读]**（§12，Figure 12-1，Table 12-1，p.91）：规格书说器件"对上电顺序极为宽容"，但最稳妥的顺序是：
1. 先上 IOVDD；
2. 再上模拟电源 AVDD 和 DRVDD（t1：IOVDD → AVDD/DRVDD，最小 0）；
3. 最后上数字内核 DVDD（t2：AVDD → DVDD，0–5 ms；t3：IOVDD → DVDD，最小 0）；
4. RESET 保持低，直到所有电源稳定；
5. **模拟电源任何时候都不得低于 DVDD**。

**对本板的含义 [估]**：1.8 V LDO 的 EN 接 3.3 V 模拟轨（或其 PG），这样 DVDD 总晚于 AVDD；LDO 软启动要在 5 ms 内完成。3.3 V 数字轨（IOVDD）要先于模拟轨，对应前面"模拟 LDO 的 EN 接数字 3.3 V 轨"，一条使能链即可同时满足 STM32 和 AIC3104：5 V → 3.3 V 数字轨 → 3.3 V 模拟 LDO（EN）→ 1.8 V LDO（EN）。

### 4.3 LCD 上电顺序（Innolux V.7，p.7）

[读] 规格书有 T1–T6 的上下电时序图，数值：T1 0–10 ms，T2 0–100 ms，T3 ≤ 200 ms，T4 ≥ 160 ms，T5 ≥ 160 ms，T6 ≥ 1 ms。图本身我没解读，各 T 对应哪个事件没核对。可以确认的是：背光应由 MCU 在 LCD 信号稳定后再开，背光升压的使能不要跟 5 V 一起自动上电。RK043FN48H 规格书（镜像）没有时序要求。

---

## 5. 整板上电顺序建议汇总 [估]

由 3.3 V 数字轨为根，一条使能链：
1. 12 V → 5 V（LMR51420）→ 5 V 轨。
2. 5 V → 3.3 V 数字（TPS62A02）。
3. 3.3 V 数字轨（或其 PG）→ EN → 3.3 V 模拟 LDO（TPS7A2033）。满足 STM32 的 "VDD < 1 V 时 VDDA < VDD + 0.3 V"，AIC3104 的 "IOVDD 先于 AVDD"。
4. 3.3 V 模拟轨 → EN → 1.8 V LDO（TPS7A2018，输入来自 3.3 V 数字轨）。满足 "DVDD 最后、模拟电源 ≥ DVDD"。
5. LAN8742A 的 nRST 由 MCU GPIO 或复位延时电路控制，至少等所有电源到位后 25 ms 释放。
6. 背光升压的 CTRL 由 MCU PWM 控制，LCD 信号稳定后再开。

---

## 6. 未核对项

1. **实际芯片版本**：STM32H743IIK6 是 rev Y 还是 rev V，我没法确认；两套数值都列了。
2. **DS12110 Table 20 的 "Typ" 对应结温**：表头没写，我按 25 °C 理解。
3. **STM32 的 rev Y ADC 电流行**：只在 rev V（Table 174）读到 ADC 消耗 VDDA；rev Y 的 ADC 电流行没找到，VDDA 预算按 rev V 数字估。
4. **IS42S32800J**：ISSI 官网返回 Incapsula 拦截页，用的是 cdn.components.ru 的 ISSI Rev B1（2021-12）转载，最大值可信，**没有典型值**，典型是我估的。
5. **LAN8742A**：用的是 DESY 转载的 SMSC Rev 1.1（2013-05-21）；Microchip 现行版本（DS00002400）里的电流值、去耦建议可能不同；只有典型值，没有最大值；CBYPASS 数值没读到；Microchip 官网 403，没试其他镜像交叉验证。
6. **Würth 7499010211A**：we-online.com 返回 403，Arrow 转载的 PDF 拉取超时，**没读到该器件规格书**。中心抽头电压、LED 的 VF/IF、引脚定义都没核对。搜索结果里同系列别的料号给出 LED 正向电压 1.8–2.4 V @20 mA，不能直接套用。
7. **Rocktech RK043FN48H**：只读到 wiki.kewl.org 的 V1.0（2015）转载；面板逻辑电流为 T.B.D；触摸 IC 电流没有；你拿到的模块版本可能不同。
8. **Innolux AT043TN24**：读的是 V.7 Rev 02（2018-04-12，NXP 社区转载）；搜索结果里 V.1 的背光是 19.8 V / 40 mA，说明不同版本差很大，要按你实际买的版本确认。上电时序图 T1–T6 没解读。
9. **SD 卡**：用的是 v3.01（2010）简化规范，utexas.edu 转载。更新版本（UHS-II、SD Express）在 3.3 V 下的电流上限可能更高，但板上只做 3.3 V 四线，我没查。
10. **TVS 钳位电压、P-MOSFET 型号**：没读规格书，SMBJ24A 的 38.9 V / 15.4 A 凭记忆，需要核对。
11. **TPS563201 的 UVLO 数值**、TLV755P 的 PSRR 和压差：没读。LMR51420 的变体后缀（X/Y 对应 500 kHz 还是 1.1 MHz）是按表顺序推断的，订货前要对照订货表确认。
12. **在产状态**：TI 器件用 ti.com 产品页（2026-11-16）确认为 Active；LM74700-Q1 只看了数据手册订货表（Active，没看产品页）；TCAN1042H、TLV320AIC3104 没查状态（用户已选定）；ADI LT3465 页面显示 PRODUCTION，没写是否推荐新设计；LAN8742A、W25Q128JV、IS42S32800J 没查状态。
13. **布局图**：我只确认了各规格书里有 "Layout Example" 一节，没审查内容。
14. **没有仿真**：各 DC-DC 的纹波、EMC、效率、热都没算，只是比较规格。
15. **估算项汇总**：FMC 翻转电流、SDRAM 典型值、PHY 最大值、LCD 逻辑电流、LED 电流、AIC3104 静态最大值与耳机动态电流、MCU VDDA 电流、5 V 轨折算电流、12 V 输入电流、保险丝取值，均为 [估]。
16. **AN4938 与 DS12110 的 tRSTTEMPO 不一致**（2.6 ms 对 377 µs），没有进一步查。
17. **KiCad 自带库**：符号和封装文件存在性已用脚本核对，没有逐个打开检查引脚电气类型和封装焊盘尺寸是否匹配 TI 封装图。

---

## 7. 主要来源

- ST DS12110 Rev 11（2026-01）：`https://www.st.com/resource/en/datasheet/stm32h743ii.pdf`（WebFetch 下载；本地 `ds\ds12110.pdf`）
- ST AN4938 Rev 7：`https://www.st.com/resource/en/application_note/an4938-getting-started-with-stm32h74xig-and-stm32h75xig-mcus-hardware-development-stmicroelectronics.pdf`
- ST 社区 FAQ（VDD33USB/VDD50USB 不用时的接法）：`https://community.st.com/t5/stm32-mcus/faq-configuring-the-vdd50usb-and-vdd33usb-pins-on-stm32h7-when/ta-p/727887`
- TI 数据手册（`https://www.ti.com/lit/ds/symlink/<料号>.pdf`，curl 可直接下载）：tlv320aic3104（SLAS510G）、tcan1042h（SLLSES7D）、tps61169、tps61165、tps54202、lmr51420、lmr33620、tps62933、tps563201、tps62a02、tps62130a、tps62160、lp5907、tps7a20、tlv755p、tps7a05、lm74700-q1、tps2663、tps25947
- TI 产品页（WebFetch，状态）：`https://www.ti.com/product/<料号>`
- Winbond W25Q128JV Rev F：`https://www.winbond.com/resource-files/w25q128jv%20revf%2003272018%20plus.pdf`
- ISSI IS42S32800J Rev B1 转载：`https://cdn.components.ru/media/PDF/205047.pdf`
- SMSC LAN8742A Rev 1.1 转载：`https://www.zeuthen.desy.de/~sulanke/Projects/ICECUBE/mDOM/mainboard/datasheets/eth_phy_LAN8742a.pdf`
- Rocktech RK043FN48H-CT672B V1.0 转载：`https://wiki.kewl.org/_media/boards:rk043fn48h-ct672b-v1.0.pdf`
- Innolux AT043TN24 V.7 Rev 02 转载：`https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/imx-processors/163096/1/AT043TN24%20V.7_V02_20180423.pdf`
- SD Physical Layer Simplified Spec v3.01 转载：`https://www.cs.utexas.edu/~simon/378/resources/Part_1_Physical_Layer_Simplified_Specification_Ver_3.01_Final_100518.pdf`
- ADI LT3465 产品页：`https://www.analog.com/en/products/lt3465.html`
