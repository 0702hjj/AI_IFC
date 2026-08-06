# 上传第一个 IFC

仓库自带一个 buildingSMART 官方样例 IFC：

`viewer/converter/test/fixtures/wall-with-opening-and-window.ifc`

## 操作流程

1. **上传**：在模型库页拖入 `.ifc` 文件（≤200MB，非 .ifc 会被拒绝）。上传后状态进入 `converting`，页面以 2 秒间隔轮询，完成后变为 `ready`；失败会显示错误并可重试。
2. **进入模型**：点击模型进入三维查看器。左侧模型树默认展开一层，可搜索、按 IFC 类型过滤、逐节点显隐；点击构件会高亮并在右侧属性面板显示其属性集（pset）。
3. **审查**：使用可见性工具栏（隐藏/隔离/X-Ray/重置）、剖切滑杆与距离测量检查模型；选中构件可创建 Issue（自动携带相机视角与截图），3D 钉会出现在构件上。
4. **编辑**：在属性面板中，白名单字段（Name/Description/Classification/FireRating/Comments）可直接行内编辑保存为 override；详细编辑流程见 [IFC 属性编辑](/viewer/editing)。
5. **对比版本**：工具栏「Diff」选择 base 与 target（版本或 current）进行语义对比，见 [版本与 Diff Viewer](/viewer/versions-diff)。

## 排查

| 现象 | 处理 |
| --- | --- |
| 上传后一直 converting | 查看 server 日志中的 converter stderr；手动运行 `node viewer/converter/convert.js <ifc> <outDir>` 复现；确认 `nodeBin` / `converterScript` 配置 |
| 转换 failed | `POST /api/v1/models/{id}/retry` 重试 |
| 编辑报 404 model not found | edit-service 的 `VIEWER_DATA_DIR` 与 Go `dataDir` 不是同一目录 |
| 编辑报 422 | 属性名不存在或值类型不符——请求零副作用，修正后重发 |
| commit 报 409 | 没有 pending（pending 已落盘，edit-service 重启不丢） |
| 改了属性前端没刷新 | 经 Go 代理 commit 才触发重转；直连 edit-service 后需手动刷新或经代理重放 |

完整排查表见 [测试与调试](/development/testing)。
