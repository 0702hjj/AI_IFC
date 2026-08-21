package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"

	"github.com/cloudwego/eino/components/tool"
	"github.com/cloudwego/eino/components/tool/utils"
	"github.com/cloudwego/eino/schema"

	"ifcviewer/server/internal/editsvc"
	"ifcviewer/server/internal/store"
)

type ctxKeySessionID struct{}

// WithSessionID 把会话 id 注入 ctx（Run 在启动 ReAct 循环前调用；
// 测试/装配侧可用它手工构造带会话上下文的 ctx）。
func WithSessionID(ctx context.Context, sessionID string) context.Context {
	return context.WithValue(ctx, ctxKeySessionID{}, sessionID)
}

// SessionIDFromContext 取出 Run 注入的会话 id（工具经它解析会话绑定模型）。
func SessionIDFromContext(ctx context.Context) string {
	s, _ := ctx.Value(ctxKeySessionID{}).(string)
	return s
}

// ToolDeps 是领域工具集的依赖包。工具面领域收敛：不持有 bash/任意文件写能力，
// 全部变更经 edit-service（ifc）/ cad-service（dxf）REST，按模型 kind 路由。
type ToolDeps struct {
	IFC *editsvc.Client // ifc kind 后端（services/ifc :8100）
	CAD *editsvc.Client // dxf kind 后端（services/cad :8200）；nil 时 dxf 工具报错文本
	St  *store.Store    // kind 路由 + list/get model info

	// SessionModel 从 ctx 解析当前会话绑定的模型 id（无绑定返回 ""）；可空。
	SessionModel func(ctx context.Context) string
	// MarkDirty 在变更类工具成功后标记会话 dirty（notify 精确信号，不再只靠 mtime）；
	// create_project 不置位（新模型与绑定模型是两个对象，置位会让 notify 错绑管线）；可空。
	MarkDirty func(ctx context.Context)
	// PushStaged 在 run_script 成功后推送 viewer.staged 中途预览信号
	// （{modelId, kind} 载荷，走 pushSystem 管线；同 MarkDirty 的可空适配器模式）；可空。
	PushStaged func(ctx context.Context, modelID, kind string)
	// CreateProject 创建「项目」（项目级 A1：projectID + 首交付模型，kind ifc|dxf）；
	// 返回可 JSON 化的 {model, project}；可空。
	CreateProject func(ctx context.Context, title, kind string) (any, error)
	// InitModel 在项目下初始化骨架模型（agent 会话内新建 DXF/IFC——script-as-source：
	// 骨架脚本构建出最小模型 v1）。返回 {modelId, kind, title, projectId}；可空。
	InitModel func(ctx context.Context, projectID, kind, title string) (any, error)

	// --- D2 项目/方案域（交付对齐） ---
	// SessionProject 从 ctx 解析会话绑定项目 id（A2；无绑定返回 ""）；可空。
	SessionProject func(ctx context.Context) string
	// ProjectModels 列项目下模型聚合（id/kind/name/status）；可空。
	ProjectModels func(ctx context.Context, projectID string) ([]store.ModelRef, error)
	// PlanGet 读方案产物当前态（name = plan.json|bim_supplement.json）；可空。
	PlanGet func(ctx context.Context, projectID, name string) (string, error)
	// PlanDeliver 触发 plan 交付（B2：aiplan land → 落方案级目录），
	// 返回 {planVersion, bimVersion}；可空。
	PlanDeliver func(ctx context.Context, projectID, plan, bimSupplement string) (map[string]any, error)
	// SkillWorkDir 返回项目 skill 工作区绝对路径（{DATA}/skill-work/{projectID}，
	// 首次调用 MkdirAll；projectId 隔离多项目不混淆）——aidxf 中间产物
	// （derived/missions/deliver）落盘根，复用 plans/{projectID} 的 projectId 隔离地基；可空。
	SkillWorkDir func(ctx context.Context, projectID string) (string, error)
}

func (d ToolDeps) markDirty(ctx context.Context) {
	if d.MarkDirty != nil {
		d.MarkDirty(ctx)
	}
}

