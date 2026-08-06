// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package main

import (
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
