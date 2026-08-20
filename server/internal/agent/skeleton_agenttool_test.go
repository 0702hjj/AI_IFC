package agent

import (
	"context"
	"strings"
	"testing"

	"github.com/cloudwego/eino/components/model"
	"github.com/cloudwego/eino/components/tool"
	"os"
)

// TestSkeletonAgentToolRealSkills：真实 skills/ 目录下三角色装配（路线 B）——
// orchestrator 挂全量 skill（含 aiplan 对话协调层）+ AgentAsTool(ifc/cad)，
// 子 agent 各自挂 skill middleware；scriptedModel 派发 ifc-agent 子 agent 读
// 会话 id 后收尾，验证整条链路在真实 skill 数据上不报错且子事件带标签。
func TestSkeletonAgentToolRealSkills(t *testing.T) {
	if _, err := os.Stat(distSkillsDir()); err != nil {
		t.Skipf("skills/dist 未打包（本地先跑 tools/skill_pack.py；CI 无 dist 跳过集成）: %v", err)
	}
	sidTool, err := newStringTool("read_sid", func(ctx context.Context) (string, error) {
		return "sid=" + SessionIDFromContext(ctx), nil
	})
	if err != nil {
		t.Fatal(err)
	}
	child := Script{Steps: []ScriptStep{
		{ToolCalls: []ToolCallSpec{{ID: "c1", Name: "read_sid", Arguments: `{}`}}},
		{Chunks: []string{"子代理完成"}},
	}}
	parent := Script{Steps: []ScriptStep{
		{ToolCalls: []ToolCallSpec{{ID: "p1", Name: PersonaIFC, Arguments: `{"request":"建一堵墙"}`}}},
		{Chunks: []string{"汇总完成"}},
	}}

	ag, err := New(LLMConfig{},
		WithSkillsDir("/home/cyvol0521/.code/gaiahub/CADapi/AI_IFC/skills/dist"),
		WithModel(NewScriptedModel(parent)),
		WithChildModelFactory(func() model.ToolCallingChatModel { return NewScriptedModel(child) }),
		WithTools([]tool.BaseTool{sidTool}),
		WithMaxStep(10),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	ch, err := ag.Run(context.Background(), "sess-real-agtool", "画个 IFC 墙")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)

	// 子边界：started/finished 合成 + 子事件带标签
	iStart, startEv := findStatus(t, evs, "started")
	iFin, finEv := findStatus(t, evs, "finished")
	if startEv.SubagentID == "" || finEv.SubagentID == "" || startEv.SubagentID != finEv.SubagentID {
		t.Fatalf("子边界标签异常: started=%q finished=%q", startEv.SubagentID, finEv.SubagentID)
	}
	// 子 read_sid 结果含父会话 id（AgentAsTool ctx 继承）
	var got string
	for i := iStart; i <= iFin; i++ {
		if evs[i].Type == EventToolResult && payloadString(t, evs[i], "name") == "read_sid" {
			got = payloadString(t, evs[i], "content")
		}
	}
	if !strings.Contains(got, "sess-real-agtool") {
		t.Fatalf("子 read_sid = %q, want 含父会话 id", got)
	}
	// AgentAsTool 工具结果 = 子最终答复
	if last := evs[len(evs)-1]; last.Type != EventTurnEnd {
		t.Fatalf("末事件 = %s, want turn/end", last.Type)
	}
}
