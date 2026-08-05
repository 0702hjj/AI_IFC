# Building Type 参考体系：规范框定与能力赋予

> 状态：规范草案 v0.1(2026-08-05)
> 边界声明：**本文只框定规范与能力映射，不设计完整工作流程**（不产出 steps/、不定义端到端管线、不写 helpers 实现）。流程设计是后续独立事项。

## 1. 背景与目标

aidxfv1 当前是"通用 DXF 生成 skill + LLM 现写几何"。商场实战（mall_l1）暴露了缺口：**建筑类型知识没有固化载体**——墙厚取值、符号画法、标注链规则、房间词汇全靠模型每次现编，质量与一致性不可控。

目标：为 aidxfv1 建立 **building-type 参考层**——每种建筑类型一份规范化参考包，模型在生成该类型图纸时按包取词、取值、取画法、取校验规则。

**主要参考对象：CodeFrame**(`src/CodeFrame`,Proprietary 许可证）。
法律边界：**只借鉴其规范结构与模式，文字、表格、代码全部自写**；其价值在于"建筑类型知识如何固化"的范式，不在内容本身。

## 2. CodeFrame 深度调查结果

CodeFrame 目前只支持一种类型（加州独立 ADU)，但它把"一种建筑类型"的知识固化成了**五个载体**，这正是可泛化的范式：

| 载体 | 文件 | 承载的知识 | 对 aidxfv1 的意义 |
|---|---|---|---|
| 惯例蒸馏文档 | `docs/drafting-conventions.md` | 从 11 套真实住宅图纸集蒸馏的画法规则，每条打 HAVE/ADOPT/LATER 状态标签，附采纳日志 | **类型知识的来源与固化流程**：真实图纸集 → 逐条规则 → 状态管理 |
| 配置参考手册 | `skills/codeframe-adu/REFERENCE.md` | 坐标约定、偏移方向表、swing 词汇表、**常用值表**（墙厚 0.42/0.58/0.375、窗台 3.0–4.0、洁具标准占地尺寸表）、负能力声明 | **LLM 面向的参考包本体**：JSON Schema 表达不了的约定全部落在这里 |
| 类型化 Schema | `src/codeframe/schema.py` | pydantic 模型 = 类型词汇全集（fixture 10 种、roof 3 型、swing 4 值、detector 3 类）+ **几何必要性校验**(`_geometry_errors`：出界、开门超墙长、egress 窗 CRC R310 几何上限）+ `extra="forbid"` 拒未知字段 | **词汇与校验规则的机器可读形态** |
| Agent 契约 | `skills/codeframe-adu/SKILL.md` | 职责硬边界："你访谈并写 config,CLI 画图；缺尺寸就问，不许编"；范围声明（单层/木结构/矩形/仅坡屋顶，不合就 upfront 拒绝） | **类型适用范围的声明方式** |
| 架构与 ADR | `docs/architecture.md` + `docs/adr/` | 两层硬边界（Agent 便利层 / 确定性内核）、ADR-0002 explicit-geometry-no-auto-layout、字节级可重现 | **边界原则的决策留痕方式** |

关键范式提炼：

1. **显式几何、无自动布局**：房间只是标签点，面积 STATED never computed；缺值=校验错误而非猜测。这保证了确定性，也把"设计判断"全部留给 LLM/人。
2. **几何校验与规范校验分离**：内核只查几何必要性（egress 窗的窗台≤44" 是几何上限），净开启面积等语义判断标注 BY DRAFTER。
3. **负能力显式成文**：REFERENCE.md 末尾专章 "What the core will NOT do"——边界不靠默契，靠声明。
4. **常用值表即默认参数**：墙厚、窗台、洁具占地这类"类型经验值"以表格固化，标注"placeholder 在方案阶段可用"。
5. **画法惯例带状态机**：每条规则 HAVE/ADOPT/LATER + 采纳日志，类型知识可演进且不丢历史。

## 3. 规范框定：Building-Type 参考包的组成

每种建筑类型的参考包**必须**包含以下八节（T1–T8)。这是规范本身——缺节的类型包视为不完整，不挂载到 aidxfv1。

### T1 类型适用范围声明
- 该类型包覆盖/不覆盖什么（层数、结构形式、平面拓扑、屋顶形式）。
- 不适配时的行为：upfront 声明不适用，不硬套。
- 先例：codeframe-adu SKILL.md 的 Scope 节（"single story, wood frame, rectangular, gable only…不合就说，不掰 config")。

