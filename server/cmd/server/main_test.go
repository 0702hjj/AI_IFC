// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func writeConfig(t *testing.T, content string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "config.json")
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write config: %v", err)
	}
	return path
}

func TestLoadConfigDefaultsHostToLocalhost(t *testing.T) {
	path := writeConfig(t, `{"port": 8090, "dataDir": "../data"}`)

	cfg, err := loadConfig(path)
	if err != nil {
		t.Fatalf("loadConfig: %v", err)
	}
	if cfg.Host != "127.0.0.1" {
		t.Fatalf("expected default host 127.0.0.1, got %q", cfg.Host)
	}
}

func TestLoadConfigPreservesExplicitHost(t *testing.T) {
	path := writeConfig(t, `{"host": "0.0.0.0", "port": 9000}`)

	cfg, err := loadConfig(path)
	if err != nil {
		t.Fatalf("loadConfig: %v", err)
	}
	if cfg.Host != "0.0.0.0" {
		t.Fatalf("expected host 0.0.0.0, got %q", cfg.Host)
	}
	if cfg.Port != 9000 {
		t.Fatalf("expected port 9000, got %d", cfg.Port)
	}
}

func TestLoadConfigDefaultsAuthOffAndDefaultCORS(t *testing.T) {
	path := writeConfig(t, `{}`)

	cfg, err := loadConfig(path)
	if err != nil {
		t.Fatalf("loadConfig: %v", err)
	}
	if cfg.APIToken != "" {
		t.Fatalf("expected empty apiToken (auth off), got %q", cfg.APIToken)
	}
	want := []string{"http://localhost:5173", "http://localhost:8080"}
	if strings.Join(cfg.CORSOrigins, ",") != strings.Join(want, ",") {
		t.Fatalf("expected default CORS %v, got %v", want, cfg.CORSOrigins)
	}
}

func TestLoadConfigAuthFromJSON(t *testing.T) {
	path := writeConfig(t, `{"apiToken": "tok", "corsOrigins": "https://a.example, https://b.example"}`)

	cfg, err := loadConfig(path)
	if err != nil {
		t.Fatalf("loadConfig: %v", err)
	}
	if cfg.APIToken != "tok" {
		t.Fatalf("expected apiToken tok, got %q", cfg.APIToken)
	}
	want := []string{"https://a.example", "https://b.example"}
	if strings.Join(cfg.CORSOrigins, ",") != strings.Join(want, ",") {
		t.Fatalf("expected CORS %v, got %v", want, cfg.CORSOrigins)
	}
}

// TestLoadConfigLLMFromJSONAndEnv：LLM 三参从 server_config.json 读取，VIEWER_LLM_* env 覆盖。
func TestLoadConfigLLMFromJSONAndEnv(t *testing.T) {
	path := writeConfig(t, `{"llmAPIKey":"k-json","llmBaseURL":"https://llm.example/v1","llmModel":"m-json"}`)
	cfg, err := loadConfig(path)
	if err != nil {
		t.Fatalf("loadConfig: %v", err)
	}
	if cfg.LLMAPIKey != "k-json" || cfg.LLMBaseURL != "https://llm.example/v1" || cfg.LLMModel != "m-json" {
		t.Fatalf("json LLM 配置未读到: %+v", cfg)
	}

	t.Setenv("VIEWER_LLM_API_KEY", "k-env")
	t.Setenv("VIEWER_LLM_BASE_URL", "https://env.example/v1")
	t.Setenv("VIEWER_LLM_MODEL", "m-env")
	cfg, err = loadConfig(path)
	if err != nil {
		t.Fatalf("loadConfig: %v", err)
	}
	if cfg.LLMAPIKey != "k-env" || cfg.LLMBaseURL != "https://env.example/v1" || cfg.LLMModel != "m-env" {
		t.Fatalf("env 应覆盖 json: %+v", cfg)
	}
}

