"""W-0025: skill hooks 形态/schema/行为测试——「校验即事件」的机器契约。

hooks 是 aiifc skill 包的顶层目录（opencode 插件 + Claude Code 配置 + 校验脚本），
本文件校验：
- bundle 布局与文件存在性（opencode/claude 双形态 + 公共校验脚本）
- schema（opencode 插件含 tool.execute.after 注册；claude 配置 JSON 合法含 PostToolUse）
- validate_script.py 行为（纯 ast 静态校验单测，不依赖 ifcopenshell；
  sandbox 试跑测试在 ifcopenshell 可用时跑）
- 事件 URI 规范化（aiifc://model/{id}/script/validated 形态）
- SKILL.md 文档 hooks 小节 + 降级路径
"""

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "skills" / "aiifc" / "hooks"
SKILL_MD = REPO_ROOT / "skills" / "aiifc" / "SKILL.md"
FLOWS_DIR = REPO_ROOT / "skills" / "aiifc" / "references" / "docs" / "flows"

sys.path.insert(0, str(HOOKS_DIR))
import validate_script  # noqa: E402

HOOK_FILES = (
    "README.md",
    "claude-settings.json",
    "opencode-plugin.ts",
    "validate_script.py",
    "validate_script.sh",
)

EVENT_URI_RE = re.compile(r"^aiifc://(model/m_[0-9a-f]{16}/)?script/(validated|validation-failed)$")

GOOD_SCRIPT = '''PARAMS = {"length": 5.0, "height": 3.0, "nested": {"t": 0.2}, "tags": ["a"]}

def build(params, out_path):
    pass

if __name__ == "__main__":
    build(PARAMS, "model.ifc")
'''

BAD_SCRIPT = '''PARAMS = {"length": 5.0}

def build(params):
    pass
'''

MODEL_ID = "m_0123456789abcdef"


