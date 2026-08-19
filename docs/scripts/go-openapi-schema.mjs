// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj
//
// 手工维护的 Go server（server，:8090）OpenAPI schema 定义源。
//
// 诚实设计边界：Go 用 stdlib net/http mux，无 schema 反射——request/response
// schema 无法从代码自动导出。方案 = 路由清单自动（gen-go-routes.mjs 从 mux 注册
// 提取）+ schema 手工维护（本文件）+ 覆盖漂移检测（gen-go-openapi.mjs 断言
// 「schema 端点集 ⊆ routes 端点集 且 routes 端点集 ⊆ schema 端点集」）。
//
// 键格式：`<METHOD> <path>`（与 go-rest-api.routes.json 的 method/path 完全一致）。
// 内容来源：docs/site/reference/rest-api.md 契约 + server/internal/api/*.go
// 实际行为 + services/ifc/app/routes_scripts.py（script 代理透传的响应形状）。
//
// 每条端点可含：
//   summary / description / tags / operationId
//   parameters: OpenAPI 参数数组（path/query；modelId pattern ^m_[0-9a-f]{16}$）
//   requestBody: { description, contentType?, multipart?, schema }
//   responses:  { <httpStatus>: { description, data? | raw? } }
//     data → 200 成功信封 {code:0,message:"ok",data}（data 可为 $ref 或内联 schema）
//     raw  → 非信封响应（静态资源/SSE/下载）：{ contentType, schema }
//   errors: [code, ...] 错误码表（错误信封 {code,message,data:null}）

