# IFC Viewer 测试与验证指南

> 本文说明 viewer 三个模块的测试覆盖程度、运行方式与手工验证清单。
> 架构与接口见 [design.md](./design.md) 与 [api.md](./api.md)。

## 1. 测试总览

| 模块 | 框架 | 测试数 | 层次 | 运行命令 |
|---|---|---|---|---|
| `converter/` | node:test | 1（集成） | 真实 IFC 转换快照 | `cd converter && npm test` |
| `server/` | go test | 24 | 单元 + httptest API + 并发 | `cd server && go test ./... && go vet ./...` |
| `web/` | vitest + jsdom | 47（9 个文件） | api client / 组件 / store / hook / 纯函数 | `cd web && npm test`（构建：`npm run build`） |
| 端到端 | bash smoke | 1 流程 | 上传→转换→下载→Issue CRUD 全链路 | `scripts/smoke.sh`（需 server 运行） |

开发过程采用 TDD：每个模块先写失败测试再实现，测试文件与源码同目录（每个子文件夹内均有对应 `*_test.go` / `*.test.ts(x)` / `*.test.js`）。

## 2. converter/（Node 转换器）

`converter/test/convert.test.js` —— 对真实 IFC 样例（`test/fixtures/wall-with-opening-and-window.ifc`，buildingSMART 官方样例）执行完整转换并断言：

- `model.xkt` 产出且大小 >4KB（几何非空）
- `metadata.json` 含 `Ifc*` 类型、≥1 个携带属性集的构件
- 引用完整性：所有 `propertySetIds`、`parent` 引用均可解析（无悬空）
- 隐含保证：XKT entity id 与元模型 GlobalId 一致性（`convert.js` 内置校验，不一致直接报错退出）

CLI 行为另行手工验证过：参数缺失 exit 2、转换失败 exit 1 + stderr、成功时 stdout 末行 `{"ok":true,...}`。

## 3. server/（Go 后端，stdlib only）

| 包 | 测试 | 覆盖点 |
|---|---|---|
| `internal/store` | `TestCreateGetListDelete` | 创建/读取/列表（时间倒序）/删除全生命周期、id 格式 |
| | `TestRecoverMarksConvertingFailed` | 重启恢复：converting→failed |
| | `TestInvalidIDRejected` | 路径穿越防护（`../../etc`、畸形 id 对 Get/SetStatus/Delete 均被拒） |
| `internal/convert` | `TestQueueSuccessAndFailure` | 转换成功→ready、失败→failed+错误信息（fake runner） |
| | `TestDuplicateEnqueueWhileRunning` | 运行中重复入队返回 false（阻塞 runner，确定性） |
| | `TestEnqueueAfterClose` | 队列关闭后 Enqueue 返回 false 而非 panic |
| | `TestShutdownCancelsInflightJob` | 关停 ctx 取消在途转换子进程 |
| `internal/api` | `TestUploadListDownloadDelete` | httptest 全流程：非法扩展名 400、超限 400、正常上传、列表、下载（Content-Disposition + 内容一致）、静态 404、删除、未知 id 404 |
| | `TestIssueCRUD/Errors/Screenshot` | issues 路由：创建（multipart + PNG 截图校验）→ 列表 → PATCH 状态 → 删除；空 title/非法 status 400、模型或 issue 不存在 404、截图静态路由回取 |
| `internal/issue` | 11 个用例 | FileStore CRUD、原子写、id/状态/title 校验、CreatedAt 降序、截图落盘与连带删除 |
| `cmd/server` | `TestLoadConfig*` | 配置缺省 host→127.0.0.1、显式 host 保留 |

并发相关测试均可在 `-race` 下通过（`go test ./... -race`）。

## 4. web/（React 前端）

