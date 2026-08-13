# W-0037: ifc diff 结果缓存发布共享 tmp 名竞态（并发同 (base,target) → 500）

- **状态：** done（关闭于「本迭代分支 feat/v0.6-cad-diff（PR 待提）」）

## 关闭结论（2026-08-13）

镜像 W-0036 修复：`services/ifc/app/routes_diff.py` 缓存发布 tmp 名按
pid+线程 id 唯一化。barrier 回归用例修复前必红（FileNotFoundError at
`os.replace(tmp, cache_path)`），修复后全量 243 绿（242 基线 + 1 新增）、
压力复跑 20/20 绿。证据见
`.superpowers/sdd/2026-08-13-services-cad-chunk-b/w0037-report.md`。
- **优先级：** P1
- **Milestone：** v0.6（services/cad script-as-source；镜像 ifc 侧修复）
- **来源：** chunk B W-0036 修复评审 out-of-scope 发现（2026-08-13，分支 feat/v0.6-cad-diff）
- **执行者/分支：** opencode / feat/v0.6-cad-diff

## 背景

W-0036 在 services/cad 修复了同型 bug：`routes_diff.post_diff` 的 diff 结果缓存
发布段在模型锁外，同 `(base,target)` 并发请求双双未命中缓存时共享
`diff-{base}-{target}.json.tmp` 名，一方 `os.replace` 把 tmp 改名后另一方的
`os.replace` 必抛 FileNotFoundError → 500。services/ifc 与 cad 同构，
`services/ifc/app/routes_diff.py:139-143` 存在完全相同的问题，按评审结论
镜像修复。

## 涉及位置

- `services/ifc/app/routes_diff.py:139-143`（缓存发布段，共享 tmp 名）
- `services/ifc/tests/test_diff.py`（回归用例落点）
- 参考修复：commit 0f12428（`services/cad/app/routes_diff.py` +
  `services/cad/tests/test_diff.py` barrier 回归用例）

## 方案

镜像 cad 修复（最小 diff）：

1. **TDD 回归测试**：把 cad 侧 barrier 用例
   `test_concurrent_same_pair_diff_cache_publish_no_500` 移植到 ifc 侧
   （适配 fixture/helper 名），dump barrier 确定性排出写-写交错，修复前必红。
2. **修复**：tmp 名按写者唯一化
   `f"{cache_path}.{os.getpid()}.{threading.get_ident()}.tmp"`，唯一 tmp +
   `os.replace` 保持发布原子性（后者覆盖前者，两次发布同 payload 等价）。

## 验收标准

- 回归用例修复前红、修复后绿；全量测试绿（242 基线 + 新增）。
- 回归用例压力复跑 20 次全绿。
- 无残留 tmp 文件，缓存 payload 完整可读。

## 测试要求

- 修复必须配竞态回归用例（TDD：先红后绿）。
- 新增测试量 ≥ 新增实现量（仓内 ≥1:1 硬规则）。
