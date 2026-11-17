# tutorials-en：英文教程、博客、课程与论坛里的"布线 + 等长配合"参考

范围：英文教程、博客、课程资料、论坛帖。目标是找资深工程师在 BGA 处理器与存储器之间如何协调走线和等长（蛇形线放哪、留多少空间、什么时候决定）。

**先说结论（诚实评估）：这个角度偏薄。** 有真实板子截图的来源是三个：ThunderScope FPGA 模块（Hackaday.io）、FEDEVEL 论坛的 Artix-7 + DDR3 帖、Robert Feranec 的 Altium 客座博客。【复查更正】原来写的"又附带资深工程师评论"不准确：只有第三个（Feranec 自己的开源设计 iMX6 Rex）出自资深工程师之手。ThunderScope 日志作者自称这是他"第一个带大 BGA 和 DDR3 的设计"（原文 "my first design with a big BGA part and DDR3 memory"），日志里没有引用第三方对版图的评论；FEDEVEL 帖的发帖人自称 "it my first DDR3 design"（2019-08-09），评论里 Feranec 只谈扇出、摆放和线宽，没有评蛇形线本身，Paul van Avesaath 的资历页面没写。所以 01 到 05、12 只能当"这类布局长什么样"的形态参考，不能当"资深做法"的证据；Feranec 的图（06、07）讲的是层与过孔的规划，不是蛇形线。其余是工具厂商博客的示意图、芯片厂应用笔记的版图图，以及一篇讲蛇形线几何的经典文章。没有找到"两颗芯片只隔几毫米、0.65 mm BGA 对 0.8 mm BGA"的带图实例，只找到一篇文字版的近似案例（FEDEVEL 7946）。

标注约定：
- **【图中所见】** 我用 Read 工具看过图后的描述，只写看到的。
- **【原文】** 来源页面上作者的原话（短引用，英文原样）。
- **【推断】** 我自己的判断，不是来源说的。
- 图上量出来的数字都是目测估计，已标"估计"。没有比例尺的图不给毫米数。

下载的原始页面、HTML 文本、未入库图片在
`C:/Users/22137/AppData/Local/Temp/claude/e5c1c9180d588be6/2f055cfe-5936-4fc3-83bf-239216ba1437/scratchpad/refs/tutorials-en/`（img1 到 img7、html、txt、dl-icd1、dl-icd2）。其中没有执行过任何下载内容。

## 图片清单（本文件夹内，共 13 张，均小于 1.5 MB）

| 文件 | 来源 | 内容 |
|---|---|---|
| 01-thunderscope-inner-tuning-pocket.png | A | 两个内层视图并排：金色走线层 + 带铜区的层，蛇形块位置 |
| 02-thunderscope-top-and-bottom.png | A | 红色层与蓝色层并排（推断为顶层与底层） |
| 12-thunderscope-dual-chip-branch-via-field.png | A | 顶/底两颗 DDR3 的焊盘区与到过孔场的分支线（原图 542x191，放大 3 倍，偏糊）。【弱：看不出分支已做等长】 |
| 03-fedevel-artix-ddr3-nested-lanes.png | B | 早期粗连线：同心嵌套的绕行通道。【注意：作者说这只是评估摆放的粗略走线，等长还没开始，不是调长方案】 |
| 04-fedevel-artix-ddr3-serpentine-pocket.png | B | 存储器与 BGA 之间塞满多块蛇形线。【发帖人自称首次做 DDR3，非资深作品】 |
| 05-fedevel-artix-ddr3-second-layer.png | B | 地址 + Bank0 第二版，带评审意见。【同上，新手作品；评审提了两点意见：旋转芯片缩短总长、别把长度调在 FPGA 下面】 |
| 06-feranec-imx6rex-layer-flow.png | C | 一组信号的层转换示意（L1 到 L10 到 L11 到 L12）。【弱：缩略示意图，只有 Layer 10 上有一点波浪线】 |
| 07-feranec-imx6rex-outside-groups-layer3.jpg | C | 带批注的 DDR3 扇出后布线图（外侧组走 L3、近侧组走 L10） |
| 08-altium-accordion-parallel-bus.png | D | 并行总线上的 accordion 蛇形块（厂商教学截图，板子不明） |
| 09-altium-sawtooth-and-trombone.png | D | sawtooth 尺寸示意 + trombone 交互调整截图（厂商教学图，非实板） |
| 10-altium-ddr4-channel-two-chips.png | E | BGA 到两颗 DDR 的通道，标了 ADDR / DQ。【偏弱：938x639，蛇形线属哪一组看不出；页面无图注，板子来源未说明】 |
| 11-microchip-an4598-ddr3l-addr-and-data.png | F | Microchip 应用笔记的 DDR3L 地址控制层与数据字节通道 |
| 13-johnson-serpentine-layout-tradeoffs.png | G | Howard Johnson 的蛇形线 a/b/c/d 四种形态（原图 229x228，放大 4 倍）。【示意图，不是实板】 |

---

## A. ThunderScope FPGA 模块（Hackaday.io 日志）

- 标题：FPGA Module: Extreme Artix Optimization（项目日志，ThunderScope 开源示波器）
- 网址：https://hackaday.io/project/180090/log/205329-fpga-module-extreme-artix-optimization
- 作者：Aleksa（日志日期 2022-04-25）
- 许可：页面未声明。项目自称开源，但这个日志页面没写许可条款，只作内部参考。
- 图片：01、02、12。另有一张整板照片 hd_top.jpg（2413x2650，1.3 MB）没入库，在 scratchpad 里。
- 板子/总线：Artix-7 CSG325（原文写明），一个 x32 DDR3L 接口，由两颗 DDR3 芯片构成（原文只说 x32 接口和两颗芯片；"每颗 x16"是我按位宽推的。复查：页面写的是被替换的第三方模块 "had two x16 DDR3 memory chips"，新设计只写 "a x32 wide DDR3L interface"，新板每颗是否 x16 页面没直接写）。层数：日志文字没提。GIF 的 6 帧我复查时逐帧看过，依次是红（顶）、整片绿（像地平面）、金色信号层、分割彩色铜区加灰色线束的混合层、整片绿、蓝（底），符合"顶底加四个内层共 6 层"的读法，但帧上没有层名，仍是推断。
- 相关度：高。唯一一个有完整多层图、BGA 与存储器靠得近的真实例子。【复查：对"布局形态"相关度高；但作者自称这是他第一个带大 BGA + DDR3 的设计，日志里没有引用第三方对版图的评论（页面标有 "1 Comment"，内容我没核对），所以不能当"资深做法"的证据。】

