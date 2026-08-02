// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj
import { defineConfig } from 'vitepress'

export default defineConfig({
  lang: 'zh-CN',
  title: 'AI_IFC',
  description: '自托管、开源的 IFC 审查与编辑平台',
  base: '/AI_IFC/',
  cleanUrls: true,
  lastUpdated: true,

  head: [
    ['meta', { name: 'theme-color', content: '#3fb950' }],
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/AI_IFC/favicon.svg' }],
  ],

  themeConfig: {
    nav: [
      { text: '快速开始', link: '/guide/project-intro' },
      { text: 'Viewer 使用', link: '/viewer/library' },
      { text: '开发指南', link: '/development/architecture' },
      { text: 'API 与 AI', link: '/reference/rest-api' },
      { text: '项目', link: '/project/roadmap' },
    ],

    sidebar: [
      {
        text: '快速开始',
        items: [
          { text: '项目介绍', link: '/guide/project-intro' },
          { text: '环境要求与本地部署', link: '/guide/quickstart' },
          { text: '上传第一个 IFC', link: '/guide/first-ifc' },
          { text: '配置说明', link: '/guide/configuration' },
        ],
      },
      {
        text: 'Viewer 使用',
        items: [
          { text: '模型库与模型上传', link: '/viewer/library' },
          { text: '模型树与属性检查', link: '/viewer/model-tree' },
          { text: '可见性、剖切与测量', link: '/viewer/viewing' },
          { text: 'Issue 与 3D Pin', link: '/viewer/issues' },
          { text: 'IFC 属性编辑', link: '/viewer/editing' },
          { text: '版本与 Diff Viewer', link: '/viewer/versions-diff' },
        ],
      },
      {
        text: '开发指南',
        items: [
          { text: '总体架构', link: '/development/architecture' },
          { text: '仓库结构', link: '/development/repo-structure' },
          { text: 'Web 前端', link: '/development/web' },
          { text: 'Go Server', link: '/development/server' },
          { text: 'IFC Converter', link: '/development/converter' },
          { text: 'Edit Service', link: '/development/edit-service' },
          { text: '测试与调试', link: '/development/testing' },
        ],
      },
      {
        text: 'API 与 AI',
        items: [
          { text: 'Viewer REST API', link: '/reference/rest-api' },
          { text: 'IFC 编辑 API', link: '/reference/edit-api' },
          { text: 'AI 接入', link: '/reference/ai' },
          { text: 'OpenAPI 文件', link: '/reference/openapi' },
        ],
      },
      {
        text: '项目',
        items: [
          { text: 'Roadmap', link: '/project/roadmap' },
          { text: '已知限制', link: '/project/known-limits' },
          { text: '贡献指南', link: '/project/contributing' },
          { text: 'License 与第三方组件', link: '/project/license' },
        ],
      },
    ],

    search: {
      provider: 'local',
      options: {
        translations: {
          button: { buttonText: '搜索文档', buttonAriaLabel: '搜索文档' },
          modal: {
            noResultsText: '未找到相关结果',
            resetButtonTitle: '清除查询条件',
            footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' },
          },
        },
      },
    },

    outline: { label: '本页目录', level: [2, 3] },
    lastUpdated: { text: '最后更新于' },
    docFooter: { prev: '上一篇', next: '下一篇' },
    returnToTopLabel: '返回顶部',
    sidebarMenuLabel: '菜单',
    darkModeSwitchLabel: '外观',
    lightModeSwitchTitle: '切换到浅色模式',
    darkModeSwitchTitle: '切换到深色模式',

    editLink: {
      pattern: 'https://github.com/0702hjj/AI_IFC/edit/main/docs/site/:path',
      text: '在 GitHub 上编辑此页',
    },

    socialLinks: [{ icon: 'github', link: 'https://github.com/0702hjj/AI_IFC' }],

    footer: {
      message: 'AGPL-3.0-only',
      copyright: 'Copyright © 2026 0702hjj',
    },
  },
})
