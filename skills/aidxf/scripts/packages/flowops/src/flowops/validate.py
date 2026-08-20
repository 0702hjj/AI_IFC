"""flowops/validate.py —— DSL 声明 schema 校验（质量防线 L1/L2 工具）。

纪律：调 references/schemas/ 的 JSON Schema（T02/T03 冻结件），
FAIL 返回结构化错误（exit 2 语义的 SchemaError 形态）。
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

_SCHEMAS_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent.parent.parent
    / "references" / "schemas"
)


class ValidationError(Exception):
    """声明非法（exit 2 语义）。"""

    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__(f"{len(errors)} schema 错误")


def _load_schema(name: str) -> dict:
    with open(_SCHEMAS_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def _validate_doc(doc: dict, schema_name: str) -> list[dict]:
    validator = Draft202012Validator(_load_schema(schema_name))
    errors = []
    for e in sorted(validator.iter_errors(doc), key=lambda e: ".".join(str(p) for p in e.absolute_path)):
        errors.append({
            "path": ".".join(str(p) for p in e.absolute_path),
            "message": e.message,
        })
    return errors


def validate_plan(plan: dict) -> list[dict]:
    """plan.json schema 校验（plan.schema.json v3.1 副本）。"""
    return _validate_doc(plan, "plan.schema.json")


def validate_skeleton(skeleton: dict) -> list[dict]:
    """skeleton.json schema 校验。"""
    return _validate_doc(skeleton, "skeleton.schema.json")


def validate_rooms(rooms: dict) -> list[dict]:
    """rooms.json schema 校验。"""
    return _validate_doc(rooms, "rooms.schema.json")


def validate_building(building: dict) -> list[dict]:
    """building.json schema 校验。"""
    return _validate_doc(building, "building.schema.json")


def assert_valid(doc: dict, schema_name: str) -> None:
    """校验并抛 ValidationError（exit 2 语义）。"""
    errors = _validate_doc(doc, schema_name)
    if errors:
        raise ValidationError(errors)
