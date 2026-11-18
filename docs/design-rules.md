# 设计规则：数值和事实

规则的数值、和 Altium 的对照、板厂覆盖值、规则文件的坑。"该怎么做"在 [shape/](shape/)（起工程和确认规则生效见 [shape/rules-and-schematic.md](shape/rules-and-schematic.md)），工具命令在 [tools.md](tools.md)。

来源：Altium 规则集 `E:\AD25workspace\pcb_rules\common.RUL`（54 条，2026-11-12 迁移）。模板文件：`templates/common/`（`common.kicad_pro` / `.kicad_pcb` / `.kicad_dru`），新工程把三个文件复制过去并改成同一个工程名。差分对的线宽和间距模板里故意没填。

## 规则对照（1 mil = 0.0254 mm）

| AD 规则 | AD 值 | KiCad 值 | 存放位置 |
|---|---|---|---|
| Clearance | 5 mil | 0.127 mm | 板设置 min_clearance + 各网络类 |
| Width SIGNAL（min/pref/max） | 4/8/32 mil | 0.1016/0.2032/0.8128 | Default 网络类 + `signal_width` |
| Width PWR | 6/12/100 mil | 0.1524/0.3048/2.54 | PWR 网络类 + `pwr_width` |
| Width Crystal Oscillator Line | 10 mil 固定 | 0.254 | XTAL 网络类 + `xtal_width` |
| RoutingVias（孔/外径，min–max） | 12/20；孔 12–30，径 16–50 mil | 0.3048/0.508；孔 0.3048–0.762，径 0.4064–1.27 | 网络类 + `via_size` |
| HoleSize | 10–120 mil | 0.254–3.048 | 板设置 + `hole_range` |
| （AD 里没有）最短线段 | — | ≥ 0.1 mm | `min_segment`（`track_segment_length`），2026-11-13 加 |
| MinimumAnnularRing | 2 mil | 0.0508 | 板设置 |
| HoleToHoleClearance | 10 mil | 0.254 | 板设置 |
| BoardOutlineClearance | 10 mil | 0.254 | 板设置 min_copper_edge_clearance |
| SolderMaskExpansion（焊盘） | 4 mil | 0.1016 | `.kicad_pcb` pad_to_mask_clearance |
| SolderMaskExpansion "oil"（过孔盖油） | tenting | 正反面 tenting | `.kicad_pcb` tenting |
| MinimumSolderMaskSliver | 3.2 mil | 0.0813 | `.kicad_pcb` solder_mask_min_width |
| PasteMaskExpansion | 0 | 0 | `.kicad_pcb` |
| MatchedLengths USB3.0 | 5 mil | skew ≤ 0.127 | `usb3_skew`（网络类名 `USB3`） |
| AcuteAngle ≥45° + RoutingCorners 45° | — | 内角 ≥135°（禁止 90° 和锐角） | `corner_angle`，严重级别 error |
| ComponentClearance | 10 mil | courtyard 重叠检查 | 严重级别 error |

## 和 AD 不同的决定

| 项目 | 决定 | 原因 |
|---|---|---|
| Via in Pad（孔 6 mil） | **不迁移** | AD 里它的作用范围是 All 且优先级最高，实际覆盖了普通过孔规则。盘中孔只在 BGA/LGA 等高速板时单独制定 |
| 差分对 USB2.0/USB3.0 线宽 5.1/间距 5 mil | **不迁移** | 只是占位值；阻抗取决于板厂叠层，布局前按板厂数据计算 |
| PolygonConnect Direct（全连接） | 插件焊盘用**花焊盘**（辐条 0.254、间隙 0.254、至少 2 根辐条连通），贴片焊盘**全连接** | 插件焊盘全连接到大铜面时，手工焊接很难上锡；贴片走回流焊，全连接导热导电更好 |
| 丝印间距（AD 为 0） | 丝印间距 0.1 mm，文字高 ≥1.0 mm、线宽 ≥0.15 mm；丝印压铜/重叠/压板边报 warning | AD 里靠手动调整；自动布局需要检查兜底 |
| 网络类自动归类 | 按网络名匹配，完整清单见 `common.kicad_pro` 的 `netclass_patterns`。PWR：地（`GND*` `AGND*` `PGND*`）、`+`/`-` 开头、`VCC*` `VDD*` `AVDD*` `VBUS*` `VBAT*` `VIN*` `VSYS*` `VMOT*` `VM`、裸电压名（`3V3*` `5V*` `1V8*` `12V*` `24V*` 等）及其层次路径形式（`*/3V3*`）。XTAL：`*XTAL*` `*OSC_IN*` `*OSC32_IN` `*X32K*`，以及整名或带分隔符的 `XI` `XO` `XIN` `XOUT`（`*/XI` `*_XIN` `*-XIN`） | AD 里手动分配。XI/XO 类故意不用 `*XI` 这种宽匹配：实测 `MAXI`、`AUXIN` 会被误归入晶振类 |

## 未迁移（AD 默认/占位，或 KiCad 无对应）

Fanout、RoutingTopology、RoutingPriority、RoutingLayers、LayerPairs、Testpoint 系列、BackDrilling、Height、ComponentOrientations、ParallelSegment、Length（100000 mil）、StubLength、MaximumViaCount（1000）、NetAntennae、SupplyNets、UnpouredPolygon。
ReturnPath 由 kicad-happy 的回流路径分析覆盖。

## 已知陷阱

