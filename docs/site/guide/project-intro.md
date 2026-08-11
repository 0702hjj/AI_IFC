# 项目介绍

AI_IFC 是一个**自托管、开源**的 AI 生成平台，提供两个对等的逻辑外加一个推荐项（框架 spec：`docs/superpowers/specs/2026-08-11-platform-framework-design.md`）：

- **逻辑一：AI 生成 IFC**（已交付）——`skills/aiifc/` skill 封装 + `services/ifc`（`viewer/edit-service/`）的 diff 与面向前端修改的接口协议（script-as-source 编辑 API）。
- **逻辑二：AI 生成 CAD**（skill 域已交付，diff/编辑 API 待建）——`skills/aidxfv/`（由 `AI_CAD/skills/aidxfv*` 收敛）+ `services/cad`（与 ifc 同构）。
- **推荐项：Agent 工作流控制**（可选，做不好可删）——orchestrator + 事件总线。

可复用性原则：skill 封装两个、业务逻辑两个、前端可选实现、PostgreSQL 可选实现，接口写好可直接调用或移植。它从 SimpleCADAPI fork 而来；SimpleCADAPI 相关代码已于 2026-08-06 移至私有归档仓 [0702hjj/SimpleCADAPI-archive](https://github.com/0702hjj/SimpleCADAPI-archive)。

## 定位

- **是什么**：IFC 模型的自托管审查 + 编辑平台——script-as-source 编辑（一切修改落在 Python 构建脚本上）、语义化版本对比，以及设计师/AI 双角色共用的编辑 API；同一套「skill + diff + 接口协议」模式将复制到 CAD 段。
- **面向谁**：内网/个人自托管的 BIM 团队；做 IFC / CAD 工具链的开发者；需要「AI 可接入的编辑底座」的研究者。
- **当前能力**：IFC 段端到端可用——上传 → 转换 → 三维审查 → Issue → 脚本编辑（定位/改写/沙箱/暂存）→ 大版本 → 版本 diff。

## 能力边界

**已交付：**

- IFC 上传与队列化转换（XKT 几何 + 语义元数据）。
- 三维审查：模型树、属性检查、可见性工具、剖切、测量、NavCube。
- Issue 与 3D Pin：带相机视角与截图创建、状态流转、点击定位。
- 脚本编辑（script-as-source）：Python 构建脚本是 IFC 唯一事实源——选中构件定位脚本调用点（ScriptMap）、PARAMS 表单 / libcst 标量改写（edit-call）、沙箱验证、10 步暂存环、大版本成对快照（脚本 + map；IFC 只物化最新、历史按需重建）。
- 版本快照与属性级语义 diff（Diff Viewer）。
- 人与 AI 共用同一套编辑 API，provenance 区分 `UI` / `AI` / `USER`；MCP server 薄封装编辑 API（stdio）。
- PostgreSQL 可选存储（issues / overrides / change log）；不配置时文件存储零依赖可跑。

**未交付（见 [已知限制](/project/known-limits) 与 [Roadmap](/project/roadmap)）：**

- 多用户/鉴权；Docker Compose 一键部署；Viewer 使用与开发指南细节页的英文版本。（几何 diff 不做——IFC 是脚本产物，改几何 = 改脚本，diff 为脚本 diff + 属性级语义 diff。）

## 四组件架构

| 组件 | 技术 | 职责 |
| --- | --- | --- |
| `web` | React 19 + xeokit | 模型库、三维查看、脚本编辑（PARAMS 表单 + 脚本编辑器 + 定位）、Issue、Diff Viewer |
| `server` | Go 1.26（stdlib + pgx/v5） | 上传/转换队列、REST API、编辑编排、存储抽象 |
| `converter` | Node CLI（web-ifc + xeokit-convert） | IFC → XKT + metadata.json |
| `edit-service` | Python FastAPI + IfcOpenShell + ifcdiff | 脚本沙箱执行、版本快照、ScriptMap 定位、语义 diff |

三语言并存是生态现实而非设计偏好：每个语言绑定的是该生态里唯一或最优的 IFC 库。服务之间通过 REST 与子进程解耦，任一组件可独立替换。

详细架构见 [总体架构](/development/architecture)。