export const schemas = {
  Model: {
    type: 'object',
    required: ['id', 'name', 'size', 'status', 'createdAt', 'error'],
    properties: {
      id: { type: 'string', pattern: '^m_[0-9a-f]{16}$', description: '模型 id' },
      name: { type: 'string', description: '文件名' },
      size: { type: 'integer', format: 'int64', description: 'IFC 文件字节数' },
      status: { type: 'string', enum: ['converting', 'ready', 'failed'] },
      createdAt: { type: 'string', format: 'date-time', description: 'ISO8601 UTC' },
      error: { type: 'string', description: '失败原因（ready 时为空串）' },
    },
  },
  ModelList: {
    type: 'array',
    items: { $ref: '#/components/schemas/Model' },
  },
  Camera: {
    type: 'object',
    required: ['eye', 'look', 'up'],
    properties: {
      eye: { type: 'array', minItems: 3, maxItems: 3, items: { type: 'number' } },
      look: { type: 'array', minItems: 3, maxItems: 3, items: { type: 'number' } },
      up: { type: 'array', minItems: 3, maxItems: 3, items: { type: 'number' } },
    },
  },
  Provenance: {
    type: 'object',
    required: ['source'],
    properties: {
      source: { type: 'string', enum: ['UI', 'AI', 'USER'], description: '变更来源' },
      origin: { type: 'string' },
    },
  },
  Issue: {
    type: 'object',
    required: ['id', 'entityId', 'entityName', 'entityType', 'title', 'comment', 'status', 'author', 'provenance', 'camera', 'screenshot', 'createdAt', 'updatedAt'],
    properties: {
      id: { type: 'string', pattern: '^i_[0-9a-f]{12}$', description: 'issue id' },
      entityId: { type: 'string' },
      entityName: { type: 'string' },
      entityType: { type: 'string' },
      title: { type: 'string' },
      comment: { type: 'string' },
      status: { type: 'string', enum: ['open', 'checking', 'resolved'] },
      author: { type: 'string', description: '默认 local-user' },
      provenance: { $ref: '#/components/schemas/Provenance' },
      camera: { $ref: '#/components/schemas/Camera' },
      screenshot: { type: 'string', description: '相对路径 issues/{id}.png，无截图时为空串' },
      createdAt: { type: 'string', format: 'date-time' },
      updatedAt: { type: 'string', format: 'date-time' },
    },
  },
  IssueList: {
    type: 'array',
    items: { $ref: '#/components/schemas/Issue' },
  },
  IssuePatch: {
    type: 'object',
    properties: {
      title: { type: 'string' },
      comment: { type: 'string' },
      status: { type: 'string', enum: ['open', 'checking', 'resolved'] },
    },
    description: '仅更新传入字段；title 清空后非空才合法',
  },
  IssueInput: {
    type: 'object',
    required: ['entityId', 'entityName', 'entityType', 'title', 'comment'],
    properties: {
      entityId: { type: 'string' },
      entityName: { type: 'string' },
      entityType: { type: 'string' },
      title: { type: 'string' },
      comment: { type: 'string' },
      author: { type: 'string' },
      provenance: { $ref: '#/components/schemas/Provenance' },
      camera: { $ref: '#/components/schemas/Camera' },
    },
  },
  ChangeEntry: {
    type: 'object',
    required: ['id', 'entityId', 'entityName', 'field', 'oldValue', 'newValue', 'author', 'provenance', 'operation', 'createdAt'],
    properties: {
      id: { type: 'string', pattern: '^c_[0-9a-f]{12}$', description: 'change id' },
      entityId: { type: 'string' },
      entityName: { type: 'string' },
      field: { type: 'string', description: '白名单字段：Name/Description/Classification/FireRating/Comments' },
      oldValue: { type: 'string', description: '被覆盖前的值' },
      newValue: { type: 'string', description: '空字符串 = 清除该字段 override' },
      author: { type: 'string' },
      provenance: { $ref: '#/components/schemas/Provenance' },
      operation: { type: 'string', enum: ['update'] },
      diff: { type: 'object', description: '脚本 diff（optional）' },
      createdAt: { type: 'string', format: 'date-time' },
    },
  },
  ChangeList: {
    type: 'array',
    items: { $ref: '#/components/schemas/ChangeEntry' },
  },
  OverrideFields: {
    type: 'object',
    additionalProperties: { type: 'string' },
    description: 'entityId → 字段 → 值 的 override 集合',
  },
  Overrides: {
    type: 'object',
    additionalProperties: { $ref: '#/components/schemas/OverrideFields' },
    description: '全部 override：{ [entityId]: { [field]: value } }，无 override 时为 {}',
  },
  PropertiesPatch: {
    type: 'object',
    required: ['fields'],
    properties: {
      entityName: { type: 'string' },
      fields: {
        type: 'object',
        minProperties: 1,
        additionalProperties: { type: 'string' },
        description: '字段名 ∈ {Name, Description, Classification, FireRating, Comments}；空串值 = 清除 override',
      },
      author: { type: 'string', description: '默认 local-user' },
      provenance: { $ref: '#/components/schemas/Provenance' },
    },
  },
  ChatSession: {
    type: 'object',
    required: ['chatSessionId', 'opencodeSessionId', 'modelId', 'title', 'createdAt'],
    properties: {
      chatSessionId: { type: 'string', pattern: '^c_[0-9a-f]{16}$' },
      opencodeSessionId: { type: 'string', description: '历史字段名（契约兼容保留）；Eino 接管后语义为 agent 会话 ID' },
      modelId: { type: 'string', pattern: '^m_[0-9a-f]{16}$', description: '空串 = 未绑定模型' },
      title: { type: 'string' },
      createdAt: { type: 'string', format: 'date-time' },
    },
  },
  ChatSessionList: {
    type: 'array',
    items: { $ref: '#/components/schemas/ChatSession' },
  },
  CreateSessionBody: {
    type: 'object',
    properties: {
      title: { type: 'string', description: '默认 "chat"' },
      modelId: { type: 'string', pattern: '^m_[0-9a-f]{16}$', description: '绑定模型；同 modelId 幂等复用已有会话' },
    },
  },
  PostMessageBody: {
    type: 'object',
    required: ['text'],
    properties: { text: { type: 'string', minLength: 1 } },
  },
  ScriptStatus: {
    type: 'object',
    required: ['modelId', 'script', 'staged', 'canUndo', 'canRedo', 'maxSteps'],
    properties: {
      modelId: { type: 'string', pattern: '^m_[0-9a-f]{16}$' },
      script: { type: 'string' },
      staged: { type: 'integer', minimum: 0 },
      canUndo: { type: 'boolean' },
      canRedo: { type: 'boolean' },
      maxSteps: { type: 'integer' },
    },
  },
  StageScriptBody: {
    type: 'object',
    properties: {
      script: { type: 'string', description: '脚本全文（与 params 恰好二选一）' },
      params: { type: 'object', description: 'PARAMS 块改写（与 script 恰好二选一）' },
      note: { type: 'string' },
    },
  },
  ScriptState: {
    type: 'object',
    required: ['modelId', 'staged', 'canUndo', 'canRedo'],
    properties: {
      modelId: { type: 'string', pattern: '^m_[0-9a-f]{16}$' },
      staged: { type: 'integer', minimum: 0 },
      canUndo: { type: 'boolean' },
      canRedo: { type: 'boolean' },
    },
  },
  ScriptParams: {
    type: 'object',
    required: ['modelId', 'params'],
    properties: {
      modelId: { type: 'string', pattern: '^m_[0-9a-f]{16}$' },
      params: { type: 'object' },
    },
  },
  ScriptVersionInfo: {
    type: 'object',
    required: ['version', 'createdAt'],
    properties: {
      version: { type: 'string', pattern: '^v\\d+$' },
      createdAt: { type: 'string', format: 'date-time' },
      note: { type: 'string' },
    },
  },
  ScriptList: {
    type: 'object',
    required: ['modelId', 'scripts', 'versions'],
    properties: {
      modelId: { type: 'string', pattern: '^m_[0-9a-f]{16}$' },
      scripts: { type: 'array', items: { $ref: '#/components/schemas/ScriptVersionInfo' } },
      versions: { type: 'array', items: { $ref: '#/components/schemas/ScriptVersionInfo' } },
    },
  },
  ScriptRunResult: {
    type: 'object',
    required: ['modelId', 'ok'],
    properties: {
      modelId: { type: 'string', pattern: '^m_[0-9a-f]{16}$' },
      ok: { type: 'boolean', const: true },
      semanticDiff: {
        anyOf: [{ $ref: '#/components/schemas/SemanticDiffCounts' }, { type: 'null' }],
        description: '构件级 {added, removed, changed} 计数（旧 uploads 产物 vs 本次 run）；diff 失败/首次 run 无旧产物时为 null',
      },
    },
  },
  SemanticDiffCounts: {
    type: 'object',
    required: ['added', 'removed', 'changed'],
    properties: {
      added: { type: 'integer' },
      removed: { type: 'integer' },
      changed: { type: 'integer' },
    },
  },
  SaveBody: {
    type: 'object',
    properties: { note: { type: 'string' } },
  },
  ScriptSaveResult: {
    type: 'object',
    required: ['modelId', 'version', 'staged', 'alignment'],
    properties: {
      modelId: { type: 'string', pattern: '^m_[0-9a-f]{16}$' },
      version: { type: 'string', pattern: '^v\\d+$' },
      staged: { type: 'integer', minimum: 0 },
      alignment: {
        type: 'object',
        nullable: true,
        properties: { added: { type: 'integer' }, removed: { type: 'integer' }, changed: { type: 'integer' } },
      },
    },
  },
  RollbackBody: {
    type: 'object',
    required: ['version'],
    properties: { version: { type: 'string', pattern: '^v\\d+$' } },
  },
  ScriptRollbackResult: {
    type: 'object',
    required: ['modelId', 'version', 'script'],
    properties: {
      modelId: { type: 'string', pattern: '^m_[0-9a-f]{16}$' },
      version: { type: 'string', pattern: '^v\\d+$' },
      script: { type: 'string' },
    },
  },
  ScriptDiffBody: {
    type: 'object',
    required: ['base', 'target'],
    properties: {
      base: { type: 'string', pattern: '^v\\d+$' },
      target: { type: 'string', pattern: '^v\\d+$' },
    },
  },
  ScriptDiffResult: {
    type: 'object',
    required: ['base', 'target', 'engine'],
    properties: {
      base: { type: 'string' },
      target: { type: 'string' },
      engine: { type: 'string', const: 'script' },
      diff: { type: 'string', description: 'unified 文本 diff' },
      params: { type: 'object', description: 'PARAMS 变更' },
      stats: { type: 'object', description: 'diff 统计' },
    },
  },
  LocateResult: {
    type: 'object',
    required: ['found'],
    properties: {
      found: { type: 'boolean' },
      designKey: { type: 'string' },
      stale: { type: 'boolean', description: 'staging 与 map 分叉，行号不可信' },
      line: { type: 'integer' },
      col: { type: 'integer' },
      snippet: { type: 'string' },
      origin: { type: 'string' },
    },
  },
  DiffBody: {
    type: 'object',
    required: ['base', 'target'],
    properties: {
      base: { type: 'string', pattern: '^v\\d+$' },
      target: { type: 'string', description: '版本号或 "current"（uploads 现态）' },
    },
  },
  DiffResult: {
    type: 'object',
    required: ['base', 'target'],
    properties: {
      base: { type: 'string' },
      target: { type: 'string' },
      added: { type: 'array', items: { type: 'string' }, description: '新增 GlobalId' },
      removed: { type: 'array', items: { type: 'string' }, description: '删除 GlobalId' },
      changed: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            guid: { type: 'string' },
            changes: {
              type: 'array',
              items: {
                type: 'object',
                properties: { field: { type: 'string' }, old: {}, new: {} },
              },
            },
          },
        },
      },
    },
  },
  EditVersionsResult: {
    type: 'object',
    required: ['versions', 'current'],
    properties: {
      versions: { type: 'array', items: { $ref: '#/components/schemas/ScriptVersionInfo' } },
      current: { type: 'string', nullable: true, description: '最新版本号（无任何提交时为 null）' },
    },
  },
  PendingEntry: {
    type: 'object',
    additionalProperties: true,
    description: 'pending 项（L1 直改退役后仅供 script-run 回放簿记，形状以运行服务为准）',
  },
  EditHistoryEntry: {
    type: 'object',
    additionalProperties: true,
    description: '持久化编辑历史条目（含 operation 字段；直改退役后只读保留）',
  },
  AbortResult: {
    type: 'object',
    required: ['aborted'],
    properties: { aborted: { type: 'boolean', const: true } },
  },
  AcceptedResult: {
    type: 'object',
    required: ['accepted'],
    properties: { accepted: { type: 'boolean', const: true } },
  },
  DiscardedResult: {
    type: 'object',
    required: ['discarded'],
    properties: { discarded: { type: 'integer' } },
  },
  ErrorEnvelope: {
    type: 'object',
    required: ['code', 'message', 'data'],
    properties: {
      code: { type: 'integer', description: '业务错误码（≠0）' },
      message: { type: 'string' },
      data: { type: 'null' },
    },
  },
}

