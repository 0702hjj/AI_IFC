# 迁移计划：text-to-cad `dxf` skill → `AI_IFC/skills/aidxfv1`

- **优先级：P1**
- 状态：已完成（2026-08-04，全部验证门禁通过）
- 日期：2026-08-04

## 决策（已确认）

- **目标位置**：`AI_IFC/skills/aidxfv1`（`opencode.json` 已注册 `skills` 路径，与 `aiifc`/`simplecadapi` 同级）
- **cadpy 引擎**：裁剪为 DXF 闭包（仅依赖 `ezdxf`，去掉 `build123d`/`cadquery-ocp`）
- **SKILL.md**：去掉全部跨 skill 引用（`$cad`/`$cad-viewer`/`$sendcutsend`），改为自带验证手册

## 源

`AI_CAD/resource/text-to-cad/skills/dxf/`（MIT License，earthtojake/text-to-cad）

## 目标结构

```
AI_IFC/skills/aidxfv1/
├── SKILL.md              # 重写：name=aidxfv1、无跨skill引用、加 aiifc 式 frontmatter
├── LICENSE               # 原样保留（MIT，须保留版权声明）
├── requirements.txt      # 保留：ezdxf + --editable ./scripts/packages/cadpy
├── agents/openai.yaml    # 原样保留（信息性）
├── references/
│   └── VALIDATION.md     # 新增：自包含的 DXF 校验手册
└── scripts/
    ├── dxf/              # 原样拷贝：__main__.py / __init__.py / cli.py / render_payload.py
    └── packages/cadpy/   # 裁剪版（见步骤 2-3）
```

## 实施步骤

### 1. 拷贝入口与元数据

- `scripts/dxf/` 四个文件原样拷贝（`__main__.py` 的 sys.path 引导、`cli.py` 的 argparse、`render_payload.py` 的 viewer 渲染载荷均与 STEP 无关）
- `LICENSE`、`agents/openai.yaml`、原 `requirements.txt` 拷贝

### 2. 裁剪 cadpy（核心工作）

保留这些纯 stdlib/轻依赖模块（已逐一核实无 `from cadpy.*` 依赖或仅依赖轻模块）：

- `__init__.py`, `py.typed`
- `metadata.py`（AST 检测 gen_dxf/gen_step）
- `file_metadata.py`（溯源元数据注入）
- `cli_logging.py`, `generation_status.py`
- `catalog.py`（CadSource / StepImportOptions / source_from_path / iter_cad_sources）
- `selector_types.py`, `cad_ref_syntax.py`

不拷贝：`step_export` / `step_scene` / `step_metadata` / `step_hash` / `step_artifact(s)` / `step_targets` / `glb` / `glb_topology` / `glb_mesh_payload` / `stl` / `threemf` / `assembly*`（assembly/assembly_spec/assembly_composition/assembly_export/assembly_flatten）/ `analysis` / `render` / `api` / `lookup` 等 STEP/GLB 模块。

### 3. 改造 `generation.py`（2351 行 → 保留但轻量化）

- 把第 16-68 行的重依赖 import（`analysis`, `assembly_composition`, `assembly_spec`, `glb`, `glb_topology`, `render`, `step_export`, `stl`, `threemf`, `step_scene`, `step_targets`）全部改为**函数内懒加载**（DXF 路径永不调用，故不会执行）
- 修改 `_display_path`(203-208)：去掉 `REPO_ROOT` 相对化，改为纯 `resolved.as_posix()`（消除对 `assembly_spec` 的模块级依赖）
- 保留 DXF 路径全部函数：`generate_dxf_targets`(2265)、`_selected_specs_for_targets`(1893)、`_validate_dxf_target`(2071)、`_apply_dxf_output_override(s)`、`run_script_generator`/`_run_script_generator_inner`(1051/1076)、`_normalize_dxf_payload`(790)、`_write_dxf_payload`(1024)、`_generated_dxf_summary`(2093)、`_parse_cli_target_specs`(237) 等；STEP 专属函数保留但引用懒加载
- `cadpy/pyproject.toml`：去掉 `build123d`、`cadquery-ocp` 依赖（保留 setuptools 打包配置）

### 4. 重写 `SKILL.md`

- frontmatter：`name: aidxfv1`、`license: MIT`、`compatibility`、`metadata.project: aidxfv1`（对齐 aiifc 风格）
- 删除 `$cad`/`$cad-viewer`/`$sendcutsend`；Handoff 段改为：用 ezdxf 校验 + 可选 `ezdxf.addons.drawing` + matplotlib 出 PNG 自查
- 保留 Defaults（mm 单位、1:1 modelspace、闭合切割轮廓、折弯/切割分层）、Workflow（brief→源码→`python scripts/dxf`→校验）、Validation、报告纪律（"report only checks that actually ran"）
- 加 Provenance 段注明源自 earthtojake/text-to-cad（MIT）

### 5. 新增 `references/VALIDATION.md`（自包含，替代原 cad skill 的验证参考）

- 校验清单：按类型/图层统计实体、LWPOLYLINE closed 标志、extents 核对、逐项尺寸验证、bend/cut 图层命名规则、报告纪律

### 6. 验证（完整性门禁，全部通过才算完成）

1. `uv venv && uv pip install -r requirements.txt`，**确认不安装 build123d/cadquery-ocp**（`uv pip list`）
2. `python -c "from cadpy.generation import generate_dxf_targets"` 在无 build123d 环境下导入成功
3. 冒烟：用 `test_standalone_source.py` 的 40×20 矩形 `gen_dxf()` 夹具 → `python scripts/dxf src.py` → 断言同名 `.dxf` 落盘且非空、注入源码 hash 元数据
4. 行为等价验证：手动复现该测试类 5 个断言（纯 dxf 源识别 / urdf 无 gen_step 报错 / 显式 target 解析 sibling 路径 / 目录扫描跳过 dxf 源 / 生成写盘）
5. `python scripts/dxf --help`、缺失 `gen_dxf()` 时的报错路径
6. `grep` 审计 `generation.py` 无残留模块级重依赖

## 风险与权衡

| 项 | 说明 |
|---|---|
| 懒加载转换遗漏 | 用"无 build123d 环境下完整 import + 冒烟跑通"作为强制门禁兜底 |
| `_display_path` 改动 | 错误信息不再显示仓库相对路径，仅影响可读性 |
| 保留 STEP 死代码 | 完整性优先；上游再同步时改动面小（仅 import 转换 + `_display_path` 两处） |
| 目录扫描 | `iter_cad_sources` 会扫 `.step` 文件，DXF 场景无影响 |
