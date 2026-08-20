"""
design_review.py — 生成后设计质量审查。

检查优先级:
    SS  空间结构完整性(最高优先级,Project→Site→Building→Storey 链 + 构件挂载)
    GI  几何完整性 GI-01~06(包络闭合/窗贴墙/楼梯开洞/洞口包含/墙贴板/柱贴板)
    GEO Body 几何存在性 + 门窗洞口链接
    PR/RH/MC/CP/FD/SQ  SPATIAL_QUALITY.md 设计规则(保持现有实现)

P2 接地(research/check_strut/ifcquery_investigation.md §7):
    - GI-01 包络闭合: container 分组 + 墙轴线端点拓扑(无需几何内核)
    - GI-02 窗墙附着: FillsVoids → opening → VoidsElements 关系链 + 几何兜底
    - 可选碰撞: import ifcquery.clash (--clash 开启)

输出: analysis_results/<model>_analysis.json(含空间结构树,喂给 LLM 审查)

硬编码的 error 深挖(非文本纪律):
    run() 结束后自动从 error 消息提取 #stepid,扫描其 placement/geometry_summary/
    container 嵌入 report["error_elements"];门窗/洞口类 error 额外附 nearest_wall
    (墙轴线无 Axis 表示时从 Body 轮廓兜底估算)。LLM 拿到报告即有全部修复坐标,
    无需再手动调 ifc_inspect。

用法:
    # 独立运行(读 IFC 文件,写 analysis_results/)
    python design_review.py model.ifc [building_type] [--out DIR] [--no-json] [--clash]

    # 在 example 中调用(生成后审查)
    from flows.design_review import run
    report = run(model, building_type="school", model_name="my_school")
    # report["ok"] / report["errors"] / report["warnings"] / report["info"]

规则来源: references/SPATIAL_QUALITY.md
"""

import json
import re
import sys
from pathlib import Path

import numpy as np
import ifcopenshell
import ifcopenshell.util.placement
import ifcopenshell.util.element

try:  # 包内导入(example: from flows.design_review import run)
    from flows.design_review_utils import (
        _scan_element, _world_pos, _has_body, _get_psets_safe, _get_material_safe,
        _get_container_safe, _by_type_safe, _overlap,
    )
    from flows.design_review_spatial import SpatialReviewMixin
    from flows.design_review_gi import GeometricIntegrityMixin
    from flows.design_review_measure import MeasureMixin
    from flows.design_review_rules import DesignRulesMixin
except ImportError:  # 独立运行(python docs/flows/design_review.py)
    from design_review_utils import (
        _scan_element, _world_pos, _has_body, _get_psets_safe, _get_material_safe,
        _get_container_safe, _by_type_safe, _overlap,
    )
    from design_review_spatial import SpatialReviewMixin
    from design_review_gi import GeometricIntegrityMixin
    from design_review_measure import MeasureMixin
    from design_review_rules import DesignRulesMixin


class DesignReviewer(SpatialReviewMixin, GeometricIntegrityMixin,
                     MeasureMixin, DesignRulesMixin):
    """设计质量审查器。读 IFC 模型,先查空间结构(SS),再查几何完整性(GI),最后查设计规则。

    规则实现按职责拆在 mixin 模块(W-0049 行数门控):
    design_review_spatial(SS+error 深挖) / design_review_gi(GI) /
    design_review_measure(量取+GEO) / design_review_rules(PR/RH/MC/FD/CLASH)。
    """

    # SS-05 需要检查空间挂载的构件类
    _CONTAINED_CLASSES = (
        "IfcWall", "IfcSlab", "IfcDoor", "IfcWindow", "IfcColumn", "IfcBeam",
        "IfcStair", "IfcStairFlight", "IfcRailing", "IfcRoof", "IfcPlate",
        "IfcMember", "IfcCurtainWall", "IfcRamp", "IfcRampFlight",
        "IfcCovering", "IfcFurniture", "IfcBuildingElementProxy",
    )

    def __init__(self, model: ifcopenshell.file, building_type: str = "public"):
        self.model = model
        self.building_type = building_type  # residential / office / school / retail / public
        self.errors = []
        self.warnings = []
        self.info = []
        self.mm = self._length_unit_scale()  # 1mm = self.mm 个模型单位

    def run(self) -> dict:
        """执行全部规则检查,返回审查报告。"""
        self._check_spatial_structure()      # SS-01~06 最高优先级
        self._check_geometric_integrity()    # GI-01~06
        self._check_geometry_presence()      # GEO has_body
        self._check_proportion_rules()       # PR-01~04
        self._check_rhythm_rules()           # RH-02
        self._check_material_rules()         # MC-01/03
        self._check_facade_depth_rules()     # FD(stub)
        self._check_clashes()                # CLASH 穿模（结构构件互相穿透）

        ok = len(self.errors) == 0
        report = {
            "ok": ok,
            "building_type": self.building_type,
            "schema": self.model.schema,
            "length_unit_scale_mm": self.mm,
            "spatial_structure": self.build_spatial_tree(),
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "summary": f"{len(self.errors)} errors, {len(self.warnings)} warnings, {len(self.info)} info",
        }
        # 硬编码:error 涉及构件的几何细节自动嵌入(无需 LLM 再调 ifc_inspect)
        details = self._collect_error_details()
        if details:
            report["error_elements"] = details
        return report


