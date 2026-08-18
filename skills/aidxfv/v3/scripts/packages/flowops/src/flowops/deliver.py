"""flowops/deliver.py —— confirmed 层封存 + building.json（T44，V2 building 迁移）。

纪律（filestructure PART B）：deliver/ 含 <floor>.dxf + <floor>.rooms.json + building.json。
building.json 继承 V2 S4 形态：floors/doors/metadata/checksums。
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _collect_confirmed_missions(project_dir: Path) -> list[dict]:
    """扫 missions/<node>/ 收集 confirmed 层产物（floor.dxf + rooms.json 都在）。"""
    out = []
    missions_dir = project_dir / "missions"
    if not missions_dir.exists():
        return out
    for mission_dir in sorted(missions_dir.iterdir()):
        if not mission_dir.is_dir():
            continue
        dxf = mission_dir / "floor.dxf"
        rooms = mission_dir / "rooms.json"
        if dxf.exists() and rooms.exists():
            out.append({
                "node": mission_dir.name,
                "floor": mission_dir.name.split(".")[0],
                "dxf": dxf,
                "rooms": rooms,
            })
    return out


def deliver(project_name: str, project_dir: str, deliver_dir: str | None = None) -> dict:
    """confirmed 层封存 + building.json。

    :param project_name: 项目名（building.project）
    :param project_dir: 项目工作目录（含 missions/）
    :param deliver_dir: deliver/ 输出目录（缺省 <project_dir>/deliver）
    :return: building.json dict
    """
    project = Path(project_dir)
    out = Path(deliver_dir) if deliver_dir else project / "deliver"
    out.mkdir(parents=True, exist_ok=True)

    floors = []
    checksums = {}
    for m in _collect_confirmed_missions(project):
        floor = m["floor"]
        # 封存 DXF
        dxf_name = f"{floor}.dxf"
        shutil.copy2(m["dxf"], out / dxf_name)
        dxf_sha = _sha256_bytes(m["dxf"].read_bytes())
        checksums[dxf_name] = dxf_sha
        # 封存 rooms（<floor>.rooms.json，楼层扩展信息保留在封存文件里）
        rooms_name = f"{floor}.rooms.json"
        shutil.copy2(m["rooms"], out / rooms_name)
        # floor 条目（继承 V2 S4，遵守 building.schema 契约）
        floors.append({
            "floor": floor,
            "elevation_mm": 0,
            "height_mm": 3000,
            "dxf": dxf_name,
            "sha256": dxf_sha,
        })

    building = {
        "version": 1,
        "project": project_name,
        "metadata": {
            "generated_at": "2026-08-10T00:00:00Z",
            "by": "aidxfv3",
        },
        "floors": floors,
        "doors": [],  # 门表由 S3 details 汇总（T44 骨架）
        "checksums": checksums,
    }
    (out / "building.json").write_text(
        json.dumps(building, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return building
