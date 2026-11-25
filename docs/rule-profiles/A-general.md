# 规格档 A：通用（无 BGA）

适用：没有 BGA、引脚间距 0.5 mm 及以上（QFN、LQFP、0.5 mm LGA）的板子，双层或四层。带 0.8 mm 球距 BGA 用 [B](B-bga-080.md)，0.65 mm 及以下用 [C](C-bga-065.md)。

状态：在两块做完的板子上用过。模板是 `templates/common/`（保留 AD 原值），板厂覆盖值写在工程自己的三个文件里。

## 嘉立创双层板

模板保留 AD 原值；用嘉立创双层板的工程在自己的三个文件里覆盖下面几项（首个例子：`stm32f411_minsys/`，2026-11-12）。

| 项目 | 模板值 | 覆盖值 | 原因 | 改哪里 |
|---|---|---|---|---|
| 阻焊扩展 | 0.1016 mm | 0.05 mm | 0.5 mm 间距的 QFN / USB-C 引脚之间留不下阻焊桥（该板 DRC 报 111 条 `solder_mask_bridge`，改后为 0） | `.kicad_pcb` 的 `pad_to_mask_clearance` |
| 最小线宽 | 0.1016 mm | 0.127 mm | 嘉立创 1–2 层板线宽/线距下限 5 mil | `.kicad_pro` 的 `min_track_width` + `.kicad_dru` 的 `signal_width` |
| 过孔 | 0.3048 / 0.508 mm | 0.3 / 0.6 mm | 模板焊环只有 0.1 mm；嘉立创各页面给的焊环下限不一致（0.13–0.25 mm），下单前再核对 | `.kicad_pro` 各网络类 + `.kicad_dru` 的 `via_size` |

## 嘉立创四层板

首个例子：`steval_fcu001v2/`（JLC04161H-3313，1.6 mm，2026-11-12）。在双层板的覆盖值上再改下面几项。

| 项目 | 双层板的值 | 四层板的值 | 原因 | 改哪里 |
|---|---|---|---|---|
| 过孔下限 | 0.3 / 0.6 mm | 0.2 / 0.45 mm（默认仍用 0.3 / 0.6） | 0.5 mm 间距 QFN 的引脚要换层时，相邻两根 0.15 mm 走线之间放不下 0.6 mm 过孔（需要中心距 0.502 mm，只有 0.5 mm）；0.45 mm 的可以排成交错的两三排 | `.kicad_pro` 的 `min_via_diameter` / `min_through_hole_diameter` / `min_via_annular_width` + `.kicad_dru` 的 `via_size`、`hole_range` |
| 孔径上限 | 3.048 mm | 3.3 mm | M3 安装孔是 3.2 mm | `.kicad_dru` 的 `hole_range` |
| USB2 线宽/间距 | 0.2 / 0.15 mm，不控阻抗 | 0.15 / 0.15 mm | 按 IPC-2141 公式，L1 对 L2（0.0994 mm 半固化片，Er 4.1）约 88 Ω。叠层数据没在嘉立创计算器上核对 | `.kicad_pro` 的 USB2 网络类 + `usb2_width` |
| USB2 对内等长 | `(constraint skew (max 0.5mm))` | 加 `(within_diff_pairs)` | 不加的话，同一网络类里的两对差分线（保护器件两侧各一对）会互相比较长度 | `.kicad_dru` 的 `usb2_skew` |
| USB2 对内间距上限 | 0.7 mm | 0.8 mm | 差分对在 U3 处绕开中间的地焊盘，分开 0.77 mm、长约 1.4 mm | `.kicad_dru` 的 `usb2_gap` |

已知陷阱（四层板上新踩的）：

- **网络类通配符只认 `*`**：`*MOTOR?_N`、`*USB_D[+-]` 这类写法不报错也不匹配，网络留在 Default 类。表现是 1 mm 的电机线被 `signal_width` 报过宽、USB 的等长规则不触发。逐个网络名写。
- **`VBAT*` 会把 `VBAT_SENSE` 归进 PWR**：采样线也按 PWR 的 0.1524 mm 下限检查。
- **0.5 mm 间距 LGA 的阻焊桥**：阻焊扩展 0.05 mm 时焊盘间只剩 0.05 mm，低于 0.08 mm 下限，每个焊盘对报一条 `solder_mask_bridge`。给这些封装打开"允许阻焊桥"（`fp.SetAllowSolderMaskBridges(True)`），代价是每个封装多一条 `lib_footprint_mismatch`。
- **封装自带的禁布区**：`RF_Module:ST_SPBTLE` 带一个 12 × 12 mm 的四层禁布区，比外框大，布局时外框不重叠也会报 `items_not_allowed`。`placement.via_spots`（`Tools/KiCadDesignTools/placement/via_spots.py`）不看封装里的禁布区。
