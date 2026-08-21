# W-0054: project 管理相关更新——chat 项目生命周期 + 模型注册 + 前端入口

- **状态：** open
- **优先级：** P1
- **Milestone：** v0.13（见 PLAN-v0.1.0.md）
- **来源：** 2026-08-21 用户裁决：「还有的话，是目前 project 管理相关的更新」
- **执行者/分支：** （领取时填）

## 背景

project 管理随 agent 接入一起演进，目前是「chat 项目」+「平台模型」两套并存但管理 API 不完整：

**现状（2026-08-21 摸底）**：
- 项目创建/删除：`POST /api/v1/chat/projects` + `DELETE /api/v1/chat/projects/{id}`（chat.go:101-102），前端 `web/src/api/client.ts` 已接（createChatProject/deleteChatProject）。
- 项目数据：`{DATA}/projects/{projectID}/project.json`（`store/project.go`：Create / CreateWithKind / AddModel / Get / List / Delete）。`kind` 支持 ifc / cad / cad->ifc（cad->ifc 创建时自动绑 ifc 骨架模型）。
- 模型注册：`store.Project.AddModel(id, modelID, kind, name, status)`；agent 端 `init_model` 工具创建骨架模型并分配 modelId 绑进项目。
- plan 文件：`GET/PUT /api/v1/projects/{projectID}/{name}` + plan_history + diff + deliver（chat.go:105-109）。
- 项目模型列表 REST：**只有内部 List**，无独立「项目详情/项目下模型列表」REST 端点。

**已知缺口（待本 item 系统化）**：
1. **项目模型列表/详情 REST 缺失**：前端看不到「这个项目下有哪些模型」——只有 agent 内部 get_project_models 工具，无公开 REST。
2. **模型从项目解绑/删除**：`AddModel` 有，无 `RemoveModel`；删除平台模型（`DELETE /api/v1/models/{id}`）不会从项目 project.json 摘除 → 孤儿 modelId。
3. **项目列表前端入口**：前端只有 create/delete chat 项目，无项目列表 UI（LibraryPage 是模型库，不是项目库）。
4. **kind 流转**：项目 kind 是创建时定死的（ifc/cad/cad->ifc），后续能否演进（ifc→cad->ifc）无规则。

## 涉及位置

- `server/internal/store/project.go`（Create/CreateWithKind/AddModel/Get/List/Delete）
- `server/internal/api/chat.go`（project 路由注册）· `chat_orchestrator.go`（createProject）· `chat_tools.go`（createProjectForAgent）
- `server/internal/agent/tools.go`（init_model / get_project_models / deliver_plan / deliver_building）
- `web/src/api/client.ts` · `web/src/pages/LibraryPage.tsx`（项目入口候选）
- `api_regulation.md`（REST 契约红线——新增端点必须 envelope + 契约测试）

## 方案

1. **项目详情/模型列表 REST**：加 `GET /api/v1/chat/projects/{id}`（envelope：project + models 列表）+ 可选 `GET /api/v1/chat/projects`（列表）；对照 api_regulation.md 的 REST 7 路由红线设计路径。
2. **模型解绑**：`RemoveModel` + 平台模型删除时联动摘除项目引用（或删除时检查项目引用拒绝/警告）。
3. **前端项目入口**：LibraryPage 加「项目」视图（列表/新建/删除/看项目下模型），或 ChatSidebar 加项目选择。前端改动需评估（前端零改动是 chat 契约红线，但项目 UI 是新功能）。
4. **kind 流转规则**：明确项目 kind 是否可演进 + 规则。

## 验收标准

- 项目详情 REST（含模型列表）上线，envelope + 契约测试。
- 模型删除联动：删除平台模型后项目 project.json 无孤儿 modelId（或明确拒绝策略）。
- 前端有项目列表/新建/删除入口（项目视图或 ChatSidebar 项目选择），能看到项目下模型。
- kind 流转有规则文档（可演进/不可演进 + 理由）。

## 测试要求

- store 层：RemoveModel / 删除联动测试。
- REST 层：新端点 envelope + 契约测试（对照 api_regulation.md）。
- 前端：项目视图组件测试（vitest）。
- 测试量 ≥ 实现量。
