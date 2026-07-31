package change

import (
	"context"
	"encoding/json"
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
	modelID := "m_test_change_pg01"
	t.Cleanup(func() {
		if _, err := pool.Exec(context.Background(), `DELETE FROM changes WHERE model_id = $1`, modelID); err != nil {
			t.Errorf("cleanup: %v", err)
		}
	})
	ps, err := NewPgStore(pool)
	if err != nil {
		t.Fatalf("new pg store: %v", err)
	}
	return ps, modelID
}

func TestPgAppendAndList(t *testing.T) {
	ps, modelID := newTestPgStore(t)
	e := &Entry{
		EntityID: "e1", EntityName: "Wall", Field: "width",
		OldValue: "100", NewValue: "200",
		Author: "local-user", Provenance: Provenance{Source: "UI"},
	}
	e2 := &Entry{EntityID: "e1", EntityName: "Wall", Field: "height", OldValue: "3000", NewValue: "3200", Author: "ai-bot", Provenance: Provenance{Source: "AI"}}
	if err := ps.Append(modelID, e, e2); err != nil {
		t.Fatalf("append: %v", err)
	}
	if e.ID == "" || len(e.ID) != 14 || e.ID[:2] != "c_" {
		t.Fatalf("bad id: %q", e.ID)
	}
	if e.CreatedAt.IsZero() {
		t.Fatal("createdAt not set")
	}
	list, err := ps.List(modelID)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if len(list) != 2 {
		t.Fatalf("list = %+v", list)
	}
	if list[0].ID != e2.ID || list[1].ID != e.ID {
		t.Fatalf("order = [%s %s], want [%s %s]", list[0].ID, list[1].ID, e2.ID, e.ID)
	}
	if list[1].Field != "width" || list[1].OldValue != "100" || list[1].NewValue != "200" || list[1].EntityName != "Wall" {
		t.Fatalf("entry = %+v", list[1])
	}
	if list[1].Author != "local-user" || list[1].Provenance.Source != "UI" {
		t.Fatalf("provenance = %+v", list[1])
	}
	if list[0].Author != "ai-bot" || list[0].Provenance.Source != "AI" {
		t.Fatalf("provenance = %+v", list[0])
	}
}

func TestPgMigrateAddsColumnsIdempotent(t *testing.T) {
	dsn := os.Getenv("VIEWER_TEST_PG_DSN")
	if dsn == "" {
		t.Skip("VIEWER_TEST_PG_DSN not set")
	}
	pool, err := pgxpool.New(context.Background(), dsn)
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	defer pool.Close()
	ctx := context.Background()
	if _, err := pool.Exec(ctx, `DROP TABLE IF EXISTS changes`); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `CREATE TABLE changes (
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
	)`); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 2; i++ {
		if _, err := NewPgStore(pool); err != nil {
			t.Fatalf("NewPgStore #%d on legacy table: %v", i+1, err)
		}
	}
	var opCount, diffCount int
	if err := pool.QueryRow(ctx,
		`SELECT
			(SELECT count(*) FROM information_schema.columns WHERE table_name='changes' AND column_name='operation'),
			(SELECT count(*) FROM information_schema.columns WHERE table_name='changes' AND column_name='diff')`).Scan(&opCount, &diffCount); err != nil {
		t.Fatal(err)
	}
	if opCount != 1 || diffCount != 1 {
		t.Fatalf("columns operation=%d diff=%d, want 1/1", opCount, diffCount)
	}
}

func TestPgOperationDiffRoundtrip(t *testing.T) {
	ps, modelID := newTestPgStore(t)
	diff := json.RawMessage(`{"op":"override"}`)
	e := &Entry{
		EntityID: "e1", EntityName: "Wall", Field: "width",
		OldValue: "100", NewValue: "200",
		Author: "ai-bot", Provenance: Provenance{Source: "AI"},
		Operation: "migrate", Diff: diff,
	}
	noDiff := &Entry{EntityID: "e2", EntityName: "Wall", Field: "height", OldValue: "3000", NewValue: "3200"}
	if err := ps.Append(modelID, e, noDiff); err != nil {
		t.Fatalf("append: %v", err)
	}
	if noDiff.Operation != "update" {
		t.Fatalf("Append must normalize empty operation, got %q", noDiff.Operation)
	}
	list, err := ps.List(modelID)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	byID := map[string]*Entry{}
	for _, got := range list {
		byID[got.ID] = got
	}
	gotE := byID[e.ID]
	if gotE == nil || gotE.Operation != "migrate" {
		t.Fatalf("entry = %+v, want operation migrate", gotE)
	}
	var gotDiff interface{}
	if err := json.Unmarshal(gotE.Diff, &gotDiff); err != nil {
		t.Fatalf("diff not valid json: %v", err)
	}
	m, ok := gotDiff.(map[string]interface{})
	if !ok || m["op"] != "override" || len(m) != 1 {
		t.Fatalf("diff = %v, want %s", gotDiff, diff)
	}
	gotNo := byID[noDiff.ID]
	if gotNo == nil || gotNo.Operation != "update" {
		t.Fatalf("entry = %+v, want operation update", gotNo)
	}
	if gotNo.Diff != nil {
		t.Fatalf("diff = %s, NULL column must read back nil", gotNo.Diff)
	}
}

func TestPgListEmpty(t *testing.T) {
	ps, modelID := newTestPgStore(t)
	list, err := ps.List(modelID)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if len(list) != 0 {
		t.Fatalf("list = %+v, want empty", list)
	}
}

func TestPgDeleteModel(t *testing.T) {
	ps, modelID := newTestPgStore(t)
	if err := ps.Append(modelID,
		&Entry{EntityID: "e1", Field: "Name", NewValue: "x"},
		&Entry{EntityID: "e2", Field: "Name", NewValue: "y"}); err != nil {
		t.Fatal(err)
	}
	if err := ps.DeleteModel(modelID); err != nil {
		t.Fatalf("deleteModel: %v", err)
	}
	list, err := ps.List(modelID)
	if err != nil {
		t.Fatal(err)
	}
	if len(list) != 0 {
		t.Fatalf("list = %+v, want empty", list)
	}
	if err := ps.DeleteModel(modelID); err != nil {
		t.Fatalf("second deleteModel err = %v, want nil", err)
	}
}