class TestHooksBundleLayout:
    """hooks 目录是 skill bundle 的一部分：文件齐全 + 双形态 schema 合法。"""

    def test_hooks_files_exist(self):
        for rel in HOOK_FILES:
            assert (HOOKS_DIR / rel).is_file(), f"hooks 缺少 {rel}"

    def test_opencode_plugin_registers_tool_execute_after(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert "tool.execute.after" in text, "opencode 插件必须注册 tool.execute.after hook"
        assert "write" in text and "edit" in text, "插件必须监听 write/edit 工具"
        assert "validate_script.py" in text, "插件必须委托给 validate_script.py"

    def test_opencode_plugin_is_typescript_module(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert "export default" in text, "插件必须是 opencode 可加载的默认导出模块"

    def test_claude_settings_json_valid_with_posttooluse(self):
        raw = json.loads((HOOKS_DIR / "claude-settings.json").read_text(encoding="utf-8"))
        hooks = raw["hooks"]
        assert "PostToolUse" in hooks, "claude hooks 配置必须含 PostToolUse"
        assert len(hooks["PostToolUse"]) >= 1
        inner = hooks["PostToolUse"][0]
        assert "matcher" in inner
        assert re.search(r"Write|Edit", inner["matcher"]), "matcher 应覆盖 Write/Edit 工具"
        commands = [h["command"] for h in inner["hooks"]]
        assert any("validate_script.sh" in c for c in commands), \
            "PostToolUse 必须指向 validate_script.sh"

    def test_validate_script_sh_is_shell_script(self):
        head = (HOOKS_DIR / "validate_script.sh").read_text(encoding="utf-8").splitlines()
        assert head and head[0].startswith("#!"), "validate_script.sh 必须是可执行脚本"

    def test_hooks_readme_documents_event_uris(self):
        text = (HOOKS_DIR / "README.md").read_text(encoding="utf-8")
        for uri in ("aiifc://model/{id}/script/validated",
                    "aiifc://script/validated",
                    "aiifc://script/validation-failed"):
            assert uri in text, f"hooks README 必须定义事件 URI: {uri}"


class TestOpencodePluginProbe:
    """opencode 插件解释器探测（AIIFC_PYTHON → 仓库 edit-service venv → python3）。

    仓库根不得按固定层级数硬编码（软链安装经 import.meta.url 解析到真实 hooks 目录、
    复制安装则在 .opencode/plugin/ 下——两者深度不同），必须用 AGENTS.md/.git 锚点
    逐级向上定位。见 W-0025 review Finding 1。
    """

    def test_anchor_walk_from_hooks_dir_lands_on_repo_root(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert "AGENTS.md" in text and ".git" in text, \
            "插件必须用 AGENTS.md/.git 锚点向上找仓库根"
        root = None
        dir_ = HOOKS_DIR
        for _ in range(8):
            if (dir_ / "AGENTS.md").is_file() or (dir_ / ".git").exists():
                root = dir_
                break
            parent = dir_.parent
            if parent == dir_:
                break
            dir_ = parent
        assert root == REPO_ROOT, \
            f"锚点向上找仓库根落点错误: {root} != {REPO_ROOT}（固定层级会落在仓库父目录）"

    def test_repo_root_not_resolved_by_fixed_levels(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert 'path.resolve(THIS_DIR, ".."' not in text, \
            "仓库根不得用固定层级数（软链/复制安装深度不同）——必须锚点向上找"

    def test_venv_python_candidate_resolves_under_repo_root(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert '"services", "ifc", ".venv", "bin", "python"' in text, \
            "插件必须构造仓库内 services/ifc venv python 候选路径"
        # 只断言候选路径是仓库根下的相对构造，不断言文件真实存在：
        # CI 的 skill job 用独立 .ci-venv，不创建 services/ifc 的 .venv——
        # 存在性由插件运行时 existsSync 探测决定（缺失时降级 python3），
        # 测试环境不得假设本机开发 venv（2026-08-10 CI flake）。
        candidate = REPO_ROOT / "services" / "ifc" / ".venv" / "bin" / "python"
        assert candidate.parents[2].name == "ifc"
        assert candidate.parents[3].name == "services"
        assert REPO_ROOT in candidate.parents

    def test_probe_chain_order_env_then_venv_then_python3(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert "AIIFC_PYTHON" in text
        assert text.index("AIIFC_PYTHON") < text.index('"services", "ifc"') < text.index('"python3"'), \
            "探测链顺序必须 AIIFC_PYTHON → 仓库 venv → python3"


class TestOpencodePluginTimeouts:
    """插件 spawn 超时必须显著大于沙箱超时（W-0025 review Finding 2）。

    否则挂死脚本被插件 SIGTERM 提前掐死，validate_script.py 来不及打印 timed_out
    事件——「失败即事件」退化为静默跳过，且孤儿沙箱子进程残留（TemporaryDirectory
    清理不执行）。
    """

    def test_spawn_timeout_exceeds_sandbox_timeout(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        spawn_ms = re.search(r"SPAWN_TIMEOUT_MS\s*=\s*(\d[\d_]*)", text)
        sandbox_s = re.search(r"SANDBOX_TIMEOUT_S\s*=\s*(\d+)", text)
        assert spawn_ms and sandbox_s, "插件必须定义 SPAWN_TIMEOUT_MS 与 SANDBOX_TIMEOUT_S"
        spawn_ms = int(spawn_ms.group(1).replace("_", ""))
        sandbox_s = int(sandbox_s.group(1))
        assert spawn_ms > sandbox_s * 1000, \
            f"插件超时({spawn_ms}ms)必须大于沙箱超时({sandbox_s}s)"
        assert spawn_ms >= 2 * sandbox_s * 1000, \
            f"插件超时应至少为沙箱超时的 2 倍（当前 {spawn_ms}ms vs {sandbox_s}s）"

    def test_sandbox_timeout_bound_to_constant(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert re.search(r'"--sandbox-timeout",\s*String\(SANDBOX_TIMEOUT_S\)', text), \
            "--sandbox-timeout 必须绑定 SANDBOX_TIMEOUT_S 常量（防两处漂移）"

    def test_timeout_kills_process_group(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert "detached" in text, "spawn 必须 detached（独立进程组）"
        assert "process.kill(-proc.pid" in text, "超时必须杀进程组防孤儿沙箱"


class TestOpencodePluginEditTrigger:
    """edit 工具载荷是 {filePath, oldString, newString}（write 才是 {filePath, content}）。

    按工具分支取参；edit 替换区不含契约特征时回读磁盘（替换区外仍可能保留
    PARAMS = / def build(params）。
    """

    def test_edit_reads_newstring(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert 'tool === "edit"' in text, "必须按工具分支取参"
        assert 'args?.newString' in text, "edit 必须从 args.newString 取内容"

    def test_write_reads_content(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert 'args?.content' in text, "write 必须从 args.content 取内容"

    def test_edit_falls_back_to_disk_content(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert "readFileSync" in text, "edit 替换区无契约特征时应回读磁盘文件"




class TestSkillMdDocumentsHooks:
    """SKILL.md 必须文档化 hooks：安装/用法 + 事件 URI + 降级路径（hooks 是增强不是替代）。"""

    def test_skill_md_has_hooks_section(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        assert "hooks" in text.lower()
        for marker in ("aiifc://script/validated", "aiifc://script/validation-failed",
                       "validate_script.py", "PostToolUse"):
            assert marker in text, f"SKILL.md hooks 小节缺少 {marker}"

    def test_skill_md_documents_degradation_path(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        assert "MUST #27" in text, "降级路径必须保留 MUST #27 手动校验指引"
        assert "validate_script_contract" in text
