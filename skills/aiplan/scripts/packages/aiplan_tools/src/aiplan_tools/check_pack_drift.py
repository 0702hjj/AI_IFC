"""check_pack_drift —— 类型包 .md ↔ .rules.json 同源漂移检查。

aiplan 的 building_types 是本 skill 自持的（自包含纪律——
两个独立 skill 各自维护一份，"同一套"是部署约定，不是运行时依赖）。

本脚本检查 aiplan **内部**每个类型包的 .md 与 .rules.json 是否同源：
- .rules.json 的每条规则用 canonical_rule 规范化为字符串
- .md 表格内以反引号嵌入同一字符串
- 两边规则集不一致 → 报漂移（改 json 不改 md 或反之）

canonical_rule 为本 skill 自持实现（规范化逻辑事实源）。

用法：
    check_pack_drift.py                  # 检查全部双写包
    check_pack_drift.py residence office # 只查指定包
退出码：0=无漂移 1=有漂移（逐条打印）
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from aiplan_tools.paths import BUILDING_TYPES

PACKS = BUILDING_TYPES


def canonical_rule(rule: dict) -> str:
    """规则实例规范化字符串（本 skill 自持实现，即事实源）。

    形如 `hub_connect(hub=living,members=bathroom.*,bedroom.*,kitchen)[must]`
    （list 参数排序逗号连接，kwargs 按键排序，空白全去除）。
    """
    parts = []
    for key in sorted(rule["args"]):
        val = rule["args"][key]
        if isinstance(val, list):
            val = ",".join(sorted(str(v) for v in val))
        parts.append(f"{key}={val}")
    return f"{rule['predicate']}({';'.join(parts)})[{rule['strength']}]"


_MD_RULE_RE = re.compile(r"`(\w+\([^`]+\)\[(?:must|prefer|avoid)\])`")


def check_drift(md_path: Path, json_path: Path) -> list[str]:
    """比对 .md 内嵌规范化规则与 .rules.json，返回漂移描述列表（空=无漂移）。"""
    md_text = md_path.read_text(encoding="utf-8")
    pack = json.loads(json_path.read_text(encoding="utf-8"))
    md_rules = set(_MD_RULE_RE.findall(md_text))
    json_rules = {canonical_rule(r) for r in pack.get("rules", [])}
    drifts = [f"json 有 md 无: {r}" for r in sorted(json_rules - md_rules)]
    drifts += [f"md 有 json 无: {r}" for r in sorted(md_rules - json_rules)]
    return drifts


def check_pack(name: str, packs_dir: Path = PACKS) -> list[str]:
    """检查单个类型包的 .md ↔ .rules.json 同源，返回漂移列表（空=一致）。"""
    md = packs_dir / f"{name}.md"
    js = packs_dir / f"{name}.rules.json"
    if not js.exists():
        return []  # 无 .rules.json 的包（如 retail 只有 .md）不查
    if not md.exists():
        return [f"{name}: .md 缺失（有 .rules.json 但无 .md）"]
    return check_drift(md, js)


def check_all(packs_dir: Path = PACKS) -> dict[str, list[str]]:
    """检查全部双写包（有 .rules.json 的），返回 {包名: 漂移列表}。"""
    names = sorted(p.stem.replace(".rules", "") for p in packs_dir.glob("*.rules.json"))
    return {n: check_pack(n, packs_dir) for n in names}


def _main(argv: list[str]) -> int:
    packs = PACKS
    names = argv or sorted(p.stem.replace(".rules", "") for p in packs.glob("*.rules.json"))
    failed = False
    for name in names:
        drifts = check_pack(name, packs)
        if drifts:
            failed = True
            print(f"[DRIFT] {name}:")
            for d in drifts:
                print(f"  - {d}")
        else:
            print(f"[OK] {name}")
    return 1 if failed else 0



def main() -> int:
    """console_scripts 无参入口（setuptools 调用）。"""
    import sys
    return _main(sys.argv[1:])

if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
