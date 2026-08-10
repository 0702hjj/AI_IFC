// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

// chat_orchestrator.go：三连触发（file.edited/session.idle → notify）、制品归档、
// 骨架 IFC 模板与 GlobalId 生成、空白项目创建。
package api

import (
	"context"
	"crypto/rand"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"ifcviewer/server/internal/editsvc"
	"ifcviewer/server/internal/opencode"
)

// --- 空白项目：点击「新建」即完成初始化（骨架模型 + modelId），agent 只是后续的修改者 ---

const ifcBase64Alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"

// newGlobalID 生成 IFC GlobalId（22 字符，首字符 0-3，128bit 随机数按 IFC base64 编码）。
func newGlobalID() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	b[0] &= 0x03
	var sb strings.Builder
	sb.Grow(22)
	acc, nbits := 0, 0
	for _, by := range b {
		acc = acc<<8 | int(by)
		nbits += 8
		for nbits >= 6 {
			nbits -= 6
			sb.WriteByte(ifcBase64Alphabet[(acc>>nbits)&0x3F])
		}
	}
	if nbits > 0 {
		sb.WriteByte(ifcBase64Alphabet[(acc<<(6-nbits))&0x3F])
	}
	return sb.String()[:22]
}

// skeletonIFC 是最小合法 IFC（仅 IfcProject + 几何上下文 + 单位），
// converter/edit-service 均已验证可正常消化。两个 %s = project GlobalId、项目名。
const skeletonIFC = `ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');
FILE_NAME('skeleton.ifc','2026-01-01T00:00:00',(''),(''),'ifcopenshell','AI_IFC','');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCPROJECT('%s',#5,'%s',$,$,$,$,(#9),#13);
#5=IFCOWNERHISTORY($,$,$,$,$,$,$,$);
#9=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#10,$);
#10=IFCAXIS2PLACEMENT3D(#11,$,$);
#11=IFCCARTESIANPOINT((0.,0.,0.));
#13=IFCUNITASSIGNMENT((#14));
#14=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);
ENDSEC;
END-ISO-10303-21;
`

// ifcStringEscape 转义 IFC STEP 字符串（单引号双写）。
func ifcStringEscape(s string) string { return strings.ReplaceAll(s, "'", "''") }

// createProject 创建空白项目：写入骨架 IFC 并注册为模型（modelId 即刻就位），
// 入队转换。之后 AI 从零构建走的是与改模型完全相同的主链路。
func (h *ChatHandler) createProject(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Title string `json:"title"`
	}
	_ = json.NewDecoder(r.Body).Decode(&body) // title 可空
	if body.Title == "" {
		body.Title = "AI 项目"
	}
	content := fmt.Sprintf(skeletonIFC, newGlobalID(), ifcStringEscape(body.Title))
	m, err := h.deps.St.Create(body.Title+".ifc", int64(len(content)), strings.NewReader(content))
	if err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	h.deps.Q.Enqueue(m.ID)
	writeJSON(w, m)
}

// onEvent 是 P2 三连触发器：file.edited 命中工作区 → 置 dirty；
// session.idle + dirty + bound → 异步执行 notify 三连。
func (h *ChatHandler) onEvent(ev opencode.Event) {
	switch ev.Type {
	case "file.edited":
		var p struct {
			File string `json:"file"`
		}
		if err := json.Unmarshal(ev.Properties, &p); err != nil {
			return
		}
		mid := modelIDFromEditedFile(p.File)
		if mid == "" {
			return
		}
		h.mu.Lock()
		for _, cs := range h.sessions {
			if cs.ModelID == mid {
				cs.dirty = true
			}
		}
		h.mu.Unlock()
	case "session.idle":
		ocSID := ev.SessionID()
		if ocSID == "" {
			return
		}
		h.mu.Lock()
		cid, ok := h.byOC[ocSID]
		cs := h.sessions[cid]
		if !ok || cs == nil || cs.ModelID == "" {
			h.mu.Unlock()
			return
		}
		// 变更检测：file.edited 已置 dirty（write/edit 工具路径）；
		// 否则兜底查工作区 mtime（agent 用 bash 跑脚本改文件时 opencode 不发 file.edited）。
		dirtyNow := cs.dirty
		if !dirtyNow {
			if fi, err := os.Stat(filepath.Join(h.deps.DataDir, "uploads", cs.ModelID+".ifc")); err == nil && fi.ModTime().After(cs.lastCheck) {
				dirtyNow = true
			}
		}
		if !dirtyNow {
			h.mu.Unlock()
			return
		}
		cs.dirty = false // 同一 turn 只触发一次
		cs.lastCheck = time.Now()
		h.mu.Unlock()
		log.Printf("chat: session %s idle with modified model %s → notify", ocSID, cs.ModelID)
		go h.notify(cs)
	}
}

