package override

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sync"
)

var ErrInvalidField = errors.New("field not in whitelist")

// 白名单字段恰好为这五个，其他一律拒绝。
var validFields = map[string]bool{
	"Name":           true,
	"Description":    true,
	"Classification": true,
	"FireRating":     true,
	"Comments":       true,
}

func validate(patch map[string]string) error {
	for f := range patch {
		if !validFields[f] {
			return ErrInvalidField
		}
	}
	return nil
}

// Store 抽象 override 存储，FileStore 与 PgStore 实现同一接口。
type Store interface {
	GetAll(modelID string) (map[string]map[string]string, error)
	Set(modelID, entityID string, patch map[string]string) (old map[string]string, err error)
}

// apply 在已有数据上执行 patch：空字符串值 = 删除该字段 override。
// 返回被覆盖前的旧值（无旧值的键不存在）。
func apply(all map[string]map[string]string, entityID string, patch map[string]string) map[string]string {
	cur := all[entityID]
	old := map[string]string{}
	for f := range patch {
		if v, ok := cur[f]; ok {
			old[f] = v
		}
	}
	for f, v := range patch {
		if v == "" {
			delete(cur, f)
			continue
		}
		if cur == nil {
			cur = map[string]string{}
			all[entityID] = cur
		}
		cur[f] = v
	}
	if len(cur) == 0 {
		delete(all, entityID)
	}
	return old
}

// FileStore 假定 modelID 已被调用方校验，直接用于拼接磁盘路径。
type FileStore struct {
	DataDir string
	mu      sync.Mutex
}

func NewFileStore(dataDir string) *FileStore { return &FileStore{DataDir: dataDir} }

func (s *FileStore) overridesPath(modelID string) string {
	return filepath.Join(s.DataDir, "models", modelID, "overrides.json")
}

func (s *FileStore) readAll(modelID string) (map[string]map[string]string, error) {
	data, err := os.ReadFile(s.overridesPath(modelID))
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var out map[string]map[string]string
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (s *FileStore) writeAll(modelID string, all map[string]map[string]string) error {
	data, err := json.MarshalIndent(all, "", "  ")
	if err != nil {
		return err
	}
	tmp := s.overridesPath(modelID) + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, s.overridesPath(modelID))
}

func (s *FileStore) GetAll(modelID string) (map[string]map[string]string, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.readAll(modelID)
}

func (s *FileStore) Set(modelID, entityID string, patch map[string]string) (map[string]string, error) {
	if err := validate(patch); err != nil {
		return nil, err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	all, err := s.readAll(modelID)
	if err != nil {
		return nil, err
	}
	if all == nil {
		all = map[string]map[string]string{}
	}
	old := apply(all, entityID, patch)
	if err := s.writeAll(modelID, all); err != nil {
		return nil, err
	}
	return old, nil
}
