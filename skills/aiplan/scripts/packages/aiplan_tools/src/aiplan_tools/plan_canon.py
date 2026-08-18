"""plan_canon —— plan.json / bim_supplement.json 的 canonical 序列化 + sha256。

canon 算法（与 cad 侧对接格式一致——两 skill 各自独立，算法同源手动同步）：
    json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    → .encode("utf-8") → sha256 hexdigest

这是落盘管线（P1.3 validate → canon → sha256 → 写盘）与成对哈希校验的共用底座。
保证字节级可重现：同对象两次 canon 字节相同、sha 相同。

用法：
    plan_canon.py plan.json            # 打印 sha256
    plan_canon.py plan.json --dump     # 打印 canon 字符串（落盘前用）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def canon_dump(obj) -> str:
    """canonical JSON 字符串（与 V2 成对哈希算法同款，字节级稳定）。"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def canon_sha256(obj) -> str:
    """canonical 序列化后的 sha256 hexdigest（64 位小写 hex）。"""
    return hashlib.sha256(canon_dump(obj).encode("utf-8")).hexdigest()


def canon_write(obj, path) -> str:
    """对象 canon 序列化后写盘（原子写：先 .new 再 replace），返回 sha256。

    落盘的文件 = canon_dump 的内容（紧凑、排序稳定、可 diff 为空）。
    """
    text = canon_dump(obj)
    p = Path(path)
    p.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="plan/bim_supplement 的 canonical 序列化 + sha256")
    p.add_argument("path", help="JSON 文件路径（或 - 从 stdin 读）")
    p.add_argument("--dump", action="store_true", help="打印 canon 字符串而非 sha256")
    args = p.parse_args(argv)

    if args.path == "-":
        obj = json.load(sys.stdin)
    else:
        obj = json.loads(Path(args.path).read_text(encoding="utf-8"))

    if args.dump:
        print(canon_dump(obj))
    else:
        print(canon_sha256(obj))
    return 0



def main() -> int:
    """console_scripts 无参入口（setuptools 调用）。"""
    import sys
    return _main(sys.argv[1:])

if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
