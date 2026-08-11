# Viewer P0 缺口功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 viewer 补齐 Issue/Markup、Model Tree 搜索/过滤/isolate、Property Inspector 搜索/复制、Hide/Isolate/X-Ray 工具栏四项功能（spec: `docs/superpowers/specs/2026-07-28-viewer-p0-gaps-design.md`）。

**Architecture:** Go server 新增 `internal/issue` 包（`Store` 接口 + 文件实现，后期可平移 PostgreSQL）与 4 条 issues REST 路由；前端弃用 TreeViewPlugin 改自建 React 树，zustand 扩展可见性状态，新增 IssuePanel 底部抽屉。

**Tech Stack:** Go 1.26（stdlib only）、React 19 + TS + Vite + zustand 5、@xeokit/xeokit-sdk、vitest 4 + @testing-library/react。

## Global Constraints

- Go 端**零第三方依赖**（stdlib-only），沿用 `{code,message,data}` 信封（code=0 成功；错误码 40001/40002/40400/50000）、CORS 中间件、tmp+rename 原子写
- model id 正则 `^m_[0-9a-f]{16}$`；issue id 正则 `^i_[0-9a-f]{12}$`
- 截图仅 PNG、≤5MB；multipart 请求整体 ≤6MB
- Issue status 枚举：`"open" | "checking" | "resolved"`
- 前端 TS 文件 ≤500 行，import 用 `@` alias，纯 CSS（无 Tailwind），UI 文案中文
- 不改动 converter、上传/转换队列、模型列表 API、`model.json` 结构
- 测试命令：server `go test ./...`（工作目录 `server`）；web `npm test`（工作目录 `web`，即 `vitest run`）；e2e `bash scripts/smoke.sh`（需 server 运行于 :8090）
- git 仓库根为 `AI_IFC/`，所有提交在此仓库内；commit message 风格参照历史（如 `feat(viewer): ...`、`fix:...`）

---

### Task 1: server `internal/issue` 包 —— 类型 + FileStore List/Create

**Files:**
- Create: `server/internal/issue/issue.go`
- Test: `server/internal/issue/issue_test.go`

**Interfaces:**
- Produces（后续任务依赖）:
  - `type Issue struct{ ID, EntityID, EntityName, EntityType, Title, Comment, Status, Screenshot string; Camera Camera; CreatedAt, UpdatedAt time.Time }`（json tag 全小驼峰：`id, entityId, entityName, entityType, title, comment, status, screenshot, camera, createdAt, updatedAt`）
  - `type Camera struct{ Eye, Look, Up [3]float64 }`（json: `eye, look, up`）
  - `type IssuePatch struct{ Title, Comment, Status *string }`（json: `title, comment, status`）
  - `type Store interface { List(modelID string) ([]*Issue, error); Create(modelID string, iss *Issue) (*Issue, error); Update(modelID, issueID string, patch IssuePatch) (*Issue, error); Delete(modelID, issueID string) error; SaveScreenshot(modelID, issueID string, png []byte) (string, error) }`
  - `func NewFileStore(dataDir string) *FileStore`
  - 错误：`ErrNotFound, ErrInvalidID, ErrInvalidStatus, ErrEmptyTitle`
  - 数据文件：`{dataDir}/models/{modelID}/issues.json`；截图：`{dataDir}/models/{modelID}/issues/{issueID}.png`

- [ ] **Step 1: 写失败测试**

`server/internal/issue/issue_test.go`:

```go
package issue

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func newTestStore(t *testing.T) (*FileStore, string) {
	t.Helper()
	dir := t.TempDir()
	modelID := "m_0123456789abcdef"
	if err := os.MkdirAll(filepath.Join(dir, "models", modelID), 0o755); err != nil {
		t.Fatal(err)
	}
	return NewFileStore(dir), modelID
}

func TestCreateAndList(t *testing.T) {
	fs, modelID := newTestStore(t)
	created, err := fs.Create(modelID, &Issue{
		EntityID: "3a82-xxxx", EntityName: "Wall", EntityType: "IfcWall",
		Title:   "Door width incorrect",
		Comment: "check",
		Camera:  Camera{Eye: [3]float64{1, 2, 3}, Look: [3]float64{0, 0, 0}, Up: [3]float64{0, 0, 1}},
	})
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if created.ID == "" || len(created.ID) != 14 || created.ID[:2] != "i_" {
		t.Fatalf("bad id: %q", created.ID)
	}
	if created.Status != "open" {
		t.Fatalf("default status = %q, want open", created.Status)
	}
	if created.CreatedAt.IsZero() || created.UpdatedAt.IsZero() {
		t.Fatal("timestamps not set")
	}
	list, err := fs.List(modelID)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if len(list) != 1 || list[0].ID != created.ID {
		t.Fatalf("list = %+v", list)
	}
}

func TestListEmptyWhenNoFile(t *testing.T) {
	fs, modelID := newTestStore(t)
	list, err := fs.List(modelID)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if len(list) != 0 {
		t.Fatalf("list = %+v, want empty", list)
	}
}

func TestCreateEmptyTitle(t *testing.T) {
	fs, modelID := newTestStore(t)
	if _, err := fs.Create(modelID, &Issue{Title: "  "}); !errors.Is(err, ErrEmptyTitle) {
		t.Fatalf("err = %v, want ErrEmptyTitle", err)
	}
}

func TestCreateInvalidStatus(t *testing.T) {
	fs, modelID := newTestStore(t)
	if _, err := fs.Create(modelID, &Issue{Title: "x", Status: "bogus"}); !errors.Is(err, ErrInvalidStatus) {
		t.Fatalf("err = %v, want ErrInvalidStatus", err)
	}
}
```

- [ ] **Step 2: 运行确认失败**

Run: `cd server && go test ./internal/issue/ -v`
Expected: FAIL（`internal/issue` 不存在，编译错误）

- [ ] **Step 3: 实现 `server/internal/issue/issue.go`**

```go
package issue

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"
)

var ErrNotFound = errors.New("issue not found")
var ErrInvalidID = errors.New("invalid issue id")
var ErrInvalidStatus = errors.New("invalid issue status")
var ErrEmptyTitle = errors.New("issue title is required")

var idPattern = regexp.MustCompile(`^i_[0-9a-f]{12}$`)

var validStatus = map[string]bool{"open": true, "checking": true, "resolved": true}

type Camera struct {
	Eye  [3]float64 `json:"eye"`
	Look [3]float64 `json:"look"`
	Up   [3]float64 `json:"up"`
}

type Issue struct {
	ID         string    `json:"id"`
	EntityID   string    `json:"entityId"`
	EntityName string    `json:"entityName"`
	EntityType string    `json:"entityType"`
	Title      string    `json:"title"`
	Comment    string    `json:"comment"`
	Status     string    `json:"status"`
	Camera     Camera    `json:"camera"`
	Screenshot string    `json:"screenshot"`
	CreatedAt  time.Time `json:"createdAt"`
	UpdatedAt  time.Time `json:"updatedAt"`
}

type IssuePatch struct {
	Title   *string `json:"title"`
	Comment *string `json:"comment"`
	Status  *string `json:"status"`
}

// Store 抽象后期可平移 PostgreSQL（新增 PgStore 实现即可，调用方零改动）。
type Store interface {
	List(modelID string) ([]*Issue, error)
	Create(modelID string, iss *Issue) (*Issue, error)
	Update(modelID, issueID string, patch IssuePatch) (*Issue, error)
	Delete(modelID, issueID string) error
	SaveScreenshot(modelID, issueID string, png []byte) (string, error)
}

// FileStore 假定 modelID 已被调用方校验（handler 先经 store.Store.Get 校验格式与存在性）。
type FileStore struct {
	DataDir string
	mu      sync.Mutex
}

func NewFileStore(dataDir string) *FileStore { return &FileStore{DataDir: dataDir} }

func (s *FileStore) issuesPath(modelID string) string {
	return filepath.Join(s.DataDir, "models", modelID, "issues.json")
}

func (s *FileStore) issuesDir(modelID string) string {
	return filepath.Join(s.DataDir, "models", modelID, "issues")
}

func newID() string {
	b := make([]byte, 6)
	_, _ = rand.Read(b)
	return "i_" + hex.EncodeToString(b)
}

func (s *FileStore) readAll(modelID string) ([]*Issue, error) {
	data, err := os.ReadFile(s.issuesPath(modelID))
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var out []*Issue
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (s *FileStore) writeAll(modelID string, issues []*Issue) error {
	data, err := json.MarshalIndent(issues, "", "  ")
	if err != nil {
		return err
	}
	tmp := s.issuesPath(modelID) + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, s.issuesPath(modelID))
}

func (s *FileStore) List(modelID string) ([]*Issue, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	issues, err := s.readAll(modelID)
	if err != nil {
		return nil, err
	}
	sort.Slice(issues, func(i, j int) bool { return issues[i].CreatedAt.After(issues[j].CreatedAt) })
	return issues, nil
}

func (s *FileStore) Create(modelID string, iss *Issue) (*Issue, error) {
	iss.Title = strings.TrimSpace(iss.Title)
	if iss.Title == "" {
		return nil, ErrEmptyTitle
	}
	if iss.Status == "" {
		iss.Status = "open"
	}
	if !validStatus[iss.Status] {
		return nil, ErrInvalidStatus
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	issues, err := s.readAll(modelID)
	if err != nil {
		return nil, err
	}
	now := time.Now().UTC()
	iss.ID = newID()
	iss.CreatedAt = now
	iss.UpdatedAt = now
	iss.Screenshot = ""
	issues = append(issues, iss)
	if err := s.writeAll(modelID, issues); err != nil {
		return nil, err
	}
	return iss, nil
}
```

（`Update/Delete/SaveScreenshot` 在 Task 2 添加。）

- [ ] **Step 4: 运行确认通过**

Run: `cd server && go test ./internal/issue/ -v`
Expected: PASS（4 个测试）

- [ ] **Step 5: Commit**

```bash
cd AI_IFC && git add server/internal/issue/ && git commit -m "feat(viewer): issue 包类型与 FileStore List/Create"
```

---

### Task 2: server `internal/issue` —— Update/Delete/SaveScreenshot

**Files:**
- Modify: `server/internal/issue/issue.go`
- Test: `server/internal/issue/issue_test.go`

**Interfaces:**
- Consumes: Task 1 的 `FileStore`、`Issue`、`IssuePatch`、`readAll/writeAll`
- Produces: `(*FileStore).Update/Delete/SaveScreenshot`（Task 3 handler 依赖）

- [ ] **Step 1: 追加失败测试**

`issue_test.go` 追加：

