# step-01a 4 轮细则（P1 设计的轮次内容）

> 本文件是 step-01 渐进设计对话的**轮次细则**：每轮"问什么 / 怎么构造 / 怎么校验"。
> 交互节奏（连问批量/精问/直落）、回退主干见 `step-01-design.md`；question 用法/修改协议/冲突
> 裁决见 `step-01b-protocol.md`。
> 本文件自包含（skill 内），不依赖 skill 外文档；设计参考指向 skill 内 `references/`。

## 第 1 轮 · 骨架（连问批量，一整段草案 + 一个确认框）

**B0 方向卡**：含 4 项——`direction`（类型方向）/ `form_hint`（形态方向）/ `scale_hint`（规模量级）/
`vibe`（气质关键词数组）。
- 输入源：外部文档线索 / building_type 类型包 / 用户直接说（听完翻译成方向卡回显确认）
- **不碰具体参数**，只定方向基调

**A 地块**：
- `site.lot_polygon_mm`：文字描述地块形状/朝向/四至（板式/L形/异形/围合、哪面临街/临景）+ 确认（缺口追问 GAP-3）
- `site.setbacks_mm`：逐向确认（front/rear/left/right 四向退线）
- `site.origin` / `site.north_deg`：约定项（左下角原点、正北 0°），回显带一句，**直落不单独问**

**B 分区骨架**：
- `zones[].{function, floors, floor_height_mm}`：逐 zone 确认（缺口追问 GAP-1/2/4）
- `vertical_relations[]`：竖向关系（核心筒直通地面、后勤独立）

**确认方式**：一整段草案（方向卡 + 地块 + 分区 + **已知硬缺口候选**）+ **仅一个**确认框
（options：`全部 OK，继续` / `改某项` / `我自己描述`）。层数/地块尺寸若资料未给，
必须并进本框选项或 custom，**禁止**方向确认后再单独开一轮问层数。
不回显字段名——按实际项目用建筑师词汇。

## 第 2 轮 · 几何（精问）

**机器段（用户锁第 1 轮后本回合内连续执行，禁止对用户说话/等许可）**：

