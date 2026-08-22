// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/cloudwego/eino/components/tool"

	"ifcviewer/server/internal/agent"
	"ifcviewer/server/internal/api"
	"ifcviewer/server/internal/change"
	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/editsvc"
	"ifcviewer/server/internal/issue"
	"ifcviewer/server/internal/override"
	"ifcviewer/server/internal/store"
)

// 配置路径均相对于进程工作目录解析（非可执行文件目录）。
type config struct {
	Host            string `json:"host"`
	Port            int    `json:"port"`
	DataDir         string `json:"dataDir"`
	NodeBin         string `json:"nodeBin"`
	ConverterScript string `json:"converterScript"`
	MaxUploadMB     int64  `json:"maxUploadMB"`
	WebDist         string `json:"webDist"`
	PgDSN           string `json:"pgDSN"`
	EditServiceURL  string `json:"editServiceURL"`
	CadServiceURL   string `json:"cadServiceURL"`
	LLMAPIKey       string `json:"llmAPIKey"`
	LLMBaseURL      string `json:"llmBaseURL"`
	LLMModel        string `json:"llmModel"`
	SkillsDir       string `json:"skillsDir"` // 扁平 skills 目录（BaseDir/*/SKILL.md），挂官方 skill middleware
	MCPDir          string `json:"mcpDir"`    // mcp/ 目录（stdio MCP server 的 cwd，server.py 所在）；空=不接 MCP
	SkillVenv       string `json:"skillVenv"` // 独立 skill venv 路径（bin 注入 PATH，execute 能调到 aiplan/aidxfv3）
	SkillCLI        string `json:"skillCLI"`  // execute 命令白名单（逗号分隔；默认 aiplan,aidxfv3）
	APIToken        string `json:"apiToken"`
	CORSOriginsRaw  string `json:"corsOrigins"`
	CORSOrigins     []string
}

func loadConfig(path string) (*config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var cfg config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, err
	}
	if cfg.Host == "" {
		cfg.Host = "127.0.0.1"
	}
	if d := os.Getenv("VIEWER_WEB_DIST"); d != "" {
		cfg.WebDist = d
	}
	if cfg.WebDist == "" {
		cfg.WebDist = "../web/dist"
	}
	if dsn := os.Getenv("VIEWER_PG_DSN"); dsn != "" {
		cfg.PgDSN = dsn
	}
	if u := os.Getenv("VIEWER_EDIT_SERVICE_URL"); u != "" {
		cfg.EditServiceURL = u
	}
	if cfg.EditServiceURL == "" {
		cfg.EditServiceURL = "http://127.0.0.1:8100"
	}
	if u := os.Getenv("VIEWER_CAD_SERVICE_URL"); u != "" {
		cfg.CadServiceURL = u
	}
	if cfg.CadServiceURL == "" {
		cfg.CadServiceURL = "http://127.0.0.1:8200"
	}
	if k := os.Getenv("VIEWER_LLM_API_KEY"); k != "" {
		cfg.LLMAPIKey = k
	}
	if u := os.Getenv("VIEWER_LLM_BASE_URL"); u != "" {
		cfg.LLMBaseURL = u
	}
	if m := os.Getenv("VIEWER_LLM_MODEL"); m != "" {
		cfg.LLMModel = m
	}
	if s := os.Getenv("VIEWER_SKILLS_DIR"); s != "" {
		cfg.SkillsDir = s
	}
	if s := os.Getenv("VIEWER_MCP_DIR"); s != "" {
		cfg.MCPDir = s
	}
	if v := os.Getenv("VIEWER_SKILLS_VENV"); v != "" {
		cfg.SkillVenv = v
	}
	if c := os.Getenv("VIEWER_SKILLS_CLI"); c != "" {
		cfg.SkillCLI = c
	}
	if cfg.SkillCLI == "" {
		cfg.SkillCLI = "aiplan,aidxfv3,aiifc" // 默认 = dist 正式集合 CLI 入口（含 aiifc——P2 消费上游链）
	}
	if t := os.Getenv("VIEWER_API_TOKEN"); t != "" {
		cfg.APIToken = t
	}
	if o := os.Getenv("VIEWER_CORS_ORIGINS"); o != "" {
		cfg.CORSOriginsRaw = o
	}
	for _, o := range strings.Split(cfg.CORSOriginsRaw, ",") {
		if o = strings.TrimSpace(o); o != "" {
			cfg.CORSOrigins = append(cfg.CORSOrigins, o)
		}
	}
	if len(cfg.CORSOrigins) == 0 {
		cfg.CORSOrigins = api.DefaultCORSOrigins()
	}
	return &cfg, nil
}

