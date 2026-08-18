"""P5.3 中断恢复测试（L-05，D-4）。

验收（implement.md P5.3 / acceptance_tests.md L-05）：
- plan/ 不存在 → route 返回 step-00（从头走完整 P0→P2）
- plan/plan.json + bim_supplement.json 都存在且结构完整 → route 返回 step-02（直进校验）
- plan 存在但 bim 缺失 → step-00（不完整）
- 文件损坏 → step-00
D-4：草案不落盘，所以无中间态路由。
"""

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
from aiplan_tools import route  # noqa: E402
from aiplan_tools import land_pair  # noqa: E402

REFS = HERE.parent / "references"


@pytest.fixture
def plan_demo():
    return json.loads((REFS / "examples" / "plan_demo.json").read_text(encoding="utf-8"))


@pytest.fixture
def bim_demo():
    return json.loads((HERE.parent / "references" / "examples" / "bim_supplement_demo.json").read_text(encoding="utf-8"))


def test_empty_workspace_routes_to_step00(tmp_path):
    """L-05a：plan/ 不存在 → step-00（从头）。"""
    assert route.route(tmp_path) == "step-00"


def test_frozen_pair_routes_to_step02(tmp_path, plan_demo, bim_demo):
    """L-05b：已冻结双产物 → step-02（直进校验，跳过 step-01）。"""
    out = tmp_path / "plan"
    land_pair.land_pair(plan_demo, bim_demo, out)
    assert route.route(tmp_path) == "step-02"


def test_plan_only_no_bim_routes_to_step00(tmp_path, plan_demo):
    """plan 存在但 bim 缺失 → step-00（不完整，从头）。"""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "plan.json").write_text(json.dumps(plan_demo), encoding="utf-8")
    assert route.route(tmp_path) == "step-00"


def test_corrupted_plan_routes_to_step00(tmp_path):
    """文件损坏（非法 JSON）→ step-00。"""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "plan.json").write_text("{bad json", encoding="utf-8")
    (plan_dir / "bim_supplement.json").write_text("{}", encoding="utf-8")
    assert route.route(tmp_path) == "step-00"


def test_bim_missing_source_sha_routes_to_step00(tmp_path, plan_demo):
    """bim 结构不完整（无 source_plan_sha256）→ step-00。"""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "plan.json").write_text(json.dumps(plan_demo), encoding="utf-8")
    (plan_dir / "bim_supplement.json").write_text(
        json.dumps({"version": 1, "project": "x"}),  # 无 source_plan_sha256
        encoding="utf-8")
    assert route.route(tmp_path) == "step-00"


def test_route_deterministic(tmp_path, plan_demo, bim_demo):
    """路由确定性：同状态两次路由结果相同。"""
    out = tmp_path / "plan"
    land_pair.land_pair(plan_demo, bim_demo, out)
    assert route.route(tmp_path) == route.route(tmp_path) == "step-02"


def test_route_cli(tmp_path):
    """CLI：打印 step 名，退出码 0。"""
    assert route._main([str(tmp_path)]) == 0
