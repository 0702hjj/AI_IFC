"""validate_bim_supplement —— bim_supplement.json 双门禁（schema + 语义）。

落盘管线（implement.md P2.2）：schema 门禁（bim_supplement.schema.json）
+ 语义门禁（bim_supplement_lint.py）→ 两者都过才允许落盘。

与 validate_plan.py 对称（plan.json 用 schema 单门禁；bim_supplement 多一层语义）。

用法：
    validate_bim_supplement.py bim_supplement.json     # 退出码 0=通过 1=有错
    validate_bim_supplement.py bim_supplement.json --quiet
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from aiplan_tools.paths import REFS
from aiplan_tools import bim_supplement_lint  # noqa: E402

SCHEMA = REFS / "schemas" / "bim_supplement.schema.json"


def validate(doc, schema_path: Path | None = None) -> list[str]:
    """双门禁校验，返回错误消息列表（空=通过）。

    schema_path 默认指向 aiplan/references/schemas/bim_supplement.schema.json。
    """
    sp = schema_path or SCHEMA
    schema = json.loads(sp.read_text(encoding="utf-8"))
    schema_errs = [
        f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
        for e in sorted(Draft202012Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    ]
    sem_errs = [f"语义: {e}" for e in bim_supplement_lint.lint(doc)]
    return schema_errs + sem_errs


def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="bim_supplement.json 双门禁（schema + 语义）")
    p.add_argument("path", help="bim_supplement.json 路径")
    p.add_argument("--quiet", action="store_true", help="不打印错误细节")
    p.add_argument("--schema", help="覆盖 schema 路径")
    args = p.parse_args(argv)

    doc = json.loads(Path(args.path).read_text(encoding="utf-8"))
    sp = Path(args.schema) if args.schema else None
    errs = validate(doc, sp)
    if errs:
        if not args.quiet:
            print(f"[FAIL] {len(errs)} 个校验错误:", file=sys.stderr)
            for e in errs:
                print(f"  - {e}", file=sys.stderr)
        return 1
    if not args.quiet:
        print("[OK] bim_supplement.json 通过双门禁")
    return 0



def main() -> int:
    """console_scripts 无参入口（setuptools 调用）。"""
    import sys
    return _main(sys.argv[1:])

if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
