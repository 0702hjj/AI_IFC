# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""edit-call 端点与 script_edit 标量重写。

- ``script_edit.rewrite_call_argument``：libcst 无损重写指定行的调用参数
  （仅标量字面量；表达式/容器注入 → ValueError；无调用行/语法错误 → ValueError）。
- ``POST /models/{id}/script/edit-call``：designKey → current.map.json 定位
  → 重写 → 沙箱 run → staging.push。任何失败 422 且零副作用；
  origin=traced → 422（不可自动改写）；designKey 未定位 → 404。
"""

from __future__ import annotations

import json
from pathlib import Path

import ifcopenshell
import pytest
from fastapi.testclient import TestClient

from app import script_edit
from tests.conftest import MODEL_ID

WALL_SCRIPT = '''\
import sys

import ifcopenshell

from script_lib import attach_design_key, create_entity, create_skeleton, write_and_validate

PARAMS = {{"key": "{key}"}}

def build(params, out_path):
    model = ifcopenshell.file(schema="IFC4")
    body, _ = create_skeleton(model)
    w = create_entity(model, "IfcWall", key="s1:wall:1", name="W1")
    attach_design_key(model, w, "s1:wall:1")
    write_and_validate(model, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''

PARAMS_KEY_SCRIPT = '''\
import sys

import ifcopenshell

from script_lib import attach_design_key, create_entity, create_skeleton, write_and_validate

PARAMS = {{"key": "{key}"}}

def build(params, out_path):
    model = ifcopenshell.file(schema="IFC4")
    body, _ = create_skeleton(model)
    w = create_entity(model, "IfcWall", key=params["key"], name="W1")
    attach_design_key(model, w, params["key"])
    write_and_validate(model, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''

TRACED_KEY_SCRIPT = '''\
import sys

import ifcopenshell

from script_lib import attach_design_key, create_entity, create_skeleton, write_and_validate

PARAMS = {{"key": "{key}"}}

def build(params, out_path):
    model = ifcopenshell.file(schema="IFC4")
    body, _ = create_skeleton(model)
    w = create_entity(model, "IfcWall", key="s1:" + "wall:1", name="W1")
    attach_design_key(model, w, "s1:wall:1")
    write_and_validate(model, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''


class TestRewriteCallArgument:
    def test_rewrite_string_argument(self):
        script = 'w = create_entity(model, "IfcWall", key="s1:wall:1", name="old")\n'
        out = script_edit.rewrite_call_argument(script, 1, "name", "new")
        assert '"new"' in out and '"old"' not in out
        assert 'key="s1:wall:1"' in out

    def test_rewrite_int_argument(self):
        script = 'w = create_entity(model, "IfcWall", key="k", count=1)\n'
        out = script_edit.rewrite_call_argument(script, 1, "count", 42)
        assert "count=42" in out

    def test_rewrite_float_argument(self):
        script = 'w = create_entity(model, "IfcWall", key="k", height=3.0)\n'
        out = script_edit.rewrite_call_argument(script, 1, "height", 2.5)
        assert "height=2.5" in out

    def test_rewrite_bool_argument_not_int(self):
        """bool 是 int 子类：True 必须写成 True 而不是 1。"""
        script = 'w = create_entity(model, "IfcWall", key="k", flag=False)\n'
        out = script_edit.rewrite_call_argument(script, 1, "flag", True)
        assert "flag=True" in out
        assert "flag=1" not in out

    def test_rewrite_appends_missing_argument(self):
        script = 'w = create_entity(model, "IfcWall", key="k")\n'
        out = script_edit.rewrite_call_argument(script, 1, "name", "W9")
        assert 'name="W9"' in out

    def test_rewrite_only_touches_target_line(self):
        script = (
            'a = create_entity(model, "IfcWall", key="k1", name="one")\n'
            'b = create_entity(model, "IfcWall", key="k2", name="two")\n'
        )
        out = script_edit.rewrite_call_argument(script, 2, "name", "TWO")
        assert 'name="one"' in out
        assert 'name="TWO"' in out

    def test_rewrite_preserves_comments_and_blank_lines(self):
        """libcst 无损：注释、空行、缩进原样保留。"""
        script = (
            "# header comment\n"
            "\n"
            "def build(params, out_path):\n"
            "    # inner comment\n"
            "    w = create_entity(model, \"IfcWall\", key=\"k\", name=\"old\")  # tail\n"
            "\n"
            "    return w\n"
        )
        out = script_edit.rewrite_call_argument(script, 5, "name", "new")
        assert out == script.replace('name="old"', 'name="new"')

    def test_rewrite_no_call_at_line_raises(self):
        with pytest.raises(ValueError):
            script_edit.rewrite_call_argument("x = 1\n", 1, "name", "v")

    def test_rewrite_syntax_error_raises_valueerror(self):
        with pytest.raises(ValueError):
            script_edit.rewrite_call_argument("def broken(:\n", 1, "name", "v")

    @pytest.mark.parametrize("bad", [{"a": 1}, [1, 2], (1,), None])
    def test_rewrite_rejects_non_scalar_value(self, bad):
        """容器/None 注入 → ValueError（只允许 str/int/float/bool 字面量）。"""
        with pytest.raises(ValueError):
            script_edit.rewrite_call_argument(
                'w = f(key="k", name="x")\n', 1, "name", bad
            )


def _uploads_ifc(data_dir: Path) -> Path:
    return data_dir / "uploads" / f"{MODEL_ID}.ifc"


def _wall_name(data_dir: Path) -> str:
    model = ifcopenshell.open(str(_uploads_ifc(data_dir)))
    return model.by_type("IfcWall")[0].Name


def _save_script(client: TestClient, script: str) -> None:
    r = client.put(f"/models/{MODEL_ID}/script", json={"script": script})
    assert r.status_code == 200, r.text
    r = client.post(f"/models/{MODEL_ID}/script/save", json={})
    assert r.status_code == 200, r.text


def _edit_call(client: TestClient, body: dict, model_id: str = MODEL_ID):
    return client.post(f"/models/{model_id}/script/edit-call", json=body)


class TestEditCallSuccess:
    def test_edit_call_stages_and_reruns(
        self, client: TestClient, data_dir: Path
    ):
        _save_script(client, WALL_SCRIPT.format(key="s1:wall:1"))
        assert _wall_name(data_dir) == "W1"

        r = _edit_call(
            client,
            {"designKey": "s1:wall:1", "argument": "name", "value": "W2"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["modelId"] == MODEL_ID
        assert body["staged"] == 1
        assert 'name="W2"' in body["script"]

        assert _wall_name(data_dir) == "W2"

        r = client.get(f"/models/{MODEL_ID}/script")
        assert r.status_code == 200
        staged = r.json()
        assert staged["staged"] == 1
        assert staged["canUndo"] is True

    def test_edit_call_params_origin_editable_for_other_argument(
        self, client: TestClient, data_dir: Path
    ):
        """origin=params 的调用点可改写：key 走 params 引用，但 name 仍是字面量。"""
        _save_script(client, PARAMS_KEY_SCRIPT.format(key="s1:wall:2"))
        map_path = data_dir / "models" / MODEL_ID / "current.map.json"
        entry = json.loads(map_path.read_text(encoding="utf-8"))["s1:wall:2"]
        assert entry["origin"] == "params"

        r = _edit_call(
            client,
            {"designKey": "s1:wall:2", "argument": "name", "value": "WP"},
        )
        assert r.status_code == 200, r.text
        assert _wall_name(data_dir) == "WP"


class TestEditCallFailures:
    def test_edit_call_unknown_designkey_404(
        self, client: TestClient, data_dir: Path
    ):
        _save_script(client, WALL_SCRIPT.format(key="s1:wall:1"))
        r = _edit_call(
            client,
            {"designKey": "s1:wall:nope", "argument": "name", "value": "X"},
        )
        assert r.status_code == 404

    def test_edit_call_missing_map_404(self, client: TestClient, data_dir: Path):
        _save_script(client, WALL_SCRIPT.format(key="s1:wall:1"))
        map_path = data_dir / "models" / MODEL_ID / "current.map.json"
        assert map_path.is_file()
        map_path.unlink()

        r = _edit_call(
            client,
            {"designKey": "s1:wall:1", "argument": "name", "value": "X"},
        )
        assert r.status_code == 404

    def test_edit_call_unknown_model_404(self, client: TestClient, data_dir: Path):
        r = _edit_call(
            client,
            {"designKey": "k", "argument": "name", "value": "X"},
            model_id="m_ffffffffffffffff",
        )
        assert r.status_code == 404

    def test_edit_call_traced_origin_422(
        self, client: TestClient, data_dir: Path
    ):
        """key 来自表达式（origin=traced）→ 422，提示直接改脚本。"""
        _save_script(client, TRACED_KEY_SCRIPT.format(key="s1:wall:1"))
        map_path = data_dir / "models" / MODEL_ID / "current.map.json"
        entry = json.loads(map_path.read_text(encoding="utf-8"))["s1:wall:1"]
        assert entry["origin"] == "traced"

        r = _edit_call(
            client,
            {"designKey": "s1:wall:1", "argument": "name", "value": "X"},
        )
        assert r.status_code == 422
        assert _wall_name(data_dir) == "W1"

    def test_edit_call_non_scalar_value_422(
        self, client: TestClient, data_dir: Path
    ):
        _save_script(client, WALL_SCRIPT.format(key="s1:wall:1"))
        r = _edit_call(
            client,
            {"designKey": "s1:wall:1", "argument": "name", "value": {"x": 1}},
        )
        assert r.status_code == 422
        assert _wall_name(data_dir) == "W1"

    def test_edit_call_build_failure_422_zero_side_effects(
        self, client: TestClient, data_dir: Path
    ):
        """重写本身合法但沙箱 run 失败（追加工厂不认识的 kwargs → TypeError）
        → 422，且 staging/uploads/map 全部不变。"""
        _save_script(client, WALL_SCRIPT.format(key="s1:wall:1"))
        before_ifc = _uploads_ifc(data_dir).read_bytes()
        map_path = data_dir / "models" / MODEL_ID / "current.map.json"
        before_map = map_path.read_bytes()

        r = _edit_call(
            client,
            {"designKey": "s1:wall:1", "argument": "bogus_kwarg", "value": 1},
        )
        assert r.status_code == 422, r.text

        r = client.get(f"/models/{MODEL_ID}/script")
        assert r.status_code == 200
        assert r.json()["staged"] == 0
        assert _uploads_ifc(data_dir).read_bytes() == before_ifc
        assert map_path.read_bytes() == before_map
