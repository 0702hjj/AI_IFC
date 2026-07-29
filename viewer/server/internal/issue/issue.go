package issue

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"
)

var ErrNotFound = errors.New("issue not found")
var ErrInvalidID = errors.New("invalid issue id")
var ErrInvalidStatus = errors.New("invalid issue status")
var ErrEmptyTitle = errors.New("issue title is required")

var idPattern = regexp.MustCompile(`^i_[0-9a-f]{12}$`)

var validStatus = map[string]bool{"open": true, "checking": true, "resolved": true}

type Camera struct {
	Eye  [3]float64 `json:"eye"`
	Look [3]float64 `json:"look"`
	Up   [3]float64 `json:"up"`
}

type Issue struct {
	ID         string    `json:"id"`
	EntityID   string    `json:"entityId"`
	EntityName string    `json:"entityName"`
	EntityType string    `json:"entityType"`
	Title      string    `json:"title"`
	Comment    string    `json:"comment"`
	Status     string    `json:"status"`
	Camera     Camera    `json:"camera"`
	Screenshot string    `json:"screenshot"`
	CreatedAt  time.Time `json:"createdAt"`
	UpdatedAt  time.Time `json:"updatedAt"`
}

type IssuePatch struct {
	Title   *string `json:"title"`
	Comment *string `json:"comment"`
	Status  *string `json:"status"`
}

// Store 抽象后期可平移 PostgreSQL 等实现。
type Store interface {
	List(modelID string) ([]*Issue, error)
	Create(modelID string, iss *Issue) (*Issue, error)
	Update(modelID, issueID string, patch IssuePatch) (*Issue, error)
	Delete(modelID, issueID string) error
	SaveScreenshot(modelID, issueID string, png []byte) (string, error)
}

// FileStore 假定 modelID 已被调用方校验，直接用于拼接磁盘路径。
type FileStore struct {
	DataDir string
	mu      sync.Mutex
}

func NewFileStore(dataDir string) *FileStore { return &FileStore{DataDir: dataDir} }

func (s *FileStore) issuesPath(modelID string) string {
	return filepath.Join(s.DataDir, "models", modelID, "issues.json")
}

func (s *FileStore) issuesDir(modelID string) string {
	return filepath.Join(s.DataDir, "models", modelID, "issues")
}

func newID() string {
	b := make([]byte, 6)
	_, _ = rand.Read(b)
	return "i_" + hex.EncodeToString(b)
}

func (s *FileStore) readAll(modelID string) ([]*Issue, error) {
	data, err := os.ReadFile(s.issuesPath(modelID))
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var out []*Issue
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (s *FileStore) writeAll(modelID string, issues []*Issue) error {
	data, err := json.MarshalIndent(issues, "", "  ")
	if err != nil {
		return err
	}
	tmp := s.issuesPath(modelID) + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, s.issuesPath(modelID))
}

func (s *FileStore) List(modelID string) ([]*Issue, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	issues, err := s.readAll(modelID)
	if err != nil {
		return nil, err
	}
	sort.Slice(issues, func(i, j int) bool { return issues[i].CreatedAt.After(issues[j].CreatedAt) })
	return issues, nil
}

func (s *FileStore) Create(modelID string, iss *Issue) (*Issue, error) {
	iss.Title = strings.TrimSpace(iss.Title)
	if iss.Title == "" {
		return nil, ErrEmptyTitle
	}
	if iss.Status == "" {
		iss.Status = "open"
	}
	if !validStatus[iss.Status] {
		return nil, ErrInvalidStatus
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	issues, err := s.readAll(modelID)
	if err != nil {
		return nil, err
	}
	now := time.Now().UTC()
	iss.ID = newID()
	iss.CreatedAt = now
	iss.UpdatedAt = now
	iss.Screenshot = ""
	issues = append(issues, iss)
	if err := s.writeAll(modelID, issues); err != nil {
		return nil, err
	}
	return iss, nil
}

func (s *FileStore) Update(modelID, issueID string, patch IssuePatch) (*Issue, error) {
	if !idPattern.MatchString(issueID) {
		return nil, ErrInvalidID
	}
	if patch.Status != nil && !validStatus[*patch.Status] {
		return nil, ErrInvalidStatus
	}
	if patch.Title != nil {
		*patch.Title = strings.TrimSpace(*patch.Title)
		if *patch.Title == "" {
			return nil, ErrEmptyTitle
		}
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	issues, err := s.readAll(modelID)
	if err != nil {
		return nil, err
	}
	for _, iss := range issues {
		if iss.ID != issueID {
			continue
		}
		if patch.Title != nil {
			iss.Title = *patch.Title
		}
		if patch.Comment != nil {
			iss.Comment = *patch.Comment
		}
		if patch.Status != nil {
			iss.Status = *patch.Status
		}
		iss.UpdatedAt = time.Now().UTC()
		if err := s.writeAll(modelID, issues); err != nil {
			return nil, err
		}
		return iss, nil
	}
	return nil, ErrNotFound
}

func (s *FileStore) Delete(modelID, issueID string) error {
	if !idPattern.MatchString(issueID) {
		return ErrInvalidID
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	issues, err := s.readAll(modelID)
	if err != nil {
		return err
	}
	out := issues[:0]
	found := false
	for _, iss := range issues {
		if iss.ID == issueID {
			found = true
			continue
		}
		out = append(out, iss)
	}
	if !found {
		return ErrNotFound
	}
	if err := s.writeAll(modelID, out); err != nil {
		return err
	}
	_ = os.Remove(filepath.Join(s.issuesDir(modelID), issueID+".png"))
	return nil
}

func (s *FileStore) SaveScreenshot(modelID, issueID string, png []byte) (string, error) {
	if !idPattern.MatchString(issueID) {
		return "", ErrInvalidID
	}
	if err := os.MkdirAll(s.issuesDir(modelID), 0o755); err != nil {
		return "", err
	}
	rel := "issues/" + issueID + ".png"
	abs := filepath.Join(s.DataDir, "models", modelID, rel)
	tmp := abs + ".tmp"
	if err := os.WriteFile(tmp, png, 0o644); err != nil {
		return "", err
	}
	if err := os.Rename(tmp, abs); err != nil {
		return "", err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	issues, err := s.readAll(modelID)
	if err != nil {
		return "", err
	}
	for _, iss := range issues {
		if iss.ID == issueID {
			iss.Screenshot = rel
			iss.UpdatedAt = time.Now().UTC()
			if err := s.writeAll(modelID, issues); err != nil {
				return "", err
			}
			return rel, nil
		}
	}
	return "", ErrNotFound
}
