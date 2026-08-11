// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package api

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/editsvc"
	"ifcviewer/server/internal/store"
)

// newNotifyTestHandler 构造带 edit 客户端 + store + 队列的 chat handler
//（notify 依赖 Ed/St/Q/DataDir；不启动 dispatchLoop）。
func newNotifyTestHandler(t *testing.T, pyURL string) (*ChatHandler, *store.Store, chan string) {
	t.Helper()
	dataDir := t.TempDir()
	st := store.NewStore(dataDir)
	runs := make(chan string, 4)
	q := convert.NewQueue(st, spyRunner{runs: runs}, 1)
	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	q.Start(ctx)
	var ed *editsvc.Client
	if pyURL != "" {
		ed = editsvc.New(pyURL)
	}
	h := &ChatHandler{
		deps:     ChatDeps{Ed: ed, St: st, Q: q, DataDir: dataDir},
		mux:      http.NewServeMux(),
		sessions: map[string]*chatSession{},
		byOC:     map[string]string{},
		subs:     map[string]map[chan []byte]struct{}{},
		creating: map[string]*sync.Mutex{},
	}
	h.registerRoutes()
	return h, st, runs
}

// newNotifySession 建一条会话 + 模型（uploads 落盘），返回会话。
func newNotifySession(t *testing.T, h *ChatHandler) *chatSession {
	t.Helper()
	m, err := h.deps.St.Create("m.ifc", 4, strings.NewReader("fake"))
	if err != nil {
		t.Fatal(err)
	}
	return &chatSession{ID: "c_notify", ModelID: m.ID, CreatedAt: time.Now().UTC().Format(time.RFC3339)}
}

// subscribe 挂一个 SSE 订阅者（pushSystem 的落点），返回收事件帧的 channel。
func (h *ChatHandler) subscribe(cid string) chan []byte {
	ch := make(chan []byte, 16)
	h.mu.Lock()
	if h.subs[cid] == nil {
		h.subs[cid] = map[chan []byte]struct{}{}
	}
	h.subs[cid][ch] = struct{}{}
	h.mu.Unlock()
	return ch
}

// waitChatEvent 等一条指定类型的事件帧（notify 为同步调用，事件在调用内已推送）。
func waitChatEvent(t *testing.T, ch chan []byte, wantType string) []byte {
	t.Helper()
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		select {
		case frame := <-ch:
			if strings.Contains(string(frame), "event: "+wantType) {
				return frame
			}
		case <-time.After(10 * time.Millisecond):
		}
	}
	t.Fatalf("no %s event within timeout", wantType)
	return nil
}

// notifyCallSeq 把 fakePy 收到的调用还原为 "METHOD /path" 序列。
func notifyCallSeq(py *fakePy) []string {
	var out []string
	for _, c := range py.calls {
		out = append(out, c.Method+" "+c.Path)
	}
	return out
}

const notifySmokeScript = `PARAMS = {"name": "Smoke Wall", "fireRating": "F60"}


def build(params, out_path):
    import ifcopenshell.api as api
    model = api.run("project.create_file")
    prj = api.run("root.create_entity", model, ifc_class="IfcProject", name=params["name"])
    api.run("unit.assign_unit", model)
    api.run("context.add_context", model, context_type="Model")
    wall = api.run("root.create_entity", model, ifc_class="IfcWall", name=params["name"])
    api.run("pset.add_pset", model, product=wall, name="Pset_WallCommon")
    api.run("pset.edit_pset", model, pset=model.by_type("IfcPropertySet")[-1],
            properties={"FireRating": params["fireRating"]})
    model.write(out_path)


if __name__ == "__main__":
    import sys
    build(PARAMS, sys.argv[1])
`

