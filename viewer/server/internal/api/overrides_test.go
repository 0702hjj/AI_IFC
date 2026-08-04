// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"sort"
	"strings"
	"testing"

	"ifcviewer/server/internal/change"
)

func putProperties(t *testing.T, mux http.Handler, modelID, entityID, body string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest("PUT", "/api/v1/models/"+modelID+"/entities/"+entityID+"/properties", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

func getOverrides(t *testing.T, mux http.Handler, modelID string) (int, map[string]map[string]string) {
	t.Helper()
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/v1/models/"+modelID+"/overrides", nil))
	var env envelope
	if err := json.Unmarshal(rec.Body.Bytes(), &env); err != nil {
		t.Fatal(err)
	}
	raw, _ := json.Marshal(env.Data)
	var all map[string]map[string]string
	if err := json.Unmarshal(raw, &all); err != nil {
		t.Fatal(err)
	}
	return rec.Code, all
}

func listChangeEntries(t *testing.T, chg *change.FileStore, modelID string) []*change.Entry {
	t.Helper()
	entries, err := chg.List(modelID)
	if err != nil {
		t.Fatal(err)
	}
	sort.Slice(entries, func(i, j int) bool { return entries[i].Field < entries[j].Field })
	return entries
}

func TestListOverridesEmpty(t *testing.T) {
	mux, modelID, _ := newChangesTestServer(t)
	code, all := getOverrides(t, mux, modelID)
	if code != http.StatusOK {
		t.Fatalf("status = %d", code)
	}
	if all == nil || len(all) != 0 {
		t.Fatalf("all = %+v, want empty {}", all)
	}
}

func TestPutPropertiesWritesOverridesAndChangeLog(t *testing.T) {
	mux, modelID, chg := newChangesTestServer(t)
	rec := putProperties(t, mux, modelID, "e1", `{"entityName":"Wall","fields":{"Name":"X","Comments":"c1"}}`)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	var env envelope
	if err := json.Unmarshal(rec.Body.Bytes(), &env); err != nil {
		t.Fatal(err)
	}
	raw, _ := json.Marshal(env.Data)
	var effective map[string]string
	if err := json.Unmarshal(raw, &effective); err != nil {
		t.Fatal(err)
	}
	if effective["Name"] != "X" || effective["Comments"] != "c1" || len(effective) != 2 {
		t.Fatalf("effective = %+v", effective)
	}
	code, all := getOverrides(t, mux, modelID)
	if code != http.StatusOK || all["e1"]["Name"] != "X" || all["e1"]["Comments"] != "c1" {
		t.Fatalf("code = %d all = %+v", code, all)
	}
	entries := listChangeEntries(t, chg, modelID)
	if len(entries) != 2 {
		t.Fatalf("entries = %+v", entries)
	}
	for _, e := range entries {
		if e.EntityID != "e1" || e.EntityName != "Wall" || e.Author != "local-user" || e.Provenance.Source != "UI" {
			t.Fatalf("entry = %+v", e)
		}
		if e.OldValue != "" {
			t.Fatalf("entry = %+v, first write oldValue must be empty", e)
		}
	}
	if entries[0].Field != "Comments" || entries[0].NewValue != "c1" {
		t.Fatalf("entry = %+v", entries[0])
	}
	if entries[1].Field != "Name" || entries[1].NewValue != "X" {
		t.Fatalf("entry = %+v", entries[1])
	}
}

func TestPutPropertiesOldValueFromPreviousOverride(t *testing.T) {
	mux, modelID, chg := newChangesTestServer(t)
	putProperties(t, mux, modelID, "e1", `{"fields":{"Name":"X"}}`)
	rec := putProperties(t, mux, modelID, "e1", `{"entityName":"Wall","fields":{"Name":"Y"}}`)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	entries := listChangeEntries(t, chg, modelID)
	if len(entries) != 2 {
		t.Fatalf("entries = %+v", entries)
	}
	var last *change.Entry
	for _, e := range entries {
		if e.NewValue == "Y" {
			last = e
		}
	}
	if last == nil || last.OldValue != "X" {
		t.Fatalf("entry = %+v, want X -> Y", last)
	}
}

func TestPutPropertiesEmptyValueClears(t *testing.T) {
	mux, modelID, chg := newChangesTestServer(t)
	putProperties(t, mux, modelID, "e1", `{"fields":{"Name":"X","Comments":"c1"}}`)
	rec := putProperties(t, mux, modelID, "e1", `{"fields":{"Name":""}}`)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	var env envelope
	if err := json.Unmarshal(rec.Body.Bytes(), &env); err != nil {
		t.Fatal(err)
	}
	raw, _ := json.Marshal(env.Data)
	var effective map[string]string
	if err := json.Unmarshal(raw, &effective); err != nil {
		t.Fatal(err)
	}
	if _, ok := effective["Name"]; ok {
		t.Fatalf("effective = %+v, Name must be cleared", effective)
	}
	if effective["Comments"] != "c1" {
		t.Fatalf("effective = %+v, Comments must survive", effective)
	}
	entries := listChangeEntries(t, chg, modelID)
	if len(entries) != 3 {
		t.Fatalf("entries = %+v", entries)
	}
	var cleared *change.Entry
	for _, e := range entries {
		if e.Field == "Name" && e.NewValue == "" {
			cleared = e
		}
	}
	if cleared == nil || cleared.OldValue != "X" {
		t.Fatalf("clear entry = %+v, want old X new \"\"", cleared)
	}
}

func TestPutPropertiesDefaultsAuthorProvenanceOperation(t *testing.T) {
	mux, modelID, chg := newChangesTestServer(t)
	rec := putProperties(t, mux, modelID, "e1", `{"entityName":"Wall","fields":{"Name":"X"}}`)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	entries := listChangeEntries(t, chg, modelID)
	if len(entries) != 1 {
		t.Fatalf("entries = %+v", entries)
	}
	e := entries[0]
	if e.Author != "local-user" || e.Provenance.Source != "UI" || e.Operation != "update" {
		t.Fatalf("entry = %+v, want local-user/UI/update", e)
	}
}

func TestPutPropertiesCustomAuthorAndProvenance(t *testing.T) {
	mux, modelID, chg := newChangesTestServer(t)
	rec := putProperties(t, mux, modelID, "e1",
		`{"entityName":"Wall","fields":{"Name":"X"},"author":"ai-bot","provenance":{"source":"AI"}}`)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	entries := listChangeEntries(t, chg, modelID)
	if len(entries) != 1 {
		t.Fatalf("entries = %+v", entries)
	}
	e := entries[0]
	if e.Author != "ai-bot" || e.Provenance.Source != "AI" || e.Operation != "update" {
		t.Fatalf("entry = %+v, want ai-bot/AI/update", e)
	}
}

func TestPutPropertiesRejectsBadProvenanceSource(t *testing.T) {
	mux, modelID, chg := newChangesTestServer(t)
	rec := putProperties(t, mux, modelID, "e1",
		`{"entityName":"Wall","fields":{"Name":"X"},"provenance":{"source":"robot"}}`)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	var env envelope
	if err := json.Unmarshal(rec.Body.Bytes(), &env); err != nil {
		t.Fatal(err)
	}
	if env.Code != codeInvalidType {
		t.Fatalf("code = %d, want %d", env.Code, codeInvalidType)
	}
	entries := listChangeEntries(t, chg, modelID)
	if len(entries) != 0 {
		t.Fatalf("entries = %+v, rejected patch must not log", entries)
	}
	code, all := getOverrides(t, mux, modelID)
	if code != http.StatusOK || len(all) != 0 {
		t.Fatalf("all = %+v, rejected patch must not persist", all)
	}
}

func TestPutPropertiesRejectsInvalidField(t *testing.T) {
	mux, modelID, chg := newChangesTestServer(t)
	rec := putProperties(t, mux, modelID, "e1", `{"fields":{"Height":"3000"}}`)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	var env envelope
	if err := json.Unmarshal(rec.Body.Bytes(), &env); err != nil {
		t.Fatal(err)
	}
	if env.Code != codeInvalidType {
		t.Fatalf("code = %d, want %d", env.Code, codeInvalidType)
	}
	entries := listChangeEntries(t, chg, modelID)
	if len(entries) != 0 {
		t.Fatalf("entries = %+v, rejected patch must not log", entries)
	}
	code, all := getOverrides(t, mux, modelID)
	if code != http.StatusOK || len(all) != 0 {
		t.Fatalf("all = %+v, rejected patch must not persist", all)
	}
}

func TestPutPropertiesRejectsEmptyFields(t *testing.T) {
	mux, modelID, _ := newChangesTestServer(t)
	for _, body := range []string{`{}`, `{"fields":{}}`} {
		rec := putProperties(t, mux, modelID, "e1", body)
		if rec.Code != http.StatusBadRequest {
			t.Fatalf("body %s: status = %d", body, rec.Code)
		}
		var env envelope
		if err := json.Unmarshal(rec.Body.Bytes(), &env); err != nil {
			t.Fatal(err)
		}
		if env.Code != codeInvalidType {
			t.Fatalf("body %s: code = %d, want %d", body, env.Code, codeInvalidType)
		}
	}
}

func TestPutPropertiesModelNotFound(t *testing.T) {
	mux, _, _ := newChangesTestServer(t)
	rec := putProperties(t, mux, "m_0000000000000000", "e1", `{"fields":{"Name":"X"}}`)
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404", rec.Code)
	}
}

func TestListOverridesModelNotFound(t *testing.T) {
	mux, _, _ := newChangesTestServer(t)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/v1/models/m_0000000000000000/overrides", nil))
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404", rec.Code)
	}
}