**图中所见**
- 01 左半（金色走线内层）：数据线从上方中部的存储器区出发，分成左右两束，绕外圈嵌套的同心通道（45° 折角、通道间距看着均匀）下到下方中部的 FPGA 区。左束里面有一整块并排的细小 accordion 蛇形线，同一列、同一节距，像一个长方形"方阵"，外侧还有几条宽的圆角 S 形回环。这一块沿着存储器球区与 BGA 球区之间的竖向空档展开：主体在两者中间，但上缘离存储器球区只隔一两个过孔间距，下缘靠近 BGA 球区上沿（复查时放大 2 倍看过，原来写的"不在存储器脚旁边"说得太满）。右束的中外圈通道上有细密的涟漪形蛇形线，最外一圈基本平直，内圈较短的通道上也有 accordion 块。我读到的大意是：最外圈长通道基本是平的，蛇形线集中在内侧较短的通道上，但右束的蛇形并不只在内侧（这是看形状得出的，没有逐网络核对）。
- 01 右半：和左半是不同的一层（对照 GIF 第 4 帧：这一层本身就同时有分割的彩色铜区和灰色线束，所以铜区和线束是同一层，不是叠加显示）。灰色线束穿过铜区里的一个缺口，蛇形块落在缺口里。缺口的边是 45° 的、紧贴线束外圈，这和"铺铜时自动避让走线"看起来一样，所以不能据此说缺口是事先预留的。
- 02 左（红色那层，按颜色和日志"一颗在顶、一颗在底"推断是顶层；图上没有层名）：BGA 在下方中部，上方是存储器焊盘区，两者之间的间隔很小（没有比例尺，不给毫米数）。BGA 左侧有一列很窄很高、非常密的 accordion 蛇形块；右侧有圆弧角的蛇形块。02 右（蓝色那层，推断是底层）：外圈有嵌套通道，中部有一小段蛇形线。
- 12：左红（顶）右蓝（底），两边的存储器焊盘区位置基本重合（背靠背；焊盘图案是否镜像我无法确认，两面分支的走法也不同）；中间两排带钻孔的大过孔就是"过孔场"，球焊盘的分支线连到这些过孔。图里看得到分支布线，但看不出每根分支已经做过等长（没有蛇形线），原图又只有 542x191，所以只能当"背靠背加过孔场"的示意，弱参考。
- 蛇形线的几何：腿近似竖直，圆角或小 45°。腿间隙：复查时我按像素量了 01 里的密 accordion（线宽约 2 px，相邻腿净间隙约 5 px），约 2 到 2.5 倍线宽；原来写的"1 到 1.5 倍"偏小。图是缩小的截图，误差大约一半，只能当量级参考，不能当规则用。【第二次复查用像素扫描重量：01 左束密 accordion 竖向扫描，线宽 2 px，腿间净间隙多为 3 到 4 px、个别 6 px，约 1.5 到 3 倍线宽，典型约 2 倍；上面"约 2 到 2.5 倍"略偏大，仍只是量级估计。】

**来源文字（原文）**
- "I accomplished this by placing the two DDR3 chips in the same location, one on the top and one on the bottom. I then length matched each trace on both sides (the branches) to a field of vias and brought all the signals out to the FPGA on another layer."
- "This diagram shows the way I routed the non-data signals (all data signals have on-die termination and don't branch out). Each branch of the tree must have equal lengths as well."
- "The rest of the data signals just needed some length matching, though it was tough to fit all those signals in to each layer!"
- "it was time to layout my first design with a big BGA part and DDR3 memory!"

**对照七个观察点**
1. 调长位置：【图中所见】数据线蛇形块在存储器和 BGA 之间的竖向空档里（内层，那一层的铜区有一个缺口），不紧贴球焊盘，但两端离球区也只隔一两个过孔间距。命令/地址分支则是在两颗芯片的分支处就匹配到过孔场（原文）。
2. 留空间：【图中所见】存储器与 BGA 之间有一整片空档给通道和蛇形块；铜区在那一层有一个缺口让线束通过。【推断，证据偏弱】作者可能是布局时就留了位置，但缺口也可能只是铺铜后自动避让，图上分不出，原文也没提留空间。
3. 绕行与蛇形：【图中所见】两者并用——外圈通道本身就是"绕远路"，内圈短线再加蛇形。
4. 相邻蛇形线：【图中所见】同一块里并排、同节距、对齐成方阵；不同组的块大小不同。
5. 几何：见上，只有估计值。
6. 工作流：来源只说明了"两颗芯片背靠背，分支各自匹配到过孔场再引出"，没写布线顺序或目标长度怎么定。
7. 紧凑情形：存储器离 FPGA 很近。【推断】作者能靠绕外圈拉长，说明他事先留出了绕行的空间；但原文没提这点。【复查补充，估计】01/02 的存储器球区下缘到 BGA 球区上缘，按 BGA 过孔节距约 17 px 当作 0.8 mm 球距反推比例（约 21 px/mm；CSG325 的 0.8 mm 球距是我按封装规格取的，日志里没写），间隔约 120 到 140 px，即约 5 到 7 mm；球区边界是目测，误差可达两成，只能说是"几毫米量级"，不能当尺寸引用。

---

## B. FEDEVEL 论坛：DDR3L rules and constrains confirmations（Artix-7 + 一颗 DDR3）

- 标题：DDR3L rules and constrains confirmations（2019-05 至 2019-08）
- 网址：https://fedevel.com/forum/your-projects/10831-ddr3l-rules-and-constrains-confirmations （courses.fedevel.com 上有镜像）
- 作者：发帖人 Mihai（用户）；评论人 Paul van Avesaath、Robert Feranec（FEDEVEL 创始人）
- 许可：页面未声明，用户论坛帖。
- 图片：03（帖中 photoid10886，2019-05-20 发）、04（photoid10924，2019-05-21 发）、05（photoid11601，2019-08-09 发）。另有未入库：id10876（iMX6 DDR3 长度匹配示意图，见下）、photoid10937（UG586 截图）、photoid11600（11601 的缩略版）。
- 板子/总线：发帖人称用 Artix-7 FPGA，一颗 256x16 的 DDR3，16 位数据，点对点，8 层叠层（原文；同帖 2019-05-24 原话 "8 Layer stack-up (with 2 inner signal layers)"，即只有 2 个内层信号层）。BGA 封装没写；图里是一个大球阵。
- 相关度：高（形态参考）。有三个阶段的真实截图，加上评审人的点评。【复查更正：原来写"资深人员的点评"过头。发帖人 Mihai 在 2019-08-09 自称 "it my first DDR3 design, the next one will be better"；Paul van Avesaath 说 "That looks excellent" 是同行评语，页面没写他的资历；Feranec（FEDEVEL 创始人）的回复只涉及扇出、摆放、线宽和参考板，没评蛇形线。所以 03/04/05 是新手作品，能看"调长块长什么样、塞在哪"，不是最佳实践。】

