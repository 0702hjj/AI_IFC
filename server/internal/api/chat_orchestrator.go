// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_orchestrator.go：turn 结束触发 notify、制品归档、
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
	"ifcviewer/server/internal/store"
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

// skeletonProjectIFC 渲染骨架 IFC 内容（复用方：createProject REST 路由 +
// agent create_project 工具——同一生成逻辑，单一事实源）。
func skeletonProjectIFC(globalID, escapedTitle string) string {
	return fmt.Sprintf(skeletonIFC, globalID, escapedTitle)
}

// skeletonDXF 是最小合法 DXF（空图纸：HEADER + 空 ENTITIES）。
// services/cad 的 model_upload_path 守卫要求 uploads/{id}.dxf 存在——新建
// kind=dxf 项目用空图起步，几何由后续脚本构建。
const skeletonDXF = `0
SECTION
2
HEADER
9
$ACADVER
1
AC1009
0
ENDSEC
0
SECTION
2
ENTITIES
0
ENDSEC
0
EOF
`

// createProject 创建空白项目（项目级，A1）：projectID + 首交付模型（kind 可选
// ifc/dxf，默认 ifc）。返回兼容结构（id = 首模型 id，前端 ModelInfo 旧逻辑可用；
// projectId = 项目 id，A2 会话绑定用它）。之后 AI 从零构建走与改模型相同的主链路。
func (h *ChatHandler) createProject(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Title string `json:"title"`
		Kind  string `json:"kind"`
	}
	_ = json.NewDecoder(r.Body).Decode(&body) // title/kind 可空
	kind := body.Kind
	if kind == "" {
		kind = store.KindIFC
	}
	m, p, err := h.createProjectForAgent(r.Context(), body.Title, kind)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	// Ps 未配置（旧装配降级）：返回单模型（旧行为，前端 ModelInfo 契约不变）。
	if p == nil {
		writeJSON(w, m)
		return
	}
	writeJSON(w, map[string]any{
		"id":        m.ID, // 首模型（兼容前端 ModelInfo）
		"projectId": p.ID,
		"title":     p.Title,
		"kind":      m.Kind,
		"status":    m.Status,
		"createdAt": p.CreatedAt,
		"models":    p.Models,
	})
}

// notifyIfDirty 是 agent loop 结束（turn/end，事件流关闭）后的变更检测 + 触发点：
// 会话绑定模型且工作区 IFC 被改（mtime 晚于 lastCheck）→ 异步执行 notify
// （Core+Shell 闭环落盘，顺序契约不变）。
func (h *ChatHandler) notifyIfDirty(cs *chatSession) {
	if cs.ModelID == "" {
		return
	}
	h.mu.Lock()
	// 变更检测：查工作区 mtime（agent 工具/bash 改文件即新于 lastCheck）。
	// 已知死路（有意保留）：兜底只 stat {id}.ifc——dxf 模型的源文件是 {id}.dxf，
	// 永远 stat 不到，mtime 兜底对 dxf 不生效；dxf 会话的变更检测只靠工具面
	// markSessionDirty 的精确信号（write/edit 类工具成功即置 dirty）。当前 agent
	// 工具集不发 bash/裸文件写，主链路无回归；若未来放开 dxf 的自由文件工具，
	// 兜底需按 kind 改 stat 源文件（SourcePath）。
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
	log.Printf("chat: session %s turn end with modified model %s → notify", cs.AgentID, cs.ModelID)
	go h.notify(cs)
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

// notify 是 AI 大改后的固定流程入口（Shell 壳）：组装第一轮 Event + NotifyState
// （读 staging 注入 Script），交给 Core+Shell 闭环执行。
// 流程（决策在 planNotify，顺序即契约）：
// 第一轮 idle+dirty+bound → DELETE pending（坏文件自检）→ 有脚本则 PUT /script →
// run → save；saved 事件驱动第二轮 archive + 重转 + viewer.committed；无脚本路径
// discard 后即重转 + viewer.committed（空版本）；任一步失败 → viewer.notify_failed。
// kind 感知：dxf 会话整条管线走 cad 后端（:8200），staging 读 {id}.py 同形。
func (h *ChatHandler) notify(cs *chatSession) {
	ctx, cancel := context.WithTimeout(context.Background(), notifyTimeout)
	defer cancel()
	modelID := cs.ModelID
	var m *store.Model
	if h.deps.St != nil {
		m, _ = h.deps.St.Get(modelID) // 未知模型：m=nil → editClientForKind 回退 Ed（现状行为）
	}
	cl := h.deps.editClientForKind(m)
	st := NotifyState{Dirty: true, Bound: true}
	if m != nil {
		st.ModelKind = m.Kind // dxf → Core 短路 reconvert（XKT 是 ifc 专属产物）
	}
	scriptPath := filepath.Join(h.deps.DataDir, "staging", modelID+".py")
	// 先读 staging 再删 pending（discard 在 runShell 首轮）：read_staging_script 失败时
	// pending 保留，行为更保守（与旧实现相反，有意为之——读不出脚本宁可中止也不丢变更）。
	if fileExists(scriptPath) {
		content, err := os.ReadFile(scriptPath)
		if err != nil {
			h.runFailed(ctx, cs, "read_staging_script", err, cl)
			return
		}
		st.HasStagingScript = true
		st.Script = string(content)
	}
	ev := newEvent("aiifc://chat/"+cs.ID+"/idle", modelID, cs.ID, map[string]any{})
	h.runShell(ctx, cs, ev, st, cl)
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
// kind 感知：dxf 模型走 cad 后端（editClientForKind）。
func (h *ChatHandler) scriptDiffContext(ctx context.Context, modelID string) string {
	var m *store.Model
	if h.deps.St != nil {
		m, _ = h.deps.St.Get(modelID)
	}
	ed := h.deps.editClientForKind(m)
	if ed == nil {
		return ""
	}
	vers, err := ed.GetScriptVersions(ctx, modelID)
	if err != nil {
		log.Printf("chat: script versions %s: %v（降级不注入 diff）", modelID, err)
		return ""
	}
	if len(vers.Scripts) < 2 {
		return ""
	}
	base := vers.Scripts[len(vers.Scripts)-2].Version
	target := vers.Scripts[len(vers.Scripts)-1].Version
	d, err := ed.PostScriptDiff(ctx, modelID, base, target)
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
