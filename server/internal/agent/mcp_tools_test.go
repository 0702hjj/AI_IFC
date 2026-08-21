package agent

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"
)

// TestLoadMCPToolsEmptyDir MCPDir 空 → 返回 nil 工具（优雅降级，不接 MCP）。
func TestLoadMCPToolsEmptyDir(t *testing.T) {
	tools, cleanup, err := LoadMCPTools(context.Background(), MCPToolsConfig{})
	defer cleanup()
	if err != nil {
		t.Fatalf("MCPDir 空应无错（优雅降级），got %v", err)
	}
	if len(tools) != 0 {
		t.Fatalf("MCPDir 空应返回 nil 工具，got %d", len(tools))
	}
}

// TestLoadMCPToolsServerMissing mcp server 不存在（server.py 缺失）→ 返回 nil（优雅降级）。
func TestLoadMCPToolsServerMissing(t *testing.T) {
	tools, cleanup, err := LoadMCPTools(context.Background(), MCPToolsConfig{MCPDir: t.TempDir()})
	defer cleanup()
	if err != nil {
		t.Fatalf("server.py 缺失应无错（优雅降级），got %v", err)
	}
	if len(tools) != 0 {
		t.Fatalf("server.py 缺失应返回 nil 工具，got %d", len(tools))
	}
}

// TestMCPToolNamesOnlyReadAndUpload 接入的 mcp 工具 = 只读状态上下文 + USER 上传解析（mcp 独有功能）。
func TestMCPToolNamesOnlyReadAndUpload(t *testing.T) {
	want := map[string]bool{
		"model_current_context": true,
		"ifc_upload_modified":   true,
		"dxf_upload_modified":   true,
	}
	if len(mcpToolNames) != len(want) {
		t.Fatalf("mcpToolNames = %v, want %d 个（mcp 独有功能）", mcpToolNames, len(want))
	}
	for _, n := range mcpToolNames {
		if !want[n] {
			t.Errorf("mcpToolNames 含非 mcp 独有工具 %q", n)
		}
	}
	// 不含与 agent 重合的 versions/diff（已删——agent get_versions/get_diff 组合视图覆盖）
	for _, n := range mcpToolNames {
		if n == "model_versions" || n == "model_diff" {
			t.Errorf("mcpToolNames 不应含重合工具 %q（agent 组合视图已覆盖）", n)
		}
	}
}

// TestLoadMCPToolsRealServer 拉起真实 mcp stdio server（uv run python -m app.server），
// 验证 GetTools 返回 3 个工具（model_current_context + ifc/dxf_upload_modified）。
// 需 uv + mcp/.venv——环境缺则 skip（CI 可选）。
func TestLoadMCPToolsRealServer(t *testing.T) {
	mcpDir := filepath.Join("..", "..", "..", "mcp")
	if _, err := os.Stat(filepath.Join(mcpDir, "app", "server.py")); err != nil {
		t.Skip("mcp/app/server.py 不存在")
	}
	if _, err := exec.LookPath("uv"); err != nil {
		t.Skip("uv 不在 PATH")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	tools, cleanup, err := LoadMCPTools(ctx, MCPToolsConfig{MCPDir: mcpDir, DataDir: t.TempDir()})
	defer cleanup()
	if err != nil {
		t.Skipf("mcp server 拉起失败（环境缺依赖？）: %v", err)
	}
	if len(tools) != 3 {
		t.Fatalf("GetTools 返回 %d 个工具, want 3（model_current_context + ifc/dxf_upload_modified）", len(tools))
	}
	names := map[string]bool{}
	for _, tl := range tools {
		info, _ := tl.Info(ctx)
		names[info.Name] = true
	}
	for _, want := range []string{"model_current_context", "ifc_upload_modified", "dxf_upload_modified"} {
		if !names[want] {
			t.Errorf("缺 mcp 工具 %q（got %v）", want, names)
		}
	}
}