// loadConfigOrExample 读配置；path 缺失时回退同目录的 server_config.example.json。
// server_config.json 已移出 git 跟踪（本地敏感配置不入库）——CI 干净克隆没有，
// 缺则从 example 兜底（example 是完整可用默认配置，apiKey 空 = scriptedModel 离线），
// 避免 server 起不来。example 也读不到才报错。
func loadConfigOrExample(path string) (*config, error) {
	cfg, err := loadConfig(path)
	if err == nil {
		return cfg, nil
	}
	examplePath := filepath.Join(filepath.Dir(path), "server_config.example.json")
	ex, exErr := loadConfig(examplePath)
	if exErr == nil {
		log.Printf("config %s 缺失（%v），回退 example %s", path, err, examplePath)
		return ex, nil
	}
	return nil, fmt.Errorf("%w（且 example %s 也读不到: %v）", err, examplePath, exErr)
}


// buildRootMux 装配根 mux 的子树分发：
//   /api/v1/chat/  与 /api/v1/projects/ 都归 chatHandler（chat/项目方案/交付域）；
//   其余走 api.go handler + 静态托管。子树分发须显式注册——/api/v1/projects/
//   若漏注册会落 "/" 兜底（api.go 无这些路由 → 方案端点 404，2026-08-21 实证）。
func buildRootMux(chatHandler http.Handler, rootHandler http.Handler) *http.ServeMux {
	root := http.NewServeMux()
	root.Handle("/api/v1/chat/", chatHandler)
	root.Handle("/api/v1/projects/", chatHandler)
	root.Handle("/", rootHandler)
	return root
}

