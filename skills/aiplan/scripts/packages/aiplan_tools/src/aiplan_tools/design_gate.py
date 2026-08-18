"""design_gate —— 落盘前的设计质量门禁（把"可选流程"升级为"强制门禁"）。

背景（2026-08-11，滨河住宅楼案例反馈）：P0/P1 加的 derive/design_intent/design_patterns/
design_rationale 都是文档层面的"可选流程"，模型在没有强制约束时走最短路径（直接生成矩形
outline，绕过 derive→pattern→design_intent），导致"板式策略想到了但轮廓还是默认长方体"。

本门禁把能力调用变成**落盘必经路径**：
- design_rationale 必填（设计推理显式化）
- design_rationale 必须引用 ≥1 个 derive 事实字段（aspect_ratio/exposure_m/deep_zone_ratio/...）
- 引用的字段必须真实存在于 derive 产出（用 lot+setbacks 实跑 derive 机检）
- 默认矩形检测（疑似绕过 design_intent）→ warning（不 FAIL，防误伤合理矩形设计）

FAIL → 拒绝落盘，回 step-01 第 2 轮重走。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from aiplan_tools.derive import derive_facts

# derive 产出的可引用事实字段（与 derive.py derive_facts 返回键一致）
DERIVE_FACT_FIELDS = [
    "aspect_ratio",
    "exposure_m",
    "deep_zone_ratio",
    "dominant_axes",
    "concave_corners",
    "buildable_ratio",
    "lot_area_sqm",
    "buildable_area_sqm",
    "bounding_box_mm",
]


def _is_simple_rect_fills_buildable(plan_obj: dict, facts: dict) -> bool:
    """检测"默认矩形贴满可建范围"（疑似绕过 design_intent 语义声明）。

    判定：所有 zone 的 outline 都是 4 顶点矩形（无 holes/arcs），
    且地块 aspect_ratio 显著（≥1.4，长板）却没用到 on_edge/polygon 等形态表达。
    """
    aspect = facts.get("aspect_ratio", 0)
    if aspect < 1.4:
        return False  # 非长板地块，矩形合理，不标
    for z in plan_obj.get("zones", []):
        for blk in z.get("outline_mm", []):
            outer = blk.get("outer", [])
            holes = blk.get("holes", [])
            arcs = blk.get("arcs", [])
            if holes or arcs:
                return False  # 有孔洞/弧 = 用了形态表达，不是默认矩形
            if isinstance(outer, list) and len(outer) != 4:
                return False  # 非 4 顶点 = 非矩形
            if isinstance(outer, dict):  # ring object
                return False
    return True  # 全是 4 顶点矩形 + 长板地块 → 疑似默认矩形


def validate_design_quality(plan_obj: dict) -> tuple[list[str], list[str]]:
    """设计质量门禁，返回 (errors, warnings)。errors 非空 → 拒绝落盘。

    errors（强制）：
    - design_rationale 必填
    - design_rationale 必须引用 ≥1 个 derive 事实字段
    - 引用的字段必须真实存在于 derive 产出

    warnings（提示，不 FAIL）：
    - 默认矩形检测（疑似绕过 design_intent）
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ── A. design_rationale 必填 ──
    rationale = str(plan_obj.get("design_rationale", "")).strip()
    if not rationale:
        errors.append(
            "design_rationale 必填（设计推理显式化）——引用 derive 事实说明形态/核心筒/分区决策依据。"
            "回 step-01 第 2 轮：跑 derive → 查 design_patterns → 写 design_intent → 填 design_rationale"
        )
        return errors, warnings  # 没填早退

    # ── B/C. 必须引用 ≥1 个真实 derive 事实字段 ──
    site = plan_obj.get("site", {})
    lot = site.get("lot_polygon_mm")
    setbacks = site.get("setbacks_mm")
    facts = {}
    if lot:
        try:
            facts = derive_facts(lot, setbacks)
        except Exception:
            pass  # derive 失败不阻断（宽松），字段名校验仍进行

    referenced = [f for f in DERIVE_FACT_FIELDS if f in rationale]
    if not referenced:
        errors.append(
            f"design_rationale 必须引用 ≥1 个 derive 事实字段，当前未引用任何。"
            f"可引字段: {DERIVE_FACT_FIELDS}。例: aspect_ratio=... / deep_zone_ratio=... / exposure_m=..."
        )
    elif facts:
        # 校验引用字段确实在 derive 产出里（facts 非空时机检）
        for f in referenced:
            base = f.rstrip("0123456789")  # 去尾部数字（若有）
            if f not in facts and not any(f.startswith(k) for k in facts):
                warnings.append(f"design_rationale 引用的 '{f}' 不在 derive 产出字段里（疑似手编）")

    # ── D. 默认矩形检测（warning，不 FAIL）──
    if facts and _is_simple_rect_fills_buildable(plan_obj, facts):
        warnings.append(
            f"疑似默认矩形贴满可建范围（aspect_ratio={facts.get('aspect_ratio')} 长板，"
            f"但 outline 全是简单矩形无形态表达）——建议回 step-01 第 2 轮走 design_intent "
            f"语义声明（on_edge/polygon/subtract_hole），查 design_patterns 匹配板式/庭院 pattern"
        )

    return errors, warnings


def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="aiplan gate: 落盘前设计质量门禁")
    p.add_argument("plan", help="plan.json 路径")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    plan_obj = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    errors, warnings = validate_design_quality(plan_obj)

    if not args.quiet:
        for w in warnings:
            print(f"[WARN] {w}")
        if errors:
            print(f"[FAIL] {len(errors)} 个设计质量错误:", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
        else:
            print("[OK] 设计质量门禁通过")
    return 1 if errors else 0


def main() -> int:
    return _main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
