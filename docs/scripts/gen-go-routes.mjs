#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj
//
// Generate docs/site/public/go-rest-api.routes.json from the Go server's mux
// registrations (server/internal/api/{api,edit}.go). Deterministic.
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
const apiDir = join(repoRoot, 'server', 'internal', 'api')
const outPath = join(repoRoot, 'docs', 'site', 'public', 'go-rest-api.routes.json')

const files = ['api.go', 'edit.go', 'chat.go', 'script.go']
const endpointRe = /mux\.HandleFunc\(\s*"([A-Z]+)\s+([^"]+)"\s*,\s*(\w+(?:\.\w+)?(?:\("[^"]*"\))?)\)/g
const endpoints = []
for (const f of files) {
  const src = readFileSync(join(apiDir, f), 'utf8')
  for (const m of src.matchAll(endpointRe)) {
    endpoints.push({ method: m[1], path: m[2], handler: m[3], file: `server/internal/api/${f}` })
  }
}
endpoints.sort((a, b) => a.path.localeCompare(b.path) || a.method.localeCompare(b.method))

const contract = {
  service: 'server (Go)',
  source: 'server/internal/api/{api,edit,chat,script,design}.go',
  generatedBy: 'docs/scripts/gen-go-routes.mjs',
  note: 'Machine-readable endpoint inventory extracted from Go mux registrations. Human-readable contract: docs/site/reference/rest-api.md.',
  endpoints,
}
writeFileSync(outPath, JSON.stringify(contract, null, 2) + '\n', 'utf8')
console.log(`wrote ${outPath} (${endpoints.length} endpoints)`)