**图中所见**
- 03：从左下 DDR3 球区向上翻到上方、再向右下接到右侧 BGA，共 8 条金色线（我在图中同一竖线上数到 8 条）。其中 6 条是一条套一条的同心嵌套长通道，没有交叉，45° 折角，通道间距均匀（中心距约 40 像素对线宽约 6 像素，估计约 6 到 7 倍线宽）；另 2 条在右上、较短，其中一条只有两个小凸起（几乎没有蛇形线）。中间留着一大块空地。发帖人自己说这只是评估摆放用的粗略走线，原帖（05-20）："This is just a basic routing, to have an idea how the tracks will be arranged. After I am decided with the placement, I will start with the routing and the length matching"。所以 03 里的嵌套通道不是调长方案，长度差异并没有被调过；原来写的"靠绕道区分长度"是我的误读，已删除。
- 04：同一对芯片的下一版。存储器（左）和 BGA（右）之间被塞进至少 6 个独立的蛇形块，方向有竖直、有 45° 斜向，大小不一，上排有一排很多腿的窄蛇形线，中部有四个上下叠在一起的竖直蛇形块（复查时数到 4 个，原来写 3 个）。整体看是"见缝插针"，不是一整块对齐的方阵。像素量取：线宽约 5 到 6 px，相邻腿净间隙约 12 到 13 px，约 2 到 2.5 倍线宽（这是本文件夹里较可靠的一处几何量，但仍是估计）。
- 05：绿色单层。存储器焊盘区（标 U33）在左，BGA 在右，走线绕过左下角，外圈有一圈约 10 条的嵌套通道，通道上沿底边有一排排的小齿形蛇形线；中部有一个梳状竖直蛇形块。

**来源文字（原文）**
- Paul（针对 04）："That looks excellent.. i usually do the address and command lines first because they are not interchangable like the DQ's so keep that in mind.. also address and cmd lines are slower than the rest.. so can have more tolerances and are not that critical in choosing different layers to route on.."
- Paul（针对 03）："Try to keep all signals on the same layer. ... You may swap the dq0 - dq7 in any order you want to make that happen...."
- Feranec："routing 95% of BGA is simple, but last few pins can be extremely hard or impossible to connect. Be sure, you will be able to fan out the pins in the area where you route the memory signals - otherwise you may end up in situation when you will need to delete or re-do a lot of already finished layout."
- 发帖人："I have redone the DDR3 layout over 10 times, to find a nice placement and a good pinout with low skew."
- 发帖人："I am thinking for a better placement to keep the tracks smaller than 5 cm."
- 发帖人引用 UG586：地址线 "swappable within a byte group of the FPGA I/O bank"（他的转述）。
- Paul（针对 05）："nice work!, but looking at it I do get te feeling you could rotate your ddr chip 90 degrees , this way your overal length will be shorter.. also routing the length of one of your signal beneath the FPGA / uP is not a wise thing to do unless you do not have any other option.. this wil really restrict your rouitng options on that layer.."
- Feranec 的线宽（05-27，回答发帖人关于 OpenRex 的问题）："inner layers 0.12, outer layers 0.114"（mm，叠层表另附）；这是 50 欧阻抗线宽，和蛇形几何无关。发帖人自己的 8 层叠层算出 0.16 mm（内层）和 0.35 mm（外层），并说他在信号之间设了 0.25 mm 的净距（"I have established a clearance of 0.25 mm between each signals"，06-12），是一般线间距，不是蛇形专用。

**对照七个观察点**
1. 调长位置：【图中所见】在存储器和 BGA 之间的中段，用地方就塞。评审人的态度：不要把长度调在 FPGA 下面。
2. 留空间：评审意见集中在"先保证扇出有位置"和"换芯片朝向缩短总长"。【推断】这说明评审人（Feranec；Paul 的资历页面没写）把空间视为布局阶段就要定的东西。
3. 绕行与蛇形：03 靠绕行，04/05 靠蛇形，两者并用。
4. 相邻蛇形线：04 是不规则的多块；05 是通道上的齿形加一个梳状块。
5. 几何：只有线宽 0.12/0.114 mm 和 0.25 mm 间距这类原文数字；蛇形几何没有数字。
6. 工作流：【原文】地址/命令先布（不可互换）；DQ 位可在字节内任意交换；同一组尽量同层；引脚和位置反复迭代。
7. 紧凑情形：发帖人为了缩短总长，反复迭代布局十几次，并接受评审建议旋转芯片。

**顺带：iMX6 DDR3 长度匹配示意图**（https://assets.fedevel.com/blog/2019/10/c298e-imx6-ddr3-length-matching.jpg ，另见 https://home.fedevel.com/blog/ddr3-length-matching-rules ，FEDEVEL 自制，注明依据 iMX6 设计指南；未入库，在 scratchpad/img1）。【图中所见，复查时重新对过图】时钟 "Clock (min)"（±5 mils）是参考长度；命令/地址/控制组落在 "Clock (min) - 200 mils" 到 "Clock (min)" 之间，组内 ±25 mils；数据组相对时钟 "Not defined"，只管组内 ±25 mils、DQS ±10 mils。注意这是 T-branch 拓扑的 iMX6 专用图（FEDEVEL 页面写明依据 iMX6 设计指南），不能直接套到别的处理器上。数据组长度没有绑定时钟，原来写的"其他组相对时钟留差"对数据组不成立。

---

## C. Robert Feranec：How to Route DDR3 Memory and CPU fan-out（Altium 客座博客）

- 标题：How to Route DDR3 Memory and CPU fan-out
- 网址：https://resources.altium.com/p/how-to-route-ddr3-memory-and-cpu-fan-out
- 作者：Robert Feranec（FEDEVEL）；创建 2017-02-21，更新 2020-11-04
- 许可：页面正文未见许可声明，Altium 站点内容，视为版权所有，仅内部参考。
- 图片：06（原文图 1）、07（原文图 7，批注图）。其余图 2 到 6 没入库，在 scratchpad/img7 里（图 5、6 是 via 与扇出空间的批注图）。
- 板子/总线：iMX6 Rex（i.MX6 + DDR3，文中提到走到 L12，所以是多层板）。
- 相关度：中高（复查：这是本文件夹里唯一明确出自资深工程师本人板子的图，页面导语写 "based on his open-source hardware design of the iMX6 Rex"；但文字只讲层与过孔规划，没有讲调长，"布线和调长一起决定"这一层是我的推断）。不是讲蛇形线本身，而是讲"事先规划各层空间，使扇出和调长都不出意外"，正好对应用户说的"布线和调长要一起决定"。

