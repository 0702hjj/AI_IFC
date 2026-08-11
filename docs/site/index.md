---
layout: home

hero:
  name: AI_IFC
  text: 两个对等逻辑 + Agent 工作流推荐项
  tagline: 自托管开源 AI 生成平台：AI 生成 IFC 与 AI 生成 CAD 各成闭环（skill + diff + 编辑 API），前端与 PG 可选。可复用性优先，接口可直接调用或移植。
  actions:
    - theme: brand
      text: 开始使用
      link: /guide/quickstart
    - theme: alt
      text: GitHub
      link: https://github.com/0702hjj/AI_IFC

features:
  - icon: ✏️
    title: 脚本编辑
    details: web 修改统一为改构建脚本：选中构件定位脚本调用点，PARAMS 表单或脚本编辑器改写，沙箱验证后暂存，保存即不可变大版本。
  - icon: 🔍
    title: 语义版本 diff
    details: 按 GlobalId 的属性级 diff：新增/删除/修改着色与 old → new 明细，不带几何噪声。
  - icon: 📜
    title: 脚本即事实源
    details: Python 构建脚本是 IFC 唯一事实源：沙箱执行、大版本成对快照、脚本 diff 两级粒度。
  - icon: 🤖
    title: 设计师/AI 双角色 API
    details: 人与 AI 共用同一套 REST 编辑 API，provenance 区分来源；OpenAPI 工具目录可直接喂给 LLM。
  - icon: 🔌
    title: MCP 接入
    details: MCP server 薄封装编辑 API（stdio），可解析用户在外部工具改后的 IFC/DXF 并标注 USER 来源。
  - icon: 🏠
    title: 自托管
    details: 四个本地进程即可跑全平台，文件存储零依赖；可选 PostgreSQL。AGPL-3.0 开源。
---

## 什么是 AI_IFC

AI_IFC 是一个自托管、开源的 **AI 生成平台**，提供两个对等的逻辑：

- **AI 生成 IFC**（已交付）：`aiifc` skill 让 AI 写 IfcOpenShell 代码生成/修改模型；`services/ifc`（edit-service）提供脚本沙箱执行、版本快照与语义 diff，以及面向前端修改的 script-as-source 编辑 API——浏览器里三维审查、对构件提 Issue、改 PARAMS/脚本、保存大版本、用 diff 对比变化，人与 AI 共用同一套 API。
- **AI 生成 CAD**（skill 域已交付，diff/编辑 API 待建）：`aidxfv` skill 让 AI 用 ezdxf 生成/校验 DXF；`services/cad` 将与 `services/ifc` 同构。
- **Agent 工作流控制**（推荐项，可选）：orchestrator + 事件总线（`aiifc://` 事件 URI），做不好可删。

可复用性优先：skill 封装两个、业务逻辑两个、前端可选、PostgreSQL 可选，接口写好可直接调用或移植。框架详见 [平台框架 spec](/project/roadmap) 指向的仓库 spec。

典型工作流（IFC）：上传 IFC → 转换完成后三维审查 → 对构件提 Issue → 选中构件定位脚本、改 PARAMS/脚本 → 沙箱验证后保存大版本 → 用 Diff 对比版本变化。定位与组件架构详见 [项目介绍](/guide/project-intro)。

## 界面截图

![三维查看器](/screenshots/viewer.png)

| 模型库 | 属性编辑 | 版本对比 | AI 对话 |
|---|---|---|---|
| ![模型库](/screenshots/library.png) | ![属性编辑](/screenshots/properties.png) | ![版本对比](/screenshots/diff.png) | ![AI 对话](/screenshots/chat.png) |

## 开始使用

1. [环境要求与本地部署](/guide/quickstart) — 装好依赖，用四个终端启动全部组件。
2. [上传第一个 IFC](/guide/first-ifc) — 上传样例模型，走一遍审查 → Issue → 编辑 → Diff 全流程。
3. [AI 接入](/reference/ai) — 把同一套编辑 API 开放给 AI agent。

## 链接

- [GitHub 仓库](https://github.com/0702hjj/AI_IFC) — 源码、Issue 与 PR
- [更新日志](/project/changelog) — 版本变更记录（当前 v0.1.0）
- [Roadmap](/project/roadmap) · [已知限制](/project/known-limits) · [贡献指南](/project/contributing)
