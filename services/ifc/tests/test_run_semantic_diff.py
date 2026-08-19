# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""run 响应附构件级语义 diff 计数（``semanticDiff``）。

``POST /models/{id}/script/run`` 成功后在响应里附带旧 uploads 产物 vs 本次
run 产物的构件级 ``{added, removed, changed}`` 计数（既有 diffing 引擎），
AI 自纠看构件增减而非脚本文本行数。容错纪律照抄 ``_bootstrap_alignment``：
diff 失败/无旧产物 → ``semanticDiff=None``，绝不让已成功的 run 失败。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import diffing
from tests.conftest import MODEL_ID

WALL_SCRIPT = '''\
import sys

import ifcopenshell

from script_lib import create_entity, create_skeleton, write_and_validate

PARAMS = {{"key": "{key}"}}

def build(params, out_path):
    model = ifcopenshell.file(schema="IFC4")
    body, _ = create_skeleton(model)
    w = create_entity(model, "IfcWall", key=params["key"], name="W1")
    write_and_validate(model, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''


def _wall_script(key: str = "s1:wall:1") -> str:
    return WALL_SCRIPT.format(key=key)


def _stage_and_run(client: TestClient, script: str):
    r = client.put(f"/models/{MODEL_ID}/script", json={"script": script})
    assert r.status_code == 200, r.text
    return client.post(f"/models/{MODEL_ID}/script/run")


class TestRunSemanticDiff:
    def test_first_run_returns_semantic_diff_counts(self, client: TestClient):
        """首次 run：旧产物为上传原件，与生成产物 GlobalId 不重叠。"""
        r = _stage_and_run(client, _wall_script())
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["modelId"] == MODEL_ID
        assert body["ok"] is True
        diff = body["semanticDiff"]
        assert set(diff) == {"added", "removed", "changed"}
        assert all(isinstance(diff[k], int) for k in diff)
        assert diff["added"] >= 1
        assert diff["removed"] >= 1
        assert diff["changed"] == 0

    def test_second_run_diffs_against_previous_run(self, client: TestClient):
        """第二次 run：基线是上一次 run 的产物（同 key 构件对齐）。"""
        r = _stage_and_run(client, _wall_script("s1:wall:1"))
        assert r.status_code == 200, r.text
        r = _stage_and_run(client, _wall_script("s1:wall:2"))
        assert r.status_code == 200, r.text
        diff = r.json()["semanticDiff"]
        assert diff is not None
        # key 变化 → 旧墙 removed、新墙 added；骨架构件 GlobalId 稳定不对齐
        # 与否只影响计数大小，不断言精确值，只断言确有构件增减。
        assert diff["added"] >= 1
        assert diff["removed"] >= 1

    def test_diff_failure_degrades_to_none(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        """diff 引擎爆炸 → semanticDiff=None，run 本身仍 200（容错纪律）。"""

        def _boom(old_path: str, new_path: str) -> dict:
            raise RuntimeError("ifcdiff exploded")

        monkeypatch.setattr(diffing, "compute_diff", _boom)
        r = _stage_and_run(client, _wall_script())
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["semanticDiff"] is None
