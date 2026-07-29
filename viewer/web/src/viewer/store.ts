import { create } from "zustand";

export type ViewerTool = "select" | "measure";

interface ViewerState {
  selectedId: string | null;
  tool: ViewerTool;
  hiddenIds: string[];
  isolateId: string | null;
  xray: boolean;
  setSelected: (id: string | null) => void;
  setTool: (tool: ViewerTool) => void;
  toggleHidden: (id: string) => void;
  isolate: (id: string | null) => void;
  setXray: (v: boolean) => void;
  resetVisibility: () => void;
}

export const useViewerStore = create<ViewerState>((set) => ({
  selectedId: null,
  tool: "select",
  hiddenIds: [],
  isolateId: null,
  xray: false,
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
}));
