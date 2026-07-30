package change

import (
	"context"
	"encoding/json"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// PgStore 将 change 记录存入 PostgreSQL（列式 + provenance jsonb）。
type PgStore struct {
	pool *pgxpool.Pool
}

// NewPgStore 使用已有连接池，构造时自动建表。
func NewPgStore(pool *pgxpool.Pool) (*PgStore, error) {
	s := &PgStore{pool: pool}
	if err := s.migrate(context.Background()); err != nil {
		return nil, err
	}
	return s, nil
}

func (s *PgStore) migrate(ctx context.Context) error {
	_, err := s.pool.Exec(ctx, `CREATE TABLE IF NOT EXISTS changes (
		id text PRIMARY KEY,
		model_id text NOT NULL,
		entity_id text NOT NULL,
		entity_name text NOT NULL,
		field text NOT NULL,
		old_value text NOT NULL,
		new_value text NOT NULL,
		author text NOT NULL,
		provenance jsonb NOT NULL,
		created_at timestamptz NOT NULL
	)`)
	return err
}

func (s *PgStore) List(modelID string) ([]*Entry, error) {
	rows, err := s.pool.Query(context.Background(),
		`SELECT id, entity_id, entity_name, field, old_value, new_value, author, provenance, created_at
		 FROM changes WHERE model_id = $1 ORDER BY created_at DESC`, modelID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*Entry
	for rows.Next() {
		var e Entry
		var provenance []byte
		if err := rows.Scan(&e.ID, &e.EntityID, &e.EntityName, &e.Field, &e.OldValue, &e.NewValue,
			&e.Author, &provenance, &e.CreatedAt); err != nil {
			return nil, err
		}
		if err := json.Unmarshal(provenance, &e.Provenance); err != nil {
			return nil, err
		}
		out = append(out, &e)
	}
	return out, rows.Err()
}

func (s *PgStore) Append(modelID string, entries ...*Entry) error {
	ctx := context.Background()
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)
	for _, e := range entries {
		e.ID = newID()
		e.CreatedAt = time.Now().UTC()
		provenance, err := json.Marshal(e.Provenance)
		if err != nil {
			return err
		}
		if _, err := tx.Exec(ctx,
			`INSERT INTO changes (id, model_id, entity_id, entity_name, field, old_value, new_value, author, provenance, created_at)
			 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
			e.ID, modelID, e.EntityID, e.EntityName, e.Field, e.OldValue, e.NewValue, e.Author, provenance, e.CreatedAt); err != nil {
			return err
		}
	}
	return tx.Commit(ctx)
}

// DeleteModel 删除该模型全部 change 行；零行不报错（幂等）。
func (s *PgStore) DeleteModel(modelID string) error {
	_, err := s.pool.Exec(context.Background(), `DELETE FROM changes WHERE model_id = $1`, modelID)
	return err
}
