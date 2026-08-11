# 仓库结构

> 平台框架：两个对等逻辑（AI 生成 IFC / AI 生成 CAD）+ Agent 工作流推荐项；功能块横切（skill ×2 ↔ services ×2 ↔ 共享可选运行时）。详见 [框架 spec](https://github.com/0702hjj/AI_IFC/blob/main/docs/superpowers/specs/2026-08-11-platform-framework-design.md)。

```
AI_IFC/
├── skills/                   # ① AI 生成 skill 封装（agent-agnostic，可分发）
│   ├── aiifc/                #   IFC 生成/修改（ifcopenshell）
│   └── aidxfv/               #   CAD 生成/修改（v1 通用 DXF / v2 建筑平面管线；由 AI_CAD/skills 迁移收敛）
├── services/                 # ② 业务逻辑核心（diff + 面向前端修改的接口协议）
│   ├── ifc/                  #   IFC 段（FastAPI + IfcOpenShell，:8100）
│   └── cad/                  #   CAD 段（待建，与 ifc 同构）
├── web/                      # ③ 共享可选运行时 · 前端（React 19 + xeokit，:5173）
├── server/                   #   · Go 网关（:8090，REST 入口 + 编排 + 存储抽象）
├── converter/                #   · Node 转换器（IFC → XKT）
├── mcp/                      #   · MCP 桥（可选）
├── scripts/smoke.sh          #   · 端到端冒烟
├── data/                     #   · 运行时数据（gitignored，services/ifc 与 server 共享）
├── AI_CAD/                   # CAD skill 域 + 调研（aidxfv1/aidxfv2 已迁入 skills/aidxfv，research 保留）
├── docs/
│   ├── site/                 # 唯一公开文档站源（VitePress）
│   │   ├── .vitepress/config.mts
│   │   ├── index.md
│   │   ├── guide/  viewer/  development/  reference/  project/
│   │   └── public/           # favicon、ai-tools.openapi.json 等静态资源
│   ├── internal/             # 内部计划、团队同步、阶段评估（不发布）
│   ├── work/                 # 工作项看板（审计、计划、可跟踪条目）
│   └── superpowers/          # 设计规范与实施计划
├── research/                 # 调研笔记与目标映射（内部）
├── examples/                 # 归档：SCAD 示例
├── .github/workflows/        # CI（server/web 等）与 docs（构建 + Pages 部署）
├── LICENSE                   # AGPL-3.0-only
└── NOTICE                    # 三方组件与归档代码边界
```

原 `viewer/` 目录已物理拆分：`edit-service` → `services/ifc/`、`web|server|converter|mcp-server|scripts` → 顶层同名目录、`data` → 顶层 `data/`（gitignored）；`AI_CAD/skills/aidxfv1|aidxfv2` → `skills/aidxfv/v1|v2`。SCAD 遗产代码（`src/simplecadapi/`、`skills/simplecadapi/`、根打包配置）已于 2026-08-06 移至私有归档仓 [0702hjj/SimpleCADAPI-archive](https://github.com/0702hjj/SimpleCADAPI-archive)，本仓不再包含。

## 文档边界

- `docs/site/` 是唯一公开文档站源，内容由 VitePress 构建并以 `/AI_IFC/` 为 base 发布到 GitHub Pages。
- `docs/internal/` 不进入站点导航与搜索（原 `docs/archive/` 已随 2026-08-05 清理移除，见 git 历史）。
- 各服务 README 只保留邻近源码的最小启动提示，详细说明一律链接到公开文档站。
