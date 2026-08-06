# Script-as-Source：Python 脚本为 IFC 唯一事实源

**日期：** 2026-08-06
**状态：** 已确认（用户裁决：PARAMS 顶层常量 + 存量 design JSON 直接下线）
**前置：** 2026-08-06 design JSON 边界讨论——design JSON 只能表达平面方案级内容（墙/开口/板/层高），无法完全表示 IFC；REST edit API 与 design JSON 双轨分叉；regenerate 会覆盖 IFC 侧修改。

## 决策（用户裁决）

1. **Python 构建脚本是 IFC 的唯一一一对应表示**。design.json / params.json 均为辅助信息：不是完整信息、不是 IFC 标注文件、不进版本、不做 diff。
2. 工作流：AI 生成完整 Python 脚本 → 直接生成 IFC。
3. design JSON diff 引擎废弃（design_diff.py 删除）；大版本 diff 借鉴 design JSON 之前的直接 IFC diff（ifcdiff，现役 diffing.py）。
4. 版本模型不变：大版本回退 + 前置后置 5-10 步短回溯暂存链（WPS 式，不做完整链）。
5. 存量 design JSON 管线（regenerate / DesignPanel design 表单 / design 大版本）**直接下线**，老模型仅保留 IFC 快照。

## 核心模型

```
scripts/v{n}.py      ← 唯一事实源：AI 生成的完整构建脚本
versions/v{n}.ifc    ← 派生物：脚本受限执行的产物
staging（5-10 步）    ← 短回溯链：每步 = 脚本一次修改的快照；保存 → 大版本 v{n}
```

- 回退 = 恢复 `scripts/v{n}.py` → 重跑 → IFC
- AI 下次介入时输入：当前脚本 + 脚本 diff + IFC 语义 diff 摘要 → **增量修改而非重写**（skill 纪律约束）

## 脚本契约（进 skill MUST）

1. 脚本头部必须有 `PARAMS = {...}` 顶层字面量 dict（JSON-compatible）：所有可调参数集中于此
2. 确定性身份：构件 GlobalId 用 `uuid5(NAMESPACE_AI_IFC, key)`，写 `Pset_AIIFC.designKey`（沿用现 build_script_template 机制，抽为 flows 公共 helper）
3. 入口：`build(params: dict, out_path: str) -> None`；脚本 `__main__` 读 PARAMS 调 build
4. 产物必须过 `ifcopenshell.validate`

## diff 引擎（三层）

| 层 | 对象 | 受众 |
|---|---|---|
| 脚本 unified text diff | scripts/v{n-1}.py ↔ v{n}.py | AI（下次输出的上下文） |
| IFC 语义 diff（ifcdiff 属性级 GlobalId 对齐） | versions/v{n-1}.ifc ↔ v{n}.ifc | 用户（Diff Viewer 不变） |
| IFC 指纹 diff | 外部上传模型兜底 | 不变 |

## UI（设计师为主）

- DesignPanel 重构：解析当前脚本的 PARAMS → 生成表单；「下钻」→ 脚本编辑器（textarea/轻量高亮即可，不引 Monaco——YAGNI）
- 表单提交 / 脚本保存 = staging 一步；「保存版本」= 跑脚本 → 大版本

## 执行安全

edit-service 以 subprocess + timeout（60s）+ rlimits（CPU/内存）+ 独立临时目录跑脚本；失败 → 422 + stderr 截尾 2KB。容器部署天然无网（compose 内网）。

## 废弃清单

- 删：`design_diff.py`（+ 其测试改造）、`regenerate.py` design JSON 管线、routes_design 的 design JSON 端点
- 改：`design_staging.py` → 脚本快照 staging；`design_versions.py` → script_versions（scripts/v{n}.py 为主、designs/v{n}.json 不再产生）
- 前端：designEdit.ts / DesignPanel.tsx 重构；client.ts design 方法换 scripts 端点
- Go：design.go 代理路由随 edit-service 端点调整

## 工作项

- W-0011：edit-service scripts 管线（staging/save/rollback/run 沙箱 + 端点）
- W-0012：diff 引擎切换（脚本 diff + design_diff 退役）
- W-0013：前端 DesignPanel 重构（PARAMS 表单 + 脚本编辑器）
- W-0014：skill 契约更新（SKILL.md MUST + PLAN_DXF_IFC.md 重写 + flows helper 抽取）
- W-0015：design JSON 下线 + 文档声明（site design-edit 重写 + 边界声明）
- W-0016：AI 循环接入（chat 编排把脚本 diff 注入下次 prompt）

依赖序：W-0014（契约）→ W-0011 → W-0012 → W-0013 → W-0015 → W-0016
