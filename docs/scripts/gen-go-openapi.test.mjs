// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj
//
// 自证测试：docs/scripts/gen-go-openapi.mjs 的覆盖漂移检测对两类违规输入断言红：
//   1. routes（mux 注册）有端点而 schema 缺 → missing 非空
//   2. schema 有端点而 routes 无（死路由）→ dead 非空
// 运行：cd docs && node --test scripts/gen-go-openapi.test.mjs
import { test } from 'node:test'
import assert from 'node:assert'
import { checkCoverage, buildOpenAPI } from './gen-go-openapi.mjs'
import { endpoints, schemas } from './go-openapi-schema.mjs'

function allRoutes() {
  return Object.keys(endpoints).map((k) => {
    const idx = k.indexOf(' ')
    return { method: k.slice(0, idx), path: k.slice(idx + 1) }
  })
}

test('coverage: schema 与 routes 完全一致（基线）', () => {
  const { missing, dead } = checkCoverage(allRoutes(), Object.keys(endpoints))
  assert.deepEqual(missing, [])
  assert.deepEqual(dead, [])
})

test('coverage: routes 有端点但 schema 缺 → missing 报红', () => {
  const routes = [...allRoutes(), { method: 'POST', path: '/api/v1/models/{id}/future' }]
  const { missing, dead } = checkCoverage(routes, Object.keys(endpoints))
  assert.deepEqual(missing, ['POST /api/v1/models/{id}/future'])
  assert.deepEqual(dead, [])
})

test('coverage: schema 有死路由（routes 无）→ dead 报红', () => {
  const routes = allRoutes().filter((r) => !(r.method === 'GET' && r.path === '/api/v1/models'))
  const { missing, dead } = checkCoverage(routes, Object.keys(endpoints))
  assert.deepEqual(missing, [])
  assert.deepEqual(dead, ['GET /api/v1/models'])
})

test('coverage: 两端同时漂移 → missing 与 dead 都报', () => {
  const routes = allRoutes()
    .filter((r) => !(r.method === 'DELETE' && r.path === '/api/v1/models/{id}'))
    .concat([{ method: 'GET', path: '/api/v1/models/{id}/ghost' }])
  const { missing, dead } = checkCoverage(routes, Object.keys(endpoints))
  assert.deepEqual(missing, ['GET /api/v1/models/{id}/ghost'])
  assert.deepEqual(dead, ['DELETE /api/v1/models/{id}'])
})

test('buildOpenAPI: 生成完整 OpenAPI 3.0（envelope 包裹 + 错误码 + 静态资源不走信封）', () => {
  const doc = buildOpenAPI(allRoutes(), endpoints, schemas)
  assert.equal(doc.openapi, '3.0.3')
  const uniquePaths = new Set(allRoutes().map((r) => r.path)).size
  assert.equal(Object.keys(doc.paths).length, uniquePaths)

  const list = doc.paths['/api/v1/models']['get']
  assert.equal(list.operationId, 'getApiV1Models')
  const ok = list.responses['200'].content['application/json'].schema
  assert.equal(ok.type, 'object')
  assert.deepEqual(ok.required, ['code', 'message', 'data'])
  assert.deepEqual(ok.properties.code.enum, [0])
  assert.equal(ok.properties.data.$ref, '#/components/schemas/ModelList')

  const upload = doc.paths['/api/v1/models']['post']
  assert.ok(upload.requestBody.content['multipart/form-data'])
  assert.equal(upload.responses['400'].content['application/json'].schema.$ref, '#/components/schemas/ErrorEnvelope')

  const xkt = doc.paths['/v1/models/{id}/model.xkt']['get']
  assert.ok(xkt.responses['200'].content['application/octet-stream'])
  assert.ok(!xkt.responses['200'].content['application/json'])
})

test('buildOpenAPI: 缺少 schema 端点时抛出错误', () => {
  const extra = allRoutes().concat([{ method: 'POST', path: '/api/v1/not-covered' }])
  assert.throws(() => buildOpenAPI(extra, endpoints, schemas), /缺少 schema 端点/)
})
