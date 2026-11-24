# 工具用法和已知的坑

事实和命令，不是规则。"该怎么做"在 [shape/](shape/) 里；这里只回答"用什么、怎么跑、哪里会坑"。

## 位置

- KiCad 10.0.8：`D:\KiCad\bin\`（`kicad-cli.exe`，带 pcbnew 的 `python.exe`），不在 PATH 上。
- KiCadRoutingTools（自动布线）：`Tools/KiCadRoutingTools/`，独立 git 仓库，已 gitignore。它的脚本假定 cwd 是该目录，用 `.venv/Scripts/python.exe -X utf8` 运行。
- kicad-happy（审查 / EMC / BOM / JLC）：项目级插件，见 `.claude/settings.json`。SPICE 暂不可用（未装独立 ngspice）。

## 常用命令

| 做什么 | 命令 |
|---|---|
| 规则是否生效 | `D:\KiCad\bin\python.exe scripts\dru_canary.py <工程>.kicad_pcb`，输出 `OK` |
| 每条规则是否匹配到对象 | `D:\KiCad\bin\python.exe scripts\dru_match.py <工程>.kicad_pcb`，空匹配的规则标 `EMPTY`（RUL-2）；每条规则跑一次 DRC，31 条规则约 1 分钟 |
| 生成等长窗口规则 | `D:\KiCad\bin\python.exe scripts\len_rules.py <工程>.kicad_pcb`（读板目录的 `length_groups.json`，改写 `.kicad_dru` 末尾的生成段）；加 `--check` 只报告是否过期 |
| 全部工具的回归 | `D:\KiCad\bin\python.exe scripts\regress.py`（跑 `scripts/tests/*/check.py`，PROC-15） |
| 走线阻抗 | `D:\KiCad\bin\python.exe scripts\impedance.py`（嘉立创 JLC06161H-3313E 上的单端和差分，二维场解；结果是计算值） |
| H743 板按步骤构建 | `sh stm32h743_sdram/build.sh rules`（工程文件、规则基准板、金丝雀、规则匹配、等长窗口；规则匹配逐条跑约 8 分钟，加 `SKIP_DRU_MATCH=1` 跳过它，留给 `finish-checks` 跑一次）。`make_project.py` 还把已有板文件层表里的铜层行改成它的 `LAYERS`（只改这几行，2026-11-23 起 In2.Cu 信号 `L3_SIG`、In4.Cu 电源 `L5_PWR`）；route1 / route2 开头也跑一次 |
| 铜皮区域草图 | `D:\KiCad\bin\python.exe scripts\cu_sketch.py check <草图> [--board <板>]`，另有 `apply`（按草图写铺铜区，只动它自己建的 `cu:` 开头的区）、`read`（从板读回草图，PWR-7）、`measure`（铜皮那组指标）。草图格式见脚本开头和 `stm32h743_sdram/copper.sketch` |
| 总线走线（线束、BGA 扇出、蛇形等长） | `D:\KiCad\bin\python.exe scripts\busroute\build.py <走线描述.py> [--fast] [--sketch] [--out 目录] [--write-board]`。默认在 `--out` 下的板子副本上构建，加 `--write-board` 才写真板；`--fast` 只做几何检查（57 根不到 1 秒），完整构建含 DRC、长度、指标、图片（7–14 秒）。描述文件的格式见 `scripts/busroute/job.py` 开头（蛇形：`TUNING` 加补线位置 `Bundle.slot` / `job.slot`，画法和限制在 `scripts/busroute/tune.py` 开头），例子是 `scripts/tests/busroute/bench_routes.py`、`bench_tune.py` |
| 等长预算（只算不画） | `D:\KiCad\bin\python.exe scripts\busroute\build.py <走线描述.py> --tuning-budget`：每组的目标（组内最长 − 容差 + 余量）、每根的自然长度和要补多少、每个补线位置在摆幅 amp 和 amp_max 时按 RTE-2 的式子能补多少（不查间距），列出容量不够的网络；有不够的退出码 1。读板不写板，基准板上 0.1 秒 |
| 对时钟的等长组（基准分段相加） | `TUNING` 的组写成 `{"nets": [...], "ref": ["FMC_SDCLK", "FMC_SDCLK_R"], "lo": -20, "hi": 20}`（不写 `spread`）：基准是几段相加（串阻两侧），先补基准到“最长成员 − hi + 余量”（几段的补线位置按写的顺序分摊），再按补到的基准把短的成员补到“基准 + lo + 余量”。DRC 侧在 `length_groups.json` 写同样的窗口（`len_rules.py` 生成） |
| 蛇形避让后建的组 | 走线描述里 `TUNE_OBSTACLES = <板>`：那块板上别的网络的线、圆弧、过孔也当障碍。`build.sh route1 / route2` 先把板子拷一份、去掉 SDRAM 组自己的铜（`out/<步>/obstacles.kicad_pcb`），SDRAM 组的蛇形就避开随后才重建的电源组和各局部组 |
| H743 板 SDRAM 的补线空间 | `D:\KiCad\bin\python.exe stm32h743_sdram\tune_sites.py <板> [--spread 5] [--window 20] [--natural <metrics.json>]`：L1 / L3 / L4 上每根要补的线（四个字节通道、时钟、地址命令）在规则区外的直线段两侧各能放一块多高、补多少、被谁挡住；在不带蛇形的构建结果上跑（走线描述加环境变量 `NOTUNE=1`） |
| 摆位 | `D:\KiCad\bin\python.exe stm32h743_sdram\place.py`；`--pcb <副本> --rot <角度>` 在副本上试别的 SDRAM 转向 |
| 布局指标（LAY-2、5、6、8） | `D:\KiCad\bin\python.exe scripts\place_check.py <板> [--edge J1=L ...] [--allow-under U1,U2] [--not-supply U3.5] [--json <输出>]`：摆进板框的个数、courtyard 重叠、安装孔周禁布、封装禁布区、连接器到板边、背面焊盘压顶面焊盘、每个电源脚到最近 100 nF 的距离、排针和测试点旁的丝印位置；几秒 |
| 出线通道（LAY-2） | `D:\KiCad\bin\python.exe scripts\escape_check.py <板> --ref U1 [--ref ...] [--window x0 y0 x1 y1] [--debug U1.A1 <png>]`：每个焊盘单独查能否走出去（到窗口边、到同网络的别的器件、电源网络能否打孔），最多两个过孔；不算容量。两颗 BGA 加 40 mm 窗口约 15 秒 |
| H743 板布局一步 | `sh stm32h743_sdram/build.sh layout`（摆位 → 线序草图重建 → 上面两个检查 → 铜皮草图检查 → `layout_probe.py` 的实测试走；约 70 秒） |
| H743 板走线二一步 | `sh stm32h743_sdram/build.sh route2`（route1 的全部，再按 `build.sh` 里 `ROUTE2_GROUPS` 的顺序把各组局部走线写入真板（`LOCAL_BOARD`=真板，`--write-board`），填充、DRC、布局检查，`route2_report.py` 出一张表 `out/route2/table.txt`：每个走线描述文件一行、以太网差分对、布局和铜皮草图，后面接 route1 的 SDRAM 表；约 4–5 分钟）。加一组 = 在 `ROUTE2_GROUPS` 加一行“组名 文件名”，描述文件从 `LOCAL_BOARD` 读板。平面开槽量 L2、L5（总线窗口 `slots.json`，L5 全板每块 `slots_l5.json`），外层地铺铜每块有没有地过孔 `pour_islands.txt`；图：信号层 L1 / L3 / L4 / L6，平面 `L2_planes.png`、`L5_planes.png`、`L5_board.png` |
| H743 板收尾一步 | `sh stm32h743_sdram/build.sh finish`（route2 之后，可重复：剥掉上次收尾写的东西 → 光学定位点 → L3 / L4 铺地和禁止铺铜区（`finish_pour.py`：两颗 BGA 的规则区；每块蛇形外扩 0.5 mm，蛇形从板上的圆弧找，只有 `tune.py` 写圆弧）→ 窄铜和小碎片加禁止铺铜区（`finish.py clean <板> <目录> shape`，最多两轮）→ 缝合地过孔两轮（L1、L3、L4、L6 的每片；长条两端各一个）→ 没处放过孔的内层碎片加禁止铺铜区（`clean ... anchor`）→ 铜皮报告 `pours_after.txt`（每层碎片、最窄、窄条、L4 / L6 在 L5 块缝上的线旁边有没有地）→ 阻焊和丝印 → 泪滴 → 带原理图一致性的 DRC、金丝雀、渲染图；约 8.5 分钟，2026-11-24 实测 496 s）。整步低优先级跑：`cmd //c "start /low /affinity F /wait /b sh stm32h743_sdram/build.sh finish"`。`FINISH_BOARD=<副本>` 在副本上跑：副本目录里要有同名的 `.kicad_pro`、`.kicad_dru`，查原理图一致性还要原理图和库表；这时不看锁文件、不重写工程文件 |
| H743 板发布用图（带网络名） | `sh stm32h743_sdram/build.sh publish`（即 `D:\KiCad\bin\python.exe stm32h743_sdram\publish.py [--rest 20] [--stage all/dump/svg/png] [--only L1,L3,silk,all_layers,signal_layers]`）：板子拷到 `out/publish_work/` 只读；pcbnew 取线、圆弧、过孔、焊盘、铺铜填充，`kicad-cli pcb export svg --theme _builtin_default` 取层颜色和丝印，脚本画 SVG 并加网络名，无头 Edge 按 ≤4000 px 分块截成 PNG 再拼。输出 `stm32h743_sdram/publish/`（每层整板 100 px/mm、MCU/SDRAM 局部 250 px/mm、叠层图，说明见那里的 `README.md`）。重活一次一个、低优先级四核、间隔 20 s，约 15 分钟（每张 PNG 约 50 s）。不出 3D 图（用户在 KiCad 3D 查看器里手工截） |
| H743 板电源与铜皮一步 | `sh stm32h743_sdram/build.sh copper`（摆位 → 铺铜区 → `routes_power.py`（BGA 区外）和 `routes_power_bga.py`（两颗 BGA 的电源球、背面去耦）写真板 → 填充 → 同样两组写线序草图副本、填充、平面开槽（U31）→ 出线检查 → 图 → `out/copper/table.txt`；约 3.5 分钟） |
| 原理图构建并检查 | `sh scripts/sch_build.sh <工程目录> <输出目录>`（生成 → 升级到 KiCad 10 格式 → ERC → 网表 → PDF） |
| H743 板的原理图 | `sh stm32h743_sdram/build.sh sch`（上一行，加网表对意图、对 `pins.csv`、对 `swap.csv` 的检查和 kicad-happy 审查；约 15 秒）；单独试一页：`sh stm32h743_sdram/sch/try_page.sh <输出目录> <页名>` |
| DRC | `kicad-cli pcb drc --refill-zones --severity-all`；收尾时加 `--schematic-parity` |
| 重新填充铺铜并存回板文件 | `kicad-cli pcb drc --refill-zones --save-board --severity-all --format json -o <报告> <板>`；之后的测量和出图直接读板文件里的填充，不在 pcbnew 里再填一次 |
| 检查本地 HTML 页面 | `"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --headless=new --window-size=1500,1900 --screenshot=<png> "file:///<路径>"`，再看截图 |
| 线形检查 | `scripts/track_shape.py <板>` |
| 四层板一次构建 | `sh steval_fcu001v2/build_pcb.sh <报告目录>`（`place.py` → `route.py` → `silk.py` → 泪滴，顺序不能换） |

## `scripts/` 下的工具

| 脚本 | 用途 |
|---|---|
| `kisch.py` | 生成原理图：从官方符号库取符号、按引脚坐标连线。每个工程一个 `gen_sch.py`，参考 `stm32f411_minsys/gen_sch.py` |
| `drc_probe.py` | 公共函数：在板子的副本上换一份规则文件跑 DRC、解析报告、用探针规则量网络长度 |
| `dru_match.py`、`len_rules.py`、`impedance.py`、`regress.py` | 见上面的命令表 |
| `net2pcb.py` | 网表进板 |
| `pcb_view.py` | 带走线和飞线的示意图 |
| `layer_view.py` | 带坐标网格的单层视图，规划手工走线用 |
| `via_spots.py` | 找合法过孔位置（不看封装里的禁布区） |
| `track_shape.py` | DRC 不查的走线形状：非 45° 线段、阶梯线、小倒角直角、短距离连续折弯、碎线段。圆弧算进走线：圆弧不算折弯，拐点后不到 0.35 mm 接一段同向转弯的圆弧报 `sharp`，两段相切圆弧之间的短腿（蛇形）不报；板上有圆弧时多一行 `arc-joint`（不相切的圆弧接点，> 1°）。没有圆弧的板输出和以前逐字相同。基准 `scripts/tests/track_shape/check.py` |
| `pour_islands.py` | 找没接到网络上的铺铜碎片 |
| `silk_refs.py` | 自动摆位号，稀的板子用；密板把标注坐标写在工程的 `silk.py`（参考 `steval_fcu001v2/silk.py`） |
| `place_check.py`、`escape_check.py` | 见上面的命令表；基准 `scripts/tests/place_check/check.py` |
| `teardrops.py` | 泪滴。Python API 不暴露泪滴参数，脚本写入文件后由 `kicad-cli` 生成 |
| `auto_tracks.py` | 把自动布线结果抽成 JSON，由工程的 `route.py` 回放 |
| `auto_clean.py` | 清理布线器留下的锯齿和直角 |
| `auto_tidy.py` | 在固定点之间把布线器的折线拉直，自带间距检查，跑完仍要 DRC |

原理图版面用 `pdftoppm -r 200 -png -x -y -W -H` 裁剪放大看文字重叠。

`kisch.py` 的分页（2026-11-20）：`Design(project)` 加 `design.page(name, title)`，每页的画法和单张的 `Sch` 相同，另有 `glabel()` 写全局标号；`design.save(目录)` 写一个只放图纸符号的根图 `<工程>.kicad_sch` 和每页一个 `<工程>_<页名>.kicad_sch`。KiCad 没有真正的多文件平铺设计，这是它的标准做法（相当于 AD 里不放端口、网络标号全局有效的平铺工程）。网表里的网络名：全局标号是裸名（`FMC_D0`），电源符号是符号值（`+3V3`），子页上的本地标号是 `/<页名>/<标号>`（改页名就改网络名），单张图的本地标号是 `/<标号>`。跨页的网络用全局标号；规则文件按裸名写。电源轨上不要再放全局标号（全局标号会顶掉电源名）。根图是第 0 页，页面从 1 起。ERC 的违规按整份报告数，不按页数（有两类违规会被记到根图名下）。

## 指标表的列（PROC-4）

每次构建输出同一张，数字只从板文件和 DRC 报告取。

| 组 | 列 |
|---|---|
| 连通 | DRC 未连接数、开路清单、其他 DRC 项按类型计数 |
| 线形 | `track_shape.py` 各项，加圆弧的几何检查 |
| 等长 | 每组在窗口内的根数、最差一根差多少、每根总长对上限、蛇形块数和补的总长、没补够的网络和差多少 |
| 过孔 | 每根过孔数的最大值和合计、超过约定上限的清单 |
| 线序 | 各线最短路径相差多少、同层交叉数 |
| 铜皮 | 每块的边数、不在 45° 格上的边数、碎片数、最窄连接和位置、不同网络最小距离、铜皮类未连接数、电源面块数 |
| 规则生效 | 金丝雀结果、空匹配的规则数 |
| 构建 | 耗时、当前第几轮 |

## 用 KiCadRoutingTools 时（两块测试板上的做法）

- 内层只做平面时给它 `--layers F.Cu B.Cu`。
- 手工铜皮要锁住：`route.py --no-pour <副本>` 写出的副本里手工铜皮是锁定的；另设 `KICAD_RIP_PREEXISTING=0 KICAD_FINALIZE_RIP=0`，加 `--keep-input-copper`。不这样它会拆掉手工走的差分对重走。
- 不让它缩尺寸：默认它会把过孔缩到 0.25 mm、线宽缩到 0.089 mm。用 `--escalation off --fab-tier standard`；`--same-net-pad-clearance 0.1` 禁止盘中孔。
- 0.5 mm 间距 IC 的扇出它在精确尺寸下过不了（四层板第一次 17/24）。把要换层的引脚用 0.45/0.2 过孔交错排成两三排，总线整组手工走，它只接过孔之后的长线。
- 分批跑，先走最受限的；一批失败的网络和它的邻居一起重跑（`--skip` 把它们从回放里去掉）。
- 每次导入结果后跑 `auto_clean.py`，全部走通后跑 `auto_tidy.py --clearance 0.13`，再 DRC，再 `track_shape.py`。它会用一串 0.2 mm 竖线加 0.035 mm 斜线拼出非 45° 的斜线，逐段的角度检查查不出来。
- 它的线头常停在过孔中心旁边 0.05–0.25 mm 处（靠铜皮重叠连通，DRC 不报），重走时接到中心。
- 它的 `route_planes.py` 不用来铺铜和分割电源层（PWR-4，用户 2026-11-16 否决）。当时在占位板上试的是 0.24.0：一层分给多个网络写成 `--nets "A|B|C"`，一次约 10 秒；它会在同网络的球和过孔之间补短线，会往 `.kicad_pro` 里写值，没有外层局部铜皮的功能。

## 已知的坑

- **`.kicad_dru` 语法错误会让整个文件静默失效**，细节见 [design-rules.md](design-rules.md) 的"已知陷阱"。
- **用户开着 KiCad 时改 `.kicad_pro` 会丢**：KiCad 关闭工程时用内存里的旧设置覆盖文件。工程目录下有 `~*.lck` 说明 KiCad 正开着。
- **pcbnew**：`board.Remove()` 之后，同一进程里 `board.Zones()`、`GetFootprints()` 等集合会返回无类型对象，访问即报错或崩溃。先读完需要的数据再删；删完还要继续读就另起一个进程（同一进程里重新 `LoadBoard` 也不行，参考 `steval_fcu001v2/silk.py` 的 `--strip`）。
- **pcbnew：板文件里的铺铜填充是带切缝的**。孔洞用零宽的切缝连到外轮廓，`HoleCount()` 是 0。对填充做收缩（`Deflate`）之前先 `Simplify()`，否则会沿切缝断开，量出来的宽度偏小（铜皮原型上 1.57 mm 量成了 0.65 mm）。
- **pcbnew：KiCad 10 的 `BOARD.GetBoardPolygonOutlines()` 要两个参数**，第二个是 `aInferOutlineIfNecessary`。
- **对整层铺铜做收缩运算很慢**：一整层铺地带着几百个避让孔，收缩几毫米一次要几分钟。这类测量只对电源块和局部铜皮做。
- **`route.py` 会清掉泪滴**，所以泪滴放在走线和铺铜定稿之后。
- **删掉封装自带的丝印外框、打开"允许阻焊桥"**，每个封装各多一条 `lib_footprint_mismatch`，在审查清单里说明。
- **厂商网站对自动下载的限制**（2026-11 实测）：TI、Winbond、Vishay 的 PDF 用 `curl` 能直接下；ST 的 PDF `curl` 拿不到，用 WebFetch；ISSI 返回占位页（反爬），Micron 和 Winbond 的零件页是 JS 渲染、读不到；Microchip、Hirose、Würth（we-online）、sdcard.org 对 `curl` 和 WebFetch 都返回 403。拿不到的不绕过，列出官网地址请用户手动下载到板目录的 `datasheet/`（不提交）。2026-11-20 补：Abracon、ECS、Bourns、Same Sky、Keystone、onsemi、Coilcraft 的 PDF `curl` 能下；Vishay 要用产品页上的确切文件名（`vishay.com/en/product/<文档号>/`），猜的文件名返回 HTML；Murata、TDK、Nexperia、Phoenix Contact 拒绝 `curl`；ST 的 RM0433 超过抓取工具的大小上限。
- **`kicad-happy:digikey` 需要 `DIGIKEY_CLIENT_ID` / `DIGIKEY_CLIENT_SECRET`**，环境里没有，在产状态和库存查不了。
- **多列表格的 PDF 文字层会错列**（TI 订货表把 TPS62A02PDDCR 读成别的封装）：表格渲染成图读，`pdftotext` 只作核对（PROC-14）。ST 的 Altium 导出原理图，文字层里网络名和位号是乱的，同样处理。
- **pcbnew 的 `SaveBoard` 会在板文件旁边写一个默认的 `.kicad_pro`**（板子是从没有工程文件的位置读进来时）：网络类和板级下限全部变回 KiCad 默认值，规则文件照常加载，表现是按网络类写的规则全部匹配不到东西。先存板，再拷工程文件。
- **断言探针（`assertion`）每个对象只报一条**：几条断言规则匹配同一个对象时只有一条出现在报告里，所以 `dru_match.py` 每条规则单独跑一次 DRC。断言只看单个对象，条件里的 `B.` 子句探不了。
- **DRC 报告里规则名的写法不统一**：多数违规把规则名放在单引号里，差分对间隙（`diff_pair_gap_out_of_range`）是不带引号的裸名；网络类的间距违规引号里是网络类名（如 `Default`）。
- **只接了一层的过孔不计入网络长度**（过孔高度按实际换层算），但 `via_count` 照样数它。
- **过孔可以去掉未连接内层上的焊盘**：pcbnew 里 `via.SetRemoveUnconnected(True)` 加 `SetKeepStartEnd(True)`，板文件里是 `(remove_unused_layers yes) (keep_end_layers yes)`（界面：过孔属性的“焊环”选“起始、结束和已连接的层”）。DRC 认这个设置：该层上只按孔到铜查，不再按焊盘查间距（2026-11-20 实测）。
- **kicad-happy 的 skill 在子 agent 和这类后台会话里调不了**，但分析脚本可以直接跑：`python ~/.claude/plugins/marketplaces/kicad-happy/skills/kicad/scripts/analyze_schematic.py <根图> --text --stage schematic`。它会在当前目录建 `analysis/`，所以先 `cd` 到输出目录。
- **原理图里库符号横放的两脚件**（`Device:D`、`D_Zener`、`LED`）和竖放的（`R`、`C`）引脚方向不同：按“上面的脚接 a”这类位置判断之前要先转对方向，否则两个脚落到同一个网络上（H743 板的 `sch/common.py` 的 `two()` 第一版有这个错，三页各自绕开，靠网表核对发现）。
- **KiCad 的 `power` 库没有 `+3V3A`**（有 `+3V3`、`+3.3VA`）：H743 板在工程符号库里放了一个改名的副本。电源符号的网络名取自它的 Value。
- **读写板子时网络会被旧的铺铜填充带偏**：过孔落在别的网络的旧填充里、自己那块铜上又没有本网络的焊盘时，`LoadBoard` / `SaveBoard` 会把它改成填充的网络（加在旧 GND 填充里的 `+5V` 过孔存出来是 GND）。脚本往板上加铜之前先清填充（`zone.UnFill()`），`cu_sketch.py apply` 就是这么做的。
- **规则文件里的 `zone_connection` 压过铺铜区自己的焊盘连接设置**（10.0.8 实测：区设成花焊盘、全连接、不连接，填充结果相同）。
- **孤岛按连通判定，不是只看焊盘**（2026-11-24 在 H743 板上实测修正；这里以前写“只有过孔不算”）：一块填充经过本网络的过孔、线、别的铜皮能连到焊盘就不算孤岛。L1 上一块 7.8 mm²、只有一个缝合地过孔（过孔连到 L2 整层地）的碎片在“总是移除”下留着；内层铺地里带地过孔的块 DRC 不报 `isolated_copper`，一个过孔都没有的块才报。所以内层铺地用“总是移除”会把没有过孔的块全删掉，缝合过孔来不及接；用按面积移除（`ISLAND_REMOVAL_MODE_AREA`，`SetMinIslandArea` 的单位是 nm²，2 mm² 写 `int(2e12)`）只删小于门槛的无连接块；有过孔连着的小块哪种模式都不删，要脚本去（`finish_pour.py` 的 `clean`）。“总是移除”只在同一个区另有连通的块时才删。
- **新建 `ZONE()` 的默认值**：间距 0.5 mm、最小宽度 0.25 mm、花焊盘间隙和辐条 0.5 mm、移除孤岛。脚本建区要逐项写明。
- **`kicad-cli` 的 DRC 报告最多列 499 条未连接**：没布线的板子上别从报告里数某一组的未连接（H743 板 pcbnew 数出来是 633 条）。
- **KiCad 10 的板文件里走线和过孔按网络名记**（没有网络表），可以当文本增删；`busroute` 就是这样写板的，其余内容逐字节不变。
- **规则区内 0.30 / 0.15 的过孔，中心距至少 0.425 mm**：卡住的是孔到铜（0.075 + 0.15 + 0.2），不是焊盘间距。
- **`pcbnew` 的 `GetLayerName` 返回的是自定义层名**（`L2_GND`），文件里是 `In1.Cu`。
- **route2 不剥收尾写的铺铜区和禁止铺铜区**（`FIN_` 开头：L3 / L4 铺地、蛇形和碎铜的禁止区、光学定位点的禁止区）：route2 的填充和表里会带着上一次收尾的内层铺地和旧位置的禁止区（缝合过孔被当无主铜删了，内层铺地的块会报 `isolated_copper`）。route2 之后总要再跑 `finish`，它先全部剥掉再按新走线重做。
- **pcbnew 的 `FromMM` 不收 `numpy.float64`**（报 `TypeError`）：从 numpy 数组算出来的坐标先 `float()`。
- **Bash 工具的前台命令过 3 分钟会被自动移到后台**（输出管到 `tail` 时文件里一直是空的，结束才有）：`build.sh finish` 这类长步骤照样只跑一个、等它结束的通知再动下一步，不要以为它停了又起一个。
- **`kicad-cli` 的控制台输出不是 UTF-8**：`subprocess.run(..., text=True)` 会在读线程里解码出错，按字节取。
- **`place.py` 这类脚本里 `board.Remove()` 要放在所有读取之后**：第二次运行时先删旧板框再遍历铺铜区会段错误（上面那条 pcbnew 的坑的又一例）。
- **工程文件已存在时 `SaveBoard` 照样重写 `.kicad_pro`**：填进 pcbnew 的默认值、重排网络类（规则值不变）。H743 板的工程文件由 `make_project.py` 生成，`place.py` 存板前读下工程文件的字节、存完写回（2026-11-21）。
- **pcbnew：`LSET(层号)` 在 KiCad 10 的 Python 里报重载错误**：先 `ls = pcbnew.LSET()` 再 `ls.AddLayer(层号)`。
- **pcbnew：courtyard 和 Fab 图形的 `GetBoundingBox()` 含线宽的一半**：按外形算距离、面积时取轮廓的顶点（`GetCourtyard(...).Outline(0)`），或把框缩回线宽的一半。
- **背面两脚件的焊盘位置**：`place.py` 先翻面再设方向，结果和顶面同一方向时焊盘位置相同（1 脚在 −x，转 90° 后在 +y），2026-11-21 实测。
- **布局阶段的出线检查要在线序草图的副本上跑**：SDRAM 的走线只在 `out/sketch/rot0/` 的副本里，真板文件里没有。
- **Git Bash 会把 `/` 开头的网络名改写成路径**：传网络名的命令前 `export MSYS2_ARG_CONV_EXCL='*'`。
- **Shell here-doc 会改写反斜杠和 `\n`**：补丁脚本用文件写，不用 here-doc。
- **`busroute` 不在平面层上画线**（2026-11-23 起）：板文件层表里类型是 `power` 的铜层（H743 板 L2、L5）算平面层，走线描述里有线放在这些层上直接报错（`RouteError`）；其余铜层都能走线（H743 板 L1、L3、L4、L6）。
- **`busroute` 在规则区内默认把线宽改成 0.09**：电源类的狗骨线、背面短线要保留给定线宽，在走线描述里写 `PROFILE = {"area_free_classes": ["PWR"]}`（规则文件 `bga_width_inside` 本来就不管 PWR 类）。
- **DRC 的 `corner_angle` 也查在过孔中心相交的两段线**：两个球共用一个过孔、两条狗骨线成 90° 时报 `track_angle`；`bga_power.py` 让第二条线停在过孔里、离中心每轴 0.05 mm（靠过孔铜连上，没有共同端点）。
- **`escape_check.py` 允许单根线从 BGA 球阵内部穿过去**：电源球的狗骨线和过孔会把这些路堵上，外圈球的"不打孔出线"可能因此变成"打 1 个孔"；对比前先看路径是不是从球阵内部走的（`--debug`）。
- **在铺铜板的副本上做实验，先 `copper_report.py unfill`**：旧填充会在读板时改过孔的网络（上一条 pcbnew 的坑），DRC 也会报一堆和旧填充的间距。
- **KiCad 10 板文件里的走线圆弧**是 `(arc (start x y) (mid x y) (end x y) (width) (layer) (net "名") (uuid))`，`busroute` 和直线段一样按文本写入（写在直线段之后、过孔之前）。DRC 量网络长度按圆弧真长（三点定圆）：蛇形基准板上脚本算的长度和 DRC 量的最多差 0.0001 mm。
- **RTE-7 的"半径 0.25"和数据线"腿中心距 0.3"不能同时成立**：弯顶、弯底是半圆，RTE-2 的 0.858·p 也是按半圆（半径 = p / 2）算的。`tune.py` 取半径 = 腿间距 / 2（数据 0.15，时钟 0.5 时 0.25），`TUNING` 的 `radius` 只当上限，腿间距大于 2 × radius 报错。
- **腿间距 0.5（半径 0.25）时摆幅 0.5–0.605 画不出**：腿长 a − 2r 落在 0 和 0.105 mm 之间，短于 `min_segment`（0.1 整在斜线上会被 DRC 量成 0.0999999）。`tune.py` 跳过这些高度，改用少一个弯、高一点的块（基准板上 3 个 0.5014 改成 2 个 0.6985）。
- **`Bundle.slot(free=…)` 让位的折线要离下一个拐角够远**：外侧的线在 s1 之后再走 dV 加嵌套量才折回，离拐角近时报 `runs backwards` 或短于 0.1 的线段（蛇形基准板第一次 s1 离拐角约 0.6 mm 就报了）；折回段和拐角挤在 2 mm 内时 `track_shape.py` 报 crowded。
- **蛇形和线束的线距**（2026-11-22，H743 板停点 6）：线束里 0.25 mm 线距的两根线边到边 0.148 mm，低于 `TUNING` 的 `clr` 0.19。`tune.py` 以前因此拒绝任何紧挨邻线的补线位置（弯朝另一侧也不行）；现在某个采样点离别的网络不比同一位置的原直线更近时不按 `clr` 查，所以弯这一侧仍要让出 `clr`（`Bundle.slot(free=…)` / `widen`），背面的邻线可以留在原线距。`tune.py` 不画规则区里的蛇形（`area_gap` 对区内一律不过）；线束里一根线的 jog 离前一个拐角不到 2 mm 时 `track_shape.py` 报 crowded（圆弧不算折弯）。
- **挪了器件之后，压在新焊盘上的旧走线会被 pcbnew 改成那个焊盘的网络**（2026-11-22，停点 7：R102 转向后，`+5V_REG` 的旧线和过孔存出来成了 `FB_5V`，`SHARED` 组按网络和位置找自己的旧铜，找不到就留在板上造成短路）。改了 `place.py` 的构建先 `copper_report.py strip` 各组、再摆位（`build.sh route1 / route2` 就是这个顺序）。
- **没有组认领的铜不会被重建，也不会被清掉**（2026-11-23）：`copper_report.py strip` 只删各组记录里的铜；停点 5 留下的一个 `+3V3_MCU` 过孔和 0.57 mm 的 L6 短线（一个悬空线头）一直留在板上。`build.sh route2` 把所有组都剥掉之后跑 `copper_report.py orphans`，剩下的线、圆弧、过孔全删并列出（`out/route2/orphans.txt`）。
- **蛇形组先建、别的组后建时，蛇形看不到后建的铜**：SDRAM 组在剥光的板上先建，电源组和各局部组后建；不给 `TUNE_OBSTACLES`，蛇形会画到它们的线上（DRC 才发现）。迭代时在带全部组的板子副本上（先 `copper_report.py strip <副本> sdram`）用 `SDRAM_BOARD=<副本>` 跑 `--fast`，看到的空间和真板一样。
- **DRC 量网络长度时，拐点落在焊盘里的那一段算短了**：线在焊盘里折一下再到中心，DRC 量出来比几何短 0.01–0.07 mm（停点 7：`ETH_TX_N` 0.064、`PHY_XO_R` 0.063、`CAN_TERM` 0.043）。有长度规则的线（差分对、等长组）把拐点放到焊盘外；`busroute` 的长度判定只对有长度规则的网络卡 0.002 mm，其余列为备注。
- **差分对间隙检查把平行而不相邻的两段也当成耦合段**：`ETH_TX_P` 绕 RJ45 2 脚的 45° 小段和 `ETH_TX_N` 进 2 脚的 45° 斜线在投影上重叠 0.35 mm、相距 1.66 mm，报 `diff_pair_gap_out_of_range`（最大 0.8）。让两段的投影不重叠即可。
- **两个封装的 courtyard 正好贴边，DRC 报 `courtyards_overlap`，`place_check.py` 不报**（它按面积 > 0.001 mm² 算）：摆件留 0.02 mm 以上。
- **`busroute` 的快速检查读封装里的禁布区，也把同号的第二个焊盘当障碍**（2026-11-22 起；以前 RJ45 的屏蔽片只认一个、`Shield-board contact area` 不读）。封装里的禁布区在发现里叫 `位号:区名`。
- **基准板拷真板的 `.kicad_dru` 时要清掉 `len_rules.py` 的生成段**（2026-11-23）：生成段的窗口是按真板量出的长度算的（`sdram_addr_window` 按真板 SDCLK 39.34 mm 卡 `FMC_A*` ≥ 19.34），基准板上同名的网络落在窗口外，busroute 基准的蛇形各例因此报 `length_out_of_range: 1`（`FMC_A3`）。`tests/busroute/check.py` 的 `bench_dru()` 和 `rules_fixture.py` 的静态阶段都只留手写规则、生成段置空；基准要窗口就自己写。
- **蛇形块的弯数由补线位置的长度决定，要的量不到 n 个最矮的弯时会少画弯**（2026-11-24，H743 板 50 mil 等长）：`tune.py` 取“摆幅不低于 amp、正好补够”的最多弯数，要补 1.18 mm 时画一个 0.72 高的弯而不是两个 0.5 的（两个 0.5 的补 1.485）。规划里写了 n 个弯而量不够时，补线位置加 `humps=n`（`job.slot(..., humps=n)` / `Bundle.slot(..., humps=n)`，只用于单侧）：正好 n 个弯，摆幅按要补的量算、不低于 amp；不低于 amp 也多补时照画，多补多少记一条 NOTE（这根线会比目标长，DRC 的 skew 规则仍是判据）。基准 `tests/busroute/check.py` 的 humps 一例
- **`track_shape.py` 把同一直线上的两段（线宽变化处，规则区边外 0.3 mm）当成拐角**（2026-11-24 修正）：蛇形的第一个圆弧离线宽变化处不到 0.35 mm 时报 `sharp`。现在同向的两段不算拐角，基准 `tests/track_shape/check.py` 的 E 例
- **`track_shape.py` 以前遇到圆弧就断开走线**：拐点后 0.1 mm 接同向圆弧的地方报 0 处（RTE-8 的信号）。现在跟着圆弧走；四层板（有圆弧）只多一行 `arc-joint: 0`，其余各项不变，两块没有圆弧的板输出逐字相同（2026-11-22 对比）。
