"""goldlib/query.py —— 特征直查（T32，pull 模式）。

纪律（learn_gold §6）：正文永远从文件锚点取，DB 只存索引。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def query(db_path: str, kind: str = "case", pain: str | None = None,
          geom_facts: dict | None = None, rooms: list | None = None,
          type: str | None = None) -> list[dict]:
    """特征直查。

    :param db_path: golden.db 路径
    :param kind: "case"（金例）/ "pattern"（模式）
    :param pain: 痛点编号（P1-x / P2-x）
    :param geom_facts: 派生事实（适用条件求值预筛，K2）
    :param rooms: 房间语义（未用）
    :param type: 类型桶（residence/office/retail）
    :return: 命中列表（正文从文件锚点取）
    """
    conn = sqlite3.connect(db_path)
    try:
        if kind == "case":
            rows = conn.execute(
                "SELECT case_id,type,quality_score,template_worthy,path,skeleton_dsl FROM cases"
                + (" WHERE type=?" if type else ""),
                ((type,) if type else ()),
            ).fetchall()
            out = []
            for case_id, ctype, qs, tw, path, sk_dsl in rows:
                item = {
                    "case_id": case_id, "type": ctype,
                    "quality_score": qs, "template_worthy": bool(tw),
                }
                # 正文（meta）从文件锚点取
                meta_path = Path(path)
                if meta_path.exists():
                    try:
                        item["meta"] = json.loads(
                            meta_path.read_text(encoding="utf-8"))
                    except Exception:
                        item["meta"] = {}
                # skeleton_dsl：该案例骨架的 DSL 封装（LLM 学习对象）
                if sk_dsl:
                    try:
                        item["skeleton_dsl"] = json.loads(sk_dsl)
                    except Exception:
                        item["skeleton_dsl"] = sk_dsl
                out.append(item)
            return out

        elif kind == "pattern":
            if pain:
                rows = conn.execute(
                    "SELECT pattern_id,kind,pains,conditions,support,path FROM patterns "
                    "WHERE pains LIKE ?", (f"%{pain}%",)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT pattern_id,kind,pains,conditions,support,path FROM patterns").fetchall()
            from goldlib.evaluator import evaluate_condition
            out = []
            for pid, pkind, pains, conditions, support, path in rows:
                # 适用条件预筛（K2）：geom_facts 命中才返回
                if geom_facts is not None:
                    try:
                        cond = json.loads(conditions) if conditions else {}
                    except Exception:
                        cond = {}
                    if not evaluate_condition(cond, geom_facts):
                        continue
                item = {
                    "pattern_id": pid, "kind": pkind,
                    "pains": pains, "support": support,
                }
                if support <= 1:
                    item["note"] = "[孤证]"
                # 正文片段从文件锚点取（DB 只存指针）
                item["source"] = path
                out.append(item)
            return out
        return []
    finally:
        conn.close()
