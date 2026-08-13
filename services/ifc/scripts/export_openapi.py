# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Export the FastAPI app's OpenAPI schema to docs/site/public/ai-tools.openapi.json.

Run from services/ifc:

    uv run python scripts/export_openapi.py

Keeps docs/site/public/ai-tools.openapi.json in sync with the implementation by
construction: the schema comes from ``create_app().openapi()``, the same
object served at runtime by ``GET /openapi.json``.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app

OUT = Path(__file__).resolve().parents[3] / "docs" / "site" / "public" / "ai-tools.openapi.json"


def main() -> None:
    schema = create_app().openapi()
    OUT.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
