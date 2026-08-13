// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package store

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"
)

var ErrNotFound = errors.New("model not found")
var ErrInvalidID = errors.New("invalid model id")
var ErrInvalidKind = errors.New("invalid model kind")
var ErrUnsupportedExt = errors.New("unsupported file extension")

// 模型类别（W-0040）：ifc 走 converter XKT 链路；dxf 由 services/cad 直接产
// render.json，无转换。空 kind 视为 ifc（存量 model.json 迁移口径，见 Get）。
const (
	KindIFC = "ifc"
	KindDXF = "dxf"
)

func ValidKind(kind string) bool { return kind == KindIFC || kind == KindDXF }

// KindForFilename 按扩展名判定模型类别（白名单 .ifc/.dxf，大小写不敏感）；
// 其余返回 ErrUnsupportedExt，由 handler 翻译为 400。
func KindForFilename(name string) (string, error) {
	switch strings.ToLower(filepath.Ext(name)) {
	case ".ifc":
		return KindIFC, nil
	case ".dxf":
		return KindDXF, nil
	}
	return "", ErrUnsupportedExt
}

var idPattern = regexp.MustCompile(`^m_[0-9a-f]{16}$`)

func validID(id string) bool { return idPattern.MatchString(id) }

type Model struct {
	ID        string    `json:"id"`
	Name      string    `json:"name"`
	Size      int64     `json:"size"`
	Status    string    `json:"status"`
	Kind      string    `json:"kind"`
	CreatedAt time.Time `json:"createdAt"`
	Error     string    `json:"error"`
}

type Store struct{ DataDir string }

func NewStore(dataDir string) *Store { return &Store{DataDir: dataDir} }

func newID() string {
	b := make([]byte, 8)
	_, _ = rand.Read(b)
	return "m_" + hex.EncodeToString(b)
}

func (s *Store) IFCPath(id string) string  { return filepath.Join(s.DataDir, "uploads", id+".ifc") }
func (s *Store) DXFPath(id string) string  { return filepath.Join(s.DataDir, "uploads", id+".dxf") }
func (s *Store) ModelDir(id string) string { return filepath.Join(s.DataDir, "models", id) }

// SourcePath 按 kind 返回上传源文件路径（空 kind 视同 ifc，与 Get 迁移口径一致）。
func (s *Store) SourcePath(m *Model) string {
	if m.Kind == KindDXF {
		return s.DXFPath(m.ID)
	}
	return s.IFCPath(m.ID)
}

func (s *Store) Create(name string, size int64, src io.Reader) (*Model, error) {
	return s.CreateWithKind(name, size, src, KindIFC)
}

// CreateWithKind 落上传文件 + model.json。ifc 初始 converting（等转换队列）；
// dxf 无 XKT 转换，创建即 ready（W-0040）。
func (s *Store) CreateWithKind(name string, size int64, src io.Reader, kind string) (*Model, error) {
	if !ValidKind(kind) {
		return nil, ErrInvalidKind
	}
	id := newID()
	srcPath := s.IFCPath(id)
	status := "converting"
	if kind == KindDXF {
		srcPath = s.DXFPath(id)
		status = "ready"
	}
	if err := os.MkdirAll(filepath.Dir(srcPath), 0o755); err != nil {
		return nil, err
	}
	if err := os.MkdirAll(s.ModelDir(id), 0o755); err != nil {
		return nil, err
	}
	f, err := os.Create(srcPath)
	if err != nil {
		return nil, err
	}
	written, copyErr := io.Copy(f, src)
	closeErr := f.Close()
	if copyErr != nil {
		return nil, copyErr
	}
	if closeErr != nil {
		return nil, closeErr
	}
	m := &Model{ID: id, Name: name, Size: written, Status: status, Kind: kind, CreatedAt: time.Now().UTC()}
	if err := s.write(m); err != nil {
		return nil, err
	}
	return m, nil
}

func (s *Store) write(m *Model) error {
	data, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return err
	}
	tmp := filepath.Join(s.ModelDir(m.ID), "model.json.tmp")
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, filepath.Join(s.ModelDir(m.ID), "model.json"))
}

func (s *Store) Get(id string) (*Model, error) {
	if !validID(id) {
		return nil, ErrInvalidID
	}
	data, err := os.ReadFile(filepath.Join(s.ModelDir(id), "model.json"))
	if errors.Is(err, os.ErrNotExist) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	var m Model
	if err := json.Unmarshal(data, &m); err != nil {
		return nil, err
	}
	// 存量迁移：无 kind 字段的旧记录按 ifc 处理（不破坏现有模型，W-0040）。
	if m.Kind == "" {
		m.Kind = KindIFC
	}
	return &m, nil
}

func (s *Store) List() ([]*Model, error) {
	entries, err := os.ReadDir(filepath.Join(s.DataDir, "models"))
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var out []*Model
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		m, err := s.Get(e.Name())
		if err == nil {
			out = append(out, m)
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].CreatedAt.After(out[j].CreatedAt) })
	return out, nil
}

func (s *Store) SetStatus(id, status, errMsg string) error {
	m, err := s.Get(id)
	if err != nil {
		return err
	}
	m.Status = status
	m.Error = errMsg
	return s.write(m)
}

func (s *Store) Delete(id string) error {
	m, err := s.Get(id)
	if err != nil {
		return err
	}
	_ = os.Remove(s.SourcePath(m))
	return os.RemoveAll(s.ModelDir(id))
}

func (s *Store) Recover() error {
	models, err := s.List()
	if err != nil {
		return err
	}
	for _, m := range models {
		if m.Status == "converting" {
			if err := s.SetStatus(m.ID, "failed", "interrupted by server restart"); err != nil {
				return err
			}
		}
	}
	return nil
}
