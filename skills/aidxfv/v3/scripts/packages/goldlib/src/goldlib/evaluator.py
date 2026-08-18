"""goldlib/evaluator.py —— pattern 适用条件白名单求值器（T32，K2）。

纪律（learn_gold §4 K2）：适用条件全部用 geom 派生字段表达，机器可预筛。
**不引 eval/exec**——手写白名单求值，只支持字段比较 + and/or 组合。

条件形态（JSON）：
- {"field": value}                → facts[field] == value
- {"field_min": n} / {"field_max": n} → facts[field] >= n / <= n
- {"field_in": [a, b]}            → facts[field] in [a, b]
- {"or": [cond...]} / {"and": [cond...]} → 组合
"""

from __future__ import annotations


def _eval_atom(key: str, value, facts: dict) -> bool:
    if key == "or":
        return any(_eval_condition(c, facts) for c in value)
    if key == "and":
        return all(_eval_condition(c, facts) for c in value)
    if key.endswith("_min"):
        field = key[:-4]
        return facts.get(field, -1e18) >= value
    if key.endswith("_max"):
        field = key[:-4]
        return facts.get(field, 1e18) <= value
    if key.endswith("_in"):
        field = key[:-3]
        return facts.get(field) in value
    # 精确相等（含布尔/枚举）
    return facts.get(key) == value


def _eval_condition(cond, facts: dict) -> bool:
    if not isinstance(cond, dict):
        return False
    return all(_eval_atom(k, v, facts) for k, v in cond.items())


def evaluate_condition(condition: dict, facts: dict) -> bool:
    """适用条件对 geom_facts 求值。条件为空 → True（无限制）。"""
    if not condition:
        return True
    return _eval_condition(condition, facts)