```
1. derive（地块事实，设计依据）
   .venv/bin/aiplan derive --lot '<lot>' --setbacks '<setbacks>'
   事实：aspect_ratio / exposure_m / deep_zone_ratio / dominant_axes / concave_corners
   入参格式（2026-08-17 统一：文件路径 或 内联 JSON）：
   - --lot = 地块顶点数组（mm 坐标，顺/逆时针都行）：
     '[<0,0>,<80000,0>,<80000,120000>,<0,120000>]'  # 80×120m 地块
     也接受 dict 容错：'{"points":[[0,0],...]}'（防 KeyError: 0）
   - --setbacks（可选）= 退线 dict，键名固定：
     '{"front":5000,"rear":5000,"left":3000,"right":3000}'
     front=北(y 大侧) / rear=南(y 小侧) / left=西(x 小侧) / right=东(x 大侧)
   - 退线 + 轮廓必须自洽：退线内缩后的可建进深要放得下户型进深 + 阳台凸出。
     先算一遍 derive，若 buildable_area_sqm 远小于所需层面积 → 收紧退线再 derive（勿直接画越线轮廓）
   产出即设计依据：aspect_ratio 判板式/塔式、exposure_m.S 定南房面宽预算、
   deep_zone_ratio 定暗区功能、dominant_axes 定轴网基准——写轮廓前先读事实。

2. 命中 pattern（只读 index + 命中段）
   读 references/design_patterns/index.json
   按 derive 事实匹配「适用条件」→ 得到 pattern_id 列表
   只打开命中条的 file，定位到 dsl_anchor 那一节（不要通读 md）

   典型映射：
   | 事实 | 优先 pattern |
   |---|---|
   | 异形/斜边/凹角 | irregular_edge_polyline |
   | 规则阳台/核筒外凸 | projection_on_edge |
   | 圆角幕墙 | arc_fillet_corners |
   | 中庭 | holes_courtyard |
   | 多核 | multi_core_rings（凸字形再加 convex_core_path） |
   | 多体量不相连 | multi_rings_same_zone |
   | 裙房+塔楼 / 多层 zone | podium_tower + core_stack_alignment |
3. 对照 1 个金例（只读 design_intent.json）
   读 references/golden/index.json，按 type + implements 选 1 条
   再读 golden/<path>/design_intent.json
   默认对照：
   | type | 金例 |
   |---|---|
   | office | office_std_01 |
   | hotel | hotel_std_01 |
   | residence 规则凸出 | res_3c6u_std |
   | residence 斜墙切角 / 并排板式 | res_2s4u_std |
   | retail 圆角+中庭 | retail_mall_01 |
   | retail 长板异形 | retail_wanda_std |
   | single_family | floorplan_structure |

4. 写 design_intent（现行协议）——先写再问，不要先问再写
   form.path.rings[].edges.{west,north,east,south}
   segments: projection | recess | arc
   holes / core 数组（每项 path.rings）
   禁止 path.outer.base

**轮廓 = 户型策略的几何痕迹（通用引导，2026-08-17 提炼自金例）**：
户型策略每一条都必须在轮廓上留下凹凸，**主体以多点凹凸为基底**：
- 每户南向阳台/露台凸出 → 2 点凸出（如 res_2s4u `[17100,8225]→[13883,8586]`）
- 户间天井/凹口/错位 → 折回点（如 `[13989,990]→[19239,2299]`）
- 入口/门廊/台阶 → 局部凹或台阶（如 `[6759,876]→[0,724]`）
- 核心筒靠外墙凸出（住宅核筒井道）→ 边内大折或 projection（如 res_3c6u 北边 3 凸出，
  深 2.8~3.0m）
- 斜墙/大切角 → 直接写边多顶点（如 res_2s4u west 斜墙、east 大切角）
- 角部圆角/切角柔化 → `{"type":"arc","at_vertex":<下标>,"radius_m":<真实半径>}`
  （参照 hotel r=4.5m、retail_mall r=15.1m——办公塔/酒店/商业都可用，体量柔化常规手法）
- **判定**：写完后数轮廓顶点——每户/每组功能应有对应凹凸；南边只有 2 个角点 = 没表达
  户型，重写。参照 res_2s4u_std（南边 19 点）与 res_3c6u_std（北边 14 点）的凹凸密度。

5. 翻译 + 校验（FAIL 不回显、不 question；先自改，改不动才 question）
   .venv/bin/aiplan normalize --intent design_intent.json --lot '<lot>' > normalized.json
   .venv/bin/aiplan geom check --zones normalized.json --lot '<lot>' --setbacks '<setbacks>'
   # --zones 直接吃 normalized.json 落盘文件（也可内联）；area 同理吃 normalized.json
```

**校验契约（2026-08-17 明确，减少卡壳）**：
- **多 zone 全量一次校验**（推荐）：`aiplan geom check --zones <normalize产物>`——
  逐 zone 轮廓 + 跨层对齐一起跑；`--zones` 接受 normalize 顶层 `{"zones":[...]}` 或裸数组，
  **文件路径 / 内联 JSON 都吃**（normalize stdout 先落盘 `normalized.json` 再传路径）
- **单 zone 单核**：`check --outline ... --anchor '[x,y]'`（锚点是单个坐标对）
- **多核住宅/商业**：`check --zones` 自动逐核校验（`--anchor` 只吃单点）
- **同边多个 segments（阳台带/露台分段）**：offset+width 区间互不重叠，
  重叠 → normalize 报 `segment_overlap`（点名两段区间）；先错开 offset 再跑
- **align 只比较同一竖向栈**（position.on 链或轮廓重叠）的核——独立楼栋的核不互比，
  南排北排各自成栈；同栈核错位报 `核心筒[<id>] 锚点不一致`
- **无效几何会带 explain_validity 定位**（哪个 ring 自交）——按定位修，不盲猜
- **轮廓凸出必须守退线**：阳台/飘窗凸出后轮廓最外缘距地块边仍 ≥ 对应退线；
  `geom check` 报 `退线不满足: <方位> 距地块边 <n>mm < 要求 <m>mm` 时，
  把主体墙内移让凸出段落在退线内（凸出抵退线边缘），而非删凸出
- **normalize 产物格式**：`outer` 是 ring object `{vertices, arcs?}`——`area` 直接吃该产物，
  无需手工转裸数组

**人对段（仅此处可 question）**：机器 PASS 后，用建筑师语言回显形态策略 + 为什么
（引用 derive 字段=值），progress 放 question header/正文首行；选项确认/改轮廓/改核心筒。
第 2 轮可连续多个 question，中间不准夹叙述停顿。