```go
func TestUpdate(t *testing.T) {
	fs, modelID := newTestStore(t)
	created, err := fs.Create(modelID, &Issue{Title: "old"})
	if err != nil {
		t.Fatal(err)
	}
	status, title := "resolved", "new title"
	got, err := fs.Update(modelID, created.ID, IssuePatch{Title: &title, Status: &status})
	if err != nil {
		t.Fatalf("update: %v", err)
	}
	if got.Title != "new title" || got.Status != "resolved" {
		t.Fatalf("got %+v", got)
	}
	if !got.UpdatedAt.After(created.CreatedAt) && !got.UpdatedAt.Equal(created.CreatedAt) {
		t.Fatal("updatedAt not refreshed")
	}
	list, _ := fs.List(modelID)
	if list[0].Title != "new title" {
		t.Fatal("update not persisted")
	}
}

func TestUpdateNotFound(t *testing.T) {
	fs, modelID := newTestStore(t)
	status := "resolved"
	if _, err := fs.Update(modelID, "i_abcdef012345", IssuePatch{Status: &status}); !errors.Is(err, ErrNotFound) {
		t.Fatalf("err = %v, want ErrNotFound", err)
	}
}

func TestUpdateInvalidID(t *testing.T) {
	fs, modelID := newTestStore(t)
	status := "resolved"
	if _, err := fs.Update(modelID, "bad id", IssuePatch{Status: &status}); !errors.Is(err, ErrInvalidID) {
		t.Fatalf("err = %v, want ErrInvalidID", err)
	}
}

func TestUpdateInvalidStatus(t *testing.T) {
	fs, modelID := newTestStore(t)
	created, _ := fs.Create(modelID, &Issue{Title: "x"})
	status := "bogus"
	if _, err := fs.Update(modelID, created.ID, IssuePatch{Status: &status}); !errors.Is(err, ErrInvalidStatus) {
		t.Fatalf("err = %v, want ErrInvalidStatus", err)
	}
}

func TestDelete(t *testing.T) {
	fs, modelID := newTestStore(t)
	created, _ := fs.Create(modelID, &Issue{Title: "x"})
	if _, err := fs.SaveScreenshot(modelID, created.ID, []byte("fakepng")); err != nil {
		t.Fatal(err)
	}
	if err := fs.Delete(modelID, created.ID); err != nil {
		t.Fatalf("delete: %v", err)
	}
	list, _ := fs.List(modelID)
	if len(list) != 0 {
		t.Fatalf("list = %+v, want empty", list)
	}
	if _, err := os.Stat(filepath.Join(fs.issuesDir(modelID), created.ID+".png")); !errors.Is(err, os.ErrNotExist) {
		t.Fatal("screenshot file not removed")
	}
	if err := fs.Delete(modelID, created.ID); !errors.Is(err, ErrNotFound) {
		t.Fatalf("second delete err = %v, want ErrNotFound", err)
	}
}

func TestSaveScreenshot(t *testing.T) {
	fs, modelID := newTestStore(t)
	created, _ := fs.Create(modelID, &Issue{Title: "x"})
	rel, err := fs.SaveScreenshot(modelID, created.ID, []byte("fakepng"))
	if err != nil {
		t.Fatalf("save: %v", err)
	}
	want := "issues/" + created.ID + ".png"
	if rel != want {
		t.Fatalf("rel = %q, want %q", rel, want)
	}
	data, err := os.ReadFile(filepath.Join(fs.DataDir, "models", modelID, want))
	if err != nil || string(data) != "fakepng" {
		t.Fatalf("file: %v %q", err, data)
	}
	list, _ := fs.List(modelID)
	if list[0].Screenshot != want {
		t.Fatalf("record screenshot = %q", list[0].Screenshot)
	}
}
```

- [ ] **Step 2: 运行确认失败**

Run: `cd server && go test ./internal/issue/ -v`
Expected: FAIL（`Update`/`Delete`/`SaveScreenshot` 未定义）

- [ ] **Step 3: 实现（追加到 `issue.go`）**

```go
func (s *FileStore) Update(modelID, issueID string, patch IssuePatch) (*Issue, error) {
	if !idPattern.MatchString(issueID) {
		return nil, ErrInvalidID
	}
	if patch.Status != nil && !validStatus[*patch.Status] {
		return nil, ErrInvalidStatus
	}
	if patch.Title != nil {
		*patch.Title = strings.TrimSpace(*patch.Title)
		if *patch.Title == "" {
			return nil, ErrEmptyTitle
		}
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	issues, err := s.readAll(modelID)
	if err != nil {
		return nil, err
	}
	for _, iss := range issues {
		if iss.ID != issueID {
			continue
		}
		if patch.Title != nil {
			iss.Title = *patch.Title
		}
		if patch.Comment != nil {
			iss.Comment = *patch.Comment
		}
		if patch.Status != nil {
			iss.Status = *patch.Status
		}
		iss.UpdatedAt = time.Now().UTC()
		if err := s.writeAll(modelID, issues); err != nil {
			return nil, err
		}
		return iss, nil
	}
	return nil, ErrNotFound
}

func (s *FileStore) Delete(modelID, issueID string) error {
	if !idPattern.MatchString(issueID) {
		return ErrInvalidID
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	issues, err := s.readAll(modelID)
	if err != nil {
		return err
	}
	out := issues[:0]
	found := false
	for _, iss := range issues {
		if iss.ID == issueID {
			found = true
			continue
		}
		out = append(out, iss)
	}
	if !found {
		return ErrNotFound
	}
	if err := s.writeAll(modelID, out); err != nil {
		return err
	}
	_ = os.Remove(filepath.Join(s.issuesDir(modelID), issueID+".png"))
	return nil
}

func (s *FileStore) SaveScreenshot(modelID, issueID string, png []byte) (string, error) {
	if !idPattern.MatchString(issueID) {
		return "", ErrInvalidID
	}
	if err := os.MkdirAll(s.issuesDir(modelID), 0o755); err != nil {
		return "", err
	}
	rel := "issues/" + issueID + ".png"
	abs := filepath.Join(s.DataDir, "models", modelID, rel)
	tmp := abs + ".tmp"
	if err := os.WriteFile(tmp, png, 0o644); err != nil {
		return "", err
	}
	if err := os.Rename(tmp, abs); err != nil {
		return "", err
	}
	if _, err := s.Update(modelID, issueID, IssuePatch{}); err != nil {
		return "", err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	issues, err := s.readAll(modelID)
	if err != nil {
		return "", err
	}
	for _, iss := range issues {
		if iss.ID == issueID {
			iss.Screenshot = rel
			if err := s.writeAll(modelID, issues); err != nil {
				return "", err
			}
			return rel, nil
		}
	}
	return "", ErrNotFound
}
```

注意：`SaveScreenshot` 中调用 `Update(modelID, issueID, IssuePatch{})` 仅为校验存在性并刷新记录；若觉得冗余，可将存在性校验合并进后面的循环（实现时可简化，行为以测试为准）。

- [ ] **Step 4: 运行确认通过**

Run: `cd server && go test ./internal/issue/ -v`
Expected: PASS（10 个测试）

- [ ] **Step 5: Commit**

```bash
cd AI_IFC && git add server/internal/issue/ && git commit -m "feat(viewer): issue FileStore Update/Delete/SaveScreenshot"
```

---

### Task 3: server API 路由 + main.go 装配

**Files:**
- Modify: `server/internal/api/api.go`
- Modify: `server/internal/api/api_test.go`（NewHandler 调用点）
- Modify: `server/cmd/server/main.go:66`
- Modify: `server/cmd/server/main_test.go`（若含 NewHandler 调用，同步更新）
- Test: `server/internal/api/issues_test.go`（新文件）

**Interfaces:**
- Consumes: Task 1/2 的 `issue.Store`、`issue.Issue`、`issue.IssuePatch`、错误哨兵
- Produces: 4 条 REST 路由 + 截图静态路由（Task 10 前端调用）：
  - `GET /api/models/{id}/issues` → `data: Issue[]`
  - `POST /api/models/{id}/issues`（multipart：`issue`=JSON 字符串，可选 `screenshot`=PNG 文件）→ `data: Issue`
  - `PATCH /api/models/{id}/issues/{issueId}`（JSON body `IssuePatch`）→ `data: Issue`
  - `DELETE /api/models/{id}/issues/{issueId}` → `data: null`
  - `GET /models/{id}/issues/{file}`（file 必须匹配 `^i_[0-9a-f]{12}\.png$`）→ PNG 字节流

- [ ] **Step 1: 写失败测试 `server/internal/api/issues_test.go`**

先查看现有 `api_test.go` 的测试脚手架（如何构造 `store.Store`、`convert.Queue`、`httptest`），保持同一风格。测试文件：

```go
package api

import (
	"bytes"
	"encoding/json"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"testing"

	"ifcserver/internal/issue"
)

// newIssueTestServer 参照 api_test.go 现有脚手架构造 handler 与一个已存在的模型，
// 返回 (mux, modelID)。若 api_test.go 已有等价 helper 则复用，不要重复定义。
func createTestIssue(t *testing.T, mux http.Handler, modelID string) issue.Issue {
	t.Helper()
	var body bytes.Buffer
	w := multipart.NewWriter(&body)
	if err := w.WriteField("issue", `{"entityId":"e1","entityName":"Wall","entityType":"IfcWall","title":"t1","comment":"c","camera":{"eye":[1,2,3],"look":[0,0,0],"up":[0,0,1]}}`); err != nil {
		t.Fatal(err)
	}
	if err := w.Close(); err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest("POST", "/api/models/"+modelID+"/issues", &body)
	req.Header.Set("Content-Type", w.FormDataContentType())
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("create status = %d body = %s", rec.Code, rec.Body)
	}
	var env envelope
	if err := json.Unmarshal(rec.Body.Bytes(), &env); err != nil {
		t.Fatal(err)
	}
	raw, _ := json.Marshal(env.Data)
	var iss issue.Issue
	if err := json.Unmarshal(raw, &iss); err != nil {
		t.Fatal(err)
	}
	if iss.ID == "" || iss.Status != "open" {
		t.Fatalf("issue = %+v", iss)
	}
	return iss
}

func TestIssueCRUD(t *testing.T) {
	mux, modelID := newIssueTestServer(t)
	iss := createTestIssue(t, mux, modelID)

	// list
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/models/"+modelID+"/issues", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("list status = %d", rec.Code)
	}

	// patch status
	patch := bytes.NewBufferString(`{"status":"resolved"}`)
	req := httptest.NewRequest("PATCH", "/api/models/"+modelID+"/issues/"+iss.ID, patch)
	req.Header.Set("Content-Type", "application/json")
	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("patch status = %d body = %s", rec.Code, rec.Body)
	}

	// delete
	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("DELETE", "/api/models/"+modelID+"/issues/"+iss.ID, nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("delete status = %d", rec.Code)
	}
}

func TestIssueErrors(t *testing.T) {
	mux, modelID := newIssueTestServer(t)

	// model 不存在
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/models/m_0000000000000000/issues", nil))
	if rec.Code != http.StatusNotFound {
		t.Fatalf("want 404, got %d", rec.Code)
	}

	// 空 title
	var body bytes.Buffer
	w := multipart.NewWriter(&body)
	_ = w.WriteField("issue", `{"entityId":"e1","title":"  "}`)
	_ = w.Close()
	req := httptest.NewRequest("POST", "/api/models/"+modelID+"/issues", &body)
	req.Header.Set("Content-Type", w.FormDataContentType())
	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("empty title: want 400, got %d", rec.Code)
	}

	// 非法 status
	iss := createTestIssue(t, mux, modelID)
	req = httptest.NewRequest("PATCH", "/api/models/"+modelID+"/issues/"+iss.ID, bytes.NewBufferString(`{"status":"bogus"}`))
	req.Header.Set("Content-Type", "application/json")
	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("bad status: want 400, got %d", rec.Code)
	}

	// issue 不存在
	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("DELETE", "/api/models/"+modelID+"/issues/i_abcdef012345", nil))
	if rec.Code != http.StatusNotFound {
		t.Fatalf("want 404, got %d", rec.Code)
	}
}

func TestIssueScreenshot(t *testing.T) {
	mux, modelID := newIssueTestServer(t)
	png := append([]byte{0x89, 'P', 'N', 'G', '\r', '\n', 0x1a, '\n'}, make([]byte, 32)...)
	var body bytes.Buffer
	w := multipart.NewWriter(&body)
	_ = w.WriteField("issue", `{"entityId":"e1","title":"with shot","camera":{"eye":[0,0,0],"look":[0,0,0],"up":[0,0,1]}}`)
	fw, err := w.CreateFormFile("screenshot", "screenshot.png")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := fw.Write(png); err != nil {
		t.Fatal(err)
	}
	_ = w.Close()
	req := httptest.NewRequest("POST", "/api/models/"+modelID+"/issues", &body)
	req.Header.Set("Content-Type", w.FormDataContentType())
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("create with screenshot: %d %s", rec.Code, rec.Body)
	}
	var env envelope
	_ = json.Unmarshal(rec.Body.Bytes(), &env)
	raw, _ := json.Marshal(env.Data)
	var iss issue.Issue
	_ = json.Unmarshal(raw, &iss)
	if iss.Screenshot == "" {
		t.Fatal("screenshot path empty")
	}
	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("GET", "/models/"+modelID+"/"+iss.Screenshot, nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("serve screenshot: %d", rec.Code)
	}
}
```

