package override

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func newTestFileStore(t *testing.T) (*FileStore, string) {
	t.Helper()
	dir := t.TempDir()
	modelID := "m_0123456789abcdef"
	if err := os.MkdirAll(filepath.Join(dir, "models", modelID), 0o755); err != nil {
		t.Fatal(err)
	}
	return NewFileStore(dir), modelID
}

func TestFileSetAndGetAll(t *testing.T) {
	fs, modelID := newTestFileStore(t)
	old, err := fs.Set(modelID, "e1", map[string]string{"Name": "Wall A", "FireRating": "F30"})
	if err != nil {
		t.Fatalf("set: %v", err)
	}
	if len(old) != 0 {
		t.Fatalf("old = %+v, want empty", old)
	}
	old, err = fs.Set(modelID, "e2", map[string]string{"Description": "d2"})
	if err != nil {
		t.Fatalf("set: %v", err)
	}
	all, err := fs.GetAll(modelID)
	if err != nil {
		t.Fatalf("getAll: %v", err)
	}
	if len(all) != 2 || all["e1"]["Name"] != "Wall A" || all["e1"]["FireRating"] != "F30" || all["e2"]["Description"] != "d2" {
		t.Fatalf("all = %+v", all)
	}
}

func TestFileSetReturnsOldValues(t *testing.T) {
	fs, modelID := newTestFileStore(t)
	if _, err := fs.Set(modelID, "e1", map[string]string{"Name": "X", "Comments": "c1"}); err != nil {
		t.Fatalf("set: %v", err)
	}
	old, err := fs.Set(modelID, "e1", map[string]string{"Name": "Y", "Description": "new"})
	if err != nil {
		t.Fatalf("set: %v", err)
	}
	if len(old) != 1 || old["Name"] != "X" {
		t.Fatalf("old = %+v, want {Name:X}", old)
	}
	if _, ok := old["Description"]; ok {
		t.Fatalf("old = %+v, Description key must be absent", old)
	}
}

func TestFileSetEmptyValueClears(t *testing.T) {
	fs, modelID := newTestFileStore(t)
	if _, err := fs.Set(modelID, "e1", map[string]string{"Name": "X", "Comments": "c1"}); err != nil {
		t.Fatalf("set: %v", err)
	}
	old, err := fs.Set(modelID, "e1", map[string]string{"Name": ""})
	if err != nil {
		t.Fatalf("set: %v", err)
	}
	if old["Name"] != "X" {
		t.Fatalf("old = %+v, want {Name:X}", old)
	}
	all, err := fs.GetAll(modelID)
	if err != nil {
		t.Fatalf("getAll: %v", err)
	}
	if _, ok := all["e1"]["Name"]; ok {
		t.Fatalf("all = %+v, Name must be cleared", all)
	}
	if all["e1"]["Comments"] != "c1" {
		t.Fatalf("all = %+v, Comments must survive", all)
	}
	// 清除最后一个字段后实体条目也应移除
	if _, err := fs.Set(modelID, "e1", map[string]string{"Comments": ""}); err != nil {
		t.Fatalf("set: %v", err)
	}
	all, err = fs.GetAll(modelID)
	if err != nil {
		t.Fatalf("getAll: %v", err)
	}
	if _, ok := all["e1"]; ok {
		t.Fatalf("all = %+v, e1 must be removed", all)
	}
}

func TestFileSetRejectsInvalidField(t *testing.T) {
	fs, modelID := newTestFileStore(t)
	_, err := fs.Set(modelID, "e1", map[string]string{"Height": "3000"})
	if !errors.Is(err, ErrInvalidField) {
		t.Fatalf("err = %v, want ErrInvalidField", err)
	}
	_, err = fs.Set(modelID, "e1", map[string]string{"Name": "ok", "GlobalId": "x"})
	if !errors.Is(err, ErrInvalidField) {
		t.Fatalf("err = %v, want ErrInvalidField", err)
	}
	all, err := fs.GetAll(modelID)
	if err != nil {
		t.Fatalf("getAll: %v", err)
	}
	if len(all) != 0 {
		t.Fatalf("all = %+v, rejected patch must not persist", all)
	}
}

func TestFileGetAllEmptyWhenNoFile(t *testing.T) {
	fs, modelID := newTestFileStore(t)
	all, err := fs.GetAll(modelID)
	if err != nil {
		t.Fatalf("getAll: %v", err)
	}
	if len(all) != 0 {
		t.Fatalf("all = %+v, want empty", all)
	}
}

func TestFileDeleteModel(t *testing.T) {
	fs, modelID := newTestFileStore(t)
	if _, err := fs.Set(modelID, "e1", map[string]string{"Name": "x"}); err != nil {
		t.Fatal(err)
	}
	if err := fs.DeleteModel(modelID); err != nil {
		t.Fatalf("deleteModel: %v", err)
	}
	if _, err := os.Stat(fs.overridesPath(modelID)); !errors.Is(err, os.ErrNotExist) {
		t.Fatal("overrides.json not removed")
	}
	if err := fs.DeleteModel(modelID); err != nil {
		t.Fatalf("second deleteModel err = %v, want nil", err)
	}
}