> 判断必须写成 `derive字段=值 → 决策`，写入 `design_rationale`。

**核心筒**：
1. 有垂直交通核则 `core` 必填完整 rings（可数组）；独栋无核则声明省略
2. 跨层 shape 一致；顶层缩小走 zone_split
3. core ⊆ outline（不压 holes）
4. 回显前 `geom align`

**非几何信息（zone.note + 分裂联动）**：轮廓确认后问"有没有几何框不定的信息（开洞/额外设计）"：

| 需求 | 轮廓/功能实质变化？ | 处理 |
|---|---|---|
| **轮廓级孔洞**（中庭/天井） | 否（轮廓内几何） | `rings[].holes[]` 同 edges 四边（见 holes_courtyard）——不走 note |
| 楼板级开洞 / 贯通 / 挑空 | 否（属性级） | `zones[].note`（自然语言直录——位置/尺寸/朝向原话直录，不强行结构化） |
| **退台 / 设备层 / 中庭公共层** | **是** | **必须分裂新 zone**（S1-S3，见下） |

**分裂方法论 S1-S3**（退台/设备层/中庭公共层——轮廓/功能实质变化）：

| # | 原则 | 执行 |
|---|---|---|
| S1 | **分裂粒度** | 轮廓/功能**逐段变化 → 每段独立 id**（不合并） |
| S2 | **重走设计确认** | 新 zone **重走 几何/功能/配比/规范** 确认——不继承父 zone 结果 |
| S3 | **对齐保证** | 新 zone 核心筒/管井与父 zone **跨层对齐**（几何一致）——`geom align` 校验 |

分裂 zone 记入 `vertical_relations`（`type=zone_split`，含 parent/child/reason）。

## 第 3 轮 · 功能（连问批量，一整段草案 + 一个确认框）

**D 功能构成**：
- `zones[].typology_candidates`：候选拍板（候选集在 step-00/01 起草为文字描述空间逻辑与取舍）
- `zones[].program`：房间表（count / area_sqm 区间 / per_floor / includes / min_width_mm）

**E 面积配比**（`zones[].area_allocation[].{block, ratio, area_sqm, source}`）：
```
① 算 zone 总面积（outline_mm → shoelace）
   .venv/bin/aiplan area normalized.json '<program JSON>' '<type>'
   # outline 直接吃第 2 轮 normalize 产物（文件路径，ring object 自动解析）
② 查标准参考（ratio_standards：references/building_types/<type>.cases.json）
③ 对每个必填 block 弹占比确认（合并进第 3 轮批量，不逐 block 弹）
```
**配比检查**：所有 block 确认后跑 `check_allocation`——block 合计超总面积 → 报错回弹；
合计 <80% → 提醒"有大块面积未分块"。跨 zone 汇总回显。

**F 规范要求**：
- `requirements[].{subject, rule, strength}`
  - **rule 词表**：`references/predicate_vocabulary.md`（V3 扁平规则名唯一来源，不发明新规则名）
  - **subject 词表**：building_types 的 T2 词汇
- `standards.packs`：类型包引用（无匹配包 → T0 通用 + BY REVIEW，显式声明）
- `standards.overrides`：走廊宽度等覆盖
- `standards.emphases`：**自然语言直读**——回显用户原话，不二次解析

## 第 4 轮 · 结构空间（精问：两板块合并一轮）

**G 屋顶 + 特殊结构**：
- `roof.{type, slope_deg, ridge_h_m, overhang_m}`：精问合并一次问（roof 值域见自持
  `references/schemas/bim_supplement.schema.json` + `references/bim_param_defaults.md`）
- `special_structures[].{type,...}`：逐条确认（parapet/balcony/atrium/massing_twist/massing_mirror）
- `psets.{building, walls, slabs_roof, circulation}`：**直落层——不弹框**。
  按 `references/bim_param_defaults.md` §2 默认，回显带一句"psets 按类型标准默认"；用户不反对即落盘

**H 空间补充（space_notes）**：用户提到**难以 2D/结构化描述的空间信息** →
不强行结构化，直接进 space_notes（每条约 {subject, note, floors?, source}）。
**判定**：能结构化 → special_structures/roof；难结构化 → space_notes。