func (d ToolDeps) pushStaged(ctx context.Context, m *store.Model) {
	if d.PushStaged != nil {
		d.PushStaged(ctx, m.ID, m.Kind)
	}
}

// resolve 归一 modelId（参数缺省回退会话绑定模型）并做 kind 路由。
// 失败返回非空 errText——工具把错误以文本返回供 LLM 观测自愈（sec-agent 模式），
// 非法/未知 modelId 在此拦截，不会触达任何后端（守卫）。
func (d ToolDeps) resolve(ctx context.Context, modelID string) (*store.Model, *editsvc.Client, string) {
	if modelID == "" && d.SessionModel != nil {
		modelID = d.SessionModel(ctx)
	}
	if modelID == "" {
		return nil, nil, "未指定 modelId，且当前会话未绑定模型——请先 create_project 或在绑定模型的会话中重试"
	}
	if d.St == nil {
		return nil, nil, "调用失败：store 未配置（模型工具不可用）"
	}
	m, err := d.St.Get(modelID)
	if err != nil {
		return nil, nil, truncateToolResult(fmt.Sprintf("模型 %q 不可用：%v", modelID, err))
	}
	cl := d.IFC
	if m.Kind == store.KindDXF {
		cl = d.CAD
	}
	if cl == nil {
		return nil, nil, truncateToolResult(fmt.Sprintf("模型 %s 的后端未配置（kind=%s）", modelID, m.Kind))
	}
	return m, cl, ""
}


// mustTool 构造 InferTool；schema 是静态的，构造失败即程序员错误，启动期直接 panic
// （同 http.ServeMux 冲突 panic 语义），不拖错误签名污染 DomainTools 契约。
func mustTool[T, R any](name, desc string, fn func(context.Context, T) (R, error)) tool.InvokableTool {
	tl, err := utils.InferTool(name, desc, fn)
	if err != nil {
		panic(fmt.Sprintf("domain tool %s: %v", name, err))
	}
	return tl
}

