// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package override

import (
	"context"
	"sort"

	"github.com/jackc/pgx/v5/pgxpool"
)

// PgStore 将 override 记录存入 PostgreSQL（列式，PK 三元组）。
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
	_, err := s.pool.Exec(ctx, `CREATE TABLE IF NOT EXISTS overrides (
		model_id text NOT NULL,
		entity_id text NOT NULL,
		field text NOT NULL,
		value text NOT NULL,
		PRIMARY KEY (model_id, entity_id, field)
	)`)
	return err
}

func (s *PgStore) GetAll(modelID string) (map[string]map[string]string, error) {
	rows, err := s.pool.Query(context.Background(),
		`SELECT entity_id, field, value FROM overrides WHERE model_id = $1`, modelID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[string]map[string]string{}
	for rows.Next() {
		var entityID, field, value string
		if err := rows.Scan(&entityID, &field, &value); err != nil {
			return nil, err
		}
		if out[entityID] == nil {
			out[entityID] = map[string]string{}
		}
		out[entityID][field] = value
	}
	return out, rows.Err()
}

func (s *PgStore) Set(modelID, entityID string, patch map[string]string) (map[string]string, error) {
	if err := validate(patch); err != nil {
		return nil, err
	}
	ctx := context.Background()
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return nil, err
	}
	defer tx.Rollback(ctx)
	rows, err := tx.Query(ctx,
		`SELECT field, value FROM overrides WHERE model_id = $1 AND entity_id = $2 FOR UPDATE`, modelID, entityID)
	if err != nil {
		return nil, err
	}
	cur := map[string]string{}
	for rows.Next() {
		var field, value string
		if err := rows.Scan(&field, &value); err != nil {
			rows.Close()
			return nil, err
		}
		cur[field] = value
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	old := map[string]string{}
	for f := range patch {
		if v, ok := cur[f]; ok {
			old[f] = v
		}
	}
	fields := make([]string, 0, len(patch))
	for f := range patch {
		fields = append(fields, f)
	}
	sort.Strings(fields)
	for _, f := range fields {
		v := patch[f]
		if v == "" {
			if _, err := tx.Exec(ctx,
				`DELETE FROM overrides WHERE model_id = $1 AND entity_id = $2 AND field = $3`,
				modelID, entityID, f); err != nil {
				return nil, err
			}
			continue
		}
		if _, err := tx.Exec(ctx,
			`INSERT INTO overrides (model_id, entity_id, field, value) VALUES ($1, $2, $3, $4)
			 ON CONFLICT (model_id, entity_id, field) DO UPDATE SET value = EXCLUDED.value`,
			modelID, entityID, f, v); err != nil {
			return nil, err
		}
	}
	if err := tx.Commit(ctx); err != nil {
		return nil, err
	}
	return old, nil
}

// DeleteModel 删除该模型全部 override 行；零行不报错（幂等）。
func (s *PgStore) DeleteModel(modelID string) error {
	_, err := s.pool.Exec(context.Background(), `DELETE FROM overrides WHERE model_id = $1`, modelID)
	return err
}
