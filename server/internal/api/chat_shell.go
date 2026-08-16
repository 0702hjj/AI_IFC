// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_shell.go：notify 流程的 Imperative Shell——执行 Core（chat_core.go）产出的
// Action 列表，承载全部副作用（edit-service REST、staging 读取、制品归档、SetStatus/
// Enqueue、SSE 推送），并把每步执行结果归一为新 Event 回填 Core（多轮闭环）。
// 决策在 Core（planNotify），副作用在这里——唯一 IO 层。
package api

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"time"

	"ifcviewer/server/internal/editsvc"
)

// notifyTimeout 是 notify 流程的整体超时（现状 180s 保留，触发点 context 语义）。
const notifyTimeout = 180 * time.Second

// runShell 执行 Core 返回的 Action 批次并回填闭环：逐条按序执行（顺序即契约）；
// 每步成功结果归一为新 Event → 再调 planNotify 驱动下一轮；任一步失败 → fail-fast
// 归一 script/failed 事件 → Core 决策出 notify_failed → 推送后终止。
// cl 是本会话模型的编辑后端（notify 处按 kind 解析；dxf→cad :8200）。
func (h *ChatHandler) runShell(ctx context.Context, cs *chatSession, ev Event, st NotifyState, cl *editsvc.Client) {
	for {
		acts := planNotify(ev, st)
		if len(acts) == 0 {
			return
		}
		ev = Event{}
		for _, a := range acts {
			newEv, err := h.execAction(ctx, cs, a, cl)
			if err != nil {
				step := a.Step
				var se *stepError
				if errors.As(err, &se) {
					step = se.step
				}
				h.runFailed(ctx, cs, step, err, cl)
				return
			}
			if newEv.URI != "" {
				ev = newEv
			}
		}
	}
}

// execAction 执行单条 Action，返回成功后的新 Event（终态 Action 无回填 → URI 空）。
// 失败返回错误；save 的版本不可解析用 stepError 细分 step（save_script / save_version）。
func (h *ChatHandler) execAction(ctx context.Context, cs *chatSession, a Action, cl *editsvc.Client) (Event, error) {
	modelID := cs.ModelID
	switch a.Type {
	case ActionDiscardPending:
		if _, err := cl.DeletePending(ctx, modelID); err != nil {
			return Event{}, err
		}
		return newEvent("aiifc://model/"+modelID+"/pending/discarded", modelID, cs.ID, map[string]any{"discarded": 0}), nil

	case ActionStageScript:
		stageBody, _ := json.Marshal(map[string]any{"script": a.Script})
		if _, err := cl.Do(ctx, http.MethodPut, "/models/"+modelID+"/script", stageBody); err != nil {
			return Event{}, err
		}
		return newEvent("aiifc://model/"+modelID+"/script/staged", modelID, cs.ID, map[string]any{"staged": 1}), nil

	case ActionRunScript:
		if _, err := cl.DoSlow(ctx, http.MethodPost, "/models/"+modelID+"/script/run", nil); err != nil {
			return Event{}, err
		}
		return newEvent("aiifc://model/"+modelID+"/script/run", modelID, cs.ID, map[string]any{"ok": true}), nil

	case ActionSaveScript:
		saveRaw, err := cl.DoSlow(ctx, http.MethodPost, "/models/"+modelID+"/script/save", nil)
		if err != nil {
			return Event{}, failStep("save_script", err)
		}
		version, cause := resolveVersion(ctx, cl, modelID, saveRaw)
		if cause != nil {
			return Event{}, failStep("save_version", cause)
		}
		return newEvent("aiifc://model/"+modelID+"/script/saved", modelID, cs.ID, map[string]any{"version": version}), nil

	case ActionArchiveArtifact:
		// 归档失败仅日志（现状非致命）；staging 源在成功归档后删除。
		h.archiveStagingArtifact(modelID, a.Version, modelID+".py", "scripts", "py")
		return Event{}, nil

	case ActionReconvert:
		// run/save 已重写 uploads/{id}.ifc，正常必重转；同源未变（IFC mtime 不新于
		// XKT）的冗余重放（无脚本手术式路径、多次 idle 重触发）被去重跳过，保持 ready。
		if !h.deps.Q.EnqueueIfStale(modelID) {
			log.Printf("chat: notify %s: reconvert skipped (IFC not newer than XKT)", modelID)
			return Event{}, nil
		}
		log.Printf("chat: notify %s: reconvert queued", modelID)
		return Event{}, nil

	case ActionNotify:
		log.Printf("chat: notify %s committed (version %s)", modelID, a.Version)
		h.pushSystem(cs.ID, "viewer.committed", map[string]any{
			"modelId": modelID, "version": a.Version, "committed": true,
		})
		return Event{}, nil

	case ActionNotifyFailed:
		log.Printf("chat: notify %s step %s failed: %s", modelID, a.Step, a.Reason)
		h.pushSystem(cs.ID, "viewer.notify_failed", map[string]any{
			"modelId": modelID, "step": a.Step, "reason": a.Reason,
		})
		return Event{}, nil

	default:
		log.Printf("chat: notify %s: unknown action %q", modelID, a.Type)
		return Event{}, nil
	}
}

