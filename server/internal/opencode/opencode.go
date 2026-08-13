// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// Package opencode 是 opencode serve（AI agent 服务）的 HTTP/SSE 客户端。
// 非 2xx 响应映射为带状态码的 *Error，由 handler 层转 envelope。
package opencode

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// Error 表示 opencode serve 返回的非 2xx 响应。
type Error struct {
	Status int
	Body   string
}

func (e *Error) Error() string {
	return fmt.Sprintf("opencode serve: status %d: %s", e.Status, e.Body)
}

// Session 对应 opencode 的会话对象（仅取 chat 模块需要的字段）。
type Session struct {
	ID    string `json:"id"`
	Title string `json:"title"`
}

// Event 是 opencode SSE 总线上的一条事件（type + 未解析的 properties）。
type Event struct {
	Type       string          `json:"type"`
	Properties json.RawMessage `json:"properties"`
}

// SessionID 尽力从 properties 中提取 sessionID（不同事件结构不同）。
// 提取不到（如 server.connected、file.edited）返回空串，由调用方决定广播。
func (e Event) SessionID() string {
	var p struct {
		SessionID string `json:"sessionID"`
		Info      struct {
			SessionID string `json:"sessionID"`
		} `json:"info"`
		Part struct {
			SessionID string `json:"sessionID"`
		} `json:"part"`
	}
	if err := json.Unmarshal(e.Properties, &p); err != nil {
		return ""
	}
	if p.SessionID != "" {
		return p.SessionID
	}
	if p.Info.SessionID != "" {
		return p.Info.SessionID
	}
	return p.Part.SessionID
}

type Client struct {
	base string
	hc   *http.Client // 普通调用 30s；SSE 订阅单独建无超时请求
}

func New(baseURL string) *Client {
	return &Client{base: baseURL, hc: &http.Client{Timeout: 30 * time.Second}}
}

func (c *Client) do(ctx context.Context, method, path string, body []byte) ([]byte, error) {
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
	resp, err := c.hc.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, &Error{Status: resp.StatusCode, Body: string(data)}
	}
	return data, nil
}

// CreateSession 创建 opencode 会话。
func (c *Client) CreateSession(ctx context.Context, title string) (*Session, error) {
	body, _ := json.Marshal(map[string]string{"title": title})
	data, err := c.do(ctx, http.MethodPost, "/session", body)
	if err != nil {
		return nil, err
	}
	var s Session
	if err := json.Unmarshal(data, &s); err != nil {
		return nil, err
	}
	return &s, nil
}

// PromptAsync 异步发送消息（204，响应内容走 SSE 事件流）。
func (c *Client) PromptAsync(ctx context.Context, sessionID, text, agent string) error {
	part := map[string]string{"type": "text", "text": text}
	payload := map[string]any{"parts": []map[string]string{part}}
	if agent != "" {
		payload["agent"] = agent
	}
	body, _ := json.Marshal(payload)
	_, err := c.do(ctx, http.MethodPost, "/session/"+sessionID+"/prompt_async", body)
	return err
}

// Abort 中止会话当前执行（POST /session/{id}/abort，无 body）。
// opencode 会停止当前 turn 并发 session.idle + 进行中 part 的 removed 事件。
func (c *Client) Abort(ctx context.Context, sessionID string) error {
	_, err := c.do(ctx, http.MethodPost, "/session/"+sessionID+"/abort", nil)
	return err
}

// MessageWithParts 是历史消息条目（text part 已足以回填聊天）。
type MessageWithParts struct {
	Info struct {
		ID   string `json:"id"`
		Role string `json:"role"`
	} `json:"info"`
	Parts []struct {
		Type string `json:"type"`
		Text string `json:"text"`
	} `json:"parts"`
}

// GetMessages 拉取会话历史消息（GET /session/:id/message）。
func (c *Client) GetMessages(ctx context.Context, sessionID string) ([]MessageWithParts, error) {
	data, err := c.do(ctx, http.MethodGet, "/session/"+sessionID+"/message", nil)
	if err != nil {
		return nil, err
	}
	var msgs []MessageWithParts
	if err := json.Unmarshal(data, &msgs); err != nil {
		return nil, err
	}
	return msgs, nil
}

// Subscribe 订阅 opencode 全局事件流（GET /event）。
// 返回的 channel 在连接断开时关闭——重连与退避由调用方负责。
func (c *Client) Subscribe(ctx context.Context) (<-chan Event, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.base+"/event", nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "text/event-stream")
	resp, err := (&http.Client{}).Do(req) // 无超时：长连接
	if err != nil {
		return nil, err
	}
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		return nil, &Error{Status: resp.StatusCode, Body: string(body)}
	}
	ch := make(chan Event, 64)
	go func() {
		defer close(ch)
		defer resp.Body.Close()
		sc := bufio.NewScanner(resp.Body)
		sc.Buffer(make([]byte, 0, 256*1024), 4*1024*1024)
		for sc.Scan() {
			line := sc.Bytes()
			if !bytes.HasPrefix(line, []byte("data:")) {
				continue
			}
			payload := bytes.TrimSpace(bytes.TrimPrefix(line, []byte("data:")))
			var ev Event
			if err := json.Unmarshal(payload, &ev); err != nil {
				continue
			}
			select {
			case ch <- ev:
			case <-ctx.Done():
				return
			}
		}
	}()
	return ch, nil
}
