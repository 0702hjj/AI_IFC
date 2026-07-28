package store

import (
	"strings"
	"testing"
)

func TestCreateGetListDelete(t *testing.T) {
	s := NewStore(t.TempDir())
	m, err := s.Create("a.ifc", 11, strings.NewReader("hello world"))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(m.ID, "m_") || len(m.ID) != 18 {
		t.Fatalf("bad id %q", m.ID)
	}
	if m.Status != "converting" {
		t.Fatalf("status = %q", m.Status)
	}
	got, err := s.Get(m.ID)
	if err != nil || got.Name != "a.ifc" {
		t.Fatalf("get: %v %+v", err, got)
	}
	if err := s.SetStatus(m.ID, "ready", ""); err != nil {
		t.Fatal(err)
	}
	list, err := s.List()
	if err != nil || len(list) != 1 || list[0].Status != "ready" {
		t.Fatalf("list: %v %+v", err, list)
	}
	if err := s.Delete(m.ID); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Get(m.ID); err != ErrNotFound {
		t.Fatalf("expected ErrNotFound, got %v", err)
	}
}

func TestRecoverMarksConvertingFailed(t *testing.T) {
	s := NewStore(t.TempDir())
	m, _ := s.Create("b.ifc", 3, strings.NewReader("abc"))
	if err := s.Recover(); err != nil {
		t.Fatal(err)
	}
	got, _ := s.Get(m.ID)
	if got.Status != "failed" || got.Error == "" {
		t.Fatalf("recover: %+v", got)
	}
}
