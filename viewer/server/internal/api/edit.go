// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package api

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"

	"ifcviewer/server/internal/change"
	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/editsvc"
	"ifcviewer/server/internal/store"
)

const (
	codeConflict   = 40900
	codeBadGateway = 50200
)

func (h *handler) registerEditRoutes(mux *http.ServeMux) {
	mux.HandleFunc("PUT /api/v1/models/{id}/edit/entities/{guid}", h.editPutEntity)
	mux.HandleFunc("GET /api/v1/models/{id}/edit/entities/{guid}/editable-schema", h.editGetEditableSchema)
	mux.HandleFunc("DELETE /api/v1/models/{id}/edit/entities/{guid}", h.editDeleteEntity)
	mux.HandleFunc("GET /api/v1/models/{id}/edit/pending", h.editGetPending)
	mux.HandleFunc("DELETE /api/v1/models/{id}/edit/pending", h.editDeletePending)
	mux.HandleFunc("GET /api/v1/models/{id}/edit/history", h.editHistory)
	mux.HandleFunc("GET /api/v1/models/{id}/edit/versions", h.editVersions)
	mux.HandleFunc("POST /api/v1/models/{id}/edit/diff", h.editDiff)
	mux.HandleFunc("POST /api/v1/models/{id}/edit/commit", h.editCommit)
	mux.HandleFunc("POST /api/v1/models/{id}/overrides/migrate", h.migrateOverrides)
}

// writeEditErr 透传 Python 状态码语义：404→404、409→409、422→400，其余（含不可达）→502。
func writeEditErr(w http.ResponseWriter, err error) {
	var ee *editsvc.Error
	if errors.As(err, &ee) {
		switch ee.Status {
		case http.StatusNotFound:
			writeErr(w, http.StatusNotFound, codeNotFound, ee.Detail)
		case http.StatusConflict:
			writeErr(w, http.StatusConflict, codeConflict, ee.Detail)
		case http.StatusUnprocessableEntity:
			writeErr(w, http.StatusBadRequest, codeInvalidType, ee.Detail)
		default:
			writeErr(w, http.StatusBadGateway, codeBadGateway, "edit service error: "+ee.Detail)
		}
		return
	}
	writeErr(w, http.StatusBadGateway, codeBadGateway, err.Error())
}

func readBody(w http.ResponseWriter, r *http.Request) []byte {
	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)
	data, err := io.ReadAll(r.Body)
	if err != nil {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "invalid request body")
		return nil
	}
	return data
}

// provenanceSource 从请求体取 provenance.source（缺省 UI）并过 ValidSource。
func provenanceSource(body []byte) (string, error) {
	var in struct {
		Provenance *change.Provenance `json:"provenance"`
	}
	if len(body) > 0 {
		if err := json.Unmarshal(body, &in); err != nil {
			return "", err
		}
	}
	source := "UI"
	if in.Provenance != nil && in.Provenance.Source != "" {
		source = in.Provenance.Source
	}
	if !change.ValidSource(source) {
		return "", fmt.Errorf("provenance.source must be UI, AI or USER")
	}
	return source, nil
}

func (h *handler) editPutEntity(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	body := readBody(w, r)
	if body == nil {
		return
	}
	if _, err := provenanceSource(body); err != nil {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "provenance.source must be UI, AI or USER")
		return
	}
	data, err := h.ed.PutEntity(r.Context(), m.ID, r.PathValue("guid"), body)
	if err != nil {
		writeEditErr(w, err)
		return
	}
	writeJSON(w, json.RawMessage(data))
}

func (h *handler) editGetEditableSchema(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	data, err := h.ed.GetEditableSchema(r.Context(), m.ID, r.PathValue("guid"))
	if err != nil {
		writeEditErr(w, err)
		return
	}
	writeJSON(w, json.RawMessage(data))
}