// 错误码表：code → { status, description }。错误响应统一信封 {code,message,data:null}。
export const errorCodes = {
  40001: { status: 400, description: '参数/校验错误' },
  40002: { status: 400, description: '超出大小上限' },
  40100: { status: 401, description: '未授权：缺少或无效的 Authorization: Bearer 令牌' },
  40400: { status: 404, description: '模型/Issue/会话/资源不存在' },
  40900: { status: 409, description: '状态冲突（无脚本可执行/无可撤销/暂存步骤不足等）' },
  50000: { status: 500, description: '服务器内部错误' },
  50200: { status: 502, description: '上游服务不可达或错误（edit-service / cad-edit-service）' },
  50400: { status: 504, description: 'diff timed out' },
}

function modelIdParam() {
  return { name: 'id', in: 'path', required: true, description: '模型 id', schema: { type: 'string', pattern: '^m_[0-9a-f]{16}$' } }
}

function chatCidParam() {
  return { name: 'cid', in: 'path', required: true, description: 'chat 会话 id', schema: { type: 'string', pattern: '^c_[0-9a-f]{16}$' } }
}

function issueIdParam() {
  return { name: 'issueId', in: 'path', required: true, description: 'issue id', schema: { type: 'string', pattern: '^i_[0-9a-f]{12}$' } }
}

