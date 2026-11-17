# 4b_combined_p05：和 4_combined 同样的走线，蛇形腿间距全部 0.5

原型（issue 21），用完即弃。走线和换位表与 `4_combined` 完全相同（都来自 `variants/4_combined/plan4.py`），只把数据线和 DQM 的蛇形腿间距从 0.3 改成 0.5，用来在同一套走线上比较两种间距。

结果：0.5 也全部放得下，19 / 19 在窗口内，DRC 0 项，没有哪根缺长度。数字、对比表、等高约定的例外（0 处）和要看的地方都写在 `../4_combined/README.md`。

打开方式：KiCad 里开 `out/4b_combined_p05/routetune.kicad_pro`。
