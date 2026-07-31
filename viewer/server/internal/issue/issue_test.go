// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package issue

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func newTestStore(t *testing.T) (*FileStore, string) {
	t.Helper()
	dir := t.TempDir()
	modelID := "m_0123456789abcdef"
	if err := os.MkdirAll(filepath.Join(dir, "models", modelID), 0o755); err != nil {
		t.Fatal(err)
	}
	return NewFileStore(dir), modelID
}

func TestCreateAndList(t *testing.T) {
	fs, modelID := newTestStore(t)
	created, err := fs.Create(modelID, &Issue{
		EntityID: "3a82-xxxx", EntityName: "Wall", EntityType: "IfcWall",
		Title:   "Door width incorrect",
		Comment: "check",
		Camera:  Camera{Eye: [3]float64{1, 2, 3}, Look: [3]float64{0, 0, 0}, Up: [3]float64{0, 0, 1}},
	})
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if created.ID == "" || len(created.ID) != 14 || created.ID[:2] != "i_" {
		t.Fatalf("bad id: %q", created.ID)
	}
	if created.Status != "open" {
		t.Fatalf("default status = %q, want open", created.Status)
	}
	if created.CreatedAt.IsZero() || created.UpdatedAt.IsZero() {
		t.Fatal("timestamps not set")
	}
	list, err := fs.List(modelID)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if len(list) != 1 || list[0].ID != created.ID {
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

func TestCreateDefaultAuthorAndProvenance(t *testing.T) {
	fs, modelID := newTestStore(t)
	created, err := fs.Create(modelID, &Issue{Title: "x"})
	if err != nil {
		t.Fatal(err)
	}
	if created.Author != "local-user" {
		t.Fatalf("default author = %q, want local-user", created.Author)
	}
	if created.Provenance.Source != "UI" {
		t.Fatalf("default provenance.source = %q, want UI", created.Provenance.Source)
	}
	list, _ := fs.List(modelID)
	if list[0].Author != "local-user" || list[0].Provenance.Source != "UI" {
		t.Fatalf("defaults not persisted: %+v", list[0])
	}
}

func TestCreateExplicitAuthorAndProvenance(t *testing.T) {
	fs, modelID := newTestStore(t)
	created, err := fs.Create(modelID, &Issue{Title: "x", Author: "ai-bot", Provenance: Provenance{Source: "AI"}})
	if err != nil {
		t.Fatal(err)
	}
	if created.Author != "ai-bot" || created.Provenance.Source != "AI" {
		t.Fatalf("explicit values overwritten: %+v", created)
	}
}

func TestCreateEmptyTitle(t *testing.T) {
	fs, modelID := newTestStore(t)
	if _, err := fs.Create(modelID, &Issue{Title: "  "}); !errors.Is(err, ErrEmptyTitle) {
		t.Fatalf("err = %v, want ErrEmptyTitle", err)
	}
}

func TestCreateInvalidStatus(t *testing.T) {
	fs, modelID := newTestStore(t)
	if _, err := fs.Create(modelID, &Issue{Title: "x", Status: "bogus"}); !errors.Is(err, ErrInvalidStatus) {
		t.Fatalf("err = %v, want ErrInvalidStatus", err)
	}
}

func TestListSortedByCreatedAtDesc(t *testing.T) {
	fs, modelID := newTestStore(t)
	first, err := fs.Create(modelID, &Issue{Title: "first"})
	if err != nil {
		t.Fatal(err)
	}
	second, err := fs.Create(modelID, &Issue{Title: "second"})
	if err != nil {
		t.Fatal(err)
	}
	list, err := fs.List(modelID)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if len(list) != 2 {
		t.Fatalf("list = %+v", list)
	}
	if list[0].ID != second.ID || list[1].ID != first.ID {
		t.Fatalf("list order = [%s %s], want [%s %s]", list[0].ID, list[1].ID, second.ID, first.ID)
	}
}

func TestUpdate(t *testing.T) {
	fs, modelID := newTestStore(t)
	created, err := fs.Create(modelID, &Issue{Title: "old"})
	if err != nil {
		t.Fatal(err)
	}
	status, title := "resolved", "new title"
	got, err := fs.Update(modelID, created.ID, IssuePatch{Title: &title, Status: &status})
	if err != nil {
		t.Fatalf("update: %v", err)
	}
	if got.Title != "new title" || got.Status != "resolved" {
		t.Fatalf("got %+v", got)
	}
	if !got.UpdatedAt.After(created.CreatedAt) && !got.UpdatedAt.Equal(created.CreatedAt) {
		t.Fatal("updatedAt not refreshed")
	}
	list, _ := fs.List(modelID)
	if list[0].Title != "new title" {
		t.Fatal("update not persisted")
	}
}

func TestUpdateNotFound(t *testing.T) {
	fs, modelID := newTestStore(t)
	status := "resolved"
	if _, err := fs.Update(modelID, "i_abcdef012345", IssuePatch{Status: &status}); !errors.Is(err, ErrNotFound) {
		t.Fatalf("err = %v, want ErrNotFound", err)
	}
}

func TestUpdateInvalidID(t *testing.T) {
	fs, modelID := newTestStore(t)
	status := "resolved"
	if _, err := fs.Update(modelID, "bad id", IssuePatch{Status: &status}); !errors.Is(err, ErrInvalidID) {
		t.Fatalf("err = %v, want ErrInvalidID", err)
	}
}

func TestUpdateInvalidStatus(t *testing.T) {
	fs, modelID := newTestStore(t)
	created, _ := fs.Create(modelID, &Issue{Title: "x"})
	status := "bogus"
	if _, err := fs.Update(modelID, created.ID, IssuePatch{Status: &status}); !errors.Is(err, ErrInvalidStatus) {
		t.Fatalf("err = %v, want ErrInvalidStatus", err)
	}
}

func TestDelete(t *testing.T) {
	fs, modelID := newTestStore(t)
	created, _ := fs.Create(modelID, &Issue{Title: "x"})
	if _, err := fs.SaveScreenshot(modelID, created.ID, []byte("fakepng")); err != nil {
		t.Fatal(err)
	}
	if err := fs.Delete(modelID, created.ID); err != nil {
		t.Fatalf("delete: %v", err)
	}
	list, _ := fs.List(modelID)
	if len(list) != 0 {
		t.Fatalf("list = %+v, want empty", list)
	}
	if _, err := os.Stat(filepath.Join(fs.issuesDir(modelID), created.ID+".png")); !errors.Is(err, os.ErrNotExist) {
		t.Fatal("screenshot file not removed")
	}
	if err := fs.Delete(modelID, created.ID); !errors.Is(err, ErrNotFound) {
		t.Fatalf("second delete err = %v, want ErrNotFound", err)
	}
}

func TestSaveScreenshot(t *testing.T) {
	fs, modelID := newTestStore(t)
	created, _ := fs.Create(modelID, &Issue{Title: "x"})
	rel, err := fs.SaveScreenshot(modelID, created.ID, []byte("fakepng"))
	if err != nil {
		t.Fatalf("save: %v", err)
	}
	want := "issues/" + created.ID + ".png"
	if rel != want {
		t.Fatalf("rel = %q, want %q", rel, want)
	}
	data, err := os.ReadFile(filepath.Join(fs.DataDir, "models", modelID, want))
	if err != nil || string(data) != "fakepng" {
		t.Fatalf("file: %v %q", err, data)
	}
	list, _ := fs.List(modelID)
	if list[0].Screenshot != want {
		t.Fatalf("record screenshot = %q", list[0].Screenshot)
	}
}

func TestFileDeleteModel(t *testing.T) {
	fs, modelID := newTestStore(t)
	created, err := fs.Create(modelID, &Issue{Title: "x"})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := fs.SaveScreenshot(modelID, created.ID, []byte("fakepng")); err != nil {
		t.Fatal(err)
	}
	if err := fs.DeleteModel(modelID); err != nil {
		t.Fatalf("deleteModel: %v", err)
	}
	if _, err := os.Stat(fs.issuesPath(modelID)); !errors.Is(err, os.ErrNotExist) {
		t.Fatal("issues.json not removed")
	}
	if _, err := os.Stat(fs.issuesDir(modelID)); !errors.Is(err, os.ErrNotExist) {
		t.Fatal("issues/ dir not removed")
	}
	if err := fs.DeleteModel(modelID); err != nil {
		t.Fatalf("second deleteModel err = %v, want nil", err)
	}
}
