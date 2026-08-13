// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package override

import (
	"context"
	"errors"
	"os"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"
)

func newTestPgStore(t *testing.T) (*PgStore, string) {
	t.Helper()
	dsn := os.Getenv("VIEWER_TEST_PG_DSN")
	if dsn == "" {
		t.Skip("VIEWER_TEST_PG_DSN not set")
	}
	pool, err := pgxpool.New(context.Background(), dsn)
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	t.Cleanup(pool.Close)
	modelID := "m_test_override_pg01"
	t.Cleanup(func() {
		if _, err := pool.Exec(context.Background(), `DELETE FROM overrides WHERE model_id = $1`, modelID); err != nil {
			t.Errorf("cleanup: %v", err)
		}
	})
	ps, err := NewPgStore(pool)
	if err != nil {
		t.Fatalf("new pg store: %v", err)
	}
	return ps, modelID
}

func TestPgSetAndGetAll(t *testing.T) {
	ps, modelID := newTestPgStore(t)
	old, err := ps.Set(modelID, "e1", map[string]string{"Name": "Wall A", "FireRating": "F30"})
	if err != nil {
		t.Fatalf("set: %v", err)
	}
	if len(old) != 0 {
		t.Fatalf("old = %+v, want empty", old)
	}
	if _, err := ps.Set(modelID, "e2", map[string]string{"Description": "d2"}); err != nil {
		t.Fatalf("set: %v", err)
	}
	all, err := ps.GetAll(modelID)
	if err != nil {
		t.Fatalf("getAll: %v", err)
	}
	if len(all) != 2 || all["e1"]["Name"] != "Wall A" || all["e1"]["FireRating"] != "F30" || all["e2"]["Description"] != "d2" {
		t.Fatalf("all = %+v", all)
	}
}

func TestPgSetReturnsOldValues(t *testing.T) {
	ps, modelID := newTestPgStore(t)
	if _, err := ps.Set(modelID, "e1", map[string]string{"Name": "X", "Comments": "c1"}); err != nil {
		t.Fatalf("set: %v", err)
	}
	old, err := ps.Set(modelID, "e1", map[string]string{"Name": "Y", "Description": "new"})
	if err != nil {
		t.Fatalf("set: %v", err)
	}
	if len(old) != 1 || old["Name"] != "X" {
		t.Fatalf("old = %+v, want {Name:X}", old)
	}
	if _, ok := old["Description"]; ok {
		t.Fatalf("old = %+v, Description key must be absent", old)
	}
}

func TestPgSetEmptyValueClears(t *testing.T) {
	ps, modelID := newTestPgStore(t)
	if _, err := ps.Set(modelID, "e1", map[string]string{"Name": "X", "Comments": "c1"}); err != nil {
		t.Fatalf("set: %v", err)
	}
	old, err := ps.Set(modelID, "e1", map[string]string{"Name": ""})
	if err != nil {
		t.Fatalf("set: %v", err)
	}
	if old["Name"] != "X" {
		t.Fatalf("old = %+v, want {Name:X}", old)
	}
	all, err := ps.GetAll(modelID)
	if err != nil {
		t.Fatalf("getAll: %v", err)
	}
	if _, ok := all["e1"]["Name"]; ok {
		t.Fatalf("all = %+v, Name must be cleared", all)
	}
	if all["e1"]["Comments"] != "c1" {
		t.Fatalf("all = %+v, Comments must survive", all)
	}
}

func TestPgSetRejectsInvalidField(t *testing.T) {
	ps, modelID := newTestPgStore(t)
	_, err := ps.Set(modelID, "e1", map[string]string{"Height": "3000"})
	if !errors.Is(err, ErrInvalidField) {
		t.Fatalf("err = %v, want ErrInvalidField", err)
	}
}

func TestPgGetAllEmpty(t *testing.T) {
	ps, modelID := newTestPgStore(t)
	all, err := ps.GetAll(modelID)
	if err != nil {
		t.Fatalf("getAll: %v", err)
	}
	if len(all) != 0 {
		t.Fatalf("all = %+v, want empty", all)
	}
}

func TestPgDeleteModel(t *testing.T) {
	ps, modelID := newTestPgStore(t)
	if _, err := ps.Set(modelID, "e1", map[string]string{"Name": "x"}); err != nil {
		t.Fatal(err)
	}
	if _, err := ps.Set(modelID, "e2", map[string]string{"FireRating": "F30"}); err != nil {
		t.Fatal(err)
	}
	if err := ps.DeleteModel(modelID); err != nil {
		t.Fatalf("deleteModel: %v", err)
	}
	all, err := ps.GetAll(modelID)
	if err != nil {
		t.Fatal(err)
	}
	if len(all) != 0 {
		t.Fatalf("all = %+v, want empty", all)
	}
	if err := ps.DeleteModel(modelID); err != nil {
		t.Fatalf("second deleteModel err = %v, want nil", err)
	}
}
