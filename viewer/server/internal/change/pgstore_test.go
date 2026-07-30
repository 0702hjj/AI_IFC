package change

import (
	"context"
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
