// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj
//
// Go server OpenAPI 端点条目（chat / models / issues / overrides·changes 域）。
// 由 go-openapi-schema.mjs 聚合进 endpoints；条目格式见该文件头注释。
import { modelIdParam, chatCidParam, issueIdParam, entityIdParam, projectIdParam } from './go-openapi-schema-params.mjs'

export const modelEndpoints = {
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

  // ─────────────────────────── 项目方案级存储（交付对齐 B1）───────────────────────────
  'GET /api/v1/projects/{projectID}/{name}': {
    summary: '读方案产物（plan.json / bim_supplement.json）',
    description: '读项目下的方案产物当前态（plan/cad/ifc 共享项目资源）。name 白名单：plan.json / bim_supplement.json。未落盘 404。',
    tags: ['plan'],
    parameters: [projectIdParam(), { name: 'name', in: 'path', required: true, description: '产物名（plan.json|bim_supplement.json）', schema: { type: 'string', enum: ['plan.json', 'bim_supplement.json'] } }],
    responses: {
      200: { description: 'ok', data: { type: 'object', properties: { projectId: { type: 'string' }, name: { type: 'string' }, version: { type: 'string', example: 'v1' }, content: { type: 'object' } } } },
    },
    errors: ['40400', '40001', '50000'],
  },
  'PUT /api/v1/projects/{projectID}/{name}': {
    summary: '写方案产物（plan.json / bim_supplement.json，方案级版本化）',
    description: '写项目下的方案产物并归档历史（plan_history/{name}/v{n}.json 递增）。body {content: <json 对象>}；content.project 必须 = projectID（共享 ID 对齐）。返回新版本名。',
    tags: ['plan'],
    parameters: [projectIdParam(), { name: 'name', in: 'path', required: true, description: '产物名（plan.json|bim_supplement.json）', schema: { type: 'string', enum: ['plan.json', 'bim_supplement.json'] } }],
    requestBody: {
      description: 'JSON body，content 为方案 JSON 对象',
      contentType: 'application/json',
      schema: {
        type: 'object',
        properties: { content: { type: 'object', description: '方案产物（合法 JSON 对象；project 字段 = projectID）' } },
      },
    },
    responses: {
      200: { description: 'ok', data: { type: 'object', properties: { projectId: { type: 'string' }, name: { type: 'string' }, version: { type: 'string', example: 'v1' } } } },
    },
    errors: ['40001', '40400', '50000'],
  },
  'GET /api/v1/projects/{projectID}/plan_history': {
    summary: '列方案产物历史版本',
    description: '列项目下某方案产物的历史版本（v{n} 升序）。query name 缺省 plan.json。',
    tags: ['plan'],
    parameters: [projectIdParam(), { name: 'name', in: 'query', required: false, description: '产物名（默认 plan.json）', schema: { type: 'string', enum: ['plan.json', 'bim_supplement.json'] } }],
    responses: {
      200: { description: 'ok', data: { type: 'object', properties: { projectId: { type: 'string' }, name: { type: 'string' }, history: { type: 'array', items: { type: 'string' } } } } },
    },
    errors: ['40400', '40001', '50000'],
  },
  'GET /api/v1/projects/{projectID}/plan_history/{base}/{target}/diff': {
    summary: '方案级 JSON diff（历史版本间 / 历史 vs current）',
    description: '比较方案产物的两个版本（base/target 为 v{n} 或 current），返回字段级差异（add/remove/modify + 路径）。方案演化可追溯（B3）。',
    tags: ['plan'],
    parameters: [projectIdParam(),
      { name: 'base', in: 'path', required: true, description: '基准版本（v{n} 或 current）', schema: { type: 'string' } },
      { name: 'target', in: 'path', required: true, description: '目标版本（v{n} 或 current）', schema: { type: 'string' } },
      { name: 'name', in: 'query', required: false, description: '产物名（默认 plan.json）', schema: { type: 'string', enum: ['plan.json', 'bim_supplement.json'] } }],
    responses: {
      200: { description: 'ok', data: { type: 'object', properties: { projectId: { type: 'string' }, name: { type: 'string' }, base: { type: 'string' }, target: { type: 'string' }, changes: { type: 'array', items: { type: 'object', properties: { op: { type: 'string', enum: ['add', 'remove', 'modify'] }, path: { type: 'string' }, before: {}, after: {} } } } } } },
    },
    errors: ['40400', '40001', '50000'],
  },
}
