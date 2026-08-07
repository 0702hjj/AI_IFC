// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj
import { defineConfig } from 'vitepress'

export default defineConfig({
  base: '/AI_IFC/',
  cleanUrls: true,
  lastUpdated: true,

  head: [
    ['meta', { name: 'theme-color', content: '#3fb950' }],
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/AI_IFC/favicon.svg' }],
  ],

  locales: {
    root: {
      label: '简体中文',
      lang: 'zh-CN',
      title: 'AI_IFC',
      description: '自托管、开源的 IFC 审查与编辑平台',
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
              { text: '编辑 API 参考（自动生成）', link: '/reference/edit-api-reference' },
              { text: 'AI 接入', link: '/reference/ai' },
              { text: 'AI Skill（aiifc）', link: '/reference/ai-skill' },
              { text: 'Script 编辑与版本', link: '/reference/design-edit' },
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
    },

    en: {
      label: 'English',
      lang: 'en',
      title: 'AI_IFC',
      description: 'Self-hosted, open-source IFC review and editing platform',
      themeConfig: {
        nav: [
          { text: 'Quick Start', link: '/en/guide/project-intro' },
          { text: 'Architecture', link: '/en/development/architecture' },
          { text: 'API Reference', link: '/en/reference/rest-api' },
          { text: 'Contributing', link: '/en/project/contributing' },
        ],

        sidebar: [
          {
            text: 'Quick Start',
            items: [
              { text: 'Project Introduction', link: '/en/guide/project-intro' },
              { text: 'Environment & Local Deployment', link: '/en/guide/quickstart' },
              { text: 'Upload Your First IFC', link: '/en/guide/first-ifc' },
              { text: 'Configuration', link: '/en/guide/configuration' },
            ],
          },
          {
            text: 'Viewer Usage',
            items: [
              { text: 'Model Library & Upload', link: '/en/viewer/library' },
              { text: 'Model Tree & Property Inspection', link: '/en/viewer/model-tree' },
              { text: 'Visibility, Sectioning & Measurement', link: '/en/viewer/viewing' },
              { text: 'Issues & 3D Pins', link: '/en/viewer/issues' },
              { text: 'IFC Property Editing', link: '/en/viewer/editing' },
              { text: 'Versions & Diff Viewer', link: '/en/viewer/versions-diff' },
            ],
          },
          {
            text: 'Development',
            items: [
              { text: 'Architecture', link: '/en/development/architecture' },
            ],
          },
          {
            text: 'API & AI',
            items: [
              { text: 'Viewer REST API', link: '/en/reference/rest-api' },
              { text: 'IFC Editing API', link: '/en/reference/edit-api' },
              { text: 'Editing API Reference (generated)', link: '/reference/edit-api-reference' },
              { text: 'AI Integration', link: '/en/reference/ai' },
              { text: 'AI Skill (aiifc)', link: '/en/reference/ai-skill' },
              { text: 'Script Editing & Versions', link: '/en/reference/design-edit' },
              { text: 'OpenAPI Files', link: '/en/reference/openapi' },
            ],
          },
          {
            text: 'Project',
            items: [
              { text: 'Contributing', link: '/en/project/contributing' },
            ],
          },
        ],

        search: { provider: 'local' },

        outline: { label: 'On this page', level: [2, 3] },
        lastUpdated: { text: 'Last updated' },
        docFooter: { prev: 'Previous', next: 'Next' },
        returnToTopLabel: 'Back to top',
        sidebarMenuLabel: 'Menu',
        darkModeSwitchLabel: 'Appearance',
        lightModeSwitchTitle: 'Switch to light mode',
        darkModeSwitchTitle: 'Switch to dark mode',

        editLink: {
          pattern: 'https://github.com/0702hjj/AI_IFC/edit/main/docs/site/:path',
          text: 'Edit this page on GitHub',
        },

        socialLinks: [{ icon: 'github', link: 'https://github.com/0702hjj/AI_IFC' }],

        footer: {
          message: 'AGPL-3.0-only',
          copyright: 'Copyright © 2026 0702hjj',
        },
      },
    },
  },
})
