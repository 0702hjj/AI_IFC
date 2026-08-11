#!/usr/bin/env node
// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj
//
// Generate docs/site/public/go-server.openapi.json (OpenAPI 3.0) for the Go
// viewer server (:8090).
//
// 诚实设计边界：Go 用 stdlib net/http mux，无 schema 反射——request/response
// schema 无法从代码自动导出。方案 = 路由清单自动（gen-go-routes.mjs 从 mux 注册
// 提取）+ schema 手工维护（go-openapi-schema.mjs）+ 覆盖漂移检测：
//
//   生成器断言「schema 端点集 ⊆ routes 端点集 且 routes 端点集 ⊆ schema 端点集」。
//   新增路由未配 schema → 红；schema 有死路由 → 红。这是能达到的最强自动一致性。
//
// 输出 OpenAPI 3.0：info/tags/paths（summary/operationId/parameters/
// requestBody/response envelope schema）+ components/schemas。
// Deterministic output: stable sorting, no timestamps.
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { endpoints, schemas, errorCodes } from './go-openapi-schema.mjs'

const docsRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')

export function routeKey(route) {
  return `${route.method} ${route.path}`
}

// checkCoverage 双向覆盖校验：routes 端点集 vs schema 端点集。
// 返回 { missing, dead }（纯函数，供测试自证）：
//   missing = routes 有但 schema 无（新增路由未配 schema → 应红）
//   dead    = schema 有但 routes 无（死 schema 条目 → 应红）
export function checkCoverage(routesEndpoints, schemaKeys) {
  const routes = new Set(routesEndpoints.map(routeKey))
  const schema = new Set(schemaKeys)
  const missing = [...routes].filter((k) => !schema.has(k)).sort()
  const dead = [...schema].filter((k) => !routes.has(k)).sort()
  return { missing, dead }
}

function operationIdFor(method, path) {
  return (
    method.toLowerCase() +
    path
      .split('/')
      .filter(Boolean)
      .map((seg) => seg.replace(/[{}\-.]/g, ' '))
      .map((seg) => seg.replace(/\b[a-z]/g, (c) => c.toUpperCase()).replace(/\s+/g, ''))
      .join('')
  )
}

function envelopeOf(dataSchema) {
  const data =
    dataSchema === null
      ? { type: 'object', nullable: true, description: '始终为 null' }
      : typeof dataSchema === 'string'
        ? { $ref: dataSchema }
        : dataSchema
  return {
    type: 'object',
    required: ['code', 'message', 'data'],
    properties: {
      code: { type: 'integer', enum: [0] },
      message: { type: 'string', example: 'ok' },
      data,
    },
  }
}

function buildResponses(schemaEntry) {
  const out = {}
  for (const [status, spec] of Object.entries(schemaEntry.responses || {})) {
    if (spec.raw) {
      out[status] = {
        description: spec.description,
        content: { [spec.raw.contentType]: { schema: spec.raw.schema } },
      }
    } else if (spec.data !== undefined) {
      out[status] = {
        description: spec.description,
        content: { 'application/json': { schema: envelopeOf(spec.data) } },
      }
    } else {
      out[status] = { description: spec.description }
    }
  }
  for (const code of schemaEntry.errors || []) {
    const err = errorCodes[code]
    if (!err) throw new Error(`go-openapi: 未知错误码 ${code}（go-openapi-schema.mjs 的 errorCodes 未定义）`)
    const status = String(err.status)
    if (!out[status]) {
      out[status] = {
        description: err.description,
        content: { 'application/json': { schema: { $ref: '#/components/schemas/ErrorEnvelope' } } },
      }
    } else {
      out[status].description += `；${err.description}`
    }
  }
  return out
}

function buildRequestBody(body) {
  const contentType = body.multipart ? 'multipart/form-data' : body.contentType || 'application/json'
  return {
    description: body.description,
    required: body.required !== false,
    content: { [contentType]: { schema: body.schema } },
  }
}

