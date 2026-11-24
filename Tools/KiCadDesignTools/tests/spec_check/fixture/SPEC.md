# 基准板：方案定稿（只有 spec_check 读的那张表）

## 7. 规格档（已定）

### 7.2 本板取值（已定；必填）

| 项目 | 本板取值 | 数据源 | 依据 / 说明 |
|---|---|---|---|
| 信号层数 | 4 个信号层：信号 / 地 / 信号 / 信号 / 电源 / 信号 | `board.toml:layers.roles` | |
| 小去耦到电源球的距离上限 | 2.5 mm | — | |
| BGA 背面去耦的封装 | 0402 | — | |
| 蛇形腿中心距：数据 | 0.3 mm（3H） | `routes_bus.py:TUNING.pitch.default` | |
| 蛇形腿中心距：时钟 | 0.5 mm（5H） | `routes_bus.py:TUNING.pitch.CK` | |
| 蛇形起始摆幅 | 0.5 mm | `routes_bus.py:TUNING.amp` | |
| 蛇形块两头的直线 | 0.7 mm | `routes_bus.py:TUNING.keep` | |
| 数据线组内等长：字节通道 0 | D0–D7 + DM0，组内最长减最短不超过 1.27 mm（50 mil） | `kicad_dru:bench_lane0.skew.max` | |
| 地址命令对时钟 | A0–A3 每根对时钟 ±10 mm | `length_groups.json:groups[rule=bench_window].lo`；`length_groups.json:groups[rule=bench_window].hi`；`routes_bus.py:TUNING.groups.addr.hi` | |
| 过孔数上限：哪些线 | D0–D7、DM0、CK | — | |
| 过孔数上限：个数 | 每根 3 个 | `kicad_dru:bench_via_max.via_count.max`；`routes_bus.py:VIA_LIMIT` | |
| 电源层块间的缝 | 0.5 mm | `copper.sketch:gap` | |
| 外层铺铜最小铜宽 | 0.3 mm（铺地）；局部铜皮 0.2 mm | `copper.sketch:L1_GND.minwidth`；`copper.sketch:minwidth` | |
| 平面上过孔避让连成的槽 | 不设长度上限，只报数 | — | |
