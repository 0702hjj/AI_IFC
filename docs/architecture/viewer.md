# Viewer 迭代路线图（2026-07-29 更新）

> 本文原为 P0–P3 组件优先级路线图。P0 已全部落地，现更新为下一迭代计划。
> 对齐文档：`md/dxf_agent/deep-research-report.md`（变更追踪 / 编辑 API / 前端修改流）、`viewer/docs/design.md` §7 演进方向。

## 一、原路线图完成状态

| 优先级 | 组件 | 状态（2026-07-29） |
| --- | --- | --- |
| P0 | Property Inspector | ✅ 只读 + 属性搜索/pset 折叠/复制（修改功能见迭代 N+1） |
| P0 | Model Tree + 过滤 | ✅ 自建树：搜索 + 类型过滤 + 显隐（默认展开 1 层） |
| P0 | Issue/Markup | ✅ 创建（相机+截图）/列表/状态流转/删除/视角恢复（文件存储） |
| P1 | Measure | ✅ 距离测量 |
| P1 | Hide/Isolate/X-Ray 工具栏 | ✅ |
| P1 | Model Compare（Diff Viewer） | ❌ 迭代 N+2 |
| P2 | Property Editor | ❌ 迭代 N+1（override 阶段） |
| P2 | Rule Checker（批量审查） | ❌ 暂缓 |
| P3 | Parametric Modeling | ❌ 不做 |

平台已从「IFC Viewer」变为「BIM Review Platform」。下一阶段主线：**人的修改闭环**（看 → 发现问题 → 定位 → 修改 → 跟踪）。

## 二、与 deep-research-report 的对齐

我们负责报告中的「IFC 显示 + 人的修改」部分，对应关系：

| 报告章节 | 内容 | 落地方式 |
| --- | --- | --- |
| §2.4 前端修改流 | 选中构件 → 改参 → API → 保存/commit，viewer 实时刷新 | 迭代 N+1 属性修改器沿用此交互流（override 阶段不刷新几何，仅改属性显示） |
| §2.2 实体编辑 API | `PUT /models/{id}/entities/{guid}` | 迭代 N+2 引入 IfcOpenShell Python 编辑服务真改 IFC |
| §1.1 commit 模型 | author/timestamp/operation/diff/provenance | 迭代 N+1 修改记录对齐此 schema，provenance 区分 UI/AI |
| §1.3 IfcDiff | 按 GlobalId 语义 diff（added/removed/changed） | 迭代 N+2 Diff Viewer 的 diff 引擎 |
| §4 混合存储 | Git 存 IFC + DB 存元数据/commit log | DB 部分先落地（PG 存 Issue/override/历史）；IFC 版本化暂缓 |

不在我们范围：§2.3 AI 沙箱、§3 IFC→Python 工具（AI 线另行跟进，见 §五）。

## 三、迭代 N+1（下一迭代，viewer 线）

目标：纯现有技术栈（Go + React + PG）完成「人的修改」第一步与审查协同收尾。

1. **Issue 接 PG + 修改记录/历史**
   - 新增 `PgStore` 实现 `internal/issue.Store` 接口（pgx 驱动，server 首次引入第三方依赖，需更新 plan.md 约束说明）
   - Issue schema 扩展对齐报告 §1.1：`author`（先写死 local-user）、`provenance: {source: "UI"}`
   - 新增通用「修改记录」存储（change log）：实体 + 字段 + old/new + 时间 + author，供属性修改器写入、历史面板展示
2. **属性修改器（override 阶段）**
   - PropertyPanel 只读 → 可编辑：Name/Description/Classification/FireRating/Comments 等白名单字段
   - 保存为 metadata override（不改 IFC 本体），渲染时 override 覆盖原值显示；每次修改写一条 change log
   - 交互对齐报告 §2.4：选中 → 改值 → 保存 → 记录 → 可查看历史
3. **3D Issue Pin 收尾**
   - HTML overlay 钉（entity 中心投影，每帧同步），点击钉定位 Issue
   - 真机浏览器验证截图非空白（preserveDrawingBuffer 已固化，需人工确认）

## 四、迭代 N+2（引入 Python 服务）

4. **Diff Viewer**
   - 独立 IfcDiff Python 服务（IfcOpenShell，按 GlobalId 语义 diff）
   - UI：V1/V2 模型选择 → 绿（新增）/红（删除）/黄（修改）着色 + 属性 diff 列表（old→new）
5. **真改 IFC（override 之后）**
   - 同一 Python 服务实现报告 §2.2 `PUT /models/{id}/entities/{guid}` + pending/commit 流程（报告 §2.4 Figure 2）
   - override 数据迁移为真实 IFC 修改；修改后重新转换 XKT 刷新 viewer
   - change log 增加 diff 字段（报告 §1.1 `diff: {added, removed, changed}`）

## 五、AI 线（并行候选，非 viewer 主线）

按 viewerstatus.md 评估，「AI 用 IfcOpenShell 生成 IFC」主线目前为空，候选（优先级低于 viewer 线）：

6. **启用 ifcmcp + 写最小 ai_ifc skill**：ifcmcp（31 个工具）接进 `.mcp.json`，按 `research/ifc/simplecadapi_skill_anatomy.md` 复刻清单写 `skills/ai_ifc/` 骨架——最快验证 AI 操作 IFC 的路径
7. **IFC 生成 examples**：用 ifcopenshell.api 跑通「骨架优先」最小样例（Project→Site→Building→Storey→Wall，过 ifcopenshell.validate）

长期：AI 与人走同一套编辑 API（报告 §2.1 双角色），Python 服务的 MCP 化在迭代 N+2 之后考虑。

## 六、前端布局（维持）

```
------------------------------------------------
| Toolbar (+ 可见性工具栏)                      |
------------------------------------------------
| Model Tree  |                    | Properties |
| (搜索/过滤)  |     xeokit        | (可编辑→)  |
|             |      View          |            |
------------------------------------------------
| Issue Panel（+ 修改历史 →）                   |
------------------------------------------------
```