func main() {
	configPath := flag.String("config", "server_config.json", "path to config file (relative to working directory)")
	flag.Parse()

	cfg, err := loadConfigOrExample(*configPath)
	if err != nil {
		log.Fatalf("load config: %v", err)
	}

	st := store.NewStore(cfg.DataDir)
	if err := st.Recover(); err != nil {
		log.Fatalf("recover store: %v", err)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	runner := convert.ExecRunner{NodeBin: cfg.NodeBin, Script: cfg.ConverterScript}
	q := convert.NewQueue(st, runner, 2)
	q.Start(ctx)

	var iss issue.Store
	var chg change.Store
	var ovr override.Store
	if cfg.PgDSN != "" {
		pool, err := pgxpool.New(context.Background(), cfg.PgDSN)
		if err != nil {
			log.Fatalf("connect postgres: %v", err)
		}
		defer pool.Close()
		iss, err = issue.NewPgStore(pool, cfg.DataDir)
		if err != nil {
			log.Fatalf("init issue pg store: %v", err)
		}
		chg, err = change.NewPgStore(pool)
		if err != nil {
			log.Fatalf("init change pg store: %v", err)
		}
		ovr, err = override.NewPgStore(pool)
		if err != nil {
			log.Fatalf("init override pg store: %v", err)
		}
		log.Printf("storage: postgres")
	} else {
		iss = issue.NewFileStore(cfg.DataDir)
		chg = change.NewFileStore(cfg.DataDir)
		ovr = override.NewFileStore(cfg.DataDir)
	}
	ed := editsvc.New(cfg.EditServiceURL)
	cad := editsvc.New(cfg.CadServiceURL)
	handler := api.NewHandlerWithProjectStore(st, q, iss, chg, ovr, ed, cad, cfg.MaxUploadMB<<20, cfg.CORSOrigins, store.NewProjectStore(cfg.DataDir))
	// chat 模块（demo）：独立 handler，/api/v1/chat/ 子树优先匹配，其余走既有 handler。
	// 对话由内置 Eino agent 驱动（API key 空时回退确定性 scriptedModel，离线 demo 可用）；
	// 领域工具集按模型 kind 路由（ifc→ed :8100 / dxf→cad :8200，agent.DomainTools）。
	// 装配顺序：先建 ChatHandler（工具 deps 需要 handler 的会话表回调），再建 agent
	//（注入领域工具），最后回填 Ag——handler 与 agent 互相引用只能这样破环。
	// 独立 skill venv（第二层）：bin 前缀进 PATH（execute 的 /bin/sh -c 能调到
	// aiplan/aidxfv3）+ execute 命令白名单配置化对齐 dist + aiplan 可执行（B2 plan 交付）。
	aiplanBin := ""
	if cfg.SkillVenv != "" {
		if fi, err := os.Stat(cfg.SkillVenv); err == nil && fi.IsDir() {
			binDir := filepath.Join(cfg.SkillVenv, "bin")
			if err := os.Setenv("PATH", binDir+string(os.PathListSeparator)+os.Getenv("PATH")); err == nil {
				log.Printf("chat: skill venv 已注入 PATH（%s）", binDir)
			}
			if p, err := exec.LookPath("aiplan"); err == nil {
				aiplanBin = p
			}
		} else {
			log.Printf("chat: skillVenv %q 不存在，execute 可能找不到 skill CLI（跑 tools/install_skill_venv.sh）", cfg.SkillVenv)
		}
	}
	evStore := agent.NewEventStore(cfg.DataDir)
	chatHandler := api.NewChatHandler(api.ChatDeps{
		Ev: evStore,
		Ed: ed, Cad: cad, St: st, Ps: store.NewProjectStore(cfg.DataDir),
		PlanSt: store.NewPlanStore(cfg.DataDir), AiplanBin: aiplanBin, Q: q, DataDir: cfg.DataDir,
	})
	llmCfg := agent.LLMConfig{
		APIKey: cfg.LLMAPIKey, BaseURL: cfg.LLMBaseURL, Model: cfg.LLMModel,
	}
	var cliNames []string
	for _, c := range strings.Split(cfg.SkillCLI, ",") {
		if c = strings.TrimSpace(c); c != "" {
			cliNames = append(cliNames, c)
		}
	}
	agent.SetSkillCommandAllowlist(cliNames)
	log.Printf("chat: execute 命令白名单 = %v（VIEWER_SKILLS_CLI 可覆盖）", cliNames)
	// 对齐官方 ch09 resolveSkillsDir：目录不存在/不可读时跳过挂载（skill 工具不出现），
	// 而不是装配后运行时才爆。skillsDir 为空则完全不挂 skill middleware。
	// 相对路径先归一为绝对（skill middleware 要求 BaseDir 绝对；cwd 不确定时
	// 相对路径会在加载期才爆，这里启动期即钉死）。
	skillsDir := cfg.SkillsDir
	if skillsDir != "" {
		if abs, err := filepath.Abs(skillsDir); err == nil {
			skillsDir = abs
		}
		if fi, err := os.Stat(skillsDir); err != nil || !fi.IsDir() {
			log.Printf("chat: skillsDir %q 不存在或不可读，跳过 skill middleware 挂载（配置 VIEWER_SKILLS_DIR）", skillsDir)
			skillsDir = ""
		}
	}
	// MCP 工具接入（只读定位——实时跟进项目进程）：拉起 mcp stdio server，
	// 三个 agent 共享一个 session（GetTools 一次，工具实例复用）。MCPDir 缺省
	// 推 <repo>/mcp（server 可执行文件上一级的 mcp/）；拉起失败优雅降级（不接）。
	mcpDir := cfg.MCPDir
	if mcpDir != "" {
		if abs, err := filepath.Abs(mcpDir); err == nil {
			mcpDir = abs
		}
	}
	mcpTools, mcpCleanup, mcpErr := agent.LoadMCPTools(context.Background(), agent.MCPToolsConfig{
		MCPDir:  mcpDir,
		DataDir: cfg.DataDir,
	})
	if mcpErr != nil {
		log.Printf("chat: MCP server 拉起失败（%v），跳过 MCP 工具接入", mcpErr)
		mcpTools = nil
	} else if len(mcpTools) > 0 {
		defer mcpCleanup()
		log.Printf("chat: MCP 工具已接入（%d 个，mcpDir=%s）", len(mcpTools), mcpDir)
	}
	domainTools := func() []tool.BaseTool {
		// chatHandler.DomainTools() 已是 []tool.BaseTool（api 层组装好），直接追加 mcp 工具。
		return append(chatHandler.DomainTools(), mcpTools...)
	}
	chatAgent, err := agent.New(llmCfg,
		agent.WithStore(evStore),
		agent.WithTools(domainTools()),
		agent.WithPersona(agent.OrchestratorPersona),
		agent.WithSkillsDir(skillsDir),
	)
	if err != nil {
		log.Fatalf("create chat agent: %v", err)
	}
	chatHandler.SetAgent(chatAgent)
	// 按项目类型分化的主 agent（D13：AgentAsTool 选择性装配 + kind persona +
	// aiplan 挂载差异）。会话经 agentForSession 按 Project.Kind 路由；
	// 历史项目会话恢复同样命中（不落回默认全装）。
	byKind := map[string]*agent.Agent{}
	for _, k := range []string{"cad", "ifc", "cad->ifc"} {
		ka, err := agent.New(llmCfg,
			agent.WithStore(evStore),
			agent.WithTools(domainTools()),
			agent.WithSkillsDir(skillsDir),
			agent.WithKind(k),
		)
		if err != nil {
			log.Fatalf("create %s chat agent: %v", k, err)
		}
		byKind[k] = ka
	}
	chatHandler.SetAgents(byKind)
	if cfg.LLMAPIKey == "" {
		log.Printf("chat: VIEWER_LLM_API_KEY 未配置，回退 scriptedModel（离线 demo 模式）")
	}
	if cfg.SkillsDir != "" {
		log.Printf("chat: skill middleware 已挂载（skillsDir=%s）", cfg.SkillsDir)
	} else {
		log.Printf("chat: skillsDir 未配置（VIEWER_SKILLS_DIR 或 server_config.json skillsDir），skill 工具未挂载")
	}
	root := buildRootMux(chatHandler, api.NewStaticHandler(cfg.WebDist, handler))
	if _, err := os.Stat(cfg.WebDist); err != nil {
		log.Printf("web dist 不可用（%s）：静态页面返回 503，API 不受影响（构建：cd web && npm run build）", cfg.WebDist)
	}
	addr := fmt.Sprintf("%s:%d", cfg.Host, cfg.Port)
	srv := &http.Server{Addr: addr, Handler: api.TokenAuth(cfg.APIToken)(root)}
	if cfg.APIToken != "" {
		log.Printf("api token auth: enabled")
	}

	errCh := make(chan error, 1)
	go func() {
		log.Printf("data dir: %s", cfg.DataDir)
		log.Printf("listening on %s", addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			errCh <- err
		}
	}()

	select {
	case err := <-errCh:
		log.Fatalf("serve: %v", err)
	case <-ctx.Done():
	}

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Fatalf("shutdown: %v", err)
	}
	stop()
	log.Printf("shut down")
}
