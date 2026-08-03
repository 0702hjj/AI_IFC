# AI_IFC 文档站重构设计规范

**日期：** 2026-08-02  
**状态：** 已确认，待实施  
**公开地址：** <https://0702hjj.github.io/AI_IFC/>

## 1. 背景

AI_IFC 已转为公开仓库，当前活跃产品是 `viewer/` 下的 IFC 审查与编辑平台。仓库已有 README、使用指南、架构文档、接口契约、AI 接入指南和内部迭代资料，但内容分散在根目录、`docs/`、`viewer/docs/` 和各服务 README 中；原 SimpleCADAPI 文档又占用了 `docs/api`、`docs/core`、`docs/stdlib` 等通用路径。

本次迭代参考 BotRS 和 FRP-Panel 的 docs-as-code 方式：文档随主仓库提交和评审，由 VitePress 构建，并通过 GitHub Pages 自动发布。它不是独立 GitHub Wiki。

## 2. 目标与受众

第一版文档站服务于基于本仓库进行开发、部署和使用 Viewer 的人员。完成后，首次接触仓库的开发者应当能够：

1. 理解 AI_IFC 当前定位、能力边界和四组件架构。
2. 在本地启动 converter、edit-service、server 和 web。
3. 上传 IFC，完成审查、Issue、属性编辑、commit、版本和 diff 流程。
4. 找到稳定的 REST API、IFC 编辑 API 和 AI 接入说明。
5. 找到测试、调试、贡献、许可证及已知限制说明。

## 3. 本轮范围

### 3.1 必须完成

- 建立 VitePress 文档站脚手架。
- 建立面向 Viewer 的首页和导航。
- 迁移第一版公开内容。
- 合并重复内容并建立单一信息源。
- 校订过时状态和不准确表述。
- 将 SimpleCADAPI 文档和内部资料移出公开文档站。
- 在 Pull Request 中验证文档构建，在 `main` 更新后部署 GitHub Pages。
- 更新根 README，使其指向正式文档站。
- 在项目迭代计划中记录双语扩展和 API 自动生成后续任务。

### 3.2 本轮不实现

- 完整中英文双语站点。
- 根据 OpenAPI 自动生成 API 页面。
- 自动校验静态 OpenAPI 与服务实现完全一致。
- 文档版本切换。
- MCP 文档或 MCP 服务实现。
- Docker Compose；在其真正落地前，文档只能描述当前本地部署方式。

## 4. 技术方案

### 4.1 文档技术栈

- VitePress
- Node.js 22
- npm 与 `package-lock.json`
- GitHub Actions
- GitHub Pages

文档源目录为 `docs/site/`。VitePress 配置位于 `docs/site/.vitepress/config.mts`，依赖清单位于 `docs/package.json`。本地命令从仓库根目录进入 `docs/` 执行：

```bash
npm ci
npm run docs:dev
npm run docs:build
```

站点必须配置：

- `lang: "zh-CN"`
- `base: "/AI_IFC/"`
- 本地搜索
- `lastUpdated`
- clean URLs
- GitHub 编辑链接，目标路径为 `docs/site/:path`
- GitHub 仓库社交链接

### 4.2 发布流程

新增 `.github/workflows/docs.yml`：

- `pull_request` 到 `main`：安装依赖并运行 `npm run docs:build`。
- push 到 `main`：构建并部署 Pages。
- 支持 `workflow_dispatch`。
- 使用官方 `actions/configure-pages`、`actions/upload-pages-artifact` 和 `actions/deploy-pages`。
- 部署作业只在 push 到 `main` 或手工触发时执行。
- 使用独立文档部署 concurrency group。

正式地址固定为 <https://0702hjj.github.io/AI_IFC/>。

## 5. 仓库文档边界

重构后采用以下职责划分：

```text
docs/
├── package.json
├── package-lock.json
├── site/                       # 唯一公开文档站源
│   ├── .vitepress/
│   ├── index.md
│   ├── guide/
│   ├── viewer/
│   ├── development/
│   ├── reference/
│   ├── ai/
│   └── project/
├── internal/                   # 内部计划、团队同步、阶段评估
├── archive/
│   └── simplecadapi/           # 原 SCAD API/core/stdlib/legacy 文档
└── superpowers/                # 设计规范和实施计划
```

边界规则：

- `docs/site/` 中不得出现仅对内部协作有意义的实施过程。
- `docs/internal/` 和 `docs/archive/` 不进入 VitePress 导航和搜索。
- `viewer/docs/plan.md` 属于历史实施计划，不作为公开用户指南。
- API 页面以 Viewer 当前接口为主题，不能继续让 SimpleCADAPI 占用公开的 `/api` 语义。
- 各服务 README 可保留邻近源码的最小启动提示，但详细说明应链接到公开文档站，不能形成第二套完整手册。

## 6. 信息架构

### 6.1 顶部导航

- 快速开始
- Viewer 使用
- 开发指南
- API 与 AI
- 项目

### 6.2 侧边栏

```text
首页
├── 快速开始
│   ├── 项目介绍
│   ├── 环境要求与本地部署
│   ├── 上传第一个 IFC
│   └── 配置说明
├── Viewer 使用
│   ├── 模型库与模型上传
│   ├── 模型树与属性检查
│   ├── 可见性、剖切与测量
│   ├── Issue 与 3D Pin
│   ├── IFC 属性编辑
│   └── 版本与 Diff Viewer
├── 开发指南
│   ├── 总体架构
│   ├── 仓库结构
│   ├── Web 前端
│   ├── Go Server
│   ├── IFC Converter
│   ├── Edit Service
│   └── 测试与调试
├── API 与 AI
│   ├── Viewer REST API
│   ├── IFC 编辑 API
│   ├── AI 接入
│   └── OpenAPI 文件
└── 项目
    ├── Roadmap
    ├── 已知限制
    ├── 贡献指南
    └── License 与第三方组件
```

