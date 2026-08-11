// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package change

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"testing"
)

func TestValidSource(t *testing.T) {
	for _, s := range []string{"UI", "AI", "USER"} {
		if !ValidSource(s) {
			t.Fatalf("ValidSource(%q) = false, want true", s)
		}
	}
	for _, s := range []string{"", "ui", "ai", "system", "MIGRATION"} {
		if ValidSource(s) {
			t.Fatalf("ValidSource(%q) = true, want false", s)
		}
	}
}

func TestAppendListOperationDiffRoundtrip(t *testing.T) {
	fs, modelID := newTestStore(t)
	diff := json.RawMessage(`{"fields":[{"field":"width","old":"100","new":"200"}]}`)
	e := &Entry{
		EntityID: "e1", EntityName: "Wall", Field: "width",
		OldValue: "100", NewValue: "200",
		Author: "ai-bot", Provenance: Provenance{Source: "USER", Origin: "upload"},
		Operation: "migrate", Diff: diff,
	}
	if err := fs.Append(modelID, e); err != nil {
		t.Fatalf("append: %v", err)
	}
	legacy := &Entry{EntityID: "e1", Field: "height", OldValue: "3000", NewValue: "3200"}
	if err := fs.Append(modelID, legacy); err != nil {
		t.Fatalf("append: %v", err)
	}
	list, err := fs.List(modelID)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if len(list) != 2 {
		t.Fatalf("list = %+v", list)
	}
	byOp := map[string]*Entry{}
	for _, got := range list {
		byOp[got.ID] = got
	}
	gotMigrate := byOp[e.ID]
	if gotMigrate == nil || gotMigrate.Operation != "migrate" {
		t.Fatalf("entry = %+v, want operation migrate", gotMigrate)
	}
	if gotMigrate.Provenance.Source != "USER" || gotMigrate.Provenance.Origin != "upload" {
		t.Fatalf("provenance = %+v, want USER/upload", gotMigrate.Provenance)
	}
	var gotDiff, wantDiff interface{}
	if err := json.Unmarshal(gotMigrate.Diff, &gotDiff); err != nil {
		t.Fatalf("diff not valid json: %v", err)
	}
	if err := json.Unmarshal(diff, &wantDiff); err != nil {
		t.Fatal(err)
	}
	if fmt.Sprintf("%v", gotDiff) != fmt.Sprintf("%v", wantDiff) {
		t.Fatalf("diff = %v, want %v", gotDiff, wantDiff)
	}
	gotLegacy := byOp[legacy.ID]
	if gotLegacy == nil || gotLegacy.Operation != "update" {
		t.Fatalf("entry = %+v, empty operation must normalize to update", gotLegacy)
	}
	if gotLegacy.Diff != nil {
		t.Fatalf("diff = %s, want nil", gotLegacy.Diff)
	}
	if legacy.Operation != "update" {
		t.Fatalf("Append must normalize empty operation in place, got %q", legacy.Operation)
	}
}

func TestListNormalizesLegacyChangesJSON(t *testing.T) {
	fs, modelID := newTestStore(t)
	legacy := []map[string]interface{}{
		{
			"id": "c_aaaaaaaaaaaa", "entityId": "e1", "entityName": "Wall",
			"field": "width", "oldValue": "100", "newValue": "200",
			"author": "local-user", "provenance": map[string]string{"source": "UI"},
			"createdAt": "2025-01-01T00:00:00Z",
		},
	}
	data, err := json.Marshal(legacy)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(fs.changesPath(modelID), data, 0o644); err != nil {
		t.Fatal(err)
	}
	list, err := fs.List(modelID)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if len(list) != 1 {
		t.Fatalf("list = %+v", list)
	}
	if list[0].Operation != "update" {
		t.Fatalf("operation = %q, want update", list[0].Operation)
	}
	if list[0].Diff != nil {
		t.Fatalf("diff = %s, want nil", list[0].Diff)
	}
}

func newTestStore(t *testing.T) (*FileStore, string) {
	t.Helper()
	dir := t.TempDir()
	modelID := "m_0123456789abcdef"
	if err := os.MkdirAll(filepath.Join(dir, "models", modelID), 0o755); err != nil {
		t.Fatal(err)
	}
	return NewFileStore(dir), modelID
}

func TestAppendAndList(t *testing.T) {
	fs, modelID := newTestStore(t)
	e := &Entry{
		EntityID: "e1", EntityName: "Wall", Field: "width",
		OldValue: "100", NewValue: "200",
		Author: "local-user", Provenance: Provenance{Source: "UI"},
	}
	if err := fs.Append(modelID, e); err != nil {
		t.Fatalf("append: %v", err)
	}
	if e.ID == "" || len(e.ID) != 14 || e.ID[:2] != "c_" {
		t.Fatalf("bad id: %q", e.ID)
	}
	if e.CreatedAt.IsZero() {
		t.Fatal("createdAt not set")
	}
	e2 := &Entry{EntityID: "e1", Field: "height", OldValue: "3000", NewValue: "3200"}
	if err := fs.Append(modelID, e2); err != nil {
		t.Fatalf("append: %v", err)
	}
	list, err := fs.List(modelID)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if len(list) != 2 {
		t.Fatalf("list = %+v", list)
	}
	if list[0].ID != e2.ID || list[1].ID != e.ID {
		t.Fatalf("list order = [%s %s], want [%s %s]", list[0].ID, list[1].ID, e2.ID, e.ID)
	}
	if list[1].Field != "width" || list[1].OldValue != "100" || list[1].NewValue != "200" || list[1].Author != "local-user" {
		t.Fatalf("entry = %+v", list[1])
	}
}

func TestAppendBatch(t *testing.T) {
	fs, modelID := newTestStore(t)
	a := &Entry{EntityID: "e1", Field: "a", OldValue: "1", NewValue: "2"}
	b := &Entry{EntityID: "e1", Field: "b", OldValue: "3", NewValue: "4"}
	if err := fs.Append(modelID, a, b); err != nil {
		t.Fatalf("append: %v", err)
	}
	list, _ := fs.List(modelID)
	if len(list) != 2 {
		t.Fatalf("list = %+v", list)
	}
}

func TestListEmptyWhenNoFile(t *testing.T) {
	fs, modelID := newTestStore(t)
	list, err := fs.List(modelID)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if len(list) != 0 {
		t.Fatalf("list = %+v, want empty", list)
	}
}

func TestFileDeleteModel(t *testing.T) {
	fs, modelID := newTestStore(t)
	if err := fs.Append(modelID, &Entry{EntityID: "e1", Field: "Name", NewValue: "x"}); err != nil {
		t.Fatal(err)
	}
	if err := fs.DeleteModel(modelID); err != nil {
		t.Fatalf("deleteModel: %v", err)
	}
	if _, err := os.Stat(fs.changesPath(modelID)); !errors.Is(err, os.ErrNotExist) {
		t.Fatal("changes.json not removed")
	}
	if err := fs.DeleteModel(modelID); err != nil {
		t.Fatalf("second deleteModel err = %v, want nil", err)
	}
}