func (h *handler) editDeleteEntity(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	body := readBody(w, r)
	if body == nil {
		return
	}
	if _, err := provenanceSource(body); err != nil {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "provenance.source must be UI, AI or USER")
		return
	}
	data, err := h.ed.DeleteEntity(r.Context(), m.ID, r.PathValue("guid"), body)
	if err != nil {
		writeEditErr(w, err)
		return
	}
	writeJSON(w, json.RawMessage(data))
}

func (h *handler) editGetPending(w http.ResponseWriter, r *http.Request) {	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	data, err := h.ed.GetPending(r.Context(), m.ID)
	if err != nil {
		writeEditErr(w, err)
		return
	}
	writeJSON(w, json.RawMessage(data))
}

func (h *handler) editDeletePending(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	data, err := h.ed.DeletePending(r.Context(), m.ID)
	if err != nil {
		writeEditErr(w, err)
		return
	}
	writeJSON(w, json.RawMessage(data))
}

func (h *handler) editHistory(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	data, err := h.ed.GetHistory(r.Context(), m.ID)
	if err != nil {
		writeEditErr(w, err)
		return
	}
	writeJSON(w, json.RawMessage(data))
}

func (h *handler) editVersions(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	versions, err := h.ed.GetVersions(r.Context(), m.ID)
	if err != nil {
		writeEditErr(w, err)
		return
	}
	writeJSON(w, versions)
}

func (h *handler) editDiff(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	body := readBody(w, r)
	if body == nil {
		return
	}
	data, err := h.ed.PostDiff(r.Context(), m.ID, body)
	if err != nil {
		writeEditErr(w, err)
		return
	}
	writeJSON(w, json.RawMessage(data))
}

// valueString 把 Python 返回的任意 JSON 标量转为 change log 的字符串值。
func valueString(v any) string {
	switch t := v.(type) {
	case nil:
		return ""
	case string:
		return t
	default:
		b, err := json.Marshal(t)
		if err != nil {
			return fmt.Sprint(t)
		}
		return string(b)
	}
}

// expandEntries 把 commit 返回的 entries 按 field change 展开为 change.Entry，
// Diff 默认为该 guid 本次 commit 的 changes 数组。
func expandEntries(entries []editsvc.Entry, operation string) []*change.Entry {
	var out []*change.Entry
	for _, e := range entries {
		diff, err := json.Marshal(e.Changes)
		if err != nil {
			diff = nil
		}
		for _, ch := range e.Changes {
			out = append(out, &change.Entry{
				EntityID:   e.GUID,
				EntityName: "",
				Field:      ch.Field,
				OldValue:   valueString(ch.OldValue),
				NewValue:   valueString(ch.NewValue),
				Author:     e.Author,
				Provenance: change.Provenance{Source: e.Provenance.Source},
				Operation:  operation,
				Diff:       diff,
			})
		}
	}
	return out
}

func versionNum(v string) int {
	if !strings.HasPrefix(v, "v") {
		return 0
	}
	n, err := strconv.Atoi(v[1:])
	if err != nil {
		return 0
	}
	return n
}

func (h *handler) editCommit(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	body := readBody(w, r)
	if body == nil {
		return
	}
	if _, err := provenanceSource(body); err != nil {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "provenance.source must be UI, AI or USER")
		return
	}
	resp, err := commitOrchestrate(r.Context(), h.ed, h.st, h.chg, h.q, m.ID)
	if err != nil {
		writeEditErr(w, err)
		return
	}
	writeJSON(w, resp)
}

