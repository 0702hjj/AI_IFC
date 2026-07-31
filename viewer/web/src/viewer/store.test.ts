// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

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

describe("issues", () => {
  const sample = {
    id: "i_1", entityId: "w1", entityName: "Wall A", entityType: "IfcWall",
    title: "t", comment: "", status: "open" as const,
    camera: { eye: [1, 2, 3] as [number, number, number], look: [0, 0, 0] as [number, number, number], up: [0, 0, 1] as [number, number, number] },
    screenshot: "", createdAt: "", updatedAt: "",
  };

  beforeEach(() => {
    useViewerStore.setState({ issues: [], selectedIssueId: null });
  });

  it("upsertIssue prepends new issues and replaces existing ones", () => {
    useViewerStore.getState().upsertIssue(sample);
    useViewerStore.getState().upsertIssue({ ...sample, id: "i_2" });
    expect(useViewerStore.getState().issues.map((i) => i.id)).toEqual(["i_2", "i_1"]);
    useViewerStore.getState().upsertIssue({ ...sample, title: "updated" });
    const issues = useViewerStore.getState().issues;
    expect(issues.map((i) => i.id)).toEqual(["i_2", "i_1"]);
    expect(issues[1].title).toBe("updated");
  });

  it("removeIssue drops the issue and clears its selection", () => {
    useViewerStore.getState().setIssues([sample]);
    useViewerStore.getState().setSelectedIssue("i_1");
    useViewerStore.getState().removeIssue("i_1");
    expect(useViewerStore.getState().issues).toEqual([]);
    expect(useViewerStore.getState().selectedIssueId).toBeNull();
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
