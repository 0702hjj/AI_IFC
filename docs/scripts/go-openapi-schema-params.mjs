// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj
//
// Go server OpenAPI path 参数 helper（供 go-openapi-schema-endpoints-*.mjs 复用）。
export function modelIdParam() {
  return { name: 'id', in: 'path', required: true, description: '模型 id', schema: { type: 'string', pattern: '^m_[0-9a-f]{16}$' } }
}

export function chatCidParam() {
  return { name: 'cid', in: 'path', required: true, description: 'chat 会话 id', schema: { type: 'string', pattern: '^c_[0-9a-f]{16}$' } }
}

export function projectIdParam() {
  return { name: 'projectID', in: 'path', required: true, description: '项目 id（方案级存储键）', schema: { type: 'string', pattern: '^p_[0-9a-f]{16}$' } }
}

export function issueIdParam() {
  return { name: 'issueId', in: 'path', required: true, description: 'issue id', schema: { type: 'string', pattern: '^i_[0-9a-f]{12}$' } }
}

export function entityIdParam() {
  return { name: 'entityId', in: 'path', required: true, description: '实体 id（IFC GlobalId）', schema: { type: 'string' } }
}
