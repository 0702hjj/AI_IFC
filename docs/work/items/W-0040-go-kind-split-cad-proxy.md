# W-0040: Go kind 分流 + services/cad 代理（Model.Kind + .dxf 上传分流 + 13 端点代理 + render.json 只读）

- **状态：** open
- **优先级：** P1
- **Milestone：** v0.6（services/cad script-as-source，chunk C）
- **来源：** spec 2026-08-12-services-cad-script-as-source-design.md §1.3「Go 网关」+ §二 3「模型类型」+「工作项建议」5/7
- **执行者/分支：** opencode / feat/v0.7-cad-render

## 背景

services/cad :8200 已具备与 services/ifc 同构的全套 REST 端点（chunk A+B），但 Go server :8090 是唯一对外入口，目前只代理 IFC 链路。本项让 CAD 链路对外可达：模型记录加 `kind` 区分 ifc/dxf，上传按扩展名分流（DXF 不进 converter 子进程），`/api/v1` 下代理 cad script 端点，并暴露 render.json 只读端点供前端 Canvas 预览。镜像 `server/internal/api/script.go` 现有 IFC 代理模式。

## 涉及位置

- `server/internal/api/`：cad 代理 handler（镜像 `script.go`）、model 记录 kind 字段、上传分流、render.json 只读端点、auth 豁免白名单
- `server/internal/store`（或 model 记录所在处）：`Model.Kind` 持久化 + 旧记录迁移
- 参照：`server/internal/api/script.go`（fast/slow 双 client 代理范式）、IFC 侧 `GET /v1/models/...` 只读文件 auth 豁免现状

## 方案

1. **Model.Kind**：模型记录加 `kind: "ifc"|"dxf"`；存量记录迁移默认 `ifc`（不破坏现有模型）。
2. **上传分流**：`.dxf` 上传走 services/cad 引导（bootstrap.dxf + 初始脚本），不进 converter 子进程（DXF 无需 XKT 转换，services/cad 直接产 render.json）。
3. **代理 13 端点**：`/api/v1` 下 cad script 全量端点代理（GET/PUT script、params、undo/redo/discard、run、save、scripts、rollback、script/diff、staging/diff、locate）；`edit-call` 按 spec 不经 Go 代理（仅服务直连暴露）。fast/slow 双 client——run/save/rollback 走 120s slow client；响应统一 envelope `{code,message,data}`。
4. **render.json 只读端点**：`GET /api/v1/models/{id}/render.json`（只读文件下发）；auth 豁免白名单同步更新（对齐 IFC 侧 `GET /v1/models/...` 只读豁免）。

**显式范围外：** render payload v2 生成本身（W-0039）、web Canvas 查看器与 ViewerPage 分流（后续工作项）、MCP diff 切换（spec「工作项建议」7 后半）。

## 验收标准

- `Model.Kind` 落库；旧记录迁移后默认 `ifc`，现有 IFC 模型行为不回归。
- `.dxf` 上传创建 kind=dxf 模型、走 services/cad，不触发 converter 子进程；`.ifc` 路径不回归。
- cad script 13 端点经 `/api/v1` 代理可达；run/save/rollback 走 slow client（120s）；edit-call 不出现在 Go 路由表。
- envelope 契约测试覆盖代理端点（`code=0` 成功形态 + 错误翻译）。
- render.json 只读端点可下文件；auth 开启时该 GET 在豁免白名单内，其余 cad 端点需 Bearer token（401 envelope 码 `40100`）。
- `cd server && go test ./... && go vet ./...` 全绿。

## 测试要求

- envelope 契约测试：13 代理端点 mock services/cad 断言 envelope 包装与状态码翻译（镜像 IFC 侧代理测试）。
- kind 分流测试：dxf 上传不进 converter（断言无子进程调用/无 XKT 入队）；旧记录迁移默认 ifc。
- 双 client 测试：run/save/rollback 路由到 slow client（超时配置断言）。
- auth 白名单测试：render.json GET 豁免、写端点 401。
- 异步写盘纪律：涉及重生成队列的测试用条件等待（轮询 + 超时），禁止固定 sleep。
- 新增测试量 ≥ 新增实现量（仓内 ≥1:1 硬规则）。
