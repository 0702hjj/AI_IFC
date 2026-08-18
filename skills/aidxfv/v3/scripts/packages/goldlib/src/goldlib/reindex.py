"""goldlib/reindex.py —— 文件 → golden.db 重建（T31，幂等）。

纪律（learn_gold §6）：文件是事实源，DB 是可重建派生物（永不手改）。
四表：cases/patterns/evidence/params。
幂等：同输入同输出（全量重建，不增量）。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    type TEXT,
    area_sqm REAL,
    shape_tags TEXT,
    quality_score REAL,
    template_worthy INTEGER,
    path TEXT,
    skeleton_dsl TEXT
);
CREATE TABLE IF NOT EXISTS patterns (
    pattern_id TEXT PRIMARY KEY,
    kind TEXT,
    topic_file TEXT,
    pains TEXT,
    conditions TEXT,
    support INTEGER DEFAULT 1,
    path TEXT
);
CREATE TABLE IF NOT EXISTS evidence (
    pattern_id TEXT,
    case_id TEXT,
    at_path TEXT,
    PRIMARY KEY (pattern_id, case_id)
);
CREATE TABLE IF NOT EXISTS params (
    pattern_id TEXT,
    key TEXT,
    min REAL,
    max REAL,
    PRIMARY KEY (pattern_id, key)
);
"""


def _scan_cases(gold_dir: Path) -> list[dict]:
    """扫描 golden 下案例 meta.json → cases 行。

    兼容结构：`<case_id>/meta.json`（测试夹具）、`<type>/<case_id>/meta.json`，
    以及生产结构 `golden/<type>/<case_id>/meta.json`（gold_dir=references/ 时，
    2026-08-12 住宅楼 res_2s4u_std 入库发现漏扫修复）。
    **跳过 _quarantine/**（隔离区永不注入/永不检索，learn_gold 纪律）。
    2026-08-11：案例的 skeleton_dsl 从同目录 `skeleton.json` 读（该案例骨架的 DSL 封装）。
    """
    out = []
    candidates = (sorted(gold_dir.glob("*/*/meta.json"))
                  + sorted(gold_dir.glob("*/meta.json")))
    # 生产结构：references/golden/<type>/<case_id>/meta.json（三层）
    golden_sub = gold_dir / "golden"
    if golden_sub.exists():
        candidates += (sorted(golden_sub.glob("*/*/meta.json"))
                       + sorted(golden_sub.glob("*/meta.json")))
    for meta_path in sorted(set(candidates)):
        rel = meta_path.relative_to(gold_dir)
        if "_quarantine" in rel.parts:
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        # skeleton_dsl：同目录 skeleton.json（案例骨架 DSL 封装，LLM 学习对象）
        skeleton_dsl = None
        sk_path = meta_path.parent / "skeleton.json"
        if sk_path.exists():
            try:
                skeleton_dsl = sk_path.read_text(encoding="utf-8")
            except Exception:
                skeleton_dsl = None
        out.append({
            "case_id": meta.get("case_id", meta_path.parent.name),
            "type": meta.get("type", "unknown"),
            "area_sqm": meta.get("area_sqm"),
            "shape_tags": json.dumps(meta.get("shape_tags", []), ensure_ascii=False),
            "quality_score": meta.get("quality_score"),
            "template_worthy": int(bool(meta.get("template_worthy", False))),
            "path": str(meta_path),
            "skeleton_dsl": skeleton_dsl,
            # evidence 链源（learn_gold §5：案例 implements → pattern 出处）
            "implements": meta.get("implements", []),
        })
    return out