**图中所见**
- 06：四张缩略图排成一行：Layer 1（Top）、Layer 10、Layer 11、Layer 12（Bottom），黄圈和箭头标出同一组信号从一层到下一层的路径。Layer 10 上是一束斜向的线，带小的波浪形蛇形线；Layer 11 和 Layer 12 只剩过孔圈，没有走线。原文图 1 说明里的组名是 "DATA 6 Group"。图很小，是弱参考，只能说明"同组走同样的层转换"，看不出调长安排。
- 07：青色走线，约 45° 的并行通道。图上有三个黄色椭圆、两个文字框（文字是图片自带的，页面正文里没有对应的图注；图 7 的页面图注是另一句，见下）："These 'outside groups' are routed on layer 3, because there is no room for them on layer 10." 和 "The tracks of the 'closest groups' are routed beneath the Address, Command and Control groups on layer 10."。中间一圈有两块圆角 accordion（各 4 到 6 条腿），上方有几处波浪形和大 U 形折返。蛇形线既有在通道中段的，也有紧挨着球区出口的（上方椭圆里的大圆弧折返离焊盘只有几个焊盘间距），所以不能说"蛇形线都不在球区边上"（原来写的"不在球区边上"已删除）。这两个批注讲的是层分配（哪组走 L3、哪组走 L10），不是调长位置。【复查补充】两条批注的箭头在图中交叉：第一个框（outside groups）的箭头指向上、下两个椭圆，第二个框（closest groups）的箭头指向中间椭圆，这个对应关系是我从箭头方向读的，不完全确定。中间那块蛇形线属于哪一组、在哪一层，图和页面文字都没说。页面把这张图（图 7）的用途写成"地址/命令/控制组走 L3 微孔后，L10 在它下面腾出空间给 closest groups 扇出"，所以图的重点是留空间，不是调长；图里蛇形线的存在只是顺带可见。

**来源文字（原文）**
- "It is recommended that all the signals which belong to the same group should be routed 'the same way' ie using the same topology and layer transitions."
- "One of the advantages of DDR routing the signals this way is that during length tuning (a.k.a. delay or phase tuning) the z-axis length in the vias may be ignored."
- 图 5 说明："Two or three tracks can fit between microvias, in the same space needed for one track between Through Hole Vias."
- 图 7 说明："Free space left under groups routed with microvias can be used to fanout the 'closest groups'."
- 结语："By a bit of care and planning ahead, routing and length tuning DDR3 fanouts can be a stress-free process, even on the most compact and densely packed design guidelines."

**对照七个观察点**
1. 调长位置：图 7 里中段和球区出口附近都有蛇形线；文字没有讲调长放哪、为什么放那里。
2. 留空间：这是这篇的重点——【原文】用微孔 vs 通孔决定每层剩多少空间；一对过孔之间能走几根线（两三根对一根）。
3. 绕行与蛇形：没有讨论。
4. 相邻蛇形线：图里是局部、并行通道里的小块。
5. 几何：无数字。
6. 工作流：【原文】先按组命名网络类、给每组上色、再做扇出规划（决定每组走哪层、用什么过孔），然后才布线和调长；同组信号过孔转换一致，所以调长时可以忽略过孔的 z 向长度。
7. 紧凑情形：文中标题就是 "very high density and tightly packed"；对策是把层和过孔先规划好。

---

## D. Altium：Length Matching for High-speed Signals: Trombone, Accordion, and Sawtooth Tuning

- 网址：https://resources.altium.com/p/length-matching-for-high-speed-signals-trombone-accordion-and-sawtooth-tuning
- 作者：Zachariah Peterson；创建 2019-11-03，更新 2023-03-10
- 许可：页面正文未见许可声明，视为 Altium 版权，仅内部参考。
- 图片：08（并行总线上的 accordion 截图）、09（sawtooth 尺寸图在上，trombone 交互调整截图在下）。
- 板子/总线：08 没写是哪块板，文字说 "typical example is DDR"。09 同样是通用示意。
- 相关度：中。是工具厂商的教学图，价值在几何和"蛇形线放哪不重要"这一句。

**图中所见**
- 08：黑底绿线。一束大体水平、带 45° 折角的并行总线，左侧中部有成对的金色过孔竖向排列。每根线上有一段 accordion，蛇形块放在上下相邻的过孔对之间的空档里，并且各块的横向位置错开；各行腿的高度不一（复查时按行粗量，原图约 80、50、60、70 px，没有"越往下腿越高"的规律，原来这句不成立，已删除）。右侧另有一束 45° 斜向的块。腿间隙：线很细（约 1.5 px），相邻腿间隙约 7 px，约 4 到 5 倍线宽；原来写的"1.5 到 2 倍"偏小。图是缩小的截图，误差大，只是估计。【第二次复查像素扫描：线宽 1 到 2 px，腿间净间隙 6 到 7 px，约 3.5 到 5 倍线宽，与上面基本一致；这是教学截图里腿间距很松的例子，和 FEDEVEL 04 的约 2 倍相差明显。】
- 09 上：sawtooth 示意，一根线上有三个梯形凸起，旁边是另一条直线；标注 "<3w"（凸起顶部的宽度）、"2s"（凸起高度）、"w"（线宽）、"s"（线间距）。这是全文唯一明确的几何数字。
- 09 下：trombone 的交互调整截图，紫色走线。前景有一个正在调的白色选框，里面是几个带 45° 外角的 U 形回环；上部是已经调好的邻线，齿高不一。

**来源文字（原文）**
- 关于并行总线："This method is often found in applications involving a parallel bus of many single-ended signals; the typical example is DDR. ... Therefore, it does not matter where we put the length tuning sections as the receiving component does not distinguish between differential-mode and common-mode noise."
- 关于间距："you should be careful not to place each section of a serpentine length matching section too close together."
- sawtooth："there is an 'S-2S' rule ... this was originally intended to ensure that 45-degree bends are used"；以及 "the length of the extended portion of the sawtooth could range from W to 3W, although some guidelines differ on this rule."
- trombone："it will create much more NEXT than accordion or sawtooth length tuning."