// TestNotifyScriptPipeline 断言 notify 走 script 管线（staging 有脚本时）：
// DELETE pending → PUT /script（暂存 staging 脚本）→ run（沙箱试跑）→ save（落版本）
// → 置 converting + 重转 → 推 viewer.committed（带 version）→ staging 脚本归档。
func TestNotifyScriptPipeline(t *testing.T) {
	py, pyURL := newFakePy(t)
	h, st, runs := newNotifyTestHandler(t, pyURL)
	cs := newNotifySession(t, h)
	mid := cs.ModelID

	py.set("DELETE", "/models/"+mid+"/pending", 200, `{"discarded":0}`)
	py.set("PUT", "/models/"+mid+"/script", 200, `{"modelId":"`+mid+`","staged":1,"canUndo":true,"canRedo":false}`)
	py.set("POST", "/models/"+mid+"/script/run", 200, `{"modelId":"`+mid+`","ok":true}`)
	py.set("POST", "/models/"+mid+"/script/save", 200, `{"modelId":"`+mid+`","version":"v1","staged":0}`)

	stagingDir := filepath.Join(h.deps.DataDir, "staging")
	if err := os.MkdirAll(stagingDir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(stagingDir, mid+".py"), []byte(notifySmokeScript), 0o644); err != nil {
		t.Fatal(err)
	}

	ch := h.subscribe(cs.ID)
	h.notify(cs)

	// 调用顺序：DELETE pending → PUT /script → run → save（script 管线，无已退役端点）
	want := []string{
		"DELETE /models/" + mid + "/pending",
		"PUT /models/" + mid + "/script",
		"POST /models/" + mid + "/script/run",
		"POST /models/" + mid + "/script/save",
	}
	if got := notifyCallSeq(py); strings.Join(got, "|") != strings.Join(want, "|") {
		t.Fatalf("notify calls = %v, want %v", got, want)
	}
	// PUT /script 的 body 是 staging 脚本全文
	var stageBody struct {
		Script string `json:"script"`
	}
	if err := json.Unmarshal([]byte(py.calls[1].Body), &stageBody); err != nil {
		t.Fatalf("stage body decode: %v (%s)", err, py.calls[1].Body)
	}
	if stageBody.Script != notifySmokeScript {
		t.Fatalf("staged script mismatch: got %d bytes, want %d", len(stageBody.Script), len(notifySmokeScript))
	}

	// viewer.committed 带 version（save 返回值透传）
	frame := waitChatEvent(t, ch, "viewer.committed")
	if !strings.Contains(string(frame), `"version":"v1"`) {
		t.Fatalf("committed frame = %s, want version v1", frame)
	}
	if strings.Contains(string(frame), "viewer.notify_failed") {
		t.Fatalf("unexpected notify_failed: %s", frame)
	}

	// 重转被触发（status converting → ready）
	waitRun(t, runs)
	waitReady(t, st, mid)

	// staging 脚本随版本归档到 models/{mid}/scripts/v1.py，staging 源删除
	if !fileExists(filepath.Join(h.deps.DataDir, "models", mid, "scripts", "v1.py")) {
		t.Fatal("脚本未归档到 scripts/v1.py")
	}
	if fileExists(filepath.Join(stagingDir, mid+".py")) {
		t.Fatal("归档后 staging 源文件应被删除")
	}
}

// TestNotifyNoScriptReloadOnly 断言 staging 无脚本（手术式编辑）时 notify 只做
// DELETE pending + 重转：不发 PUT /script、不产生版本。
func TestNotifyNoScriptReloadOnly(t *testing.T) {
	py, pyURL := newFakePy(t)
	h, st, runs := newNotifyTestHandler(t, pyURL)
	cs := newNotifySession(t, h)
	mid := cs.ModelID

	py.set("DELETE", "/models/"+mid+"/pending", 200, `{"discarded":0}`)

	ch := h.subscribe(cs.ID)
	h.notify(cs)

	want := []string{"DELETE /models/" + mid + "/pending"}
	if got := notifyCallSeq(py); strings.Join(got, "|") != strings.Join(want, "|") {
		t.Fatalf("notify calls = %v, want %v", got, want)
	}
	frame := waitChatEvent(t, ch, "viewer.committed")
	if strings.Contains(string(frame), `"version":"v1"`) {
		t.Fatalf("无脚本不应有版本：%s", frame)
	}
	waitRun(t, runs)
	waitReady(t, st, mid)
}

