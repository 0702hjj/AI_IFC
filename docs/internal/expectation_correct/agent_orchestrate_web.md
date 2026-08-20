# Agent 编排：网页对齐层 + 数据流

> 从 agent_orchestrate.md 拆分（历史演进文档，2026-08-20 拆分为多文件满足 ≤500 行门控）。前端/SSE 契约 + 数据流场景走读。

## 四、网页对齐层：接口全景（双方都要懂的契约）

### 3.1 REST 路由（chat.go:79-87，全部走 `/api/v1` 前缀，envelope `{code,message,data}`）

| 方法 | 路径 | 功能 | 响应 |
|---|---|---|---|
| POST | `/api/v1/chat/sessions` | 创建会话（幂等：同 modelId 只一个） | `{chatSessionId, opencodeSessionId, modelId, title, createdAt}` |
| GET | `/api/v1/chat/sessions` | 列会话 | 数组 |
| POST | `/api/v1/chat/sessions/{cid}/messages` | 发消息启动一轮 agent | `{"accepted": true}` |
| GET | `/api/v1/chat/sessions/{cid}/messages` | 历史回填（投影） | `[{info, parts}]` |
| GET | `/api/v1/chat/sessions/{cid}/events` | **SSE 事件流**（EventSource 直连） | text/event-stream |
| POST | `/api/v1/chat/sessions/{cid}/abort` | 中止当前 turn | `{"aborted": true}` |
| POST | `/api/v1/chat/projects` | 创建骨架项目（AI 对话从零建模入口） | 模型对象（含 modelId） |

注意：`/events` 带 `Last-Event-ID` 重连时补发 missed 帧；不带则行为与旧版一致（不补发）。鉴权开启时 `GET /chat/sessions/...` 只读端点白名单（auth.go:55）。

### 3.2 SSE 帧契约（翻译层 chat_translate.go，浏览器消费的逐事件清单）

> 传输层：每帧 `id: {会话内递增seq}\ndata: {json}\n\n`；seq 复用了 pushLocked（chat_sse.go:95），重同步缓冲 64 条环形。事件名 = opencode 形状（W-0043 契约红线：**前端零改动**）。

**主会话帧**（不带 subagentId 字段，旧形状不变）：

| event 名 | data 形状 | 触发时机 | ChatSidebar 行为（ChatSidebar.tsx） |
|---|---|---|---|
| `session.status` | `{status:{type:"busy"\|"idle"}}` | turn/start、turn/end | busy 置位/清除，禁用发送 |
| `message.updated` | `{info:{id,role,sessionID}}` | turn/start（user 消息）、每步 model step/start（assistant 消息行） | 记 role 到 rolesRef（用户输入已本地乐观插入，跳过渲染） |
| `message.part.updated` | `{part:{id,type:text\|reasoning\|tool,messageID,sessionID,text?,state?}}` | 首分片建行（text 空文本）、tool/call（running）、tool/result（completed/error） | text/reasoning 建行（增量交给 delta）；tool 建工具卡片（title/input/output/error 状态渲染） |
| `message.part.delta` | `{sessionID,messageID,partID,field:"text",delta}` | assistant/chunk 每个分片 | 按 partID 追加到 m.text（流式渲染） |
| `message.part.removed` | `{part:{id}}` | 消息重写/abort 收尾 | 删行防残留 |
| `session.idle` | `{}` | turn/end | busy 清除 |
| `session.error` | `{error}` | EventError | 红色系统消息 |
| `viewer.committed` | `{modelId,version,committed:true}` | notify 落盘成功 | ✅ 系统消息 + `flagPendingModelReload()`（轮询到 ready 重载画布） |
| `viewer.notify_failed` | `{modelId,step,reason}` | notify 任一步失败 | ⚠️ 系统消息 |

**子 agent 帧**（附加 `subagentId` 字段，前端据此分流右侧边栏，不进主消息流）：

