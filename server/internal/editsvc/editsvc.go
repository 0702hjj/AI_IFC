// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

// Package editsvc 是 Python 编辑服务（services/ifc）的 HTTP 客户端。
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

// ScriptVersion 是脚本大版本条目（GET /models/{id}/scripts 的 scripts 元素）。
type ScriptVersion struct {
	Version   string `json:"version"`
	CreatedAt string `json:"createdAt"`
	Note      string `json:"note"`
}

// ScriptVersions 是 GET /models/{id}/scripts 的响应（只看 scripts；legacy 模型为空表）。
type ScriptVersions struct {
	Scripts []ScriptVersion `json:"scripts"`
}

// ScriptParamChange 是脚本 diff 的单条 PARAMS key 变化（added/removed/modified）。
type ScriptParamChange struct {
	Key    string `json:"key"`
	Action string `json:"action"`
	Old    any    `json:"old,omitempty"`
	New    any    `json:"new,omitempty"`
}

// ScriptDiffStats 是 unified diff 的 +/- 行数。
type ScriptDiffStats struct {
	Added   int `json:"added"`
	Removed int `json:"removed"`
}

// ScriptDiffResult 是 POST /models/{id}/script/diff 的响应（AI 面向的主 diff）。
type ScriptDiffResult struct {
	Base          string              `json:"base"`
	Target        string              `json:"target"`
	TextDiff      string              `json:"text_diff"`
	ParamsChanges []ScriptParamChange `json:"params_changes"`
	Stats         ScriptDiffStats     `json:"stats"`
}

type Version struct {
	Version   string `json:"version"`
	CreatedAt string `json:"createdAt"`
}

type Versions struct {
	Versions []Version `json:"versions"`
	Current  string    `json:"current"`
}

type Client struct {
	base string
	fast *http.Client // 简单调用 10s
	slow *http.Client // commit/diff 120s
}

func New(baseURL string) *Client {
	return NewWithTimeouts(baseURL, 10*time.Second, 120*time.Second)
}

// NewWithTimeouts 注入 fast/slow 超时（测试用短超时断言 client 选择；生产用 New）。
func NewWithTimeouts(baseURL string, fast, slow time.Duration) *Client {
	return &Client{
		base: baseURL,
		fast: &http.Client{Timeout: fast},
		slow: &http.Client{Timeout: slow},
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

// Do 透传任意 edit-service 端点（design-JSON 编辑/暂存/大版本等），返回原始 body。
func (c *Client) Do(ctx context.Context, method, path string, body []byte) (json.RawMessage, error) {
	data, err := c.do(ctx, c.fast, method, path, body)
	if err != nil {
		return nil, err
	}
	return json.RawMessage(data), nil
}

// DoSlow 与 Do 同形但走 slow client：script run/save/rollback 触发沙箱执行
//（edit-service script_runner.RUN_TIMEOUT_S=60s），fast 的 10s 会先于 edit-service
// 超时，造成 Go 报错而 edit-service 已跑完落盘的三方状态分叉（M5 终审 C2）。
func (c *Client) DoSlow(ctx context.Context, method, path string, body []byte) (json.RawMessage, error) {
	data, err := c.do(ctx, c.slow, method, path, body)
	if err != nil {
		return nil, err
	}
	return json.RawMessage(data), nil
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

// PostDiff 透传 diff 请求（body 原样转发）。走 slow client 120s：edit-service
// 侧 diff 默认 60s 超时（EDIT_SERVICE_DIFF_TIMEOUT_S）先触发并回 504（diff timed
// out），writeEditErr 透传 504→504；slow 120s 兜底 edit-service 未回应的场景。
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

// GetScriptVersions 列出脚本大版本（chat 注入 diff 前判断是否 ≥2 个）。
func (c *Client) GetScriptVersions(ctx context.Context, modelID string) (*ScriptVersions, error) {
	data, err := c.do(ctx, c.fast, http.MethodGet, "/models/"+modelID+"/scripts", nil)
	if err != nil {
		return nil, err
	}
	var v ScriptVersions
	if err := json.Unmarshal(data, &v); err != nil {
		return nil, fmt.Errorf("edit service: decode scripts: %w", err)
	}
	return &v, nil
}

// PostScriptDiff 拉两个大版本的脚本 diff（text_diff + params_changes + stats）。
func (c *Client) PostScriptDiff(ctx context.Context, modelID, base, target string) (*ScriptDiffResult, error) {
	body, _ := json.Marshal(map[string]string{"base": base, "target": target})
	data, err := c.do(ctx, c.slow, http.MethodPost, "/models/"+modelID+"/script/diff", body)
	if err != nil {
		return nil, err
	}
	var d ScriptDiffResult
	if err := json.Unmarshal(data, &d); err != nil {
		return nil, fmt.Errorf("edit service: decode script diff: %w", err)
	}
	return &d, nil
}
