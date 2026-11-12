# steval_fcu001v2

四层板 layout 测试用的原理图：ST 官方评估板 STEVAL-FCU001V2（小四轴飞控）的重新录入。

- 来源：`ref/steval-fcu001v2-schematic.pdf`（ST schematic pack Rev 2，2024-06），同目录有 BOM、data brief、UM2958。
- 生成：`sh scripts/sch_build.sh steval_fcu001v2 <输出目录>`。位号沿用 ST 的（CN1、P1–P8、LD1–LD3、S1、BT1），方便对照。
- 画法：每个引脚一段短线加网络标号或电源符号，没有长连线。连接关系以导出的网表为准。
- 还没有 `.kicad_pro` / `.kicad_pcb` / `.kicad_dru`：等叠层和板厂定了，在规则阶段从 `templates/common/` 一起建。

## 和 ST 图纸不一样的地方

| ST 图纸 | 这里 | 原因 |
|---|---|---|
| `V_USB`、`VBAT+` | `VBUS`、`+BATT` | 用 KiCad 自带电源符号 |
| `USB_DP` / `USB_DM`（MCU 侧） | `USB_D+` / `USB_D-` | KiCad 靠 `+`/`-` 后缀识别差分对 |
| `DP` / `DM`（连接器侧） | `USB_CONN_D+` / `USB_CONN_D-` | 同上 |
| `MOTORn-` | `MOTORn_N` | 避免被当成差分对的负端 |
| R25（0R，接在两种地符号之间） | 去掉，只有一个 `GND` | 原板把 USB 侧的地和系统地分开画、用 0R 单点连接；要保留单点接地的话布局前说 |
| 栅极、LED 阳极等没有名字的节点 | `Mn_GATE`、`LDn_A`、`Pn_2`、`CHG_PROG`、`CHG_STAT`、`USB_SHIELD`、`USBLC_VBUS` | 标号画法需要名字 |

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
9. **排针**：BT1、P1、P2、P4、P5 用 2.54 mm 弯针，P3、P7、P6 用直针，P8 用 1.27 mm 2×5 贴片针；BOM 的具体料号（Adam Tech、Samtec FTSH）没逐个对封装。
10. **阻容封装**：统一 0402（图纸上 R1 标 0805、R26 标 0201，BOM 都是 0402）；R12、R13、R16、R17 按 BOM 用 0603，图纸注明要过 3 A 峰值电流。
11. **原板尺寸和外形**：没查。V1 的 Gerber 是双层板，没有官方四层 layout 可对照。

## ERC

0 错误，1 条警告：U8 的 SDx（双向）接在 VDD 上，和 LDO 输出（电源输出）同网。ST 图纸就是把 SDx/SCx 接 VDD 的，保留。
