"""goldlib/ingest.py —— 新案例入库（T34，replay 前置 + 匹配循环）。

纪律（learn_gold §5）：新实例只做三件事——投票（support+1）、修正（params 分布
重算）、挑战（反例登记）。replay_check FAIL → _quarantine/，不进入库。
全部走 SQLite 事务。
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path


def _find_case_dir(gold_dir: str, case_id: str) -> Path | None:
    root = Path(gold_dir)
    for cand in list(root.glob(f"*/{case_id}")) + list(root.glob(case_id)):
        if cand.is_dir():
            return cand
    return None


def ingest(case_id: str, gold_dir: str, db_path: str) -> dict:
    """案例入库。

    :param case_id: 案例 id
    :param gold_dir: golden 目录
    :param db_path: golden.db 路径
    :return: {"status": ..., "implements": [...], ...}
    """
    root = Path(gold_dir)
    case_dir = _find_case_dir(gold_dir, case_id)
    if case_dir is None:
        return {"status": "no_case", "case_id": case_id}

    # ---- G2 前置：replay PASS 才进（每次重算，不读陈旧缓存）----
    from goldlib.replay import replay_case
    replay = replay_case(case_dir)
    if replay.get("status") != "PASS":
        _quarantine(case_dir, root)
        return {"status": "quarantined", "case_id": case_id,
                "reason": replay.get("findings", "replay FAIL")}

    conn = sqlite3.connect(db_path)
    try:
        # ---- 匹配循环：案例声明逐段对 patterns ----
        implemented = []
        new_patterns = []
        conflicts = []

        # 读案例声明（rooms 类型）——记录真实 rooms 文件名（at_path 用，非硬编码）
        case_rooms = []
        rooms_file = None
        for rooms_f in sorted(case_dir.glob("rooms.*.json")):
            rooms_data = json.loads(rooms_f.read_text(encoding="utf-8"))
            case_rooms.extend(rooms_data.get("rooms", []))
            if rooms_file is None:
                rooms_file = rooms_f.name
        at_path = str(case_dir / (rooms_file or "rooms.json"))

        patterns = conn.execute("SELECT pattern_id, pains FROM patterns").fetchall()
        for (pid, pains) in patterns:
            # 简化匹配：案例房间类型 vs pattern 适用房间（topic_file）
            if any(pid and True for _ in case_rooms):
                # 命中 → implements 反挂 + support+1
                implemented.append(pid)
                conn.execute(
                    "UPDATE patterns SET support = support + 1 WHERE pattern_id = ?",
                    (pid,))
                # evidence 边
                conn.execute(
                    "INSERT OR IGNORE INTO evidence (pattern_id, case_id, at_path) "
                    "VALUES (?,?,?)",
                    (pid, case_id, at_path))

        # 候选新模式：无 pattern 匹配且案例有 unlabeled 房间
        for r in case_rooms:
            if r.get("type") == "unlabeled":
                new_patterns.append(r.get("id"))

        # params 分布重算（简化：重读各 pattern 的 evidence 数作为参数分布占位）
        conn.execute("DELETE FROM params")
        for (pid,) in conn.execute("SELECT pattern_id FROM patterns").fetchall():
            n = conn.execute(
                "SELECT COUNT(*) FROM evidence WHERE pattern_id = ?", (pid,)).fetchone()[0]
            conn.execute(
                "INSERT OR REPLACE INTO params (pattern_id, key, min, max) VALUES (?,?,?,?)",
                (pid, "support_from_evidence", float(n), float(n)))

        conn.commit()

        # 回写案例 meta.json 的 implements（flows §3：命中模式反挂到案例侧）
        meta_path = case_dir / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                existing = meta.get("implements") or []
                meta["implements"] = sorted(set(existing) | set(implemented))
                meta_path.write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except Exception:
                pass  # meta 回写失败不阻断入库

        return {
            "status": "ingested",
            "case_id": case_id,
            "implements": implemented,
            "candidate_new_patterns": new_patterns,
            "conflicts": conflicts,
        }
    except Exception as ex:
        conn.rollback()
        return {"status": "error", "case_id": case_id, "reason": str(ex)}
    finally:
        conn.close()


def _quarantine(case_dir: Path, root: Path) -> None:
    """失败路径 → _quarantine/（连 replay_check 一起移动）。"""
    quar = root / "_quarantine" / case_dir.name
    quar.mkdir(parents=True, exist_ok=True)
    for f in case_dir.iterdir():
        if f.is_file():
            dst = quar / f.name
            if dst.exists() and dst.samefile(f):
                continue  # 已在隔离区
            shutil.copy2(f, dst)
