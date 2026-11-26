# 走线

信号怎么走：约定、线序、等长、线形、哪些手工画、自动布线器怎么用。线形的数值标准在 [design-rules.md](../design-rules.md) 的"走线形状"一节；自动布线器的具体用法在 [tools.md](../tools.md)。

Next id: RTE-20

## Pillars

- 线序和等长都要在布局阶段就留好余地，走完再补是补不回来的。
- DRC 干净不等于整齐；整齐有自己的检查。
- 连通和整齐都要；拿一个换另一个要摆到指标表上给用户看。
- 规则跟着事实走：厂商指南、板厂能力和实测推翻了哪条，就改哪条（PROC-16）。

## Open questions

- 蛇形离拐点、邻线、规则区边留多远：原型取了 0.35 / 0.19 / 0.127 mm，用户没确认；正式板第一组蛇形出来时再给用户看一次。

- RTE-16 到 RTE-19 和 RTE-5、RTE-11 新增的部分，有六样检查还没有工具：换层地过孔的距离、高速线跨参考层的槽、同组过孔数和层序一致、声明过的分叉点放行、网络类之间的间距（含规则区内豁免和收窄段长度）、离参考面边缘的距离。接口和基准在 RK3568 验证方案汇总时定。
- 表层包地怎么画（地线宽度、地过孔怎么排、进球区前在哪里收）：等[包地原型票](https://github.com/immorcoding/PCB/issues/47)。

## Titles

- [conventions](routing.conventions.md): 动手前的约定和给用户看的时机。
- [order-and-length](routing.order-and-length.md): 线序和等长。
- [shape](routing.shape.md): 线形和完成标准。
- [hand-and-auto](routing.hand-and-auto.md): 手工和自动的分工。
- [high-speed](routing.high-speed.md): 高速接口的线：差分对、线距和包地、参考面和换层回流。
