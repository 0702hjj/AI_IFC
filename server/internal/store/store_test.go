// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package store

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
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

// kind 判定归 domain（W-0040）：扩展名白名单 .ifc/.dxf，其余 ErrUnsupportedExt。
func TestKindForFilename(t *testing.T) {
	for _, c := range []struct{ name, want string }{
		{"a.ifc", KindIFC},
		{"A.IFC", KindIFC},
		{"b.dxf", KindDXF},
		{"B.DXF", KindDXF},
		{"平面 图.dxf", KindDXF},
	} {
		got, err := KindForFilename(c.name)
		if err != nil || got != c.want {
			t.Fatalf("KindForFilename(%q) = %q, %v; want %q", c.name, got, err, c.want)
		}
	}
	for _, bad := range []string{"a.txt", "noext", "a.ifc.txt", "a.step"} {
		if _, err := KindForFilename(bad); !errors.Is(err, ErrUnsupportedExt) {
			t.Fatalf("KindForFilename(%q): err = %v, want ErrUnsupportedExt", bad, err)
		}
	}
}

// Create 缺省 kind=ifc：状态 converting（进转换队列），文件落 uploads/{id}.ifc。
func TestCreateDefaultsKindIFC(t *testing.T) {
	s := NewStore(t.TempDir())
	m, err := s.Create("a.ifc", 4, strings.NewReader("fake"))
	if err != nil {
		t.Fatal(err)
	}
	if m.Kind != KindIFC {
		t.Fatalf("kind = %q, want %q", m.Kind, KindIFC)
	}
	if m.Status != "converting" {
		t.Fatalf("status = %q, want converting", m.Status)
	}
	got, err := s.Get(m.ID)
	if err != nil || got.Kind != KindIFC {
		t.Fatalf("persisted kind = %q, %v", got.Kind, err)
	}
}

// dxf kind：无 XKT 转换，创建即 ready；文件落 uploads/{id}.dxf（W-0040）。
func TestCreateWithKindDXF(t *testing.T) {
	s := NewStore(t.TempDir())
	m, err := s.CreateWithKind("b.dxf", 4, strings.NewReader("fake"), KindDXF)
	if err != nil {
		t.Fatal(err)
	}
	if m.Kind != KindDXF {
		t.Fatalf("kind = %q, want %q", m.Kind, KindDXF)
	}
	if m.Status != "ready" {
		t.Fatalf("status = %q, want ready（dxf 不进转换队列）", m.Status)
	}
	data, err := os.ReadFile(s.DXFPath(m.ID))
	if err != nil || string(data) != "fake" {
		t.Fatalf("dxf upload: %v %q", err, data)
	}
	if _, err := os.Stat(s.IFCPath(m.ID)); !os.IsNotExist(err) {
		t.Fatalf("dxf 模型不应有 .ifc 上传文件: %v", err)
	}
	got, err := s.Get(m.ID)
	if err != nil || got.Kind != KindDXF || got.Status != "ready" {
		t.Fatalf("persisted: %+v, %v", got, err)
	}
}

func TestCreateWithKindRejectsInvalid(t *testing.T) {
	s := NewStore(t.TempDir())
	if _, err := s.CreateWithKind("x.ifc", 1, strings.NewReader("x"), "step"); !errors.Is(err, ErrInvalidKind) {
		t.Fatalf("err = %v, want ErrInvalidKind", err)
	}
}

// 存量迁移：无 kind 字段的旧 model.json Get 后按 ifc 处理（不破坏现有模型）。
func TestGetMigratesMissingKindToIFC(t *testing.T) {
	s := NewStore(t.TempDir())
	m, err := s.Create("a.ifc", 4, strings.NewReader("fake"))
	if err != nil {
		t.Fatal(err)
	}
	legacy := fmt.Sprintf(`{"id":%q,"name":"a.ifc","size":4,"status":"ready","createdAt":%q,"error":""}`,
		m.ID, m.CreatedAt.UTC().Format(time.RFC3339Nano))
	if err := os.WriteFile(filepath.Join(s.ModelDir(m.ID), "model.json"), []byte(legacy), 0o644); err != nil {
		t.Fatal(err)
	}
	got, err := s.Get(m.ID)
	if err != nil {
		t.Fatal(err)
	}
	if got.Kind != KindIFC {
		t.Fatalf("migrated kind = %q, want %q", got.Kind, KindIFC)
	}
}

func TestSourcePathByKind(t *testing.T) {
	s := NewStore(t.TempDir())
	id := "m_0123456789abcdef"
	if got := s.SourcePath(&Model{ID: id, Kind: KindDXF}); got != s.DXFPath(id) {
		t.Fatalf("dxf SourcePath = %q, want %q", got, s.DXFPath(id))
	}
	if got := s.SourcePath(&Model{ID: id, Kind: KindIFC}); got != s.IFCPath(id) {
		t.Fatalf("ifc SourcePath = %q, want %q", got, s.IFCPath(id))
	}
	// 迁移口径：空 kind 视同 ifc。
	if got := s.SourcePath(&Model{ID: id}); got != s.IFCPath(id) {
		t.Fatalf("empty-kind SourcePath = %q, want %q", got, s.IFCPath(id))
	}
}

func TestDeleteRemovesDXFUpload(t *testing.T) {
	s := NewStore(t.TempDir())
	m, err := s.CreateWithKind("b.dxf", 4, strings.NewReader("fake"), KindDXF)
	if err != nil {
		t.Fatal(err)
	}
	if err := s.Delete(m.ID); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(s.DXFPath(m.ID)); !os.IsNotExist(err) {
		t.Fatalf("dxf upload not removed: %v", err)
	}
	if _, err := s.Get(m.ID); err != ErrNotFound {
		t.Fatalf("expected ErrNotFound, got %v", err)
	}
}
