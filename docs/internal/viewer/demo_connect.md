# Demo 接入契约：聊天页 ↔ Go server（融入 chat 模块）↔ opencode / viewer

> 日期：2026-08-01（重写：聊天桥接**融入 Go server**，取消独立 demo-bridge）。本文档定义「用户聊天提需求 → opencode agent 改/生成 IFC → Go 内固定代码自动报备落盘 → 前端看到新模型」demo 的接入契约。
> 契约来源：opencode serve OpenAPI（`http://<host>:4096/doc`）与 `@opencode-ai/sdk` types.gen.ts、opencode 官网 Server/SDK/Web 文档（2026-08-01 调研）；viewer 侧以 `server/internal/`、`edit-service/app/` 实现逐一核对为准。

## 0. 远景边界（产品形态定位）

1. **对话式界面是唯一入口**：用户在聊天页「说 → 改 → 看」，查看器（xeokit）作为聊天页旁的展示面板。
2. **agent 职责最小化**：opencode agent（LLM）**只负责理解需求并产出正确的 IFC 文件**；落盘提交、版本快照、重转触发、模型注册等「项目任务侧」事务**全部由 Go server 内的固定代码自动完成**，LLM 对这些接口零感知。
3. **两条任务线**：改模型（会话已绑定 modelId）与从零构建（空白会话 → AI 生成 → 自动注册绑定）。

## 1. 总体架构（三服务 + opencode serve）

```
用户 ──► 聊天前端 ──► Go server :8090（唯一入口，含新增 chat 模块）
                          │  ├─ internal/opencode：opencode serve 客户端（仿 internal/editsvc）
                          │  ├─ internal/api/chat.go：chat 路由 + SSE 透传（仿 edit.go）
                          │  └─ 后台 goroutine：事件监听 → 固定代码三连/注册（仿 convert.Queue 模式）
                          ├──► opencode serve :4096 ── agent 本地改 {dataDir}/uploads/{id}.ifc
                          ├──► edit-service :8100（edit 代理，原样不动）
                          └──► convert.Queue ──exec──► converter（Node，IFC→XKT，原样不动）
浏览器查看器 ◄── 2s 轮询 /api/models/{id}（converting→ready）──┘
```

**AI 侧/前端只面对 :8090**：聊天、报备、模型状态、XKT 一个服务全包。

### 职责划分

| 层 | 职责 | 改动量 |
|---|---|---|
| opencode agent（LLM） | 理解需求 → ifcopenshell 改/生成 IFC → 自检 | 零（仅补 agent 规则） |
| **Go server chat 模块（新增）** | chat 路由、SSE 透传、事件监听、固定代码三连/注册 | **本 demo 唯一新增后端代码** |
| viewer 其余部分（edit 代理/edit-service/converter/web 现有组件） | 被调方：落盘/快照/重转/展示 | 零 |
| 聊天前端 | 对话 UI + 流式渲染 + 项目入口 | 新页面 |

### agent 负担最小化（固定代码包办清单）

| 事务 | 自动处理者 | 触发信号 |
|---|---|---|
| 落盘提交（三连） | Go 事件监听 goroutine | opencode SSE `session.idle` + `file.edited` 双条件 |
| 版本快照 / history / AI 审计指纹 | edit-service（commit） | 三连调用 |
| XKT 重转 | Go convert.Queue | commit 编排自动入队 |
| 从零构建模型初始化 | `POST /api/chat/projects`（骨架 IFC + store.Create） | 用户点「新建」即触发，与 agent 无关 |
| 回退执行 | Go 固定代码 | 聊天固定指令（如「回退到上一版」） |

## 1.1 对话界面实现途径（opencode 官网调研）

| 途径 | 结论 |
|---|---|
| `opencode web`（官方现成 UI） | ❌ 不进产品链路（不可定制）；demo 期可当调试观察窗 |
| JS SDK（`@opencode-ai/sdk`） | 备选；Go 技术栈不用 |
| **裸 REST + SSE（选定）** | Go 用 `net/http` 客户端调 opencode REST、订阅 `/event`；浏览器用原生 `EventSource` 连 Go 的透传端点。上行 POST、下行 SSE，无需 WebSocket |

## 2. 前端 ↔ Go：chat API 契约（新增，按 viewer 规范）

