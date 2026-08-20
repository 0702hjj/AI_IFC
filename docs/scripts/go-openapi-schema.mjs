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
//
// 模块拆分（W-0049 文件 ≤500 行门控）：本文件只做聚合导出，导出签名不变——
//   schemas / errorCodes ← go-openapi-schema-components.mjs
//   endpoints            ← go-openapi-schema-endpoints-model.mjs + go-openapi-schema-endpoints-edit.mjs
//                          （path 参数 helper 共用 go-openapi-schema-params.mjs）

export { schemas, errorCodes } from './go-openapi-schema-components.mjs'

import { modelEndpoints } from './go-openapi-schema-endpoints-model.mjs'
import { editEndpoints } from './go-openapi-schema-endpoints-edit.mjs'

export const endpoints = { ...modelEndpoints, ...editEndpoints }
