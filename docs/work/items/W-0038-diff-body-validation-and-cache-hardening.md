# W-0038: DiffBody base/target 形状校验 + 物化落盘 tmp+replace 加固（两侧同做）

- **状态：** open
- **优先级：** P2
- **Milestone：** v0.6（services/cad script-as-source；ifc 侧镜像）
- **来源：** chunk B 终审 deferred 合并（2026-08-13，分支 feat/v0.6-cad-diff）
- **执行者/分支：** （领取时填）

## 背景

chunk B 终审提出两条跨侧同型的加固项，统一收拢为一项两侧同做：

1. **DiffBody 形状校验缺失**：`POST /models/{id}/diff` 的 body `{base, target}`
   在 `services/ifc/app/routes_diff.py` 与 `services/cad/app/routes_diff.py` 两侧
   均未用 pydantic `Field(pattern=...)` 声明式校验 base/target 形状——缓存路径
   `versions/diff-{base}-{target}.json` 在未经校验的输入上直接构造，注入异常
   字符（路径分隔符等）可越出预期路径。
2. **物化落盘非原子**：`ifc_materialize` / `dxf_materialize` 直写最终缓存路径，
   进程中断（kill/崩溃）可能在缓存位留下写了一半的毒化缓存，后续请求把残缺
   文件当成合法命中。应 tmp+`os.replace` 原子发布（与 diff 结果缓存发布同构，
   参考 W-0036/W-0037）。

## 涉及位置

- `services/ifc/app/routes_diff.py`（DiffBody 模型 + 缓存路径构造）
- `services/cad/app/routes_diff.py`（同上，镜像）
- `services/ifc/app/ifc_materialize.py`（直写最终缓存路径）
- `services/cad/app/dxf_materialize.py`（同上，镜像）
- 测试落点：`services/ifc/tests/test_diff.py` / `services/cad/tests/test_diff.py`
  及对应 materialize 测试文件

## 方案

1. **形状校验（两侧）**：DiffBody 的 `base`/`target` 字段加 pydantic
   `Field(pattern=...)`（版本号形状按两侧现行版本命名规则；`target` 额外放行
   `"current"`），非法形状 422 在缓存路径构造前拦截。属请求形状校验，归声明式
   层，不进 `verify*`。
2. **原子物化（两侧）**：物化结果先写同目录唯一 tmp（pid+线程 id，参考
   W-0036/W-0037 范式），完成后 `os.replace` 到最终缓存路径，保证缓存位要么
   不存在、要么完整。

## 验收标准

- 两侧 DiffBody 非法 base/target 形状 → 422，不触缓存路径构造；合法形状行为不变。
- 两侧 materialize 均为 tmp+replace 原子发布，无直写最终路径残留逻辑。
- 两侧各配契约/回归测试（形状校验 422 用例 + 原子发布用例）。
- `test_verify_isolation.py` 的 ALLOWLIST 不新增任何条目。
- 两侧全量测试绿；新增测试量 ≥ 新增实现量。

## 测试要求

- TDD：先写失败测试（422 拦截用例、原子发布回归用例），再改实现。
- 校验隔离机器强制保持绿：新增检查只准落在声明式层或既有 `verify*`/`validate*` 内。
