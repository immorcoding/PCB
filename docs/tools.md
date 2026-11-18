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
| 原理图构建并检查 | `sh scripts/sch_build.sh <工程目录> <输出目录>`（生成 → 升级到 KiCad 10 格式 → ERC → 网表 → PDF） |
| DRC | `kicad-cli pcb drc --refill-zones --severity-all`；收尾时加 `--schematic-parity` |
| 重新填充铺铜并存回板文件 | `kicad-cli pcb drc --refill-zones --save-board --severity-all --format json -o <报告> <板>`；之后的测量和出图直接读板文件里的填充，不在 pcbnew 里再填一次 |
| 检查本地 HTML 页面 | `"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --headless=new --window-size=1500,1900 --screenshot=<png> "file:///<路径>"`，再看截图 |
| 线形检查 | `scripts/track_shape.py <板>` |
| 四层板一次构建 | `sh steval_fcu001v2/build_pcb.sh <报告目录>`（`place.py` → `route.py` → `silk.py` → 泪滴，顺序不能换） |

## `scripts/` 下的工具

| 脚本 | 用途 |
|---|---|
| `kisch.py` | 生成原理图：从官方符号库取符号、按引脚坐标连线。每个工程一个 `gen_sch.py`，参考 `stm32f411_minsys/gen_sch.py` |
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

`kisch.py` 现在只能写单张平铺的图。H7 测试板要给它补分页：多张图纸靠网络标号连通的平铺设计，不做层次图（用户 2026-11-18 定，还没写）。

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
- **厂商网站对自动下载的限制**（2026-11 实测）：TI、Winbond、Vishay 的 PDF 用 `curl` 能直接下；ST 的 PDF `curl` 拿不到，用 WebFetch；ISSI 返回占位页（反爬），Micron 和 Winbond 的零件页是 JS 渲染、读不到；Microchip、Hirose、Würth（we-online）、sdcard.org 对 `curl` 和 WebFetch 都返回 403。拿不到的不绕过，列出官网地址请用户手动下载到板目录的 `datasheet/`（不提交）。
- **`kicad-happy:digikey` 需要 `DIGIKEY_CLIENT_ID` / `DIGIKEY_CLIENT_SECRET`**，环境里没有，在产状态和库存查不了。
- **多列表格的 PDF 文字层会错列**（TI 订货表把 TPS62A02PDDCR 读成别的封装）：表格渲染成图读，`pdftotext` 只作核对（PROC-14）。ST 的 Altium 导出原理图，文字层里网络名和位号是乱的，同样处理。
- **Git Bash 会把 `/` 开头的网络名改写成路径**：传网络名的命令前 `export MSYS2_ARG_CONV_EXCL='*'`。
- **Shell here-doc 会改写反斜杠和 `\n`**：补丁脚本用文件写，不用 here-doc。
