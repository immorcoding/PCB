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

## 用 KiCadRoutingTools 时（两块测试板上的做法）

- 内层只做平面时给它 `--layers F.Cu B.Cu`。
- 手工铜皮要锁住：`route.py --no-pour <副本>` 写出的副本里手工铜皮是锁定的；另设 `KICAD_RIP_PREEXISTING=0 KICAD_FINALIZE_RIP=0`，加 `--keep-input-copper`。不这样它会拆掉手工走的差分对重走。
- 不让它缩尺寸：默认它会把过孔缩到 0.25 mm、线宽缩到 0.089 mm。用 `--escalation off --fab-tier standard`；`--same-net-pad-clearance 0.1` 禁止盘中孔。
- 0.5 mm 间距 IC 的扇出它在精确尺寸下过不了（四层板第一次 17/24）。把要换层的引脚用 0.45/0.2 过孔交错排成两三排，总线整组手工走，它只接过孔之后的长线。
- 分批跑，先走最受限的；一批失败的网络和它的邻居一起重跑（`--skip` 把它们从回放里去掉）。
- 每次导入结果后跑 `auto_clean.py`，全部走通后跑 `auto_tidy.py --clearance 0.13`，再 DRC，再 `track_shape.py`。它会用一串 0.2 mm 竖线加 0.035 mm 斜线拼出非 45° 的斜线，逐段的角度检查查不出来。
- 它的线头常停在过孔中心旁边 0.05–0.25 mm 处（靠铜皮重叠连通，DRC 不报），重走时接到中心。

## 已知的坑

- **`.kicad_dru` 语法错误会让整个文件静默失效**，细节见 [design-rules.md](design-rules.md) 的"已知陷阱"。
- **用户开着 KiCad 时改 `.kicad_pro` 会丢**：KiCad 关闭工程时用内存里的旧设置覆盖文件。工程目录下有 `~*.lck` 说明 KiCad 正开着。
- **pcbnew**：`board.Remove()` 之后，同一进程里 `board.Zones()`、`GetFootprints()` 等集合会返回无类型对象，访问即报错或崩溃。先读完需要的数据再删；删完还要继续读就另起一个进程（同一进程里重新 `LoadBoard` 也不行，参考 `steval_fcu001v2/silk.py` 的 `--strip`）。
- **`route.py` 会清掉泪滴**，所以泪滴放在走线和铺铜定稿之后。
- **删掉封装自带的丝印外框、打开"允许阻焊桥"**，每个封装各多一条 `lib_footprint_mismatch`，在审查清单里说明。
- **Git Bash 会把 `/` 开头的网络名改写成路径**：传网络名的命令前 `export MSYS2_ARG_CONV_EXCL='*'`。
- **Shell here-doc 会改写反斜杠和 `\n`**：补丁脚本用文件写，不用 here-doc。
