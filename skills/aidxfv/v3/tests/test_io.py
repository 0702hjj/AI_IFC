"""floorgeom/io.py 测试（T10）：canon 确定性 + sha256 稳定。"""

import json
from pathlib import Path

import pytest

from floorgeom.io import canon_bytes, sha256_of, write_json


class TestCanonBytes:
    def test_canon_twice_identical_bytes(self):
        payload = {"b": 2, "a": [1, {"y": "中", "x": 3}], "z": None}
        assert canon_bytes(payload) == canon_bytes(payload)

    def test_canon_sort_keys(self):
        """键排序：{"a":1,"b":2} 而不是声明顺序。"""
        payload = {"b": 2, "a": 1}
        raw = json.dumps(payload, ensure_ascii=False)
        assert canon_bytes(payload) == b'{"a":1,"b":2}\n'
        assert canon_bytes(payload) != (raw + "\n").encode("utf-8")

    def test_canon_utf8_ensure_ascii_false(self):
        """中文保持 UTF-8 原样（ensure_ascii=False）。"""
        payload = {"name": "走廊"}
        assert "走廊".encode("utf-8") in canon_bytes(payload)

    def test_canon_compact_separators(self):
        """紧凑分隔符（无空格）。"""
        payload = {"a": [1, 2], "b": {"c": 3}}
        assert canon_bytes(payload) == b'{"a":[1,2],"b":{"c":3}}\n'

    def test_canon_byte_deterministic_across_runs(self):
        payload = {"x": [3.14, "弧", None], "nested": {"deep": {"k": "v"}}}
        assert canon_bytes(payload) == canon_bytes(payload)


class TestSha256:
    def test_sha256_stable(self):
        payload = {"zone": "podium", "floors": [1, 2]}
        assert sha256_of(payload) == sha256_of(payload)

    def test_sha256_64_hex(self):
        assert len(sha256_of({"a": 1})) == 64
        int(sha256_of({"a": 1}), 16)  # 是合法 hex

    def test_sha256_different_payload_different_hash(self):
        assert sha256_of({"a": 1}) != sha256_of({"a": 2})

    def test_sha256_dict_order_insensitive(self):
        """canon 排序 → 键声明顺序不影响 hash。"""
        assert sha256_of({"a": 1, "b": 2}) == sha256_of({"b": 2, "a": 1})


class TestWriteJson:
    def test_write_roundtrip(self, tmp_path):
        payload = {"zone": "podium", "x": [1, 2, 3]}
        p = tmp_path / "out.json"
        sha = write_json(payload, p)
        assert p.read_bytes() == canon_bytes(payload)
        assert json.loads(p.read_text()) == payload
        assert len(sha) == 64

    def test_write_twice_identical_bytes(self, tmp_path):
        payload = {"rooms": [{"id": "a"}, {"id": "b"}]}
        p1 = tmp_path / "a.json"
        p2 = tmp_path / "b.json"
        write_json(payload, p1)
        write_json(payload, p2)
        assert p1.read_bytes() == p2.read_bytes()

    def test_write_returns_sha256(self, tmp_path):
        payload = {"a": 1}
        p = tmp_path / "x.json"
        assert write_json(payload, p) == sha256_of(payload)
