# IFC Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 AI_IFC/viewer/ 下实现独立全栈 IFC 查看器：Go 后端（上传/转换/静态服务/下载）+ Node 转换器（IFC→XKT+元数据）+ React/xeokit 前端（模型库 + 查看器）。

**Architecture:** 浏览器只消费 XKT 与 xeokit 元模型 JSON，永不解析 IFC。Go 后端除 `github.com/jackc/pgx/v5`（PostgreSQL 存储，可选）外零第三方依赖（stdlib net/http），通过子进程调用 Node 转换器；转换器用 @xeokit/xeokit-convert 产几何、用 web-ifc 产元模型，二者注入同一 XKTModel 保证 id 一致。

**Tech Stack:** Go 1.26 (stdlib only，例外：pgx/v5 用于可选 PG 存储), Node ≥18 (@xeokit/xeokit-convert, web-ifc), React 18 + Vite + TS + @xeokit/xeokit-sdk + react-router-dom + zustand。

## Global Constraints

- 所有代码位于 `AI_IFC/viewer/`；所有 git 提交在 AI_IFC 仓库（`<repo>`）
- 后端端口 `8090`；前端 dev 端口 `5173`，vite proxy `/api` 与 `/models` → `http://localhost:8090`
- 上传仅 `.ifc`，上限 200MB；JSON 信封 `{code, message, data}`，成功 `code=0`
- 模型 id：`"m_"` + 16 位小写 hex（crypto/rand）
- Go 后端仅允许 `github.com/jackc/pgx/v5`（PostgreSQL 存储，可选），其余保持 stdlib only
- 前端 TS 文件 ≤500 行；路径别名 `@` → `src`
- 接口契约以 `api.md` 为准
- 转换 worker 数 = 2；重启后 `converting` 一律恢复为 `failed`

---

### Task 1: converter — Node 转换器（IFC → model.xkt + metadata.json）

**Files:**
- Create: `viewer/converter/package.json`
- Create: `viewer/converter/convert.js`
- Create: `viewer/converter/lib/metadata.js`
- Create: `viewer/converter/test/convert.test.js`
- Create: `viewer/converter/test/fixtures/wall-with-opening-and-window.ifc`（从 `research/ifc/Sample-Test-Files-main/IFC 4.0.2.1 (IFC 4)/ISO Spec - ReferenceView_V1.2/wall-with-opening-and-window.ifc` 复制）

**Interfaces:**
- Produces（被 server 调用）: `node converter/convert.js <input.ifc> <outDir>`；成功时写出 `<outDir>/model.xkt` 与 `<outDir>/metadata.json`，stdout 最后一行输出 `{"ok":true,"xktBytes":N,"metaObjects":M}`；失败时 exit code≠0，stderr 含错误原因
- metadata.json 为 xeokit 元模型格式（api.md §5）：`{id?, projectId, metaObjects:[{id,type,name,parent,propertySetIds?}], propertySets:[{id,name,type,properties:[{name,value,type}]}]}`；`metaObjects[].id` = IFC GlobalId，与 XKT 内 entity id 一致

- [ ] **Step 1: 初始化 converter 包并安装依赖**

```bash
cd <repo>/viewer/converter
npm init -y
npm install @xeokit/xeokit-convert web-ifc
mkdir -p test/fixtures
cp "../../research/ifc/Sample-Test-Files-main/IFC 4.0.2.1 (IFC 4)/ISO Spec - ReferenceView_V1.2/wall-with-opening-and-window.ifc" test/fixtures/
```

`package.json` 增加：`"scripts": {"test": "node --test test/"}`；确认 `node_modules/web-ifc/web-ifc-api-node.js` 与 `node_modules/web-ifc/web-ifc.wasm` 存在。

- [ ] **Step 2: 写失败测试**

`viewer/converter/test/convert.test.js`：

```js
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const { convertIfc } = require("../convert");

const FIXTURE = path.join(__dirname, "fixtures", "wall-with-opening-and-window.ifc");
const OUT = path.join(__dirname, ".tmp-out");

test("convertIfc produces xkt and metadata", async (t) => {
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.mkdirSync(OUT, { recursive: true });
  const stats = await convertIfc(FIXTURE, OUT);
  assert.ok(stats.xktBytes > 10 * 1024, "xkt should be non-trivial");
  assert.ok(stats.metaObjects > 0);
  const meta = JSON.parse(fs.readFileSync(path.join(OUT, "metadata.json"), "utf8"));
  const types = new Set(meta.metaObjects.map((o) => o.type));
  assert.ok([...types].some((t2) => t2.startsWith("Ifc")), "should contain Ifc* types");
  // 每个 propertySetIds 引用必须可解析
  const psetIds = new Set(meta.propertySets.map((p) => p.id));
  for (const o of meta.metaObjects) {
    for (const pid of o.propertySetIds || []) assert.ok(psetIds.has(pid), `dangling pset ${pid}`);
  }
  // parent 引用必须可解析或为 null
  const objIds = new Set(meta.metaObjects.map((o) => o.id));
  for (const o of meta.metaObjects) {
    if (o.parent != null) assert.ok(objIds.has(o.parent), `dangling parent ${o.parent}`);
  }
  // 至少一个构件携带属性集
  assert.ok(meta.metaObjects.some((o) => (o.propertySetIds || []).length > 0), "expected psets");
});
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd viewer/converter && npm test`
Expected: FAIL，`Cannot find module '../convert'`

- [ ] **Step 4: 实现元数据提取 lib/metadata.js**