| event 名 | data | 前端行为 |
|---|---|---|
| `subagent.status` | `{subagentId,parentSessionId,persona,status:"started"\|"finished",task}` | started 建分组（persona 徽章+task），finished 置完成 |
| `message.part.updated`（带 subagentId） | 同上 + subagentId；part.id 前缀 `sp_`（防与主会话碰撞） | 并入对应分组 |
| `message.part.delta`（带 subagentId） | 同上 + subagentId | 追加到分组 part 文本 |

**确定性 id 约定**（chat_translate.go:24-38，实时帧与历史投影共用，前端按 id 去重）：
- 用户消息 `msg_{turn}_user`、用户 part `part_{turn}_user`
- 助手消息 `msg_{turn}_{step}`、文本 part `part_{turn}_{step}_text`、思考 part `part_{turn}_{step}_reasoning`
- 工具 part `part_{turn}_{step}_tool_{callID}`（callID 空退化 `..._tool`）
- 子消息 `sub_{subagentId}_msg_{turn}_{step}`、子 part `sp_{subagentId}_{turn}_{step}_{kind}`

### 3.3 翻译层映射（agent 内部事件 → SSE 帧，chat_translate.go:91-191）

| agent 事件 | 产出的 SSE 帧 |
|---|---|
| `turn/start` | `session.status busy` + `message.updated`（user 行） |
| `step/start`（kind=model） | `message.updated`（assistant 行）；tool step 不产帧 |
| `assistant/chunk` | `message.part.updated`（首分片建行）+ `message.part.delta`（逐片） |
| `assistant/message` | 正文非空且未建行 → `message.part.updated`（text） |
| `tool/call` | `message.part.updated`（tool part, status:running）——工具卡片建行 |
| `tool/result` | 成功 → `message.part.updated`（completed+output）；失败 → `error` 载荷（status:error，前端 ✗ 态） |
| `error` | `session.error` |
| `turn/end` | `session.status idle` + `session.idle` |
| `subagent/status` | `subagent.status`；其余子事件走 translateChild（带 subagentId 的 part 帧） |

### 3.4 notify 落盘闭环（AI 改完模型后平台自动收尾，ChatSidebar 侧只看到两个系统事件）

```
turn/end → consumeRun 流关闭 → notifyIfDirty(cs)（chat_orchestrator.go:100）
  变更检测：cs.dirty（工具面 markDirty 精确信号）∨ uploads/{id}.ifc mtime > lastCheck（兜底）
  → notify(cs)（:150）：
      读 staging/{modelId}.py（有则注入 NotifyState.Script；读不出宁可中止也不丢变更）
      组装第一轮事件 aiifc://chat/{cid}/idle + NotifyState{Dirty,Bound,HasStagingScript,Script}
      → runShell（chat_shell.go:29）：循环 planNotify(Event+State)→Action 列表→逐条 execAction
```

**Core（chat_core.go planNotify，纯函数零 IO）** 的分支 → Action：

| 分支 | Action 序列 |
|---|---|
| idle + dirty + bound + 有脚本 | discard_pending → stage_script → run_script → save_script（saved 事件驱动第二轮） |
| 第二轮（saved 事件，version 已知） | archive_artifact（staging → `models/{id}/scripts/v{n}.py` 删源）→ reconvert（EnqueueIfStale）→ notify（viewer.committed） |
| idle + dirty + 无脚本 | discard_pending → reconvert → notify（空版本 viewer.committed） |
| 任一步失败（script/failed） | notify_failed（viewer.notify_failed {step,reason}），fail-fast 不跨步重试 |

**Shell（chat_shell.go execAction，唯一 IO 层）** 的动作与失败语义：
- `discard_pending` → `DeletePending`（坏文件自检：强制 edit-service 磁盘重载）
- `stage/run/save` → 对应 REST；save 版本不可解析 → `save_version` 细分 fail（防空版本静默吞掉导致 staging 滞留、下次 idle 重复 save）
- `reconvert` → `EnqueueIfStale`（IFC 不新于 XKT 时跳过冗余重放）
- dxf kind 整条管线走 cad :8200；`ModelKind=DXF` 时 Core 短路 reconvert（XKT 是 IFC 专属产物）
- 180s 整体超时（notifyTimeout）

