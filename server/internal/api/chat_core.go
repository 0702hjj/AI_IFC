// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

// chat_core.go：notify 流程的 Pure Core——Event + State → Action 列表纯函数（零 IO）。
// 决策与副作用分离：Core 只回答「这个事件 + 这个状态，下一步该执行哪些 Action」；
// 副作用全部由 Shell（chat_shell.go）执行，并把每步结果转回新 Event 驱动下一轮。
package api

import (
	"encoding/json"
	"strings"
)

// Event 是总线最小契约（Shell 适配器归一后的统一形态；本任务由 onEvent/notify 组装）。
type Event struct {
	URI       string          // "aiifc://model/{id}/script/saved"
	ModelID   string          // 归一提取（空则无 modelId 上下文）
	SessionID string          // chatSessionId（chat 域事件）
	Seq       uint64          // 每会话递增（幂等去重用；M6 事件总线落地时启用）
	Payload   json.RawMessage // 事件载荷（version/step/reason 等）
}

// Action 是 Shell 要执行的副作用原子操作（纯声明，零 IO）。
type Action struct {
	Type    ActionType
	Step    string // notify_failed 的 step 名（现状语义保留）
	Script  string // stage_script：脚本全文（Shell 注入，来自 staging 读取）
	Version string // archive/reconvert/notify：save 回填的版本号
	Reason  string // notify_failed 的原因
}

// ActionType 标识一条副作用 Action。
type ActionType string

const (
	ActionDiscardPending  ActionType = "discard_pending"
	ActionStageScript     ActionType = "stage_script"
	ActionRunScript       ActionType = "run_script"
	ActionSaveScript      ActionType = "save_script"
	ActionArchiveArtifact ActionType = "archive_artifact"
	ActionReconvert       ActionType = "reconvert"
	ActionNotify          ActionType = "notify"        // → 推 viewer.committed
	ActionNotifyFailed    ActionType = "notify_failed" // → 推 viewer.notify_failed
)

// NotifyState 是决策所需的最小状态快照（纯数据，无 IO 句柄；staging 内容由 Shell 读好注入）。
type NotifyState struct {
	Dirty            bool   // file.edited 或 mtime 兜底置位
	HasStagingScript bool   // staging/{modelId}.py 存在
	Script           string // staging/{modelId}.py 全文（Shell 注入）
	Bound            bool   // 会话已绑定 modelId
}

// planNotify 是 notify 流程的 Core：Event + State → Action 列表。
// 纯函数：不 IO（不读 staging、不调 edit-service、不写状态）；返回的 Action 顺序即
// Shell 必须遵守的执行顺序（顺序即契约）。
//
// 两轮语义（spec §5.2）：第一轮 idle+dirty+bound → [discard_pending]（坏文件自检），
// 有脚本则追加 script 管线 [stage_script, run_script, save_script]（版本不可知 →
// 收尾延后到 saved 事件）；save 成功产出 saved 事件 → 第二轮 [archive_artifact,
// reconvert, notify(version)]。无脚本路径 discard 完成即收尾 [reconvert, notify(空版本)]。
// failed 事件 → [notify_failed(step, reason)]。
func planNotify(ev Event, st NotifyState) []Action {
	switch {
	case ev.URI == "aiifc://chat/"+ev.SessionID+"/idle" && st.Dirty && st.Bound:
		acts := []Action{{Type: ActionDiscardPending, Step: "discard_pending"}}
		if st.HasStagingScript {
			acts = append(acts,
				Action{Type: ActionStageScript, Step: "stage_script", Script: st.Script},
				Action{Type: ActionRunScript, Step: "run_script"},
				Action{Type: ActionSaveScript, Step: "save_script"},
			)
		}
		return acts

	case ev.URI == "aiifc://model/"+ev.ModelID+"/script/saved":
		return []Action{
			{Type: ActionArchiveArtifact, Step: "archive", Version: payloadVersion(ev)},
			{Type: ActionReconvert, Step: "reconvert"},
			{Type: ActionNotify, Step: "notify", Version: payloadVersion(ev)},
		}

	case ev.URI == "aiifc://model/"+ev.ModelID+"/pending/discarded" && !st.HasStagingScript:
		return []Action{
			{Type: ActionReconvert, Step: "reconvert"},
			{Type: ActionNotify, Step: "notify"}, // Version 空 → viewer.committed 无版本
		}

	case isFailure(ev): // URI == "…/script/failed"（含取消归一）
		return []Action{{Type: ActionNotifyFailed, Step: stepOf(ev), Reason: reasonOf(ev)}}

	default: // 中间状态事件（staged / run / 中间 discard）无需新动作
		return nil
	}
}

// payloadVersion 从 saved 事件载荷解析版本号（零 IO，只解析 ev.Payload）。
func payloadVersion(ev Event) string {
	var p struct {
		Version string `json:"version"`
	}
	_ = json.Unmarshal(ev.Payload, &p)
	return p.Version
}

// stepOf 从 failed 事件载荷解析失败 step 名（零 IO）。
func stepOf(ev Event) string {
	var p struct {
		Step string `json:"step"`
	}
	_ = json.Unmarshal(ev.Payload, &p)
	return p.Step
}

// reasonOf 从 failed 事件载荷解析失败原因（零 IO）。
func reasonOf(ev Event) string {
	var p struct {
		Reason string `json:"reason"`
	}
	_ = json.Unmarshal(ev.Payload, &p)
	return p.Reason
}

// isFailure 判定事件是否为 script/failed（失败归一；含取消归一）。
func isFailure(ev Event) bool {
	return strings.HasSuffix(ev.URI, "/script/failed")
}
