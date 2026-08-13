# Chunk C 服务端：render.json + Go kind 分流 + cad 代理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox syntax.

**Goal:** services/cad 产实体带 key 的 render.json（schemaVersion 2）；Go 网关引入 model kind（ifc/dxf）与 :8200 代理；为 web 查看器备好数据源。

**Architecture:** render 由 services/cad 在 run/save 时随产物原子发布（`models/{id}/render.json`），GET 直读缓存；Go 侧 `store.Model` 加 `Kind`，上传按扩展名分流，dxf 不进 converter，script 代理按 kind 选 client。

**Tech Stack:** Python/FastAPI/ezdxf（services/cad）、Go stdlib（server）。

## Global Constraints

- 分支 `feat/v0.7-cad-render`（自 main 新建）；commit 中文前缀式；TDD；测试 ≥1:1。
- Go 侧：校验归 domain validate + 哨兵错误，handler 只 decode→调用→errors.Is 翻译；envelope 契约测试必配（新增端点）。
- Python 侧：verify 隔离 ALLOWLIST 保持空。
- 携带终审遗留：未知类型 keyed 实体的 layer/color/linetype 三字段——本 chunk 在 dxf_diffing 签名与 render payload 一并补上（原 deferred #1 清偿）。
- 兼容性：`model.json` 无 kind 字段的旧记录默认 `ifc`（迁移测试）；上传仍拒绝非 .ifc/.dxf。
- VitePress 文档本 chunk 不写（用户裁决：开发完统一补）；README/AGENTS 照常同步。

---

### Task 1: 立项 W-0039/W-0040 + PLAN 行

- [ ] W-0039「cad render.json（payload v2）」：验收——`GET /models/{id}/render.json` 实体带 XDATA key；LINE/LWPOLYLINE(bulge→arc)/CIRCLE/ARC/TEXT/MTEXT/INSERT 覆盖；unsupported 明面化；run/save 后原子更新；契约测试。
- [ ] W-0040「Go kind 分流 + cad 代理」：验收——Model.Kind + 旧记录迁移默认 ifc；.dxf 上传走 cad（不进 converter）；/api/v1 下 cad script 13 端点代理（fast/slow 双 client、envelope 契约测试）；render.json 只读端点 + auth 豁免白名单更新。
- [ ] PLAN v0.6 加 chunk C 行。
- [ ] Commit `docs(work): W-0039/W-0040 立项 + PLAN chunk C 行`

---

### Task 2: services/cad render.json（TDD）

**Files:**
- Create: `services/cad/app/render.py`
- Modify: `services/cad/app/routes_scripts.py`（run/save 后发布 render.json）、新增 `GET /models/{id}/render.json` 端点（放 routes_scripts 或新 routes_render.py——看行数，超 ~600 行就新文件）、`main.py` 挂路由
- Test: `services/cad/tests/test_render.py`

**Interfaces（Produces——web 查看器与 Go 依赖）:**

```python
def build_render_payload(dxf_path: str) -> dict
# {"schemaVersion": 2, "bounds": {...}, "layers": [...],
#  "entities": [{"key": str|None, "type": "LINE"|..., "layer": str, "color": int, "linetype": str, ...geometry}],
#  "unsupported": [{"type", "handle", "coords"}]}
```

- [ ] **Step 1: 失败测试**
  - 七类实体渲染：key/type/layer/几何字段（LINE start/end；LWPOLYLINE 炸开为 line/arc 段含 bulge→arc 转换——参考 `skills/aidxfv/v1/scripts/dxf/render_payload.py:132-161` 的 bulge 算法；CIRCLE/ARC center/radius/角度；TEXT/MTEXT text/insert；INSERT name/insert + 块内实体展开一层）
  - 未知类型进 `unsupported`（type/handle/coords），不静默丢
  - 坐标：保留原始 DXF 坐标（不做 screen 归一化——v1 的归一化是 CLI 预览遗留，v2 交给前端变换），数字 round 6
  - key 与 current.map.json 一致性契约测试（render 实体的 key 集合 == map 的 key 集合）
  - 端点：200/404（无模型/无 render.json 且无法生成）
  - run/save 后 render.json 更新（与 uploads dxf 同内容代）
