"""golden meta.json 数据卫生测试（W-0050 审计收尾）。

遍历 references/golden/ 全部案例的 meta.json：
- 必需键集合（case_id/type/一句话）齐全；
- 键名只含中英文/数字/下划线（拦 " এক句话" 类乱码混入）；
- 「一句话」为真实描述，非 "..." 占位或截断（... 结尾）。
"""

import json
import re
from pathlib import Path

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "references" / "golden"

REQUIRED_KEYS = {"case_id", "type", "一句话"}
KEY_RE = re.compile(r"^[\u4e00-\u9fffA-Za-z0-9_]+$")


def _all_meta_paths():
    return sorted(GOLDEN_DIR.glob("*/meta.json")) + sorted(GOLDEN_DIR.glob("*/*/meta.json"))


def test_golden_meta_files_exist():
    assert _all_meta_paths(), "golden 目录下应至少有一个 meta.json"


def test_golden_meta_required_keys():
    for p in _all_meta_paths():
        meta = json.loads(p.read_text(encoding="utf-8"))
        missing = REQUIRED_KEYS - meta.keys()
        assert not missing, f"{p.relative_to(GOLDEN_DIR)} 缺必需键: {missing}"


def test_golden_meta_key_names_sane():
    for p in _all_meta_paths():
        meta = json.loads(p.read_text(encoding="utf-8"))
        for key in meta:
            assert KEY_RE.match(key), \
                f"{p.relative_to(GOLDEN_DIR)} 键名含非法字符: {key!r}"


def test_golden_meta_one_liner_not_placeholder():
    for p in _all_meta_paths():
        meta = json.loads(p.read_text(encoding="utf-8"))
        value = str(meta.get("一句话", "")).strip()
        assert value and value not in {"...", "…"} and not value.endswith("..."), \
            f"{p.relative_to(GOLDEN_DIR)} 一句话是占位/截断值: {value!r}"
