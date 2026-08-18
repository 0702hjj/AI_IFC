"""validate_intent —— design_intent.json schema 门禁（P1 迁移）。

design_intent.json 的 schema 在 references/schemas/design_intent.schema.json（aiplan 自持）。
校验语义层封闭词表：5 种 form（oneOf 锁死）+ 8 方位 + region 枚举。

用法：
    validate_intent.py design_intent.json            # 退出码 0=通过 1=有错
    validate_intent.py design_intent.json --quiet
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from aiplan_tools.paths import REFS

INTENT_SCHEMA = REFS / "schemas" / "design_intent.schema.json"


def validate(intent_obj, schema_path: Path | None = None) -> list[str]:
    """校验 design_intent_obj，返回错误消息列表（空=通过）。"""
    sp = schema_path or INTENT_SCHEMA
    schema = json.loads(sp.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
            for e in sorted(validator.iter_errors(intent_obj), key=lambda e: list(e.path))]


def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="design_intent.json schema 门禁")
    p.add_argument("path", help="design_intent.json 路径")
    p.add_argument("--quiet", action="store_true")
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
        print("[OK] design_intent.json 通过 schema 门禁")
    return 0


def main() -> int:
    return _main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
