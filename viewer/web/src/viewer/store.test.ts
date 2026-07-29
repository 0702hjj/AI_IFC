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

describe("visibility", () => {
  beforeEach(() => {
    useViewerStore.getState().resetVisibility();
  });

  it("toggleHidden adds and removes ids", () => {
    const s = useViewerStore.getState();
    s.toggleHidden("a");
    expect(useViewerStore.getState().hiddenIds).toEqual(["a"]);
    useViewerStore.getState().toggleHidden("a");
    expect(useViewerStore.getState().hiddenIds).toEqual([]);
  });

  it("isolate sets and clears isolateId", () => {
    useViewerStore.getState().isolate("a");
    expect(useViewerStore.getState().isolateId).toBe("a");
    useViewerStore.getState().isolate(null);
    expect(useViewerStore.getState().isolateId).toBeNull();
  });

  it("resetVisibility clears hidden/isolate/xray", () => {
    const s = useViewerStore.getState();
    s.toggleHidden("a");
    s.isolate("b");
    s.setXray(true);
    useViewerStore.getState().resetVisibility();
    const after = useViewerStore.getState();
    expect(after.hiddenIds).toEqual([]);
    expect(after.isolateId).toBeNull();
    expect(after.xray).toBe(false);
  });
});
