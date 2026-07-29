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
