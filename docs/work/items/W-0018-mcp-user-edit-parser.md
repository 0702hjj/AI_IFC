# W-0018: MCP server 解析用户文件修改并标注

- **状态：** open
- **优先级：** P1
- **Milestone：** M6 多 Agent 编排
- **来源：** 2026-08-06 用户愿景
- **执行者/分支：** （领取时填）

## 背景

用户输入（上传 DXF 样例 / 上传 IFC 样例 / 修改 IFC 某部分 / 修改 DXF 某部分）需要一个 MCP server 解析对应文件的修改，并**标注是用户修改的内容**（provenance=USER），供整体 Agent 与 diff 引擎消费。本机 ~/projects/work/IfcOpenShell 源码含 ifcmcp（31 个工具，stdio）可作参考/复用。

## 涉及位置

- 新增 MCP server（独立组件，位置待定：tools/ 或独立目录）
- 与 edit-service 的版本/diff 数据互通（标注写入 diff 结果 / change log 的 provenance）

## 方案（待细化）

1. 解析能力：IFC 修改（对照当前版本跑指纹/语义 diff，定位用户改动的构件与字段）；DXF 修改（图层/实体级对比，ezdxf）
2. 标注：修改条目携带 provenance=USER + 来源（上传/手动编辑），与 AI 生成内容区分
3. 输出：结构化「用户修改事件」，供 orchestrator 注入提示词与版本系统归档

## 验收标准

- 用户上传修改后的 IFC → 输出与当前版本的差异清单，每条标注 USER
- DXF 修改同理（图层/实体粒度）
- 与 ifcdiff 语义 diff 输出 schema 对齐（diff_summary 复用）

## 测试要求

- fixture 驱动：构造「原 IFC + 用户改后 IFC」对，断言差异定位与标注正确
