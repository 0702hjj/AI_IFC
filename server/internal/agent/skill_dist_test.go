package agent

import (
	"context"
	"testing"

	"github.com/cloudwego/eino/adk/middlewares/skill"
	"os"
	localbk "github.com/cloudwego/eino-ext/adk/backend/local"
)

// TestSkillDistOnlyFormalSet：agent 只面对 skills/dist 正式发布集合——
// 恰好 3 个（aidxf/aiplan/aiifc），开发版本（aidxfv 指针/aibim-orchestrator/
// aiblueprint-mcp）不出现。防止误把 skillsDir 指回 skills/ 根目录。
func TestSkillDistOnlyFormalSet(t *testing.T) {
	if _, err := os.Stat(distSkillsDir()); err != nil {
		t.Skipf("skills/dist 未打包（本地先跑 tools/skill_pack.py；CI 无 dist 跳过集成）: %v", err)
	}
	ctx := context.Background()
	backend, err := localbk.NewBackend(ctx, &localbk.Config{})
	if err != nil {
		t.Fatal(err)
	}
	sb, err := skill.NewBackendFromFilesystem(ctx, &skill.BackendFromFilesystemConfig{
		Backend: backend,
		BaseDir: distSkillsDir(),
	})
	if err != nil {
		t.Fatal(err)
	}
	fms, err := sb.List(ctx)
	if err != nil {
		t.Fatalf("List dist skills: %v", err)
	}

	names := map[string]bool{}
	for _, fm := range fms {
		names[fm.Name] = true
	}
	// 正式集合必须包含
	for _, want := range []string{"aidxf", "aiplan", "aiifc"} {
		if !names[want] {
			t.Errorf("dist 缺正式 skill %q；got %v", want, names)
		}
	}
	// 开发版本/杂项不得出现
	for _, banned := range []string{"aidxfv", "aibim-orchestrator", "aiblueprint-mcp"} {
		if names[banned] {
			t.Errorf("dist 不应包含开发/杂项 skill %q", banned)
		}
	}
	if len(fms) != 3 {
		t.Errorf("dist 应有 3 个正式 skill，got %d：%v", len(fms), names)
	}
}

func distSkillsDir() string {
	return "/home/cyvol0521/.code/gaiahub/CADapi/AI_IFC/skills/dist"
}
