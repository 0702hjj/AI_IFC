# AI_IFC 迭代计划 v1

**日期：** 2026-08-03  
**状态：** 设计草案  
**参考：** agent-browser（vercel-labs）skill 分发、superpowers（obra）多 harness 安装、frp-panel README 风格

## 1. 背景与目标

AI_IFC 已完成 aiifc skill 开发、打包器 tool、CI Python job 集成和文档站 skill 页面。当前状态：

- skill 分发结构是简单的 tar.gz 打包，没有 discovery stub / templates 等分层
- API 路径无版本号，Go server 用 `/api/models`，edit-service 用 `/models` 不一致
- CI 只有 converter/server/web/smoke/edit-service/skill-pack 六个 job，缺少测试整合
- 文档已漂移（部分路径/依赖描述过时），无 screenshots/videos 展示层

本次迭代计划覆盖这四个方面。

## 2. 迭代一：完善 skill 分发结构

**参考来源：** agent-browser（discovery stub + per-domain skills）、superpowers（npm 分发 + multi-harness 安装）

### 2.1 改动

- `skills/aiifc/SKILL.md` 重写为**发现桩**（~50 行）：只包含 skill 定位、加载方式、`hidden: true`（避免污染自动发现列表），主体内容由 `skills/aiifc/references/` 各文档承载
- 新增 `skills/aiifc/templates/`：从现有 `flows/` 选几个可独立运行的模板（skeleton/wall/opening 组合），与 agent-browser 的 `templates/` 对齐
- `README.md` 补**多 harness 安装说明**：opencode（`skills.paths`）、Claude Code（`~/.claude/skills/`）、Cursor 等，各给一条命令
- 打包器 `tools/skill_pack_aiifc.py` 不变（校验 + tar.gz 分发包仍是分发基底）

### 2.2 验收

- SKILL.md 发现桩 ≤ 60 行
- 安装说明覆盖 ≥ 3 个 agent（opencode / Claude Code / Cursor）
- `templates/` 目录存在，含 ≥ 2 个可运行模板
- 打包器产物仍能通过 CI 校验

## 3. 迭代二：API 统一版本化

**目标：** Go server 作为唯一对外入口，全部业务/编辑/chat 端点在 `/api/v1/{resource}/{id}` 之下。edit-service 的 `/models/...` 作为内部实现，通过 Go 代理层前缀转换。

### 3.1 路由映射

| 当前（Go） | 新（/api/v1/） | 说明 |
|---|---|---|
| `GET /api/models` | `GET /api/v1/models` | 模型列表 |
| `POST /api/models` | `POST /api/v1/models` | 上传创建 |
| `GET /api/models/{id}` | `GET /api/v1/models/{id}` | 模型详情 |
| `DELETE /api/models/{id}` | `DELETE /api/v1/models/{id}` | 删除 |
| `POST /api/models/{id}/retry` | `POST /api/v1/models/{id}/retry` | 重试转换 |
| `GET /api/models/{id}/changes` | `GET /api/v1/models/{id}/changes` | 变更日志 |
| `GET /api/models/{id}/overrides` | `GET /api/v1/models/{id}/overrides` | override 列表 |
| `POST /api/models/{id}/overrides/migrate` | `POST /api/v1/models/{id}/overrides/migrate` | 迁移真改 |
| `PUT /api/models/{id}/entities/{entityId}/properties` | `PUT /api/v1/models/{id}/entities/{entityId}/properties` | override 属性 |
| `PUT /api/models/{id}/edit/entities/{guid}` | `PUT /api/v1/models/{id}/edit/entities/{guid}` | 真改 pending |
| `GET /api/models/{id}/edit/pending` | `GET /api/v1/models/{id}/edit/pending` | pending 列表 |
| `DELETE /api/models/{id}/edit/pending` | `DELETE /api/v1/models/{id}/edit/pending` | 清 pending |
| `POST /api/models/{id}/edit/commit` | `POST /api/v1/models/{id}/edit/commit` | commit |
| `GET /api/models/{id}/edit/history` | `GET /api/v1/models/{id}/edit/history` | 编辑历史 |
| `GET /api/models/{id}/edit/versions` | `GET /api/v1/models/{id}/edit/versions` | 版本列表 |
| `POST /api/models/{id}/edit/diff` | `POST /api/v1/models/{id}/edit/diff` | diff |
| `GET /api/models/{id}/issues` | `GET /api/v1/models/{id}/issues` | Issue 列表 |
| `POST /api/models/{id}/issues` | `POST /api/v1/models/{id}/issues` | 创建 Issue |
| `PATCH /api/models/{id}/issues/{issueId}` | `PATCH /api/v1/models/{id}/issues/{issueId}` | 更新 Issue |
| `DELETE /api/models/{id}/issues/{issueId}` | `DELETE /api/v1/models/{id}/issues/{issueId}` | 删除 Issue |
| `POST /api/chat/projects` | `POST /api/v1/projects` | 创建空白项目 |
| `POST /api/chat/sessions` | `POST /api/v1/chat/sessions` | 创建会话 |
| `GET /api/chat/sessions` | `GET /api/v1/chat/sessions` | 列表 |
| `POST /api/chat/sessions/{cid}/messages` | `POST /api/v1/chat/sessions/{cid}/messages` | 发消息 |
| `GET /api/chat/sessions/{cid}/messages` | `GET /api/v1/chat/sessions/{cid}/messages` | 历史 |
| `GET /api/chat/sessions/{cid}/events` | `GET /api/v1/chat/sessions/{cid}/events` | SSE 事件流 |
| `POST /api/chat/sessions/{cid}/abort` | `POST /api/v1/chat/sessions/{cid}/abort` | 中止 |
| 静态资源 `/models/{id}/model.xkt` | `/v1/models/{id}/model.xkt` | 静态文件（无 `/api` 前缀） |
| 静态资源 `/models/{id}/metadata.json` | `/v1/models/{id}/metadata.json` | 同上 |
| 静态资源 `/models/{id}/issues/{file}` | `/v1/models/{id}/issues/{file}` | 同上 |
| Issue 截图 `/api/models/{id}/download` | `/api/v1/models/{id}/download` | 下载 |