**对照七个观察点**
1. 调长位置：【原文】单端并行总线上"放哪里无所谓"（指电气上）。这句话只讲电气，没讲空间怎么分配。【复查：该句的理由是"这些线不是差分对，线对之间没有精确相位要求，接收端分不出差模和共模噪声"，即不必像差分对那样担心模式转换；同一页仍要求别把蛇形段靠太近，并警告 trombone 的 NEXT 更多，所以不能读成"放哪儿都行"。】
2. 留空间：未讨论。
3. 绕行与蛇形：未讨论。
4. 相邻蛇形线：08 是并排错位的块；文中只说别靠太近，没给数字。
5. 几何：sawtooth 的标注（<3w、2s）是唯一数字；其余是估计。"<3w""2s"只在图里，页面文字里没有这两个标注；文字写的是 "W to 3W" 和 "S-2S" 规则，页面图注是 "the 3W rule"，和图一致（我看图确认了标注存在）。
6. 工作流：只有"用哪种形状"的选择表，没有布线顺序。
7. 紧凑情形：未讨论。

---

## E. Altium：PCB Routing Guidelines for DDR4 Memory Devices

- 网址：https://resources.altium.com/p/pcb-routing-guidelines-ddr4-memory-devices
- 作者：Zachariah Peterson；创建 2018-06-20，更新 2021-05-14
- 许可：同上。
- 图片：10（原文 ddr4-channel-1.png）。同页另有 SODIMM 图 sodimm-2.png 没入库。
- 板子/总线：图上标了 DDR1、DDR2 两颗存储器；总线为 DDR4。
- 相关度：中。图是 BGA 到存储器的一段通道，标了 ADDR 与 DQ 各自占的区域。

**图中所见**
- 青色走线为主，大 BGA 在左，右边是两个洋红色框的存储器封装，标 DDR1、DDR2，右上还有一列电阻/电容类小封装，标 ADDR。DQ 标签在中上部。DQ 标签附近有一束线，从 BGA 右缘出来，绕过中上部一个圆角矩形的大弯，再向右下去往两颗存储器一带（具体接哪颗从图上看不清）；束的上部（右上）有一块梳状的蛇形线，但它属于 DQ 还是 ADDR 那一束，图上看不出；DQ 标签旁的回环里有一个窄长的发夹形折返；下方靠近 DDR2 处有波浪形线段。DQ 标签上方有一小块没有走线的暗色空地（回环内侧），不是 BGA 与存储器之间的整片空地。这张图没有图注（alt 文字是 "DDR4 routing channel"），页面正文把它称为 "a good example"（CLK、DQ、ADDR 一个字节组）。

**来源文字（原文）**
- "It's a good strategy to plan out the space required on multiple layers, and make sure to route the DQ, DQS, and DM signals within a given byteline group on the same layer to avoid layer-to-layer propagation delay differences."
- "Placing everything on one layer allows you to define a specific trace width to ensure fixed impedance. In addition, this helps with length matching across the bus as all your signals will have a definite propagation delay on that specific layer."
- 关于偏差："Some datasheets will specify something like 1 mm length tolerances ... It's best to play it safe and just timing match as close as possible across the bus."
- 关于间距：（复查：原文说 5H 是 "A very conservative practice"，即很保守的做法，不是硬性规则）CLK 对与其他线至少 5H，地址/命令/控制与 DQ/DQS/DM 可放宽到 3H（H 为到最近参考面的垂直距离）。

**对照七个观察点**
1. 调长位置：【图中所见】在通道中段、绕行束里；没有文字说明理由。
2. 留空间：原文只说"提前规划多层所需空间"，没有给量。
3. 绕行与蛇形：图里 DQ 束先绕再蛇形。
4. 相邻蛇形线：图小，不好判断。
5. 几何：间距用 H 的倍数（5H / 3H），不是用线宽。
6. 工作流：同一字节组同一层；先规划空间。
7. 紧凑情形：没有。

---

## F. Microchip AN4598：3.4.2 Implementation Example for DDR3L

- 网址：https://onlinedocs.microchip.com/oxy/GUID-65098DF5-BE35-4370-98B0-7001ABCC6086-en-US-1/GUID-B54F77F1-2BF9-4892-B052-D23FE51AFBB4.html
- 作者/机构：Microchip（页面头部标 SAMA7G54、AN4598）
- 许可：页面只说 "The online versions of the documents are provided as a courtesy"，没有再用许可。仅内部参考。
- 图片：11（左：图 3-9 地址与控制；右：图 3-10 数据字节通道）。
- 板子/总线：【复查更正】SAMA7G54 只出现在页面头部；正文是通用的 16 位 DRAM 点对点要求（原文 "When routing a 16-bit bus width DRAM interface, it is recommended to use 16-bit memory devices." 和 "The single memory device should be routed in a simple point-to-point topology."），没有写图里就是哪块板。
- 相关度：中。是芯片厂的参考版图，可能和别的角度（厂商应用笔记）重复。

**图中所见**
- 两幅图里 MPU 球阵都在右上角（右上角有标签 "Room-MPU"），存储器的焊盘在中偏左下，是两列竖排的红色焊盘。
- 左（地址/控制，蓝线）：线从右上角出来，沿上边向左，再沿左边向下，形成层层嵌套的矩形通道（外圈更长）。内圈较短的线带有宽而长的水平 accordion。
- 右（数据）：字节通道 0（金色）和字节通道 1（洋红）各占一层（【复查：推断，未证实】页面只说图 3-10 画的是字节通道 0 和 1，没说哪条通道是哪种颜色、在哪一层；金色对应通道 0、洋红对应通道 1、"各占一层"都是我按颜色不同读的）。金色那组在左侧，是一排长度逐条变化的水平 U 形条，像楼梯一样一级一级地缩短；洋红那组在右侧，是沿竖向通道一节节堆叠的 accordion（腿是水平的）。图 3-9 / 3-10 的页面图注（"DDR3L Address and Control" / "DDR3L Data Lanes"）已核对。
- 总线走的是"绕存储器一圈"的大绕行，没有近距离直连。

**来源文字（原文）**
- "Traces belonging to the address, command and control group should be length-matched within this group."
- "It is also good practice to route data signals that belong to the same byte lane on the same layer."
- "For the address/command/control signals bus in Figure 3-9, the routing constraints can be more relaxed and the routing can be made on any available signal layer."
- "It is recommended to match any group of high-speed signals as tightly as possible."

**对照七个观察点**
1. 调长位置：【图中所见】在大绕行通道的中段，靠近存储器一侧的转角。
2. 留空间：【图中所见】外圈留了很宽的环形空地；图里写着 "Room-MPU" 但文中没解释。
3. 绕行与蛇形：两者并用，外圈线绕远，内圈线加蛇形。
4. 相邻蛇形线：左图是宽条状 U 形、长短不一；右图金色组是阶梯状、洋红组是并排竖直块。
5. 几何：无数字。
6. 工作流：【原文】组内匹配；同字节通道同层；地址/控制可以放宽。
7. 紧凑情形：没有。

