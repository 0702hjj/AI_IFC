"""P2 BIM 补充产物测试：bim_supplement_lint / validate_bim_supplement / land_pair。

验收（implement.md P2）：
- lint: N-09 type↔必填 / N-11 常识下限 / N-12 同 type 去重，各正反例
- validate_bim_supplement: schema+语义双门禁，金样通过、反例被拦
- land_pair: 成对落盘到 plan/ 目录，canon 字节级可重现，source_plan_sha256 互指
"""

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
from aiplan_tools import bim_supplement_lint  # noqa: E402
from aiplan_tools import validate_bim_supplement  # noqa: E402
from aiplan_tools import land_pair  # noqa: E402
from aiplan_tools import plan_canon  # noqa: E402

REFS = HERE.parent / "references"


@pytest.fixture
def demo():
    return json.loads((REFS / "examples" / "bim_supplement_demo.json").read_text(encoding="utf-8"))


@pytest.fixture
def plan_demo():
    return json.loads((REFS / "examples" / "plan_demo.json").read_text(encoding="utf-8"))


# ── P2.1 bim_supplement_lint ──────────────────────────────────────────────


def test_lint_golden_clean(demo):
    """金样零语义错误。"""
    assert bim_supplement_lint.lint(demo) == []


def test_lint_massing_twist_missing_twist_deg(demo):
    """N-09: massing_twist 缺必填 twist_deg → 报。"""
    import copy
    bad = copy.deepcopy(demo)
    bad["special_structures"].append({"type": "massing_twist"})
    errs = bim_supplement_lint.lint(bad)
    assert any("massing_twist" in e and "twist_deg" in e for e in errs)


def test_lint_headroom_below_common_sense(demo):
    """N-11: required_headroom_mm=100 < 1000 → 报。"""
    import copy
    bad = copy.deepcopy(demo)
    bad["psets"]["circulation"]["required_headroom_mm"] = 100
    assert any("required_headroom_mm" in e for e in bim_supplement_lint.lint(bad))


def test_lint_duplicate_type(demo):
    """N-12: 两个 atrium → 报同 type 重复。"""
    import copy
    bad = copy.deepcopy(demo)
    bad["special_structures"].append({"type": "atrium", "size_m": [10, 8]})
    assert any("同 type 重复" in e and "atrium" in e for e in bim_supplement_lint.lint(bad))


def test_lint_is_valid_helper(demo):
    """is_valid 便捷函数。"""
    assert bim_supplement_lint.is_valid(demo) is True


# ── P2.2 validate_bim_supplement 双门禁 ────────────────────────────────────


def test_validate_bim_demo_passes(demo):
    """金样过双门禁。"""
    assert validate_bim_supplement.validate(demo) == []


def test_validate_bim_schema_error_caught(demo):
    """schema 层错误（version=2）被双门禁拦。"""
    import copy
    bad = copy.deepcopy(demo)
    bad["version"] = 2
    errs = validate_bim_supplement.validate(bad)
    assert errs and any("version" in e for e in errs)


def test_validate_bim_semantic_error_caught(demo):
    """语义层错误（massing_twist 缺 twist_deg）被双门禁拦。"""
    import copy
    bad = copy.deepcopy(demo)
    bad["special_structures"].append({"type": "massing_twist"})
    errs = validate_bim_supplement.validate(bad)
    assert errs and any("语义" in e for e in errs)


def test_validate_bim_cli_exit_code(tmp_path, demo):
    """CLI 退出码：金样 0，坏文件 1。"""
    good = tmp_path / "good.json"
    good.write_text(json.dumps(demo), encoding="utf-8")
    assert validate_bim_supplement._main([str(good), "--quiet"]) == 0

    import copy
    bad_obj = copy.deepcopy(demo)
    bad_obj["version"] = 2
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(bad_obj), encoding="utf-8")
    assert validate_bim_supplement._main([str(bad), "--quiet"]) == 1


# ── P2.3 land_pair 成对落盘 ───────────────────────────────────────────────


def test_land_pair_writes_both_files(tmp_path, plan_demo, demo):
    """成对落盘：run 目录下两文件都存在，canon 字节级可重现。"""
    out = tmp_path / "plan"
    plan_sha, bim_sha, run_dir = land_pair.land_pair(plan_demo, demo, out)
    assert (run_dir / "plan.json").exists()
    assert (run_dir / "bim_supplement.json").exists()
    assert len(plan_sha) == 64 and len(bim_sha) == 64


def test_land_pair_sha_interlock(tmp_path, plan_demo, demo):
    """L-01: bim_supplement.source_plan_sha256 == plan.json canon 后 sha（互指）。"""
    out = tmp_path / "plan"
    plan_sha, _, run_dir = land_pair.land_pair(plan_demo, demo, out)
    reread_bim = json.loads((run_dir / "bim_supplement.json").read_text(encoding="utf-8"))
    assert reread_bim["source_plan_sha256"] == plan_sha


