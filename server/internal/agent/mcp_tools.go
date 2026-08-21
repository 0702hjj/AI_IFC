// mcp_tools.go —— MCP 工具接入（官方 eino-ext officialmcp + modelcontextprotocol/go-sdk）。
//
// 定位：把 mcp/app（stdio MCP server）的工具经官方 MCP client 转为 Eino tool，
// 接入三个 agent（orchestrator + ifc-agent + cad-agent）——**只读定位**（实时跟进
// 项目进程：model_current_context 状态上下文 + USER 直改上传解析 ifc/dxf_upload_modified）。
//
// 协议链路（官方组件，零自创）：
//   CommandTransport（stdio，拉起 `uv run python -m app.server`，cwd=mcp/）
//     → mcp.NewClient.Connect → ClientSession
//     → officialmcp.GetTools（ToolNameList 过滤）→ []tool.BaseTool
//
// 三个 agent 共享一个 MCP session（一个 stdio server 进程）——GetTools 一次，
// 工具实例给三个 agent 复用（避免每 agent 拉起一个 server 进程）。
package agent

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"

	omcp "github.com/cloudwego/eino-ext/components/tool/mcp/officialmcp"
	"github.com/cloudwego/eino/components/tool"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// mcpToolNames 是接入的 mcp 工具（mcp/app 独有功能，只读定位——实时跟进项目进程）。
//   model_current_context：改前状态上下文（当前版本 + staging + 最近事件）——三 agent 都用
//   ifc_upload_modified / dxf_upload_modified：USER 直改上传解析（provenance=USER 入 change log）
var mcpToolNames = []string{
	"model_current_context",
	"ifc_upload_modified",
	"dxf_upload_modified",
}

// MCPToolsConfig 是 MCP 工具装配参数。
type MCPToolsConfig struct {
	// MCPDir 是 mcp/ 目录（server.py 所在，stdio server 的 cwd）。空 = 不接 MCP。
	MCPDir string
	// DataDir 是 VIEWER_DATA_DIR（mcp server 需要，模型文件解析）。
	DataDir string
}

// LoadMCPTools 拉起 mcp stdio server 并返回其工具（officialmcp.GetTools）。
// MCPDir 空 / 拉起失败 → 返回 nil（优雅降级——MCP 是增强项，不接不影响主链路）。
// 返回的 cleanup 用于进程退出时关闭 session + 终止 server 子进程。
func LoadMCPTools(ctx context.Context, cfg MCPToolsConfig) ([]tool.BaseTool, func(), error) {
	if cfg.MCPDir == "" {
		return nil, func() {}, nil
	}
	serverPy := filepath.Join(cfg.MCPDir, "app", "server.py")
	if _, err := os.Stat(serverPy); err != nil {
		return nil, func() {}, nil // mcp server 不存在 → 不接
	}
	// stdio CommandTransport：`uv run python -m app.server`（cwd=mcp/，带 VIEWER_DATA_DIR）
	cmd := exec.CommandContext(ctx, "uv", "run", "python", "-m", "app.server")
	cmd.Dir = cfg.MCPDir
	if cfg.DataDir != "" {
		cmd.Env = append(os.Environ(), "VIEWER_DATA_DIR="+cfg.DataDir)
	}
	transport := &mcp.CommandTransport{Command: cmd}
	client := mcp.NewClient(&mcp.Implementation{
		Name:    "aiifc-agent",
		Version: "0.1.0",
	}, nil)
	session, err := client.Connect(ctx, transport, nil)
	if err != nil {
		return nil, func() {}, err
	}
	tools, err := omcp.GetTools(ctx, &omcp.Config{
		Cli:          session,
		ToolNameList: mcpToolNames,
	})
	if err != nil {
		_ = session.Close()
		return nil, func() {}, err
	}
	cleanup := func() { _ = session.Close() }
	return tools, cleanup, nil
}