// TestLoadConfigLLMDefaultsEmpty：缺省三参为空（agent 回退 scriptedModel，离线 demo 模式）。
func TestLoadConfigLLMDefaultsEmpty(t *testing.T) {
	path := writeConfig(t, `{}`)
	cfg, err := loadConfig(path)
	if err != nil {
		t.Fatalf("loadConfig: %v", err)
	}
	if cfg.LLMAPIKey != "" || cfg.LLMBaseURL != "" || cfg.LLMModel != "" {
		t.Fatalf("LLM 缺省应为空（scriptedModel 回退）: %+v", cfg)
	}
}

// TestLoadConfigSkillsDirFromJSONAndEnv：skillsDir 从 server_config.json 读取，
// VIEWER_SKILLS_DIR env 覆盖；缺省为空（skill middleware 不挂载）。
func TestLoadConfigSkillsDirFromJSONAndEnv(t *testing.T) {
	path := writeConfig(t, `{"skillsDir":"/abs/path/skills"}`)
	cfg, err := loadConfig(path)
	if err != nil {
		t.Fatalf("loadConfig: %v", err)
	}
	if cfg.SkillsDir != "/abs/path/skills" {
		t.Fatalf("json skillsDir 未读到: %+v", cfg)
	}

	t.Setenv("VIEWER_SKILLS_DIR", "/env/path/skills")
	cfg, err = loadConfig(path)
	if err != nil {
		t.Fatalf("loadConfig: %v", err)
	}
	if cfg.SkillsDir != "/env/path/skills" {
		t.Fatalf("env 应覆盖 json: %+v", cfg)
	}

	t.Setenv("VIEWER_SKILLS_DIR", "") // 清除 env，验证缺省为空
	path2 := writeConfig(t, `{}`)
	cfg, err = loadConfig(path2)
	if err != nil {
		t.Fatalf("loadConfig: %v", err)
	}
	if cfg.SkillsDir != "" {
		t.Fatalf("skillsDir 缺省应为空: %+v", cfg)
	}
}

// TestLoadConfigSkillVenvAndCLI：skillVenv / skillCLI 从 server_config.json 读取，
// VIEWER_SKILLS_VENV / VIEWER_SKILLS_CLI env 覆盖；skillCLI 缺省 = dist 对齐默认集。
func TestLoadConfigSkillVenvAndCLI(t *testing.T) {
	path := writeConfig(t, `{"skillVenv":"/abs/skills/.venv","skillCLI":"aiplan,aidxfv3"}`)
	cfg, err := loadConfig(path)
	if err != nil {
		t.Fatalf("loadConfig: %v", err)
	}
	if cfg.SkillVenv != "/abs/skills/.venv" || cfg.SkillCLI != "aiplan,aidxfv3" {
		t.Fatalf("skill 配置未读到: %+v", cfg)
	}

	t.Setenv("VIEWER_SKILLS_VENV", "/env/venv")
	t.Setenv("VIEWER_SKILLS_CLI", "myskill")
	cfg, err = loadConfig(path)
	if err != nil {
		t.Fatalf("loadConfig: %v", err)
	}
	if cfg.SkillVenv != "/env/venv" || cfg.SkillCLI != "myskill" {
		t.Fatalf("env 应覆盖 json: %+v", cfg)
	}

	t.Setenv("VIEWER_SKILLS_CLI", "")
	path2 := writeConfig(t, `{}`)
	cfg, err = loadConfig(path2)
	if err != nil {
		t.Fatalf("loadConfig: %v", err)
	}
	if cfg.SkillCLI != "aiplan,aidxfv3" {
		t.Fatalf("skillCLI 缺省应为 dist 默认集: %+v", cfg)
	}
}

// TestLoadConfigRetiredOpenCodeURLEnvironmentIgnored：VIEWER_OPENCODE_URL 已随
// opencode serve 退役（chunk E，Eino 进程内接管）——环境变量残留不再被读取，
// 配置结构中亦无该字段（openCodeURL 键被静默忽略，不报错）。
func TestLoadConfigRetiredOpenCodeURLEnvironmentIgnored(t *testing.T) {
	t.Setenv("VIEWER_OPENCODE_URL", "http://127.0.0.1:4096")
	path := writeConfig(t, `{"openCodeURL":"http://127.0.0.1:4096","port":8090,"dataDir":"../data"}`)
	cfg, err := loadConfig(path)
	if err != nil {
		t.Fatalf("退役键残留不应报错: %v", err)
	}
	_ = cfg // OpenCodeURL 字段已删除——编译期保证不可再引用
}

