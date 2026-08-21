// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// tools_helpers.go：工具通用 helper + 请求 schema（从 tools.go 拆出，W-0049 行数门控）。
package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"


	"ifcviewer/server/internal/editsvc"
)

// maxToolResult 是单条工具结果的上限（64KB）——防爆模型上下文（Token 节流）。
const maxToolResult = 65536

// toolErr 把后端/依赖错误格式化为截断后的工具输出（错误文本化统一入口——
// 错误串同样受 64KB 上限约束，防爆模型上下文）。
func toolErr(err error) string {
	return truncateToolResult(fmt.Sprintf("调用失败：%v", err))
}

func truncateToolResult(s string) string {
	if len(s) > maxToolResult {
		return s[:maxToolResult] + "...(truncated)"
	}
	return s
}

func toolJSON(v any) string {
	raw, err := json.Marshal(v)
	if err != nil {
		return fmt.Sprintf(`{"error":%q}`, err.Error())
	}
	return truncateToolResult(string(raw))
}

// semanticDiffSummary 从 run 响应里取构件级计数（edit-service run 端点附的
// semanticDiff：旧产物 vs 本次产物的 {added, removed, changed}）折叠为一行
// 摘要。字段为 null（diff 失败/无旧产物降级）、缺失或响应畸形 → 空串，
// 调用侧回退行级 staging diff 摘要。
func semanticDiffSummary(raw json.RawMessage) string {
	var d struct {
		SemanticDiff *struct {
			Added   int `json:"added"`
			Removed int `json:"removed"`
			Changed int `json:"changed"`
		} `json:"semanticDiff"`
	}
	if err := json.Unmarshal(raw, &d); err != nil || d.SemanticDiff == nil {
		return ""
	}
	return fmt.Sprintf("[staging diff] 构件 +%d -%d ~%d",
		d.SemanticDiff.Added, d.SemanticDiff.Removed, d.SemanticDiff.Changed)
}

// stagingDiffSummary 拉 staging 最近两步的轻量脚本 diff（GET /script/staging/diff）
// 并折叠为一行摘要：行级 added/removed 计数 + PARAMS 变化行——追加进 run_script
// 工具结果，tool 卡片零改动即可显示，AI 也能观测自纠。
// diff 不可用（少于两个暂存步 409、后端错误、响应畸形）返回空串降级——
// 摘要是观测增强，绝不拖垮已成功的 run 结果。
func stagingDiffSummary(ctx context.Context, cl *editsvc.Client, modelID string) string {
	raw, err := cl.Do(ctx, http.MethodGet, "/models/"+modelID+"/script/staging/diff", nil)
	if err != nil {
		return ""
	}
	var d struct {
		Stats         editsvc.ScriptDiffStats     `json:"stats"`
		ParamsChanges []editsvc.ScriptParamChange `json:"params_changes"`
	}
	if err := json.Unmarshal(raw, &d); err != nil {
		return ""
	}
	var b strings.Builder
	fmt.Fprintf(&b, "[staging diff] added=%d removed=%d", d.Stats.Added, d.Stats.Removed)
	for _, c := range d.ParamsChanges {
		switch c.Action {
		case "added":
			fmt.Fprintf(&b, "\nPARAMS + %s = %v", c.Key, c.New)
		case "removed":
			fmt.Fprintf(&b, "\nPARAMS - %s (旧值 %v)", c.Key, c.Old)
		default: // modified
			fmt.Fprintf(&b, "\nPARAMS ~ %s: %v -> %v", c.Key, c.Old, c.New)
		}
	}
	return b.String()
}

// toolRaw 把后端原始响应转为工具输出；错误文本化（不抛 Go error 中断 ReAct 循环）。
func toolRaw(raw json.RawMessage, err error) (string, error) {
	if err != nil {
		return fmt.Sprintf("调用失败：%v", err), nil
	}
	return truncateToolResult(string(raw)), nil
}
// --- 工具参数 schema（jsonschema tag 即模型可见的参数说明） ---

type emptyReq struct{}

type modelRefReq struct {
	ModelID string `json:"modelId,omitempty" jsonschema:"description=目标模型 id（m_ 开头）；缺省取当前会话绑定模型"`
}

type stageScriptReq struct {
	Script  string `json:"script" jsonschema:"required,description=完整构建脚本全文（在 get_script 读出的既有脚本上增量修改；禁止整体重写风格）"`
	Note    string `json:"note,omitempty" jsonschema:"description=本次变更说明"`
	ModelID string `json:"modelId,omitempty" jsonschema:"description=目标模型 id（m_ 开头）；缺省取当前会话绑定模型"`
}

type saveScriptReq struct {
	Note    string `json:"note,omitempty" jsonschema:"description=大版本说明"`
	ModelID string `json:"modelId,omitempty" jsonschema:"description=目标模型 id（m_ 开头）；缺省取当前会话绑定模型"`
}

type initModelReq struct {
	ProjectID string `json:"projectId,omitempty" jsonschema:"description=项目 id（p_...；缺省用当前会话绑定项目）"`
	Kind      string `json:"kind,omitempty" jsonschema:"description=模型类别：dxf（默认，CAD 图纸）或 ifc"`
	Title     string `json:"title" jsonschema:"required,description=模型名（如「一层平面」「我的建筑」）"`
}

type diffReq struct {
	Base    string `json:"base" jsonschema:"required,description=基线大版本号（如 v1）"`
	Target  string `json:"target" jsonschema:"required,description=目标大版本号（如 v2）"`
	ModelID string `json:"modelId,omitempty" jsonschema:"description=目标模型 id（m_ 开头）；缺省取当前会话绑定模型"`
}

type createProjectReq struct {
	Title string `json:"title" jsonschema:"required,description=项目名（人类可读）"`
	Kind  string `json:"kind,omitempty" jsonschema:"description=首交付模型类别：ifc（默认）或 dxf"`
}

// projectRefReq 是项目域工具的统一入参（projectID 缺省回退会话绑定项目）。
type projectRefReq struct {
	ProjectID string `json:"projectId,omitempty" jsonschema:"description=项目 id（p_...；缺省用当前会话绑定项目）"`
}

// deliverPlanReq 是 plan 交付入参（plan/bimSupplement 为方案 JSON 对象文本）。
type deliverPlanReq struct {
	ProjectID     string          `json:"projectId,omitempty" jsonschema:"description=项目 id（p_...；缺省用当前会话绑定项目）"`
	Plan          json.RawMessage `json:"plan" jsonschema:"required,description=plan.json 内容（对象）"`
	BimSupplement json.RawMessage `json:"bimSupplement,omitempty" jsonschema:"description=bim_supplement.json 内容（对象，可空）"`
}

// locateReq 是调用点定位入参（XDATA key）。
type locateReq struct {
	Key     string `json:"key" jsonschema:"required,description=XDATA 稳定 key（如 0:line:1，从 render.json 实体选中获得）"`
	ModelID string `json:"modelId,omitempty" jsonschema:"description=目标模型 id（m_ 开头）；缺省取当前会话绑定模型"`
}

// editCallReq 是标量改写入参（value 为 JSON 标量）。
type editCallReq struct {
	Key      string          `json:"key" jsonschema:"required,description=XDATA 稳定 key"`
	Argument string          `json:"argument" jsonschema:"required,description=要改写的参数名"`
	Value    json.RawMessage `json:"value" jsonschema:"required,description=新标量值（str/int/float/bool）"`
	ModelID  string          `json:"modelId,omitempty" jsonschema:"description=目标模型 id（m_ 开头）；缺省取当前会话绑定模型"`
}

