# Viewer P0 缺口功能设计：Model Tree 增强 + 可见性工具栏 + Property Inspector 增强 + Issue/Markup

日期：2026-07-28
状态：已确认（方案 A）
依据文档：`AI_IFC/docs/architecture/viewer.md`（P0/P1 路线图）、`AI_IFC/docs/architecture/viewerstatus.md`（缺口评估第 3 项）

## 1. 目标与范围

把 viewer 从「IFC Viewer」补齐为「BIM Review Platform」的四个组件（viewer.md 结论），本期只做前端流程闭环，**不引入数据库**：

| 功能 | 优先级来源 |
|---|---|
| Issue/Markup 系统（创建/列表/状态流转/相机恢复/截图） | viewer.md P0 |
| Model Tree 搜索 + 分类过滤 + isolate/hide | viewer.md P0 |
| Property Inspector 属性搜索 / pset 折叠 / 复制（只读，不含修改） | viewer.md P0 |
| Hide / Isolate / X-Ray / Reset 浮动工具栏 | viewer.md P1 |

**非目标**（本期不做）：
- PostgreSQL 持久化（Issue 暂存文件系统，接口预留，后期平移）
- 属性修改、修改记录（viewer.md P2）
- 3D Issue Pin overlay（接口预留，后期再加）
- 多选、Diff Viewer、Rule Checker、几何编辑

**约束**：
- Go 端保持零第三方依赖（stdlib-only，`docs/plan.md` 约束不破坏）
- 沿用 `{code,message,data}` 错误信封、CORS 中间件、id 正则校验、tmp+rename 原子写等现有模式
- 前端：React 19 + TS + Vite + zustand + 纯 CSS（无 Tailwind），TS 文件 ≤500 行，`@` alias
- 不改动 converter、上传/转换队列、模型列表 API、xeokit 加载链路、`model.json` 结构

## 2. Server 设计

### 2.1 新包 `server/internal/issue/`

```go
type Issue struct {
    ID         string    `json:"id"`         // "i_" + 12 位小写 hex
    EntityID   string    `json:"entityId"`   // IFC GlobalId（与 metaObjects[].id 一致）
    EntityName string    `json:"entityName"`
    EntityType string    `json:"entityType"`
    Title      string    `json:"title"`      // 必填
    Comment    string    `json:"comment"`
    Status     string    `json:"status"`     // "open" | "checking" | "resolved"
    Camera     Camera    `json:"camera"`     // {eye, look, up} 各 [3]float64
    Screenshot string    `json:"screenshot"` // "issues/{id}.png"，无截图时 ""
    CreatedAt  time.Time `json:"createdAt"`
    UpdatedAt  time.Time `json:"updatedAt"`
}

type IssuePatch struct {
    Title   *string `json:"title"`
    Comment *string `json:"comment"`
    Status  *string `json:"status"`
}

type IssueStore interface {
    List(modelID string) ([]Issue, error)
    Create(modelID string, issue Issue) (Issue, error)
    Update(modelID, issueID string, patch IssuePatch) (Issue, error) // title/comment/status
    Delete(modelID, issueID string) error
    SaveScreenshot(modelID, issueID string, png []byte) (string, error)
}
```

- `FileStore` 实现：数据存 `data/models/{id}/issues.json`（数组，整体读改写，tmp+rename 原子写，复用 store.go 模式）；截图存 `data/models/{id}/issues/{issueId}.png`
- id 生成：`"i_" + 12 位小写 hex`（crypto/rand）；校验正则 `^i_[0-9a-f]{12}$`；model id 复用现有 `store` 包校验
- 后期平移 PostgreSQL：新增 `PgStore` 实现同一接口，API 层与前端零改动
- 删除模型时（现有 `DELETE /api/models/{id}`）连带删除 issues.json 与 issues/ 目录（models/{id} 目录本就整体删除，天然满足）

### 2.2 API 路由（`internal/api/api.go` 扩展）

| 路由 | Handler | 说明 |
|---|---|---|
| `GET /api/models/{id}/issues` | listIssues | 按 createdAt desc 返回数组 |
| `POST /api/models/{id}/issues` | createIssue | multipart：`issue` 字段（JSON，含 title/comment/entity*/camera）+ 可选 `screenshot` 文件（PNG，≤5MB） |
| `PATCH /api/models/{id}/issues/{issueId}` | updateIssue | JSON body：`{title?, comment?, status?}`，status 校验枚举 |
| `DELETE /api/models/{id}/issues/{issueId}` | deleteIssue | 连同截图文件删除 |
| `GET /models/{id}/issues/{file}` | serveModelFile 扩展 | 截图静态服务，路径校验防穿越（沿用现有 serveModelFile 思路） |

错误码沿用现有：`40001`（参数错误，含 id 非法/title 为空/status 非法/截图超限或类型错）、`40400`（模型或 issue 不存在）、`50000`（内部错误）。

### 2.3 main.go 装配

`NewStore` 之后 `issue.NewFileStore(dataDir)`，传入 `api.NewHandler`（Handler 增加 issueStore 参数）。无新配置项。

## 3. Web 设计

### 3.1 zustand store 扩展（`src/viewer/store.ts`）

```ts
{
  selectedId: string | null
  tool: "select" | "measure"
  hiddenIds: Set<string>
  isolateId: string | null
  xray: boolean
  setSelected / setTool / hideIds / isolate / setXray / resetVisibility
}
```

xeokit 对象可见性副作用由 hook（`useVisibility`）订阅 store 后应用到 `scene.objects[id]`：
`visible = !hiddenIds.has(id) && (!isolateId || id === isolateId)`，`xrayed = xray && id !== isolateId`；Reset 恢复全部。

