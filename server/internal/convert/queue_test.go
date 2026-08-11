// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package convert

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"ifcviewer/server/internal/store"
)

type fakeRunner struct{ fail bool }

func (f fakeRunner) Run(ctx context.Context, in, out string) error {
	if f.fail {
		return errors.New("boom: node exited 1")
	}
	return nil
}

type blockingRunner struct {
	started chan struct{}
	release chan struct{}
}

func newBlockingRunner() *blockingRunner {
	return &blockingRunner{started: make(chan struct{}, 4), release: make(chan struct{})}
}

func (b *blockingRunner) Run(ctx context.Context, in, out string) error {
	b.started <- struct{}{}
	<-b.release
	return nil
}

type countingRunner struct {
	mu   sync.Mutex
	runs int
}

func (c *countingRunner) Run(ctx context.Context, in, out string) error {
	c.mu.Lock()
	c.runs++
	c.mu.Unlock()
	return nil
}

func (c *countingRunner) count() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.runs
}

type ctxAwareRunner struct {
	started chan struct{}
}

func (c *ctxAwareRunner) Run(ctx context.Context, in, out string) error {
	close(c.started)
	<-ctx.Done()
	return ctx.Err()
}

func waitStatus(t *testing.T, st *store.Store, id, want string) {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		m, err := st.Get(id)
		if err == nil && m.Status == want {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	m, _ := st.Get(id)
	t.Fatalf("status never became %q (now %q)", want, m.Status)
}

func TestQueueSuccessAndFailure(t *testing.T) {
	st := store.NewStore(t.TempDir())
	ok, _ := st.Create("ok.ifc", 1, strings.NewReader("x"))
	bad, _ := st.Create("bad.ifc", 1, strings.NewReader("x"))

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	q := NewQueue(st, fakeRunner{}, 2)
	q.Start(ctx)
	if !q.Enqueue(ok.ID) {
		t.Fatal("enqueue ok failed")
	}
	waitStatus(t, st, ok.ID, "ready")

	q2 := NewQueue(st, fakeRunner{fail: true}, 1)
	q2.Start(ctx)
	q2.Enqueue(bad.ID)
	waitStatus(t, st, bad.ID, "failed")
	m, _ := st.Get(bad.ID)
	if m.Error == "" {
		t.Fatal("expected error message recorded")
	}
}

func TestEnqueueWhileRunningReruns(t *testing.T) {
	st := store.NewStore(t.TempDir())
	m, _ := st.Create("dup.ifc", 1, strings.NewReader("x"))

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	br := newBlockingRunner()
	q := NewQueue(st, br, 1)
	q.Start(ctx)
	if !q.Enqueue(m.ID) {
		t.Fatal("first enqueue failed")
	}
	<-br.started
	if q.Enqueue(m.ID) {
		t.Fatal("duplicate enqueue while running should return false")
	}
	close(br.release)
	<-br.started // dirty：同一 id 重跑一次
	waitStatus(t, st, m.ID, "ready")
	select {
	case <-br.started:
		t.Fatal("unexpected third run")
	case <-time.After(100 * time.Millisecond):
	}
}

func TestEnqueueNoDirtyRunsOnce(t *testing.T) {
	st := store.NewStore(t.TempDir())
	m, _ := st.Create("once.ifc", 1, strings.NewReader("x"))

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	cr := &countingRunner{}
	q := NewQueue(st, cr, 1)
	q.Start(ctx)
	if !q.Enqueue(m.ID) {
		t.Fatal("enqueue failed")
	}
	waitStatus(t, st, m.ID, "ready")
	time.Sleep(100 * time.Millisecond)
	if n := cr.count(); n != 1 {
		t.Fatalf("runs = %d, want exactly 1", n)
	}
}

func TestEnqueueAfterClose(t *testing.T) {
	st := store.NewStore(t.TempDir())
	m, _ := st.Create("late.ifc", 1, strings.NewReader("x"))

	ctx, cancel := context.WithCancel(context.Background())
	q := NewQueue(st, fakeRunner{}, 1)
	q.Start(ctx)
	cancel()
	time.Sleep(100 * time.Millisecond)
	if q.Enqueue(m.ID) {
		t.Fatal("enqueue on closed queue should return false")
	}
}

func TestShutdownCancelsInflightJob(t *testing.T) {
	st := store.NewStore(t.TempDir())
	m, _ := st.Create("slow.ifc", 1, strings.NewReader("x"))

	ctx, cancel := context.WithCancel(context.Background())
	cr := &ctxAwareRunner{started: make(chan struct{})}
	q := NewQueue(st, cr, 1)
	q.Start(ctx)
	if !q.Enqueue(m.ID) {
		t.Fatal("enqueue failed")
	}
	<-cr.started
	cancel()
	waitStatus(t, st, m.ID, "failed")
	got, _ := st.Get(m.ID)
	if got.Error == "" {
		t.Fatal("expected cancellation error recorded")
	}
}

// waitRuns 条件等待 runner 执行次数达标（异步写盘不得固定 sleep，教训 2026-08-06）。
func waitRuns(t *testing.T, cr *countingRunner, want int) {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if cr.count() >= want {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("runs = %d, want >= %d", cr.count(), want)
}

// writeXKT 在 models/{id}/ 下写 model.xkt 并把 mtime 设为 t。
func writeXKT(t *testing.T, st *store.Store, id string, mt time.Time) {
	t.Helper()
	xkt := filepath.Join(st.ModelDir(id), "model.xkt")
	if err := os.WriteFile(xkt, []byte("xkt"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.Chtimes(xkt, mt, mt); err != nil {
		t.Fatal(err)
	}
}

// TestEnqueueIfStale 断言同源去重：IFC mtime 不新于 XKT → 跳过（false、不入队）；
// IFC 更新（mtime 新于 XKT）→ 重转（true、入队）。
func TestEnqueueIfStale(t *testing.T) {
	st := store.NewStore(t.TempDir())
	m, _ := st.Create("stale.ifc", 1, strings.NewReader("x"))

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	cr := &countingRunner{}
	q := NewQueue(st, cr, 1)
	q.Start(ctx)

	base := time.Now()
	if err := os.Chtimes(st.IFCPath(m.ID), base, base); err != nil {
		t.Fatal(err)
	}
	writeXKT(t, st, m.ID, base.Add(time.Minute))

	if q.EnqueueIfStale(m.ID) {
		t.Fatal("IFC mtime 早于 XKT：期望跳过（false）")
	}
	if n := cr.count(); n != 0 {
		t.Fatalf("runs = %d, want 0（跳过不入队）", n)
	}

	if err := os.Chtimes(st.IFCPath(m.ID), base, base.Add(2*time.Minute)); err != nil {
		t.Fatal(err)
	}
	if !q.EnqueueIfStale(m.ID) {
		t.Fatal("IFC mtime 新于 XKT：期望重转（true）")
	}
	waitRuns(t, cr, 1)
}

// TestEnqueueIfStaleConservative 断言保守原则：XKT 缺失 / IFC 缺失 → 都返回 true 重转。
func TestEnqueueIfStaleConservative(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	st := store.NewStore(t.TempDir())
	m, _ := st.Create("no-xkt.ifc", 1, strings.NewReader("x"))
	cr := &countingRunner{}
	q := NewQueue(st, cr, 1)
	q.Start(ctx)
	if !q.EnqueueIfStale(m.ID) {
		t.Fatal("XKT 缺失：期望保守重转（true）")
	}
	waitRuns(t, cr, 1)

	st2 := store.NewStore(t.TempDir())
	m2, _ := st2.Create("no-ifc.ifc", 1, strings.NewReader("x"))
	cr2 := &countingRunner{}
	q2 := NewQueue(st2, cr2, 1)
	q2.Start(ctx)
	if err := os.Remove(st2.IFCPath(m2.ID)); err != nil {
		t.Fatal(err)
	}
	if !q2.EnqueueIfStale(m2.ID) {
		t.Fatal("IFC 缺失：期望保守重转（true）")
	}
	waitRuns(t, cr2, 1)
}

// TestEnqueueIfStaleEqualMtime 断言 mtime 相等（IFC 恰好等于 XKT）也跳过——
// 严格「不新于」语义：IFC mtime <= XKT mtime → false。
func TestEnqueueIfStaleEqualMtime(t *testing.T) {
	st := store.NewStore(t.TempDir())
	m, _ := st.Create("equal.ifc", 1, strings.NewReader("x"))

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	cr := &countingRunner{}
	q := NewQueue(st, cr, 1)
	q.Start(ctx)

	base := time.Now()
	if err := os.Chtimes(st.IFCPath(m.ID), base, base); err != nil {
		t.Fatal(err)
	}
	writeXKT(t, st, m.ID, base)

	if q.EnqueueIfStale(m.ID) {
		t.Fatal("IFC mtime == XKT mtime：期望跳过（false）")
	}
	if n := cr.count(); n != 0 {
		t.Fatalf("runs = %d, want 0", n)
	}
}
