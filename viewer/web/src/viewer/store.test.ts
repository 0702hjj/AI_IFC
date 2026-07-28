import { describe, it, expect, beforeEach } from "vitest";
import { useViewerStore } from "./store";

beforeEach(() => {
  useViewerStore.setState({ selectedId: null, tool: "select" });
});

describe("viewer store", () => {
  it("defaults to no selection and select tool", () => {
    const s = useViewerStore.getState();
    expect(s.selectedId).toBeNull();
    expect(s.tool).toBe("select");
  });

  it("setSelected updates selectedId", () => {
    useViewerStore.getState().setSelected("wall-1");
    expect(useViewerStore.getState().selectedId).toBe("wall-1");
    useViewerStore.getState().setSelected(null);
    expect(useViewerStore.getState().selectedId).toBeNull();
  });

  it("setTool switches tools", () => {
    useViewerStore.getState().setTool("measure");
    expect(useViewerStore.getState().tool).toBe("measure");
  });
});
