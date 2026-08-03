// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

// chat.go：对话式 AI 建模的 chat 模块（demo）。
// 独立 Handler，与既有 NewHandler 并列挂载（main.go 组合 root mux），不触碰既有路由。
// 职责：会话管理（chatSessionId ↔ opencodeSessionId ↔ modelId）、消息转发、SSE 透传。
// 后续 P2 在同一事件分发循环内挂三连触发器（见 dispatcher 的 TODO 钩子）。
package api

import (
	"bufio"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"

	"ifcviewer/server/internal/change"
	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/editsvc"
	"ifcviewer/server/internal/opencode"
	"ifcviewer/server/internal/store"
)

// chatAgent 是转发给 opencode 的 agent 名（IFC_front/AI_IFC/.opencode/agent/ifc-demo.md）。
const chatAgent = "ifc-demo"

type chatSession struct {
	ID         string    `json:"chatSessionId"`
	OpencodeID string    `json:"opencodeSessionId"`
	ModelID    string    `json:"modelId"`
	Title      string    `json:"title"`
	CreatedAt  string    `json:"createdAt"`
	dirty      bool      `json:"-"` // write/edit 工具改过 uploads/{modelId}.ifc（file.edited 捕获）
	lastCheck  time.Time `json:"-"` // 上次变更检测时刻；idle 时 mtime 晚于它即视为被改（兜底 bash/脚本改文件场景）
}

// ChatDeps 是 chat 模块的依赖包（notify 三连需要 edit 编排全套依赖）。
type ChatDeps struct {
	OC      *opencode.Client
	Ed      *editsvc.Client
	St      *store.Store
	Chg     change.Store
	Q       *convert.Queue
	DataDir string
}

// ChatHandler 是 chat 模块的 HTTP handler（内部小 mux + 会话 map + 事件分发 + 三连触发）。
type ChatHandler struct {
	deps   ChatDeps
	agent  string
	mux    *http.ServeMux
	cancel context.CancelFunc

	mu       sync.RWMutex
	sessions map[string]*chatSession             // chatSessionId → session
	byOC     map[string]string                   // opencodeSessionId → chatSessionId
	subs     map[string]map[chan []byte]struct{} // chatSessionId → 浏览器 SSE 订阅者集合

	createMu sync.Mutex             // 仅保护下面的 creating map
	creating map[string]*sync.Mutex // per-modelId 创建串行锁：根治同 modelId 并发 createSession 的 TOCTOU 竞态
}

// NewChatHandler 创建 chat 模块 handler 并启动 opencode 事件订阅循环（随 ctx 退出）。
// 会话映射持久化在 {DataDir}/chat-sessions.json（原子写），server 重启后会话连续性仍在
// （opencode 侧会话本身即持久，重启后可继续拉历史/续聊）。
func NewChatHandler(ctx context.Context, d ChatDeps) *ChatHandler {
	cctx, cancel := context.WithCancel(ctx)
	h := &ChatHandler{
		deps: d, agent: chatAgent, mux: http.NewServeMux(), cancel: cancel,
		sessions: map[string]*chatSession{}, byOC: map[string]string{},
		subs: map[string]map[chan []byte]struct{}{}, creating: map[string]*sync.Mutex{},
	}
	h.loadSessions()
	h.registerRoutes()
	go h.dispatchLoop(cctx)
	return h
}

// registerRoutes 注册 chat 模块全部路由（NewChatHandler 与测试 handler 共用）。
func (h *ChatHandler) registerRoutes() {
	h.mux.HandleFunc("POST /api/chat/sessions", h.createSession)
	h.mux.HandleFunc("GET /api/chat/sessions", h.listSessions)
	h.mux.HandleFunc("POST /api/chat/sessions/{cid}/messages", h.postMessage)
	h.mux.HandleFunc("GET /api/chat/sessions/{cid}/messages", h.getMessages)
	h.mux.HandleFunc("GET /api/chat/sessions/{cid}/events", h.events)
	h.mux.HandleFunc("POST /api/chat/sessions/{cid}/abort", h.abortSession)
	h.mux.HandleFunc("POST /api/chat/projects", h.createProject)
}

func (h *ChatHandler) sessionsPath() string {
	return filepath.Join(h.deps.DataDir, "chat-sessions.json")
}