包络遵循 viewer 统一规范：成功 `{"code":0,"message":"ok","data":...}`；失败 `{"code":<业务码>,"message":...,"data":null}`。

### 2.1 会话管理

```
POST /api/chat/sessions
body: { "title": "项目A", "modelId": "m_xxx" }            // 幂等：同 modelId 复用既有会话（§5.3）
→ data: { "chatSessionId": "c_xxx", "opencodeSessionId": "ses_xxx", "modelId": null }

GET  /api/chat/sessions → data: [ { chatSessionId, title, modelId, createdAt } ... ]
```

会话映射（chatSessionId ↔ opencodeSessionId ↔ modelId）由 chat 模块维护，demo 期内存 map 即可（服务重启会话失效，可接受）。

### 2.2 发消息

```
POST /api/chat/sessions/{cid}/messages
body: { "text": "把外墙厚度改成300mm" }
→ data: { "accepted": true }        // 受理即返回；agent 响应走 SSE
```

chat 模块内部转发 opencode `POST /session/{oid}/prompt_async`（§3.2）。

### 2.3 事件流（SSE 透传）

```
GET /api/chat/sessions/{cid}/events        // text/event-stream
```

浏览器 `EventSource` 消费。Go 后台 goroutine 订阅 opencode `/event`（全局一条），按 sessionID 过滤后转发给对应会话的 SSE 客户端，事件类型原样透传（§3.3），另注入两类 chat 模块自有事件：

| 自定义 event | data | 含义 |
|---|---|---|
| `viewer.committed` | `{modelId, version, committed}` | 三连完成，已落盘快照，转换排队中 |
| `viewer.notify_failed` | `{reason}` | 报备失败（如坏文件），原文件状态说明 |

### 2.4 模型状态（复用现有）

`GET /api/models/{id}` → `data.status`（converting/ready/failed）——前端 2s 轮询，viewer 现成逻辑。

## 3. Go ↔ opencode serve：原生契约（调研结论）

### 3.1 会话

```
POST {OPENCODE}/session  body: {"title"?}  → Session {id: "ses_xxx", ...}
```

### 3.2 发消息（异步，配 SSE）

```
POST {OPENCODE}/session/{id}/prompt_async
body: { "parts": [{"type":"text","text":"..."}], "model"?: {"providerID","modelID"}, "agent"?: "ifc-research" }
→ 204 No Content
```

同步变体 `POST /session/{id}/message`（等 agent 跑完返回 `{info: AssistantMessage, parts: Part[]}`）demo 不用。响应结构：`TextPart{type:"text",text}`（正文）、`ToolPart{type:"tool",tool,state}`（过程）、`ReasoningPart`（推理）。

### 3.3 事件流

```
GET {OPENCODE}/event        // SSE；首事件 server.connected，之后总线广播
```

chat 模块消费的事件（types.gen.ts 已核实）：

| event.type | properties | 用途 |
|---|---|---|
| `message.part.updated` | `{part, delta?}` | 流式正文（delta 增量，透传给浏览器） |
| `message.updated` | `{info: Message}` | 元数据（tokens、error） |
| `session.status` | `{sessionID, status:{type:"idle"\|"busy"\|"retry"}}` | 状态条 |
| **`session.idle`** | `{sessionID}` | **turn 结束——三连/注册触发钩子** |
| **`file.edited`** | `{file}` | **命中 uploads/{id}.ifc → 置 dirty** |
| `permission.updated` | `{...}` | agent 请求权限时提示（如启用权限规则） |

### 3.4 配置

`server_config.json` 新增 `openCodeURL`（环境变量 `VIEWER_OPENCODE_URL` 覆盖，缺省 `http://127.0.0.1:4096`）——仿 `EditServiceURL` 模式。opencode 启动：`opencode serve --port 4096 --cors http://localhost:5173`（**工作目录 = `IFC_front/AI_IFC`**——demo 适配环境，`skills/aiifc` 已从开发版复制至此；需补 `opencode.json`（从 `CADapi/AI_IFC` 适配复制 provider/skills.paths/mcp）与 `.opencode/agent/` demo 专用规则，与开发环境隔离不混淆）。

## 3.5 存储布局与工作区划分（符合 viewer 设计原则）