// DomainTools 装配 chat agent 的领域工具集（9 个）：
// list_models / get_model_info / get_script / stage_script / run_script /
// save_script / get_versions / get_diff / create_project。
// 语义镜像 services/ifc（:8100）与 services/cad（:8200）的 REST 端点；
// run/save/diff 走 slow client（沙箱执行最长 60s，fast 10s 会三方状态分叉）。
func DomainTools(deps ToolDeps) []tool.InvokableTool {
	return []tool.InvokableTool{
		mustTool("list_models", "列出平台全部模型（id/名称/kind(ifc|dxf)/状态/创建时间）",
			func(ctx context.Context, _ emptyReq) (string, error) {
				if deps.St == nil {
					return "调用失败：store 未配置（list_models 不可用）", nil
				}
				ms, err := deps.St.List()
				if err != nil {
					return toolErr(err), nil
				}
				return toolJSON(ms), nil
			}),

		mustTool("get_model_info", "获取单个模型信息（id/名称/kind/状态/大小/创建时间）",
			func(ctx context.Context, in modelRefReq) (string, error) {
				m, _, errText := deps.resolve(ctx, in.ModelID)
				if errText != "" {
					return errText, nil
				}
				return toolJSON(m), nil
			}),

		mustTool("get_script", "读取模型当前构建脚本（有暂存读暂存，否则读最近大版本基线）",
			func(ctx context.Context, in modelRefReq) (string, error) {
				m, cl, errText := deps.resolve(ctx, in.ModelID)
				if errText != "" {
					return errText, nil
				}
				return toolRaw(cl.Do(ctx, http.MethodGet, "/models/"+m.ID+"/script", nil))
			}),

		mustTool("stage_script", "暂存构建脚本（全量替换；不执行）。之后必须 run_script 沙箱验证，再 save_script 落大版本",
			func(ctx context.Context, in stageScriptReq) (string, error) {
				m, cl, errText := deps.resolve(ctx, in.ModelID)
				if errText != "" {
					return errText, nil
				}
				body, _ := json.Marshal(map[string]string{"script": in.Script, "note": in.Note})
				out, err := cl.Do(ctx, http.MethodPut, "/models/"+m.ID+"/script", body)
				if err != nil {
					return toolErr(err), nil
				}
				deps.markDirty(ctx)
				return toolRaw(out, nil)
			}),

		mustTool("run_script", "沙箱执行当前暂存脚本（验证可构建并重写工作区模型文件；不落版本）",
			func(ctx context.Context, in modelRefReq) (string, error) {
				m, cl, errText := deps.resolve(ctx, in.ModelID)
				if errText != "" {
					return errText, nil
				}
				out, err := cl.DoSlow(ctx, http.MethodPost, "/models/"+m.ID+"/script/run", nil)
				if err != nil {
					return toolErr(err), nil
				}
				deps.markDirty(ctx)
				deps.pushStaged(ctx, m)
				text := truncateToolResult(string(out))
				// 摘要降级链：构件级（run 响应 semanticDiff）→ 行级 staging diff → 无摘要。
				if s := semanticDiffSummary(out); s != "" {
					text += "\n" + s
				} else if s := stagingDiffSummary(ctx, cl, m.ID); s != "" {
					text += "\n" + s
				}
				return truncateToolResult(text), nil
			}),

		mustTool("save_script", "沙箱执行并落大版本（scripts/v{n}.py + 版本快照，原子）；save 前确保已 stage_script",
			func(ctx context.Context, in saveScriptReq) (string, error) {
				m, cl, errText := deps.resolve(ctx, in.ModelID)
				if errText != "" {
					return errText, nil
				}
				body, _ := json.Marshal(map[string]string{"note": in.Note})
				out, err := cl.DoSlow(ctx, http.MethodPost, "/models/"+m.ID+"/script/save", body)
				if err != nil {
					return toolErr(err), nil
				}
				deps.markDirty(ctx)
				return toolRaw(out, nil)
			}),

		mustTool("get_versions", "列出模型的大版本（IFC 快照 versions + 构建脚本 scripts + 当前版本 current）——模型版本历史全景（参考 mcp model_versions 组合视图）",
			func(ctx context.Context, in modelRefReq) (string, error) {
				m, cl, errText := deps.resolve(ctx, in.ModelID)
				if errText != "" {
					return errText, nil
				}
				return combineModelVersions(ctx, cl, m.ID)
			}),

		mustTool("get_diff", "拉两个大版本的组合 diff：ifc=IFC 语义 diff（构件增删改）+ script=构建脚本 diff（text_diff+PARAMS 变化）——模型级版本对比全景（参考 mcp model_diff 组合视图）",
			func(ctx context.Context, in diffReq) (string, error) {
				m, cl, errText := deps.resolve(ctx, in.ModelID)
				if errText != "" {
					return errText, nil
				}
				return combineModelDiff(ctx, cl, m.ID, in.Base, in.Target)
			}),

		mustTool("create_project", "创建空白项目（项目级：projectID + 首交付模型，kind 可选 ifc/dxf 默认 ifc），返回首模型（modelId 供后续编辑）+ projectId（会话绑定用它）",
			func(ctx context.Context, in createProjectReq) (string, error) {
				if deps.CreateProject == nil {
					return "create_project 未配置（装配缺失）", nil
				}
				v, err := deps.CreateProject(ctx, in.Title, in.Kind)
				if err != nil {
					return toolErr(err), nil
				}
				// 不 markDirty：新模型 B 与会话绑定的模型 A 是两个对象——置 dirty 会让
				// turn 结束的 notifyIfDirty 对未变更的 A 跑完整管线（stale staging 时
				// save 出无意图版本）。新模型的转换由 CreateProject 内部 Enqueue 直接触发，
				// 不依赖 notify；后续对 B 的 stage/run/save 才会置 dirty。
				return toolJSON(v), nil
			}),

		mustTool("init_model", "在项目下初始化骨架模型（新建 DXF/IFC：骨架脚本沙箱构建出最小模型 v1，分配 modelId）——agent 会话内新建模型的入口；CAD 项目每次新建图纸时调用，后续看 get_project_models 决定新建或编辑已有",
			func(ctx context.Context, in initModelReq) (string, error) {
				if deps.InitModel == nil {
					return "init_model 未配置（装配缺失）", nil
				}
				pid := in.ProjectID
				if pid == "" {
					pid = resolveProjectID(ctx, deps, "")
				}
				kind := in.Kind
				if kind == "" {
					kind = "dxf"
				}
				v, err := deps.InitModel(ctx, pid, kind, in.Title)
				if err != nil {
					return toolErr(err), nil
				}
				deps.markDirty(ctx)
				return toolJSON(v), nil
			}),

		mustTool("get_project_plans", "读项目方案产物当前态（plan.json / bim_supplement.json）——plan 是任务书（对接 cad/bim），先读它再决定派发",
			func(ctx context.Context, in projectRefReq) (string, error) {
				projectID := resolveProjectID(ctx, deps, in.ProjectID)
				if projectID == "" {
					return "未指定 projectId，且当前会话未绑定项目——请先 create_project 或在绑定项目的会话中重试", nil
				}
				if deps.PlanGet == nil {
					return "get_project_plans 未配置（装配缺失）", nil
				}
				plan, err := deps.PlanGet(ctx, projectID, "plan.json")
				if err != nil {
					return toolErr(err), nil
				}
				bim, err := deps.PlanGet(ctx, projectID, "bim_supplement.json")
				if err != nil {
					return toolErr(err), nil
				}
				return toolJSON(map[string]any{
					"projectId": projectID, "plan": json.RawMessage(plan), "bimSupplement": json.RawMessage(bim),
				}), nil
			}),

		mustTool("deliver_plan", "执行 plan 交付（aiplan land → 方案级目录版本化）：body 传 plan + bimSupplement（可从 get_project_plans 读后修改再交）",
			func(ctx context.Context, in deliverPlanReq) (string, error) {
				projectID := resolveProjectID(ctx, deps, in.ProjectID)
				if projectID == "" {
					return "未指定 projectId，且当前会话未绑定项目——请先 create_project 或在绑定项目的会话中重试", nil
				}
				if deps.PlanDeliver == nil {
					return "deliver_plan 未配置（装配缺失）", nil
				}
				v, err := deps.PlanDeliver(ctx, projectID, string(in.Plan), string(in.BimSupplement))
				if err != nil {
					return toolErr(err), nil
				}
				return toolJSON(v), nil
			}),

		mustTool("get_project_models", "列项目下模型聚合（id/kind/name/status）——项目会话内查看全部交付模型",
			func(ctx context.Context, in projectRefReq) (string, error) {
				projectID := resolveProjectID(ctx, deps, in.ProjectID)
				if projectID == "" {
					return "未指定 projectId，且当前会话未绑定项目——请先 create_project 或在绑定项目的会话中重试", nil
				}
				if deps.ProjectModels == nil {
					return "get_project_models 未配置（装配缺失）", nil
				}
				models, err := deps.ProjectModels(ctx, projectID)
				if err != nil {
					return toolErr(err), nil
				}
				return toolJSON(map[string]any{"projectId": projectID, "models": models}), nil
			}),

		mustTool("get_skill_workdir", "返回项目 skill 工作区绝对路径（{DATA}/skill-work/{projectID}，首次调用自动建目录；projectId 隔离多项目不混淆）——aidxf 中间产物（derived/missions/deliver）落盘根：所有 aidxfv3 命令的 --project 必须用它",
			func(ctx context.Context, in projectRefReq) (string, error) {
				projectID := resolveProjectID(ctx, deps, in.ProjectID)
				if projectID == "" {
					return "未指定 projectId，且当前会话未绑定项目——请先 create_project 或在绑定项目的会话中重试", nil
				}
				if deps.SkillWorkDir == nil {
					return "get_skill_workdir 未配置（装配缺失）", nil
				}
				dir, err := deps.SkillWorkDir(ctx, projectID)
				if err != nil {
					return toolErr(err), nil
				}
				return toolJSON(map[string]any{"projectId": projectID, "workdir": dir}), nil
			}),

		mustTool("get_script_locate", "XDATA key → 脚本调用点定位（line/col/snippet）——选中构件后定位到创建它的脚本位置（M3-①）",
			func(ctx context.Context, in locateReq) (string, error) {
				m, cl, errText := deps.resolve(ctx, in.ModelID)
				if errText != "" {
					return errText, nil
				}
				return toolRaw(cl.Do(ctx, http.MethodGet, "/models/"+m.ID+"/script/locate?key="+url.QueryEscape(in.Key), nil))
			}),

		mustTool("edit_script_call", "libcst 标量改写定位到的调用点实参（key+argument+value；沙箱 run + staging.push，422/409 零副作用）",
			func(ctx context.Context, in editCallReq) (string, error) {
				m, cl, errText := deps.resolve(ctx, in.ModelID)
				if errText != "" {
					return errText, nil
				}
				body, _ := json.Marshal(map[string]any{
					"key": in.Key, "argument": in.Argument, "value": json.RawMessage(in.Value),
				})
				return toolRaw(cl.DoSlow(ctx, http.MethodPost, "/models/"+m.ID+"/script/edit-call", body))
			}),
	}
}