---

## G. Howard Johnson：Serpentine Delays（EDN，2001-02-05）

- 网址：https://www.sigcon.com/Pubs/edn/serpentine.htm
- 作者：Dr. Howard Johnson；许可：页脚 "©2001 Signal Consulting, Inc. and Dr. Howard Johnson. All rights reserved."，仅内部参考。
- 图片：13（图 1，a 到 d；原图 229x228 的 GIF，放大 4 倍，边缘较糊）。
- 板子：无，纯几何讨论。相关度：中。回答"蛇形线几何"这一点，且和"留出过孔空间"直接相关。

**图中所见**
- (a) 标准蛇形线，图上用虚线框和 "SWITCHBACK" 标出一个 U 形折返；(b) 把腿压得更密，腿多而窄；(c) 折返少、每条腿很长（原文说法是 "shorter and fatter"，即整体更短更胖；原文说每段延迟变大且耦合显著时会使接收波形失真）；(d) 把蛇形线拉开，凸起之间的凹口里放着四个过孔圆圈。

**来源文字（原文）**
- "you should avoid long, coupled switchbacks."
- "To save space, try squashing the traces closer together (Figure 1b). If the reduction in delay due to NEXT coupling requires the use of more sections (as shown), the layout in Figure 1b may not actually save space at all."
- "The layout in Figure 1d stretches the serpentine to eliminate the coupling issue. The stretched layout neither suffers from delay reduction or distortion nor wipes out big blocks of space for vias on other layers."
- 数字（原文）：50 欧微带、8 mil 线宽和 8 mil 间距、板面离参考面 5 mil，NEXT 约 6%；上升时间 1 ns 的 FR-4 上，耦合折返的最大有用长度约 1 英寸；100 ps 则约 0.1 英寸。

**对照七个观察点**
- 只涉及点 4、5：为了省面积把腿压紧，可能因为耦合反而要更多节、总面积不省。【推断】对 SDRAM 这类较慢的边沿，限制更松，但"压紧不一定省空间"这个结论仍然成立。其余点未涉及。

---

## H. 只有文字（没入库图）的几个相关来源

### H1. FEDEVEL 论坛 7946：SDRAM and Flash Length tunning/matching（最接近用户场景的文字案例）
- 网址：https://courses.fedevel.com/forum/your-projects/7946-sdram-and-flash-length-tunning-matching （2018-05）
- 图：帖里两张图我看过：一张是三个矩形的位置示意（NAND、SDRAM、MCU），一张是原理图（SDRAM 型号 W989D2DBJX6I，DQ0 到 DQ31），没有版图，所以没入库。
- 板子：STM32F4 + W989D2DBJX6I（"Winbond"是我按料号前缀写的，页面没写厂商）（32 位 DQ，原理图可见）+ NAND，6 层（复查：页面叠层列出 L1 到 L6，没写"6 层"这几个字），SDRAM 约 166 MHz，1.8 V。封装【推断】应该是 90 球 0.8 mm 的 LPSDR，帖里没写。
- 【原文】"due to space constraints the SDRAM and Flash are placed quite close to the MCU and therefor each other."
- 【原文】"the Data Lines 16..31 became quite short(~20mm) compared to the rest of the bus nets."
- 【原文】"I was able to match the length by bringing the signals to L1 (upper Signal layer) and add some accordeons("zigzags") but I am afraid that this might bring more issues than benefits."
- 【原文】"I know the best would be to start the routing from the SDRAM from zero by perhaps change the component orientation to vertical, but that would mean redo mutch of the work"
- Feranec 的回复："Normally, I would try to avoid to go into this kind of situation from beginning, now it may be hard to try to improve it."
- 意义：这正是用户描述的症状（芯片靠得近、一部分网络天生太短、没地方加长）。资深工程师的答案是"开头就别进入这种局面"（他的回复只有这一句，没有给具体办法）。【复查更正】原来写的"最稳的办法是改变元件朝向、从存储器起重新布"是发帖人 pedlaf 自己说的（"I know the best would be to start the routing from the SDRAM from zero by perhaps change the component orientation to vertical"），不是资深工程师的建议；Feranec 只回了 "Normally, I would try to avoid to go into this kind of situation from beginning, now it may be hard to try to improve it."

### H2. FEDEVEL 论坛 13431：三阶段流程（Feranec 自述的工作流）
- 网址：https://designhelp.fedevel.com/forum/test/pcb-layout/13431-ddr3-routing-with-xilinx-zynq-chip-as-driver （2020-04）
- 提问人（Zynq + DDR3）的困境："In my routing I have 20 mm difference between longer track and shorter. In this way I have to use big space to tunning tracks."
- Feranec 的回答（原文）："I usually have three phases: 1) connect - in this phase, there may be big difference between tracks, still, be sure difference is not too big as it may be very difficult to add a lot of length on many signals. 2) do approximate length matching (almost the right length, but not spending too much time playing with it) - often I make the tracks a little bit longer as it is simple to make them shorter 3) fine tuning (final length matching and locking down the tracks) - adjusting the tracks to the target length."
- 同帖他还说地址/命令/控制信号 "b is safer"（两层都有走线段、所有线同样走法）。
- 同一回复的最后一句（原文）："So it depends in what phase of design you are ... in phase 1 you may have 20mm difference."——针对提问者"差 20 mm、要用很大空间去调"的担心，他说第一阶段差 20 mm 可以（提问者是 ADDR/CMD/CTRL 组，Zynq + DDR3）。
- 【推断】这是整套来源里最直接回答"布线和调长怎么配合"的一段话：阶段一连线（长度差别别大到很难加长，但 20 mm 可以接受），阶段二故意做得略长，阶段三再收。原来写的"连线阶段就要控制长度差别不能太大"漏了 20 mm 这一句，已补。

### H3. FEDEVEL 论坛 3504：LPC1788 两层板 SDRAM 蛇形线评审
- 网址：https://courses.fedevel.com/forum/schematic-design-pcb-layout/3504-how-to-routing-sdram-for-lpc1788-stm32f4 （2016-08）
- 评论里的几何建议（用户名 mairomaster，普通论坛用户，页面没写资历，不是 Feranec；2016-08-05）："You might want to leave slightly more space between the separate tracks and between the waves in a single track if possible, to reduce crosstalk." 以及 "3 times the track width is a generally safe value. Also it's good to have a bit wider waves, because of self cross talk withing a signal."
- Feranec 的态度："I am not 100% sure about length matching on 2 layer PCB. ... Maybe in your case the length matching may cause more problems than benefits." 和 "The memory is probably slow and the tolerance for length matching may be bigger, so the routed tracks may be in tolerance even they do not use the 'waves' to adjust the length."
- 图（photoid3516）是两层板、非常密、很小（849x478），我看过但没入库。

