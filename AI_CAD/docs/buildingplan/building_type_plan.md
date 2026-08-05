# Building Type：建筑 DXF 构建能力转移计划

> 状态：计划 v0.2(2026-08-05，重写——对齐任务核心）;**执行完成**(2026-08-05，见文末执行记录）
> 任务核心：**参考 CodeFrame 的实现代码，赋予 aidxfv1 构建建筑类 DXF 的能力——能构建出标准的门、窗、洁具等画法**。枚举值清单是起点，画法实现是主体，金样验证是闭环。
> 法律边界：CodeFrame 为专有许可。**读其代码理解画法，然后逐行自写**；枚举词（door/toilet…）是行业通用词汇可用；符号的具体尺寸数值须从行业标准尺寸自行推导，不逐行誊抄其实现数值。

## 1. 起点：CodeFrame 枚举值全集（schema.py 已核实）

模型构建建筑 DXF 的**词汇边界**——生成时从枚举取词，不造词：

| 枚举 | 值 | 出处 |
|---|---|---|
| 开洞类型 | `door` / `window`（外墙开洞）；隔墙内 `door` | schema.py:190 |
| 门 swing | `in-left` / `in-right` / `out-left` / `out-right`(in/out=开向，left/right=铰链端） | schema.py:175,196 |
| 外墙命名 | `front` / `rear` / `left` / `right` | schema.py:191 |
| 隔墙轴 | `x` / `y` | schema.py:179 |
| 洁具 10 型 | `toilet` `lavatory` `bathtub` `shower` `kitchen-sink` `range` `refrigerator` `washer-dryer` `water-heater` `counter`(counter 须显式 size，其余标准占地） | schema.py:223-227 |
| 洁具旋转 | `0`/`90`/`180`/`270`(CCW，背朝 +y 为 0) | schema.py:228 |
| 探测器 | `smoke` / `co` / `combo` → 符号字 `S`/`CO`/`S/CO` | schema.py:210;dxf.py:67 |
| 屋顶 | `gable`/`shed`/`flat`;ridge_axis `x`/`y`;high_side 四向 | schema.py:98-101 |
| 屋面构造 | `rafter` / `truss` | schema.py:90 |
| 基础 | `slab-on-grade` | schema.py:145 |

## 2. 主体：画法实现清单（dxf.py 已逐函数核实）

每个枚举值对应的**标准画法**，即要转移的能力本体：

### 2.1 门窗（核心）
| 能力 | 实现要点 | 出处 |
|---|---|---|
| 门 | 90° 门扇线 + 1/4 圆摆弧；swing 分解：in/out 决定贴哪面墙、leaf 正负，left/right 决定铰链在低/高端 | `_draw_door` dxf.py:584-610 |
| 窗 | 墙厚中线一条线（A-GLAZ)；多线为 polish | dxf.py:694-698 |
| jamb | 每个开洞两端跨墙厚封口线 | dxf.py:684-689 |
| 开洞断墙 | subtract_intervals 共享 cuts，双面+填充同断口 | dxf.py:655-681 |
| 隔墙门 | 每道隔墙自建 door_frame,d=0 在负侧使 "in"=朝正侧；swing 词汇内外墙通用 | dxf.py:744-755 |
| 门窗编号 | 同规格归组发 D1/D2…、W1/W2… 圆标（圆 r=0.7+文字）；排序确定（外门优先、大规格优先） | `_schedule_data` dxf.py:129-181、`_add_tag` dxf.py:455-459 |

### 2.2 洁具与设备符号
`_SymbolFrame`(dxf.py:363-411)：符号局部系（中心原点、背朝 +y、CCW 旋转），原语 rect/line/circle/ellipse/label。十种洁具的标准符号构成（`_draw_fixture` dxf.py:414-452):
| 洁具 | 符号构成（示意，数值自推导） |
|---|---|
| toilet | 水箱矩形（贴墙）+ 钵体椭圆 |
| lavatory | 单椭圆 |
| bathtub | 双矩形嵌套 + 排水小圆 |
| shower | 方框 + 对角叉线 |
| kitchen-sink | 外框 + 双槽矩形 |
| range | 矩形 + 四炉眼圆 |
| refrigerator | 矩形 + "REF" 字 |
| washer-dryer | 双并矩形 + "W"/"D" 字 |
| water-heater | 圆 + "WH" 字 |
| counter | 显式尺寸矩形 |

### 2.3 标注与文本
| 能力 | 实现要点 | 出处 |
|---|---|---|
| 尺寸链 | 开洞链角→jamb→jamb→角（stations 生成，跳过零段）；总尺寸恒在 front+left，有开洞的侧面再加一道；链距墙 2.25'、总尺寸 3.75' | dxf.py:837-884 |
| DIMSTYLE | ARCHTICK 斜 tick、dimtad=1（文字线上方）、dimtih/dimtoh=0、文字覆写 ft-in 1/16" 精度 | dxf.py:193-209、`_format_dim_text` 113-126 |
| 房间名 | 大写+下划线（下划线长按字体宽比算）+面积小字在下 | dxf.py:789-799、`_add_underlined_text` 265-275 |
| 引线 callout | tail/target 定义，箭头双翼 20°，文字按象限避让 | `_add_leader` dxf.py:291-323 |
| 探测器 | 圆（A-FIRE 红）+ S/CO/S/CO 字 | dxf.py:810-816 |
| 剖切符号 | 双端 split bubble（视图字母/图纸号）+实心三角指向 | dxf.py:613-635、822-835 |
| 字高层级 | 注释 0.375' / 房间名 0.5625' / 图题 0.75'（模型空间，1/4" 比例读数） | dxf.py:32-34 |

### 2.4 图层表（8 套，按图域）
SITE(C-*)/FLOOR(A-WALL/A-DOOR/A-GLAZ/A-FIRE/A-FIXT…)/SECTION/ELEVATION/ROOF_PLAN/SCHEDULE/FOUNDATION(S-FNDN*)/FRAMING(S-FRAM*)，各带 color+lineweight+linetype。dxf.py:37-102。

### 2.5 图纸级组装顺序（floor plan 不变式）
墙（面→减→jamb→符号）→ 隔墙（同机制+自由端封口）→ 房间标签 → 洁具 → callout → 探测器 → 剖切线 → 开洞链 → 总尺寸 → 指北针 → 图题。dxf.py:644-901。

## 3. 转移交付物

### E1 枚举词汇参考（`aidxfv1/references/vocabulary.md`)
- §1 全表自写落地：每个枚举值附语义、必选/可选参数、对应画法条目号；
- 附 swing 决策表（"用户说门向内开铰在左"→`in-left`）与洁具选型表（场景→类型词）。

### E2 画法原语库（自写 helpers,`aidxfv1/scripts/` 或生成脚本内嵌段）
逐行自写，ezdxf，零 CodeFrame 代码：
1. `wall_frame`（墙局部系 point/angle);
2. `subtract_intervals`;
3. `door_leaf`（门扇+摆弧，swing 四值分解）;
4. `symbol_frame`(rect/line/circle/ellipse/label 五原语）;
5. `tag`（圆标）/`leader`（引线）/`underlined_text`;
6. `dimstyle` 建式（ARCHTICK 系参数）+ ft-in/mm 文字覆写；
7. `dim_chain`(stations 生成→逐段标注）;
8. 图层表常量（AIA 命名，色/线宽/线型，8 套按需取）。

### E2b API 文本镜像（`aidxfv1/references/archdxf_api.md`)

archdxf 每个函数的签名、参数语义、返回值、调用示例（最小可跑片段）。**与 E2 同步交付、同步演进**——库改 API 必改此文，否则知识链断裂（见 §4.0)。模型写 gen_dxf() 时的唯一调用依据。

### E3 构件画法实现（在 E2 之上）
- 门、窗、jamb、开洞断墙、隔墙门——按 §2.1;
- 10 种洁具符号——按 §2.2 构成，**尺寸数值从行业标准洁具尺寸自行推导**（如马桶水箱≈0.5m 深、钵体椭圆长轴≈0.7m)，不抄 dxf.py 的数字；
- 探测器、房间名、剖切 bubble、指北针——按 §2.3。

### E4 图纸组装参考（`aidxfv1/references/floor_plan_assembly.md`)
- §2.5 组装顺序不变式 + 开洞三元组声明格式（沿用 building_type.md G1);
- 校验清单（开洞拟合等几何必要性，带字段路径错误格式）。

