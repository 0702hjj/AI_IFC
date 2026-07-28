import { create } from "zustand";

export type ViewerTool = "select" | "measure";

interface ViewerState {
  selectedId: string | null;
  tool: ViewerTool;
  setSelected: (id: string | null) => void;
  setTool: (tool: ViewerTool) => void;
}

export const useViewerStore = create<ViewerState>((set) => ({
  selectedId: null,
  tool: "select",
  setSelected: (id) => set({ selectedId: id }),
  setTool: (tool) => set({ tool }),
}));
