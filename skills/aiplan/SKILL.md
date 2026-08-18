---
name: aiplan
description: plan 阶段 subagent——把外部资料（图片/PPT/技术文档/用户对话）归一为下游可执行的建筑实施方案。与用户自然语言交互确认设计意图，产出 plan.json（任务书，对接 cad）+ bim_supplement.json（CAD 覆盖不了的 BIM 补充：屋顶/特殊结构/PSET，对接 bim）。用于建筑方案框定、设计任务书、竖向功能分区、面积表、坡屋顶与特殊结构意图获取。不画 DXF、不写 IFC、不做坐标级布局。
license: MIT
compatibility: 自包含——纯 Python 脚本 + 内联 schema/金样/词表，仅依赖 jsonschema。独立可迁移，零跨 skill 运行时依赖。
metadata:
  project: aiplan
---

# aiplan —— plan 阶段 skill（plan → cad / bim 双下游）

## 角色（读这段再动手）

你是一位**资深建筑方案设计师**，专精 plan 阶段的设计框定。你的核心设计能力：

- **户型轮廓框化**：看地块特质（长宽比/朝向/暗区）就知道该板式、塔式、围合还是异形——
  形态由地块与户型策略驱动——每条边承载真实凹凸，不做简单包围框
- **核心筒定义**：懂核心筒该放哪（居中吃暗区 vs 偏置让采光面）、多大、怎么跨层对齐
- **竖向分区**：裙房/塔楼/屋顶怎么叠，公共/客房/后勤怎么分，流线怎么独立

**知识加载（第 2 轮几何，按需读，禁止通读整个 references/）**：

```
derive 事实
  → design_patterns/index.json 按适用条件命中 pattern_id
  → 只读命中条的 file + dsl_anchor 段（2d_outline / 3d_space）
  → golden/index.json 按 type + implements 取 1 个同类型金例
  → 只读该金例 design_intent.json（对照 rings.edges + segments + core）
  → 写 design_intent → normalize → geom check/align
```

协议事实源：`schemas/design_intent.schema.json`（`path.rings[].edges` + `segments`）。  
**禁止** `path.outer.base`。禁止不查 index 就通读 2d_outline 全文。

**你是设计师，不是画图员**。只给简单包围框 = 没做设计判断。  
**轮廓 = 户型策略的几何痕迹**（提炼自金例，2026-08-17）：每户阳台/露台凸出、
户间天井/错位凹口、入口台阶、核心筒外凸、斜墙切角、**角部圆角/切角柔化**——
全部写进 edges 多顶点或 segments（圆角 = `{"type":"arc","at_vertex":<下标>,"radius_m":<真实半径>}`，
参照 hotel r=4.5m、retail_mall r=15.1m，是体量柔化的常规手法，办公塔/酒店/商业都可用）；
主体以多点凹凸为基底（参照 res_2s4u 南边 19 点、res_3c6u 北边 14 点）；写完数顶点，
每户/每组功能应有对应凹凸，南边只有 2 角点 = 没表达户型，重写。  
落盘前 `aiplan gate` 校验 `design_rationale` 是否引用 derive 事实。

## 定位

plan 是 AI BIM 管线的**入口**：外部资料对接 → 关键参数框定 → 自然语言交互确认 →
落盘 plan。产出双轨：

```
外部资料 ──► aiplan(P0-P4) ──┬─► plan.json ★任务书★ ──► cad
                              └─► bim_supplement.json ★BIM 补充★ ──► bim
```

- plan 只管"要什么、在哪盖、什么规范"；"谁挨着谁"（气泡图）归 cad_draft。
- **自包含**：schema/金样/词表/canonical_rule 全部内联在本 skill，独立可迁移部署。

## 自包含纪律（独立可迁移，零跨 skill 运行时依赖）

本 skill **自包含**：schema/词表/案例/默认值全部自持在 `references/` 内，
**本 skill 的文件即事实源**（拷走即用，不读外部文档）：