// commitOrchestrate 执行 Python commit 及 Go 侧编排：commit → change log（含 diff 补充）
// → 置 converting → 入队重转。editCommit handler 与 chat 模块（AI 三连）共用。
// 策略：Python commit 成功后一律排重转；change log 写失败仅降级为响应 warning。
// Python commit 不带 body（operation 默认 update；author/provenance 随 PUT 流入 pending）。
func commitOrchestrate(ctx context.Context, ed *editsvc.Client, st *store.Store, chg change.Store, q *convert.Queue, modelID string) (map[string]any, error) {
	res, err := ed.Commit(ctx, modelID, nil)
	if err != nil {
		return nil, err
	}
	entries := expandEntries(res.Entries, "update")
	// diff 字段补充（非致命）：base = v{n-1}，n 取 versions.current。
	if vers, err := ed.GetVersions(ctx, modelID); err != nil {
		log.Printf("edit commit %s: get versions for diff: %v", modelID, err)
	} else if n := versionNum(vers.Current); n >= 2 {
		d, err := ed.Diff(ctx, modelID, fmt.Sprintf("v%d", n-1), "current")
		if err != nil {
			log.Printf("edit commit %s: diff v%d->current: %v", modelID, n-1, err)
		} else {
			byGUID := map[string][]editsvc.DiffChange{}
			for _, c := range d.Changed {
				byGUID[c.GUID] = c.Changes
			}
			for _, e := range entries {
				if chs, ok := byGUID[e.EntityID]; ok {
					if raw, err := json.Marshal(chs); err == nil {
						e.Diff = raw
					}
				}
			}
		}
	}
	var warning string
	if err := chg.Append(modelID, entries...); err != nil {
		log.Printf("edit commit %s: change log append failed after commit: %v", modelID, err)
		warning = "commit applied but change log write failed: " + err.Error()
	}
	if err := st.SetStatus(modelID, "converting", ""); err != nil {
		log.Printf("edit commit %s: set converting: %v", modelID, err)
	}
	if !q.Enqueue(modelID) {
		log.Printf("edit commit %s: conversion already pending", modelID)
	}
	resp := map[string]any{
		"committed":    res.Committed,
		"entries":      res.Entries,
		"reconverting": true,
	}
	if warning != "" {
		resp["warning"] = warning
	}
	return resp, nil
}

// --- override → 真改迁移 ---

type metaProperty struct {
	Name string `json:"name"`
}

type metaPset struct {
	ID         string         `json:"id"`
	Name       string         `json:"name"`
	Properties []metaProperty `json:"properties"`
}

type metaObject struct {
	ID             string   `json:"id"`
	PropertySetIDs []string `json:"propertySetIds"`
}

type modelMetadata struct {
	MetaObjects  []metaObject `json:"metaObjects"`
	PropertySets []metaPset   `json:"propertySets"`
}

// findPsetWithProperty 在该实体关联的 pset 中找含指定属性的 pset 名，找不到返回 ""。
func findPsetWithProperty(meta *modelMetadata, entityID, prop string) string {
	if meta == nil {
		return ""
	}
	ids := map[string]bool{}
	for _, mo := range meta.MetaObjects {
		if mo.ID == entityID {
			for _, id := range mo.PropertySetIDs {
				ids[id] = true
			}
		}
	}
	for _, ps := range meta.PropertySets {
		if !ids[ps.ID] {
			continue
		}
		for _, p := range ps.Properties {
			if p.Name == prop {
				return ps.Name
			}
		}
	}
	return ""
}

type migrateItem struct {
	EntityID string `json:"entityId"`
	Field    string `json:"field"`
}

type migrateFailed struct {
	EntityID string `json:"entityId"`
	Field    string `json:"field"`
	Reason   string `json:"reason"`
}

