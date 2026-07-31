// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package issue

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"
)

func newTestPgStore(t *testing.T) (*PgStore, string) {
	t.Helper()
	dsn := os.Getenv("VIEWER_TEST_PG_DSN")
	if dsn == "" {
		t.Skip("VIEWER_TEST_PG_DSN not set")
	}
	pool, err := pgxpool.New(context.Background(), dsn)
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	t.Cleanup(pool.Close)
	dir := t.TempDir()
	modelID := "m_test_issue_pg01"
	t.Cleanup(func() {
		if _, err := pool.Exec(context.Background(), `DELETE FROM issues WHERE model_id = $1`, modelID); err != nil {
			t.Errorf("cleanup: %v", err)
		}
	})
	ps, err := NewPgStore(pool, dir)
	if err != nil {
		t.Fatalf("new pg store: %v", err)
	}
	return ps, modelID
}

func TestPgCreateAndList(t *testing.T) {
	ps, modelID := newTestPgStore(t)
	created, err := ps.Create(modelID, &Issue{
		EntityID: "3a82-xxxx", EntityName: "Wall", EntityType: "IfcWall",
		Title:   "pg issue",
		Comment: "check",
		Camera:  Camera{Eye: [3]float64{1, 2, 3}, Look: [3]float64{0, 0, 0}, Up: [3]float64{0, 0, 1}},
	})
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if created.ID == "" || len(created.ID) != 14 || created.ID[:2] != "i_" {
		t.Fatalf("bad id: %q", created.ID)
	}
	if created.Status != "open" || created.Author != "local-user" || created.Provenance.Source != "UI" {
		t.Fatalf("defaults: %+v", created)
	}
	if created.Screenshot != "" {
		t.Fatalf("screenshot = %q, want empty", created.Screenshot)
	}
	list, err := ps.List(modelID)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if len(list) != 1 || list[0].ID != created.ID || list[0].Title != "pg issue" {
		t.Fatalf("list = %+v", list)
	}
	if list[0].Author != "local-user" || list[0].Provenance.Source != "UI" {
		t.Fatalf("defaults not persisted: %+v", list[0])
	}
}

func TestPgCreateValidation(t *testing.T) {
	ps, modelID := newTestPgStore(t)
	if _, err := ps.Create(modelID, &Issue{Title: "  "}); !errors.Is(err, ErrEmptyTitle) {
		t.Fatalf("err = %v, want ErrEmptyTitle", err)
	}
	if _, err := ps.Create(modelID, &Issue{Title: "x", Status: "bogus"}); !errors.Is(err, ErrInvalidStatus) {
		t.Fatalf("err = %v, want ErrInvalidStatus", err)
	}
}

func TestPgListSortedDesc(t *testing.T) {
	ps, modelID := newTestPgStore(t)
	first, err := ps.Create(modelID, &Issue{Title: "first"})
	if err != nil {
		t.Fatal(err)
	}
	second, err := ps.Create(modelID, &Issue{Title: "second", Author: "ai-bot", Provenance: Provenance{Source: "AI"}})
	if err != nil {
		t.Fatal(err)
	}
	list, err := ps.List(modelID)
	if err != nil {
		t.Fatal(err)
	}
	if len(list) != 2 || list[0].ID != second.ID || list[1].ID != first.ID {
		t.Fatalf("list = %+v", list)
	}
	if list[0].Author != "ai-bot" || list[0].Provenance.Source != "AI" {
		t.Fatalf("explicit values overwritten: %+v", list[0])
	}
}

func TestPgUpdate(t *testing.T) {
	ps, modelID := newTestPgStore(t)
	created, err := ps.Create(modelID, &Issue{Title: "old"})
	if err != nil {
		t.Fatal(err)
	}
	status, title := "resolved", "new title"
	got, err := ps.Update(modelID, created.ID, IssuePatch{Title: &title, Status: &status})
	if err != nil {
		t.Fatalf("update: %v", err)
	}
	if got.Title != "new title" || got.Status != "resolved" {
		t.Fatalf("got %+v", got)
	}
	list, _ := ps.List(modelID)
	if list[0].Title != "new title" {
		t.Fatal("update not persisted")
	}
	status = "checking"
	if _, err := ps.Update(modelID, "i_abcdef012345", IssuePatch{Status: &status}); !errors.Is(err, ErrNotFound) {
		t.Fatalf("err = %v, want ErrNotFound", err)
	}
	if _, err := ps.Update(modelID, "bad id", IssuePatch{Status: &status}); !errors.Is(err, ErrInvalidID) {
		t.Fatalf("err = %v, want ErrInvalidID", err)
	}
	bogus := "bogus"
	if _, err := ps.Update(modelID, created.ID, IssuePatch{Status: &bogus}); !errors.Is(err, ErrInvalidStatus) {
		t.Fatalf("err = %v, want ErrInvalidStatus", err)
	}
}

func TestPgDelete(t *testing.T) {
	ps, modelID := newTestPgStore(t)
	created, err := ps.Create(modelID, &Issue{Title: "x"})
	if err != nil {
		t.Fatal(err)
	}
	if err := ps.Delete(modelID, created.ID); err != nil {
		t.Fatalf("delete: %v", err)
	}
	list, _ := ps.List(modelID)
	if len(list) != 0 {
		t.Fatalf("list = %+v, want empty", list)
	}
	if err := ps.Delete(modelID, created.ID); !errors.Is(err, ErrNotFound) {
		t.Fatalf("second delete err = %v, want ErrNotFound", err)
	}
}

func TestPgSaveScreenshot(t *testing.T) {
	ps, modelID := newTestPgStore(t)
	created, err := ps.Create(modelID, &Issue{Title: "x"})
	if err != nil {
		t.Fatal(err)
	}
	rel, err := ps.SaveScreenshot(modelID, created.ID, []byte("fakepng"))
	if err != nil {
		t.Fatalf("save: %v", err)
	}
	want := "issues/" + created.ID + ".png"
	if rel != want {
		t.Fatalf("rel = %q, want %q", rel, want)
	}
	data, err := os.ReadFile(filepath.Join(ps.DataDir, "models", modelID, want))
	if err != nil || string(data) != "fakepng" {
		t.Fatalf("file: %v %q", err, data)
	}
	list, _ := ps.List(modelID)
	if list[0].Screenshot != want {
		t.Fatalf("record screenshot = %q", list[0].Screenshot)
	}
}

func TestPgDeleteModel(t *testing.T) {
	ps, modelID := newTestPgStore(t)
	if _, err := ps.Create(modelID, &Issue{Title: "a"}); err != nil {
		t.Fatal(err)
	}
	if _, err := ps.Create(modelID, &Issue{Title: "b"}); err != nil {
		t.Fatal(err)
	}
	if err := ps.DeleteModel(modelID); err != nil {
		t.Fatalf("deleteModel: %v", err)
	}
	list, err := ps.List(modelID)
	if err != nil {
		t.Fatal(err)
	}
	if len(list) != 0 {
		t.Fatalf("list = %+v, want empty", list)
	}
	if err := ps.DeleteModel(modelID); err != nil {
		t.Fatalf("second deleteModel err = %v, want nil", err)
	}
}
