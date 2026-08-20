// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package store

import (
	"strings"
	"testing"
)

// TestPlanPutGet 方案级存储当前态读写（B1）。
func TestPlanPutGet(t *testing.T) {
	s := NewPlanStore(t.TempDir())
	pid := "p_0000000000000001"

	// 首次 PUT → v1
	v, err := s.Put(pid, "plan.json", []byte(`{"version":1,"project":"p_0000000000000001"}`))
	if err != nil {
		t.Fatal(err)
	}
	if v != "v1" {
		t.Fatalf("version = %q, want v1", v)
	}
	got, err := s.Get(pid, "plan.json")
	if err != nil || !strings.Contains(string(got), "p_0000000000000001") {
		t.Fatalf("get plan: %v %s", err, got)
	}
	// 当前文件落盘
	cur, err := s.Get(pid, "plan.json")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(cur), `"version":1`) {
		t.Fatalf("plan content = %s", cur)
	}
}

// TestPlanPutVersioning 方案级版本化：每次 PUT 归档历史 + 版本递增（P-1 裁决）。
func TestPlanPutVersioning(t *testing.T) {
	s := NewPlanStore(t.TempDir())
	pid := "p_0000000000000002"

	v1, _ := s.Put(pid, "plan.json", []byte(`{"project":"p_0000000000000002","rev":1}`))
	v2, _ := s.Put(pid, "plan.json", []byte(`{"project":"p_0000000000000002","rev":2}`))
	if v1 != "v1" || v2 != "v2" {
		t.Fatalf("versions = %q/%q, want v1/v2", v1, v2)
	}
	// 历史归档存在（旧当前态 rev:1 → v1；总状态 = history[v1] + current[v2]）
	hist, err := s.ListHistory(pid, "plan.json")
	if err != nil || len(hist) != 1 || hist[0] != "v1" {
		t.Fatalf("history = %v %v, want [v1]", hist, err)
	}
	// 当前态 = 最新
	cur, _ := s.Get(pid, "plan.json")
	if !strings.Contains(string(cur), `"rev":2`) {
		t.Fatalf("current = %s, want rev:2", cur)
	}
	// bim_supplement 独立版本链
	b1, _ := s.Put(pid, "bim_supplement.json", []byte(`{"project":"p_0000000000000002"}`))
	if b1 != "v1" {
		t.Fatalf("bim version = %q, want v1（独立链）", b1)
	}
}

// TestPlanPutInvalidName 白名单外 name 拒绝（领域收敛单点）。
func TestPlanPutInvalidName(t *testing.T) {
	s := NewPlanStore(t.TempDir())
	if _, err := s.Put("p_0000000000000001", "other.json", []byte(`{}`)); err != ErrInvalidKind {
		t.Fatalf("err = %v, want ErrInvalidKind", err)
	}
	if _, err := s.Get("p_0000000000000001", "other.json"); err != ErrInvalidKind {
		t.Fatalf("get err = %v, want ErrInvalidKind", err)
	}
}

// TestPlanGetNotFound 未落盘返回 ErrNotFound（与 Model/Project 同哨兵）。
func TestPlanGetNotFound(t *testing.T) {
	s := NewPlanStore(t.TempDir())
	if _, err := s.Get("p_0000000000000001", "plan.json"); err != ErrNotFound {
		t.Fatalf("err = %v, want ErrNotFound", err)
	}
	if _, err := s.ListHistory("p_0000000000000001", "plan.json"); err != nil {
		t.Fatalf("empty history err = %v, want nil", err)
	}
}

// TestPlanLoadHistory 读历史版本内容（diff 端点数据源）。
func TestPlanLoadHistory(t *testing.T) {
	s := NewPlanStore(t.TempDir())
	pid := "p_0000000000000003"
	s.Put(pid, "plan.json", []byte(`{"project":"p_0000000000000003","rev":1}`))
	s.Put(pid, "plan.json", []byte(`{"project":"p_0000000000000003","rev":2}`))
	// 历史 v1 = rev:1（旧当前态归档）
	v1, err := s.LoadHistory(pid, "plan.json", "v1")
	if err != nil || !strings.Contains(string(v1), `"rev":1`) {
		t.Fatalf("load v1: %v %s", err, v1)
	}
	// 不存在的版本 → ErrNotFound
	if _, err := s.LoadHistory(pid, "plan.json", "v9"); err != ErrNotFound {
		t.Fatalf("load v9 err = %v, want ErrNotFound", err)
	}
	// 当前态版本不是历史（v2 是 current，不在 history）
	if _, err := s.LoadHistory(pid, "plan.json", "v2"); err != ErrNotFound {
		t.Fatalf("load v2 (current) err = %v, want ErrNotFound", err)
	}
}

// TestJSONDiff 方案级 JSON 字段级 diff（新增/删除/修改/嵌套路径）。
func TestJSONDiff(t *testing.T) {
	base := `{"version":1,"project":"p_x","site":{"name":"A","area":100},"zones":[{"zone":"z1","floors":3},{"zone":"z2","floors":2}]}`
	target := `{"version":2,"project":"p_x","site":{"name":"A","area":120,"height":30},"zones":[{"zone":"z1","floors":4},{"zone":"z3","floors":1}]}`
	diff, err := JSONDiff([]byte(base), []byte(target))
	if err != nil {
		t.Fatal(err)
	}
	got := map[string]bool{}
	for _, d := range diff {
		got[d.Op+" "+d.Path] = true
	}
	want := map[string]bool{
		"modify version":         true,
		"modify site.area":       true,
		"add site.height":        true,
		"modify zones[0].floors": true,
		"modify zones[1].zone":   true, // z3 替换 z2（数组按索引比较 → modify 字段）
		"modify zones[1].floors": true,
	}
	for w := range want {
		if !got[w] {
			t.Fatalf("missing diff %q; got %v", w, got)
		}
	}
}
