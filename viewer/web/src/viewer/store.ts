import { create } from "zustand";
import { fetchOverrides } from "@/api/client";
import type { EntityFields, OverridesMap } from "@/api/types";

export type ViewerTool = "select" | "measure";

interface ViewerState {
  selectedId: string | null;
  tool: ViewerTool;
  hiddenIds: string[];
  isolateId: string | null;
  xray: boolean;
  overrides: OverridesMap;
  changesVersion: number;
  setSelected: (id: string | null) => void;
  setTool: (tool: ViewerTool) => void;
  toggleHidden: (id: string) => void;
  isolate: (id: string | null) => void;
  setXray: (v: boolean) => void;
  resetVisibility: () => void;
  loadOverrides: (modelId: string) => Promise<void>;
  setEntityOverrides: (entityId: string, fields: EntityFields) => void;
  bumpChanges: () => void;
}

export const useViewerStore = create<ViewerState>((set) => ({
  selectedId: null,
  tool: "select",
  hiddenIds: [],
  isolateId: null,
  xray: false,
  overrides: {},
  changesVersion: 0,
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
}));
