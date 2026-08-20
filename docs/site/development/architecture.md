# 总体架构

```mermaid
graph LR
  subgraph 客户端层
    UI[浏览器<br/>React 19 + xeokit / web-ifc<br/>web]
    AI[AI Agent]
  end

  subgraph 服务层
    GO[Go server :8090<br/>server<br/>编排 / REST / 存储抽象<br/>Eino chat agent]
    PY[Python edit-service :8100<br/>services/ifc<br/>FastAPI + IfcOpenShell]
    CAD[Python cad-edit-service :8200<br/>services/cad<br/>FastAPI + ezdxf]
    CV[Node converter<br/>converter<br/>IFC → XKT + metadata.json]
  end

  subgraph 存储层
    PG[(PostgreSQL<br/>issues / changes / overrides)]
    FS[(文件系统<br/>uploads/*.ifc, models/{id}/)]
  end

  UI -->|REST envelope + chat SSE| GO
  AI -->|同一套编辑 API| PY
  AI -->|或经 Go 代理| GO
  GO -->|/api/v1/models/{id}/script/* 代理 + 编排| PY
  GO -->|dxf kind 分流| CAD
  GO -->|子进程 node convert.js| CV
  GO -->|pgx/v5，可选| PG
  GO --> FS
  PY -->|脚本沙箱执行 / 版本快照 / history| FS
  CAD -->|DXF 脚本沙箱 / 版本 / render.json| FS
  CV -->|model.xkt + metadata.json| FS
```

## chat agent（Eino ADK，进程内）

chat 侧 AI 对话由 `server/internal/agent/` 的 **Eino ADK** 驱动（`adk.ChatModelAgent` + `Runner` + OpenAI 兼容组件），完全在 Go 进程内运行：

- **事件流**：ADK AgentEvent 经翻译层映射为平台事件，再产出与前端 ChatSidebar 契约一致的 SSE 帧（message/part 事件族）；会话持久化为 append-only JSONL 事件日志（投影派生消息历史 + 跨 turn 历史回填）。原 opencode serve 外部进程已退役（W-0043），SSE/REST 契约不变。
- **领域工具集**：LLM 不给 bash/任意文件工具，只给平台领域工具（`list_models` / `get_model_info` / `get_script` / `stage_script` / `run_script` / `save_script` / `get_versions` / `get_diff` / `create_project`），按模型 kind 路由到 edit-service 或 cad-edit-service；工具错误以文本返回供模型自愈，结果 64KB 截断。
- **三角色编排（AgentAsTool）**：orchestrator（对话入口 + 意图路由）经官方 `AgentAsTool` 派 `ifc-agent`（aiifc skill）/ `cad-agent`（aidxf skill）子 agent——独立 ChatModelAgent + 独立模型实例，深度预算 1（子 agent 无派发工具）；子 agent 事件带 `subagentId` 标签经同一 SSE 下发，前端右侧边栏分组展示。
- **skill 能力**：`skills/dist` 正式集合（aiplan/aiifc/aidxf）经官方 skill middleware 加载；filesystem 收敛适配（读 references + execute 白名单 CLI，禁任意文件写）；独立 skill venv 提供 CLI 执行环境。
- **会话连续性 + HITL**：跨 turn 历史回填（检查阀门 ≤60% context 全量喂 / 超预算语义压缩）；`ask_user` 工具（官方 interrupt/resume）→ `question.ask` SSE 帧，用户回答经 `/answer` 续跑。
- **离线模式（scriptedModel）**：`llmAPIKey` 为空时回退确定性脚本模型——测试与离线 demo 不依赖真实 LLM。

## 组件职责

| 组件 | 技术 | 职责 | 选型原因 |
| --- | --- | --- | --- |
| web | React 19 + TS + Vite + zustand + xeokit-sdk + web-ifc/three（IFC 双引擎并存） | 审查/编辑/Diff 的全部交互 | xeokit 的 XKT 二进制加载与 BIM 工具链；web-ifc 直读 IFC（不经转换，并存渐进） |
| server | Go 1.26（stdlib net/http + pgx/v5 + cloudwego/eino） | 上传/转换队列、REST、编辑编排、存储抽象、进程内 chat agent | 静态编译、并发模型 |
| converter | Node CLI（web-ifc + xeokit-convert） | IFC → XKT 几何 + 语义提取 | xeokit-convert 只有 npm 形态 |
| edit-service | Python 3.10 + FastAPI + ifcopenshell + ifcdiff | 脚本沙箱执行、版本快照（script-as-source）、ScriptMap 定位、语义 diff | IfcOpenShell 是 IFC 编辑的事实标准 |
| cad-edit-service | Python 3.10 + FastAPI + ezdxf | DXF 脚本沙箱、版本、diff、render.json 直挂 | ezdxf 是 DXF 编辑的事实标准 |
| PostgreSQL | 可选 | issues / changes / overrides 三表 | 不配置 `pgDSN` 时全部落文件，零依赖可跑 |