```js
const path = require("path");
const WebIFC = require("web-ifc/web-ifc-api-node.js");

// 提取空间结构树 + 属性集，输出 xeokit 元模型 JSON
async function extractMetadata(ifcData) {
  const ifcAPI = new WebIFC.IfcAPI();
  ifcAPI.SetWasmPath(path.join(__dirname, "..", "node_modules", "web-ifc") + "/");
  await ifcAPI.Init();
  const modelID = ifcAPI.OpenModel(new Uint8Array(ifcData));
  try {
    const props = new WebIFC.Properties(ifcAPI);
    const spatial = await props.getSpatialStructure(modelID, false);
    const metaObjects = [];
    const propertySets = [];

    function typeName(code) {
      try { return ifcAPI.GetNameFromTypeCode(code) || "IfcElement"; } catch { return "IfcElement"; }
    }

    async function walk(node, parentId) {
      const gid = node.GlobalId && node.GlobalId.value ? node.GlobalId.value : `e${node.expressID}`;
      const psets = await props.getPropertySets(modelID, node.expressID, true, false);
      const propertySetIds = [];
      for (const ps of psets || []) {
        const psId = `pset_${node.expressID}_${propertySetIds.length}`;
        const properties = (ps.HasProperties || []).map((p) => ({
          name: p.Name && p.Name.value != null ? String(p.Name.value) : "Property",
          value: p.NominalValue && p.NominalValue.value !== undefined ? p.NominalValue.value : null,
          type: p.NominalValue && p.NominalValue.type != null ? String(p.NominalValue.type) : "value",
        }));
        propertySets.push({ id: psId, name: ps.Name && ps.Name.value ? String(ps.Name.value) : "Pset", type: "Pset", properties });
        propertySetIds.push(psId);
      }
      const mo = {
        id: String(gid),
        type: typeName(node.type),
        name: node.Name && node.Name.value != null ? String(node.Name.value) : typeName(node.type),
        parent: parentId,
      };
      if (propertySetIds.length > 0) mo.propertySetIds = propertySetIds;
      metaObjects.push(mo);
      for (const child of node.children || []) await walk(child, mo.id);
    }

    await walk(spatial, null);
    return { projectId: "project", metaObjects, propertySets };
  } finally {
    ifcAPI.CloseModel(modelID);
  }
}

module.exports = { extractMetadata };
```

- [ ] **Step 5: 实现 convert.js（几何 + 元数据注入同一 XKTModel）**

```js
#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const { XKTModel, parseIFCIntoXKTModel, writeXKTModelToArrayBuffer } = require("@xeokit/xeokit-convert");
const { extractMetadata } = require("./lib/metadata");

async function convertIfc(inputPath, outDir) {
  const ifcData = fs.readFileSync(inputPath);
  const meta = await extractMetadata(ifcData);

  const xktModel = new XKTModel();
  await parseIFCIntoXKTModel({
    data: ifcData,
    xktModel,
    wasmPath: path.join(__dirname, "node_modules", "web-ifc") + "/",
    log: (msg) => console.error(`[parseIFC] ${msg}`),
  });

  // 将提取的元模型注入同一 XKTModel，id 与几何 entity 对齐
  for (const ps of meta.propertySets) {
    xktModel.createPropertySet({
      propertySetId: ps.id,
      propertySetType: ps.type,
      propertySetName: ps.name,
      properties: ps.properties.map((p, i) => ({ id: `${ps.id}_p${i}`, type: "Default", name: p.name, value: p.value })),
    });
  }
  for (const mo of meta.metaObjects) {
    xktModel.createMetaObject({
      metaObjectId: mo.id,
      metaObjectType: mo.type,
      metaObjectName: mo.name,
      parentMetaObjectId: mo.parent || undefined,
      propertySetIds: mo.propertySetIds || [],
    });
  }

  // 一致性校验：带几何的 entity id 必须能与元模型对上
  const entityIds = Object.keys(xktModel.entities || {});
  const metaIds = new Set(meta.metaObjects.map((o) => o.id));
  const matched = entityIds.filter((id) => metaIds.has(id));
  if (entityIds.length > 0 && matched.length === 0) {
    throw new Error(`entity id mismatch: sample entity ids ${entityIds.slice(0, 3).join(",")} not found in metamodel; inspect xktModel.entities keys and adjust extractMetadata id mapping`);
  }

  await xktModel.finalize();
  const xktArrayBuffer = writeXKTModelToArrayBuffer(xktModel, "", {}, {});

  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, "model.xkt"), Buffer.from(xktArrayBuffer));
  fs.writeFileSync(path.join(outDir, "metadata.json"), JSON.stringify(meta, null, 2));
  return { xktBytes: xktArrayBuffer.byteLength, metaObjects: meta.metaObjects.length };
}

if (require.main === module) {
  const [input, outDir] = process.argv.slice(2);
  if (!input || !outDir) {
    console.error("usage: node convert.js <input.ifc> <outDir>");
    process.exit(2);
  }
  convertIfc(input, outDir)
    .then((stats) => console.log(JSON.stringify({ ok: true, ...stats })))
    .catch((err) => { console.error(`conversion failed: ${err.message}`); process.exit(1); });
}

module.exports = { convertIfc };
```

- [ ] **Step 6: 运行测试确认通过；若 entity id 校验失败则按错误提示对齐 id 映射**

Run: `cd viewer/converter && npm test`
Expected: PASS。若 FAIL 于 "entity id mismatch"：打印 `xktModel.entities` 前 5 个 key，确认 parseIFC 使用的 id 形态（如 GlobalId 原样 / 带前缀），修改 `lib/metadata.js` 的 `gid` 生成逻辑使其一致后重跑。

- [ ] **Step 7: 手工验证 CLI 入口**

Run: `node convert.js test/fixtures/wall-with-opening-and-window.ifc /tmp/opencode/xkt-smoke`
Expected: stdout 末行 `{"ok":true,...}`，两个产物文件存在。

- [ ] **Step 8: Commit**

