# Edit Service

`services/ifc/`：Python FastAPI + ifcopenshell + ifcdiff，默认 `:8100`，提供脚本沙箱执行、版本快照、ScriptMap 定位与语义 diff。原 L1 直改链路（pending → commit 真改 IFC）已退役（410，回捞锚点 `fb55a8a`）。

## 运行与配置

```bash
cd services/ifc
uv sync
uv run uvicorn app.main:app --port 8100
```

| 环境变量 | 默认 | 说明 |
| --- | --- | --- |
| `VIEWER_DATA_DIR` | `../data` | 与 Go `dataDir` 同目录（必须） |
| `EDIT_SERVICE_PORT` | `8100` | 监听端口 |

> 依赖 `ifcopenshell` / `ifcdiff` / `ifcquery` 均为 PyPI 官方发布（对齐 IfcOpenShell 0.8.5），`uv sync` 直接安装，无本地源码依赖。

## 编辑 API

模型 id 匹配 `^m_[0-9a-f]{16}$`，对应 IFC 路径 `{VIEWER_DATA_DIR}/uploads/{id}.ifc`。

| 端点 | 语义 |
| --- | --- |
| `GET/PUT /models/{id}/script` | 读当前脚本 / 暂存一次脚本编辑（整体替换或仅改 PARAMS）；plain 首次暂存保留 `bootstrap.ifc` |
| `GET /models/{id}/script/params` | PARAMS dict（ast 提取，不执行） |
| `POST /models/{id}/script/undo\|redo\|discard` | 暂存导航 / 放弃 |
| `POST /models/{id}/script/run` | 沙箱试运行暂存脚本（预览，无版本） |
| `POST /models/{id}/script/save` | 晋升大版本（跑脚本 + 脚本/map 成对快照）；有 bootstrap 时响应带 `alignment` |
| `GET /models/{id}/scripts` · `POST .../script/rollback` · `POST .../script/diff` · `GET .../script/staging/diff` | 大版本列表 / 回退 / 脚本 diff / 暂存步 diff |
| `GET /models/{id}/script/locate?guid=` | guid → designKey → 调用点（line/col/snippet/origin）；miss → 200 `{"found": false}` |
| `POST /models/{id}/script/edit-call` | libcst 标量改写 + 沙箱验证 + 暂存；非法输入 422 零副作用 |
| `GET /models/{id}/versions` · `POST /models/{id}/diff` · `POST /models/{id}/diff/upload` | 版本列表 / 版本间语义 diff / 上传对比 |
| `GET/DELETE /models/{id}/pending` · `GET /models/{id}/history` | 只读保留（pending 现为 script-run 回放簿记；history 只增，新增来自 `POST /user-edits`） |
| `PUT/DELETE /models/{id}/entities/{guid}` · `GET .../editable-schema` · `POST /models/{id}/commit` | **退役，410 Gone** |

完整契约（body、错误码、Go 代理映射）见 [IFC 编辑 API](/reference/edit-api)。

## 实现要点

- `app/script_runner.py`：沙箱执行（subprocess + killpg + rlimits + bwrap 网络隔离）；`app/script_staging.py`：10 步暂存环；`app/script_versions.py`：大版本三件成对（`v{n}.py` + `v{n}.map.json` 全留，`versions/v{n}.ifc` 只留最新）。
- `app/ifc_materialize.py`：历史版本 IFC 按需从脚本重建（`ifc_cache/` LRU 4）；重建仅语义相等，比较走 diff 而非字节。
- `app/script_edit.py`：libcst 标量参数无损重写（edit-call）；`app/script_params.py`：PARAMS ast 提取/替换。
- `app/route_common.py`：跨路由请求解析 helper 单点；业务规则校验住各 `verify*` 函数（见仓库 AGENTS.md「校验与业务隔离」硬规则）。
- `app/registry.py`：模型缓存（同路径同对象）/ 原子保存（tmp + os.replace）/ 每路径文件锁。
- `app/diffing.py`：IfcDiff 适配——仅 `attributes`/`property` 两种 relationship；changed 用 `get_info()`+`get_psets()` 自算字段级 old/new；快照间结果缓存。
- history 持久化在 `{VIEWER_DATA_DIR}/models/{id}/edit-history.json`（原子写）。

## 测试

```bash
cd services/ifc
uv run --group dev pytest
```
