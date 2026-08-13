# cad-edit-service

CAD 业务逻辑核心（FastAPI + ezdxf）：与 `services/ifc` 完全同构的 **script-as-source 编辑 API**（`PUT /script` 暂存 → `script/run` 沙箱试运行 → `script/save` 大版本）+ DXF 版本快照。可脱离 Go server / web / converter / PostgreSQL 独立部署与调用。

与 services/ifc 的关系：逻辑二「AI 生成 CAD」的业务逻辑核心，路由/暂存/沙箱/版本语义与 ifc 一一镜像（模型对象由 IFC 换成 DXF，构建脚本走 `skills/aidxfv` 的 `cad_script_lib` 契约，实体身份靠 XDATA）；但无 ModelRegistry/PendingStore（无内存实体缓存、无 L1 直改遗产）。

**无鉴权，务必只绑 127.0.0.1**（与 edit-service 同一约束；对外经 Go server 代理——chunk C 已交付：Go 按 model kind 分流代理 cad 全端点（edit-call 除外），`GET /v1/models/{id}/render.json` 直挂只读）。

## 运行

```bash
uv sync
VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8200
```

配置（环境变量）：`CAD_SERVICE_PORT`（默认 8200）、`VIEWER_DATA_DIR`（默认 `../data`，建议绝对路径，须与 Go server 指向同一 `data`）、`AIDXF_FLOWS_DIR`（默认 `../../skills/aidxfv/v1/scripts/flows`，沙箱脚本契约校验依赖 aidxfv skill flows）、`CAD_SERVICE_MAX_MODELS`（默认 8）。

## 编辑 API（chunk A+B+C 已交付）

模型 id 必须匹配 `^m_[0-9a-f]{16}$`，对应 DXF 路径 `{VIEWER_DATA_DIR}/uploads/{id}.dxf`。

| 端点 | 语义 |
| --- | --- |
| `GET/PUT /models/{id}/script` | 读当前脚本 / 暂存一次编辑（整体替换或仅改 PARAMS） |
| `GET /models/{id}/script/params` · `POST .../undo\|redo\|discard` | PARAMS 提取 / 暂存导航与放弃 |
| `POST /models/{id}/script/run` | 沙箱试运行（预览，无版本；原子替换 `uploads/{id}.dxf` + ScriptMap sidecar） |
| `POST /models/{id}/script/save` | 晋升大版本（`scripts/v{n}.py` + `v{n}.map.json` 全留，`versions/v{n}.dxf` 只留最新） |
| `GET /models/{id}/scripts` · `POST .../script/rollback` · `.../script/diff` · `GET .../script/staging/diff` | 大版本列表 / 回退 / 脚本 diff / 暂存步 diff |
| `GET /models/{id}/versions` | DXF 版本快照列表 |
| `POST /models/{id}/diff` | 实体级语义 diff（XDATA key 对齐；body `{base, target}`，target 接受 `"current"`；不可变对缓存 `versions/diff-{base}-{target}.json`，504 超时） |
| `GET /models/{id}/script/locate?key=` | XDATA key → 脚本调用点定位（map scriptHash stale 时 200 降级 `{"found": false, "stale": true}`） |
| `POST /models/{id}/script/edit-call` | libcst 标量改写（locate 命中的调用点；stale 409 fail-closed） |
| `GET /models/{id}/render.json` | render payload v2（schemaVersion 2：实体带 XDATA key + unsupported 明面化；run/save 成功后原子更新，供前端 Canvas 2D 只读预览） |
| `GET /health` | 存活探针 |

Chunk 边界——**本服务尚未包含**（后续 chunk 按 spec 2026-08-12-services-cad-script-as-source-design.md 工作项 5-7）：web 前端 Canvas 查看器与编辑（Go 代理映射、render.json 已随 chunk C 交付）。

## 测试

```bash
uv run --group dev pytest   # 209 测试
```