```bash
cd <repo>
git add viewer/converter
git commit -m "feat(viewer): add IFC->XKT converter with metamodel extraction"
```

（`node_modules` 与 `test/.tmp-out` 需加入 `viewer/converter/.gitignore`）

---

### Task 2: server — 存储层 store（文件系统 + model.json 状态）

**Files:**
- Create: `viewer/server/go.mod`
- Create: `viewer/server/internal/store/store.go`
- Create: `viewer/server/internal/store/store_test.go`

**Interfaces:**
- Produces（被 Task 3/4 消费）:
  - `type Model struct { ID string; Name string; Size int64; Status string; CreatedAt time.Time; Error string }`（Status ∈ `"converting"|"ready"|"failed"`，JSON tag 小写：`id,name,size,status,createdAt,error`）
  - `type Store struct{ DataDir string }`；`func NewStore(dataDir string) *Store`
  - `(s *Store) Create(name string, size int64, src io.Reader) (*Model, error)` — 生成 id、落盘 `uploads/{id}.ifc`、写 `models/{id}/model.json{status:"converting"}`
  - `(s *Store) Get(id string) (*Model, error)`（不存在返回 `ErrNotFound`）
  - `(s *Store) List() ([]*Model, error)` — 扫描 `models/*/model.json`，按 CreatedAt 倒序
  - `(s *Store) SetStatus(id, status, errMsg string) error`
  - `(s *Store) Delete(id string) error` — 删 `uploads/{id}.ifc` 与 `models/{id}/`
  - `(s *Store) IFCPath(id string) string`；`(s *Store) ModelDir(id string) string`
  - `(s *Store) Recover() error` — 把所有 `converting` 改为 `failed`（errMsg `"interrupted by server restart"`）

- [ ] **Step 1: 初始化 go module 并写失败测试**

```bash
mkdir -p <repo>/viewer/server
cd <repo>/viewer/server
go mod init ifcviewer/server
```

`internal/store/store_test.go`：

```go
package store

import (
	"strings"
	"testing"
)

func TestCreateGetListDelete(t *testing.T) {
	s := NewStore(t.TempDir())
	m, err := s.Create("a.ifc", 11, strings.NewReader("hello world"))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(m.ID, "m_") || len(m.ID) != 18 {
		t.Fatalf("bad id %q", m.ID)
	}
	if m.Status != "converting" {
		t.Fatalf("status = %q", m.Status)
	}
	got, err := s.Get(m.ID)
	if err != nil || got.Name != "a.ifc" {
		t.Fatalf("get: %v %+v", err, got)
	}
	if err := s.SetStatus(m.ID, "ready", ""); err != nil {
		t.Fatal(err)
	}
	list, err := s.List()
	if err != nil || len(list) != 1 || list[0].Status != "ready" {
		t.Fatalf("list: %v %+v", err, list)
	}
	if err := s.Delete(m.ID); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Get(m.ID); err != ErrNotFound {
		t.Fatalf("expected ErrNotFound, got %v", err)
	}
}

func TestRecoverMarksConvertingFailed(t *testing.T) {
	s := NewStore(t.TempDir())
	m, _ := s.Create("b.ifc", 3, strings.NewReader("abc"))
	if err := s.Recover(); err != nil {
		t.Fatal(err)
	}
	got, _ := s.Get(m.ID)
	if got.Status != "failed" || got.Error == "" {
		t.Fatalf("recover: %+v", got)
	}
}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd viewer/server && go test ./internal/store/`
Expected: FAIL（编译错误，store 未实现）

- [ ] **Step 3: 实现 store.go**

核心实现（error 包装、原子写：先写 `model.json.tmp` 再 rename）：

```go
package store

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"sort"
	"time"
)

var ErrNotFound = errors.New("model not found")

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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd viewer/server && go test ./internal/store/ -v`
Expected: PASS（2 个测试）

- [ ] **Step 5: Commit**

```bash
cd <repo>
git add viewer/server
git commit -m "feat(viewer): add filesystem model store with status tracking"
```

---

### Task 3: server — 转换队列 convert（worker pool + 子进程）

**Files:**
- Create: `viewer/server/internal/convert/queue.go`
- Create: `viewer/server/internal/convert/queue_test.go`

**Interfaces:**
- Consumes: Task 2 的 `store.Store`（`SetStatus`, `IFCPath`, `ModelDir`）
- Produces（被 Task 4 消费）:
  - `type Runner interface { Run(ctx context.Context, inputPath, outDir string) error }`
  - `type ExecRunner struct { NodeBin, Script string }` — `exec.CommandContext(ctx, NodeBin, Script, inputPath, outDir)`，stderr 尾 500 字符进 error
  - `type Queue struct`；`func NewQueue(st *store.Store, r Runner, workers int) *Queue`；`(q *Queue) Start(ctx context.Context)`；`(q *Queue) Enqueue(id string) bool`（重复 id 返回 false）
- 行为：job 成功 → `SetStatus(id,"ready","")`；失败 → `SetStatus(id,"failed", err.Error())`

- [ ] **Step 1: 写失败测试（fake Runner）**