### 3.2 兼容策略

**直接破旧立新，不保留旧路由别名**。理由：
- 目前无外部消费者（文档站指向的 API 文档会同步更新）
- 保留旧路由是纯维护负担，且前端 `client.ts` 和 smoke.sh 是唯一调用方，改动可控
- smoke.sh 和前端 client.ts 随本次迭代同步更新

### 3.3 涉及文件

- `server/internal/api/*.go`（路由注册）
- `web/src/api/client.ts`（前端调用）
- `scripts/smoke.sh`（端到端测试）
- `docs/site/reference/rest-api.md` + `en/`（文档站 API 文档）
- `docs/site/reference/edit-api.md` + `en/`
- `docs/site/reference/ai.md` + `en/`（AI 接入文档里的路径）
- `docs/site/reference/ai-skill.md` + `en/`（skill 文档里的路径）
- `docs/internal/team-sync.md` 等内部文档

### 3.4 验收

- 全部新路由注册且能返回 200
- 旧路由返回 404 或 301
- 前端模型库/查看器/聊天全流程可走通
- smoke.sh 全绿
- 文档站 API 文档路径已更新

## 4. 迭代三：彻底重构 CI/测试

### 4.1 测试目录整合

- skill 打包测试 `test_skill_pack.py` + `test_skill_pack_aiifc.py` 收拢到 `tests/skill/`
- CI `skill-pack` job 改指 `tests/skill/`
- SCAD 测试（`test/` 其余 33 文件 + `tests/` 2 文件）保留不动，标注归档

### 4.2 CI 各 job 职责

| Job | 触发条件 | 内容 |
|---|---|---|
| `converter` | PR + push main | Node IFC→XKT 测试 |
| `server` | PR + push main | Go vet + race test |
| `web` | PR + push main | vitest + build |
| `edit-service` | PR + push main | Python pytest 38 |
| `skill-pack` | PR + push main | 打包测试 + flows 冒烟 + IFC 校验 |
| `smoke` | PR + push main | 端到端（upload→convert→issue→edit→diff） |

### 4.3 新测试内容

- `tests/skill/test_flows_smoke.py`：skeleton/wall/full_building 等 flows 在隔离目录跑，输出 `model.ifc` 过 `ifcopenshell.validate`
- `tests/skill/test_skill_pack_aiifc.py` + `test_skill_pack.py`：现有打包测试（无改动，只移动）

### 4.4 验收

- `tests/skill/` 目录存在，pytest 全绿
- CI 所有 job 全绿
- `test/` 和 `tests/` 的 SCAD 测试未受影响

## 5. 迭代四：文档更新 + 展示层

### 5.1 文档审计与清理

按优先级逐文档审查：