首页表达采用 FRP-Panel 的产品入口方式：先解释用途、核心能力和开始路径。开发区采用 BotRS 的指南、API、示例式渐进组织，但不在第一版制造大量细碎页面。

## 7. 内容迁移设计

| 目标内容 | 主要来源 | 处理规则 |
| --- | --- | --- |
| 首页 | `README.md`、`README.zh-CN.md` | 提炼 Viewer 定位、能力、架构和快速入口，不复制完整 README |
| 快速开始 | `docs/usage.md`、`viewer/README.md` | 合并环境、四服务启动、首次上传和基础验证 |
| 配置说明 | `viewer/server/server_config.json`、服务 README | 汇总配置文件、环境变量、端口和数据目录 |
| Viewer 使用 | `docs/usage.md`、Viewer 实现 | 按真实用户工作流拆分，避免组件清单式重复 |
| 总体架构 | `docs/architecture/ai-bim.md`、`viewer-detail.md` | 保留稳定架构，删除阶段性汇报语气 |
| 子系统开发 | 四个 Viewer 子目录及 README | 各页说明职责、依赖、启动、关键边界和测试 |
| 测试与调试 | `viewer/docs/README.md`、根 README | 保留命令和覆盖边界，不硬编码测试数量 |
| Viewer REST API | `viewer/docs/api.md` | 校订为 Go server 当前公开契约 |
| IFC 编辑 API | `docs/ai-integration.md`、edit-service README | 建立 edit-service 端点唯一参考，避免重复定义 |
| AI 接入 | `docs/ai-integration.md` | 保留双角色、provenance 和完整调用流 |
| Roadmap | `roadmap.md`、`open-source-plan.md` | 公开版只保留已完成、近期、后续，不暴露内部 N+ 编号叙事 |
| 已知限制 | 架构文档和计划 | 汇总为唯一、明确、可维护页面 |

迁移允许拆分和重写。旧文件只有在所有有效内容已迁移、引用已更新后才可归档；不得先删除再补内容。

## 8. 状态校订基线

所有公开页面必须符合以下事实：

- 活跃产品是 `viewer/`，SimpleCADAPI 为归档代码。
- Viewer 已实现上传、转换、模型树、属性检查、可见性工具、Issue、3D Pin、真实 IFC 属性编辑、pending/commit、版本快照和属性级 diff。
- `viewer/edit-service/` 已落地，不能再描述为未来计划。
- diff 当前聚焦直接属性和 property set 语义变化，不宣称提供完整几何 diff。
- PostgreSQL 对 Issue、override 和 change store 是可选项，模型文件仍使用文件系统。
- Docker Compose 尚未完成时，不宣称支持一键部署。
- AI 与 UI 可以共享编辑 API，但 AI 生成 IFC、MCP 封装、认证和多用户不属于当前已交付功能。
- OpenAPI 当前是仓库内导出的静态文件，自动生成和漂移检测属于后续迭代。
- 不公开硬编码测试数量、个人本机路径、兄弟仓库路径或内部协作上下文。
- 已知的本地 `ifcdiff` 依赖和部署限制必须如实说明，直到实现发生变化。

## 9. 后续迭代记录

本轮需要更新公开 Roadmap 和内部迭代计划，明确记录：

### 9.1 双语扩展

- 第一版中文文档稳定后再增加英文 locale。
- 英文优先覆盖首页、快速开始、总体架构、贡献和 API 入口。
- 禁止仅创建空的英文导航或内容占位页。

### 9.2 API 自动生成

- 从 FastAPI OpenAPI schema 生成或同步 edit-service API 页面。
- 为 Go server 建立机器可读规范或等价的契约生成方式。
- CI 检测 schema 与已提交产物是否漂移。
- 人工指南继续解释工作流和语义，自动页面只负责字段与端点参考。

### 9.3 可选增强

- 文档截图和录屏。
- 版本化文档。
- 外部链接定期检查。

## 10. 质量与错误处理

- VitePress 构建不得通过全局忽略死链绕过错误。
- 内部链接、静态资源、Pages base path 必须在构建和上线后验证。
- 文档命令必须能从其声明的工作目录直接执行。
- 未安装可选 PostgreSQL 时，默认文件存储路径仍应可用。
- 页面涉及未交付能力时必须标记为 Roadmap，不得提供不可执行步骤。
- 移动或归档文档后，仓库内所有 Markdown 相对链接必须同步更新。

## 11. 验收标准

1. 在干净环境执行 `cd docs && npm ci && npm run docs:build` 成功。
2. Pull Request 会验证文档构建，`main` 会自动部署 Pages。
3. <https://0702hjj.github.io/AI_IFC/> 可访问，刷新深层页面不会因 base path 错误而丢失资源。
4. 所有主导航页面存在，且没有占位内容。
5. 新开发者仅使用公开文档即可启动 Viewer 四组件并上传样例 IFC。
6. 编辑、pending、commit、版本和 diff 的说明与当前实现一致。
7. 公开站点导航与搜索不暴露 SimpleCADAPI API、内部实施计划和团队同步材料。
8. README 指向正式文档站。
9. 公开 Roadmap 和内部计划均记录双语扩展及 API 自动生成，但第一版不实现它们。
10. 文档构建、现有 Viewer CI 和关键链接检查全部通过。
