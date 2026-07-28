package api

import (
	"context"
	"encoding/json"
	"io"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/store"
)

type okRunner struct{}

func (okRunner) Run(ctx context.Context, in, out string) error { return nil }

type env struct {
	Code    int             `json:"code"`
	Message string          `json:"message"`
	Data    json.RawMessage `json:"data"`
}

func setup(t *testing.T) (*httptest.Server, *store.Store) {
	t.Helper()
	st := store.NewStore(t.TempDir())
	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	q := convert.NewQueue(st, okRunner{}, 1)
	q.Start(ctx)
	srv := httptest.NewServer(NewHandler(st, q, 1<<20)) // 测试上限 1MB
	t.Cleanup(srv.Close)
	return srv, st
}

func upload(t *testing.T, url, filename, content string) *httptest.ResponseRecorder {
	t.Helper()
	var body strings.Builder
	w := multipart.NewWriter(&body)
	fw, _ := w.CreateFormFile("file", filename)
	fw.Write([]byte(content))
	w.Close()
	req, _ := http.NewRequest("POST", url+"/api/models", strings.NewReader(body.String()))
	req.Header.Set("Content-Type", w.FormDataContentType())
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	rec := httptest.NewRecorder()
	rec.Code = resp.StatusCode
	rec.Body.Write(b)
	return rec
}

func TestUploadListDownloadDelete(t *testing.T) {
	srv, st := setup(t)

	// 非法扩展名
	rec := upload(t, srv.URL, "a.txt", "x")
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("ext check: %d %s", rec.Code, rec.Body.String())
	}
	// 超限（上限 1MB）
	rec = upload(t, srv.URL, "big.ifc", strings.Repeat("x", 1<<20+1))
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("size check: %d", rec.Code)
	}
	// 正常上传
	rec = upload(t, srv.URL, "ok.ifc", "ISO-10303-21;fake")
	if rec.Code != http.StatusOK {
		t.Fatalf("upload: %d %s", rec.Code, rec.Body.String())
	}
	var e env
	json.Unmarshal(rec.Body.Bytes(), &e)
	if e.Code != 0 {
		t.Fatalf("envelope: %+v", e)
	}
	var created store.Model
	json.Unmarshal(e.Data, &created)
	if created.Status != "converting" && created.Status != "ready" {
		t.Fatalf("status: %q", created.Status)
	}
	// 等待转换完成（fake runner 立即成功）
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		m, _ := st.Get(created.ID)
		if m.Status == "ready" {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	// 列表
	resp, _ := http.Get(srv.URL + "/api/models")
	body, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	var le env
	json.Unmarshal(body, &le)
	var list []store.Model
	json.Unmarshal(le.Data, &list)
	if len(list) != 1 {
		t.Fatalf("list: %d", len(list))
	}
	// 下载原始 IFC
	resp, _ = http.Get(srv.URL + "/api/models/" + created.ID + "/download")
	b, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	if !strings.Contains(resp.Header.Get("Content-Disposition"), "ok.ifc") || string(b) != "ISO-10303-21;fake" {
		t.Fatalf("download: %v %q", resp.Header, b)
	}
	// 静态 xkt（文件不存在 → 404）
	resp, _ = http.Get(srv.URL + "/models/" + created.ID + "/model.xkt")
	resp.Body.Close()
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("static: %d", resp.StatusCode)
	}
	// 删除
	req, _ := http.NewRequest("DELETE", srv.URL+"/api/models/"+created.ID, nil)
	resp, _ = http.DefaultClient.Do(req)
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("delete: %d", resp.StatusCode)
	}
	if _, err := st.Get(created.ID); err != store.ErrNotFound {
		t.Fatalf("after delete: %v", err)
	}
	// 未知 id → 404
	resp, _ = http.Get(srv.URL + "/api/models/m_deadbeefdeadbeef")
	resp.Body.Close()
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("404: %d", resp.StatusCode)
	}
}
