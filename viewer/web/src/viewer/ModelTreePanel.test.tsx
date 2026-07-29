import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";

const mockCtx: { current: unknown } = { current: null };
vi.mock("./ViewerContext", () => ({ useViewer: () => mockCtx.current }));

import { ModelTreePanel } from "./ModelTreePanel";
import { useViewerStore } from "./store";

afterEach(cleanup);

const metaObjects = {
  p: { id: "p", name: "Project", type: "IfcProject", parent: null, propertySets: [] },
  st: { id: "st", name: "L1", type: "IfcBuildingStorey", parent: "p", propertySets: [] },
  w1: { id: "w1", name: "Wall A", type: "IfcWall", parent: "st", propertySets: [] },
  d1: { id: "d1", name: "Door A", type: "IfcDoor", parent: "st", propertySets: [] },
};

function setup() {
  mockCtx.current = {
    viewer: { cameraFlight: { flyTo: vi.fn() } },
    metaModel: { metaObjects },
  };
  useViewerStore.setState({
    selectedId: null, tool: "select", hiddenIds: [], isolateId: null, xray: false,
  });
}

describe("ModelTreePanel", () => {
  beforeEach(setup);

  it("renders tree nodes", () => {
    render(<ModelTreePanel />);
    expect(screen.getByText("Project")).toBeTruthy();
    expect(screen.getByText("Wall A")).toBeTruthy();
  });

  it("search filters nodes by name", () => {
    render(<ModelTreePanel />);
    fireEvent.change(screen.getByPlaceholderText("搜索名称或类型"), {
      target: { value: "door" },
    });
    expect(screen.getByText("Door A")).toBeTruthy();
    expect(screen.queryByText("Wall A")).toBeNull();
  });

  it("type filter shows only selected types", () => {
    render(<ModelTreePanel />);
    fireEvent.click(screen.getByLabelText("IfcDoor"));
    expect(screen.getByText("Door A")).toBeTruthy();
    expect(screen.queryByText("Wall A")).toBeNull();
  });

  it("hide button toggles hiddenIds in store", () => {
    render(<ModelTreePanel />);
    const row = screen.getByText("Wall A").closest("li")!;
    fireEvent.click(row.querySelector("button.tree-hide-btn")!);
    expect(useViewerStore.getState().hiddenIds).toEqual(["w1"]);
  });

  it("clicking node title selects and flies to entity", () => {
    render(<ModelTreePanel />);
    fireEvent.click(screen.getByText("Wall A"));
    expect(useViewerStore.getState().selectedId).toBe("w1");
    expect((mockCtx.current as { viewer: { cameraFlight: { flyTo: unknown } } }).viewer.cameraFlight.flyTo).toHaveBeenCalled();
  });
});
