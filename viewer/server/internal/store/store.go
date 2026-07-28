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
	"time"
)

var ErrNotFound = errors.New("model not found")
var ErrInvalidID = errors.New("invalid model id")

var idPattern = regexp.MustCompile(`^m_[0-9a-f]{16}$`)

func validID(id string) bool { return idPattern.MatchString(id) }

type Model struct {
	ID        string    `json:"id"`
	Name      string    `json:"name"`
	Size      int64     `json:"size"`
	Status    string    `json:"status"`
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
func (s *Store) ModelDir(id string) string { return filepath.Join(s.DataDir, "models", id) }

func (s *Store) Create(name string, size int64, src io.Reader) (*Model, error) {
	id := newID()
	if err := os.MkdirAll(filepath.Dir(s.IFCPath(id)), 0o755); err != nil {
		return nil, err
	}
	if err := os.MkdirAll(s.ModelDir(id), 0o755); err != nil {
		return nil, err
	}
	f, err := os.Create(s.IFCPath(id))
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
	m := &Model{ID: id, Name: name, Size: written, Status: "converting", CreatedAt: time.Now().UTC()}
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
	if _, err := s.Get(id); err != nil {
		return err
	}
	_ = os.Remove(s.IFCPath(id))
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
