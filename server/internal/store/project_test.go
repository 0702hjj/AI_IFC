// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package store

import (
	"strings"
	"testing"
)

// TestProjectCreateGetList 项目创建/读取/列表的基本契约（A1）。
func TestProjectCreateGetList(t *testing.T) {
	s := NewProjectStore(t.TempDir())
	p, err := s.Create("新项目")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(p.ID, "p_") || len(p.ID) != 18 {
		t.Fatalf("bad project id %q", p.ID)
	}
	if p.Title != "新项目" {
		t.Fatalf("title = %q", p.Title)
	}
	if len(p.Models) != 0 {
		t.Fatalf("new project should have no models, got %+v", p.Models)
	}
	got, err := s.Get(p.ID)
	if err != nil || got.ID != p.ID {
		t.Fatalf("get: %v %+v", err, got)
	}
	list, err := s.List()
	if err != nil || len(list) != 1 {
		t.Fatalf("list: %v %d", err, len(list))
	}
}

// TestProjectAddModel 项目下模型聚合（A1：单 kind 主模型 / 管线多模型）。
func TestProjectAddModel(t *testing.T) {
	s := NewProjectStore(t.TempDir())
	p, err := s.Create("管线项目")
	if err != nil {
		t.Fatal(err)
	}
	if err := s.AddModel(p.ID, "m_0000000000000001", "dxf", "plan.dxf", "ready"); err != nil {
		t.Fatal(err)
	}
	if err := s.AddModel(p.ID, "m_0000000000000002", "ifc", "bim.ifc", "converting"); err != nil {
		t.Fatal(err)
	}
	got, err := s.Get(p.ID)
	if err != nil {
		t.Fatal(err)
	}
	if len(got.Models) != 2 {
		t.Fatalf("models = %d, want 2", len(got.Models))
	}
	if got.Models[0].ID != "m_0000000000000001" || got.Models[0].Kind != "dxf" {
		t.Fatalf("model0 = %+v", got.Models[0])
	}
	// 同项目加模型幂等（同 modelId 不重复）
	if err := s.AddModel(p.ID, "m_0000000000000001", "dxf", "plan.dxf", "ready"); err != nil {
		t.Fatal(err)
	}
	got, _ = s.Get(p.ID)
	if len(got.Models) != 2 {
		t.Fatalf("dup add: models = %d, want 2", len(got.Models))
	}
}

// TestProjectNotFound 不存在项目返回 ErrNotFound（与 store.Model 同哨兵）。
func TestProjectNotFound(t *testing.T) {
	s := NewProjectStore(t.TempDir())
	if _, err := s.Get("p_0000000000000000"); err != ErrNotFound {
		t.Fatalf("err = %v, want ErrNotFound", err)
	}
	if _, err := s.Get("m_0000000000000000"); err != ErrInvalidID {
		t.Fatalf("err = %v, want ErrInvalidID", err)
	}
}
