package agent

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/cloudwego/eino/adk"
	"github.com/cloudwego/eino/components/model"
	"github.com/cloudwego/eino/components/tool"
	"github.com/cloudwego/eino/compose"
	"github.com/cloudwego/eino/schema"
)

const defaultPersona = `你是 AI_IFC 平台的内置智能体，帮助设计师通过对话完成 IFC/CAD 模型的生成与修改。

编辑纪律（script-as-source：脚本是模型的唯一事实源，改模型 = 改脚本）：
- 先 get_script 读当前脚本，在既有脚本上做增量修改，禁止整体重写。
- 变更走 stage_script → run_script（沙箱验证）→ save_script（落大版本）三段式；run 失败先读错误改脚本再重试。
- 保持 PARAMS 的 key 稳定：只改值或新增 key，不改既有 key 名；设计意图优先用 PARAMS 参数化表达。
IFC 与 DXF 模型走同一套工具（后端按 kind 自动路由），每一步说明依据。`

const defaultMaxStep = 20

// DefaultMaxStep 是子 agent run 的默认步数上限（SubagentConfig.MaxStep 缺省值）。
const DefaultMaxStep = defaultMaxStep

// defaultAgentName 是主 agent 的默认名（模型 step/start 事件展示名；子 agent 经 WithName 覆盖）。
const defaultAgentName = "aiifc-main"

// defaultMaxContextChars 是模型 context 的字符近似（会话记忆阀门基准，historyBudgetRatio=60%）。
// 未超 60% 全量喂历史；超过触发语义压缩。1M 字符 ≈ 主流长上下文模型窗口
// （128K~1M token 量级；若部署模型窗口更小，用 WithMaxContextChars 调低）。
const defaultMaxContextChars = 1_000_000

type Option func(*agentOptions)

type agentOptions struct {
	name            string
	model           model.ToolCallingChatModel
	childModel      func() model.ToolCallingChatModel // 子 agent 模型工厂（路线 B；nil 时默认新建）
	tools           []tool.BaseTool
	persona         string
	maxStep         int
	maxContextChars int // 模型 context 字符近似（会话记忆阀门基准）
	store           *EventStore
	skillsDir       string // 扁平 skills 目录（BaseDir/*/SKILL.md）；空 = 不挂 skill middleware
}

// WithName 设置 agent 名（step/start 事件展示名，供前端区分主/子角色）。
func WithName(name string) Option {
	return func(o *agentOptions) { o.name = name }
}

func WithModel(m model.ToolCallingChatModel) Option {
	return func(o *agentOptions) { o.model = m }
}

// WithChildModelFactory 设置子 agent（ifc/cad）的模型工厂（路线 B）：
// 每次调用产出一个独立实例（scriptedModel 有 pos 游标，主/子必须独立；
// openai 无状态可共享但独立更干净）。nil 时默认按 cfg 新建、空回退 scripted。
func WithChildModelFactory(f func() model.ToolCallingChatModel) Option {
	return func(o *agentOptions) { o.childModel = f }
}

func WithTools(tools []tool.BaseTool) Option {
	return func(o *agentOptions) { o.tools = tools }
}

func WithPersona(persona string) Option {
	return func(o *agentOptions) { o.persona = persona }
}

func WithMaxStep(n int) Option {
	return func(o *agentOptions) { o.maxStep = n }
}

// WithMaxContextChars 设置模型 context 的字符近似（会话记忆阀门基准）：
// 历史未超 60% 全量喂，超预算语义压缩。默认 defaultMaxContextChars。
func WithMaxContextChars(n int) Option {
	return func(o *agentOptions) { o.maxContextChars = n }
}

func WithStore(s *EventStore) Option {
	return func(o *agentOptions) { o.store = s }
}

// WithSkillsDir 挂载官方 skill middleware（adk/middlewares/skill）：
// 目录须为扁平结构（BaseDir/*/SKILL.md），middleware 自动注入 skill 工具
// 与 progressive disclosure 系统提示词。空目录/不传 = 不挂载（离线/测试路径）。
func WithSkillsDir(dir string) Option {
	return func(o *agentOptions) { o.skillsDir = dir }
}