1. **高优先级（外部可见）**：`docs/site/reference/ai.md`、`docs/site/reference/edit-api.md`、`docs/site/reference/rest-api.md` 中的路径/依赖说明——API 变更后必须更新
2. **中优先级（内部可读）**：`docs/internal/team-sync.md`、`docs/internal/architecture/roadmap.md`、`viewer/README.md`、`services/ifc/README.md`——路径/依赖描述同步
3. **低优先级（归档）**：`docs/archive/`、`docs/superpowers/`、`research/`——标记过时或不更新

### 5.2 screenshots/videos

参考 frp-panel 的 README 风格，在 README 和 docs 站点首页/入门页面嵌入：

- **截图**：模型库页面、三维查看器（含剖切/测量）、属性编辑面板、Diff Viewer、聊天侧边栏
- **视频（可选）**：端到端工作流（上传→审查→编辑→commit→diff）+ AI 对话生成模型

**前提**：前端 UI 稳定（API 版本化后不破坏 UI 调用路径）

### 5.3 验收

- 文档站无路径/依赖过时内容
- README 首屏有截图 3-5 张
- 文档站首页有截图轮播或 feature 卡片配图

## 6. 后续展望

### 6.1 中期：前端参数化编辑（改 design JSON，类 Revit 体验的轻量版）

**2026-08-03 探讨结论：** 方向从「前端直接编辑 IFC 几何」调整为「**前端编辑生成 IFC 的 design JSON（语义参数层）**」。理由：

- 现有三层架构 `design JSON（意图，无坐标）→ design_builder → features.json → build_script_template.py → IFC` 中，**design JSON 天然是参数化编辑面**——它描述「墙轴 / 洞口沿轴位置 / 厚度 / 层高」而非坐标，正是前端 UI 需要的语义
- py 代码（build_script_template）是**实现层**，作为只读真相源，不应被前端直接修改
- 这比「前端直接改 IFC 几何」实现成本低一个量级，且与 aiifc skill 的 design JSON 框定完全打通

**编辑链路（建议）：**
```
前端选择构件（xeokit picking）
  → 后端把构件（GlobalId）映射回 design JSON 条目（storey + wall/opening index）
  → 前端显示参数表单（沿轴位置/尺寸/厚度/类型）
  → 用户改参数 → 更新 design JSON
  → 重跑 design_builder + build_script_template → 新 IFC
  → commit → 版本快照 → XKT 重转
```

**核心难点：** IFC 构件（GlobalId）↔ design JSON 条目（storey+index）的**映射层**——生成时需在 build_script_template 里为每个构件写入可回溯的标识（如 GlobalId 关联 design JSON 坐标 + 索引）。

**前置条件：**
- aiifc skill 的 design JSON 框定流程成熟（迭代一）
- 构件 ↔ design JSON 的映射机制设计（可在本迭代的 skill 工作中预留）
- 用户需求验证（确认痛点是否真的是几何参数调整）

**与「类 Revit 在线几何编辑」（真正的自由几何推拉）区分：** 那是远期独立项目，需要前端几何内核，不在本路线内。

### 6.2 后续：计划 → 2D DXF → IFC 完整工作流（与 6.1 互补）

**建议路线：**
1. aiifc skill 的 design JSON 增加 2D 平面图输出字段（已有 wall axis/outline 等基础）
2. 用 ezdxf 从 design JSON 生成 2D DXF（前端可用 svg 预览）
3. 复用 `research/ifc/` 的 cad-to-shapely→IfcOpenShell 调研底稿，把 DXF 作为 IFC 生成的输入而非终点
4. 最终形态：用户说需求 → design JSON → 2D 平面图预览 → 确认 → 生成 IFC → 进入平台编辑流程（含 6.1 的参数化编辑）

**与 aiifc skill 的关系：** design JSON 是已有环节，补 2D 输出是自然扩展，不破坏现有结构。

**与 6.1 的关系：** 6.1 提供「改参数 → 重生」的编辑闭环；6.2 提供「从 2D 平面图起步」的生成入口。两者共享 design JSON 作为中心，可并行推进。

## 7. 里程碑与顺序

| 迭代 | 依赖 | 预估时间 |
|---|---|---|
| 一：skill 分发 | 无 | 1-2 天 |
| 二：API 统一 | 无 | 2-3 天 |
| 三：CI/测试 | 迭代二（API 稳定后） | 1-2 天 |
| 四：文档 + 展示 | 迭代二/三（内容稳定后） | 2-3 天 |

总周期：约 1-2 周（按实际可用时间调整）。