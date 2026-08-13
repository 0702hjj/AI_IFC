// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"ifcviewer/server/internal/change"
)

func TestListChanges(t *testing.T) {
	mux, modelID, chg := newChangesTestServer(t)
	first := &change.Entry{EntityID: "e1", EntityName: "Wall", Field: "width", OldValue: "100", NewValue: "200", Author: "local-user", Provenance: change.Provenance{Source: "UI"}}
	second := &change.Entry{EntityID: "e1", EntityName: "Wall", Field: "height", OldValue: "3000", NewValue: "3200"}
	if err := chg.Append(modelID, first, second); err != nil {
		t.Fatal(err)
	}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/v1/models/"+modelID+"/changes", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	var env envelope
	if err := json.Unmarshal(rec.Body.Bytes(), &env); err != nil {
		t.Fatal(err)
	}
	raw, _ := json.Marshal(env.Data)
	var list []*change.Entry
	if err := json.Unmarshal(raw, &list); err != nil {
		t.Fatal(err)
	}
	if len(list) != 2 {
		t.Fatalf("list = %+v", list)
	}
	if list[0].ID != second.ID || list[1].ID != first.ID {
		t.Fatalf("order = [%s %s], want [%s %s]", list[0].ID, list[1].ID, second.ID, first.ID)
	}
	if list[1].Field != "width" || list[1].Provenance.Source != "UI" {
		t.Fatalf("entry = %+v", list[1])
	}
}

func TestListChangesEmpty(t *testing.T) {
	mux, modelID, _ := newChangesTestServer(t)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/v1/models/"+modelID+"/changes", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d", rec.Code)
	}
	var env envelope
	_ = json.Unmarshal(rec.Body.Bytes(), &env)
	raw, _ := json.Marshal(env.Data)
	if string(raw) != "[]" {
		t.Fatalf("data = %s, want []", raw)
	}
}

func TestListChangesModelNotFound(t *testing.T) {
	mux, _, _ := newChangesTestServer(t)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/v1/models/m_0000000000000000/changes", nil))
	if rec.Code != http.StatusNotFound {
		t.Fatalf("want 404, got %d", rec.Code)
	}
}
