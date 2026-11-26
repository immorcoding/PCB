# 调研：差分对布线和等长的现成做法（KiCad 10 和开源工具）

票：[#31](https://github.com/immorcoding/PCB/issues/31)（地图 [#26](https://github.com/immorcoding/PCB/issues/26)，约定来源 PROC-5）。
日期 2026-11-26。KiCad 10.0.8（`D:\KiCad\bin\`），Windows 11。分支 `research/diff-pair-tooling`，只存档不合并。
前作：分支 `research/kicad-length-rules` 的 `docs/research/kicad-length-rules.md`（长度规则的命令行实验，下称“前作”）。本篇不重复它的实验，只引用结论。

证据标记（全篇统一）：

- **【源码】** 读了 KiCad 10.0.8 标签的源码（`https://gitlab.com/kicad/code/kicad/-/raw/10.0.8/<路径>`），没有运行。
- **【手册】** 读了 `https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html`（下称“手册”，引节名和锚点）。
- **【本机】** 读了本机已装的 KiCad 10.0.8 的 `pcbnew.py`（`D:\KiCad\bin\Lib\site-packages\pcbnew.py`）和本仓库文件，没有运行。
- **【README】** 读了第三方项目的文档或源码，没有运行。
- **【网页】** 读了厂商或博客页面；注明“搜索摘要”的，只看到搜索结果里的摘录，没有打开原文，数字要当线索不当定论。
- **【未验证】** 没有证据，或只有推断。

没有运行 `kicad-cli`、DRC 或任何重计算。凡是只靠读源码得出的 DRC 行为，第 9 节列了要在小板上补做的实验。

---

## 0. 紧凑结论

| # | 问题 | 一句话答案 |
|---|---|---|
| 1 | 怎样识别差分对 | 只看网络名结尾：去掉末尾的数字和下划线后，最后一个字符是大写 `P`/`N` 或 `+`/`-`，且板上存在互补的那根网络【源码】。大小写敏感；`_t/_c`、`DP/DM`、`_p/_n` **不认**。手册说两种后缀不能混用【手册】。 |
| 2 | 差分对相关的约束项 | `diff_pair_gap`（min/opt/max，长度）、`diff_pair_uncoupled`（只有 max）、`skew` 加选项 `within_diff_pairs`、`length`。长度和 skew 还能写时间单位 `ps`。条件函数 `A.inDiffPair('基名')`、`AB.isCoupledDiffPair()`。语法见第 2 节。 |
| 3 | DRC 怎么判“耦合” | **只有两根线完全平行（方向向量叉积在 1 nm 整数下恰为 0）、投影有重叠、两段之间没有别的铜**，才算耦合段【源码】；不要求“近似平行”，也不要求和 PNS 一样的 45° 对称。圆弧只在“同心的圆弧对”之间算耦合。 |
| 4 | 非耦合长度 | `max(P 总长, N 总长)` 减去耦合段长度之和；总长只数走线和圆弧，不数过孔，不含 pad-to-die；间隙越界的耦合段算非耦合【源码】。 |
| 5 | 对内偏差 | `skew` 加 `within_diff_pairs`：每对内取较长的一根作基准，`abs(差) > max` 报错。每根网络的长度 = 走线（焊盘内和过孔盘内按“中心到出盘点的直线”折算）+ 过孔穿过的层间高度（`use_height_for_length_calcs` 开时）+ 该网络所有焊盘的 pad-to-die【源码】。 |
| 6 | pad-to-die | 焊盘属性里的“焊盘到芯片长度”（`PAD.GetPadToDieLength()`，另有 `GetPadToDieDelay()`），**计入** DRC 的 `length`/`skew` 和调整工具【源码、手册】。脚本可读写，本仓库的 `lengths` 目前不计。 |
| 7 | KiCad 自己的几何 | 耦合段是 45° 格上的一对平行线，出焊盘用“网关”（gateway）：两根线从焊盘锚点经 45° 引线汇到耦合间距；偏差补偿是**单根线上的一串方形或圆角凸起**，默认最小幅 0.2、最大幅 1.0、间距 0.6 mm（对内偏差工具）。第 4 节。 |
| 8 | pcbnew Python | 能读写走线、过孔、焊盘属性，`BOARD.DpCoupledNet(net)` 可用；**不能**调内置的调整，`PCB_TUNING_PATTERN` 没有 Python 类，长度计算类 `LENGTH_DELAY_CALCULATION` 只有不透明指针【本机】。 |
| 9 | 开源工具 | KiCadRoutingTools（MIT，0.24.0）有完整的差分对布线、对内和组内蛇形、pad-to-die、GND 返回过孔，是目前唯一现成的；Freerouting（GPL-3.0）没有差分对。其余只有检查脚本。第 6 节。 |
| 10 | 业内对内补偿约定 | 补在**较短一根**上、**靠近不等长产生处**（TI、Intel 的指南一致）；凸起要小而少、不平行、45° 或圆角；各家的尺寸数字不统一，没有查到权威的统一标准。第 7 节。 |

---

## 1. 范围和读了什么

本仓库状态【本机】：

- `Tools/KiCadDesignTools/routing/busroute/` 全是单端：线束（`bundle.py`）、BGA 扇出（`fanout.py`）、换层过孔阵、圆弧蛇形（`tune.py`）。没有差分对。
- `job.py` 的文档字符串里 `TUNING` 的组只有单端的 `spread`（组内最长减最短）和 `ref`（参考组）两种。
- `third_party/` 只有三个后处理脚本（`auto_tracks`、`auto_clean`、`auto_tidy`），处理 KiCadRoutingTools 的输出；`docs/tools.md` 的“用 KiCadRoutingTools 时”一节说它会拆掉手工走的差分对重走，要用 `--keep-input-copper` 等。
- 已有的差分对相关坑：K14（`diff_pair_gap_out_of_range` 规则名在报告里不带引号）、K53（拐点落在焊盘里的那一段 DRC 量短 0.01–0.07 mm）、K54（平行而不相邻的两段被当成耦合段）。模板 `templates/common/common.kicad_dru` 里有一条 `usb3_skew`，没有 `within_diff_pairs`，也没有验证过会触发（前作 3.3 节）。四层板的 `usb2_skew` / `usb2_gap` 在 `steval_fcu001v2/steval_fcu001v2.kicad_dru`。
- 规则：`docs/shape/routing.md` 的 RTE-2（预留补线空间、公式）、RTE-7（圆弧蛇形，半径取腿距一半）、RTE-14（容差按接口定）、RTE-15、RTE-4（默认不用通用自动布线器）。

---

## 2. KiCad 10 怎样识别差分对，自定义规则里的约束项

### 2.1 命名约定

手册“Routing differential pairs”（`#routing-differential-pairs`）【手册】：差分对是“有共同基名、一个正后缀一个负后缀”的两根网络；支持 `+`/`-` 或 `P`/`N`；“两种后缀不能混用”（`USB+` 和 `USB_N` 不成对）。

源码里的实际规则【源码】（`pcbnew/board.cpp` 的 `BOARD::MatchDpSuffix`，`pcbnew/drc/drc_engine.cpp` 的 `DRC_ENGINE::MatchDpSuffix` 和 `IsNetADiffPair`，两处逻辑相同）：

1. 从网络名末尾往前走，跳过数字 `0-9` 和下划线 `_`。
2. 遇到的第一个别的字符必须是 `+`、`-`、`N`、`P` 之一（**只认大写**），否则不是差分对。`P`/`+` 为正，`N`/`-` 为负。
3. 互补网络名 = 去掉这个字符后，把它换成相反的那个，后面的数字和下划线原样保留。所以 `DQS_P0` 配 `DQS_N0`，`CLK_P` 配 `CLK_N`。
4. 板上必须真的存在互补网络（`aBoard->FindNet`），否则不算。

不认的写法：`_p/_n`（小写）、`_t/_c`（DDR 的 DQS_t / CK_c）、`DP/DM`（USB：`USB_DP` 的互补被算成 `USB_DN`，不是 `USB_DM`）、`DPLUS/DMINUS`。这些要在原理图里改名成 `_P/_N` 才能被 DRC 和交互式布线器当差分对。手册没写 `_t/_c`，源码里也没有。

对比：KiCadRoutingTools 认的写法多得多（`_t/_c`、`DP/DM/DN` 等，其 `docs/differential-pairs.md` “Identifying Differential Pairs”）【README】，但这只对它自己有效，KiCad 的 DRC 不认。

名字里的层次前缀 `/` 不影响：判断只看末尾。`A.inDiffPair('/USB')` 的参数是基名，带层次前缀（手册 `inDiffPair('x')`，`#custom_rule_syntax` 的函数表）。

### 2.2 约束项的语法

出处：手册 `#custom_rule_syntax`（“Custom rule syntax”）的约束表、解析器 `pcbnew/drc/drc_rule_parser.cpp`【手册、源码】。

| 约束 | 子项 | 单位 | 检查什么（手册原文要点）和已知局限 |
|---|---|---|---|
| `diff_pair_gap` | `min` `opt` `max` | 长度（`mm`、`mil`、`in` 等，带单位） | 检查差分对两根线在**平行段**上的间隙；“不测非平行段（如从器件扇出的部分）”。`opt` 给交互式布线器放新对用，不触发错误。间隙是**边到边**（中心距减两线半宽之和）【源码，`extractDiffPairCoupledItems`】。 |
| `diff_pair_uncoupled` | 只有 `max`（`min` 和 `opt` 被忽略） | 长度 | 检查一对里“不和另一根耦合”的长度；“不平行，或超出 `diff_pair_gap` 范围，都算非耦合”。 |
| `skew` | `min` `opt` `max`，选项 `(within_diff_pairs)` | 长度或时间（`ps`） | 每根网络与组内最长那根的差；基准不可指定。`within_diff_pairs` 让规则“对每一对有效差分对分别检验”；不加则在所有命中的网络里比（总线）。`opt` 是 skew 调整工具的目标（缺省取 `min`，再缺省为 0）。 |
| `length` | `min` `opt` `max` | 长度或时间（`ps`） | 每根网络的总长；`opt` 是长度调整工具的目标。对内、对间的窗口都用它。 |
| `via_count` | `min` `max`，无单位 | — | 每根网络的过孔数。过孔高度开关关掉后它静默失效（前作 2.2 节）。 |

语法细节【源码，`drc_rule_parser.cpp`】：

- `within_diff_pairs` 只能用在 `skew`，用在别的约束上解析报错“within_diff_pairs option invalid for constraint type”。
- 每个值用 `parseValueWithUnits`；`length` 和 `skew` 允许时间单位，同一个约束里不能混用长度和时间（手册 `#setting_target_delay`）。写时间单位会让调整工具进入时间域，并需要“调整配置文件”（tuning profile，板设置里的每层传播延迟）。
- 单位前有空格可以（`52 mm`）、不带单位整个文件被跳过、规则行尾有 `#` 注释整个文件被跳过：这些是前作 3.2 节在命令行里实测过的，对差分对约束同样适用。

条件函数【手册，`#custom_rule_syntax` 函数表】：

- `A.inDiffPair('x')`：对象在差分对里，且基名匹配 `x`，`*`/`?` 通配；互补网络不存在时恒为假。
- `AB.isCoupledDiffPair()`：A、B 是同一对里相反极性的两根。用来给“差分对内部”放宽间距，例如手册示例：

```
(rule "Differential pair clearance"
    (condition "A.inDiffPair('*') && !AB.isCoupledDiffPair()")
    (constraint clearance (min 1.5mm)))
```

- 网络类里设的“差分对线宽/间隙”会生成隐含规则【源码，`drc_engine.cpp` 约 310–360 行】：线宽规则条件是 `A.hasExactNetclass(..) && A.inDiffPair('*')`；间隙规则为 `diff_pair_gap`，`min` 取板最小间距、`opt` 取网络类的差分对间隙，**没有 `max`**，所以网络类单独设置不会产生间隙超上限的报错（手册 `#drc` 里“Differential pair gap out of range”一节也这么说）。网络类的差分对间隙比普通间距小时，还会加一条只对 `AB.isCoupledDiffPair()` 生效的间距规则，把耦合对内部的最小间距降到差分对间隙。

时间域的字段：`length`/`skew` 约束写 `ps` 时，约束的 `TIME_DOMAIN` 选项打开，DRC 比较的是 `totalDelay`；需要板里有调整配置文件（每层单位延迟）。本项目用长度域，暂不涉及【源码，`drc_test_provider_matched_length.cpp` 的 `checkLengths`/`checkSkews`】。

---

## 3. DRC 怎样算

### 3.1 对内偏差（`skew` + `within_diff_pairs`）

源码 `pcbnew/drc/drc_test_provider_matched_length.cpp` 的 `checkSkews`【源码】：

1. 先把规则命中的网络按网络号放进表，对每根网络用 `m_board->DpCoupledNet()` 找互补网络，两根都在命中集里才成对。只命中一根的对被**悄悄跳过**（不报错）。
2. 每对里取较长的一根为基准；`skew = 自己 − 基准`；`abs(skew) > max` 报 `skew_out_of_range`。基准自己不受 `min` 约束。
3. 不加 `within_diff_pairs` 时，命中的所有网络是一组、基准是组内最长的那根（前作 2.3 节已实测）。

推论：同一网络类里有多对差分线时（四层板的 USB2 保护器件两侧各一对），要加 `within_diff_pairs`，否则两对互相比（本仓库 `docs/rule-profiles/A-general.md` 第 26 行已记）。

### 3.2 每根网络的“长度”是什么

`LENGTH_DELAY_CALCULATION::CalculateLengthDetails`（`pcbnew/length_delay_calculation/length_delay_calculation.cpp`），DRC 调用时选项是 `OptimiseVias`、`MergeTracks`、`OptimiseTracesInPads` 全开、`InferViaInPad` 关【源码】。总长 = `TrackLength + ViaLength + PadToDieLength`：

| 项 | 怎么算 | 出处 |
|---|---|---|
| 走线 | 同层首尾相接的线合并；圆弧按真弧长 | `mergeLines`；前作 2.1 节实测直线和圆弧与解析值差 < 0.0001 mm |
| 过孔盘内的走线 | 走线端点落在过孔盘内时，从盘边（与线的交点）算起，盘内部分不计 | `OptimiseTraceInVia`、`clipLineToVia` |
| 焊盘内的走线 | 走线端点正好在焊盘锚点（中心）且落在焊盘多边形内时，焊盘内的一段**换成“中心到出盘点的直线”**；所以焊盘里有折线时，DRC 量出来比几何短（K53 的原因） | `OptimiseTraceInPad`、`clipLineToPad` |
| 过孔 | 只算信号**实际用到的两层之间**的叠层高度（`optimiseVias`）；`use_height_for_length_calcs`（板设置 Constraints 页“Include stackup height in track length calculations”）关掉则为 0 | `ViaLength`；手册 `#length_tuning_pitfalls_and_tips`；前作 2.2 节 |
| 焊盘 | 网络里**每个**焊盘的 pad-to-die 都加上 | `PadToDieLength += item.GetPad()->GetPadToDieLength()` |
| 分支 | 整根网络所有分支都计入（DRC 不做点到点优化） | 前作 2.1 节；手册说调整工具只支持点对点网络 |

手册还说：调整工具算长度时“把路径优化成焊盘间最短”，Net Inspector 只是简单求和（`#length_tuning_pitfalls_and_tips`、`#net-inspector`）；DRC 用的是上表的优化口径（与调整工具同一个类）。Net Inspector 的“Via Length”是每个过孔的**整板高度**，和 DRC 不一样（手册 `#net-inspector`）。

对本仓库的含义：`routing/busroute/routes.py` 的 `lengths` 已经做到“走线 + 实际穿过的层间高度”（`tune.py` 文档字符串），缺三项：（a）焊盘内折线按“中心到出盘点直线”折算，（b）pad-to-die，（c）过孔盘内的走线截断。第 (a) 项 K53 已有对策：有长度规则的线把拐点放到焊盘外。

### 3.3 pad-to-die（封装内引线长度）

- 属性：焊盘属性对话框“Specify pad to die length”，写进板文件的 `(die_length <mm>)`；KiCad 10 新增 `(die_delay <ps>)`（“Specify pad to die delay”）【手册焊盘属性一节（Fabrication property 一带，我没有记下锚点），KiCadRoutingTools 文档 `length-matching.md` 的“Pad-to-Die Length”也写了这两个记号】。
- 计入哪里：手册说它“会被长度调整工具和 Net Inspector 加到走线长度上”；源码里 DRC 的 `length`/`skew` 也加【源码，见 3.2】。自定义规则里还有属性 `A.Pad_To_Die_Length`（手册属性表）。
- 差分对调整工具量对内偏差时，每根线的长度 = 该线两端焊盘的 pad-to-die + 走线【源码，`pns_meander_skew_placer.cpp` 的 `Start`：`m_padToDieLengthP/N`】；对长度调整（成对）则取 `max(P 总, N 总)`（`pns_dp_meander_placer.cpp` 的 `origPathLength`）。
- Python：`PAD.GetPadToDieLength()` / `SetPadToDieLength(int)`、`GetPadToDieDelay()` / `SetPadToDieDelay(int)` 都可用【本机，`pcbnew.py` 第 15455–15469 行】。
- 注意：RK3568 这类封装的内部引线长度表要自己填进焊盘（KiCad 库里的封装通常是 0，前作 2.1 节同）；填了之后 DRC 的长度就含它，这和 #12 约定“不计封装内长度”的口径相反，要在 SPEC 里选一个。

### 3.4 非耦合长度和间隙（`diff_pair_gap`、`diff_pair_uncoupled`）

源码 `pcbnew/drc/drc_test_provider_diff_pair_coupling.cpp`【源码，行号按 10.0.8 标签】：

**什么算耦合段**（`extractDiffPairCoupledItems`，约 295–392 行）。对 P 网络的每根直线段和 N 网络的每根直线段：

1. 两段所在层集有交集；
2. 两段各自平方长度 > 2（单位 1 nm 的平方，即长度约 > 1.4 nm）；
3. `!ssp.Intersect(ssn, false, true)`。第三个参数 `aLines = true` 表示按**无限长直线**求交（`libs/kimath/src/geometry/seg.cpp` 的 `SEG::intersects`）：不平行的两段，所在直线必有交点，**直接被排除**；平行不共线时 `determinant == 0 && collinear_test != 0`，返回无交点，通过；共线则按直线算有交点，被排除。`determinant` 是方向向量叉积，用 1 nm 整数算，**必须恰为 0**；
4. `commonParallelProjection`：P 段在 N 段所在直线上的投影与 N 段有重叠（重叠长度为 0 不算）；取重叠部分作耦合段；
5. 两个耦合段的最近点连线上，用铜 R 树查有没有别的铜（排除自身、与耦合段端点相连的走线/过孔、从焊盘出线的那一根）；没有才算耦合。

间隙 = 两耦合段最近点距离 − (wP + wN) / 2。**不要求两线宽度相同，也不要求间隙恒定**，只看每对耦合段。
**圆弧**：只有 P 的圆弧和 N 的圆弧之间才配对，且要求“圆心距小于线宽”（几乎同心）、半径差比 ≤ 0.5、重叠角 > `MinParallelAngle`（0.001°）、两个裁剪弧长都 ≥ 1 nm。圆弧和直线之间不配对【源码，约 108–205 行、396–487 行】。

**判定**（`Run`，约 491–772 行）：

- 间隙的上下限比较带容差 `DRCEpsilon`（高级配置默认 0.0005 mm = 0.5 µm，`common/advanced_config.cpp` 第 247 行）。
- 越界的耦合段**不计入**耦合长度。
- `totalLen = max(N 总长, P 总长)`；这里的“长度”只数该网络里的走线和圆弧（`PCB_TRACK::GetLength`），**不含过孔、不含 pad-to-die**，且**排除**属于 KiCad 调整图形（`tuning_pattern` 生成器）的走线。
- `非耦合长度 = totalLen − Σ耦合长度`；`diff_pair_uncoupled (max X)` 当它 > X 时报 `diff_pair_uncoupled_length_too_long`。
- **间隙越界的报告有个条件**：只有“没有写 `diff_pair_uncoupled` 规则，或者非耦合长度已经超限”时才逐段报 `diff_pair_gap_out_of_range`。也就是说，同时写了两条规则时，间隙越界是“花非耦合预算”，预算没超就不报。

对本项目的含义：

- 脚本写进板文件的走线只要满足“平行（整数叉积为 0）+ 无他铜隔开 + 间隙在窗口内”，就会被当成耦合，**不需要**任何特殊标记。
- 脚本偏移出 P/N 两根线时，要保证偏移是**整数 nm 向量**：对 45° 线，P 段 `(x0,y0)-(x0+L,y0+L)` 偏移 `(a,−a)`（a 为整数 nm）后方向向量仍是 `(L,L)`，叉积为 0；如果两端各自独立取整、或者用 `d/√2` 浮点后分别取整，端点偏差 1 nm 就会让叉积不为 0，整段“消失”成非耦合。对策：先在整数坐标里确定 P 线的顶点，N 线的每个顶点 = P 线对应顶点加同一个整数偏移（拐角处按角平分线的整数偏移），不要两条线各算各的。这一条是从源码推出来的，需要用小板验证（第 9 节实验 E1）。
- 间隙取整数 nm 的偏移，意味着 45° 段的间隙是 `a·√2` 减线宽，不是任意值；规格里取间隙时留 ±1 nm 级的余地不成问题（容差 0.5 µm）。
- K54 的现象就是这个定义的直接结果：两段都是 45°、平行、投影重叠，哪怕相距 1.66 mm 也配对，间隙超 max 报错。解法是让投影不重叠，或者放宽 `max`。
- 扇出段（两线不平行）被算成非耦合，所以 `diff_pair_uncoupled` 的预算要覆盖出焊盘和出 BGA 的张开段；成对换层的过孔附近也一样（过孔不计长度，但过孔两侧的线若不平行就是非耦合）。
- 补偿凸起：对内补偿的凸起放在较短一根上，凸起的两条竖边与 N 线垂直（投影重叠为零，非耦合），凸起顶边与 N 线平行且投影重叠，**距离变大**：没写 `diff_pair_gap (max ..)` 时它仍算耦合；写了 max 就越界、算非耦合。它是否被“两线之间有别的铜”挡住（凸起往外凸时，P 线本体正好在顶边和 N 线之间），源码上要靠铜 R 树的 `CheckColliding` 判定，**【未验证】**，实验 E2。
- KiCad 自己生成的调整图形里的线被源码**整体排除**（`isInTuningPattern`）：既不算耦合，也不进 `totalLen`。脚本写的普通走线没有这个豁免。前作 3b 节试过把脚本写的走线包进 `(generated … tuning_pattern)`：板文件层面能读、能存，但界面里能不能重生成没验证。**不建议**靠它躲开非耦合检查：被排除的线连长度都不进 `diff_pair_uncoupled` 的 `totalLen`，但 `length`/`skew` 照算，口径就分叉了。

### 3.5 已知的其他局限（手册和源码）

- 调整工具只支持点对点网络；遇到分支就停在分支处（手册 `#length_tuning_pitfalls_and_tips`）。
- 差分对长度调整只能用在耦合段；非耦合段只能用单根线调整（手册 `#length-tuning`）。
- DRC 的 `skew` 基准是组内最长，不能指定基准（前作 2.3 节），所以“数据线对时钟 ±X”要用 `length` 窗口（RTE-2 的现状）。
- 命令行下规则文件有错会静默整个跳过（前作 3.2 节，K1）。
- 间隙检查不管线宽是否一致、不管是否在同一个网络类。

---

## 4. KiCad 交互式差分对走线和偏差调整的几何

### 4.1 差分对走线（PNS 的 `pns_diff_pair*.cpp`）【源码】

- 耦合段：两根线是 45° 格上的平行线，间距取自规则（`diff_pair_gap` 的 `opt`，或网络类的差分对间隙，手册 `#routing-differential-pairs`）。PNS 自己的“耦合”判据比 DRC 严一点：`ApproxParallel(…, 2)` 加“间隙落在窗口内”加投影重叠（`DIFF_PAIR::CoupledSegmentPairs`，`pns_diff_pair.cpp` 约 869–900 行）。
- 出焊盘：手册说“起点或终点两根线的距离和设定间隙不同时，路由器会生成一小段‘扇出’以缩短非耦合长度”（`#routing-differential-pairs`）。源码里这叫**网关**（`DP_GATEWAYS`，`BuildGeneric` 和 `BuildFromPrimitivePair`）：对一对焊盘或过孔，枚举若干“耦合间隙的锚点对”（中点出线：两根线在焊盘连线的中点两侧各半个间隙；直线直线交点型；直线对角线混合型等，各有优先级，焊盘距离大于 3 倍间隙时中点出线优先级更高），每个网关带两条“入线”，用 `DIRECTION_45::BuildInitialTrace` 在 45° 格里从焊盘锚点画到网关锚点。继续已有的差分对时，还会加“把锚点斜 22.5° 外扩 `间隙·sin 22.5°`”的网关（`buildDpContinuation`）。
- 换层：手册：“换层或放过孔时，路由器放两个相邻的过孔，在遵守铜和孔间距的前提下尽量靠近”（`#routing-differential-pairs`）。源码里过孔间隙取 `max(板最小间距, 规则 via_gap)`，网络类里也有“差分对过孔间隙”（`pns_kicad_iface.cpp` 约 1224–1283 行；`NETCLASS.GetDiffPairViaGap()` 在 Python 里可读）。**没有放回流地过孔的功能。**
- 起始点比间隙窄时（BGA 颈缩区），允许“4 倍间隙”的过渡窗口（`DIFF_PAIR::BuildInitial` 的注释和 `transitionRadius = 4 * configuredGap`）。

### 4.2 长度调整图形（`pns_meander*.cpp`、`pcb_tuning_pattern.cpp`）【源码、手册】

参数（`MEANDER_SETTINGS`，`pns_meander.cpp` 构造函数；板默认值在 `board_design_settings.cpp/h`）：

| 参数 | 缺省 | 说明 |
|---|---|---|
| 最小幅 `m_minAmplitude` | 0.2 mm | 圆角样式下还要 ≥ `|基线偏移| + 线宽` |
| 最大幅 `m_maxAmplitude` | 1.0 mm | 从最大幅往下按 `m_step`（0.05 mm）试，装得下的最大幅 |
| 间距 `m_spacing` | 单根和对内偏差 0.6 mm，成对长度 1.0 mm（`DEFAULT_MEANDER_SPACING`、`DEFAULT_DP_MEANDER_SPACING`） | 实际间距取 `max(线宽 + 间隙, m_spacing)`；成对时再加 `2·|基线偏移|` |
| 圆角百分比 | 80 | 圆角半径 = 间距 × 百分比 / 2，夹在“`|偏移| + 线宽/2`”和“`min((幅 + |偏移|)/2, 间距/2)`”之间 |
| 样式 | 圆角（`MEANDER_STYLE_ROUND`），可选 45° 倒角 | |
| 单侧、初始侧 | 默认两侧交替 | |
| 长度容差 | 0.1 mm | `DEFAULT_LENGTH_TOLERANCE`；目标取自 `length`/`skew` 规则的 `opt`（缺省取 `min`） |

形状（`MEANDER_TYPE`）：单侧 `_|^|_`、起头 `_|^|`、收尾 `|^|_`、转折 `|^|`；每个凸起的补长约 `2·幅 − 2.34·倒角`（KiCadRoutingTools 文档对自己的倒角版本给的式子，KiCad 的圆角版本由几何决定，本项目的 RTE-2 式子 `n(2a − 0.858p)` 是圆弧版的精确式）。

三种工具【源码】：

- **单根线长度调整**（`MEANDER_PLACER`）：把用户点的那一段切成前、调、后三段，对“调”的部分按用户的光标位置生成凸起，到目标长度为止。起头和收尾由用户选位置，**没有“靠近不等长产生处”的自动逻辑**。
- **差分对长度调整**（`DP_MEANDER_PLACER`）：对耦合段的**中线**（两根线对应端点的平均）生成“双线凸起”，两根线是同心的圆弧或倒角，基线偏移 = `(间隙 + 线宽)/2`；长度按 `max(P 总长 + pad-to-die, N 总长 + pad-to-die)` 算。成对凸起的最小圆角半径 = `|偏移| + 线宽/2`，这是 P/N 不交叉的几何下限。
- **差分对偏差调整**（`MEANDER_SKEW_PLACER`）：只往**用户点的那一根**线上加凸起，目标 = 另一根线的长度（含 pad-to-die）+ 目标偏差；也是用户选位置。

调整图形的存储【源码，`pcbnew/generators/pcb_tuning_pattern.cpp` 的 `GetProperties`】：一个 `PCB_GENERATOR`，类型字符串 `tuning_pattern`，属性有 `tuning_mode`、`initial_side`、`end`、`corner_radius_percent`、`single_sided`、`rounded`、`min_amplitude`、`max_amplitude`、`min_spacing`、`target_length(_min/_max)`、`target_delay`、`target_skew`、`override_custom_rules` 等；走线本身是普通的 `segment`/`arc`，放在一个组里。要在 KiCad 界面里更新（Edit → Update All Tuning Patterns）必须经过 PNS 路由器重新生成基线（`Update`、`initBaseLines`），脚本不能在界面外触发（见第 5 节）。

对本项目的含义：KiCad 的偏差工具生成的是**单根线上整块的方凸起或圆角凸起**，没有“把补偿分成几个小凸起放在不等长处”的逻辑；本项目 `tune.py` 的圆弧蛇形（半径取腿距一半、单侧、块内等高）和它是同一类形状，只缺“放在较短一根上、成对的避让”。

---

## 5. pcbnew Python 接口里能用的部分

读的是本机 `pcbnew.py`（10.0.8）【本机】：

| 能力 | 有没有 | 说明 |
|---|---|---|
| 判断一对差分网络 | 有 | `BOARD.DpCoupledNet(NETINFO_ITEM)` 返回互补网络或 `None`；`BOARD.MatchDpSuffix`、`DRC_ENGINE.IsNetADiffPair` 没有导出（行为与第 2.1 节一致，自己写一个等价的 8 行函数更稳） |
| 网络类的差分对线宽、间隙、过孔间隙 | 有 | `NETCLASS.GetDiffPairWidth/Gap/ViaGap`（及 `*Opt`、`Set*`、`*Parent`）；板的当前差分对尺寸 `BOARD_DESIGN_SETTINGS.GetCurrentDiffPairViaGap` 等 |
| pad-to-die | 有 | 见 3.3 |
| 过孔高度开关 | 有 | `BOARD_DESIGN_SETTINGS.m_UseHeightForLengthCalcs` |
| 长度计算器 | **没有可用接口** | `BOARD.GetLengthCalculation()` 返回 `LENGTH_DELAY_CALCULATION *`，`pcbnew.py` 里没有这个类的包装，拿到的是不透明指针；调不了 `CalculateLengthDetails` |
| 调整图形 | **没有类** | `BOARD.Generators()` 返回 `GENERATORS`（`PCB_GENERATOR` 的 deque），有枚举 `PCB_GENERATOR_T`，但没有 `PCB_GENERATOR` 和 `PCB_TUNING_PATTERN` 的 Python 类（前作 3 节也这么试出来）；也不能从 Python 触发内置调整 |
| 内置调整的触发 | 只有界面内的动作 | IPC API（`kipy`）只能按名字运行界面动作，需要界面开着（前作 3 节，【源码，未执行】）；`kicad-cli pcb` 没有调整命令 |
| 写走线、圆弧、过孔 | 有 | 这是本仓库现在的做法（`PCB_TRACK`、`PCB_ARC`、`PCB_VIA`），差分对不需要额外对象：P、N 是两个网络上的普通走线 |

所以：**内置调整不能脚本化**，生成的 tuning pattern 对象在 Python 里读不了也建不了；脚本只能写普通走线。DRC 当长度量具的办法（`rules.drc_probe`，前作 3.4 节原型）仍是唯一能得到“KiCad 口径长度”的路径。

---

## 6. 开源工具里现成的实现

### 6.1 KiCadRoutingTools（本仓库 `Tools/KiCadRoutingTools/`，gitignore，0.24.0）

- 许可：MIT（`LICENSE`，作者 Andy Haas，仓库 `https://github.com/drandyhaas/KiCadRoutingTools`）【README】。
- 差分对功能（`docs/differential-pairs.md`、`docs/length-matching.md`、`py_router/diff_pair_routing.py` 6600 行、`length_matching.py` 5200 行、`diff_pair_loop.py`、`diff_pair_multipoint.py`、`diff_xnet.py`）：
  - 识别命名比 KiCad 宽（`_P/_N`、`_t/_c`、`DP/DM`、`+/-` 等）。
  - **中线 + 偏移**：先在 (x, y, θ) 位姿空间上用带 Dubins 启发的 A* 走一条中线，再按角平分线偏移出 P/N（`create_parallel_path_from_float`，拐角处按 `2/长度` 缩放保持垂直间距），出焊盘用“后退位置”（setback）阶梯和 9 个角度试出清空位置；支持裸焊盘端点、多点对（3 个以上端点，链式腿）、混合（耦合中段 + 单端腿）、短对退化为单端、极性交换（默认关）。
  - **成对换层**：过孔放在中线两侧，偏移 `max(间隙, 过孔中心距/2, 线到对侧过孔所需间距 − 间隙)`（`_pair_via_offset`）；过孔前后各要有一段 ±45° 内的共线进出（“共线过孔约束”）；换层代价加倍。
  - **回流地过孔**：默认在每对信号过孔旁放 GND 过孔，沿线方向偏 `过孔直径 + 间距`，垂直方向偏 `对内间距 + 线宽/2 + 间距 + 过孔直径/2`，前后两侧各试一个（`_gnd_via_offsets`、`_create_gnd_vias`）；放不下就不放并报告；`--no-gnd-vias` 关闭。
  - **长度匹配**：组间（对和对）对**中线**做梯形/圆角凸起，再由中线重新生成 P/N，所以保持对称；组内凸起 `generate_centerline_meander`，倒角取“P/N 半间距的 1.5 倍”（`--diff-chamfer-extra`，>1 防止 P/N 在拐角交叉）；**对内偏差**用 `--diff-pair-intra-match` 往较短一根上加小凸起（最小幅 0.1 mm，凸起要避让对侧线），算的是“铺在板上的铜”的偏差，按 KiCad 的口径（pad-to-die、过孔层间高度、焊盘内截断），出来后再按 `net_queries.diff_pair_skew` 复核，超容差再补一次（“用交付铜重算”）；对内偏差一对 = 较大腿，与 KiCad 的对调整一致。
  - 另有：时间匹配、AC 耦合（串联隔直电容两侧的两对按总长配）、DDR 字节组自动分组（`auto_group_ddr4_nets`）。
- 质量证据（只读文档和目录，没有运行）：README 称每次改动都在“真实开源板子语料”上做 A/B（DRC 违规和未连接数）、约 770 个测试文件；文档里大量带 issue 号的修补（#1218、#1303、#1583、#1622 等）说明边角情况多、迭代快。本仓库对它的使用记录见 `docs/tools.md` “用 KiCadRoutingTools 时”：线形被判不整齐、会缩尺寸、会拆手工差分对重走；`docs/shape/routing.md` 的 RTE-4 把它降为“例外才用”。
- 能不能直接用：作为**整套布线器**不符合本项目的“脚本生成、确定性、线形整齐”路线（RTE-4、RTE-13）；作为**算法和数值的参考**很有价值，见第 8 节。可以借用代码（MIT，需保留版权声明），但要自己重写成确定性的、整数坐标的版本，不要照搬它的网格 A*。

### 6.2 Freerouting

- 许可 GPL-3.0；README 没有提差分对和等长，只有网络类的“忽略指定网络类”选项（`https://github.com/freerouting/freerouting`，【网页】）。
- 议题 #358 “Differential pair routing”（`https://github.com/freerouting/freerouting/issues/358`）：2024-10-17 维护者回复“没有时间做，欢迎社区提 PR”，2025-02-21 被机器人按“过期”关闭，没有实现（【网页】）。
- 结论：没有差分对支持；GPL 也不能并入本仓库的工具。

### 6.3 其他

- `mithro/kicad-length-matching-checks`（BSD-3-Clause）：两个检查脚本（`length_match.py`、`diff_pair.py`），只检查不生成，README 没提 pad-to-die 和过孔（`https://github.com/mithro/kicad-length-matching-checks`，【网页】）。价值不大，KiCad 10 的 DRC 已经内置这些检查。
- Python 的“长度总和”小脚本（gist）：忽略几何和多端，不可用（搜索摘要，没有打开）。
- KiCad 自己的路由器是 C++ 且依赖界面（第 5 节）。
- Altium、Cadence 等是商用，只作术语和约定的参照（第 7 节）。
- 没有查到别的开源 KiCad 差分对布线或蛇形生成库；这一点是“没查到”，不是“没有”。

---

## 7. 业内对内补偿的约定

没有找到一份权威、统一、带尺寸数字的标准；下面按可靠程度排列。

### 7.1 放哪一端

- **补在较短的那根上，靠近不等长产生的位置**：
  - TI Jacinto 7 高速接口布局指南 SPRACP4A 第 2.3 节“Differential Signal Length Matching”：“When matching the intra-pair skew of the high-speed signals, add serpentine routing to match the lengths as close to the mismatched ends as possible”（`https://ti.com/document-viewer/lit/html/SPRACP4A/GUID-0D0B8295-DB95-4D93-B0D8-B9648C839B29`，【网页，已打开】）。
  - TI DS320PR1601 的指南（SNLA426）：搜索摘要说“不匹配要在它出现的差分线段的起点处补偿”（`https://ti.com/document-viewer/lit/html/SNLA426/GUID-2070A710-E25B-4C99-A3BA-E7AB876AA5C9` 一带，【网页，搜索摘要，没有打开这一节】；我打开的 SNLA426 另一节只有“蛇形应避免”和“蛇形长度至少 3×线宽”，见 7.2）。
  - Intel（现 Altera）Agilex 7 的 PCB 指南：搜索摘要的小标题是“intrapair deskew close to the skew-happening location”，并建议“从发送端开始，在接收端结束，偏差一出现就补”（`https://www.intel.com/content/www/us/en/docs/programmable/683864/current/pcb-traces.html`，【网页，搜索摘要，原文要重定向，没有取到】）。
  - Cadence 博客：补在较短一根上，“最好放在长度开始分叉的拐角处或附近”（`https://resources.pcb.cadence.com/blog/2025-differential-pair-length-matching-guidelines`，【网页，搜索摘要，正文没取到】）。
- Altium 用户的对应做法【网页，已打开】`https://www.altium.com/documentation/altium-designer/pcb/high-speed-design/length-tuning`：对内用“Within Differential Pair Length”约束，只调较短那根（Route » Interactive Length Tuning）；静态相位匹配“可以加在较短那根的任意位置”，动态相位匹配“通常沿较短那根的多点添加”；自动对内调整用 Sawtooth（锯齿）样式，以减少对阻抗平衡的扰动。
- 仿真证据（单一来源，不是标准）：Copperhead 用 openEMS 对一个 U 形弯的 16 Gb/s 差分对做了 140 次仿真：等长补偿只去掉了弯产生偏差的 44–75%；补偿放在弯处比放在发送端（launch）好（61% 对 53%）；少而宽的凸起比多个小凸起好（每个凸起的效率 0.74 对 0.44），凸起之间的间距压到最小间距规则会损失 16–24 个百分点；“把整对绕出去”完全不能减小对内偏差（`https://copperhead.sh/research/diffpair-meanders/`，【网页，已打开】）。它是仿真，只有一种线宽和间距，作者自己也说结论不是普适的。**它和“多个小凸起”的说法相反**，说明“小凸起”只是一种约定，不是定论。

小结：位置共识 = **较短一根、靠近不等长的来源（出焊盘处的扇出、弯、过孔），不要拖到链路尾部**。

### 7.2 凸起的典型尺寸

| 来源 | 数字 | 备注 |
|---|---|---|
| KiCad 10 缺省（源码） | 幅 0.2–1.0 mm，步长 0.05，间距 0.6 mm（成对 1.0 mm），圆角 80% | 默认值不是标准，是工具缺省 |
| TI SNLA426 第 17 节 | 蛇形长度“至少 3×W 或 3×RPH，取大者”；蛇形会把紧耦合变松耦合；加宽线补阻抗 | `https://ti.com/document-viewer/lit/html/SNLA426/GUID-E8B065A9-CC09-40E3-917A-20764C2CBBD6`，【网页，已打开】；“RPH”页面上没解释，我没有查到定义 |
| Intel AN 958 5.1.5.3 | 蛇形用 45° 弯，高速时两线“不要在任何地方互相平行”；松耦合对用“分开再回来”的形状；紧耦合对在引脚处补偿 | `https://docs.altera.com/r/docs/683073/current/an-958-board-design-guidelines/skew-minimization`，【网页，已打开】；无尺寸数字 |
| Intel Agilex 5 PCB 指南 | 蛇形长度小于 100 mil，用 45° 弯或弧 | 【网页，搜索摘要】 |
| AtlasPCB（厂商博客，搜索摘要的归属） | 蛇形段之间间距 ≥ 4×线宽（防自串扰），幅度 ≥ 2×线宽，放在偏差源之后 | `https://www.atlaspcb.com/blog/pcb-impedance-matching-differential-pairs/`，【网页，搜索摘要，没有打开，也没有核对数字出自这一篇；非一手】 |
| Microchip 高速布局页（搜索摘要） | 对内偏差 < 5 mil | 没有打开原文，只作容差线索 |

“长度不超过线宽的若干倍、高度不超过间距的若干倍”这种说法，我没有在一手资料里找到明确出处；上面这些数字（3×W 的最小长度、≥4×W 的间距、小于 100 mil 的总长）是能查到的全部。**这一条要写进规格时，用本项目自己的原型定数，不要引用成行业标准。**

### 7.3 成对换层过孔和回流地过孔

- TI DS250DF230 数据手册 11.1 节第 7 条：“If vias are used for the high-speed signals, the ground via must be implemented adjacent to the signal via. For differential pair, the typical via configuration is ground-signal-signal-ground.”（`https://ti.com/document-viewer/DS250DF230/datasheet/GUID-65462836-B6D8-4841-BAFF-72897B954A86`，【网页，已打开】，没有距离数字）
- 距离数字：TI 某文档“对称地放在信号过孔 200 mil（中心距）以内，越近越好”；Cadence 电子书“1–2 mm 以内，差分对换层尤其要紧”（搜索摘要，没有打开原文，不能当定论）。IEEE EMC 学会的设计提示称把参考地过孔从不对称位置移到对称位置，共模转换降了 40 dB 以上，仅一个例子（`https://ewh.ieee.org/soc/emcs/acstrial/newsletters/winter11/DesignTips.html`，搜索摘要）。
- 两个信号过孔之间怎么放：KiCad 是“尽量靠近、遵守间距”（4.1 节）；KiCadRoutingTools 是中线两侧、偏移 `max(…)`（6.1 节）。**P、N 两个过孔放在同一层对上，P 线和 N 线换层前后的走线长度对称**：这条是常识，我没有找到带数字的一手出处。
- 过孔不计入 DRC 的非耦合长度，但会让两侧的线不平行（见 3.4）；要在 `diff_pair_uncoupled` 里留预算。

---

## 8. 结论：直接用 KiCad 检查的、要自己写的、可以借的

### 8.1 可以直接用 KiCad 的规则检查

| 要查什么 | 规则 | 备注 |
|---|---|---|
| 对内偏差 | `(constraint skew (max X) (within_diff_pairs))`，条件按网络类 | 一类里有多对时必须带 `within_diff_pairs`；结果含过孔层间高度和 pad-to-die |
| 对间（组内）窗口 | `length (min..)(opt..)(max..)`，由 `rules.len_rules` 生成 | 现有流程；差分对的“对长”取哪根？DRC 每根网络分别判，两根都进窗口即可 |
| 耦合间隙范围 | `diff_pair_gap (min..)(max..)` | 条件 `A.inDiffPair('*')` 加网络类；注意 K54 |
| 非耦合长度预算 | `diff_pair_uncoupled (max ..)` | 同上；扇出、换层和补偿凸起都花这份预算 |
| 对内走线的间距（耦合段内部缩小） | 网络类的差分对间隙 + `AB.isCoupledDiffPair()` 隐含规则 | KiCad 自动生成 |
| P/N 过孔数相同 | `via_count (max n)` 对两根都写同一个 n | 只能限上限，不能判相等；要判相等得自己写 |
| 长度表 | 前作 3.4 节的探针法（`rules.drc_probe`、`len_rules`） | 已有；差分对每根网络一行，对内偏差再自己减 |

### 8.2 KiCad 查不了，几何要在 busroute 里自己写

1. **成对布线本体**：从两个端点（球或焊盘）出线，生成耦合的 P/N 线束：中线 + 整数偏移（保证叉积为 0）、45° 倒角或圆弧（圆弧要两根线同心，才被 DRC 当耦合，3.4 节）。线束已有的“车道”概念（`bundle.py`）要扩成“一条车道占两根线的宽度”。
2. **成对出 BGA**：球对的出线（“网关”思路：KiCad 的网关枚举 + 本项目的确定性规则，不用搜索）；差分球成对引出到球区外并停在线头上；对 `escape_check` 的口径要加“对”的判定（两根线同时出得去）。
3. **成对换层**：过孔对的位置（两个过孔 + 对称的回流地过孔）和过孔前后的共线进出；和现有的“换层过孔阵”（`bundle.py`）合并，P/N 过孔数、层序必须相同。
4. **对内补偿**：放在较短一根、靠近不等长产生处的小凸起（KiCad 没有这种自动放置）；要求：避让对侧线（凸起往外凸，不往对侧凸）、凸起在焊盘和过孔盘之外（K53）、和 `tune.py` 的圆弧形状一致（半径取腿距一半，RTE-7）。
5. **长度口径补全**：`routes.lengths` 要加 pad-to-die、焊盘内折线按“中心到出盘点直线”折算（或要求拐点在盘外）、过孔盘内走线截断，才与 DRC 完全一致；对的长度取较长一根（`pns_dp_meander_placer.cpp`）。
6. **差分对并入组内等长**：把一对当成组里的一个成员（长度 = 较长腿），组内补偿放在对的中线上（两根线同时补，用 KiCad 的成对凸起几何：基线偏移 = (间隙 + 线宽)/2，最小圆角半径 = 偏移 + 线宽/2，成对间距再加 2×偏移），对内偏差最后补（KiCadRoutingTools 的执行顺序：先组间、后对内，因为组间重新生成两根线会抹掉对内凸起；其文档 `differential-pairs.md` “Execution order”）。
7. **检查**：非耦合长度预算的估算（在构建阶段先算，不等 DRC）、回流地过孔是否在、P/N 过孔是否成对对称、凸起是否在较短一根上。这些 KiCad 都不查。

### 8.3 值得借的算法和代码（KiCadRoutingTools，MIT）

| 值得借的 | 在哪里 | 怎么借 |
|---|---|---|
| 中线偏移出 P/N 的拐角处理（角平分线、`2/长度` 缩放） | `diff_pair_routing.py::create_parallel_path_from_float` | 思路借，坐标改成整数 nm；偏移向量统一取整 |
| P/N 过孔和 GND 过孔的偏移公式 | `_pair_via_offset`、`_gnd_via_offsets`、`_layer_track_via_offset`（`docs/differential-pairs.md` “Via Positions”、“GND Via Placement”也列了） | 公式直接用，数值换成本项目 `Profile` 的间距 |
| 对内偏差的“用交付铜复核再补一次” | `length_matching.py::regrade_intra_pair_reports`、`rematch_intra_pairs_on_shipped_copper` | 思路借：本项目已有 DRC 当量具，可在构建最后一步量一次、超容差再补 |
| 对的长度 = 较大腿、pad-to-die 按腿加 | `member_pad_to_die`、`pair_leg_metric` | 口径借（与 KiCad 一致） |
| 先组间后对内的顺序 | `docs/differential-pairs.md` “Execution order” | 照用 |
| 中线凸起倒角取 P/N 半间距的 1.5 倍以上，防止交叉 | `--diff-chamfer-extra`、`resolve_meander_chamfer` | 本项目是圆弧，等价条件是圆弧半径 ≥ `|偏移| + 线宽/2`（KiCad 的 `cornerRadius` 下限） |
| 不值得借 | 位姿 A* 加 Dubins 启发、网格吸附、极性交换、后处理清理 | 与 RTE-4 的“脚本确定性生成”冲突；它的清理步骤会改动已匹配的长度（它自己的 issue #1622 就是这个问题） |

### 8.4 不确定或没查到的

- DRC 对“凸起顶边和对侧线之间有没有铜”的判定（3.4 节 E2）；
- 脚本偏移的整数取整是否真的会让叉积非零而丢耦合（3.4 节 E1）——源码层面推出来的，没有运行；
- `skew within_diff_pairs` 在网络没有互补网络（只命中一根）时静默跳过，我没有实测；
- KiCad 10 的 `(die_delay)` 在 DRC 空间域里是否有影响：源码里 `totalPadToDie` 是长度，`PadToDieDelay` 只进时间域；
- “RPH”（TI SNLA426）的含义、TI 200 mil 和 Cadence 1–2 mm 的原文：只有搜索摘要；
- Intel/Altera 的 Agilex 7 指南和 AN 958 原文：Intel 的页面现在重定向到 `docs.altera.com`，只取到 AN 958 的 5.1.5.3 节，Agilex 7 一节只有搜索摘要；
- 回流地过孔的一手距离数字和凸起尺寸比例，没有找到可靠一手来源；
- 没有逐个核对 KiCadRoutingTools 的实际输出质量（只读了文档和函数清单）；用户的记忆里它的线形被判不整齐（RTE-4 的 Why），这一条针对单端自动布线，差分对没单独试过。

---

## 9. 建议补做的小实验（不在本篇范围，没有运行）

都在小板上用 `kicad-cli` 只跑 DRC，经构建入口或 `core/heavy`，一次一个：

- **E1 整数偏移**：一对 45° 线，P 端点整数，N 端点分别用（a）同一整数向量偏移、（b）`d/√2` 浮点后各自四舍五入、（c）故意差 1 nm；看哪种被算成耦合（有没有 `diff_pair_gap_out_of_range` 或 `diff_pair_uncoupled` 的计数变化）。
- **E2 补偿凸起**：在较短一根上放一个单侧凸起（朝外凸、朝对侧凸各一个），分别在 `diff_pair_gap (max)` 有、无时看顶边是否算耦合、非耦合长度增加多少；同时放一个圆弧凸起看圆弧不配对的影响。
- **E3 pad-to-die 和焊盘内折线**：给 P 焊盘填 `die_length`，看 `skew within_diff_pairs` 的报告值；再把焊盘里的折线放进/移出焊盘，验证 3.2 节的折算和 K53。
- **E4 只命中一根**：`skew (within_diff_pairs)` 规则只命中一对里的一根网络，看是否静默。
- **E5 成对换层**：一对 P/N 过孔加两个 GND 过孔，看 `diff_pair_uncoupled` 的值是否按 3.4 节的预期（过孔两侧不平行段计入非耦合）。

---

## 10. 对工具设计的几条直接建议

1. 先写**检查**再写生成：成对线束的几何检查（整数叉积为零、间隙、对称、凸起位置）和长度口径补全（pad-to-die、焊盘内折线），可以直接对着现有手工差分对（四层板的 USB2、H743 的以太网对）验证，不依赖新生成器。
2. 对内偏差统一用 `skew … within_diff_pairs`，对间用 `length` 窗口；差分对的“组内长度”取较长腿，和 KiCad、KiCadRoutingTools 一致。
3. 补偿凸起默认放较短一根、靠近出焊盘或第一个弯；预算里先扣 `diff_pair_uncoupled`。
4. 圆弧凸起不被 DRC 当耦合（圆弧只和同心圆弧配对），这对对内补偿是好事（不会触发间隙越界），对成对蛇形则相反：成对的圆弧蛇形必须是同心弧（半径差 = 间距），才能被当作耦合，否则整段算非耦合，要吃预算。
5. 不依赖 `tuning_pattern` 生成器、Python 调整接口和任何界面动作。