```go
package convert

import (
	"context"
	"errors"
	"testing"
	"time"

	"ifcviewer/server/internal/store"
)

type fakeRunner struct{ fail bool }

func (f fakeRunner) Run(ctx context.Context, in, out string) error {
	if f.fail {
		return errors.New("boom: node exited 1")
	}
	return nil
}

func waitStatus(t *testing.T, st *store.Store, id, want string) {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		m, err := st.Get(id)
		if err == nil && m.Status == want {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	m, _ := st.Get(id)
	t.Fatalf("status never became %q (now %q)", want, m.Status)
}

func TestQueueSuccessAndFailure(t *testing.T) {
	st := store.NewStore(t.TempDir())
	ok, _ := st.Create("ok.ifc", 1, strings.NewReader("x"))
	bad, _ := st.Create("bad.ifc", 1, strings.NewReader("x"))

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	q := NewQueue(st, fakeRunner{}, 2)
	q.Start(ctx)
	if !q.Enqueue(ok.ID) {
		t.Fatal("enqueue ok failed")
	}
	if q.Enqueue(ok.ID) {
		t.Fatal("duplicate enqueue should return false")
	}
	waitStatus(t, st, ok.ID, "ready")

	q2 := NewQueue(st, fakeRunner{fail: true}, 1)
	q2.Start(ctx)
	q2.Enqueue(bad.ID)
	waitStatus(t, st, bad.ID, "failed")
	m, _ := st.Get(bad.ID)
	if m.Error == "" {
		t.Fatal("expected error message recorded")
	}
}
```

（`strings` import 需补上。）

- [ ] **Step 2: 运行测试确认失败**

Run: `cd viewer/server && go test ./internal/convert/`
Expected: FAIL（编译错误）

- [ ] **Step 3: 实现 queue.go**

```go
package convert

import (
	"context"
	"fmt"
	"os/exec"
	"sync"

	"ifcviewer/server/internal/store"
)

type Runner interface {
	Run(ctx context.Context, inputPath, outDir string) error
}

type ExecRunner struct {
	NodeBin string
	Script  string
}

func (r ExecRunner) Run(ctx context.Context, inputPath, outDir string) error {
	cmd := exec.CommandContext(ctx, r.NodeBin, r.Script, inputPath, outDir)
	var stderr cappedBuffer
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("convert2xkt failed: %v: %s", err, stderr.String())
	}
	return nil
}

// cappedBuffer 只保留末尾 500 字节，避免错误信息撑爆 model.json
type cappedBuffer struct{ buf []byte }

func (c *cappedBuffer) Write(p []byte) (int, error) {
	c.buf = append(c.buf, p...)
	if len(c.buf) > 500 {
		c.buf = c.buf[len(c.buf)-500:]
	}
	return len(p), nil
}

func (c *cappedBuffer) String() string { return string(c.buf) }

type Queue struct {
	st      *store.Store
	runner  Runner
	jobs    chan string
	mu      sync.Mutex
	pending map[string]bool
}

func NewQueue(st *store.Store, r Runner, workers int) *Queue {
	q := &Queue{st: st, runner: r, jobs: make(chan string, 64), pending: map[string]bool{}}
	for i := 0; i < workers; i++ {
		go q.work()
	}
	return q
}

func (q *Queue) Start(ctx context.Context) {
	go func() {
		<-ctx.Done()
		close(q.jobs)
	}()
}

func (q *Queue) Enqueue(id string) bool {
	q.mu.Lock()
	defer q.mu.Unlock()
	if q.pending[id] {
		return false
	}
	q.pending[id] = true
	q.jobs <- id
	return true
}

func (q *Queue) work() {
	for id := range q.jobs {
		func() {
			defer func() {
				q.mu.Lock()
				delete(q.pending, id)
				q.mu.Unlock()
			}()
			ctx := context.Background()
			if err := q.runner.Run(ctx, q.st.IFCPath(id), q.st.ModelDir(id)); err != nil {
				_ = q.st.SetStatus(id, "failed", err.Error())
			} else {
				_ = q.st.SetStatus(id, "ready", "")
			}
		}()
	}
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd viewer/server && go test ./internal/convert/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd <repo>
git add viewer/server
git commit -m "feat(viewer): add conversion queue with worker pool and exec runner"
```

---

### Task 4: server — HTTP API + 静态服务 + main

**Files:**
- Create: `viewer/server/internal/api/api.go`
- Create: `viewer/server/internal/api/api_test.go`
- Create: `viewer/server/cmd/server/main.go`
- Create: `viewer/server/server_config.json`

**Interfaces:**
- Consumes: Task 2 `store.Store`；Task 3 `convert.Queue` / `convert.ExecRunner`
- Produces: `func NewHandler(st *store.Store, q *convert.Queue, maxUploadBytes int64) http.Handler`；路由（api.md §1-2）：
  - `POST /api/models`、`GET /api/models`、`GET /api/models/{id}`、`POST /api/models/{id}/retry`、`DELETE /api/models/{id}`、`GET /api/models/{id}/download`
  - `GET /models/{id}/model.xkt`、`GET /models/{id}/metadata.json`（http.ServeFile，自带 Range）
- config JSON：`{"port": 8090, "dataDir": "../data", "nodeBin": "node", "converterScript": "../converter/convert.js", "maxUploadMB": 200}`

- [ ] **Step 1: 写失败测试（httptest 全流程）**

`internal/api/api_test.go`（queue 用立即成功的 fake runner，直接复用 Task 3 的 Queue + 内联 fake）：

