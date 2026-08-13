// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package store

import (
	"os"
	"path/filepath"
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

func TestInvalidIDRejected(t *testing.T) {
	dir := t.TempDir()
	s := NewStore(dir)
	outside := filepath.Join(dir, "..", "escaped_marker")
	badIDs := []string{"../../etc", "m_bad", "m_", "", "..", "m_0123456789abcdefg", "m_0123456789abcdeg"}
	for _, id := range badIDs {
		if _, err := s.Get(id); err == nil {
			t.Fatalf("Get(%q) expected error", id)
		}
		if err := s.SetStatus(id, "ready", ""); err == nil {
			t.Fatalf("SetStatus(%q) expected error", id)
		}
		if err := s.Delete(id); err == nil {
			t.Fatalf("Delete(%q) expected error", id)
		}
	}
	if _, err := os.Stat(outside); !os.IsNotExist(err) {
		t.Fatalf("file outside DataDir touched: %v", err)
	}
	evilDir := filepath.Join(dir, "evil")
	if err := os.MkdirAll(evilDir, 0o755); err != nil {
		t.Fatal(err)
	}
	evilJSON := filepath.Join(evilDir, "model.json")
	if err := os.WriteFile(evilJSON, []byte(`{"id":"x","name":"evil","status":"ready"}`), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Get("../evil"); err == nil {
		t.Fatal("Get traversal read file outside DataDir")
	}
	if err := s.SetStatus("../evil", "failed", "x"); err == nil {
		t.Fatal("SetStatus traversal wrote file outside DataDir")
	}
	if err := s.Delete("../evil"); err == nil {
		t.Fatal("Delete traversal removed dir outside DataDir")
	}
	data, err := os.ReadFile(evilJSON)
	if err != nil || !strings.Contains(string(data), `"status":"ready"`) {
		t.Fatalf("outside file modified: %v %q", err, data)
	}
	if _, err := s.Get("m_0123456789abcdef"); err != ErrNotFound {
		t.Fatalf("well-formed missing id: expected ErrNotFound, got %v", err)
	}
}
