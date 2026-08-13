# W-0036: cad materialize/LRU 低频竞态 flake（test_concurrent_diffs_across_lru_eviction_no_500）

- **状态：** done（关闭于「本迭代分支 feat/v0.6-cad-diff（PR 待提）」，commit 0f12428）
- **优先级：** P2
- **Milestone：** v0.6（services/cad script-as-source）
- **来源：** chunk B Task 4 评审（2026-08-13，分支 feat/v0.6-cad-diff）
- **执行者/分支：** opencode subagent / feat/v0.6-cad-diff

## 关闭结论（2026-08-13）

根因非 evict-vs-read：`routes_diff.post_diff` 的结果缓存发布段在模型锁外，
同 `(base,target)` 并发请求双双未命中缓存时共享 `diff-*.json.tmp` 名，一方
`os.replace` 后另一方必抛 FileNotFoundError → 500（flaky 用例 `[1..5]*2` 的
重复 base 对命中该窗口）。修复：tmp 名按 pid+线程 id 唯一化。证据与 5× 全绿
证明见 `.superpowers/sdd/2026-08-13-services-cad-chunk-b/w0036-report.md`。

## 背景

`services/cad/tests/test_dxf_lazy_materialize.py::test_concurrent_diffs_across_lru_eviction_no_500` 在 chunk B 全量跑（185 测试）中低频失败一次；单跑/复跑均绿。评审认定为 materialize/LRU 路径的真实低频竞态窗口（可能 evict-vs-read：LRU 逐出与 in-flight 物化/读取交错），非测试本身问题。当前无法稳定复现，先立项跟踪。

> 2026-08-13 收口复跑第二次复现：全量跑 1 failed/184 passed（失败详情未留存，印证「诊断增强」应最先落）；该用例单跑绿、全量复跑 185 全绿。

## 涉及位置

- `services/cad/app/dxf_materialize.py`（沙箱重建 + LRU 缓存）
- `services/cad/app/routes_diff.py`（diff worker 持锁逻辑）
- `services/cad/tests/test_dxf_lazy_materialize.py:228`（flaky 用例）

## 方案

三段推进：

1. **诊断增强**：该用例断言失败时 dump 状态码 + 响应体，便于下次失败时定位（先落这段，成本最低）。
2. **加压复现**：单测内循环 ~50 次跑同一并发场景，尝试稳定复现竞态窗口。
3. **加固**：确认 materialize/read/evict 三条路径同持 per-model 锁；或 LRU 逐出时跳过 in-flight 物化中的条目。

## 验收标准

- 用例在加压循环（~50 次）下全绿，或竞态根因修复后全量跑多次不再出现。
- 失败时断言输出含足够诊断信息（状态码 + 响应体）。

## 测试要求

- 诊断增强与加压循环本身即测试变更；加固需配竞态回归用例。
- 新增测试量 ≥ 新增实现量（仓内 ≥1:1 硬规则）。
