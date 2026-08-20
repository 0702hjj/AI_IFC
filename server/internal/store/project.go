// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// project.go：项目级聚合存储（A1，交付对齐）——项目是「唯一且通用」的
// 创建单元（用户点聊天框新建项目），项目下可含多个模型（单 kind = 主交付
// 模型；dxf→ifc 管线 = 多模型共享 projectID）。
//
// 落盘：{DATA}/projects/{projectID}/project.json（原子 tmp+rename）。
// 方案级目录 {DATA}/plans/{projectID}/（plan 产物）与项目本体分开——B 块。
package store

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"time"
)

// projectIDPattern 是项目 id 格式（p_ + 16 hex，与 modelId 同风格）。
var projectIDPattern = regexp.MustCompile(`^p_[0-9a-f]{16}$`)

func validProjectID(id string) bool { return projectIDPattern.MatchString(id) }

// ModelRef 是项目下模型的引用（聚合视图，非完整 Model 元数据）。
type ModelRef struct {
	ID     string `json:"id"`
	Kind   string `json:"kind"`
	Name   string `json:"name"`
	Status string `json:"status"`
}

// Project 是项目级聚合实体。
type Project struct {
	ID        string     `json:"id"`
	Title     string     `json:"title"`
	Models    []ModelRef `json:"models"`
	CreatedAt time.Time  `json:"createdAt"`
}

// ProjectStore 管理项目聚合（文件存储，单写者纪律同 Store）。
type ProjectStore struct{ DataDir string }

func NewProjectStore(dataDir string) *ProjectStore { return &ProjectStore{DataDir: dataDir} }

func newProjectID() string {
	b := make([]byte, 8)
	_, _ = rand.Read(b)
	return "p_" + hex.EncodeToString(b)
}

func (s *ProjectStore) dir(id string) string { return filepath.Join(s.DataDir, "projects", id) }

func (s *ProjectStore) path(id string) string { return filepath.Join(s.dir(id), "project.json") }

func (s *ProjectStore) write(p *Project) error {
	data, err := json.MarshalIndent(p, "", "  ")
	if err != nil {
		return err
	}
	tmp := s.path(p.ID) + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, s.path(p.ID))
}

// Create 创建空项目（无模型）；模型随后经 AddModel 挂入（create_project 先建
// 项目再挂首模型，A1）。
func (s *ProjectStore) Create(title string) (*Project, error) {
	id := newProjectID()
	if err := os.MkdirAll(s.dir(id), 0o755); err != nil {
		return nil, err
	}
	p := &Project{ID: id, Title: title, Models: []ModelRef{}, CreatedAt: time.Now().UTC()}
	if err := s.write(p); err != nil {
		return nil, err
	}
	return p, nil
}

// AddModel 向项目挂模型（幂等：同 modelId 不重复）；项目不存在返回 ErrNotFound。
func (s *ProjectStore) AddModel(id, modelID, kind, name, status string) error {
	p, err := s.Get(id)
	if err != nil {
		return err
	}
	for _, m := range p.Models {
		if m.ID == modelID {
			return nil // 幂等
		}
	}
	p.Models = append(p.Models, ModelRef{ID: modelID, Kind: kind, Name: name, Status: status})
	return s.write(p)
}

// Get 读项目；非法 id 返回 ErrInvalidID，不存在返回 ErrNotFound（与 Model 同哨兵）。
func (s *ProjectStore) Get(id string) (*Project, error) {
	if !validProjectID(id) {
		return nil, ErrInvalidID
	}
	data, err := os.ReadFile(s.path(id))
	if os.IsNotExist(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	var p Project
	if err := json.Unmarshal(data, &p); err != nil {
		return nil, err
	}
	if p.Models == nil {
		p.Models = []ModelRef{}
	}
	return &p, nil
}

// List 列出全部项目（按 CreatedAt 倒序，同 Model.List 语义）。
func (s *ProjectStore) List() ([]*Project, error) {
	entries, err := os.ReadDir(filepath.Join(s.DataDir, "projects"))
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var out []*Project
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		p, err := s.Get(e.Name())
		if err == nil {
			out = append(out, p)
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].CreatedAt.After(out[j].CreatedAt) })
	return out, nil
}

// Delete 删除项目（含 models 引用聚合；模型文件本体不删——项目删除 ≠ 模型删除，
// 由调用方决定是否连带清理）。
func (s *ProjectStore) Delete(id string) error {
	if _, err := s.Get(id); err != nil {
		return err
	}
	return os.RemoveAll(s.dir(id))
}
