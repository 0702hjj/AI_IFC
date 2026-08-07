# W-0020: 文档滞后清理批次（v0.2 叙事）

- **状态：** open
- **优先级：** P2
- **Milestone：** v0.2
- **来源：** 2026-08-07 重评估滞后点清单
- **执行者/分支：** （领取时填）

## 背景

post-M5 重评估发现的文档滞后/漂移，随 v0.2 批次一并清理。

## 清单

1. `skills/aiifc/workflows/PLAN_DXF_IFC.md:76`：diff 表仍列已删除的 IFC 指纹 diff（spec:41 已销账）——删行
2. `docs/internal/architecture/ai-bim-agent-page.md:133`：死链 `docs/internal/ai-integration.md`（已删）——改指 site 的 AI 接入页
3. `docs/internal/architecture/ai-bim.md`（2026-07-30）与 ai-bim-agent-page.md（08-03）两代并存：ai-bim.md 加 superseded 注记指向 agent-page + script-as-source spec（不删，保留决策史）
4. `research/ifc/MCP_API.md`：旧路径 `/CADapi/...` → `~/projects/work/IfcOpenShell`
5. **W-0008**（本项内完成并关闭）：config.mts 英文 nav 补 Viewer Usage → /en/viewer/library
6. site roadmap：已完成区补 v0.2 批次条目（本批各项 done 时回填）
7. AI_CAD 侧仅标记不动手：aidxfv2/SKILL.md frontmatter `name: aidxfv1` 误发布风险——在 AI_CAD 发现清单里记录（不修改同事文件，报告注明）

## 验收标准

- 逐项销账可 grep 验证；docs:build + check:api 绿
- W-0008 关闭（英文 nav 生效）

## 测试要求

- vitepress build 死链拦截即验证
