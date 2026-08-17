package api

import (
	"bufio"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

// --- SSE Last-Event-ID 重同步（P1-4-B） ---

type sseFrame struct{ id, event, data string }

// readSSEFrames 从 SSE 流读 n 个数据帧（跳过注释行），超时或流断即失败。
func readSSEFrames(t *testing.T, r *bufio.Reader, n int) []sseFrame {
	t.Helper()
	type res struct {
		f   sseFrame
		err error
	}
	ch := make(chan res, n+1)
	go func() {
		var f sseFrame
		has := false
		for {
			line, err := r.ReadString('\n')
			if err != nil {
				ch <- res{err: err}
				return
			}
			line = strings.TrimSuffix(line, "\n")
			switch {
			case line == "":
				if has {
					ch <- res{f: f}
					f = sseFrame{}
					has = false
				}
			case strings.HasPrefix(line, ":"): // 注释（: connected）
			case strings.HasPrefix(line, "id: "):
				f.id = strings.TrimPrefix(line, "id: ")
				has = true
			case strings.HasPrefix(line, "event: "):
				f.event = strings.TrimPrefix(line, "event: ")
				has = true
			case strings.HasPrefix(line, "data: "):
				f.data = strings.TrimPrefix(line, "data: ")
				has = true
			}
		}
	}()
	frames := make([]sseFrame, 0, n)
	timer := time.After(5 * time.Second)
	for len(frames) < n {
		select {
		case r := <-ch:
			if r.err != nil {
				t.Fatalf("SSE read: %v（已读 %d/%d 帧）", r.err, len(frames), n)
			}
			frames = append(frames, r.f)
		case <-timer:
			t.Fatalf("超时：等 %d 帧只读到 %d", n, len(frames))
		}
	}
	return frames
}

// newSSETestHandler 构造带一条已绑定会话的 chat handler（scripted agent，不走真模型）。
func newSSETestHandler(t *testing.T) (*ChatHandler, *httptest.Server, string) {
	t.Helper()
	h := newChatTestHandler(t)
	cs := &chatSession{
		ID: "c_sse", AgentID: "s_sse", ModelID: "m_eeeeeeeeeeeeeeee",
		Title: "t", CreatedAt: time.Now().UTC().Format(time.RFC3339), lastCheck: time.Now(),
	}
	h.sessions[cs.ID] = cs
	h.byAgent[cs.AgentID] = cs.ID
	srv := httptest.NewServer(h.mux)
	t.Cleanup(srv.Close)
	return h, srv, cs.ID
}

func sseConnect(t *testing.T, srv *httptest.Server, cid, lastEventID string) (*http.Response, *bufio.Reader) {
	t.Helper()
	req, err := http.NewRequest(http.MethodGet, srv.URL+"/api/v1/chat/sessions/"+cid+"/events", nil)
	if err != nil {
		t.Fatal(err)
	}
	if lastEventID != "" {
		req.Header.Set("Last-Event-ID", lastEventID)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	if resp.StatusCode != http.StatusOK {
		resp.Body.Close()
		t.Fatalf("SSE status = %d, want 200", resp.StatusCode)
	}
	return resp, bufio.NewReader(resp.Body)
}

// TestSSEResyncLastEventID：订阅者断开期间产生 3 个事件，带 Last-Event-ID 重连应补发且顺序正确。
func TestSSEResyncLastEventID(t *testing.T) {
	h, srv, cid := newSSETestHandler(t)

	// 连接 1：读到 ": connected" 即说明订阅已注册；随后收 2 个事件（id 1、2）。
	resp1, r1 := sseConnect(t, srv, cid, "")
	h.pushSystem(cid, "viewer.test", map[string]any{"n": 1})
	h.pushSystem(cid, "viewer.test", map[string]any{"n": 2})
	live := readSSEFrames(t, r1, 2)
	if live[0].id != "1" || live[1].id != "2" {
		t.Fatalf("在线帧 id = %q,%q，want 1,2（每事件应带递增 id）", live[0].id, live[1].id)
	}
	resp1.Body.Close()

	// 断开期间产生 3 个事件（id 3、4、5）。
	h.pushSystem(cid, "viewer.test", map[string]any{"n": 3})
	h.pushSystem(cid, "viewer.test", map[string]any{"n": 4})
	h.pushSystem(cid, "viewer.test", map[string]any{"n": 5})

	// 带 Last-Event-ID: 2 重连 → 补发 3 条，顺序 3,4,5。
	resp2, r2 := sseConnect(t, srv, cid, "2")
	defer resp2.Body.Close()
	missed := readSSEFrames(t, r2, 3)
	for i, want := range []string{"3", "4", "5"} {
		if missed[i].id != want {
			t.Fatalf("补发帧[%d].id = %q，want %q（重连补发顺序错误）", i, missed[i].id, want)
		}
		if missed[i].event != "viewer.test" {
			t.Fatalf("补发帧[%d].event = %q，want viewer.test", i, missed[i].event)
		}
		wantData := fmt.Sprintf(`{"n":%d}`, i+3)
		if missed[i].data != wantData {
			t.Fatalf("补发帧[%d].data = %q，want %q", i, missed[i].data, wantData)
		}
	}
}

// TestSSEResyncBufferOverflow：缓冲只留最近 64 条；Last-Event-ID 已滚出缓冲时，
// 从重连点最早的可用事件续传（id 7..70），客户端可从 id 间隙感知空洞。
func TestSSEResyncBufferOverflow(t *testing.T) {
	h, srv, cid := newSSETestHandler(t)

	const total = 70
	for i := 1; i <= total; i++ { // 无订阅者也应入缓冲
		h.pushSystem(cid, "viewer.test", map[string]any{"n": i})
	}

	resp, r := sseConnect(t, srv, cid, "1")
	defer resp.Body.Close()
	frames := readSSEFrames(t, r, sseReplayBufferSize)
	if frames[0].id != "7" { // 70 - 64 + 1
		t.Fatalf("首条补发 id = %q，want 7（缓冲最早可用事件）", frames[0].id)
	}
	for i := 1; i < len(frames); i++ {
		var prev, cur int
		fmt.Sscanf(frames[i-1].id, "%d", &prev)
		fmt.Sscanf(frames[i].id, "%d", &cur)
		if cur != prev+1 {
			t.Fatalf("补发 id 不连续：%q → %q", frames[i-1].id, frames[i].id)
		}
	}
	if frames[len(frames)-1].id != "70" {
		t.Fatalf("末条补发 id = %q，want 70", frames[len(frames)-1].id)
	}
}

// TestSSENoLastEventIDNoReplay：契约兼容——不带 Last-Event-ID 的旧客户端行为不变
// （不补发历史，只收重连后的新事件）。
func TestSSENoLastEventIDNoReplay(t *testing.T) {
	h, srv, cid := newSSETestHandler(t)

	h.pushSystem(cid, "viewer.test", map[string]any{"n": 1})
	resp, r := sseConnect(t, srv, cid, "")
	defer resp.Body.Close()
	h.pushSystem(cid, "viewer.test", map[string]any{"n": 2})
	frames := readSSEFrames(t, r, 1)
	if frames[0].id != "2" {
		t.Fatalf("首帧 id = %q，want 2（无 Last-Event-ID 不应补发 id=1 的历史）", frames[0].id)
	}
}
