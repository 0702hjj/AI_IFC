# 测试与调试

## 各模块测试

| 模块 | 框架 | 覆盖范围 | 运行命令 |
| --- | --- | --- | --- |
| converter | node:test | 真实 IFC 转换集成（快照、引用完整性、id 一致性） | `cd viewer/converter && npm test` |
| server | go test | 单元 + httptest API + 并发（`-race`） | `cd viewer/server && go test ./... && go vet ./...` |
| edit-service | pytest | 编辑 / 版本 / diff 路由 | `cd viewer/edit-service && uv run pytest` |
| web | vitest + jsdom | api client / 组件 / store / hook / 纯函数 | `cd viewer/web && npm test` |
| 端到端 | bash smoke | 上传→转换→下载→Issue→override/changes 全链路 | `cd viewer && ./scripts/smoke.sh`（需 server 运行） |

开发过程采用 TDD：每个模块先写失败测试再实现，测试文件与源码同目录。

## 端到端冒烟

前提：server 已在 `:8090` 运行；edit-service 可达时追加编辑链路（不可达自动跳过）。

```bash
cd server && go run ./cmd/server &
cd viewer && ./scripts/smoke.sh    # 成功以 smoke OK 结尾
```

覆盖：上传 fixture IFC → 轮询至 ready → XKT/metadata/download 200 → Issue 创建/列表/截图/状态流转/删除 → override 写入与生效值断言 → change log old→new 断言 → 清理。

## 手工验证清单（浏览器）

1. 打开 `http://localhost:5173` ，上传 `.ifc`（≤200MB）。
2. 列表状态 `converting → ready`（2s 轮询）；failed 显示错误并可重试。
3. 进入查看器：模型渲染、轨道旋转/缩放、NavCube 可用。
4. 模型树：默认展开 1 层；搜索/类型过滤；节点显隐；点击节点相机飞行 + 高亮。
5. 属性面板：pset 折叠/搜索/复制；白名单字段行内编辑，override 生效并带标记。
6. 可见性工具栏：隐藏选中、隔离、X-Ray、重置。
7. 剖切（X/Y/Z 滑杆）与距离测量。
8. Issue：选中构件新建（自动截图与相机）→ 3D 钉显示并可点击定位 → 状态流转 → 删除。
9. Diff：选择 base/target → 绿/红/黄着色 + old→new 列表 → 清除复位。

## 故障排查

| 现象 | 排查 |
| --- | --- |
| 上传后一直 converting | 看 server 日志 converter stderr；手动跑 convert.js 复现；确认 nodeBin/converterScript |
| 转换 failed | `POST /api/v1/models/{id}/retry` 重试 |
| 编辑 404 model not found | VIEWER_DATA_DIR 与 dataDir 不同目录 |
| 编辑 422 | 属性名/类型不符，请求零副作用，修正重发 |
| commit 409 | 无 pending（内存态，服务重启会丢） |
| 改了属性前端没刷新 | 直连 edit-service 的 commit 不触发重转；走 Go 代理 |
| PG 连不上 | 清空 pgDSN 回退文件存储 |