// loadSessions 启动时恢复会话映射（文件不存在视为首次启动）。
// 去重：同 modelId 只保留最早 createdAt 一条——清理历史竞态残留（StrictMode 双发期产生），
// 保证 createSession 的幂等检查（map 遍历）稳定命中同一条，不会因 map 顺序随机导致历史时有时无。
func (h *ChatHandler) loadSessions() {
	data, err := os.ReadFile(h.sessionsPath())
	if err != nil {
		return
	}
	var list []*chatSession
	if err := json.Unmarshal(data, &list); err != nil {
		log.Printf("chat: load sessions: %v", err)
		return
	}
	earliest := map[string]*chatSession{} // modelId(非空) → 最早 createdAt
	var noModel []*chatSession            // 无 modelId 的不幂等，全部保留
	for _, cs := range list {
		if cs.ModelID == "" {
			noModel = append(noModel, cs)
			continue
		}
		if cur, ok := earliest[cs.ModelID]; !ok || cs.CreatedAt < cur.CreatedAt {
			earliest[cs.ModelID] = cs
		}
	}
	deduped := noModel
	for _, cs := range earliest {
		deduped = append(deduped, cs)
	}
	for _, cs := range deduped {
		cs.dirty = false
		cs.lastCheck = time.Now() // 防重启后 mtime 误判
		h.sessions[cs.ID] = cs
		h.byOC[cs.OpencodeID] = cs.ID
	}
	if len(deduped) != len(list) {
		log.Printf("chat: dedup sessions %d → %d (清理同 modelId 竞态残留)", len(list), len(deduped))
		h.saveSessions() // 写回清理后的，避免下次再加载到重复
	} else if len(deduped) > 0 {
		log.Printf("chat: restored %d session(s)", len(deduped))
	}
}

// saveSessions 原子写会话映射（tmp + rename，同 viewer 原子写模式）。
func (h *ChatHandler) saveSessions() {
	h.mu.RLock()
	list := make([]*chatSession, 0, len(h.sessions))
	for _, cs := range h.sessions {
		list = append(list, cs)
	}
	h.mu.RUnlock()
	data, err := json.MarshalIndent(list, "", "  ")
	if err != nil {
		return
	}
	tmp := h.sessionsPath() + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		log.Printf("chat: save sessions: %v", err)
		return
	}
	if err := os.Rename(tmp, h.sessionsPath()); err != nil {
		log.Printf("chat: save sessions rename: %v", err)
	}
}

func (h *ChatHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) { h.mux.ServeHTTP(w, r) }

func newChatID() string {
	b := make([]byte, 8)
	_, _ = rand.Read(b)
	return "c_" + hex.EncodeToString(b)
}

// findSession 按 modelId 查已绑定会话（空 modelId 永远不命中——不幂等）。
func (h *ChatHandler) findSession(modelID string) *chatSession {
	if modelID == "" {
		return nil
	}
	h.mu.RLock()
	defer h.mu.RUnlock()
	for _, cs := range h.sessions {
		if cs.ModelID == modelID {
			return cs
		}
	}
	return nil
}

// createLock 返回某 modelId 专用的创建串行锁（同 modelId 并发请求共享同一把，互不阻塞其他 modelId）。
func (h *ChatHandler) createLock(key string) *sync.Mutex {
	h.createMu.Lock()
	defer h.createMu.Unlock()
	mu, ok := h.creating[key]
	if !ok {
		mu = &sync.Mutex{}
		h.creating[key] = mu
	}
	return mu
}

