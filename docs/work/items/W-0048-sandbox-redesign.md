# W-0048: 沙箱设计修正——执行环境收敛与 uv 依赖管理

- **状态：** open
- **优先级：** P1
- **Milestone：** v0.11（见 PLAN-v0.1.0.md）
- **来源：** 2026-08-19 用户裁决（W-0047 复盘）：「本仓功能冗余，设计不合理」——双后端降级冗余、双 runner 复制漂移、沙箱依赖环境不可控
- **执行者/分支：** （领取时填）

## 背景

W-0047 加固后的沙箱仍有三处结构性冗余（用户裁决需修正）：

1. **双后端冗余**：bwrap + rlimit 两条隔离路径，rlimit 是弱隔离（不拦 FS 越界写/网络），存在意义仅限无 bwrap 的 dev 机。生产应只有 bwrap 一条路径。
2. **双 runner 复制**：`services/ifc/app/script_runner.py` 与 `services/cad/app/script_runner.py` 逐行复制（W-0047 已同步加固一次），漂移风险持续存在。
3. **沙箱依赖环境不可控**：脚本只能复用服务自身 venv 的包（PYTHONPATH=flows + 服务 site-packages），脚本无法声明依赖；服务升级依赖会影响脚本行为。

方向（用户裁决 2026-08-19）：用 **uv 做沙箱内的包管理**——脚本可声明依赖，由 uv 解析进隔离执行环境。注意分层：uv 管依赖隔离/可复现，bwrap 管安全边界（FS/网络/资源），两者组合而非替代。

## 涉及位置

- `services/ifc/app/script_runner.py`、`services/cad/app/script_runner.py`（合一抽取）
- `services/ifc/app/config.py`、`services/cad/app/config.py`（后端选择配置收敛）
- 沙箱 env 构建（`_sandbox_env`）→ uv 临时环境

## 方案

1. **rlimit 后端退役**：生产路径只留 bwrap；rlimit 收缩为测试夹具（或删除，测试全部走 bwrap mock/真跑）。无 bwrap 直接启动失败/503（fail-closed 已有），删除 `ALLOW_RLIMIT_FALLBACK` 开关语义改为「仅测试」。
2. **双 runner 合一**：抽公共沙箱包（如 `services/_sandbox/` 或共享 wheel），ifc/cad 各留薄适配（产物名/flows 前缀差异）。
3. **uv 沙箱执行环境**：脚本头部可声明依赖（PEP 723 inline metadata 或 flows 契约扩展），run 前 `uv` 解析+创建/复用缓存环境，bwrap 内执行。与 DSL 方向互补：DSL 成熟后脚本面收窄，此环境服务于逃生舱脚本。
4. 顺带按「代码门控」拆超限文件：两侧 `routes_scripts.py`（716/649 行，白名单在册）。

## 验收标准

- 单后端：无 bwrap 环境 run 一律 503（无降级开关）；测试不依赖 rlimit 路径。
- 单 runner：两服务 import 同一沙箱模块；隔离测试（越界/断网/泛洪/并发）单侧维护双侧生效。
- 脚本依赖声明经 uv 解析后在沙箱内可 import（含缓存复用，不重复解析）。
- `routes_scripts.py` 两侧拆分出白名单。

## 测试要求

- TDD；合并 runner 前先抽契约测试钉两测行为一致（参数化同用例跑两侧）。
- uv 环境解析的失败模式（依赖不存在/网络不可达）有测试。