## 核心数据流

### 上传转换流

```
浏览器上传 .ifc → Go 校验/存 uploads/{id}.ifc（status=converting）
  → 转换队列（2 worker，dedup + dirty 重跑）→ node convert.js
  → models/{id}/model.xkt（几何）+ metadata.json（空间树/pset）
  → status=ready → 前端 XKTLoaderPlugin 同时加载几何与语义
```

关键不变量：**XKT 构件 id = metadata metaObject id = IFC GlobalId**——选中、着色、diff 结果全靠这条链对齐。

### IFC 查看双引擎（并存渐进）

IFC 模型渲染有两条独立链路，用户级开关切换（localStorage `viewerEngine`，默认 xeokit）：

- **xeokit（默认）**：上传/编辑后经 converter 预转 XKT，加载 `model.xkt + metadata.json`；选中/diff/issue 定位等全套 BIM 工具链在此链路。
- **web-ifc（W-0044）**：浏览器内 wasm 直读上传原件 IFC（`GET /v1/models/{id}/download` → web-ifc IfcAPI → three 场景），不经 converter、不依赖转换完成；提供几何渲染/轨道控制/空间树/属性面板/选中高亮的基本集。web-ifc + three 经动态 import 独立分包，默认 xeokit 路径不加载该 chunk。

两链路选中语义对齐（构件 id 均为 IFC expressID/GlobalId 级），为后续 web-ifc 链路补齐编辑/Diff 交互预留同一套 store 联动。

### 编辑流（script-as-source）

web/AI 的修改统一为「改构建脚本」；IFC 是脚本沙箱执行的派生产物。原 L1 直改链路（`PUT /entities/{guid}` → pending → `POST /commit` 真改 IFC）已退役（410，回捞锚点 `fb55a8a`）。

```
PUT /models/{id}/script  {script | params}
  → 契约静态校验（失败 422 零副作用）→ 暂存一步（10 步环窗，落盘恢复，可 undo/redo）
  （plain 模型首次暂存时上传原件保留为 bootstrap.ifc）
POST /models/{id}/script/run      沙箱试运行预览（无版本）
POST /models/{id}/script/save
  → 沙箱跑脚本生成 IFC（失败 422，暂存保留）
  → 大版本 v{n}：scripts/v{n}.py + v{n}.map.json 成对快照（lockstep）
  → versions/v{n}.ifc 只物化最新，历史版本 IFC 快照删除（可按需重建）
  → 有 bootstrap.ifc 时响应带 alignment 对齐计数
（经 Go 代理时，run/save/rollback 成功后：）
  → 转换队列重转 XKT → 前端轮询到 ready 自动重载
```

定位与定向改写：

```
GET /models/{id}/script/locate?guid=
  → 读 IFC Pset_AIIFC.designKey → 查当前 ScriptMap（暂存优先）
  → hit：{line, col, snippet, origin}；miss：200 {"found": false}
POST /models/{id}/script/edit-call  {designKey, argument, value}（仅 edit-service 直连）
  → libcst 标量重写 → 契约校验 + 沙箱重跑 → 成功等同一次暂存；任何失败 422 零副作用
```

### 版本与 diff 流

- 大版本三件成对：`scripts/v{n}.py`（事实源）+ `v{n}.map.json`（定位）全量保留；`versions/v{n}.ifc` 只物化最新，历史版本 diff/下载时从脚本沙箱重建（`ifc_cache/` LRU 4）——确定性 GlobalId 保证语义可对齐，字节不做断言。
- `POST /models/{id}/diff {base, target}`：IfcDiff（`relationships=["attributes","property"]`，从构造上排除几何）给出 added/removed 集合；适配层对 changed 实体自算字段级 old/new；归约为 `{added, removed, changed:[{guid, changes:[{field,old,new}]}]}`。
- 快照间 diff 结果缓存（版本不可变，缓存天然有效）；`POST /diff/upload` 对比外部改后 IFC（不落盘不缓存）。

## 版本模型

change log 条目含：`author`（默认 `local-user`，v1 无认证）、`createdAt`（UTC）、`operation`、`provenance`（`{source: UI|AI|USER}`，API 层枚举校验）。版本为线性快照序列（分支/合并未做，属多用户范围）；回滚 = 恢复历史脚本重跑（append-only，不改写历史）。

已知技术债（详见 [已知限制](/project/known-limits)）：历史记录并存（Go change log / edit-service edit-history）粒度与用途不同；Python 侧存储仅文件模式。