### T2 类型词汇与枚举
- 该类型的构件/房间/设备词汇全集，以枚举形式给出（如住宅的洁具 10 型；商场的店铺/中庭/主力店/后勤走廊词汇——mall_l1 实战已产出初稿）。
- 每个词汇附：符号语义、必选参数、可选参数。
- 形态：表格 + （可选）JSON Schema 片段。

### T3 坐标与命名约定
- 原点规则、轴方向、墙/朝向命名法（front/rear/left/right 或柱网编号）、偏移量起算方向表。
- 原则：**同一类型包内约定唯一**，跨包可不同但必须在包内声明。
- 先例：REFERENCE.md 的 opening offset 表（每面墙从哪端量、墙长等于什么）。

### T4 常用值表（默认参数）
- 该类型的经验取值：墙厚、层高、门窗标准尺寸、走廊宽度、净高、设备占地等。
- 每个值标注性质：**经验默认 / 规范下限（带法条引用）/ 占位值**。
- 先例：墙厚表（0.42/0.58/0.375)、洁具标准占地表（toilet 1.5×2.33…)、vapor retarder 注明管辖差异（CRC 10-mil vs LADBS 6 vs Redding 15)。

### T5 符号与画法规范
- 该类型每种构件的平面符号画法：门=90°门扇+1/4 圆弧、窗=墙厚内居中细线、墙体 poché 填充、房间名层级（大写+下划线+面积小字）、callout 引线规则、剖切符号、指北针等。
- 每条附实现要点（如"土层填充用显式 45° 线而非 HATCH pattern——ezdxf pattern 渲染顺序不确定，破坏字节级重现")。
- 先例：drafting-conventions.md §1–§9。

### T6 标注与文本规范
- 尺寸链分层规则（开洞链→墙段→总尺寸，哪些面必须标总尺寸）、文字规范（全大写、字高层级）、单位书写格式（ft-in 连字符、mm)、标注样式（ARCHTICK 等）。
- 先例：drafting-conventions.md §3–§4 + dxf.py DIMSTYLE 覆写（dimtxt 须在 dimstyle 上设——已实测）。

### T7 几何校验规则
- 该类型的**几何必要性**检查清单：出界、开洞超墙长、门类互斥字段（door 无 sill / window 无 swing)、法规的几何上限（如 egress 窗台≤44")。
- 铁律：**只查几何可判定项；语义判断（净面积、适用性）标 BY DRAFTER/BY REVIEW，不进自动校验**。
- 先例：schema.py `_geometry_errors`（错误信息带字段路径、可行动）。

### T8 负能力声明
- 该类型包明确不做什么：不自动布局、不推断缺失尺寸、不做规范符合性裁决、不画未定义构件。
- 先例：REFERENCE.md "What the core will NOT do" 三条。

## 4. 能力赋予：参考包 → aidxfv1 的映射

参考包不是文档摆设，每节对应 aidxfv1 的一个能力槽位：

| 参考包节 | 赋予的能力 | 落点（aidxfv1 侧形态） |
|---|---|---|
| T1 范围声明 | **类型路由**：识别任务类型→选包；超范围→声明不适用 | skill 触发描述 + 各包 T1 节 |
| T2 词汇枚举 | **受约束的类型词汇**：模型生成时从枚举取词，不造词 | references/ 下类型包文档；后续可升级为 JSON Schema 校验 |
| T3 坐标约定 | **一致的定位语言**：模型与用户/包内描述位置时使用同一套约定 | 类型包文档；生成脚本头部约定注释 |
| T4 常用值表 | **有出处的默认参数**：用户未给值时按表取默认并声明来源，不瞎编 | 类型包文档表格 |
| T5 画法规范 | **一致的符号输出**：同类型图纸符号风格稳定 | 类型包文档；后续可固化为 helpers（参照 CodeFrame 模式自写，见其 geometry.py WallFrame 局部坐标思路） |
| T6 标注规范 | **合规标注链**：尺寸分层、文字风格统一，减少 mall 案那类标注碰撞返工 | 类型包文档 + BUILDING_DRAFTING.md 章节 |
| T7 几何校验 | **类型化审查规则**：audit/review 按包加载校验清单，错误码化 | review 规则库（结构监察之后、业务规则槽位） |
| T8 负能力 | **诚实的边界**：模型知道何时该问、该拒绝、该标 BY REVIEW | 类型包文档 + skill 守则 |

能力赋予的原则：