| 文件 | 覆盖点 |
|---|---|
| `api/client.test.ts` | 信封解包、非零 code 抛错、multipart POST、下载 URL、DELETE；issues client（list/create/patch/delete） |
| `viewer/store.test.ts` | zustand 选择状态 / 工具模式切换 / 可见性状态（hide/isolate/xray/reset） |
| `viewer/tree-utils.test.ts` | buildTree 层级组装、typeCounts 降序、filterTree（名称/类型/祖先保留/空集语义） |
| `viewer/ModelTreePanel.test.tsx` | 树渲染、默认 1 层展开、搜索过滤、类型过滤、hide 写 store、点击选中+飞行 |
| `viewer/useVisibility.test.ts` | hidden/isolate/xray/reset 对 scene.objects 的 visible/xrayed 应用 |
| `viewer/VisibilityToolbar.test.tsx` | 按钮 disabled 态、隔离/X-Ray/重置状态流转 |
| `viewer/PropertyPanel.test.tsx` | 属性搜索、pset 折叠（默认第一个展开）、复制按钮写 clipboard、空态 |
| `viewer/IssuePanel.test.tsx` | Issue 列表、无选中禁创建、创建携带相机、状态 PATCH、点击飞行+选中、确认删除 |
| `viewer/Toolbar.test.tsx` | 无 viewer 上下文时的降级渲染 |

**覆盖边界（明确未覆盖）**：xeokit 画布内的真实 WebGL 交互（模型渲染、拾取高亮、剖切拖拽、测量打点、Issue 截图像素内容）无法用 jsdom 测试。开发期通过**无头 Chromium + SwiftShader** 验证过：模型渲染出非零像素、树节点点击飞行+属性面板联动、剖切滑杆、测量创建/清除、选择模式恢复、零控制台报错。该验证目前为手工方式，未纳入 CI（见 §6 后续方向）。

## 5. 端到端冒烟（scripts/smoke.sh）

前提：server 已在 `:8090` 运行。流程：

1. 上传 fixture IFC → 轮询状态（30×2s 超时，failed 立即退出）
2. 断言 `model.xkt`、`metadata.json`、`/download` 均 200
3. Issue 链路：创建（multipart + PNG 截图）→ 列表断言（status=open、截图路径）→ 截图静态 200 → PATCH resolved → 删除 → 列表为空
4. 删除模型清理，输出 `smoke OK`

```bash
cd server && go run ./cmd/server &   # 终端 1
scripts/smoke.sh                      # 终端 2
```

## 6. 手工验证清单（浏览器）

```bash
cd server && go run ./cmd/server      # :8090
cd web && npm install && npm run dev  # :5173
```

1. 打开 `http://localhost:5173` ，上传一个 `.ifc`（≤200MB；非 .ifc / 超限应被前端拦截）
2. 列表中状态 `converting → ready`（2s 轮询自动刷新）；failed 应显示错误并可重试
3. 进入查看器：模型渲染、轨道旋转/缩放、NavCube 可用
4. 左侧树：默认展开 1 层；搜索「wall」过滤命中；类型过滤勾选 IfcWall；节点 👁 显隐；点节点相机飞行+高亮
5. 点击构件：右侧属性面板显示 pset（第一个展开、其余可点开）；属性搜索过滤；复制按钮写入剪贴板；点空白取消选择
6. 可见性工具栏：隐藏选中、隔离、X-Ray、重置可见性
7. 工具栏：复位视角；剖切（X/Y/Z 滑杆）；测量（两点距离、双击结束、清除）；下载 IFC 得到原文件
8. 底部 Issue 面板：选中构件 → 新建 Issue（标题必填，自动带截图与相机）→ 列表出现红点条目；点击条目相机恢复视角并选中构件；状态下拉切换 Open/Checking/Resolved；删除需二次确认；刷新页面 Issue 仍在（文件持久化）

## 7. 后续测试方向（未纳入本期）

- 将无头浏览器验证固化为 Playwright e2e（CI 中跑 SwiftShader）
- converter 增加多 IFC 版本样例（IFC2X3 / IFC4X3）与损坏文件用例
- server 增加 retry 路由、并发上传的 httptest 覆盖
- npm audit 传递依赖 2 个 high（dev 工具链，暂未处理）
