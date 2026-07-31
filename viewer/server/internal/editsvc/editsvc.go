// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

// Package editsvc 是 Python 编辑服务（viewer/edit-service）的 HTTP 客户端。
// Python 的错误响应 {"detail": ...} 映射为带状态码的 *Error，由 handler 层转 envelope。
package editsvc

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// Error 表示 Python 服务返回的非 2xx 响应。
type Error struct {
	Status int
	Detail string
}

func (e *Error) Error() string {
	return fmt.Sprintf("edit service: status %d: %s", e.Status, e.Detail)
}

type Provenance struct {
	Source string `json:"source"`
}

// Change 是 pending/history entry 里的单条字段变更（oldValue/newValue 可为任意 JSON 标量）。
type Change struct {
	Field    string `json:"field"`
	OldValue any    `json:"oldValue"`
	NewValue any    `json:"newValue"`
}

// Entry 对应 Python 的 pending/history 条目。
type Entry struct {
	ID         string     `json:"id"`
	GUID       string     `json:"guid"`
	Changes    []Change   `json:"changes"`
	Author     string     `json:"author"`
	Provenance Provenance `json:"provenance"`
	Timestamp  string     `json:"timestamp"`
	Operation  string     `json:"operation,omitempty"`
}

type CommitResult struct {
	Committed int     `json:"committed"`
	Entries   []Entry `json:"entries"`
}

type Version struct {
	Version   string `json:"version"`
	CreatedAt string `json:"createdAt"`
}

type Versions struct {
	Versions []Version `json:"versions"`
	Current  string    `json:"current"`
}

// DiffChange 是 diff.changed 里的变更项（field/old/new 形状，与 Change 不同）。
type DiffChange struct {
	Field string `json:"field"`
	Old   any    `json:"old"`
	New   any    `json:"new"`
}

type DiffChanged struct {
	GUID    string       `json:"guid"`
	Changes []DiffChange `json:"changes"`
}

type DiffResult struct {
	Base    string        `json:"base"`
	Target  string        `json:"target"`
	Added   []string      `json:"added"`
	Removed []string      `json:"removed"`
	Changed []DiffChanged `json:"changed"`
}

type Client struct {
	base string
	fast *http.Client // 简单调用 10s
	slow *http.Client // commit/diff 120s
}

func New(baseURL string) *Client {
	return &Client{
		base: baseURL,
		fast: &http.Client{Timeout: 10 * time.Second},
		slow: &http.Client{Timeout: 120 * time.Second},
	}
}

func parseDetail(data []byte) string {
	var e struct {
		Detail json.RawMessage `json:"detail"`
	}
	if err := json.Unmarshal(data, &e); err != nil || len(e.Detail) == 0 {
		return string(data)
	}
	var s string
	if err := json.Unmarshal(e.Detail, &s); err == nil {
		return s
	}
	return string(e.Detail) // 422 校验错误 detail 为数组，原样保留
}

func (c *Client) do(ctx context.Context, hc *http.Client, method, path string, body []byte) ([]byte, error) {
	var rdr io.Reader
	if body != nil {
		rdr = bytes.NewReader(body)
	}
	req, err := http.NewRequestWithContext(ctx, method, c.base+path, rdr)
	if err != nil {
		return nil, err
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := hc.Do(req)
	if err != nil {
		return nil, fmt.Errorf("edit service unreachable: %w", err)
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(io.LimitReader(resp.Body, 10<<20))
	if err != nil {
		return nil, fmt.Errorf("edit service: read response: %w", err)
	}
	if resp.StatusCode >= 400 {
		return nil, &Error{Status: resp.StatusCode, Detail: parseDetail(data)}
	}
	return data, nil
}

func (c *Client) PutEntity(ctx context.Context, modelID, guid string, body []byte) (json.RawMessage, error) {
	return c.do(ctx, c.fast, http.MethodPut, "/models/"+modelID+"/entities/"+guid, body)
}

func (c *Client) GetPending(ctx context.Context, modelID string) (json.RawMessage, error) {
	return c.do(ctx, c.fast, http.MethodGet, "/models/"+modelID+"/pending", nil)
}

func (c *Client) DeletePending(ctx context.Context, modelID string) (json.RawMessage, error) {
	return c.do(ctx, c.fast, http.MethodDelete, "/models/"+modelID+"/pending", nil)
}

func (c *Client) GetHistory(ctx context.Context, modelID string) (json.RawMessage, error) {
	return c.do(ctx, c.fast, http.MethodGet, "/models/"+modelID+"/history", nil)
}

// PostDiff 透传 diff 请求（body 原样转发）。
func (c *Client) PostDiff(ctx context.Context, modelID string, body []byte) (json.RawMessage, error) {
	return c.do(ctx, c.slow, http.MethodPost, "/models/"+modelID+"/diff", body)
}

func (c *Client) GetVersions(ctx context.Context, modelID string) (*Versions, error) {
	data, err := c.do(ctx, c.fast, http.MethodGet, "/models/"+modelID+"/versions", nil)
	if err != nil {
		return nil, err
	}
	var v Versions
	if err := json.Unmarshal(data, &v); err != nil {
		return nil, fmt.Errorf("edit service: decode versions: %w", err)
	}
	return &v, nil
}

// Diff 以类型化方式调 diff（commit 编排用）。
func (c *Client) Diff(ctx context.Context, modelID, base, target string) (*DiffResult, error) {
	body, _ := json.Marshal(map[string]string{"base": base, "target": target})
	data, err := c.do(ctx, c.slow, http.MethodPost, "/models/"+modelID+"/diff", body)
	if err != nil {
		return nil, err
	}
	var d DiffResult
	if err := json.Unmarshal(data, &d); err != nil {
		return nil, fmt.Errorf("edit service: decode diff: %w", err)
	}
	return &d, nil
}

func (c *Client) Commit(ctx context.Context, modelID string, body []byte) (*CommitResult, error) {
	data, err := c.do(ctx, c.slow, http.MethodPost, "/models/"+modelID+"/commit", body)
	if err != nil {
		return nil, err
	}
	var r CommitResult
	if err := json.Unmarshal(data, &r); err != nil {
		return nil, fmt.Errorf("edit service: decode commit: %w", err)
	}
	return &r, nil
}
