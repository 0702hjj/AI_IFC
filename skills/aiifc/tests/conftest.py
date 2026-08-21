"""aiifc tests conftest——注入 aiifc 包 + aidxf dxfkit/archdxf（consume_upstream 的 DXF 读取依赖）。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # skills/aiifc
REPO = ROOT.parent.parent                            # repo root

# aiifc 包（scripts/aiifc）
sys.path.insert(0, str(ROOT / "scripts" / "aiifc"))
# aidxf dxfkit/archdxf（consume_upstream 的 DXF outline 读取依赖——dist 单一事实源）
for pkg in ("dxfkit", "archdxf"):
    p = REPO / "skills" / "dist" / "aidxf" / "scripts" / "packages" / pkg / "src"
    if p.is_dir():
        sys.path.insert(0, str(p))