func (h *ChatHandler) createSession(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Title   string `json:"title"`
		ModelID string `json:"modelId"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "invalid json body")
		return
	}
	// 幂等：同一 modelId 只会有一个会话——退出再打开返回同一会话（会话连续性）。
	// 快速路径：读锁先查，命中即返回。
	if existing := h.findSession(body.ModelID); existing != nil {
		writeJSON(w, existing)
		return
	}
	if body.Title == "" {
		body.Title = "chat"
	}
	// per-modelId 串行创建：同 modelId 的并发请求在此互斥（StrictMode dev 双发 / 用户连点），
	// 网络往返在锁内但仅阻塞同 modelId；拿到锁后 double-check，已被别人建好就直接复用。
	cmu := h.createLock(body.ModelID)
	cmu.Lock()
	defer cmu.Unlock()
	if existing := h.findSession(body.ModelID); existing != nil {
		writeJSON(w, existing)
		return
	}
	s, err := h.deps.OC.CreateSession(r.Context(), body.Title)
	if err != nil {
		writeChatErr(w, err)
		return
	}
	cs := &chatSession{
		ID: newChatID(), OpencodeID: s.ID, ModelID: body.ModelID,
		Title: body.Title, CreatedAt: time.Now().UTC().Format(time.RFC3339),
		lastCheck: time.Now(),
	}
	h.mu.Lock()
	h.sessions[cs.ID] = cs
	h.byOC[cs.OpencodeID] = cs.ID
	h.mu.Unlock()
	h.saveSessions()
	writeJSON(w, cs)
}

// getMessages 透传 opencode 会话历史（重新打开时回填聊天内容）。
func (h *ChatHandler) getMessages(w http.ResponseWriter, r *http.Request) {
	cs := h.sessionOrErr(w, r.PathValue("cid"))
	if cs == nil {
		return
	}
	msgs, err := h.deps.OC.GetMessages(r.Context(), cs.OpencodeID)
	if err != nil {
		writeChatErr(w, err)
		return
	}
	writeJSON(w, msgs)
}

// abortSession 中止 AI 当前 turn（透传 opencode POST /session/{ocId}/abort）。
// 前端在 busy 时把"发送"钮变"停止"调此端点；opencode 随后发 session.idle + 进行中 part 的 removed。
func (h *ChatHandler) abortSession(w http.ResponseWriter, r *http.Request) {
	cs := h.sessionOrErr(w, r.PathValue("cid"))
	if cs == nil {
		return
	}
	if err := h.deps.OC.Abort(r.Context(), cs.OpencodeID); err != nil {
		writeChatErr(w, err)
		return
	}
	writeJSON(w, map[string]bool{"aborted": true})
}

func (h *ChatHandler) listSessions(w http.ResponseWriter, r *http.Request) {
	h.mu.RLock()
	out := make([]*chatSession, 0, len(h.sessions))
	for _, cs := range h.sessions {
		out = append(out, cs)
	}
	h.mu.RUnlock()
	writeJSON(w, out)
}

func (h *ChatHandler) postMessage(w http.ResponseWriter, r *http.Request) {
	cs := h.sessionOrErr(w, r.PathValue("cid"))
	if cs == nil {
		return
	}
	var body struct {
		Text string `json:"text"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.Text == "" {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "text required")
		return
	}
	text := body.Text
	if cs.ModelID != "" {
		text = fmt.Sprintf("[系统上下文] 当前会话绑定模型文件 viewer/data/uploads/%s.ifc（改它即改该模型；若是从零构建需求，该文件初始为骨架，直接在其上建造）。本会话 chatSessionId：%s。\n\n[用户需求] %s",
			cs.ModelID, cs.ID, body.Text)
	}
	if err := h.deps.OC.PromptAsync(r.Context(), cs.OpencodeID, text, h.agent); err != nil {
		writeChatErr(w, err)
		return
	}
	writeJSON(w, map[string]bool{"accepted": true})
}

// events 是该会话的 SSE 透传端点：浏览器 EventSource 连这里。
func (h *ChatHandler) events(w http.ResponseWriter, r *http.Request) {
	cs := h.sessionOrErr(w, r.PathValue("cid"))
	if cs == nil {
		return
	}
	flusher, ok := w.(http.Flusher)
	if !ok {
		writeErr(w, http.StatusInternalServerError, codeInternal, "streaming unsupported")
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	ch := make(chan []byte, 32)
	h.mu.Lock()
	if h.subs[cs.ID] == nil {
		h.subs[cs.ID] = map[chan []byte]struct{}{}
	}
	h.subs[cs.ID][ch] = struct{}{}
	h.mu.Unlock()
	defer func() {
		h.mu.Lock()
		delete(h.subs[cs.ID], ch)
		h.mu.Unlock()
	}()
	fmt.Fprintf(w, ": connected\n\n")
	flusher.Flush()
	for {
		select {
		case data := <-ch:
			if _, err := w.Write(data); err != nil {
				return
			}
			flusher.Flush()
		case <-r.Context().Done():
			return
		}
	}
}

func (h *ChatHandler) sessionOrErr(w http.ResponseWriter, cid string) *chatSession {
	h.mu.RLock()
	cs := h.sessions[cid]
	h.mu.RUnlock()
	if cs == nil {
		writeErr(w, http.StatusNotFound, codeNotFound, "chat session not found")
		return nil
	}
	return cs
}

// --- 空白项目：点击「新建」即完成初始化（骨架模型 + modelId），agent 只是后续的修改者 ---

const ifcBase64Alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"

// newGlobalID 生成 IFC GlobalId（22 字符，首字符 0-3，128bit 随机数按 IFC base64 编码）。
func newGlobalID() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	b[0] &= 0x03
	var sb strings.Builder
	sb.Grow(22)
	acc, nbits := 0, 0
	for _, by := range b {
		acc = acc<<8 | int(by)
		nbits += 8
		for nbits >= 6 {
			nbits -= 6
			sb.WriteByte(ifcBase64Alphabet[(acc>>nbits)&0x3F])
		}
	}
	if nbits > 0 {
		sb.WriteByte(ifcBase64Alphabet[(acc<<(6-nbits))&0x3F])
	}
	return sb.String()[:22]
}

