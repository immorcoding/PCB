# 收件箱：tools-followup

- 2026-11-24 · routing · cite · RTE-5 · 起作用：平面槽长的两处上限改成可选、缺省不限（routing.md Signals 里 2026-11-24 那条“不一致”可以关掉）：`busroute` 的 `Profile.slot_max` 缺省 `None`，换层过孔阵连成的槽只记进 `metrics.json` 的 `slots`（表里一行“[槽]”），走线文件 `PROFILE = {"slot_max": ...}` 设了才出 `SLOT`；`planning.bga_fan` 不写 `[block] slot_max` 就不加槽的约束，只报最长的链。H743 的 `slot_max = 3.0` 没删：它是规划程序里的约束（台阶行和惰性割），删了重新规划可能出不同的 `bga_fan.json`，文件里注明“只为复现 2026-11-23 的方案，不是新板的上限”；老模型 `planning.bga_plan` 仍要一个值（没有时报错退出 2）。两块板的走线文件都没有用换层过孔阵，`SLOT` 一直是 0；H743 的 `routes_sdram.py` 在副本上快速构建，58 根线的长度和过孔数和 `out/final` 逐根相同。
