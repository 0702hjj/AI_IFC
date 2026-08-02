---
layout: home

hero:
  name: AI_IFC
  text: IFC 审查与编辑平台
  tagline: 自托管、开源。在浏览器里审查 IFC 模型、真实修改属性、做语义版本对比，并把同一套编辑 API 开放给人与 AI。
  actions:
    - theme: brand
      text: 快速开始
      link: /guide/project-intro
    - theme: alt
      text: 上传第一个 IFC
      link: /guide/first-ifc

features:
  - title: 三维审查
    details: 上传 IFC 即转为 XKT 快速渲染；模型树、属性检查、剖切、测量与 3D Issue 钉一应俱全。
  - title: 真实编辑
    details: 属性 override 与 pending → commit 两阶段真改 IFC，每次 commit 生成不可变版本快照。
  - title: 语义版本对比
    details: 按 GlobalId 的属性级 diff：新增/删除/修改着色与 old → new 明细，不带几何噪声。
  - title: 人 / AI 双角色
    details: 人与 AI 共用同一套 REST 编辑 API，provenance 区分 UI / AI；OpenAPI 工具目录可直接喂给 LLM。
---

## 它能做什么

AI_IFC 是一个 IFC（Industry Foundation Classes）模型的审查与编辑平台，由四个组件构成：

- **web**：React + xeokit 浏览器端，负责模型库、三维查看、属性检查、Issue、属性编辑与版本对比。
- **server**：Go 后端，负责上传、转换队列、REST API 与编辑编排，存储可选文件或 PostgreSQL。
- **converter**：Node 转换器，把 IFC 转为 XKT 几何与语义元数据。
- **edit-service**：Python（FastAPI + IfcOpenShell）编辑服务，负责真改 IFC、版本快照与语义 diff。

典型工作流：上传 IFC → 转换完成后三维审查 → 对构件提 Issue → 编辑属性（override 或真改）→ commit 生成版本 → 用 Diff 对比版本变化。

## 开始路径

1. [项目介绍](/guide/project-intro) — 了解定位、能力边界与四组件架构。
2. [环境要求与本地部署](/guide/quickstart) — 装好依赖，用四个终端启动全部组件。
3. [上传第一个 IFC](/guide/first-ifc) — 上传样例模型，走一遍审查 → Issue → 编辑 → Diff 全流程。
4. [Viewer REST API](/reference/rest-api) 与 [IFC 编辑 API](/reference/edit-api) — 接口契约；[AI 接入](/reference/ai) 面向 AI agent。

## 项目状态

平台已端到端可用（上传 → 转换 → 审查 → 编辑 → commit → diff）。当前仓库以 `viewer/` 为活跃产品；仓库历史中的 SimpleCADAPI（SCAD）代码作为归档保留，详见 [License 与第三方组件](/project/license)。

版本路线见 [Roadmap](/project/roadmap)，已知边界见 [已知限制](/project/known-limits)。
