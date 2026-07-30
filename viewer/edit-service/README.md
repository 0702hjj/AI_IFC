# ifc-edit-service

IFC 模型编辑服务（FastAPI + ifcopenshell）。迭代 N+2 起为 viewer 栈提供真实的 IFC 编辑能力；当前为骨架：`/health` + `ModelRegistry`（模型缓存 / 原子保存 / 每路径文件锁）。

## 运行

```bash
uv sync
uv run uvicorn app.main:app --port 8100
```

配置（环境变量）：`EDIT_SERVICE_PORT`（默认 8100）、`VIEWER_DATA_DIR`（默认 `../data`，与 viewer/server 数据目录语义一致）。

## 测试

```bash
uv run pytest
```
