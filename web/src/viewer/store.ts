// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import { create } from "zustand";
import { fetchOverrides } from "@/api/client";
import type { EntityFields, Issue, OverridesMap, ScriptLocateOrigin } from "@/api/types";

export type ViewerTool = "select" | "measure";

// 定位脚本：PropertyPanel 请求 locate 后置入，DesignPanel 消费（跳行 / PARAMS 表单聚焦）
// 并清零。nonce 保证同一行重复跳转也会触发消费方 effect。
export interface ScriptJump {
  line: number;
  origin?: ScriptLocateOrigin;
  paramsKeys?: string[]; // origin=params 时的 PARAMS 表单聚焦键（W-0022）
  nonce: number;
}

// AI run_script 沙箱成功后的中间产物预览信号（viewer.staged，ChatSidebar 监听写入）。
// ViewerPage 按管线分流消费：dxf/webifc 直挂自动重载，xeokit 出角标点击才重载。
// nonce 递增保证同一 model 连续多次 staged 也能触发消费方 effect。
export interface StagedPreview {
  modelId: string;
  kind: "ifc" | "dxf";
  nonce: number;
}

interface ViewerState {
  selectedId: string | null;
  tool: ViewerTool;
  hiddenIds: string[];
  isolateId: string | null;
  xray: boolean;
  overrides: OverridesMap;
  changesVersion: number;
  issues: Issue[];
  selectedIssueId: string | null;
  diffOpen: boolean;
  chatOpen: boolean;
  pendingModelReload: boolean; // AI commit 后（viewer.committed）置 true；前端轮询到 ready 即 reload 并清零
  stagedPreview: StagedPreview | null; // AI run_script 中间产物（viewer.staged）；消费方按 nonce 触发
  modelCreated: { modelId: string; kind: string; nonce: number } | null; // AI init_model 新模型（model.created）；消费方切渲染并清零
  scriptJump: ScriptJump | null;
  setSelected: (id: string | null) => void;
  setTool: (tool: ViewerTool) => void;
  toggleHidden: (id: string) => void;
  isolate: (id: string | null) => void;
  setXray: (v: boolean) => void;
  resetVisibility: () => void;
  loadOverrides: (modelId: string) => Promise<void>;
  setEntityOverrides: (entityId: string, fields: EntityFields) => void;
  bumpChanges: () => void;
  setIssues: (issues: Issue[]) => void;
  upsertIssue: (issue: Issue) => void;
  removeIssue: (id: string) => void;
  setSelectedIssue: (id: string | null) => void;
  setDiffOpen: (open: boolean) => void;
  setChatOpen: (open: boolean) => void;
  flagPendingModelReload: () => void;
  clearPendingModelReload: () => void;
  flagStagedPreview: (p: { modelId: string; kind: "ifc" | "dxf" }) => void;
  flagModelCreated: (p: { modelId: string; kind: string }) => void;
  clearModelCreated: () => void;
  requestScriptJump: (jump: {
    line: number;
    origin?: ScriptLocateOrigin;
    paramsKeys?: string[];
  }) => void;
  clearScriptJump: () => void;
}

export const useViewerStore = create<ViewerState>((set) => ({
  selectedId: null,
  tool: "select",
  hiddenIds: [],
  isolateId: null,
  xray: false,
  overrides: {},
  changesVersion: 0,
  issues: [],
  selectedIssueId: null,
  diffOpen: false,
  chatOpen: false,
  pendingModelReload: false,
  stagedPreview: null,
  modelCreated: null,
  scriptJump: null,
  setSelected: (id) => set({ selectedId: id }),
  setTool: (tool) => set({ tool }),
  toggleHidden: (id) =>
    set((s) => ({
      hiddenIds: s.hiddenIds.includes(id)
        ? s.hiddenIds.filter((x) => x !== id)
        : [...s.hiddenIds, id],
    })),
  isolate: (id) => set({ isolateId: id }),
  setXray: (v) => set({ xray: v }),
  resetVisibility: () => set({ hiddenIds: [], isolateId: null, xray: false }),
  loadOverrides: async (modelId) => {
    const all = await fetchOverrides(modelId);
    set({ overrides: all ?? {} });
  },
  setEntityOverrides: (entityId, fields) =>
    set((s) => {
      const overrides = { ...s.overrides };
      if (Object.keys(fields).length === 0) delete overrides[entityId];
      else overrides[entityId] = fields;
      return { overrides };
    }),
  bumpChanges: () => set((s) => ({ changesVersion: s.changesVersion + 1 })),
  setIssues: (issues) => set({ issues }),
  upsertIssue: (issue) =>
    set((s) => ({
      issues: s.issues.some((x) => x.id === issue.id)
        ? s.issues.map((x) => (x.id === issue.id ? issue : x))
        : [issue, ...s.issues],
    })),
  removeIssue: (id) =>
    set((s) => ({
      issues: s.issues.filter((x) => x.id !== id),
      selectedIssueId: s.selectedIssueId === id ? null : s.selectedIssueId,
    })),
  setSelectedIssue: (id) => set({ selectedIssueId: id }),
  setDiffOpen: (open) => set({ diffOpen: open }),
  setChatOpen: (open) => set({ chatOpen: open }),
  flagPendingModelReload: () => set({ pendingModelReload: true }),
  clearPendingModelReload: () => set({ pendingModelReload: false }),
  flagStagedPreview: (p) =>
    set((s) => ({ stagedPreview: { ...p, nonce: (s.stagedPreview?.nonce ?? 0) + 1 } })),
  flagModelCreated: (p) =>
    set((s) => ({ modelCreated: { ...p, nonce: (s.modelCreated?.nonce ?? 0) + 1 } })),
  clearModelCreated: () => set({ modelCreated: null }),
  requestScriptJump: (jump) =>
    set((s) => ({ scriptJump: { ...jump, nonce: (s.scriptJump?.nonce ?? 0) + 1 } })),
  clearScriptJump: () => set({ scriptJump: null }),
}));