1. **先文档后代码**：八节全部以参考文档形态先行（LLM 直接可读）;helpers/Schema/规则库是后续固化，不阻塞规范建立。
2. **包间独立**：类型包互不引用，公共部分（如 AIA 图层表、DIMSTYLE）上抽到 aidxfv1 通用层，类型包只写差异。
3. **状态标签沿用**：包内每条规则可打 HAVE/ADOPT/LATER，配合采纳日志演进（CodeFrame drafting-conventions.md 的成熟做法）。

## 5. 类型覆盖范围（框定，不展开）

| 类型 | 知识来源 | 状态 |
|---|---|---|
| 低层住宅 / ADU | CodeFrame 五载体（模式参考，内容自写） | 范式最完整，优先建立 |
| 商业零售（商场/购物中心） | mall_l1 实战案（150×100m，双面店+中庭，已两轮视觉重修） | 已有词汇与参数雏形，待规范化 |
| 办公建筑 | 无 | 占位 |
| 其他（工业/酒店/医疗…） | 无 | 随需求纳入，纳入即须补全 T1–T8 |

## 6. 明确不做（本次边界）

- 不设计 plan→cad→bim 的完整流程，不产出 steps/ 工作流（属 three_dock.md 待办 2 的独立事项）。
- 不写 helpers 库、不写校验代码——能力槽位先以文档形态挂空。
- 不做自动布局/自动房间的任何设计（沿用 explicit-geometry 原则）。
- **不纳入 STEP/3D/体量逻辑**：cad 入口产物边界 = DXF 图纸集（+PDF 预览）;BIM 维度由 aiifc 转换路线独立承担。
- 不复制 CodeFrame 任何文字/代码（Proprietary)；本文所有表格内容为调查后的范式提炼。

## 7. 后续事项（仅登记）

1. 按 T1–T8 模板产出第一个类型包：**住宅/ADU**（模式最新鲜）或**商业零售**（实战素材最新鲜），二选一。
2. 通用层上抽：AIA 图层表、DIMSTYLE 覆写、feet-inches/mm 文本格式，从类型包中分离。
3. 类型包 → aidxfv1 references/ 的挂载方式与触发词（skill description 增补类型词）。
4. 通用层构造文档（§8 G1–G7 落为 aidxfv1 references/construction.md）与自研 helpers(wall_frame / subtract_intervals / door_leaf，从零自写）。

## 8. 专项能力：门窗与隔墙的构造规范

门窗开洞与隔墙是平面生成中**几何最容易错**的部分（mall_l1 实战中每面墙的开洞坐标都靠模型手工换算，四个朝向四种算式）。CodeFrame 用三个机制把这件事变成了不变式，本节将其框定为 aidxfv1 **通用层构造规范**（类型无关；类型包只提供差异参数）。

### 8.1 CodeFrame 机制调查（源码定位）

**机制一：墙局部坐标系 WallFrame**(`geometry.py:33-68`)
每面墙定义一个坐标架 `WallFrame(origin, s_dir, d_dir, length)`:`s` 沿墙（从该墙的偏移原点起算）,`d` 跨墙厚（内正，外饰面 d=0)。`point(s, d)` 局部→平面，`angle(local_deg)` 局部角→平面角。四面外墙的 frame 是一张预定义表（`wall_frame()`,geometry.py:61-68)。**效果：开洞、符号、标注的所有计算在 (s, d) 二维局部系进行，模型永远不碰朝向三角函数。**

**机制二：区间相减 subtract_intervals**(`geometry.py:17-29`)
`span − cuts → 剩余段列表`。墙的两个面、poché 填充、尺寸链**共用同一份 cuts**（开洞区间列表），保证三者断口永远对齐。

**机制三：开洞构造不变式**(`dxf.py:655-708`)
1. 外墙外面角到角、内面止于内角，两面都在开洞处断开；
2. poché 填充的**角部归属规则**:front/rear 拥有角部方块，left/right 只填到内角——相邻墙交界处不重叠；
3. 每个开洞两端画 jamb 线（跨墙厚封口）;
4. 门 = 90° 门扇线 + 1/4 圆弧（`_draw_door`,dxf.py:584-610):swing 词汇分解为 `in/out`（决定门扇贴哪面）× `left/right`（决定铰链在低端/高端）;
5. 窗 = 墙厚中线一条线（A-GLAZ 层）;mark 标签放墙外中点，EGRESS 标签放墙内。

