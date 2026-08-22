// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package api

import (
	"context"
	"encoding/json"
	"io"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"ifcviewer/server/internal/change"
	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/issue"
	"ifcviewer/server/internal/override"
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
	srv := httptest.NewServer(NewHandler(st, q, issue.NewFileStore(st.DataDir), change.NewFileStore(st.DataDir), override.NewFileStore(st.DataDir), nil, nil, 1<<20)) // 测试上限 1MB
	t.Cleanup(srv.Close)
	return srv, st
}

// waitReadyModel 等队列 worker 完成 SetStatus 落盘，避免 TempDir 清理撞异步写盘（AGENTS 纪律 #5）。
func waitReadyModel(t *testing.T, st *store.Store, id string) {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		m, err := st.Get(id)
		if err == nil && m.Status == "ready" {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	m, _ := st.Get(id)
	t.Fatalf("model %s never became ready (now %q)", id, m.Status)
}

func upload(t *testing.T, url, filename, content string) *httptest.ResponseRecorder {
	t.Helper()
	var body strings.Builder
	w := multipart.NewWriter(&body)
	fw, _ := w.CreateFormFile("file", filename)
	fw.Write([]byte(content))
	w.Close()
	req, _ := http.NewRequest("POST", url+"/api/v1/models", strings.NewReader(body.String()))
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
	resp, _ := http.Get(srv.URL + "/api/v1/models")
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
	resp, _ = http.Get(srv.URL + "/api/v1/models/" + created.ID + "/download")
	b, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	if !strings.Contains(resp.Header.Get("Content-Disposition"), "ok.ifc") || string(b) != "ISO-10303-21;fake" {
		t.Fatalf("download: %v %q", resp.Header, b)
	}
	// 静态 xkt（文件不存在 → 404）
	resp, _ = http.Get(srv.URL + "/v1/models/" + created.ID + "/model.xkt")
	resp.Body.Close()
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("static: %d", resp.StatusCode)
	}
	// 删除
	req, _ := http.NewRequest("DELETE", srv.URL+"/api/v1/models/"+created.ID, nil)
	resp, _ = http.DefaultClient.Do(req)
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("delete: %d", resp.StatusCode)
	}
	if _, err := st.Get(created.ID); err != store.ErrNotFound {
		t.Fatalf("after delete: %v", err)
	}
	// 未知 id → 404
	resp, _ = http.Get(srv.URL + "/api/v1/models/m_deadbeefdeadbeef")
	resp.Body.Close()
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("404: %d", resp.StatusCode)
	}
}

func TestDeleteModelCascadesStores(t *testing.T) {
	srv, st := setup(t)
	rec := upload(t, srv.URL, "ok.ifc", "ISO-10303-21;fake")
	if rec.Code != http.StatusOK {
		t.Fatalf("upload: %d %s", rec.Code, rec.Body.String())
	}
	var e env
	json.Unmarshal(rec.Body.Bytes(), &e)
	var created store.Model
	json.Unmarshal(e.Data, &created)
	waitReadyModel(t, st, created.ID)

	iss := issue.NewFileStore(st.DataDir)
	if _, err := iss.Create(created.ID, &issue.Issue{Title: "x"}); err != nil {
		t.Fatal(err)
	}
	chg := change.NewFileStore(st.DataDir)
	if err := chg.Append(created.ID, &change.Entry{EntityID: "e1", Field: "Name", NewValue: "y"}); err != nil {
		t.Fatal(err)
	}
	ovr := override.NewFileStore(st.DataDir)
	if _, err := ovr.Set(created.ID, "e1", map[string]string{"Name": "y"}); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"issues.json", "changes.json", "overrides.json"} {
		if _, err := os.Stat(filepath.Join(st.DataDir, "models", created.ID, name)); err != nil {
			t.Fatalf("%s should exist before delete: %v", name, err)
		}
	}

	req, _ := http.NewRequest("DELETE", srv.URL+"/api/v1/models/"+created.ID, nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("delete: %d", resp.StatusCode)
	}
	for _, name := range []string{"issues.json", "changes.json", "overrides.json"} {
		if _, err := os.Stat(filepath.Join(st.DataDir, "models", created.ID, name)); !os.IsNotExist(err) {
			t.Fatalf("%s not removed after delete: %v", name, err)
		}
	}
}

func TestPutEntityPropertiesBodyTooLarge(t *testing.T) {
	srv, st := setup(t)
	rec := upload(t, srv.URL, "ok.ifc", "ISO-10303-21;fake")
	if rec.Code != http.StatusOK {
		t.Fatalf("upload: %d %s", rec.Code, rec.Body.String())
	}
	var e env
	json.Unmarshal(rec.Body.Bytes(), &e)
	var created store.Model
	json.Unmarshal(e.Data, &created)
	waitReadyModel(t, st, created.ID)

	big := `{"entityName":"Wall","fields":{"Name":"` + strings.Repeat("x", 1<<20) + `"}}`
	req, _ := http.NewRequest("PUT",
		srv.URL+"/api/v1/models/"+created.ID+"/entities/e1/properties", strings.NewReader(big))
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400: %s", resp.StatusCode, b)
	}
	var be env
	json.Unmarshal(b, &be)
	if be.Code != codeInvalidType {
		t.Fatalf("code = %d, want %d", be.Code, codeInvalidType)
	}
}

// TestDeleteModelRemovesFromProject：删除平台模型联动项目摘除——防孤儿 modelId 残留。
func TestDeleteModelRemovesFromProject(t *testing.T) {
	st := store.NewStore(t.TempDir())
	ps := store.NewProjectStore(st.DataDir)
	q := convert.NewQueue(st, okRunner{}, 1)
	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	q.Start(ctx)
	srv := httptest.NewServer(NewHandlerWithProjectStore(st, q, issue.NewFileStore(st.DataDir),
		change.NewFileStore(st.DataDir), override.NewFileStore(st.DataDir), nil, nil, 1<<20, nil, ps))
	t.Cleanup(srv.Close)

	// 造项目 + 项目下模型（正向 Project.Models + 反向 Model.ProjectID）
	p, err := ps.CreateWithKind("p1", "cad")
	if err != nil {
		t.Fatal(err)
	}
	m, err := st.CreateWithKindInProject("图纸", 0, strings.NewReader(""), store.KindDXF, p.ID)
	if err != nil {
		t.Fatal(err)
	}
	if err := ps.AddModel(p.ID, m.ID, store.KindDXF, "图纸", "ready"); err != nil {
		t.Fatal(err)
	}

	// 删除模型 → 项目引用应摘除
	req, _ := http.NewRequest(http.MethodDelete, "/api/v1/models/"+m.ID, nil)
	rec := httptest.NewRecorder()
	srv.Config.Handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("delete status = %d body=%s", rec.Code, rec.Body.String())
	}
	got, _ := ps.Get(p.ID)
	if len(got.Models) != 0 {
		t.Fatalf("删除模型后项目 Models = %v, want 空（孤儿 modelId 应摘除）", got.Models)
	}
}
