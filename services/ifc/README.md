# ifc-edit-service

IFC 业务逻辑核心（FastAPI + ifcopenshell）：**script-as-source 编辑 API**（`PUT /script` 暂存 → `script/run` 沙箱试运行 → `script/save` 大版本）+ 版本快照与语义 diff。可脱离 Go server / web / converter / PostgreSQL 独立部署与调用，详见文档站 [services/ifc 独立部署与调用](https://0702hjj.github.io/AI_IFC/guide/services-ifc.html)。

## 运行

```bash
uv sync
VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100
```

配置（环境变量）：`EDIT_SERVICE_PORT`（默认 8100）、`VIEWER_DATA_DIR`（默认 `../data`，建议绝对路径）、`AIIFC_FLOWS_DIR`（默认 `../../skills/aiifc/references/docs/flows`，沙箱脚本契约校验依赖 aiifc skill flows）、`EDIT_SERVICE_MAX_MODELS`（默认 8）。

沙箱（W-0047，环境变量）：`SCRIPT_MAX_FSIZE_BYTES`（RLIMIT_FSIZE 单文件写上限，默认 256 MiB）、`SCRIPT_MAX_OUTPUT_BYTES`（脚本 stdout+stderr 累计上限，超出杀进程组 422，默认 1 MiB）、`SCRIPT_MAX_PRODUCT_BYTES`（产物与 map sidecar 发布上限，超限 422 不落盘，默认 256 MiB）、`SCRIPT_RUN_CONCURRENCY`（进程级 run/save 并发闸，满即 429，默认 3）、`ALLOW_RLIMIT_FALLBACK`（bwrap 不可用时显式放行 rlimit 降级——rlimit 不隔离网络与沙箱外 FS，**生产不要设**；缺省不设则 run/save 拒绝执行 503）。

## 编辑 API

模型 id 必须匹配 `^m_[0-9a-f]{16}$`，对应 IFC 路径 `{VIEWER_DATA_DIR}/uploads/{id}.ifc`。

| 端点 | 语义 |
| --- | --- |
| `GET/PUT /models/{id}/script` | 读当前脚本 / 暂存一次编辑（整体替换或仅改 PARAMS） |
| `GET /models/{id}/script/params` · `POST .../undo|redo|discard` | PARAMS 提取 / 暂存导航与放弃 |
| `POST /models/{id}/script/run` | 沙箱试运行（预览，无版本） |
| `POST /models/{id}/script/save` | 晋升大版本（`scripts/v{n}.py` + `v{n}.map.json` 全留，`versions/v{n}.ifc` 只留最新） |
| `GET /models/{id}/scripts` · `POST .../script/rollback` · `.../diff` · `GET .../staging/diff` | 大版本列表 / 回退 / 脚本 diff / 暂存步 diff |
| `GET /models/{id}/script/locate?guid=` · `POST .../script/edit-call` | guid→调用点定位 / libcst 标量改写（edit-call 仅直连） |
| `GET /models/{id}/versions` · `POST /models/{id}/diff` · `POST .../diff/upload` | 版本列表 / 版本间语义 diff / 上传对比 |
| `GET/DELETE /models/{id}/pending` · `GET /models/{id}/history` | 只读保留（pending 为 script-run 回放簿记；history 只增） |
| `POST /models/{id}/user-edits` | 登记外部用户修改（`source="USER"`） |
| `PUT/DELETE /models/{id}/entities/{guid}` · `GET .../editable-schema` · `POST /models/{id}/commit` | **退役，410 Gone**（直改 IFC 已废弃，一切修改走构建脚本；回捞锚点 `fb55a8a`） |

完整契约（body、错误码、envelope 语义、Go 代理映射）见文档站 [IFC 编辑 API](https://0702hjj.github.io/AI_IFC/reference/edit-api.html)；独立部署、端点全清单与移植指南见 [services/ifc 独立部署与调用](https://0702hjj.github.io/AI_IFC/guide/services-ifc.html)；机器可消费 OpenAPI schema 见 `docs/site/public/ai-tools.openapi.json`（编辑 API 变更后重新导出：`uv run python scripts/export_openapi.py`）。

## 测试

```bash
uv run --group dev pytest
```