**机制四：隔墙构造**(`dxf.py:710-786`)
- 隔墙用 `(axis, offset, from, to, thickness)` 声明式描述；
- 绘制范围**钳制到外墙内面**(`lo = max(from_, 外墙厚)`)，不与外墙填充重叠；
- 门洞用同一份 subtract_intervals 机制；
- 每道隔墙自建 door_frame(d=0 在负侧，使 "in" = 朝正侧开启）——内外墙共用同一套 swing 词汇；
- **自由端封口**：不到外墙的端头画 cap 线；
- 定位尺寸：从最近的外墙面标到隔墙，取墙中站。

### 8.2 构造规范（G1–G7，通用层）

| 编号 | 规范 | 内容 |
|---|---|---|
| G1 | 开洞定位语言 | 开洞永远以 **（所属墙， 沿墙偏移 offset, 宽度）** 三元组声明；禁止用全局坐标直接摆门窗。位置描述的一切换算在写声明时完成，画图时零换算 |
| G2 | 墙局部坐标系 | 每面墙一个 frame(s 沿墙 / d 跨厚内正）;**所有开洞、门扇、弧线、标注计算在局部系进行**。生成脚本必须含 frame 定义段，不允许出现逐墙手写朝向算式 |
| G3 | 区间相减不变式 | 墙面线、填充、尺寸链共用同一份 cuts；构造顺序固定为：**面 → 减去开洞 → jamb 封口 → 符号**。任何"先画整墙再盖白块"式的遮挡做法禁止 |
| G4 | 角部归属 | 相邻墙交界处的填充/线归属必须唯一且在包内声明（哪个朝向拥有角部），防重叠、防缺口 |
| G5 | swing 词汇 | `in/out`（开向建筑内/外或墙的正/负侧）× `left/right`（铰链在低/高偏移端）四值枚举；门扇=90°、弧线=1/4 圆，不得发明其他画法（双开门、移门等作为词汇扩展登记，未定画法前不用） |
| G6 | 隔墙模型 | 隔墙以 (axis, offset, from, to, thickness) 声明；绘制范围钳制到相交墙的内面；自由端必须封口；定位尺寸从最近外墙标出 |
| G7 | 开洞校验 | 几何必要性：`offset + width ≤ 墙长`、隔墙上 `door.at + width ≤ wall.to`、门类字段互斥（door 无 sill / window 无 swing)、门窗顶不超墙高。语义判断（疏散宽度是否够等）标 BY REVIEW |

### 8.3 能力赋予映射

| 规范 | 赋予模型的能力 | 落点 |
|---|---|---|
| G1+G2 | **位置描述 → 构造的确定翻译**：用户说"前墙正中开 3 尺门"，模型算一次 offset=(16−3)/2=6.5，之后构造零决策 | 通用层构造文档（aidxfv1 references/) |
| G3+G4 | **开洞不断错、填充不重叠**：复杂平面（商场步行街两侧各 10 间、全案 40 个零售单元的连续分隔）也可机械执行 | 同上；后续固化为自写 helpers（自研 wall_frame/subtract/door_leaf,ezdxf，不复制 CodeFrame 代码） |
| G5 | **门朝向的一致表达与绘制** | 通用层词汇表；类型包扩展（商场：玻璃地弹门、卷帘门画法待定义后登记） |
| G6 | **隔墙即声明**：商铺分隔、后勤走廊隔墙用同一模型，含自由端与定位尺寸 | 通用层文档 + 类型包厚度表 |
| G7 | **开洞层自查**：audit/review 按清单报错，带字段路径 | review 规则库槽位 |

### 8.4 类型包的差异职责（门窗/隔墙维度）

通用层管机制，类型包只管参数与词汇差异：

| 差异项 | 住宅/ADU 示例 | 商业零售示例（mall_l1 实战提炼） |
|---|---|---|
| 标准门宽/门型 | 2'6"–3'0" 单扇，swing 四值 | 店面玻璃地弹门（通宽）、后勤门 900–1000mm、防火门（词汇扩展，画法待定） |
| 窗型 | 单线窗 + sill 高度表（3.0/3.5–4.0) | 店面玻璃幕墙（ storefront 连续带，mall 案已实现为独立图层构造，须回译为 G1 三元组 + 幕墙词汇）、高侧窗 |
| 隔墙厚度 | 2×4 内隔墙 0.375 | 商铺分隔 100–150mm、防火分区隔墙（须配防火门词汇） |
| 开洞校验附加 | egress 窗几何上限（CRC R310 类） | 疏散门宽度几何下限、店面开洞率（BY REVIEW) |

### 8.5 本节明确不做