同时修改 `api_test.go`（和 `main_test.go`，若有）中所有 `NewHandler(st, q, ...)` 调用为 `NewHandler(st, q, iss, ...)`，`iss := issue.NewFileStore(tmpDir)`。

- [ ] **Step 2: 运行确认失败**

Run: `cd server && go test ./internal/api/ -v`
Expected: FAIL（编译错误：`NewHandler` 参数不匹配 / 路由不存在 404）

- [ ] **Step 3: 实现 `api.go` 修改**

顶部 import 增加 `"io"`、`"regexp"`、`"ifcserver/internal/issue"`。handler 结构体与构造函数：

```go
type handler struct {
	st        *store.Store
	q         *convert.Queue
	iss       issue.Store
	maxUpload int64
}

func NewHandler(st *store.Store, q *convert.Queue, iss issue.Store, maxUploadBytes int64) http.Handler {
	h := &handler{st: st, q: q, iss: iss, maxUpload: maxUploadBytes}
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/models", h.upload)
	mux.HandleFunc("GET /api/models", h.list)
	mux.HandleFunc("GET /api/models/{id}", h.get)
	mux.HandleFunc("POST /api/models/{id}/retry", h.retry)
	mux.HandleFunc("DELETE /api/models/{id}", h.delete)
	mux.HandleFunc("GET /api/models/{id}/download", h.download)
	mux.HandleFunc("GET /models/{id}/model.xkt", h.serveModelFile("model.xkt"))
	mux.HandleFunc("GET /models/{id}/metadata.json", h.serveModelFile("metadata.json"))
	mux.HandleFunc("GET /api/models/{id}/issues", h.listIssues)
	mux.HandleFunc("POST /api/models/{id}/issues", h.createIssue)
	mux.HandleFunc("PATCH /api/models/{id}/issues/{issueId}", h.updateIssue)
	mux.HandleFunc("DELETE /api/models/{id}/issues/{issueId}", h.deleteIssue)
	mux.HandleFunc("GET /models/{id}/issues/{file}", h.serveIssueFile)
	return cors(mux)
}
```

CORS 中间件 `Access-Control-Allow-Methods` 改为 `"GET, POST, PATCH, DELETE, OPTIONS"`。

常量与新增 handler：

```go
const maxIssueUpload = 6 << 20  // 6MB
const maxScreenshot = 5 << 20   // 5MB

var issueFilePattern = regexp.MustCompile(`^i_[0-9a-f]{12}\.png$`)

func (h *handler) listIssues(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	issues, err := h.iss.List(m.ID)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	if issues == nil {
		issues = []*issue.Issue{}
	}
	writeJSON(w, issues)
}

func (h *handler) createIssue(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	r.Body = http.MaxBytesReader(w, r.Body, maxIssueUpload)
	if err := r.ParseMultipartForm(maxIssueUpload); err != nil {
		writeErr(w, http.StatusBadRequest, codeTooLarge, "request exceeds size limit")
		return
	}
	raw := r.FormValue("issue")
	if raw == "" {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "missing issue field")
		return
	}
	var in issue.Issue
	if err := json.Unmarshal([]byte(raw), &in); err != nil {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "invalid issue json")
		return
	}
	var png []byte
	if file, _, err := r.FormFile("screenshot"); err == nil {
		defer file.Close()
		data, err := io.ReadAll(io.LimitReader(file, maxScreenshot+1))
		if err != nil || len(data) > maxScreenshot {
			writeErr(w, http.StatusBadRequest, codeTooLarge, "screenshot exceeds 5MB")
			return
		}
		if http.DetectContentType(data) != "image/png" {
			writeErr(w, http.StatusBadRequest, codeInvalidType, "screenshot must be png")
			return
		}
		png = data
	}
	created, err := h.iss.Create(m.ID, &in)
	if errors.Is(err, issue.ErrEmptyTitle) || errors.Is(err, issue.ErrInvalidStatus) {
		writeErr(w, http.StatusBadRequest, codeInvalidType, err.Error())
		return
	}
	if err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	if png != nil {
		if _, err := h.iss.SaveScreenshot(m.ID, created.ID, png); err != nil {
			writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
			return
		}
		created.Screenshot = "issues/" + created.ID + ".png"
	}
	writeJSON(w, created)
}

func (h *handler) updateIssue(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	var patch issue.IssuePatch
	if err := json.NewDecoder(r.Body).Decode(&patch); err != nil {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "invalid json body")
		return
	}
	got, err := h.iss.Update(m.ID, r.PathValue("issueId"), patch)
	if errors.Is(err, issue.ErrNotFound) || errors.Is(err, issue.ErrInvalidID) {
		writeErr(w, http.StatusNotFound, codeNotFound, "issue not found")
		return
	}
	if errors.Is(err, issue.ErrInvalidStatus) || errors.Is(err, issue.ErrEmptyTitle) {
		writeErr(w, http.StatusBadRequest, codeInvalidType, err.Error())
		return
	}
	if err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	writeJSON(w, got)
}

func (h *handler) deleteIssue(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	if err := h.iss.Delete(m.ID, r.PathValue("issueId")); err != nil {
		if errors.Is(err, issue.ErrNotFound) || errors.Is(err, issue.ErrInvalidID) {
			writeErr(w, http.StatusNotFound, codeNotFound, "issue not found")
			return
		}
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	writeJSON(w, nil)
}

func (h *handler) serveIssueFile(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	file := r.PathValue("file")
	if !issueFilePattern.MatchString(file) {
		writeErr(w, http.StatusNotFound, codeNotFound, "file not found")
		return
	}
	http.ServeFile(w, r, filepath.Join(h.st.ModelDir(m.ID), "issues", file))
}
```

`main.go:66` 改为：

```go
iss := issue.NewFileStore(cfg.DataDir)
handler := api.NewHandler(st, q, iss, cfg.MaxUploadMB<<20)
```

（import 增加 `"ifcserver/internal/issue"`。）

- [ ] **Step 4: 运行确认通过**

Run: `cd server && go test ./... && go vet ./...`
Expected: 全部 PASS，vet 无输出

- [ ] **Step 5: Commit**

```bash
cd AI_IFC && git add server/ && git commit -m "feat(viewer): issues REST API（CRUD + 截图）与 main 装配"
```

---

### Task 4: web API 类型与 client 扩展

**Files:**
- Modify: `web/src/api/types.ts`
- Modify: `web/src/api/client.ts`
- Test: `web/src/api/client.test.ts`（追加）

**Interfaces:**
- Produces（Task 10 依赖）:
  - `interface IssueCamera { eye: [number,number,number]; look: [number,number,number]; up: [number,number,number] }`
  - `type IssueStatus = "open" | "checking" | "resolved"`
  - `interface Issue { id; entityId; entityName; entityType; title; comment; status: IssueStatus; camera: IssueCamera; screenshot; createdAt; updatedAt }`
  - `interface NewIssue { entityId; entityName; entityType; title; comment; camera: IssueCamera }`
  - `listIssues(modelId): Promise<Issue[]>`
  - `createIssue(modelId, issue: NewIssue, screenshot: Blob | null): Promise<Issue>`
  - `updateIssue(modelId, issueId, patch: Partial<Pick<Issue,"title"|"comment"|"status">>): Promise<Issue>`
  - `deleteIssue(modelId, issueId): Promise<null>`
  - `issueAssetUrl(modelId, issue: Issue): string`

- [ ] **Step 1: 写失败测试（`client.test.ts` 追加，参照现有 5 个测试的 fetch mock 风格）**

```ts
import { listIssues, createIssue, updateIssue, deleteIssue } from "./client";

const sampleIssue = {
  id: "i_abcdef012345", entityId: "e1", entityName: "Wall", entityType: "IfcWall",
  title: "t", comment: "", status: "open",
  camera: { eye: [1, 2, 3], look: [0, 0, 0], up: [0, 0, 1] },
  screenshot: "", createdAt: "2026-07-28T00:00:00Z", updatedAt: "2026-07-28T00:00:00Z",
};

describe("issue api", () => {
  it("listIssues unwraps envelope", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(
      JSON.stringify({ code: 0, message: "ok", data: [sampleIssue] }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    )));
    const issues = await listIssues("m_0123456789abcdef");
    expect(issues).toHaveLength(1);
    expect(issues[0].id).toBe("i_abcdef012345");
    vi.unstubAllGlobals();
  });

  it("createIssue posts multipart with issue json and screenshot", async () => {
    const spy = vi.fn(async (_url: string, init?: RequestInit) => {
      const fd = init?.body as FormData;
      expect(JSON.parse(fd.get("issue") as string).title).toBe("t");
      expect(fd.get("screenshot")).toBeTruthy();
      return new Response(JSON.stringify({ code: 0, message: "ok", data: sampleIssue }),
        { status: 200, headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", spy);
    await createIssue("m_0123456789abcdef", {
      entityId: "e1", entityName: "Wall", entityType: "IfcWall", title: "t", comment: "",
      camera: { eye: [1, 2, 3], look: [0, 0, 0], up: [0, 0, 1] },
    }, new Blob(["x"], { type: "image/png" }));
    expect(spy).toHaveBeenCalledOnce();
    vi.unstubAllGlobals();
  });

  it("updateIssue patches status, deleteIssue deletes", async () => {
    const spy = vi.fn(async () => new Response(
      JSON.stringify({ code: 0, message: "ok", data: sampleIssue }),
      { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", spy);
    await updateIssue("m_0123456789abcdef", "i_abcdef012345", { status: "resolved" });
    await deleteIssue("m_0123456789abcdef", "i_abcdef012345");
    expect(spy).toHaveBeenCalledTimes(2);
    const [patchUrl, patchInit] = spy.mock.calls[0];
    expect(patchInit?.method).toBe("PATCH");
    expect(patchUrl).toContain("/api/models/m_0123456789abcdef/issues/i_abcdef012345");
    const [, delInit] = spy.mock.calls[1];
    expect(delInit?.method).toBe("DELETE");
    vi.unstubAllGlobals();
  });
});
```

