"""bim_supplement_lint —— bim_supplement.json 语义校验（schema 拦不住的三类）。

schema（bim_supplement.schema.json）拦硬约束（类型/枚举/值域/必填）；
本模块拦 schema 表达不了的语义规则（契约 §7 备注）：

- N-09 type↔字段配对：每个 special_structures 元素的 type 决定哪些字段必填
  （当前仅 massing_twist 必填 twist_deg；其余 type 契约标"全字段可选"）
- N-11 规范常识下限：required_headroom_mm 等"有规范下限"的字段低于常识值
- N-12 同 type 去重：special_structures 数组里同一 type 只允许出现一次

单一实现纪律（D-6 同款教训）：本函数是落盘门禁（validate_bim_supplement.py）
与测试（test_bim_supplement.py）的共用底座，**不双实现**——测试 import 本模块。
"""

from __future__ import annotations

# N-09: type → 必填字段（契约 02_roof_special_geometry §2.3 + §3 取舍）
REQUIRED_FIELDS_BY_TYPE: dict[str, list[str]] = {
    "massing_twist": ["twist_deg"],
    # parapet/balcony/atrium/massing_mirror: 契约标"全字段可选"，无必填
}

# N-11: 有规范常识下限的字段（键路径 → 下限值）
COMMON_SENSE_MIN: dict[str, float] = {
    "psets.*.required_headroom_mm": 1000,  # 净空常识下限 1m
}


def lint(doc) -> list[str]:
    """语义校验，返回错误描述列表（空=通过）。

    纯函数，确定性：同输入同输出。不抛异常，全部错误收集后返回。
    """
    errs: list[str] = []

    # N-09: type↔必填字段配对
    for i, s in enumerate(doc.get("special_structures", [])):
        t = s.get("type", "?")
        for field in REQUIRED_FIELDS_BY_TYPE.get(t, []):
            if field not in s:
                errs.append(f"special_structures[{i}] type={t} 缺必填字段 {field}")

    # N-11: 规范常识下限
    for section, val in doc.get("psets", {}).items():
        if not isinstance(val, dict):
            continue
        for k, v in val.items():
            if k == "required_headroom_mm" and isinstance(v, (int, float)) and v < 1000:
                errs.append(f"psets.{section}.required_headroom_mm={v} < 1000 违反规范常识下限")

    # N-12: 同 type 去重
    types = [s.get("type") for s in doc.get("special_structures", [])]
    seen: set[str] = set()
    for t in types:
        if t in seen:
            errs.append(f"special_structures 同 type 重复: {t}")
        seen.add(t)

    return errs


def is_valid(doc) -> bool:
    """便捷：lint 通过返回 True。"""
    return not lint(doc)
