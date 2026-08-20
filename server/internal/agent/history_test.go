package agent

import (
	"context"
	"testing"
	"time"

	"github.com/cloudwego/eino/components/model"
	"github.com/cloudwego/eino/schema"
)

// mkTurnEvents 构造一轮事件（用户指令 → assistant 回复 → 工具调用链）。
func mkTurnEvents(turn int, user, assistant string, toolResults int) []Event {
	evs := []Event{
		{Type: EventTurnStart, Turn: turn, Payload: jsonPayload(map[string]any{"user": user}), Ts: time.Now()},
	}
	if assistant != "" {
		evs = append(evs, Event{Type: EventAssistantMessage, Turn: turn, Step: 1,
			Payload: jsonPayload(map[string]any{"content": assistant}), Ts: time.Now()})
	}
	for i := 0; i < toolResults; i++ {
		evs = append(evs, Event{Type: EventToolResult, Turn: turn, Step: 2,
			Payload: jsonPayload(map[string]any{"id": "t", "name": "get_script", "content": "脚本全文很长很长"}, ), Ts: time.Now()})
	}
	return evs
}

// TestBuildHistoryMessagesFullWhenUnderBudget：检查阀门——未超 60% 预算，
// 历史全量折叠（含工具调用链配对）。
func TestBuildHistoryMessagesFullWhenUnderBudget(t *testing.T) {
	evs := append(mkTurnEvents(1, "第一问", "第一答", 2), mkTurnEvents(2, "第二问", "第二答", 1)...)
	msgs := BuildHistoryMessages(evs, 100_000)

	var userCnt, toolCnt int
	for _, m := range msgs {
		switch m.Role {
		case schema.User:
			userCnt++
		case schema.Tool:
			toolCnt++
		}
	}
	if userCnt != 2 {
		t.Fatalf("全量路径应含 2 条 user，got %d（%v）", userCnt, msgs)
	}
	if toolCnt != 3 {
		t.Fatalf("全量路径应含 3 条 tool（未压缩），got %d", toolCnt)
	}
}

// TestBuildHistoryMessagesCompressWhenOverBudget：检查阀门——超预算触发语义压缩：
// 只保留每轮 用户指令 + 最终无工具回复，工具调用链被丢弃。
func TestBuildHistoryMessagesCompressWhenOverBudget(t *testing.T) {
	evs := append(mkTurnEvents(1, "生成 IFC 长任务", "已完成，产物 v3", 30),
		mkTurnEvents(2, "层高改 3 米", "已改", 5)...)
	msgs := BuildHistoryMessages(evs, 100) // 极小预算 → 强制压缩

	var toolCnt int
	for _, m := range msgs {
		if m.Role == schema.Tool {
			toolCnt++
		}
	}
	if toolCnt != 0 {
		t.Fatalf("压缩路径应无 tool 消息（工具调用链丢弃），got %d", toolCnt)
	}
	if len(msgs) == 0 {
		t.Fatalf("压缩后不应为空（至少保留最近一轮指令+回复）")
	}
	// 语义保留：最新一轮（层高改 3 米）应在
	var gotUser bool
	for _, m := range msgs {
		if m.Role == schema.User && m.Content == "层高改 3 米" {
			gotUser = true
		}
	}
	if !gotUser {
		t.Fatalf("压缩后缺最近一轮用户指令：%v", msgs)
	}
}

// TestBuildHistoryMessagesSkipsSubagentEvents：子 agent 事件（SubagentID 非空）
// 不进历史（子内容经 AgentAsTool 结果回流父模型，重复注入会重复计数）。
func TestBuildHistoryMessagesSkipsSubagentEvents(t *testing.T) {
	parent := mkTurnEvents(1, "画个平面", "已派发", 1)
	child := []Event{
		{Type: EventTurnStart, Turn: 1, SubagentID: "sa_1_1", ParentSessionID: "s",
			Payload: jsonPayload(map[string]any{"user": "子任务"}), Ts: time.Now()},
		{Type: EventAssistantMessage, Turn: 1, SubagentID: "sa_1_1", ParentSessionID: "s",
			Payload: jsonPayload(map[string]any{"content": "子内容"}), Ts: time.Now()},
	}
	msgs := BuildHistoryMessages(append(parent, child...), 100_000)
	for _, m := range msgs {
		if m.Content == "子内容" || m.Content == "子任务" {
			t.Fatalf("子事件内容泄漏进历史：%v", m)
		}
	}
}

// spyInputModel 捕获模型输入（验证会话连续性喂历史），内部透传 scriptedModel。
type spyInputModel struct {
	inner  model.ToolCallingChatModel
	inputs [][]*schema.Message
}

func (m *spyInputModel) Generate(ctx context.Context, input []*schema.Message, opts ...model.Option) (*schema.Message, error) {
	m.inputs = append(m.inputs, input)
	return m.inner.Generate(ctx, input, opts...)
}

func (m *spyInputModel) Stream(ctx context.Context, input []*schema.Message, opts ...model.Option) (*schema.StreamReader[*schema.Message], error) {
	m.inputs = append(m.inputs, input)
	return m.inner.Stream(ctx, input, opts...)
}

func (m *spyInputModel) WithTools(tools []*schema.ToolInfo) (model.ToolCallingChatModel, error) {
	inner, err := m.inner.WithTools(tools)
	if err != nil {
		return nil, err
	}
	return &spyInputModel{inner: inner}, nil
}

// TestRunSessionContinuityHistoryInjected：第 2 轮模型输入含第 1 轮历史
// （user + assistant），会话连续性接线生效。
func TestRunSessionContinuityHistoryInjected(t *testing.T) {
	store := NewEventStore(t.TempDir())
	// 两轮都用同一脚本（Repeat：每轮产出同一句回复，模型有状态 pos 不串）
	script := Script{Steps: []ScriptStep{{Chunks: []string{"本轮回复"}}, {Chunks: []string{""}, Repeat: true}}}
	spy := &spyInputModel{inner: NewScriptedModel(script)}
	ag, err := New(LLMConfig{},
		WithModel(spy),
		WithStore(store),
		WithMaxStep(10),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	// turn 1
	ch1, err := ag.Run(context.Background(), "sess-cont", "第一问")
	if err != nil {
		t.Fatalf("Run1: %v", err)
	}
	collect(t, ch1)
	// turn 2
	ch2, err := ag.Run(context.Background(), "sess-cont", "第二问")
	if err != nil {
		t.Fatalf("Run2: %v", err)
	}
	collect(t, ch2)

	if len(spy.inputs) < 2 {
		t.Fatalf("模型应被调用 2 次（两轮），got %d", len(spy.inputs))
	}
	secondInput := spy.inputs[len(spy.inputs)-1]
	// 第 2 轮输入应含：历史(user "第一问" + assistant "本轮回复") + 当前 user "第二问"
	var sawHistoryUser, sawHistoryAssistant, sawCurrent bool
	for _, m := range secondInput {
		switch {
		case m.Role == schema.User && m.Content == "第一问":
			sawHistoryUser = true
		case m.Role == schema.Assistant && m.Content == "本轮回复":
			sawHistoryAssistant = true
		case m.Role == schema.User && m.Content == "第二问":
			sawCurrent = true
		}
	}
	if !sawHistoryUser || !sawHistoryAssistant || !sawCurrent {
		t.Fatalf("第 2 轮输入应含历史+当前，got %v", secondInput)
	}
}