- [ ] **Step 2: 实现 render.py + 端点 + run/save 钩子**（发布走 tmp+os.replace；生成失败不阻断 run/save 主流程但删旧 render.json 防错位——与 map 侧车同纪律）
- [ ] **Step 3: 顺带清偿 deferred #1**：dxf_diffing 未知类型 keyed 实体补 layer/color/linetype 三字段签名 + 回归测试
- [ ] **Step 4: 全量绿 + Commit** `feat(services/cad): render.json payload v2——实体带 key + unsupported 明面化（W-0039）`

---

### Task 3: Go kind 分流 + cad 代理（TDD）

**Files:**
- Modify: `server/internal/store/store.go`（Model.Kind、`SourcePath(id)` 替 IFCPath 或并存按 kind 分派）、`server/internal/api/api.go`（上传分流、download 按 kind、路由注册）、`server/internal/api/script.go`（代理按 kind 选 client）、`server/cmd/server/main.go`（VIEWER_CAD_SERVICE_URL 装配）
- Create: `server/internal/api/script_cad.go`（cad 代理路由，镜像 script.go）、render.json 只读端点
- Test: 对应 *_test.go + envelope 契约测试 + auth 白名单守卫更新

**Interfaces:**
- Consumes: services/cad 全部 13+1 端点（chunk A/B 已交付）
- Produces: `VIEWER_CAD_SERVICE_URL`（默认 http://127.0.0.1:8200）；`store.Model.Kind`（"ifc"|"dxf"，缺省迁移为 ifc）；`/api/v1/models/{id}/render.json`（GET 只读，auth 豁免白名单加入）

- [ ] **Step 1: 失败测试**——store kind 迁移（无 kind 的 model.json → Get 后 Kind=="ifc"）；上传 .dxf → kind=dxf 且状态直接 ready（不进 converter 队列）；.ifc 行为不变回归；cad 代理端点 envelope（mock :8200）；dxf 模型 run/save 代理成功**不触发** EnqueueIfStale（XKT 重转仅 ifc kind）；render.json 豁免白名单守卫。
- [ ] **Step 2: 实现**——store.Kind + validate；upload 分流（扩展名白名单 .ifc/.dxf，其它 40001）；queue 对 dxf kind 短路；script 代理入口 `h.st.Get(id)` 按 kind 选 client（ifc→editsvc :8100，dxf→cadsvc :8200），cad 代理 13 端点镜像（含 fast/slow、writeEditErr 同映射）；render.json 只读端点 serveModelFile 模式 + auth.go 白名单 + 守卫测试更新。
- [ ] **Step 3: `go test ./... && go vet ./...` 全绿 + Commit** `feat(server): model kind 分流 + services/cad 代理（W-0040）`

---

### Task 4: 收口

- [ ] AGENTS.md（组件表 cad 行端点数、server 行测试数同步；架构图/组件描述加 cad 代理一句）；services/cad README 端点表补 render.json；W-0039/W-0040 置 done；PLAN chunk C 行 ✅
- [ ] 全量验证：server go test+vet、services/cad pytest、web 不受影响（不动 web）
- [ ] Commit `docs: chunk C 服务端收口`

---

## Self-Review 记录

- 覆盖：spec §二.1（render payload v2）→Task 2；§二.3（kind 分流）+ §1.3（Go 代理）→Task 3；deferred #1 清偿→Task 2 Step 3。
- 类型一致：render payload schema 在 Task 2 定义、Task 3 Go 端点透传不解析；Kind 值域 "ifc"|"dxf" 全计划统一。
- 风险：INSERT 块展开深度（定一层，防递归）；bulge→arc 算法移植需对拍 v1 实现；dxf kind 的 retry/状态机分支（upload 直接 ready，无 converting 态）。
