# 调研：KiCad 的长度规则在命令行 DRC 里是否生效，以及现成的等长工具

票：[#14](https://github.com/immorcoding/PCB/issues/14)（地图 [#1](https://github.com/immorcoding/PCB/issues/1)，约定来源 [#12](https://github.com/immorcoding/PCB/issues/12)）。
日期 2026-11-16。KiCad 10.0.8（`D:\KiCad\bin\`），Windows 11。分支 `research/kicad-length-rules`，只存档不合并。

证据标记（全篇统一）：

- **【实验】** 我在自己建的临时小板上用 `kicad-cli` / pcbnew Python 实际跑出来的。脚本和结果都在 `docs/research/kicad-length-rules/` 下。
- **【源码】** 读 KiCad 10.0.8 标签的源码（gitlab 的 `10.0.8` tag）得到的，没有跑。
- **【手册】** 读 docs.kicad.org 10.0 的 PCB Editor 手册得到的，没有跑。
- **【README】** 只读了第三方项目的说明文件，没有跑。
- **【未验证】** 没有证据，或只有推断。

实验结果和手册/源码注释不一致的地方以实验为准，并写在对应小节里。

---

## 0. 紧凑结论

| # | 问题 | 一句话答案 | 对这块板的建议 |
|---|---|---|---|
| 1a | `length` 约束在命令行 DRC 报不报 | **报**【实验】。每根网络一个总长：走线（直线和圆弧都按几何算，和解析值差 < 0.0001 mm）+ 过孔穿过的层间高度（只算信号实际用到的两层之间）+ 焊盘的 pad-to-die，端点取焊盘中心；整根网络的所有分支都加进去。 | 约定 #12 的口径（焊盘到焊盘 + 过孔实际穿过的层间高度、不计封装内长度）**就是 KiCad 的默认算法**，前提三条：叠层在板文件里填了真值、`use_height_for_length_calcs` 为 true、封装的 pad-to-die 留 0。 |
| 1b | 带过孔 / 圆弧算得对不对 | 对【实验】。过孔高度按板文件的叠层算；没有叠层块时用 KiCad 自己生成的默认叠层，数不对（本实验里每根网络差 0.07–0.37 mm）；`use_height_for_length_calcs` 关掉后过孔长度为 0，而且 `via_count` 约束**静默失效**。 | 六层板把 JLC06161H-3313E 的叠层填进 Physical Stackup；DRC 前核对一次。 |
| 1c | `skew` 怎么用 | 一条规则命中的所有网络是一组，**基准是组内最长的那根**，每根与它的差（绝对值）不得超过 `max`【实验+源码】。 | **表达不了** "一组线对 SDCLK ±2.5 mm" 和 "时钟不长于数据线"（基准不能指定，窗口是单边的 [最长 − max, 最长]）。改用生成式的 `length (min)(opt)(max)` 窗口规则：窗口数字由脚本按 SDCLK 实测长度算好写进 `.kicad_dru`（每组一条规则，不是每根一条）【实验】。 |
| 1d | 60 mm 上限、过孔数 | `length (max 60mm)` 和 `via_count (max 2)` 都能直接写，一条规则管整个网络类【实验】。 | 照写。 |
| 1e | 串联电阻把网络分成两段 | DRC 逐网络量，**不跨电阻**；`fromTo` 也只在同一网络内取路径【实验】。 | SDCLK 的总长 = MCU 侧一段 + SDRAM 侧一段，由脚本相加后换算每个窗口，不要指望 DRC 报总长。 |
| 2a | 按网络类还是按网络名 | **两种在命令行都生效**，结果一样：`A.NetClass == 'X'`、`A.hasNetclass('X')`、`A.NetName == '/SDRAM_D*'`（含通配）【实验】。网络类靠 `.kicad_pro` 的 `netclass_patterns`。网络名要带层次前缀 `/`。 | 按网络类写（名单集中在 `.kicad_pro`）；通配留给临时检查。 |
| 2b | 写错会不会静默 | 分两类【实验】。**整个文件被静默跳过**：括号缺失、约束名拼错、数值不带单位、条件里单个 `=`、规则行尾 `#` 注释。**文件照常加载，只是这条规则什么都匹配不到**：网络类名/网络名/规则区名拼错、函数名或属性名拼错、网络名漏了开头的 `/`。两类都不报任何信息，退出码 0。 | 现有金丝雀（`corner_angle`）能抓第一类（同一个文件里的所有规则一起失效），**抓不住第二类**。不必为长度单独加一条金丝雀；要加的是"每条长度/偏差规则至少匹配到一根网络"的检查，见 §3.4 的 `length_table.py`。 |
| 3 | KiCad 自带的蛇形工具能否脚本调用 | **不能脱离界面**。pcbnew Python：`board.Generators()` 返回不透明的 SwigPyObject，没有 `PCB_TUNING_PATTERN` 类【实验】。IPC 接口：proto 里没有调整图形的类型，只有 `RunAction`（按名字触发界面动作，如 `pcbnew.Generator.regenerateAllTuning`），需要界面开着且在设置里打开 API 服务（这台机器上是关的）【源码，未执行】。`kicad-cli pcb` 只有 drc/export/import/render/upgrade【实验】。 | 蛇形继续用脚本画：KiCad 自己的调整器出来的也是"线段 + 90° 圆弧"（`rounded yes`），形状同类。脚本画的是**普通走线**。 |
| 3b | 脚本写 `(generated … tuning_pattern)` 行不行 | 文件层面行【实验】：pcbnew 读得进、存得回、`kicad-cli pcb upgrade` 保留、DRC 长度不变；类型名写错则**整块板读不进**。界面里能否把它认作可编辑的调整图形、能否"更新全部调整图形"重生成：**没验证**。`kicad-cli` 没有重生成命令。 | 先不包这层。普通走线用户也能手动拖；要让用户接着拉，另在直线段上用界面的调整工具加图形（手册说同一根线上可放多个）【手册】。 |
| 4 | 现成工具 | 见 §5。**没有**一个能"在命令行把圆弧蛇形加到已布好的线上"的现成开源工具。最接近的：KiCad 自己的 PNS 调整器（只能在界面里，或用第三方 `pns_drive` 在从源码构建的 KiCad 里无界面跑）；KiCadRoutingTools 的长度匹配（MIT，命令行，**45° 切角不是圆弧**，绑在布线步骤里）。 | 自己写圆弧蛇形（本调研的 pcbnew 脚本已证明线段 + `PCB_ARC` 的长度被 DRC 精确计入）。 |
| 5 | 线宽按规则区切换 | DRC 能按规则区约束线宽【实验】：`intersectsArea`（含 `insideArea` 别名）= 线的任何部分碰到区就算区内，**端点落在区边上的线也算**；`enclosedByArea` = 整条线（含线宽）都在区内。DRC 逐段判，不判"在边界上变宽"本身。路径上换线宽要在**区边外至少半个线宽**处进行。布线器能否自动换线宽：手册说 `opt` 值被交互布线器采用，**没验证**。 | 区内用三条规则（§6.3），区外第一个拐点前换宽。 |

---

## 1. 临时小板和脚本

全部在 `docs/research/kicad-length-rules/`：

```
lentest/        长度实验板（6 层，显式叠层）
  make_board.py       用 pcbnew Python 生成 lentest.kicad_pcb/.kicad_pro/expected.json
  expected.json       每根网络按几何算出的解析长度（走线部分）
  rules/*.kicad_dru   每个实验一个规则文件
  results/*.rpt|txt   DRC 原始报告和汇总
  run_drc.py parse_report.py summarize.py compare_e01.py run_broken.py run_variants.py run_skew.py
  length_table.py     原型：用 DRC 当量具，从 .kicad_dru 生成长度表并检出"空规则"
areatest/       规则区线宽实验板（4 层，一个叫 bga 的规则区）
tuning/         蛇形/调整图形实验（make_generated.py 等，results.txt）
```

`lentest` 板（全部网络的走线长度事先已知）：J1、J2 两个封装各 16 个焊盘，相距 50 mm；每行一根网络：

| 网络 | 内容 | 走线解析长度 (mm) |
|---|---|---|
| `/SDRAM_D0` | 直线，F.Cu | 50.0000 |
| `/SDRAM_D1` | 45° 绕行 | 51.6569 |
| `/SDRAM_D2` | 两个半圆弧（r 1.5）+ 直线 | 53.4248 |
| `/SDRAM_D3` | F.Cu → 通孔 → B.Cu → 通孔 → F.Cu | 50.0000 + 2 个 F–B 过孔 |
| `/SDRAM_D4` | 中段在 In2.Cu | 50.0000 + 2 个 F–In2 |
| `/SDRAM_D5` | 中段在 In4.Cu | 50.0000 + 2 个 F–In4 |
| `/SDRAM_D6` | 中段在 In1.Cu | 50.0000 + 2 个 F–In1 |
| `/SDRAM_D7` | 故意超长 | 70.0000 |
| `/SDRAM_D8` | 直线，J1 焊盘 pad-to-die 3.0、J2 焊盘 1.5 | 50.0000 + 4.5 |
| `/SDCLK` | 45° 小绕行 | 50.8284 |
| `/SDRAM_D9` | 项目约定的圆弧蛇形（r 0.25、摆幅 0.5、5 个凸起，29 段线+弧） | 52.8540 |
| `/SDRAM_D10` | r 0.25、带 1.0 直腿的蛇形，3 个凸起 | 57.7124 |
| `/CLK2_A`、`/CLK2_B` | 串联电阻 R1 前后两段 | 3.2000、45.2000 |
| `/QSPI_CLK`、`/QSPI_IO0` | 另一个网络类 | 50.0000、51.6569 |
| `/TBR` | 主路径 50 + 一根 5 mm 悬空短桩 | 55.0000（整网）/ 50.0000（路径） |
| `/ARC_30deg_r0.25` 等 5 根 | 孤立的弧：30°/90°/225°/340°（r 0.25–2）和 5°（r 100） | 见 §2.1 |

网络类（`.kicad_pro` 的 `netclass_patterns`）：`SDRAM` = `/SDRAM_*`、`/SDCLK*`、`/CLK2_*`；`QSPI` = `/QSPI_*`。叠层写在 `.kicad_pcb` 的 `(setup (stackup …))`：F-In1 0.1、In1-In2 0.4、In2-In3 0.2、In3-In4 0.5、In4-B 0.1，铜 0.035/0.0152——故意取互不相同的厚度，让每种过孔高度都能区分。

运行（工作目录 `docs/research/kicad-length-rules/lentest`）：

```
D:\KiCad\bin\python.exe -I make_board.py . ..\..\..\..\templates\common\common.kicad_pro
D:\KiCad\bin\python.exe -I run_drc.py rules\e01_probe_all_lengths.kicad_dru
D:\KiCad\bin\python.exe -I compare_e01.py
```

`run_drc.py` 把板、工程、一个规则文件拷到临时目录，跑 `kicad-cli pcb drc --severity-all --format report --units mm`，不会改动 `lentest/` 里的板。

---

## 2. 问题 1：`length` / `skew` 在命令行 DRC 里的表现

### 2.1 报的长度是什么（E01，【实验】）

规则（`rules/e01_probe_all_lengths.kicad_dru`）：

```
(version 1)
(rule "probe_all_lengths"
  (constraint length (max 1mm)))
```

`max 1mm` 被所有真实网络超过，所以每根网络都被报一次，"实际"就是 KiCad 量到的总长。报告行（本机界面语言为中文，说明文字是翻译过的，所以脚本只认 `[length_out_of_range]` 和数字）：

```
[length_out_of_range]: 走线长度超出范围 (约束条件 规则 'probe_all_lengths' 中, 最大长度 1.0000 mm; 实际 52.8616 mm)
    Rule: probe_all_lengths; error
    @(10.0000 mm, 12.0000 mm): Track [/SDRAM_D3] on F.Cu, length 10.0000 mm
```

`compare_e01.py` 的输出（`results/e01_compare.txt`）：

| 网络 | 走线解析值 | DRC 实际 | 差（过孔 / pad-to-die） |
|---|---|---|---|
| `/SDRAM_D0` 直线 | 50.0000 | 50.0000 | 0 |
| `/SDRAM_D1` 45° 绕行 | 51.6569 | 51.6569 | 0 |
| `/SDRAM_D2` 半圆弧 | 53.4248 | 53.4248 | 0 |
| `/SDRAM_D3` 两个 F–B 过孔 | 50.0000 | 52.8616 | +2.8616（每个 1.4308） |
| `/SDRAM_D4` F–In2 | 50.0000 | 51.1156 | +1.1156（每个 0.5578） |
| `/SDRAM_D5` F–In4 | 50.0000 | 52.5764 | +2.5764（每个 1.2882） |
| `/SDRAM_D6` F–In1 | 50.0000 | 50.2852 | +0.2852（每个 0.1426） |
| `/SDRAM_D8` pad-to-die 3.0 + 1.5 | 50.0000 | 54.5000 | +4.5 |
| `/SDRAM_D9` 圆弧蛇形 | 52.8540 | 52.8540 | 0 |
| `/SDRAM_D10` 圆弧蛇形（带直腿） | 57.7124 | 57.7124 | 0 |
| `/ARC_30deg_r0.25` | 2.1309 | 2.1309 | 0 |
| `/ARC_90deg_r0.25` | 2.3927 | 2.3927 | 0 |
| `/ARC_225deg_r2` | 9.8540 | 9.8540 | 0 |
| `/ARC_340deg_r1` | 7.9341 | 7.9341 | 0 |
| `/ARC_5deg_r100` | 10.7266 | 10.7266 | 0 |
| `/TBR`（带 5 mm 桩） | 55.0000 | 55.0000 | 整网所有分支相加 |

读法：

- **圆弧**：所有角度和半径都和解析值一致到报告的 4 位小数。源码文件头那句 `Todo: arc support` 已过时【源码+实验】。
- **过孔**：只算信号实际用到的两层之间。D4（走 In2）每个过孔 0.5578，D3（走 B.Cu）每个 1.4308；这符合 #12 的"过孔实际穿过的层间高度"。高度的算法在 `BOARD_STACKUP::GetLayerDistance`【源码】：从起始铜层数到终止铜层，F.Cu / B.Cu 按整层厚度，中间的内层铜按整层，作为端点的内层只算一半。用本板叠层核对：F→In1 = 0.035 + 0.1 + 0.0152/2 = 0.1426 ✓；F→In2 = 0.035 + 0.1 + 0.0152 + 0.4 + 0.0076 = 0.5578 ✓。
- **pad-to-die**：默认**计入**（D8 多出 4.5）。H7 的 BGA 和 SDRAM 封装来自 KiCad 库，pad-to-die 为 0，不用管；谁给封装焊盘填了"焊盘到芯片长度"，DRC 长度就会多出这一项，与 #12 "不计封装内长度" 的口径相反。
- **端点**：走线端点在焊盘中心时，不扣焊盘内的那段（D0 正好 50.0000）。源码里 `optimiseTracesInPads` 把进入焊盘的线裁成"焊盘中心 → 出焊盘点 → 其余"，长度不变，只会把焊盘内绕路的线拉直【源码】。焊盘内绕弯的情况没试【未验证】。
- **整网**：`/TBR` 的 5 mm 悬空短桩被加进去（55.0000）。要只量焊盘到焊盘的路径，用 `A.fromTo('J1-16','J2-16')`：得到 50.0000（`results/e06_e10_skew_order_fromto.txt` 的 e10e）。手册说调整工具只支持点对点网络【手册】。

### 2.2 叠层和"含过孔高度"开关（E04/E05，【实验】）

`run_variants.py`（`results/e04_e05_variants.txt`）：同一条探针规则跑三个版本：

| 网络 | A 显式叠层、开关开 | B 板文件里删掉叠层块 | C 开关关（`use_height_for_length_calcs=false`） |
|---|---|---|---|
| `/SDRAM_D3`（2 个 F–B） | 52.8616 | 53.1600 | 50.0000 |
| `/SDRAM_D4`（2 个 F–In2） | 51.1156 | 51.2710 | 50.0000 |
| `/SDRAM_D5`（2 个 F–In4） | 52.5764 | 52.5070 | 50.0000 |
| `/SDRAM_D6`（2 个 F–In1） | 50.2852 | 50.6530 | 50.0000 |
| `/SDRAM_D8`（pad-to-die） | 54.5000 | 54.5000 | 54.5000 |

- B：没有叠层块时 KiCad 用 `BuildDefaultStackupList` 生成的默认叠层【源码】，过孔高度和真实叠层不同，每根网络差 0.07–0.37 mm（D6 最大）。**要在 Physical Stackup 里填板厂的真值。**
- C：开关关掉后过孔长度为 0，pad-to-die 仍计入。
- `via_count (max 1)` 规则：A 里正确报出 D3–D6；C 里**一根都不报**（源码里过孔数只在开关开着时累计【源码】，实验证实）。这是静默失效。

### 2.3 `skew` 怎么用（E03、E06、E08，【实验+源码】）

源码 `drc_test_provider_matched_length.cpp`【源码】的逻辑：一条规则命中的所有网络是一组；每根网络的"长度"同上；基准是组内最长的那根；每根的 `skew = 自己 − 最长`，`abs(skew) > max` 报错；`min` 不用在基准本身上；`opt` 是调整工具的目标值。

E03（`rules/e03_skew_by_netclass.kicad_dru`）：

```
(rule "sdram_skew_class"
  (condition "A.NetClass == 'SDRAM' && A.NetName != '/SDRAM_D7'")
  (constraint skew (max 2.5mm)))
```

报告（节选）：基准是 `/SDRAM_D10`（57.7124），其余每根都报，例如 `/SDRAM_D2 skew -4.2876 (limit 2.5)`，说明文字里带"目标网络长度 57.7124 (网络名 /SDRAM_D10)"。

**能表达什么、不能表达什么**：

| 要求 | `skew` 能否表达 | 说明 |
|---|---|---|
| 一组线两两相差不超过 W | 能 | `skew (max W)`，组由网络类、网络名通配或 `fromTo` 定义 |
| 一组线对 **SDCLK** ±2.5 mm | **不能** | 基准是组内最长的，不是 SDCLK。E06：组 {SDCLK 50.828, D0 50.000, D2 53.425}，`skew (max 2.5)` 报的是 SDCLK（−2.596）和 D0（−3.425），而真正对 SDCLK ±2.5 只该报 D2（+2.597） |
| 时钟不长于数据线 | **不能** | 基准永远是最长的，方向反了 |
| 每根不超过 60 mm | 不用 skew，用 `length (max 60mm)`（E02） | 一条规则管整个网络类 |
| 过孔数 ≤ 2 | 用 `via_count (max 2)` | 开关要开着 |

**替代写法：窗口规则（E07，【实验】）**。窗口对所有成员相同，所以**每组一条规则**，只有数字要由脚本生成：

```
(rule "sdram_data_window"
  (condition "A.NetName == '/SDRAM_D*'")
  (constraint length (min 48.3284mm) (opt 50.8284mm) (max 53.3284mm)))
```

数字 = SDCLK 实测长度 ± 2.5（SDCLK 为 50.8284）。结果（`results/e06_e10_skew_order_fromto.txt` 的 e07c）：D2（53.4248）、D7（70）、D8（54.5）、D10（57.7124）被报，D0（50.000）不报；这些就是预期的越界网络。`opt` 同时是 KiCad 调整工具在界面里的默认目标长度【手册】。"不短于时钟"同理写 `(min <SDCLK 长度>)`（e07b：D0 50.000、D6 50.285 被报，D4 51.116 不报）。

代价：窗口数字是从当前走线算出来的，SDCLK 变了就要重生成这一段规则（`length_table.py` 的探针做法可以每次构建重量一次）。

### 2.4 规则顺序、`length` 与 `skew` 并存、`fromTo`（【实验】）

- **后面的规则优先**（E09）：类规则 `max 60` 在前、`/SDRAM_D7` 例外 `max 75` 在后时，D7（70）不报；两条顺序对调后 D7 被报。这和手册"从最后一条往前判，命中即停"一致。
- **`length` 只和 `length` 规则竞争，`skew` 只和 `skew` 规则竞争**（E08）：同一批网络上一条 `length (max 52)`、一条 `skew (max 7)` 同时生效，各报各的。
- **`fromTo`**（E10）：`A.fromTo('J1-4','J2-4')` 取该路径上的走线、过孔、焊盘，D3 报 52.8616（含过孔）。`fromTo('J1-13','J2-13')` 跨串联电阻 R1 **没有命中任何东西**；分别写 `fromTo('J1-13','R1-1')` 和 `fromTo('R1-2','J2-13')` 才分别得到 `/CLK2_A` 3.2000 和 `/CLK2_B` 45.2000。手册的串阻例子也是这么写的【手册】。

---

## 3. 问题 2：规则怎么写才生效、写错会怎样

### 3.1 按网络类 / 按网络名（E02，【实验】）

三条规则文件，条件分别是 `A.NetClass == 'SDRAM'`、`A.hasNetclass('SDRAM')`、`A.NetName == '/SDRAM_D*'`，约束都是 `length (max 60mm)`。三次都只报 `/SDRAM_D7`（`nums=[60.0, 70.0]`，见 `results/e02_e03_summary.txt`）。

- 网络类分配取自 `.kicad_pro` 的 `net_settings.netclass_patterns`，命令行里照常生效。
- `A.NetClass` 是网络类列表（带 `Default`），`==` 对列表里任意一项成立；`hasNetclass()` 更直接。
- 属性名不区分大小写（`A.netclass` 也行，b10）。
- 网络名包含层次路径前缀：顶层网络是 `/SDRAM_D0`，写 `'SDRAM_D*'` 匹配不到（b02）。

### 3.2 写错时的表现（E10，`run_broken.py`，【实验】）

每个文件 = 一条必然触发的金丝雀规则（`/SDRAM_D7` 超过 60 mm）+ 一条有缺陷的规则。`results/e10_broken_rules.txt`：

| 缺陷 | 文件是否加载 | 缺陷规则是否起作用 | 控制台 |
|---|---|---|---|
| 无缺陷（对照） | 是 | 是（7 根） | 只有违规数 |
| 网络类名拼错 `'SDRAMM'` | 是 | **否，静默** | 无信息 |
| 网络名漏了开头的 `/` | 是 | **否，静默** | 无信息 |
| 函数名拼错 `hasNetclas()` | 是 | **否，静默** | 无信息 |
| 属性名拼错 `NetClas` | 是 | **否，静默** | 无信息 |
| 括号缺一个 | **否，整个文件被跳过** | — | 无信息，退出码 0 |
| 约束名拼错 `lenght` | **否，整个文件被跳过** | — | 无信息 |
| 数值不带单位 `(max 52)` | **否，整个文件被跳过** | — | 无信息 |
| 条件里单个 `=` | **否，整个文件被跳过** | — | 无信息 |
| 规则行尾 `# 注释` | **否，整个文件被跳过**（已知陷阱的再现） | — | 无信息 |
| `(max 52 mm)`（单位前有空格） | 是 | 是（等同 `52mm`） | — |
| 属性名小写 | 是 | 是 | — |

（"加载"的判据：金丝雀或缺陷规则至少有一个报出来。缺陷规则也命中 D7 时，它按"后面的优先"盖掉金丝雀，所以对照、空格、小写三行金丝雀列是 False，但缺陷规则报了 7 根，说明文件已加载。）

手册说规则错误"会让 DRC 不能运行"【手册】，那是界面；**命令行里是静默跳过整个文件**，DRC 照常出报告、退出码 0。

### 3.3 金丝雀要不要加一条长度规则

- **不需要为"文件有没有加载"单加长度金丝雀**：第一类失效（整个文件被跳过）会让 `corner_angle` 一起消失，现有的 `scripts/dru_canary.py` 已能抓住【实验：上表五行都属此类】。
- **需要补的是第二类**（规则加载了但什么都不匹配）：现有金丝雀抓不住。做法见下节。
- 模板 `templates/common/common.kicad_dru` 里已有一条 `usb3_skew`（`A.NetClass == 'USB3'`），金丝雀没有证明它会触发，当前板上也没有 USB3 网络类；H7 板不用它，别当成验证过的规则。

### 3.4 原型：用 DRC 当量具生成长度表并检出"空规则"（`lentest/length_table.py`，【实验】）

做法：把 `.kicad_dru` 里每条带 `length` 的规则复制成同名、同条件、约束为 `length (max 0.001mm)` 的探针规则（`skew` 规则同理换成 `skew (max 0.0001mm)`），跑一次 `kicad-cli`，按报告里的规则名分组，得到"每条规则命中了哪些网络、各多长"。命中 0 根的规则打印 `EMPTY`。`length` 和 `skew` 分两次跑，因为二者各自竞争（§2.4）。

`results/e11_length_table.txt`（规则文件 `rules/e11_for_length_table.kicad_dru`，里面故意有一条 `'SDRAMM'` 拼错的规则）：

```
[length] rule 'sdram_len': 13 nets, longest 70.0000, shortest 3.2000 ...
[length] rule 'typo_class': EMPTY -- matched no routed net (typo in the condition? net not routed?)
[length] rule 'clk_path': 1 nets, longest 50.8284, shortest 50.8284 ...
[skew]   rule 'sdram_skew': 13 members; reference (longest) length 57.7124; others: ...
```

这同时就是 RTE-2 要的"长度表每次构建输出"：数字是 DRC 自己量的，和 DRC 判定一致。

---

## 4. 问题 3：KiCad 自带的长度调整能否脚本调用

### 4.1 pcbnew Python（【实验】，`tuning/probe_generators.py`，`tuning/results.txt`）

在 KiCad 自己的 QA 测试板（含一个 tuning pattern）上：

```
Generators() -> tuple of length 1
element type: SwigPyObject      # 没有任何方法：public attributes: acquire/append/disown/next/own
classes in pcbnew whose name contains GENERATOR / TUNING / MEANDER: DEFAULT_*_MEANDER_SPACING, GENERATORS
```

- 能列出板上的调整图形，但是**不透明对象，调不了任何方法**，也没有创建用的类。
- `board.GetDesignSettings().m_SingleTrackMeanderSettings` 能取到对象，但没有可访问的属性。
- `board.GetLengthCalculation()` 同样是不透明对象。pcbnew 里能直接用的只有逐段的 `track.GetLength()`（只含几何，不含过孔和 pad-to-die）。
- `kicad-cli pcb --help`：子命令只有 `drc, export, import, render, upgrade`，**没有"重生成调整图形"**。

### 4.2 IPC 接口 / kipy（【源码】，未执行）

- `board_types.proto`（10.0.8）：有 Track、Arc、Via、Zone、Group 等，**没有 generator / tuning pattern 类型**；用 kipy 能建线段和圆弧，建不了调整图形。
- `editor_commands.proto` 有 `RunAction { string action }`，注释写明 "TOOL_ACTIONs are specifically *not* an API"。调整相关的动作名（`pcb_actions.cpp`）：`pcbnew.LengthTuner.TuneSingleTrack`（要鼠标交互）、`pcbnew.Generator.regenerateAllTuning`（"尝试在范围内重新调整现有调整图形"）、`pcbnew.Generator.regenerateAll`。
- 前提：KiCad 界面开着、板子在 PCB 编辑器里打开、"启用 KiCad API"勾选。本机 `kicad_common.json` 里 `api.enable_server` 是 `false`。我没有改用户配置，**没有执行任何 IPC 调用**。
- `pip install kicad-python` 在 KiCad 自带 Python 里没装【未验证它能否装、能否连上】。

### 4.3 脚本画的蛇形在 KiCad 里是什么

- 默认是**普通线段 + `PCB_ARC`**，没有"调整图形"身份。长度被 DRC 精确计入（D9、D10，§2.1）。
- KiCad 自己的调整器出来的内容也是线段 + 弧：QA 样板板上共 25 段线 + 24 段弧，其中 47 个是这个调整图形的成员，`(rounded yes)`、`(corner_radius_percent 100)`【样板文件】；源码里圆角样式 `MEANDER_STYLE_ROUND = 1` 是"90° 圆弧"，`MEANDER_STYLE_CHAMFER` 才是 45° 切角【源码】。项目模板 `templates/common/common.kicad_pro` 的 `tuning_pattern_settings.single_track_defaults` 已是 `corner_style: 1`（圆角）、`corner_radius_percentage: 100`、`spacing 0.6`、`max_amplitude 1.0`，用户在界面里拉出来的就是圆弧，和 RTE-7 一致。

### 4.4 板文件里的 tuning pattern 长什么样（来源：KiCad 10.0.8 重新保存的结果，`tuning/make_generated.py`）

```
(generated
    (uuid "7876d1fc-caed-4faa-9074-b9fb2b247d14")
    (type tuning_pattern)
    (name "Tuning Pattern")
    (layer "F.Cu")
    (base_line (pts (xy 5 54) (xy 15.5 54)))        # 调整前的直线
    (corner_radius_percent 100)
    (end (xy 15.5 54))
    (initial_side "left")
    (is_time_domain no)
    (last_diff_pair_gap 0.18)
    (last_netname "/SDRAM_D9")
    (last_status "too_short")
    (last_track_width 0.1)
    (last_tuning_length 0)
    (max_amplitude 0.5)
    (min_amplitude 0.2)
    (min_spacing 0.5)
    (origin (xy 5 54))
    (override_custom_rules no)
    (rounded yes)
    (single_sided no)
    (target_delay …) (target_delay_max …) (target_delay_min …)
    (target_length 52.854) (target_length_max 52.954) (target_length_min 52.754)
    (target_skew 0) (target_skew_max 0.1) (target_skew_min -0.1)
    (tuning_mode "single")
    (members "<线段/弧的 uuid>" "…" …)             # 构成图形的 track/arc 的 uuid
)
```

（实际文件是多行缩进；上面为阅读压缩。）它是板文件顶层的一个块，`members` 引用板上已有线段和弧的 uuid，块本身不含几何。字段集合来自 `PCB_TUNING_PATTERN::GetProperties`【源码】；7.99 时代的样板（`(id …)` 不加引号、`last_tuning` 字符串）10.0.8 也读。

### 4.4.1 脚本直接写这个块（【实验】，`tuning/make_generated.py`、`check_generated_drc.py`、`check_unknown_type.py`，结果 `tuning/results.txt`）

在 `lentest.kicad_pcb` 上，用 pcbnew 读出 `/SDRAM_D9` 蛇形那 29 个对象的 uuid，把上面的块拼到文件末尾：

| 检查 | 结果 |
|---|---|
| `pcbnew.LoadBoard` | 读得进，`Generators()` 长度 1 |
| `pcbnew.SaveBoard` 再存 | 块保留，members 仍是 29 个 |
| `kicad-cli pcb upgrade` | 块保留，members 29 个 |
| `kicad-cli pcb drc` | `/SDRAM_D9` 长度 52.854 不变，违规总数不变 |
| 对照：把 `tuning_pattern` 改成 `bogus_pattern` | `pcbnew.LoadBoard` **整块板读不进**（返回 None） |

所以写这个块在**文件层面可行**；但对照说明块写错会让整个板子打不开，这块一旦采用要用 `kicad-cli pcb upgrade` / DRC 做读入检查。

**没验证的部分**：这个块在界面里是否被认作可选中、可拖拽编辑的调整图形；"更新全部调整图形"能否据 `base_line` 和成员重新生成。源码里 `PCB_TUNING_PATTERN::Update()` 需要界面里的 `GENERATOR_TOOL` 和 PNS 布线器【源码】，命令行没有入口，所以"再让 `kicad-cli` 重新生成"**不可行**。

---

## 5. 问题 4：现成工具

调查方式：GitHub 搜索（`meander`、`length matching`、`serpentine`、`tuning pattern`）+ 本机 `Tools/KiCadRoutingTools/` + 读 README/源码。第三方代码下载到仓库外的独立目录，没有提交，没有执行。许可证取自 GitHub 的 SPDX 字段；本机 KiCadRoutingTools 另读了 LICENSE 文件头（MIT），`PabloSoage` 仓库的 README 自述 GPL-3.0-or-later，其余没读 LICENSE 全文。

| 工具 | 许可证 | 做什么 | 圆弧拐角 | 脱离界面 | 验证程度 |
|---|---|---|---|---|---|
| KiCad 自带调整器（`pcbnew/router/pns_meander*.cpp`） | GPL-3.0-or-later | 单线/差分长度调整、延迟调整 | **是**（默认 90° 圆弧，可选 45° 切角） | 否（界面） | 【手册+源码+QA 样板】 |
| `KiCadRoutingTools`（本机 `Tools/KiCadRoutingTools/`，drandyhaas） | MIT | `route.py --length-match-group`：布线后给短的网络加"trombone"蛇形；DDR 自动分组；算过孔桶长度、pad-to-die；读 `.kicad_dru` 的长度窗口；`check_drc.py` 独立核对长度规则 | **否**，45° 切角的矩形凸起（`docs/length-matching.md`、`length_matching.py` 里的 `chamfer`） | 是（命令行） | 只读了文档和代码，**没运行**。它是布线步骤的一部分，不是"给已布好的线加蛇形"的独立工具：文档说已布好的成员要加 `--force-reroute` 重走 |
| `PabloSoage/kicad-pcb-routing-tools`（2026-11，面向 KiCad 10） | GPL-3.0-or-later | ① `layout/meander.py`：给一段直线加矩形凸起，纯文本改板文件（不 import pcbnew），带间距检查（shapely）；② `pns_drive`：把 KiCad 自己的 PNS 路由器链接进一个小程序，脚本驱动，含 `tune single\|dp\|skew X1 Y1 X2 Y2 LAYER TARGET` | ① **否**（矩形）；② 用 KiCad 自己的蛇形放置器，圆/切角取决于 `MEANDER_SETTINGS`，README 没说默认值【未验证】 | ① 是；② 是，但要**自己从 KiCad 10.0.8 源码树构建**（README 给的是 Linux/apptainer 容器流程，没有 Windows 构建说明） | 只读 README 和 `pns_drive.cpp` 的命令列表，**没构建、没运行** |
| `leZfromFr/kicad-python-scripts` 的 `length-matching` | MIT | 演示：用 pcbnew Python 画"线段 + `PCB_ARC`"的圆角蛇形，二分法求环高度使两根线等长 | **是** | 是（pcbnew Python） | 只读 README；演示脚本，不是通用工具。我自己用同样做法画了圆弧蛇形并验证长度（§2.1） |
| `parisxmas/fastroute`（Freerouting 的 Rust 移植） | GPL-3.0 | 自动布线器，`--tune` 布线后用蛇形匹配长度，读 `.kicad_dru` 的长度/skew 规则 | 未说明【未验证】 | 是 | 只读 README |
| `mithro/kicad-length-matching-checks` | BSD-3-Clause（2016 年，旧） | 检查长度匹配（网络类加 `_LM` 后缀） | — | pcbnew Python | 只看搜索结果摘要 |
| `esden/KiBus` | 无许可证 | 总线长度匹配监视 + 愿望清单（含"串阻两侧网络合并"） | — | — | README；WIP，已迁 Codeberg |
| `MitjaNemec/Kicad_action_plugins`（含 `length_stats`） | 无许可证文件 | 统计选中网络的长度 | — | 界面插件 | 仓库目录列表 |
| `AleksaBjelogrlic/kicad_delay_tuner` | MIT | 用 IPC API 取长度、按延迟算等效长度、写规则值给 KiCad 的调整器用 | — | 否（要界面开着、API 开着） | README |
| `qfreiman/flytools` | GPL-3.0 | 延迟计算 / 电子表格 | — | 部分 | README |
| `tiandahuang/kicad-serpentine` | 无许可证 | 柔性板蛇形走线生成（不是等长） | 是 | 界面插件 | README |

其余：KiCad 论坛上有一个 "Length Matching Plugin"（约四年前的 beta），GitLab 上 #18118、#18979 是对 KiCad 本体的需求单（内容只看到摘要）；`OneKiwiTech/kicad-length-matching` 在 GitHub 上查不到（404）。

PROC-5 的结论：**没有**现成的"命令行、圆弧、加在已布好线上"的蛇形工具，所以蛇形脚本自己写（本调研的 pcbnew 画法已验证长度被 DRC 精确计入）；"用 DRC 当量具生成长度表"这件事没找到现成的，`length_table.py` 是本调研写的约 100 行原型。KiCadRoutingTools 的 45° 切角和 RTE-7 要的圆弧不符，只能当对照和长度核对用，不能直接出蛇形。

---

## 6. 问题 5：线宽在规则区内外切换

### 6.1 现成做法

- **手册自带的例子**【手册】：`BGA neckdown` 用 `A.intersectsCourtyard('U3')` 加 `track_width (min 0.2mm) (opt 0.25mm)` 和 `clearance`，思路和"规则区内换线宽"相同。`track_width` 的 `opt` "被交互布线器当作该网络的默认线宽"。
- `A.intersectsArea('<规则区名>')` 等函数按**规则区或铜皮的名字**取区【手册】；本实验里规则区是 `ZONE` 加 `SetIsRuleArea(True)` + `SetZoneName("bga")`，名字支持通配（q07）。
- 没找到现成的"脚本里按规则区自动换线宽"的开源做法。KiCadRoutingTools 有"电源网络在细间距焊盘处自动缩线宽"（README），不是按规则区。`pns_drive` 的 `size 0 0` 表示"按规则取宽"【README】。**布线器（界面或无界面）实际会不会随规则区换 `opt` 线宽，没验证。**

### 6.2 `intersectsArea` / `insideArea` / `enclosedByArea` 对跨界线段的含义（`areatest`，【实验】）

板：规则区 `bga` = x 0..20、y 0..20 的矩形；线段 a1–a9（线宽 0.09 或 0.1016，区内/区外/跨边/边上换宽）和圆弧 b1–b5；`.kicad_pro` 沿用模板（板级最小线宽 0.1016）。每条规则文件和报告在 `areatest/rules/`、`areatest/results/`，汇总 `results/q_summary.txt`。通用规则 `signal_min`：`A.Type == 'Track'` → `track_width (min 0.1016mm)`。

| 规则 | 结论 |
|---|---|
| q01 只有 `signal_min` | 所有 0.09 的线（区内也一样）都被报；圆弧也被 `A.Type == 'Track'` 匹配 |
| q02 再加 `A.intersectsArea('bga')` → `min 0.09` | 区内、跨边的 0.09 线通过（a1、a5、a7 内段、a8、a9、b3、b5）；区外 0.09（a3）仍被报；区内 0.05 被新规则报（b1、b4）。圆弧也被这条规则命中 |
| q03 `intersectsArea` → `min 0.09 max 0.09` | **区内的 0.1016 被报**（a2）；**跨边的 0.1016 被报**（a6）；**在边上换宽的 a7：从边上开始的 0.1016 段被报**，因为线端的圆头伸进区里半个线宽 |
| q04 `insideArea` | 和 q03 完全一致（手册标注已弃用，等同 `intersectsArea`） |
| q05 `enclosedByArea` → `min 0.09 max 0.09` | 只有整条线（含线宽）都在区内才命中。跨边的、**端点正好在边上的**内段（a7 的 0.09 段）、a8/a9 的内段都不命中，落回通用规则 `signal_min`，被报"0.09 < 0.1016" |
| q06 三条规则：`!enclosed && intersects` → `min 0.09`；`enclosed` → `min 0.09 max 0.09`；通用规则 | 全部符合预期：区内 0.1016 被报，跨边和边上换宽的段都通过，区外 0.09 被报 |
| q07 `intersectsArea('bg*')` | 通配符生效，结果同 q03 |
| q08 区名拼错 `'bgaa'` | **静默**：没有报错，所有线落回通用规则（0.09 的线全被报） |

**换宽位置**：a8（0.09 段在边外 1 mm 处换宽）和 a9（边外 0.06 mm 处换宽）在 q03 里都不被报；a7（正好在边上）被报。线宽 0.1016 的圆头半宽 0.0508，所以换宽点要在**区边外 ≥ 半个线宽**（再留余量）处。H7 板的规则区是封装外扩 1 mm，在区边外第一个拐点换宽没有问题。

**DRC 怎么判宽度变化**：`track_width` 是**逐段**判的，每一段单独按自己匹配到的规则比较线宽；相邻两段宽度不同本身不是违规。线段"在不在区里"只取决于上面三个函数对这一段的判定。

### 6.3 建议写法

```
# 通用：区外信号线下限
(rule "signal_min"
  (condition "A.Type == 'Track'")
  (constraint track_width (min 0.1016mm)))
# 碰到规则区的线（含跨边的）：允许 0.09
(rule "bga_crossing"
  (condition "A.Type == 'Track' && A.intersectsArea('bga*') && !A.enclosedByArea('bga*')")
  (constraint track_width (min 0.09mm)))
# 整条线都在区内：必须正好 0.09
(rule "bga_inside"
  (condition "A.Type == 'Track' && A.enclosedByArea('bga*')")
  (constraint track_width (min 0.09mm) (max 0.09mm)))
```

后面的优先，所以越具体的越靠后。圆弧和直线一样被匹配。规则区名字拼错是静默的，要和 §3.4 的探针一样加一个检查（例如另写一条 `A.intersectsArea('bga*')` 的探针规则，确认至少命中一根线）。

---

## 7. 已验证和未验证

**已验证（我跑出来的）**：`length` 在命令行报告，且口径如 §2.1；圆弧长度精确；过孔只算实际穿过的层间；叠层缺失/开关关闭的后果；pad-to-die 计入；整网含分支、`fromTo` 取路径；`skew` 的基准是组内最长；`skew` 表达不了对 SDCLK 的 ±窗口；生成式窗口规则可用；`via_count`；规则顺序；`length`/`skew` 并存；串阻两段不能跨；网络类/网络名通配/`hasNetclass` 都生效；两类静默失效（§3.2）；pcbnew 看到调整图形但不能操作；`kicad-cli pcb` 没有重生成命令；脚本写 `(generated …)` 的文件层面行为；规则区三个函数的行为和换宽位置；`length_table.py` 能检出空规则。

**从官方手册/源码读到（没跑）**：IPC 接口的 `RunAction` 和动作名；调整器的圆角样式枚举；`Update()` 依赖界面里的工具；`GetLayerDistance` 的算法（数值上用实验核对了）；时间域（`ps` 单位）调整；`optimiseTracesInPads` 的裁剪规则。

**未验证**：见交付说明（e）。

---

## 8. 复现

```
cd docs/research/kicad-length-rules/lentest
D:\KiCad\bin\python.exe -I make_board.py . ..\..\..\..\templates\common\common.kicad_pro
D:\KiCad\bin\python.exe -I run_drc.py rules\e01_probe_all_lengths.kicad_dru ; compare_e01.py
D:\KiCad\bin\python.exe -I run_broken.py
D:\KiCad\bin\python.exe -I run_variants.py
D:\KiCad\bin\python.exe -I run_skew.py
D:\KiCad\bin\python.exe -I length_table.py lentest.kicad_pcb rules\e11_for_length_table.kicad_dru
cd ..\areatest
D:\KiCad\bin\python.exe -I make_board.py . ..\..\..\..\templates\common\common.kicad_pro ; run_area.py
cd ..\tuning
D:\KiCad\bin\python.exe -I make_generated.py ..\lentest <仓库外的空目录> ; check_generated_drc.py <同一目录> ; check_unknown_type.py <同一目录>
```

`tuning/probe_generators.py` 需要 KiCad 自己的 QA 板（`qa/data/pcbnew/tuning_generators_load_save.kicad_pcb`，GPL，未入库），从 KiCad 10.0.8 标签下载到仓库外。
