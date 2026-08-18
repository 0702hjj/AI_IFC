"""aiplan_tools 路径定位：找 aiplan skill 根目录（references/ 等在其下）。

独立迁移纪律：aiplan skill 拷到任何位置都能跑。skill 根定位顺序：
1. 环境变量 AI_PLAN_ROOT（部署时显式指定，最可靠）；
2. 从本文件位置向上搜索 SKILL.md（不依赖固定目录深度，迁移稳健）；
3. editable 安装位置推断（parents[4]，兼容旧布局）。

用法：
    from aiplan_tools import paths
    schema = paths.REFS / "schemas" / "plan.schema.json"
"""

from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent  # .../aiplan_tools/


def _search_upward(start: Path) -> Path | None:
    """从 start 向上逐级找含 SKILL.md + references/ 的目录（skill 根）。"""
    for p in [start, *start.parents]:
        if (p / "SKILL.md").is_file() and (p / "references").is_dir():
            return p
    return None


def find_skill_root() -> Path:
    """返回 aiplan skill 根目录。

    优先顺序：AI_PLAN_ROOT 环境变量 → 向上搜索 SKILL.md → parents[4] 推断。
    全部失败抛 RuntimeError（给出设置 AI_PLAN_ROOT 的指引）。
    """
    env = os.environ.get("AI_PLAN_ROOT")
    if env:
        root = Path(env).resolve()
        if (root / "references").is_dir() and (root / "SKILL.md").exists():
            return root
        raise RuntimeError(f"AI_PLAN_ROOT={root} 不是有效 aiplan skill 根（缺 references/ 或 SKILL.md）")
    # 向上搜索（首选，迁移稳健——不依赖固定深度）
    found = _search_upward(HERE)
    if found:
        return found
    # editable 旧布局推断（parents[4]）
    root = HERE.parents[4]
    if (root / "references").is_dir() and (root / "SKILL.md").exists():
        return root
    raise RuntimeError(
        f"无法定位 aiplan skill 根（搜索 {HERE} 向上未找到 SKILL.md）。"
        "请设置环境变量 AI_PLAN_ROOT=<skill 根目录>。"
    )


SKILL_ROOT = find_skill_root()
REFS = SKILL_ROOT / "references"
BUILDING_TYPES = REFS / "building_types"
