# 平台框架：两个对等逻辑（IFC / CAD）+ Agent 工作流推荐项

> 日期：2026-08-11 · 状态：定稿（用户裁决 2026-08-11）
> 前置：W-0017（orchestrator）、W-0025（事件 URI 化）、docs/superpowers/specs/2026-08-11-orchestrator-design.md

## 1. 定位

本仓库是**可复用性优先**的 AI 生成平台，提供两个**对等**逻辑，外加一个**推荐形式**（可选，做不好可删）：

| 项 | 内容 | 当前状态 |
|---|---|---|
| **逻辑一：AI 生成 IFC** | skill 封装 + Python diff + 面向前端修改的接口协议 | 已交付（`skills/aiifc/` + `viewer/edit-service/` 的 diff 与 script-as-source 编辑 API） |
| **逻辑二：AI 生成 CAD** | 完全类似的 skill 封装 + 对应 diff + 面向前端修改的接口协议 | 部分交付（`AI_CAD/skills/aidxfv*` 纯 skill 域；diff 与前端接口协议待补） |
| **推荐形式：Agent 工作流控制** | orchestrator（意图路由 + 子 Agent）+ 事件总线 | 方向已定（W-0017 spec）；落地可选，做不好可删 |

两逻辑**对等**：不是「IFC 为主、CAD 附属」，而是各成一套「skill → 业务逻辑（diff + 接口协议）→ 可选运行时」的闭环。平台对外的承诺是两套接口协议可独立调用、可移植。

## 2. 可复用性原则（用户裁决 2026-08-11）

1. **skill 封装两个**：`aiifc`（IFC 生成/修改）、`aidxfv`（CAD 生成/修改）——agent-agnostic、可分发。
2. **业务逻辑封装两个**：`services/ifc`（IFC 的 diff 与面向前端修改的接口协议）、`services/cad`（CAD 的 diff 与面向前端修改的接口协议）——与 skill 一一对应。
3. **前端可选实现**：viewer 前端是参考实现，不是平台本体；接口协议写好后任何前端（自研/第三方）都能对接。
4. **后端 PG 可选实现**：PostgreSQL 是可插拔存储，默认文件存储零依赖可跑。
5. **共用运行时骨架**：两逻辑共享同一套运行时（Go 网关 + FastAPI 业务服务 + 转换器），新逻辑复用骨架而非复制。
6. **接口可直接调用或移植**：业务逻辑核心与运行时解耦，单逻辑可独立部署。

## 3. 功能块结构（横切）

按功能块横切（而非按 IFC/CAD 纵切），共享件只落一份：

```
skills/            # ① AI 生成 skill 封装（agent-agnostic，可分发）
  aiifc/           #   IFC 生成/修改（ifcopenshell）
  aidxfv/          #   CAD 生成/修改（ezdxf + vendored cadpy/archdxf）
services/          # ② 业务逻辑核心（diff + 面向前端修改的接口协议）
  ifc/             #   IFC 段：diff 引擎 + script-as-source 编辑 API
  cad/             #   CAD 段：diff 引擎 + 编辑 API（待建，与 ifc 同构）
web/               # ③ 前端（可选实现；两逻辑共用 viewer 交互体验）
server/            # ④ Go 网关（REST 入口 + 编排 + 存储抽象）
converter/         # ⑤ 格式转换（IFC→XKT 等）
pg/                # ⑥ PostgreSQL（可选实现）
tools/             # ⑦ skill 打包器 / 契约工具
docs/              # 文档站 + 工作看板 + spec
```

对应关系：`skill ×2` ↔ `services ×2` ↔ 共享 `web / server / converter / pg`。

## 4. 当前 → 目标映射（渐进收敛，不搬家）

| 目标 | 当前物理位置 | 说明 |
|---|---|---|
| `skills/aiifc` | `skills/aiifc/` | 已就位 |
| `skills/aidxfv` | `AI_CAD/skills/aidxfv1/`、`aidxfv2/` | 渐进收敛（AI_CAD 下多版本并存），搬入 `skills/aidxfv/` |
| `services/ifc` | `viewer/edit-service/` | IFC 业务逻辑核心（diff + 编辑 API），目录名保留为历史别名 |
| `services/cad` | （待建） | CAD 段业务逻辑核心，与 `services/ifc` 同构 |
| `web` | `viewer/web/` | 前端（可选实现） |
| `server` | `viewer/server/` | Go 网关（共用运行时骨架） |
| `converter` | `viewer/converter/` | 格式转换（共用） |
| `pg` | `viewer/server/internal/{store,override,change,issue}/pgstore.go` | PostgreSQL 可选存储 |
| `AI_CAD/research` | `AI_CAD/research/` | 调研材料，保留原目录 |

**渐进规则**：
- 存量目录（`viewer/`、`AI_CAD/`）物理位置**不动**，避免破坏 git 历史与 CI；新逻辑按目标结构落位。
- 文档与契约按目标结构表述（README/AGENTS/docs 用 `services/ifc`、`skills/aidxfv` 指代），物理路径作为实现细节。
- `AI_CAD/` 逐步收敛：skill 部分迁入 `skills/aidxfv/`（保留 MIT 归属），research 保留；收敛完成前以 `skills/aidxfv/` 为正式入口。

## 5. Agent 工作流控制（推荐形式）

- **定位**：推荐项，不是平台本体；做不好可整体删除，不影响两逻辑。
- **内容**：orchestrator（意图路由 + 子 Agent 封装 + 结果汇总）+ 事件总线（`aiifc://` URI 规约 + Pure Core/Shell）。设计见 `2026-08-11-orchestrator-design.md`。
- **落地节奏**：notify 事件化（已随 2026-08-11 迭代交付）→ orchestrator 骨架（M6，可选）→ 子 Agent 接入（M6+，可选）。

## 6. 里程碑

| 里程碑 | 内容 | 依赖 |
|---|---|---|
| v0.3（2026-08-11） | 框架定位入约（本 spec + README/AGENTS/docs）+ notify 事件化 + deferred minors 清扫 | 本 spec |
| M6（可选项） | `services/cad` 业务逻辑核心搭建（diff + 编辑 API，与 ifc 同构） | v0.3 |
| M6+（可选项） | CAD skill 收敛入 `skills/aidxfv/`、CAD 前端接入、Agent 工作流骨架 | M6 |
| M7+ | A2A 出口 / Eino 决策点（见 orchestrator spec §4.2） | M6+ |

> 框架的两个逻辑是长期承诺；Agent 工作流控制在每个里程碑评审时可删可留。