- 不写 helpers 实现代码（自研固化是后续事项，登记于 §7)。
- 不做自动开洞/自动门窗布置——位置永远来自声明（沿用 explicit-geometry)。
- 非正交墙（弧形、斜墙）暂不纳入 frame 模型；类型包遇到即声明超范围。
- CodeFrame v1 "内墙不开窗"是它的范围声明，不是本规范的约束——商业零售的店面幕墙按类型包词汇扩展处理。

## 9. 补查：codeframe 全库地图与 sample-output 实证（2026-08-05)

### 9.1 库全图（8 模块，3401 行）

| 模块 | 行数 | 职责 | 已查 |
|---|---|---|---|
| `schema.py` | 492 | Project Config pydantic 模型 + 几何必要性校验 | ✅ 全文 |
| `geometry.py` | 96 | WallFrame / subtract_intervals / slope / 立面区间镜像 | ✅ 全文 |
| `dxf.py` | 2058 | 全部 DXF 图纸 writer(floor/site/roof/4 立面/section/foundation/framing/details/schedules/notes×3/compliance) | ✅ 关键段（开洞/隔墙/门） |
| `sheets.py` | 293 | PDF 图纸集合成（matplotlib PdfPages):**探 extents → 选比例 → 带比例标注重建视图**；标题栏装饰、PRELIMINARY 戳 | ✅ 本次 |
| `cli.py` | 162 | `schema`/`validate`/`generate` 三命令；**条件 writer 列表**驱动图纸集组成 | ✅ 本次 |
| `massing.py` | 290 | Box/Prism/Solid 体量 → freecadcmd 无头导出 STEP | ✅ 本次——**不采用，超范围**（本体系专注 DXF，无 STEP/3D 需求） |
| `__init__.py`/`__main__.py` | 10 | 入口 | ✅ |

### 9.2 sample-output/poppy-1br 实证

**确认：poppy-1br 就是 codeframe-adu skill（访谈写 config)+ `codeframe generate`（确定性内核）的一次完整运行产物。**

证据链：
1. 输入 `examples/poppy_one_bedroom_adu.json`(22'×34' 1BR ADU,50'×100' 地块，含 foundation + truss framing + section A);
2. `cli.py:110-146` 的 writer 列表与目录文件**一一对应**:15 张无条件/条件 DXF(general_notes、code_compliance、site、floor、roof、4 立面、section_a、schedules、structural_notes、foundation_plan、roof_framing_plan、details——逐项数共 15)+ drawing_set.pdf;(`model_3d.step` 为 FreeCAD 体量导出，仅作生成方式佐证，**本体系不采用**);
3. 全文件同一时间戳，单批产出；
4. ezdxf 读检：图层为 AIA 体系且**按图域分前缀**（建筑图 A-*/场地 C-*)，实体构成符合画法规范（floor_plan:HATCH 18=poché、ARC 4=门摆、DIMENSION 27=标注链）;**appids 仅 ACAD/EZDXF 默认——无任何语义标注（无 XDATA/XRECORD)**。

### 9.3 新增范式提炼

1. **图纸集组成 = config 驱动的条件输出**:foundation/framing/sections 有配置才有对应图纸，无则不画（cli.py 条件 writer)。→ 我们的类型包应规定"图纸集构成规则"（什么输入条件产出什么图），这是 T 节之外的新组成维度，归入 T1 范围声明的配套。
2. **单 config → 全套 DXF**：一套输入出 15 张 DXF + PDF 图纸集，explicit-geometry 单一事实源的可扩展性实证——图纸集规模可以远大于我们目前的单张平面。
3. **无语义是刻意的边界**:CodeFrame 纯制图、零语义标注；与我们 L1–L3 语义构筑（XDATA/XRECORD）正好分层互补——**制图质量向它看齐，语义层是我们自己的差异化能力**（服务 aiifc 转换），不冲突。
4. **范围裁减：专注 DXF，完全不纳入 STEP/3D 逻辑**——massing.py 的体量导出机制（序列化参数→外部内核建模→优雅降级）不作参考；BIM 维度由 aiifc 转换路线独立承担，cad 入口的产物边界就是 DXF 图纸集（+PDF 预览）。
5. **sample-output 的参考资产价值**:poppy-1br 全套图是**画法规范的视觉金样**（每张图长什么样、什么图层、什么实体构成可直接读检），可作为我们住宅/ADU 类型包 T5/T6 节编写时的对照样本；PDF drawing_set 是图纸集合成（比例选择、标题栏）的直接参照。
