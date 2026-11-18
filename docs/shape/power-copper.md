# 电源与铜皮

哪些网络用铜皮、铜皮什么时候画、画成什么形状。

Next id: PWR-10

## Pillars

- 该用铜皮的网络从一开始就按铜皮来规划，不先当线走。
- 铜皮的外形和走线同一个标准：整齐，只有 45° 和 90°。

## classes

网络的分类和处理顺序。

### Rules

- **PWR-1** · provisional · 方案阶段把网络分成走线类和铜皮类，列表给用户确认。铜皮类包括地、输入电源、每颗稳压器的输入、输出和开关节点、各路电压轨（不论电流大小），并标明画法：大电流、负载分散的轨在电源层分块，其余画成外层局部铜皮。反馈、自举、使能、电流采样、芯片内部稳压器的电容脚是走线类。 _Why:_ 用户 2026-11-15 的复盘：人工会先想好哪些网络要用铜皮；H7 测试板上几毫安的小轨和电容脚要逐条问才分得清。 _Source:_ [H7 测试板的网络分类表](https://github.com/immorcoding/PCB/issues/11)
- **PWR-2** · provisional · 铜皮类网络不进布线器，也不先拉线；在"电源与铜皮"阶段专门处理。 _Why:_ 六层废弃板的开关节点先拉了 0.18 mm 的线再往上盖铜，电源面是信号走完后在剩下的缝里分出来的。

## shapes

铜皮和电源面的外形与连通。

### Rules

- **PWR-3** · provisional · 铜皮外形手工定，边只用 0°、45°、90°。 _Why:_ 用户 2026-11-13 的要求；第一版用焊盘的凸包，边是歪的。
- **PWR-4** · provisional · 电源面按铜皮区域草图分块；不跑自动分割，也不拿它的结果当参考。 _Why:_ 六层废弃板的自动分割给出 24 块，其中 12 块和主体不连通，还有 0.3–1 mm 宽的细长通道；H7 占位板上现成工具（KiCadRoutingTools）把 `+5V` 画成穿过两颗 BGA 过孔区的细条，没接到模拟 LDO，用户 2026-11-16 看过并排的两版后否决。 _Source:_ [铜皮区域原型](https://github.com/immorcoding/PCB/issues/16)
- **PWR-7** · provisional · 铜皮区域草图是一个文本文件，每块写网络、层、顶点；脚本检查通过才生成铺铜区。文本为准：用户在 KiCad 里改过铺铜区之后，先读回成文本再继续。 _Why:_ 用户 2026-11-16 看过原型后定；重跑脚本会按文本重画，冲掉 KiCad 里的手工改动。 _Source:_ [铜皮区域原型](https://github.com/immorcoding/PCB/issues/16)
- **PWR-8** · exploring · 电源层上不同网络的块之间留 0.5 mm 的缝，写成草图里单独的参数，不靠铺铜间距。 _Why:_ 用户 2026-11-16 为 H7 测试板定的；靠铺铜间距时缝只有 0.13 mm。 _Source:_ [铜皮区域原型](https://github.com/immorcoding/PCB/issues/16)
- **PWR-5** · exploring · 地用内层整层加外层铺地，外层最小铜宽 0.3 mm 并清孤岛。 _Why:_ 六层废弃板加外层铺地后，地的未连接从 41 项降到 13 项，不必每个地焊盘旁边挤一个过孔。
- **PWR-6** · provisional · 铺铜连没连上，以 KiCad 自己填充后的结果为准（`kicad-cli pcb drc --refill-zones` 的未连接数）；接不到铺铜的地焊盘用 `scripts/pour_islands.py` 找出来补孔。 _Why:_ 脚本里算的填充和 KiCad 的不一定一样。
- **PWR-9** · provisional · 铺铜和焊盘的连接沿用规则文件（插件焊盘花焊盘、贴片焊盘全连接），不为局部铜皮另设；局部铜皮把它碰到的插件焊盘整个包住。 _Why:_ 只从一侧碰到插件焊盘时只连上一根辐条，DRC 报 `starved_thermal`；贴片焊盘也用花焊盘时 H7 占位板上有 30 处接不上。用户 2026-11-16 定。 _Source:_ [铜皮区域原型](https://github.com/immorcoding/PCB/issues/16)

### References

- 分支 `integration-rk3568` 的 `rk3568_minsys/analysis/r3_pmic_FCu.png`：沿直连线的带状铜皮，边都是 45°/90°（PWR-3）
- 同一分支的 `rk3568_minsys/analysis/r3_In2.png`：自动分割的电源面，反例（PWR-4）
- 分支 `prototype/copper-regions` 的 `prototypes/copper-regions/out/a_sketch/L3.png`：按草图分块的 L3，用户 2026-11-16 认可（PWR-3、PWR-4、PWR-8）
- 同一分支的 `prototypes/copper-regions/out/b_krt/L3.png`：现成工具自动分割的 L3，反例（PWR-4）
- 同一分支的 `prototypes/copper-regions/sketch.txt`：草图文本的样例（PWR-7）
- 同一分支的 `prototypes/copper-regions/out/a_sketch/L1_power.png`：电源区的局部铜皮，DC 座的插件焊盘被整个包住（PWR-9）

### Signals

- 2026-11-16 · cite · PWR-4 · H7 测试板的电源层在方案阶段就定成三块（`+3V3`、`+5V`、`+3V3A`），每块都有实际负载，形状留到铜皮区域草图画（[决定票](https://github.com/immorcoding/PCB/issues/11)）。
- 2026-11-16 · cite · PWR-5 · H7 测试板的地不分割，模拟地和数字地是同一个网络，靠布局分区（[决定票](https://github.com/immorcoding/PCB/issues/11)）。
- 2026-11-16 · cite · new · H7 测试板每条轨只放测试点，不串 0 Ω 或跳线，理由是串联件会把铜皮掐成细脖子；目前只是这块板的决定（[决定票](https://github.com/immorcoding/PCB/issues/11)）。
- 2026-11-16 · cite · PWR-3 · 草图脚本在写文件之前检查每条边是不是 0°、45°、90°，不合格就不生成；H7 占位板上手画的 7 块铜皮没有一条边越格（[原型票](https://github.com/immorcoding/PCB/issues/16)）。
- 2026-11-16 · cite · PWR-6 · 原型各版的数字都取自 `kicad-cli pcb drc --refill-zones --save-board` 填充并保存后的板文件，脚本不自己算填充（[原型票](https://github.com/immorcoding/PCB/issues/16)）。
- 2026-11-16 · friction · PWR-5 · 规则只说了外层铺地的最小铜宽，没说局部铜皮的最小宽度和它到铺地的间距；原型里取的是最小宽 0.20–0.25 mm、间距 0.20 mm（[原型票](https://github.com/immorcoding/PCB/issues/16)）。
