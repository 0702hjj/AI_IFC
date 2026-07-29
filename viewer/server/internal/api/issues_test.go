package api

import (
	"bytes"
	"context"
	"encoding/json"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"ifcviewer/server/internal/change"
	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/issue"
	"ifcviewer/server/internal/store"
)

// newIssueTestServer 构造 handler 与一个已存在的模型，返回 (mux, modelID)。
func newIssueTestServer(t *testing.T) (http.Handler, string) {
	t.Helper()
	mux, modelID, _ := newChangesTestServer(t)
	return mux, modelID
}

func newChangesTestServer(t *testing.T) (http.Handler, string, *change.FileStore) {
	t.Helper()
	st := store.NewStore(t.TempDir())
	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	q := convert.NewQueue(st, okRunner{}, 1)
	q.Start(ctx)
	chg := change.NewFileStore(st.DataDir)
	mux := NewHandler(st, q, issue.NewFileStore(st.DataDir), chg, 1<<20)
	m, err := st.Create("ok.ifc", 4, strings.NewReader("fake"))
	if err != nil {
		t.Fatal(err)
	}
	return mux, m.ID, chg
}

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