def _scan_patterns(gold_dir: Path) -> list[dict]:
    """扫描 building_types/*/skeleton_patterns.md + room_patterns/*.md → patterns 行。

    pattern 条目 = markdown 中以 `## pattern:` 开头的块，头部元数据为
    `命中痛点: P1-x` 等行。
    """
    out = []
    candidates = []
    bt_dir = gold_dir / "building_types"
    rp_dir = gold_dir / "room_patterns"
    if bt_dir.exists():
        candidates.extend(bt_dir.glob("*/skeleton_patterns.md"))
    if rp_dir.exists():
        candidates.extend(rp_dir.glob("*.md"))
    for path in sorted(candidates):
        if not path.exists():
            continue
        # 按目录区分 kind：building_types/*/skeleton_patterns.md → skeleton；room_patterns/*.md → room
        kind = "room" if str(path).replace("\\", "/").endswith("room_patterns/") or (
            "room_patterns" in str(path).replace("\\", "/")) else "skeleton"
        content = path.read_text(encoding="utf-8")
        for block in _parse_pattern_blocks(content):
            block["kind"] = kind
            block["path"] = str(path)
            out.append(block)
    return out


def _parse_pattern_blocks(content: str) -> list[dict]:
    """从 markdown 解析 `## pattern:` 块。返回 [{pattern_id, kind, pains, ...}]。"""
    blocks = []
    current = None
    for line in content.splitlines():
        if line.startswith("## pattern:"):
            if current:
                blocks.append(current)
            current = {"pattern_id": line.split(":", 1)[1].strip(),
                       "pains": "", "topic_file": "", "conditions": "{}"}
        elif current is not None:
            if line.startswith("命中痛点:"):
                current["pains"] = line.split(":", 1)[1].strip()
            elif line.startswith("适用房间:"):
                current["topic_file"] = line.split(":", 1)[1].strip()
            elif line.startswith("适用条件:"):
                cond_raw = line.split(":", 1)[1].strip()
                current["conditions"] = cond_raw
    if current:
        blocks.append(current)
    return blocks


def reindex(gold_dir: str, db_path: str) -> None:
    """全量重建 golden.db。

    :param gold_dir: references/ 目录（含 golden/ + building_types/ + room_patterns/）
    :param db_path: 输出 golden.db 路径
    """
    root = Path(gold_dir)
    db = Path(db_path)
    db.parent.mkdir(parents=True, exist_ok=True)

    # 同步再生 index.json（机器再生，检索索引）
    from goldlib.schema import build_index, validate_index
    index = build_index(str(root))
    if validate_index(index) == []:
        index_path = root / "index.json"
        index_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # 幂等（字节级确定）：删旧文件全新创建——DELETE 复用旧页碎片会导致字节不定
    if db.exists():
        db.unlink()

    conn = sqlite3.connect(db)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.execute("DELETE FROM cases")
        conn.execute("DELETE FROM patterns")
        conn.execute("DELETE FROM evidence")
        conn.execute("DELETE FROM params")

        for c in _scan_cases(root):
            conn.execute(
                "INSERT INTO cases (case_id,type,area_sqm,shape_tags,quality_score,"
                "template_worthy,path,skeleton_dsl) VALUES (?,?,?,?,?,?,?,?)",
                (c["case_id"], c["type"], c["area_sqm"], c["shape_tags"],
                 c["quality_score"], c["template_worthy"], c["path"], c["skeleton_dsl"]),
            )
        for p in _scan_patterns(root):
            conn.execute(
                "INSERT INTO patterns (pattern_id,kind,topic_file,pains,conditions,"
                "support,path) VALUES (?,?,?,?,?,?,?)",
                (p["pattern_id"], p.get("kind", "skeleton"), p.get("topic_file", ""),
                 p.get("pains", ""), p.get("conditions", ""), 1, p["path"]),
            )
        # evidence 双向链（learn_gold §5）：case.implements ↔ pattern（出处可溯）
        for c in _scan_cases(root):
            for pid in c["implements"] or []:
                conn.execute(
                    "INSERT OR IGNORE INTO evidence (pattern_id, case_id, at_path) "
                    "VALUES (?,?,?)",
                    (pid, c["case_id"], "meta.json#implements"),
                )
        conn.commit()
    finally:
        conn.close()
