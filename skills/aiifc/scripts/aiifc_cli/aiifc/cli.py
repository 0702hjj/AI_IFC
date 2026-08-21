"""aiifc.cli —— IFC 建模 CLI（flows 脚本的 agent 可执行入口，薄壳无业务逻辑）。

定位（不重新规划 aiifc 现有 flows）：references/docs/flows/ 下的脚本（design_builder /
build_script_template / dxf_from_design）已成体系、是「直接调用」（python xxx.py）形态——
本 CLI 只做**通用 shell 调用能力的薄壳**：`aiifc <cmd>` → subprocess 跑对应 flows 脚本
（不改 flows 本身），让 flows 能经 agent execute 跑（白名单 aiifc，同 aidxfv3/aiplan 形态）。
**consume-upstream 是新定义的库**（aiifc.consume_upstream，import 调用——cad->ifc 消费上游
转换器，不动现有 flows）。

子命令：
  design-build      design.json → features.json（flows/design_builder.py）
  build-script      features.json → IFC（flows/build_script_template.py）
  dxf-from-design   design.json → DXF（flows/dxf_from_design.py）
  consume-upstream  上游产物 → design.json（aiifc.consume_upstream 新库，cad->ifc 消费上游）
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def _flows_dir() -> Path:
    """aiifc skill 根下 references/docs/flows（现有 flows 脚本所在）。

    定位：AIIFC_FLOWS_DIR env（显式）→ 本包上溯 skills/aiifc/references/docs/flows（源/dist 同构）。
    """
    if d := os.environ.get("AIIFC_FLOWS_DIR"):
        return Path(d)
    # 本文件 skills/aiifc/scripts/aiifc/aiifc/cli.py → 上 4 级 = skills/aiifc
    return Path(__file__).resolve().parents[3] / "references" / "docs" / "flows"


def _emit(data: dict, out: str | None) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=1)
    if out:
        Path(out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def _run_flow(script: str, flow_args: list[str], out: str | None) -> int:
    """薄壳：subprocess 跑 flows 脚本（通用 shell 调用，不改 flows）。错误文本化（不裸 traceback）。"""
    script_path = _flows_dir() / script
    if not script_path.is_file():
        _emit({"valid": False, "error": f"flows 脚本不存在: {script_path}"}, out)
        return 1
    r = subprocess.run([sys.executable, str(script_path), *flow_args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        _emit({"valid": False, "error": (r.stderr.strip() or r.stdout.strip())[:2000]}, out)
        return r.returncode
    return 0


def _cmd_design_build(args) -> int:
    out_file = args.out or "features.json"
    rc = _run_flow("design_builder.py", [args.design, "-o", out_file], args.out and None or None)
    if rc != 0:
        return rc
    _emit({"valid": True, "features": out_file}, None)
    return 0


def _cmd_build_script(args) -> int:
    out_file = args.out or "model.ifc"
    rc = _run_flow("build_script_template.py", [args.features, "-o", out_file], None)
    if rc != 0:
        return rc
    _emit({"valid": True, "ifc": out_file}, None)
    return 0


def _cmd_dxf_from_design(args) -> int:
    out_file = args.out or "plan.dxf"
    rc = _run_flow("dxf_from_design.py", [args.design, "-o", out_file], None)
    if rc != 0:
        return rc
    _emit({"valid": True, "dxf": out_file}, None)
    return 0


def _cmd_consume_upstream(args) -> int:
    """上游产物 → design.json（cad->ifc 消费上游——新定义库 aiifc.consume_upstream，import 调用）。

    输入：building.json（zones 记 modelId）+ bim_supplement.json + DXF 目录（各 zone DXF）。
    输出：design.json（DESIGN_JSON_SCHEMA 协议：frame.storeys + floors.walls/openings/roof）。
    """
    from aiifc.consume_upstream import consume_upstream
    try:
        design = consume_upstream(
            building_path=args.building,
            bim_path=args.bim,
            dxf_dir=args.dxf_dir,
        )
    except Exception as e:  # noqa: BLE001 —— 薄壳兜底，错误文本化
        _emit({"valid": False, "error": str(e)}, args.out)
        return 1
    out_file = args.out or "design.json"
    Path(out_file).write_text(json.dumps(design, ensure_ascii=False, indent=1), encoding="utf-8")
    _emit({"valid": True, "design": out_file,
           "storeys": len(design.get("frame", {}).get("storeys", {}))}, None)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="aiifc", description="aiifc IFC 建模 CLI（flows 脚本通用 shell 入口）")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("design-build", help="design.json → features.json（flows/design_builder.py）")
    d.add_argument("design", help="design.json 路径")
    d.add_argument("-o", "--out", default="features.json")

    b = sub.add_parser("build-script", help="features.json → IFC（flows/build_script_template.py）")
    b.add_argument("features", help="features.json 路径")
    b.add_argument("-o", "--out", default="model.ifc")

    x = sub.add_parser("dxf-from-design", help="design.json → DXF（flows/dxf_from_design.py）")
    x.add_argument("design", help="design.json 路径")
    x.add_argument("-o", "--out", default="plan.dxf")

    c = sub.add_parser("consume-upstream", help="上游产物 → design.json（aiifc.consume_upstream 新库，cad->ifc）")
    c.add_argument("--building", required=True, help="building.json 路径（zones 记 modelId）")
    c.add_argument("--bim", required=True, help="bim_supplement.json 路径")
    c.add_argument("--dxf-dir", required=True, help="各 zone DXF 目录（或 workdir）")
    c.add_argument("-o", "--out", default="design.json")
    return p


_HANDLERS = {
    "design-build": _cmd_design_build,
    "build-script": _cmd_build_script,
    "dxf-from-design": _cmd_dxf_from_design,
    "consume-upstream": _cmd_consume_upstream,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return _HANDLERS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
