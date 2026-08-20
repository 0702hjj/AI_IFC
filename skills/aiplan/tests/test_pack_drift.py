"""P4 类型包同源漂移测试：check_pack_drift（内部 .md ↔ .rules.json）。

验收（implement.md P4）：
- 初态：aiplan 自持类型包的 .md 与 .rules.json 同源（check_all 全空）
- 改 .rules.json 不改 .md → 报漂移
- 改 .md 不改 .rules.json → 报漂移
- canonical_rule 内联（本 skill 自持实现，即规范化逻辑事实源）
"""

import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
from aiplan_tools import check_pack_drift as cpd  # noqa: E402

PACKS = HERE.parent / "references" / "building_types"


@pytest.fixture
def isolated_packs(tmp_path):
    """复制真实类型包到 tmp，隔离测试（不改真实 building_types）。"""
    dst = tmp_path / "building_types"
    shutil.copytree(PACKS, dst)
    return dst


def test_initial_state_no_drift():
    """初态：aiplan 自持类型包 .md↔.rules.json 同源，check_all 全空。"""
    results = cpd.check_all(PACKS)
    assert all(v == [] for v in results.values()), results


def test_canonical_rule_inline():
    """canonical_rule 内联在本 skill（独立可迁移，与 cad 侧同源手动同步）。"""
    assert hasattr(cpd, "canonical_rule")
    # 规范化字符串稳定
    r = {"predicate": "hub_connect", "args": {"hub": "living", "members": ["bathroom", "bedroom"]}, "strength": "must"}
    assert cpd.canonical_rule(r) == "hub_connect(hub=living;members=bathroom,bedroom)[must]"


def test_rules_json_drift_json_changed(isolated_packs):
    """改 .rules.json（加规则）不改 .md → 报'json 有 md 无'。"""
    pack = json.loads((isolated_packs / "residence.rules.json").read_text(encoding="utf-8"))
    pack["rules"].append({"predicate": "new_pred", "args": {"x": "y"}, "strength": "must"})
    (isolated_packs / "residence.rules.json").write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
    drifts = cpd.check_pack("residence", isolated_packs)
    assert any("json 有 md 无" in d for d in drifts)


def test_rules_json_drift_md_changed(isolated_packs):
    """改 .md（删一行规则反引号）不改 .rules.json → json 比 md 多 → 报'json 有 md 无'。"""
    md = (isolated_packs / "residence.md").read_text(encoding="utf-8")
    import re
    md_changed = re.sub(r"`\w+\([^`]+\)\[(?:must|prefer|avoid)\]`", "（已删）", md, count=1)
    (isolated_packs / "residence.md").write_text(md_changed, encoding="utf-8")
    drifts = cpd.check_pack("residence", isolated_packs)
    assert any("json 有 md 无" in d for d in drifts)


def test_no_rules_json_pack_skipped():
    """无 .rules.json 的包（如 retail 只有 .md）不查，不报。"""
    drifts = cpd.check_pack("retail", PACKS)
    assert drifts == []


def test_missing_md_with_rules_json(isolated_packs):
    """有 .rules.json 但 .md 缺失 → 报。"""
    (isolated_packs / "residence.md").unlink()
    drifts = cpd.check_pack("residence", isolated_packs)
    assert any(".md 缺失" in d for d in drifts)


def test_cli_exit_code(isolated_packs, capsys):
    """CLI：初态退出码 0；有漂移退出码 1。"""
    from aiplan_tools import check_pack_drift as mod
    assert mod._main([]) == 0  # 默认 PACKS 初态无漂移
    # 用 isolated 测漂移态
    pack = json.loads((isolated_packs / "office.rules.json").read_text(encoding="utf-8"))
    pack["rules"].append({"predicate": "x", "args": {"a": "b"}, "strength": "must"})
    (isolated_packs / "office.rules.json").write_text(json.dumps(pack), encoding="utf-8")
    orig = mod.PACKS
    mod.PACKS = isolated_packs
    try:
        assert mod._main([]) == 1
    finally:
        mod.PACKS = orig
