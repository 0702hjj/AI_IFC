---
name: aidxfv3
description: plan→cad 建筑平面管线 v3——接 aiplan 落盘的 plan.json，LLM 声明骨架/房间 DSL，机器做确定性工作（派生/锚定/校验/渲染/检索），产出 skeleton/rooms/DXF/building.json。用于建筑平面图/户型/标准层/办公/住宅/商业平面生成。两段式四步：JSON 先行 → 断点确认 → worker 逐构件画 DXF。
version: 0.1.0
license: MIT
compatibility: 自包含——纯 Python 包（floorgeom/dxfkit/goldlib/flowops）+ 内联 schema/词表/类型包，依赖 ezdxf + shapely。独立可迁移，零跨 skill 运行时依赖。
metadata:
  project: aidxfv3
---

# aidxfv3 —— plan→cad 建筑平面管线 v3（LLM 设计 × 机器锚定）

## 角色

你负责 **plan→cad 建筑平面管线**：接收 aiplan 的 plan.json（任务书，只读），
按 S0-S4 生成建筑平面 DXF。核心分工：

- **LLM 主导设计**：声明 skeleton.json（骨架：分区/核心筒/走廊/切割线/blocks）
  与 rooms.json（房间：承接分区/画墙/标签）——说哪里/多大/邻着谁，坐标交给机器
- **机器做确定性工作**：派生/锚定/校验/渲染/检索全机器——`aidxfv3 normalize`
  是唯一坐标计算点（分层外推/差集/切割/墙解析/沿墙定位）

**执行方式**：每一步用工具实际运行 `aidxfv3` 命令、读取真实产出、把产出落盘。
命令的运行结果（文件/退出码/JSON）是本 skill 的工作对象。

## 定位

cad 是 AI BIM 管线的中段：上游 aiplan 落盘 plan.json（任务书）→ 本 skill 生成
逐层 DXF + building.json（工程图纸 + bim 接口）→ 下游 bim 消费。

```
aiplan(plan.json) ──► aidxfv3(S0-S4) ──► building.json + 逐层 DXF + 封存 rooms ──► bim
```

- 职责：把 plan 的设计意图落地成可交付的平面图
- `plan.json` 只读输入，全程不改

## 自包含

schema/词表/类型包/金例全部自持在 `references/` 内，本 skill 的文件即事实源（拷走即用）：

| 自持文件 | 角色 |
|---|---|
| `references/schemas/` | 契约（plan 副本 / skeleton / rooms / building，schema 即事实源） |
| `references/prompts/` | 主 agent + worker 行为规范（skeleton/breakpoint/dispatch/floor_rooms/floor_details） |
| `references/building_types/` | 类型包（.md + .cases.json + skeleton_patterns） |
| `references/room_patterns/` | 房间写法库（index.json + 各 pattern md） |
| `references/golden/` | 金例（skeleton/rooms/readback/replay，真实图纸产物） |
| `references/draw_api.md` / `draw_composition.md` | 画图调用面 + 整层组装序 |
| `references/machine_contract.md` | **机器命令契约**：CLI 输入输出 schema + 边界行为 + 退出码 + 归一化陷阱 |
| `references/vocabulary/` | 谓词词表 |

## 信息源

模型执行所需的一切事实源都在 `references/` 内，按需取用、够用即止：

- **命令怎么工作**（schema / 边界行为 / 退出码 / 归一化陷阱）→ `references/machine_contract.md`
- **画图调用面**（逐构件函数签名）→ `references/draw_api.md` + `references/draw_composition.md`
- **设计规范**（骨架/房间/断点/类型包/房间写法/词表）→ `references/prompts/`、`references/building_types/`、`references/room_patterns/`、`references/vocabulary/`、`references/schemas/`
- **金例**（真实产物可参照套用）→ `references/golden/` 或 `aidxfv3 gold query`
- 每个 step 开头有「信息源」清单，列出本步需要的文件——照清单读即可完成任务

拿不准时按序取：step 的「信息源」清单 → 对应 references 文件 → `aidxfv3 gold query` 看金例 → 跑命令看真实产出。

## Use this skill when

用户要做建筑平面图 / 户型图 / 标准层 / 办公 / 住宅 / 商业平面生成（plan→cad）。
**适用边界**：画方案泡泡图归 aiplan、写 IFC 归 bim、坐标级布局由机器完成。

## Building pipeline（step-routed，mandatory）