viewer 的设计原则是「**文件系统即真相、约定式目录布局、路径即键**」（模型无 SQL，元数据 `model.json`，版本快照即文件）——本接入严格沿用，不引入新的存储范式：

```
① viewer 数据区（viewer 拥有，真相所在）：{dataDir} = viewer/data/
   ├── uploads/{modelId}.ifc              ← 模型工作区（agent 大改的唯一目标）
   ├── models/{modelId}/                  ← viewer 产物：model.xkt/metadata.json/model.json/
   │                                        edit-history.json/versions/v{n}.ifc（agent 禁入）
   └── staging/{chatSessionId}.ifc        ← 【demo 新增约定】从零构建暂存 + agent 改副本临时区

② opencode 工作区（AI 侧拥有）：IFC_front/AI_IFC/（opencode serve 工作目录）
   ├── opencode.json（待补，从 CADapi/AI_IFC 适配复制）
   ├── skills/aiifc/（已从开发版复制，demo 改造版）
   └── .opencode/agent/（待补，demo 专用规则）

③ 归属关系（用户↔会话↔模型）：chat 模块内存 map（demo）→ 未来 DB
④ 实验产物：/tmp/opencode/ 或本文档附录，不进以上任何区
```

**三原则（贯穿全文，任何设计决策不得违反）**：

1. **数据不进项目目录**：IFC、快照、转换产物全在 `viewer/data/`；`IFC_front/AI_IFC/` 只有代码/skill/规则（可 git 管理）
2. **写权限收窄**：agent 对 `viewer/data/` 仅可写 `uploads/{id}.ifc`（改模型目标）与 `staging/`（草稿）；`models/` 是 viewer 自留地，碰即破坏快照体系
3. **归属不进文件系统**：多用户远景也**不**把目录改为 `users/{uid}/...`——`uploads/{id}.ifc` 路径约定是 Go store、edit-service、converter 三方共享协议；用户归属永远放映射层

**viewer 设计原则遵循清单**：原子写（staging/副本先写临时名再替换，同 `os.replace` 模式）· 包络统一 `{code,message,data}`（§2）· id 寻址不变（`^m_[0-9a-f]{16}$`，staging 不进入 id 命名空间）· 两阶段语义（三连走 pending/commit，不直写 versions/）· 版本只增不改（回退=revert 语义产生新版本）· 降级语义（commit warning 视为降级非失败）· 分层编排（Go 编排、Python 执行，新增 chat 模块同为编排层成员）。

## 4. 固定代码：三连报备（Go 内部执行）

触发：`session.idle` 且会话 bound 且检测到工作区变更（`file.edited` 命中 ∪ mtime 兜底，见 §6 表 #7）。已实现于 `server/internal/api/chat.go`（`onEvent`/`notify`）；commit 编排抽为包级函数 `commitOrchestrate`（edit.go），handler 与 chat 模块共用。

### 4.1 流程与要点

```
① 坏文件自检（借力）：editsvc.DELETE /models/{id}/pending
   —— 该调用强制 edit-service 从磁盘重载；文件损坏时 load 失败即报错 → 中止、
      推 viewer.notify_failed，绝不继续（否则 commit 会用旧内存模型覆盖 agent 的修改）
② guid 自取（正则）：逐行扫 uploads/{id}.ifc，命中即止
   regexp: #\d+\s*=\s*IFCPROJECT\('([^']+)'     // IfcProject 恒存在；STEP 文本格式，无需 ifcopenshell
③ 审计标记：editsvc.PUT /models/{id}/entities/{guid}
   body: {"psets":{"Pset_ViewerMeta":{"AISummary":"<一句话>"}}, "author":"opencode-cli",
          "provenance":{"source":"AI"}}           // pset 新增，不污染原数据
   // 实测边界：标记写在 IfcProject 上不会出现在 edit/diff 结果里（IfcProject 非产品实体，
   // diff 不比较它）；AI 审计的展示面是修改历史 tab（Go change log），agent 的真实属性修改
   // （如墙 Name）正常进入 diff.changed（已实测：Name old→new 精确捕获）
④ 落盘+编排：复用 edit.go commit 的编排逻辑（建议抽为共享函数，chat 模块调用，避免 HTTP 自调）：
   editsvc.POST /models/{id}/commit（body 带 author/provenance）
   → change log 追加 → SetStatus(converting) → convert.Queue.Enqueue
   → 推 viewer.committed；change log 失败按既有降级语义（warning，非失败）
```

