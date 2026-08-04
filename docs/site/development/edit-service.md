# Edit Service

`viewer/edit-service/`：Python FastAPI + ifcopenshell + ifcdiff，默认 `:8100`，提供真改 IFC、pending/commit、版本快照与语义 diff。

## 运行与配置

```bash
cd viewer/edit-service
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
| `PUT /models/{id}/entities/{guid}` | 应用 `fields`/`psets` 到内存模型并记为 pending（不落盘）；先全量校验再应用（原子） |
| `GET /models/{id}/pending` | 列出当前 pending |
| `DELETE /models/{id}/pending` | 丢弃 pending：卸载并重载内存模型 |
| `POST /models/{id}/commit` | 全部 pending 原子落盘 → 版本快照 → 追加 history → 清空 pending；无 pending → 409 |
| `GET /models/{id}/history` | 列出持久化编辑历史（含真实 oldValue） |
| `GET /models/{id}/versions` | 版本快照列表与 current |
| `POST /models/{id}/diff` | 版本间语义 diff（base/target，target 可为 `current`） |

完整契约（body、错误码、Go 代理映射）见 [IFC 编辑 API](/reference/edit-api)。

## 实现要点

- `app/registry.py`：模型缓存（同路径同对象）/ 原子保存（tmp + os.replace）/ 每路径文件锁。
- `app/versions.py`：版本只增不改；首次 commit 先存 v1（原上传）再存 v2。
- `app/diffing.py`：IfcDiff 适配——仅 `attributes`/`property` 两种 relationship；changed 用 `get_info()`+`get_psets()` 自算字段级 old/new；快照间结果缓存。
- history 持久化在 `{VIEWER_DATA_DIR}/models/{id}/edit-history.json`（原子写）。

## 测试

```bash
cd viewer/edit-service
uv run pytest
```
