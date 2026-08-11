// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package api

import (
	"encoding/json"
	"reflect"
	"testing"
)

// chat_core_test.go：notify 流程 Pure Core（planNotify 纯函数）的分支单测。
// Core 零 IO：只断言 Event + State → Action 列表（顺序即契约），不触碰磁盘/REST/SSE。

func TestPlanNotifyIdleDirtyBoundWithScript(t *testing.T) {
	st := NotifyState{Dirty: true, Bound: true, HasStagingScript: true, Script: "print(1)"}
	ev := Event{URI: "aiifc://chat/c_1/idle", SessionID: "c_1", Payload: json.RawMessage(`{}`)}
	got := planNotify(ev, st)
	want := []Action{
		{Type: ActionDiscardPending, Step: "discard_pending"},
		{Type: ActionStageScript, Step: "stage_script", Script: "print(1)"},
		{Type: ActionRunScript, Step: "run_script"},
		{Type: ActionSaveScript, Step: "save_script"},
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("planNotify(idle+dirty+bound+script) = %+v, want %+v", got, want)
	}
}

func TestPlanNotifyIdleDirtyBoundNoScript(t *testing.T) {
	st := NotifyState{Dirty: true, Bound: true, HasStagingScript: false}
	ev := Event{URI: "aiifc://chat/c_2/idle", SessionID: "c_2", Payload: json.RawMessage(`{}`)}
	got := planNotify(ev, st)
	want := []Action{{Type: ActionDiscardPending, Step: "discard_pending"}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("planNotify(idle+dirty+bound+无脚本) = %+v, want %+v", got, want)
	}
}

func TestPlanNotifyIdleNotDirtyOrNotBoundIsNil(t *testing.T) {
	cases := []struct {
		name string
		st   NotifyState
	}{
		{"not_dirty", NotifyState{Dirty: false, Bound: true}},
		{"not_bound", NotifyState{Dirty: true, Bound: false}},
		{"neither", NotifyState{Dirty: false, Bound: false}},
	}
	ev := Event{URI: "aiifc://chat/c_3/idle", SessionID: "c_3", Payload: json.RawMessage(`{}`)}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := planNotify(ev, tc.st); got != nil {
				t.Fatalf("planNotify(idle + %s) = %+v, want nil", tc.name, got)
			}
		})
	}
}

func TestPlanNotifyIdleWrongSessionIsNil(t *testing.T) {
	// URI 与 SessionID 不匹配（非本会话的 idle）→ 不触发。
	st := NotifyState{Dirty: true, Bound: true}
	ev := Event{URI: "aiifc://chat/c_other/idle", SessionID: "c_9", Payload: json.RawMessage(`{}`)}
	if got := planNotify(ev, st); got != nil {
		t.Fatalf("planNotify(idle URI/Session 不匹配) = %+v, want nil", got)
	}
}

func TestPlanNotifySavedEventRoundTwo(t *testing.T) {
	ev := Event{
		URI:     "aiifc://model/m_aaaaaaaaaaaaaaaa/script/saved",
		ModelID: "m_aaaaaaaaaaaaaaaa",
		Payload: json.RawMessage(`{"version":"v3"}`),
	}
	got := planNotify(ev, NotifyState{})
	want := []Action{
		{Type: ActionArchiveArtifact, Step: "archive", Version: "v3"},
		{Type: ActionReconvert, Step: "reconvert"},
		{Type: ActionNotify, Step: "notify", Version: "v3"},
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("planNotify(saved) = %+v, want %+v", got, want)
	}
}

func TestPlanNotifyDiscardedNoScriptRoundTwo(t *testing.T) {
	ev := Event{
		URI:     "aiifc://model/m_bbbbbbbbbbbbbbbb/pending/discarded",
		ModelID: "m_bbbbbbbbbbbbbbbb",
		Payload: json.RawMessage(`{"discarded":0}`),
	}
	got := planNotify(ev, NotifyState{HasStagingScript: false})
	want := []Action{
		{Type: ActionReconvert, Step: "reconvert"},
		{Type: ActionNotify, Step: "notify"}, // Version 空 → viewer.committed 无版本
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("planNotify(discarded+无脚本) = %+v, want %+v", got, want)
	}
}

