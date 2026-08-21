// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// plan.go：方案级存储（B1，交付对齐）——plan.json / bim_supplement.json 按
// 方案（projectID）落盘 + 方案级版本化（plan 演化独立于模型版本，P-1/P-3）。
//
// 落盘：{DATA}/plans/{projectID}/{name}（当前态，原子 tmp+rename）；
//       历史：{DATA}/plans/{projectID}/plan_history/{name}/v{n}.json（归档递增）。
// name 白名单：plan.json | bim_supplement.json（领域收敛单点）。
package store

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

// ErrInvalidJSON 是方案产物非合法 JSON 的错误（Put 校验单点）。
var ErrInvalidJSON = errors.New("invalid json content")

// planFileNames 是方案级目录允许的产物名（白名单枚举，PUT/GET 单点校验）。
var planFileNames = map[string]bool{
	"plan.json":           true,
	"bim_supplement.json": true,
}

var planHistoryRe = regexp.MustCompile(`^v(\d+)\.json$`)
var planVersionRe = regexp.MustCompile(`^v\d+$`)

// PlanStore 管理方案级产物（当前态 + 历史版本）。
type PlanStore struct{ DataDir string }

func NewPlanStore(dataDir string) *PlanStore { return &PlanStore{DataDir: dataDir} }

func (s *PlanStore) dir(projectID string) string { return filepath.Join(s.DataDir, "plans", projectID) }

func (s *PlanStore) currentPath(projectID, name string) string {
	return filepath.Join(s.dir(projectID), name)
}

func (s *PlanStore) historyDir(projectID, name string) string {
	base := strings.TrimSuffix(name, ".json") // plan.json → plan
	return filepath.Join(s.dir(projectID), "plan_history", base)
}

func validPlanName(name string) bool { return planFileNames[name] }

// Get 读当前态方案产物；非法 name → ErrInvalidKind，未落盘 → ErrNotFound。
func (s *PlanStore) Get(projectID, name string) ([]byte, error) {
	if !validPlanName(name) {
		return nil, ErrInvalidKind
	}
	if !validProjectID(projectID) {
		return nil, ErrInvalidID
	}
	data, err := os.ReadFile(s.currentPath(projectID, name))
	if os.IsNotExist(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	return data, nil
}

// Put 写当前态方案产物并归档历史（方案级版本化）：旧内容 → history/v{n}.json，
// 新内容原子写当前文件。返回新版本名（首个 = v1）。
func (s *PlanStore) Put(projectID, name string, content []byte) (string, error) {
	if !validPlanName(name) {
		return "", ErrInvalidKind
	}
	if !validProjectID(projectID) {
		return "", ErrInvalidID
	}
	// 轻校验：内容必须是合法 JSON 对象（详细 schema 校验由 aiplan land / 调用方做）。
	if !json.Valid(content) {
		return "", ErrInvalidJSON
	}
	dir := s.dir(projectID)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}
	// 归档旧当前态（首次 PUT 无旧文件 → v1）：
	// 旧当前对应的版本 = 历史目录下一号（oldVer）；新当前版本 = oldVer+1。
	version := "v1"
	if old, err := os.ReadFile(s.currentPath(projectID, name)); err == nil {
		histDir := s.historyDir(projectID, name)
		if err := os.MkdirAll(histDir, 0o755); err != nil {
			return "", err
		}
		oldVer := nextHistoryVersion(histDir)
		if err := writeAtomic(filepath.Join(histDir, oldVer+".json"), old); err != nil {
			return "", err
		}
		version = "v" + itoa(atoiOrZero(strings.TrimPrefix(oldVer, "v"))+1)
	}
	// 当前态原子写
	if err := writeAtomic(s.currentPath(projectID, name), content); err != nil {
		return "", err
	}
	return version, nil
}

// nextHistoryVersion 计算下一个历史版本号（v{n} 递增；空目录 → v1）。
func nextHistoryVersion(histDir string) string {
	entries, err := os.ReadDir(histDir)
	if err != nil {
		return "v1"
	}
	maxN := 0
	for _, e := range entries {
		if m := planHistoryRe.FindStringSubmatch(e.Name()); m != nil {
			n := atoiOrZero(m[1])
			if n > maxN {
				maxN = n
			}
		}
	}
	return "v" + itoa(maxN+1)
}

// ListHistory 列出方案产物历史版本（v{n}，升序）；无历史返回空列表。
func (s *PlanStore) ListHistory(projectID, name string) ([]string, error) {
	if !validPlanName(name) {
		return nil, ErrInvalidKind
	}
	if !validProjectID(projectID) {
		return nil, ErrInvalidID
	}
	histDir := s.historyDir(projectID, name)
	entries, err := os.ReadDir(histDir)
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var out []string
	for _, e := range entries {
		if planHistoryRe.MatchString(e.Name()) {
			out = append(out, strings.TrimSuffix(e.Name(), ".json"))
		}
	}
	sort.Strings(out)
	return out, nil
}

// LoadHistory 读方案产物的历史版本内容；非法 name/id → ErrInvalidKind/ErrInvalidID，
// 版本不存在（含当前态版本——它不在 history/ 下）→ ErrNotFound。
// Delete 删除项目全部方案产物（plans/{projectID} 目录）；幂等（不存在不报错）。
func (s *PlanStore) Delete(projectID string) error {
	return os.RemoveAll(s.dir(projectID))
}

func (s *PlanStore) LoadHistory(projectID, name, version string) ([]byte, error) {
	if !validPlanName(name) {
		return nil, ErrInvalidKind
	}
	if !validProjectID(projectID) {
		return nil, ErrInvalidID
	}
	if !planVersionRe.MatchString(version) {
		return nil, ErrNotFound
	}
	data, err := os.ReadFile(filepath.Join(s.historyDir(projectID, name), version+".json"))
	if os.IsNotExist(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	return data, nil
}

func writeAtomic(path string, content []byte) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, content, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

func atoiOrZero(s string) int {
	n := 0
	for _, c := range s {
		if c < '0' || c > '9' {
			return 0
		}
		n = n*10 + int(c-'0')
	}
	return n
}

func itoa(n int) string {
	return strconv.Itoa(n)
}
