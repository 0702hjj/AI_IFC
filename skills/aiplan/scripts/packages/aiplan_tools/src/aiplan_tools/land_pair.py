"""land_pair —— plan 阶段双产物成对落盘（run 目录唯一性 + L-01 哈希互指）。

落盘管线总装（implement.md P1+P2）：
    plan.json ──► validate_plan ──► canon ──┐
    bim_supplement.json ──► validate_bim_supplement ──► canon ──┤
                                                                ▼
                          {workspace}/plan/<时间戳>_<项目>/
                              ├─ plan.json            （canon 写盘）
                              └─ bim_supplement.json  （source_plan_sha256 = plan 实算 sha）

铁律（D-3/D-5）：
- **每次落盘单开目录**（run 唯一性）：`plan/<时间戳>_<项目>/`——不覆盖任何历史，
  每次设计是一个独立 run 目录，历史全程可追溯（用户拍板）；
- 两文件同目录（run 目录内）；canon 后字节级可重现；
- bim_supplement.source_plan_sha256 必须等于 plan.json canon 后的 sha256（成对互指）；
- 落盘前双门禁都过，绝不带病写盘。

用法：
    land_pair.py plan.json bim_supplement.json --outdir plan/
    # 读两文件 → 双门禁 → 重算 source_plan_sha256 → canon 写盘到新 run 目录 → 打印路径与两 sha
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from aiplan_tools import plan_canon  # noqa: E402
from aiplan_tools import validate_plan  # noqa: E402
from aiplan_tools import validate_bim_supplement  # noqa: E402
from aiplan_tools import design_gate  # noqa: E402


def run_dir_name(plan_obj: dict, stamp: str | None = None) -> str:
    """生成 run 目录名：<时间戳>_<项目>。项目名清洗（去掉路径分隔符/空白）。"""
    stamp = stamp or time.strftime("%Y%m%dT%H%M%S")
    proj = str(plan_obj.get("project", "untitled")).strip() or "untitled"
    for ch in ('/', '\\', ':', '*', '?', '"', '<', '>', '|', ' '):
        proj = proj.replace(ch, "_")
    return f"{stamp}_{proj}"


def land_pair(plan_obj, bim_obj, outdir: Path) -> tuple[str, str, Path]:
    """成对落盘到新 run 目录，返回 (plan_sha256, bim_sha256, run_dir)。

    步骤：① 双门禁 ② 重算 source_plan_sha256 互指 ③ 单开 run 目录 canon 写盘。
    任一门禁失败抛 ValueError（带错误列表），不写盘。
    """
    # ① 双门禁（不通过则拒绝写盘）
    plan_errs = validate_plan.validate(plan_obj)
    if plan_errs:
        raise ValueError(f"plan.json 门禁失败:\n  - " + "\n  - ".join(plan_errs))
    bim_errs = validate_bim_supplement.validate(bim_obj)
    if bim_errs:
        raise ValueError(f"bim_supplement.json 双门禁失败:\n  - " + "\n  - ".join(bim_errs))

    # ①b 设计质量门禁（2026-08-11，把"可选流程"升级为强制门禁——design_rationale 必填 + 引 derive 事实）
    gate_errors, gate_warnings = design_gate.validate_design_quality(plan_obj)
    for w in gate_warnings:
        print(f"[WARN] {w}", file=sys.stderr)
    if gate_errors:
        raise ValueError(f"设计质量门禁失败（回 step-01 第 2 轮重走）:\n  - " + "\n  - ".join(gate_errors))

    # ② 成对互指：bim_supplement.source_plan_sha256 = plan canon 后的 sha
    plan_sha = plan_canon.canon_sha256(plan_obj)
    bim_obj = dict(bim_obj)  # 不改调用方对象
    bim_obj["source_plan_sha256"] = plan_sha

    # ③ 单开 run 目录（唯一性：每次落盘独立目录，不覆盖历史）
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    run_dir = outdir / run_dir_name(plan_obj)
    # 同秒同名防碰撞（极端情况追加序号）
    n = 2
    while run_dir.exists():
        run_dir = outdir / f"{run_dir_name(plan_obj)}_{n}"
        n += 1
    run_dir.mkdir(parents=True, exist_ok=True)
    plan_path = run_dir / "plan.json"
    bim_path = run_dir / "bim_supplement.json"

    written_plan_sha = plan_canon.canon_write(plan_obj, str(plan_path) + ".new")
    written_bim_sha = plan_canon.canon_write(bim_obj, str(bim_path) + ".new")
    Path(str(plan_path) + ".new").replace(plan_path)
    Path(str(bim_path) + ".new").replace(bim_path)

    # 落盘后校验互指（防御性：写盘后重读校验）
    reread_bim = json.loads(bim_path.read_text(encoding="utf-8"))
    assert reread_bim["source_plan_sha256"] == written_plan_sha, "落盘后互指校验失败"

    return written_plan_sha, written_bim_sha, run_dir


def _main(argv: list[str]) -> int:
    """CLI 入口。兼容两种 argv 约定：
    - console_scripts：argv[0..]=plan bim（无占位）
    - aiplan land 分组路由（POSITIONAL_FIRST）：argv[0]="aiplan land" 占位
      （area/land 约定 argv[0]=脚本名）——argparse 型模块必须跳过占位，
      否则占位被当 plan 位置参数、真实 plan 被当 bim（2026-08-13 落盘卡死 bug）。
    """
    if argv and argv[0].startswith("aiplan "):
        argv = argv[1:]
    p = argparse.ArgumentParser(description="plan 双产物成对落盘（双门禁 + canon + 互指，单开 run 目录）")
    p.add_argument("plan", help="plan.json 路径")
    p.add_argument("bim", help="bim_supplement.json 路径")
    p.add_argument("--outdir", default="plan", help="落盘根目录（默认 plan/，每次新建 run 子目录）")
    args = p.parse_args(argv)

    plan_obj = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    bim_obj = json.loads(Path(args.bim).read_text(encoding="utf-8"))

    try:
        plan_sha, bim_sha, run_dir = land_pair(plan_obj, bim_obj, Path(args.outdir))
    except ValueError as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        return 1

    print(f"[OK] 落盘到 {run_dir}/")
    print(f"  plan.json            sha256={plan_sha}")
    print(f"  bim_supplement.json  sha256={bim_sha}")
    print(f"  source_plan_sha256  →{plan_sha[:16]}… (互指)")
    return 0


def main() -> int:
    """console_scripts 无参入口（setuptools 调用）。"""
    return _main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