// TestNotifyReconvertSkippedWhenNotStale 断言无脚本手术式路径 + IFC 未变
//（mtime 不新于 XKT）时 notify 跳过重转：不发 converting、不入队，保持 ready——
// 这是重转去重的核心收益（多次 idle 重放同源不再全量重转）。
func TestNotifyReconvertSkippedWhenNotStale(t *testing.T) {
	py, pyURL := newFakePy(t)
	h, st, runs := newNotifyTestHandler(t, pyURL)
	cs := newNotifySession(t, h)
	mid := cs.ModelID

	py.set("DELETE", "/models/"+mid+"/pending", 200, `{"discarded":0}`)

	// 造一个 mtime 不早于 IFC 的 XKT → 同源未变
	base := time.Now()
	if err := os.Chtimes(h.deps.St.IFCPath(mid), base, base); err != nil {
		t.Fatal(err)
	}
	xkt := filepath.Join(h.deps.DataDir, "models", mid, "model.xkt")
	if err := os.WriteFile(xkt, []byte("xkt"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.Chtimes(xkt, base, base.Add(time.Minute)); err != nil {
		t.Fatal(err)
	}
	if err := st.SetStatus(mid, "ready", ""); err != nil {
		t.Fatal(err)
	}

	h.notify(cs)

	assertNoRun(t, runs)
	m, _ := st.Get(mid)
	if m.Status != "ready" {
		t.Fatalf("status = %s, want ready（重转跳过、不发 converting）", m.Status)
	}
}

// TestNotifySaveVersionUnresolvableFails 断言 save 成功但版本不可解析
//（响应未带 version，且兜底 GetVersions 失败 / 读到空 current）→ 显式
// viewer.notify_failed(save_version)、不排重转、不推 committed、staging 脚本保留
// ——防止空版本被静默吞掉导致 archive 跳过 → 下次 idle 重复 save。
func TestNotifySaveVersionUnresolvableFails(t *testing.T) {
	cases := []struct {
		name   string
		status int
		body   string
	}{
		{"versions_request_fails", 500, `{"detail":"boom"}`},
		{"versions_current_empty", 200, `{"versions":[],"current":""}`},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			py, pyURL := newFakePy(t)
			h, _, runs := newNotifyTestHandler(t, pyURL)
			cs := newNotifySession(t, h)
			mid := cs.ModelID

			py.set("DELETE", "/models/"+mid+"/pending", 200, `{"discarded":0}`)
			py.set("PUT", "/models/"+mid+"/script", 200, `{"modelId":"`+mid+`","staged":1}`)
			py.set("POST", "/models/"+mid+"/script/run", 200, `{"modelId":"`+mid+`","ok":true}`)
			py.set("POST", "/models/"+mid+"/script/save", 200, `{"modelId":"`+mid+`","staged":0}`)
			py.set("GET", "/models/"+mid+"/versions", tc.status, tc.body)

			stagingDir := filepath.Join(h.deps.DataDir, "staging")
			if err := os.MkdirAll(stagingDir, 0o755); err != nil {
				t.Fatal(err)
			}
			scriptPath := filepath.Join(stagingDir, mid+".py")
			if err := os.WriteFile(scriptPath, []byte(notifySmokeScript), 0o644); err != nil {
				t.Fatal(err)
			}

			ch := h.subscribe(cs.ID)
			h.notify(cs)

			frame := waitChatEvent(t, ch, "viewer.notify_failed")
			if !strings.Contains(string(frame), `"step":"save_version"`) {
				t.Fatalf("notify_failed frame = %s, want step save_version", frame)
			}
			assertNoRun(t, runs)
			if !fileExists(scriptPath) {
				t.Fatal("版本不可解析时 staging 脚本应保留（不归档、不静默吞掉）")
			}
		})
	}
}

// TestNotifyScriptRunFailurePushesFailed 断言 run 沙箱失败 → viewer.notify_failed、
// 不排重转、staging 脚本保留（可修后重试）。
func TestNotifyScriptRunFailurePushesFailed(t *testing.T) {
	py, pyURL := newFakePy(t)
	h, _, runs := newNotifyTestHandler(t, pyURL)
	cs := newNotifySession(t, h)
	mid := cs.ModelID

	py.set("DELETE", "/models/"+mid+"/pending", 200, `{"discarded":0}`)
	py.set("PUT", "/models/"+mid+"/script", 200, `{"modelId":"`+mid+`","staged":1}`)
	py.set("POST", "/models/"+mid+"/script/run", 422, `{"detail":"sandbox boom"}`)

	stagingDir := filepath.Join(h.deps.DataDir, "staging")
	if err := os.MkdirAll(stagingDir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(stagingDir, mid+".py"), []byte(notifySmokeScript), 0o644); err != nil {
		t.Fatal(err)
	}

	ch := h.subscribe(cs.ID)
	h.notify(cs)

	frame := waitChatEvent(t, ch, "viewer.notify_failed")
	if !strings.Contains(string(frame), `"step":"run_script"`) {
		t.Fatalf("notify_failed frame = %s, want step run_script", frame)
	}
	assertNoRun(t, runs)
	if !fileExists(filepath.Join(stagingDir, mid+".py")) {
		t.Fatal("run 失败后 staging 脚本应保留（可修后重试）")
	}
}
