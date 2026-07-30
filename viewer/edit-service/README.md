# ifc-edit-service

IFC 模型编辑服务（FastAPI + ifcopenshell）。迭代 N+2 起为 viewer 栈提供真实的 IFC 编辑能力：`/health` + `ModelRegistry`（模型缓存 / 原子保存 / 每路径文件锁）+ 实体编辑 API（pending/commit 两阶段 + history）。

## 运行

```bash
uv sync
uv run uvicorn app.main:app --port 8100
```

配置（环境变量）：`EDIT_SERVICE_PORT`（默认 8100）、`VIEWER_DATA_DIR`（默认 `../data`，与 viewer/server 数据目录语义一致）。

## 编辑 API

模型 id 必须匹配 `^m_[0-9a-f]{16}$`，对应 IFC 路径 `{VIEWER_DATA_DIR}/uploads/{id}.ifc`。

| 端点 | 语义 |
| --- | --- |
| `PUT /models/{id}/entities/{guid}` | 把 `fields`（实体直接属性）/`psets`（pset 单值属性，不存在则创建）应用到内存模型并记为一条 pending change（不落盘）。body：`{"fields": {...}, "psets": {...}, "author": "local-user", "provenance": {"source": "UI"\|"AI"}}`。先全量校验再应用（原子）；属性不存在 / 类型不符 / 坏 provenance → 422；guid 或模型不存在 → 404 |
| `GET /models/{id}/pending` | 列出当前 pending changes |
| `POST /models/{id}/commit` | 全部 pending 原子落盘（持锁）→ 追加 history（entries 补 `"operation": "update"`）→ 清空 pending；返回 `{committed, entries}`；无 pending → 409 |
| `DELETE /models/{id}/pending` | 丢弃 pending：卸载并重新从磁盘加载模型 |
| `GET /models/{id}/history` | 列出 history |

history 持久化在 `{VIEWER_DATA_DIR}/models/{id}/edit-history.json`（原子写），每条 entry 记录从 IFC 读到的真实 `oldValue`（pset 属性原本不存在时为 `null`）。

**注意**：pending changes 只存在于内存（按模型 id）；服务重启会丢失未 commit 的 pending（v1 可接受行为），history 不受影响。

## 测试

```bash
uv run pytest
```
