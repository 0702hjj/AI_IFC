# aiifc hooks —— 校验即事件（拉 → 推）

aiifc skill 的 hooks 层把「校验」从被动纪律变成事件驱动闭环：agent 写入/编辑**构建脚本**
时自动触发契约校验（+ 可选沙箱试跑），结果以**事件**回填对话——失败即事件，不污染主上下文。

与 AGENTS.md「纪律事件化」节同构（controller 不轮询、子代理报告即事件载荷）：
hooks 是 skill 包的可选增强层，**不是替代**——不支持 hooks 的环境维持手动校验路径
（SKILL.md MUST #27：agent 自己调 `script_lib.validate_script_contract(path)`）。

## 文件

| 文件 | 形态 | 作用 |
|---|---|---|
| `opencode-plugin.ts` | opencode 插件 | 注册 `tool.execute.after`，write/edit 写入构建脚本时自动触发 |
| `claude-settings.json` | Claude Code hooks 配置（模板） | PostToolUse hook 指向 `validate_script.sh` |
| `validate_script.sh` | shell 薄包装 | Claude Code 形态入口：stdin 载荷 → 校验 → hook JSON |
| `validate_script.py` | **公共实现（单点定义）** | 静态契约校验（ast，stdlib-only）+ 可选沙箱试跑 + 事件组装 |
| `README.md` | 本文档 | 事件 URI 规范 + 安装 + 降级路径 |

两种形态共享同一个 `validate_script.py`——校验逻辑单点定义，不复制第二份。

## 事件 URI 表

校验结果统一以 `aiifc://` URI 命名，为 W-0017 多 agent 协同的事件总线打底：

| 事件 URI | 含义 | 触发 |
|---|---|---|
| `aiifc://script/validated` | 契约校验通过（无 modelId 上下文） | 写入构建脚本 |
| `aiifc://script/validation-failed` | 契约校验失败（无 modelId 上下文） | 写入构建脚本 |
| `aiifc://model/{id}/script/validated` | 契约校验通过（脚本路径含 modelId） | 写入构建脚本 |
| `aiifc://model/{id}/script/validation-failed` | 契约校验失败（路径含 modelId） | 写入构建脚本 |

- `{id}` = modelId（`^m_[0-9a-f]{16}$`），从脚本路径启发式提取：文件名 stem 或
  任一祖先目录名匹配即命中（demo 布局 `staging/{modelId}.py` / `models/{modelId}/scripts/v{n}.py`）；
  可用 `--model-id` 显式指定。提取不到则用无 modelId 的 URI。
- 事件载荷（JSON）：`{uri, ok, path, mode, errors?, modelId?, sandbox?}`
  - `mode`：`static`（仅静态校验）/ `sandbox`（静态 + 沙箱试跑）/ `skip`（非构建脚本）
  - `errors`：契约错误列表（仅失败时非空）
  - `sandbox`：试跑详情 `{ran, exit_code, out_exists, stderr_tail?, timed_out?}`
- **回填纪律**：事件作为简短元信息回填（opencode 走 `title`/`metadata` + 一行 `output`；
  Claude Code 走 `additionalContext`，最多 3 条错误摘要截断 120 字符）。**完整错误不进对话**。

## 触发条件

仅当写入的 `*.py` 内容含**契约特征**时触发：`def build(params` 或 `PARAMS =`。
其它文件写入零成本（`skip`，不产生事件、不占主上下文）。

## 校验内容

1. **静态契约校验**（必做，ast 解析零副作用，只依赖标准库）：
   可解析为 Python；顶层 `PARAMS = {...}` 字面量 dict 且 JSON-compatible；
   顶层 `build(params, out_path)` 入口；`if __name__ == "__main__":` 守卫。
   与 `references/docs/flows/script_lib.py::validate_script_contract` 结论一致
   （有 ifcopenshell 时直接复用它；无则用内嵌 ast 逻辑，漂移防护见
   `tests/skill/test_skill_hooks.py::TestStaticValidate::test_drift_with_script_lib`）。
2. **沙箱试跑**（可选，仅当静态通过且运行解释器有 ifcopenshell）：
   临时目录 + subprocess + timeout（默认 60s）执行脚本，产物写临时目录，
   不污染工作区；试跑失败（非零退出/超时）→ `validation-failed` 事件（`mode: sandbox`）。
   无 ifcopenshell 自动降级为仅静态校验（`mode: static`）。

## 安装

### opencode

把插件放进 opencode 的插件目录（软链或复制均可）：

```bash
ln -s $(pwd)/skills/aiifc/hooks/opencode-plugin.ts .opencode/plugin/aiifc-hooks.ts
```

Python 探测链：`AIIFC_PYTHON` 环境变量 → 仓库内 `services/ifc/.venv/bin/python`
（有 ifcopenshell）→ `python3`。仓库根不按固定层级数硬编码：从 hooks 目录（软链
安装经 `import.meta.url` 解析到真实目录；复制安装则在 `.opencode/plugin/`）逐级向上，
按含 `AGENTS.md`/`.git` 的目录定位——两种安装形态均成立。

超时预算（opencode 侧）：沙箱试跑 30s（`--sandbox-timeout 30`），插件 spawn 兜底
90s（3×30s）。挂死脚本先被沙箱自行掐断并产 `timed_out` 事件（失败即事件）；插件
超时只兜残余挂死进程，且按进程组 SIGKILL 清场，防孤儿沙箱残留。其余超时 60s
（validate_script.py 沙箱默认值）。

### Claude Code

1. 把 `claude-settings.json` 的 `hooks` 块合并进你的 settings
   （`~/.claude/settings.json` 用户级或项目级），把 `{{SKILL_DIR}}` 换成 skill
   实际安装路径，例如：
   ```json
   { "hooks": { "PostToolUse": [ { "matcher": "Write|Edit", "hooks": [ {
       "type": "command",
       "command": "bash ~/.claude/skills/aiifc/hooks/validate_script.sh",
       "timeout": 60,
       "description": "aiifc 构建脚本契约校验（校验即事件）"
   } ] } ] } }
   ```
2. `validate_script.sh` 需要可执行权限（`chmod +x`）或经 `bash` 调用（如上）。
3. Python 探测链：`AIIFC_PYTHON` → 仓库内 edit-service venv → `python3`；
   无 ifcopenshell 时自动降级为纯静态校验。

## 降级路径（重要）

hooks 是**增强不是替代**：

- 不支持 hooks 的 agent 环境（Cursor 等）：维持 SKILL.md MUST #27 手动校验路径——
  agent 写脚本后自己调 `script_lib.validate_script_contract(path)`，出口必经
  `script_lib.write_and_validate`（MUST #29）。
- hooks 触发失败（解释器缺失/超时/解析错误）静默跳过，绝不阻塞工具执行。

## 调试

```bash
# 直接跑静态校验（任意 python，无需 ifcopenshell）
python3 hooks/validate_script.py path/to/script.py --static-only

# 完整事件（有 ifcopenshell 的解释器，默认含沙箱试跑）
services/ifc/.venv/bin/python hooks/validate_script.py path/to/script.py

# Claude Code 载荷模拟
echo '{"tool_name":"Write","tool_input":{"file_path":"a.py"}}' \
  | bash hooks/validate_script.sh
```