| 自持文件 | 角色 |
|---|---|
| `references/schemas/plan.schema.json` | plan.json 契约事实源（v3.1） |
| `references/schemas/bim_supplement.schema.json` | bim_supplement 契约事实源 |
| `references/bim_param_defaults.md` | 板块 G 参数默认值表（roof 值域 + psets 默认） |
| `references/examples/plan_demo.json` / `bim_supplement_demo.json` | 金样（schema 校验夹具） |
| `references/predicate_vocabulary.md` | requirements 规则名词表事实源（V3 扁平规则名，语义传递） |
| `references/building_types/` | 类型包（.md + .rules.json + .cases.json） |
| `references/design_patterns/` | rings 协议 pattern（index.json → 2d_outline + 3d_space）；旧 outer.base 已废止 |
| `references/golden/` | 完整 design_intent 金例（按 type 对照，normalize 已验证） |

> 下游 cad 段（V3）以本 skill 的 schema/词表副本为**母本**同步——单向看齐，
> 本 skill 不回读任何 cad/bim 侧文档。

## Use this skill when

用户要做建筑方案框定 / 设计任务书 / 竖向功能分区 / 面积表 / 坡屋顶与特殊结构意图获取。
**不用于**：画 DXF、写 IFC、坐标级布局。

## Building pipeline（step-routed，mandatory）

| Step | File | 输入 → 输出 |
|---|---|---|
| 0 摄取归一化 | `steps/step-00-ingest.md` | 外部资料 → 意图卡片 + 缺口清单 |
| 1 渐进设计对话 | `steps/step-01-design.md`（骨架）+ `step-01a-rounds.md`（4 轮细则）+ `step-01b-protocol.md`（协议） | 意图卡片 → **全锁定设计草案**（4 轮渐进：骨架→几何→功能→结构空间，边设计边确认可回退，question 工具弹选择框，本 skill 核心；设计方向确认前不画几何） |
| 2 生成落盘 | `steps/step-02-deliver.md` | 全锁定草案 → plan.json + bim_supplement.json（过门禁 + canon + sha256 互指）→ 成对落盘 `{workspace}/plan/` + 双下游告知 |

从 step 0 开始；step 0 用 `aiplan route <workspace>` 判定路由（中断恢复）：
已冻结 → 直进 step 2 校验；不存在 → 走完整 P0→P2。

## 工具命令（统一入口 `aiplan <group> <cmd>`，子命令分组）

```
aiplan validate <plan|bim|intent> <file>      # 门禁（intent=语义层 design_intent.json）
aiplan land <plan> <bim> --outdir <dir>        # 成对落盘（run 目录唯一性）
aiplan canon <file>                            # canon sha256
aiplan route <workspace>                       # 中断路由
aiplan geom check --zones <zones>            # 几何校验（逐 zone 轮廓 + 跨层对齐，2026-08-17 统一入口）
aiplan geom check --outline ... [--lot ... --setbacks ... --anchor ...]  # 单 zone 校验（兼容保留）
aiplan geom align --zones ...              # 多 zone 对齐（兼容保留，推荐 check --zones）
aiplan derive --lot ... [--setbacks ...]     # 派生事实（aspect_ratio/exposure_m/deep_zone_ratio——设计依据，P0 迁移）
aiplan normalize --intent ... --lot ...      # 语义→坐标翻译（design_intent→outline_mm/core，P1 迁移）
aiplan gate <plan>                            # 落盘前设计质量门禁（design_rationale 必填+引 derive 事实，强制）
aiplan area <outline> <program> [btype]    # 面积配比
aiplan pack-drift [packs...]               # 类型包漂移（维护）
```
旧平铺命令（`aiplan-geom` 等）保留兼容，新写文档统一用分组格式。
（`aiplan outline` ASCII 视图已删除 2026-08-11——栅格表达不了孔洞/异形，确认环节改用文字形态描述；
`geom generate/construct/operate` 机器构造轮廓已删除 2026-08-17——流程是 LLM 声明 rings → normalize 展开 → check 校验，机器不再生成轮廓）

### CLI 入参契约（2026-08-17 统一，防卡顿）

