# Viewer 迭代路线图（2026-07-30 更新）

> 本文原为 P0–P3 组件优先级路线图，现为 **viewer 线**迭代计划。跨工作线的开源 v1 总计划见 [roadmap.md](./roadmap.md)。
> 对齐文档：`md/dxf_agent/deep-research-report.md`（目标映射见 `research/overview.md`）、`viewer/docs/design.md` §7 演进方向。

## 一、原路线图完成状态

| 优先级 | 组件 | 状态（2026-07-29） |
| --- | --- | --- |
| P0 | Property Inspector | ✅ 只读 + 属性搜索/pset 折叠/复制（编辑能力见 Property Editor 行） |
| P0 | Model Tree + 过滤 | ✅ 自建树：搜索 + 类型过滤 + 显隐（默认展开 1 层） |
| P0 | Issue/Markup | ✅ 创建（相机+截图）/列表/状态流转/删除/视角恢复（文件/PG 双存储） |
| P1 | Measure | ✅ 距离测量 |
| P1 | Hide/Isolate/X-Ray 工具栏 | ✅ |
| P1 | Model Compare（Diff Viewer） | ✅ 迭代 N+2 已落地（版本选择 + 绿/红/黄着色 + old→new 列表） |
| P2 | Property Editor | ✅ 真改已落地（迭代 N+2：edit-service pending/commit 真改 IFC；override 编辑保留，可一键迁移真改） |
| P2 | Rule Checker（批量审查） | ❌ 暂缓 |
| P3 | Parametric Modeling | ❌ 不做 |

平台已从「IFC Viewer」变为「BIM Review Platform」。下一阶段主线：**人的修改闭环**（看 → 发现问题 → 定位 → 修改 → 跟踪）。

## 二、与 deep-research-report 的对齐

我们负责报告中的「IFC 显示 + 人的修改」部分，对应关系：

| 报告章节 | 内容 | 落地方式 |
| --- | --- | --- |
| §2.4 前端修改流 | 选中构件 → 改参 → API → 保存/commit，viewer 实时刷新 | 迭代 N+1 属性修改器沿用此交互流（override 阶段不刷新几何，仅改属性显示） |
| §2.2 实体编辑 API | `PUT /models/{id}/entities/{guid}` | ✅ 迭代 N+2：`viewer/edit-service/`（FastAPI + ifcopenshell）真改 IFC，Go 代理 `/api/models/{id}/edit/...` |
| §1.1 commit 模型 | author/timestamp/operation/diff/provenance | 迭代 N+1 修改记录对齐此 schema，provenance 区分 UI/AI |
| §1.3 IfcDiff | 按 GlobalId 语义 diff（added/removed/changed） | ✅ 迭代 N+2：版本快照 + `POST /models/{id}/diff`（属性级），Diff Viewer 消费 |
| §4 混合存储 | Git 存 IFC + DB 存元数据/commit log | DB 部分先落地（PG 存 Issue/override/历史）；IFC 版本化暂缓 |

不在我们范围：§2.3 AI 沙箱、§3 IFC→Python 工具（AI 生成由另一同学负责，我们交付接入架构，见 §五与 roadmap.md §四）。

## 三、迭代 N+1（已完成 ✅，2026-07-29 落地，commits 8f41770 起）

目标：纯现有技术栈（Go + React + PG）完成「人的修改」第一步与审查协同收尾。

1. **Issue 接 PG + 修改记录/历史** ✅
   - `internal/issue` 新增 `PgStore`（pgx/v5，server 首个第三方依赖，plan.md 约束已更新）；`pgDSN`/`VIEWER_PG_DSN` 配置启用，未配置保持文件存储
   - Issue schema 已扩展对齐报告 §1.1：`author`（默认 `local-user`）、`provenance: {source: "UI"}`
   - 新增通用「修改记录」存储 `internal/change`（实体 + 字段 + old/new + 时间 + author，File/Pg 双实现），`GET /api/models/{id}/changes`
2. **属性修改器（override 阶段）** ✅
   - PropertyPanel 只读 → 可编辑：Name/Description/Classification/FireRating/Comments 白名单字段
   - 保存为 metadata override（`internal/override`，不改 IFC 本体），渲染时 override 覆盖原值显示并带修改标记；每次修改写一条 change log
   - 交互对齐报告 §2.4：选中 → 改值 → 保存 → 记录 → IssuePanel「修改历史」tab 查看
3. **3D Issue Pin 收尾** ✅
   - HTML overlay 钉（entity 中心投影，每帧同步）已落地，点击钉定位 Issue
   - 真机浏览器验证通过：截图非空白（preserveDrawingBuffer 固化）、钉落在构件上、点击钉定位、属性编辑入修改历史

## 四、迭代 N+2（已完成 ✅，2026-07-30 落地，分支 iteration-n+2 commits da57ab3..81ede3d；总计划见 roadmap.md §二）

4. **Diff Viewer**
   - 独立 IfcDiff Python 服务（IfcOpenShell，按 GlobalId 语义 diff）
   - UI：V1/V2 模型选择 → 绿（新增）/红（删除）/黄（修改）着色 + 属性 diff 列表（old→new）
5. **真改 IFC（override 之后）**
   - 同一 Python 服务实现报告 §2.2 `PUT /models/{id}/entities/{guid}` + pending/commit 流程（报告 §2.4 Figure 2）
   - override 数据迁移为真实 IFC 修改；修改后重新转换 XKT 刷新 viewer
   - change log 增加 diff 字段（报告 §1.1 `diff: {added, removed, changed}`）

## 五、AI 线（接入架构，非本仓库开发 AI 生成本体）

「AI 生成 IFC」由另一同学负责（2026-07-30 决策）。我们交付**可接入的架构**（详见 roadmap.md §四）：

6. **双角色编辑 API**（N+2 ✅）：AI 与人走同一套 REST 编辑 API（报告 §2.1），provenance.source 区分 UI/AI；AI REST 直连已真机验证
7. **工具 schema 文档**（N+2 ✅）：`docs/ai-integration.md` + `docs/ai-tools.openapi.json`（FastAPI 导出，可直接喂给 LLM）
8. **MCP 化预留**：报告 §4.1 建议 REST+MCP 双暴露；v1 先 REST，MCP 薄包装（参考 ifcmcp 31 工具模式）列 v1.1 候选

原候选「启用 ifcmcp + ai_ifc skill + IFC 生成 examples」移交 AI 生成线（调研材料已备：`research/ifc/simplecadapi_skill_anatomy.md`、`ifc_structrue_breakdown.md` 骨架优先策略、`MCP_API.md` ifcmcp 31 工具清单）。

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
