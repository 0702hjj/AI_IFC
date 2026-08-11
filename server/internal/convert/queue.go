// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package convert

import (
	"context"
	"fmt"
	"os/exec"
	"sync"

	"ifcviewer/server/internal/store"
)

type Runner interface {
	Run(ctx context.Context, inputPath, outDir string) error
}

type ExecRunner struct {
	NodeBin string
	Script  string
}

func (r ExecRunner) Run(ctx context.Context, inputPath, outDir string) error {
	cmd := exec.CommandContext(ctx, r.NodeBin, r.Script, inputPath, outDir)
	var stderr cappedBuffer
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("convert2xkt failed: %v: %s", err, stderr.String())
	}
	return nil
}

type cappedBuffer struct{ buf []byte }

func (c *cappedBuffer) Write(p []byte) (int, error) {
	c.buf = append(c.buf, p...)
	if len(c.buf) > 500 {
		c.buf = c.buf[len(c.buf)-500:]
	}
	return len(p), nil
}

func (c *cappedBuffer) String() string { return string(c.buf) }

type Queue struct {
	st      *store.Store
	runner  Runner
	jobs    chan string
	mu      sync.Mutex
	pending map[string]bool
	running map[string]bool
	dirty   map[string]bool
	closed  bool
	ctx     context.Context
}

func NewQueue(st *store.Store, r Runner, workers int) *Queue {
	q := &Queue{
		st: st, runner: r, jobs: make(chan string, 64),
		pending: map[string]bool{}, running: map[string]bool{}, dirty: map[string]bool{},
		ctx: context.Background(),
	}
	for i := 0; i < workers; i++ {
		go q.work()
	}
	return q
}

func (q *Queue) Start(ctx context.Context) {
	q.mu.Lock()
	q.ctx = ctx
	q.mu.Unlock()
	go func() {
		<-ctx.Done()
		q.mu.Lock()
		q.closed = true
		close(q.jobs)
		q.mu.Unlock()
	}()
}

// Enqueue 排队一次转换；已在队列中返回 false。运行中再次 Enqueue 记 dirty，
// worker 完成后会按最新文件内容重跑一次（runner 执行时才读 IFC 文件，
// 排队未启动的任务天然拾取新内容，无需 dirty）。
func (q *Queue) Enqueue(id string) bool {
	q.mu.Lock()
	defer q.mu.Unlock()
	if q.closed {
		return false
	}
	if q.pending[id] {
		if q.running[id] {
			q.dirty[id] = true
		}
		return false
	}
	q.pending[id] = true
	q.jobs <- id
	return true
}

func (q *Queue) work() {
	for id := range q.jobs {
		for {
			q.mu.Lock()
			q.running[id] = true
			ctx := q.ctx
			q.mu.Unlock()
			if err := q.runner.Run(ctx, q.st.IFCPath(id), q.st.ModelDir(id)); err != nil {
				_ = q.st.SetStatus(id, "failed", err.Error())
			} else {
				_ = q.st.SetStatus(id, "ready", "")
			}
			q.mu.Lock()
			delete(q.running, id)
			if !q.dirty[id] {
				delete(q.pending, id)
				q.mu.Unlock()
				break
			}
			// 运行期间有新提交：无论本次成败都按最新内容重转一次
			delete(q.dirty, id)
			q.mu.Unlock()
		}
	}
}