func TestPlanNotifyFailedEvent(t *testing.T) {
	ev := Event{
		URI:     "aiifc://model/m_cccccccccccccccc/script/failed",
		ModelID: "m_cccccccccccccccc",
		Payload: json.RawMessage(`{"step":"run_script","reason":"sandbox boom"}`),
	}
	got := planNotify(ev, NotifyState{})
	want := []Action{{Type: ActionNotifyFailed, Step: "run_script", Reason: "sandbox boom"}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("planNotify(failed) = %+v, want %+v", got, want)
	}
}

// TestPlanNotifyIntermediateEventsNil 断言中间态事件（staged/run）与「有脚本时的 discard」不产出新动作。
func TestPlanNotifyIntermediateEventsNil(t *testing.T) {
	cases := []struct {
		name string
		ev   Event
		st   NotifyState
	}{
		{"staged", Event{URI: "aiifc://model/m_x/script/staged", ModelID: "m_x", Payload: json.RawMessage(`{"staged":1}`)}, NotifyState{}},
		{"run", Event{URI: "aiifc://model/m_x/script/run", ModelID: "m_x", Payload: json.RawMessage(`{"ok":true}`)}, NotifyState{}},
		{"discard_with_script", Event{URI: "aiifc://model/m_x/pending/discarded", ModelID: "m_x", Payload: json.RawMessage(`{"discarded":0}`)}, NotifyState{HasStagingScript: true}},
		{"unknown_uri", Event{URI: "aiifc://model/m_x/edited", ModelID: "m_x", Payload: json.RawMessage(`{"path":"x"}`)}, NotifyState{Dirty: true}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := planNotify(tc.ev, tc.st); got != nil {
				t.Fatalf("planNotify(%s) = %+v, want nil", tc.name, got)
			}
		})
	}
}

func TestNotifyPayloadHelpers(t *testing.T) {
	if v := payloadVersion(Event{Payload: json.RawMessage(`{"version":"v9"}`)}); v != "v9" {
		t.Fatalf("payloadVersion = %q, want v9", v)
	}
	if v := payloadVersion(Event{Payload: json.RawMessage(`{"no":"version"}`)}); v != "" {
		t.Fatalf("payloadVersion(无 version) = %q, want empty", v)
	}
	if v := payloadVersion(Event{}); v != "" {
		t.Fatalf("payloadVersion(空载荷) = %q, want empty", v)
	}

	if s := stepOf(Event{Payload: json.RawMessage(`{"step":"save_version"}`)}); s != "save_version" {
		t.Fatalf("stepOf = %q, want save_version", s)
	}
	if r := reasonOf(Event{Payload: json.RawMessage(`{"reason":"boom"}`)}); r != "boom" {
		t.Fatalf("reasonOf = %q, want boom", r)
	}

	if !isFailure(Event{URI: "aiifc://model/m_x/script/failed"}) {
		t.Error("isFailure(failed URI) = false, want true")
	}
	if isFailure(Event{URI: "aiifc://model/m_x/script/saved"}) {
		t.Error("isFailure(saved URI) = true, want false")
	}
	if isFailure(Event{URI: ""}) {
		t.Error("isFailure(空 URI) = true, want false")
	}
}

// TestPlanNotifyPureZeroIO 自证 Core 零 IO：给定相同输入两次调用结果一致（幂等、无隐藏状态）。
func TestPlanNotifyPureZeroIO(t *testing.T) {
	st := NotifyState{Dirty: true, Bound: true, HasStagingScript: true, Script: "print(1)"}
	ev := Event{URI: "aiifc://chat/c_7/idle", SessionID: "c_7", Payload: json.RawMessage(`{}`)}
	first := planNotify(ev, st)
	second := planNotify(ev, st)
	if !reflect.DeepEqual(first, second) {
		t.Fatalf("planNotify 两次调用结果不一致（非纯函数）: %+v vs %+v", first, second)
	}
}
