// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_runs_race_test.go：runs 表防御竞态——条件删除（旧 run 迟收尾不得删
// 新 run 的登记）。
package api

import (
	"context"
	"net/http"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/cloudwego/eino/components/model"
	"github.com/cloudwego/eino/schema"

	"ifcviewer/server/internal/agent"
)

// --- runs 表防御竞态：条件删除 ---

// countingModel：第一跑阻塞（等 close(release)），其后每跑立即答复收尾——
// 构造「旧 run 迟收尾 vs 新 run 已登记」的竞态窗口。
type countingModel struct {
	step    *int32
	release chan struct{}
	started chan struct{}
}

func newCountingModel(step *int32) *countingModel {
	return &countingModel{step: step, release: make(chan struct{}), started: make(chan struct{}, 4)}
}

func (m *countingModel) WithTools(tools []*schema.ToolInfo) (model.ToolCallingChatModel, error) {
	return m, nil
}

func (m *countingModel) Stream(ctx context.Context, input []*schema.Message, opts ...model.Option) (*schema.StreamReader[*schema.Message], error) {
	n := atomic.AddInt32(m.step, 1)
	if n == 1 {
		m.started <- struct{}{}
		<-m.release // 第一跑阻塞，直到测试放行
	}
	return schema.StreamReaderFromArray([]*schema.Message{{Role: schema.Assistant, Content: "ok"}}), nil
}

func (m *countingModel) Generate(ctx context.Context, input []*schema.Message, opts ...model.Option) (*schema.Message, error) {
	n := atomic.AddInt32(m.step, 1)
	if n == 1 {
		m.started <- struct{}{}
		<-m.release
	}
	return &schema.Message{Role: schema.Assistant, Content: "ok"}, nil
}

// TestRunsDeleteConditionalOnRunIdentity：post run1（阻塞）→ post run2（覆盖表项、
// 取消 run1）→ run1 收尾不得删 run2 的登记；run2 收尾后表项清空。
func TestRunsDeleteConditionalOnRunIdentity(t *testing.T) {
	dataDir := t.TempDir()
	evStore := agent.NewEventStore(dataDir)
	var step int32
	cm := newCountingModel(&step)
	ag, err := agent.New(agent.LLMConfig{}, agent.WithModel(cm), agent.WithStore(evStore))
	if err != nil {
		t.Fatal(err)
	}
	h := &ChatHandler{
		deps:     ChatDeps{Ag: ag, Ev: evStore, DataDir: dataDir},
		mux:      http.NewServeMux(),
		sessions: map[string]*chatSession{},
		byAgent:  map[string]string{},
		runs:     map[string]*chatRun{},
		subs:     map[string]map[chan []byte]struct{}{},
		creating: map[string]*sync.Mutex{},
	}
	h.registerRoutes()
	cs, err := doChatCreate(h, `{"title":"t"}`)
	if err != nil {
		t.Fatal(err)
	}
	if code := postChat(t, h, cs.ID, "第一跑"); code != http.StatusOK {
		t.Fatalf("post1 status = %d", code)
	}
	<-cm.started // run1 模型已启动（阻塞中）
	waitForRunsCount(t, h, cs.ID, 1)
	if code := postChat(t, h, cs.ID, "第二跑"); code != http.StatusOK {
		t.Fatalf("post2 status = %d", code)
	}
	// run1 被取消 → 迟收尾；run2 已登记并完成 → 表项由 run2 自己删除。
	waitForRunsCount(t, h, cs.ID, 0)
	// 放行第一跑（其 consumeRun 现在才收尾）：表已空，无「误删/复活」可言，
	// 但不得 panic 或重新写入（run1 的 identity 已不是表内条目）。
	close(cm.release)
	// 给 run1 收尾一点时间后再断言表项仍为空（条件等待 run1 残留不出现）
	time.Sleep(50 * time.Millisecond)
	waitForRunsCount(t, h, cs.ID, 0)
}

// waitForRunsCount 条件等待 runs 表条目数（超时失败）。
func waitForRunsCount(t *testing.T, h *ChatHandler, cid string, want int) {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		h.mu.RLock()
		got := 0
		if _, ok := h.runs[cid]; ok {
			got = 1
		}
		h.mu.RUnlock()
		if got == want {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("runs[%s] 条目数未到 %d", cid, want)
}