type Agent struct {
	name            string
	runner          *adk.Runner
	store           *EventStore
	maxStep         int
	maxContextChars int
}

// New 装配 ADK 三角色（路线 B，D10）：
//   - orchestrator（主 agent）：领域工具 + AgentAsTool(ifc/cad) + EmitInternalEvents；
//     skill middleware 全量挂载（aiplan 对话协调层 + aibim-orchestrator 编排手册，D11）
//   - ifc-agent / cad-agent：独立 ChatModelAgent（各自 persona/独立模型实例/领域工具 +
//     skill middleware），被 AgentAsTool 包装进 orchestrator 工具面
//
// cfg.APIKey 为空（且未注入 WithModel）时回退确定性 scriptedModel，离线 demo 与测试
// 不依赖真模型。skillsDir 非空时挂官方 skill middleware（skill 工具自动进入模型工具面）。
func New(cfg LLMConfig, opts ...Option) (*Agent, error) {
	o := agentOptions{name: defaultAgentName, persona: defaultPersona, maxStep: defaultMaxStep, maxContextChars: defaultMaxContextChars}
	for _, opt := range opts {
		opt(&o)
	}
	cm := o.model
	if cm == nil {
		var err error
		cm, err = NewChatModel(context.Background(), cfg)
		if err != nil {
			return nil, fmt.Errorf("create chat model: %w", err)
		}
		if cm == nil {
			cm = defaultScriptedModel()
		}
	}
	childModel := o.childModel
	if childModel == nil {
		childModel = func() model.ToolCallingChatModel {
			c, err := NewChatModel(context.Background(), cfg)
			if err != nil || c == nil {
				return defaultScriptedModel()
			}
			return c
		}
	}
	ctx := context.Background()

	// 子 agent（ifc/cad）：独立模型实例 + 领域工具（A2 工具面按角色分离留后续精化）
	// 角色 skill 映射（第一层：意图路由）：ifc-agent→aiifc、cad-agent→aidxf
	// ask_user 工具（HITL 开放断点）：orchestrator + 子 agent 都能问用户
	domainAndAsk := append(append([]tool.BaseTool{}, o.tools...), AskUserTool())
	ifcAgent, err := newRoleAgent(ctx, roleAgentConfig{
		name: PersonaIFC, description: "IFC 建模子 agent（aiifc skill，script-as-source：stage→run→save 三段式）",
		instruction: ifcAgentPersona, model: childModel(), tools: domainAndAsk,
		skillsDir: o.skillsDir, skills: []string{"aiifc"}, maxStep: o.maxStep,
	})
	if err != nil {
		return nil, err
	}
	cadAgent, err := newRoleAgent(ctx, roleAgentConfig{
		name: PersonaCAD, description: "CAD 绘图子 agent（aidxf skill，DXF 生成/校验；建筑平面任务对齐 plan 需求）",
		instruction: cadAgentPersona, model: childModel(), tools: domainAndAsk,
		skillsDir: o.skillsDir, skills: []string{"aidxf"}, maxStep: o.maxStep,
	})
	if err != nil {
		return nil, err
	}

	// orchestrator：领域工具 + AgentAsTool(ifc/cad) + EmitInternalEvents（子事件实时上浮）
	// 角色 skill 映射：orchestrator→aiplan（对话协调层内联，D11）；编排手册在 OrchestratorPersona
	var handlers []adk.TypedChatModelAgentMiddleware[*schema.Message]
	if o.skillsDir != "" {
		skillMW, err := newSkillMiddleware(ctx, o.skillsDir, "aiplan")
		if err != nil {
			return nil, err
		}
		handlers = append(handlers, skillMW)
	}
	// filesystem middleware（D12/M2-0）：读 skill references + execute 白名单（orchestrator 也需读 aiplan references）
	fsMW, err := newFilesystemMiddleware(ctx)
	if err != nil {
		return nil, err
	}
	handlers = append(handlers, fsMW)
	// 工具错误兜底（官方 SafeToolMiddleware 形状）：工具 Go error → 文本结果
	// （"[tool error] ..."），翻译层恢复为带 error 载荷的 tool/result（单卡错误态），
	// 模型可见可自愈；interrupt 错误透传（HITL 原语不被吞）。
	handlers = append(handlers, newSafeToolMiddleware())

	ag, err := adk.NewChatModelAgent(ctx, &adk.ChatModelAgentConfig{
		Name:          o.name,
		Description:   "AI_IFC 平台主智能体：意图路由 + 领域工具（REST 沙箱交付）+ AgentAsTool(ifc/cad) + skill 技能包",
		Instruction:   o.persona,
		Model:         cm,
		MaxIterations: o.maxStep,
		ToolsConfig: adk.ToolsConfig{
			ToolsNodeConfig: compose.ToolsNodeConfig{
				Tools: orchestratorTools(domainAndAsk, ifcAgent, cadAgent),
			},
			EmitInternalEvents: true, // 子 AgentEvent 实时上浮（翻译层 RunPath 打标）
		},
		Handlers: handlers,
	})
	if err != nil {
		return nil, fmt.Errorf("create adk chat model agent: %w", err)
	}
	runner := adk.NewRunner(ctx, adk.RunnerConfig{
		Agent:           ag,
		EnableStreaming: true,
		CheckPointStore: newMemoryCheckPointStore(), // HITL 前置：中断状态落检查点，Resume 续跑
	})
	return &Agent{name: o.name, runner: runner, store: o.store, maxStep: o.maxStep, maxContextChars: o.maxContextChars}, nil
}

