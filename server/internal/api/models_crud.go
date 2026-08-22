// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// models_crud.go：平台模型 CRUD（upload/list/get/retry/delete/download + 静态渲染文件）。
// 从 api.go 拆出（W-0049 行数门控）：删除模型联动项目摘除（RemoveModel 防孤儿 modelId）。

package api

import (
	"errors"
	"log"
	"net/http"
	"net/url"
	"path/filepath"
	"regexp"

	"ifcviewer/server/internal/store"
)

func (h *handler) modelOrErr(w http.ResponseWriter, id string) *store.Model {
	m, err := h.st.Get(id)
	if errors.Is(err, store.ErrNotFound) || errors.Is(err, store.ErrInvalidID) {
		writeErr(w, http.StatusNotFound, codeNotFound, "model not found")
		return nil
	}
	if err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return nil
	}
	return m
}

func (h *handler) upload(w http.ResponseWriter, r *http.Request) {
	r.Body = http.MaxBytesReader(w, r.Body, h.maxUpload)
	if err := r.ParseMultipartForm(h.maxUpload); err != nil {
		writeErr(w, http.StatusBadRequest, codeTooLarge, "file exceeds size limit")
		return
	}
	file, fh, err := r.FormFile("file")
	if err != nil {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "missing file field")
		return
	}
	defer file.Close()
	kind, err := store.KindForFilename(fh.Filename)
	if errors.Is(err, store.ErrUnsupportedExt) {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "only .ifc and .dxf files are allowed")
		return
	}
	m, err := h.st.CreateWithKind(fh.Filename, fh.Size, file, kind)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	// dxf 无 XKT 转换（services/cad 直接产 render.json），创建即 ready、不入队。
	if kind == store.KindIFC {
		h.q.Enqueue(m.ID)
	}
	writeJSON(w, m)
}

func (h *handler) list(w http.ResponseWriter, r *http.Request) {
	models, err := h.st.List()
	if err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	if models == nil {
		models = []*store.Model{}
	}
	writeJSON(w, models)
}

func (h *handler) get(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	writeJSON(w, m)
}

func (h *handler) retry(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	if m.Status != "failed" {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "only failed models can be retried")
		return
	}
	// dxf 无转换链路：直接回 ready，不入队（W-0040）。
	if m.Kind == store.KindDXF {
		if err := h.st.SetStatus(m.ID, "ready", ""); err != nil {
			writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
			return
		}
	} else {
		if err := h.st.SetStatus(m.ID, "converting", ""); err != nil {
			writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
			return
		}
		h.q.Enqueue(m.ID)
	}
	m, err := h.st.Get(m.ID)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	writeJSON(w, m)
}

func (h *handler) delete(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	// 先清理各 store 的模型作用域数据（PG 模式下文件系统删除无法覆盖），再删模型目录。
	if err := h.iss.DeleteModel(m.ID); err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	if err := h.chg.DeleteModel(m.ID); err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	if err := h.ovr.DeleteModel(m.ID); err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	// 项目联动：模型若有反向归属（Model.ProjectID），从项目摘除——防孤儿 modelId 残留 project.json。
	if h.ps != nil && m.ProjectID != "" {
		if err := h.ps.RemoveModel(m.ProjectID, m.ID); err != nil {
			log.Printf("models/%s: 项目摘除 %s 失败（仅告警，不阻断删除）: %v", m.ID, m.ProjectID, err)
		}
	}
	if err := h.st.Delete(m.ID); err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	writeJSON(w, nil)
}

func (h *handler) download(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	w.Header().Set("Content-Disposition", "attachment; filename*=UTF-8''"+url.PathEscape(m.Name))
	http.ServeFile(w, r, h.st.SourcePath(m))
}

func (h *handler) serveModelFile(name string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		m := h.modelOrErr(w, r.PathValue("id"))
		if m == nil {
			return
		}
		http.ServeFile(w, r, filepath.Join(h.st.ModelDir(m.ID), name))
	}
}

const maxIssueUpload = 6 << 20 // 6MB
const maxScreenshot = 5 << 20  // 5MB

var issueFilePattern = regexp.MustCompile(`^i_[0-9a-f]{12}\.png$`)