### 4.2 语义备忘（与 HTTP 契约一致，供核对）

- 顺序不可换：①清缓存 → ③标 pending → ④落盘；空 pending commit 会 409（③就是入场券）
- 版本规则：首次 commit 自动存 v1（原始上传）+ v2；之后每次 v{n+1}，快照全量、只增不改
- Queue 的 dirty 机制：转换中再次 commit 入队，会按最新文件重跑，不会用旧内容白转

### 4.3 回退（复用同一管道）

```
rollback_to(modelId, version):
    预检 versions/v{n}.ifc 存在（os.Stat）
    复制 versions/v{n}.ifc → uploads/{id}.ifc
    走 §4.1 同一套三连（summary="Rollback to v{n}"）
```

语义为 git revert：回退也产生新版本、history 留痕、历史不抹除。

## 5. 从零构建链路（骨架初始化，2026-08-02 修订）

**设计原则：「新建」点击那一刻项目即完整就位（modelId + 初始文件 + 会话绑定），agent 只是后续的修改者。** 会话永远 bound，状态机单态，从零构建与改模型走**完全同一条主链路**——无注册分支、无特殊事件。

### 5.1 流程（已实现）

```
用户点「新建空白项目」
→ POST /api/chat/projects：Go 写入骨架 IFC（最小合法文件：IfcProject + 几何上下文 + 单位，
  GlobalId 由 Go 按 IFC base64 规则生成）→ store.Create 得 modelId → 入队转换（已实测 ready）
→ 前端跳 /view/{modelId}（正常项目页；进页自动建 bound 会话，幂等）
→ 用户说「建一个两层小楼」→ agent 改 uploads/{id}.ifc（初始为骨架，直接在其上建造）
→ 走 §4 主链路：mtime 检测 → 三连 → v1=骨架快照 → v2=首个 AI 模型 → 重转 → 自动刷新
   （diff v1→v2 全量 added，演示效果优于注册分支方案）
```

### 5.2 agent 侧约定（`IFC_front/AI_IFC/.opencode/agent/ifc-demo.md`，已同步）

- **改文件统一走主链路**：修改/从零构建目标都是 `uploads/{modelId}.ifc`（从零时初始为骨架）
- 流程一律：`staging/` 改副本 → 自检 → 原子替换（写 `.new` 再 `os.replace`）
- staging **仅作草稿区**（原 `staging/{chatSessionId}.ifc` 从零生成约定已废弃）
- **复杂建模 design 先行**：多房间/异形/多层等复杂几何，先读 `DESIGN_PATTERNS.md` + `docs/design/` + `DESIGN_JSON_SCHEMA.md` 选型，产出 design.json 落盘 `staging/{modelId}.design.json`，经 `design_builder.py` → 构建脚本。简单单墙/板可跳过。
- **制品随版本同步归档**（Go notify 在 commit 后自动）：`staging/{modelId}.py` → `models/{id}/scripts/v{n}.py`；`staging/{modelId}.design.json` → `models/{id}/designs/v{n}.json`。两制品同版归档、设计意图与构建脚本可追溯。无对应 staging 文件则跳过（手术式编辑无脚本、简单改动无 design.json）。
- 自检三件套（可打开 / 唯一 IfcProject / 骨架完整）；写权限仅 uploads 与 staging；禁调 HTTP

## 5.3 会话连续性（已实现）

- **幂等绑定**：`POST /api/chat/sessions` 对同一 modelId 只会有一个会话——退出再打开返回同一会话；幂等实现为 **per-modelId 创建锁 + double-checked locking**（`createSession` 网络调用在锁内但仅串行化同 modelId），**并发安全**——根治 React StrictMode dev 双发 / 用户连点导致的 TOCTOU 竞态（不会产生双会话、不会因 Go map 遍历随机而破坏连续性）
- **持久化**：会话映射原子写 `{dataDir}/chat-sessions.json`（tmp+rename，同 viewer 模式），server 重启自动恢复（opencode 侧会话本身即持久，可继续拉历史/续聊）
- **历史回填**：`GET /api/chat/sessions/{cid}/messages` 透传 opencode 历史，前端挂载时渲染

## 6. 数据对齐事项（接入前逐项核对）

