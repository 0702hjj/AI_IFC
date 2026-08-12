---
name: aiifc
description: Thin IfcOpenShell reference skill for IFC model authoring via ifcopenshell.api, including spatial structure, geometry, openings, materials, psets and design-review workflows.
version: 0.1.0
license: LGPL-3.0
compatibility: Documentation/reference bundle for ifcopenshell API surfaces.
metadata:
  project: aiifc
  package-name: ifcopenshell
---

# AI_IFC SDK Skill

## Philosophy

- Thin reference skill: docs only, no SDK source code bundled.
- Agent reads these docs, then writes ifcopenshell.api code directly (not MCP tool calls).
- Python runtime: needs `ifcopenshell` + `ifcquery` + `numpy` (see `requirements.txt`; PyPI releases, no local source). Use whichever Python has them installed — system `python3` often lacks ifcopenshell.

## MUST Requirements

**Reading:**
1. Read `references/SDK_OVERVIEW.md` and `references/docs/api/README.md` before choosing usecases.
2. Read the exact usecase Markdown page (`docs/api/<pkg>.<usecase>.md`) for every usecase you call.
3. Read `references/MODELING_WORKFLOWS.md` before building your first model.
4. **Read `references/SPATIAL_QUALITY.md` BEFORE framing any design JSON** — footprint articulation (CP-05), door swing clearance (GI-08), stair continuity (GI-09) must be internalized up front so the design JSON is born compliant. Also read `references/DESIGN_PATTERNS.md` before choosing massing/facade/spatial organization.
5. **Component recipes — consult before building any element**: check `references/docs/design/` for a matching recipe. The index is in `docs/design/README.md`.