### H4. Barry Olney（In-Circuit Design）：Losing a Bit of Memory（PCBDesign 杂志，2013-05）
- 网址：https://www.icd.com.au/articles/Losing_a_Bit_of_Memory_PCBDesign-May2013.pdf （下载在 scratchpad/dl-icd1）
- 只有仿真波形，没有版图，没入库图。
- 【原文】"No matter what type of memory you are using, the clock (or strobe) should always have the longest delay so the other signals have time to settle, before the clock arrives at the device, and samples the bus."
- 【原文】"Remember: The clock must have the longest delay, which is not necessarily the longest length."
- 【原文】"Routing all signals to the same delay can seem more difficult at first because of the lack of real estate, the tight space to drop vias and the large number of interconnects. However, it is the best way because it makes the signal timing analysis straightforward."
- 【原文】"the serpentine trace is 150ps faster than the straight trace"（他的仿真里，两条等长线，一条是紧耦合蛇形线）。

### H5. SierraConnect：DDR3 Interface Design with STM32MP157FAC1 Using KiCad（2025-07）
- 网址：https://sierraconnect.protoexpress.com/t/ddr3-interface-design-with-stm32mp157fac1-using-kicad/3331
- 发帖人称匹配到 1.016 mm。回帖人（timothy.phillips）："Length matching is preferred using time delay (ps) over physical length." 和 "I also personally length match as tight as possible instead of only the minimum allowed." 
- 页面附了一张 949x606 的 KiCad 截图，但多层叠在一起，看不清哪根线在哪层，我看过后没入库。页面没给层数、BGA 间距、蛇形线几何。

---

## 反复出现的做法（跨来源）

1. **同一组信号走一样的路**（同样的层、同样的过孔转换），这样调长时可以不管过孔的 z 向长度。来源：C、E、F；FEDEVEL 5828 里 Feranec 答 "Route them the same way."；【复查】3666 是普通用户 nachodizz990 的经验帖，不是资深工程师；13042 里 Feranec 说的是反面条件 "Yes, length in VIA needs to be considered."（层转换不同时必须计入过孔长度）。没做到的反面案例：H1（短网络被迫上外层）。
2. **嵌套同心通道 + 蛇形线并用**：长网络走外圈，短网络走内圈，再在内圈短线上加蛇形线。【复查更正】原来写的"蛇形块落在通道中段，不在球区边上"不成立：C 的 07 有紧挨球区出口的蛇形线，A 的 01 左束蛇形块上缘离存储器球区只隔一两个过孔间距。"外圈长、内圈短加蛇形"这条只在 A（01，看形状读的，没逐网络核对）和 F（11 左，内圈短线带 accordion）的图里读到；B 的 03 是评估摆放的粗连线、没调长，04 是见缝插针的不规则块，不是嵌套通道；E 的 10 图小看不清。【推断】这是一个比"事后找直线段加蛇形线"更像"一开始就留位置"的做法，但这些来源都没有明说"先留空间"，是从图上读到的。
3. **蛇形块塞在两个已知空档里**：过孔列之间（D 的 08）、存储器与 BGA 之间的整片空地（A、B）、A 的 01 右那个铜区缺口（【复查】未证实是专门预留的，也可能只是铺铜自动避让，见 A）。
4. **先决定层和过孔方案，再布线、再调长**：C 的扇出规划；Feranec 的三阶段（连线、粗配、精调），第一阶段的长度差别别大到很难加长，但同一回复里他明说第一阶段差 20 mm 可以（H2）。
5. **改布局比硬调更值**：旋转芯片缩短总长（B 的 Paul）、把布局重做十几次找好位置和引脚（B）；H1 里"改元件朝向、从存储器起重新布"是发帖人自己的想法，不是资深工程师的建议（复查更正），Feranec 只说了"开头就别进入这种局面"。
6. **引脚/位交换减少交叉**：数据位可以在字节通道内任意交换（B 的 Paul），地址线在 FPGA 的同一字节组内可交换（B，发帖人引用 UG586）。这是 FPGA 的情况；STM32 FMC 的 SDRAM 是否同样可交换，这些来源里没有。
7. **时钟/选通线定目标长度**：时钟最长，地址组相对时钟留差（B 的示意图；H4）。【复查：B 的示意图是 iMX6 专用、T-branch 拓扑，数据组相对时钟 "Not defined"；H4 讲的是时钟延迟最长，"not necessarily the longest length"，不是长度最长。】
8. **蛇形线几何**：避免"长的紧耦合折返"（G）；间距别太近（D 只说别太近、没给数；H3 的 3 倍线宽是普通论坛用户 mairomaster 的说法，页面没写资历；G）；sawtooth 的凸起顶宽小于 3w、高 2s（D）。注意 G 指出把腿压紧并不一定省面积，因为耦合会缩短延迟，要更多节。
9. **别过度收紧**：慢速存储器、两层板上硬做等长可能得不偿失（H3，Feranec）。

## 没找到的 / 只有部分的

