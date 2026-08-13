# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Render payload endpoint (W-0039): GET /models/{id}/render.json.

已发布的 render.json（run/save 钩子原子写入，与 uploads dxf 同内容代）
直接读文件返回；未发布（upload-only 模型/老数据）时按 uploads dxf 即时
生成——纯读端点，不落盘。模型缺失（route_common）与生成失败 → 404，
raise 只住 verify* 函数（test_verify_isolation 机器强制，ALLOWLIST 空）。
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Path, Request

from . import render
from .route_common import MODEL_ID_PATTERN, model_upload_path

router = APIRouter()


def verify_render_payload(request: Request, model_id: str) -> Dict[str, Any]:
    """render.json 必须可取（已发布读文件 / 未发布即时生成）。

    404 的唯一翻译点：模型缺失（model_upload_path）或 payload 生成失败
    （DXF 不可解析等）。已发布文件损坏时降级为即时生成，绝不对损坏
    sidecar 500。
    """
    dxf_path = model_upload_path(request, model_id)
    render_path = os.path.join(
        request.app.state.settings.data_dir, "models", model_id, "render.json"
    )
    if os.path.isfile(render_path):
        try:
            with open(render_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            if isinstance(payload, dict):
                return payload
        except (OSError, ValueError):
            pass
    try:
        return render.build_render_payload(dxf_path)
    except Exception as exc:
        raise HTTPException(
            status_code=404, detail=f"render payload unavailable: {exc}"
        )


@router.get("/models/{id}/render.json")
def get_render_json(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Return the model's render payload v2 (entity-keyed geometry JSON)."""
    return verify_render_payload(request, id)
