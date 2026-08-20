// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj
//
// Go server OpenAPI 端点条目（edit 代理 / script-as-source 代理 / 静态资源域）。
// 由 go-openapi-schema.mjs 聚合进 endpoints；条目格式见该文件头注释。
import { modelIdParam } from './go-openapi-schema-params.mjs'

export const editEndpoints = {
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