| Step | File | 输入 → 输出 |
|---|---|---|
| 0 预处理 | `steps/step-00-preprocess.md` | plan.json → derived/（floors + zone 包 + skeleton_base 底座）→ **断点⓪** |
| 1 骨架设计 | `steps/step-01-skeleton.md` | derived/ → skeleton.json（声明）→ **断点①** |
| 2 房间设计 | `steps/step-02-rooms.md` | skeleton → rooms.json（承接分区画墙）+ floor.dxf → **断点②** |
| 3 细节 | `steps/step-03-details.md` | rooms → floor.dxf（门窗统一规律 + 柱网 + 标注） |
| 4 交付 | `steps/step-04-deliver.md` | 全部层 → building.json + 逐层 DXF + 封存 rooms |

从 step 0 开始。

## 进度编排（多 zone / 中断恢复）

**分工**：
- subagent 派发/回收由主 agent 用**原生 agent 协议**（task 派发，subagent 完成回来汇报）。
- `aidxfv3 state` 负责**状态记录**：补缺 mission、按产物推进、恢复对账。

**推进规则（`aidxfv3 state advance`）**——产物驱动，逐级到位：
`rooms.json → declared`；`+ geom.json → presented`；`+ floor.dxf → built`；
`+ readback.json + geom_check.json(PASS) → done`。

**多 zone（异楼层裙房/塔楼）**：`floors.json#dag.edges` 恒空，各 zone 独立 mission 并行。S2 起：
```
aidxfv3 state sync --project <dir>     # 补出全部 zone 的 mission
# 主 agent 逐个 task 并行派发 subagent，产物落 missions/<zone>.rooms/
```

**中断恢复**：`aidxfv3 state reconcile --project <dir>` 汇总全部 mission 真实状态，按
`references/prompts/orchestrator/dispatch.md` 恢复路由继续。

## 工具命令（统一入口 `aidxfv3 <cmd>`）

```
aidxfv3 preprocess --plan <plan.json> --out <derived>   # S0：校验+派生+归并+zone 打包（plan.json 路径外部传入）
aidxfv3 validate --dsl skeleton.json                 # schema 门禁（exit 2 = SchemaError）
aidxfv3 normalize --dsl skeleton.json                # DSL → 几何坐标（唯一坐标计算点）
aidxfv3 check --dsl skeleton.json --plan <plan.json>   # 骨架级机检（分区越轮廓/blocks/holes）
aidxfv3 pack --node <zone>.<stage> --project <dir>   # mission 渲染（zone 切片+知识注入）
aidxfv3 state sync       --project <dir>             # 对照 floors.json#dag.nodes 补缺全部 zone mission
aidxfv3 state advance    --project <dir> --node <zone>.rooms   # 按产物推进单 mission 状态
aidxfv3 state reconcile  --project <dir>             # 中断恢复：扫 missions/ 汇总真实状态
aidxfv3 readback --dxf floor.dxf                     # DXF → 房间图（对账输入）
aidxfv3 reconcile --decl rooms.json --graph <回读图> # 声明 vs 底稿对账
aidxfv3 draw ...                                     # archdxf 逐构件画法（worker 调用）
aidxfv3 sync / deliver                               # 编辑回收 / 封存 + building.json
aidxfv3 gold query --params '{"kind":"case","type":"office"}'   # 参考库检索
```

## 交互协议（断点 = question 确认）

用 opencode 原生 **`question` 工具**弹框确认——断点⓪/①/②、缺口追问、冲突裁决
全走 `question`（header + question + options + custom），用户在 TUI 里选或自定义填。

**流畅性铁律**：
- 合法停顿只有 `question`（断点⓪ S0 确认 / 断点① 骨架 / 断点② 房间）
- 进度写在 question 的 header 或正文首行
- 断点确认后本回合内连续执行机器活；PASS 再问，FAIL 先自改

- 断点规范：`references/prompts/orchestrator/breakpoint.md`
- 调度回收：`references/prompts/orchestrator/dispatch.md`
- 骨架设计：`references/prompts/orchestrator/skeleton.md`
- worker 规范：`floor_rooms.md`（房间分墙）/ `floor_details.md`（门窗统一规律）

## 类型包触发词

- 住宅 / residence / 户型 / 住宅楼 → residence 包
- 办公 / office / 写字楼 → office 包
- 商业 / retail / 商场 / 购物中心 / 商铺 → retail 包
- 独栋 / single_family / ADU → single_family 包

## 验证

```bash
cd skills/aidxfv3 && .venv/bin/python -m pytest tests/ -q
```
