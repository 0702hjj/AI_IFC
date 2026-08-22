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

// TestModelProjectIDBacklink：模型反向归属——CreateWithKindInProject 写入 Model.ProjectID。
func TestModelProjectIDBacklink(t *testing.T) {
	dir := t.TempDir()
	st := NewStore(dir)
	ps := NewProjectStore(dir)
	p, err := ps.CreateWithKind("p1", "ifc")
	if err != nil {
		t.Fatal(err)
	}
	m, err := st.CreateWithKindInProject("model1", 0, strings.NewReader(""), KindIFC, p.ID)
	if err != nil {
		t.Fatalf("CreateWithKindInProject: %v", err)
	}
	got, err := st.Get(m.ID)
	if err != nil {
		t.Fatal(err)
	}
	if got.ProjectID != p.ID {
		t.Fatalf("model.ProjectID = %q, want %q（反向归属）", got.ProjectID, p.ID)
	}
}

// TestProjectRemoveModel：RemoveModel 从项目摘除 modelId（幂等；未挂模型幂等空操作）。
func TestProjectRemoveModel(t *testing.T) {
	s := NewProjectStore(t.TempDir())
	p, err := s.CreateWithKind("p1", "cad")
	if err != nil {
		t.Fatal(err)
	}
	if err := s.AddModel(p.ID, "m_1", KindDXF, "图", "ready"); err != nil {
		t.Fatal(err)
	}
	if err := s.RemoveModel(p.ID, "m_1"); err != nil {
		t.Fatalf("RemoveModel: %v", err)
	}
	got, _ := s.Get(p.ID)
	if len(got.Models) != 0 {
		t.Fatalf("RemoveModel 后项目 Models = %v, want 空", got.Models)
	}
	// 幂等：再删一次不报错
	if err := s.RemoveModel(p.ID, "m_1"); err != nil {
		t.Fatalf("RemoveModel 幂等: %v", err)
	}
	// 项目不存在 → 报错
	if err := s.RemoveModel("p_missing", "m_1"); err == nil {
		t.Fatal("RemoveModel 项目不存在应报错")
	}
}