// modelIDFromEditedFile 从 file.edited 的路径提取 modelId（命中 {dataDir}/uploads/{id}.ifc）。
func modelIDFromEditedFile(file string) string {
	base := filepath.Base(filepath.ToSlash(file))
	if !strings.HasSuffix(base, ".ifc") || !strings.Contains(filepath.ToSlash(file), "/uploads/") {
		return ""
	}
	id := strings.TrimSuffix(base, ".ifc")
	if !modelIDRe.MatchString(id) {
		return ""
	}
	return id
}

var modelIDRe = regexp.MustCompile(`^m_[0-9a-f]{16}$`)

// notify 是 AI 大改后的固定流程（顺序不可换）：
// ① DELETE pending（强制 edit-service 从磁盘重载 = 坏文件自检，防旧内存模型覆盖 agent 的修改）
// ② staging 有构建脚本（{dataDir}/staging/{modelId}.py）→ script 管线：
//   PUT /script（暂存）→ POST /script/run（沙箱试跑）→ POST /script/save（落 v{n}
//   大版本 + IFC 快照）；无脚本（手术式编辑）→ 跳过，仅重转。
// ③ 置 converting + 入队重转（run/save 已重写 uploads/{id}.ifc，必须重转）。
// 完成后向该会话推送 viewer.committed；失败推 viewer.notify_failed。
func (h *ChatHandler) notify(cs *chatSession) {
	ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
	defer cancel()
	modelID := cs.ModelID
	fail := func(step string, err error) {
		log.Printf("chat: notify %s step %s failed: %v", modelID, step, err)
		h.pushSystem(cs.ID, "viewer.notify_failed", map[string]any{
			"modelId": modelID, "step": step, "reason": err.Error(),
		})
	}

	if _, err := h.deps.Ed.DeletePending(ctx, modelID); err != nil {
		fail("discard_pending", err)
		return
	}
	version := ""
	scriptPath := filepath.Join(h.deps.DataDir, "staging", modelID+".py")
	if fileExists(scriptPath) {
		content, err := os.ReadFile(scriptPath)
		if err != nil {
			fail("read_staging_script", err)
			return
		}
		stageBody, _ := json.Marshal(map[string]any{"script": string(content)})
		if _, err := h.deps.Ed.Do(ctx, http.MethodPut, "/models/"+modelID+"/script", stageBody); err != nil {
			fail("stage_script", err)
			return
		}
		if _, err := h.deps.Ed.DoSlow(ctx, http.MethodPost, "/models/"+modelID+"/script/run", nil); err != nil {
			fail("run_script", err)
			return
		}
		saveRaw, err := h.deps.Ed.DoSlow(ctx, http.MethodPost, "/models/"+modelID+"/script/save", nil)
		if err != nil {
			fail("save_script", err)
			return
		}
		var saveResp struct {
			Version string `json:"version"`
		}
		if err := json.Unmarshal(saveRaw, &saveResp); err != nil || saveResp.Version == "" {
			// 兜底：save 响应解码失败（或未带 version）时回退查 versions current
			//（save 已落盘，GetVersions 必可读到新版本）。
			if vers, verr := h.deps.Ed.GetVersions(ctx, modelID); verr == nil && vers.Current != "" {
				version = vers.Current
			} else if verr != nil {
				log.Printf("chat: notify %s: decode save response: %v, fallback versions: %v", modelID, err, verr)
			}
		} else {
			version = saveResp.Version
		}
	}
	// 重转：script save / 手术式编辑均已重写 uploads/{id}.ifc
	if err := h.deps.St.SetStatus(modelID, "converting", ""); err != nil {
		log.Printf("chat: notify %s: set converting: %v", modelID, err)
	}
	if !h.deps.Q.Enqueue(modelID) {
		log.Printf("chat: notify %s: conversion already pending", modelID)
	}
	// ⑤ 制品归档（过程与结果同存，随版本同步）：staging/{modelId}.py → scripts/v{n}.py。
	// 无对应 staging 文件则跳过（手术式编辑无脚本）。
	h.archiveStagingArtifact(modelID, version, modelID+".py", "scripts", "py")
	out := map[string]any{
		"modelId": modelID, "version": version, "committed": true,
	}
	log.Printf("chat: notify %s committed (version %s)", modelID, version)
	h.pushSystem(cs.ID, "viewer.committed", out)
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

// copyFile 复制文件（先写 tmp 再改名，同 viewer 原子写模式）。
func copyFile(src, dst string) error {
	data, err := os.ReadFile(src)
	if err != nil {
		return err
	}
	tmp := dst + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, dst)
}

