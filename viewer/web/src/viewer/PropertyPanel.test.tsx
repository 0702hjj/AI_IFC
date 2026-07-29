import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";

const mockCtx: { current: unknown } = { current: null };
vi.mock("./ViewerContext", () => ({ useViewer: () => mockCtx.current }));

import { PropertyPanel } from "./PropertyPanel";
import { useViewerStore } from "./store";

afterEach(cleanup);

const metaObject = {
  id: "w1",
  name: "Wall A",
  type: "IfcWall",
  parent: "st",
  propertySets: [
    {
      id: "pset1",
      name: "Pset_WallCommon",
      type: "Pset",
      properties: [
        { name: "FireRating", value: "120 min", type: "1" },
        { name: "LoadBearing", value: true, type: "3" },
      ],
    },
    {
      id: "pset2",
      name: "Pset_Geometry",
      type: "Pset",
      properties: [{ name: "Height", value: 3200, type: "4" }],
    },
  ],
};

function setup() {
  mockCtx.current = { metaModel: { metaObjects: { w1: metaObject } } };
  useViewerStore.setState({
    selectedId: null, tool: "select", hiddenIds: [], isolateId: null, xray: false,
  });
}

describe("PropertyPanel", () => {
  beforeEach(setup);

  it("shows empty state when nothing is selected", () => {
    render(<PropertyPanel />);
    expect(screen.getByText("点击构件查看属性")).toBeTruthy();
  });

  it("stays in empty state without a meta model even if selected", () => {
    mockCtx.current = null;
    useViewerStore.getState().setSelected("w1");
    render(<PropertyPanel />);
    expect(screen.getByText("点击构件查看属性")).toBeTruthy();
  });

  it("search filters properties by name or value", () => {
    useViewerStore.getState().setSelected("w1");
    render(<PropertyPanel />);
    fireEvent.change(screen.getByPlaceholderText("搜索属性"), {
      target: { value: "fire" },
    });
    expect(screen.getByText("FireRating")).toBeTruthy();
    expect(screen.queryByText("LoadBearing")).toBeNull();
  });

  it("second pset collapsed by default, expands on click", () => {
    useViewerStore.getState().setSelected("w1");
    render(<PropertyPanel />);
    expect(screen.queryByText("Height")).toBeNull();
    fireEvent.click(screen.getByText("Pset_Geometry"));
    expect(screen.getByText("Height")).toBeTruthy();
  });

  it("copy button writes name: value to clipboard", async () => {
    const writeText = vi.fn(async () => {});
    Object.assign(navigator, { clipboard: { writeText } });
    useViewerStore.getState().setSelected("w1");
    render(<PropertyPanel />);
    const row = screen.getByText("FireRating").closest("tr")!;
    fireEvent.click(row.querySelector("button.property-copy-btn")!);
    expect(writeText).toHaveBeenCalledWith("FireRating: 120 min");
  });
});
