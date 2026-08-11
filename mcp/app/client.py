# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Thin REST client for the platform edit-service (default http://127.0.0.1:8100)."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx


class EditServiceError(RuntimeError):
    """edit-service returned an error status; carries status + detail."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"edit-service {status}: {detail}")
        self.status = status
        self.detail = detail


class EditServiceClient:
    def __init__(
        self, base_url: str, transport: Optional[httpx.BaseTransport] = None
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url, transport=transport, timeout=60.0
        )

    def _request(
        self, method: str, path: str, allow_404: bool = False, **kwargs: Any
    ) -> Any:
        resp = self._http.request(method, path, **kwargs)
        if allow_404 and resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            try:
                detail = str(resp.json().get("detail", resp.text))
            except ValueError:
                detail = resp.text
            raise EditServiceError(resp.status_code, detail)
        return resp.json()

    def diff_upload(self, model_id: str, ifc_path: str) -> Dict[str, Any]:
        with open(ifc_path, "rb") as fh:
            files = {
                "file": (os.path.basename(ifc_path), fh, "application/octet-stream")
            }
            return self._request(
                "POST", f"/models/{model_id}/diff/upload", files=files
            )

    def post_user_edits(
        self,
        model_id: str,
        origin: str,
        events: List[Dict[str, Any]],
        author: str = "user-upload",
    ) -> Dict[str, Any]:
        return self._request(
            "POST",
            f"/models/{model_id}/user-edits",
            json={"origin": origin, "author": author, "events": events},
        )

    def versions(self, model_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/models/{model_id}/versions")

    def scripts(self, model_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/models/{model_id}/scripts")

    def diff(self, model_id: str, base: str, target: str) -> Dict[str, Any]:
        return self._request(
            "POST", f"/models/{model_id}/diff", json={"base": base, "target": target}
        )

    def script_diff(
        self, model_id: str, base: str, target: str
    ) -> Optional[Dict[str, Any]]:
        return self._request(
            "POST",
            f"/models/{model_id}/script/diff",
            json={"base": base, "target": target},
            allow_404=True,
        )

    def get_script(self, model_id: str) -> Optional[Dict[str, Any]]:
        return self._request("GET", f"/models/{model_id}/script", allow_404=True)

    def history(self, model_id: str) -> List[Dict[str, Any]]:
        return self._request("GET", f"/models/{model_id}/history")
