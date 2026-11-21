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
| H743 板按步骤构建 | `sh stm32h743_sdram/build.sh rules`（工程文件、规则基准板、金丝雀、规则匹配；1.5–3 分钟） |
| 铜皮区域草图 | `D:\KiCad\bin\python.exe scripts\cu_sketch.py check <草图> [--board <板>]`，另有 `apply`（按草图写铺铜区，只动它自己建的 `cu:` 开头的区）、`read`（从板读回草图，PWR-7）、`measure`（铜皮那组指标）。草图格式见脚本开头和 `stm32h743_sdram/copper.sketch` |
| 总线走线（线束、BGA 扇出） | `D:\KiCad\bin\python.exe scripts\busroute\build.py <走线描述.py> [--fast] [--sketch] [--out 目录] [--write-board]`。默认在 `--out` 下的板子副本上构建，加 `--write-board` 才写真板；`--fast` 只做几何检查（57 根不到 1 秒），完整构建含 DRC、长度、指标、图片（7–14 秒）。描述文件的格式见 `scripts/busroute/job.py` 开头，例子是 `scripts/tests/busroute/bench_routes.py` |
| 摆位 | `D:\KiCad\bin\python.exe stm32h743_sdram\place.py`；`--pcb <副本> --rot <角度>` 在副本上试别的 SDRAM 转向 |
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
| `track_shape.py` | DRC 不查的走线形状：非 45° 线段、阶梯线、小倒角直角、短距离连续折弯、碎线段 |
| `pour_islands.py` | 找没接到网络上的铺铜碎片 |
| `silk_refs.py` | 自动摆位号，稀的板子用；密板把标注坐标写在工程的 `silk.py`（参考 `steval_fcu001v2/silk.py`） |
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
| 等长 | 每组在窗口内的根数、最差一根差多少、每根总长对上限、蛇形块数和补的总长 |
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
- **孤岛的判定只看焊盘**：一块填充所在的铜上没有焊盘就算孤岛，只有过孔不算；“总是移除孤岛”只在同一个区另有连通的块时才删。
- **新建 `ZONE()` 的默认值**：间距 0.5 mm、最小宽度 0.25 mm、花焊盘间隙和辐条 0.5 mm、移除孤岛。脚本建区要逐项写明。
- **`kicad-cli` 的 DRC 报告最多列 499 条未连接**：没布线的板子上别从报告里数某一组的未连接（H743 板 pcbnew 数出来是 633 条）。
- **KiCad 10 的板文件里走线和过孔按网络名记**（没有网络表），可以当文本增删；`busroute` 就是这样写板的，其余内容逐字节不变。
- **规则区内 0.30 / 0.15 的过孔，中心距至少 0.425 mm**：卡住的是孔到铜（0.075 + 0.15 + 0.2），不是焊盘间距。
- **`pcbnew` 的 `GetLayerName` 返回的是自定义层名**（`L2_GND`），文件里是 `In1.Cu`。
- **`kicad-cli` 的控制台输出不是 UTF-8**：`subprocess.run(..., text=True)` 会在读线程里解码出错，按字节取。
- **`place.py` 这类脚本里 `board.Remove()` 要放在所有读取之后**：第二次运行时先删旧板框再遍历铺铜区会段错误（上面那条 pcbnew 的坑的又一例）。
- **Git Bash 会把 `/` 开头的网络名改写成路径**：传网络名的命令前 `export MSYS2_ARG_CONV_EXCL='*'`。
- **Shell here-doc 会改写反斜杠和 `\n`**：补丁脚本用文件写，不用 here-doc。
