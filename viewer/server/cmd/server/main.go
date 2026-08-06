// SPDX-License-Identifier: AGPL-3.0-only
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
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"ifcviewer/server/internal/api"
	"ifcviewer/server/internal/change"
	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/editsvc"
	"ifcviewer/server/internal/issue"
	"ifcviewer/server/internal/opencode"
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
	PgDSN           string `json:"pgDSN"`
	EditServiceURL  string `json:"editServiceURL"`
	OpenCodeURL     string `json:"openCodeURL"`
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
	if dsn := os.Getenv("VIEWER_PG_DSN"); dsn != "" {
		cfg.PgDSN = dsn
	}
	if u := os.Getenv("VIEWER_EDIT_SERVICE_URL"); u != "" {
		cfg.EditServiceURL = u
	}
	if cfg.EditServiceURL == "" {
		cfg.EditServiceURL = "http://127.0.0.1:8100"
	}
	if u := os.Getenv("VIEWER_OPENCODE_URL"); u != "" {
		cfg.OpenCodeURL = u
	}
	if cfg.OpenCodeURL == "" {
		cfg.OpenCodeURL = "http://127.0.0.1:4096"
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

func main() {
	configPath := flag.String("config", "server_config.json", "path to config file (relative to working directory)")
	flag.Parse()

	cfg, err := loadConfig(*configPath)
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
	handler := api.NewHandlerWithCORS(st, q, iss, chg, ovr, ed, cfg.MaxUploadMB<<20, cfg.CORSOrigins)
	// chat 模块（demo）：独立 handler，/api/v1/chat/ 子树优先匹配，其余走既有 handler。
	chatHandler := api.NewChatHandler(ctx, api.ChatDeps{
		OC: opencode.New(cfg.OpenCodeURL), Ed: ed, St: st, Chg: chg, Q: q, DataDir: cfg.DataDir,
	})
	root := http.NewServeMux()
	root.Handle("/api/v1/chat/", chatHandler)
	root.Handle("/", handler)
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