// archiveStagingArtifact 把 staging 区的一个制品归档到 models/{id}/{subdir}/v{n}.{dstSuffix}（随版本同步）。
// stagingName 是 staging 区文件全名（如 "{id}.py"）；不存在则跳过。
// 归档成功后删除 staging 源文件（同脚本归档语义）。version 为空（commit 未产生版本）则整体跳过。
func (h *ChatHandler) archiveStagingArtifact(modelID, version, stagingName, subdir, dstSuffix string) {
	if version == "" {
		return
	}
	src := filepath.Join(h.deps.DataDir, "staging", stagingName)
	if !fileExists(src) {
		return
	}
	dstDir := filepath.Join(h.deps.DataDir, "models", modelID, subdir)
	dst := filepath.Join(dstDir, version+"."+dstSuffix)
	if err := os.MkdirAll(dstDir, 0o755); err != nil {
		log.Printf("chat: mkdir %s: %v", dstDir, err)
		return
	}
	if err := copyFile(src, dst); err != nil {
		log.Printf("chat: archive %s %s: %v", subdir, modelID, err)
		return
	}
	os.Remove(src)
	log.Printf("chat: archived %s/%s.%s", subdir, version, dstSuffix)
}

// --- W-0016：AI 循环接入——把最近两个大版本的脚本 diff 注入下次 prompt ---

// scriptDiffContextMaxBytes 是注入 prompt 的脚本 diff 全量文本上限（4KB）；
// 超长降级为 stats + PARAMS 摘要（不含全量文本），防爆上下文。
const scriptDiffContextMaxBytes = 4096

// scriptDiffContext 拉取模型最近两个大版本的脚本 diff，渲染为系统上下文片段。
// 不足两个大版本（含无脚本的 legacy 模型）、edit-service 不可达、diff 拉取失败：
// 均返回 ""——调用方保持现行为（只注入模型路径），不阻塞消息下发。
func (h *ChatHandler) scriptDiffContext(ctx context.Context, modelID string) string {
	if h.deps.Ed == nil {
		return ""
	}
	vers, err := h.deps.Ed.GetScriptVersions(ctx, modelID)
	if err != nil {
		log.Printf("chat: script versions %s: %v（降级不注入 diff）", modelID, err)
		return ""
	}
	if len(vers.Scripts) < 2 {
		return ""
	}
	base := vers.Scripts[len(vers.Scripts)-2].Version
	target := vers.Scripts[len(vers.Scripts)-1].Version
	d, err := h.deps.Ed.PostScriptDiff(ctx, modelID, base, target)
	if err != nil {
		log.Printf("chat: script diff %s %s→%s: %v（降级不注入 diff）", modelID, base, target, err)
		return ""
	}
	return formatScriptDiffContext(modelID, d)
}

// formatScriptDiffContext 渲染注入文本：脚本 diff（超 4KB 给摘要）+ PARAMS 变化 + 纪律提示。
func formatScriptDiffContext(modelID string, d *editsvc.ScriptDiffResult) string {
	params := "无"
	if len(d.ParamsChanges) > 0 {
		if b, err := json.Marshal(d.ParamsChanges); err == nil {
			params = string(b)
		}
	}
	var b strings.Builder
	fmt.Fprintf(&b, "本模型由构建脚本生成（script-as-source：脚本是唯一事实源，改模型 = 改脚本后 save）。最近两个大版本（%s → %s）的脚本变化：", d.Base, d.Target)
	if len(d.TextDiff) <= scriptDiffContextMaxBytes {
		fmt.Fprintf(&b, "\n脚本 diff（+%d/-%d 行）：\n```diff\n%s\n```",
			d.Stats.Added, d.Stats.Removed, strings.TrimRight(d.TextDiff, "\n"))
	} else {
		fmt.Fprintf(&b, "\n脚本 diff 超 4KB，仅给摘要：+%d/-%d 行（全量可经 POST /api/v1/models/%s/script/diff 拉取）。",
			d.Stats.Added, d.Stats.Removed, modelID)
	}
	fmt.Fprintf(&b, "\nPARAMS 变化：%s", params)
	b.WriteString("\n纪律：在既有构建脚本上做增量修改，禁止整体重写；保持 PARAMS 的 key 稳定（只改值或新增 key，不改既有 key 名）。")
	return b.String()
}