// turnCount 返回历史父 turn/start 数（Run/Resume 共用基准）：
// 子 agent 事件（含其 turn/start）不打扰父 turn 计数。store nil（离线/测试）返回 0。
// 语义差异：Run 新开一轮 → turn = count+1；Resume 继续当前轮 → turn = max(count, 1)。
func (a *Agent) turnCount(sessionID string) (int, error) {
	if a.store == nil {
		return 0, nil
	}
	prev, err := a.store.Load(sessionID)
	if err != nil {
		return 0, fmt.Errorf("load session %s: %w", sessionID, err)
	}
	n := 0
	for _, ev := range prev {
		if ev.Type == EventTurnStart && ev.SubagentID == "" {
			n++
		}
	}
	return n, nil
}

// Run 执行一轮 ADK ReAct 循环，返回只读事件通道（循环结束即关闭）。
// 事件同时扇出到通道与 EventStore（append-only JSONL）；Ts 在扇出时打戳。
// 底层：adk.Runner.Run → 消费 AgentEvent 流 → 翻译层映射为平台 9 种事件
// （见 events.go §4 adkTranslator）。与旧 react 路径的事件序列形状保持一致（前端零改动）。
// 调用方必须排空通道直至关闭（缓冲 256，无人消费会阻塞）。
func (a *Agent) Run(ctx context.Context, sessionID, userText string) (<-chan Event, error) {
	if err := validateSessionID(sessionID); err != nil {
		return nil, err
	}
	ctx = WithSessionID(ctx, sessionID) // 工具经 SessionIDFromContext 解析会话绑定模型
	n, err := a.turnCount(sessionID)
	if err != nil {
		return nil, err
	}
	turn := n + 1 // 新开一轮

	out := make(chan Event, 256)
	// sendRaw 是唯一发送路径：落盘（EventStore）+ 扇出通道。
	sendRaw := func(ev Event) {
		if a.store != nil {
			if err := a.store.Append(sessionID, ev); err != nil && ev.Type != EventError {
				out <- Event{Type: EventError, Turn: turn, Step: ev.Step, Ts: time.Now(),
					Payload: jsonPayload(map[string]any{"error": "event store append: " + err.Error()})}
			}
		}
		out <- ev
	}

	go func() {
		sendRaw(Event{Type: EventTurnStart, Turn: turn, Payload: jsonPayload(map[string]any{"user": userText}), Ts: time.Now()})
		// 会话连续性：历史（检查阀门 BuildHistoryMessages） + 当前消息喂给模型。
		// 未超 60% 预算全量回填；超预算语义压缩（每轮指令+最终回复）。store nil（离线/测试）不喂历史。
		msgs := []*schema.Message{}
		if a.store != nil {
			if prev, err := a.store.Load(sessionID); err == nil {
				msgs = append(msgs, BuildHistoryMessages(prev, a.maxContextChars)...)
			}
		}
		msgs = append(msgs, schema.UserMessage(userText))
		// 翻译层消费 ADK 事件流并扇出（含子事件 RunPath 打标 + subagent/status 合成）；
		// Next 迭代结束（含错误/取消）后自行收尾 turn/end。
		tr := newAdkTranslator(turn, a.name, sessionID, a.maxStep, sendRaw)
		// v1 无 CheckPointStore：WithCheckPointID 仅设置 runCtx 的 checkpoint 标识，
		// 不落盘（Runner store=nil 时跳过 checkpoint 保存）。接 HITL（zref_resume）时
		// 需先给 Runner 配 CheckPointStore 再启用 ResumeWithParams。
		iter := a.runner.Run(ctx, msgs, adk.WithCheckPointID(sessionID))
		tr.run(ctx, iter)
		close(out)
	}()

	return out, nil
}

