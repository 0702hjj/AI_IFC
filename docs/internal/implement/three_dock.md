# three_dock 待办清单

## 1. aiifc 迭代升级：落盘交付全部交给脚手架，减轻 LLM 负担

**目标**：aiifc（bim 入口）迭代时，LLM 只负责"建模决策 + `gen_ifc()` 实现"，落盘交付（输出路径、溯源、校验、审计、错误报告）全部下沉给脚手架执行代码，LLM 不再自行管理文件落盘。

**参考逻辑**：`AI_CAD/skills/aidxfv1`（cadpy 编排模式，已验证可用）——

- **插件式契约**：脚手架用 AST 静态发现/校验 `gen_dxf()`，LLM 只填函数体（对应 aiifc 侧为 `gen_ifc()` / 脚本式 cad→设计参数转换器）；参考 `scripts/packages/cadpy/src/cadpy/metadata.py`（八项运行前检查）与 `AI_CAD/skills/aidxfv1/references/VALIDATION.md`
- **CLI 全权拥有输出路径**：脚本不写文件，sibling 规则 + `--output` 重定向 + 冲突报错；参考 `generation.py` 的 `_apply_dxf_output_overrides` / `_write_dxf_payload`
- **溯源注入**：产物头部写入 `cadpy:sourcePath/sourceHash`，改源码必重生成、增量可判（bim 侧对应"cad 产物哈希注入 IFC，检测 IFC 过期"）；参考 `file_metadata.py`
- **分层监察、报错可返回重修**：AST → 执行 → 落盘 → 结构 audit（`audit_dxf.py`）→ 业务 review（错误码化 JSON findings），每环 LLM 读错重修重跑；执行确定性、可重放，重修成本低
- **语义直读替代几何猜测**：cad 产物挂 AIBIM XDATA/XRECORD（IfcWall/材料/高度/GUID），aiifc 转换脚本纯查表生成设计参数参考，确定性、可重放；对应架构文档 4.3.6 脚本式转换方向

**迁移要点**：按上述模式为 aiifc 封装同类编排层（发现 → 校验 → 执行 → 落盘 → 溯源 → 审计），复用 aiifc 现有骨架/容器/placement/pset/design 流程与自检机制，仅替换输入契约与交付通道。

## 2. aiifc 结构升级：知识库形态 → 步骤化工作流引擎形态

**现状问题**：aiifc 为"知识库形态"——SKILL.md(177 行)+ 7 份 references 平铺共 1116 行，LLM 每次任务需全量读入并自行组织执行顺序，context 消耗大、执行纪律靠自觉、无断点恢复、验证结论无证据分级。

**目标**：改造为"工作流引擎形态"——SKILL.md 只留总纲（默认行为 + 意图开关 + 流程概览），执行细节拆入 `steps/` 分步文件按需加载，建模过程有运行记录、可断点续跑、验证证据分级。

**参考逻辑**：`AI_CAD/resource/aiblueprint` 的 `agents-config/skills/apex/`（Melvynx/aiblueprint,MIT，成熟多步骤 skill 样板）——

- **渐进披露**：SKILL.md 仅 ~60 行总纲，"Load only the current step"；细节在 `steps/step-00-init.md … step-10-verify.md` 按需加载，省 context
- **可恢复运行记录**：minimal resumable run record + `-r <id>` 断点续跑（对应 aiifc 多楼层/多构件长任务中断恢复）
- **验证证据分级与失败诚实分类**：区分 local/static、provider、deployment、live 四级 proof；检查结果分类 passed / failed-by-change / pre-existing / unavailable / not-run（对应 aiifc 自检机制的报告规范化）
- **意图开关**：一个 skill 多档行为（如 `-x` 对抗审查、`-e` 低预算、`-t` 是否写测试）；aiifc 可设"快速建模/全量自检/仅转换不建模"等档位

**aiifc 侧 steps/ 拆分建议**：00 读输入契约（plan/cad 落盘 + 设计 JSON）→ 01 转换设计参数参考 → 02 骨架/容器建立 → 03 逐类构件建模（placement/pset/design 复用现有流程）→ 04 空间质量自检（SPATIAL_QUALITY.md 转为检查清单）→ 05 报错重修循环 → 06 IFC 落盘交付 + 溯源注入 → 07 交付报告（证据分级）。

**迁移要点**：references/ 七份文档不删除，降级为"步骤内按需引用的规范源"；与待办 1 的脚手架编排层配套——脚手架管落盘交付，steps/ 管执行纪律。同套结构同步应用于 aidxfv1 v1.1 升级。
