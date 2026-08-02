#!/usr/bin/env node
// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj
//
// Generate docs/site/reference/edit-api-reference.md from the committed OpenAPI
// schema at docs/site/public/ai-tools.openapi.json (exported from the FastAPI
// edit-service by viewer/edit-service/scripts/export_openapi.py).
// Deterministic output: stable sorting, no timestamps.
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const docsRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const schemaPath = join(docsRoot, 'site', 'public', 'ai-tools.openapi.json')
const outPath = join(docsRoot, 'site', 'reference', 'edit-api-reference.md')

const schema = JSON.parse(readFileSync(schemaPath, 'utf8'))
const out = []
out.push('# 编辑 API 参考（自动生成）', '')
out.push(
  '> 本页由 `docs/scripts/gen-edit-api-reference.mjs` 从 `docs/site/public/ai-tools.openapi.json` 自动生成，**请勿手工编辑**。',
  '> 源 schema 由 edit-service 导出（`viewer/edit-service/scripts/export_openapi.py`）；工作流与语义解释见 [IFC 编辑 API](/reference/edit-api)。',
  ''
)
out.push(`- 服务：${schema.info?.title ?? 'ifc-edit-service'} ${schema.info?.version ?? ''}`)
out.push(`- OpenAPI 版本：${schema.openapi ?? ''}`)
if (schema.servers?.length) {
  out.push(`- 默认地址：${schema.servers.map((s) => s.url).join(', ')}`)
}
out.push('', '## 端点', '')

const paths = Object.keys(schema.paths || {}).sort()
if (paths.length === 0) out.push('（无端点）')
for (const p of paths) {
  const methods = Object.keys(schema.paths[p])
    .filter((m) => ['get', 'post', 'put', 'patch', 'delete'].includes(m))
    .sort()
  for (const m of methods) {
    const op = schema.paths[p][m]
    out.push(`### ${m.toUpperCase()} ${p}`, '')
    if (op.summary) out.push(op.summary, '')
    if (op.description) out.push(op.description, '')
    const params = op.parameters || []
    if (params.length) {
      out.push('参数：', '', '| 名称 | 位置 | 必填 | 类型 | 说明 |', '| --- | --- | --- | --- | --- |')
      for (const pa of params) {
        out.push(
          `| \`${pa.name}\` | ${pa.in} | ${pa.required ? '是' : '否'} | ${pa.schema?.type ?? ''} | ${(pa.description ?? '').replace(/\|/g, '\\|')} |`
        )
      }
      out.push('')
    }
    const rb = op.requestBody?.content?.['application/json']?.schema
    if (rb) {
      out.push('请求体（application/json）：', '', '```json', JSON.stringify(rb, null, 2), '```', '')
    }
    const codes = Object.keys(op.responses || {}).sort()
    if (codes.length) {
      out.push('响应：', '', '| 状态码 | 说明 |', '| --- | --- |')
      for (const c of codes) {
        out.push(`| ${c} | ${(op.responses[c].description ?? '').replace(/\|/g, '\\|')} |`)
      }
      out.push('')
    }
  }
}

const components = schema.components?.schemas || schema['$defs'] || {}
const names = Object.keys(components).sort()
if (names.length) {
  out.push('## 组件 Schema', '')
  for (const n of names) {
    out.push(`### ${n}`, '', '```json', JSON.stringify(components[n], null, 2), '```', '')
  }
}

writeFileSync(outPath, out.join('\n') + '\n', 'utf8')
console.log(`wrote ${outPath}`)
