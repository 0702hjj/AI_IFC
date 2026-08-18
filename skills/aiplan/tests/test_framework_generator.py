"""P1 框架生成器测试：plan_canon / validate_plan。

验收（implement.md P1）：
- plan_canon 与 V2 test_demo_pair_sha_consistent 算法完全一致（plan_demo sha 相同）
- validate_plan 金样通过、反例（缺 site/越界字段/version=1）被拦
（outline_ascii 已删除 2026-08-11——ASCII 栅格表达力不足，确认环节改用文字形态描述）
"""

import hashlib
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
from aiplan_tools import plan_canon  # noqa: E402
from aiplan_tools import validate_plan  # noqa: E402

# 自包含：plan_demo.json 在本 skill references/examples/（独立可迁移）
REFS = HERE.parent / "references"


# ── P1.2 plan_canon ───────────────────────────────────────────────────────


def test_canon_matches_v2_algorithm():
    """plan_canon 的 sha256 必须等于 V2 test_demo_pair_sha_consistent 的算法产出。

    这是成对哈希成立的前提——算法漂移则 cad_draft.source_plan_sha256 全部失配。
    """
    plan_demo = json.loads((REFS / "examples" / "plan_demo.json").read_text(encoding="utf-8"))
    # V2 算法（test_contract_schemas.py:132-133）原样复刻
    v2_canon = json.dumps(plan_demo, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    v2_sha = hashlib.sha256(v2_canon.encode("utf-8")).hexdigest()
    # plan_canon 必须给出相同结果
    assert plan_canon.canon_sha256(plan_demo) == v2_sha


def test_canon_deterministic():
    """同对象两次 canon 字节级相同。"""
    obj = {"b": 2, "a": 1, "c": [3, 1, 2]}
    assert plan_canon.canon_dump(obj) == plan_canon.canon_dump(obj)


def test_canon_sorts_keys():
    """canon 排序键（a 在 b 前）。"""
    assert plan_canon.canon_dump({"b": 2, "a": 1}) == '{"a":1,"b":2}'


def test_canon_unicode_not_escaped():
    """ensure_ascii=False：中文不转义（与 V2 一致，金样含中文）。"""
    assert plan_canon.canon_dump({"k": "示例"}) == '{"k":"示例"}'


def test_canon_bim_supplement_pair():
    """bim_supplement_demo.source_plan_sha256 == plan_demo 实算（成对哈希）。"""
    bs = json.loads((HERE.parent / "references" / "examples" / "bim_supplement_demo.json").read_text(encoding="utf-8"))
    plan_demo = json.loads((REFS / "examples" / "plan_demo.json").read_text(encoding="utf-8"))
    assert plan_canon.canon_sha256(plan_demo) == bs["source_plan_sha256"]


# ── P1.3 validate_plan ────────────────────────────────────────────────────


def test_validate_plan_demo_passes():
    """金样 plan_demo 通过门禁。"""
    plan_demo = json.loads((REFS / "examples" / "plan_demo.json").read_text(encoding="utf-8"))
    assert validate_plan.validate(plan_demo) == []


def test_validate_plan_missing_site_rejected():
    """缺 site 被拦（V2 required）。"""
    plan_demo = json.loads((REFS / "examples" / "plan_demo.json").read_text(encoding="utf-8"))
    bad = json.loads(json.dumps(plan_demo))
    del bad["site"]
    errs = validate_plan.validate(bad)
    assert errs and any("site" in e for e in errs)


def test_validate_plan_ghost_layout_rejected():
    """顶层 layout 字段被拦（V2 additionalProperties false，边界审计红线）。"""
    plan_demo = json.loads((REFS / "examples" / "plan_demo.json").read_text(encoding="utf-8"))
    bad = json.loads(json.dumps(plan_demo))
    bad["layout"] = {}
    errs = validate_plan.validate(bad)
    assert errs


def test_validate_plan_version_1_rejected():
    """version=1 被拦（V2 const 2）。"""
    plan_demo = json.loads((REFS / "examples" / "plan_demo.json").read_text(encoding="utf-8"))
    bad = json.loads(json.dumps(plan_demo))
    bad["version"] = 1
    errs = validate_plan.validate(bad)
    assert errs


def test_validate_plan_cli_exit_code(tmp_path):
    """CLI 退出码：金样 0，坏文件 1。"""
    plan_demo = json.loads((REFS / "examples" / "plan_demo.json").read_text(encoding="utf-8"))
    good = tmp_path / "good.json"
    good.write_text(json.dumps(plan_demo), encoding="utf-8")
    assert validate_plan._main([str(good), "--quiet"]) == 0

    bad = tmp_path / "bad.json"
    bad_obj = json.loads(json.dumps(plan_demo))
    del bad_obj["site"]
    bad.write_text(json.dumps(bad_obj), encoding="utf-8")
    assert validate_plan._main([str(bad), "--quiet"]) == 1