- **Phil's Lab 的 SDRAM 内容**：FEDEVEL 博客上有 #80（SDRAM Hardware & Firmware Tutorial）的条目，但章节标题全是 "Introduction"，没有静帧或文章配图；没找到对应的 GitHub 版图文件。所以 Phil's Lab 这条线没有可用的图。他的 #5 视频里 SDRAM 放在板子背面且速度较低，不涉及等长细节（来自论坛评论的转述，我没看视频）。
- **Feranec 的 YouTube 视频静帧**：只看到视频缩略图（xSignals、fly-by、T-branch），没有版图静帧；没下载视频。
- **Rick Hartley / Eric Bogatin 的蛇形线材料**：没找到带版图的文章；搜索里有人把"3 倍线宽"归给 Bogatin，我没找到出处，不能确认。
- **Toradex / Variscite / Cadence / Sierra Circuits 的布线指南**：没有深入。Cadence 的 DDR 页面里图是脚本加载的缩略图，抓不到版图；搜索摘要里提到 Cadence 电子书说"调长段不要集中在一处、要沿线分散"，我打开页面没能核实，不引用。
- **Reddit r/PrintedCircuitBoard "Roast my DDR4 routing"**：Reddit 本身抓取被拒，镜像站超时。只看到搜索摘要里的两句话（BGA 球周围弯弯绕绕是因为"There isn't that much space to have the delay matching for some of those traces"；"I usually try to escape the two outer rings of BGA balls on the same layer as the part"），页面和图都没看到，未核实。镜像网址：https://lr.us.psf.lt/r/PrintedCircuitBoard/comments/1dvave1/roast_my_ddr4_routing
- **element14 论坛 "CircuitStudio SDRAM routing impossible"（STM32H723 + IS42 SDRAM）**：连接超时，没读到，只有搜索摘要。网址：https://community.element14.com/products/manufacturers/altium/f/forum/40146/circuitstudio-sdram-routing-impossible-10000-upgrade-kicad
- **BeagleBone Black 的 DDR3 截图**（AM3358 + 一颗很近的 DDR3，帖里称走线最长不到 900 mil）：FEDEVEL 2999 帖里的两张图 id3000.jpg、id3001.jpg 返回 403，没存。网址：https://courses.fedevel.com/forum/beginners/2999-ddr3-memory-routing 。帖子文字里 TI 的人说在这个长度下不同层速度差可以忽略，Feranec 的回应是"I rather length match the board than risking of spending hundreds of hours with debugging"。
- **两颗芯片相距几毫米、0.65 mm BGA 对 0.8 mm BGA 的带图实例**：没找到。最接近的是 A（BGA 与存储器间隔很小，但没有比例尺，封装也不同）和 H1（文字）。【复查补充：A 的间隔按球距粗估约 5 到 7 mm，是估计，见 A 的第 7 点；A 的作者自称是首次做大 BGA + DDR3。】
- **有可量取蛇形几何数字的图**：只有 D 的 sawtooth 标注。其余蛇形线几何都是目测估计。
- **STM32 FMC SDRAM 的引脚/位交换**：没找到来源明说。
- **STM32F746 + IS42S32400 的 ST 社区帖（Eagle 版图）**：图里蛇形线很多但作者是业余水平，没有资深工程师评论，且页面没讨论蛇形线放哪，没入库。

---

## 复查记录（第二次核对，2026-11-17）

核对方式：13 张入库图全部用 Read 打开，均存在、可读，没有缺失；把来源页面逐个重新取文核对引文（Altium 三篇、FEDEVEL 论坛 10831/7946/13431/3504 四帖、Hackaday、Microchip、Johnson、Sierra、FEDEVEL 博客，Olney 的 PDF 用 pypdf 抽正文核对；跨来源总结里引到的 3666/5828/13042 只核对了已下载的文本，没有重新取网址）；几何数字用像素扫描重量；ThunderScope 的 6 帧 GIF 重新逐帧看过。

**引文：全部核对通过**（逐字出现在给定网址）。个别措辞差异已在正文标出：Altium 图 5/7 的说明只在图注里；07 图里两个批注文字只在图里，页面正文只有相近的话（"there will not be space left on the Layer 10 to fanout the 'outside groups'"）；Altium 原文用弯引号；Feranec 在论坛的用户名是 robertferanec。

**本次修改的内容**
1. 开头结论：删掉"又附带资深工程师评论"的说法。ThunderScope 作者自称首个大 BGA + DDR3 设计，FEDEVEL 发帖人自称首个 DDR3 设计，只有 Feranec 的 iMX6 Rex（06、07）出自资深工程师本人板子；01 到 05、12 降为"形态参考"。
2. 图片清单：04、05 标注新手作品，10 标注偏弱（图小、蛇形线归属不明、板子来源未说明）。
3. A：补"x16"的页面原话（是被替换模块的）；补相关度的资历提醒；密 accordion 腿间距改为实测 1.5 到 3 倍线宽（典型约 2 倍），原来"2 到 2.5 倍"略偏大；新增存储器到 BGA 间隔约 5 到 7 mm 的粗估（明确标为估计，球距 0.8 mm 是按封装规格取的）。
4. B：相关度和评审人措辞改为"评审人"，不再称"资深人员"；补 8 层叠层里只有 2 个内层信号层。
5. C：07 补充两个批注的箭头交叉、对应关系不确定，并说明页面把图 7 的用途写成"留空间做扇出"；相关度补"唯一明确出自资深工程师本人板子"。
6. D：把"蛇形线放哪不重要"限定到原文的理由（非差分、无成对相位要求），并说明同页仍要求间距和警告 trombone 的 NEXT；08 补实测 3.5 到 5 倍线宽。
7. E：5H 在原文是"很保守的做法"，不是硬性规则。
8. F：SAMA7G54 只在页面头部，正文是通用 16 位点对点要求；"字节通道 0 是金色、通道 1 是洋红、各占一层"页面没写，改标为推断。
9. H1：把"改元件朝向、从存储器起重新布"从"资深工程师的答案"更正为发帖人自己的话；"6 层"改注为页面叠层列出 L1 到 L6。
10. 跨来源总结：第 1 条标出 3666 是普通用户帖、13042 是反面条件；第 2 条删掉"蛇形块不在球区边上"（与 C、A 自己的描述矛盾），并说明只有 A、F 的图支持"外圈长内圈短"；第 3 条说明铜区缺口未证实是预留；第 4 条补"第一阶段差 20 mm 可以"；第 5 条同 H1 的更正；第 7 条补 iMX6 专用、T-branch、数据组 "Not defined"、时钟是延迟最长而不是长度最长；第 8 条标出 3 倍线宽来自普通用户；"没找到"一项补 A 的间隔粗估。

**核对后确认没问题的数字**（来源文字或像素扫描，复查两次）：Feranec 线宽 0.12/0.114 mm、发帖人 0.25 mm 间距、0.16/0.35 mm 线宽、5 cm；H1 的约 20 mm 和 H2 的 20 mm；H4 的 150 ps；H5 的 1.016 mm；Johnson 的 50 欧、8 mil、5 mil、约 6%、约 1 英寸/0.1 英寸；Altium sawtooth 的 W 到 3W 与图中 "<3w"、"2s"；iMX6 示意图的 ±5 mils、-200 mils、±25 mils、±10 mils（对图）；03 的 8 条线和约 40 px 中心距对约 6 px 线宽（扫描 38 到 45 px 对 5 到 7 px）；04 的 5 到 6 px 线宽对 12 到 13 px 间隙。

**仍然只是推断或估计，没有变成事实**：01 右半的铜区缺口是否预留；01、02、12 的层数（6 帧无层名）和"顶/底"归属；12 的"过孔场"是两面位置重合的通孔这一读法；所有"外圈长、内圈短"的读法；所有图上量出的几何比例（缩小截图，误差大）；ThunderScope 页面 "1 Comment" 的内容没核对。
