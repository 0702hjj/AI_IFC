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

## 版本快照与 diff

版本快照规则（`app/versions.py`，版本文件只增不改、原子写 tmp + os.replace）：

- 快照存放在 `{VIEWER_DATA_DIR}/models/{id}/versions/v{n}.ifc`（n 从 1 开始）。
- 首次 commit：先把 `uploads/{id}.ifc`（原始上传态）复制为 `v1.ifc`，落盘后把新文件复制为 `v2.ifc`。
- 之后每次 commit 成功：新落盘文件复制为 `v{n+1}.ifc`。

| 端点 | 语义 |
| --- | --- |
| `GET /models/{id}/versions` | `{"versions": [{"version": "v1", "createdAt": ...}, ...], "current": "v2"}`；未 commit 过时 versions 为空、current 为 null |
| `POST /models/{id}/diff` | body `{"base": "v1", "target": "v2"}`（target 也接受 `"current"` = uploads 现态）。返回 `{"base", "target", "added": [guid], "removed": [guid], "changed": [{"guid", "changes": [{"field", "old", "new"}]}]}`；版本不存在 → 404；缺参 → 422 |

diff 语义（`app/diffing.py`，基于 ifcdiff 的 `IfcDiff`，仅以 `attributes`/`property` 两种 relationship 运行）：以 GlobalId 为实体标识；changed 归约为实体直接属性与 pset 属性的字段级 old→new，entity 引用属性（ObjectPlacement/Representation 等几何表示层）不参与比较，天然过滤几何噪声。

**缓存策略**：base/target 都是不可变版本快照时，结果缓存在 `versions/diff-{base}-{target}.json`，二次调用直接命中；`target="current"` 时不缓存（uploads 文件可变，无稳定缓存 key）。

**ifcdiff 依赖**：pyproject 里以 editable 本地路径引用 `../../../IfcOpenShell/src/ifcdiff`（deepdiff/orderly-set 随它进来）；开源时需改为 vendor 或 PyPI 依赖。

## AI 接入

AI agent 以 REST 直连本服务（默认 `http://127.0.0.1:8100`，与浏览器经 Go 代理走的是同一套端点），调用时传 `provenance.source="AI"`。完整接入指南（双角色架构、curl 全流程、tool catalog、provenance/commit 模型、限制与 MCP 化路线）见 [`docs/ai-integration.md`](../../docs/ai-integration.md)；机器可消费的 OpenAPI schema 见 [`docs/ai-tools.openapi.json`](../../docs/ai-tools.openapi.json)，编辑 API 变更后重新导出：

```bash
uv run python scripts/export_openapi.py
```

## 测试

```bash
uv run pytest
```