| # | 事项 | 对齐要求 | 不对齐的后果 |
|---|---|---|---|
| 1 | `dataDir` 三方一致 | Go（`server_config.json` dataDir，实际 = `viewer/data/`）= edit-service（`VIEWER_DATA_DIR`）= opencode 进程可读写同一目录 | 改的不是同一份文件 / 404 |
| 2 | 会话绑定 | 永远 bound（骨架初始化后无 unbound 态）；同 modelId 幂等复用；映射持久化 chat-sessions.json | 重复会话 / 重启丢会话 |
| 3 | model id 格式 | `^m_[0-9a-f]{16}$`（store.Create 生成）；staging 文件不进 id 命名空间 | 404 / 命名冲突 |
| 4 | opencode 环境 | 工作目录 = `IFC_front/AI_IFC`；`opencode.json` 已适配复制（provider/skills.paths/mcp）；`model.providerID/modelID` 与其一致；`agent` 用 demo 规则 agent 名 | 加载到开发版环境 / 用错模型 / 无 IFC 技能 |
| 5 | 包络分界 | 浏览器只见 Go 包络 `{code,message,data}`；opencode 原生 JSON 只在 Go 内部，不透出 | 前端格式混乱 |
| 6 | provenance | 三连 PUT/commit 必带 `provenance.source="AI"`、`author="opencode-cli"`（Go 校验枚举 UI\|AI） | 40001 / history 无 AI 标记 |
| 7 | 触发双条件（**已实测修正**） | `session.idle` + 变更检测；变更检测 = `file.edited`（仅覆盖 write/edit 工具）∪ **工作区 mtime > lastCheck（兜底主路径——实测 agent 用 bash 跑 python 改文件时 opencode 不发 file.edited）**；仅 idle 会空报备 | 空版本快照污染历史 / 漏报备 |
| 8 | staging 定位 | 仅作 agent 改副本草稿区（原从零生成取件约定已废弃）；最终产物必须落 `uploads/{modelId}.ifc` | 产物不落主链路 → 不触发报备 |
| 9 | 上传约束 | 注册复用 store.Create：`.ifc`、≤200MB（MaxUploadMB） | 拒绝 |
| 10 | SSE 生命周期 | Go 对 opencode 全局一条订阅常驻（断线重连+退避）；浏览器每会话一条透传 | 事件丢失→漏触发 |
| 11 | 快照体积 | 版本全量复制，大模型每 commit 占一份磁盘 | 磁盘水位（设计如此） |
| 12 | 会话映射易失 | 内存 map：Go 重启会话失效，前端需重建会话（demo 接受） | 重启后旧会话 404 |

## 7. viewer 侧缺口清单（供实现方，demo 不阻塞）

| # | 缺口 | 建议 | 影响 |
|---|---|---|---|
| 1 | 无「外部改文件后触发重转」端点 | `POST /api/models/{id}/reconvert`（SetStatus+Enqueue 两步） | demo 靠三连蹭重转 |
| 2 | 无版本回退端点 | `POST /api/models/{id}/revert {version}`（可与 #1 合并为「以指定版本替换当前」） | demo 靠 §4.3 内部复制绕行 |
| 3 | 大改无逐处审计 | diff 属性级且过滤几何（设计如此） | 只有版本级粒度，demo 接受 |
| 4 | 前端无空白项目入口 | 聊天前端双入口（新建空白/打开已有），属本 demo 自建 | 第 5 章方案即对策 |

## 8. 风险与边界

- **并发**：单机单用户；agent 改文件与 edit-service 读写无跨进程锁，避免 agent 干活时人工编辑同模型
- **pending 易失**：edit-service 重启丢 pending（history/版本不受影响）；三连间隔极短，风险可忽略
- **坏文件两道闸**：agent 先改副本自检（§5.2）+ Go 三连首调即检（§4.1①）；仍出问题则从最近 `versions/v{n}.ifc` 复制恢复
- **opencode API 版本**：契约基于 2026-08-01 调研（anomalyco/opencode@dev）；升级后以 `http://127.0.0.1:4096/doc` 重新核对
- **chat 模块边界**：新增代码独立成 `internal/opencode/` + `api/chat.go`，不揉进 edit.go，保持可拆——若日后拆回独立服务，搬运成本低