// runFailed 把一步失败归一为 script/failed 事件 → Core 决策 → 执行 notify_failed 推送。
func (h *ChatHandler) runFailed(ctx context.Context, cs *chatSession, step string, err error, cl *editsvc.Client) {
	log.Printf("chat: notify %s step %s failed: %v", cs.ModelID, step, err)
	failEv := newEvent("aiifc://model/"+cs.ModelID+"/script/failed", cs.ModelID, cs.ID,
		map[string]any{"step": step, "reason": err.Error()})
	for _, a := range planNotify(failEv, NotifyState{}) {
		if _, aerr := h.execAction(ctx, cs, a, cl); aerr != nil {
			log.Printf("chat: notify %s: execute %s: %v", cs.ModelID, a.Step, aerr)
		}
	}
}

// resolveVersion 从 save 响应解析版本号；响应未带 version 时兜底查 versions current
//（save 已落盘，GetVersions 必可读到新版本）。仍不可解析 → 返回 cause（显式 fail：
// 防空版本被静默吞掉导致 archive 跳过、staging 滞留、下次 idle 重复 save）。
func resolveVersion(ctx context.Context, ed *editsvc.Client, modelID string, saveRaw []byte) (string, error) {
	var saveResp struct {
		Version string `json:"version"`
	}
	if err := json.Unmarshal(saveRaw, &saveResp); err != nil || saveResp.Version == "" {
		if vers, verr := ed.GetVersions(ctx, modelID); verr == nil && vers.Current != "" {
			return vers.Current, nil
		} else {
			var cause error
			switch {
			case err != nil:
				cause = fmt.Errorf("decode save response: %w", err)
			case verr != nil:
				cause = fmt.Errorf("fallback GetVersions: %w", verr)
			default:
				cause = errors.New("save succeeded but no version (decode ok, versions current empty)")
			}
			return "", cause
		}
	}
	return saveResp.Version, nil
}

// newEvent 构造总线事件（payload 序列化失败视为空载荷——字段解析零容忍即回退零值）。
func newEvent(uri, modelID, sessionID string, payload map[string]any) Event {
	raw, _ := json.Marshal(payload)
	return Event{URI: uri, ModelID: modelID, SessionID: sessionID, Payload: raw}
}

// stepError 携带失败动作的具体 step（save_script / save_version 细分；其余动作步名即 Action.Step）。
type stepError struct {
	step string
	err  error
}

func (e *stepError) Error() string { return e.err.Error() }
func (e *stepError) Unwrap() error { return e.err }

func failStep(step string, err error) error { return &stepError{step: step, err: err} }
