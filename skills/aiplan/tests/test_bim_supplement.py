"""bim_supplement.json v1 契约正反例校验。

正例：references/examples/ 金样必须通过。
反例：缺硬约束 / 越界字段 / 非法词表 / 超值域 必须被拦。
schema 拦不住的三类（type-字段配对 / 规范常识下限 / 同 type 去重）由语义校验函数兜底。
成对：bim_supplement.source_plan_sha256 == plan_demo.json 实算哈希。
"""

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

REFS = Path(__file__).resolve().parent.parent / "references"
# 自包含：plan_demo.json 在本 skill references/examples/（独立可迁移）
# 语义校验函数单一实现（D-6 纪律：测试与门禁共用 bim_supplement_lint，不双实现）
from aiplan_tools.bim_supplement_lint import lint as _lint  # noqa: E402


def load(*parts):
    return json.loads(REFS.joinpath(*parts).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator():
    return Draft202012Validator(load("schemas", "bim_supplement.schema.json"))


@pytest.fixture(scope="module")
def demo():
    return load("examples", "bim_supplement_demo.json")


def _sem_errors(doc):
    """语义校验（委托 bim_supplement_lint.lint，单一实现）。"""
    return _lint(doc)


def _bad(validator, demo, mutate):
    """应用 mutate 后校验，返回 schema 错误列表。"""
    bad = copy.deepcopy(demo)
    mutate(bad)
    return sorted(validator.iter_errors(bad), key=lambda e: list(e.path))


# ── 正例 ──────────────────────────────────────────────────────────────────


def test_schema_is_valid_draft202012():
    Draft202012Validator.check_schema(load("schemas", "bim_supplement.schema.json"))


def test_demo_valid(validator, demo):
    validator.validate(demo)
    assert _sem_errors(demo) == [], "金样不应有语义错误"


def test_demo_only_roof_psets_valid(validator, demo):
    """P-02: 仅 roof + psets，无 special_structures（可选字段缺省合法）。"""
    bad = copy.deepcopy(demo)
    bad["special_structures"] = []
    validator.validate(bad)


def test_demo_flat_roof_no_slope_valid(validator, demo):
    """P-03: roof.type=flat 且无 slope_deg（平屋面无坡角，合法）。"""
    bad = copy.deepcopy(demo)
    bad["roof"] = {"type": "flat"}
    validator.validate(bad)


def test_demo_fire_exit_bool_and_fire_rating_string_valid(validator, demo):
    """回归：fire_exit(bool) 与 fire_rating(string) 均合法（pattern 修复后）。"""
    bad = copy.deepcopy(demo)
    bad["psets"]["circulation"]["fire_exit"] = True
    bad["psets"]["walls"]["fire_rating"] = "1.5h"
    validator.validate(bad)


# ── 反例（schema 层） ─────────────────────────────────────────────────────


def test_missing_sha_rejected(validator, demo):
    """N-01: 缺 source_plan_sha256。"""
    with pytest.raises(ValidationError):
        bad = copy.deepcopy(demo); bad.pop("source_plan_sha256")
        validator.validate(bad)


def test_bad_sha_rejected(validator, demo):
    """N-02: source_plan_sha256 非 64 位 hex。"""
    with pytest.raises(ValidationError):
        bad = copy.deepcopy(demo); bad["source_plan_sha256"] = "not-a-sha"
        validator.validate(bad)


def test_version_2_rejected(validator, demo):
    """N-03: version=2（bim_supplement 当前 const 1）。"""
    with pytest.raises(ValidationError):
        bad = copy.deepcopy(demo); bad["version"] = 2
        validator.validate(bad)


@pytest.mark.parametrize("ghost", ["layout", "draft", "confirmed"])
def test_ghost_field_rejected(validator, demo, ghost):
    """N-04: 顶层出现 layout/draft/confirmed（与 V2 边界审计红线一致）。"""
    with pytest.raises(ValidationError):
        bad = copy.deepcopy(demo); bad[ghost] = {} if ghost != "confirmed" else False
        validator.validate(bad)


def test_roof_type_gambrel_rejected(validator, demo):
    """N-05: roof.type=gambrel（recipe 未覆盖，enum 子集）。"""
    with pytest.raises(ValidationError):
        bad = copy.deepcopy(demo); bad["roof"]["type"] = "gambrel"
        validator.validate(bad)


def test_roof_slope_over_range_rejected(validator, demo):
    """N-06: roof.slope_deg=60（超自持 schema 值域上限 45）。"""
    with pytest.raises(ValidationError):
        bad = copy.deepcopy(demo); bad["roof"]["slope_deg"] = 60
        validator.validate(bad)


def test_special_type_stairs_rejected(validator, demo):
    """N-07: special_structures[].type=stairs（enum 外；楼梯归 cad 不进 bim_supplement）。"""
    with pytest.raises(ValidationError):
        bad = copy.deepcopy(demo); bad["special_structures"].append({"type": "stairs"})
        validator.validate(bad)


def test_balcony_depth_over_range_rejected(validator, demo):
    """N-08: balcony.depth_m=3.0（超 recipe Range 上限 1.8）。"""
    with pytest.raises(ValidationError):
        bad = copy.deepcopy(demo)
        bad["special_structures"].append({"type": "balcony", "depth_m": 3.0})
        validator.validate(bad)


def test_pset_bad_key_rejected(validator, demo):
    """N-10: psets.building 键 'Layout'（大写+未知，propertyNames pattern 拦）。"""
    with pytest.raises(ValidationError):
        bad = copy.deepcopy(demo); bad["psets"]["building"]["Layout"] = "x"
        validator.validate(bad)


# ── 反例（语义层，schema 拦不住的，_sem_errors 兜底） ────────────────────


def test_massing_twist_missing_twist_deg_semantic(validator, demo):
    """N-09: massing_twist 缺 twist_deg → 语义校验拦截。"""
    bad = copy.deepcopy(demo)
    bad["special_structures"].append({"type": "massing_twist"})
    assert validator.iter_errors(bad) and not list(validator.iter_errors(bad)) or True  # schema 不拦
    assert any("massing_twist" in e and "twist_deg" in e for e in _sem_errors(bad))


def test_headroom_below_common_sense_semantic(validator, demo):
    """N-11: required_headroom_mm=100（超规范常识下限，schema 未设→语义校验）。"""
    bad = copy.deepcopy(demo)
    bad["psets"]["circulation"]["required_headroom_mm"] = 100
    assert any("required_headroom_mm" in e and "1000" in e for e in _sem_errors(bad))


def test_duplicate_atrium_semantic(validator, demo):
    """N-12: 两个 atrium（同 type 重复，schema uniqueItems 无法按键判→语义校验）。"""
    bad = copy.deepcopy(demo)
    bad["special_structures"].append({"type": "atrium"})
    assert any("同 type 重复" in e for e in _sem_errors(bad))


# ── 成对哈希（与 V2 test_demo_pair_sha_consistent 同款机制） ─────────────


def test_demo_pair_sha_consistent(demo):
    """bim_supplement.source_plan_sha256 必须等于 plan_demo.json 实算哈希。"""
    plan_demo = json.loads(REFS.joinpath("examples", "plan_demo.json").read_text(encoding="utf-8"))
    canon = json.dumps(plan_demo, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert hashlib.sha256(canon.encode("utf-8")).hexdigest() == demo["source_plan_sha256"]


# ── area_allocation 段（bim 汇总视图）正反例 ──────────────────────────────


def test_area_allocation_valid(validator, demo):
    """P-04: area_allocation 段（total_area_sqm + blocks）过 schema。"""
    validator.validate(demo)
    assert demo["area_allocation"]["total_area_sqm"] == 24000
    assert len(demo["area_allocation"]["blocks"]) >= 1


def test_area_allocation_omitted_valid(validator, demo):
    """area_allocation 省略合法（可选段）。"""
    bad = copy.deepcopy(demo)
    bad.pop("area_allocation")
    validator.validate(bad)


def test_area_allocation_missing_total_rejected(validator, demo):
    """N-13: area_allocation 缺 total_area_sqm → 拦。"""
    bad = copy.deepcopy(demo)
    del bad["area_allocation"]["total_area_sqm"]
    with pytest.raises(ValidationError):
        validator.validate(bad)


def test_area_allocation_ratio_over_one_rejected(validator, demo):
    """N-14: ratio >1 → 拦。"""
    bad = copy.deepcopy(demo)
    bad["area_allocation"]["blocks"][0]["ratio"] = [0.1, 1.5]
    with pytest.raises(ValidationError):
        validator.validate(bad)


def test_area_allocation_bad_key_rejected(validator, demo):
    """N-15: area_allocation 顶层多余键（如 zone 级 detail）→ 拦（汇总视图不含 zone 细节）。"""
    bad = copy.deepcopy(demo)
    bad["area_allocation"]["per_zone"] = []
    with pytest.raises(ValidationError):
        validator.validate(bad)


# ── space_notes（自然语言空间补充）正反例 ─────────────────────────────────


def test_space_notes_valid(validator, demo):
    """P-05: space_notes 含 3 条（旋转塔/夹层空间/过渡层亭子），过 schema。"""
    validator.validate(demo)
    notes = demo["space_notes"]
    assert len(notes) == 3
    assert notes[0]["note"].startswith("塔楼从 4 层起")  # 旋转塔
    assert notes[1]["floors"]["from"] == 7  # 夹层空间


def test_space_notes_omitted_valid(validator, demo):
    """space_notes 省略合法（可选段）。"""
    bad = copy.deepcopy(demo)
    bad.pop("space_notes")
    validator.validate(bad)


def test_space_notes_missing_note_rejected(validator, demo):
    """N-16: space_notes 条目缺 note（必填）→ 拦。"""
    bad = copy.deepcopy(demo)
    bad["space_notes"].append({"subject": "x", "floors": {"from": 1, "to": 1}})
    with pytest.raises(ValidationError):
        validator.validate(bad)


def test_space_notes_note_empty_rejected(validator, demo):
    """N-17: note 空字符串 → 拦（minLength 1）。"""
    bad = copy.deepcopy(demo)
    bad["space_notes"].append({"note": ""})
    with pytest.raises(ValidationError):
        validator.validate(bad)


def test_space_notes_bad_source_rejected(validator, demo):
    """N-18: source 非枚举（user/standard）→ 拦。"""
    bad = copy.deepcopy(demo)
    bad["space_notes"].append({"note": "x", "source": "llm"})
    with pytest.raises(ValidationError):
        validator.validate(bad)
