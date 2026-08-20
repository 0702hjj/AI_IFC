"""goldlib/schema.py —— golden 目录元信息内部校验（T30）。

不放 JSON Schema 重型化；常量 + 校验函数。
"""

from __future__ import annotations

META_REQUIRED = {"case_id", "type", "quality_score", "template_worthy"}
REPLAY_REQUIRED = {"status"}


def validate_meta(meta: dict) -> list[str]:
    """meta.json 校验，返回违规列表（空=通过）。"""
    errs = []
    for k in META_REQUIRED:
        if k not in meta:
            errs.append(f"meta 缺 {k}")
    if "case_id" in meta and not isinstance(meta["case_id"], str):
        errs.append("case_id 必须是字符串")
    if "quality_score" in meta and not (0 <= float(meta["quality_score"]) <= 1):
        errs.append("quality_score 应在 [0,1]")
    return errs


def validate_replay(replay: dict) -> list[str]:
    """replay_check.json 校验（G2 闸门产物）。"""
    errs = []
    if replay.get("status") not in ("PASS", "FAIL"):
        errs.append("replay status 必须是 PASS/FAIL")
    return errs


def validate_index(index: dict) -> list[str]:
    """index.json 校验（golden 检索索引）。"""
    errs = []
    if not isinstance(index.get("cases"), list):
        errs.append("index 缺 cases 列表")
    for c in index.get("cases", []):
        if "case_id" not in c:
            errs.append("index case 缺 case_id")
    return errs


def build_index(gold_dir: str) -> dict:
    """从 golden 目录生成 index.json（机器再生，检索索引）。

    兼容生产结构 `golden/<type>/<case_id>/meta.json`（三层，
    2026-08-12 住宅楼入库发现漏扫修复）与扁平结构 `<case_id>/meta.json`。
    """
    from pathlib import Path
    root = Path(gold_dir)
    cases = []
    candidates = (sorted(root.glob("*/*/meta.json")) + sorted(root.glob("*/meta.json")))
    golden_sub = root / "golden"
    if golden_sub.exists():
        candidates += (sorted(golden_sub.glob("*/*/meta.json"))
                       + sorted(golden_sub.glob("*/meta.json")))
    for meta_path in sorted(set(candidates)):
        if "_quarantine" in meta_path.parts:
            continue
        try:
            import json
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            cases.append({
                "case_id": meta.get("case_id", meta_path.parent.name),
                "type": meta.get("type", "unknown"),
                "quality_score": meta.get("quality_score"),
                "template_worthy": bool(meta.get("template_worthy", False)),
                "path": str(meta_path),
            })
        except Exception:
            continue
    return {"cases": cases}
