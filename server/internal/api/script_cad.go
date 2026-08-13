// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package api

import (
	"net/http"

	"ifcviewer/server/internal/editsvc"
	"ifcviewer/server/internal/store"
)

// kind 分流（W-0040）：script/edit 代理面在 ifc（services/ifc :8100）与
// dxf（services/cad :8200）间按模型 kind 选后端，Go 路由表两 kind 完全同构。
// edit-call 按 spec 不经 Go 代理（服务直连纪律同 IFC）；render.json 走
// serveModelFile 只读下发（见 api.go 路由注册）。

// editClientFor 取模型并按 kind 选代理 client：dxf → h.cad，其余（含存量无
// kind 迁移记录）→ h.ed。模型缺失 → 404（modelOrErr）；对应后端未配置 → 502。
// 返回 nil client 表示错误已写出，调用点直接 return。这是错误翻译 helper
// （同 modelOrErr），非业务校验。
func (h *handler) editClientFor(w http.ResponseWriter, id string) (*store.Model, *editsvc.Client) {
	m := h.modelOrErr(w, id)
	if m == nil {
		return nil, nil
	}
	cl := h.ed
	if m.Kind == store.KindDXF {
		cl = h.cad
	}
	if cl == nil {
		writeErr(w, http.StatusBadGateway, codeBadGateway, "model service not configured")
		return nil, nil
	}
	return m, cl
}