```go
package api

import (
	"context"
	"encoding/json"
	"io"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/store"
)

type okRunner struct{}

func (okRunner) Run(ctx context.Context, in, out string) error { return nil }

type env struct {
	Code     int             `json:"code"`
	Message  string          `json:"message"`
	Data     json.RawMessage `json:"data"`
}

func setup(t *testing.T) (*httptest.Server, *store.Store) {
	t.Helper()
	st := store.NewStore(t.TempDir())
	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	q := convert.NewQueue(st, okRunner{}, 1)
	q.Start(ctx)
	srv := httptest.NewServer(NewHandler(st, q, 1<<20)) // 测试上限 1MB
	t.Cleanup(srv.Close)
	return srv, st
}

func upload(t *testing.T, url, filename, content string) *httptest.ResponseRecorder {
	t.Helper()
	var body strings.Builder
	w := multipart.NewWriter(&body)
	fw, _ := w.CreateFormFile("file", filename)
	fw.Write([]byte(content))
	w.Close()
	req, _ := http.NewRequest("POST", url+"/api/models", strings.NewReader(body.String()))
	req.Header.Set("Content-Type", w.FormDataContentType())
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	rec := httptest.NewRecorder()
	rec.Code = resp.StatusCode
	rec.Body.Write(b)
	return rec
}

func TestUploadListDownloadDelete(t *testing.T) {
	srv, st := setup(t)

	// 非法扩展名
	rec := upload(t, srv.URL, "a.txt", "x")
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("ext check: %d %s", rec.Code, rec.Body.String())
	}
	// 超限（上限 1MB）
	rec = upload(t, srv.URL, "big.ifc", strings.Repeat("x", 1<<20+1))
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("size check: %d", rec.Code)
	}
	// 正常上传
	rec = upload(t, srv.URL, "ok.ifc", "ISO-10303-21;fake")
	if rec.Code != http.StatusOK {
		t.Fatalf("upload: %d %s", rec.Code, rec.Body.String())
	}
	var e env
	json.Unmarshal(rec.Body.Bytes(), &e)
	if e.Code != 0 {
		t.Fatalf("envelope: %+v", e)
	}
	var created store.Model
	json.Unmarshal(e.Data, &created)
	if created.Status != "converting" && created.Status != "ready" {
		t.Fatalf("status: %q", created.Status)
	}
	// 等待转换完成（fake runner 立即成功）
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		m, _ := st.Get(created.ID)
		if m.Status == "ready" {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	// 列表
	resp, _ := http.Get(srv.URL + "/api/models")
	body, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	var le env
	json.Unmarshal(body, &le)
	var list []store.Model
	json.Unmarshal(le.Data, &list)
	if len(list) != 1 {
		t.Fatalf("list: %d", len(list))
	}
	// 下载原始 IFC
	resp, _ = http.Get(srv.URL + "/api/models/" + created.ID + "/download")
	b, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	if !strings.Contains(resp.Header.Get("Content-Disposition"), "ok.ifc") || string(b) != "ISO-10303-21;fake" {
		t.Fatalf("download: %v %q", resp.Header, b)
	}
	// 静态 xkt（文件不存在 → 404）
	resp, _ = http.Get(srv.URL + "/models/" + created.ID + "/model.xkt")
	resp.Body.Close()
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("static: %d", resp.StatusCode)
	}
	// 删除
	req, _ := http.NewRequest("DELETE", srv.URL+"/api/models/"+created.ID, nil)
	resp, _ = http.DefaultClient.Do(req)
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("delete: %d", resp.StatusCode)
	}
	if _, err := st.Get(created.ID); err != store.ErrNotFound {
		t.Fatalf("after delete: %v", err)
	}
	// 未知 id → 404
	resp, _ = http.Get(srv.URL + "/api/models/m_deadbeefdeadbeef")
	resp.Body.Close()
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("404: %d", resp.StatusCode)
	}
}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd viewer/server && go test ./internal/api/`
Expected: FAIL（编译错误）

- [ ] **Step 3: 实现 api.go**

要点：`http.ServeMux`（Go 1.22 方法路由）、`http.MaxBytesReader`、信封 `writeJSON(w, code, data)` / `writeErr(w, httpStatus, code, msg)`、全局限定错误码 `40001` 非法类型 / `40002` 超限 / `40400` 不存在 / `50000` 内部错误、静态目录挂在 mux 的 `GET /models/{id}/model.xkt` 与 `GET /models/{id}/metadata.json` 上用 `http.ServeFile`、download 用 `Content-Disposition: attachment; filename*=UTF-8''<url-escaped name>`、简单 CORS 中间件（`Access-Control-Allow-Origin: *`，OPTIONS 直接 204）。

骨架：

```go
func NewHandler(st *store.Store, q *convert.Queue, maxUploadBytes int64) http.Handler {
	h := &handler{st: st, q: q, maxUpload: maxUploadBytes}
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/models", h.upload)
	mux.HandleFunc("GET /api/models", h.list)
	mux.HandleFunc("GET /api/models/{id}", h.get)
	mux.HandleFunc("POST /api/models/{id}/retry", h.retry)
	mux.HandleFunc("DELETE /api/models/{id}", h.delete)
	mux.HandleFunc("GET /api/models/{id}/download", h.download)
	mux.HandleFunc("GET /models/{id}/model.xkt", h.serveModelFile("model.xkt"))
	mux.HandleFunc("GET /models/{id}/metadata.json", h.serveModelFile("metadata.json"))
	return cors(mux)
}
```

`upload`：`r.Body = http.MaxBytesReader(w, r.Body, h.maxUpload)` → `ParseMultipartForm` → 取 `file` → 后缀 `.ifc`（`strings.EqualFold(filepath.Ext(name), ".ifc")`）→ `st.Create(name, size, file)` → `q.Enqueue(m.ID)` → 返回创建对象。`retry`：仅 `failed` 可重试，置 `converting` 后 Enqueue。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd viewer/server && go test ./... -v`
Expected: 全部 PASS

- [ ] **Step 5: 实现 main.go + 配置**

`cmd/server/main.go`：读 `server_config.json`（相对可执行文件工作目录，支持 `-config` flag 覆盖）→ `NewStore` → `Recover()` → `ExecRunner` → `NewQueue(st, runner, 2)` → `Start` → `http.ListenAndServe(fmt.Sprintf(":%d", cfg.Port), handler)`，并在启动时打印数据目录与端口。`server_config.json` 内容按 Interfaces 中的示例。

- [ ] **Step 6: 端到端手工验证（真转换）**

Run:
```bash
cd viewer/server && go build -o /tmp/opencode/ifcserver ./cmd/server
cd <repo>/viewer/server && /tmp/opencode/ifcserver &
curl -F "file=@../converter/test/fixtures/wall-with-opening-and-window.ifc" http://localhost:8090/api/models
sleep 3 && curl http://localhost:8090/api/models
```
Expected: 状态从 `converting` 变为 `ready`；`curl -I http://localhost:8090/models/{id}/model.xkt` 返回 200。（验证后 kill 进程）