def test_land_pair_canon_reproducible(tmp_path, plan_demo, demo):
    """canon 字节级可重现：两次落盘（各自 run 目录）字节相同。"""
    out = tmp_path / "plan"
    _, _, run1 = land_pair.land_pair(plan_demo, demo, out)
    _, _, run2 = land_pair.land_pair(plan_demo, demo, out)
    assert (run1 / "plan.json").read_bytes() == (run2 / "plan.json").read_bytes()
    assert (run1 / "bim_supplement.json").read_bytes() == (run2 / "bim_supplement.json").read_bytes()


def test_land_pair_rejects_bad_plan(tmp_path, plan_demo, demo):
    """plan 门禁失败 → 不写盘、抛 ValueError。"""
    import copy
    bad_plan = copy.deepcopy(plan_demo)
    del bad_plan["site"]
    with pytest.raises(ValueError, match="plan.json 门禁失败"):
        land_pair.land_pair(bad_plan, demo, tmp_path / "plan")


def test_land_pair_rejects_bad_bim(tmp_path, plan_demo, demo):
    """bim 双门禁失败 → 不写盘、抛 ValueError。"""
    import copy
    bad_bim = copy.deepcopy(demo)
    bad_bim["version"] = 2
    with pytest.raises(ValueError, match="bim_supplement"):
        land_pair.land_pair(plan_demo, bad_bim, tmp_path / "plan")


def test_land_pair_cli(tmp_path, plan_demo, demo):
    """CLI：两文件路径 → 单开 run 目录落盘 + 打印 sha，退出码 0。"""
    plan_p = tmp_path / "plan.json"
    bim_p = tmp_path / "bim.json"
    plan_p.write_text(json.dumps(plan_demo), encoding="utf-8")
    bim_p.write_text(json.dumps(demo), encoding="utf-8")
    out = tmp_path / "out"
    rc = land_pair._main([str(plan_p), str(bim_p), "--outdir", str(out)])
    assert rc == 0
    runs = [d for d in out.iterdir() if d.is_dir()]
    assert len(runs) == 1  # 单开一个 run 目录
    assert (runs[0] / "plan.json").exists()
    assert (runs[0] / "bim_supplement.json").exists()


def test_land_pair_cli_group_routed_placeholder(tmp_path, plan_demo, demo):
    """回归（2026-08-13 落盘卡死 bug）：分组路由 `aiplan land` 补 argv[0] 占位
    （POSITIONAL_FIRST 约定：argv[0]='aiplan land'=脚本名）——argparse 型模块
    必须跳过占位，否则占位被当 plan 位置参数、真实 plan 被当 bim 报多余参数。

    修复前：land_pair._main(["aiplan land", plan, bim]) → parse_args 崩（bim 多余）
    修复后：占位跳过 → plan/bim 正确解析 → exit 0。
    """
    plan_p = tmp_path / "plan.json"
    bim_p = tmp_path / "bim.json"
    plan_p.write_text(json.dumps(plan_demo), encoding="utf-8")
    bim_p.write_text(json.dumps(demo), encoding="utf-8")
    out = tmp_path / "out"
    # 分组路由透传的真实形态（cli.py POSITIONAL_FIRST 补占位后）
    rc = land_pair._main(["aiplan land", str(plan_p), str(bim_p),
                          "--outdir", str(out)])
    assert rc == 0, "带占位的分组路由调用必须落盘成功（不报多余参数）"
    runs = [d for d in out.iterdir() if d.is_dir()]
    assert len(runs) == 1
    assert (runs[0] / "plan.json").exists()
    assert (runs[0] / "bim_supplement.json").exists()


def test_land_pair_creates_unique_run_dirs(tmp_path, plan_demo, demo):
    """落盘唯一性：每次落盘单开 <时间戳>_<项目>/ 目录，零覆盖（用户拍板）。"""
    import copy
    base_plan = copy.deepcopy(plan_demo)
    base_bim = copy.deepcopy(demo)
    # 第一次落盘
    _, _, run1 = land_pair.land_pair(base_plan, base_bim, tmp_path)
    # 第二次（同项目再跑 → 防碰撞加 _2）
    _, _, run2 = land_pair.land_pair(base_plan, base_bim, tmp_path)
    # 第三次（不同项目 → 独立目录）
    plan3 = copy.deepcopy(base_plan)
    plan3["project"] = "另一栋楼"
    _, _, run3 = land_pair.land_pair(plan3, base_bim, tmp_path)
    # 三个独立目录，零覆盖
    runs = sorted(tmp_path.iterdir())
    assert len(runs) == 3
    names = [r.name for r in runs]
    assert run1.name in names and run2.name in names and run3.name in names
    assert "另一栋楼" in run3.name  # run 名含项目
    # 每个 run 目录内两文件齐全 + 互指
    for r in runs:
        p = json.loads((r / "plan.json").read_text(encoding="utf-8"))
        b = json.loads((r / "bim_supplement.json").read_text(encoding="utf-8"))
        assert b["source_plan_sha256"] == land_pair.plan_canon.canon_sha256(p)
    # 无顶层覆盖文件
    assert not (tmp_path / "plan.json").exists()
