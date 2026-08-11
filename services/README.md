# services/ — 业务逻辑核心（可复用，接口可直接调用或移植）

平台框架（`docs/superpowers/specs/2026-08-11-platform-framework-design.md`）定义两个对等的业务逻辑核心：每个核心提供 **diff + 面向前端修改的接口协议**，与对应 skill 配对，可脱离前端/网关独立部署。

| 目录 | 业务逻辑 | 当前物理实现（渐进收敛，不搬家） |
|---|---|---|
| `services/ifc` | IFC 段：diff 引擎 + script-as-source 编辑 API | `viewer/edit-service/`（FastAPI + IfcOpenShell，:8100） |
| `services/cad` | CAD 段：diff 引擎 + 编辑 API（待建，与 ifc 同构） | — |

- **services/ifc 独立调用指南**：见文档站 [services/ifc 独立部署与调用](/guide/services-ifc)。
- **共享可选运行时**：`viewer/web`（前端，可选）、`viewer/server`（Go 网关 :8090）、`viewer/converter`（转换）、PostgreSQL（可选）。
- **skill 封装**：`skills/aiifc/`（IFC）、`skills/aidxfv/`（CAD，由 `AI_CAD/skills/aidxfv*` 收敛）。

渐进规则：存量物理路径不动（`viewer/edit-service` 是 `services/ifc` 的历史别名），新逻辑按目标结构落位。
