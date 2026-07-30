package issue

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// PgStore 将 issue 记录存入 PostgreSQL（data jsonb），截图仍落盘 DataDir 下。
type PgStore struct {
	pool    *pgxpool.Pool
	DataDir string
}

// NewPgStore 使用已有连接池，dataDir 用于截图落盘；构造时自动建表。
func NewPgStore(pool *pgxpool.Pool, dataDir string) (*PgStore, error) {
	s := &PgStore{pool: pool, DataDir: dataDir}
	if err := s.migrate(context.Background()); err != nil {
		return nil, err
	}
	return s, nil
}

func (s *PgStore) migrate(ctx context.Context) error {
	_, err := s.pool.Exec(ctx, `CREATE TABLE IF NOT EXISTS issues (
		id text PRIMARY KEY,
		model_id text NOT NULL,
		data jsonb NOT NULL,
		created_at timestamptz NOT NULL
	)`)
	return err
}

func (s *PgStore) List(modelID string) ([]*Issue, error) {
	rows, err := s.pool.Query(context.Background(),
		`SELECT data FROM issues WHERE model_id = $1 ORDER BY created_at DESC`, modelID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*Issue
	for rows.Next() {
		var data []byte
		if err := rows.Scan(&data); err != nil {
			return nil, err
		}
		var iss Issue
		if err := json.Unmarshal(data, &iss); err != nil {
			return nil, err
		}
		out = append(out, &iss)
	}
	return out, rows.Err()
}

func (s *PgStore) Create(modelID string, iss *Issue) (*Issue, error) {
	if err := prepare(iss); err != nil {
		return nil, err
	}
	now := time.Now().UTC()
	iss.ID = newID()
	iss.CreatedAt = now
	iss.UpdatedAt = now
	iss.Screenshot = ""
	data, err := json.Marshal(iss)
	if err != nil {
		return nil, err
	}
	_, err = s.pool.Exec(context.Background(),
		`INSERT INTO issues (id, model_id, data, created_at) VALUES ($1, $2, $3, $4)`,
		iss.ID, modelID, data, now)
	if err != nil {
		return nil, err
	}
	return iss, nil
}

func (s *PgStore) Update(modelID, issueID string, patch IssuePatch) (*Issue, error) {
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
	ctx := context.Background()
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return nil, err
	}
	defer tx.Rollback(ctx)
	var data []byte
	err = tx.QueryRow(ctx,
		`SELECT data FROM issues WHERE id = $1 AND model_id = $2 FOR UPDATE`, issueID, modelID).Scan(&data)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	var iss Issue
	if err := json.Unmarshal(data, &iss); err != nil {
		return nil, err
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
	data, err = json.Marshal(&iss)
	if err != nil {
		return nil, err
	}
	if _, err := tx.Exec(ctx, `UPDATE issues SET data = $1 WHERE id = $2`, data, issueID); err != nil {
		return nil, err
	}
	if err := tx.Commit(ctx); err != nil {
		return nil, err
	}
	return &iss, nil
}

func (s *PgStore) Delete(modelID, issueID string) error {
	if !idPattern.MatchString(issueID) {
		return ErrInvalidID
	}
	tag, err := s.pool.Exec(context.Background(),
		`DELETE FROM issues WHERE id = $1 AND model_id = $2`, issueID, modelID)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	_ = os.Remove(filepath.Join(s.DataDir, "models", modelID, "issues", issueID+".png"))
	return nil
}

// DeleteModel 删除该模型全部 issue 行；零行不报错（幂等）。
func (s *PgStore) DeleteModel(modelID string) error {
	_, err := s.pool.Exec(context.Background(), `DELETE FROM issues WHERE model_id = $1`, modelID)
	return err
}

func (s *PgStore) SaveScreenshot(modelID, issueID string, png []byte) (string, error) {
	if !idPattern.MatchString(issueID) {
		return "", ErrInvalidID
	}
	rel, err := writeScreenshot(s.DataDir, modelID, issueID, png)
	if err != nil {
		return "", err
	}
	ctx := context.Background()
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return "", err
	}
	defer tx.Rollback(ctx)
	var data []byte
	err = tx.QueryRow(ctx,
		`SELECT data FROM issues WHERE id = $1 AND model_id = $2 FOR UPDATE`, issueID, modelID).Scan(&data)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", ErrNotFound
	}
	if err != nil {
		return "", err
	}
	var iss Issue
	if err := json.Unmarshal(data, &iss); err != nil {
		return "", err
	}
	iss.Screenshot = rel
	iss.UpdatedAt = time.Now().UTC()
	data, err = json.Marshal(&iss)
	if err != nil {
		return "", err
	}
	if _, err := tx.Exec(ctx, `UPDATE issues SET data = $1 WHERE id = $2`, data, issueID); err != nil {
		return "", err
	}
	if err := tx.Commit(ctx); err != nil {
		return "", err
	}
	return rel, nil
}
