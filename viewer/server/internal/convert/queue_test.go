// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package convert

import (
	"context"
	"errors"
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
