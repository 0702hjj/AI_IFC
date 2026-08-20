// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// jsondiff.go：方案级 JSON 字段级 diff（B3，交付对齐）——plan/bim_supplement
// 版本间的结构化差异（路径级 add/remove/modify），供 diff 端点与 agent 消费。
package store

import (
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
)

// JSONDiffEntry 是一条字段级差异（路径用 "a.b[0].c" 形式）。
type JSONDiffEntry struct {
	Op     string      `json:"op"` // add | remove | modify
	Path   string      `json:"path"`
	Before interface{} `json:"before,omitempty"`
	After  interface{} `json:"after,omitempty"`
}

// JSONDiff 比较两个 JSON 文档（必须都是合法 JSON 值），返回路径级差异。
// 数组按索引比较（元素替换 = remove+add 或 modify）；对象按 key 比较。
func JSONDiff(base, target []byte) ([]JSONDiffEntry, error) {
	var b, t interface{}
	if err := json.Unmarshal(base, &b); err != nil {
		return nil, errors.New("base 不是合法 JSON: " + err.Error())
	}
	if err := json.Unmarshal(target, &t); err != nil {
		return nil, errors.New("target 不是合法 JSON: " + err.Error())
	}
	var out []JSONDiffEntry
	diffValue("", b, t, &out)
	return out, nil
}

func diffValue(path string, b, t interface{}, out *[]JSONDiffEntry) {
	switch bt := b.(type) {
	case map[string]interface{}:
		tt, ok := t.(map[string]interface{})
		if !ok {
			diffScalar(path, b, t, out)
			return
		}
		// 对象：遍历 base key，缺失 = remove；遍历 target key，新增 = add；都有 = 递归
		for k, bv := range bt {
			tv, ok := tt[k]
			if !ok {
				*out = append(*out, JSONDiffEntry{Op: "remove", Path: joinPath(path, k), Before: bv})
				continue
			}
			diffValue(joinPath(path, k), bv, tv, out)
		}
		for k, tv := range tt {
			if _, ok := bt[k]; !ok {
				*out = append(*out, JSONDiffEntry{Op: "add", Path: joinPath(path, k), After: tv})
			}
		}
	case []interface{}:
		tt, ok := t.([]interface{})
		if !ok {
			diffScalar(path, b, t, out)
			return
		}
		// 数组：按索引比较（min 长度内逐元素递归；超长 = add/remove）
		n := len(bt)
		if len(tt) < n {
			n = len(tt)
		}
		for i := 0; i < n; i++ {
			diffValue(path+"["+strconv.Itoa(i)+"]", bt[i], tt[i], out)
		}
		for i := n; i < len(bt); i++ {
			*out = append(*out, JSONDiffEntry{Op: "remove", Path: path + "[" + strconv.Itoa(i) + "]", Before: bt[i]})
		}
		for i := n; i < len(tt); i++ {
			*out = append(*out, JSONDiffEntry{Op: "add", Path: path + "[" + strconv.Itoa(i) + "]", After: tt[i]})
		}
	default:
		diffScalar(path, b, t, out)
	}
}

func diffScalar(path string, b, t interface{}, out *[]JSONDiffEntry) {
	if !jsonEqual(b, t) {
		*out = append(*out, JSONDiffEntry{Op: "modify", Path: path, Before: b, After: t})
	}
}

// jsonEqual 宽松相等（数字比较：float64 精确比较；JSON 数值解析后同型）。
func jsonEqual(a, b interface{}) bool {
	switch av := a.(type) {
	case float64:
		bv, ok := b.(float64)
		return ok && av == bv
	case string:
		bv, ok := b.(string)
		return ok && av == bv
	case bool:
		bv, ok := b.(bool)
		return ok && av == bv
	case nil:
		return b == nil
	default:
		return false
	}
}

func joinPath(path, key string) string {
	if path == "" {
		return key
	}
	return path + "." + key
}

// JSONDiffSummary 渲染可读摘要（供 agent 工具结果 / 调试）：行列表。
func JSONDiffSummary(diff []JSONDiffEntry) string {
	if len(diff) == 0 {
		return "（无差异）"
	}
	out := ""
	for _, d := range diff {
		out += fmt.Sprintf("%s %s\n", d.Op, d.Path)
	}
	return out
}
