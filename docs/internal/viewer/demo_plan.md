# Demo 完整执行计划：对话式 AI 建模闭环

> 日期：2026-08-01（重写：聊天桥接**融入 Go server**，取消独立 demo-bridge）。本文档是分步实施计划（做什么、先后顺序、验收标准）。
> 接口契约、请求/响应格式、数据对齐事项见配套文档 [`demo_connect.md`](demo_connect.md)（引用其章节号，不重复细节）。

## 远景一句话

用户在**对话式界面**里和 AI 说话：「建一栋两层小楼」→ AI 从零生成模型；「把外墙改厚」→ AI 大改模型——**AI 只负责产出 IFC 文件，落盘、版本、重转、注册全部由 Go server 内的固定代码自动完成**，用户刷新即见新模型，可查历史、可回退。

## 阶段总览

| Phase | 目标 | 关键产出 | 验收标准 |
|---|---|---|---|
| P0 环境就绪 | 三服务 + opencode serve 起通、目录对齐 | 运行中的服务栈 | 上传模型 → ready → 查看器可见 |
| P1 Go chat 模块骨架 | opencode 客户端 + chat 路由 + SSE 透传 | `internal/opencode/` + `api/chat.go` | curl 发消息 → SSE 收到流式事件 |
| P2 主链路（改模型） | 事件监听 + 固定代码三连 | 监听 goroutine + notify 逻辑 | agent 改完自动出 v2，前端见新模型 |
| P3 聊天前端 | 对话 UI + 流式渲染 + 模型面板 | 新聊天页面 | 浏览器完成「说→改→看」闭环 |
| P4 从零构建 | 空白会话 → AI 生成 → 内部注册绑定 | staging 约定 + 注册分支 | 无文件上传，对话生成模型并显示 |
| P5 回退与审计 | 回退指令 + 审计面验证 | `rollback_to` | 回退显示旧模型，版本+1、history 留痕 |
| P6 演练沉淀 | 彩排 + 文档 | 演示脚本、截图 | 按脚本 10 分钟无卡点演完 |

依赖：P0 → P1 → P2 → P3（主链路可用）→ P4 / P5（可并行）→ P6。

---

## P0 环境就绪

| # | 步骤 | 命令/位置 | 验收 |
|---|---|---|---|
| 0.1 | edit-service :8100 | `cd viewer/edit-service && uv run uvicorn app.main:app --port 8100`（前置：ifcdiff 软链已建） | `curl :8100/health` → ok |
| 0.2 | Go server :8090 | `cd viewer/server && go run ./cmd/server` | `curl :8090/api/models` → `{"code":0,...}` |
| 0.3 | web :5173 | `cd viewer/web && npm run dev` | 模型库页可开 |
| 0.4 | opencode serve :4096 | 工作目录 = **`IFC_front/AI_IFC`**（demo 适配环境，与开发版隔离）；`opencode serve --port 4096 --cors http://localhost:5173` | `curl :4096/global/health` → healthy |
| 0.4b | opencode 环境适配 | ① `opencode.json` 从 `CADapi/AI_IFC` 适配复制到 `IFC_front/AI_IFC/`（provider、`"skills":{"paths":["skills"]}`、mcp）② 确认 `skills/aiifc` 已就位（已复制）③ 建 `.opencode/agent/` demo 规则文件（staging 约定、写权限收窄、禁调 viewer HTTP） | opencode 内 agent/skills 列表可见 |
| 0.5 | **数据目录对齐**（头号坑） | `server_config.json` dataDir（= `viewer/data/`）= edit-service `VIEWER_DATA_DIR`，且 opencode 可读写同一目录；建 `viewer/data/staging/` | 三处比对一致 |
| 0.6 | 冒烟 | 浏览器上传 fixture（`viewer/converter/test/fixtures/`） | converting→ready，xeokit 显示 |

**产出**：运行中的服务栈 + 一个 ready 测试模型（记录 modelId）。

## P1 Go chat 模块骨架

按现有结构模式增量开发（对照 demo_connect §1 的落点表）：