- [ ] **Step 7: Commit**

```bash
cd <repo>
git add viewer/server
git commit -m "feat(viewer): add HTTP API, static serving, download and server entrypoint"
```

---

### Task 5: web — 脚手架 + API client + 模型库页 LibraryPage

**Files:**
- Create: `viewer/web/`（Vite react-ts 脚手架）
- Create: `viewer/web/src/api/client.ts`
- Create: `viewer/web/src/api/types.ts`
- Create: `viewer/web/src/api/client.test.ts`
- Create: `viewer/web/src/pages/LibraryPage.tsx`
- Create: `viewer/web/src/App.tsx`、`viewer/web/src/main.tsx`、`viewer/web/vite.config.ts`（改 proxy）

**Interfaces:**
- Produces（被 Task 6-8 消费）:
  - `types.ts`: `interface ModelInfo { id: string; name: string; size: number; status: "converting"|"ready"|"failed"; createdAt: string; error: string }`
  - `client.ts`: `listModels(): Promise<ModelInfo[]>`、`uploadModel(file: File): Promise<ModelInfo>`、`deleteModel(id: string): Promise<void>`、`retryModel(id: string): Promise<ModelInfo>`、`downloadUrl(id: string): string`（返回 `/api/models/${id}/download`）、`modelAssetUrl(id: string, file: "model.xkt"|"metadata.json"): string`
  - 路由：`/` → LibraryPage，`/view/:id` → ViewerPage（Task 6 占位）

- [ ] **Step 1: 脚手架与依赖**

```bash
cd <repo>/viewer
npm create vite@latest web -- --template react-ts
cd web
npm install
npm install @xeokit/xeokit-sdk react-router-dom zustand
npm install -D vitest @testing-library/react jsdom
```

`vite.config.ts` 增加：

```ts
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": "/src" } },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8090",
      "/models": "http://localhost:8090",
    },
  },
  test: { environment: "jsdom" },
});
```

`package.json` scripts 加 `"test": "vitest run"`；`tsconfig` paths 配 `@/*`。

- [ ] **Step 2: 写 client 失败测试**

`src/api/client.test.ts`（vitest + 全局 fetch stub）：

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { listModels, uploadModel, deleteModel, downloadUrl } from "./client";

const envelope = (data: unknown) => ({ code: 0, message: "ok", data });

beforeEach(() => vi.restoreAllMocks());

describe("api client", () => {
  it("listModels unwraps envelope", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(envelope([{ id: "m_1" }])), { status: 200 })));
    const models = await listModels();
    expect(models).toEqual([{ id: "m_1" }]);
  });
  it("throws on non-zero code", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ code: 40001, message: "bad type", data: null }), { status: 400 })));
    await expect(listModels()).rejects.toThrow("bad type");
  });
  it("uploadModel posts multipart FormData", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope({ id: "m_2" })), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const file = new File(["x"], "a.ifc");
    await uploadModel(file);
    const [url, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/models");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
  });
  it("downloadUrl format", () => {
    expect(downloadUrl("m_abc")).toBe("/api/models/m_abc/download");
  });
  it("deleteModel uses DELETE", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope(null)), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    await deleteModel("m_1");
    expect((spy.mock.calls[0] as unknown as [string, RequestInit])[1].method).toBe("DELETE");
  });
});
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd viewer/web && npm test`
Expected: FAIL（client 未实现）

- [ ] **Step 4: 实现 types.ts + client.ts**

```ts
// types.ts
export interface ModelInfo {
  id: string;
  name: string;
  size: number;
  status: "converting" | "ready" | "failed";
  createdAt: string;
  error: string;
}
```

```ts
// client.ts
import type { ModelInfo } from "./types";

interface Envelope<T> { code: number; message: string; data: T }

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, init);
  const env: Envelope<T> = await resp.json();
  if (!resp.ok || env.code !== 0) throw new Error(env.message || `HTTP ${resp.status}`);
  return env.data;
}

export function listModels() { return request<ModelInfo[]>("/api/models"); }
export function uploadModel(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  return request<ModelInfo>("/api/models", { method: "POST", body: fd });
}
export function retryModel(id: string) { return request<ModelInfo>(`/api/models/${id}/retry`, { method: "POST" }); }
export function deleteModel(id: string) { return request<null>(`/api/models/${id}`, { method: "DELETE" }); }
export const downloadUrl = (id: string) => `/api/models/${id}/download`;
export const modelAssetUrl = (id: string, file: "model.xkt" | "metadata.json") => `/models/${id}/${file}`;
```

- [ ] **Step 5: 运行测试确认通过后实现 LibraryPage**

功能：文件选择 + 拖拽上传（前端校验 `.ifc` 与 ≤200MB）、表格列（名称/大小/状态/时间/操作）、`converting` 存在时每 2s 轮询 `listModels`、操作列按状态渲染（ready: 查看/下载/删除；failed: 错误 tooltip/重试/删除）。路由 `App.tsx`：

```tsx
<BrowserRouter>
  <Routes>
    <Route path="/" element={<LibraryPage />} />
    <Route path="/view/:id" element={<ViewerPage />} />
  </Routes>