> **Optional workflow**: when a task benefits from staged planning (assist a designer from idea to IFC), consult `workflows/PLAN_DXF_IFC.md` — plan → DXF → IFC. It is a **selective feature, not mandatory**; skip it entirely for simple direct builds (`simple wall/slab` MUST #19) or when the user's input already targets a specific stage.

**API usage:**
6. All API calls use **keyword arguments**; the first positional argument is always `model`.
7. Use `ifcopenshell.api.run("<package>.<usecase>", model, **kwargs)`.
8. Follow the documented API signatures exactly — do not invent parameters.

**Skeleton:**
9. **Skeleton first**: build Project→Site→Building→Storey spatial tree before any element or geometry.
10. **Every element needs a container**: always `spatial.assign_container`. No orphan elements.

**Geometry:**
11. **If a product has geometry, it needs placement**: `geometry.edit_object_placement` for every product with a body representation.
12. **`create_2pt_wall` returns the representation but does NOT assign it** — always `geometry.assign_representation` separately.

**Opening:**
13. **Set world coordinates for openings before `feature.add_feature`** (it converts world → relative automatically). Never set "wall-local" coordinates manually.
14. **Opening thickness must exceed wall thickness** (≥ 1.5×) to fully penetrate.

**Normativity:**
15. **Pset applicability**: before `pset.add_pset`, verify via `PsetQto.get_applicable_names()` (see PSET_REFERENCE.md).
16. **PredefinedType enum**: verify the value is in the entity's allowed enum list (see ENTITY_SPECS.md).
17. **Pset + material coverage**: every product class must get ≥1 pset AND ≥1 material; spot-check with `util.element.get_psets(e)` / `get_material(e)`.

**Generation (script is the single source of truth):**
18. **Complex buildings**: MAY be framed with a design JSON **draft** first (auxiliary planning info, NOT a complete representation, NOT the deliverable) — LLM outputs parametric intent, never coordinate math. See `references/DESIGN_JSON_SCHEMA.md`. The deliverable is always a **build script** conforming to the script contract below (#25-31); `flows/design_builder.py` → `features.json` → `flows/build_script_template.py` is one way to get there.
19. **Simple single wall/slab**: may still be coded directly (Pipeline Stages).

**Validation (three layers):**
20. **During**: `tracker.snapshot()` after each step changing geometry or placement.
21. **After**: run `flows/design_review.py` once per build as a **fixed black-box check** — read its text report. If errors, fix the model against `references/SPATIAL_QUALITY.md`.
22. **Export**: `model.write()` is followed by `ifcopenshell.validate`. No model is complete without passing schema validation.

**Output:**
23. **Output paths (generic)**: generated IFC → working directory as **`model.ifc`** (write via staging copy, self-check, then atomic replace). If your host provides a specific output contract, follow that instead.
24. **No visualization rendering**: do NOT call `ifc_plot` / `ifc_render` / any image output. All verification is **text-only**: `ifcopenshell.validate` + `design_review.py` + `ifc_inspect.py`.

**Script contract (script-as-source — the build script is the single source of truth for the IFC):**
25. **PARAMS block**: every build script MUST declare a top-level `PARAMS = {...}` **literal dict (JSON-compatible)** holding all tunable parameters. Host UIs render the parameter form from PARAMS, so nothing tunable may live outside it.
26. **Deterministic identity**: every element's GlobalId MUST come from `script_lib.deterministic_guid(key)` with a stable, unique key `{storey}:{kind}:{n}`. `script_lib.create_entity` derives the GlobalId and writes `Pset_AIIFC.designKey` automatically — only entities created via raw `root.create_entity` need an explicit `script_lib.attach_design_key`, and that explicit key MUST equal the creation key (mismatch = designKey/GlobalId drift, breaks the locate chain). Same script + same PARAMS → same GlobalIds across runs and versions.
27. **Entry point**: the script MUST expose `build(params, out_path)`; the `__main__` guard calls `build(PARAMS, out)`. Verify compliance statically with `script_lib.validate_script_contract(path)`.
28. **Incremental edits, never rewrites**: modifying an existing model = **incrementally editing its existing script** (PARAMS first, then the minimal geometry logic). NEVER regenerate/rewrite the script from scratch — keep the script diff readable, it is the AI's context for the next edit.
29. **Validate exit**: script output MUST go through `script_lib.write_and_validate(model, out_path)` (model.write + ifcopenshell.validate). No script run is complete without passing schema validation.
30. **C-locate（创建点可定位）**：审查可见构件必须经 `script_lib.create_entity(...)` 创建；禁止绕过工厂直接 `root.create_entity`——工厂记录调用点供 web 端「选中构件→定位脚本」。
31. **C-scalar（web 可编辑参数为标量）**：需要 web 端编辑的参数必须是标量字面量或 `params` 引用；表达式参数只能手改脚本（edit-call 拒绝）。

## Entity Mental Model

Every element needs four components:

| Component | Usecase | What it does |
|---|---|---|
| **Entity** | `root.create_entity` | Creates the IFC entity |
| **Placement** | `geometry.edit_object_placement` | Position/rotation |
| **Representation** | `geometry.add_*_representation` + `assign_representation` | Body geometry |
| **Container** | `spatial.assign_container` | Places into a storey |

Optional: **Type** (`type.assign_type`), **Material** (`material.assign_material`), **Style/color** (`style_color.py`), **Pset/Qto** (`pset.add_pset`/`add_qto`), **Opening** (`feature.add_feature`), **Filling** (`feature.add_filling`).

## References (Reading Map)

| Doc | Role |
|---|---|
| `references/SDK_OVERVIEW.md` | Package map, entity-relationship model, typical patterns |
| `references/MODELING_WORKFLOWS.md` | Pipeline stages, placement/opening/grounding discipline, **Design JSON 框定**, ifc_inspect |
| `references/DESIGN_JSON_SCHEMA.md` | Design JSON format contract (wall forms, normalization rules, full example) |
| `references/DESIGN_PATTERNS.md` | Design patterns: massing, facade, structure, circulation, spatial |
| `references/ENTITY_SPECS.md` | Entity attribute tables (REQ/OPT/type/source) |
| `references/PSET_REFERENCE.md` | Applicable Pset/Qto per element type |
| `references/SPATIAL_QUALITY.md` | Design review rules (SS/GI/PR/RH/MC/CP/FD/SQ) |
| `references/docs/api/README.md` + `<pkg>.<usecase>.md` | API index (14 categories, 103 usecases) + exact signatures |
| `references/docs/flows/README.md` + `*.py` | Runnable per-stage code and tools (tracker / design_review / ifc_inspect / **script_lib** / dxf_from_design) |
| `references/docs/design/README.md` + recipes | Component building recipes (stairs, roof, windows, parapet, balcony) |
| `templates/build_skeleton.py` | Minimal complete model (skeleton + wall + slab) — copy and edit |
| `workflows/PLAN_DXF_IFC.md` | **工作流编排**：plan（可选草稿）→ script（事实源）→ IFC 的阶段顺序与跳步规则（辅助设计师） |

## Installing the skill

This skill is an agent-agnostic directory bundle (SKILL.md + references/). Any tool supporting the Anthropic Agent Skills layout can load it:

**opencode:**
```bash
# Project-level: add to opencode.json
# "skills": { "paths": ["skills"] }
# (aiifc is already under skills/aiifc in this repo)

# Or global (symlink or copy):
ln -s $(pwd)/skills/aiifc ~/.config/opencode/skills/aiifc
```

**Claude Code:**
```bash
# Copy or symlink to the Claude skills directory:
ln -s $(pwd)/skills/aiifc ~/.claude/skills/aiifc
```

**Cursor / other Agent Skills tools:**
```bash
# Copy the skill directory to the agent's skills path:
cp -r skills/aiifc <agent-skills-dir>/aiifc
```

**Distributable bundle:**
```bash
python tools/skill_pack.py --archive   # produces skills/dist/aiifc.tar.gz (default skill: aiifc)
tar xzf skills/dist/aiifc.tar.gz -C ~/.config/opencode/skills/
```

## Hooks — 校验即事件（拉 → 推，可选增强）

默认纪律是「拉」：agent 写脚本后**自己记得**调 `validate_script_contract`（MUST #27）。
hooks 把它变成「推」：支持 hooks 的环境里，agent 用 write/edit 写入/编辑**构建脚本**
（`*.py` 且含 `def build(params` 或 `PARAMS =` 契约特征）时，自动触发契约校验
（+ 可选沙箱试跑），结果作为**事件**回填——失败即事件，不污染主上下文。

> **hooks 是增强不是替代**：不支持 hooks 的环境（Cursor 等）维持手动校验路径——
> agent 仍按 MUST #27 调 `script_lib.validate_script_contract(path)`，出口必经
> `script_lib.write_and_validate`（MUST #29）。hooks 触发失败也静默跳过，绝不阻塞工具执行。

### 事件 URI

| 事件 URI | 含义 |
|---|---|
| `aiifc://script/validated` | 契约校验通过（无 modelId 上下文） |
| `aiifc://script/validation-failed` | 契约校验失败（无 modelId 上下文） |
| `aiifc://model/{id}/script/validated` | 契约校验通过（脚本路径含 modelId） |
| `aiifc://model/{id}/script/validation-failed` | 契约校验失败（路径含 modelId） |

`{id}` = modelId（`^m_[0-9a-f]{16}$`），从脚本路径启发式提取（文件名 stem 或祖先目录名匹配；
demo 布局 `staging/{modelId}.py` / `models/{modelId}/scripts/v{n}.py`），提取不到则用无 modelId 的 URI。
完整说明见 `hooks/README.md`。

### 安装

- **opencode**：软链/复制 `hooks/opencode-plugin.ts` 到 `.opencode/plugin/`（如
  `.opencode/plugin/aiifc-hooks.ts`）。Python 探测：`AIIFC_PYTHON` → 仓库
  `services/ifc/.venv/bin/python`（有 ifcopenshell）→ `python3`。
- **Claude Code**：把 `hooks/claude-settings.json` 的 `hooks` 块合并进
  `~/.claude/settings.json`（把 `{{SKILL_DIR}}` 换成 skill 安装路径），PostToolUse
  hook 指向 `hooks/validate_script.sh`。
- 两种形态共享 `hooks/validate_script.py`（校验逻辑单点定义，无 ifcopenshell 时
  自动降级为纯静态 ast 校验；静态校验只用标准库）。

## Demo integration (AI_IFC viewer — optional, not part of the distributable skill)

When this skill runs **inside the AI_IFC demo** (opencode serve + viewer), the host provides a fixed contract that overrides the generic output paths (MUST #23). This section is maintained in-repo for the demo and is **not** part of the distributable skill bundle.

- Build scripts (`.py`) → `examples/`; generated IFC files → **`data/uploads/{modelId}.ifc`** (write via a staging copy, self-check, then atomic replace; `modelId` is injected via system context). Build scripts MUST follow the script contract (#25-31): `PARAMS` block, deterministic GlobalIds, `build(params, out_path)` entry, validate exit.
- **design.json** (optional planning draft only, MUST #18 — auxiliary info, not versioned, not diffed): keep it in your scratch space; the demo does NOT persist or archive it. Only the build script is archived with the version.
- Python runtime: **always `services/ifc/.venv/bin/python`** (run from the repo root; the edit-service uv project env has ifcopenshell / ezdxf / ifcquery preinstalled — the root `.venv` does NOT). Equivalent: `cd services/ifc && uv run python ...`.
- Agent rules live in `.opencode/agent/ifc-demo.md` (write scoping, staging, atomic-replace, no viewer HTTP calls); the Go server auto-handles commit/version/XKT-reconvert on `file.edited` + `session.idle`.