（若 `client.test.ts` 已有 fetch mock helper，复用其风格；`vi` 从 `vitest` import。）

- [ ] **Step 2: 运行确认失败**

Run: `cd web && npx vitest run src/api/client.test.ts`
Expected: FAIL（`listIssues` 等未导出）

- [ ] **Step 3: 实现**

`types.ts` 追加：

```ts
export interface IssueCamera {
  eye: [number, number, number];
  look: [number, number, number];
  up: [number, number, number];
}

export type IssueStatus = "open" | "checking" | "resolved";

export interface Issue {
  id: string;
  entityId: string;
  entityName: string;
  entityType: string;
  title: string;
  comment: string;
  status: IssueStatus;
  camera: IssueCamera;
  screenshot: string;
  createdAt: string;
  updatedAt: string;
}

export interface NewIssue {
  entityId: string;
  entityName: string;
  entityType: string;
  title: string;
  comment: string;
  camera: IssueCamera;
}
```

`client.ts` 追加（import 处加 `Issue, NewIssue, IssueStatus` 类型）：

```ts
export function listIssues(modelId: string) {
  return request<Issue[]>(`/api/models/${modelId}/issues`);
}
export function createIssue(modelId: string, issue: NewIssue, screenshot: Blob | null) {
  const fd = new FormData();
  fd.append("issue", JSON.stringify(issue));
  if (screenshot) fd.append("screenshot", screenshot, "screenshot.png");
  return request<Issue>(`/api/models/${modelId}/issues`, { method: "POST", body: fd });
}
export function updateIssue(
  modelId: string,
  issueId: string,
  patch: Partial<Pick<Issue, "title" | "comment" | "status">>
) {
  return request<Issue>(`/api/models/${modelId}/issues/${issueId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}
export function deleteIssue(modelId: string, issueId: string) {
  return request<null>(`/api/models/${modelId}/issues/${issueId}`, { method: "DELETE" });
}
export const issueAssetUrl = (modelId: string, issue: Issue) => `/models/${modelId}/${issue.screenshot}`;
```

- [ ] **Step 4: 运行确认通过**

Run: `cd web && npx vitest run src/api/client.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd AI_IFC && git add web/src/api/ && git commit -m "feat(viewer): web issue API 类型与 client"
```

---

### Task 5: web `tree-utils.ts` 纯函数

**Files:**
- Create: `web/src/viewer/tree-utils.ts`
- Test: `web/src/viewer/tree-utils.test.ts`

**Interfaces:**
- Produces（Task 7 依赖）:
  - `interface MetaObjectLite { id: string; name: string; type: string; parent: string | null }`
  - `interface TreeNode { id: string; name: string; type: string; children: TreeNode[] }`
  - `buildTree(objects: MetaObjectLite[]): TreeNode[]`
  - `typeCounts(objects: MetaObjectLite[]): [string, number][]`（按数量降序）
  - `filterTree(nodes: TreeNode[], query: string, allowedTypes: ReadonlySet<string>): TreeNode[]`（allowedTypes 为空集 = 不过滤；保留命中节点及其祖先）

- [ ] **Step 1: 写失败测试 `tree-utils.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import { buildTree, filterTree, typeCounts, type MetaObjectLite } from "./tree-utils";

const objects: MetaObjectLite[] = [
  { id: "p", name: "Project", type: "IfcProject", parent: null },
  { id: "s", name: "Site", type: "IfcSite", parent: "p" },
  { id: "b", name: "Building", type: "IfcBuilding", parent: "s" },
  { id: "st1", name: "L1", type: "IfcBuildingStorey", parent: "b" },
  { id: "w1", name: "Wall A", type: "IfcWall", parent: "st1" },
  { id: "w2", name: "Wall B", type: "IfcWall", parent: "st1" },
  { id: "d1", name: "Door A", type: "IfcDoor", parent: "st1" },
];

describe("buildTree", () => {
  it("assembles hierarchy from parent links", () => {
    const tree = buildTree(objects);
    expect(tree).toHaveLength(1);
    const storey = tree[0].children[0].children[0].children[0];
    expect(storey.id).toBe("st1");
    expect(storey.children.map((c) => c.id)).toEqual(["w1", "w2", "d1"]);
  });
});

describe("typeCounts", () => {
  it("counts by type, sorted desc", () => {
    const counts = typeCounts(objects);
    expect(counts[0]).toEqual(["IfcWall", 2]);
    expect(counts.find(([t]) => t === "IfcDoor")).toEqual(["IfcDoor", 1]);
  });
});