</BrowserRouter>
```

（ViewerPage 先放占位 `export default function ViewerPage(){ return <div>viewer</div> }`，Task 6 替换。）

- [ ] **Step 6: 手工联调**

启动 Task 4 的服务器与 `npm run dev`，浏览器上传 fixture IFC，确认列表状态流转 ready、可下载、可删除。

- [ ] **Step 7: Commit**

```bash
cd <repo>
git add viewer/web
git commit -m "feat(viewer): add web scaffold, api client and model library page"
```

（`viewer/web/.gitignore` 含 `node_modules`、`dist`）

---

### Task 6: web — 查看器核心 ViewerContext + ViewerPage（加载 XKT + 拾取）

**Files:**
- Create: `viewer/web/src/viewer/ViewerContext.tsx`
- Create: `viewer/web/src/viewer/usePicking.ts`
- Create: `viewer/web/src/viewer/store.ts`
- Create: `viewer/web/src/pages/ViewerPage.tsx`

**Interfaces:**
- Consumes: Task 5 `modelAssetUrl`
- Produces（被 Task 7/8 消费）:
  - `store.ts`（zustand）: `{ selectedId: string|null; tool: "select"|"measure"; setSelected(id); setTool(t) }`
  - `ViewerContext`: `{ viewer: Viewer; sceneModel: Entity; metaModel: MetaModel } | null`（模型 loaded 后置非 null）；`useViewer()` hook
  - `usePicking()`：挂到 ViewerContext 内部，点击构件 → `setSelected(entityId)` + `lastSelected` 高亮（`viewer.scene.selectedObjectIds`），点空白取消选择

- [ ] **Step 1: 实现 store.ts 与 ViewerContext.tsx**

ViewerContext 要点：

```tsx
const viewer = new Viewer({ canvasId: "xeokit-canvas", transparent: true });
new NavCubePlugin(viewer, { canvasId: "navcube-canvas", visible: true });
const xktLoader = new XKTLoaderPlugin(viewer);
const sceneModel = xktLoader.load({
  id: "model",
  src: modelAssetUrl(id, "model.xkt"),
  metaModelSrc: modelAssetUrl(id, "metadata.json"),
  edges: true,
});
sceneModel.on("loaded", () => {
  viewer.cameraFlight.flyTo(sceneModel);
  setCtx({ viewer, sceneModel, metaModel: sceneModel.metaModel });
});
sceneModel.on("error", (e) => setError(String(e)));
```

卸载时 `viewer.destroy()`。布局：全屏 canvas + 右侧占位面板容器 + NavCube 小 canvas（绝对定位右下）。加载失败显示错误与返回链接。

- [ ] **Step 2: 实现 usePicking.ts**

```ts
viewer.cameraControl.on("picked", (e) => {
  const entity = e.entity; // Entity
  if (entity && entity.isObject) setSelected(entity.id);
});
viewer.cameraControl.on("pickedNothing", () => setSelected(null));
```

配合 `useEffect` 对 `selectedId` 做 `viewer.scene.selectedObjectIds = selectedId ? [selectedId] : []`（`viewer.scene.highlightedObjectIds` 同理用于 hover，可选）。

- [ ] **Step 3: ViewerPage 组装 + 手工验证**

`ViewerPage`：`const { id } = useParams()` → `<ViewerProvider modelId={id}>` 包裹 canvas 与占位侧栏。启动后端（数据目录里已有 ready 模型）+ dev server，打开 `/view/<id>`，确认模型渲染、可旋转缩放、点击构件有选中高亮（DevTools 无报错）。

- [ ] **Step 4: Commit**

```bash
cd <repo>
git add viewer/web
git commit -m "feat(viewer): add xeokit viewer core with xkt loading and picking"
```

---

### Task 7: web — 构件树 ModelTreePanel + 属性面板 PropertyPanel

**Files:**
- Create: `viewer/web/src/viewer/ModelTreePanel.tsx`
- Create: `viewer/web/src/viewer/PropertyPanel.tsx`
- Modify: `viewer/web/src/pages/ViewerPage.tsx`

**Interfaces:**
- Consumes: Task 6 `useViewer()`、`store.selectedId`
- Produces: `<ModelTreePanel/>`（TreeViewPlugin，containment 层级，checkbox 控制显隐，节点点击 → setSelected + cameraFlight.flyTo）；`<PropertyPanel/>`（展示 `metaScene.metaObjects[selectedId]` 的 name/type/propertySets）

- [ ] **Step 1: 实现 ModelTreePanel.tsx**

```tsx
const { viewer, sceneModel } = useViewer()!;
useEffect(() => {
  const treeView = new TreeViewPlugin(viewer, {
    containerElement: ref.current!,
    hierarchy: "containment",
    autoExpandDepth: 1,
  });
  const onTitle = treeView.on("nodeTitleClicked", (e) => {
    setSelected(e.treeViewNode.objectId);
    viewer.cameraFlight.flyTo(e.treeViewNode.objectId);
  });
  return () => { treeView.unSubscribe(onTitle); treeView.destroy(); };
}, [viewer, sceneModel]);
```

TreeViewPlugin 自带 checkbox → 显隐联动；容器为左栏 `<div ref={ref} className="tree-panel"/>`，需引入 xeokit 自带样式（`@xeokit/xeokit-sdk` 无 css 导出，按 xeokit 示例内置必要的 `.xeokit-tree-view` 样式到 `src/viewer/tree.css`）。

- [ ] **Step 2: 实现 PropertyPanel.tsx**

```tsx
const { metaModel } = useViewer()!;
const selectedId = useViewerStore((s) => s.selectedId);
const mo = selectedId ? metaModel.metaObjects[selectedId] : null;
// 渲染 mo.name / mo.type / mo.propertySets: [{name, properties:[{name,value}]}] 表格
```

空态显示「点击构件查看属性」。

- [ ] **Step 3: ViewerPage 接入两栏布局并手工验证**

确认：树展开/勾选显隐正确；点击树节点相机飞行 + 选中；点击构件右侧属性面板显示 pset；无 pset 构件不报错。

- [ ] **Step 4: Commit**

```bash
cd <repo>
git add viewer/web
git commit -m "feat(viewer): add model tree panel and property panel"
```

---

### Task 8: web — Toolbar + 剖切 SectionControl + 测量

**Files:**
- Create: `viewer/web/src/viewer/Toolbar.tsx`
- Create: `viewer/web/src/viewer/SectionControl.tsx`
- Create: `viewer/web/src/viewer/useMeasurements.ts`
- Modify: `viewer/web/src/pages/ViewerPage.tsx`

**Interfaces:**
- Consumes: Task 6 `useViewer()`、store 的 `tool`；Task 5 `downloadUrl`
- Produces:
  - `<Toolbar/>`：复位视角（`cameraFlight.flyTo(sceneModel)`）、剖切开关、测量开关（`setTool("select"|"measure")`）、清除测量、下载 IFC（`<a href={downloadUrl(id)}>`）
  - `<SectionControl enabled/>`：SectionPlanesPlugin 单剖切面，轴向选择（X/Y/Z）+ range 滑杆（范围取 `scene.aabb` 对应轴的 min..max）拖动 `sectionPlane.pos`
  - `useMeasurements()`：DistanceMeasurementsPlugin + DistanceMeasurementsMouseControl，`tool==="measure"` 时 `control.activate()` 否则 `deactivate()`；`clear()` 销毁全部测量

- [ ] **Step 1: 实现 useMeasurements.ts**

```ts
export function useMeasurements() {
  const { viewer } = useViewer()!;
  const tool = useViewerStore((s) => s.tool);
  const refs = useRef<{ plugin: DistanceMeasurementsPlugin; control: DistanceMeasurementsMouseControl } | null>(null);
  useEffect(() => {
    const plugin = new DistanceMeasurementsPlugin(viewer, {});
    const control = new DistanceMeasurementsMouseControl(plugin, { snapping: true });
    refs.current = { plugin, control };
    return () => { control.destroy(); plugin.destroy(); };
  }, [viewer]);
  useEffect(() => {
    const c = refs.current?.control;
    if (!c) return;
    if (tool === "measure") c.activate(); else c.deactivate();
  }, [tool]);
  const clear = useCallback(() => refs.current?.plugin.clear(), []);
  return { clear };
}
```

测量开启时 cameraControl 仍在工作（左键点两点出测量，双击结束），切回 select 自动停用。

- [ ] **Step 2: 实现 SectionControl.tsx**

```ts
const sectionPlanes = new SectionPlanesPlugin(viewer, {});
const aabb = viewer.scene.aabb;
// axis ∈ "x"|"y"|"z"；pos 初始为中点；滑杆 onChange 设置 sectionPlane.pos = [x,y,z]（对应轴取滑值，其余取中心）
// 关闭时 sectionPlane.destroy()；开启时创建 new SectionPlane({pos, dir: axis==='x'?[-1,0,0]:...})
```

- [ ] **Step 3: Toolbar + ViewerPage 集成，手工验证**

验证清单：复位视角有效；剖切三轴滑动正常且关闭后模型完整；测量模式可打两点显示距离、清除后消失；下载按钮得到原 IFC 文件。

- [ ] **Step 4: Commit**

```bash
cd <repo>
git add viewer/web
git commit -m "feat(viewer): add toolbar, section plane control and distance measurements"
```

---

### Task 9: 冒烟脚本 + README + 最终验证

**Files:**
- Create: `viewer/scripts/smoke.sh`
- Create: `viewer/README.md`

- [ ] **Step 1: 写 smoke.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail
# 前提：server 已在 :8090 运行
BASE=http://localhost:8090
FIXTURE="$(dirname "$0")/../converter/test/fixtures/wall-with-opening-and-window.ifc"
ID=$(curl -sf -F "file=@${FIXTURE}" "$BASE/api/models" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["id"])')
echo "uploaded: $ID"
for i in $(seq 1 30); do
  STATUS=$(curl -sf "$BASE/api/models/$ID" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["status"])')
  [ "$STATUS" = "ready" ] && break
  [ "$STATUS" = "failed" ] && { echo "conversion failed"; exit 1; }
  sleep 2
done
[ "$STATUS" = "ready" ] || { echo "timeout"; exit 1; }
curl -sf -o /dev/null -w "xkt: %{http_code} %{size_download}B\n" "$BASE/models/$ID/model.xkt"
curl -sf -o /dev/null -w "meta: %{http_code} %{size_download}B\n" "$BASE/models/$ID/metadata.json"
curl -sf -o /dev/null -w "download: %{http_code}\n" "$BASE/api/models/$ID/download"
curl -sf -X DELETE "$BASE/api/models/$ID" > /dev/null
echo "smoke OK"
```

`chmod +x viewer/scripts/smoke.sh`。

- [ ] **Step 2: 写 README.md**

内容：架构图（引用 docs/design.md）、三模块启动方式（converter 无需启动；`cd server && go run ./cmd/server`；`cd web && npm install && npm run dev`）、依赖版本（Node≥18、Go≥1.22）、冒烟测试方法、目录说明。

- [ ] **Step 3: 全量最终验证**

```bash
cd viewer/converter && npm test
cd ../server && go test ./...
cd ../web && npm test && npm run build
# 起服务器后
../scripts/smoke.sh
```

Expected: 全部通过；`npm run build` 无 TS 错误。

- [ ] **Step 4: Commit**

```bash
cd <repo>
git add viewer/scripts viewer/README.md viewer/docs
git commit -m "feat(viewer): add smoke script, README and design/api docs"
```