def _default_out_dir() -> Path:
    """analysis_results/ 位于 AI_IFC 根目录(skills/aiifc/references/docs/flows/ 上五级)。"""
    try:
        return Path(__file__).resolve().parents[5] / "analysis_results"
    except Exception:
        return Path.cwd() / "analysis_results"


def run(model_or_path, building_type: str = "public", model_name: str = None,
        out_dir: str | Path = None, write_json: bool = None) -> dict:
    """
    统一入口: 接受 model 对象或 IFC 文件路径,返回审查报告。

    :param model_or_path: ifcopenshell.file 或 IFC 文件路径
    :param building_type: residential | office | school | retail | public
    :param model_name: 输出 JSON 的文件名前缀;传路径时默认为文件 stem
    :param out_dir: JSON 输出目录(默认 AI_IFC/analysis_results/)
    :param write_json: 是否写 JSON;默认路径输入时写、model 对象输入时不写
                       (model 对象想写需传 model_name)
    """
    path = None
    if isinstance(model_or_path, (str, Path)):
        path = Path(model_or_path)
        model = ifcopenshell.open(str(path))
        if model_name is None:
            model_name = path.stem
        if write_json is None:
            write_json = True
    else:
        model = model_or_path
        if write_json is None:
            write_json = model_name is not None

    reviewer = DesignReviewer(model, building_type)
    report = reviewer.run()
    if path:
        report["model"] = str(path)

    if write_json and model_name:
        out = Path(out_dir) if out_dir else _default_out_dir()
        out.mkdir(parents=True, exist_ok=True)
        out_path = out / f"{model_name}_analysis.json"
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str),
                            encoding="utf-8")
        report["json_path"] = str(out_path)

    return report


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args:
        print("Usage: python design_review.py <model.ifc> [building_type] [--out DIR] [--no-json] [--clash]")
        print("  building_type: residential | office | school | retail | public")
        sys.exit(1)
    path = args[0]
    btype = args[1] if len(args) > 1 else "public"
    out_dir = None
    if "--out" in sys.argv:
        out_dir = sys.argv[sys.argv.index("--out") + 1]

    report = run(path, btype, out_dir=out_dir, write_json="--no-json" not in flags)

    print(f"[DESIGN REVIEW] {path}")
    print(f"  Type: {btype} | Schema: {report['schema']} | Unit scale: {report['length_unit_scale_mm']}")
    print(f"  {report['summary']}")
    if report["errors"]:
        print("\nERRORS:")
        for e in report["errors"]:
            print(f"  {e}")
    if report["warnings"]:
        print("\nWARNINGS:")
        for w in report["warnings"]:
            print(f"  {w}")
    if report["info"]:
        print("\nINFO:")
        for i in report["info"]:
            print(f"  {i}")

    # --clash 已废弃：CLASH 检查现已纳入 run() 主流程（→ WARNINGS [CLASH]，含正常接合假阳性）。
    # 保留 flag 向后兼容，复用 report 已有结果，不重跑。
    if "--clash" in flags:
        clash_warns = [w for w in report["warnings"] if w.startswith("[CLASH]")]
        if clash_warns:
            print(f"\nCLASHES (穿模，含正常接合假阳性，需复核): {len(clash_warns)} elements")
            for w in clash_warns[:10]:
                print(f"  {w}")
        elif any("clash check skipped" in i for i in report["info"]):
            print("\nCLASHES: skipped (ifcquery not available)")
        else:
            print("\nCLASHES: 0 (no geometric intersection)")

    if report.get("json_path"):
        print(f"\n→ {report['json_path']}")
    sys.exit(0 if report["ok"] else 1)
