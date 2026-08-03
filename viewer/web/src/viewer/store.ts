// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import { create } from "zustand";
import { fetchOverrides } from "@/api/client";
import type { EntityFields, Issue, OverridesMap } from "@/api/types";

export type ViewerTool = "select" | "measure";

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
}));