### 3.2 ModelTreePanel 重写（弃用 TreeViewPlugin）

- 数据源：`metaModel.metaObjects`，由 `parent` 链在 `buildTree(metaObjects)` 纯函数中组装为树节点 `{ id, name, type, children[] }`
- 搜索框：大小写不敏感匹配 name/type；`filterTree(tree, query, allowedTypes)` 纯函数返回保留命中节点及其祖先的子树，命中节点自动展开并高亮
- 分类过滤：下拉列出模型中存在的 IFC 类型 + 数量（`typeCounts(metaObjects)` 纯函数），勾选集合传入 `filterTree`
- 节点行：名称 + 👁 hide/show 切换（写 `hiddenIds`）；点击 → `setSelected(id)` + `cameraFlight.flyTo`
- 默认展开 1 层；不做虚拟化
- 纯函数（`buildTree`/`filterTree`/`typeCounts`）独立成 `src/viewer/tree-utils.ts`，便于单测

### 3.3 VisibilityToolbar（并入现有 Toolbar 区）

按钮：`[ Hide Selected ]` `[ Isolate ]` `[ X-Ray ]` `[ Reset ]`

- Hide Selected：`selectedId` 非空时可用，`hiddenIds.add(selectedId)`
- Isolate：`selectedId` 非空时可用，`isolateId = selectedId`（只显示选中对象，单选语义）
- X-Ray：切换 `xray`，非 isolate 对象半透明
- Reset：清空 `hiddenIds`/`isolateId`/`xray`

### 3.4 PropertyPanel 增强（保持只读）

- 顶部搜索框：过滤当前构件所有 pset 的属性（匹配属性名与值，大小写不敏感）
- 每个 Pset 分组可折叠，默认展开第一个
- 每行属性末尾复制按钮：`navigator.clipboard.writeText(`${name}: ${value}`)`

### 3.5 IssuePanel（底部抽屉，可收起）

- 数据：进入 ViewerPage 后 `GET /api/models/{id}/issues` 拉取，本地 state 管理（本页内无跨组件共享需求，不放入 zustand）
- 列表项：状态色点（open=红 / checking=黄 / resolved=绿）+ title + entityName + createdAt；hover 显示截图缩略图；点击 → `cameraFlight.flyTo(issue.camera)` + `setSelected(entityId)`
- 创建：有 `selectedId` 时「+ 新建 Issue」可用 → 表单（title 必填、comment 可选）→ 提交时：
  1. 从 `viewer.scene.canvas` `toBlob('image/png')` 截图
  2. 从 `viewer.camera` 读取 `{eye, look, up}`
  3. multipart POST（`issue` JSON + `screenshot` 文件）
- 状态流转：条目内下拉三态 → PATCH
- 删除：点击后二次确认 → DELETE
- `client.ts` 新增 `listIssues / createIssue / updateIssue / deleteIssue`，沿用 `request<T>` 信封解包；`api/types.ts` 新增 `Issue`、`IssueStatus` 类型

### 3.6 布局

```
------------------------------------------------
| Toolbar (+ VisibilityToolbar 按钮组)          |
------------------------------------------------
| ModelTreePanel |   xeokit canvas  | Property  |
| (搜索+过滤)     |                  | Panel     |
------------------------------------------------
| IssuePanel（抽屉，可收起）                      |
------------------------------------------------
```

## 4. 错误处理

- Server：issue id 正则校验；title 必填；status 枚举校验；截图仅 PNG 且 ≤5MB（`http.DetectContentType` 校验）；model 不存在 → 40400
- 前端：沿用 `client.ts` 抛错模式；IssuePanel 内联错误提示；截图失败（WebGL canvas 被 taint 等）降级为无截图创建，不阻断流程
- 相机恢复时 entity 已不存在（模型更新后旧 issue）：flyTo 相机仍执行，高亮跳过

## 5. 测试策略（TDD）

| 层 | 测试 |
|---|---|
| server `internal/issue` | 单元：CRUD、原子写、id 校验、截图落盘/删除、枚举校验 |
| server `internal/api` | 路由：4 条新路由成功路径 + 40001/40400 错误路径 |
| web `tree-utils` | 纯函数：buildTree / filterTree（搜索、类型过滤、祖先保留）/ typeCounts |
| web `store` | 状态迁移：hide/isolate/xray/reset 组合 |
| web 组件 | ModelTreePanel（搜索交互）、PropertyPanel（搜索/复制 mock clipboard）、IssuePanel（列表/创建/状态流转，mock fetch） |
| e2e | `scripts/smoke.sh` 追加：创建 issue（带截图）→ 列表断言 → PATCH 状态 → 删除 |

运行方式不变：`go test ./...`、`npm test`（vitest）、`scripts/smoke.sh`。

## 6. 文档同步（实施收尾时覆写）

- `viewer/docs/design.md`：移除「标注持久化」非目标，补 Issue 文件存储说明与 IssueStore 接口预留 DB 的说明
- `viewer/docs/api.md`：新增 4 条路由契约 + Issue JSON schema + 错误码
- `AI_IFC/docs/architecture/viewerstatus.md`：P0/P1 缺口表更新为已完成

## 7. 后期扩展预留

- PostgreSQL：实现 `PgStore`（满足 `IssueStore` 接口），pgx 驱动，配置项 `postgres.dsn`
- 3D Issue Pin：Issue 已含 entityId + camera，overlay 投影所需数据齐备
- BCF 导出：Issue 字段与 BCF viewpoint（camera + selection + snapshot）天然对齐
