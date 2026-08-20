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
