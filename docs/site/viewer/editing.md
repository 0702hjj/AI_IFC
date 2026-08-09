# IFC 脚本编辑

web 端的「修改」统一为「修改构建脚本」（script-as-source）：IFC 永远是脚本的派生产物，任何持久化的修改必然伴随一次脚本变更。原 L1 直改链路（pending → commit 真改 IFC）已整体退役（端点返回 410 Gone，可从 git 历史回捞，锚点 `fb55a8a`）。

## 模型两种形态

- **script-backed**（有构建脚本）：完整编辑能力——选中定位、PARAMS 表单、脚本编辑器、暂存与大版本。
- **plain**（外部上传、无脚本）：仅查看与审查（Issue/Diff）。前端不提供编辑入口；无 AI 时的小改发生在自己的 BIM/CAD 软件里，重新上传即新的参考输入。经 AI 复现为脚本后转为 script-backed（见下文 bootstrap）。

## 选中构件 → 定位脚本

属性面板已只读化，不再直接改值。选中构件后点**「定位脚本」**：

1. 前端调 `GET /api/v1/models/{id}/script/locate?guid=`：guid → 读 IFC 的 `Pset_AIIFC.designKey` → 查当前（暂存优先，否则最新大版本）ScriptMap（`v{n}.map.json`）。
2. 命中：自动切到 Design 面板脚本编辑器，光标落到调用行并高亮该行。
3. 未命中：locate 返回 200 `{"found": false}`，面板提示只读（构件无 designKey 属契约违规，请上报 bug）。

## 改写（两条子路径）

定位结果带 `origin` 标签，决定改写策略：

- **`origin=params`**：构件参数来自脚本头部 `PARAMS`——在 Design 面板 PARAMS 表单中改对应键的值，提交即暂存一步（`PUT /script`）。
- **`origin=literal`**：参数是内联标量字面量——在脚本编辑器中直接改该行的参数值。API 侧另有 `POST /models/{id}/script/edit-call`（edit-service 直连）：libcst 无损重写单个标量参数（str/int/float/bool，保留格式与注释）→ 沙箱重跑验证 → 成功等同一次 `PUT /script` 暂存；`origin=traced`、非标量、非法参数名或非有限浮点一律 422 零副作用。
- **`origin=traced`**（designKey 运行期算出）：可定位到工厂调用行，但不可自动改写——请在脚本编辑器中手改。

## 沙箱验证与暂存

表单提交 / 编辑器保存先过脚本契约静态校验（失败 422 零副作用）后进入暂存区；edit-call 则在暂存前先沙箱重跑验证（**build 失败 = 422 零副作用**）。暂存区最多 10 步环窗，原子落盘、重启恢复，可 undo/redo：

- **放弃** → 丢弃暂存链，零 diff、零版本。
- **试运行** → 沙箱执行暂存脚本预览产物，不产生版本。
- **保存版本** → 跑脚本生成 IFC，晋升为大版本 v{n+1}（脚本 + map 成对快照，IFC 只物化最新，见 [版本与 Diff Viewer](/viewer/versions-diff)）。

## bootstrap：上传 IFC → 脚本（AI 路线）

有 AI 参与时，上传 IFC 的意图是**参考生成**：

1. 用户上传 IFC（plain 态，仅可查看）。
2. AI 经 MCP server 读取模型，用 aiifc skill 编写复现脚本。
3. 首次 `PUT /script` 时平台自动把上传原件保留为 `bootstrap.ifc`；脚本经沙箱验证后 `script/save` 存大版本 v1，模型转为 script-backed。
4. 首次 save 的响应带 `alignment` 计数（`added/removed/changed`，bootstrap.ifc vs 生成 IFC 的语义 diff 摘要）——作为「复现走样」的验收信号。

接口契约见 [Script 编辑与版本对比](/reference/design-edit) 与 [IFC 编辑 API](/reference/edit-api)。
