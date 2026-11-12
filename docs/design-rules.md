# 设计规则（common 模板）

来源：Altium 规则集 `E:\AD25workspace\pcb_rules\common.RUL`（54 条，2026-11-12 迁移）。
模板文件：`templates/common/`（`common.kicad_pro` / `common.kicad_pcb` / `common.kicad_dru`）。

## 新工程怎么用

1. 把 `templates/common/` 下三个 `common.*` 文件复制到新工程目录，改成同一个工程名（如 `myboard.kicad_pro` / `.kicad_pcb` / `.kicad_dru`）。
   也可以在 KiCad 里把 `templates/` 加为用户模板目录，用"从模板新建工程"。
2. **布局前**：确定板厂和板材，用板厂提供的叠层数据算差分阻抗，再为每种接口（USB2、USB3……）建网络类并填线宽/间距。模板里故意没填。
3. 改了 `.kicad_dru` 之后，必须跑一次 DRC 并确认至少有一条 `corner_angle` 能触发（见下面"已知陷阱"）。

## 规则对照（1 mil = 0.0254 mm）

| AD 规则 | AD 值 | KiCad 值 | 存放位置 |
|---|---|---|---|
| Clearance | 5 mil | 0.127 mm | 板设置 min_clearance + 各网络类 |
| Width SIGNAL（min/pref/max） | 4/8/32 mil | 0.1016/0.2032/0.8128 | Default 网络类 + `signal_width` |
| Width PWR | 6/12/100 mil | 0.1524/0.3048/2.54 | PWR 网络类 + `pwr_width` |
| Width Crystal Oscillator Line | 10 mil 固定 | 0.254 | XTAL 网络类 + `xtal_width` |
| RoutingVias（孔/外径，min–max） | 12/20；孔 12–30，径 16–50 mil | 0.3048/0.508；孔 0.3048–0.762，径 0.4064–1.27 | 网络类 + `via_size` |
| HoleSize | 10–120 mil | 0.254–3.048 | 板设置 + `hole_range` |
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
| 丝印间距（AD 为 0） | 丝印间距 0.1 mm，文字高 ≥0.8 mm、线宽 ≥0.15 mm；丝印压铜/重叠/压板边报 warning | AD 里靠手动调整；自动布局需要检查兜底 |
| 网络类自动归类 | 按网络名匹配，完整清单见 `common.kicad_pro` 的 `netclass_patterns`。PWR：地（`GND*` `AGND*` `PGND*`）、`+`/`-` 开头、`VCC*` `VDD*` `AVDD*` `VBUS*` `VBAT*` `VIN*` `VSYS*` `VMOT*` `VM`、裸电压名（`3V3*` `5V*` `1V8*` `12V*` `24V*` 等）及其层次路径形式（`*/3V3*`）。XTAL：`*XTAL*` `*OSC_IN*` `*OSC32_IN` `*X32K*`，以及整名或带分隔符的 `XI` `XO` `XIN` `XOUT`（`*/XI` `*_XIN` `*-XIN`） | AD 里手动分配。XI/XO 类故意不用 `*XI` 这种宽匹配：实测 `MAXI`、`AUXIN` 会被误归入晶振类 |

## 未迁移（AD 默认/占位，或 KiCad 无对应）

Fanout、RoutingTopology、RoutingPriority、RoutingLayers、LayerPairs、Testpoint 系列、BackDrilling、Height、ComponentOrientations、ParallelSegment、Length（100000 mil）、StubLength、MaximumViaCount（1000）、NetAntennae、SupplyNets、UnpouredPolygon。
ReturnPath 由 kicad-happy 的回流路径分析覆盖。

## 已知陷阱

- **`.kicad_dru` 任何语法错误都会让整个文件静默失效**，kicad-cli 不报错，DRC 照常输出，只是自定义规则全部不生效。
  - 角度不带单位：`(min 135)`，写 `135deg` 会失效。
  - `min_resolved_spokes` 直接写数字：`(constraint min_resolved_spokes 2)`，写 `(min 2)` 会失效。
- `corner_angle` 也会报 90° 的 T 型分叉，需要逐条判断。
- 每处角度违规会报两次（两段走线各一次）。

## 验证记录（2026-11-12，KiCad 10.0.8）

在测试板上放置故意违规的走线/过孔，确认触发：90° 拐角、PWR 线 0.13 mm 过细、信号线 1.0 mm 过粗、过孔孔径 0.2 mm 过小；45° 拐弯和 0.13 mm 信号线不误报；`+3V3` 自动归入 PWR。
铺铜后在焊盘外 0.15 mm 处 8 方向取样：插件焊盘为辐条（花焊盘），贴片焊盘四周全铜；去掉规则文件后贴片焊盘变回 KiCad 默认的花焊盘。

## 工程级覆盖：嘉立创双层板

模板保留 AD 原值；用嘉立创双层板的工程在自己的三个文件里覆盖下面几项（首个例子：`stm32f411_minsys/`，2026-11-12）。

| 项目 | 模板值 | 覆盖值 | 原因 | 改哪里 |
|---|---|---|---|---|
| 阻焊扩展 | 0.1016 mm | 0.05 mm | 0.5 mm 间距的 QFN / USB-C 引脚之间留不下阻焊桥（该板 DRC 报 111 条 `solder_mask_bridge`，改后为 0） | `.kicad_pcb` 的 `pad_to_mask_clearance` |
| 最小线宽 | 0.1016 mm | 0.127 mm | 嘉立创 1–2 层板线宽/线距下限 5 mil | `.kicad_pro` 的 `min_track_width` + `.kicad_dru` 的 `signal_width` |
| 过孔 | 0.3048 / 0.508 mm | 0.3 / 0.6 mm | 模板焊环只有 0.1 mm；嘉立创各页面给的焊环下限不一致（0.13–0.25 mm），下单前再核对 | `.kicad_pro` 各网络类 + `.kicad_dru` 的 `via_size` |