// skeletonIFC 是最小合法 IFC（仅 IfcProject + 几何上下文 + 单位），
// converter/edit-service 均已验证可正常消化。两个 %s = project GlobalId、项目名。
const skeletonIFC = `ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');
FILE_NAME('skeleton.ifc','2026-01-01T00:00:00',(''),(''),'ifcopenshell','AI_IFC','');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCPROJECT('%s',#5,'%s',$,$,$,$,(#9),#13);
#5=IFCOWNERHISTORY($,$,$,$,$,$,$,$);
#9=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#10,$);
#10=IFCAXIS2PLACEMENT3D(#11,$,$);
#11=IFCCARTESIANPOINT((0.,0.,0.));
#13=IFCUNITASSIGNMENT((#14));
#14=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);
ENDSEC;
END-ISO-10303-21;
`

// ifcStringEscape 转义 IFC STEP 字符串（单引号双写）。
func ifcStringEscape(s string) string { return strings.ReplaceAll(s, "'", "''") }

// createProject 创建空白项目：写入骨架 IFC 并注册为模型（modelId 即刻就位），
// 入队转换。之后 AI 从零构建走的是与改模型完全相同的主链路。
func (h *ChatHandler) createProject(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Title string `json:"title"`
	}
	_ = json.NewDecoder(r.Body).Decode(&body) // title 可空
	if body.Title == "" {
		body.Title = "AI 项目"
	}
	content := fmt.Sprintf(skeletonIFC, newGlobalID(), ifcStringEscape(body.Title))
	m, err := h.deps.St.Create(body.Title+".ifc", int64(len(content)), strings.NewReader(content))
	if err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	h.deps.Q.Enqueue(m.ID)
	writeJSON(w, m)
}

// dispatchLoop 全局订阅 opencode /event，断线退避重连；每条事件先过触发器（onEvent）再透传（forward）。
func (h *ChatHandler) dispatchLoop(ctx context.Context) {
	backoff := time.Second
	for {
		if ctx.Err() != nil {
			return
		}
		ch, err := h.deps.OC.Subscribe(ctx)
		if err != nil {
			log.Printf("chat: subscribe opencode events: %v (retry in %s)", err, backoff)
		} else {
			backoff = time.Second
			for ev := range ch {
				h.onEvent(ev)
				h.forward(ev)
			}
			log.Printf("chat: opencode event stream closed (retry in %s)", backoff)
		}
		select {
		case <-ctx.Done():
			return
		case <-time.After(backoff):
		}
		if backoff < 30*time.Second {
			backoff *= 2
		}
	}
}