- **`.kicad_dru` 任何语法错误都会让整个文件静默失效**，kicad-cli 不报错，DRC 照常输出，只是自定义规则全部不生效。
  - 角度不带单位：`(min 135)`，写 `135deg` 会失效。
  - `min_resolved_spokes` 直接写数字：`(constraint min_resolved_spokes 2)`，写 `(min 2)` 会失效。
  - 数值必须带单位：`(min 0.09mm)`，写 `(min 0.09)` 会失效（角度和 `min_resolved_spokes` 除外，见上）。
  - 条件里的相等写 `==`，单个 `=` 会失效。
  - 约束名拼错（如 `clearence`）会失效。
  - 规则行尾不能跟 `#` 注释：`(constraint ... ))   # 说明` 会让整个文件失效（2026-11-12 踩过，金丝雀抓到）。注释单独占一行。
- **名字拼错不会让文件失效，只会让那条规则匹配不到任何东西**：网络类名、网络名、规则区名、函数名拼错时文件照常加载，金丝雀抓不到；要另外检查每条规则至少匹配一个对象（RUL-2）。
- `track_angle` 的阈值按整数度比较：写 `(min 134.9)` 等同于 135。KiCad 把部分精确的 45° 拐弯量成 134.9999° 并报错（常见于起点在旋转 45° 的焊盘上的走线），所以带 45° 旋转器件的工程把 `corner_angle` 写成 `(min 134)`。
- **`intersectsArea()` 对铺铜区是按整块判断的**：规则区的间距规则只写 `A.intersectsArea('BGA_…')` 时，一块铺铜只要盖到规则区，全板都按区内的间距填充（H7 的铜皮原型上实测 0.092 mm，铺铜区设的是 0.20；废弃的 RK3568 板也是这样）。条件前面加 `A.Type != 'Zone' && B.Type != 'Zone'`，写法见 [规格档 C](rule-profiles/C-bga-065.md)。金丝雀查不出这种作用范围的错，要量一处铺铜到别的铜的实际距离。
- `corner_angle` 也会报 90° 的 T 型分叉，需要逐条判断。
- 每处角度违规会报两次（两段走线各一次）。
- **`corner_angle` 只比较相邻两段**：两个 45° 拐点之间夹一段极短的线（四层板 `MOTOR3`：0.05 mm），每个拐点都是 135°，不报，看上去却是直角。`min_segment` 把 0.1 mm 以下的挡掉；0.1–0.35 mm 的小倒角由 `track_shape.py` 的 `sharp` 项查。下限不能在 DRC 里直接提高：0.2 mm 时四层板多报 5 条正常的焊盘出线，0.3 mm 时多报 20 条。

## 走线形状（DRC 不查，用 `scripts/track_shape.py` 查）

下面的数字是四层板上用户认可的那一版的水平（2026-11-12），不是用户逐条定的指标。怎么用见 [shape/routing.md](shape/routing.md) 的 RTE-8 到 RTE-10。

| 项目 | 标准 | 说明 |
|---|---|---|
| 不在 0°/45°/90° 上的线段 | 0 | |
| 阶梯线 | 0 | 一串微小线段拼成的非 45° 斜线。布线器会这么走（四层板 `MOTOR1`：22 级、2.6 mm、整体 78.5°），每段单独量都合规，要按连续短线段的整体走向查 |
| 2 mm 内 3 个以上折弯 | 手工走线 0；自动走线逐处看过再列出原因 | 四层板认可的那一版剩 13 处，都在自动走线上 |
| 短于 0.1 mm 的线段 | 0 | DRC 规则 `min_segment` 也查 |
| 小倒角直角（`sharp`） | 0 | 短于 0.35 mm 的线段两侧走向合计转 90° 以上。0.35 mm 是我定的：四层板上手工走线的常规倒角是 0.42 mm（含 USB 差分对的拐角），再高就把它们也报出来 |
| 等长补偿 | 圆弧蛇形 | 四层板 USB：半径 0.25 mm、摆幅 0.5 mm |

## 丝印

文字下限是字高 1.0 mm、线宽 0.15 mm（嘉立创两个站点写的最小字高，2026-11-18 起）；四层板实际用的 0.8 × 0.6 mm 低于它，那块板不改。印什么、位号留不留见 [shape/finishing.md](shape/finishing.md)。

## 验证记录（2026-11-12，KiCad 10.0.8）

在测试板上放置故意违规的走线/过孔，确认触发：90° 拐角、PWR 线 0.13 mm 过细、信号线 1.0 mm 过粗、过孔孔径 0.2 mm 过小；45° 拐弯和 0.13 mm 信号线不误报；`+3V3` 自动归入 PWR。
铺铜后在焊盘外 0.15 mm 处 8 方向取样：插件焊盘为辐条（花焊盘），贴片焊盘四周全铜；去掉规则文件后贴片焊盘变回 KiCad 默认的花焊盘。

## 规格档

一块板子开工时选一档，每一档是一套自洽的数值；不从低一档改起（见 [shape/rules-and-schematic.md](shape/rules-and-schematic.md) 的 RUL-11、RUL-12）。本文件上面的对照表、陷阱和线形标准对三档都适用。

| 档 | 适用 | 状态 |
|---|---|---|
| [A 通用](rule-profiles/A-general.md) | 无 BGA，双层或四层 | 两块板用过 |
| [B 0.8 mm BGA](rule-profiles/B-bga-080.md) | TFBGA，四层起 | 草稿 |
| [C 0.65 mm 及以下 BGA](rule-profiles/C-bga-065.md) | UFBGA、应用处理器，六层起 | 规则验证过，板子没做完 |
