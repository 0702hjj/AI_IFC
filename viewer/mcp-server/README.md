# aiifc-mcp-server

平台 MCP server（stdio）：解析用户在外部修改后的 IFC / DXF 文件，输出结构化「用户修改事件」并标注 `provenance=USER`，写入该模型的 change log（edit-history），供整体 Agent 与 diff 引擎消费。

薄包 edit-service REST（平台独有能力：版本 / staging / diff / provenance 都在 edit-service），本组件只做：DXF 图层/实体级对比（ezdxf，**不做 layout 反解**）、diff → 用户修改事件的映射、MCP 协议面。

## 工具

| 工具 | 作用 |
| --- | --- |
| `ifc_upload_modified(model_id, ifc_path, author?)` | 上传改后 IFC：与现态跑语义 diff（edit-service `POST /models/{id}/diff/upload`）→ 事件标 USER（origin=ifc-upload）追加 change log → 返回事件（GlobalId + name/type 可读标注）+ summary |
| `dxf_upload_modified(model_id, dxf_path, base_dxf_path?, author?)` | DXF 图层/实体级对比（按图层统计增删改 + 文本标注变化），基线为 `base_dxf_path` 或 `{VIEWER_DATA_DIR}/models/{id}/source.dxf`；事件标 USER（origin=dxf-upload） |
| `model_versions(model_id)` | 大版本列表（IFC 快照 + 构建脚本）+ current |
| `model_diff(model_id, base, target)` | 大版本 diff：IFC 语义 diff + 脚本 diff 透传（无脚本模型 script=null） |
| `model_current_context(model_id)` | Agent 快速上下文：当前版本、staging 状态、最近 20 条修改事件 |

## 运行

```bash
uv sync --group dev
uv run python -m app.server            # stdio
uv run --group dev pytest              # 测试
```

配置（环境变量）：

- `EDIT_SERVICE_URL`：默认 `http://127.0.0.1:8100`
- `VIEWER_DATA_DIR`：DXF 基线查找（与 Go server / edit-service 指向同一数据目录）

MCP 客户端注册示例（`.mcp.json`）：

```json
{
  "mcpServers": {
    "aiifc": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "python", "-m", "app.server"],
      "cwd": "viewer/mcp-server",
      "env": {"VIEWER_DATA_DIR": "/abs/path/to/viewer/data"}
    }
  }
}
```
