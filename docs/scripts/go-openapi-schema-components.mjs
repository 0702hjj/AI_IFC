// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj
//
// Go server OpenAPI 组件 schema（components/schemas）与错误码表。
// 由 go-openapi-schema.mjs 聚合导出；条目格式与设计边界说明见该文件头注释。
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
      buildingChanges: {
        type: ['array', 'null'],
        description: 'building.json 交付索引字段级差异（两侧均有 sidecar 时非空；否则 null）',
        items: { type: 'object', properties: { op: { type: 'string', enum: ['add', 'remove', 'modify'] }, path: { type: 'string' }, before: {}, after: {} } },
      },
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