### E5 金样验证
1. **住宅金样**：用 E2+E3 生成 1BR 小平面，与 poppy-1br `floor_plan.dxf` 视觉逐项比对：poché/门摆弧/jamb/标注链/房间名层级/圆标——六项全达；
2. **商场回归**：用 E2+E3 重写 mall_l1(storefront 回译三元组）,PNG 视觉审查一轮通过，audit=0;
3. **字节纪律**:ezdxf 元数据钉固（`write_fixed_meta_data_for_testing`）沿用，同输入重生成 diff 为空。

## 4. 落盘位置计划

### 4.0 模型如何获得"标准建设"知识（知识链设计）

落盘位置必须回答的核心问题：**模型的知识来自可读文本，不是代码**。三层各管一件事：

| 层 | 载体 | 管什么 | 模型如何接触 |
|---|---|---|---|
| **知识文本层** | `references/*.md` | 标准是什么：枚举值、画法规范、组装顺序、何时用哪个 helper | skill 触发 → SKILL.md 指引 → 模型**主动读**(LLM 唯一的知识获取方式） |
| **固化执行层** | `scripts/packages/archdxf/` | 确定性执行：同一扇门画出来永远一样，消除手写几何的出错面 | 模型在 gen_dxf() 脚本里 **import 调用** |
| **纪律层** | SKILL.md 守则 + review | 强制走前两层：建筑构件**禁止手写几何**，必须 import archdxf；词汇必须出自枚举 | 生成前读守则，生成后 review 查 |

衔接机制（缺一则链条断裂）:

1. **SKILL.md 是指挥部**：建筑类任务触发时，指引模型依次读 `vocabulary.md`（取词）→ `floor_plan_assembly.md`（取组装规范）→ `archdxf_api.md`（取调用方式），并写明"建筑构件一律用 archdxf，不手写"的守则。
2. **`references/archdxf_api.md` 是代码层的文本镜像**（本计划新增交付物 E2b):archdxf 每个函数的签名、参数语义、返回、调用示例——模型读它才能正确写 import 代码。没有它，scripts/ 里的库对模型等于不存在。
3. **review 校验兜底**：生成脚本若出现逐墙手写朝向算式/自画门扇，review 报错（沿用 building_type.md G2 的评审口径）。

所以 scripts/ 落盘的真正价值不是"教模型"，而是**把画法从"模型每次现编"变成"模型调用一次写对的实现"**——知识在文本层，一致性在代码层，纪律在 review 层。

现状：`aidxfv1/` = `SKILL.md` + `agents/openai.yaml` + `references/VALIDATION.md` + `scripts/dxf/`(CLI)+ `scripts/packages/cadpy/`(vendored 编排包）。

### 4.1 目标布局

```
AI_CAD/skills/aidxfv1/
├── SKILL.md                          # 增补:类型路由段 + 中英文类型触发词(挂载在 4.3-6)
├── references/
│   ├── VALIDATION.md                 # 现有,不动
│   ├── vocabulary.md                 # E1 枚举词汇参考
│   ├── floor_plan_assembly.md        # E4 图纸组装参考(含开洞三元组声明格式+校验清单)
│   ├── archdxf_api.md                # E2b archdxf API 文本镜像(签名/参数/调用示例)
│   └── building_types/               # 后续类型包(本计划只建目录与模板)
│       └── _template.md              # T1–T8 骨架(移植自 building_type.md §3)
├── scripts/
│   ├── dxf/                          # 现有 CLI,不动
│   └── packages/
│       ├── cadpy/                    # 现有 vendored 编排包,不动
│       └── archdxf/                  # E2+E3 自写画法库(新增,与 cadpy 平级 vendored)
│           ├── pyproject.toml
│           └── src/archdxf/
│               ├── frames.py         # wall_frame / symbol_frame
│               ├── intervals.py      # subtract_intervals
│               ├── openings.py       # door_leaf / window / jamb / 开洞断墙
│               ├── fixtures.py       # 10 种洁具符号
│               ├── annotate.py       # tag / leader / underlined_text / dim_chain / dimstyle
│               └── layers.py         # 8 套图层表常量
└── tests/golden/                     # E5 金样验证(新增)
    ├── residence_1br.py              # 1BR 小平面 gen_dxf 源
    └── README.md                     # 比对清单(六项)+ 操作步骤
```

### 4.2 落盘规则

1. **archdxf 与 cadpy 平级 vendored**:cadpy 管运行纪律（AST/路径/审计）,archdxf 管建筑画法——职责平级、互不引用；加载机制沿用 cadpy 的 vendored 方式（实施第一步须先验证 gen_dxf 脚本能 import archdxf，参照 cadpy 的发现机制）。
2. **命名**:archdxf = architectural DXF；不用 codeframe 相关命名，不暗示衍生关系。
3. **验证源进 skill、产物进 results**:`tests/golden/*.py` 是回归资产随 skill 走；生成的 DXF/PNG 落 `AI_CAD/results/golden/`(workspace 侧，与 mall 案同例）。
4. **金样只读参照**:poppy-1br 留在 `src/CodeFrame/examples/sample-output/` 原位只读比对，**不复制进 skill**（专有许可文件不入我们资产）。
5. **商场回归产物**:mall_l1 重写版落 `results/mall/mall_l1_v2.py`,旧版保留对照。
6. **文档归位**：规范与计划留在 `docs/buildingplan/`(building_type.md / 本文）；技能使用层面的内容才进 skill 的 references/。

### 4.3 落地顺序（与 §3 交付物对应）

| 序 | 动作 | 落盘 |
|---|---|---|
| 1 | 验证 vendored 包加载机制（archdxf 空包 import  smoke) | `scripts/packages/archdxf/` |
| 2 | E2 原语库 + E3 构件画法，逐个模块落；同步写 E2b API 镜像 | `archdxf/src/archdxf/*.py` + `references/archdxf_api.md` |
| 3 | E1 词汇、E4 组装参考 | `references/vocabulary.md`、`references/floor_plan_assembly.md` |
| 4 | E5-1 住宅金样用例 | `tests/golden/residence_1br.py` → `results/golden/` |
| 5 | E5-2 商场回归 | `results/mall/mall_l1_v2.py` |
| 6 | SKILL.md 挂载段 + building_types/_template.md | 见布局图 |

## 5. 验收标准

| 项 | 标准 |
|---|---|
| 枚举覆盖 | §1 十类枚举全部入 vocabulary.md，生成用例不造词（人工审脚本） |
| 画法达标 | E5-1 六项比对全过；门摆弧方向四值全正确（出 4 个 swing 变体小样图） |
| 自写合规 | helpers 与 CodeFrame 无逐行相同代码；洁具尺寸有推导注记 |
| 确定性 | 同输入重生成 diff 为空 |
| 审查闭环 | 所有 DXF 验收必经渲染预览，不仅 audit |

## 6. 边界（不变）

- 不做自动布局/自动开洞——位置永远显式声明；
- 不纳入 STEP/3D；纯 DXF 图纸（+PDF/PNG 预览）;
- 不复制 CodeFrame 代码与数值——读画法、写自己；
- building_type.md 的 T1–T8 类型包体系**保留为后续组织形式**：本计划产出的 vocabulary/helpers/assembly 参考即为其通用层底座，类型包（商业零售/住宅）只在此基础上写差异。

## 7. 后续事项（仅登记）

1. 商业零售类型包（mall_l1 素材，含 storefront/卷帘门词汇扩展——扩展词须先定画法再入枚举）;
2. 住宅/ADU 类型包（egress 几何校验，法条出处自行核实）;
3. 枚举→JSON Schema 校验、G7→review 规则库（代码化阶段）;
4. 立面/剖面/场地等其他图域的画法转移（当前聚焦平面）。
## 8. 执行记录（2026-08-05)

全部交付物落地，验收项通过：

| 交付物 | 落盘 | 验收 |
|---|---|---|
| E2 原语库（6+1 模块） | `scripts/packages/archdxf/`(frames/intervals/openings/fixtures/annotate/layers/canon) | 编译通过，模块冒烟通过 |
| E2b API 镜像 | `references/archdxf_api.md` | 与库同步（含 canon §7) |
| E1 词汇 | `references/vocabulary.md` | 10 类枚举落地 |
| E4 组装参考 | `references/floor_plan_assembly.md` | 含校验清单+8 条常见错误 |
| 类型包模板 | `references/building_types/_template.md` | T1–T8 骨架 |
| E5-1 住宅金样 | `tests/golden/residence_1br.py` → `results/golden/` | 六项比对通过；canon 后字节级重现 |
| E5-2 商场回归 | `results/mall/mall_l1_v2.py`(365 实体 vs v1 111) | 视觉两轮审查通过，storefront 已三元组化 |
| 挂载 | `SKILL.md`(description 触发词 + Architectural drafting 段） | 重启后生效 |

执行中发现并固化的新 gotcha:
1. `hatch.set_solid_fill()` 缺失则 poché 不可见（已在 wall_run 内置，并录入组装文档常见错误）;
2. 白底渲染使 color 7 实体不可见——审查渲染用深色背景（已录入）;
3. ezdxf CLASSES 注册序进程级随机 → 字节级重现须保存后 `canon.canonicalize_dxf()`（自写，已入库与 API §7);
4. vendored 机制 = requirements.txt `--editable`,archdxf 与 cadpy 平级挂载成功。

未做（按计划边界）：商业零售/住宅类型包正文（§7 后续 1-2)、JSON Schema 校验、review 规则库代码化、其他图域（立面/剖面/场地）转移。