### 3.5 前端消费对照（ChatSidebar.tsx:175-331）

EventSource 挂 `chatEventsUrl(cid)`；断线由 EventSource 原生自动重连（带 Last-Event-ID，服务端补发 missed）；`error`/`open` 事件控制「连接断开」提示。子 agent 分组渲染（:436-514 可折叠边栏）：`subagent.status started` 建组 → 带 subagentId 的 part 帧并入组内 → `finished` 置完成态。前端右侧边栏展示、主消息流不受污染。

---

## 五、数据流场景走读（带 curl / 代码路径的探索路线）

### 场景 A：网页对话「帮我新建一个项目，然后建一堵墙」（完整闭环）

1. 前端 `POST /api/v1/chat/projects {title}` → 骨架 IFC 生成 + 注册 `m_...` + 入队转换（chat_orchestrator.go:58）。
2. 前端 `POST /api/v1/chat/sessions {modelId}` → 幂等返回会话。
3. 用户发消息 → `POST /messages {text}` → postMessage 拼系统上下文（`[系统上下文] 会话绑定模型...\n\n[用户需求] ...`，≥2 版本时追加脚本 diff 上下文 W-0016）→ `Ag.Run`。
4. agent 循环：`create_project`（或直接用绑定模型）→ `stage_script` → `run_script` → `save_script`；浏览器实时看到工具卡片从 running → completed。
5. turn/end → SSE `session.idle` → notifyIfDirty（dirty 已由 save_script markDirty）→ notify 闭环 → `viewer.committed {version:"v1"}` → 前端轮询到 ready 自动重载画布。

### 场景 B：主 Agent 派子 agent 画 CAD

1. 用户在绑定 DXF 模型的会话里说「画一个两室一厅平面」。
2. 主 agent 判断意图 → 调 `dispatch_cad_agent {task:"...（自包含需求 + 输入锚点）"}`。
3. runChild：发 `subagent.status started`（前端建分组）→ 子 run（cadAgentPersona）用**父会话绑定**的 DXF 模型走工具（stage/run/save 打到 :8200）→ 子事件全部打 `sa_{turn}_{seq}` 标签上浮（前端边栏分组）→ `finished`。
4. 子报告（turn/end 的 message）作为 dispatch 工具的**结果文本**回到主 agent 上下文 → 主 agent 转述给用户。
5. 主 turn 结束 → 子 save 已 markDirty（注意：markSessionDirty 按 ctx 里的 agentSessionId 解析——子会话 id 复用父会话，所以 dirty 落在父会话上）→ notify 闭环照常。

### 场景 C：REST 直连（无网页）——你这边主要形态

agent 直连 edit-service :8100（不经 Go server）：`PUT /models/{id}/script` → `POST /models/{id}/script/run` → `POST /models/{id}/script/save`。注意：**直连的 run/save 不触发 Go 侧 XKT 重转**（ai.md 明示）；需要前端自动刷新时改走 Go 代理 `:8090/api/v1/models/{id}/script/...`。provenance 直连时传 `source="AI"`。

### 场景 D：离线模式（无 API key）

`agent.New` 回退 scriptedModel（固定一句答复，不调工具）——浏览器能正常建会话/发消息/看到 busy→idle 流转，只是没有智能内容。测试全部跑这条路径（scripted 确定性：同脚本两跑事件序列全等）。

### 场景 E：abort 中止

`POST /abort` → runs 表取消对应 ctx → agent 发 turn/end（无 error）→ 翻译层照常推 idle，前端 busy 清除。runs 表条件删除（identity 指针比对）防旧 run 误删新 run 登记（chat_eino.go:84-97 注释）。

---
