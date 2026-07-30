package change

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