// onEvent 是 P2 三连触发器：file.edited 命中工作区 → 置 dirty；
// session.idle + dirty + bound → 异步执行 notify 三连。
func (h *ChatHandler) onEvent(ev opencode.Event) {
	switch ev.Type {
	case "file.edited":
		var p struct {
			File string `json:"file"`
		}
		if err := json.Unmarshal(ev.Properties, &p); err != nil {
			return
		}
		mid := modelIDFromEditedFile(p.File)
		if mid == "" {
			return
		}
		h.mu.Lock()
		for _, cs := range h.sessions {
			if cs.ModelID == mid {
				cs.dirty = true
			}
		}
		h.mu.Unlock()
	case "session.idle":
		ocSID := ev.SessionID()
		if ocSID == "" {
			return
		}
		h.mu.Lock()
		cid, ok := h.byOC[ocSID]
		cs := h.sessions[cid]
		if !ok || cs == nil || cs.ModelID == "" {
			h.mu.Unlock()
			return
		}
		// 变更检测：file.edited 已置 dirty（write/edit 工具路径）；
		// 否则兜底查工作区 mtime（agent 用 bash 跑脚本改文件时 opencode 不发 file.edited）。
		dirtyNow := cs.dirty
		if !dirtyNow {
			if fi, err := os.Stat(filepath.Join(h.deps.DataDir, "uploads", cs.ModelID+".ifc")); err == nil && fi.ModTime().After(cs.lastCheck) {
				dirtyNow = true
			}
		}
		if !dirtyNow {
			h.mu.Unlock()
			return
		}
		cs.dirty = false // 同一 turn 只触发一次
		cs.lastCheck = time.Now()
		h.mu.Unlock()
		log.Printf("chat: session %s idle with modified model %s → notify", ocSID, cs.ModelID)
		go h.notify(cs, "AI modification")
	}
}

// modelIDFromEditedFile 从 file.edited 的路径提取 modelId（命中 {dataDir}/uploads/{id}.ifc）。
func modelIDFromEditedFile(file string) string {
	base := filepath.Base(filepath.ToSlash(file))
	if !strings.HasSuffix(base, ".ifc") || !strings.Contains(filepath.ToSlash(file), "/uploads/") {
		return ""
	}
	id := strings.TrimSuffix(base, ".ifc")
	if !modelIDRe.MatchString(id) {
		return ""
	}
	return id
}

var modelIDRe = regexp.MustCompile(`^m_[0-9a-f]{16}$`)

var ifcProjectRe = regexp.MustCompile(`IFCPROJECT\('([^']+)'`)

// ifcProjectGUID 逐行扫描 IFC（STEP 文本），提取 IfcProject 的 GlobalId（恒存在，无需 ifcopenshell）。
func ifcProjectGUID(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for sc.Scan() {
		if m := ifcProjectRe.FindSubmatch(sc.Bytes()); m != nil {
			return string(m[1]), nil
		}
	}
	if err := sc.Err(); err != nil {
		return "", err
	}
	return "", fmt.Errorf("IFCPROJECT not found in %s", path)
}

// notify 是 AI 大改后的固定三连（顺序不可换）：
// ① DELETE pending（强制 edit-service 从磁盘重载 = 坏文件自检，防旧内存模型覆盖 agent 的修改）
// ② PUT pset 审计标记（provenance=AI，commit 入场券）
// ③ commitOrchestrate（落盘 + v{n+1} 快照 + change log + 重转）
// 完成后向该会话推送 viewer.committed；失败推 viewer.notify_failed。
func (h *ChatHandler) notify(cs *chatSession, summary string) {
	ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
	defer cancel()
	modelID := cs.ModelID
	fail := func(step string, err error) {
		log.Printf("chat: notify %s step %s failed: %v", modelID, step, err)
		h.pushSystem(cs.ID, "viewer.notify_failed", map[string]any{
			"modelId": modelID, "step": step, "reason": err.Error(),
		})
	}

	if _, err := h.deps.Ed.DeletePending(ctx, modelID); err != nil {
		fail("discard_pending", err)
		return
	}
	guid, err := ifcProjectGUID(filepath.Join(h.deps.DataDir, "uploads", modelID+".ifc"))
	if err != nil {
		fail("extract_guid", err)
		return
	}
	putBody, _ := json.Marshal(map[string]any{
		"psets":      map[string]any{"Pset_ViewerMeta": map[string]any{"AISummary": summary}},
		"author":     "opencode-cli",
		"provenance": map[string]string{"source": "AI"},
	})
	if _, err := h.deps.Ed.PutEntity(ctx, modelID, guid, putBody); err != nil {
		fail("mark", err)
		return
	}
	resp, err := commitOrchestrate(ctx, h.deps.Ed, h.deps.St, h.deps.Chg, h.deps.Q, modelID)
	if err != nil {
		fail("commit", err)
		return
	}
	version := ""
	if vers, err := h.deps.Ed.GetVersions(ctx, modelID); err == nil {
		version = vers.Current
	}
	// ⑤ 制品归档（过程与结果同存，随版本同步）：构建脚本 + 设计意图 JSON
	// staging 命名：{modelId}.py（脚本）、{modelId}.design.json（设计意图）；
	// 归档：models/{id}/scripts/v{n}.py、models/{id}/designs/v{n}.json。
	// 无对应 staging 文件则跳过（手术式编辑无脚本；简单改动无 design.json）。
	h.archiveStagingArtifact(modelID, version, modelID+".py", "scripts", "py")
	h.archiveStagingArtifact(modelID, version, modelID+".design.json", "designs", "json")
	out := map[string]any{
		"modelId": modelID, "version": version, "committed": resp["committed"],
	}
	if w, ok := resp["warning"]; ok {
		out["warning"] = w
	}
	log.Printf("chat: notify %s committed (version %s)", modelID, version)
	h.pushSystem(cs.ID, "viewer.committed", out)
}

