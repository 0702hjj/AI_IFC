"""validate_plan —— plan.json 落盘前 schema 门禁。

plan.json 的 schema 在本 skill 的 references/schemas/plan.schema.json（aiplan 自持副本，
本 skill 自包含——schema 即契约事实源）。

落盘管线顺序（implement.md P1）：schema 门禁 → canon → sha256 → 写盘。
本脚本是第一步：校验不过则拒绝落盘，绝不带病写盘。

用法：
    validate_plan.py plan.json            # 退出码 0=通过 1=有错（错误逐条打印）
    validate_plan.py plan.json --quiet    # 只看退出码
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

# schema 自持在本 skill 内（独立可迁移）
from aiplan_tools.paths import REFS

PLAN_SCHEMA = REFS / "schemas" / "plan.schema.json"


def validate(plan_obj, schema_path: Path | None = None) -> list[str]:
    """校验 plan_obj，返回错误消息列表（空=通过）。

    schema_path 默认指向本 skill 的 references/schemas/plan.schema.json。
    """
    sp = schema_path or PLAN_SCHEMA
    schema = json.loads(sp.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
            for e in sorted(validator.iter_errors(plan_obj), key=lambda e: list(e.path))]


def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="plan.json schema 门禁")
    p.add_argument("path", help="plan.json 路径")
    p.add_argument("--quiet", action="store_true", help="不打印错误细节")
    p.add_argument("--schema", help="覆盖 schema 路径")
    args = p.parse_args(argv)

    obj = json.loads(Path(args.path).read_text(encoding="utf-8"))
    sp = Path(args.schema) if args.schema else None
    errs = validate(obj, sp)
    if errs:
        if not args.quiet:
            print(f"[FAIL] {len(errs)} 个校验错误:", file=sys.stderr)
            for e in errs:
                print(f"  - {e}", file=sys.stderr)
        return 1
    if not args.quiet:
        print("[OK] plan.json 通过 schema 门禁")
    return 0



def main() -> int:
    """console_scripts 无参入口（setuptools 调用）。"""
    import sys
    return _main(sys.argv[1:])

if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
