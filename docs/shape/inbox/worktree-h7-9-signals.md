# 收件箱：worktree-h7-9-signals

来自 2026-11-16 的 wayfinder 会话，解决 [定外设清单和引脚占用口径](https://github.com/immorcoding/PCB/issues/9)。合并到 `main` 后用 `shape-your-project` skill 清空。

## Signals

### process.md

- 2026-11-16 · PROC-8 · 起作用：口径、外设组合、每个外设的器件和接口分三轮（18 题）列给用户定；"六成"的口径定为按 IO 数（÷ 140），最终 127 / 140；没在官网核到的规格书和靠推断的参数八条记入未核对项（[决定票](https://github.com/immorcoding/PCB/issues/9)）。
- 2026-11-16 · PROC-8 · 用户纠正：认领票时我只读了正文、没读评论，第一轮推荐的套 B 和评论里记的讨论倾向（套 A 加音频、分立电源）相冲突，用户指出后那一轮作废重问。读票要连评论一起读（`gh issue view --json body,comments`），这一点现在没有写在任何规则里。
- 2026-11-16 · PROC-8 · 起作用：方案阶段的假设被规格书推翻一次。问用户时假定 ST 那块 4.3 寸屏是 40 脚 0.5 mm 排线，核对后发现外形图标的是 0.8 mm，ST 是直接焊在板上；改问一次后定为 0.5 mm 通用脚序的座。
- 2026-11-16 · PROC-5 · 缺口（接上一条同类信号）：Microchip 官网对 curl 和 WebFetch 都返回 403，只能读第三方镜像；TI 的规格书 curl 能直接下；`kicad-happy:digikey` 需要 `DIGIKEY_CLIENT_ID` / `DIGIKEY_CLIENT_SECRET`，环境里没有。这些还没记进 `tools.md`。
- 2026-11-16 · PROC-14 · 起作用：外设器件有没有现成的符号和封装，是让调研 agent 直接查 KiCad 库文件得出的（LAN8742A 的符号 24 脚逐脚对过规格书），没有凭记忆说。

### rules-and-schematic.md

- 2026-11-16 · RUL-10 · 第五次没用上：这次两个调研 agent 的技能列表里都有 `kicad-happy:datasheets`，也都加载了，但都没跑它的提取流程。理由是：它是"本地 PDF 提取并缓存到工程"的流水线，不管下载；固定的提取结构不含 I2C 地址、各模式电流、在产状态；方案阶段没有工程目录可挂缓存。两个 agent 都改用 pdftotext 加渲染图，并给了页码（[决定票](https://github.com/immorcoding/PCB/issues/9)）。这条规则在方案阶段该怎么执行，仍然没有写明。
- 2026-11-16 · RUL-6 · 提前起作用：SAI1、I2C4 的七个脚和套 A 原有 108 个脚的球号，在方案阶段就对照 DS12110 的引脚表用脚本比过；AF 编号只重核了新增的七个脚，其余留在未核对项。
- 2026-11-16 · RUL-7 · 相关：12 个辅助脚里除 SWO、背光 PWM、按键外都是普通 GPIO，和用户约定布局时可以在空脚间调换、换了当场报告；连接器位置仍在地图的迷雾里。