export function buildOpenAPI(routesEndpoints, schemaEndpoints, schemaComponents) {
  const paths = {}
  for (const route of routesEndpoints) {
    const key = routeKey(route)
    const se = schemaEndpoints[key]
    if (!se) throw new Error(`go-openapi: 缺少 schema 端点 ${key}`)
    const method = route.method.toLowerCase()
    if (!paths[route.path]) paths[route.path] = {}
    const op = {
      summary: se.summary ?? '',
      description: se.description ?? '',
      operationId: se.operationId ?? operationIdFor(route.method, route.path),
      tags: se.tags ?? [],
      parameters: se.parameters ?? [],
      responses: buildResponses(se),
    }
    if (se.requestBody) op.requestBody = buildRequestBody(se.requestBody)
    paths[route.path][method] = op
  }
  return {
    openapi: '3.0.3',
    info: {
      title: 'AI_IFC viewer server (Go)',
      version: '0.2.0',
      description:
        'AI_IFC 平台对外唯一入口（默认 :8090）。JSON 信封统一 `{code, message, data}`，`code=0` 成功。' +
        '模型 id 格式 `^m_[0-9a-f]{16}$`；issue id 格式 `^i_[0-9a-f]{12}$`。\n\n' +
        '生成方式（诚实边界：Go 用 stdlib mux，无 schema 反射）：路由清单由 `docs/scripts/gen-go-routes.mjs` 从 mux 注册自动提取，' +
        '请求/响应 schema 由 `docs/scripts/go-openapi-schema.mjs` 手工维护；`gen-go-openapi.mjs` 对两者做双向覆盖漂移检测——' +
        '新增路由未配 schema 或 schema 存在死路由都会令生成失败（CI 红）。\n\n' +
        '鉴权：默认关闭（`apiToken`/`VIEWER_API_TOKEN` 为空）。开启后除 OPTIONS 与 `GET /v1/models/...` 只读静态文件外，' +
        '全部端点需 `Authorization: Bearer <token>`（401 envelope 码 40100）。',
    },
    servers: [{ url: 'http://localhost:8090', description: 'Go 网关（本地默认端口）' }],
    tags: [
      { name: 'chat', description: '对话式 AI 建模（demo 模块）' },
      { name: 'models', description: '模型上传/列表/详情/删除/下载/重试' },
      { name: 'issues', description: '设计审查 Issue 与截图' },
      { name: 'overrides', description: 'metadata override 属性改写 + change log' },
      { name: 'edit', description: '编辑代理（只读/对比端点）' },
      { name: 'script', description: 'script-as-source 编辑代理（暂存/沙箱/大版本）' },
      { name: 'static', description: '静态资源（直挂，不走 JSON 信封）' },
    ],
    paths,
    components: {
      schemas: schemaComponents,
      securitySchemes: {
        bearerAuth: {
          type: 'http',
          scheme: 'bearer',
          description: '可选：默认鉴权关闭；启用（VIEWER_API_TOKEN 非空）后需 Bearer 令牌。',
        },
      },
    },
  }
}

function main() {
  const routesPath = join(docsRoot, 'site', 'public', 'go-rest-api.routes.json')
  const outPath = join(docsRoot, 'site', 'public', 'go-server.openapi.json')
  const routes = JSON.parse(readFileSync(routesPath, 'utf8'))

  const { missing, dead } = checkCoverage(routes.endpoints, Object.keys(endpoints))
  const problems = []
  if (missing.length) {
    problems.push('routes（mux 注册）有端点但 schema 未覆盖——新增路由未配 schema，必须补齐：')
    problems.push(missing.map((k) => `  - ${k}`).join('\n'))
  }
  if (dead.length) {
    problems.push('schema 有端点但 routes（mux 注册）无此路由——死 schema 条目，必须删除：')
    problems.push(dead.map((k) => `  - ${k}`).join('\n'))
  }
  if (problems.length) {
    console.error('go-openapi 覆盖校验失败（docs/scripts/gen-go-openapi.mjs）')
    console.error(problems.join('\n'))
    console.error('修复：新端点去 docs/scripts/go-openapi-schema.mjs 补 schema 条目；死路由则删除对应条目。')
    process.exit(1)
  }

  const doc = buildOpenAPI(routes.endpoints, endpoints, schemas)
  writeFileSync(outPath, JSON.stringify(doc, null, 2) + '\n', 'utf8')
  console.log(`wrote ${outPath} (${Object.keys(doc.paths).length} paths, ${Object.keys(doc.components.schemas).length} schemas)`)
}

const isMain = process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url
if (isMain) main()