func (h *handler) migrateOverrides(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	var in struct {
		Author     string             `json:"author"`
		Provenance *change.Provenance `json:"provenance"`
	}
	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)
	if err := json.NewDecoder(r.Body).Decode(&in); err != nil && !errors.Is(err, io.EOF) {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "invalid json body")
		return
	}
	author := in.Author
	if author == "" {
		author = "local-user"
	}
	source := "UI"
	if in.Provenance != nil && in.Provenance.Source != "" {
		source = in.Provenance.Source
	}
	if !change.ValidSource(source) {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "provenance.source must be UI, AI or USER")
		return
	}
	all, err := h.ovr.GetAll(m.ID)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	migrated := []migrateItem{}
	failed := []migrateFailed{}
	if len(all) == 0 {
		writeJSON(w, map[string]any{"migrated": migrated, "failed": failed})
		return
	}

	var meta *modelMetadata
	if data, err := os.ReadFile(filepath.Join(h.st.ModelDir(m.ID), "metadata.json")); err == nil {
		var md modelMetadata
		if err := json.Unmarshal(data, &md); err == nil {
			meta = &md
		}
	}

	entityIDs := make([]string, 0, len(all))
	for id := range all {
		entityIDs = append(entityIDs, id)
	}
	sort.Strings(entityIDs)
	var warning string
	success := map[string][]string{}
	for _, entityID := range entityIDs {
		fields := map[string]any{}
		psets := map[string]map[string]any{}
		var attempted []string
		names := make([]string, 0, len(all[entityID]))
		for f := range all[entityID] {
			names = append(names, f)
		}
		sort.Strings(names)
		for _, f := range names {
			v := all[entityID][f]
			switch f {
			case "FireRating":
				psetName := findPsetWithProperty(meta, entityID, "FireRating")
				if psetName == "" {
					failed = append(failed, migrateFailed{entityID, f, "no pset containing FireRating found in metadata"})
					continue
				}
				psets[psetName] = map[string]any{"FireRating": v}
				attempted = append(attempted, f)
			default: // Name/Description/Comments/Classification → fields（Classification 多数会 422 → failed）
				fields[f] = v
				attempted = append(attempted, f)
			}
		}
		if len(attempted) == 0 {
			continue
		}
		putBody, _ := json.Marshal(map[string]any{
			"fields":     fields,
			"psets":      psets,
			"author":     author,
			"provenance": map[string]string{"source": source},
		})
		if _, err := h.ed.PutEntity(r.Context(), m.ID, entityID, putBody); err != nil {
			reason := err.Error()
			var ee *editsvc.Error
			if errors.As(err, &ee) {
				reason = ee.Detail
			}
			for _, f := range attempted {
				failed = append(failed, migrateFailed{entityID, f, reason})
			}
			continue
		}
		success[entityID] = attempted
	}

	if len(success) > 0 {
		commitBody, _ := json.Marshal(map[string]any{
			"author":     author,
			"provenance": map[string]string{"source": source},
			"operation":  "migrate",
		})
		res, err := h.ed.Commit(r.Context(), m.ID, commitBody)
		if err != nil {
			// commit 失败：所有 override 原样保留，下次可重试
			writeEditErr(w, err)
			return
		}
		for _, entityID := range entityIDs {
			attempted, ok := success[entityID]
			if !ok {
				continue
			}
			patch := map[string]string{}
			for _, f := range attempted {
				patch[f] = ""
				migrated = append(migrated, migrateItem{entityID, f})
			}
			if _, err := h.ovr.Set(m.ID, entityID, patch); err != nil {
				log.Printf("migrate %s: clear overrides for %s: %v", m.ID, entityID, err)
			}
		}
		// 策略同 editCommit：commit 成功后一律排重转；change log 写失败降级为 warning
		if err := h.chg.Append(m.ID, expandEntries(res.Entries, "migrate")...); err != nil {
			log.Printf("migrate %s: change log append failed after commit: %v", m.ID, err)
			warning = "commit applied but change log write failed: " + err.Error()
		}
		if err := h.st.SetStatus(m.ID, "converting", ""); err != nil {
			log.Printf("migrate %s: set converting: %v", m.ID, err)
		}
		if !h.q.Enqueue(m.ID) {
			log.Printf("migrate %s: conversion already pending", m.ID)
		}
	}
	resp := map[string]any{"migrated": migrated, "failed": failed}
	if warning != "" {
		resp["warning"] = warning
	}
	writeJSON(w, resp)
}
