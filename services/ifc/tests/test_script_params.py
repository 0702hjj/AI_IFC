# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""script_params: ast-based PARAMS extraction and replacement.

``GET .../script/params`` feeds the DesignPanel form; ``PUT .../script`` with
a params-only body replaces the PARAMS block server-side so the form never
touches the rest of the script.
"""

from __future__ import annotations

import pytest

from app import script_params

SCRIPT = '''\
"""demo"""

PARAMS = {"name": "t", "width": 6, "nested": {"a": [1, 2.5, True, None]}}


def build(params, out_path):
    open(out_path, "w").write(str(params["width"]))


if __name__ == "__main__":
    import sys
    build(PARAMS, sys.argv[1])
'''


class TestExtractParams:
    def test_extract(self):
        params = script_params.extract_params(SCRIPT)
        assert params == {"name": "t", "width": 6,
                          "nested": {"a": [1, 2.5, True, None]}}

    def test_no_params_raises(self):
        with pytest.raises(ValueError, match="PARAMS"):
            script_params.extract_params("def build(p, o):\n    pass\n")

    def test_non_dict_params_raises(self):
        with pytest.raises(ValueError):
            script_params.extract_params("PARAMS = [1, 2]\n")

    def test_non_literal_params_raises(self):
        with pytest.raises(ValueError):
            script_params.extract_params('import os\nPARAMS = {"a": os.getcwd()}\n')

    def test_syntax_error_raises(self):
        with pytest.raises(ValueError):
            script_params.extract_params("PARAMS = {")


class TestReplaceParams:
    def test_replace_roundtrip(self):
        new = {"name": "u", "width": 9}
        out = script_params.replace_params(SCRIPT, new)
        assert script_params.extract_params(out) == new

    def test_replace_preserves_rest_of_script(self):
        out = script_params.replace_params(SCRIPT, {"x": 1})
        assert '"""demo"""' in out
        assert "def build(params, out_path):" in out
        assert 'if __name__ == "__main__":' in out

    def test_replace_multiline_params_block(self):
        src = 'PARAMS = {\n    "a": 1,\n    "b": 2,\n}\n\ndef build(p, o):\n    pass\n'
        out = script_params.replace_params(src, {"c": 3})
        assert script_params.extract_params(out) == {"c": 3}
        assert "def build(p, o):" in out

    def test_replace_emits_valid_python_literals(self):
        out = script_params.replace_params(
            SCRIPT, {"s": "中文", "b": True, "n": None, "f": 1.5, "l": [1]}
        )
        assert script_params.extract_params(out) == {
            "s": "中文", "b": True, "n": None, "f": 1.5, "l": [1],
        }

    def test_replace_without_params_raises(self):
        with pytest.raises(ValueError, match="PARAMS"):
            script_params.replace_params("x = 1\n", {"a": 1})

    def test_replace_rejects_non_json_params(self):
        with pytest.raises(ValueError):
            script_params.replace_params(SCRIPT, {"bad": object()})