| # | 步骤 | 说明 | 验收 |
|---|---|---|---|
| 1.1 | `internal/opencode/` 客户端 | 仿 `internal/editsvc/`：建会话、`prompt_async`、订阅 `/event`（带断线重连+退避）；错误映射为带状态码的 Error | 单测连真实 :4096 通过 |
| 1.2 | `internal/api/chat.go` 路由 | 仿 `edit.go` 注册进 mux：`POST /api/chat/sessions`、`GET /api/chat/sessions`、`POST /api/chat/sessions/{cid}/messages`、`GET /api/chat/sessions/{cid}/events`；包络 `{code,message,data}` | curl 建会话/发消息返回包络正确 |
| 1.3 | 会话映射 | 内存 map：chatSessionId ↔ opencodeSessionId ↔ modelId（可空） | — |
| 1.4 | SSE 透传 | 全局一条 opencode `/event` 订阅 goroutine → 按 sessionID 过滤 → 转发各会话 SSE 客户端（http.Flusher） | `curl -N` 看到 `message.part.updated` 事件 |
| 1.5 | 配置 | `server_config.json` 加 `openCodeURL` + `VIEWER_OPENCODE_URL` 环境变量（仿 EditServiceURL） | 缺省 :4096 可连 |

**产出**：chat 模块骨架，「前端 ↔ Go ↔ opencode」管道通。

## P2 主链路（改模型）

| # | 步骤 | 说明 | 验收 |
|---|---|---|---|
| 2.1 | 事件监听触发器 | 订阅循环内：`file.edited` 命中 `uploads/{modelId}.ifc` → dirty=true；`session.idle` + dirty + bound → 触发 notify（demo_connect §4.1） | 日志可见触发记录 |
| 2.2 | notify 固定代码 | ① editsvc DELETE pending（坏文件自检，借力 load 失败）② 正则取 IfcProject guid ③ editsvc PUT pset 标记（provenance=AI）④ 复用 commit 编排（建议从 edit.go 抽共享函数：editsvc commit + change log + SetStatus + Enqueue）→ 推 `viewer.committed` | 单测：手动改 uploads 文件后触发 → versions 出 v{n+1} |
| 2.3 | commit 编排抽函数 | 把 `edit.go` commit handler 里「调 Python commit → change log → SetStatus → Enqueue」抽为包内函数，handler 与 chat 模块共用 | edit_test.go 原有用例全绿 |
| 2.4 | agent 规则配置 | `IFC_front/AI_IFC/.opencode/agent/` demo 规则：先在 staging 改副本自检、原子替换（写临时名+改名）uploads/{id}.ifc；写权限仅 uploads/staging 两处；禁调 viewer HTTP | agent 行为符合预期 |
| 2.5 | 端到端联调 | 聊天发「把某构件改名」→ 全链路观察 | SSE 流式过程 + `viewer.committed`；versions 出 v2；查看器刷新见新模型；修改历史 tab 有 opencode-cli/AI 条目 |

**产出**：「改模型」闭环可用。

## P3 聊天前端

新页面，**不动 viewer 现有组件**（查看器面板复用现有 Viewer 组件/路由）：

| # | 步骤 | 说明 | 验收 |
|---|---|---|---|
| 3.1 | 页面骨架 | 左右布局：左聊天区（消息列表+输入框），右查看器面板 | 页面可开 |
| 3.2 | 流式渲染 | `EventSource` 连 `/api/chat/sessions/{cid}/events`：`message.part.updated` delta 追加渲染；tool part 显示「正在执行…」；`viewer.committed` 显示「已落盘 v{n+1}，转换中」 | 打字机效果可见 |
| 3.3 | 模型状态条 | 轮询 `GET /api/models/{id}`（2s），converting 显示「转换中…」，failed 显示 error | 改模型后状态条变化正确 |
| 3.4 | 双入口 | 「打开已有模型」（选 modelId 建 bound 会话）/「新建空白项目」（unbound） | 两种会话均可建 |
| 3.5 | 挂接 | 聊天页作为新路由挂 viewer web（最小侵入新增，不改现有组件） | 一处说、一处看 |

**产出**：浏览器内「说 → 改 → 看」闭环。

## P4 从零构建链路（骨架初始化方案，2026-08-02 修订并实施 ✅）

> **方案变更**：用户点击「新建」那一刻项目即完整就位（modelId + 骨架文件 + 会话绑定），agent 只是后续的修改者。原「staging 取件 + 注册分支 + unbound 状态机」方案废弃。会话永远 bound，从零构建与改模型走同一主链路。