function entityIdParam() {
  return { name: 'entityId', in: 'path', required: true, description: '实体 id（IFC GlobalId）', schema: { type: 'string' } }
}

export const endpoints = {
  // ─────────────────────────── chat（demo）───────────────────────────
  'POST /api/v1/chat/projects': {
    summary: '创建空白项目',
    description: '写入骨架 IFC 并注册为模型（modelId 即刻就位），随后 AI 从零构建走与改模型相同的主链路。title 可空，默认 "AI 项目"。',
    tags: ['chat'],
    requestBody: {
      description: 'JSON body，title 可空',
      contentType: 'application/json',
      schema: {
        type: 'object',
        properties: { title: { type: 'string', description: '默认 "AI 项目"' } },
      },
    },
    responses: {
      200: { description: 'ok', data: '#/components/schemas/Model' },
    },
    errors: ['50000'],
  },
  'GET /api/v1/chat/sessions': {
    summary: '会话列表',
    description: '列出全部 chat 会话（demo 模块，内存态 + chat-sessions.json 持久化）。',
    tags: ['chat'],
    responses: {
      200: { description: 'ok', data: '#/components/schemas/ChatSessionList' },
    },
    errors: [],
  },
  'POST /api/v1/chat/sessions': {
    summary: '创建会话（同 modelId 幂等）',
    description: '创建 chat 会话并绑定模型（进程内 Eino agent）。同一 modelId 永远只有一个会话——退出再打开返回同一会话。modelId 可空（会话不绑定模型）。',
    tags: ['chat'],
    requestBody: {
      description: 'JSON body',
      contentType: 'application/json',
      schema: { $ref: '#/components/schemas/CreateSessionBody' },
    },
    responses: {
      200: { description: 'ok', data: '#/components/schemas/ChatSession' },
    },
    errors: ['40001', '50200'],
  },
  'POST /api/v1/chat/sessions/{cid}/abort': {
    summary: '中止会话当前 turn',
    description: '中止 AI 当前响应（前端 busy 时"发送"变"停止"调用此端点）。',
    tags: ['chat'],
    parameters: [chatCidParam()],
    responses: {
      200: { description: 'ok', data: '#/components/schemas/AbortResult' },
    },
    errors: ['40400', '50200'],
  },
  'GET /api/v1/chat/sessions/{cid}/events': {
    summary: '会话事件流（SSE）',
    description: 'Server-Sent Events：`event: <type>` + `data: <json>` 帧。事件类型含 session.creating / session.idle / message / session.error / viewer.committed / viewer.notify_failed 等。非信封响应。',
    tags: ['chat'],
    parameters: [chatCidParam()],
    responses: {
      200: {
        description: 'text/event-stream 事件流',
        raw: { contentType: 'text/event-stream', schema: { type: 'string', description: 'SSE 帧（event + data）' } },
      },
    },
    errors: ['40400'],
  },
  'GET /api/v1/chat/sessions/{cid}/messages': {
    summary: '会话消息历史',
    description: '回填会话历史（重新打开会话时）。data 形状与 opencode 历史形状对齐（Eino 事件日志投影）。',
    tags: ['chat'],
    parameters: [chatCidParam()],
    responses: {
      200: {
        description: 'ok',
        data: { type: 'array', items: { type: 'object', additionalProperties: true }, description: '消息数组（opencode 兼容形状）' },
      },
    },
    errors: ['40400', '50200'],
  },
  'POST /api/v1/chat/sessions/{cid}/messages': {
    summary: '发送消息给 AI',
    description: '把用户消息（含绑定模型时的系统上下文）异步交给进程内 Eino agent。返回 accepted=true 表示已受理，事件经 SSE 推送。',
    tags: ['chat'],
    parameters: [chatCidParam()],
    requestBody: {
      description: 'JSON body，text 必填非空',
      contentType: 'application/json',
      schema: { $ref: '#/components/schemas/PostMessageBody' },
    },
    responses: {
      200: { description: 'ok', data: '#/components/schemas/AcceptedResult' },
    },
    errors: ['40001', '40400', '50200'],
  },

  // ─────────────────────────── models ───────────────────────────
  'POST /api/v1/models': {
    summary: '上传 IFC 模型',
    description: '上传 IFC 文件并触发异步转换（→ converter 产出 XKT/metadata）。仅 `.ifc`，≤200MB。',
    tags: ['models'],
    requestBody: {
      description: 'multipart/form-data：字段 file',
      multipart: true,
      schema: {
        type: 'object',
        required: ['file'],
        properties: { file: { type: 'string', format: 'binary', description: '.ifc 文件（≤200MB）' } },
      },
    },
    responses: {
      200: { description: 'ok（status=converting）', data: '#/components/schemas/Model' },
    },
    errors: ['40001', '40002', '50000'],
  },
  'GET /api/v1/models': {
    summary: '模型列表',
    description: '列出全部模型，按 createdAt 降序（前端 2s 轮询直至所有模型脱离 converting）。',
    tags: ['models'],
    responses: {
      200: { description: 'ok', data: '#/components/schemas/ModelList' },
    },
    errors: ['50000'],
  },
  'GET /api/v1/models/{id}': {
    summary: '模型详情',
    description: '单模型详情，结构与列表项相同。',
    tags: ['models'],
    parameters: [modelIdParam()],
    responses: {
      200: { description: 'ok', data: '#/components/schemas/Model' },
    },
    errors: ['40400'],
  },
  'POST /api/v1/models/{id}/retry': {
    summary: '重试失败模型转换',
    description: '仅 `failed` 模型可重试：重新入队转换并返回更新后的模型对象（status=converting）。',
    tags: ['models'],
    parameters: [modelIdParam()],
    responses: {
      200: { description: 'ok（status=converting）', data: '#/components/schemas/Model' },
    },
    errors: ['40001', '40400', '50000'],
  },
  'DELETE /api/v1/models/{id}': {
    summary: '删除模型',
    description: '删除该模型的 IFC、XKT、metadata、状态文件及 issues/changes/overrides。',
    tags: ['models'],
    parameters: [modelIdParam()],
    responses: {
      200: { description: 'ok（data: null）', data: null },
    },
    errors: ['40400', '50000'],
  },
  'GET /api/v1/models/{id}/download': {
    summary: '下载原始 IFC',
    description: '下载原始 IFC 文件（非信封响应），带 Content-Disposition attachment。',
    tags: ['models'],
    parameters: [modelIdParam()],
    responses: {
      200: {
        description: '原始 .ifc 文件流',
        raw: { contentType: 'application/octet-stream', schema: { type: 'string', format: 'binary' } },
      },
    },
    errors: ['40400'],
  },

  // ─────────────────────────── issues ───────────────────────────
  'GET /api/v1/models/{id}/issues': {
    summary: 'Issue 列表',
    description: '返回该模型全部 Issue，按 createdAt 降序。',
    tags: ['issues'],
    parameters: [modelIdParam()],
    responses: {
      200: { description: 'ok', data: '#/components/schemas/IssueList' },
    },
    errors: ['40400', '50000'],
  },
  'POST /api/v1/models/{id}/issues': {
    summary: '创建 Issue',
    description: 'multipart/form-data：`issue` 字段为 JSON 字符串（entityId/entityName/entityType/title/comment/author?/provenance?/camera?），title 必填；`screenshot` 可选 PNG ≤5MB。返回含生成的 id、status=open、默认 author/provenance 与 screenshot 相对路径。',
    tags: ['issues'],
    parameters: [modelIdParam()],
    requestBody: {
      description: 'multipart/form-data：issue（JSON 字符串，必填）+ screenshot（PNG，≤5MB，可选）',
      multipart: true,
      schema: {
        type: 'object',
        required: ['issue'],
        properties: {
          issue: { type: 'string', description: 'Issue JSON 字符串（见组件 IssueInput 结构）' },
          screenshot: { type: 'string', format: 'binary', description: 'PNG ≤5MB' },
        },
      },
    },
    responses: {
      200: { description: 'ok', data: '#/components/schemas/Issue' },
    },
    errors: ['40001', '40002', '50000'],
  },
  'PATCH /api/v1/models/{id}/issues/{issueId}': {
    summary: '更新 Issue',
    description: 'JSON body：title/comment/status 仅更新传入字段。',
    tags: ['issues'],
    parameters: [modelIdParam(), issueIdParam()],
    requestBody: {
      description: 'JSON body（全字段可选）',
      contentType: 'application/json',
      schema: { $ref: '#/components/schemas/IssuePatch' },
    },
    responses: {
      200: { description: 'ok', data: '#/components/schemas/Issue' },
    },
    errors: ['40001', '40400'],
  },
  'DELETE /api/v1/models/{id}/issues/{issueId}': {
    summary: '删除 Issue',
    description: '删除 Issue 及其截图文件。',
    tags: ['issues'],
    parameters: [modelIdParam(), issueIdParam()],
    responses: {
      200: { description: 'ok（data: null）', data: null },
    },
    errors: ['40400'],
  },
  'GET /v1/models/{id}/issues/{file}': {
    summary: 'Issue 截图静态服务',
    description: '非信封响应。`file` 必须匹配 `i_[0-9a-f]{12}\\.png`，否则 404。',
    tags: ['static'],
    parameters: [
      modelIdParam(),
      { name: 'file', in: 'path', required: true, description: '截图文件名', schema: { type: 'string', pattern: '^i_[0-9a-f]{12}\\.png$' } },
    ],
    responses: {
      200: {
        description: 'PNG 图片',
        raw: { contentType: 'image/png', schema: { type: 'string', format: 'binary' } },
      },
    },
    errors: ['40400'],
  },

  // ─────────────────────────── overrides / changes ───────────────────────────
  'GET /api/v1/models/{id}/overrides': {
    summary: '属性 Override 集合',
    description: '返回全部 override：`{ [entityId]: { [field]: value } }`（无 override 时为 `{}`）。',
    tags: ['overrides'],
    parameters: [modelIdParam()],
    responses: {
      200: { description: 'ok', data: '#/components/schemas/Overrides' },
    },
    errors: ['40400', '50000'],
  },
  'PUT /api/v1/models/{id}/entities/{entityId}/properties': {
    summary: '改写实体属性（metadata override）',
    description: '属性修改走 metadata override（不改 IFC 本体）。fields 必填非空；字段名不在白名单返回 40001；空串值 = 清除该字段 override。每字段写一条 change log。返回该实体当前生效的 override 集合。',
    tags: ['overrides'],
    parameters: [modelIdParam(), entityIdParam()],
    requestBody: {
      description: 'JSON body',
      contentType: 'application/json',
      schema: { $ref: '#/components/schemas/PropertiesPatch' },
    },
    responses: {
      200: { description: 'ok（该实体当前生效 override）', data: '#/components/schemas/OverrideFields' },
    },
    errors: ['40001', '40400', '50000'],
  },
  'GET /api/v1/models/{id}/changes': {
    summary: '修改记录（change log）',
    description: '按 createdAt 降序返回 ChangeEntry[]（无记录时为 `[]`）。',
    tags: ['overrides'],
    parameters: [modelIdParam()],
    responses: {
      200: { description: 'ok', data: '#/components/schemas/ChangeList' },
    },
    errors: ['40400', '50000'],
  },

  // ─────────────────────────── 编辑代理（只读/对比）───────────────────────────
  'POST /api/v1/models/{id}/edit/diff': {
    summary: '版本语义 diff（代理 edit-service）',
    description: '代理 `POST /models/{id}/diff`：对比两个大版本快照（target 可为 "current" 表示 uploads 现态），返回 GlobalId 键的 added/removed/changed 属性级 diff。',
    tags: ['edit'],
    parameters: [modelIdParam()],
    requestBody: {
      description: 'JSON body',
      contentType: 'application/json',
      schema: { $ref: '#/components/schemas/DiffBody' },
    },
    responses: {
      200: { description: 'ok', data: '#/components/schemas/DiffResult' },
    },
    errors: ['40001', '40400', '40900', '50200', '50400'],
  },
  'GET /api/v1/models/{id}/edit/history': {
    summary: '编辑历史（代理 edit-service，只读）',
    description: '代理 `GET /models/{id}/history`：持久化编辑历史（直改退役后只读保留历史数据）。',
    tags: ['edit'],
    parameters: [modelIdParam()],
    responses: {
      200: {
        description: 'ok',
        data: { type: 'array', items: { $ref: '#/components/schemas/EditHistoryEntry' } },
      },
    },
    errors: ['40400', '50200'],
  },
  'GET /api/v1/models/{id}/edit/pending': {
    summary: '当前 pending（代理 edit-service，只读）',
    description: '代理 `GET /models/{id}/pending`：列出当前 pending（直改退役后仅供 script-run 回放簿记）。',
    tags: ['edit'],
    parameters: [modelIdParam()],
    responses: {
      200: {
        description: 'ok',
        data: { type: 'array', items: { $ref: '#/components/schemas/PendingEntry' } },
      },
    },
    errors: ['40400', '50200'],
  },
  'DELETE /api/v1/models/{id}/edit/pending': {
    summary: '丢弃 pending（代理 edit-service）',
    description: '代理 `DELETE /models/{id}/pending`：丢弃全部 pending（卸载并从磁盘重载内存模型）。',
    tags: ['edit'],
    parameters: [modelIdParam()],
    responses: {
      200: { description: 'ok', data: '#/components/schemas/DiscardedResult' },
    },
    errors: ['40400', '50200'],
  },
  'GET /api/v1/models/{id}/edit/versions': {
    summary: '版本快照列表（代理 edit-service）',
    description: '代理 `GET /models/{id}/versions`：列出大版本快照（未提交前 versions=[]、current=null）。',
    tags: ['edit'],
    parameters: [modelIdParam()],
    responses: {
      200: { description: 'ok', data: '#/components/schemas/EditVersionsResult' },
    },
    errors: ['40400', '50200'],
  },

  // ─────────────────────────── script-as-source 代理 ───────────────────────────
  'GET /api/v1/models/{id}/script': {
    summary: '当前脚本（代理 edit-service）',
    description: '代理 `GET /models/{id}/script`：当前暂存脚本（或最后保存的大版本 base）。纯 IFC 上传的 legacy 模型无脚本 → 404。',
    tags: ['script'],
    parameters: [modelIdParam()],
    responses: {
      200: { description: 'ok', data: '#/components/schemas/ScriptStatus' },
    },
    errors: ['40400', '50200'],
  },
  'PUT /api/v1/models/{id}/script': {
    summary: '暂存脚本（代理 edit-service）',
    description: '代理 `PUT /models/{id}/script`：全量替换脚本或仅改 PARAMS 块（script/params 恰好二选一）。写入 WPS 式 10 步暂存链。',
    tags: ['script'],
    parameters: [modelIdParam()],
    requestBody: {
      description: 'JSON body',
      contentType: 'application/json',
      schema: { $ref: '#/components/schemas/StageScriptBody' },
    },
    responses: {
      200: { description: 'ok', data: '#/components/schemas/ScriptState' },
    },
    errors: ['40001', '40900', '50200'],
  },
  'GET /api/v1/models/{id}/script/params': {
    summary: '脚本 PARAMS（代理 edit-service）',
    description: '代理 `GET /models/{id}/script/params`：ast 提取当前脚本的 PARAMS dict（不执行）。',
    tags: ['script'],
    parameters: [modelIdParam()],
    responses: {
      200: { description: 'ok', data: '#/components/schemas/ScriptParams' },
    },
    errors: ['40400', '50200'],
  },
  'POST /api/v1/models/{id}/script/undo': {
    summary: '撤销暂存（代理 edit-service）',
    description: '代理 `POST /models/{id}/script/undo`：回退一步暂存链（无可撤销 → 409）。',
    tags: ['script'],
    parameters: [modelIdParam()],
    responses: {
      200: {
        description: 'ok',
        data: { type: 'object', required: ['modelId', 'script', 'canRedo'], properties: { modelId: { type: 'string' }, script: { type: 'string' }, canRedo: { type: 'boolean' } } },
      },
    },
    errors: ['40400', '40900', '50200'],
  },
  'POST /api/v1/models/{id}/script/redo': {
    summary: '重做暂存（代理 edit-service）',
    description: '代理 `POST /models/{id}/script/redo`：前进一步暂存链（无可重做 → 409）。',
    tags: ['script'],
    parameters: [modelIdParam()],
    responses: {
      200: {
        description: 'ok',
        data: { type: 'object', required: ['modelId', 'script', 'canUndo'], properties: { modelId: { type: 'string' }, script: { type: 'string' }, canUndo: { type: 'boolean' } } },
      },
    },
    errors: ['40400', '40900', '50200'],
  },
  'POST /api/v1/models/{id}/script/discard': {
    summary: '丢弃暂存（代理 edit-service）',
    description: '代理 `POST /models/{id}/script/discard`：丢弃暂存编辑，回到最后保存的大版本（不产生版本）。',
    tags: ['script'],
    parameters: [modelIdParam()],
    responses: {
      200: {
        description: 'ok',
        data: { type: 'object', required: ['modelId', 'discarded', 'script'], properties: { modelId: { type: 'string' }, discarded: { type: 'boolean' }, script: { type: 'string' } } },
      },
    },
    errors: ['40400', '40900', '50200'],
  },
  'POST /api/v1/models/{id}/script/run': {
    summary: '沙箱运行脚本（代理 edit-service）',
    description: '代理 `POST /models/{id}/script/run`：沙箱运行当前暂存脚本并原子替换 uploads/{id}.ifc（不产生版本）。成功后排 XKT 重转（模型 status → converting）。沙箱最长 60s。',
    tags: ['script'],
    parameters: [modelIdParam()],
    responses: {
      200: { description: 'ok', data: '#/components/schemas/ScriptRunResult' },
    },
    errors: ['40400', '40900', '50200'],
  },
  'POST /api/v1/models/{id}/script/save': {
    summary: '保存为大版本（代理 edit-service）',
    description: '代理 `POST /models/{id}/script/save`：沙箱运行后快照 scripts/v{n}.py + versions/v{n}.ifc（原子、lockstep）。运行失败 → 422 且不产生版本。成功后排 XKT 重转。',
    tags: ['script'],
    parameters: [modelIdParam()],
    requestBody: {
      description: 'JSON body（可选）',
      contentType: 'application/json',
      schema: { $ref: '#/components/schemas/SaveBody' },
    },
    responses: {
      200: { description: 'ok', data: '#/components/schemas/ScriptSaveResult' },
    },
    errors: ['40400', '40900', '50200'],
  },
  'POST /api/v1/models/{id}/script/rollback': {
    summary: '回滚到大版本（代理 edit-service）',
    description: '代理 `POST /models/{id}/script/rollback`：恢复指定大版本的脚本到暂存并重新运行进 uploads。成功后排 XKT 重转。',
    tags: ['script'],
    parameters: [modelIdParam()],
    requestBody: {
      description: 'JSON body',
      contentType: 'application/json',
      schema: { $ref: '#/components/schemas/RollbackBody' },
    },
    responses: {
      200: { description: 'ok', data: '#/components/schemas/ScriptRollbackResult' },
    },
    errors: ['40001', '40400', '40900', '50200'],
  },
  'POST /api/v1/models/{id}/script/diff': {
    summary: '大版本脚本 diff（代理 edit-service）',
    description: '代理 `POST /models/{id}/script/diff`：两大版本的 unified 文本 diff + PARAMS 变更 + 统计（AI 主要面向的 diff）。',
    tags: ['script'],
    parameters: [modelIdParam()],
    requestBody: {
      description: 'JSON body',
      contentType: 'application/json',
      schema: { $ref: '#/components/schemas/ScriptDiffBody' },
    },
    responses: {
      200: { description: 'ok', data: '#/components/schemas/ScriptDiffResult' },
    },
    errors: ['40001', '40400', '40900', '50200'],
  },
  'GET /api/v1/models/{id}/script/staging/diff': {
    summary: '暂存步骤小版本 diff（代理 edit-service）',
    description: '代理 `GET /models/{id}/script/staging/diff`：暂存链步间 diff（默认最近两步）。query（from/to）原样透传。',
    tags: ['script'],
    parameters: [
      modelIdParam(),
      { name: 'from', in: 'query', required: false, description: '起始步骤下标（0-based，默认最新两步中的前一步）', schema: { type: 'integer', minimum: 0 } },
      { name: 'to', in: 'query', required: false, description: '结束步骤下标（默认最新一步）', schema: { type: 'integer', minimum: 0 } },
    ],
    responses: {
      200: { description: 'ok', data: '#/components/schemas/ScriptDiffResult' },
    },
    errors: ['40001', '40400', '40900', '50200'],
  },
  'GET /api/v1/models/{id}/script/locate': {
    summary: '定位 guid 脚本调用点（代理 edit-service）',
    description: '代理 `GET /models/{id}/script/locate?guid=`：guid → designKey → 脚本调用点（行/列/片段）。miss 返回 200 {found:false}（不 5xx）。staging 与 map 分叉时降级 {found:false, stale:true}。',
    tags: ['script'],
    parameters: [
      modelIdParam(),
      { name: 'guid', in: 'query', required: true, description: 'IFC GlobalId', schema: { type: 'string' } },
    ],
    responses: {
      200: { description: 'ok', data: '#/components/schemas/LocateResult' },
    },
    errors: ['40400', '50200'],
  },
  'GET /api/v1/models/{id}/scripts': {
    summary: '大版本列表（代理 edit-service）',
    description: '代理 `GET /models/{id}/scripts`：脚本大版本列表（legacy IFC-only 模型为空）。',
    tags: ['script'],
    parameters: [modelIdParam()],
    responses: {
      200: { description: 'ok', data: '#/components/schemas/ScriptList' },
    },
    errors: ['40400', '50200'],
  },

  // ─────────────────────────── 静态资源（直挂，不走信封）───────────────────────────
  'GET /v1/models/{id}/metadata.json': {
    summary: '模型元数据（xeokit 元模型）',
    description: '非信封响应。converter 用 web-ifc 从原 IFC 提取的空间结构树 + 属性集，可直接作为 XKTLoaderPlugin.load({metaModelSrc}) 输入。',
    tags: ['static'],
    parameters: [modelIdParam()],
    responses: {
      200: {
        description: 'xeokit 元模型 JSON',
        raw: { contentType: 'application/json', schema: { type: 'object', description: '见 rest-api.md「metadata.json Schema」' } },
      },
    },
    errors: ['40400'],
  },
  'GET /v1/models/{id}/render.json': {
    summary: 'CAD 渲染数据（render payload v2）',
    description: '非信封响应。services/cad 在 script/run、script/save 成功后原子发布的实体级渲染 JSON（schemaVersion 2，实体带 XDATA key），供前端 Canvas 2D 预览；仅 kind=dxf 模型存在。',
    tags: ['static'],
    parameters: [modelIdParam()],
    responses: {
      200: {
        description: 'render payload v2 JSON',
        raw: { contentType: 'application/json', schema: { type: 'object', description: '见 rest-api.md「render.json Schema」' } },
      },
    },
    errors: ['40400'],
  },
  'GET /v1/models/{id}/model.xkt': {
    summary: 'XKT 几何数据',
    description: '非信封响应。XKT 二进制几何数据（支持 Range 请求）。',
    tags: ['static'],
    parameters: [modelIdParam()],
    responses: {
      200: {
        description: 'XKT 二进制流',
        raw: { contentType: 'application/octet-stream', schema: { type: 'string', format: 'binary' } },
      },
    },
    errors: ['40400'],
  },
}