// resolveProjectID 归一项目 id（参数缺省回退会话绑定项目）。
func resolveProjectID(ctx context.Context, deps ToolDeps, projectID string) string {
	if projectID == "" && deps.SessionProject != nil {
		projectID = deps.SessionProject(ctx)
	}
	return projectID
}

// AsBaseTools 把 DomainTools 产出转为 WithTools 的入参形状。
func AsBaseTools(ts []tool.InvokableTool) []tool.BaseTool {
	out := make([]tool.BaseTool, len(ts))
	for i, t := range ts {
		out[i] = t
	}
	return out
}

// --- HITL 开放断点：ask_user（官方 FollowUpTool 模式对齐，M3） -----------------

// AskUserInfo 是中断时呈现给用户的信息（翻译层据此发 question/ask 帧）；
// UserAnswer 由 /answer 经 Agent.Resume 填充。
type AskUserInfo struct {
	Question   string
	UserAnswer string
}

// AskUserState 是中断时保存的工具状态（恢复时读回问题，非目标中断时重新中断）。
type AskUserState struct {
	Question string
}

func init() {
	schema.Register[*AskUserInfo]()
	schema.Register[*AskUserState]()
}

type askUserReq struct {
	Question string `json:"question" jsonschema:"required,description=需要用户确认/补充的问题（自包含——用户只看到这个问题；如：'是否确认以 3 米层高保存？'）"`
}

