# W-0047: 沙箱加固——真实用户上线前的隔离补齐

- **状态：** in-progress
- **优先级：** P0
- **Milestone：** v0.11（见 PLAN-v0.1.0.md）
- **来源：** 2026-08-19 用户裁决（本月内上线真实用户，沙箱隔离优先于 DSL）+ 沙箱勘察报告（explore 子代理，2026-08-19）
- **执行者/分支：** kimi-code / feat/sandbox-hardening

## 背景

script-as-source 的 Python 构建脚本在沙箱执行（`services/ifc` 与 `services/cad` 同构，`script_runner.py` 双份复制）。现状在「单机可信开发者」假设下合格（超时/内存/fork/断网均有测试背书），但「任意真实用户可经 REST 提交脚本」的威胁模型下有四个洞：

1. **跨租户可读**：bwrap `--ro-bind / /` 把整个 `/data` 挂给脚本只读，脚本可把他人模型内容写进自己产物经下载接口带出。
2. **无并发/资源闸**：FastAPI 默认 40 线程并发 × 每 run 1GiB+60s；stdout 全量读入内存无截断；产物无大小上限（可写满 /data 卷）。
3. **降级静默放行**：bwrap 探测失败退到 rlimit 模式后网络不再被封（可直连 postgres/内网），仅一条 warning 日志。
4. **容器 root + cad 无部署形态**：`services/ifc/Dockerfile` 无 USER；`services/cad` 无 Dockerfile、compose 无条目。

## 涉及位置

- `services/ifc/app/script_runner.py`、`services/cad/app/script_runner.py`（`_sandbox_cmd` / `_limits` / `run_script`，两份复制同步改）
- `services/ifc/app/routes_scripts.py`、`services/cad/app/routes_scripts.py`（run/save 入口并发闸）
- `services/ifc/Dockerfile`（USER）、`services/cad/Dockerfile`（新建）、`docker-compose.yml`（cad 条目）
- 部署文档：`docs/site/`（guide/deploy 相关页）强制 `VIEWER_API_TOKEN`

## 方案

1. **bwrap 挂载收窄**：`--ro-bind / /` 改为按需挂载（/usr /lib /lib64 /bin + flows_dir + tmpfs /tmp + workdir 可写），不挂 /data。ifc/cad 双侧。
2. **资源与并发**：`RLIMIT_FSIZE`（256 MiB）；stdout 分块读+超上限杀进程；产物（out.ifc/out.dxf/map.json）发布后大小校验；run/save 入口 `threading.Semaphore(N)`（N 可配置，默认 2-4），满即 429/503。
3. **降级 fail-closed**：rlimit 后端在非显式开关（`ALLOW_RLIMIT_FALLBACK=1`）下拒绝执行（503）；dev 环境默认可放行（本地无 bwrap 时开发不中断），生产 compose 不配该开关。
4. **部署形态**：两个 Dockerfile 加非 root USER（bwrap 在非 root 走 userns 照常）；cad 补 Dockerfile + compose 条目（绑 127.0.0.1，与 ifc 同约束）；部署文档把 `VIEWER_API_TOKEN` 列为必填。
5. 统一两份 runner 的复制漂移：本次只保证改动双侧同步，抽公共包留后续（单独工作项）。

## 验收标准

- 脚本 `open('/data/...')` / 读 `/etc` 在 bwrap 下失败（测试断言）。
- 并发 run 超过闸值返回 429/503；stdout 泛洪/超大产物被截断或拒绝。
- 无 bwrap 且无 ALLOW_RLIMIT_FALLBACK 时 run 拒绝执行（503）；有开关时行为同旧。
- compose up 后 cad 服务健康；两容器进程非 root。
- CI 全绿（含 compose smoke）。

## 测试要求

- TDD：每个洞先写失败测试（复现越界读/泛洪/并发/降级放行），再改实现转绿。
- 新增测试量 ≥ 新增实现量；异步/子进程断言用条件等待，禁止固定 sleep。
- 双侧服务同构改动各配测试（隔离断言在 rlimit 降级下 skip 的既有模式照抄）。
