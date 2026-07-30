package change

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sort"
	"sync"
	"time"
)

type Provenance struct {
	Source string `json:"source"`
}

// ValidSource 仅允许 UI / AI 两种 provenance 来源。
func ValidSource(s string) bool {
	return s == "UI" || s == "AI"
}

type Entry struct {
	ID         string          `json:"id"`
	EntityID   string          `json:"entityId"`
	EntityName string          `json:"entityName"`
	Field      string          `json:"field"`
	OldValue   string          `json:"oldValue"`
	NewValue   string          `json:"newValue"`
	Author     string          `json:"author"`
	Provenance Provenance      `json:"provenance"`
	Operation  string          `json:"operation"`
	Diff       json.RawMessage `json:"diff,omitempty"`
	CreatedAt  time.Time       `json:"createdAt"`
}

// normalize 把空 Operation 归一化为 "update"，兼容存量数据。
func normalize(e *Entry) {
	if e.Operation == "" {
		e.Operation = "update"
	}
}

// Store 抽象后期可平移 PostgreSQL 等实现。
type Store interface {
	List(modelID string) ([]*Entry, error)
	Append(modelID string, entries ...*Entry) error
	DeleteModel(modelID string) error
}

// FileStore 假定 modelID 已被调用方校验，直接用于拼接磁盘路径。
type FileStore struct {
	DataDir string
	mu      sync.Mutex
}

func NewFileStore(dataDir string) *FileStore { return &FileStore{DataDir: dataDir} }

func (s *FileStore) changesPath(modelID string) string {
	return filepath.Join(s.DataDir, "models", modelID, "changes.json")
}

func newID() string {
	b := make([]byte, 6)
	_, _ = rand.Read(b)
	return "c_" + hex.EncodeToString(b)
}

func (s *FileStore) readAll(modelID string) ([]*Entry, error) {
	data, err := os.ReadFile(s.changesPath(modelID))
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var out []*Entry
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (s *FileStore) writeAll(modelID string, entries []*Entry) error {
	data, err := json.MarshalIndent(entries, "", "  ")
	if err != nil {
		return err
	}
	tmp := s.changesPath(modelID) + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, s.changesPath(modelID))
}

func (s *FileStore) List(modelID string) ([]*Entry, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	entries, err := s.readAll(modelID)
	if err != nil {
		return nil, err
	}
	for _, e := range entries {
		normalize(e)
	}
	sort.Slice(entries, func(i, j int) bool { return entries[i].CreatedAt.After(entries[j].CreatedAt) })
	return entries, nil
}

func (s *FileStore) Append(modelID string, entries ...*Entry) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	all, err := s.readAll(modelID)
	if err != nil {
		return err
	}
	for _, e := range entries {
		e.ID = newID()
		e.CreatedAt = time.Now().UTC()
		normalize(e)
		all = append(all, e)
	}
	return s.writeAll(modelID, all)
}

// DeleteModel 删除该模型的 changes.json；文件不存在视为成功（幂等）。
func (s *FileStore) DeleteModel(modelID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if err := os.Remove(s.changesPath(modelID)); err != nil && !errors.Is(err, os.ErrNotExist) {
		return err
	}
	return nil
}
