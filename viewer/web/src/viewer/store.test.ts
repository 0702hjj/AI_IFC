import { describe, it, expect, beforeEach, vi } from "vitest";

const api = vi.hoisted(() => ({ fetchOverrides: vi.fn() }));
vi.mock("@/api/client", () => api);

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

describe("overrides", () => {
  beforeEach(() => {
    useViewerStore.setState({ overrides: {}, changesVersion: 0 });
    vi.clearAllMocks();
  });

  it("loadOverrides fetches overrides for a model into the store", async () => {
    api.fetchOverrides.mockResolvedValue({ w1: { Name: "Wall B" } });
    await useViewerStore.getState().loadOverrides("m1");
    expect(api.fetchOverrides).toHaveBeenCalledWith("m1");
    expect(useViewerStore.getState().overrides).toEqual({ w1: { Name: "Wall B" } });
  });

  it("setEntityOverrides replaces one entity's fields", () => {
    useViewerStore.setState({ overrides: { w1: { Name: "A" } } });
    useViewerStore.getState().setEntityOverrides("w1", { FireRating: "90 min" });
    expect(useViewerStore.getState().overrides).toEqual({ w1: { FireRating: "90 min" } });
  });

  it("setEntityOverrides removes the entity when fields are empty", () => {
    useViewerStore.setState({ overrides: { w1: { Name: "A" } } });
    useViewerStore.getState().setEntityOverrides("w1", {});
    expect(useViewerStore.getState().overrides).toEqual({});
  });

  it("bumpChanges increments changesVersion", () => {
    useViewerStore.getState().bumpChanges();
    expect(useViewerStore.getState().changesVersion).toBe(1);
  });
});