// --- HITL：CheckPointStore + Resume（2026-08-19 接线，M3） -------------------
//
// 与「会话记忆」分工（不要混）：
//   - EventStore JSONL + BuildHistoryMessages = 平台层会话记忆（历史喂模型）
//   - CheckPointStore = ADK 框架内部的中断恢复状态（StatefulInterrupt → Resume 续跑）
//
// 参考实现：eino-examples/quickstart/chatwitheino/cmd/ch09 handleInterrupt +
// eino-examples/adk/common/tool/follow_up_tool.go + store.go（in-memory）。

// memoryCheckPointStore 是 compose.CheckPointStore 的 in-memory 实现（官方 store.go 同构）：
// 存「中断时刻的 agent 运行状态」，供 ResumeWithParams 续跑。进程内有效——
// 服务重启丢中断（v1 接受；持久化留后续）。
type memoryCheckPointStore struct {
	mu  sync.Mutex
	mem map[string][]byte
}

func newMemoryCheckPointStore() *memoryCheckPointStore {
	return &memoryCheckPointStore{mem: map[string][]byte{}}
}

func (s *memoryCheckPointStore) Set(_ context.Context, checkPointID string, checkPoint []byte) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.mem[checkPointID] = checkPoint
	return nil
}

func (s *memoryCheckPointStore) Get(_ context.Context, checkPointID string) ([]byte, bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	v, ok := s.mem[checkPointID]
	return v, ok, nil
}

// Resume 是 HITL 续跑入口：从 CheckPointStore 读中断状态，用用户回答
// （params.Targets[interruptID]）续跑 agent。checkPointID = 会话 id
// （Run 时 WithCheckPointID(sessionID) 落盘）。
// 事件流与 Run 同一翻译层（子事件打标 / question 帧 / turn 收尾）。
// turn 从 EventStore 恢复（中断发生在第 N 轮，resume 后事件仍属第 N 轮）。
func (a *Agent) Resume(ctx context.Context, sessionID string, params *adk.ResumeParams) (<-chan Event, error) {
	if err := validateSessionID(sessionID); err != nil {
		return nil, err
	}
	ctx = WithSessionID(ctx, sessionID)
	n, err := a.turnCount(sessionID)
	if err != nil {
		return nil, err
	}
	turn := n
	if turn < 1 {
		turn = 1 // 中断必有 turn/start；防御兜底
	}
	out := make(chan Event, 256)
	sendRaw := func(ev Event) {
		if a.store != nil {
			_ = a.store.Append(sessionID, ev)
		}
		out <- ev
	}
	go func() {
		iter, err := a.runner.ResumeWithParams(ctx, sessionID, params)
		if err != nil {
			sendRaw(Event{Type: EventError, Turn: turn, Payload: jsonPayload(map[string]any{"error": err.Error()}), Ts: time.Now()})
			close(out)
			return
		}
		tr := newAdkTranslator(turn, a.name, sessionID, a.maxStep, sendRaw)
		tr.run(ctx, iter)
		close(out)
	}()
	return out, nil
}
