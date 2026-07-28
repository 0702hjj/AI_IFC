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
	closed  bool
	ctx     context.Context
}

func NewQueue(st *store.Store, r Runner, workers int) *Queue {
	q := &Queue{st: st, runner: r, jobs: make(chan string, 64), pending: map[string]bool{}, ctx: context.Background()}
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

func (q *Queue) Enqueue(id string) bool {
	q.mu.Lock()
	defer q.mu.Unlock()
	if q.closed || q.pending[id] {
		return false
	}
	q.pending[id] = true
	q.jobs <- id
	return true
}

func (q *Queue) work() {
	for id := range q.jobs {
		func() {
			defer func() {
				q.mu.Lock()
				delete(q.pending, id)
				q.mu.Unlock()
			}()
			q.mu.Lock()
			ctx := q.ctx
			q.mu.Unlock()
			if err := q.runner.Run(ctx, q.st.IFCPath(id), q.st.ModelDir(id)); err != nil {
				_ = q.st.SetStatus(id, "failed", err.Error())
			} else {
				_ = q.st.SetStatus(id, "ready", "")
			}
		}()
	}
}