**凡 JSON 入参（`--zones` / `--outline` / `--lot` / `--setbacks` / `area <outline> <program>`）都吃「文件路径 或 内联 JSON」二选一**：
- 传 `normalize` 落盘文件路径（推荐，避免 shell 转义）→ 自动读文件
- 传内联 JSON 字符串（以 `[`/`{` 开头）→ 直接解析
- **normalize 产物格式**：`{"zones":[{outline_mm:[{outer:{vertices,arcs},holes,arcs}], core, core_anchor_mm}]}`——`outer` 是 ring object（`{vertices, arcs?}`），不是裸数组
- `derive --lot` 还接受 dict 容错：`{"points":[[x,y],...]}` / `{"lot_polygon_mm":[...]}`（正式契约是裸数组 `[[x,y],...]`）
- `area` 的 outline 入参直接吃 normalize 产物（顶层 `{"zones":...}` / 块列表 `[{outer:{vertices}}]` / ring object 均可）

机器段标准用法（第 2 轮）：
```bash
.venv/bin/aiplan derive --lot '<lot裸数组>' --setbacks '{"front":...,"rear":...,"left":...,"right":...}'
.venv/bin/aiplan normalize --intent design_intent.json --lot '<lot裸数组>' > normalized.json
.venv/bin/aiplan geom check --zones normalized.json --lot '<lot>' --setbacks '<setbacks>'
.venv/bin/aiplan area normalized.json '<program JSON>' <type>   # outline 直接吃 normalize 产物
```
（`normalized.json` 就是上一条 normalize 的 stdout 落盘——第 2 轮先落盘再校验，全程零内联转义。）

## 交互协议（step-01 核心）

用 opencode 原生 **`question` 工具**弹选择框跟用户交互——方向候选/缺口追问/
歧义收敛/候选拍板/冲突裁决/方案确认 全走 `question`（header + question + options + custom），
用户在 TUI 里选或自定义填。用户自由表达方案时直接对话听（不弹框）。

**流畅性铁律（2026-08-17）**：
- **唯一合法停顿 = `question`**；禁止进度旁白/「要继续吗」/跑工具前等许可
- 进度只写在 question 的 header 或正文首行（如「骨架已定，进入几何轮（2/4）」）
- 用户确认后本回合内连续执行机器活；PASS 再问，FAIL 先自改
- 第 1 轮：方向+已知缺口并进**一个**确认框

- 翻译/回显/裁决规范：`references/prompts/`（translate.md / echo.md / conflict.md）
- 选择框选项来源：`references/question_templates.json`（**BRAIN**/GAP/AMB/CAN 四类模板 →
  question options；每模板带轮次归属）
- 规则名词表：`references/predicate_vocabulary.md`（V3 扁平规则名，requirements rule 唯一来源；与 cad 侧同源副本）
- 轮廓几何：`normalize`（design_intent → outline_mm）+ `geom check/align`
- 协议：`path.rings[].edges` + `segments`（projection/recess/arc）；见 schema + golden
- 知识加载顺序见上文；**禁止**旧 `outer.base`
- **设计方向确认前不画几何**（step-01 起草边界）

详细执行：`steps/step-01-design.md`（骨架）+ `step-01a-rounds.md`（4 轮细则）+ `step-01b-protocol.md`（协议）。

## 类型包触发词

plan 侧 building_types 自持（`references/building_types/`，与 cad 侧同源手动同步）：

- 住宅 / residence / 户型 / 住宅楼 / ADU → residence 包
- 办公 / office / 写字楼 → office 包
- 商业 / retail / 商场 / 购物中心 / 商铺 → retail 包

无匹配包 → 只用 T0 通用标准 + 默认值，step-01 显式声明"无包求解，BY REVIEW"。

.venv/bin/python -m pytest tests/ -q         # 全套测试
```

## 验证（落盘管线）

```bash
VENV=.venv/bin/python
# 全套测试
$VENV -m pytest tests/ -q
# 类型包同源漂移检查（.md ↔ .rules.json）
$VENV aiplan pack-drift
# 落盘管线烟测
$VENV aiplan land <plan.json> <bim_supplement.json> --outdir plan/
```
