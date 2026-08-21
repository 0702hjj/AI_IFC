"""aidxfv3 —— CLI 薄壳（W4 T45 全接）。

纪律（refine&addon_package §5）：薄壳无业务逻辑；包内函数签名不变；
lazy import（import 放函数体内）；JSON in / JSON out；退出码 0 通过 / 1 FAIL / 2 SchemaError。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SUBCOMMANDS = [
    "init", "preprocess", "derive", "normalize", "check", "draw",
    "svg", "readback", "reconcile", "sync",
    "pack", "state", "gold", "deliver",
]


def resolve_skill_workdir(project_id: str) -> str:
    """projectId → 平台 skill 工作区绝对路径（{VIEWER_DATA_DIR}/skill-work/{projectID}）。

    结构性保证中间产物落盘位置：CLI 内部算 workdir（不靠 LLM 传对 --project 路径）。
    平台内使用（agent execute 跑时 env 有 VIEWER_DATA_DIR）；独立使用时用 --project 直传路径。
    """
    if not project_id:
        return ""
    data_root = os.environ.get("VIEWER_DATA_DIR", "")
    if not data_root:
        raise SystemExit(
            "VIEWER_DATA_DIR 未设置——--project-id 需平台环境（agent execute 注入）；"
            "独立使用请用 --project 直传工作目录"
        )
    return os.path.join(data_root, "skill-work", project_id)


def _apply_project_id(args) -> None:
    """--project-id 优先：CLI 内部算 skill-work/{projectID} 覆盖 args.project（结构性落盘根）。

    有 --project-id 时 args.project 被覆盖为平台工作区——后续各子命令用 args.project 即
    落到 skill-work/{projectID}（不靠 LLM 传对路径）。无 --project-id 时保留 --project 原值
    （独立使用/显式路径）。
    """
    pid = getattr(args, "project_id", None)
    if pid:
        args.project = resolve_skill_workdir(pid)

STATE_SUBCOMMANDS = ["sync", "advance", "reconcile"]

GOLD_SUBCOMMANDS = ["reindex", "query", "reverse", "replay", "ingest"]


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", help="产出文件路径（缺省输出到 stdout）")
    parser.add_argument("--plan", help="plan.json 路径")
    parser.add_argument("--zone", help="zone id")
    parser.add_argument("--dsl", help="DSL 声明文件路径（skeleton.json / rooms.json）")
    parser.add_argument("--geom", help="几何模型 JSON 路径（normalize 产出）")
    parser.add_argument("--params", help="校验参数 JSON 路径（derived/floors.json）")
    parser.add_argument("--dxf", help="DXF 文件路径")
    parser.add_argument("--decl", help="声明文件路径（对账/同步用）")
    parser.add_argument("--graph", help="回读房间图 JSON 路径")
    parser.add_argument("--node", help="mission node（如 tower_std.rooms）")
    parser.add_argument("--project", help="项目工作目录（独立使用直传；平台内有 --project-id 时被覆盖）")
    parser.add_argument("--project-id", dest="project_id",
                        help="平台项目 id（p_...）——CLI 内部算 skill-work/{projectID} 为工作区（结构性落盘根，优先于 --project）")
    parser.add_argument("--units", help="DXF 单位（mm/inch）")
    parser.add_argument("--case", help="金例 case_id（gold 子命令）")
    parser.add_argument("--floors", nargs="+",
                        help="楼层几何模型 JSON ×N（check 跨层 R-06 用）")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aidxfv3",
        description="aidxfv3 CLI——LLM 设计 × 机器锚定（plan→cad v3）。"
                    "纯函数 / JSON in out / 退出码 0 通过 1 FAIL 2 SchemaError。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    commands = {
        "init": "init 工作区（--project-id → 建 skill-work/{projectID} + marker 锚定，后续步骤不用一直传/算）",
        "validate": "DSL/plan schema 校验（exit 2 SchemaError）",
        "preprocess": "S0 全量预处理：schema 校验 + 派生 + 楼层归并 + zone 打包",
        "derive": "plan → 派生几何事实（边清单/方位/凹角/暗区/换算尺…）",
        "normalize": "DSL 声明 → 坐标几何（snap/索引解析/消重叠/实测回算）",
        "check": "规则机检（轮廓级摄取 + 房间级 R-01~R-09）",
        "draw": "archdxf 逐构件画法封装（主 agent 调用，非渲染器）",
        "svg": "DXF → SVG 导出",
        "readback": "底稿翻译：DXF → 房间图",
        "reconcile": "声明 vs 底稿对账",
        "sync": "DXF 直接编辑回收：哈希 → 回读 → audit → 更新声明",
        "pack": "mission 渲染（zone 切片 + 骨架段 + feedback → prompt.md）",
        "deliver": "confirmed 封存 + building.json + checksums",
    }
    for name, help_text in commands.items():
        p = sub.add_parser(name, help=help_text)
        _add_common(p)
        if name == "pack":
            # pack 专属：goldlib push 预筛注入（按类型选段）
            p.add_argument("--type", help="building_type（如 residence），用于 gold pattern 预筛")
            p.add_argument("--db", help="golden.db 路径（预筛 pattern 用）")

    gold = sub.add_parser("gold", help="参考库子命令组")
    gsub = gold.add_subparsers(dest="gold_command", required=True)
    gsub.add_parser("reindex", help="文件 → golden.db 重建（幂等）")
    gsub.add_parser("query", help="特征直查（pull 模式）")
    gsub.add_parser("reverse", help="底稿 → 反推 DSL 声明")
    gsub.add_parser("replay", help="replay 前置（G2 闸门产物）")
    gsub.add_parser("ingest", help="新案例入库（vote/correct/challenge）")
    for gp in gsub.choices.values():
        _add_common(gp)

    state = sub.add_parser("state", help="状态编排组（只记状态，不自动派发/检查）")
    ssub = state.add_subparsers(dest="state_command", required=True)
    ssub.add_parser("sync", help="对照 floors.json#dag.nodes 幂等补缺 mission")
    ssub.add_parser("advance", help="按产物推进单 mission 状态（--node）")
    ssub.add_parser("reconcile", help="中断恢复全量对账（扫 missions/ 汇总真实状态）")
    for sp in ssub.choices.values():
        _add_common(sp)
    return parser


# ---------------------------------------------------------------------------
# 命令实现（薄壳：只做 IO + 调包函数，无业务逻辑）
# ---------------------------------------------------------------------------

def _read_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _emit(data, out: str | None) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    if out:
        Path(out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def _cmd_validate(args) -> int:
    from flowops.validate import validate_plan, validate_skeleton, validate_rooms
    if args.plan:
        errors = validate_plan(_read_json(args.plan))
    elif args.dsl:
        doc = _read_json(args.dsl)
        if "zones" in doc and "frame" in doc:
            errors = validate_skeleton(doc)
        else:
            errors = validate_rooms(doc)
    else:
        errors = [{"message": "需 --plan 或 --dsl"}]
    _emit({"valid": not errors, "errors": errors}, args.out)
    return 0 if not errors else 2


def _cmd_preprocess(args) -> int:
    from flowops.preprocess import preprocess
    plan = _read_json(args.plan)
    out_dir = args.out or "derived"
    try:
        result = preprocess(plan, out_dir)
    except ValueError as ex:
        _emit({"valid": False, "error": str(ex)}, None)
        return 1
    _emit({"valid": True, "out": out_dir, "zones": list(result["zone_packs"])}, None)
    return 0


def _cmd_derive(args) -> int:
    from floorgeom.derive import derive
    plan = _read_json(args.plan)
    result = derive(plan)
    _emit(result, args.out)
    return 0


def _cmd_normalize(args) -> int:
    from floorgeom.normalize import SchemaError, normalize_rooms, normalize_skeleton
    doc = _read_json(args.dsl)
    try:
        if "zones" in doc and "frame" in doc:
            result = normalize_skeleton(doc)
        else:
            # --params 可给 skeleton 几何模型或 skeleton.json（DSL 自动 normalize）
            skeleton = _load_skeleton_model(args.params) if args.params else {}
            result = normalize_rooms(doc, skeleton)
    except SchemaError as ex:
        _emit({"valid": False, "error": ex.error}, args.out)
        return 2
    _emit(result, args.out)
    return 0


def _load_skeleton_model(path: str) -> dict:
    """skeleton 几何模型加载：DSL（含 typology 字段）自动过 normalize_skeleton。

    薄壳 IO 适配：调用方既可给 normalize 产出的几何模型，也可直接给
    skeleton.json（DSL）——后者先经唯一坐标计算点转换。
    """
    doc = _read_json(path)
    zones = doc.get("zones") or []
    if zones and "typology" in zones[0]:  # DSL 特征（typology 是 skeleton DSL required）
        from floorgeom.normalize import normalize_skeleton
        return normalize_skeleton(doc)
    return doc


def _outline_polys_from_skeleton(skeleton_model: dict) -> list:
    """轮廓多边形列表（薄壳转发 floorgeom——几何逻辑不出包）。"""
    from floorgeom.check import outline_polygons_from_skeleton
    return outline_polygons_from_skeleton(skeleton_model)


def _cmd_check(args) -> int:
    from floorgeom.check import (
        check_alignment_zones, check_blocks_semantic, check_floor,
        check_holes_alignment, check_outline_plan,
        check_skeleton_outline_containment,
    )
    errs: list[str] = []       # 致命（exit 1）
    warnings: list[str] = []   # 警告（报告但不阻断）
    if args.floors:
        # 跨层 R-06：核心筒跨层一致（每层 normalize 产出的几何模型）
        from floorgeom.check import check_core_alignment
        floors = [_read_json(f) for f in args.floors]
        for r in check_core_alignment(floors):
            (errs if r.get("severity") in ("FAIL", "error")
             else warnings).append(f"[{r.get('rule')}] {r.get('detail')}")
    elif args.dsl:
        doc = _read_json(args.dsl)
        if "zones" in doc and "frame" in doc:
            # 骨架级（D34）：schema → normalize → 越轮廓 + blocks 语义 + holes 对齐
            from flowops.validate import validate_skeleton
            from floorgeom.normalize import SchemaError, normalize_skeleton
            verrs = validate_skeleton(doc)
            if verrs:
                _emit({"valid": False,
                       "errors": [str(e) for e in verrs]}, args.out)
                return 2
            try:
                model = normalize_skeleton(doc)
            except SchemaError as ex:
                _emit({"valid": False, "errors": [str(ex)]}, args.out)
                return 2
            errs += check_skeleton_outline_containment(model)
            for z in doc.get("zones") or []:
                warnings += [f"[{r.get('rule')}] {r.get('detail')}"
                             for r in check_blocks_semantic(z)]
            if args.plan:  # holes 对齐（T2 原样消费传透）
                plan = _read_json(args.plan)
                pzones = {pz["id"]: pz for pz in plan.get("zones") or []}
                for z in doc.get("zones") or []:
                    pzone = pzones.get(z.get("zone")) or (
                        (plan.get("zones") or [None])[0])
                    if pzone:
                        for r in check_holes_alignment(z, pzone):
                            (errs if r.get("severity") in ("FAIL", "error")
                             else warnings).append(r["detail"])
        else:
            # 房间级（R-01~R-09）：rooms DSL + --geom skeleton（DSL 自动 normalize）
            if not args.geom:
                _emit({"valid": False,
                       "errors": ["rooms 级校验需 --geom <skeleton 几何或 skeleton.json>"]},
                      args.out)
                return 2
            from floorgeom.normalize import SchemaError, normalize_rooms
            try:
                skel_model = _load_skeleton_model(args.geom)
                geom_model = normalize_rooms(doc, skel_model)
            except SchemaError as ex:
                _emit({"valid": False, "errors": [str(ex)]}, args.out)
                return 2
            reports = check_floor(
                geom_model,
                outline_polygons=_outline_polys_from_skeleton(skel_model) or None)
            for r in reports:
                (errs if r.get("severity") in ("FAIL", "error")
                 else warnings).append(f"[{r.get('rule')}] {r.get('detail')}")
    elif args.plan:
        # plan 轮廓级摄取 + 多 zone 对齐
        plan = _read_json(args.plan)
        errs += check_outline_plan(plan) + check_alignment_zones(plan)
    else:
        errs.append("需 --plan 或 --dsl")
    _emit({"valid": not errs, "errors": errs, "warnings": warnings}, args.out)
    return 0 if not errs else 1


def _cmd_readback(args) -> int:
    from dxfkit.readback import readback, to_room_graph
    layer_map = _read_json(args.params) if args.params else None
    graph = readback(args.dxf, layer_map=layer_map, units=args.units)
    _emit(to_room_graph(graph) if args.graph else graph, args.out)
    return 0


def _cmd_reconcile(args) -> int:
    from floorgeom.reconcile import reconcile
    decl = _read_json(args.decl)
    graph = _read_json(args.graph)
    report = reconcile(decl, graph)
    errors = [f for f in report if f["severity"] == "error"]
    _emit({"valid": not errors, "findings": report}, args.out)
    return 0 if not errors else 1


def _cmd_sync(args) -> int:
    from flowops.sync import sync_floor
    old = _read_json(args.decl) if args.decl else {"rooms": [], "doors": [], "walls": []}
    result = sync_floor(args.dxf, args.params or "", old, units=args.units)
    _emit(result, args.out)
    return 0 if result.get("verdict") == "pass" else 1


def _cmd_pack(args) -> int:
    from flowops.pack import init_state, pack_mission, register_mission
    init_state(args.project)
    # push 预筛：按类型从 golden.db 取 pattern 命中段（pack 时机器注入，K1 最小注入）
    knowledge = []
    if args.db and args.type:
        try:
            from goldlib.query import query
            hits = query(args.db, kind="pattern", type=args.type)
            for h in hits[:5]:  # 最多注入 5 段（避免上下文膨胀）
                # DSL 片段从 source 文件锚点取（DB 只存指针，learn_gold §6 纪律）
                dsl = _extract_pattern_dsl(h.get("source") or "")
                if dsl:
                    knowledge.append({"kind": "pattern", "pain": h.get("pains", ""), "dsl": dsl})
        except Exception:
            pass  # 无 db/无命中 → 不注入，主 agent 可 pull
    mission = pack_mission(args.node, args.project, inputs={}, knowledge=knowledge)
    register_mission(args.node, args.project)
    _emit({"mission": mission["node"], "status": mission["status"],
           "knowledge_injected": len(knowledge)}, args.out)
    return 0


def _extract_pattern_dsl(source: str) -> str:
    """从 pattern 源文件提取 DSL 片段（`DSL 片段:` 到下一个 `##` 之间）。"""
    from pathlib import Path
    p = Path(source)
    if not p.exists():
        return ""
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except Exception:
        return ""
    in_dsl = False
    out = []
    for line in lines:
        if line.startswith("DSL 片段"):
            in_dsl = True
            continue
        if in_dsl:
            if line.startswith("## ") or line.startswith("决策依据") or line.startswith("配套校验"):
                break
            out.append(line)
    return "\n".join(out).strip()


def _cmd_deliver(args) -> int:
    from flowops.deliver import deliver
    building = deliver("project", args.project)
    _emit({"building": building.get("project"), "floors": len(building["floors"])}, args.out)
    return 0


def _cmd_gold(args) -> int:
    if args.gold_command == "reindex":
        from goldlib.reindex import reindex
        reindex(args.project, args.out)
        _emit({"reindexed": True, "db": args.out}, None)
        return 0
    if args.gold_command == "query":
        from goldlib.query import query
        params = json.loads(args.params) if args.params else {}
        hits = query(args.project, kind=params.get("kind", "case"),
                     pain=params.get("pain"), geom_facts=params.get("geom_facts"),
                     type=params.get("type"))
        _emit({"hits": hits}, args.out)
        return 0
    if args.gold_command == "reverse":
        from goldlib.reverse import reverse
        graph = _read_json(args.graph)
        decl = reverse(graph)
        _emit(decl, args.out)
        return 0
    if args.gold_command == "replay":
        from goldlib.replay import replay_case
        result = replay_case(args.project)
        _emit(result, args.out)
        return 0 if result.get("status") == "PASS" else 1
    if args.gold_command == "ingest":
        from goldlib.ingest import ingest
        result = ingest(args.case, args.project, args.out)
        _emit(result, None)  # 输出走 stdout——args.out 是 db 路径，写出会覆盖 golden.db
        return 0 if result.get("status") == "ingested" else 1
    return 1


def _cmd_draw(args) -> int:
    """draw 是逐构件原语（非渲染器）——CLI 入口验证包可用。"""
    import dxfkit.draw  # noqa: F401  lazy import，仅验证可导入
    _emit({"draw": "主 agent 直接 import dxfkit.draw 逐构件调用"}, None)
    return 0


def _cmd_svg(args) -> int:
    from dxfkit.svg import export
    export(args.dxf, args.out)
    _emit({"exported": args.out}, None)
    return 0


def _cmd_init(args) -> int:
    """init 工作区（一次搞定，后续步骤不用一直传/算 workdir）：
    --project-id → 建 skill-work/{projectID}/ + 写 marker（projectId 锚定），返回 workdir。

    后续命令 --project-id 复用同一 projectId（CLI 内部算同一 workdir），或 --project 直传
    init 返回的 workdir。交付（S4）跟 tool 交际见 steps/step-04-deliver.md（CLI 产中间产物 +
    build 脚本，tool 注册平台模型/组装 building.json）。
    """
    if not args.project_id:
        _emit({"valid": False, "error": "init 需 --project-id"}, args.out)
        return 1
    workdir = resolve_skill_workdir(args.project_id)
    os.makedirs(workdir, exist_ok=True)
    marker = {
        "projectId": args.project_id,
        "workdir": workdir,
        "kind": "aidxf-work",
    }
    marker_path = os.path.join(workdir, ".aidxf-work.json")
    with open(marker_path, "w", encoding="utf-8") as f:
        json.dump(marker, f, ensure_ascii=False, indent=2)
    _emit({"valid": True, "projectId": args.project_id, "workdir": workdir,
           "marker": marker_path}, args.out)
    return 0


def _cmd_state(args) -> int:
    """state 编排：sync（补缺）/ advance（推进单 mission）/ reconcile（全量对账）。

    只做状态记录，不自动派发 subagent、不自动跑 check/reconcile——决策归主 agent。
    """
    from flowops.orchestrate import advance_status, reconcile_state, sync_missions
    if not args.project:
        _emit({"valid": False, "error": "需 --project"}, args.out)
        return 1
    if args.state_command == "sync":
        result = sync_missions(args.project)
        _emit({"valid": True, "created": result["created"],
               "existing": result["existing"]}, args.out)
        return 0
    if args.state_command == "advance":
        if not args.node:
            _emit({"valid": False, "error": "advance 需 --node"}, args.out)
            return 1
        status = advance_status(args.project, args.node)
        _emit({"valid": True, "node": args.node, "status": status}, args.out)
        return 0
    if args.state_command == "reconcile":
        report = reconcile_state(args.project)
        _emit({"valid": True, "missions": report}, args.out)
        return 0
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "init": _cmd_init,
        "validate": _cmd_validate,
        "preprocess": _cmd_preprocess,
        "derive": _cmd_derive,
        "normalize": _cmd_normalize,
        "check": _cmd_check,
        "draw": _cmd_draw,
        "svg": _cmd_svg,
        "readback": _cmd_readback,
        "reconcile": _cmd_reconcile,
        "sync": _cmd_sync,
        "pack": _cmd_pack,
        "state": _cmd_state,
        "deliver": _cmd_deliver,
        "gold": _cmd_gold,
    }
    handler = handlers.get(args.command)
    if handler is None:
        print(f"aidxfv3: 子命令 '{args.command}' 未接通", file=sys.stderr)
        return 1
    # --project-id 优先：CLI 内部算 skill-work/{projectID} 覆盖 args.project（init 除外——
    # init 本身用 project_id 建工作区，不需要覆盖）。
    if args.command != "init":
        _apply_project_id(args)
    try:
        return handler(args)
    except FileNotFoundError as ex:
        # 不静默：输入文件缺失 → 结构化错误 + exit 1
        _emit({"valid": False, "error": "file_not_found", "path": str(ex.filename)},
              getattr(args, "out", None))
        return 1
    except Exception as ex:  # 兜底：不裸 traceback 假成功
        _emit({"valid": False, "error": str(ex)}, getattr(args, "out", None))
        return 1


if __name__ == "__main__":
    sys.exit(main())