// askUser 是 ask_user 工具的执行体（对齐官方 FollowUp 三分支：
// 首次中断 / resume 拿回答 / 非目标中断重新挂起）。
func askUser(ctx context.Context, in askUserReq) (string, error) {
	wasInterrupted, _, storedState := tool.GetInterruptState[*AskUserState](ctx)
	if !wasInterrupted {
		info := &AskUserInfo{Question: in.Question}
		return "", tool.StatefulInterrupt(ctx, info, &AskUserState{Question: in.Question})
	}

	isResumeTarget, hasData, data := tool.GetResumeContext[*AskUserInfo](ctx)
	if isResumeTarget && hasData {
		if data.UserAnswer == "" {
			return "", fmt.Errorf("ask_user resumed without a user answer")
		}
		return data.UserAnswer, nil
	}
	if !isResumeTarget {
		// 非目标中断（多断点场景）：重新挂起，保留原问题
		return "", tool.StatefulInterrupt(ctx, &AskUserInfo{Question: storedState.Question}, storedState)
	}
	return "", fmt.Errorf("ask_user resumed without data")
}

// AskUserTool 产出 ask_user 工具（挂 orchestrator + 子 agent，模型缺信息/需确认时自主调用）。
func AskUserTool() tool.InvokableTool {
	return mustTool("ask_user", "向用户提问以获取缺失信息或确认（用户只看到问题文本，你的回答 = 用户原文）。需要设计确认/方案确认/补充信息时调用",
		askUser)
}
