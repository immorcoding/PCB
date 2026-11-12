# steval_fcu001v2

四层板 layout 测试用的原理图：ST 官方评估板 STEVAL-FCU001V2（小四轴飞控）的重新录入。

- 来源：`ref/steval-fcu001v2-schematic.pdf`（ST schematic pack Rev 2，2024-06），同目录有 BOM、data brief、UM2958。
- 生成：`sh scripts/sch_build.sh steval_fcu001v2 <输出目录>`。位号沿用 ST 的（CN1、P1–P8、LD1–LD3、S1、BT1），方便对照。
- 画法：每个引脚一段短线加网络标号或电源符号，没有长连线。连接关系以导出的网表为准。
- 板子：嘉立创四层 JLC04161H-3313，1.6 mm，44 × 40 mm，器件在顶层，只有第二组电机焊盘在底层。规则覆盖写在 `steval_fcu001v2.kicad_dru` 开头。
- 布局：`place.py`（坐标表），示意图 `placement.png`。还没有走线。
- 各层用途（2026-11-12 和用户定）：L1 信号和器件，L2 整层地，L3 电源层（`+BATT` 和 `VDD` 分割），L4 信号加铺地。

## 和 ST 图纸不一样的地方

| ST 图纸 | 这里 | 原因 |
|---|---|---|
| `V_USB`、`VBAT+` | `VBUS`、`+BATT` | 用 KiCad 自带电源符号 |
| `USB_DP` / `USB_DM`（MCU 侧） | `USB_D+` / `USB_D-` | KiCad 靠 `+`/`-` 后缀识别差分对 |
| `DP` / `DM`（连接器侧） | `USB_CONN_D+` / `USB_CONN_D-` | 同上 |
| `MOTORn-` | `MOTORn_N` | 避免被当成差分对的负端 |
| R25（0R，接在两种地符号之间） | 去掉，只有一个 `GND` | 原板把 USB 侧的地和系统地分开画、用 0R 单点连接；要保留单点接地的话布局前说 |
| 电机排针 P1 / P4 / P2 / P5（2 针） | 裸焊盘 MP1–MP16（每个电机 `+BATT` 和 `Mn_OUT` 各一个，1.5 × 3 mm；MP1–8 在顶层，MP9–16 在底层同一位置） | 用户要求：飞控板的电机输出一般是焊盘，过流大 |
| CN1 Molex 47590-0001（micro-AB，沉板，板边要开槽） | Molex 47346-0001（micro-B，贴片，直板边） | 不开槽；引脚顺序相反，USB 差分对从 MCU 到座子不用交叉 |
| 没有安装孔 | H1–H4，M3 | 原型板固定用 |
| 栅极、LED 阳极等没有名字的节点 | `Mn_GATE`、`LDn_A`、`Mn_OUT`、`CHG_PROG`、`CHG_STAT`、`USB_SHIELD`、`USBLC_VBUS` | 标号画法需要名字 |

## 符号和封装的替代

官方库里没有的器件，用引脚号相同的符号顶替，Value 写的是 ST 的型号。

| 位号 | ST 型号 | 用的符号 | 用的封装 |
|---|---|---|---|
| U3 | USBULC6-2M6（µQFN 1.45×1.0） | `USBLC6-2P6` | `Texas_USON-6_1x1.45mm_P0.5mm_SMD` |
| U4 | STC4054GR（TSOT23-5） | `MCP73831-2-OT` | `TSOT-23-5` |
| U8 | LSM6DSR（LGA-14） | `LSM6DSL` | `LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y` |
| U1 | BLUENRG-M0A | `SPBTLE-RF` | `ST_SPBTLE` |
| Q1–Q4 | STL10N3LLH5（图纸）/ STL6N3LLH6（BOM） | `Q_NMOS_SSSGD` | `VSON-8_3.3x3.3mm_P0.65mm_NexFET` |
| D5 | ESDA7P60-1U1M | `D_Zener` | `ST_QFN-2L_1.6x1.0mm` |

## 未核对项

没有对着规格书核对过的引脚、封装和参数，带到交付。

1. **Q1–Q4 型号和封装**：ST 图纸写 STL10N3LLH5（8 脚，1–3 源极、4 栅极、5–8 漏极），BOM 写 STL6N3LLH6（PowerFLAT 2×2）。这里按图纸的引脚功能，封装用了 3.3×3.3 的通用 VSON-8，没核对过 ST 的推荐焊盘。
2. **U3 封装**：用了尺寸相同的 TI USON-6 顶替，焊盘编号顺序和尺寸没对过 USBULC6-2M6 规格书。
3. **U1 封装**：假定 BLUENRG-M0A 和 SPBTLE-RF 焊盘相同，没对过规格书；模块天线下方的禁布区要求也没查。
4. **U4 引脚**：按图纸上的引脚号（1 CHRG、2 GND、3 BAT、4 VCC、5 PROG）录入，没对过 STC4054 规格书。
5. **U8 引脚**：LSM6DSR 借用 LSM6DSL 符号，图纸上的引脚号和符号一致，没对过规格书。
6. **S1**：KMR231GLFS 用了带接地脚的 `KMR2xxG` 封装，接地脚接 GND；型号是否带接地脚没查。
7. **D5 极性**：按图纸 1 脚接 VBUS；封装的 1 号焊盘是否是阴极没查。
8. **Y1**：BOM 里晶振的型号没读出来（PDF 表格文字错位），封装暂用 3225 四脚，负载电容 15 pF 沿用图纸。
9. **排针**：BT1 用 2.54 mm 弯针，P3、P7、P6 用直针，P8 用 1.27 mm 2×5 贴片针；BOM 的具体料号（Adam Tech、Samtec FTSH）没逐个对封装。
10. **阻容封装**：统一 0402（图纸上 R1 标 0805、R26 标 0201，BOM 都是 0402）；R12、R13、R16、R17 按 BOM 用 0603，图纸注明要过 3 A 峰值电流。
11. **原板尺寸和外形**：没查。V1 的 Gerber 是双层板，没有官方四层 layout 可对照。
12. **叠层数据**：3313 半固化片 0.0994 mm / Er 4.1、芯板 1.265 mm 是凭记忆写的，没在嘉立创阻抗计算器上核对。USB 线宽 0.15 / 间距 0.15 mm 是按 IPC-2141 公式估的（约 88 Ω）；这块板的 USB 只有全速。
13. **CN1 板边位置**：板边放在封装原点下方 2.7 mm（外壳焊盘外 0.55 mm），没对过 Molex 47346-0001 图纸上的板边尺寸。
14. **U1 天线净空**：模块天线端贴着上板边放。`ST_SPBTLE` 封装自带 12 × 12 mm 的四层禁布区，布局已避开；这个尺寸是 SPBTLE-RF 的，没对过 BLUENRG-M0A 规格书。
15. **U7 / U8 阻焊桥**：0.5 mm 间距 LGA 焊盘之间 DRC 报 24 条 `solder_mask_bridge`（阻焊扩展 0.05 mm 时桥宽不足 0.08 mm），收尾阶段决定是改阻焊参数还是接受焊盘间不留阻焊。

## ERC

0 错误，1 条警告：U8 的 SDx（双向）接在 VDD 上，和 LDO 输出（电源输出）同网。ST 图纸就是把 SDx/SCx 接 VDD 的，保留。
