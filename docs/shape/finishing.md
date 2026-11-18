# 收尾

走线和铜皮定稿之后的事：丝印、泪滴、最后的检查。文字尺寸等数值在 [design-rules.md](../design-rules.md)。

Next id: FIN-5

## Pillars

- 丝印是给拿到板子的人看的：先保证功能标注，再谈位号。

## silkscreen

丝印印什么。

### Rules

- **FIN-1** · provisional · 位号要么全留要么全不留；密度高放不下时只印功能标注，位号留在 Fab 层。留不留在布局阶段问用户。 _Why:_ 用户的要求：留就把阻容和芯片的都留着；四层板按 0.8 mm 字高 102 个位号只放下 55 个。
- **FIN-2** · provisional · 功能标注至少包括：排针每个引脚的功能、电源和电机的极性、测试点和按键的名字；直插排针正反面都标；3D 渲染里看字有没有被器件本体盖住。 _Why:_ 四层板审查时用户定的内容。
- **FIN-3** · provisional · 文字再小于规则下限之前先改规则并问用户。 _Why:_ 用户看 0.8 × 0.65 mm 的字仍觉得偏大，四层板收到 0.8 × 0.6 mm；再小板厂能不能印清楚没有核对过。

## closing

收尾的顺序和最后的检查。

### Rules

- **FIN-4** · provisional · 收尾顺序：地过孔 → 丝印 → 泪滴（走线和铺铜定稿之后）→ 渲染图；然后带 `--schematic-parity` 重跑 DRC、重跑金丝雀、甄别 kicad-happy 的发现。 _Why:_ 泪滴会被重新走线清掉；原理图一致性只有带这个选项才查。

## Signals
- 2026-11-15 · FIN-3 · 有了答案：嘉立创两个站点都写丝印字高最小 1.0 mm，项目现在用的 0.8 mm 低于它（[调研票](https://github.com/immorcoding/PCB/issues/5)）。
- 2026-11-16 · FIN-3 · 未处理：嘉立创丝印字高下限 1.0 mm 的答案早有了，`design-rules.md` 仍写 0.8 mm（[任务票](https://github.com/immorcoding/PCB/issues/18)）。