| # | 步骤 | 说明 | 验收 |
|---|---|---|---|
| 4.1 | 骨架技术验证 ✅ | 最小合法 IFC（IfcProject+上下文+单位）经上传 → converter ready；edit-service 可开 | `m_100ce81a07293fe2` ready |
| 4.2 | `POST /api/chat/projects` ✅ | Go 写骨架（IFC base64 GlobalId 生成器，`chat_test.go` 单测）→ store.Create → Enqueue | 返回 modelId，converting→ready |
| 4.3 | 前端入口 ✅ | 模型库「新建空白项目」→ createChatProject → 跳 `/view/{id}`（进页自动建 bound 会话并展开侧边栏）；`/view/new` 特判与 model_registered 跳转已删除 | 点击即入正常项目页 |
| 4.4 | agent 规则同步 ✅ | ifc-demo.md：从零构建同样走 uploads 主链路（staging 仅草稿区）；SKILL.md #22 输出路径改 `uploads/{modelId}.ifc` | 规则与 SKILL 一致 |
| 4.5 | 会话连续性 ✅ | 幂等：同 modelId 复用会话（两次 create 同 cid ✓）；持久化 chat-sessions.json（kill 重启 restored 同 cid ✓）；历史回填 GET messages（4 条 ✓） | 退出再打开同一会话 + 历史可见 |
| 4.6 | 端到端联调 | `/view/{骨架}` →「建一个两层小楼」→ 主链路三连 → v1=骨架 v2=AI 模型 → diff 全量 added → 自动刷新 | 一句话出模型 |

**产出**：「建一个两层小楼」一句话出模型。

## P5 回退与审计

| # | 步骤 | 说明 | 验收 |
|---|---|---|---|
| 5.1 | `rollback_to` | Go 内实现：预检版本存在 → 复制 `versions/v{n}.ifc` → `uploads/{id}.ifc` → 走 P2 同一套三连（summary="Rollback to v{n}"）（demo_connect §4.3） | 调用后显示旧模型，版本号+1 |
| 5.2 | 回退指令 | 聊天固定句式（「回退到上一版」「回退到 v2」）→ chat 模块解析执行（指令前缀匹配，不做 NLP） | 对话回退生效 |
| 5.3 | 审计面走查 | 修改历史 tab（AI 条目）、`GET /versions`、`POST /diff` 全展示 | 三处数据一致 |

## P6 演练与沉淀

| # | 步骤 | 说明 |
|---|---|---|
| 6.1 | 彩排 | 按演示脚本走 3 遍，掐表 |
| 6.2 | 预案 | 服务重启顺序；坏文件恢复（最近版本 cp 回 uploads）；转换超时话术；会话失效重建（P1.3 内存映射） |
| 6.3 | 沉淀 | 命令、请求/响应样例、截图 → `demo_connect.md` 附录；缺口清单状态更新 |

## 演示脚本（demo 当天，约 10 分钟）

1. **开场**（30s）：架构一句话——「我说话，AI 改模型，落盘版本全是 Go 里固定代码自动办的」
2. **从零构建**（3min）：新建空白项目 →「建一个两层小楼，带门窗」→ 流式看 agent 干活 → `viewer.model_registered` → 查看器亮出模型
3. **对话修改**（2min）：「把外墙厚度改成 300」→ 过程流 → `viewer.committed v2` → 刷新见变化
4. **审计面**（2min）：修改历史 tab（opencode-cli/AI）→ 版本列表 → diff 视图
5. **回退**（1min）：「回退到上一版」→ 模型变回，版本 v3
6. **收尾**（30s）：缺口清单（revert/reconvert 端点）为下一步正式化内容

## 分工建议

| 方 | 负责 |
|---|---|
| 接入/AI 侧 | Go chat 模块（P1/P2/P4/P5）、聊天前端（P3）、agent 规则配置、staging 约定 |
| viewer 实现方 | P0 环境支持；commit 编排抽函数（P2.3，重构不动行为）；缺口清单 demo 后议 |

## 关键纪律（全程遵守，对齐 viewer 设计原则）

- **chat 代码独立可拆**：新增限 `internal/opencode/` + `api/chat.go` + main.go 装配，不揉进 edit.go；P2.3 是唯一触碰既有代码的点（纯重构）
- **LLM 零接口感知**：提交/注册/回退全由固定代码触发，agent 规则明文禁止调 viewer HTTP
- **坏文件两道闸**：agent 先在 staging 改副本自检（事前）+ 三连首调即检（事后兜底）
- **数据目录三方一致**：环境变动后第一件事核对 P0.5
- **viewer 包络统一**：浏览器只见 `{code,message,data}`；opencode 原生格式不出 Go
- **存储范式不另起炉灶**：文件系统即真相、路径即键；staging/副本写临时名再原子改名（同 viewer `os.replace` 模式）；归属关系放 chat 模块映射层，不为用户分目录
- **环境隔离**：demo 用 `IFC_front/AI_IFC`（复制的 skill + 适配的 opencode.json），不碰 `CADapi/AI_IFC` 开发环境
