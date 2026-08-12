# W-0033: services/cad 骨架（staging/versions/run/save/rollback + 沙箱）

- **状态：** done（Task 3 地基 2382ad1：config/main/route_common/staging/versions/params/script_diff + 27 测试；Task 4 沙箱 + routes_scripts 0513084：95 测试全绿）
- **优先级：** P1
- **Milestone：** v0.6（services/cad script-as-source）
- **来源：** spec 2026-08-12-services-cad-script-as-source-design.md §1.2 + 「工作项建议」2
- **执行者/分支：** opencode / feat/v0.5-portability-reuse

## 背景

spec 决策 4 锁定两阶段实施：Phase 1 服务端闭环（services/cad 全套 API + 只读 Canvas 预览），先把 AI 闭环跑通。本项是 services/cad 骨架（chunk A 第二块）：FastAPI 服务（建议 :8200），与 services/ifc :8100 同构，镜像其文件布局、成对快照、沙箱与 REST 端点形状。**显式不含** locate/edit-call/语义 diff——那是 chunk B（spec「工作项建议」3、4），依赖本骨架先立。

## 涉及位置

- `services/cad/`（新增，FastAPI，端口建议 :8200）
- 依赖 W-0032 的 `cad_script_lib` / `validate_script_contract()`（经环境变量路径 import，同 `AIIFC_FLOWS_DIR` 机制）
- 参照：`services/ifc/app/`（routes_scripts.py、script_runner.py 等，可拷后改）

## 方案

1. **文件布局**（`VIEWER_DATA_DIR/models/{id}/` 下，镜像 IFC 侧）：`scripts/v{n}.py` + `v{n}.meta.json` + `v{n}.map.json`（全留）、`versions/v{n}.dxf`（只留最新，旧的裁剪）、`script_staging.json`（WPS 式 10 步环形暂存）、`current.map.json`。
2. **成对快照**：`scripts/v{n}.py` 与 `versions/v{n}.dxf` 同 n lockstep；回退 = 恢复脚本进暂存 + 重跑，永不逐步 revert。
3. **沙箱**：复用 services/ifc `script_runner.py` 模式——静态契约门（调 W-0032 的 `validate_script_contract()`）→ subprocess + 临时目录，bwrap 优先 / rlimit 兜底，killpg 超时，stderr 截尾 2KB → 422，tmp + `os.replace` 原子发布。
4. **REST 端点**（形状与 IFC 完全一致，本项范围）：
   - `GET/PUT /models/{id}/script`（读当前脚本 / 暂存编辑）
   - `GET .../script/params`（ast 提取 PARAMS，不执行）
   - `POST .../script/undo|redo|discard`（暂存链导航）
   - `POST .../script/run`（沙箱试跑 → 原子替换当前 DXF + 发布 map；不成版本）
   - `POST .../script/save`（跑 + 成对快照；失败 422 不留版本）
   - `GET .../scripts` · `POST .../script/rollback`（大版本列表 / 回退）
   - `GET .../script/staging/diff`（暂存步间 diff）
   - `GET .../versions`（版本列表）
5. **校验纪律**：业务校验住 `verify*`/`validate*`，handler 只做 decode→verify→调领域→翻译错误；配 `test_verify_isolation` 同款契约测试。

**显式范围外（chunk B）：** `script/locate`、`script/edit-call`（libcst 改写）、实体级语义 diff 引擎、Go 代理路由、render payload v2。（订正：脚本**文本** diff——`POST /script/diff` 大版本 diff 与 `GET /script/staging/diff`——属本项 chunk A，已交付；chunk B 不含的是实体级语义 diff。）

## 验收标准

- 上述端点齐：staging（undo/redo/discard）/ run / save / rollback / scripts / params / staging-diff / versions-list 全部可用，形状与 IFC 侧一致。
- 沙箱行为达标：bwrap 优先 / rlimit 兜底、killpg 超时、stderr 截尾 2KB → 422、tmp + `os.replace` 原子发布。
- verify 隔离契约测试（`test_verify_isolation` 同款）绿。
- `cd services/cad && uv run --group dev pytest` 全绿。
- 文档/注释明示本项不含 locate/edit-call/语义 diff（chunk B）。

## 测试要求

- 沙箱测试：超时 killpg、rlimit、原子发布（镜像 services/ifc 现有用例）。
- 成对快照测试：save 后 `scripts/v{n}.py` 与 `versions/v{n}.dxf` lockstep；rollback = 恢复脚本进暂存 + 重跑；失败 422 不留版本。
- 暂存链测试：10 步环形、undo/redo/discard 导航、staging diff。
- verify 隔离契约测试（机器强制，镜像 `services/ifc/tests/test_verify_isolation.py`）。
- 新增测试量 ≥ 新增实现量（仓内 ≥1:1 硬规则）。
