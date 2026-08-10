# 更新日志

记录各版本的主要变更。完整历史见 [GitHub 提交记录](https://github.com/0702hjj/AI_IFC/commits/main)。

## 未发布（v0.2 进行中）

**Script-as-source 统一编辑（web 修改 = 改脚本）**

- 选中构件定位脚本调用点：`GET /script/locate?guid=`（guid→designKey→行/列/snippet/origin），PropertyPanel 只读化 + 「定位脚本」跳 Design 面板脚本编辑器。
- 新增 `POST /script/edit-call`（edit-service 直连）：libcst 标量参数无损重写 + 沙箱验证 + 暂存；契约新增 C-locate（#30，构件必经 `create_entity` 工厂）与 C-scalar（#31，web 可编辑参数为标量/PARAMS 引用）。
- 大版本三件成对：`scripts/v{n}.py` + `v{n}.map.json` 全量保留、lockstep 编号；`versions/v{n}.ifc` 只物化最新，历史版本按需从脚本重建（`ifc_cache/` LRU 4）。
- bootstrap：plain 模型首次暂存脚本自动保留上传原件为 `bootstrap.ifc`；首次 save 响应带 `alignment` 对齐计数。
- **create_skeleton 骨架确定性化**：Project/Site/Building/Storey 骨架实体改走 `create_entity` 确定性路径——GlobalId 由稳定 key（`skeleton:project` / `skeleton:site` / `skeleton:building` / `skeleton:storey:{名字}`）经 `deterministic_guid` 派生，自动写 `Pset_AIIFC.designKey` 且可 locate 定位。**兼容性**：生成期脚本契约变更，用旧版 script_lib 生成的模型骨架 GlobalId 与新版不同（首跑对齐报告/历史重建会带一次骨架 diff 噪声，可接受）。
- **L1 直改链路退役（410 Gone）**：`PUT/DELETE /entities/{guid}`、`editable-schema`、`POST /commit` 及 Go 侧直改代理路由下线（回捞锚点 `fb55a8a`）；`POST /diff`（IFC 语义 diff）与 `POST /diff/upload` 保留。

**Script-as-source（M5）**

- Python 构建脚本成为 IFC 唯一事实源：脚本契约（PARAMS + 确定性 GlobalId + build 入口）、脚本沙箱执行、WPS 式脚本暂存 + 大版本成对快照（`scripts/v{n}.py` + `versions/v{n}.ifc`）。
- 脚本 diff（text + PARAMS 键级，大/小版本两级）；Design 面板重构为 PARAMS 表单 + 脚本编辑器；design JSON 编辑管线下线。
- chat 编排注入脚本大版本 diff 上下文；script save/run/rollback 成功后自动触发 XKT 重转。

**MCP 与用户来源**

- 新增 `mcp-server`：编辑 API 的 MCP 薄封装（stdio），可解析用户在外部工具改后的 IFC/DXF 并标注 `USER` 来源（provenance 由 `UI`/`AI` 扩为三者）。

**属性真改直通**

- 属性编辑不再有 override 中间层，直接走 pending → commit 真改闭环；新增 editable-schema 与构件删除端点；PropertyPanel 改为类型化表单。

**修复与其他**

- ChatSidebar 历史/SSE 合并修复，EventSource 容错与重连。
- edit-service 镜像装 bwrap、端口绑 loopback；CI 新增 mcp-server job 与 compose 真冒烟。

## v0.1.0（2026-08，首个公开发布）

**审查平台**

- IFC 上传与队列化转换（XKT 几何 + 语义元数据）；模型树、属性检查、可见性工具、剖切、测量、NavCube。
- Issue 与 3D Pin：带相机视角与截图创建、状态流转、点击定位。
- issues / overrides / change log 的 File / PostgreSQL 双实现。

**真改 IFC 与版本**

- edit-service（FastAPI + IfcOpenShell）：属性 override 与 pending → commit 两阶段真改 IFC、不可变版本快照、按 GlobalId 的属性级语义 diff、Diff Viewer。

**AI 接入**

- 人/AI 双角色共用同一套 REST 编辑 API（provenance 区分），OpenAPI 工具目录与接入指南。
- aiifc 建模 skill：agent 无关，AI 直接写 `ifcopenshell.api` 代码生成或大改 IFC 模型；含 Plan → DXF → IFC 三阶段编排工作流与 DXF 生成器。
- 确定性构件身份：稳定 `key` → `uuid5` 确定性 GlobalId → `Pset_AIIFC.designKey` 双向映射。

**工程化**

- API 统一版本化 `/api/v1/{resource}/{id}`，Go server 为唯一对外入口，统一 envelope 契约。
- 依赖自包含（ifcopenshell / ifcdiff / ifcquery 全部 PyPI 官方发布）；文档站（VitePress）+ 英文 locale + API 文档机器生成与 CI 漂移检测。
- SCAD 遗产代码移至私有归档仓 [0702hjj/SimpleCADAPI-archive](https://github.com/0702hjj/SimpleCADAPI-archive)，本仓聚焦 `viewer/` 产品。