describe("filterTree", () => {
  const tree = buildTree(objects);

  it("matches by name, keeping ancestors", () => {
    const out = filterTree(tree, "door a", new Set());
    const storey = out[0].children[0].children[0].children[0];
    expect(storey.children.map((c) => c.id)).toEqual(["d1"]);
  });

  it("matches by type case-insensitively", () => {
    const out = filterTree(tree, "ifcwall", new Set());
    const storey = out[0].children[0].children[0].children[0];
    expect(storey.children.map((c) => c.id)).toEqual(["w1", "w2"]);
  });

  it("filters by allowed types, keeping ancestors", () => {
    const out = filterTree(tree, "", new Set(["IfcDoor"]));
    const storey = out[0].children[0].children[0].children[0];
    expect(storey.children.map((c) => c.id)).toEqual(["d1"]);
  });

  it("empty query and empty types returns full tree", () => {
    expect(filterTree(tree, "", new Set())).toEqual(tree);
  });

  it("no match returns empty", () => {
    expect(filterTree(tree, "nonexistent", new Set())).toEqual([]);
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd web && npx vitest run src/viewer/tree-utils.test.ts`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 `tree-utils.ts`**

```ts
export interface MetaObjectLite {
  id: string;
  name: string;
  type: string;
  parent: string | null;
}

export interface TreeNode {
  id: string;
  name: string;
  type: string;
  children: TreeNode[];
}

export function buildTree(objects: MetaObjectLite[]): TreeNode[] {
  const nodes = new Map<string, TreeNode>();
  for (const o of objects) {
    nodes.set(o.id, { id: o.id, name: o.name, type: o.type, children: [] });
  }
  const roots: TreeNode[] = [];
  for (const o of objects) {
    const node = nodes.get(o.id)!;
    const parent = o.parent ? nodes.get(o.parent) : undefined;
    if (parent) {
      parent.children.push(node);
    } else {
      roots.push(node);
    }
  }
  return roots;
}

export function typeCounts(objects: MetaObjectLite[]): [string, number][] {
  const counts = new Map<string, number>();
  for (const o of objects) {
    counts.set(o.type, (counts.get(o.type) ?? 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1]);
}

function nodeMatches(node: TreeNode, query: string, allowedTypes: ReadonlySet<string>): boolean {
  const q = query.trim().toLowerCase();
  const queryOk =
    q === "" ||
    node.name.toLowerCase().includes(q) ||
    node.type.toLowerCase().includes(q);
  const typeOk = allowedTypes.size === 0 || allowedTypes.has(node.type);
  return queryOk && typeOk;
}

export function filterTree(
  nodes: TreeNode[],
  query: string,
  allowedTypes: ReadonlySet<string>
): TreeNode[] {
  const out: TreeNode[] = [];
  for (const node of nodes) {
    const children = filterTree(node.children, query, allowedTypes);
    if (nodeMatches(node, query, allowedTypes) || children.length > 0) {
      out.push(children.length > 0 ? { ...node, children } : node);
    }
  }
  return out;
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd web && npx vitest run src/viewer/tree-utils.test.ts`
Expected: PASS（7 个测试）

- [ ] **Step 5: Commit**

```bash
cd AI_IFC && git add web/src/viewer/tree-utils.* && git commit -m "feat(viewer): tree 构建/过滤/统计纯函数"
```

---

### Task 6: zustand store 可见性状态扩展

**Files:**
- Modify: `web/src/viewer/store.ts`
- Test: `web/src/viewer/store.test.ts`（追加）

**Interfaces:**
- Produces（Task 7/8/10 依赖）: store 新增字段与 action：
  - `hiddenIds: string[]`、`isolateId: string | null`、`xray: boolean`
  - `toggleHidden(id: string)`、`isolate(id: string | null)`、`setXray(v: boolean)`、`resetVisibility()`

- [ ] **Step 1: 追加失败测试（`store.test.ts`）**

```ts
describe("visibility", () => {
  beforeEach(() => {
    useViewerStore.getState().resetVisibility();
  });

  it("toggleHidden adds and removes ids", () => {
    const s = useViewerStore.getState();
    s.toggleHidden("a");
    expect(useViewerStore.getState().hiddenIds).toEqual(["a"]);
    useViewerStore.getState().toggleHidden("a");
    expect(useViewerStore.getState().hiddenIds).toEqual([]);
  });

  it("isolate sets and clears isolateId", () => {
    useViewerStore.getState().isolate("a");
    expect(useViewerStore.getState().isolateId).toBe("a");
    useViewerStore.getState().isolate(null);
    expect(useViewerStore.getState().isolateId).toBeNull();
  });

  it("resetVisibility clears hidden/isolate/xray", () => {
    const s = useViewerStore.getState();
    s.toggleHidden("a");
    s.isolate("b");
    s.setXray(true);
    useViewerStore.getState().resetVisibility();
    const after = useViewerStore.getState();
    expect(after.hiddenIds).toEqual([]);
    expect(after.isolateId).toBeNull();
    expect(after.xray).toBe(false);
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd web && npx vitest run src/viewer/store.test.ts`
Expected: FAIL（`toggleHidden` 等不存在）

- [ ] **Step 3: 实现 `store.ts`（全量替换）**

```ts
import { create } from "zustand";

export type ViewerTool = "select" | "measure";

interface ViewerState {
  selectedId: string | null;
  tool: ViewerTool;
  hiddenIds: string[];
  isolateId: string | null;
  xray: boolean;
  setSelected: (id: string | null) => void;
  setTool: (tool: ViewerTool) => void;
  toggleHidden: (id: string) => void;
  isolate: (id: string | null) => void;
  setXray: (v: boolean) => void;
  resetVisibility: () => void;
}

export const useViewerStore = create<ViewerState>((set) => ({
  selectedId: null,
  tool: "select",
  hiddenIds: [],
  isolateId: null,
  xray: false,
  setSelected: (id) => set({ selectedId: id }),
  setTool: (tool) => set({ tool }),
  toggleHidden: (id) =>
    set((s) => ({
      hiddenIds: s.hiddenIds.includes(id)
        ? s.hiddenIds.filter((x) => x !== id)
        : [...s.hiddenIds, id],
    })),
  isolate: (id) => set({ isolateId: id }),
  setXray: (v) => set({ xray: v }),
  resetVisibility: () => set({ hiddenIds: [], isolateId: null, xray: false }),
}));
```

- [ ] **Step 4: 运行确认通过（含既有测试回归）**

Run: `cd web && npx vitest run src/viewer/store.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd AI_IFC && git add web/src/viewer/store.* && git commit -m "feat(viewer): store 可见性状态（hidden/isolate/xray）"
```

---

### Task 7: ModelTreePanel 重写（自建 React 树 + 搜索 + 类型过滤 + hide）

**Files:**
- Modify: `web/src/viewer/ModelTreePanel.tsx`（全量重写）
- Modify: `web/src/viewer/tree.css`（替换为新树的样式，删除 `.xeokit-tree-view` 相关）
- Test: `web/src/viewer/ModelTreePanel.test.tsx`（新文件）

**Interfaces:**
- Consumes: Task 5 `buildTree/filterTree/typeCounts/MetaObjectLite`；Task 6 store `selectedId/setSelected/hiddenIds/toggleHidden`；`useViewer()` 的 `ctx.metaModel.metaObjects`、`ctx.viewer.cameraFlight.flyTo`
- Produces: 默认导出不变 `export function ModelTreePanel()`（ViewerPage 无需改动）

- [ ] **Step 1: 写失败测试 `ModelTreePanel.test.tsx`**

```tsx
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";

const mockCtx: { current: unknown } = { current: null };
vi.mock("./ViewerContext", () => ({ useViewer: () => mockCtx.current }));

import { ModelTreePanel } from "./ModelTreePanel";
import { useViewerStore } from "./store";

afterEach(cleanup);

const metaObjects = {
  p: { id: "p", name: "Project", type: "IfcProject", parent: null, propertySets: [] },
  st: { id: "st", name: "L1", type: "IfcBuildingStorey", parent: "p", propertySets: [] },
  w1: { id: "w1", name: "Wall A", type: "IfcWall", parent: "st", propertySets: [] },
  d1: { id: "d1", name: "Door A", type: "IfcDoor", parent: "st", propertySets: [] },
};

function setup() {
  mockCtx.current = {
    viewer: { cameraFlight: { flyTo: vi.fn() } },
    metaModel: { metaObjects },
  };
  useViewerStore.setState({
    selectedId: null, tool: "select", hiddenIds: [], isolateId: null, xray: false,
  });
}

describe("ModelTreePanel", () => {
  beforeEach(setup);

  it("renders tree nodes", () => {
    render(<ModelTreePanel />);
    expect(screen.getByText("Project")).toBeTruthy();
    expect(screen.getByText("Wall A")).toBeTruthy();
  });

  it("search filters nodes by name", () => {
    render(<ModelTreePanel />);
    fireEvent.change(screen.getByPlaceholderText("搜索名称或类型"), {
      target: { value: "door" },
    });
    expect(screen.getByText("Door A")).toBeTruthy();
    expect(screen.queryByText("Wall A")).toBeNull();
  });

  it("type filter shows only selected types", () => {
    render(<ModelTreePanel />);
    fireEvent.click(screen.getByLabelText("IfcDoor"));
    expect(screen.getByText("Door A")).toBeTruthy();
    expect(screen.queryByText("Wall A")).toBeNull();
  });

  it("hide button toggles hiddenIds in store", () => {
    render(<ModelTreePanel />);
    const row = screen.getByText("Wall A").closest("li")!;
    fireEvent.click(row.querySelector("button.tree-hide-btn")!);
    expect(useViewerStore.getState().hiddenIds).toEqual(["w1"]);
  });

  it("clicking node title selects and flies to entity", () => {
    render(<ModelTreePanel />);
    fireEvent.click(screen.getByText("Wall A"));
    expect(useViewerStore.getState().selectedId).toBe("w1");
    expect((mockCtx.current as { viewer: { cameraFlight: { flyTo: unknown } } }).viewer.cameraFlight.flyTo).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd web && npx vitest run src/viewer/ModelTreePanel.test.tsx`
Expected: FAIL（搜索框 / `tree-hide-btn` 不存在）

- [ ] **Step 3: 实现 `ModelTreePanel.tsx`（全量替换，不再 import TreeViewPlugin）**

```tsx
import { useEffect, useMemo, useState } from "react";
import type { MetaObject } from "@xeokit/xeokit-sdk";
import { useViewer } from "./ViewerContext";
import { useViewerStore } from "./store";
import { buildTree, filterTree, typeCounts, type MetaObjectLite, type TreeNode } from "./tree-utils";
import "./tree.css";

export function ModelTreePanel() {
  const ctx = useViewer();
  const selectedId = useViewerStore((s) => s.selectedId);
  const setSelected = useViewerStore((s) => s.setSelected);
  const hiddenIds = useViewerStore((s) => s.hiddenIds);
  const toggleHidden = useViewerStore((s) => s.toggleHidden);

  const [query, setQuery] = useState("");
  const [activeTypes, setActiveTypes] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const objects = useMemo<MetaObjectLite[]>(() => {
    if (!ctx?.metaModel) return [];
    const rec = ctx.metaModel.metaObjects as unknown as Record<string, MetaObject>;
    return Object.values(rec).map((o) => ({
      id: o.id,
      name: o.name ?? "",
      type: o.type,
      parent: (o as unknown as { parent?: string | null }).parent ?? null,
    }));
  }, [ctx]);

  const tree = useMemo(() => buildTree(objects), [objects]);
  const counts = useMemo(() => typeCounts(objects), [objects]);
  const filtering = query.trim() !== "" || activeTypes.size > 0;
  const visible = useMemo(
    () => (filtering ? filterTree(tree, query, activeTypes) : tree),
    [tree, query, activeTypes, filtering]
  );

  useEffect(() => {
    setExpanded(new Set(tree.map((n) => n.id)));
  }, [tree]);

  if (!ctx) return null;
  const hidden = new Set(hiddenIds);

  const toggleType = (t: string) => {
    setActiveTypes((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
  };

  const renderNode = (node: TreeNode, depth: number) => {
    const isOpen = filtering || expanded.has(node.id);
    return (
      <li key={node.id} className={hidden.has(node.id) ? "tree-hidden" : ""}>
        <div className="tree-row" style={{ paddingLeft: depth * 16 }}>
          {node.children.length > 0 && !filtering ? (
            <button
              type="button"
              className="tree-toggle"
              aria-label={isOpen ? "折叠" : "展开"}
              onClick={() =>
                setExpanded((prev) => {
                  const next = new Set(prev);
                  if (next.has(node.id)) next.delete(node.id);
                  else next.add(node.id);
                  return next;
                })
              }
            >
              {isOpen ? "▾" : "▸"}
            </button>
          ) : (
            <span className="tree-toggle-placeholder" />
          )}
          <button
            type="button"
            className="tree-hide-btn"
            aria-label={hidden.has(node.id) ? "显示" : "隐藏"}
            onClick={() => toggleHidden(node.id)}
          >
            {hidden.has(node.id) ? "🚫" : "👁"}
          </button>
          <span
            className={`tree-title${selectedId === node.id ? " selected" : ""}`}
            onClick={() => {
              setSelected(node.id);
              ctx.viewer.cameraFlight.flyTo({ component: node.id });
            }}
          >
            {node.name || node.id}
            <em className="tree-type">{node.type}</em>
          </span>
        </div>
        {isOpen && node.children.length > 0 && (
          <ul>{node.children.map((c) => renderNode(c, depth + 1))}</ul>
        )}
      </li>
    );
  };

  return (
    <aside className="tree-panel">
      <input
        className="tree-search"
        type="search"
        placeholder="搜索名称或类型"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <details className="tree-type-filter">
        <summary>类型过滤{activeTypes.size > 0 ? `（${activeTypes.size}）` : ""}</summary>
        <div className="tree-type-list">
          {counts.map(([t, n]) => (
            <label key={t}>
              <input
                type="checkbox"
                checked={activeTypes.has(t)}
                onChange={() => toggleType(t)}
                aria-label={t}
              />
              {t}（{n}）
            </label>
          ))}
        </div>
      </details>
      <ul className="tree-root">{visible.map((n) => renderNode(n, 0))}</ul>
    </aside>
  );
}
```

`tree.css` 全量替换：

```css
.tree-panel {
  order: 0;
  width: 280px;
  flex-shrink: 0;
  border-right: 1px solid #ddd;
  background: #fff;
  overflow: auto;
  padding: 8px;
  font-size: 13px;
  display: flex;
  flex-direction: column;
}

.tree-search {
  width: 100%;
  box-sizing: border-box;
  margin-bottom: 6px;
  padding: 4px 6px;
}

.tree-type-filter summary { cursor: pointer; user-select: none; }
.tree-type-list { display: flex; flex-direction: column; max-height: 160px; overflow: auto; padding: 4px 0; }
.tree-type-list label { display: flex; gap: 4px; align-items: center; line-height: 20px; }

.tree-root, .tree-panel ul { list-style: none; padding-left: 0; margin: 0; overflow: auto; }

.tree-row { display: flex; align-items: center; gap: 4px; line-height: 24px; white-space: nowrap; }
.tree-toggle { border: none; background: none; cursor: pointer; width: 16px; padding: 0; }
.tree-toggle-placeholder { width: 16px; flex-shrink: 0; }
.tree-hide-btn { border: none; background: none; cursor: pointer; padding: 0 2px; font-size: 12px; }
.tree-title { cursor: pointer; overflow: hidden; text-overflow: ellipsis; }
.tree-title:hover { color: #1565c0; text-decoration: underline; }
.tree-title.selected { color: #1565c0; font-weight: 600; }
.tree-type { color: #999; font-style: normal; margin-left: 6px; font-size: 11px; }
.tree-hidden .tree-title { opacity: 0.45; }
```

- [ ] **Step 4: 运行确认通过（含全量回归）**

Run: `cd web && npm test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd AI_IFC && git add web/src/viewer/ModelTreePanel* web/src/viewer/tree.css && git commit -m "feat(viewer): 自建 ModelTree（搜索/类型过滤/hide），弃用 TreeViewPlugin"
```

---

### Task 8: useVisibility hook + VisibilityToolbar

**Files:**
- Create: `web/src/viewer/useVisibility.ts`
- Test: `web/src/viewer/useVisibility.test.ts`
- Create: `web/src/viewer/VisibilityToolbar.tsx`
- Test: `web/src/viewer/VisibilityToolbar.test.tsx`
- Modify: `web/src/viewer/ViewerContext.tsx:70-71`（挂载 hook）
- Modify: `web/src/viewer/Toolbar.tsx`（工具栏加按钮组）

**Interfaces:**
- Consumes: Task 6 store；`useViewer()` ctx
- Produces:
  - `useVisibility(ctx: ViewerContextValue | null): void`（在 ViewerProvider 内挂载）
  - `export function VisibilityToolbar()`（供 Toolbar 嵌入）

- [ ] **Step 1: 写失败测试**

`useVisibility.test.ts`：

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useVisibility } from "./useVisibility";
import { useViewerStore } from "./store";
import type { ViewerContextValue } from "./ViewerContext";

function fakeCtx() {
  const objects: Record<string, { visible: boolean; xrayed: boolean }> = {
    a: { visible: true, xrayed: false },
    b: { visible: true, xrayed: false },
  };
  const ctx = { viewer: { scene: { objects } } } as unknown as ViewerContextValue;
  return { ctx, objects };
}

beforeEach(() => {
  useViewerStore.setState({ hiddenIds: [], isolateId: null, xray: false });
});

describe("useVisibility", () => {
  it("hides objects in hiddenIds", () => {
    const { ctx, objects } = fakeCtx();
    useViewerStore.getState().toggleHidden("a");
    renderHook(() => useVisibility(ctx));
    expect(objects.a.visible).toBe(false);
    expect(objects.b.visible).toBe(true);
  });

  it("isolate shows only the isolated object", () => {
    const { ctx, objects } = fakeCtx();
    useViewerStore.getState().isolate("a");
    renderHook(() => useVisibility(ctx));
    expect(objects.a.visible).toBe(true);
    expect(objects.b.visible).toBe(false);
  });

  it("xray marks non-isolated objects xrayed", () => {
    const { ctx, objects } = fakeCtx();
    useViewerStore.getState().setXray(true);
    renderHook(() => useVisibility(ctx));
    expect(objects.a.xrayed).toBe(true);
    expect(objects.b.xrayed).toBe(true);
  });

  it("reset restores all", () => {
    const { ctx, objects } = fakeCtx();
    useViewerStore.getState().toggleHidden("a");
    const { rerender } = renderHook(() => useVisibility(ctx));
    useViewerStore.getState().resetVisibility();
    rerender();
    expect(objects.a.visible).toBe(true);
    expect(objects.a.xrayed).toBe(false);
  });
});
```

`VisibilityToolbar.test.tsx`：

```tsx
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { VisibilityToolbar } from "./VisibilityToolbar";
import { useViewerStore } from "./store";

afterEach(cleanup);
beforeEach(() => {
  useViewerStore.setState({
    selectedId: null, tool: "select", hiddenIds: [], isolateId: null, xray: false,
  });
});

describe("VisibilityToolbar", () => {
  it("hide/isolate disabled without selection", () => {
    render(<VisibilityToolbar />);
    expect(screen.getByText("隐藏选中")).toHaveProperty("disabled", true);
    expect(screen.getByText("隔离")).toHaveProperty("disabled", true);
  });

  it("isolate toggles store isolateId", () => {
    useViewerStore.getState().setSelected("a");
    render(<VisibilityToolbar />);
    fireEvent.click(screen.getByText("隔离"));
    expect(useViewerStore.getState().isolateId).toBe("a");
    fireEvent.click(screen.getByText("隔离"));
    expect(useViewerStore.getState().isolateId).toBeNull();
  });

  it("xray toggles store", () => {
    render(<VisibilityToolbar />);
    fireEvent.click(screen.getByText("X-Ray"));
    expect(useViewerStore.getState().xray).toBe(true);
  });

  it("reset clears visibility state", () => {
    useViewerStore.getState().setXray(true);
    render(<VisibilityToolbar />);
    fireEvent.click(screen.getByText("重置可见性"));
    expect(useViewerStore.getState().xray).toBe(false);
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd web && npx vitest run src/viewer/useVisibility.test.ts src/viewer/VisibilityToolbar.test.tsx`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

`useVisibility.ts`：

```ts
import { useEffect } from "react";
import { useViewerStore } from "./store";
import type { ViewerContextValue } from "./ViewerContext";

export function useVisibility(ctx: ViewerContextValue | null) {
  const hiddenIds = useViewerStore((s) => s.hiddenIds);
  const isolateId = useViewerStore((s) => s.isolateId);
  const xray = useViewerStore((s) => s.xray);

  useEffect(() => {
    if (!ctx) return;
    const objects = ctx.viewer.scene.objects as unknown as Record<
      string,
      { visible: boolean; xrayed: boolean }
    >;
    const hidden = new Set(hiddenIds);
    for (const id of Object.keys(objects)) {
      const obj = objects[id];
      obj.visible = !hidden.has(id) && (isolateId === null || id === isolateId);
      obj.xrayed = xray && id !== isolateId;
    }
  }, [ctx, hiddenIds, isolateId, xray]);
}
```

`ViewerContext.tsx`：import 增加 `import { useVisibility } from "./useVisibility";`，在 `:71`（`useSelectionHighlight(...)` 之后）加一行 `useVisibility(ctx);`。

`VisibilityToolbar.tsx`：

```tsx
import { useViewerStore } from "./store";

export function VisibilityToolbar() {
  const selectedId = useViewerStore((s) => s.selectedId);
  const hiddenIds = useViewerStore((s) => s.hiddenIds);
  const isolateId = useViewerStore((s) => s.isolateId);
  const xray = useViewerStore((s) => s.xray);
  const toggleHidden = useViewerStore((s) => s.toggleHidden);
  const isolate = useViewerStore((s) => s.isolate);
  const setXray = useViewerStore((s) => s.setXray);
  const resetVisibility = useViewerStore((s) => s.resetVisibility);

  const dirty = hiddenIds.length > 0 || isolateId !== null || xray;

  return (
    <div className="visibility-toolbar" role="toolbar" aria-label="可见性工具栏">
      <button
        type="button"
        className="toolbar-btn"
        disabled={!selectedId}
        onClick={() => selectedId && toggleHidden(selectedId)}
      >
        隐藏选中
      </button>
      <button
        type="button"
        className={`toolbar-btn${isolateId ? " active" : ""}`}
        aria-pressed={isolateId !== null}
        disabled={!selectedId && !isolateId}
        onClick={() => isolate(isolateId ? null : selectedId)}
      >
        隔离
      </button>
      <button
        type="button"
        className={`toolbar-btn${xray ? " active" : ""}`}
        aria-pressed={xray}
        onClick={() => setXray(!xray)}
      >
        X-Ray
      </button>
      <button
        type="button"
        className="toolbar-btn"
        disabled={!dirty}
        onClick={resetVisibility}
      >
        重置可见性
      </button>
    </div>
  );
}
```

`Toolbar.tsx`：import `VisibilityToolbar`，在「清除测量」按钮之后、「下载 IFC」之前插入 `<VisibilityToolbar />`（它会渲染一组 toolbar-btn，样式沿用 Toolbar.css）。

- [ ] **Step 4: 运行确认通过（全量）**

Run: `cd web && npm test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd AI_IFC && git add web/src/viewer/useVisibility* web/src/viewer/VisibilityToolbar* web/src/viewer/ViewerContext.tsx web/src/viewer/Toolbar.tsx && git commit -m "feat(viewer): 可见性 hook 与 Hide/Isolate/X-Ray 工具栏"
```

---

### Task 9: PropertyPanel 增强（搜索 / pset 折叠 / 复制）

**Files:**
- Modify: `web/src/viewer/PropertyPanel.tsx`
- Modify: `web/src/viewer/PropertyPanel.css`（追加样式）
- Modify: `web/src/viewer/PropertyPanel.test.tsx`（重写，mock ViewerContext）

**Interfaces:**
- Consumes: 现有 `useViewer()`、`selectedId`
- Produces: 组件签名不变 `export function PropertyPanel()`

- [ ] **Step 1: 重写测试 `PropertyPanel.test.tsx`**

```tsx
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";

const mockCtx: { current: unknown } = { current: null };
vi.mock("./ViewerContext", () => ({ useViewer: () => mockCtx.current }));

import { PropertyPanel } from "./PropertyPanel";
import { useViewerStore } from "./store";

afterEach(cleanup);

const metaObject = {
  id: "w1",
  name: "Wall A",
  type: "IfcWall",
  parent: "st",
  propertySets: [
    {
      id: "pset1",
      name: "Pset_WallCommon",
      type: "Pset",
      properties: [
        { name: "FireRating", value: "120 min", type: "1" },
        { name: "LoadBearing", value: true, type: "3" },
      ],
    },
    {
      id: "pset2",
      name: "Pset_Geometry",
      type: "Pset",
      properties: [{ name: "Height", value: 3200, type: "4" }],
    },
  ],
};

function setup() {
  mockCtx.current = { metaModel: { metaObjects: { w1: metaObject } } };
  useViewerStore.setState({
    selectedId: null, tool: "select", hiddenIds: [], isolateId: null, xray: false,
  });
}

describe("PropertyPanel", () => {
  beforeEach(setup);

  it("shows empty state when nothing is selected", () => {
    render(<PropertyPanel />);
    expect(screen.getByText("点击构件查看属性")).toBeTruthy();
  });

  it("stays in empty state without a meta model even if selected", () => {
    mockCtx.current = null;
    useViewerStore.getState().setSelected("w1");
    render(<PropertyPanel />);
    expect(screen.getByText("点击构件查看属性")).toBeTruthy();
  });

  it("search filters properties by name or value", () => {
    useViewerStore.getState().setSelected("w1");
    render(<PropertyPanel />);
    fireEvent.change(screen.getByPlaceholderText("搜索属性"), {
      target: { value: "fire" },
    });
    expect(screen.getByText("FireRating")).toBeTruthy();
    expect(screen.queryByText("LoadBearing")).toBeNull();
  });

  it("second pset collapsed by default, expands on click", () => {
    useViewerStore.getState().setSelected("w1");
    render(<PropertyPanel />);
    expect(screen.queryByText("Height")).toBeNull();
    fireEvent.click(screen.getByText("Pset_Geometry"));
    expect(screen.getByText("Height")).toBeTruthy();
  });

  it("copy button writes name: value to clipboard", async () => {
    const writeText = vi.fn(async () => {});
    Object.assign(navigator, { clipboard: { writeText } });
    useViewerStore.getState().setSelected("w1");
    render(<PropertyPanel />);
    const row = screen.getByText("FireRating").closest("tr")!;
    fireEvent.click(row.querySelector("button.property-copy-btn")!);
    expect(writeText).toHaveBeenCalledWith("FireRating: 120 min");
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd web && npx vitest run src/viewer/PropertyPanel.test.tsx`
Expected: FAIL（搜索框 / 折叠 / 复制按钮不存在）

- [ ] **Step 3: 实现 `PropertyPanel.tsx`（全量替换）**

```tsx
import { useEffect, useState } from "react";
import type { MetaObject } from "@xeokit/xeokit-sdk";
import { useViewer } from "./ViewerContext";
import { useViewerStore } from "./store";
import "./PropertyPanel.css";

interface Prop {
  name: string;
  value: unknown;
  type?: string;
}

interface Pset {
  id: string;
  name: string;
  properties?: Prop[];
}

export function PropertyPanel() {
  const ctx = useViewer();
  const selectedId = useViewerStore((s) => s.selectedId);
  const [query, setQuery] = useState("");
  const [toggled, setToggled] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setToggled({});
    setQuery("");
  }, [selectedId]);

  const metaModel = ctx?.metaModel ?? null;
  const metaObjects = metaModel
    ? (metaModel.metaObjects as unknown as Record<string, MetaObject>)
    : null;
  const metaObject =
    selectedId && metaObjects ? (metaObjects[selectedId] ?? null) : null;

  const psets = (metaObject?.propertySets ?? []) as unknown as Pset[];
  const q = query.trim().toLowerCase();
  const searching = q !== "";

  const propMatches = (p: Prop) =>
    p.name.toLowerCase().includes(q) ||
    (p.value != null && String(p.value).toLowerCase().includes(q));

  const isOpen = (id: string, index: number) =>
    searching || (id in toggled ? toggled[id] : index === 0);

  return (
    <aside className="property-panel">
      <h2>属性</h2>
      {!metaObject && <p className="property-empty">点击构件查看属性</p>}
      {metaObject && (
        <div className="property-body">
          <input
            className="property-search"
            type="search"
            placeholder="搜索属性"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <dl className="property-summary">
            <dt>名称</dt>
            <dd>{metaObject.name || "（未命名）"}</dd>
            <dt>类型</dt>
            <dd>{metaObject.type}</dd>
          </dl>
          {psets.map((pset, index) => {
            const props = (pset.properties ?? []).filter(
              (p) => !searching || propMatches(p) || pset.name.toLowerCase().includes(q)
            );
            if (searching && props.length === 0) return null;
            return (
              <section key={pset.id} className="property-set">
                <h3
                  className="property-set-title"
                  onClick={() =>
                    setToggled((prev) => ({
                      ...prev,
                      [pset.id]: !isOpen(pset.id, index),
                    }))
                  }
                >
                  {isOpen(pset.id, index) ? "▾ " : "▸ "}
                  {pset.name}
                </h3>
                {isOpen(pset.id, index) && (
                  <table>
                    <tbody>
                      {props.map((prop, i) => (
                        <tr key={`${prop.name}-${i}`}>
                          <td className="property-name">{prop.name}</td>
                          <td className="property-value">
                            {prop.value == null ? "" : String(prop.value)}
                          </td>
                          <td className="property-copy">
                            <button
                              type="button"
                              className="property-copy-btn"
                              aria-label={`复制 ${prop.name}`}
                              onClick={() =>
                                navigator.clipboard.writeText(
                                  `${prop.name}: ${prop.value == null ? "" : String(prop.value)}`
                                )
                              }
                            >
                              复制
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </section>
            );
          })}
        </div>
      )}
    </aside>
  );
}
```

`PropertyPanel.css` 追加：

```css
.property-search {
  width: 100%;
  box-sizing: border-box;
  margin-bottom: 8px;
  padding: 4px 6px;
}

.property-set-title { cursor: pointer; user-select: none; }
.property-copy { width: 1%; white-space: nowrap; }
.property-copy-btn { border: none; background: none; color: #1565c0; cursor: pointer; font-size: 12px; padding: 0 4px; }
```

- [ ] **Step 4: 运行确认通过（全量）**

Run: `cd web && npm test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd AI_IFC && git add web/src/viewer/PropertyPanel* && git commit -m "feat(viewer): PropertyPanel 搜索/pset 折叠/属性复制"
```

---

### Task 10: IssuePanel（列表 / 创建 / 状态流转 / 删除 / 相机恢复）

**Files:**
- Create: `web/src/viewer/IssuePanel.tsx`
- Create: `web/src/viewer/IssuePanel.css`
- Test: `web/src/viewer/IssuePanel.test.tsx`
- Modify: `web/src/pages/ViewerPage.tsx`（挂载）
- Modify: `web/src/pages/ViewerPage.css`（抽屉定位样式）

**Interfaces:**
- Consumes: Task 4 的 `listIssues/createIssue/updateIssue/deleteIssue/issueAssetUrl`、`Issue/NewIssue/IssueStatus`；store `selectedId/setSelected`；`useViewer()`
- Produces: `export function IssuePanel({ modelId }: { modelId: string })`

- [ ] **Step 1: 写失败测试 `IssuePanel.test.tsx`**

```tsx
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockCtx: { current: unknown } = { current: null };
vi.mock("./ViewerContext", () => ({ useViewer: () => mockCtx.current }));

const api = {
  listIssues: vi.fn(),
  createIssue: vi.fn(),
  updateIssue: vi.fn(),
  deleteIssue: vi.fn(),
  issueAssetUrl: vi.fn(() => "/models/m/shot.png"),
};
vi.mock("@/api/client", () => api);

import { IssuePanel } from "./IssuePanel";
import { useViewerStore } from "./store";

afterEach(cleanup);

const sample = {
  id: "i_abcdef012345", entityId: "w1", entityName: "Wall A", entityType: "IfcWall",
  title: "Door width incorrect", comment: "", status: "open",
  camera: { eye: [1, 2, 3], look: [0, 0, 0], up: [0, 0, 1] },
  screenshot: "", createdAt: "2026-07-28T00:00:00Z", updatedAt: "2026-07-28T00:00:00Z",
};

function setup() {
  mockCtx.current = {
    viewer: {
      camera: { eye: [1, 2, 3], look: [0, 0, 0], up: [0, 0, 1] },
      cameraFlight: { flyTo: vi.fn() },
      scene: { objects: { w1: {} } },
    },
    metaModel: { metaObjects: { w1: { id: "w1", name: "Wall A", type: "IfcWall" } } },
  };
  useViewerStore.setState({
    selectedId: null, tool: "select", hiddenIds: [], isolateId: null, xray: false,
  });
  api.listIssues.mockResolvedValue([sample]);
  api.updateIssue.mockResolvedValue({ ...sample, status: "resolved" });
  api.deleteIssue.mockResolvedValue(null);
  api.createIssue.mockResolvedValue({ ...sample, id: "i_new000000001", title: "new" });
}

describe("IssuePanel", () => {
  beforeEach(setup);

  it("lists issues on mount", async () => {
    render(<IssuePanel modelId="m_0123456789abcdef" />);
    expect(await screen.findByText("Door width incorrect")).toBeTruthy();
    expect(screen.getByText("Wall A")).toBeTruthy();
  });

  it("create button disabled without selection", async () => {
    render(<IssuePanel modelId="m_0123456789abcdef" />);
    await screen.findByText("Door width incorrect");
    expect(screen.getByText("新建 Issue")).toHaveProperty("disabled", true);
  });

  it("creates issue with camera from viewer", async () => {
    useViewerStore.getState().setSelected("w1");
    render(<IssuePanel modelId="m_0123456789abcdef" />);
    await screen.findByText("Door width incorrect");
    fireEvent.click(screen.getByText("新建 Issue"));
    fireEvent.change(screen.getByPlaceholderText("标题"), { target: { value: "new" } });
    fireEvent.click(screen.getByText("提交"));
    await waitFor(() => expect(api.createIssue).toHaveBeenCalledOnce());
    const [, payload] = api.createIssue.mock.calls[0];
    expect(payload.title).toBe("new");
    expect(payload.entityId).toBe("w1");
    expect(payload.camera.eye).toEqual([1, 2, 3]);
  });

  it("status select patches issue", async () => {
    render(<IssuePanel modelId="m_0123456789abcdef" />);
    await screen.findByText("Door width incorrect");
    fireEvent.change(screen.getByLabelText("状态"), { target: { value: "resolved" } });
    await waitFor(() =>
      expect(api.updateIssue).toHaveBeenCalledWith(
        "m_0123456789abcdef", "i_abcdef012345", { status: "resolved" }
      )
    );
  });

  it("clicking issue flies camera and selects entity", async () => {
    render(<IssuePanel modelId="m_0123456789abcdef" />);
    fireEvent.click(await screen.findByText("Door width incorrect"));
    const ctx = mockCtx.current as { viewer: { cameraFlight: { flyTo: ReturnType<typeof vi.fn> } } };
    expect(ctx.viewer.cameraFlight.flyTo).toHaveBeenCalledWith({
      eye: [1, 2, 3], look: [0, 0, 0], up: [0, 0, 1],
    });
    expect(useViewerStore.getState().selectedId).toBe("w1");
  });

  it("delete removes issue after confirm", async () => {
    vi.stubGlobal("confirm", vi.fn(() => true));
    render(<IssuePanel modelId="m_0123456789abcdef" />);
    await screen.findByText("Door width incorrect");
    fireEvent.click(screen.getByLabelText("删除 Issue"));
    await waitFor(() => expect(api.deleteIssue).toHaveBeenCalledOnce());
    await waitFor(() => expect(screen.queryByText("Door width incorrect")).toBeNull());
    vi.unstubAllGlobals();
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd web && npx vitest run src/viewer/IssuePanel.test.tsx`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 `IssuePanel.tsx`**

```tsx
import { useEffect, useState } from "react";
import {
  createIssue,
  deleteIssue,
  issueAssetUrl,
  listIssues,
  updateIssue,
} from "@/api/client";
import type { Issue, IssueStatus } from "@/api/types";
import { useViewer } from "./ViewerContext";
import { useViewerStore } from "./store";
import "./IssuePanel.css";

const STATUS_LABELS: Record<IssueStatus, string> = {
  open: "Open",
  checking: "Checking",
  resolved: "Resolved",
};

export function IssuePanel({ modelId }: { modelId: string }) {
  const ctx = useViewer();
  const selectedId = useViewerStore((s) => s.selectedId);
  const setSelected = useViewerStore((s) => s.setSelected);

  const [issues, setIssues] = useState<Issue[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    listIssues(modelId)
      .then(setIssues)
      .catch((e: Error) => setError(e.message));
  }, [modelId]);

  const captureScreenshot = (): Promise<Blob | null> =>
    new Promise((resolve) => {
      const canvas = document.getElementById("xeokit-canvas") as HTMLCanvasElement | null;
      if (!canvas || !canvas.toBlob) return resolve(null);
      try {
        canvas.toBlob((b) => resolve(b), "image/png");
      } catch {
        resolve(null);
      }
    });

  const submit = async () => {
    if (!ctx || !selectedId || !title.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const metaObjects = ctx.metaModel?.metaObjects as unknown as Record<
        string,
        { name?: string; type?: string }
      > | undefined;
      const meta = metaObjects?.[selectedId];
      const cam = ctx.viewer.camera;
      const screenshot = await captureScreenshot();
      const created = await createIssue(
        modelId,
        {
          entityId: selectedId,
          entityName: meta?.name ?? "",
          entityType: meta?.type ?? "",
          title: title.trim(),
          comment,
          camera: {
            eye: [...cam.eye] as [number, number, number],
            look: [...cam.look] as [number, number, number],
            up: [...cam.up] as [number, number, number],
          },
        },
        screenshot
      );
      setIssues((prev) => [created, ...prev]);
      setTitle("");
      setComment("");
      setFormOpen(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const locate = (iss: Issue) => {
    if (!ctx) return;
    ctx.viewer.cameraFlight.flyTo({
      eye: iss.camera.eye,
      look: iss.camera.look,
      up: iss.camera.up,
    });
    const objects = ctx.viewer.scene.objects as unknown as Record<string, unknown>;
    if (objects[iss.entityId]) setSelected(iss.entityId);
  };

  const changeStatus = async (iss: Issue, status: IssueStatus) => {
    try {
      const updated = await updateIssue(modelId, iss.id, { status });
      setIssues((prev) => prev.map((x) => (x.id === iss.id ? updated : x)));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const remove = async (iss: Issue) => {
    if (!window.confirm(`删除 Issue「${iss.title}」？`)) return;
    try {
      await deleteIssue(modelId, iss.id);
      setIssues((prev) => prev.filter((x) => x.id !== iss.id));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <section className={`issue-panel${collapsed ? " collapsed" : ""}`}>
      <header className="issue-panel-header" onClick={() => setCollapsed((v) => !v)}>
        <span>Issues（{issues.length}）</span>
        <button
          type="button"
          className="issue-new-btn"
          disabled={!selectedId}
          title={selectedId ? "" : "先在模型中选中一个构件"}
          onClick={(e) => {
            e.stopPropagation();
            setFormOpen((v) => !v);
          }}
        >
          新建 Issue
        </button>
      </header>
      {!collapsed && (
        <div className="issue-panel-body">
          {error && <p className="issue-error">{error}</p>}
          {formOpen && (
            <div className="issue-form">
              <input
                placeholder="标题"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
              <textarea
                placeholder="备注（可选）"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
              />
              <button type="button" disabled={!title.trim() || submitting} onClick={submit}>
                {submitting ? "提交中…" : "提交"}
              </button>
            </div>
          )}
          <ul className="issue-list">
            {issues.map((iss) => (
              <li key={iss.id} className="issue-item">
                <span className={`issue-status-dot issue-status-${iss.status}`} />
                <button type="button" className="issue-title" onClick={() => locate(iss)}>
                  {iss.title}
                </button>
                <span className="issue-entity">{iss.entityName || iss.entityId}</span>
                {iss.screenshot && (
                  <img
                    className="issue-thumb"
                    src={issueAssetUrl(modelId, iss)}
                    alt="截图"
                  />
                )}
                <select
                  aria-label="状态"
                  value={iss.status}
                  onChange={(e) => changeStatus(iss, e.target.value as IssueStatus)}
                >
                  {(Object.keys(STATUS_LABELS) as IssueStatus[]).map((s) => (
                    <option key={s} value={s}>
                      {STATUS_LABELS[s]}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="issue-delete-btn"
                  aria-label="删除 Issue"
                  onClick={() => remove(iss)}
                >
                  ✕
                </button>
              </li>
            ))}
            {issues.length === 0 && <li className="issue-empty">暂无 Issue</li>}
          </ul>
        </div>
      )}
    </section>
  );
}
```

`IssuePanel.css`：

```css
.issue-panel {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  bottom: 0;
  width: min(760px, 60%);
  background: #fff;
  border: 1px solid #ddd;
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.08);
  z-index: 10;
  font-size: 13px;
}

.issue-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  cursor: pointer;
  user-select: none;
  font-weight: 600;
}

.issue-panel.collapsed .issue-panel-body { display: none; }
.issue-panel-body { max-height: 240px; overflow: auto; padding: 0 12px 8px; }
.issue-error { color: #b00020; margin: 4px 0; }

.issue-form { display: flex; gap: 6px; align-items: flex-start; margin-bottom: 8px; }
.issue-form input { flex: 1; padding: 4px 6px; }
.issue-form textarea { flex: 2; padding: 4px 6px; height: 34px; resize: vertical; }

.issue-list { list-style: none; margin: 0; padding: 0; }
.issue-item { display: flex; align-items: center; gap: 8px; line-height: 28px; }
.issue-status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.issue-status-open { background: #d32f2f; }
.issue-status-checking { background: #f9a825; }
.issue-status-resolved { background: #2e7d32; }
.issue-title { border: none; background: none; cursor: pointer; color: #1565c0; padding: 0; text-align: left; }
.issue-title:hover { text-decoration: underline; }
.issue-entity { color: #777; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.issue-thumb { width: 40px; height: 28px; object-fit: cover; border: 1px solid #ddd; }
.issue-delete-btn { border: none; background: none; cursor: pointer; color: #999; }
.issue-delete-btn:hover { color: #b00020; }
.issue-empty { color: #999; }
```

`ViewerPage.tsx`：import `IssuePanel`，在 `<PropertyPanel />` 之后加 `<IssuePanel modelId={id} />`。

`ViewerPage.css` 无需改动（`.issue-panel` 已 `position: absolute`，相对 `.viewer-page` 定位，其 `position: relative` 已存在）。

- [ ] **Step 4: 运行确认通过（全量 + 类型检查）**

Run: `cd web && npm test && npm run build`
Expected: vitest PASS；`tsc -b && vite build` 无类型错误

- [ ] **Step 5: Commit**

```bash
cd AI_IFC && git add web/src/viewer/IssuePanel* web/src/pages/ && git commit -m "feat(viewer): IssuePanel（创建/列表/状态流转/相机恢复/截图）"
```

---

### Task 11: e2e smoke 扩展 + 文档覆写

**Files:**
- Modify: `scripts/smoke.sh`
- Modify: `viewer/docs/api.md`（追加 issues 契约）
- Modify: `viewer/docs/design.md`（更新非目标与存储说明）
- Modify: `docs/internal/architecture/viewerstatus.md`（缺口表勾选）

**Interfaces:**
- Consumes: Task 3 的路由、Task 10 的前端功能

- [ ] **Step 1: 扩展 `smoke.sh`**

在 `curl -sf -o /dev/null -w "download: ..."` 行之后、`DELETE /api/models/$ID` 之前插入：

```bash
# issues CRUD
python3 -c 'import base64,sys;sys.stdout.buffer.write(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="))' > /tmp/smoke-shot.png
ISSUE_ID=$(curl -sf \
  -F 'issue={"entityId":"3a82-xxxx","entityName":"Wall","entityType":"IfcWall","title":"smoke issue","comment":"c","camera":{"eye":[1,2,3],"look":[0,0,0],"up":[0,0,1]}}' \
  -F "screenshot=@/tmp/smoke-shot.png;type=image/png" \
  "$BASE/api/models/$ID/issues" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["id"])')
echo "issue created: $ISSUE_ID"
curl -sf "$BASE/api/models/$ID/issues" | python3 -c 'import sys,json;d=json.load(sys.stdin)["data"];assert len(d)==1 and d[0]["status"]=="open" and d[0]["screenshot"].startswith("issues/"),d'
curl -sf -o /dev/null -w "shot: %{http_code}\n" "$BASE/models/$ID/issues/$ISSUE_ID.png"
curl -sf -X PATCH -H 'Content-Type: application/json' -d '{"status":"resolved"}' \
  "$BASE/api/models/$ID/issues/$ISSUE_ID" | python3 -c 'import sys,json;assert json.load(sys.stdin)["data"]["status"]=="resolved"'
curl -sf -X DELETE "$BASE/api/models/$ID/issues/$ISSUE_ID" > /dev/null
curl -sf "$BASE/api/models/$ID/issues" | python3 -c 'import sys,json;assert json.load(sys.stdin)["data"]==[]'
```

- [ ] **Step 2: 跑通 smoke**

启动 server（`cd server && go run ./cmd/server -config server_config.json`，后台），然后：

Run: `cd viewer && bash scripts/smoke.sh`
Expected: 末尾输出 `smoke OK`，中间含 `issue created:` 与 `shot: 200`

- [ ] **Step 3: 覆写文档**

1. `viewer/docs/api.md`：追加「Issues」章节，内容为下（按该文件既有 markdown 风格插入到合适位置）：

```markdown
## Issues（审查标记）

所有路由沿用 `{code,message,data}` 信封。issue id 格式 `i_` + 12 位小写 hex；status ∈ `open | checking | resolved`。

### GET /api/models/{id}/issues
返回 `data: Issue[]`，按 createdAt 降序。

### POST /api/models/{id}/issues
multipart/form-data：
- `issue`（必填）：JSON 字符串 `{"entityId","entityName","entityType","title","comment","camera":{"eye":[x,y,z],"look":[x,y,z],"up":[x,y,z]}}`，title 必填
- `screenshot`（可选）：PNG 文件，≤5MB

返回 `data: Issue`（含生成的 `id`、`status:"open"`、`screenshot` 相对路径如 `issues/{id}.png`、`createdAt/updatedAt`）。

### PATCH /api/models/{id}/issues/{issueId}
JSON body：`{"title"?, "comment"?, "status"?}`，仅更新传入字段。返回 `data: Issue`。

### DELETE /api/models/{id}/issues/{issueId}
删除 Issue 及其截图。返回 `data: null`。

### GET /models/{id}/issues/{file}
Issue 截图静态服务，`file` 必须匹配 `i_[0-9a-f]{12}\.png`。

错误码：40001（参数/校验错误）、40002（超限）、40400（模型或 Issue 不存在）、50000（内部错误）。
```

2. `viewer/docs/design.md`：将「非目标」中的「标注持久化」删除，改为在存储一节补充：「Issue/Markup 持久化采用文件存储（`models/{id}/issues.json` + `issues/*.png`），由 `internal/issue.Store` 接口抽象，后期可平移 PostgreSQL（新增 PgStore 实现，API/前端零改动）」。

3. `docs/internal/architecture/viewerstatus.md`：P0/P1 缺口表更新为：

```markdown
| 优先级 | 组件 | 现状 |
| P0 | Property Inspector | ✅ 有（只读，含搜索/复制；无修改/修改记录） |
| P0 | Model Tree + 过滤 | ✅ 有（搜索 + 分类过滤 + hide） |
| P0 | Issue/Markup (BCF) | ✅ 有（创建/列表/状态流转/相机恢复/截图；文件存储，DB 预留） |
| P1 | 测量 | ✅ 距离有 |
| P1 | Hide/Isolate/X-Ray 工具栏 | ✅ 有 |
| P1 | 版本对比 Diff Viewer | ❌ 没做 |
| P2 | 属性修改器 | ❌ 只读 |
```

- [ ] **Step 4: 最终全量回归**

Run: `cd server && go test ./... && go vet ./...`
Run: `cd web && npm test && npm run build`
Run: `cd web && npx oxlint`（若 package.json 有 lint script 则用 `npm run lint`）
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
cd AI_IFC && git add scripts/smoke.sh docs/internal/viewer/api.md docs/internal/viewer/design.md docs/internal/architecture/viewerstatus.md && git commit -m "feat(viewer): smoke 覆盖 issues CRUD；同步 design/api/viewerstatus 文档"
```

---

## Self-Review 记录

- Spec 覆盖：spec §2（server）→ Task 1-3；§3.1（store）→ Task 6；§3.2（树）→ Task 5/7；§3.3（工具栏）→ Task 8；§3.4（Inspector）→ Task 9；§3.5（IssuePanel）→ Task 10；§4（错误处理）→ 各任务测试；§5（测试）→ 各任务 + Task 11 smoke；§6（文档）→ Task 11。
- 类型一致性：`Issue/NewIssue/IssueCamera/IssueStatus`（Task 4）= server `Issue` json tag（Task 1）；`toggleHidden/isolate/setXray/resetVisibility`（Task 6）在 Task 7/8/10 使用一致；`issueAssetUrl` 在 Task 10 使用。
- 已知取舍：Task 2 `SaveScreenshot` 的存在性校验实现可简化（行为以测试为准）；截图失败前端降级为无截图创建（Task 10 `captureScreenshot` try/catch）。