// TestShippedConfigsContainNoOpenCodeURL：随仓发布的 server_config.example.json（server_config.json 已移出跟踪，example 即「随仓发布配置」）
// 不得再含退役键 openCodeURL，且 llm 三参（空缺省）在位。
func TestShippedConfigsContainNoOpenCodeURL(t *testing.T) {
	for _, name := range []string{"server_config.example.json"} {
		raw, err := os.ReadFile(filepath.Join("..", "..", name))
		if err != nil {
			t.Fatalf("read %s: %v", name, err)
		}
		if strings.Contains(string(raw), "openCodeURL") || strings.Contains(string(raw), "opencode") {
			t.Fatalf("%s 仍含退役键 openCodeURL/opencode", name)
		}
		for _, key := range []string{"llmAPIKey", "llmBaseURL", "llmModel"} {
			if !strings.Contains(string(raw), `"`+key+`"`) {
				t.Fatalf("%s 缺 llm 配置键 %q", name, key)
			}
		}
		var cfg struct {
			LLMAPIKey  string `json:"llmAPIKey"`
			LLMBaseURL string `json:"llmBaseURL"`
			LLMModel   string `json:"llmModel"`
		}
		if err := json.Unmarshal(raw, &cfg); err != nil {
			t.Fatalf("decode %s: %v", name, err)
		}
		if cfg.LLMAPIKey != "" || cfg.LLMBaseURL != "" || cfg.LLMModel != "" {
			t.Fatalf("%s llm 三参缺省应为空（scriptedModel 离线 demo 回退）: %+v", name, cfg)
		}
	}
}

// TestLoadConfigWebDist：webDist 缺省回退默认（../web/dist，与 dataDir 同 cwd 约定），
// json 配置生效，VIEWER_WEB_DIST env 覆盖。
func TestLoadConfigWebDist(t *testing.T) {
	path := writeConfig(t, `{}`)
	cfg, err := loadConfig(path)
	if err != nil {
		t.Fatalf("loadConfig: %v", err)
	}
	if cfg.WebDist != "../web/dist" {
		t.Fatalf("webDist 缺省应为 ../web/dist，got %q", cfg.WebDist)
	}

	path = writeConfig(t, `{"webDist": "/srv/aiifc/web"}`)
	cfg, err = loadConfig(path)
	if err != nil {
		t.Fatalf("loadConfig: %v", err)
	}
	if cfg.WebDist != "/srv/aiifc/web" {
		t.Fatalf("json webDist 未读到: %q", cfg.WebDist)
	}

	t.Setenv("VIEWER_WEB_DIST", "/opt/web/dist")
	cfg, err = loadConfig(path)
	if err != nil {
		t.Fatalf("loadConfig: %v", err)
	}
	if cfg.WebDist != "/opt/web/dist" {
		t.Fatalf("env 应覆盖 json: %q", cfg.WebDist)
	}
}

func TestLoadConfigEnvOverridesAuth(t *testing.T) {
	t.Setenv("VIEWER_API_TOKEN", "env-tok")
	t.Setenv("VIEWER_CORS_ORIGINS", "https://env.example")
	path := writeConfig(t, `{"apiToken": "json-tok", "corsOrigins": "https://json.example"}`)

	cfg, err := loadConfig(path)
	if err != nil {
		t.Fatalf("loadConfig: %v", err)
	}
	if cfg.APIToken != "env-tok" {
		t.Fatalf("env 应覆盖 json: %q", cfg.APIToken)
	}
	if len(cfg.CORSOrigins) != 1 || cfg.CORSOrigins[0] != "https://env.example" {
		t.Fatalf("env 应覆盖 json: %v", cfg.CORSOrigins)
	}
}