// pushSystem 向指定会话的浏览器订阅者推送 chat 模块自定义 SSE 事件。
func (h *ChatHandler) pushSystem(cid, eventType string, data map[string]any) {
	raw, err := json.Marshal(data)
	if err != nil {
		return
	}
	frame := []byte("event: " + eventType + "\ndata: " + string(raw) + "\n\n")
	h.mu.RLock()
	defer h.mu.RUnlock()
	h.pushLocked(cid, frame)
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

// copyFile 复制文件（先写 tmp 再改名，同 viewer 原子写模式）。
func copyFile(src, dst string) error {
	data, err := os.ReadFile(src)
	if err != nil {
		return err
	}
	tmp := dst + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, dst)
}

// archiveStagingArtifact 把 staging 区的一个制品归档到 models/{id}/{subdir}/v{n}.{dstSuffix}（随版本同步）。
// stagingName 是 staging 区文件全名（如 "{id}.py"、"{id}.design.json"）；不存在则跳过。
// 归档成功后删除 staging 源文件（同脚本归档语义）。version 为空（commit 未产生版本）则整体跳过。
func (h *ChatHandler) archiveStagingArtifact(modelID, version, stagingName, subdir, dstSuffix string) {
	if version == "" {
		return
	}
	src := filepath.Join(h.deps.DataDir, "staging", stagingName)
	if !fileExists(src) {
		return
	}
	dstDir := filepath.Join(h.deps.DataDir, "models", modelID, subdir)
	dst := filepath.Join(dstDir, version+"."+dstSuffix)
	if err := os.MkdirAll(dstDir, 0o755); err != nil {
		log.Printf("chat: mkdir %s: %v", dstDir, err)
		return
	}
	if err := copyFile(src, dst); err != nil {
		log.Printf("chat: archive %s %s: %v", subdir, modelID, err)
		return
	}
	os.Remove(src)
	log.Printf("chat: archived %s/%s.%s", subdir, version, dstSuffix)
}

// forward 把一条 opencode 事件封装为 SSE 帧，定向（或广播）推给浏览器订阅者。
func (h *ChatHandler) forward(ev opencode.Event) {
	frame := []byte("event: " + ev.Type + "\ndata: " + string(ev.Properties) + "\n\n")
	ocSID := ev.SessionID()
	h.mu.RLock()
	defer h.mu.RUnlock()
	if ocSID != "" {
		if cid, ok := h.byOC[ocSID]; ok {
			h.pushLocked(cid, frame)
			return
		}
	}
	for cid := range h.subs { // 广播（server.connected / file.edited 等无 sessionID 事件）
		h.pushLocked(cid, frame)
	}
}

func (h *ChatHandler) pushLocked(cid string, frame []byte) {
	for ch := range h.subs[cid] {
		select {
		case ch <- frame:
		default: // 订阅者消费不及时，丢帧保主循环
		}
	}
}

// writeChatErr 把 opencode 客户端错误映射为 envelope（不可达/异常 → 502）。
func writeChatErr(w http.ResponseWriter, err error) {
	if oe, ok := err.(*opencode.Error); ok {
		writeErr(w, http.StatusBadGateway, codeBadGateway, fmt.Sprintf("opencode %d: %s", oe.Status, oe.Body))
		return
	}
	writeErr(w, http.StatusBadGateway, codeBadGateway, err.Error())
}
